'''
FILE-ID:      FILE-301
COMPONENT:    COMP-C1 Framework / Host
SPEC:         contract.HostContract · contract.UiProjectionPort · contract.COMMAND_LEGALITY
              COMPONENTS.md@v2 §4 · SPEC.md@v2.1 §1

ROLE:
    应用生命周期 + 组件装配 + 算法编排 + 失败归一化 + 投影生成。
    全系统**唯一**的编排点。

INTENT:
    为什么 C1 必须存在（否则它会被当成多余的一层）：
    去掉 C1 后必然发生两件事之一：
        a) C2 得知道有哪些算法 → **深组件被破坏**，
           Core 变成插件需求的函数（正是负责人裁定要消灭的反模式）
        b) C4 直接调 C2/C3   → **界面进入计算路径**，
           UI 崩溃会污染数据面
    所以 C1 的职责是具体的、不可省的：持有会话、驱动状态机、调算法、
    归一化失败、产出投影。删掉本文件，全系统没有任何地方知道
    "先建数据面、再跑算法、再出视图"这个顺序。

MUST:
    - 正常流程状态单调推进，不跳过 DATA_READY
    - CANCEL / RESET 是管理操作，允许回退到稳定态
    - 算法**只能**在 DATA_READY 下触发
    - 兼容性检查是**单向**的（用 contract.COMMAND_LEGALITY 校验命令）
    - 单个算法失败**不影响**其他算法
    - 投影必须**已下采样**，且每条曲线声明 timeline_basis
    - C4 缺席时全流程仍能跑通（不变量 F）

MUST NOT:
    - 做任何信号处理（fft / pyin / stft / dtw / resample 一律禁止）
      —— 若你需要"算一下"，说明该逻辑属于 C2 或 C3
    - 因为某算法缺端口就去让 C2 生成数据（**核心禁令**）
    - 让算法异常穿透（必须捕获并转成 FAILED 信封）
    - 把不同 timeline_basis 的曲线放进同一个投影（会误导，见 UiSeries）

INPUT:
    （无 —— 本模块是装配点，被 __main__.py 或 cockpit 驱动）

OUTPUT:
    HostApp —— 同时实现 HostContract 的消费方与 UiProjectionPort

BUILD-INSTRUCTION:
    .spec/build/FILE-301-v1.md
'''

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from ..algorithms.registry import Registry
from ..algorithms.runtime import ResolvedSurface, resolve_inputs, validate_result
from ..contract import (
    AlgorithmError,
    AlgorithmResultEnvelope,
    COMMAND_LEGALITY,
    ContractViolation,
    CoreBuildError,
    ErrorCode,
    HarmonicaError,
    PluginSpec,
    SessionState,
    TimelineBasis,
    UI_PAYLOAD_KEYS,
    UiCommand,
    UiCommandKind,
    UiProjectionPort,
    UiScalar,
    UiSeries,
    UiView,
)
from ..core.api import HostCore

MAX_PROJECTION_POINTS: int = 2000
"""单条曲线在投影里的最大点数。

依据宪章 §44.12（Human Control Cockpit）：人类不得面对几十万个数据点。
120 s 音频在 hop=256 下有约 2 万个帧 —— 直接画出来既慢又无信息量。
下采样是**投影的职责**，不是界面的职责（界面不得重算）。
"""


__all__ = ["HostApp", "MAX_PROJECTION_POINTS", "build_default_app"]


class HostApp(UiProjectionPort):
    """编排层。持有会话、驱动状态机、调算法、产出投影。

    `HostContract` 是 C1 → C2 的接口，由 C2 实现；本类是它的消费方。
    `UiProjectionPort` 是 C1 → C4 的接口，由本类实现。因此本类还拥有
    `run_algorithms`、`check_compatibility`、`normalize_error` 与 `build_view`
    这些编排职责。

    C1 是一次运行只服务一个会话的门面，但 C2 本身仍支持多会话。门面在
    生命周期方法中记住当前句柄；显式传入 `session_id` 的运行、销毁和投影
    方法会校验它确实指向当前会话。
    """

    def __init__(self, core: object, registry: Registry | None = None) -> None:
        """装配 C1，保存核心句柄与 bootstrap 产出的注册表。

        `core` 是 HostContract 的实现对象，故意保持为 `object`，以便测试替身
        驱动。`registry` 是 `algorithms/bootstrap.py` 产出的 Registry；它不在
        构造函数中创建，也不读取文件系统。

        注册表条目数不立即当成分母：分母 N 在会话建立时对 `registry.list()`
        做一次快照，之后整个会话固定使用该快照。这样注册表后来发生增删时，
        正在运行的 k/N 进度不会倒退。
        """
        if registry is not None and not callable(getattr(registry, "list", None)):
            raise self._violation("registry 必须提供 list()")
        self._core = core
        self._registry = registry
        self._session_id: str | None = None
        self._profile_version: str | None = None
        self._state: SessionState = SessionState.CREATED
        self._session_specs: tuple[PluginSpec, ...] = ()
        self._algorithm_count: int = 0
        self._results: tuple[AlgorithmResultEnvelope, ...] = ()
        self._progress: float | None = 0.0
        self._error_code: str | None = None
        self._error_detail: str | None = None
        self._cancel_after_build = False

    # ── ① 生命周期 ────────────────────────────────────────────

    def create_session(self, profile_version: str) -> str:
        """创建会话，记住 session_id，状态进入 CREATED。"""
        if not isinstance(profile_version, str) or not profile_version:
            raise self._violation("profile_version 必须是非空字符串")
        sid = self._core.create_session(profile_version)
        if not isinstance(sid, str) or not sid:
            raise self._violation("C2 返回了无效的 session_id")
        self._session_id = sid
        self._profile_version = profile_version
        self._state = SessionState.CREATED
        self._session_specs = (
            tuple(self._registry.list()) if self._registry is not None else ()
        )
        self._algorithm_count = len(self._session_specs)
        self._results = ()
        self._progress = 0.0
        self._error_code = None
        self._error_detail = None
        self._cancel_after_build = False
        return sid

    def status(self, session_id: str) -> SessionState:
        """返回会话状态。

        契约（`contract.HostContract.status`）：
        - 只返回 SessionState 的六个值之一；C2 内部阶段
          （INGESTING / ALIGNING / BUILDING_PORTS / …）不得外泄。
        """
        self._require_current_session(session_id)
        return self._state

    def acquire_surface(self, session_id: str) -> Any:
        """取得数据面的只读句柄。

        契约（`contract.HostContract.acquire_surface`）：
        - 前置：状态 == DATA_READY，否则抛 ContractViolation。
        - 所有权：句柄有效期至 destroy_session。

        ★ 此前本类【缺】这两个方法，HostContract 声明的 7 个方法只实现了 5 个。
        ★ 后果是任何按契约写关键字调用的代码都会在运行期炸
        ★ AttributeError，而不是在装配期暴露 —— 属于「契约声明了但没兑现」。
        """
        self._require_current_session(session_id)
        if self._state is not SessionState.DATA_READY:
            # ★ ErrorCode 里没有 CONTRACT_VIOLATION 这一项；
            # ★ 数据面未就绪属 C2 侧前置不满足，取 CORE_BUILD_FAILED。
            raise ContractViolation(
                ErrorCode.CORE_BUILD_FAILED,
                f"acquire_surface 要求 DATA_READY，当前 {self._state.name}",
            )
        return self._core.acquire_surface(session_id)

    def destroy_session(self, session_id: str) -> None:
        """销毁指定会话；销毁当前会话时本地状态进入 CLOSED。"""
        self._core.destroy_session(session_id)
        if session_id == self._session_id:
            self._session_id = None
            self._profile_version = None
            self._state = SessionState.CLOSED
            self._session_specs = ()
            self._algorithm_count = 0
            self._results = ()
            self._progress = None
            self._error_code = None
            self._error_detail = None
            self._cancel_after_build = False

    def set_reference(self, session_id: str, uri: str) -> None:
        """登记参考演奏 uri；C1 先检查文件存在，再交给 C2。

        ★ 参数名与 `contract.HostContract` 逐字一致（`uri`）——
          关键字调用是契约的一部分，改名会让按契约写的代码运行期炸。
        """
        self._set_input(session_id, uri, practice=False)

    def set_practice(self, session_id: str, uri: str) -> None:
        """登记练习演奏 uri；C1 先检查文件存在，再交给 C2。

        ★ 参数名与 `contract.HostContract` 逐字一致（`uri`）。
        """
        self._set_input(session_id, uri, practice=True)

    def _set_input(self, session_id: str, uri: str, *, practice: bool) -> None:
        """登记一侧输入，并让状态以 C2 的状态查询为准。"""
        sid = self._require_current_session(session_id)
        if self._state not in (SessionState.CREATED, SessionState.INPUT_READY):
            raise self._violation(
                f"当前状态 {self._state.value} 不接受输入登记", sid
            )
        if not isinstance(uri, str):
            raise self._violation("输入路径必须是字符串", sid)
        try:
            exists = Path(uri).is_file()
        except (OSError, ValueError) as exc:
            raise self._violation("输入路径无法访问", sid) from exc
        if not exists:
            raise self._violation("输入路径不存在或不是普通文件", sid)
        if practice:
            self._core.set_practice(sid, uri)
        else:
            self._core.set_reference(sid, uri)
        self._state = self._core.status(sid)
        self._error_code = None
        self._error_detail = None

    def build_surface(self, session_id: str) -> None:
        """同步构建数据面，状态 INPUT_READY → BUILDING → DATA_READY。"""
        sid = self._require_current_session(session_id)
        if self._state is not SessionState.INPUT_READY:
            raise self._violation(
                f"build_surface 前置状态必须是 INPUT_READY，当前 {self._state.value}",
                sid,
            )
        self._state = SessionState.BUILDING
        self._progress = 0.0
        self._cancel_after_build = False
        try:
            self._core.build_surface(sid)
        except Exception as exc:
            self._state = SessionState.FAILED
            self._progress = None
            if isinstance(exc, HarmonicaError):
                self._error_code, self._error_detail = self.normalize_error(exc)
            else:
                self._error_code = ErrorCode.CORE_BUILD_FAILED.value
                self._error_detail = "构建数据面失败"
            raise
        self._state = self._core.status(sid)
        if self._state is not SessionState.DATA_READY:
            raise self._violation("C2 构建完成但未进入 DATA_READY", sid)
        # 同步构建期间收到 CANCEL 时只记录意图，绝不打断 C2；构建完成后
        # 数据面已经合法，仍以 C2 的最终状态为准。
        self._cancel_after_build = False
        self._progress = 1.0
        self._error_code = None
        self._error_detail = None

    # ── ② 编排 ────────────────────────────────────────────────

    def check_compatibility(self, algorithm_id: str) -> bool:
        """只检查插件声明的 required 端口是否存在。"""
        sid = self._require_session()
        spec = next(
            (item for item in self._session_specs if item.algorithm_id == algorithm_id),
            None,
        )
        if spec is None:
            return False
        surface = self._core.acquire_surface(sid)
        available = surface.manifest().ports
        return all(item.port_id in available for item in spec.required_inputs)

    def run_algorithms(self, session_id: str) -> Sequence[AlgorithmResultEnvelope]:
        """按会话快照顺序运行全部算法，并隔离每个算法的故障。"""
        sid = self._require_current_session(session_id)
        if self._state is not SessionState.DATA_READY:
            raise self._violation(
                f"算法只能在 DATA_READY 触发，当前 {self._state.value}", sid
            )
        total = self._algorithm_count
        if total == 0:
            # 契约要求 N=0 时不得计算 k/N；这是装配/状态错误而非正常空结果。
            raise self._violation("注册表快照为空，不能运行算法", sid)
        surface = self._core.acquire_surface(sid)
        manifest = surface.manifest()
        results: list[AlgorithmResultEnvelope] = []
        self._progress = 0.0
        for index, spec in enumerate(self._session_specs, start=1):
            results.append(self._run_one(spec, surface, manifest))
            self._progress = index / total
        self._results = tuple(results)
        return self._results

    def _run_one(
        self,
        spec: PluginSpec,
        surface: Any,
        manifest: Any,
    ) -> AlgorithmResultEnvelope:
        """运行一个插件；任何插件级异常都只影响这一条结果。"""
        available = manifest.ports
        if not all(item.port_id in available for item in spec.required_inputs):
            return self._incompatible_envelope(
                spec,
                "数据面缺少插件声明的必需端口",
            )

        try:
            resolution, resolution_status = resolve_inputs(spec, manifest)
        except Exception as exc:
            return self._failed_envelope(
                spec,
                detail=f"输入解析失败：{type(exc).__name__}",
            )
        if resolution_status == "INCOMPATIBLE":
            return self._incompatible_envelope(
                spec,
                "输入解析不兼容："
                + ", ".join(sorted(resolution.incompatible_required)),
            )
        if resolution_status != "OK":
            return self._failed_envelope(
                spec,
                detail=f"输入解析返回未知状态：{resolution_status}",
            )

        # ★ BLOCK-2 乙：C1 保留原始 InputResolution，只把它投影成
        # ResolutionView 交给 C3 的薄适配器；插件永远拿不到原始对象。
        resolved_surface = ResolvedSurface(surface, resolution.as_view())
        try:
            envelope = spec.entry(resolved_surface)
        except Exception as exc:
            return self._failed_envelope(
                spec,
                detail=f"{type(exc).__name__}: 算法执行失败",
            )

        invalid_reason = self._validate_result(spec, envelope, resolution)
        if invalid_reason is not None:
            return self._failed_envelope(
                spec,
                code=ErrorCode.ALGORITHM_RESULT_INVALID,
                detail=invalid_reason,
            )
        return envelope

    def _validate_result(
        self,
        spec: PluginSpec,
        envelope: Any,
        resolution: Any,
    ) -> str | None:
        """校验信封、BLOCK-2 乙 consumed_ports 与自描述 payload。"""
        if not isinstance(envelope, AlgorithmResultEnvelope):
            return f"返回类型不是 AlgorithmResultEnvelope：{type(envelope).__name__}"
        if envelope.algorithm_id != spec.algorithm_id:
            return "信封 algorithm_id 与注册表规格不一致"
        if envelope.algorithm_version != spec.algorithm_version:
            return "信封 algorithm_version 与注册表规格不一致"
        try:
            required = tuple(item.port_id for item in spec.required_inputs)
            if tuple(envelope.required_ports) != required:
                return "信封 required_ports 与注册表规格不一致"
        except (TypeError, AttributeError):
            return "信封 required_ports 不是有效端口序列"
        try:
            validate_result(envelope)
        except Exception as exc:
            return f"结果校验失败：{type(exc).__name__}"

        # ★ BLOCK-2 乙：consumed_ports ⊆ available，位置就在 C1 调用点。
        try:
            consumed = tuple(envelope.consumed_ports)
            if any(not isinstance(item, str) for item in consumed):
                return "consumed_ports 含非字符串端口"
            if not set(consumed) <= set(resolution.available):
                return "consumed_ports 含本次解析未提供的端口"
            if not set(consumed) <= set(required):
                return "consumed_ports 含插件未声明的端口"
        except (TypeError, AttributeError):
            return "consumed_ports 不是有效端口序列"

        # runtime 负责类型/单位/时间轴等纯自洽检查；这里补跨算法的 key 唯一性。
        try:
            seen: set[str] = set()
            for item in envelope.payload:
                key = getattr(item, "key", None)
                if not isinstance(key, str) or not key:
                    return "payload 含空或非字符串 key"
                if key in seen:
                    return f"payload key 重复：{key}"
                seen.add(key)
        except (TypeError, AttributeError):
            return "payload 不是可检查的序列"
        return None

    def _failed_envelope(
        self,
        spec: PluginSpec,
        *,
        code: ErrorCode | str = ErrorCode.ALGORITHM_FAILED,
        detail: str,
    ) -> AlgorithmResultEnvelope:
        """构造 C1 自己的 FAILED 信封，不把异常继续抛给调用者。"""
        return AlgorithmResultEnvelope(
            algorithm_id=spec.algorithm_id,
            algorithm_version=spec.algorithm_version,
            status="FAILED",
            required_ports=tuple(item.port_id for item in spec.required_inputs),
            consumed_ports=(),
            payload=(),
            error_code=self._code_text(code),
            error_detail=detail,
            elapsed_sec=None,
            coverage=None,
            warnings=(),
        )

    def _incompatible_envelope(
        self,
        spec: PluginSpec,
        detail: str,
    ) -> AlgorithmResultEnvelope:
        """构造 INCOMPATIBLE 信封，数据面和其它算法保持有效。"""
        return AlgorithmResultEnvelope(
            algorithm_id=spec.algorithm_id,
            algorithm_version=spec.algorithm_version,
            status="INCOMPATIBLE",
            required_ports=tuple(item.port_id for item in spec.required_inputs),
            consumed_ports=(),
            payload=(),
            error_code=ErrorCode.PLUGIN_INCOMPATIBLE.value,
            error_detail=detail,
            elapsed_sec=None,
            coverage=None,
            warnings=(),
        )

    # ── ③ 失败归一化 ──────────────────────────────────────────

    def normalize_error(self, exc: Exception) -> tuple[str, str]:
        """把受控异常归一化为不泄漏实现细节的开发者一句话。"""
        if isinstance(exc, CoreBuildError):
            return self._error_code_value(exc), "构建数据面失败"
        if isinstance(exc, ContractViolation):
            return self._error_code_value(exc), "调用违反契约"
        if isinstance(exc, AlgorithmError):
            return self._error_code_value(exc), "算法执行失败"
        # 普通异常若从插件边界冒到这里，按算法失败处理；堆栈不进入 UI。
        return ErrorCode.ALGORITHM_FAILED.value, "算法执行失败"

    # ── ④ 投影生成 ────────────────────────────────────────────

    def build_view(self, session_id: str) -> UiView:
        """把当前状态、结果和端口摘要投影成只读 UiView。"""
        sid = self._require_current_session(session_id)
        series, scalars, projection_error = self._project_results()
        port_summary: tuple[Any, ...] = ()
        view_error = self._error_code
        view_detail = self._error_detail
        if self._state is SessionState.DATA_READY:
            try:
                surface = self._core.acquire_surface(sid)
                port_summary = tuple(surface.manifest().ports.values())
            except Exception as exc:
                if view_error is None:
                    view_error = ErrorCode.INTERNAL_ERROR.value
                    view_detail = f"端口摘要不可用：{type(exc).__name__}"
        if projection_error is not None:
            if view_error is None:
                view_error = ErrorCode.ALGORITHM_RESULT_INVALID.value
                view_detail = projection_error
            else:
                view_detail = f"{view_detail}；{projection_error}"

        if self._state is SessionState.DATA_READY:
            progress: float | None = 1.0
        elif self._state in (
            SessionState.CREATED,
            SessionState.INPUT_READY,
            SessionState.BUILDING,
        ):
            progress = 0.0 if self._progress is None else self._progress
        else:
            progress = None

        return UiView(
            session_id=sid,
            state=self._state,
            series=tuple(series),
            scalars=tuple(scalars),
            progress=progress,
            port_summary=port_summary,
            error_code=view_error,
            error_detail=view_detail,
            note=self._note_for_state(),
        )

    def _project_results(
        self,
    ) -> tuple[list[UiSeries], list[UiScalar], str | None]:
        """把信封 payload 同构复制到投影，并做曲线下采样。"""
        projected_series: list[UiSeries] = []
        projected_scalars: list[UiScalar] = []
        projected_keys: set[str] = set()
        basis: TimelineBasis | None = None
        projection_error: str | None = None

        for envelope in self._results:
            if envelope.status not in ("OK", "DEGRADED"):
                # ★★ 失败信封必须【记账】，不能静默丢弃 ★★
                #
                # ★ 此前此处直接 continue，于是「三个算法全部 INCOMPATIBLE」
                # ★ 会投影出一份「scalars=[] series=[]」的干净视图 ——
                # ★ 外部看过去与「全部算成功但恰好没指标」完全无法区分，
                # ★ 而入口只判 state == DATA_READY，于是 rc=0 假绿成立。
                #
                # ★ 现在把它并进 projection_error，让 build_view 把它带到
                # ★ view.error_detail，入口据此非零退出。
                detail = f"{envelope.algorithm_id} 未产出（status={envelope.status}"
                if envelope.error_code is not None:
                    detail += f", error_code={envelope.error_code}"
                if envelope.error_detail:
                    detail += f", {envelope.error_detail}"
                detail += "）"
                projection_error = (
                    detail
                    if projection_error is None
                    else f"{projection_error}；{detail}"
                )
                continue
            for item in envelope.payload:
                if not isinstance(item, (UiScalar, UiSeries)):
                    projection_error = "结果 payload 含非投影对象"
                    continue
                key = f"{envelope.algorithm_id}.{item.key}"
                if key in projected_keys:
                    projection_error = f"投影 key 重复：{key}"
                    continue
                projected_keys.add(key)
                if isinstance(item, UiScalar):
                    projected_scalars.append(
                        UiScalar(
                            key=key,
                            label=item.label,
                            value=item.value,
                            unit=item.unit,
                            threshold=item.threshold,
                        )
                    )
                    continue

                item_basis = item.timeline_basis
                if not isinstance(item_basis, TimelineBasis):
                    projection_error = "曲线 timeline_basis 不属于契约枚举"
                    continue
                if basis is None:
                    basis = item_basis
                elif basis is not item_basis:
                    projection_error = "投影中出现不同 timeline_basis 的曲线"
                    continue
                t, values = self._downsample(item.t, item.values)
                projected_series.append(
                    UiSeries(
                        key=key,
                        label=item.label,
                        t=t,
                        values=values,
                        unit=item.unit,
                        timeline_basis=item_basis,
                        source_port=item.source_port,
                    )
                )
        return projected_series, projected_scalars, projection_error

    def _downsample(
        self,
        t: Sequence[float],
        values: Sequence[float],
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """在不使用第三方库的前提下均匀下采样到上限。"""
        count = len(t)
        if count != len(values):
            raise ValueError("UiSeries 的 t 与 values 长度不一致")
        if count <= MAX_PROJECTION_POINTS:
            return tuple(t), tuple(values)
        if count == 0:
            return (), ()
        last = count - 1
        indices = [
            int(round(index * last / (MAX_PROJECTION_POINTS - 1)))
            for index in range(MAX_PROJECTION_POINTS)
        ]
        return (
            tuple(t[index] for index in indices),
            tuple(values[index] for index in indices),
        )

    def _note_for_state(self) -> str:
        if self._state is SessionState.DATA_READY:
            return "数据面已就绪，可运行算法"
        if self._state is SessionState.FAILED:
            return "数据面构建或运行失败"
        if self._state is SessionState.CLOSED:
            return "会话已关闭"
        return "会话正在推进"

    # ── ⑤ UiProjectionPort（C4 的唯一入口）────────────────────

    def snapshot(self) -> UiView:
        """取当前投影快照；只读，不推进状态或触发计算。"""
        if self._session_id is None:
            return UiView(
                session_id="",
                state=SessionState.CREATED,
                progress=0.0,
                note="尚未创建会话",
            )
        return self.build_view(self._session_id)

    def submit(self, command: UiCommand) -> None:
        """校验并执行一条界面意图；非法命令不得改变状态。"""
        if not isinstance(command, UiCommand):
            raise self._violation("命令必须是 UiCommand")
        kind = command.kind
        legal_states = COMMAND_LEGALITY.get(kind)
        if legal_states is None or self._state not in legal_states:
            raise self._violation(
                f"命令 {getattr(kind, 'value', kind)} 在当前状态 {self._state.value} 非法"
            )
        payload = command.payload
        expected_keys = UI_PAYLOAD_KEYS[kind]
        if not isinstance(payload, dict) or set(payload) != set(expected_keys):
            raise self._violation("命令载荷键名或数量不符合契约")
        if "path" in expected_keys and not isinstance(payload["path"], str):
            raise self._violation("路径载荷必须是字符串")

        if kind is UiCommandKind.SET_REFERENCE:
            self.set_reference(self._require_session(), payload["path"])
        elif kind is UiCommandKind.SET_PRACTICE:
            self.set_practice(self._require_session(), payload["path"])
        elif kind is UiCommandKind.BUILD_SURFACE:
            self.build_surface(self._require_session())
        elif kind is UiCommandKind.RUN_ALGORITHMS:
            self.run_algorithms(self._require_session())
        elif kind is UiCommandKind.CANCEL:
            if self._state is SessionState.BUILDING:
                # 同步 C2 没有取消检查点；只记录，不打断构建。
                self._cancel_after_build = True
            # INPUT_READY 与 DATA_READY 的 CANCEL 是幂等空操作。
        elif kind is UiCommandKind.RESET:
            self._reset_session()

    def _reset_session(self) -> None:
        """按契约清理输入和数据面，再建立可继续登记的 CREATED 会话。"""
        old_sid = self._session_id
        if old_sid is None:
            self._state = SessionState.CREATED
            return
        profile_version = self._profile_version
        if profile_version is None:
            raise self._violation("当前会话没有 profile_version", old_sid)
        self._core.destroy_session(old_sid)
        new_sid = self._core.create_session(profile_version)
        self._session_id = new_sid
        self._profile_version = profile_version
        self._state = self._core.status(new_sid)
        self._session_specs = (
            tuple(self._registry.list()) if self._registry is not None else ()
        )
        self._algorithm_count = len(self._session_specs)
        self._results = ()
        self._progress = 0.0
        self._error_code = None
        self._error_detail = None
        self._cancel_after_build = False

    # ── 小型契约辅助 ──────────────────────────────────────────

    def _require_session(self) -> str:
        if self._session_id is None:
            raise self._violation("尚未创建会话")
        return self._session_id

    def _require_current_session(self, session_id: str) -> str:
        current = self._require_session()
        if session_id != current:
            raise self._violation("session_id 不是 C1 当前会话", current)
        return current

    @staticmethod
    def _code_text(code: ErrorCode | str) -> str:
        return code.value if isinstance(code, ErrorCode) else str(code)

    @staticmethod
    def _error_code_value(exc: HarmonicaError) -> str:
        code = getattr(exc, "code", ErrorCode.INTERNAL_ERROR)
        return code.value if isinstance(code, ErrorCode) else str(code)

    @staticmethod
    def _violation(
        detail: str,
        session_id: str | None = None,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
    ) -> ContractViolation:
        return ContractViolation(
            code=code,
            detail=detail,
            session_id=session_id,
            component="COMP-C1",
        )


def build_default_app() -> HostApp:
    """装配默认配置的应用，供 __main__.py 与 cockpit 使用。

    物理算法装配根是 `algorithms/bootstrap.py`；本函数只取它产出的
    Registry，Host 自身不 import pitch/timing/dynamics。
    """
    from ..algorithms.bootstrap import build_default_registry
    from ..core.api import HostCore

    return HostApp(core=HostCore(), registry=build_default_registry())
