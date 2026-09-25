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

- **当前未注入**：`launch_cockpit`、本机 UI 入口及所有渲染/命令函数仍是 SHELL；不能把渲染协议描述当作已运行的界面。（`harmonica_eval/cockpit/__init__.py:43-61`；`harmonica_eval/cockpit/app.py:77-92`、`:99-263`；`.spec/OWNER-DIRECTIVES.md:50-87`）
- **时间轴展示依赖正确轴标注**：REFERENCE 与 WARPED 的物理含义不同；若实现漏标轴，界面会把归一化位置误读为抢拍/拖拍，这是当前必须现场验证的风险。（`harmonica_eval/cockpit/app.py:130-143`；`harmonica_eval/contract.py:1000-1012`）
- **构建进度是粗粒度/可能为 None**：C4 不得自行从状态推断百分比；平滑进度需要 C1/契约层另行裁定，C4 不得补造。（`harmonica_eval/cockpit/app.py:159-171`；`harmonica_eval/contract.py:1022-1066`）
- **端口/实现未闭合，不能端到端宣称可用**：C4 依赖调用方注入已实现的 `UiProjectionPort`；当前 HostApp 的快照/提交仍为 SHELL。（`harmonica_eval/host/app.py:227-252`；`harmonica_eval/cockpit/app.py:77-92`）
- **“可整体删除”仍需真实测试证据**：BI 给出非破坏性删除等价检验，而不是在本 README 中伪造通过结果。（`.spec/build/FILE-400-v1.md:166-172`、`:231-246`）
- **【未裁定 · 规格内部冲突】C4 “不得加入 HTTP”与 FILE-401 冻结的本机 HTTP 方案冲突。** `COMPONENTS.md:271-279` 明确警告不要为界面添加 HTTP 服务；`.spec/build/FILE-401-v1.md:107-138` 则冻结零第三方依赖的 `http.server.ThreadingHTTPServer` + 系统浏览器方案，并规定只绑 `127.0.0.1`（绑定细则见 `.spec/build/FILE-401-v1.md:142-179`）。两处都是规格材料且未给出冲突裁定；**本文不裁定哪一方为准，也不把 HTTP 方案写成已获最终批准。** 当前 `cockpit/app.py` 仍只有空壳入口，不能据此宣称 HTTP 界面已经存在。（`harmonica_eval/cockpit/app.py:77-92`）
- **陈旧的下游提示不能作为端口或注册清单**：`.spec/prompts/COMP-C3/downstream.md` 仍写旧注册/端口/时间轴口径；当前 C3 入口应看 FILE-200/205 与源码，历史提示仅作追溯。（`.spec/prompts/COMP-C3/downstream.md:42-92`；`.spec/build/FILE-200-v1.md:112-127`、`:163-172`；`.spec/build/FILE-205-v1.md:82-194`）
- **🔴 GC-204-01：C1 session API 尚未统一。** 这不由 C4 实现解决，但当前 HostApp 快照所依赖的会话句柄/状态投影仍受显式 `session_id` 与隐式当前会话的未决冲突影响。（`harmonica_eval/contract.py:759-838`；`harmonica_eval/host/app.py:89-110`、`:127-168`；`.spec/GATE-CHALLENGES-C3.md:12-86`、`:449-464`）**未裁定，阻塞 Cast Freeze。**
- **✅ GC-204-08 已关闭（原「🔴 未裁定，阻塞插件迁移」）**：这项裁定不改变 C4 的边界——C4 仍只消费 C1 发布的投影与命令，不 import 具体算法、也不持有注册表。裁定内容是「物理装配根为 `harmonica_eval/algorithms/bootstrap.py`，Host 只接收它产出的已装配 `Registry`」（`.spec/GATE-CHALLENGES-C3.md:544`、`:543`；`harmonica_eval/host/app.py:113-124`）。★ **装配链尚未接通**（`bootstrap.py` 目前无模块 import），但那属于 C1/C3 的注入工作，不影响 C4 只消费投影的边界。
