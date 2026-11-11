"""Audio I/O independent of removed TorchAudio backend APIs."""

import io
from math import gcd

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def load_audio(source, sample_rate: int) -> np.ndarray:
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    audio, original_rate = sf.read(source, dtype="float32", always_2d=True)
    audio = audio.mean(axis=1)
    if not len(audio) or not np.isfinite(audio).all():
        raise ValueError("Audio is empty or contains non-finite samples")
    if original_rate != sample_rate:
        divisor = gcd(original_rate, sample_rate)
        audio = resample_poly(audio, sample_rate // divisor, original_rate // divisor)
    return np.asarray(audio, dtype=np.float32)
