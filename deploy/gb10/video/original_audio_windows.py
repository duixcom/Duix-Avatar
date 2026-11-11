"""Original 2025 Duix audio-window alignment recovered from its x86 extension.

The full differential evidence is audio-window-equivalence.json. This function
does not run WeNet or optional VAD. Features must be the original [T, 256]
WeNet output, including the model's original waveform edge padding. Optional
VAD should modify features before this function, as the original service does.
"""
import numpy as np


def get_windows(features, duration, fps):
    """Return int(duration*fps) original 20x256 feature views.

    Alignment is int(i * (T - 20) / (N - 1)), including both endpoints.
    The original extension also raises ZeroDivisionError when N == 1.
    Reject fewer than 20 feature steps instead of forwarding invalid shapes.
    """
    features = np.asarray(features)
    if features.ndim != 2 or features.shape[1] != 256:
        raise ValueError('Expected original WeNet features with shape [T, 256]')
    if features.shape[0] < 20:
        raise ValueError('Original DINet requires at least 20 WeNet feature steps')
    count = int(duration * fps)
    result = []
    for index in range(count):
        center = int(index * (features.shape[0] - 20) / (count - 1)) + 10
        result.append(features[center - 10:center + 10])
    return result
