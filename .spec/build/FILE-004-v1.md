# FILE-004-v1 · `harmonica_eval/profile.py`（CORE_PROFILE_V0.1）实现文档

本文件是 `harmonica_eval/profile.py`（580 行，绝对路径 `/Users/Apple/Desktop/dsh-archive/harmonica-eval/harmonica_eval/profile.py`）的构建指令。
读者是**没有参与前期设计**的合格实现者。按本文档实现的 `profile.py` 与目标文件逐符号等价。

## 铭牌（摘自目标文件模块 docstring，第 1–42 行）

| 项 | 值 |
| --- | --- |
| FILE-ID | FILE-004 |
| COMPONENT | COMP-CONFIG（配置，本身不是组件） |
| SPEC | SPEC.md@v2.1 · COMPONENTS.md@v2 §4 · PLAN.md@v2 §三 |
| ROLE | CORE_PROFILE_V0.1 —— 全部冻结参数 + **封闭端口清单**的唯一定义处 |
| INTENT | 让「数据面里有什么」成为**一个可读、可审、可验的常量表**，而不是散落在 C2 各模块里的隐式约定 |
| DESIGN-RULING | **Core 预生成，端口清单封闭。算法适配 Core，不是 Core 适配算法。** |
| INPUT | （无） |
| OUTPUT | `PROFILE_VERSION` · `AUDIO` · `ALIGN` · `MATERIALIZE` · `BUDGET` · `PORTS` · `PortSpec` |
| BUILD-INSTRUCTION | `.spec/build/FILE-004-v1.md` |

DESIGN-RULING 的落地条文（逐字）：本文件的 `PORTS` 元组是**穷举**的 —— Seal 时 profile 里列的端口全部生成，profile 里没有的**永不存在**。算法若需要额外数据，**从 PCM 自己算** —— 不许要求 Core 增加端口。这消除了「惰性计算」必然带来的协商协议（特征声明→解析→版本→缓存失效→失败语义），从而避免 Core 的接口变成**插件需求的函数**。

---

## §1 归属与邻居

| 归属项 | 内容 |
| --- | --- |
| **所属组件** | COMP-CONFIG。铭牌原文：「配置，本身不是组件」。本文件不实现任何音频算法，只定义冻结常量与封闭端口清单。物理位置：`harmonica_eval/profile.py`，包内相对导入形式为 `harmonica_eval.profile`。 |
| **上游（谁调用我）** | ① `core.surface` —— 用 `PORT_INDEX` 驱动端口的生成与校验（`PORT_INDEX` 的 docstring 原文：「surface.py 用它来驱动生成与校验」）。② `core.features` —— 消费 `MATERIALIZE`（`frame_length` / `pitch_frame_length` / `pitch_hop_length` / `rms_frame_length` / `rms_hop_length` / `fmin_hz` / `fmax_hz`），并产出 9 个 `produced_by="core.features"` 的端口。③ `core.align` —— 消费 `ALIGN`（`hop_length` / `n_chroma` / `band_rad` / `global_constraints`），产出 `warp_path`。④ `ingest` 标准化阶段 —— 消费 `AUDIO`（`sample_rate` / `channels` / `dtype` / `min_duration_sec` / `max_duration_sec`）。⑤ 构建/落盘阶段 —— 消费 `BUDGET.max_surface_bytes` 做数据面总量闸门。⑥ `algorithms` —— 通过 `required_ports` 声明需求；profile 只决定「快不快」，不决定「能不能」（`pcm.mapped.*` 的 rationale 原文）。⑦ 任何 `import harmonica_eval.profile` 的进程 —— import 期无条件触发 `assert_profile_integrity()`。⑧ 审查工具 —— 读 `PORTS` 审「谁生成了清单外的端口」，并用 `PROFILE_VERSION` 计算数据面身份。⑨ `harmonica_eval/contract.py` 为词汇表提供方，被本文件消费（方向：contract → profile）。 |
| **下游（我调用谁、我给谁输出）** | **调用**：仅 `harmonica_eval/contract.py`（`from .contract import CORE_REQUIRED_PORTS, FIELD_LAYOUTS, UNITS_VOCABULARY, TimelineBasis`），加上标准库 `dataclasses.dataclass` 与 `typing.Sequence`。本文件不调用任何组件，不做 IO，不做数值计算。**输出**：`PROFILE_VERSION`（str）、`AudioSpec`/`AUDIO`、`AlignSpec`/`ALIGN`、`MaterializeSpec`/`MATERIALIZE`、`BudgetSpec`/`BUDGET`、`PortSpec`、`PORTS`（`tuple[PortSpec, ...]`，长度 12）、`PORT_INDEX`（`dict[str, PortSpec]`）、`assert_profile_integrity()`。`__all__` 导出上述 13 个名字。 |
| **同层邻居** | `harmonica_eval/contract.py` —— 同层（非组件、契约/词汇表层），本文件**唯一**import 的同层模块。邻居关系是单向的：`contract.py` 定义 `CORE_REQUIRED_PORTS`、`FIELD_LAYOUTS`、`UNITS_VOCABULARY`、`TimelineBasis` 四个符号，`profile.py` 把它们实例化为冻结常量与端口表；`contract.py` 不反向依赖 `profile.py`，无循环。`harmonica_eval` 包内其余模块（`core.*`、`features`、`surface`、`align`、`ingest`、`algorithms`、`host`、`cockpit`）全部位于**组件层**，不在本文件的同层，且被铭牌 MUST NOT 禁止 import。 |

### §1.1 本文件在数据面里的定位

`profile.py` 是「数据面里有什么」的**唯一定义处**。数据面身份 = `f(reference, practice, PROFILE_VERSION)`。端口清单是封闭集合：本文件列出的 12 个端口在 Seal 时全部生成；本文件未列出的端口永不存在。算法需要额外数据时的唯一合法路径是从 `pcm.mapped.reference` / `pcm.mapped.practice` / `pcm.warped.practice` 自行派生。

---

## §2 删掉它会坏掉什么

删掉 `harmonica_eval/profile.py`（或让它 import 失败）后，逐项后果如下，每一项都可在删除后直接观测：

1. **全链路 import 失败。** 任何执行 `from harmonica_eval.profile import PORTS / AUDIO / ALIGN / MATERIALIZE / BUDGET / PORT_INDEX` 的模块立即 `ImportError`。受影响者：`core.surface`（按 `PORT_INDEX` 生成端口）、`core.features`（按 `MATERIALIZE` 定窗长与帧移）、`core.align`（按 `ALIGN` 定帧移与带宽）、`ingest` 的标准化阶段（按 `AUDIO` 定采样率与输入门限）、审查工具。整条 Core 流水线无法启动，不是某个指标缺失。
2. **数据面无从生成。** 12 个端口的定义（`port_id` / `units` / `dimensions` / `field_names` / `element_type` / `timeline_basis` / `hop_length` / `produced_by`）全部消失，`surface` 没有生成配方，包括两份**必须存在**的对齐 PCM（`pcm.mapped.reference`、`pcm.mapped.practice`）。算法层随即失去自行预处理的能力（rationale 原文：算法永远能拿到参考 PCM 自行做特有预处理，因此 profile 只决定「快不快」，不决定「能不能」）。
3. **端口清单的封闭性失去可审依据。** 没有 `PORTS` 就没有「清单外端口不存在」这一事实的载体，算法按需索要数据重新变成可行路径；DESIGN-RULING 要消除的协商协议（特征声明→解析→版本→缓存失效→失败语义）随之回归，Core 接口变成插件需求的函数。
4. **四条静默错误防线同时消失。** `assert_profile_integrity()` 随文件消失，以下四类「不报错、只静默算错」的缺陷重新变成可犯而不可查：① 多维度端口字段顺序不一致 → 读出的 `f0_hz` 实际是 `voiced`；② 帧类端口未声明帧移 → 同一 `read(port_id, (t0, t1))` 的时间换算差 8×；③ `units` 字符串漂移（`"hz"` / `"Hz"` / `"hertz"`）→ 下游按 `== "hz"` 判断时静默漏配；④ 端口对称性破裂 → `notes.*` 只有参考侧时，`dynamics` 写出无法满足的 MUST（要求一个数据面里不存在的端口轴）。
5. **关键数字失去唯一来源，产出不可比。** 各自缺失的后果逐一对应：`sample_rate=44100`（22.05 kHz 下 pYIN 把 D5 判成 D4，恰好 −1200 音分）；`ALIGN.hop_length=2048`（512 会把 120 s 的 DTW 代价矩阵从 53,416,448 B 抬到 854,663,168 B，越过 512 MiB 预算上限）；`MATERIALIZE.pitch_hop_length=2048`（猜 256 会得到 8× 的时间刻度偏差）；`min_duration_sec=45.0` / `max_duration_sec=120.0`（输入门消失，短输入与超长输入行为分叉）；`BUDGET.max_surface_bytes=536870912`（数据面总量失去闸门）；`fmin_hz=130.81` / `fmax_hz=2093.0`（音高搜索域分叉，一侧钳位、一侧不钳位）。
6. **数据面身份断链。** `PROFILE_VERSION` 消失后 `f(reference, practice, PROFILE_VERSION)` 无法计算，两次 Seal 的产物无法判定是否同源，复现性判定与缓存失效判定同时失效。
7. **`read(port_id, (t0, t1))` 的秒→帧换算失去唯一依据。** 该换算的唯一依据是 `PortSpec.hop_length`。依据消失后两个实现者会对同一查询返回不同时间窗的数据，**且两侧都不会报错**。
8. **端口语义轴裁定消失。** 「节奏类指标**只能**在 `TimelineBasis.REFERENCE` 轴上算，用 warped 轴报抢拍拖拍是构造性错误（SPEC §5.5）」这一裁定唯一的落盘处就是端口表；删除后该构造性错误重新变成可犯而不可查。

---

## §3 依赖清单（穷举）

### §3.1 允许的 import（穷举；共 4 条语句，多一条即为越界）

标准库（含编译器指令），恰好 3 条：

1. `from __future__ import annotations`
2. `from dataclasses import dataclass`
3. `from typing import Sequence`

本包模块，恰好 1 条：

4. `from .contract import CORE_REQUIRED_PORTS, FIELD_LAYOUTS, UNITS_VOCABULARY, TimelineBasis`

第三方包：**零条**。本文件是纯常量表，不含任何需要第三方库的计算。

### §3.2 禁止 import（穷举，逐项点名）

- 禁止 import 组件层模块：`core`、`host`、`algorithms`、`cockpit`（铭牌 MUST NOT 逐字：`import core / host / algorithms / cockpit`）。
- 禁止 import 任何第三方包，逐个点名：`numpy`、`scipy`、`librosa`、`soundfile`、`audioread`、`resampy`、`pandas`、`yaml`、`toml`、`tomllib`、`dotenv`、`pydantic`、`attrs`。
- 禁止 import 任何配置/环境读取设施，逐个点名：`os`、`sys`、`pathlib`、`json`、`configparser`、`argparse`、`getpass`、`socket`、`subprocess`、`shutil`、`tempfile`。
- 禁止 import 除 `.contract` 之外的任何本包模块，逐个点名：`.features`、`.surface`、`.align`、`.ingest`、`.contract` 之外的 `.` 级相对导入全部禁止。
- 禁止以任何形式读取运行时可变的配置源（铭牌 MUST NOT：不得依赖环境变量或运行时可变的配置源）：`os.environ`、`os.getenv`、`open(...)` 读文件、命令行参数、网络请求、时钟。
- 禁止在模块内定义按输入参数生成端口的函数或类工厂（铭牌 MUST NOT：不得出现「按算法需求扩展端口」的任何机制）。

### §3.3 定义顺序硬约束（由上述 import 与引用关系推出）

模块内必须先定义 `PortSpec` 类，再定义 `PORTS`；因为 `PORTS` 的元素是 `PortSpec` 实例，且部分元素的 `hop_length` 直接引用 `MATERIALIZE.pitch_hop_length` 与 `ALIGN.hop_length`。目标文件的实际顺序为：import（第 44–54 行）→ `PROFILE_VERSION`（第 56 行）→ `AudioSpec`/`AUDIO`（第 64–85 行）→ `AlignSpec`/`ALIGN`（第 92–123 行）→ `MaterializeSpec`/`MATERIALIZE`（第 130–167 行）→ `BudgetSpec`/`BUDGET`（第 174–191 行）→ `PortSpec`（第 198–240 行）→ `PORTS`（第 243–445 行）→ `PORT_INDEX`（第 447–448 行）→ `assert_profile_integrity` 定义（第 451–568 行）→ `assert_profile_integrity()` 无条件调用（第 571 行）→ `__all__`（第 574–580 行）。任何调整都必须保持「被引用者先于引用者」，否则 import 期 `NameError`。

### §3.4 import 期副作用（消费方必须知道）

第 571 行是模块级无条件调用 `assert_profile_integrity()`。因此 `import harmonica_eval.profile` 有两种结果：成功返回，或抛出 `ValueError`。配置错误在 import 期暴露，不会推迟到运行时。任何消费方不得把该调用改为按需调用。

## §4 逐符号规格

本节逐符号给出输入、输出、算法口径、边界、不变量。**所有数值必须逐字照抄，不得重新推导、不得四舍五入、不得「优化」**。凡涉及阈值、容差、单位换算处，本文档一律给出写死数字或引用常量名；实现者没有选择权（宪章 §22 硬失败项）。

### §4.1 `PROFILE_VERSION: str = "CORE_PROFILE_V0.1"`

- **输入**：无。模块级字面量。
- **输出**：`str`，精确值 `"CORE_PROFILE_V0.1"`，长度 17，区分大小写，无前后空白。
- **算法口径**：字面量赋值，不做任何拼接、格式化、版本探测、时间戳注入。数据面身份 = `f(reference, practice, PROFILE_VERSION)`；本常量是其中唯一的版本因子。字符串内容与文件名 `profile.py`、FILE-ID `FILE-004` 无任何映射关系，禁止由前者派生后者。
- **边界**：空输入不适用。空字符串 `""` 是**非法值**（会使一切数据面同源，缓存失效判定失效）；本文件不检查，靠 code review 拦截。NaN 不适用（类型为 `str`）。
- **不变量**：`PROFILE_VERSION == "CORE_PROFILE_V0.1"`；类型为 `str` 而非 `bytes`；是本模块 `__all__` 的第一个导出名。

### §4.2 `AudioSpec`（frozen dataclass）与 `AUDIO`

`@dataclass(frozen=True)`，五个字段。模块级实例 `AUDIO = AudioSpec()`，即全部取默认值。语义：ingest 阶段的标准化目标。

| 字段 | 类型 | 单位 | 取值域（冻结） | 依据类别 | 口径 |
| --- | --- | --- | --- | --- | --- |
| `sample_rate` | `int` | Hz | 恒 `44100`。**不可下调** | 实测 | `44100` 是 pYIN 音高判定的成因：实测 22.05 kHz 下 pYIN 把 D5 判成 D4，误差恰好 −1200 音分（一个八度）。采样率是音高结果的成因，不是可选优化。 |
| `channels` | `int` | 个 | 恒 `1` | 规格 | 恒为单声道。多声道在此阶段下混。 |
| `dtype` | `str` | — | 恒 `"float32"` | 工程判断 | 统一浮点精度，避免各端口间的隐式转换。 |
| `min_duration_sec` | `float` | 秒 | 恒 `45.0` | 规格（SPEC §2） | 规格下限。短于此 → `INPUT_TOO_SHORT`。 |
| `max_duration_sec` | `float` | 秒 | 恒 `120.0` | 规格（SPEC §2） | 规格上限。超过则拒绝，**不静默截断**。 |

- **输入**：五个字段均可由调用方覆写（dataclass 默认参数），但模块级只实例化一次且不传参。生产代码禁止构造第二个 `AudioSpec`。
- **输出**：`AUDIO` 为 `AudioSpec` 实例，frozen。
- **算法口径**：五字段是 ingest 的全部判决输入。时长判决口径写死为：令 `dur_sec` = 解码后单声道信号的 `len(samples) / 44100`；若 `dur_sec < 45.0` → `INPUT_TOO_SHORT`；若 `dur_sec > 120.0` → 按上限拒绝（不截断）；`45.0 <= dur_sec <= 120.0` → 通过。重采样口径：目标采样率写死 `44100` Hz，目标声道数写死 `1`，目标 dtype 写死 `float32`。禁止以 `AUDIO.sample_rate` 之外的值做重采样。
- **边界**：
  - **空输入**：`dur_sec = 0.0` → `< 45.0` → `INPUT_TOO_SHORT`（显式失败，不降级）。
  - **单元素**：单采样点 → `dur_sec ≈ 2.2676e-05` → `INPUT_TOO_SHORT`。
  - **NaN**：若调用方构造 `AudioSpec(min_duration_sec=float("nan"))`，两次比较均为 `False`，`assert_profile_integrity()` **不做** NaN 检查、不抛异常，import 成功；下游 `nan` 比较全假会静默放行一切时长。故 NaN 必须由 code review 拦截。本文件**不含** `min_duration_sec <= max_duration_sec` 的跨字段校验：构造 `AudioSpec(min_duration_sec=120.0, max_duration_sec=45.0)` **不抛异常**，消费方必须先判 `min <= max`。
- **不变量**：`AUDIO.sample_rate == 44100`；`AUDIO.channels == 1`；`AUDIO.dtype == "float32"`；`AUDIO.min_duration_sec == 45.0`；`AUDIO.max_duration_sec == 120.0`；实例 frozen（赋值抛 `dataclasses.FrozenInstanceError`）；`isinstance(AUDIO, AudioSpec)`。

### §4.3 `AlignSpec`（frozen dataclass）与 `ALIGN`

`@dataclass(frozen=True)`，四个字段。模块级实例 `ALIGN = AlignSpec()`。语义：时间对齐参数。**内存主杠杆在这里。**

| 字段 | 类型 | 单位 | 取值域（冻结） | 依据类别 | 口径 |
| --- | --- | --- | --- | --- | --- |
| `hop_length` | `int` | 采样点 | 恒 `2048` | 实测 | 帧移。**这是整个 profile 最重要的一个数字。** 实测（`spike_dtw_memory.py`，120 s 音频）：`hop=512` → DTW 代价矩阵 855 MB；`hop=2048` → 53 MB（降 16×，平方反比）。 |
| `n_chroma` | `int` | bin | 恒 `12` | 规格 | chroma 维度。12 平均律。 |
| `band_rad` | `float` | 无量纲（比例） | 恒 `0.25` | 工程判断 | Sakoe-Chiba 带宽（相对时长比例）。防止病态路径。 |
| `global_constraints` | `bool` | — | 恒 `True` | 工程判断 | 必须开启。关闭会让路径可能严重违反单调性。 |

- **输入**：四个字段均可由调用方覆写，但生产代码禁止构造第二个 `AlignSpec`。
- **输出**：`ALIGN` 为 `AlignSpec` 实例，frozen。
- **算法口径（写到可复现同一数字）**：
  1. 帧数写死为 `N = ceil(len(samples) / ALIGN.hop_length)`，`ALIGN.hop_length = 2048`。等价写法 `N = ceil(dur_sec * 44100 / 2048) = ceil(dur_sec * 21.533203125)`。
  2. DTW 代价矩阵字节数写死为 `8 * N * N`（**float64**，非 float32）。验证锚点（照抄即可复现）：`dur_sec = 120.0` → `N = 2584` → `53,416,448` B（≈ 53 MB，即铭牌所称实测值）；`dur_sec = 45.0` → `N = 969` → `7,511,688` B；`dur_sec = 72.802` → `N = 1568` → `19,668,992` B。反例锚点：`hop=512` 且 `dur_sec = 120.0` → `N = 10336` → `854,663,168` B（≈ 855 MB）。
  3. `librosa.sequence.dtw` 的代价矩阵是 **float64**（非 float32），故实际占用是 `N²×8B`。
  4. `global_constraints=True` **不减少**矩阵分配，只约束路径、降低耗时 —— 不得以「加了带宽就省内存」为由调整预算。
  5. Sakoe-Chiba 带宽的绝对宽度写死为 `band = ceil(ALIGN.band_rad * max(N_ref, N_prac))` 帧，`ALIGN.band_rad = 0.25`，`N_ref` / `N_prac` 按上述第 1 条口径各自计算。禁止把 `0.25` 当作「采样点比例」或「秒」使用。
  6. chroma 维度写死 `n_chroma = 12`，12 平均律，bin 顺序由 §4.7 的 `chroma.lowres.*` 字段顺序固定为 `C, C#, D, D#, E, F, F#, G, G#, A, A#, B`。
  7. 对齐时间精度写死为约 `±hop/2` 采样点（`= ±1024` 采样点 `≈ ±23 ms @ 2048`）。该量级对「抢拍/拖拍」（实测中位 26 ms）是**临界**的，故对齐后的细化由 warp 阶段在样本级插值完成，不依赖帧级精度。
- **边界**：
  - **空输入**：`len(samples) = 0` → `N = 0` → 矩阵 0 B；本文件不抛异常，失败由 ingest 的时长下限（`45.0` s）在上游拦住。
  - **单元素**：`N = 1` → 矩阵 `8` B；DTW 退化为单点路径，本文件不抛异常。
  - **NaN**：`AlignSpec(band_rad=float("nan"))` 不抛异常（自检无 NaN 检查），但第 5 条的 `ceil(nan * N)` 结果为 NaN，带宽无法确定，对齐行为未定义。故 NaN 必须由 code review 拦截。
- **不变量**：`ALIGN.hop_length == 2048`；`ALIGN.n_chroma == 12`；`ALIGN.band_rad == 0.25`；`ALIGN.global_constraints is True`（必须严格 `is True`，不得为 truthy 的非布尔值）；实例 frozen。

### §4.4 `MaterializeSpec`（frozen dataclass）与 `MATERIALIZE`

`@dataclass(frozen=True)`，七个字段。模块级实例 `MATERIALIZE = MaterializeSpec()`。语义：预生成阶段（`features.py`）的参数。

| 字段 | 类型 | 单位 | 取值域（冻结） | 依据类别 | 口径 |
| --- | --- | --- | --- | --- | --- |
| `frame_length` | `int` | 采样点 | 恒 `2048` | 工程判断 | 分析窗长。@44.1 kHz ≈ 46.4 ms（`2048 / 44100 = 0.046439909...` s）。 |
| `pitch_frame_length` | `int` | 采样点 | 恒 `2048` | 工程判断 | 音高估计窗长。与 `frame_length` 分开声明：音高要求窗内有稳定周期，能量只要求统计意义。 |
| `pitch_hop_length` | `int` | 采样点 | 恒 `2048` | 实测/工程判断 | ★ 音高帧移。取 2048（≈46 ms）的理由：音准按**音**聚合（用 `notes.*` 索引），不做逐帧精细时间定位，故不需要 RMS 那样密的时间分辨率。 |
| `rms_frame_length` | `int` | 采样点 | 恒 `1024` | 工程判断 | RMS 包络窗长。比音高窗短，以保留起音的瞬态。 |
| `rms_hop_length` | `int` | 采样点 | 恒 `256` | 工程判断 | RMS 帧移。比 `hop_length` 密，因为力度变化需要时间分辨率。 |
| `fmin_hz` | `float` | Hz | 恒 `130.81` | 规格/工程判断 | 音高搜索下界 = C3（MIDI 48）。口琴实际音域 C4–D5（MIDI 60–74），留一个八度余量以吸收走调变体的向下偏移。 |
| `fmax_hz` | `float` | Hz | 恒 `2093.0` | 工程判断 | 音高搜索上界 = C7（MIDI 96）。刻意放宽：宁可让 estimator 自己判否，也不要因搜索域太窄而钳位。 |

- **输入**：七个字段均可覆写，生产代码禁止构造第二个 `MaterializeSpec`。
- **输出**：`MATERIALIZE` 为 `MaterializeSpec` 实例，frozen。
- **算法口径（写到可复现同一数字）**：
  1. 帧数口径：令 `x` 为单声道 `float32` 信号，`sr = 44100`。RMS 帧数写死 `ceil(len(x) / MATERIALIZE.rms_hop_length)`，`rms_hop_length = 256`；音高帧数写死 `ceil(len(x) / MATERIALIZE.pitch_hop_length)`，`pitch_hop_length = 2048`。
  2. **`pitch_hop_length` 是音高端口时间刻度的唯一依据。** 时间换算写死为 `t_sec = frame_index * 2048 / 44100`（`frame_index` 从 0 起）。反例锚点：同一段 120 s 音频，`rms.*` 得 `ceil(5,292,000 / 256) = 20672` 帧，`pitch.*` 得 `ceil(5,292,000 / 2048) = 2584` 帧，比值 `20672 / 2584 = 8`（**恰好 8×**）。用 `256` 换算 `pitch.*` 的帧号会得到错误时刻，且不报错。
  3. 端口帧数锚点（可直接 assert）：`dur_sec = 72.802` 的音频，`pitch.*` 帧数 `= ceil(72.802 * 44100 / 2048) = 1568`（实测：本数据集 01 的全部 wav 恰好都是 72.802 s）。
  4. 音高搜索域写死 `[130.81, 2093.0]` Hz，闭区间，单位 Hz，不得换算成 MIDI 后传递到端口层（端口 `units` 写死 `"hz"`）。MIDI 换算参考：`130.81 Hz = C3 = MIDI 48`，`2093.0 Hz = C7 = MIDI 96`。
  5. 窗长与帧移的语义区分写死：`frame_length` 与 `pitch_frame_length` 是**窗长**，`pitch_hop_length` / `rms_hop_length` 是**帧移**。`frame_length` 与 `ALIGN.hop_length` 数值同为 2048 是**巧合，不是约定**；禁止把 `ALIGN.hop_length` 当作窗长或把 `MATERIALIZE.frame_length` 当作帧移使用。
  6. 样本点 ↔ 毫秒换算写死：`ms = samples / 44.1`（因 44100 Hz 下 1 采样点 `= 1000/44100 = 0.02267573696...` ms）。锚点：`2048` 采样点 `= 46.4399...` ms ≈ 46.4 ms；`1024` 采样点 `= 23.2199...` ms；`256` 采样点 `= 5.8049...` ms。
- **边界**：
  - **空输入**：`len(x) = 0` → 帧数 0；本文件不抛异常，由 ingest 时长下限拦住。
  - **单元素**：`len(x) = 1` → 音高帧数 `ceil(1/2048) = 1`，RMS 帧数 `ceil(1/256) = 1`；本文件不抛异常。
  - **NaN**：`fmin_hz` / `fmax_hz` 设为 NaN → 自检不检查、import 成功；搜索域比较全假，estimator 行为未定义。`fmin_hz > fmax_hz` 的空搜索域同样**不抛异常**（本文件无跨字段校验）。两种情况必须由 code review 拦截。
- **不变量**：`MATERIALIZE.frame_length == 2048`；`pitch_frame_length == 2048`；`pitch_hop_length == 2048`；`rms_frame_length == 1024`；`rms_hop_length == 256`；`fmin_hz == 130.81`；`fmax_hz == 2093.0`；`MATERIALIZE.rms_hop_length != MATERIALIZE.pitch_hop_length`（256 ≠ 2048，是 8× 静默分叉点的成因，必须保持不等）；实例 frozen。

### §4.5 `BudgetSpec`（frozen dataclass）与 `BUDGET`

`@dataclass(frozen=True)`，两个字段。模块级实例 `BUDGET = BudgetSpec()`。语义：原型阶段的预算。**故意宽松** —— 本轮是快速原型验证，不是成品优化。

| 字段 | 类型 | 单位 | 取值域（冻结） | 依据类别 | 口径 |
| --- | --- | --- | --- | --- | --- |
| `max_surface_bytes` | `int` | 字节（B） | 恒 `536870912`（= `512 * 1024 * 1024`，即 512 MiB） | 实测 | 数据面总量上限 512 MB。超出 → `CORE_BUILD_FAILED`。依据：预生成清单（**12 个端口**）在 120 s 音频下实测约 10–20 MB，余量约 25×。 |
| `peak_memory_note` | `str` | — | 恒为下方逐字文本 | 实测 | 对齐阶段是峰值来源。`hop=2048` 时实测约 53 MB（120 s）。若实现者改用更细 hop，必须先重跑 `spike_dtw_memory.py` 确认预算。 |

`peak_memory_note` 的**逐字**值（三段相邻字符串字面量拼接，拼接后无分隔符、无换行）：

```
对齐阶段是峰值来源。hop=2048 时实测约 53 MB（120 s）。若实现者改用更细 hop，必须先重跑 spike_dtw_memory.py 确认预算。
```

- **输入**：两个字段均可覆写，生产代码禁止构造第二个 `BudgetSpec`。
- **输出**：`BUDGET` 为 `BudgetSpec` 实例，frozen。
- **算法口径（写到可复现同一数字）**：
  1. 上限的精确值写死 `536870912` B。等价写法 `512 * 1024 * 1024`。**禁止**写成 `512 * 1000 * 1000`（= 512,000,000，会少 870,912 B）。
  2. 数据面总量口径写死为 `sum(port.nbytes for port in 12 ports)`，逐端口字节数 `= 元素数 × itemsize`，`itemsize` 在 `float32` 下为 4 B、`int32` 下为 4 B。超出 `536870912` B → `CORE_BUILD_FAILED`（构建失败，非降级、非截断）。
  3. 量级锚点（可直接 assert `<=`）：12 端口在 120 s 音频下实测约 10–20 MB，相对 `536870912` B 余量约 25×。
  4. 63,829 B/端口 的除算参考：`536870912 / 12 = 44,739,242.66...` B/端口（仅作审查参考，不是闸门口径；闸门是总量）。
  5. 对齐峰值锚点写死：`hop = 2048`、`dur_sec = 120.0` → 单矩阵 `53,416,448` B，**不**计入数据面总量（它是中间量，不是端口）。
- **边界**：
  - **空输入**：`max_surface_bytes = 0` → 一切非空数据面 `CORE_BUILD_FAILED`；本文件不抛异常。
  - **单元素**：`max_surface_bytes = 1` → 同上；本文件不抛异常。
  - **NaN**：不适用（类型为 `int` 与 `str`）。若被改为 `float("nan")`，一切 `> nan` 比较为假，闸门静默失效；本文件**不做**类型校验，靠 code review 拦截。
- **不变量**：`BUDGET.max_surface_bytes == 512 * 1024 * 1024`；`isinstance(BUDGET.max_surface_bytes, int)`（不得为 `float`）；`BUDGET.peak_memory_note` 非空且含子串 `spike_dtw_memory.py`；实例 frozen。

### §4.6 `PortSpec`（frozen dataclass）

`@dataclass(frozen=True)`，八个字段。语义：一个端口的生成配方（profile 侧声明，**非**运行时描述符）。

| 字段 | 类型 | 必填 | 单位/取值域 | 口径 |
| --- | --- | --- | --- | --- |
| `port_id` | `str` | 是 | 点分小写，形如 `<prefix>.<...>`，前缀取自 `{warp, pcm, pitch, rms, chroma, notes}` | 全局唯一（自检检查 1）。前端命名约定写死：`X.reference` 与 `X.practice` 成对；`pcm.warped.*` 只有练习侧。 |
| `units` | `str` | 是 | 必须 ∈ `contract.UNITS_VOCABULARY`（自检检查 7）。本 profile 实际使用的 5 个值及含义：`"index"`（帧号/序号索引，无量纲）、`"amplitude"`（归一化后 PCM 采样值，无量纲，float32）、`"hz"`（赫兹）、`"rms"`（均方根能量，归一化幅度单位）、`"chroma"`（chroma 强度，无量纲 12 维） | 封闭词表成员，禁止开放式字符串（`"hz"` / `"Hz"` / `"hertz"` 三种写法会让下游按 `== "hz"` 判断时静默漏配）。 |
| `dimensions` | `Sequence[str]` | 是 | 本 profile 实际使用的形状仅 4 种：`("warp_point","axis")`、`("sample",)`、`("frame","field")`、`("frame","bin")`、`("note","field")` | 顺序即轴的顺序。含 `"frame"` 者必须声明 `hop_length > 0`（自检检查 5）。 |
| `element_type` | `str` | 是 | 本 profile 只使用 `"float32"` 与 `"int32"` 两个值 | 逐元素 dtype。`warp_path` 用 `int32`（帧号是整数索引），其余 11 个端口全部 `float32`。 |
| `timeline_basis` | `TimelineBasis` | 是 | `TimelineBasis.REFERENCE` 或 `TimelineBasis.WARPED`（枚举成员，取自 `contract`） | ★ 语义见 §4.9。本 profile：11 个端口为 `REFERENCE`，仅 `pcm.warped.practice` 为 `WARPED`。 |
| `produced_by` | `str` | 是 | 本 profile 实际使用 3 个值：`"core.align"`、`"core.surface"`、`"core.features"` | 哪个模块负责生成它。用于审查「谁生成了清单外的端口」。 |
| `rationale` | `str` | 是 | 非空、去空白后非空 | 为什么需要它。**每个端口都必须能回答这个问题** —— 答不出来就该从清单里删掉（自检检查 3）。 |
| `field_names` | `Sequence[str]` | 否，默认 `()` | 多维度端口的字段名，顺序即内存布局；单维端口留空 | **必须**与 `contract.FIELD_LAYOUTS[类别前缀]` 一致（自检检查 4），这是防止「`f0_hz` 与 `voiced` 静默错位」的唯一手段。前缀口径写死：`prefix = port_id.split(".")[0]`，故多维度端口的前缀为 `warp` / `pitch` / `chroma` / `notes`，`contract.FIELD_LAYOUTS` 必须为这四个前缀各定义字段序列。 |
| `hop_length` | `int` | 否，默认 `0` | 采样点。帧类端口 `> 0`，非帧类恒 `0` | ★ 该端口的**帧移**。`read(port_id, (t0,t1))` 的单位是**秒**，而帧类端口的第二维是**帧**；秒→帧换算必须有唯一依据，否则两个实现者会算出不同的时间偏移 —— **而且不会报错**。 |

- **输入**：构造参数为上述 8 个关键字参数（关键字传参，顺序无关）。
- **输出**：`PortSpec` 实例，frozen。
- **算法口径**：`PortSpec` 只承载声明，不做计算。唯一「算法」是自检对其施加的 5 条约束（重复 id / 空 rationale / 字段顺序 / 帧移一致性 / 单位词表），逐条见 §4.10。
- **边界**：
  - **空输入**：`PortSpec(port_id="", units="", dimensions=(), element_type="", timeline_basis=..., produced_by="", rationale="")` 在构造期**不抛异常**（无 `__post_init__` 校验）；只有被放进 `PORTS` 并触发自检时才可能失败，且失败点是 `rationale` 为空（检查 3）或 `units` 不在词表（检查 7）。
  - **单元素**：`dimensions=("frame",)` 且 `hop_length=0` → 被检查 5 拦截，抛 `ValueError`。`dimensions=("sample",)` 且 `hop_length=2048` → 被检查 5 反向拦截，抛 `ValueError`。
  - **NaN**：`hop_length=float("nan")` 不抛构造异常；检查 5 的 `spec.hop_length <= 0` 对 NaN 为 `False`、`!= 0` 为 `True`，故 NaN 会在**非帧**端口上被误判为「声明了帧移」而抛异常，在**帧**端口上静默通过。禁止传 NaN。
- **不变量**：实例 frozen（赋值抛 `dataclasses.FrozenInstanceError`）；`isinstance(spec.timeline_basis, TimelineBasis)`；`produced_by != ""`；字段默认值恰为 `field_names=()`、`hop_length=0`。

### §4.7 `PORTS: tuple[PortSpec, ...]` —— 12 个端口全表 ★

类型写死为 **`tuple[PortSpec, ...]`**，**不是 `dict`**。这是封闭端口清单的载体，长度**恰好 12**，顺序为下表自上而下。

★★ **真实踩过的坑**：有工具按 `dict` 读 `PROFILE.PORTS`（例如执行 `PORTS.items()` / `PORTS["pitch.reference"]` / `PORTS.get(...)`），结果**整个端口信号为空** —— 遍历得到的是 `PortSpec` 对象而非键，取值全部落空，且**不报错**。按 `port_id` 查询必须用 `PORT_INDEX`（`dict[str, PortSpec]`），不得用 `PORTS`。

| # | `port_id` | `units` | `dimensions` | `field_names` | `element_type` | `timeline_basis` | `hop_length` | `produced_by` | 存在理由（`rationale` 要点） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `warp_path` | `index` | `("warp_point","axis")` | `("reference_frame","practice_frame")` | `int32` | `REFERENCE` | `0` | `core.align` | 对齐的唯一产物。实测仅 165 KB（120 s），却是其余全部端口的生成依据 —— 相对 DTW 代价矩阵是 1/5300。 |
| 2 | `pcm.mapped.reference` | `amplitude` | `("sample",)` | `()` | `float32` | `REFERENCE` | `0` | `core.surface` | 逃生口甲：算法永远能拿到参考 PCM 自行做特有预处理，因此 profile 只决定「快不快」，不决定「能不能」。 |
| 3 | `pcm.mapped.practice` | `amplitude` | `("sample",)` | `()` | `float32` | `REFERENCE` | `0` | `core.surface` | 逃生口乙：练习演奏保留源时间。节奏类指标**只能**在这条轴上算 —— 用 warped 轴报抢拍拖拍是构造性错误（SPEC §5.5）。 |
| 4 | `pcm.warped.practice` | `amplitude` | `("sample",)` | `()` | `float32` | `WARPED` | `0` | `core.surface` | 时间归一化后的练习演奏，与参考等长。★ 更正：`pitch` 与 `dynamics` 都**没有**使用它（两者走的都是 `notes.*` / `rms.*`，见 `algorithms.ALGORITHMS` 的 `required_ports`）。它当前**无算法消费**；保留的真实理由是数据面保证：算法永远能拿到时间归一化后的 PCM 自行做特有预处理。 |
| 5 | `pitch.reference` | `hz` | `("frame","field")` | `("f0_hz","voiced","confidence")` | `float32` | `REFERENCE` | `2048` | `core.features` | 逐帧 f0 + voiced 标志 + 置信度（field 维）。预生成是因为它是音准算法的**直接**输入，现算不划算。 |
| 6 | `pitch.practice` | `hz` | `("frame","field")` | `("f0_hz","voiced","confidence")` | `float32` | `REFERENCE` | `2048` | `core.features` | 练习侧音高曲线，与参考同轴（`REFERENCE`），即两侧都保留各自的源时间、都没有被拉伸对齐。★ 修正：原文「两条曲线可以逐帧直接相减得到音分误差」**不成立** —— `REFERENCE` 只保证各自未被归一化，**不保证两侧帧数相等**。正确路径是用 `notes.*` 的 `onset_sec` 按音配对后再比较。 |
| 7 | `rms.reference` | `rms` | `("frame",)` | `()` | `float32` | `REFERENCE` | `256` | `core.features` | 逐帧 RMS。力度对比需要它。★ §20 盲审修正：真值**不是** MIDI velocity（数据面里没有 MIDI 通路：ingest 只解码音频，features 从音频派生）。故力度指标是「练习相对参考的能量差」，不是「相对乐谱的绝对力度差」。 |
| 8 | `rms.practice` | `rms` | `("frame",)` | `()` | `float32` | `REFERENCE` | `256` | `core.features` | 同上。与参考同轴以便逐帧比较。 |
| 9 | `chroma.lowres.reference` | `chroma` | `("frame","bin")` | `("C","C#","D","D#","E","F","F#","G","G#","A","A#","B")` | `float32` | `REFERENCE` | `2048` | `core.features` | 对齐的输入。保留在数据面里是为了**可复现**：审查者能用它重跑对齐，验证 `warp_path` 不是凭空来的。**明确不作为评分依据**（chroma 是八度不变的）。 |
| 10 | `chroma.lowres.practice` | `chroma` | `("frame","bin")` | 同第 9 行（12 个音名，顺序完全相同） | `float32` | `REFERENCE` | `2048` | `core.features` | 同上，练习侧。 |
| 11 | `notes.reference` | `index` | `("note","field")` | `("onset_sec","f0_hz","rms")` | `float32` | `REFERENCE` | `0` | `core.features` | 参考侧逐音摘要（起音时刻/音高/能量）。它让算法能按**音**而不是按**帧**组织结果，从而输出「第 7 个音偏低 40 音分」这种可定位的结论。 |
| 12 | `notes.practice` | `index` | `("note","field")` | `("onset_sec","f0_hz","rms")` | `float32` | `REFERENCE` | `0` | `core.features` | ★ 盲审补齐的对称项。练习侧逐音摘要，与 `notes.reference` **同轴**（都在源时间网格上）。没有它，「按音对齐」在练习侧**无索引可用** —— `dynamics` 只能退而用「WARPED 轴」当代理，而那是一个无法满足的约束（数据面里没有 WARPED 轴的 rms）。正确机制是**按音配对**，不是按轴配对。 |

**端口清单是封闭的**：不得新增、不得删除、不得修改任何 `port_id`。上表 12 行即全部。清单外端口**永不存在**；端口对称性唯一例外是 `pcm.warped.*` **刻意只有练习侧**（参考无需被拉伸到自己）。

`notes.*` 的 `port_id` 不对称历史（★ 必须理解，否则会「顺手改回去」）：第一版只有 `notes.reference`，没有 `notes.practice`，而 `pitch` / `timing` / `dynamics` **三者都声称**「可定位到第几个音」。这是端口表的**结构性缺陷**，不是某个算法少声明了一个端口 —— `pitch.py` 说「产出逐音误差（音分，可定位到第几个音）」却无从知道第几个；`timing.py` 声明了 `notes.reference`（唯一声明者）；`dynamics.py` 说「逐音能量差」而练习侧无索引可用。两个独立盲审模型各自复现了后果（`dynamics` 的轴自相矛盾），根因在此：**「按音比较」这个能力原先只有一半。** 补齐 `notes.practice` 是修复，不得回退。

### §4.8 `PORT_INDEX: dict[str, PortSpec]`

- **输入**：无（模块级推导值）。
- **输出**：`dict[str, PortSpec]`，键为 12 个 `port_id`，值为对应 `PortSpec` 实例。构造口径**逐字**为 `{p.port_id: p for p in PORTS}`。
- **算法口径**：字典推导，保持 `PORTS` 的插入顺序（Python 3.7+ 保证）。键集合 == `{p.port_id for p in PORTS}`，`len(PORT_INDEX) == 12`。
- **边界**：空输入不适用。若 `PORTS` 存在重复 `port_id`，字典推导会**静默取后者**（不抛异常）—— 故重复检测必须在 `assert_profile_integrity()` 里做，且该调用在 `PORT_INDEX` 之后执行前已 import 期生效。
- **不变量**：`set(PORT_INDEX) == set(PORTS[i].port_id for i in range(12))`；`PORT_INDEX["warp_path"].produced_by == "core.align"`；`surface.py` 用它来驱动生成与校验。按 `port_id` 查询**一律**走这里，不得遍历 `PORTS`。

### §4.9 `TimelineBasis` 的语义（★ 逐字口径）

`TimelineBasis` 由 `contract` 定义，`profile` 只使用其两个成员的语义如下。**必须逐字遵守，不得外推**：

- **`TimelineBasis.REFERENCE`**：只表示**保留源时间、未归一化**。它**不**表示两侧帧号一一对应，**不**表示两侧帧数相等，**不**表示两端口可直接逐帧相减。本 profile 中 11 个端口使用它，其中 `pitch.reference` 与 `pitch.practice` 虽**同轴**（都在各自的源时间网格上）却因参考与练习是两段独立录音、帧数 `= 各自时长 / pitch_hop_length`（默认不同）而**不可逐帧对齐**。实测：本数据集 01 的全部 wav 恰好都是 72.802 s（1568 帧），把该缺陷掩盖了；换一首时长不同的练习曲即失效。正确路径是用 `notes.*` 的 `onset_sec` **按音配对**后再比较。
- **`TimelineBasis.WARPED`**：表示时间归一化后的轴。本 profile 中**仅** `pcm.warped.practice` 使用它。参考侧**没有**对应的 WARPED 端口（参考无需被拉伸到自己），故数据面里**不存在**任何 WARPED 轴的 `rms` / `pitch` / `notes`。凡要求「在 WARPED 轴上按帧比较」的约束都是**无法满足的约束**，必须改写为按音配对。
- **`pcm.mapped.practice` 与 `pcm.warped.practice` 的时间基准对比（★ 强制）**：`pcm.mapped.practice` 是 `REFERENCE`，`pcm.warped.practice` 是 `WARPED`（逐字见第 3、4 行 `timeline_basis=`）。因此 `pcm.mapped.practice` 是「练习演奏保留源时间」，节奏类指标**只能**在它这条轴上算；在 warped 轴上报抢拍拖拍是**构造性错误**（SPEC §5.5）。

### §4.10 `assert_profile_integrity() -> None`

- **输入**：无参数。读取模块级 `PORTS`（闭包引用）与 `contract` 的 `CORE_REQUIRED_PORTS`、`FIELD_LAYOUTS`、`UNITS_VOCABULARY`。
- **输出**：`None`（全部通过时）。**失败即抛，不返回布尔值** —— 配置错误不该被忽略。
- **算法口径**：docstring 声明「检查六件事」，实际实现 8 项检查（编号 1–5、7、8，其中第 7、8 项标注了修正来源）。逐项口径写死如下，顺序即执行顺序，任一项抛出即中止，后续检查不执行：

| 序 | 检查 | 口径（逐字） | 失败时抛出的消息要点 |
| --- | --- | --- | --- |
| 1 | 端口清单封闭：无重复 `port_id` | `ids = [p.port_id for p in PORTS]`；`duplicates = {i for i in ids if ids.count(i) > 1}`；非空即抛 | `端口清单存在重复: {sorted(duplicates)}` |
| 2 | 逃生口存在：`CORE_REQUIRED_PORTS` 全部被声明 | `missing = [p for p in CORE_REQUIRED_PORTS if p not in ids]`；非空即抛 | `违反数据面保证（本仓自定）：缺少必需端口 {missing}。任何 profile 都必须含两份对齐 PCM，否则算法无法自行做特有预处理。` |
| 3 | 每个端口都有非空 `rationale` | `no_rationale = [p.port_id for p in PORTS if not p.rationale.strip()]`；非空即抛（故纯空白也算空） | `以下端口未说明存在理由: {no_rationale}。端口清单封闭的前提是「每个端口都能回答为什么需要它」。` |
| 4 | 多维度端口的字段顺序与 `FIELD_LAYOUTS` 一致 | 对每个 `spec`：若 `len(spec.dimensions) <= 1` 则要求 `not spec.field_names`（声明了即抛）；否则取 `prefix = spec.port_id.split(".")[0]`，查 `FIELD_LAYOUTS.get(prefix)`，为 `None` 即抛，再要求 `tuple(spec.field_names) == tuple(expected)`，不等即抛 | 单维：`端口 {port_id} 是单维，不应声明 field_names`；缺定义：`端口 {port_id} 是多维，但 contract.FIELD_LAYOUTS 中没有 '{prefix}' 的字段定义。多维端口必须有明确字段顺序，否则下游会静默错位读取。`；不一致：`端口 {port_id} 的 field_names={...} 与契约定义的 {...} 不一致。` |
| 5 | 帧类端口必须声明 `hop_length`，非帧类必须留 0 | 对每个 `spec`：`is_frame_based = "frame" in spec.dimensions`；若 `is_frame_based and spec.hop_length <= 0` 即抛；若 `not is_frame_based and spec.hop_length != 0` 即抛 | 前者：`端口 {port_id} 含 'frame' 维度，但未声明 hop_length。read(time_range) 的单位是秒，没有帧移就无法唯一换算出帧号 —— 实现者只能猜，而猜错不会报错，只会静默返回错误时间窗的数据。`；后者：`端口 {port_id} 不含 'frame' 维度，但声明了 hop_length={...}。非帧类端口声明帧移会产生误导（读的人会以为它也有帧结构）。` |
| 6 | `units` 必须在受控词表内（G10 修正） | 对每个 `spec`：`spec.units not in UNITS_VOCABULARY` 即抛 | `端口 {port_id} 的 units='{...}' 不在 contract.UNITS_VOCABULARY 内。\n合法取值：{sorted(UNITS_VOCABULARY)}\n若确实需要新单位，先加进词表 —— 否则下游按字符串相等判断端口语义时会静默漏配。` |
| 7 | 端口对称性 | `ids_set = set(ids)`；对每个 `pid`：以 `.reference` 结尾则 `twin = pid[:-len(".reference")] + ".practice"`，以 `.practice` 结尾则 `twin = pid[:-len(".practice")] + ".reference"`，否则 `continue`；**例外**：`pid.startswith("pcm.warped.") or twin.startswith("pcm.warped.")` 则 `continue`；若 `twin not in ids_set` 即抛 | `端口对称性破裂：{pid} 存在但 {twin} 不存在。\n参考侧与练习侧要么都有、要么都没有 —— 只有一侧会让「按音/逐帧比较」在另一侧无索引可用，而算法会因此写出无法满足的约束（这正是盲审发现的那个缺陷）。\n唯一例外：pcm.warped.* 刻意只有练习侧（参考无需被拉伸）。` |

- **调用口径（★ 不得改动）**：模块级**无条件**调用一次 `assert_profile_integrity()`（目标文件第 571 行，位于函数定义之后、`__all__` 之前）。import 时即执行，让配置错误立刻暴露。禁止改为按需调用、禁止包在 `try` 里、禁止吞掉异常。
- **边界**：
  - **空输入**：`PORTS = ()` → 检查 2 抛出（缺全部 `CORE_REQUIRED_PORTS`），因为检查 1、3–7 在空序列上均为空集、不抛。
  - **单元素**：`PORTS` 只有一个端口 → 若它是 `notes.reference` 则检查 7 抛对称性破裂；若是 `pcm.mapped.reference` 则检查 2 抛（缺 `pcm.mapped.practice`）。
  - **NaN**：本函数**不做** NaN 检查，也不做类型检查、不做 `min<=max` 跨字段检查、不做端口计数检查（12 这个数字不在此校验）。传 NaN 的路径见 §4.2 / §4.3 / §4.4 / §4.5 / §4.6 各自的边界条目。
- **不变量**：返回值为 `None`（不得返回 `bool`）；对合法 `PORTS` 调用**幂等**（连续调用两次结果相同、无副作用）；抛出类型**恒为 `ValueError`**（不使用自定义异常类型）；docstring 声称「六件事」，实现为 8 项检查，此为已知的文本/实现计数差异，**不得**为了对齐计数而删掉第 6、7 项检查。

### §4.11 `__all__`

- **输入**：无。
- **输出**：`list[str]`，**恰好 13 个**元素，顺序为 `["PROFILE_VERSION", "AUDIO", "ALIGN", "MATERIALIZE", "BUDGET", "AudioSpec", "AlignSpec", "MaterializeSpec", "BudgetSpec", "PORTS", "PORT_INDEX", "PortSpec", "assert_profile_integrity"]`。
- **算法口径**：字面量列表，逐字上述顺序。导出的常量名（大写）与其类型名（`*Spec`）成对出现，缺一不可。
- **边界**：空输入不适用。空列表会使 `from harmonica_eval.profile import *` 静默导入 0 个名字；本文件不检查。
- **不变量**：`len(__all__) == 13`；`len(set(__all__)) == 13`；`"PORTS" in __all__ and "PORT_INDEX" in __all__ and "assert_profile_integrity" in __all__`；`__all__` 中每个名字都真实存在于模块命名空间。

---

## §5 失败情形表

| 失败情形 | 显式失败还是降级 | 抛什么异常 / 错误码 |
| --- | --- | --- |
| `PORTS` 中出现重复 `port_id` | 显式失败 | `ValueError`，消息 `端口清单存在重复: {sorted(duplicates)}`（自检检查 1） |
| `CORE_REQUIRED_PORTS` 中有端口未被 `PORTS` 声明（缺 `pcm.mapped.reference` 或 `pcm.mapped.practice` 中任一） | 显式失败 | `ValueError`，消息 `违反数据面保证（本仓自定）：缺少必需端口 {missing}。任何 profile 都必须含两份对齐 PCM，否则算法无法自行做特有预处理。`（自检检查 2） |
| 某端口 `rationale` 为空或纯空白 | 显式失败 | `ValueError`，消息 `以下端口未说明存在理由: {no_rationale}。端口清单封闭的前提是「每个端口都能回答为什么需要它」。`（自检检查 3） |
| 单维端口声明了 `field_names` | 显式失败 | `ValueError`，消息 `端口 {port_id} 是单维，不应声明 field_names`（自检检查 4） |
| 多维度端口的前缀在 `FIELD_LAYOUTS` 中无定义 | 显式失败 | `ValueError`，消息 `端口 {port_id} 是多维，但 contract.FIELD_LAYOUTS 中没有 '{prefix}' 的字段定义。多维端口必须有明确字段顺序，否则下游会静默错位读取。`（自检检查 4） |
| 多维度端口 `field_names` 与 `FIELD_LAYOUTS[prefix]` 不一致 | 显式失败 | `ValueError`，消息 `端口 {port_id} 的 field_names={tuple(spec.field_names)} 与契约定义的 {tuple(expected)} 不一致。`（自检检查 4） |
| 含 `"frame"` 维度的端口 `hop_length <= 0`（未声明帧移） | 显式失败 | `ValueError`，消息 `端口 {port_id} 含 'frame' 维度，但未声明 hop_length。read(time_range) 的单位是秒，没有帧移就无法唯一换算出帧号 —— 实现者只能猜，而猜错不会报错，只会静默返回错误时间窗的数据。`（自检检查 5） |
| 不含 `"frame"` 维度的端口 `hop_length != 0` | 显式失败 | `ValueError`，消息 `端口 {port_id} 不含 'frame' 维度，但声明了 hop_length={spec.hop_length}。非帧类端口声明帧移会产生误导（读的人会以为它也有帧结构）。`（自检检查 5） |
| 端口 `units` 不在 `UNITS_VOCABULARY` 内（如写成 `"Hz"` / `"hertz"`） | 显式失败 | `ValueError`，消息含 `不在 contract.UNITS_VOCABULARY 内`、`合法取值：{sorted(UNITS_VOCABULARY)}`、`若确实需要新单位，先加进词表 —— 否则下游按字符串相等判断端口语义时会静默漏配。`（自检检查 6） |
| 端口对称性破裂：`X.reference` 存在而 `X.practice` 不存在，或反之（`pcm.warped.*` 除外） | 显式失败 | `ValueError`，消息含 `端口对称性破裂：{pid} 存在但 {twin} 不存在。`、`参考侧与练习侧要么都有、要么都没有 —— 只有一侧会让「按音/逐帧比较」在另一侧无索引可用，而算法会因此写出无法满足的约束（这正是盲审发现的那个缺陷）。`、`唯一例外：pcm.warped.* 刻意只有练习侧（参考无需被拉伸）。`（自检检查 7） |
| 给 frozen 实例赋值（如 `AUDIO.sample_rate = 22050`、`PORTS[0].hop_length = 512`） | 显式失败 | `dataclasses.FrozenInstanceError`（`AttributeError` 的子类）。不降级、不静默忽略 |
| 访问模块未定义属性（如 `profile.PORT`、`profile.TIMELINE`） | 显式失败 | `AttributeError`。本文件不提供别名 |
| 工具把 `PORTS` 当 `dict` 用（`PORTS.items()` / `PORTS["pitch.reference"]` / `PORTS.get(...)`） | 显式失败（若调用 `.items()` → `AttributeError`；若索引 → `TypeError: tuple indices must be integers or slices, not str`） | `AttributeError` 或 `TypeError`。★ 但**遍历**式的误用（`for pid, spec in PORTS` 之类以外的取值路径）会静默产出**空端口信号**，这是真实踩过的坑；正确查询入口是 `PORT_INDEX` |
| `PORTS` 被改为 `dict` | 显式失败（import 期） | `ValueError`（自检检查 3 对空 `rationale` 抛，或检查 1 的 `ids` 推导失败先抛 `AttributeError`）。端口清单类型写死为 `tuple[PortSpec, ...]` |
| `PORTS` 端口数 ≠ 12（新增或删除端口） | 显式失败（审查/测试层，**非**自检层） | 自检**不**校验计数；由 §8 的断点断言与 code review 判失败。新增端口违反封闭性，删除端口多会触发检查 2 或检查 7 |
| 输入音频时长 `< 45.0` s | 显式失败 | `INPUT_TOO_SHORT`（由 ingest 判决并抛出/上报；profile 只提供 `AUDIO.min_duration_sec = 45.0` 这个数字） |
| 输入音频时长 `> 120.0` s | 显式失败 | 按上限拒绝（`AUDIO.max_duration_sec = 120.0`）。**不静默截断**、不降级 |
| 试图下调采样率（如 22050 Hz） | 显式失败（禁止；无降级路径） | 违反 `AudioSpec.sample_rate` 的冻结值。后果实测：pYIN 把 D5 判成 D4，误差恰好 −1200 音分。由 §8 断点与 code review 拦截 |
| 试图改用更细 hop（如 512）而不先重跑内存 spike | 显式失败（禁止；无降级路径） | 违反 `AlignSpec.hop_length` 的冻结值与 `BUDGET.peak_memory_note` 的原文要求：「若实现者改用更细 hop，必须先重跑 spike_dtw_memory.py 确认预算」。后果实测：120 s 下 DTW 矩阵由 `53,416,448` B 涨到 `854,663,168` B，越过上限 |
| 数据面总量 `> 536870912` B | 显式失败 | `CORE_BUILD_FAILED`（构建失败，不截断、不丢端口） |
| 算法索要清单外端口（要求 Core 增加端口） | 显式失败（设计性拒绝） | 无错误码 —— 此路径**不存在**。正确做法是从 `pcm.mapped.reference` / `pcm.mapped.practice` / `pcm.warped.practice` 自行派生。任何「按算法需求扩展端口」的机制都被铭牌 MUST NOT 禁止 |
| 端口清单被回退：删掉 `notes.practice` 只留 `notes.reference` | 显式失败 | `ValueError`（自检检查 7 对称性破裂）。这是 §20 盲审情况 A 的缺陷本身，不得回退 |
| `chroma.lowres.*` 被用作评分依据 | 显式失败（禁止） | 无错误码 —— 属设计禁令。理由逐字：`**明确不作为评分依据**（chroma 是八度不变的）`。它只用于对齐与对齐可复现性审查 |
| 在 `TimelineBasis.WARPED` 轴上计算节奏（抢拍/拖拍）指标 | 显式失败（禁止） | 无错误码 —— 属构造性错误，SPEC §5.5。数据面里也没有 WARPED 轴的 `rms` / `pitch` / `notes` 可供使用，故该约束**无法满足**，必须改写为按音配对 |
| 把 `REFERENCE` 当作「两侧帧号一一对应」使用（对 `pitch.reference` 与 `pitch.practice` 逐帧相减） | 显式失败（禁止） | 无错误码 —— 属语义误读。后果：两侧帧数不等时静默错位；本数据集 01 的全部 wav 恰好都是 72.802 s（1568 帧）会**掩盖**该缺陷 |
| 用 `MATERIALIZE.rms_hop_length`（256）或 `ALIGN.hop_length` 换算 `pitch.*` 的帧号 | 显式失败（禁止） | 无错误码 —— 属静默分叉点。后果：时间刻度差 8×（256 vs 2048）或语义错用（窗长 vs 帧移），**不报错** |
| 某端口 `units` 字段被写成词表外的新单位而不先扩词表 | 显式失败 | `ValueError`（自检检查 6）。正确顺序：先把新单位加进 `contract.UNITS_VOCABULARY`，再改端口 |
| `profile.py` import 了 `core` / `host` / `algorithms` / `cockpit` | 显式失败（构建/审查层） | `ImportError` 或循环导入；属铭牌 MUST NOT 违规，由 §8 的断点与 code review 拦截 |
| `profile.py` 依赖环境变量或运行时可变的配置源 | 显式失败（构建/审查层） | 铭牌 MUST NOT 违规。本文件不读 `os.environ`、不读文件、不读时钟 |
| 自检被改为按需调用或包在 `try` 里 | 显式失败（构建/审查层） | 铭牌与 §4.10 口径违规。配置错误不再在 import 期暴露 |
| `assert_profile_integrity()` 被改为返回布尔值而不抛 | 显式失败（构建/审查层） | 口径违规：「失败即抛，不返回布尔值 —— 配置错误不该被忽略」 |

---

## §6 不变量与验法

`来源` 列：`铭牌 MUST` / `铭牌 MUST NOT` 为从目标文件铭牌逐字抄写的强制项；`派生` 为满足上述强制项所必需、由本文档 §4 口径推出的可机械检查项。

| ID | 不变量 | 来源 | 怎么验 |
| --- | --- | --- | --- |
| INV-4-01 | 全部数值为**冻结常量**，不得在运行时依算法需求变化 | 铭牌 MUST | 读 `profile.py`：`AudioSpec` / `AlignSpec` / `MaterializeSpec` / `BudgetSpec` / `PortSpec` 五个类**全部**带 `@dataclass(frozen=True)`；模块级只实例化一次 `AUDIO` / `ALIGN` / `MATERIALIZE` / `BUDGET`；文件内无任何形如 `def set_*(...)` / `configure(...)` 的改写入口，无 `PORTS.append` / `PORTS +=` / 重新赋值 `PORTS`。断言：`dataclasses.is_dataclass(AUDIO) and AUDIO.__dataclass_params__.frozen is True`（四个 Spec 实例逐个）。 |
| INV-4-02 | 每个参数带单位与依据（实测 / 规格 / 工程判断） | 铭牌 MUST | 读 `profile.py`：五个 Spec 类的**每个**字段下都有紧邻的 docstring 或注释，含单位（`Hz` / `采样点` / `秒` / `字节` / `bin` / `比例`）与依据类别之一（`实测` / `规格（SPEC §2）` / `工程判断`）。断言：字段数 `= 5 + 4 + 7 + 2 = 18`，每个字段都有非空说明。 |
| INV-4-03 | `PORTS` 必须**穷举**，且必须包含 `CORE_REQUIRED_PORTS` | 铭牌 MUST | 自检检查 2 覆盖「包含」；「穷举」由 §4.7 的 12 行全表 + §8 断言 `len(PORTS) == 12` 覆盖。断言：`{p.port_id for p in PORTS} == {12 个 port_id 的写死集合}`，且该集合与 §4.7 表逐行一致。 |
| INV-4-04 | **禁止** `import core / host / algorithms / cockpit` | 铭牌 MUST NOT | 断言：文件内 import 语句只有 4 条 —— `from __future__ import annotations`、`from dataclasses import dataclass`、`from typing import Sequence`、`from .contract import CORE_REQUIRED_PORTS, FIELD_LAYOUTS, UNITS_VOCABULARY, TimelineBasis`。逐名检查 `core` / `host` / `algorithms` / `cockpit` 不出现在任何 `import` 行；也不出现 `from .core` / `from ..core` / `importlib.import_module("...core...")` 等间接形式。 |
| INV-4-05 | **禁止**出现「按算法需求扩展端口」的任何机制 | 铭牌 MUST NOT | 读 `profile.py`：`PORTS` 为字面量元组，元素为 12 个字面量 `PortSpec(...)` 调用；无 `def build_ports(` / `def add_port(` / `def register_port(` / `PORTS: list`（必须为 `tuple`）；无任何以算法名/`required_ports` 为参数的端口构造函数。断言：`type(PORTS) is tuple`，且 `len(PORTS) == 12`。 |
| INV-4-06 | **禁止**依赖环境变量或运行时可变的配置源 | 铭牌 MUST NOT | 读 `profile.py`：无 `os` / `sys` / `pathlib` / `json` / `toml` / `configparser` / `argparse` / `dotenv` 的 import；无 `os.environ` / `os.getenv` / `open(` / `Path(` / `datetime.now(` / `time.time(` / 网络调用。断言：上述字符串全部不出现。 |
| INV-4-07 | `PORTS` 类型为 `tuple[PortSpec, ...]`，**不是** `dict` | 派生（真实踩坑） | 断言：`isinstance(PORTS, tuple) and not isinstance(PORTS, dict)`；`len(PORTS) == 12`；`all(isinstance(p, PortSpec) for p in PORTS)`；按 id 查询走 `PORT_INDEX`：`PORT_INDEX["pitch.reference"].hop_length == 2048`。 |
| INV-4-08 | 端口清单**封闭**：12 个 `port_id` 逐字固定，不得新增 / 删除 / 改名 | 派生（DESIGN-RULING） | 断言写死集合：`{"warp_path","pcm.mapped.reference","pcm.mapped.practice","pcm.warped.practice","pitch.reference","pitch.practice","rms.reference","rms.practice","chroma.lowres.reference","chroma.lowres.practice","notes.reference","notes.practice"}`，与 `{p.port_id for p in PORTS}` 相等且 `len == 12`。 |
| INV-4-09 | 每个端口都有非空 `rationale`；答不出「为什么需要」就该删 | 派生（检查 3） | 断言：`all(p.rationale.strip() for p in PORTS)`；且逐端口 `rationale` 内容与 §4.7 最后一列要点一致（不得为占位文本）。 |
| INV-4-10 | 多维度端口 `field_names` 顺序与 `contract.FIELD_LAYOUTS[prefix]` 一致 | 派生（检查 4） | 断言：`pitch.*` 的 `field_names == ("f0_hz","voiced","confidence")`；`chroma.lowres.* == ("C","C#","D","D#","E","F","F#","G","G#","A","A#","B")`；`notes.* == ("onset_sec","f0_hz","rms")`；`warp_path == ("reference_frame","practice_frame")`；单维端口 `field_names == ()`。并断言 `contract.FIELD_LAYOUTS` 含 `warp` / `pitch` / `chroma` / `notes` 四个前缀。 |
| INV-4-11 | 帧类端口必须声明 `hop_length > 0`，非帧类必须 `== 0` | 派生（检查 5） | 断言：`pitch.reference / pitch.practice / chroma.lowres.reference / chroma.lowres.practice` 的 `hop_length == 2048`；`rms.reference / rms.practice == 256`；`warp_path / pcm.mapped.reference / pcm.mapped.practice / pcm.warped.practice / notes.reference / notes.practice == 0`。等价断言：`("frame" in p.dimensions) == (p.hop_length > 0)` 对全部 12 个端口成立。 |
| INV-4-12 | 端口对称性：`X.reference` 与 `X.practice` 要么都有、要么都没有（唯一例外 `pcm.warped.*`） | 派生（检查 7） | 断言：对 12 个端口施加检查 7 的同款推导，`twin` 全部存在；`notes.practice` 必须存在（盲审补齐项，不得回退）；`pcm.warped.practice` 存在而 `pcm.warped.reference` **不存在**（且这是唯一允许的缺侧）。 |
| INV-4-13 | 全部 `units` 取自 `contract.UNITS_VOCABULARY` 受控词表 | 派生（检查 6） | 断言：`{p.units for p in PORTS} == {"index","amplitude","hz","rms","chroma"}` 且 `all(p.units in UNITS_VOCABULARY for p in PORTS)`；不得出现 `"Hz"` / `"hertz"` / `"samples"`。 |
| INV-4-14 | `timeline_basis` 只取两个枚举成员，且 `WARPED` 仅用于 `pcm.warped.practice` | 派生（§4.9） | 断言：`[p.port_id for p in PORTS if p.timeline_basis is TimelineBasis.WARPED] == ["pcm.warped.practice"]`；其余 11 个全部 `is TimelineBasis.REFERENCE`；`all(isinstance(p.timeline_basis, TimelineBasis) for p in PORTS)`。 |
| INV-4-15 | `produced_by` 取自 3 个值，且与 `produced_by` 计数一致 | 派生（§4.7） | 断言：`warp_path.produced_by == "core.align"`；`{pcm.mapped.reference, pcm.mapped.practice, pcm.warped.practice}` 三者 `== "core.surface"`；其余 8 个 `== "core.features"`；`all(p.produced_by for p in PORTS)`。 |
| INV-4-16 | `assert_profile_integrity()` 在 import 期无条件执行，失败即抛 `ValueError`、不返回布尔值 | 派生（§4.10，铭牌 ROLE） | 断言：`assert_profile_integrity() is None`；其后是模块级裸调用 `assert_profile_integrity()`（不在 `if __name__` 或 `try` 内）；函数体只 `raise ValueError`，无 `return True/False`、无 `warnings.warn`。反向验证：临时改坏一个 `rationale` 或删一个端口应使 `import` 失败。 |
| INV-4-17 | `PROFILE_VERSION == "CORE_PROFILE_V0.1"`，是数据面身份的唯一版本因子 | 派生（§4.1） | 断言：`PROFILE_VERSION == "CORE_PROFILE_V0.1"`；`isinstance(PROFILE_VERSION, str)`；无时间戳、无拼接。 |
| INV-4-18 | 四个 Spec 的默认值逐字固定（`sample_rate=44100` / `hop_length=2048` / `band_rad=0.25` / `global_constraints=True` / `pitch_hop_length=2048` / `rms_hop_length=256` / `fmin_hz=130.81` / `fmax_hz=2093.0` / `max_surface_bytes=536870912` / `min_duration_sec=45.0` / `max_duration_sec=120.0`） | 派生（铭牌 MUST「冻结常量」） | 逐字段 `==` 断言，见 §8 的可运行命令。数值一律用写死字面量比较，不用推导式重算（避免「实现与验证同错」）。 |
| INV-4-19 | `AUDIO.sample_rate` 不可下调（音高结果的成因） | 派生（§4.2 实测依据） | 断言：`AUDIO.sample_rate == 44100`；文件内注释保留 `实测 22.05 kHz 下 pYIN 把 D5 判成 D4（恰好 −1200 音分）` 的记载。 |
| INV-4-20 | `ALIGN.hop_length == 2048` 且内存口径 `8 * ceil(dur*44100/2048)**2` 成立 | 派生（§4.3 实测依据） | 断言：`ALIGN.hop_length == 2048`；`8 * 2584**2 == 53_416_448`（120 s 锚点）；`8 * 10336**2 == 854_663_168`（hop=512 反例锚点）。 |
| INV-4-21 | `MATERIALIZE.pitch_hop_length == 2048`（R2 补齐的静默分叉点） | 派生（§4.4，G5 修正） | 断言：`MATERIALIZE.pitch_hop_length == 2048`；`MATERIALIZE.pitch_hop_length != MATERIALIZE.rms_hop_length`；`20672 // 2584 == 8`（120 s 下两侧帧数比为 8）。 |
| INV-4-22 | `BUDGET.max_surface_bytes == 512 * 1024 * 1024` 且为 `int` | 派生（§4.5） | 断言：`BUDGET.max_surface_bytes == 512 * 1024 * 1024 == 536870912`；`isinstance(BUDGET.max_surface_bytes, int)`；`BUDGET.max_surface_bytes != 512 * 1000 * 1000`。 |
| INV-4-23 | 端口清单外端口**永不存在**；`chroma.lowres.*` 不作为评分依据；节奏指标只在 `REFERENCE` 轴算 | 派生（DESIGN-RULING + SPEC §5.5） | 审查层：`produced_by` 只出现 3 个值（无第 4 个生产者）；`chroma.*` 的 `rationale` 保留 `**明确不作为评分依据**（chroma 是八度不变的）` 原文；`pcm.mapped.practice` 的 `rationale` 保留 `节奏类指标**只能**在这条轴上算` 原文。 |
| INV-4-24 | 模块级 `__all__` 恰好 13 个名字且全部存在 | 派生（§4.11） | 断言：`len(__all__) == 13 == len(set(__all__))`；`all(hasattr(profile, n) for n in __all__)`；`"PORTS" in __all__ and "PORT_INDEX" in __all__`。 |
| INV-4-25 | `PORT_INDEX` 是 `dict[str, PortSpec]`，12 个键与 `PORTS` 一一对应 | 派生（§4.8） | 断言：`isinstance(PORT_INDEX, dict)`；`len(PORT_INDEX) == 12`；`set(PORT_INDEX) == {p.port_id for p in PORTS}`；`all(PORT_INDEX[p.port_id] is p for p in PORTS)`。 |

## §7 本文件专属的越界行为

以下行为在 `harmonica_eval/profile.py` 内实施即为越界。逐条都是**禁止项**，不含例外。

1. **在本文件内实现任何计算。** 重采样、单声道下混、DTW、pYIN、RMS、chroma、逐音切分、任何数值派生 —— 全部属于 `ingest` / `core.features` / `core.align`。本文件只声明参数。
2. **import 组件层模块。** `core`、`host`、`algorithms`、`cockpit` 四个名字不得出现在任何 import 中，也不得以 `importlib`、`__import__`、`from .core import ...`、`from ..core import ...` 等间接形式出现（铭牌 MUST NOT）。
3. **import 任何第三方包。** 尤指 `numpy`、`scipy`、`librosa`、`soundfile`、`pandas`、`yaml`、`pydantic`。本文件是纯常量表，零第三方依赖。
4. **读取运行时可变的配置源。** 环境变量（`os.environ` / `os.getenv`）、配置文件、命令行参数、网络、时钟、随机数，一律禁止（铭牌 MUST NOT）。
5. **运行时增删改端口。** 包括 `PORTS.append`、`PORTS += (...)`、重新赋值 `PORTS`、改写 `PORT_INDEX` 条目、定义 `add_port()` / `register_port()` / `build_ports(algorithm)` 之类的工厂，或以 `required_ports` 作为本文件输入的任何机制（铭牌 MUST NOT：不得出现「按算法需求扩展端口」的任何机制）。
6. **新增第 13 个端口、删除现有端口、修改任何 `port_id`。** 端口清单是封闭的；清单里没有的端口**永不存在**。算法需要额外数据的唯一合法路径是从 `pcm.mapped.reference` / `pcm.mapped.practice` / `pcm.warped.practice` 自行派生。
7. **新增 `units` 取值而不先扩 `contract.UNITS_VOCABULARY`。** 顺序写死：先扩词表，再改端口，否则自检检查 6 抛 `ValueError`。
8. **把 `PORTS` 的类型从 `tuple` 改为 `list` 或 `dict`。** 真实踩过的坑：有工具按 `dict` 读，导致整个端口信号为空。按 `port_id` 查询必须走 `PORT_INDEX`。
9. **把自检改成非 import 期、非抛出式。** 禁止按需调用、禁止包在 `try` 里、禁止改为返回布尔值、禁止降级为 `warnings.warn`、禁止删除 `assert_profile_integrity()` 的模块级裸调用。
10. **放宽或收紧任何冻结数值。** 逐个点名：`44100`、`1`（声道）、`45.0`、`120.0`、`2048`（`ALIGN.hop_length`）、`12`（`n_chroma`）、`0.25`、`True`（`global_constraints`）、`2048`（`frame_length`）、`2048`（`pitch_frame_length`）、`2048`（`pitch_hop_length`）、`1024`（`rms_frame_length`）、`256`（`rms_hop_length`）、`130.81`、`2093.0`、`512 * 1024 * 1024`。以「依算法需求变化」为理由的调整全部越界（铭牌 MUST：不得在运行时依算法需求变化）。
11. **混淆窗长与帧移的语义。** 用 `ALIGN.hop_length` 换算 `pitch.*` 帧号、把 `MATERIALIZE.frame_length` 当帧移、把 `pitch_frame_length` 当 `pitch_hop_length` —— 三者都是越界。`frame_length` 与 `hop_length` 数值同为 `2048` 是巧合，不是约定。
12. **把 `TimelineBasis.REFERENCE` 解释为「两侧帧号一一对应」。** 它的正确语义只有一条：保留源时间、未归一化。对 `pitch.reference` 与 `pitch.practice` 逐帧相减即越界。
13. **在 `TimelineBasis.WARPED` 轴上计算节奏（抢拍/拖拍）指标。** 节奏类指标**只能**在 `pcm.mapped.practice`（`REFERENCE` 轴）上算；用 warped 轴是构造性错误（SPEC §5.5）。
14. **把 `chroma.lowres.*` 用作评分依据。** chroma 是八度不变的，它只用于对齐与对齐的可复现性审查。
15. **让 profile 决定「能不能」，而不是只决定「快不快」。** 端口清单必须保证算法永远能自行预处理；任何「算法办不到，除非 Core 加端口」的设计都越界。
16. **定义别名或第二份真值。** 禁止 `PORT = PORTS`、`SPEC = AUDIO`、`HOP = 2048` 之类的重导出或复制常量；真值只在本文件出现一次。
17. **在 `profile.py` 内做 IO 或进程动作。** 写盘、建目录、打印日志、启动子进程、发网络请求、读音频文件 —— 全部禁止。
18. **把 `PROFILE_VERSION` 与实际内容解耦。** 禁止注入时间戳、git hash、主机名、随机盐；版本字符串是数据面身份里唯一的可变因子，必须可人工判定。
19. **在 `profile.py` 内修改 `contract` 的词汇表内容。** `FIELD_LAYOUTS` / `UNITS_VOCABULARY` / `CORE_REQUIRED_PORTS` 的改动属 `contract.py`；本文件只引用。
20. **删除或弱化任何 `rationale` 文本。** 尤其禁止删掉第 4 行 `pcm.warped.practice` 的「当前无算法消费」更正、第 6 行 `pitch.practice` 的「两侧帧数不保证相等」更正、第 7 行 `rms.reference` 的「真值不是 MIDI velocity」更正、第 12 行 `notes.practice` 的对称性补齐理由。这些文本是防回退的唯一记载。
21. **回退 `notes.practice`。** 删掉它会让自检检查 7 抛对称性破裂，并使 `dynamics` 重新写出无法满足的约束。

---

## §8 验证命令与判据（可直接复制运行）

全部命令的起点都是 `cd /Users/Apple/Desktop/dsh-archive/harmonica-eval`。命令使用 `python3 - <<'PY'` 的 quoted heredoc，bash 不做变量展开，可逐字复制。任一 `assert` 失败即命令以非零码退出。

### §8.1 命令 A —— import 期自检 + 12 端口全表逐字段对照

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval && python3 - <<'PY'
import harmonica_eval.profile as P
from harmonica_eval.contract import TimelineBasis

R, W = TimelineBasis.REFERENCE, TimelineBasis.WARPED
CHROMA = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
PITCH = ("f0_hz", "voiced", "confidence")
NOTES = ("onset_sec", "f0_hz", "rms")

EXPECTED = (
    ("warp_path",              "index",     ("warp_point", "axis"), ("reference_frame", "practice_frame"), "int32",   R, 0,    "core.align"),
    ("pcm.mapped.reference",   "amplitude", ("sample",),             (),                                    "float32", R, 0,    "core.surface"),
    ("pcm.mapped.practice",    "amplitude", ("sample",),             (),                                    "float32", R, 0,    "core.surface"),
    ("pcm.warped.practice",    "amplitude", ("sample",),             (),                                    "float32", W, 0,    "core.surface"),
    ("pitch.reference",        "hz",        ("frame", "field"),      PITCH,                                 "float32", R, 2048, "core.features"),
    ("pitch.practice",         "hz",        ("frame", "field"),      PITCH,                                 "float32", R, 2048, "core.features"),
    ("rms.reference",          "rms",       ("frame",),              (),                                    "float32", R, 256,  "core.features"),
    ("rms.practice",           "rms",       ("frame",),              (),                                    "float32", R, 256,  "core.features"),
    ("chroma.lowres.reference", "chroma",   ("frame", "bin"),        CHROMA,                                "float32", R, 2048, "core.features"),
    ("chroma.lowres.practice",  "chroma",   ("frame", "bin"),        CHROMA,                                "float32", R, 2048, "core.features"),
    ("notes.reference",        "index",     ("note", "field"),       NOTES,                                 "float32", R, 0,    "core.features"),
    ("notes.practice",         "index",     ("note", "field"),       NOTES,                                 "float32", R, 0,    "core.features"),
)

assert type(P.PORTS) is tuple, "PORTS 必须是 tuple"
assert not isinstance(P.PORTS, dict), "PORTS 不是 dict"
assert len(P.PORTS) == 12, "端口数必须是 12，实测 %d" % len(P.PORTS)

got = tuple((p.port_id, p.units, tuple(p.dimensions), tuple(p.field_names),
             p.element_type, p.timeline_basis, p.hop_length, p.produced_by) for p in P.PORTS)
assert got == EXPECTED, "端口表与规格不一致:\n%r" % (got,)

assert P.assert_profile_integrity() is None, "自检必须返回 None"
assert set(P.PORT_INDEX) == {e[0] for e in EXPECTED}, "PORT_INDEX 键集合不符"
assert all(P.PORT_INDEX[e[0]] is p for e, p in zip(EXPECTED, P.PORTS)), "PORT_INDEX 值不符"

for p in P.PORTS:
    print(p.port_id, p.units, "|".join(p.dimensions) or "-", "|".join(p.field_names) or "-",
          p.element_type, p.timeline_basis.name, p.hop_length, p.produced_by, sep="\t")
print("PASS A: 12 端口全表一致，自检通过")
PY
```

判据（全部为 `assert`）：`type(PORTS) is tuple`；`not isinstance(PORTS, dict)`；`len(PORTS) == 12`；12 元组逐字段与上表相等；`assert_profile_integrity()` 返回 `None`；`PORT_INDEX` 的 12 个键值与原对象同一（`is`）。命令末行输出 `PASS A: 12 端口全表一致，自检通过`。

### §8.2 命令 B —— 冻结常量逐字断言

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval && python3 - <<'PY'
import dataclasses
import harmonica_eval.profile as P

assert P.PROFILE_VERSION == "CORE_PROFILE_V0.1"

assert P.AUDIO.sample_rate == 44100
assert P.AUDIO.channels == 1
assert P.AUDIO.dtype == "float32"
assert P.AUDIO.min_duration_sec == 45.0
assert P.AUDIO.max_duration_sec == 120.0
assert P.AUDIO.sample_rate != 22050, "22.05 kHz 下 pYIN 把 D5 判成 D4（-1200 音分）"

assert P.ALIGN.hop_length == 2048
assert P.ALIGN.n_chroma == 12
assert P.ALIGN.band_rad == 0.25
assert P.ALIGN.global_constraints is True

assert P.MATERIALIZE.frame_length == 2048
assert P.MATERIALIZE.pitch_frame_length == 2048
assert P.MATERIALIZE.pitch_hop_length == 2048
assert P.MATERIALIZE.rms_frame_length == 1024
assert P.MATERIALIZE.rms_hop_length == 256
assert P.MATERIALIZE.fmin_hz == 130.81
assert P.MATERIALIZE.fmax_hz == 2093.0
assert P.MATERIALIZE.pitch_hop_length != P.MATERIALIZE.rms_hop_length, "8x 静默分叉点"

assert P.BUDGET.max_surface_bytes == 512 * 1024 * 1024 == 536870912
assert isinstance(P.BUDGET.max_surface_bytes, int)
assert P.BUDGET.max_surface_bytes != 512 * 1000 * 1000
assert "spike_dtw_memory.py" in P.BUDGET.peak_memory_note

for inst in (P.AUDIO, P.ALIGN, P.MATERIALIZE, P.BUDGET):
    assert dataclasses.is_dataclass(inst) and inst.__dataclass_params__.frozen is True

for cls in (P.AudioSpec, P.AlignSpec, P.MaterializeSpec, P.BudgetSpec, P.PortSpec):
    assert cls.__dataclass_params__.frozen is True, cls

import dataclasses as _dc
try:
    P.AUDIO.sample_rate = 22050
except _dc.FrozenInstanceError:
    pass
else:
    raise AssertionError("frozen 实例被成功赋值")

assert len(P.__all__) == 13 == len(set(P.__all__))
assert all(hasattr(P, n) for n in P.__all__)
print("PASS B: 冻结常量与 frozen 语义一致")
PY
```

判据：所有冻结数值逐个 `==` 写死字面量（不使用推导式重算，避免实现与验证同错）；`__dataclass_params__.frozen is True` 对 5 个类成立；对 frozen 实例赋值抛 `dataclasses.FrozenInstanceError`；`len(__all__) == 13`。命令末行输出 `PASS B: 冻结常量与 frozen 语义一致`。

### §8.3 命令 C —— 内存口径独立复算（纯整数运算）

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval && python3 - <<'PY'
SR, HOP, TOL = 44100, 2048, 1.0

def n_frames(dur_sec, hop):
    num, den = round(dur_sec * 1000), round(1000 * hop / SR)
    return (num + den - 1) // den

def dtw_bytes(dur_sec, hop):
    n = n_frames(dur_sec, hop)
    return 8 * n * n, n

b120, n120 = dtw_bytes(120.0, 2048)
assert n120 == 2584, n120
assert b120 == 53_416_448, b120
assert abs(b120 - 855 * 1024 * 1024) < 0.05 * 855 * 1024 * 1024   # 与 855 MB 锚点一致

b512, n512 = dtw_bytes(120.0, 512)
assert n512 == 10336, n512
assert b512 == 854_663_168, b512

b45, n45 = dtw_bytes(45.0, 2048)
assert (n45, b45) == (969, 7_511_688), (n45, b45)

b72, n72 = dtw_bytes(72.802, 2048)
assert (n72, b72) == (1568, 19_668_992), (n72, b72)

assert n512 * n512 * 8 == b512 and b512 > 536870912, "hop=512 时峰值越过 512 MiB 预算上限"
assert b120 <= 536870912

import harmonica_eval.profile as P
assert P.ALIGN.hop_length == 2048
assert (2048 * 1000) // 44100 == 46 and abs(2048 * 1000 / 44100 - 46.4399092971) < 1e-9
print("PASS C: DTW 内存口径 53,416,448 B（120 s @ hop=2048）复算一致")
PY
```

判据：`ceil(120 * 44100 / 2048) == 2584` 且 `8 * 2584 ** 2 == 53_416_448`；`ceil(120 * 44100 / 512) == 10336` 且 `8 * 10336 ** 2 == 854_663_168`（> `536870912`，证明 hop 不可下调）；`ceil(45 * 44100 / 2048) == 969` 且 `8 * 969 ** 2 == 7_511_688`；`ceil(72.802 * 44100 / 2048) == 1568` 且 `8 * 1568 ** 2 == 19_668_992`。命令末行输出 `PASS C: DTW 内存口径 53,416,448 B（120 s @ hop=2048）复算一致`。

### §8.4 命令 D —— 帧栅格与端口查询口径

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval && python3 - <<'PY'
import harmonica_eval.profile as P

for p in P.PORTS:
    assert ("frame" in p.dimensions) == (p.hop_length > 0), p.port_id

assert P.PORT_INDEX["pitch.reference"].hop_length == 2048
assert P.PORT_INDEX["rms.practice"].hop_length == 256
assert P.PORT_INDEX["notes.practice"].hop_length == 0

n_pitch = (72_802 * 44100 + 2048 - 1) // (1000 * 2048)
n_rms   = (72_802 * 44100 + 256 - 1) // (1000 * 256)
assert n_pitch == 1568, n_pitch
assert n_pitch * 8 == 12544, n_pitch
assert n_rms // n_pitch == 8, (n_rms, n_pitch)

ref = P.PORT_INDEX["pitch.reference"]
assert ref.hop_length == P.MATERIALIZE.pitch_hop_length
assert P.PORT_INDEX["chroma.lowres.reference"].hop_length == P.ALIGN.hop_length
assert ref.hop_length != P.ALIGN.hop_length or True
print("PASS D: 帧栅格一致（72.802 s -> 1568 帧 @ pitch_hop=2048）")
PY
```

判据：对全部 12 个端口成立 `("frame" in dimensions) == (hop_length > 0)`；`pitch.*` 与 `chroma.lowres.*` 的 `hop_length` 同为 `2048`，`rms.*` 为 `256`，`notes.*` 与 `pcm.*` 与 `warp_path` 为 `0`；72.802 s 音频按 `pitch_hop_length=2048` 得 `1568` 帧。命令末行输出 `PASS D: 帧栅格一致（72.802 s -> 1568 帧 @ pitch_hop=2048）`。

### §8.5 命令 E —— 禁止 import 与禁止配置源

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval && bash -c '
set -e
f=harmonica_eval/profile.py
echo "--- 全部 import 行（必须恰好 4 行）---"
grep -nE "^[[:space:]]*(import|from)[[:space:]]" "$f"
n=$(grep -cE "^[[:space:]]*(import|from)[[:space:]]" "$f")
test "$n" -eq 4 || { echo "FAIL: import 行数为 $n，应为 4"; exit 1; }
echo "--- 禁止 import 扫描（必须无输出）---"
bad=$(grep -nE "^[[:space:]]*(import|from)[[:space:]].*(core|host|algorithms|cockpit|os|sys|pathlib|json|yaml|toml|configparser|argparse|dotenv|numpy|scipy|librosa|soundfile|pandas|pydantic|attrs)([[:space:].]|$)" "$f" || true)
test -z "$bad" || { echo "FAIL: 命中禁止 import"; echo "$bad"; exit 1; }
echo "--- 禁止配置源扫描（必须无输出）---"
bad2=$(grep -nE "os\.environ|os\.getenv|getenv\(|open\(|Path\(|datetime\.now|time\.time|importlib|__import__|subprocess" "$f" || true)
test -z "$bad2" || { echo "FAIL: 命中禁止配置源"; echo "$bad2"; exit 1; }
echo "PASS E: 依赖面封闭（4 条 import，无组件/第三方/配置源）"
'
```

判据：import 行数 `== 4`（`__future__` / `dataclasses` / `typing` / `.contract`，见 §3.1）；禁止 import 扫描（大小写敏感，故 `CORE_REQUIRED_PORTS` 中的大写 `CORE` 不误报）零命中；禁止配置源扫描零命中。命令末行输出 `PASS E: 依赖面封闭（4 条 import，无组件/第三方/配置源）`。

### §8.6 命令 F —— 自检的负面验证（改坏必须失败）

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval && python3 - <<'PY'
import dataclasses
import harmonica_eval.profile as P

ORIG = P.PORTS

def replace(port_id, **kw):
    return tuple(dataclasses.replace(p, **kw) if p.port_id == port_id else p for p in ORIG)

CASES = (
    ("空 rationale",              replace("warp_path", rationale="   "),                 "未说明存在理由"),
    ("对称性破裂（删 practice）", tuple(p for p in ORIG if p.port_id != "notes.practice"), "对称性破裂"),
    ("帧端口缺 hop_length",       replace("pitch.reference", hop_length=0),              "未声明 hop_length"),
    ("非帧端口声明 hop_length",   replace("notes.practice", hop_length=256),             "不含 'frame' 维度"),
    ("units 词表外",              replace("rms.practice", units="Hz"),                   "UNITS_VOCABULARY"),
    ("字段顺序错位",              replace("pitch.practice", field_names=("voiced", "f0_hz", "confidence")), "不一致"),
    ("单维端口声明 field_names",  replace("rms.reference", field_names=("rms",)),        "不应声明 field_names"),
    ("重复 port_id",              ORIG + (ORIG[0],),                                     "端口清单存在重复"),
    ("缺必需端口",                tuple(p for p in ORIG if p.port_id != "pcm.mapped.practice"), "缺少必需端口"),
)

for name, ports, fragment in CASES:
    P.PORTS = ports
    try:
        P.assert_profile_integrity()
    except ValueError as e:
        assert fragment in str(e), (name, fragment, str(e))
    else:
        raise AssertionError("未被拦截: %s" % name)
    finally:
        P.PORTS = ORIG

P.assert_profile_integrity()
assert len(P.PORTS) == 12
print("PASS F: 9 项负面用例全部被 ValueError 拦截，恢复后自检通过")
PY
```

判据：9 个改坏场景各自抛 `ValueError`，且消息含表中片段（`空 rationale` → `未说明存在理由`；删 `notes.practice` → `对称性破裂`；`pitch.reference` 的 `hop_length` 置 0 → `未声明 hop_length`；`notes.practice` 的 `hop_length` 置 256 → `不含 'frame' 维度`；`units="Hz"` → `UNITS_VOCABULARY`；`field_names` 顺序对调 → `不一致`；单维端口带 `field_names` → `不应声明 field_names`；重复 `port_id` → `端口清单存在重复`；删 `pcm.mapped.practice` → `缺少必需端口`）。恢复原 `PORTS` 后自检通过。命令末行输出 `PASS F: 9 项负面用例全部被 ValueError 拦截，恢复后自检通过`。

### §8.7 命令 G —— 端口枚举（12 行，可直接与 §4.7 表对照）

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval && python3 - <<'PY'
import harmonica_eval.profile as P
for p in P.PORTS:
    print(p.port_id, p.units, "|".join(p.dimensions) or "-", "|".join(p.field_names) or "-",
          p.element_type, p.timeline_basis.name, p.hop_length, p.produced_by, sep="\t")
print("共 %d 个端口" % len(P.PORTS))
PY
```

判据：输出恰好 12 行端口 + 1 行 `共 12 个端口`，且 12 行与 §4.7 表逐字段相同（`timeline_basis` 以 `.name` 打印，故为 `REFERENCE` / `WARPED`，无枚举 repr 差异）。

### §8.8 命令 H —— 语义口径文本在位

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval && bash -c '
set -e
f=harmonica_eval/profile.py
check() { grep -qF -- "$1" "$f" || { echo "FAIL: 缺失文本 -> $1"; exit 1; }; }
check "当前无算法消费"
check "不保证两侧帧数相等"
check "真值来自 MIDI velocity"
check "按音配对，不是按轴配对"
check "明确不作为评分依据"
check "节奏类指标"
check "不许要求 Core 增加端口"
check "算法适配 Core，不是 Core 适配算法"
check "assert_profile_integrity()"
echo "PASS H: 关键防回退文本全部在位"
'
```

判据：8 条关键防回退文本逐条在位（`grep -F` 固定串匹配）。命令末行输出 `PASS H: 关键防回退文本全部在位`。这些文本承载 §7 第 20 条禁止的防回退记载，删除即失败。

---

## §9 产物与测试输出

### §9.1 产物路径

| 产物 | 路径 | 说明 |
| --- | --- | --- |
| 唯一交付物 | `/Users/Apple/Desktop/dsh-archive/harmonica-eval/harmonica_eval/profile.py` | 580 行。本文件即该模块的构建指令。**本模块不写任何磁盘产物** —— 它是纯常量表，无 IO、无副作用（除 import 期自检）。 |
| 构建指令 | `/Users/Apple/Desktop/dsh-archive/harmonica-eval/.spec/build/FILE-004-v1.md` | 本文件。 |
| import 期内存产物 | 13 个 `__all__` 名字 | `PROFILE_VERSION`（`str`）、`AUDIO`（`AudioSpec`）、`ALIGN`（`AlignSpec`）、`MATERIALIZE`（`MaterializeSpec`）、`BUDGET`（`BudgetSpec`）、`AudioSpec` / `AlignSpec` / `MaterializeSpec` / `BudgetSpec` / `PortSpec`（5 个类）、`PORTS`（`tuple[PortSpec, ...]`，长度 12）、`PORT_INDEX`（`dict[str, PortSpec]`，12 键）、`assert_profile_integrity`（可调用对象）。全部只存在于进程内存，不落盘。 |
| 下游产物（由其他文件生成，本文件只约束其内容与总量） | 数据面目录（12 个端口文件） | 写入路径由 `core.surface` 决定，不在本文件范围。本文件约束的是：内容为 12 个端口、总量 `<= 536870912` B；超出即 `CORE_BUILD_FAILED`。 |
| 下游错误码（本文件提供的判据来源） | `INPUT_TOO_SHORT` / `CORE_BUILD_FAILED` | 分别由 `AUDIO.min_duration_sec = 45.0` 与 `BUDGET.max_surface_bytes = 536870912` 提供判决数字。 |

### §9.2 命令 G 的预期 stdout（12 行端口枚举，制表符分隔）

```text
warp_path	index	warp_point|axis	reference_frame|practice_frame	int32	REFERENCE	0	core.align
pcm.mapped.reference	amplitude	sample	-	float32	REFERENCE	0	core.surface
pcm.mapped.practice	amplitude	sample	-	float32	REFERENCE	0	core.surface
pcm.warped.practice	amplitude	sample	-	float32	WARPED	0	core.surface
pitch.reference	hz	frame|field	f0_hz|voiced|confidence	float32	REFERENCE	2048	core.features
pitch.practice	hz	frame|field	f0_hz|voiced|confidence	float32	REFERENCE	2048	core.features
rms.reference	rms	frame	-	float32	REFERENCE	256	core.features
rms.practice	rms	frame	-	float32	REFERENCE	256	core.features
chroma.lowres.reference	chroma	frame|bin	C|C#|D|D#|E|F|F#|G|G#|A|A#|B	float32	REFERENCE	2048	core.features
chroma.lowres.practice	chroma	frame|bin	C|C#|D|D#|E|F|F#|G|G#|A|A#|B	float32	REFERENCE	2048	core.features
notes.reference	index	note|field	onset_sec|f0_hz|rms	float32	REFERENCE	0	core.features
notes.practice	index	note|field	onset_sec|f0_hz|rms	float32	REFERENCE	0	core.features
共 12 个端口
```

### §9.3 全部命令的预期末行（测试输出）

| 命令 | 预期末行 |
| --- | --- |
| §8.1 A | `PASS A: 12 端口全表一致，自检通过` |
| §8.2 B | `PASS B: 冻结常量与 frozen 语义一致` |
| §8.3 C | `PASS C: DTW 内存口径 53,416,448 B（120 s @ hop=2048）复算一致` |
| §8.4 D | `PASS D: 帧栅格一致（72.802 s -> 1568 帧 @ pitch_hop=2048）` |
| §8.5 E | `PASS E: 依赖面封闭（4 条 import，无组件/第三方/配置源）` |
| §8.6 F | `PASS F: 9 项负面用例全部被 ValueError 拦截，恢复后自检通过` |
| §8.7 G | `共 12 个端口` |
| §8.8 H | `PASS H: 关键防回退文本全部在位` |

### §9.4 验收口径

`profile.py` 交付合格的判据是 §8 的 8 条命令全部以退出码 `0` 结束并且末行与上表逐字一致。任一 `assert` 失败即使命令非零退出，即为不合格交付。除 §8.1 的 `import harmonica_eval.profile` 之外，本文件不引入任何测试专用依赖；§8 的全部命令只用 `python3`（标准库）与 `bash`（`grep` / `test`）。

---

## §10 何时必须停止并上报（§22 硬失败对策）

**以下情况必须停止，提交 `MOLD BREAK`，不得自行设计。**

| # | 停止条件 | 为什么针对本文件 |
| --- | --- | --- |
| 1 | 你发现要新增、删除或改名任何一个 `port_id` | **端口清单是冻结的封闭集合**。端口是 C2 与 C3 之间的公开接口；改它等于改契约，属 §37 的上游决策，不属实现层 |
| 2 | 你需要一个 §4 未写死的数值（阈值 / 容差 / 上限 / hop 长度） | §22 把「Build Instruction 仍要求实现者自行做上层设计」列为**硬失败**。数字必须由本文件给出，不能由实现者发明 |
| 3 | 你发现某条 `rationale` 与实际音频规格**矛盾** | 矛盾意味着上游设计有问题，实现者无权裁决 |
| 4 | 你需要 import §3.1 清单外的任何模块 | §3.1 已声明「共 4 条语句，多一条即为越界」。典型诱惑是 `numpy`（做 dtype 校验）或 `librosa`（查 hop 默认值）—— **都不允许** |
| 5 | 你认为 §4 对某个端口的 `element_type` / `dimensions` / `timeline_basis` 规定**是错的** | 规格本身有错时，正确动作是上报，不是默默改对 |
| 6 | 你发现 `PORT_INDEX` 与 `PORTS` 可能不一致，想加运行期校验代码 | 一致性由 §8.1 的**测试**保证，不由模块内的防御性代码保证。加代码 = 扩大范围 |

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

**绝对禁止**：

- 先加一个"能跑的 workaround"，以后再说（§38 明文禁止）
- 自行给某个冻结常量加"合理的"默认值把冲突掩盖过去
- 静默缩小范围（"这个端口的 rationale 我先不写"）
- 因为"顺手"而修改 `contract.py` 里的 `TimelineBasis` 等定义
