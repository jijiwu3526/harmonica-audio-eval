# FILE-200 — `harmonica_eval/algorithms/__init__.py`

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/algorithms/__init__.py`
> 生成依据：`SPEC.md@v2.1` · `harmonica_eval/contract.py`（`PluginSpec` / `InputRequirement` / `AlgorithmResultEnvelope`）· `harmonica_eval/algorithms/registry.py` · `COMPONENTS.md@v2 §3`
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-200 |
| 所属组件 | COMP-C3 Algorithm |
| 层级 | L3（symbol / implementation） |
| 上游 | Python 导入方；插件装配由 C1 的 `build_default_app()` 负责。本文件不接收音频、Surface 或算法参数。 |
| 下游 | `harmonica_eval.contract` 提供 `PluginSpec` / `InputRequirement`；`harmonica_eval.algorithms.registry` 提供 `Registry`。本文件只把三者作为类型出口公开。 |
| 同层邻居 | `harmonica_eval/algorithms/registry.py`（注册表实现）；`pitch.py`、`timing.py`、`dynamics.py`（具体算法模块，本文件不得导入）。 |
| 你的权限 | 只实现 `harmonica_eval/algorithms/__init__.py`；不得修改任何其他源码或规格。 |

本文件是 `harmonica_eval.algorithms` 包的公开入口，不是算法清单、算法注册点或算法实现文件。C1、C3 的其他实现只通过本文件取得插件契约类型和注册表类型。

---

## 2 · 这个文件为什么存在

追溯到 Product Intent「双音频对比 → 客观数值指标」以及架构要求「新增算法不应改写核心与框架」。本文件把插件契约的类型出口收敛到 C3 算法包：调用方只从同一处取得 `PluginSpec`、`InputRequirement` 和 `Registry`，不必分别寻找契约定义与注册表实现。

本文件曾把三个具体算法硬绑进宿主，已移除。那种做法使算法集合、具体入口和结果字段映射都集中在这个文件，因而新增算法必须改写算法框架。当前文件只承担类型出口与 re-export；具体算法的注册由 C1 的 `build_default_app()` 逐个调用 `Registry.register` 完成。

删除本文件会破坏以下公开导入路径：调用方不能再从 `harmonica_eval.algorithms` 取得 `PluginSpec` 或 `InputRequirement`，也不能从该包入口取得 `Registry`。这不会删除任何算法实现，也不会改变 `Registry` 的运行行为。

---

## 3 · 你能用的东西（依赖清单，封闭）

**允许的 import 只有以下三项**：

1. `from __future__ import annotations`
2. `from ..contract import InputRequirement, PluginSpec`
3. `from .registry import Registry`

- 第三方依赖：空集。
- 本包内依赖：仅 `..contract` 与 `.registry` 两个模块。
- 标准库依赖：仅 `__future__` 的 `annotations`。
- 依赖必须写在模块顶层；不得放入函数体或其他延迟位置。
- 不得通过 `__import__`、`importlib`、字符串路径或 `getattr` 间接加载其他模块。

**禁止 import 或动态加载**：

- `harmonica_eval.core`、`harmonica_eval.host`、`harmonica_eval.cockpit` 的任何模块；
- `harmonica_eval.algorithms.pitch`、`harmonica_eval.algorithms.timing`、`harmonica_eval.algorithms.dynamics` 或任何其他具体算法实现模块；
- `dataclasses`、`typing`、`inspect`、`importlib` 以及清单外的标准库；
- numpy、scipy、soundfile、librosa 或任何第三方模块；
- 清单外的本包模块。

需要清单外的依赖时，停止并按 §10 上报；不得以兼容分支或延迟导入绕过本节。

---

## 4 · 你要实现什么（行为规格）

### 4.0 模块铭牌

在文件顶部写一个模块 docstring。铭牌必须包含以下 10 个字段，字段名按下列形式出现；`WHY` 等补充段可存在，但不得缺少这 10 个字段：

```text
FILE-ID:
COMPONENT:
SPEC:
ROLE:
INTENT:
MUST:
MUST NOT:
INPUT:
OUTPUT:
BUILD-INSTRUCTION:
```

格式要求：

- 使用模块 docstring，而不是普通注释作为铭牌载体。
- `FILE-ID` 的值为 `FILE-200`；`COMPONENT` 的值为 `COMP-C3 Algorithm`。
- `ROLE` 写明本文件是插件契约的类型出口与 re-export。
- `INTENT` 写明新增算法不在本文件增加登记。
- `MUST` / `MUST NOT` 分别写出可检查的正向约束与禁止项。
- `INPUT` 写明来自 `..contract` 和 `.registry` 的符号。
- `OUTPUT` 写明三个公开类型与 `__all__`。
- `BUILD-INSTRUCTION` 写 `.spec/build/FILE-200-v1.md`。
- 文档与注释使用中文；重要裁定可用 `★` 标记。

### 4.1 两个契约类型的 re-export

在模块 docstring 之后、`__all__` 之前，按 §3 的位置要求写出 `..contract` 的导入，导入名逐字为 `InputRequirement` 与 `PluginSpec`。

这两个名字必须直接绑定到 `..contract` 导出的对象；不得在本文件定义同名类、包装类、别名类、函数代理或运行时复制。

### 4.2 `Registry` 类型的 re-export

在同一 import 区域，从 `.registry` 导入名逐字为 `Registry`。该名字必须直接绑定到 `.registry.Registry`；本文件不实现、不继承、不实例化、不包装 `Registry`。

### 4.3 `__all__`

在 import 之后定义模块级 `__all__`，格式为 `list[str]`，内容按下列顺序逐字列出：

```python
__all__: list[str] = ["InputRequirement", "PluginSpec", "Registry"]
```

`__all__` 的集合必须恰好是这三个名字，不得添加其他名字，不得为空，不得用生成式或动态表达式替代。模块的直接导入路径必须能取得这三个名字。

### 4.4 包入口的行为边界

本文件除模块 docstring、上述 import 与 `__all__` 外，不实现函数、类、算法入口、注册动作或结果校验动作。

- 不构造 `PluginSpec` 或 `InputRequirement` 实例。
- 不构造 `Registry`，不调用 `Registry.register`，不保存任何插件规格。
- 不保存算法 ID、算法版本、算法入口、端口清单或 payload 字段表。
- 不执行算法逻辑，不读取 Surface，不写文件，不联网，不打印，不记录日志。
- 不做重复 ID 检查；该检查由 `Registry.register` 在注册时负责。
- 不提供算法目录扫描、动态发现、兼容别名或弃用入口。

### 4.5 模块导入契约

模块顶层执行上述 import 与 `__all__` 赋值即可；不要求额外执行注册、自检、初始化、缓存或延迟加载。导入本文件不应启动算法、不应创建会话、不应产生注册副作用。

`Registry` 的实例化与显式注册属于 C1 的装配点；本文件只提供类型出口。任何需要改变注册顺序、插件集合或运行期行为的需求，不在本文件实现。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| `..contract` 不存在或其中缺少 `InputRequirement` / `PluginSpec` | 不捕获、不降级，导入失败 | `ImportError` / `AttributeError` 原异常向上传播 |
| `.registry` 不存在或其中缺少 `Registry` | 不捕获、不降级，导入失败 | `ImportError` / `AttributeError` 原异常向上传播 |
| 清单外依赖被声明 | 视为越界，停止实现 | 按 §10 上报 |
| 插件注册时出现重复 `algorithm_id` | 本文件不处理 | 由 `Registry.register` 按其契约显式报错 |
| 运行期算法兼容性或结果校验失败 | 本文件不处理 | 由 C1/runtime 按 `AlgorithmResultEnvelope` 契约处理 |
| 需要清单外 import 才能继续 | 停止，不做 workaround | 按 §10 上报 |

禁止在本文件捕获导入异常后改用替代对象，禁止静默跳过 re-export，禁止返回占位对象，禁止把具体算法模块作为回退实现。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-200-1 | `__all__` 恰好包含 `InputRequirement`、`PluginSpec`、`Registry` 三项 | §8.2 |
| INV-200-2 | 三项均可从 `harmonica_eval.algorithms` 直接导入，并与定义模块中的对象相同 | §8.2 |
| INV-200-3 | 模块 docstring 含 FILE-200 铭牌的全部 10 个字段 | §8.3 |
| INV-200-4 | import 集合恰为 `__future__`、`..contract`、`.registry` 三类 | §8.4 |
| INV-200-5 | 本文件不 import `core`、`host`、`cockpit` | §8.4 |
| INV-200-6 | 本文件不 import `.pitch`、`.timing`、`.dynamics` 或任何其他具体算法实现模块 | §8.5 |
| INV-200-7 | 本文件不重新提供已删除的三个公开符号 | §8.6 |
| INV-200-8 | 文件行数不超过宽松上界 100 行 | §8.7 |
| INV-200-9 | 本文件不含 `pass`、裸 `...` 表达式或 `return None` 实现泄漏 | §8.8 |
| INV-200-10 | 导入本文件不触发注册、算法执行或结果校验 | §8.2 的直接导入通过；其他动作不在本文件 |

---

## 7 · 边界（明确不做）

- 不修改 `contract.py`、`registry.py`、`host/`、`core/`、`cockpit/` 或任何具体算法模块。
- 不新增任何标准库、第三方或本包依赖。
- 不 import 或 re-export `pitch`、`timing`、`dynamics` 的实现、入口或常量。
- 不在 `__init__.py` 保存算法清单、插件实例、入口映射、端口清单或 payload 字段映射。
- 不新增、恢复或兼容包装三个已删除的公开符号。
- 不实现 `Registry` 的 register/list/get 方法，不调用这些方法。
- 不承担注册点的职责；注册点由 C1 的 `build_default_app()` 负责。
- 不实现算法逻辑、Surface 访问、结果构造、结果校验或 UI 投影。
- 不增加函数、类、异常、常量、模块属性转发器或 `__getattr__`。
- 不写文件、读文件、联网、打印、写日志、缓存全局状态或执行动态 import。
- 不把 100 行上界解释为精确行数；本节只规定可检查的宽松边界。
- 发现必须修改其他文件、改变契约或新增设计决定时，不在本文件处理，转 §10。

---

## 8 · 怎么验证你写对了

以下命令均从仓库根目录执行。每条命令的判据是退出码为 0 且输出行符合标注；任何 traceback 都视为失败。

### 8.1 解释器前置

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python --version
```

判据：命令退出码为 0；实际输出：

```text
Python 3.13.13
```

### 8.2 `__all__` 与三个 re-export

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
import harmonica_eval.algorithms as A
from harmonica_eval.algorithms import InputRequirement, PluginSpec, Registry
from harmonica_eval.contract import InputRequirement as ContractInputRequirement
from harmonica_eval.contract import PluginSpec as ContractPluginSpec
from harmonica_eval.algorithms.registry import Registry as SourceRegistry

expected = {"InputRequirement", "PluginSpec", "Registry"}
assert set(A.__all__) == expected
assert len(A.__all__) == 3
assert len(set(A.__all__)) == 3
assert (InputRequirement, PluginSpec, Registry) == (
    ContractInputRequirement,
    ContractPluginSpec,
    SourceRegistry,
)
print("EXPORTS-OK", A.__all__)
PY
```

判据：`__all__` 集合和长度均通过，三个名字可直接 import 且与定义模块对象相同；实际输出：

```text
EXPORTS-OK ['InputRequirement', 'PluginSpec', 'Registry']
```

### 8.3 铭牌完整性

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
import ast
from pathlib import Path

path = Path("harmonica_eval/algorithms/__init__.py")
doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
assert doc is not None
fields = (
    "FILE-ID", "COMPONENT", "SPEC", "ROLE", "INTENT",
    "MUST", "MUST NOT", "INPUT", "OUTPUT", "BUILD-INSTRUCTION",
)
missing = [field for field in fields if not any(
    line.split(":", 1)[0].strip() == field
    for line in doc.splitlines()
    if ":" in line
)]
assert missing == [], missing
print("PLAQUE-OK", len(fields), "fields")
PY
```

判据：模块 docstring 含全部 10 个标准铭牌字段；额外字段不构成失败；实际输出：

```text
PLAQUE-OK 10 fields
```

### 8.4 依赖封闭与禁止跨层 import

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
import ast
from pathlib import Path

path = Path("harmonica_eval/algorithms/__init__.py")
tree = ast.parse(path.read_text(encoding="utf-8"))
absolute = {
    (node.level, node.module, tuple(alias.name for alias in node.names))
    for node in ast.walk(tree)
    if isinstance(node, ast.ImportFrom) and node.level == 0
}
relative = {
    (node.level, node.module, tuple(alias.name for alias in node.names))
    for node in ast.walk(tree)
    if isinstance(node, ast.ImportFrom) and node.level > 0
}
assert absolute == {(0, "__future__", ("annotations",))}, absolute
assert relative == {
    (2, "contract", ("InputRequirement", "PluginSpec")),
    (1, "registry", ("Registry",)),
}, relative
assert not [
    node for node in ast.walk(tree)
    if isinstance(node, ast.Import)
    and any(a.name.split(".")[0] in {"core", "host", "cockpit"} for a in node.names)
]
assert not [
    node for node in ast.walk(tree)
    if isinstance(node, ast.ImportFrom)
    and (node.module or "").split(".")[0] in {"core", "host", "cockpit"}
]
assert not [
    node for node in ast.walk(tree)
    if isinstance(node, ast.Call)
    and (
        (isinstance(node.func, ast.Name) and node.func.id == "__import__")
        or (isinstance(node.func, ast.Attribute)
            and node.func.attr in {"__import__", "import_module"})
    )
]
print("DEPENDENCIES-OK", "__future__ + ..contract + .registry; no core/host/cockpit")
PY
```

判据：只允许 `__future__`、`..contract`、`.registry`，且没有 core/host/cockpit 或动态 import；实际输出：

```text
DEPENDENCIES-OK __future__ + ..contract + .registry; no core/host/cockpit
```

### 8.5 不得 import 具体算法实现模块

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
import ast
import harmonica_eval.algorithms as A
from pathlib import Path

path = Path("harmonica_eval/algorithms/__init__.py")
tree = ast.parse(path.read_text(encoding="utf-8"))
concrete = {"pitch", "timing", "dynamics"}
offenders = []
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if node.level == 1 and (
            module in concrete
            or module.split(".")[0] in concrete
            or module.split(".")[0] == "algorithms"
        ):
            offenders.append(ast.unparse(node))
        if node.level == 1 and module == "":
            offenders.extend(
                f"from . import {alias.name}"
                for alias in node.names
                if alias.name in concrete
            )
        if node.level == 0 and module.startswith("harmonica_eval.algorithms."):
            offenders.append(ast.unparse(node))
    elif isinstance(node, ast.Import):
        offenders.extend(
            alias.name for alias in node.names
            if alias.name.startswith("harmonica_eval.algorithms.")
        )
assert offenders == [], offenders
for name in concrete:
    assert not hasattr(A, name), name
print("NO-ALGORITHM-IMPORTS-OK")
PY
```

判据：没有任何具体算法实现模块的静态 import 或包入口属性；实际输出：

```text
NO-ALGORITHM-IMPORTS-OK
```

### 8.6 已删除符号防回退

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
import harmonica_eval.algorithms as A
from pathlib import Path

path = Path("harmonica_eval/algorithms/__init__.py")
source = path.read_text(encoding="utf-8")
forbidden = ("ALGORITHMS", "PAYLOAD_SCHEMAS", "assert_registry_integrity")
present = [name for name in forbidden if name in source or hasattr(A, name)]
assert present == [], present
print("LEGACY-SYMBOLS-OK", len(forbidden), "guarded")
PY
```

判据：源码文本与模块属性均不得重新出现这三个符号；实际输出：

```text
LEGACY-SYMBOLS-OK 3 guarded
```

### 8.7 行数宽松上界

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
from pathlib import Path

path = Path("harmonica_eval/algorithms/__init__.py")
line_count = len(path.read_text(encoding="utf-8").splitlines())
assert 0 < line_count <= 100, line_count
print("LINE-COUNT-OK", line_count, "<= 100")
PY
```

判据：文件非空且行数不超过 100；不要求恰好 55 行；实际输出：

```text
LINE-COUNT-OK 55 <= 100
```

### 8.8 零实现泄漏

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
import ast
from pathlib import Path

path = Path("harmonica_eval/algorithms/__init__.py")
tree = ast.parse(path.read_text(encoding="utf-8"))
leaks = []
for node in ast.walk(tree):
    if isinstance(node, ast.Pass):
        leaks.append((node.lineno, "pass"))
    elif (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and node.value.value is Ellipsis
    ):
        leaks.append((node.lineno, "..."))
    elif isinstance(node, ast.Return) and (
        node.value is None
        or (
            isinstance(node.value, ast.Constant)
            and node.value.value is None
        )
    ):
        leaks.append((node.lineno, "return None"))
assert leaks == [], leaks
print("ZERO-IMPLEMENTATION-OK")
PY
```

判据：没有 `pass`、裸 `...` 表达式或 `return None`；实际输出：

```text
ZERO-IMPLEMENTATION-OK
```

### 8.9 判据清单

- [ ] §8.1 退出码为 0，解释器版本为上面记录的实际版本。
- [ ] §8.2 输出 `EXPORTS-OK ['InputRequirement', 'PluginSpec', 'Registry']`。
- [ ] §8.3 输出 `PLAQUE-OK 10 fields`。
- [ ] §8.4 输出 `DEPENDENCIES-OK __future__ + ..contract + .registry; no core/host/cockpit`。
- [ ] §8.5 输出 `NO-ALGORITHM-IMPORTS-OK`。
- [ ] §8.6 输出 `LEGACY-SYMBOLS-OK 3 guarded`。
- [ ] §8.7 输出 `LINE-COUNT-OK 55 <= 100`（未来实现只需满足 `0 < 行数 <= 100`）。
- [ ] §8.8 输出 `ZERO-IMPLEMENTATION-OK`。
- [ ] 以上命令均无 traceback，且只验证本文件，不修改源码。

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- 产物路径：`harmonica_eval/algorithms/__init__.py`（完整文件）。
- 解释器证据：`python --version` 原文。

```text
Python 3.13.13
```

- §8.2 完整 stdout：

```text
EXPORTS-OK ['InputRequirement', 'PluginSpec', 'Registry']
```

- §8.3 完整 stdout：

```text
PLAQUE-OK 10 fields
```

- §8.4 完整 stdout：

```text
DEPENDENCIES-OK __future__ + ..contract + .registry; no core/host/cockpit
```

- §8.5 完整 stdout：

```text
NO-ALGORITHM-IMPORTS-OK
```

- §8.6 完整 stdout：

```text
LEGACY-SYMBOLS-OK 3 guarded
```

- §8.7 完整 stdout：

```text
LINE-COUNT-OK 55 <= 100
```

- §8.8 完整 stdout：

```text
ZERO-IMPLEMENTATION-OK
```

- `git diff --check` 应无输出、退出码为 0。
- 本文件不产出数值，因此无黄金数值向量；§8 的 stdout 即本文件的验收证据。

---

## 10 · ★ 何时必须停止并上报（§22 硬失败对策）

出现下列任一情况，停止实现，不自行设计替代方案：

1. 需要改变 `PluginSpec`、`InputRequirement`、`Registry` 或 `AlgorithmResultEnvelope` 的现有契约。
2. 需要在 `algorithms/__init__.py` 之外的文件中新增、删除或迁移注册行为。
3. 需要让本文件知道具体算法、具体入口、端口集合或 payload 字段集合。
4. 需要引入 §3 清单以外的 import、第三方包、I/O、网络、日志或动态加载。
5. 需要增加本文件之外的公开符号、错误码、端口、阈值或兼容分支。
6. 发现本文件与 `contract.py`、`registry.py` 或 C1 装配点的实际形状冲突。
7. 发现 §8 任一判据无法在不修改其他文件的情况下通过。
8. 发现验收命令自身无法解析当前目标文件，或运行环境不满足命令前置。

不得先写 workaround，不得以兼容别名恢复已删除结构，不得静默缩小范围。停止时使用以下格式：

```text
MOLD BREAK
- 文件 ID：FILE-200
- 触发条款：§10 第 <n> 条
- 我在做什么：
- 卡在哪：
- 实际需要 vs 规格给出：
- 为什么无法在不做上层设计的前提下继续：
- 建议的上游处理位置：
```

若实际契约与本规格冲突，使用：

```text
GATE CHALLENGE
- 相关 Requirement：
- 相关 Build Instruction 章节：
- 实际需要 vs 规格给出：
- 为什么冲突：
- 复现证据：
- 建议的上游处理位置：
```

---

## 附：本文件的公开接口速查

| 项目 | 格式 / 内容 | 来源 |
| --- | --- | --- |
| 模块 | `harmonica_eval.algorithms` | 目标文件 |
| 公开出口 | `InputRequirement` · `PluginSpec` · `Registry` | §4.1–§4.3 |
| `__all__` | `["InputRequirement", "PluginSpec", "Registry"]` | §4.3 |
| 契约类型来源 | `..contract.InputRequirement` / `..contract.PluginSpec` | §3–§4.1 |
| 注册表类型来源 | `.registry.Registry` | §3–§4.2 |
| 允许的标准库 import | `__future__.annotations` | §3 |
| 允许的本包 import | `..contract`、`.registry` | §3 |
| 禁止的跨层 import | `core` / `host` / `cockpit` | §3、§8.4 |
| 禁止的具体实现 import | `.pitch` / `.timing` / `.dynamics` 及其他算法模块 | §3、§8.5 |
| 铭牌字段数 | 10 个标准字段 | §4.0、§8.3 |
| 行数判据 | `0 < 行数 <= 100` | §8.7 |
| 失败传播 | 依赖错误原样传播，不 fallback | §5 |
| 注册职责 | C1 `build_default_app()` 显式调用 `Registry.register` | §2、§4.4–§4.5 |
| 数值输出 | 无 | §9 |
