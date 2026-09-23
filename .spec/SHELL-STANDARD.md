# 空壳文件格式标准（SHELL-STANDARD v1）

> 本文件是**四个子智能体的共同施工规范**。
> 目的：让 18 个文件由 4 个不同智能体写出后，看起来像**一个人写的**。
> 依据：宪章 §17（文件坑位 Freeze 前必须存在）、§18（现场铭牌）、§19（Build Packet）。

---

## 一、每个文件必须有的四段

```python
'''
FILE-ID:      FILE-0NN
COMPONENT:    COMP-CN
SPEC:         <依据文档@版本>
ROLE:         一句话：这个文件在系统里干什么
INTENT:       为什么把它单独切成一个文件（不切会怎样）
MUST:         必须做到（可检查的断言）
MUST NOT:     绝不允许（越界或不做的）
INPUT:        从谁拿什么
OUTPUT:       给谁什么
BUILD-INSTRUCTION: .spec/build/FILE-0NN-v1.md
'''

from __future__ import annotations
# ... import


# ═══════════════ 分区标题 ═══════════════
def function_name(args) -> Return:
    """一句话职责。

    详细契约：什么情况下返回什么、什么情况下抛什么。
    """
    raise NotImplementedError("SHELL: FILE-0NN 待注入实现")


# ═══════════════ 冻结的常量 ═══════════════
DEFAULT_X = 0.0
```

---

## 二、硬性规则

### 规则 1：现场铭牌用**模块 docstring**，不用 `# 注释`

宪章 §18 要求文件顶部有铭牌。用 docstring 而**不是** `#` 注释，因为：
docstring 可以 `import` 后用 `__doc__` 读出来，**可被自动审查**；`#` 注释不能。

### 规则 2：函数体**只放一行** `raise NotImplementedError`

```python
    raise NotImplementedError("SHELL: FILE-0NN 待注入实现")
```

**不许**放 `pass`（静默返回 None 会被误当成正常）、
不许放 `...`（会被误当成已实现）、不许放 `return None`（更糟）。

这一行同时是**三个可执行的断言**：
1. 文件真的是空的（调用必炸，不会被误认为已实现）
2. 报错信息带 FILE-ID，一眼知道该填哪个文件
3. 全仓库 grep `NotImplementedError("SHELL:` 即可数出剩余坑位数

### 规则 3：签名必须完整、带类型标注

空壳的价值在于**结构可审查**。`def f(x):` 这种签名等于没写。
每个参数、每个返回值都要有类型标注。

### 规则 4：绝不写实现片段

不许"我先写一半逻辑放着"。不许有 `if`/`for`/`try` 等控制流。
不许调用第三方库做实际计算。
**唯一的例外**：`raise` 语句本身。

#### 例外：`__main__.py` 的入口保护

`harmonica_eval/__main__.py` 末尾**允许**保留：

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

**为什么必须破例**（由 C4 智能体发现并论证）：
这是 `ast.If`，字面上违反规则 4。但删掉它，`python3 -m harmonica_eval`
会**静默什么都不做** —— 连 `NotImplementedError` 都不抛。
于是空壳最重要的断言（"调用必炸"）失效：
一个坏掉的入口会看起来像正常退出。

**判据**：这个 `if` 不实现任何业务逻辑，它只是**运行时的入口开关**。
凡符合此判据的（仅 `__main__.py`、仅此一种形态）允许保留；
其他任何控制流仍一律禁止。

### 规则 5：常量可以是真的

冻结的默认值（阈值、单位、参数名）**应该写真实值**——
它们是设计信息，不是实现。例如：

```python
MAX_CENTS_DEVIATION = 50.0   # 规格：稳定音 ≤50 音分
```

### 规则 6：import 必须是真的

import 语句必须是**最终需要的**那些（不是"先都写上"）。
这使 `import` 本身成为一次结构验证：若某文件 import 了不该 import 的模块，
盲审能立刻发现。例如 `core/` 里出现 `from ..algorithms import ...` 就是违规。

### 规则 7：不要 `pass` 类体

空的 dataclass 用 `...` 或直接列字段。若类真的无成员，用 docstring 说明为何存在。

---

## 三、四个组件的专属约束

### `core/`（C2）

- **禁止** import `host` / `algorithms` / `cockpit`
- **禁止**出现任何算法名（pitch/timing/dynamics 作为算法概念）
  - 例外：端口名 `pitch.reference` 是**数据**名，允许
- 所有端口生成必须**由 `profile.PORTS` 驱动**，不得硬编码端口名列表

### `algorithms/`（C3）

- **禁止** import `core` 内部模块（只能 import `..contract`）
- **禁止**任何"请求生成数据"的调用
- 每个算法必须能独立返回 `AlgorithmResultEnvelope`，包括失败时

### `host/`（C1）

- 全系统**唯一**允许同时 import core + algorithms 的地方
- **禁止**出现 DSP 调用（fft/pyin/...）——C1 不计算任何信号

### `cockpit/`（C4）

- **禁止** import `core` / `algorithms`
- **禁止** import 任何 UI 框架之外的 DSP 库
- UI 框架选择留给实现者，空壳只需声明依赖 contract

---

## 四、命名与注释语言

| 项 | 规则 |
| --- | --- |
| 标识符 | 英文，`snake_case` |
| 注释 / docstring | **中文**（负责人阅读用） |
| 端口 id | `类别.修饰.角色`，全小写，如 `pcm.mapped.practice` |
| 错误码 | `SCREAMING_SNAKE`，英文 |
| 单位 | 一律写在名字或 docstring 里（`_sec` / `_hz` / `_cents`），**不靠猜** |

---

## 五、自检清单（子智能体交付前必须逐条过）

- [ ] 每个函数体只有一行 `raise NotImplementedError("SHELL: FILE-0NN 待注入实现")`
- [ ] 每个函数都有完整类型标注
- [ ] 模块 docstring 含全部 9 个字段（FILE-ID / COMPONENT / SPEC / ROLE / INTENT / MUST / MUST NOT / INPUT / OUTPUT / BUILD-INSTRUCTION）
- [ ] import 列表是最终需要的，且不违反组件专属约束
- [ ] 常量是真实冻结值，不是占位
- [ ] 无 `pass`、无 `...`、无 `return None`、无控制流
- [ ] 每个公开符号都进了 `__all__`（如该文件定义 `__all__`）
- [ ] `python3 -c "import 该模块"` 成功

---

## 六、验证命令（我会在合并时跑）

```bash
# 1. 全部模块可 import（§17）
python3 -c "import harmonica_eval, harmonica_eval.core, ..."

# 2. 空壳完整性：每个函数都该抛 NotImplementedError
python3 tools/verify_shell.py

# 3. 依赖方向：core/ 不得 import algorithms/
python3 tools/verify_layers.py

# 4. 现场铭牌：每个文件都有 FILE-ID
grep -L "FILE-ID:" harmonica_eval/**/*.py
```
