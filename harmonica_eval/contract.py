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

    依据 SPEC.md §5.5「两轴分离」。
    """

    REFERENCE = "REFERENCE"
    """保留源时间。对齐后重采样到**参考演奏**的时间轴。
    抢拍拖拍在此轴上**可见**。→ 节奏类指标必须用它。"""

    WARPED = "WARPED"
    """时间归一化。练习被拉伸到与参考等长。
    抢拍拖拍在此轴上**被抹掉**。→ 拿它报节奏错误是构造性错误。"""


class AlignmentRepresentation(str, Enum):
    """数据面**始终**包含的两份对齐 PCM（宪章 §11 逃生口）。

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
的端口，其前缀必须在这张表里，且字段数必须等于 `dimensions[-1]` 声明的大小。
"""


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
    """'amplitude' / 'hz' / 'rms' / 'cents' / 'seconds' / 'index' …"""

    field_names: Sequence[str] = ()
    """第二维的字段名，顺序即内存布局顺序。

    单维端口为空元组。多维度端口**必须**填，且必须与
    `FIELD_LAYOUTS[类别前缀]` 完全一致 —— 这是防止静默错位的唯一手段。
    """

    timeline_basis: TimelineBasis = TimelineBasis.REFERENCE
    """**必填语义**。忘记声明会导致节奏指标算错（见 TimelineBasis）。"""

    sample_rate: int = 0
    """**必填语义**。采样率是算法结果的成因，不是元数据。
    0 表示该端口与采样率无关（如 chroma / index 类）。"""

    content_hash: str = ""
    """Seal 时计算的内容指纹，用于同 build 回归断言。"""


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

        失败语义（**必须严格区分，不得混淆**）：
        - 端口不存在 → 抛 `ContractViolation`
        - `t0 >= t1`，或 `t1` 超出该端口时长 → 抛 `ContractViolation`
        - **绝不返回空视图冒充成功**（宪章 §5.6 No Silent Degradation）

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
"""任何 profile 都**必须**包含的端口（宪章 §11 逃生口）。

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

    def set_reference(self, uri: str) -> None:
        """登记参考演奏。**不触发**解码或计算。"""
        ...

    def set_practice(self, uri: str) -> None:
        """登记学习者演奏。**不触发**解码或计算。"""
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
    """归属 C4。界面断开不影响会话，仅记录。"""

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
    """**必填**：节奏类展示必须用 REFERENCE，否则会误导。"""
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


@dataclass(frozen=True)
class UiCommand:
    """一条用户意图。C1 是唯一执行者与校验者。"""

    kind: UiCommandKind
    payload: dict = field(default_factory=dict)


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
]
