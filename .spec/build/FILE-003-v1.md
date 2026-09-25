# FILE-003 — harmonica_eval/contract.py

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/contract.py`
> 生成依据：`SPEC.md@v2.1` · `contract.py` · `profile.py@CORE_PROFILE_V0.1` · `COMPONENTS.md`
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-003 |
| 所属组件 | COMP-CONTRACT（C1/C2/C3/C4 四个组件之间的分界线，本身不是组件；全仓依赖链的根） |
| 层级 | L3（symbol / implementation） |
| 上游 | 无运行期输入（铭牌 INPUT：（无）——纯声明、无行为）。规格上游：`SPEC.md@v2.1`、`COMPONENTS.md@v2`、`PLAN.md@v2`、`profile.py@CORE_PROFILE_V0.1`（端口封闭清单的唯一来源）。import 侧上游（谁调用我）：C1 host、C2 core、C3 algorithms、C4 cockpit 的全部实现文件与 `profile.assert_profile_integrity()`——机械分析证实共 **11 个文件**依赖本文件，它是全仓唯一割点 |
| 下游 | 本文件不调用任何人（MUST NOT：零本包 import，依赖链根）。输出侧（我给谁输出）：C2 core（实现 `HostContract` 与 `AlgorithmDataContract`）；C3 algorithms（消费 `PortDescriptor` / `AlgorithmDataContract` / `ErrorCode`，返回 `AlgorithmResultEnvelope`）；C1 host（消费 `SessionState` / `COMMAND_LEGALITY` / `UI_PAYLOAD_KEYS` / `FORBIDDEN_OPERATIONS` / `AlgorithmResultEnvelope`）；C4 cockpit（消费 `UiView` / `UiSeries` / `UiScalar` / `UiCommandKind` / `UiProjectionPort`）；profile.py（消费 `FIELD_LAYOUTS` / `UNITS_VOCABULARY` / `CORE_REQUIRED_PORTS` 做完整性校验） |
| 同层邻居 | `profile.py`（端口封闭清单与 profile 常量的唯一定义处，本文件的端口语义由它实例化）；`core/api.py`（HostContract 实现入口，其 `status()` 只外泄 SessionState）；`algorithms/dynamics.py`（AlgorithmDataContract 消费方，曾因 TimelineBasis 第一版含糊定义写出无法满足的 MUST，是本文件冻结口径的直接受益者） |

**你的权限**：只实现本文件。不得修改任何其他文件，不得修改契约，
不得新增端口，不得新增依赖。

---

## 2 · 这个文件为什么存在

**Product Intent 追溯**：SPEC.md 的产品意图是「双音频对比 → 客观数值指标」，由四个组件协作完成：C1 Framework/Host（编排）、C2 Audio Core（数据面）、C3 Algorithms（指标）、C4 Cockpit（展示）。SPEC.md §5.5 规定时间轴两轴分离；宪章 §21 把 Cross-Agent Semantic Variance 列为结构性风险：四个组件（尤其由不同实现者/不同代理完成时）若对「状态、时间基准、端口、结果、失败」各自造词，就会在**无报错的情况下静默算错**。本文件把这套共享词汇冻结为**可 import 的实体**（Enum / dataclass / Protocol / 常量元组），使「四个组件的边界」成为机器可检查的事实，而不是文档里的约定。

**删掉它会坏掉什么（逐条机械后果）**：

1. **编译级断裂**：机械分析证实全仓 11 个文件 import 本文件；删除后 C1/C2/C3/C4 与 profile 全部 ImportError，仓库不可构建。它不是工具库，是结构承重墙。
2. **C2 失去实现对象**：`HostContract`（7 操作）与 `AlgorithmDataContract`（2 个纯查表操作 + 1 个只读状态属性 `resolution`，不计入操作数）不存在 → core 无法声明它对 C1 暴露什么；`SessionState` 消失 → `status()` 无返回类型，C2 内部阶段（INGESTING、ALIGNING、BUILDING_PORTS 这类名字）失去「禁止外泄」的对照物，深组件边界瓦解。
3. **C3 失去数据面词汇**：`PortDescriptor` / `FIELD_LAYOUTS` 消失 → 算法无从判断端口是否有自己要的量、多维端口第二维字段顺序无共同事实来源 → 两个实现者写出不同内存布局，读出的 `f0_hz` 是 `voiced` 且**不报错**。`AlgorithmResultEnvelope` 消失 → 「失败也要返回信封」的隔离机制不存在，单个算法的异常穿透到 C1 打断全部流程。
4. **节奏指标静默算错**：`TimelineBasis` 消失 → 无人在结构上强迫端口声明挂哪条时间网格 → 节奏指标被放到归一化网格上计算，抢拍拖拍被静默抹掉（结果恒为 0 且不报错）。这正是宪章 §21 缺陷的原型。
5. **失败语义退化**：`ErrorCode` / `HarmonicaError` 族消失 → 失败退化为裸异常与自由字符串，C1 无法归一化上报，COMPONENTS.md §7 失败语义表失去唯一权威来源。
6. **编排权泄漏无人能查**：`FORBIDDEN_OPERATIONS` / `COMMAND_LEGALITY` / `UI_PAYLOAD_KEYS` 消失 → Core 长出 align / fft / register_algorithm 这类越界方法、界面命令载荷键名各写各的，都没有机械断言可查。

六条全部指向同一根因「跨组件词汇不统一 ⇒ 静默错误」，故本文件必须存在，且只含声明。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**（封闭清单，逐项列出，无任何省略）：
- 标准库（共 4 个，用法冻结）：
  - `__future__` —— 仅 `from __future__ import annotations`
  - `dataclasses` —— 仅 `dataclass` 与 `field`
  - `enum` —— 仅 `Enum`
  - `typing` —— 仅 `Any`、`Callable`、`Mapping`、`Protocol`、`Sequence`
- 第三方（共 2 个）：
  - `numpy` —— 仅作类型注解用途；本文件不调用任何 numpy 函数
  - `numpy.typing` —— 仅 `NDArray`（用于 `BufferView.data` 注解）
- 本包内：**无**。本文件是全仓依赖链的根，一个本包模块都不得 import（包括 `profile.py`）。

**禁止 import**（对上面清单的补集，逐项点名高风险项）：
- 本包任何模块：`harmonica_eval.core.*`、`harmonica_eval.host.*`、`harmonica_eval.algorithms.*`、`harmonica_eval.cockpit.*`、`harmonica_eval.profile` —— 铭牌 MUST NOT 明文
- `hashlib` —— `content_hash` 的 sha256 算法由 C2 在 Seal 时执行；本文件**只冻结算法定义**（见 §4.6），不得在本文件执行它（执行即违反「任何计算」禁令）
- `os`、`pathlib`、`io`、`json`、`logging`、`abc`、`collections`、`re`、`math`、`random` —— 本文件无 I/O、无日志、无计算
- `scipy`、`librosa`、`soundfile`、`pydantic`、`attrs` —— 任何一个都构成新增第三方依赖
- 除上列 6 项之外的其余全部标准库与第三方模块

★ 违反本清单即触发 §10 第 3 条（依赖不在清单内），必须停止上报，不得自行「顺手」引入。

★ 本清单必须**穷举**，不许出现「等」「之类」。

---

## 4 · 你要实现什么（行为规格）

**总则**：本文件是纯声明模块。每个公开符号只做「定义 + 语义注释」，不承载 I/O 或业务计算。有限实体逻辑仅限三处：`ResolutionView.is_available` 只查 `frozenset` 成员（`harmonica_eval/contract.py:411-413`）、`AudioFormat.__post_init__` 的输入校验（`harmonica_eval/contract.py:171-175`）、`HarmonicaError.__str__` 的展示格式化（`harmonica_eval/contract.py:944-953`）。以下按 `__all__` 分组逐符号写。

### 4.0 类型注记约定

- 文中「秒」一律指 `float`，单位秒；「帧」指分析帧号（`int`）；「采样点」指样本下标（`int`）。
- 时间基准缺失的量不存在：凡描述「时刻/时长/区间」的字段，其宿主符号必须携带 `TimelineBasis` 或 `timeline_basis` 字段。

### 4.1 SessionState（Enum，6 值）与会话状态机

值（`str` 子类，字符串值与成员名相同）：`CREATED` / `INPUT_READY` / `BUILDING` / `DATA_READY` / `FAILED` / `CLOSED`。各值语义：CREATED=会话已创建尚无输入；INPUT_READY=两段音频资产都已就位尚未开始构建；BUILDING=C2 正在构建数据面，此状态下禁止触发任何算法；DATA_READY=数据面已按 profile 预生成完毕并 Seal，是**算法的唯一合法触发点**；FAILED=构建或运行失败，数据面**不存在**（不得部分发布）；CLOSED=会话已销毁，资源已释放。

**合法状态转移表（封闭，逐条枚举）**：

| 从 | 触发 | 到 |
| --- | --- | --- |
| CREATED | set_reference 与 set_practice 中任一成功 | INPUT_READY |
| INPUT_READY | build_surface 开始 | BUILDING |
| BUILDING | build_surface 成功（Seal 完成） | DATA_READY |
| BUILDING | build_surface 抛 CoreBuildError | FAILED |
| DATA_READY | destroy_session | CLOSED |
| FAILED | destroy_session | CLOSED |
| 任一非 CLOSED 状态 | destroy_session | CLOSED |
| BUILDING | CANCEL（COMMAND_EFFECTS） | **不打断同步构建**；构建完成后按 `CANCEL` 的目标转移生效 |
| FAILED | RESET（COMMAND_EFFECTS） | CREATED（销毁数据面与已登记输入，会话对象保留） |

非法转移（必须拒绝且状态不变）：任何向「回退方向」的转移（如 DATA_READY→BUILDING、INPUT_READY→CREATED，RESET/CANCEL 按上表除外）；FAILED 之后除 destroy_session/RESET 外的一切操作；CLOSED 之后的一切操作。**C1 对 status() 能看到的只有这 6 个值**；C2 内部阶段名（INGESTING / ALIGNING / BUILDING_PORTS 等）禁止出现在返回值、日志字段名与 UiView 之外的任何跨组件边界上。

### 4.2 TimelineBasis（Enum，2 值）——含已修真实缺陷的根因

值：`REFERENCE` = **源时间网格**（以参考演奏的时钟为刻度，保留原始时间关系；距离与时刻都有绝对意义——第 10 秒就是第 10 秒）；`WARPED` = **归一化网格**（把练习拉伸到与参考等长后的网格；只有「第几个音」有意义，绝对时刻没有意义——第 10 秒在这里只是位置标记）。

**两轴描述的是「哪条时间网格」，不是「什么物理量」。** 同一个物理量（如练习的 PCM、练习的能量）在两套网格上**各有一份端口**——这才是 SPEC §5.5「同时提供保留源时间与时间归一化两种表示」的含义。因此 REFERENCE **不是**「参考演奏专属的轴」：练习侧的 `pcm.mapped.practice` 与 `rms.practice` 也在它上面，它们描述练习在参考时钟上的样子。

★ 已修真实缺陷的根因（必须写进实现者认知）：

1. 第一版把 REFERENCE 定义成「保留源时间。对齐后重采样到参考演奏的时间轴」——**两句话互相矛盾**（既保留源时间，又重采样到别人的时间轴，是两条不同的网格）。该含糊定义向下游传播，直接导致 `algorithms/dynamics.py` 写出一条**无法满足的 MUST**（要求读 WARPED 轴的 `rms.*`，而数据面里不存在该端口）；两个独立盲审模型各自复现了这个冲突。修正后的命名即本条的冻结语义。
2. **REFERENCE 只表示「保留源时间、未被时间归一化」，不表示两侧帧号一一对应。** 两段是独立录音，采样点数与帧数默认**不相等**；同一个「第 1000 帧」在参考侧与练习侧的物理时刻没有对应关系。故**「逐帧相减」无定义**——任何「参考数组−练习数组」式的逐帧运算在源时间网格上都是构造性错误。比较必须**按音配对**（经 `warp_path` 或 `notes.*` 的 onset 对齐，把两侧各自网格上的对应音找到，再对配对后的量做差），或改在 WARPED 网格上比较「第几个音」的含义。凡算法需要逐帧差，唯一合法前提是两侧端口**同网格、同 shape、同 hop_length**（如 `pcm.mapped.reference` 与 `pcm.mapped.practice` 在标准化后同长同率）。
3. WARPED 网格上「练习比参考早/晚多少」**不存在**（已被归一化抹掉）。**禁止**在 WARPED 上计算或展示任何节奏类量——那是构造性错误，结果恒为 0 且不报错。节奏类指标必须在 REFERENCE 上算（SPEC §5.5 强制）。

配套枚举 `AlignmentRepresentation`（2 值）：`MAPPED`=保留源时间（对齐后落在参考时间轴上）；`WARPED`=时间归一化（与参考等长）。数据面**始终**包含这两份对齐 PCM（本仓自定保证，原写「宪章 §11 逃生口」是伪造引用）；因为它们永远存在，任何算法都能拿 PCM 自行做特有预处理。

### 4.3 AudioFormat（frozen dataclass）

- 输入（构造参数）：`sample_rate: int`（Hz，正整数；实测口径：同一段音频在 22.05 kHz 下 f0 会被判低八度（−1200 音分），44.1 kHz 下正常——采样率是**结果的成因**，不是元数据）；`channels: int`（恒为 1，多声道在 ingest 阶段已下混）；`dtype: str`（恒为 `'float32'`，numpy dtype 名称）。
- 输出：一个不可变实例；所有端口继承它，全局唯一。
- 执行体（`__post_init__` 校验）：`channels != 1` → 抛 `ValueError("契约要求 mono")`；`dtype != "float32"` → 抛 `ValueError("契约要求 float32")`。`sample_rate` 无数值校验。
- 边界：不存在的边界分支——三个字段都是必填位置参数，无默认值。
- 不变量：实例化后字段值永不改变（frozen）；同一数据面内所有 `PortDescriptor.sample_rate` 与它一致。

### 4.4 FIELD_LAYOUTS（常量映射，4 键）

- 类型：`Mapping[str, tuple[str, ...]]`；键 = port_id 的**类别前缀**（第一个 `.` 之前的部分）；值 = 第二维字段名元组，**顺序即内存布局顺序**。
- 穷举内容（全部 4 键，逐字冻结）：
  - `"warp_path"` → `("reference_frame", "practice_frame")`
  - `"pitch"` → `("f0_hz", "voiced", "confidence")`
  - `"notes"` → `("onset_sec", "f0_hz", "rms")`
  - `"chroma"` → `("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")` —— 12 个音级，**从 C 开始**（bin 0 = C，依次半音上行；**不是**从 A 开始）
- 单位/取值域：`warp_path` 两列单位 `index`（帧号，见 §4.7 warp_path 特殊语义）；`pitch.f0_hz` 单位 `hz`、`pitch.voiced` 为布尔有效性、`pitch.confidence` 无量纲置信度；`notes.onset_sec` 单位 `seconds`、`notes.f0_hz` 单位 `hz`、`notes.rms` 单位 `rms`；`chroma.*` 各列单位 `chroma`（无量纲相对值）。
- 存在理由：`dimensions=('frame','field')` 只说了「第二维是字段」，没说字段是什么、什么顺序。没有这张表，两个实现者会写出不同内存布局，读出的 `f0_hz` 可能是 `voiced` 且**不报错**，只静默算错。chroma 的音级起点同理有歧义（bin 0 是 C 还是 A），故一并冻结。
- 校验接线：`profile.assert_profile_integrity()` 检查——凡 `len(dimensions) > 1` 的端口，其前缀必须在本表内，且端口实际字段数必须等于 `len(field_names)`（profile 侧可静态检查）。★ G6 修正：原写「字段数必须等于 `dimensions[-1]` 声明的大小」按字面无法实现，因为 `dimensions` 里是语义名字符串（`'frame'`/`'bin'`/`'field'`），不含尺寸；真正尺寸在 `PortDescriptor.shape` 里且运行期才填。
- 边界：查不到的类别前缀 → `KeyError`（ProfileError 的表现，见 §5）；本常量本身不做运行期查表校验。
- 不变量：元组顺序永不改变；新增多维端口类别必须先改本表并升契约版本。

### 4.5 CONTENT_HASH_MAGIC 与 UNITS_VOCABULARY（常量）

- `CONTENT_HASH_MAGIC: bytes = b"harmonica-eval/surface/v1\x00"`。作用：`content_hash` 的域分隔前缀（G12），让该 hash 的输入空间与任何其他用途的 sha256 不重叠；末尾 `\x00` 是长度分隔，防止 `"a"+"bc"` 与 `"ab"+"c"` 碰撞。取值逐字节冻结。
- `UNITS_VOCABULARY: frozenset[str]`，**穷举 10 个合法值**：`amplitude`（`pcm.mapped.*` / `pcm.warped.*`）、`chroma`（`chroma.lowres.*`）、`hz`（`pitch.*`）、`index`（`warp_path` / `notes.*`）、`rms`（`rms.*`）、`cents`、`db`、`seconds`（后三个为算法 payload 预留，当前未被任何 profile 端口使用；预留项必须由某个未来 profile 真正使用，否则应删——本词表不收集「以后可能有用」的值）、`ratio`（比例，如 `off_pitch_ratio` / `early_ratio`）、`count`（无量纲计数，如 `n_notes_used` / `n_unpaired`）。
- 存在理由（G10）：`units` 是算法判断「这个端口是不是我要的量」的依据；开放式字符串会让 `"hz"`/`"Hz"`/`"hertz"` 三种写法在 `== "hz"` 判断下静默不匹配。第一版举例还漏了 profile 实际在用的 `chroma`。取值由 `assert_profile_integrity()` 检查。
- 不变量：词表封闭；端口 `units` 取值必属此表；比较一律用本表内的小写字面量精确相等。

### 4.6 PortDescriptor（frozen dataclass，端口自描述头）

- 输入（构造参数，逐字段）：
  - `port_id: str` —— 稳定标识（如 `'pcm.mapped.reference'`），Seal 后不可变。
  - `schema_version: str` —— 端口 schema 版本字符串。
  - `element_type: str` —— numpy dtype 名称，取值域 `{'float32', 'int32'}`（profile 实际使用的全部取值）。
  - `dimensions: Sequence[str]` —— 维度语义名，合法取值逐个为 `'sample'` / `'frame'` / `'warp_point'` / `'axis'` / `'field'` / `'bin'`（profile 实际使用的全部语义名）。
  - `shape: Sequence[int]` —— 各维尺寸，运行期填充。
  - `units: str` —— 物理单位，取值必属 `UNITS_VOCABULARY`（10 值，见 §4.5）。
  - `field_names: Sequence[str] = ()` —— 第二维字段名，顺序即内存布局顺序；单维端口为空元组；多维端口必须与 `FIELD_LAYOUTS[类别前缀]` 完全一致（防止静默错位的唯一手段）。
  - `timeline_basis: TimelineBasis = TimelineBasis.REFERENCE` —— 必填语义；忘记声明会导致节奏指标算错。
  - `hop_length: int = 0` —— 该端口的**帧移**（单位：采样点）。帧类端口必填；非帧类（index / 逐音表）为 0。数值事实：`profile.ALIGN.hop_length = 2048`（chroma 帧移），`MATERIALIZE.rms_hop_length = 256`（RMS 帧移），两者相差 8×，故必须在描述符里逐端口声明，不许实现者猜（G5）。`read(time_range)` 的秒→帧换算依据**本字段**，不是 `profile.ALIGN.hop_length`。
  - `sample_rate: int = 0` —— 采样率（Hz），必填语义；`0` 表示与采样率无关（如 chroma / index 类）。
  - `content_hash: str = ""` —— Seal 时计算的内容指纹（sha256 hex，64 个十六进制字符）。
- `content_hash` 冻结算法（G12，实现须逐字节照做，在 C2 Seal 期执行，本文件只定义）：`h = hashlib.sha256()`；`h.update(CONTENT_HASH_MAGIC)`；`h.update(port_id.encode("utf-8"))`；`h.update(element_type.encode("utf-8"))`；`h.update(np.asarray(shape, dtype="<i8").tobytes())`（小端）；`h.update(data.tobytes(order="C"))`（C 序、原始 dtype）；`content_hash = h.hexdigest()`。三条必须满足的性质：① 包含 shape 与 dtype（否则 (2,3) 与 (3,2) 同 hash）；② 固定小端字节序（否则跨架构不可比）；③ C 序展平（否则同数据的非连续视图会算出不同 hash）。用途：同一实现内回归 + 跨实现对照；**不**用于安全用途（不是抗碰撞承诺）。
- 边界：frozen dataclass，构造后不可变；`field_names`/`dimensions`/`shape` 传入后不得被外部修改（实现侧存放元组或只读序列）。
- 不变量：`len(field_names) == 0` 当且仅当 `'field'` 不在 `dimensions` 里；多维端口 `tuple(field_names) == FIELD_LAYOUTS[port_id.split('.', 1)[0]]`。

### 4.7 BufferView 与 SurfaceManifest

- `BufferView`（frozen dataclass）：对某端口的只读借用视图。字段：`data: npt.NDArray[Any]`（`field(repr=False)`，实际 numpy 数组）、`element_count: int`（恒等于 `data.size`，即各维尺寸之积）、`element_type: str`（与宿主 `PortDescriptor.element_type` 相同）。所有权始终属于 C2；借用方不得修改、不得释放、不得跨会话持有；实现层必须保证 `data.flags.writeable is False`。边界：`data.ndim` 必须等于描述符 `dimensions` 的长度；`element_count == product(data.shape)` 不成立即为实现缺陷（ContractViolation 级别的事实）。
- `SurfaceManifest`（frozen dataclass）：数据面自描述清单。字段：`profile_version: str`（构造数据面用的 profile 版本）、`audio_format: AudioFormat`（§4.3）、`reference_duration_sec: float`（参考演奏时长，秒）、`practice_duration_sec: float`（练习演奏时长，秒）、`ports: Mapping[str, PortDescriptor]`（全部端口，键为 port_id）、`sealed: bool`（Seal 后为 True）。外部通过它枚举端口而**无需预知端口清单**——这是「深组件」的关键：C2 内部可重组而不破坏外部。不变量：`sealed is False` 时该清单**不得**交给任何算法；`ports` 必须包含 `CORE_REQUIRED_PORTS` 的全部 2 项。
- `ResolutionView`（frozen dataclass）：插件运行入口可见的输入解析只读视图。字段：`available: frozenset[str]`（本次实际可用的 required / optional 端口）与 `missing_optional: frozenset[str]`（声明了但未取得或未通过检查的 optional 端口）；只有只读查询方法 `is_available(port_id: str) -> bool`，没有 setter 或变更方法。插件读取 `missing_optional` 即可知道哪些 optional 没拿到；它是契约层视图类型，不是 runtime 的原始 `InputResolution`（源码事实：`harmonica_eval/contract.py:390-413`；查询实现为 `return port_id in self.available`，不修改任何状态）。

### 4.8 AlgorithmResultEnvelope（frozen dataclass，算法标准回执）

- 输入（构造参数）：`algorithm_id: str`；`algorithm_version: str`；`status: str`，取值域**封闭四元** `{'OK', 'DEGRADED', 'INCOMPATIBLE', 'FAILED'}`；`required_ports: Sequence[str]`（算法声明需要的端口，仅用于兼容性检查，单向）；`consumed_ports: Sequence[str]`（本次**实际读取**的端口，仅用于证据与追溯，**绝不**反向触发 C2 生成数据）；`payload: Sequence[UiScalar | UiSeries]`（结果本体；每个标量最终成为一个 `UiScalar`，逐音序列成为一个 `UiSeries`，字段名由对象自身的 `key` 自描述，框架不维护第二份键名清单）；`error_code: str | None = None`（失败时填 `ErrorCode` 的 `.value`，如 `"ALGORITHM_FAILED"`）；`error_detail: str | None = None`；`elapsed_sec: float | None = None`（算法耗时，秒）；`coverage: float | None = None`（覆盖比例，0.0–1.0；无法测量时为 `None`，不得用 0.0 冒充）；`warnings: tuple[str, ...] = ()`（人可读告警，每条一句）。
- 输出/用途：C3 每个算法运行后返回一个实例；C1 逐个消费它更新 UiView 与证据包。
- **核心纪律：算法失败也必须返回信封（status='FAILED'），而不是抛异常穿透到 C1。** 这是 C1 隔离故障的唯一机制：单个算法崩溃不得打断其余算法与会话。
- 四值语义：`OK`=兼容并正常完成全部预期能力；`DEGRADED`=正常运行但因 optional 输入缺失或明确的输入质量限制，只提供部分能力，`coverage` 或 `warnings` 至少一项必须非空；`INCOMPATIBLE`=required 输入不满足，入口根本不应调用（对应 `PLUGIN_INCOMPATIBLE`）；`FAILED`=输入本来兼容但执行失败。`OK` / `DEGRADED` 的 `error_code` 必须为 `None`。
- 边界：`status='OK'` 时 `payload` 必须非空且 `error_code is None`；`status='DEGRADED'` 时 `payload` 可非空，但必须以 `coverage` 或 `warnings` 明示降级证据；`status='FAILED'` 时 `error_code` 必须非 None；`status='INCOMPATIBLE'` 表示 `required_ports` 中存在数据面没有的端口（对应 `PLUGIN_INCOMPATIBLE`）。
- 不变量：`consumed_ports ⊆ required_ports`；`error_code` 非 None 时必属 `ErrorCode` 的 12 个 `.value` 之一；信封一旦构造不可变。★ 算法清单的权威是 `algorithms.registry.Registry` 的显式注册结果；payload 字段名的权威是插件产出的 `UiScalar` / `UiSeries.key`，不再存在框架侧按算法标识索引的冻结表。

### 4.9 AlgorithmDataContract（Protocol，C3 → 数据面，2 个纯查表操作 + 1 个只读状态属性）

**2 个纯查表操作**（`manifest()` / `read()`）**+ 1 个只读状态属性 `resolution`，不计入操作数**。现有
`tools/check_counts.py` 的旧数量判据只核对 callable 操作，不能把本属性计入操作数；这一判据
待负责人的独立任务更新，本文件不删减或改写事实来迎合它。
`resolution` 返回 `ResolutionView`（`harmonica_eval/contract.py:654-678`）。

实现者：C2 产出的 Surface；调用者：C3 各算法。设计裁定（负责人，不可推翻）：**Core 预生成，端口清单封闭，算法适配 Core**。接口明确区分 **2 个纯查表操作**（`manifest()` / `read()`）与 **1 个只读状态属性 `resolution`，不计入操作数**。`resolution` 是 `@property`，返回 `ResolutionView`；`read()` **无副作用**——不触发任何计算、不会失败于「算不出来」；Seal 时数据面里已有算法要的一切，若算法需要数据面之外的东西，从 PCM 自己算。成员定义：`harmonica_eval/contract.py:654-678`。

- `manifest() -> SurfaceManifest`：输入无；输出 §4.7 的清单。用于枚举端口并判断兼容性。纯读取，无副作用，不抛受控异常。
- `resolution -> ResolutionView`（**只读状态属性，不计入操作数**）：返回本次插件运行可见的输入解析视图。插件通过 `view.missing_optional` 知道哪些 optional 没拿到，也可调用只读查询 `view.is_available(port_id)`；不得把 runtime 的原始 `InputResolution` 传入或暴露给插件。`resolution` 无 setter，C2 的 `core/surface.py::Surface` 当前也不提供该状态（`harmonica_eval/core/surface.py:112-144`），runtime 计划只用 `ResolvedSurface` 适配器组合 C2 数据面与解析视图后再交给单参 `entry`；但该适配器的 `manifest()` / `read()` / `resolution` 当前**均为 SHELL**，实现未注入，故这条装配链目前尚不可工作（契约意图见 `harmonica_eval/contract.py:654-678`，空壳事实见 `harmonica_eval/algorithms/runtime.py:99-131`）。**已知未决：谁负责把 C2 Surface 包装成完整 `AlgorithmDataContract`（含 `resolution`）仍待裁定；不得把 C2 Surface 改称已实现该属性。**
- `read(port_id: str, time_range: tuple[float, float] | None = None) -> BufferView`：
  - 输入：`port_id`（必须已存在于数据面）；`time_range` **统一以秒为单位**（不是帧、不是采样点），左闭右开 `[t0, t1)`；`None` ⇒ 整段。坐标含义由该端口 `timeline_basis` 决定：REFERENCE → 相对参考演奏起点的秒；WARPED → 相对时间归一化后起点的秒。秒→帧/索引换算由**实现**负责，调用方不得自行乘除 hop；换算依据是该端口自己的 `hop_length`。
  - 换算规则（按端口 `units` / `dimensions`，冻结）：
    - `units == "amplitude"` → 帧/位置 = 秒 × sample_rate（采样点）
    - `dimensions` 含 `"frame"` → 位置 = 秒 × sample_rate / hop_length（帧）
    - `units == "index"` → 位置 = 秒 × sample_rate / hop_length（索引）
    - `units == "chroma"` → 同 frame 规则
  - `notes.*` 特殊：逐音表（非等间隔栅格），`hop_length=0` 的含义即「本端口不是栅格，不要用帧移换算」；`time_range` 按 `field_names` 中的 `onset_sec` **筛选行**，返回 `onset_sec ∈ [t0, t1)` 的音。
  - `warp_path` 特殊：路径点表（`units="index"` 指的是**列语义**（帧号），不是时间单位），时间窗按 `reference_frame` 换算后的秒值筛选（因其 basis 为 REFERENCE）。
  - 输出：§4.7 的 `BufferView`；保证 `data.flags.writeable is False`、`data.ndim == len(descriptor.dimensions)`、`element_count == product(data.shape)`。
  - 失败语义（**必须严格区分，不得混淆**）：端口不存在 → 抛 `ContractViolation`；`t0 >= t1` 或 `t1` 超出该端口时长 → 抛 `ContractViolation`；**绝不返回空视图冒充成功**（宪章 §5.6）。唯一例外：时间窗**合法**但窗内确实无数据（如 `notes.*` 落在一段静音里无任何 onset）→ 返回**空视图是正确的**，不是静默降级，因为「窗内没有音」是真实答案；判据：`t1` 在时长内 ⇒ 空是合法结果；`t1` 超时长 ⇒ 抛错。
  - 边界：单元素窗（`t1 - t0` 恰好覆盖 1 帧/1 音）返回 1 行数据；NaN 时刻不是合法输入，`t0`/`t1` 为 NaN 时按「超界」处理抛 `ContractViolation`。
  - 不变量：同参重复调用返回内容相等（纯查表）；不产生任何状态改变。

### 4.10 HostContract（Protocol，C1 → C2，7 操作，不多不少）

实现者：COMP-C2 Audio Core；调用者：COMP-C1 Framework / Host。逐一：

1. `create_session(profile_version: str) -> str`：输入 profile 版本字符串（如 `'CORE_PROFILE_V0.1'`，必须显式传入——数据面内容是 (reference, practice, profile_version) 的函数，没有它「同一对输入」不成立）；输出 session_id（str，唯一句柄）。状态 CREATED。
2. `set_reference(session_id: str, uri: str) -> None`：登记参考演奏，**不触发**解码或计算。合法状态 CREATED / INPUT_READY；两段都登记后 → INPUT_READY。★ G8 修正：第一版签名无 `session_id`，而其余 5 个操作都要求它——契约内部不自洽，多会话直接歧义、单会话需「当前会话」隐含状态；修正后**所有会话级操作显式定位会话**，不引入隐含状态。
3. `set_practice(session_id: str, uri: str) -> None`：同上，登记学习者演奏。
4. `build_surface(session_id: str) -> None`：**一次性预生成**全部端口并 Seal。前置：状态 == INPUT_READY；后置：状态 == DATA_READY，数据面不可变；失败：抛 `CoreBuildError`，状态 → FAILED，**不得部分发布**，资源全部释放，且未触发任何算法。本操作**不接收任何算法信息**（不知道谁会来读）。构建为同步阻塞调用，内部四阶段（ingest → align → features → surface）禁止外泄；`CANCEL` 在 `BUILDING` 时不打断构建，契约没有取消标志的设置或观察通道，故不得注入后台线程、回调或 checkpoint。
5. `status(session_id: str) -> SessionState`：只返回 §4.1 的 6 值之一；C2 内部阶段不得外泄。
6. `acquire_surface(session_id: str) -> AlgorithmDataContract`：取得数据面只读句柄。前置：状态 == DATA_READY，否则抛 `ContractViolation`；句柄有效期至 destroy_session。
7. `destroy_session(session_id: str) -> None`：销毁会话并释放全部资源；之后使用旧句柄的任何行为都是 `ContractViolation`。

失败语义共用规则：`session_id` 不存在或已销毁 → `ContractViolation`；状态不满足前置 → `ContractViolation`；输入资产不可读/过短/静音/过长 → `CoreBuildError`（携带对应 `ErrorCode`），见 §5。不变量：7 操作封闭，不多不少；`FORBIDDEN_OPERATIONS` 的 10 个名字绝不允许出现在 C2 的公开方法名里（判据：C1 需要其中任何一个 = 编排权或算法知识泄漏进了 Core，违反宪章 §5.9 与 §47.6）。`FORBIDDEN_OPERATIONS` 穷举（10 项）：`align`、`fft`、`stft`、`compute_feature`、`generate_pitch_input`、`generate_plugin_requirement`、`prepare_for_pitch`、`prepare_for_timing`、`register_algorithm`、`list_algorithms`。

`CORE_REQUIRED_PORTS: tuple[str, ...] = ("pcm.mapped.reference", "pcm.mapped.practice")` —— 任何 profile 都必须包含的端口（本仓自定保证；原引「宪章 §11」为伪造引用）。其余端口可随 profile 版本变化，但这两份对齐 PCM 永远存在：保证算法永远能自行做特有预处理，profile 只决定「快不快」，不决定「能不能」。

### 4.11 ErrorCode（Enum，12 值）——逐码触发条件

每个码的 `.value` 与成员名相同。触发条件逐码冻结：

1. `INPUT_UNREADABLE` —— 归属 C2。触发：音频文件不存在 / 权限拒绝 / 无法解码（坏文件、不支持的容器与编码）。结果：数据面不存在，算法不启动。
2. `INPUT_TOO_SHORT` —— 归属 C2。触发：任一段时长短于最小可分析长度（阈值由 profile.AUDIO 定义，本文件不定数值）。结果：数据面不存在。
3. `INPUT_SILENT` —— 归属 C2。触发：整段静音，无法建立任何有效映射。结果：数据面不存在。
4. `INPUT_TOO_LONG` —— 归属 C2。触发：任一段时长长于 `profile.AUDIO.max_duration_sec`（规格上限 **120 s**）。★ 修复记录：写 ingest 时发现的自身缺口——原契约只有 TOO_SHORT 没有 TOO_LONG，超长音频会被勉强归类为「不可读」掩盖真实原因。处理：**拒绝，不静默截断**（静默截断会让分析结果对应到用户不知道的时间范围）。结果：数据面不存在。
5. `CORE_BUILD_FAILED` —— 归属 C2。触发：标准化 / 对齐 / 预生成任一步失败（上述 4 个输入码之外的构建期失败）。结果：**不得部分发布**，全部资源释放，状态 → FAILED。
6. `ALIGNMENT_UNRECOVERABLE` —— 归属 C2。触发：无法建立有效时间映射。**禁止**静默退化为「逐点硬比」（宪章 §5.6）——逐点硬比会产出看似有效实则无意义的指标。结果：状态 → FAILED。
7. `PLUGIN_INCOMPATIBLE` —— 归属 **C1 判定**。触发：算法 `required_ports` 声明了数据面没有的端口。结果：该算法返回 `AlgorithmResultEnvelope(status='INCOMPATIBLE')`；**数据面仍有效**，其他算法不受影响。
8. `ALGORITHM_FAILED` —— 归属 C3。触发：算法崩溃（异常）/ 产出含 NaN / 产出非法结果。结果：该算法信封 `status='FAILED'`；数据面与其余算法不受影响。
9. `ALGORITHM_RESULT_INVALID` —— 归属 **C1（校验）**。触发：算法返回的结果违反自描述契约（如 payload 含非 `UiScalar` / `UiSeries` 对象、单位不在 `UNITS_VOCABULARY`、`UiSeries.t` / `values` 长度不等，或 `DEGRADED` 缺少 `coverage` / `warnings` 证据）。结果：该插件按失败处理；数据面仍有效。
10. `ALGORITHM_TIMEOUT` —— 归属 C1。**v0.1 未实现**（已知缺口：死循环会卡住流程）；保留编号占位，任何路径**不得**在 v0.1 产出它。
11. `COCKPIT_DETACHED` —— 归属 C4。★ G14 修正：第一版定义了它但**没有任何地方能产生**（`UiProjectionPort` 只有 snapshot/submit，无上报通道，C1 也不检测界面存活）——这是已删除功能的残留，不是待实现接口。**v0.1 不会产生此码**；保留它只为让 `ErrorCode` 编号在文档/报表中不偏移（已发出的证据包不失效）。v0.1 对界面断开的实际处理（MT-007）：C4 进程消失 → C1 **什么都不做**，会话继续（不变量 F：C4 可缺席）。若将来要记录界面事件，正确做法是新增事件通道，不是复用 ErrorCode（断开不是错误，塞进错误码会污染失败统计）。
12. `INTERNAL_ERROR` —— 兜底。触发：出现即表示存在未分类失败路径，应视为**缺陷**上报，不得把它当正常分支使用。

异常族（§4.13 详述）与码的归属关系：`ContractViolation`（程序缺陷，不可重试）、`CoreBuildError`（承载码 1–6）、`AlgorithmError`（承载码 8）。

### 4.12 HarmonicaError 族（3 个异常类 + 基类执行体）

- `HarmonicaError(Exception)`，dataclass 字段：`code: ErrorCode`（必填）；`detail: str = ""`；`session_id: str | None = None`；`port_id: str | None = None`；`component: str | None = None`。执行体 `__str__`（唯一执行代码，展示用）：输出 `[{code.value}] ({component}) {detail or "no detail"} session={session_id} port={port_id}`，其中 component / session / port 三段仅在对应字段非 None 时出现。作用：携带结构化上下文，便于 C1 归一化上报。
- `ContractViolation(HarmonicaError)`：调用方违反契约——Seal 前取数据面、读不存在的端口、写只读缓冲、销毁后使用旧句柄、非法状态调用。**程序缺陷**，不是环境问题，不得被重试逻辑吞掉。
- `CoreBuildError(HarmonicaError)`：C2 构建期失败（码 1–6）。数据面不存在，算法不得启动。
- `AlgorithmError(HarmonicaError)`：C3 运行期失败（码 8）。数据面与其余算法不受影响；v0.1 中算法异常被 C1 捕获后折入 `AlgorithmResultEnvelope(status='FAILED')`，不穿透。
- 边界：三个子类均不新增字段、不改写 `__str__`；一切受控失败必须经此族抛出，裸 `ValueError`/`RuntimeError` 不得跨组件边界传播（`AudioFormat.__post_init__` 的 ValueError 属于构造期编程错误，不跨边界）。

### 4.13 UiScalar / UiSeries / UiView

- `UiScalar`（frozen）：`key: str`；`label: str`（给人看的中文短名）；`value: float`；`unit: str`，取值域 `{'cents', 'ms', 'db', 'ratio', ''}`；`threshold: float | None = None`（None = 纯陈述、无判定）。纪律：只陈述数值与含义，**不下教学结论**（SPEC §3）。
- `UiSeries`（frozen）：`key: str`；`label: str`；`t: Sequence[float]`（时间轴，秒，`field(repr=False)`）；`values: Sequence[float]`（`field(repr=False)`）；不变量 `len(t) == len(values)`；`unit: str`；`timeline_basis: TimelineBasis`（**必填**）。纪律：曲线**必须已下采样**后交付；★ 已裁定：**禁止把不同 timeline_basis 的曲线画在同一张图上**（两条轴的 t 物理含义不同，叠加必然误导，会让抢拍拖拍看起来「对齐了」）；同一 basis 的多条曲线可以叠加。`source_port: str | None = None`（None = 算法直接产出）。
- `UiView`（frozen）：`session_id: str`；`state: SessionState`；`series: Sequence[UiSeries] = ()`；`scalars: Sequence[UiScalar] = ()`；`progress: float | None`（取值域 0.0–1.0 **比例，不是百分数**；`None` = 该会话没有进度概念——尚未开始或已进入终态；`1.0` 与 `state == DATA_READY` 一致；界面不得自行归一化、不得推断百分比）；`port_summary: Sequence[PortDescriptor] = ()`（端口结构只读摘要，**投影 5 字段子集**，见下方专段）；`error_code: str | None = None`；`error_detail: str | None = None`；`note: str = ""`（给开发者的一句话说明）。
- `port_summary` 冻结语义（负责人裁定 2026-09-24，CONTRACT-UI 升 v2 时新增）：
  - **投影 5 字段子集**：`port_id` / `units` / `dimensions` / `shape` / `timeline_basis`。
  - **不投影其余 6 个**：`schema_version` / `element_type` / `field_names` / `hop_length` / `sample_rate` / `content_hash` —— 它们是 **C2 的实现细节**；G14 说的是「不直连 C2」，若经 C1 转手把 11 个字段**全部**投影给 C4，那只是换了个手，**实质仍是 C2 内部结构泄漏**。降信息熵要在这个方向上也成立。
  - `field_names` 尤其不投影：它已由契约层 `FIELD_LAYOUTS` 承载，**那是单一真相源**；再投影一份就是制造第二份，迟早漂移。
  - `()` ＝ **C1 未提供**（尚无数据面或该投影未实现），**不是**「没有端口」的断言；二者不得混为一谈。
  - 由 **C1 在 `snapshot()` 时投影**，C4 只消费；C1 **不得**为补全信息而让 C4 直连 C2（G14）。
- ★★ **有限扩面冻结记录（防止本条被当作可援引的先例）★★
  1. **`port_summary` 是 `UiView` 上的【数据字段】，不是 `UiProjectionPort` 上的【第三个操作】。** §4.15「port 上不得再增第三个操作」**继续有效**，本次未触碰、也不得据此放宽。
  2. 本次扩面的**唯一理由**：C4 没有**合法通道**得知端口结构（直接 import `profile` 即绕过 G14 直连 C2），而该信息对其调试视图**必需**。
  3. ★ **本次是唯一一次**以「补通道缺失」为由对 `UiView` 的扩面。
  4. ★ **后续任何 `UiView` 字段的增删，须重新裁定，不得援引本次先例。** 「上次也是加字段」不是理由。
- `progress` 产生机制（G9，冻结）：**「C1 已完成的正交步骤数 / 总步骤数」**。BUILD_SURFACE 期间 → 0.0 → 1.0 的**单次跳变**（或 None），没有中间值——因为那需要 Core 汇报内部阶段，而内部阶段禁止外泄；RUN_ALGORITHMS 期间 → `k / N`（k = 已完成插件数，N = `Registry.list()` 的当前注册总数，按注册顺序）。这是刻意取舍：平滑进度条需要 Core 开放内部阶段 = 契约从 7 操作变 8 操作，违反封闭契约原则；本轮不做。记入已知缺口：若将来需要平滑进度，正确做法是在 C1 里把构建拆成可观测的多次调用（同样须负责人裁定）。

### 4.14 UiCommandKind / COMMAND_LEGALITY / COMMAND_EFFECTS / UiCommand / UI_PAYLOAD_KEYS

- `UiCommandKind`（Enum，6 值）：`SET_REFERENCE` / `SET_PRACTICE` / `BUILD_SURFACE` / `RUN_ALGORITHMS` / `CANCEL` / `RESET`。刻意保持极小：C4 **不能凭界面发明内核能力**。
- `COMMAND_LEGALITY: Mapping[UiCommandKind, frozenset[SessionState]]`（逐项冻结）：SET_REFERENCE → {CREATED, INPUT_READY}；SET_PRACTICE → {CREATED, INPUT_READY}；BUILD_SURFACE → {INPUT_READY}；RUN_ALGORITHMS → {DATA_READY}；CANCEL → {INPUT_READY, BUILDING, DATA_READY}；RESET → 全部 6 个状态。用途：C1 **必须**用它校验（非法命令 → 拒绝且**不改变状态**）；C4 **可以**用它置灰按钮（纯 UI 优化，**不是**安全边界）；即使 C4 不置灰，C1 也必须校验——界面不是可信输入源。
- `COMMAND_EFFECTS: Mapping[UiCommandKind, str]`（G11，冻结语义，逐条）：SET_REFERENCE = 登记参考演奏路径，成功 → INPUT_READY；SET_PRACTICE = 登记练习演奏路径，成功 → INPUT_READY；BUILD_SURFACE = 开始构建数据面，进入 BUILDING，成功 → DATA_READY；RUN_ALGORITHMS = 运行全部已注册算法，**状态不变**（仍在 DATA_READY）；CANCEL = 中止进行中的操作 → **回到操作前的稳定态**，细化为：INPUT_READY 下无进行中操作，状态不变（幂等）；BUILDING 下**不打断同步构建**，构建完成后按 `CANCEL` 的目标转移生效；DATA_READY 下只中止正在运行的算法、**数据面保持有效**，回 DATA_READY（已 Seal 的数据面不因取消而销毁）。RESET = 销毁数据面、清空已登记输入，回 CREATED（会话对象本身保留，可继续登记新输入）。★ `CANCEL` 只能在 `INPUT_READY` / `DATA_READY` 阶段被即时响应。契约没有取消标志的设置或观察通道，故不存在可执行的端口级检查要求；不得注入后台线程、回调或 checkpoint。★ CANCEL 与 RESET 都**不是错误**：不得产生 ErrorCode，新状态不是 FAILED——用户主动中止 ≠ 系统失败。
- `UiCommand`（frozen）：`kind: UiCommandKind`；`payload: dict = field(default_factory=dict)`。载荷键名冻结（G7，唯一权威即下表）：SET_REFERENCE `{"path": str}`（绝对路径，音频文件）；SET_PRACTICE `{"path": str}`；BUILD_SURFACE `{}`；RUN_ALGORITHMS `{}`；CANCEL `{}`；RESET `{}`。规则：键名不得增删（需要新载荷时改契约并升 CONTRACT-UI-v2 版本）；C1 **必须**校验——未知键、缺必需键、值类型不符 → **拒绝命令**（拒绝而非忽略：忽略会让 C4 以为命令生效了）；非法命令被拒绝且不改变状态，不许「尽力而为」。
- `UI_PAYLOAD_KEYS: Mapping[UiCommandKind, tuple[str, ...]]`（逐项）：SET_REFERENCE → `("path",)`；SET_PRACTICE → `("path",)`；BUILD_SURFACE → `()`；RUN_ALGORITHMS → `()`；CANCEL → `()`；RESET → `()`。教训同 `FIELD_LAYOUTS`：`dict` 类型不携带键名信息，产出方与消费方必须有共同事实来源，否则静默错位。

### 4.15 UiProjectionPort（Protocol，C1 ↔ C4，2 操作）

- `snapshot() -> UiView`：取当前投影快照；**纯读取，无副作用**；返回 §4.13 的完整只读投影。
- `submit(command: UiCommand) -> None`：下发一条用户意图；由 C1 按 `COMMAND_LEGALITY` / `UI_PAYLOAD_KEYS` 校验并执行。
- 纪律：这是 C1 对 C4 的**唯一入口**（与数据面契约同为「接口极小」设计）；C4 只允许依赖 `UiView`，不得反向访问 C1/C2/C3 内部；port 上不得再增第三个操作。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| 构造 `AudioFormat(channels≠1)` | 显式失败（构造期编程错误，属本文件仅有的非契约异常面之一） | `ValueError("契约要求 mono")` |
| 构造 `AudioFormat(dtype≠'float32')` | 显式失败 | `ValueError("契约要求 float32")` |
| `read()` 端口不存在 | 显式失败；绝不返回空视图冒充成功（宪章 §5.6） | `ContractViolation`，`code=ErrorCode.INTERNAL_ERROR` 之外的语义由 detail 携带 `port_id` |
| `read()` 的 `t0 >= t1`，或 `t1` 超出该端口时长，或 `t0/t1` 为 NaN | 显式失败；不得夹取（clamp）到边界 | `ContractViolation` |
| `read()` 时间窗合法但窗内无数据（如 `notes.*` 落在静音段无 onset） | **返回空 BufferView 是正确结果**——「窗内没有音」是真实答案，不是降级（判据：`t1` 在时长内） | 空 `BufferView`（`element_count == 0`） |
| Seal 前调用 `acquire_surface()` | 显式失败；程序缺陷，不得重试 | `ContractViolation` |
| `destroy_session()` 后使用旧 session_id / surface 句柄 | 显式失败 | `ContractViolation` |
| 状态不满足操作前置（如 CREATED 状态 `build_surface`） | 显式失败且状态不变（不许「尽力而为」） | `ContractViolation` |
| 输入不可读 / 无法解码 / 权限拒绝 | 显式失败；状态 → FAILED；数据面不存在；资源全释放 | `CoreBuildError`，`code=ErrorCode.INPUT_UNREADABLE` |
| 任一段短于最小可分析长度 | 显式失败；同上 | `CoreBuildError`，`code=ErrorCode.INPUT_TOO_SHORT` |
| 整段静音 | 显式失败；同上 | `CoreBuildError`，`code=ErrorCode.INPUT_SILENT` |
| 任一段长于 `profile.AUDIO.max_duration_sec`（上限 120 s） | 显式失败；**拒绝，不静默截断** | `CoreBuildError`，`code=ErrorCode.INPUT_TOO_LONG` |
| 标准化 / 对齐 / 预生成任一步失败 | 显式失败；**不得部分发布**，资源全释放，未触发任何算法 | `CoreBuildError`，`code=ErrorCode.CORE_BUILD_FAILED` |
| 无法建立有效时间映射 | 显式失败；**禁止**静默退化为逐点硬比 | `CoreBuildError`，`code=ErrorCode.ALIGNMENT_UNRECOVERABLE` |
| 算法声明数据面没有的端口 | 降级为该算法退出，**其余流程不受影响**（数据面仍有效） | 该算法返回 `AlgorithmResultEnvelope(status='INCOMPATIBLE', error_code='PLUGIN_INCOMPATIBLE')`，不抛异常 |
| 算法运行崩溃 / 产出 NaN / 非法结果 | 降级为该插件失败，**其余流程不受影响**；失败也要返回信封，异常不得穿透到 C1 | `AlgorithmResultEnvelope(status='FAILED', error_code='ALGORITHM_FAILED')`；内部捕获 `AlgorithmError` |
| 算法返回的结果违反自描述契约（payload 元素类型/单位/曲线形状不合法，或 `DEGRADED` 缺少 `coverage` / `warnings` 证据） | 该插件按失败处理；数据面仍有效 | `AlgorithmResultEnvelope(status='FAILED', error_code='ALGORITHM_RESULT_INVALID')` |
| 算法超时 | **v0.1 未实现**（已知缺口：死循环会卡住流程）；任何路径不得产出该码 | 无（`ErrorCode.ALGORITHM_TIMEOUT` 仅为编号占位） |
| 界面（C4）断开 | 什么都不做，会话继续（不变量 F：C4 可缺席）；**不是错误**，不得产生错误码污染失败统计 | 无（`ErrorCode.COCKPIT_DETACHED` 在 v0.1 无产生点） |
| CANCEL / RESET | 用户主动中止 ≠ 系统失败；按 `COMMAND_EFFECTS` 转移状态，不产生 ErrorCode，新状态不是 FAILED | 正常返回 |
| 未分类失败路径 | 兜底码出现即视为**缺陷**上报，不得当正常分支使用 | `HarmonicaError`，`code=ErrorCode.INTERNAL_ERROR` |
| 实现者新增本文件未定义的失败分支 | 触发 §10 上报（新错误码 = 上层设计），不得自行扩展 | —（流程门禁） |

★ 宪章 §5.6：禁止静默降级。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-003-1 | 本文件只含 Enum / dataclass / Protocol / 常量元组；零计算、零 I/O、零第三方算法调用（铭牌 MUST）。按现有数量统计口径（异常基类 `HarmonicaError` 不计入），模块内有 **12 个 dataclass**（包含新增的 `ResolutionView`）；执行体仅限：`AudioFormat.__post_init__` 两处校验、`ResolutionView.is_available` 只读集合查询、`HarmonicaError.__str__` 展示格式化、Enum/Protocol 定义本身 | AST 断言：模块顶层除 class/assignment/`__all__`/imports/docstring 外无语句；无 `open`/`print`/`hashlib`/`os` 引用（§8 脚本 Q1） |
| INV-003-2 | 不 import 本包任何模块（core / host / algorithms / cockpit / profile），也不 import `hashlib` 等计算库；依赖链根（铭牌 MUST NOT） | 断言 `contract.__file__` 所属模块的 import 表 ⊆ {`__future__`, `dataclasses`, `enum`, `typing`, `numpy`, `numpy.typing`}（§8 脚本 Q1） |
| INV-003-3 | 端口描述符能表达 profile.py 的全部字段（铭牌 MUST）：`PortDescriptor` 字段集 ⊇ profile 每个端口声明所需的全部语义（port_id / schema_version / element_type / dimensions / shape / units / field_names / timeline_basis / hop_length / sample_rate / content_hash） | 构造 `FIELD_LAYOUTS` 全部 4 类前缀 × `UNITS_VOCABULARY` 实际使用的 5 个 units 值的 `PortDescriptor` 实例，逐一成功（§8 脚本 Q2） |
| INV-003-4 | `FIELD_LAYOUTS` 封闭且顺序冻结：恰 4 键 `warp_path`/`pitch`/`notes`/`chroma`，值分别等于 `("reference_frame","practice_frame")` / `("f0_hz","voiced","confidence")` / `("onset_sec","f0_hz","rms")` / 12 音级 `("C","C#","D","D#","E","F","F#","G","G#","A","A#","B")`，bin 0 = C | 断言 `dict(FIELD_LAYOUTS) == 冻结字典` 且每值为 tuple（§8 脚本 Q2） |
| INV-003-5 | `UNITS_VOCABULARY` 封闭：恰 10 个元素 {amplitude, chroma, hz, index, rms, cents, db, seconds, ratio, count}；`CORE_REQUIRED_PORTS` 恰 2 项（pcm.mapped.reference / pcm.mapped.practice）；`FORBIDDEN_OPERATIONS` 恰 10 项且含 `align`/`fft`/`register_algorithm` | 断言三个常量与其冻结字面量相等（§8 脚本 Q2） |
| INV-003-6 | `SessionState` 恰 6 值；`status()` 契约只允许返回这 6 值之一，C2 内部阶段不得外泄 | 断言 `len(SessionState) == 6` 且成员名集合 == {CREATED, INPUT_READY, BUILDING, DATA_READY, FAILED, CLOSED}（§8 脚本 Q2） |
| INV-003-7 | `TimelineBasis` 恰 2 值，语义冻结为「哪条时间网格」：REFERENCE=源时间网格（保留源时间、未被时间归一化），WARPED=归一化网格；REFERENCE **不**蕴含两侧帧号一一对应，两段独立录音帧数默认不等，「逐帧相减」无定义，必须按音配对 | 断言成员集合 == {REFERENCE, WARPED}；文本断言本文件 §4.2 含「逐帧相减」无定义与按音配对表述（§8 脚本 Q3） |
| INV-003-8 | `AlgorithmDataContract` 恰 2 个操作（`manifest` / `read`；**操作数不含 `resolution` 属性**），另有 1 个只读状态属性 `resolution`；`read` 无副作用、单位为秒、绝不以空视图冒充成功（时间窗非法时抛 `ContractViolation`；窗内确无数据且 `t1` 在时长内时空视图合法）；`resolution` 返回 `ResolutionView`，供插件查询可用性并读取 `missing_optional` | Protocol 成员断言：公开成员恰为 `{"manifest", "read", "resolution"}`；操作成员恰为 `{"manifest", "read"}`，且 `vars(AlgorithmDataContract)["resolution"]` 为 `property`；`ResolutionView` 字段与 `is_available` 由 Q2 断言；read 失败语义由实现侧（FILE-005/006）测试复验（§8 脚本 Q2） |
| INV-003-9 | `HostContract` 恰 7 个操作，不多不少：create_session / set_reference / set_practice / build_surface / status / acquire_surface / destroy_session；且 `FORBIDDEN_OPERATIONS` 的 10 个名字不得出现在任何 C2 实现的公开方法名中 | Protocol 成员断言 == 冻结集合；Inspector General 断言 `FORBIDDEN_OPERATIONS ∩ dir(core实现) == ∅`（§8 脚本 Q2） |
| INV-003-10 | `AlgorithmResultEnvelope.status` 取值域封闭 {'OK','DEGRADED','INCOMPATIBLE','FAILED'}；`payload` 是 `Sequence[UiScalar | UiSeries]`；`DEGRADED` 必须有 `coverage` 或 `warnings` 证据；失败/不兼容也必须返回信封，异常不得穿透到 C1 | Q2 断言 dataclass 字段、payload 注解、四值集合与各状态构造行为；Q3 断言本文件 §4.8 明文列出四值及其证据纪律（§8 脚本 Q2/Q3） |
| INV-003-11 | `ErrorCode` 恰 12 值，名称与 `.value` 一一相同；各码触发条件以 §4.11 为唯一事实来源 | 断言 `len(ErrorCode) == 12` 且 `{m.name: m.value}` 为恒等映射（§8 脚本 Q2） |
| INV-003-12 | `COMMAND_LEGALITY` / `COMMAND_EFFECTS` / `UI_PAYLOAD_KEYS` 键集 == `UiCommandKind` 全部 6 成员；SET_REFERENCE/SET_PRACTICE 载荷恰为 `("path",)`，其余 4 个为空元组；非法命令必须被拒绝且不改变状态 | 断言三个映射的键集与值（§8 脚本 Q2） |
| INV-003-13 | `UiSeries.timeline_basis` 必填且禁止不同 basis 曲线同图；`UiView.progress` 取值域 0.0–1.0 或 None，1.0 与 DATA_READY 一致 | 类型断言（timeline_basis 无默认值即强制）；实现侧 C4 投影测试复验同图禁令（§8 脚本 Q2） |
| INV-003-14 | 受控失败全部经 HarmonicaError 族（ContractViolation / CoreBuildError / AlgorithmError）抛出，裸异常不得跨组件边界传播 | 实现侧集成测试逐组件断言异常类型 ⊆ HarmonicaError 族；本文件级：断言三者 issubclass 于 HarmonicaError（§8 脚本 Q2） |
| INV-003-15 | `__all__` 与文件实际公开符号一致（列出的每个名字在模块命名空间存在） | 断言 `all(hasattr(contract, n) for n in contract.__all__)`（§8 脚本 Q1） |
| INV-003-16 | ★ C3 插件契约完整暴露：`algorithms.__all__ == ["InputRequirement", "PluginSpec", "Registry"]`；算法包不 import 任何具体实现 `.pitch` / `.timing` / `.dynamics`，也不重新暴露任何已删除的算法清单/字段映射/旧注册自检符号 | Q1 增补可执行断言：从 `algorithms/__init__.py` AST 解析 import 与顶层定义，逐项核对（§8 脚本 Q1） |

---

## 7 · 边界（明确不做）

本文件只冻结词汇与结构，不承担任何行为。以下每一条都是**本文件专属的越界行为**：实现者在 `harmonica_eval/contract.py` 里写出其中任何一条，即违反铭牌 MUST / MUST NOT 与宪章 §5.9，必须停止并上报，不得自行保留。

- **不做任何计算**：不实现 `content_hash` 的 sha256 计算（`hashlib` 的调用点在 C2 的 Seal 阶段）、不做秒↔帧换算、不做下采样、不做归一化、不做任何 numpy 运算；`numpy` 在本文件中只作为类型注解出现（`npt.NDArray[Any]`）。
- **不做 I/O**：不读音频文件、不探测路径是否存在、不打开或关闭句柄、不打印、不写日志、不读写配置。`set_reference(session_id, uri)` 只登记字符串，解码与校验发生在 C2 的 `build_surface`。
- **不做校验逻辑**：不提供 `assert_profile_integrity()`、不检查 `units ∈ UNITS_VOCABULARY`、不检查 `field_names` 与 `FIELD_LAYOUTS[类别前缀]` 相等、不检查 `shape` 与 `element_count` 自洽。这些检查的宿主分别是 `profile.assert_profile_integrity()` 与 C2 的读取实现；本文件只提供被检查的字面量。
- **不定义端口清单**：不写 `pcm.mapped.reference`、`pcm.mapped.practice` 之外的端口常量，不在本文件出现 profile 端口表，不给 `hop_length` 设默认业务值（`0` 只表示「本端口不是等间隔栅格」，不表示「回退到 `profile.ALIGN.hop_length`」）。
- **不定义阈值与数值**：最小可分析长度、静音门限、`max_duration_sec = 120`、`ALIGN.hop_length = 2048`、`MATERIALIZE.rms_hop_length = 256` 一律不写进本文件；本文件只以文字引用它们（如 `INPUT_TOO_LONG` 的触发条件引用 `profile.AUDIO.max_duration_sec`）。把数字抄进本文件「方便引用」同样是越界。
- **不定义 C2 内部阶段**：`INGESTING`、`ALIGNING`、`BUILDING_PORTS` 这类内部阶段名不得成为本文件的 Enum 成员、常量或 Protocol 操作名。
- **不承诺两侧帧号一一对应**：`TimelineBasis.REFERENCE` 只表示「保留源时间、未被时间归一化」，**不**表示参考侧与练习侧的第 n 帧是同一物理时刻。两段是独立录音，采样点数与帧数默认不相等，故「逐帧相减」无定义。逐帧差的唯一合法前提是两侧端口同网格、同 `shape`、同 `hop_length`（例如标准化后的 `pcm.mapped.reference` 与 `pcm.mapped.practice`）；跨网格比较必须**按音配对**（经 `warp_path` 或 `notes.*` 的 onset 对齐）。本文件不提供任何帧号映射表。
- **不实现 Protocol**：`HostContract`（7 操作）、`AlgorithmDataContract`（2 个纯查表操作 + 1 个只读状态属性 `resolution`）、`UiProjectionPort`（2 操作）在本文件中只有声明体 `...`；实现分别属于 COMP-C2 与 COMP-C1。本文件不提供默认实现、mixin、基类或适配器。
- **不新增端口、不新增操作、不新增错误码**：`HostContract` 恒为 7 操作（第 8 个操作即破坏封闭契约原则，进度查询已被负责人裁定不做）、`ErrorCode` 恒为 12 值、`UiCommandKind` 恒为 6 值、`FIELD_LAYOUTS` 恒为 4 键。需要变更时改契约版本，不改本文件。
- **不给编号占位码补产生点**：`ALGORITHM_TIMEOUT` 在 v0.1 无实现、`COCKPIT_DETACHED` 在 v0.1 无上报通道。本文件不得为它们加事件通道，不得在 `UiProjectionPort` 上加第三个操作。
- **不定义算法侧内容**：不定义算法 ID 列表、算法 registry、算法 payload 的具体键名与数值口径、算法超时秒数。`AlgorithmResultEnvelope.payload` 只冻结自描述形状 `Sequence[UiScalar | UiSeries]`；字段名的唯一权威是插件产出对象的 `key` 字段，插件通过 `PluginSpec` 向显式 `Registry` 声明输入需求。
- **不定义 UI 侧内容**：不定义布局、颜色、坐标范围、下采样率、进度条中间值。`UiSeries` 只声明「必须已下采样」与「同一张图不得混用两条 `timeline_basis`」，点数由 C3/C4 决定；`UiView.progress` 在 BUILD_SURFACE 期间没有中间值（§4.13 G9）。
- **不定义重试与恢复策略**：不提供重试次数、退避、降级开关。`ContractViolation`（程序缺陷）与 `CoreBuildError`（构建失败）都不在本文件里被捕获或转换成别的类型。
- **不做便利函数与默认业务值**：不写 `units_of(port)`、`is_rhythm_port(port)`、`SESSION_DEFAULT` 这类名字；铭牌 MUST NOT 明文禁止「便利函数」与「默认业务值」。
- **不 import 本包任何模块**：包括 `profile.py`。本文件是依赖链的根，`profile` 反向 import 本文件；反向 import 会形成环，并让端口语义的唯一定义处变成两个。

---

## 8 · 怎么验证你写对了

前置条件（三条，缺一即命令不可运行）：① 工作目录为 `/Users/Apple/Desktop/dsh-archive/harmonica-eval`；② `harmonica_eval/contract.py` 已落盘；③ `numpy` 可 `import`（本文件顶层 `import numpy`）。三段脚本按文件路径加载被测模块（`importlib.util.spec_from_file_location`），**不**触发 `harmonica_eval/__init__.py`，因此验证结果只反映 `contract.py` 本身，不会因包内其他模块的状态而假失败。三段必须**全部退出码 0**。

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
set -euo pipefail
PYTHON="${PYTHON:-python3}"
mkdir -p data/out
: > data/out/FILE-003-verify.txt

# ── Q1 · AST 静态断言：零计算 / 零 I/O / 零本包 import / 执行体仅两处 / __all__ 自洽 ──
"$PYTHON" - <<'PY' 2>&1 | tee data/out/FILE-003-q1.txt | tee -a data/out/FILE-003-verify.txt
import ast, importlib.util, pathlib, sys

SRC = pathlib.Path("harmonica_eval/contract.py")
src = SRC.read_text(encoding="utf-8")
tree = ast.parse(src)

# INV-003-2：import 表 ⊆ 封闭清单，且不得使用相对 import
# ★ 2026-09-24 更正（⑳ 执行确认）：封闭清单漏了 `types`（标准库）
#   contract.py:50 `from types import MappingProxyType` —— 标准库，不是本包依赖
#   ★ 漏列会让「零本包 import」这条不变量被标准库误报，属判据缺陷而非实现违规
ALLOWED_IMPORTS = {"__future__", "dataclasses", "enum", "typing", "types", "numpy", "numpy.typing"}
mods = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        mods.update(a.name for a in node.names)
    elif isinstance(node, ast.ImportFrom):
        assert node.level == 0, f"MUST NOT 相对 import @line {node.lineno}"
        mods.add(node.module)
assert mods <= ALLOWED_IMPORTS, f"越界 import: {sorted(mods - ALLOWED_IMPORTS)}"

# INV-003-1：模块顶层只有 import / class / 常量赋值 / docstring / 冻结的只读查询
# ★ 2026-09-25 修正（★ 规格冲突，★ 不是阶段态过期）：
#   本断言原先不含 ast.FunctionDef，于是 hop_of 一出现就红
#   （实测 AssertionError: 顶层非法语句 FunctionDef @line 845）。
# ★ ★ 冲突双方（★ 两份规格原本互相矛盾，★ 这里写明依据）：
#     · INV-003-1 说「本文件只含 Enum / dataclass / Protocol / 常量元组」
#     · FILE-201-v1.md:137 明文要求「现契约层新增只读查询 hop_of(port_id)」，
#       并让算法侧写 `from ..contract import hop_of`
# ★ ★ 裁定：hop_of 是【规格明确要求的】唯一模块级函数 ——
#   理由是 hop 的权威源在 C2（profile），而算法侧判据 G 的 import 面
#   冻结不含 profile；契约层提供只读转供，是为了让 hop 只有【一份真相源】，
#   而不是让每个算法各抄一份（★ 那正是本项目要消灭的熵）。
# ★ ★ 因此：不删 hop_of，不改 INV-003-1 的意图，
#   只把「模块级函数」纳入允许集合，★ 且【收窄为仅这一个】——
#   新增第二个模块级函数仍会红。
# ★ 历史留档（★ 不是判据）：修复前 contract.py 顶层零函数，断言不含 FunctionDef。
TOP_OK = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Assign, ast.AnnAssign, ast.Expr, ast.FunctionDef)
# ★ 允许的模块级函数【精确名单】—— ★ 不是「所有函数都行」
ALLOWED_TOP_FUNCS = frozenset({"hop_of"})
_defined_funcs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
assert _defined_funcs <= ALLOWED_TOP_FUNCS, (
    f"模块级函数超出允许名单 {sorted(ALLOWED_TOP_FUNCS)}：{sorted(_defined_funcs - ALLOWED_TOP_FUNCS)}")
for node in tree.body:
    assert isinstance(node, TOP_OK), f"顶层非法语句 {type(node).__name__} @line {node.lineno}"
    if isinstance(node, ast.Expr):
        assert isinstance(node.value, ast.Constant) and isinstance(node.value.value, str), \
            f"顶层表达式只允许 docstring @line {node.lineno}"

# INV-003-1：模块内恰 12 个普通 dataclass（HarmonicaError 基类另计，故含基类为 13）
DCD_NAMES = tuple(
    n.name for n in tree.body
    if isinstance(n, ast.ClassDef)
    and any(
        (isinstance(d, ast.Name) and d.id == "dataclass")
        or (isinstance(d, ast.Attribute) and d.attr == "dataclass")
        or (isinstance(d, ast.Call) and (
            (isinstance(d.func, ast.Name) and d.func.id == "dataclass")
            or (isinstance(d.func, ast.Attribute) and d.func.attr == "dataclass")
        ))
        for d in n.decorator_list
    )
)
# `from dataclasses import dataclass` 后的装饰器是 ast.Name；上面的静态结构也覆盖
# `dataclasses.dataclass(...)` 等等价写法。HarmonicaError 是异常基类，按项目统计口径另列。
assert len(DCD_NAMES) == 13, DCD_NAMES
assert DCD_NAMES.count("HarmonicaError") == 1, DCD_NAMES
assert len(set(DCD_NAMES) - {"HarmonicaError"}) == 12, DCD_NAMES
assert "ResolutionView" in DCD_NAMES, DCD_NAMES

# INV-003-1：类体只含方法声明 / 赋值 / 注解 / docstring
CLASS_OK = (ast.FunctionDef, ast.Assign, ast.AnnAssign, ast.Expr, ast.ClassDef)
for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
    for node in cls.body:
        assert isinstance(node, CLASS_OK), f"{cls.name} 体内非法语句 {type(node).__name__} @line {node.lineno}"

# INV-003-1：唯一允许有实体的方法：AudioFormat 两处校验、ResolutionView 集合查询、HarmonicaError 展示格式化
EXEC_BODIES = {"AudioFormat.__post_init__", "ResolutionView.is_available", "HarmonicaError.__str__"}
seen = set()
for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
    for fn in (n for n in cls.body if isinstance(n, ast.FunctionDef)):
        q = f"{cls.name}.{fn.name}"
        seen.add(q)
        if q in EXEC_BODIES:
            assert not (len(fn.body) == 1 and isinstance(fn.body[0], ast.Expr)), f"{q} 不应为空声明体"
            continue
        ok = (len(fn.body) == 1 and isinstance(fn.body[0], ast.Expr)
              and isinstance(fn.body[0].value, ast.Constant) and fn.body[0].value.value is Ellipsis)
        if not ok:
            # 允许最后一个语句为 `...`；其前只能是 docstring，不允许实际计算。
            assert fn.body and isinstance(fn.body[-1], ast.Expr) \
                and isinstance(fn.body[-1].value, ast.Constant) \
                and fn.body[-1].value.value is Ellipsis, \
                f"{q} 的声明体必须以 `...` 结尾且不得含实际计算"
            for stmt in fn.body[:-1]:
                assert isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) \
                    and isinstance(stmt.value.value, str), f"{q} 的非末语句只能是 docstring"
assert EXEC_BODIES <= seen, f"缺少执行体: {sorted(EXEC_BODIES - seen)}"
assert len(seen) == 15, f"方法数应为 15（AlgorithmDataContract 2 操作+1 属性、HostContract 7 操作、UiProjectionPort 2 操作、ResolutionView 1 查询、HarmonicaError 1 展示、AudioFormat 1 校验），实际 {len(seen)}: {sorted(seen)}"

# INV-003-1：真实代码中不得出现计算 / I/O 名字（AST 节点级，docstring 内的算法描述不算）
FORBIDDEN_NAMES = {"open", "print", "input", "eval", "exec", "compile", "__import__",
                   "hashlib", "os", "sys", "pathlib", "io", "json", "logging",
                   "math", "random", "scipy", "librosa", "soundfile", "pydantic", "attrs"}
names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
assert not (names & FORBIDDEN_NAMES), f"出现越界名字: {sorted(names & FORBIDDEN_NAMES)}"
FORBIDDEN_ATTRS = {"sha256", "hexdigest", "update", "system", "popen", "exists",
                   "tobytes", "asarray", "read_text", "write_text", "open"}
attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
assert not (attrs & FORBIDDEN_ATTRS), f"出现越界属性访问: {sorted(attrs & FORBIDDEN_ATTRS)}"

# INV-003-15：__all__ 列出的每个名字都在模块命名空间存在，且无重复
spec = importlib.util.spec_from_file_location("contract_under_test", SRC)
c = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = c
spec.loader.exec_module(c)
assert len(c.__all__) == len(set(c.__all__)), "__all__ 存在重复项"
# ★ 2026-09-25：32 → 34。增的两项是 hop_of 与 PORT_HOP_LENGTHS。
#   依据：FILE-201-v1.md:137 明文要求契约层提供只读查询 hop_of(port_id)，
#   让算法侧「用 contract.hop_of 而非 import profile」（该文件 §8 有断言
#   'hop_of' in src）。两项都是为让 hop 只有【一份真相源】而设 ——
#   否则每个算法各抄一份 hop，那正是本项目要消灭的熵。
# ★ 判断依据是「每一个名字都要能说出它为什么在公开面上」，不是「凑够个数」。
assert len(c.__all__) == 34, f"__all__ 应为 34 项，实际 {len(c.__all__)}"
# ★ C3 插件化：算法包只做稳定类型出口，框架不得重新硬绑具体算法
ALGO = pathlib.Path("harmonica_eval/algorithms/__init__.py")
algo_tree = ast.parse(ALGO.read_text(encoding="utf-8"))
assert isinstance(next(n.value for n in algo_tree.body
                        if isinstance(n, ast.AnnAssign)
                        and isinstance(n.target, ast.Name) and n.target.id == "__all__"),
                  ast.List)
assert ast.literal_eval(next(n.value for n in algo_tree.body
                              if isinstance(n, ast.AnnAssign)
                              and isinstance(n.target, ast.Name) and n.target.id == "__all__")) == [
                                  "InputRequirement", "PluginSpec", "Registry"]
for node in ast.walk(algo_tree):
    if isinstance(node, ast.ImportFrom):
        assert (node.module or "") not in {".pitch", ".timing", ".dynamics"}, ast.unparse(node)
    if isinstance(node, ast.Import):
        assert all(a.name not in {"harmonica_eval.algorithms.pitch",
                                  "harmonica_eval.algorithms.timing",
                                  "harmonica_eval.algorithms.dynamics"} for a in node.names)
public_names = {n.id for n in algo_tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
public_names |= {n.target.id for n in algo_tree.body if isinstance(n, ast.AnnAssign)
                 and isinstance(n.target, ast.Name) and not n.target.id.startswith("_")}
public_names |= {t.id for n in algo_tree.body if isinstance(n, ast.Assign)
                 for t in n.targets if isinstance(t, ast.Name) and not t.id.startswith("_")}
assert not (set(public_names) & {"ALGORITHMS", "PAYLOAD_SCHEMAS", "assert_registry_integrity"})
# docstring 中记录了「已删除」的历史说明，不属于现行导出面。
assert not ({"ALGORITHMS", "PAYLOAD_SCHEMAS", "assert_registry_integrity"} & set(c.__all__))
missing = [n for n in c.__all__ if not hasattr(c, n)]
assert not missing, f"__all__ 列了不存在的名字: {missing}"
for required in ("SessionState", "TimelineBasis", "AlignmentRepresentation", "AudioFormat",
                 "FIELD_LAYOUTS", "CONTENT_HASH_MAGIC", "UNITS_VOCABULARY", "PortDescriptor",
                 "BufferView", "SurfaceManifest", "ResolutionView", "AlgorithmResultEnvelope",
                 "InputRequirement", "PluginSpec",
                 "AlgorithmDataContract", "CORE_REQUIRED_PORTS", "HostContract",
                 "FORBIDDEN_OPERATIONS", "ErrorCode", "HarmonicaError", "ContractViolation",
                 "CoreBuildError", "AlgorithmError", "UiScalar", "UiSeries", "UiView",
                 "UiCommandKind", "UiCommand", "COMMAND_LEGALITY", "COMMAND_EFFECTS",
                 "UI_PAYLOAD_KEYS", "UiProjectionPort"):
    assert required in c.__all__, f"__all__ 缺少 {required}"
print("imports =", sorted(mods))
print("__all__ len =", len(c.__all__))
print("Q1 OK")
PY

# ── Q2 · 运行期常量 / 枚举 / Protocol / dataclass 断言 ──
"$PYTHON" - <<'PY' 2>&1 | tee data/out/FILE-003-q2.txt | tee -a data/out/FILE-003-verify.txt
import dataclasses, importlib.util, inspect, pathlib, sys

spec = importlib.util.spec_from_file_location("contract_under_test", pathlib.Path("harmonica_eval/contract.py"))
c = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = c
spec.loader.exec_module(c)

# INV-003-4：FIELD_LAYOUTS 恰 4 键、值为 tuple、chroma bin 0 = C
assert dict(c.FIELD_LAYOUTS) == {
    "warp_path": ("reference_frame", "practice_frame"),
    "pitch": ("f0_hz", "voiced", "confidence"),
    "notes": ("onset_sec", "f0_hz", "rms"),
    "chroma": ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"),
}
assert len(c.FIELD_LAYOUTS) == 4
assert all(isinstance(v, tuple) for v in c.FIELD_LAYOUTS.values())
assert len(c.FIELD_LAYOUTS["chroma"]) == 12 and c.FIELD_LAYOUTS["chroma"][0] == "C"

# INV-003-5：三个常量与其冻结字面量相等
assert c.UNITS_VOCABULARY == frozenset(
    {"amplitude", "chroma", "hz", "index", "rms", "cents", "seconds", "db", "ratio", "count"})
assert len(c.UNITS_VOCABULARY) == 10
assert c.CORE_REQUIRED_PORTS == ("pcm.mapped.reference", "pcm.mapped.practice")
assert c.FORBIDDEN_OPERATIONS == (
    "align", "fft", "stft", "compute_feature", "generate_pitch_input",
    "generate_plugin_requirement", "prepare_for_pitch", "prepare_for_timing",
    "register_algorithm", "list_algorithms")
assert len(c.FORBIDDEN_OPERATIONS) == 10
assert {"align", "fft", "register_algorithm"} <= set(c.FORBIDDEN_OPERATIONS)
assert c.CONTENT_HASH_MAGIC == b"harmonica-eval/surface/v1\x00"

# INV-003-6 / INV-003-7：会话状态恰 6 值；时间基准恰 2 值
assert len(c.SessionState) == 6
assert {m.name for m in c.SessionState} == {
    "CREATED", "INPUT_READY", "BUILDING", "DATA_READY", "FAILED", "CLOSED"}
assert all(m.value == m.name for m in c.SessionState)
assert set(c.TimelineBasis.__members__) == {"REFERENCE", "WARPED"} and len(c.TimelineBasis) == 2
assert set(c.AlignmentRepresentation.__members__) == {"MAPPED", "WARPED"}

# INV-003-8 / INV-003-9：Protocol 操作数不多不少；只读状态属性不计操作
def public_names(cls):
    return {n for n in vars(cls) if not n.startswith("_")}


def operations(cls):
    return {
        n for n in public_names(cls)
        if not isinstance(vars(cls)[n], property)
    }


assert public_names(c.AlgorithmDataContract) == {"manifest", "resolution", "read"}
assert operations(c.AlgorithmDataContract) == {"manifest", "read"}
assert isinstance(vars(c.AlgorithmDataContract)["resolution"], property)
assert operations(c.HostContract) == {"create_session", "set_reference", "set_practice",
                                      "build_surface", "status", "acquire_surface", "destroy_session"}
assert operations(c.UiProjectionPort) == {"snapshot", "submit"}
assert list(inspect.signature(c.HostContract.create_session).parameters) == ["self", "profile_version"]
assert list(inspect.signature(c.HostContract.set_reference).parameters) == ["self", "session_id", "uri"]
assert list(inspect.signature(c.HostContract.set_practice).parameters) == ["self", "session_id", "uri"]
assert list(inspect.signature(c.HostContract.build_surface).parameters) == ["self", "session_id"]
assert list(inspect.signature(c.AlgorithmDataContract.read).parameters) == ["self", "port_id", "time_range"]

# INV-003-3：4 个类别前缀 × 实际使用的 5 个 units 值，PortDescriptor 全部可构造
USED_UNITS = ("amplitude", "chroma", "hz", "index", "rms")
DIMS = {"amplitude": ("sample",), "chroma": ("frame", "field"), "hz": ("frame", "field"),
        "index": ("warp_point", "axis"), "rms": ("frame",)}
for prefix, fields in c.FIELD_LAYOUTS.items():
    for u in USED_UNITS:
        dims = DIMS[u]
        d = c.PortDescriptor(
            port_id=f"{prefix}.q2", schema_version="v1", element_type="float32",
            dimensions=dims,
            shape=(8, len(fields)) if len(dims) > 1 else (8,),
            units=u, field_names=fields,
            timeline_basis=c.TimelineBasis.REFERENCE, hop_length=2048, sample_rate=44100)
        assert c.FIELD_LAYOUTS[d.port_id.split(".", 1)[0]] == tuple(d.field_names)

# INV-003-11：ErrorCode 恰 12 值，name 与 value 一一相同
assert len(c.ErrorCode) == 12
assert all(m.value == m.name for m in c.ErrorCode)
assert {m.name for m in c.ErrorCode} == {
    "INPUT_UNREADABLE", "INPUT_TOO_SHORT", "INPUT_SILENT", "INPUT_TOO_LONG",
    "CORE_BUILD_FAILED", "ALIGNMENT_UNRECOVERABLE", "PLUGIN_INCOMPATIBLE",
    "ALGORITHM_FAILED", "ALGORITHM_RESULT_INVALID", "ALGORITHM_TIMEOUT",
    "COCKPIT_DETACHED", "INTERNAL_ERROR"}

# INV-003-12：三个映射的键集 == UiCommandKind 全部 6 成员；载荷键逐项冻结
kinds = set(c.UiCommandKind)
assert len(kinds) == 6
for m in (c.COMMAND_LEGALITY, c.COMMAND_EFFECTS, c.UI_PAYLOAD_KEYS):
    assert set(m) == kinds, f"键集与 UiCommandKind 不符: {sorted(kinds - set(m))}"
assert c.UI_PAYLOAD_KEYS[c.UiCommandKind.SET_REFERENCE] == ("path",)
assert c.UI_PAYLOAD_KEYS[c.UiCommandKind.SET_PRACTICE] == ("path",)
for k in (c.UiCommandKind.BUILD_SURFACE, c.UiCommandKind.RUN_ALGORITHMS,
          c.UiCommandKind.CANCEL, c.UiCommandKind.RESET):
    assert c.UI_PAYLOAD_KEYS[k] == ()
assert c.COMMAND_LEGALITY[c.UiCommandKind.SET_REFERENCE] == frozenset({c.SessionState.CREATED, c.SessionState.INPUT_READY})
assert c.COMMAND_LEGALITY[c.UiCommandKind.BUILD_SURFACE] == frozenset({c.SessionState.INPUT_READY})
assert c.COMMAND_LEGALITY[c.UiCommandKind.RUN_ALGORITHMS] == frozenset({c.SessionState.DATA_READY})
assert c.COMMAND_LEGALITY[c.UiCommandKind.CANCEL] == frozenset(
    {c.SessionState.INPUT_READY, c.SessionState.BUILDING, c.SessionState.DATA_READY})
assert c.COMMAND_LEGALITY[c.UiCommandKind.RESET] == frozenset(set(c.SessionState))

# INV-003-14：三个异常类都派生自 HarmonicaError
assert issubclass(c.HarmonicaError, Exception)
for cls in (c.ContractViolation, c.CoreBuildError, c.AlgorithmError):
    assert issubclass(cls, c.HarmonicaError), cls.__name__

# INV-003-1 的执行体：AudioFormat 两处校验 + HarmonicaError.__str__ 展示格式
assert c.AudioFormat(sample_rate=44100, channels=1, dtype="float32").sample_rate == 44100
for channels, dtype, msg in ((2, "float32", "契约要求 mono"), (1, "float64", "契约要求 float32")):
    try:
        c.AudioFormat(sample_rate=44100, channels=channels, dtype=dtype)
    except ValueError as exc:
        assert str(exc) == msg, (str(exc), msg)
    else:
        raise AssertionError("AudioFormat 未拒绝非法构造")
err = c.ContractViolation(code=c.ErrorCode.INTERNAL_ERROR, component="C2", session_id="s1", port_id="p1")
assert str(err) == "[INTERNAL_ERROR] (C2) no detail session=s1 port=p1", str(err)

# INV-003-10 / INV-003-13：插件契约、信封与投影对象的字段与必填语义
assert len(inspect.signature(c.InputRequirement).parameters) == 6
assert list(inspect.signature(c.InputRequirement).parameters) == [
    "port_id", "schema_version", "timeline_basis", "element_type", "required_fields", "sample_rate"]
assert [n for n, p in inspect.signature(c.InputRequirement).parameters.items() if p.default is inspect.Parameter.empty] == ["port_id"]
assert len(inspect.signature(c.PluginSpec).parameters) == 6
assert list(inspect.signature(c.PluginSpec).parameters) == [
    "algorithm_id", "algorithm_version", "label", "required_inputs", "optional_inputs", "entry"]

assert len(inspect.signature(c.AlgorithmResultEnvelope).parameters) == 11
assert list(inspect.signature(c.AlgorithmResultEnvelope).parameters) == [
    "algorithm_id", "algorithm_version", "status", "required_ports", "consumed_ports",
    "payload", "error_code", "error_detail", "elapsed_sec", "coverage", "warnings"]
payload_annotation = inspect.signature(c.AlgorithmResultEnvelope).parameters["payload"].annotation
assert str(payload_annotation) == "Sequence[UiScalar | UiSeries]", payload_annotation
STATUS_DOMAIN = {"OK", "DEGRADED", "INCOMPATIBLE", "FAILED"}
STATUS_KWARGS = {
    "OK": {"coverage": 1.0},
    "DEGRADED": {"coverage": 0.5, "warnings": ("可选输入缺失",)},
    "INCOMPATIBLE": {"error_code": c.ErrorCode.PLUGIN_INCOMPATIBLE.value},
    "FAILED": {"error_code": c.ErrorCode.ALGORITHM_FAILED.value, "error_detail": "boom"},
}
common = dict(algorithm_id="demo", algorithm_version="1", required_ports=(), consumed_ports=())
constructed = set()
for status in STATUS_DOMAIN:
    result = c.AlgorithmResultEnvelope(
        status=status, payload=(), **common, **STATUS_KWARGS[status])
    assert result.status == status
    constructed.add(result.status)
assert constructed == STATUS_DOMAIN
scalar = c.UiScalar(key="median_abs_cents", label="中位绝对偏差", value=1.0, unit="cents")
series = c.UiSeries(key="per_note_cents", label="逐音偏差", t=(0.0, 0.5),
                    values=(1.0, -2.0), unit="cents", timeline_basis=c.TimelineBasis.REFERENCE)
env = c.AlgorithmResultEnvelope(
    status="FAILED", payload=(scalar, series), error_code=c.ErrorCode.ALGORITHM_FAILED.value,
    error_detail="boom", **common)
assert env.status == "FAILED" and env.error_code == "ALGORITHM_FAILED"
ok = c.AlgorithmResultEnvelope(status="OK", payload=(scalar,), coverage=1.0, **common)
degraded = c.AlgorithmResultEnvelope(status="DEGRADED", payload=(scalar,), warnings=("可选输入缺失",), **common)
assert ok.error_code is None and degraded.error_code is None
try:
    c.UiSeries(key="k", label="l", t=(0.0,), values=(1.0,), unit="cents")
except TypeError:
    pass
else:
    raise AssertionError("UiSeries.timeline_basis 有默认值，必填语义被破坏")
assert c.UiView(session_id="s", state=c.SessionState.DATA_READY, progress=1.0).progress == 1.0
assert c.UiView(session_id="s", state=c.SessionState.CREATED, progress=None).progress is None

# 全部 frozen dataclass 均不可变
for name in ("AudioFormat", "PortDescriptor", "BufferView", "SurfaceManifest", "ResolutionView",
             "AlgorithmResultEnvelope", "InputRequirement", "PluginSpec",
             "UiScalar", "UiSeries", "UiView", "UiCommand"):
    assert getattr(c, name).__dataclass_params__.frozen is True, f"{name} 不是 frozen"
view = c.ResolutionView(available=frozenset({"pcm.mapped.reference"}),
                        missing_optional=frozenset({"notes.reference"}))
assert view.is_available("pcm.mapped.reference") is True
assert view.is_available("notes.reference") is False
assert view.is_available("unknown") is False
try:
    view.available = frozenset()
except dataclasses.FrozenInstanceError:
    pass
else:
    raise AssertionError("ResolutionView 可变，frozen 语义被破坏")
pd = c.PortDescriptor(port_id="pitch.lowres", schema_version="v1", element_type="float32",
                      dimensions=("frame", "field"), shape=(4, 3), units="hz",
                      field_names=c.FIELD_LAYOUTS["pitch"],
                      timeline_basis=c.TimelineBasis.REFERENCE,
                      hop_length=2048, sample_rate=44100)
try:
    pd.units = "rms"
except dataclasses.FrozenInstanceError:
    pass
else:
    raise AssertionError("PortDescriptor 可变，frozen 语义被破坏")

# §9 要求提交的实测数字，逐行打印（全部来自上面的真实对象，不是抄写）
print("counts =", {"SessionState": len(c.SessionState), "TimelineBasis": len(c.TimelineBasis),
                   "AlignmentRepresentation": len(c.AlignmentRepresentation),
                   "ErrorCode": len(c.ErrorCode), "UiCommandKind": len(c.UiCommandKind),
                   "FIELD_LAYOUTS": len(c.FIELD_LAYOUTS), "UNITS_VOCABULARY": len(c.UNITS_VOCABULARY),
                   "CORE_REQUIRED_PORTS": len(c.CORE_REQUIRED_PORTS),
                   "FORBIDDEN_OPERATIONS": len(c.FORBIDDEN_OPERATIONS),
                   "HostContract": len(operations(c.HostContract)),
                   "AlgorithmDataContract": len(operations(c.AlgorithmDataContract)),
                   "UiProjectionPort": len(operations(c.UiProjectionPort)),
                   "InputRequirement": len(inspect.signature(c.InputRequirement).parameters),
                   "PluginSpec": len(inspect.signature(c.PluginSpec).parameters),
                   "AlgorithmResultEnvelope": len(inspect.signature(c.AlgorithmResultEnvelope).parameters),
                   "__all__": len(c.__all__)})
print("CONTENT_HASH_MAGIC ok =", c.CONTENT_HASH_MAGIC == b"harmonica-eval/surface/v1\x00")


def probe(fn):
    try:
        fn()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return "NO-RAISE"


print("probe AudioFormat(channels=2)      ->", probe(lambda: c.AudioFormat(sample_rate=44100, channels=2, dtype="float32")))
print("probe AudioFormat(dtype='float64') ->", probe(lambda: c.AudioFormat(sample_rate=44100, channels=1, dtype="float64")))
print("probe UiSeries 省略 timeline_basis ->", probe(lambda: c.UiSeries(key="k", label="l", t=(0.0,), values=(1.0,), unit="cents")))
print("Q2 OK")
PY

# ── Q3 · 文本断言：TimelineBasis.REFERENCE 的冻结口径（INV-003-7）与 status 取值域（INV-003-10） ──
"$PYTHON" - <<'PY' 2>&1 | tee data/out/FILE-003-q3.txt | tee -a data/out/FILE-003-verify.txt
import ast, importlib.util, pathlib, sys

SRC = pathlib.Path("harmonica_eval/contract.py")
tree = ast.parse(SRC.read_text(encoding="utf-8"))
doc = pathlib.Path(".spec/build/FILE-003-v1.md").read_text(encoding="utf-8")

sec42 = doc.split("### 4.2", 1)[1].split("### 4.3", 1)[0]
for needle in ("两侧帧号一一对应", "逐帧相减", "按音配对",
               "同网格、同 shape、同 hop_length", "源时间网格", "归一化网格"):
    assert needle in sec42, f"§4.2 缺少冻结表述: {needle}"
sec48 = doc.split("### 4.8", 1)[1].split("### 4.9", 1)[0]
for needle in ("'OK'", "'DEGRADED'", "'INCOMPATIBLE'", "'FAILED'"):
    assert needle in sec48, f"§4.8 缺少 status 取值域: {needle}"
for needle in ("Sequence[UiScalar | UiSeries]", "coverage", "warnings", "key"):
    assert needle in sec48, f"§4.8 缺少自描述 payload 规则: {needle}"
assert "REFERENCE 只表示" in doc or "不表示两侧帧号一一对应" in doc

# 枚举成员文档按 AST 取（不依赖 Enum 成员 __doc__ 的运行期行为）
def member_docs(class_name):
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    out, pending = {}, None
    for node in cls.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            pending = node.targets[0].id
        elif (pending and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
              and isinstance(node.value.value, str)):
            out[pending] = node.value.value
            pending = None
    return out

basis = member_docs("TimelineBasis")
assert set(basis) == {"REFERENCE", "WARPED"}, f"TimelineBasis 成员缺失: {sorted(basis)}"
for needle in ("源时间网格", "抢拍拖拍"):
    assert needle in basis["REFERENCE"], f"TimelineBasis.REFERENCE 缺少: {needle}"
for needle in ("归一化网格", "禁止"):
    assert needle in basis["WARPED"], f"TimelineBasis.WARPED 缺少: {needle}"

# REFERENCE 成员文档不得出现任何「逐帧」式帧号对应表述
assert "逐帧" not in basis["REFERENCE"], "REFERENCE 文档不得出现「逐帧」字样"

spec = importlib.util.spec_from_file_location("contract_under_test", SRC)
c = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = c
spec.loader.exec_module(c)
assert isinstance(c.TimelineBasis.REFERENCE, c.TimelineBasis)
print("Q3 OK")
PY
```

**验收判据**（可机械判定，非「看起来对」）。下列每一条都对应上面脚本里的一条 `assert`，全部通过即为验收通过：

- [ ] INV-003-1：Q1 的 AST 断言通过——模块顶层语句 ∈ {import, class, 常量赋值/注解赋值, docstring}；类体语句 ∈ {方法声明, 赋值, 注解赋值, docstring}；15 个方法中只有 `AudioFormat.__post_init__`（两处校验）、`ResolutionView.is_available`（一次集合成员查询）与 `HarmonicaError.__str__`（展示格式化）有实体逻辑，其余 12 个声明体只含 docstring 与末尾 `...`（长规格 docstring 位于 `...` 前，AST 断言逐条确认其前没有实际计算）；真实代码（AST `Name`/`Attribute` 节点）中不出现 `open`/`print`/`hashlib`/`os`/`sha256`/`tobytes`/`asarray` 等计算与 I/O 名字。dataclass 数量断言：按 `HarmonicaError` 异常基类不计入的现有统计口径恰为 12（包含 `ResolutionView`；若把基类也按 Python 装饰器计数则为 13，文档同时写明两种口径）。
- [ ] INV-003-2：Q1 的 import 表断言通过——`{__future__, dataclasses, enum, typing, numpy, numpy.typing}` 之外的模块一个都没有，`ast.ImportFrom.level == 0`（无相对 import，即无本包 import）。
- [ ] INV-003-3：Q2 的 4 前缀 × 5 units 共 20 个 `PortDescriptor` 全部构造成功，且每个实例的 `FIELD_LAYOUTS[port_id.split('.', 1)[0]] == tuple(field_names)`。
- [ ] INV-003-4：Q2 的 `dict(FIELD_LAYOUTS)` 等于 4 键冻结字典，每个值为 `tuple`，chroma 长度 12 且首元素为 `"C"`。
- [ ] INV-003-5：Q2 的 `UNITS_VOCABULARY`（10 元素，含 `ratio` / `count`）、`CORE_REQUIRED_PORTS`（2 项）、`FORBIDDEN_OPERATIONS`（10 项，含 `align`/`fft`/`register_algorithm`）、`CONTENT_HASH_MAGIC`（逐字节）断言全部通过。
- [ ] INV-003-6：Q2 的 `len(SessionState) == 6` 且成员名集合等于冻结集合。
- [ ] INV-003-7：Q3 的文本断言通过——本文件 §4.2 含「两侧帧号一一对应」「逐帧相减」「按音配对」「同网格、同 shape、同 hop_length」；由 AST 取出的 `TimelineBasis.REFERENCE` 成员文档含「源时间网格」与「抢拍拖拍」且不含「逐帧」字样，`TimelineBasis.WARPED` 成员文档含「归一化网格」与「禁止」。
- [ ] INV-003-8：Q2 的 `public_names(AlgorithmDataContract) == {"manifest", "read", "resolution"}`、`operations(AlgorithmDataContract) == {"manifest", "read"}`、`resolution` 是 `property`，且 `ResolutionView.is_available` 对可用/缺失/未知端口分别返回 `True` / `False` / `False`；`read` 形参恰为 `["self", "port_id", "time_range"]`。
- [ ] INV-003-9：Q2 的 `operations(HostContract)` 等于 7 操作冻结集合，且 5 个会话级操作的形参逐个匹配（`set_reference`/`set_practice` 均含 `session_id`）。
- [ ] INV-003-10：Q2 断言 `InputRequirement` 6 字段且仅 `port_id` 必填、`PluginSpec` 6 字段、`AlgorithmResultEnvelope` 11 字段、`payload` 注解逐字为 `Sequence[UiScalar | UiSeries]`，并成功构造 `OK` / `DEGRADED` / `FAILED` 三种自描述结果；Q3 断言本文件 §4.8 明文列出 `'OK'`/`'DEGRADED'`/`'INCOMPATIBLE'`/`'FAILED'` 四值及降级证据规则。
- [ ] INV-003-11：Q2 的 `len(ErrorCode) == 12` 且 `{m.name: m.value}` 为恒等映射。
- [ ] INV-003-12：Q2 的三个映射键集 == `set(UiCommandKind)`（6 成员）；`UI_PAYLOAD_KEYS` 中 `SET_REFERENCE`/`SET_PRACTICE` 恰为 `("path",)`、其余 4 个为空元组；6 条 `COMMAND_LEGALITY` 逐条等于冻结集合。
- [ ] INV-003-13：Q2 中 `UiSeries(...)` 省略 `timeline_basis` 抛 `TypeError`（必填语义成立）；`UiView(progress=1.0)` 与 `UiView(progress=None)` 均可构造。
- [ ] INV-003-14：Q2 的 `issubclass(ContractViolation|CoreBuildError|AlgorithmError, HarmonicaError)` 全部为真，且 `HarmonicaError` 派生自 `Exception`。
- [ ] INV-003-15：Q1 的 `__all__` 断言通过——无重复项，长度恰为 32，每个列出的名字都在模块命名空间存在，32 个必需符号全部在列。
- [ ] 三段脚本的输出依次为 `Q1 OK`、`Q2 OK`、`Q3 OK`，且整段 bash 退出码为 0（`set -euo pipefail` 下任一 `assert` 失败即非 0）。

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

全部路径相对仓库根 `/Users/Apple/Desktop/dsh-archive/harmonica-eval`。提交证据 = 下列每一项都实际存在、且内容与本文件 §7/§8 一致。

**产物（1 个，唯一）**

- [ ] `harmonica_eval/contract.py` —— 本文件唯一的交付物。判据：存在且非空；`python3 -c "import ast,pathlib; ast.parse(pathlib.Path('harmonica_eval/contract.py').read_text(encoding='utf-8'))"` 退出码 0（可解析）；文件头三行依次为 `FILE-ID: FILE-003`、`COMPONENT: COMP-CONTRACT…`、`SPEC: SPEC.md@v2.1 …`；`__all__` 长度恰为 32（§8 Q1），且每项都在模块命名空间存在。

**验证命令与输出（3 段，逐段落盘）**

- [ ] §8 的 Q1 段（AST 静态断言）实际运行，退出码 0，stdout 末行为 `Q1 OK`。原始输出落到 `data/out/FILE-003-q1.txt`。
- [ ] §8 的 Q2 段（常量/枚举/Protocol/dataclass 断言）实际运行，退出码 0，stdout 末行为 `Q2 OK`。原始输出落到 `data/out/FILE-003-q2.txt`。
- [ ] §8 的 Q3 段（文本口径与枚举成员文档断言）实际运行，退出码 0，stdout 末行为 `Q3 OK`。原始输出落到 `data/out/FILE-003-q3.txt`。
- [ ] 三段合并落盘：`data/out/FILE-003-verify.txt`（由 §8 命令里的 `tee -a` 直接生成，不是手工拼接），内容为 Q1/Q2/Q3 三段 stdout 与 stderr 按执行顺序的全文。判据：文件内出现 `Q1 OK`、`Q2 OK`、`Q3 OK` 三行，且不含 `Traceback`、不含 `AssertionError`。
- [ ] 三段各自的退出码：`set -euo pipefail` 下整段 bash 的退出码即三段的复合退出码（任一 `assert` 失败 → 管道非 0 → bash 非 0）。判据：报告里写明实测退出码，且必须为 `0`；非 0 即验收不通过。

**必须一并提交的实测数字（写进证据文件，不接受「都通过了」这种说法）**

- [ ] import 表实测值：实际被 import 的顶层模块名集合，必须恰为 `{'__future__', 'dataclasses', 'enum', 'typing', 'numpy', 'numpy.typing'}`（6 个）。
- [ ] 计数实测值：`len(SessionState)=6`、`len(TimelineBasis)=2`、`len(AlignmentRepresentation)=2`、`len(ErrorCode)=12`、`len(UiCommandKind)=6`、`len(FIELD_LAYOUTS)=4`、`len(UNITS_VOCABULARY)=10`、`len(CORE_REQUIRED_PORTS)=2`、`len(FORBIDDEN_OPERATIONS)=10`、普通 dataclass 数 12（`HarmonicaError` 基类另计，含基类 13）、`HostContract` 操作数 7、`AlgorithmDataContract` 操作数 2（另有 1 个 `resolution` 只读状态属性）、`UiProjectionPort` 操作数 2、`InputRequirement` 字段数 6、`PluginSpec` 字段数 6、`AlgorithmResultEnvelope` 字段数 11、`__all__` 长度 32。
- [ ] 常量逐字节值：`CONTENT_HASH_MAGIC == b"harmonica-eval/surface/v1\x00"` 的比较结果（`True`/`False`）。
- [ ] 反例实测：`AudioFormat(channels=2)` 抛出的异常类型与 `str(exc)`（必须为 `ValueError` / `契约要求 mono`）；`AudioFormat(dtype='float64')` 同上（`ValueError` / `契约要求 float32`）；`UiSeries` 省略 `timeline_basis` 抛出的异常类型（必须为 `TypeError`）。

**未做与已知缺口（必须显式声明，不得省略）**

- [ ] `ErrorCode.ALGORITHM_TIMEOUT`：v0.1 无产生点，任何路径不得产出。
- [ ] `ErrorCode.COCKPIT_DETACHED`：v0.1 无产生点，`UiProjectionPort` 无上报通道，不得为其新增第三个操作。
- [ ] `read()` 的失败语义（端口不存在 / `t0 >= t1` / `t1` 超时长 / NaN 时刻 → `ContractViolation`；窗内无数据且 `t1` 在时长内 → 空 `BufferView` 合法）在本文件中**只有声明**，实际复验属 FILE-005/006；本文件级证据**不**声称已复验该行为。
- [ ] `content_hash` 的 sha256 计算在本文件中**未执行**（`hashlib` 不在 import 表内）；实际计算与跨实现对照属 C2 Seal 阶段。

**边界声明（本次交付的越界检查）**

- [ ] 本次改动只落在 `.spec/build/FILE-003-v1.md` 的 §7 / §8 / §9，§1–§6 与 §10 逐字未动（判据：对 §1–§6 与 §10 做改动前后文本比对，字节一致）。
- [ ] `harmonica_eval/contract.py` 本身在本次交付中零改动（本文件是冻结产物，实现者不得修改）。
- [ ] 未新增任何文件（`data/out/` 下的验证输出除外）、未改文件名、未删除任何既有节标题。

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
