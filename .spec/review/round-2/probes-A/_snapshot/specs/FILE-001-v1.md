# FILE-001 — `harmonica_eval/__init__.py`

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/__init__.py`
> 生成依据：`PLAN.md@v2 §四` · `.spec/SHELL-STANDARD.md@v1` · `SPEC.md@v2.1 §1`
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

> ⚠ 本文件的特殊性：**目标文件已经是完整实现，不是空壳。**
> 它是全仓唯一一个"虚拟期就已落地"的文件 —— 因为它只含声明，不含行为，
> 所以不存在"待注入实现"。你的任务是**核验并保持**，不是"写代码"。
> 详见 §4.0。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-001 |
| 所属组件 | **COMP-PKG**（包入口）—— ★ **本身不是组件** |
| 层级 | L2（package surface） |
| 上游 | 任何 `import harmonica_eval` 的使用者（含 C1、C4、测试、外部脚本） |
| 下游 | **无。刻意无。** 本文件不 import 任何东西 |
| 同层邻居 | 无（它是包的第一个执行点） |

**你的权限**：只改本文件。不得修改任何子模块，不得新增子模块，
不得修改 `SPEC.md` / `profile.py` / `contract.py`。

**★ 为什么 COMP-PKG 不是组件**：宪章 §8 定义组件为
「可以独立建立契约的责任单元」。本文件**不建立任何契约**、不拥有行为、
不持有状态 —— 它是包的**标签**，不是包的**部件**。
`COMPONENTS.md` 因此没有把它列为 COMP-C1..C4 之一。
这不是遗漏，是分类正确。

---

## 2 · 这个文件为什么存在

回答一个问题：**「`harmonica_eval` 这个包的公开面是什么？」**

需要一个**可读、可审的落点**。若不放在这里，答案就会散落在
各处的 `import` 惯例里 —— 那时"哪些是公开的"只能靠考古得知，
而考古结论会随代码演化静默漂移。

**删掉它会坏掉什么**：技术上什么都不会坏（Python 允许包无 `__init__` 内容）。
但从 §41「任何代码都能回答为什么存在」的角度，它就是那个**唯一能回答
"包的公开面是什么"的地方**。删掉它 = 这个问题重新变成不可回答。

**它还承担一个结构性职责**：`__init__.py` 是包导入的**第一个执行点**。
在这里 import 任何子模块，都会让每个使用者（包括只想读一个常量的脚本）
付出加载全部组件的代价，并引入 import 顺序与循环依赖的风险。
故本文件的核心设计是**零子模块 import** —— 见 §6 的 INV-001-1。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：
- **无。**

**禁止 import**：
- 任何标准库（连 `typing` 都不需要 —— 见下）
- 任何第三方（`numpy` 等）
- 任何本包内的模块（`contract` / `profile` / `core` / `algorithms` / `host` / `cockpit`）
- 任何相对 import（`from . import x` / `from .contract import y`）

> ★ 这是全仓**唯一**一份"可以 import 的内容为空"的依赖清单。
> 它不是省事，是设计：见 §6 INV-001-1。

**关于 `typing`**：目标文件里的类型标注写的是 `__all__: list[str]`，
用的是**内置泛型**（PEP 585，Python 3.9+）。
本项目 Python 版本为 3.13，故**不需要** `from typing import List`。
不得为了"兼容旧版本"引入 `typing`。

---

## 4 · 你要实现什么（行为规格）

### 4.0 ★ 先读这段：本文件已实现，你要做的是核验

目标文件当前**已经是完整实现**（65 行，含 docstring）。
它没有 `raise NotImplementedError`，也不该有 ——
它只含**声明**，而声明**在虚拟期就应该是最终的**。

你要做的是**逐项核验 §4.1–4.3 的四样东西是否与本文件一致**，
并在**不一致时**按本文件修正。**不要"重写"或"补全"任何东西。**

**若你发现本文件与 §4 冲突** → 不要自行裁决，转 §10。

---

### 4.1 模块级字面量：`__version__`（**必须逐字存在**，审查者会 grep）

```python
__version__ = "0.1.0"
```

- **值**：语义化版本字符串，当前 `"0.1.0"`
- **★ 它不是数据面身份**。数据面身份是 `profile.PROFILE_VERSION`。
  两者**必须允许不同步**：包可以升级到 `0.2.0` 而数据格式仍是 `v0.1`。
  把它们绑在一起会让"改个错别字"变成"数据格式变更"。
- **必须有 docstring**，且必须写明上面这条区分。
- **不得**从别处计算或 import 它（本文件不 import 任何东西）。

### 4.2 `__all__`（**刻意为空**）

```python
__all__: list[str] = []
```

- **值必须为空列表**，且**必须带类型标注 `list[str]`**（不是 `tuple`）。
- **★ 为什么为空**：本文件不 import 任何子模块，所以
  `contract` / `core` 等**不是本模块的属性**。
  把它们列进 `__all__` 会让 `from harmonica_eval import *` 抛

  ```
  AttributeError: module 'harmonica_eval' has no attribute 'core'
  ```

  —— 这是**假声明**，比不声明更糟。
  （★ 本条由 C4 智能体盲审实测发现，是本仓第 12 项检查的由来。）

- **必须有 docstring**，且必须写明上述失败模式。

### 4.3 `PUBLIC_SUBMODULES`（文档性常量，**必须逐字存在**）

```python
PUBLIC_SUBMODULES: tuple[str, ...] = (
    "contract", "profile", "core", "algorithms", "host", "cockpit",
)
```

- **类型必须是 `tuple[str, ...]`**，不是 `list`：它表达的是**冻结的设计事实**，
  不是运行期可变集合。用 tuple 让"改它"成为一个需要显式动作的决定。
- **顺序**：必须与本清单一致（`contract` 在前，`cockpit` 在末）。
  该顺序来自 `PLAN.md §四` 的分层叙述。
- **★ 必须包含 `cockpit`，即使它可缺席。**
  理由必须写进 docstring：「公开面」描述的是**设计上的一等公民**，
  不是「当前磁盘上存在什么」。缺席与否是**实现形态**，不是**接口形态**。
  （不变量 F 说 cockpit 可缺席；这两件事不矛盾，见 §6 INV-001-3。）
- **它是文档性常量，不是 import 指令** —— 这必须写进 docstring，
  否则读者会以为它触发了加载，从而误判它违反了 §6 INV-001-1。

### 4.4 模块 docstring：必须存在的六个段落

目标文件的 docstring 使用固定的小节名。**逐字保留**：

| 小节 | 必须写明的内容 |
| --- | --- |
| `FILE-ID` | `FILE-001` |
| `COMPONENT` | `COMP-PKG（包入口，本身不是组件）` |
| `SPEC` | 上游工件与版本 |
| `ROLE` | 一句话：包出口，声明版本与公开面（6 个子模块） |
| `INTENT` | 为什么需要一个落点 + 为什么刻意零 import |
| `MUST` / `MUST NOT` | 与 §6 的不变量表**逐条对应** |
| `INPUT` | `（无）` |
| `OUTPUT` | `__version__ · __all__ · PUBLIC_SUBMODULES` |
| `BUILD-INSTRUCTION` | `.spec/build/FILE-001-v1.md` |

---

## 5 · 失败语义

**本文件不产生任何运行期失败路径。** 它不执行逻辑、不接收输入、不抛异常。

| 情形 | 行为 |
| --- | --- |
| `import harmonica_eval` | 必须**无条件成功**，不依赖任何子模块是否存在 |
| 某个子模块文件缺失 | **不得**影响 `import harmonica_eval` |
| 某个子模块 import 报错 | **不得**影响 `import harmonica_eval` |
| Python < 3.9 | 不支持（`list[str]` 会失败）。本项目锁定 3.13，不处理 |

**★ 上表第 2、3 行是重点**：本文件存在的结构性价值之一，
就是**让包的导入在组件残缺时仍然成功**。若实现后
`import harmonica_eval` 因某个子模块坏了而失败，那是**严重回归**。

★ 宪章 §5.6：禁止静默降级。本文件没有可降级的行为 —— 它只有声明。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-001-1 | **包导入期零子模块加载**：`import harmonica_eval` 后，`sys.modules` 中不出现 `harmonica_eval.contract` / `.profile` / `.core` / `.algorithms` / `.host` / `.cockpit` | 见 §8 判据 1 |
| INV-001-2 | `__all__` **恰好为空**，且类型是 `list` | `assert harmonica_eval.__all__ == []` 且 `type(...) is list` |
| INV-001-3 | `PUBLIC_SUBMODULES` **恰好含 6 个名字且含 `cockpit`**，类型是 `tuple` | `assert isinstance(PUBLIC_SUBMODULES, tuple)` 且 `"cockpit" in PUBLIC_SUBMODULES` |
| INV-001-4 | 本文件**不含**任何 `import` 语句、函数定义、类定义、控制流 | §8 判据 2（AST 级） |
| INV-001-5 | `from harmonica_eval import *` **不得抛异常** | §8 判据 3 |
| INV-001-6 | `__version__` 是 `str`，且**与 `profile.PROFILE_VERSION` 无耦合**（不同名、不同源、不同值允许不同） | grep 确认本文件不出现 `PROFILE_VERSION` |

---

## 7 · 边界（明确不做）

- **不 re-export 组件符号**（例如 `from .contract import HostContract`）。
  那会把包入口变成**隐藏的装配点**，并立刻违反 INV-001-1。
- **不定义 `__getattr__` 做懒加载**。它能让 `harmonica_eval.core` 看起来可用，
  但代价是：导入行为变成隐式的、`__all__` 与属性不再一致、
  且 INV-001-1 无法再用简单断言验证。**本项目不需要这个便利。**
- **不定义函数 / 类 / 控制流**（连 `if` 都不要）。
- **不加 `__author__` / `__license__` 等元数据**。未被要求。
- **不做 Python 版本兼容分支**。
- 若你发现"不做某个东西就实现不了" → **不要做**，转 §10。

---

## 8 · 怎么验证你写对了

```bash
# 判据 1（INV-001-1）：包导入期零子模块加载
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python3 -c "
import sys, harmonica_eval
leaked = [m for m in sys.modules if m.startswith('harmonica_eval.')]
assert not leaked, f'包导入期泄漏了子模块: {leaked}'
print('✅ INV-001-1 通过')
"

# 判据 2（INV-001-4）：AST 级确认无 import / 无函数 / 无类 / 无控制流
python3 -c "
import ast
t = ast.parse(open('harmonica_eval/__init__.py', encoding='utf-8').read())
banned = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef,
          ast.ClassDef, ast.If, ast.For, ast.While, ast.Try, ast.With)
bad = [type(n).__name__ for n in ast.walk(t) if isinstance(n, banned)]
assert not bad, f'出现禁止的节点: {bad}'
print('✅ INV-001-4 通过')
"

# 判据 3（INV-001-5）：star-import 不得抛异常
python3 -c "
exec('from harmonica_eval import *')
print('✅ INV-001-5 通过')
"

# 判据 4（INV-001-2 / 001-3）：导出面与公开模块清单
python3 -c "
import harmonica_eval as h
assert h.__all__ == [] and type(h.__all__) is list, h.__all__
assert isinstance(h.PUBLIC_SUBMODULES, tuple), type(h.PUBLIC_SUBMODULES)
assert len(h.PUBLIC_SUBMODULES) == 6, h.PUBLIC_SUBMODULES
assert 'cockpit' in h.PUBLIC_SUBMODULES
print('✅ INV-001-2 / INV-001-3 通过')
"

# 判据 5（INV-001-6）：与数据面身份无耦合
! grep -q "PROFILE_VERSION" harmonica_eval/__init__.py && echo "✅ INV-001-6 通过"

# 判据 6：全仓既有检查仍通过（本文件不得引入任何违规）
python3 tools/verify_shell.py
```

**验收判据**（可机械判定，非"看起来对"）：
- [ ] 判据 1 通过 —— 且这是**本文件最重要的一条**，它是本文件存在的理由
- [ ] 判据 2 通过 —— 无任何禁止的 AST 节点
- [ ] 判据 3 通过 —— star-import 不抛 `AttributeError`
- [ ] 判据 4 通过 —— `__all__` 空、`PUBLIC_SUBMODULES` 是 6 元 tuple
- [ ] 判据 5 通过 —— 不出现 `PROFILE_VERSION`
- [ ] 判据 6 通过 —— `tools/verify_shell.py` 结论为「通过」

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] 上述 6 条判据的**完整命令输出**（不是"我跑过了"）
- [ ] `git diff --stat harmonica_eval/__init__.py`
      —— ★ 若本文件已正确，diff **应为空**。空 diff 是**合格**结果，不是没干活。
- [ ] 若做了任何修改：逐条说明改了什么、依据本文件哪一节

> ★ 特别说明：本文件的"完成"很可能等于**零改动**。
> 不要为了"看起来干了活"而修改它。§7 已明确禁止为它增加任何东西。

---

## 10 · ★ 何时必须停止并上报（§22 硬失败对策）

**以下情况必须停止，提交 `MOLD BREAK`，不得自行设计：**

1. 你发现要满足 §4 就**必须** import 某个子模块
   （例如为了让 `PUBLIC_SUBMODULES` "真的可用"）
2. §4 与目标文件现有内容**冲突**
3. 你认为 §6 的某条不变量**是错的**（例如认为 `__all__` 不该为空）
4. 你需要的依赖**不在 §3 清单里** —— 注意 §3 是**空清单**，
   所以任何 import 都属于本条
5. §4 的行为规格不足以确定唯一实现

**上报格式**（宪章 §37 Gate Challenge）：
```
GATE CHALLENGE
- 相关 Requirement：
- 相关 Build Instruction 章节：
- 实际需要 vs 规格给出：
- 为什么冲突：
- 复现证据：
- 建议的上游处理位置：
```

**绝对禁止**：
- 先加一个"能跑的 workaround"，以后再说（§38 明文禁止）
- 为了让 `__all__` "更有用"而往里填子模块名
- 静默缩小范围（"这个常量我先不写"）

---

## 附：本文件的冻结常量速查

| 常量 | 值 | 来源 |
| --- | --- | --- |
| `__version__` | `"0.1.0"` | 本文件 §4.1 |
| `__all__` | `[]`（`list[str]`） | 本文件 §4.2 |
| `PUBLIC_SUBMODULES` | 6 元 tuple，含 `cockpit` | `PLAN.md §四` | `本文件 §4.3` |
| 数据面身份（**不是**本文件的值） | `profile.PROFILE_VERSION` | `profile.py` |
