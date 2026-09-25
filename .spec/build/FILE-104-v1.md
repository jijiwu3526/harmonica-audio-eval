# FILE-104 — harmonica_eval/core/surface.py

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/core/surface.py`
> 生成依据：`SPEC.md@v2.1` · `contract.py` · `profile.py@CORE_PROFILE_V0.1` · `COMPONENTS.md`
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-104 |
| 所属组件 | COMP-C2 Audio Core（COMPONENTS.md@v2 §4.2） |
| 层级 | L3（symbol / implementation） |
| 上游 | **调用方**：`harmonica_eval/core/api.py`（COMP-C2 对 `contract.HostContract` 的实现）。它是本文件 `build_surface` 的**唯一**调用者：在 `HostContract.build_surface(session_id)` 内部把三个上游产物传进来 —— ingest 阶段标准化后的 `reference` / `practice`（float32 mono PCM，1-D）、`profile.AUDIO.sample_rate`（int，Hz）、对齐阶段产出的 `warp_path`（int32[N, 2]）。**输入数据的产生者**是 ingest 阶段与对齐阶段；本文件不产生 PCM、不产生 warp_path、不做任何解码或对齐。 |
| 下游 | ① `harmonica_eval/algorithms/*.py`（COMP-C3）通过 `Surface.manifest()` 与 `Surface.read()` 两个操作读数据，这是算法能看到的全部数据入口；② `harmonica_eval/core/api.py` 消费 `build_surface` 的返回值，用 `manifest().sealed` 判定 `DATA_READY`，并在 `acquire_surface()` 里把 `Surface` 交给 C1；③ 端口数据由 `profile.PortSpec.produced_by` 指名的 core 端口生产模块产出，本文件向下调用它们并把结果汇总；④ 本文件向下依赖 `harmonica_eval/contract.py`（类型、异常、`FIELD_LAYOUTS`、`CONTENT_HASH_MAGIC`、`CORE_REQUIRED_PORTS`）与 `harmonica_eval/profile.py`（端口清单与预算常量）。 |
| 同层邻居 | `harmonica_eval/core/api.py`（实现 `HostContract` 的 7 个操作，会话状态机与资源释放）、`harmonica_eval/core/ingest.py`（解码 / 重采样 / 下混 / 时长与静音校验）、`profile.PortSpec.produced_by` 指名的端口生产模块（f0 / onset / rms / chroma 等特征的物化处）、`harmonica_eval/algorithms/dynamics.py` 等 C3 算法文件（数据面的消费者，不属于本文件）。 |

**你的权限**：只实现本文件。不得修改任何其他文件，不得修改契约，
不得新增端口，不得新增依赖。

---

## 2 · 这个文件为什么存在

本文件是 `contract.py` 中 `AlgorithmDataContract` 协议在 COMP-C2 侧的**唯一实现者**，
也是 SPEC.md@v2.1 中「Core 预生成、端口清单封闭、算法适配 Core」这条架构裁定的落地点。

追溯链：
- Product Intent：用户上传两段演奏（参考 + 练习），得到客观数值指标。指标必须**可复现**
  —— 同一对输入必须产出同一组数字，否则数字无法被信任、无法被回归验证。
- Requirement：`SPEC.md@v2.1` §5.5「两轴分离」要求数据面**同时**提供保留源时间（`REFERENCE`）
  与时间归一化（`WARPED`）两种表示，且每个端口必须声明自己挂在哪条轴上。
- Requirement：`CONTRACT-ALGORITHM-DATA-v1` 规定算法与 Core 之间只有 `manifest()` /
  `read()` 两个纯查表操作，`read()` 无副作用、不触发计算。

**删掉它会坏掉什么**（逐条，均为可观测的断裂）：

1. **C3 全部算法的一次性全断。** `Surface` 是 `AlgorithmDataContract` 的唯一实现。
   删掉它以后，C1 的 `acquire_surface()` 拿不到符合协议的句柄，
   `runtime` 传给每个算法的数据面参数为 `None`（或类型不符），
   所有算法在第一步 `manifest()` 就崩 —— 三个注册算法的结果集恒为空。
2. **`HostContract.build_surface()` 无法实现。** 该操作的契约后置条件是
   「状态 == DATA_READY，数据面不可变」。没有 `build_surface()` 函数就没有可 Seal 的对象，
   C2 的状态机永远停在 `INPUT_READY`，`RUN_ALGORITHMS` 命令在
   `contract.COMMAND_LEGALITY` 里对 `INPUT_READY` 非法 → 用户点「运行」被拒绝。
3. **「同一对输入 ⇒ 同一组数字」这条回归断言失去锚点。** 只有本文件为每个端口计算
   `content_hash`（算法见 `PortDescriptor.content_hash` 的冻结字节序列）。
   删掉它以后，profile 变了、端口内容变了、但端口的 `shape` / `dtype` 没变时，
   回归测试会**静默通过**，指标漂移无人发现。
4. **`read()` 的秒→帧换算规则失去唯一实现。** 该换算依赖每个端口自己的
   `PortDescriptor.hop_length`（`pitch.*` 与 `chroma.*` 用 `profile.ALIGN.hop_length`=2048，
   `rms.*` 用 `profile.MATERIALIZE.rms_hop_length`=256，两者相差 8×）。
   删掉它以后，各算法各自乘除 hop，同一段音频会算出**相差 8 倍时间窗**的数据，
   **且不会报错** —— 这正是 G5 修正要消灭的静默算错。
5. **「端口不存在必须抛错」这条硬约束失去执行点。** 若没有本文件，
   读不到端口的一方会返回空数组冒充成功，节奏指标在静音输入上恒为 0 而不报错 ——
   违反宪章 §5.6 No Silent Degradation。
6. **深组件边界瓦解。** `manifest()` 是 C3 了解数据面的唯一途径。
   删掉它以后，算法只能 import `profile.py` 直接枚举端口，C2 内部实现随即暴露给 C3，
    Core 无法在不破坏算法的前提下重组内部实现 —— `contract.py` 中
   「DESIGN-RULING：Core 预生成，端口清单封闭」这条裁定失效。

反面结论：**答得出**，故本文件应当存在。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：

- 标准库：
  - `from __future__ import annotations`（文件首行之后的第一个语句）
  - `hashlib` —— 计算 `content_hash`
  - `math` —— `math.prod` 计算 `element_count`
  - `typing` —— `Mapping`、`Sequence`、`Any`（`typing.Mapping` / `typing.Sequence` 用于函数签名）
  - `collections.abc` —— `Mapping as MappingABC`（运行期 `isinstance` 检查 `generate_all_ports` 的返回值）
  - `types` —— `types.MappingProxyType`（§4.2 `build_descriptor` 用它把描述符映射包成只读）

    ★★ **本版补入（第三轮盲审 A 的 FINDING-9）：上一版漏了 `types`。** ★★

    本节开头声明「本清单必须**穷举**，不许出现「等」「之类」」，
    但 §4.7 第 12 步**强制**要求 `import types`，而它不在清单里；
    §4.7 还自我豁免说「这是标准库，属于 §3 允许清单的补充」——
    那句话**否定了 §3 的穷举性**，两份表述互斥。已把 `types` 写入清单，
    并删除 §4.7 的自我豁免表述。
- 第三方：
  - `numpy` —— 数组操作（`np.asarray` / `np.ndarray` / `np.dtype` / `np.product` 的替代）
  - `numpy.typing` —— 仅用于 `npt.NDArray` 类型标注
- 本包内：
  - `harmonica_eval.contract` 的 **8 个名字**，一个不多：
    `AlgorithmDataContract`、`AudioFormat`、`BufferView`、`PortDescriptor`、
    `SurfaceManifest`、`ContractViolation`、`CoreBuildError`、`ErrorCode`；
    以及 **2 个模块级常量/表**：`FIELD_LAYOUTS`、`CONTENT_HASH_MAGIC`。
  - `harmonica_eval.profile` 的 **7 个名字**：
    `PORTS`、`PORT_INDEX`、`BUDGET`、`AUDIO`、`ALIGN`、`MATERIALIZE`、`PROFILE_VERSION`。

    ★★ **本版更正：原写「6 个名字」，而下方列了 7 个。** ★★

    **原写**：「`harmonica_eval.profile` 的 **6 个名字**：」。
    **为什么错**：紧随其后的列举共 **7** 个反引号名字 —— `PORTS`、`PORT_INDEX`、
    `BUDGET`、`AUDIO`、`ALIGN`、`MATERIALIZE`、`PROFILE_VERSION`，
    数字与列举差 1；实现者按数字写 `__all__`、按列举写 import，
    会得到两份不一致的清单，而本清单必须**穷举**（见下方 ★）。
    **改成**：**7 个名字**，与本行列举的 7 条一一对应。
  - `profile.PortSpec.produced_by` 指名的 core 端口生产模块，**只能**通过
    `importlib.import_module` 按其**点分模块路径字符串**动态取得，
    或由 `harmonica_eval/core/` 内的直接模块 import 取得；取到的可调用对象的实参
    见 §4.4 的逐结构键实参表。

    ★★ **本版更正：删去已作废的四参签名约定。** ★★

    **原写**：「取到的可调用对象签名约定为
    `(reference, practice, sample_rate, warp_path) -> NDArray`」。
    **为什么错**：§4.4 已把该四参约定整段标为「**上一版原文（已作废）**」，
    并实测指出三个生产者模块的实际签名（1–3 参）与它**没有一个对得上**，
    且该约定里既无 `port_id` 也无 `side`，无法区分同一生产者的两侧端口。
    留在 §3 等于给实现者两份互斥的调用约定。
    **改成**：不在此处复述签名，改为指向 §4.4 的逐结构键实参表（唯一权威口径）。

**禁止 import**：

- 禁止 import `harmonica_eval.core.api`（会造成 api → surface → api 的循环 import，
  且 Surface 不得反向持有会话句柄）。
- 禁止 import `harmonica_eval.core.ingest`（本文件不负责解码；PCM 由上游传入）。
- 禁止 import `harmonica_eval.algorithms` 及其任何子模块（C3 是数据面的**消费者**，
  Core 不得依赖算法 —— 违反 `contract.py` 的 DESIGN-RULING）。
- 禁止 import `harmonica_eval.host` 及其任何子模块（C1 是调用方，反向依赖即层次倒置）。
- 禁止 import `harmonica_eval.cockpit` 及其任何子模块（C4 与本组件无任何边）。
- 禁止 import `harmonica_eval.contract` 中的下列名字（它们有各自的归属组件）：
  `SessionState`、`TimelineBasis`、`AlignmentRepresentation`、
  `AlgorithmResultEnvelope`、`HostContract`、`CORE_REQUIRED_PORTS`、
  `UNITS_VOCABULARY`、`HarmonicaError`、`AlgorithmError`、
  `UiScalar`、`UiSeries`、`UiView`、`UiCommand`、`UiCommandKind`、
  `UiProjectionPort`、`COMMAND_LEGALITY`、`COMMAND_EFFECTS`、`UI_PAYLOAD_KEYS`、
  `FORBIDDEN_OPERATIONS`。
- 禁止 import 任何音频 I/O 或解码库：`soundfile`、`librosa`、`audioread`、
  `pydub`、`scipy.io.wavfile`、`wave`、`av`、`ffmpeg` 的任何 Python 绑定。
- 禁止 import 任何 DSP 或数值算法库：`scipy`（全部子模块）、`sklearn`、`torch`、
  `numba`、`cython`、`jax`、`cupy`、`numpy.fft` 之外的 FFT 实现。
- 禁止 import 任何 I/O 与进程库：`os`、`os.path`、`io`、`pathlib`、`subprocess`、
  `socket`、`shutil`、`tempfile`、`requests`、`urllib`、`http`。
- 禁止 import 任何并发库：`threading`、`multiprocessing`、`asyncio`、`concurrent.futures`。
- 禁止 import 任何序列化库：`pickle`、`json`、`yaml`、`msgpack`、`csv`。
- 禁止 import 任何日志与配置库：`logging`、`warnings`、`configparser`、`dotenv`。
- 禁止 import 任何测试库：`pytest`、`unittest`、`hypothesis`、`numpy.testing`。
- 禁止 import `time`、`datetime`（时间戳会让 `content_hash` 与构建结果不可复现）。
- 禁止在模块顶层执行任何非声明语句（例外仅两类：`__all__` 赋值，以及 §4.0
  **要求**的列号常量核验断言 `assert FIELD_LAYOUTS["notes"][0] == "onset_sec"`
  与 `assert FIELD_LAYOUTS["warp_path"][0] == "reference_frame"`；
  除此之外不得有函数调用、常量计算、文件读取）。

  ★★ **本版更正：原例外只列 `__all__` 赋值，与 §4.0 的强制断言互斥。** ★★

  **原写**：「除 `__all__` 赋值外，不得有函数调用、常量计算、文件读取」。
  **为什么错**：§4.0 明文**要求**「实现**必须**在模块导入时用一次断言核验」
  `assert FIELD_LAYOUTS["notes"][0] == "onset_sec"` 与
  `assert FIELD_LAYOUTS["warp_path"][0] == "reference_frame"`，
  「核验失败即 `ImportError` 级别缺陷，**不得**静默继续」。
  按原句字面执行，这两条顶层断言本身就落在被禁止的「非声明语句」里 ——
  写则违反本行，不写则违反 §4.0，实现者被卡死。
  **改成**：把例外从「`__all__` 赋值」扩展为「`__all__` 赋值 + §4.0 要求的
  列号常量核验断言」，断言原文照抄 §4.0，不得增删、不得改成别处的调用。

★ 本清单必须**穷举**，不许出现「等」「之类」。

---

## 4 · 你要实现什么（行为规格）

### 4.0 模块级常量（实现必须在模块顶层定义，数值写死）

```python
_SAMPLE_RATE_FREE_PREFIXES: frozenset[str] = frozenset({"chroma", "warp_path", "notes"})
_NOTES_FIELD_ONSET_SEC: int = 0        # FIELD_LAYOUTS["notes"] 中 "onset_sec" 的列号
_WARP_FIELD_REFERENCE_FRAME: int = 0   # FIELD_LAYOUTS["warp_path"] 中 "reference_frame" 的列号
_DURATION_ROUND_DIGITS: int = 6        # reference/practice 时长的小数位
```

以上三个列号常量**必须**与 `contract.FIELD_LAYOUTS` 对得上；
实现**必须**在模块导入时用一次断言核验（`assert FIELD_LAYOUTS["notes"][0] == "onset_sec"`
与 `assert FIELD_LAYOUTS["warp_path"][0] == "reference_frame"`），
核验失败即 `ImportError` 级别缺陷，**不得**静默继续。

**冻结数值核验清单**（实现必须在 `assert_profile_integrity()` 之外另行核验，
任一条不符即抛 `CoreBuildError(CORE_BUILD_FAILED)`）：

  - 采样率取值：`profile.AUDIO.sample_rate` 必须等于 **44100**（Hz）。
  - 时长上限：`profile.AUDIO.max_duration_sec` 必须等于 **120.0**（秒）。
  - 帧移：`profile.ALIGN.hop_length` 必须等于 **2048**（采样点），
    用于 `pitch.*` 与 `chroma.*`；`profile.MATERIALIZE.rms_hop_length`
    必须等于 **256**（采样点），用于 `rms.*`。
  - 预算：`profile.BUDGET.max_surface_bytes` 必须等于 **536870912**（字节，512 MiB）。
  - 端口前缀分类：`_SAMPLE_RATE_FREE_PREFIXES` 恰为
    `{"chroma", "warp_path", "notes"}` 三个。
  - 列号常量：`_NOTES_FIELD_ONSET_SEC == 0` 且
    `_WARP_FIELD_REFERENCE_FRAME == 0`。

---

### 4.0.1 冻结数值核验清单（§4.0 的续，非独立节）

★★ **本版更正（第三轮盲审 A 的 FINDING-12）：本节原编号为 `### 4.1`，
与 §4.8 的 `### 4.1`… 重号，且两次标题逐字相同，导致
「见 §4.1」这类交叉引用无法判定指向。已改为 §4.0.1。** ★★

**`port_prefix` 的唯一口径**（本文件内部助手，**不是**骨架里的公开符号 ——
实测 `core.surface.port_prefix` 不存在；它由本文件自行定义）：

取 `port_id` 中**第一个 `.` 之前**的子串；若不含 `.`，则返回整个 `port_id`。
例：`"pcm.mapped.reference"` → `"pcm"`；`"warp_path"` → `"warp_path"`；
`"pitch.practice"` → `"pitch"`。

**以下是本文件必须在导入期核验的冻结数值**（§4.0 要求的断言，见 §3 的例外条款）：

  - 采样率取值：`profile.AUDIO.sample_rate` 必须等于 **44100**（Hz）。
  - 时长上限：`profile.AUDIO.max_duration_sec` 必须等于 **120.0**（秒）。
  - 帧移：`profile.ALIGN.hop_length` 必须等于 **2048**（采样点），
    用于 `pitch.*` 与 `chroma.*`；`profile.MATERIALIZE.rms_hop_length`
    必须等于 **256**（采样点），用于 `rms.*`。
  - 预算：`profile.BUDGET.max_surface_bytes` 必须等于 **536870912**（字节，512 MiB）。
  - 端口前缀分类：`_SAMPLE_RATE_FREE_PREFIXES` 恰为
    `{"chroma", "warp_path", "notes"}` 三个。
  - 列号常量：`_NOTES_FIELD_ONSET_SEC == 0` 且
    `_WARP_FIELD_REFERENCE_FRAME == 0`。

---

### 4.8 `port_prefix(port_id: str) -> str`

- **输入**：`port_id: str`。取值域：`profile.PORTS` 中任一 `PortSpec.port_id`，
  或任意字符串。不得为 `None`（传 `None` 抛 `TypeError`，由 Python 本身抛出）。
- **输出**：`str`，第一个 `.` 之前的子串；无 `.` 时返回原串。空字符串返回 `""`。
- **算法口径**：`port_id.split(".", 1)[0]`。**不得**用 `rsplit`，不得用
  `partition` 之外的其他切法；不得做大小写归一，不得做 strip。
- **边界**：传 `""` → 返回 `""`（**不抛错**）。传 `"abc."` → 返回 `"abc"`。
  传 `".abc"` → 返回 `""`。
- **不变量**：对任意 `port_id`，`port_prefix(port_id)` 是 `port_id` 的前缀；
  且 `port_prefix(port_prefix(p)) == port_prefix(p)`（幂等）。

---

### 4.2 `build_descriptor(port_id: str, data: npt.NDArray, sample_rate: int) -> PortDescriptor`

- **输入**：
  - `port_id: str` —— 必须是 `profile.PORT_INDEX` 的键。不在其中 → 抛 `KeyError`
    （由 `PORT_INDEX[port_id]` 的查表直接抛出，**不得**捕获后改成别的异常类型）。
  - `data: npt.NDArray` —— 已生成的端口数组。取值域：任意 `numpy.ndarray`，
    其 `dtype` 必须与 `PORT_INDEX[port_id].element_type` 一致（见下方算法口径第 5 步）。
  - `sample_rate: int` —— Hz，取值域为正整数（`profile.AUDIO.sample_rate`）。
- **输出**：`contract.PortDescriptor`（frozen dataclass），字段逐项为：

  | 字段 | 取值来源（唯一口径） |
  | --- | --- |
  | `port_id` | 入参原样，**不做任何归一化** |
  | `schema_version` | `profile.PROFILE_VERSION`（例：`"CORE_PROFILE_V0.1"`）。**不得**写死字符串字面量 |
  | `element_type` | `str(data.dtype)`，例：`"float32"` / `"int32"` / `"int64"`。**不得**回抄 `PortSpec.element_type`（那会掩盖数组 dtype 与 profile 不一致的缺陷） |
  | `dimensions` | `tuple(PORT_INDEX[port_id].dimensions)`，原样拷贝为 `tuple`（不得截断、不得重排） |
  | `shape` | `tuple(int(x) for x in data.shape)` —— 必须转成 Python `int`，**不得**留 `numpy.int64`（那会破坏 dataclass 的 `==` 与哈希） |
  | `units` | `PORT_INDEX[port_id].units`，原样 |

  #### ★ `shape` 的来源：运行期事实，不是静态配置（负责人裁定 2026-09-24）

  **`PortDescriptor.shape` 在 `profile.PortSpec` 中没有对应字段，这是有意的。**

  理由：`shape` 依赖音频实际时长。例如 `chroma.lowres.*` 的
  `dimensions=('frame','bin')`、`hop_length=2048`，其帧数为
  `ceil(n_samples / 2048)` —— 而 `n_samples` **只存在于 C2 内部**，
  静态 profile 里没有。**把它写进 `PortSpec` 等于把运行时事实伪装成静态配置。**

  **因此裁定：`shape` 由 C1 向 C2 询问获得，不从 `PortSpec` 静态推导。**

  **载体已经存在，不新增任何操作**（`FILE-003` §4.15「port 上不得再增第三个操作」
  继续有效）：

  ```
  Surface.manifest() -> SurfaceManifest.ports: Mapping[str, PortDescriptor]
  ★ C1 只需 manifest()，即可拿到每个端口的 shape
  ```

  ★ **实现约束**：
  - `build_descriptor()` 必须用**实际数组的 `data.shape`** 填充（见上表），**不得**用
    `dimensions` 里的语义名去反推尺寸 —— 语义名不含尺寸（见 `contract.py` §G6 修正）
  - C1 在 `snapshot()` 投影 `port_summary` 时，`shape` 直接取自 `manifest()`，
    **不得**自行推导
  - 若某端口尚未生成数据（`manifest().sealed` 为 False），
    **不得**填一个占位 shape 冒充 —— 按既有失败路径显式失败
  | `field_names` | 见下方「field_names 三条规则」 |
  | `timeline_basis` | `PORT_INDEX[port_id].timeline_basis`，**必填**，不得依赖默认值 |
  | `hop_length` | `PORT_INDEX[port_id].hop_length`，原样（含 `0`） |
  | `sample_rate` | 见下方「sample_rate 两条规则」 |
  | `content_hash` | 见下方「content_hash 冻结算法」 |

  **field_names 三条规则**（按序判定，命中即停）：
  1. 若 `len(PORT_INDEX[port_id].dimensions) == 1` → `field_names = ()`（空元组）。
  2. 否则若 `port_prefix(port_id) in contract.FIELD_LAYOUTS`
     → `field_names = tuple(FIELD_LAYOUTS[port_prefix(port_id)])`。
     **必须**从 `FIELD_LAYOUTS` 取，**严禁**在本文件内硬编码
     `("f0_hz", "voiced", "confidence")` 这类字面量。
  3. 否则 → 抛 `ContractViolation(code=ErrorCode.CORE_BUILD_FAILED, port_id=port_id,
     detail="multi-dimensional port has no FIELD_LAYOUTS entry")`。

  **sample_rate 两条规则**（按序判定，命中即停）：
  1. 若 `port_prefix(port_id)` 是 `"chroma"`、`"warp_path"`、`"notes"` 三者之一
     → `sample_rate = 0`。
  2. 否则 → `sample_rate = int(sample_rate)`（端口与采样率有关，填传入值）。

  **content_hash 冻结算法**（逐字节照做，不得增删任何一次 `update`，不得改变顺序）：

  ```python
  h = hashlib.sha256()
  h.update(CONTENT_HASH_MAGIC)                                  # b"harmonica-eval/surface/v1\x00"
  h.update(port_id.encode("utf-8"))
  h.update(str(data.dtype).encode("utf-8"))                     # element_type
  h.update(np.asarray(data.shape, dtype="<i8").tobytes())        # 小端 int64
  h.update(data.tobytes(order="C"))                             # C 序，原始 dtype
  content_hash = h.hexdigest()                                  # 64 个小写十六进制字符
  ```

  三条必须同时成立的性质（缺一即为缺陷）：
  - **含 shape 与 dtype**：否则 `(2,3)` 与 `(3,2)` 同 hash。
  - **固定小端**：`np.asarray(shape, dtype="<i8")`。在**大端**机器上
    `np.asarray(shape, dtype="<i8")` 会做字节序转换，结果与 x86 一致。
    **不得**使用 `dtype="i8"` 或 `dtype=np.int64`（那是本机序）。
  - **C 序展平**：`data.tobytes(order="C")`。**不得**用 `order="K"` 或 `order="F"`。
  注意：`data.tobytes()` 按数组的**逻辑值**输出，对非连续视图
  （如 `data[::2]`）与对 `np.ascontiguousarray(data)` 的结果**相同** —— 这是
  该算法可跨实现复现的前提，实现者**不得**改成 `data.data.tobytes()`（那会踩到 padding）。

- **边界**（逐条给返回值）：
  - `data` 为 0 元素数组（`shape == (0,)` 或 `(0, 3)`）→ **正常返回**描述符，
    `content_hash` 仍按上述算法计算（空字节序列参与哈希）。**不抛错**。
  - `data` 为单元素数组（`shape == (1,)`）→ 正常返回。
  - `data` 含 `NaN` → **不检查 `NaN`，不抛错**。理由：本函数只做描述与指纹，
    `NaN` 的合法性由端口生产模块负责；此处抛错会让 `read()` 的纯查表语义
    被构建期的数值检查污染。
  - `data` 为 `Inf` → 同上，不检查、不抛错。
  - `data` 为**非连续视图** → 正常返回；`content_hash` 按逻辑值计算（见上）。
  - `data` 为 0 维数组（`shape == ()`）→ 正常返回，`shape = ()`。
  - `sample_rate = 0` 传入且端口属于 `pcm` / `rms` / `pitch` 前缀
    → **不抛错**，原样填 `0`。`sample_rate` 的合法性由 §5 的
    `build_surface` 入口检查（见 §5 第 2 行），不在本函数重复检查。
- **不变量**：
  - `descriptor.shape` 与 `data.shape` 逐元素相等，且元素类型为 `int`。
  - `descriptor.element_type == str(data.dtype)`。
  - `len(descriptor.field_names) == 0` 当且仅当 `len(descriptor.dimensions) == 1`。
  - 同一 `(port_id, data)` 输入两次调用返回的 `content_hash` **逐字符相同**。
  - `descriptor.port_id` 与入参 `port_id` 逐字符相同。

---

### 4.3 `seal(data: npt.NDArray) -> npt.NDArray`

- **输入**：`data: npt.NDArray`。取值域：任意 `numpy.ndarray`。
- **输出**：**同一个对象**（`out is data` 为 `True`），不拷贝、不改变 `dtype`、
  不改变 `shape`、不改变 `strides`、不改变数据字节。
- **算法口径**：唯一一条语句 `data.setflags(write=False)`，随后 `return data`。
  在调用前后，`data.flags.writeable` 必须由 `True` 变为 `False`。
  **不得**使用 `data.copy()`、`np.ascontiguousarray`、`data.view()`、
  `np.frombuffer` 或任何会产生新对象的写法 —— 会产生新对象即违反
  `BufferView` 的「所有权始终属于 C2」。
- **边界**：
  - 空数组（`shape == (0,)`）→ 正常 Seal，`writeable` 变 `False`。
  - 单元素数组 → 正常 Seal。
  - 含 `NaN` → 正常 Seal（`setflags` 与数值无关）。
  - 已经是只读（`writeable` 已为 `False`）→ **幂等**，再次调用返回同一对象，
    不抛错。
  - `data` 是**其他数组的视图**（`data.base is not None`）→ 对视图调
    `setflags(write=False)` 只影响该视图对象，**不影响** base 数组。
    这是 numpy 的既有语义，本文件**不**对 base 做任何处理。
  - `data` 不可写的原因来自只读 buffer（如 `np.frombuffer(b"...")`）→
    调用成功，`writeable` 保持 `False`。
- **不变量**：
  - 返回后 `out.flags.writeable is False`。
  - 返回后对 `out[0] = 0.0` 的任何写入尝试抛 `ValueError`
    （消息含 `"read-only"`；**不得**捕获或包装该异常）。
  - `out is data`。

---

### 4.4 `generate_all_ports(reference, practice, sample_rate, warp_path) -> Mapping[str, npt.NDArray]`

- **输入**：
  - `reference: npt.NDArray` —— float32、mono、1-D、C 连续。取值域：样本值
    在 `[-1.0, 1.0]`（超出不检查、不裁剪）；长度单位是**采样点**，
    必须满足 `len(reference) == round(reference_duration_sec * sample_rate)`。
  - `practice: npt.NDArray` —— 同上，长度**可以**与 `reference` 不同
    （那是时间归一化端口存在的理由）。
  - `sample_rate: int` —— Hz，取值域为正整数，必须等于 `profile.AUDIO.sample_rate`。
  - `warp_path: npt.NDArray` —— int32、形状 `(N, 2)`、`N >= 2`，
    第 0 列 = `reference_frame`，第 1 列 = `practice_frame`
    （顺序取自 `contract.FIELD_LAYOUTS["warp_path"]`）。
    取值域：两列均**非递减**，且
    `reference_frame ∈ [0, len(reference))`、`practice_frame ∈ [0, len(practice))`。
- **输出**：`Mapping[str, npt.NDArray]`，实现在**必须**返回普通 `dict`。
  键集合与 `profile.PORT_INDEX` 的键集合**完全一致**：
  `set(返回值的键) == set(profile.PORT_INDEX.keys())`。
  多一个键或少一个键都抛 `CoreBuildError(CORE_BUILD_FAILED)`（见 §5）。
- **算法口径**：
  1. `expected = set(profile.PORT_INDEX.keys())`。
  2. 对 `port_id in profile.PORTS`（**按 `PORTS` 元组的声明顺序**遍历，
     `PORTS` 是 `tuple[PortSpec, ...]`，`PORT_INDEX` 是它的字典投影 ——
     两份必须一致）。
  3. 每个端口的生成者由 `PortSpec.produced_by` 指名。实现**不得**在本文件内
     另写特征提取代码；只做一次查表调用。
  4. **调用约定（★ 本版重写，上一版是错的，且不可满足）**

     ★★ **上一版原文（已作废）**：
     > 「调用约定（**唯一**）：生成者可调用对象接收**位置参数 4 个**，
     > 顺序为 `(reference, practice, sample_rate, warp_path)`，返回一个
     > `numpy.ndarray`。」

     **为什么它不可满足**（实测，不是推演）：三个生产者模块的**实际签名**
     与这个四参约定**没有一个对得上**：

     ```
     core.features.materialize_pitch (samples, sample_rate)          # 2 参
     core.features.materialize_rms   (samples)                       # 1 参
     core.features.materialize_chroma(samples, sample_rate)          # 2 参（BLOCK-9 修正）
     core.features.materialize_notes (pitch, rms, sample_rate)       # 3 参，且要中间量
     core.align.align                (reference, practice)           # 2 参
     ```

     三个不可满足点：
     1. **参数个数**：约定要 4 个，实际 1–3 个。
     2. **参数语义**：约定第 1 个是 `reference`，而 `materialize_*` 第 1 个是
        `samples`（**单侧**的样本，不是两侧）。
     3. **★ 最根本**：`pitch.reference` 与 `pitch.practice` 的 `produced_by`
        **完全相同**（都是 `core.features`），而 `materialize_pitch` 一次只吃
        **一侧**的 `samples`。四参约定里既没有 `port_id`、也没有 `side`，
        所以**无法区分**这次调用是在为哪一侧、哪个端口生产。
        `notes.*` 更严重 —— 它需要 `pitch` / `rms` 作**中间量**，
        而中间量根本不在参数表里。

     **本版冻结的正确约定**：`core.surface` 维护一张**显式的端口→生产者派发表**，
     而不是把一个四参签名硬套到三个语义完全不同的模块上。

     ★★ **第三版更正（P2 管线审查 F3）：派发表的键不得是端口 id 字面量。** ★★

     上一版我写「键 = `port_id`」，并给了一张逐行写死端口 id 的表。
     **那与 INV-104-1 直接互斥** —— 该不变量要求 `surface.py` 源码里
     `"pcm.mapped"` / `"pitch."` / `"chroma."` / `"rms."` / `"notes."`
     五个字面量的命中数为 **0**。按上一版写，8 个特征端口的分派无法实现。
     （这条是我自己引入的，P2 审查抓到。）

     **本版冻结的正确约定**：派发表用**结构键**，键取自 `PortSpec` 的字段，
     **不是**端口名字面量。

     | 项 | 规定 |
     | --- | --- |
     | 派发表的形态 | 模块级常量 `PRODUCER_DISPATCH: Mapping[tuple, Callable]`，**键 = `(produced_by, units, dimensions, timeline_basis)`**，值 = 真实的生产者可调用对象 |
     | 为什么这个键 | 实测：该四元组在 12 个端口上给出 **7 个互异键**，恰好等于「生产者 × 产物种类」的个数；剩下 5 对靠**侧别后缀**区分（见下） |
     | 键集合 | 必须**恰好**等于 `{(s.produced_by, s.units, s.dimensions, s.timeline_basis) for s in profile.PORTS}`（穷举，不得少、不得多） |
     | 调用形态 | `PRODUCER_DISPATCH[_key(spec)](...)`，**按每个生产者自己的真实签名**传参（见下表） |
     | 侧别 | 由 `port_id.rsplit(".", 1)[-1]` 取值：`"reference"` 喂参考样本、`"practice"` 喂练习样本。**这两个词不在 INV-104-1 的禁用字面量里**，可安全使用 |
     | 中间量 | `notes.*` 依赖的 `pitch` / `rms`，取**同一次构建中已经产出的**中间量。**不得**重算 |
     | 遍历顺序 | **必须**按 `PORTS` 元组的声明顺序；且 `notes.*` 排在 `pitch.*` / `rms.*` **之后**（依赖顺序，见下） |
     | 自检 | 构建开始时断言 `set(PRODUCER_DISPATCH) == {_key(s) for s in profile.PORTS}`，不等 → `CoreBuildError(CORE_BUILD_FAILED)` |

     **实测的 7 个结构键**（由 `profile.PORTS` 现算，不是手抄）：

     | `(produced_by, units, dimensions, timeline_basis)` | 覆盖的端口 | 生产者 |
     | --- | --- | --- |
     | `("core.align", "index", ("warp_point","axis"), REFERENCE)` | `warp_path` | `core.align.align` |
     | `("core.features", "hz", ("frame","field"), REFERENCE)` | `pitch.reference` / `pitch.practice` | `core.features.materialize_pitch` |
     | `("core.features", "rms", ("frame",), REFERENCE)` | `rms.reference` / `rms.practice` | `core.features.materialize_rms` |
     | `("core.features", "chroma", ("frame","bin"), REFERENCE)` | `chroma.lowres.reference` / `chroma.lowres.practice` | `core.features.materialize_chroma` |
     | `("core.features", "index", ("note","field"), REFERENCE)` | `notes.reference` / `notes.practice` | `core.features.materialize_notes` |
     | `("core.surface", "amplitude", ("sample",), REFERENCE)` | `pcm.mapped.reference` / `pcm.mapped.practice` | **纯转发入参**：`reference` / `practice` 原样登记 |
     | `("core.surface", "amplitude", ("sample",), WARPED)` | `pcm.warped.practice` | **索引重排**：按 `warp_path` 第 1 列重排 `practice`（见下） |

     > 注意 `pcm.mapped.*` 与 `pcm.warped.practice` 靠 **`timeline_basis`** 分开
     > （REFERENCE vs WARPED）—— 这正是该字段存在的理由之一。

     **冻结的派发语义（按结构键，实现者不得增删改）**：

     下表**不写端口 id**（INV-104-1 禁止源码里出现那些字面量），
     只写「结构键 → 生产者 → 实参怎么算」。侧别由后缀决定（见上表）。

     | 结构键（见上表） | 生产者 | 实参 |
     | --- | --- | --- |
     | `core.align` 那一行 | `core.align.align` | `(reference, practice)` |
     | `hz` + `("frame","field")` | `core.features.materialize_pitch` | `(该侧样本, sample_rate)` |
     | `rms` + `("frame",)` | `core.features.materialize_rms` | `(该侧样本,)` |
     | `chroma` + `("frame","bin")` | `core.features.materialize_chroma` | `(该侧样本, sample_rate)` |
     | `index` + `("note","field")` | `core.features.materialize_notes` | `(同侧已产出的 pitch, 同侧已产出的 rms, sample_rate)` |
     | `core.surface` + REFERENCE | **纯转发** | 入参 `reference` / `practice` 原样登记（零计算） |
     | `core.surface` + WARPED | **索引重排** | 见 §4.4「索引重排的冻结口径」 |

     > **「该侧样本」怎么取**：`side = port_id.rsplit(".", 1)[-1]`；
     > `side == "reference"` → 参考样本，`side == "practice"` → 练习样本。
     > `warp_path` 没有侧别后缀，它同时要两侧（唯一一个）。
     >
     > **「同侧已产出的」怎么取**：中间量存在 `generate_all_ports` 的局部
     > dict 里。取用前断言该键已存在，否则 `CoreBuildError(CORE_BUILD_FAILED)`
     > —— 这同时是依赖顺序的自检。
     >
     > ★★ **更正（第三轮盲审 B 的 BLOCK-10）：中间 dict 的键必须是
     > `(结构键, side)` 二元组，不能是纯结构键。** ★★
     >
     > **为什么**：实测 12 个端口只映射到 **7 个互异结构键** ——
     > 有 **5 对**端口的四元组**完全相同**：
     >
     > | 结构键 | 共用它的两个端口 |
     > | --- | --- |
     > | `core.surface` + amplitude + `("sample",)` + REFERENCE | `pcm.mapped.reference` / `pcm.mapped.practice` |
     > | `core.features` + hz + `("frame","field")` | `pitch.reference` / `pitch.practice` |
     > | `core.features` + rms + `("frame",)` | `rms.reference` / `rms.practice` |
     > | `core.features` + chroma + `("frame","bin")` | `chroma.lowres.reference` / `chroma.lowres.practice` |
     > | `core.features` + index + `("note","field")` | `notes.reference` / `notes.practice` |
     >
     > 若用纯结构键，后写的**练习侧**会覆盖**参考侧**。
     > 而 `materialize_notes` 要「同侧已产出的 pitch」——
     > 它会**静默拿到练习侧的音高去算参考侧的音符**，
     > **不报错、不抛异常，产出错的数据面**。
     > 这是"静默算错"，比"写不出来"危险得多。
     >
     > **冻结写法**：`buf[(struct_key, side)] = arr`，
     > `side` 取自 `port_id.rsplit(".", 1)[-1]`（`warp_path` 无后缀，
     > 它不进这个 dict，单独持有）。取用恒为 `buf[(struct_key, side)]`。

     ★★ **`pcm.*` 三个端口的生产者 —— 已裁定（负责人 2026-09-24 批准）** ★★

     **裁定结果**：`pcm.mapped.*` 是 **`ingest` 产物的纯转发**，由
     `generate_all_ports` 直接登记，**不是重采样**；`pcm.warped.practice`
     由 `core.surface` 按 `warp_path` 做**索引重排**（不是重采样）。
     两条都落在 `profile` 冻结的 `produced_by="core.surface"` 之内 ——
     **不改任何冻结配置**。

     **为什么 `pcm.mapped.*` 是纯转发（实测依据）**：

     `generate_all_ports(reference, practice, sample_rate, warp_path)` 的
     `reference` / `practice` 两个入参，**就是阶段 1（INGEST）交给阶段 2 的
     规范化 PCM**（见 `FILE-105-v1.md` 阶段 1→2 的传递）。
     因此：

     ```
     pcm.mapped.reference  ≡  reference     # 同一个对象，零计算
     pcm.mapped.practice   ≡  practice      # 同一个对象，零计算
     ```

     `profile.PORT_INDEX["pcm.mapped.*"].units == "amplitude"`、
     `dimensions == ("sample",)`、`hop_length == 0` —— 全部与"按采样点索引的
     原始 PCM"一致。**没有任何数值运算**，所以不构成重采样，
     与 §7「本文件不实现任何重采样算法」**不冲突**。

     **为什么 `pcm.warped.practice` 由本文件做索引重排**：

     - 它必须「与参考**等长**」（`rationale` 原文），长度改变 ⇒ 必须动样本；
     - 但它**当前没有任何算法消费**。算法清单不来自框架侧硬绑元组；当前
       插件需求以装配期经 `algorithms.registry.Registry` 显式注册的
       `PluginSpec.required_inputs` / `optional_inputs` 为权威，它们不含
       `pcm.warped.practice`。它是**数据面保证**（`rationale` 已如实标注），
       不是某个插件的必需输入；
     - `align()` 只返回 `warp_path`（实测返回注解 `npt.NDArray`），
       不产 PCM ⇒ 唯一持有 `warp_path` 又负责装配的地方就是本文件。

     **索引重排的冻结口径**（唯一，实现者不得自选）：

     ★★ **必须做两级换算：帧网格 → 采样点网格。** ★★

     `warp_path` 是 DTW **帧**网格上的映射（行数 = 参考**帧数**），
     而 `pcm.warped.practice` 的 `dimensions == ("sample",)`
     —— 它是**采样点**序列，必须与参考的**采样点数**等长。
     两者差 `ALIGN.hop_length` 倍（本 profile = **2048**）。

     ```
     hop = profile.ALIGN.hop_length          # 2048
     n_ref_samples = len(reference)          # 参考采样点数
     n_prac_samples = len(practice)

     for i in range(n_ref_samples):
         f_ref = i // hop                     # 该采样点落在哪个参考帧
         f_ref = min(f_ref, len(warp_path) - 1)   # 末尾夹紧
         f_prac = warp_path[f_ref, col]       # col = practice_frame 列号
         j = f_prac * hop                     # 帧号 → 该帧起点的采样点
         j = clip(j, 0, n_prac_samples - 1)
         out[i] = practice[j]                 # 最近邻，不插值

     结果长度 == n_ref_samples（与参考**采样点**等长）
     ```

     - **最近邻**，**不插值**：插值会引入本文件不该有的数值算法；
       且 `warp_path` 本身已是整数帧号（`element_type == "int32"`）。
     - `col` **必须**用 `FIELD_LAYOUTS["warp_path"].index("practice_frame")` 查，
       **不得**硬编码 `1`。
     - `hop` **必须**取 `profile.ALIGN.hop_length`，**不得**写死 `2048`，
       **不得**用 `PORT_INDEX["warp_path"].hop_length`（那是 **0**）。
     - 结果 dtype 必须 `float32`（与 `profile` 一致），且**必须 Seal**。

     ★ **诚实记录（本版自查发现，两名审查者尚未报告）**：本段第一次写的时候，
     我把结果长度写成 `n_ref_frames`（参考**帧数**），**少乘了 `hop`** ——
     产出会比参考短 2048 倍，而 `dimensions == ("sample",)` 要求它按采样点计长。
     这与 P2 审查的 F7（`warp_path` 的 `hop=0` 致换算恒为 0）是**同一族错误**：
     都是把「帧网格」与「采样点网格」混为一谈。
     我在同一处连犯两次，说明这个混淆点必须显式写进规格。

     **失败语义**：`warp_path` 为空（0 行）而 `pcm.warped.practice` 非空
     ⇒ `CoreBuildError(CORE_BUILD_FAILED)`，`detail` 说明长度无法确定。
     **不得**用空数组冒充（静默降级，违反 §5.6）。

     ★ **诚实记录（沿革）**：上一版我把这三行标成「★ 未决」，
     并在实现指引里写「留空并抛 `CoreBuildError`」。**那个指引是错的** ——
     `generate_all_ports` 是**一次性穷举全部端口**的，
     任何一个端口抛异常都会让**整个数据面构建失败**，
     于是 `pitch` / `dynamics` 也一起跑不起来。
     我当时把「一个端口没生产者」误当成「一个端口失败」，
     实际是「全部端口失败」。现按负责人裁定改为真实生产。
     P2 审查（F2）指出「按规格数据面永远构建不成功」，**它是对的**。     ★ **依赖顺序（冻结）**：`PORTS` 元组的声明顺序**必须**保证
     `pitch.*` / `rms.*` 出现在 `notes.*` **之前**，否则 `notes.*` 取不到中间量。
     若 `PORTS` 的实际顺序不满足，实现**必须**先做一次拓扑排序
     （依赖：`notes.<side>` ← `pitch.<side>`, `rms.<side>`；
     `pcm.*` ← `warp_path`），**不得**靠重排 `PORTS` 来"修好"它
     （`PORTS` 是冻结配置，重排是接口变更 → 见 §10）。

  5. 返回数组必须满足 `profile.PORT_INDEX[port_id].element_type`
     （字符串比较，例 `"float32"`）；不符 → 抛
     `CoreBuildError(CORE_BUILD_FAILED)`（见 §5）。
  6. 返回值放入 `out[port_id]`。**同一个 port_id 不得被写两次**；
     若两个 port_id 由**同一次调用**产出（本版派发表中不存在这种情况），
     允许复用同一 ndarray 对象 —— 后者在 `build_surface` 中会被统一 Seal。
  7. 收尾做基数比对：`set(out.keys()) == expected`，不符抛
     `CoreBuildError(CORE_BUILD_FAILED)`，`detail` 写明
     `missing=` 与 `extra=` 的排序后列表。
- **边界**（逐条给返回值）：
  - `profile.PORTS` 为空 → 返回 `{}`（**不抛错**；由
    `build_surface` 在预算校验后继续，最终 `manifest().ports` 为空映射）。
  - `warp_path` 为形状 `(0, 2)` 的空数组 → **不抛错**，由
    `produced_by` 指名的生成者决定行为；本函数不做 `N >= 2` 的检查
    （那属于对齐阶段的前置条件，见 §7）。
  - `reference` 或 `practice` 为空数组 → **不抛错**，同上，
    由生成者决定；本函数不检查长度。
  - `reference` 或 `practice` 含 `NaN` → **不抛错**，原样透传给生成者。
  - `sample_rate <= 0` → **不抛错**，原样透传。
- **不变量**：
  - 返回值是 `dict`，且 `len(返回值) == len(profile.PORTS)`。
  - 返回值的每个 value 都是 `numpy.ndarray`（不是 list、不是标量）。
  - 本函数**不修改** `reference` / `practice` / `warp_path` 的任何元素，
    也不改变它们的 `writeable` 标志。
  - 调用两次（同一组输入）返回的两个 `dict` 的键顺序相同
    （因为按 `PORTS` 声明顺序遍历）。

---

### 4.5 `assert_budget(ports: Mapping[str, npt.NDArray]) -> int`

- **输入**：`ports: Mapping[str, npt.NDArray]`。取值域：键为端口 ID，
  值为已生成但**尚未 Seal** 的 ndarray（本函数不要求也不改变 Seal 状态）。
- **输出**：`int` —— 总字节数。精确口径（唯一）：
  ```python
  total = 0
  for arr in ports.values():
      total += int(arr.nbytes)
  ```
  `nbytes` 是 numpy 属性 = `prod(shape) * itemsize`，**含** strides 为 0 的广播
  视图的**逻辑**大小（不是实际占用内存）。**不得**改用
  `arr.size * arr.itemsize` 之外的其他公式，**不得**改用 `sys.getsizeof`，
  **不得**只算连续数组。
- **阈值**：硬编码上限取自 `profile.BUDGET.max_surface_bytes`。
  本原型轮次的值为 **536870912 字节（512 MiB）**。
  判定为**严格大于**：`total > profile.BUDGET.max_surface_bytes` 即失败。
  `total == 536870912` **通过**。
- **边界**：
  - `ports` 为空映射 → 返回 `0`，**不抛错**。
  - 单个端口为 0 元素数组 → 其 `nbytes == 0`，计入总和。
  - 数组中含 `NaN` → 与字节数无关，正常返回。
  - `ports` 的值不是 ndarray（如 list）→ 属性访问抛 `AttributeError`，
    **不捕获**（那是程序缺陷）。
  - `total` 恰好等于 `536870912` → 返回 `536870912`，**不抛错**。
  - `total` 等于 `536870913` → 抛 `CoreBuildError`（见 §5）。
- **不变量**：
  - 返回值 `>= 0`。
  - 返回值等于各 value 的 `nbytes` 之和（可独立重算比对）。
  - 本函数**不修改** `ports` 及其任何 value。

---

### 4.6 `class Surface(AlgorithmDataContract)`

构造约定（本文件内部使用，**不**是公开 API）：实现以
`Surface(manifest_obj, data_map)` 形式构造，其中 `manifest_obj: SurfaceManifest`、
`data_map: Mapping[str, npt.NDArray]`。两个属性在构造后**不得**再赋值
（用 `__slots__`、`frozen` dataclass 或属性只读均可，但必须满足：
`surface.manifest` 与 `surface._data` 的重新赋值抛 `AttributeError`）。

---

#### 4.6.1 `Surface.manifest(self) -> SurfaceManifest`

- **输入**：`self`。
- **输出**：`contract.SurfaceManifest`（frozen dataclass），字段逐项：

  | 字段 | 取值（唯一口径） |
  | --- | --- |
  | `profile_version` | `profile.PROFILE_VERSION` |
  | `audio_format` | `contract.AudioFormat(sample_rate=sample_rate, channels=1, dtype="float32")`。`channels` 与 `dtype` 是**契约冻结字面量**（`AudioFormat.__post_init__` 会拒绝其他值）。 |
  | `reference_duration_sec` | `round(len(reference) / sample_rate, 6)`，单位秒。保留 6 位小数（例：120.0 s 输入 → `120.0`）。 |
  | `practice_duration_sec` | `round(len(practice) / sample_rate, 6)`，单位秒。 |
  | `ports` | `Mapping[str, PortDescriptor]`，键集合与 `profile.PORT_INDEX` 完全一致；value 由 §4.2 的 `build_descriptor` 产出。实现**必须**返回 `types.MappingProxyType` 包裹的只读映射（调用方写入抛 `TypeError`）。 |
  | `sealed` | 数据面 Seal 完成则为 `True`；任何端口未 Seal（`any(arr.flags.writeable for arr in data_map.values())` 为真）则为 `False`。**不得**硬编码 `True`。 |

- **算法口径**：**无计算**。本方法返回构造时已装配好的对象或其只读投影。
  在调用 `manifest()` 时**不得**访问 `data_map` 的任何元素内容
  （读 `flags.writeable` 与 `shape` 除外，它们不触发计算）。
- **边界**：
  - 数据面为空端口集 → 返回 `ports = {}` 的清单，`sealed = True`。
  - 数组含 `NaN` → 不影响。
  - 本方法**永不抛错**（构造成功之后）。
- **不变量**：
  - 连续两次调用返回的对象**相等**（`dataclass.__eq__` 逐字段比较为 `True`）。
  - `manifest().ports` 的键集合 == `set(profile.PORT_INDEX.keys())`。
  - `manifest().ports` 不可写入（`mp["x"] = ...` 抛 `TypeError`）。
  - 本方法是**纯查表**：不修改 `self`、不产生新数组、不调用任何生成者。

---

#### 4.6.2 `Surface.read(self, port_id, time_range=None) -> BufferView`

- **输入**：
  - `port_id: str` —— 必须是 `self` 的端口键之一。
  - `time_range: tuple[float, float] | None` —— 单位**秒**，左闭右开 `[t0, t1)`。
    取值域：`t0 < t1`，`t0 >= 0.0`，`t1 <= 该端口的时长上界`（见下换算表）。
    允许 `t0 == 0.0`。允许浮点 `NaN` / `Inf`（判定见 §5）。
- **输出**：`contract.BufferView`（frozen dataclass），字段：
  - `data: npt.NDArray` —— **借用视图**（`data.base is self._data[port_id]`），
    `data.flags.writeable is False`。
  - `element_count: int` —— `int(np.prod(data.shape))`；`data.shape == ()` 时
    为 `1`（`np.prod(()) == 1.0` → `1`）。
  - `element_type: str` —— `str(data.dtype)`。

- **★ 秒 → 索引换算（全部端口统一，唯一口径）**

  设 `sr = self._manifest.audio_format.sample_rate`，
  `d = self._manifest.ports[port_id]`，`hop = d.hop_length`，
  `n = d.shape[0]`（第 0 维长度；标量端口 `n = 1`），
  `f = port_prefix(port_id)`。

  | 条件（按序判定，命中即停） | 起始索引 | 结束索引（开） | 端口时长上界（秒） |
  | --- | --- | --- | --- |
  | `f == "notes"` | 见下方「notes 行筛选」 | 同左 | **该端口所属音频的时长**（见下方「notes 的上界」） |
  | `f == "warp_path"` | 见下方「warp_path 点筛选」 | 同左 | `max(0.0, (n - 1) * profile.ALIGN.hop_length / sr)` |
  | `"amplitude" in d.units` | `floor(t0 * sr)` | `floor(t1 * sr)` | `n / sr` |
  | `"frame" in d.dimensions` | `floor(t0 * sr / hop)` | `floor(t1 * sr / hop)` | `n * hop / sr` |
  | 以上都不命中 | 抛 `ContractViolation(CORE_BUILD_FAILED)` | 同左 | —— |

  **notes 行筛选（`f == "notes"`）**：`time_range` 按
  `FIELD_LAYOUTS["notes"]` 中 `onset_sec` 的列号（**第 0 列**）筛选**行**：
  返回 `onset_sec ∈ [t0, t1)` 的所有行，保持原行序，作为切片
  `data[onset_sec >= t0 & onset_sec < t1]`。
  先算掩码再取行，**不得**用 `searchsorted` 的索引差（那不会排除 `NaN`）。
  ★★ **notes 的上界（本版更正，第三轮盲审 B 的 BLOCK-12）** ★★

  上界取**该端口所属音频的时长**，按侧别从 manifest 取 ——
  `manifest.reference_duration_sec`（reference 侧）或
  `manifest.practice_duration_sec`（practice 侧）。

  **原写 `notes_max_onset_sec + 1.0`，与音频真实时长脱钩，是错的。** 实测：

  | 输入 | 音频时长 | `max(onset)` | 原公式上界 | 可读窗覆盖 |
  | --- | --- | --- | --- | --- |
  | 50 s 连续正弦（只切出 1 个音） | 50.0 s | 0.046 | 1.046 s | **2.1%** |
  | 72.8 s 真实口琴（34 个音） | 72.8 s | 69.474 | 70.474 s | 96.8% |
  | 120 s（2 个音，尾音很长） | 120.0 s | 3.000 | 4.000 s | **3.3%** |

  第二行看着"差不多对"，那是因为**音多、铺得满**；一旦音少或尾部留白，
  可读窗就塌缩到音频开头的一小块。**长音、单音、慢曲都会被误拒** ——
  而 `notes` 恰恰是三条算法（pitch/timing/dynamics）共同的必需端口，
  它的窗口塌缩会向上传染成"算法读不到数据"。

  下面这条定义仍然需要（它用于**行筛选**，即"哪些行落进 [t0,t1)"），
  但它**不再充当上界**：`notes_max_onset_sec = float(np.nanmax(col0))`，
  `col0` 是该端口第 0 列；若该端口 0 行，取值 `0.0`。
  **0 行时上界仍取音频时长**（不是 `1.0`）—— 空端口配满窗，
  让"这个端口确实没有音符"成为一个可被读到的**事实**，
  而不是伪装成"时间窗非法"。
  分段筛选后必须**拷贝**成新数组（`np.ascontiguousarray`）后 Seal 再返回，
  因为行筛选无法用切片表达。

  **warp_path 点筛选（`f == "warp_path"`）**：用**第 0 列**
  （`FIELD_LAYOUTS["warp_path"][0] == "reference_frame"`）换算成秒。

  ★★ **第七版更正（P2 管线审查 F7）：上一版这里用 `hop`，而 `warp_path`
  的 `hop_length` 是 `0` —— 那条换算恒等于 0，使任何时间窗读取都失败。** ★★

  实测：`profile.PORT_INDEX["warp_path"].hop_length == 0`
  （`PortSpec.hop_length=0` 表示"不按帧移索引"）。上一版写
  `t_i = col0[i] * hop / sr` → `t_i ≡ 0.0`；再判 `t_i ∈ [t0, t1)`，
  对任何 `t1 > 0` 的窗口都为空 → 抛 `ContractViolation`。
  **等于 `warp_path` 的 `read` 永远不可用**（而它是 pitch 配对的依据）。

  **本版冻结的正确换算**：`warp_path` 的第 0 列 `reference_frame` 是
  **帧号**，其帧移由 **`profile.ALIGN.hop_length`（本 profile = 2048）** 给出 ——
  它是 warp 路径赖以计算的 DTW 网格步长，**不是** `PortSpec.hop_length`。
  故：

  ```
  t_i = col0[i] * profile.ALIGN.hop_length / sr
  ```

  **不得**用 `d.hop_length`（那是 0）。**不得**写死 `2048`，
  必须取 `profile.ALIGN.hop_length`（这样改 profile 时行为跟着变）。

  返回满足 `t_i ∈ [t0, t1)` 的所有行，保持原行序。先算掩码再取行；
  结果**必须拷贝**并 Seal。
  `warp_path` 的时长上界 = `max(0.0, (n - 1) * profile.ALIGN.hop_length / sr)`；
  空表（`n = 0`）→ 上界 `0.0`。

  > **为什么这里与 `pcm.*` 不同**：`pcm.*` 走 `"amplitude" in d.units` 分支
  > （按采样点索引，不需要 hop），所以 `hop=0` 无害。
  > `warp_path` 的 units 是 `index`、dimensions 是 `("warp_point","axis")`，
  > **不命中** amplitude 分支，因此必须显式给出帧移 —— 上一版漏了这一点。

  **`floor` 的取整口径**：使用 `math.floor`（向下取整到 −∞ 方向）。
  `t0 = 0.0` → `floor(0.0) = 0`。**不得**用 `int()`（对负数是截断）、
  **不得**用 `round()`、**不得**用 `np.floor` 之外的任何口径。
  由于 §5 已先行拒绝负的 `t0`，`floor` 与 `int` 在合法输入上结果相同；
  仍**必须**写 `math.floor`，以使非法输入的失败路径可预期。

  **`hop` 的取法**：`hop` 只在**帧类与 index 类**端口的换算里出现。
  `pitch.*` 与 `chroma.*` 用 `profile.ALIGN.hop_length`（本 profile 为 **2048**）；
  `rms.*` 用 `profile.MATERIALIZE.rms_hop_length`（本 profile 为 **256**）；
  `pcm.*` 用 `hop_length = 0`（走 amplitude 分支，不需要 hop）。
  hop 一律从 `self._manifest.ports[port_id].hop_length` 取，
  **严禁**在本文件内写死 `2048` / `256`，也**严禁**用
  `profile.ALIGN.hop_length` 顶替 `rms.*` 的帧移（两者相差 **8×**）。
  若某端口走到 `"frame" in d.dimensions` 分支而 `hop <= 0` →
  抛 `ContractViolation(CORE_BUILD_FAILED)`（除零防护）。

  **单位换算常量**：秒 × 采样率 = 采样点；秒 × 采样率 / hop = 帧。
  `sample_rate` 取 `self._manifest.audio_format.sample_rate`，
  **不得**取 `profile.AUDIO.sample_rate` 的字面量。

- **算法口径（完整步骤）**：
  1. 若 `port_id not in self._data` → 抛
     `ContractViolation(code=ErrorCode.CORE_BUILD_FAILED, port_id=port_id,
     detail="port not in surface")`。
  2. 若 `self._manifest.sealed is False` → 抛 `ContractViolation`（Seal 前不得读）。
  3. 取 `d = self._manifest.ports[port_id]`，按上表算 `upper`（时长上界）。
  4. 若 `time_range is None` → 返回整段：`out = self._data[port_id]`
     （**不拷贝**），`element_count = int(np.prod(out.shape))`，`element_type = str(out.dtype)`。
     此时 `out.flags.writeable is False` 由 `build_surface` 的 Seal 保证。
  5. 否则解包 `t0, t1 = time_range`。逐项判定：
     `t0` 或 `t1` 不是 `int` / `float` → 抛 `TypeError`；
     `t0 != t0` 或 `t1 != t1`（`NaN`）→ 抛 `ContractViolation`；
     `t0 >= t1` → 抛 `ContractViolation`；`t0 < 0.0` → 抛 `ContractViolation`；
     `t1 > upper` → 抛 `ContractViolation`。
  6. 按上表算 `i0` / `i1`。
  7. **amplitude 分支**：`out = self._data[port_id][i0:i1]`（**视图，不拷贝**）。
  8. **frame 分支**：`out = self._data[port_id][i0:i1]`（**视图，不拷贝**；
     第二维全部保留，故 `out.shape[1] == d.shape[1]`）。
  9. **notes / warp_path 分支**：先算掩码再 `np.ascontiguousarray` 拷贝，
     再 Seal（`out.setflags(write=False)`）。
  10. 组装 `BufferView(data=out, element_count=int(np.prod(out.shape)),
      element_type=str(out.dtype))` 并返回。
  11. **全程不得**调用任何生成者、不得重算特征、不得读写磁盘、不得修改 `self`。
  12. **允许**返回 0 长度视图：当窗**合法**（`t1 <= upper`）而窗内确实无数据
      （如 `notes.*` 在一段静音里无 onset，或 `t1 - t0` 小于一个 hop）
      → 返回 `element_count = 0` 的合法 `BufferView`。这是真实答案，
      **不是**静默降级。判据一句话：`t1` 在时长内 ⇒ 空是合法结果；
      `t1` 超时长 ⇒ 抛错。
  13. **本方法永不构造新数组**，唯二例外是 notes / warp_path 两个筛选分支
      （行筛选无法用切片表达），且该拷贝在返回前已 Seal。

- **边界**（逐条给返回值 / 异常）：
  - 空端口数据（`d.shape[0] == 0`）+ `time_range = None` → 返回
    `element_count = 0` 的 `BufferView`。
  - 空端口数据 + `time_range = (0.0, 0.0)` → `t0 >= t1`，抛 `ContractViolation`。
  - 单元素端口（`shape == (1,)`）+ `time_range = (0.0, 1.0 / sr)` →
    返回 `element_count = 1`。
  - 数组含 `NaN` → **不检查、不抛错**；`NaN` 原样出现在返回的视图里。
  - `time_range = (0.0, t1)` 且 `t1 == upper` → **合法**（右开区间端点，
    取到最后一个索引为 `n - 1`）。`t1` 只超出 `upper` 一个浮点 ULP
    也抛 `ContractViolation`（**不做**容差放宽）。
  - `time_range` 是长度为 2 的 `list`（不是 `tuple`）→ **合法**，按位置解包。
  - `time_range` 长度不为 2 → `ValueError`（由解包直接抛出，不捕获）。
  - `port_id` 为 `""` → 不在 `self._data` 中，抛 `ContractViolation`。
  - 返回的 `data` 即使来自拷贝分支，`writeable` 也**必须**为 `False`。
- **不变量**：
  - `read(p, None).element_count == int(np.prod(manifest().ports[p].shape))`。
  - `read(p, (0.0, upper)).element_count` 等于 `read(p, None).element_count`
    （amplitude / frame 分支；notes 与 warp_path 分支因右开区间可能少最后一行，
    此时以实际筛选结果为准，**不**要求相等）。
  - `read(p, tr).data.ndim == len(manifest().ports[p].dimensions)`。
  - `read(p, tr).element_type == manifest().ports[p].element_type`。
  - 返回对象的 `data.flags.writeable is False`。
  - 同一 `(port_id, time_range)` 两次调用返回的 `data` **逐元素相等**
    （`np.array_equal` 为 `True`），且两次调用后 `self` 的内部状态不变。
  - 多维端口第二维的顺序与 `manifest().ports[p].field_names` 一致
    （由 §4.2 从 `FIELD_LAYOUTS` 取字段名保证）。

---

### 4.7 `build_surface(reference, practice, sample_rate, warp_path) -> Surface`

- **输入**：同 §4.4 的四个参数，语义与取值域逐条相同。
- **输出**：`Surface`，满足 `output.manifest().sealed is True`。
- **算法口径**（按序，任一步失败即整体失败）：
  1. 校验 `sample_rate`：若不是 `int`，或 `<= 0`，或
     `!= profile.AUDIO.sample_rate` → 抛
     `CoreBuildError(CORE_BUILD_FAILED)`。本 profile 的值为 **44100**。
  2. 校验 `reference.ndim == 1` 且 `practice.ndim == 1` → 否则抛
     `CoreBuildError(CORE_BUILD_FAILED)`（多声道必须在 ingest 阶段下混完成）。
  3. 校验 `reference.dtype == np.float32` 且 `practice.dtype == np.float32`
     → 否则抛 `CoreBuildError(CORE_BUILD_FAILED)`。
  4. 校验 `warp_path.dtype == np.int32`、`warp_path.ndim == 2`、
     `warp_path.shape[1] == 2` → 否则抛 `CoreBuildError(CORE_BUILD_FAILED)`。
  5. `ports = generate_all_ports(reference, practice, sample_rate, warp_path)`。
  6. `assert_budget(ports)` —— 失败语义见 §5。
  7. 对 `ports.values()` 中**每个** ndarray 调用 `seal(...)`。
     顺序为 `PORTS` 的声明顺序。
  8. 计算 `reference_duration_sec = round(len(reference) / sample_rate, 6)`，
     `practice_duration_sec = round(len(practice) / sample_rate, 6)`。
  9. 对每个 `port_id` 调 `build_descriptor(port_id, ports[port_id], sample_rate)`
     构造描述符；描述符映射用 `types.MappingProxyType` 包裹。
  10. 构造 `SurfaceManifest(profile_version=profile.PROFILE_VERSION,
      audio_format=AudioFormat(sample_rate, 1, "float32"),
      reference_duration_sec=..., practice_duration_sec=...,
      ports=只读映射, sealed=True)`。
  11. 返回 `Surface(manifest_obj, ports)`。
  12. **导入时机**：`types.MappingProxyType` 需要
      `import types`；它**已在 §3 的标准库清单里**（见该清单的 `types` 条目），
      实现**必须**在模块顶部写 `import types`（不得在函数体内做局部 import）。

      ★ **更正（FINDING-9）**：上一版此处写「这是标准库，属于 §3 允许清单的补充」——
      那句话与 §3「本清单必须穷举」互斥，已删除。`types` 现在是清单内的正式条目。
- **失败语义补充**：第 1–4 步的失败**必须发生在**第 5 步之前，
  因为「不得部分发布」要求：任何情况下都**不得**有半个数据面被构造出来。
  第 5 步之后的失败（预算超限、描述符构造失败）同样抛
  `CoreBuildError`，且**不**返回任何对象。
- **边界**：
  - `reference` 与 `practice` 都为空数组（长度 0）→ 第 2–4 步检查通过
    （`ndim == 1`、`dtype == float32`），进入生成流程；本函数**不**检查
    最小长度（`INPUT_TOO_SHORT` 由 ingest 阶段判定，见 §7）。
  - `warp_path` 为 `(0, 2)` → 形状检查通过，进入生成流程。
  - `reference` 含 `NaN` → **不检查、不抛错**，进入生成流程。
  - `sample_rate` 为 `numpy.int64(44100)` → **合法**（`np.int64` 是 `int`
    的子类）；`sample_rate` 为 `44100.0`（float）→ 抛 `CoreBuildError`。
- **不变量**：
  - 成功返回时 `output.manifest().sealed is True`。
  - 成功返回时所有端口数组的 `flags.writeable is False`。
  - 成功返回时 `set(output.manifest().ports.keys()) == set(profile.PORT_INDEX.keys())`。
  - 失败时**不返回任何对象**（必抛异常），且**不**对外暴露半成品
    （已分配的 numpy 数组由调用方 `api.py` 负责释放，本文件不做显式释放，
    见「不得部分发布」的原文归属）。
  - 同一组四个输入两次调用，两次 `manifest().ports[p].content_hash` 逐字符相同。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| `build_surface`：`sample_rate` 不是 `int`（如 `44100.0` / `"44100"` / `None`） | **显式失败**，整体构建中止，无对象返回 | `CoreBuildError(code=ErrorCode.CORE_BUILD_FAILED, detail="sample_rate type/range")` |
| `build_surface`：`sample_rate <= 0` | **显式失败** | `CoreBuildError(CORE_BUILD_FAILED)` |
| `build_surface`：`sample_rate != profile.AUDIO.sample_rate`（≠ 44100） | **显式失败**。禁止重采样「修正」，禁止静默接受 | `CoreBuildError(CORE_BUILD_FAILED)` |
| `build_surface`：`reference.ndim != 1` 或 `practice.ndim != 1` | **显式失败**。禁止 `mean(axis=1)` 之类的自作主张下混 | `CoreBuildError(CORE_BUILD_FAILED)` |
| `build_surface`：`reference.dtype != float32` 或 `practice.dtype != float32` | **显式失败**。禁止隐式 `astype` 转换 | `CoreBuildError(CORE_BUILD_FAILED)` |
| `build_surface`：`warp_path.dtype != int32` | **显式失败** | `CoreBuildError(CORE_BUILD_FAILED)` |
| `build_surface`：`warp_path.ndim != 2` 或 `warp_path.shape[1] != 2` | **显式失败** | `CoreBuildError(CORE_BUILD_FAILED)` |
| `generate_all_ports`：返回值键集合 ≠ `profile.PORT_INDEX` 键集合 | **显式失败**。禁止「补一个空端口凑数」，禁止忽略多出的键 | `CoreBuildError(CORE_BUILD_FAILED)`，`detail` 含 `missing=[...] extra=[...]`（各自 `sorted()` 后 `repr`） |
| `generate_all_ports`：某端口生成结果的 `str(dtype) != PortSpec.element_type` | **显式失败**。禁止隐式 `astype` 修正 | `CoreBuildError(CORE_BUILD_FAILED)`，`detail` 含 `port_id` 与实际 dtype |
| `generate_all_ports`：某端口生成者返回非 `ndarray`（如 `list` / `None`） | **显式失败**。禁止 `np.asarray` 兜底 | `CoreBuildError(CORE_BUILD_FAILED)` |
| `generate_all_ports`：`profile.PORTS` 为空 | **降级但合法**：返回 `{}`，这是「端口清单为空」的真实答案，非静默降级 | 返回 `{}` |
| `generate_all_ports`：端口生成者自身抛异常 | **显式失败**，不吞、不包装成别的错误码，原异常向上传播（`api.py` 归一化为 `CORE_BUILD_FAILED`） | 原异常原样抛出（`__cause__` / 栈帧不被破坏） |
| `assert_budget`：`total > profile.BUDGET.max_surface_bytes`（> 536870912） | **显式失败**。禁止截断、禁止只 Seal 一部分、禁止丢弃端口 | `CoreBuildError(CORE_BUILD_FAILED)`，`detail` 含实际总字节与上限值 |
| `assert_budget`：`total == 536870912`（恰好等于上限） | **通过** | 返回 `536870912` |
| `assert_budget`：`ports` 为空映射 | **通过** | 返回 `0` |
| `build_descriptor`：`port_id` 不在 `profile.PORT_INDEX` | **显式失败**。禁止返回默认描述符 | `KeyError(port_id)`（由查表直接抛出） |
| `build_descriptor`：多维端口的前缀不在 `contract.FIELD_LAYOUTS` | **显式失败**。禁止回退到「按列号命名」或空元组 | `ContractViolation(code=ErrorCode.CORE_BUILD_FAILED, port_id=port_id)` |
| `build_descriptor`：`data` 含 `NaN` / `Inf` | **降级但合法**：正常构造描述符，不检查数值 | 返回 `PortDescriptor` |
| `build_descriptor`：`data` 为 0 元素或单元素数组 | **降级但合法** | 返回 `PortDescriptor` |
| `seal`：`data` 已是只读 | **幂等**，不抛错 | 返回同一对象 |
| `seal` 之后：调用方尝试写入返回的数组 | **显式失败**（numpy 行为），不吞 | `ValueError`，消息含 `"read-only"` |
| `Surface.read`：`port_id` 不在数据面（含空字符串） | **显式失败**。★ 禁止返回空数组冒充成功（宪章 §5.6） | `ContractViolation(code=ErrorCode.CORE_BUILD_FAILED, port_id=port_id)` |
| `Surface.read`：数据面尚未 Seal（`manifest().sealed is False`） | **显式失败**。Seal 前不得读取 | `ContractViolation(CORE_BUILD_FAILED)` |
| `Surface.read`：`t0 >= t1`（含 `t0 == t1`） | **显式失败**。零宽窗不是「空结果」，是非法参数 | `ContractViolation(CORE_BUILD_FAILED, port_id=port_id)` |
| `Surface.read`：`t0 < 0.0` | **显式失败** | `ContractViolation(CORE_BUILD_FAILED, port_id=port_id)` |
| `Surface.read`：`t1 > upper`（超出该端口时长，含一个 ULP） | **显式失败**。★ 判据：`t1` 超时长 ⇒ 抛错；`t1` 在时长内 ⇒ 空视图合法 | `ContractViolation(CORE_BUILD_FAILED, port_id=port_id)` |
| `Surface.read`：`t0` 或 `t1` 为 `NaN` | **显式失败**。禁止把 `NaN` 当 0 处理 | `ContractViolation(CORE_BUILD_FAILED, port_id=port_id)` |
| `Surface.read`：`t0` 或 `t1` 为 `+Inf` / `-Inf` | **显式失败**（`+Inf > upper` 或 `-Inf < 0.0` 命中上方规则） | `ContractViolation(CORE_BUILD_FAILED, port_id=port_id)` |
| `Surface.read`：`t0` 或 `t1` 不是 `int` / `float`（如 `str` / `None`） | **显式失败**，类型错误 | `TypeError` |
| `Surface.read`：`time_range` 元素个数不为 2 | **显式失败** | `ValueError`（解包） |
| `Surface.read`：窗**合法**但窗内无数据（静音段 `notes.*`，或窗宽小于一个 hop） | **降级但合法**：返回 `element_count == 0` 的 `BufferView`。这是真实答案，不是静默降级 | 返回 `BufferView(data=len-0 数组, element_count=0, element_type=...)` |
| `Surface.read`：端口的 `hop_length <= 0` 却走到 frame 换算分支 | **显式失败**（除零防护）。禁止用 `profile.ALIGN.hop_length` 顶替 | `ContractViolation(CORE_BUILD_FAILED, port_id=port_id)` |
| `Surface.read`：端口的 `units` 与 `dimensions` 都不命中换算表 | **显式失败**。禁止回退到「当整段返回」 | `ContractViolation(CORE_BUILD_FAILED, port_id=port_id)` |
| `Surface.read`：读到的数组含 `NaN` | **降级但合法**：原样返回 | 返回 `BufferView` |
| `Surface.read`：`time_range=None` | **通过**（整段） | 返回 `BufferView` |
| `Surface.manifest`：构造成功后任何调用 | **永不失败** | 返回 `SurfaceManifest` |
| `Surface` 构造后：调用方尝试给 `manifest` / `_data` 重新赋值 | **显式失败** | `AttributeError` |
| `Surface.manifest().ports`：调用方尝试写入 | **显式失败** | `TypeError`（`MappingProxyType` 行为） |
| 端口不存在但调用方声明了它（算法侧 `required_ports`） | **不由本文件处理**：数据面仍有效，判定归 C1 | C1 记 `ErrorCode.PLUGIN_INCOMPATIBLE`（本文件不抛） |
| 输入整段静音 / 过短 / 过长 / 不可读 | **不由本文件处理**：发生在本文件之前（ingest 阶段） | ingest 抛 `INPUT_SILENT` / `INPUT_TOO_SHORT` / `INPUT_TOO_LONG` / `INPUT_UNREADABLE`（本文件不产生这四个码） |
| 用户取消构建（`CANCEL` 在 `BUILDING`） | **不是失败**：`build_surface` 是同步阻塞调用，`CANCEL` 不打断构建；构建完成后按 `CANCEL` 的目标转移生效 | 本文件**不产生** `ErrorCode`；不提供取消标志的设置或观察通道，不设检查点 |

★ 宪章 §5.6：禁止静默降级。上表每一行的「降级但合法」都有明确判据，不是模糊退让；
其余每一行都是显式失败，**禁止**用返回值掩盖。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-104-1 | **MUST：由 `profile.PORTS` 驱动生成（穷举），不得硬编码端口名。** 数据面的键集合恒等于 `set(profile.PORT_INDEX.keys())` | `assert set(build_surface(ref, pra, 44100, wp).manifest().ports.keys()) == set(profile.PORT_INDEX.keys())`；并在 `surface.py` 源码中按 **§8 的 `BANNED` 正则**检索**完整端口 ID 与二级端口名**（含侧别），命中数必须为 **0**。★ **更正（BLOCK-14）**：原写「检索 `"pcm.mapped"` / `"pitch."` / `"chroma."` / `"rms."` / `"notes."` 五个字面量」—— 与 §8 的七字面量清单**不一致**，且**裸前缀名 `"pitch"`/`"notes"` 是 §4.4 派发所必需**，禁掉就写不出来。已统一为 §8 的 `BANNED` 口径 |
| INV-104-2 | **MUST：Seal —— 所有数组 `setflags(write=False)`，Seal 后不可变** | `s = build_surface(...)`；`assert all(not v.flags.writeable for v in s._data.values())`；对任一端口 `v = s._data["pcm.mapped.reference"]`，`try: v[0] = 0.0; assert False except ValueError: pass` |
| INV-104-3 | **MUST：为每个端口计算 `content_hash`（供同 build 回归断言）** | 两次独立 `build_surface` 同一组输入，逐端口 `assert s1.manifest().ports[p].content_hash == s2.manifest().ports[p].content_hash`；且 `assert all(len(d.content_hash) == 64 for d in s.manifest().ports.values())`；且 `content_hash` 非空字符串 |
| INV-104-4 | **MUST：`read()` 是纯查表 —— 无副作用、不失败于「算不出来」** | 连续两次 `read("rms.practice", (1.0, 2.0))` 返回的 `np.array_equal(bv1.data, bv2.data)` 为 `True`；且调用 `read` 前后 `manifest()` 逐字段相等；且对一个端口做 100 次不同窗口的 `read` 后，进程内不存在任何新生成的端口数组（`id()` 集合不变） |
| INV-104-5 | **MUST：时长/尺寸校验 —— 总字节超过 `profile.BUDGET.max_surface_bytes` → 构建失败** | `assert profile.BUDGET.max_surface_bytes == 536870912`；构造 `ports = {"x": np.zeros(134217729, dtype="float32")}`（= 536870916 字节 > 512 MiB），`assert_budget(ports)` 抛 `CoreBuildError`；再构造 `{"x": np.zeros(134217728, dtype="float32")}`（= 536870912 字节，恰好等于），`assert assert_budget(ports) == 536870912` |
| INV-104-6 | **MUST NOT：暴露可写视图** | `assert s.read("pcm.mapped.practice", (0.0, 1.0)).data.flags.writeable is False`；对 `read` 的每个返回逐个端口、逐个窗口断言同一式；且 `assert s.read("pcm.mapped.practice", None).data.flags.writeable is False` |
| INV-104-7 | **MUST NOT：在 `read()` 里触发任何计算** | 源码级：`Surface.read` 函数体内检索 `produced_by` / `generate_all_ports` / `assert_budget` 三个标识符，命中数必须为 **0**；运行期：`read` 的耗时与 `time_range` 宽度无关（同一端口读 0.01 s 与读整段的 wall time 差 < 10 ms，仅作辅助证据） |
| INV-104-8 | **MUST NOT：端口不存在时返回空数组（必须抛 `ContractViolation`）** | `try: s.read("no.such.port", None); assert False except ContractViolation: pass`；`try: s.read("", None); assert False except ContractViolation: pass`；且断言抛出的对象 `isinstance(e, ContractViolation)` 且 `e.port_id == "no.such.port"` |
| INV-104-9 | **MUST NOT：允许 Seal 后追加端口** | `try: s.manifest().ports["injected"] = None; assert False except TypeError: pass`；且 `try: s._data["injected"] = np.zeros(1, dtype="float32"); assert False except TypeError: pass`；且 `assert len(s.manifest().ports) == len(profile.PORTS)` |
| INV-104-10 | 端口键集合封闭：多一个或少一个都是缺陷 | `assert_budget` / `generate_all_ports` 的基数比对：monkeypatch 端口生成者使其返回多一个键，`assert` 触发 `CoreBuildError`；再使其少一个键，`assert` 触发 `CoreBuildError` |
| INV-104-11 | 多维端口的 `field_names` 必须逐字等于 `contract.FIELD_LAYOUTS[前缀]` | `for p, d in s.manifest().ports.items(): if len(d.dimensions) > 1: assert tuple(d.field_names) == tuple(FIELD_LAYOUTS[p.split(".", 1)[0]])` |
| INV-104-12 | 每个端口的 `hop_length` 取自 `profile.PORT_INDEX[p].hop_length`；`sample_rate` 按 §4.0 的 `_SAMPLE_RATE_FREE_PREFIXES` **分支**取值：无关端口填 `0`，其余填 `profile.AUDIO.sample_rate` | ★★ **本版更正（第三轮盲审 B 的 BLOCK-11）：原断言对所有端口一律要求 `d.sample_rate == profile.AUDIO.sample_rate`（44100）—— 与 §4.0 的规则和 `contract.py` 的明文语义都冲突，12 个端口里有 5 个必失败。** ★★ 正确断言：`free = port_prefix(p) in _SAMPLE_RATE_FREE_PREFIXES`，然后 `assert d.sample_rate == (0 if free else profile.AUDIO.sample_rate)`。`contract.PortDescriptor.sample_rate` 的 docstring 明写「**0 表示该端口与采样率无关（如 chroma / index 类）**」—— 契约站在 §4.0 这边。**不要把前缀集合在本行重新写一遍**，直接引用 §4.0 那个已被核验的常量，让规则只有一处定义。★ **更正（P1 审查 F5）**：原写 `PORT_INDEX[p].sample_rate` —— `PortSpec` **没有**该字段（实测字段表：`port_id, units, dimensions, element_type, timeline_basis, produced_by, rationale, field_names, hop_length`），按字面执行会 `AttributeError`。`sample_rate` 是 `PortDescriptor` 的字段 |
| INV-104-13 | 每个端口必须声明 `timeline_basis`，且等于 `profile.PORT_INDEX[p].timeline_basis` | `for p, d in s.manifest().ports.items(): assert isinstance(d.timeline_basis, TimelineBasis) and d.timeline_basis is profile.PORT_INDEX[p].timeline_basis` |
| INV-104-14 | `read` 的时间窗语义：秒、左闭右开 `[t0, t1)` | 对 `pcm.mapped.reference`（44100 Hz）读 `(0.0, 0.001)` → `element_count == 44`（`floor(0.001 * 44100) == 44`）；读 `(0.0, 44 / 44100)` → `element_count == 44`；读 `(0.0, upper)` 与 `None` 结果 `element_count` 相等 |
| INV-104-15 | `read` 的越界语义：`t0 >= t1` 或 `t1` 超出该端口时长 → `ContractViolation` | `for tr in [(1.0, 1.0), (2.0, 1.0), (-0.1, 1.0), (0.0, upper + 1e-9), (0.0, float("inf"))]: try: s.read("pcm.mapped.reference", tr); assert False except ContractViolation: pass` |
| INV-104-16 | `read` 返回的 `BufferView` 三个字段彼此自洽 | `bv = s.read("notes.practice")`（time_range 传 None 取全量）；`assert bv.element_count == int(np.prod(bv.data.shape))`；`assert bv.element_type == str(bv.data.dtype)`；`assert bv.data.ndim == len(s.manifest().ports["notes.practice"].dimensions)` |
| INV-104-17 | `build_surface` **不得部分发布**：任何一步失败都不返回对象 | 传入 `dtype="float64"` 的 `reference`，`try: build_surface(...); assert False except CoreBuildError: pass`；传入 `sample_rate=22050`，同上；传入总字节超预算的输入，同上。三种情况下均无 `Surface` 对象可被取得 |
| INV-104-18 | 时长口径固定为「采样点数 / 采样率，保留 6 位小数」 | `s = build_surface(np.zeros(44100 * 3, dtype="float32"), np.zeros(44100 * 2, dtype="float32"), 44100, wp)`；`assert s.manifest().reference_duration_sec == 3.0`；`assert s.manifest().practice_duration_sec == 2.0` |
| INV-104-19 | `manifest().sealed is True` 是数据面可交付的充要标志 | `assert build_surface(...).manifest().sealed is True`；且 `Surface.manifest()` 中 `sealed` 由 `all(not a.flags.writeable for a in self._data.values())` 实算，不得硬编码 `True`（源码检索 `sealed=True` 字面量命中数为 0，构造处除外） |
| INV-104-20 | `seal()` 返回同一对象，不拷贝、不改 strides | `a = np.zeros(4, dtype="float32"); b = seal(a)`；`assert b is a`；`assert a.flags.writeable is False`；`assert a.strides == (4,)` |
| INV-104-21 | `content_hash` 的输入字节序列与 `PortDescriptor.content_hash` 的冻结算法逐字节一致 | 手工重算：`h = hashlib.sha256(); h.update(CONTENT_HASH_MAGIC); h.update(port_id.encode()); h.update("float32".encode()); h.update(np.asarray(shape, dtype="<i8").tobytes()); h.update(data.tobytes(order="C"))`，`assert h.hexdigest() == s.manifest().ports[port_id].content_hash` |
| INV-104-22 | `content_hash` 区分 shape 与 dtype（不得只哈希数据字节） | `a = np.zeros((2, 3), dtype="float32"); b = np.zeros((3, 2), dtype="float32")`；两者的 `content_hash` 必须不同；`np.zeros(6, "float32")` 与 `np.zeros(6, "int32")` 的 `content_hash` 必须不同 |
| INV-104-23 | `content_hash` 对非连续视图按 C 序逻辑值计算 | `x = np.arange(12, dtype="float32").reshape(3, 4)`；`assert content_hash_of(x[::2]) == content_hash_of(np.ascontiguousarray(x[::2]))` |
| INV-104-24 | `build_descriptor` 的 `shape` 元素类型是 Python `int` | `assert all(type(v) is int for v in s.manifest().ports["pcm.mapped.reference"].shape)`；`assert all(type(v) is int for v in s.manifest().ports["notes.practice"].shape)` |
| INV-104-25 | `element_count` 与端口的 `shape` 乘积一致 | `for p, d in s.manifest().ports.items(): assert s.read(p, None).element_count == int(np.prod(d.shape))` |
| INV-104-26 | `assert_budget` 的返回值为各端口 `nbytes` 之和 | `t = assert_budget({"a": np.zeros(3, "float32"), "b": np.zeros((2, 5), "float64")})`；`assert t == 3 * 4 + 2 * 5 * 8 == 92` |
| INV-104-27 | 秒→帧换算按端口**自己的** `hop_length`，`rms.*`(256) 与 `chroma.*`(2048) 不得混用 | ★★ **本版重写（第三轮盲审 B 的 BLOCK-13）。原断言有两处错，且是一条假闸门。** ★★ 正确写法按**帧数**（`data.shape[0]`）比，并用**正向**闸门：`rms_frames = s.read("rms.practice", (0.0, 1.0)).data.shape[0]` → 断言 `== 172`；`chroma_frames = s.read("chroma.lowres.reference", (0.0, 1.0)).data.shape[0]` → 断言 `== 21`；再断言 `abs(rms_frames / chroma_frames - 8.0) < 0.2`（256 vs 2048 恰 8×）。<br>**错处一（验错了量）**：原写 `element_count == 21` —— 但 §4.6.2 定义 `element_count = int(np.prod(data.shape))`，而 chroma 形状是 `(21, 12)`，真值 **252**。`21` 是**帧数**不是元素数。<br>**错处二（反向闸门没有判别力）**：原要求比值「落在 `[7.9, 8.1]` **之外**」。实测三种情形 —— 正确实现 `252/172 = 1.465`（放行）、hop 混用 `2064/172 = 12.0`（**也放行**）、`element_count` 误返回 `shape[0]` 时 `21/172 = 0.122`（也放行）。**它要抓的那个缺陷恰好被它放行**，这是一条永远通过、且验错对象的假闸门（方法论 §6.3）。正向闸门才拦得住。 |
| INV-104-28 | `notes.*` 的时间窗按 `onset_sec` 字段筛行，不使用帧移换算 | 构造 `notes.practice` 的 `onset_sec` 列为 `[0.5, 1.5, 2.5]`，`read("notes.practice", (1.0, 2.0))` 的 `element_count == 1 * 3`（一行三字段，`field_names = ("onset_sec","f0_hz","rms")`） |
| INV-104-29 | `Surface` 构造后属性不可重新赋值 | `try: s.manifest = None; assert False except AttributeError: pass`；`try: s._data = {}; assert False except AttributeError: pass` |
| INV-104-30 | `manifest()` 是纯查表，连续两次调用结果相等 | `assert s.manifest() == s.manifest()`（dataclass 逐字段比较）；且两次调用的 `ports` 键顺序相同（`list(a.ports) == list(b.ports)`） |
| INV-104-31 | 空窗合法时返回空视图，不冒充、不抛错（`t1` 在时长内 ⇒ 空是合法结果） | `read("notes.practice", (0.0, upper))` 在 `notes.practice` 为 0 行时返回 `element_count == 0`；此时 `t1 == upper` 未越界，**不得**抛 `ContractViolation` |
| INV-104-32 | 端口不存在时**不得**返回空数组（与 INV-104-31 的区分） | `try: bv = s.read("notes.absent", (0.0, 1.0)); assert False except ContractViolation: pass` —— 即「空是合法结果」只适用于**存在**的端口 |

---

## 7 · 边界（明确不做）

- **不实现音频解码、重采样、下混、时长校验。** 这四件事全部发生在 ingest 阶段，
  失败码是 `INPUT_UNREADABLE` / `INPUT_TOO_SHORT` / `INPUT_TOO_LONG` / `INPUT_SILENT`。
  本文件收到的一定已是 float32 mono 44100 Hz PCM；收到别的形态就抛
  `CoreBuildError(CORE_BUILD_FAILED)`，**不**自行修复。
- **不实现时间对齐、不计算 `warp_path`。** `warp_path` 是入参，
  由对齐阶段产出。本文件不检查其单调性、不检查其端点覆盖全曲、不检查 `N >= 2`。
- **不实现任何特征提取。** f0、onset、RMS、chroma 的计算全部在
  `PortSpec.produced_by` 指名的模块里。本文件只做查表调用与汇总。
- **不做内存优化。** 不压缩、不分块、不惰性生成、不共享 buffer、
  不做 `float32` → `float16` 之类的省内存转换。预算上限 512 MiB 是刻意放宽的
  （见 §4.5），实测 12 个端口在 120 s 音频下约 10–20 MB。
- **不做缓存与持久化。** 不写磁盘、不落 `data/out/`、不 pickle、不存全局单例。
  数据面只活在进程内存里，随会话销毁而释放。
- **不做多会话管理。** `Surface` 不知道 `session_id`，不持有任何会话状态，
  不做引用计数，不做生命周期管理。资源释放归 `api.py`。
- **不做取消检查点。** `build_surface` 是同步阻塞调用，`CANCEL` 在 `BUILDING`
  时不打断构建；契约没有取消标志的设置或观察通道，故不存在可执行的端口级检查要求。
  本文件的 `build_surface` 同步执行，内部不读取消标志。
  **不得**在本文件里 import 任何取消/事件机制，也**不得**注入后台线程、回调或 checkpoint。
- **不做算法兼容性检查。** 「算法声明了数据面没有的端口」由 C1 判定为
  `PLUGIN_INCOMPATIBLE`；本文件不读 `AlgorithmResultEnvelope.required_ports`，
  也不为任何算法补端口。
- **不做进度上报。** 不暴露内部阶段名、不写日志、不产生 `progress` 值。
  `UiView.progress` 的产生机制在 C1，见 `contract.UiView.progress` 的冻结说明。
- **不修改契约。** 不改 `contract.py`、不改 `profile.py`、不新增端口、
  不新增错误码、不新增依赖。
- **不做数值内容的正确性判定。** 不检查 `NaN` / `Inf` / 超范围样本值、
  不检查 f0 是否在合理音域、不检查 RMS 是否为负。数值合法性由各端口的
  生产模块负责；本文件只做 dtype / shape / 键集合 / 字节预算四类结构校验。
- **不做跨实现 hash 的兼容层。** 不提供 `content_hash` 的「容错比较」
  （如忽略 dtype 或只比数据字节）。`content_hash` 是逐字符比较的字符串。
- **不做 `WARPED` 轴的 PCM 重采样。** `pcm.warped.practice` 等端口的生成
  在 `produced_by` 指名的模块里；本文件不实现任何重采样算法。

  ★ **更正（本版）**：上一版这句话与 `produced_by` **自相矛盾** ——
  `profile.py` 把 `pcm.*` 的 `produced_by` 就写成 `core.surface`（即本文件），
  所以「在 `produced_by` 指名的模块里」= 「在本文件里」，
  而同一句话又说「本文件不实现」。**这是一个自我否定的句子。**
  正确状态（已裁定）：`pcm.mapped.*` 是**纯转发**（零计算，不是重采样）；
  `pcm.warped.practice` 是**索引重排**（最近邻取样，也不是重采样 ——
  它不改变采样率、不做插值）。见 §4.4 的裁定段。
  本文件仍然**不**实现任何重采样算法（不改变采样率、不插值）。
- **不处理界面（C4）与宿主编排（C1）的任何需求。** 不暴露额外公开方法，
  不提供 `__len__` / `__iter__` / `__getitem__` / `keys()` / `to_dict()` /
  `snapshot()` / `close()` 等便利接口 —— `Surface` 的公开面**只有**
  `manifest()` 与 `read()` 两个方法。
- **不修改传入的四个输入数组。** 不改 `writeable` 标志、不原地修改元素、
  不做 `sort()` / `resize()` / `setflags()`。

---

## 8 · 怎么验证你写对了

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
# 1 · 静态闸门：模块可导入 + 无语法/依赖越界
python -c "import harmonica_eval.core.surface as m; print(m.__file__)"

# 2 · 无残留壳：不得再有 NotImplementedError / SHELL 标记
python -c "import inspect, harmonica_eval.core.surface as m; s=inspect.getsource(m); assert 'NotImplementedError' not in s, 'SHELL 未注入'; assert 'SHELL' not in s, 'SHELL 标记残留'; print('shell-clean')"

# 3 · 依赖越界扫描：surface.py 不得出现被禁 import
# ★★★ 更正（⑳ 二次执行确认）：原版用**裸子串** `b in s` ★★★
#   它会把【注释与 docstring 里对被禁项的说明】也算成违规：
#   实测 surface.py:157 有一行注释解释「那多出来的帧是 librosa boundary='zeros' 补出来的」
#   → hit = ['librosa'] → 恒红。
#   ★ 判据要测「真的 import 了」，★ 不是「源码里提到过这个词」。
#   改为 AST 口径：★ 只查 Import / ImportFrom 节点，★ 注释与 docstring 一律不查。
#   ★ 它与下方 INV-104-1 同口径（剥掉注释与字符串后再判）。
python -c "
import ast, inspect
import harmonica_eval.core.surface as m
src = inspect.getsource(m)
tree = ast.parse(src)
# 剥掉所有字符串常量与 docstring，避免说明文字被当成依赖
for node in ast.walk(tree):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        node.value = ''
BANNED_MODS = {
    'librosa', 'soundfile', 'scipy', 'os', 'io', 'logging', 'time',
    'json', 'pickle', 'threading', 'pathlib',
    'harmonica_eval.algorithms', 'harmonica_eval.host', 'harmonica_eval.cockpit',
}
BANNED_SUB = {'harmonica_eval.core.api', 'harmonica_eval.core.ingest'}
hit = []
for node in ast.walk(tree):
    names = []
    if isinstance(node, ast.Import):
        names = [a.name for a in node.names]
    elif isinstance(node, ast.ImportFrom) and node.module:
        names = [node.module]
    for n in names:
        if n.split('.')[0] in BANNED_MODS or n in BANNED_SUB:
            hit.append(n)
assert hit == [], hit
print('deps-clean')
"

# 4 · 端口名硬编码扫描：端口 ID 字面量命中数必须为 0
# ★★ 更正（第三轮盲审 B 的 BLOCK-14 + ⑳ 执行确认）：上一版这条命令用
#   **裸前缀子串检索**，`'warp_path.' in s` 会命中**合法代码** `warp_path.dtype`
#   （§4.7 第 4 步明确要求校验 `warp_path.dtype == np.int32`），
#   实测 hit = ['warp_path.'] → 恒假。
#   改为 AST 口径：只禁**完整端口 ID 与副名**，允许裸前缀出现在
#   标识符、docstring 与错误文案里。
python -c "
import ast, inspect, re
import harmonica_eval.core.surface as m
# 与下方 INV-104-1 的 BANNED 正则**同一口径**（完整端口 ID / 二级端口名；
# 裸前缀名与 docstring 不查）。
BANNED = re.compile(
    r'^(?:pcm\.(?:mapped|warped)(?:\.(?:reference|practice))?'
    r'|chroma\.lowres(?:\.(?:reference|practice))?'
    r'|(?:pitch|rms|notes)\.(?:reference|practice))$')
tree = ast.parse(inspect.getsource(m))
# ★ 2026-09-25 修正（判据过宽，★ 非实现缺陷）：
#   本判据原样扫【所有字符串常量】，于是 surface.py 里
#   `ContractViolation(..., port_id=\"pcm.warped.practice\")` 的三处被判成
#   「硬编码端口 ID」（实测 hit 里三条全是它）。
# ★ ★ 但那三处是【错误信封的诊断字段】—— 它说「这次失败属于哪个端口」，
#   不是「数据从哪个端口取」。§4.4 明确要求越界要显式失败并带 port_id，
#   ★ 所以那正是【规格要求写的】，不是「绕过描述符查数据」。
# ★ ★ 判据要守的是「不要硬编码端口 ID 去做【数据来源】判断」，
#   不是「源码里不许出现这个字符串」。
# ★ 修法：只豁免【作为 ContractViolation 的 port_id 关键字实参】的位置；
#   ★ 其它任何地方硬编码完整端口 ID 仍然被抓。
def _is_violation_port_id(node):
    # node 是 ast.keyword(port_id=...)；其父需在 Call 里且 callee 是 ContractViolation
    kw = node
    return getattr(kw, 'arg', None) == 'port_id'

_contract_violation_port_ids = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        fn = node.func
        name = getattr(fn, 'id', None) or getattr(fn, 'attr', None)
        if name == 'ContractViolation':
            for kw in node.keywords:
                if kw.arg == 'port_id' and isinstance(kw.value, ast.Constant):
                    _contract_violation_port_ids.add(id(kw.value))

hits = [n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and BANNED.match(n.value.strip())
        and id(n) not in _contract_violation_port_ids]
assert hits == [], hits
print('no-hardcoded-port-ids')
"

# 5 · 端到端装配 + 全部不变量（把下面 heredoc 存成一次运行即可）
python - <<'PY'
import hashlib
import math
import numpy as np
from harmonica_eval import contract, profile
from harmonica_eval.contract import ContractViolation, CoreBuildError, ErrorCode, FIELD_LAYOUTS, CONTENT_HASH_MAGIC
from harmonica_eval.core.surface import (
    assert_budget, build_descriptor, build_surface, seal,
)

SR = 44100
assert profile.AUDIO.sample_rate == SR, profile.AUDIO.sample_rate
assert profile.BUDGET.max_surface_bytes == 536870912, profile.BUDGET.max_surface_bytes
assert profile.ALIGN.hop_length == 2048, profile.ALIGN.hop_length
assert profile.MATERIALIZE.rms_hop_length == 256, profile.MATERIALIZE.rms_hop_length

ref = np.zeros(SR * 3, dtype="float32")
pra = np.zeros(SR * 2, dtype="float32")
# ★ 原写作 `[[0, 0], [SR - 1, SR * 2 - 1]]` —— 它把**采样点**当成了**帧号**：
#   `warp_path` 的两列都是 DTW **帧网格**上的索引，而
#   `(88200 - 1) // 2048 = 43` 才是练习侧合法帧号上界（帧起点须 < 样本数），
#   `SR * 2 - 1 = 88199` 超出约 88000 帧。
#   ★ 后果：`j = 帧号 * hop = 88199 * 2048` 远远越过练习样本数，
#   ★ 原实现会抛 numpy IndexError —— 那是【未校验越界】的缺陷，不是判据本意。
# ★ 本版改为合法帧号，并另加一条「越界必须显式失败」的断言（见下）。
_legal_max_frame = (len(pra) - 1) // profile.ALIGN.hop_length
# ★★ 2026-09-25 修正（判据自身算术 bug，★ 非实现缺陷）：
#   本行原写作 `wp = np.asarray([[0, 0], [SR - 1, _legal_max_frame]], ...)`。
# ★ ★ 那把【采样点】44100 放进了 warp_path 的第一列。实测：
#     FIELD_LAYOUTS['warp_path'] == ('reference_frame', 'practice_frame')
#     —— ★ 两列都是【帧网格】索引，而合法帧号上界是
#     (len(pra)-1)//2048 = 43，★ 44100 远超它。
# ★ ★ 于是第 28 行那段【故意造越界】的 try 之前，
#   第 34 行的正常路径就已经越界 → 抛 CORE_BUILD_FAILED，
#   整段以 ContractViolation 收场，判据自身失效。
# ★ 修法：两列都用帧号，各按自己那一侧的样本数算合法上界。
#   ★ 越界路径（第 28-32 行）仍只让【练习侧】越界，★ 语义一字未改。
_ref_legal_max = (len(ref) - 1) // profile.ALIGN.hop_length
wp = np.asarray([[0, 0], [_ref_legal_max, _legal_max_frame]], dtype="int32")
# ★ 越界路径：帧号超出合法上界时必须抛 ContractViolation，不得抛 IndexError
try:
    build_surface(ref, pra, SR, np.asarray([[0, 0], [0, _legal_max_frame + 1]], dtype="int32"))
    raise AssertionError("out-of-range practice_frame should fail explicitly")
except ContractViolation as e:
    assert "practice_frame" in str(e) or "exceeds" in str(e), e

s = build_surface(ref, pra, SR, wp)

# INV-104-1 端口穷举
assert set(s.manifest().ports.keys()) == set(profile.PORT_INDEX.keys())
assert len(s.manifest().ports) == len(profile.PORTS)

# INV-104-2 Seal
assert all(not v.flags.writeable for v in s._data.values())
try:
    s._data["pcm.mapped.reference"][0] = 0.0
    raise AssertionError("writable!")
except ValueError:
    pass

# INV-104-3 / 21 / 22 content_hash
s2 = build_surface(ref, pra, SR, wp)
for p, d in s.manifest().ports.items():
    assert d.content_hash and len(d.content_hash) == 64
    assert d.content_hash == s2.manifest().ports[p].content_hash
    arr = s._data[p]
    h = hashlib.sha256()
    h.update(CONTENT_HASH_MAGIC)
    h.update(p.encode("utf-8"))
    h.update(str(arr.dtype).encode("utf-8"))
    h.update(np.asarray(arr.shape, dtype="<i8").tobytes())
    h.update(arr.tobytes(order="C"))
    assert h.hexdigest() == d.content_hash, p

# INV-104-8 端口不存在必须抛 ContractViolation（不得返回空数组）
for bad in ("no.such.port", ""):
    try:
        s.read(bad, None)
        raise AssertionError("empty array masquerading as success")
    except ContractViolation as e:
        assert isinstance(e, ContractViolation)

# INV-104-14 / 15 秒语义与越界
bv = s.read("pcm.mapped.reference", (0.0, 0.001))
assert bv.element_count == 44, bv.element_count
upper = 3.0
assert s.read("pcm.mapped.reference", (0.0, upper)).element_count == s.read("pcm.mapped.reference", None).element_count
for tr in [(1.0, 1.0), (2.0, 1.0), (-0.1, 1.0), (0.0, upper + 1e-9), (0.0, float("inf")), (float("nan"), 1.0)]:
    try:
        s.read("pcm.mapped.reference", tr)
        raise AssertionError(("no raise", tr))
    except ContractViolation:
        pass

# INV-104-16 BufferView 自洽
# ★ 2026-09-25 修正（判据用错坐标语义，不是实现缺陷）：
#   本行原先 s.read("notes.practice", (0.0, 5.0))。
#   ★ notes.* 是 hop=0 的【音符表】，不是帧域序列；read 的 time_range 是
#     【秒】窗口，上界按两侧音频时长取 max（此处练习侧仅 3 秒），
#     所以 5.0 越界 → ContractViolation: t1 5.0 exceeds port upper bound 3.0。
#   ★ 本条要验的是 BufferView 三字段自洽，与窗口无关 —— 传 None 取全量。
#   ★ 判据语义（BufferView 自洽）一字未改。
bv = s.read("notes.practice")
assert bv.element_count == int(np.prod(bv.data.shape))
assert bv.element_type == str(bv.data.dtype)
assert bv.data.ndim == len(s.manifest().ports["notes.practice"].dimensions)

# INV-104-11 / 12 / 13 描述符逐字段
for p, d in s.manifest().ports.items():
    spec = profile.PORT_INDEX[p]
    if len(d.dimensions) > 1:
        assert tuple(d.field_names) == tuple(FIELD_LAYOUTS[p.split(".", 1)[0]]), p
    assert d.hop_length == spec.hop_length, p
    # ★ 原写作 `d.sample_rate == spec.sample_rate` —— 恒假：`PortSpec`
    # ★ 没有 `sample_rate` 字段（实测字段集：port_id / units / dimensions /
    # ★ element_type / timeline_basis / produced_by / rationale /
    # ★ field_names / hop_length）。采样率是**音频格式属性**，唯一权威在
    # ★ `manifest.audio_format.sample_rate`；与采样率无关的端口
    # ★ （chroma / warp_path / notes）填 0，见 §4.2 sample_rate 两条规则。
    # ★ 2026-09-25 修正（判据引用了不存在的私有名）：
    #   本段是独立脚本（check_bi_scripts_exec.py 每段各跑一次），
    #   而 §4.0 里那行 `_SAMPLE_RATE_FREE_PREFIXES = ...` 属于【另一段】代码，
    #   不在本段作用域 → NameError（实测 FILE-104 停在 4/5）。
    #   ★ 修法：引用公开真相源 profile.SAMPLE_RATE_FREE_PREFIXES，
    #   ★ 与 bootstrap / tests 同一份名单（单一真相源），不在判据里重抄一遍。
    if p.split(".", 1)[0] in profile.SAMPLE_RATE_FREE_PREFIXES:
        assert d.sample_rate == 0, p
    else:
        assert d.sample_rate == s.manifest().audio_format.sample_rate, p
    assert d.timeline_basis is spec.timeline_basis, p
    assert all(type(v) is int for v in d.shape), p

# INV-104-18 时长口径
assert s.manifest().reference_duration_sec == 3.0
assert s.manifest().practice_duration_sec == 2.0

# INV-104-19 sealed
assert s.manifest().sealed is True

# INV-104-9 Seal 后不可追加端口
try:
    s.manifest().ports["injected"] = None
    raise AssertionError("ports writable")
except TypeError:
    pass
try:
    s._data["injected"] = np.zeros(1, dtype="float32")
    raise AssertionError("_data writable")
except TypeError:
    pass

# INV-104-20 seal 同一对象
a = np.zeros(4, dtype="float32")
b = seal(a)
assert b is a and a.flags.writeable is False and a.strides == (4,)

# INV-104-26 预算求和
t = assert_budget({"a": np.zeros(3, "float32"), "b": np.zeros((2, 5), "float64")})
assert t == 92, t
# 恰好等于上限通过
assert assert_budget({"x": np.zeros(134217728, dtype="float32")}) == 536870912
# 超一个元素即失败
try:
    assert_budget({"x": np.zeros(134217729, dtype="float32")})
    raise AssertionError("budget not enforced")
except CoreBuildError as e:
    assert e.code is ErrorCode.CORE_BUILD_FAILED

# INV-104-17 不得部分发布
for bad_ref, bad_sr, bad_wp in [
    (ref.astype("float64"), SR, wp),
    (ref, 22050, wp),
    (ref.reshape(-1, 1), SR, wp),
    (ref, SR, wp.astype("int64")),
    (ref, SR, wp[:, :1]),
]:
    try:
        build_surface(bad_ref, pra, bad_sr, bad_wp)
        raise AssertionError("partial publish")
    except CoreBuildError:
        pass

# INV-104-29 属性只读
for attr in ("manifest", "_data"):
    try:
        setattr(s, attr, None)
        raise AssertionError("mutable attr " + attr)
    except AttributeError:
        pass

# INV-104-30 manifest 纯查表
assert s.manifest() == s.manifest()
assert list(s.manifest().ports) == list(s.manifest().ports)

# INV-104-25 element_count
for p, d in s.manifest().ports.items():
    assert s.read(p, None).element_count == int(np.prod(d.shape)), p

# INV-104-27 hop 不混用（rms 256 vs chroma 2048）
rms_n = s.read("rms.practice", (0.0, 1.0)).element_count
chr_n = s.read("chroma.lowres.reference", (0.0, 1.0)).element_count
assert rms_n == 44100 // 256, rms_n
# ★ 原写作 `assert chr_n == 44100 // 2048`（= 21）—— 恒假：
# ★ chroma 的 `dimensions == ("frame", "bin")`，`bin` = 12 个音级，
# ★ `read()` 返回的 `element_count = int(np.prod(shape))`。
# ★ 所以 1 秒窗的正确值是 `帧数 × 12`，不是帧数。
# ★ 实测（78.8 s 全曲，hop=2048）：shape=(1697, 12) → 20364。
assert chr_n == (44100 // 2048) * 12, chr_n
# ★ 同时锁住「第二维必须是 12 个音级」这一条 —— 少乘 *12 的写法
# ★ 会把 20364 误判成 21，正是本条要防的回归。
assert s.read("chroma.lowres.reference", (0.0, 1.0)).data.ndim == 2, "chroma 是二维端口"

print("FILE-104 ALL INVARIANTS PASS")
PY

# 6 · 冻结面回归（若仓库已有则运行）
python -m pytest tests -q -k "surface or contract or inv_104" 2>/dev/null || true
```

**验收判据**（可机械判定，非「看起来对」）：

- [ ] `python -c "import harmonica_eval.core.surface"` 退出码为 **0**，无 `ImportError` / `ModuleNotFoundError`。
- [ ] `inspect.getsource(harmonica_eval.core.surface)` 中不出现子串 `NotImplementedError`，也不出现子串 `SHELL`。
- [ ] 源码中不出现**完整端口 ID 或二级端口名**字面量（端口名只能来自 `profile.PORTS`）；**裸前缀名允许**（§4.4 派发必需）。判据见上方的 `BANNED` 正则。

  ★★ **本版更正（第三轮盲审 B 的 BLOCK-14 + ⑳ 执行）：原判据没有判别力，且与 §4.4 互斥。** ★★

  **禁的是「完整端口 ID」，不是「裸前缀名」。** 这条界线必须划清，
  否则判据会与规格自己打架：

  | 形态 | 例 | 该不该禁 | 为什么 |
  | --- | --- | --- | --- |
  | 完整端口 ID（含侧别） | `"pcm.mapped.reference"`、`"pitch.practice"` | **禁** | 这就是"硬编码端口名" |
  | 二级端口名 | `"pcm.mapped"`、`"chroma.lowres"` | **禁** | 同上，等价于写死了端口集合 |
  | 裸前缀名 | `"pitch"`、`"notes"`、`"warp_path"`、`"chroma"` | **必须允许** | §4.4 的 `PRODUCER_DISPATCH` 按前缀派发，**没有它们就写不出来** |
  | 模块 docstring | 含端口名做说明 | **必须允许** | §4.4 要求铭牌写 `MUST/INPUT/OUTPUT`，本就要提端口名 |
  | 报错文案 | `"warp_path 必须是 int32[N,2]"` | **必须允许** | 面向人的描述，不是机器可读的键 |

  原判据要求 `warp_path.` 命中数为 0 —— 但 `warp_path` 是
  `build_surface(reference, practice, sample_rate, warp_path)` 的**参数名**，
  于是 `warp_path.dtype` 这种**正常类型检查**被判违规
  （实测参考实现第 551 行被误报）。
  而原 INV-104-1 表里写的是另外五个字面量（`pcm.mapped`/`pitch.`/`chroma.`/`rms.`/`notes.`），
  **与这份清单不一致** —— 同一份文件两处规定不同，实现者只能猜。

  **冻结判据**（唯一口径，两处都改成本式）：

  ```python
  import ast, inspect, re
  import harmonica_eval.core.surface as m

  # 只查「整串恰好是一个完整端口 ID 或二级端口名」的字符串字面量。
  # 不查裸前缀名（派发必需）、不查 docstring、不查报错文案。
  BANNED = re.compile(
      r"^(?:pcm\.(?:mapped|warped)(?:\.(?:reference|practice))?"
      r"|chroma\.lowres(?:\.(?:reference|practice))?"
      r"|(?:pitch|rms|notes)\.(?:reference|practice))$"
  )
  tree = ast.parse(inspect.getsource(m))
  hits = [n.value for n in ast.walk(tree)
          if isinstance(n, ast.Constant) and isinstance(n.value, str)
          and BANNED.match(n.value.strip())]
  assert hits == [], hits
  ```

  实测该判据对参考实现：**命中 0**（裸前缀名与 docstring 都不误报）；
  若把 `"pcm.mapped.reference"` 写进源码，则立刻命中。
- [ ] 源码中不出现 `librosa`、`soundfile`、`scipy`、`import os`、`import io`、`logging`、`import time`、`json`、`pickle`、`threading`、`pathlib`、`harmonica_eval.algorithms`、`harmonica_eval.host`、`harmonica_eval.cockpit`、`harmonica_eval.core.api`、`harmonica_eval.core.ingest` 中的任何一个。
- [ ] `set(build_surface(ref, pra, 44100, wp).manifest().ports.keys()) == set(profile.PORT_INDEX.keys())` 为 `True`。
- [ ] `len(Surface read 全部端口后 manifest().ports) == len(profile.PORTS)`，且数据面**没有**任何未在 `profile.PORTS` 中声明的端口。
- [ ] `all(not v.flags.writeable for v in s._data.values())` 为 `True`；对任一端口数组执行写入抛 `ValueError`。
- [ ] 两次独立 `build_surface`（同一组四输入）逐端口 `content_hash` 逐字符相同。
- [ ] 手工按 `PortDescriptor.content_hash` 的冻结字节序列重算的 sha256，与数据面里该端口的 `content_hash` 逐字符相同。
- [ ] `(2,3)` 与 `(3,2)` 两个 float32 零数组的 `content_hash` 不相同；float32 与 int32 同形状零数组的 `content_hash` 不相同。
- [ ] `s.read("no.such.port", None)` 与 `s.read("", None)` 都抛 `ContractViolation`，**都不**返回数组。
- [ ] `s.read("pcm.mapped.reference", (0.0, 0.001)).element_count == 44`。
- [ ] `s.read("pcm.mapped.reference", (0.0, 3.0)).element_count == s.read("pcm.mapped.reference", None).element_count`。
- [ ] `(1.0, 1.0)`、`(2.0, 1.0)`、`(-0.1, 1.0)`、`(0.0, 3.0 + 1e-9)`、`(0.0, inf)`、`(nan, 1.0)` 六种 `time_range` 各自抛 `ContractViolation`。
- [ ] `s.read("rms.practice", (0.0, 1.0)).element_count == 172` 且 `s.read("chroma.lowres.reference", (0.0, 1.0)).element_count == 252`（`(44100 // 256)` 与 `(44100 // 2048) * 12`），证明 `rms` 与 `chroma` 没有混用帧移，且 chroma 的 `element_count` 正确反映了 `("frame", "bin")` 的第二维（12 个音级）。★ 原写作 `== 21` 是恒假值（把帧数当成了元素数）。
- [ ] `assert_budget({"a": np.zeros(3, "float32"), "b": np.zeros((2, 5), "float64")}) == 92`。
- [ ] `assert_budget({"x": np.zeros(134217728, dtype="float32")}) == 536870912`（恰好等于上限，通过）。
- [ ] `assert_budget({"x": np.zeros(134217729, dtype="float32")})` 抛 `CoreBuildError` 且 `e.code is ErrorCode.CORE_BUILD_FAILED`。
- [ ] `build_surface` 对以下五种输入各自抛 `CoreBuildError`，且**没有**任何 `Surface` 对象被返回：float64 PCM、`sample_rate=22050`、`ndim==2` 的 PCM、int64 的 `warp_path`、列数为 1 的 `warp_path`。
- [ ] `s.manifest().ports` 与 `s._data` 的写入尝试都抛 `TypeError`；`s.manifest = None` 与 `s._data = {}` 都抛 `AttributeError`。
- [ ] `s.manifest() == s.manifest()` 为 `True`，且两次调用的 `list(ports)` 顺序相同。
- [ ] `s.manifest().sealed is True`，且 `s.manifest().reference_duration_sec == 3.0`、`practice_duration_sec == 2.0`（输入为 3 s 与 2 s）。
- [ ] 逐端口 `d.hop_length == profile.PORT_INDEX[p].hop_length`、`d.sample_rate == profile.AUDIO.sample_rate`、`d.timeline_basis is profile.PORT_INDEX[p].timeline_basis`。
- [ ] 逐多维端口 `tuple(d.field_names) == tuple(FIELD_LAYOUTS[p.split(".", 1)[0]])`。
- [ ] `seal(a) is a` 为 `True`，且 `a.strides` 不变。
- [ ] 上述 Python 校验脚本最后打印 `FILE-104 ALL INVARIANTS PASS`，退出码为 **0**。

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] **产物路径 1（主产物，唯一被修改的源文件）**：`harmonica_eval/core/surface.py`
      —— 160 行的壳已被真实实现替换，文件内不再有 `NotImplementedError` 与 `SHELL` 标记。
- [ ] **产物路径 2（测试文件）**：`tests/test_surface_104.py`
      —— 覆盖 §6 表内全部 32 条 INV-104-*，一条不变量至少一个断言函数。
      （若仓库测试目录名不是 `tests/`，落在仓库既有的测试目录，**不新建目录层级**。）
- [ ] **测试输出（原文粘贴，不得改写）**：
      - 命令 1 的 stdout：`harmonica_eval/core/surface.py` 的绝对路径。
      - 命令 2 的 stdout：`shell-clean`。
      - 命令 3 的 stdout：`deps-clean`。
      - 命令 4 的 stdout：`no-hardcoded-port-ids`。
      - 命令 5 的 stdout 末行：`FILE-104 ALL INVARIANTS PASS`，退出码 `0`。
      - 命令 6 的 `pytest` 摘要行：形如 `N passed in X.XXs`，且 `failed` 数为 **0**。
- [ ] **每个端口的 content_hash 实测值表**：11 行，列为
      `port_id | element_type | shape | content_hash`。这张表是与后续 profile 版本
      对照的基线，**必须**随证据包提交（同 build 回归断言的锚点）。
- [ ] **构建预算实测值**：单行，形如
      `total_surface_bytes=NNNNNN (limit=536870912, ratio=0.0XX)`。
- [ ] **实测输入规格**：`reference` 与 `practice` 的采样点数、时长（秒）、
      `warp_path.shape`、生成脚本使用的随机种子（固定种子，`np.random.default_rng(seed)`）。
      没有这四个数，证据不可复现（AGENTS.md 交付前自检项）。
- [ ] **越界自检结论**：逐条对照 §7 的 13 条越界项，写明「未越界」，
      并给出对应证据（源码检索命令 3 / 命令 4 的输出即为第 1 条越界与特征提取
      相关越界的证据）。
- [ ] **未决项清单**：若实现过程中发现 §4 无法确定唯一实现的点，
      提交 `MOLD BREAK`（格式见 §10），**不**自行补默认值。
      若无，明确写「无未决项」。

---

## 10 · ★ 何时必须停止并上报（§22 硬失败对策）

**以下情况必须停止，提交 `MOLD BREAK`，不得自行设计：**

1. 你发现本文件**需要做上层设计**才能实现（定新阈值 / 新口径 / 新端口 / 新错误码）
2. 本文件与任何上游工件**冲突**
3. 你需要的依赖**不在 §3 清单里**
4. §4 的行为规格**不足以确定唯一实现**
5. 你认为 §4 的规格本身**是错的**

**上报格式**（宪章 §37 Gate Challenge）：
```
GATE CHALLENGE
- 相关 Requirement：
- 相关 Build Instruction 章节：
- 实际需要 vs 规格给出：
- 为什么冲突：
- 复现证据：
- 建议的上游处理位置：
```

**绝对禁止**：先做 workaround（§38 明文禁止）· 自行加「合理的」默认值掩盖冲突 ·
静默缩小范围。
