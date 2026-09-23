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
    - 消费 pitch.reference / pitch.practice（两者同轴，可逐帧相减）
    - 产出逐音误差（音分，可定位到第几个音）
    - 只在 voiced 且时长 ≥ MIN_STABLE_NOTE_SEC 的音上统计
    - 报告采样率（它是结果的成因，必须随结果一起记录）
    - 失败也返回 AlgorithmResultEnvelope（不抛异常穿透到 C1）

MUST NOT:
    - chroma 化（见上，会把八度错误隐藏掉）
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
    sample_rate: int,
) -> object:
    """逐帧比较两条音高曲线，返回逐音的音分偏差。

    两条曲线同轴（都是 REFERENCE），故可直接逐帧相减 ——
    这正是 profile 把它们都声明为 REFERENCE 的理由。

    ⚠ voiced 处理：只有**两侧都 voiced** 的帧才参与比较。
    一侧有声一侧无声，那是**漏音/多音**（属于另一类问题），
    不是"音高偏差"，混进来会污染音准统计。

    实现须引用 contract.FIELD_LAYOUTS['pitch'] 解释 (f0_hz, voiced, confidence)，
    **不得**另行硬编码字段位置。
    """
    raise NotImplementedError("SHELL: FILE-201 待注入实现")


def summarize_deviations(deviations_cents: object) -> object:
    """把逐音偏差汇总成可上报的指标。

    至少产出：
        median_abs_cents      中位绝对偏差
        off_pitch_ratio       超过 MAX_CENTS_DEVIATION 的音占比
        n_notes_used          参与统计的音数（**必须报告** ——
                              样本量太小的时候，比例类指标没有意义）
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
