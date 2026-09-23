'''
FILE-ID: FILE-012
COMPONENT: COMP-CONTRACT（跨组件契约层）
SPEC: COMPONENTS.md@v2 §2 · §4 · SPEC.md@v2.1 §1

ROLE:
    C1 ↔ C4 的界面契约：UI View（下行投影）与 UI Command（上行意图）。
    纯声明，无渲染、无业务逻辑。

INTENT:
    让「界面」与「内核」之间只有一层薄契约，从而使 C4 可被删除而不影响内核
    （Invariant F），也使内核可以无头运行。

MUST:
    - 只声明数据结构与 Protocol，不含任何渲染或框架依赖
    - 投影必须是**已下采样**的（避免"人类面对几千个文件"——宪章 §44.12）
    - 投影必须自描述（名称/单位/时间基准），否则 C4 只能靠猜

MUST NOT:
    - import 任何 UI 框架（Dash/Streamlit/Flask/…）
    - 让 C4 直接接触数据面句柄或音频缓冲
    - 在投影里塞入算法内部结构（C4 不解释算法内部）

INPUT:
    （无）

OUTPUT:
    UiView · UiSeries · UiScalar · UiCommand · UiCommandKind · UiProjectionPort

BUILD-INSTRUCTION:
    .spec/build/FILE-012-v1.md

NOTE:
    本契约**不依赖 OC1（数据面形态）**：
    投影只表达"可展示的序列与标量"，与数据面如何存储/计算无关。
'''

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Sequence

from .session import SessionState, TimelineBasis


# ─────────────────────────────────────────────────────────────────────
# UI View —— C1 → C4 的只读投影
# ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class UiScalar:
    """一个可展示的标量指标。

    只陈述数值与该数值的含义，**不下教学结论**（SPEC §3）。
    """

    key: str
    """稳定标识，如 'pitch_cents_mae'。"""

    label: str
    """给人看的短名，中文。"""

    value: float
    unit: str
    """单位：'cents' / 'ms' / 'db' / 'ratio' / '' 。"""

    threshold: float | None = None
    """可选的参考阈值。None 表示纯粹陈述、无判定。"""


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
    """时间轴含义。节奏类展示必须用 REFERENCE，否则会误导。"""

    source_port: str | None = None
    """该曲线源自哪个端口（便于调试追溯）。None 表示由算法直接产出。"""


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
    """0.0–1.0；None 表示无进度概念。"""

    error_code: str | None = None
    error_detail: str | None = None

    note: str = ""
    """给开发者的一句话说明（例如"数据面已 Seal，可运行算法"）。"""


class UiProjectionPort(Protocol):
    """C1 对 C4 提供的唯一入口。

    C4 通过它订阅投影、下发命令。**只有这两个操作**——
    与数据面契约同为"接口极小"的设计。
    """

    def snapshot(self) -> UiView:
        """取当前投影快照。必须是纯读取，无副作用。"""
        ...

    def submit(self, command: "UiCommand") -> None:
        """下发一条用户意图。由 C1 校验并执行。"""
        ...


# ─────────────────────────────────────────────────────────────────────
# UI Command —— C4 → C1 的用户意图
# ─────────────────────────────────────────────────────────────────────

class UiCommandKind(str, Enum):
    """界面能表达的**全部**意图。

    刻意保持极小：C4 不能凭界面发明内核能力。
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
    """命令参数。例如 SET_REFERENCE 的 {'uri': '...'}。"""
