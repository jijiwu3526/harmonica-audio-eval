# `harmonica_eval/core/` — C2 数据面

> **本文档于 2026-09-26 依据源码重写。** 旧版是一份索引，其中「关键入口仍抛
> `NotImplementedError`」的陈述已被证伪（全目录 `NotImplementedError` **零命中**）。
> 冲突逐条记录在 §6。
> **权威仍在 `.spec/` 与源码铭牌。** 本文与它们冲突时以它们为准。

---

## 1 · 我是谁

`core/` 是 **C2 数据面**：把两段音频变成 **12 个端口**，而端口是算法的**唯一输入**。

```
两个 .wav 路径
   │
   ├─ ingest.py    220 行  解码 → 单声道 → 重采样 → 规格校验
   ├─ align.py     367 行  低分辨率 chroma → DTW → warp_path
   ├─ features.py  337 行  pitch / rms / chroma / notes
   ├─ surface.py   756 行  组装 Surface，seal 后只读
   └─ api.py       321 行  HostCore 协议
   │
   ▼
Surface（12 端口）→ C3 算法 → 16 个标量
```

**位置**：在 `contract.py`（冻结契约）之下、`algorithms/` 之上。
`core.__all__` 恰 **5** 项：`ingest` `align` `features` `surface` `api`。

---

## 2 · 我吃什么

| 入口 | 输入 | 约束 |
|---|---|---|
| `ingest.ingest` | 两个**仓库相对**路径 | 44.1 kHz / mono / **45–120 s** |
| `align.align` | ingest 产物 | — |
| `features.materialize_*` | align 产物 | — |
| `surface.build_surface` | 上述全部 | — |
| `api.HostCore` | 协议 | `acquire_surface` / `read` / `manifest` |

**★ 路径必须是仓库相对路径。** 绝对路径会被拒——实测报
`输入路径不存在或不是普通文件`。

**★ 规格校验在 `ingest.validate_duration`**，短于 45 s 或长于 120 s 都拒，
错误码 `INPUT_TOO_SHORT` / `INPUT_TOO_LONG`，**不是崩溃**。

---

## 3 · 我吐出什么

### 12 个端口（实测 `profile.PORTS`）

| port_id | dimensions | element_type | produced_by |
|---|---|---|---|
| `warp_path` | warp_point×axis | int32 | `core.align` |
| `pcm.mapped.reference` | sample | float32 | `core.surface` |
| `pcm.mapped.practice` | sample | float32 | `core.surface` |
| `pcm.warped.practice` | sample | float32 | `core.surface` |
| `pitch.reference` | frame×field | float32 | `core.features` |
| `pitch.practice` | frame×field | float32 | `core.features` |
| `rms.reference` | frame | float32 | `core.features` |
| `rms.practice` | frame | float32 | `core.features` |
| `chroma.lowres.reference` | frame×bin | float32 | `core.features` |
| `chroma.lowres.practice` | frame×bin | float32 | `core.features` |
| `notes.reference` | note×field | float32 | `core.features` |
| `notes.practice` | note×field | float32 | `core.features` |

**★ `PortSpec` 的九个字段（本节上一版只列了四个，★ 漏了 `hop_length` 与 `rationale`）★★**

```
port_id · units · dimensions · element_type · timeline_basis
produced_by · rationale · field_names · hop_length
```

**★ 两个不能省的字段 ★**

```
hop_length   帧移。★ 0 = 逐样本（非帧对齐），非 0 = 该端口每 hop_length 样本一帧
rationale    ★ 为什么【存在】。★ 它不是装饰——★ 读它才知道这个端口能不能删
             ★ 例：pcm.warped.practice 的 rationale 写着
             ★ 「它当前【无算法消费】。★ 保留的真实理由是数据面保证：
             ★   算法永远能拿到时间归一化后的 PCM 自行做特有预处理」
```

**★ `rationale` 里藏着两条防误改的记录（★ 2026-09-26 实测）★★**
```
★ warp_path：「相对 DTW 代价矩阵是 1/5300」——★ 有人会想「DTW 都不用了还留它」
★ pcm.mapped.practice：「逃生口甲」——★ practice 保留源时间，★ 节奏类指标
  只能在它上面算，★ 「用 warped 轴报抢拍拖拍是构造性错误（SPEC §5.5）」
★ ★ ★ 而这两条一旦被「优化」掉，★ 指标会安静地算错
```

### `timeline_basis` 决定那条轴能不能用（★ 最易错的一处）

```
REFERENCE  源时间网格。★ 抢拍拖拍在这一轴上可见
WARPED     归一化网格。★ ★ 抢拍拖拍已被抹掉

★ ★ ★ 而 profile 有一份 `SAMPLE_RATE_FREE_PREFIXES = {"chroma","notes","warp_path"}`
★ ★ ★ 意思是：这三个前缀【不受 sample_rate 换算影响】，★ 两侧都按 44100 取
★ ★ ★ ★ pcm.* 不在其中——★ 它是采样点序列，★ 必须换算
```

### 谁消费哪个端口（实测 `ALGORITHM_INPUTS`，非注释）

| 算法 | 实际消费 |
|---|---|
| `pitch` | `pitch.reference` `pitch.practice` `notes.reference` `notes.practice` |
| `timing` | `pcm.mapped.reference` `pcm.mapped.practice` `notes.reference` |
| `dynamics` | `rms.reference` `rms.practice` `notes.reference` `notes.practice` |

**★ 这张表决定插件作者能否拿到数据。** 加插件时在
`PluginSpec.required_inputs` 声明所需端口，装配根负责校验它是否被生产。

**★ 三个必须知道的事实**：

- `pcm.warped.practice` **当前无任何算法消费**。保留是「逃生口」——
  让算法永远能拿到时间归一化后的 PCM 自行做特有预处理，**不是缺陷**。
- `timing` 消费 `pcm.mapped.*`（**源时间**）而非 warped 轴。
  **用 warped 轴报抢拍拖拍是构造性错误**（SPEC §5.5）。
- `notes.practice` **确实被生产且被两个算法消费**——旧版「分工不完整」已不成立。

### Surface 的三个成员

```python
surface.manifest()     # 端口清单
surface.read(port_id)  # 读一个端口
surface.resolution     # 状态（当前为 None，见 §5 ②）
```

---

## 4 · ★ 我不做什么 ★

**这一节是全项目最缺的，而它最有价值。**

| 我不做 | 因为 | 依据 |
|---|---|---|
| **不算指标** | 16 个标量由 C3 算；core 只产端口 | `core/*.py` 无 `UiScalar` 构造 |
| **不装配插件** | Registry 与装配根在 C3 | `algorithms/bootstrap.py:326` |
| **不提供 HTTP** | 那是 C4 | `cockpit/app.py` |
| **不生成自然语言反馈** | SPEC 铁律 2 明令禁止 | `SPEC.md` |
| **不判定合格与否** | 端口只陈述数值，不下评语 | `SPEC.md` §3 |
| **不按算法要求改精度** | 精度由 `profile` 冻结，core 不图精度 | `align.py:124-126` |
| **不因平台而改写** | 换手机前端时**本目录一行不动** | 见下 |

**★ 核心边界一句话**：

> **core 是端口的生产者，端口是算法的唯一输入。**
> 界面层与数据面之间隔着一个无平台依赖的窄接口（`UiProjectionPort`），
> **core 与 `contract.py` / `profile.py` 都不需要改。**

**依赖面实测**（各文件顶层 `import`，★ 2026-09-26 重新逐文件核对）：

```
ingest   → numpy · scipy.signal.resample_poly · soundfile
align    → numpy · scipy.signal.stft · scipy.spatial.distance.cdist
features → numpy · ★ librosa（有则用）· ★ core.backend（numpy/scipy 自写后端）
surface  → numpy（本包内，无第三方）
api      → （无第三方 import）        ← ★ 旧文写「仅 typing」，★ 实为无
★ ★ torch 全目录零引用
```

### ★★ `features` 的两后端（★ 2026-09-26 新增，★ 换手机的直接依据）★★

**为什么会有两后端**：目标平台是 Android（arm64-v8a / API 34）。librosa 拖
numba/llvmlite，**设备上没有 wheel**，探针跑阶段 3 时就倒在裸
`import librosa` 上 —— **一个模块把整条阶段 3 拖垮**。
故 `core/backend/`（本目录新建）用 numpy+scipy 自写了那两个唯一的调用点。

| 后端 | chroma_stft | pyin | 依赖 | 何时生效 |
|---|---|---|---|---|
| `librosa` | `librosa.feature.chroma_stft` | `librosa.pyin` | librosa 0.11.0 | `import librosa` 成功（电脑） |
| `native` | `core/backend/chroma.py` | `core/backend/pyin.py` | numpy + scipy | librosa 装不上（手机） |

**两条路径的签名与返回值形状完全一致**，故「电脑上跑」与「手机上跑」是
**同一份代码的不同后端**：

```
chroma_stft → (n_chroma, n_frames) float32
pyin         → (f0, voiced_flag, voiced_prob)，三个 1-D、每帧一个值
```

**冻结的东西一个没动**：两个调用点的参数值、参数语义、
`VOICED_CONFIDENCE_FLOOR` 与 `confidence >= floor ⇒ voiced` 的**等号口径**，
全部原样。`features.py` 只加了一层**分派**。

强制指定后端（对拍用）：

```bash
DSH_FEATURE_BACKEND=native    python3 ...   # 强制自写
DSH_FEATURE_BACKEND=librosa   python3 ...   # 强制 librosa（缺它则显式失败，不静默退回）
```

`features.ACTIVE_BACKEND` / `ACTIVE_BACKEND_REASON` 暴露当前走的是哪条实现
（**只用于诊断与对拍，不参与任何数值决策**）。

**★ 对拍实测（电脑，4 段输入，判据未因结果而放宽）★★**

| 输入 | chroma Pearson r | chroma max\|Δ\| | pyin median\|Δcents\| | pyin max\|Δcents\| | 帧数 |
|---|---|---|---|---|---|
| 合成 12 s（seed=0） | **1.000000000** | 1.25e-06 | **0.0000** | 0.0000 | 相同 |
| 合成 8 s（seed=7） | **1.000000000** | 2.44e-06 | **0.0000** | 0.0000 | 相同 |
| 真实录音 `01_奇异恩典/原曲_完整版.wav`（前 12 s） | **1.000000000** | 1.43e-06 | **0.0000** | 0.0000 | 相同 |
| 真实录音 `01_奇异恩典/练习曲/02_节奏抢拖.wav`（前 12 s） | **1.000000000** | 1.43e-06 | **0.0000** | 0.0000 | 相同 |

附带：`voiced_flag` 一致率 **100.000%**；`voiced_prob` max\|Δ\| = **0.0**。

**★ 差异来源（★ 不是「差不多」，是可指认的浮点口径差）★★
- **chroma 残差 1e-6 量级**：librosa 内部用 float32 做 `einsum` 累加，
  自写用 float64 累加后再 cast float32 ⇒ 只有最后一位的舍入不同。
- **pyin 逐位一致**：两边调的是**同一个** `scipy.fft.rfft/irfft`、
  同一个 `next_fast_len`、同一个 `scipy.signal.get_window("hann", ..., fftbins=True)`。
  连 librosa 的两处 off-by-one 都刻意复刻了：
  `bin_index` 的 clip 上界是 `n_pitch_bins`（不是 `n_pitch_bins-1`）、
  `localmin` 首元素恒为 False。

复现：`python3 tools/verify_backend_equivalence.py`

**★ 对抗判据（★ 防「两边根本没各自算」——全对而无反证手段，与没测到同义）★★**

| 判据 | 内容 | 实测 |
|---|---|---|
| 判据4 | **屏蔽 librosa**，强制自写后端跑 `build_surface` 全部 **12 个端口** | **PASS** 12/12 端口非空、形状正确 |
| 判据5 | `sys.modules['librosa']=None` 后 `import features` | **PASS** → `ACTIVE_BACKEND = native` |

判据4 逐端口（20 s 切片，reference=原曲、practice=练习曲）：

| port_id | shape | 非空 | 全零 | NaN | hash librosa | hash native | 同? |
|---|---|---|---|---|---|---|---|
| `warp_path` | (443, 2) | OK | 否 | 无 | `dd6d5ac6…` | `dd6d5ac6…` | ✓ |
| `pcm.mapped.reference` | (882000,) | OK | 否 | 无 | `9835e424…` | `9835e424…` | ✓ |
| `pcm.mapped.practice` | (882000,) | OK | 否 | 无 | `351fbe4b…` | `351fbe4b…` | ✓ |
| `pcm.warped.practice` | (882000,) | OK | 否 | 无 | `ea824b24…` | `ea824b24…` | ✓ |
| `pitch.reference` | (430, 3) | OK | 否 | 无 | `d834fe4a…` | `d834fe4a…` | ✓ |
| `pitch.practice` | (430, 3) | OK | 否 | 无 | `e4da1409…` | `e4da1409…` | ✓ |
| `rms.reference` | (3442,) | OK | 否 | 无 | `9b0cd028…` | `9b0cd028…` | ✓ |
| `rms.practice` | (3442,) | OK | 否 | 无 | `b79236d5…` | `b79236d5…` | ✓ |
| `chroma.lowres.reference` | (431, 12) | OK | 否 | 无 | `e9a729a7…` | `d86ee64c…` | **✗** |
| `chroma.lowres.practice` | (431, 12) | OK | 否 | 无 | `e3f12e5d…` | `a19047d2…` | **✗** |
| `notes.reference` | (10, 3) | OK | 否 | 无 | `43aeae7d…` | `43aeae7d…` | ✓ |
| `notes.practice` | (11, 3) | OK | 否 | 无 | `5933eafa…` | `5933eafa…` | ✓ |

**★ 12 个端口里 10 个 content_hash 逐字节相同**——包括
`pitch.*`（pyin 的产物）与 `notes.*`（由 pitch 派生的逐音摘要），
这说明**自写 pyin 的输出与 librosa 逐位相同**，不是「差不多」。

**★ 只有 2 个 `chroma.lowres.*` 不同，差异可完整解释 ★**：
`max|Δ| = 1.431e-06`、`mean|Δ| = 7.57e-08`、
**Pearson r = 1.000000000000**。
来源单一：librosa 内部用 **float32** 做 `einsum` 累加，
自写用 **float64** 累加后再 cast float32 ⇒ 只有最后一位的舍入不同
（逐 bit 相同比例 15%，但相关系数是 1.000000000000）。

> ★ **判据是「12 端口全部非空 + 形状正确」，不是「hash 必须相同」。**
> ★ chroma 的 hash 不同**如实报告**，没有为了对上而调整任何判据或实现。

无 librosa 环境的端到端跑通：`python3 tools/verify_no_librosa_env.py`
（它在 import 前把 `librosa` 从 `__import__` 里挡掉，模拟设备）
⇒ 实测 `pitch`/`notes` 端口两后端 **max|Δ| = 0.0**，`chroma` 1.43e-06。
全 12 端口对拍：`python3 tools/verify_full_surface_backends.py`

**★ 逐个调用点（★ 换平台时按这张表定位，★ 不用通读）★★**

| 依赖 | file:line | 用途 | 换手机要换吗 |
|---|---|---|---|
| `soundfile` | `ingest.py:52` import · **`:89-94`** 唯一使用点 | `SoundFile(uri)` 读、`sf.samplerate`、`sf.read(always_2d=True)` | ★ **要换** |
| `scipy.signal.resample_poly` | `ingest.py:53` import · **`:137`** | 多相滤波重采样到 44100 | ★ **可能要换** |
| `scipy.signal.stft` | `align.py:72` import · **`:159`** | 对齐特征，nperseg=4096 | ★ **可能要换** |
| `scipy.spatial.distance.cdist` | `align.py:73` import | DTW 代价矩阵 | ★ **可能要换** |
| `pyin` | `features.py` 顶层分派 · 调用点 `materialize_pitch` | 逐帧基频 | ★ **不用换**（已有 native 后端） |
| `chroma_stft` | `features.py` 顶层分派 · 调用点 `materialize_chroma` | 12 音级能量 | ★ **不用换**（已有 native 后端） |
| `numpy` | 全部五文件 + `core/backend/*` | 数组运算 | ★ 移动端有成熟轮子 |

> ★ **换手机时 `core` 只有两处要改**：
> ★ **`ingest.py:89-94`（读音频）** 与 **`ingest.py:137`（重采样）**。
> ★ 其余全是 numpy 运算。
> ★ ★ 而 librosa 那两处（`pyin` / `chroma_stft`）**已经不需要换了** ——
> ★ ★ `core/backend/` 的 numpy/scipy 自写实现已与 librosa **逐位对上**
> ★ ★ （pyin 逐位一致、chroma 差在 float32 舍入的 1e-6 量级），
> ★ ★ 且**帧数完全相同**，故 `core/surface.py` 的帧对齐不受影响。

---

## 4.5 · ★ 边界守卫（★ 全部实测，★ 2026-09-26）★

**这一节回答「我喂它什么会得到什么、什么会报错」——★ 别人接手时最先踩的东西。**

### ★ `ingest` 阶段（★ 抛 `CoreBuildError`）

| 输入 | 实测结果 |
|---|---|
| 路径不存在 | `CoreBuildError: [INPUT_UNREADABLE] 路径不存在或不是普通文件：<path>` |
| 零字节文件 | `CoreBuildError: [INPUT_UNREADABLE] 解码失败：<path>（Error opening …）` |
| 10 秒音频（下限 45s） | `CoreBuildError: [INPUT_TOO_SHORT] 时长 10.000s 短于下限 45.0s（441000 样本 @ 44100 Hz）` |
| 全零音频 | `CoreBuildError: [INPUT_SILENT] 整段 RMS 0.000e+00 低于阈值 1.000e-04（线性幅度，非 dBFS）` |
| **60 秒正常** | ★ **OK，n=2646000** |

**★ 两条「不报错」的情形（★ 容易被误以为该拒绝）★★**
```
★ 双声道 60 秒 → ★ OK。★ ingest.py:75-76 用算术平均【下混单声道】，
  而非「只取第 0 声道」——★ 后者会静默丢弃另一声道
★ 48 kHz 60 秒 → ★ OK。★ resample_poly 重采样到 44100（ingest.py:137）
★ ★ ★ 而那条注释写明了原因：「FFT 法假设信号周期延拓」，★ 多相滤波无此假设
```

### 守卫清单（★ 精确位置）

| 守卫 | file:line | 作用 |
|---|---|---|
| `validate_duration` | `ingest.py:141` | 45–120 s 上下限 |
| `assert_not_silent` | `ingest.py:175` | RMS 低于 1e-4 |
| `assert_monotonic` | `align.py:299` | warp_path 必须单调 |
| `assert_budget` | `surface.py:420` | 端口总字节上限 |
| `_reject_nonfinite` | `features.py:79` | NaN / inf 拒绝 |
| `_check_rate` | `features.py:88` | 采样率须等于 profile |
| `_as_mono_float32` | `features.py:96` | dtype 与形状 |
| `_frame_count` | `features.py:108` | 帧数与 hop 一致 |
| `seal` | `surface.py:301` | 数组只读封装 |

### ★ 两条「静默出错」的高风险点（★ 改代码时最容易踩）★★

```
★ ingest.py:137  resample_poly(samples, 44100, native_sr)
★ ★ 若漏传 native_sr（写成两个 44100），★ 会静默产出原采样率的数组，★ 不报错
★
★ features.py:227  librosa.feature.chroma_stft(..., sr=sample_rate)
★ ★ 源码注释原话：「sr 必传：漏传会用 librosa 默认的 22050，
★ ★ 频率轴整体错一倍且不报错」
★ ★ ★ 而那种错【不抛异常】，★ 指标会安静地全错 —— ★ 本项目最防的那类假绿
```

---

## 5 · 遗留项（★ 已核实，★ 非阶段态残留）

**① `pcm.warped.practice` 无算法消费** —— 见 §3。保留是为数据面通用性。

**② `Surface.resolution` 返回 `None`** —— `contract.py:654-678` 声明它为只读状态，
而 `core/surface.py:112-145` 的 `Surface` 继承 `AlgorithmDataContract`，
因此该属性是 `None` 而非「不提供」。
**「谁负责把 C2 Surface 包装成含 `resolution` 的完整契约」仍未裁定。**

**③ `timing` 走 `pcm.mapped.*` 而非 warped 轴** —— 这是**正确设计**（SPEC §5.5），
记在此处以防后来者「修正」成 warped 轴。

---

## 6 · 冲突清单（★ 旧文档 vs 代码，★ 2026-09-26 实测）

| 旧文档陈述 | 实测结论 | 依据 |
|---|---|---|
| 「关键入口仍抛 `NotImplementedError("SHELL: …")`」 | **★ 已证伪。** 全目录 `NotImplementedError` **零命中**、`SHELL` **零命中**；实为 `CoreBuildError`（44 处） | `core/*.py` 全文 grep |
| 引 `ingest.py:96-105` 为抛 `NotImplementedError` | 该处现为 `raise CoreBuildError(INPUT_UNREADABLE, …)` | `ingest.py:96-105` |
| 引 `align.py:122-132` 同上 | 该处现为 `compute_alignment_features` 的 docstring | `align.py:122-132` |
| 「`notes.practice` 的现场分工不完整」 | **★ 已证伪。** 由 `core.features` 生产，`pitch`/`dynamics` 均消费 | `ALGORITHM_INPUTS` 实测 |
| 「`as_view()` / `manifest()` / `read()` 为 SHELL」 | **★ 已证伪。** 三者均已实现 | `surface.py:112-145` |
| 「`runtime.py:65-131` 为 SHELL」 | **★ 已证伪。** 该文件 `NotImplementedError` 零命中 | `algorithms/runtime.py` |

★ **六条里五条是「已废止的阶段态」** —— 它们**曾经为真**，所以读起来像事实。

### ★★ 本次（2026-09-26 第二次核对）新发现的三条

| # | 旧文档陈述 | 实测结论 | 依据 |
|---|---|---|---|
| ⑦ | §4 依赖表写 `features → numpy` | **★ 错，漏了 librosa。** `features.py:57` `import librosa`，`pyin`(:155) 与 `chroma_stft`(:227) 两处调用 | `grep -E "^import librosa"` |
| ⑧ | §4 依赖表写 `api → 仅 typing` | **★ 含糊。** `api.py` **无任何第三方 import**，连 `typing` 都不在顶层 | `grep -E "^(import\|from)" api.py` |
| ⑨ | §3 端口表只列 4 个字段 | **★ 不完整。** `PortSpec` 有 9 个字段，漏了 `hop_length` / `rationale` / `field_names` / `units` / `timeline_basis` | `dataclasses.fields(PortSpec)` |

★ **★ 而 ⑦ 那条最要紧：★ 若照旧表去「精简依赖」，会以为 librosa 没人用 ★★**
```bash
grep -n "librosa\." harmonica_eval/core/features.py
#   :155  librosa.pyin(...)
#   :227  librosa.feature.chroma_stft(...)
```

### ★ 本次新补的三节（旧文没有，★ 而它们是「掌控感」的一半）

```
§3 增补  PortSpec 九字段 + hop_length / rationale 的含义 + timeline_basis 陷阱
§4.5 新增 边界守卫（★ 9 个守卫的 file:line + 5 种非法输入的【实测异常】）
§4 改写  依赖调用点表（★ 7 个依赖逐个给 file:line + 换手机要换哪些）
★ ★ ★ 而「缺」比「错」更隐蔽 —— ★ 旧文的冲突清单里【没有一条是关于「缺」的】
```

---

## 7 · 规格对照

| 文件 | Build Instruction |
|---|---|
| `ingest.py` | [`FILE-101-v1.md`](../../.spec/build/FILE-101-v1.md) |
| `align.py` | [`FILE-102-v1.md`](../../.spec/build/FILE-102-v1.md) |
| `features.py` | [`FILE-103-v1.md`](../../.spec/build/FILE-103-v1.md) |
| `surface.py` | [`FILE-104-v1.md`](../../.spec/build/FILE-104-v1.md) |
| `api.py` | [`FILE-105-v1.md`](../../.spec/build/FILE-105-v1.md) |
| `__init__.py` | [`FILE-100-v1.md`](../../.spec/build/FILE-100-v1.md) |
| 端口声明 | [`FILE-004-v1.md`](../../.spec/build/FILE-004-v1.md)（`profile.py`） |
| 契约 | [`FILE-003-v1.md`](../../.spec/build/FILE-003-v1.md) |

---

## 8 · 复现

```bash
cd <仓库根>          # ★ clone 之后你的实际目录，★ 不是某个人的机器路径

# 一条命令跑通全链路
PYTHONDONTWRITEBYTECODE=1 python3 -m harmonica_eval \
  --reference harmonica_mvp_dataset/01_奇异恩典/标准旋律版.wav \
  --practice  harmonica_mvp_dataset/01_奇异恩典/练习曲/01_音准走调.wav

# §3 两张表的来源
PYTHONDONTWRITEBYTECODE=1 python3 -c "
import sys; sys.path.insert(0,'.')
from harmonica_eval import profile
for p in profile.PORTS: print(f'{p.port_id:26s} {p.produced_by}')"

PYTHONDONTWRITEBYTECODE=1 python3 -c "
import sys; sys.path.insert(0,'.')
from harmonica_eval.algorithms.bootstrap import ALGORITHM_INPUTS
for k, v in ALGORITHM_INPUTS.items(): print(k, list(v))"

# §3 PortSpec 九字段（★ 上一版只列了四个，★ 漏了两个）
PYTHONDONTWRITEBYTECODE=1 python3 -c "
import sys, dataclasses; sys.path.insert(0,'.')
from harmonica_eval import profile
print([f.name for f in dataclasses.fields(profile.PortSpec)])"

# §4 依赖调用点（★ 逐文件，★ 不靠印象）
for f in ingest align features surface api; do
  printf '%-9s ' "$f.py"
  grep -E "^(import|from) (numpy|scipy|soundfile|librosa)" \
    harmonica_eval/core/$f.py | grep -oE "(numpy|scipy|soundfile|librosa)" | sort -u | tr '\n' ' '
  echo
done

# §4.5 边界守卫（★ 实测，★ 不许写「应该会报错」）
PYTHONDONTWRITEBYTECODE=1 python3 -c "
import sys, numpy as np, soundfile as sf; sys.path.insert(0,'.')
t = np.arange(int(44100*10))/44100.0            # 10 秒 → 短于下限
sf.write('/tmp/_short.wav', (0.5*np.sin(2*np.pi*440*t)).astype('float32'), 44100, subtype='FLOAT')
sf.write('/tmp/_silent.wav', np.zeros(int(44100*60), dtype='float32'), 44100, subtype='FLOAT')
from harmonica_eval.core.ingest import ingest
for name in ('_short', '_silent'):
    try:
        ingest(f'/tmp/{name}.wav')
        print(name, '→ OK  ★ 但那说明守卫没生效')
    except Exception as e:
        print(name, '→', type(e).__name__, str(e)[:70])"

# 门禁
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_smoke_injection.py
```
