'''
FILE-ID:      FILE-202
COMPONENT:    COMP-C3 Algorithm
SPEC:         SPEC.md@v2.1 §5.5（两轴分离）· contract.TimelineBasis

ROLE:
    节奏对比：比较参考与练习的**起音时刻**，输出抢拍/拖拍。

INTENT:
    这是全系统**唯一**必须在保留源时间的轴上计算的算法。

    ★ 为什么这不是一个实现细节，而是构造性约束：
    数据面提供两条轴 —— REFERENCE（保留源时间）与 WARPED（时间归一化）。
    归一化会把练习拉伸到与参考等长，**抢拍拖拍在这个操作里被抹掉了**。
    因此拿 WARPED 轴算节奏，结果恒等于 0，而且**看起来一切正常**。

    这是一个不会报错、只会给出错误答案的陷阱。故本文件把轴的约束
    写在最显眼处，并要求每条输出曲线显式声明自己的 timeline_basis。

MUST:
    - 用 pcm.mapped.reference / pcm.mapped.practice（**两者都是 REFERENCE 轴**）
    - 参考侧起音时刻取自 notes.reference（同一轴上）
    - 输出带符号的偏差（负 = 抢拍，正 = 拖拍），单位毫秒
    - 每条输出曲线声明 TimelineBasis.REFERENCE
    - 失败也返回 AlgorithmResultEnvelope

MUST NOT:
    - 使用 pcm.warped.practice 或任何 WARPED 轴数据（会抹掉本算法要测的东西）
    - 只报绝对值（丢失"抢"与"拖"的方向 —— 修正方向相反）
    - 把起音检测的差异当成"错音"（那是 pitch 的职责）
    - 输出教学结论

INPUT:
    surface: AlgorithmDataContract（只读）

OUTPUT:
    AlgorithmResultEnvelope，payload 含：
        逐音起音偏差（ms，带符号）、中位偏差、离散度、抢拍/拖拍比例

BUILD-INSTRUCTION:
    .spec/build/FILE-202-v1.md
'''

from __future__ import annotations

from ..contract import AlgorithmDataContract, AlgorithmResultEnvelope, TimelineBasis

ALGORITHM_ID: str = "timing"
ALGORITHM_VERSION: str = "1.0.0"

AXIS: TimelineBasis = TimelineBasis.REFERENCE
"""本算法**必须**使用的时间轴。★ 硬约束，不可改为 WARPED。

用 WARPED 会让结果恒为 0 且不报错 —— 见模块 docstring。
把它定义成模块常量是为了让审查者能一眼看到、也便于 grep 验证。
"""

ONSET_MATCH_TOLERANCE_SEC: float = 0.5
"""起音配对的最大时间容差（秒）。

超过此值认为两个起音无法配对（漏音或多余音），
不计入"偏差"统计 —— 把 5 秒的错位当成"拖了 5000 毫秒"是荒谬的。
"""


def detect_onsets(samples: object, sample_rate: int) -> object:
    """从**保留源时间**的 PCM 检测起音时刻（秒）。

    输入必须是 pcm.mapped.*（REFERENCE 轴）。
    参考侧可以用 notes.reference 的 onset_sec 作为更可靠的真值 ——
    因为参考曲目的真值来自 MIDI，比从音频检测更准。
    """
    raise NotImplementedError("SHELL: FILE-202 待注入实现")


def match_onsets(
    ref_onsets: object,
    prac_onsets: object,
    tolerance_sec: float = ONSET_MATCH_TOLERANCE_SEC,
) -> object:
    """把练习的起音与参考的起音配对。

    返回配对结果，**必须**同时报告未能配对的起音数：
    漏吹的音与多吹的音不产生"时间偏差"，但它们是重要的信息，
    静默丢弃会让报告看起来比实际更好。
    """
    raise NotImplementedError("SHELL: FILE-202 待注入实现")


def compute_deviations(matched: object) -> object:
    """计算逐音起音偏差。

    **带符号**：负 = 抢拍（早于参考），正 = 拖拍（晚于参考）。
    只报绝对值会丢掉方向，而修正"抢"与修正"拖"是相反的动作。

    单位：毫秒。
    """
    raise NotImplementedError("SHELL: FILE-202 待注入实现")


def summarize_deviations(deviations_ms: object) -> object:
    """汇总节奏指标。

    至少产出：
        median_ms        中位偏差（带符号）
        mad_ms           中位绝对偏差（离散度）
        early_ratio      抢拍比例
        late_ratio       拖拍比例
        n_matched        成功配对的音数
        n_unmatched      未能配对的音数（**不得隐去**）
    """
    raise NotImplementedError("SHELL: FILE-202 待注入实现")


def run(surface: AlgorithmDataContract) -> AlgorithmResultEnvelope:
    """算法入口。

    ⚠ 实现时第一步就应断言数据来自 REFERENCE 轴。
    读取 pcm.mapped.* / notes.reference（它们的 timeline_basis 都是 REFERENCE）。

    失败：返回 status='FAILED' 的信封，不抛异常。
    """
    raise NotImplementedError("SHELL: FILE-202 待注入实现")
