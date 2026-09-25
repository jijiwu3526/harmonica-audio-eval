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
    - 正常流程状态单调推进：CREATED → INPUT_READY → BUILDING → DATA_READY，
      任一状态可 → FAILED，结束 → CLOSED；不跳过 DATA_READY。
      CANCEL / RESET 是管理操作，允许回退到稳定态。
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
    - 让 destroy_session 之后已发出的 Surface 句柄继续可读
      （任何 manifest() / read() 都必须抛 ContractViolation）

INPUT:
    （无 —— 本模块是被调用方）

OUTPUT:
    HostCore —— 实现 HostContract 的会话管理器

BUILD-INSTRUCTION:
    .spec/build/FILE-105-v1.md
'''

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Mapping

from ..contract import (
    ContractViolation,
    CoreBuildError,
    ErrorCode,
    HarmonicaError,
    HostContract,
    SessionState,
)
from ..profile import AUDIO
from .surface import Surface


@dataclass
class _Session:
    """模块私有会话记录，恰含 FILE-105 §4.1 冻结的 6 个字段。"""

    session_id: str
    profile_version: str
    state: SessionState = SessionState.CREATED
    reference_uri: str | None = None
    practice_uri: str | None = None
    surface: Surface | None = None


class HostCore(HostContract):
    """CONTRACT-HOST-v1 的实现。全系统唯一的会话状态持有者。

    ⚠ 本类的方法集合必须**恰好**是契约声明的 7 个。
    多一个都是契约变更（宪章 §47.6 Silent Contract Mutation）。
    """

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}

    def _require(self, session_id: str) -> _Session:
        """取已登记会话；未知 id 统一归一化为 C2 契约错误。"""
        session = self._sessions.get(session_id)
        if session is None:
            raise ContractViolation(
                code=ErrorCode.INTERNAL_ERROR,
                detail="未知 session_id",
                session_id=session_id,
                component="COMP-C2",
            )
        return session

    def _set_uri(self, session_id: str, uri: str, side: str) -> None:
        """登记一侧输入；只在 CREATED / INPUT_READY 可用。"""
        session = self._require(session_id)
        if not isinstance(uri, str) or uri == "":
            raise ContractViolation(
                code=ErrorCode.INTERNAL_ERROR,
                detail="uri 必须是非空 str",
                session_id=session_id,
                component="COMP-C2",
            )
        if session.state not in (SessionState.CREATED, SessionState.INPUT_READY):
            raise ContractViolation(
                code=ErrorCode.INTERNAL_ERROR,
                detail=f"当前状态 {session.state.value} 不接受输入登记",
                session_id=session_id,
                component="COMP-C2",
            )
        if side == "reference":
            session.reference_uri = uri
        else:
            session.practice_uri = uri
        if session.reference_uri is not None and session.practice_uri is not None:
            session.state = SessionState.INPUT_READY

    def create_session(self, profile_version: str) -> str:
        """创建分析会话，返回 session_id。状态 → CREATED。

        profile_version 必须显式传入并**记录在会话里** ——
        没有它，「同一对输入」不成立：
        数据面内容是 (reference, practice, profile_version) 的函数。
        """
        if not isinstance(profile_version, str) or profile_version == "":
            raise ContractViolation(
                code=ErrorCode.INTERNAL_ERROR,
                detail="profile_version 必须是非空 str",
                component="COMP-C2",
            )
        sid = uuid.uuid4().hex
        self._sessions[sid] = _Session(
            session_id=sid,
            profile_version=profile_version,
            state=SessionState.CREATED,
            reference_uri=None,
            practice_uri=None,
            surface=None,
        )
        return sid

    def set_reference(self, session_id: str, uri: str) -> None:
        """登记参考演奏。**不触发**解码或计算。

        ★ G8 修正：补上 `session_id`（原签名 `set_reference(uri)` 与
        同协议其余 5 个操作不自洽 —— 见 contract.HostContract 的说明）。

        合法状态：CREATED / INPUT_READY
        两段都登记后 → INPUT_READY
        """
        self._set_uri(session_id, uri, "reference")

    def set_practice(self, session_id: str, uri: str) -> None:
        """登记学习者演奏。**不触发**解码或计算。

        ★ G8 修正：补上 `session_id`。

        合法状态：CREATED / INPUT_READY
        两段都登记后 → INPUT_READY
        """
        self._set_uri(session_id, uri, "practice")

    def build_surface(self, session_id: str) -> None:
        """**一次性预生成**全部端口并 Seal。状态 INPUT_READY → BUILDING → DATA_READY。

        这不是惰性求值 —— 见 features.py 的模块 docstring（负责人裁定）。

        失败：抛 CoreBuildError，状态 → FAILED，**不得部分发布**，
              资源全部释放，且**未触发任何算法**。
        """
        session = self._require(session_id)
        if session.state is not SessionState.INPUT_READY:
            raise ContractViolation(
                code=ErrorCode.INTERNAL_ERROR,
                detail=(
                    "build_surface 前置状态必须是 INPUT_READY，"
                    f"当前 {session.state.value}"
                ),
                session_id=session_id,
                component="COMP-C2",
            )

        session.state = SessionState.BUILDING
        stage = "INGESTING"
        try:
            from . import align as _align
            from . import ingest as _ingest
            from . import surface as _surface

            reference = _ingest.ingest(session.reference_uri)  # type: ignore[arg-type]
            practice = _ingest.ingest(session.practice_uri)  # type: ignore[arg-type]

            stage = "ALIGNING"
            warp_path = _align.align(reference, practice)
            sample_rate = int(AUDIO.sample_rate)
            stage = "SEALING"
            built = _surface.build_surface(
                reference, practice, sample_rate, warp_path
            )
        except HarmonicaError as err:
            session.surface = None
            session.state = SessionState.FAILED
            raise CoreBuildError(
                code=err.code,
                detail=f"{stage}: {err.detail}",
                session_id=session_id,
                component="COMP-C2",
            ) from err
        except Exception as err:
            session.surface = None
            session.state = SessionState.FAILED
            raise CoreBuildError(
                code=ErrorCode.CORE_BUILD_FAILED,
                detail=f"{stage}: {type(err).__name__}: {err}",
                session_id=session_id,
                component="COMP-C2",
            ) from err

        session.surface = built
        session.state = SessionState.DATA_READY
        return None

    def status(self, session_id: str) -> SessionState:
        """返回会话状态。

        **只返回 SessionState 的六个值之一**。
        内部阶段（INGESTING / ALIGNING / BUILDING_PORTS…）**不得外泄** ——
        泄漏它会让 C1 开始依赖 Core 的内部实现，深组件随即瓦解。
        """
        return self._require(session_id).state

    def acquire_surface(self, session_id: str) -> Surface:
        """取得数据面的只读句柄。

        前置：状态 == DATA_READY，否则抛 ContractViolation。
        所有权：句柄有效期至 destroy_session；借用方不得释放。

        ★★★ 返回的 Surface 必须真的带 `resolution` 属性 ★★★

        规格冻结要求（FILE-003:175）：`AlgorithmDataContract` 是
        「2 个操作 + 1 个只读状态属性 `resolution`，不计入操作数」。

        ★ 当前实测：`Surface().resolution` 返回 `None`
        （继承 Protocol 的 `...` 默认体，C2 尚未显式实现）。
        ★ ★ **C1 依赖它做 BLOCK-2 方案乙的校验**：
        ```
        C1 在调用点比较 consumed_ports ⊆ available
        → 需要知道「哪些端口实际可用」
        → 读句柄的 resolution
        ```
        ★ 若它为 None，C1 会把「全部端口可用」当成结论 ——
        ★ ★ 那是**静默的错误校验**，正是 timing 铭牌警告的
        ★ ★ 「不会报错、只给错误答案」那一类陷阱。

        ★ **本方法不新增任何操作**（FILE-003 §4.15 禁止 port 增第三个操作）；
        ★ 修复路径是 C2 在 `Surface` 里显式实现该属性，不是在这里加方法。

        ★ 端口的实际 `shape` 从该句柄的 `manifest()` 取得
        （负责人裁定 2026-09-24：「C1 向 C2 询问 shape」）。

        理由：`shape` 是**运行期事实**（帧数依赖音频时长与 hop），
        `profile.PortSpec` 里没有该字段，**也不得**从 `dimensions`
        的语义名反推 —— 语义名只表维度种类，不含大小。

        ★ C1 在 `snapshot()` 投影 `UiView.port_summary` 时，`shape` 直接取自
        `manifest().ports[*].shape`，**不得**自行推导、不得填占位值。
        ★ **本文件因此不需要新增任何方法**（`FILE-003` §4.15 仍禁止 port 增第三个操作）。
        """
        session = self._require(session_id)
        if session.state is not SessionState.DATA_READY or session.surface is None:
            raise ContractViolation(
                code=ErrorCode.INTERNAL_ERROR,
                detail="状态非 DATA_READY，无数据面可取得",
                session_id=session_id,
                component="COMP-C2",
            )
        return session.surface

    def destroy_session(self, session_id: str) -> None:
        """销毁会话并释放全部资源。状态 → CLOSED。

        ★ `destroy_session` **必须使所有已发出的 Surface 句柄失效**。
        之后对旧句柄的任何 `manifest()` / `read()` 调用都必须抛
        `ContractViolation`，不得继续暴露已释放的数据面。

        原因是资源生命周期必须在销毁处收束：旧句柄若仍可读，
        会继续占用数据面预算（最高 512 MiB）并形成泄漏；让
        `acquire_surface` 不再返回旧引用**不足以**收束已发出去的引用。
        `Surface` 负责执行读操作时的失效判定，本方法负责触发并保证
        这一生命周期边界。

        必须幂等（重复销毁不报错）—— 清理路径上的异常会掩盖真实失败。
        """
        session = self._sessions.get(session_id)
        if session is None:
            return None
        # ★ 契约 INV-105-8：使**已发出的所有句柄**失效。
        #   只清 session.surface 不足以收束 —— 调用方手里可能还握着旧引用。
        #   `_invalidate()` 是 Surface 内部生命周期钩子；公开操作面不变。
        if session.surface is not None:
            session.surface._invalidate()
        session.surface = None
        session.reference_uri = None
        session.practice_uri = None
        session.state = SessionState.CLOSED
        return None


INTERNAL_STAGES: Mapping[SessionState, tuple[str, ...]] = {
    SessionState.BUILDING: (
        "INGESTING", "ALIGNING", "MATERIALIZING", "SEALING",
    ),
}
"""C2 内部阶段 —— **仅供内部日志使用，绝不出现在 status() 的返回里。**

保留这份清单是为了让审查者能验证一件事：
`status()` 的返回值只可能来自 SessionState，不可能来自这里。
"""
