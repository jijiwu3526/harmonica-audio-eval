# 口琴演奏分析：公开研究、数据集与工具生态调研

> **性质声明**：本文为**客观事实调研**，只报告可以给出 URL 的检索结果，
> **不构成技术路线决策，也不推荐任何技术路线**。技术路线由项目负责人确定。
> 项目边界与已定决策以 **`../SPEC.md`**（唯一权威规格）为准；本文若与其冲突，以 SPEC.md 为准。
> 边界提示（SPEC.md §1、§2）：本项目**只做「双音频对比 → 客观数值指标」**；
> **自然语言反馈 / Agent 生成、AI 审美评价、模型训练、UI 均明确不在本项目范围内**。
> 因此本文第 3 节中关于"教练式反馈"的调研，属于**生态客观事实记录**，
> 不代表其属于本项目边界。
>
> 调研日期：**2026-09-23**（所有 star 数、更新时间均为该日快照）。
> 检索手段：web_search / web_fetch、Crossref API、OpenAlex API、GitHub REST API、
> Zenodo API、PyPI / npm registry，以及**实际 clone / 下载仓库源码与 README 逐行核对**。
>
> **证据分级约定**：
> - ✅ **我确认存在**——有可直接访问的 URL，且关键结论来自一手来源（论文元数据 / 仓库源码 / README）。
> - ⚠️ **找到相似但不完全匹配**——存在相关对象，但不满足问题原本的限定（如"口琴专用"）。
> - ❌ **我未找到（可能不存在）**——多轮多关键词检索无公开证据。**这本身是结论**。
>
> **置信度**：高 = 一手来源直接证实；中 = 一手来源间接证实或元数据一致但未读全文；低 = 仅单条线索、无法交叉验证。

---

## 0. 一句话结论

口琴在 MIR 学术文献中是一个**极度冷门**的对象：存在**自动转录**（把音频转成音符）层面的
论文与数据集，也存在**物理声学**（簧片、压音机理）层面的文献，但
**没有找到"口琴演奏质量评价 / 演奏评分"这一命题的专门学术论文**。
工程侧则相反——存在 1 个活跃度很高的口琴专用开源项目（Harmonicon），
它围绕**曲谱对齐**实现了分段评分与教练式反馈，但**不做与原曲音频的对比**。

---

## 1. 问题一：是否存在口琴专用的演奏评价 / 演奏质量分析学术论文？

### 1.1 结论

| 类别 | 结论 |
| --- | --- |
| 口琴**演奏质量评价 / 评分** | ❌ **我未找到**专门论文。置信度：**中**（多库检索均无命中，但不能排除非英文/未索引文献） |
| 口琴**自动转录（AMT）** | ✅ **我确认存在**，且是该领域唯一的代表性工作 |
| 口琴**物理声学 / 压音机理** | ✅ **我确认存在**（与"演奏评价"目标不同） |

### 1.2 确认存在的论文

#### (A) 口琴自动转录（最接近"口琴音频结构化分析"的学术工作）

✅ **我确认存在**

- **标题**：*Automatic Transcription of Diatonic Harmonica Recordings*
- **作者**：Filipe Lins, Marcelo Johann, Emmanouil Benetos, Rodrigo Schramm
- **发表**：ICASSP 2019（IEEE 国际声学、语音与信号处理会议），页码 256–260
- **DOI**：[10.1109/icassp.2019.8682334](https://doi.org/10.1109/icassp.2019.8682334)
- **IEEE Xplore**：<https://ieeexplore.ieee.org/document/8682334>
- **作者预印本（QMUL 开放获取）**：<https://qmro.qmul.ac.uk/xmlui/bitstream/handle/123456789/56489/Benetos%20Automatic%20Transcription%20of%20Diatonic%202019%20Accepted.pdf?sequence=2>
- **官方代码仓库**：<https://github.com/filipemlins/Automatic-Music-Transcription-Harmonica>
- **置信度：高**（Crossref 元数据、OpenAlex 摘要、GitHub 仓库三方一致）

**论文实际做了什么**（摘录自 OpenAlex 收录的官方摘要，并经仓库源码核对）：

> "It estimates the multi-pitch activations through a spectrogram factorisation framework.
> This framework is based on **Probabilistic Latent Component Analysis (PLCA)** and uses a
> fixed 4-dimensional dictionary with spectral templates extracted from Harmonica's instrument
> timbre. … we propose a set of **harmonic constraints that are inherent to the Harmonica
> instrument note layout** or are caused by specific diatonic Harmonica playing techniques.
> … This work also builds a **new audio dataset** containing solo recordings of diatonic
> Harmonica excerpts and the respective multi-pitch annotations. … report the results based on
> **frame-based F-measure** statistics."

要点（对本项目重要）：

1. 它解决的是**多音（多簧同时发声）激活估计**，即和弦/双音场景的转录；
2. 它明确利用了口琴的**乐器布局先验**（哪些音能同时出现）作为约束——这是"口琴专用"的真正体现；
3. 它的评价指标是**转录准确率（frame-based F-measure）**，**不是**演奏质量。

#### (B) 口琴物理声学 / 压音机理（不是"演奏评价"，但涉及 bend/vibrato 的物理）

✅ **我确认存在**。这些文献解释压音**为什么发生**，不测量演奏好坏。按 Crossref 检索结果列出：

| 标题 | 作者 | 出处 | DOI |
| --- | --- | --- | --- |
| Acoustical and physical dynamics of the diatonic harmonica | — | JASA, 1998 | [10.1121/1.421359](https://doi.org/10.1121/1.421359) |
| Pitch bending in the diatonic harmonica | James P. Cottingham | JASA, 2012 | [10.1121/1.4755348](https://doi.org/10.1121/1.4755348) |
| Real-time magnetic resonance imaging of the upper airways during harmonica pitch bends | — | Proceedings of Meetings on Acoustics, 2013 | [10.1121/1.4799443](https://doi.org/10.1121/1.4799443) |
| The harmonica as a blues instrument (Part I / II) | — | JASA / POMA, 2012–2014 | [10.1121/1.4755350](https://doi.org/10.1121/1.4755350) |
| Interactions of both reeds in a channel of diatonic harmonica | Millot, Cuesta, Valette | ISMA 1997 | [10.25144/15148](https://doi.org/10.25144/15148) |
| Time-domain simulation of harmonica pitch bending | — | JASA, 2025 | [10.1121/10.0041240](https://doi.org/10.1121/10.0041240) |
| Time-domain simulation of harmonica pitch bending and overblowing | — | JASA, 2026 | [10.1121/10.0043784](https://doi.org/10.1121/10.0043784) |
| Fluid dynamic harmonica bending model | — | JASA, 2025 | [10.1121/10.0038291](https://doi.org/10.1121/10.0038291) |

**置信度：高**（Crossref 逐条返回元数据）。
**注意**：多数为会议摘要（conference-abstract），其价值在于**压音的物理参数范围**可作为特征设计的先验，
但**不提供任何演奏评分方法**。

### 1.3 找到相似但不完全匹配的工作

⚠️ **不是口琴，但命题高度相似**——这两项说明"管/簧类乐器的自动演奏评价"在学术上是成立的：

| 标题 | 乐器 | 出处 | DOI / URL |
| --- | --- | --- | --- |
| A Multimodal Learning System for Automated Assessment of Accordion Playing Techniques | **手风琴** | Proc. 3rd Int'l Conf. on Machine Intelligence and Digital Applications, 2026-04-24 | [10.1145/3801438.3804854](https://doi.org/10.1145/3801438.3804854) |
| Self-supervised multimodal transformer for fine-grained detection of controlled perturbation events in piano performance | 钢琴 | Scientific Reports, 2026-06-08 | [10.1038/s41598-026-45945-9](https://doi.org/10.1038/s41598-026-45945-9) |
| An Overview of Automatic Piano Performance Assessment within the Music Education Context | 钢琴（综述） | ICAART 2022 | [10.5220/0011137600003182](https://doi.org/10.5220/0011137600003182) |

- 手风琴与口琴同为**自由簧（free-reed）**乐器，该论文的"多模态自动评估"是最接近的类比对象。
  **置信度：中**（Crossref 确认标题/作者/出处存在，但摘要未开放，未读到方法细节，**不能据标题推断其具体能力**）。
- 钢琴演奏评估的综述说明"自动演奏评估"是一个成熟子领域，但**对象是钢琴，不是口琴**。置信度：高。

### 1.4 我未找到的东西（明确记录）

❌ **未找到**（以下关键词已多轮检索 Crossref / OpenAlex / web_search，无命中）：

- `harmonica performance evaluation`
- `harmonica performance assessment` / `harmonica automatic assessment`
- `harmonica intonation analysis`
- `harmonica vibrato analysis`（**检索到的 vibrato 文献均非口琴**，例如人声 vibrato、query-by-humming）
- `口琴 演奏 分析` / `口琴 自动 评分`（中文检索同样无命中）

**置信度：中**。理由：OpenAlex 对 `harmonica performance evaluation` 返回 2084 条，
但前排全部是噪声（如"Boston Naming Test performance"里的 harmonica 误匹配、
"harmonica tube"热交换器、"Harmonica Index"噪声评价指标——后者是**环境噪声**指标，
名字虽同但完全无关）。用 `title.search:harmonica` 精确过滤后，**418 条标题命中里没有一条是演奏评价**。

> **本条即结论**：就公开英文/中文学术索引而言，**"口琴专用演奏评价论文"这一项不存在公开证据**。

---

## 2. 问题二：是否存在口琴音频的公开数据集？

### 2.1 结论

✅ **我确认存在 1 个真正可用的口琴多音标注数据集**（来自 1.2(A) 的论文），
**放在论文官方 GitHub 仓库源码树内**，无需额外申请。
除此之外，**没有找到**独立的、以"口琴"为主题的公开 MIR 数据集。

### 2.2 确认存在的数据集

✅ **我确认存在**

- **名称**：论文未给数据集起独立专名，仓库中目录为 `Annotaded/`、`AnnotatedSetupFinalHz/`、
  `AnnotatedSetupFinalMidi/`、`datasets/`（原文拼写即 `Annotaded`）
- **位置**：<https://github.com/filipemlins/Automatic-Music-Transcription-Harmonica>
- **内容**（**我实际遍历仓库 git tree 统计，非估计**）：
  - `.wav` 文件 **337 个**，合计 **1,156,464,954 字节 ≈ 1.08 GiB**
  - `.mid` 文件 **265 个**
  - `*Hz.txt` 音高标注文件 **87 个**
  - `Annotaded/` 下按口琴调性分三组：`Harmonica_em_Bb`(13 wav) / `Harmonica_em_C`(17 wav) / `Harmonica_em_G`(14 wav)
  - 另有 `AnnotatedSetupFinalHz/`(179 条目)、`AnnotatedSetupFinalMidi/`(179 条目) 与 `datasets/` 目录
  - 多数 wav 为 3,189,440 字节或 3,723,392 字节——若为 44.1 kHz/16-bit 单声道，约合 36–42 秒/条
- **标注形式**：`multi-pitch annotations`（多音标注），以 `.mid` + `*Hz.txt`（频率序列）形式提供
- **许可**：⚠️ **仓库无 LICENSE 文件**（GitHub API `license = None`）
- **置信度：高**（数据集存在、规模、路径均为我实际调用 GitHub Trees API 统计所得）

⚠️ **重要限制（客观事实）**：

1. **无许可证** = 法律上不可直接复用/再分发，需联系作者确认。
2. **标注是"音符/音高"级别的转录标注，不是"演奏质量/评分"标注**。它无法直接用于训练或验证
   "什么算好的演奏"。
3. 仓库自 **2020-04-14** 后无推送（`pushed_at = 2020-04-14T22:10:40Z`），
   star 数 **6**，**非活跃**。

### 2.3 找到相似但不完全匹配

⚠️ 以下含口琴素材，但**不是**以"口琴演奏分析"为目标的专用数据集：

| 名称 | 与口琴的关系 | 结论 | 来源 |
| --- | --- | --- | --- |
| NSynth / VCSL 等通用采样库 | 可能含少量口琴单音采样 | 用于**合成**，非真实演奏 | — |
| IRMAS（乐器识别数据集） | 传统上**不含** harmonica 类 | ❌ 无法确认含口琴 | <https://github.com/tuwien-musicir/IRMAS> |
| Audio Dataset of Traditional Portuguese Musical Instruments | 标题为传统乐器 | 未见口琴 | <https://data.mendeley.com/datasets/yjdfnymgf2/1> |
| `wood harmonica`（Zenodo） | **实为 3D 模型**（Objaverse/Sketchfab 的 .glb），非音频 | ❌ 不适用 | [10.5281/zenodo.10228073](https://doi.org/10.5281/zenodo.10228073) |

### 2.4 我未找到的东西（明确记录）

❌ **未找到**：

- **HuggingFace Datasets 上不存在** search=`harmonica` 的数据集
  （`https://huggingface.co/api/datasets?search=harmonica` 返回空列表）。
  置信度：**中**（API 返回空，且对 `harp`、`blues harp` 同样为空）。
- **Zenodo 上不存在口琴演奏音频数据集**。`q=harmonica` 共 115 条命中，
  逐条检查资源类型为 `dataset` 的仅 2 条：`wood harmonica`（3D 模型）与
  `1892 Campaign Harmonica`（历史物件，非音频）。
  置信度：**中**。
- **不存在口琴专用的"演奏质量/评分"标注数据集**。
  置信度：**中**（此为 1.4 与 2.4 的推论：连评价论文都不存在，其标注数据集亦无公开证据）。

> **本条的客观含义**：现有唯一的公开口琴数据集服务于**转录**任务，
> 其标注粒度（音高/音符）与"演奏质量评价"所需的标注粒度**不匹配**。

---

## 3. 问题三：Harmonica 相关开源项目实际支持哪些能力？

### 3.1 Harmonicon

- **仓库**：<https://github.com/tcanabrava/harmonicon>
- **我实际使用的核实方式**：下载 `main` 分支 tarball（43.8 MB）并**解压后直接阅读 Rust 源码与文档**

| 项目 | 实测值（2026-09-23 快照） |
| --- | --- |
| Star | **43** |
| Fork | 13 |
| 最后推送 | **2026-09-22T11:05:44Z**（即调研前一日，**极活跃**） |
| 最新 release | `v0.0.11`（2026-09-08） |
| 语言 / 技术栈 | **Rust**（≈3.56 MB，主体）+ Fluent + Python + Shell；引擎 **Bevy 0.19**；音频采集用 `cpal` |
| 许可 | **MIT** |
| 形态 | 桌面游戏（2D/3D），含 Web(WASM)/Android 打包路径 |
| 版本状态 | 自述 **early/experimental `0.1.0`**（README）；实测 release 仍在 `0.0.x` |

README 自述（原文）：

> "A rhythm game for **blues harmonica** (diatonic and chromatic), built in Rust with the Bevy engine.
> Notes scroll toward a hit line and you play them on a **real harmonica** — Harmonicon listens to
> your microphone, detects the pitches you're playing in real time, and **scores you on timing**."

#### 对提问的 (a)(b)(c) 逐项核实

| 能力 | 结论 | 证据 |
| --- | --- | --- |
| **(a) 与原曲 / 参考音频对比** | ❌ **不支持** | 见下 |
| **(b) 分段评分** | ⚠️ **部分支持**（按**乐句 phrase** 分段，但**非逐段分数**） | 见下 |
| **(c) 错误反馈** | ✅ **支持**（教练式文本 + 定位到具体段落） | 见下 |

##### (a) 与原曲 / 参考音频对比 —— ❌ 不支持

**我实际检查的结果**：

- 全仓库 grep `reference_audio` / `original recording` / `compare.*recording` / `time_align` / `dtw`
  在 Rust 源码与文档中**无任何命中**（仅命中 UI 布局的 `align_items`，非音频对齐）。
- 参考物是 **`ScheduledNote` 的期望音高序列**（chart），来自 MIDI / Guitar Pro / MuseScore / MusicXML，
  **不是参考音频**。见 `crates/harmonicon-gameplay/src/gameplay/notes.rs`：
  ```rust
  pub struct ScheduledNote {
      pub time: f64,
      pub duration: f64,
      pub hole: u8,
      pub is_blow: bool,
      /// The MIDI note number this note expects, pre-computed at spawn
      pub expected_pitch: Option<u8>,
      ...
  }
  ```
- 核心判分函数 `crates/harmonicon-core/src/scoring.rs::classify_note` 的签名是
  `offset`（时间差）+ `playing_expected`（布尔）→ 纯**音符级离散比对**：
  ```rust
  pub const fn classify_note(
      offset: f64,
      playing_expected: bool,
      perfect_window: f64,
      good_window: f64,
      miss_window: f64,
  ) -> NoteOutcome
  ```
- 对比逻辑注释明确：`"Every place scoring needs to compare 'what pitch is the player playing'
  against 'what pitch does the chart expect,' both sides are a MIDI note number (u8)"`
  （`contributing/src/scoring-system.md`）——**对比对象是整数 MIDI 号，不是音频**。
- 仓库确有音频文件引用（`backing_stems`、`music.ogg`、`MusicPlayer`），但用途是
  **播放伴奏**，不是**作为对齐/评分的参考信号**。

**置信度：高**（源码级证据 + 无命中反证）。

##### (b) 分段评分 —— ⚠️ 部分支持

**支持的部分**：

- 有完整的**乐句分段（phrase section）**概念，源码 `crates/harmonicon-gameplay/src/gameplay/notes.rs:76`：
  ```rust
  /// Index into `adaptive_difficulty::AdaptiveDifficulty::sections` — the
  /// musical phrase this note belongs to.
  pub phrase_section: usize,
  ```
- 有 `group_phrase_sections()`（`adaptive_difficulty.rs:43`）与"已掌握乐句"追踪
  （`bump_learned_sections`、`learned_vec_from_map`）。
- 结果页会**定位**到最密集的失误段落（`crates/harmonicon-gameplay/src/gameplay/results.rs`）：
  ```rust
  /// Bars of the song "Practice missed section" loops around the densest cluster of misses.
  const PRACTICE_WINDOW_BARS: f64 = 2.0;
  ```
  并据此生成 `PracticeRange { start_time, end_time }` 供循环重练。

**不支持的部分**：

- **没有"逐段分数"**。全局分数是单一聚合值：
  ```rust
  pub fn accuracy(stats: &SongStats) -> f32 {
      let weighted = stats.perfect as f32 + stats.good as f32 * 0.7 + stats.delayed as f32 * 0.45;
      weighted / total as f32
  }
  ```
  以及 `grade()` → `"A+" | "A" | "B" | "C" | "D" | "F"`（仅整曲一个等级）。
- 乐句分段的用途是**自适应难度解锁**与**重练定位**，**不是产出 per-segment 评分**。

**置信度：高**（读到了结构定义与评分函数本体）。

##### (c) 错误反馈 —— ✅ 支持，且实现完整

存在专门的 `crates/harmonicon-gameplay/src/gameplay/coaching.rs`（570 行），
以及结果页 `results.rs`（其文件头自述 *"Post-song results screen, read as **coaching**"*）。

**反馈维度**（`coaching.rs:73` 的 `Observation` 枚举，原文注释）：

```rust
pub enum Observation {
    /// One technique lags well behind plain notes.
    Technique { technique: &'static str, hits: u32, total: u32 },
    /// Too many notes never scored at all.
    MissedNotes { misses: u32, total: u32 },
    /// Hits lean late (`late == true`) or early: `share` of them fell on that
    /// side, well outside the on-time band.
    Timing { late: bool, share: f32 },
    /// The right note landed, but with another hole leaking alongside it.
    LeakyAttacks { clean: u32, total: u32 },
    Solid,
}
```

即反馈覆盖 **技术类型维度（bend / vibrato / wah-wah / overblow / overdraw / slide）、
漏音数、过早/过晚倾向、起音漏气（相邻孔串音）、以及"没问题"**。

还有**定位到段落的空间反馈**——`coaching.rs:226` `missed_range()` 找出失误最密集的窗口：

```rust
/// ... window_secs ... finds the densest cluster of misses
pub fn missed_range(misses: &[(f64, f64)], window_secs: f64, lead_in_secs: f64) -> Option<(f64, f64)>
```

以及**按技术类型排序、指出最该练什么**（`ranked_techniques()`，按 miss 数降序、
再按 accuracy 升序）。

**置信度：高**（函数本体、枚举、注释均已读取）。

##### 附带确认：bend / vibrato 检测的真实实现程度

这一点对问题四很关键，且**证据比 README 宣传更强**：

- **vibrato 是真测量，不是只看谱面声明**。`crates/harmonicon-core/src/scoring.rs:172`：
  ```rust
  /// Consecutive reversals are half a cycle apart; average them then double
  /// the period to get a full-cycle rate.
  pub fn measured_oscillation_hz(samples: &[(f64, f32)], min_swing: f32) -> Option<f32>
  ```
  阈值常量 `VIBRATO_MIN_SWING_CENTS: f32 = 15.0`、`WAH_MIN_SWING_FRAC: f32 = 0.12`，
  并有容差判定 `oscillation_matches_rate(measured_hz, target_hz, tolerance_frac)`，
  注释说明容差 `0.4` = ±40%，理由为"hand vibrato/wah speed varies naturally"。
- **bend 被当作离散的半音偏移**，而非连续曲线。`notes.rs:246` 注释原文：
  > "The MIDI note the player must actually produce for a note. A `bend` … (the pitch is
  > continuous, but the matched target is discrete), so the bend is [rounded]"
  ```rust
  Modifier::Bend { semitones, .. } => Some(semitones.round() as i32),
  let midi = note_to_midi(natural)? + bend;
  ```
- **五个音高检测算法可选**，`crates/harmonicon-dsp/src/lib.rs:82`：
  `Fft`（默认，多音）、`Yin`、`Pyin`、`Mcleod`(MPM)、`Nmf`（多音模板 NMF）。
  代码注释给出**实测结论**：`pYIN and MPM resolve D4+G4 as a phantom F4, a pitch nobody played`——
  即单音算法遇和弦会报出**不存在的音**。
- **有离线评测工具**：`crates/harmonicon-bench/src/note_bench.rs` 与 `synthetic_dataset.rs`。
- **作者公开表示需要真实录音语料**：`docs/pitch_detection_plan.md` 设有
  "**Ready for recordings**" 一节，列出需要录制/标注的场景
  （单音、bend、overblow/overdraw、相邻孔和弦、八度、舌堵、吹吸切换、纯气息、房间噪声，
  并覆盖不同音量、麦克风距离、至少两支麦克风）——**说明该项目自身也尚未完成该语料的建设**。

**置信度：高**。

#### Harmonicon 的客观定位

⚠️ 它是**节奏游戏（rhythm game）**，不是演奏评价/教学分析系统。
它的评分主体是**时序命中（timing）**，音高只用于"是否弹对了那个音"的二值门控；
它**没有**音准偏差（cents）、力度、音色等维度的评分。

---

### 3.2 其它 Harmonica / 口琴开源项目

我在 GitHub 用 `harmonica+pitch`、`harmonica+bend+tuner`、`q=harmonica sort:stars` 等
多组查询做过穷举式检索（`harmonica+pitch` 全站仅 **13** 个结果）。

| 项目 | 定位 | Star | 语言 | 最后推送 | 许可 | (a) 原曲对比 | (b) 分段评分 | (c) 错误反馈 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [tcanabrava/harmonicon](https://github.com/tcanabrava/harmonicon) | 口琴节奏游戏（真实口琴输入） | 43 | Rust | 2026-09-22 | MIT | ❌ | ⚠️ 部分 | ✅ |
| [egdels/bluesharpbendingapp](https://github.com/egdels/bluesharpbendingapp) | 压音练习 + 实时音高反馈 | 26 | Java | 2026-07-26 | MIT | ❌ | ❌ | ⚠️ 可视化 |
| [filipemlins/Automatic-Music-Transcription-Harmonica](https://github.com/filipemlins/Automatic-Music-Transcription-Harmonica) | 论文代码（口琴自动转录） | 6 | MATLAB | **2020-04-14** | ❌ 无 | ❌ | ❌ | ❌ |
| [sirmbcode/harmonicanalyzer](https://github.com/sirmbcode/harmonicanalyzer) | JUCE+LEAF 实时音高插件 | 2 | C | 2025-06-20 | — | ❌ | ❌ | ❌ |
| [kumarvmcshubham/harmonicaguru](https://github.com/kumarvmcshubham/harmonicaguru) | PWA 口琴训练（宣称 AI 反馈） | 0 | JS | 2026-05-08 | — | ❌ | ❌ | ⚠️ 未核实 |
| [aiandylatam/harmonica-trainer](https://github.com/aiandylatam/harmonica-trainer) | 半音阶口琴练习工具 | 0 | HTML | 2026-05-10 | — | ❌ | ❌ | ❌ |
| [aiandylatam/bluesharp-trainer](https://github.com/aiandylatam/bluesharp-trainer) | 全音阶口琴练习工具 | 0 | HTML | 2026-06-14 | — | ❌ | ❌ | ❌ |
| [Roger00/bluesharp](https://github.com/Roger00/bluesharp) | 口琴/人声音高追踪 | 0 | Java | **2016-10-31** | — | ❌ | ❌ | ❌ |
| [georgethebeatle/bend-go-meter](https://github.com/georgethebeatle/bend-go-meter) | 全音阶口琴调音器 | 2 | Go | **2016-10-09** | — | ❌ | ❌ | ❌ |

**置信度：高**（star / 日期 / 语言均来自 GitHub API；行为能力判断来自 README/源码，
未逐行核对的项目已标注"未核实"）。

#### 3.3 `bluesharpbendingapp`（"Let's Bend"）细节 —— 我实际 clone 核对了源码

- **仓库**：<https://github.com/egdels/bluesharpbendingapp>；官网 <https://letsbend.de>
- **Star 26 / Fork 3 / MIT / Java(1.6 MB) / 最后推送 2026-07-26**
- **技术栈**：Java 17+ + Gradle；桌面端 JavaFX + `javax.sound.sampled`；Android 端 `MediaRecorder`；
  WebApp 为 Spring Boot + 原生 JS；**另有独立 npm 包**
  [`bluesharp-pitch-detection`](https://www.npmjs.com/package/bluesharp-pitch-detection)
  （MIT，最新 **3.5.0**，发布于 2025-08-29，共 4 个版本）——**这是 3.4 节少数可直接复用的口琴向产物**。
- **实际能力**（clone 后核对）：
  - 目录 `base/src/main/java/.../utils/` 下有自研 `YINPitchDetector.java`、`MPMPitchDetector.java`、
    `FFTDetector.java`、`HybridPitchDetector.java`、`ChordDetector.java`
  - `controller/NoteContainer.java` 有 **cents 偏差**计算（`calculates the deviation in cents`）
  - `model/harmonica/Harmonica.java` 暴露 `getBlowBendingTonesCount(channel)` /
    `getDrawBendingTonesCount(channel)`——**压音按"能压到哪些音"建模，而非检测压音过程**
  - 有 `model/training/{MajorScaleTraining, BluesScaleTraining, MajorPentatonicScaleTraining,
    MajorChordArpeggioTraining}.java`——**音阶/琶音跟练**
  - **实时、不落盘**：README 明确 "Microphone data is not persisted; instead, the following is
    computed in real-time: Frequency, Volume."
- **对 (a)(b)(c) 的判断**：
  - (a) ❌ 无任何"与原曲音频对比"逻辑；grep `reference` 命中的全是**参考音高/concert pitch (A=440)**，
    不是参考**录音**
  - (b) ❌ 无分段评分；`Training` 接口只暴露 `getNotes()/getActualNote()/getPreviousNote()` 等状态推进
  - (c) ⚠️ 有**实时可视化反馈**（把实际音高相对目标画出来），但**不是事后文字/错误归因反馈**

**置信度：高**（源码目录结构与关键类已逐一读取）。

### 3.4 关于名字里带 "Harmonica" 的其它项目（**同名陷阱，必须排除**）

⚠️ 检索 "Harmonicon" / "Harmonica" 时会大量命中**与口琴无关**的同名项目。
为避免误判，明确列出已排除项（**均与口琴音频无关**）：

| 名称 | 实际是什么 | 来源 |
| --- | --- | --- |
| `charmbracelet/harmonica`（1615★） | Go 物理动画库 | <https://github.com/charmbracelet/harmonica> |
| `fatiando/harmonica`（306★） | 地球物理重磁数据正演/反演 | <https://github.com/fatiando/harmonica> |
| `KenjiOhtsuka/harmonica`（131★） | Kotlin 数据库迁移工具 | <https://github.com/KenjiOhtsuka/harmonica> |
| `callowbird/Harmonica`（177★） | 超参数优化论文代码 | <https://github.com/callowbird/Harmonica> |
| **arXiv 2609.04640 "Harmonica"** | ⚠️ **乐器无关**的音乐转录模型家族（multi-depth harmonic convolution），**名字叫 Harmonica 但与口琴无关** | [arXiv:2609.04640](https://arxiv.org/abs/2609.04640) |

> ⚠️ **arXiv "Harmonica" 是最容易误判的一项**：我通过 arXiv API 核对了其标题与摘要，
> 原文为 *"a family of **instrument-agnostic** music transcription models"*，
> 作者 Longshen Ou 等，提交于 2026-09-04。**它不是口琴专用模型**。
> 置信度：**高**。

---

## 4. 问题四：是否有成熟、可直接使用的口琴 pitch / bend / vibrato 检测代码或工具？

### 4.1 结论

| 需求 | 结论 |
| --- | --- |
| **通用 pitch 提取工具** | ✅ **非常成熟**，多个可直接 `pip install`、许可证宽松 |
| **口琴专用 pitch 检测** | ✅ **存在**（Harmonicon 的 Rust DSP crate；`bluesharp-pitch-detection` npm 包） |
| **bend（压音）检测** | ⚠️ **只有"离散音高级"实现**；**未找到连续的压音轨迹检测专用工具** |
| **vibrato（颤音）检测** | ⚠️ **有可用的次生实现**（Harmonicon 的 `measured_oscillation_hz`）；**未找到口琴专用独立库** |

### 4.2 通用音高提取工具（按可用性排序）

| 工具 | 类型 | 许可 | 最新活动 | 可安装 | 对 bend/vibrato 的适用性 |
| --- | --- | --- | --- | --- | --- |
| [**librosa**](https://github.com/librosa/librosa) `pyin` / `yin` | 传统 DSP，pYIN | **ISC**（宽松） | 2026-09-21（8622★） | `pip install librosa`（**1.0.0**） | ⚠️ 单音；谐振/压音期可能跳变。**本项目已装 0.11.0** |
| [**torchcrepe**](https://github.com/maxrmorrison/torchcrepe) | 神经网络 CREPE | **MIT** | 2025-05-16（524★） | `pip install torchcrepe`（**0.0.24**） | ✅ 连续 f0 曲线，适合音准/vibrato 分析；有 `periodicity` 置信度 |
| [**CREPE**（原版）](https://github.com/marl/crepe) | 神经网络（TF） | **MIT** | 2024-08-19（1415★） | 需 TF | 同上，但 TF 依赖较重 |
| [**basic-pitch**](https://github.com/spotify/basic-pitch) | 神经网络 AMT | **Apache-2.0** | 2025-11-13（5614★） | `pip install basic-pitch`（**0.4.0**） | ✅ README 明确 *"generate a MIDI file, complete with **pitch bends**"*——**唯一明确内建 bend 输出的通用工具** |
| [**aubio**](https://github.com/aubio/aubio) | C 库（yin/mcomb 等） | ⚠️ **GPL-3.0** | 2026-04-10（3757★） | `pip install aubio` | 实时性好；**GPL 传染性需注意** |
| [**Essentia**](https://github.com/MTG/essentia) | 综合 MIR | ⚠️ **AGPL-3.0** | 2026-09-21（3735★） | conda / 源码 | 功能全；**AGPL 传染性需注意** |
| [**Praat / parselmouth**](https://github.com/YannickJadoul/Parselmouth) | 语音学音高/颤动分析 | ⚠️ **GPL-3.0** | 2026-08-21（1290★） | `pip install praat-parselmouth`（0.4.7） | ✅ **语音学领域对 jitter/shimmer/vibrato 的分析最成熟**，含 vibrato 相关测量 |
| [**RMVPE**](https://github.com/Dream-High/RMVPE) | 神经网络 f0（语音/歌声） | **Apache-2.0** | 2024-01-25（332★） | 非正式 PyPI | ⚠️ 面向人声，**未见口琴验证** |

**置信度：高**（star/许可/推送日期均来自 GitHub API；版本号与许可来自 PyPI JSON API）。

**关于 `basic-pitch` 的重要客观事实**：它是本清单中**唯一README 明确声明输出 pitch bend** 的工具，
且许可证（Apache-2.0）对本项目友好；但它是**乐器无关（instrument-agnostic）**模型，
**其 bend 输出在口琴上的准确性无公开验证**。置信度：**高**（就"无公开验证"这一否定结论而言为中）。

**关于 `pyin` 的客观事实**：Harmonicon 代码注释记录了实测现象——
*pYIN 与 MPM 会把 D4+G4 这个双音解析成一个不存在的 F4*。
口琴常有双簧/和弦发声，这与原交接简报（`00-context.md`，**该文件已随目录压缩移除**）
提到的"口琴为单旋律乐器，对音高分析友好"
存在**潜在张力**：单音假设成立与否，取决于演奏法。这是**事实记录，不是路线建议**。

### 4.3 口琴专用实现

| 实现 | 语言 | 许可 | 可用性 | 覆盖能力 | 来源 |
| --- | --- | --- | --- | --- | --- |
| **`harmonicon-dsp`**（Harmonicon 的 crate） | Rust | **MIT** | ⚠️ 未发布到 crates.io（需取源码） | ✅ FFT / YIN / pYIN / MPM / NMF 五种；含口琴**音域约束**与**吹吸方向推断** | `crates/harmonicon-dsp/src/lib.rs` |
| **`measured_oscillation_hz`** | Rust | **MIT** | ⚠️ 同上 | ✅ **vibrato / wah 速率测量**（含最小摆幅阈值 15 cents） | `crates/harmonicon-core/src/scoring.rs:172` |
| **`bluesharp-pitch-detection`** | JavaScript | **MIT** | ✅ **`npm i bluesharp-pitch-detection`**（3.5.0） | YIN / MPM / FFT / Hybrid；Web Audio + AudioWorklet；**明确聚焦口琴** | [npm](https://www.npmjs.com/package/bluesharp-pitch-detection) |
| **论文 PLCA 实现** | MATLAB | ❌ **无许可** | ⚠️ 源码可读，**法律上不可直接复用** | 多音转录（转录，非评价） | [仓库](https://github.com/filipemlins/Automatic-Music-Transcription-Harmonica) |

**置信度：高**。

### 4.4 bend 检测的客观现状（本节是最重要的否定结论之一）

❌ **我未找到**专门做**连续压音轨迹（bend trajectory）检测**的口琴工具或库。

我实际看到的 bend 相关实现，**全部是"把压音当作预先知道的离散音高档位"**：

1. **Harmonicon**：`Modifier::Bend { semitones, .. } => Some(semitones.round() as i32)`
   ——注释自陈 *"the pitch is continuous, but the matched target is discrete"*，
   即它**假设** bend 幅度是谱面给定的，用于校验，**不检测**压音过程。
2. **bluesharpbendingapp**：`getBlowBendingTonesCount(channel)` / `getDrawBendingTonesCount(channel)`
   ——是**口琴物理模型**的查表（这个孔能压出几个音），配合实时 cents 偏差显示；
   **没有** bend 事件检测 API。
3. **Harmonicon 作者博客**（2026-09-07）记录了一处 bug 修复，暴露了这类实现的脆弱点：
   > "My table of how far each hole bends had **every hole capped at a semitone and a half**,
   > which is just wrong. A bend pulls a reed toward the other reed in the same hole … **Three
   > full semitones on hole 3** … **Nothing at all on holes 5 and 7**."
   ——即**压音能力表本身是需要按孔位精确建模的**，这类表容易写错。

**置信度：高**（对"未找到"而言为中：不能排除非英文/未公开的工具）。

⚠️ **找到相似但不完全匹配**：**`basic-pitch`** 输出含 pitch bend 的 MIDI，
可作为连续压音信息的**间接**来源；但它是通用模型，**未见口琴专项评估**。

### 4.5 vibrato 检测的客观现状

❌ **未找到**口琴专用的独立 vibrato 分析库。
⚠️ 但**存在一个可直接阅读/移植的可用实现**：Harmonicon 的 `measured_oscillation_hz`
（MIT 许可），思路是**统计音高序列的"翻转点"、取相邻翻转间隔均值后取倒数×2 得到整周期频率**，
并带有最小摆幅门限（`VIBRATO_MIN_SWING_CENTS = 15.0` cents）与 ±40% 的速率容差。

⚠️ **找到相似但不完全匹配**：语音学工具（Praat / parselmouth，GPL-3.0）对 vibrato /
jitter / shimmer 的测量**在语音领域远比音乐领域成熟**，可借鉴其方法；但**未见于口琴**。

**置信度：高**（就"存在可用实现"而言）；**中**（就"无口琴专用独立库"这一否定结论而言）。

---

## 5. 汇总表格

### 5.1 四个问题的总览

| # | 问题 | 结论 | 置信度 | 关键证据 URL |
| --- | --- | --- | --- | --- |
| 1 | 口琴专用**演奏评价**论文 | ❌ **未找到（可能不存在）** | 中 | 多库检索无命中；[Crossref](https://api.crossref.org/works?query.bibliographic=harmonica+performance+evaluation) / [OpenAlex](https://api.openalex.org/works?filter=title.search:harmonica) |
| 1 | 口琴**自动转录**论文 | ✅ **确认存在** | 高 | [ICASSP 2019, DOI](https://doi.org/10.1109/icassp.2019.8682334) · [预印本](https://qmro.qmul.ac.uk/xmlui/bitstream/handle/123456789/56489/Benetos%20Automatic%20Transcription%20of%20Diatonic%202019%20Accepted.pdf?sequence=2) |
| 1 | 口琴**物理/压音机理**论文 | ✅ **确认存在**（≥8 篇） | 高 | [10.1121/1.4755348](https://doi.org/10.1121/1.4755348) · [10.1121/10.0043784](https://doi.org/10.1121/10.0043784) |
| 1 | 类比的**自由簧乐器评价**（手风琴） | ⚠️ **相似不匹配** | 中 | [10.1145/3801438.3804854](https://doi.org/10.1145/3801438.3804854) |
| 2 | 口琴**公开音频数据集** | ✅ **确认存在 1 个**（转录标注，**无许可**） | 高 | [仓库](https://github.com/filipemlins/Automatic-Music-Transcription-Harmonica)（337 wav ≈ 1.08 GiB） |
| 2 | 口琴**演奏质量标注数据集** | ❌ **未找到** | 中 | HuggingFace / Zenodo 检索均为空 |
| 3 | Harmonicon **原曲音频对比** | ❌ **不支持** | 高 | 源码 [scoring.rs](https://github.com/tcanabrava/harmonicon/blob/main/crates/harmonicon-core/src/scoring.rs) |
| 3 | Harmonicon **分段评分** | ⚠️ **仅乐句定位，无逐段分数** | 高 | `notes.rs:76` `phrase_section`；`results.rs` `PRACTICE_WINDOW_BARS` |
| 3 | Harmonicon **错误反馈** | ✅ **支持**（教练式 + 段落定位） | 高 | `gameplay/coaching.rs`（570 行）`Observation` 枚举 |
| 4 | 通用 pitch 工具 | ✅ **成熟且宽松许可** | 高 | librosa(ISC) / torchcrepe(MIT) / basic-pitch(Apache-2.0) |
| 4 | 口琴专用 pitch 检测代码 | ✅ **存在** | 高 | [harmonicon-dsp](https://github.com/tcanabrava/harmonicon)（MIT） · [npm 包](https://www.npmjs.com/package/bluesharp-pitch-detection)（MIT） |
| 4 | **bend（压音）检测** | ⚠️ **仅离散音高级；无连续轨迹检测工具** | 高 | `Modifier::Bend → semitones.round()` |
| 4 | **vibrato 检测** | ⚠️ **有可移植实现，无专用库** | 高/中 | `scoring.rs:172` `measured_oscillation_hz` |

### 5.2 项目能力对比矩阵

| 项目 | 明确口琴专用 | (a) 原曲音频对比 | (b) 分段评分 | (c) 错误反馈 | 许可 | 活跃度 |
| --- | --- | --- | --- | --- | --- | --- |
| **Harmonicon** | ✅ | ❌ | ⚠️ 定位，无分数 | ✅ 教练式 | MIT | 🔥 极活跃 |
| **Let's Bend** | ✅ | ❌ | ❌ | ⚠️ 仅实时可视化 | MIT | 活跃 |
| **AMT-Harmonica**（论文） | ✅ | ❌ | ❌ | ❌ | ❌ 无 | 💤 2020 起停滞 |
| **Harmonica**（arXiv 模型） | ❌ 乐器无关 | ❌ | ❌ | ❌ | — | 新 |
| **basic-pitch** | ❌ 乐器无关 | ❌ | ❌ | ❌ | Apache-2.0 | 活跃 |
| **librosa / torchcrepe** | ❌ 通用 | ❌ | ❌ | ❌ | ISC / MIT | 活跃 |

### 5.3 核心否定结论清单（**这些是最有价值的发现**）

1. ❌ **没有**口琴专用「演奏评价 / 演奏质量」学术论文的公开证据。
2. ❌ **没有**口琴「演奏质量」标注数据集；唯一的公开口琴数据集服务于**转录**任务。
3. ❌ **没有**任何口琴开源项目实现「与原曲音频对比」。
4. ❌ **没有**任何口琴开源项目输出「逐段评分」（Harmonicon 只做乐句**定位**，分数是整曲聚合）。
5. ❌ **没有**连续的口琴**压音轨迹检测**工具；现有实现均把 bend 当作已知的离散音高。
6. ❌ **没有**口琴专用的独立 **vibrato 分析库**。
7. ⚠️ 名字含 "Harmonica"/"Harmonicon" 的项目**绝大多数与口琴无关**，检索时极易误判
   （尤其 arXiv 的 "Harmonica" 转录模型是**乐器无关**的）。

---

## 6. 对技术路线选择的含义（仅陈述事实约束，不替负责人做决定）

> 以下仅列出**上述事实**对 **`SPEC.md`** 各条目/待确认项的**客观约束**，不包含任何推荐。
> 技术路线由项目负责人确定。
>
> 编号对应 `SPEC.md`：§1 边界、§2 已确认决策、§3 输出物、§4 特征性价比、
> §5 时间对齐、§6 分段、§7 音高提取选型、§8 待办。
>
> **前置提醒**：`SPEC.md` §2 已确认「评价对象 = 双音频对比」，
> 且 §2/§1 **明确排除**了自然语言反馈与 Agent 生成。因此本文第 3 节查到的
> Harmonicon「教练式反馈」**不属于本项目可复用范围**，仅可作为"参考物是什么"的旁证。

**关于 §1 边界 / §2 评价对象（双音频对比）**

- 事实：**没有找到公开可复用的"口琴参考音频对比"实现**——Harmonicon、Let's Bend 均无此能力。
- 事实：唯一可比对的开源实现，其参考物是 **MIDI 音符序列**
  （`ScheduledNote.expected_pitch: Option<u8>`），比对形式为 `offset` + 布尔 `playing_expected`，
  即**结构化音符 vs 演奏**，而非**音频 vs 音频**。
- 事实：唯一的口琴自动转录论文（ICASSP 2019）的输出也是**音符级转录**，不是音频差异指标。
- 推论性事实：SPEC.md §3 要求的 `metrics.json` 中
  `alignment` / `pitch_cents_mae` / `timing_mae_ms` / `energy_db_delta` 等字段形态，
  在口琴领域**没有现成实现可对照其取值范围或"正常/异常"边界**。

**关于 §4 特征性价比（音高 / 节奏 / 力度 / 颤音压音 / 音色）**

- 音高：事实：口琴 bend 的**物理参数范围**有文献可依（如 3 号孔可达 3 个半音、5/7 号孔无压音，
  见 Harmonicon 2026-09-07 博客及 JASA 系列论文），但这些文献**不提供演奏评价方法或阈值**。
- 颤音/压音：事实：存在一个 MIT 许可的**可运行 vibrato 速率测量实现**
  （`measured_oscillation_hz`，含 15 cents 最小摆幅门限），但其判定目标是
  "是否达到谱面声明的速率 ±40%"，**不是**"颤音质量好坏"，也**不是** SPEC.md §4 所需的
  "颤音/压音"差异指标；**未找到**连续压音轨迹检测实现。
- 音色：事实：Harmonicon 的评分**主体只有 timing**；音准（cents）仅作二值门控
  （`playing_expected`）。即**没有**音准偏差、力度、音色任一维度的口琴评分实现可参考——
  SPEC.md §4 表中「核心」三项与「暂缓」项，均**无公开先例可对标阈值**。
- 稳定性：事实：Harmonicon 作者公开表示，其真实录音语料**尚未建成**，
  并列出必须覆盖"不同音量、麦克风距离、至少两支麦克风"（`docs/pitch_detection_plan.md`）。
  这与 SPEC.md §4 把音色判为"**低**（麦克风/距离/环境敏感）"的关切方向一致，
  但**该判断在公开文献中亦无口琴专项实验数据支撑**。

**关于 §5 时间对齐（CENS 粗对齐 + f0 细对比）**

- 事实：检索范围内**未找到任何口琴领域的音频对齐先例**（无论 DTW、音符级或节拍级）。
  SPEC.md §5 归纳的甜区来自 **librosa 官方教程与 Müller《FMP》教科书**，
  这是**通用音乐同步**的工程共识，**不是口琴专项验证结果**。
- 事实：SPEC.md §5 提出"口琴是单声部乐器，chroma 会丢失八度信息、无法反映走音"这一判断，
  与 Harmonicon 源码注释记录的实测现象存在**潜在张力**：
  该注释称 pYIN 与 MPM 会把 **D4+G4 双音解析成不存在的 F4**，
  即口琴在双簧/和弦发声时**不满足单声部假设**。两说是否冲突，取决于实际演奏法。
- 事实：**未找到**任何"口琴 CENS/DTW 对齐 + f0 细对比"的公开实现或评测。

**关于 §6 分段（A 人工 / B 等分 / C 乐句自动 / D 曲谱驱动）**

- 事实：**没有任何口琴开源项目输出逐段评分**。
  Harmonicon 有**乐句（phrase section）**结构（`notes.rs:76` `phrase_section`、
  `adaptive_difficulty.rs:43` `group_phrase_sections()`），但其用途是
  **自适应难度解锁**与**重练循环定位**（`results.rs` 的 `PRACTICE_WINDOW_BARS = 2.0`，
  用 `missed_range()` 找失误最密集窗口），**不产出 per-segment 分数**。
  其整曲分数是聚合值（`accuracy()` + `grade()` A+…F）。
- 事实：即 SPEC.md §6 的 **C（乐句自动切分）** 有一个可阅读的工程实现（MIT），
  但**没有**"分段后如何给每段打分"的公开参考。
- 事实：**未找到**曲谱驱动的口琴分段先例（D）。

**关于 §7 音高提取选型**

- 事实：SPEC.md §7 的两个候选**均可直接使用**：
  `librosa.pyin`（ISC，本机已装 0.11.0，零下载）与
  `torchcrepe`（MIT，PyPI 0.0.24，**本机未装**，首次运行需下载权重）。
- 事实：**不存在"口琴专用"的 CREPE/pYIN 权重或微调版本**；
  候选模型均为**通用**（instrument-agnostic）模型，**未见口琴专项精度评估**。
- 事实：Harmonicon 用 Rust 实现了 FFT / YIN / pYIN / MPM / NMF 五种检测器（MIT），
  其源码注释记录：**pYIN 与 MPM 在 D4+G4 上会报出不存在的 F4**，
  而 FFT（默认）与 NMF 能正确解析双音——即**单音 vs 多音检测器的失败模式在该项目中被实测过**。
- 事实：可选的其它引擎许可约束：`basic-pitch`（Apache-2.0，**是本文清单中唯一 README 明确
  输出 pitch bend 的工具**）、`aubio`（**GPL-3.0**）、`Essentia`（**AGPL-3.0**）、
  `parselmouth`（**GPL-3.0**）。SPEC.md §7 目前只列了 torchcrepe 与 librosa.pyin。

**关于 §3 输出物 / §8 待办（数据来源）**

- 事实：唯一的公开口琴音频数据集（337 wav / ≈1.08 GiB / `.mid` + `*Hz.txt` 标注）
  **无许可证**，且标注是**多音转录**而非演奏质量，仓库自 2020 年起停滞。
- 事实：HuggingFace Datasets 与 Zenodo 上**未找到口琴演奏音频数据集**。
- 事实：Harmonicon 作者明确表示需要**自建**录音语料。这与 SPEC.md §8
  "负责人提供数据来源（录音规格/样例）"一项的客观处境一致：
  **公开数据不足以替代自采数据**。

**关于 §4 验证标准 / "特征能否区分演奏质量"**

- 事实：现有口琴论文采用的指标是 **frame-based F-measure**（转录准确率），
  与"特征能否区分演奏质量"**不是同一类指标**。
- 事实：原交接简报的核心待验证命题——"口琴演奏中的客观声学特征是否可以区分不同演奏质量"——
  在公开文献中**没有可对标的实验设计、基准或标注数据**。

**跨条目的总体客观约束**

- 事实：若要做**音频 vs 音频对比**或**逐段评分**，**公开可复用的口琴实现似乎缺失**，
  两项均需自行实现。
- 事实：**口琴专用的"音符级/乐句级对齐 + 教练式反馈"已有完整开源实现可阅读**
  （Harmonicon，MIT 许可，Rust，极活跃，2026-09 仍在日更）；
  但其中的"反馈"部分**落在本项目 SPEC.md §1 边界之外**，
  可复用的是其**口琴音域/吹吸/压音约束建模**与**分段/对齐思路**。
- 事实：**口琴专用的实时音高检测有两条可直接使用的路径**：
  Rust 的 `harmonicon-dsp`（MIT，需取源码）与 JS 的 `bluesharp-pitch-detection`（MIT，npm 可装）。
- 事实：**通用音高提取不构成瓶颈**；bend 与 vibrato 的**检测**（而非评分）当前只有
  离散音高级 / 速率级实现，且均已有一个 MIT 许可的参考实现可阅读。

---

## 附录 A：检索方法与已核实的检索端点

为便于复核，列出本次调研**实际调用并得到有效响应**的检索端点：

| 用途 | 端点 |
| --- | --- |
| 论文元数据 | `https://api.crossref.org/works?query.bibliographic=…`、`https://api.crossref.org/works/{DOI}` |
| 论文检索与摘要 | `https://api.openalex.org/works?search=…`、`?filter=title.search:harmonica` |
| arXiv 元数据 | `http://export.arxiv.org/api/query?id_list=2609.04640` |
| GitHub 仓库 | `https://api.github.com/repos/{owner}/{repo}`、`/languages`、`/git/trees/{branch}?recursive=1`、`/releases`、`/commits` |
| GitHub 检索 | `https://api.github.com/search/repositories?q=…` |
| 数据集 | `https://huggingface.co/api/datasets?search=harmonica` |
| 数据集 | `https://zenodo.org/api/records?q=harmonica` |
| Python 包 | `https://pypi.org/pypi/{pkg}/json` |
| npm 包 | `https://registry.npmjs.org/{pkg}` |

### 已知的检索限制（如实记录）

1. **Semantic Scholar API 全程返回 HTTP 429**（rate limit），故论文检索改由 Crossref + OpenAlex 承担；
   可能因此漏检部分会议论文。
2. **部分 PDF 无法取回正文**：QMUL 预印本 PDF 下载后为空文件；IEEE Xplore 与 ACM DL 返回 403 反爬。
   故论文正文细节依赖 **OpenAlex 收录的官方摘要** 与 **GitHub 仓库源码**交叉印证。
3. **手风琴论文（10.1145/3801438.3804854）未读到方法细节**——
   Crossref 无摘要，ACM PDF 被反爬拦截。表中仅标注其为"相似但不完全匹配"。
4. **`0-context.md` 提到的 "Automatic Music Transcription (Harmonica)" 线索已定位并核实**，
   即 1.2(A) 的 ICASSP 2019 论文及其 GitHub 仓库。
5. **非英文文献覆盖有限**：中文（`口琴 演奏 分析`）、日文检索均无有效命中；
   不排除中/日/韩学位论文或非索引期刊中存在相关工作。

## 附录 B：本次调研实际执行的文件级核实

| 对象 | 核实方式 | 规模 |
| --- | --- | --- |
| `tcanabrava/harmonicon` | 下载 `main` tarball 并解压，阅读 Rust 源码与 `contributing/src/*.md` | 43.8 MB，1070 个 tree 条目，14 个 crate |
| `egdels/bluesharpbendingapp` | `git clone --depth 1` 后检索源码结构 | 19 MB |
| `filipemlins/Automatic-Music-Transcription-Harmonica` | GitHub Trees API 递归遍历 + 文件计数 | 3493 个 tree 条目，337 wav / 1.08 GiB |

关键源码文件（可直接核对）：

- `crates/harmonicon-dsp/src/lib.rs`（`PitchAlgorithm` 五种算法）
- `crates/harmonicon-core/src/scoring.rs`（`classify_note`、`measured_oscillation_hz`）
- `crates/harmonicon-gameplay/src/gameplay/notes.rs`（`ScheduledNote`、`phrase_section`）
- `crates/harmonicon-gameplay/src/gameplay/judge.rs`（vibrato 判定调用点）
- `crates/harmonicon-gameplay/src/gameplay/coaching.rs`（`Observation`、`missed_range`、`ranked_techniques`）
- `crates/harmonicon-gameplay/src/gameplay/results.rs`（`accuracy`、`grade`、`PRACTICE_WINDOW_BARS`）
- `docs/pitch_detection_plan.md`（作者自述的待录制语料清单）
