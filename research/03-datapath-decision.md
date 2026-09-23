# 03 · 数据通路决策（OC1 关闭）

> 本文件关闭 `COMPONENTS.md` §8 的 **OC1**（数据面形态未决项）。
> 方法：外部调研（子智能体，含出处）+ 本机实测（两个 SPIKE）。
> 结论均为**实测支持**或**明确标注为推断**。

---

## 0. 决策摘要

| 决策 | 内容 |
| --- | --- |
| **D1 对齐分辨率是内存主杠杆** | DTW 用**低分辨率**（hop=2048 或更宽），**不是**频谱档数 |
| **D2 不预存派生数据** | 频谱类按需现算（实测 65 ms/档）；只物化小摘要 |
| **D3 真正要物化的极小** | warp path（165 KB）+ RMS 包络 + 低分辨率 chroma |
| **D4 存储用只读 memmap** | 不引入 HDF5 / Zarr（手机端无可用绑定） |
| **D5 契约承诺"可获取"，不承诺"已物化"** | aligned PCM 永远**能拿到**；是否预先算好是实现自由 |

---

## 1. 触发这次调研的原因

负责人提出疑问：*"难道流式传输才是正解？我没想到这东西这么占内存。但也可以不存内存，存在磁盘里直接读取。"*

这个疑问是**对的**，但**占内存的元凶不是我以为的那个**。

---

## 2. 实测：内存主战场是 DTW 代价矩阵，不是频谱

脚本 `harmonica_mvp_dataset/spike_dtw_memory.py`（librosa 0.11，真实跑 DTW）

| 时长 | 对齐 hop | 帧数 N | 代价矩阵 D | warp path | DTW 耗时 |
| --- | --- | --- | --- | --- | --- |
| 120 s | 512 | 10 336 | **855 MB** | 165 KB | 2.99 s |
| 120 s | 512 + Sakoe-Chiba 0.25 | 10 336 | **855 MB** | 165 KB | 2.15 s |
| **120 s** | **2048** | 2 584 | **53 MB** | 41 KB | 0.09 s |
| 180 s | 512 | 15 504 | **1 923 MB** | 248 KB | 3.75 s |

### 2.1 关键发现

**（a）`D` 是 float64，不是 float32 ⇒ 比调研预测翻倍。**
`np.float64`，10 336² × 8 B = 854.7 MB。调研按 float32 推算为 427 MB，实际 855 MB。

**（b）Sakoe-Chiba 带约束不减少 `D` 的分配。**
带约束后 `D` 仍是 855 MB（比值 1.00），仅路径被约束、耗时才降。
→ **实现陷阱**：以为加了带宽就省内存，是错的。

**（c）hop 放宽 4× ⇒ `D` 降 16×（平方反比）。**
855 MB → 53 MB，实测降 **16.0×**。

**（d）真正必须全局物化的只有 warp path。**
165 KB，相对代价矩阵是 **1/5300**。

### 2.2 与频谱的对比（120 s，SPEC 上限）

```text
DTW  hop=512   →  855 MB   ← 真正的主战场（我原先完全没算）
DTW  hop=2048  →   53 MB   ← 只改一个参数
STFT 一档双信号 →   85 MB   ← 我原先以为的主战场
PCM ×3         →   64 MB
warp path      →  0.165 MB  ← 真正要存的
```

> **结论**：内存预算的**唯一大杠杆是对齐分辨率**。
> 削减频谱档数是无效努力（那是 85 MB 级），而调 hop 是 855 → 53 MB 级。

---

## 3. 调研结论（含出处）

### 3.1 流式 ≠ 惰性+缓存（三个概念）

- **流式**：固定块迭代，状态有界。[librosa.stream](https://librosa.org/doc/latest/api/generated/librosa.stream.html)：*"Stream audio in fixed-length buffers… returns a generator"*
- **惰性**：建表达式图，取值时才算（Dask/xarray）。仍需描述整份数据。
- **缓存**：算完存起来。[librosa 缓存](https://librosa.org/doc/latest/cache.html)默认**关闭**，基于 `joblib.Memory`，官方明写 *"The cache does not implement any eviction policy. As such, it can grow without bound on disk if not purged."*

### 3.2 流式在"先对齐再比较"流程里只**部分**可行

[librosa.stream](https://librosa.org/doc/latest/api/generated/librosa.stream.html) 官方 caveat 3 原文：

> *"Many analyses require access to the entire signal to behave correctly, such as `resample`, `cqt`, or `beat_track`, so these methods will not be appropriate for streamed data."*

| 可流式（逐块，`center=False`） | 必须全局 |
| --- | --- |
| STFT / Mel / CQT（算完即用，不落盘） | DTW 累积代价矩阵 |
| RMS 能量包络 | **warp path**（核心产物） |
| 逐块重采样 + 逐块对比 | 全曲归一化统计量 |
| 逐音局部指标（若已有全局 warp 作锚） | beat / tempo tracking |

### 3.3 存储选型：只读 memmap

| 路线 | 手机端 | 判断 |
| --- | --- | --- |
| **`numpy.memmap`** | ✅ POSIX 原生 | **采用** |
| HDF5 / h5py | ⚠️ 仅第三方 HDF5Kit / 自编 JNI；SWMR 单写多读且耦合 v110 格式 | 否 |
| Zarr | ❌ [官方实现列表](https://zarr.dev/implementations/)无 Swift/ObjC/Kotlin | 否 |
| Arrow / Parquet | ⚠️ 表格模型，不适配稠密时频数组 | 否 |
| LMDB / SQLite | ⚠️ 无 ndarray 切片语义 | 否 |

`mode='r'` 只读映射的额外好处（iOS）：clean page 在内存压力下可被系统直接回收，
不占 jetsam 预算（[Apple jetsam 文档](https://developer.apple.com/documentation/xcode/identifying-high-memory-use-with-jetsam-event-reports)）。

### 3.4 MIR 界确实"现算特征、不建大特征库"

- [librosa.stft](https://librosa.org/doc/latest/api/generated/librosa.stft.html) 返回**完整数组**，无 lazy 返回；唯一内存手段是 `out=` 预分配
- [librosa.feature.melspectrogram](https://librosa.org/doc/latest/api/generated/librosa.feature.melspectrogram.html) 同样返回完整数组
- Essentia 标准模式整份加载（[streaming_extractor_music.cpp](https://github.com/MTG/essentia/blob/master/src/examples/streaming_extractor_music.cpp)）；流式是独立的 token 网络
- madmom *"Some programs can also be run in online mode"*（[usage](https://madmom.readthedocs.io/en/latest/usage.html)）

---

## 4. 调研对我 4 条前提的修正（逐条裁定）

| # | 我原来的前提 | 裁定 | 依据 |
| --- | --- | --- | --- |
| 1 | "必须预计算才能快" | **成立，已自我修正** | 实测 65 ms 现算 vs 127 MB 预存 |
| 2 | "PCM 三份是必须的通用底座" | **部分接受** | 归一化 PCM 可由「练习 PCM + warp path」确定性重建。**但契约仍承诺"永远能拿到 aligned PCM"**——见 §5 |
| 3 | "数据面冻结的应是定义而非字节" | **接受，已是我的方向** | 与实测一致 |
| 4 | 漏算 DTW 代价矩阵 | **完全接受，且比预测更糟** | 实测 float64 ⇒ 855 MB（预测 427 MB） |

### 4.1 关于第 2 条的重要保留

调研建议"不物化对齐后 PCM"。我**接受其实现层面**，但**不接受其契约层面**：

宪章 §11 的逃生口要求"算法永远能拿 PCM 自行预处理"。这个**保证必须保留**，
否则算法作者无法确定自己能否做特有预处理，深组件会退化成"猜哪些数据存在"。

所以正确的表述是：

> **契约承诺的是「永远可获取」，不是「已经算好」。**
> 是否物化、何时物化、放内存还是 mmap —— 全是实现自由。

这同时满足 §11 与内存约束，且解释了为什么 §5 的 D5 是这个形状。

---

## 5. 关闭 OC1 后的数据面定义

> **⚠ 本节已被否决，见文末 §7。**
> 保留原文以记录判断过程；**当前有效裁定是「Core 预生成、端口清单封闭」**。

### 5.1 契约层（对算法承诺，不可协商）

1. 数据面**自描述**：算法通过 manifest 枚举端口，无需预知清单
2. **aligned PCM 永远可获取**（mapped + warped）—— §11 逃生口
3. 每个端口必须声明 `timeline_basis` / `sample_rate` / `units` / `dimensions`
4. 兼容性检查**单向**：算法声明需要什么只用于判断"有没有"，**绝不反推生成**
5. Seal 后**逻辑不可变**（物理上是否惰性计算，是实现细节）

### 5.2 实现层（L2 自由，但受实测预算约束）

**物化（极小）**

```text
warp_path        int32[N,2]      ~165 KB   ← 真正底座
rms_ref/prac     float32[N]      ~40 KB each
chroma_lowres    float32[12,N]   ~500 KB each (hop=2048)
```

**按需现算 + LRU 缓存（不物化）**

```text
STFT 幅度谱 / Mel / CQT / 复数谱 / 帧库
对齐后 PCM（由 warp_path 从原始 PCM 按需重采样）
```

**强制实现约束**

- 对齐必须用**低分辨率**特征（hop ≥ 2048），且必须开 `global_constraints`
- 分帧用 stride 视图零拷贝（[librosa.util.frame](https://librosa.org/doc/latest/api/generated/librosa.util.frame.html) 的做法）
- 分帧分析统一 `center=False`，与流式语义一致

### 5.3 预算（120 s，SPEC 上限）

| 项 | 规模 |
| --- | --- |
| 常驻物化 | **< 2 MB** |
| DTW 峰值（hop=2048） | 53 MB |
| 按需一档 STFT（双信号） | 85 MB（算完即弃） |
| **峰值内存** | **约 140 MB** |

对比原设计（预存 3 档频谱 + 全物化 PCM + hop=512 对齐）：**约 1.0 GB**。

---

## 6. 依据与可复现性

| 证据 | 文件 |
| --- | --- |
| DTW 内存实测 | `data/out/spike_dtw_memory.json` |
| 端口经济性实测 | `data/out/spike_port_economics.json` |
| Core 构建成本实测 | `data/out/spike_core_memory.json` |
| 脚本（无随机性，固定输入） | `spike_dtw_memory.py` / `spike_port_economics.py` / `spike_core_memory.py` |

### 6.1 已知的测量局限

- RSS 为**进程高水位**，跨用例累积，**不可归因到单个用例**。
  可精确归因的是 `D.nbytes` 与耗时，表中已按此报告。
- 实测在 **Mac** 完成；手机端（iOS jetsam / Android LMK）**未测**。
- 合成 chroma（正弦，确定性）用于测规模；真实音乐的对齐**精度**未在此验证。
- `essentia.upf.edu` 调研时 DNS 失败，Essentia 证据改用 GitHub 一手源码。

---

## 7. ⚠ 重要更正（负责人裁定，本文 §5 被推翻）

**本文 §5 的 D5「契约承诺『可获取』，不承诺『已物化』」——已被负责人否决。**

### 7.1 否决理由（负责人原话要点）

> "你又把那一个 core 变为那一个插件提交需要 core 再生成的一个数据了。
> 实际上在我看来，core 一定是要预生成的，否则就要去准备接口协议。"

### 7.2 我错在哪（自相矛盾）

我一边声称「Core 绝不能知道算法的存在」，一边设计了一个
**Core 要为算法现场算数据**的接口。这两件事不可能同时成立：

|  | 预生成（负责人裁定） | 按需现算（我的 §5） |
| --- | --- | --- |
| 契约性质 | **查表**：有什么读什么 | **协商**：我要什么你得能算 |
| 新增算法 | Core **不动**，算法适配 Core | Core 要能响应新需求 |
| 额外协议 | **无** | 特征声明→解析→版本→缓存失效→失败语义 |
| 端口清单 | **封闭** | 随插件需求增长 |

**要害**：惰性计算要活下来，**必须**定义一套协商协议；
而一旦有了那套协议，Core 的外部接口就成了**插件需求的函数**——
**这正是我声称要避免的反模式。**

### 7.3 更正后的裁定

> **Core 预生成。端口清单封闭。算法适配 Core，不是 Core 适配算法。**
> 算法若需要额外的东西，**从数据面里的 PCM 自己算**，
> **不许反过来要求 Core 提供**。

### 7.4 一个矛盾因此消失

§2 实测说「预存频谱不划算」（127 MB 换 65 ms）。
在**预生成**前提下这不构成矛盾，因为 v0.1 **根本不需要存频谱**：

口琴对比真正要的是**音高曲线、能量包络、chroma**——各几百 KB，预生成毫无压力。

所以：**只预生成「真的要用」的特征（封闭清单），而不是一个投机的频谱仓库。**
预生成与体积小**同时满足**。

### 7.5 §2 实测结论仍然有效，但降级为「参数选择」

DTW 代价矩阵实测（855 MB @ hop=512 → 53 MB @ hop=2048）
**依然有效**，但它现在的用途只有一个：**选定对齐分辨率这一个参数**。
它不再参与架构决策（不再需要 memmap / LRU / 存储后端选型）。

### 7.6 另一个被否决的前提：手机内存约束

负责人早已裁定 **Mac 先行 → 核心调完 → 再移植手机**。
故"内存硬约束"**在原型阶段不成立**。§3、§5 中所有为手机端做的妥协
（memmap、无压缩、jetsam 分析）**本轮全部不采用**。

记录保留，作为**将来移植时**的参考，不作为现在的架构依据。
