# CAST-FREEZE 检查清单（v1.0）

> 依据：宪章 §30（CAST FREEZE 是一次 git 事件）、§31（Freeze 前零未决）、
> §20（Blind Independent Reproducibility Test）、§35（Real ⊑ Virtual）、
> §43（冻结行为不冻结结构）、§47.10（禁止提前冻结）。
>
> **本清单必须在打 tag 前逐条通过。任一未过 → 不打 tag。**
> 打 tag 命令：`git tag -a CAST-FREEZE-v1.0 -m "..."`

---

## A. 结构完整（§17 文件坑位必须存在）

- [ ] 18 个文件全部存在
- [ ] 每个文件有 `FILE-ID` 现场铭牌（§18）
- [ ] 铭牌含全部字段（ROLE / INTENT / MUST / MUST NOT / INPUT / OUTPUT）
- [ ] 全部模块可 `import`（Python 层面无语法/循环依赖错误）

**验证**：`python3 tools/verify_shell.py`

---

## B. 空壳纯净（本轮只造空壳）

- [ ] 每个函数体只有 `raise NotImplementedError("SHELL: FILE-0NN 待注入实现")`
- [ ] 无 `pass` / `...` / `return None`
- [ ] 无控制流（if/for/try/while）
- [ ] 无第三方算法调用

**验证**：`tools/verify_shell.py` 的「空壳纯净度」段

---

## C. 依赖方向（可自动验证的结构事实）

- [ ] `core/` 未 import `host` / `algorithms` / `cockpit`
- [ ] `algorithms/` 未 import `core` / `host` / `cockpit`
- [ ] `cockpit/` 未 import `core` / `algorithms` / `host`
- [ ] `contract.py` / `profile.py` 未 import 任何组件
- [ ] `host/` 是唯一允许跨界的模块

**验证**：`tools/verify_shell.py` 的「依赖方向」段

**为什么这条最重要**：只要 `core/` 不 import `algorithms/`，
「换算法不改核心」就是**机器可验证的事实**，不是靠自觉维持的纪律。

---

## D. 边界约束（负责人裁定，不可推翻）

- [ ] **Core 预生成**：`build_surface()` 是一次性预生成，无惰性求值
- [ ] **端口清单封闭**：由 `profile.PORTS` 驱动，无硬编码、无动态扩展
- [ ] **`read()` 无副作用**：不触发计算、不失败于"算不出来"
- [ ] **兼容性检查单向**：只判断有无，**绝不**反推生成
- [ ] **无存储后端**：未引入 memmap / LRU / HDF5 / Zarr（本轮不做）
- [ ] **无算法概念泄漏进 core**：未定义 `FORBIDDEN_OPERATIONS` 中任何方法
- [ ] **两轴分离**：节奏类输出声明 `TimelineBasis.REFERENCE`
- [ ] **C4 可缺席**：`__main__.py` 未 import `cockpit`

---

## E. 契约一致（§31 零未决）

- [ ] `contract.py` 的全部类型被下游正确引用（无孤岛）
- [ ] `profile.PORTS` 的 12 个端口都有 `produced_by` 指向真实模块
- [ ] `CORE_REQUIRED_PORTS` 在 `profile.PORTS` 中全部存在（import 时已自检）
- [ ] `algorithms.ALGORITHMS` 的 `required_ports` 都是 `profile.PORTS` 子集
- [ ] **不存在任何 TODO / FIXME / 未决标记**

**验证**：`grep -rn "TODO\|FIXME\|XXX\|待定" harmonica_eval/`

---

## F. 独立盲审（§20 Blind Independent Reproducibility Test）

### F-0 ★ 方法本身必须先正确（我第一版做错了）

**§20 的原文要求**（L1080–1114）：

> 对同一个 BUILD-037，分别交给**多个**：不知道彼此、没有参与前序设计、
> 不共享历史 conversation 的合格模型。
> 比较**它们**对以下内容的理解：目标 / 边界 / 输入输出 / 状态 / 错误语义 /
> 依赖 / 测试计划 / 不可修改事项 / 实现策略的必要约束。
> 不要求代码一样。要求：**语义高度收敛。**

**我第一版的做法是错的**：派了**一个**审查者写一份"有没有歧义"的报告。

为什么错：一个模型说"有歧义"是**主观意见**；
两个模型给出**互相冲突但都合理**的读法，才是**客观证据**。
只有一个审查者时，"方差"这个量根本不存在。

**正确做法**：
- 至少 **2 个不同模型**，每个可重复多次
- 互不知情、无共享上下文、未参与设计
- 给**同一批被迫做出确定选择的问题**（不问"你觉得有歧义吗"——模型会迎合）
- **机械比对**它们的答案，分歧即缺陷

> ⚠ 实测教训：`workflow` 里 `deepseek` 的 3 次全部返回 null，
> 只拿到 `ling` 一个模型的 3 次重复。
> **同一模型跑 3 次不算多个模型** —— 它的错误是相关的，
> 3 次一致说明不了语义收敛。必须换用真正不同的模型补齐。

### F-1 三分类判定（不是"通过/不通过"）

§20 要求按**情况**判定，而非打分：

| 情况 | 判据 | 结论 | 动作 |
| --- | --- | --- | --- |
| **A** | 多个模型出现**合理但互相冲突**的理解 | `MOLD AMBIGUITY` | **不得**归因于"模型风格不同"→ 修模具 |
| **B** | 多个独立模型**都认为无法实现** | `MOLD INFEASIBILITY` | 向上回传，改设计或改意图 |
| **C** | 语义理解稳定，实现方式不同 | `Semantic Variance: Low`<br>`Implementation Variance: Allowed` | **理想状态**，可冻结 |

§22 补充：**「Blind Reproducibility 出现重大语义分叉」属硬失败**，
不能靠其他维度的高分补偿。

- [ ] 已用 ≥2 个**不同模型**执行（不是同一模型重复）
- [ ] 审查者互不知情、未参与设计、无共享上下文
- [ ] 逐条机械比对了答案，分叉点已列出
- [ ] 判定落在情况 A / B / C 三者之一
- [ ] **情况 A 或 B ⇒ 不打 tag，走 `MOLD BREAK`**

---

## F-2 ★ Mission Threads 对抗审查（§11）

**§11 原文**：

> 最高层模型不应主要阅读 10 万行代码，也不应只看静态方框图。
> **它应围绕端到端任务链攻击系统。**
>
> 顶层模型真正应该回答：
> **在世界状态发生变化时，这张虚拟图仍然能否完成 Mission？**

**我此前漏掉的一层**：我在文档里反复提"Mission Thread"，
**却从未真正写出过一条**。方框图只能证明连接关系存在，
证明不了"世界不配合时还能不能走完"。

- [ ] `.spec/MISSION-THREADS.md` 存在，且覆盖正常路径 + 世界异常路径
- [ ] 每条 MT 有**可判定的通过判据**
- [ ] 每条 MT 有**负向断言**（必须不发生的事）
- [ ] 反方攻击清单 ≥10 条，每条都被某条 MT 或机械检查覆盖
- [ ] MT 覆盖全部组件契约边界
- [ ] 已知缺口（如 MT-006 算法死循环）如实记录，**不假装能通过**

---

## G. 证据与可复现

- [ ] 所有实测脚本有固定输入、无随机性
- [ ] `data/out/` 下的 SPIKE 结果已提交
- [ ] 文档间无矛盾（`SPEC.md` / `COMPONENTS.md` / `CONTRACTS.md` / `PLAN.md`）
- [ ] git 工作区干净（无未提交改动）

---

## 打 tag 前最后确认

```bash
# 全部检查
python3 tools/verify_shell.py

# 无未决标记
grep -rn "TODO\|FIXME" harmonica_eval/ || echo "✅ 无未决标记"

# 工作区干净
git status --porcelain

# 打 tag（仅当以上全过）
git tag -a CAST-FREEZE-v1.0 -m "空壳冻结：18 文件，12 端口封闭清单，契约全冻结"
```

---

## 冻结之后意味着什么

| 冻结的东西 | 含义 |
| --- | --- |
| **接口行为** | §43：冻结行为，不冻结结构。实现可重组，只要行为不变 |
| **端口清单** | 12 个端口封闭。新增端口 = 破坏冻结（需 `MOLD BREAK`） |
| **依赖方向** | 可自动检查，违反即驳回 |
| **不冻结的东西** | 函数内部实现方式、数据结构的物理布局、UI 框架选择、缓存策略 |

**下一步**：派 L3 智能体按 `.spec/build/FILE-0NN-v1.md` 逐个注入实现，
每个文件注入后跑 §35 检查（`Real ⊑ Virtual`：真实件必须仍满足虚拟件的全部保证）。
