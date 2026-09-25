'''
FILE-ID:      FILE-103
COMPONENT:    COMP-C2 Audio Core
SPEC:         profile.MATERIALIZE · profile.PORTS · contract.FIELD_LAYOUTS

ROLE:
    预生成算法所需的全部逐帧/逐音特征：音高曲线、能量包络、低分辨率 chroma、
    逐音摘要。

INTENT:
    「Core 预生成」这一架构裁定的**落地处**。

    为什么不惰性现算（负责人裁定，不可推翻）：
        惰性计算要活下来必须定义一套协商协议
        （特征声明 → 解析 → 版本 → 缓存失效 → 算失败的语义）。
        一旦有了那套协议，**Core 的外部接口就成了插件需求的函数** ——
        正是「深组件」要消灭的反模式。
    故：**在 Seal 时把算法要的一切都算好。** 算法若需要额外数据，
    从 pcm.mapped.* 自己算，不许要求 Core 增加端口。

MUST:
    - 严格按 profile.PORTS 生成，端口名为键、形状与 dtype 与声明一致
    - 多维度端口的**字段顺序必须**取自 contract.FIELD_LAYOUTS（见下）
    - 音高必须是**绝对音高**（Hz），不得 chroma 化
    - 未发声帧的 f0 置 0 且 voiced=0（不要用 NaN —— 它会污染后续统计）

MUST NOT:
    - 硬编码端口名列表（必须由 profile.PORTS 驱动）
    - 降采样后算音高（实测：22.05 kHz 下 D5 被判成 D4，恰好 −1200 音分）
    - chroma 化音高（chroma 八度不变，会把差一个八度的错音判成正确）
    - 在未发声帧上给出 f0 猜测值（宁可为 0 + voiced=0）

INPUT:
    samples: float32 mono PCM
    sample_rate: int

OUTPUT:
    各端口的 ndarray，键为 profile 中的 port_id

BUILD-INSTRUCTION:
    .spec/build/FILE-103-v1.md
'''

from __future__ import annotations

import numpy.typing as npt

MIN_STABLE_NOTE_SEC: float = 0.150
"""参与音准统计的最短音长（秒）。

短于此的音，周期数太少，f0 估计不可靠 —— 把它算进"走音比例"
会引入噪声而非信号。规格 §7 的「稳定音」即指达到此长度的音。
"""

VOICED_CONFIDENCE_FLOOR: float = 0.5
"""低于此置信度的帧视为未发声。

具体量纲由实现选用的估计器决定（如 pYIN 的 voiced_prob）。
这里只冻结**下游可依赖的语义**：confidence < floor ⇒ voiced == 0。
"""


def materialize_pitch(samples: npt.NDArray, sample_rate: int) -> npt.NDArray:
    """生成逐帧音高曲线，形状 (n_frames, n_fields)。

    字段顺序 = contract.FIELD_LAYOUTS['pitch'] = (f0_hz, voiced, confidence)。

    ⚠ 绝对音高，不是 chroma。这是硬要求：
    chroma 是八度不变的，用它做音准会把「低了一个八度」判成完全正确。

    ⚠ 必须在 profile.AUDIO.sample_rate 上运行。不得为了速度降采样 ——
    实测证据：22.05 kHz 下同一段音频的 D5 会被判成 D4（−1200 音分）。

    未发声帧：f0_hz = 0, voiced = 0, confidence 如实报告。
    **不要用 NaN** —— 它会静默污染中位数/均值等后续统计。
    """
    raise NotImplementedError("SHELL: FILE-103 待注入实现")


def materialize_rms(samples: npt.NDArray) -> npt.NDArray:
    """生成逐帧 RMS 能量包络，形状 (n_frames,)。

    窗长/帧移取 profile.MATERIALIZE.rms_frame_length / rms_hop_length
    （刻意比音高窗密，以保留起音瞬态）。

    单位：线性 RMS。**不要在这里转 dB** —— 转 dB 是算法侧的表达选择。
    """
    raise NotImplementedError("SHELL: FILE-103 待注入实现")


def materialize_chroma(samples: npt.NDArray) -> npt.NDArray:
    """生成低分辨率 chroma，形状 (n_frames, 12)。

    字段顺序 = contract.FIELD_LAYOUTS['chroma']，**bin 0 = C**（不是 A）。
    这个起点同样有歧义，故一并冻结。

    ⚠ 本端口的用途是**对齐与可复现**，明确**不作为评分依据**：
    chroma 八度不变，无法区分 C4 与 C5。
    保留在数据面里是为了让审查者能重跑对齐、验证 warp_path 不是凭空来的。
    """
    raise NotImplementedError("SHELL: FILE-103 待注入实现")


def materialize_notes(
    pitch: npt.NDArray,
    rms: npt.NDArray,
    sample_rate: int,
) -> npt.NDArray:
    """生成参考侧逐音摘要，形状 (n_notes, n_fields)。

    字段顺序 = contract.FIELD_LAYOUTS['notes'] = (onset_sec, f0_hz, rms)。

    为什么需要它：它让算法能按**音**而不是按**帧**组织结果，
    从而输出「第 7 个音偏低 40 音分」这种**可定位**的结论，
    而不是「整体音准误差 40 音分」这种无法行动的数字。

    只对 voiced 且连续时长 ≥ MIN_STABLE_NOTE_SEC 的片段成音。
    """
    raise NotImplementedError("SHELL: FILE-103 待注入实现")
