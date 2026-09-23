'''
FILE-ID: FILE-011
COMPONENT: COMP-CONTRACT（跨组件契约层）
SPEC: SPEC.md@v2.1 · COMPONENTS.md@v2 §7

ROLE:
    统一错误码与异常层次。纯声明。

INTENT:
    让失败语义成为契约的一部分，而不是各组件即兴发挥。
    宪章 §5.6 No Silent Degradation：失败必须显式、可分类、可上报。

MUST:
    - 每个错误码附「归属组件」与「系统级后果」注释
    - 异常携带结构化上下文（session_id / port_id / detail）
    - 区分「构建期失败」与「运行期失败」——二者后果完全不同

MUST NOT:
    - 捕获异常后静默降级（例如对齐失败就退化为逐点硬比）
    - 把内部堆栈直接暴露给 C1（C1 只拿错误码 + 简短 detail）

INPUT:
    （无）

OUTPUT:
    ErrorCode · HarmonicaError 及其子类

BUILD-INSTRUCTION:
    .spec/build/FILE-011-v1.md
'''

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    """全部失败原因。新增必须同步 COMPONENTS.md §7 失败语义表。"""

    # ── 输入层 ────────────────────────────────────────────────
    INPUT_UNREADABLE = "INPUT_UNREADABLE"
    """归属 C2。文件不可读/权限拒绝/格式不可解码。数据面不存在，算法不启动。"""

    INPUT_TOO_SHORT = "INPUT_TOO_SHORT"
    """归属 C2。短于最小可分析长度。数据面不存在。"""

    INPUT_SILENT = "INPUT_SILENT"
    """归属 C2。整段静音，无法建立任何有效映射。数据面不存在。"""

    # ── 构建层 ────────────────────────────────────────────────
    CORE_BUILD_FAILED = "CORE_BUILD_FAILED"
    """归属 C2。标准化/对齐/实体化任一步失败。**不得部分发布**，全部资源释放。"""

    ALIGNMENT_UNRECOVERABLE = "ALIGNMENT_UNRECOVERABLE"
    """归属 C2。无法建立有效时间映射。**禁止**静默退化为逐点硬比。"""

    # ── 算法层 ────────────────────────────────────────────────
    PLUGIN_INCOMPATIBLE = "PLUGIN_INCOMPATIBLE"
    """归属 C1 判定。算法声明了数据面没有的端口。数据面仍有效，其他算法不受影响。"""

    ALGORITHM_FAILED = "ALGORITHM_FAILED"
    """归属 C3。算法崩溃/NaN/非法 schema。数据面仍有效。"""

    ALGORITHM_RESULT_INVALID = "ALGORITHM_RESULT_INVALID"
    """归属 C1（校验）。结果不符合其声明的 schema。"""

    ALGORITHM_TIMEOUT = "ALGORITHM_TIMEOUT"
    """归属 C1。v0.1 未实现（已知缺口，见 COMPONENTS.md §7）。"""

    # ── 界面层 ────────────────────────────────────────────────
    COCKPIT_DETACHED = "COCKPIT_DETACHED"
    """归属 C4。界面断开不影响会话，仅记录。"""

    # ── 未知 ──────────────────────────────────────────────────
    INTERNAL_ERROR = "INTERNAL_ERROR"
    """兜底。出现即表示有未分类失败路径，应视为缺陷。"""


@dataclass
class HarmonicaError(Exception):
    """全部受控失败的基类。

    携带结构化上下文，使 C1 能归一化上报而不泄漏内部实现。
    """

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
    """调用方违反了契约（例如在 Seal 前取数据面、试图写只读缓冲）。

    这是**程序缺陷**，不是环境问题；不应被重试逻辑吞掉。
    """


class CoreBuildError(HarmonicaError):
    """C2 构建期失败。数据面不存在，算法不得启动。"""


class AlgorithmError(HarmonicaError):
    """C3 运行期失败。数据面与其余算法不受影响。"""
