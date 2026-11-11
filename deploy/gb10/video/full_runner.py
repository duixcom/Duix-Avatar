"""Native current Duix video pipeline with bounded source-frame memory.

Original DINet/WeNet, SCRFD/PFPLD/WHENet, source restoration and landmark
blending are composed here. Export and native CUDA checks are separate tools.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time

from runner import probe_media, run_command
from original_runner import OriginalDuixRunner
from bounded_frames import BoundedFrames, source_frame_index


class FullOriginalRunner(OriginalDuixRunner):
    engine = 'Duix original DINetV1 + WeNet + source GFPGAN + landmark blending'

    def __init__(self, root='/models/video', full_root='/models/video', max_duration=1800,
                 batch_size=2, blend_dynamic='lmk', enhancement=True):
        super().__init__(root, batch_size=batch_size)
        if not math.isfinite(max_duration) or not 0 < max_duration <= 1800:
            raise ValueError('Audio limit must be in (0, 1800] seconds')
        if blend_dynamic not in ('lmk', 'xseg', 'static'):
            raise ValueError('Unknown original blend mode')
        self.full_root = Path(full_root).resolve()
        self.max_duration = max_duration
        self.max_video_side = None
        self.blend_dynamic = blend_dynamic
        self.enhancement = enhancement
        self.full_loaded = False

    def _load(self):
        if self.full_loaded:
            return
        super()._load()
        from latest_crop_adapter import LatestCropAdapter
        from latest_headpose import Headpose
        from latest_preprocess import LatestPreprocessor
        from original_enhancement import OriginalGFPGAN, OriginalFaceAttr, OriginalXseg
        from original_face_detect import session_options
        from trt_session import TensorRTSession
        import onnxruntime as ort

        manifest = json.loads((self.full_root / 'full-model-manifest.json').read_text())
        for record in manifest['files']:
            path = self.full_root / record['path']
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                    digest.update(chunk)
            if digest.hexdigest() != record['sha256']:
                raise RuntimeError('Original extra model checksum mismatch: ' + record['path'])
        models = self.full_root / 'models'
        head_session = ort.InferenceSession(str(models / 'face_detect_utils/resources/model_float32.onnx'),
                                           session_options(2), providers=['CPUExecutionProvider'])
        self.headpose = Headpose(None, session=head_session)
        self.preprocessor = LatestPreprocessor(self.metadata['wh'], self.detector, self.landmarks,
                                               self.headpose, self.adapter.img_size, driver_flag=False)
        self.xseg = OriginalXseg(models / 'xseg/xseg_211104_4790000.onnx') if self.blend_dynamic == 'xseg' else None
        self.adapter = LatestCropAdapter(self.adapter.netG, self.metadata, device='cuda', xseg=self.xseg)
        if self.enhancement:
            self.gfpgan = OriginalGFPGAN(models / 'pretrain_models/face_lib/face_restore/gfpgan/GFPGANv1.4.onnx',
                                        session=TensorRTSession(models / 'gfpgan-gb10-fp32.engine'))
            self.face_attr = OriginalFaceAttr(models / 'face_attr_detect/face_attr_epoch_12_220318.onnx')
        self.full_loaded = True

    def __call__(self, video, audio, output, progress, options=None):
        from original_audio_windows import get_windows
        from original_audio_silence import apply_default_silence
        from original_enhancement import OriginalSourceEnhancer
        from original_face_geometry import paste_crop
        from original_mux import mux_command
        import soundfile as sf

        video, audio, output = Path(video), Path(audio), Path(output)
        if output.exists() or output.is_symlink():
            raise FileExistsError('Output file already exists')
        options = options or {'pn': 1}
        progress(2, 'Checking input media')
        source_info = probe_media(video, 'video', float('inf'))
        audio_info = probe_media(audio, 'audio', self.max_duration)
        self._load()
        cv2, np = self.cv2, self.np
        timeout = max(120, audio_info['duration'] * 5)
        with tempfile.TemporaryDirectory(prefix='.duix-full-' + output.stem + '-', dir=output.parent) as directory:
            scratch = Path(directory)
            normalized_audio = scratch / 'audio.wav'
            normalized_video = scratch / 'source.mp4'
            capture = cv2.VideoCapture(str(video))
            source_fourcc = int(capture.get(cv2.CAP_PROP_FOURCC))
            capture.release()
            copy_video = source_fourcc in {cv2.VideoWriter_fourcc(*name) for name in ('H264', 'avc1', 'h264')}
            # Preserve the original format_video_audio branch: H264 is
            # remuxed; other codecs are converted to H264 CRF15, without
            # changing frame rate or dimensions.
            run_command(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                         '-i', video, '-c:v', 'copy' if copy_video else 'libx264',
                         '-crf', '15', '-an', normalized_video], max(120, source_info['duration'] * 5))
            run_command(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                         '-i', audio, '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', normalized_audio], timeout)
            samples, rate = sf.read(normalized_audio)
            duration = len(samples) / rate
            with BoundedFrames(normalized_video, block_size=8) as source:
                fps = float('%.2f' % source.fps)
                if not math.isfinite(fps) or fps <= 0:
                    raise ValueError('Source video has invalid frame rate')
                first = source.read(0)
                height, width = (int(size // 2 * 2) for size in first.shape[:2])
                if int(duration * fps) < 2:
                    raise ValueError('Audio must span at least two video frames')
                del first
                progress(6, 'Extracting original WeNet speech features on CUDA')
                features = self.wenet.extract(normalized_audio)
                if not np.isfinite(features).all():
                    raise RuntimeError('Original WeNet returned non-finite features')
                silence = np.load(self.root / 'face-models/silence_fu.npy', allow_pickle=False)
                apply_default_silence(features, samples, rate, silence)
                windows = get_windows(features, duration, fps)
                enhancer = OriginalSourceEnhancer(self.gfpgan, self.detector, self.face_attr,
                    batch_size=self.batch_size) if self.enhancement else None
                silent = scratch / 'silent.avi'
                writer = cv2.VideoWriter(str(silent), cv2.VideoWriter_fourcc(*'XVID'), fps, (width, height))
                if not writer.isOpened():
                    raise RuntimeError('Cannot initialize the video encoder')
                rejected, enhanced, batches = 0, 0, 0
                try:
                    for start in range(0, len(windows), self.batch_size):
                        count = min(self.batch_size, len(windows) - start)
                        frames = [source.read(source_frame_index(start + offset, source.count, options.get('pn', 1) == 1))
                                  for offset in range(count)]
                        frames = [cv2.resize(frame, (width, height)) if frame.shape[:2] != (height, width) else frame
                                  for frame in frames]
                        if enhancer:
                            frames = enhancer.process_batch(frames, start + count)
                            enhanced += count if enhancer.need_chaofen else 0
                        entries, no_face = self.preprocessor.process_batch(frames, batches)
                        crops = self.adapter.inference_notraining(windows[start:start + count], entries, count, 0,
                            blend_dynamic=self.blend_dynamic, frameId=start + count)
                        if len(crops) != count:
                            raise RuntimeError('Original DINet returned an incomplete batch')
                        for index, crop in enumerate(crops):
                            # Honor the original no_face recovery intent while
                            # fixing its alias bug: the fallback source must
                            # not already contain a pasted placeholder crop.
                            frame = frames[index] if index in no_face else paste_crop(
                                frames[index].copy(), crop, entries[index]['bounding_box'], (height, width))
                            if frame.dtype != np.uint8 or frame.shape != (height, width, 3):
                                raise RuntimeError('Original compositor returned an invalid frame')
                            writer.write(frame)
                        rejected += len(no_face)
                        batches += 1
                        progress(15 + int(77 * (start + count) / len(windows)), 'Rendering original Duix models on GB10')
                finally:
                    writer.release()
                metrics = dict(frames=len(windows), source_frames=source.count,
                               source_fps=source.fps, processing_fps=fps,
                               rejected_face_frames=rejected, source_enhancement_frames=enhanced,
                               peak_cached_frames=source.peak_cached_frames, batch_size=self.batch_size,
                               reference_playback='ping-pong' if options.get('pn', 1) == 1 else 'forward-loop')
            progress(95, 'Encoding original H264 CRF15 and AAC output')
            result = scratch / 'result.mp4'
            run_command(mux_command(silent, audio, result), timeout)
            final_info = probe_media(result, 'video', self.max_duration + 1)
            probe_media(result, 'audio', self.max_duration + 1)
            if abs(final_info['duration'] - duration) > max(.2, 1 / fps):
                raise RuntimeError('Generated video duration does not match its audio')
            os.link(result, output)
            metrics.update(final_info)
            self.last_metrics = metrics
        progress(99, 'Original Duix video ready')
        return final_info


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='/models/video')
    p.add_argument('--full-root', default='/models/video')
    p.add_argument('--video', required=True)
    p.add_argument('--audio', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--pn', type=int, default=1)
    p.add_argument('--blend', default='lmk')
    p.add_argument('--report')
    args = p.parse_args()
    renderer = FullOriginalRunner(args.root, args.full_root, blend_dynamic=args.blend)
    started = time.perf_counter()
    renderer(args.video, args.audio, args.output,
             lambda progress, message: print(json.dumps(dict(progress=progress, message=message,
                  seconds=round(time.perf_counter() - started, 3))), flush=True), options={'pn': args.pn})
    if args.report:
        Path(args.report).write_text(json.dumps(dict(renderer.last_metrics,
            seconds=time.perf_counter()-started), indent=2) + '\n')


if __name__ == '__main__':
    main()
