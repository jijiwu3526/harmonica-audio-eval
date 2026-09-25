'''
FILE-ID:      FILE-205
COMPONENT:    COMP-C3 Algorithm
SPEC:         SPEC.md@v2.1 · contract.InputRequirement · contract.PluginSpec
              · contract.AlgorithmResultEnvelope · SHELL-STANDARD v1

ROLE:
    执行期输入解析与结果校验；只回答插件能否使用当前数据面、结果是否诚实。

INTENT:
    把「少算却报 OK」「读了未获准的端口」「在错误时间轴上计算」
    这三类通常不会报错、只会静默算错的错误挡在运行边界之外。
    不把这些规则塞进 contract.py，是因为它们描述执行期产物，不是跨组件契约。

MUST:
    - 逐条检查 PluginSpec.required_inputs 的端口、schema、时间轴、dtype、字段与采样率
    - 任一 required 不满足时返回 INCOMPATIBLE，并明确标记失败项
    - 全部 required 满足时记录 available 与 missing_optional
    - ★ 通过 ResolutionView 把本次解析事实挂到 ResolvedSurface，交给单参 entry
    - validate_result 校验四值状态、单位、UiSeries 形状、时间轴、coverage 与 error_code
    - ★ DEGRADED 必须伴随 coverage 或 warnings 中至少一项可观察证据

MUST NOT:
    - import core / host / cockpit
    - 因 optional 或 required 缺失而请求 Core 生成端口
    - 把 schema_version 当作逐端口语义版本
    - 把 PortDescriptor.sample_rate == 0 误判成数据缺失
    - 把 DEGRADED 无证据时把它当成 OK 接受
    - 把 InputResolution 暴露为**插件**控制输入（只经 ResolutionView；
      ★ 负责人 BLOCK-2 裁定方案乙：C1 在调用点可见 InputResolution，
      插件仍不可见 —— 两者权限不同，见 resolve_inputs 的详细契约）
    - 让 C2 Surface 持有或实现解析状态

INPUT:
    resolve_inputs：PluginSpec 与已 Seal 的 SurfaceManifest。
    validate_result：AlgorithmResultEnvelope。

OUTPUT:
    InputResolution —— 本文件的私有 dataclass；**对 C1 可见**（BLOCK-2 乙），
    经 as_view() 投影后才对插件可见。
    ResolvedSurface —— C3 薄适配器，组合 C2 Surface 与 ResolutionView。
    resolve_inputs 返回 (InputResolution, str)；validate_result 成功返回 None，
    失败抛 ValueError。

BUILD-INSTRUCTION:
    .spec/build/FILE-205-v1.md
'''

from __future__ import annotations

import math
from dataclasses import dataclass

from ..contract import (
    UNITS_VOCABULARY,
    AlgorithmResultEnvelope,
    ErrorCode,
    InputRequirement,
    PluginSpec,
    SurfaceManifest,
    UiScalar,
    UiSeries,
    AlgorithmDataContract,
    BufferView,
    ResolutionView,
)


# ═════════════════════════════════════════════════════════════════════
# 冻结的校验常量（FILE-205 §5.3 第 1 / 7 项）
# ═════════════════════════════════════════════════════════════════════

_LEGAL_STATUS = frozenset({'OK', 'DEGRADED', 'INCOMPATIBLE', 'FAILED'})
"""信封允许的四态。未知状态会让调用方按错误分支解释结果。"""

_STATUS_ERROR_CODES = {
    'INCOMPATIBLE': frozenset({ErrorCode.PLUGIN_INCOMPATIBLE}),
    'FAILED': frozenset({
        ErrorCode.ALGORITHM_FAILED,
        ErrorCode.ALGORITHM_TIMEOUT,
        ErrorCode.ALGORITHM_RESULT_INVALID,
    }),
}
"""失败态的合法错误码集合。

★ 只列插件结果码。C2 / 环境 / 界面类错误码
（INPUT_UNREADABLE / CORE_BUILD_FAILED / COCKPIT_DETACHED 等）
不属于插件结果，故不在此表内。
"""


@dataclass(frozen=True)
class InputResolution:
    """一次运行期输入解析的事实记录。

    为什么留在本文件而不进 contract.py：它描述的是某次插件运行对某份
    manifest 的解析结果，不是调用双方预先约定的跨组件接口。
    放进契约层会把执行期产物误写成稳定公共词汇。

    ★ available / missing_optional 都按 port_id 记账。
    不设置布尔字段，因为「任一 required 不满足」已由 status 表达，
    再放一个容易与失败项分叉的布尔量会制造第二份事实。
    `as_view()` 是 runtime 内部的投影入口：原始 `InputResolution` 不出
    runtime，只有 `ResolutionView` 抵达插件的 `AlgorithmDataContract`。
    """

    available: frozenset[str]
    """全部通过检查的 required 与 optional 端口 id。"""

    missing_optional: frozenset[str]
    """声明了但未通过检查的 optional 端口 id；不阻止插件运行。"""

    incompatible_required: frozenset[str]
    """未通过检查的 required 端口 id；非空必须判 INCOMPATIBLE。"""

    def as_view(self) -> ResolutionView:
        """产生供插件读取的不可变视图；不暴露 `InputResolution` 本身。

        ★ 实现（FILE-205 §4，2026-09-24 授权注入）。
          只搬运 `available` 与 `missing_optional` 两个只读事实；
          ★ `incompatible_required` **刻意不投影** —— 端口不可用时
          status 已是 INCOMPATIBLE、插件入口根本不会被调用，
          把失败项交给插件只会诱导它去解释一个不该解释的状态。
        """
        return ResolutionView(
            available=self.available,
            missing_optional=self.missing_optional,
        )


@dataclass(frozen=True)
class ResolvedSurface:
    """C3 的薄适配器：组合 C2 数据面与本次解析的只读视图。

    ★ 组合而非修改：C2 的 `Surface` 不需要认识解析事实，也不被写入。
    适配器只把 `manifest()` / `read()` 委托给原对象，并把
    `ResolutionView` 作为只读状态交给单参 `PluginSpec.entry`。

    ★ 实现（FILE-205 §5.1，2026-09-24 授权注入）。
      本类共 3 个成员：`manifest()` / `read()` 两个委托方法
      与 `resolution` 这个只读属性。三者都不持有解析状态之外的可变数据，
      也不修改被委托的 C2 数据面。
    """

    _surface: AlgorithmDataContract
    _resolution: ResolutionView

    def manifest(self) -> SurfaceManifest:
        """委托 C2 数据面返回 manifest；不改变解析事实。"""
        return self._surface.manifest()

    def read(
        self,
        port_id: str,
        time_range: tuple[float, float] | None = None,
    ) -> BufferView:
        """委托 C2 数据面读取端口；不改变解析事实。"""
        return self._surface.read(port_id, time_range)

    @property
    def resolution(self) -> ResolutionView:
        """返回只读解析视图；属性本身不可替换，视图也不可变。"""
        return self._resolution


def resolve_inputs(
    spec: PluginSpec,
    manifest: SurfaceManifest,
) -> tuple[InputResolution, str]:
    """解析插件输入，返回 (InputResolution, status)。

    每条 required_inputs / optional_inputs 的 InputRequirement 都必须通过
    以下六项机械检查；缺一即该端口不可用：

    1. 端口存在：req.port_id in manifest.ports。
       防的是：读取不存在的端口会失败，或错误插件被误判为兼容。

    2. schema：req.schema_version in ('*', desc.schema_version)。
       防的是：要求另一 profile/schema 时仍取数，导致布局或语义漂移。
       ★ 当前 12 个端口的 schema_version 全部是 'CORE_PROFILE_V0.1'，
       实际承载的是 profile 版本，不是逐端口语义版本；默认必须写 '*'，
       不得依赖它做细粒度判断，细粒度判断走 field_names / dimensions /
       element_type。

    3. 时间轴：req.timeline_basis is None or == desc.timeline_basis。
       防的是：在 WARPED 归一化轴上计算节奏，把抢拍拖拍静默抹成 0。

    4. dtype：req.element_type is None or == desc.element_type。
       防的是：插件按错误 dtype 解释字节，得到看似正常的错误数值。

    5. 字段：set(req.required_fields) <= set(desc.field_names)。
       防的是：列名已变而插件仍按旧位置取 f0_hz/voiced，静默错列。

    6. 采样率：req.sample_rate is None or desc.sample_rate == req.sample_rate。
       防的是：跨采样率混用音高等结果，把结果成因丢掉。
       ★ PortDescriptor.sample_rate == 0 合法；实测 warp_path、
       chroma.*、notes.* 都是 0，含义是「与采样率无关」，不是缺数据。
       因此这些端口可正常 required/optional，但 req.sample_rate=0
       非法，禁止把它当「要求采样率为 0」。

    任一 required 不满足 → status='INCOMPATIBLE'，incompatible_required
    标出具体端口；此时插件入口不应调用。全部 required 满足 → status='OK'，
    即使 optional 全部缺失也可运行；available 记录实际可用端口，
    missing_optional 记录声明但未取得的 optional 端口。

    ★ 负责人 BLOCK-2 裁定（方案乙）—— `InputResolution` **暴露给 C1**：
      本函数是唯一产出它的位置，C1（Host）在调用点拿它做
      `consumed_ports ⊆ available` 的机械比对，runtime **不**代做这一步。

    ★★ 但「暴露给 C1」**不等于**「暴露给插件」。两层权限严格不同：
        C1（Host）      → 拿 `InputResolution`（本函数的返回值），
                          用途只有一个：校验信封声明的 consumed_ports
                          是否都在本次实际可用的端口里。
        插件（算法）    → **只**拿 `AlgorithmDataContract` 视图，
                          经 `InputResolution.as_view()` 产生
                          `ResolutionView`，再用 `ResolvedSurface`
                          组合 C2 数据面交给单参 entry。
                          插件拿不到、也不需要 `InputResolution` 本身。

    ★ 这样分工的理由：consumed_ports 是**结果信封**里的字段（contract.py
    的 AlgorithmResultEnvelope），而"本次实际可用哪些端口"是**执行期事实**。
    两者只有同时持有才能比对 —— 信封在 C1 手里，解析事实也必须在 C1 手里。
    runtime 若代做比对，就得接收信封参数，签名从「纯解析」变成「解析+校验"，
    职责变胖且无法单独复用。

    ★ 实现（FILE-205 §5.2，2026-09-24 授权注入）。

    ★ `manifest.ports` 是 `Mapping[str, PortDescriptor]`（按 port_id 索引），
      所以「端口存在」就是一次键查询，不需要遍历。
    """
    ports = manifest.ports

    def passes(req: InputRequirement) -> bool:
        """六项机械检查（FILE-205 §5.2 第 1–6 项），任一不过即不可用。"""
        desc = ports.get(req.port_id)
        if desc is None:
            return False
        # 2. schema：要求具体版本时必须匹配；'*' 表示不约束。
        if req.schema_version not in ('*', desc.schema_version):
            return False
        # 3. 时间轴：None 表示不约束；不一致会让归一化轴抹掉真实时间差。
        if req.timeline_basis is not None and req.timeline_basis != desc.timeline_basis:
            return False
        # 4. dtype：按错误 dtype 解释字节会得到看似正常的错值。
        if req.element_type is not None and req.element_type != desc.element_type:
            return False
        # 5. 字段：列名已变而插件仍按旧位置取数，会静默错列。
        if not set(req.required_fields) <= set(desc.field_names):
            return False
        # 6. 采样率：R6 对 None 放行，对非 None 做【精确匹配】。
        # ★ 规格 FILE-205:200-201 明确「插件不得写 req.sample_rate=0 来表示
        # 『要求采样率为 0』」。所以 req=0 不是「不约束」，而是一个必然不匹配的
        # 非 None 值 —— 精确匹配会让它被判不可用，正是该行为。
        # ★ 描述符那侧的 0（warp_path / chroma / notes 等与采样率无关的端口）
        #   仍正常通过：那里是 req=None，或 req 与 desc 同为 0。
        if req.sample_rate is not None and desc.sample_rate != req.sample_rate:
            return False
        return True

    required = tuple(spec.required_inputs)
    optional = tuple(spec.optional_inputs)

    incompatible = frozenset(r.port_id for r in required if not passes(r))
    ok_optional = frozenset(r.port_id for r in optional if passes(r))
    missing_opt = frozenset(r.port_id for r in optional if r.port_id not in ok_optional)
    ok_required = frozenset(r.port_id for r in required if r.port_id not in incompatible)

    resolution = InputResolution(
        available=ok_required | ok_optional,
        missing_optional=missing_opt,
        incompatible_required=incompatible,
    )
    # 任一 required 不可用即整体不兼容；optional 全缺仍可运行。
    status = 'INCOMPATIBLE' if incompatible else 'OK'
    return resolution, status


def validate_result(result: AlgorithmResultEnvelope) -> None:
    """校验插件返回的 AlgorithmResultEnvelope；成功返回 None，失败抛 ValueError。

    至少机械校验以下纯自洽不变量，任一失败都抛 ValueError，detail 指明
    字段与实际值：

    1. result.status 属于 ('OK', 'DEGRADED', 'INCOMPATIBLE', 'FAILED')。
       防的是未知状态绕过故障分类，让调用方按错误分支解释结果。

    2. payload 的每个元素都是 UiScalar 或 UiSeries，且每个元素的 unit
       属于 contract.UNITS_VOCABULARY。
       防的是插件塞入裸对象、未知单位或拼错单位；下游按词表解释数字时会
       静默错配，界面即使能画出来也无法说明这个数字是什么。

    3. 每个 UiSeries 满足 len(t) == len(values)。
       防的是时间点与数值错位：绘图可能仍成功，但一个值会落到错误时刻。

    4. 每个 UiSeries 必须显式携带 timeline_basis。
       防的是把 REFERENCE 与 WARPED 曲线混画；归一化轴会把抢拍拖拍显示成
       对齐，令使用者得出与真实演奏时间相反的判断。

    5. coverage 若非 None，必须是 0.0–1.0（含端点）的有限数。
       防的是负数或大于 1 的值冒充覆盖率，或 NaN/无穷大污染结果可信度。

    6. ★ status == 'DEGRADED' 时，coverage 非 None 或 warnings 非空，
       至少一项成立；否则就是「偷偷少算」，必须拒绝，绝不允许伪装成
       完整 OK。missing_optional 的证据由 C1 持有，C1 负责把 optional
       缺失且插件未显式说明的情况拒绝或补警；纯结果校验只要求信封内
       自带可观察证据。

    7. status ∈ ('INCOMPATIBLE', 'FAILED') 时 error_code 不得为 None，
       且必须属于该状态的合法 ErrorCode：INCOMPATIBLE 对应
       PLUGIN_INCOMPATIBLE；FAILED 对应 ALGORITHM_FAILED /
       ALGORITHM_TIMEOUT / ALGORITHM_RESULT_INVALID。
       防的是失败没有可归一化原因，或自由字符串让 C1 只能猜，且无法
       区分不兼容、执行失败与非法结果。

    8. status ∈ ('OK', 'DEGRADED') 时 error_code 必须为 None。
       防的是成功或明确降级仍携带错误码，使状态与证据互相矛盾；DEGRADED
       是已解释的部分能力，不是失败。

    ★ 上述错误码检查按 ErrorCode 枚举裁定进行，因此不列举 INPUT_UNREADABLE /
    INPUT_TOO_SHORT / INPUT_SILENT / INPUT_TOO_LONG / CORE_BUILD_FAILED /
    ALIGNMENT_UNRECOVERABLE / COCKPIT_DETACHED / INTERNAL_ERROR 作为插件结果码：
    它们属于 C2、环境或界面，不是插件结果。contract.py 的现有说明还保留一处
    「DEGRADED / OK → error_code is None」的旧括号，★ 原文括号漏了分号，语义即
    DEGRADED 与 OK 均要求 error_code 为 None；本文件按未加括号的四项列举执行。

    ★ 负责人 BLOCK-2 裁定（方案乙）—— 解析事实在 C1 手里，runtime 不代做比对：
      `InputResolution` 是本文件的私有 dataclass，但**对 C1 可见**：
      `resolve_inputs` 返回它，C1 在调用点用它比对
      `consumed_ports ⊆ available`（consumed_ports 来自信封，见 contract.py
      的 AlgorithmResultEnvelope；available 来自 InputResolution）。
      ★ 两者必须同时在 C1 手里才能比 —— 这就是乙方案把 resolution
      交给 C1 的全部理由。

      插件侧不受影响：插件只拿 `ResolvedSurface`（含 `ResolutionView` 视图），
      拿不到 `InputResolution` 本身。运行时若发现某个插件读了不存在的端口，
      那是插件 bug，不在 validate_result 的职责内。

    ★ 上述口径与 `validate_result` 的分工不冲突，因为两者管的是不同事实：
        validate_result  只管「信封自身是否自洽」（不看任何外部状态）
        C1 在调用点      管「信封声称消费的端口是否真的可用」
    ★ validate_result **不接收** resolution / manifest，因此它的签名无需变更。

    ★ ErrorCode 已被导入，供上述状态/错误码对应关系使用；不得新增任何
    自由字符串错误码。validate_result 永不读取端口、manifest 或外部状态。

    ★ 实现（FILE-205 §5.3，2026-09-24 授权注入）。
    """
    # 1. 状态必须属于四个合法值。
    if result.status not in _LEGAL_STATUS:
        raise ValueError(f'status 非法：{result.status!r}，合法值 {sorted(_LEGAL_STATUS)}')

    # 2. payload 元素类型 + 单位词表。★ 单位不在词表内必须拒绝 ——
    #    这是「毫秒 vs 秒」单位冲突的守门：拼错单位会让界面把数字画出来却说不清是什么。
    for item in result.payload:
        if not isinstance(item, (UiScalar, UiSeries)):
            raise ValueError(f'payload 含非 UiScalar/UiSeries 元素：{type(item).__name__}')
        if item.unit not in UNITS_VOCABULARY:
            raise ValueError(f'payload[{item.key}] 单位不在词表：{item.unit!r}')

    # 3. 曲线时间点与数值必须等长，否则一个值会落到错误时刻。
    for item in result.payload:
        if isinstance(item, UiSeries) and len(item.t) != len(item.values):
            raise ValueError(
                f'UiSeries[{item.key}] t/values 长度不等：{len(item.t)} vs {len(item.values)}')

    # 4. 曲线必须显式声明时间轴，禁止 REFERENCE 与 WARPED 混画。
    for item in result.payload:
        if isinstance(item, UiSeries) and item.timeline_basis is None:
            raise ValueError(f'UiSeries[{item.key}] 缺 timeline_basis')

    # 5. coverage 若给出，必须是 0.0–1.0 的有限数（NaN/inf 会污染可信度）。
    if result.coverage is not None:
        if not math.isfinite(result.coverage) or not (0.0 <= result.coverage <= 1.0):
            raise ValueError(f'coverage 越界或非有限：{result.coverage!r}')

    # 6. DEGRADED 必须自带可观察证据，否则就是「偷偷少算」伪装成完整。
    if result.status == 'DEGRADED':
        if not result.warnings and result.coverage is None:
            raise ValueError('status=DEGRADED 但 coverage 为 None 且 warnings 为空')

    # 7. 失败态必须带该状态对应的合法 ErrorCode。
    if result.status in ('INCOMPATIBLE', 'FAILED'):
        if result.error_code is None:
            raise ValueError(f'status={result.status} 但 error_code 为 None')
        if result.error_code not in _STATUS_ERROR_CODES[result.status]:
            raise ValueError(
                f'status={result.status} 与 error_code={result.error_code.name} 不匹配')
    # 8. 成功或明确降级不得携带错误码，否则状态与证据互相矛盾。
    elif result.error_code is not None:
        raise ValueError(f'status={result.status} 不应携带 error_code={result.error_code.name}')


__all__ = [
    "InputResolution",
    "ResolutionView",
    "ResolvedSurface",
    "resolve_inputs",
    "validate_result",
]
