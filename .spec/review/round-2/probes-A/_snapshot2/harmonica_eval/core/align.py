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

MUST NOT:
    - 静默退化为「逐点硬比」（宪章 §5.6 No Silent Degradation）
      —— 宁可直接失败，也不要给出一个看起来正常但毫无对齐的结果
    - 返回代价矩阵（调用方不需要，且它是内存炸弹）
    - 用 chroma 之外的高分辨率特征"顺便提高精度"
    - 假定 hop_length 可以下调（见下）

INPUT:
    reference: float32 mono PCM
    practice:  float32 mono PCM

OUTPUT:
    warp_path —— int32[N, 2]，字段顺序见 contract.FIELD_LAYOUTS

BUILD-INSTRUCTION:
    .spec/build/FILE-102-v1.md
'''

from __future__ import annotations

import numpy.typing as npt

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


def compute_alignment_features(samples: npt.NDArray) -> npt.NDArray:
    """计算用于对齐的低分辨率 chroma。

    hop 取 profile.ALIGN.hop_length（2048）。**不要在这里图精度** ——
    见模块 docstring 的实测数字：分辨率加倍，代价矩阵涨 4 倍。

    注意 chroma 是**八度不变**的，正因如此它适合做对齐（音区差异不该
    影响"这两个音是不是同一个音"的判断），但**绝不适合做评分**。
    评分用的绝对音高在 features.py。

    返回形状 (n_chroma, n_frames)，取自 profile.ALIGN.n_chroma。
    """
    raise NotImplementedError("SHELL: FILE-102 待注入实现")


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
    raise NotImplementedError("SHELL: FILE-102 待注入实现")


def assert_monotonic(warp_path: npt.NDArray) -> None:
    """校验路径的参考索引单调不回退。

    失败：抛 ContractViolation —— 非单调路径意味着上游 DTW 实现有缺陷，
    不是输入数据的问题，故不归为 ALIGNMENT_UNRECOVERABLE。
    """
    raise NotImplementedError("SHELL: FILE-102 待注入实现")


def measure_coverage(warp_path: npt.NDArray, n_ref_frames: int) -> float:
    """测算对齐覆盖了参考时长的比例。

    返回 0.0–1.0。低于 WARP_PATH_MIN_COVERAGE 时应由 align() 抛
    ALIGNMENT_UNRECOVERABLE —— 局部对齐冒充整体对齐是误导。
    """
    raise NotImplementedError("SHELL: FILE-102 待注入实现")


def align(
    reference: npt.NDArray,
    practice: npt.NDArray,
) -> npt.NDArray:
    """完整对齐流程：算特征 → DTW → 校验单调 → 校验覆盖 → 返回路径。

    失败：
        无法建立有效映射 → CoreBuildError(ALIGNMENT_UNRECOVERABLE)
        **严禁**在此处退化为逐点硬比（宪章 §5.6）。
    """
    raise NotImplementedError("SHELL: FILE-102 待注入实现")
