# FILE-205 — `harmonica_eval/algorithms/runtime.py`

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/algorithms/runtime.py`
> 生成依据：
> - `harmonica_eval/algorithms/runtime.py`@v1（246 行冻结空壳，含现场铭牌、私有 `InputResolution`、`ResolvedSurface` 组合适配器与两空函数）
> - `harmonica_eval/contract.py` 的 `InputRequirement`、`PluginSpec`、`SurfaceManifest`、
>   `AlgorithmResultEnvelope`、`ErrorCode`、`UiScalar`、`UiSeries`、`UNITS_VOCABULARY`、
>   `AlgorithmDataContract`、`BufferView`、`ResolutionView`
> - `harmonica_eval/host/app.py` 的 `run_algorithms` / 结果校验调用边界
> - `COMPONENTS.md`@v2 §3 COMP-C3
> - SHELL-STANDARD v1
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-205 |
| 所属组件 | COMP-C3 Algorithm |
| 层级 | L3（symbol / implementation） |
| 上游 | C1 `harmonica_eval.host.app.HostApp`（当前仍为 SHELL）是运行期编排者；它当前并未实现任何 Surface 包装或解析调用。`runtime.py` 的组件结构冻结为 `InputResolution` → `as_view()` → `ResolvedSurface`；C1 要使用该结构时再接线。插件返回 `AlgorithmResultEnvelope` 后也仍待 C1 接线调用 `validate_result`；源码边界：`harmonica_eval/host/app.py:182-196`、`harmonica_eval/algorithms/runtime.py:65-131` |
| 下游 | `harmonica_eval.contract` 的输入/结果/只读视图类型；原始 `InputResolution` 仅在 runtime 私有边界内使用，不进 `contract.py`、不由 C1 或插件持有；抵达插件的是 `ResolvedSurface.resolution -> ResolutionView`（`harmonica_eval/algorithms/runtime.py:73-89`、`harmonica_eval/contract.py:390-413`） |
| 同层邻居 | `harmonica_eval/algorithms/registry.py`（装配期登记）、`__init__.py`（类型出口）、具体算法模块（不由本文件调用） |

**你的权限**：只处理本文件 `harmonica_eval/algorithms/runtime.py` 中的冻结空壳：`InputResolution.as_view`、`ResolvedSurface.manifest/read/resolution`、`resolve_inputs` 与 `validate_result`。
**本轮没有任何实现注入授权**（见 `.spec/OWNER-DIRECTIVES.md` 指令 2）；
上述五个方法当前全部保持 SHELL（`harmonica_eval/algorithms/runtime.py:89-96,116-131,134-178,181-237`）。
不得修改 `contract.py`、`profile.py`、`host/`、`core/`、`cockpit/`、具体算法模块或其他 `.py`；
不得修改壳件铭牌、docstring、签名、`InputResolution` / `ResolvedSurface` 的冻结定义或 `__all__`。

C1 是唯一把本文件的输入解析产物与结果校验串进一次会话的编排者；本文件不读取
`PluginSpec.entry`，不运行插件，不访问文件系统、网络或平台 API。

---

## 2 · 这个文件为什么存在

追溯：Product Intent「双音频对比 → 客观数值指标」；架构承诺「换算法不改核心」。

本文件把运行边界上最容易被静默忽略的错误挡在外面：端口是否存在、声明的 schema /
时间轴 / dtype / 字段 / 采样率是否匹配，以及插件返回的信封是否自洽。
它描述的是**执行期检查**，不是一份新的跨组件公共契约。

**删掉它会坏掉什么**（逐条列出）：

1. 插件可以在端口不存在或类型不符时继续运行，错误延迟到数值结果甚至报告中才暴露。
2. `DEGRADED` 可以没有 coverage 或 warnings，空壳式“少算却报 OK”无法机械拦截。
3. `UiSeries` 的时间点与数值可以错位，或缺少 `timeline_basis`，界面会把归一化轴误画成真实时间。
4. C1 若把原始 `InputResolution` 直接传给插件，插件就可能依赖并误以为 C1 把 `incompatible_required` 等执行期控制事实也授权给它；只读 `ResolutionView` 才能把“可用 / 缺 optional”与 runtime 私有记录隔开（`harmonica_eval/algorithms/runtime.py:73-89`、`harmonica_eval/contract.py:390-413`）。
5. 校验器会被迫把执行期控制信息塞进结果信封，破坏「结果只描述结果」的证据边界。

★ **执行期产物不进入 contract.py**：`InputResolution` 只记录某次 `PluginSpec` 对某份
manifest 的解析事实，3 个字段均留在 runtime 私有类型中（`harmonica_eval/algorithms/runtime.py:65-89`）。
把它放进契约层会把一次运行的状态误写成所有调用方预先约定的公共词汇。因此本文件私有定义它；
契约层不定义、不 re-export，**原始 `InputResolution` 不出 runtime 边界。**
插件抵达的是 contract 层的 frozen `ResolutionView`（字段仅 `available` / `missing_optional`，
查询仅 `is_available`；`harmonica_eval/contract.py:390-413`），由 runtime 私有 `InputResolution.as_view()`
投影、再挂到 `ResolvedSurface.resolution`（`harmonica_eval/algorithms/runtime.py:89-96,128-131`）。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import（穷举，清单外一律禁止）**：

- Python 标准库：`from __future__ import annotations`；`dataclasses`（只用 `dataclass`）。
- 第三方：**无**。
- 本包内：`from ..contract import` 以下 11 个符号，恰好为：
  `UNITS_VOCABULARY`、`AlgorithmResultEnvelope`、`ErrorCode`、`InputRequirement`、
  `PluginSpec`、`SurfaceManifest`、`UiScalar`、`UiSeries`、`AlgorithmDataContract`、
  `BufferView`、`ResolutionView`（源码：`harmonica_eval/algorithms/runtime.py:50-62`）。
- `InputResolution` 只能在本文件定义；不得从 `..contract` 或其它模块导入。
- 公开出口 `__all__ = ["InputResolution", "ResolutionView", "ResolvedSurface", "resolve_inputs", "validate_result"]` 不得增删（源码：`harmonica_eval/algorithms/runtime.py:240-246`）。其中 `ResolutionView` 是对 contract 类型的稳定 re-export，不是新的契约定义。

**禁止 import**：

- `harmonica_eval.core`、`harmonica_eval.host`、`harmonica_eval.cockpit` 的任何模块或相对路径。
- 具体算法模块 `.pitch`、`.timing`、`.dynamics`；本文件不运行插件。
- `harmonica_eval.profile`、任何第三方包、`importlib`、文件 I/O、网络、日志、平台模块。
- `numpy` 及其它数组库：六项检查读取的是 `SurfaceManifest` 的描述符，不需要重算信号。
- 任何清单外模块。需要新依赖 → 停止并转 §10。

**依赖方向的原因**：C3 运行时只依赖跨组件契约；直接 import Core / Host / Cockpit
会使插件反向知道调用方实现，破坏组件边界与可替换性。

---

## 4 · 你要实现什么（行为规格）

### 4.0 壳件中已存在的冻结内容

壳件已写定并**冻结**：

- 模块 docstring 全部现场铭牌、边界文字与裁定；
- 两条 import 声明与 5 项 `__all__`；
- `@dataclass(frozen=True) class InputResolution` 及其 3 个字段、字段顺序、注解和 docstring；
- `InputResolution.as_view() -> ResolutionView`；
- `@dataclass(frozen=True) class ResolvedSurface` 及其 `_surface: AlgorithmDataContract` / `_resolution: ResolutionView` 两字段；
- `ResolvedSurface.manifest() -> SurfaceManifest`、`read(...) -> BufferView`、`resolution -> ResolutionView`；
- `resolve_inputs(spec: PluginSpec, manifest: SurfaceManifest) -> tuple[InputResolution, str]`；
- `validate_result(result: AlgorithmResultEnvelope) -> None`；
- 上述方法的完整详细契约 docstring。

**★ 当前状态：负责人已于 2026-09-24 授权注入（第 3 刀），六个冻结方法均已实现。**
`as_view()` / `ResolvedSurface.manifest()` / `ResolvedSurface.read()` / `ResolvedSurface.resolution` /
`resolve_inputs()` / `validate_result()` 现为真实实现，§8.2 已相应改写为**行为验收**
（原「未注入应抛 NotImplementedError」判据是空壳期条件，注入后不再适用）。
冻结形状不变：不得把 `InputResolution` 移入 `contract.py`、改名、加字段、改 frozen 状态
或改变模块归属。`ResolvedSurface` 四方法仍在 `harmonica_eval/algorithms/runtime.py` 同一文件内。

### 4.1 `InputResolution`（本文件私有，冻结形状）

- **定义位置**：必须在 `runtime.py` 内以 `@dataclass(frozen=True)` 定义。
- **字段顺序与注解**：`available: frozenset[str]`、`missing_optional: frozenset[str]`、
  `incompatible_required: frozenset[str]`；不得增删、换序或改注解。
- **语义**：
  - `available`：通过检查的 required 与 optional 端口 id。
  - `missing_optional`：声明了但未通过检查的 optional 端口 id；不阻止运行。
  - `incompatible_required`：未通过检查的 required 端口 id；非空即 INCOMPATIBLE。
- **status 关系**：状态由 `resolve_inputs` 的第二返回值表达；不得新增布尔字段制造第二份事实。
- **不在契约层**：不得在 `harmonica_eval/contract.py` 定义、导入、导出或 re-export
  `InputResolution`。`contract.py` 的文档字符串提及该名称，是为了说明“它住在 runtime、刻意不进契约层”，
  这不是定义或导出；结构验收按 AST 与 `__all__` 判定，不按整份文件文本 grep。
- **可观察性**：它是 C1 调用点拿到可用端口、缺失 optional 与不兼容 required 的唯一事实载体；
  不得用隐式全局状态替代它。字段 3 个，**`incompatible_required` 仍在**；本轮没有删除或改名。
- **插件边界**：原始 `InputResolution` 不出 runtime。只有 `as_view()` 生成的 `ResolutionView`
  抵达插件，且视图**没有** `incompatible_required` 字段（`harmonica_eval/contract.py:390-413`）。
  C1 仍可在调用点同时持有原始对象，用其 `available` 检查 `consumed_ports ⊆ available`。
- **`as_view()` 当前为空壳**：只冻结“把 `available` / `missing_optional` 投影成 frozen
  `ResolutionView`”的边界，不包含任何返回构造或转换逻辑；源码仍是
  `raise NotImplementedError("SHELL: FILE-205 待注入实现")`（`harmonica_eval/algorithms/runtime.py:89-96`）。

### 4.2 `ResolvedSurface`（C3 组合适配器，冻结形状；四个方法当前均为 SHELL）

- **定义与字段**：`@dataclass(frozen=True)`；字段顺序固定为
  `_surface: AlgorithmDataContract`、`_resolution: ResolutionView`；不得增删、换序或改名
  （`harmonica_eval/algorithms/runtime.py:99-114`）。
- **组合而非修改 C2**：`_surface` 是已 Seal 的 C2 数据面句柄，`_resolution` 是本次解析视图。
  适配器不得把解析状态写回 `_surface`；C2 `core/surface.py::Surface` 当前也没有 `resolution`
  属性（`harmonica_eval/core/surface.py:112-144`）。
- **四个方法当前均为空壳**：
  - `manifest()`：计划委托 `_surface.manifest()`，当前抛 SHELL（`runtime.py:116-118`）；
  - `read()`：计划委托 `_surface.read()`，当前抛 SHELL（`runtime.py:120-126`）；
  - `resolution`：`@property`，计划返回 `_resolution`，当前抛 SHELL（`runtime.py:128-131`）；
  - `as_view()`：虽不是本类方法，但属于同一条投影链，当前同样抛 SHELL（`runtime.py:89-96`）。
  **负责人已撤回实现，未授权注入；本文件不得声称这些委托已经工作。**
- **装配序列自洽性（目标形状，不是现状）**：C1 取 C2 Surface → runtime `resolve_inputs` 得到
  原始 `InputResolution` → `resolution.as_view()` 得 `ResolutionView` → 构造
  `ResolvedSurface(surface, view)` → 单参 `PluginSpec.entry(resolved_surface)`。插件只读
  `resolved_surface.resolution`，原始 `InputResolution` 不出 runtime。
- **装配接线状态**：`ResolvedSurface` 负责包裹 C2 Surface，但 C1 当前 `run_algorithms` 仍为 SHELL，
  没有这条构造序列的实现证据（`harmonica_eval/host/app.py:182-196`）。
  - ★ **Registry 的物理装配根已裁定**：`algorithms/bootstrap.py`（`GC-204-08` CLOSED，方案甲，
    2026-09-24；台账 `.spec/GATE-CHALLENGES-C3.md:544`）。
  - ★ **C1 与本文件的职责已裁定（BLOCK-2 方案乙，2026-09-24）**：C1 拿 `InputResolution`
    做 `consumed_ports ⊆ available` 比对；插件仍只看 `ResolutionView`。
  - ★ **但该接线尚未落地**——相关函数仍为 SHELL。若实现中发现必须越出冻结边界 → 按 §MOLD BREAK 上报。

### 4.3 `resolve_inputs(spec, manifest) -> tuple[InputResolution, str]`

- **输入**：
  - `spec: PluginSpec`：只读读取 `required_inputs` 与 `optional_inputs`。
  - `manifest: SurfaceManifest`：只读读取 `ports` 及其 `PortDescriptor` 字段。
- **输出**：`tuple[InputResolution, str]`；第二项是 `status`，输入解析不满足 required 时为
  `INCOMPATIBLE`；required 全部满足时为 `OK`；optional 缺失本身不使解析成为 `INCOMPATIBLE`。
  `resolve_inputs` 不返回 `DEGRADED` / `FAILED`，也不运行插件；后者分别由插件结果与结果校验表达。
- **逐条输入检查（对每条 required / optional 的 `InputRequirement` 都执行）**：

  | 编号 | 检查 | 合格条件 |
  | --- | --- | --- |
  | R1 | 端口存在 | `req.port_id in manifest.ports` |
  | R2 | schema | `req.schema_version in ('*', desc.schema_version)` |
  | R3 | 时间轴 | `req.timeline_basis is None or req.timeline_basis == desc.timeline_basis` |
  | R4 | dtype | `req.element_type is None or req.element_type == desc.element_type` |
  | R5 | 字段 | `set(req.required_fields) <= set(desc.field_names)` |
  | R6 | 采样率 | `req.sample_rate is None or desc.sample_rate == req.sample_rate` |

  任一检查失败，就该端口“不可用”；不得尝试读缓冲区、生成新端口或把失败改成默认值。
- **required 口径**：任一 required 不满足时，状态为 `INCOMPATIBLE`，其 port_id 进入
  `incompatible_required`；入口不应被调用。全部 required 满足时状态为 `OK`，即使全部 optional 缺失也可运行。
- **optional 口径**：通过检查的 optional 进入 `available`；失败的 optional 进入
  `missing_optional`；optional 失败不得污染 `incompatible_required`，也不得自动生成 Core 端口。
- **空输入**：`required_inputs` 为空时，required 条件自然满足，状态为 `OK`；
  optional 仍逐条按 R1–R6 检查。
- **不可变输出**：三个集合字段使用 `frozenset`；不得返回 `set`、list 或重复事实的映射。
- **不变量**：同一份 spec + 同一份 manifest 的解析结果可重复；本函数不修改 spec、manifest
  或任何 descriptor。
- **当前状态**：`resolve_inputs` 仍是完整签名与详细 docstring 下的 SHELL；没有检查逻辑已实现
  （`harmonica_eval/algorithms/runtime.py:134-178`）。

★ **schema 裁定**：当前 12 个 `PortDescriptor.schema_version` 全部等于
`'CORE_PROFILE_V0.1'`。它是 profile 版本，不是逐端口语义版本；默认 `InputRequirement.schema_version`
必须是 `'*'`，R2 只能做上述精确/通配匹配，不能把它当细粒度语义版本。细粒度匹配走
`element_type` / `required_fields` / 时间轴。

★ **采样率裁定**：当前 12 个端口中有 5 个 `sample_rate == 0`（`warp_path`、`chroma.lowres.*`、
`notes.*`）。`0` 的含义是“与采样率无关”，不是数据缺失；这些端口可正常声明为 required/optional。
插件不得写 `req.sample_rate = 0` 来表示“要求采样率为 0”；R6 对 `None` 放行，对非 `None` 做
精确匹配，不能把描述符的 0 自动解释成缺数据或让所有无约束输入失败。

### 4.4 `validate_result(result) -> None`

- **输入**：一个 `AlgorithmResultEnvelope`；只读，不修改 payload、信封字段或外部状态。
- **输出**：成功返回 `None`；任一检查失败抛 `ValueError`，detail 必须指明字段与实际值。
- **纯校验范围**：只判断信封自身可机械判断的自洽性；不读 manifest、不读端口、不读
  `PluginSpec`、不读 `InputResolution`、不调用插件入口。

按以下 8 项检查，顺序、优先级与边界按壳件 docstring 执行：

1. `result.status` 属于 `('OK', 'DEGRADED', 'INCOMPATIBLE', 'FAILED')`。
2. payload 每个元素都是 `UiScalar` 或 `UiSeries`；每个元素 unit 属于 `UNITS_VOCABULARY`。
3. 每个 `UiSeries` 满足 `len(t) == len(values)`。
4. 每个 `UiSeries` 显式携带合法 `timeline_basis`。
5. `coverage` 若非 `None`，必须是 `[0.0, 1.0]` 内的有限数。
6. `status == 'DEGRADED'` 时，`coverage` 非 `None` 或 `warnings` 非空至少一项成立。
7. `status` 为 `INCOMPATIBLE` / `FAILED` 时，`error_code` 非 `None`，且属于该状态合法
   `ErrorCode`；具体允许集合按壳件 docstring：`INCOMPATIBLE → PLUGIN_INCOMPATIBLE`，
   `FAILED → ALGORITHM_FAILED / ALGORITHM_TIMEOUT / ALGORITHM_RESULT_INVALID`。
8. `status` 为 `OK` / `DEGRADED` 时 `error_code` 为 `None`。

补充边界：未知状态、自由字符串错误码、裸 payload 元素、未知单位、曲线错位、缺时间轴、
NaN/无穷 coverage、无证据 DEGRADED 全部必须显式失败；不得以 `OK` 代替。

- **当前状态**：`validate_result` 仍是 SHELL，上述 8 项均是待授权后的验收规格而非已实现行为
  （`harmonica_eval/algorithms/runtime.py:181-237`）。

- **责任边界**：原始 `InputResolution` 与其 `available` 不出 runtime，故 `validate_result` 与插件
  都无法证明 `consumed_ports ⊆ available`。该检查必须在 runtime/C1 共同持有的编排层完成；不得
  把它塞进 `AlgorithmResultEnvelope` / payload（那会把控制信息变成插件可伪造的数据），也不得
  为此给 `validate_result` 增参。runtime 源码已把该职责写为 C1 调用点边界
  （`harmonica_eval/algorithms/runtime.py:173-176,229-232`）；FILE-205 不得实现它。

### 4.5 未来获授权注入时的实现格式

- 六个既有空壳方法各自替换为完整函数体，保留原签名、冻结字段与 docstring。
- 私有辅助函数只能在 `runtime.py` 内使用；不得新增公开符号、异常类、错误码或模块级状态。
- 可以使用枚举/契约类型的值与 tuple 成员进行精确判定；不要把未知值静默归一为 OK。
- 失败必须抛出带上下文的 `ValueError`；不得 `except Exception: pass`，不得打印后继续。
- 本文件不负责生成结果、不修复插件返回值；需要这些动作 → 停止并按 §10 上报。
- **当前负责人尚未授权注入**（`.spec/OWNER-DIRECTIVES.md:50-85`）；本节只记录将来获授权后的实现边界。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| required 端口不存在 | 解析不兼容，入口不调用 | 返回 `('INCOMPATIBLE', resolution)` |
| required 的 schema/时间轴/dtype/字段/采样率任一不满足 | 标出全部不兼容 required 端口 | 返回 `('INCOMPATIBLE', resolution)` |
| optional 端口任一检查失败 | 记录 missing_optional，不阻止运行 | `('OK', resolution)` |
| 所有 required 满足、optional 可全缺 | 正常运行 | `('OK', resolution)` |
| 插件结果 status 未知 | 显式失败 | `ValueError`，detail 指明 status |
| payload 元素/单位/曲线形状/时间轴不合法 | 显式失败 | `ValueError` |
| coverage 越界或非有限 | 显式失败 | `ValueError` |
| DEGRADED 无 coverage 且无 warnings | 拒绝“偷偷少算” | `ValueError` |
| 失败状态缺错误码或码不匹配 | 显式失败 | `ValueError` |
| 成功/降级状态携带 error_code | 显式失败 | `ValueError` |
| C1 所需的 consumed_ports ⊆ available 检查 | **不在本文件**；由 runtime/C1 共同持有的编排层完成，原始 `InputResolution` 不出 runtime | 本文件不得抛替代错误 |
| 未预期内部异常 | 不吞异常、不伪造成功 | 保留可诊断异常；不得新增错误码 |

★ 宪章 §5.6：禁止静默降级。optional 缺失只有在解析阶段如实记录、在结果阶段以 DEGRADED
证据呈现时才是合法降级；不满足六项检查的 required 不能被“自动生成”或“当成可用”。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-205-1 | `InputResolution` 在 `runtime.py` 以 frozen dataclass 定义，仍为 `available` / `missing_optional` / `incompatible_required` 3 字段 | §8.2 AST |
| INV-205-2 | `InputResolution` 不在 `contract.py` 定义、导入或导出；契约层只新增独立的 `ResolutionView` | §8.2 AST + `__all__` + `hasattr` |
| INV-205-2A | `ResolvedSurface` 为 frozen dataclass，字段恰为 `_surface: AlgorithmDataContract` / `_resolution: ResolutionView`；`as_view`、`manifest`、`read`、`resolution` 四个方法当前均抛 SHELL | §8.2 AST + 空壳探针；源码 `harmonica_eval/algorithms/runtime.py:89-131` |
| INV-205-2B | 原始 `InputResolution` 不出 runtime；只有 `ResolutionView` 抵达插件，视图没有 `incompatible_required` 字段 | §8.2 分别检查 runtime dataclass 字段与 contract `ResolutionView` 字段；源码 `harmonica_eval/algorithms/runtime.py:65-96`、`harmonica_eval/contract.py:390-413` |
| INV-205-3 | `resolve_inputs` 对 required / optional 的 6 项检查逐项执行 | 注入后行为验收；空壳期验证完整 docstring 与签名 |
| INV-205-4 | required 不满足返回 INCOMPATIBLE，optional 不满足只记录 missing_optional | 注入后行为验收 |
| INV-205-5 | schema_version 仅作 `*` 或精确 profile 版本匹配 | §8.2 读取壳件 docstring + 注入后验收 |
| INV-205-6 | `sample_rate == 0` 表示与采样率无关，不表示缺数据 | §8.2 读取 profile 实测 + 注入后验收 |
| INV-205-7 | `validate_result` 成功返回 `None`，失败抛 `ValueError` | §8.2 空壳门禁 + 注入后行为验收 |
| INV-205-8 | 八项结果自洽检查完整 | 注入后逐项负向验收；空壳期验证 docstring |
| INV-205-9 | DEGRADED 必须有 coverage 或 warnings 证据 | 注入后负向验收 |
| INV-205-10 | `consumed_ports ⊆ available` 不在本文件实现 | §8.3 AST 边界断言 |
| INV-205-11 | runtime 不 import core / host / cockpit | §8.2 import AST + §8.3 grep |
| INV-205-12 | 两个签名与返回注解逐字冻结 | §8.2 AST |
| INV-205-13 | 模块 docstring 含 10 个现场字段 | §8.2 nameplate |
| INV-205-14 | 两个占位 raise 消息均含 `FILE-205` | §8.2 |

---

## 7 · 边界（明确不做）

- **不把原始 `InputResolution` 暴露给插件，也不把它放进 `contract.py`**。它是执行期产物，不是跨组件契约；不得通过
  re-export、类型别名或新增 `__all__` 名称间接搬入契约层。插件只拿 `ResolutionView`。
- **责任边界**：`consumed_ports ⊆ available` **不由本文件校验**。原始解析事实与 `available`
  不出 runtime，插件只见 `ResolutionView`；该检查须在 runtime/C1 共同持有的编排层完成。
  不得把 available 塞进 result/payload（等于用结果数据传控制信息，插件也能伪造它）。
- **不把 schema_version 当逐端口语义版本**。当前 12 个端口均为 profile 版本字符串，细粒度
  兼容性只能通过 R3–R5 表达。
- **不把 `PortDescriptor.sample_rate == 0` 当数据缺失**。它是“与采样率无关”；不得因 0 自动
  拒绝端口，也不得要求插件以 0 表示无采样率。
- **不请求 Core 生成端口**，不调用 manifest 之外的生成接口，不要求 C2 为 optional 缺失补数据。
- **不运行插件入口，不读取 BufferView，不执行 DSP**；本文件只处理描述符与结果对象。
- **不修改 payload 以使结果通过**；非法结果必须抛 `ValueError` 交给 C1 处理。
- **不新增公开符号、异常类、错误码、模块级缓存或输入参数**。当前 5 项 `__all__` 与两类
  frozen dataclass 是已冻结审查形状；未来实现只能在现有成员中补逻辑。需要新语义 → 停止并转 §10。
- **不修改任何其它 `.py` 文件**。契约冲突必须上报，不在本文件打补丁。
- **不把 SHELL 写成已实现**：尤其 C2 `Surface` 没有 `resolution`（`core/surface.py:112-144`），
  `ResolvedSurface` 虽给出预期组合形状，但四个方法尚未实现；
  ★ Registry 的物理装配根已裁定为 `algorithms/bootstrap.py`（`GC-204-08` CLOSED），
  C1 与本文件的职责已按 BLOCK-2 方案乙划清，但**接线尚未落地**——不得把它写成已完成。

---

## 8 · 怎么验证你写对了

★ **阶段：实现期（负责人 2026-09-24 授权注入，第 3 刀）。**
★ §8.2 的行为验收已按实现期改写为**校验真实返回值**；其依赖方向、私有类型、铭牌
★ 三组断言**注入前后都必须成立，原样保留**。
★ **§8.3（C1 职责边界）与 §8.4（依赖方向）注入后继续有效，不因注入而放宽。**

### 8.1 运行环境

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python --version
```

判据：退出码为 0；原文写入 §9。

### 8.2 空壳性、依赖方向、私有性与铭牌

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
import ast
from pathlib import Path
from harmonica_eval.algorithms import runtime
from harmonica_eval import contract

path = Path('harmonica_eval/algorithms/runtime.py')
tree = ast.parse(path.read_text(encoding='utf-8'))

# 真实委托对象（ResolvedSurface 的三个方法会真去调它，不能用 object() 占位）。
class _FakeSurface:
    def manifest(self):
        return 'MANIFEST-SENTINEL'
    def read(self, port_id, time_range=None):
        return f'READ:{port_id}:{time_range}'

_fake = _FakeSurface()
_view = runtime.ResolutionView(available=frozenset({'a'}), missing_optional=frozenset())

for name, fn, args in (
    ('InputResolution.as_view', runtime.InputResolution.as_view,
     (runtime.InputResolution(frozenset(), frozenset(), frozenset()),)),
    ('ResolvedSurface.manifest', runtime.ResolvedSurface.manifest,
     (runtime.ResolvedSurface(_fake, _view),)),
    ('ResolvedSurface.read', runtime.ResolvedSurface.read,
     (runtime.ResolvedSurface(_fake, _view), 'p')),
    ('ResolvedSurface.resolution', runtime.ResolvedSurface.resolution.fget,
     (runtime.ResolvedSurface(_fake, _view),)),
):
    # ★ 实现期判据：不得再抛「待注入实现」，且**必须真返回委托结果**。
    try:
        out = fn(*args)
    except NotImplementedError as exc:
        raise AssertionError(
            f'{name} 仍是空壳（{exc}）—— 实现期不得抛 NotImplementedError')
    print(f'{name}: {out!r}')

# ★ 委托必须真穿透，不能是恒返回值或 None 占位。
assert runtime.ResolvedSurface(_fake, _view).manifest() == 'MANIFEST-SENTINEL', \
    'ResolvedSurface.manifest 未真委托给底层 surface'
assert runtime.ResolvedSurface(_fake, _view).read('p', (0.0, 1.0)) == 'READ:p:(0.0, 1.0)', \
    'ResolvedSurface.read 未真委托（端口 id / time_range 必须原样透传）'
assert runtime.ResolvedSurface(_fake, _view).resolution is _view, \
    'ResolvedSurface.resolution 未返回组合进来的视图'

# ★ as_view 必须投影 available / missing_optional，且**不投影 incompatible_required**。
_v = runtime.InputResolution(
    available=frozenset({'a'}), missing_optional=frozenset({'b'}),
    incompatible_required=frozenset({'c'})).as_view()
assert _v.available == frozenset({'a'}), _v
assert _v.missing_optional == frozenset({'b'}), _v
assert not hasattr(_v, 'incompatible_required'), '视图不得暴露 incompatible_required'
assert isinstance(_v, contract.ResolutionView), type(_v)

for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            assert alias.name.split('.')[0] not in {'core', 'host', 'cockpit'}, alias.name
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ''
        if node.level == 0:
            assert module.split('.')[0] not in {'core', 'host', 'cockpit'}, module
        else:
            assert module not in {'core', 'host', 'cockpit'}, module
print('RUNTIME-DEPENDENCY-OK')

contract_tree = ast.parse(Path('harmonica_eval/contract.py').read_text(encoding='utf-8'))
assert any(isinstance(n, ast.ClassDef) and n.name == 'InputResolution' for n in tree.body)
assert any(isinstance(n, ast.ClassDef) and n.name == 'ResolvedSurface' for n in tree.body)
assert not any(isinstance(n, ast.ClassDef) and n.name == 'InputResolution' for n in contract_tree.body)
assert not any(isinstance(n, ast.ImportFrom) and 'InputResolution' in [a.name for a in n.names] for n in ast.walk(contract_tree))
for n in ast.walk(contract_tree):
    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__all__' for t in n.targets):
        assert not any(isinstance(e, ast.Constant) and e.value == 'InputResolution' for e in ast.walk(n.value))
assert not hasattr(contract, 'InputResolution')
assert hasattr(contract, 'ResolutionView')
assert [f.name for f in runtime.InputResolution.__dataclass_fields__.values()] == [
    'available', 'missing_optional', 'incompatible_required']
assert [f.name for f in runtime.ResolvedSurface.__dataclass_fields__.values()] == [
    '_surface', '_resolution']
assert [f.name for f in contract.ResolutionView.__dataclass_fields__.values()] == [
    'available', 'missing_optional']
print('RUNTIME-PRIVATE-TYPE-OK')

fields = ('FILE-ID:', 'COMPONENT:', 'SPEC:', 'ROLE:', 'INTENT:', 'MUST:', 'MUST NOT:', 'INPUT:', 'OUTPUT:', 'BUILD-INSTRUCTION:')
doc = ast.get_docstring(tree)
assert all(field in doc for field in fields)
print('RUNTIME-NAMEPLATE-OK 10')
print('RUNTIME-SHELL-OK')
PY
```

判据：退出码为 0；六个冻结空壳方法（`InputResolution.as_view`、`ResolvedSurface.manifest` /
`read` / `resolution`、`resolve_inputs`、`validate_result`）均抛 `NotImplementedError` 且消息含
`FILE-205`；输出含 `RUNTIME-DEPENDENCY-OK`、`RUNTIME-PRIVATE-TYPE-OK`、
`RUNTIME-NAMEPLATE-OK 10`、`RUNTIME-SHELL-OK`；无 traceback。

★ 私有性判据必须按上面的 AST、`__all__` 与属性检查执行，不能改成对 `contract.py` 全文
grep `InputResolution`：契约 docstring 刻意提到该名，是说明它不进契约层，不是定义它。

### 8.3 ★ C1 职责边界（consumed_ports / available）

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
import ast
from pathlib import Path

path = Path('harmonica_eval/algorithms/runtime.py')
tree = ast.parse(path.read_text(encoding='utf-8'))

# 去掉 docstring Expr 节点；只扫描可执行 AST。
for parent in ast.walk(tree):
    body = getattr(parent, 'body', None)
    if isinstance(body, list):
        body[:] = [n for n in body if not (
            isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
        )]

def expression_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            names.add(child.value)
    return names

for node in ast.walk(tree):
    if isinstance(node, ast.Compare):
        found = expression_names(node.left)
        for comparator in node.comparators:
            found |= expression_names(comparator)
        assert not {'consumed_ports', 'available'} <= found, (node.lineno, found)
print('RUNTIME-C1-BOUNDARY-OK')
PY
```

判据：退出码为 0，唯一输出 `RUNTIME-C1-BOUNDARY-OK`。
这个检查覆盖 `result.consumed_ports`、`available`、属性/下标访问以及把二者放在同一
`Compare` 表达式的各种形态；docstring 里的职责说明不计入可执行比较。

### 8.4 依赖方向 grep

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
if grep -nE '^[[:space:]]*(from|import)[[:space:]].*(core|host|cockpit)' harmonica_eval/algorithms/runtime.py; then
  echo 'RUNTIME-DEPENDENCY-FAIL'
  exit 1
else
  echo 'RUNTIME-DEPENDENCY-OK'
fi
```

判据：退出码为 0，输出仅 `RUNTIME-DEPENDENCY-OK`。

### 8.5 判据清单

- [ ] ★ §8.2 四个组合/视图方法**真返回委托结果**：manifest 透传 sentinel、
  read 原样透传 port_id 与 time_range、resolution 返回组合进来的同一对象、
  as_view 投影 available/missing_optional 且**不暴露 incompatible_required**；
  且**均不得再抛** `NotImplementedError`。
- [ ] §8.2 确认 `InputResolution` 在 runtime.py 定义、在 contract.py 不定义/不导入/不导出；
  `ResolutionView` 在 contract.py 定义、runtime 重新导出；`ResolvedSurface` 仅在 runtime 定义。
- [ ] §8.2 的十字段铭牌与 import 方向断言全部通过，末行 `RUNTIME-SHELL-OK`
  （★ 该标记现指「依赖方向/私有类型/铭牌三组不变量通过」，不再是「函数是空壳」）。
- [ ] §8.3 的 AST 比较边界断言通过，末行 `RUNTIME-C1-BOUNDARY-OK`。
- [ ] §8.4 grep 无匹配，输出 `RUNTIME-DEPENDENCY-OK`。
- [ ] ★ 实现期：只改 `runtime.py`；`.spec` 本文件随阶段同步；未 git add / commit。
- [ ] ★ 实现期已补跑：六项输入检查、八项结果校验、optional 全缺仍 OK、
  payload unit 不在词表必被拒（毫秒单位冲突的守门）；反向用例见 §9 证据。

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] 完整目标文件：`harmonica_eval/algorithms/runtime.py`（空壳与注入后版本分别存档）。
- [ ] `git diff --stat` 原文，证明实现者只改本文件。
- [ ] `git diff harmonica_eval/algorithms/runtime.py` 原文，证明铭牌、docstring、签名、私有类型与 `__all__` 未漂移。
- [ ] §8.1 `python --version` 原文。
- [ ] §8.2 完整 stdout 原文（四行委托/视图实参与三个 OK 标记）。
- [ ] §8.3 完整 stdout 原文（`RUNTIME-C1-BOUNDARY-OK`）。
- [ ] §8.4 完整 stdout 原文（`RUNTIME-DEPENDENCY-OK`）。
- [ ] 不得伪造输入解析或结果校验的数值结果；黄金向量须由实跑产生。
- [ ] 若任何命令失败，提交失败原文与 `GATE CHALLENGE`，不得只写“预期通过”。

---

## 10 · ★ 何时必须停止并上报（§22 硬失败对策）

**以下情况必须停止，不得自行设计：**

1. 你需要把 `InputResolution` 定义、导入或 re-export 到 `contract.py`。
2. 你需要给 `InputResolution` 新增字段、状态布尔值、隐式全局缓存或可变容器。
3. 你需要改变 `resolve_inputs` / `validate_result` 的参数、返回注解或第三种状态。
4. 你需要改变六项输入检查、八项结果检查、错误码集合或时间轴口径。
5. 你需要让 `validate_result` 接收 `available`、`InputResolution`、manifest 或端口数据。
6. 你需要比较 `consumed_ports` 与 `available`，或把 available 塞进 result/payload。
7. 你需要新增依赖、import 具体算法、core/host/cockpit，或执行 DSP/插件入口。
8. 你发现 `contract.py` 的 `AlgorithmResultEnvelope`、`InputRequirement` 或 `SurfaceManifest`
   与本规格实际字段不一致。
9. 你需要把 `schema_version` 当逐端口语义版本，或把 `sample_rate == 0` 当缺数据。
10. 你发现必须用新的错误码/新状态来表达才能完成校验。
11. 你需要让 C2 `Surface` 实现 `resolution`，或把原始 `InputResolution` 传给**插件**；这两项都会越出
    当前冻结边界，须由负责人裁定。
    ★ 注：C1 拿 `InputResolution` 已由 BLOCK-2 方案乙裁定（2026-09-24），**不受此条限制**；
    ★ 但「给插件」仍然禁止。`GC-204-08` 已 CLOSED，不再是本条的阻塞来源。

**MOLD BREAK 上报格式**：

```
MOLD BREAK
- 文件 ID：FILE-205
- 触发条款：§10 第 <n> 条
- 我在做什么：
- 卡在哪：
- 实际需要 vs 规格给出：
- 为什么我无法在不做上层设计的前提下继续：
- 建议的上游处理位置：
```

**绝对禁止**：

- 把原始 `InputResolution` 偷渡进 contract.py 或暴露给插件；
- 以“方便校验”为由把 available 写入信封或新增隐式全局；
- 把 C1 的 consumed_ports 检查加进 runtime；
- 静默吞异常、打印后继续、伪造 OK 或补造缺失端口；
- 把任何 SHELL 写成已实现、已装配或已授权；
- 修改任何 `.py` 文件、契约或其它模块。

---

## 附：本文件的冻结常量速查

| 项 | 值 | 来源 |
| --- | --- | --- |
| `InputResolution` | `@dataclass(frozen=True)`，3 个 `frozenset[str]` 字段：`available` / `missing_optional` / `incompatible_required` | `harmonica_eval/algorithms/runtime.py:65-87` |
| `InputResolution.as_view` | `-> ResolutionView` | `harmonica_eval/algorithms/runtime.py:89-96` |
| `ResolutionView` | contract 层 `@dataclass(frozen=True)`，字段 `available` / `missing_optional`，查询 `is_available` | `harmonica_eval/contract.py:390-413` |
| `ResolvedSurface` | `@dataclass(frozen=True)`，字段 `_surface: AlgorithmDataContract` / `_resolution: ResolutionView` | `harmonica_eval/algorithms/runtime.py:99-114` |
| `ResolvedSurface.manifest` | `() -> SurfaceManifest` | `harmonica_eval/algorithms/runtime.py:116-118` |
| `ResolvedSurface.read` | `(port_id, time_range=None) -> BufferView` | `harmonica_eval/algorithms/runtime.py:120-126` |
| `ResolvedSurface.resolution` | `@property -> ResolutionView` | `harmonica_eval/algorithms/runtime.py:128-131` |
| `InputResolution` 位置 | `harmonica_eval.algorithms.runtime` 私有定义；原始对象不出 runtime | `harmonica_eval/algorithms/runtime.py:65-96` / `contract.py:390-413` |
| `resolve_inputs` 签名 | `(spec: PluginSpec, manifest: SurfaceManifest) -> tuple[InputResolution, str]` | `harmonica_eval/algorithms/runtime.py:134-178` |
| `validate_result` 签名 | `(result: AlgorithmResultEnvelope) -> None` | `harmonica_eval/algorithms/runtime.py:181-237` |
| 输入机械检查 | 6 项：存在/schema/时间轴/dtype/字段/采样率 | `runtime.py` docstring |
| 结果机械检查 | 8 项：状态/payload/曲线/时间轴/coverage/DEGRADED/错误码 | `runtime.py` docstring |
| `schema_version` 实测值 | 12 个端口均 `'CORE_PROFILE_V0.1'` | `profile.py` / contract docstring |
| `sample_rate == 0` 端口 | 5 个：`warp_path`、`chroma.lowres.*`、`notes.*` | `profile.py` / contract docstring |
| `consumed_ports` 边界 | `consumed_ports ⊆ available` **不由本文件实现**；原始 `InputResolution` **对 C1 可见**（BLOCK-2 乙，2026-09-24），插件只见 `ResolutionView` | `harmonica_eval/algorithms/runtime.py` `resolve_inputs` docstring |
| `__all__` | `["InputResolution", "ResolutionView", "ResolvedSurface", "resolve_inputs", "validate_result"]` | `harmonica_eval/algorithms/runtime.py:240-246` |
| 注入授权 | ★ **已授权**（2026-09-24，第 3 刀）；六个方法均已实现，§8 为行为验收 | `.spec/OWNER-DIRECTIVES.md:50-85`; `harmonica_eval/algorithms/runtime.py:89-131,178,237` |
| 现场字段 | 10 个，含 `FILE-ID` 与 `BUILD-INSTRUCTION` | SHELL-STANDARD v1 |
