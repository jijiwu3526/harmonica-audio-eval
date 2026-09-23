# 空壳铸造 · 收敛报告

> 面向：项目负责人（L0）
> 用途：一次读完就知道「空壳造完了没有、能不能冻结、有什么问题」
> 状态：**进行中**

---

## 一、一句话结论

**4 个子智能体已派出，正在填 18 个文件的模具。**
契约层（`contract.py` / `profile.py`）已冻结并通过自检，其中**盲审自测抓到并修复了 6 处静默错位风险**。

---

## 二、已经完成的部分

| # | 产物 | 说明 |
| --- | --- | --- |
| 1 | `harmonica_eval/contract.py` | 24 个公开符号、11 个错误码、10 个禁止方法名 |
| 2 | `harmonica_eval/profile.py` | 11 个端口的**封闭清单** + import 时自检 |
| 3 | `.spec/SHELL-STANDARD.md` | 空壳格式标准（9 字段铭牌 + `NotImplementedError` 协议） |
| 4 | `.spec/CAST-FREEZE-CHECKLIST.md` | 7 段冻结检查，含 §20 盲审方法 |
| 5 | `.spec/BLIND-REVIEW-PROTOCOL.md` | 盲审协议（白名单/黑名单/三个问题） |
| 6 | `.spec/prompts/COMP-*/downstream.md` | 4 份下行视图（生成指令） |
| 7 | `tools/verify_shell.py` | 机械验证：结构 / 纯净度 / 依赖方向 / 禁名单 |

---

## 三、★ 过程中的重要发现：6 处静默错位风险

**这是本轮最有价值的产出**，因为它抓到的是「不会报错、只会算错」的缺陷。

### 问题

`dimensions=('frame', 'field')` 这种声明是**假的严谨**：
它说了"第二维是字段"，但**没说字段是什么、什么顺序**。

后果：两个实现者会写出不同的内存布局，读出来的 `f0_hz` 可能是 `voiced`——
**而且不会报错，只会静默算错。**

### 修法

新增 `contract.FIELD_LAYOUTS`，冻结全部多维端口的字段顺序：

```text
warp_path  → (reference_frame, practice_frame)
pitch.*    → (f0_hz, voiced, confidence)
notes.*    → (onset_sec, f0_hz, rms)
chroma.*   → 12 音级，bin 0 = C     ← 起点同样有歧义，一并冻结
```

并在 `profile.assert_profile_integrity()` 里加了断言，配**负向测试**：

```text
✅ 负向测试：故意把 field_names 顺序颠倒
   → 被拦截：「端口 pitch.reference 的 field_names=('voiced','f0_hz','confidence')
              与契约定义的 ('f0_hz','voiced','confidence') 不一致」
```

**这 6 条不是假想，是我在派工前自己做了一轮盲审自测真实抓到的。**
若等到 4 个智能体各自写完再发现，就是 4 份返工。

---

## 四、顺带修掉的两个隐患

| # | 隐患 | 风险 | 处理 |
| --- | --- | --- | --- |
| 1 | `harmonica_eval/contract/` 残留目录（只剩 pycache） | **namespace package 会让 `import harmonica_eval.contract` 解析到目录而非文件**，静默 import 到旧代码 | 已删除 |
| 2 | `PortSpec` 字段顺序违反 dataclass 规则 | import 直接崩 | 已修（把带默认值的字段移到最后） |

---

## 五、派工情况

| 组件 | 智能体 | 状态 |
| --- | --- | --- |
| C2 core（6 文件） | 第 1 个**失败**（未产出）→ 已重派 | 🔄 进行中 |
| C3 algorithms（4 文件） | 运行中 | 🔄 进行中 |
| C1 host（2 文件） | 运行中 | 🔄 进行中 |
| C4 cockpit + 入口（4 文件） | 运行中 | 🔄 进行中 |

**C2 首派失败的原因**：未产出任何文件即终止。已重派并强调「先读完所有必读文件再动手」。
其余三个智能体已收到契约更新通知（`FIELD_LAYOUTS`），并被要求**引用而非重抄**字段列表。

---

## 六、进度

```text
文件：2 / 18   ← 契约层与配置（地基，已冻结）
      ██░░░░░░░░░░░░░░░░

阶段：
  [✅] 冻结接口
  [✅] 写 4 份 downstream.md
  [🔄] 派工填空壳          ← 当前
  [ ] 合并 + 机械验证
  [ ] 独立盲审
  [ ] CAST-FREEZE-v1.0
  [ ] 注入实现
```

---

## 七、下一步

1. 收齐 4 个组件的空壳（18 文件）
2. 跑 `tools/verify_shell.py`：结构 / 纯净度 / 依赖方向 / 禁名单
3. 派**独立盲审智能体**（按协议：只给空壳 + 契约，不给任何设计文档）
4. 盲审通过 → 打 `tag CAST-FREEZE-v1.0`
5. 逐个生成 Build Instruction → 注入实现

**若盲审发现歧义 → `MOLD BREAK`**：回虚拟世界修，不带病开铸。

---

## 八、已知缺口（不隐瞒）

| # | 缺口 | 现状 |
| --- | --- | --- |
| 1 | 算法死循环会卡住流程 | v0.1 无超时机制，已写入 `ErrorCode.ALGORITHM_TIMEOUT` 但标注未实现 |
| 2 | C2 首派智能体失败 | 已重派，暂无影响 |
| 3 | 数据集只有 1 首 | 剩 9 首待批量建（等你听完第 1 首） |
| 4 | 对齐精度未用真实音乐验证 | 只用合成 chroma 测过规模 |
| 5 | 手机端未测 | 本轮不做（Mac 先行） |
