'''
FILE-ID:      FILE-105
COMPONENT:    COMP-C2 Audio Core
SPEC:         contract.HostContract · contract.SessionState · COMPONENTS.md@v2 §4.1

ROLE:
    实现 CONTRACT-HOST-v1 的 **7 个操作**，持有会话状态机与资源生命周期。

INTENT:
    让 Core 的门面**极小且不可增长**。7 个操作是 C1 能对 C2 说的全部话语；
    任何第 8 个操作都意味着核心在获得新职责，必须走 MOLD BREAK 而非就地添加。

    ★ FORBIDDEN_OPERATIONS 定义了**绝不允许**出现在这里的方法名。
    判据：若 C1 需要调用其中任何一个，说明编排权或算法知识泄漏进了 Core。
    这使「Core 不知道算法的存在」成为一条可被机械验证的事实。

MUST:
    - 状态机单调推进：CREATED → INPUT_READY → BUILDING → DATA_READY，
      任一状态可 → FAILED，结束 → CLOSED。**不可回退、不可跳过。**
    - status() **只返回 SessionState 的六个值之一**；
      内部阶段（INGESTING / ALIGNING / BUILDING_PORTS…）不得外泄
    - build_surface() 失败时：状态 → FAILED，**不得部分发布**，
      资源全部释放，且**未触发任何算法**
    - 同一对输入 + 同一 profile_version ⇒ 同一数据面（content_hash 一致）

MUST NOT:
    - 定义 FORBIDDEN_OPERATIONS 中的任何方法名
    - 接收任何算法信息（它不知道谁会来读）
    - 在 status() 里泄漏内部阶段
    - 允许在非 DATA_READY 状态取得数据面

INPUT:
    （无 —— 本模块是被调用方）

OUTPUT:
    HostCore —— 实现 HostContract 的会话管理器

BUILD-INSTRUCTION:
    .spec/build/FILE-105-v1.md
'''

from __future__ import annotations

from typing import Mapping

from ..contract import HostContract, SessionState
from .surface import Surface


class HostCore(HostContract):
    """CONTRACT-HOST-v1 的实现。全系统唯一的会话状态持有者。

    ⚠ 本类的方法集合必须**恰好**是契约声明的 7 个。
    多一个都是契约变更（宪章 §47.6 Silent Contract Mutation）。
    """

    def create_session(self, profile_version: str) -> str:
        """创建分析会话，返回 session_id。状态 → CREATED。

        profile_version 必须显式传入并**记录在会话里** ——
        没有它，「同一对输入」不成立：
        数据面内容是 (reference, practice, profile_version) 的函数。
        """
        raise NotImplementedError("SHELL: FILE-105 待注入实现")

    def set_reference(self, uri: str) -> None:
        """登记参考演奏。**不触发**解码或计算。

        合法状态：CREATED / INPUT_READY
        两段都登记后 → INPUT_READY
        """
        raise NotImplementedError("SHELL: FILE-105 待注入实现")

    def set_practice(self, uri: str) -> None:
        """登记学习者演奏。**不触发**解码或计算。

        合法状态：CREATED / INPUT_READY
        两段都登记后 → INPUT_READY
        """
        raise NotImplementedError("SHELL: FILE-105 待注入实现")

    def build_surface(self, session_id: str) -> None:
        """**一次性预生成**全部端口并 Seal。状态 INPUT_READY → BUILDING → DATA_READY。

        这不是惰性求值 —— 见 features.py 的模块 docstring（负责人裁定）。

        失败：抛 CoreBuildError，状态 → FAILED，**不得部分发布**，
              资源全部释放，且**未触发任何算法**。
        """
        raise NotImplementedError("SHELL: FILE-105 待注入实现")

    def status(self, session_id: str) -> SessionState:
        """返回会话状态。

        **只返回 SessionState 的六个值之一**。
        内部阶段（INGESTING / ALIGNING / BUILDING_PORTS…）**不得外泄** ——
        泄漏它会让 C1 开始依赖 Core 的内部实现，深组件随即瓦解。
        """
        raise NotImplementedError("SHELL: FILE-105 待注入实现")

    def acquire_surface(self, session_id: str) -> Surface:
        """取得数据面的只读句柄。

        前置：状态 == DATA_READY，否则抛 ContractViolation。
        所有权：句柄有效期至 destroy_session；借用方不得释放。
        """
        raise NotImplementedError("SHELL: FILE-105 待注入实现")

    def destroy_session(self, session_id: str) -> None:
        """销毁会话并释放全部资源。状态 → CLOSED。

        之后使用旧句柄的任何行为都是 ContractViolation。
        必须幂等（重复销毁不报错）—— 清理路径上的异常会掩盖真实失败。
        """
        raise NotImplementedError("SHELL: FILE-105 待注入实现")


INTERNAL_STAGES: Mapping[SessionState, tuple[str, ...]] = {
    SessionState.BUILDING: (
        "INGESTING", "ALIGNING", "MATERIALIZING", "SEALING",
    ),
}
"""C2 内部阶段 —— **仅供内部日志使用，绝不出现在 status() 的返回里。**

保留这份清单是为了让审查者能验证一件事：
`status()` 的返回值只可能来自 SessionState，不可能来自这里。
"""
