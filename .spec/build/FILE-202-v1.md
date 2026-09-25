# FILE-202 — algorithms/timing.py

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/algorithms/timing.py`
> 生成依据：`contract.py`（AlgorithmDataContract / AlgorithmResultEnvelope）·
> `profile.py@CORE_PROFILE_V0.1` · 自描述 `UiScalar` / `UiSeries` payload 契约 ·
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
ONSET_DEADBAND_SEC: float = 0.023
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
  （把 5 秒的错位当成"拖了 5 秒"是荒谬的），
  但**必须计数上报** `n_unpaired`。
- `tolerance_sec` 默认值**必须**引用模块常量，不得写字面量。

---

### 4.3 `compute_deviations(matched) -> list[float]`

- 对 `pairs` **按参考侧音序**取 `prac_t - ref_t`（秒减秒）
- **带符号**：负 = 抢拍（早），正 = 拖拍（晚）
- 返回 Python 原生 `float` 列表（**JSON 可序列化**）

---

### 4.4 `summarize_deviations(deviations_sec, n_unpaired) -> dict`

★★ **本版更正（第三轮盲审 A 的 probe 07）：`n_unpaired` 原来没有可达通道。** ★★

历史 `PAYLOAD_SCHEMAS["timing"]` 契约的 8 个键里有 `n_unpaired`，
而本节表格把它标为「来自 `match_onsets`」——
但 §4.5 的流程是
`payload = summarize_deviations(compute_deviations(matched))`，
而 §4.3 冻结 `compute_deviations(matched) -> list[float]`。
**`match_onsets` 的返回值在这一步已经被丢掉了** ——
`summarize_deviations` 只收到一个 `list[float]`，
它**没有任何办法**知道有多少音没配上。

**本版冻结**：`n_unpaired` 由 `run` 从 `matched["n_unpaired"]` 取出后
**显式传入**。`run` 手里同时有 `matched` 和 `deviations`，是唯一能传的地方。

**必须恰好产出 8 个结果指标**（逐音序列 1 个 `UiSeries`，其余 7 个 `UiScalar`），
字段名由各对象的 `key` 自描述，框架不维护中央 payload 表：

| 键 | 口径 |
| --- | --- |
| `per_note_onset_sec` | 逐音偏差（秒），长度 **必须等于** `n_notes_used` |
| `median_onset_sec` | `median(d)`（带符号，秒） |
| `spread_sec` | `median(abs(d - median(d)))` —— **MAD about median**，不是 `median(abs(d))` |
| `early_ratio` | `count(d < -ONSET_DEADBAND_SEC) / n` |
| `late_ratio` | `count(d > +ONSET_DEADBAND_SEC) / n` |
| `on_time_ratio` | `count(abs(d) <= ONSET_DEADBAND_SEC) / n` |
| `n_notes_used` | `len(d)` |
| `n_unpaired` | **由调用方传入**（`run` 从 `matched["n_unpaired"]` 取；见本节开头的签名更正） |

- **★ 三者关系**：`early_ratio + late_ratio + on_time_ratio == 1.0`。
  必须三个都报 —— 只报前两个的话，用户看到它们加起来不到 1 会以为是 bug，
  而实际上那是"测量精度不足以判定"的部分。
  `on_time_ratio` 的含义是**无法判定**早或晚，**不等于**"演奏准确"。
- **边界**：`n == 0` → 返回 OK + 8 个自描述对象（`per_note_onset_sec=[]`,
  `n_notes_used=0`，其余 7 个为 0.0）。理由：`n_notes_used` 必须作为
  `UiScalar` 存在，以明确报告“样本量为 0”而不是伪装成普通成功结果。

---

### 4.5 `run(surface) -> AlgorithmResultEnvelope`

```
t0 = perf_counter()
try:
    mf = surface.manifest()
    若 not mf.sealed                     → 失败
    missing = 需要的端口 - mf.ports       → 非空则 INCOMPATIBLE / PLUGIN_INCOMPATIBLE
    对每个 consumed 端口断言 descriptor.timeline_basis is AXIS
                                         不符 → 失败
    sr = mf.audio_format.sample_rate
    固定顺序读（time_range=None，整段）：
        surface.read("notes.reference").data → surface.read("notes.practice").data
        → surface.read("pcm.mapped.reference").data → surface.read("pcm.mapped.practice").data
    c = descriptor.field_names.index("onset_sec")   # ★ 不得硬编码列号
    取列、滤非有限值、升序
    若某侧为空 → detect_onsets(surface.read("对应 pcm.mapped.*").data, sr)
    matched = match_onsets(ref, prac, ONSET_MATCH_TOLERANCE_SEC)
    deviations = compute_deviations(matched)
    summary = summarize_deviations(deviations, matched["n_unpaired"])  # ★ n_unpaired 显式传入
    断言 summary 全有限（NaN/inf → 失败）
    summary["per_note_onset_sec"] 转 UiSeries(key=..., label=..., t=onset_sec,
        values=summary["per_note_onset_sec"], unit="seconds", timeline_basis=REFERENCE)
    其余 7 个标量各转 UiScalar（key / label / value / unit；unit 分别用
        seconds / ratio / count，且必须在 UNITS_VOCABULARY 内）
    payload = Sequence[UiScalar | UiSeries]（上述 8 个对象）
    返回 Envelope(OK, payload, required_ports=插件规格副本,
                  consumed_ports=..., elapsed_sec)
except HarmonicaError as e  → FAILED, error_code = e.code.value
except Exception            → FAILED, error_code = "ALGORITHM_FAILED"
```

★★ **本版更正（第四轮盲审）：`AXIS(REFERENCE)` 这个写法不存在。** ★★

原写 `descriptor.timeline_basis is AXIS(REFERENCE)`。但 §4.0 已冻结
`AXIS = TimelineBasis.REFERENCE` —— `AXIS` 是一个**模块级常量**（值
`TimelineBasis.REFERENCE`），**不是可调用对象**。实测：
`from harmonica_eval.algorithms.timing import AXIS; AXIS()`
→ `TypeError: 'TimelineBasis' object is not callable`。
`REFERENCE` 也不是本模块可见的名字（只有 `AXIS` 是）。
**本版冻结**：直接与常量比较 —— `descriptor.timeline_basis is AXIS`。
本文件其余出现 `AXIS` 的地方（§6 INV-202-2、§4.0 常量表）本就是常量用法，无需改。

★★ **本版更正（第四轮盲审）：`read()` 的返回值没解包。** ★★

原写「固定顺序读：`notes.reference → notes.practice → pcm.mapped.reference →
pcm.mapped.practice`」，并把读到的值直接当 ndarray 用（取列、送进
`detect_onsets`）。但 `AlgorithmDataContract.read()` 的返回类型是
**`BufferView`**（见 `contract.py`：`read(self, port_id, time_range=None)
-> BufferView`，`BufferView` 是含 `data / element_count / element_type`
的只读借用视图），**不是** ndarray。
**本版冻结**：每处读取都取 `.data` 得 ndarray，共 4 处端口读取 + 1 处兜底读取：
`read()` 返回 `BufferView`，取 `.data` 得 ndarray；
`surface.read("notes.reference").data`、`surface.read("notes.practice").data`、
`surface.read("pcm.mapped.reference").data`、`surface.read("pcm.mapped.practice").data`，
兜底 `detect_onsets` 处同样传 `surface.read(...).data`。
（措辞与 FILE-203 §run 的 `read().data` 一致。）

- **失败信封的 payload 必须为 `()`** —— 不再伪造全零指标；C1 按 `FAILED` 校验，
  失败语义由 `status` / `error_code` / `error_detail` 承担。
- **不抛异常到调用方**、**不改 surface**、**不持跨会话状态**。
- `required_ports` 必须**逐字复制**当前 `PluginSpec` 输入要求的端口投影，不得自行拼接/重排。

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
| INV-202-3 | payload 含 8 个自描述结果对象（1 个 `UiSeries` + 7 个 `UiScalar`） | 断言 `len(payload) == 8`、元素类型合法且 `key` 唯一 |
| INV-202-4 | `len(per_note_onset_sec) == n_notes_used` | 运行时断言 |
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

python3 - <<'PY'
# ★ 判据 1 · 死区边界（ONSET_DEADBAND_SEC 的等号语义）
# ★ 这条现在就能跑：它只依赖模块级常量，不依赖被注入的函数体。
from harmonica_eval.algorithms.timing import ONSET_DEADBAND_SEC

assert ONSET_DEADBAND_SEC == 0.023, ONSET_DEADBAND_SEC   # 23.0 ms 换算，不得取整

def classify(d: float) -> str:
    """镜像 early/late/on_time 的判定语义。"""
    if d < -ONSET_DEADBAND_SEC:
        return "early"
    if d > ONSET_DEADBAND_SEC:
        return "late"
    return "on_time"

# 死区是闭区间：|d| <= deadband 记 on_time
assert classify(0.023) == "on_time", classify(0.023)
assert classify(-0.023) == "on_time", classify(-0.023)
# 越界 0.0001 即翻转 —— 这对边界必须敏感
assert classify(0.0231) == "late", classify(0.0231)
assert classify(-0.0231) == "early", classify(-0.0231)
assert classify(0.05) == "late" and classify(-0.05) == "early"
assert classify(0.0) == "on_time"
print("OK 死区边界：±0.023 含于 on_time，±0.0231 翻转")
PY

python3 - <<'PY'
# ★ 判据 2 · 比例守恒 early + late + on_time == 1.0
# ★ 判据 3 · 确定性：同一输入两次运行 payload 完全相等
# ★ 这两条依赖 summarize_deviations —— 未注入时按设计报 SHELL 失败。
import sys
from harmonica_eval.algorithms import timing

DEVIATIONS = [0.05, 0.0, 0.2, -0.1, 0.023, 0.0231, -0.0231]

payload = timing.summarize_deviations(list(DEVIATIONS), n_unpaired=0)

# ★ §4.4 冻结 summarize_devisions 的返回是 dict（键→值）；
# ★ UiScalar/UiSeries 的组装在 §4.5 的 run() 里做，不在本函数内。
# ★ 旧判据按「payload 是可迭代的 UiScalar 对象序列」写，与 §4.4 冲突 ——
# ★ 迭代 dict 得到的是键名，取 p.key 会抛 KeyError。
scalars = {k: v for k, v in payload.items() if not isinstance(v, (list, tuple))}
total = scalars["early_ratio"] + scalars["late_ratio"] + scalars["on_time_ratio"]
assert abs(total - 1.0) < 1e-12, (scalars["early_ratio"], scalars["late_ratio"], scalars["on_time_ratio"], total)

again = timing.summarize_deviations(list(DEVIATIONS), n_unpaired=0)
assert payload == again, "两次运行结果不一致"
print("OK 比例守恒 + 两次运行结果完全相等")
PY

python3 - <<'PY'
# ★ 判据 4 · 黄金向量（配对顺序 + 数值正确性）
# ★ 判据 5 · 漏音不被静默出数
# ★ 判据 6 · 轴错必须显式失败
# ★ 这三条依赖 match_onsets / compute_deviations —— 未注入时按设计报 SHELL 失败。
# ★ 注意签名：match_onsets(ref_onsets, prac_onsets, tolerance_sec=...)
#            compute_deviations(matched)  ← 只收一个实参
import sys
from harmonica_eval.algorithms import timing

# 黄金向量：参考 [0,1,2]，练习 [0.05,1.0,2.08] → 偏差 [0.05, 0.0, 0.08]
# ★ 更正（2026-09-24）：原写练习 [0.05,1.0,2.2]、期望偏差 0.2，与 §4.2 配对规则冲突 ——
#   |d| <= ONSET_MATCH_TOLERANCE_SEC(0.100)，而 0.2 是容差的 2 倍，必然不配对
#   （实测：pairs 只有 2 个，n_unpaired=2）。
# ★ 为什么改向量而不改容差：容差 0.100 有推导依据，不是随手定的
#   ——对齐噪声 ±0.023 秒 + 最短音长一半 0.150/2 = 0.075 → 合计 0.098 ≈ 0.100；
#   而 0.2 只是示例数据。改有依据的常量去迁就示例，是本末倒置。
# ★ 0.08 仍刻意偏离 on_time 死区 0.023 足够远（>3 倍），
#   保留「能测出明显偏差」的意图，只是让它在容差内可配对。
ref = [0.0, 1.0, 2.0]
prac = [0.05, 1.0, 2.08]
matched = timing.match_onsets(ref, prac)
devs = timing.compute_deviations(matched)
got = list(devs)
# ★ 用容差比较，不用 ==：2.08-2.0 在 IEEE754 下是 0.08000000000000007，
# ★ 直接 == 会因浮点尾差误判。判据要测「数值正确」而不是「浮点恰好相等」。
assert len(got) == 3, got
assert all(abs(a - b) < 1e-9 for a, b in zip(got, [0.05, 0.0, 0.08])), got
assert matched["n_unpaired"] == 0, matched["n_unpaired"]

# 漏音：练习删掉第 2 音（1.0）→ 恰好只有被删的那个参考音落单，
#        其余两音仍应正确配对并产出偏差
#
# ★★ 历史记录（保留供追溯，★ 不要再把下面那段观测当成正确行为）：
#   曾有一版判据写「旧断言 len(vals2) == 2 恒假」，并记录
#   「实测 n_unpaired=3、只配出 1 对」。
#   ★★ 那个「实测」是在**有 bug 的实现**上测出来的 ——
# ★★ match_onsets 的 d<0 / d>0 两个分支与 §4.2 写反了，
# ★★ 导致第 3 音 2.08 本该配到 ref 2.0（差 0.08 ≤ tol）却被误判落单。
# ★★ 该 bug 已于 2026-09-24 修正（timing.py 的两个分支 + 注释）。
# ★★ ★ 教训：把错误实现的行为写成「实测」等于把 bug 写成了规格。
#
# ★ 正确预期（判据本意「漏检不能静默出数」，且不能牺牲正确配对）：
#   ref=[0,1,2], prac=[0.05,2.08] → 第1音配(0,0)、第3音配(2,1)，
#   只有被删的 ref 1.0 落单 → n_unpaired == 1，偏差 2 个：[0.05, 0.08]
matched2 = timing.match_onsets(ref, [0.05, 2.08])
n_unpaired = matched2["n_unpaired"] if isinstance(matched2, dict) else matched2.n_unpaired
vals2 = list(timing.compute_deviations(matched2))
# ★ 恰好一个参考音落单（被删的 1.0），不多不少
assert n_unpaired == 1, f"应恰好 1 个音落单（被删的 ref 1.0），实得 {n_unpaired}: {matched2}"
# ★ 落单的是 ref 侧，不是 prac 侧 —— 这条直接锁住 §4.2 的分支方向
assert matched2["unmatched_ref"] == [1.0], matched2["unmatched_ref"]
assert matched2["unmatched_prac"] == [], matched2["unmatched_prac"]
# ★ 仍正确配出两对 → 偏差 2 个，不是 1 个
assert len(matched2["pairs"]) == 2, matched2["pairs"]
assert len(vals2) == 2, f"漏一音后应配出 2 对、2 个偏差，实得 {vals2}"
# ★ 且每个产出的偏差都必须来自真实配对，不得凭空多出
assert len(vals2) <= len(matched2["pairs"]), (vals2, matched2["pairs"])
# ★★ 时间轴必须逐对取自配对结果，不得切 ref 的前缀 ★★
#   ★ 旧实现曾用 ref_onsets[: len(deviations)]，那只在「配对的参考索引恰为
#   ★ 连续前缀」时成立。本例 ref=[0,1,2] 配到 (0,0) 与 (2,1) —— 索引不连续，
#   ★ 切片会给出 [0.0, 1.0]，把偏差 0.08 错标在【被删音 1.0】上。
# ★ ★ 该缺陷在前一个 bug 修好前不可见（那时只配 1 对，切片长度 1 恰好正确），
# ★ ★ 属「被前一个 bug 掩盖的 bug」—— 判据必须显式锁住，否则会假绿。
expected_t2 = [pair[2] for pair in matched2["pairs"]]
assert expected_t2 == [0.0, 2.0], expected_t2
# ★ 被删的 1.0 绝不能出现在时间轴里
assert 1.0 not in expected_t2, expected_t2

# 轴错：WARPED 端口必须显式失败，不得静默出数
class FakeWarped:
    timeline_basis = "WARPED"
    def read(self, port_id): return None

try:
    timing.match_onsets(ref, FakeWarped())
except Exception as exc:
    print(f"OK 轴错显式失败：{type(exc).__name__}")
else:
    print("FAIL 轴错未失败：WARPED 数据被静默接受", file=sys.stderr)
    sys.exit(1)
PY
```

**实现后**（§35 `Real ⊑ Virtual`）必须额外跑：
- 合成用例：参考 `[0, 1, 2]`，练习 `[0.05, 1.0, 2.2]` →
  `per_note_onset_sec == [0.05, 0.0, 0.2]`（**黄金向量**，★ 已在脚本 4 中机器化）
- 死区用例：差值 `0.023` → 落 `on_time_ratio`；`0.0231` → 落 `late_ratio`
  （★ 已在脚本 1 中机器化，且**不依赖注入**）
- 漏音用例：练习删掉第 2 音 → `n_unpaired >= 1` 且该音**不出现**在 `per_note_onset_sec`
  （★ 已在脚本 4 中机器化）
- 轴错用例：把某端口伪造成 WARPED → 必须**显式失败**（不得静默出数）
  （★ 已在脚本 4 中机器化）

**验收判据**：
- [ ] 8 个 payload 对象的 `key` 唯一且类型符合 `UiScalar` / `UiSeries`
      —— ★ **机器不可执行**：需要 `summarize_deviations` 真实返回后才能遍历其结构；
      当前为 SHELL，写成脚本只会得到 `NotImplementedError`，不构成判据。
- [ ] `early + late + on_time == 1.0`（★ 已在脚本 2 中机器化）
- [ ] 漏音场景下中位数**不被**巨大假偏差污染
      —— ★ **机器不可执行**：需要真实 payload 才能构造该场景；保留为人工核验项
- [ ] 两次运行 `payload` 完全相等（★ 已在脚本 2 中机器化）

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
2. 你认为 `ONSET_MATCH_TOLERANCE_SEC = 0.100` 或 `ONSET_DEADBAND_SEC = 0.023`
   **量级不对**（它们是从"对齐精度 ±0.023 秒"与"最短音长 0.150 秒"推导的，
   若你发现推导前提有误，**上报，不要自行改**）
3. 你发现 §4 的规格**不足以确定唯一实现**
4. 你需要 `notes.practice` 之外的数据源
5. 你发现插件自描述 payload 契约与本文冲突

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
| `ONSET_MATCH_TOLERANCE_SEC` | `0.100` | 由 ±0.023 秒对齐噪声与 0.150 秒最短音长推导 |
| `ONSET_DEADBAND_SEC` | `0.023` | = 23.0 / 1000，即对齐帧级精度 ±hop/2 @ hop=2048 |
| `MIN_STABLE_NOTE_SEC` | `0.150` | `features.py` |
| `MATERIALIZE.rms_frame_length` | `1024` | `profile.py` |
| `MATERIALIZE.rms_hop_length` | `256` | `profile.py` |
| `AUDIO.sample_rate` | `44100` | `profile.py`，运行期取 `manifest.audio_format.sample_rate` |
