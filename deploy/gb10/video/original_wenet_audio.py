"""Portable original Duix 5090 log-mel frontend and WeNet waveform wrapper.

Frontend recovered from official wenet/tools/_extract_feats.py, using the
official 5090 dependency list's librosa 0.11.0 semantics. This is the original
custom log-mel path; the unused Kaldi MFCC/fbank path is not substituted.
"""
from pathlib import Path

import librosa
import numpy as np
from scipy import signal
import torch


SAMPLE_RATE = 16000


class OriginalWenet:
    def __init__(self, torchscript_path, device='cpu'):
        self.device = torch.device(device)
        self.model = torch.jit.load(str(torchscript_path), map_location=self.device).eval()

    def extract(self, wav_path):
        return waveform_features(self.model, wav_path, self.device)


def load_wav(value):
    if isinstance(value, (str, Path)):
        return librosa.load(str(value), sr=SAMPLE_RATE)[0]
    return np.asarray(value)


def log_mel(waveform):
    # Preserve SciPy lfilter float64 and original power2db(+1e-5), no peak
    # normalization, no CMVN, no rescaling by 32768.
    emphasized = signal.lfilter([1, -0.97], [1], waveform)
    spectrum = librosa.stft(emphasized, n_fft=1024, hop_length=160,
                           win_length=800, window='hann', center=True,
                           pad_mode='constant')
    power = np.abs(spectrum.T) ** 2
    basis = librosa.filters.mel(sr=16000, n_fft=1024, n_mels=80,
                               fmin=0.0, fmax=None)
    mel = np.dot(basis, power.T).T
    return 10.0 * np.log10(mel + 1e-5) - 20


def encode_chunk(model, waveform, device):
    mel = log_mel(waveform)
    feats = torch.from_numpy(mel).float().to(device).unsqueeze(0)
    lengths = torch.tensor([mel.shape[0]], dtype=torch.int64, device=device)
    with torch.inference_mode():
        return model(feats, lengths).squeeze(0).cpu().numpy()


def waveform_features(model, waveform, device='cpu', section=560000):
    """Original current 5090 compute_bnf behavior, checked against compiled .so.

    section is accepted for API compatibility: original .so ignores it and
    uses chunks of 560,000 samples. Leading/trailing 0.4s zeros are retained.
    """
    waveform = np.concatenate((np.zeros(6400), load_wav(waveform), np.zeros(6400)))
    result = []
    for i in range(len(waveform) // 560000 + 1):
        chunk = waveform[560000 * i:560000 * (i + 1)]
        add_silence = len(chunk) < SAMPLE_RATE
        if add_silence:
            chunk = np.append(chunk, np.zeros(SAMPLE_RATE))
        output = encode_chunk(model, chunk, device)
        result.append(output[:-25] if add_silence else output)
    return np.concatenate(result, axis=0)
