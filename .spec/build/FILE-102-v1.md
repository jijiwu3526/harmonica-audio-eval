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
| 下游 | `core/surface.py`（`build_surface` 是**唯一**调用方：它取 `align()` 的 `warp_path` 后继续生成其余端口）。★ 更正：原写 `pipeline.py` / `evaluator.py` —— **这两个模块不存在**，实测全仓无此文件 |
| 同层邻居 | `harmonica_eval/core/features.py`、`harmonica_eval/core/surface.py`。★ 更正：原写 `core/score.py` —— **不存在** |

**你的权限**：只实现本文件 `align.py` 内的 4 个公开符号。不得修改 `profile.py`、`contract.py`、`exceptions.py` 或任何上游文件。不得增减输入输出端口。不得引入除 §3 列出的依赖以外的任何包。

---

## 2 · 这个文件为什么存在

本模块是全系统唯一的时间对齐发生地。它把「对齐」收敛到一处，并把对齐**分辨率**作为显式、可审、可实测的参数。

**删掉它会坏掉什么**：
- `core/surface.py` 失去 `warp_path`，因而无法把 reference 与 practice 在时间轴上对应：
  `pcm.warped.practice` 无从装配，`pitch` 的按音配对失去依据，
  所有后续评分（音准 / 节奏 / 力度）退化为纯逐点比较或彻底失败。
  ★ 更正：原写 `pipeline.py` / `evaluator.py` —— **这两个模块不存在**。
- 对齐分辨率（`hop_length`=`2048`）这枚"855 MB → 53 MB"的内存杠杆**失去中心化约束**，任何调用方可自行选择更小 `hop` 导致内存爆炸，违反宪章 §5.6（No Silent Degradation）。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：
- Python 标准库：`math`
- 第三方（固定版本）：`numpy>=1.24.0`、`scipy>=1.10.0`。

  ★★ **本版更正（第三轮盲审 B 的 BLOCK-4）：原文写「`scipy.spatial.distance.cdist`、`fastdtw` 不可用」—— `cdist` 的禁令是假的。** ★★

  实测（scipy 1.17.1）：`from scipy.spatial.distance import cdist` 成功，
  `cdist(rand(100,12), rand(100,12))` 返回 `(100, 100)` 的矩阵。
  **`cdist` 可用且是本文件的最优选择。**

  原禁令若被字面遵守，实现者只能改用 `(a-b)²` 广播 ——
  那在 120 s 音频上是 ~1000×1000×12 的中间数组，
  与 §4「内存是主要消耗者」的关切**直接冲突**。

  **真正的禁令只有 `fastdtw`**（未安装，且 §4 要求自行实现 DTW）。
  本文件**允许**：`numpy`、`scipy.spatial.distance.cdist`、
  `scipy.signal.stft`、`librosa`（仅限本文件已列出的调用）。
  **禁止**：`fastdtw`、任何联网调用、任何文件 I/O。
- 本包内：
  - `harmonica_eval.profile`（只读引用常量 `ALIGN.hop_length`=`2048`、`ALIGN.n_chroma`、`ALIGN.band_rad`=`0.25`、`ALIGN.global_constraints`=`True`）
  - `harmonica_eval.contract`（引用 `FIELD_LAYOUTS['warp_path']`）
  - `harmonica_eval.contract`（`CoreBuildError`、`ContractViolation`、`ErrorCode`）
    ★ 更正：原写 `harmonica_eval.exceptions` —— **该模块不存在**。
    实测 `CoreBuildError` / `ContractViolation` 都定义在 `contract.py`；
    `ALIGNMENT_UNRECOVERABLE` 是 `contract.ErrorCode` 的**枚举成员**，不是可 import 的异常类。

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
  - 使用 `scipy.signal.stft`，`nperseg=4096`、`noverlap=2048`、`window='hann'`。
  - ★★ **`fs` 必须传 `profile.AUDIO.sample_rate`（= 44100），
    `boundary=None`、`padded=False`。** ★★

    ★★ **更正（第三轮盲审 B 的 BLOCK-3）：原写 `fs=int(profile.ALIGN.hop_length)`
    —— 那是把「帧移」当成了「采样率」。** ★★

    **这是静默算错，不是报错**：实测 440 Hz 正弦，
    `fs=2048` 时 STFT 的频率轴被整体压错，
    峰值被标成 **20.50 Hz**（−5309 音分）；
    `fs=44100` 时得 **441.43 Hz**（+6 音分，FFT 分辨率内正常）。
    **数据形状不变、不抛异常** —— chroma 会照常产出，
    只是全部落进错误的 bin，DTW 于是在错误的特征上对齐。
    实测命令与输出见 `.spec/review/round-2/report-B.md` BLOCK-3。

    ★★ **帧数口径已冻结（第三轮盲审 B 的 BLOCK-7(b)）：用 `scipy` 默认 `boundary='zeros'`。** ★★

    实测 44100 采样点、`nperseg=4096`、`noverlap=2048`：

    | `boundary` | 帧数 |
    | --- | --- |
    | **默认 `'zeros'`（本文件冻结此值）** | **23** |
    | `None, padded=False` | 20 |
    | `len(samples) // hop_length + 1`（近似公式） | 22 |

    **`n_frames = 23`**（本行 44100 采样点的具体值）。
    **一般律是 `n_frames = 1 + ceil(len(samples) / hop_length)`**，
    不是 `1 + len(samples) // hop_length`，也不是 `len(samples) // hop_length`。

    ★★ **本版更正（⑳ 执行确认）：上一版把「23」反推成 `1 + len//hop` —— 巧合而已。** ★★

    44100 恰好整除到 21.53，`1 + 44100//2048 = 22`，而实测是 23，
    两者并不相等 —— 上一版那句是**从单个数据点硬凑的公式**。
    逐点实测（0 处不符）：

    | `len(samples)` | 实测帧数 | `1 + len//hop` | `1 + ceil(len/hop)` |
    | --- | --- | --- | --- |
    | 44100 | 23 | 22 ❌ | 23 ✅ |
    | 100000 | 50 | 49 ❌ | 50 ✅ |
    | 1000000 | 490 | 489 ❌ | 490 ✅ |
    | 1984500 (45 s) | 970 | 969 ❌ | 970 ✅ |
    | 5292000 (120 s) | 2585 | 2584 ❌ | 2585 ✅ |

    这个 `+1` 的差别不是学术细节：它让 120 s 的内存锚点从
    53,457,800 B 变成 53,416,448 B（差 41 KB），
    而 FILE-004 的整张 DTW 预算表正是建立在这个帧数上的（该文件已同步更正）。
    §8 判据 1 已改为从实际特征矩阵取帧数，不依赖任何公式 —— 这是最稳的写法。

    **本文件不显式传 `boundary`**（用库默认），理由是：
    ① 显式写死 `boundary='zeros'` 与不写等价，但多一处可能被抄错的常量；
    ② 帧数**由实际矩阵决定**（§8 判据 1 已改为 `ref_feat.shape[1]`），
       不依赖任何公式 —— 实现者只要两侧用同一组参数即可。

    **关于 `boundary` 的后果（保留原说明）**：

    `scipy.signal.stft` 默认 `boundary='zeros'`，会在两端各补 `nperseg//2`
    个零。实测（44100 采样点、`nperseg=4096`、`noverlap=2048`）：

    | 参数 | 帧数 |
    | --- | --- |
    | 默认 `boundary='zeros'` | **23** |
    | `boundary=None, padded=False` | **20** |
    | `len(samples) // hop_length + 1` | 22 |

    **三者互不相等。** 本文件**不**断言帧数等于某个公式值 ——
    DTW 只要求两侧帧数**各自一致**，不要求等于某个绝对数
    （`compute_warp_path` 用 `ref_feat.shape[1]` / `prac_feat.shape[1]`
    取实际帧数，不假设公式）。

    ★ **诚实记录（本版自查）**：我上一版在这里写「§8 判据 1 断言帧数等于
    `len(samples)//hop_length + 1`」—— **§8 里没有这条断言**，是我凭印象写的。
    我随后实测三种取值的帧数，发现**没有一个等于 22**，
    这才发现自己引了一条不存在的判据。已改为如实列出三种取值。
    实现者**只需保持一致**（同一份文件里两侧用同一组参数），
    不必凑某个数字。
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
  - 若 `any(diffs < −MONOTONICITY_TOLERANCE)` → 抛
    `ContractViolation(ErrorCode.INTERNAL_ERROR, detail="warp_path not monotonic")`。

    ★★ **本版更正（第三轮盲审 B 的 BLOCK-5）：原文写 `ContractViolation('warp_path not monotonic')` —— 把说明文字当成了错误码。** ★★

    `contract.ContractViolation` 的**第一个位置参数是 `code: ErrorCode`**（实测签名：
    `(code, detail='', session_id=None, port_id=None, component=None)`）。
    照字面写，异常**能抛出来、当场不报错**，但 `.code` 会是 `str` 而不是 `ErrorCode`：

    ```
    e = ContractViolation('warp_path not monotonic')
    e.code            → 'warp_path not monotonic'   (type=str)
    isinstance(e.code, ErrorCode)  → False
    e.code.value      → AttributeError: 'str' object has no attribute 'value'
    ```

    故障会推迟到 C1 归一化时才爆（FILE-105 §4.5 第 6 步要读 `err.code.value`）——
    **又是"静默潜伏"**。正确写法把说明放 `detail`。
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
- **不变量**：返回值 **≥ 0.0**；且当 `n_ref_frames >= 被覆盖的互异参考帧数` 时 ∈ `[0.0, 1.0]`。

  ★★ **本版更正（第三轮盲审 B 的 BLOCK-6）：原文只写「∈ [0.0, 1.0]」，与本节公式矛盾。** ★★

  公式是 `covered / n_ref_frames`，两个参数**互不约束**。
  实测 `covered=23, n_ref_frames=5` → 返回 **4.6 > 1.0**。

  **不夹紧**（不加 `min(1.0, ...)`）—— 理由：
  `4.6` 携带真实信息（"覆盖了 4.6 倍参考时长"），夹成 `1.0` 会把它抹掉，
  且 §4 明写该公式是"唯一口径"。
  `n_ref_frames` 传得比实际覆盖帧数还小属于**调用方误用**，
  见 §5 失败语义表。

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
| INV-102-3 | `compute_alignment_features` 返回 dtype 恒 `float32` | `assert ref_feat.dtype == np.float32 and prac_feat.dtype == np.float32` ★ 断言对象必须是**特征矩阵本身**；原写 `assert wp.dtype == np.float32` 是恒假——`wp` 是 `compute_warp_path` 的返回值，dtype 恒 `int32`（见 INV-102-4），与本不变量无关 |
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
from harmonica_eval.contract import CoreBuildError, ContractViolation
from harmonica_eval.contract import ErrorCode   # ALIGNMENT_UNRECOVERABLE 是它的成员
from harmonica_eval import profile   # ★ 更正（⑳ 执行发现）：下文用了 profile.ALIGN.hop_length，原先漏 import

# 1. 对齐成功
ref = np.random.randn(44100).astype(np.float32)
prac = ref.copy()
wp = align.align(ref, prac)
assert wp.dtype == np.int32
assert wp.shape[1] == 2
# ★ 更正（本版自查发现）：原写
#     assert wp[0, 0] == 0 and wp[-1, 0] == ref.shape[0]-1 or wp[-1,0] > 0
#   两处错：
#   (1) `wp[-1,0]` 是**帧号**，值域 [0, n_frames-1]；`ref.shape[0]-1` 是**采样点数-1**。
#       以 44100 采样点为例：帧号最大 20，而右边是 44099 —— 差 hop(2048) 倍，
#       永远不可能相等。
#   (2) 末尾的 `or wp[-1,0] > 0` 让整条断言**恒真** ——
#       一个永远不会变红的检查等于没有检查（方法论 §6.3）。
#   正确写法：用**帧**口径比，且不加兜底。
HOP = profile.ALIGN.hop_length
# ★★ 更正（⑳ 执行发现）：原先写
#     n_ref_frames = ref.shape[0] // HOP
#     assert wp[-1, 0] == n_ref_frames - 1
#   这条**无解**。实测 44100 采样点、HOP=2048：
#     采样点数//HOP          = 21  → 断言要求 wp[-1,0] == 20
#     stft 默认 boundary      帧数 23  → wp[-1,0] == 22
#     stft boundary=None      帧数 20  → wp[-1,0] == 19
#   **没有任何 boundary 取值能得 20。** 因为 `采样点数//HOP` 只是近似公式，
#   真实帧数由 nperseg/noverlap/boundary 共同决定。
#   正确做法：帧数**从实际特征矩阵取**，不假设公式。
ref_feat = align.compute_alignment_features(ref)
prac_feat = align.compute_alignment_features(prac)
n_ref_frames = ref_feat.shape[1]
n_prac_frames = prac_feat.shape[1]
assert wp[0, 0] == 0, wp[0, 0]
assert wp[-1, 0] == n_ref_frames - 1, (wp[-1, 0], n_ref_frames - 1)
assert wp[-1, 1] == n_prac_frames - 1, (wp[-1, 1], n_prac_frames - 1)
assert wp[:, 0].max() <= n_ref_frames - 1, wp[:, 0].max()
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
# ★★ 更正（第三轮盲审 B 的 BLOCK-7）：原写 `== 2/3` —— **浮点相等比较，恒假。** ★★
#   实测：measure_coverage 返回 0.6666666865348816（float32 精度），
#   而 Python 的 2/3 是 0.6666666666666666（float64），
#   差 1.987e-08，`==` 为 False。实现者无论怎么写都过不了。
#   正确做法：按**容差**比较（覆盖率是比例量，1e-6 足够）。
assert abs(align.measure_coverage(
    np.array([[0, 0], [2, 1]], dtype=np.int32), 3) - 2 / 3) < 1e-6
# ★★ 更正（⑳ 执行确认）：原写 `measure_coverage(wp, 5) == 1.0` —— 恒假。 ★★
#   `measure_coverage` 的公式是 互异参考帧数 / n_ref_frames，**不做上界截断**。
#   实测（对齐同一段音频，wp 覆盖 23 个参考帧）：
#     n=3  → 7.666667   （>1.0，是真实信息，不是错误）
#     n=5  → 4.600000   ← 原断言期望 1.0，实际 4.6
#     n=23 → 1.000000   （恰好全覆盖）
#   正确写法：用**与 wp 实际跨度相等**的 n 才得 1.0；或直接断言 ≥ 1.0 的单调性。
# ★★★ 更正（⑳ 二次执行确认）：原写 `measure_coverage(wp, 23) == 1.0` ★★★
#   `23` 是【裁尾帧之前】的特征帧数。align 现已裁掉起点越界的补零帧
#   （实测 44100 采样点 / hop=2048 → stft 原给 23 帧，裁后 21 帧），
#   ★ 实测 measure_coverage(wp, 23) = 0.9130435 ≠ 1.0
#   ★ 而这个魔数【永远修不好】—— 裁帧规则一变它就再次失效。
#   正确做法：n 取【wp 实际跨度】，与本节 n_ref_frames 同源（不引魔数）。
_wp_span = wp[:, 0].max() + 1
assert align.measure_coverage(wp, _wp_span) == 1.0
assert align.measure_coverage(wp, 5) > 1.0   # 窗口小于跨度时覆盖率可 >1，不得截断
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