# CONTRACTS —— 契约冻结台账

> 本文件记录**哪些契约声明已冻结、哪些运行期行为尚待实现**。
> 依据宪章 §9（可执行契约）、§15（成对版本化）、§45（状态模型）、§47.10（禁止提前冻结）。
> 事实来源以 `harmonica_eval/contract.py`（契约声明）、`harmonica_eval/profile.py`
> （冻结 profile）及 `.spec/build/FILE-003-v1.md`（冻结的 Build Instruction）为准。
>
> **原则：冻结一个契约，等于承诺下游可以依赖它。**
> 在上游未定前冻结，是把返工成本转嫁给所有下游组件。
>
> ★ 本台账中的「已冻结」只表示**接口结构与语义已经写定**；不表示
> C1/C2/C3/C4 的运行期行为已经实现。当前组件代码仍有 `NotImplementedError`
> 骨架，凡不能从代码核实的行为均明确标为「待实现，骨架中无对应」。

---

## 0. 当前冻结状态总览

**OC1 已关闭，且裁定方式与初版相反**（见 `research/03-datapath-decision.md` §7）：

> **Core 预生成，端口清单封闭。算法适配 Core，不是 Core 适配算法。**
> 不做惰性计算、不做存储后端选型、不做 LRU 缓存。
> 原因：惰性计算要求 Core 为算法现场算数据，必须附带协商协议，
> 而那会让 Core 的外部接口变成**插件需求的函数**——正是要避免的反模式。

| 契约 | 声明与状态 | 运行期实现状态 |
| --- | --- | --- |
| **CONTRACT-SESSION-v1** | 会话状态、时间基准、音频格式；✅ **FROZEN** | 纯声明已在 `contract.py`；无独立运行期实现 |
| **CONTRACT-ERRORS-v1** | 错误码与异常层次；✅ **FROZEN** | 类型已实现；产生、归一化与上报路径**待实现，骨架中无对应** |
| **CONTRACT-HOST-v1** | C1 → C2，7 个操作；✅ **FROZEN** | `core/api.py:HostCore` 有 7 个对应空壳；**待实现，骨架中无对应** |
| **CONTRACT-ALGORITHM-DATA-v1** | C3 → 数据面，2 个操作；✅ **FROZEN**（纯查表、无副作用） | `core/surface.py:Surface` 有空壳；**待实现，骨架中无对应** |
| **CONTRACT-UI-v2** | C1 ↔ C4 投影与命令；✅ **FROZEN** | `host/app.py`、`cockpit/app.py` 有空壳；**待实现，骨架中无对应** |
| **CORE_PROFILE_V0.1** | **封闭端口清单（12 个端口，写死）**；✅ **FROZEN** | profile 声明与 import 期完整性检查已有；C2 物化行为**待实现，骨架中无对应** |

> ★ **状态口径**：契约声明没有待定项；OC1 已关闭，`acquire_surface()`、
> `manifest()` / `read()` 的返回类型和纯查表语义均已写入冻结契约。
> 但这**不等于**运行期已经可依赖：组件仍是骨架，不能把本文当作端到端实现证据。

---

## 1. OC1 对契约的最终影响

| 内容 | 冻结后的真实口径 | 代码依据 |
| --- | --- | --- |
| **会话状态 6 值** | `SessionState` 恰有 6 值：`CREATED` / `INPUT_READY` / `BUILDING` / `DATA_READY` / `FAILED` / `CLOSED` | `contract.py:58-82` |
| **时间基准 2 值** | `TimelineBasis` 恰有 2 值：`REFERENCE` / `WARPED`；另定义 `AlignmentRepresentation` 2 值 | `contract.py:85-152` |
| **音频格式** | `AudioFormat(sample_rate, channels, dtype)`；构造时要求 mono / float32 | `contract.py:155-173` |
| **错误码** | `ErrorCode` 恰有 12 值；其中 `ALGORITHM_TIMEOUT` 与 `COCKPIT_DETACHED` 在 v0.1 不产生 | `contract.py:598-664` |
| **Host 的生命周期操作** | `HostContract` 恰有 7 操作；除 `acquire_surface` 外为生命周期/状态操作，`acquire_surface` 返回数据面契约 | `contract.py:492-571` |
| **算法数据面接口** | `AlgorithmDataContract` 恰有 `manifest` / `read` 2 操作；`read()` 明确无计算副作用 | `contract.py:399-473` |
| **UI 投影接口** | `UiProjectionPort` 恰有 `snapshot` / `submit` 2 操作；`UiCommandKind` 恰有 6 值 | `contract.py:807-950` |

### 1.1 已关闭的旧「待 OC1」项

旧台账曾把 `acquire_surface()` 的返回类型、`read()` 的签名与副作用、
`SurfaceManifest` 的结构列为待定。OC1 关闭后，这些项目**不再是待定项**：

| 旧待定项 | 冻结结果 | 实际位置 |
| --- | --- | --- |
| `acquire_surface()` 返回什么 | 返回 `AlgorithmDataContract`，不是特定存储后端或内存数组句柄 | `contract.py:558-564` |
| `read(port_id, time_range)` | 返回 `BufferView`；时间为秒；纯读取，不触发计算 | `contract.py:413-473` |
| `SurfaceManifest` 字段 | `profile_version` / `audio_format` / 两段时长 / `ports` / `sealed` | `contract.py:355-369` |

> ★ 当前代码**没有**存储后端或“内存数据面”专有句柄类型；不得把
> `acquire_surface` 改写成 ndarray、memmap 句柄或存储实现专属类型。

---

## 2. 已冻结契约明细

### 2.1 CONTRACT-SESSION-v1 ✅

**真实文件**：`harmonica_eval/contract.py`（旧台账所列
`harmonica_eval/contract/session.py` 不存在）。

**本组产出**：`SessionState`（6 值）· `TimelineBasis`（2 值）·
`AlignmentRepresentation`（2 值）· `AudioFormat`（3 字段）。

**为什么安全**：这组词汇描述会话、坐标和标准化格式，不依赖存储后端。
运行期状态推进与音频标准化**待实现，骨架中无对应**。

**状态口径**：正常流程状态单调推进，不跳过数据面构建；`CANCEL` 与 `RESET`
是管理操作，允许回退到稳定态。`CANCEL` 在 `BUILDING` 时**不打断同步构建**；
构建完成后按 `CANCEL` 的目标转移生效。`CANCEL` 只能在 `INPUT_READY` /
`DATA_READY` 阶段被即时响应。`RESET` 丢弃数据面与已登记输入，回 `CREATED`，
会话对象本身保留。契约没有取消标志的设置或观察通道，故不存在可执行的
端口级检查要求；也**不得**注入后台线程、回调或 checkpoint 来改变这一冻结行为。
具体冻结转移以 `COMMAND_EFFECTS` 为准。

### 2.2 CONTRACT-ERRORS-v1 ✅

**真实文件**：`harmonica_eval/contract.py`（旧台账所列
`harmonica_eval/contract/errors.py` 不存在）。

**产出**：`ErrorCode`（12 值）· `HarmonicaError`（5 字段）·
`ContractViolation` · `CoreBuildError` · `AlgorithmError`。

**强制语义**（与当前 `COMPONENTS.md` / `contract.py` 对齐）：

| 失败 | 归属 | 数据面 | 其他算法 | 代码状态 |
| --- | --- | --- | --- | --- |
| 输入不可解码 / 过短 / 静音 / 过长 | C2 | **不存在** | 不启动 | 码已定义；抛出路径**待实现，骨架中无对应** |
| 对齐无法建立有效映射 | C2 | **不存在** | 不启动 | 码已定义；抛出路径**待实现，骨架中无对应** |
| 算法要求未知端口 | C1 判定 | 有效 | 正常 | `PLUGIN_INCOMPATIBLE` 已定义；判定路径**待实现，骨架中无对应** |
| 算法崩溃 / NaN | C3 | 有效 | 正常 | `ALGORITHM_FAILED` 已定义；捕获与折返信封**待实现，骨架中无对应** |
| 算法结果 schema 非法 | C1 校验 | 有效 | 正常 | `ALGORITHM_RESULT_INVALID` 已定义；校验路径**待实现，骨架中无对应** |
| **算法死循环** | C3 | 有效 | **会卡住（v0.1 已知缺口）** | `ALGORITHM_TIMEOUT` 已定义，但 v0.1 不得产生 |
| 界面断开 | C4 | 有效 | 正常 | `COCKPIT_DETACHED` 已定义，但 v0.1 **不会产生** |

**特别禁止**：`ALIGNMENT_UNRECOVERABLE` **不得**被降级为“逐点硬比继续跑”。
静默降级违反宪章 §5.6。该禁令已进入冻结声明；实际抛出路径尚未实现。

### 2.3 CONTRACT-HOST-v1 ✅

**真实文件**：`harmonica_eval/contract.py`（旧台账所列
`harmonica_eval/contract/host.py` 不存在）。

**产出**：`HostContract`（7 个操作）+ `FORBIDDEN_OPERATIONS`（10 个禁止方法名）。

7 个操作及签名：

| # | 操作 | 返回类型 |
| --- | --- | --- |
| 1 | `create_session(profile_version: str)` | `str` |
| 2 | `set_reference(session_id: str, uri: str)` | `None` |
| 3 | `set_practice(session_id: str, uri: str)` | `None` |
| 4 | `build_surface(session_id: str)` | `None` |
| 5 | `status(session_id: str)` | `SessionState` |
| 6 | `acquire_surface(session_id: str)` | `AlgorithmDataContract` |
| 7 | `destroy_session(session_id: str)` | `None` |

`FORBIDDEN_OPERATIONS` 恰有 10 项：`align` / `fft` / `stft` /
`compute_feature` / `generate_pitch_input` / `generate_plugin_requirement` /
`prepare_for_pitch` / `prepare_for_timing` / `register_algorithm` /
`list_algorithms`。

★ `core/api.py:HostCore` 的 7 个操作目前都落在 `NotImplementedError` 空壳内；
接口形状与禁止名单可核实，状态机、I/O 和失败处理均为
**待实现，骨架中无对应**。

### 2.4 CONTRACT-UI-v2 ✅

**真实文件**：`harmonica_eval/contract.py`（旧台账所列
`harmonica_eval/contract/ui.py` 不存在）。

**产出**：`UiView`（9 字段）· `UiSeries`（7 字段）· `UiScalar`（5 字段）·
`UiCommand`（2 字段）· `UiCommandKind`（6 值）· `UiProjectionPort`（2 操作）·
`COMMAND_LEGALITY` · `COMMAND_EFFECTS` · `UI_PAYLOAD_KEYS`。

**要点**：
- C4 只有 `snapshot()` / `submit()` 两个操作。
- `UiCommandKind` 只有 6 值；C4 **不能凭界面发明内核能力**。
- `UiSeries.timeline_basis` 无默认值，必须显式声明。
- 投影必须已下采样；C4 渲染**待实现，骨架中无对应**。

### 2.5 CONTRACT-ALGORITHM-DATA-v1 ✅

**真实文件**：`harmonica_eval/contract.py`（旧台账所列
`harmonica_eval/contract/data_surface.py` 不存在）。

**产出**：`AlgorithmDataContract`（2 操作）+ `PortDescriptor`（11 字段）+
`BufferView`（3 字段）+ `SurfaceManifest`（6 字段）+
`AlgorithmResultEnvelope`（11 字段）+ `FIELD_LAYOUTS`（4 键）+
`UNITS_VOCABULARY`（10 值：`amplitude` / `chroma` / `hz` / `index` / `rms` /
`cents` / `db` / `seconds` / `ratio` / `count`）+ `CORE_REQUIRED_PORTS`（2 端口）。
其中 `ratio` 表示 0–1 比例（如 `off_pitch_ratio`），`count` 表示无量纲计数
（如 `n_notes_used`）。

> ★ 旧台账所写 `REQUIRED_PORT_INVARIANTS`（4 条）**在代码中不存在**，
> 不得再作为可 import 符号引用。相关规则实际落在 `PortDescriptor` 字段、
> `FIELD_LAYOUTS`、`UNITS_VOCABULARY`、`CORE_REQUIRED_PORTS` 的注释与
> `profile.assert_profile_integrity()` 中。

| 规则 | 代码中的真实口径 |
| --- | --- |
| 时间基准 | `PortDescriptor.timeline_basis` 存在，默认 `REFERENCE` |
| 采样率 | `PortDescriptor.sample_rate` 存在；`0` 明确表示与采样率无关，故并非所有端口都必须非零 |
| 单位与维度 | `PortDescriptor.units` / `dimensions` 存在；单位受 `UNITS_VOCABULARY` 约束 |
| 必需端口 | `CORE_REQUIRED_PORTS` 恰为 `pcm.mapped.reference` / `pcm.mapped.practice` 两项 |

`manifest()` / `read()` 的签名、返回类型和纯查表语义已冻结；
`core/surface.py:Surface` 的数据面物化与读取行为
**待实现，骨架中无对应**。

---

## 3. 撤回稿与当前代码的关系

| 旧内容 | 当前真实状态 |
| --- | --- |
| `.spec/draft/DRAFT-FILE-010-types.py` | 文件仍存在，且仍是**撤回草案**；不得把它当运行时代码引用 |
| 草案中的 `PortDescriptor` / `BufferView` / `SurfaceManifest` | 同名类型已在当前 `contract.py` 重新定义并扩展；当前结构以 `contract.py` 为准 |
| 草案中的 `SurfaceHandle` | 当前代码**没有**该 Protocol；`acquire_surface()` 返回 `AlgorithmDataContract` |
| 草案中的 `SessionHandle` | 当前代码**没有**该 dataclass；会话标识是普通 `str` |

> ★ “撤回”指撤回该草稿的提前冻结口径，不表示这些概念永远不能再出现。
> 若概念后来依据已关闭的 OC1 正式写入冻结契约，必须以当前 `contract.py` 为事实来源。

---

## 4. 验证

### 4.1 契约模块可加载

```bash
python3 -c "import harmonica_eval.contract as c; print(len(c.__all__))"
```

**实测结果**：`29`。

### 4.2 公开面

`contract.__all__` 列出 29 个符号，覆盖会话/时间、数据面、Host、错误、UI
及契约辅助常量。旧台账所写“19 个公开符号”已过时。

### 4.3 验证边界

本节只证明**契约声明模块可 import、导出面数量正确**；
不证明 C1/C2/C3/C4 的运行期行为。组件实现状态统一记为
**待实现，骨架中无对应**。
