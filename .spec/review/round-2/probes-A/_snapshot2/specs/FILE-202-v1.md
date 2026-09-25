# FILE-202 — algorithms/timing.py

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/algorithms/timing.py`
> 生成依据：`contract.py`（AlgorithmDataContract / AlgorithmResultEnvelope）·
> `profile.py@CORE_PROFILE_V0.1` · `algorithms/__init__.py`（PAYLOAD_SCHEMAS）·
> `SPEC.md §5` · `COMPONENTS.md §4`
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-202 |
| 所属组件 | COMP-C3 Algorithm |
| 层级 | L3（symbol / implementation） |
| 上游 | C1 `HostApp.run_algorithms()` 调用 `run(surface)` |
| 下游 | 只读 `AlgorithmDataContract`；不调用任何 Core 内部模块 |
| 同层邻居 | `pitch.py` / `dynamics.py` / `__init__.py` |

**你的权限**：只实现本文件。不得修改 `contract.py` / `profile.py` /
`__init__.py`，不得新增端口，不得新增第三方依赖。

---

## 2 · 这个文件为什么存在

回答用户最朴素的那个问题：**「我这两个音，谁早了谁晚了，早/晚了多少？」**

它是三个算法里唯一**必须**使用源时间轴的：
时间归一化（把练习拉伸到与参考等长）会**恰好抹掉**它要测的东西 ——
抢拍拖拍在归一化轴上恒为 0，而且**不会报错**。
删掉本文件，「节奏」这一整个维度消失（SPEC §1 的三大维度之一）。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：
- 标准库：`math`, `statistics`, `time` (`perf_counter`), `typing`
- 第三方：`numpy`（`asarray` / `median` / `isfinite`）
- 本包内：`..contract`（`AlgorithmDataContract`, `AlgorithmResultEnvelope`,
  `TimelineBasis`, `AlgorithmError`）

**禁止 import**：
- **不得** import `..profile`（会造成循环 import：
  `algorithms/__init__` 已经 import 本模块）
- **不得** import `core.*`（依赖方向：C3 → C2 只经契约，不认实现）
- **不得** import `host.*` / `cockpit.*`
- 不得引入 `librosa` / `scipy` / `soundfile`（本文件不需要，且未在预算内）

---

## 4 · 你要实现什么（行为规格）

### 4.0 模块常量（**必须逐字存在**，审查者会 grep）

```python
ALGORITHM_ID: str = "timing"
ALGORITHM_VERSION: str = "1.0.0"
AXIS = TimelineBasis.REFERENCE     # ★ 硬约束，不得改为 WARPED
ONSET_MATCH_TOLERANCE_SEC: float = 0.100
ONSET_DEADBAND_MS: float = 23.0
MS_PER_SEC: float = 1000.0
```

`REQUIRED_PORTS` / `CONSUMED_PORTS`：**不要写镜像常量**。
运行期从 `surface.manifest()` 读实际端口，只校验"我需要的在不在"。
（理由：镜像无法与注册表同步，且算法无法 import 注册表 —— 见 `__init__.py` 说明。）

---

### 4.1 `detect_onsets(samples, sample_rate) -> ndarray`

**仅兜底路径**：`notes.*` 为空时才用。

- **输入**：`samples` 一维实数序列（来自 `pcm.mapped.*`）；
  `sample_rate` 正整数 Hz
- **输出**：一维 `float64` 数组，**升序**，单位**秒**
- **口径**（必须写到可复现同一数字）：
  1. `win = 1024`, `hop = 256`（与 `profile.MATERIALIZE.rms_*` 一致）
  2. `env[k] = RMS(x[k*hop : k*hop+win])`
  3. `nov[k] = max(0, 20*log10(env[k]+eps) - 20*log10(env[k-1]+eps))`，`eps=1e-12`
  4. `thr[k] = 1.5 * median(nov[k±1.0s]) + 1e-3`
  5. 取局部极大，且 `nov[k] > thr[k]`，且与前一 onset 间隔 `>= 0.05 s`
  6. `onset_sec = k * hop / sample_rate`
- **边界**：空输入或 `sample_rate <= 0` → `ValueError`；
  无 onset → 返回**空数组**（不是 `None`）

---

### 4.2 `match_onsets(ref_onsets, prac_onsets, tolerance_sec=ONSET_MATCH_TOLERANCE_SEC) -> dict`

**保序双指针**（两侧各自升序，**不允许交叉配对**）：

```
i = j = 0
while i < len(ref) and j < len(prac):
    d = prac[j] - ref[i]
    if |d| <= tol:  配对成功, i++, j++
    elif d < 0:     j++          # 练习多出的音
    else:           i++          # 参考被漏掉的音
余下分别归入 unmatched_ref / unmatched_prac
```

- **返回**：
  ```
  {"pairs": [(i, j, ref_t, prac_t), ...],
   "unmatched_ref": [...], "unmatched_prac": [...],
   "n_ref": int, "n_prac": int, "n_unpaired": int}
  ```
- **★ 音数不等**：漏音与多音**不参与任何偏差统计**
  （把 5 秒的错位当成"拖了 5000 毫秒"是荒谬的），
  但**必须计数上报** `n_unpaired`。
- `tolerance_sec` 默认值**必须**引用模块常量，不得写字面量。

---

### 4.3 `compute_deviations(matched) -> list[float]`

- 对 `pairs` **按参考侧音序**取 `(prac_t - ref_t) * MS_PER_SEC`
- **带符号**：负 = 抢拍（早），正 = 拖拍（晚）
- 返回 Python 原生 `float` 列表（**JSON 可序列化**）

---

### 4.4 `summarize_deviations(deviations_ms, n_unpaired) -> dict`

★★ **本版更正（第三轮盲审 A 的 probe 07）：`n_unpaired` 原来没有可达通道。** ★★

`PAYLOAD_SCHEMAS["timing"]` 的 8 个键里有 `n_unpaired`，
而本节表格把它标为「来自 `match_onsets`」——
但 §4.5 的流程是
`payload = summarize_deviations(compute_deviations(matched))`，
而 §4.3 冻结 `compute_deviations(matched) -> list[float]`。
**`match_onsets` 的返回值在这一步已经被丢掉了** ——
`summarize_deviations` 只收到一个 `list[float]`，
它**没有任何办法**知道有多少音没配上。

**本版冻结**：`n_unpaired` 由 `run` 从 `matched["n_unpaired"]` 取出后
**显式传入**。`run` 手里同时有 `matched` 和 `deviations`，是唯一能传的地方。

**必须恰好产出 8 个键**，与 `algorithms.PAYLOAD_SCHEMAS["timing"]`
**逐字一致**（键名以那张表为唯一权威）：

| 键 | 口径 |
| --- | --- |
| `per_note_onset_ms` | 逐音偏差，长度 **必须等于** `n_notes_used` |
| `median_onset_ms` | `median(d)`（带符号） |
| `spread_ms` | `median(abs(d - median(d)))` —— **MAD about median**，不是 `median(abs(d))` |
| `early_ratio` | `count(d < -ONSET_DEADBAND_MS) / n` |
| `late_ratio` | `count(d > +ONSET_DEADBAND_MS) / n` |
| `on_time_ratio` | `count(abs(d) <= DEADBAND) / n` |
| `n_notes_used` | `len(d)` |
| `n_unpaired` | **由调用方传入**（`run` 从 `matched["n_unpaired"]` 取；见本节开头的签名更正） |

- **★ 三者关系**：`early_ratio + late_ratio + on_time_ratio == 1.0`。
  必须三个都报 —— 只报前两个的话，用户看到它们加起来不到 1 会以为是 bug，
  而实际上那是"测量精度不足以判定"的部分。
  `on_time_ratio` 的含义是**无法判定**早或晚，**不等于**"演奏准确"。
- **边界**：`n == 0` → 返回 OK + 全零 payload（`per_note=[]`, `n_notes_used=0`）。
  理由：`n` 本身是 payload 键，"报告样本量为 0"优于"抛异常"。

---

### 4.5 `run(surface) -> AlgorithmResultEnvelope`

```
t0 = perf_counter()
try:
    mf = surface.manifest()
    若 not mf.sealed                     → 失败
    missing = 需要的端口 - mf.ports       → 非空则 INCOMPATIBLE / PLUGIN_INCOMPATIBLE
    对每个 consumed 端口断言 descriptor.timeline_basis is AXIS(REFERENCE)
                                         不符 → 失败
    sr = mf.audio_format.sample_rate
    固定顺序读（time_range=None，整段）：
        notes.reference → notes.practice → pcm.mapped.reference → pcm.mapped.practice
    c = descriptor.field_names.index("onset_sec")   # ★ 不得硬编码列号
    取列、滤非有限值、升序
    若某侧为空 → detect_onsets(对应 pcm.mapped.*, sr)
    matched = match_onsets(ref, prac, ONSET_MATCH_TOLERANCE_SEC)
    deviations = compute_deviations(matched)
    payload = summarize_deviations(deviations, matched["n_unpaired"])   # ★ n_unpaired 显式传入
    断言 payload 全有限（NaN/inf → 失败）
    返回 Envelope(OK, payload, required_ports=注册表副本, consumed_ports=..., elapsed_sec)
except HarmonicaError as e  → FAILED, error_code = e.code.value
except Exception            → FAILED, error_code = "ALGORITHM_FAILED"
```

- **失败信封的 payload 也填全零 8 键** —— 防止 C1 对 FAILED 也做 schema
  校验时误判 `ALGORITHM_RESULT_INVALID`。失败语义由 `status` / `error_code` 承担。
- **不抛异常到调用方**、**不改 surface**、**不持跨会话状态**。
- `required_ports` 必须**逐字复制**注册表中 timing 的那一项，不得自行拼接/重排。

---

## 5 · 失败语义

| 情形 | 行为 | 结果 |
| --- | --- | --- |
| surface 未 sealed | 显式失败 | `INCOMPATIBLE` / `PLUGIN_INCOMPATIBLE` |
| 缺所需端口 | 显式失败 | `INCOMPATIBLE` / `PLUGIN_INCOMPATIBLE` |
| 端口轴不是 REFERENCE | 显式失败 | `FAILED` / `ALGORITHM_FAILED` |
| payload 含 NaN/inf | 显式失败 | `FAILED` / `ALGORITHM_FAILED` |
| `notes.*` 为空 | **兜底**到 `detect_onsets`，不算失败 | OK |
| 两侧都无 onset（`n_notes_used==0`） | 返回零值 payload | OK |
| 任何未预期异常 | 捕获，不穿透 | `FAILED` / `ALGORITHM_FAILED` |

★ **禁止**：缺端口时"用别的端口凑"；轴不对时"先算着"；异常时返回 `None`。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-202-1 | 全部时间数学用**秒**，不乘除 hop | grep：不得出现 `2048` / `256` 字面量参与换算 |
| INV-202-2 | 使用 REFERENCE 轴 | grep `AXIS`；启动时断言端口轴 |
| INV-202-3 | payload 键**恰好** 8 个 | 与 `PAYLOAD_SCHEMAS["timing"]` 比对 |
| INV-202-4 | `len(per_note_onset_ms) == n_notes_used` | 运行时断言 |
| INV-202-5 | 三比例之和 == 1.0（n>0 时） | 运行时断言，容差 1e-9 |
| INV-202-6 | 未配对音不进入偏差统计 | 构造漏音用例验证 |
| INV-202-7 | `run` 不抛异常到调用方 | 注入异常验证 |
| INV-202-8 | 相同输入两次运行结果一致 | 同 build 两次跑，比对 |

---

## 7 · 边界（明确不做）

- **不使用** `pcm.warped.practice` 或任何 WARPED 轴数据
- **不使用** `warp_path`（本算法不做任何时间映射 —— 见下）
- **不做** DSP 之外的信号处理（不滤波、不降噪、不做 onset 分类）
- **不生成**教学结论 / 自然语言（SPEC §1：只到数值层）
- **不判断**"合格/不合格"（阈值由消费方决定）

> ★ **为什么不读 `warp_path`**（前版曾把它列为必需端口，已移除）：
> `warp_path` 按定义是 DTW 对应关系，拿它把练习时刻映射到参考钟**就是**
> 时间归一化 —— 那会让抢拍拖拍恒为 0。故"声明需要它"与"不许用归一化"
> 不可兼得。实测全项目无算法消费它：它是**证据端口**（供审查者复现对齐）。

---

## 8 · 怎么验证你写对了

```bash
python3 tools/verify_shell.py            # 空壳期：应通过
python3 tools/verify_stubs_raise.py      # 空壳期：74/74
python3 tools/build_virtual_graph.py --check
```

**实现后**（§35 `Real ⊑ Virtual`）必须额外跑：
- 合成用例：参考 `[0, 1, 2]`，练习 `[0.05, 1.0, 2.2]` →
  `per_note_onset_ms == [50.0, 0.0, 200.0]`（**黄金向量**）
- 死区用例：差值 `23.0` → 落 `on_time_ratio`；`23.1` → 落 `late_ratio`
- 漏音用例：练习删掉第 2 音 → `n_unpaired >= 1` 且该音**不出现**在 `per_note_onset_ms`
- 轴错用例：把某端口伪造成 WARPED → 必须**显式失败**（不得静默出数）

**验收判据**：
- [ ] 8 个 payload 键名与注册表逐字一致
- [ ] `early + late + on_time == 1.0`
- [ ] 漏音场景下中位数**不被**巨大假偏差污染
- [ ] 两次运行 `payload` 完全相等

---

## 9 · 完成后提交什么证据（§36）

- [ ] 上述黄金向量的**实际输出**（贴数字，不是"通过"）
- [ ] `python3 tools/verify_shell.py` 全绿输出
- [ ] 轴错用例的**失败截图/输出**（证明它真的会炸）
- [ ] 本文件对应的 `Real ⊑ Virtual` 比对记录

---

## 10 · ★ 何时必须停止并上报

**必须停止的情形**：

1. 你认为需要**新增一个阈值/口径**而 §4 没写
2. 你认为 `ONSET_MATCH_TOLERANCE_SEC = 0.100` 或 `ONSET_DEADBAND_MS = 23.0`
   **量级不对**（它们是从"对齐精度 ±23ms"与"最短音长 150ms"推导的，
   若你发现推导前提有误，**上报，不要自行改**）
3. 你发现 §4 的规格**不足以确定唯一实现**
4. 你需要 `notes.practice` 之外的数据源
5. 你发现 `PAYLOAD_SCHEMAS["timing"]` 与本文冲突

**上报格式**（宪章 §37）：
```
GATE CHALLENGE
- 相关 Requirement：
- 相关 Build Instruction 章节：
- 实际需要 vs 规格给出：
- 为什么冲突：
- 复现证据：
- 建议的上游处理位置：
```

**绝对禁止**：先做 workaround（§38）；自行加"合理"默认值；
静默缩小范围。

---

## 附：冻结常量速查

| 常量 | 值 | 来源 |
| --- | --- | --- |
| `ONSET_MATCH_TOLERANCE_SEC` | `0.100` | 由 ±23ms 对齐噪声与 150ms 最短音长推导 |
| `ONSET_DEADBAND_MS` | `23.0` | = 对齐帧级精度 ±hop/2 @ hop=2048 |
| `MIN_STABLE_NOTE_SEC` | `0.150` | `features.py` |
| `MATERIALIZE.rms_frame_length` | `1024` | `profile.py` |
| `MATERIALIZE.rms_hop_length` | `256` | `profile.py` |
| `AUDIO.sample_rate` | `44100` | `profile.py`，运行期取 `manifest.audio_format.sample_rate` |
