'''
FILE-ID: FILE-004
COMPONENT: COMP-CONFIG（配置，本身不是组件）
SPEC: SPEC.md@v2.1 · COMPONENTS.md@v2 §4 · PLAN.md@v2 §三

ROLE:
    CORE_PROFILE_V0.1 —— 全部冻结参数 + **封闭端口清单**的唯一定义处。

INTENT:
    让「数据面里有什么」成为**一个可读、可审、可验的常量表**，
    而不是散落在 C2 各模块里的隐式约定。

DESIGN-RULING（负责人裁定，本文件是其落地）:
    **Core 预生成，端口清单封闭。算法适配 Core，不是 Core 适配算法。**

    因此本文件的 PORTS 元组是**穷举**的：
    Seal 时 profile 里列的端口全部生成，profile 里没有的**永不存在**。
    算法若需要额外数据，**从 PCM 自己算**——不许要求 Core 增加端口。

    这消除了「惰性计算」必然带来的协商协议
    （特征声明→解析→版本→缓存失效→失败语义），
    从而避免 Core 的接口变成**插件需求的函数**。

MUST:
    - 全部数值为**冻结常量**，不得在运行时依算法需求变化
    - 每个参数带单位与依据（实测 / 规格 / 工程判断）
    - PORTS 必须穷举，且必须包含 CORE_REQUIRED_PORTS

MUST NOT:
    - import core / host / algorithms / cockpit
    - 出现「按算法需求扩展端口」的任何机制
    - 依赖环境变量或运行时可变的配置源

INPUT:
    （无）

OUTPUT:
    PROFILE_VERSION · AUDIO · ALIGN · MATERIALIZE · BUDGET · PORTS · PortSpec

BUILD-INSTRUCTION:
    .spec/build/FILE-004-v1.md
'''

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .contract import (
    CORE_REQUIRED_PORTS,
    FIELD_LAYOUTS,
    UNITS_VOCABULARY,
    TimelineBasis,
)

PROFILE_VERSION = "CORE_PROFILE_V0.1"
"""数据面身份的一部分。数据面内容 = f(reference, practice, PROFILE_VERSION)。"""


# ═════════════════════════════════════════════════════════════════════
# 一 · 音频标准化
# ═════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AudioSpec:
    """ingest 阶段的标准化目标。"""

    sample_rate: int = 44100
    """Hz。**不可下调**：实测 22.05 kHz 下 pYIN 把 D5 判成 D4（恰好 −1200 音分）。
    采样率是音高结果的成因，不是可选优化。"""

    channels: int = 1
    """恒为单声道。多声道在此阶段下混。"""

    dtype: str = "float32"
    """统一浮点精度，避免各端口间的隐式转换。"""

    min_duration_sec: float = 45.0
    """规格下限（SPEC §2）。短于此 → INPUT_TOO_SHORT。"""

    max_duration_sec: float = 120.0
    """规格上限（SPEC §2）。超过则拒绝，不静默截断。"""


AUDIO = AudioSpec()


# ═════════════════════════════════════════════════════════════════════
# 二 · 对齐
# ═════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AlignSpec:
    """时间对齐参数。**内存主杠杆在这里。**"""

    hop_length: int = 2048
    """帧移（采样点）。**这是整个 profile 最重要的一个数字。**

    实测（spike_dtw_memory.py，120 s 音频）：

        hop=512  → DTW 代价矩阵 855 MB
        hop=2048 → DTW 代价矩阵  53 MB   （降 16×，平方反比）

    注意：`librosa.sequence.dtw` 的代价矩阵是 **float64**（非 float32），
    故实际占用是 N²×8B。且 `global_constraints=True` **不减少**矩阵分配，
    只约束路径、降低耗时——不要误以为加了带宽就省内存。

    降分辨率的代价：对齐时间精度约 ±hop/2 采样点（≈ ±23 ms @ 2048）。
    对「抢拍/拖拍」这一量级（实测中位 26 ms）而言是**临界**的，
    故对齐后的细化由 warp 阶段在样本级插值完成，不依赖帧级精度。
    """

    n_chroma: int = 12
    """chroma 维度。12 平均律。"""

    band_rad: float = 0.25
    """Sakoe-Chiba 带宽（相对时长比例）。防止病态路径。"""

    global_constraints: bool = True
    """必须开启。关闭会让路径可能严重违反单调性。"""


ALIGN = AlignSpec()


# ═════════════════════════════════════════════════════════════════════
# 三 · 物化参数
# ═════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MaterializeSpec:
    """预生成阶段（features.py）的参数。"""

    frame_length: int = 2048
    """分析窗长（采样点）。@44.1kHz ≈ 46.4 ms。"""

    pitch_frame_length: int = 2048
    """音高估计窗长。与 frame_length 分开声明，因为二者语义不同：
    音高要求窗内有稳定周期，能量只要求统计意义。"""

    pitch_hop_length: int = 2048
    """★ 音高帧移。G5 修正新增 —— 第一版**根本没有这个数字**。

    第一版只声明了窗长（pitch_frame_length），实现者只能猜帧移：
    猜 2048（= ALIGN.hop_length）与猜 256（= rms_hop_length）都不报错，
    但产出的 pitch 曲线时间刻度会差 8×。

    取 2048（≈46 ms）的理由：音准现在**按音聚合**（用 notes.* 索引），
    不做逐帧精细时间定位，故不需要 RMS 那样密的时间分辨率。
    """

    rms_frame_length: int = 1024
    """RMS 包络窗长。比音高窗短，以保留起音的瞬态。"""

    rms_hop_length: int = 256
    """RMS 帧移。比 hop_length 密，因为力度变化需要时间分辨率。"""

    fmin_hz: float = 130.81
    """音高搜索下界 = C3（MIDI 48）。口琴实际音域 C4–D5（MIDI 60–74），
    留一个八度余量以吸收走调变体的向下偏移。"""

    fmax_hz: float = 2093.0
    """音高搜索上界 = C7（MIDI 96）。刻意放宽：
    宁可让 estimator 自己判否，也不要因搜索域太窄而钳位。"""


MATERIALIZE = MaterializeSpec()


# ═════════════════════════════════════════════════════════════════════
# 四 · 预算与上限
# ═════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class BudgetSpec:
    """原型阶段的预算。**故意宽松**——本轮是快速原型验证，不是成品优化。"""

    max_surface_bytes: int = 512 * 1024 * 1024
    """数据面总量上限 512 MB。超出 → CORE_BUILD_FAILED。

    依据：预生成清单（11 个端口）在 120 s 音频下实测约 10–20 MB，
    余量约 25×。放宽是为了让实现者**不必**为省内存牺牲正确性——
    内存优化不属于本轮目标（负责人裁定：Mac 先行，先跑通）。"""

    peak_memory_note: str = (
        "对齐阶段是峰值来源。hop=2048 时实测约 53 MB（120 s）。"
        "若实现者改用更细 hop，必须先重跑 spike_dtw_memory.py 确认预算。"
    )


BUDGET = BudgetSpec()


# ═════════════════════════════════════════════════════════════════════
# 五 · 封闭端口清单 ★ 本文件的核心
# ═════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PortSpec:
    """一个端口的生成配方（profile 侧声明，非运行时描述符）。"""

    port_id: str
    units: str
    dimensions: Sequence[str]
    element_type: str
    timeline_basis: TimelineBasis
    produced_by: str
    """哪个模块负责生成它。用于审查「谁生成了清单外的端口」。"""

    rationale: str
    """为什么需要它。**每个端口都必须能回答这个问题**——
    答不出来就该从清单里删掉。"""

    field_names: Sequence[str] = ()
    """多维度端口的字段名，顺序即内存布局。单维端口留空。

    **必须**与 `contract.FIELD_LAYOUTS[类别前缀]` 一致 ——
    这是防止「f0_hz 与 voiced 静默错位」的唯一手段。"""

    hop_length: int = 0
    """★ 该端口的**帧移**（采样点）。帧类端口必须声明，非帧类填 0。
    （G5 修正：盲审发现的静默分叉点。）

    为什么必须有这个字段：`read(port_id, (t0,t1))` 的单位是**秒**，
    而帧类端口的第二维是**帧**。秒→帧的换算必须有唯一依据，
    否则两个实现者会算出不同的时间偏移 —— **而且不会报错**。

    第一版的实际情况：
        ALIGN.hop_length      = 2048   ← 这是**对齐用 chroma** 的帧移
        MATERIALIZE.frame_length = 2048  ← 这是**窗长**，不是帧移
        MATERIALIZE.rms_hop_length = 256 ← RMS 的帧移
        pitch.* / chroma.lowres.* 的帧移：**根本没有声明**

    `frame_length` 与 `hop_length` 数值恰好都是 2048，是**巧合**，不是约定。
    实现者若顺手用 ALIGN.hop_length 去换算 pitch 的帧号，会得到错误时刻；
    若用 rms_hop_length（256），则差 8×。两种都不会报错。

    该字段同时让 `assert_profile_integrity()` 能检查：
        - 含 'frame' 维度的端口必须声明 hop_length > 0
        - 不含 'frame' 维度的端口必须留 0""".rstrip()


PORTS: tuple[PortSpec, ...] = (
    # ── 对齐结果（真正必须物化的东西）────────────────────────────
    PortSpec(
        port_id="warp_path",
        units="index",
        dimensions=("warp_point", "axis"),
        field_names=("reference_frame", "practice_frame"),
        element_type="int32",
        timeline_basis=TimelineBasis.REFERENCE,
                hop_length=0,
produced_by="core.align",
        rationale=(
            "对齐的唯一产物。实测仅 165 KB（120 s），"
            "却是其余全部端口的生成依据 —— 相对 DTW 代价矩阵是 1/5300。"
        ),
    ),

    # ── 两份对齐 PCM（宪章 §11 逃生口，永远存在）─────────────────
    PortSpec(
        port_id="pcm.mapped.reference",
        units="amplitude",
        dimensions=("sample",),
        element_type="float32",
        timeline_basis=TimelineBasis.REFERENCE,
                hop_length=0,
produced_by="core.surface",
        rationale=(
            "逃生口甲：算法永远能拿到参考 PCM 自行做特有预处理，"
            "因此 profile 只决定「快不快」，不决定「能不能」。"
        ),
    ),
    PortSpec(
        port_id="pcm.mapped.practice",
        units="amplitude",
        dimensions=("sample",),
        element_type="float32",
        timeline_basis=TimelineBasis.REFERENCE,
                hop_length=0,
produced_by="core.surface",
        rationale=(
            "逃生口乙：练习演奏保留源时间。"
            "节奏类指标**只能**在这条轴上算 —— "
            "用 warped 轴报抢拍拖拍是构造性错误（SPEC §5.5）。"
        ),
    ),
    PortSpec(
        port_id="pcm.warped.practice",
        units="amplitude",
        dimensions=("sample",),
        element_type="float32",
        timeline_basis=TimelineBasis.WARPED,
                hop_length=0,
produced_by="core.surface",
        rationale=(
            "时间归一化后的练习演奏，与参考等长。"
            "供音高/力度类指标使用 —— 它们关心「弹了什么」，不关心「何时弹」。"
        ),
    ),

    # ── 音高曲线（音准算法的直接输入）────────────────────────────
    PortSpec(
        port_id="pitch.reference",
        units="hz",
        dimensions=("frame", "field"),
        field_names=("f0_hz", "voiced", "confidence"),
        element_type="float32",
        timeline_basis=TimelineBasis.REFERENCE,
                hop_length=MATERIALIZE.pitch_hop_length,
produced_by="core.features",
        rationale=(
            "逐帧 f0 + voiced 标志 + 置信度（field 维）。"
            "预生成是因为它是音准算法的**直接**输入，现算不划算。"
        ),
    ),
    PortSpec(
        port_id="pitch.practice",
        units="hz",
        dimensions=("frame", "field"),
        field_names=("f0_hz", "voiced", "confidence"),
        element_type="float32",
        timeline_basis=TimelineBasis.REFERENCE,
                hop_length=MATERIALIZE.pitch_hop_length,
produced_by="core.features",
        rationale=(
            "练习侧音高曲线，与参考同轴（REFERENCE），"
            "从而两条曲线可以逐帧直接相减得到音分误差。"
        ),
    ),

    # ── 能量包络（力度算法的直接输入）────────────────────────────
    PortSpec(
        port_id="rms.reference",
        units="rms",
        dimensions=("frame",),
        element_type="float32",
        timeline_basis=TimelineBasis.REFERENCE,
                hop_length=MATERIALIZE.rms_hop_length,
produced_by="core.features",
        rationale="逐帧 RMS。力度对比需要它，且真值来自 MIDI velocity。",
    ),
    PortSpec(
        port_id="rms.practice",
        units="rms",
        dimensions=("frame",),
        element_type="float32",
        timeline_basis=TimelineBasis.REFERENCE,
                hop_length=MATERIALIZE.rms_hop_length,
produced_by="core.features",
        rationale="同上。与参考同轴以便逐帧比较。",
    ),

    # ── 低分辨率 chroma（仅供对齐，不对外评分）───────────────────
    PortSpec(
        port_id="chroma.lowres.reference",
        units="chroma",
        dimensions=("frame", "bin"),
        field_names=("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"),
        element_type="float32",
        timeline_basis=TimelineBasis.REFERENCE,
                hop_length=ALIGN.hop_length,
produced_by="core.features",
        rationale=(
            "对齐的输入。保留在数据面里是为了**可复现**："
            "审查者能用它重跑对齐，验证 warp_path 不是凭空来的。"
            "**明确不作为评分依据**（chroma 是八度不变的）。"
        ),
    ),
    PortSpec(
        port_id="chroma.lowres.practice",
        units="chroma",
        dimensions=("frame", "bin"),
        field_names=("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"),
        element_type="float32",
        timeline_basis=TimelineBasis.REFERENCE,
                hop_length=ALIGN.hop_length,
produced_by="core.features",
        rationale="同上，练习侧。",
    ),

    # ── 逐音摘要（算法的索引层）──────────────────────────────────
    # ★★ MOLD BREAK 修正（§20 盲审情况 A）★★
    #
    # 这里原先是**不对称**的：只有 notes.reference，没有 notes.practice。
    # 而 pitch / timing / dynamics **三者都声称**"可定位到第几个音"。
    #
    # 这是端口表的结构性缺陷，不是某个算法少声明了一个端口：
    #   pitch.py    "产出逐音误差（音分，可定位到第几个音）" ← 凭什么知道第几个？
    #   timing.py   声明了 notes.reference（唯一声明者）✓
    #   dynamics.py "逐音能量差"                          ← 练习侧无索引可用
    #
    # 两个独立盲审模型各自复现了后果（dynamics 的轴自相矛盾），
    # 但根因在这里 —— **"按音比较"这个能力原先只有一半。**
    PortSpec(
        port_id="notes.reference",
        units="index",
        dimensions=("note", "field"),
        field_names=("onset_sec", "f0_hz", "rms"),
        element_type="float32",
        timeline_basis=TimelineBasis.REFERENCE,
                hop_length=0,
produced_by="core.features",
        rationale=(
            "参考侧逐音摘要（起音时刻/音高/能量）。"
            "它让算法能按**音**而不是按**帧**组织结果，"
            "从而输出「第 7 个音偏低 40 音分」这种可定位的结论。"
        ),
    ),
    PortSpec(
        port_id="notes.practice",
        units="index",
        dimensions=("note", "field"),
        field_names=("onset_sec", "f0_hz", "rms"),
        element_type="float32",
        timeline_basis=TimelineBasis.REFERENCE,
                hop_length=0,
produced_by="core.features",
        rationale=(
            "★ 盲审补齐的对称项。练习侧逐音摘要，与 notes.reference **同轴**"
            "（都在源时间网格上）。"
            "没有它，「按音对齐」在练习侧**无索引可用** —— "
            "dynamics 只能退而用「WARPED 轴」当代理，"
            "而那是一个无法满足的约束（数据面里没有 WARPED 轴的 rms）。"
            "正确机制是**按音配对**，不是按轴配对。"
        ),
    ),
)

PORT_INDEX: dict[str, PortSpec] = {p.port_id: p for p in PORTS}
"""按 port_id 索引。surface.py 用它来驱动生成与校验。"""


def assert_profile_integrity() -> None:
    """profile 自检。**在 import 时即执行**，让配置错误立刻暴露。

    检查六件事：
      1. 端口清单是**封闭**的：无重复 port_id
      2. 逃生口存在：CORE_REQUIRED_PORTS 全部被声明
      3. 每个端口都有非空 rationale（答不出「为什么需要」就该删）
      4. 多维度端口的字段顺序与契约 FIELD_LAYOUTS 一致
      5. ★ 帧类端口必须声明 hop_length，非帧类必须留 0
      6. ★ 端口对称性：X.reference 与 X.practice 要么都有、要么都没有

    第 5、6 条是 `MOLD BREAK` 后新增的（§20 盲审情况 A）。
    二者都属于「不报错、只静默算错/静默无法实现」的缺陷类别 ——
    与第 4 条同一个教训，只是我第一版没把它推广到帧栅格与端口对称性。

    失败即抛，不返回布尔值 —— 配置错误不该被忽略。
    """
    ids = [p.port_id for p in PORTS]

    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"端口清单存在重复: {sorted(duplicates)}")

    missing = [p for p in CORE_REQUIRED_PORTS if p not in ids]
    if missing:
        raise ValueError(
            f"违反宪章 §11 逃生口：缺少必需端口 {missing}。"
            "任何 profile 都必须含两份对齐 PCM，"
            "否则算法无法自行做特有预处理。"
        )

    no_rationale = [p.port_id for p in PORTS if not p.rationale.strip()]
    if no_rationale:
        raise ValueError(
            f"以下端口未说明存在理由: {no_rationale}。"
            "端口清单封闭的前提是「每个端口都能回答为什么需要它」。"
        )

    # 检查 4：多维度端口必须声明字段顺序，且与契约一致。
    # 这是独立盲审发现的缺口 —— 没有它，两个实现者会写出不同的内存布局，
    # 读出来的 f0_hz 可能是 voiced，**而且不会报错，只会静默算错**。
    for spec in PORTS:
        if len(spec.dimensions) <= 1:
            if spec.field_names:
                raise ValueError(
                    f"端口 {spec.port_id} 是单维，不应声明 field_names"
                )
            continue

        prefix = spec.port_id.split(".")[0]
        expected = FIELD_LAYOUTS.get(prefix)
        if expected is None:
            raise ValueError(
                f"端口 {spec.port_id} 是多维，但 contract.FIELD_LAYOUTS 中"
                f"没有 '{prefix}' 的字段定义。多维端口必须有明确字段顺序，"
                "否则下游会静默错位读取。"
            )
        if tuple(spec.field_names) != tuple(expected):
            raise ValueError(
                f"端口 {spec.port_id} 的 field_names={tuple(spec.field_names)} "
                f"与契约定义的 {tuple(expected)} 不一致。"
            )

    # 检查 5：帧类端口必须声明帧移，非帧类必须留 0。
    # G5 修正 —— 盲审发现的静默分叉点：read() 的单位是秒，而帧类端口的
    # 第二维是帧，秒→帧换算必须有唯一依据。第一版 pitch.*/chroma.* 的
    # 帧移**根本没有声明**，两个实现者会算出差 8× 的时刻且不报错。
    for spec in PORTS:
        is_frame_based = "frame" in spec.dimensions
        if is_frame_based and spec.hop_length <= 0:
            raise ValueError(
                f"端口 {spec.port_id} 含 'frame' 维度，但未声明 hop_length。"
                "read(time_range) 的单位是秒，没有帧移就无法唯一换算出帧号 —— "
                "实现者只能猜，而猜错不会报错，只会静默返回错误时间窗的数据。"
            )
        if not is_frame_based and spec.hop_length != 0:
            raise ValueError(
                f"端口 {spec.port_id} 不含 'frame' 维度，"
                f"但声明了 hop_length={spec.hop_length}。"
                "非帧类端口声明帧移会产生误导（读的人会以为它也有帧结构）。"
            )

    # 检查 7：units 必须在受控词表内（G10 修正）。
    # 开放式字符串会让两个实现者写出 "hz"/"Hz"/"hertz" 三种，
    # 而下游按 == "hz" 判断时静默不匹配。
    for spec in PORTS:
        if spec.units not in UNITS_VOCABULARY:
            raise ValueError(
                f"端口 {spec.port_id} 的 units='{spec.units}' "
                f"不在 contract.UNITS_VOCABULARY 内。\n"
                f"合法取值：{sorted(UNITS_VOCABULARY)}\n"
                "若确实需要新单位，先加进词表 —— "
                "否则下游按字符串相等判断端口语义时会静默漏配。"
            )

    # 检查 8：端口对称性。
    # §20 盲审情况 A 的根因 —— 第一版 notes.* 只有 reference 侧，
    # 导致 dynamics 写出无法满足的 MUST（要求一个不存在的端口轴）。
    # 对称性破裂是可机械检查的，故在此设卡。
    ids_set = set(ids)
    for pid in ids:
        if pid.endswith(".reference"):
            twin = pid[: -len(".reference")] + ".practice"
        elif pid.endswith(".practice"):
            twin = pid[: -len(".practice")] + ".reference"
        else:
            continue
        # 例外：pcm.warped.* 刻意只有练习侧 —— 参考无需被拉伸到自己。
        if pid.startswith("pcm.warped.") or twin.startswith("pcm.warped."):
            continue
        if twin not in ids_set:
            raise ValueError(
                f"端口对称性破裂：{pid} 存在但 {twin} 不存在。\n"
                "参考侧与练习侧要么都有、要么都没有 —— "
                "只有一侧会让「按音/逐帧比较」在另一侧无索引可用，"
                "而算法会因此写出无法满足的约束（这正是盲审发现的那个缺陷）。\n"
                "唯一例外：pcm.warped.* 刻意只有练习侧（参考无需被拉伸）。"
            )


assert_profile_integrity()


__all__ = [
    "PROFILE_VERSION",
    "AUDIO", "ALIGN", "MATERIALIZE", "BUDGET",
    "AudioSpec", "AlignSpec", "MaterializeSpec", "BudgetSpec",
    "PORTS", "PORT_INDEX", "PortSpec",
    "assert_profile_integrity",
]
