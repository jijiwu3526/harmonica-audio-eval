'''
COMPONENT:    COMP-C2 Audio Core · backend

ROLE:
    `chroma_stft` 的 numpy/scipy 自写实现，与 librosa 0.11.0 同算法路径。

算法路径（与 librosa.feature.chroma_stft 逐项对应）:
    1. STFT: |rfft(hann(y)|)|²  → 功率谱 S，形状 (1+n_fft/2, n_frames)。
       ★ 帧数 = 1 + (len(y)+n_fft - n_fft) // hop（center=True 两端各补 n_fft//2）
         —— 与 librosa.stft(center=True) 逐帧一致，★ surface 的帧对齐依赖它。
    2. 滤波器组: filters.chroma(sr, n_fft, tuning, n_chroma) 的 numpy 复刻
       —— 高斯 bump 投到 12 个 pitch class，ctroct=5.0/octwidth=2 主导窗，
          base_c=True（bin 0 = C），每列按 norm=2（滤波器归一化，★ 注意
          这与输出归一化是两回事）归一。
    3. 投影: raw_chroma = chromafb @ S → (n_chroma, n_frames)。
    4. 归一化: norm=np.inf ⇒ 每帧按 L∞ 归一（沿 axis=-2 即每列/每帧）。

★ 复刻要点（★ 任何偏差都会让相关系数掉下来）:
    - 功率谱 power=2（不是幅度）
    - base_c=True ⇒ 结束时 np.roll(wts, -3*(n_chroma//12))
    - 0 Hz 的假 bin 取 frqbins[0] - 1.5*n_chroma
    - 滤波器列归一用 norm=2（librosa.chroma 默认），输出归一用 norm=inf
'''

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy.fft import rfft

from ._stft import frame, hann_window

__all__ = ["chroma_stft", "chroma_filterbank"]


def _hz_to_chroma_bins(frequencies: npt.NDArray, tuning: float,
                       n_chroma: int) -> npt.NDArray:
    """复刻 librosa.filters.chroma 内部的频率→色度 bin 映射。

    librosa: frqbins = n_chroma * hz_to_octs(f, tuning, bins_per_octave=n_chroma)
    hz_to_octs 用 A440 = 440*2**(tuning/n_chroma)，octs = log2(f/(A440/16))。
    """
    a440 = 440.0 * 2.0 ** (tuning / n_chroma)
    return n_chroma * np.log2(frequencies / (a440 / 16.0))


def chroma_filterbank(sr: float, n_fft: int, n_chroma: int = 12,
                      tuning: float = 0.0, ctroct: float = 5.0,
                      octwidth: float | None = 2,
                      norm: float | None = 2,
                      base_c: bool = True) -> npt.NDArray:
    """numpy 复刻 librosa.filters.chroma（n_chroma=12、tuning、ctroct、octwidth）。

    返回 (n_chroma, 1 + n_fft//2)。逐行与 librosa 一致（见文件 docstring）。
    """
    # Get the FFT bins, not counting the DC component.
    frequencies = np.linspace(0, sr, n_fft, endpoint=False)[1:]
    frqbins = _hz_to_chroma_bins(frequencies, tuning, n_chroma)

    # Make up a value for the 0 Hz bin = 1.5 octaves below bin 1
    # (so chroma is 50% rotated from bin 1, and bin width is broad).
    frqbins = np.concatenate(([frqbins[0] - 1.5 * n_chroma], frqbins))

    binwidthbins = np.concatenate(
        (np.maximum(frqbins[1:] - frqbins[:-1], 1.0), [1])
    )

    D = np.subtract.outer(frqbins, np.arange(0, n_chroma, dtype="d")).T

    n_chroma2 = np.round(float(n_chroma) / 2)

    # Project into range -n_chroma/2 .. n_chroma/2, offset to keep positive for rem.
    D = np.remainder(D + n_chroma2 + 10 * n_chroma, n_chroma) - n_chroma2

    # Gaussian bumps - 2*D to make them narrower.
    wts = np.exp(-0.5 * (2 * D / np.tile(binwidthbins, (n_chroma, 1))) ** 2)

    # Normalize each column (the *filter* normalization, norm=2 by default).
    if norm == np.inf:
        length = np.max(np.abs(wts), axis=0, keepdims=True)
    else:
        length = np.sum(np.abs(wts) ** norm, axis=0, keepdims=True) ** (1.0 / norm)
    length = np.where(length < np.finfo(np.float64).tiny, 1.0, length)
    wts = wts / length

    # Scaling for fft bins (dominance window).
    if octwidth is not None:
        wts *= np.tile(
            np.exp(-0.5 * (((frqbins / n_chroma - ctroct) / octwidth) ** 2)),
            (n_chroma, 1),
        )

    if base_c:
        wts = np.roll(wts, -3 * (n_chroma // 12), axis=0)

    # Remove aliasing columns; keep rows contiguous. librosa returns float32 here.
    return np.ascontiguousarray(wts[:, : 1 + n_fft // 2], dtype=np.float32)


def _stft_power(y: npt.NDArray, n_fft: int, hop_length: int,
               center: bool) -> npt.NDArray:
    """功率谱 |rfft(hann(y))|²，返回 (1 + n_fft//2, n_frames)。

    帧数与 librosa.stft(center=True) 逐帧一致（两端各补 n_fft//2 零）。
    """
    if center:
        y = np.pad(y, (n_fft // 2, n_fft // 2), mode="constant")

    win = hann_window(n_fft)
    y_frames = frame(y, n_fft, hop_length)          # (n_fft, n_frames)
    spectrum = rfft(y_frames * win[:, None], axis=0, n=n_fft)
    return (np.abs(spectrum) ** 2).astype(np.float32)


def chroma_stft(
    *,
    y: npt.NDArray,
    sr: float,
    n_fft: int = 2048,
    hop_length: int = 512,
    n_chroma: int = 12,
    tuning: float = 0.0,
    norm: float | None = np.inf,
    center: bool = True,
    window: str = "hann",
    **_ignored,
) -> npt.NDArray:
    """自写 chroma_stft —— 签名与 librosa.feature.chroma_stft 对齐。

    只实现 features.py 实际用到的参数语义；`window` 固定走 hann（librosa 默认），
    多余 kwargs 被吞掉以容忍调用方传 librosa 专有参数。

    ★ 冻结口径（★ 与两个调用点一致）:
        tuning=0.0, norm=np.inf, center=True, n_chroma 可变。
        返回 (n_chroma, n_frames) float32，bin 0 = C（base_c=True）。
    """
    y = np.asarray(y, dtype=np.float32)
    if y.ndim != 1:
        raise ValueError(f"chroma_stft: y 必须是 1-D，得到 {y.ndim}-D")
    if window != "hann":
        raise NotImplementedError(
            f"自写 chroma_stft 只实现 hann 窗（librosa 默认），得到 {window!r}"
        )

    S = _stft_power(y, n_fft=n_fft, hop_length=hop_length, center=center)

    chromafb = chroma_filterbank(
        sr=sr, n_fft=n_fft, n_chroma=n_chroma, tuning=tuning
    )

    # Project FFT bins onto chroma bins.
    raw_chroma = chromafb.astype(np.float64) @ S.astype(np.float64)

    # Column-wise (per-frame) normalization along axis=-2.
    if norm is not None:
        mag = np.abs(raw_chroma)
        if norm == np.inf:
            length = np.max(mag, axis=0, keepdims=True)
        elif norm == -np.inf:
            length = np.min(mag, axis=0, keepdims=True)
        elif norm == 0:
            length = np.sum(mag > 0, axis=0, keepdims=True, dtype=mag.dtype)
        else:
            length = np.sum(mag ** norm, axis=0, keepdims=True) ** (1.0 / norm)
        threshold = np.finfo(np.float64).tiny
        small = length < threshold
        # Leave small-norm columns un-normalized (librosa fill=None behavior).
        length = np.where(small, 1.0, length)
        raw_chroma = raw_chroma / length

    return raw_chroma.astype(np.float32)
