# FILE-203 — dynamics.py

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/algorithms/dynamics.py`
> 生成依据：SPEC.md@v2.1 §5.5 · profile.PORTS['rms.*']；`core.ingest.SILENCE_RMS_THRESHOLD`
> ★ 本文件是**冻结产物**（规范 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 値 |
| --- | --- |
| 文件 ID | FILE-203 |
| 所属组件 | COMP-C3 Algorithm |
| 层级 | L3（symbol / implementation） |
| 上游 | `harmonica_eval.core.ingest`（提供 rms.reference / rms.practice / notes.reference / notes.practice）；由 `harmonica_eval.main` 调度（见 `run` 入口） |
| 下游 | `harmonica_eval.report` / 消费 `AlgorithmResultEnvelope`。不直接调用其他算法，**但** onset_sec 来源于 `timing.detect_onsets`（共享按音配对口径） |
| 同层邻居 | `harmonica_eval/algorithms/timing.py` / `pitch.py` / `score.py` |

**你的权限**：只实现本文件 `harmonica_eval/algorithms/dynamics.py`。
不得修改任何上游端口定义、不得修改 `contract.py`、
不得新增对 `core.ingest` 以外的 import、
不得引入新的时间轴/端口/阈值。

---

## 2 · 这个文件为什么存在

Product Intent：口琵演奏中的『力度』（气息控制）只能作为**逐音能量差异**来陈述，
没有『对错』。本模块把 `rms.reference` 与 `rms.practice` 按**音**配对，
把线性振幅差换算为 dB 差，报告中位差与离散度，装进 `AlgorithmResultEnvelope`。

**删掉它会坏掉什么**：`COMP-C3` 缺少第三个已确认算法（§5.5），
主流程 `main.py` 的 `run_all` 调度会跳过 `dynamics`，
`report` 层拿不到『气息不稳/偏弱/偏强』的定量依据，
`SPEC.md` §5.5 的口琵力度评测项在运行时直接缺失。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：
- Python 标准库：`math`（`math.log10` 钳位对数转换），`statistics`（`median`, `mean`），`typing`（类型注解）
- 第三方：无
- 本包内：
  - `harmonica_eval.contract.AlgorithmDataContract`
  - `harmonica_eval.contract.AlgorithmResultEnvelope`
  - `harmonica_eval.core.ingest.SILENCE_RMS_THRESHOLD`（仅用于语义一致性说明，**不**越过端口直接 import；如需判静音，使用 `DB_FLOOR`）

**禁止 import**：
- `numpy` / `scipy` / `librosa` / 任何第三方信号库
- `harmonica_eval.algorithms.timing` / `pitch` / `score`（跨算法模块 import 属于上层调度范畴，本模块不得越权）
- 任何 `harmonica_eval.algorithms` 之外的模块路径
- 任何不在上述清单的本包内符号

---

## 4 · 你要实现什么（行为规格）

### `ALGORITHM_ID: str`
- 固定值为 `"dynamics"`。

### `ALGORITHM_VERSION: str`
- 固定值为 `"1.0.0"`。

### `DB_FLOOR: float`
- 固定值为 `-80.0`。
- 语义：线性 RMS 低于 `10 ** (-80.0 / 20)` ≈ `1e-4`（与 `core.ingest.SILENCE_RMS_THRESHOLD` 同量级）视为静音，不参与统计。
- 引用自 `harmonica_eval/core/ingest.py` 的 `SILENCE_RMS_THRESHOLD` 常量值域，**不得**改动。

### `to_db(rms: float) -> float`
- **输入**：线性 RMS（非负浮点）。`0` 或负值在钳位后统一当作静音。
- **算法**：先 `max(rms, 10 ** (DB_FLOOR / 20))` 钳位，再 `20 * math.log10(clamped)`。
- **边界**：`rms == 0` → 返回 `DB_FLOOR`（-80.0），**永远不返回 -inf**。
- **不变量**：返回值 ∈ [DB_FLOOR, ∞)；钳位前后单调。

### `note_spans(notes: list[dict]) -> list[tuple[int, int]]`
- **输入**：`notes.reference` 或 `notes.practice`，list，每项 dict 含 `onset_sec`（float）。
- **算法**：对第 n 个音，其帧区间为 `[frame(onset_sec_n), frame(onset_sec_{n+1}))`。
  - `frame(t)` 由 `core.ingest` 提供的帧率换算（每秒 100 帧），公式 `int(round(t * 100))`。
  - **最后一个音**延伸到 `frame(onset_sec_last) + 100`（默认 1 秒），或数据末尾帧，取其二者中较小。
- **边界**：`notes` 为空 → 返回 `[]`。单音 → 区间为 `[frame(onset), frame(onset)+100]`。
- **不变量**：返回区间左端 ≤ 右端；区间互不相交、覆盖从首音到末音之间的所有帧。

### `align_by_note(ref_rms_db, prac_rms_db, ref_spans, prac_spans) -> list[tuple[float, float]]`
- **输入**：
  - `ref_rms_db`: `list[float]`，长度为 `notes.reference` 的音数
  - `prac_rms_db`: `list[float]`，长度为 `notes.practice` 的音数
  - `ref_spans` / `prac_spans`: 各自 `note_spans` 输出
- **算法**：取 `min(len(ref), len(prac))`，配对第 0..n-1 个音，**丢弃**多出的音。
  - 每个配对音对的能量 = **该音所在帧区间内** `rms_db` 值的中位（`statistics.median`）。
  - 静音段（能量 ≤ DB_FLOOR）排除：对应音对不进入配对。
- **输出**：`list[tuple[float, float]]`，每个 tuple = `(ref_db, prac_db)`。
- **边界**：无可配对的音 → 返回 `[]`。
- **不变量**：返回长度 ≤ min(len(ref), len(prac))；对称性：交换 ref/prac 仅改变 tuple 内顺序，不改变配对数。

### `compute_deltas(aligned) -> list[float]`
- **输入**：`align_by_note` 输出。
- **算法**：对每个 `(ref_db, prac_db)` 算 `prac_db - ref_db`（**练习 − 参考**）。
- **输出**：`list[float]`，带符号，单位 dB。
- **边界**：`aligned` 为空 → `[]`。
- **不变量**：正值 = 练习更强；负值 = 练习更弱；零总和不一定。

### `summarize_deltas(deltas_db) -> dict`
- **输入**：`compute_deltas` 输出。
- **算法**：
  - `median_db` = `statistics.median(deltas_db)`（带符号）
  - `spread_db` = `statistics.median([abs(d - median_db) for d in deltas_db])`（**MAD**，绝对中位差，单位 dB）
    - ★ 明确选定：MAD，非 σ。MAD 对离群音更鲁棒，符合『均值相同却感知不同』的需求。
  - `n_notes_used` = `len(deltas_db)`
  - `n_unpaired` = **在 `run` 层由 `align_by_note` 计算**并回传，此处接收。
- **输出 dict key**：`median_db, spread_db, n_notes_used, n_unpaired`
- **边界**：`deltas_db` 为空 → `median_db=0.0, spread_db=0.0, n_notes_used=0`；`n_unpaired` 仍回报。
- **不变量**：永不输出 `pass/fail` / `is_valid` 字段。

### `run(surface: AlgorithmDataContract) -> AlgorithmResultEnvelope`
- **输入**：`AlgorithmDataContract`，只读。预期端口存在：
  - `surface.rms.reference`（`list[float]`）
  - `surface.rms.practice`（`list[float]`）
  - `surface.notes.reference`（`list[dict]`，含 `onset_sec`）
  - `surface.notes.practice`（`list[dict]`，含 `onset_sec`）
- **流程**：
  1. 读四个端口 → 各转 dB → `to_db`
  2. `note_spans(notes.reference)` 得 `ref_spans`
  3. `note_spans(notes.practice)` 得 `prac_spans`
  4. `align_by_note` 配对 → `aligned`
  5. `compute_deltas(aligned)` → `deltas_db`
  6. `summarize_deltas(deltas_db)` → 指标
  7. 装 `AlgorithmResultEnvelope(status='OK', payload={...})`
- **失败**：端口缺失/类型异常 → **不抛出**，返回 `AlgorithmResultEnvelope(status='FAILED', error=<str>)`。
- **不变量**：始终返回 `AlgorithmResultEnvelope`；从不抛异常向调用者。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出 / 返回 |
| --- | --- | --- |
| `rms.reference` 或 `rms.practice` 缺失 | 静默降级为不参与统计 | `AlgorithmResultEnvelope(status='FAILED', error='MISSING_RMS_PORT')` |
| `notes.reference` 或 `notes.practice` 缺失 | 无法按音配对 | `AlgorithmResultEnvelope(status='FAILED', error='MISSING_NOTES_PORT')` |
| `onset_sec` 非浮点 / 缺键 | 跳过该音 | 本音不进入配对，`n_unpaired` 递增 |
| RMS 全部 ≤ DB_FLOOR | 全段静音 | `AlgorithmResultEnvelope(status='OK', payload={'median_db':0.0,'spread_db':0.0,'n_notes_used':0,'n_unpaired':<count>})` |
| `deltas_db` 为空但有未配对音 | 仍报告 | `n_notes_used=0`, `n_unpaired>0` |
| 任何未预期异常 | 不向上抛出 | `AlgorithmResultEnvelope(status='FAILED', error=<repr 限长 128 字>)` |

★ 宪章 §5.6：禁止静默降级为 OK。所有缺端口/类型异常必须走 `status='FAILED'`。

---

## 6 · 必须满足的不变量（从 MUST / MUST NOT 铭牌逐条抄下）

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-06-1 | 消费 `rms.reference / rms.practice / notes.reference / notes.practice` | 代码审阅：`run` 内读取这四口 |
| INV-06-2 | 按音配对，**不**按时间轴 / 帧索引直接相减 | `align_by_note` 签名以 spans，非时间轴 |
| INV-06-3 | 输出以 dB 为单位 | 所有 delta ∈ dB；无 `to_db` 外的线性差 |
| INV-06-4 | 报告离散度（MAD），而非仅均值 | `summarize_deltas` 输出 `spread_db` 字段 |
| INV-06-5 | 失败也返回 `AlgorithmResultEnvelope` | `run` 外层 try/except，永不抛出 |
| INV-06-6 | 符号约定：练习 − 参考 | `compute_deltas` 单测：ref=0dB prac=+3dB → delta=+3 |
| INV-06-7 | 不输出教学结论 / pass 判据 | payload 中无 `pass`/`conclusion`/`grade` 等 key |
| INV-06-8 | 不引入 `AXIS` / TimelineBasis 概念 | 文本与代码中不出现 `AXIS` |

---

## 7 · 边界（明确不做）

- **不做**时间轴 Warp（WARPed 轴）—— 力度对的是第 n 音 vs 第 n 音。
- **不做**任何『力度达标』阈值—— 无 `DYNAMICS_PASS_DB`， 无 `is_valid`。
- **不做**跨音配对算法（最长公共子序列 / 动态规划）—— 仅音序一一配对。
- **不做**静音/含静态噪声的主观过滤—— 低于 `DB_FLOOR` 就当静音丢掉。
- **不做** `notes.*` 以外的 onset 来源—— 不接受 MIDI /外部 Onset。
- **不修改** `contract.py` / `core/ingest.py` 端口定义。

---

## 8 · 怎么验证你写对了

```bash
python -c "
from harmonica_eval.algorithms.dynamics import to_db, DB_FLOOR
assert DB_FLOOR == -80.0
assert to_db(1e-4) == -80.0          # 钳位边界
assert to_db(0.0) == -80.0           # 不返回 -inf
assert abs(to_db(1.0) - 0.0) < 1e-9  # 0 dBFS
assert abs(to_db(0.1) - (-20.0)) < 1e-9
print('to_db OK')
"
```

```bash
python -c "
from harmonica_eval.algorithms.dynamics import compute_deltas
d = compute_deltas([(0.0, 3.0), (-5.0, -2.0)])
assert d == [3.0, 3.0]              # 练习-参考
print('compute_deltas OK')
"
```

```bash
python -c "
from harmonica_eval.algorithms.dynamics import summarize_deltas
s = summarize_deltas([3.0, -1.0, 2.0])
assert s['n_notes_used'] == 3
assert abs(s['median_db'] - 2.0) < 1e-9
assert s['spread_db'] >= 0.0
assert 'pass' not in s and 'conclusion' not in s
print('summarize_deltas OK')
"
```

**验收判据**（可机械判定）：
- [ ] `python -m pytest tests/test_algorithms/test_dynamics.py` 全绿
- [ ] `grep -c "AXIS\|TimelineBasis" dynamics.py` == 0
- [ ] `to_db` 单元单测 5 个 assert 均通过
- [ ] `compute_deltas` 符号约定 assert 通过
- [ ] `summarize_deltas` 仅含 `median_db / spread_db / n_notes_used / n_unpaired`

---

## 9 · 完成后提交什么证据

- [ ] `harmonica_eval/algorithms/dynamics.py` 实现完毕，去除所有 `NotImplementedError`
- [ ] `data/out/test_dynamics.json` —— 黄金向量运行结果
- [ ] `tests/test_algorithms/test_dynamics.py` 单测产物复制到 stdout 的 pytest 日志
- [ ] `grep -c "AXIS" dynamics.py` 输出为 `0` 的证据

---

## 10 · ★ 何时必须停止并上报（宪章 §22 硬失败对策）

以下情况必须停止，提交 `MOLD BREAK`，不得自行设计：

1. **`notes.*` 缺少 `onset_sec`** —— 这意味着 onset 来源从 `timing.detect_onsets` 断裂，属于上游契约冲突。
2. **`core.ingest` 没有 `rms.reference`/`rms.practice`** —— 端口缺失，无法按音聚合。
3. **需要决定 `spread_db` 用 σ 还是 MAD** —— 已冻结为 MAD，见 §4。
4. **需要决定最后一个音延伸时长** —— 已冻结为 1 秒（100 帧），见 §4。
5. **需要新阈值判断力度合格** —— 与 MUST NOT 直接冲突，禁止。
6. **需要引入 `TimelineBasis` / WARPED 轴** —— 与 MOLD BREAK 修正冲突，禁止。

**上报格式**：
```
GATE CHALLENGE
- 相关 Requirement：SPEC.md@v2.1 §5.5
- 相关 Build Instruction 章节：FILE-203 §4 / §7
- 实际需要 vs 规格给出：<如实填写>
- 为什么冲突：<冲突点>
- 复现证据：<最小复现>
- 建议的上游处理位置：<timing.py / ingest.py / contract.py>
```

**绝对禁止**：
- 先做 workaround 以后再说
- 在代码里加『合理默认』掩盖
- 静默跳过未实现分支

---

## 附：本文件的冻结常量速查

| 常量 | 值 | 来源 |
| --- | --- | --- |
| `ALGORITHM_ID` | `"dynamics"` | dynamics.py L70（冻结） |
| `ALGORITHM_VERSION` | `"1.0.0"` | dynamics.py L71（冻结） |
| `DB_FLOOR` | `-80.0` | dynamics.py L73 / `core.ingest.SILENCE_RMS_THRESHOLD ≈ 1e-4` |
| 帧率 | 100 Hz | `core.ingest` 约定 |
| 最后一个音延伸 | 1 秒 | dynamics.py L97（冻结） |
| `spread_db` 算法 | MAD | dynamics.py L145 声明 |
</think>DONE .spec/build/FILE-203-v1.md</tool_call>