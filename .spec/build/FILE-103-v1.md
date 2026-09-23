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
- 第三方：`numpy`（≥1.24）· `numpy.typing`（`npt`）· `librosa`（0.10.x）
- 本包内：`harmonica_eval.core.profile`（`PORTS` / `AUDIO` / `MATERIALIZE`）· `harmonica_eval.core.contract`（`FIELD_LAYOUTS` / `ErrorCode`）

**禁止 import**：
- 任何下游方向模块：`harmonica_eval.algorithms.*`、任何算法实现模块（依赖方向只允许 algorithms → core，禁止 core → algorithms）
- 任何解码 / 重采样 / 文件 IO 模块（`soundfile`、`wave`、`pathlib` 的 IO 用法、`os` 文件操作）
- 任何绘图 / 打印 / 日志模块（`matplotlib`、`logging`、`print` 到 stdout）
- `scipy`、`pandas`、`sklearn`、`torch`、`numba`、`cython`
- 任何不在上述清单里的东西

## 4 · 你要实现什么（行为规格）

模块级常量（已存在于目标文件，**保持名字、类型、数值不变**）：

- `MIN_STABLE_NOTE_SEC: float = 0.150` —— 参与音准统计的最短音长（秒）。
- `VOICED_CONFIDENCE_FLOOR: float = 0.5` —— 低于此置信度的帧视为未发声。

**★ 阈值口径（冻结，不得自行选择）**：
- 未发声判定阈值 = `VOICED_CONFIDENCE_FLOOR` = **0.5**；判据为 `confidence < 0.5 ⇒ voiced == 0`（严格小于；`confidence == 0.5` 视为**发声**）。
- 成音最短时长阈值 = `MIN_STABLE_NOTE_SEC` = **0.150 秒**；判据为片段时长 `≥ 0.150` 秒（严格按 `≥`；等于 0.150 秒的片段**成音**）。
- 单位换算：音高一律 **Hz**（绝对音高），本文件内**不做**任何 Hz→音分、Hz→MIDI、Hz→chroma 的换算。RMS 一律**线性 RMS**，本文件内**不做** dB 换算。
- 时间基准：`onset_sec` 为**片段首帧**在输入 `samples` 中的时间位置，单位秒，以 `samples[0]` 为 0.0；等价于帧索引 × 帧移 ÷ `sample_rate`。

### `materialize_pitch(samples: npt.NDArray, sample_rate: int) -> npt.NDArray`

- **输入**：`samples` 为 1-D `float32` 单声道 PCM，取值域 `[-1.0, 1.0]`；`sample_rate` 为 int，调用方保证等于 `profile.AUDIO.sample_rate`。空数组（长度 0）为合法输入。
- **输出**：2-D `float32` ndarray，形状 `(n_frames, n_fields)`，`n_fields` 取自 `len(contract.FIELD_LAYOUTS['pitch'])`，字段顺序取自 `contract.FIELD_LAYOUTS['pitch'] = (f0_hz, voiced, confidence)`。
- **算法口径**：逐帧估计器在**调用方给定的 `sample_rate` 上运行**，帧参数取 `profile.MATERIALIZE.pitch_frame_length` / `pitch_hop_length`，估计器为 `librosa.pyin`，`fmin` / `fmax` 取自 `profile.MATERIALIZE.pitch_fmin` / `pitch_fmax`；`f0_hz` = pYIN 输出的基频（Hz）；`confidence` = pYIN 的 `voiced_prob`；`voiced` = `(confidence >= VOICED_CONFIDENCE_FLOOR)` 的 0/1 整数。
- **边界**：`samples` 长度 0 ⇒ 返回形状 `(0, n_fields)` 的空数组，不抛异常。帧数不足一帧（`len(samples) < frame_length`）⇒ `librosa.pyin` 以 `center=True` 补齐后仍产出 1 帧，按正常路径返回。未发声帧 ⇒ `f0_hz = 0.0` **且** `voiced = 0`，`confidence` 如实报告（不置 0、不置 1）。输入含 NaN/inf ⇒ 抛 `ErrorCode.INVALID_AUDIO`（见 §5），**不得**产出含 NaN 的输出。
- **不变量**：输出中 `np.isnan(...).any() == False` 且 `np.isinf(...).any() == False`（**禁止用 NaN 表示未发声** —— NaN 会静默污染中位数/均值统计）；`voiced == 0` 的行其 `f0_hz == 0.0`；`voiced` 列取值集合 ⊆ `{0.0, 1.0}`；`confidence` 列取值域 `[0.0, 1.0]`。

### `materialize_rms(samples: npt.NDArray) -> npt.NDArray`

- **输入**：`samples` 为 1-D `float32` 单声道 PCM；空数组为合法输入。本函数**不接收** `sample_rate`。
- **输出**：1-D `float32` ndarray，形状 `(n_frames,)`，**线性 RMS**，值域 `[0.0, 1.0]`（输入域 `[-1.0, 1.0]` 下）。
- **算法口径**：为每帧计算 `sqrt(mean(x[i]**2))`，帧窗长 = `profile.MATERIALIZE.rms_frame_length`，帧移 = `profile.MATERIALIZE.rms_hop_length`（刻意比音高窗密，以保留起音瞬态）；无补零以外的窗函数加权，即以矩形窗直接求均方根。帧数计算：`n_frames = 1 + (len(samples) - rms_frame_length) // rms_hop_length`，当 `len(samples) < rms_frame_length` 时按 `librosa.util.frame` 的补零语义产出 1 帧。
- **边界**：`samples` 长度 0 ⇒ 返回形状 `(0,)` 的空数组，不抛异常。全零输入 ⇒ 返回全 `0.0`（静音是真实测量值，不是失败）。单元素输入 ⇒ 返回 1 帧。输入含 NaN/inf ⇒ 抛 `ErrorCode.INVALID_AUDIO`（见 §5）。
- **不变量**：输出无 NaN、无 inf；输出全部 `>= 0.0`；**本函数不做 dB 换算** —— 转 dB 是算法侧的表达选择。

### `materialize_chroma(samples: npt.NDArray) -> npt.NDArray`

- **输入**：`samples` 为 1-D `float32` 单声道 PCM；空数组为合法输入。本函数**不接收** `sample_rate`。
- **输出**：2-D `float32` ndarray，形状 `(n_frames, 12)`，字段顺序取自 `contract.FIELD_LAYOUTS['chroma']`，**bin 0 = C**（不是 A）；bin 索引 `k` 对应音级 `(C, C#, D, D#, E, F, F#, G, G#, A, A#, B)[k]`。
- **算法口径**：`librosa.feature.chroma_stft`，帧参数取 `profile.MATERIALIZE.chroma_frame_length` / `chroma_hop_length`，`n_chroma = 12`，`tuning = 0.0`（不估计调音偏移，保证可复现），`norm = np.inf`（逐帧无穷范数归一化），`center = True`。**低分辨率**：`n_chroma` 固定 12，不做 36/120 维高阶 chroma。
- **边界**：`samples` 长度 0 ⇒ 返回形状 `(0, 12)` 的空数组，不抛异常。全零输入（静音）⇒ 返回全 `0.0` 的 `(n_frames, 12)`（不抛异常）。输入含 NaN/inf ⇒ 抛 `ErrorCode.INVALID_AUDIO`（见 §5）。
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
- **边界**：`pitch` 为空或无任何满足时长阈值的片段 ⇒ 返回形状 `(0, n_fields)` 的空数组，不抛异常。`rms` 为空 ⇒ 抛 `ErrorCode.INVALID_AUDIO`（见 §5），**不得**用 0 或该片段外数据填充。片段中位数恰好落在两帧之间 ⇒ 取两值算术平均（`numpy.median` 默认口径，不插值到其它值）。
- **不变量**：输出无 NaN、无 inf；`onset_sec` 严格递增（升序，且因片段互不重叠而不相等）；每行 `f0_hz > 0.0`；每行对应的片段时长 `>= 0.150` 秒；输出行数 `<=` `pitch` 中 `voiced == 1` 的帧数。

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| `samples` 含 NaN 或 inf | 显式失败，不降级 | `ErrorCode.INVALID_AUDIO` |
| `materialize_notes` 收到含 NaN/inf 的 `pitch` 或 `rms` | 显式失败，不降级 | `ErrorCode.INVALID_AUDIO` |
| `sample_rate <= 0` | 显式失败，不降级 | `ErrorCode.INVALID_AUDIO` |
| `materialize_notes` 的 `pitch` / `rms` 为 0 维或形状不符（`pitch.ndim != 2`、`rms.ndim != 1`） | 显式失败，不降级 | `ErrorCode.INVALID_AUDIO` |
| `materialize_notes` 的 `pitch.shape[1] != len(FIELD_LAYOUTS['pitch'])` | 显式失败，不降级 | `ErrorCode.INVALID_AUDIO` |
| `samples` 为空数组（长度 0） | 降级为空结果（合法输入） | 返回空数组，不抛 |
| 纯静音输入 | 降级为空结果（合法输入） | `pitch` 全 `voiced=0`；`rms` 全 `0.0`；`chroma` 全 `0.0`；`notes` 为空数组 |
| 帧数不足一帧 | 按补零语义产出 1 帧，正常返回 | 返回该帧结果 |
| 端口名不在 `profile.PORTS` | 显式失败，不降级 | `ErrorCode.PORT_NOT_FOUND` |
| 估计器（`librosa`）内部失败 | 显式失败，不降级 | `ErrorCode.PITCH_ESTIMATION_FAILED` |

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
python -c "from harmonica_eval.core.contract import FIELD_LAYOUTS as L; \
assert tuple(L['pitch']) == ('f0_hz','voiced','confidence'); \
assert tuple(L['notes']) == ('onset_sec','f0_hz','rms'); \
assert len(L['chroma']) == 12 and L['chroma'][0] == 'C'; print('layout ok')"

# 4. 空输入与静音语义
python -c "
import numpy as np, harmonica_eval.core.features as f
from harmonica_eval.core.contract import FIELD_LAYOUTS as L
from harmonica_eval.core.profile import AUDIO
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
from harmonica_eval.core.profile import AUDIO
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
assert n.shape[1] == len(__import__('harmonica_eval.core.contract', fromlist=['x']).FIELD_LAYOUTS['notes'])
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
| `chroma_frame_length` / `chroma_hop_length` | 引用常量名，不抄数字 | `profile.MATERIALIZE` |
| `pitch_fmin` / `pitch_fmax` | 引用常量名，不抄数字 | `profile.MATERIALIZE` |
| `sample_rate` | 引用常量名，不抄数字 | `profile.AUDIO.sample_rate` |
| 由本文件生产的端口数 | 8 / 12 | `profile.PORTS` |
