# FILE-200 — `harmonica_eval/algorithms/__init__.py`

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/algorithms/__init__.py`
> 生成依据：
> - `harmonica_eval/algorithms/__init__.py`@v1（289 行壳件，含 ROLE / INTENT / MUST / MUST NOT 铭牌、`AlgorithmSpec`、`ALGORITHMS`、`PAYLOAD_SCHEMAS`）
> - `profile.PORTS`（数据面端口唯一权威）
> - `contract.AlgorithmDataContract`、`contract.AlgorithmResultEnvelope`、`contract.AlgorithmError`
> - `COMPONENTS.md@v2 §3`
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-200 |
| 所属组件 | COMP-C3 Algorithm |
| 层级 | L3（symbol / implementation） |
| 上游 | C1（Core 编排器）：`import` 本模块，遍历 `ALGORITHMS`，用 `required_ports` 与数据面比对，缺端口即跳过该算法（INCOMPATIBLE），否则调用 `entry(surface)` |
| 下游 | `harmonica_eval.contract`（`AlgorithmDataContract` / `AlgorithmResultEnvelope`）、`harmonica_eval.profile`（`PORTS`）、同包算法模块 `harmonica_eval.algorithms.pitch` / `.timing` / `.dynamics` |
| 同层邻居 | `harmonica_eval/algorithms/pitch.py`、`harmonica_eval/algorithms/timing.py`、`harmonica_eval/algorithms/dynamics.py`（三者各实现一个 `run()`，本文件只引用，不改写） |
| 你的权限 | 只实现本文件 `harmonica_eval/algorithms/__init__.py` |

C2 完全不知道本文件存在。本文件的任何调用都来自 C1。

---

## 2 · 这个文件为什么存在

追溯：Product Intent「双音频对比 → 客观数值指标」；架构承诺「换算法不改核心」。

本文件是该承诺的**唯一落点**：系统里存在哪些算法、每个算法需要哪些端口、每个算法的 payload 键叫什么，全部由本文件声明。C1 从本文件读取注册表并逐个调用；C2 不感知算法集合。

**删掉它会坏掉什么**（逐条列出，缺一即证明本文件不可删）：

1. C1 失去算法清单来源 → 无法枚举算法、无法做 INCOMPATIBLE 判定、无法调用任何算法。
2. `required_ports` 失去唯一权威 → C1 无从知道某算法需要哪些端口，`AlgorithmResultEnvelope.required_ports` 这一追溯字段失去可填入的事实来源。
3. `PAYLOAD_SCHEMAS` 消失 → `host/app.py` 的 schema 校验器与 UI 投影失去键名共同事实来源，产出方与校验方再次分叉，退化为「不报错、只静默算错」。
4. `assert_registry_integrity()` 消失 → 重复算法 ID、指向不存在端口的声明、成对端口单边声明、payload 键表与算法集合不匹配，全部延后到运行期才暴露，或永不暴露。
5. 「新增算法只改这个文件」的成本结构崩塌 → 加一个算法变成改 Core。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import（穷举，清单外一律禁止）**：

- Python 标准库（仅这 3 个模块 + 1 个 future 声明）：
  - `from __future__ import annotations`
  - `dataclasses`（只用 `dataclass`）
  - `typing`（只用 `Callable`、`Mapping`、`Sequence`）
  - `inspect`（只用 `signature`，供 §4.4 检查 C5）
- 第三方：**无**。本文件的第三方依赖集合是空集。
- 本包内（精确模块与符号，穷举）：
  - `from ..contract import AlgorithmDataContract, AlgorithmResultEnvelope`
  - `from ..profile import PORTS`
  - `from . import dynamics, pitch, timing`
  - 通过 `pitch` / `timing` / `dynamics` 模块对象读取的符号，仅这 3 个：`ALGORITHM_ID`、`ALGORITHM_VERSION`、`run`

**禁止 import**：

- `harmonica_eval.core`、`harmonica_eval.host`、`harmonica_eval.cockpit`（任何形式，含函数内延迟 import、含 `importlib` 间接 import）
- `numpy`、`scipy`、`soundfile`、`librosa` 及任何第三方包
- `os`、`sys`、`json`、`pathlib`、`logging`、`time`、`random`、`functools`、`collections`、`types`、`copy`
- 任何不在上述清单里的东西。需要清单外的依赖 → 停止，转 §10。

**版本锁定**：第三方集合为空，故版本锁定项为空。标准库由运行解释器提供，实际版本以 §9 证据包中的 `python --version` 原文为准；本文件不另立解释器版本下限。

**唯一相对壳件新增的包内依赖**：`from ..profile import PORTS`。理由：§4.4 检查 C2 必须核对端口存在性，壳件未 import 该模块。`profile` 是配置叶子模块，不 import 本模块；若发现 `profile` 反向 import 本模块（循环 import）→ 停止，转 §10。

---

## 4 · 你要实现什么（行为规格）

### 4.0 壳件中已存在的冻结内容

壳件 `harmonica_eval/algorithms/__init__.py` 已写定并**冻结**：模块 docstring、`AlgorithmSpec`、`assert_registry_integrity()` 的 docstring、`ALGORITHMS` 元组、`PAYLOAD_SCHEMAS` 表、以及全部 MUST / MUST NOT 铭牌与沿革注释。

实现者的工作只有两项：

1. 把 `assert_registry_integrity()` 的 `raise NotImplementedError(...)` 替换为 §4.4 的实现；
2. 在模块末尾（所有定义之后）加恰好一次模块级调用 `assert_registry_integrity()`（§4.5）。

`ALGORITHMS` 与 `PAYLOAD_SCHEMAS` 的字面内容、元素顺序、键顺序、注释文字**不得改动**（含删除、重排、改写注释）。若你认为其中任何一项是错的 → 停止，转 §10。

---

### 4.1 `AlgorithmSpec`（冻结数据类，只读不改）

- **定义**：`@dataclass(frozen=True)` 修饰的类，字段顺序恰为 `algorithm_id: str`、`version: str`、`required_ports: Sequence[str]`、`entry: Callable[[AlgorithmDataContract], AlgorithmResultEnvelope]`、`label: str`。
- **不得**新增字段、不得设默认值、不得加 `__post_init__`、不得改 `eq` / `order` / `frozen`、不得加 `slots`。
- **输入/输出**：无方法；只有字段。
- **不变量**：实例可哈希（`required_ports` 在 `ALGORITHMS` 中一律是 `tuple`，故 `hash(spec)` 必须成功）。
- **边界**：本文件不构造 `ALGORITHMS` 之外的 `AlgorithmSpec` 实例（§8 的负向测试除外，且该测试只构造临时对象并立即丢弃）。

### 4.2 `ALGORITHMS: tuple[AlgorithmSpec, ...]`

- **输出**：长度恰为 3 的元组，顺序**冻结**为：`pitch` → `timing` → `dynamics`。C1 按此顺序迭代，结果顺序与判定顺序由此确定。
- **每条的字段值（冻结）**：

| 位置 | `algorithm_id` | `version` | `required_ports`（顺序冻结） | `entry` | `label` |
| --- | --- | --- | --- | --- | --- |
| 0 | `pitch.ALGORITHM_ID` | `pitch.ALGORITHM_VERSION` | `("pitch.reference", "pitch.practice", "notes.reference", "notes.practice")` | `pitch.run` | `"音准"` |
| 1 | `timing.ALGORITHM_ID` | `timing.ALGORITHM_VERSION` | `("pcm.mapped.reference", "pcm.mapped.practice", "notes.reference", "notes.practice")` | `timing.run` | `"节奏"` |
| 2 | `dynamics.ALGORITHM_ID` | `dynamics.ALGORITHM_VERSION` | `("rms.reference", "rms.practice", "notes.reference", "notes.practice")` | `dynamics.run` | `"力度"` |

- **`algorithm_id` / `version` 必须从算法模块属性读取，禁止在本文件重抄字符串字面量**（两处写同一份事实必然分叉，与 `FIELD_LAYOUTS` 是同一教训）。`label` 是本文件自有的中文字面量。
- **`required_ports` 的算法口径（冻结，不得改写）**：
  - 三个算法**都**声明 `notes.reference` + `notes.practice`。理由（原文保留）：pitch 用逐音索引把逐帧偏差聚合成「第 n 个音偏了多少音分」；timing 用 `onset_sec` 作两侧起音时刻的真值；dynamics 用逐音区间取能量，从而**按音配对**而非按时间轴配对。
  - ★ **`pitch` 声明 `notes.reference` + `notes.practice` 的硬理由**：参考录音与练习录音是两段独立录音，帧数默认不等，逐帧对齐不可用；必须按音配对才能比较，否则音准比较不成立。
  - **`timing` 不得声明 `warp_path`**：timing 的要点是不做任何时间归一化（归一化会把抢拍拖拍抹成 0），而 `warp_path` 按定义是 DTW 对应关系，拿它把练习时刻映射到参考钟**就是**归一化。「声明需要它」与「不许用归一化映射」不可兼得。`warp_path` 是证据端口，只有 core 生成，全项目没有算法消费。
  - `required_ports` 的顺序是规范顺序，C1 逐字复制进信封时**不得**重排。
- **不变量**：`ALGORITHMS` 是 `tuple`（不可变），`len(ALGORITHMS) == 3`，三个 `algorithm_id` 互不相同。

### 4.3 `PAYLOAD_SCHEMAS: Mapping[str, tuple[str, ...]]` ★ 唯一权威

**本表是 payload 键名的唯一权威。** 算法实现与 C1 校验器都必须引用它。每个算法 payload 的键必须**恰好**是表中列出的那些（不多不少）。

**三个算法各自的键，逐字列出，顺序即表中顺序（冻结）**：

- `"pitch"`（5 个键）：
  1. `per_note_cents`
  2. `median_abs_cents`
  3. `off_pitch_ratio`
  4. `n_notes_used`
  5. `sample_rate`
- `"timing"`（8 个键）：
  1. `per_note_onset_ms`
  2. `median_onset_ms`
  3. `spread_ms`
  4. `early_ratio`
  5. `late_ratio`
  6. `on_time_ratio`
  7. `n_notes_used`
  8. `n_unpaired`
- `"dynamics"`（5 个键）：
  1. `per_note_delta_db`
  2. `median_db`
  3. `spread_db`
  4. `n_notes_used`
  5. `n_unpaired`

**表的规则（冻结）**：

- 键集合恰为三个 `algorithm_id`：`set(PAYLOAD_SCHEMAS) == {s.algorithm_id for s in ALGORITHMS}`，且互不遗漏、不含额外键。
- 每个值是 `tuple`，元素互不重复，每个元素是非空 `str`。
- `per_note_*` 是逐音序列，长度必须等于该次统计的 `n_notes_used`（该约束在运行期由算法与 C1 校验器落实，本文件只负责键名权威）。
- `UiScalar.key` / `UiSeries.key` 的取值必须取自本表的键名，从而 `metrics.json` 与界面不出现两套名字。

★★ **已知不对称（如实记录，禁止自行修）**：`pitch` 的 schema 有 `sample_rate` 而**没有** `n_unpaired`；`timing` 与 `dynamics` 都**有** `n_unpaired`。后果：**音准算法排除掉的未配对音无处报告**，`metrics.json` 与界面无法显示音准侧丢弃了多少音。

- 记录编号：`GAP-200-1`。
- 处置：**不在本文件修复**。改动 `PAYLOAD_SCHEMAS` 等于改冻结表，属接口变更，按宪章 §37 上报，不自行添加 `n_unpaired`。实现者不得「顺手补齐」该键。

### 4.4 `assert_registry_integrity() -> None`

- **输入**：无参数。
- **输出**：成功时返回 `None`（类型注解为 `-> None`）。
- **行为**：在调用时刻读取**模块级全局** `ALGORITHMS` 与 `PAYLOAD_SCHEMAS`，按 C1→C7 顺序逐条检查，**首个**违反即抛出，不做继续检查，不聚合错误。
- **读数方式（冻结）**：必须以运行期全局名查找读取 `ALGORITHMS` 与 `PAYLOAD_SCHEMAS`；**不得**把二者写成函数默认参数、不得闭包捕获、不得在模块 import 时复制成局部常量。§8 的负向测试依赖这一条。
- **检查清单（7 条，顺序与编号冻结）**：

| 编号 | 检查内容 | 违反时抛出的消息前缀 |
| --- | --- | --- |
| C1 | `algorithm_id` 无重复（`len(set(ids)) == len(ALGORITHMS)`） | `REGISTRY_INTEGRITY:C1:` |
| C2 | 每个 `required_ports` 中的每个端口 `port in PORTS` 为真 | `REGISTRY_INTEGRITY:C2:` |
| C3 | 每个 `required_ports` 非空（`len(...) >= 1`） | `REGISTRY_INTEGRITY:C3:` |
| C4 | 三个算法模块与注册条目一一对应 | `REGISTRY_INTEGRITY:C4:` |
| C5 | `entry` 可调用，且签名恰为冻结形式 | `REGISTRY_INTEGRITY:C5:` |
| C6 | 每个算法的端口成对：`X.reference` 与 `X.practice` 要么都有、要么都没有 | `REGISTRY_INTEGRITY:C6:` |
| C7 | `PAYLOAD_SCHEMAS` 与 `ALGORITHMS` 双向键覆盖一致，且表本身良构 | `REGISTRY_INTEGRITY:C7:` |

- **C2 口径**：用 `port in PORTS` 做成员测试（对 `Mapping` 是键成员，对名称序列是值成员），不依赖 `PORTS` 的具体容器类型；对 `PORTS` 的容器类型、长度、内容本文件不作任何断言。
- **C4 口径（冻结为一一对应）**：对 `m in (pitch, timing, dynamics)`，`ALGORITHMS` 中必须**恰有 1 条**满足 `spec.algorithm_id == m.ALGORITHM_ID` 且 `spec.version == m.ALGORITHM_VERSION`。因此「某个模块未被注册」与「某条注册没有对应模块」都触发 C4。检查 C4 只读这 3 个模块属性，不读算法模块的任何其他符号。
- **C5 口径（冻结为可机械判定，不校验注解文本）**：
  1. `callable(entry)` 必须为真；
  2. `inspect.signature(entry)` 的参数列表中，参数总数必须恰为 1，该参数的 `kind` 必须是 `POSITIONAL_ONLY` 或 `POSITIONAL_OR_KEYWORD`，且 `VAR_POSITIONAL` / `VAR_KEYWORD` / `KEYWORD_ONLY` 一个都不得出现；
  3. 参数**名**不校验；注解**文本**不校验（`from __future__ import annotations` 让运行期注解是字符串，校验注解文本必然误判）；
  4. `inspect.signature` 抛出的 `TypeError` 或 `ValueError` 必须被捕获并转抛为 C5 的 `RuntimeError`（这类异常本身就意味着签名不合冻结形式），不得吞掉。
- **C6 口径（冻结，后缀字面量写死）**：设 `S = set(spec.required_ports)`。对每个以 `".reference"` 结尾的 `p`，`p[: -len(".reference")] + ".practice"` 必须在 `S` 中；对每个以 `".practice"` 结尾的 `p`，`p[: -len(".practice")] + ".reference"` 必须在 `S` 中。两侧都必须查。
- **C7 口径（双向覆盖 + 良构，边界冻结）**：
  1. 对每条 `spec`，`spec.algorithm_id in PAYLOAD_SCHEMAS` 必须为真；
  2. 对 `PAYLOAD_SCHEMAS` 的每个键 `k`，必须存在 `spec` 使 `spec.algorithm_id == k`；
  3. 每个值必须是 `tuple`，长度 ≥ 1，每个元素是非空 `str`，同值内无重复键名。
  - **C7 的边界（明确写死，避免越权）**：运行期 payload 的实际键集合是运行期产物，import 期静态检查够不着它。因此本函数对「payload 键恰为表中键」的**静态**部分只做上面 3 项；逐次运行「恰为」的相等校验由 C1 的校验器以 `PAYLOAD_SCHEMAS` 为权威在运行期执行。**不得**为了在 import 期做运行期比较而 import 算法模块的额外常量或新增算法模块符号；**不得**把这项边界当作「以后再补」。
- **异常类型与消息格式（冻结）**：一律抛内置 `RuntimeError`，消息格式为 `REGISTRY_INTEGRITY:<编号>: <细节>`，`<编号>` 取 `C1`…`C7`；`<细节>` 必须包含触发违规的标识（违规的 `algorithm_id`、端口名或 payload 键名），使人工定位无需复跑。不新增错误码、不改 `contract`、不使用 `assert` 语句（`assert` 会被 `-O` 去掉）。
- **检查集合封闭**：「`ALGORITHMS` 是 tuple」与「`PAYLOAD_SCHEMAS` 不可变」**不**放进本函数（本函数的检查集恰为 7 条）。这两条由 §8 判据验证。
- **不变量**：返回 `None` 时，C1…C7 全部为真；连续调用两次结果相同（幂等，无状态）；调用不修改任何全局。

### 4.5 import 期副作用（冻结）

模块末尾必须恰有**一次**模块级语句 `assert_registry_integrity()`，位置在所有定义之后（`PAYLOAD_SCHEMAS` 赋值之后）。配置错误由此在 import 时立刻暴露。

该调用**不得**被 `try` / `except` 包裹，不得只在 `__main__` 下调用，不得放进函数体内延迟执行。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| `algorithm_id` 重复 | 显式失败，立即停止检查 | `RuntimeError("REGISTRY_INTEGRITY:C1: ...")` |
| `required_ports` 含 `PORTS` 中不存在的端口 | 显式失败，立即停止检查 | `RuntimeError("REGISTRY_INTEGRITY:C2: ...")` |
| 某算法 `required_ports` 为空 | 显式失败，立即停止检查 | `RuntimeError("REGISTRY_INTEGRITY:C3: ...")` |
| 算法模块未被注册 / 注册条目无对应模块 / `version` 与模块不一致 | 显式失败，立即停止检查 | `RuntimeError("REGISTRY_INTEGRITY:C4: ...")` |
| `entry` 不可调用，或参数个数不为 1，或出现 `*args` / `**kwargs` / 仅关键字参数 | 显式失败，立即停止检查 | `RuntimeError("REGISTRY_INTEGRITY:C5: ...")` |
| `inspect.signature` 自身抛 `TypeError` / `ValueError` | 捕获后转抛，不吞 | `RuntimeError("REGISTRY_INTEGRITY:C5: ...")` |
| 端口成对性破裂（只有 `X.reference` 或只有 `X.practice`） | 显式失败，立即停止检查 | `RuntimeError("REGISTRY_INTEGRITY:C6: ...")` |
| `PAYLOAD_SCHEMAS` 缺某个 `algorithm_id` 键 / 含未注册的键 / 值不是 `tuple` / 值为空 / 元素非 `str` 或空串 / 值内键名重复 | 显式失败，立即停止检查 | `RuntimeError("REGISTRY_INTEGRITY:C7: ...")` |
| 全部检查通过 | 返回 | `None` |
| `from ..profile import PORTS` 失败（`ImportError` / `ModuleNotFoundError`） | 传播，不捕获，不降级 | 原异常向上冒泡，import 失败 |
| 算法模块 import 失败 | 传播，不捕获，不降级 | 原异常向上冒泡，import 失败 |
| 「payload 键恰为表中键」的运行期比较 | **不在本文件执行**；由 C1 校验器在运行期以本表为权威执行 | 由 C1 产生 `ALGORITHM_RESULT_INVALID` |

★ 宪章 §5.6：**禁止静默降级**。以下做法全部被本表禁止，出现即判实现错误：

- 返回 `True` / `False` 或错误列表代替抛出；
- `logging.warning` / `print` 后继续；
- `except Exception: pass` 或任何形式的吞异常；
- 「端口不存在就把它从 `required_ports` 里去掉」「成对性破裂就自动补一个端口」「键表缺项就自动补 `n_unpaired`」这类**就地修复**；
- 把失败推迟到运行期再用默认值掩盖。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-200-1 | `ALGORITHMS` 是 `tuple`，长度 3，顺序为 pitch → timing → dynamics | §8.2 中 `isinstance(A.ALGORITHMS, tuple)` 与三元素顺序断言 |
| INV-200-2 | `ALGORITHMS` 三条的 `algorithm_id` / `version` 逐条等于对应算法模块的同名属性（无字符串重抄） | §8.2 中对 `pitch/timing/dynamics` 属性的等值断言 |
| INV-200-3 | 每个 `required_ports` 是 `profile.PORTS` 的子集 | §8.2 中逐端口 `port in profile.PORTS` |
| INV-200-4 | 每个算法的 `required_ports` 成对：`notes.reference` 与 `notes.practice` 三个算法都有；`pitch.*`、`pcm.mapped.*`、`rms.*` 各自成对 | §8.2 的 `required_ports` 逐字等值断言 + §8.4 的 C6 负向测试 |
| INV-200-5 | `timing` 的 `required_ports` 不含 `warp_path` | §8.2 中 `"warp_path" not in A.ALGORITHMS[1].required_ports` |
| INV-200-6 | `PAYLOAD_SCHEMAS` 键集合恰为 `{"pitch","timing","dynamics"}`，三值逐字等于 §4.3 列出的键序列 | §8.2 的三条元组等值断言 |
| INV-200-7 | `PAYLOAD_SCHEMAS["pitch"]` 不含 `n_unpaired`；`timing`、`dynamics` 都含 `n_unpaired`（不对称被如实保留） | §8.2 中 `"n_unpaired" not in ...["pitch"]` 与两条 `in` 断言 |
| INV-200-8 | `per_note_*` 键名在表中以 `per_note_` 前缀出现，且长度等于该次统计的 `n_notes_used`（运行期约束，由算法与 C1 落实） | §8.2 中三个 `per_note_*` 键存在性断言；长度约束由 FILE-201/202/203 与 C1 的测试覆盖 |
| INV-200-9 | `AlgorithmSpec` 实例可哈希（`required_ports` 是 `tuple`） | §8.2 中 `hash(spec)` 对三条全部成功 |
| INV-200-10 | `assert_registry_integrity()` 返回 `None` 且幂等 | §8.2 中连续两次调用均为 `None` |
| INV-200-11 | 七条检查各自可独立触发，抛出 `RuntimeError` 且消息前缀为 `REGISTRY_INTEGRITY:C<编号>:` | §8.4 的 C1 / C3 / C6 / C7 负向测试 |
| INV-200-12 | import 本模块时恰执行一次 `assert_registry_integrity()`，位置在 `PAYLOAD_SCHEMAS` 赋值之后 | §8.5 的 AST 静态检查 |
| INV-200-13 | 模块不 import `core` / `host` / `cockpit` / 任何第三方 | §8.5 的 AST 静态检查（import 白名单） |

---

## 7 · 边界（明确不做）

- 不实现任何算法逻辑。逐音偏差、onset 配对、能量统计全部属于 FILE-201/202/203；本文件只声明。
- 不修改 `harmonica_eval/algorithms/pitch.py`、`timing.py`、`dynamics.py`、`contract.py`、`profile.py` 或任何其他文件。只写本文件。
- 不增删算法、不改 `ALGORITHMS` 的顺序、不改任何 `required_ports` 的内容或顺序。
- 不新增端口。声明 `profile` 中不存在的端口会在启动时被判不可用。
- 不修改 `PAYLOAD_SCHEMAS` 的键。**特别地：不得为 `pitch` 补 `n_unpaired`**（`GAP-200-1`，改表属接口变更，按 §37 上报）。
- 不把 `ALGORITHMS` 或 `PAYLOAD_SCHEMAS` 变成可变容器（不得用 `list`、不得用可变 `dict` 替换现有字面量、不得加 `__setitem__` 之类的包装类型）。
- 不新增公开符号：不新增模块级常量、不新增异常类、不新增辅助函数、不新增 `__all__`、不新增 `__getattr__`。
- 不落盘、不读文件、不联网、不写日志、不打印、不缓存、不做延迟初始化、不做 `importlib` 动态加载。
- 不实现「payload 键恰为表中键」的运行期校验器（那是 C1 的 `ALGORITHM_RESULT_INVALID` 路径）。
- 不实现「每个端口都被某个算法消费」的检查。端口存在有三种正当理由：被算法直接消费（`pitch.*` / `rms.*` / `notes.reference`）、被 Core 内部消费（`chroma.lowres.*`）、数据面保证（`pcm.warped.practice`）。强制「必须被消费」会把后两类误判为死端口并删除，毁掉「对齐可复现」与「算法可自行预处理」两个设计保证。
- 不给 `assert_registry_integrity()` 加参数、返回值、开关或「跳过检查」的环境变量分支。
- 若你发现「不做以上某条就实现不了」 → **不要做**，转 §10。

---

## 8 · 怎么验证你写对了

### 8.1 前置

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python --version
```

`python --version` 的原文必须记入 §9 证据包。

### 8.2 正向验收（全部 assert 必须通过）

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval

python - <<'PY'
import harmonica_eval.algorithms as A
from harmonica_eval import profile
from harmonica_eval.algorithms import dynamics, pitch, timing

# INV-200-1
assert isinstance(A.ALGORITHMS, tuple)
assert len(A.ALGORITHMS) == 3
# INV-200-2（不重抄字面量：与模块属性比对）
assert [s.algorithm_id for s in A.ALGORITHMS] == [pitch.ALGORITHM_ID, timing.ALGORITHM_ID, dynamics.ALGORITHM_ID]
assert [s.version for s in A.ALGORITHMS] == [pitch.ALGORITHM_VERSION, timing.ALGORITHM_VERSION, dynamics.ALGORITHM_VERSION]
assert [s.entry for s in A.ALGORITHMS] == [pitch.run, timing.run, dynamics.run]
assert [s.label for s in A.ALGORITHMS] == ["音准", "节奏", "力度"]
# PAYLOAD_SCHEMAS 的键即 algorithm_id（C7 口径 1、2）
assert set(A.PAYLOAD_SCHEMAS) == {s.algorithm_id for s in A.ALGORITHMS}
assert set(A.PAYLOAD_SCHEMAS) == {"pitch", "timing", "dynamics"}
# required_ports 逐字冻结
assert A.ALGORITHMS[0].required_ports == ("pitch.reference", "pitch.practice", "notes.reference", "notes.practice")
assert A.ALGORITHMS[1].required_ports == ("pcm.mapped.reference", "pcm.mapped.practice", "notes.reference", "notes.practice")
assert A.ALGORITHMS[2].required_ports == ("rms.reference", "rms.practice", "notes.reference", "notes.practice")
# INV-200-3 / INV-200-5 / INV-200-9
for s in A.ALGORITHMS:
    for p in s.required_ports:
        assert p in profile.PORTS, p
    assert len(s.required_ports) >= 1
    hash(s)
assert "warp_path" not in A.ALGORITHMS[1].required_ports
# INV-200-6
assert A.PAYLOAD_SCHEMAS["pitch"] == ("per_note_cents", "median_abs_cents", "off_pitch_ratio", "n_notes_used", "sample_rate")
assert A.PAYLOAD_SCHEMAS["timing"] == ("per_note_onset_ms", "median_onset_ms", "spread_ms", "early_ratio", "late_ratio", "on_time_ratio", "n_notes_used", "n_unpaired")
assert A.PAYLOAD_SCHEMAS["dynamics"] == ("per_note_delta_db", "median_db", "spread_db", "n_notes_used", "n_unpaired")
# INV-200-7（不对称如实保留）
assert "n_unpaired" not in A.PAYLOAD_SCHEMAS["pitch"]
assert "n_unpaired" in A.PAYLOAD_SCHEMAS["timing"]
assert "n_unpaired" in A.PAYLOAD_SCHEMAS["dynamics"]
# INV-200-8（per_note_* 存在）
assert "per_note_cents" in A.PAYLOAD_SCHEMAS["pitch"]
assert "per_note_onset_ms" in A.PAYLOAD_SCHEMAS["timing"]
assert "per_note_delta_db" in A.PAYLOAD_SCHEMAS["dynamics"]
# INV-200-10（返回 None 且幂等）
assert A.assert_registry_integrity() is None
assert A.assert_registry_integrity() is None
print("POSITIVE-OK")
PY
```

期望输出末行：`POSITIVE-OK`。

★ 若 `pitch.ALGORITHM_ID != "pitch"`（或 `timing` / `dynamics` 同理），则壳件自身的 `PAYLOAD_SCHEMAS` 键与本规格互斥 → 停止，转 §10，**不得**自行给表改名。

### 8.3 无异常穿透验收

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python -c "import harmonica_eval.algorithms as A; print('IMPORT-OK', len(A.ALGORITHMS), sorted(A.PAYLOAD_SCHEMAS))"
```

期望输出：`IMPORT-OK 3 ['dynamics', 'pitch', 'timing']`。无任何 traceback。

### 8.4 负向验收（失败语义可机械触发）

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval

python - <<'PY'
import harmonica_eval.algorithms as A

def expect_registry(code, mutate):
    saved = A.ALGORITHMS
    try:
        A.ALGORITHMS = mutate(saved)
        try:
            A.assert_registry_integrity()
        except RuntimeError as e:
            assert str(e).startswith("REGISTRY_INTEGRITY:" + code + ":"), (code, str(e))
            return
        raise AssertionError("未抛出 RuntimeError: " + code)
    finally:
        A.ALGORITHMS = saved

def expect_payload(code, mutate):
    saved = A.PAYLOAD_SCHEMAS
    try:
        A.PAYLOAD_SCHEMAS = mutate(saved)
        try:
            A.assert_registry_integrity()
        except RuntimeError as e:
            assert str(e).startswith("REGISTRY_INTEGRITY:" + code + ":"), (code, str(e))
            return
        raise AssertionError("未抛出 RuntimeError: " + code)
    finally:
        A.PAYLOAD_SCHEMAS = saved

s0 = A.ALGORITHMS[0]

# C1：重复 algorithm_id
expect_registry("C1", lambda s: s + (s[0],))
# C3：required_ports 为空
expect_registry("C3", lambda s: (A.AlgorithmSpec(s0.algorithm_id, s0.version, (), s0.entry, s0.label),) + s[1:])
# C2：声明不存在的端口
expect_registry("C2", lambda s: (A.AlgorithmSpec(s0.algorithm_id, s0.version, ("pitch.reference", "pitch.practice", "notes.reference", "notes.practice", "no.such.port"), s0.entry, s0.label),) + s[1:])
# C6：成对性破裂（只有 reference 侧）
expect_registry("C6", lambda s: (A.AlgorithmSpec(s0.algorithm_id, s0.version, ("pitch.reference",), s0.entry, s0.label),) + s[1:])
# C5：参数个数不为 1
expect_registry("C5", lambda s: (A.AlgorithmSpec(s0.algorithm_id, s0.version, s0.required_ports, (lambda a, b: None), s0.label),) + s[1:])
# C4：version 与算法模块不一致
expect_registry("C4", lambda s: (A.AlgorithmSpec(s0.algorithm_id, s0.version + ".bogus", s0.required_ports, s0.entry, s0.label),) + s[1:])
# C7：表缺一个算法键
expect_payload("C7", lambda m: {k: v for k, v in m.items() if k != "pitch"})
# C7：表内键名重复
expect_payload("C7", lambda m: dict(m, pitch=("per_note_cents", "per_note_cents")))

# 复原后仍必须通过
assert A.assert_registry_integrity() is None
print("NEGATIVE-OK")
PY
```

期望输出末行：`NEGATIVE-OK`。

### 8.5 静态结构验收（import 期调用 + import 白名单）

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval

python - <<'PY'
import ast, pathlib

path = pathlib.Path("harmonica_eval/algorithms/__init__.py")
tree = ast.parse(path.read_text(encoding="utf-8"))

# INV-200-12：恰一次模块级 assert_registry_integrity()，且在 PAYLOAD_SCHEMAS 赋值之后
calls = [n for n in tree.body
         if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
         and getattr(n.value.func, "id", None) == "assert_registry_integrity"]
assert len(calls) == 1, len(calls)
assigns = [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))]
payload_lines = []
for n in assigns:
    targets = n.targets if isinstance(n, ast.Assign) else [n.target]
    if any(getattr(t, "id", None) == "PAYLOAD_SCHEMAS" for t in targets):
        payload_lines.append(n.lineno)
assert len(payload_lines) == 1, payload_lines
assert calls[0].lineno > payload_lines[0]

# INV-200-13：import 白名单（只允许 __future__ / dataclasses / typing / inspect + 三个相对 import）
allowed_roots = {"__future__", "dataclasses", "typing", "inspect"}
for n in ast.walk(tree):
    if isinstance(n, ast.Import):
        for a in n.names:
            assert a.name.split(".")[0] in allowed_roots, a.name
    elif isinstance(n, ast.ImportFrom):
        if n.level == 0:
            assert (n.module or "").split(".")[0] in allowed_roots, n.module
        else:
            assert n.level == 2 and n.module in {"contract", "profile"}, (n.level, n.module)
for bad in ("core", "host", "cockpit"):
    assert bad not in path.read_text(encoding="utf-8").split("'''")[0]
print("STATIC-OK")
PY
```

期望输出末行：`STATIC-OK`。

### 8.6 判据清单（可机械判定，逐条勾选）

- [ ] §8.2 末行输出 `POSITIVE-OK`，退出码 0。
- [ ] §8.3 输出 `IMPORT-OK 3 ['dynamics', 'pitch', 'timing']`，无 traceback。
- [ ] §8.4 末行输出 `NEGATIVE-OK`，八条负向用例全部抛出 `RuntimeError` 且前缀编号正确。
- [ ] §8.5 末行输出 `STATIC-OK`。
- [ ] `assert_registry_integrity()` 的返回注解是 `None`，函数体内不含 `return True` / `return False` / `return [...]`。
- [ ] 函数体内不含 `assert ` 语句（`assert` 会被 `python -O` 去掉）。
- [ ] 函数体内不含 `except Exception` / `except BaseException` / `except:` 裸捕获。
- [ ] `git diff --stat` 相对基线只列出 `harmonica_eval/algorithms/__init__.py` 一个文件。

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] 产物路径：`harmonica_eval/algorithms/__init__.py`（完整文件，非片段）。
- [ ] `git diff --stat` 原文，证明只有本文件被改动。
- [ ] `git diff harmonica_eval/algorithms/__init__.py` 原文，证明 `ALGORITHMS`、`PAYLOAD_SCHEMAS`、全部 docstring 与铭牌文字零改动，新增内容仅为 `assert_registry_integrity()` 的函数体与末尾一次模块级调用。
- [ ] `python --version` 原文。
- [ ] §8.2 的完整 stdout 原文（含 `POSITIVE-OK`）。
- [ ] §8.3 的完整 stdout 原文（含 `IMPORT-OK`）。
- [ ] §8.4 的完整 stdout 原文（含 `NEGATIVE-OK`），并列出八条负向用例各自触发的编号（C1 / C2 / C3 / C4 / C5 / C6 / C7 / C7）。
- [ ] §8.5 的完整 stdout 原文（含 `STATIC-OK`）。
- [ ] 黄金向量：本文件不产出数值，无数值证据项。
- [ ] 若 §8.2 的 `pitch.ALGORITHM_ID == "pitch"` 类断言不成立：`GATE CHALLENGE` 原文，且**不提交**实现。

---

## 10 · ★ 何时必须停止并上报（§22 硬失败对策）

**以下情况必须停止，不得自行设计：**

1. 你发现本文件**需要做上层设计**才能实现 —— 具体指：需要决定一个新阈值、新口径、新端口、新错误码、新公开符号或新依赖。
2. 本文件与任何上游工件**冲突** —— 具体指：`profile.PORTS` 与某条 `required_ports` 冲突；`contract.AlgorithmResultEnvelope` 与信封口径冲突；某算法模块的 `ALGORITHM_ID` / `ALGORITHM_VERSION` / `run` 与本文件 §4.2 的冻结值冲突。
3. 你需要的依赖**不在 §3 清单里**。
4. §4 的行为规格**不足以确定唯一实现** —— 具体指：C1…C7 任一条你无法写出唯一判定。
5. 你认为 §4 的规格本身**是错的**。
6. 你**想动** `PAYLOAD_SCHEMAS` —— 包括为 `pitch` 补 `n_unpaired`（`GAP-200-1`）、改键名、改键顺序、增删键。冻结表的变更属接口变更。
7. 你**想动** `ALGORITHMS` —— 包括增删算法、改顺序、改 `required_ports` 内容、给 `timing` 加回 `warp_path`。
8. 你**想改** `contract` / `profile` / 任一算法模块 / 任一其他文件。

**MOLD BREAK 上报格式**：

```
MOLD BREAK
- 文件 ID：FILE-200
- 触发条款：§10 第 <n> 条
- 我在做什么：
- 卡在哪：
- 实际需要 vs 规格给出：
- 为什么我无法在不做上层设计的前提下继续：
- 建议的上游处理位置：
```

**GATE CHALLENGE 上报格式**（宪章 §37）：

```
GATE CHALLENGE
- 相关 Requirement：
- 相关 Build Instruction 章节：
- 实际需要 vs 规格给出：
- 为什么冲突：
- 复现证据：
- 建议的上游处理位置：
```

**绝对禁止**：

- 先做一个「能跑的 workaround」，以后再说（§38 明文禁止）。
- 自行在代码里加一个「合理的」默认值把冲突掩盖过去（含：端口不存在就删声明、成对性破裂就自动补端口、键表缺项就补 `n_unpaired`、检查失败就 `try/except` 跳过）。
- 静默缩小范围（「这条检查我先不实现」「`-O` 下失效无所谓」）。
- 改 `PAYLOAD_SCHEMAS` 或 `ALGORITHMS` 让检查通过。

---

## 附：本文件的冻结常量速查

| 常量 | 值 | 来源 |
| --- | --- | --- |
| 注册条目数 | `3` | `ALGORITHMS` |
| 注册顺序 | `pitch` → `timing` → `dynamics` | `ALGORITHMS` |
| `ALGORITHMS[0].required_ports` | `("pitch.reference", "pitch.practice", "notes.reference", "notes.practice")` | `__init__.py` L162–L167 |
| `ALGORITHMS[1].required_ports` | `("pcm.mapped.reference", "pcm.mapped.practice", "notes.reference", "notes.practice")` | `__init__.py` L174–L179 |
| `ALGORITHMS[2].required_ports` | `("rms.reference", "rms.practice", "notes.reference", "notes.practice")` | `__init__.py` L186–L191 |
| `label` | `"音准"` / `"节奏"` / `"力度"` | `__init__.py` L169 / L181 / L193 |
| `PAYLOAD_SCHEMAS["pitch"]` | `("per_note_cents", "median_abs_cents", "off_pitch_ratio", "n_notes_used", "sample_rate")` | `__init__.py` L248–L254 |
| `PAYLOAD_SCHEMAS["timing"]` | `("per_note_onset_ms", "median_onset_ms", "spread_ms", "early_ratio", "late_ratio", "on_time_ratio", "n_notes_used", "n_unpaired")` | `__init__.py` L255–L264 |
| `PAYLOAD_SCHEMAS["dynamics"]` | `("per_note_delta_db", "median_db", "spread_db", "n_notes_used", "n_unpaired")` | `__init__.py` L265–L271 |
| 检查编号 | `C1`…`C7`，按此顺序求值，首个违反即抛 | `assert_registry_integrity` docstring |
| 异常类型 | 内置 `RuntimeError` | 本文件 §4.4 冻结 |
| 消息前缀 | `REGISTRY_INTEGRITY:<C1..C7>: ` | 本文件 §4.4 冻结 |
| 成对后缀字面量 | `".reference"` / `".practice"` | 本文件 §4.4 C6 冻结 |
| `entry` 参数个数 | 恰为 `1`（`POSITIONAL_ONLY` 或 `POSITIONAL_OR_KEYWORD`） | 本文件 §4.4 C5 冻结 |
| 已知缺口编号 | `GAP-200-1`（pitch 缺 `n_unpaired`，未配对音无处报告，不自行修） | 本文件 §4.3 |
| 允许的标准库 import | `__future__` / `dataclasses` / `typing` / `inspect` | 本文件 §3 |
| 允许的包内 import | `..contract` / `..profile` / `.`（`dynamics`、`pitch`、`timing`） | 本文件 §3 |
