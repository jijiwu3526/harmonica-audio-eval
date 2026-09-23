# FILE-201 — harmonica_eval/algorithms/pitch.py

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/algorithms/pitch.py`
> 生成依据：`SPEC.md@v2.1` · `contract.py` · `profile.py@CORE_PROFILE_V0.1` · `COMPONENTS.md`
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-201 |
| 所属组件 | COMP-C3 Algorithm |
| 层级 | L3（symbol / implementation） |
| 上游 | C1 host.app 调用 run(surface)。输入是 C1 传入的 surface（已解码音频的表面数据，单位为 SPEC.md 规定的统一采样口径），本文件不自行读取音频文件。 |
| 下游 | 只读 `..contract` 中的 AlgorithmDataContract，向 C1 host.app 返回 AlgorithmResultEnvelope。不调用 Core 内部模块。 |
| 同层邻居 | `harmonica_eval/algorithms/timing.py` / `harmonica_eval/algorithms/dynamics.py` / `harmonica_eval/algorithms/__init__.py` |

**你的权限**：只实现本文件。不得修改任何其他文件，不得修改契约，
不得新增端口，不得新增依赖。

---

## 2 · 这个文件为什么存在

本文件实现 `harmonica_eval/algorithms/pitch.py`，向评测结果提供「音准」维度的客观数值指标。

追溯到 Product Intent / Requirement：本项目只做「双音频对比 → 客观数值指标」。音准是 SPEC.md §7 中唯一带有硬阈值的学习维度——SPEC.md §7 为该维度写死了判定阈值，指标不达阈值即该维度判定为不通过。

删掉它会坏掉什么：本文件缺席后，`harmonica_eval/algorithms/__init__.py` 暴露的算法集合缺少音准入口，C1 host.app 调用 `run(surface)` 得到的 AlgorithmResultEnvelope 不含音准维度的指标，「音准」维度整个消失；SPEC.md §7 的学习维度集合随之残缺，那条唯一的硬阈值判定无从执行。节奏、力度两个维度各自承担自己的判定职责，不承接音准的计算，没有替代模块填补这个空缺。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：
- 标准库：`math`（`log2`）；`statistics`（`median`）；`time`（只用 `perf_counter`，给 `elapsed_sec` 计时）；`typing`
- 第三方：`numpy`（`asarray` / `isfinite` / `median` / `abs` / `zeros` / `float64` / `int32`）
- 本包内：`..contract`（`AlgorithmDataContract` / `AlgorithmResultEnvelope` / `FIELD_LAYOUTS` / `ErrorCode`）

**禁止 import**：
- **不得** import `..profile`（会造成循环 import：`algorithms/__init__` 已 import 本模块，
  而 `profile` 又被 `algorithms/__init__` 之外的多处引用；壳里也刻意没引它）
- **不得** import `..core.*`（依赖方向：C3 → C2 **只经契约**，不认实现。
  一旦 import 了 `core`，C3 就知道 C2 的内部结构，深组件即被穿透）
- **不得** import `..host` / `..cockpit`（依赖方向相反，且 C4 可缺席）
- **不得** import `..algorithms.timing` / `..algorithms.dynamics`（同层横向依赖。
  三个算法**互不知道对方存在**；共享口径靠契约，不靠互相调用）
- **不得** import 任何 DSP / 音高库：`librosa`（含 `pyin`、`piptrack`）、
  `crepe`、`torchcrepe`、`aubio`、`parselmouth`、`torch`、`scipy`、`soundfile`
  —— 音高**提取**是 `core/features.py` 的职责，本文件只**比较**已提取的曲线
- **不得** import `pandas` / `matplotlib` / `rich`（报告呈现与 C4 的职责）
- **不得** import 任何 I/O：`os`、`sys`、`pathlib`、`json`、`logging`、`warnings`
  —— 本文件是纯计算，不读文件、不写盘、不打印
- 不得 import 任何 `random` / 时间/日期模块（结果必须可复现，不得有随机性）

★ 本清单必须**穷举**，不许出现「等」「之类」。
★ 特别注意 `statistics.median` 与 `numpy.median` **都允许**，但**必须只用其中一个**
并全文一致 —— 两者在偶数个元素上的算法相同（取中间两个的平均），
但混用会让读者无法确认口径。**本文件推荐 `numpy.median`**（与 `numpy` 一起用，
少一个 import）。

---

## 4 · 你要实现什么（行为规格）

### 4.0 模块常量（**必须逐字存在**，审查者会 grep）

```python
ALGORITHM_ID: str = "pitch"
ALGORITHM_VERSION: str = "1.0.0"
MAX_CENTS_DEVIATION: float = 50.0
MIN_STABLE_NOTE_SEC: float = 0.150
AXIS = TimelineBasis.REFERENCE
```

- `MAX_CENTS_DEVIATION = 50.0` —— 来自 **SPEC.md §7.3**（「≥150 ms 的稳定音符上，
  中位误差应 ≤ 50 音分」），**不是工程估计值**。
  它是**判据**（这个音算不算准），不是"完美线"（有多好）。
- `MIN_STABLE_NOTE_SEC = 0.150` —— 与 `core.features.MIN_STABLE_NOTE_SEC` **同义**
  （SPEC.md §7.3 的「≥150 ms」）。短音的音高估计不可靠，纳入统计是噪声不是信号。
- `AXIS = TimelineBasis.REFERENCE` —— 音准关心"吹了什么"，不关心"何时吹"，
  故用源时间轴。**不得改为 WARPED**（那会抹掉 timing 要测的东西）。
  ★ 注意：`AXIS` 只声明**用哪条轴**，**绝不蕴含**两侧帧号对齐 —— 见 §4.2。

**不要写 `REQUIRED_PORTS` / `CONSUMED_PORTS` 镜像常量**：
运行期从 `surface.manifest()` 读实际端口，只校验"我需要的在不在"。
理由：镜像无法与注册表同步，且算法无法 import 注册表（见 §3）。

---

### 4.1 `hz_to_cents(f0_hz, ref_hz) -> float`

- **输入**：`f0_hz: float`、`ref_hz: float`，单位 **Hz**，**必须均 > 0**
- **输出**：`float`，单位**音分**（cents），带符号（正 = 偏高）
- **算法口径**（写死）：
  ```python
  return 1200.0 * math.log2(f0_hz / ref_hz)
  ```
  基准：`f0_hz == ref_hz` → `0.0`；`f0_hz == 2*ref_hz` → `+1200.0`（一个八度）
- **边界**：
  | 输入 | 行为 |
  | --- | --- |
  | `f0_hz <= 0` 或 `ref_hz <= 0` | `ValueError`（调用方未按 voiced 过滤，是**编程错误**） |
  | 任一为 `NaN` | `ValueError`（`NaN` 不满足 `> 0`，自然被上一行拦下） |
  | 任一为 `inf` | `ValueError` |
  | 正常 | 返回音分，可能是任意大的正负值（**不截断**：偏两个八度就是 ±2400 音分，那是真实信息） |
- **不变量**：输出对同一输入恒等（纯函数，无状态）；
  `hz_to_cents(x, x) == 0.0` 对任意 `x > 0` **精确成立**（`log2(1.0) == 0.0`）

★ **必须用绝对音高，禁止 chroma 化。** 这是本算法的核心约束：
chroma 是**八度不变**的 —— 用它做音准会把「低了一个八度」判成完全正确。
实测佐证：同一段音频在 22.05 kHz 下 f0 被判低八度（恰好 −1200 音分），
若用 chroma，这个错误**完全不可见**。

---

### 4.2 `compare_pitch_curves(ref_pitch, prac_pitch, ref_notes, prac_notes, sample_rate) -> dict`

**职责**：逐音比较两侧音高，返回逐音的音分偏差。

★★ **本函数是本次由下往上核对修正的核心，实现者必须读懂这段再动手。** ★★

**被修正的错误推理（原文档写的，已作废）**：
> 「两条曲线同轴（都是 REFERENCE），故可直接逐帧相减」

**为什么错**：`TimelineBasis.REFERENCE` 的含义是
「保留源时间、未被时间归一化」，它**不蕴含**「两侧帧号一一对应」。
参考与练习是**两段独立录音**，时长各自落在
`[profile.AUDIO.min_duration_sec, profile.AUDIO.max_duration_sec]` = `[45.0, 120.0]` 秒。
`pitch.*` 的帧数 = 时长 ÷ `MATERIALIZE.pitch_hop_length`，
故两侧 `n_frames` **默认不相等**，逐帧相减**无定义**。

**为什么这个缺陷一直没暴露**：本数据集 01 的全部 7 个 wav 都由同一渲染器批量产出，
长度**恰好全是 72.802 s**（1568 帧），帧数差为 0 —— "恰好等长"掩盖了它。
换一首演奏时长不同的练习曲（**这正是真实使用场景**）立刻崩。

**正确做法**：用两侧各自的 `notes.*` 的 `onset_sec` 建立对应，
**按音配对**后再比较。这才是 `ALGORITHMS` 声明 pitch 需要
`notes.reference` + `notes.practice` 的**真正理由** ——
原先的论证只讲到"为了能标注第几个音"（**可定位**），
没讲到"不等长**根本无法比较**"（**可比较**）。
论证不完整，所以本函数的签名一直漏掉了这两个参数。

---

- **输入**：
  | 参数 | 类型 | 形状 | 字段顺序（**必须引用 `contract.FIELD_LAYOUTS`，不得硬编码位置**） |
  | --- | --- | --- | --- |
  | `ref_pitch` | `NDArray` | `(n_frames_ref, 3)` | `FIELD_LAYOUTS['pitch']` = `('f0_hz', 'voiced', 'confidence')` |
  | `prac_pitch` | `NDArray` | `(n_frames_prac, 3)` | 同上 |
  | `ref_notes` | `NDArray` | `(n_notes_ref, 3)` | `FIELD_LAYOUTS['notes']` = `('onset_sec', 'f0_hz', 'rms')` |
  | `prac_notes` | `NDArray` | `(n_notes_prac, 3)` | 同上 |
  | `sample_rate` | `int` | — | 两侧**同一**采样率（由 `core.ingest` 保证；见 FILE-101） |

  ★ `ref_pitch` 与 `prac_pitch` 的**第一维默认不相等**，实现**不得**假设它们相等。

- **输出**：`dict`，**恰好三个键**：
  ```python
  {
    "per_note_cents": list[float],   # 逐音带符号偏差，长度 == n_paired
    "n_paired": int,                 # 成功配对的音数
    "n_unpaired": int,               # 未能配对的音数（★ 见下"已知缺口"）
  }
  ```

- **算法口径**（逐步写死，实现者须能复现同一数字）：
  1. **取音符起点**：`ref_onsets = ref_notes[:, IDX_onset_sec]`，
     `prac_onsets = prac_notes[:, IDX_onset_sec]`（`IDX_*` 由
     `FIELD_LAYOUTS['notes'].index(...)` 求得，**不得写字面量 0**）。
  2. **保序双指针配对**（两侧 onset 各自升序，**不允许交叉配对**）：
     ```
     i = j = 0; pairs = []; unpaired = 0
     while i < n_ref and j < n_prac:
         pairs.append((i, j)); i += 1; j += 1
     余下的 max(0, n_ref-i) + max(0, n_prac-j) 计入 unpaired
     ```
     ★ **本函数用"按音序配对"**（第 n 个音对第 n 个音），**不做时间容差判断**
     —— 容差配对是 `timing` 的职责（它有自己的 `ONSET_MATCH_TOLERANCE_SEC`）。
     这里只要"第几个音对第几个音"这个**索引对应关系**。
  3. **每对音内部求偏差**：
     - 由 `ref_onsets[i]` 与 `ref_onsets[i+1]` 得到参考侧该音覆盖的帧区间
       `[round(t_start * sample_rate / hop), round(t_end * sample_rate / hop))`
       —— `hop` 取 `MATERIALIZE.pitch_hop_length`。
       ★ 最后一个音的右边界取 `n_frames_ref`（无下一个音时就到曲线末尾）。
     - 两侧**各自独立**算各自的帧区间（用各自的 `n_frames` 截断），
       **绝不**假设 `ref` 的帧号能用在 `prac` 上。
     - 在该区间内取两侧**都 voiced**（`voiced != 0`）的帧对。
       ★ 因为两侧区间长度可能不同，取 `min(len_ref_seg, len_prac_seg)` 对齐，
       逐对计算。
     - 对该对音：`cents = median([hz_to_cents(p, r) for r, p in zip(seg_ref, seg_prac)])`
       —— **取中位数**，不取平均（单个野点不该拉动整音判定）。
  4. **丢弃无效音**：若某对音中"两侧都 voiced"的帧数为 0，该音**不产生偏差**，
     且**不计入 `n_paired`**（计入 `n_unpaired`）。
     若帧数 < `MIN_STABLE_NOTE_SEC * sample_rate / hop`（不足 150 ms），**同样丢弃**
     —— 短音的音高估计不可靠（SPEC.md §7.3）。
  5. **返回**：`per_note_cents` 为 `list[float]`（**不是 `NDArray`**，
     因为要装进 `AlgorithmResultEnvelope.payload` 做序列化）；
     `n_paired = len(per_note_cents)`。

- **边界**：
  | 输入 | 行为 |
  | --- | --- |
  | 任一数组为空 | 返回 `{"per_note_cents": [], "n_paired": 0, "n_unpaired": <另一侧音数>}` |
  | 两侧都空 | 返回全 0 / 空列表 |
  | 两侧帧数不等（**常态**） | 正常工作 —— 这正是本函数存在的理由 |
  | 某音一侧有声一侧无声 | 该音丢弃，计入 `n_unpaired`（漏音/多音属另一类问题，混进来会污染音准统计） |
  | 某音短于 150 ms | 丢弃，计入 `n_unpaired` |
  | `sample_rate <= 0` | `ValueError` |
  | 数组第二维 ≠ 3 | `ValueError`（编程错误） |
  | 含 `NaN` 的 f0 | 该帧视为非 voiced 处理（`NaN != 0` 为真，故须**显式**用 `np.isfinite` 一并排除） |

- **不变量**：
  - `len(per_note_cents) == n_paired`；
  - `n_paired + n_unpaired == max(len(ref_onsets), len(prac_onsets))`；
  - 所有返回的 cents 均为**有限**浮点数（无 `NaN` / `inf`）；
  - **函数不做任何 I/O、不改动输入数组**。

- **★ 已知缺口（由下往上核对发现，如实记录不掩盖，实现者不得"顺手修"）**：
  `timing` 与 `dynamics` 的 payload 都含 `n_unpaired`（未能配对的音数），
  **`pitch` 的 payload 没有**（见 `PAYLOAD_SCHEMAS['pitch']`，只有 5 个键）。
  而本函数的配对**同样会失败**（漏音 / 多音 / 音数不等），
  被排除的音**同样无处报告**。
  后果：读者无法分辨「整首都测了」与「只测上了少数几个音」，
  而 `off_pitch_ratio` 的**分母**恰恰就是 `n_notes_used` ——
  「全曲 115 个音里 58 个走音」与「12 个音里 6 个走音」会得到同一个数字。

  根因：`PAYLOAD_SCHEMAS` 由人工维护、三份各自演化，缺少对称性约束。
  修它需要在**冻结表**加键 = **接口变更**。
  故：**本函数照常返回 `n_unpaired`（它是有用的中间量），
  但 `run()` 装信封时不得把它写进 payload**（那会违反冻结的 schema）。
  **按 §37 Gate Challenge 上报**，见 §10。

---

### 4.3 `summarize_deviations(deviations_cents) -> dict`

- **输入**：`deviations_cents: list[float] | NDArray` —— §4.2 产出的逐音偏差
- **输出**：`dict`，**键名以 `algorithms.PAYLOAD_SCHEMAS["pitch"]` 为唯一权威**，
  **恰好 5 个键，一字不得增删**：
  ```python
  {
    "per_note_cents":   list[float],  # 带符号逐音偏差，长度 == n_notes_used
    "median_abs_cents": float,        # 中位**绝对**偏差
    "off_pitch_ratio":  float,        # 超过 MAX_CENTS_DEVIATION 的音占比 ∈ [0,1]
    "n_notes_used":     int,          # 参与统计的音数（**必须报告**）
    "sample_rate":      int,          # ★ 由 run() 填入，本函数不收此参数则返回时省略
  }
  ```
  ★ 由于 `sample_rate` 是"结果的成因"而非统计量，**本函数签名里没有它**；
  故本函数返回**前 4 个键**，由 `run()` 补上 `sample_rate` 得到完整 5 键。
  若实现者选择让本函数直接收 `sample_rate` 并返回 5 键，**也允许**
  （两种都不违反契约），但**必须在文档里写清选了哪种**。

- **算法口径**（写死）：
  ```python
  vals = np.asarray(deviations_cents, dtype=np.float64)
  n = int(vals.size)
  if n == 0:
      return {"per_note_cents": [], "median_abs_cents": 0.0,
              "off_pitch_ratio": 0.0, "n_notes_used": 0}
  abs_vals = np.abs(vals)
  return {
      "per_note_cents":   [float(v) for v in vals],
      "median_abs_cents": float(np.median(abs_vals)),
      "off_pitch_ratio":  float(np.count_nonzero(abs_vals > MAX_CENTS_DEVIATION) / n),
      "n_notes_used":     n,
  }
  ```
  - 中位数用 `np.median`（偶数个时取中间两数**平均**）
  - `off_pitch_ratio` 的分母**是 `n`（即 `n_notes_used`）**，不是全曲音数
  - 比较用 `>`，不用 `>=`：**恰好 50.0 音分算"准"**
    （SPEC §7.3 的措辞是「应 ≤ 50 音分」，故 50.0 合法）

- **边界**：
  | 输入 | 行为 |
  | --- | --- |
  | 空列表 | 返回 `n_notes_used=0`，比例与中位数均 `0.0`（**不是 `NaN`**） |
  | 单元素 | 中位绝对偏差 = 该元素的绝对值 |
  | 全部恰好 50.0 | `off_pitch_ratio == 0.0`（因为是"≤ 50 算准"） |
  | 含 `NaN` | 由 §4.2 保证不出现；若出现，`np.median` 会返回 `NaN` —— 实现须在 §4.2 端拦掉 |
- **不变量**：`off_pitch_ratio ∈ [0.0, 1.0]`；`median_abs_cents >= 0.0`；
  `len(per_note_cents) == n_notes_used`

---

### 4.4 `run(surface) -> AlgorithmResultEnvelope`

**职责**：算法入口。流程：读端口 → 比较 → 汇总 → 装信封。

- **输入**：`surface: AlgorithmDataContract`（**只读**，只有 `read()` 与 `manifest()`）
- **输出**：`AlgorithmResultEnvelope`（字段见 `contract.py`）：
  ```
  algorithm_id       = ALGORITHM_ID        ("pitch")
  algorithm_version  = ALGORITHM_VERSION   ("1.0.0")
  status             = "SUCCEEDED" | "FAILED"
  required_ports     = ("pitch.reference", "pitch.practice", "notes.reference", "notes.practice")
  consumed_ports     = 实际成功读取的端口元组
  payload            = §4.3 的 5 键字典（失败时为 {}）
  error_code         = ErrorCode 的值 或 None
  error_detail       = 人类可读说明 或 None
  elapsed_sec        = perf_counter 差值（float）
  ```

- **算法口径**（顺序写死）：
  1. `t0 = time.perf_counter()`
  2. `man = surface.manifest()` —— 校验四个必需端口都在（缺任一 → 失败信封）
  3. `ref_pitch = surface.read("pitch.reference")`，其余三个同理
  4. `res = compare_pitch_curves(ref_pitch, prac_pitch, ref_notes, prac_notes, sample_rate)`
  5. `payload = summarize_deviations(res["per_note_cents"])`
  6. `payload["sample_rate"] = <两侧的采样率>` —— **补上第 5 个键**
  7. 装信封返回，`elapsed_sec = time.perf_counter() - t0`

- **★ 失败语义（本函数最容易写错的地方）**：
  **任何失败都必须返回 `status="FAILED"` 的信封，绝不抛异常。**
  理由：算法失败不应穿透到 C1，否则故障无法隔离 —— 一个算法崩了会带崩整条流水线。
  用 `try/except Exception` 包住 2–6 步，在 except 里装失败信封：
  - `error_code = ErrorCode.ALGORITHM_FAILED.value`
  - `error_detail = f"{type(e).__name__}: {e}"`
  - `payload = {}`
  - ★ **不留 `error_code=None`**：失败却无码，C1 无法分类。

- **边界**：
  | 情形 | 行为 |
  | --- | --- |
  | 必需端口缺失 | 失败信封，`ALGORITHM_FAILED` |
  | `surface.read()` 抛异常 | 失败信封，`ALGORITHM_FAILED` |
  | 两侧音符全部配不上 | **成功**信封，`payload` 里 `n_notes_used=0`（这是有效结论："一个音都没对上"） |
  | `sample_rate` 拿不到 | 失败信封（因为它是结果的成因，缺它结果不可信） |
  | 任何未预期异常 | 失败信封，`ALGORITHM_FAILED`，detail 带异常类型 |

- **不变量**：
  - **本函数永不抛异常**（这条可机械断言：用会抛的 mock surface 调它）；
  - 返回的 `algorithm_id` / `algorithm_version` 恒为常量；
  - `status == "FAILED"` 时 `error_code` 必非 `None`；
  - `elapsed_sec` 必为有限非负数

---

## 5 · 失败语义

**分层规则**：`hz_to_cents` / `compare_pitch_curves` / `summarize_deviations`
是**纯计算**，编程错误抛 `ValueError`；
`run()` 是**边界**，把一切异常收进失败信封，**永不外抛**。

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| `hz_to_cents` 收到 `<= 0` 的 f0 | 显式失败（调用方未按 voiced 过滤） | `ValueError` |
| `compare_pitch_curves` 收到 `sample_rate <= 0` | 显式失败 | `ValueError` |
| `compare_pitch_curves` 收到第二维 ≠ 3 的数组 | 显式失败 | `ValueError` |
| 某音两侧无共同 voiced 帧 | **丢弃该音**，计入 `n_unpaired` | 返回（不抛） |
| 某音短于 `MIN_STABLE_NOTE_SEC` | **丢弃该音**，计入 `n_unpaired` | 返回（不抛） |
| 两侧音数不等 | **正常工作** | 返回 `n_unpaired > 0` |
| `run()` 必需端口缺失 | **失败信封** | 返回 `status="FAILED"`，`ALGORITHM_FAILED` |
| `run()` 内部任何异常 | **失败信封** | 返回 `status="FAILED"`，`ALGORITHM_FAILED` |
| `run()` 两侧音全配不上 | **成功信封** | `status="SUCCEEDED"`，`n_notes_used=0` |

★ **宪章 §5.6：禁止静默降级。** 本文件明令禁止：

- ❌ 音高曲线不等长时**截断到较短的一侧**后逐帧相减 —— 这正是被修正的那个错误
- ❌ 配不上的音**当作偏差 0** 计入统计
- ❌ 未 voiced 的帧**按 0 音分**混进中位数
- ❌ 失败时不装 `error_code` 就返回空 payload
- ❌ 任何 `except: pass`

**唯一的"宽容"是设计内的**：两侧音数不等、某音短于 150 ms、
某音无共同 voiced 帧 —— 这三种都**丢弃并计数**（`n_unpaired`），
不是降级，是**口径**（"统计只在可比的对象上进行"）。

---

## 6 · 必须满足的不变量

从铭牌的 MUST / MUST NOT 逐条抄下并给验法：

| ID | 不变量 | 来源 | 怎么验 |
| --- | --- | --- | --- |
| INV-201-1 | 消费 `pitch.reference` / `pitch.practice` / `notes.reference` / `notes.practice` 四个端口 | MUST | §8 判据 A |
| INV-201-2 | 产出**逐音**误差（音分，可定位到第几个音） | MUST | §8 判据 B |
| INV-201-3 | **必须能拿到音符边界**才能产出逐音结果 | MUST | §8 判据 B（签名含 `ref_notes` / `prac_notes`） |
| INV-201-4 | 只在 voiced 且时长 ≥ `MIN_STABLE_NOTE_SEC` 的音上统计 | MUST | §8 判据 D |
| INV-201-5 | 报告 `sample_rate` | MUST | §8 判据 E |
| INV-201-6 | 失败也返回信封，**不抛异常穿透到 C1** | MUST | §8 判据 F |
| INV-201-7 | **禁止 chroma 化** —— 必须用绝对音高 | MUST NOT | §8 判据 G |
| INV-201-8 | **禁止按帧号直接对齐两侧** | MUST NOT | §8 判据 H |
| INV-201-9 | 不用 mapped 轴（用 REFERENCE，见 `AXIS`） | MUST NOT | §8 判据 G |
| INV-201-10 | 不在未发声帧上计算误差 | MUST NOT | §8 判据 D |
| INV-201-11 | 不输出教学结论（只到数值层） | MUST NOT | §8 判据 E/G（payload 恰好 5 键，无文本字段） |
| INV-201-12 | 不 import §3 清单外的任何模块 | — | §8 判据 G |

---

## 7 · 边界（明确不做）

- **不做音高提取**（pYIN / CREPE / 自相关 / FFT）—— 那是 `core/features.py` 的职责。
  本文件只**比较**已提取好的两条曲线。**这是本文件最重要的边界**：
  一旦在这里做提取，`pitch.*` 端口的语义就被复制到算法层，
  深组件即被穿透，且两侧提取口径可能不一致。
- **不做时间对齐 / DTW** —— 属于 `core/align.py`。本文件用 `notes.*` 的
  `onset_sec` 建立**索引级**对应，不做信号级对齐。
- **不做容差配对** —— 起音容差是 `timing` 的职责（它有
  `ONSET_MATCH_TOLERANCE_SEC`）。本文件只做"第 n 个音对第 n 个音"。
- **不做 chroma / 音级 / 调性分析** —— 见 INV-201-7，chroma 会把八度错误藏起来。
- **不做教学结论 / 自然语言反馈**（"你这里偏低了"）—— 只到数值层，
  反馈生成已明确排除在本项目外（AGENTS.md 铁律 2）。
- **不做可视化 / 报告渲染** —— 属于 C4。
- **不读音频文件、不写盘、不打印** —— 本文件是纯计算。
- **不 import 同层算法**（timing / dynamics）—— 共享口径靠契约，不靠互相调用。
- **不修改输入数组** —— `surface.read()` 返回的可能是共享缓冲区视图，
  就地修改会污染后续算法。若需变换，先 `np.array(..., copy=True)`。
- **不自行给 `PAYLOAD_SCHEMAS` 加 `n_unpaired` 键** —— 那是冻结表，属接口变更。
  见 §4.2 的已知缺口与 §10。
- 若你发现"不做某个东西就实现不了" → **不要做**，转 §10。

---

## 8 · 怎么验证你写对了

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval

# ── 判据 A（INV-201-1）：注册表声明的必需端口
python3 -c "
from harmonica_eval.algorithms import ALGORITHMS
p = next(a for a in ALGORITHMS if a.algorithm_id == 'pitch')
assert p.required_ports == ('pitch.reference','pitch.practice','notes.reference','notes.practice'), p.required_ports
print('PASS A: pitch 声明了 4 个必需端口，含两侧音符')
"

# ── 判据 B（INV-201-2 / INV-201-3）：逐音结果 + 签名含音符边界
python3 -c "
import inspect, numpy as np
from harmonica_eval.algorithms.pitch import compare_pitch_curves
sig = list(inspect.signature(compare_pitch_curves).parameters)
assert 'ref_notes' in sig and 'prac_notes' in sig, f'签名缺音符边界: {sig}'
r = compare_pitch_curves(
    np.array([[440.0,1,0.9],[441.0,1,0.9],[442.0,1,0.9]], dtype=np.float64),
    np.array([[450.0,1,0.9],[451.0,1,0.9]], dtype=np.float64),
    np.array([[0.0,440.0,0.1],[1.0,441.0,0.1],[2.0,442.0,0.1]], dtype=np.float64),
    np.array([[0.0,450.0,0.1],[1.0,451.0,0.1]], dtype=np.float64),
    44100)
assert len(r['per_note_cents']) == r['n_paired'], r
assert r['n_paired'] + r['n_unpaired'] == 3, r
print(f'PASS B: 逐音结果 {r[\"n_paired\"]} 对，未配对 {r[\"n_unpaired\"]}')
"

# ── 判据 C：绝对音高（八度错误必须可见 —— chroma 化会漏掉）
python3 -c "
from harmonica_eval.algorithms.pitch import hz_to_cents
assert abs(hz_to_cents(220.0, 440.0) + 1200.0) < 1e-9
assert hz_to_cents(440.0, 440.0) == 0.0
assert abs(hz_to_cents(880.0, 440.0) - 1200.0) < 1e-9
print('PASS C: 绝对音高 —— 八度错误可见（-1200 音分）')
"

# ── 判据 D（INV-201-4 / INV-201-10）：短音与未 voiced 帧必须被丢弃
python3 -c "
import numpy as np
from harmonica_eval.algorithms.pitch import compare_pitch_curves, MIN_STABLE_NOTE_SEC
r = compare_pitch_curves(
    np.array([[440.0,1,0.9]], dtype=np.float64),
    np.array([[440.0,1,0.9]], dtype=np.float64),
    np.array([[0.0,440.0,0.1]], dtype=np.float64),
    np.array([[0.0,440.0,0.1]], dtype=np.float64),
    44100)
assert r['n_paired'] == 0, f'短音未被丢弃: {r}'
r2 = compare_pitch_curves(
    np.array([[0.0,0,0.0],[0.0,0,0.0]], dtype=np.float64),
    np.array([[0.0,0,0.0],[0.0,0,0.0]], dtype=np.float64),
    np.array([[0.0,440.0,0.1]], dtype=np.float64),
    np.array([[0.0,440.0,0.1]], dtype=np.float64),
    44100)
assert r2['n_paired'] == 0, f'未 voiced 音未被丢弃: {r2}'
print(f'PASS D: 短音与未 voiced 音均被丢弃（MIN_STABLE_NOTE_SEC={MIN_STABLE_NOTE_SEC}）')
"

# ── 判据 E（INV-201-5 / INV-201-11）：payload 恰好 5 键
python3 -c "
from harmonica_eval.algorithms import PAYLOAD_SCHEMAS
from harmonica_eval.algorithms.pitch import summarize_deviations
got = set(summarize_deviations([0.0, 10.0, 60.0]).keys()) | {'sample_rate'}
assert got == set(PAYLOAD_SCHEMAS['pitch']), (got, set(PAYLOAD_SCHEMAS['pitch']))
s = summarize_deviations([0.0, 10.0, 60.0])
assert s['n_notes_used'] == 3
assert abs(s['off_pitch_ratio'] - 1/3) < 1e-12, s
assert s['median_abs_cents'] == 10.0, s
assert summarize_deviations([50.0])['off_pitch_ratio'] == 0.0
print('PASS E: payload 5 键齐全，边界 50.0 判为准')
"

# ── 判据 F（INV-201-6）：run() 永不抛异常
python3 -c "
from harmonica_eval.algorithms.pitch import run
class Boom:
    def manifest(self): raise RuntimeError('模拟数据面炸了')
    def read(self, *a, **k): raise RuntimeError('boom')
env = run(Boom())
assert env.status == 'FAILED', env.status
assert env.error_code, '失败却没有 error_code'
print(f'PASS F: 异常被收进失败信封（{env.error_code}），未穿透')
"

# ── 判据 G（INV-201-7 / 9 / 12）：AST + grep 结构性约束
python3 - <<'PY'
import ast, pathlib
src = pathlib.Path('harmonica_eval/algorithms/pitch.py').read_text(encoding='utf-8')
tree = ast.parse(src)
mods = set()
for n in ast.walk(tree):
    if isinstance(n, ast.Import):
        mods.update(a.name.split('.')[0] for a in n.names)
    elif isinstance(n, ast.ImportFrom) and n.module:
        mods.add(n.module.split('.')[0])
ALLOWED = {'__future__', 'math', 'statistics', 'time', 'typing', 'numpy', 'contract'}
extra = {m for m in mods if m and m not in ALLOWED}
assert not extra, f'越界 import: {extra}'
for banned in ('chroma', 'librosa', 'crepe', 'torch', 'scipy', 'soundfile',
               'pyin', 'TimelineBasis.WARPED'):
    assert banned not in src, f'出现禁止的符号: {banned}'
assert 'AXIS' in src and 'TimelineBasis.REFERENCE' in src, 'AXIS 未声明为 REFERENCE'
print(f'PASS G: import 面封闭 {sorted(m for m in mods if m)}，无 chroma / 无 WARPED')
PY

# ── 判据 H（INV-201-8）：两侧不等长是常态，必须正常工作
python3 -c "
import numpy as np
from harmonica_eval.algorithms.pitch import compare_pitch_curves
ref  = np.tile(np.array([[440.0,1,0.9]]), (1568,1))   # 72.802 s @ hop=2048
prac = np.tile(np.array([[445.0,1,0.9]]), (969,1))    # 45 s
r = compare_pitch_curves(
    ref, prac,
    np.array([[i*2.0, 440.0, 0.1] for i in range(30)], dtype=np.float64),
    np.array([[i*2.0, 445.0, 0.1] for i in range(20)], dtype=np.float64),
    44100)
assert r['n_paired'] + r['n_unpaired'] == 30, r
print(f'PASS H: 两侧帧数不等（1568 vs 969）正常工作，配对 {r[\"n_paired\"]} 未配对 {r[\"n_unpaired\"]}')
"

# ── 判据 I：全仓机械检查仍通过
python3 tools/verify_shell.py
```

**验收判据**（可机械判定，非「看起来对」）：
- [ ] 判据 A 通过 —— 4 个必需端口（含**两侧音符**）
- [ ] 判据 B 通过 —— 签名含 `ref_notes` / `prac_notes`，产出**逐音**结果
- [ ] 判据 C 通过 —— 低八度给出 **−1200 音分**（chroma 化会让它是 0）
- [ ] 判据 D 通过 —— 短音与未 voiced 音**都被丢弃**
- [ ] 判据 E 通过 —— payload **恰好 5 键**，`50.0` 判为准
- [ ] 判据 F 通过 —— `run()` **永不抛异常**，失败有 `error_code`
- [ ] 判据 G 通过 —— 无 chroma / 无 WARPED / import 面封闭
- [ ] 判据 H 通过 —— **两侧不等长正常工作**（这是被修正缺陷的回归测试）
- [ ] 判据 I 通过 —— `tools/verify_shell.py` 结论为「通过」

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] 上述 9 条判据的**完整命令输出**（不是"我跑过了"）
- [ ] `git diff --stat harmonica_eval/algorithms/pitch.py`
- [ ] ★ **不等长回归证据**：一份对照实验输出，证明
      「旧做法（按帧号相减）在两侧不等长时失败或给出错误结果」而
      「新做法（按音配对）正常」—— 这是本次修正的**核心证据**，
      必须能看出差异，不能只说"我改了"
- [ ] **真实数据集验证**：对 `harmonica_mvp_dataset/01_奇异恩典/` 的
      `标准旋律版.wav`（参考）与 `01_音准走调.wav`（练习）跑一次完整
      `run(surface)`，报告 payload 的 5 个键
      ★ 并注明：这两个文件恰好都是 72.802 s，**所以这份验证不能证明不等长路径正确** ——
        不等长必须由判据 H 的合成数据证明
- [ ] 若你在实现中发现 §4.2 的配对规则**无法产生唯一实现**（例如
      "第 n 个音对第 n 个音"在漏音场景下语义不清）→ 提交 `MOLD BREAK`，
      **不要**自行发明更聪明的配对算法

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
