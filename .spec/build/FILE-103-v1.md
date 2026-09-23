# FILE-103 — harmonica_eval/core/features.py

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/core/features.py`
> 生成依据：`SPEC.md`（唯一权威规格）· `profile.py`（MATERIALIZE / PORTS / AUDIO）· `contract.py`（FIELD_LAYOUTS / ErrorCode）· 目标文件现存模块 docstring（FILE-ID: FILE-103 · COMPONENT: COMP-C2 Audio Core）
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-103 |
| 所属组件 | COMP-C2 Audio Core |
| 层级 | L3（symbol / implementation） |
| 上游 | Seal 流程（Core 封存阶段）调用 `materialize_*` 系列；输入为解码后的 `samples: float32 mono PCM` 与 `sample_rate: int` |
| 下游 | `contract`/`profile` 声明的全部端口消费者：三个算法模块（音准 / 节奏 / 对齐）读取端口数组；`notes` 端口供算法按音组织结论 |
| 同层邻居 | COMP-C2 内的解码/重采样、Seal 编排、端口装配文件（同组件其他 FILE-ID） |
| 你的权限 | 只实现本文件。不得修改任何其他文件，不得修改契约，不得新增端口，不得新增依赖 |

**★ 产出枢纽定位（必读）**：`profile.PORTS` 声明 12 个端口，其中 **8 个端口由本文件生产** —— 本文件是 Core 的产出枢纽，不是辅助工具。任何端口形状、dtype、字段顺序的偏差，会同时打穿三个算法。

**★ 共享词汇定位（必读）**：`notes.*` 字段（`onset_sec` / `f0_hz` / `rms`）是**全部三个算法共享的词汇**。三个算法彼此不共享中间结果，只共享本文件产出的端口数据。因此 `notes` 的字段语义（单位、时间基准、字段顺序、未发声处理）是跨算法的公共契约：此处改一个字段含义，等于同时改三个算法。这也正是「Core 预生成」架构裁定的落地点 —— 算法若要额外数据，从 `pcm.mapped.*` 自己算，不许要求 Core 增加端口。

## 2 · 这个文件为什么存在

本文件是「**Core 预生成**」这一架构裁定的**落地处**（不可推翻的负责人裁定）。

存在理由追溯到 Product Intent / Requirement：产品承诺「双音频对比 → 客观数值指标」，且指标必须可定位到「第 7 个音偏低 40 音分」这种可行动结论，而非「整体误差 40 音分」。要做到可定位，就必须在 Seal 时已存在逐帧音高曲线与逐音摘要。

为什么不惰性现算：惰性计算要活下来必须定义一套协商协议（特征声明 → 解析 → 版本 → 缓存失效 → 算失败的语义）。一旦有了那套协议，**Core 的外部接口就成了插件需求的函数** —— 正是「深组件」要消灭的反模式。故本文件把算法要的一切在 Seal 时算好。

**删掉它会坏掉什么**：12 个端口里 8 个消失，三个算法模块全部拿不到输入（音准无 `pitch`、节奏无 `rms`、对齐无 `chroma`、逐音定位无 `notes`），`contract.FIELD_LAYOUTS` 中 `pitch` / `chroma` / `notes` 三张布局表失去唯一生产者，Seal 无法完成端口装配，整条比较链路在 Seal 阶段即失败。

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：
- Python 标准库：`from __future__ import annotations`（`annotations` 唯一允许项）
- 第三方：`numpy`（≥1.24）· `numpy.typing`（`npt`）· `librosa`（**0.11.0**，实测版本）
- 本包内：`..profile`（`PORTS` / `PORT_INDEX` / `AUDIO` / `MATERIALIZE`）· `..contract`（`FIELD_LAYOUTS` / `ErrorCode` / `CoreBuildError`）

> ★ **路径修正（本版修正的一处真实错误）**：上一版此处写作
> `harmonica_eval.profile` / `harmonica_eval.contract` —— **这两个模块不存在**。
> 实际位置是**包根**的 `harmonica_eval/profile.py` 与 `harmonica_eval/contract.py`。
> 本文件位于 `harmonica_eval/core/features.py`，故正确的写法是**两级相对导入**：
> ```python
> from ..profile import AUDIO, MATERIALIZE, PORTS, PORT_INDEX
> from ..contract import FIELD_LAYOUTS, ErrorCode, CoreBuildError
> ```
> 上一版的写法会让实现者写出 `ModuleNotFoundError: No module named 'harmonica_eval.profile'`。

**禁止 import**：
- 任何下游方向模块：`..algorithms.*`、任何算法实现模块（依赖方向只允许 algorithms → core，禁止 core → algorithms）
- 任何解码 / 重采样 / 文件 IO 模块（`soundfile`、`wave`、`pathlib` 的 IO 用法、`os` 文件操作）
- 任何绘图 / 打印 / 日志模块（`matplotlib`、`logging`、`print` 到 stdout）
- `scipy`、`pandas`、`sklearn`、`torch`、`torchcrepe`、`numba`、`cython`
- 任何不在上述清单里的东西

> ★ `torchcrepe` 在**禁止**名单里，但这不是"永远不许用"——
> 它意味着**当前版本不引入神经网络引擎**（见 §4.0 的引擎条款与 §11）。
> 若负责人裁定改用 `torchcrepe`，那是一次**规格变更**（会同时改本清单与 §4.0），
> 不是实现者可以自行决定的事。

## 4 · 你要实现什么（行为规格）

### 4.0 ★★ 引擎选型：为什么本文件写「首选 pYIN」而不是「就是 pYIN」

**这是本版最重要的一处修正，实现者必须先读懂它，再写 `materialize_pitch`。**

**SPEC.md@v2.1 §7.5 的原文裁定：**

> **引擎选型不在此处冻结。** 候选（`torchcrepe` 神经网络 / `librosa.pyin` 传统 DSP）
> 作为实现候选记录在 `COMPONENTS.md`，**不具约束力**。
> 但 §7.5 要求：最终选定前，必须有一次**对照实验**，用数据决定选型。

**上一版本文件犯的错**：它把「估计器为 `librosa.pyin`」写成了**冻结规格**。
但本文件是**冻结产物**（§30），且开头写着「实现者**不得**修改本文件」——
于是那句"估计器为 pyin"实际上把一个 SPEC 明确**不冻结**的决定**冻结掉了**。
后果不是抽象的：

1. 实现者会照着 pYIN 写，因为文档是冻结的、且被要求不得质疑；
2. SPEC §7.5 要求的那场**对照实验永远不会发生**（没人会去挑战一份冻结文档）；
3. 输的那一方（可能是 `torchcrepe`）**再也没有机会进来**。

这正是本项目一直在防的那类错误 —— **把"待定"偷偷变成"已定"，
并伪装成权威**。与早先那次「伪造宪章引用」是同一族缺陷：
一句凭印象写下的判断，进了文档，随后看起来就像事实。

**本版的正确口径（实现者照此执行）：**

| 项 | 规定 |
| --- | --- |
| **首选实现** | `librosa.pyin`。它是**默认路径**，实现者应当先把它跑通 |
| **是否冻结** | **不冻结。** 引擎是可替换的实现选型 |
| **替换条件** | 替换**必须**附一次对照实验的数据（见 §11），且**须经负责人裁定** |
| **实现者能否自行换** | **不能。** 你认为 pYIN 不合适 → 按 §10 上报，不要自行换 |
| **本文件的 §4 规格约束的是什么** | 约束的是**行为**（输出的形状 / 字段顺序 / 单位 / 未发声语义 / 不变量），**不是**引擎身份 |

★ **关键区分**：本文件对 `materialize_pitch` 的**全部**硬性规定
（形状 `(n_frames, 3)`、字段顺序 `FIELD_LAYOUTS['pitch']`、
未发声 `f0_hz=0 且 voiced=0`、禁止 NaN、`confidence` 取值域）
**都是引擎无关的** —— 换任何引擎都必须满足。
这正是「冻结行为，不冻结结构」（COMPONENTS.md §39 引用 §43）的落地方式：
**契约是行为，选型是内部实现。**

---

模块级常量（已存在于目标文件，**保持名字、类型、数值不变**）：

- `MIN_STABLE_NOTE_SEC: float = 0.150` —— 参与音准统计的最短音长（秒）。
- `VOICED_CONFIDENCE_FLOOR: float = 0.5` —— 低于此置信度的帧视为未发声。

**★ 阈值口径（冻结，不得自行选择）**：
- 未发声判定阈值 = `VOICED_CONFIDENCE_FLOOR` = **0.5**；判据为 `confidence < 0.5 ⇒ voiced == 0`（严格小于；`confidence == 0.5` 视为**发声**）。
- 成音最短时长阈值 = `MIN_STABLE_NOTE_SEC` = **0.150 秒**；判据为片段时长 `≥ 0.150` 秒（严格按 `≥`；等于 0.150 秒的片段**成音**）。
- 单位换算：音高一律 **Hz**（绝对音高），本文件内**不做**任何 Hz→音分、Hz→MIDI、Hz→chroma 的换算。RMS 一律**线性 RMS**，本文件内**不做** dB 换算。
- 时间基准：`onset_sec` 为**片段首帧**在输入 `samples` 中的时间位置，单位秒，以 `samples[0]` 为 0.0；等价于帧索引 × 帧移 ÷ `sample_rate`。

**★ 帧参数的唯一来源（本版修正）**：
- `pitch_frame_length` / `pitch_hop_length` / `rms_frame_length` / `rms_hop_length`
  / `fmin_hz` / `fmax_hz` —— 全部取自 `profile.MATERIALIZE`。
- **`chroma_frame_length` / `chroma_hop_length` 不存在**（上一版引用了这两个名字，是错的）。
  chroma 的帧移取 `profile.ALIGN.hop_length`（= **2048**），
  这与 `profile.PORTS` 中 `chroma.lowres.*` 声明的 `hop_length=2048` **一致**
  —— 该端口就是给对齐用的，故与对齐用同一个帧移。
  chroma 的窗长取 `profile.MATERIALIZE.frame_length`（= 2048）。
- `fmin` / `fmax` 的正确名字是 **`fmin_hz` / `fmax_hz`**（上一版写作 `pitch_fmin` / `pitch_fmax`，是错的）。

### `materialize_pitch(samples: npt.NDArray, sample_rate: int) -> npt.NDArray`

- **输入**：`samples` 为 1-D `float32` 单声道 PCM，取值域 `[-1.0, 1.0]`；`sample_rate` 为 int，调用方保证等于 `profile.AUDIO.sample_rate`。空数组（长度 0）为合法输入。
- **输出**：2-D `float32` ndarray，形状 `(n_frames, n_fields)`，`n_fields` 取自 `len(contract.FIELD_LAYOUTS['pitch'])`，字段顺序取自 `contract.FIELD_LAYOUTS['pitch'] = (f0_hz, voiced, confidence)`。
- **算法口径**：逐帧估计器在**调用方给定的 `sample_rate` 上运行**，帧参数取 `profile.MATERIALIZE.pitch_frame_length` / `pitch_hop_length`，`fmin` / `fmax` 取自 `profile.MATERIALIZE.fmin_hz` / `fmax_hz`。
  - **首选实现**：`librosa.pyin`（默认路径，见 §4.0 的引擎条款）。
    `f0_hz` = pYIN 输出的基频（Hz）；`confidence` = pYIN 的 `voiced_prob`；
    `voiced` = `(confidence >= VOICED_CONFIDENCE_FLOOR)` 的 0/1 整数。
  - ★ **但引擎不冻结**：以上仅规定**首选实现**与**必须满足的行为**。
    换引擎的完整条件见 §4.0 与 §11 —— 实现者**不得自行替换**。
  - ★ **若替换引擎**，`confidence` 的语义仍是「该帧发声的置信度，值域 `[0,1]`」。
    不同引擎的置信度**不可直接比较**（pYIN 的 `voiced_prob` 与神经网络的
    sigmoid 输出不是同一个量），故替换时**必须**同步提交 §11 要求的对照实验。
- **边界**：`samples` 长度 0 ⇒ 返回形状 `(0, n_fields)` 的空数组，不抛异常。帧数不足一帧（`len(samples) < pitch_frame_length`）⇒ 以 `center=True` 补齐后仍产出 1 帧，按正常路径返回。未发声帧 ⇒ `f0_hz = 0.0` **且** `voiced = 0`，`confidence` 如实报告（不置 0、不置 1）。输入含 NaN/inf ⇒ 抛 `CoreBuildError(ErrorCode.CORE_BUILD_FAILED)`（见 §5），**不得**产出含 NaN 的输出。
- **不变量**：输出中 `np.isnan(...).any() == False` 且 `np.isinf(...).any() == False`（**禁止用 NaN 表示未发声** —— NaN 会静默污染中位数/均值统计）；`voiced == 0` 的行其 `f0_hz == 0.0`；`voiced` 列取值集合 ⊆ `{0.0, 1.0}`；`confidence` 列取值域 `[0.0, 1.0]`。

### `materialize_rms(samples: npt.NDArray) -> npt.NDArray`

- **输入**：`samples` 为 1-D `float32` 单声道 PCM；空数组为合法输入。本函数**不接收** `sample_rate`。
- **输出**：1-D `float32` ndarray，形状 `(n_frames,)`，**线性 RMS**，值域 `[0.0, 1.0]`（输入域 `[-1.0, 1.0]` 下）。
- **算法口径**：为每帧计算 `sqrt(mean(x[i]**2))`，帧窗长 = `profile.MATERIALIZE.rms_frame_length`，帧移 = `profile.MATERIALIZE.rms_hop_length`（刻意比音高窗密，以保留起音瞬态）；无补零以外的窗函数加权，即以矩形窗直接求均方根。帧数计算：`n_frames = 1 + (len(samples) - rms_frame_length) // rms_hop_length`，当 `len(samples) < rms_frame_length` 时按 `librosa.util.frame` 的补零语义产出 1 帧。
- **边界**：`samples` 长度 0 ⇒ 返回形状 `(0,)` 的空数组，不抛异常。全零输入 ⇒ 返回全 `0.0`（静音是真实测量值，不是失败）。单元素输入 ⇒ 返回 1 帧。输入含 NaN/inf ⇒ 抛 `ErrorCode.CORE_BUILD_FAILED`（见 §5）。
- **不变量**：输出无 NaN、无 inf；输出全部 `>= 0.0`；**本函数不做 dB 换算** —— 转 dB 是算法侧的表达选择。

### `materialize_chroma(samples: npt.NDArray) -> npt.NDArray`

- **输入**：`samples` 为 1-D `float32` 单声道 PCM；空数组为合法输入。本函数**不接收** `sample_rate`。
- **输出**：2-D `float32` ndarray，形状 `(n_frames, 12)`，字段顺序取自 `contract.FIELD_LAYOUTS['chroma']`，**bin 0 = C**（不是 A）；bin 索引 `k` 对应音级 `(C, C#, D, D#, E, F, F#, G, G#, A, A#, B)[k]`。
- **算法口径**：`librosa.feature.chroma_stft`，帧参数取 `profile.MATERIALIZE.frame_length`（窗长）/ `profile.ALIGN.hop_length`（帧移 = 2048，与 `profile.PORTS` 中 `chroma.lowres.*` 声明的 `hop_length` 一致），`n_chroma = 12`，`tuning = 0.0`（不估计调音偏移，保证可复现），`norm = np.inf`（逐帧无穷范数归一化），`center = True`。**低分辨率**：`n_chroma` 固定 12，不做 36/120 维高阶 chroma。
- **边界**：`samples` 长度 0 ⇒ 返回形状 `(0, 12)` 的空数组，不抛异常。全零输入（静音）⇒ 返回全 `0.0` 的 `(n_frames, 12)`（不抛异常）。输入含 NaN/inf ⇒ 抛 `ErrorCode.CORE_BUILD_FAILED`（见 §5）。
- **不变量**：输出第二维恒为 12；输出无 NaN、无 inf；逐帧 L∞ 范数为 `0.0`（静音帧）或 `1.0`。**本端口明确不作为评分依据** —— chroma 八度不变，无法区分 C4 与 C5；保留在数据面里是为了让审查者能重跑对齐、验证 `warp_path` 不是凭空来的。

### `materialize_notes(pitch: npt.NDArray, rms: npt.NDArray, sample_rate: int) -> npt.NDArray`

- **输入**：`pitch` 为 `materialize_pitch` 的输出（形状 `(n_frames, n_fields)`，字段顺序 `(f0_hz, voiced, confidence)`）；`rms` 为 `materialize_rms` 的输出（形状 `(n_frames,)`）；`sample_rate` 为 int，与生成 `pitch` 时相同。`pitch` 与 `rms` 帧数不同（各自帧移不同），按**时间**而非索引对齐。
- **输出**：2-D `float32` ndarray，形状 `(n_notes, n_fields)`，`n_fields` 取自 `len(contract.FIELD_LAYOUTS['notes'])`，字段顺序取自 `contract.FIELD_LAYOUTS['notes'] = (onset_sec, f0_hz, rms)`。
- **算法口径**：
  1. 在 `voiced` 列上做**连续段切分**：`voiced == 1` 的相邻帧构成同一片段，遇到 `voiced == 0` 即断开。
  2. 片段时长 = `片段帧数 × pitch_hop_length ÷ sample_rate`，保留 `voiced` 列上**首帧**为其起点。
  3. 仅保留时长 `>= MIN_STABLE_NOTE_SEC`（= 0.150 秒）的片段成音；短于此的片段**丢弃**（不合并、不补零、不产生行）。
  4. 每音一行：`onset_sec` = 片段首帧时间（秒，以 `samples[0]` 为 0.0，= 帧索引 × `pitch_hop_length` ÷ `sample_rate`）；`f0_hz` = 片段内 `voiced == 1` 帧的 `f0_hz` **中位数**（Hz，绝对音高，不 chroma 化）；`rms` = 片段在时间上覆盖的 `rms` 帧的**中位数**（线性 RMS）。时间覆盖口径：`rms` 帧索引 `j` 满足 `j × rms_hop_length` 落在 `[片段起始样本, 片段结束样本)` 内。
  5. 输出行按 `onset_sec` **升序**排列。
- **边界**：`pitch` 为空或无任何满足时长阈值的片段 ⇒ 返回形状 `(0, n_fields)` 的空数组，不抛异常。`rms` 为空 ⇒ 抛 `ErrorCode.CORE_BUILD_FAILED`（见 §5），**不得**用 0 或该片段外数据填充。片段中位数恰好落在两帧之间 ⇒ 取两值算术平均（`numpy.median` 默认口径，不插值到其它值）。
- **不变量**：输出无 NaN、无 inf；`onset_sec` 严格递增（升序，且因片段互不重叠而不相等）；每行 `f0_hz > 0.0`；每行对应的片段时长 `>= 0.150` 秒；输出行数 `<=` `pitch` 中 `voiced == 1` 的帧数。

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| `samples` 含 NaN 或 inf | 显式失败，不降级 | `ErrorCode.CORE_BUILD_FAILED` |
| `materialize_notes` 收到含 NaN/inf 的 `pitch` 或 `rms` | 显式失败，不降级 | `ErrorCode.CORE_BUILD_FAILED` |
| `sample_rate <= 0` | 显式失败，不降级 | `ErrorCode.CORE_BUILD_FAILED` |
| `materialize_notes` 的 `pitch` / `rms` 为 0 维或形状不符（`pitch.ndim != 2`、`rms.ndim != 1`） | 显式失败，不降级 | `ErrorCode.CORE_BUILD_FAILED` |
| `materialize_notes` 的 `pitch.shape[1] != len(FIELD_LAYOUTS['pitch'])` | 显式失败，不降级 | `ErrorCode.CORE_BUILD_FAILED` |
| `samples` 为空数组（长度 0） | 降级为空结果（合法输入） | 返回空数组，不抛 |
| 纯静音输入 | 降级为空结果（合法输入） | `pitch` 全 `voiced=0`；`rms` 全 `0.0`；`chroma` 全 `0.0`；`notes` 为空数组 |
| 帧数不足一帧 | 按补零语义产出 1 帧，正常返回 | 返回该帧结果 |
| 端口名不在 `profile.PORTS` | 显式失败，不降级 | `ErrorCode.CORE_BUILD_FAILED` |
| 估计器（`librosa`）内部失败 | 显式失败，不降级 | `ErrorCode.CORE_BUILD_FAILED` |

★ 宪章 §5.6：**禁止静默降级**。任何「算不出来就返回默认值」的行为被本条明确禁止 —— 除上表列出的空输入 / 静音两类**合法输入**外，本文件**不得**返回 0、空数组或任何默认值来掩盖失败。失败必须抛出上表列出的错误码。

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-103-1 | 端口生成严格由 `profile.PORTS` 驱动，**不硬编码端口名列表** | `assert 'pitch' not in inspect.getsource(features).replace("FIELD_LAYOUTS","")` 一类的白盒断言：源码中不出现端口名作为字面量集合；`assert set(FIELD_LAYOUTS) >= {'pitch','chroma','notes'}` 由 profile 侧满足 |
| INV-103-2 | 多维度端口字段顺序取自 `contract.FIELD_LAYOUTS`，不自行排列 | `assert FIELD_LAYOUTS['pitch'] == ('f0_hz','voiced','confidence')`；`assert FIELD_LAYOUTS['notes'] == ('onset_sec','f0_hz','rms')` |
| INV-103-3 | 音高是**绝对音高（Hz）**，未 chroma 化 | `assert pitch[pitch[:,1]==1][:,0].max() > 200.0`（男声口琴实测基频上限远超一个八度带）；`assert not np.array_equal(np.sort(np.unique(pitch[:,0])), np.arange(12))` |
| INV-103-4 | 未发声帧 `f0_hz == 0` 且 `voiced == 0`，**未使用 NaN** | `assert not np.isnan(pitch).any()`；`assert (pitch[pitch[:,1]==0][:,0] == 0.0).all()` |
| INV-103-5 | `confidence < VOICED_CONFIDENCE_FLOOR` ⇒ `voiced == 0` | `assert (pitch[pitch[:,2] < VOICED_CONFIDENCE_FLOOR][:,1] == 0).all()` |
| INV-103-6 | 音高估计**不在降采样音频上运行** | 断言调用 `materialize_pitch(samples, sr)` 内部使用的帧参数与 `sr` 均为入参；`assert calls['sample_rate'] == profile.AUDIO.sample_rate`（在 `sr = profile.AUDIO.sample_rate` 下调用时） |
| INV-103-7 | `materialize_rms` 输出**线性 RMS**，未转 dB | `assert (rms >= 0.0).all()`；`assert rms.max() <= 1.0`；`assert not np.allclose(rms, 20*np.log10(np.maximum(rms,1e-12)), atol=1e-6)` |
| INV-103-8 | `materialize_chroma` 第二维恒为 12，且 **bin 0 = C** | `assert chroma.shape[1] == 12`；`assert FIELD_LAYOUTS['chroma'][0] == 'C'` |
| INV-103-9 | `notes` 只对 `voiced` 且连续时长 `>= MIN_STABLE_NOTE_SEC` 的片段成音 | `assert (np.diff(notes[:,0]) > 0).all()`；`assert notes.shape[0] <= (pitch[:,1]==1).sum()`；对每个 `onset_sec` 断言对应片段帧数 × hop ÷ sr `>= MIN_STABLE_NOTE_SEC` |
| INV-103-10 | `notes` 行按 `onset_sec` 升序且无重复 | `assert (np.diff(notes[:,0]) > 0).all()` |
| INV-103-11 | 输出不含 NaN / inf（任何端口、任何输入） | `assert not np.isnan(out).any() and not np.isinf(out).any()`，对 `pitch` / `rms` / `chroma` / `notes` 四个输出各断言一次 |
| INV-103-12 | 空输入返回空数组而非抛异常 | `assert materialize_pitch(np.zeros(0, np.float32), sr).shape == (0, len(FIELD_LAYOUTS['pitch']))`；`assert materialize_rms(np.zeros(0, np.float32)).shape == (0,)`；`assert materialize_chroma(np.zeros(0, np.float32)).shape == (0, 12)`；`assert materialize_notes(np.zeros((0, len(FIELD_LAYOUTS['pitch'])), np.float32), np.zeros(0, np.float32), sr).shape == (0, len(FIELD_LAYOUTS['notes']))` |

## 7 · 边界（明确不做）

- **不实现任何算法**：不在本文件内计算音准误差、节奏偏差、音分、相似度、评分。
- **不做 Hz→音分 / Hz→MIDI / Hz→chroma 换算**，不做 RMS→dB 换算。这些是算法侧的表达选择。
- **不做音量归一化、去噪、降噪、去混响、VAD 以外的门限处理**。
- **不降采样**：不得为了速度把输入降到 22.05 kHz（实测：22.05 kHz 下 D5 被判成 D4，恰好 −1200 音分）。
- **不 chroma 化音高**：chroma 八度不变，会把差一个八度的错音判成正确。
- **不在未发声帧上给出 f0 猜测值**（宁可为 0 + `voiced=0`）。
- **不新增端口**，不新增 `profile.PORTS` 之外的键；用户要求新端口时转 §10。
- **不写文件、不打印、不记录日志、不绘图**。
- **不做缓存、不做惰性求值、不做特征声明/版本协商协议**（那正是本架构要消灭的反模式）。
- **不引入任何未被 `profile.MATERIALIZE` 声明的参数**；`profile.MATERIALIZE` 中不存在的帧长/帧移不得由实现者自选。
- 若你发现「不做这个就实现不了」→ **不要做**，转 §10。

## 8 · 怎么验证你写对了

```bash
# 1. 公开符号存在且签名一致
python -c "import inspect, harmonica_eval.core.features as f; \
print(inspect.signature(f.materialize_pitch)); print(inspect.signature(f.materialize_rms)); \
print(inspect.signature(f.materialize_chroma)); print(inspect.signature(f.materialize_notes))"

# 2. 常量冻结
python -c "import harmonica_eval.core.features as f; \
assert f.MIN_STABLE_NOTE_SEC == 0.150; assert f.VOICED_CONFIDENCE_FLOOR == 0.5; print('const ok')"

# 3. 契约字段顺序未被改动
python -c "from harmonica_eval.contract import FIELD_LAYOUTS as L; \
assert tuple(L['pitch']) == ('f0_hz','voiced','confidence'); \
assert tuple(L['notes']) == ('onset_sec','f0_hz','rms'); \
assert len(L['chroma']) == 12 and L['chroma'][0] == 'C'; print('layout ok')"

# 4. 空输入与静音语义
python -c "
import numpy as np, harmonica_eval.core.features as f
from harmonica_eval.contract import FIELD_LAYOUTS as L
from harmonica_eval.profile import AUDIO
sr = AUDIO.sample_rate
z = np.zeros(0, np.float32)
assert f.materialize_pitch(z, sr).shape == (0, len(L['pitch']))
assert f.materialize_rms(z).shape == (0,)
assert f.materialize_chroma(z).shape == (0, 12)
assert f.materialize_notes(np.zeros((0, len(L['pitch'])), np.float32), z, sr).shape == (0, len(L['notes']))
q = np.zeros(sr, np.float32)
assert not np.isnan(f.materialize_pitch(q, sr)).any()
assert (f.materialize_pitch(q, sr)[:, 1] == 0).all()
assert (f.materialize_rms(q) == 0.0).all()
assert f.materialize_notes(f.materialize_pitch(q, sr), f.materialize_rms(q), sr).shape[0] == 0
print('empty/silence ok')"

# 5. 未发声帧零值与无 NaN
python -c "
import numpy as np, harmonica_eval.core.features as f
from harmonica_eval.profile import AUDIO
sr = AUDIO.sample_rate
t = np.arange(sr, dtype=np.float32) / sr
sig = (0.4 * np.sin(2*np.pi*440.0*t)).astype(np.float32)
p = f.materialize_pitch(sig, sr)
assert not np.isnan(p).any() and not np.isinf(p).any()
vf = p[p[:, 1] == 0]
assert (vf[:, 0] == 0.0).all()
assert (p[p[:, 2] < f.VOICED_CONFIDENCE_FLOOR][:, 1] == 0).all()
vo = p[p[:, 1] == 1]
assert len(vo) > 0 and abs(np.median(vo[:, 0]) - 440.0) < 5.0
r = f.materialize_rms(sig)
assert (r >= 0.0).all() and r.max() <= 1.0 and abs(r.max() - 0.4/np.sqrt(2)) < 0.02
c = f.materialize_chroma(sig)
assert c.shape[1] == 12
assert np.allclose(np.linalg.norm(c, ord=np.inf, axis=1)[np.linalg.norm(c, ord=np.inf, axis=1) > 0], 1.0)
n = f.materialize_notes(p, r, sr)
assert n.shape[1] == len(__import__('harmonica_eval.contract', fromlist=['x']).FIELD_LAYOUTS['notes'])
assert (np.diff(n[:, 0]) > 0).all() if n.shape[0] > 1 else True
assert (n[:, 1] > 0).all() if n.shape[0] > 0 else True
assert n.shape[0] <= (p[:, 1] == 1).sum()
print('numeric ok', n.shape)"
```

**验收判据**（可机械判定的，而非「看起来对」）：
- [ ] 上述 5 条命令全部以退出码 0 结束，且依次打印 `const ok` / `layout ok` / `empty/silence ok` / `numeric ok`。
- [ ] `assert not np.isnan(out).any()` 对 `pitch` / `rms` / `chroma` / `notes` 四个输出在**空输入、静音、440 Hz 正弦**三种输入下均成立。
- [ ] `assert (pitch[pitch[:,1]==0][:,0] == 0.0).all()` 成立（未发声帧 f0 为 0）。
- [ ] `assert (rms >= 0.0).all() and rms.max() <= 1.0` 成立（线性 RMS，未转 dB）。
- [ ] `assert chroma.shape[1] == 12 and FIELD_LAYOUTS['chroma'][0] == 'C'` 成立。
- [ ] `assert notes.shape[0] <= (pitch[:,1]==1).sum()` 且 `assert (np.diff(notes[:,0]) > 0).all()` 成立。
- [ ] `grep -n "NotImplementedError" harmonica_eval/core/features.py` 无输出（4 个 SHELL 全部落地）。
- [ ] `assert f.MIN_STABLE_NOTE_SEC == 0.150 and f.VOICED_CONFIDENCE_FLOOR == 0.5` 成立。
- [ ] 440 Hz 正弦输入下 `abs(np.median(pitch[pitch[:,1]==1][:,0]) - 440.0) < 5.0` 成立（±5 Hz 容差）。

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] 产物路径：`harmonica_eval/core/features.py`（4 个公开符号全部实现，无 `NotImplementedError`）
- [ ] 测试输出：§8 五条命令的完整 stdout 与退出码
- [ ] 若涉及数值：440 Hz 正弦的 `pitch` 中位数对比结果（期望 `440.0 ± 5.0` Hz）、`rms` 峰值对比结果（期望 `0.4/√2 ± 0.02`）
- [ ] 契约未改动证据：`contract.FIELD_LAYOUTS` / `profile.PORTS` 的 diff 为空
- [ ] 依赖封闭证据：`harmonica_eval/core/features.py` 的 import 段与 §3 清单逐项一致

## 10 · ★ 何时必须停止并上报（§22 硬失败对策）

**以下情况必须停止，提交 `MOLD BREAK`，不得自行设计：**

1. 你发现本文件**需要做上层设计**才能实现（例如：需要决定一个新阈值 / 新口径 / 新端口 / 新错误码）
2. 本文件与任何上游工件**冲突**（`SPEC.md` / `profile.py` / `contract.py` / 目标文件模块 docstring）
3. 你需要的依赖**不在 §3 清单里**
4. §4 的行为规格**不足以确定唯一实现**（例如 `profile.MATERIALIZE` 未声明某个帧长 / 帧移，而你无法从清单内取得）
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

**绝对禁止**：
- 先做一个「能跑的 workaround」，以后再说（§38 明文禁止）
- 自行在代码里加一个「合理的」默认值把冲突掩盖过去
- 静默缩小范围（「这个分支我先不实现」）

---

## 11 · ★ 引擎对照实验（SPEC §7.5 的硬要求）

> **本节不是"实现者的任务"，是"上游尚未完成的事"。**
> 它存在于此，是因为 SPEC §7.5 要求它**必须发生**，
> 而上一版本文件通过"把 pYIN 冻结掉"事实上**取消了它**。

### 11.1 为什么必须有这场实验

SPEC.md@v2.1 §7.5 原文：

> 但 §7.5 要求：最终选定前，必须有一次**对照实验**，用数据决定选型。

理由不是形式主义。`torchcrepe`（神经网络）与 `librosa.pyin`（传统 DSP）
在本项目的关键场景上**预期行为不同**：

| 维度 | pYIN（传统 DSP） | torchcrepe（神经网络） | 对本项目的影响 |
| --- | --- | --- | --- |
| 口琴高次谐波 | 自相关类方法易被强谐波误导 | 训练数据驱动，预期更稳 | ★ 口琴谐波极丰富，这是核心风险 |
| 弯音 / 滑音 | 逐帧独立，过渡段易碎 | 时序建模，预期更连贯 | 影响 `notes.*` 切分 |
| 弱音起音 | 依赖 `voiced_prob` 阈值 | 概率输出更平滑 | 影响 `VOICED_CONFIDENCE_FLOOR=0.5` 是否合适 |
| 速度 | 较慢（本项目 45–120 s，可接受） | 需 GPU 或较慢 CPU | 影响 Mac 本机体验 |
| 依赖体积 | 已装 | 引入 torch（数百 MB） | 影响 C4 与手机端可行性 |
| 可复现性 | 确定性 | 权重固定时确定 | 影响黄金向量 |

**上表是"预期"，不是"结论"** —— 写在这里是为了说明**为什么值得测**，
不是为了让实现者据此选 pYIN。**最终以实验数据为准。**

### 11.2 实验设计（冻结，不得自行更改）

| 项 | 规定 |
| --- | --- |
| **输入语料** | 数据集 01 号曲的**全部 7 个 wav**（`原曲_完整版` / `标准旋律版` / 5 个练习曲变体） |
| **必须加入的困难样本** | ① `01_音准走调.wav`（测走音是否被正确判出）② `05_漏音断句.wav`（测漏音处是否误报音高） |
| **对照指标** | ① **稳定音中位绝对误差**（音分）② **八度错误率**（判成 ±1200 音分的音占比）③ **`voiced` 判决一致率**（两引擎在同一帧上是否同意发声）④ **逐音 `onset_sec` 差异**（秒）⑤ **单曲耗时**（秒）⑥ **峰值内存**（MB） |
| **判定基准** | MIDI 真值（数据集构建时已知，**不是**另一个引擎的输出） |
| **验收门槛** | 稳定音中位绝对误差 ≤ 50 音分（SPEC §7.3）；**八度错误率必须为 0** —— 硬门槛，因为 chroma 化的历史教训正是"八度错误不可见" |
| **产出物** | `.spec/ENGINE-COMPARISON.md`：逐指标对照表 + 原始数字 + 可复现命令 |
| **裁定权** | **负责人**。实验只提供数据，不做选择 |

### 11.3 实现者此刻应当做什么

| 情形 | 动作 |
| --- | --- |
| 你正在实现 `materialize_pitch` | **用 pYIN 实现**（首选路径），**不要**等实验 |
| 你认为 pYIN 在口琴上明显不合格 | 按 §10 提交 `MOLD BREAK`，附上你观察到的具体反例 |
| 你想"顺手试试 torchcrepe" | **不要。** 那是超出本文件范围的行为，见 §7 |
| 实验做完后负责人裁定换引擎 | 那时会有**新版本的 Build Instruction**；届时按新版本改 |

★ **关键**：本节的目的是**让那场实验不被遗忘**，不是**让实现者去做它**。
实现者按 pYIN 交付即可 —— 交付物中不要求包含本实验。

### 11.4 本节的登记状态

| 项 | 状态 |
| --- | --- |
| SPEC §7.5 要求 | 引擎选型不冻结 + 必须有对照实验 |
| 实验是否已做 | ❌ **未做** |
| 当前默认引擎 | `librosa.pyin`（**首选实现**，非冻结选型） |
| 阻塞谁 | 不阻塞代码注入（pYIN 路径可先跑）；**阻塞"引擎选型冻结"这个决定本身** |
| 谁负责 | 上游（负责人裁定 + 助手执行实验） |
| 已登记于 | `.spec/graph/overlay.json` 的 `known_gaps`（见 GAP-6） |

---

## 附：本文件的冻结常量速查

| 常量 | 值 | 来源 |
| --- | --- | --- |
| `MIN_STABLE_NOTE_SEC` | `0.150` 秒 | `harmonica_eval/core/features.py:48` |
| `VOICED_CONFIDENCE_FLOOR` | `0.5` | `harmonica_eval/core/features.py:55` |
| `FIELD_LAYOUTS['pitch']` | `(f0_hz, voiced, confidence)` | `contract.FIELD_LAYOUTS` |
| `FIELD_LAYOUTS['chroma']` | 12 项，bin 0 = C | `contract.FIELD_LAYOUTS` |
| `FIELD_LAYOUTS['notes']` | `(onset_sec, f0_hz, rms)` | `contract.FIELD_LAYOUTS` |
| `pitch_frame_length` / `pitch_hop_length` | 引用常量名，不抄数字 | `profile.MATERIALIZE` |
| `rms_frame_length` / `rms_hop_length` | 引用常量名，不抄数字 | `profile.MATERIALIZE` |
| chroma 窗长 / 帧移 | 引用常量名，不抄数字 | `profile.MATERIALIZE.frame_length` / `profile.ALIGN.hop_length` |
| `fmin_hz` / `fmax_hz` | 引用常量名，不抄数字 | `profile.MATERIALIZE` |
| `sample_rate` | 引用常量名，不抄数字 | `profile.AUDIO.sample_rate` |
| 由本文件生产的端口数 | 8 / 12 | `profile.PORTS` |
