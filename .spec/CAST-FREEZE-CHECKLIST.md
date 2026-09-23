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
- [ ] `profile.PORTS` 的 11 个端口都有 `produced_by` 指向真实模块
- [ ] `CORE_REQUIRED_PORTS` 在 `profile.PORTS` 中全部存在（import 时已自检）
- [ ] `algorithms.ALGORITHMS` 的 `required_ports` 都是 `profile.PORTS` 子集
- [ ] **不存在任何 TODO / FIXME / 未决标记**

**验证**：`grep -rn "TODO\|FIXME\|XXX\|待定" harmonica_eval/`

---

## F. 独立盲审（§20 Blind Independent Reproducibility Test）

**方法**：派一个**未参与设计**的智能体，只给它：
- 冻结的契约（`contract.py` / `profile.py`）
- 空壳文件

**不给**：`upstream.md` / `downstream.md` / `PLAN.md` / 本清单 / 任何设计意图说明。

**问它三个问题**：

1. 你能从这个空壳推出每个文件要实现什么吗？哪里推不出来？
2. 有没有哪个地方存在**两种合理解读**？（即签名有歧义）
3. 如果你要实现它，你会**缺少什么信息**？

**通过判据**：没有"推不出来"、没有"两种合理解读"、没有"缺少关键信息"。
**若发现歧义 → `MOLD BREAK`，回到虚拟世界改设计，不带病开铸。**

- [ ] 盲审已执行
- [ ] 盲审未发现歧义（或已修正并复审）

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
git tag -a CAST-FREEZE-v1.0 -m "空壳冻结：18 文件，11 端口封闭清单，契约全冻结"
```

---

## 冻结之后意味着什么

| 冻结的东西 | 含义 |
| --- | --- |
| **接口行为** | §43：冻结行为，不冻结结构。实现可重组，只要行为不变 |
| **端口清单** | 11 个端口封闭。新增端口 = 破坏冻结（需 `MOLD BREAK`） |
| **依赖方向** | 可自动检查，违反即驳回 |
| **不冻结的东西** | 函数内部实现方式、数据结构的物理布局、UI 框架选择、缓存策略 |

**下一步**：派 L3 智能体按 `.spec/build/FILE-0NN-v1.md` 逐个注入实现，
每个文件注入后跑 §35 检查（`Real ⊑ Virtual`：真实件必须仍满足虚拟件的全部保证）。
