# CONTRACTS —— 契约冻结台账

> 本文件记录**哪些契约已冻结、哪些还没有，以及为什么**。
> 依据宪章 §9（可执行契约）、§15（成对版本化）、§45（状态模型）、§47.10（禁止提前冻结）。
>
> **原则：冻结一个契约，等于承诺下游可以依赖它。**
> 在上游未定前冻结，是把返工成本转嫁给所有下游组件。

---

## 0. 当前冻结状态总览

**OC1 已关闭，且裁定方式与初版相反**（见 `research/03-datapath-decision.md` §7）：

> **Core 预生成，端口清单封闭。算法适配 Core，不是 Core 适配算法。**
> 不做惰性计算、不做存储后端选型、不做 LRU 缓存。
> 原因：惰性计算要求 Core 为算法现场算数据，必须附带协商协议，
> 而那会让 Core 的外部接口变成**插件需求的函数**——正是要避免的反模式。

| 契约 | 覆盖 | 状态 |
| --- | --- | --- |
| **CONTRACT-SESSION-v1** | 会话状态、时间基准、音频格式 | ✅ **FROZEN** |
| **CONTRACT-ERRORS-v1** | 错误码与异常层次 | ✅ **FROZEN** |
| **CONTRACT-HOST-v1** | C1 → C2，7 个操作 | ✅ **FROZEN**（`acquire_surface` 返回内存数据面句柄） |
| **CONTRACT-ALGORITHM-DATA-v1** | C3 → 数据面，2 个操作 | ✅ **FROZEN**（`manifest()` / `read()`，纯查表、无副作用） |
| **CONTRACT-UI-v1** | C1 ↔ C4 投影与命令 | ✅ **FROZEN** |
| **CORE_PROFILE_V0.1** | **封闭端口清单**（12 个端口，写死） | ✅ **FROZEN** |

**所有契约均已冻结，无待定项。**

---

## 1. 为什么 OC1 只阻塞两个契约的一半

这是本次分层的一个关键判断，写下来供复核：

### 1.1 不依赖 OC1 的部分

| 内容 | 为什么与存储形态无关 |
| --- | --- |
| **会话状态 6 值** | `DATA_READY` 的语义是「数据面已按 profile 构建完毕并 Seal」。无论数据面在内存、在磁盘，还是根本没物化（惰性），该语义**都成立**。 |
| **时间基准 2 值** | 来自 `SPEC.md` §5.5「两轴分离」，是**产品需求**层面的强制（归一化会抹掉抢拍拖拍）。与实现无关。 |
| **音频格式** | mono / float32 / 44100 Hz 是 `CORE_PROFILE_V0.1` 的输入标准化契约。 |
| **错误码** | 失败**语义**（数据面不存在 / 数据面有效但算法失败 / 静默降级禁止）与存储无关。 |
| **UI 投影** | 只表达「可展示的序列与标量」，C4 永远看不到数据面。 |
| **Host 的 5 个操作** | `create_session` / `set_reference` / `set_practice` / `build_surface` / `status` / `destroy_session` —— 全是生命周期操作，不涉及数据面结构。 |

### 1.2 依赖 OC1 的部分

| 内容 | 为什么必须等 |
| --- | --- |
| `acquire_surface()` 的**返回类型** | 惰性实现下，句柄必须能表达"这次读取会触发计算"；流式实现下可能根本没有随机访问句柄。 |
| `read(port_id, range)` 的**签名与副作用语义** | 全物化 = 纯读取；惰性 = **有副作用**（触发计算）且可能失败；流式 = 可能不存在此操作。 |
| `SurfaceManifest` 的结构 | 惰性实现可能需要暴露"哪些端口已在内存"。 |

> **结论**：`HostContract` 与 `AlgorithmDataContract` 的**结构**（存在哪些操作）可以现在冻结，
> 因为「C1 不该有 align()」「算法不该能请求生成数据」这些**边界判断**与存储无关。
> 但它们的**签名细节**必须等 OC1。

---

## 2. 已冻结契约明细

### 2.1 CONTRACT-SESSION-v1 ✅

**文件**：`harmonica_eval/contract/session.py`
**产出**：`SessionState` · `TimelineBasis` · `AlignmentRepresentation` · `AudioFormat`

**为什么安全**：本文件刻意**只含不随 OC1 变化的词汇**。
凡依赖 OC1 的类型（端口描述符、缓冲视图、数据面清单、句柄）一律不在此处。

### 2.2 CONTRACT-ERRORS-v1 ✅

**文件**：`harmonica_eval/contract/errors.py`
**产出**：`ErrorCode`（12 个码）· `HarmonicaError` · `ContractViolation` · `CoreBuildError` · `AlgorithmError`

**强制语义**（来自 `COMPONENTS.md` §7）：

| 失败 | 归属 | 数据面 | 其他算法 |
| --- | --- | --- | --- |
| 输入不可解码 / 过短 / 静音 | C2 | **不存在** | 不启动 |
| 对齐无法建立有效映射 | C2 | **不存在** | 不启动 |
| 算法要求未知端口 | C1 判定 | 有效 | 正常 |
| 算法崩溃 / 非法结果 | C3 | 有效 | 正常 |
| **算法死循环** | C3 | 有效 | **会卡住（v0.1 已知缺口）** |
| 界面断开 | C4 | 有效 | 正常 |

**特别禁止**：`ALIGNMENT_UNRECOVERABLE` **不得**被降级为"逐点硬比继续跑"。
静默降级违反宪章 §5.6。

### 2.3 CONTRACT-HOST-v1 🟡

**文件**：`harmonica_eval/contract/host.py`
**产出**：`HostContract`（7 个操作）+ `FORBIDDEN_OPERATIONS`（10 个禁止方法名）

**已冻结的部分**：7 个操作的存在与语义、以及**禁止名单**。

`FORBIDDEN_OPERATIONS` 是一个**可执行的检查清单**：
若 `CONTRACT-HOST-v1` 上出现 `align` / `fft` / `prepare_for_*` / `register_algorithm` 等，
即说明编排权或算法知识泄漏进了 Core，深组件被破坏。
这份名单可直接被 Inspector General 用作断言。

### 2.4 CONTRACT-UI-v1 ✅

**文件**：`harmonica_eval/contract/ui.py`
**产出**：`UiView` · `UiSeries` · `UiScalar` · `UiCommand` · `UiCommandKind` · `UiProjectionPort`

**要点**：
- 与数据面契约同为「接口极小」：C4 只有 `snapshot()` / `submit()` 两个操作
- `UiCommandKind` 只有 6 个值 —— C4 **不能凭界面发明内核能力**
- `UiSeries` 必须携带 `timeline_basis` —— 否则节奏类展示会被 warped 轴误导
- 投影必须**已下采样**（宪章 §44.12：人类不得面对几千个文件）

### 2.5 CONTRACT-ALGORITHM-DATA-v1 🟡

**文件**：`harmonica_eval/contract/data_surface.py`
**产出**：`AlgorithmDataContract`（2 个操作）+ `REQUIRED_PORT_INVARIANTS`（4 条）

**已冻结的部分**：只存在 2 个操作；以及 4 条**与存储无关**的端口不变量：

1. 端口必须声明 `timeline_basis`
2. 端口必须声明 `sample_rate`（实测：采样率是 f0 结果的成因）
3. 端口必须声明 `units` 与 `dimensions`
4. 数据面**始终**含两份 aligned PCM（本仓自定保证，见 COMPONENTS.md §4.2）

**待 OC1**：`manifest()` / `read()` 的返回类型与副作用语义。

---

## 3. 已撤回的提前冻结

| 曾冻结内容 | 撤回原因 | 现状 |
| --- | --- | --- |
| `contract/types.py`（`PortDescriptor` / `BufferView` / `SurfaceManifest` / `SurfaceHandle` / `SessionHandle`） | 在 OC1 未定时就按「已物化的随机访问数据面」写下接口，属 §47.10 提前冻结 | `.spec/draft/DRAFT-FILE-010-types.py`，**禁止引用** |

撤回理由（详细）：接口形态**完全取决于**数据面怎么存/怎么算：

```text
全内存物化 → read(port_id, range) 立即返回 ndarray
mmap/磁盘  → 必须能返回分块视图，且要暴露"这段在不在内存"
惰性计算   → read 有副作用（触发计算），且可能失败
流式       → 根本没有 read(port_id, range)，而是 iter_chunks()
```

---

## 4. 验证

契约层必须满足宪章 §17「stub 可加载」：

```bash
python3 -c "import harmonica_eval.contract as c; print(len(c.__all__))"
```

实测结果：**import OK · 19 个公开符号**。
