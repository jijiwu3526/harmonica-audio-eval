'''
FILE-ID: FILE-013
COMPONENT: COMP-CONTRACT（跨组件契约层）
SPEC: COMPONENTS.md@v2 §4 · SPEC.md@v2.1 §5.5

ROLE:
    会话状态与时间基准的词汇表。纯声明，无行为。

INTENT:
    为全系统提供两个**与数据面形态无关**的共享词汇：
      1. 会话状态 —— C1 唯一允许看到的状态机
      2. 时间基准 —— 每个量必须声明它挂在哪条时间轴上

WHY-THIS-FILE-IS-SAFE-TO-FREEZE-NOW:
    本项目当前唯一未决项是 OC1（数据面形态：全物化 / mmap / 惰性 / 流式）。
    本文件刻意**只包含不随 OC1 变化的词汇**：

    - 会话状态取自 CONTRACT-HOST-v1，是生命周期概念。
      `DATA_READY` 的含义是「数据面已构建并 Seal」——
      无论它存在内存、磁盘，还是根本没物化（惰性），该语义都成立。
    - 时间基准来自 SPEC.md §5.5「两轴分离」，是**产品需求**层面的强制：
      归一化会抹掉抢拍拖拍，故节奏类指标必须在保留源时间的轴上算。
      这与实现无关。

    凡**依赖** OC1 的类型（端口描述符、缓冲视图、数据面清单、句柄）
    **一律不在本文件**，它们的草稿在 `.spec/draft/` 且不得被引用。

MUST:
    - 只包含 Enum 与不依赖存储形态的 dataclass
    - 每个成员带语义注释

MUST NOT:
    - 出现 PortDescriptor / BufferView / SurfaceManifest / SurfaceHandle
      （这些依赖 OC1，见上）
    - 包含任何计算或 I/O

INPUT:
    （无）

OUTPUT:
    SessionState · TimelineBasis · AlignmentRepresentation · AudioFormat

BUILD-INSTRUCTION:
    .spec/build/FILE-013-v1.md
'''

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SessionState(str, Enum):
    """会话状态。**C1 只允许看到这些**；C2 内部阶段不得外泄。

    单调推进，不可回退（Invariant A 的前提）：
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
    """数据面已按 profile 构建完成并 Seal。**这是算法的唯一合法触发点**。"""

    FAILED = "FAILED"
    """构建或运行失败。数据面**不存在**（不得部分发布）。"""

    CLOSED = "CLOSED"
    """会话已销毁，资源已释放。"""


class TimelineBasis(str, Enum):
    """一个量挂在哪条时间轴上。**每个端口/每条曲线都必须声明**。

    依据 SPEC.md §5.5：两轴必须分离，且节奏类指标只能在 REFERENCE 上算。
    """

    REFERENCE = "REFERENCE"
    """保留源时间。对齐后重采样到**参考演奏**的时间轴。
    抢拍拖拍在此轴上**可见**。→ 节奏类指标必须用它。"""

    WARPED = "WARPED"
    """时间归一化。练习被拉伸到与参考等长。
    抢拍拖拍在此轴上**被抹掉**。→ 拿它报节奏错误是构造性错误。"""


class AlignmentRepresentation(str, Enum):
    """数据面必须**始终**提供的两份对齐 PCM（宪章 §11 逃生口）。

    因为这两份永远存在，profile 只决定「快不快」，不决定「能不能」：
    任何算法都能拿 PCM 自行做特有预处理。
    """

    MAPPED = "MAPPED"
    """保留源时间（对齐后落在参考时间轴上）。"""

    WARPED = "WARPED"
    """时间归一化（与参考等长）。"""


@dataclass(frozen=True)
class AudioFormat:
    """C2 标准化之后的统一格式。

    这是**全局唯一**的格式声明；所有端口都继承它。
    """

    sample_rate: int
    """Hz。**必须记录**：实测同一段音频在 22.05 kHz 下 f0 会被判低八度
    （−1200 音分），44.1 kHz 下正常。采样率是**结果的成因**，不是元数据。"""

    channels: int
    """恒为 1。多声道在 ingest 阶段已下混。"""

    dtype: str
    """numpy dtype 名称，恒为 'float32'。"""

    def __post_init__(self) -> None:
        if self.channels != 1:
            raise ValueError("C2 契约要求 mono")
        if self.dtype != "float32":
            raise ValueError("C2 契约要求 float32")
