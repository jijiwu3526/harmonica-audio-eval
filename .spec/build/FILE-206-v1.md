# FILE-206 — `harmonica_eval/algorithms/bootstrap.py`

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/algorithms/bootstrap.py`
> 生成依据：
> - `harmonica_eval/algorithms/bootstrap.py`@v1（123 行壳件，含现场铭牌、`REGISTRATION_ORDER`、两个空函数）
> - `harmonica_eval/contract.py` 的 `PluginSpec` / `InputRequirement`
> - `harmonica_eval/algorithms/registry.py` 的 `Registry`
> - `harmonica_eval/algorithms/{pitch,timing,dynamics}.py` 的模块级常量与 `run` 入口
> - `COMPONENTS.md`@v2 §3 COMP-C3 · `.spec/GATE-CHALLENGES-C3.md` GC-204-08
> - SHELL-STANDARD v1
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-206 |
| 所属组件 | COMP-C3 Algorithm |
| 层级 | L3（symbol / implementation） |
| 上游 | C1 `harmonica_eval.host.app.HostApp` 的装配期调用点（Host 接收本文件产出的 `Registry`） |
| 下游 | `harmonica_eval.contract.PluginSpec`；`harmonica_eval.algorithms.registry.Registry` |
| 同层邻居 | `harmonica_eval/algorithms/registry.py`（注册表容器）、`harmonica_eval/algorithms/runtime.py`（执行期输入解析）、`harmonica_eval/algorithms/__init__.py`（包出口，只 re-export） |

**你的权限**：只实现本文件 `harmonica_eval/algorithms/bootstrap.py` 的两个既有空函数
（`build_plugin_specs` / `build_default_registry`）。

不得修改 `contract.py`、`registry.py`、`runtime.py`、`host/`、`core/`、`cockpit/`、
任何具体算法模块（`pitch.py` / `timing.py` / `dynamics.py`）或其他 `.py` 文件；
不得修改壳件中的现场铭牌、docstring、签名、`__all__`、模块级 import 或 `REGISTRATION_ORDER`。

C2（`core/`）完全不知道本文件存在；本文件也不管理 C1 的会话状态、Core 的数据面或 C4 的界面。

---

## 2 · 这个文件为什么存在

追溯：架构承诺「换算法不改核心」；盲审发现的物理死路（GC-204-08）。

裁定前，两条要求无法同时满足，而且矛盾已经写在 `host/app.py` 的 docstring 里：

- **要求甲**（`COMPONENTS.md` + `check_plugin_contract.py` 第②条）：
  `host/` 不得 import 任何具体算法实现模块。
- **要求乙**（`COMPONENTS.md:381-387`）：
  新增插件只允许「写 `algorithms/<name>/` + 在 C1 装配点多一行 `registry.register(...)`」。

两条同时成立时，`registry.register(pitch/timing/dynamics)` 在**物理上无法书写** ——
要构造 `PluginSpec` 就必须 import 具体模块，而 Host 被禁止 import。
换句话说：**没有第三个地方承担装配，装配链就不存在。**

★ 本文件把「知道所有实现」这一职责**从 C1 移到一个专属位置**：
bootstrap 独占具体算法的 import，Host 只接收已构造好的 `Registry`。
这样要求甲对 Host 继续成立（它确实不 import 具体算法），
而「谁负责装配」变成一个**可审查的、单点的物理事实**。

**删掉它会坏掉什么**（逐条）：

1. C1 若要自行 import 具体算法 → `check_plugin_contract.py` 第②条立即变红。
2. 若把清单塞进 `algorithms/_builtin.py` → 契约层重新认识具体算法，本轮刚拆掉的中央 `ALGORITHMS` 换个地方复发。
3. 若放宽为「运行期不 import」→ 判据从 AST 可判定退化为需区分运行/装配期，放弃更强保证。
4. 装配职责散落多处 → 「谁负责装配」无法用一次 AST 扫描回答，回到本次盲审前的状态。

★ **本文件只冻结形状，不冻结实现细节。** 你是第一个按本文件实现它的人。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import（穷举，清单外一律禁止）**：

- Python 标准库：`from __future__ import annotations`（壳件已有）。
- 第三方：**无**。
- `from ..contract import InputRequirement, PluginSpec`（壳件已有）。
- `from . import dynamics, pitch, timing`（壳件已有，**这是本文件存在的理由**）。
- `from .registry import Registry`（壳件已有）。
- 已有公开出口：`__all__ = ["ALGORITHM_INPUTS", "REGISTRATION_ORDER", "build_default_registry", "build_plugin_specs"]`，不得增删。

★ **`ALGORITHM_INPUTS` 为合法公开符号**（负责人 2026-09-24 裁定）：
  它是方案甲的**权威端口需求声明** —— 三个算法各需要哪些端口，全部冻结在本文件里。
  ★ 把它藏起来，方案甲的裁定就形同虚设：调用方会转而去各算法模块里找，
  ★ 那样又回到「装配知识分散」的老问题（GC-204-08 的原始成因）。

**禁止 import**：

- `harmonica_eval.core`、`harmonica_eval.host`、`harmonica_eval.cockpit` 的任何模块或任何相对路径。
- `importlib`、`pkgutil`、`importlib.metadata`、entry-points 读取、目录扫描等任何动态发现机制
  （与 `Registry` 同禁令——框架不得靠"发现"认识插件）。
- `os`、`sys`、`pathlib`、文件 I/O、网络模块、日志模块、第三方包。
- 任何清单外的包内或标准库模块。需要新依赖 → 停止并转 §10。

**依赖方向的原因**：C3 只经 `contract.PluginSpec` 接收插件声明；
一旦本文件知道 Core、Host 或 C4，新增插件就会反向要求框架改动，违反「换算法不改核心」。

---

## 4 · 你要实现什么（行为规格）

### 4.0 壳件中已存在的冻结内容（**不得改动**）

```python
REGISTRATION_ORDER: tuple[str, ...] = ("pitch", "timing", "dynamics")
# ★ 与 §4.1 的公开出口清单保持一致（四项）——
#   ALGORITHM_INPUTS 是方案甲裁定的【权威端口需求声明】，
#   藏起来（改 `_` 前缀）会让裁定形同虚设：调用方会转去各算法模块找，
#   那样又回到「装配知识分散」的原始成因（GC-204-08）。
__all__ = ["ALGORITHM_INPUTS", "REGISTRATION_ORDER", "build_default_registry", "build_plugin_specs"]
```

`REGISTRATION_ORDER` 是**全系统唯一的插件顺序来源**。`Registry` 只保序不排序；
C1 的 `run_algorithms` 按 `Registry.list()` 遍历，因此**改这里就改报告顺序，改别处不生效**。

★ **不要重新推导这个顺序，不要按字母序排，不要把 `dynamics` 提前。**
理由已冻结在壳件 docstring 里：pitch 是 timing 的前置（提供音边界），
timing 依赖 pitch 产出的音边界，dynamics 不依赖前两者。

### 4.1 `build_plugin_specs() -> tuple[PluginSpec, ...]`

**返回**：恰好 3 个 `PluginSpec` 的 tuple，顺序与 `REGISTRATION_ORDER` 严格一致。

每个 `PluginSpec` 的六个字段（真实定义见 `contract.py`）：

| 字段 | 取值来源（★ 不得在本文件编造） |
| --- | --- |
| `algorithm_id` | 对应模块的 `ALGORITHM_ID`（实测值：`"pitch"` / `"timing"` / `"dynamics"`） |
| `algorithm_version` | 对应模块的 `ALGORITHM_VERSION`（实测值：三者均为 `"v1.0.0"`） |
| `label` | 对应模块的 `LABEL` 常量（负责人 2026-09-24 裁定；实测值：`"音准"` / `"节奏"` / `"力度"`）。★ **禁止回退为 `algorithm_id`** —— 静默回退会让界面把英文 ID 当中文名显示且全程无报错，违反宪章 §5.6「禁止静默降级」。★ **模块缺 `LABEL` 即抛 `PLUGIN_INCOMPATIBLE`**，不得回退 |
| `required_inputs` | 由本文件的 `ALGORITHM_INPUTS[algorithm_id]` 逐条给出端口 id，★ **再由 `_requirement()` 从 `profile.PORT_INDEX[port_id]` 派生其余属性**（方案甲：权威声明在本文件，不在算法模块）。★ **不得硬编码** `timeline_basis` / `element_type` / `required_fields` / `sample_rate` —— `PortSpec` 根本没有这些字段，硬编会产生第二份真相源 |
| `optional_inputs` | 恒为 `()`。三个算法当前无 optional 端口（壳件 docstring 已冻结该结论）；若将来新增，须同步改本表与 `ALGORITHM_INPUTS` |
| `entry` | 对应模块的公开入口 `run`，签名统一为 `run(surface: AlgorithmDataContract) -> AlgorithmResultEnvelope`（已实测三者一致） |

★ **`sample_rate` 的来源（负责人 2026-09-24 裁定：代码不动，补依据）**：
  取自 `profile.AUDIO.sample_rate`。★ 它是**音频格式的全局属性**，不是逐端口属性
  ——`PortSpec` 字段表里根本没有 `sample_rate`，若硬编进每个 `InputRequirement`
  就是复制 12 份同一真值。manifest 侧的 `audio_format.sample_rate` 同源。

**必须满足的不变量**：

1. 返回长度恒为 3，且 `tuple(s.algorithm_id for s in result) == REGISTRATION_ORDER`。
2. 三个 `entry` 必须**真的是**三个不同模块的 `run`（不得写成同一个 lambda 或占位）。
3. **不得**在本文件替算法编造输入要求。壳件 docstring 已冻结此禁令：
   > `required_inputs` / `optional_inputs` 由算法自描述，bootstrap **不得**在此替算法编造输入要求。
4. **不得**调用 `run`、**不得**读端口、**不得**做 DSP、**不得**解释 payload。

### 4.2 `build_default_registry() -> Registry`

**返回**：一个已装好上述 3 个 `PluginSpec` 的 `Registry`。

步骤（唯一合法实现路径）：

1. 构造一个空 `Registry()`。
2. 对 `build_plugin_specs()` 返回的每个 spec 依次调用 `registry.register(spec)`。
3. 返回该 `Registry`。

**必须满足的不变量**：

1. `registry.list()` 的长度恒为 3。
2. `tuple(s.algorithm_id for s in registry.list()) == REGISTRATION_ORDER`。
3. `registry.get("pitch")` 等三个 id 均返回非 `None`，且 `is` 同一对象。
4. **重复 `algorithm_id` 必须由 `Registry.register` 显式报错，bootstrap 不得吞掉**——
   不得 `try/except` 包裹 `register`，不得静默跳过重复项。
5. **只返回 `Registry`。** Host 拿到它之后不再 import 任何具体算法——
   这正是本文件存在的意义。

### 4.3 明确不做的事

- **不做目录扫描、不读 entry-points、不做动态发现**（与 `Registry` 同禁令）。
- **不提供 `unregister` / `enable` / `disable`**（运行期改插件集合属 Host 职责）。
- **不重新定义 `PluginSpec`**，不在本文件内构造新的类型。
- **不复制注册顺序的第二份来源**——顺序只认 `REGISTRATION_ORDER`。
- **不吞异常、不加 `try/except` 降级**。装配失败必须暴露。

### 4.4 ★ 未决项：实现前必须知道的两个真实阻塞

> **★ 2026-09-24 更新**：② 的**权威来源已裁定**（见 §4.5，方案甲）。
> 下方保留裁定前的原始记录作为决策历史。① 仍未关闭（零实例是注入前的
> 必然状态，不是缺陷）。

**这两条不是本文件的疏漏，是本轮盲审发现、尚未裁定的架构问题。**
请勿用猜测填补，如实上报。

**① `PluginSpec` 只有类型定义，零实例**

```
contract.PluginSpec   6 字段定义完整
但全仓没有任何一个 PluginSpec 实例
三个算法模块只有 ALGORITHM_ID / ALGORITHM_VERSION 常量与 run 入口
```

**② `FILE-201` 的判据 A 与本文件的裁定互相矛盾（盲审 BLOCK-4）**

`.spec/build/FILE-201-v1.md:466-476` 的判据 A 要求：

```python
from harmonica_eval.algorithms.pitch import SPEC   # ← pitch.py 没有 SPEC
p = SPEC
assert p.algorithm_id == 'pitch'                 # ← 该字段已改名 algorithm_id
```

★ **三处同时失效**：`SPEC` 不存在、`plugin_id` 已由负责人 BLOCK-4 裁定改名为
`algorithm_id`、判据要求的端口元组没有任何合法来源。

★ **这正是本文件要解决的问题的一部分**：若由 bootstrap 统一构造 `PluginSpec`，
则 `SPEC` 应改为从 `bootstrap` 取得；但 `FILE-201` 属 C3 另一个文件，**不在你的权限内**。

---

### 4.5 ✅ 已裁定：端口需求由 bootstrap 集中声明（方案甲）

> **负责人 2026-09-24 裁定**：`required_inputs` / `optional_inputs` 的
> **权威来源是 `bootstrap.ALGORITHM_INPUTS`**，不是各算法自导出 `SPEC`，
> 也不是 C1 投影。

**裁定理由（三条）**

1. **与刚关闭的 GC-204-08 完全一致。** `bootstrap` 的职责原文
   （`host/app.py:114`）就是「唯一知道有哪些实现的地方」。
   端口需求属于「实现需要什么」，天然是装配根的知识。
2. **选乙会让装配知识重新分散。** 各算法自导出 `SPEC` 等于把刚关闭的
   装配权冲突换个位置 `reintroduce`。
3. **「新增算法不改 bootstrap」这个优势已由 §8.3 机器守住**
   （全仓恰好一处 import 具体算法）。新增算法确实要改本文件，
   但那本来就是装配根该做的事。

**已落地的声明**（`harmonica_eval/algorithms/bootstrap.py`）

| 算法 | 必需端口 | 出处 |
| --- | --- | --- |
| `pitch` | `pitch.reference` · `pitch.practice` · `notes.reference` · `notes.practice` | `pitch.py:19` |
| `timing` | `pcm.mapped.reference` · `pcm.mapped.practice` · `notes.reference` | `timing.py:21-22` |
| `dynamics` | `rms.reference` · `rms.practice` · `notes.reference` · `notes.practice` | `dynamics.py:20` |

★ **`timing` 刻意不含 `pcm.warped.practice`** —— `timing.py:30` 的 MUST NOT
明文禁止使用它或任何 WARPED 轴数据（会把抢拍拖拍抹成 0 且不报错）。
**把它列进依赖等于要求它存在。**

★ **`dynamics` 也不含 `pcm.warped.practice`** —— 尽管它是数据面唯一的 WARPED
端口。`dynamics.py:37-49` 记载了 MOLD BREAK：原 MUST「用 WARPED 轴语义」
**无法满足**（`rms.*` 在 profile 里都是 REFERENCE 轴），
已改为**按音配对**，`AXIS` 常量随之删除。

**实现时必须遵守的三条**

1. `set(ALGORITHM_INPUTS) == set(REGISTRATION_ORDER)`，不一致即抛错，
   **不得静默补齐**。
2. `InputRequirement` 的 `timeline_basis` / `element_type` / `required_fields`
   **从 `profile.PORT_INDEX` 派生，不得硬编码** —— 硬编码会产生第二份真相源。
3. `optional_inputs` v0.1 全部为空；将来若某算法有「缺失也能出正确结果」的
   端口，**另立 `ALGORITHM_OPTIONAL_INPUTS`**，不得混入本表。

**★ 仍未关闭的**：`FILE-201` 判据 A 本身仍要求 `pitch.SPEC`，
那需要同步 `FILE-201-v1.md`（属 C3 另一文件，不在本文件权限内）。
本裁定只确定了**来源**，未修改那一侧的判据文本。

---

## 5 · 冻结语义（不变量，逐条）

| 编号 | 不变量 |
| --- | --- |
| INV-206-1 | 本文件是全系统**唯一** import `dynamics` / `pitch` / `timing` 具体模块的位置 |
| INV-206-2 | 本文件只做「import → 构造 `PluginSpec` → `register`」，**不做任何算法逻辑** |
| INV-206-3 | 注册顺序**恒等**于 `REGISTRATION_ORDER`；不得在别处重排 |
| INV-206-4 | 三个 `entry` 分别是三个模块的 `run`，不是同一个对象 |
| INV-206-5 | 重复 `algorithm_id` 由 `Registry.register` 报错，本文件**不得吞掉** |
| INV-206-6 | 本文件**不被** `core` / `host` / `cockpit` import（它们只接收已构造的 `Registry`） |
| INV-206-7 | 不做目录扫描 / entry-points / 任何动态发现 |
| INV-206-8 | `build_default_registry()` **只返回 `Registry`**，不返回元组、不返回 spec 列表 |

---

## 6 · 失败路径

| 情况 | 行为 |
| --- | --- |
| `Registry.register` 因重复 `algorithm_id` 报错 | **原样抛出**，不得 `try/except` 吞掉 |
| 某算法模块不存在或 import 失败 | 模块级 import 阶段即失败，**原样抛出** |
| `PluginSpec` 字段缺失或类型不符 | `TypeError` **原样抛出**，不得补默认值 |
| `REGISTRATION_ORDER` 与实际模块数不符 | **必须是 `AssertionError`**（`len == 3`），不得静默按实际数量构造 |

★ **通用原则**：本文件**不吞任何异常**。装配失败必须立刻暴露，
因为它意味着「系统不知道有哪些实现」——那正是本文件要消除的状态。

★ **不得**把失败降级为「注册能注册多少算多少」。那会让缺算法的报告看起来正常。

---

## 7 · 边界（MUST NOT 汇总）

- 不得 import `core` / `host` / `cockpit` 的任何模块或任何相对路径。
- 不得 import 具体算法模块**之外**的 `algorithms` 包内实现（`registry` / `runtime` 除外，见 §3）。
- 不得扫描目录、读 entry-points、做动态发现。
- 不得在此运行算法、读端口、做 DSP、解释 payload。
- 不得提供 `unregister` / `enable` / `disable`。
- 不得在本文件重新定义 `PluginSpec` 或复制注册顺序的第二份来源。
- 不得为算法编造 `required_inputs` / `optional_inputs`（见 §4.4）。
- 不得 `try/except` 包裹 `register` 以吞掉重复注册错误。
- 不得新增第三方依赖。
- **不得被 `core` / `host` / `cockpit` import**（那会重新制造 GC-204-08）。

---

## 8 · 怎么验证你写对了

本轮对象是**尚未注入实现的冻结空壳**。因此 §8 的命令是「模具完整性验收」：
它们必须在当前空壳上真实通过；空壳性是未来注入前必须先被证明的条件。

### 8.1 运行环境

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python --version
```

判据：命令退出码为 0；实际输出写入 §9 证据包。

### 8.2 注入后行为验收：两个函数必须产出正确的注册表

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
from harmonica_eval.algorithms.bootstrap import (
    ALGORITHM_INPUTS, REGISTRATION_ORDER, build_default_registry,
    build_plugin_specs,
)
from harmonica_eval.profile import PORT_INDEX

assert REGISTRATION_ORDER == ('pitch', 'timing', 'dynamics'), REGISTRATION_ORDER
# 方案甲的完整性要求：声明的算法集合必须与装配顺序一致，不一致即装配层缺陷
assert set(ALGORITHM_INPUTS) == set(REGISTRATION_ORDER), (
    set(ALGORITHM_INPUTS), set(REGISTRATION_ORDER))

specs = build_plugin_specs()
assert len(specs) == 3, len(specs)
assert tuple(s.algorithm_id for s in specs) == REGISTRATION_ORDER, specs
# 每个声明的端口必须真实存在于 profile，声明不得凭空编造
for aid, ports in ALGORITHM_INPUTS.items():
    for pid in ports:
        assert pid in PORT_INDEX, (aid, pid)
# 端口需求条数必须与 §4.5 冻结表逐条对应
for s in specs:
    assert len(s.required_inputs) == len(ALGORITHM_INPUTS[s.algorithm_id]), s.algorithm_id
    assert s.entry is not None, s.algorithm_id
    assert s.algorithm_version, s.algorithm_id

reg = build_default_registry()
assert [s.algorithm_id for s in reg.list()] == list(REGISTRATION_ORDER), reg.list()
for s in reg.list():
    assert reg.get(s.algorithm_id) is s, s.algorithm_id
assert reg.get('__not_registered__') is None
print('BOOTSTRAP-OK', [s.algorithm_id for s in reg.list()])
PY
```

判据：退出码为 0；输出含 `BOOTSTRAP-OK ['pitch', 'timing', 'dynamics']`。
★ **比原判据更严**：原判据只验证「未注入时抛 FILE-206」；
★ 本判据验证**返回值真的正确** —— 数量、顺序、端口存在性、需求条数、
★ `entry` 非空、`get` 命中同一对象、`get` 未命中返 `None`。
★ 任何一项不符即失败，**不允许「只要不崩就算过」**。

### 8.3 装配根唯一性：只有本文件 import 具体算法

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
import ast
from pathlib import Path

ROOT = Path('harmonica_eval')
ALGO = {'pitch', 'timing', 'dynamics'}
offenders = []

for path in sorted(ROOT.rglob('*.py')):
    if '__pycache__' in path.parts:
        continue
    rel = path.as_posix()
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            names = {a.name for a in node.names}
            hit = names & ALGO
            if hit:
                offenders.append((rel, node.lineno, sorted(hit)))

for rel, lineno, names in offenders:
    print(f'{rel}:{lineno} -> {names}')

assert len(offenders) == 1, f'expected exactly 1 site, got {len(offenders)}'
assert offenders[0][0] == 'harmonica_eval/algorithms/bootstrap.py', offenders[0]
print('PASS: bootstrap.py 是唯一 import 具体算法的位置')
PY
```

判据：输出恰好一条 `bootstrap.py:56` 记录，随后 `PASS`；退出码为 0。
★ **这正是 GC-204-08 的可机械判定形式**：一旦第二个文件 import 具体算法，立即变红。

### 8.4 依赖方向：本文件不得被 core / host / cockpit import

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
import ast
from pathlib import Path

FORBIDDEN = ('core', 'host', 'cockpit')
hits = []

for path in sorted(Path('harmonica_eval').rglob('*.py')):
    if '__pycache__' in path.parts:
        continue
    rel = path.as_posix()
    if rel == 'harmonica_eval/algorithms/bootstrap.py':
        continue
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ''
            if mod.endswith('bootstrap') or 'bootstrap' in {a.name for a in node.names}:
                if any(f'harmonica_eval.{f}' in mod or f == mod for f in FORBIDDEN):
                    hits.append((rel, node.lineno, mod))

for item in hits:
    print('HIT', item)
assert not hits, f'core/host/cockpit must not import bootstrap: {hits}'
print('PASS: 无 core/host/cockpit import bootstrap')
PY
```

判据：输出 `PASS`；退出码为 0。

### 8.5 全局依赖方向与插件契约

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_shell.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_plugin_contract.py
```

判据：两条命令退出码均为 0；`verify_shell` 报告「依赖方向」段全绿，
`check_plugin_contract` 报告 13/13 通过。

### 8.6 未来注入后的行为验收（**当前必然失败，是正确状态**）

以下脚本在**实现完成后**必须通过；在当前空壳上它**应当失败**——
失败原因是 `NotImplementedError: SHELL: FILE-206`，那是对的，不要放宽。

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python - <<'PY'
from harmonica_eval.algorithms.bootstrap import (
    REGISTRATION_ORDER, build_default_registry, build_plugin_specs,
)

specs = build_plugin_specs()
assert len(specs) == 3, len(specs)
assert tuple(s.algorithm_id for s in specs) == REGISTRATION_ORDER

entries = {id(s.entry) for s in specs}
assert len(entries) == 3, '三个 entry 必须是三个不同对象'
for s in specs:
    assert callable(s.entry), s.algorithm_id
    assert s.algorithm_version, s.algorithm_id

reg = build_default_registry()
listed = reg.list()
assert len(listed) == 3, len(listed)
assert tuple(s.algorithm_id for s in listed) == REGISTRATION_ORDER
for aid in REGISTRATION_ORDER:
    assert reg.get(aid) is not None, aid

print('PASS 8.6: 装配完成且顺序正确')
PY
```

★ **当前实跑结果应为 `NotImplementedError: SHELL: FILE-206 待注入实现`，退出码非 0。**
★ 这是**正确状态**。若它通过，说明有人提前注入了实现。

---

## 9 · 证据包

实现完成后，把以下真实输出贴进本节（**不得编造**）：

- `8.1` 的 `python --version`
- `8.2` 的两行 `SHELL:` 输出
- `8.3` 的唯一 import 记录 + `PASS`
- `8.4` 的 `PASS`
- `8.5` 两条工具的完整输出
- `8.6` 的 `PASS 8.6`（注入后才有）
- `python3 tools/verify_stubs_raise.py` 的完整输出
- `python3 tools/check_counts.py` 的完整输出
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q` 的完整输出

---

## 10 · 需要负责人裁定才能继续的（发现即报，不得自行决定）

1. **`required_inputs` / `optional_inputs` 的权威来源**（见 §4.4）。
   本文件不得替算法编造，算法模块当前也无自描述。
2. **`FILE-201` 判据 A 的三处失效**（`SPEC` 不存在、`plugin_id` 已改名、端口元组无来源）。
   该文件不在本任务权限内，需另派任务同步。
3. **装配链当前仍是断的**：本文件已就位，但**没有任何文件 import 它**
   （Host 仍是 SHELL）。裁定落地了，物理通路要等注入才接通。
