> **本文是索引，不是权威。** 权威在 `.spec/` 与源码铭牌。
> 本文任何内容与它们冲突时以它们为准，并把冲突报给负责人。

# C4 Developer Cockpit 索引

## 这个组件负责什么

C4 是仅运行在 Mac、面向开发者的只读调试视图：把 C1 的投影显示出来，并通过 C1 提交受契约约束的意图；它不进入音频计算路径、不直接访问 C2/C3，也必须可以整体删除而不影响内核。（`SPEC.md:9-22`；`COMPONENTS.md:269-296`）

## 正式无头入口

C4 缺席时，正式无头入口仍是 `harmonica_eval/__main__.py`：接收参考与练习两段音频，驱动“建数据面 → 跑算法”的完整流程，并落盘 `metrics.json` 与同目录的 `report.md`。未指定 `--out` 时，`metrics.json` 的缺省落点是 `data/out/metrics.json`；指定 `--out` 时，`report.md` 与其同目录。入口只消费 C1 发布的 `UiView` 投影，不做 DSP、不导入 cockpit；★ 入口已于本次注入周期完成，五个缺陷样本均 rc=0 并落盘 `metrics.json`（16 scalars + 2 series）。（`harmonica_eval/__main__.py`）

## 文件索引

| 文件 | 职责 | 现场依据 |
| --- | --- | --- |
| `__init__.py` | C4 包出口；唯一公开入口 `launch_cockpit(port)`，并声明不 import core/algorithms/host。 | `harmonica_eval/cockpit/__init__.py:6-22`、`:34-64` |
| `app.py` | 本机 UI 入口、投影渲染、命令构造与提交；只依赖契约和标准库。 | `harmonica_eval/cockpit/app.py:6-35`、`:77-281` |
| `preview.py` + `preview.html` | **契约结构预览视图**（非产品界面、非本包正式入口）：把已冻结的契约层可视化为一张结构预览页。存在意义是回答「如果现在接真数据，契约够不够画界面」——画不出的字段即暴露契约缺口，在注入前发现比注入后返工便宜。 | `harmonica_eval/cockpit/preview.py:6-27`；`.spec/build/FILE-401-P-v1.md` |

### ★★ preview 与 app 的职责分界（不重复）★★

| | `preview.py`（已完成） | `app.py`（本文件注入） |
| --- | --- | --- |
| 画什么 | **契约定义**：字段结构、`PortDescriptor` 声明、类型与词表 | **运行结果**：真实 `UiView` 的值 —— 状态、四态标签、标量、端口就绪表、曲线、进度、错误 |
| 数据来源 | 读 `contract` / `profile` 的**静态声明** | 读注入的 `UiProjectionPort.snapshot()` 的**运行时投影** |
| 回答的问题 | 「契约够不够画界面」 | 「现在数据面处于什么状态」 |

★ **`app.py` 只画值，不画结构** —— 结构归 `preview.py`。两者不重复，也不互相替代。

## 产出与消费

| 方向 | 内容 | 出处 |
| --- | --- | --- |
| 消费 | 调用方注入的 `UiProjectionPort`：只读 `snapshot()`，唯一写路径 `submit()`。 | `harmonica_eval/cockpit/__init__.py:43-59`；`harmonica_eval/cockpit/app.py:77-92` |
| 显示 | `UiView` 的状态、标量、曲线、进度和错误；渲染不得重算 DSP。 | `harmonica_eval/cockpit/app.py:99-206`；`.spec/build/FILE-401-v1.md:284-323` |
| 产出 | 仅 `UiCommandKind` 已有的六种意图；文件选择只返回路径，不解码音频。 | `harmonica_eval/cockpit/app.py:58-70`、`:213-263`；`harmonica_eval/contract.py:1074-1101`、`:1154-1202` |
| 网络边界 | 绑定 `LOCAL_BIND_HOST`（默认 `0.0.0.0`，含局域网以便手机等设备访问；本机开发工具、非生产服务，进程退出即消失）。真实访问地址由启动横幅打印（`0.0.0.0` 本身不可用于浏览器）；退出码为 `EXIT_OK` / `EXIT_START_FAILED`。 | `harmonica_eval/cockpit/app.py:61`、`:155-165`；`.spec/build/FILE-401-v1.md:142-155` |

## 关键约束与不变量

- **纯视图**：不读取数据面、音频或算法内部，不做 DSP，不持有持久状态；C4 崩溃/退出不应影响已 Seal 的数据面。（`harmonica_eval/cockpit/__init__.py:13-22`；`harmonica_eval/cockpit/app.py:13-26`）
- **零内核耦合**：包导入期不加载 `app` 子模块，且禁止任何 core/algorithms/host import；调用方必须注入端口。（`harmonica_eval/cockpit/__init__.py:13-22`；`.spec/build/FILE-400-v1.md:40-58`）
- **只显示，不改算**：曲线按 `UiSeries.timeline_basis` 标出轴含义，不重采样、不插值、不平滑，不解释算法来源。（`harmonica_eval/cockpit/app.py:130-155`；`.spec/build/FILE-401-v1.md:232-282`）
- **只陈述数值**：状态、标量与错误按投影原文显示，不生成合格判定、教学建议或错误原因猜测。（`harmonica_eval/cockpit/app.py:99-187`；`.spec/build/FILE-401-v1.md:284-323`、`:349-365`）
- **六种意图穷举**：不得新增按钮、自由格式命令或“重新对齐/换算法”等能力；所有操作交给 C1 校验。（`harmonica_eval/cockpit/app.py:58-70`、`:213-263`）
- **★ 四态判别（★ 防假绿的唯一手段）★**：`app.py` 把投影判为互斥四态，判据全部来自 `UiView` 字段，不做推断：

  | 态 | 条件 | 界面显示 |
  | --- | --- | --- |
  | `A_UNBUILT` | `state` 非 `DATA_READY` | 数据面未就绪 |
  | `D_BLOCKED` | 无标量 **且** 有 `error_code`/`error_detail` | **管线中断** + 诊断原文 |
  | `B_NO_SOURCE` | 无标量 **且** 两个错误字段皆 `None` | 已通但无数据 |
  | `C_HAS_DATA` | 有标量 | 有指标 |

  ★ 单独的 D 态来自一次真实假绿：三个算法全部 `INCOMPATIBLE`、`state` 仍是 `DATA_READY`、`scalars=[]` 而 `error_detail` 里有明确诊断。★ 若按「无标量 ⇒ B」画，就把「算法全挂」画成了「正常但没数据」；若按「有诊断 ⇒ C」画，就是假绿。★ 三条互斥判据由 `_verify_view_consistency` 每次渲染前自证，判据变了当场炸。
- **零依赖铁律**：页面为原生 HTML/CSS/JS，无 npm、无 CDN、无外部字体、无图表库、无 `<script src>`、无 `<link>`。★ 「让手机能用」指的是**网络可达**（监听地址 + viewport + 响应式 + 44px 触控目标），**不是**引入依赖。
- **监听边界**：恒绑 `LOCAL_BIND_HOST`。★ 负责人裁定「直接支持局域网访问，这只是测试，没有安全问题」，故值为 `0.0.0.0`；但**不加认证、不做 CORS、不设 Cookie、不做 HTTPS、不做端口转发、不做开机自启**。★ `0.0.0.0` 是监听地址、不可直接访问，故启动时另探真实 IP 并打印两个可点击 URL。界面进程退出即消失。

## 相关规格

- 产品边界与 Mac/开发者例外：[`SPEC.md` §1](../../SPEC.md)（`SPEC.md:9-24`）。
- C4 职责与保证：[`COMPONENTS.md` COMP-C4](../../COMPONENTS.md) §3、§4、§5、§6、§7（`COMPONENTS.md:269-296`、`:324-357`、`:433-442`）。
- C4 Build Instruction：
  - [`FILE-400-v1.md` §4 包出口](../../.spec/build/FILE-400-v1.md)（`.spec/build/FILE-400-v1.md:62-117`）
  - [`FILE-401-v1.md` §4.0–§4.16 本机界面](../../.spec/build/FILE-401-v1.md)（`.spec/build/FILE-401-v1.md:105-477`）
  - [`FILE-401-P-v1.md` 契约结构预览](../../.spec/build/FILE-401-P-v1.md)（`preview.py` / `preview.html`）
- UI 类型、命令与状态：[`contract.py` UiView / UiCommand / UiProjectionPort](../../harmonica_eval/contract.py)（`harmonica_eval/contract.py:975-1217`）。

## 已知缺口与未决项

- **已注入并实测**（★ 2026-09-25 更新，★ 原写「当前未注入」已过期）：
  `launch_cockpit`、本机 UI 入口及全部渲染/命令函数均已实现，
  端到端实测 `python3 -m harmonica_eval.serve_ui --reference 原曲.wav --practice 练习曲.wav`
  起服务，12 个端口逐个可见、六个按钮按状态机顺序全部 200。
  （`harmonica_eval/cockpit/__init__.py`；`harmonica_eval/cockpit/app.py`）
- **命令的拒绝要可读**（★ 2026-09-25 修）：内核对用户输入的明确拒绝
  （`ContractViolation` / `CoreBuildError` / `AlgorithmError`）回 **400 + 原因原文**，
  只有真正的未预料异常才回 500。原先一律 `500 internal error` 五个字，
  会让「状态不对」被误读成「服务端坏了」。（`harmonica_eval/cockpit/app.py:840-880`）
- **测试时可用 `DSH_NO_BROWSER` 抑制弹窗**（★ 2026-09-25 修，治「反复跑测试导致浏览器标签越塞越多」）：
  ```bash
  DSH_NO_BROWSER=1 python3 -m harmonica_eval.serve_ui --reference 原曲.wav --practice 练习曲.wav
  ```
  ★ **默认行为不变**：不设该变量时**仍自动打开浏览器**
  （`FILE-401-v1.md:185` §4.4 第 8 步明文要求「随后 `webbrowser.open(该 URL)`」）。
  ★ **为什么用环境变量而不是 `--no-open-browser` 开关**：
  `FILE-499-v1.md:160` §7 明文「不提供 `--port` / `--host` / `--no-browser` 等任何额外开关」
  （AGENTS.md 铁律 4 零噪声），其 §8 判据把 `--no-browser` 列进 banned 集合。
  ★ 名字绕开 banned 虽能过判据，★ 但违反 §7 意图 —— **判据是精确匹配，意图不是**。
  ★ URL 仍照常打印到 stderr，**抑制的只是开浏览器**。（`harmonica_eval/cockpit/app.py:147-160`）
- **时间轴展示依赖正确轴标注**：REFERENCE 与 WARPED 的物理含义不同；若实现漏标轴，界面会把归一化位置误读为抢拍/拖拍，这是当前必须现场验证的风险。（`harmonica_eval/cockpit/app.py:130-143`；`harmonica_eval/contract.py:1000-1012`）
- **构建进度是粗粒度/可能为 None**：C4 不得自行从状态推断百分比；平滑进度需要 C1/契约层另行裁定，C4 不得补造。（`harmonica_eval/cockpit/app.py:159-171`；`harmonica_eval/contract.py:1022-1066`）
- **端口已闭合**（★ 2026-09-25 更新，★ 原写「未闭合」已过期）：`HostApp.snapshot/submit` 已实现并被 `serve_ui` 注入，12 端口端到端可见。（`harmonica_eval/host/app.py:618-648`）
- **“可整体删除”仍需真实测试证据**：BI 给出非破坏性删除等价检验，而不是在本 README 中伪造通过结果。（`.spec/build/FILE-400-v1.md:166-172`、`:231-246`）
- **【规格内部冲突 · 仍未裁定】C4 “不得加入 HTTP”与 FILE-401 冻结的本机 HTTP 方案冲突。** `COMPONENTS.md:271-279` 明确警告不要为界面添加 HTTP 服务；`.spec/build/FILE-401-v1.md:107-138` 则冻结零第三方依赖的 `http.server.ThreadingHTTPServer` + 系统浏览器方案，并规定只绑 `127.0.0.1`（绑定细则见 `.spec/build/FILE-401-v1.md:142-179`）。两处都是规格材料且未给出冲突裁定；**本文不裁定哪一方为准**。★ **实测状态**：`app.py` 已实现 27 个函数并按 FILE-401 方案起 `ThreadingHTTPServer`（端到端实测 HTTP 200、12 端口可见、六个按钮全通），即**实现侧已选 FILE-401 方案**，但规格冲突本身仍未裁定——若日后裁定以 `COMPONENTS.md` 为准，需回退这部分实现。（`harmonica_eval/cockpit/app.py:77-92`、`:300-340`）
- **陈旧的下游提示不能作为端口或注册清单**：`.spec/prompts/COMP-C3/downstream.md` 仍写旧注册/端口/时间轴口径；当前 C3 入口应看 FILE-200/205 与源码，历史提示仅作追溯。（`.spec/prompts/COMP-C3/downstream.md:42-92`；`.spec/build/FILE-200-v1.md:112-127`、`:163-172`；`.spec/build/FILE-205-v1.md:82-194`）
- **🔴 GC-204-01：C1 session API 尚未统一。** 这不由 C4 实现解决，但当前 HostApp 快照所依赖的会话句柄/状态投影仍受显式 `session_id` 与隐式当前会话的未决冲突影响。★ **实测补充**：`UiProjectionPort` 只有 `snapshot` / `submit` 两个操作且 `submit` 无 `session_id` —— 这与「一个前台看一个会话」一致（`session_id` 在 `UiView` 快照里），**但 HostApp 本身持有完整 HostContract（含显式 `session_id` 的 `set_reference(uri)` 等）**，两者是宽窄不同的两个接口。多会话能力属于 HostApp，界面侧只见到窄口。**未裁定是否满足「统一」，阻塞 Cast Freeze。**（`harmonica_eval/contract.py:759-838`；`harmonica_eval/host/app.py:89-110`、`:127-168`；`.spec/GATE-CHALLENGES-C3.md:12-86`、`:449-464`）
- **✅ GC-204-08 已关闭（原「🔴 未裁定，阻塞插件迁移」）**：这项裁定不改变 C4 的边界——C4 仍只消费 C1 发布的投影与命令，不 import 具体算法、也不持有注册表。裁定内容是「物理装配根为 `harmonica_eval/algorithms/bootstrap.py`，Host 只接收它产出的已装配 `Registry`」（`.spec/GATE-CHALLENGES-C3.md:544`、`:543`；`harmonica_eval/host/app.py:113-124`）。★ **装配链已接通**（★ 2026-09-25 实测，原写「尚未接通、bootstrap 无模块 import」已过期）：`build_default_registry()` 返回 `['pitch', 'timing', 'dynamics']` 三个已注册插件，五个缺陷样本端到端全 `rc=0`。
