'''
FILE-ID: FILE-003
COMPONENT: COMP-CONTRACT（四个组件之间的分界线，本身不是组件）
SPEC: SPEC.md@v2.1 · COMPONENTS.md@v2 · PLAN.md@v2

ROLE:
    跨组件共享的全部类型、枚举、错误码与契约 Protocol。纯声明，无行为。

INTENT:
    让 C1/C2/C3/C4 对「状态、时间基准、端口、结果、失败」使用同一套词汇，
    从结构上消除宪章 §21 Cross-Agent Semantic Variance。
    同时把「四个组件的边界」变成可 import 的实体，而不是文档里的约定。

MUST:
    - 只含 Enum / dataclass / Protocol / 常量元组
    - 每个字段带语义注释，写清单位与时间基准
    - 端口描述符必须能表达 profile.py 的全部字段

MUST NOT:
    - 任何计算、I/O、第三方算法调用
    - import core / host / algorithms / cockpit 的任何模块（本文件是依赖链的根）
    - 定义「便利函数」或默认业务值

DESIGN-RULING（负责人裁定，不可推翻）:
    **Core 预生成，端口清单封闭。算法适配 Core，不是 Core 适配算法。**
    故 AlgorithmDataContract 只有两个**纯查表**操作（manifest / read），
    read() **无副作用**：它不会触发任何计算，也不会失败于「算不出来」。
    若算法需要数据面之外的东西，**从 PCM 自己算**，不许要求 Core 提供。

INPUT:
    （无）

OUTPUT:
    SessionState · TimelineBasis · AlignmentRepresentation · AudioFormat
    PortDescriptor · BufferView · SurfaceManifest · AlgorithmResultEnvelope
    ErrorCode · HarmonicaError 族
    HostContract · AlgorithmDataContract · UiProjectionPort
    FORBIDDEN_OPERATIONS · CORE_REQUIRED_PORTS

BUILD-INSTRUCTION:
    .spec/build/FILE-003-v1.md
'''

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence

import numpy as np
import numpy.typing as npt


# ═════════════════════════════════════════════════════════════════════
# 一 · 会话状态与时间基准
# ═════════════════════════════════════════════════════════════════════

class SessionState(str, Enum):
    """会话状态。**C1 只允许看到这些**；C2 内部阶段不得外泄。

    单调推进，不可回退：
        CREATED → INPUT_READY → BUILDING → DATA_READY
        任一状态可 → FAILED；结束 → CLOSED
    """

    CREATED = "CREATED"
    """会话已创建，尚无输入。"""

    INPUT_READY = "INPUT_READY"
    """两段音频资产都已就位，尚未开始构建。"""

    BUILDING = "BUILDING"
    """C2 正在构建数据面。此状态下**禁止**触发任何算法。"""

    DATA_READY = "DATA_READY"
    """数据面已按 profile 预生成完毕并 Seal。**算法的唯一合法触发点**。"""

    FAILED = "FAILED"
    """构建或运行失败。数据面**不存在**（不得部分发布）。"""

    CLOSED = "CLOSED"
    """会话已销毁，资源已释放。"""


class TimelineBasis(str, Enum):
    """一个量挂在哪条时间轴上。**每个端口都必须声明**。

    依据 SPEC.md §5.5「两轴分离」原文：

    > 时间轴必须同时提供**保留源时间**与**时间归一化**两种表示
    > （对应 Core 数据面的 mapped / warped）。
    > **段级节奏指标必须在保留源时间的表示上计算**，
    > 否则归一化会静默抹掉抢拍拖拍。

    ★★ `MOLD BREAK` 修正（§20 盲审情况 A）★★

    本枚举第一版把 REFERENCE 定义成「保留源时间。对齐后重采样到参考演奏的时间轴」——
    **这两句话互相矛盾**：既保留源时间，又重采样到别人的时间轴，是两条不同的网格。
    该含糊定义向下游传播，直接导致 `algorithms/dynamics.py` 写出一条
    **无法满足的 MUST**（要求读 WARPED 轴的 `rms.*`，而数据面里不存在该端口）。
    两个独立盲审模型各自复现了这个冲突。

    修正要点：**两条轴描述的是「哪条时间网格」，不是「什么物理量」。**
    同一个物理量（如练习的 PCM、练习的能量）在两套网格上**各有一份端口**，
    这才是 SPEC §5.5 说的"同时提供两种表示"。

    命名也一并澄清（第一版的名字暗示"参考侧/练习侧"，是误导）：
        REFERENCE 网格 = **源时间网格**，以参考演奏的时钟为刻度
        WARPED    网格 = **归一化网格**，把练习拉伸到与参考等长
    """

    REFERENCE = "REFERENCE"
    """**源时间网格**：以参考演奏的时钟为刻度，保留原始时间关系。

    练习侧的音在**参考时钟**上的位置 = 它实际被吹出的时刻。
    因此「练习比参考早/晚多少」在这条网格上**可见** —— 抢拍拖拍在此。

    关键性质：**距离与时刻都有绝对意义。**
    第 10 秒就是第 10 秒，音与音之间的间隔是真实间隔。

    → 节奏类指标必须在它上面算（SPEC §5.5 的强制）。
    → **不要**把它读成"参考演奏专属的轴"：练习侧的 `pcm.mapped.practice`
      和 `rms.practice` 也在它上面，它们描述的是**练习在参考时钟上的样子**。
    """

    WARPED = "WARPED"
    """**归一化网格**：把练习线性/非线性拉伸到与参考等长后的网格。

    练习的第 n 个音被搬到参考第 n 个音的位置上。
    于是「练习比参考早/晚多少」在这条网格上**不存在** —— 它已被抹掉。

    关键性质：**只有"第几个音"有意义，绝对时刻没有意义。**
    第 10 秒在这里只是一个位置标记，不代表真实时间。

    → **适合**音准、力度这类"关心吹了什么、不关心何时吹"的比较。
    → **禁止**拿它报节奏错误（那是构造性错误，结果恒为 0 且不报错）。
    → **不要**以为它只存在于练习侧：任何"想按音对齐比较"的物理量，
      都可以在它上面再放一份端口（见下方 WAIT-AND-SEE）。
    """


class AlignmentRepresentation(str, Enum):
    """数据面**始终**包含的两份对齐 PCM（本仓自定保证；★ 原写"宪章 §11 逃生口"是伪造引用）。

    因为它们永远存在，任何算法都能拿 PCM 自行做特有预处理。
    """

    MAPPED = "MAPPED"
    """保留源时间（对齐后落在参考时间轴上）。"""

    WARPED = "WARPED"
    """时间归一化（与参考等长）。"""


@dataclass(frozen=True)
class AudioFormat:
    """C2 标准化之后的统一格式。全局唯一，所有端口继承它。"""

    sample_rate: int
    """Hz。**必须记录**：实测同一段音频在 22.05 kHz 下 f0 会被判低八度
    （−1200 音分），44.1 kHz 下正常。采样率是**结果的成因**，不是元数据。"""

    channels: int
    """恒为 1。多声道在 ingest 阶段已下混。"""

    dtype: str
    """numpy dtype 名称，恒为 'float32'。"""

    def __post_init__(self) -> None:
        if self.channels != 1:
            raise ValueError("契约要求 mono")
        if self.dtype != "float32":
            raise ValueError("契约要求 float32")


# ═════════════════════════════════════════════════════════════════════
# 二 · 数据面（CONTRACT-ALGORITHM-DATA-v1）
# ═════════════════════════════════════════════════════════════════════

FIELD_LAYOUTS: Mapping[str, tuple[str, ...]] = {
    "warp_path": ("reference_frame", "practice_frame"),
    "pitch": ("f0_hz", "voiced", "confidence"),
    "notes": ("onset_sec", "f0_hz", "rms"),
    "chroma": (
        "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
    ),
}
"""多维度端口的**字段顺序定义**。★ 盲审发现的缺口，已补。

为什么必须有这张表：`dimensions=('frame','field')` 只说了"第二维是字段"，
**没说字段是什么、什么顺序**。没有它，两个实现者会写出不同的内存布局，
读出来的 `f0_hz` 可能是 `voiced`——而且**不会报错**，只会静默算错。

键取 port_id 的**类别前缀**（第一个 `.` 之前的部分）：
    'warp_path' → ('reference_frame', 'practice_frame')
    'pitch.*'   → ('f0_hz', 'voiced', 'confidence')
    'notes.*'   → ('onset_sec', 'f0_hz', 'rms')
    'chroma.*'  → 12 个音级，**从 C 开始**（不是从 A）

chroma 的音级起点同样有歧义（bin 0 是 C 还是 A？），故一并冻结：
**bin 0 = C**，依次半音上行。

`profile.assert_profile_integrity()` 会检查：凡 `len(dimensions) > 1`
的端口，其前缀必须在这张表里，且字段数必须等于 `len(field_names)`。

★ G6 修正（§20 盲审发现）：原文写的是「字段数必须等于 `dimensions[-1]` 声明的
大小」——**这句话按字面无法实现**，因为 `dimensions` 里放的是**语义名字符串**
（`'frame'` / `'bin'` / `'field'`），**不含尺寸**。真正的尺寸在
`PortDescriptor.shape` 里，而那要到运行期才填。
故校验对象改为 `len(field_names)`（profile 侧可静态检查）。
"""


CONTENT_HASH_MAGIC: bytes = b"harmonica-eval/surface/v1\x00"
"""`content_hash` 的域分隔前缀（G12）。

作用：让本 hash 的输入空间与任何其他用途的 sha256 **不重叠**。
若将来有人复用同一个 sha256 做别的事（例如文件校验），
前缀保证两者不会算出相同结果而被误认为等价。
末尾的 `\\x00` 是长度分隔：防止 `"a" + "bc"` 与 `"ab" + "c"` 碰撞。
"""


UNITS_VOCABULARY: frozenset[str] = frozenset({    "amplitude",
    "chroma",
    "hz",
    "index",
    "rms",
    "cents",
    "seconds",
    "db",
})
"""端口的合法 `units` 取值（G10 修正）。

为什么需要受控词表：`units` 是给算法判断"这个端口是不是我要的量"用的。
开放式字符串意味着两个实现者可以写出 `"hz"` / `"Hz"` / `"hertz"` 三种，
而下游按 `== "hz"` 判断时会静默不匹配。

当前实际使用：
    amplitude  pcm.mapped.* / pcm.warped.*
    chroma     chroma.lowres.*      ← 第一版的举例里没有它，故补入
    hz         pitch.*
    index      warp_path / notes.*
    rms        rms.*

预留但当前未用：`cents`（音分，来自算法 payload）、`db`（同上）、
`seconds`（时刻，来自 payload）。
**预留项必须由某个未来的 profile 真正使用，否则应删** ——
本词表不收集"以后可能有用"的值。"""


@dataclass(frozen=True)
class PortDescriptor:
    """一个端口的自描述头。算法仅凭它即可决定是否可用。

    **端口清单是封闭的**（写死在 profile.py），不随算法需求增长。

    多维度端口的字段顺序见 `FIELD_LAYOUTS`——算法**必须**用它来解释第二维，
    不得自行假定顺序。
    """

    port_id: str
    """稳定标识，如 'pcm.mapped.reference'。Seal 后不可变。"""

    schema_version: str
    element_type: str
    """numpy dtype 名称，如 'float32' / 'int32'。"""

    dimensions: Sequence[str]
    """维度语义名，如 ('sample',) / ('frame',) / ('frame', 'field')。"""

    shape: Sequence[int]
    units: str
    """物理单位。★ 取值见 `UNITS_VOCABULARY`（受控词表，G10 修正）。

    第一版这里是开放式举例（`'amplitude' / 'hz' / 'rms' / 'cents' /
    'seconds' / 'index' …`），带省略号 —— 而 profile 实际用了 `'chroma'`，
    **不在举例里**。算法若按 `units` 判断端口语义，会因举例不全而误判。
    现改为受控词表，且由 `assert_profile_integrity()` 检查取值合法。
    """

    field_names: Sequence[str] = ()
    """第二维的字段名，顺序即内存布局顺序。

    单维端口为空元组。多维度端口**必须**填，且必须与
    `FIELD_LAYOUTS[类别前缀]` 完全一致 —— 这是防止静默错位的唯一手段。
    """

    timeline_basis: TimelineBasis = TimelineBasis.REFERENCE
    """**必填语义**。忘记声明会导致节奏指标算错（见 TimelineBasis）。"""

    hop_length: int = 0
    """★ 该端口的**帧移**（采样点）。帧类端口必填，非帧类为 0。

    G5 修正（§20 盲审发现）：`read(port_id, time_range)` 的 `time_range`
    单位是**秒**，而帧类端口的第二维是**帧**。秒→帧的换算必须唯一，
    否则两个实现者会算出不同时刻的数据 —— **且不会报错**。

    第一版 `PortDescriptor` 没有这个字段，而 `profile` 里
    `pitch.*` / `chroma.*` 的帧移也**根本没有声明**：
    `ALIGN.hop_length`(=2048) 是齐套的 chroma 帧移，
    `MATERIALIZE.rms_hop_length`(=256) 是 RMS 的帧移，
    两者相差 8×，实现者猜哪个都不报错。

    与 `field_names` 同理：**这是防止静默算错的唯一手段**，
    必须由 profile 声明并由 `assert_profile_integrity()` 检查。
    """

    sample_rate: int = 0
    """**必填语义**。采样率是算法结果的成因，不是元数据。
    0 表示该端口与采样率无关（如 chroma / index 类）。"""

    content_hash: str = ""
    """Seal 时计算的内容指纹。★ 算法已冻结（G12 修正）。

    第一版只说"内容指纹"，未定哈希函数与输入字节序列 ——
    于是跨实现的 `content_hash` **不可比**，而它的用途恰恰是
    「同一对输入 + 同一 profile_version ⇒ hash 一致」这条回归断言。

    冻结算法（实现必须逐字节照做）：

        h = hashlib.sha256()
        h.update(CONTENT_HASH_MAGIC)          # 域分隔，防跨用途复用
        h.update(port_id.encode("utf-8"))
        h.update(element_type.encode("utf-8"))
        h.update(np.asarray(shape, dtype="<i8").tobytes())   # 小端
        h.update(data.tobytes(order="C"))     # C 序，原始 dtype
        content_hash = h.hexdigest()

    三条必须遵守的性质：
        1. **包含 shape 与 dtype** —— 否则 (2,3) 与 (3,2) 同 hash
        2. **固定字节序**（小端）—— 否则跨架构不可比
        3. **C 序展平** —— 否则同数据的非连续视图会算出不同 hash

    注意：本 hash 用于**同一实现内的回归**与**跨实现的对照**，
    **不**用于安全用途（不是抗碰撞承诺）。
    """


@dataclass(frozen=True)
class BufferView:
    """对某端口的只读借用视图。

    所有权始终属于 C2。借用方**不得**修改、**不得**释放、
    **不得**跨会话持有。实现层必须把 writeable 置为 False。
    """

    data: npt.NDArray[Any] = field(repr=False)
    element_count: int
    element_type: str


@dataclass(frozen=True)
class SurfaceManifest:
    """数据面的自描述清单。

    外部通过它枚举端口，**无需预知端口清单**——
    这是「深组件」的关键：C2 内部可重组而不破坏外部。
    """

    profile_version: str
    audio_format: AudioFormat
    reference_duration_sec: float
    practice_duration_sec: float
    ports: Mapping[str, PortDescriptor]
    sealed: bool
    """Seal 后为 True；False 时**不得**交给算法。"""


@dataclass(frozen=True)
class AlgorithmResultEnvelope:
    """算法的标准回执。

    算法失败也**必须**返回信封（而非抛异常穿透），以便 C1 隔离故障。
    """

    algorithm_id: str
    algorithm_version: str
    status: str
    """'OK' | 'FAILED' | 'INCOMPATIBLE'。"""

    required_ports: Sequence[str]
    """算法声明需要的端口。仅用于兼容性检查（单向）。"""

    consumed_ports: Sequence[str]
    """本次**实际读取**的端口。仅用于证据与追溯，
    **绝不**反向触发 C2 生成数据。"""

    payload: Mapping[str, Any]
    """结果本体。形状由算法自己声明，C1 不解释其内部。"""

    error_code: str | None = None
    error_detail: str | None = None
    elapsed_sec: float | None = None


class AlgorithmDataContract(Protocol):
    """C3 → 数据面：**只有两个纯查表操作**。

    实现者：C2 产出的 Surface。
    调用者：C3 各算法。

    **read() 无副作用**：不触发计算、不会失败于「算不出来」。
    Seal 时数据面里已有算法要的一切——这是负责人的架构裁定。
    """

    def manifest(self) -> SurfaceManifest:
        """返回自描述清单，用于枚举端口并判断兼容性。"""
        ...

    def read(
        self,
        port_id: str,
        time_range: tuple[float, float] | None = None,
    ) -> BufferView:
        """按键读取一个端口的（可选时间窗）只读视图。

        **单位是秒**（不是帧、不是采样点）。坐标含义由该端口的
        `timeline_basis` 决定：
            REFERENCE → 秒，相对参考演奏起点
            WARPED    → 秒，相对时间归一化后的起点

        `time_range=(t0, t1)`，左闭右开 `[t0, t1)`。
        `None` ⇒ 整段。

        与帧坐标的换算由**实现**负责，调用方不得自行乘除 hop
        （那会让调用方依赖 profile 的内部参数）。
        换算依据是该端口自己的 `hop_length`（见 `PortDescriptor.hop_length`）——
        **不是** `profile.ALIGN.hop_length`，后者只是 chroma 端口的帧移。

        ★ G16 修正（§20 盲审发现）：**非帧类端口的时间窗语义**。

        `warp_path` 的 `units="index"`、`dimensions=("warp_point","axis")`
        —— 它**没有** frame 维度，却声明了 `timeline_basis=REFERENCE`。
        第一版没说对它调 `read(port_id, (t0,t1))` 时秒该怎么换算
        （用哪个 hop？warp_point 不是帧）。审查者指出这是"最尖锐"的缺口。

        冻结语义：`time_range` **对所有端口统一以秒为单位**，
        换算规则按端口的 `units` 决定：

            units == "amplitude"  → 秒 × sample_rate            → 采样点
            dimensions 含 "frame"  → 秒 × sample_rate / hop_length → 帧
            units == "index"      → 秒 × sample_rate / hop_length → 索引
                                    （notes.* 用 hop_length=0，
                                      故按 **onset_sec 字段**筛选，见下）
            units == "chroma"     → 同 frame 规则

        `notes.*` 特殊：它是**逐音**表（不是等间隔栅格），
        故 `time_range` 按 `field_names` 中的 `onset_sec` **筛选行**：
        返回 onset_sec ∈ [t0, t1) 的音。这也正是 `hop_length=0` 的含义 ——
        "本端口不是等间隔栅格，不要用帧移换算"。

        `warp_path` 特殊：它是**路径点**表，时间窗按
        `reference_frame` 换算后的秒值筛选（因为它的 basis 是 REFERENCE）。
        注意其 `unit="index"` 指的是**列语义**（帧号），不是时间单位。

        失败语义（**必须严格区分，不得混淆**）：
        - 端口不存在 → 抛 `ContractViolation`
        - `t0 >= t1`，或 `t1` 超出该端口时长 → 抛 `ContractViolation`
        - **绝不返回空视图冒充成功**（宪章 §5.6 No Silent Degradation）
          ★ 例外：若时间窗**合法**但窗内确实无数据（如 `notes.*` 在
          一段静音里没有任何 onset），返回**空视图是正确的**，
          不是静默降级 —— 因为"窗内没有音"是真实答案。
          判据：`t1` 在时长内 ⇒ 空是合法结果；`t1` 超时长 ⇒ 抛错。

        返回值保证：
        - `data.flags.writeable is False`
        - `data.ndim == len(descriptor.dimensions)`
        - `element_count == product(data.shape)`
        """
        ...


CORE_REQUIRED_PORTS: tuple[str, ...] = (
    "pcm.mapped.reference",
    "pcm.mapped.practice",
)
"""任何 profile 都**必须**包含的端口（本仓自定保证；原引"宪章 §11"为伪造）。

其余端口可以随 profile 版本变化，但这两份对齐 PCM 永远存在：
它们保证算法永远能自行做特有预处理，从而 profile 只决定「快不快」，
不决定「能不能」。
"""


# ═════════════════════════════════════════════════════════════════════
# 三 · CONTRACT-HOST-v1（C1 → C2）
# ═════════════════════════════════════════════════════════════════════

class HostContract(Protocol):
    """C1 → C2 的全部对话能力：**7 个操作，不多不少**。

    实现者：COMP-C2 Audio Core。
    调用者：COMP-C1 Framework / Host。
    """

    def create_session(self, profile_version: str) -> str:
        """创建分析会话，返回 session_id。

        profile_version 必须显式传入——没有它，「同一对输入」不成立
        （数据面内容是 (reference, practice, profile_version) 的函数）。
        """
        ...

    def set_reference(self, session_id: str, uri: str) -> None:
        """登记参考演奏。**不触发**解码或计算。

        ★ G8 修正（§20 盲审发现）：本方法第一版签名是 `set_reference(uri)`，
        **没有 session_id** —— 而同一个协议里 `build_surface` / `status` /
        `acquire_surface` / `destroy_session` **都**要求 session_id。

        这是契约内部不自洽：会话句柄既然由 `create_session` 返回、
        又必须传给其他 5 个操作，唯独两个 setter 不用它，
        实现者无法判断该往哪个会话登记（多会话时直接歧义；
        单会话时又要额外约定"当前会话"这个隐含状态）。

        修正为显式传 `session_id`：**所有会话级操作都必须显式定位会话**，
        不引入"当前会话"这种隐含状态（隐含状态是并发缺陷的温床，
        且与 `create_session` 返回 id 的设计自相矛盾）。

        合法状态：CREATED / INPUT_READY
        两段都登记后 → INPUT_READY
        """
        ...

    def set_practice(self, session_id: str, uri: str) -> None:
        """登记学习者演奏。**不触发**解码或计算。

        G8 修正：同上，补上 `session_id`。

        合法状态：CREATED / INPUT_READY
        两段都登记后 → INPUT_READY
        """
        ...

    def build_surface(self, session_id: str) -> None:
        """**一次性预生成**全部端口并 Seal。

        前置：两段资产均已登记（状态 == INPUT_READY）。
        后置：状态 == DATA_READY，数据面不可变。
        失败：抛 CoreBuildError，状态 → FAILED，**不得部分发布**，
              资源全部释放，且**未触发任何算法**。

        注意：本操作**不接收任何算法信息**。它不知道谁会来读。
        """
        ...

    def status(self, session_id: str) -> SessionState:
        """返回会话状态。

        **只返回 SessionState 的六个值之一**；C2 内部阶段
        （INGESTING / ALIGNING / BUILDING_PORTS / …）不得外泄。
        """
        ...

    def acquire_surface(self, session_id: str) -> AlgorithmDataContract:
        """取得数据面的只读句柄。

        前置：状态 == DATA_READY，否则抛 ContractViolation。
        所有权：句柄有效期至 destroy_session。
        """
        ...

    def destroy_session(self, session_id: str) -> None:
        """销毁会话并释放全部资源。

        之后使用旧句柄的任何行为都是 ContractViolation。
        """
        ...


FORBIDDEN_OPERATIONS: tuple[str, ...] = (
    "align",
    "fft",
    "stft",
    "compute_feature",
    "generate_pitch_input",
    "generate_plugin_requirement",
    "prepare_for_pitch",
    "prepare_for_timing",
    "register_algorithm",
    "list_algorithms",
)
"""CONTRACT-HOST-v1 上**绝不允许**出现的方法名。

判据：若 C1 需要调用其中任何一个，说明编排权或算法知识泄漏进了 Core。
违反宪章 §5.9（Every Agent Knows Its Place）与 §47.6（Silent Contract Mutation）。
这份名单可直接被 Inspector General 用作断言。
"""


# ═════════════════════════════════════════════════════════════════════
# 四 · 错误码与异常
# ═════════════════════════════════════════════════════════════════════

class ErrorCode(str, Enum):
    """全部失败原因。新增必须同步 COMPONENTS.md §7 失败语义表。"""

    INPUT_UNREADABLE = "INPUT_UNREADABLE"
    """归属 C2。不可读/权限拒绝/不可解码。数据面不存在，算法不启动。"""

    INPUT_TOO_SHORT = "INPUT_TOO_SHORT"
    """归属 C2。短于最小可分析长度。数据面不存在。"""

    INPUT_SILENT = "INPUT_SILENT"
    """归属 C2。整段静音，无法建立任何有效映射。数据面不存在。"""

    INPUT_TOO_LONG = "INPUT_TOO_LONG"
    """归属 C2。长于 profile.AUDIO.max_duration_sec（规格上限 120 s）。

    ★ 这是我在写 ingest.py 时发现的自身缺口：原契约只有 TOO_SHORT，
    没有 TOO_LONG，但规格明确有上限。缺它的后果是超长音频只能被
    勉强归类为「不可读」，掩盖真实原因。

    处理方式同样是**拒绝，不静默截断** —— 静默截断会让分析结果
    对应到一个用户不知道的时间范围。"""

    CORE_BUILD_FAILED = "CORE_BUILD_FAILED"
    """归属 C2。标准化/对齐/预生成任一步失败。
    **不得部分发布**，全部资源释放。"""

    ALIGNMENT_UNRECOVERABLE = "ALIGNMENT_UNRECOVERABLE"
    """归属 C2。无法建立有效时间映射。
    **禁止**静默退化为「逐点硬比」（宪章 §5.6 No Silent Degradation）。"""

    PLUGIN_INCOMPATIBLE = "PLUGIN_INCOMPATIBLE"
    """归属 C1 判定。算法声明了数据面没有的端口。
    数据面仍有效，其他算法不受影响。"""

    ALGORITHM_FAILED = "ALGORITHM_FAILED"
    """归属 C3。算法崩溃/NaN/非法结果。数据面仍有效。"""

    ALGORITHM_RESULT_INVALID = "ALGORITHM_RESULT_INVALID"
    """归属 C1（校验）。结果不符合其声明的 schema。"""

    ALGORITHM_TIMEOUT = "ALGORITHM_TIMEOUT"
    """归属 C1。**v0.1 未实现**（已知缺口：死循环会卡住流程）。"""

    COCKPIT_DETACHED = "COCKPIT_DETACHED"
    """归属 C4。界面断开不影响会话。★ G14 修正（§20 盲审发现）。

    第一版定义了这个码，但**没有任何地方能产生它** ——
    `UiProjectionPort` 只有 `snapshot` / `submit` 两个操作，
    没有上报通道；C1 也不检测界面存活。审查者原话：
    「该码目前无处产生」。

    这是**已删除的功能残留**，不是待实现的接口。故：

    ★ **v0.1 不会产生此码。** 保留它是因为删除会让
    `ErrorCode` 的编号在文档/报表里发生偏移（已发出的证据包会失效）。

    v0.1 对"界面断开"的实际处理（见 MT-007）：
        界面断开 = C4 进程消失 → C1 **什么都不做**，会话继续。
        这本来就是正确的行为（不变量 F：C4 可缺席），
        **不需要**一个错误码来记录它 —— 没有人在监听这个码。

    若将来确实要记录界面事件，正确做法是新增一个**事件通道**，
    而不是复用 `ErrorCode`（断开不是错误，塞进错误码会污染失败统计）。
    """

    INTERNAL_ERROR = "INTERNAL_ERROR"
    """兜底。出现即表示有未分类失败路径，应视为缺陷。"""


@dataclass
class HarmonicaError(Exception):
    """全部受控失败的基类。携带结构化上下文，便于 C1 归一化上报。"""

    code: ErrorCode
    detail: str = ""
    session_id: str | None = None
    port_id: str | None = None
    component: str | None = None

    def __str__(self) -> str:  # pragma: no cover - 展示用
        parts = [f"[{self.code.value}]"]
        if self.component:
            parts.append(f"({self.component})")
        parts.append(self.detail or "no detail")
        if self.session_id:
            parts.append(f"session={self.session_id}")
        if self.port_id:
            parts.append(f"port={self.port_id}")
        return " ".join(parts)


class ContractViolation(HarmonicaError):
    """调用方违反契约（Seal 前取数据面、读不存在的端口、写只读缓冲）。

    这是**程序缺陷**，不是环境问题；不应被重试逻辑吞掉。
    """


class CoreBuildError(HarmonicaError):
    """C2 构建期失败。数据面不存在，算法不得启动。"""


class AlgorithmError(HarmonicaError):
    """C3 运行期失败。数据面与其余算法不受影响。"""


# ═════════════════════════════════════════════════════════════════════
# 五 · CONTRACT-UI-v1（C1 ↔ C4）
# ═════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class UiScalar:
    """一个可展示的标量指标。

    **只陈述数值与含义，不下教学结论**（SPEC §3）。
    """

    key: str
    label: str
    """给人看的短名，中文。"""
    value: float
    unit: str
    """'cents' / 'ms' / 'db' / 'ratio' / ''。"""
    threshold: float | None = None
    """可选参考阈值。None 表示纯陈述、无判定。"""


@dataclass(frozen=True)
class UiSeries:
    """一条可绘制的曲线。**必须已下采样**。"""

    key: str
    label: str
    t: Sequence[float] = field(repr=False)
    """时间轴（秒）。长度与 values 相同。"""
    values: Sequence[float] = field(repr=False)
    unit: str
    timeline_basis: TimelineBasis
    """**必填**：节奏类展示必须用 REFERENCE，否则会误导。

    ★ C4 盲审发现的歧义，已裁定：**禁止把不同 timeline_basis 的曲线
    画在同一张图上。** 两条轴的 t 物理含义不同（一条保留源时间、
    一条已归一化），叠在一起必然误导 —— 尤其会让抢拍拖拍看起来"对齐了"。

    同一 basis 的多条曲线可以叠加（如参考与练习都在 REFERENCE 上）。
    """
    source_port: str | None = None
    """源自哪个端口（便于调试追溯）。None 表示由算法直接产出。"""


@dataclass(frozen=True)
class UiView:
    """C1 交给 C4 的完整只读投影。

    C4 只允许依赖本对象；不得反向访问 C1/C2/C3 内部。
    """

    session_id: str
    state: SessionState
    series: Sequence[UiSeries] = ()
    scalars: Sequence[UiScalar] = ()
    progress: float | None = None
    """构建进度。★ C4 盲审发现的歧义，已冻结取值域；
    ★ G9 修正（§20 盲审发现）补上了**产生机制**。

    **取值域是 0.0–1.0（比例，不是百分数）。**
        0.0      已完成 0%
        1.0      已完成 100%（与 state == DATA_READY 一致）
        None     该会话**没有进度概念**（尚未开始，或已进入终态）

    **界面不得自行归一化、不得推断百分比** —— 它只负责显示这个数。

    ── 产生机制（G9：第一版只有取值域，没有产生规则）──

    盲审指出：「`progress` 取值域冻结了，但 C2 的 `status()` 只回 6 个
    `SessionState`，内部阶段 `INTERNAL_STAGES` 明确禁止外泄 →
    C1 拿不到任何中间进度源」。属实。

    这里是**刻意**的取舍，不是遗漏：

        C1 能计数的是**它自己编排的步骤**，不是 Core 的内部阶段。
        `build_surface` 是**一次**同步阻塞调用 —— 在它内部，
        Core 会 ingest → align → features → surface 四个阶段，
        但这四个阶段名**禁止外泄**（泄漏它们会让 C1 开始依赖
        Core 的内部实现，深组件随即瓦解，见 core/api.py 的 status()）。

    故 `progress` 的定义是 **"C1 已完成的正交步骤数 / 总步骤数"**：

        BUILD_SURFACE 期间    → 0.0 → 1.0 的**单次跳变**（或 None）
                                没有中间值，因为那需要 Core 汇报内部阶段
        RUN_ALGORITHMS 期间   → k / 3（k = 已完成算法数，按 registry 顺序）

    一个"平滑的构建进度条"需要 Core 开放内部阶段 —— 那是**契约变更**，
    会让 `CONTRACT-HOST-v1` 从 7 个操作变成 8 个（加一个进度查询），
    直接违反负责人裁定的**封闭端口/封闭契约**原则。

    **本轮（快速原型验证）不做这件事。** 宁可 progress 粗粒度、
    也不为了一个进度条破坏深组件边界。

    ★ 记入已知缺口：若将来确实需要平滑进度，
    正确做法**不是**让 Core 汇报内部阶段，而是在 C1 里把构建拆成
    可观测的多次调用（那同样需要契约变更，须由负责人裁定）。"""

    error_code: str | None = None
    error_detail: str | None = None
    note: str = ""
    """给开发者的一句话说明（例如「数据面已 Seal，可运行算法」）。"""


class UiCommandKind(str, Enum):
    """界面能表达的**全部**意图。

    刻意保持极小：C4 **不能凭界面发明内核能力**。
    """

    SET_REFERENCE = "SET_REFERENCE"
    SET_PRACTICE = "SET_PRACTICE"
    BUILD_SURFACE = "BUILD_SURFACE"
    RUN_ALGORITHMS = "RUN_ALGORITHMS"
    CANCEL = "CANCEL"
    RESET = "RESET"


COMMAND_LEGALITY: Mapping[UiCommandKind, frozenset[SessionState]] = {
    UiCommandKind.SET_REFERENCE: frozenset(
        {SessionState.CREATED, SessionState.INPUT_READY}
    ),
    UiCommandKind.SET_PRACTICE: frozenset(
        {SessionState.CREATED, SessionState.INPUT_READY}
    ),
    UiCommandKind.BUILD_SURFACE: frozenset({SessionState.INPUT_READY}),
    UiCommandKind.RUN_ALGORITHMS: frozenset({SessionState.DATA_READY}),
    UiCommandKind.CANCEL: frozenset(
        {SessionState.INPUT_READY, SessionState.BUILDING, SessionState.DATA_READY}
    ),
    UiCommandKind.RESET: frozenset(set(SessionState)),
}
"""状态 × 命令的合法性矩阵。★ C4 盲审发现的缺口，已补。

在此之前这张表只存在于 C1 的 `downstream.md` 里，**契约中没有** ——
于是 C4 无法判断哪些按钮该置灰，只能一律可点、等 C1 拒绝。

现在两侧对「什么状态下能做什么」有**同一个事实来源**：
    - C1 **必须**用它校验（非法命令 → 拒绝，且**不改变状态**）
    - C4 **可以**用它置灰按钮（纯 UI 优化，**不是**安全边界）

**即使 C4 不置灰，C1 也必须校验** —— 界面不是可信输入源。
"""


COMMAND_EFFECTS: Mapping[UiCommandKind, str] = {
    UiCommandKind.SET_REFERENCE: "登记参考演奏路径；成功 → INPUT_READY",
    UiCommandKind.SET_PRACTICE: "登记练习演奏路径；成功 → INPUT_READY",
    UiCommandKind.BUILD_SURFACE: "开始构建数据面；进入 BUILDING，成功 → DATA_READY",
    UiCommandKind.RUN_ALGORITHMS: "运行全部已注册算法；**状态不变**（仍在 DATA_READY）",
    UiCommandKind.CANCEL: "中止进行中的操作 → **回到操作前的稳定态**",
    UiCommandKind.RESET: "丢弃数据面与已登记输入 → **CREATED**，会话本身保留",
}
"""每条命令的**状态效果**。★ G11 修正（§20 盲审发现）。

第一版只冻结了"什么状态下**可以**发这条命令"（`COMMAND_LEGALITY`），
**没说发完之后状态变成什么**。审查者指出 CANCEL / RESET 的语义"零定义"：

    - CANCEL 后状态去哪？（BUILDING 中取消 → 回 INPUT_READY 还是 FAILED？）
    - 已 Seal 的数据面在 CANCEL 后是否销毁？
    - RESET 重置到哪个状态？是否保留已登记的输入 URI？

这些不定义，两个实现者会写出行为不同的会话机，而**界面看起来都正常**。

冻结语义如下（`CANCEL` 的关键性质：**回到操作前的稳定态**）：

    CANCEL 在 INPUT_READY  → 无进行中操作，状态不变（幂等）
    CANCEL 在 BUILDING     → 中止构建，**销毁未完成的数据面**，回 INPUT_READY
    CANCEL 在 DATA_READY   → 只中止正在运行的算法，**数据面保持有效**，
                             回 DATA_READY（已 Seal 的数据面不因取消而销毁）

    RESET 在任意状态       → 销毁数据面、清空已登记输入，回 CREATED
                             （会话对象本身保留，可继续登记新输入）

★ 关于 `BUILDING` 期间的取消：`build_surface` 是**同步阻塞**调用，
中途没有天然中断点。契约**要求**实现者提供检查点 ——
至少在每个端口物化完成时检查一次取消标志。
**不得**用"构建太快所以不用管"来回避（120 s 音频的构建是可感知的）。

★ `CANCEL` 与 `RESET` 都**不是错误**：不得产生 `ErrorCode`，
新状态不是 `FAILED`。用户主动中止 ≠ 系统失败。
"""


@dataclass(frozen=True)
class UiCommand:
    """一条用户意图。C1 是唯一执行者与校验者。

    合法性见 `COMMAND_LEGALITY`。非法命令必须被**拒绝且不改变状态**
    （不许"尽力而为"）。
    """

    kind: UiCommandKind
    payload: dict = field(default_factory=dict)
    """★ 载荷。键名已冻结（G7 修正，§20 盲审发现）。

    第一版只有 `payload: dict`，没有任何键名定义 ——
    于是 C4 构造命令与 C1 消费命令必须**各自猜**同一个键名，
    猜错则无头链路在第一次命令下发时断掉，且契约里无处校验。
    （审查者原话：「这是缺口 1，端到端直接断」。）

    冻结的键名（**唯一权威，即本表**）：

        SET_REFERENCE   {"path": str}   绝对路径，音频文件
        SET_PRACTICE    {"path": str}   绝对路径，音频文件
        BUILD_SURFACE   {}              无载荷
        RUN_ALGORITHMS  {}              无载荷（运行全部已注册算法）
        CANCEL          {}              无载荷
        RESET           {}              无载荷

    规则：
        - 键名**不得**增删。需要新载荷时改契约并升 `CONTRACT-UI-v1` 版本。
        - 未列出的 `kind` 用空 dict。
        - C1 **必须**校验：未知键、缺必需键、值类型不符 → 拒绝命令
          （拒绝而非忽略：忽略会让 C4 以为命令生效了）。
    """


UI_PAYLOAD_KEYS: Mapping[UiCommandKind, tuple[str, ...]] = {
    UiCommandKind.SET_REFERENCE: ("path",),
    UiCommandKind.SET_PRACTICE: ("path",),
    UiCommandKind.BUILD_SURFACE: (),
    UiCommandKind.RUN_ALGORITHMS: (),
    UiCommandKind.CANCEL: (),
    UiCommandKind.RESET: (),
}
"""★ `UiCommand.payload` 的键名冻结表（G7）。

与 `FIELD_LAYOUTS` 同一个教训：`dict` 类型本身不携带任何键名信息，
产出方与消费方之间必须有**共同事实来源**，否则静默错位。

    - C4 构造命令时**必须**用这里的键名
    - C1 校验命令时**必须**比对本表（缺失/多余/类型不符 → 拒绝）"""


class UiProjectionPort(Protocol):
    """C1 对 C4 提供的唯一入口：**只有两个操作**。

    与数据面契约同为「接口极小」的设计。
    """

    def snapshot(self) -> UiView:
        """取当前投影快照。**纯读取，无副作用**。"""
        ...

    def submit(self, command: UiCommand) -> None:
        """下发一条用户意图。由 C1 校验并执行。"""
        ...


__all__ = [
    # 会话与时间
    "SessionState", "TimelineBasis", "AlignmentRepresentation", "AudioFormat",
    # 数据面
    "PortDescriptor", "BufferView", "SurfaceManifest", "AlgorithmResultEnvelope",
    "FIELD_LAYOUTS",
    "AlgorithmDataContract", "CORE_REQUIRED_PORTS",
    # Host
    "HostContract", "FORBIDDEN_OPERATIONS",
    # 错误
    "ErrorCode", "HarmonicaError", "ContractViolation", "CoreBuildError", "AlgorithmError",
    # UI
    "UiScalar", "UiSeries", "UiView", "UiCommand", "UiCommandKind", "UiProjectionPort",
    "COMMAND_LEGALITY",
    "COMMAND_EFFECTS",
    "UI_PAYLOAD_KEYS",
    "CONTENT_HASH_MAGIC",
    "UNITS_VOCABULARY",
]
