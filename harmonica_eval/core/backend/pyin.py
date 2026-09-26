'''
COMPONENT:    COMP-C2 Audio Core · backend

ROLE:
    `pyin` 的 numpy/scipy 自写实现，与 librosa 0.11.0 同算法路径。

算法路径（pYIN，Mauch & Dixon 2014，与 librosa.core.pitch.py 一一对应）:
    1. 差分函数 d(τ) = 2(ACF(0) - ACF(τ)) - Σ_{m<τ} y(m)²
    2. 累积均值归一化 CMND
    3. 抛物线插值给出亚采样点的抛物线偏移
    4. 帧级候选 + 概率:
       - 100 个阈值的 beta(2,18) 先验 → 每个阈值取首个低于它的谷
       - Boltzmann 先验偏向短周期
       - 候选量化到 n_bins_per_semitone 音分网格
    5. 2*n_pitch_bins 状态的 HMM，Viterbi 解码 → voiced_flag + f0

★ 复刻要点（★ 决定能否与 librosa 对上）:
    - 帧中心化: center=True 时前后各补 frame_length//2 个零
    - min_period = floor(sr/fmax)，max_period = min(ceil(sr/fmin), frame_length-1)
    - resolution=0.1 音分 ⇒ n_bins_per_semitone = ceil(1/0.1) = 10
    - bin_index 的 clip 上界是 n_pitch_bins（★ 不是 n_pitch_bins-1，
      ★ librosa 就是这么写的，属 off-by-one 但必须复刻）
    - transition 矩阵是 kronecker(voiced_switch, 局部三角)，p_init 均匀
    - fill_na=np.NaN → 未发声帧的 f0 是 NaN（features.py 随即 nan_to_num 成 0）

MUST NOT:
    - 依赖 numba / librosa（本后端存在的全部理由就是它们装不上）
'''

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy.fft import next_fast_len, rfft, irfft
from scipy.signal import get_window
from scipy.special import betainc

from ._stft import autocorrelate, frame, tiny

__all__ = ["pyin"]


def _cumulative_mean_normalized_difference(
    y_frames: npt.NDArray, min_period: int, max_period: int,
) -> npt.NDArray:
    """YIN 差分函数 + 累积均值归一化（复刻 librosa._cumulative_mean_...）。

    输入 (frame_length, n_frames)，输出 (max_period-min_period+1, n_frames)。
    """
    acf_frames = autocorrelate(y_frames, max_size=max_period + 1, axis=0)

    # Energy terms: 累积的 y²
    yin_frames = np.square(y_frames)
    np.cumsum(yin_frames, out=yin_frames, axis=0)

    # d(k) = 2 * (ACF(0) - ACF(k)) - sum_{m=0}^{k-1} y(m)^2
    yin_frames[0] = 0
    k = slice(1, max_period + 1)
    yin_frames[k] = 2 * (acf_frames[0:1] - acf_frames[k]) - yin_frames[: max_period]

    # 累积均值归一化
    yin_numerator = yin_frames[min_period: max_period + 1]
    k_range = np.arange(1, max_period + 1)[:, None]
    cumulative_mean = np.cumsum(yin_frames[k], axis=0) / k_range
    yin_denominator = cumulative_mean[min_period - 1: max_period]
    tiny_val = tiny(yin_denominator)
    return yin_numerator / (yin_denominator + tiny_val)


def _parabolic_interpolation(x: npt.NDArray) -> npt.NDArray:
    """逐帧抛物线插值偏移（复刻 librosa._parabolic_interpolation）。

    对 τ 轴上每一点 n 取邻域 (x[n-1], x[n], x[n+1])：
        a = x[n+1] + x[n-1] - 2 x[n]
        b = (x[n+1] - x[n-1]) / 2
        shift = -b / a，若 |b| >= |a| 则 0（最优点落在邻域之外）
    ★ 首末两个元素显式置 0（stencil 覆盖不到边界）。
    """
    a = x[2:, :] + x[:-2, :] - 2 * x[1:-1, :]
    b = (x[2:, :] - x[:-2, :]) / 2.0
    degenerate = np.abs(b) >= np.abs(a)
    denom = np.where(degenerate, 1.0, a)
    shifts = np.zeros_like(x)
    shifts[1:-1, :] = np.where(degenerate, 0.0, -b / denom)
    return shifts


def _localmin(x: npt.NDArray) -> npt.NDArray:
    """沿 axis=0 的局部极小（复刻 librosa.util.localmin）。

    判据: x[i] < x[i-1] 且 x[i] <= x[i+1]。
    ★ 首元素恒为 False（stencil 无左邻居）；
      末元素判据是 x[-1] < x[-2]（无右邻居，退化为严格小于）。
    """
    out = np.zeros(x.shape, dtype=bool)
    out[1:-1, :] = (x[1:-1, :] < x[:-2, :]) & (x[1:-1, :] <= x[2:, :])
    out[-1, :] = x[-1, :] < x[-2, :]
    return out


def _transition_local(n_states: int, width: int) -> npt.NDArray:
    """局部三角转移矩阵（复刻 librosa.sequence.transition_local）。

    transition[i, j] = 0 若 |i-j| > width；行归一。
    """
    transition = np.zeros((n_states, n_states), dtype=np.float64)
    for i in range(n_states):
        width_i = width
        trans_row = get_window("triangle", width_i, fftbins=False)
        # 居中补到 n_states 后 roll，使峰值落在对角线
        lpad = (n_states - width_i) // 2
        trans_row = np.pad(
            trans_row, [(lpad, n_states - width_i - lpad)], mode="constant"
        )
        trans_row = np.roll(trans_row, n_states // 2 + i + 1)
        # 敲掉对角带外的元素
        trans_row[min(n_states, i + width_i // 2 + 1):] = 0
        trans_row[: max(0, i - width_i // 2)] = 0
        transition[i] = trans_row
    transition /= transition.sum(axis=1, keepdims=True)
    return transition


def _transition_loop(n_states: int, prob: float) -> npt.NDArray:
    """自环转移矩阵（复刻 librosa.sequence.transition_loop）。"""
    transition = np.full((n_states, n_states), (1.0 - prob) / (n_states - 1))
    np.fill_diagonal(transition, prob)
    return transition


def _viterbi(log_prob: npt.NDArray, log_trans: npt.NDArray,
             log_p_init: npt.NDArray) -> npt.NDArray:
    """numpy 复刻 librosa.sequence._viterbi 的对数域 Viterbi。

    log_prob: (n_states, n_steps)，返回 (n_steps,) 的状态序列。
    """
    n_states, n_steps = log_prob.shape

    value = np.zeros((n_steps, n_states), dtype=np.float64)
    ptr = np.zeros((n_steps, n_states), dtype=np.int64)

    value[0] = log_prob[:, 0] + log_p_init

    for t in range(1, n_steps):
        # trans_out[j, k] = V[t-1, k] + log A[k, j]，对 k 取 argmax
        trans_out = value[t - 1][None, :] + log_trans.T   # (n_states, n_states)
        best = np.argmax(trans_out, axis=1)              # (n_states,)
        ptr[t] = best
        value[t] = log_prob[:, t] + trans_out[np.arange(n_states), best]

    states = np.zeros(n_steps, dtype=np.int64)
    states[-1] = int(np.argmax(value[-1]))
    for t in range(n_steps - 2, -1, -1):
        states[t] = ptr[t + 1, states[t + 1]]
    return states


def _observation_probabilities(
    *,
    yin_frames: npt.NDArray,
    parabolic_shifts: npt.NDArray,
    thresholds: npt.NDArray,
    beta_probs: npt.NDArray,
    boltzmann_parameter: float,
    no_trough_prob: float,
) -> npt.NDArray:
    """逐帧的 YIN 谷 → 周期候选概率（复刻 librosa.__pyin_helper 的前半段）。

    返回 (n_tau, n_frames)：行是候选周期（tau 偏移量），非零处为该候选的概率。
    ★ 拆成独立函数是为了能对着 librosa 的同名 helper 做逐帧数值对拍。
    """
    n_tau, n_frames = yin_frames.shape
    yin_probs = np.zeros_like(yin_frames)

    for i in range(n_frames):
        yin_frame = yin_frames[:, i]

        # 1) 该帧的局部极小（谷）
        is_trough = _localmin(yin_frame[:, None])[:, 0]
        is_trough[0] = yin_frame[0] < yin_frame[1]
        trough_index = np.nonzero(is_trough)[0]
        if len(trough_index) == 0:
            continue

        # 2) 每个谷在哪些阈值之下
        trough_heights = yin_frame[trough_index]
        trough_thresholds = np.less.outer(trough_heights, thresholds[1:])

        # 3) Boltzmann 先验：短周期权重更大。
        # ★ n_troughs 按 axis=0 数 —— 它是「该阈值下有几个谷在其之下」，
        #   逐**阈值**的量，不是逐谷的量。
        trough_positions = np.cumsum(trough_thresholds, axis=0) - 1
        n_troughs = np.count_nonzero(trough_thresholds, axis=0)

        trough_prior = _boltzmann_pmf(
            trough_positions, boltzmann_parameter, n_troughs
        )
        # ★ 未落到该阈值之下的谷，先验置 0（librosa 的同名一行，不可省：
        #   它同时抹掉 N=0 造成的 nan/inf）。
        trough_prior = np.where(trough_thresholds, trough_prior, 0.0)

        probs = trough_prior @ beta_probs

        # 4) 若某阈值下没有谷，把概率补到全局最小谷上
        global_min = int(np.argmin(trough_heights))
        n_thresholds_below_min = int(
            np.count_nonzero(~trough_thresholds[global_min, :])
        )
        probs[global_min] += no_trough_prob * np.sum(beta_probs[:n_thresholds_below_min])

        yin_probs[trough_index, i] = probs

    return yin_probs


def pyin(
    y: npt.NDArray,
    *,
    sr: float,
    fmin: float,
    fmax: float,
    frame_length: int = 2048,
    hop_length: int | None = None,
    n_thresholds: int = 100,
    beta_parameters: tuple[float, float] = (2, 18),
    boltzmann_parameter: float = 2,
    resolution: float = 0.1,
    max_transition_rate: float = 35.92,
    switch_prob: float = 0.01,
    no_trough_prob: float = 0.01,
    fill_na: float | None = np.nan,
    center: bool = True,
    **_ignored,
) -> tuple[npt.NDArray, npt.NDArray, npt.NDArray]:
    """自写 pyin —— 签名与 librosa.pyin 对齐。

    返回 (f0, voiced_flag, voiced_prob)，三者都是 1-D、每帧一个值
    （shape == (n_frames,)），与 librosa 完全一致。

    ★ 冻结口径（★ 与调用点一致）: center=True、fill_na=NaN（features.py
      随即 nan_to_num 成 0），其余参数取 librosa 默认。
    """
    y = np.asarray(y, dtype=np.float32)
    if y.ndim != 1:
        raise ValueError(f"pyin: y 必须是 1-D，得到 {y.ndim}-D")
    if hop_length is None:
        hop_length = frame_length // 4

    # 参数可行性检查（复刻 librosa.__check_yin_params 的硬失败项）
    if fmax > sr / 2:
        raise ValueError(f"fmax={fmax} 超过 Nyquist {sr / 2}")
    if fmin >= fmax:
        raise ValueError(f"fmin={fmin} 必须小于 fmax={fmax}")
    if fmin <= 0:
        raise ValueError(f"fmin={fmin} 必须为正")
    if sr / fmin >= frame_length - 1:
        raise ValueError(
            f"fmin={fmin} 对 frame_length={frame_length} @ sr={sr} 过小"
        )

    if center:
        y = np.pad(y, (frame_length // 2, frame_length // 2), mode="constant")

    y_frames = frame(y, frame_length=frame_length, hop_length=hop_length)
    n_frames = y_frames.shape[1]

    min_period = int(np.floor(sr / fmax))
    max_period = min(int(np.ceil(sr / fmin)), frame_length - 1)

    yin_frames = _cumulative_mean_normalized_difference(
        y_frames, min_period, max_period
    )
    parabolic_shifts = _parabolic_interpolation(yin_frames)

    # ── 阈值先验（beta 分布 CDF 的相邻差）──────────────────────────
    thresholds = np.linspace(0, 1, n_thresholds + 1)
    beta_probs = np.diff(betainc(beta_parameters[0], beta_parameters[1], thresholds))

    n_bins_per_semitone = int(np.ceil(1.0 / resolution))
    n_pitch_bins = int(np.floor(12 * n_bins_per_semitone * np.log2(fmax / fmin))) + 1

    # ── 逐帧候选与概率（复刻 librosa.__pyin_helper）───────────────
    observation_probs = _observation_probabilities(
        yin_frames=yin_frames,
        parabolic_shifts=parabolic_shifts,
        thresholds=thresholds,
        beta_probs=beta_probs,
        boltzmann_parameter=boltzmann_parameter,
        no_trough_prob=no_trough_prob,
    )

    # ── 候选频率 → 音分 bin ───────────────────────────────────────
    # ★ yin_period 现在是 τ 偏移量（行号），不是已映射的 bin；
    #   故必须**新建** (2*n_pitch_bins, n_frames) 的数组来装 bin 域的概率，
    #   不能就地改写 tau 域的数组（那会把行数从 n_tau 写坏成 n_pitch_bins）。
    yin_period, frame_index = np.nonzero(observation_probs)
    period_candidates = min_period + yin_period
    period_candidates = period_candidates + parabolic_shifts[yin_period, frame_index]
    f0_candidates = sr / period_candidates

    bin_index = 12 * n_bins_per_semitone * np.log2(f0_candidates / fmin)
    # ★ 上界 n_pitch_bins（而非 -1）是 librosa 的原样实现，刻意复刻。
    bin_index = np.clip(np.round(bin_index), 0, n_pitch_bins).astype(int)

    binned_probs = np.zeros((2 * n_pitch_bins, n_frames), dtype=np.float64)
    binned_probs[bin_index, frame_index] = observation_probs[
        yin_period, frame_index
    ]
    observation_probs = binned_probs

    voiced_prob = np.clip(
        np.sum(observation_probs[:n_pitch_bins, :], axis=0, keepdims=True), 0, 1
    )[0]
    observation_probs[n_pitch_bins:, :] = (1 - voiced_prob) / n_pitch_bins

    # ── Viterbi ───────────────────────────────────────────────────
    max_semitones_per_frame = round(max_transition_rate * 12 * hop_length / sr)
    transition_width = max_semitones_per_frame * n_bins_per_semitone + 1
    transition = _transition_local(n_pitch_bins, transition_width)
    t_switch = _transition_loop(2, 1 - switch_prob)
    transition = np.kron(t_switch, transition)

    p_init = np.ones(2 * n_pitch_bins) / (2 * n_pitch_bins)

    epsilon = tiny(observation_probs)
    log_trans = np.log(transition + epsilon)
    log_prob = np.log(observation_probs + epsilon)
    log_p_init = np.log(p_init + epsilon)

    states = _viterbi(log_prob, log_trans, log_p_init)

    freqs = fmin * 2 ** (np.arange(n_pitch_bins) / (12 * n_bins_per_semitone))
    f0 = freqs[states % n_pitch_bins]
    voiced_flag = states < n_pitch_bins

    if fill_na is not None:
        f0[~voiced_flag] = fill_na

    return f0, voiced_flag, voiced_prob


def _boltzmann_pmf(k: npt.NDArray, lambda_: float,
                   N: npt.NDArray) -> npt.NDArray:
    """Boltzmann pmf（复刻 scipy.stats.boltzmann.pmf 的闭式，避免 scipy.stats）。

    P(k) = (1 - e^{-λ}) / (1 - e^{-λN}) · e^{-λk}
    ★ 高温退化下用 expm1 保持精度。
    """
    k = np.asarray(k, dtype=np.float64)
    N = np.asarray(N, dtype=np.float64)
    # ★ N=0（某阈值下无谷）时 den=0 会 nan —— 不靠 errstate 压警告，
    #   而是先把 N<=0 的因子置 0，与下面 ``bad`` 的判定保持一致。
    degenerate = N <= 0
    safe_N = np.where(degenerate, 1.0, N)
    with np.errstate(over="ignore", invalid="ignore"):
        num = -np.expm1(-lambda_)
        den = -np.expm1(-lambda_ * safe_N)
        factor = num / den
        out = factor * np.exp(-lambda_ * k)
    # k 越界或 N 非法时置 0（对齐 scipy 的行为）
    bad = (k < 0) | (k > N) | degenerate | ~np.isfinite(out)
    out = np.where(bad, 0.0, out)
    return out
