'''
FILE-ID:      FILE-102
COMPONENT:    COMP-C2 Audio Core
SPEC:         profile.ALIGN · COMPONENTS.md@v2 §3 · SPEC.md@v2.1 §5.5

ROLE:
    建立两段演奏之间的时间映射（warp path）—— 全系统唯一的时间对齐发生地。

INTENT:
    把「对齐」这件事收敛到一处，并让它的**分辨率**成为一个显式、可审、
    有实测依据的参数。理由：对齐是内存的主要消耗者，而这一点极易被误判。

    ★ 实测（harmonica_mvp_dataset/spike_dtw_memory.py，120 s 音频，真实 DTW）：

        hop=512  → 代价矩阵 855 MB   （float64，N²×8B）
        hop=2048 → 代价矩阵  53 MB   （降 16.0×，平方反比）

    与之对比，我一直以为的"内存大户"一档 STFT 只有 85 MB。
    **调对齐分辨率是 855→53 MB 的杠杆；削减频谱档数是 85 MB 级的无效努力。**

MUST:
    - 用低分辨率特征做对齐（profile.ALIGN.hop_length，已固定 2048，不得下调）
    - 得到路径后**立即释放**代价矩阵（它比结果大 5000 倍）
    - 校验路径单调性（参考索引不得回退）
    - 无法建立有效映射 → 抛 ALIGNMENT_UNRECOVERABLE
    - 依赖只用 numpy + scipy（★ 见下方「依赖边界（与 FILE-102 §3 原文对齐）」）
    - compute_alignment_features 用 scipy.signal.stft：nperseg=4096、noverlap=2048、
      window='hann'；★ fs 必须传 profile.AUDIO.sample_rate（44100），**不得**传 hop_length
    - ★ 不显式传 boundary（用库默认 'zeros'）—— 帧数由实际矩阵决定，不假设任何公式
    - 中间结果 dtype 恒 float32，不得临时提升到 float64 再回转

★ 依赖边界（逐字对照 FILE-102-v1.md §3，★ 本节取代任何与之冲突的旧措辞）：
    - §3（:54）**允许**：`numpy`、`scipy.spatial.distance.cdist`、
      `scipy.signal.stft`、`librosa`（仅限本文件已列出的调用）
    - §3（:56）**禁止**：`fastdtw`、任何联网调用、任何文件 I/O
    - ★ 本文件【实际只 import numpy + scipy】（见下方 import 段），未 import librosa
    - ★ ★ 「真正的禁令只有 fastdtw」—— 旧注释曾写「§3 禁止 librosa /
      dtw-python / tslearn / fastdtw」，★ 那与 §3 原文矛盾，且
      dtw-python / tslearn 在 §3 中【从未被提及】；★ 本行据 §3 更正。
    - ★ 对照：`features.py` import librosa 合法（FILE-103 §3 明列 librosa 0.11.0）；
      `ingest.py` import soundfile 合法（FILE-101 定其为独有职责）。
      ★ core 各文件依赖面不同，★ 不可把某一文件的禁令推广到全层。
    - compute_warp_path 的距离矩阵 D 固定 float64，C 复用 D 的内存（写回）
    - assert_monotonic 失败抛 ContractViolation(ErrorCode.INTERNAL_ERROR, detail=...)
    - align 内部**不得** try/except 吸收 ContractViolation

MUST NOT:
    - 静默退化为「逐点硬比」（宪章 §5.6 No Silent Degradation）
      —— 宁可直接失败，也不要给出一个看起来正常但毫无对齐的结果
    - 返回代价矩阵（调用方不需要，且它是内存炸弹）
    - 用 chroma 之外的高分辨率特征"顺便提高精度"
    - 假定 hop_length 可以下调（见上）
    - 不得夹紧 coverage（不加 min(1.0, ...)）—— 见 measure_coverage docstring

INPUT:
    reference: float32 mono PCM
    practice:  float32 mono PCM

OUTPUT:
    warp_path —— int32[N, 2]，字段顺序见 contract.FIELD_LAYOUTS

BUILD-INSTRUCTION:
    .spec/build/FILE-102-v1.md
'''

from __future__ import annotations

import gc

import numpy as np
import numpy.typing as npt
from scipy.signal import stft
from scipy.spatial.distance import cdist

from .. import profile
from ..contract import ContractViolation, CoreBuildError, ErrorCode

WARP_PATH_MIN_COVERAGE: float = 0.90
"""路径必须覆盖的参考时长比例。

低于此值说明对齐只覆盖了局部（例如练习只吹了一半），
此时报"整体对齐成功"是误导。
"""

MONOTONICITY_TOLERANCE: int = 0
"""参考帧索引允许的回退帧数。0 = 严格单调不回退。

DTW 的路径在数学上保证单调，但回溯实现或后处理可能引入回退。
留这个常量是为了让"我们检查过单调性"成为一个显式事实，
而不是一句口头保证。
"""

_NPERSEG = 4096
"""STFT 窗长，§4 冻结值。"""

_NOVERLAP = 2048
"""STFT 重叠，§4 冻结值。恰为窗长一半 → hop=2048。"""

_WINDOW = "hann"
"""STFT 窗函数，§4 冻结值。"""

_N_BINS = 12
"""一个八度内的 pitch-class 分箱数。"""


def _unrecoverable(detail: str) -> CoreBuildError:
    """构造 ALIGNMENT_UNRECOVERABLE，统一失败出口。"""
    return CoreBuildError(ErrorCode.ALIGNMENT_UNRECOVERABLE, detail=detail)


def _pitch_bins(freqs: np.ndarray) -> np.ndarray:
    """把频率映射到 12 个 pitch-class 分箱（chroma-sensitive）。

    以 A0=27.5Hz 为参考点，bin = round(12·log2(f/A0)) mod 12。
    对数等分使「同一个 pitch class 落在同一个 bin」与音区无关 ——
    这正是 chroma 适合做对齐、却不适合做评分的原因。
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = np.log2(freqs / 27.5)
    return np.mod(np.round(_N_BINS * raw).astype(np.int64), _N_BINS)


def compute_alignment_features(samples: npt.NDArray) -> npt.NDArray:
    """计算用于对齐的低分辨率 chroma。

    hop 取 profile.ALIGN.hop_length（2048）。**不要在这里图精度** ——
    见模块 docstring 的实测数字：分辨率加倍，代价矩阵涨 4 倍。

    注意 chroma 是**八度不变**的，正因如此它适合做对齐（音区差异不该
    影响"这两个音是不是同一个音"的判断），但**绝不适合做评分**。
    评分用的绝对音高在 features.py。

    返回形状 (n_chroma, n_frames)，取自 profile.ALIGN.n_chroma。
    """
    samples = np.asarray(samples)
    if samples.ndim != 1:
        raise _unrecoverable(f"samples 维度应为 1，实得 {samples.ndim}")
    if samples.shape[0] == 0:
        raise _unrecoverable("samples 为空")

    # ★ fs 必须传真实采样率。若传 hop_length，频率轴被整体压错，
    #   440Hz 正弦会被标成 20.5Hz（−5309 音分）—— 形状不变、不抛异常，
    #   只是全部落进错误的 bin，DTW 于是在错误的特征上对齐。
    # ★ 不显式传 boundary：§4 冻结「用库默认 'zeros'」，
    #   帧数由实际矩阵决定，不依赖任何近似公式。
    # ★★ 但「由实际矩阵决定」不等于「全部帧都合法」（2026-09-24 实测）★★
    #   scipy.signal.stft 在默认 boundary='zeros' + padded=True 下会补出尾部零帧，
    #   其帧起点可能已越过真实音频末尾：
    #     n=3210572, hop=2048 → stft 实际 1569 帧（合法帧号 0..1568）。
    #   ★ 合法帧的判据是【帧起点严格小于信号长度】：frame*hop < n。
    #   ★★ 故合法帧数 = (n-1)//hop 【恰好】，不需要 +1 ★★
    #     (3210572-1)//2048 = 1567  → 合法帧号 0..1566
    #   ★ 原式多一个 +1（=1568），把末帧 1568 放了进来；
    #     而 1568*2048 = 3211264 ≥ 3210572 —— 那一帧起点已越过音频末尾，
    #     是【真越界】，不是口径差异。下游 SEALING 按采样点口径拒它是正确的。
    #   ★ 裁掉的是「起点已越界」的补零帧，合法帧一帧不动。
    n_legal_frames = (int(samples.shape[0]) - 1) // int(profile.ALIGN.hop_length)

    freqs, _times, spectrum = stft(
        samples,
        fs=profile.AUDIO.sample_rate,
        nperseg=_NPERSEG,
        noverlap=_NOVERLAP,
        window=_WINDOW,
    )

    magnitude = np.abs(spectrum).astype(np.float32, copy=False)
    if magnitude.shape[1] > n_legal_frames:
        # 只保留帧起点严格小于 samples 长度的帧。
        magnitude = magnitude[:, :n_legal_frames]

    # 只保留十二平均律相关频段，滤掉直流与超声噪声。
    lo = int(np.searchsorted(freqs, 27.5, side="left"))
    hi = int(np.searchsorted(freqs, 4200.0, side="right"))
    if hi <= lo:
        raise _unrecoverable("频段筛选后无可用频率")
    magnitude = magnitude[lo:hi]
    bins = _pitch_bins(freqs[lo:hi])

    n_chroma = int(profile.ALIGN.n_chroma)
    if n_chroma != _N_BINS:
        raise _unrecoverable(
            f"profile.ALIGN.n_chroma={n_chroma} 与实现的 {_N_BINS} 不一致"
        )

    chroma = np.zeros((n_chroma, magnitude.shape[1]), dtype=np.float32)
    # 多个频率可能落进同一 bin → 用 add.at 正确累加。
    for b in range(n_chroma):
        selected = magnitude[bins == b]
        if selected.size:
            chroma[b] = selected.sum(axis=0, dtype=np.float32)

    # L2 归一化：抵消整体响度，只留谱形。★ 全程保持 float32。
    norms = np.sqrt((chroma * chroma).sum(axis=0, dtype=np.float32))
    norms[norms == 0.0] = np.float32(1.0)
    chroma /= norms

    if chroma.shape[1] < 1:
        raise _unrecoverable("STFT 未产出任何帧")
    return np.ascontiguousarray(chroma, dtype=np.float32)


def compute_warp_path(
    ref_features: npt.NDArray,
    prac_features: npt.NDArray,
) -> npt.NDArray:
    """对两组对齐特征跑 DTW，返回 warp path。

    参数取自 profile.ALIGN：global_constraints=True、band_rad=0.25。

    ⚠ 两个实测得来的实现陷阱，必须写进实现：

    1. **代价矩阵是 float64**，所以占用是 N²×8B 而非 N²×4B。
       按 float32 估算会**低估一半**。
    2. **global_constraints=True 不减少矩阵分配**，只约束路径、降低耗时
       （实测 2.99 s → 2.15 s，但矩阵仍是 855 MB）。
       以为"加了带宽就省内存"是错的。

    因此：拿到路径后**立即**释放代价矩阵，不要让它在调用栈上继续存活。

    返回 int32[N, 2]，字段顺序 = contract.FIELD_LAYOUTS['warp_path']
    = (reference_frame, practice_frame)。
    """
    ref_features = np.asarray(ref_features)
    prac_features = np.asarray(prac_features)
    for name, arr in (("ref_features", ref_features), ("prac_features", prac_features)):
        if arr.ndim != 2:
            raise _unrecoverable(f"{name} 维度应为 2，实得 {arr.ndim}")
        if arr.size == 0 or arr.shape[1] == 0:
            raise _unrecoverable(f"{name} 为空")

    n_ref = int(ref_features.shape[1])
    n_prac = int(prac_features.shape[1])

    # ★ D 固定 float64（INV-102-6）。cdist 的 euclidean 默认即 float64。
    D = cdist(ref_features.T, prac_features.T, metric="euclidean")
    if D.dtype != np.float64:
        D = D.astype(np.float64)

    # 带宽约束 |i/n_ref − j/n_prac| <= band_rad。
    # global_constraints 只约束路径、**不减少矩阵分配**（§4 实测结论）。
    band = float(profile.ALIGN.band_rad)
    if bool(profile.ALIGN.global_constraints) and band > 0.0:
        i_ax = np.arange(n_ref, dtype=np.float64)[:, None]
        j_ax = np.arange(n_prac, dtype=np.float64)[None, :]
        outside = np.abs(i_ax / n_ref - j_ax / n_prac) > band
        if outside.any():
            D[outside] = np.inf

    # C 复用 D 的内存（写回），dtype 亦 float64。
    C = D
    for i in range(n_ref):
        for j in range(n_prac):
            if i == 0 and j == 0:
                continue
            best = np.inf
            if i > 0:
                best = min(best, C[i - 1, j])
            if j > 0:
                best = min(best, C[i, j - 1])
            if i > 0 and j > 0:
                best = min(best, C[i - 1, j - 1])
            C[i, j] = np.inf if not np.isfinite(best) else D[i, j] + best

    # 回溯：从 (n_ref−1, n_prac−1) 到 (0,0)，贪心选最小 predecessor。
    path: list[tuple[int, int]] = []
    i, j = n_ref - 1, n_prac - 1
    while True:
        path.append((i, j))
        if i == 0 and j == 0:
            break
        candidates: list[tuple[float, int, int]] = []
        if i > 0:
            candidates.append((float(C[i - 1, j]), i - 1, j))
        if j > 0:
            candidates.append((float(C[i, j - 1]), i, j - 1))
        if i > 0 and j > 0:
            candidates.append((float(C[i - 1, j - 1]), i - 1, j - 1))
        # 优先累计代价小者；同值时优先对角（标准 DTW 的 Saksamthon–Kern 偏好）
        candidates.sort(key=lambda item: (item[0], -(item[1] + item[2])))
        _, i, j = candidates[0]
    path.reverse()

    if not path:
        raise _unrecoverable("回溯得到空路径")

    # 列顺序 = (reference_frame, practice_frame)
    warp_path = np.ascontiguousarray(np.asarray(path, dtype=np.int32), dtype=np.int32)

    # ★ 立即释放代价矩阵（INV-102-7）：不留在调用栈上持续占用内存。
    del D, C
    gc.collect()

    if int(warp_path[:, 0].max()) > n_ref - 1:
        raise _unrecoverable("路径含越界的参考帧索引")
    return warp_path


def assert_monotonic(warp_path: npt.NDArray) -> None:
    """校验路径的参考索引单调不回退。

    失败：抛 ContractViolation —— 非单调路径意味着上游 DTW 实现有缺陷，
    不是输入数据的问题，故不归为 ALIGNMENT_UNRECOVERABLE。
    """
    warp_path = np.asarray(warp_path)
    if warp_path.ndim != 2:
        raise _unrecoverable(f"warp_path 维度应为 2，实得 {warp_path.ndim}")
    if warp_path.shape[0] < 2:
        return None  # 单点路径天然单调

    diffs = np.diff(warp_path[:, 0].astype(np.int64))
    if bool(np.any(diffs < -MONOTONICITY_TOLERANCE)):
        # ★ 第一参数是 code: ErrorCode，说明文字必须放 detail。
        #   若照字面写成 ContractViolation('warp_path not monotonic')，
        #   异常能抛出来、当场不报错，但 .code 是 str，
        #   故障会推迟到 C1 归一化时读 err.code.value 才爆 —— 又是静默潜伏。
        raise ContractViolation(
            ErrorCode.INTERNAL_ERROR, detail="warp_path not monotonic"
        )
    return None


def measure_coverage(warp_path: npt.NDArray, n_ref_frames: int) -> float:
    """测算对齐覆盖了参考时长的比例。

    返回 0.0–1.0。低于 WARP_PATH_MIN_COVERAGE 时应由 align() 抛
    ALIGNMENT_UNRECOVERABLE —— 局部对齐冒充整体对齐是误导。
    """
    warp_path = np.asarray(warp_path)
    if n_ref_frames <= 0:
        raise _unrecoverable(f"n_ref_frames 应 > 0，实得 {n_ref_frames}")
    if warp_path.ndim != 2:
        raise _unrecoverable(f"warp_path 维度应为 2，实得 {warp_path.ndim}")
    if warp_path.shape[0] == 0:
        return np.float32(0.0)

    covered = int(np.unique(warp_path[:, 0]).shape[0])
    # ★ 不夹紧（不加 min(1.0, ...)）：公式 covered/n_ref_frames 是唯一口径。
    #   当 covered=23、n_ref_frames=5 时返回 4.6 —— 它携带真实信息
    #   （"覆盖了 4.6 倍参考时长"），夹成 1.0 会把这个信息抹掉。
    #   n_ref_frames 传得比实际覆盖帧数还小属于调用方误用。
    return np.float32(covered / n_ref_frames)


def align(
    reference: npt.NDArray,
    practice: npt.NDArray,
) -> npt.NDArray:
    """完整对齐流程：算特征 → DTW → 校验单调 → 校验覆盖 → 返回路径。

    失败：
        无法建立有效映射 → CoreBuildError(ALIGNMENT_UNRECOVERABLE)
        **严禁**在此处退化为逐点硬比（宪章 §5.6）。
    """
    ref_feat = compute_alignment_features(reference)
    prac_feat = compute_alignment_features(practice)
    warp_path = compute_warp_path(ref_feat, prac_feat)

    # ★ 不得用 try/except 吸收 ContractViolation（INV-102-9）
    assert_monotonic(warp_path)

    coverage = measure_coverage(warp_path, ref_feat.shape[1])
    if coverage < WARP_PATH_MIN_COVERAGE:
        raise _unrecoverable(
            f"对齐覆盖率 {float(coverage):.4f} 低于阈值 {WARP_PATH_MIN_COVERAGE}"
        )
    return warp_path
