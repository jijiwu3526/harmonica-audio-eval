# FILE-300 — harmonica_eval/host/__init__.py

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/host/__init__.py`
> 生成依据：`contract.py`（`HostContract` / `UiProjectionPort`）·
> `PLAN.md@v2 §四/§五` · `COMPONENTS.md@v2 §3 COMP-C1` ·
> `harmonica_eval/__init__.py`（`PUBLIC_SUBMODULES`）· `.spec/BLIND-TEST-REPORT.md`（G8）
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-300 |
| 所属组件 | COMP-C1 Framework / Host |
| 层级 | L3（symbol / implementation） |
| 上游 | 任何 `import harmonica_eval.host` / `from harmonica_eval.host import app` 的调用方（`__main__.py`、`cockpit`、测试） |
| 下游 | 不调用任何模块；只把 `app`（FILE-301）声明为公开面 |
| 同层邻居 | `app.py`（FILE-301） |

**你的权限**：只实现本文件。不得修改 `app.py`、`contract.py`、`profile.py`、
`algorithms/`、`core/`，不得新增公开符号，不得新增 import。

**★ 本文件的特殊性（先读这一条，再动手）**：
本文件是空壳期**已经终态**的产物 —— 它只声明公开面，**不含任何函数或类**，
因此**没有可注入的函数体**。你的工作不是"写实现"，而是：

1. 逐字确认 §4 的四条行为仍然成立；
2. **保持文件字节不变**（除 §10 允许的上报外不得改动一行）；
3. 提交 §9 的"未改动证明"。

"给这个文件加点东西"是本文件最常见、也最严重的越界（见 §7）。

---

## 2 · 这个文件为什么存在

它回答一个没有它就只能靠约定回答的问题：**「C1 对外是什么？」**

`harmonica_eval` 的根出口 `__init__.py`（FILE-001）刻意**不 import 任何子模块**，
并用 `PUBLIC_SUBMODULES` 声明"6 个子模块属于公开面"。到了 C1 这一层，
`harmonica_eval.host` 就是那个公开子模块的**包出口**：它必须能让
`from harmonica_eval.host import app` 成为稳定契约，而不是依赖"磁盘上恰好有个 app.py"。

同时它是「**全系统只有 C1 同时依赖 core 与 algorithms**」这条装配约束的
**可读落点与机械检查锚点**：`tools/verify_shell.py` 的⑤「依赖方向」段
对 `core/` `algorithms/` `cockpit/` 设了禁止清单，而 `host/` 不在其中 ——
本文件的 docstring 就是"为什么 host 是唯一例外"的书面依据。

**删掉它会坏掉什么**（具体，不是"不完整"）：

- `from harmonica_eval.host import *` 的公开面消失（`__all__` 是唯一来源）；
- 文件身份（`FILE-ID: FILE-300` 现场铭牌）消失，
  `tools/verify_shell.py` ①「文件坑位」与③「现场铭牌」立刻报错；
- `harmonica_eval.host` 会退化成**命名空间包**（namespace package）：
  `import harmonica_eval.host` 仍能成功，但"这个包里有什么"再也无处可读 ——
  这类"不报错、只丢失声明"的退化正是本仓反复设卡的对象。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：

- Python 标准库：**无**
- 第三方：**无**
- 本包内：**无**

即：**本文件最终 import 数量必须恰好为 0。**

**禁止 import**：

- `from . import app` / `from .app import HostApp` —— 这会让包导入期就加载 C2/C3 装配
  （见 §4 的 E3 行为条款）
- `from ..contract import ...` / 任何 re-export（会让包出口变成隐藏装配点）
- `numpy` / 任何第三方库
- 任何不在上面清单里的东西（清单为空，故即"任何 import"）

> ★ 依赖清单是**闭集**：上面一行"可以"是穷举，不是举例。
> 若你认为必须 import 某个东西才能完成本文件 → 不要写，转 §10。

---

## 4 · 你要实现什么（行为规格）

本文件的**全部**模块级内容被冻结为三样：模块 docstring、`from __future__ import annotations`、
`__all__`。公开符号只有一个。

### 4.1 `__all__`（唯一公开符号）

- **类型/形状**：`list[str]`
- **取值**：`["app"]` —— 恰好 1 个元素，元素为字符串 `"app"`，**不是** `("app",)`
- **语义**：它是"本包对外承诺的公开面"的**唯一权威**。
  新增/删除元素 = 公开面变更，不是实现细节。
- **边界**：不得为 `None`、不得为空 `[]`、不得含重复项、不得含 `host` 以外的前缀
  （如 `"harmonica_eval.host.app"`）。

**由 `__all__` 决定的可观察行为**（三条都必须成立，且在 §8 可机械验证）：

| 编号 | 表达式 | 冻结结果 |
| --- | --- | --- |
| E1 | `import harmonica_eval.host as h; h.__all__` | `["app"]`（list） |
| E2 | `import harmonica_eval.host` 之后 `hasattr(h, "app")` | `False`（本文件不 import `app`，故 `app` 不是包属性） |
| E3 | `from harmonica_eval.host import app` | 成功，`app.__name__ == "harmonica_eval.host.app"` |
| E4 | `from harmonica_eval.host import *` | 绑定名 `app`，其值为**子模块** `harmonica_eval.host.app` |

> E4 是 Python 语言对 `__all__` 中**子模块名**的规定行为（星号导入会按需 import
> 该子模块），**不是**本文件写出来的效果。因此 E4 成立**不需要**在
> `__init__.py` 里加 `from . import app` —— 加了反而破坏 E2 并把
> C2/C3 的装配拖进包导入期。这是本文件唯一的"反直觉点"，见 §10-2。

### 4.2 除 `__all__` 外不得有第二个模块级符号

- 不得定义函数、类、常量、类型别名、`if` / `try` 等任何控制流。
- 不得新增 `__version__`（版本属于根包 `harmonica_eval.__init__`）。
- 不得新增 `PUBLIC_SUBMODULES`（根包才有；`host` 的公开面就是 `__all__`）。
- 模块 docstring 是**规范文本**（它写明 C1 的 MUST / MUST NOT 与装配唯一性），
  必须逐字保留；不得改写、不得截断。

### 4.3 空值 / 缺失 / 边界

- 若 `app.py` 不存在：`import harmonica_eval.host` 仍成功（E1/E2 不变），
  只有 E3/E4 抛 `ModuleNotFoundError`。**这是正确行为**，不得用
  `try/except ImportError` 把它变成静默通过。
- 若 `app.py` 自身 import 失败：E3/E4 抛出**原样异常**，不得吞、不得降级。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| `app.py` 缺失或 import 失败 | 显式失败，不降级 | E3/E4 抛 `ModuleNotFoundError` / 原异常 |
| 有人试图"修好"E4 而加 import | **禁止**（见 §7） | 转 §10 上报 |
| 任何人新增公开符号 | **禁止** | 转 §10 上报 |

★ 禁止静默降级（宪章 §5.6）：**不得**用兜底 import、不得用 `__getattr__`
伪造 `app`、不得让 `__all__` 与实际磁盘状态"自动同步"。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-300-1 | `__all__ == ["app"]`，类型为 `list` | §8 命令 ①② |
| INV-300-2 | 文件内 `import` / `from ... import` 数量 **恰好为 0** | §8 命令 ③（AST 计数） |
| INV-300-3 | 模块级符号集合 ⊆ `{docstring, __all__, __annotations__/__future__}`，无 `def` / `class` / `Assign`（除 `__all__`） | §8 命令 ③ |
| INV-300-4 | `import harmonica_eval.host` **不加载** `harmonica_eval.host.app` | §8 命令 ②（`sys.modules`） |
| INV-300-5 | 不 re-export `host.app` 之外的名字（`HostApp` / `build_default_app` / `MAX_PROJECTION_POINTS` / 任何 contract 符号） | §8 命令 ④（属性检查） |
| INV-300-6 | 现场铭牌 `FILE-ID: FILE-300` 存在且唯一 | §8 命令 ⑤ |
| INV-300-7 | 注入期本文件内容**逐字节不变** | `sha256sum` 前后比对（§9） |

---

## 7 · 边界（明确不做）

- **不**在这里实现或声明 `HostApp` / `build_default_app`（属于 `app.py`，FILE-301）
- **不**在这里 re-export `contract` / `core` / `algorithms` 的任何符号
- **不**为了"让 `from ... import *` 更稳"而 import `app`
- **不**加日志、`__getattr__`、`__dir__`、兼容分支、"以后可能有用"的占位
- **不**把 `host` 改成命名空间包（即不得删除本文件）
- **不**在此处定义 `__version__` / `__author__` / 任何元数据
- 若你发现"不加某样东西就实现不了" → **不要加**，转 §10

---

## 8 · 怎么验证你写对了

```bash
# ① 公开面冻结
python3 -c "import harmonica_eval.host as h; assert h.__all__ == ['app'], h.__all__; print('① OK', h.__all__)"

# ② 包导入不加载 app 子模块
python3 -c "import sys, harmonica_eval.host as h; assert 'harmonica_eval.host.app' not in sys.modules; print('② OK 未加载 app')"

# ③ 文件内零 import、无函数/类
python3 - <<'PY'
import ast, pathlib
src = pathlib.Path("harmonica_eval/host/__init__.py").read_text(encoding="utf-8")
tree = ast.parse(src)
imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
assigns = [n for n in tree.body if isinstance(n, ast.Assign)]
assert not imports, imports
assert not defs, defs
assert [t.id for a in assigns for t in a.targets if isinstance(t, ast.Name)] == ["__all__"], assigns
print("③ OK 零 import / 零 def / 仅 __all__ 赋值")
PY

# ④ 子模块接入
python3 -c "from harmonica_eval.host import app; print('④ OK', app.__name__)"

# ⑤ 空壳期基线（注入期后第④段会因其他文件有实现而报错，属预期）
python3 tools/verify_shell.py
```

**验收判据**（可机械判定）：

- [ ] 命令 ①–④ 全部打印 `OK`
- [ ] `grep -c "^import\|^from" harmonica_eval/host/__init__.py` 输出 `0`
- [ ] `grep -n "HostApp\|build_default_app\|MAX_PROJECTION_POINTS" harmonica_eval/host/__init__.py` 无输出
- [ ] `history`/diff 显示本文件在注入期内零改动（sha256 前后相同）

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] 命令 ①–⑤ 的**实际输出**（贴文本，不是"通过"）
- [ ] 本文件的 `sha256sum` **注入前 / 注入后**两个值（必须相同）
- [ ] `git status --short harmonica_eval/host/__init__.py` 输出（应为空）

---

## 10 · ★ 何时必须停止并上报

**必须停止的情形**：

1. 你认为 `__all__` 应当多于或少于 `["app"]`（例如把 `HostApp` 列进来）——
   那是**公开面设计**，不是实现。
2. 你为了让 E4（星号导入）成立而想加 `from . import app` ——
   E4 由语言保证，**不需要**这行；加了会破坏 E2/INV-300-4。
3. 你认为本文件应当列出 `PUBLIC_SUBMODULES` 或 `__version__` ——
   那是根包（FILE-001）的职责。
4. `tools/verify_shell.py` 报出与本文冲突的结论（例如要求本文件有函数）。
5. 你发现本文件与 `__main__.py` / `cockpit` 对 `host` 公开面的假设不一致。

**上报格式**（宪章 §37）：

```
GATE CHALLENGE
- 相关 Requirement：
- 相关 Build Instruction 章节：
- 实际需要 vs 规格给出：
- 为什么冲突：
- 复现证据：
- 建议的上游处理位置：
```

**绝对禁止**：先做一个"能跑的 workaround"（宪章 §38）；
自行加"合理"的 re-export；静默缩小或扩大公开面。

---

## 附：本文件的冻结常量速查

| 常量/事实 | 值 | 来源 |
| --- | --- | --- |
| `host.__all__` | `["app"]` | `harmonica_eval/host/__init__.py:33` |
| 根包公开子模块 | `("contract","profile","core","algorithms","host","cockpit")` | `harmonica_eval/__init__.py:52-59` |
| 依赖方向禁止清单（不含 `host`） | `core→{algorithms,host,cockpit}` 等 | `tools/verify_shell.py:205-211` |
| `HostContract` 操作数 | 7 | `harmonica_eval/contract.py:490-569` |
| `UiProjectionPort` 操作数 | 2（`snapshot` / `submit`） | `harmonica_eval/contract.py:936-948` |
| 本文件 import 数 | 0 | 本文 §3 |
