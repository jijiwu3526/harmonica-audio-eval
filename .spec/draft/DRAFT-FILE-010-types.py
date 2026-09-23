'''
FILE-ID: FILE-010
COMPONENT: COMP-CONTRACT（跨组件契约层，不属于任何单一组件）
SPEC: SPEC.md@v2.1 · COMPONENTS.md@v2 §4

ROLE:
    跨组件共享的数据类型与枚举。纯声明，无行为。

INTENT:
    让 C1/C2/C3/C4 对「状态、时间基准、端口、结果」使用同一套词汇，
    从结构上消除宪章 §21 Cross-Agent Semantic Variance。

MUST:
    - 只包含类型声明（Enum / dataclass / Protocol / type alias）
    - 每个字段带语义注释，写清单位与时间基准
    - 可序列化（JSON 友好；数组字段提供 shape/dtype 描述）

MUST NOT:
    - 包含任何计算、I/O、或第三方算法调用
    - import harmonica_eval.core / .host / .algorithms / .cockpit
    - 定义任何「便利函数」或默认业务值

INPUT:
    （无）

OUTPUT:
    SessionState · TimelineBasis · ErrorCode · AudioAsset · PortDescriptor
    BufferView · SurfaceManifest · AlgorithmResultEnvelope · SessionHandle

BUILD-INSTRUCTION:
    .spec/build/FILE-010-v1.md
'''

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence

import numpy as np
import numpy.typing as npt


# ─────────────────────────────────────────────────────────────────────
# 会话状态（对 C1 暴露的唯一状态词汇，来自 CONTRACT-HOST-v1）
# ─────────────────────────────────────────────────────────────────────

class SessionState(str, Enum):
    """会话状态。C1 只允许看到这些；C2 内部阶段不得外泄。"""

    CREATED = "CREATED"
    INPUT_READY = "INPUT_READY"
    BUILDING = "BUILDING"
    DATA_READY = "DATA_READY"
    FAILED = "FAILED"
    CLOSED = "CLOSED"


class TimelineBasis(str, Enum):
    """端口挂在哪条时间轴上。

    归一化会抹掉抢拍拖拍，故节奏类指标必须在 REFERENCE 轴上计算。
    """

    REFERENCE = "REFERENCE"   # 保留源时间（对齐后重采样到参考时间轴）
    WARPED = "WARPED"         # 时间归一化（练习被拉伸到与参考等长）


class AlignmentRepresentation(str, Enum):
    """数据面必须始终提供的两份对齐 PCM（本仓自定保证）。"""

    MAPPED = "MAPPED"     # 保留源时间
    WARPED = "WARPED"     # 时间归一化


# ─────────────────────────────────────────────────────────────────────
# 输入资产
# ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AudioAsset:
    """一段不可变的输入音频。

    只描述「从哪里读」与「应当被当作什么」，不持有解码后的数据。
    """

    asset_id: str
    """调用方给定的稳定标识，用于日志与追溯。"""

    uri: str
    """可读取位置。C1 负责把平台文件选择器的结果变成一个 uri。"""

    declared_sample_rate: int | None = None
    """调用方声明的采样率；None 表示以解码结果为准。"""


@dataclass(frozen=True)
class AudioFormat:
    """C2 标准化之后的统一格式。"""

    sample_rate: int
    """Hz。必须记录：f0 估计结果依赖采样率（实测 22.05k 会把 D5 判成 D4）。"""

    channels: int
    """恒为 1。多声道在 ingest 阶段已被下混。"""

    dtype: str
    """numpy dtype 名称，恒为 'float32'。"""

    def __post_init__(self) -> None:
        if self.channels != 1:
            raise ValueError("C2 契约要求 mono")
        if self.dtype != "float32":
            raise ValueError("C2 契约要求 float32")


# ─────────────────────────────────────────────────────────────────────
# 数据面（CONTRACT-ALGORITHM-DATA-v1）
# ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PortDescriptor:
    """一个端口的自描述头。算法仅凭它即可决定是否可用。"""

    port_id: str
    """稳定标识，如 'pcm.mapped.reference'。Seal 后不可变。"""

    schema_version: str
    """该端口自身的 schema 版本。"""

    element_type: str
    """numpy dtype 名称，如 'float32' / 'complex64'。"""

    dimensions: Sequence[str]
    """维度语义名，如 ('frame', 'bin') / ('sample',)。"""

    shape: Sequence[int]
    """实际形状。"""

    units: str
    """物理单位：'amplitude' / 'magnitude' / 'seconds' / 'hz' / 'rms' …"""

    timeline_basis: TimelineBasis
    """该端口的时间坐标含义。**必填**，无默认值。"""

    sample_rate: int
    """Hz。**必填**：采样率是算法结果的成因，不是元数据。"""

    content_hash: str
    """Seal 时计算的内容指纹，用于同 build 回归断言。"""


@dataclass(frozen=True)
class BufferView:
    """对某端口的只读借用视图。

    所有权始终属于 C2。借用方不得修改、不得释放、不得跨会话持有。
    """

    data: npt.NDArray[Any] = field(repr=False)
    """只读数组。写入行为视为契约违规。"""

    element_count: int
    """元素总数。"""

    element_type: str


@dataclass(frozen=True)
class SurfaceManifest:
    """数据面的自描述清单。

    外部通过它枚举端口，无需预知端口清单——这是「深组件」的关键：
    C2 内部可以增删端口而不破坏外部。
    """

    profile_version: str
    """生成此数据面所用的 CORE_PROFILE 版本。"""

    audio_format: AudioFormat
    """标准化后的格式，对全部端口成立。"""

    reference_duration_sec: float
    practice_duration_sec: float

    ports: Mapping[str, PortDescriptor]
    """port_id → 描述符。"""

    sealed: bool
    """Seal 后为 True；False 时不得交给算法。"""


@dataclass(frozen=True)
class AlgorithmResultEnvelope:
    """算法的标准回执。

    算法失败也必须返回信封（而非抛异常穿透），以便 C1 隔离故障。
    """

    algorithm_id: str
    algorithm_version: str

    status: str
    """'OK' | 'FAILED' | 'INCOMPATIBLE'。"""

    required_ports: Sequence[str]
    """算法声明需要的端口。仅用于兼容性检查。"""

    consumed_ports: Sequence[str]
    """本次**实际读取**的端口。用于证据与优化，不得反向触发 C2 生成数据。"""

    payload: Mapping[str, Any]
    """结果本体。形状由算法自己声明，C1 不解释其内部。"""

    error_code: str | None = None
    error_detail: str | None = None

    elapsed_sec: float | None = None


# ─────────────────────────────────────────────────────────────────────
# 会话句柄
# ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SessionHandle:
    """C1 持有的不透明会话标识。

    C1 不得通过它访问 C2 内部符号——它只用于回传给 CONTRACT-HOST-v1。
    """

    session_id: str


class SurfaceHandle(Protocol):
    """CONTRACT-ALGORITHM-DATA-v1 —— 算法侧看到的全部世界。

    只有两个操作。这是「接口极小、实现极深」的落点：
    算法不需要知道 C2 内部有任何模块、DAG 或存储后端。
    """

    def manifest(self) -> SurfaceManifest:
        """返回自描述清单。"""
        ...

    def read(
        self,
        port_id: str,
        time_range: tuple[float, float] | None = None,
    ) -> BufferView:
        """按键读取一个端口的（可选时间窗）只读视图。

        time_range 为 None 表示整段。单位为秒，坐标含义由该端口的
        timeline_basis 决定。
        """
        ...
