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
    - 消费 rms.reference / rms.practice / notes.reference / notes.practice
    - **按音配对**两侧能量（不是按时间轴、也不是按帧索引）
    - 输出以 dB 为单位的逐音差值
    - 报告离散度（σ 或 MAD），而不只是均值 ——
      均值相同的两条曲线，感知上可以完全不同
    - 失败也返回 AlgorithmResultEnvelope

MUST NOT:
    - 用线性振幅做差值上报（见上）
    - **按帧直接相减**（那会把时间错位误算成力度差：练习晚吹了 200 ms，
      参考的强拍就会对上练习的弱拍，算出巨大的假差异）
    - 把静音段的 RMS 纳入统计（那是"没吹"，不是"吹得轻"）
    - 设"合格阈值" —— 力度没有对错，只陈述差异（与 pitch 的区别所在）
    - 输出教学结论（"气息不稳"）—— 那是用户的判断，不是我们的输出

★★ MOLD BREAK 修正（§20 盲审情况 A）★★

本模块第一版写着 MUST「用 WARPED 轴语义」、MUST NOT「使用 REFERENCE 轴」，
并声明 `AXIS = TimelineBasis.WARPED`。**这条约束无法满足。**

原因：`rms.reference` / `rms.practice` 在 profile 里都被声明为 REFERENCE 轴，
而数据面里**唯一**的 WARPED 端口是 `pcm.warped.practice` —— 没有 WARPED 轴的 rms。
两个独立盲审模型各自报告了这个冲突，并各自给出三个互相冲突的"出路"。

真正的错误在于**我用"时间轴"当"按音对齐"的代理**：
- 力度想要的不是"WARPED 网格"，而是**"第 n 个音对第 n 个音"**
- 用轴来表达这件事，既丢失了逐音索引，又引入了无法满足的端口要求

正确机制：**按音配对**。两侧各自有 `notes.*` 提供逐音索引
（`notes.reference` / `notes.practice`，都带 onset_sec / f0_hz / rms），
用各自音内的帧区间取能量，再一一配对。
这样"何时吹"被排除的方式是**按音聚合**，而不是"换一条时间轴"。

故 `AXIS` 常量已删除 —— 它编码的是一条错误的约束。
"""
INPUT:
    surface: AlgorithmDataContract（只读）

OUTPUT:
    AlgorithmResultEnvelope，payload 含：
        逐音能量差（dB）、中位差、离散度、参与统计的音数

BUILD-INSTRUCTION:
    .spec/build/FILE-203-v1.md
'''

from __future__ import annotations

from ..contract import AlgorithmDataContract, AlgorithmResultEnvelope

ALGORITHM_ID: str = "dynamics"
ALGORITHM_VERSION: str = "1.0.0"

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


def note_spans(notes: object) -> object:
    """从 `notes.*` 端口算出每个音覆盖的帧区间。

    ★ 这是 MOLD BREAK 补上的函数 —— 第一版把这件事隐式交给了"时间轴"，
    而那是错的机制。

    做法：第 n 个音的区间 = [onset_n, onset_{n+1})，
    最后一个音延伸到它自己的 onset + 一个默认时长（或数据末尾）。
    切分依据是 **onset**，因为 onset 是唯一跨两侧都可比的量
    （它由 `notes.*` 的 onset_sec 给出 —— ★ 那是**检测器输出**，
    不是 MIDI 真值：数据面里没有 MIDI 通路。见 timing.detect_onsets）。

    两侧各自调用一次：`notes.reference` 与 `notes.practice` **分开**切。
    """
    raise NotImplementedError("SHELL: FILE-203 待注入实现")


def align_by_note(
    ref_rms_db: object,
    prac_rms_db: object,
    ref_spans: object,
    prac_spans: object,
) -> object:
    """按音配对两侧的能量，返回逐音的能量对。

    ★ MOLD BREAK 修正：签名从 `(ref, prac, note_boundaries)` 改为
    两侧**各自**的 spans。

    为什么：练习演奏与参考演奏的音数、时长都不同（漏音、多音、抢拍）。
    用**一份**共享边界假设"第 n 个音对第 n 个音"是不成立的。
    正确做法是两侧各自按自己的 onset 切帧，再按**音序**配对，
    配不上的音（一侧多出/缺少）单独记账，不参与差值统计。

    静音（低于 DB_FLOOR）的段**不参与**统计。
    """
    raise NotImplementedError("SHELL: FILE-203 待注入实现")


def compute_deltas(aligned: object) -> object:
    """计算逐音能量差（dB）。

    符号约定：**练习 − 参考**。
    正 = 练习更强，负 = 练习更弱。必须保留符号 ——
    "整体偏弱"与"只是不稳"需要完全不同的处理。

    只对**配得上对**的音求差：一侧多出的音（漏音/多音）不参与统计，
    但要单独计数上报 —— 它们不是"力度差异"，是另一类问题。
    """
    raise NotImplementedError("SHELL: FILE-203 待注入实现")


def summarize_deltas(deltas_db: object) -> object:
    """汇总力度指标。

    至少产出：
        median_db     中位能量差（带符号）
        spread_db     离散度（MAD 或 σ，须在实现中明确选哪个）
        n_notes_used  参与统计的音数
        n_unpaired    未配对的音数（一侧有另一侧无）

    ⚠ 本算法**不产出**"合格/不合格" —— 力度没有绝对对错（区别于 pitch）。
    这处留白是刻意的：报告差异，让用户判断。
    """
    raise NotImplementedError("SHELL: FILE-203 待注入实现")


def run(surface: AlgorithmDataContract) -> AlgorithmResultEnvelope:
    """算法入口。

    流程：读 rms.* / notes.* → 转 dB → 两侧各自按 onset 切分 → 按音配对
          → 求差 → 汇总 → 装信封。

    ★ MOLD BREAK 修正：流程从"换一条时间轴"改为"按音配对"。
    理由见模块 docstring —— 用轴当代理会丢失逐音索引，
    且要求一个数据面里不存在的端口。

    失败：返回 status='FAILED' 的信封，不抛异常。
    """
    raise NotImplementedError("SHELL: FILE-203 待注入实现")
