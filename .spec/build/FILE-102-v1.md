# FILE-102 — `harmonica_eval/core/align.py`

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/core/align.py`
> 生成依据：`harmonica_eval/profile.py`（常量 `WARP_PATH_MIN_COVERAGE`、`MONOTONICITY_TOLERANCE`）；`harmonica_eval/contract.py`（`FIELD_LAYOUTS`）；`harmonica_eval/exceptions.py`（`CoreBuildError`、`ALIGNMENT_UNRECOVERABLE`、`ContractViolation`）
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-102 |
| 所属组件 | COMP-C2 Audio Core |
| 层级 | L3（symbol / implementation） |
| 上游 | `profile.py` 提供 `ALIGN.hop_length`=`2048`、`ALIGN.n_chroma`、`ALIGN.band_rad`=`0.25`、`ALIGN.global_constraints`=`True`；`contract.py` 提供 `FIELD_LAYOUTS['warp_path']`=(reference_frame, practice_frame)；`features.py` 提供 `compute_alignment_features` 的 chroma 获取函数 |
| 下游 | `pipeline.py`、`evaluator.py` 调用 `align()` 获取 `warp_path` 用于后续评分 |
| 同层邻居 | `harmonica_eval/core/features.py`、`harmonica_eval/core/score.py` |

**你的权限**：只实现本文件 `align.py` 内的 4 个公开符号。不得修改 `profile.py`、`contract.py`、`exceptions.py` 或任何上游文件。不得增减输入输出端口。不得引入除 §3 列出的依赖以外的任何包。

---

## 2 · 这个文件为什么存在

本模块是全系统唯一的时间对齐发生地。它把「对齐」收敛到一处，并把对齐**分辨率**作为显式、可审、可实测的参数。

**删掉它会坏掉什么**：
- `pipeline.py` 和 `evaluator.py` 失去 `warp_path`，因而无法把 reference 与 practice 在时间轴上对应，所有后续评分（accuracy / timing / rhythm）变为纯逐点比较或彻底失败；客观数值指标体系-collapse。
- 对齐分辨率（`hop_length`=`2048`）这枚"855 MB → 53 MB"的内存杠杆**失去中心化约束**，任何调用方可自行选择更小 `hop` 导致内存爆炸，违反宪章 §5.6（No Silent Degradation）。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：
- Python 标准库：`math`
- 第三方（固定版本）：`numpy>=1.24.0`、`scipy>=1.10.0`（`scipy.spatial.distance.cdist`、`fastdtw` 不可用，必须用 `scipy` 或纯 `numpy` 实现DTW）
- 本包内：
  - `harmonica_eval.profile`（只读引用常量 `ALIGN.hop_length`=`2048`、`ALIGN.n_chroma`、`ALIGN.band_rad`=`0.25`、`ALIGN.global_constraints`=`True`）
  - `harmonica_eval.contract`（引用 `FIELD_LAYOUTS['warp_path']`）
  - `harmonica_eval.exceptions`（`CoreBuildError`、`ALIGNMENT_UNRECOVERABLE`、`ContractViolation`）

**禁止 import**：
- `librosa`
- `dtw` / `dtw-python` / `tslearn` / `fastdtw`
- 任何音频 I/O 库（`soundfile`、`pydub` 等）
- 任何不在上述清单里的东西

---

## 4 · 你要实现什么（行为规格）

### `compute_alignment_features(samples: npt.NDArray) -> npt.NDArray`
- **输入**：`samples` — `float32` 1-D 数组，单声道 PCM，有取值域 [-1.0, 1.0]。
- **输出**：`float32` 2-D 数组，形状 `(n_chroma, n_frames)`；`n_chroma` = `profile.ALIGN.n_chroma`；`n_frames` 由输入时长与 `profile.ALIGN.hop_length`=`2048` 决定。
- **算法口径**：
  - 使用 `scipy.signal.stft`，`nperseg=4096`、`noverlap=2048`、`window='hann'`、`fs=int(profile.ALIGN.hop_length)`。
  - 对 STFT 结果做 Chroma-sensitive 降维：对每个 frame 取 12-bin pitch-class 幅值加和（librosa-style CQT-chroma 不可用，必须沿用上式）。
  - **强制下采样**：中间结果 dtype 恒保持 `float32`，不得临时提升至 `float64` 再回转。
- **边界**：
  - `samples.shape == (0,)` → 抛 `CoreBuildError(ALIGNMENT_UNRECOVERABLE)`。
  - `samples` 维度 != 1 → 抛 `CoreBuildError(ALIGNMENT_UNRECOVERABLE)`。
- **不变量**：返回 dtype 恒 `float32`；`n_frames >= 1` 当且仅当 `len(samples) >= 1`。

### `compute_warp_path(ref_features: npt.NDArray, prac_features: npt.NDArray) -> npt.NDArray`
- **输入**：
  - `ref_features` — `float32` 2-D 数组，形状 `(n_chroma_ref, n_frames_ref)`。
  - `prac_features` — `float32` 2-D 数组，形状 `(n_chroma_prac, n_frames_prac)`。
- **输出**：`int32` 2-D 数组，形状 `(path_len, 2)`，列顺序 = `contract.FIELD_LAYOUTS['warp_path']` = `(reference_frame, practice_frame)`。
- **算法口径**：
  - 距离矩阵 `D` 的 dtype **固定 `float64`**，形状 `(n_frames_ref, n_frames_prac)`，使用欧氏距离（`scipy.spatial.distance.cdist`）计算 chroma 帧间距离。
  - DTW 累积代价矩阵 `C` 复用 `D` 内存（写回），dtype 亦 `float64`。
  - `global_constraints=True` 时：约束搜索带宽 `band_rad=0.25`（即 |i/len_ref − j/len_prac| <= 0.25）。带宽约束**仅降低计算量，不减少矩阵分配**。
  - 回溯从 `(n_frames_ref−1, n_frames_prac−1)` 到 `(0, 0)`，贪心选最小 predecessor。
  - **立即释放**：在回溯完成后、返回前执行 `del D, C` 并调用 `gc.collect()`。
- **边界**：
  - 任一输入为空 → 抛 `CoreBuildError(ALIGNMENT_UNRECOVERABLE)`。
  - 任一输入维度 != 2 → 抛 `CoreBuildError(ALIGNMENT_UNRECOVERABLE)`。
  - 对齐失败（路径长度为 0） → 抛 `CoreBuildError(ALIGNMENT_UNRECOVERABLE)`。
- **不变量**：返回 dtype 恒 `int32`；`path_len >= 1`；每个 reference_frame 值域 [0, n_frames_ref−1]。

### `assert_monotonic(warp_path: npt.NDArray) -> None`
- **输入**：`warp_path` — 同 `compute_warp_path` 输出类型。
- **输出**：`None`，副作用仅在校验失败时抛异常。
- **算法口量**：
  - 取第 0 列 `reference_frame`；记 `diffs[i] = warp_path[i+1, 0] − warp_path[i, 0]`。
  - 允许回退量上限 = `MONOTONICITY_TOLERANCE`（**固定 0**）。
  - 若 `any(diffs < −MONOTONICITY_TOLERANCE)` → 抛 `ContractViolation('warp_path not monotonic')`。
- **边界**：
  - `warp_path` 行数 < 2 → 不抛，返回 `None`（单点路径天然单调）。
- **不变量**：无副作用；校验通过后 `warp_path` 未被修改。

### `measure_coverage(warp_path: npt.NDArray, n_ref_frames: int) -> float`
- **输入**：
  - `warp_path` — 同上。
  - `n_ref_frames` — `int`，参考特征的总帧数。
- **输出**：`float32` 标量，范围 [0.0, 1.0]。
- **算法口径**：
  - `covered = len(unique(warp_path[:, 0]))`
  - `coverage = covered / n_ref_frames`，结果 cast 为 `float32`。
- **边界**：
  - `n_ref_frames <= 0` → 抛 `CoreBuildError(ALIGNMENT_UNRECOVERABLE)`。
  - `warp_path` 为空 → coverage = 0.0。
- **不变量**：返回值 ∈ [0.0, 1.0]。

### `align(reference: npt.NDArray, practice: npt.NDArray) -> npt.NDArray`
- **输入**：`reference`、`practice` — `float32` 1-D 单声道 PCM。
- **输出**：`int32` 2-D 数组 `(N, 2)` — warp path。
- **算法口径**：
  1. `ref_feat = compute_alignment_features(reference)`
  2. `prac_feat = compute_alignment_features(practice)`
  3. `wp = compute_warp_path(ref_feat, prac_feat)`
  4. `assert_monotonic(wp)` — 失败抛 `ContractViolation`，**不能**被 `except` 吸收
  5. `cov = measure_coverage(wp, ref_feat.shape[1])`
  6. 若 `cov < WARP_PATH_MIN_COVERAGE`（**固定 0.90**） → 抛 `CoreBuildError(ALIGNMENT_UNRECOVERABLE)`
  7. 返回 `wp`
- **边界**：任一步抛 `ALIGNMENT_UNRECOVERABLE` 或 `ContractViolation`，**严禁**降级为逐点硬比。
- **不变量**：返回前代价矩阵与特征矩阵已释放；返回值 dtype 恒 `int32`。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| `reference` 为空 | 显式失败 | `CoreBuildError(ALIGNMENT_UNRECOVERABLE)` |
| `reference` 非 1-D | 显式失败 | `CoreBuildError(ALIGNMENT_UNRECOVERABLE)` |
| `compute_warp_path` 路径长度为 0 | 显式失败 | `CoreBuildError(ALIGNMENT_UNRECOVERABLE)` |
| `measure_coverage` `n_ref_frames <= 0` | 显式失败 | `CoreBuildError(ALIGNMENT_UNRECOVERABLE)` |
| coverage < 0.90 | 显式失败 | `CoreBuildError(ALIGNMENT_UNRECOVERABLE)` |
| `assert_monotonic` 失败 | 显式失败 | `ContractViolation` |

★ 宪章 §5.6：**禁止**任何"算不出来就返回默认值/空路径"的静默降级。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-102-1 | `WARP_PATH_MIN_COVERAGE` 引用自 `profile.py`，值 **固定 0.90** | `assert align.WARP_PATH_MIN_COVERAGE == 0.90` |
| INV-102-2 | `MONOTONICITY_TOLERANCE` 引用自 `profile.py`，值 **固定 0** | `assert align.MONOTONICITY_TOLERANCE == 0` |
| INV-102-3 | `compute_alignment_features` 返回 dtype 恒 `float32` | `assert wp.dtype == np.float32` |
| INV-102-4 | `compute_warp_path` 返回 dtype 恒 `int32` | `assert wp.dtype == np.int32` |
| INV-102-5 | warp_path 列顺序 = `contract.FIELD_LAYOUTS['warp_path']` | `assert contract.FIELD_LAYOUTS['warp_path'] == ('reference_frame', 'practice_frame')` |
| INV-102-6 | DTW 距离矩阵 dtype **固定 `float64`** | 代码 audit，确保 `D.dtype == np.float64` |
| INV-102-7 | 回溯后立即释放代价矩阵 | 代码 audit，`del D, C` + `gc.collect()` 出现在回溯后 |
| INV-102-8 | coverage 阈值 **写死 0.90** | 代码 audit，`if cov < 0.90` 或引用 `WARP_PATH_MIN_COVERAGE` |
| INV-102-9 | `align` 内部 **不得** `try/except` 吸收 `ContractViolation` | 代码 audit |

---

## 7 · 边界（明确不做）

- 不实现 `features.py` 中 chroma 特征的终版逻辑 —— 此模块只是**消费** `features.py` 的输出，或在 `compute_alignment_features` 内做最简包装。
- 不引入 `fastdtw` 等近似算法 —— 必须精确 DTW。
- 不暴露 `band_rad` / `global_constraints` 为参数 —— 直接从 `profile.ALIGN` 读。
- 不提供 CLI / `__main__` /任何 I/O。
- 不实现评分逻辑（accuracy / timing / rhythm）。

---

## 8 · 怎么验证你写对了

```bash
python -c "
import numpy as np
from harmonica_eval.core import align
from harmonica_eval.exceptions import CoreBuildError, ContractViolation

# 1. 对齐成功
ref = np.random.randn(44100).astype(np.float32)
prac = ref.copy()
wp = align.align(ref, prac)
assert wp.dtype == np.int32
assert wp.shape[1] == 2
assert wp[0, 0] == 0 and wp[-1, 0] == ref.shape[0]-1 or wp[-1,0] > 0
assert wp[0, 1] == 0
assert align.measure_coverage(wp, wp[:, 0].max()+1) >= 0.90

# 2. 空输入
try:
    align.align(np.array([], dtype=np.float32), ref)
    assert False, 'should raise'
except CoreBuildError:
    pass

# 3. 单调校验
monotonic = np.array([[0, 0], [1, 1], [2, 2]], dtype=np.int32)
assert align.assert_monotonic(monotonic) is None

non_monotonic = np.array([[0, 0], [2, 2], [1, 1]], dtype=np.int32)
try:
    align.assert_monotonic(non_monotonic)
    assert False, 'should raise'
except ContractViolation:
    pass

# 4. coverage 边界
assert align.measure_coverage(np.array([[0, 0], [2, 1]], dtype=np.int32), 3) == 2/3
assert align.measure_coverage(wp, 5) == 1.0
"
```

**验收判据**：
- [ ] `align.align()` 对合法输入返回 `int32[N,2]` warp path
- [ ] 空输入 / 维度错 → `CoreBuildError(ALIGNMENT_UNRECOVERABLE)`
- [ ] 非单调路径 → `ContractViolation`
- [ ] coverage < 0.90 → `CoreBuildError(ALIGNMENT_UNRECOVERABLE)`
- [ ] `WARP_PATH_MIN_COVERAGE==0.90` 且 `MONOTONICITY_TOLERANCE==0`
- [ ] DTW 距离矩阵 dtype == `float64`，回溯后 `del`+gc
- [ ] `from harmonica_eval.core import align` 成功

---

## 9 · 完成后提交什么证据

- [ ] `harmonica_eval/core/align.py`（实现文件）
- [ ] §8 bash 验证脚本执行成功，粘贴 stdout 日志
- [ ] `from harmonica_eval.core import align` 无 `ImportError`

---

## 10 · ★ 何时必须停止并上报

**以下情况必须停止，提交 `MOLD BREAK`，不得自行设计：**

1. 你发现本文件**需要做上层设计**才能实现（例如：需要决定一个新阈值 / 新口径 / 新端口 / 新错误码）
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

**绝对禁止**：
- 先做一个"能跑的 workaround"，以后再说（§38 明文禁止）
- 自行在代码里加一个"合理的"默认值把冲突掩盖过去
- 静默缩小范围（"这个分支我先不实现")

---

## 附：本文件的冻结常量速查

| 常量 | 值 | 来源 |
| --- | --- | --- |
| `WARP_PATH_MIN_COVERAGE` | 0.90 | `align.py` L49 |
| `MONOTONICITY_TOLERANCE` | 0 | `align.py` L56 |
| `profile.ALIGN.hop_length` | 2048 | `profile.py` |
| `profile.ALIGN.n_chroma` | — | `profile.py` |
| `profile.ALIGN.band_rad` | 0.25 | `profile.py` |
| `profile.ALIGN.global_constraints` | True | `profile.py` |
| `contract.FIELD_LAYOUTS['warp_path']` | (reference_frame, practice_frame) | `contract.py` |
| `ALIGNMENT_UNRECOVERABLE` | — | `exceptions.py` |
| `ContractViolation` | — | `exceptions.py` |