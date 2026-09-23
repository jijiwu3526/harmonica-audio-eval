# .spec/build/ —— Build Instruction 目录

> **当前状态：18 份指令待生成。这是 `CAST-FREEZE` 的阻断项。**

---

## 一、★ 更正：本目录的 README 第一版把顺序写错了

第一版 README 声称：

> "`CAST-FREEZE` 之前**不该**有注入指令"

**这个说法与宪章冲突，已作废。** 三处原文：

**§17（文件坑位在 Freeze 前就应存在）** 列出空壳的"理想状态"：

> - imports 合法；
> - type / interface 合法；
> - stub 可加载；
> - virtual tests 可运行；
> - 文件身份明确；
> - 每个文件已有 File Contract；
> - **每个文件已有 Build Instruction。**

**§30（Freeze 交付物清单）** 明确列出 21 项，其中包含：

> File Skeletons / File Contracts / Upstream Prompts /
> Downstream Prompts / **Build Instructions** / …

**§2540（收敛顺序）** 把 Build Instruction 放在攻击与盲审**之前**：

```text
所有文件坑位被创建
        ↓
每个文件拥有明确 Build Instruction      ← 在这里
        ↓
Prompt / Contract / External Facts / Simulation 被反复攻击和校验
        ↓
独立模型做 Blind Reproducibility
```

**最直接的证据**：§20 的盲审对象写的就是一个 Build Instruction：

> 对同一个 `BUILD-037`，分别交给多个不知道彼此的模型……

若 Build Instruction 在 Freeze 后才写，**§20 就没有可测的对象**。

---

## 二、正确的顺序

| # | 动作 | 产物 |
| --- | --- | --- |
| 1 | 建文件坑位 | 18 个空壳 `.py`（已有） |
| 2 | **写 Build Instruction** | `.spec/build/FILE-0NN-v1.md` × 18 ← **待补** |
| 3 | 攻击与校验 | Prompt/Contract/External Facts/Simulation |
| 4 | 独立盲审 | §20 多模型交叉比对（对象 = Build Instruction） |
| 5 | 打 `CAST-FREEZE-v1.0` | 虚拟世界收敛 |
| 6 | 注入代码 | L3，一次一个文件 |

**为什么 Build Instruction 必须在盲审前写好**：
它就是"给实现者的指令"。若它不存在，盲审者只能去猜实现者会拿到什么；
而 §20 要测的恰恰是**这份指令**能否让多个独立模型收敛到同一理解。

★ 我此前做的两轮盲审因此有**共同的方法缺陷**：
我让审查者只看 `.py` 空壳，而**真实实现者还会拿到 Build Instruction**。
所以我测的是一个**比真实情况更弱的信息集** —— 结论偏悲观，
但也因此发现的问题都是**指令必须回答的问题**（它们现在写进了本目录）。

---

## 三、为什么 18 个文件的铭牌现在就指向这里

每个空壳文件的铭牌都写着：

```text
BUILD-INSTRUCTION: .spec/build/FILE-0NN-v1.md
```

这个引用在写第一版 README 时是**悬空的**，当时我把它辩解为
"指向未来的引用，是已知且被接受的"。

**正确说法是**：它是**待兑现的交付物**。悬空引用在 Freeze 时
必须全部兑现 —— 否则 `CAST-FREEZE-CHECKLIST` 的"零悬空引用"一项不成立。

---

## 四、每份指令的结构（§19 Build Packet 的 11 项要求）

§19 要求一份好的 Build Packet 让**没参与前期设计的新 Agent** 能够：

1. 理解自己是谁
2. 理解自己所在工位
3. 理解文件为什么存在
4. 理解允许修改的范围
5. 知道具体应实现什么
6. 知道哪些依赖可用
7. 知道哪些行为被禁止
8. 知道异常和边界
9. 知道如何测试
10. 知道完成后要提交什么证据
11. **知道何时必须停止并上报，而不是擅自设计**

对应到每份 `FILE-0NN-v1.md` 的结构：

```text
FILE-ID / 目标文件路径
职责与工位（我是谁、上下游是谁）
存在理由（追溯到上层意图 —— §23 跨层审计用）
契约来源（contract.py 的哪些类型、profile.py 的哪些常量）
行为规格（输入 → 输出，含边界与失败语义）
必须满足的不变量（从该文件的 MUST / MUST NOT 抄下来）
禁止事项（该文件专属的越界）
验证方法（怎么证明注入后仍满足虚拟件的保证 —— §35 Real ⊑ Virtual）
必须提交的证据（§36 Evidence Pack）
★ 停止条件（何时不许自己决定、必须上报）
```

**最后一项是 §22 硬失败"Build Instruction 仍要求 Coding Agent
自行做上层设计"的直接对策** —— 这正是我前两轮盲审暴露的核心问题：
实现者被迫自己发明阈值（如抢拍判据）、自己选口径（如 MAD）。

---

## 五、注入纪律

**一次只注入一个文件**，注入后立刻跑该文件的验证。
不要批量注入 —— 批量注入会让失败无法归因。
