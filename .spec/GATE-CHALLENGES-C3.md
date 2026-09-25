# GATE CHALLENGES — C3 插件化改造过程中提出、尚未关闭的挑战

> 依据宪章 §37（Gate Challenge Protocol）：实现过程中发现"冻结的契约无法自洽实现"时，
> **必须当场停下并记录**，不得自行放宽、不得"以后再说"、不得在实现里绕过。
> 每条挑战要么被负责人裁定关闭，要么按 §40 传播陈旧后重铸。
>
> 本文件记录 **C3 Algorithm Plugin 化**这一轮改造中提出的全部挑战。
> 状态取值：`OPEN`（待裁定） / `CLOSED`（已裁定并落盘）。

---

## GC-204-01 ★ C1 会话 API 与 G8 裁定自相矛盾

**状态**：`OPEN` — 阻塞 Cast Freeze

### 事实

`contract.HostContract` 的 G8 修正**明确裁定**：

> 「会话句柄既然由 `create_session` 返回、又必须传给其他 5 个操作，
> 唯独两个 setter 不用它，实现者无法判断该往哪个会话登记（多会话时直接歧义；
> 单会话时又要额外约定"当前会话"这个隐含状态）。
> **修正为显式传 `session_id`：所有会话级操作都必须显式定位会话，
> 不引入"当前会话"这种隐含状态**（隐含状态是并发缺陷的温床，
> 且与 `create_session` 返回 id 的设计自相矛盾）。」
> —— `harmonica_eval/contract.py:505-522`

实测两处签名（`python3 -c` 枚举，非推测）：

| 操作 | `contract.HostContract`（已冻结） | `host/app.py HostApp`（现状） |
| --- | --- | --- |
| `create_session` | `(profile_version) -> str` | `(profile_version)` ✅ 一致 |
| `set_reference` | `(session_id, uri)` | `(path)` ❌ |
| `set_practice` | `(session_id, uri)` | `(path)` ❌ |
| `build_surface` | `(session_id)` | `()` ❌ |
| `status` | `(session_id)` | *不存在* |
| `acquire_surface` | `(session_id)` | *不存在* |
| `destroy_session` | `(session_id)` | `(session_id)` ✅ |

### 为什么这是挑战而不是"已修好"

这不是"C1 门面与 C2 契约不同"那种可以各行其是的分层差异 ——
**`HostApp` 自身就内部不自洽**：

- 三个操作**要** `session_id`：`destroy_session` / `run_algorithms` / `build_view`
- 三个操作**不要** `session_id`：`set_reference` / `set_practice` / `build_surface`

而 `host/app.py:144` 的 docstring 直书「**用 C1 记住的会话**」，
`:95-98` 的流程图也写「用 **C1 记住的 id** 调 C2」。

**这正是 G8 当初判为缺陷的同一个形状**：句柄由 `create_session` 返回，
一部分操作要它、一部分不要，且靠"当前会话"这个隐含状态补齐。
G8 在 `HostContract` 上修好了，**在它上面一层的 C1 门面上原样保留着**。

### 为什么会漏掉

G8 是 §20 盲审发现并修复的，修复范围只覆盖了 `contract.py`。
`HostApp` 的骨架签名是更早铸的，未被回查。**这是"修正未向上一层传播"的典型案例**，
与本轮已记录的两次同类事故（`restore` 冲掉修复、`check_counts` 未同步新符号）同族。

### 待裁定的三个选项

| 选项 | 内容 | 代价 |
| --- | --- | --- |
| **A** | `HostApp` 全部会话级操作显式收 `session_id`，与 G8 对齐 | 改 `host/app.py` 3 个签名 + `__main__.py` 调用点 + FILE-301/002 两份 BI；多会话能力成立 |
| **B** | `HostApp` 显式声明为**单会话门面**：三个"要 id"的操作也改为无参，id 全部内部持有 | 改动更小，但等于**正式承认** C1 依赖隐含状态 —— 与 G8 的裁定**直接冲突**，需负责人明确推翻 G8 |
| **C** | 拆分：`HostApp`（单会话门面，给 C4 与 `__main__`）与 `SessionRegistry`（多会话，给未来） | 最完整，但新增一个类型，超出"快速原型"规模 |

### 我的建议

**选 A。** 理由：

1. G8 的理由是硬的（隐含状态是并发缺陷温床），不宜推翻 —— 推翻它需要负责人
   重新裁定一次"v0.1 是否需要多会话"。
2. 本项目的真实用法只有单会话，但**"当前只有一种用法"不等于"契约可以假装支持多种"**。
   若选 B，`HostContract` 的多会话能力就成了**声明了但无法使用**的规格。
3. A 的改动量可控（3 个签名 + 调用点 + 2 份 BI），不触及 Core 与插件层。

**但这是路线问题，由负责人定。** 在裁定前，实现者不得自行按 B 写。

### 影响面

- `harmonica_eval/host/app.py`（FILE-301 骨架 3 个签名 + docstring）
- `harmonica_eval/__main__.py`（FILE-002，`run_headless` 的调用点）
- `.spec/build/FILE-301-v1.md`、`.spec/build/FILE-002-v1.md`
- `tools/verify_shell.py` 的 ⑱ 签名一致性检查（改后需重跑）

---

## GC-204-02 ★ `_scratch` 陈旧副本会静默污染验证

**状态**：`CLOSED`（已加机械护栏）

### 事实

`_scratch/harmonica_eval` 是主包的**完整复制品**（非符号链接），
`diff -rq` 实测已有 **36 处差异**。

本轮实际踩中：验证新插件契约时在 `_scratch` 下
`import InputRequirement` 报 `ImportError`，而主包里该类型确实存在 ——
因为 Python 优先加载了 `_scratch/harmonica_eval`。

### 危害

任何人（或任何智能体）在 `_scratch` 下验证主包契约/架构，
都会拿到**陈旧代码**并得出**看似正常的错误结论**。
这类错误不会报错，只会给出错误的"通过"。

### 处置

不删 `_scratch`（它是审查者 B 的参考实现，是唯一能端到端跑通 §8 判据的工件），
改为加机械护栏：`tools/check_scratch_freshness.py` +
`_scratch/_STALE_WARNING.md` 说明两者的正确用法。

**正确用法**：
- 验证契约/架构/类型 → 用**主包** `harmonica_eval/`
- 跑端到端数值 → 用 `_scratch/`
- **永远不要用 `_scratch` 的结果去论证主包的契约或类型**

---

## GC-204-03 `validate_result` 的职责边界（已裁定关闭）

**状态**：`CLOSED`（裁定：不改签名）

### 挑战

子代理提出：`validate_result(result)` 单参数拿不到 `resolve_inputs` 的
`available`，因此无法校验 `consumed_ports ⊆ available`。

它给出两个自选方案，其中一个要把 `available` 塞进
`result.payload['_runtime_resolution']`。

### 裁定

**两个方案都不采纳。** 保持单参数签名，且**不把 `available` 塞进结果**。

理由：把控制信息放进结果数据，插件就能伪造它，证据边界与结果边界混淆。
正确的边界划法：

| 归属 | 负责什么 |
| --- | --- |
| `validate_result(result)` | **纯自洽性**：status ∈ 四值、unit ∈ 词表、`len(t)==len(values)`、coverage ∈ 0–1、`DEGRADED` 必须有 coverage 或 warnings、不兼容/失败必须有 error_code |
| **C1 在调用点** | `consumed_ports ⊆ available` —— 只有 C1 同时持有 `PluginSpec` / `SurfaceManifest` / `InputResolution` |

已在 `contract.py` 的 `warnings` docstring 与 `runtime.py` 的
`validate_result` docstring 中双向写明此边界，防止后来者"好心"加回去。

### 连带修正

裁定过程中发现契约 docstring 自相矛盾：原写 `DEGRADED` 的佐证包含
"缺 optional 事实"，但那项事实**不在信封内**，纯校验拿不到。
已改为佐证仅 `coverage` / `warnings` 两项，并说明 `missing_optional` 归 C1。

---

## GC-204-04 `entry` 签名是否加 `InputResolution` 参数

**状态**：`CLOSED`（裁定：保持单参数 `entry(surface)`）

### 挑战

设计方案曾提议 `entry(surface, resolution)`，理由是插件需要知道
哪些 optional 输入拿到了，否则每个插件都要自己 try/except 读端口，
重复实现兼容检查。

### 裁定

**不采纳。** 保持 `entry(surface: AlgorithmDataContract) -> AlgorithmResultEnvelope`。

理由：

1. 规格明确要求"插件内部可以 manifest()/read()"，且**明确禁止**为省事
   把 `surface.read()` 到处散落；`resolution` 属于同类"为便利而扩大接口"的做法。
2. optional 输入的缺失，插件**应当**在读到端口时自己判断
   （`read` 抛 `ContractViolation` 是既有契约，插件 try/except 即可）。
3. `PluginSpec.optional_inputs` 已经在**注册期**声明了意图；
   运行期到底拿到了什么，是**执行事实**，插件自己读才知道 ——
   这与"报告自己实际读了哪些端口"（`consumed_ports`）是同一个诚实原则：
   **插件如实自报，不靠外部替它记账**。

代价：插件需自行 try/except 处理 optional 缺失。这是**可接受的重复**，
换来接口更小、插件更独立。已记入 `PluginSpec.entry` 的实现约定。

---

## GC-204-05 `UNITS_VOCABULARY` 缺 `ratio` / `count`

**状态**：`CLOSED`（裁定：加入，8 → 10）

### 事实

`off_pitch_ratio` 是 0–1 比例，`n_notes_used` 是计数，
但原 8 值词表里没有任何一个能正确描述它们。

### 裁定

加入 `ratio` 与 `count`，词表 8 → 10。

理由：

1. 不加就得留空字符串，直接违反项目铁律
   「每个数字都要能回答它是什么、怎么算的、**单位是什么**」。
2. 该词表**本来就把 `cents`/`db`/`seconds` 标为"来自 payload"** ——
   "payload 的单位也归本表管"这条规则早已存在，只是当时漏了这两类。
   补上是**完成既有规则**，不是新增规则。
3. 判据仍受控：10 个封闭值，不会退化开放式字符串（那正是 G10 修的问题）。

---

## GC-204-06 ★ `InputResolution` 归属：契约层还是执行期

**状态**：`CLOSED`（裁定：定义在 `runtime.py`，不进 `contract.py`）

### 挑战

子代理指出：若把它定义在 `contract.py`，就与"契约层只放跨组件冻结类型"的原则冲突；
若放 `runtime.py`，则 `entry` 签名注解需跨模块引用。

### 裁定

**定义在 `runtime.py`（FILE-205），不进 `contract.py`。**

理由：`InputResolution` 是**一次执行**的产物（本次哪些 optional 拿到了），
不是跨组件的冻结契约。放进 `contract.py` 会让契约层随每次运行的内容变化。

**连带风险（子代理发现，已处理）**：
`contract.py` 的 `warnings` docstring 里**提到**了 `InputResolution` 这个名字
（为了说明它住在 runtime、刻意不进契约层）。
因此 FILE-205 的 §8 **不能**用"contract.py 文本不得出现 InputResolution"
这种文本 grep 判据 —— 那会误报。

已改为**结构性断言**（实测已确认成立）：
- `runtime.py` 有 `ClassDef(InputResolution)`
- `contract.py` 无该类定义、无该类 import、`__all__` 不含它

★ 这条是本项目"**文本判据会误报，结构性判据才可靠**"的又一例证：
凡是"某符号不应出现在某文件"的要求，都要先问一句"它会不会合理地出现在注释里"。

---

## GC-204-07 ★ 我用裸子串统计陈旧引用，数错了

**状态**：`CLOSED`（已更正口径）

### 事实

我给子代理派活时报告的"陈旧引用数"是用裸子串 `ALGORITHMS` 统计的，
得出一份看似精确的表（FILE-003 有 8 处、FILE-105 有 1 处、FILE-401 有 7 处）。

子代理复核时发现不对 —— 那三份文件里的命中**全部**是
`RUN_ALGORITHMS`（`contract.UiCommandKind` 的一个成员，
表示用户按下"运行算法"这个命令），与已删除的 `algorithms.ALGORITHMS`
毫无关系。

我用词边界 `\b(PAYLOAD_SCHEMAS|ALGORITHMS)\b` 独立复核，确认**子代理是对的，
我的表是错的**：

| 文件 | 我报的（裸子串） | 实测（词边界） | 真实陈旧？ |
| --- | --- | --- | --- |
| FILE-003 | 8 | **0** | ❌ 全是 `RUN_ALGORITHMS` |
| FILE-105 | 1 | **0** | ❌ 同上 |
| FILE-401 | 7 | **0** | ❌ 同上 |
| FILE-002 | 2 | 2 | ✅ |
| FILE-004 | 1 | 1 | ✅ |
| FILE-104 | 2 | **1** | ✅（另 1 处是 `RUN_ALGORITHMS`） |
| FILE-200 | 1 | 1 | ⚠️ 是 §8.6 防回退守卫的 `forbidden` 元组本身，**正确，勿动** |

### 为什么会错

我把"快速扫一遍得出个数"当成了可靠事实，没有验证这个计数是否可区分
`ALGORITHMS` 与 `RUN_ALGORITHMS`。

**这与本项目已记录的多次事故同族**：凡是"某个检查命中了 N 处"的结论，
必须先问一句"它命中的是不是我要找的那个东西"。
历史上已发生过：`chroma` 命中了禁止词所在的那行 docstring、
`warp_path.dtype` 被裸前缀检查误报、`b120` 与 `855 MB` 变量张冠李戴。

### 处置

- 已向子代理发更正，实际范围从 11 份收窄到 **7 份**
  （FILE-002 / 004 / 104 / 201 / 202 / 203 / 301）
- 明确告知：不得动任何 `RUN_ALGORITHMS`
- 顺带发现 `check_counts.py` 里 `Rule` 的正则若也用裸子串，
  会有同样的误判风险 —— 已在派活口径中要求子代理复核

### 附带的元教训

★ 子代理**没有**直接照我给的数去改，而是自己复核后上报差异。
这是正确的行为：它把"上级的数字"当**待验证的断言**，而不是**事实**。
本项目的审查纪律要求"每条发现要有 `path:line` + 证据"，
对上级派活同样适用 —— 这条纪律第一次在**派活方向**上生效，
说明它确实被内化了，而不是只在被审时表演。

---

## GC-204-08 ★★ 不变量甲与不变量乙直接冲突，且已写进代码注释

**状态**：`CLOSED`（2026-09-24 负责人裁定方案甲落地，已实测验证）
~~`OPEN` — 阻塞插件迁移~~

### 事实

两条要求无法同时满足，而且**矛盾已经写在了代码注释里**：

- **要求甲**（不变量②，`COMPONENTS.md` + `check_plugin_contract.py` 第②条）：
  `host/` 不得 import 任何具体算法实现
- **要求乙**（不变量 C，`COMPONENTS.md:381-387`）：
  新增插件只允许「写 `algorithms/<name>/` + **在 C1 装配点多一行 `registry.register(...)`**」

而 `host/app.py:114-122` 的 docstring **同时**写着两句互斥的话：

> 「C1 是**唯一**知道"有哪些实现"的地方。」
> 「跨界 import 的是**契约层**（`..algorithms`），**不是某个具体算法实现模块**。」

★ **后一句是我上一轮让子代理改的**（原文是「算法注册表来自
`algorithms.ALGORITHMS`（本模块 import 它）」）。
我把它改成了一个**结构上不可能成立**的说法 ——
C1 要显式 `register` 各插件，就必须 import 它们。

### 为什么会这样

这是我自己的传递错误：
1. 上一轮我裁定「C1 是唯一跨界的装配点，跨界 import 的是契约层」；
2. 子代理照做了，把这句写进了 `host/app.py`；
3. **我没回头验证这句话在结构上能不能成立**。

这不是子代理的错 —— 它执行的是我的裁定。**裁定本身有问题。**

### 三个解法与裁定建议

详见 `.spec/PLUGIN-LAYOUT.md` 第 5 节。摘要：

| 解法 | 做法 | 裁定 |
| --- | --- | --- |
| **一：独立装配根** | 新增 `harmonica_eval/bootstrap.py` 作为 composition root；`host/` 降为纯逻辑层，**物理上**没有 import 插件的上下文 | ★ **推荐** |
| 二：清单放 `algorithms/` | `algorithms/_builtin.py` 列默认三件 | **否决** —— 契约层重新认识具体算法，本轮刚拆掉的 `ALGORITHMS` 换个地方复发 |
| 三：放宽甲 | 改成「运行期不 import」 | **否决** —— 判据从 AST 可判定退化为需区分运行/装配期，且放弃更强保证 |

★ **推荐解法一的额外理由**：
`COMPONENTS.md:79-94` 本来就把 C1 定义为 composition root。
**我们不是在发明新结构，是在让代码结构终于对上规格里已有的定义。**

### 影响面

- `harmonica_eval/host/app.py:114-122`（那句不成立的 docstring）
- `COMPONENTS.md:381-387`（不变量 C 措辞：「C1 装配点」→「装配根 `bootstrap.py`」）
- `tools/check_plugin_contract.py` 第②条（扫描范围与新增判据）
- `harmonica_eval/host/app.py`（由其 `build_default_app()` 接收 `bootstrap.build_default_registry()` 的产物；**不是**由 `__main__.py` 直接调用装配根 —— `__main__.py` 不 import `bootstrap`，否则它会越过 C1 直连 C3）
  ★ **勘误（2026-09-24）**：本行原写「`harmonica_eval/__main__.py`（改为调用 `bootstrap.build_default_app()`）」，
  ★ **两处均与实况不符**——`bootstrap.build_default_app()` 这个函数名从不存在
  ★ （实际是 `build_default_registry()`，见 `harmonica_eval/algorithms/bootstrap.py:323`），
  ★ 且调用方应是 **Host** 而非 `__main__.py`。已按 `harmonica_eval/host/app.py:257` 与
  ★ `harmonica_eval/algorithms/bootstrap.py:323` 的实况更正。

### ✅ 已解决（2026-09-24 负责人裁定 · 方案甲落地并实测）

**裁定内容**：负责人裁定 **BLOCK-1 = 方案甲（独立装配根）**。
「知道所有实现」这一职责从 C1 移到一个专属位置：
bootstrap 独占具体算法的 import，Host 只接收已构造好的 `Registry`。
这样要求甲对 Host 继续成立（它确实不 import 具体算法），
而「谁负责装配」变成一个**可审查的、单点的物理事实**。

**落地位置**（★ 与上文推荐解法有一处路径差异，特此记录）：

| 项 | 上文推荐 | 实际落地 |
| --- | --- | --- |
| 文件路径 | `harmonica_eval/bootstrap.py`（包根） | ★ `harmonica_eval/algorithms/bootstrap.py`（C3 内） |

★ **为什么落在 C3 内**：装配根 import 的是 `dynamics` / `pitch` / `timing` 三个 C3 模块；
放在 `algorithms/` 包内，它对这三个模块的相对 import 是同包引用（`from . import dynamics`），
不产生新的跨组件依赖。放在包根则需要 `from .algorithms import ...`，
会让「装配根」本身成为一层新的跨界点。**两种位置都能关闭本挑战，
本轮选择前者以避免新增跨界层级。**

**落地文件**：
- `harmonica_eval/algorithms/bootstrap.py`（123 行壳件，2 函数 / 2 SHELL / 0 实现）
  - 铭牌 `FILE-ID: FILE-206`
  - `REGISTRATION_ORDER = ("pitch", "timing", "dynamics")`（唯一顺序来源）
  - `build_plugin_specs()` / `build_default_registry()` 两个函数体保持 SHELL
- `.spec/build/FILE-206-v1.md`（Build Instruction，本轮补齐）
  - §8.3 给出「装配根唯一性」的可机械判定形式：
    **全仓恰好一处 import 具体算法模块，且必须是 `bootstrap.py`**；
    一旦出现第二处，立即变红。

**实测证据**（本轮实跑，非引用转述）：

```
$ PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_shell.py
  ⑤ 依赖方向（core 不得知道算法的存在）
    ✅ 18 个文件，全部符合依赖方向

$ grep -nE "import" harmonica_eval/host/app.py | grep -iE "pitch|timing|dynamics"
  （无输出 —— host 已不 import 具体算法）

$ grep -rn "from \. import.*(pitch|timing|dynamics)" --include="*.py" harmonica_eval/
  harmonica_eval/algorithms/bootstrap.py:56:from . import dynamics, pitch, timing
  （唯一一处）

$ PYTHONDONTWRITEBYTECODE=1 python3 tools/check_bi_scripts_exec.py
  ❌ FILE-206-v1  PASS 3/4
      · 脚本4: EXEC_FAIL NotImplementedError: SHELL: FILE-206 待注入实现
  （§8.6 是「注入后行为验收」，当前必然失败 —— 正确的空壳状态）
```

★ **上列四条共同证明**：不变量甲对 Host 继续成立，且「谁负责装配」已是单点可扫描事实。

**★ 关闭时仍未连通的物理通路（如实记录，不掩盖）**：

裁定与壳件已落地，但**装配链尚未接通** ——
`bootstrap.py` 目前**没有被任何文件 import**，因为 Host 仍是 SHELL。
「知道所有实现」有了唯一位置，但还没有调用者。
**这需要注入 `FILE-301`（Host 装配点）才会闭合，不属于本挑战的裁定范围。**

**★ 遗留的关联死路（属盲审 BLOCK-4，不在本挑战内）**：

`.spec/build/FILE-201-v1.md:466-476` 判据 A 要求
`from harmonica_eval.algorithms.pitch import SPEC` 并断言 `p.algorithm_id == 'pitch'`，
但三处同时失效：`SPEC` 不存在、`plugin_id` 已由负责人 BLOCK-4 裁定改名为 `algorithm_id`、
所需端口元组无合法来源。**该文件需另派任务同步，本轮未改。**

**★ 上文「影响面」四项的真实状态**：

| 项 | 状态 |
| --- | --- |
| `host/app.py:114-122` `HostApp.__init__` docstring | ✅ **已同步**（现写「C1 不再是『知道有哪些实现』的地方」，并指向 `algorithms/bootstrap`；`harmonica_eval/host/app.py:113-124`） |
| `COMPONENTS.md:381-387` 不变量 C 措辞 | ✅ **已同步**（现写「物理装配根 `algorithms/bootstrap.py`」；`COMPONENTS.md:384`） |
| `tools/check_plugin_contract.py` 第②条 | ✅ 当前 13/13 通过，无需改动 |
| `host/app.py:257` `build_default_app` docstring | ★ **仍待同步**：仍自称「composition root：全系统唯一知道『用哪个 Core 实现、有哪些算法』的地方」，与已关闭的裁定冲突（装配根已是 `algorithms/bootstrap.py`）。该函数当前为 SHELL，措辞随注入一并改。 |
| Host 侧接线：`build_default_app()` 接收 `bootstrap.build_default_registry()` 的产物 | ★ **仍待同步**（两者当前均为 SHELL，待注入时接线） |

★ **本挑战关闭的是「不变量冲突」这一裁定层问题，不等于上述同步工作已完成。**

---

## GC-204-09 ★ 我在同一轮内三次"没实测就下结论"

**状态**：`CLOSED`（已核实并记录，作为本项目的行为约束）

### 三次失误（全部有实测证据）

**失误一：给子代理的"陈旧引用清单"漏掉了整个 `prompts/` 目录。**

我的排查命令只扫了 `.spec/build/FILE-*-v1.md`，
而 `.spec/prompts/COMP-C1/downstream.md` 与 `COMP-C3/downstream.md`
**各含 1 处把 `ALGORITHMS` 当现行权威的活引用**。
子代理自行扩大扫描范围才发现（现已修）。

★ **性质**：我给的是一个**看起来很具体**的清单（带文件名和命中数），
具体到让人以为它已经完整。具体性伪装了完整性。

**失误二：把 `harmonica_eval/cockpit/app.py` 误报为破坏面。**

我说它"直接引用了被删的 `ALGORITHMS`"。子代理实跑后指出：
那里是 `UiCommandKind.RUN_ALGORITHMS`（`cockpit/app.py:62`），
是**用户点"运行算法"这个命令的合法契约枚举**，与被删的注册表毫无关系。
**我又一次被裸子串骗了** —— 正是 GC-204-07 同一个坑，我在同一天内踩了两次。

**失误三：把 `tools/derive_clusters.py` 列为破坏面，但我根本没运行过它。**

实测 `python3 tools/derive_clusters.py --raw` → **exit 0**。
它当时是"静默降级"（try 里读不到就打个警告），
子代理后来指出**静默降级违反宪章 §5.6**，建议改为显式失败 —— 这个判断是对的。
但"它有问题"和"它崩溃"是两回事，我把两者混为一谈。

### 为什么值得单独记录

GC-204-07 已经记录过一次"裸子串计数失误"。
**我在同一天内重复了同一个错误模式**，且是在刚刚认领完"我不会再犯"之后。

★ 更值得警惕的是失误三：**我列了一张"破坏面清单"给负责人，
里面有一条我从未执行过任何命令。**
那不是判断失误，是**根本没有判断**。

### 固化的行为约束

1. **凡是要写进"清单"的东西，必须先跑一遍确认。**
   清单的每一项都要有 `文件:行号` + 实际命令输出。
   凭印象列出的条目不写进清单。
2. **同一类错误（裸子串、误报）当天重复发生时，必须停下来查根因**，
   而不是又道歉一次。GC-204-07 的根因是"计数口径未定义"，
   正确处置是**换成词边界 + 把口径写进脚本**，而不是"下次小心"。
   ★ 本轮 `check_counts.py` 已改为词边界口径，根因已消除。
3. **子代理的纠正一律先核实再采纳，但一律不辩护。**
   本轮 5 次被纠正，全部成立。这不是子代理比主管聪明，
   是**主管在并行下没有执行验证的余裕**。

---

## GC-204-10 "行号优先、锚点兜底"是设计错误

**状态**：`CLOSED`（已裁定改为锚点优先）

### 事实

`check_counts.py` 的 Rule 原本用**行号**定位文档里的数量声明。
我加了 `locate` 锚点作为兜底，定位顺序是：

```
先试 line_no → 该行不含 locate 时，才在全文搜 locate
```

★ **这个顺序让锚点形同虚设**：只要行号碰巧对，**锚点写错永远不会被发现**。

实测后果已经发生：
`ErrorCode` 那条 Rule 的锚点从一开始就写错了
（指向 `INV-003-10`，但 ErrorCode 实际在 `INV-003-11`），
因为行号恰好命中，它一直报"通过"。

**更严重的是**：独立实测发现 3 条 `INV-003-N` 锚点在目标文档里**各匹配 3 行**
（INV 表格 + §8 代码块注释 + §9 判据清单三处引用同一编号）。
也就是说"用 INV 编号当锚点"这个假设**整体不成立**，
而这个缺陷在"行号优先"机制下**永远不会被暴露**。

### 裁定

**锚点优先，行号只作校验**：
- 有 `locate` → **必须**用锚点定位；行号只用来**校验**是否漂移。
  锚点 0 命中或 >1 命中 → **直接报错，不许回退到行号**。
- 无 `locate`（约 53 条）→ 保持行号定位，但**汇总里必须报告"N 条未锚定"**，
  让这批的行号漂移风险**可见**，而不是隐形。

### 元教训

★ **"加了一层防护"不等于"防护生效"。**
我加锚点时以为自己在修脆弱性，实际上只是给脆弱性套了个
**只在特定时刻才生效**的壳。
真正检验防护是否生效的办法只有一个：**故意写错，看它会不会红**。
本轮之前我没做过这个测试，是子代理发现的。

---

## 附：本轮未关闭挑战汇总

| ID | 状态 | 阻塞 Freeze？ |
| --- | --- | --- |
| GC-204-01 C1 会话 API 与 G8 矛盾 | **OPEN** | ✅ 是 |
| GC-204-02 `_scratch` 陈旧副本 | CLOSED | 否 |
| GC-204-03 `validate_result` 职责边界 | CLOSED | 否 |
| GC-204-04 `entry` 签名 | CLOSED | 否 |
| GC-204-05 `UNITS` 缺两值 | CLOSED | 否 |
| GC-204-06 `InputResolution` 归属 | CLOSED | 否 |
| GC-204-07 裸子串计数失误 | CLOSED | 否 |
| GC-204-08 不变量甲/乙冲突 | CLOSED | 否（2026-09-24 裁定方案甲落地；★ 装配链待注入接通，见该节「已解决」） |
| GC-204-09 三次未实测即下结论 | CLOSED | 否 |
| GC-204-10 锚点机制设计错误 | CLOSED | 否 |

**当前一条 OPEN：GC-204-01（阻塞 Freeze）。**
★ GC-204-08 已于 2026-09-24 关闭（裁定方案甲，`algorithms/bootstrap.py` 落地并实测通过）；
★ 但其「装配链待注入接通」一项仍待 FILE-301 注入后闭合，详见该节「已解决」。



