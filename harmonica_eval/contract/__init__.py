'''
FILE-ID: FILE-011
COMPONENT: COMP-CONTRACT（跨组件契约层）

ROLE:
    契约层的公开出口。集中 re-export，使下游只需 import 一个名字。

INTENT:
    单一入口 ⇒ 契约变更时只需改这里，且可看出"对外承诺了什么"。

MUST:
    - 只 re-export，不含任何逻辑
    - 明确区分「已冻结」与「待 OC1 裁定」

MUST NOT:
    - 在此处做任何计算或校验
    - re-export 任何实现模块

BUILD-INSTRUCTION:
    .spec/build/FILE-011-v1.md
'''

from .session import (
    AlignmentRepresentation,
    AudioFormat,
    SessionState,
    TimelineBasis,
)
from .errors import ErrorCode, HarmonicaError, ContractViolation, AlgorithmError, CoreBuildError
from .host import HostContract, FORBIDDEN_OPERATIONS
from .data_surface import AlgorithmDataContract, REQUIRED_PORT_INVARIANTS
from .ui import UiCommand, UiCommandKind, UiProjectionPort, UiScalar, UiSeries, UiView

__all__ = [
    # 已冻结（不依赖 OC1）
    "SessionState", "TimelineBasis", "AlignmentRepresentation", "AudioFormat",
    "ErrorCode", "HarmonicaError", "ContractViolation", "AlgorithmError", "CoreBuildError",
    "UiView", "UiSeries", "UiScalar", "UiCommand", "UiCommandKind", "UiProjectionPort",
    # 结构已冻结、签名待 OC1
    "HostContract", "AlgorithmDataContract",
    "FORBIDDEN_OPERATIONS", "REQUIRED_PORT_INVARIANTS",
]
