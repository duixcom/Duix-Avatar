"""Pure Torch mel filter bank functions from PyTorch Audio v2.10.0.

Source: https://github.com/pytorch/audio/blob/v2.10.0/src/torchaudio/functional/functional.py
Copyright holders and BSD license: see TORCHAUDIO_LICENSE beside this module.
Only these four pure functions are copied; no native TorchAudio module is used.
"""

import math
import warnings
from typing import Optional
import torch
from torch import Tensor

def _hz_to_mel(freq: float, mel_scale: str = "htk") -> float:
    r"""Convert Hz to Mels.

    Args:
        freqs (float): Frequencies in Hz
        mel_scale (str, optional): Scale to use: ``htk`` or ``slaney``. (Default: ``htk``)

    Returns:
        mels (float): Frequency in Mels
    """

    if mel_scale not in ["slaney", "htk"]:
        raise ValueError('mel_scale should be one of "htk" or "slaney".')

    if mel_scale == "htk":
        return 2595.0 * math.log10(1.0 + (freq / 700.0))

    # Fill in the linear part
    f_min = 0.0
    f_sp = 200.0 / 3

    mels = (freq - f_min) / f_sp

    # Fill in the log-scale part
    min_log_hz = 1000.0
    min_log_mel = (min_log_hz - f_min) / f_sp
    logstep = math.log(6.4) / 27.0

    if freq >= min_log_hz:
        mels = min_log_mel + math.log(freq / min_log_hz) / logstep

    return mels



def _mel_to_hz(mels: Tensor, mel_scale: str = "htk") -> Tensor:
    """Convert mel bin numbers to frequencies.

    Args:
        mels (Tensor): Mel frequencies
        mel_scale (str, optional): Scale to use: ``htk`` or ``slaney``. (Default: ``htk``)

    Returns:
        freqs (Tensor): Mels converted in Hz
    """

    if mel_scale not in ["slaney", "htk"]:
        raise ValueError('mel_scale should be one of "htk" or "slaney".')

    if mel_scale == "htk":
        return 700.0 * (10.0 ** (mels / 2595.0) - 1.0)

    # Fill in the linear scale
    f_min = 0.0
    f_sp = 200.0 / 3
    freqs = f_min + f_sp * mels

    # And now the nonlinear scale
    min_log_hz = 1000.0
    min_log_mel = (min_log_hz - f_min) / f_sp
    logstep = math.log(6.4) / 27.0

    log_t = mels >= min_log_mel
    freqs[log_t] = min_log_hz * torch.exp(logstep * (mels[log_t] - min_log_mel))

    return freqs



def _create_triangular_filterbank(
    all_freqs: Tensor,
    f_pts: Tensor,
) -> Tensor:
    """Create a triangular filter bank.

    Args:
        all_freqs (Tensor): STFT freq points of size (`n_freqs`).
        f_pts (Tensor): Filter mid points of size (`n_filter`).

    Returns:
        fb (Tensor): The filter bank of size (`n_freqs`, `n_filter`).
    """
    # Adopted from Librosa
    # calculate the difference between each filter mid point and each stft freq point in hertz
    f_diff = f_pts[1:] - f_pts[:-1]  # (n_filter + 1)
    slopes = f_pts.unsqueeze(0) - all_freqs.unsqueeze(1)  # (n_freqs, n_filter + 2)
    # create overlapping triangles
    zero = torch.zeros(1)
    down_slopes = (-1.0 * slopes[:, :-2]) / f_diff[:-1]  # (n_freqs, n_filter)
    up_slopes = slopes[:, 2:] / f_diff[1:]  # (n_freqs, n_filter)
    fb = torch.max(zero, torch.min(down_slopes, up_slopes))

    return fb



def melscale_fbanks(
    n_freqs: int,
    f_min: float,
    f_max: float,
    n_mels: int,
    sample_rate: int,
    norm: Optional[str] = None,
    mel_scale: str = "htk",
) -> Tensor:
    r"""Create a frequency bin conversion matrix.

    .. devices:: CPU

    .. properties:: TorchScript

    Note:
        For the sake of the numerical compatibility with librosa, not all the coefficients
        in the resulting filter bank has magnitude of 1.

        .. image:: https://download.pytorch.org/torchaudio/doc-assets/mel_fbanks.png
           :alt: Visualization of generated filter bank

    Args:
        n_freqs (int): Number of frequencies to highlight/apply
        f_min (float): Minimum frequency (Hz)
        f_max (float): Maximum frequency (Hz)
        n_mels (int): Number of mel filterbanks
        sample_rate (int): Sample rate of the audio waveform
        norm (str or None, optional): If "slaney", divide the triangular mel weights by the width of the mel band
            (area normalization). (Default: ``None``)
        mel_scale (str, optional): Scale to use: ``htk`` or ``slaney``. (Default: ``htk``)

    Returns:
        Tensor: Triangular filter banks (fb matrix) of size (``n_freqs``, ``n_mels``)
        meaning number of frequencies to highlight/apply to x the number of filterbanks.
        Each column is a filterbank so that assuming there is a matrix A of
        size (..., ``n_freqs``), the applied result would be
        ``A @ melscale_fbanks(A.size(-1), ...)``.

    """

    if norm is not None and norm != "slaney":
        raise ValueError('norm must be one of None or "slaney"')

    # freq bins
    all_freqs = torch.linspace(0, sample_rate // 2, n_freqs)

    # calculate mel freq bins
    m_min = _hz_to_mel(f_min, mel_scale=mel_scale)
    m_max = _hz_to_mel(f_max, mel_scale=mel_scale)

    m_pts = torch.linspace(m_min, m_max, n_mels + 2)
    f_pts = _mel_to_hz(m_pts, mel_scale=mel_scale)

    # create filterbank
    fb = _create_triangular_filterbank(all_freqs, f_pts)

    if norm is not None and norm == "slaney":
        # Slaney-style mel is scaled to be approx constant energy per channel
        enorm = 2.0 / (f_pts[2 : n_mels + 2] - f_pts[:n_mels])
        fb *= enorm.unsqueeze(0)

    if (fb.max(dim=0).values == 0.0).any():
        warnings.warn(
            "At least one mel filterbank has all zero values. "
            f"The value for `n_mels` ({n_mels}) may be set too high. "
            f"Or, the value for `n_freqs` ({n_freqs}) may be set too low."
        )

    return fb
