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

ONSET_MATCH_TOLERANCE_SEC: float = 0.100
"""起音配对的最大时间容差（秒）。超过此值认为两个起音无法配对
（漏音或多余音），不计入"偏差"统计 —— 把 5 秒的错位当成
"拖了 5000 毫秒"是荒谬的。

★ 第三轮修正（§20 盲审第二轮发现）：第一版取 `0.5` 秒，**是拍脑袋定的，
且量级错误**。审查者指出它与本算法要测的现象相差约 20 倍。

用已有数据推导（不是重新拍一个数）：

    约束下界：必须 > 对齐噪声，否则真配对被误拒
              对齐帧级精度 ±23 ms（profile.ALIGN：hop=2048 → ±hop/2）
              → ≥ 2×23 ≈ 46 ms
    约束上界：必须 < 最短统计音长，否则"漏音后的下一个音"会被误配成对
              最短统计音长 = features.MIN_STABLE_NOTE_SEC = 150 ms
              → < 150 ms

    原值 500 ms **比最短音长还大 3.3×** —— 它必然把相邻音误配，
    把假偏差（最多 ±500 ms）灌进中位数。
    而本算法要测的现象量级只有 **26 ms**（profile 实测中位）。

    取 100 ms：
        = 对齐噪声的 4.3×   （足够容忍对齐误差）
        = 最短音长的 0.67×  （不足以跨越一个音）
    两个约束都满足，且与 `MIN_STABLE_NOTE_SEC` 一致。

★ 注意它与"抢拍/拖拍判据"**不是**同一个量：
本常量只回答"两个起音能否配成一对"。
"算不算抢拍"的阈值见下方 `ONSET_DEADBAND_MS`。
"""

ONSET_DEADBAND_MS: float = 23.0
"""判定"抢拍/拖拍"的死区（毫秒）。**第三轮新增** —— §20 盲审第二轮发现
这个阈值在全项目**任何文件里都不存在**，实现者只能自定，
于是不同实现者会产出**不可比**的 early_ratio / late_ratio。

为什么必须有它：`ONSET_MATCH_TOLERANCE_SEC` 只回答"能否配对"，
不回答"算不算抢拍"。没有死区就只有两种选择，都不可接受：
    - 死区 = 0   → 任何 0.1 ms 的差都被计成"抢拍"或"拖拍"，
                   而测量精度本身是 ±23 ms，等于把噪声当信号
    - 死区很大 → 几乎全部音都"准时"，指标退化为常数

取值依据（用已有数据推导，不是拍脑袋）：
    对齐帧级精度 ±23 ms（profile.ALIGN：hop=2048 → ±hop/2 采样点）
    **低于测量精度的差异不可区分于噪声**，故死区 = 23 ms。

    参考量级：抢拍拖拍实测中位 26 ms（profile 记录）。
    即：本死区刚好卡在"噪声"与"真实偏差"的分界上 ——
    恰好一半左右的音会落在死区内，这是**诚实**的结果，
    而不是把所有音都强行分成早/晚两类。

★ 副作用（必须在 payload 里明说）：`early_ratio + late_ratio` **不再等于 1**，
三者满足 `early_ratio + late_ratio + on_time_ratio == 1`。
其中 `on_time_ratio` 的含义是"偏差小于测量精度，无法判定早或晚"——
**不**等于"演奏准确"。故 payload 必须同时报告它，
否则用户看到两个加起来不到 1 的比例会以为是 bug。
"""


def detect_onsets(samples: object, sample_rate: int) -> object:
    """从**保留源时间**的 PCM 检测起音时刻（秒）。

    输入必须是 pcm.mapped.*（REFERENCE 轴）。

    参考侧优先用 `notes.reference` 的 onset_sec（同轴、且已被 features 层
    统一处理过），但**它仍然是检测器输出，不是 MIDI 真值**。

    ★ §20 盲审修正：本函数原先写"参考曲目的真值来自 MIDI，比从音频检测更准"
    —— **这个前提不成立**。数据面里**没有** MIDI 通路：
    `ingest` 只解码音频，`features.materialize_notes(pitch, rms, sample_rate)`
    是从音频派生的音高/能量切出来的，`profile.PORTS` 里没有任何音符事件端口。

    后果（必须在实现与解读时都记住）：
        参考侧自身的起音检测误差会 **1:1 进入每一条偏差**。
        本算法测的是「练习相对参考的**相对**偏差」，
        不是「练习相对乐谱的**绝对**偏差」——
        若参考演奏本身抢拍 30 ms，那 30 ms 会**整体平移**所有结果。

    这也是为什么算法输出里**不得**出现"你比乐谱慢了"这类结论（SPEC §1）。
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

    ★ 键名以 `algorithms.PAYLOAD_SCHEMAS["timing"]` 为**唯一权威**。
    本 docstring 原先写的 `median_ms` / `mad_ms` / `n_matched` / `n_unmatched`
    与冻结表**不一致** —— 那是 §20 盲审发现的硬冲突：
    模块说自己产出 A、注册表说必须恰好产出 B，实现者无法同时满足。

    现统一到冻结表的 8 个键：
        per_note_onset_ms   逐音起音偏差（ms，带符号），长度 == n_notes_used
        median_onset_ms     中位偏差（带符号）
        spread_ms           离散度（MAD about median；口径必须写死在实现里）
        early_ratio         抢拍比例（d < -ONSET_DEADBAND_MS）
        late_ratio          拖拍比例（d > +ONSET_DEADBAND_MS）
        on_time_ratio       落在死区内的比例（**无法判定**早或晚，≠ 演奏准确）
        n_notes_used        参与统计的音数（== 配对数 == len(per_note_onset_ms)）
        n_unpaired          未能配对的音数（漏音 + 多音）

    ⚠ 三者关系：`early_ratio + late_ratio + on_time_ratio == 1.0`。
    必须三个都报 —— 只报前两个的话，用户看到它们加起来不到 1
    会以为是 bug，而实际上那是"测量精度不足以判定"的部分（见 ONSET_DEADBAND_MS）。

    ★ `n_unpaired` 是**必须报告**的，理由与原 docstring 一致
    （"不得隐去"）：漏音/多音不是"节奏偏差"，若不报出来，
    用户会以为整首都被统计了，而实际上有若干音根本没参与。
    """
    raise NotImplementedError("SHELL: FILE-202 待注入实现")


def run(surface: AlgorithmDataContract) -> AlgorithmResultEnvelope:
    """算法入口。

    ⚠ 实现时第一步就应断言数据来自 REFERENCE 轴。
    读取 pcm.mapped.* / notes.reference（它们的 timeline_basis 都是 REFERENCE）。

    失败：返回 status='FAILED' 的信封，不抛异常。
    """
    raise NotImplementedError("SHELL: FILE-202 待注入实现")
