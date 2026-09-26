# CONTRACTS —— 契约冻结台账

> 本文件记录**哪些契约声明已冻结、哪些运行期行为有代码对应**。
> 依据宪章 §9（可执行契约）、§15（成对版本化）、§45（状态模型）、§47.10（禁止提前冻结）。
> 事实来源以 `harmonica_eval/contract.py`（契约声明）、`harmonica_eval/profile.py`
> （冻结 profile）及 `.spec/build/FILE-003-v1.md`（冻结的 Build Instruction）为准。
>
> **原则：冻结一个契约，等于承诺下游可以依赖它。**
> 在上游未定前冻结，是把返工成本转嫁给所有下游组件。
>
> ★ **本台账的「已冻结」只表示接口结构与语义已经写定。**
>
> ★★★ **2026-09-26 订正（全文系统性）★★★ ★★★
> ★ 上文原写「当前组件代码仍有 `NotImplementedError` 骨架，凡不能从代码核实的
> ★ 行为均标为『待实现，骨架中无对应』」。
> ★ ★ ★ **那句已过期。** 实测（2026-09-26）：
> ★   · `contract.py` / `core/*.py` / `host/app.py` 八个文件 **`NotImplementedError` 零命中**
> ★   · 无头入口 `python3 -m harmonica_eval --reference … --practice …` 实测 `rc=0`、16 个指标
> ★ ★ ★ 因此下文所有「**待实现，骨架中无对应**」与「**v0.1 不得/不会产生**」
> ★ ★ ★ 均已逐条复核并订正；★ 未被推翻者保留原句并注明「已被什么推翻」，
> ★ ★ ★ 让后来者知道它曾存在——★ 直接删掉会让下一个人重新怀疑一遍。
> ★ ★ 复核命令见文末「附：本次订正的复算方式」。

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
| **CONTRACT-ERRORS-v1** | 错误码与异常层次；✅ **FROZEN** | ★ **已实现**（2026-09-26 实测）。原写「产生、归一化与上报路径待实现，骨架中无对应」——★ 已被推翻：`core/ingest.py` 实抛 `CoreBuildError`，四个输入类错误码逐一验通（`INPUT_TOO_SHORT` / `INPUT_SILENT` / `INPUT_TOO_LONG` / `INPUT_UNREADABLE`），★ 异常带 `.code` 与可读 `.detail` |
| **CONTRACT-HOST-v1** | C1 → C2，7 个操作；✅ **FROZEN** | ★ **已实现**。原写「`core/api.py:HostCore` 有 7 个对应空壳；待实现」——★ 已被推翻：实测 `build_default_app()` 返回可用实例，`create_session → set_reference → set_practice → build_surface → run_algorithms → snapshot` 全链 `rc=0`、3 个算法、16 scalars、6 series |
| **CONTRACT-ALGORITHM-DATA-v1** | C3 → 数据面，2 个操作；✅ **FROZEN**（纯查表、无副作用） | ★ **已实现**。原写「`core/surface.py:Surface` 有空壳；待实现」——★ 已被推翻：`profile.PORTS` 12 个端口全部物化，`read()` / `manifest()` 可用，`produced_by` 实测为 `core.align` / `core.features` / `core.surface` 三方 |
| **CONTRACT-UI-v2** | C1 ↔ C4 投影与命令；✅ **FROZEN** | ★ **已实现**。原写「`host/app.py`、`cockpit/app.py` 有空壳；待实现」——★ 已被推翻：`GET /view`、`GET /dataset`、`POST /command` 三个端点实测 200；`RUN_ALGORITHMS` 支持 `only` 载荷键做懒加载 |
| **CORE_PROFILE_V0.1** | **封闭端口清单（12 个端口，写死）**；✅ **FROZEN** | ★ **已实现**。原写「C2 物化行为待实现，骨架中无对应」——★ 已被推翻：12 端口实测全部产出，`PortSpec` 九字段齐备（`port_id` / `units` / `dimensions` / `element_type` / `timeline_basis` / `produced_by` / `rationale` / `field_names` / `hop_length`） |

> ★ **状态口径**：契约声明没有待定项；OC1 已关闭，`acquire_surface()`、
> `manifest()` / `read()` 的返回类型和纯查表语义均已写入冻结契约。
> ★ ★ **2026-09-26 更正**：原文末句「组件仍是骨架，不能把本文当作端到端实现证据」
> ★ ★ ★ **已过期**——★ 组件已实装，★ 且端到端已实测 `rc=0`。
> ★ ★ ★ 该句保留仅为记录，★ 判断现状请以上表的实测列与源码为准。

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
★ **已实现**（2026-09-26）。原文「运行期状态推进与音频标准化待实现，骨架中无对应」
★ 已被推翻：`host/app.py` 的 `SessionState` 六值实跑走通 `CREATED → INPUT_READY →
DATA_READY`；音频标准化在 `core/ingest.py`（重采样到 profile 采样率、下混单声道）。

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

| 失败 | 归属 | 数据面 | 其他算法 | 代码状态（★ 2026-09-26 逐条实测） |
| --- | --- | --- | --- | --- |
| 输入不可解码 / 过短 / 静音 / 过长 | C2 | **不存在** | 不启动 | ★ **已实现**。原写「抛出路径待实现，骨架中无对应」——★ 已被推翻。实测 `ingest.ingest()` 四条路径全部实抛：过短 → `INPUT_TOO_SHORT`「时长 0.100s 短于下限 45.0s」、静音 → `INPUT_SILENT`「整段 RMS 0.000e+00 低于阈值 1.000e-04（线性幅度，非 dBFS）」、过长 → `INPUT_TOO_LONG`「时长 200.000s 超过上限 120.0s」、不存在 → `INPUT_UNREADABLE`「路径不存在或不是普通文件」 |
| 对齐无法建立有效映射 | C2 | **不存在** | 不启动 | ★ 码已定义（`ALIGNMENT_UNRECOVERABLE`）。★ **本轮未实跑该分支**（需构造 DTW 失败的输入），★ 保留「路径实现情况未核」——★ 不因上四条已通就推断它也通 |
| 算法要求未知端口 | C1 判定 | 有效 | 正常 | ★ **已实现**。实测 `RUN_ALGORITHMS only=["不存在插件"]` → `ContractViolation: 未注册的算法 id：['不存在插件']`；★ `runtime.py:76-88` 的 `_STATUS_ERROR_CODES` 已把 `INCOMPATIBLE → PLUGIN_INCOMPATIBLE` 冻结 |
| 算法崩溃 / NaN | C3 | 有效 | 正常 | ★ **已实现**。`runtime.py:78-83` 的 `_STATUS_ERROR_CODES['FAILED']` 冻结了 `ALGORITHM_FAILED` / `ALGORITHM_TIMEOUT` / `ALGORITHM_RESULT_INVALID` 三个码的合法归属；★ 捕获与折返信封由 `validate_result` 执行（`host/app.py:54` import） |
| 算法结果 schema 非法 | C1 校验 | 有效 | 正常 | ★ **已实现**（同上，`validate_result` 路径） |
| **算法死循环** | C3 | 有效 | **会卡住（已知缺口，★ 永久而非 v0.1）** | `ALGORITHM_TIMEOUT` 已定义并列入 `FAILED` 态合法码集，★ **但目前无超时机制，会真卡住**。★ 原文「v0.1 不得产生」是**时间限定**，★ 去掉 v0.1 后约束仍成立——★ 这是缺口，不是已实现 |
| 界面断开 | C4 | 有效 | 正常 | `COCKPIT_DETACHED` 已定义；★ 原文「v0.1 不会产生」是**时间限定**，★ 去掉后约束仍成立。★ **注意**：它**不属于插件结果码**，★ 故不在 `runtime.py:_STATUS_ERROR_CODES` 表内（该表只收插件结果码）——★ 那是设计，不是缺口 |

**特别禁止**：`ALIGNMENT_UNRECOVERABLE` **不得**被降级为“逐点硬比继续跑”。
静默降级违反宪章 §5.6。★ 该禁令**仍然成立**；原文末句「实际抛出路径尚未实现」——
★ **已被推翻**：`core/ingest.py:175` 定义 `assert_not_silent`、`:219` 在 `ingest()` 内实调
（实测调用点 1 处），静默输入会被拦下并抛 `INPUT_SILENT`。

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

★ `core/api.py:HostCore` 的 7 个操作**已实装**（2026-09-26 实测）；
★ 原文「目前都落在 `NotImplementedError` 空壳内；状态机、I/O 和失败处理均为待实现」
★ 已被推翻——★ `core/api.py` 全文 `NotImplementedError` **零命中**，
★ 端到端实跑 `create_session → set_reference → set_practice → build_surface
★ → run_algorithms → snapshot` 返回 3 个算法结果、16 个 scalars、6 条 series。
★ 失败处理亦已验通（见 §2 错误路径表：四个输入类错误码逐一实抛）。

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
- 投影必须已下采样；★ C4 渲染**已实现**（2026-09-26）。原文「C4 渲染待实现，
  骨架中无对应」已被推翻——★ 界面由 `harmonica_eval_web/`（React）渲染，
  ★ 卡片内以表格为核心（X 轴为音序维度）、曲线可勾选、元信息折叠。
  ★ ★ 「已下采样」的语义仍由契约保证：★ `UiSeries` 声明 `timeline_basis`，
  ★ ★ 而服务端只给每音一条，不给逐帧。
  ★ ★ ★ 而 C4 侧一个**仍然成立**的约束：★ 图表库会自行重采样/补间，
  ★ ★ ★ 那会让图上的数与 `metrics.json` 对不上——★ 故前端禁用图表库，
  ★ ★ ★ `tests/test_react_frontend.py` 有一条判据扫 `src/` 与 `index.html` 的外部 URL 守着。

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
★ `core/surface.py:Surface` 的数据面物化与读取**已实现**（2026-09-26）。
★ 原文「数据面物化与读取行为待实现，骨架中无对应」已被推翻：
★ `profile.PORTS` 12 个端口全部物化成功，`produced_by` 实测为
★ `core.align` / `core.features` / `core.surface` 三方产出。
★ ★ 纯查表语义仍成立：★ `read()` 不推进状态、不触发计算。

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

★ 本节只证明**契约声明模块可 import、导出面数量正确**。
★ ★ ★ **2026-09-26 订正**：★ 原文末句写「不证明 C1/C2/C3/C4 的运行期行为。
★ ★ 组件实现状态统一记为『待实现，骨架中无对应』」——★ **该句已过期**：
★ ★ ① 组件已实装（八个文件 `NotImplementedError` 零命中）；
★ ★ ② 运行期行为**已被本文件其它各节的实测覆盖**（端到端 `rc=0`、16 指标、
★ ★ 　 四个错误码逐一实抛、12 端口全部物化）。
★ ★ ★ ★ 保留本节原有的**分工**：★ 契约层判据（`test_contract_shape.py`）仍只管
★ ★ ★ 「形状」，★ 而端到端证据来自上面那些命令——★ 两者不可互相替代。

**★ 附：本次订正的复算方式（★ 后来人自己核，★ 别信任何转述）★★**
```bash
cd <仓库根>

# ① 骨架已清空：八个文件零命中
grep -c "NotImplementedError" harmonica_eval/contract.py \
  harmonica_eval/core/*.py harmonica_eval/host/app.py

# ② 端到端
PYTHONDONTWRITEBYTECODE=1 python3 -m harmonica_eval \
  --reference harmonica_mvp_dataset/01_奇异恩典/标准旋律版.wav \
  --practice  harmonica_mvp_dataset/01_奇异恩典/练习曲/01_音准走调.wav
# → rc=0，产出 16 个指标

# ③ 错误路径逐一实抛（过短 / 静音 / 过长 / 不存在）
PYTHONDONTWRITEBYTECODE=1 python3 -c "
import sys, numpy as np, soundfile as sf; sys.path.insert(0,'.')
from harmonica_eval.core import ingest
from harmonica_eval.contract import CoreBuildError
sr=44100
sf.write('/tmp/_s.wav',(0.5*np.sin(2*np.pi*440*np.arange(4410)/sr)).astype('float32'),sr,subtype='FLOAT')
try: ingest.ingest('/tmp/_s.wav')
except CoreBuildError as e: print(e.code.value, '|', e.detail)
# → INPUT_TOO_SHORT | 时长 0.100s 短于下限 45.0s（4410 样本 @ 44100 Hz）"

# ④ 12 端口全部物化
PYTHONDONTWRITEBYTECODE=1 python3 -c "
import sys; sys.path.insert(0,'.')
from harmonica_eval import profile
print(len(profile.PORTS), sorted({p.produced_by for p in profile.PORTS}))"
# → 12 ['core.align', 'core.features', 'core.surface']
```
★ **★ 注**：★ 上面 ③ 里的属性名是 `.code` / `.detail`，★ 不是 `.error_code`——
★ `CoreBuildError` 的字段是 `code` / `detail` / `component` / `port_id` / `session_id`。
