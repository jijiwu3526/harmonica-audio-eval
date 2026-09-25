# 组件归属推导 · 由下往上的核对记录

> 本文件回答负责人的问题：
> 「先思考这一坨代码可以组成什么组件，那一坨可以组成什么组件，
> 然后把这些组件与之前的设计做对比。」
>
> 以及：「虚拟树」在软件铸造厂宪章里**有没有写**。
>
> 生成方式：`tools/derive_clusters.py`（可重跑）· 登记于 `.spec/graph/overlay.json`
>
> ★ 本文件是**我自己的核验记录**，不是给负责人读的版本。
> 负责人版本在 `docs/for-owner/组件归属-由下往上.html`。

---

## 0 · 先说结论（三句话）

1. **机械推导确认了 C3，部分确认了 C2 与 C4，未能确认 C1** —— 而 C1 未被确认
   是**信号缺失**，不是设计错误（原因见 §4.1）。
2. **本次推导查出了 2 个真实缺陷**，都在 `pitch` 上，且是**同一个根因**；
   12 项既有机械检查**全部漏过**它们。已修，并新增检查⑬防复发。
3. **「虚拟树」在宪章里不存在。** 宪章写的是 `Virtual System Graph`（§10），
   而「树」是这张图里**三类关系之一**（§44.2 的 Decomposition Tree）。
   我把概念对齐后的产物登记在 `.spec/graph/`。

---

## 1 · 为什么必须机械化，不能靠我"看一遍然后说我推导出来了"

负责人给的方法是**由下往上**。但我知道答案（铭牌上写着 `COMPONENT: COMP-C2`）。

若我手工读一遍代码、再写出"我推导出这 18 个文件属于 4 个组件"，
那不是由下往上 —— 那是**自上而下 + 事后编理由**。
两者在文本上长得一模一样，无法分辨。

所以规则是：**推导过程不得读取铭牌的 `COMPONENT` 字段。**
这一条写进了 `tools/derive_clusters.py` 的实现里（`_read_plate` 把该字段
单独存为 `_plate_COMPONENT`，只在校验阶段对照，聚类阶段不参与）。
**对照结果不一致 = 真发现**，这才是由下往上的收益。

---

## 2 · 四种信号：哪些能用，哪些在空壳期是残缺的

| 信号 | 内容 | 空壳期完整性 | 为什么 |
| --- | --- | --- | --- |
| S1 | import 边 | ❌ **残缺** | 18 个文件函数体全是 `raise NotImplementedError`，真实调用边**还没被写出来** |
| S2 | 端口生产（`PORTS[*].produced_by`） | ✅ 完整 | 由 `profile.PORTS` 的数据决定，与函数体无关 |
| S3 | 算法消费（插件 `PluginSpec.required_inputs`） | ✅ 完整 | 同上 |
| S4 | 契约符号足迹（文件引用了 `contract.py` 的哪些符号） | ✅ 完整 | 由类型标注与常量定义承载，而空壳期**恰恰只有这些写全了** |

**S1 残缺是本方法论最重要的发现。** 它意味着：
任何"用 import 图推断组件边界"的做法，在铸造厂的虚拟期都是**在推断一个尚未存在的图**。

### 2.1 第一版工具的真实失败

第一版我用「import 图 + 贪心模块度聚类」，结果是**一坨 8 文件的浆糊**：

```
坨 1（8 文件）：__main__ · cockpit · cockpit.app · contract · core.api
                · core.surface · host.app · profile      ← 全糊在一起
```

诊断出两个原因，**都是真实的，不是调参问题**：

1. **import 图残缺**（上表 S1）。
2. **`contract.py` 是枢纽节点**。模块度算法会把枢纽自己的社区粘成一大坨 ——
   这是 resolution limit 的镜像，是算法已知病，不是数据问题。

于是换成 **Jaccard 平均连接层次聚类**（对枢纽天然免疫：枢纽特征集大，
与谁都只有低 Jaccard，于是自己成为孤点 —— 这**正确**，契约本来就不是组件）。

### 2.2 第二版工具的两个自身缺陷（记录在案）

| 缺陷 | 症状 | 修法 |
| --- | --- | --- |
| `profile.PORTS` 是 `tuple[PortSpec, ...]`，第一版按 `dict` 读 | S2 整个信号为空，端口图全丢 | 改为遍历 tuple |
| `__all__` 出现在几乎每个文件里，成了**假桥** | `core ↔ host` 相似度虚高到 **1.000**，粘成假坨 | 从契约符号集里剔除 dunder |

---

## 3 · 多角度确认（负责人要求"通过多角度来思考确认"）

单靠一种聚类不足以定论，故跑了 **5 个独立角度**：

| # | 角度 | 回答什么 | 结果 |
| --- | --- | --- | --- |
| 1 | 阈值敏感性 | 聚类结论**稳不稳** | ⚠️ 见 §3.1 —— **没有稳定平台** |
| 2 | 稳健黏连对 | 哪些关系**与阈值无关** | 4 对（§3.2） |
| 3 | 端口供需二分图 | 谁和谁**真的通过端口对话** | `notes.*` 是全算法共享词汇（§3.3） |
| 4 | 割点分析（Tarjan） | 谁删掉会**切断**别人 | `contract` 是**全图唯一割点**（§3.4） |
| 5 | 失败点 / 状态归属 | 谁抛异常、谁持有可变状态 | 无模块级可变状态（除 `__version__`/`__all__`）（§3.5） |

### 3.1 ★ 阈值敏感性 —— 本方法论最关键的诚实点

```
   阈值    坨数   最大坨   跨铭牌坨
  0.05     10      5        2
  0.10     13      3        2
  0.15     14      3        1
  0.20     15      3        1
  0.25     15      3        1
  0.30     15      3        1
  0.34     17      2        0
  0.40     18      1        0
  0.50     18      1        0
```

**从 1 坨摆到 18 坨，没有稳定平台。**

结论必须如实写：**空壳期代码不足以决定组件边界。**
这不是调参失败 —— 阈值调到某个值让"结果好看"，那是自欺。
真实含义是：**边界信息不在代码里，而在 docstring 与契约里。**
所以下面只取「跨全部阈值稳健」的部分当结论，其余一律标 `NOT-CONFIRMED`。

### 3.2 稳健黏连对（4 对，与阈值无关）

| 稳定性 | Jaccard | 对 | 读法 |
| --- | --- | --- | --- |
| **7/7** | 0.350 | `dynamics ↔ timing` | 同层算法，共享契约签名与「按音配对」口径 |
| 6/7 | 0.316 | `dynamics ↔ pitch` | 同上 |
| 6/7 | 0.300 | `pitch ↔ timing` | 同上 |
| 6/7 | 0.300 | `__main__ ↔ cockpit.app` | **★ 见下** |

**`__main__ ↔ cockpit.app` 是本次唯一"设计没写、推导发现"的对。**
两者共享 `contract:UiSeries` / `contract:UiView` / `sym:EXIT` / `sym:build` / `sym:render`。

读法：**它们是同一类东西 —— 内核之外的结果消费者。**
一个是无头落盘（写 `metrics.json` + `report.md`），一个是图形界面。
设计里二者分属 `COMP-PKG` 与 `COMP-C4`，铭牌不同；
但在**结构角色**上它们对等，都只读 `UiView`、都不进计算路径。

⇒ 这从代码层给**不变量 F**（"删掉 C4 内核仍须跑通"）提供了证据：
无头入口与 C4 处在对等位置，所以"删掉 C4 不受影响"是**结构性的**，不是补丁。
这一条已登记进 `overlay.json` 的 `stable_findings`。

### 3.3 端口供需图（空壳期完整）

```
生产者：core.align   → warp_path
        core.features→ chroma.lowres.* · notes.* · pitch.* · rms.*   （12 个里产 8 个）
        core.surface → pcm.mapped.* · pcm.warped.practice

消费者：pitch    ← notes.* · pitch.*
        timing   ← notes.* · pcm.mapped.*
        dynamics ← notes.* · rms.*

★ 全算法共享词汇 = notes.*
★ 无算法消费   = chroma.lowres.* · warp_path
```

两条读法：

1. **`notes.*` 是 C2/C3 之间的实际接口重心**，不是 `pitch.*` / `rms.*` / `pcm.*`。
   这机械解释了为什么 MOLD BREAK 必须补上 `notes.practice` ——
   缺了它，三个算法里有两个拿不到逐音索引。
2. `chroma.lowres.*` 与 `warp_path` 无算法消费，是**证据端口**
   （供审查者复现对齐、验证其余端口不是凭空来的），**不是死端口**。
   工具不对它们报警，正是 `profile` 的刻意豁免。

### 3.4 割点：全图只有一个

```
harmonica_eval.contract  ——  度 = 11，删掉它 11 个文件的依赖同时断裂
```

**这是本次推导最干净的一条机械结论。** 一个既连接所有人、
又谁的内部都不属于的节点 —— 那正是「契约」的定义。

⇒ 它从机械上**证实**了 `COMPONENT-CONTRACT` 铭牌的声明：
「四个组件之间的分界线，**本身不是组件**」。

### 3.5 失败点与状态归属

18 个文件里**没有任何模块级可变状态**（除 `__init__` 的 `__version__` 与各出口的 `__all__`），
也没有一个 `global` 声明。抛异常点集中在 `host.app`（13）、`cockpit.app`（10）、
`profile`（10）、`__main__`（8）—— 与"这些是边界/装配层"的定位一致。

---

## 4 · 与之前的设计逐组件对比

> 判定三值：`CONFIRMED`（机械证据支持）· `PARTIAL`（部分支持）·
> `NOT-CONFIRMED`（证据不足以支持 —— **不等于错**）

### 4.1 COMP-C1 Framework / Host —— `NOT-CONFIRMED`

- **证据**：`host.app` 只 import `contract`，与任何文件都不构成稳健黏连。
- **为什么没确认**：C1 的存在理由是**编排**，而编排边（谁调谁、按什么顺序）
  在空壳期**不存在** —— 函数体是 `raise`。**机械推导看不见它。这是信号缺失。**
- **与设计冲突吗**：不冲突，但**也未被证实**。要证实需实现落地后重跑本工具。
- **风险**：低。C1 的边界由契约（`CONTRACT-HOST-v1` 的 7 个操作）定义，
  不由耦合度定义。

### 4.2 COMP-C2 Audio Core —— `PARTIAL`

- **证据**：端口生产图把 `core.align` / `core.features` / `core.surface`
  区分为三个不同生产者，三者**互不共享端口族**；`core.api` 是唯一
  import `core.surface` 的文件。
- **为什么只是部分**：推导支持"**C2 是一个内聚单元**"，
  但**推不出**其内部 5 路切分（ingest / align / features / surface / api）。
  因为那 5 路是一条**数据流链**（解码→对齐→物化→装配→编排），
  而数据流写在 docstring 里，不写在代码里。
- **与设计冲突吗**：一致。且推导**独立复现**了"`core.api` 是唯一对外门面" ——
  它是 core 内部唯一被 import 的文件。
- **风险**：低。内部切分是 C2 的私有实现细节，深组件保证它不外泄。

### 4.3 COMP-C3 Algorithm —— `CONFIRMED` ✅

- **证据**：三个算法**两两稳健黏连**（7/7、6/7、6/7），
  共享 `AlgorithmDataContract` / `AlgorithmResultEnvelope` / `needs:notes` / `run` / `summarize`。
- **与设计冲突吗**：一致，且是本次推导**最强**的一条结论。
- **风险**：极低。

### 4.4 COMP-C4 Developer Cockpit —— `PARTIAL`

- **证据**：`cockpit` 与 `cockpit.app` 只 import `contract`，与 C2/C3 **零耦合** ——
  机械证实了「C4 不进计算路径」。
- **额外发现**：`__main__ ↔ cockpit.app` 同类（§3.2）。
- **与设计冲突吗**：与不变量 F 一致，且为该不变量提供了代码层证据。
- **风险**：低。

### 4.5 汇总

| 组件 | 判定 | 与现有设计 |
| --- | --- | --- |
| COMP-C1 | `NOT-CONFIRMED`（信号缺失） | 不冲突，未证实 |
| COMP-C2 | `PARTIAL` | 一致 + 独立复现门面结论 |
| COMP-C3 | `CONFIRMED` | 一致（最强） |
| COMP-C4 | `PARTIAL` | 一致 + 为不变量 F 提供证据 |

**总判定：组件边界不需要重划。** 推导没有产生任何与现有设计冲突的结论，
反而在三处**独立复现**了设计的论断（契约非组件、core.api 唯一门面、C4 不进计算路径）。

---

## 5 · ★ 本次推导查出的 2 个真实缺陷（12 项检查全部漏过）

两个缺陷都在 `pitch.py`，而且是**同一个根因**。

### 5.1 根因

`TimelineBasis.REFERENCE` 的含义是
**「保留源时间、未被时间归一化」**，它**不蕴含**「两侧帧号一一对应」。

参考与练习是**两段独立录音**，时长各自落在
`[profile.AUDIO.min_duration_sec, max_duration_sec]` = `[45, 120]` 秒。
`pitch.*` 的帧数 = 时长 / `MATERIALIZE.pitch_hop_length`，
故两侧 `n_frames` **默认不相等**，逐帧相减**无定义**。

### 5.2 为什么一直没暴露

实测本数据集 01 的全部 wav：

```
标准旋律版.wav     72.802 s    1568 pitch 帧
01_音准走调.wav    72.802 s    1568 pitch 帧   Δ = 0
02_节奏抢拖.wav    72.802 s    1568 pitch 帧   Δ = 0
03_气息不匀.wav    72.802 s    1568 pitch 帧   Δ = 0
04_错音.wav        72.802 s    1568 pitch 帧   Δ = 0
05_漏音断句.wav    72.802 s    1568 pitch 帧   Δ = 0
```

**恰好全是 72.802 s**（同一渲染器批量产出）。
"恰好等长"把缺陷掩盖了 —— 换一首演奏时长不同的练习曲
（**这正是真实使用场景**）立刻崩。

### 5.3 缺陷 A：签名收不到音符边界

- 插件规格声明 pitch 需要
  `('pitch.reference', 'pitch.practice', 'notes.reference', 'notes.practice')`
- `algorithms/__init__.py` 的 MOLD BREAK 注记明写：
  「pitch 用逐音索引把逐帧偏差聚合成『第 n 个音偏了多少音分』」
- **但** `compare_pitch_curves(ref_pitch, prac_pitch, sample_rate)` **没有 notes 参数**，
  docstring 却写"返回**逐音**的音分偏差"。`summarize_deviations` 同样只收一个参数。

⇒ 实现者被要求"聚合到第 n 个音"，却不被交给任何音符边界。他只能：
(a) 自己发明音符切分（重做 `features` 的活），或
(b) 假装逐帧结果就是逐音结果（**静默算错**）。
两条路都是 §22 硬失败。

**为什么 MOLD BREAK 当时没修好**：那次的论证只讲到"为了能标注第几个音"（**可定位**），
没讲到"不等长**根本无法比较**"。论证不完整，所以签名照旧漏了参数。

### 5.4 缺陷 B：三处「同轴即可逐帧相减」的假推理

| 文件 | 行 | 原文 |
| --- | --- | --- |
| `profile.py` | 333 | 「与参考同轴（REFERENCE），从而两条曲线可以逐帧直接相减得到音分误差」 |
| `pitch.py` | 19 | 「消费 pitch.reference / pitch.practice（两者同轴，可逐帧相减）」 |
| `pitch.py` | 79 | 「两条曲线同轴（都是 REFERENCE），故可直接逐帧相减」 |

三处同一根因。已全部改为正确论述：用 `notes.*` 的 `onset_sec` 按音配对后再比较。

### 5.5 修复内容

| 文件 | 改动 |
| --- | --- |
| `pitch.py` | MUST 补 `notes.reference/practice`；MUST NOT 补"禁止按帧号直接对齐"；`compare_pitch_curves` 签名补 `ref_notes` / `prac_notes` 并重写整段规格 |
| `profile.py` | `pitch.practice` 的 rationale 更正 |
| `pitch.py` | `summarize_deviations` 补记**已知缺口**（见 §5.6） |
| `tools/verify_shell.py` | **新增检查⑬**：声称产出『逐音』的算法模块，必须有函数接收音符边界 |

### 5.6 顺带查出的第 3 个不对称（未自行修，按 §37 上报）

```
pitch     n_notes_used ✓   n_unpaired ✗   共 5 键
timing    n_notes_used ✓   n_unpaired ✓   共 8 键
dynamics  n_notes_used ✓   n_unpaired ✓   共 5 键
```

`timing` 的 docstring 明写：「漏吹的音与多吹的音不产生时间偏差，
但它们是重要的信息，**静默丢弃会让报告看起来比实际更好**」。

`pitch` 的配对同样会失败（漏音/多音/音数不等），配不上的音同样被排除 ——
**排除数量却无处报告**。后果：读者无法分辨「整首都测了」与「只测上了少数几个音」，
而 `off_pitch_ratio` 的分母正是 `n_notes_used`。

**历史根因**：当时的 `PAYLOAD_SCHEMAS` 由人工维护、三份各自演化，缺少对称性约束。
该表已随插件化删除；现在 payload 由 `UiScalar.key` / `UiSeries.key` 自描述。

**为什么不自行修**：修它要在**冻结表**加键 = 接口变更。
按宪章 §37 Gate Challenge 上报，不自行添加。

---

## 6 · 新增检查⑬，以及它自己的一次误报

检查⑬ 的规则：算法模块的 docstring 若声称产出 `逐音`/`per_note` 结果，
则同模块内必须有某个公开函数的形参名含音符边界词根。

**第一版把词根收窄成只有 `note`，刷出 1 条误报**：

```
❌ timing.py ... 签名：match_onsets(ref_onsets, prac_onsets, tolerance_sec)
```

`match_onsets` **确实**接收了音符边界（起音时刻就是边界），
只是变量名叫 `onset` 不叫 `note`。

这正是本仓在检查⑪、⑫ 上**重复吃过两次的亏**：
**过宽的检查制造噪声，过窄的检查漏掉真缺陷。**
现按实际语义补齐词根 `(note, onset, span, bound)`，并把这个误报记录在
检查⑬ 的 docstring 里 —— 不是为了免责，是因为**下一个人会踩同一个坑**。

修后：检查⑬ 精确命中 1 条真缺陷（`pitch.py`），无噪声。

---

## 7 · 「虚拟树」这个概念，宪章里到底有没有

负责人的原话：「对虚拟树这个有概念吗软件铸造厂里面有没有写」。

### 7.1 直接回答：**没有「虚拟树」这个词**

对宪章全文（2631 行 / 54 节）做检索：

| 检索词 | 出现次数 |
| --- | --- |
| `虚拟树` | **0** |
| `树` | **2**（L671「真正的系统不应首先以**目录树**存在」；L1888 反模式清单） |
| `Graph` | 17 |
| `Virtual System Graph` | 3 |

### 7.2 宪章真正写的是 `Virtual System Graph`（§10）

> **§10 · Virtual System Graph 才是系统级 Source of Truth**
>
> 真正的系统不应首先以目录树存在。
> 它首先应以 **Executable Virtual System Graph** 存在。
>
> 这张图要能表达：Component Identity / Provides / Requires /
> Interface Contract / Data Flow / Control Flow / State /
> Failure Propagation / Dependency / Resource Budget /
> Security Boundary / Mission Threads / 当前 realization 状态。

### 7.3 「树」是这张图里**三类关系之一**（§44.2）

宪章 §44.2 要求 Engineering Graph Kernel **同时管理三类关系**：

```text
Decomposition Tree   →  它属于谁？                  ← 「树」在这里
Dependency DAG       →  谁依赖谁、谁 READY、谁 BLOCKED？
Traceability Graph   →  为什么存在、怎样证明、上游变化会污染谁？
```

⇒ **「树」不是「图」的同义词，而是图的一个投影。**
负责人说的"虚拟树"，落到宪章术语上最接近的是
**Decomposition Tree**（它属于谁）；但完整要求是**三类关系都要有**。

### 7.4 我按此做了什么

| 宪章要求 | 本仓产物 | 数据来源 |
| --- | --- | --- |
| Decomposition Tree | `virtual-system-graph.json` 的 `decomposition` | **从代码推导**（读铭牌 `COMPONENT`） |
| Dependency DAG | 同文件的 `dependency` | **从代码推导**（端口供需 + import） |
| Traceability Graph | 同文件的 `traceability` + `overlay.json` | **手写**（代码里不存在） |

关键设计：**能从代码推导的一律推导，只有代码里不存在的才允许手写。**
手写部分单独放 `.spec/graph/overlay.json`，与生成物分开 ——
这样"哪些是我推导的、哪些是我声称的"**一眼可辨**。

为什么坚持这条：本仓刚发生过一次事故 —— 我手写的「宪章 §11 逃生口」引用
是**伪造的**，并传播到 6 个文件。手写的结构化事实会**静默漂移**，
而且**无法机械反驳**。所以现在能推导的绝不手写。

### 7.5 一个诚实的缺口

宪章 §10 还要求：

> 理想情况下，虚拟组件可以用 stub / mock / model 参与端到端运行。
> 因此在一行真实业务实现都没有时，系统应已经能
> 输入虚拟数据 → 经过虚拟组件 → 执行关键 Mission Thread → 得到符合预期的虚拟输出。

**本仓目前做不到** —— 18 个空壳全部 `raise NotImplementedError`，
尚无 stub/mock 实现层。已作为 **GAP-5** 登记在 `overlay.json`，
并标了 `owner_decision_needed: true`。

**这不是我"忘了"**，是两件事的取舍：先补 Build Instruction（Freeze 阻塞项），
还是先补 mock 执行层。前者是宪章 §17/§30 的硬要求，后者是 §10 的"理想情况下"。
我选了前者。**若负责人认为该反过来，请裁定。**

---

## 8 · 可复现

```bash
cd harmonica-eval
python3 tools/derive_clusters.py            # 完整推导 + 铭牌对照 + 阈值敏感性
python3 tools/derive_clusters.py --raw      # 只看四种信号
python3 tools/build_virtual_graph.py        # 重建虚拟图
python3 tools/build_virtual_graph.py --check   # 只校验
python3 tools/verify_shell.py               # 13 项机械检查
```

本文件的所有数字与结论都可由上述命令重现。
