# §30 Freeze 交付物对照表

> **本文档回答一个问题**：宪章要求 `CAST-FREEZE-v1.0` 这个 commit 里有什么，
> 我们现在有什么，差什么。
>
> 全部条目**逐字取自宪章 §30（L1454–1503）**，不是我归纳的清单。

---

## 一、宪章原文的 21 项

```text
Product Intent                      ✓
Foundry / Project Doctrine          ✓
Role Manifests                      ?
                                    
Architecture Graph                  ✓
Virtual Components                  ✓
Mission Threads                     ✓
Architecture Decisions              ✓
                                    
Component Contracts                 ✓
Component Designs                   ?
                                    
File Skeletons                      ✓
File Contracts                      ✓
                                    
Upstream Prompts                    ?
Downstream Prompts                  ?
Build Instructions                  ✗  ← 阻断项
                                    
Dependency DAG                      ?
Traceability Graph                  ?
                                    
Test Definitions                    ✓
Performance Budgets                 ?
Resource Budgets                    ?
Security Constraints                ?
                                    
External Fact Evidence              ✓
Adversarial Review Results          ✗  ← 阻断项
Blind Reproducibility Results       ✓
Cross-Layer Audit Results           ✗  ← 阻断项
Prompt Quality Results              ✗  ← 阻断项
```

图例：`✓` 已有 · `?` 部分或位置不明 · `✗` 完全没有

---

## 二、★ 关键发现：对抗审查在**铸造之前**，不是之后

业主问："铸造完后是不是有对抗审查？"

**答案是：宪章把对抗审查放在 `CAST-FREEZE` 之前，而不是之后。**

### 证据 1：§30 把它列为 Freeze 交付物

`Adversarial Review Results` 与 `Blind Reproducibility Results` 并列
出现在"**该 commit 应包含**"的清单里（L1493–1494）。
若它在铸造后做，就不可能出现在铸造那个 commit 里。

### 证据 2：§51 最终愿景的顺序图（L2538–2553）

```text
所有文件坑位被创建
        ↓
每个文件拥有明确 Build Instruction
        ↓
Prompt / Contract / External Facts / Simulation
被反复攻击和校验                      ← 对抗审查在这里
        ↓
独立模型做 Blind Reproducibility
        ↓
最高模型跨层随机抽查
        ↓
整个虚拟工程达到稳定解
        ↓
========================
      CAST FREEZE          ← 铸造在这里
========================
        ↓
大量 Coding Agents 并行领取固定 Work Packets
        ↓
代码注入
```

**对抗审查、盲审、跨层抽查三件事全部发生在 `CAST FREEZE` 上方。**

### 证据 3：§44.7 与审计清单的措辞

§44.7 Feasibility & Review System 与审计架构清单
（L2366–2372）都列了 `adversarial review`，但它们描述的是
**铸造厂自身应具备的子系统**，不是"铸造后的一道工序"。

### 结论

`adversarial review` 的**对象是虚拟工件**
（Prompt / Contract / External Facts / Simulation / Mission Thread），
**不是已注入的代码**。

我此前把它误解为"铸造完再审查代码"。**宪章里没有这道工序。**

★ 但业主的方向感是对的：**确实存在"铸造后"的审查机制，
只是它不叫对抗审查**，见下节。

---

## 三、铸造**之后**真实存在的机制（宪章确实规定了）

宪章把"铸造后"的保障拆成了**四件不同的事**，
它们都不是 `adversarial review`：

### 1. §34 渐进实体化 —— 用替换顺序定位故障

不是"审查代码"，而是**一次只替换一个组件**，
每替换一个就跑相关 Mission Threads。
首次失败点的组件即首要调查对象（L1635）。
**这是顺序设计，不是审查活动。**

### 2. §36 Evidence Pack —— 证据代替"测试绿了"

明令禁止 `Tests Green = Correct`（L1663–1665）。
实现者必须提交 10 类证据（Specification / Contract / Unit Tests /
Mission Thread Tests / Runtime Evidence / Performance Evidence /
Static Analysis / **Independent Source Audit** / Security Evidence /
Traceability）。

★ 其中 `Independent Source Audit` 就是**对已注入源码的独立审计** ——
这是最接近业主所说"铸造完后审查"的东西。

### 3. §37 Gate Challenge Protocol —— 实现者**挑战**验收标准

若 Coding Agent 认为测试或验收本身错误，**不许直接改**，
必须提交 `GATE CHALLENGE`（含 Requirement / Test / 实际行为 /
预期行为 / 冲突原因 / 复现证据 / 建议的上游处理位置），
再由有权角色裁决是 Code 错 / Test 错 / Spec 错 / 外部假设错。

**这是"下游对上游的对抗"**，方向与 `adversarial review` 相反。

### 4. §38 MOLD BREAK —— 下游实现不了时向上爆炸

禁止"先做个能跑的 workaround"，必须停机上报。
见 `.spec/BLIND-TEST-REPORT.md` 中已执行过一次的记录。

### 5. §40 Staleness 自动传播

上游变了，下游的陈旧状态**必须自动标记**，不能靠人记得。

---

## 四、因此现在的阻断项（按优先级）

| # | 缺什么 | 属于 | 为什么阻断 |
| --- | --- | --- | --- |
| 1 | **18 份 Build Instruction** | §17 / §30 | 每份空壳铭牌都指向它们；§20 盲审的对象就是它 |
| 2 | **Adversarial Review Results** | §30 | 未做（我做的两轮盲审是 §20，不是 §44.7） |
| 3 | **Cross-Layer Audit Results** | §30 / §23 | 未做 |
| 4 | **Prompt Quality Results** | §30 / §22 | 14 维评分未产出 |
| 5 | Upstream / Downstream Prompts | §14 / §30 | 未产出 |
| 6 | Resource / Performance Budgets | §29 / §30 | 未产出（我此前已指出 §29 缺时效预算） |

**注意 #2 与 §20 盲审的区别**（我此前混为一谈）：

| | §20 Blind Reproducibility | §44.7 Adversarial Review |
| --- | --- | --- |
| 目的 | 测**模具精度**（多模型能否收敛到同一语义） | 测**工件的抗打击性**（主动找漏洞） |
| 方法 | 互不知晓的模型独立实现，比对结果 | 假定工件有缺陷，主动构造攻击 |
| 产出 | 语义方差 / 三方裁决 | 缺陷清单 + 受影响工件 |
| 我已做 | ✓ 两轮（见 `BLIND-TEST-REPORT.md`） | ✗ |

**已做的部分对抗工作**（散落但未成文）：
- `.spec/MISSION-THREADS.md` 的攻击表（10 条 ATK）
- `tools/attacks/verify_attack_surfaces.py`（4 条攻击的实证）
但这些是**定点攻击**，不是 §30 要求的那份**结果文档**。
