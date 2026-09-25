> **本文是索引，不是权威。** 权威在 `.spec/` 与源码铭牌。
> 本文任何内容与它们冲突时以它们为准，并把冲突报给负责人。

# C2 Audio Core 索引

## 这个组件负责什么

C2 把两段输入音频编译成一份完整、不可变、与算法无关的标准分析数据面；它内部隐藏标准化、对齐、物化和端口存储，只向 C1 暴露 Host 门面、算法只读数据面契约。（`COMPONENTS.md:136-176`；`harmonica_eval/core/__init__.py:6-20`）

按 `.spec/OWNER-DIRECTIVES.md` 指令 2（未授权前禁止注入），当前工作区的实体函数仍是待注入壳件；在负责人同意前不得写入实现。（`.spec/OWNER-DIRECTIVES.md:50-87`；例如 `harmonica_eval/core/ingest.py:96-105`、`harmonica_eval/core/align.py:122-132`、`harmonica_eval/core/surface.py:147-160`、`harmonica_eval/core/api.py:114-120`）

## 正式无头入口

`harmonica_eval/__main__.py` 是 C4 缺席时的正式无头入口：接收参考与练习两段音频，驱动“建数据面 → 跑算法”的完整流程，并落盘 `metrics.json` 与同目录的 `report.md`。未指定 `--out` 时，`metrics.json` 的缺省落点是 `data/out/metrics.json`；指定 `--out` 时，`report.md` 与其同目录。入口本身不做 DSP、不导入 cockpit；相关入口当前仍为 SHELL，注入前不得把它写成已交付行为。（`harmonica_eval/__main__.py:6-24`、`:49-56`）

## 文件索引

| 文件 | 职责 | 现场依据 |
| --- | --- | --- |
| `__init__.py` | C2 包出口；公开子模块，并把 C1 的调用入口收敛到 `core.api`。 | `harmonica_eval/core/__init__.py:6-20`、`:35-52` |
| `ingest.py` | 音频解码、下混、重采样、时长与静音校验，产出标准 PCM。 | `harmonica_eval/core/ingest.py:6-31`、`:50-105` |
| `align.py` | 低分辨率 chroma、DTW、warp path 的单调性与覆盖校验。 | `harmonica_eval/core/align.py:6-43`、`:49-61`、`:65-132` |
| `features.py` | 预生成音高、RMS、chroma 与逐音摘要端口。 | `harmonica_eval/core/features.py:6-42`、`:63-118` |
| `surface.py` | 端口描述、预算检查、Seal，以及 `Surface.manifest/read`。 | `harmonica_eval/core/surface.py:6-39`、`:57-160` |
| `api.py` | `HostContract` 的会话状态机、生命周期和 C2 资源边界。 | `harmonica_eval/core/api.py:6-40`、`:50-120` |

## 产出端口

端口的唯一配置来源是 `profile.PORTS`；它要求 Core 预生成封闭清单，算法适配 Core 而不是让 Core 按插件需求扩展。（`harmonica_eval/profile.py:13-32`、`:243-445`）`core/__init__.py` 的门面说明把 `warp_path` 归给 `core.align`、特征端口归给 `core.features`、`pcm.*` 归给 `core.surface`；C1 只应通过 `core.api` 对话。（`harmonica_eval/core/__init__.py:42-52`）

### 生成表（不要手改）

> 本表由 `harmonica_eval/profile.py` 的 `PORTS` 生成。
> **改端口请改 `profile.py`，不要改本表。**

生成命令（实际运行）：

```bash
python3 -c 'from harmonica_eval.profile import PORTS
print("| port_id | units | dimensions | field_names | element_type | timeline_basis | hop_length | produced_by |")
print("| --- | --- | --- | --- | --- | --- | ---: | --- |")
for p in PORTS:
    fields = ", ".join(p.field_names) if p.field_names else "—"
    print(f"| `{p.port_id}` | `{p.units}` | `{tuple(p.dimensions)}` | {fields} | `{p.element_type}` | `{p.timeline_basis.value}` | `{p.hop_length}` | `{p.produced_by}` |")'
```

真实输出：

```text
| port_id | units | dimensions | field_names | element_type | timeline_basis | hop_length | produced_by |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| `warp_path` | `index` | `('warp_point', 'axis')` | reference_frame, practice_frame | `int32` | `REFERENCE` | `0` | `core.align` |
| `pcm.mapped.reference` | `amplitude` | `('sample',)` | — | `float32` | `REFERENCE` | `0` | `core.surface` |
| `pcm.mapped.practice` | `amplitude` | `('sample',)` | — | `float32` | `REFERENCE` | `0` | `core.surface` |
| `pcm.warped.practice` | `amplitude` | `('sample',)` | — | `float32` | `WARPED` | `0` | `core.surface` |
| `pitch.reference` | `hz` | `('frame', 'field')` | f0_hz, voiced, confidence | `float32` | `REFERENCE` | `2048` | `core.features` |
| `pitch.practice` | `hz` | `('frame', 'field')` | f0_hz, voiced, confidence | `float32` | `REFERENCE` | `2048` | `core.features` |
| `rms.reference` | `rms` | `('frame',)` | — | `float32` | `REFERENCE` | `256` | `core.features` |
| `rms.practice` | `rms` | `('frame',)` | — | `float32` | `REFERENCE` | `256` | `core.features` |
| `chroma.lowres.reference` | `chroma` | `('frame', 'bin')` | C, C#, D, D#, E, F, F#, G, G#, A, A#, B | `float32` | `REFERENCE` | `2048` | `core.features` |
| `chroma.lowres.practice` | `chroma` | `('frame', 'bin')` | C, C#, D, D#, E, F, F#, G, G#, A, A#, B | `float32` | `REFERENCE` | `2048` | `core.features` |
| `notes.reference` | `index` | `('note', 'field')` | onset_sec, f0_hz, rms | `float32` | `REFERENCE` | `0` | `core.features` |
| `notes.practice` | `index` | `('note', 'field')` | onset_sec, f0_hz, rms | `float32` | `REFERENCE` | `0` | `core.features` |
```

表中 `PORTS` 的生成位置与封闭性检查见 `harmonica_eval/profile.py:243-245`、`:451-571`；字段布局、单位词表与时间轴的契约出处见 `harmonica_eval/contract.py:87-141`、`:181-240`。

## 关键约束与不变量

- **封闭端口清单**：Seal 时必须穷举 `profile.PORTS`，不得因算法缺端口而动态追加；`read()` 是纯查表，不在读取时计算。（`harmonica_eval/profile.py:13-32`；`harmonica_eval/core/surface.py:15-27`）
- **两轴分离**：`REFERENCE` 是源时间网格，`WARPED` 是时间归一化网格；节奏计算不能偷换到 `WARPED`。（`harmonica_eval/contract.py:87-141`；`harmonica_eval/algorithms/timing.py:10-18`）
- **绝对音高与采样率**：音高端口必须保留 Hz、voiced、confidence；采样率是结果成因，必须随结果记录。（`harmonica_eval/core/features.py:21-31`、`:63-76`；`SPEC.md:134-147`）
- **只读与故障隔离**：数据面 Seal 后不可写；C2 失败不部分发布；`status()` 只返回六个 `SessionState`，内部阶段不得外泄。（`harmonica_eval/core/api.py:18-30`、`:87-120`；`harmonica_eval/core/surface.py:15-27`）
- **依赖方向**：`core/` 不导入 host、algorithms 或 cockpit，且不能通过“顺便”计算特征。（`harmonica_eval/core/__init__.py:18-21`；`harmonica_eval/core/ingest.py:21-25`）

## 相关规格

- C2 职责、保证与不变量：[`COMPONENTS.md` COMP-C2](../../COMPONENTS.md)，重点看 §3、§4.2、§5、§7（`COMPONENTS.md:136-197`、`:324-341`、`:377-387`、`:433-442`）。
- 行为边界：[`SPEC.md` §5 时间对齐与 §7 音高](../../SPEC.md)（`SPEC.md:95-119`、`:134-153`）。
- C2 内部 Build Instruction：
  - [`FILE-100-v1.md` §4 包公开面](../../.spec/build/FILE-100-v1.md)（`.spec/build/FILE-100-v1.md:59-190`）
  - [`FILE-101-v1.md` §4.1–§4.5 ingest](../../.spec/build/FILE-101-v1.md)（`.spec/build/FILE-101-v1.md:92-300`）
  - [`FILE-102-v1.md` §4 align](../../.spec/build/FILE-102-v1.md)（`.spec/build/FILE-102-v1.md:73-245`）
  - [`FILE-103-v1.md` §4 features](../../.spec/build/FILE-103-v1.md)（`.spec/build/FILE-103-v1.md:64-210`；引擎对照实验见 `:386-450`）
  - [`FILE-104-v1.md` §4.2–§4.7 surface](../../.spec/build/FILE-104-v1.md)（`.spec/build/FILE-104-v1.md:244-922`）
  - [`FILE-105-v1.md` §4.0–§4.10 HostCore](../../.spec/build/FILE-105-v1.md)（`.spec/build/FILE-105-v1.md:107-375`）

## 已知缺口与未决项

- **当前壳件未实现**：`ingest`、`align`、`features`、`surface` 与 `api` 的关键入口仍抛 `NotImplementedError("SHELL: ...")`，不能把本索引的实现意图当作已交付行为。（`.spec/OWNER-DIRECTIVES.md:50-87`；`harmonica_eval/core/ingest.py:96-105`；`harmonica_eval/core/align.py:122-132`；`harmonica_eval/core/surface.py:147-160`；`harmonica_eval/core/api.py:114-120`）
- **`notes.practice` 的现场分工不完整**：`profile.PORTS` 已同时声明 `notes.reference` 与 `notes.practice`，并写明按音配对需要练习侧索引；但 `features.materialize_notes` 当前 docstring 只写“参考侧逐音摘要”，函数签名也没有说明两侧分别如何产出。（`harmonica_eval/profile.py:399-445`；`harmonica_eval/core/features.py:104-118`）这是源码现场与索引之间的缺口，不能假装已闭合。
- **【未裁定】`core/surface.py` 的 `Surface` 继承了 `AlgorithmDataContract`，因此暴露了一个返回 `None` 的 `resolution`，而不是不提供该属性。** 契约 Protocol 当前声明 `AlgorithmDataContract.resolution` 为只读状态（`harmonica_eval/contract.py:654-678`），C2 `Surface` 继承该 Protocol；因此 `Surface().resolution` 为 `None`（`harmonica_eval/core/surface.py:112-145`）。`ResolvedSurface` 拟组合 C2 数据面与解析视图，但 `as_view()` 与它的 `manifest()` / `read()` / `resolution` 当前为 SHELL；按 `.spec/OWNER-DIRECTIVES.md` 指令 2（未授权前禁止注入），不得注入实现（`harmonica_eval/algorithms/runtime.py:65-131`；`.spec/OWNER-DIRECTIVES.md:50-87`）。因此“谁负责把 C2 Surface 包装成完整 `AlgorithmDataContract`（含 `resolution`）”仍未裁定；README 不把适配方案写成已解决。（`.spec/build/FILE-003-v1.md:173-191`；`.spec/build/FILE-205-v1.md:99-113`）
- **⚠ `COMPONENTS.md` 对频谱物化时点内部冲突**：旧文字仍写“只冻结定义、按需实体化”（`COMPONENTS.md:343-369`、`:427-429`），但负责人更正已明确否决惰性计算并要求 Core 全量预生成封闭 profile（`COMPONENTS.md:409-420`；`.spec/build/FILE-004-v1.md:13-20`；`CONTRACTS.md:19-33`）。本索引采用后者作为现行裁定，同时保留冲突位置供负责人回看。
- **`pcm.warped.practice` 当前无算法消费**：profile 现场已记录相关插件均走 `notes.*` / `rms.*`，该端口保留是为通用 PCM 底座，而不是现行插件必需项。（`harmonica_eval/profile.py:288-305`）
- **音高引擎仍需对照实验**：实现者不能把候选引擎直接当最终选择；FILE-103 登记了实验与结果要求。（`SPEC.md:146-151`；`.spec/build/FILE-103-v1.md:386-450`）
- **跨组件契约仍有未决挑战**：见 [`GATE-CHALLENGES-C3.md`](../../.spec/GATE-CHALLENGES-C3.md)；GC-204-08 已关闭，但 GC-204-01 仍 OPEN。（`.spec/GATE-CHALLENGES-C3.md:544`、`:12-87`、`:449-464`）
- **🔴 GC-204-01：C1 `session_id` 契约矛盾。** `HostContract` 的会话级操作要求显式 `session_id`，而 C1/HostApp 的注释主张用隐式当前会话；该挑战会波及 C1→C2 调用边界。（`harmonica_eval/contract.py:759-838`；`harmonica_eval/host/app.py:89-110`；`.spec/GATE-CHALLENGES-C3.md:12-86`、`:449-464`）**未裁定，阻塞 Cast Freeze。**
- **✅ GC-204-08 已关闭（原「🔴 未裁定，阻塞插件迁移」）。** 原冲突是「Host 禁具体算法 import」与「C1 显式注册」物理上不能同时成立。**裁定方案甲**：唯一物理装配根为 `harmonica_eval/algorithms/bootstrap.py`，它产出已装配 `Registry`；`HostApp` 只接收该 Registry，自身不 import 具体算法。（`.spec/GATE-CHALLENGES-C3.md:544`、`:549`；`.spec/build/FILE-206-v1.md`）
  - ★ **这不改变 C2 Core 的边界**：「core 不得知道具体算法存在」这条不变量**仍然有效**——`bootstrap` 位于 C3 侧，不违反它。
  - ★ **本组件的注册与装配一律不经 Core**；若实现中发现需要 Core 侧改动 → 按 §MOLD BREAK 上报。
