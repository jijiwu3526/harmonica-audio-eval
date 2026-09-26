'''
COMPONENT:    COMP-C2 Audio Core · backend

ROLE:
    自写后端的**共享低层原语**：分帧 / 窗函数 / 有界自相关。
    chroma.py 与 pyin.py 都从这里取，避免两处各写一份帧数公式
    （★ 两处各写一份是 surface 帧数错位事故的温床）。

★ 帧数口径（★ 全项目唯一的帧数来源，★ surface 的对齐依赖它）:
    center=True、pad_mode='constant' 时：
        n_frames = 1 + (n_padded - n_fft) // hop_length
    其中 n_padded = n + n_fft // 2（前后各补 n_fft//2 零）。
    ★ 这正是 librosa `util.frame(np.pad(y, (n_fft//2, n_fft//2)))` 的结果，
      也是 surface.py:158 注释里「boundary='zeros' + padded=True 补出来的
      多出帧」的同一套 —— 复现它，帧数才可能相等。
'''

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy.fft import irfft, next_fast_len, rfft
from scipy.signal import get_window


def frame_count(n_samples: int, n_fft: int, hop_length: int,
                center: bool) -> int:
    """给定长度与参数，返回**与 librosa 逐帧一致**的帧数。

    center=True 时 librosa 先把 y 两端各补 n_fft//2 个零再分帧，
    帧数 = 1 + (len(y) - n_fft) // hop（不足一帧时 librosa 抛错，
    但 features.py 的调用点在更外层已保证不会进这里）。
    """
    if center:
        padded = n_samples + 2 * (n_fft // 2)
    else:
        padded = n_samples
    if padded < n_fft:
        raise ValueError(
            f"输入太短：center={center} 下需 >= {n_fft} 个样本（补零后），"
            f"得到 {padded}"
        )
    return 1 + (padded - n_fft) // hop_length


def frame(x: npt.NDArray, frame_length: int, hop_length: int) -> npt.NDArray:
    """按 librosa.util.frame 的语义切帧：返回 (frame_length, n_frames)。

    librosa 用 stride 视图（零拷贝）。这里用索引矩阵（会复制），
    ★ 数值完全相同，但更直白、对老 numpy 也稳。
    """
    n = x.shape[-1]
    if n < frame_length:
        raise ValueError(f"frame: 输入 {n} < frame_length {frame_length}")
    n_frames = 1 + (n - frame_length) // hop_length
    idx = np.arange(frame_length)[None, :] + hop_length * np.arange(n_frames)[:, None]
    return x[idx].T  # (frame_length, n_frames)


def pad_center(x: npt.NDArray, size: int) -> npt.NDArray:
    """居中补零到 size（复刻 librosa.util.pad_center 的 constant 模式）。"""
    n = x.shape[-1]
    lpad = (size - n) // 2
    return np.pad(x, [(0, 0)] * (x.ndim - 1) + [(lpad, size - n - lpad)])


def autocorrelate(y: npt.NDArray, max_size: int, axis: int = -1) -> npt.NDArray:
    """有界滞后自相关（复刻 librosa.core.autocorrelate，real 分支）。

    对 `axis` 做 power-spectrum → irfft，再把该轴切到 max_size。
    与 librosa 用同一个 next_fast_len、同一条 irfft，故结果逐位一致。

    ★ pyin 必须传 axis=-2（滞后期在帧轴上）：librosa 的 pyin 也是这么调的，
      默认的 axis=-1 会把「帧」当成滞后期，形状直接错。
    """
    n = y.shape[axis]
    max_size = int(min(max_size, n))
    n_pad = next_fast_len(2 * n - 1, real=True)
    powspec = np.abs(rfft(y, n=n_pad, axis=axis)) ** 2
    autocorr = irfft(powspec, n=n_pad, axis=axis)
    subslice = [slice(None)] * autocorr.ndim
    subslice[axis] = slice(max_size)
    return autocorr[tuple(subslice)]


def tiny(x: npt.NDArray | float) -> np.floating:
    """对应 dtype 的最小正可用数（复刻 librosa.util.tiny）。

    ★ 必须返回 **numpy 标量**而非 Python float：
      librosa 返回 np.finfo(...).tiny（np.float64 标量），在 NEP 50 下
      与 float32 数组相加会提升为 float64；返回 Python float 则是弱标量，
      运算留在 float32。两者结果相差 ~1e-7，并会经抛物线插值放大。
    """
    arr = np.asarray(x)
    if np.issubdtype(arr.dtype, np.floating) or np.issubdtype(
        arr.dtype, np.complexfloating
    ):
        dtype = arr.dtype
    else:
        dtype = np.dtype(np.float32)
    return np.finfo(dtype).tiny


def hann_window(n: int) -> npt.NDArray:
    """周期 hann 窗（librosa stft 的默认窗，fftbins=True）。

    librosa 走 scipy.signal.get_window('hann', Nx, fftbins=True)；
    直接调同一个 scipy 函数即可保证逐位一致。
    """
    return get_window("hann", n, fftbins=True)


__all__ = [
    "frame_count", "frame", "pad_center", "autocorrelate", "tiny",
    "hann_window",
]
