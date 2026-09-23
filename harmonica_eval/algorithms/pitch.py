'''
FILE-ID:      FILE-201
COMPONENT:    COMP-C3 Algorithm
SPEC:         SPEC.md@v2.1 §7 · contract.FIELD_LAYOUTS['pitch'] · profile.PORTS

ROLE:
    音准对比：比较参考与练习的**绝对音高**，输出可定位到具体音的偏差。

INTENT:
    音准是口琴学习者最直接的反馈维度，也是本项目唯一有明确量化阈值的维度
    （规格 §7：稳定音 ≤50 音分）。

    ★ 本算法**必须**用绝对音高，禁止 chroma 化。
    chroma 是八度不变的 —— 用它做音准会把「低了一个八度」判成完全正确。
    实测佐证：同一段音频在 22.05 kHz 下 f0 被判低八度（恰好 −1200 音分），
    若用 chroma 这个错误将完全不可见。

MUST:
    - 消费 pitch.reference / pitch.practice / notes.reference / notes.practice
    - 产出逐音误差（音分，可定位到第几个音）
    - 只在 voiced 且时长 ≥ MIN_STABLE_NOTE_SEC 的音上统计
    - 报告采样率（它是结果的成因，必须随结果一起记录）
    - 失败也返回 AlgorithmResultEnvelope（不抛异常穿透到 C1）

MUST NOT:
    - chroma 化（见上，会把八度错误隐藏掉）
    - **按帧号直接对齐两侧**（见下方 compare_pitch_curves 的长注记：
      REFERENCE 轴不保证帧号对齐）
    - 用 mapped 轴（音准关心"吹了什么"，不关心"何时吹" —— 那是 timing 的事）
    - 在未发声帧上计算误差（那些帧没有音高，不是"音高错"）
    - 输出教学结论（"你这里偏低了"）—— 只到数值层（SPEC §1）

INPUT:
    surface: AlgorithmDataContract（只读）

OUTPUT:
    AlgorithmResultEnvelope，payload 含：
        逐音偏差（音分）、走音比例、中位绝对误差、采样率

BUILD-INSTRUCTION:
    .spec/build/FILE-201-v1.md
'''

from __future__ import annotations

from ..contract import AlgorithmDataContract, AlgorithmResultEnvelope

ALGORITHM_ID: str = "pitch"
ALGORITHM_VERSION: str = "1.0.0"

MAX_CENTS_DEVIATION: float = 50.0
"""稳定音的容许偏差（音分）。来自 SPEC.md §7，不是工程估计值。

超过它即计入「走音比例」。注意这是**判据**，不是"完美线"——
它回答"这个音算不算准"，不回答"有多好"。
"""

MIN_STABLE_NOTE_SEC: float = 0.150
"""参与统计的最短音长（秒）。与 core.features.MIN_STABLE_NOTE_SEC 同义。

短音的音高估计不可靠，纳入统计会引入噪声而非信号。
"""


def hz_to_cents(f0_hz: float, ref_hz: float) -> float:
    """把频率比换算成音分。1200 音分 = 一个八度。

    公式：1200 * log2(f0 / ref)
    未发声（任一为 0）时**不得**调用 —— 调用方须先用 voiced 过滤。
    """
    raise NotImplementedError("SHELL: FILE-201 待注入实现")


def compare_pitch_curves(
    ref_pitch: object,
    prac_pitch: object,
    ref_notes: object,
    prac_notes: object,
    sample_rate: int,
) -> object:
    """逐音比较两侧音高，返回逐音的音分偏差。

    ★★ 由下往上核对代码时修正（原表述是错的）★★

    原文写：「两条曲线同轴（都是 REFERENCE），故可直接逐帧相减」。
    **这个推理不成立。** `TimelineBasis.REFERENCE` 的含义是
    「保留源时间、未被时间归一化」，它**不**蕴含「两侧帧号一一对应」。

    参考与练习是**两段独立录音**，时长各自落在
    `[profile.AUDIO.min_duration_sec, max_duration_sec]` 区间内。
    `pitch.*` 的帧数 = 时长 / `MATERIALIZE.pitch_hop_length`，
    故两侧 n_frames **默认不相等**，逐帧相减无定义。

    为什么这个缺陷一直没暴露：本数据集 01 的全部 wav 都是同一渲染器
    批量产出、长度恰好全是 72.802 s（1568 帧），于是"恰好等长"掩盖了它。
    换一首演奏时长不同的练习曲（这正是真实使用场景）立刻崩。

    正确做法：用两侧各自的 `notes.*` 的 `onset_sec` 建立对应，
    **按音配对**后再比较。这也是 `ALGORITHMS` 声明 pitch 需要
    `notes.reference` + `notes.practice` 的真正理由 ——
    原先的论证只讲到"为了能标注第几个音"（可定位），
    没讲到"不等长根本无法比较"（可比较）。论证不完整，
    所以本函数的签名一直漏掉了这两个参数。

    配对规则：
        - 按音序配对（第 n 个音对第 n 个音），与 dynamics.align_by_note 同口径
        - 配不上的音（一侧多出 / 缺少）单独记账，不参与偏差统计
        - 每对音内部**只在两侧都 voiced 的帧上**求偏差
    一侧有声一侧无声是**漏音/多音**（属于另一类问题），
    不是"音高偏差"，混进来会污染音准统计。

    voiced 处理：未发声帧的 f0_hz 为 0，其 cents 偏差**无定义**
    （`hz_to_cents` 明令不得在任一为 0 时调用）。实现须先按 voiced 过滤。

    实现须引用 contract.FIELD_LAYOUTS['pitch'] 解释 (f0_hz, voiced, confidence)、
    引用 contract.FIELD_LAYOUTS['notes'] 解释 (onset_sec, f0_hz, rms)，
    **不得**另行硬编码字段位置。
    """
    raise NotImplementedError("SHELL: FILE-201 待注入实现")


def summarize_deviations(deviations_cents: object) -> object:
    """把逐音偏差汇总成可上报的指标。

    键名以 `algorithms.PAYLOAD_SCHEMAS["pitch"]` 为**唯一权威**（5 个键）：
        per_note_cents      逐音音分偏差（带符号），长度 == n_notes_used
        median_abs_cents    中位绝对偏差
        off_pitch_ratio     超过 MAX_CENTS_DEVIATION 的音占比
        n_notes_used        参与统计的音数（**必须报告**）
        sample_rate         采样率（结果的成因，不是元数据）

    ⚠ `off_pitch_ratio` 的分母是 `n_notes_used`，故两者必须一起读：
    只报比例的话，「全曲 115 个音里 58 个走音」与
    「12 个音里 6 个走音」会得到同一个数字。

    ★ 已知缺口（由下往上核对发现，如实记录不掩盖）：
    timing 与 dynamics 的 payload 都含 `n_unpaired`（未能配对的音数），
    **pitch 没有**。而 pitch 的配对同样会失败（漏音/多音/音数不等），
    配不上的音同样被排除在统计之外 —— 排除数量却无处报告。
    后果：读者无法分辨「整首都测了」与「只测上了少数几个音」。

    根因是 PAYLOAD_SCHEMAS 由人工维护、三份各自演化，缺少对称性约束。
    修它需要在冻结表加键（接口变更），故此处**不自行添加** ——
    按 §37 Gate Challenge 上报，见本文件 BUILD-INSTRUCTION 的 §10。
    """
    raise NotImplementedError("SHELL: FILE-201 待注入实现")


def run(surface: AlgorithmDataContract) -> AlgorithmResultEnvelope:
    """算法入口。

    流程：读端口 → 比较 → 汇总 → 装信封。

    必须记录 sample_rate —— 它是结果的成因，不是元数据。
    实测：22.05 kHz 下 D5 被判成 D4（−1200 音分）。
    拿到一份没有采样率的音准报告，无法判断它是否可信。

    失败：返回 status='FAILED' 的信封，error_code 取 AlgorithmError 对应码。
    **不抛异常** —— 算法失败不应穿透到 C1，否则故障无法隔离。
    """
    raise NotImplementedError("SHELL: FILE-201 待注入实现")
