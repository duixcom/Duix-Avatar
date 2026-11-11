"""Original Duix amplitude-based silence handling (VAD=False path).

Preserves the original 1600-sample windows, 1000-sample stride and 25 Hz
feature indexing. The learned optional VAD model is outside this module.
"""
import numpy as np


def silence_intervals(waveform, sample_rate):
    waveform = np.asarray(waveform)
    if waveform.ndim != 1:
        raise ValueError('Original silence adapter expects mono waveform')
    hop_length = int(sample_rate / 10)
    duration = len(waveform) / sample_rate
    start = 0.0
    result = []
    for offset in range(0, len(waveform) - hop_length, 1000):
        if not np.all(np.abs(waveform[offset:offset + hop_length]) <= 0.05):
            end = offset / sample_rate
            if end - start > 0.5:
                result.append([start, end])
            start = (offset + hop_length) / sample_rate
    if duration - start >= 0.5:
        result.append([start, duration])
    return result


def apply_silence_intervals(features, intervals, duration, silence_vector):
    """Mutate [T,256] features as original get_new_wenet does before windows."""
    features = np.asarray(features)
    silence_vector = np.asarray(silence_vector).reshape(-1)
    if features.ndim != 2 or features.shape[1] != 256 or silence_vector.shape != (256,):
        raise ValueError('Expected original [T,256] features and [256] silence vector')
    for start, end in intervals:
        first = 0 if start == 0 else int(start * 25) + 10
        stop = len(features) if end == duration else int(end * 25) - 10
        for index in range(first, stop):
            features[index] = silence_vector
    return features


def apply_default_silence(features, waveform, sample_rate, silence_vector):
    return apply_silence_intervals(features, silence_intervals(waveform, sample_rate),
                                  len(waveform) / sample_rate, silence_vector)
