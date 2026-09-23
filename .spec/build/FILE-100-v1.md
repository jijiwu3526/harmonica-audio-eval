# FILE-100 — `harmonica_eval/core/__init__.py`

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/core/__init__.py`
> 生成依据：`COMPONENTS.md@v2 §3` · `PLAN.md@v2 §四` · `SPEC.md@v2.1 §5/§6` · 目标文件自身铭牌（53 行）
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-100 |
| 所属组件 | COMP-C2 Audio Core |
| 层级 | L3（symbol / implementation）；本文件是 COMP-C2 在 L3 的**包边界节点** |
| 上游 | `profile.PORTS`（契约来源，`__all__` 的比对基准）；任何执行 `import harmonica_eval.core` 的调用方（C1 host、C3 cockpit 的测试） |
| 下游 | `harmonica_eval/core/ingest.py`、`align.py`、`features.py`、`surface.py`、`api.py`（本文件只在 `__all__` 中**声明**它们的名字，不导入它们） |
| 同层邻居 | `harmonica_eval/core/ingest.py`、`harmonica_eval/core/align.py`、`harmonica_eval/core/features.py`、`harmonica_eval/core/surface.py`、`harmonica_eval/core/api.py` |
| 你的权限 | 只写 `harmonica_eval/core/__init__.py` 这一个文件 |

**你的权限**：只实现本文件。不得修改任何其他文件，不得修改契约，不得新增端口，不得新增依赖。

本文件的内容是**逐字节冻结**的：53 行、4 个顶层 AST 节点、1 条 import 语句、`__all__` 含 5 个元素。你的任务是把这些冻结事实落成合法 Python 源文件，不是重新设计公开面。

---

## 2 · 这个文件为什么存在

追溯到 Product Intent：本项目对外只提供「双音频对比 → 客观数值指标」。C1（host）与 C3（cockpit）必须能拿到 Core 的指标，同时**不得**知道 Core 内部如何切分模块。本文件就是这条边界的唯一落点。

**删掉它会坏掉什么**：

1. `harmonica_eval/core/` 不再是 Python 包，`import harmonica_eval.core` 抛 `ModuleNotFoundError`，`import harmonica_eval.core.api` 随之全部失效 —— C1 无法拿到 CONTRACT-HOST-v1 的 7 个操作。
2. 「Audio Core 对外提供什么」失去唯一可读落点（宪章 §41）。C1 会被迫直接 `import harmonica_eval.core.features` 之类的深路径，Core 的内部切分从此对 C1 可见，**深组件（deep module）性质被破坏**。
3. 端口归属失去可审计的声明：`profile.PORTS` 的 `produced_by` 与代码实际公开面之间不再有可比对的东西，端口漂移无法在构建期被拦截。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：

- Python 标准库：**无**（零个标准库模块）
- 第三方：**无**（零个）
- 本包内：**无**（零个）
- 唯一的 import 语句：`from __future__ import annotations`（`__future__` 是编译指示伪模块，不计入标准库依赖；它必须是本文件内**唯一**的 import 语句）

**禁止 import**：

- `numpy`、`scipy`、`torch`、`tensorflow`、`librosa`、`soundfile`、`pandas`、`numba`（本文件零第三方 import，上述任何一个出现在 `sys.modules` 里都是失败）
- `harmonica_eval.host`（任何形式：`import`、`from ... import`、`importlib`、相对导入）
- `harmonica_eval.algorithms`（任何形式）
- `harmonica_eval.cockpit`（任何形式）
- `harmonica_eval.core.ingest` / `.align` / `.features` / `.surface` / `.api`（本文件不得导入自己的子模块，任何形式）
- 任何不在上述清单里的东西

---

## 4 · 你要实现什么（行为规格）

本文件不含阈值、不含容差、不含单位换算（无算术、无比较、无时间基准）。本节所有「写死」体现为**结构性常量**：文件行数 `53`、顶层 AST 节点数 `4`、import 语句数 `1`、`__all__` 元素数 `5`、公开子模块数 `5`、CONTRACT-HOST-v1 操作数 `7`。全部见文末「附：本文件的冻结常量速查」。

本文件的公开符号只有 `__all__` 一个；另有两处冻结的字符串字面量（模块 docstring、门面说明串）。逐项规格如下。

### 4.1 顶层结构（冻结为 4 个 AST 节点，顺序不可换）

| 序号 | 节点类型 | 行区间 | 内容 |
| --- | --- | --- | --- |
| 0 | `Expr`（`Constant(str)`） | 1–31 | 模块 docstring |
| 1 | `ImportFrom` | 33 | `from __future__ import annotations` |
| 2 | `Assign` | 35–41 | `__all__ = [...]` |
| 3 | `Expr`（`Constant(str)`） | 42–53 | 门面说明串（裸字符串表达式语句） |

- 文件总行数（`src.splitlines()` 的长度）：**等于 53**。
- 第 32 行与第 34 行：**空行**。
- 文件末尾：**恰好一个换行符**，其前一行是第 53 行的 `"""`。
- 顶层不得出现 `Import`、`FunctionDef`、`AsyncFunctionDef`、`ClassDef`、`If`、`Try`、`For`、`While`、`With`、`Lambda`、`Global`、`Nonlocal` 中的任何一种（`ast.walk` 全域扫描，见 §8 判据 A）。

### 4.2 `from __future__ import annotations`

- **输入**：无。**输出**：无（编译期行为）。
- **口径**：`ast.ImportFrom`，`level == 0`，`module == "__future__"`，`names` 恰好为 `[alias(name="annotations", asname=None)]`。
- **边界**：这是全文件唯一的 import 语句；不得追加任何其他 import。
- **不变量**：`len([n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]) == 1`。

### 4.3 `__all__`（本文件唯一的公开符号）

- **输入**：无。
- **输出**：一个 `list`，其值**逐元素冻结**为：

  ```python
  __all__ = [
      "ingest",
      "align",
      "features",
      "surface",
      "api",
  ]
  ```

- **算法口径**：`Assign` 节点，`targets` 恰好为 `[Name(id="__all__", ctx=Store())]`；`value` 是 `ast.List`，`len(value.elts) == 5`，每个 `elt` 是 `ast.Constant` 且 `isinstance(elt.value, str) is True`。元素**顺序**冻结为 `ingest, align, features, surface, api`。
- **边界（逐条写死返回值）**：
  - 元素个数为 `0`：**不合法**，失败。
  - `__all__` 写成 `tuple` / `set` / `frozenset`：**不合法**，失败（必须是 `list` 字面量）。
  - `__all__` 由拼接、`sorted(...)`、星号展开、列表推导构造：**不合法**，失败。
  - `__all__` 中出现重复元素：**不合法**，失败。
  - `__all__` 中出现非 `str` 元素：**不合法**，失败。
  - 元素个数为 `5` 但顺序不同：**不合法**，失败。
- **单位**：无。**时间基准**：无。
- **不变量**：`harmonica_eval.core.__all__ == ["ingest", "align", "features", "surface", "api"]`（`list` 比较，非集合比较）。
- **契约一致性口径**：定义 `declared = set(__all__)`；定义 `produced = {p.produced_by.split(".")[1] for p in profile.PORTS 中所有端口 if p.produced_by.startswith("core.")}`。必须 `declared == produced`。`produced_by` 的取法：该字段是 `str` 时取本身；是 `str` 的可迭代容器时逐个取。端口总数、端口 ID 一律以 `profile.PORTS` 为准，本文件不复写。

### 4.4 模块 docstring（第 1–31 行）

- **输入**：无。**输出**：`harmonica_eval.core.__doc__`。
- **算法口径**：`tree.body[0]` 是 `Expr` 且 `value` 是 `Constant(str)`。docstring 内必须出现下列 10 个键，且**首次出现的位置严格递增**：

  `FILE-ID:` → `COMPONENT:` → `SPEC:` → `ROLE:` → `INTENT:` → `MUST:` → `MUST NOT:` → `INPUT:` → `OUTPUT:` → `BUILD-INSTRUCTION:`

- **冻结内容**（`\s+` 表示一个或多个空白字符，其余字符逐字相同）：
  - `FILE-ID:\s+FILE-100`
  - `COMPONENT:\s+COMP-C2 Audio Core`
  - `BUILD-INSTRUCTION:` 段落指向 `.spec/build/FILE-100-v1.md`
  - MUST 段必须含字符串：`只声明公开面，不含逻辑`
  - MUST 段必须含字符串：`公开面必须与 profile.PORTS 的 produced_by 所指模块一致`
  - MUST NOT 段必须含字符串：`import host / algorithms / cockpit（任何形式）`
  - MUST NOT 段必须含字符串：`在包导入期做重量级 import（numpy 之外不加载重型依赖）`
  - MUST NOT 段必须含字符串：`在此处 re-export 子模块的内部符号`
  - `INPUT:` 段落的内容为「（无）」
  - `OUTPUT:` 段落的内容为 `__all__`
- **边界**：docstring 为空字符串：**不合法**，失败。缺任一键：**不合法**，失败。键顺序与上表不符：**不合法**，失败。
- **不变量**：`harmonica_eval.core.__doc__` 非空且 `len(harmonica_eval.core.__doc__.splitlines()) == 31`。

### 4.5 门面说明串（第 42–53 行）

- **输入**：无。**输出**：无（裸字符串表达式语句，不绑定任何名字）。
- **算法口径**：`tree.body[3]` 是 `Expr` 且 `value` 是 `Constant(str)`。该串必须含 `core.<name>` 5 行，每行形如 `core.<name>` + 空白 + `→` + 空白 + 端口说明：
  - `core.ingest` → 含 `标准化 PCM`，且含 `不产出端口，是前置步骤`
  - `core.align` → 正则 `core\.align\s+→\s+warp_path`
  - `core.features` → 含 `pitch.*`、`rms.*`、`chroma.lowres.*`、`notes.*`
  - `core.surface` → 正则 `core\.surface\s+→\s+pcm\.\*`，且含 `装配 + Seal`
  - `core.api` → 正则 `core\.api\s+→\s+CONTRACT-HOST-v1\s+的\s+7\s+个操作`
- 该串必须含冻结字符串：``**C1 只应 import `core.api`。**``
- 该串必须含 `profile.PORTS` 字样，并说明其余子模块的公开只为可测试性与可审查性。
- **边界**：该串缺失：**不合法**，失败。任一行 `core.<name>` 缺失：**不合法**，失败。操作数不写 `7`：**不合法**，失败。
- **不变量**：该节点不得绑定名字（`Assign` 形式不合法），不得是 f-string（`JoinedStr` 不合法）。
- **说明**：门的唯一入口是 `core.api`；`__all__` 声明 5 个子模块，是因为 `profile.PORTS` 的 `produced_by` 覆盖这 5 个。这两条同时为真，不构成冲突：声明 ≠ 入口。

### 4.6 包导入期行为

- **输入**：执行 `import harmonica_eval.core`。**输出**：模块对象，其 `__all__` 与 `__doc__` 如 4.3 / 4.4。
- **算法口径**：本文件零运行期语句，导入期不执行任何逻辑、不访问文件系统、不读环境变量、不发网络请求、不打印。
- **边界**：`harmonica_eval/core/ingest.py` 等子模块缺失时，`import harmonica_eval.core` **必须仍然成功**（因为本文件不导入子模块）。
- **不变量**：导入完成后，`sys.modules` 中不存在任何以 `harmonica_eval.core.` 开头的键；`numpy` 与 §3 禁止清单中的所有重型依赖均不在 `sys.modules` 中。

---

## 5 · 失败语义

本文件无运行期逻辑，**全部失败都发生在构建期/校验期**，由 §8 的判据抛出 `AssertionError`（非零退出码）。本文件内部**不得**实现任何运行时校验代码。

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| `harmonica_eval/core/ingest.py`（或 `.align/.features/.surface/.api`）不存在 | 本文件不导入子模块，`import harmonica_eval.core` 正常成功；不得为此加 try/except、不得加 `__getattr__` | 无异常；`import harmonica_eval.core` 返回模块对象 |
| 调用方写 `from harmonica_eval.core import *` 而子模块缺失 | 由 Python 导入机制显式失败，本文件不拦截、不降级 | `ImportError` / `ModuleNotFoundError`（由 import 机制产生，非本文件代码） |
| `profile.PORTS` 的 `produced_by` 集合与 `__all__` 不一致 | 构建期显式失败，禁止改 `__all__` 去迁就、禁止改 `profile.py` | `AssertionError`（§8 判据 B） |
| 文件内出现除 `from __future__ import annotations` 之外的 import | 构建期显式失败 | `AssertionError`（§8 判据 A） |
| 导入本包时连带导入了任一 `harmonica_eval.core.*` 子模块 | 构建期显式失败 | `AssertionError`（§8 判据 C） |
| 导入本包时加载了 `numpy` 或任一禁止清单中的重型依赖 | 构建期显式失败 | `AssertionError`（§8 判据 C） |
| 导入本包时加载了 `harmonica_eval.host` / `.algorithms` / `.cockpit` | 构建期显式失败 | `AssertionError`（§8 判据 C） |
| `__all__` 被写成 `tuple`、含非 `str`、含重复、长度 ≠ 5、顺序不同 | 构建期显式失败 | `AssertionError`（§8 判据 A） |
| 本文件出现函数、类、`if`、`try`、`for`、`while`、`with`、`lambda`、`global`、`nonlocal` | 构建期显式失败 | `AssertionError`（§8 判据 A） |
| 本文件语法错误 | 构建期显式失败 | `SyntaxError`（`ast.parse` / `py_compile`） |
| 「算不出来就返回默认值」 | 本文件无计算，此路径不存在；任何形式的默认值、兜底、静默降级**一律禁止**（宪章 §5.6） | 不适用 |

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-100-1 | 只声明公开面，不含逻辑 | §8 判据 A：AST 全域扫描，`FunctionDef/AsyncFunctionDef/ClassDef/If/Try/For/While/With/Lambda/Global/Nonlocal` 出现次数均为 0 |
| INV-100-2 | 全文件恰好 1 条 import 语句，且为 `from __future__ import annotations` | §8 判据 A：import 节点计数 `== 1`，且 `module == "__future__"`、`names == ["annotations"]`、`level == 0` |
| INV-100-3 | 本文件不导入任何 `harmonica_eval.core.*` 子模块，也不得做 re-export | §8 判据 A（AST 层：无 `.ingest/.align/.features/.surface/.api` 引用）+ 判据 C（运行期：`sys.modules` 无以 `harmonica_eval.core.` 开头的键） |
| INV-100-4 | 公开面与 `profile.PORTS` 的 `produced_by` 所指模块一致 | §8 判据 B：`declared == produced`，两集合各打印 |
| INV-100-5 | `__all__` 是 `list` 字面量，恰好 5 个 `str`，顺序为 `ingest, align, features, surface, api` | §8 判据 A：逐元素 `==` 比较 |
| INV-100-6 | 导入本包不加载 `numpy` 及 `torch/scipy/librosa/soundfile/pandas/numba/tensorflow` | §8 判据 C：逐个 `not in sys.modules` |
| INV-100-7 | 导入本包不加载 `harmonica_eval.host` / `.algorithms` / `.cockpit` | §8 判据 C：逐个 `not in sys.modules` |
| INV-100-8 | 模块 docstring 含 10 个冻结键且首次出现位置严格递增 | §8 判据 A：`pos == sorted(pos)` 且 10 项互不相同 |
| INV-100-9 | 文件 53 行、4 个顶层节点、节点类型顺序为 `Expr(Constant str) / ImportFrom / Assign / Expr(Constant str)` | §8 判据 A：`len(src.splitlines()) == 53`、`len(tree.body) == 4`、四段类型逐个 `isinstance` |
| INV-100-10 | 文件不改动任何其他文件、不新增依赖 | §9：`git status --porcelain` 只列出 `harmonica_eval/core/__init__.py` 一个条目 |

---

## 7 · 边界（明确不做）

- 不导入任何子模块，不做任何形式的 re-export（含 `from .api import *`、`from . import ingest`、`__getattr__` 惰性导入）。
- 不定义函数、类、异常、`TypeVar`、`NamedTuple`、`Protocol`。
- 不定义 `__all__` 以外的模块级常量或变量（不得加 `__version__`、`__author__`、`VERSION`、`DEFAULT_*`）。
- 不在本文件内实现任何端口、任何特征计算、任何 PCM 处理（那是 `ingest/align/features/surface/api` 的职责）。
- 不写运行期校验、日志、`print`、`warnings`、`atexit`、`if TYPE_CHECKING` 块、`try/except`。
- 不新增、不删除、不重排 `__all__` 的条目，不改动 4.4/4.5 的冻结字符串。
- 不加任何第三方依赖，不改 `pyproject.toml` / `setup.cfg` / `requirements*.txt`。
- 不改 `profile.py`、不改 `COMPONENTS.md` / `PLAN.md` / `SPEC.md`、不改任何 `.spec/` 下的文件（含本文件）。
- 不为了让判据变绿而放宽判据、删判据、跳过判据。
- 若你发现「不做上述某件事就实现不了」→ **不要做**，转 §10。

---

## 8 · 怎么验证你写对了

```bash
set -euo pipefail
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval

# 0) 语法与字节码编译
python3 -m py_compile harmonica_eval/core/__init__.py

# 1) 判据 A：本文件自身的结构性判据（纯标准库，必然可跑）
python3 - <<'PY'
import ast, re, pathlib

FROZEN = ["ingest", "align", "features", "surface", "api"]
KEYS = ["FILE-ID:", "COMPONENT:", "SPEC:", "ROLE:", "INTENT:",
        "MUST:", "MUST NOT:", "INPUT:", "OUTPUT:", "BUILD-INSTRUCTION:"]

src = pathlib.Path("harmonica_eval/core/__init__.py").read_text(encoding="utf-8")

# INV-100-9
assert len(src.splitlines()) == 53, len(src.splitlines())
assert src.endswith('"""\n') or src.endswith('"""'), "facade string must close the file"

tree = ast.parse(src)
# INV-100-9：4 个顶层节点，类型与顺序冻结
assert len(tree.body) == 4, len(tree.body)
assert isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) \
    and isinstance(tree.body[0].value.value, str)
# INV-100-2
assert isinstance(tree.body[1], ast.ImportFrom)
assert tree.body[1].module == "__future__" and tree.body[1].level == 0
assert [(a.name, a.asname) for a in tree.body[1].names] == [("annotations", None)]
# INV-100-5
assert isinstance(tree.body[2], ast.Assign)
assert len(tree.body[2].targets) == 1
t = tree.body[2].targets[0]
assert isinstance(t, ast.Name) and t.id == "__all__" and isinstance(t.ctx, ast.Store)
lst = tree.body[2].value
assert isinstance(lst, ast.List), type(lst).__name__
assert len(lst.elts) == 5, len(lst.elts)
assert all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in lst.elts)
vals = [e.value for e in lst.elts]
assert vals == FROZEN, vals
assert len(set(vals)) == 5, "duplicate entries in __all__"
# INV-100-10(b)：门面串是裸字符串表达式，不绑定名字
assert isinstance(tree.body[3], ast.Expr) and isinstance(tree.body[3].value, ast.Constant) \
    and isinstance(tree.body[3].value.value, str)

# INV-100-2：import 语句总数 == 1
imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
assert len(imports) == 1, len(imports)

# INV-100-1：零逻辑
BANNED = {"FunctionDef", "AsyncFunctionDef", "ClassDef", "If", "Try",
          "For", "While", "With", "Lambda", "Global", "Nonlocal"}
seen = {type(n).__name__ for n in ast.walk(tree)}
assert seen & BANNED == set(), seen & BANNED

# INV-100-3：不导入子模块、不做 re-export
for bad in ("ingest", "align", "features", "surface", "api"):
    assert f".{bad}" not in src.replace("core." + bad, ""), bad

# INV-100-8：docstring 10 键
doc = tree.body[0].value.value
assert doc, "module docstring is empty"
assert len(doc.splitlines()) == 31, len(doc.splitlines())
pos = [doc.index(k) for k in KEYS]
assert pos == sorted(pos) and len(set(pos)) == 10, pos
assert re.search(r"^FILE-ID:\s+FILE-100\s*$", doc, re.M)
assert re.search(r"^COMPONENT:\s+COMP-C2 Audio Core\s*$", doc, re.M)
assert ".spec/build/FILE-100-v1.md" in doc
assert "只声明公开面，不含逻辑" in doc
assert "公开面必须与 profile.PORTS 的 produced_by 所指模块一致" in doc
assert "import host / algorithms / cockpit（任何形式）" in doc
assert "在包导入期做重量级 import（numpy 之外不加载重型依赖）" in doc
assert "在此处 re-export 子模块的内部符号" in doc
assert re.search(r"^OUTPUT:\s*\n\s*__all__\s*$", doc, re.M)

# 4.5 门面串
fac = tree.body[3].value.value
for m in FROZEN:
    assert f"core.{m}" in fac, m
assert re.search(r"core\.align\s+→\s+warp_path", fac)
assert re.search(r"core\.surface\s+→\s+pcm\.\*", fac)
assert re.search(r"core\.api\s+→\s+CONTRACT-HOST-v1\s+的\s+7\s+个操作", fac)
assert "标准化 PCM" in fac and "不产出端口，是前置步骤" in fac
for tok in ("pitch.*", "rms.*", "chroma.lowres.*", "notes.*", "装配 + Seal"):
    assert tok in fac, tok
assert "**C1 只应 import `core.api`。**" in fac
assert "profile.PORTS" in fac

print("PASS 判据A 文件行数=53 顶层节点=4 import语句=1 __all__=5 门面串=10键OK")
PY

# 2) 判据 B：与 profile.PORTS 的 produced_by 交叉一致
python3 - <<'PY'
import harmonica_eval.core as core
import harmonica_eval.profile as profile

def _iter_ports(p):
    if isinstance(p, dict):
        return list(p.values())
    return list(p)

def _field(obj, name):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)

def _names(v):
    if isinstance(v, str):
        return [v]
    return [x for x in v]

declared = set(core.__all__)
produced = set()
for port in _iter_ports(profile.PORTS):
    for pb in _names(_field(port, "produced_by")):
        assert isinstance(pb, str), pb
        if pb.startswith("core."):
            produced.add(pb.split(".")[1])

print("declared =", sorted(declared))
print("produced =", sorted(produced))
assert declared == produced, (sorted(declared), sorted(produced))
assert core.__all__ == ["ingest", "align", "features", "surface", "api"], core.__all__
print("PASS 判据B declared == produced ==", sorted(declared))
PY

# 3) 判据 C：导入期无越界加载（干净解释器）
python3 -c "
import sys, harmonica_eval.core as core
assert core.__all__ == ['ingest','align','features','surface','api'], core.__all__
leaked = [m for m in sys.modules if m.startswith('harmonica_eval.core.')]
assert leaked == [], leaked
for bad in ('harmonica_eval.host','harmonica_eval.algorithms','harmonica_eval.cockpit',
            'numpy','torch','scipy','librosa','soundfile','pandas','numba','tensorflow'):
    assert bad not in sys.modules, bad
print('PASS 判据C 导入期零越界加载')
"

# 4) 只改了一个文件
git status --porcelain
git diff --stat
```

**验收判据**（可机械判定，全部必须为真）：

- [ ] `python3 -m py_compile harmonica_eval/core/__init__.py` 退出码为 `0`。
- [ ] 判据 A 脚本退出码为 `0`，末尾打印 `PASS 判据A ...`。
- [ ] `len(pathlib.Path("harmonica_eval/core/__init__.py").read_text(encoding="utf-8").splitlines()) == 53`。
- [ ] `len(ast.parse(src).body) == 4`，且四段类型依序为 `Expr / ImportFrom / Assign / Expr`。
- [ ] `[n for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]` 的长度 `== 1`。
- [ ] `harmonica_eval.core.__all__ == ["ingest", "align", "features", "surface", "api"]`（`list` 精确相等）。
- [ ] `{type(n).__name__ for n in ast.walk(tree)} & {"FunctionDef","AsyncFunctionDef","ClassDef","If","Try","For","While","With","Lambda","Global","Nonlocal"} == set()`。
- [ ] 判据 B 脚本退出码为 `0`，`declared == produced` 且两集合均已打印。
- [ ] 判据 C 脚本退出码为 `0`，`[m for m in sys.modules if m.startswith("harmonica_eval.core.")] == []`。
- [ ] 判据 C 中 11 个禁止模块名全部 `not in sys.modules`。
- [ ] `git status --porcelain` 只输出一行，且该行路径为 `harmonica_eval/core/__init__.py`。

**验证禁令**：判据脚本中**不得**出现 `from harmonica_eval.core import *`（它会触发子模块导入并污染判据 C）；不得 `pip install` 任何东西；不得修改任何文件来让判据变绿。

---

## 9 · 完成后提交什么证据

- [ ] 产物：`harmonica_eval/core/__init__.py`（53 行，`sha256sum` 值一并提交）。
- [ ] `python3 -m py_compile harmonica_eval/core/__init__.py` 的完整输出与退出码 `0`。
- [ ] 判据 A 的完整 stdout，含 `PASS 判据A ...` 一行。
- [ ] 判据 B 的完整 stdout，含打印出的 `declared = [...]` 与 `produced = [...]` 两行（这是端口一致性的黄金向量对比结果）。
- [ ] 判据 C 的完整 stdout，含 `PASS 判据C ...` 一行。
- [ ] `git status --porcelain` 的完整输出，证明只改动了 `harmonica_eval/core/__init__.py`（INV-100-10）。
- [ ] `git diff --stat` 的完整输出。
- [ ] 若任一判据未通过：提交失败判据的原始 stderr 全文 + 复现命令，并按 §10 上报，**不得**提交「部分通过」的产物。

---

## 10 · ★ 何时必须停止并上报（§22 硬失败对策）

**以下情况必须停止，提交 `MOLD BREAK`，不得自行设计：**

1. 你发现本文件**需要做上层设计**才能实现（例如：需要决定新的 `__all__` 成员、新的公开面口径、新的端口、新的错误码、新的层间依赖）。
2. 本文件与任何上游工件（`SPEC.md@v2.1` / `COMPONENTS.md@v2` / `PLAN.md@v2` / `profile.PORTS` / 目标文件自身铭牌）**冲突**。
3. 你需要的依赖**不在 §3 清单里**（含：你判断必须 import 某个标准库或子模块才能完成本文件）。
4. §4 的行为规格**不足以确定唯一实现**（含：§8 判据 B 因 `profile.PORTS` 的实际形态与本文件假设不符而抛 `KeyError` / `AttributeError` / `TypeError`）。
5. 你认为 §4 的规格本身**是错的**（含：你认为 `__all__` 应当包含 `profile.PORTS` 之外的成员，或认为 `core.api` 之外还应有别的入口）。
6. §8 判据 C 失败，且失败原因是**本文件之外**的模块（例如 `harmonica_eval/__init__.py` 在导入期把 `numpy` 或 `harmonica_eval.core.api` 拉进了 `sys.modules`）——此时**不得**修改本文件，**不得**修改其他文件。

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

- 先做一个「能跑的 workaround」，以后再说（§38 明文禁止）。
- 自行在代码里加一个「合理的」默认值把冲突掩盖过去（例如：给 `__all__` 加一项、把 `__all__` 改成 `tuple`、加 `try/except` 包住子模块导入）。
- 静默缩小范围（「这个子模块我先不声明」）。
- 删除或放宽 §8 的判据使校验通过。

---

## 附：本文件的冻结常量速查

| 常量 | 值 | 来源 |
| --- | --- | --- |
| 目标文件总行数 | `53` | `harmonica_eval/core/__init__.py` 全文（1–53） |
| 顶层 AST 节点数 | `4` | 行 1（docstring）/ 33（`__future__`）/ 35（`__all__`）/ 42（门面串） |
| import 语句数 | `1` | 行 33 |
| `__all__` 元素个数 | `5` | 行 35–41 |
| `__all__` 值（含顺序） | `["ingest", "align", "features", "surface", "api"]` | 行 36–40 |
| 公开子模块数 | `5` | 行 45–49 |
| CONTRACT-HOST-v1 操作数 | `7` | 行 49 |
| 组件 ID | `COMP-C2 Audio Core` | 行 3 |
| 文件 ID | `FILE-100` | 行 2 |
| docstring 行数 | `31` | 行 1–31 |
| docstring 冻结键数 | `10` | 行 2 / 3 / 4 / 6 / 9 / 14 / 18 / 23 / 26 / 29 |
| 门面串行数 | `12` | 行 42–53 |
| 本文件（Build Instruction）路径 | `.spec/build/FILE-100-v1.md` | 行 30 |
| 阈值 / 容差 / 单位换算 | 不适用（本文件零算术、零比较、零单位） | 目标文件全文 |
