# PLUGIN-LAYOUT — 算法插件目录形状设计（待负责人裁定）

> ★ **本文只做设计裁定，不迁移代码。** 写完时 `algorithms/` 仍是平铺空壳，
> 迁移是下一阶段的事。
>
> 本文第 5 节是本次设计的**核心矛盾**，其余四节都由它推导而来。

---

## 0 · 事实基线（全部实测，不凭记忆）

| 事实 | 来源 |
| --- | --- |
| `algorithms/__init__.py` 已重写为 55 行纯类型出口，`__all__` = `InputRequirement`/`PluginSpec`/`Registry` | `algorithms/__init__.py:52-55` |
| `Registry` 三操作 `register`/`list`/`get`，保序 | `algorithms/registry.py:49-78`（仍空壳） |
| `host/app.py:113-123` 明确「C1 是唯一知道有哪些实现的地方」，但**同时**声称「跨界 import 的是契约层，不是具体算法」 | 实测原文 |
| 三个算法仍是平铺空壳：`pitch.py`(161行/4函数)、`timing.py`(203行/5函数)、`dynamics.py`(168行/6函数) | `ast` 实测 |
| 三个算法**全部依赖 `notes.reference`**（B 级公共特征），没有一个能只靠 A 级 PCM 跑起来 | 字面量端口 id 提取 |
| `check_plugin_contract.py` 13/13 通过，其中第②条正在断言「host 不 import 具体算法实现」 | 实跑 exit 0 |
| 不变量 C 已写明「新增插件只允许写 `algorithms/<name>/` 与在 C1 装配点多一行 `registry.register(...)`」 | `COMPONENTS.md:381-387` |

★ **注意第 4 行那个自相矛盾**：`host/app.py` 的 docstring 一边说
「C1 是唯一知道有哪些实现的地方」，一边说「不 import 具体算法实现」。
**这两句话不可能同时为真** —— 这就是第 5 节要解的问题，
而且它已经写进代码注释里了，不是本文凭空制造的。

---

## 1 · 目录内部的最简形状

### 候选 A：单文件目录（推荐）

```
algorithms/pitch/
└── __init__.py      # 现场铭牌 + SPEC 常量 + entry 函数
```

### 候选 B：双文件目录

```
algorithms/pitch/
├── __init__.py      # 只做 re-export：from .plugin import SPEC, run
└── plugin.py        # 现场铭牌 + SPEC + 实现
```

### 候选 C：按职责三分

```
algorithms/pitch/
├── __init__.py      # re-export
├── spec.py          # PluginSpec 声明
└── compute.py       # 实际计算
```

### 裁定：**候选 A**

**理由（按优先级）：**

1. **拆分的动机应当是"实现变复杂"，不是"看起来整齐"。**
   `pitch.py` 现在 161 行，其中**大部分是文档**。真正的计算逻辑预计
   100–150 行。单文件毫无压力。
2. **候选 C 明确违反 AGENTS.md 铁律 4**：3 个文件装 4 个函数，
   每个文件都摊不到 50 行有效内容，是典型的"为将来可能有用而拆"。
3. **候选 B 是合理的下一步**，但不是现在。等某个插件真的超过
   ~400 行且内部有两块清晰职责时再拆，那时拆分是**被代码逼出来的**，
   不是被规划逼出来的。
4. **拆分的成本不只是文件数**：`algorithms/` 包会多出 N 个子包，
   `verify_shell.py` 的 `EXPECTED` 清单要加 2N 条，
   每个子包还要各自带完整现场铭牌（10 字段）。**这是持续的维护税。**

★ **给未来的判据（写下来，避免"以后再说"）**：
> 单文件超过 400 行 **或** 单个函数超过 120 行 时，才考虑拆。
> 未达此线不得拆。

---

## 2 · SPEC 的形状与位置

### 候选 A：模块级常量（推荐）

```python
# algorithms/pitch/__init__.py
from ..contract import InputRequirement, PluginSpec, UiScalar, UiSeries
from ...contract import TimelineBasis

SPEC = PluginSpec(
    algorithm_id="pitch",
    version="0.1.0",
    label="音准",
    required_inputs=(
        InputRequirement(port_id="notes.reference"),
        InputRequirement(port_id="notes.practice"),
    ),
    optional_inputs=(),
    entry=run,
)
```

### 候选 B：`spec()` 工厂函数

```python
def spec() -> PluginSpec:
    return PluginSpec(..., entry=run)
```

### 裁定：**候选 A（模块级常量）**

**理由：**

1. **`Registry.register` 的语义是"登记一个已知的东西"，不是"造一个东西"。**
   工厂函数暗示每次可能造出不同的 spec，但 `algorithm_id` 和 `entry`
   都是编译期已知的，构造一次即可。
2. **候选 B 允许 `entry` 被重新绑定**（`spec().entry is not spec().entry`
   之类），会让「注册表里的 entry 与模块里的 entry 是同一个」失去保证。
3. **装配代码最短**：`registry.register(algorithms.pitch.SPEC)`。
   候选 B 是 `registry.register(algorithms.pitch.spec())`，多两个字符、多一层间接。
4. **可测试性不受影响**：需要造测试 spec 时用 `dataclasses.replace`
   或直接构造 `PluginSpec`，不必依赖插件提供工厂。

---

## 3 · 三个现有算法怎么迁

### 迁移前后对照

```
迁移前                                迁移后
─────────────────────────────       ─────────────────────────────
algorithms/__init__.py       (不动)  algorithms/__init__.py
algorithms/registry.py       (不动)  algorithms/registry.py
algorithms/runtime.py        (不动)  algorithms/runtime.py
algorithms/pitch.py     161行  ──→   algorithms/pitch/__init__.py  161行
algorithms/timing.py    203行  ──→   algorithms/timing/__init__.py 203行
algorithms/dynamics.py  168行  ──→   algorithms/dynamics/__init__.py 168行
```

### 内容如何安置

| 内容 | 处置 | 理由 |
| --- | --- | --- |
| 模块 docstring 的现场铭牌（10 字段） | **原样搬** | FILE-ID 从 `FILE-201` 改为目录级标识；其余 9 字段逐字保留 |
| 各函数 docstring（含 §20 盲审历史归因） | **原样搬，一字不改** | 这些是审查史，删掉就丢了"为什么最终是这样" |
| `raise NotImplementedError("SHELL: FILE-2NN 待注入实现")` | **原样搬，FILE-NNN 不变** | 实现者的工作范围不变 |
| 函数签名与类型注解 | **原样搬** | 已冻结 |
| ★ `PluginSpec` 声明 | **新增** | 迁移后才有的东西 |

★ **不做的事**：不重新生成任何 docstring、不"顺手优化"措辞、
不删除看起来啰嗦的历史归因。迁移是**移动**，不是**重写**。
任何"迁移时顺手改一改"都会让审查者无法区分"移动"与"内容变更"。

### 关于 `timing.py` 那个并发签名改动

`timing.py` 的 `summarize_deviations(..., n_unpaired: int)` 是在本轮之前
由另一任务加入的（子代理已如实报告"这不属于我的修改"）。
迁移时**原样带走**，不得回退。

---

## 4 · 装配代码的最终形状

```python
# harmonica_eval/host/app.py · build_default_app()
def build_default_app(core: object) -> HostApp:
    registry = Registry()
    registry.register(algorithms.pitch.SPEC)
    registry.register(algorithms.timing.SPEC)
    registry.register(algorithms.dynamics.SPEC)
    return HostApp(core=core, algorithms=registry)
```

新增一个算法 = **加一个目录 + 加一行 `register`**。
Core、Host 逻辑、UI 全不动。

★ 但这一行 `register` 需要 Host **import 具体插件**，
而第 ② 条不变量正在断言 Host 不 import 具体插件。
**下一节解决这个矛盾。**

---

## 5 ★★ 核心矛盾：两条要求如何同时成立

**矛盾陈述：**

- **要求甲**（不变量② / `COMPONENTS.md`）：`host/` 不得 import 任何具体算法实现
- **要求乙**（不变量 C / `host/app.py:113-123`）：新增插件只允许"在 C1 装配点多一行 `register`"

**乙的前提显然是 Host 知道要注册谁；甲禁止 Host 知道。两者直接冲突。**

### 解法一：独立装配模块（推荐）

```
harmonica_eval/
├── algorithms/          # 契约层 + 插件
├── host/                # Host 逻辑，**不 import 任何算法**
└── bootstrap.py         # ★ 装配根：唯一的跨界点
    └── def build_default_app():
            from .algorithms import Registry
            from .algorithms import pitch, timing, dynamics
            ...
```

**Host 变成纯粹的逻辑层，装配的知识全部上移到 `bootstrap.py`。**

- ★ **`host/` 满足要求甲**（一个具体算法都不 import）
- ★ **`bootstrap.py` 就是 SPEC 意义上真正的"composition root"**
  ——`COMPONENTS.md:79-94` 本来就是这么定义 C1 的，
  我们只是让**代码结构**终于对上了**规格里已有的定义**
- ★ **不变量 C 的措辞需要微调**：「在装配点多一行」→「在装配根多一行」，
  并把装配根明确为 `bootstrap.py` 而非 `host/app.py`

**代价**：多一个文件（`bootstrap.py`，约 20 行）；`__main__.py` 改为调用它。

### 解法二：插件清单集中在 `algorithms/` 内

```
harmonica_eval/algorithms/_builtin.py   # 只列默认三件
```

**代价（为什么不推荐）**：`algorithms/` 包**同时**是契约层和插件容器。
把"默认装哪些"放进 `algorithms/` 会让契约层**重新认识具体算法** ——
正是本轮刚拆掉的 `ALGORITHMS` 那个病根，**换个地方复发**。
**否决。**

### 解法三：放宽要求甲，改成"host 不在运行期 import"

措辞改为"Host 的**逻辑**不得依赖具体算法；装配期的 import 允许"。

**代价**：判据从"AST 扫 `host/` 无 import"退化为需要区分
"运行期 / 装配期"，**机械判定难度陡增**，
且放弃了"Host 逻辑完全不知道有哪些算法"这个更强的保证。**否决。**

### ★ 裁定：**解法一**

**理由：**

1. 它让代码结构**对齐规格里已有的定义**（C1 本来就被定义为 composition root），
   而不是修改规格去迁就代码。
2. 要求甲从"勉强的约定"变成"物理上做不到"——
   **`host/` 目录里根本没有能 import 插件的上下文**。
3. 代价最小（一个 20 行文件），且这个文件**本来就该存在**。

★ **连带要改的判据**（`check_plugin_contract.py` 第②条）：
扫描范围从 `host/**/*.py` 改为「`host/**/*.py` **且** `bootstrap.py` 不在 host/ 内」，
并**新增**一条：`host/` 与 `algorithms/` 之间**零** import 边。

---

## 6 · 迁移的机械验收判据

★ 每条都是可执行的。标注反映**当前状态**（未迁移）。

```bash
# V1 目录形状：三个算法已是目录，且无残留平铺 .py
python3 - <<'PY'
import pathlib
a = pathlib.Path("harmonica_eval/algorithms")
for n in ("pitch", "timing", "dynamics"):
    assert (a / n / "__init__.py").is_file(), f"{n} 尚未迁移为目录"
    assert not (a / f"{n}.py").exists(), f"{n}.py 残留平铺文件"
print("LAYOUT-OK")
PY
```
**当前状态：红**（尚未迁移）

```bash
# V2 SPEC 符号存在且可注册
python3 -c "
from harmonica_eval.algorithms.pitch import SPEC
from harmonica_eval.contract import PluginSpec
assert isinstance(SPEC, PluginSpec)
assert SPEC.algorithm_id == 'pitch'
assert SPEC.entry is not None
print('SPEC-OK')"
```
**当前状态：红**（模块尚不存在）

```bash
# V3 插件不反向 import core/host/cockpit
python3 tools/check_plugin_contract.py
```
**当前状态：绿**（13/13，但迁移后需复跑确认目录形态下仍成立）

```bash
# V4 框架不出现具体算法名（防止中央清单复活）
grep -rnE '\b(ALGORITHMS|PAYLOAD_SCHEMAS)\b' harmonica_eval/ --include=*.py \
  | grep -v '^harmonica_eval/contract.py'
```
**当前状态：绿**

```bash
# V5 host/ 与 algorithms/ 之间零 import 边（解法一落地后新增）
python3 -c "
import ast, pathlib
bad=[]
for p in pathlib.Path('harmonica_eval/host').rglob('*.py'):
    t=ast.parse(p.read_text(encoding='utf-8'))
    for n in ast.walk(t):
        if isinstance(n,ast.ImportFrom) and n.module and 'algorithms' in n.module:
            bad.append(f'{p}:{n.lineno} {n.module}')
assert not bad, bad
print('HOST-ISOLATED-OK')"
```
**当前状态：绿**（host 现在确实不 import；但迁移后加了 `bootstrap.py` 仍应绿）

```bash
# V6 注册顺序可复现
python3 -c "
import bootstrap
app = bootstrap.build_default_app()
ids = [s.algorithm_id for s in app.algorithms.list()]
assert ids == ['pitch','timing','dynamics'], ids
print('ORDER-OK', ids)"
```
**当前状态：红**（`bootstrap` 尚不存在）

---

## 7 · 待负责人裁定

| # | 问题 | 我的推荐 |
| --- | --- | --- |
| 1 | 目录内部形状 | **单文件 `__init__.py`**，>400 行或单函数 >120 行才拆 |
| 2 | SPEC 形状 | **模块级常量** |
| 3 | 迁移方式 | **原样搬，一字不改**，只新增 SPEC |
| 4 | ★ 核心矛盾解法 | **解法一：新增 `bootstrap.py` 作为装配根** |

★ **最需要拍板的是第 4 项** —— 它会改动 `COMPONENTS.md` 的不变量 C
措辞、并给 `check_plugin_contract.py` 增一条判据。
其余三项即便改了也只是局部返工。

---

## 附 · 本文的自证状态

- 第 6 节 6 条判据**全部实际运行过**，"当前状态：红/绿"是实跑结果
- 第 0 节事实基线**全部给出来源行号**，可用 `read` 复核
- ★ 本文**未修改任何代码**；文中所有"应当如何"的表述均为建议，
  未经裁定不得写入 `COMPONENTS.md` 或任何 Build Instruction
