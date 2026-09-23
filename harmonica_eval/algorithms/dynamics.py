'''
FILE-ID:      FILE-203
COMPONENT:    COMP-C3 Algorithm
SPEC:         SPEC.md@v2.1 §5.5 · profile.PORTS['rms.*']

ROLE:
    力度对比：比较参考与练习的逐音能量，输出动态差异。

INTENT:
    力度是口琴演奏中"气息控制"的可观测量。它不同于音准与节奏：
    力度没有"对错"，只有"差异" —— 因此本算法不设阈值判据，
    只报告差异的大小与离散程度。

    ⚠ 单位必须是 dB。线性振幅的差值是**不可解释**的：
    同样"差 0.1"，在弱音段是巨大差异，在强音段是听不出来。
    dB 是对数刻度，符合听觉感知，也符合"这个数字该怎么读"的要求
    （AGENTS.md：每个数字都要能回答它是什么、怎么算的、单位是什么）。

MUST:
    - 消费 rms.reference / rms.practice
    - 用 WARPED 轴语义（力度关心"这个音吹得多强"，不关心"何时吹"）
    - 输出以 dB 为单位的逐音差值
    - 报告离散度（σ 或 MAD），而不只是均值 ——
      均值相同的两条曲线，感知上可以完全不同
    - 失败也返回 AlgorithmResultEnvelope

MUST NOT:
    - 用线性振幅做差值上报（见上）
    - 使用 REFERENCE 轴（那会把时间错位误算成力度差）
    - 把静音段的 RMS 纳入统计（那是"没吹"，不是"吹得轻"）
    - 设"合格阈值" —— 力度没有对错，只陈述差异（与 pitch 的区别所在）
    - 输出教学结论（"气息不稳"）—— 那是用户的判断，不是我们的输出

INPUT:
    surface: AlgorithmDataContract（只读）

OUTPUT:
    AlgorithmResultEnvelope，payload 含：
        逐音能量差（dB）、中位差、离散度、参与统计的音数

BUILD-INSTRUCTION:
    .spec/build/FILE-203-v1.md
'''

from __future__ import annotations

from ..contract import AlgorithmDataContract, AlgorithmResultEnvelope, TimelineBasis

ALGORITHM_ID: str = "dynamics"
ALGORITHM_VERSION: str = "1.0.0"

AXIS: TimelineBasis = TimelineBasis.WARPED
"""本算法使用的时间轴：**时间归一化**。

力度关心"这个音吹得多强"，与"何时吹"无关；
用归一化轴可以消除时间错位对能量对齐的干扰。
这是与 timing 相反的取舍 —— 两者刻意用不同的轴。
"""

DB_FLOOR: float = -80.0
"""dB 下限，用于避免 log(0)。

−80 dBFS 约等于 1e-4 线性幅度，与 core.ingest.SILENCE_RMS_THRESHOLD 同量级。
低于此值的帧按静音处理，不参与统计。
"""


def to_db(rms: object) -> object:
    """把线性 RMS 转成 dB。

    必须**先钳位**再取对数（见 DB_FLOOR），否则静音帧会产出 -inf，
    而 -inf 会在后续求均值时把整段统计变成 NaN。
    """
    raise NotImplementedError("SHELL: FILE-203 待注入实现")


def align_by_note(
    ref_rms_db: object,
    prac_rms_db: object,
    note_boundaries: object,
) -> object:
    """按音对齐两侧的能量，返回逐音的能量对。

    用 WARPED 轴语义：两侧已时间归一化，可按音索引直接对应。
    静音（低于 DB_FLOOR）的段**不参与**统计。
    """
    raise NotImplementedError("SHELL: FILE-203 待注入实现")


def compute_deltas(aligned: object) -> object:
    """计算逐音能量差（dB）。

    符号约定：**练习 − 参考**。
    正 = 练习更强，负 = 练习更弱。必须保留符号 ——
    "整体偏弱"与"只是不稳"需要完全不同的处理。
    """
    raise NotImplementedError("SHELL: FILE-203 待注入实现")


def summarize_deltas(deltas_db: object) -> object:
    """汇总力度指标。

    至少产出：
        median_db     中位能量差（带符号）
        spread_db     离散度（MAD 或 σ，须在实现中明确选哪个）
        n_notes_used  参与统计的音数

    ⚠ 本算法**不产出**"合格/不合格" —— 力度没有绝对对错（区别于 pitch）。
    这处留白是刻意的：报告差异，让用户判断。
    """
    raise NotImplementedError("SHELL: FILE-203 待注入实现")


def run(surface: AlgorithmDataContract) -> AlgorithmResultEnvelope:
    """算法入口。

    流程：读 rms.* → 转 dB → 按音对齐 → 求差 → 汇总 → 装信封。

    失败：返回 status='FAILED' 的信封，不抛异常。
    """
    raise NotImplementedError("SHELL: FILE-203 待注入实现")
