# FILE-101 — harmonica_eval/core/ingest.py

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/core/ingest.py`
> 生成依据：`SPEC.md@v2.1` · `contract.py` · `profile.py@CORE_PROFILE_V0.1` · `COMPONENTS.md`
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-101 |
| 所属组件 | COMP-C2 Audio Core（音频内核；全系统唯一决定「什么算标准输入」的地方） |
| 层级 | L3（symbol / implementation） |
| 上游 | `harmonica_eval/core/api.py::build_surface()` —— C1 通过 `contract.HostContract.build_surface(session_id)` 触发它，它在构建流程里对参考与练习各调用一次 `ingest(uri)`（两次调用走同一条代码路径，本模块不知道谁是参考、谁是练习）。输入只有 `uri: str`：由 C1 的 `set_reference` / `set_practice` 登记的**本地文件系统路径**。本模块不接收 `session_id`，不读会话状态，不产生任何端口。 |
| 下游 | 直接：调用方 `core/api.py` 取走返回值 `npt.NDArray`（float32 / 单声道 / 44100 Hz）。数据的最终去处（**本模块不调用它们中的任何一个**，输出方式是返回值，不是端口）：`core/surface.py` 用它物化 `pcm.mapped.reference`、`pcm.mapped.practice`、`pcm.warped.practice`；`core/features.py` 从它派生 `pitch.reference`、`pitch.practice`、`rms.reference`、`rms.practice`、`chroma.lowres.reference`、`chroma.lowres.practice`、`notes.reference`、`notes.practice`；`core/align.py` 消费 chroma 做 DTW 并产出 `warp_path`。 |
| 同层邻居 | `core/align.py`（`profile.PORTS[*].produced_by == "core.align"`）、`core/features.py`（`produced_by == "core.features"`）、`core/surface.py`（`produced_by == "core.surface"`）、`core/api.py`。四者与本文件同属 COMP-C2 的 L3 实现层，**互不 import**；各自认领 `profile.PORTS` 里声明给自己的端口，职责边界不靠约定而靠 `produced_by` 字段。 |

**你的权限**：只实现本文件。不得修改任何其他文件，不得修改契约，
不得新增端口，不得新增依赖。

---

## 2 · 这个文件为什么存在

**追溯链**：Product Intent「双音频对比 → 客观数值指标」→ Requirement SPEC.md@v2.1 §2（输入音频规格：单声道、44100 Hz、时长 45–120 秒）→ SPEC.md@v2.1 §5.5（两轴分离，要求存在一份统一 PCM 作为两轴的共同底座）→ COMPONENTS.md@v2 §3（COMP-C2 Audio Core 的 ingest 阶段）→ 本文件。

**删掉它会坏掉什么**（逐项，全部可机械判定）：

1. **全系统的「标准输入」没有定义处。** `profile.AUDIO` 只是一张常量表，它声明了目标（44100 Hz / 1 声道 / float32 / [45.0, 120.0] 秒）却不执行任何一步。删掉本文件后，`AudioSpec` 变成无人执行的声明，没有任何代码把任意可解码文件变成 `AudioSpec` 描述的那个东西。`core/surface.py` 与 `core/features.py` 拿不到 PCM，**全部 12 个端口一个都物化不出来**，`build_surface()` 必然失败，会话永远停在 `BUILDING` 或转 `FAILED`。
2. **采样率分叉会以静默的方式改变结论。** 若没有单一入口，「谁先拿到文件谁自己解码」，同一段 D5 在 44.1 kHz 路径上判为 D5、在 22.05 kHz 路径上判为 D4（恰好 −1200 音分）。两条路径都不报错，只是音准指标相差整整一个八度。本文件的存在把采样率从「各模块的实现细节」变成「全系统唯一的一个数字」。
3. **四种输入不合格原因全部无法上报。** `contract.ErrorCode` 里归属 C2 的 `INPUT_UNREADABLE` / `INPUT_TOO_SHORT` / `INPUT_TOO_LONG` / `INPUT_SILENT` 只有本文件的五个函数会产生。删掉它，C1 无法区分「文件损坏」「录音太短」「录音太长」「录了一片寂静」——四者会退化成同一个笼统失败，用户拿不到可行动的失败原因。
4. **时长区间与静音门限失去唯一判决点。** `AudioSpec.min_duration_sec`(=45.0) / `max_duration_sec`(=120.0) 与 `SILENCE_RMS_THRESHOLD`(=1e-4) 都是冻结常量，本文件是它们唯一的执行者。删掉它，规格里的「45–120 秒」就只是一句注释。
5. **「重采样必须显式且可审」这条要求失去唯一落点。** SPEC.md@v2.1 §7.4 明令
   「对齐两侧必须**同率**」——而真实录音的源采样率是**任意**的（44.1 kHz / 48 kHz /
   22.05 kHz 都可能）。要让两侧同率，就必须有一次采样率统一。本仓把它收敛到本文件，
   且**要求这次转换是显式、可单独验证的一步**（故拆出 `resample_to_profile`）。

   ★ 为什么拆成独立函数而不是混在解码里：SPEC §7.4 的实测警告是
   「22.05 kHz 下 D5 被判成 D4（恰好 −1200 音分）」——采样率是**结果的成因**。
   把重采样做成一个能被单独调用、单独断言的公开函数，审查者才能回答
   「到底有没有发生重采样、从多少到多少、有没有引入可测的损失」。
   若混进 `ingest` 的黑盒里，这个因果链就不可审了。

**反面判据（若答不出就不该存在）**：以上五条中的第 3、5 条是本文件独有的——没有任何其他文件能承担「解码失败分类」与「采样率统一的唯一转换点」这两件事。故本文件必须存在。

★ **分层说明（避免与 `core/surface.py` 的表述看起来冲突）**：
`ingest` 是**唯一做重采样的地方**；`surface` 层**不做**重采样，
且见到 ≠44100 Hz 就显式失败（它的判据见 FILE-104 §5）。
两句合起来是**同一条规则的两个位置**：**转换一次，之后人人可以断言它已成立**。
这正是深组件该有的形态 —— 若每层都各自"顺手重采样一下"，
就会出现"N 次重采样、N 套滤波参数"，而采样率是音高结果的成因。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：
- 标准库：`from __future__ import annotations`（文件首行，已在壳里）；`os.path`（只用 `os.path.isfile`，用于「路径不存在/不是普通文件」的显式预检）；`typing`（只在需要标注时用 `Any`）。除此之外的标准库模块一律不得出现，尤其 `wave`、`aifc`、`audioop`、`sunau`、`subprocess`、`shutil`、`tempfile`、`json`、`logging`、`warnings`、`time`、`random`、`pickle`、`hashlib`。
- 第三方：`numpy`（`np.mean` / `np.square` / `np.sqrt` / `np.isfinite` / `np.ascontiguousarray` / `np.float32` / `np.float64`）；`numpy.typing as npt`（`npt.NDArray`，已在壳里）；`soundfile`（**唯一**解码器：`soundfile.SoundFile`、`soundfile.read`、`soundfile.info`、`soundfile.LibsndfileError`）；**`scipy.signal.resample_poly`（唯一的重采样实现）**。除这四个包名外，不得出现任何第三方 import。
- 本包内：`from ..contract import CoreBuildError, ErrorCode`（`harmonica_eval/contract.py`）；`from ..profile import AUDIO`（`harmonica_eval/profile.py`）。本文件位于 `harmonica_eval/core/ingest.py`，故用两级相对导入 `..`。只用 `AUDIO.sample_rate`、`AUDIO.channels`、`AUDIO.dtype`、`AUDIO.min_duration_sec`、`AUDIO.max_duration_sec` 这五个属性；只用 `ErrorCode.INPUT_UNREADABLE`、`ErrorCode.INPUT_TOO_SHORT`、`ErrorCode.INPUT_TOO_LONG`、`ErrorCode.INPUT_SILENT` 这四个枚举值与异常类 `CoreBuildError`。

> ★ **关于 `scipy` 的说明（本清单唯一的例外，必须写清以免实现者困惑）**
>
> 上一版此处把 `scipy` 整体列为禁止——**那是错的**，且与空壳的 MUST
> （「重采样到 profile.AUDIO.sample_rate」）及 SPEC §7.4（「对齐两侧必须同率」）
> 直接矛盾：要求重采样，却禁掉全部重采样实现。
>
> 正确口径：**只允许 `scipy.signal.resample_poly` 这一个符号**，
> 因为它是本仓唯一被批准的采样率统一手段（多相滤波，带抗混叠，可复现）。
> 仍**禁止** `scipy` 的其他一切用法，特别是：
> `scipy.io.wavfile`（绕过 soundfile 解码）、`scipy.signal.resample`
> （FFT 法，边界效应不同，会与 `resample_poly` 产生不同数字）、
> `scipy.signal.decimate` / `interp1d` / 任何滤波器、`scipy.fft`、`scipy.stats`。

**禁止 import**：
- 任何**其他**重采样/变速/变调实现：`librosa`（含 `librosa.resample`、`librosa.effects.time_stretch`）、`soxr`、`resampy`、`samplerate`、`audioop.ratecv`、`ffmpeg`/`ffprobe`（不通过 `subprocess` 或任何绑定间接调用）。**变速与变调在任何情况下都禁止**——那是时间轴拉伸，会破坏 timing 要测的东西。
- 任何其他解码器或容器读取路径：`wave`、`aifc`、`sunau`、`audioread`、`pydub`、`moviepy`、`torchaudio`、`av`、`cv2`、`sounddevice`、`pyaudio`、`scipy.io.wavfile`、`numpy.fromfile` 直读音频字节。
- 任何特征/音高/能量/对齐计算：`librosa`、`pyin`、`crepe`、`aubio`、`praat-parselmouth`、`torch`、`scipy.signal`、`scipy.fft`、`numpy.fft`。特征属于 `core/features.py`（见 §7）。
- 任何降噪/增强/归一化/动态处理：`noisereduce`、`pyloudnorm`、`sklearn`、`scipy.signal`（滤波器/包络/限幅）。
- 本包的其他层与同层模块：`harmonica_eval.host`、`harmonica_eval.algorithms`、`harmonica_eval.cockpit`、`harmonica_eval.core.api`、`harmonica_eval.core.align`、`harmonica_eval.core.features`、`harmonica_eval.core.surface`。本文件只允许向上依赖 `harmonica_eval.contract` 与 `harmonica_eval.profile` 两个**包根**模块，禁止任何同层横向依赖（否则 `core` 内部出现环，import 顺序会变成隐式契约）。

  > ★ 更正（本版）：上一版此处把 `harmonica_eval.core.profile` 也列进了禁止清单。**该模块不存在** —— `profile` 与 `contract` 都在**包根**（`harmonica_eval/profile.py`、`harmonica_eval/contract.py`），不在 `core/` 下。列一个不存在的模块会让读者以为它存在，并去推导一个不成立的依赖方向。
- 任何产生副作用的模块：`os`（只用 `os.path`）、`sys`、`pathlib` 的写操作、`atexit`、`signal`、`multiprocessing`、`threading`、`socket`、`requests`、`urllib`。本文件只读本地文件，不做网络、不写盘、不起线程/进程。
- 环境变量与运行时配置来源：`os.environ`、`configparser`、`dotenv`。全部阈值只能来自 `profile.AUDIO` 与本模块的 `SILENCE_RMS_THRESHOLD`。

★ 本清单必须**穷举**，不许出现「等」「之类」。

---

## 4 · 你要实现什么（行为规格）

### 4.0 模块常量（**必须逐字存在**，审查者会 grep）

```python
SILENCE_RMS_THRESHOLD: float = 1e-4
```

单位：**线性幅度**（float32 归一化到 ±1.0 的刻度），不是 dBFS。
取 `1e-4`（约 −80 dBFS）而非严格 `0`：真实录音总有底噪，
严格判 0 会让"录了一段寂静"被当成有效输入。

`RESAMPLE_*` 之类**不要新增常量**；重采样参数直接引用
`profile.AUDIO.sample_rate`，滤波参数由 §4.2 写死。

---

### 4.1 `decode_to_mono(uri) -> tuple[NDArray, int]`

**职责**：解码为单声道浮点数组，**保持源采样率**（不在此重采样）。

- **输入** `uri: str` —— 本地文件系统路径。`str`，非空。
- **输出** `(samples, native_sample_rate)`：
  - `samples`：一维 `float32` `NDArray`，**单声道**，取值范围 `[-1.0, 1.0]`，
    **连续内存**（`np.ascontiguousarray`）。
  - `native_sample_rate`：`int`，文件的**源**采样率（Hz），> 0。
- **算法口径**（写到可复现同一数组的程度）：
  1. 预检 `os.path.isfile(uri)`；不成立 → `INPUT_UNREADABLE`。
  2. 用 `soundfile.SoundFile(uri)` 打开；任何 `LibsndfileError` / `OSError`
     → `INPUT_UNREADABLE`，`detail` 带原始异常文本。
  3. `soundfile.read(frames=-1, dtype="float32", always_2d=True)`
     —— **必须 `always_2d=True`**，否则单声道文件返回一维、
     多声道返回二维，下混代码要写两个分支（§22 禁止的分叉）。
  4. 下混：`samples = data.mean(axis=1)`（对声道维取**算术平均**）。
     - 单声道时 `mean(axis=1)` 是恒等操作，结果不变。
     - ★ 不得用"只取第 0 声道"：那会静默丢弃其他声道的信息，
       而用户以为整个文件被分析了。
  5. 返回 `(np.ascontiguousarray(mono, dtype=np.float32), int(sf.info(uri).samplerate))`。
- **边界**：
  | 输入 | 行为 |
  | --- | --- |
  | `uri` 非 `str` 或空串 | `INPUT_UNREADABLE` |
  | 路径不存在 / 是目录 | `INPUT_UNREADABLE` |
  | 格式不支持 / 文件损坏 | `INPUT_UNREADABLE` |
  | 采样率为 0 或负 | `INPUT_UNREADABLE`（异常文件） |
  | 0 帧（空音频） | 返回 `(空 float32 数组, sr)`，**不在此抛错**；时长校验在 §4.3 |
  | 多声道 | 下混为单声道（见步骤 4） |
  | 含 `NaN` / `inf` 的样本 | **不在此清理**，原样返回；由 §4.4 的 RMS 计算暴露 |
- **不变量**：`samples.ndim == 1`；`samples.dtype == np.float32`；
  `native_sample_rate > 0`；**本函数绝不改变采样率**。

---

### 4.2 `resample_to_profile(samples, native_sr) -> NDArray`

**职责**：把采样率统一到 `profile.AUDIO.sample_rate`（44100 Hz）。

★ **为什么这一步必须存在而不是"拒绝非 44.1 kHz 输入"**：
SPEC.md@v2.1 §7.4 明令「对齐两侧必须**同率**」。参考与练习是两次独立录音，
源采样率可以不同（44.1 kHz 与 48 kHz 混用是常态）。若直接拒绝非 44.1 kHz，
用户会拿到一个他无法自行解决的失败——而统一采样率是**本系统完全有能力做的事**。

- **输入** `samples`：一维 `float32` `NDArray`；
  `native_sr`：`int`，源采样率（Hz）。
- **输出**：一维 `float32` `NDArray`，采样率为 `AUDIO.sample_rate`。
- **算法口径**（**必须写死，不得留给实现者选**）：
  ```python
  if native_sr == AUDIO.sample_rate:
      return np.ascontiguousarray(samples, dtype=np.float32)   # 恒等，不引入损失
  out = scipy.signal.resample_poly(samples, AUDIO.sample_rate, native_sr)
  return np.ascontiguousarray(out, dtype=np.float32)
  ```
  - 用**多相滤波**（`resample_poly`），不用 FFT 法（`scipy.signal.resample`）：
    FFT 法会假设信号周期延拓，在文件首尾引入边界效应，
    而本仓对首尾各 0.4 s 静音有明确规格（SPEC §2），边界污染会直接进入音准统计。
  - `up = AUDIO.sample_rate`，`down = native_sr`，**必须传原始整数**，
    不要先约分（`resample_poly` 内部会处理，手工约分反而可能与预期不符）。
  - 输出长度 = `ceil(len(samples) * up / down)`。**不强制等于输入长度的比例后取整**，
    以库的行为为准 —— 实现者不得自行 pad/trim 去"凑整"。
- **边界**：
  | 输入 | 行为 |
  | --- | --- |
  | `native_sr == AUDIO.sample_rate` | 直接返回副本，**不发生重采样** |
  | `native_sr <= 0` | `INPUT_UNREADABLE` |
  | `samples` 为空数组 | 返回空数组（不抛错） |
  | `samples.ndim != 1` | `ValueError`（编程错误，不是用户输入错误） |
  | 含 `NaN` / `inf` | 原样传播（`resample_poly` 会保持非有限值），由 §4.4 暴露 |
- **不变量**：输出 `ndim == 1`、`dtype == np.float32`、连续内存；
  `native_sr == 目标` 时输出与输入**逐元素相等**（这条可机械断言）。

---

### 4.3 `validate_duration(n_samples, sample_rate) -> float`

**职责**：校验时长落在 `profile.AUDIO` 的允许区间，返回时长（秒）。

- **输入** `n_samples: int`（≥ 0）；`sample_rate: int`（> 0）。
- **输出** `float` —— 时长，单位**秒**。
- **算法口径**（写死）：
  ```python
  duration = n_samples / sample_rate
  if duration < AUDIO.min_duration_sec:   # 45.0
      raise CoreBuildError(ErrorCode.INPUT_TOO_SHORT, ...)
  if duration > AUDIO.max_duration_sec:   # 120.0
      raise CoreBuildError(ErrorCode.INPUT_TOO_LONG, ...)
  return duration
  ```
  - 阈值**必须**引用 `AUDIO.min_duration_sec` / `AUDIO.max_duration_sec`，
    **不得写字面量 45.0 / 120.0**（否则规格改了这里不会跟着改）。
  - 比较用 `<` 与 `>`，**不是** `<=` / `>=`：
    恰好 45.0 s 与恰好 120.0 s **是合法的**（区间为闭区间 `[45.0, 120.0]`）。
- **边界**：
  | 输入 | 行为 |
  | --- | --- |
  | `duration < 45.0` | `INPUT_TOO_SHORT` |
  | `duration == 45.0` | **合法**，返回 45.0 |
  | `duration == 120.0` | **合法**，返回 120.0 |
  | `duration > 120.0` | `INPUT_TOO_LONG` |
  | `n_samples == 0` | `INPUT_TOO_SHORT` |
  | `sample_rate <= 0` | `ValueError`（编程错误） |
  | ★ 超长 | **必须拒绝，不得静默截断** —— 截断会让分析结果对应到一个
    用户并不知道的时间范围，而他以为整首都分析过了 |
- **不变量**：返回值 ∈ `[45.0, 120.0]`；抛错时**不返回任何值**。

---

### 4.4 `assert_not_silent(samples) -> float`

**职责**：校验整段非静音，返回整段 RMS。

- **输入** `samples`：一维 `float32` `NDArray`。
- **输出** `float` —— 整段 RMS，单位**线性幅度**。
- **算法口径**（写死）：
  ```python
  rms = float(np.sqrt(np.mean(np.square(samples.astype(np.float64)))))
  if rms < SILENCE_RMS_THRESHOLD:      # 1e-4
      raise CoreBuildError(ErrorCode.INPUT_SILENT, ...)
  return rms
  ```
  - **必须先转 `float64` 再平方**：`float32` 平方在大动态范围下会累积误差，
    而本函数的结果要与 `1e-4` 这个**绝对值**比较。
  - 用**整段** RMS，不是分帧 RMS：本函数只回答"这段录音整体是不是空的"，
    局部静音是**合法**的（乐句之间就有静音），属于算法层的分析对象。
  - 比较用 `<`，不是 `<=`：恰好等于 `1e-4` **是合法的**。
- **边界**：
  | 输入 | 行为 |
  | --- | --- |
  | `rms < 1e-4` | `INPUT_SILENT` |
  | `rms == 1e-4` | **合法**，返回 1e-4 |
  | 全零数组 | `INPUT_SILENT` |
  | 空数组 | `INPUT_SILENT`（`mean` 产生 `NaN`/警告；实现须先判空并直接抛 `INPUT_SILENT`） |
  | 含 `NaN` | `rms` 为 `NaN`；`NaN < threshold` 为 `False`，故**不会**被拦下 |
  | 含 `inf` | `rms` 为 `inf`，**不会**被拦下 |
- **★ 已知缺口（如实记录，不掩盖）**：上表最后两行说明，
  含 `NaN`/`inf` 的输入**能穿过**静音校验，随后会在重采样或特征阶段
  以更难诊断的形式暴露。正确修法是在本函数里加
  `if not np.isfinite(samples).all(): raise CoreBuildError(INPUT_UNREADABLE, ...)`，
  但那会**改变本函数的语义**（从"判静音"变成"判静音+判有限性"），
  且 `INPUT_UNREADABLE` 的既定含义是"文件不可读"，用于"文件可读但样本非有限"
  属于**错误码语义的扩用**。故此处**不自行添加**，按 §37 上报（见 §10）。
- **不变量**：返回值 ≥ `1e-4`；抛错时不返回任何值。

---

### 4.5 `ingest(uri) -> NDArray`（**唯一对外入口**）

**职责**：完整标准化流程，返回全系统统一的 PCM。

- **输入** `uri: str` —— 本地文件路径。
- **输出**：一维 `float32` `NDArray`，满足
  `AUDIO.sample_rate == 44100`、单声道、连续内存。
  ★ **只返回样本，不返回采样率** —— 因为采样率恒为
  `AUDIO.sample_rate`（常量），返回它等于把常量当变量传（§22 禁止）。
- **算法口径**（**步骤顺序是规格的一部分，不得调整**）：
  ```python
  1. samples, native_sr = decode_to_mono(uri)
  2. samples = resample_to_profile(samples, native_sr)
  3. validate_duration(samples.shape[0], AUDIO.sample_rate)   # ← 用**重采样后**的长度与目标采样率
  4. assert_not_silent(samples)
  5. return samples
  ```
  - ★ **第 3 步必须用重采样后的长度与 `AUDIO.sample_rate`**，
    不能沿用 `native_sr`。理由：重采样会改变样本数
    （实测 48000→44100 时 44100 个样本变成 40517 个），
    若用 `native_sr` 算时长，得到的**秒数相同**（重采样不改时长），
    但用重采样后的长度配 `AUDIO.sample_rate` 才是"最终产物的时长"。
    两者在数学上相等，实现须选后者以保持"校验的就是要交付的东西"。
  - **顺序理由**：先重采样再校验时长，是因为重采样几乎不改变时长，
    但**先解码再重采样**才能知道源采样率；静音校验放在最后，
    因为它是唯一需要看完整样本的检查。
- **边界**：透传底层四个函数的全部失败（见 §5）。
- **不变量**：
  - 成功返回时：`ndim == 1`、`dtype == np.float32`、连续、非空；
  - 时长 ∈ `[45.0, 120.0]` 秒；
  - 整段 RMS ≥ `SILENCE_RMS_THRESHOLD`；
  - **失败时抛 `CoreBuildError`，绝不返回"降级后的默认数组"**。

---

## 5 · 失败语义

**本模块的全部失败路径（穷举）。** 所有失败均抛 `CoreBuildError`，
携带 `contract.ErrorCode`；`detail` 必须含足以定位的信息
（路径、实际值、期望区间），但**不得**含完整音频内容。

| 情形 | 行为 | 抛出 |
| --- | --- | --- |
| `uri` 非 `str` / 空串 / 路径不存在 / 是目录 | 显式失败 | `CoreBuildError(INPUT_UNREADABLE)` |
| 格式不支持 / 文件损坏 / 非音频 | 显式失败（`LibsndfileError` 或 `OSError` 转译） | `CoreBuildError(INPUT_UNREADABLE)` |
| 源采样率 ≤ 0 | 显式失败 | `CoreBuildError(INPUT_UNREADABLE)` |
| 时长 `< 45.0` s | 显式失败 | `CoreBuildError(INPUT_TOO_SHORT)` |
| 时长 `> 120.0` s | 显式失败 | `CoreBuildError(INPUT_TOO_LONG)` |
| 整段 RMS `< 1e-4` | 显式失败 | `CoreBuildError(INPUT_SILENT)` |
| `samples.ndim != 1`（编程错误） | 显式失败 | `ValueError` |
| `sample_rate <= 0`（编程错误） | 显式失败 | `ValueError` |
| 样本含 `NaN` / `inf` | **⚠ 当前不被拦下**（见 §4.4 已知缺口） | —— |

★ **宪章 §5.6：禁止静默降级。** 本模块明令禁止以下"看起来更友好"的做法：

- ❌ 超长音频**截断**到 120 s 后继续
- ❌ 静音音频**返回零数组**让流程继续
- ❌ 解码失败**返回空数组**并让调用方"自己判断"
- ❌ 采样率不对**强行当作 44.1 kHz** 继续算
- ❌ 任何 `try/except` 后返回默认值而不抛错

**唯一的例外**：`resample_to_profile` 在 `native_sr == AUDIO.sample_rate`
时直接返回副本 —— 这不是降级，是**恒等变换**（数学上无损，且可机械断言）。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-101-1 | `ingest()` 成功返回的数组恒为 `ndim==1`、`dtype==float32`、连续内存 | §8 判据 A |
| INV-101-2 | `ingest()` 返回的采样率恒为 `AUDIO.sample_rate`（44100），**且它是常量不是变量** | §8 判据 A（返回后按 44100 Hz 解释） |
| INV-101-3 | 时长恒 ∈ `[45.0, 120.0]` 秒；区间**闭** | §8 判据 C（边界用例） |
| INV-101-4 | 整段 RMS 恒 ≥ `SILENCE_RMS_THRESHOLD` | §8 判据 C |
| INV-101-5 | `native_sr == 44100` 时 `resample_to_profile` **逐元素恒等** | §8 判据 B |
| INV-101-6 | 全部失败均抛 `CoreBuildError`，**绝不返回默认值** | §8 判据 E（负面用例） |
| INV-101-7 | 本模块**不做**任何归一化 / 去噪 / 动态处理 / 特征计算 | §8 判据 F（AST + grep） |
| INV-101-8 | 本模块**不 import** §3 清单外的任何模块 | §8 判据 F |
| INV-101-9 | 多声道文件被下混为单声道，且**不是**"只取第 0 声道" | §8 判据 D（构造双声道，左 1.0 右 0.0，断言结果 ≈ 0.5） |

---

## 7 · 边界（明确不做）

- **不做音量归一化**（peak / RMS normalization）—— 力度是算法要比较的量之一，
  归一化会把 `dynamics` 要测的东西抹掉。
- **不做去噪 / 增强 / 压缩 / 限幅 / 高通**—— 属本项目边界之外（AGENTS.md 铁律 2），
  且任何动态处理都会污染 `rms.*` 端口。
- **不做静默截断**，也不做自动补静音来"凑够" 45 s。
- **不做变速 / 变调**—— 那是时间轴拉伸，会破坏 `timing` 要测的抢拍拖拍。
  ★ 注意与 §4.2 的区别：**统一采样率**（改的是每秒采多少个点）允许且必须做；
  **变速**（改的是音乐本身多快）绝对禁止。两者在实现上容易混，故明写。
- **不计算任何特征**——f0 / RMS / chroma / 音符切分全部属于 `core/features.py`。
- **不做 DTW 或任何对齐**——属于 `core/align.py`。
- **不读会话状态、不接收 `session_id`**——本模块是纯函数式的一步转换。
- **不写盘、不落日志、不访问网络**。
- **不 import 同层模块**（`core.api` / `align` / `features` / `surface`）——
  `core` 内部的编排是 `core.api` 的职责。
- 若你发现"不做某个东西就实现不了" → **不要做**，转 §10。

---

## 8 · 怎么验证你写对了

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval

# ── 判据 A（INV-101-1 / INV-101-2）：规格与 dtype
python3 -c "
import numpy as np
from harmonica_eval.core.ingest import ingest
from harmonica_eval.profile import AUDIO
p = 'harmonica_mvp_dataset/01_奇异恩典/原曲_完整版.wav'
x = ingest(p)
assert x.ndim == 1, x.ndim
assert x.dtype == np.float32, x.dtype
assert x.flags['C_CONTIGUOUS'], '非连续内存'
assert AUDIO.sample_rate == 44100
print(f'PASS A: ndim=1 dtype=float32 连续 采样率={AUDIO.sample_rate}')
"

# ── 判据 B（INV-101-5）：同率时重采样必须是恒等
python3 -c "
import numpy as np
from harmonica_eval.core.ingest import resample_to_profile
from harmonica_eval.profile import AUDIO
rng = np.random.default_rng(42)
x = rng.standard_normal(44100).astype(np.float32)
y = resample_to_profile(x, AUDIO.sample_rate)
assert y.shape == x.shape, (y.shape, x.shape)
assert np.array_equal(x, y), '同率重采样不是恒等 —— 引入了无谓损失'
print('PASS B: 同率重采样逐元素恒等')
"

# ── 判据 C（INV-101-3 / INV-101-4）：闭区间边界与静音
python3 -c "
import numpy as np
from harmonica_eval.core.ingest import validate_duration, assert_not_silent
from harmonica_eval.contract import CoreBuildError, ErrorCode
from harmonica_eval.profile import AUDIO

# 闭区间：恰好端点合法
assert validate_duration(int(45.0*44100), 44100) == 45.0
assert validate_duration(int(120.0*44100), 44100) == 120.0
# 越界必须抛，且码要对
for n, code in ((int(44.9*44100), ErrorCode.INPUT_TOO_SHORT),
                (int(120.1*44100), ErrorCode.INPUT_TOO_LONG)):
    try:
        validate_duration(n, 44100); raise SystemExit(f'未拒绝 {n}')
    except CoreBuildError as e:
        assert e.code == code, (e.code, code)
# 静音
try:
    assert_not_silent(np.zeros(44100, dtype=np.float32)); raise SystemExit('未拒绝静音')
except CoreBuildError as e:
    assert e.code == ErrorCode.INPUT_SILENT, e.code
# 恰好在阈值上合法
assert assert_not_silent(np.full(44100, 1e-4, dtype=np.float32)) == 1e-4
print('PASS C: 闭区间边界 + 静音门限正确')
"

# ── 判据 D（INV-101-9）：下混是平均，不是取第 0 声道
python3 -c "
import numpy as np, soundfile as sf, tempfile, os
from harmonica_eval.core.ingest import decode_to_mono
d = tempfile.mkdtemp()
p = os.path.join(d, 'stereo.wav')
st = np.stack([np.ones(44100), np.zeros(44100)], axis=1).astype(np.float32)
sf.write(p, st, 44100)
mono, sr = decode_to_mono(p)
assert abs(float(mono[0]) - 0.5) < 1e-6, f'下混结果 {mono[0]}，应为 0.5（平均值）'
print('PASS D: 双声道 (1.0, 0.0) 下混为 0.5 —— 用的是平均')
"

# ── 判据 E（INV-101-6）：负面用例全部显式失败，不返回默认值
python3 -c "
import numpy as np, tempfile, os, soundfile as sf
from harmonica_eval.core.ingest import ingest
from harmonica_eval.contract import CoreBuildError
d = tempfile.mkdtemp()
cases = {}
cases['不存在'] = os.path.join(d, 'nope.wav')
p = os.path.join(d, 'short.wav'); sf.write(p, np.zeros(1000, np.float32), 44100); cases['太短'] = p
p = os.path.join(d, 'silent.wav'); sf.write(p, np.zeros(60*44100, np.float32), 44100); cases['静音'] = p
p = os.path.join(d, 'long.wav'); sf.write(p, np.random.randn(130*44100).astype(np.float32)*0.1, 44100); cases['太长'] = p
p = os.path.join(d, 'bad.wav'); open(p,'wb').write(b'not audio'); cases['损坏'] = p
for name, path in cases.items():
    try:
        ingest(path); raise SystemExit(f'{name}: 未失败 —— 静默降级！')
    except CoreBuildError as e:
        print(f'  {name} -> {e.code.value}')
print('PASS E: 5 个负面用例全部显式失败')
"

# ── 判据 F（INV-101-7 / INV-101-8）：依赖面封闭 + 无越界计算
python3 - <<'PY'
import ast, pathlib
src = pathlib.Path('harmonica_eval/core/ingest.py').read_text(encoding='utf-8')
tree = ast.parse(src)
mods = set()
for n in ast.walk(tree):
    if isinstance(n, ast.Import):
        mods.update(a.name.split('.')[0] for a in n.names)
    elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
        mods.add(n.module.split('.')[0])
ALLOWED = {'__future__', 'os', 'typing', 'numpy', 'soundfile', 'scipy'}
extra = mods - ALLOWED
assert not extra, f'越界 import: {extra}'
# scipy 只许用 resample_poly
if 'scipy' in mods:
    assert 'scipy.signal' in src and 'resample_poly' in src
    for banned in ('resample(', 'decimate', 'interp1d', 'scipy.io', 'scipy.fft'):
        assert banned not in src, f'scipy 越界用法: {banned}'
# 禁止同层 import
for banned in ('core.api', 'core.align', 'core.features', 'core.surface',
               'from .api', 'from .align', 'from .features', 'from .surface'):
    assert banned not in src, f'同层横向依赖: {banned}'
print(f'PASS F: 依赖面封闭 {sorted(mods)}，无越界计算')
PY

# ── 判据 G：全仓机械检查仍通过（本文件不得引入新违规）
python3 tools/verify_shell.py
```

**验收判据**（可机械判定，非「看起来对」）：
- [ ] 判据 A 通过 —— 返回 `float32 / 一维 / 连续`
- [ ] 判据 B 通过 —— 同率重采样**逐元素恒等**（INV-101-5）
- [ ] 判据 C 通过 —— 45.0 与 120.0 **恰好合法**，越界抛**正确**的码
- [ ] 判据 D 通过 —— 双声道下混为 **0.5**（平均），不是 1.0（取第 0 声道）
- [ ] 判据 E 通过 —— 5 个负面用例**全部显式失败**，无一静默降级
- [ ] 判据 F 通过 —— import 面封闭，`scipy` 只用 `resample_poly`
- [ ] 判据 G 通过 —— `tools/verify_shell.py` 结论为「通过」

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] 上述 7 条判据的**完整命令输出**（不是"我跑过了"）
- [ ] `git diff --stat harmonica_eval/core/ingest.py`
- [ ] **真实数据集验证**：对 `harmonica_mvp_dataset/01_奇异恩典/` 下**全部 7 个 wav**
      跑一次 `ingest`，输出每份的 `(shape, dtype, duration_sec, rms)`
- [ ] **重采样实证**（若实现了真实转换路径）：构造一个 48 kHz 文件，
      记录 `native_sr`、`len(samples)`、转换后 `len`、以及转换前后**时长是否一致**
      （允许 ±1 个样本的舍入差）
- [ ] 若发现 `NaN`/`inf` 能穿过校验（§4.4 已知缺口），
      提交 `MOLD BREAK` 并附复现脚本，**不要**自行加错误码

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
