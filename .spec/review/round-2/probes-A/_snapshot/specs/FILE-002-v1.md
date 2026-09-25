# FILE-002 — harmonica_eval/__main__.py

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/__main__.py`
> 生成依据：`harmonica_eval/__main__.py` 头铭牌（FILE-ID: FILE-002 / COMPONENT: COMP-PKG / SPEC: SPEC.md@v2.1 §3 · PLAN.md@v2 §四/§六 · COMPONENTS.md@v2 §5 不变量 F）· `.spec/build/_TEMPLATE.md`（10 节结构）
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-002 |
| 所属组件 | COMP-PKG（包入口；本身不是组件） |
| 层级 | L3（symbol / implementation） |
| 上游 | 进程调用者：`python3 -m harmonica_eval --reference <wav> --practice <wav> [--out <json>]`（人类 / 脚本 / CI）。数据上游为 C1 发布的会话状态与数值结果（经 `contract.UiView` 投影） |
| 下游 | `harmonica_eval.contract`（只读导入；取 `UiView` / `UiScalar` / `UiSeries`）。落盘产物 `data/out/metrics.json` 与 `data/out/report.md` 的读者：人类、diff 工具、CI 归档 |
| 同层邻居 | 包内其他文件：`harmonica_eval/__init__.py`、`harmonica_eval/contract.py`、C2 / C3 的实现模块。本文件对它们**只读**；import 面只允许 `.contract`（见 §3） |
| 你的权限 | 只实现本文件 `harmonica_eval/__main__.py` |

**你的权限**：只实现本文件。不得修改任何其他文件，不得修改契约，不得新增端口，不得新增依赖。

`harmonica_eval/contract.py` 是 C1 的投影契约，属**只读上游**：本文件引用其中的符号与字段名，绝不修改、绝不复制其定义、绝不用本地副本替代。

---

## 2 · 这个文件为什么存在

追溯到 SPEC.md §3「单次分析产出（`data/out/`）」与 PLAN.md §八 阶段 D「首次端到端出指标」：本文件是那个交付物的**入口**。它把两段音频推进完整流程（建数据面 → 跑算法），再把 C1 的投影落成两份人类与机器都可读的产物。

**删掉它会坏掉什么**：

1. **不变量 F 失去验证载体**。COMPONENTS.md §5 不变量 F 要求「C4 缺席时全流程仍须跑通」。没有本文件，就没有任何一条**不经过界面**的执行通路，不变量 F 无法被观测。
2. **阶段 D 无法交付**。没有进程入口，就没有「首次端到端出指标」这个可运行物件；C1 / C2 / C3 全部只能被单元测试局部触达。
3. **结果无法离开进程**。指标只存在于内存里的 `UiView`，无法被 diff、无法被归档、无法回答「这个数字是什么、怎么算的、单位是什么」。
4. **CI 与脚本失去退出码**。没有 `EXIT_OK / EXIT_FAILED / EXIT_USAGE` 三分，自动化无法区分「我调错了」与「它跑挂了」。

### ★ 结构定位：无头入口与 C4 图形界面是同一类东西

C4（图形界面，`cockpit`）与本文件在结构上是**同一类东西**：两者都是**内核之外的结果消费者**。

- 两者的输入面完全相同：`contract.UiView`（`state` / `scalars` / `series` / `error_code` / `error_detail`）。
- 两者都**不进入内核**：不做 DSP、不做对齐、不做特征计算、不做指标重算、不改写 C1 给的任何数值。
- 两者的差别只在**消费方式**：C4 把投影画到屏幕上；本文件把投影**落到磁盘上**（`metrics.json` + `report.md`）。
- 两者之间**零依赖、零 import、零调用**：本文件绝不 import `cockpit`，C4 绝不 import 本文件。

**「删掉 C4 内核仍须跑通」在这一文件中的体现**：本文件是 C4 缺席时的**唯一通路**。把 `cockpit` 从环境中整体移除（不可导入）后，本文件的 import 图**不发生任何变化**，`run_headless` → 双落盘 → 退出码这条链路仍必须完整产出两份产物。因此本文件的验收方式不是「跑一遍试试」，而是「在 `cockpit` 被显式阻断导入的进程中跑通」（§8 判据）。

---

## 3 · 你能用的东西（依赖清单，封闭）

**允许 import**（穷举；集合之外的一切均禁止）：

| 类别 | 名称 | 用途 |
| --- | --- | --- |
| 标准库 | `__future__`（`annotations`） | 文件头已存在的未来导入 |
| 标准库 | `argparse` | 命令行解析 |
| 标准库 | `json` | `metrics.json` 序列化 |
| 标准库 | `sys` | `sys.argv`、`sys.stderr` |
| 标准库 | `pathlib`（`Path`） | 输出路径与落盘 |
| 标准库 | `typing`（`Sequence`） | 签名注解 |
| 本包内 | `.contract`（`UiView` / `UiScalar` / `UiSeries`） | 投影契约（**只读数据结构**） |
| 本包内 | `.host.app`（`build_default_app`，见下方 ★ 更正） | **C1 门面**：`run_headless` 必须能驱动会话 |

★★ **更正（本版，这是一处会导致入口完全无法工作的缺陷）** ★★

**上一版写的是**：`.contract`（…「及该模块导出的**会话驱动符号**」），
并把「本包内除 `.contract` 之外的任何模块」列入**禁止**。

**实测证明这两条合起来使 `run_headless` 无法实现**：

1. **`contract.py` 里没有任何"会话驱动符号"。** 实测其全部 39 个导出：
   - 3 个 `Protocol`：`AlgorithmDataContract` / `HostContract` / `UiProjectionPort`
     —— **Protocol 不能实例化**（实测 `HostContract()` → `TypeError`），
     只能作类型注解，**无法驱动任何会话**；
   - 5 个 `Enum`、9 个 `dataclass`、4 个异常类、2 个常量元组。
   `contract.py` 自己的 ROLE 也写着「**纯声明，无行为**」。
2. **真正的 C1 门面在 `host/app.py`**：`class HostApp`（:70）与
   `build_default_app()`（:243）。实测**全仓没有任何调用方**。
3. **而上一版禁止 import `host`。** 于是：
   - §4.2 要求 `run_headless` 「把 `reference_uri`、`practice_uri` 交给 C1 会话」、
     「必须等到 `state == DATA_READY`」；
   - 但唯一能驱动会话的对象在 `host`，而 `host` 被禁；
   - `contract` 里又没有可驱动的东西。
   ⇒ **入口 → C1 的这条边在 import 层面是断的。**
   实现者只能二选一：违反 §3 去 import `host`，或者违反 §4.2 不驱动会话。
   **两者都是缺陷**，且这正是 §10 定义的「本文件与任何上游工件冲突」。

**本版冻结的修正**：**允许** `from harmonica_eval.host.app import build_default_app`。

★ **第二版再更正（P2 管线审查 F1）**：上一版我写的是「允许 import `.host`」——
**那仍然跑不通**。实测：

```
>>> from harmonica_eval.host import build_default_app
ImportError: cannot import name 'build_default_app' from 'harmonica_eval.host'
```

因为 `host/__init__.py` 的 `__all__ = ["app"]` **只声明子模块名**，
并不把 `build_default_app` 绑成包属性（见 FILE-300 §4.1 的 E2/E3 讨论）。
唯一能跑的写法是 `from harmonica_eval.host.app import build_default_app`，
其 AST 键是 **`.host.app`**（三段），不是 `.host`。
上一版把白名单写成 `.host`，于是「允许 import 的东西」与
「唯一能跑通的写法」**差一个层级** —— 实现者仍被卡死。

**这条正是本轮的教训**：`produced_by` / `__all__` / import 路径三者
各自都"看起来对"，只有真跑一次才知道哪条能通。

- `run_headless` **必须**通过 `build_default_app()` 取得 C1 门面，
  再依次调用其 `HostContract` 消费方方法完成四步。
- **仍然禁止** import：`cockpit`（不变量 F 的判定线不变）、C2 / C3 的**实现模块**
  （`core.*` / `algorithms.*`）—— 入口只与 C1 门面与 `contract` 对话。
- **依赖方向仍然正确**：`__main__` → `host.app` → (`core`, `algorithms`)。
  `host` 是装配点，入口依赖装配点是正常的（入口本就在最外层）。
- §8 的 import 闭包断言与 §6 的 INV-002-1 相应放宽为：
  `import 闭包 ⊆ {__future__, argparse, json, sys, pathlib, typing, .contract, .host.app}`，
  且**仍须断言 `cockpit` 不在闭包内**（这才是不变量 F 的真正判据）。

★ **诚实记录**：`FILE-002` 与 `FILE-105`（`api.py`）之间原本还有一处不一致 ——
`FILE-105` 说 C1 经 `HostCore` 的 7 个操作驱动，而 `FILE-002` 说 C1 门面在
`contract` 里。本更正后，**唯一**的 C1 门面是 `host.app.build_default_app`，
`FILE-105` 的 `HostCore` 是 C2 侧实现 `HostContract` 的对象（**被 C1 持有**），
两者是「调用方 / 实现方」关系，不再冲突。

**禁止 import**（逐条列举）：

- `harmonica_eval.cockpit`、任何名字以 `cockpit` 开头的模块、任何 UI / 图形 / 终端渲染依赖。**这是不变量 F 的判定线。**
- 本包内除 `.contract` 与 `.host.app` 之外的任何模块（含 `__init__`、C2 / C3 的实现模块 `core.*` / `algorithms.*`、任何 pipeline / ingest / align / features / metrics 实现模块）。**★ 本版更正：`.host` 已从禁止改为允许**（见上表下方的 ★★ 更正）。
- 第三方数值与音频栈：`numpy`、`scipy`、`soundfile`、`librosa`、`audioread`、`resampy`、`pandas`、`matplotlib`、`plotly`。
- 网络与进程：`requests`、`urllib`、`http`、`socket`、`subprocess`、`multiprocessing`、`concurrent`、`asyncio`。
- 噪声与不确定性来源：`logging`、`warnings`、`random`、`time`、`datetime`、`uuid`、`os.environ` 的任何读取、`platform`、`getpass`。
- 任何不在上表「允许 import」行内的东西。

**Python 版本约束**：沿用仓库既有 `python3`。只用 3.8 起可用的语法与 API。文本写盘必须显式 `open(path, "w", encoding=..., newline=...)`，不调用 `Path.write_text` 的 `newline` 参数（该参数 3.10 才存在）。

---

## 4 · 你要实现什么（行为规格）

### 4.0 冻结常量（模块级，只读，不得改值）

| 常量名 | 值 | 用途 | 来源 |
| --- | --- | --- | --- |
| `DEFAULT_OUT_DIR` | `"data/out"` | 缺省输出目录 | `harmonica_eval/__main__.py:49` |
| `DEFAULT_METRICS_FILENAME` | `"metrics.json"` | `--out` 缺省文件名 | `harmonica_eval/__main__.py:52` |
| `REPORT_FILENAME` | `"report.md"` | 报告文件名，与 `metrics.json` 同目录 | `harmonica_eval/__main__.py:55` |
| `EXIT_OK` | `0` | 全流程成功 | `harmonica_eval/__main__.py:58` |
| `EXIT_FAILED` | `1` | 运行期失败 | `harmonica_eval/__main__.py:61` |
| `EXIT_USAGE` | `2` | 命令行用法错误（与 argparse 约定一致） | `harmonica_eval/__main__.py:64` |
| `_JSON_SCHEMA_VERSION` | `1` | `metrics.json` 顶层 `schema_version` | 本文件冻结 |
| `_JSON_INDENT` | `2` | `json.dump(indent=)` | 本文件冻结 |
| `_JSON_SEPARATORS` | `(",", ": ")` | `json.dump(separators=)` | 本文件冻结 |
| `_JSON_ENSURE_ASCII` | `False` | 中文 `label` 以 UTF-8 原样存 | 本文件冻结 |
| `_JSON_ALLOW_NAN` | `False` | NaN / Infinity 必须显式失败 | 本文件冻结 |
| `_JSON_SORT_KEYS` | `False` | 键序 = 本文件规定的固定序 | 本文件冻结 |
| `_TEXT_ENCODING` | `"utf-8"` | 两份产物的编码 | 本文件冻结 |
| `_TEXT_NEWLINE` | `"\n"` | 两份产物的换行 | 本文件冻结 |
| `_REPORT_TITLE` | `"# 数值报告"` | `report.md` 首行 | 本文件冻结 |
| `_REPORT_EMPTY_ITEM` | `"- （无）"` | 空节占位行 | 本文件冻结 |
| `_BASIS_GLOSS` | `{"REFERENCE": "保留源时间，抢拍拖拍可见", "WARPED": "时间归一化，抢拍拖拍已被抹掉"}` | `timeline_basis` 轴语义注解 | 本文件冻结（与 `summarize_series` 铭牌一致） |
| `_UNIT_CONVERSION_FACTOR` | `1` | **本文件不做任何单位换算**（恒等因子） | 本文件冻结 |
| `_SECONDS_UNIT_LABEL` | `"秒"` | 报告中 t 轴单位字样 | 本文件冻结 |

`DEFAULT_OUT_DIR`、`DEFAULT_METRICS_FILENAME`、`REPORT_FILENAME`、`EXIT_OK`、`EXIT_FAILED`、`EXIT_USAGE` 六个名字与取值由头铭牌冻结，必须原样保留，且必须出现在 `__all__` 中。

### 4.1 `build_parser() -> argparse.ArgumentParser`

- **输入**：无。
- **输出**：一个 `argparse.ArgumentParser` 实例，**只**含三个选项，名称与语义固定：

| 选项 | 必填 | 类型 | 语义 | 缺省 |
| --- | --- | --- | --- | --- |
| `--reference` | 是 | `str` | 参考演奏路径（原样字符串） | 无 |
| `--practice` | 是 | `str` | 练习演奏路径（原样字符串） | 无 |
| `--out` | 否 | `str` | `metrics.json` 的落点 | `None`（由 `main` 折算成 `DEFAULT_OUT_DIR / DEFAULT_METRICS_FILENAME`） |

- **算法口径**：构造 parser 并 `add_argument` 三次；`prog` 不设置；`--out` 的 `default=None`；`required` 只在两个路径选项上设 `True`。帮助文本必须包含三个语义关键词：`参考演奏`、`练习演奏`、`metrics.json`。
- **边界**：**不调用 `parse_args`**（解析归 `main`）。函数体内不读 `sys.argv`、不访问文件系统、不退出进程。
- **不变量**：`build_parser()` 连续两次调用返回等价配置；未知选项（例如 `--verbose`、`--seed`、`--config`）由 argparse 判为用法错误并以 `EXIT_USAGE` 退出。
- **参考方向不可互换**：`--reference` 是参考演奏、`--practice` 是练习演奏。节奏类指标的方向、bias 的正负号取决于此。本文件不校验顺序、不做交换、不做推断。
- **音频格式**：`.wav` 只是用法示意；本文件**不校验扩展名、不解码、不打开文件**。格式解析归 C2 ingest。

### 4.2 `run_headless(reference_uri: str, practice_uri: str, out_path: Path) -> UiView`

- **输入**：`reference_uri` 参考演奏路径（原样字符串，不做 URI 解析、不做 glob、不做相对路径归一化）；`practice_uri` 练习演奏路径（同上）；`out_path` `metrics.json` 的落点。
- **输出**：C1 的最终投影 `UiView`（含 `state` / `scalars` / `series` / `error_code` / `error_detail`）。
- **算法口径**（固定四步，顺序不可变；除第 1 步与第 3 步的 gate 判定外不插入任何逻辑）：
  1. 登记两段输入：把 `reference_uri`、`practice_uri` 交给 C1 会话（登记顺序：先参考、后练习）。
  2. 构建数据面：预生成 + Seal。**必须等到 `state == DATA_READY`**。
  3. Gate 判定：`state == DATA_READY` → 触发算法；`state != DATA_READY` → **不触发算法**，直接返回当前视图。
  4. 取视图：返回 C1 的最终投影 `UiView`。
- **`out_path` 的用途冻结**：仅供 C1 会话记录「本次运行的输出落点」（是否接受该信息由 `contract` 的会话驱动面决定）。本函数**不创建目录、不打开文件、不做存在性检查、不写任何字节**。若实现者判定该参数在 `contract` 的驱动面上无对应位置，保留签名即可，**不得为了「用上它」而新增任何行为**。
- **失败态**：`state` 为失败态时**照样返回视图**（不抛），退出码由 `main` 决定。
- **异常**：`OSError` / `ValueError` 属进程级失败，**直接抛，不吞**。
- **禁止**：函数体内不出现 `try` / `except`（算法级失败由 C1 归一化为 `error_code`，本函数如实转述）。不归一化、不翻译、不包装 `error_code`。不重算任何数值。
- **不变量**：返回后，`view` 的每个字段都与 C1 发布的内容逐位相同；除 C1 会话自身的副作用外，本函数不产生任何文件系统副作用。

### 4.3 `write_metrics_json(view: UiView, out_path: Path, reference_uri: str, practice_uri: str) -> None`

★★ **签名更正（第三轮盲审 A 发现，本版修正）：本函数原来只收 `(view, out_path)`，
**无法**产出 §4.3 第 3 步要求的 `inputs` —— 这是一个**死路**。** ★★

真实缺陷：`inputs` 固定为 `{"reference": <reference_uri 原样>, "practice": <practice_uri 原样>}`，
但 `UiView` 的 8 个字段是
`session_id / state / series / scalars / progress / error_code / error_detail / note`
—— **没有任何字段携带 URI**（实测：`UiScalar` 无、`UiSeries` 无）。
而本文件 §3 禁止 import `core.*`，故本函数**也不能**去问 C1 的会话要。
⇒ 原来的签名下，第 3 步**无法实现**，实现者只能自己发明一个通道。

**修法**：`main` 手里同时有 `args.reference` / `args.practice` 和 `view`，
由**调用方显式传入**，不新增任何数据通道。
这**不动 `contract.py` 一行** —— 这两个函数都是 `__main__` 的私有函数，
不在任何契约里。同样更正适用于 §4.4 `render_report_markdown`（见该节）。

★ 这是**同一根因的第三次出现**：投影（`UiView`）不携带写盘方需要的量，
而写盘方拿不到别的通道。前两次是 F8 的 `meta.duration_*` 与
`alignment.*`。三次都指向同一个结论：**「谁能看见什么」必须在设计时逐项对齐，
不能默认「反正是同一个进程」**。

---

★★ **关于 SPEC §3 的 `metrics.json` 结构 —— 已裁定（负责人 2026-09-24 批准）** ★★

`SPEC.md §3` 给出了一份**不同的**顶层结构：
`meta` / `alignment` / `global` / `sections[]`。
本文件冻结的是 `schema_version` / `inputs` / `state` / `scalars` / `series`。
**两者此前没有任何映射关系**（P1 审查 F8 / P2 审查 F9 独立发现）。

**裁定**：**以本文件的结构为准**；SPEC §3 的 JSON 片段**降级为示意**，
不是冻结契约。理由三条，逐条可查：

1. **SPEC §3 的键没有可计算的来源。** 实测全仓检索：
   `in_tune_ratio` / `pitch_bias_cents` / `voiced_ratio` 三个键
   **定义数 = 0**（除 SPEC 自身）；
   `pitch_cents_mae` / `timing_mae_ms` / `energy_db_delta` 各只有 **1 处**，
   且都在 `research/02-landscape-research.md`（**调研笔记，非规格**）。
   SPEC §3 只给了字段名与 `0.0` 占位，**没有给任何一个键的计算口径**。
   按它实现 = 让实现者自己发明口径 —— 那正是 SPEC 自己禁止的。
2. **SPEC §3 的 `alignment.*` 四个键在 12 个端口里没有数据来源。**
   `method` / `mean_abs_warp_sec` / `tempo_ratio` / `confidence`
   实测**没有任何端口**承载它们。`align()` 只返回 `warp_path`
   （返回注解 `npt.NDArray`）。要产出它们必须**新增端口** ——
   而端口清单是**封闭的 12 个**（负责人裁定）。
3. **SPEC §3 的 `sections[]` 依赖 SPEC §6，而 §6 尚未确认。**
   `SPEC.md:137` 仍是 `- [ ] 负责人确认 §6 分段方式`。
   按 AGENTS.md 铁律 3「未确认项不得实现」，**不得**写入主流程。

**SPEC §3 的意图如何保留**：它要的每个量，在**本文件的结构**里都有落点 ——
通过 `scalars` 的 `key` 表达（键名取自 `algorithms.PAYLOAD_SCHEMAS`，
见 `FILE-200` 的规则「`UiScalar.key` 的取值必须取自本表的键名」）：

| SPEC §3 的键 | 本结构里的落点 | 来源 |
| --- | --- | --- |
| `global.pitch_cents_mae` | `scalars["median_abs_cents"]` | `pitch` payload |
| `global.in_tune_ratio` | `scalars["off_pitch_ratio"]` 的补（`1 - x`）★ **口径待定，见下** | `pitch` payload |
| `global.timing_mae_ms` | `scalars["median_onset_ms"]` | `timing` payload |
| `global.energy_db_delta` | `scalars["median_db"]` | `dynamics` payload |
| `meta.sr` | `scalars["sample_rate"]`（`pitch` payload 已含） | `pitch` payload |
| `meta.duration_ref` / `duration_user` | ★ **无落点，见下** | —— |
| `alignment.*` | ★ **无落点**（无端口承载） | —— |
| `sections[]` | ★ **不做**（§6 未确认） | —— |

★ **`in_tune_ratio` 的口径未定，本文件不发明**：
`pitch` payload 只有 `off_pitch_ratio`（偏离音比例），
SPEC 要的是 `in_tune_ratio`（在音比例）。二者是否互补取决于
`off_pitch_ratio` 的分母口径 —— 而该口径**未冻结**。
故本文件**不写**这个换算，实现者若需要须先由负责人裁定。

★ **`meta.duration_*` 无落点**：实测 `UiView` 的字段是
`session_id / state / series / scalars / progress / error_code / error_detail / note`
—— **没有**采样率、没有时长。而 `__main__` 只拿得到 `UiView`（拿不到 `SurfaceManifest`）。
故 `duration_ref` / `duration_user` 若要出现在产物里，
**必须先有人把它们放进投影**（`UiScalar` 或 `UiSeries`）—— 那是 C1 的改动，
不是本文件的。本文件**不得**自行去问 C2 要 manifest（那会破坏
「入口只与 C1 门面对话」的分层，见 §3）。

> **这是 SPEC 与模具之间唯一一处**由负责人明确裁定的降级。
> 已登记在 `.spec/review/round-1/DISPOSITION.md` §5（F8）。

---

- **输入**：`view` C1 投影；`out_path` 目标文件路径。
- **输出**：`None`（副作用：写出 `out_path`）。
- **算法口径**（固定，不得增删键、不得改键序）：
  1. `out_path.parent.mkdir(parents=True, exist_ok=True)`（`out_path` 无父目录时，`Path(".")` 的 `mkdir` 必须成功）。
  2. 构造顶层对象，键序**固定**为：`schema_version` → `inputs` → `state` → [`error_code`] → [`error_detail`] → `scalars` → `series`。方括号内两键**仅在投影对应字段非 `None` 且非空串时出现**；不补 `null`、不写空串。
  3. `inputs` 固定为 `{"reference": reference_uri, "practice": practice_uri}`，键序固定。★ 两个值取自**本函数的入参**（见本节开头的签名更正），**不得**从 `view` 里翻找、不得新增 `UiScalar` 键去承载路径（`FILE-200` 规定 `UiScalar.key` 必须取自 `PAYLOAD_SCHEMAS` 的键名，其中没有 URI 类键）。
  4. `state` = 投影 `state` 的枚举名：若 `getattr(state, "name", None)` 是 `str` 则取该值，否则取 `str(state)`。不映射、不翻译。
  5. `scalars` = 按投影原序的列表，每个元素键序固定为：`key` → `label` → `value` → `unit` → [`threshold`]。`threshold` 仅在投影携带该字段时出现（原样写出，不判定、不与 `value` 比较、不生成布尔结论）。
  6. `series` = 按投影原序的列表，每个元素键序固定为：`key` → `label` → `unit` → `timeline_basis` → `n_points`。`timeline_basis` 写成枚举名（规则同第 4 步），取值必须落在 `{"REFERENCE", "WARPED"}`。

     ★★ **第四版更正（P2 管线审查 F4）：`n_points` 不是 `UiSeries` 的字段。** ★★

     上一版要求 `n_points` 取「投影 `UiSeries` 的点数**元信息**（整型），
     不遍历、不统计 `values`」，并在 §5 禁止用 `len(values)` 替代。
     **实测**：`contract.UiSeries` 的字段恰好 7 个 ——
     `key, label, t, values, unit, timeline_basis, source_port`；
     `hasattr(UiSeries, "n_points")` 为 **False**，全仓 `n_points` 命中数 **0**。
     于是上一版把实现者逼进死胡同：**要一个不存在的字段，
     又禁止唯一能算出它的办法**。

     **本版冻结的口径**：`n_points` = `len(s.t)`（`t` 是 `UiSeries` 的
     **公开具体字段**，`Sequence[float]`，不是惰性对象）。
     - 断言 `len(s.t) == len(s.values)`（这是 C4 侧也做的校验 —— 见
       `FILE-401-v1.md` **§4.7 `render_series_plot`** 第 6 步
       「数据长度校验：`assert len(series.t) == len(series.values)`」；
       ★ 更正：原文写「见 FILE-401 §4.x」是个**占位符**，没有可查的节号 ——
       盲审 probe 14 实测 FILE-401 中不存在名为 `§4.x` 的节），
       不等 → 停止并上报（§10），**不得**截断到较短者。
     - `n_points` 是**本文件算出来的派生子**，不是从投影读来的字段。
     - §5 的原禁令相应收窄为：**不得**用 `len(s.values)` 之外的途径"估算"点数
       （例如按时间跨度除以某个 hop 猜）；`len(s.t)` 是**唯一**正确来源。
  7. 序列化：`json.dump(obj, fh, ensure_ascii=_JSON_ENSURE_ASCII, indent=_JSON_INDENT, separators=_JSON_SEPARATORS, sort_keys=_JSON_SORT_KEYS, allow_nan=_JSON_ALLOW_NAN)`；随后显式写入一个 `"\n"`。
  8. 打开方式固定：`open(out_path, "w", encoding=_TEXT_ENCODING, newline=_TEXT_NEWLINE)`。
- **数值口径（写死）**：
  - **不做舍入**。`value` 为 `float` 时以 JSON number 写出，其最短往返表示与投影值的 `repr` 完全一致；禁止 `round()`、禁止格式化截断、禁止转字符串。
  - **不做单位换算**。换算因子恒为 `_UNIT_CONVERSION_FACTOR = 1`。`unit` 字段原样透传；时间类数值的单位由投影给出，本文件不改写、不规范化。
  - **不做补齐、不做推断**。键名与 `contract.UiScalar.key` / `contract.UiSeries.key` 一致。`UiScalar` 支持的取值类型：`int` / `float` / `str` / `bool` / `None`；`None` 如实写成 JSON `null`。
  - 同 `key` 的两条标量：**不合并、不去重、不重命名**，按原序各写一条（去重是 C1 的职责）。
- **边界**：空 `scalars` → 写 `"scalars": []`；空 `series` → 写 `"series": []`。`NaN` / `Infinity` 因 `allow_nan=False` 触发 `ValueError`（见 §5）。`view.error_code` 非空时照样落盘，如实写出。
- **异常**：`out_path` 不可写、父目录无法创建、磁盘满 → `OSError` 抛出，不吞、不降级、不换落点。
- **不变量**：落盘后，`json.load` 得到的 `scalars` / `series` 的长度与顺序与投影**逐位相同**；产物中不存在投影里没有的量。

### 4.4 `render_report_markdown(view: UiView, reference_uri: str, practice_uri: str) -> str`

- **输入**：C1 投影 + 本次运行的两个输入路径字符串。★ **签名更正**（与 §4.3 同因）：
  报告正文要求写出「参考 / 练习」两行，而 `UiView` **不携带 URI** ——
  原签名 `(view)` 同样无法产出这两行。由调用方 `main` 显式传入。
- **输出**：Markdown 文本（`str`），**以单个 `"\n"` 结尾**，无尾部空行。
- **算法口径**（骨架固定；`[]` 表示该行仅在条件成立时出现）：

```markdown
# 数值报告

- 状态：<state>
- 参考：<reference_uri>
- 练习：<practice_uri>
[- 错误码：<error_code>]
[- 错误详情：<error_detail>]

## 标量指标

- <label> = <value> <unit>（阈值 <threshold> <unit>）

## 曲线

- <label>：单位 <unit>，时间基准 <basis>（<basis 注解>），采样点 <n>，t 轴单位：秒
```

- `state` 文本规则同 §4.3 第 4 步。参考 / 练习两行的值**取自本函数的 `reference_uri` / `practice_uri` 入参**（与 §4.3 第 3 步同源，均为 `main` 的 `args.reference` / `args.practice`）；`describe_inputs` 只用于 CLI 用法回显（§4.6），**不得**在此处被调用 —— 本函数**禁止** import 或调用 `describe_inputs`（避免出现第二个来源）。
- `error_code` / `error_detail` 两行：投影对应字段非 `None` 且非空串时写出，**如实写，不美化、不翻译、不省略**。
- **`value` 格式化（写死）**：`int`（非 `bool`）→ `str(v)`；`float` → `repr(v)`；`bool` → `"true"` / `"false"`；`str` → 原样；`None` → `"N/A"`。禁止使用 `:.2f`、`%`、千分位、科学计数法重写。
- **`unit` 格式化（写死）**：`unit` 为 `None` 或空串时，省略` <unit>` 整段（不留多余空格）。`threshold` 为 `None` 时写 `（阈值 N/A）`。
- **阈值并列**：`threshold` 存在时写 `（阈值 <threshold> <unit>）`；**不判定「合格 / 不合格」**、不与 `value` 比较、不生成布尔结论。
- **曲线节**：每条 `UiSeries` 只列元信息（`label` / `unit` / `timeline_basis` / 采样点数），**不铺开数据点**、不重采样、不统计 `values`。本体即 `summarize_series` 的输出（§4.5）。
- **空节**：`scalars` 为空 → 该节正文为单行 `- （无）`；`series` 为空 → 该节正文为单行 `- （无）`。
- **顺序**：标量按投影原序，曲线按投影原序。不按 `label` 排序、不按 `key` 排序。
- **禁止内容**：不出现判定词与教学措辞：`合格`、`不合格`、`达标`、`优秀`、`建议`、`应该`、`结论`、`提升`。不下教学结论、不生成自然语言反馈（SPEC §1：只到数值层）。
- **不变量**：报告中出现的每个数字都在投影里找得到；投影里没有的量，报告中不出现。

### 4.5 `summarize_series(series: Sequence[UiSeries]) -> str`

- **输入**：C1 下采样后的曲线列表（每条含 `unit` 与 `timeline_basis`）。
- **输出**：**单个** `str`：每条曲线一行，行间以 `"\n"` 连接，无尾随 `"\n"`。空列表 → 返回 `""`（空字符串）。
- **单行格式（写死）**：
  `- <label>：单位 <unit>，时间基准 <basis>（<basis 注解>），采样点 <n>，t 轴单位：秒`
  - `<basis>` ∈ `{"REFERENCE", "WARPED"}`；`<basis 注解>` 取 `_BASIS_GLOSS[<basis>]`。
  - `<unit>` 为 `None` 或空串时写 `单位 未标注`（不写空段、不留双空格）。
  - `<n>` = 该 `UiSeries` 的点数元信息（整型，`str(n)`）。
- **算法口径**：只读元信息。**不重新采样、不统计 `values`、不计算任何数值**。
- **边界**：单元素列表 → 一行；`series` 中某条缺 `timeline_basis` → 见 §5（上报，不猜）。
- **不变量**：返回值中每条曲线**必须**写明 `timeline_basis`。REFERENCE = 保留源时间（抢拍拖拍可见）；WARPED = 时间归一化（抢拍拖拍已被抹掉）。轴的含义不标出来，图就会被误读。

### 4.6 `describe_inputs(reference_uri: str, practice_uri: str) -> str`

- **输入**：两段输入路径（原样字符串）。
- **输出**：单行 `str`，格式写死：
  `输入：参考=<reference_uri>；练习=<practice_uri>`
  路径含空格或非 ASCII 字符时原样写入，**不加引号、不转义、不做 URL 编码**。
- **算法口径**：只拼接字符串。**不读文件、不探测时长、不解析格式、不做存在性检查**（那是 C2 的 ingest）。不写入音频内容本身（`.gitignore`：音频不进库）。
- **不变量**：输出中两个路径与原输入逐字符相同（`out == f"输入：参考={reference_uri}；练习={practice_uri}"`）。

### 4.7 `main(argv: Sequence[str] | None = None) -> int`

- **输入**：`argv` 参数序列（**不含程序名**）。`None` → 取 `sys.argv[1:]`（把 `None` 原样交给 `parse_args`）。
- **算法口径**（固定顺序）：
  1. `args = build_parser().parse_args(None if argv is None else list(argv))`。
  2. `out_path = Path(args.out) if args.out else Path(DEFAULT_OUT_DIR) / DEFAULT_METRICS_FILENAME`。
  3. `view = run_headless(args.reference, args.practice, out_path)`。
  4. `write_metrics_json(view, out_path, args.reference, args.practice)`。
  5. `report_path = out_path.parent / REPORT_FILENAME`；以 `_TEXT_ENCODING` / `_TEXT_NEWLINE` 写入 `render_report_markdown(view, args.reference, args.practice)`。
  6. 退出码：`EXIT_FAILED` ⟺ 投影 `error_code` 非 `None` 且非空串；否则 `EXIT_OK`。
  7. **失败时照样走完第 4、5 步**：失败也必须落两份产物（可读报告里如实写 `error_code`）。
- **异常处理（写死）**：捕获 `OSError` 与 `ValueError`（含 `json` 的 `allow_nan=False` 触发的 `ValueError`）→ 向 `sys.stderr` 写**一行** `error: <异常类名>: <异常消息>` → 返回 `EXIT_FAILED`。除这两类之外的异常不捕获、不包装。
- **用法错误**：交给 `argparse` 自身报错并以 `EXIT_USAGE`（2）退出；`main` **不捕获** `SystemExit`。
- **输出纪律**：无论成功失败，**不把堆栈或诊断写到 stdout**（可读报告走 `report.md`；一行诊断走 stderr）。不打印进度条、不打印指标表。
- **绝不 import `cockpit`**：本入口是 C4 缺席时的唯一通路（不变量 F）。
- **不变量**：`main` 的返回值恒为 `EXIT_OK` / `EXIT_FAILED` 之一；`EXIT_USAGE` 只经 `SystemExit` 出现。

### 4.8 本文件层面的数值口径总则

本文件**不参与任何数值计算**（`MUST NOT`：不做 DSP、对齐、特征计算或任何数值处理）。因此本文件层面的「阈值 / 容差」集合为**空集**：不存在任何本文件自定义的判定阈值或容差。唯一由本文件固定的数值口径是序列化与格式化，全部写在 §4.0 与 §4.3 / §4.4；其中单位换算因子恒为 `_UNIT_CONVERSION_FACTOR = 1`（即不换算）。投影携带的 `threshold` 只被**原样搬运**，永不被比较。

### 4.9 公开符号闭合表

`__all__` 必须**恰好**为以下 13 项，顺序不限，不得增删：

`DEFAULT_OUT_DIR`、`DEFAULT_METRICS_FILENAME`、`REPORT_FILENAME`、`EXIT_OK`、`EXIT_FAILED`、`EXIT_USAGE`、`build_parser`、`run_headless`、`render_report_markdown`、`write_metrics_json`、`main`、`summarize_series`、`describe_inputs`。

四个 `raise NotImplementedError("SHELL: FILE-002 待注入实现")` 占位（`build_parser` / `run_headless` / `render_report_markdown` / `write_metrics_json` / `main`，共 5 处）必须被真实实现替换。文件末尾的 `if __name__ == "__main__": raise SystemExit(main())` 必须原样保留。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| 缺 `--reference` 或 `--practice`，或出现未知选项 | 显式失败：argparse 打用法到 stderr | `SystemExit(EXIT_USAGE)` = 2 |
| `--out` 指向的父目录无法创建 | 显式失败：不换落点、不改文件名、不降级到 stdout | `OSError` 从 `write_metrics_json` 抛 → `main` 捕获 → stderr 一行 → 返回 `EXIT_FAILED` = 1 |
| 目标文件无写权限 / 磁盘满 | 同上 | `OSError` → `EXIT_FAILED` = 1 |
| 输入音频缺失 / 不可解码 | **本文件不判定**：由 C2 ingest 报错、C1 归一化为 `error_code`；视图照常返回，两份产物照常落盘并写出 `error_code` | 返回视图 → `EXIT_FAILED` = 1 |
| `state != DATA_READY` 且 `error_code` 非空 | 显式失败：**不触发算法**，返回视图，仍落两份产物 | `EXIT_FAILED` = 1 |
| `state != DATA_READY` 但 `error_code` 为空 | **合同冲突**：不猜、不自造错误码、不写 `"UNKNOWN"` | 停止并上报（§10） |
| 投影含 `NaN` / `Infinity` | 显式失败：`allow_nan=False` 拒绝写出非法 JSON；**禁止**写成 `null`、`"NaN"`、`0` | `ValueError` → `main` 捕获 → `EXIT_FAILED` = 1（`metrics.json` 不被写出） |
| 某条 `UiSeries` 缺 `timeline_basis`，或 `timeline_basis` 落在 `{REFERENCE, WARPED}` 之外 | 停止：不猜轴语义、不写 `"UNKNOWN"`、不省略该字段 | 停止并上报（§10） |
| `len(s.t) != len(s.values)`（投影自相矛盾） | 停止：**禁止**截断到较短者、**禁止**按时间跨度估算点数 | 停止并上报（§10） |
| `metrics.json` 已写出，随后 `report.md` 写失败 | 显式失败：已落盘的 `metrics.json` **保留**，不回滚、不删除 | `OSError` → `EXIT_FAILED` = 1 |
| 任何「算不出来就返回默认值」的念头 | **禁止**（宪章 §5.6：禁止静默降级） | —— |
| 任何「先写个 workaround 以后再修」的念头 | **禁止**（§38） | 停止并上报（§10） |

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-002-1 | 本文件**绝不 import** `cockpit` 或任何 UI 依赖；import 闭包 ⊆ §3 允许清单（含 `.host.app`） | §8 的 AST 扫描断言 |
| INV-002-2 | **删掉 C4，内核仍须跑通**：在 `cockpit` 被 `sys.meta_path` 阻断导入的进程中，`main(...)` 仍返回 `EXIT_OK` 并产出两份产物 | §8 的「C4 缺席」用例 |
| INV-002-3 | 产物可追溯：`metrics.json` 的 `scalars` / `series` 与投影**逐位相同**（长度、顺序、`key` 集合、`value` 的 `repr`） | §8 的等价断言（`run_headless` 与产物对比） |
| INV-002-4 | 每条曲线必带 `timeline_basis`，取值 ∈ `{REFERENCE, WARPED}`；`report.md` 每条曲线行含「时间基准」与中文注解 | §8 的正则与取值断言 |
| INV-002-5 | 单位换算因子恒为 1：本文件不做换算、不改写 `unit`、不给时间量加单位换算 | §8 断言 `_UNIT_CONVERSION_FACTOR == 1` 且产物 `unit` 与投影 `unit` 全等 |
| INV-002-6 | 不静默降级：`error_code` 非空 ⟹ 退出码 `EXIT_FAILED`，且 `error_code` 同时出现在 `metrics.json` 与 `report.md` | §8 的失败用例 |
| INV-002-7 | 确定性：同一输入连续两次运行，`metrics.json` 与 `report.md` 字节完全相同（无时间戳、无随机、无主机名、无绝对路径注入） | §8 的两次运行 + `cmp` |
| INV-002-8 | 落盘范围闭合：除 `out_path` 与其同目录的 `report.md` 外，本文件不创建、不修改任何文件与目录 | §8 的 `git status --porcelain` 断言 |
| INV-002-9 | 失败态与错误码一致：若观察到 `state` 为失败态而 `error_code` 为空，必须上报而非自造 | §8 的人工核对 + §10 上报记录 |
| INV-002-10 | 失败也落盘：`EXIT_FAILED` 路径下两份产物**都存在** | §8 的失败用例 `test -f` 断言 |
| INV-002-11 | 无堆栈污染：`stdout` 中不出现 `Traceback` | §8 的 stdout 断言 |
| INV-002-12 | 权限闭合：除 `harmonica_eval/__main__.py` 外，无任何被 git 跟踪的文件被修改 | §8 的 `git diff --name-only` 断言 |

---

## 7 · 边界（明确不做）

- 不解码、不校验、不打开、不探测任何音频文件（格式与时长归 C2 ingest）。
- 不做 URI 解析：不展开 `~`、不转 `file://`、不做 glob、不做相对路径归一化（路径按原样字符串搬运）。
- 不做 DSP、不做对齐、不做特征计算、不做指标计算、不做重采样、不做时间归一化（归 C2 / C3）。
- 不做单位换算（换算因子恒为 1）。
- 不重新计算、不舍入、不改写、不补齐 C1 给的任何数值。
- 不判定「合格 / 不合格」，不给阈值比较结论，不生成教学结论或自然语言反馈（SPEC §1：只到数值层）。
- 不 import `cockpit`、不 import C4 的任何模块、不 import §3 清单之外的任何模块。
- 不新增命令行选项（含 `--verbose`、`--log-level`、`--seed`、`--config`、`--format`、`--force`）。
- 不读环境变量、不读配置文件、不读 stdin。
- 不打印进度、不打印指标表到 stdout、不写日志文件。
- 不生成图表、不引入绘图依赖。
- 不联网、不起子进程、不做并发。
- 不修改 `contract.py`、不新增端口、不新增错误码、不改文件名常量。
- 不做「原子写」（先写临时文件再 rename）：直接覆盖写。
- 不做 `report.md` 之外的第三份产物（不写 CSV、不写 HTML、不写摘要）。
- 若你发现「不做这个就实现不了」→ **不要做**，转 §10。

---

## 8 · 怎么验证你写对了

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval

# 0) 权限闭合：只允许本文件被改动（无被跟踪文件的其他改动）
test "$(git diff --name-only | grep -v '^harmonica_eval/__main__.py$' | wc -l | tr -d ' ')" = "0"

# 1) 占位实现必须全部消失
test "$(grep -c 'SHELL: FILE-002 待注入实现' harmonica_eval/__main__.py)" = "0"

# 2) import 闭包扫描（AST，不看注释里的 "cockpit" 字样）
python3 - <<'PY'
import ast, pathlib
ALLOWED = {"__future__", "argparse", "json", "sys", "pathlib", "typing", ".contract", ".host.app"}
src = pathlib.Path("harmonica_eval/__main__.py").read_text(encoding="utf-8")
mods = set()
for node in ast.walk(ast.parse(src)):
    if isinstance(node, ast.Import):
        mods |= {a.name.split(".")[0] for a in node.names}
    elif isinstance(node, ast.ImportFrom):
        mods.add(("." * node.level) + (node.module or "") if node.level else (node.module or "").split(".")[0])
assert mods <= ALLOWED, f"非法 import: {sorted(mods - ALLOWED)}"
assert not any(m.startswith(".cockpit") or m.startswith("cockpit") for m in mods)
print("IMPORT-CLOSURE OK:", sorted(mods))
PY

# 3) 用法错误：退出码必须是 2，且不产出产物
python3 -m harmonica_eval --reference data/in/ref.wav > /tmp/f002.out 2>/tmp/f002.err; rc=$?
test "$rc" = "2"
test "$(grep -c 'Traceback' /tmp/f002.out)" = "0"

# 4) 成功路径（自比：参考与练习取同一段音频，对齐必然有定义）
rm -rf /tmp/f002a /tmp/f002b
python3 -m harmonica_eval --reference data/in/ref.wav --practice data/in/ref.wav --out /tmp/f002a/metrics.json > /tmp/f002a.out 2>/tmp/f002a.err; rc=$?
test "$rc" = "0"
test -f /tmp/f002a/metrics.json
test -f /tmp/f002a/report.md
test "$(grep -c 'Traceback' /tmp/f002a.out)" = "0"

# 5) schema / 键序 / 数值等价断言
python3 - <<'PY'
import json, pathlib
from harmonica_eval.__main__ import run_headless
d = json.loads(pathlib.Path("/tmp/f002a/metrics.json").read_text(encoding="utf-8"))
top = list(d.keys())
assert top[:3] == ["schema_version", "inputs", "state"], top
assert top[-2:] == ["scalars", "series"], top
assert set(top) <= {"schema_version","inputs","state","error_code","error_detail","scalars","series"}, top
assert d["schema_version"] == 1
assert list(d["inputs"].keys()) == ["reference", "practice"]
for s in d["scalars"]:
    assert list(s.keys())[:4] == ["key", "label", "value", "unit"], list(s.keys())
    assert set(s.keys()) <= {"key","label","value","unit","threshold"}, list(s.keys())
    assert isinstance(s["value"], (int, float, str, bool)) or s["value"] is None
for s in d["series"]:
    assert list(s.keys()) == ["key","label","unit","timeline_basis","n_points"], list(s.keys())
    # ★ n_points 是派生量 = len(投影的 t)，不是 UiSeries 的字段
    assert isinstance(s["n_points"], int) and s["n_points"] == len(ui_series.t)
    assert s["timeline_basis"] in {"REFERENCE", "WARPED"}, s["timeline_basis"]
view = run_headless("data/in/ref.wav", "data/in/ref.wav", pathlib.Path("/tmp/f002a/metrics.json"))
got = {s["key"]: s["value"] for s in d["scalars"]}
exp = {s.key: s.value for s in view.scalars}
assert set(got) == set(exp), (sorted(set(got) ^ set(exp)))
assert all(repr(got[k]) == repr(exp[k]) for k in exp), "数值被重算或舍入"
assert [s["key"] for s in d["series"]] == [s.key for s in view.series]
print("SCHEMA+TRACEABILITY OK:", len(got), "scalars /", len(d["series"]), "series")
PY

# 6) 报告格式断言（数值陈述 + 必带轴语义 + 无判定词）
python3 - <<'PY'
import pathlib, re
t = pathlib.Path("/tmp/f002a/report.md").read_text(encoding="utf-8")
assert t.startswith("# 数值报告\n"), t[:40]
assert t.endswith("\n") and not t.endswith("\n\n")
assert "## 标量指标" in t and "## 曲线" in t
assert re.search(r"^- 状态：\S", t, re.M)
assert re.search(r"^- 参考：data/in/ref\.wav$", t, re.M)
assert re.search(r"^- 练习：data/in/ref\.wav$", t, re.M)
for line in t.splitlines():
    if line.startswith("- ") and "时间基准" in line:
        assert re.search(r"时间基准 (REFERENCE|WARPED)（[^）]+），采样点 \d+，t 轴单位：秒$", line), line
for bad in ["合格", "不合格", "达标", "优秀", "建议", "应该", "结论", "提升", "Traceback"]:
    assert bad not in t, bad
print("REPORT-FORMAT OK")
PY

# 7) 确定性：两次运行字节相同
python3 -m harmonica_eval --reference data/in/ref.wav --practice data/in/ref.wav --out /tmp/f002b/metrics.json >/dev/null 2>&1
cmp /tmp/f002a/metrics.json /tmp/f002b/metrics.json
cmp /tmp/f002a/report.md     /tmp/f002b/report.md

# 8) 失败路径：退出码 1，且两份产物仍存在并写出 error_code
rm -rf /tmp/f002f
python3 -m harmonica_eval --reference data/in/missing.wav --practice data/in/missing.wav --out /tmp/f002f/metrics.json > /tmp/f002f.out 2>/tmp/f002f.err; rc=$?
test "$rc" = "1"
test -f /tmp/f002f/metrics.json
test -f /tmp/f002f/report.md
test "$(grep -c 'Traceback' /tmp/f002f.out)" = "0"
python3 - <<'PY'
import json, pathlib
d = json.loads(pathlib.Path("/tmp/f002f/metrics.json").read_text(encoding="utf-8"))
assert isinstance(d.get("error_code"), str) and d["error_code"] != "", d.get("error_code")
assert d["error_code"] in pathlib.Path("/tmp/f002f/report.md").read_text(encoding="utf-8")
print("FAILURE-PATH OK:", d["error_code"])
PY

# 9) ★ 不变量 F：阻断 cockpit 后仍须跑通（C4 缺席）
python3 - <<'PY'
import importlib.abc, pathlib, sys
class BlockCockpit(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "cockpit" or name.startswith("cockpit."):
            raise ImportError("cockpit 已按不变量 F 被阻断")
        return None
sys.meta_path.insert(0, BlockCockpit())
sys.argv = ["harmonica_eval", "--reference", "data/in/ref.wav",
            "--practice", "data/in/ref.wav", "--out", "/tmp/f002a/metrics.json"]
import harmonica_eval.__main__ as m
assert m.main(sys.argv[1:]) == 0
assert "cockpit" not in sys.modules
assert all(not k.startswith("cockpit") for k in sys.modules)
print("INVARIANT-F OK: C4 缺席下无头链路跑通")
PY

# 10) 单位换算因子恒等
python3 -c "import harmonica_eval.__main__ as m; assert m._UNIT_CONVERSION_FACTOR == 1"
```

**验收判据**（可机械判定，全部为 assert）：

- [ ] 步骤 0：`git diff --name-only` 无本文件之外的被跟踪文件（INV-002-12）。
- [ ] 步骤 1：占位 `SHELL: FILE-002 待注入实现` 出现次数为 0。
- [ ] 步骤 2：import 集合 ⊆ `{__future__, argparse, json, sys, pathlib, typing, .contract, .host.app}` 且不含 `cockpit`（INV-002-1，★ 本版已加入 `.host.app`）。
- [ ] 步骤 3：缺参数时退出码 `== 2`，stdout 无 `Traceback`。
- [ ] 步骤 4：自比运行时退出码 `== 0`，`metrics.json` 与 `report.md` 都存在。
- [ ] 步骤 5：顶层键序、元素键序、`schema_version == 1`、`timeline_basis` 取值、`n_points` 为 `int` 全部成立；产物与 `run_headless` 视图的 `key` 集合相等、`value` 的 `repr` 逐位相等（INV-002-3）。
- [ ] 步骤 6：报告以 `# 数值报告\n` 开头、以单个 `\n` 结尾；参考 / 练习两行字符串完全相等；每条曲线行匹配 `时间基准 (REFERENCE|WARPED)（…），采样点 \d+，t 轴单位：秒`；八个禁用词一个都不出现（INV-002-4）。
- [ ] 步骤 7：两次运行的 `metrics.json` 与 `report.md` 分别 `cmp` 通过（INV-002-7）。
- [ ] 步骤 8：缺输入时退出码 `== 1`，两份产物都存在，`error_code` 是非空 `str` 且出现在 `report.md` 中（INV-002-6 / INV-002-10）。
- [ ] 步骤 9：`cockpit` 被阻断导入时 `main(...) == 0` 且 `sys.modules` 中无 `cockpit`（INV-002-2）。
- [ ] 步骤 10：`_UNIT_CONVERSION_FACTOR == 1`（INV-002-5）。

若任一步骤的断言失败原因指向 `contract` 的字段名或符号缺失，**不得改断言迁就实现**，转 §10。

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] 产物路径：`harmonica_eval/__main__.py`（唯一被修改的文件）。
- [ ] §8 全部 10 个步骤的**原始命令 + 原始输出**（含每步的退出码），以及全部 assert 的通过输出。
- [ ] 静态证据：AST import 闭包扫描的打印结果 `IMPORT-CLOSURE OK: [...]`。
- [ ] 不变量 F 证据：步骤 9 的 `INVARIANT-F OK: C4 缺席下无头链路跑通` 输出，且 `sys.modules` 中无 `cockpit` 前缀模块。
- [ ] 黄金向量对比证据：同一次运行的 `UiView` 与 `metrics.json` 的逐字段等价断言输出（`SCHEMA+TRACEABILITY OK: <N> scalars / <M> series`），且 `repr` 逐位相等。
- [ ] 确定性证据：两次运行的 `cmp` 静默通过（退出码 0）。
- [ ] 失败路径证据：`error_code` 的值与它在两份产物中的出现位置。
- [ ] 落盘样例：一次成功运行的 `metrics.json` 全文与 `report.md` 全文（产物落在 `data/out/`，该目录不进 git）。
- [ ] 权限证据：`git diff --name-only` 的输出（只含本文件）。
- [ ] 若期间触发过 §10，附上完整 `GATE CHALLENGE` 文本与最终处置结论。

---

## 10 · ★ 何时必须停止并上报（§22 硬失败对策）

**以下情况必须停止，提交 `MOLD BREAK`，不得自行设计：**

1. 你发现本文件**需要做上层设计**才能实现（例如：需要决定一个新阈值 / 新口径 / 新端口 / 新错误码 / 新命令行选项 / 新的 `metrics.json` 键）。
2. 本文件与任何上游工件**冲突**（例如：`contract.UiView` 的字段名与 §4.3 引用的名字不一致；`timeline_basis` 出现 `REFERENCE` / `WARPED` 之外的第三个取值；`state` 为 `FAILED` 而 `error_code` 为空）。
3. 你需要的依赖**不在 §3 清单里**（例如：`contract` 未导出驱动 C1 会话所需的符号，导致 `run_headless` 的第 1、2、3 步无法完成）。
4. §4 的行为规格**不足以确定唯一实现**（例如：`UiSeries` 不暴露点数元信息，而 §5 已禁止用 `len(values)` 替代）。
5. 你认为 §4 的规格本身**是错的**。

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
- 自行在代码里加一个「合理的」默认值把冲突掩盖过去（含自造 `error_code`、把缺失的 `timeline_basis` 写成 `"UNKNOWN"`、把 `NaN` 写成 `null`）。
- 静默缩小范围（「这个分支我先不实现」）。
- 改 §8 的断言或改 §4 的口径来迁就实现。

---

## 附：本文件的冻结常量速查

| 常量 | 值 | 来源 |
| --- | --- | --- |
| `DEFAULT_OUT_DIR` | `"data/out"` | `harmonica_eval/__main__.py:49` |
| `DEFAULT_METRICS_FILENAME` | `"metrics.json"` | `harmonica_eval/__main__.py:52` |
| `REPORT_FILENAME` | `"report.md"` | `harmonica_eval/__main__.py:55` |
| `EXIT_OK` | `0` | `harmonica_eval/__main__.py:58` |
| `EXIT_FAILED` | `1` | `harmonica_eval/__main__.py:61` |
| `EXIT_USAGE` | `2` | `harmonica_eval/__main__.py:64` |
| `_JSON_SCHEMA_VERSION` | `1` | 本文件 §4.0 |
| `_JSON_INDENT` | `2` | 本文件 §4.0 |
| `_JSON_SEPARATORS` | `(",", ": ")` | 本文件 §4.0 |
| `_JSON_ENSURE_ASCII` | `False` | 本文件 §4.0 |
| `_JSON_ALLOW_NAN` | `False` | 本文件 §4.0 |
| `_JSON_SORT_KEYS` | `False` | 本文件 §4.0 |
| `_TEXT_ENCODING` | `"utf-8"` | 本文件 §4.0 |
| `_TEXT_NEWLINE` | `"\n"` | 本文件 §4.0 |
| `_REPORT_TITLE` | `"# 数值报告"` | 本文件 §4.0 |
| `_REPORT_EMPTY_ITEM` | `"- （无）"` | 本文件 §4.0 |
| `_BASIS_GLOSS["REFERENCE"]` | `"保留源时间，抢拍拖拍可见"` | 本文件 §4.0 |
| `_BASIS_GLOSS["WARPED"]` | `"时间归一化，抢拍拖拍已被抹掉"` | 本文件 §4.0 |
| `_UNIT_CONVERSION_FACTOR` | `1` | 本文件 §4.0 |
| `_SECONDS_UNIT_LABEL` | `"秒"` | 本文件 §4.0 |
