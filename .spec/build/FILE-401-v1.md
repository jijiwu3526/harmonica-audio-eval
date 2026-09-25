# FILE-401 — harmonica_eval/cockpit/app.py

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/cockpit/app.py`
> 生成依据：`SPEC.md@v2.1` · `contract.py` · `profile.py@CORE_PROFILE_V0.1` · `COMPONENTS.md`
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-401 |
| 所属组件 | COMP-C4 Cockpit —— Mac 端**本机开发者调试视图**。包 `harmonica_eval/cockpit/`，本文件 `app.py` 是该包唯一的实现文件。C4 不在内核链路上：它是 `..contract` 的**消费者**，不生产契约类型、不发布数据面、不产出算法结果。 |
| 层级 | L3（symbol / implementation） |
| 上游 | 1) `harmonica_eval/cockpit/__init__.py` 的包出口 `launch_cockpit(...)` —— 唯一调用方，把 `run_local_ui(port)` 的返回值当作进程退出码；2) 调用方注入的 `UiProjectionPort` 实现（COMP-C1 Framework/Host 侧提供）—— 本文件读 `snapshot()`、写 `submit()` 的唯一来源，C4 不构造它；3) 开发者本人 —— 在 Mac 上点 6 个按钮、在弹出的文件框里选音频路径。 |
| 下游 | 1) `UiProjectionPort.snapshot() -> UiView`：唯一读路径；2) `UiProjectionPort.submit(UiCommand) -> None`：唯一写路径，且只发 `UiCommandKind` 的 6 个成员；3) 屏幕与终端：状态行、标量区、曲线区、进度行、错误区、6 个按钮（文案取 `COMMAND_LABELS`），以及一行本机 URL（写 `sys.stderr`，见 §4.4 第 8 步）；4) 对内核**无数据输出** —— 界面不返回计算结果、不返回 payload、不写任何文件。 |
| 同层邻居 | 同文件内 14 个公开符号互为邻居：常量 `LOCAL_BIND_HOST` / `EXIT_OK` / `EXIT_START_FAILED` / `COMMAND_LABELS`；入口 `run_local_ui`；渲染 `render_status` / `render_scalars` / `render_series_plot` / `render_progress` / `render_error` / `build_plots`；命令 `build_command` / `solicit_asset_uri` / `submit_command`。调用关系：`run_local_ui` → 全部 `render_*` 与 `build_plots`；`build_plots` → `render_series_plot`；`run_local_ui` → `solicit_asset_uri` → `build_command` → `submit_command`。跨文件同层邻居：C1 侧 `UiProjectionPort` 的实现类（`harmonica_eval/host/` 内）与 C3 侧产出 payload 的算法（`harmonica_eval/algorithms/` 内）—— 它们与本文件是「契约的两侧」，**互不 import**。 |

**结构定位（三条，缺一条本文件即不成立）**：

1. **只给开发者看，是 Mac 端本机视图。** 读者是坐在开发机前的实现者与负责人，用途是核对投影字段与时间轴含义。不做手机端，不做平板端，不做响应式布局，不做面向学习者的界面 —— SPEC.md@v2.1 §1 的裁定例外只覆盖这一个开发者视图。
2. **与 `__main__` 在结构上同类。** 本包的内核外结果消费者有两类：命令行入口 `__main__`（`python -m harmonica_eval`）与本文件 C4。两者都在内核之外，都只**读**内核的结果（`__main__` 读最终数值报告，C4 读 `UiView`），都不写回内核、都不持有内核对象、都不被内核 import。两者唯一的差别是输出介质：`__main__` 把结果写到 stdout，C4 把结果画到本机界面上。
3. **与内核零耦合。** C4 只认 `..contract` 的 6 个符号（见 §3）。**删掉 C4（整个 `harmonica_eval/cockpit/` 目录），C1 / C2 / C3 仍须跑通** —— 这是不变量 F 的现场检验，§8 给出机械判据。

**你的权限**：只实现本文件。不得修改任何其他文件，不得修改契约，
不得新增端口，不得新增依赖。

---

## 2 · 这个文件为什么存在

### 追溯

- **Product Intent（SPEC.md@v2.1 §1，负责人裁定例外）**：本仓的边界是「双音频对比 → 客观数值指标」，不做 UI / 产品化（AGENTS.md 铁律 2 是同款边界）。C4 是这个边界上的**唯一例外**：一个只给开发者看的本机调试视图。例外成立的代价写在目标文件铭牌的 MUST NOT 里 —— 界面不得发明内核能力、不得解释算法内部、不得承担验收。
- **Requirement（目标文件 INTENT 原文）**：把「看一眼数据面长什么样」从「写脚本 + 打印数组」变成可操作的东西，同时**不让界面知识渗进内核**：界面只认契约里的 `UiView` / `UiCommand`。
- **它服务哪条硬约束**：`TimelineBasis` 的两轴分离。段级节奏指标必须在 REFERENCE（源时间网格）上算；WARPED（归一化网格）会把抢拍拖拍抹掉。一条画在 WARPED 轴上的曲线若不标出轴含义，读者会把它当成真实时间 —— 于是「练习把所有音都吹在正确时刻」这个**假象**看起来与真的一样。C4 存在的直接目的，就是让轴的含义出现在屏幕上（`render_series_plot` 的 `axis_note` 是冻结文案，见 §4.7）。

### 删掉它会坏掉什么

1. **投影失去人类可读的出口。** `UiProjectionPort.snapshot()` 仍能取出 `UiView`，但没有任何东西把它变成人能看的文本与图；开发者退回「写一次性脚本 print 数组」，`state` / `note` / `scalars` / `series` / `progress` / `error_code` 六个字段无人消费。
2. **6 种意图失去触发入口。** `SET_REFERENCE` / `SET_PRACTICE` / `BUILD_SURFACE` / `RUN_ALGORITHMS` / `CANCEL` / `RESET` 只能手写 Python 调 `submit()`；「界面 → C1」这条链路在真实使用中从未被走通，键名与值类型错位要到接真机时才暴露。
3. **时间轴误读的成本回升。** 轴标注没有强制落点，`timeline_basis` 只活在契约文档里，不在屏幕上。
4. **不变量 F 失去现场证据。** 「C4 可缺席」从一条被反复验证的性质，退回成一句声明。

### 删掉它不会坏掉什么（本文件必须满足的性质）

- C1 的会话机（`HostContract` 的 7 个操作）、C2 的数据面（`AlgorithmDataContract` 的 `manifest` / `read`）、C3 的算法结果，**全部不受影响**：没有任何内核模块 import 本文件，也没有任何内核模块依赖界面概念。
- 机械表述：**删除 `harmonica_eval/cockpit/` 整个目录后，`harmonica_eval` 的其余部分仍须可 import、可运行**；`contract.py` 作为依赖链的根，其 import 不受影响。§8 命令 (4) 给出两条可直接运行的判据。

### 它为什么不得被扩大

每一次「顺手加一个」都是越界：加第 7 个按钮（界面发明内核能力）、把 `error_code` 翻译成修复建议（界面解释算法内部）、给数值配红绿（界面做教学结论）、把曲线平滑一下（界面重算）、写一份会话日志到磁盘（界面持有持久状态）。这些在 §7 逐条列出并禁止。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**（完整清单，多一个都不行）：

- 标准库（逐条，共 15 条；这 15 个模块名加 `contract` 即 `app.py` 允许出现的**全部** import 来源）：
  1. `__future__` —— 只允许 `from __future__ import annotations`。
  2. `os` —— 只允许 `os.path.abspath`、`os.path.isabs`、`os.environ`、`os.getpid`。禁止 `os.system`、`os.remove`、任何写盘调用与 `os.fork`。
  3. `sys` —— 只允许 `sys.stderr`、`sys.stdout`、`sys.exit`、`sys.argv`。
  4. `json` —— 只允许 `json.dumps`、`json.loads`。
  5. `html` —— 只允许 `html.escape`（把 note / detail 原文安全地嵌进 HTML）。
  6. `socket` —— 只允许 `socket.AF_INET`、`socket.SOCK_STREAM`、`socket.socket`、`socket.error`（端口探测）。
  7. `http.server` —— 只允许 `http.server.BaseHTTPRequestHandler`、`http.server.ThreadingHTTPServer`（后者在 Python 3.7+ 存在；本文件不做版本兜底、不回退到 `HTTPServer`）。
  8. `socketserver` —— 只允许 `socketserver.TCPServer.allow_reuse_address`。
  9. `threading` —— 只允许 `threading.Thread`、`threading.Lock`。
  10. `subprocess` —— 只允许 `subprocess.run`（拉起 `osascript` 弹文件框；不设 `timeout`，故不使用 `subprocess.TimeoutExpired`）。
  11. `webbrowser` —— 只允许 `webbrowser.open`。
  12. `typing` —— 只允许 `from typing import Sequence`。
  13. `urllib.parse` —— 只允许 `urllib.parse.urlparse`（校验请求路径，不接受查询串以外的输入）。
  14. `time` —— 只允许 `time.sleep`（轮询周期间隔；`_HTTP_POLL_INTERVAL_SEC = 0.5` 秒）。
  15. `signal` —— 只允许 `signal.signal`、`signal.SIGINT`、`signal.SIGTERM`（把 Ctrl-C 与 SIGTERM 统一归约为 `KeyboardInterrupt` 以走同一条关闭路径；处理器函数 `_raise_keyboard_interrupt` 以 `_` 开头，不进 `__all__`）。

★ `app.py` 的 import 集合因此是 **15 个标准库模块名 + `contract`**，再无第 16 个；§8 命令 (3) 的 `mods <=` 断言按这个集合判定。命令 (2) 的自查脚本另外 import `xml.etree.ElementTree`，那是**脚本**的依赖，不是 `app.py` 的依赖。
- 第三方：**无**。本文件不 import 任何第三方包，尤其不 import `numpy`。
- 本包内：**恰好 6 个符号，全部来自 `..contract`**，写成目标文件里那一行原样：
  `from ..contract import UiCommand, UiCommandKind, UiProjectionPort, UiScalar, UiSeries, UiView`
  （`harmonica_eval/cockpit/__init__.py` 允许 `from .app import ...` 与 `from ..contract import UiProjectionPort`，它不属于本文件的依赖。）

**禁止 import**（逐条列全，任一违反即 §10 第 3 条的 `MOLD BREAK`）：

- 禁止 import `harmonica_eval.core` 的任何模块（含 `core.api`、`core.surface`、`core.ingest`、`core.align`、`core.features`）。
- 禁止 import `harmonica_eval.algorithms` 的任何模块。
- 禁止 import `harmonica_eval.host` 的任何模块。
- 禁止 import `harmonica_eval.profile`。
- 禁止 import `harmonica_eval` 的包根（`import harmonica_eval`）—— 包根可能引入内核模块。
- 禁止 import `harmonica_eval.cockpit` 的其它私建模块（本包只允许 `__init__.py` 与 `app.py`）。
- 禁止 import `contract` 里除上述 6 个符号之外的任何符号，点名禁止：`TimelineBasis`、`SessionState`、`COMMAND_LEGALITY`、`COMMAND_EFFECTS`、`UI_PAYLOAD_KEYS`、`ErrorCode`、`HarmonicaError`、`ContractViolation`、`CoreBuildError`、`AlgorithmError`、`PortDescriptor`、`BufferView`、`SurfaceManifest`、`AlgorithmResultEnvelope`、`AlgorithmDataContract`、`HostContract`、`FORBIDDEN_OPERATIONS`、`CORE_REQUIRED_PORTS`、`FIELD_LAYOUTS`、`CONTENT_HASH_MAGIC`、`UNITS_VOCABULARY`、`AlignmentRepresentation`、`AudioFormat`。
  **需要的语义一律用字符串字面量比较**：`TimelineBasis` 是 `str` 混入枚举，故 `series.timeline_basis == "REFERENCE"` 为 `True`；载荷键名用字面量 `"path"`（与 `contract.py` 的 `UI_PAYLOAD_KEYS` 一致，见 §4.13）。
- 禁止第三方：`numpy`、`scipy`、`librosa`、`matplotlib`、`plotly`、`pandas`、`PyQt5`、`PySide6`、`flask`、`fastapi`、`requests`、`aiohttp`、`soundfile`、`pydub`、`pyaudio`、`sounddevice`、任何其它非标准库包。
- 禁止 `tkinter`、`PyObjC` / `AppKit` / `Foundation`、`pytest`。
- 禁止 `pathlib`、`wave`、`array`、`statistics`、`math`、`random`、`time.time` / `time.monotonic` / `time.strftime`、`uuid`、`platform`、`traceback`、`warnings`、`logging`、`atexit`、`multiprocessing`、`asyncio`、`concurrent.futures`、`queue`、`base64`、`csv`、`re`（正则在本文件无用途，且 `re` 会诱导对 `render_series_plot` 的返回值做字符串加工）。
- 禁止任何形式的**延迟 import 与字符串导入**：`importlib.import_module`、`__import__(...)`、`exec(...)`、`eval(...)`、`compile(...)`、`globals()[...]` 取模块、把模块名拼成字符串再 import —— 全部禁止。禁令覆盖函数体内、`if TYPE_CHECKING:` 块内、`try/except ImportError` 兜底内。
- 禁止用 `subprocess` 拉起内核进程、调试器、`python3` 子进程；`subprocess` 的唯一允许用途是 §4.14 的 `osascript` 文件框。
- 禁止 `open(...)` / `pathlib.Path.write_*` / `os.makedirs` / `tempfile` / `shutil` / `sqlite3` / `pickle` / `logging.FileHandler`：本文件不读盘也不写盘（例外：不读音频，任何情况下都不 open 音频文件）。

★ 本清单**穷举**，不出现「等」「之类」。若实现需要清单外的依赖，按 §10 第 3 条提交 `MOLD BREAK`，不得自行放宽。

---

## 4 · 你要实现什么（行为规格）

### 4.0 总则：界面框架的裁定与冻结常量

**框架裁定（负责人口径，不可推翻）**：C4 是 Mac 端本机视图、只给开发者看。界面框架采用**零第三方依赖**的方案：`http.server.ThreadingHTTPServer` 恒绑 `LOCAL_BIND_HOST`，页面用浏览器的**系统默认浏览器**打开。理由有三条，逐条可查：

1. §3 的第三方清单是**空**的。引入 PyQt / PySide / matplotlib / plotly / flask 都要求修改契约清单，属于 §10 第 3 条的 `MOLD BREAK`，实现者不得自行放宽。
2. 页面是 HTML，故 `render_series_plot` 返回 **SVG 字符串**（格式标签冻结为 `"svg"`），`build_plots` 收集后原样嵌进页面。这满足目标文件 G15 修正的「元素类型随实现者的框架决定，调用方不得对元素做字符串操作」。
3. 目标文件 MUST 原文「UI 框架的选择留给实现者」把**选择权**留给了本规格，本规格在此行使该选择权并写死结论。实现者不再二次选择。

**冻结的模块私有常量**（名字以 `_` 开头，**不得**加入 `__all__`，`__all__` 恰为 14 项）：

| 常量名 | 值 | 含义 |
| --- | --- | --- |
| `_HTTP_PORT_DEFAULT` | `8721` | 首选监听端口（int） |
| `_HTTP_PORT_MAX_PROBES` | `64` | 端口探测上限，探测范围 `8721 ≤ p < 8721 + 64`，即 8721–8784 闭区间 |
| `_PORT_PROBE_TIMEOUT_SEC` | `0.25` | 单个端口的 bind 探测超时（秒，float） |
| `_HTTP_POLL_INTERVAL_SEC` | `0.5` | 轮询线程两次 `snapshot()` 之间的间隔（秒，float） |
| `_HTTP_MAX_VIEW_BYTES` | `1000000` | POST body 字节上限（int） |
| `_SCALAR_VALUE_DECIMALS` | `6` | `render_scalars` 中 value 与 threshold 的小数位数 |
| `_THRESHOLD_DECIMALS` | `6` | 同上，与 value 一致，禁止两处不同 |
| `_PROGRESS_PERCENT_DECIMALS` | `1` | `render_progress` 的百分数小数位数 |
| `_NO_PROGRESS_TEXT` | `"无进度信息"` | `progress is None` 时的整行文案 |
| `_NO_NOTE_TEXT` | `"（无）"` | `note` 去空白后为空时的占位 |
| `_AXIS_NOTE_REFERENCE` | `"REFERENCE（源时间网格：以参考演奏时钟为刻度，抢拍拖拍在此可见）"` | REFERENCE 曲线的轴标注，逐字冻结 |
| `_AXIS_NOTE_WARPED` | `"WARPED（归一化网格：已拉伸到与参考等长，抢拍拖拍已被抹掉）"` | WARPED 曲线的轴标注，逐字冻结 |
| `_AXIS_NOTE_UNKNOWN_FMT` | `"UNKNOWN（{basis!r}，无法判定轴含义）"` | 其余取值的轴标注模板 |
| `_EMPTY_PAYLOAD` | `{}` | 无载荷命令的载荷**形状**说明（每次**新建**空 dict，禁止共享同一个对象；该常量只用于说明形状，或按 §4.13 第 3 步直接写 `{}` 字面量） |
| `_SVG_WIDTH` / `_SVG_HEIGHT` | `720` / `240` | SVG 画布尺寸（像素），viewBox 为 `"0 0 720 240"` |
| `_HTML_CONTENT_TYPE` | `"text/html; charset=utf-8"` | 页面响应的 Content-Type，逐字冻结 |

**全文件唯一的单位换算**：只有一处 —— 比例 → 百分数，`render_progress` 中的 `percent = progress * 100.0`，按 `:.1f` 格式化。**不存在**其它换算：不把秒换成毫秒、不把音分换成 Hz、不把 RMS 换成 dB、不把 sample 换成 frame。任何其它换算都由 C1/C2/C3 完成，界面只显示。

**全文件唯一的阈值**：`_HTTP_MAX_VIEW_BYTES = 1000000`。界面**不设**任何数值告警阈值、容差、合格线 —— `UiScalar.threshold` 是 C1 给的，原样并列显示。

---

### 4.1 `LOCAL_BIND_HOST: str = "0.0.0.0"`

- **输入**：无（模块级常量）。
- **输出**：`str`，值恰为 `"0.0.0.0"`（★ 负责人裁定局域网直连）。
- **算法口径**：字面量赋值，不做任何计算、不读环境变量、不读命令行。
- ★★ 附则（局域网直连）：`0.0.0.0` 是监听地址，**不可直接访问**。故 `run_local_ui` 启动时另调 `_lan_ip()` 探测本机实际 IP，并经 `_access_urls()` 打印「本机回环 + 局域网 IP」两个可点击 URL。★ 只绑 `LOCAL_BIND_HOST` 这条不变量不变。
- **边界**：不适用（常量不可变）。
- **不变量**：本文件**不得**出现字符串 `"0.0.0.0"`、`"::"`、`"localhost"` 作为绑定地址；`_bind()` 的 host 实参恒为 `LOCAL_BIND_HOST`。

### 4.2 `EXIT_OK: int = 0` 与 `EXIT_START_FAILED: int = 2`

- **输入**：无。
- **输出**：`int`，分别为 `0` 与 `2`。
- **口径**：`run_local_ui` 的返回码**只允许**取这两个值；不得出现第三个返回码，也不得返回 `None`。
- **边界**：界面存活期间发生的任何单轮渲染/轮询异常**不改变**最终返回码（仍是 `EXIT_OK`）；只有启动阶段失败才返回 `EXIT_START_FAILED`。

### 4.3 `COMMAND_LABELS: dict[UiCommandKind, str]`

- **输入**：无（模块级常量，键是 `UiCommandKind` 的枚举成员，值是中文文案）。
- **输出**：`dict`，**恰好 6 项**，插入顺序与目标文件一致：
  1. `UiCommandKind.SET_REFERENCE` → `"选择参考演奏"`
  2. `UiCommandKind.SET_PRACTICE` → `"选择练习演奏"`
  3. `UiCommandKind.BUILD_SURFACE` → `"构建数据面"`
  4. `UiCommandKind.RUN_ALGORITHMS` → `"运行算法"`
  5. `UiCommandKind.CANCEL` → `"取消"`
  6. `UiCommandKind.RESET` → `"重置会话"`
- **口径**：逐条穷举 `UiCommandKind` 的成员，不用推导、不用循环生成、不用 `COMMAND_EFFECTS` 这张契约表拼接。这张表就是「没有第 7 个按钮」的可审查证据。
- **边界**：契约将来新增成员时，本表**不自动跟随** —— 缺项会让 `build_command` 的 `assert kind in COMMAND_LABELS` 立即失败（失败点在 §5 表中）。这是刻意的：契约变更必须同步改这里。
- **不变量**：`set(COMMAND_LABELS.keys()) == set(UiCommandKind)`；`len(COMMAND_LABELS) == 6`；所有值互不相同（按钮文案不重复）。

### 4.4 `run_local_ui(port: UiProjectionPort) -> int`

- **输入**：`port` —— 调用方注入的投影端口对象（`UiProjectionPort` 的实现）。取值域：任何具备可调用属性 `snapshot`（`() -> UiView`）与 `submit`（`(UiCommand) -> None`）的对象。**C4 不构造它、不包装它、不复制它**。
- **输出**：`int`，`EXIT_OK` 或 `EXIT_START_FAILED`，二者之一。副作用：占用 `LOCAL_BIND_HOST` 上一个 8721–8784 的 TCP 端口直至返回；向 `sys.stderr` 写启动信息与失败行；拉起系统默认浏览器。
- **口径（启动序列，顺序冻结）**：
  1. **端口形状检查**：`assert hasattr(port, "snapshot") and hasattr(port, "submit")`。不满足 → `AssertionError`。
     ★ **禁止**写 `isinstance(port, UiProjectionPort)`：`UiProjectionPort` 未加 `@runtime_checkable`（契约只声明了 Protocol，未加该装饰器），该写法会抛 `TypeError: Instance and class checks can only be used with @runtime_checkable protocols`，与本规格的失败语义不符。
  2. **选定端口**：令 `p` 依次取 `8721, 8722, …, 8784`（共 `_HTTP_PORT_MAX_PROBES = 64` 个）。对每个 `p` 尝试在 `(LOCAL_BIND_HOST, p)` 上建立 TCP socket 并 `bind`；绑定成功者即为实际端口 `actual_port`，立即释放探测 socket 并把 `actual_port` 交给第 3 步。64 个全部失败 → 见第 11 步的启动失败。
  3. **建服务器**：`ThreadingHTTPServer((LOCAL_BIND_HOST, actual_port), _make_handler(port))`，其中 `allow_reuse_address = True`、`daemon_threads = True`。处理器类由 `_make_handler(port)` 现造，`port` 由**闭包**捕获 —— **不得**为此新增模块级可变全局（INV-401-8 只允许 `_PAGE` 与 `_PAGE_LOCK` 两个）。
  4. **注册退出信号**：`signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)` 与 `signal.signal(signal.SIGINT, _raise_keyboard_interrupt)`，处理器体只做 `raise KeyboardInterrupt`。若 `signal.signal` 抛 `ValueError`（本函数不在主线程）→ 进入第 11 步的启动失败，**不**降级为半可用界面。
  5. **准备全局量**（模块级，不在本函数内新建）：`_PAGE: str`（最近一次渲染的页面）与 `_PAGE_LOCK: threading.Lock`。全文模块级**可变**全局恰这两个；其余模块级名字必须是不可变常量（`str` / `int` / `float` / `dict` 常量表 / `tuple`）。`_PAGE` 的写点只有两处：本函数第 6 步与 §4.16 第 8 步。
  6. **首屏**：在 `_PAGE_LOCK` 内执行 `_PAGE = _render_page(port)`（内部调用 `port.snapshot()` 一次）。
  7. **启动轮询线程**：`threading.Thread(target=_poll_loop, args=(port,), daemon=True).start()`。
  8. **打印 URL**：向 `sys.stderr` 写 `http://127.0.0.1:{actual_port}/`；若 `_lan_ip()` 探测成功，再写 `http://<局域网IP>:{actual_port}/`。（因此 `run_local_ui` 的副作用写的是 **stderr**，不是 stdout。）随后 `webbrowser.open(该 URL)`；`webbrowser.open` 返回 `False` 或抛异常时**忽略**（URL 已在 stderr，手工打开即可），不改变退出码。
  9. **阻塞**：`server.serve_forever()`。
  10. **正常关闭**：捕获 `KeyboardInterrupt` → 只调用 `server.server_close()` → 返回 `EXIT_OK`。**禁止**调用 `server.shutdown()`：`shutdown()` 必须由另一个线程调用，在 `serve_forever()` 所在线程里调用会死锁（`shutdown()` 要等 `serve_forever()` 的循环退出，而循环正被本线程占用）；**禁止** `join()` 轮询线程。
  11. **启动失败**：第 1–8 步中任何异常（含 `AssertionError`、`OSError`、`socket.error`、`ValueError`）→ 向 `sys.stderr` 写**恰好一行** `界面启动失败：{type(e).__name__}: {e}` + 换行 → **不写堆栈**给用户 → 返回 `EXIT_START_FAILED`。已建立的 socket/服务器必须关闭（`server_close()`），不留占用端口。
- **边界**：
  - `port.snapshot()` 抛异常：不属启动失败。发生在首屏时按第 11 步处理；发生在轮询期时按 §4.5 处理。
  - `port` 为 `None`：第 1 步的 `hasattr` 为假 → 启动失败，返回 `EXIT_START_FAILED`。
  - 8721–8784 全被占：启动失败，返回 `EXIT_START_FAILED`（**不**回退到「随机高位端口」，那是实现者的自行选择）。
  - 浏览器不存在：URL 已打印，界面进程继续服务，返回码不变。
- **不变量**：
  - 只绑 `LOCAL_BIND_HOST`；不绑任何其它地址。
  - 界面进程**不**下发任何命令：`run_local_ui` 自身从不调用 `port.submit()`；写路径只存在于 POST `/command` 的请求处理器中。
  - 返回码只取 `EXIT_OK` / `EXIT_START_FAILED`。
  - 退出时**不**发送 `CANCEL`、**不**发送 `RESET`、**不**发送任何「界面断开」通知：`COCKPIT_DETACHED` 在 v0.1 无处产生（契约 G14 注释），且关闭界面顺手毁掉会话会直接违反不变量 F。
  - 不写配置文件、不写日志文件、不读盘。进程退出后本文件不留下任何痕迹。
  - 不在主线程之外的线程里注册信号；不在 `serve_forever()` 的线程里调用 `shutdown()`。
- **不承担**：重启抑制。界面启动失败**跨进程没有共享状态**（落盘被 §7 禁止），故「反复启动失败」只能由发起方 C1 依据退出码 `2` 决定停止重启。本文件只保证退出码及时且明确。

### 4.5 `_poll_loop(port: UiProjectionPort) -> None`（模块私有，不进 `__all__`）

- **输入**：同 §4.4 的 `port`。
- **输出**：无返回值（`None`）。副作用：每轮向全局 `_PAGE` 赋值、必要时向 `sys.stderr` 写失败行。
- **口径**：无限循环，每轮固定做四件事，顺序冻结：
  1. `time.sleep(_HTTP_POLL_INTERVAL_SEC)`（即 0.5 秒）。**先睡后取**，避免与首屏重复渲染。
  2. `view = port.snapshot()`
  3. `_PAGE = _render_page(port)` —— 注意：**重新取快照**，不复用第 2 步的 `view`；这样投影更新的可见延迟 ≤ 1 个轮询周期。对 `_PAGE` 的赋值**必须**在 `_PAGE_LOCK` 内进行（§4.16 第 9 步），且**不得**在锁内调用 `port.snapshot()` / `_render_page()`。
  4. 重复。
- **边界**：
  - 第 2/3 步抛任何异常 → 捕获 `Exception` → 向 `sys.stderr` 写恰好一行 `界面轮询失败：{type(e).__name__}: {e}` + 换行 → **本轮结束，循环继续**。屏幕继续显示上一屏 `_PAGE` 的内容（陈旧但未被伪造），进程不退出、返回码不变。
  - 该异常**不得**被吞掉而不留痕迹：禁止 `except Exception: pass`、禁止计数器静默丢弃、禁止只在第一次打印。
- **不变量**：轮询线程是 `daemon=True`，主线程返回即随之终止；主线程**不得** `join()` 轮询线程（会让关闭变慢或挂住）。轮询线程**不**调用 `port.submit()`。

### 4.6 `_render_page(port: UiProjectionPort) -> str`（模块私有，不进 `__all__`）

- **输入**：同 §4.4 的 `port`。
- **输出**：一个 UTF-8 `str`，是完整的 HTML 文档（首行以 `"<!DOCTYPE html>"` 开头）。
- **口径**：调用 `view = port.snapshot()` **恰好一次**，然后按**冻结顺序**拼接五个区块 + 命令区：
  1. 状态行：`render_status(view)` 的返回值
  2. 标量区：`render_scalars(view.scalars)` 的返回值
  3. 曲线区：`build_plots(view)` 的每一项，**原样**插入（SVG 元素直接嵌入，不转义、不改写）
  4. 进度行：`render_progress(view)` 的返回值
  5. 错误区：`render_error(view)` 的返回值；为空串时**不产出空段落**
  6. 命令区：**恰好 6 个**按钮，按 `COMMAND_LABELS` 的插入顺序，按钮文案逐字取 `COMMAND_LABELS[kind]`，每个按钮带属性 `data-kind="{kind.value}"`（值形如 `SET_REFERENCE`）。点击后向 `POST /command` 发送 JSON `{"kind": "<kind.value>"}`；`SET_REFERENCE` / `SET_PRACTICE` 两个按钮先经 `solicit_asset_uri(kind)`，返回 `None` 时**不发请求、不下发命令**，否则发送 `{"kind": "...", "path": "<路径>"}`。
  - 所有来自 `view` 的文本（`note`、`label`、`unit`、`error_detail`）嵌入 HTML 前必须经 `html.escape(..., quote=True)`；**SVG 元素是例外，原样插入**。
  - 区块 2–5 的文本必须按 `<pre>`（或等价的不折叠空白元素）呈现：`render_*` 返回的 `\n` 与行内空格是规格的一部分，不得被 HTML 折叠掉。
- **边界**：`view.series` 为空 → 曲线区只有空容器，不产出 `<svg>`。`render_error` 返回空串 → 不产出该区块的容器元素。`port.snapshot()` 抛异常 → 向上传播（由 §4.4 第 11 步或 §4.5 归约）。
- **不变量**：页面里 `data-kind="X"` 的取值集合**恰好**是 `{k.value for k in UiCommandKind}`（6 个，无第 7 个入口，也没有自由格式的命令输入框）。页面不含任何 `<script src="http...">` 外部资源引用。渲染不重算任何数值（§4.7–§4.10 各自的口径即为全部计算）。

### 4.7 `render_series_plot(series: UiSeries) -> object`

- **输入**：`series: UiSeries`（`contract.UiSeries`）。字段与取值域：
  - `key: str`（稳定标识）
  - `label: str`（中文短名）
  - `t: Sequence[float]` —— 时间轴，单位**秒**，长度与 `values` 相同
  - `values: Sequence[float]` —— 曲线值，单位见 `unit`
  - `unit: str` —— 纵轴单位，取值来自 `UiScalar.unit` 的词表 `'cents' / 'ms' / 'db' / 'ratio' / ''`
  - `timeline_basis` —— `TimelineBasis` 成员；`TimelineBasis` 是 `str` 混入枚举，故与字面量 `"REFERENCE"` / `"WARPED"` 直接比较成立
  - `source_port: str | None` —— 仅作追溯字段原样展示
- **输出**：`object`，**本规格冻结为 `str`**：格式标签 `"svg"`，一个格式良好的 XML 片段，根元素
  `<svg xmlns="http://www.w3.org/2000/svg" width="720" height="240" viewBox="0 0 720 240">`。
  返回类型标注保持目标文件的 `object`（G15 修正），实现返回 `str`，调用方不依赖具体类型。
  SVG 内容由**四类元素**组成：四个标注 `<text>`（`source_port` 非 `None` 时为五个）、一个注释 `<!-- omitted: k -->`、零到多个 `<polyline>`，以及根元素本身。**不产出**任何其它元素（无 `<rect>`、无 `<line>`、无 `<circle>`、无 `<g>`、无 `<style>`、无 `<script>`）。
- **算法口径（逐步骤，可复现同一字符串）**：
  1. **轴标注（不可省）**：`basis = series.timeline_basis`。文本节点 `axis_note` 取：
     - `basis == "REFERENCE"` → `_AXIS_NOTE_REFERENCE` 的逐字文案
     - `basis == "WARPED"` → `_AXIS_NOTE_WARPED` 的逐字文案
     - 其它任何值 → `_AXIS_NOTE_UNKNOWN_FMT.format(basis=basis)`，即 `UNKNOWN（'<原值>'，无法判定轴含义）`（用 `repr` 保留引号）
     `axis_note` 必须以 `<text x="0" y="254">` 出现在 SVG 中。**这条不可省**：轴不标出来，读者会把 warped 轴上的图当成真实时间而误读节奏。
  2. **横轴标注**：文本节点 `"时间（秒）"`，以 `<text x="0" y="236">` 出现。
  3. **纵轴单位标注**：文本节点取 `series.unit` 的**原文**，以 `<text x="0" y="20">` 出现；`unit` 为空串时写文本节点 `（无单位）`（四个字加全角括号）。
  4. **标题标注**：文本节点 `f"{series.label} [{series.key}]"`，以 `<text x="0" y="272">` 出现；`source_port is not None` 时另加文本节点 `f"source_port={series.source_port}"`（原样，不解释语义）。
  5. **注释标注**：`<!-- omitted: {k} -->` 写在所有 `<text>` **之后**、`</svg>` 之前。`k` = 非有限点的个数（把连续有限点切成若干段时，非有限值即切点；全为有限值时 `k = 0`）。
  6. **数据长度校验**：`assert len(series.t) == len(series.values)`，不满足 → `AssertionError`。令 `n = len(series.t)`。
  7. **横坐标**：`n == 0` 时不输出折线；`n == 1` 时横坐标 `x_0 = 0.0`；`n >= 2` 时 `x_i = 720.0 * i / (n - 1)`，`i = 0 … n-1`。
  8. **非有限值处理**：`v_i` 非有限（`v_i != v_i` 为 NaN，或 `v_i` 为 `±inf`）时该点**从折线中剔除**，相邻有限点之间**不连线**；剔除数量即第 5 步的 `k`。
  9. **纵坐标归一化**：令 `F = {v_i : v_i 有限}`，`lo = min(F)`，`hi = max(F)`（集合为空时跳过本步与第 10 步）。
     - `hi == lo` → 所有有限点纵坐标 `y_i = 120.0`（画布垂直中线）
     - 否则 `y_i = 232.0 - 224.0 * (v_i - lo) / (hi - lo)`，即 `lo` → `232.0`（底部），`hi` → `8.0`（顶部）
     - 纵轴**不**做绝对值映射、**不**做对数映射、**不**做单位换算
  10. **折线输出**：把连续有限点切成若干段，每段长度 ≥ 2 时输出一个 `<polyline fill="none" stroke="#333" stroke-width="1" points="x,y x,y …"/>`（坐标按 `f"{v:.3f}"` 格式化，点之间一个空格），同一段内的点按原顺序。长度恰为 1 的段不输出折线，也不输出任何 `<circle>` 或其它元素。剔除后总点数 < 2 → 不输出任何 `<polyline>`，其余标注照常输出。
  11. **不重采样、不插值、不平滑、不抽稀**：`t` 与 `values` 按给定顺序逐点使用，输出的点数等于有限点数。
  12. **不解释算法来源**：`source_port` 只作为文本原样展示；不写出「来自 XXX 算法」这类推断；不把 `key` 拆成算法名与端口名。
  13. **不排序、不去重**：同一 `t` 出现两次时按给定顺序画两次，不合并、不去重。
- **边界**：
  - `n == 0`（空 `t` / `values`）→ 返回**合法 SVG**，含全部 `<text>` 标注与 `<!-- omitted: 0 -->`，**无** `<polyline>`；不抛异常。
  - `n == 1` → 返回合法 SVG；横坐标 `0.0`；因单点段不连线，可无 `<polyline>`；不抛异常。
  - `values` 全为 NaN → `F` 为空 → `k = n`、无 `<polyline>`；不抛异常。
  - 单个 NaN 夹在两个有限点之间 → 该 NaN 剔除，左右两点**不连线**（两个单点段，故无可视折线）。
  - `hi == lo`（如 `values` 全为 `440.0`）→ 全部有限点 `y = 120.0`，照常输出折线。
  - `unit == ""` → 纵轴文本为 `（无单位）`。
  - `timeline_basis` 为未知字符串 → `axis_note` 走 `_AXIS_NOTE_UNKNOWN_FMT`，**不抛异常、不静默按 REFERENCE 处理**。
- **不变量**：
  - 输出**必含**与 `series.timeline_basis` 对应的轴标注文案；REFERENCE 与 WARPED 的文案互不为子串（`"源时间网格"` 与 `"归一化网格"` 互不包含，`"REFERENCE"` 与 `"WARPED"` 互不包含），故可用子串断言唯一判定。
  - `source_port is None` 时输出**不含** `"source_port="`；`source_port` 非 `None` 时输出**必含** `f"source_port={series.source_port}"`。
  - 输出**必含** `<!-- omitted: {k} -->`，`k` 等于非有限点个数。
  - 输出是格式良好的 XML（可被 `xml.etree.ElementTree.fromstring` 解析）。
  - 同一输入两次调用返回**逐字相同**的字符串（无时间戳、无随机 id、无字典迭代顺序依赖）。
  - 四个 `<text>` 节点（`source_port` 非 `None` 时五个）与其内容由本规格冻结；坐标与字号属表现层，除 §4.7 指定的 `x` / `y` 与折线坐标公式外不由本规格约束。
  - 本函数不访问 `port`、不发命令、不写盘。

### 4.8 `render_status(view: UiView) -> str`

- **输入**：`view: UiView`。使用字段：`session_id: str`、`state: SessionState`（6 值：`CREATED` / `INPUT_READY` / `BUILDING` / `DATA_READY` / `FAILED` / `CLOSED`）、`note: str`。
- **输出**：**一行** `str`，不含换行，模板逐字冻结：
  `f"会话 {session_id} | 状态 {state} | 说明 {note_text}"`
  其中分隔符是「空格 + 竖线 + 空格」。
- **算法口径**：
  1. `session_id` 取 `view.session_id` 原文；`assert "\n" not in session_id and "\r" not in session_id and "|" not in session_id`，不满足 → `AssertionError`（分隔符不能被 id 破坏）。
  2. `state` 用 `f"{view.state}"`，即枚举的**值**而非名字：`SessionState.DATA_READY` 输出 `DATA_READY`。**不翻译**：不得输出「数据已就绪」「构建中」这类中文映射，也不得把 `BUILDING` 显示成「进度 3/5」这种推断。
  3. `note_text`：取 `view.note` 原文 → 把 `\n` 与 `\r` 各替换为一个半角空格 → 去掉首尾空白（`strip()`）→ 结果为空串时用 `_NO_NOTE_TEXT`（即 `（无）`）。
- **边界**：
  - `note == ""`（默认值）→ `说明 （无）`。
  - `note` 含换行 → 折成空格，输出仍是单行。
  - `session_id == ""` → 原样输出，得到 `会话  | 状态 …`（两个空格），不报错、不替换。
  - `state` 不是 6 个值之一（不可能由契约产生）→ `f"{view.state}"` 原样输出，**不抛异常、不静默映射**。
  - 不涉及 NaN：本函数不处理浮点。
- **不变量**：返回值恰含两个 `" | "`；不含 `"\n"`；不含「进度」「%」「合格」「建议」「超标」「通过」六类词。

### 4.9 `render_scalars(scalars: Sequence[UiScalar]) -> str`

- **输入**：`scalars: Sequence[UiScalar]`，可为空序列、可为 tuple/list。每个元素的字段：`key: str`、`label: str`（中文短名）、`value: float`、`unit: str`（`'cents' / 'ms' / 'db' / 'ratio' / ''`）、`threshold: float | None`（`None` = 纯陈述、无判定）。
- **输出**：`str`。空输入 → **零长度字符串** `""`（无占位文案、无换行）。非空 → 每个标量一行，用 `"\n"` 连接，**行尾不带换行**。
- **算法口径（每行模板，逐字冻结）**：
  - `threshold is None` 且 `unit != ""` → `f"{label}：{value_str} {unit}"`
  - `threshold is None` 且 `unit == ""` → `f"{label}：{value_str}"`（**不**留尾随空格）
  - `threshold is not None` 且 `unit != ""` → `f"{label}：{value_str} {unit}（阈值 {thr_str} {unit}）"`
  - `threshold is not None` 且 `unit == ""` → `f"{label}：{value_str}（阈值 {thr_str}）"`
  其中 `value_str = f"{value:.{_SCALAR_VALUE_DECIMALS}f}"`（6 位小数）、`thr_str = f"{threshold:.{_THRESHOLD_DECIMALS}f}"`（6 位小数）；冒号是全角 `：`，括号是全角 `（）`。
  - 顺序：**严格按 `scalars` 给定顺序逐行输出**。不排序（不按 `key` 排、不按 `label` 排、不按数值大小排）、不去重、不合并同类项、不做求和/均值/最值等任何统计。
  - **只陈述数值**：不判定合格与否、不配色成红绿、不写「超标」「正常」「建议」、不下教学结论（SPEC §3）。
  - `threshold` 存在时**并列**展示（同一行、括号内），让读者自己对照；`threshold is None` 时**不得**自行补一个默认阈值。
- **边界**：
  - `scalars == ()` / `[]` → 返回 `""`。
  - `value = 0.0` → `0.000000`；`value = -0.0` → `-0.000000`（保留符号，不归一化）。
  - `value = float("nan")` → 字面量 `nan`（不拦截、不替换成 0、不抛异常）。
  - `value = float("inf")` / `float("-inf")` → 字面量 `inf` / `-inf`。
  - `threshold = 0.0` → 走「阈值存在」分支（判据用 `is not None`，**不用真值判断**），输出 `（阈值 0.000000 …）`。
  - `label == ""` → 行以 `：` 开头（如 `：12.500000 cents`），不报错、不替换。
  - `unit` 非上述词表值 → 原样输出，不校验。
- **不变量**：输出行数恰等于 `len(scalars)`（空序列时为 0 行）；对每个有限 `value`，`f"{value:.6f}"` 逐字出现在对应行内；输出中不出现 `"OK"`、`"合格"`、`"不合格"`、`"通过"`、`"超标"`、`"建议"` 六个词中的任何一个。

### 4.10 `render_progress(view: UiView) -> str`

- **输入**：`view: UiView`，只用 `progress: float | None`。取值域由契约冻结：`0.0–1.0` 为比例（**不是**百分数），`None` 表示该会话没有进度概念。
- **输出**：**一行** `str`，不含换行。
- **算法口径（全文件唯一的单位换算）**：
  - `view.progress is None` → 返回 `_NO_PROGRESS_TEXT`，逐字为 `"无进度信息"`。**不得**从 `view.state` 推断百分比、**不得**自行估算、**不得**显示 0%。
  - 否则 `percent = view.progress * 100.0`，返回 `f"构建进度 {percent:.{_PROGRESS_PERCENT_DECIMALS}f}%"`（1 位小数）。
  - **不做归一化**：不 `min(1.0, …)`、不 `max(0.0, …)`、不 `round` 到整百分比、不判是否越界。
  - 判据用 `is None`，**不用真值判断**：`progress = 0.0` 走换算分支，输出 `构建进度 0.0%`。
- **边界（逐例冻结，可直接断言）**：
  | `view.progress` | 返回值 |
  | --- | --- |
  | `None` | `无进度信息` |
  | `0.0` | `构建进度 0.0%` |
  | `0.125` | `构建进度 12.5%` |
  | `0.625` | `构建进度 62.5%` |
  | `0.999` | `构建进度 99.9%` |
  | `1.0` | `构建进度 100.0%` |
  | `1.5` | `构建进度 150.0%` |
  | `-0.25` | `构建进度 -25.0%` |
  | `float("nan")` | `构建进度 nan%` |
  | `float("inf")` | `构建进度 inf%` |
- **不变量**：`progress is None` 时输出**不含** `%` 字符；`progress is not None` 时输出**必含** `%` 字符；本函数不读 `view.state`、不读 `view.series`、不读 `view.scalars`。

### 4.11 `render_error(view: UiView) -> str`

- **输入**：`view: UiView`，只用 `error_code: str | None` 与 `error_detail: str | None`。
- **输出**：`str`，无错误时为**空串** `""`。
- **算法口径**：
  - `error_code is None and error_detail is None` → 返回 `""`（**不**显示「无错误」占位）。
  - 否则第一行为 `f"错误 {error_code if error_code is not None else '（无）'}"`；`error_detail is not None` 时追加 `"\n"` + `error_detail` **原文**（保留其内部换行，不折叠、不转义、不截断）。
  - 判据全部用 `is not None`：`error_code == ""` 视为「有值」，第一行为 `"错误 "`（「错误」后跟一个空格），**不**替换成 `（无）`。
  - 只展示 C1 归一化后的错误码与细节：**不打印堆栈**（输出中不得出现 `Traceback`、`File "`、`.py`）、**不推测原因**、**不给修复建议**、**不区分错误归属**（哪个组件失败是 C1/C2/C3 的内部语义）。
- **边界**：
  - 两者皆 `None` → `""`。
  - `error_code` 有值、`error_detail is None` → 单行 `错误 <code>`。
  - `error_code is None`、`error_detail` 有值 → `错误 （无）\n<detail>`。
  - `error_detail == ""` → 追加一个空行，得到 `错误 <code>\n`（保留尾随换行，不 strip）。
  - 全是空串（`""` / `""`）→ `错误 \n`（第一行尾随空格 + 换行 + 空行）。
- **不变量**：返回 `""` 当且仅当两个字段都是 `None`；除 `error_detail` 的**原样回显**之外，本函数不产生任何自己的文本：输出中不含 `请`、`建议`、`可能是`、`原因` 四个词（若这些词出现在 `error_detail` 里，属原样回显，界面不加工、不识别）。

### 4.12 `build_plots(view: UiView) -> Sequence[object]`

- **输入**：`view: UiView`，只用 `view.series: Sequence[UiSeries]`。
- **输出**：`list`（**不是** tuple），长度恰等于 `len(view.series)`，与 `view.series` **同序**，第 `i` 个元素恒等于 `render_series_plot(view.series[i])` 的返回值。`view.series` 为空 → 返回 `[]`。
- **算法口径**：`return [render_series_plot(s) for s in view.series]`。每条曲线**逐一**交给 `render_series_plot`，时间轴标注在单条曲线内完成（不在本函数里合并）。
- **边界**：
  - `view.series == ()` → 返回 `[]`，**不报错、不造图、不产出占位图**。
  - 单条曲线 → 长度 1 的 `list`。
  - `render_series_plot` 抛 `AssertionError`（如 `len(t) != len(values)`）→ **原样向上传播**，不捕获、不跳过该条、不返回部分结果。
- **不变量**：
  - **只读**：本函数不修改 `view`、不修改 `view.series` 的任何元素、不写盘、不调用 `port`、不触发任何 C1 侧行为。
  - **不得对元素做字符串操作**：禁止 `"".join(...)`、`.format(...)`、`+` 拼接、切片、正则、`str(...)` 施加在 `render_series_plot` 的返回值上（G15 修正）。元素类型由实现者的框架决定，本函数只做原样收集。
  - 元素之间**不合并**：不得把两条同 `timeline_basis` 的曲线合进一张图（合并是 `_render_page` 的展示层选择，不在本函数内做）；**尤其禁止**把不同 `timeline_basis` 的曲线画在同一张图上（契约 `UiSeries.timeline_basis` 的裁定）。

### 4.13 `build_command(kind: UiCommandKind, payload: dict | None = None) -> UiCommand`

- **输入**：
  - `kind` —— 只能取 `UiCommandKind` 的 6 个成员之一：`SET_REFERENCE` / `SET_PRACTICE` / `BUILD_SURFACE` / `RUN_ALGORITHMS` / `CANCEL` / `RESET`。
  - `payload: dict | None` —— 键名由契约 `UI_PAYLOAD_KEYS`（G7 冻结表）唯一确定：`SET_REFERENCE` 与 `SET_PRACTICE` 为 `("path",)`，其余 4 个成员为 `()`。
- **输出**：`UiCommand` 实例（冻结 dataclass）。返回值满足：
  - `command.kind is kind`
  - `command.payload` 是**新建**的 `dict`：`SET_*` 时为 `{"path": <路径原文>}`，其余 4 个成员时为 `{}`
- **算法口径（恒等映射，逐分支冻结）**：
  1. `assert kind in COMMAND_LABELS`，不满足 → `AssertionError`（含未知成员与非枚举值两种情况）。
  2. `expected = ("path",) if kind in (UiCommandKind.SET_REFERENCE, UiCommandKind.SET_PRACTICE) else ()`。
  3. `expected == ()` 分支：`payload` 必须是 `None` **或**空 `dict`；否则 `AssertionError`。返回 `UiCommand(kind=kind, payload={})`（新建空 dict，**不**复用 `_EMPTY_PAYLOAD` 同一个对象，避免调用方后续写入污染后续命令）。
  4. `expected == ("path",)` 分支：`payload` 必须是 `dict`，且 `set(payload.keys()) == {"path"}`（缺 `path` 或多出任何键都是 `AssertionError`）；`path = payload["path"]` 必须满足 `isinstance(path, str)`、`len(path) > 0`、`"\x00" not in path`，任一不满足 → `AssertionError`。返回 `UiCommand(kind=kind, payload={"path": path})`。
  5. **路径原样保留**：不调用 `os.path.abspath`、不做 `normpath`、不展开 `~`、不去首尾空白、不做 URL 解码。界面不自造业务字段，`payload` 只装调用方已经拿到的东西。
  6. **不校验业务合法性**：不判文件是否存在、不判是否绝对路径、不判扩展名、不判是否可解码、不判大小。不可读由 C1/C2 归一化为错误码后回显。
  7. **不预判状态**：界面**不**读 `view.state`、**不**查 `COMMAND_LEGALITY`、**不**因状态不合法而拒绝构造命令。命令是否被接受由 C1 决定（界面不做「尽力而为」的补救）。
- **边界**：
  - `kind = UiCommandKind.SET_REFERENCE`、`payload = None` → `AssertionError`（缺必需键）。
  - `kind = UiCommandKind.SET_REFERENCE`、`payload = {"path": ""}` → `AssertionError`（空路径）。
  - `kind = UiCommandKind.SET_REFERENCE`、`payload = {"path": "/tmp/a.wav", "extra": 1}` → `AssertionError`（多余键，**不静默丢弃**）。
  - `kind = UiCommandKind.BUILD_SURFACE`、`payload = {"path": "/tmp/a.wav"}` → `AssertionError`（无载荷成员不得带载荷，**不静默丢弃**）。
  - `kind = "SET_REFERENCE"`（裸字符串而非枚举成员）→ `AssertionError`。**禁止**在函数内做 `UiCommandKind(kind)` 强制转换来「宽容」处理。
  - `kind = None` → `AssertionError`。
- **不变量**：返回值的 `payload` 与入参 `payload` **不共享对象**（`command.payload is not payload`）；返回值与 `UiCommand(kind=kind, payload=期望载荷)` **相等**（冻结 dataclass 的值相等）；本函数不调用 `port`、不读 `view`、不下发命令。

### 4.14 `solicit_asset_uri(kind: UiCommandKind) -> str | None`

- **输入**：`kind` —— 只能是 `UiCommandKind.SET_REFERENCE` 或 `UiCommandKind.SET_PRACTICE`（其余成员无载荷，调用即错误）。
- **输出**：`str | None`。成功 → **绝对路径字符串**；用户取消 → `None`。
- **算法口径（Mac 本机，逐步骤冻结）**：
  1. `assert kind in (UiCommandKind.SET_REFERENCE, UiCommandKind.SET_PRACTICE)`，不满足 → `AssertionError`。
  2. 用 `subprocess.run` 调起 `osascript`，实参逐字：
     `argv = ["osascript", "-e", 'POSIX path of (choose file with prompt "选择音频文件")']`
     `capture_output=True`、`text=True`、**不设 timeout**（`timeout=None`）。对话框是模态的，阻塞直到用户回答或系统取消，这是正确语义；不设超时也就**不存在** `TimeoutExpired` 这条路径。
  3. `completed.returncode != 0`（用户点了取消，osascript 非零退出）→ 返回 `None`。
  4. `returncode == 0` 时取 `completed.stdout.strip()`（去掉尾随换行与首尾空白）。结果为空串 → 返回 `None`（与取消同解，不产生半条意图）。
  5. 结果非空 → `assert os.path.isabs(path)`，不满足 → `AssertionError`（`POSIX path of` 在本机必返回以 `/` 开头的路径；不是则说明环境异常，**不**自行补前缀）。随后 `path = os.path.abspath(path)`（幂等归一化），返回 `path`。
  6. `subprocess.run` 抛 `OSError`（`osascript` 不存在 / 非 macOS / 无 GUI 会话）→ 捕获后 `assert False, "..."`，即抛出带说明的 `AssertionError`。**不**回退到「让用户手敲路径」的替代交互（那是发明新能力）。
- **边界**：
  - 用户取消 → `None`，且**不下发任何命令**（本函数不调用 `build_command`、不调用 `submit_command`，也不返回半条意图对象）。
  - 用户选了文件 → 返回绝对路径；**只取路径字符串，不打开、不读取、不解码音频**：本函数不调用 `open()`、不读文件头、不判扩展名、不判大小、不判可解码性。
  - `kind = UiCommandKind.CANCEL` / `RESET` / `BUILD_SURFACE` / `RUN_ALGORITHMS` → `AssertionError`。
  - 路径含空格或中文 → 原样返回，不做转义、不做 URL 编码。
- **不变量**：返回值要么是 `None`，要么是 `os.path.isabs(...)` 为真的非空字符串；本函数不读盘、不写盘、不 import 任何内核模块；返回值可直接作为 §4.13 的 `payload={"path": 该值}` 使用。

### 4.15 `submit_command(port: UiProjectionPort, command: UiCommand) -> None`

- **输入**：`port` —— C1 注入的 `UiProjectionPort`（须具备可调用的 `submit`）；`command` —— 由 `build_command` 构造的 `UiCommand`（6 种意图之一）。
- **输出**：`None`（字符串 `"None"` 的 `None`，即无返回值）。副作用：**恰好一次** `port.submit(command)`。
- **算法口径（逐步骤冻结）**：
  1. `assert isinstance(command, UiCommand)`，不满足 → `AssertionError`（**不**做鸭子类型宽容：非契约对象一律拒绝）。
  2. `assert command.kind in COMMAND_LABELS`，不满足 → `AssertionError`（6 种之外无路径，没有自由格式的命令入口）。
  3. `expected_keys = ("path",) if command.kind in (UiCommandKind.SET_REFERENCE, UiCommandKind.SET_PRACTICE) else ()`；`assert set(command.payload.keys()) == set(expected_keys)`，不满足 → `AssertionError`（缺失或多余键）。
  4. `expected_keys` 非空时：`assert isinstance(command.payload["path"], str) and len(command.payload["path"]) > 0`，不满足 → `AssertionError`。
  5. `port.submit(command)` —— **唯一写路径**。调用恰好一次。
- **边界**：
  - `port.submit` 自身抛异常（C1 拒绝命令或 C1 崩溃）→ **不捕获、原样向上传播**。**不**重试、**不**排队、**不**缓存、**不**做乐观更新、**不**伪造「已生效」。落到 HTTP 层时由请求处理器归约为 `500 internal error`（§4.16 第 7 步），其余情形见 §5 表。
  - **本函数不主动调用 `port.snapshot()`**：界面状态只由轮询循环（§4.5）与 POST `/command` 的响应刷新（§4.16 第 8 步），于是「命令被拒绝」在屏幕上的表现与「命令已生效但状态未变」**完全一致** —— 这正是「如实反映、不伪造」的结构保证。
  - `command` 为 `None` / dict / 字符串 → `AssertionError`（第 1 步）。
- **不变量**：
  - `port.submit` 被调用**恰好一次**（不多、不少）。
  - 除 `port.submit` 外**不访问** `port` 的任何其它属性/方法；**不**访问 C1/C2/C3 的任何对象；**不** import 内核模块。
  - 不在界面侧保存 `command`（无队列、无历史、无重放缓冲）：函数返回后本进程除轮询用的投影外不持有该命令。
  - 界面侧**无第 7 种意图路径**：没有任何接受自由格式字符串的命令入口（见 `COMMAND_LABELS`）。

---

### 4.16 请求处理器 `_make_handler(port) -> type` 与 `_Handler`（模块私有，不进 `__all__`）

- **输入**：`_make_handler(port)` 接收同 §4.4 的 `port`；返回一个 `BaseHTTPRequestHandler` 子类（本规格称 `_Handler`），`port` 以闭包方式被该类捕获。服务器的每个请求线程使用**同一个** `_Handler` 类，故同一次界面会话里所有请求看到同一个 `port`。
- **输出**：HTTP 响应。副作用：POST `/command` 合法时调用 `build_command` 与 `submit_command`（即全文件唯一的写路径）。
- **路由与口径（逐条冻结）**：
  | 方法 | 路径 | 行为 |
  | --- | --- | --- |
  | GET | `/` | `200`，`Content-Type: text/html; charset=utf-8`，响应体为 `_PAGE`（`_render_page` 的最新结果） |
  | GET | 其它路径 | `404`，响应体逐字 `not found` |
  | POST | `/command` | 见下方命令处理口径 |
  | POST | 其它路径 | `404`，响应体逐字 `not found` |
  | PUT / DELETE / PATCH / 其它 | 任意 | `405`，响应体逐字 `method not allowed` |
- **POST `/command` 命令处理口径（顺序冻结）**：
  1. `assert path == "/command"`（否则走上表的 404）。
  2. 读 `Content-Length`。为 `None`、不是十进制整数、`<= 0`、或 `> _HTTP_MAX_VIEW_BYTES`（1000000）→ `400`，响应体逐字 `bad request`，**且不调用 `port.submit()`**。
  3. 读满 `Content-Length` 字节。不是合法 UTF-8 → `400` + `bad request`。
  4. `json.loads` 失败 → `400` + `bad request`；解析结果不是 `dict` → `400` + `bad request`。
  5. `data.get("kind")` 必须是 `str`，且取值属于 `{k.value for k in UiCommandKind}`（6 个字符串）→ 否则 `400` + `bad request`，**不**调用 `port.submit()`。
  6. `kind = UiCommandKind(data["kind"])`；`payload = {"path": data["path"]} if "path" in data else None`。
  7. `cmd = build_command(kind, payload)`；`submit_command(port, cmd)` —— **必须**复用这两个公开函数，不得在处理器内自己拼 `UiCommand`、也不得自己调 `port.submit`（否则 §8 命令 (3) 的「`submit` 调用恰 1 处」判据会失败，INV-401-4 随之失败）。
  8. 响应 `200`，`Content-Type: text/html; charset=utf-8`，响应体为 `_PAGE = _render_page(port)`（`snapshot()` 只在此处被调用一次，用于本次响应）。
  9. **写 `_PAGE` 前必须取得 `_PAGE_LOCK`**（`threading.Lock`），因为轮询线程与请求线程都会写它；读 `_PAGE`（GET `/`）时同样加锁后取值到局部变量再写响应。锁内只做「读/写一个 `str` 引用」，**不得**在锁内调用 `port.snapshot()` / `_render_page()` / `port.submit()`（避免请求线程与轮询线程互相阻塞，也避免持锁跨越可能失败的调用）。`_PAGE_LOCK` 是**普通锁**，锁内不得再取同一把锁；`_poll_loop` 取锁时**不得**使用阻塞等待之外的任何取锁方式（`acquire(blocking=False)` 这种「取不到就跳过」是静默降级，禁止）。
- **边界**：
  - 非法输入（第 2–5 步任一）→ 一行**固定**的 `400` 响应，不回显用户输入、不暴露 Python 异常消息、不打印堆栈给浏览器。向 `sys.stderr` 允许写一行说明。
  - `build_command` / `submit_command` 抛 `AssertionError`（界面自身缺陷）或 `port.submit` 抛异常 → 响应 `500`，响应体逐字 `internal error`，向 `sys.stderr` 写一行 `界面命令失败：{type(e).__name__}: {e}`。**不**吞、**不**重试。
  - 请求带查询串（如 `/command?x=1`）→ 以 `urlparse` 的 `path` 分量匹配路由，查询串被忽略。
  - 响应**不**设置任何 Cookie、**不**回显请求头、**不**做 CORS 头。
- **不变量**：全文件调用 `port.submit()` 的位置**有且仅有**本处理器第 7 步；`_PAGE` 的更新**只允许**是单条 `_PAGE = _render_page(port)` 赋值（不得就地 `+=` / `.append`）；服务器使用 `ThreadingHTTPServer` 且 `daemon_threads = True`；`_Handler` 不持有除 `port` 闭包与 `_PAGE` / `_PAGE_LOCK` 之外的进程级状态。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| `port` 缺 `snapshot` 或 `submit` 属性（含 `port is None`） | 显式失败，启动阶段终止 | 抛 `AssertionError`；被 `run_local_ui` 归约为 `界面启动失败：AssertionError: …` 一行 stderr，返回 `EXIT_START_FAILED`（2） |
| `LOCAL_BIND_HOST` 上 8721–8784 共 64 个端口全部 bind 失败 | 显式失败，启动阶段终止 | 抛 `OSError`；归约为一行 stderr，返回 `EXIT_START_FAILED`（2）。**不**重试、**不**改用随机端口、**不**降级为「无界面模式」 |
| `signal.signal` 抛 `ValueError`（非主线程） | 显式失败，启动阶段终止 | 同上：一行 stderr + 返回 `EXIT_START_FAILED`（2）。**不**降级为半可用界面 |
| 首屏 `_render_page` 内部 `port.snapshot()` 抛异常 | 显式失败，启动阶段终止 | 归约为一行 stderr，返回 `EXIT_START_FAILED`（2）。**不**显示空白页面冒充成功 |
| 轮询线程内 `port.snapshot()` 抛异常 | **降级**（两处允许降级之一），且必须留痕 | 捕获 `Exception`，向 stderr 写一行 `界面轮询失败：{type(e).__name__}: {e}`；屏幕保留上一屏内容；循环继续；进程不退、退出码不变 |
| `webbrowser.open` 返回 `False` 或抛异常 | **降级**（有替代路径：URL 已打印在 stderr） | 忽略；不改变退出码 |
| 用户按 Ctrl-C / 进程收到 SIGTERM | 正常关闭 | 捕获 `KeyboardInterrupt` → `server_close()` → 返回 `EXIT_OK`（0）。**不**下发 `CANCEL` / `RESET` |
| `render_series_plot` 收到 `len(series.t) != len(series.values)` | 显式失败，**不**截断到较短者 | 抛 `AssertionError`；向上传播到 `build_plots` → `_render_page` → 归约为启动失败（首屏）或轮询失败一行（轮询期） |
| `render_status` 收到含 `\n` / `\r` / `|` 的 `session_id` | 显式失败，**不**转义后照常输出 | 抛 `AssertionError`（分隔符不得被 id 破坏） |
| `render_series_plot` 收到未知的 `timeline_basis` 取值 | 显示为 `UNKNOWN（'<原值>'，无法判定轴含义）` | 不抛异常、**不**静默按 `REFERENCE` 处理（静默按 REFERENCE 处理就是伪造轴含义） |
| `render_progress` 收到 `progress is None` | 显示 `无进度信息` | 不抛异常、**不**从 `state` 推断百分比 |
| `render_progress` 收到越界值（`1.5` / `-0.25`） | 原样换算显示（`150.0%` / `-25.0%`） | 不抛异常、**不**截断到 `0–100%`（截断即静默改写 C1 的错误） |
| `render_scalars` 收到 `value = NaN` | 原样输出字面量 `nan` | 不抛异常、**不**替换为 `0`、**不**跳过该行 |
| `render_scalars` 收到空序列 | 返回空串 | 返回 `""`，**不**显示「无指标」占位 |
| `render_error` 两个字段皆 `None` | 返回空串 | 返回 `""`，**不**显示「无错误」占位 |
| `build_plots` 收到 `view.series == ()` | 返回空列表 | 返回 `[]`，不报错、**不**造占位图 |
| `build_command` 收到 6 种之外的 `kind`（含裸字符串、`None`） | 显式失败 | 抛 `AssertionError`。**禁止** `UiCommandKind(kind)` 强制转换来宽容处理 |
| `build_command` 收到 `SET_REFERENCE` + `payload=None`（缺 `path`） | 显式失败 | 抛 `AssertionError` |
| `build_command` 收到无载荷成员 + 非空 `payload` | 显式失败，**不**静默丢弃多余键 | 抛 `AssertionError` |
| `build_command` 收到 `payload` 含未冻结键（如 `extra`） | 显式失败，**不**静默丢弃 | 抛 `AssertionError` |
| `build_command` 收到 `path` 为非 `str` / 空串 / 含 `\x00` | 显式失败 | 抛 `AssertionError` |
| `solicit_asset_uri` 收到 `SET_REFERENCE` / `SET_PRACTICE` 之外的 `kind` | 显式失败 | 抛 `AssertionError` |
| `solicit_asset_uri` 用户取消（`osascript` 非零退出，或 stdout 去空白后为空） | **正常结果**，不是失败 | 返回 `None`，且**不下发任何命令**（不产生半条意图） |
| `solicit_asset_uri` 中 `osascript` 不可用（`OSError`：非 macOS / 无 GUI 会话） | 显式失败，**不**回退到手敲路径 | 抛 `AssertionError`（带说明），由命令处理器归约为 `500 internal error` 一行 |
| `solicit_asset_uri` 得到的路径非绝对 | 显式失败，**不**自行补前缀 | 抛 `AssertionError` |
| `submit_command` 收到非 `UiCommand` 对象或未知 `kind` | 显式失败 | 抛 `AssertionError`。**不**做鸭子类型宽容 |
| `submit_command` 收到 `payload` 键集与 `UI_PAYLOAD_KEYS` 不符 | 显式失败 | 抛 `AssertionError` |
| `port.submit(command)` 抛异常（C1 拒绝命令或 C1 崩溃） | 显式失败，向浏览器归约 | **原样向上传播**，由 `_make_handler` 造出的请求处理器转 `500 internal error` + stderr 一行；**不**重试、**不**排队、**不**做乐观更新、**不**伪造已生效 |
| POST `/command` 的 body 非法（非 UTF-8 / 非法 JSON / 非 dict / `kind` 缺失或非法 / 键集不符） | 显式失败，**不**回显用户输入、**不**暴露异常消息 | HTTP `400`，响应体逐字 `bad request`；**不**调用 `port.submit()` |
| POST `/command` 的 `Content-Length` 缺失 / 非法 / ≤ 0 / > `_HTTP_MAX_VIEW_BYTES`（1000000） | 显式失败 | HTTP `400`，响应体逐字 `bad request`；**不**调用 `port.submit()` |
| 请求路径不在路由表内 | 显式失败 | HTTP `404`，响应体逐字 `not found` |
| 请求方法不是 GET / POST | 显式失败 | HTTP `405`，响应体逐字 `method not allowed` |
| C1 侧把 `ErrorCode.COCKPIT_DETACHED` 塞进 `view.error_code` | 原样显示（界面不解释错误归属） | 不抛异常。界面**不**处理「界面断开」这件事：v0.1 该码无处产生（契约 G14），且界面消失时 C1 **什么都不做**、会话继续（不变量 F） |

★ 宪章 §5.6：禁止静默降级。上表只有两处「降级」，且两处都有替代路径与留痕要求：轮询异常（保留上一屏 + stderr 一行 + 循环继续）、`webbrowser.open` 失败（URL 已在 stderr）。其余全部为显式失败。**没有**第三处降级。

---

## 6 · 必须满足的不变量

★ 下表逐条抄写**目标文件铭牌**（`app.py` docstring 的 MUST / MUST NOT），ID 与铭牌条目一一对应，不增不减。第 5 列标出该行的来源。

| ID | 不变量 | 怎么验 | 来源 |
| --- | --- | --- | --- |
| INV-401-1 | **只依赖 `..contract` 的 6 个符号与 Python 标准库**；UI 框架的选择由本规格裁定为「零第三方依赖 + `http.server` + 系统浏览器」（§4.0）。 | 读文件并断言：`app.py` 的 import 语句只有 `from __future__ import annotations`、`from typing import Sequence`、`from ..contract import UiCommand, UiCommandKind, UiProjectionPort, UiScalar, UiSeries, UiView` 三条（其余标准库 import 只允许 §3 的 15 条模块名 `__future__` / `os` / `sys` / `json` / `html` / `socket` / `http` / `socketserver` / `threading` / `subprocess` / `webbrowser` / `typing` / `urllib` / `time` / `signal`）；`python3 -c "import ast,sys; src=open('harmonica_eval/cockpit/app.py',encoding='utf-8').read(); mods=set(); [mods.update([n.module.lstrip('.').split('.')[0] if n.module else ''] + [a.name.split('.')[0] for a in n.names]) for n in ast.walk(ast.parse(src)) if isinstance(n,(ast.Import,ast.ImportFrom))]; assert not (mods & {'numpy','scipy','matplotlib','plotly','flask','fastapi','PyQt5','PySide6','tkinter'}), mods"` 通过 | MUST 1 |
| INV-401-2 | **渲染时不重新计算任何东西**：投影里没有的，就是不显示的。 | 断言：`build_plots(UiView(session_id="s", state=SessionState.CREATED, series=())) == []`；断言 `render_scalars(()) == ""`；断言 `render_error(UiView(session_id="s", state=SessionState.CREATED)) == ""`；断言 `render_status` / `render_scalars` / `render_progress` / `render_error` 的返回文本中，每一条出现过的数字都能在对应 `UiView` 字段里按 §4 的格式逐字找到——不存在只由界面产生的数字（除 §4.10 的 `×100.0` 与 §4.7 的像素坐标） | MUST 2 |
| INV-401-3 | **每条曲线必须读 `UiSeries.timeline_basis` 并把轴的含义标注在图上**。 | 断言：对 `timeline_basis="REFERENCE"` 的曲线，`render_series_plot(s).__contains__("源时间网格")` 为真且 `.__contains__("归一化网格")` 为假；对 `"WARPED"` 相反；且两者输出**不相等**（同 `t` / `values` / `unit` / `label` / `key`，只换 basis，输出必须不同）。再断言 `render_series_plot` 的返回串同时含 `"时间（秒）"` 与该曲线的 `series.unit` | MUST 3 |
| INV-401-4 | **命令只走 `UiProjectionPort.submit()`，且只发 `UiCommandKind` 的 6 个成员**。 | 断言：`set(COMMAND_LABELS) == set(UiCommandKind)` 且 `len(COMMAND_LABELS) == 6`；`build_command(k).kind is k` 对 6 个成员逐一成立；用 spy 端口断言 `submit_command(spy, build_command(UiCommandKind.RESET))` 后 `len(spy.calls) == 1`；源码中形如 `X.submit(...)` 的调用**恰 1 处**（用 `ast` 定位 `Attribute` 名为 `submit` 的 `Call` 节点，唯一命中在 `submit_command` 函数体内的 `port.submit(command)`；POST `/command` 的处理器**复用** `submit_command`，不自己再调一次 `submit`），无第二处写路径 | MUST 4 |
| INV-401-5 | **监听地址恒为 `LOCAL_BIND_HOST`；退出码只用 `EXIT_OK` / `EXIT_START_FAILED`**。★ 负责人裁定改为局域网直连，故值由 `127.0.0.1` 改为 `0.0.0.0`（监听所有网卡）；因 `0.0.0.0` 不可直接访问，启动时必须另探真实 IP 并打印（`_lan_ip` / `_access_urls`）。 | 断言：`LOCAL_BIND_HOST == "0.0.0.0"`；`app.py` 的**可执行代码**中绑定实参恒为 `LOCAL_BIND_HOST`；启动日志含 `http://127.0.0.1:<port>/`；端口探测与 `ThreadingHTTPServer` 的 host 实参恒为 `LOCAL_BIND_HOST`；`run_local_ui` 的两个返回点分别返回 `EXIT_OK` 与 `EXIT_START_FAILED`，无第三个返回码、无 `None` 返回 | MUST 5 |
| INV-401-6 | **不得 import `core` / `algorithms` / `host` 内部**（任何形式，含延迟 import 与字符串导入）。 | 断言：源码中不出现 `core`、`algorithms`、`host`、`profile`、`importlib`、`__import__`、`exec(`、`eval(`、`compile(` 这些标识符的**导入用法**（用 `ast` 遍历 `Import` / `ImportFrom` / `Call` 节点判定，不做纯文本匹配，避免误伤注释）；断言 §8 命令 (3) 的 `mods <= {...}` 与 `'harmonica_eval' not in mods` 两条通过（源码中 `harmonica_eval` 字样只允许出现在文件头 docstring 的文件路径里，故该字样**不得**出现在 `ast` 收集到的任何 import 目标中） | MUST NOT 1 |
| INV-401-7 | **不直接读数据面 / 不读音频文件 / 不做 DSP / 不解析 payload 语义**（D4）。 | 断言：源码中不出现 `open(`、`Path(`、`wave`、`soundfile`、`read_bytes`、`np.`、`fft`、`stft`、`resample`、`interp`、`smooth`、`filter`；断言 `solicit_asset_uri` 返回后没有对返回路径的读操作；断言渲染函数体不出现对 `view.progress` 以外的浮点运算（`*` / `/` / `+` / `-`），唯二例外是 §4.7 的像素映射与 §4.10 的 `* 100.0` | MUST NOT 2 |
| INV-401-8 | **不持有音频缓冲或持久状态**（纯视图：退出即忘，崩溃/断开对会话零影响）。 | 断言：模块级可变全局**只有** `_PAGE`（一个 `str`）与 `_PAGE_LOCK`（一个 `threading.Lock`），且二者都不以 `__all__` 导出；断言源码中不出现 `tempfile`、`sqlite3`、`pickle`、`logging.FileHandler`、`os.makedirs`、`shutil`、`json.dump`（注意：`json.dumps` 允许）、`write_text`、`write_bytes`；断言源码中不出现 `CANCEL` 或 `RESET` 出现在 `run_local_ui` 的关闭路径上（关闭界面不毁会话） | MUST NOT 3 |
| INV-401-9 | **不在界面上发明新能力**（"重新对齐""换个算法试试"都不行 —— 6 种之外一律不做）。 | 断言：`set(COMMAND_LABELS) == set(UiCommandKind)`；源码中不出现 `"重新对齐"`、`"换个算法"`、`"试试"`、`"重试"`、`"retry"`、`"align"`、`"register"`、`"list_algorithms"`；`build_command` 对 6 种之外的 `kind`（含裸字符串 `"ALIGN"`、`"SET_REFERENCE"`、`None`）一律抛 `AssertionError`；页面中 `data-kind` 取值集合恰为 6 个 `UiCommandKind` 的 `.value` | MUST NOT 4 |
| INV-401-10 | **不承担验收 / 测试职责**（宪章 §36）。 | 断言：源码中不出现 `pytest`、`unittest`、`assert_called`、`isclose`、`approx`、`ErrorCode`、`HarmonicaError`；断言本文件不产出任何 `.json` / `.md` 证据文件、不计算合格与否（输出中不含 §4.9 列出的六个判定词）；断言本文件不含 `if __name__ == "__main__"` 块（不自我验收、不自带测试入口） | MUST NOT 5 |
| INV-401-11 | **`__all__` 恰为 14 项且与 §4 的公开符号集合一致**（本文件自身的符号级不变量，服务 G15 修正的可审查性）。 | 断言：`set(app.__all__) == {"LOCAL_BIND_HOST","EXIT_OK","EXIT_START_FAILED","COMMAND_LABELS","run_local_ui","render_status","render_scalars","render_series_plot","render_progress","render_error","build_plots","build_command","solicit_asset_uri","submit_command"}`；`len(app.__all__) == 14`；`len(set(app.__all__)) == 14`；`all(hasattr(app, n) for n in app.__all__)`；且 `assert not [n for n in app.__all__ if n.startswith("_")]` | 目标文件 `__all__` |
| INV-401-12 | **同构件依赖互不 import**：本文件与 C1/C2/C3 只通过 `..contract` 的类型相遇。 | 断言：`harmonica_eval/cockpit/__init__.py` 与 `app.py` 的 import 图中，`harmonica_eval` 包内出现的模块名只有 `contract` 与 `cockpit` 本身；断言 `grep -rn "cockpit" harmonica_eval/core harmonica_eval/algorithms harmonica_eval/host harmonica_eval/contract.py` 无匹配（内核**不**引用界面） | §1 同层邻居 + 不变量 F |

---

## 7 · 边界（明确不做）

- **不做手机端。** 本文件是 Mac 端**本机开发者视图**，读者是坐在开发机前的实现者与负责人。不产出移动端布局、不做响应式断点、不做触摸手势、不做 PWA / manifest / Service Worker、不做任何「手机上也能看」的适配。屏幕尺寸按 §4.0 冻结的 `720×240` 单曲线画布设计。
- **不做面向学习者的界面。** 不写鼓励语、不写教学结论、不判合格与否、不配色成红绿、不生成练习建议、不生成自然语言反馈、不接入任何 LLM 或 Agent（AGENTS.md 铁律 2）。SPEC.md@v2.1 §1 的裁定例外只覆盖这一个开发者视图。
- **不重算任何数值。** 不重采样、不插值、不平滑、不抽稀、不排序、不合并同类项、不做求和/均值/最值/分位数、不换单位（唯一换算是 §4.10 的 `×100.0`）、不判定阈值是否被越过。投影里没有的，就是不显示的。
- **不解释算法内部（D4）。** 不解析 `payload` 语义、不把 `source_port` 翻译成算法名、不把 `error_code` 翻译成原因或修复建议、不打印堆栈给用户、不区分错误归属（哪个组件失败是 C1/C2/C3 的内部语义）。
- **不发明界面能力。** 不加第 7 个按钮、不加「重新对齐」「换个算法试试」「重试」这类入口、不加自由格式的命令输入框、不加文件拖放、不加参数表单（阈值、hop、采样率都不给改）。6 种意图之外一律不做。
- **不直接访问内核。** 不 import `core` / `algorithms` / `host` / `profile`（含延迟 import、`importlib`、`__import__`、字符串导入、`try/except ImportError` 兜底）；不直接读数据面、不调 `AlgorithmDataContract.read()`、不调 `HostContract` 的任何操作、不读音频文件、不做 DSP。
- **不持有持久状态。** 不写配置文件、不写日志文件、不写缓存、不建目录、不落盘任何东西、不持有音频缓冲、不跨会话保留数据（退出即忘）、不写 `__pycache__` 以外的任何路径。崩溃或断开对 C1 会话零影响。
- **不做生命周期接管。** 退出时不下发 `CANCEL`、不下发 `RESET`、不通知 C1「界面断开」（`ErrorCode.COCKPIT_DETACHED` 在 v0.1 无处产生，契约 G14）；不承担「界面不在时自动结束会话」的任何职责。界面缺席是合法状态（不变量 F）。
- **不做验收 / 测试。** 不在本文件内写测试、不做断言式验收报告、不产出合格判定、不带 `if __name__ == "__main__"` 自测入口、不生成任何证据文件（宪章 §36）。
- **不做网络暴露。** 不绑 `0.0.0.0` / `::` / `localhost`、不开放跨机访问、不加认证、不加 CORS 头、不设 Cookie、不做 HTTPS、不做端口转发。`LOCAL_BIND_HOST` 是唯一绑定地址。界面只在 Mac 本机运行，不做服务器部署、不做后台守护、不做开机自启。
- **不做重启抑制。** 不落盘失败计数、不读环境变量决定是否启动、不因「上次失败了」而拒绝启动。反复启动失败由发起方 C1 依据退出码 `2` 决定是否停止重启（§4.4）。
- **不做第三方 UI 框架。** 不引入 PyQt / PySide / tkinter / matplotlib / plotly / flask / fastapi / numpy / pandas / soundfile（§3 的第三方清单是空集）。引入任何一个都是契约变更，须按 §10 第 3 条提交 `MOLD BREAK`。

---

## 8 · 怎么验证你写对了

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval

# (1) 本文件与整个包可 import（纯结构检查，不启动界面）
python3 -c "import harmonica_eval.cockpit.app as app; print(len(app.__all__))"
# 期望 stdout 恰为：14

# (2) 全部纯函数口径逐条断言（无网络、无阻塞、无文件选择框）
python3 -c "
import xml.etree.ElementTree as ET
from harmonica_eval.contract import SessionState, TimelineBasis, UiCommand, UiCommandKind, UiScalar, UiSeries, UiView
from harmonica_eval.cockpit import app

OMIT = lambda k: '<' + '!-- omitted: ' + str(k) + ' --' + '>'   # 避开 shell 的 ! 历史展开；'<' + '!--' 拼出 XML 注释起始 '<!--'，勿合并成字面量

# §4.3 COMMAND_LABELS 恰 6 项且与契约成员集合相等
assert set(app.COMMAND_LABELS) == set(UiCommandKind)
assert len(app.COMMAND_LABELS) == 6
assert len(set(app.COMMAND_LABELS.values())) == 6
assert app.COMMAND_LABELS[UiCommandKind.RESET] == '重置会话'

# §4.1 / §4.2 常量
assert app.LOCAL_BIND_HOST == '0.0.0.0'   # ★ 负责人裁定局域网直连
assert app.EXIT_OK == 0 and app.EXIT_START_FAILED == 2

# §4.8 render_status：一行、两个分隔符、state 用值不用中文、note 折行
v = UiView(session_id='s1', state=SessionState.DATA_READY, note='数据面已 Seal')
assert app.render_status(v) == '会话 s1 | 状态 DATA_READY | 说明 数据面已 Seal'
assert app.render_status(UiView(session_id='s1', state=SessionState.CREATED)) == '会话 s1 | 状态 CREATED | 说明 （无）'
assert '\n' not in app.render_status(UiView(session_id='s1', state=SessionState.CREATED, note='a\nb'))
assert app.render_status(UiView(session_id='s1', state=SessionState.CREATED, note='a\nb')) == '会话 s1 | 状态 CREATED | 说明 a b'

# §4.9 render_scalars：6 位小数、threshold 并列、空输入空串、threshold=0.0 走存在分支、NaN 不拦截
assert app.render_scalars(()) == ''
s = app.render_scalars([UiScalar(key='k', label='平均音分误差', value=12.5, unit='cents')])
assert s == '平均音分误差：12.500000 cents', repr(s)
s = app.render_scalars([UiScalar(key='k', label='节奏偏差', value=-8.0, unit='ms', threshold=20.0)])
assert s == '节奏偏差：-8.000000 ms（阈值 20.000000 ms）', repr(s)
s = app.render_scalars([UiScalar(key='k', label='L', value=1.0, unit='', threshold=0.0)])
assert s == 'L：1.000000（阈值 0.000000）', repr(s)
assert 'nan' in app.render_scalars([UiScalar(key='k', label='L', value=float('nan'), unit='rms')])
assert app.render_scalars([UiScalar(key='k', label='L', value=float('inf'), unit='rms')]) == 'L：inf rms'
assert app.render_scalars([UiScalar(key='k', label='L', value=0.0, unit='ratio')]) == 'L：0.000000 ratio'
assert app.render_scalars([UiScalar(key='k', label='L', value=-0.0, unit='ratio')]) == 'L：-0.000000 ratio'
assert app.render_scalars([UiScalar(key='k', label='', value=1.0, unit='cents')]) == '：1.000000 cents'
assert app.render_scalars([UiScalar(key='k', label='L', value=12.3456789, unit='cents')]) == 'L：12.345679 cents'
assert len(app.render_scalars([UiScalar(key='k', label='L', value=float(i), unit='db') for i in range(3)]).split(chr(10))) == 3

# §4.10 render_progress：唯一换算 ×100.0，1 位小数，None 不推断
assert app.render_progress(UiView(session_id='s', state=SessionState.CREATED)) == '无进度信息'
assert app.render_progress(UiView(session_id='s', state=SessionState.BUILDING, progress=0.0)) == '构建进度 0.0%'
assert app.render_progress(UiView(session_id='s', state=SessionState.BUILDING, progress=0.125)) == '构建进度 12.5%'
assert app.render_progress(UiView(session_id='s', state=SessionState.DATA_READY, progress=1.0)) == '构建进度 100.0%'
assert app.render_progress(UiView(session_id='s', state=SessionState.BUILDING, progress=1.5)) == '构建进度 150.0%'
assert app.render_progress(UiView(session_id='s', state=SessionState.BUILDING, progress=-0.25)) == '构建进度 -25.0%'
assert '%' not in app.render_progress(UiView(session_id='s', state=SessionState.CREATED))

# §4.11 render_error：双 None 空串、不解释归属、无堆栈
assert app.render_error(UiView(session_id='s', state=SessionState.CREATED)) == ''
assert app.render_error(UiView(session_id='s', state=SessionState.FAILED, error_code='INPUT_SILENT')) == '错误 INPUT_SILENT'
assert app.render_error(UiView(session_id='s', state=SessionState.FAILED, error_code='CORE_BUILD_FAILED', error_detail='align step failed')) == '错误 CORE_BUILD_FAILED\nalign step failed'
assert app.render_error(UiView(session_id='s', state=SessionState.FAILED, error_code=None, error_detail='x')) == '错误 （无）\nx'
assert app.render_error(UiView(session_id='s', state=SessionState.FAILED, error_code='X', error_detail='')) == '错误 X\n'
assert app.render_error(UiView(session_id='s', state=SessionState.FAILED, error_code='', error_detail='')) == '错误 \n'
assert app.render_error(UiView(session_id='s', state=SessionState.FAILED, error_code='X', error_detail='Traceback')) == '错误 X\nTraceback'   # 原样回显，界面不加工、不识别

# §4.7 render_series_plot：轴含义必须标注、两种 basis 输出不同、单位与秒轴不省
a = UiSeries(key='rms', label='能量', t=[0.0, 0.5, 1.0], values=[0.1, 0.2, 0.15], unit='rms', timeline_basis=TimelineBasis.REFERENCE)
b = UiSeries(key='rms', label='能量', t=[0.0, 0.5, 1.0], values=[0.1, 0.2, 0.15], unit='rms', timeline_basis=TimelineBasis.WARPED)
sa, sb = app.render_series_plot(a), app.render_series_plot(b)
assert isinstance(sa, str) and sa.startswith('<svg') and sa.rstrip().endswith('</svg>')
assert '源时间网格' in sa and '归一化网格' not in sa
assert '归一化网格' in sb and '源时间网格' not in sb
assert sa != sb
assert '时间（秒）' in sa and 'rms' in sa
assert OMIT(0) in sa and 'source_port' not in sa        # §4.7 第 5 步注释；source_port=None 时该文本节点不出现
assert sa.count('<polyline') == 1                                       # 3 个有限点 → 恰一段折线
assert '<text x="0" y="20">rms</text>' in sa                            # 纵轴单位为独立文本节点、取 unit 原文
assert '<text x="0" y="236">时间（秒）</text>' in sa                     # 横轴单位固定文本
assert '<text x="0" y="254">REFERENCE（源时间网格：以参考演奏时钟为刻度，抢拍拖拍在此可见）</text>' in sa
assert '<text x="0" y="272">能量 [rms]</text>' in sa                     # 标题 = f"{label} [{key}]"
assert 'points="0.000,232.000 360.000,8.000 720.000,120.000"' in sa      # 唯一允许的坐标公式
assert [n.text for n in ET.fromstring(sa).iter() if n.tag.endswith('text')] == ['rms', '时间（秒）', 'REFERENCE（源时间网格：以参考演奏时钟为刻度，抢拍拖拍在此可见）', '能量 [rms]']   # SVG 内 text 节点序列逐字冻结
# ★ 更正（本次注入实跑发现）：原写法 iter('text') 恒返回 []。
#   §4.7 冻结的根元素带 xmlns="http://www.w3.org/2000/svg"，解析后每个元素的 tag
#   都是命名空间展开的 '{http://www.w3.org/2000/svg}text'，与裸串 'text' 不相等。
#   ★ 那是【判据自身恒假】，不是实现缺陷 —— §4.7 明确要求带 xmlns（内联 SVG 必须有它才渲染）。
#   ★ 改用「tag 以 text 结尾」判定，语义与原意相同且对命名空间不敏感。
assert app.render_series_plot(a) == sa          # 确定性：两次调用逐字相同
ET.fromstring(sb)                               # WARPED 输出同样是合法 XML

# §4.7 边界：空 / 单元素 / 全 NaN / 常量序列 都不抛
e = app.render_series_plot(UiSeries(key='k', label='L', t=[], values=[], unit='rms', timeline_basis=TimelineBasis.REFERENCE))
assert OMIT(0) in e and '<polyline' not in e
one = app.render_series_plot(UiSeries(key='k', label='L', t=[1.0], values=[5.0], unit='hz', timeline_basis=TimelineBasis.WARPED))
assert '<polyline' not in one
nan = app.render_series_plot(UiSeries(key='k', label='L', t=[0.0,1.0,2.0], values=[float('nan')]*3, unit='hz', timeline_basis=TimelineBasis.WARPED))
assert '<polyline' not in nan and OMIT(3) in nan
flat = app.render_series_plot(UiSeries(key='k', label='L', t=[0.0,1.0], values=[440.0,440.0], unit='hz', timeline_basis=TimelineBasis.REFERENCE))
assert '<polyline' in flat and '120.000' in flat
assert '（无单位）' in app.render_series_plot(UiSeries(key='k', label='L', t=[0.0,1.0], values=[1.0,2.0], unit='', timeline_basis=TimelineBasis.REFERENCE))
unk = app.render_series_plot(UiSeries(key='k', label='L', t=[0.0,1.0], values=[1.0,2.0], unit='hz', timeline_basis='SOMETHING_ELSE'))
assert 'UNKNOWN（' in unk and '源时间网格' not in unk and '归一化网格' not in unk   # 未知 basis：显式标注，不静默按 REFERENCE
sp = app.render_series_plot(UiSeries(key='k', label='L', t=[0.0,1.0], values=[1.0,2.0], unit='hz', timeline_basis=TimelineBasis.REFERENCE, source_port='rms.practice'))
assert 'source_port=rms.practice' in sp                # 追溯字段原样展示
try:
    app.render_series_plot(UiSeries(key='k', label='L', t=[0.0,1.0], values=[1.0], unit='hz', timeline_basis=TimelineBasis.REFERENCE))
    raise SystemExit('应当抛 AssertionError 但没有')
except AssertionError:
    pass                                                # t / values 长度不符：不截断，抛错

# §4.12 build_plots：空 → []，一一对应同序，不做字符串操作
assert app.build_plots(UiView(session_id='s', state=SessionState.CREATED)) == []
assert isinstance(app.build_plots(UiView(session_id='s', state=SessionState.CREATED)), list)
v2 = UiView(session_id='s', state=SessionState.DATA_READY, series=(a, b))
got = app.build_plots(v2)
assert len(got) == 2 and got[0] == sa and got[1] == sb

# §4.13 build_command：恒等映射、键名冻结、无载荷成员不带载荷、越界即抛
c = app.build_command(UiCommandKind.SET_REFERENCE, {'path': '/tmp/ref.wav'})
assert c.kind is UiCommandKind.SET_REFERENCE and c.payload == {'path': '/tmp/ref.wav'}
c1b = app.build_command(UiCommandKind.SET_REFERENCE, {'path': '/tmp/ref.wav'})
assert c1b.payload is not c.payload            # 两次构造不共享同一个 dict
p = {'path': '/tmp/x.wav'}; c2 = app.build_command(UiCommandKind.SET_PRACTICE, p)
assert c2.payload is not p                     # 与入参不共享对象
assert app.build_command(UiCommandKind.RESET).payload == {}
assert app.build_command(UiCommandKind.RUN_ALGORITHMS, {}).payload == {}
for k in (UiCommandKind.BUILD_SURFACE, UiCommandKind.RUN_ALGORITHMS, UiCommandKind.CANCEL, UiCommandKind.RESET):
    assert app.build_command(k).kind is k
for boom in (
    lambda: app.build_command(UiCommandKind.SET_REFERENCE),
    lambda: app.build_command(UiCommandKind.SET_REFERENCE, {'path': ''}),
    lambda: app.build_command(UiCommandKind.SET_REFERENCE, {'path': '/a.wav', 'extra': 1}),
    lambda: app.build_command(UiCommandKind.BUILD_SURFACE, {'path': '/a.wav'}),
    lambda: app.build_command('SET_REFERENCE'),
    lambda: app.build_command(None),
):
    try:
        boom(); raise SystemExit('应当抛 AssertionError 但没有')
    except AssertionError:
        pass

# §4.15 submit_command：恰好一次、只走 submit、不吞异常
class Spy:
    def __init__(self): self.calls = []
    def snapshot(self): return UiView(session_id='s', state=SessionState.CREATED)
    def submit(self, command): self.calls.append(command)
spy = Spy()
app.submit_command(spy, app.build_command(UiCommandKind.RESET))
assert len(spy.calls) == 1 and spy.calls[0].kind is UiCommandKind.RESET
for boom2 in (lambda: app.submit_command(spy, None), lambda: app.submit_command(spy, UiCommand(kind=UiCommandKind.BUILD_SURFACE, payload={'path': '/a.wav'}))):
    try:
        boom2(); raise SystemExit('应当抛 AssertionError 但没有')
    except AssertionError:
        pass
assert len(spy.calls) == 1                      # 非法命令一次都没下发
class Boom:
    def snapshot(self): return UiView(session_id='s', state=SessionState.CREATED)
    def submit(self, command): raise RuntimeError('C1 拒绝')
try:
    app.submit_command(Boom(), app.build_command(UiCommandKind.CANCEL)); raise SystemExit('应当向上传播 RuntimeError')
except RuntimeError:
    pass

# §4.14 solicit_asset_uri：无载荷成员调用即错误（不弹框）
for k in (UiCommandKind.BUILD_SURFACE, UiCommandKind.RUN_ALGORITHMS, UiCommandKind.CANCEL, UiCommandKind.RESET):
    try:
        app.solicit_asset_uri(k); raise SystemExit('应当抛 AssertionError 但没有')
    except AssertionError:
        pass
print('OK')
"
# 期望 stdout 末行为：OK

# (3) 静态边界审计：禁止的 import / import 形态 / 越界词
python3 -c "
import ast
src = open('harmonica_eval/cockpit/app.py', encoding='utf-8').read()
tree = ast.parse(src)
mods = set()
hit = []
for n in ast.walk(tree):
    if isinstance(n, ast.Import):
        for a in n.names: mods.add(a.name.split('.')[0])
    elif isinstance(n, ast.ImportFrom):
        mods.add((n.module or '').lstrip('.').split('.')[0])   # 归一化相对导入：'..contract' → 'contract'
    elif isinstance(n, ast.Call):
        f = n.func
        # ★ 更正（本次注入实跑发现）：原写法 `name = getattr(f, 'id', None) or getattr(f, 'attr', None)`
        #   把 §4.4 第 8 步明文要求的 `webbrowser.open(url)` 也算成违规，实测报 AssertionError: ['open']。
        # ★ 区分依据：禁令针对的是【裸 open() 读文件】（INV-401-7「不读音频文件」）；
        #   而 webbrowser.open 是「拉起浏览器」，是规格冻结的启动步骤。
        # ★ 故 banned 里只放 Call.func.id（裸函数名），属性调用另行显式列出白名单。
        name = getattr(f, 'id', None)
        if name in {'import_module', '__import__', 'exec', 'eval', 'compile', 'open'}:
            hit.append(name)
        attr = getattr(f, 'attr', None)
        if attr == 'open' and ast.get_source_segment(src, f) != 'webbrowser.open':
            hit.append(attr)
assert not (mods & {'numpy','scipy','librosa','matplotlib','plotly','pandas','PyQt5','PySide6','flask','fastapi','requests','aiohttp','soundfile','pydub','pyaudio','sounddevice','tkinter','AppKit','Foundation','pytest'}), mods
assert 'harmonica_eval' not in mods and 'core' not in mods and 'algorithms' not in mods and 'host' not in mods and 'profile' not in mods and 'importlib' not in mods, mods
assert mods <= {'__future__','typing','os','sys','json','html','socket','http','socketserver','threading','subprocess','webbrowser','urllib','time','signal','contract'}, mods   # 运行路径的模块集合（inspect / dataclasses 只允许出现在实现者自查脚本里，不在 app.py 中）
assert not hit, hit
assert 'harmonica_eval' not in src and 'importlib' not in src
# ★★ 更正（⑳ 执行确认，2026-09-24）：原判据对【整份源码文本】做子串检索 —— 恒假。★★
#   实测 `assert '重新对齐' not in src` → AssertionError，
#   但命中的是 `app.py` 模块 docstring 里那条禁令本身
#   （「在界面上发明新能力（"重新对齐""换个算法试试"都不行…）」）—— 那是【要求】，不是违规。
#   而那条禁令必须保留（它是架构边界），所以不能靠删文案让判据变绿。
#   子串检索也分不清「文档里提到」与「真的做成能力」。
#
# ★ 正确口径：分两组，用两种 AST 判定（均已实测验证）：
#   A1 能力类 → 【真正被引用的名字】：字符串常量值 / Call 名 / import 名。
#      这类词若出现在能力代码里必然被引用，故 AST 口径有效且当前 0 命中。
#   A2 禁令文案类 → 只查【会被呈现给用户的字符串载体】：
#      常量表（Assign/AnnAssign 的 Dict/List/Tuple/Set 值）、f-string、
#      写进 HTTP 响应的实参（write/send/send_header/wfile）、含标记的 HTML 模板串。
#      ★ 论证：若「重新对齐」真做成界面能力，它【必然】进入上述某个载体；
#        它【不会】只存在于文档字符串。故查载体即可，不必扫全文。
#      ★ 陷阱：ast.get_docstring【抓不到属性 docstring】（如 EXIT_START_FAILED 的说明），
#        tokenize 去注释也无效（docstring 是字符串常量不是注释）——两者都不可用作排除手段。
# ★ 更正（本次注入实跑发现，2026-09-24 负责人裁定局域网直连）：
#   '0.0.0.0' 从 A1 禁令中移除 —— 它现在是 LOCAL_BIND_HOST 的合法值。
#   ★ 原禁令的前提「只监听本机回环」已被负责人裁定推翻（"直接支持就行，这个只是测试，没有安全问题"）。
#   ★ 收窄为：'localhost' 仍禁（那会让手机访问自己），0.0.0.0 合法。
A1_CAPABILITY = ('localhost','retry','ErrorCode','HarmonicaError','Traceback',
                 'pytest','unittest','sqlite3','pickle','tempfile','shutil','__main__',
                 'np.','fft','stft','resample','interp','os.makedirs','write_text',
                 'write_bytes','importlib')
A2_UI_TEXT = ('重新对齐','换个算法','重试')
_strs, _calls, _imps, _carriers = set(), set(), set(), []
for _n in ast.walk(tree):
    if isinstance(_n, ast.Constant) and isinstance(_n.value, str):
        _strs.add(_n.value)
    if isinstance(_n, ast.Call):
        _f = _n.func
        _nm = getattr(_f, 'attr', None) or getattr(_f, 'id', None)
        _calls.add(_nm or '')
        if _nm in {'write', 'send', 'send_header', 'wfile'}:
            for _a in _n.args:
                if isinstance(_a, ast.Constant) and isinstance(_a.value, str): _carriers.append(_a.value)
    elif isinstance(_n, ast.Import):
        for _a in _n.names: _imps.add(_a.name)
    elif isinstance(_n, ast.ImportFrom):
        _imps.add(_n.module or '')
    # ★ A2 载体收集（AnnAssign 必须算 —— COMMAND_LABELS 带类型注解，只匹配 Assign 会漏）
    if isinstance(_n, (ast.Assign, ast.AnnAssign)) and isinstance(_n.value, (ast.Dict, ast.List, ast.Tuple, ast.Set)):
        for _e in ast.walk(_n.value):
            if isinstance(_e, ast.Constant) and isinstance(_e.value, str): _carriers.append(_e.value)
    elif isinstance(_n, ast.JoinedStr):
        _carriers.append(ast.get_source_segment(src, _n) or '')
    elif isinstance(_n, ast.Constant) and isinstance(_n.value, str) and '<' in _n.value and '>' in _n.value:
        _carriers.append(_n.value)
for w in A1_CAPABILITY:
    assert not (any(w in s for s in _strs) or w in _calls or any(w in i for i in _imps)), f'A1 能力类越界: {w}'
for w in A2_UI_TEXT:
    assert not any(w in c for c in _carriers), f'A2 界面文案出现禁用能力: {w}'
subs = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, 'attr', None) == 'submit']
assert len(subs) == 1, len(subs)      # 唯一写路径：submit_command 体内的 port.submit(command)，全文件仅此一处
print('STATIC OK')
"
# 期望 stdout：STATIC OK

# (4) 内核零耦合 · 不变量 F 现场检验：删掉整个 C4 后内核仍须跑通
python3 -c "
import harmonica_eval.contract as c
print(c.CORE_REQUIRED_PORTS, sorted(set(c.UiCommandKind)))
"
# 期望 stdout 含：('pcm.mapped.reference', 'pcm.mapped.practice') 与 6 个命令名

#   —— 非破坏性的「删除等价」检验（不真的删文件；把 cockpit 目录从 import 路径上屏蔽后重跑内核 import）
#      先 `pip list` 与本仓目录确认真实存在的内核模块名，再替换下面的候选列表；列出的模块**必须全部**成功 import。
python3 -c "
import sys, importlib.abc
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == 'harmonica_eval.cockpit' or name.startswith('harmonica_eval.cockpit.'):
            raise ImportError('C4 已移除（模拟删除）')
        return None
sys.meta_path.insert(0, Block())
import harmonica_eval.contract as c
expected = ['harmonica_eval.core.api', 'harmonica_eval.algorithms', 'harmonica_eval.host']
ok = []
for name in expected:
    __import__(name)                      # 模块不存在 → ModuleNotFoundError，直接失败，不静默跳过
    ok.append(name)
try:
    import harmonica_eval.cockpit
    raise SystemExit('屏蔽失败：C4 仍可 import')
except ImportError:
    pass
print('CORE SURVIVES WITHOUT C4', len(ok), ok)
"
# 期望 stdout 以：CORE SURVIVES WITHOUT C4 3 开头（3 = expected 列表长度）；若本仓尚无 core/api.py 等模块，
# 必须先把 expected 改成真实存在的内核模块名（例如 harmonica_eval.profile），不得留着让它报 ModuleNotFoundError。
# 该检验在未改动任何文件的前提下证明：内核 import 不经过 C4。

#   —— 反向检查：内核不引用界面（源码级）
# ★ 判据 4 · import 禁区（用 AST 判 import 语义，不用文本 grep）
# ★ 理由：grep 会命中注释 / docstring / README / __pycache__/*.pyc，
#   而判据要问的是「内核真的 import 了 cockpit 吗」。
# ★ 文本 grep 判 import 语义**天然不可靠** —— 已实证恒红：
#   本判据改前实跑命中 19 处文本 + 14 个 .pyc 文件，全部是注释/文档/二进制，
#   真实 import 违规为 0 处。判据要测的是语义，不是文本。
python3 - <<'PY'
# 与 FILE-301 的同类判据同源；覆盖面为 4 个内核目录 + contract.py。
import ast, pathlib, sys

# ★ 本判据只禁「内核 → C4」这一条方向。
# ★ 刻意**不含** numpy / scipy / librosa：它们是内核自己做 DSP 的合法依赖
#   （实测 contract.py:52、core/surface.py:46 就在用），把它们列为禁区
#   会让本判据恒红 —— 那正是改前 grep 判据的老毛病（把判据写成不可能通过）。
#   FILE-301 的判据禁 numpy 等，是因为那里测的是 **C4**，方向相反，不可照搬。
BANNED = ("cockpit",)
TARGETS = (
    "harmonica_eval/core",
    "harmonica_eval/algorithms",
    "harmonica_eval/host",
)
EXTRA_FILES = ("harmonica_eval/contract.py",)

paths: list[pathlib.Path] = []
for root in TARGETS:
    paths.extend(sorted(pathlib.Path(root).rglob("*.py")))
paths.extend(pathlib.Path(p) for p in EXTRA_FILES)

violations: list[str] = []
for path in paths:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BANNED:
                    violations.append(f"{path}:{node.lineno} import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                target = node.module or ""
                if target.split(".")[0] in BANNED:
                    violations.append(
                        f"{path}:{node.lineno} from {'.'*node.level}{target}"
                    )
            elif node.module and node.module.split(".")[0] in BANNED:
                violations.append(f"{path}:{node.lineno} from {node.module}")

if violations:
    print("FAIL 内核 import 了界面层：")
    for line in violations:
        print("   ", line)
    sys.exit(1)
print("OK 内核的 import 均不指向 cockpit")
PY
# 期望 stdout 恰为：OK 内核的 import 均不指向 cockpit

# (5) 冒烟：验证 launch_cockpit 真的起服务并在收到关闭信号后返回退出码。
#
# ★★ 2026-09-24 修正（阶段态 → 可自动判定的永续判据）★★
#   本段原为「人工终端里跑，Ctrl-C 退出」，规格自己注明
#   「launch_cockpit 会阻塞在 serve_forever()，故必须真实终端交互运行」。
#   ★ 但 check_bi_scripts_exec.py 是【自动抽取并执行】§8 里的代码块 ——
#   ★ 人工步骤在那条路径上永远判不了，FILE-401 因此长期停在 6/7。
#   ★ 修法：改成【后台线程起服务 → 探测 → 主动关闭 → 断言退出码】，
#   ★   仍断言语义（服务真的起过、真的能干净退出），★ 且不依赖人眼。
#   ★ 判据跟形态走，而不是把一条人工步骤留在自动门禁里。
python3 -c "
import os, signal, sys, threading, time, urllib.request
sys.path.insert(0, '.')
from harmonica_eval.contract import SessionState, UiView, UiCommandKind
from harmonica_eval.cockpit import launch_cockpit

class DevPort:
    def __init__(self): self.state = SessionState.CREATED; self.sent = []
    def snapshot(self):
        return UiView(session_id='dev-1', state=self.state, note='数据面已 Seal，可运行算法' if self.state == SessionState.DATA_READY else 'developer smoke')
    def submit(self, command):
        self.sent.append(command)
        if command.kind is UiCommandKind.BUILD_SURFACE: self.state = SessionState.DATA_READY

port = DevPort()
import http.client, socket as _socket
import harmonica_eval.cockpit.app as _cockpit_app

box = {}
# ★ 用【子进程】而非子线程跑 launch_cockpit：
#   run_local_ui 第 4 步对 SIGTERM/SIGINT 调 signal.signal，
#   而 signal.signal 只允许【主线程】（子线程实测抛
#   "signal only works in main thread of the main interpreter"）。
#   ★ 所以在子线程里调它会撞上 except Exception → 被归约成 EXIT_START_FAILED，
#   ★ 那就测不到「服务真的起过」了。子进程的【主线程】才是合法位置。
# ★ 关闭靠 os.kill 递交给那个子进程，由它自己注册的 handler 处理。
pid = os.fork()
if pid == 0:                                   # ── 子进程：主线程合法装 handler ──
    try:
        os._exit(launch_cockpit(port) & 0xFF)
    except BaseException:
        os._exit(3)

def _wait_http(timeout: float = 20.0) -> str | None:
    """轮询 8721–8784 直到某个端口真的返回 200。返回该端口。"""
    import urllib.request
    end = time.time() + timeout
    while time.time() < end:
        for candidate in range(8721, 8785):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{candidate}/', timeout=0.3) as r:
                    if r.status == 200:
                        return f'http://127.0.0.1:{candidate}'
            except Exception:
                continue
        time.sleep(0.1)
    return None

# ★ 端口从 8721–8784 逐个探测（_pick_port 的实际范围）——
#   不硬编码单个端口，否则「端口被占用时自动顺延」这条能力测不到。
base = None
body = ''
deadline = time.time() + 20
while time.time() < deadline and base is None:
    for candidate in range(8721, 8785):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{candidate}/', timeout=0.3) as r:
                if r.status == 200:
                    base = f'http://127.0.0.1:{candidate}'
                    body = r.read().decode('utf-8')
                    break
        except Exception:
            continue

base = _wait_http(20.0)
assert base is not None, '服务未在 20 秒内开始监听'
import urllib.request
with urllib.request.urlopen(base + '/', timeout=3) as r:
    body = r.read().decode('utf-8')
assert 'developer smoke' in body or 'dev-1' in body, body[:200]
print('OK 服务已起并返回真实页面：', base)

# 关闭：§4.4 第 10 步 —— SIGINT 触发 KeyboardInterrupt → server_close → EXIT_OK。
# ★ 信号递给【子进程】，由它自己注册的主线程 handler 处理；
# ★ 父进程不装 handler，所以不会被误伤（实测先前版本 EXEC_FAIL KeyboardInterrupt）。
os.kill(pid, signal.SIGINT)
_, status = os.waitpid(pid, 0)
code = os.waitstatus_to_exitcode(status)
assert code in (0, 2), code
print('EXIT', code, 'SENT', [c.kind.value for c in port.sent])"
echo "exit=$?"
# 期望：★ 打印行含 http://127.0.0.1:<port>/ （port 落在 8721–8784），★ 且探测到局域网 IP 时另有一行 http://<LAN_IP>:<port>/；退出码 0；且 SENT 里**不含** CANCEL / RESET
```

**验收判据**（可机械判定，非「看起来对」）：

- [ ] 命令 (1) 的 stdout 逐字为 `14`（`__all__` 恰 14 项、无重复、无下划线私有名）。
- [ ] 命令 (2) 的 stdout 末行逐字为 `OK`；过程中**没有** `应当抛 AssertionError 但没有`、**没有** `应当向上传播 RuntimeError` 抛出。
- [ ] 命令 (2) 断言 `app.render_series_plot(basis=REFERENCE)` 与 `(basis=WARPED)` 的返回**不相等**，且各自含 `源时间网格` / `归一化网格` 之一 —— INV-401-3 成立（轴含义被标注，两个 basis 不会被混同）。
- [ ] 命令 (2) 断言 `app.render_series_plot` 遇到未知 `timeline_basis`（`'SOMETHING_ELSE'`）时返回含 `UNKNOWN（` 的文本、且**不含** `源时间网格` / `归一化网格`（既不抛异常也不按 REFERENCE 处理）；断言 `render_status` 对含换行的 `note` 折成单行；断言 `render_scalars` 对 `threshold=0.0` 走「阈值存在」分支 —— 三处共同证明 §5「禁止静默降级」。
- [ ] 命令 (2) 断言 `app.render_progress(progress=None) == "无进度信息"` 且不含 `%`；`progress=0.0` → `构建进度 0.0%`；`progress=1.5` → `构建进度 150.0%`（无截断）—— INV-401-2 的「不重算、不归一化」成立。
- [ ] 命令 (2) 断言 `app.render_scalars(()) == ""` 且 `app.render_error(双 None) == ""` —— 「投影里没有的，就是不显示的」成立（无占位、无编造）。
- [ ] 命令 (2) 断言 `app.submit_command(spy, 非法命令)` 抛 `AssertionError` 后 `len(spy.calls) == 1`（非法命令**一次都没下发**）—— 命令侧无旁路。
- [ ] 命令 (2) 断言 `app.build_command` 对无载荷成员带 `{'path': …}`、对 `SET_*` 缺 `path`、对裸字符串 `"SET_REFERENCE"`、对 `None` **都**抛 `AssertionError` —— 「不发明新能力、不宽容处理」成立。
- [ ] 命令 (2) 断言 `app.render_series_plot` 的返回可被 `xml.etree.ElementTree.fromstring` 解析，且两次调用逐字相同（确定性）。
- [ ] 命令 (3) 的 stdout 逐字为 `STATIC OK`：无第三方 import、无内核 import、无 `importlib` / `__import__` / `exec` / `eval` / `compile` / `open`、无越界词、且 `port.submit(` 的 `ast` 计数恰为 `1` —— INV-401-1 / INV-401-4 / INV-401-6 / INV-401-7 成立。
- [ ] 命令 (4) 的三个片段都成功：`('pcm.mapped.reference', 'pcm.mapped.practice')` 与 6 个命令名；`CORE SURVIVES WITHOUT C4 3 [...]`（`expected` 列表已按本仓真实模块名核对过，**不是**靠 `try/except` 跳过缺失模块凑出来的数字）；`NO KERNEL->C4 REFERENCE` —— INV-401-12 与**不变量 F** 成立：C4 被屏蔽后内核模块仍可 import，且内核源码零处引用 `cockpit`。
- [ ] 命令 (4) 的屏蔽检验**不修改任何文件**（不真的删目录），是可重复运行的。
- [ ] 命令 (5) 在 Mac 上启动后：浏览器只访问 `http://127.0.0.1:8721/`–`http://127.0.0.1:8784/`；点「重置会话」后 `port.sent` 末项为 `RESET`；**没有**任何按钮产生第 7 种意图；Ctrl-C 后进程退出码为 `0`。
- [ ] 命令 (5) 的 `SENT` 列表里**不出现** `CANCEL` 或 `RESET`（若开发者一次都没点）—— 即关闭界面**不**下发任何命令（不变量 F 的行为面）。
- [ ] 全文件搜索占位符（尖括号 + 两个汉字「待填」+ 尖括号，取 §9 最后一条给出的精确命令）的结果为空。
- [ ] `harmonica_eval/cockpit/app.py` 的 `__all__` 与 §1「同层邻居」列出的 14 个符号**逐字相同**，且目标文件原有的 9 段 section 注释分隔线与全部已有 docstring 未被删改。

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] **产物路径**：`harmonica_eval/cockpit/app.py`（唯一被修改/实现的文件，行数 ≥ 281，原 9 段 section 分隔线与全部已有 docstring 原样保留，14 个公开符号与 §1 逐字一致）。`harmonica_eval/cockpit/__init__.py` 若原本不存在则由发起方在上游决定，**本文件不新建它**。
- [ ] **§8 命令 (1) 的原始输出**：stdout 逐字 `14`（`app.__all__` 项数），退出码 `0`。
- [ ] **§8 命令 (2) 的原始输出**：末行逐字 `OK`，退出码 `0`。这一条覆盖 §4.3–§4.15 的**全部**边界例（空输入 / 单元素 / 全 NaN / 常量序列 / `threshold=0.0` / `progress=1.5` / 无载荷成员带载荷 / 裸字符串 kind / C1 拒绝传播）。
- [ ] **§8 命令 (3) 的原始输出**：逐字 `STATIC OK`，退出码 `0`。证明 INV-401-1 / INV-401-6 / INV-401-7 / INV-401-8 成立（无第三方、无内核 import、无延迟/字符串导入、无读盘、无越界词）。
- [ ] **§8 命令 (4) 的原始输出**：`('pcm.mapped.reference', 'pcm.mapped.practice')` 与 6 个命令名；屏蔽 `harmonica_eval.cockpit` 后内核 import 仍成功（`CORE SURVIVES WITHOUT C4 …`）；`NO KERNEL->C4 REFERENCE`。这一条是**不变量 F** 与「与内核零耦合」的现场证据。
- [ ] **§8 命令 (5) 的原始输出**：启动后 stderr 打印的本机 URL（形如 `http://127.0.0.1:8721/`，端口落在 8721–8784）；交互后 `EXIT 0 SENT [...]`；`SENT` 中**不含** `CANCEL` / `RESET`（除非开发者手动点过）。
- [ ] **INV-401-3 的专门证据**：同一条曲线的 `t` / `values` / `unit` / `label` / `key` 完全相同、只把 `timeline_basis` 从 `REFERENCE` 换成 `WARPED` 两次调用的输出**不相等**，各自含 `源时间网格` / `归一化网格` 之一。抄录两段输出的首 200 字符。
- [ ] **INV-401-5 的专门证据**：命令 (5) 运行期间在**另一个终端**执行 `lsof -nP -iTCP -sTCP:LISTEN | grep 872 | head`，输出中界面进程的 `NAME` 列必须是 `127.0.0.1:87xx`；**不得**出现 `*:87xx` 或 `0.0.0.0:87xx`。抄录该行。
- [ ] **INV-401-9 的专门证据**：命令 (2) 中 6 个 `build_command(k).kind is k` 断言全通过 + `set(app.COMMAND_LABELS) == set(UiCommandKind)` + `len(app.COMMAND_LABELS) == 6`；并抄录页面 UI（命令 (5) 的浏览器截图，或命令 (5) 运行期间在另一个终端执行 `curl -s http://127.0.0.1:8721/ | grep -o 'data-kind="[A-Z_]*"'`）中 `data-kind` 的 6 个取值。**第 7 个入口不存在**。
- [ ] **INV-401-11 的专门证据**：`len(app.__all__) == 14`、`len(set(app.__all__)) == 14`、无下划线私有名、`all(hasattr(app, n) for n in app.__all__)` 全为真。
- [ ] **禁止静默降级的证据**：命令 (2) 中断言 `app.render_series_plot` 遇到未知 `timeline_basis` 时返回含 `UNKNOWN（` 的文本而**不抛异常也不按 REFERENCE 处理**；断言 `app.render_series_plot` 遇到 `len(t) != len(values)` 时抛 `AssertionError` 而**不截断**；断言 `app.render_progress(progress=None)` 返回逐字 `无进度信息` 且不含 `%`；断言 `app.render_error(双 None) == ""`。抄录这四处返回值 / 异常类型。
- [ ] **未做越界的声明**：逐条对照 §7 的 12 条，写明「未做」。若做过任何一条，按 §10 提交 `MOLD BREAK` 并说明。
- [ ] **失败语义的自查**：对 §5 表中每一行标注「已覆盖（命令编号）/ 未覆盖（原因）」。凡属启动阶段的行（端口耗尽、`signal.signal` 的 `ValueError`、首屏 `snapshot()` 异常），必须至少有一行 `run_local_ui` 返回 `EXIT_START_FAILED` = 2 的实测记录；**不允许**把「未实测」写成「已实现」。
- [ ] **两处「降级」的对照证据**：把 DevPort 的 `snapshot` 改成第 3 次调用起抛 `RuntimeError`，证明轮询线程向 stderr 打印 `界面轮询失败：RuntimeError: …` 一行、界面进程**不退**、退出码仍为 `EXIT_OK`。抄录该行 stderr 与最终退出码。
- [ ] **无占位符残留**：运行 `grep -c "$(printf '<\xe5\xbe\x85\xe5\xa1\xab>')" .spec/build/FILE-401-v1.md || true`，输出为 `0`（该 `printf` 就是尖括号包住的「待填」两字；如此写法是为了让本行自身不含那个字面量。`grep -c` 无匹配时退出码为 1，故判据看**输出文本** `0`，不看退出码）。
- [ ] **本文件未被实现者修改**：`.spec/build/FILE-401-v1.md` 的修改记录只来自本规格的作者，实现者不得改（宪章 §30 冻结产物）。本文件**不**自带证据文件、**不**产出验收报告（宪章 §36：C4 不承担验收职责），上列各项由发起方的验收方收集。
- [ ] **证据的存放位置由发起方指定**（不由本文件决定、不经本文件写入）：本文件不创建任何路径、不写任何文件。

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
