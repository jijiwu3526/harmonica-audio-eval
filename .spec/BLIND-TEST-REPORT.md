# 盲独立可复现性测试报告（宪章 §20）

> 执行日期：本轮
> 对象：`harmonica_eval/` 空壳（18 文件，71 个空壳函数）
> 方法：≥2 个**不同模型**、互不知情、未参与设计、只能读空壳与契约
> 裁决：**`MOLD AMBIGUITY`（情况 A）→ 触发 §38 `MOLD BREAK`**

---

## 一、执行概况

| 审查者 | 模型 | 状态 | 信息来源 |
| --- | --- | --- | --- |
| Ling#1 / #2 / #3 | `ling-3.0-flash-sante-free` | ✅ 3 份 | workflow 结构化 schema |
| **DS-A** | `deepseek-v4.1-flash` | ✅ 1 份 | 自由文本 + 15 问 |
| **DS-B** | `deepseek-v4.1-flash` | ✅ 1 份 | 自由文本 + 15 问 |

**⚠ 过程中的一次失败必须记录**：首次 `workflow` 派了 6 个智能体（2 模型 × 3 次），
但 deepseek 的 3 个**全部返回 null**，只拿到 ling 一个模型的 3 次重复。

**同一模型跑 3 次不算"多个模型"** —— 它的错误是相关的。
若我当时就此收工，会得出"语义收敛"的**错误结论**。
（这正是 §20 与 §46.3 要防的事：方差必须在**模型之间**测。）

---

## 二、15 问的比对结果：**全部一致**

| 问题 | 结果 |
| --- | --- |
| q01 `read()` 单位 | 秒（5/5） |
| q02 端口不存在时行为 | 抛 `ContractViolation`（5/5） |
| q03 `pitch.*` 字段顺序 | `(f0_hz, voiced, confidence)`（5/5） |
| q04 `chroma` bin 0 | C（5/5） |
| q05 `warp_path` 列序 | `(reference_frame, practice_frame)`（5/5） |
| q06 `progress` 取值域 | 0.0–1.0（5/5） |
| q07 `timing` 的时间轴 | REFERENCE（5/5） |
| q08 超长音频错误码 | `INPUT_TOO_LONG`（5/5） |
| q09 `core` 能否 import `algorithms` | 禁止（5/5） |
| q10 Seal 后是否可写 | 不可写（5/5） |
| q11 对齐失败怎么办 | 抛错终止（5/5） |
| q12 `dynamics` 单位 | dB（5/5） |
| q13 Host 契约方法数 | 7（5/5） |
| q14 算法要额外数据怎么办 | 从 `pcm.mapped.*` 自己算（5/5） |
| **q15 综合可实现性** | **能，但有几处需要猜（5/5）** |

**表面看像情况 C（语义收敛）。但这是假象，原因见下。**

---

## 三、★ 为什么不能判"通过"：我的问题清单有偏

**审查者 DS-B 自己指出了这一点**（原话）：

> 这份空壳的 docstring 自带「★ 盲审发现的缺口，已补/已冻结」标记——
> FIELD_LAYOUTS、COMMAND_LEGALITY、progress 取值域、chroma bin0、
> warp_path 顺序都是**前一轮盲审已经冻结过**的点。
> 我作为第二轮审阅者看到的是修补后的版本，所以这 14 条格外清晰。
> **这不代表壳本身无歧义。**

这是**方法论上的要害**，我必须承认：

- 我的 15 个问题**全部指向我已经修过的地方** → 当然一致
- 定选式问题只能测量**已知项**上的收敛，
  **结构上无法发现未知缺陷**
- 两个审查者**都注意到**了这个偏向 —— 说明它们没有在迎合

**修正后的方法要求**：定选式比对 + **自由探索**必须并用。
定选测"我们冻对了吗"，自由探索才能发现"我们漏了什么"。

**事实印证**：真正的缺陷**全部**来自自由探索部分，**没有一个**来自我的 15 问。

---

## 四、★ 两个模型独立找到的同一个致命缺陷

### 4.1 `dynamics` 的时间轴自相矛盾（**契约级冲突**）

**DS-A 的表述**：

> `dynamics.py` 要求用 WARPED 轴且禁止 REFERENCE 轴，
> 但它的 `required_ports` 只有两个被声明为 REFERENCE 轴的 `rms.*` 端口；
> 数据面里根本不存在 WARPED 轴的 rms。
> **这不是留白，是两条 MUST 无法同时满足。**

**DS-B 的表述**（独立得出，且给出了三个出口）：

> (a) 自己从 `pcm.warped.practice` 算 → 那 `required_ports` 漏了端口
> (b) 无视 `AXIS` 用 REFERENCE → 违反显式 MUST NOT
> (c) 把「WARPED 轴语义」弱读为「按音索引对齐而非按绝对时间」
> **契约未裁定，必须猜。**

**我已实测确认**：

```text
dynamics.py:21   MUST    "用 WARPED 轴语义"
dynamics.py:29   MUST NOT "使用 REFERENCE 轴"
dynamics.py:52   AXIS = TimelineBasis.WARPED (模块常量，便于 grep)

但：
profile.py  rms.reference  timeline_basis = REFERENCE
profile.py  rms.practice   timeline_basis = REFERENCE
数据面里唯一的 WARPED 端口 = pcm.warped.practice
→ 不存在 WARPED 轴的 rms 端口
```

**§20 判定**：多个独立模型对同一份 MUST 给出了**多个都合理但互相冲突**的实现读法
（上述 a/b/c），且**无法从模具中裁定** ⇒ **情况 A：`MOLD AMBIGUITY`**。

### 4.2 根因：`TimelineBasis` 的定义本身就自相矛盾

我深挖后发现，`dynamics` 只是**症状**。真正的病灶在契约最底层：

```text
TimelineBasis.REFERENCE 的 docstring 同时说了两件不能并存的事：
    "保留源时间"
    "对齐后重采样到参考演奏的时间轴"
```

**你不能既保留源时间、又重采样到别人的时间轴。** 这两个说法指向两条不同的网格。
`dynamics` 的作者（我）正是因为这条定义含混，才写出自相矛盾的 MUST。

**这是「一个含混的定义向下游传播成一条无法满足的约束」的教科书案例。**

### 4.3 连带缺陷：练习侧没有逐音索引

DS-B 独立发现：

> `dynamics.align_by_note(…, note_boundaries)` 需要一个边界参数，
> 但 PORTS 只有 `notes.reference`，**没有 `notes.practice`**。
> 按音对齐在练习侧无索引可用。

这与 4.1 **是同一个缺陷的两面**：dynamics 真正需要的不是"WARPED 轴"，
而是**逐音的配对关系**。我用"WARPED 轴"当作"别让时间误差污染力度"的代理，
但正确的机制是**按音配对**，不是按轴。

---

## 五、其余硬缺口（两审查者共同或分别报告）

| # | 缺口 | 严重度 | 报告者 |
| --- | --- | --- | --- |
| G1 | `dynamics` 轴矛盾 | **致命** | A + B 独立 |
| G2 | 练习侧无逐音索引（缺 `notes.practice`） | **致命** | B |
| G3 | `AlgorithmSpec.entry` 签名"由 Build Instruction 冻结" | 高 | A + B |
| G4 | 算法 payload 键名/schema 未冻结（无第二个 `FIELD_LAYOUTS`） | 高 | A + B |
| G5 | **帧→秒换算的 hop 未冻结**，且 `ALIGN.hop_length` 与 `MATERIALIZE.frame_length` 数值巧合相同 | 高 | B |
| G6 | `dimensions` 是字符串名，但声称会校验 `dimensions[-1]` 的大小（按字面无法实现） | 中 | B |
| G7 | `UiCommand.payload` 键名完全未冻结 | 高 | A |
| G8 | `HostApp` 有 4 个契约未声明的方法，与 `HostContract` 不自洽 | 高 | A |
| G9 | `progress` 只有取值域，**没有产生机制**（内部阶段禁止外泄 → 无中间进度源） | 中 | A + B |
| G10 | `units` 无受控词表（开放式举例，实际用了举例里没有的 `"chroma"`） | 中 | B |
| G11 | `CANCEL` / `RESET` 语义零定义 | 中 | B |
| G12 | `content_hash` 算法未冻结 → 跨实现**不可比**，而它的用途正是可比性断言 | 中 | B |
| G13 | `required_ports` 有两份权威（spec 与 envelope），未说是否必须相等 | 中 | B |
| G14 | `COCKPIT_DETACHED` 无触发点（`UiProjectionPort` 无上报路径） | 低 | B |
| G15 | `cockpit.render_series_plot` 返回标注 `-> str` 但 docstring 说可返回 SVG/HTML/配置 | 低 | B |
| G16 | `read()` 对 `warp_path` 的时间窗语义未定义 | 中 | B |
| G17 | `SILENCE_RMS_THRESHOLD`(线性) 与 `DB_FLOOR`(对数) 只说"同量级"，无强制换算 | 低 | A |
| G18 | `--out` 传目录时行为未定义；`CORE_BUILD_FAILED` 与具体错误码优先级未定 | 低 | A |

**G4 和 G5 尤其值得注意**：它们**正是 `FIELD_LAYOUTS` 当初要消灭的那类缺陷**
（"不会报错、只会静默算错"），只是在 payload 层与时间换算层**没有对应的冻结表**。
**同一个教训我没有推广到全部层次。**

---

## 六、裁决

### 判定：**情况 A —— `MOLD AMBIGUITY`**

依据：

1. `dynamics` 的 MUST 与 ports 声明**结构性冲突**，存在 ≥3 种都合理的实现读法（§20 情况 A）
2. 冲突源于 `TimelineBasis` 定义自身的矛盾，**不是措辞问题**
3. 两个**不同模型独立**得出同一结论 ⇒ 客观证据，非模型风格差异
4. 审查者**都**判 `infeasible: false`（故**不是**情况 B）
5. 但 q15 一致为"**能，但有几处需要猜**"，**不是**"语义清晰" ⇒ **不是**干净的情况 C

§22 补充：**「Blind Reproducibility 出现重大语义分叉」属硬失败**，不可由其他维度补偿。

### 动作：**不得打 tag**，走 §38 `MOLD BREAK`

```text
STOP IMPLEMENTATION          ← 尚未开始实现，天然满足
↓
MOLD DEFECT REPORT           ← 本文件
↓
Affected Work Packets BLOCKED ← 全部（契约变更波及所有组件）
↓
Return to Virtual World      ← 修 contract.py / profile.py / dynamics.py
↓
Upward Constraint Revision   ← TimelineBasis 定义重写
↓
Re-convergence               ← 重跑机械验证 + 重跑 §20
↓
New CAST FREEZE              ← 新 tag
```

**§38 禁止**："先做一个能跑的 workaround，以后再说。"
故：**不修 `dynamics` 一行让它"能跑"，而是回去修 `TimelineBasis` 的定义。**

---

## 七、这次测试的净价值

| 项 | 结果 |
| --- | --- |
| 确认已冻结的 14 项 | 5/5 一致 —— 这些**真的冻住了** |
| 发现未知硬缺口 | **18 条**，其中 2 条致命 |
| 阻止的错误 | 一批"两个实现者结果不可复现地分叉、且都不报错"的数值层缺陷 |
| 方法论教训 | 定选式问题只能测已知项；**必须并用自由探索** |

**若跳过这一步直接 Freeze**：
18 个文件会全部"验证通过"（机械检查确实全过），
然后实现者在 `dynamics` 上撞墙 —— 要么违反 MUST NOT，
要么自行发明一套"WARPED 轴 rms"，
产出一份**看起来正常、但与他人不可复现**的力度报告。
