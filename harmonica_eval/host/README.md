> **本文是索引，不是权威。** 权威在 `.spec/` 与源码铭牌。
> 本文任何内容与它们冲突时以它们为准，并把冲突报给负责人。

# C1 Framework / Host 索引

## 这个组件负责什么

C1 承接用户与平台意图，持有会话、驱动一次分析流程、编排算法、归一化失败并发布只读投影；它不拥有 DSP，也不应让 C2/C3 互相知道对方。（`COMPONENTS.md:79-134`）

C1 与两个关键角色的身份关系：它是 `HostContract` 的消费方，而 `HostContract` 由 C2 的 `HostCore` 实现；它自己实现 C4 所消费的 `UiProjectionPort`。（`harmonica_eval/host/app.py:70-84`；`harmonica_eval/contract.py:759-764`、`:1205-1217`）

## 正式无头入口

`harmonica_eval/__main__.py` 是 C4 缺席时的正式无头入口：接收参考与练习两段音频，驱动“建数据面 → 跑算法”的完整流程，并落盘 `metrics.json` 与同目录的 `report.md`。未指定 `--out` 时，`metrics.json` 的缺省落点是 `data/out/metrics.json`；指定 `--out` 时，`report.md` 与其同目录。入口只消费 C1 发布的 `UiView` 投影，不做 DSP、不导入 cockpit；相关入口当前仍为 SHELL，注入前不得把它写成已交付行为。（`harmonica_eval/__main__.py:6-24`、`:49-56`）

## 文件索引

| 文件 | 职责 | 现场依据 |
| --- | --- | --- |
| `__init__.py` | C1 包出口；只声明 `app`，不加载装配逻辑。 | `harmonica_eval/host/__init__.py:6-19`、`:31-39` |
| `app.py` | 生命周期、组件装配、算法编排、错误归一化与 UI 投影。 | `harmonica_eval/host/app.py:6-47`、`:70-84`、`:113-253` |

## 产出与消费

| 方向 | 内容 | 出处 |
| --- | --- | --- |
| 消费 | C2 的 `HostContract`（7 个会话操作）和 C3 的显式 `Registry`。 | `harmonica_eval/host/app.py:113-124`；`.spec/build/FILE-301-v1.md:55-97` |
| 产出 | C4 可消费的 `UiView`；C4 的唯一写入口是 `submit(UiCommand)`。 | `harmonica_eval/host/app.py:211-244`；`harmonica_eval/contract.py:1205-1217` |
| 编排输入 | `UiCommand`、会话状态、Core 句柄；输出是状态与可视化投影。 | `COMPONENTS.md:94-107`；`harmonica_eval/host/app.py:233-244` |
| 结果 | `Sequence[AlgorithmResultEnvelope]`，按 Registry 注册顺序返回。 | `harmonica_eval/host/app.py:182-197`；`.spec/build/FILE-301-v1.md:190-204` |

## 关键约束与不变量

- **状态门**：算法只能在 `DATA_READY` 触发；正常流程状态单调推进，不能跳过数据面构建。`CANCEL` / `RESET` 是管理操作，允许回退到稳定态。（`harmonica_eval/host/app.py:24-31`；`harmonica_eval/contract.py:60-84`、`:1125-1152`）
- **单向兼容性**：C1 绝不因插件缺端口而要求 C2 生成数据；当前 Host BI 只冻结“端口存在”检查，而完整六项解析属于 runtime，当前分工尚未统一。（`harmonica_eval/host/app.py:172-181`；`.spec/build/FILE-301-v1.md:182-189`；`.spec/build/FILE-205-v1.md:115-153`）
- **故障隔离**：一个算法失败不能阻断其它算法，结果需归一化为失败信封；算法死循环仍会卡住流程。（`harmonica_eval/host/app.py:182-210`；`harmonica_eval/contract.py:887-905`）
- **投影纯显示**：C1 下采样曲线，但每条曲线必须携带 `timeline_basis`；不能混合不同时间轴，不能生成教学结论。（`harmonica_eval/host/app.py:211-226`；`harmonica_eval/contract.py:1000-1012`）
- **UI 不可信**：`submit` 必须以 `COMMAND_LEGALITY` 校验，非法命令拒绝且不改变状态。（`harmonica_eval/host/app.py:233-244`；`harmonica_eval/contract.py:1088-1111`）
- **C4 可缺席**：Host 不导入 cockpit；删除界面不影响无头流程。（`harmonica_eval/host/app.py:33-38`；`.spec/build/FILE-301-v1.md:282-295`）

## 相关规格

- C1 职责、保证、失败语义与不变量：[`COMPONENTS.md` COMP-C1](../../COMPONENTS.md) §3、§4、§5、§6、§7（`COMPONENTS.md:79-134`、`:324-357`、`:433-442`）。
- C1 Build Instruction：
  - [`FILE-300-v1.md` §4 包出口](../../.spec/build/FILE-300-v1.md)（`.spec/build/FILE-300-v1.md:85-120`）
  - [`FILE-301-v1.md` §4.0–§4.7 HostApp](../../.spec/build/FILE-301-v1.md)（`.spec/build/FILE-301-v1.md:103-264`）
- 命令与状态共享契约：[`contract.py` SessionState / COMMAND_LEGALITY / COMMAND_EFFECTS](../../harmonica_eval/contract.py)（`harmonica_eval/contract.py:60-84`、`:1088-1151`）。
- C1 是否能多会话，属于未裁定路线问题，不按 HostApp 注释自行决定。（`.spec/GATE-CHALLENGES-C3.md:61-86`）

## 已知缺口与未决项

- **🔴 GC-204-01：`HostApp` 的 `session_id` 不一致，G8 修正未向上层传播。** `HostContract` 要求会话级操作显式带 id（`harmonica_eval/contract.py:766-838`），但 HostApp 的 `set_reference` / `set_practice` / `build_surface` 隐式使用 C1 记住的 id（`harmonica_eval/host/app.py:127-169`），与契约及挑战记录直接冲突（`.spec/GATE-CHALLENGES-C3.md:18-53`）。**未裁定，阻塞 Cast Freeze。** 在裁定前不得把“单会话门面”注释当作已解决。
- **✅ GC-204-08 已关闭（原「🔴 未裁定，阻塞插件迁移」）**：不变量甲（`host/` 不 import 具体算法）与不变量乙（C1 需显式注册插件）曾在物理上直接冲突——要 `registry.register(pitch/timing/dynamics)` 就必须 import 具体对象，而旧口径「C1 是唯一知道实现处」又被禁止跨层。负责人 2026-09-24 裁定**方案甲**：新增物理装配根 `harmonica_eval/algorithms/bootstrap.py` 作为全系统唯一 import 具体算法模块的位置，Host 只接收它产出的已装配 `Registry`，自身不再 import 具体算法（`harmonica_eval/host/app.py:113-124`；`harmonica_eval/algorithms/bootstrap.py:6-13`）。台账状态为 `CLOSED`（`.spec/GATE-CHALLENGES-C3.md:544`、`:543`）。C3 检查器第②条「host 不依赖具体实现」继续由 `tools/check_plugin_contract.py` 机器守（`tools/check_plugin_contract.py:187-215`）。★ **裁定层已闭合，但装配链尚未接通**：`bootstrap.py` 目前没有被任何模块 import，物理通路要等 Host 注入后才闭合（`harmonica_eval/algorithms/bootstrap.py:287`）。原冲突描述保留于 `.spec/GATE-CHALLENGES-C3.md:297-349` 作为决策历史。
- **🔴 `ResolutionView` 尚未接入 C1**：runtime 源码已有 `ResolvedSurface` 形状，但按 `.spec/OWNER-DIRECTIVES.md` 指令 2（未授权前禁止注入），`as_view()` 与 `manifest()` / `read()` / `resolution` 当前为 SHELL；FILE-301 仍冻结直接 `entry(surface)`，当前 Host 源码也无适配器接线。（`harmonica_eval/algorithms/runtime.py:65-131`；`.spec/OWNER-DIRECTIVES.md:50-87`；`.spec/build/FILE-301-v1.md:190-204`；`harmonica_eval/host/app.py:182-210`）
- **当前未注入**：`HostApp` 构造、生命周期、运行、视图与工厂函数仍是 SHELL；`build_default_app` 也未实现。（`harmonica_eval/host/app.py:113-124`、`:127-169`、`:182-253`；`.spec/OWNER-DIRECTIVES.md:50-87`）
- **平滑进度没有来源**：Core 内部阶段禁止外泄，因此 `UiView.progress` 在构建期间只能粗粒度/不可用；这需要契约变更，不是 C1 可自行补的功能。（`harmonica_eval/contract.py:1022-1066`；`.spec/build/FILE-301-v1.md:226-245`）
- **算法死循环没有超时**：会使整个流程卡住，是 v0.1 已知缺口。（`harmonica_eval/host/app.py:182-208`；`harmonica_eval/contract.py:899-906`）
- **C1 注释把未裁定路线写成解释**：HostApp 说“隐藏当前 session 不矛盾”，但 GC-204-01 仍 OPEN；README 不应替负责人选择 A/B/C。（`harmonica_eval/host/app.py:89-110`；`.spec/GATE-CHALLENGES-C3.md:61-86`）
