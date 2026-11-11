"""Portable original Duix reference audio pipeline (official Fish image source).

RNNoise must use the native source build supplied by this recipe. This preserves
segmentation and samples while keeping the caller's upload intact. It deliberately
uses a private session directory rather than deleting the original upload as the
upstream format_wav helper does.
"""
from pathlib import Path
import subprocess
from pydub import AudioSegment
from pydub.silence import split_on_silence


def select_reference_chunks(audio_path, silence_thresh=-40):
    """Same _process_audio selection order and millisecond boundaries as upstream."""
    audio = AudioSegment.from_file(audio_path)
    chunks = split_on_silence(audio, min_silence_len=500,
                              silence_thresh=silence_thresh, keep_silence=400)
    valid_chunks = [c for c in chunks if 10000 <= len(c) <= 20000]
    if len(valid_chunks) >= 2:
        return valid_chunks[:2]
    merged, current_segments, current_duration = [], [], 0
    for chunk in chunks:
        chunk_len = len(chunk)
        if current_duration + chunk_len > 20000:
            if 10000 <= current_duration <= 20000:
                merged.append(sum(current_segments))
                if len(merged) >= 2:
                    break
            current_segments = [chunk] if chunk_len <= 20000 else []
            current_duration = chunk_len if chunk_len <= 20000 else 0
        else:
            current_segments.append(chunk)
            current_duration += chunk_len
        if 10000 <= current_duration <= 20000:
            merged.append(sum(current_segments))
            if len(merged) >= 2:
                break
            current_segments, current_duration = [], 0
    if len(merged) < 2 and 10000 <= current_duration <= 20000:
        merged.append(sum(current_segments))
    if len(merged) == 0:
        merged = [audio[0:20000]]
    return merged[:2]


def split_reference_audio(input_file, output_dir):
    """Return one short original or up to two exported 10–20 second references."""
    input_file, output_dir = Path(input_file), Path(output_dir)
    if len(AudioSegment.from_file(input_file)) < 20000:
        return [input_file]
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, audio in enumerate(select_reference_chunks(input_file)):
        output = output_dir / f'{input_file.stem}_part{i}.wav'
        audio.export(output, format='wav')
        paths.append(output)
    return paths


def preprocess_reference_audio(input_file, session_dir, rnnoise_binary, ffmpeg='ffmpeg'):
    """Format entire audio, apply original RNNoise, reformat, then select references.

    Channel count is preserved, matching the official ffmpeg command. No arbitrary
    20/30 second input truncation is applied. Returns paths suitable for FunASR.
    """
    input_file = Path(input_file).resolve(strict=True)
    session_dir = Path(session_dir).resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    first = session_dir / 'format_raw.wav'
    denoised = session_dir / 'denoise_raw.wav'
    final = session_dir / 'format_denoise_raw.wav'
    if input_file in (first, denoised, final):
        raise ValueError('input must be outside the generated session files')
    def format_wav(source, target):
        subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', str(source),
                        '-ar', '16000', '-c:a', 'pcm_s16le', str(target)],
                       check=True, stdin=subprocess.DEVNULL)
    format_wav(input_file, first)
    subprocess.run([str(rnnoise_binary), str(first), str(denoised)], check=True,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    if not denoised.is_file() or denoised.stat().st_size <= 44:
        raise RuntimeError('RNNoise did not produce a valid audio file')
    format_wav(denoised, final)
    return split_reference_audio(final, session_dir)
