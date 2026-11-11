"""Original TransDhTask.concat_watermark audio/video mux, without shell interpolation.

Despite its original function name this image's implementation has no watermark
overlay/filter. It encodes H264 CRF15 plus AAC, checks that output is nonempty.
Never invent a watermark based only on the parameter/function name.
"""
from pathlib import Path
import subprocess


def mux_command(video_path, audio_path, output_path, ffmpeg='ffmpeg'):
    return [str(ffmpeg), '-loglevel', 'warning', '-y', '-i', str(video_path),
            '-i', str(audio_path), '-c:a', 'aac', '-c:v', 'libx264', '-crf', '15',
            '-strict', '-2', str(output_path)]


def concat_watermark(video_path, audio_path, output_path, ffmpeg='ffmpeg'):
    output = Path(output_path)
    if output.resolve() in (Path(video_path).resolve(), Path(audio_path).resolve()):
        raise ValueError('Mux output must differ from both inputs')
    subprocess.run(mux_command(video_path, audio_path, output, ffmpeg), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError('ffmpegcmd some failed, size 0')
    return output
