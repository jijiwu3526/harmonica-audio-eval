# FILE-204 — `harmonica_eval/algorithms/registry.py`

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/algorithms/registry.py`
> 生成依据：
> - `harmonica_eval/algorithms/registry.py`@v1（78 行壳件，含现场铭牌、`Registry`、三个空方法）
> - `harmonica_eval/contract.py` 的 `PluginSpec`
> - `harmonica_eval/host/app.py` 的 `run_algorithms` 调用点说明
> - `COMPONENTS.md`@v2 §3 COMP-C3
> - SHELL-STANDARD v1
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-204 |
| 所属组件 | COMP-C3 Algorithm |
| 层级 | L3（symbol / implementation） |
| 上游 | C1 `harmonica_eval.host.app.HostApp` 的装配点：装配期显式调用 `Registry.register(spec)`；查询时由 C1 调用 `list()` / `get(algorithm_id)` |
| 下游 | `harmonica_eval.contract.PluginSpec`；结果供 C1 的编排逻辑读取，不直接运行插件入口 |
| 同层邻居 | `harmonica_eval/algorithms/runtime.py`（执行期输入解析）、`harmonica_eval/algorithms/__init__.py`（类型出口）、`pitch.py` / `timing.py` / `dynamics.py`（具体插件，均不是本文件的依赖） |

**你的权限**：只实现本文件 `harmonica_eval/algorithms/registry.py` 的三个既有空方法。
不得修改 `contract.py`、`host/`、`core/`、`cockpit/`、任何具体算法模块或其他 `.py` 文件；
不得修改壳件中的现场铭牌、docstring、签名、`__all__` 或 import 声明。

C2 完全不知道本文件存在；本文件也不管理 C1 的会话、Core 的数据面或 C4 的界面。

---

## 2 · 这个文件为什么存在

追溯：Product Intent「双音频对比 → 客观数值指标」；架构承诺「换算法不改核心」。

本文件是算法插件清单的**唯一显式登记处**。装配期把每个 `PluginSpec` 交给
`Registry`，运行期只从 Registry 读取「有哪些插件」以及某个标识对应的规格。
框架因此不需要目录扫描、entry-points、动态发现或认识某个具体算法。

**删掉它会坏掉什么**（逐条列出）：

1. C1 失去插件清单来源 → 无法枚举插件、无法按装配顺序调用入口，也无法回答某个 `algorithm_id` 是否已登记。
2. C1 失去统一查询边界 → 只能让每个具体模块各自暴露清单，新增插件会反向修改框架文件。
3. 运行顺序失去事实来源 → 若 C1 依据字典、目录或扫描结果排序，报告顺序会随实现细节变化，无法复现。
4. 重复 `algorithm_id` 的失败不再在登记边界暴露 → 错误可能被推迟到某个算法运行或结果解释阶段。
5. “新增算法不改核心”退化为口头约定 → 插件装配会重新依赖具体算法模块，C2/C3 的深组件边界被穿透。

★ **保序裁定**：`list()` 必须返回 tuple，顺序必须等于成功 `register()` 的调用顺序。
**为什么**：C1 的 `run_algorithms` 已冻结「返回顺序与注册顺序一致」；任何其它顺序都会让
`metrics.json` / 报告中的结果顺序不可复现。这里不规定内部如何保存，只规定可观察行为。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import（穷举，清单外一律禁止）**：

- Python 标准库：`from __future__ import annotations`（壳件已有）。
- 第三方：**无**。
- 本包内：`from ..contract import PluginSpec`（壳件已有；本文件只依赖这个契约类型）。
- 已有公开出口：`__all__ = ["Registry"]`，不得增删。

**禁止 import**：

- `harmonica_eval.core`、`harmonica_eval.host`、`harmonica_eval.cockpit` 的任何模块或任何相对路径。
- 具体算法模块 `.pitch`、`.timing`、`.dynamics`，以及 `algorithms` 包内的其它实现。
- `importlib`、`pkgutil`、`importlib.metadata`、entry-points 读取、目录扫描等任何动态发现机制。
- `os`、`sys`、`pathlib`、文件 I/O、网络模块、日志模块、第三方包。
- 任何清单外的包内或标准库模块。需要新依赖 → 停止并转 §10。

**依赖方向的原因**：C3 只经 `contract.PluginSpec` 接收插件声明；一旦本文件知道
具体算法、Core 或 Host，新增插件就会反向要求框架改动，违反「换算法不改核心」。

---

## 4 · 你要实现什么（行为规格）

### 4.0 壳件中已存在的冻结内容

壳件 `harmonica_eval/algorithms/registry.py` 已写定并**冻结**：

- 模块 docstring 的全部现场铭牌与裁定文字；
- `from __future__ import annotations`、`from ..contract import PluginSpec`；
- `__all__ = ["Registry"]`；
- `Registry` 的类 docstring；
- `register` / `list` / `get` 的方法名、参数名、参数注解、返回注解与 docstring。

实现者只把三处 `raise NotImplementedError("SHELL: FILE-204 待注入实现")`
替换为对应行为。不得把方法改成属性、不得添加默认参数、不得改名、不得改返回注解。
不得在模块级调用 Registry 构造器或建立进程级共享单例。

### 4.1 `Registry` 的对象边界

- **公开类**：只公开一个类 `Registry`。
- **公开操作**：只有 `register`、`list`、`get` 三个操作。
- **实例状态**：每个 `Registry` 实例独立保存自己的登记结果；不读写模块级可变全局，
  不跨实例共享状态。
- **输入对象**：`PluginSpec` 是跨组件契约；本文件不复制、修改或重新解释其字段。
- **不做插件发现**：Registry 不读目录、entry-points、环境变量或 manifest。
- **不做兼容性判断**：Registry 不知道 `SurfaceManifest`，不调用 `compatible_with`。
- **不运行入口**：不调用 `PluginSpec.entry`，不读取端口，不生成结果。

### 4.2 `register(self, spec: PluginSpec) -> None`

- **输入**：恰好一个 `PluginSpec`；插件身份以 `spec.algorithm_id` 为稳定标识。
- **输出**：成功时返回 `None`。
- **成功行为**：登记该规格，使其随后可由 `list()` 与 `get(spec.algorithm_id)` 读到；
  该次调用追加到可观察的注册顺序末尾。
- **重复行为**：若同一 `algorithm_id` 已经成功登记，必须显式失败；不得静默覆盖、替换、
  追加第二份，也不得把重复当作成功。
- **顺序行为**：重复失败不改变已经形成的成功登记顺序。
- **不做的事**：不检查 manifest、端口、算法入口是否可调用、运行环境或文件是否存在；
  这些不是 Registry 的职责。
- **不变量**：成功登记后 `get(spec.algorithm_id)` 能找到同一逻辑规格；`list()` 中每项只出现一次。

### 4.3 `list(self) -> tuple[PluginSpec, ...]`

- **输入**：无参数。
- **输出**：始终为 `tuple`，不是 `dict`、`list` 或其它映射容器。
- **顺序**：元素顺序严格等于成功 `register()` 的调用顺序；不排序、不按字母重排、
  不按插件名分组、不因重复查询而改变顺序。
- **空状态**：没有成功登记时返回空 tuple `()`。
- **形状**：只返回已登记的 `PluginSpec`；不附带运行期状态、manifest 或兼容性结论。
- **不变量**：连续调用之间顺序与成员不因读取而改变；返回对象满足 tuple 契约。

★ 不得用字典的迭代顺序作为本方法的顺序来源。C1 已经把注册顺序冻结为报告顺序事实，
本方法必须把该事实原样传递出去。

### 4.4 `get(self, algorithm_id: str) -> PluginSpec | None`

- **输入**：一个不透明且稳定的 `algorithm_id: str`；本文件不解析其前后缀。
- **输出**：已登记时返回对应的 `PluginSpec`；未登记时返回 `None`。
- **未命中语义**：缺失是可回答的查询结果，不抛异常、不返回空容器、不返回 False。
- **查询边界**：只按 `algorithm_id` 查找；不判断 required / optional 输入，不比较 manifest。
- **复杂度目标**：查找目标为 O(1)。如何实现由实现者决定，但不得引入线性扫描作为唯一路径。
- **不变量**：返回的规格必须是 `list()` 中同一标识的那一项；重复登记不会产生多个答案。

### 4.5 未来注入时的实现格式

- 三个既有空方法各自替换为完整函数体；保留原签名与 docstring。
- 私有实例状态、私有辅助方法可以在本文件内按实现需要添加，但不得产生新的公开操作或
  新的对外符号。
- 所有异常必须显式表达失败；不得通过返回 False、错误列表、打印后继续或吞异常来替代失败。
- 不得在本文件自行决定端口、错误码、Host 策略或插件执行策略；这些不属于本文件。
- 若发现需要改变上述公开行为、顺序或依赖方向，停止并按 §10 上报。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| `register` 遇到已登记的 `algorithm_id` | 显式失败，保留先前登记，不覆盖 | 抛出显式异常；消息应能定位该 `algorithm_id` |
| `register` 成功 | 追加一项，之后可由 `list` / `get` 读到 | 返回 `None` |
| `list` 在空 Registry 上调用 | 返回空 tuple | `()` |
| `get` 命中 | 返回登记的同一规格 | `PluginSpec` |
| `get` 未命中 | 把“没有这个插件”作为正常查询结果 | `None` |
| 输入不是 `PluginSpec` 或契约对象被破坏 | 不做静默转换、不伪造规格 | 按调用方契约失败；如需新兼容规则，停止并转 §10 |
| 依赖 import 失败 | 原异常向上冒泡，不降级、不改成空 Registry | 原始 import 异常 |
| 未预期的内部异常 | 不得 `except Exception: pass` 后假装成功 | 保留可诊断失败；具体异常组织不得新增错误码 |

★ 宪章 §5.6：禁止静默降级。重复登记不能被覆盖、丢弃或伪装成成功；查询未命中才返回 `None`。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-204-1 | Registry 只有 `register` / `list` / `get` 三个公开操作 | §8.2 的调用检查 + §8.3 AST |
| INV-204-2 | `list()` 返回 `tuple[PluginSpec, ...]`，顺序等于成功注册顺序 | §8.3 签名 AST；注入后由行为验收覆盖 |
| INV-204-3 | `get()` 对未登记标识返回 `None`，不抛“未找到”异常 | §8.2 空壳门禁；注入后由行为验收覆盖 |
| INV-204-4 | 重复 `algorithm_id` 显式失败，不覆盖旧值 | 注入后负向行为验收；空壳期由 §8.2 验证占位仍完整 |
| INV-204-5 | `get()` 的目标复杂度为 O(1) | 注入后规模/调用路径检查；不由本轮空壳伪造数值结论 |
| INV-204-6 | 只依赖 `contract.PluginSpec`，不依赖具体算法或 C1/C2/C4 | §8.2 / §8.3 import AST 与 grep |
| INV-204-7 | 不扫描目录、不读 entry-points、不动态发现 | §8.2 import AST + §8.3 文本/代码检查 |
| INV-204-8 | 不提供 `unregister`、`enable` / `disable`、`compatible_with` | §8.3 公开方法 AST |
| INV-204-9 | 不持有 Host / Session 启停或兼容性决策 | §8.2 import 方向 + §8.3 公开面 |
| INV-204-10 | 三个方法的签名与壳件逐字一致 | §8.3 AST |
| INV-204-11 | 模块 docstring 保留全部 10 个现场字段 | §8.2 nameplate 断言 |
| INV-204-12 | 三个占位 raise 消息均含 `FILE-204`，证明文件仍是可注入空壳 | §8.2 |

---

## 7 · 边界（明确不做）

- **不提供 `unregister`**。插件在装配期登记一次，运行期集合不变；提供删除操作会把本文件
  变成动态管理设施，超出 v0.1 边界。
- **不提供 `enable` / `disable`**。启停属于 Host / Session 配置；Registry 只回答“有什么”，
  Host 决定“这次跑哪些”。
- **不提供 `compatible_with()`**。兼容性需要 `SurfaceManifest`；Registry 不知道 surface，
  该判断属于 runtime / C1 编排边界。
- **不扫描目录、不读 entry-points、不使用 `importlib` 动态发现**。显式 `register` 是唯一登记入口，
  否则结果集合会随环境变化而不可复现。
- **不 import 或保存具体算法模块**。新增插件只增加装配调用，不要求本文件知道插件实现。
- **不运行 `PluginSpec.entry`**，不读取端口、不计算指标、不访问音频或文件系统。
- **不把 `list()` 返回 dict / list**，不排序、不以字母顺序替代注册顺序。
- **不新增公开方法、异常类、错误码、常量、模块级全局或兼容别名**。
- **不修改任何其他文件**。需要新错误语义、依赖或接口 → 停止并转 §10。

---

## 8 · 怎么验证你写对了

本轮对象是**尚未注入实现的冻结空壳**。因此 §8 的命令是“模具完整性验收”：
它们必须在当前空壳上真实通过；空壳性是未来注入前必须先被证明的条件。

### 8.1 运行环境

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python --version
```

判据：命令退出码为 0；实际输出写入 §9 证据包。

### 8.2 注入后行为、依赖方向与铭牌

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
import ast
from pathlib import Path
from harmonica_eval.algorithms.registry import Registry
from harmonica_eval.contract import PluginSpec

path = Path('harmonica_eval/algorithms/registry.py')
tree = ast.parse(path.read_text(encoding='utf-8'))
registry = Registry()

# ── 注入后行为验收（替代原「空壳必须抛 FILE-204」判据）──
# 1) 空表：list() 返回空 tuple，get() 未命中返回 None（不是抛错）
assert registry.list() == (), registry.list()
assert registry.get('missing') is None
# 2) 保序：按 register 顺序返回，dict 实现不得打乱
def _spec(aid: str) -> PluginSpec:
    return PluginSpec(algorithm_id=aid, algorithm_version='1.0.0', label=aid,
                      required_inputs=(), optional_inputs=(), entry=lambda s: None)
for aid in ('zebra', 'alpha', 'middle'):
    registry.register(_spec(aid))
assert [s.algorithm_id for s in registry.list()] == ['zebra', 'alpha', 'middle'], registry.list()
# 3) O(1) 查询：get 命中的必须是**同一对象**
got = registry.get('alpha')
assert got is registry.list()[1], got
# 4) 重复登记必须显式失败，且不得静默覆盖旧值
before = len(registry.list())
try:
    registry.register(_spec('alpha'))
except Exception as exc:
    assert 'alpha' in str(exc), str(exc)
    print(f'duplicate rejected: {exc}')
else:
    raise AssertionError('duplicate register did not raise')
assert len(registry.list()) == before, '旧值被覆盖了'
print('REGISTRY-BEHAVIOR-OK')

for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            assert alias.name.split('.')[0] not in {'core', 'host', 'cockpit'}, alias.name
            assert not alias.name.startswith('harmonica_eval.algorithms.pitch'), alias.name
            assert not alias.name.startswith('harmonica_eval.algorithms.timing'), alias.name
            assert not alias.name.startswith('harmonica_eval.algorithms.dynamics'), alias.name
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ''
        if node.level == 0:
            assert module.split('.')[0] not in {'core', 'host', 'cockpit'}, module
        else:
            assert module not in {'core', 'host', 'cockpit', 'pitch', 'timing', 'dynamics'}, module
print('REGISTRY-DEPENDENCY-OK')

doc = ast.get_docstring(tree)
fields = ('FILE-ID:', 'COMPONENT:', 'SPEC:', 'ROLE:', 'INTENT:', 'MUST:', 'MUST NOT:', 'INPUT:', 'OUTPUT:', 'BUILD-INSTRUCTION:')
missing = [field for field in fields if field not in doc]
assert not missing, missing
print('REGISTRY-NAMEPLATE-OK 10')
PY
```

判据：退出码为 0；输出含 `REGISTRY-BEHAVIOR-OK`（含 `duplicate rejected:` 一行）、
`REGISTRY-DEPENDENCY-OK`、`REGISTRY-NAMEPLATE-OK 10`；没有 traceback。
★ **比原判据更严**：原判据只验证「未注入时抛 FILE-204」；
★ 本判据验证 **5 项真实行为** —— 空表返回空 tuple、`get` 未命中返 `None`、
★ **保序**（故意用 `zebra / alpha / middle` 这类非字典序，
★ 让任何"排序冒充顺序"的实现立刻暴露）、`get` 命中同一对象、
★ 重复登记失败**且旧值未被覆盖**。
★ 依赖方向与铭牌两段从原判据原样保留（注入后仍必须成立）。

### 8.3 签名一致性与公开面

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
import ast
from pathlib import Path

path = Path('harmonica_eval/algorithms/registry.py')
tree = ast.parse(path.read_text(encoding='utf-8'))
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Registry')
expected = {
    'register': ([('self', None), ('spec', 'PluginSpec')], 'None'),
    'list': ([('self', None)], 'tuple[PluginSpec, ...]'),
    'get': ([('self', None), ('algorithm_id', 'str')], 'PluginSpec | None'),
}
actual = {}
for node in cls.body:
    if isinstance(node, ast.FunctionDef) and node.name in expected:
        actual[node.name] = (
            [(arg.arg, ast.unparse(arg.annotation) if arg.annotation else None) for arg in node.args.args],
            ast.unparse(node.returns) if node.returns else None,
        )
assert actual == expected, (actual, expected)
assert not any(isinstance(n, ast.FunctionDef) and n.name in {'unregister', 'enable', 'disable', 'compatible_with'} for n in cls.body)
assert ast.unparse(next(n.value for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__all__' for t in n.targets))) == "['Registry']"
print(actual)
print('REGISTRY-SIGNATURE-OK')
PY
```

判据：退出码为 0；三个签名与壳件逐字一致；`__all__` 仅为 `Registry`；
类内不存在四个被明确排除的操作；输出末行 `REGISTRY-SIGNATURE-OK`。

### 8.4 依赖方向 grep

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
if grep -nE '^[[:space:]]*(from|import)[[:space:]].*(core|host|cockpit|pitch|timing|dynamics)' harmonica_eval/algorithms/registry.py; then
  echo 'REGISTRY-DEPENDENCY-FAIL'
  exit 1
else
  echo 'REGISTRY-DEPENDENCY-OK'
fi
```

判据：退出码为 0，且唯一输出为 `REGISTRY-DEPENDENCY-OK`。
该命令只检查 import 行；不把模块 docstring 中讨论 C2/C1/C4 的文字误判为依赖。

### 8.5 判据清单

- [ ] §8.2 三个方法都抛 `NotImplementedError`，消息均含 `FILE-204`。
- [ ] §8.2 的依赖方向与 10 字段铭牌断言全部通过，末行 `REGISTRY-SHELL-OK`。
- [ ] §8.3 的三个签名、返回注解与 `__all__` 全部匹配，末行 `REGISTRY-SIGNATURE-OK`。
- [ ] §8.4 的 grep 无匹配，输出 `REGISTRY-DEPENDENCY-OK`。
- [ ] 没有修改 `harmonica_eval/algorithms/registry.py` 或任何其它 `.py` 文件。
- [ ] `git diff --stat` 的本轮新增范围只包含本文件对应的 `.md`；不得 `git add` / `git commit`。

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] 完整目标文件：`harmonica_eval/algorithms/registry.py`（注入前空壳与注入后完整文件分别存档）。
- [ ] `git diff --stat` 原文，证明实现者只改本文件。
- [ ] `git diff harmonica_eval/algorithms/registry.py` 原文，证明现场铭牌、docstring、签名、`__all__` 未漂移。
- [ ] §8.1 `python --version` 原文。
- [ ] §8.2 完整 stdout 原文（含三行 `FILE-204` 与 `REGISTRY-SHELL-OK`）。
- [ ] §8.3 完整 stdout 原文（含 `REGISTRY-SIGNATURE-OK`）。
- [ ] §8.4 完整 stdout 原文（`REGISTRY-DEPENDENCY-OK`）。
- [ ] 空壳期没有黄金向量；注入后若要报告行为证据，另附重复登记、保序 list、未命中 get 的真实运行输出。
- [ ] 若任何 §8 命令失败，提交失败原文与 `GATE CHALLENGE`，不得用文字声称“应当通过”。

---

## 10 · ★ 何时必须停止并上报（§22 硬失败对策）

**以下情况必须停止，不得自行设计：**

1. 你需要改变 `register` / `list` / `get` 的签名、参数名、返回注解或 docstring。
2. 你需要新增第四个公开操作，或实现 `unregister`、`enable` / `disable`、`compatible_with`。
3. 你需要新的错误码、异常类或对外错误协议，而现有契约没有给出。
4. 你需要 import 任何 §3 清单外的模块、具体算法模块或动态发现机制。
5. 你发现保序要求与 C1 `run_algorithms` 的冻结顺序口径冲突。
6. 你发现必须持有 Host / Session 状态、manifest 或入口调用结果才能实现本文件。
7. 你发现 `PluginSpec` 的实际字段与本规格不一致，或需要修改 `contract.py`。
8. 你认为“用另一种容器也能保持顺序”，但无法证明 C1 看到的顺序与注册顺序逐项相同。
9. 你需要把重复登记改成覆盖、删除或延迟失败。

**MOLD BREAK 上报格式**：

```
MOLD BREAK
- 文件 ID：FILE-204
- 触发条款：§10 第 <n> 条
- 我在做什么：
- 卡在哪：
- 实际需要 vs 规格给出：
- 为什么我无法在不做上层设计的前提下继续：
- 建议的上游处理位置：
```

**绝对禁止**：

- 先写一个“能跑”的 workaround，以后再补边界；
- 自行选择新的错误码、公开方法或依赖；
- 为保持顺序而偷偷排序、改名或修改 C1；
- 静默吞掉重复登记或把缺失查询改成异常；
- 修改任何 `.py` 文件、契约或现场铭牌。

---

## 附：本文件的冻结常量速查

| 项 | 值 | 来源 |
| --- | --- | --- |
| Registry 公开操作 | `register` / `list` / `get`，共 3 个 | `registry.py` 壳件 / MUST |
| `register` 签名 | `(self, spec: PluginSpec) -> None` | `registry.py` L56–L58 |
| `list` 签名 | `(self) -> tuple[PluginSpec, ...]` | `registry.py` L64–L65 |
| `get` 签名 | `(self, algorithm_id: str) -> PluginSpec \| None` | `registry.py` L72–L73 |
| `PluginSpec` 字段数 | 6：`algorithm_id` / `algorithm_version` / `label` / `required_inputs` / `optional_inputs` / `entry` | `contract.py` |
| `InputRequirement` 字段数 | 6：`port_id` / `schema_version` / `timeline_basis` / `element_type` / `required_fields` / `sample_rate` | `contract.py` |
| `list()` 返回容器 | `tuple`，注册顺序 | 壳件裁定 / C1 `run_algorithms` |
| `get()` 未命中 | `None` | 壳件方法 docstring |
| 重复 `algorithm_id` | 显式失败，不覆盖 | 壳件方法 docstring |
| 排除操作 | `unregister` / `enable` / `disable` / `compatible_with` | 壳件 MUST NOT / §7 |
| 允许包内 import | `..contract.PluginSpec` | 壳件 import |
| 现场字段 | 10 个，含 `FILE-ID` 与 `BUILD-INSTRUCTION` | SHELL-STANDARD v1 |
