# FILE-105 — harmonica_eval/core/api.py

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/core/api.py`
> 生成依据：`SPEC.md@v2.1` · `contract.py` · `profile.py@CORE_PROFILE_V0.1` · `COMPONENTS.md`
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-105 |
| 所属组件 | COMP-C2 Audio Core（`harmonica_eval/core/` 包；本文件是该包的门面层） |
| 层级 | L3（symbol / implementation） |
| 上游 | 唯一调用方 = COMP-C1 Framework/Host。调用面 = `contract.HostContract` 的 7 个操作：create_session / set_reference / set_practice / build_surface / status / acquire_surface / destroy_session；输入即这 7 个调用的参数（`profile_version: str`、`session_id: str`、`uri: str`）。C3 **不直接调用**本文件——它只接触 acquire_surface 返回的 `Surface`（经 C1 转交，实现 `AlgorithmDataContract`）。 |
| 下游 | 我调用：`harmonica_eval/contract.py`（仅 6 个名字：HostContract、SessionState、ContractViolation、CoreBuildError、ErrorCode、HarmonicaError）；`harmonica_eval/core/surface.py` 的 `Surface`（build_surface 产出、acquire_surface 返回、destroy_session 释放）；build_surface 期间依次驱动 core 包内四阶段模块 `.ingest` → `.align` → `.features` → `.surface`。我给谁输出：`HostCore` 实例给 C1（会话管理器，全系统唯一会话状态持有者）；`Surface` 给 C1、由 C1 转交 C3。 |
| 同层邻居 | `harmonica_eval/core/` 包内的阶段模块：`ingest.py`（解码/标准化）、`align.py`（时间映射）、`features.py`（端口预生成）、`surface.py`（数据面）。`contract.py` 属 COMP-CONTRACT，是跨组件共享词汇层，不是同层邻居。 |

★ **定位（机械分析已证实）**：`core/api.py` 是内核里**唯一被外部 import 的文件**——即「唯一对外门面」。C1/C3/C4 对本内核的全部触点收敛到 `HostCore` 这一个类的 7 个方法；`ingest.py` / `align.py` / `features.py` / `surface.py` 一律只被 api.py（或彼此）import，外部文件不得触达。因此本文件的方法集合就是内核对外能力的**全部**：出现第 8 个方法 = 内核获得新职责 = 必须走 MOLD BREAK，不得就地添加。`FORBIDDEN_OPERATIONS` 的十个名字（见 contract.py）是对这条边界的机械检查点。

**你的权限**：只实现本文件。不得修改任何其他文件，不得修改契约，
不得新增端口，不得新增依赖。

---

## 2 · 这个文件为什么存在

**追溯到 Product Intent / Requirement**：SPEC.md@v2.1 §4.2（CONTRACT-HOST-v1，C1→C2 唯一对话面）与 §5.5（两轴分离）；COMPONENTS.md@v2 §4.1（COMP-C2 Audio Core 的对外接口）；contract.py 的 `HostContract` Protocol 是其可 import 的实体化。**Product Intent 原文**：「双音频对比 → 客观数值指标」。要做到这一点，必须先有一个组件把两段任意格式的音频变成封闭端口集的不可变数据面——但这个组件对 C1 暴露的面必须极小，否则 C1 会开始依赖 C2 内部（阶段名、算法、端口结构），四个组件的边界即告瓦解。本文件就是这个极小面的**唯一实体**。

**删掉它会坏掉什么**：逐条可验证——

1. **C1 无处落地**：`HostContract` 是 Protocol（纯声明，零行为）。删掉 api.py，`create_session` 等 7 个操作没有任何实现，C1 的编排（UiCommand.BUILD_SURFACE / RUN_ALGORITHMS 的执行体）在 import 阶段即 `ImportError`/`TypeError`，整个流水线 0 行可运行。
2. **会话状态机消失**：CREATED → INPUT_READY → BUILDING → DATA_READY（任一 → FAILED，终态 → CLOSED）的推进逻辑全部住在本文件的 `HostCore` 里。删掉它，C3 就能在任何时刻要求任何数据——「算法的唯一合法触发点是 DATA_READY」这条 SPEC 硬规则失去执行者。
3. **内核边界失守**：本文件是内核唯一对外门面（机械分析已证实）。删掉它，外部要直接 import ingest/align/features/surface，四个阶段模块被迫各自处理 session_id、状态检查、错误归一化——要么各写一份不一致的状态机，要么把状态机塞回 contract.py（违反其 MUST NOT「任何计算」）。
4. **「Core 不知道算法的存在」不可验证**：FORBIDDEN_OPERATIONS 的机械断言挂在本文件的方法集合上；没有这个单一类，就没有可断言的对象，泄漏只能靠人眼审。

**结论**：它存在，因为「极小的对话面」和「唯一的会话状态持有者」必须有一个物理落点；这个落点只能是内核包里唯一被外部 import 的那一个文件。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：
- 标准库（穷举，恰 4 个模块）：
  - `__future__`（仅 `annotations`，文件头已用）
  - `typing`（仅 `Mapping`，`INTERNAL_STAGES` 的注解用）
  - `uuid`（仅 `uuid.uuid4().hex`，session_id 生成）
  - `dataclasses`（仅 `dataclass` / `field`，模块私有会话记录 `_Session`）
- 第三方：**无。一个都不允许。**
- 本包内（穷举，恰 6 条 import 的来源，即 6 个模块）：
  - `harmonica_eval.contract`：且仅这 6 个名字 —— `HostContract`, `SessionState`, `ContractViolation`, `CoreBuildError`, `ErrorCode`, `HarmonicaError`

    ★★ **更正（白名单与 §4.5 第 6 步自相矛盾）：上一版这里写「且仅这 5 个名字」，
    名单里没有 `HarmonicaError` —— 但 §4.5 第 6 步逐字用它做分流判据。** ★★

    原写「且仅这 **5** 个名字 —— `HostContract`, `SessionState`,
    `ContractViolation`, `CoreBuildError`, `ErrorCode`」，**5 个名字**。
    实测 `contract.py` 确有 `class HarmonicaError(Exception)`，且
    `ContractViolation` 与 `CoreBuildError` 都是它的子类。
    而 §4.5 第 6 步写的是 `except HarmonicaError as err:` —— 一个不在名单里的名字
    被直接使用。按原名单 import 必然 `NameError`；更糟的是本节末尾又写
    「凡未列入名单的模块一律禁止」，实现者会判定第 6 步违规而 GATE CHALLENGE，
    卡死在这一步。

    **本版冻结**：名单改为 **6 个名字**，补入 `HarmonicaError`。
    理由：`HarmonicaError` 是 §4.5 失败归一化的**基类判据** —— 不用它就无法区分
    「带错误码的已知失败」（第 6 步，逐字保留 `err.code`）与「未知崩溃」
    （第 7 步，`code = ErrorCode.CORE_BUILD_FAILED`）这两条不同路径。

    ★ **计数同步**：本节名单已改为 6 个名字；文件内另一处引用该计数的位置是
    顶部「下游」行（「仅 5 个名字：…」），已一并同步为 6 个名字、同序列出
    `HarmonicaError`。全文再无其它处引用这个计数。**
  - `harmonica_eval.profile`：且仅 `AUDIO` —— 只取采样率数值 `AUDIO.sample_rate`
    （本文件写 `sample_rate = int(AUDIO.sample_rate)`，见 §4.5 阶段 1 的 FINDING-7 更正）。
    **不**读 `PROFILE_VERSION`、**不**做版本比对、**不**解释 `profile_version`、
    **不**读 `AUDIO.max_duration_sec` / `ALIGN.hop_length` / `MATERIALIZE.rms_hop_length`。
    版本守卫仍在 `create_session`；本文件只读一个数值常量，不做 profile 解析。
  - `harmonica_eval.core.surface`：公开仅 `Surface`；另允许调用模块级 `build_surface` 入口（阶段 4 必需）。资源销毁时唯一允许调用的下划线成员是 `Surface._invalidate()`，它是内部生命周期钩子，不进入公开操作面。
  - `harmonica_eval.core.ingest`、`harmonica_eval.core.align`、`harmonica_eval.core.features`：仅作为 build_surface 的阶段入口调用（入口签名以各自 BUILD-INSTRUCTION 冻结的规格为准，本文件不内联其任何逻辑）

**禁止 import**：
- 标准库具名禁入：`os`, `sys`, `pathlib`, `io`, `logging`, `threading`, `asyncio`, `subprocess`, `json`, `pickle`, `random`, `time`, `hashlib`（content_hash 的计算属 surface.py，口径冻结在 `contract.PortDescriptor.content_hash`）, `re`, `math`
- 第三方具名禁入：`numpy`, `numpy.typing`, `scipy`, `soundfile`, `librosa`, `pandas`, `torch`（本文件不得接触音频字节与数值计算）
- 本包具名禁入：`harmonica_eval.host`、`harmonica_eval.algorithms`、`harmonica_eval.cockpit`（门面不得反向依赖调用方或算法）。★ `harmonica_eval.profile` **不在**本禁入名单内：它已改列入「可以 import」名单（仅 `AUDIO`）。原括注「profile 解析责任在阶段模块」不再成立 —— 阶段 4 的入口由**本文件**调用，`sample_rate` 实参必须由本文件给出（见 §4.5 阶段 1 的 FINDING-7 更正）。
    ★★ **更正（“本包具名禁入”与资源生命周期必需入口自相矛盾）**：core 包内
    ingest/align/features/surface 的其它任何 `_` 私有符号仍禁止；唯一例外是
    `harmonica_eval.core.surface.Surface._invalidate()` —— `destroy_session`
    必须调用它使已发出的旧句柄失效、立即解除其对端口数组的引用。
    该例外**不**放宽 `harmonica_eval.host` / `harmonica_eval.algorithms` /
    `harmonica_eval.cockpit` 或其它 core 私有成员的禁令，也不增加任何公开操作。
- 封闭规则：**凡未列入「可以 import」名单的模块一律禁止**。实现中出现的每一条 import 语句必须逐字落在名单内；发现需要名单之外的东西（尤其需要算法或特征计算）即为宪章 §5.9 违规，停止并 GATE CHALLENGE，不得自行扩单。

★ 本清单必须**穷举**，不许出现「等」「之类」。

★★ **更正（「本包内」计数与条目不符 + profile 的禁入/允许自相矛盾）：上一版「本包内」写「恰 6 条 import 的来源」，实际只列了 5 个模块 —— `harmonica_eval.contract`、`harmonica_eval.core.surface`、`harmonica_eval.core.ingest`、`harmonica_eval.core.align`、`harmonica_eval.core.features`；且同一节把 `harmonica_eval.profile` 列入「本包具名禁入」（理由「profile 解析责任在阶段模块」），与本文件 §4.5 阶段 1 的 FINDING-7 更正（已规定本文件**允许** `from ..profile import AUDIO` 并写 `sample_rate = int(AUDIO.sample_rate)`）**直接冲突**。** ★★

原写两处：
- 计数行：「本包内（穷举，恰 **6** 条 import 的来源）：」—— 数字 6 与并列的 5 个条目对不上。
- 禁入行：「本包具名禁入：`harmonica_eval.host`、`harmonica_eval.algorithms`、`harmonica_eval.cockpit`（…）、**`harmonica_eval.profile`（profile 解析责任在阶段模块）**、core 包内 … 任何 `_` 私有符号」。

**为什么错**：实测 `ingest(uri) -> npt.NDArray` 只返回 PCM、**不返回** `AudioFormat`（FINDING-7）；而阶段 4 的入口 `build_surface(reference, practice, sample_rate, warp_path)` 需要 `int sample_rate`，且该入口是**本文件**调用的，实参必须由本文件给出。若继续禁止 import `profile`，本文件无从取得该数值 —— 禁入行与 FINDING-7 更正不可能同时成立。原括注「profile 解析责任在阶段模块」也不成立：阶段模块各自 import profile 是它们的事，解决不了门面这一环。

**本版冻结**：
- 「本包内」名单**加入** `harmonica_eval.profile`，且仅取 `AUDIO`（只读采样率数值 `AUDIO.sample_rate`）；**不**读 `PROFILE_VERSION`、**不**做版本比对、**不**解释 `profile_version`、**不**读 `AUDIO.max_duration_sec` / `ALIGN.hop_length` / `MATERIALIZE.rms_hop_length`。版本守卫仍在 `create_session`，与本文件「`profile_version` 是不透明字符串」的既有口径不矛盾。
- 计数改为 **6**：与加入 profile 后**实际列出的 6 个来源模块**逐一对应。
- 「本包具名禁入」**删除** `harmonica_eval.profile` 及其原括注；**保留** `harmonica_eval.host` / `harmonica_eval.algorithms` / `harmonica_eval.cockpit` 与 core 包内 `_` 私有符号。

★ **同步范围**：§4.0 屏障表（`harmonica_eval/profile.py` 行）、§4.2 `create_session` 输入行、§4.5 阶段 4 实参（原文「不由本文件另行假设或读取 `profile`」）、§7「不解析 profile」条目中原有的「不 import `harmonica_eval.profile`」式措辞已按本处口径一并改为「仅可 import `AUDIO`（只取采样率数值），不做 profile 解析」。§4.5 阶段 1 的两处 `★★` 更正块与 §6 INV-105-12b 说明块中引述旧口径的文字属**历史记录**，按「不改历史更正」保留原样，其结论与本处不冲突。**

---

## 4 · 你要实现什么（行为规格）

### 4.0 门面屏障总则（★ 本份额外必写项）

`HostCore` 是内核里**唯一被外部 import 的类**，它把内核内部 **5 个模块**全部挡在身后。下表逐行给出每个模块被挡住的**具体内容**与**屏障形式**；实现者写出的 api.py 必须逐条满足，缺一条即该模块的细节开始外泄。

| 被屏蔽的内部模块 | 屏障挡住的全部内容 | 屏障形式 |
| --- | --- | --- |
| `harmonica_eval/core/ingest.py` | URI 打开、容器解码、多声道下混为 mono、重采样、`InputFormat`/`AudioFormat` 的构造、`INPUT_UNREADABLE` / `INPUT_TOO_SHORT` / `INPUT_SILENT` / `INPUT_TOO_LONG` 四个错误码的判定与抛点 | 只在 `build_surface` 内部的第 1 阶段被调用；其返回值只作为局部变量传给第 2 阶段，绝不写入任何 C1 可达的对象；其异常被归一化为 `CoreBuildError` |
| `harmonica_eval/core/align.py` | 时间映射算法、`TimelineBasis.REFERENCE`（源时间网格）与 `TimelineBasis.WARPED`（归一化网格）两条网格的构造、warp 路径点、`ALIGNMENT_UNRECOVERABLE` 的判定 | 只在 `build_surface` 内部的第 2 阶段被调用；入口参数与返回值只在本文件方法体内存活；异常归一化为 `CoreBuildError` |
| `harmonica_eval/core/features.py` | 端口清单与端口 id、每个端口的 `shape` / `element_type` / `hop_length` / `units`、逐端口物化的顺序与缓冲分配、`CORE_REQUIRED_PORTS` 的落实 | 只在 `build_surface` 内部的第 3 阶段被调用；C1 永远拿不到 `PortDescriptor`（`PortDescriptor` 只在 `Surface.manifest()` 里出现，而 `manifest()` 属 surface.py） |
| `harmonica_eval/core/surface.py` | `Surface` 的装配与 Seal、`content_hash` 的字节级计算、只读视图（`writeable is False`）的落实、句柄失效的判定 | 唯一外泄物是 `acquire_surface` 返回的那个 `Surface` 实例，且只在 `state is SessionState.DATA_READY` 之后才可能返回 |
| `harmonica_eval/profile.py` | 版本字符串的解析与合法性判定、profile 常量（`AUDIO.max_duration_sec` / `ALIGN.hop_length` / `MATERIALIZE.rms_hop_length`）的读取、端口清单的来源 | api.py 只允许 `from ..profile import AUDIO` 并读 `AUDIO.sample_rate` 一个数值（FINDING-7）；**不**读 `PROFILE_VERSION`、**不**做版本比对；`profile_version` 在本文件里是**不透明字符串**，只做存取与透传 |

C1 对本内核可观察到的全部事实**恰好 5 条**，实现者不得让第 6 条存在：

1. `create_session` 返回的 `session_id`（恰 32 位小写十六进制字符）
2. `status` 返回的 `SessionState` 六个值之一
3. 调用成功（返回 `None` / `str` / `SessionState`）或失败（`ContractViolation` 或 `CoreBuildError`，各带 `ErrorCode`）
4. `acquire_surface` 返回的 `Surface` 实例本身（其 `manifest()` / `read()` 的行为由 surface.py 的规格冻结，不属于本文件）
5. `destroy_session` 之后同一 `session_id` 的 `status` 为 `SessionState.CLOSED`

**禁止外泄清单（逐条机械可验）**：阶段名 `INGESTING` / `ALIGNING` / `MATERIALIZING` / `SEALING`、端口 id、数组形状、`hop_length`、缓冲对象、`content_hash` 字符串、字节数、耗时、采样率、异常堆栈中的阶段内部类型。判定方法：这 12 类信息在本文件里只以局部变量形式存在，绝不作为任何返回值、任何 `_Session` 字段、任何返回对象的属性的取值来源。

### 4.1 模块级私有记录 `_Session`（模块私有，名字以 `_` 开头）

`@dataclass` 修饰，**恰好 6 个字段**，无默认值以外的行为、无方法：

| 字段 | 类型 | 初值 | 语义与取值域 |
| --- | --- | --- | --- |
| `session_id` | `str` | `uuid.uuid4().hex` | 恰 32 字符，字符集 `[0-9a-f]`；同时是 `HostCore._sessions` 的键 |
| `profile_version` | `str` | `create_session` 的入参，逐字保存 | 非空；本文件不解析其内容 |
| `state` | `SessionState` | `SessionState.CREATED` | 取值域 = `SessionState` 的 6 个成员，不含第六个以外的任何值 |
| `reference_uri` | `str \| None` | `None` | 非空字符串；逐字保存，不做规范化 |
| `practice_uri` | `str \| None` | `None` | 同 `reference_uri` |
| `surface` | `Surface \| None` | `None` | **只在 Seal 成功后被写入**；`destroy_session` 后回到 `None` |

宿主：`HostCore.__init__(self) -> None` 建立 `self._sessions: dict[str, _Session] = {}`。`__init__` 是 dunder，不计入 7 个公开操作。

**辅助函数规则**：实现需要内部辅助函数时，其名字**必须**以 `_` 开头（例：`_require(session_id)`）。`dir(HostCore)` 去掉下划线开头的名字后必须恰好等于 §4.9 的 7 个名字。

### 4.2 `create_session(profile_version: str) -> str`

- **输入**：`profile_version: str`。语义 = profile 版本标识（本仓当前取值 `"CORE_PROFILE_V0.1"`）。取值域 = 任意非空 `str`。单位：无。本文件对该字符串**只做两件事**：判非空、存入 `_Session.profile_version`；不解析、不比对本仓已登记版本。（★ 本方法**不**读 `profile` 常量；`from ..profile import AUDIO` 只用于 `build_surface` 阶段 1 取 `sample_rate`，见 §3 与 FINDING-7。）
- **输出**：`str`，恰 **32** 个字符，字符集 `[0-9a-f]`，由 `uuid.uuid4().hex` 产生；返回值与 `_Session.session_id` 逐字符相同。
- **算法口径**（逐字照做，无分支余地）：
  1. `if not isinstance(profile_version, str) or profile_version == "": raise ContractViolation(code=ErrorCode.INTERNAL_ERROR, detail="profile_version 必须是非空 str", component="COMP-C2")`
  2. `sid = uuid.uuid4().hex`
  3. `self._sessions[sid] = _Session(session_id=sid, profile_version=profile_version, state=SessionState.CREATED, reference_uri=None, practice_uri=None, surface=None)`
  4. `return sid`
- **边界**：空输入（`""`）→ 抛 `ContractViolation`，**不建会话**。单元素（长度 1 的字符串，如 `"v"`）→ 合法，照常建会话并逐字保存。`NaN` → 不适用：入参类型是 `str`，传 `float('nan')` 归入「非 `str`」分支，同样抛 `ContractViolation`。
- **不变量**：本调用不读写任何已存在的 `_Session`；新会话的 `state` 恒为 `CREATED`；`_sessions` 的键恒等于对应 `_Session.session_id`。同一进程内连续调用两次必得两个不同的 `session_id`（`uuid4` 口径）。

### 4.3 `set_reference(session_id: str, uri: str) -> None`

- **输入**：`session_id: str`，取值域 = `self._sessions` 的键集合。`uri: str`，取值域 = 任意非空 `str`；语义 = 音频资产位置（绝对路径或 URI）。**本文件不打开文件、不解码、不做路径规范化、不检查存在性**——这些全部属于 ingest.py。
- **输出**：`None`。
- **算法口径**（逐字照做）：
  1. `s = self._sessions.get(session_id)`；`s is None` → `raise ContractViolation(code=ErrorCode.INTERNAL_ERROR, detail="未知 session_id", session_id=session_id, component="COMP-C2")`
  2. `if not isinstance(uri, str) or uri == "": raise ContractViolation(...)`（同一码与组件；`detail` 写明「uri 必须是非空 str」）
  3. `if s.state not in (SessionState.CREATED, SessionState.INPUT_READY): raise ContractViolation(...)`（`detail` 写明当前状态名；本次调用**零副作用**）
  4. `s.reference_uri = uri`（覆盖写，逐字保存）
  5. `if s.reference_uri is not None and s.practice_uri is not None: s.state = SessionState.INPUT_READY`
  6. `return None`
- **边界**：空输入（`session_id == ""` 或 `uri == ""`）→ 抛 `ContractViolation`。单元素（`uri` 长度 1）→ 合法，逐字保存。`NaN` → 不适用（两个入参类型都是 `str`，传数值型归入类型错误分支并抛）。**重复登记**（同一会话第二次调 `set_reference`）：合法，覆盖旧值；在 `INPUT_READY` 下覆盖后状态**仍是** `INPUT_READY`（不倒退、不重算）。
- **不变量**：本调用不触碰 `s.surface`（恒不变）、不触碰 `s.profile_version`、不触发解码或计算（`build_surface` 之外任何方法都不得调用 ingest/align/features/surface）；状态转移只可能是 `CREATED → INPUT_READY` 或「不变」，绝不出现 `INPUT_READY → CREATED`。

### 4.4 `set_practice(session_id: str, uri: str) -> None`

与 §4.3 **逐条同构**，仅把第 4 步替换为 `s.practice_uri = uri`，仅把第 5 步的判据替换为 `s.reference_uri is not None and s.practice_uri is not None`。输入 / 输出 / 边界 / 不变量与 §4.3 完全相同（含 `ErrorCode.INTERNAL_ERROR` 这一码与 `component="COMP-C2"`）。

### 4.5 `build_surface(session_id: str) -> None`

**输入**：`session_id: str`，取值域 = `self._sessions` 的键集合。**本方法不接收任何算法信息**（无算法 id、无端口 id、无特征名、无参数表）——签名已封死在 §4.9。

**输出**：`None`（成功时）。成功后 `state is SessionState.DATA_READY`，且 `_Session.surface is not None`。

**算法口径**（★ 编排链，逐字照做；顺序不可重排、不可跳过、不可并行）：

1. `s = self._sessions.get(session_id)`；`s is None` → 抛 `ContractViolation`（未知会话）。
2. `if s.state is not SessionState.INPUT_READY: raise ContractViolation(...)`。本次调用**零副作用**：`s.state` 不变、`s.surface` 不变（`DATA_READY` 下重复调用**不得**销毁已发布的数据面）。
3. `s.state = SessionState.BUILDING`。
4. `try:` 块内按**固定顺序**驱动四阶段，每阶段的返回值只以局部变量在方法体内传递，不写入 `_Session`：
   - 阶段 1 `INGEST`：**分别**调用 `harmonica_eval.core.ingest.ingest(uri)` **两次**
     —— 一次 `s.reference_uri`、一次 `s.practice_uri`；产出 = 两路规范化后的
     mono/`float32` PCM 与其 `AudioFormat`。

     ★★ **更正（P1 审查 F6）：上一版的实参个数是错的。** ★★

     原写「实参含 `(s.reference_uri, s.practice_uri, s.profile_version)`」——
     **三个参数**。实测 `core.ingest.ingest` 的签名是 **`ingest(uri)`，只有一个参数**，
     且 `FILE-101-v1.md:256` 明确标注它是「**唯一对外入口**」。
     按原规格实现必然 `TypeError`。

     **本版冻结**：
     - 调用形态 = `ingest(uri)`，**逐路**调用，共两次。
     - `profile_version` **不是** `ingest` 的参数。它属于**会话**身份
       （`create_session(profile_version)`），在阶段 1 里只做一次断言：
       ★★ **本版再更正（第三轮盲审 A 的 probe 18）：上一版这里写
       `assert s.profile_version == profile.PROFILE_VERSION` —— 但 §3 的
       import 白名单里**没有 `harmonica_eval.profile`**，且本节末尾又明写
       「不 import `harmonica_eval.profile`，不校验 `profile_version`
       是否为已知版本」。**同一份文件里既禁止 import 又要求用它的常量。** ★★

       **本版冻结**：阶段 1 **不**做任何版本比对。
       `profile_version` 是**不透明字符串** —— 由调用方（C1 的会话）传入、
       由本文件原样转交给 `create_session`，**本文件不解释它**。
       版本是否受支持由 `create_session` 自己判定（那是 C1 的职责）。
       理由：本文件是 C2 的门面，**不是** profile 的守卫；
       把版本白名单塞进 C2 会让「支持哪些 profile」分散到两处。
     - 两次调用的**顺序冻结**：先 reference、后 practice。
     - 采样率不由本文件假设：`ingest` 返回的 PCM 已按 `profile.AUDIO.sample_rate`
       规范化（SPEC §7.4 授权的重采样点唯一地在这里）。

       ★★ **更正（第三轮盲审 A 的 FINDING-7）：上一版到此为止，`sample_rate`
       从未被绑定成变量，而阶段 4 需要它。** ★★

       **实测**：`ingest(uri) -> npt.NDArray` —— 只返回 PCM，
       **不返回** `AudioFormat`。所以「产出 = PCM 与其 `AudioFormat`」这句是错的。

       **`sample_rate` 的冻结来源**：本文件**允许**从 `harmonica_eval.profile`
       取 `AUDIO`（见 §3 白名单已加入 `profile.AUDIO`），写死为：

       ```python
       from ..profile import AUDIO
       sample_rate = int(AUDIO.sample_rate)   # 44100
       ```

       **为什么允许**（而不是让阶段模块自己取）：阶段 4 的入口
       `build_surface(reference, practice, sample_rate, warp_path)` 是**本文件**
       调用的，实参必须由本文件给出；阶段模块各自 import profile 是它们的事，
       不解决门面这一环。

       **这不违反"不做版本守卫"**：本文件只读**数值常量** `AUDIO.sample_rate`，
       不读 `PROFILE_VERSION`、不比对、不解释 —— 版本守卫仍在 `create_session`。
   - 阶段 2 `ALIGN`：调用 `harmonica_eval.core.align` 的入口，实参 = 阶段 1 的产出；
     产出 = **warp 路径点**（`warp_path`，一个 `(n_ref_frames, 2)` 的 `int32` 数组）。

     ★★ **更正（负责人裁定 `pcm.*` 归属后同步）：上一版这里说 ALIGN 产出
     「两份对齐 PCM」—— 与实测不符，也与裁定冲突。** ★★

     实测：`core.align.align(reference, practice)` 的返回注解是
     `npt.NDArray`，**只返回 `warp_path`**，不产任何 PCM。

     裁定后 `pcm.*` 的归属是：
     - `pcm.mapped.reference` / `pcm.mapped.practice` —— 阶段 4（`core.surface`）
       **纯转发**阶段 1 的规范化 PCM（零计算）；
     - `pcm.warped.practice` —— 阶段 4 按 `warp_path` 做**索引重排**。

     ⇒ 阶段 2 只负责**算对齐**；PCM 的登记与装配**全部**在阶段 4。
     本阶段**不得**产出任何 PCM（否则同一份数据有两个生产者）。
   - 阶段 3 `MATERIALIZING`：★★ **本版更正（第三轮盲审 A 的 FINDING-4）：阶段 3 是语义分组，不是一次独立调用。** ★★

     **上一版写「调用 `core.features` 的入口，实参 = 阶段 2 的产出；产出 =
     profile 决定的全部端口缓冲」—— 那不可实现，已删除。** 实测两条：

     | 事实 | 实测 |
     | --- | --- |
     | `core.features` **没有**聚合入口 | 公开名只有 `materialize_pitch` / `materialize_rms` / `materialize_chroma` / `materialize_notes` 与两个阈值常量 |
     | 四个函数**没有一个**接受 `warp_path` | 签名分别是 `(samples, sample_rate)` / `(samples)` / `(samples, sample_rate)` / `(pitch, rms, sample_rate)` |

     即「实参 = 阶段 2 的产出（`warp_path`）」对不上任何入口。

     **冻结口径**：阶段 3 的逻辑**发生在阶段 4 内部** ——
     `build_surface` 调 `generate_all_ports(reference, practice, sample_rate, warp_path)`，
     由它按 §4.4 的派发表逐端口调用 `core.features` 的四个函数。
     因此：

     - 阶段 3 **不产生**任何独立返回值，**不是**本文件的一次调用；
     - 本文件在阶段 3 **不持有**任何端口缓冲（缓冲是 `generate_all_ports` 的局部量）；
     - `INTERNAL_STAGES` 里的 `"MATERIALIZING"` **保留**（它仍是状态的语义分组，
       只是不对应本文件的某一行调用）。

     **阶段 4 的实参**：`(阶段 1 的两路 PCM, sample_rate, 阶段 2 的 warp_path)`。
     `sample_rate` 由本文件从 `profile.AUDIO.sample_rate` 取得（`int(...)`，见上文
     FINDING-7 冻结）；`ingest` 返回的 PCM 已按同一常量规范化，二者同源。
   - 阶段 4 `SURFACE`：调用 `harmonica_eval.core.surface` 的入口装配并按 surface.py 冻结的口径 Seal，使 `SurfaceManifest.sealed is True`；每个端口的 `content_hash` 按 `contract.PortDescriptor.content_hash` 冻结的字节级口径计算（`CONTENT_HASH_MAGIC` + `port_id` + `element_type` + 小端 `<i8` 的 `shape` + C 序 `data.tobytes()`，sha256 十六进制）。
   - 四个阶段的**入口签名以各自 BUILD-INSTRUCTION 冻结的规格为准**；本文件不内联四阶段的任何逻辑，不做任何数值计算，不接触音频字节。
5. Seal 成功**之后**才执行 `s.surface = 第 4 阶段装配好的那一个 Surface 实例`；紧接着 `s.state = SessionState.DATA_READY`；`return None`。
6. `except HarmonicaError as err:` → `s.surface = None`；`s.state = SessionState.FAILED`；`raise CoreBuildError(code=err.code, detail=非空字符串且格式为「阶段名: 原始 detail」, session_id=session_id, component="COMP-C2") from err`。
7. `except Exception as err:`（仅 `Exception` 及其子类，**不捕获** `BaseException`）→ 与第 6 步同路径，但 `code = ErrorCode.CORE_BUILD_FAILED`，`detail` 含 `type(err).__name__` 与 `str(err)`，`from err` 保留因果链。
8. 本文件**不**调用 `harmonica_eval.algorithms` 的任何名字，也不调用任何算法入口；机械判据见 INV-105-6。

**不得部分发布**的精确含义（三条同时成立才算合规）：失败路径上 `_Session.surface` 恒为 `None`；失败路径上 `s.state` 只可能是 `FAILED`（不可能是 `BUILDING` 或 `DATA_READY`）；第 4 步产生的所有局部缓冲随方法返回被丢弃，不留任何模块级或实例级引用。

**资源释放**：第 6/7 步的执行顺序是「先把 `s.surface` 置 `None`，再改状态，再抛」——把引用置空即释放；本文件不提供额外的 `close()` / `release()` 方法（那会成为第 8 个操作）。

**边界**：空 `session_id` / 未知 `session_id` → 抛 `ContractViolation`。`CREATED`（只登记了一段或一段都没登记）→ 抛 `ContractViolation`。`BUILDING` / `DATA_READY` / `FAILED` / `CLOSED` → 抛 `ContractViolation`。单元素 / `NaN` → 不适用（唯一入参是 `session_id: str`）。**重试**：`FAILED` 是终态，状态机不允许从 `FAILED` 再入 `BUILDING`；要重试，C1 必须 `destroy_session` 后 `create_session` 重新登记。

**不变量**：正常流程的 `state` 取值序列只能是 `CREATED → INPUT_READY → BUILDING → DATA_READY`（成功路径）或 `CREATED → INPUT_READY → BUILDING → FAILED`（失败路径），不可跳过；`CANCEL` / `RESET` 是管理操作，允许回退到稳定态（具体转移见 `contract.COMMAND_EFFECTS`）；`DATA_READY` 之外 `_Session.surface` 恒为 `None`。

### 4.6 `status(session_id: str) -> SessionState`

- **输入**：`session_id: str`，取值域 = `self._sessions` 的键集合（含已 `CLOSED` 的键）。
- **输出**：`SessionState` 的**六个成员之一**，且必须是 `_Session.state` 字段当前持有的那个枚举成员（同一对象，`is` 判等成立）。
- **算法口径**：`s = self._sessions.get(session_id)`；`s is None` → 抛 `ContractViolation`；否则 `return s.state`。**一行取值，无分支、无映射、无拼接、无进度推算、无副作用。**
- **禁止**：返回 `INTERNAL_STAGES` 里的任何字符串（`INGESTING` / `ALIGNING` / `MATERIALIZING` / `SEALING`）；返回 `str` 字面量而非枚举成员；把 `BUILDING` 细化成子阶段；为任何状态计算百分比。
- **边界**：空 `session_id` / 未知 `session_id` → 抛 `ContractViolation`。`CLOSED` 会话 → **正常返回** `SessionState.CLOSED`（`destroy_session` 不得删除 `_sessions` 条目，否则本方法在销毁后抛错，破坏「`CLOSED` 是合法可查询状态」）。单元素 / `NaN` → 不适用（唯一入参是 `session_id: str`）。
- **不变量**：本方法**无副作用**（可在任意状态、任意次数调用，不改变任何 `_Session` 字段）；返回值的类型恒为 `SessionState`。

### 4.7 `acquire_surface(session_id: str) -> Surface`

- **输入**：`session_id: str`，取值域 = `self._sessions` 的键集合。
- **输出**：`Surface` 实例——**就是** `_Session.surface` 持有的那一个对象，不复制、不包装、不做只读代理转包。同一会话连续两次调用返回**同一实例**（`is` 判等成立）。
- **算法口径**（逐字照做）：
  1. `s = self._sessions.get(session_id)`；`s is None` → 抛 `ContractViolation`
  2. `if s.state is not SessionState.DATA_READY or s.surface is None: raise ContractViolation(code=ErrorCode.INTERNAL_ERROR, detail="状态非 DATA_READY，无数据面可取得", session_id=session_id, component="COMP-C2")`
  3. `return s.surface`
- **边界**：空 / 未知 `session_id` → 抛 `ContractViolation`。`CREATED` / `INPUT_READY` / `BUILDING` / `FAILED` / `CLOSED` → 抛 `ContractViolation`，**绝不返回 `None`**、**绝不返回部分数据面**、**绝不隐式触发构建**（本方法不调用 ingest/align/features/surface，机械判据见 INV-105-7）。单元素 / `NaN` → 不适用（唯一入参是 `session_id: str`）。
- **所有权**：句柄有效期至 `destroy_session`；借用方不得释放。本文件**不提供** release / close / invalidate **公开**操作（第 8 个操作 = 契约变更）；仅在 `destroy_session` 内部调用 `Surface._invalidate()` 这一私有生命周期钩子。**MUST NOT：不得让 `destroy_session` 之后已发出的任何 Surface 句柄继续可读**；之后调用 `manifest()` 或 `read(...)` 必须抛 `ContractViolation`，因为资源生命周期必须在销毁处收束，旧句柄继续暴露会占用数据面预算并造成泄漏。销毁后本文件也**不再**返回该句柄（`s.surface is None`，第 2 步必抛）；`Surface` 负责在读操作时执行失效判定。
- **不变量**：本方法**无副作用**；返回值恒为 `Surface` 或抛异常，绝不返回 `None`。

### 4.8 `destroy_session(session_id: str) -> None`

- **输入**：`session_id: str`。取值域放宽为**任意 `str`**（含空串与从未存在过的 id）——本操作是清理路径，见下。
- **输出**：`None`，**任何入参都返回 `None`**。
- **算法口径**（逐字照做）：
  1. `s = self._sessions.get(session_id)`
  2. `if s is None: return None`
  3. `Surface._invalidate()`（幂等私有钩子）后 `s.surface = None`（前者使所有已发出的旧句柄失效并解除端口数组引用；后者清会话所有权）
  4. `s.reference_uri = None`；`s.practice_uri = None`（释放已登记输入）
  5. `s.state = SessionState.CLOSED`
  6. **保留** `s.profile_version` 与 `self._sessions[session_id]` 这条字典条目（`status` 必须能在销毁后返回 `CLOSED`）
  7. `return None`
- **幂等**：对 `CLOSED` 会话再次调用 → 第 3–5 步是重复赋值，结果不变，返回 `None`，**不抛异常**；对未知 / 空 `session_id` → 第 2 步直接返回 `None`，**不抛异常**。这是本文件唯一允许「未知句柄不抛错」的操作，依据是目标文件铭牌的 MUST「必须幂等（重复销毁不报错）—— 清理路径上的异常会掩盖真实失败」。**未知 id 与已销毁 id 的行为必须完全一致、不可区分**（否则调用方会开始依赖这一区别）。
- **边界**：`CREATED` / `INPUT_READY` / `BUILDING` / `DATA_READY` / `FAILED` / `CLOSED` 六种状态下调用均合法且都到 `CLOSED`（`FAILED` 与 `CLOSED` 也走同一条路径，不特判）。单元素 / `NaN` → 不适用（唯一入参是 `session_id: str`；传数值型时 `.get()` 未命中，按未知 id 返回 `None`，同样不抛）。
- **不变量**：销毁后 `status(session_id) is SessionState.CLOSED`（不是抛错）；**MUST NOT：任何已发出的旧 Surface 句柄必须失效**，`manifest()` / `read(...)` 必须抛 `ContractViolation`；这是资源生命周期收束和防泄漏的安全不变量（不得仅把 `_Session.surface` 置 `None` 而留下仍可读的外部引用）。`CLOSED` 是终态，任何操作都不得把它改回其他状态；本方法不调用 ingest/align/features/surface 的任何入口。

### 4.9 公开符号集合（机械可断言）

| 符号 | 种类 | 签名 |
| --- | --- | --- |
| `HostCore` | class（`HostContract` 的实现） | `HostCore()` |
| `HostCore.create_session` | method | `(self, profile_version: str) -> str` |
| `HostCore.set_reference` | method | `(self, session_id: str, uri: str) -> None` |
| `HostCore.set_practice` | method | `(self, session_id: str, uri: str) -> None` |
| `HostCore.build_surface` | method | `(self, session_id: str) -> None` |
| `HostCore.status` | method | `(self, session_id: str) -> SessionState` |
| `HostCore.acquire_surface` | method | `(self, session_id: str) -> Surface` |
| `HostCore.destroy_session` | method | `(self, session_id: str) -> None` |
| `INTERNAL_STAGES` | module constant | `Mapping[SessionState, tuple[str, ...]]`，键**只有** `SessionState.BUILDING`，值**恒为** `("INGESTING", "ALIGNING", "MATERIALIZING", "SEALING")` |

**公开成员恰为上述 8 行**：`HostCore` 上除 `__init__` 与下划线开头的名字外，方法名集合必须恰好等于上表 7 个方法名。`INTERNAL_STAGES` 只被本模块的审查/断言使用，**不得**成为任何返回值的取值来源。

### 4.10 数值口径与常量引用（宪章 §22：不留「自行选择」）

本文件**不含任何阈值、容差、单位换算、数值计算**——全部数值口径位于被编排的 4 个阶段模块，本文件只负责按名引用与透传。以下常量名与数字**冻结**，实现者不得另立新值：

| 口径项 | 冻结值 / 常量名 | 在本文件的落点 |
| --- | --- | --- |
| `session_id` 长度与字符集 | 恰 32 字符，`[0-9a-f]`，来源 `uuid.uuid4().hex` | `create_session` |
| 合法会话状态 | `contract.SessionState` 的 6 个成员：`CREATED` / `INPUT_READY` / `BUILDING` / `DATA_READY` / `FAILED` / `CLOSED` | `status` 的返回值 |
| 合法输入状态（两个 setter） | `{CREATED, INPUT_READY}` | `set_reference` / `set_practice` |
| 构建前置状态 | `INPUT_READY`（唯一合法值） | `build_surface` |
| 取数据面前置状态 | `DATA_READY`（唯一合法值） | `acquire_surface` |
| 音频时长上限 | `profile.AUDIO.max_duration_sec`（规格上限 **120 s**），超限判 `INPUT_TOO_LONG` | 透传给 ingest，本文件不判 |
| chroma 端口帧移 | `profile.ALIGN.hop_length` = **2048** 采样点 | 透传给 align/features，本文件不判 |
| RMS 端口帧移 | `profile.MATERIALIZE.rms_hop_length` = **256** 采样点 | 透传给 features，本文件不判 |
| `content_hash` 域分隔前缀 | `contract.CONTENT_HASH_MAGIC` = `b"harmonica-eval/surface/v1\x00"` | 由 surface.py 计算，本文件只保证不重算 |
| 端口 `units` 合法取值 | `contract.UNITS_VOCABULARY`（受控词表） | 由 features/profile 落实 |
| 必含端口 | `contract.CORE_REQUIRED_PORTS` = `("pcm.mapped.reference", "pcm.mapped.practice")` | 由 features 落实 |
| 禁止方法名 | `contract.FORBIDDEN_OPERATIONS` 的 **10** 个名字 | 本文件的否定断言对象（INV-105-5） |
| 内部阶段名（禁止外泄） | `INTERNAL_STAGES[SessionState.BUILDING]` = `("INGESTING", "ALIGNING", "MATERIALIZING", "SEALING")` | 只用于断言，绝不返回 |

**单位约定（不换算，只透传）**：`create_session` 的 `profile_version` 与两个 setter 的 `uri` 是无单位字符串；`status` 返回枚举成员，无单位；`acquire_surface` 返回对象，无单位。本文件**不接触秒、采样点、帧、Hz、音分中的任何一个**。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| `create_session` 的 `profile_version` 为空串或非 `str` | 显式失败。**不创建会话**，`_sessions` 不新增条目 | 抛 `ContractViolation`，`code = ErrorCode.INTERNAL_ERROR`，`component = "COMP-C2"` |
| `set_reference` / `set_practice` / `build_surface` / `status` / `acquire_surface` 收到未登记的 `session_id` | 显式失败。**零副作用**（不隐式建会话、不隐式登记） | 抛 `ContractViolation`，`code = ErrorCode.INTERNAL_ERROR` |
| `set_reference` / `set_practice` 的 `uri` 为空串或非 `str` | 显式失败。**不写入 `_Session`**，不触发解码 | 抛 `ContractViolation`，`code = ErrorCode.INTERNAL_ERROR` |
| 两个 setter 在 `BUILDING` / `DATA_READY` / `FAILED` / `CLOSED` 状态下被调用 | 显式失败。状态不变、已发布数据面不变 | 抛 `ContractViolation`，`code = ErrorCode.INTERNAL_ERROR`（`detail` 含当前状态名） |
| `build_surface` 在 `CREATED`（只登记一段或一段未登记）被调用 | 显式失败。状态**不变**（仍 `CREATED`），不进入 `BUILDING` | 抛 `ContractViolation`，`code = ErrorCode.INTERNAL_ERROR` |
| `build_surface` 在 `BUILDING` / `DATA_READY` / `FAILED` / `CLOSED` 被调用 | 显式失败。状态不变；`DATA_READY` 下重复调用**不得**销毁已发布数据面 | 抛 `ContractViolation`，`code = ErrorCode.INTERNAL_ERROR` |
| 四阶段任一抛出 `HarmonicaError` 子类（含 `INPUT_UNREADABLE` / `INPUT_TOO_SHORT` / `INPUT_SILENT` / `INPUT_TOO_LONG` / `ALIGNMENT_UNRECOVERABLE` / `CORE_BUILD_FAILED`） | 显式失败。**不得部分发布**：`_Session.surface` 置 `None`，状态 → `FAILED`，全部资源释放，未触发任何算法。**禁止**静默降级为「逐点硬比」或截断输入 | 抛 `CoreBuildError`，`code` = 原始 `err.code`（逐字保留），`detail` = `「阶段名: 原始 detail」`，`from err` |
| 四阶段任一抛出非 `HarmonicaError` 的 `Exception`（含 `ValueError` / `ImportError` / `MemoryError` / `FileNotFoundError`） | 显式失败。与上一行同路径同副作用 | 抛 `CoreBuildError`，`code = ErrorCode.CORE_BUILD_FAILED`，`detail` 含 `type(err).__name__` 与 `str(err)` |
| 四阶段任一抛出 `BaseException` 非 `Exception` 子类（`KeyboardInterrupt` / `SystemExit`） | **不捕获**，原样向上传播；`_Session.state` 停在 `BUILDING` | 原异常类型不变；C1 负责随后 `destroy_session` |
| `acquire_surface` 在非 `DATA_READY` 状态（含 `CLOSED`）被调用 | 显式失败。**绝不返回 `None`**、**绝不返回部分数据面**、**绝不隐式触发构建** | 抛 `ContractViolation`，`code = ErrorCode.INTERNAL_ERROR` |
| `status` 对已 `CLOSED` 的会话被调用 | **正常返回**，不是失败 | 返回 `SessionState.CLOSED` |
| `destroy_session` 对 `CLOSED` 会话重复调用 | **幂等成功**，非失败。第 3–5 步重复赋值，结果不变 | 返回 `None` |
| `destroy_session` 对未知 `session_id`（含空串）被调用 | **幂等成功**，非失败。与「已销毁」行为完全一致、**不可区分** | 返回 `None` |
| `destroy_session` 对 `FAILED` 会话被调用 | **正常成功**，非失败。失败态可被清理到 `CLOSED` | 返回 `None` |
| `status` 返回值的类型被要求为 `SessionState` 成员 | 返回值恒为 `SessionState` 的 6 个成员之一；内部阶段名 `INGESTING` / `ALIGNING` / `MATERIALIZING` / `SEALING` **不得**成为返回值 | 返回 `SessionState` 成员 |
| C1 试图调用 `FORBIDDEN_OPERATIONS` 中的任一名字（`align` / `fft` / `stft` / `compute_feature` / `generate_pitch_input` / `generate_plugin_requirement` / `prepare_for_pitch` / `prepare_for_timing` / `register_algorithm` / `list_algorithms`） | 显式失败：这些名字在本类上**不存在**，调用即属性缺失 | `AttributeError`（CPython 对缺失属性的原生行为；本文件不提供 `__getattr__` 兜底，兜底会掩盖泄漏） |
| 算法主动中止（C1 的 `CANCEL`）或用户重置（C1 的 `RESET`） | **不是错误**，不产生任何 `ErrorCode`，状态不为 `FAILED`；按 `contract.COMMAND_EFFECTS` 冻结转移：`CANCEL` 保持已 Seal 的数据面有效、回到 `DATA_READY`；`RESET` 销毁数据面、清空已登记输入、回到 `CREATED`，会话对象本身保留 | C1 侧语义，本文件不产生异常 |
| C4 界面断开 | **不是错误**，本文件不做任何检测（`ErrorCode.COCKPIT_DETACHED` 在 v0.1 不会产生） | 本文件不产生异常 |
| 任何未列入本表的失败路径在实现中出现 | 视为缺陷：不得新增错误码，不得吞掉异常 | 必须回到 §10 提 `MOLD BREAK` |

★ 宪章 §5.6：禁止静默降级。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-105-1 | **正常流程状态单调推进**（铭牌 MUST）：`CREATED → INPUT_READY → BUILDING → DATA_READY`，任一状态可 → `FAILED`，结束 → `CLOSED`；不可跳过。**`CANCEL` / `RESET` 是管理操作，允许回退到稳定态。** | 对每个操作 × 每个状态构造调用，断言返回值或异常类型；每次调用后断言 `status()` 落在合法后继集合内。判据：从 `CREATED` 直接 `build_surface` 必抛且状态仍为 `CREATED`；从 `DATA_READY` 调 `set_reference` 必抛且状态仍为 `DATA_READY`；`FAILED` 后再调 `build_surface` 必抛且状态仍为 `FAILED`；`CANCEL` / `RESET` 按 `contract.COMMAND_EFFECTS` 转移 |
| INV-105-2 | **`status()` 只返回 `SessionState` 的六个值之一**（铭牌 MUST）；内部阶段 `INGESTING` / `ALIGNING` / `MATERIALIZING` / `SEALING` 不得外泄 | `assert isinstance(core.status(sid), SessionState)`；`assert core.status(sid).value in {"CREATED","INPUT_READY","BUILDING","DATA_READY","FAILED","CLOSED"}`；`assert core.status(sid).value not in INTERNAL_STAGES[SessionState.BUILDING]`（在 6 种状态下各断言一次） |
| INV-105-3 | **`build_surface()` 失败时状态 → `FAILED`、不得部分发布、资源全部释放、未触发任何算法**（铭牌 MUST）；且 `FAILED` 会话的 `acquire_surface` 必然抛 `ContractViolation` | 用不可读 uri 触发失败后断言：`core.status(sid) is SessionState.FAILED`；`pytest.raises(ContractViolation)` 于 `core.acquire_surface(sid)`；断言异常是 `CoreBuildError` 且 `err.code is ErrorCode.INPUT_UNREADABLE`、`err.session_id == sid`、`err.__cause__ is not None` |
| INV-105-4 | **同一对输入 + 同一 `profile_version` ⇒ 同一数据面（`content_hash` 一致）**（铭牌 MUST） | 两个独立会话、同一对 uri、同一 `profile_version`，各 `build_surface` 后逐端口比对：`m1.sealed is True`、`m2.sealed is True`、`set(m1.ports) == set(m2.ports)`、且对每个 `pid` 有 `m1.ports[pid].content_hash == m2.ports[pid].content_hash` |
| INV-105-5 | **不得定义 `FORBIDDEN_OPERATIONS` 中的任何方法名**（铭牌 MUST NOT） | `assert not (set(FORBIDDEN_OPERATIONS) & {n for n in dir(HostCore) if not n.startswith("_")})`；且 `assert not any(hasattr(core, n) for n in FORBIDDEN_OPERATIONS)` |
| INV-105-6 | **不接收任何算法信息**（铭牌 MUST NOT）：本文件不 import `harmonica_eval.algorithms` / `harmonica_eval.host` / `harmonica_eval.cockpit`，也不调用任何算法入口 | 断言 `set(sys.modules) & {"harmonica_eval.algorithms", "harmonica_eval.host", "harmonica_eval.cockpit"}` 为空 **在 import 本模块并跑完一次完整会话之后**；对照断言：运行 `import harmonica_eval.algorithms` 前后，`harmonica_eval.core.api.build_surface.__code__.co_names` 不变 |
| INV-105-7 | **不存在非 `DATA_READY` 状态取得数据面的路径**（铭牌 MUST NOT） | 在 `CREATED` / `INPUT_READY` / `BUILDING` / `FAILED` / `CLOSED` 五种状态下各调一次 `acquire_surface`，全部 `pytest.raises(ContractViolation)`；`BUILDING` 那一例在同一线程内用 `monkeypatch` 把内部阶段入口替换为「置 `BUILDING` 后调用 `acquire_surface`」的函数，断言其抛出 |
| INV-105-8 | **`destroy_session` 必须使所有已发出的 Surface 句柄失效**；之后任何 `manifest()` / `read(...)` 必须抛 `ContractViolation`（资源生命周期收束与防泄漏） | `h = core.acquire_surface(sid)`；`core.destroy_session(sid)`；断言 `core.status(sid) is SessionState.CLOSED`；`pytest.raises(ContractViolation)` 于 `h.manifest()`，并覆盖 `h.read(...)` 同样抛 `ContractViolation`。**§8 命令 6 的判据保持不变，不得放宽。** |
| INV-105-9 | **`destroy_session` 幂等**：重复销毁与未知 id 都不报错，且两者行为不可区分 | `core.destroy_session(sid)`；`core.destroy_session(sid)`；`core.destroy_session("")`；`core.destroy_session("0" * 32)` —— 四次调用都返回 `None` 且不抛异常；随后 `core.status(sid) is SessionState.CLOSED` |
| INV-105-10 | **公开操作面恰好 7 个 + 1 个模块常量 `INTERNAL_STAGES`**：类上除 `__init__` 与下划线开头的名字外无非方法属性 | 断言 `{n for n in dir(HostCore) if not n.startswith("_")} == {"create_session","set_reference","set_practice","build_surface","status","acquire_surface","destroy_session"}`；断言 `set(INTERNAL_STAGES) == {SessionState.BUILDING}` 且 `INTERNAL_STAGES[SessionState.BUILDING] == ("INGESTING","ALIGNING","MATERIALIZING","SEALING")` |
| INV-105-11 | **两个 setter 不触发解码或计算**（铭牌 MUST：只登记） | 用不存在的 uri（如 `"/nonexistent/nope.wav"`）调用 `set_reference` / `set_practice`，断言**不抛异常**且 `status` 变为 `INPUT_READY`；再断言此前对 `harmonica_eval.core.ingest` 入口的 `monkeypatch`  spy 调用计数为 `0` |
| INV-105-12a | **`create_session` 的 `profile_version` 被逐字记录**（铭牌 MUST）。本文件对它是不透明字符串：只判非空、只存入 `_Session.profile_version`；**不**解析、**不**比对已知版本、**不**产生任何可观测的数据面差异 | 建会话后白盒读 `HostCore._sessions[sid].profile_version`（`_Session` 是 §4.1 定义的模块私有记录），断言 `== "CORE_PROFILE_V0.1"`，**逐字符相等**（不归一化、不去空白、不改大小写、不做前缀匹配）；再建第二个会话传 `"CORE_PROFILE_V0.1-x"`，断言 `_sessions[sid2].profile_version == "CORE_PROFILE_V0.1-x"`、`sid2 != sid`，且第一个会话的 `_sessions[sid].profile_version` 未被第二次调用改写。★ 本判据是原 INV-105-12 中**唯一可达**的那一半 |
| INV-105-12b | ★ **SKIPPED —— 非缺陷，是预期行为，不判 PASS / FAIL**：`profile_version` **不影响** `content_hash`。`content_hash` 的输入在 FILE-104 §4.2 冻结为 `CONTENT_HASH_MAGIC` + `port_id.encode("utf-8")` + `element_type`（即 `str(data.dtype)`）+ `shape`（小端 int64）+ `data`（C 序）—— **不含** `profile_version`；而 `SurfaceManifest.profile_version` 只是 manifest 原样携带的字段。⇒ 同一对 uri、同一实现下，两个不同 `profile_version` 的会话**必然**逐端口 `content_hash` 全等，这是**预期行为**，**不是**「profile 未被消费」的证据。若要让版本影响 hash，须由项目负责人裁定修改 `content_hash` 算法（属**契约变更**：`contract.PortDescriptor.content_hash` 的冻结算法 + FILE-104 §4.2），实现者**无权**自行加盐或改输入 | **不执行**原断言。取代性断言（机械可判）：同一对 uri、`profile_version` 分别为 `"CORE_PROFILE_V0.1"` 与 `"CORE_PROFILE_V0.1-x"` 建两个会话并 `build_surface`，断言 `m1.sealed is True`、`m2.sealed is True`、`set(m1.ports) == set(m2.ports)`、且 `all(m1.ports[p].content_hash == m2.ports[p].content_hash for p in m1.ports)`。★ 本行**不得标 FAIL**，**不得**据此回 §10 上报（原判据里的 `'profile_version 未被消费'` 断言已作废） |
| INV-105-13 | **本文件不 import §3 名单之外的任何模块**（封闭依赖） | 断言 `harmonica_eval.core.api` 的源码中每条 import 语句的来源逐字落在 §3「可以 import」名单内；运行期断言 `sys.modules` 中不出现 §3「禁止 import」列出的 `json` / `pickle` / `random` / `logging` 等名字**由本模块引入**（对照 import 前后差集） |

★★ **更正（恒假判据拆分）：原 INV-105-12 的后半条断言恒假，已拆为 12a / 12b。** ★★

原写「**`create_session` 的 `profile_version` 被记录且区分会话**：不同
`profile_version` 产生不同数据面 hash（同输入下）」，判据为「同一对 uri、
`profile_version` 分别为 `"CORE_PROFILE_V0.1"` 与 `"CORE_PROFILE_V0.1-x"`
建两会话并构建，断言至少一个端口的 `content_hash` 不同（若全部相同，则
profile 解析未消费该字符串，回 §10 上报）」—— 一条判据把两个互不相干的
性质（**逐字记录** 与 **区分数据面 hash**）捆在了一起。

**为什么恒假**：`content_hash` 的输入被 `class PortDescriptor` 的 docstring
与 FILE-104 §4.2 双重冻结为 `CONTENT_HASH_MAGIC` + `port_id` +
`element_type` + `shape` + `data` **五项，其中没有 `profile_version`**；
同一处（§4.2）又明写 `profile_version` 是**不透明字符串**、只存不解析、
不比对本仓已登记版本（`profile` 仅被允许提供 `AUDIO.sample_rate` 这一个数值，
版本字符串仍不进 hash 输入）。两处叠加 ⇒ 同输入下两个会话的数据
逐字节相同 ⇒ 所有 `content_hash` **必然全等** ⇒「至少一个端口 hash 不同」
**永远不可能成立**。这条判据不是「难」，是**恒失败**：实现者无论怎么写
都过不了验收，只会把自己写成「profile 未被消费」的缺陷上报。

**本版冻结**：拆为两条 ——
- **INV-105-12a**：保留可达的那一半，只验「逐字记录」。
- **INV-105-12b**：标 **SKIPPED**，不判 PASS / FAIL。

**为什么 12b 是 SKIPPED 而非缺陷**：hash 输入里的 `port_id` /
`element_type` / `shape` / `data` 全部由 uri 指向的音频与端口清单决定，
与版本字符串无关；版本身份由 `SurfaceManifest.profile_version` **单独承载**
（`contract.py` 确有该字段）。要让版本进入 hash，就得改
`contract.PortDescriptor.content_hash` 的冻结算法 —— 那是**契约变更**，
须由项目负责人裁定，实现者无权自行加盐。故按「本层无法达成」标 SKIPPED，
并在验收表中以「不同版本 ⇒ 逐端口 hash 全等」作为取代性断言。

★ 同源残留（本次未改，超出本处修改范围）：§8 命令 5 的
`assert any(a.ports[p].content_hash != d.ports[p].content_hash ...)`
与 §9 的「profile 被消费证据」条目出自同一条原判据、同样恒假，
须由项目负责人裁定后同步，否则实现者跑 §8 命令 5 仍会失败。

---

## 7 · 边界（明确不做）

- **不做解码**：不打开 `uri` 指向的文件，不读字节，不解析容器（wav/flac/mp3），不做多声道下混、重采样、静音检测、时长检查。这些全部属 `core/ingest.py`。
- **不做时间映射**：不构造 `TimelineBasis.REFERENCE` / `TimelineBasis.WARPED` 网格，不算 warp 路径，不判 `ALIGNMENT_UNRECOVERABLE`。这些全部属 `core/align.py`。
- **不做特征计算**：不算 f0、chroma、RMS、note、能量，不做任何数值计算，不接触 numpy。全部属 `core/features.py` 与下游算法。
- **不装配数据面**：不构造 `PortDescriptor`、不分配端口缓冲、不算 `content_hash`、不决定 Seal 时机。全部属 `core/surface.py`。
- **不解析 profile**：不校验 `profile_version` 是否为已知版本，不读取 `AUDIO.max_duration_sec` / `ALIGN.hop_length` / `MATERIALIZE.rms_hop_length`，不决定端口清单。`profile_version` 是不透明字符串。★ `harmonica_eval.profile` 的唯一允许用途是从 `AUDIO` 取采样率数值 `sample_rate = int(AUDIO.sample_rate)`（§3 白名单，FINDING-7）；这不是 profile 解析。
- **不持有算法注册表**：不知道有哪些算法，不注册、不列举、不调度、不超时、不重试、不评分（SPEC 边界：本仓只做「双音频对比 → 客观数值指标」）。
- **不生成自然语言反馈**：不产出任何给人读的结论句、诊断、建议、教学提示。
- **不做 I/O 与格式化**：不打印、不写日志文件、不序列化 JSON、不写磁盘（`logging` / `json` / `pickle` / `io` / `os` / `pathlib` 全在 §3 禁入名单）。
- **不做并发控制**：不加锁、不起线程、不用 `asyncio`（`threading` / `asyncio` 在禁入名单）。调用方串行调用；两个会话的状态由两个独立的 `_Session` 记录，互不读取。
- **不做进度汇报**：不提供 `progress()` 操作，不推算百分比，`status()` 不返回任何中间进度（加一个进度查询 = 契约从 7 个操作变 8 个 = 契约变更）。
- **不做取消与重置**：不提供 `cancel()` / `reset()`（那是 C1 的编排职责）；不加取消标志、不设检查点。要重试必须 `destroy_session` 后 `create_session`。
- **不做 C4 / 界面**：不 import `harmonica_eval.cockpit`，不构造 `UiView` / `UiSeries` / `UiScalar`，不做界面存活检测。
- **不做算法结果校验**：不读 `AlgorithmResultEnvelope`，不判 `ALGORITHM_RESULT_INVALID`，不产生 `PLUGIN_INCOMPATIBLE`（端口兼容性判定在 C1）。
- **不删会话条目**：`destroy_session` 保留 `_sessions[session_id]` 与 `profile_version`，以便 `status` 在销毁后返回 `CLOSED`；不做内存回收式 `del`。
- **不定义 `__getattr__` / `__getattribute__` 兜底**：缺失属性必须原样抛 `AttributeError`，兜底会把「越界调用」变成静默成功。
- **不新增第 8 个公开操作**：出现即 `MOLD BREAK`，不在本文件就地添加。

---

## 8 · 怎么验证你写对了

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
# 1 · 模块可 import，且门面成员恰好是契约的 8 行（7 方法 + 1 常量）
python -c "import harmonica_eval.core.api as m; assert {n for n in dir(m.HostCore) if not n.startswith('_')} == {'create_session','set_reference','set_practice','build_surface','status','acquire_surface','destroy_session'}, sorted(n for n in dir(m.HostCore) if not n.startswith('_')); assert set(m.INTERNAL_STAGES) == {__import__('harmonica_eval.contract', fromlist=['SessionState']).SessionState.BUILDING}; print('OK facade=7+1')"

# 2 · 禁止方法名一个都不存在
python -c "from harmonica_eval.contract import FORBIDDEN_OPERATIONS as F; from harmonica_eval.core.api import HostCore as H; c=H(); assert not (set(F) & set(dir(H))), sorted(set(F) & set(dir(H))); assert not any(hasattr(c,n) for n in F); print('OK forbidden=0')"

# 3 · 空 / 未知 session_id 与空 uri 全部抛 ContractViolation，且全部零副作用
python -c "
from harmonica_eval.core.api import HostCore
from harmonica_eval.contract import ContractViolation as V
c = HostCore()
for fn, args in [('set_reference', ('', 'a.wav')), ('set_practice', ('', 'a.wav')),
                 ('build_surface', ('',)), ('status', ('',)), ('acquire_surface', ('',)),
                 ('set_reference', ('0'*32, 'a.wav')), ('status', ('0'*32,)),
                 ('acquire_surface', ('0'*32,)), ('set_reference', ('', '')), ('set_practice', ('', ''))]:
    try:
        getattr(c, fn)(*args); raise SystemExit('FAIL no-raise ' + fn)
    except V: pass
try:
    c.create_session(''); raise SystemExit('FAIL empty profile accepted')
except V: pass
try:
    c.create_session(None); raise SystemExit('FAIL None profile accepted')
except V: pass
sid = c.create_session('CORE_PROFILE_V0.1')
for fn, args in [('set_reference', (sid, '')), ('set_practice', (sid, '')), ('set_reference', (sid, None)),
                 ('build_surface', (sid,)), ('acquire_surface', (sid,))]:
    try:
        getattr(c, fn)(*args); raise SystemExit('FAIL no-raise ' + fn)
    except V: pass
assert c.status(sid).value == 'CREATED', 'failed call mutated state'
print('OK violations')
"

# 4 · 状态机单调 + status 不泄漏内部阶段 + 失败不部分发布
python -c "
from harmonica_eval.core.api import HostCore, INTERNAL_STAGES
from harmonica_eval.contract import ContractViolation as V, CoreBuildError, ErrorCode, SessionState as S
c = HostCore()
sid = c.create_session('CORE_PROFILE_V0.1')
assert c.status(sid) is S.CREATED
c.set_reference(sid, '/nonexistent/ref.wav'); assert c.status(sid) is S.CREATED
c.set_practice(sid, '/nonexistent/pra.wav'); assert c.status(sid) is S.INPUT_READY
# ★★ 更正（⑳ 执行确认）：原写断言「INPUT_READY 下 set_reference 必须抛」——
#   **与本文件 §4.2 第 5 步的边界条款直接矛盾。** §4.2 明写：
#   「重复登记（同一会话第二次调 set_reference）：**合法，覆盖旧值**；
#    在 INPUT_READY 下覆盖后状态仍是 INPUT_READY（不倒退、不重算）。」
#   实测参考实现：不抛，状态保持 INPUT_READY —— 与 §4.2 一致，是**判据**错。
#   改为断言「覆盖合法、状态不倒退、零副作用」。
c.set_reference(sid, '/nonexistent/other.wav')
assert c.status(sid) is S.INPUT_READY, '覆盖后状态不得倒退'
try:
    c.acquire_surface(sid); raise SystemExit('FAIL acquire before build')
except V: pass
try:
    c.build_surface(sid); raise SystemExit('FAIL build should fail on unreadable input')
except CoreBuildError as e:
    assert e.session_id == sid and e.__cause__ is not None, 'no cause chain'
assert c.status(sid) is S.FAILED
assert c.status(sid).value not in INTERNAL_STAGES[S.BUILDING]
try:
    c.acquire_surface(sid); raise SystemExit('FAIL acquire on FAILED')
except V: pass
try:
    c.build_surface(sid); raise SystemExit('FAIL rebuild on FAILED')
except V: pass
assert c.destroy_session(sid) is None
assert c.destroy_session(sid) is None
assert c.destroy_session('') is None
assert c.status(sid) is S.CLOSED
print('OK state machine')
"

# 5 · 同一对输入 ⇒ 同一数据面（content_hash 逐端口全等）；★ 不同 profile_version **同样**全等 —— `profile_version` 是只存不解析的不透明字符串，不进 `content_hash` 的五项输入（见 INV-105-12b）
#     先导出被测素材（5 / 6 两条命令都读这两个变量；路径指向本项目实际使用的音频文件）
export REF="/绝对路径/参考演奏.wav" PRA="/绝对路径/练习演奏.wav"
python -c "
import os
from harmonica_eval.core.api import HostCore
REF, PRA = os.environ['REF'], os.environ['PRA']
def build(pv):
    c = HostCore(); sid = c.create_session(pv)
    c.set_reference(sid, REF); c.set_practice(sid, PRA)
    c.build_surface(sid); return c.acquire_surface(sid).manifest()
a = build('CORE_PROFILE_V0.1'); b = build('CORE_PROFILE_V0.1')
assert a.sealed is True and b.sealed is True
assert set(a.ports) == set(b.ports)
assert all(a.ports[p].content_hash == b.ports[p].content_hash for p in a.ports)
d = build('CORE_PROFILE_V0.1-x')
# ★★ 更正（同 INV-105-12b 同源，第三轮盲审 A 复核时发现的残留）：
#   原写 assert any(a.ports[p].content_hash != d.ports[p].content_hash ...)
#   并附 'profile_version 未被消费' —— **恒假**。
#   content_hash 的输入在 FILE-104 §4.2 冻结为
#   CONTENT_HASH_MAGIC + port_id + element_type + shape + data，**不含 profile_version**，
#   所以两个版本必然逐端口 hash 全等。这不是缺陷，是**预期行为**。
#   取代为「版本不改变数据面」的正面断言。
assert d.sealed is True
assert set(a.ports) == set(d.ports)
assert all(a.ports[p].content_hash == d.ports[p].content_hash for p in a.ports), \
    'profile_version 不应影响 content_hash（它不是 hash 输入）'
print('OK determinism', len(a.ports), 'ports; profile_version 不进入 hash（预期）')
"

# 6 · 销毁后旧句柄失效
python -c "
import os
from harmonica_eval.core.api import HostCore
from harmonica_eval.contract import ContractViolation as V, SessionState as S
c = HostCore(); sid = c.create_session('CORE_PROFILE_V0.1')
c.set_reference(sid, os.environ['REF']); c.set_practice(sid, os.environ['PRA']); c.build_surface(sid)
h = c.acquire_surface(sid); c.destroy_session(sid)
assert c.status(sid) is S.CLOSED
try:
    h.manifest(); raise SystemExit('FAIL stale handle still readable')
except V: print('OK stale handle rejected')
"

# 7 · 门面不透传内部模块给 C1（无算法依赖、无阶段名外泄）
python -c "
import sys
import harmonica_eval.core.api  # noqa: F401
leaked = {'harmonica_eval.algorithms','harmonica_eval.host','harmonica_eval.cockpit'} & set(sys.modules)
assert not leaked, sorted(leaked)
print('OK no upward dependency')
"
```

**验收判据**（可机械判定，非「看起来对」）：
- [ ] 命令 1 输出 `OK facade=7+1`：`{n for n in dir(HostCore) if not n.startswith('_')}` 恰好等于 7 个操作名，且 `set(INTERNAL_STAGES) == {SessionState.BUILDING}`
- [ ] 命令 2 输出 `OK forbidden=0`：`FORBIDDEN_OPERATIONS` 的 10 个名字与 `dir(HostCore)` 的交集为空，且对实例 `hasattr` 全为 `False`
- [ ] 命令 3 输出 `OK violations`：10 组空/未知入参调用全部抛 `ContractViolation`，且失败调用后 `status(sid)` 仍为 `CREATED`
- [ ] 命令 4 输出 `OK state machine`：`CREATED`（登记一段后仍为 `CREATED`）→ `INPUT_READY` → `BUILDING` → `FAILED` 全链成立；`CoreBuildError.__cause__ is not None`；`FAILED` 后 `acquire_surface` 与再次 `build_surface` 都抛 `ContractViolation`；`status` 返回值不属于 `INTERNAL_STAGES[BUILDING]`；三次 `destroy_session`（重复 / 空串）都返回 `None` 且 `status` 为 `CLOSED`
- [ ] 命令 5 输出 `OK determinism N ports`（`N` 为该 profile 实际端口数）：`sealed is True`，两个同 profile 会话端口集合相同且逐端口 `content_hash` 全等；★ 第三个**不同 `profile_version`** 会话同样**逐端口 hash 全等**（`profile_version` 不进 hash 输入，见 INV-105-12b）——若断言「至少一个不同」则为恒假判据，不得据此上报 `MOLD BREAK`
- [ ] 命令 6 输出 `OK stale handle rejected`：`destroy_session` 后 `status` 为 `CLOSED`，旧句柄 `manifest()` 抛 `ContractViolation`
- [ ] 命令 7 输出 `OK no upward dependency`：`harmonica_eval.algorithms` / `harmonica_eval.host` / `harmonica_eval.cockpit` 均未因 import 本模块而进入 `sys.modules`
- [ ] 命令 1–7 全部 `exit code 0`，且没有任何一行输出以 `FAIL` 开头
- [ ] 本文件（`.spec/build/FILE-105-v1.md`）正文中不残留任何尖括号包裹的「待填」占位符

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] **实现文件**：`harmonica_eval/core/api.py`（本 BUILD-INSTRUCTION 的唯一产物；不再有第二个产物）
- [ ] **§8 命令 1–7 的原始 stdout 与 `exit code`**，逐条贴出，包含 `OK facade=7+1` / `OK forbidden=0` / `OK violations` / `OK state machine` / `OK determinism N ports` / `OK stale handle rejected` / `OK no upward dependency` 七行
- [ ] **门面成员快照**：`python -c "from harmonica_eval.core.api import HostCore; print(sorted(n for n in dir(HostCore) if not n.startswith('_')))"` 的完整输出（证明恰为 7 个名字，且无第 8 个操作）
- [ ] **禁止方法名快照**：`python -c "from harmonica_eval.contract import FORBIDDEN_OPERATIONS as F; print(sorted(set(F) & set(dir(__import__('harmonica_eval.core.api', fromlist=['HostCore']).HostCore))))"` 的输出为 `[]`
- [ ] **`status` 六值覆盖证据**：一个会话依次走过 `CREATED` / `INPUT_READY` / `BUILDING` / `DATA_READY` / `FAILED` / `CLOSED` 六种状态时 `status()` 的实际返回值列表，且列表中没有 `INGESTING` / `ALIGNING` / `MATERIALIZING` / `SEALING` 中的任何一个
- [ ] **确定性证据**：同一对音频、同一 `profile_version` 下两个独立会话的逐端口 `content_hash` 对照表（端口 id → 两个 hash → 是否相等），全部为「相等」
- [ ] **`profile_version` 被逐字记录**（INV-105-12a）：建会话后 `_Session.profile_version` 与传入值**逐字符相等**（含 `CORE_PROFILE_V0.1-x` 这种带后缀的）。
      ★ **本项已改写**（第三轮盲审 A 复核）：原写「两个版本的 hash 对照表，至少一行不相等（若全相等即为契约缺口，须按 §10 上报）」—— **该期望恒假**。`content_hash` 的输入不含 `profile_version`（FILE-104 §4.2 冻结），两版本必然全等；全等是**预期行为**，**不是**契约缺口，**不得**据此上报。
- [ ] **版本不影响数据面**（INV-105-12b，SKIPPED 语义）：同一对 uri、两个不同 `profile_version` 建会话并 build，两者 `sealed is True`、端口集合相同、逐端口 `content_hash` **全等**。
- [ ] **失败因果链证据**：一次 `CoreBuildError` 的 `err.code` / `err.detail` / `err.session_id` / `err.component` 与 `repr(err.__cause__)` 的完整打印
- [ ] **依赖封闭证据**：`harmonica_eval/core/api.py` 全文的 import 语句列表，逐条对照 §3「可以 import」名单，无一条越界；以及命令 7 的输出
- [ ] **素材说明**：§8 命令 5 / 6 所用 `REF` 与 `PRA` 两个环境变量的实际取值（音频文件不进 git，故只记录路径与时长）
- [ ] **已知缺口记录**（若存在）：四阶段入口签名与本文件 §4.5 第 4 步的实参不一致时，按 §10 提交 `MOLD BREAK`，不得自行改契约。★ 「命令 5 的 profile **区分**断言失败」已从本条移除——按 INV-105-12b，`profile_version` 不进 `content_hash`，不同版本 hash **本就应当全等**，不存在「区分断言」可失败

---

## 10 · ★ 何时必须停止并上报（§22 硬失败对策）

**以下情况必须停止，提交 `MOLD BREAK`，不得自行设计：**

1. 你发现本文件**需要做上层设计**才能实现（定新阈值 / 新口径 / 新端口 / 新错误码）
2. 本文件与任何上游工件**冲突**
3. 你需要的依赖**不在 §3 清单里**
4. §4 的行为规格**不足以确定唯一实现**
5. 你认为 §4 的规格本身**是错的**

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

**绝对禁止**：先做 workaround（§38 明文禁止）· 自行加「合理的」默认值掩盖冲突 ·
静默缩小范围。
