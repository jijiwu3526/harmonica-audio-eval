> **本文是索引，不是权威。** 权威在 `.spec/` 与源码铭牌。
> 本文任何内容与它们冲突时以它们为准，并把冲突报给负责人。

# C3 Algorithm 索引

## 这个组件负责什么

C3 消费只读数据面，完成一个独立算法能力，并返回自描述的 `AlgorithmResultEnvelope`；它不能管理音频生命周期、要求 C2 生成新端口或直接认识 UI。（`COMPONENTS.md:199-267`）

本目录的框架面是“显式注册 + 运行边界校验”，不是中央算法清单：`algorithms/__init__.py` 只 re-export `Registry`、`PluginSpec` 与 `InputRequirement`，Registry 只回答“有什么”，runtime 负责本次输入解析和结果自洽性。（`harmonica_eval/algorithms/__init__.py:6-37`、`:39-55`；`harmonica_eval/algorithms/registry.py:1-38`、`:49-78`；`harmonica_eval/algorithms/runtime.py:1-40`）

**冻结状态：`pitch.py` / `timing.py` / `dynamics.py` 的算法本体目前全部是纯 `SHELL`，零实现，不能运行；** 三个文件的全部算法函数体仍抛带 FILE-ID 的 `NotImplementedError`。（`harmonica_eval/algorithms/pitch.py:65-170`；`harmonica_eval/algorithms/timing.py:117-210`；`harmonica_eval/algorithms/dynamics.py:81-168`）`Registry` 与 runtime 也仍为空壳。（`harmonica_eval/algorithms/registry.py:49-78`；`harmonica_eval/algorithms/runtime.py:65-237`）

按 `.spec/OWNER-DIRECTIVES.md` 指令 2（未授权前禁止注入），`runtime.py` 的 `InputResolution.as_view()`、`ResolvedSurface.manifest()` / `read()` / `resolution`，以及 `resolve_inputs` / `validate_result` 相关入口当前为 SHELL。本文只记录冻结现场，不把它们写成可工作的委托链。（`harmonica_eval/algorithms/runtime.py:65-131`、`:134-237`；`.spec/OWNER-DIRECTIVES.md:50-87`）

## 正式无头入口

`harmonica_eval/__main__.py` 是 C4 缺席时的正式无头入口：接收参考与练习两段音频，驱动“建数据面 → 跑算法”的完整流程，并落盘 `metrics.json` 与同目录的 `report.md`。未指定 `--out` 时，`metrics.json` 的缺省落点是 `data/out/metrics.json`；指定 `--out` 时，`report.md` 与其同目录。入口只消费 C1 发布的 `UiView` 投影，不做 DSP、不导入 cockpit；相关入口当前仍为 SHELL，注入前不得把它写成已交付行为。（`harmonica_eval/__main__.py:6-24`、`:49-56`）

## 文件索引

| 文件 | 职责 | 现场依据 |
| --- | --- | --- |
| `__init__.py` | C3 类型出口；不保存算法清单或 payload 字段表。 | `harmonica_eval/algorithms/__init__.py:6-27`、`:39-55` |
| `bootstrap.py` | **唯一物理装配根**：全系统唯一 import 三个具体算法模块的位置，产出已装好的 `Registry`。负责人 BLOCK-1 裁定（方案甲）后新铸，全部函数体仍为 SHELL。 | `harmonica_eval/algorithms/bootstrap.py:1-46`、`:68-108` |
| `registry.py` | 装配期显式 `PluginSpec` 注册表，保序查询；不发现、不运行插件。 | `harmonica_eval/algorithms/registry.py:6-38`、`:49-78` |
| `runtime.py` | `InputResolution`、输入解析 `resolve_inputs`、结果校验 `validate_result`；另含未集成、未获 FILE-205 授权的 `ResolutionView` / `ResolvedSurface` 形状。 | `harmonica_eval/algorithms/runtime.py:7-40`、`:65-131`、`:134-237` |
| `pitch.py` | 绝对音高逐音比较与汇总。 | `harmonica_eval/algorithms/pitch.py:6-41`、`:48-59`、`:158-170` |
| `timing.py` | 保留源时间轴上的起音配对与抢拍/拖拍统计。 | `harmonica_eval/algorithms/timing.py:6-42`、`:48-114`、`:202-210` |
| `dynamics.py` | 按音配对 RMS，以 dB 报告动态差异。 | `harmonica_eval/algorithms/dynamics.py:6-63`、`:70-78`、`:156-168` |

## Registry 与 runtime 的职责分工

| 层 | 负责什么 | 明确不负责什么 | 出处 |
| --- | --- | --- | --- |
| `bootstrap` | **唯一** import 具体算法模块的地方；按 `REGISTRATION_ORDER` 构造 `PluginSpec` 并 `register`，产出 `Registry`。 | 不被 core/host/cockpit import；不运行算法、不读端口、不做 DSP、不重新定义 `PluginSpec`；所有函数体在授权注入前为 SHELL。 | `harmonica_eval/algorithms/bootstrap.py:19-25`、`:48-53`、`:68-108` |
| `Registry` | 装配期 `register`；运行期 `list`/`get`；保序、O(1) 查询、重复 `algorithm_id` 显式失败。 | 不扫描目录、不读取 entry-points、不判断 surface 兼容性、不运行插件、不做启停或会话管理。 | `harmonica_eval/algorithms/registry.py:10-19`、`:27-38`、`:49-78`；`.spec/build/FILE-204-v1.md:93-138` |
| `runtime` | 对 required/optional 输入逐项检查，记录可用与缺失事实；校验结果状态、单位、曲线、覆盖率与错误码。 | 不导入 C1/C2/C4 实现，不读取 `PluginSpec.entry`，不请求 Core 生成端口；`consumed_ports ⊆ available` 由 C1 调用点负责。 | `harmonica_eval/algorithms/runtime.py:7-40`、`:134-178`、`:181-237`；`.spec/build/FILE-205-v1.md:35-53`、`:115-183` |

因此，`bootstrap` 是"谁把插件装进去"，`Registry` 是"有哪些插件、顺序是什么"，`runtime` 是"这一次能否运行、结果是否诚实"；三者都不是算法实现本身。（`harmonica_eval/algorithms/bootstrap.py:19-25`；`harmonica_eval/algorithms/registry.py:49-53`；`harmonica_eval/algorithms/runtime.py:7-13`）

## 装配权：为什么是独立的 bootstrap（负责人 BLOCK-1 裁定，方案甲）

裁定前的实况是**物理上无解**：

```
不变量甲  C1 是全系统唯一知道「有哪些实现」的地方
不变量乙  C1 跨界 import 的是契约层，不是某个具体算法实现模块
```

要 `registry.register(pitch/timing/dynamics)` 就必须 import 具体模块，而乙禁止 C1 这么做 —— 两条同时成立时装配链**写不出来**。`.spec/GATE-CHALLENGES-C3.md` 把这一冲突登记为 **GC-204-08（OPEN · 阻塞插件迁移）**。

裁定后的分工：

| 主体 | import 具体算法？ | 拿到什么 |
| --- | --- | --- |
| `bootstrap.py` | ★ **是，且仅此一处** | 自己 import 三个算法，构造并注册 |
| C1（`HostApp`） | **否** | 只接收 `bootstrap` 产出的 `Registry` |
| C2 / C4 | **否** | 只用 `contract` 的类型 |

这样不变量乙对 C1 **继续成立**（它确实不 import 具体算法），而"谁负责装配"变成单点、可审查的物理事实。

✅ **已补齐**：`FILE-206-v1.md` Build Instruction 已建立（423 行，含 4 个 heredoc 验收脚本）。GC-204-08 台账已由负责人确认关闭（`.spec/GATE-CHALLENGES-C3.md:544`），原冲突描述保留为决策历史。

★ **但装配链仍未接通**：`bootstrap.py` 没有任何文件 import（Host 还是 SHELL）。**裁定落地了，物理通路要等注入 FILE-301 才闭合。** 另：「影响面」四项中只有 `check_plugin_contract` 已完成，`host/app.py:114-122` 的 docstring 与 `COMPONENTS.md:381-387` 的措辞仍待同步。

## 端口需求由谁声明（负责人 2026-09-24 裁定，方案甲）

`PluginSpec.required_inputs` / `optional_inputs` 的**权威来源是 `bootstrap.ALGORITHM_INPUTS`**，不是各算法自导出 `SPEC`，也不是 C1 投影。

★ `ALGORITHM_INPUTS` 是**正式公开出口**（负责人 2026-09-24 裁定）——
它是方案甲的权威端口需求声明，藏起来会让裁定形同虚设。

### 中文显示名 `LABEL`（负责人 2026-09-24 裁定）

`PluginSpec.label` 取自各算法模块的 `LABEL` 常量，装配根**不回退**：

| 算法 | `LABEL` | 出处 |
| --- | --- | --- |
| `pitch` | `音准` | `SPEC.md` §5「音高 / 音准（cents）」——本算法产出音分误差 |
| `timing` | `节奏` | `SPEC.md` §5「节奏 / 音符起始」——本算法比起音时刻 |
| `dynamics` | `力度` | `SPEC.md` §5「力度 / 能量」——本算法比能量差 |

★ **模块缺 `LABEL` 即抛 `PLUGIN_INCOMPATIBLE`**，不回退为 `algorithm_id`。
★ 理由：回退后界面会把英文 ID 当中文名显示且**全程无报错**，
★ 违反宪章 §5.6「禁止静默降级」。宁可装配失败，也不要静默给出错误文案。

| 算法 | 必需端口 | 出处 |
| --- | --- | --- |
| `pitch` | `pitch.reference` · `pitch.practice` · `notes.reference` · `notes.practice` | `pitch.py:19` |
| `timing` | `pcm.mapped.reference` · `pcm.mapped.practice` · `notes.reference` | `timing.py:21-22` |
| `dynamics` | `rms.reference` · `rms.practice` · `notes.reference` · `notes.practice` | `dynamics.py:20` |

★ **`timing` 刻意不含 `pcm.warped.practice`** —— `timing.py:30` 的 MUST NOT 明文禁止（会把抢拍拖拍抹成 0 且不报错）。**把它列进依赖等于要求它存在。**

★ **`dynamics` 也不含它** —— `dynamics.py:37-49` 记载 MOLD BREAK：`rms.*` 在 profile 里都是 REFERENCE 轴，原「用 WARPED 轴」的要求无法满足，已改为按音配对，`AXIS` 常量随之删除。

★ **实现时**：`InputRequirement` 的 `timeline_basis` / `element_type` / `required_fields` 从 `profile.PORT_INDEX` 派生，**不得硬编码** —— 硬编码会产生第二份真相源。`optional_inputs` v0.1 全空。

## 解析事实在谁手里（负责人 BLOCK-2 裁定，方案乙）

`consumed_ports` 是**结果信封**的字段（`contract.AlgorithmResultEnvelope`），而"本次实际可用哪些端口"是**执行期事实**（`runtime.InputResolution`）。两者只有同时在手才能比对：

| 主体 | 拿得到 `InputResolution`？ | 用途 |
| --- | --- | --- |
| C1（Host） | ★ **是** —— `resolve_inputs` 的返回值 | 比对 `consumed_ports ⊆ available` |
| 插件（算法） | **否** —— 只拿经 `as_view()` 投影的 `ResolutionView` | 读取自己声明的端口 |

`validate_result` **不接收** resolution / manifest，**签名无需变更**：它只管"信封自身是否自洽"，而"信封声称消费的端口是否真的可用"由 C1 在调用点比对。两者管的是不同事实，不构成重复。（`harmonica_eval/algorithms/runtime.py:177-196`、`:248-264`；`harmonica_eval/contract.py:519-528`）

★ **注意**：`contract.ResolutionView` 只有 `available` 与 `missing_optional`，**没有** `incompatible_required`。C1 做 `consumed_ports ⊆ available` 比对用不到后者（失败项已由 `status='INCOMPATIBLE'` 表达），因此乙方案不要求扩展该类型。（`harmonica_eval/contract.py:393-411`；`harmonica_eval/algorithms/runtime.py:73-87`）

## 三个算法的端口依赖（实测索引）

下表只把源码铭牌和 Build Instruction 的依赖声明并列；实际 `PluginSpec` 迁移尚未完成，不能把此表当作已经注册的机器清单。（`.spec/PLUGIN-LAYOUT.md:10-25`、`:122-149`、`:318-338`）

| 算法 | 现场声明的直接依赖 | 关键语义 | 出处 |
| --- | --- | --- | --- |
| `pitch` | `pitch.reference`、`pitch.practice`、`notes.reference`、`notes.practice` | 绝对 Hz 音高；按音配对，不能把 REFERENCE 轴误当两侧帧号对齐。 | `harmonica_eval/algorithms/pitch.py:18-31`、`:81-118`；`.spec/build/FILE-201-v1.md:466-477` |
| `timing` | `pcm.mapped.reference`、`pcm.mapped.practice`、`notes.reference`；onset 检测需要 mapped PCM，notes 是优先路径。 | 必须在 REFERENCE 轴；负值为抢拍、正值为拖拍。 | `harmonica_eval/algorithms/timing.py:20-38`、`:117-138`、`:202-210`；`.spec/build/FILE-202-v1.md:74-90` |
| `dynamics` | `rms.reference`、`rms.practice`、`notes.reference`、`notes.practice` | 按音配对，不按帧或轴代理；输出 dB 差异，不设合格阈值。 | `harmonica_eval/algorithms/dynamics.py:19-34`、`:35-53`、`:90-124` |

★ **实测结论：pitch/timing/dynamics 三者都依赖 `notes.reference`，没有哪个能只靠 A 级 PCM 跑起来。** 依据是源码现场逐文件出现该端口依赖：pitch `:18-21`，timing `:20-23`，dynamics `:19-22`；同时 `.spec/PLUGIN-LAYOUT.md` 明确记录了这一实测结论（`.spec/PLUGIN-LAYOUT.md:17-20`）。`notes.*` 的对称端口在 `profile.PORTS` 中已存在，但迁移后的 `PluginSpec` 尚未落盘，因此不要把“依赖设计”写成“已注册事实”。（`harmonica_eval/profile.py:399-445`；`.spec/PLUGIN-LAYOUT.md:122-149`）

## 12 条架构不变量

`tools/check_plugin_contract.py` 的 `run_normal_checks` 运行 **12 条编号守卫 + 1 条无编号 composite**，共 13 项：① core 不依赖具体算法；② host 不依赖具体算法实现；③ cockpit 不依赖具体算法；④ algorithms 不反向 import 上层；⑤ 框架无按 algorithm_id 索引的 payload 表；⑥ Host 无 plugin_id/algorithm_id 硬编码比较；⑦ 框架代码/注解无具体 payload 字段；⑧ `InputRequirement` 仅 `port_id` 必填；⑨ `PluginSpec` 输入集合为 tuple；⑩ 单位词表完整且无空串；⑪ 插件文件保持精确空壳；⑫ `profile.PORTS` 保留 `notes.reference`。（`tools/check_plugin_contract.py:995-1086`）`CASE_ORDER` 注入模式把 composite 拆成 projection-annotation / degraded-evidence 两案，所以显示为 14 案；它们不是第 13、14 条编号架构不变量。（`tools/check_plugin_contract.py:975-992`、`:1120-1167`）完整 AST/形状判据见同文件 `:101-215`、`:247-383`、`:399-472`、`:475-514`、`:517-704`。

★ 当前实跑 `python3 tools/check_plugin_contract.py` 的现场结果是 **13/13，exit 0**，其中是 **12 条编号不变量 + 1 条无编号 payload/DEGRADED composite**；它证明精确空壳与 12 条静态守卫通过，**不覆盖** `ResolutionView` / `ResolvedSurface` 的集成语义。（`tools/check_plugin_contract.py:975-992`、`:1010-1109`；`harmonica_eval/algorithms/runtime.py:89-131`）

## Optional 机制与 `ResolutionView`

- `contract.py` 的冻结现场：`ResolutionView` 是 frozen dataclass，字段为 `available` / `missing_optional`，唯一查询方法 `is_available()` 已实现；`AlgorithmDataContract` 只有 `manifest()` / `read()` 两个操作，另有只读 `resolution` 属性（属性不计入操作）。`contract_dataclasses` 的冻结计数为 **12**；`HarmonicaError` 是异常数据类，机械计数单列，不混入这 12 个契约 dataclass。（`harmonica_eval/contract.py:390-413`、`:654-685`、`:934-942`；`.spec/build/FILE-002-v1.md:78`；`tools/check_counts.py:365-397`）
- `InputResolution` 是 runtime 私有 frozen dataclass，字段顺序固定为 `available` / `missing_optional` / `incompatible_required`；`ResolvedSurface` 是组合适配器形状，字段 `_surface` / `_resolution`。按 `.spec/OWNER-DIRECTIVES.md` 指令 2（未授权前禁止注入），两者相关的 `as_view()`、`manifest()`、`read()`、`resolution`、`resolve_inputs` 与 `validate_result` 当前为 SHELL。（`harmonica_eval/algorithms/runtime.py:65-96`、`:99-131`、`:134-237`；`.spec/OWNER-DIRECTIVES.md:50-87`）

**★ 状态：optional 视图机制只传播到类型/形状层，没有实现或集成。** FILE-205 仍明确只授权两个函数、封闭八个 import、三名称 `__all__`（`.spec/build/FILE-205-v1.md:26-31`、`:57-75`、`:84-113`、`:458-472`）；`runtime.py` 当前全部相关实体入口仍是 `SHELL`，其中 `ResolvedSurface` 的 `manifest()` / `read()` / `resolution` **没有委托 return**。（`harmonica_eval/algorithms/runtime.py:89-131`、`:134-237`）Host 仍按直接 `entry(surface)` 编排，没有适配器接线（`.spec/build/FILE-301-v1.md:182-204`）。所以不能称 optional 机制已实现、已集成或已验收。

## 关键约束与不变量

- 插件只依赖契约，不反向 import Core/Host/Cockpit，也不横向认识其它算法实现。（`harmonica_eval/algorithms/__init__.py:22-27`；`tools/check_plugin_contract.py:187-215`）
- payload 是自描述 `Sequence[UiScalar | UiSeries]`，框架不维护按 `algorithm_id` 索引的字段表；新算法不能靠修改中央映射接入。（`harmonica_eval/contract.py:450-489`；`tools/check_plugin_contract.py:247-272`、`:317-333`）
- 算法不修改数据面、不跨会话持有端口指针、不依赖 process-global 可变单例；结果失败要隔离为信封而非穿透异常。（`COMPONENTS.md:223-255`；`harmonica_eval/contract.py:639-651`）
- `timing` 必须保留 `REFERENCE` 时间轴；`dynamics` 的按音配对不能退回错误的 WARPED 轴代理；`pitch` 不能 chroma 化。（`harmonica_eval/algorithms/timing.py:10-18`、`:51-56`；`harmonica_eval/algorithms/dynamics.py:35-53`；`harmonica_eval/algorithms/pitch.py:13-16`）
- v0.1 算法死循环没有超时机制，会卡住编排；这是现场已知缺口，不得被 README 隐去。（`COMPONENTS.md:250-257`；`harmonica_eval/host/app.py:182-195`）

## 相关规格

- C3 职责、保证、不变量：[`COMPONENTS.md` COMP-C3](../../COMPONENTS.md) §3、§4.2、§5、§7（`COMPONENTS.md:199-267`、`:324-342`、`:377-387`、`:433-442`）。
- 插件目录迁移提案（不是裁定）：[`.spec/PLUGIN-LAYOUT.md`](../../.spec/PLUGIN-LAYOUT.md) §0、§3、§4、§5、§6、§7（`.spec/PLUGIN-LAYOUT.md:10-25`、`:122-176`、`:180-245`、`:248-315`、`:318-338`）。
- C3 Build Instruction：
  - [`FILE-200-v1.md` §4 包出口](../../.spec/build/FILE-200-v1.md)（`.spec/build/FILE-200-v1.md:61-130`）
  - [`FILE-201-v1.md` §4.0–§4.4 pitch](../../.spec/build/FILE-201-v1.md)（`.spec/build/FILE-201-v1.md:66-383`）
  - [`FILE-202-v1.md` §4.0–§4.5 timing](../../.spec/build/FILE-202-v1.md)（`.spec/build/FILE-202-v1.md:55-232`）
  - [`FILE-203-v1.md` §4.0–§4.5 dynamics](../../.spec/build/FILE-203-v1.md)（`.spec/build/FILE-203-v1.md:66-215`）
  - [`FILE-204-v1.md` §4.0–§4.5 Registry](../../.spec/build/FILE-204-v1.md)（`.spec/build/FILE-204-v1.md:77-149`）
  - [`FILE-205-v1.md` §4.0–§4.4 runtime](../../.spec/build/FILE-205-v1.md)（`.spec/build/FILE-205-v1.md:82-194`）

## 已知缺口与未决项

- **🔴 GC-204-01：`HostApp` 的 `session_id` 不一致，G8 修正未向上层传播。** 契约要求所有会话级操作显式传 `session_id`（`harmonica_eval/contract.py:766-838`），而现场 HostApp 的 `set_reference`、`set_practice`、`build_surface` 不带 id，其他方法又带（`harmonica_eval/host/app.py:127-168`、`:182-225`）。**未裁定，阻塞 Cast Freeze。** 详见 `.spec/GATE-CHALLENGES-C3.md:12-86` 与汇总 `:449-464`。
- **✅ GC-204-08 已关闭（原「🔴 未裁定，阻塞插件迁移」）**：迁移提案曾建议独立 `bootstrap.py` 作为物理装配根，但长期标「待负责人裁定」，而 C3 又被禁止 import 具体算法——要 `registry.register(pitch/timing/dynamics)` 就必须 import 具体对象，两条同源要求在物理上不可同时满足。负责人 2026-09-24 裁定**方案甲**并落地：物理装配根为 `harmonica_eval/algorithms/bootstrap.py`，它是全系统唯一 import 具体算法模块的位置；端口需求（`ALGORITHM_INPUTS`）亦由该文件集中声明，各算法模块不自行导出 `SPEC`。台账状态为 `CLOSED`（`.spec/GATE-CHALLENGES-C3.md:544`、`:543`）。★ **裁定层已闭合，装配链尚未接通**：`bootstrap.py` 目前无任何模块 import，物理通路待 Host 注入后闭合。Host 侧口径已同步为「只接收 bootstrap 产出的 Registry」（`harmonica_eval/host/app.py:113-124`）。原冲突描述保留于 `.spec/GATE-CHALLENGES-C3.md:297-349` 作为决策历史；`.spec/PLUGIN-LAYOUT.md` 仍是**迁移提案而非裁定**，其「待裁定」措辞属提案自身的历史状态，不据此推翻已生效的裁定。
- **当前没有可执行注册清单/装配路径**：`__init__.py` 明确不构造 `PluginSpec` 或调用 `Registry.register`（`harmonica_eval/algorithms/__init__.py:39-55`；`.spec/build/FILE-200-v1.md:112-127`）；三个算法目录没有 `PluginSpec` 实例，故“源码依赖表”不是 Registry 的机器清单。（`.spec/PLUGIN-LAYOUT.md:122-149`、`:318-338`）
- **optional / `ResolutionView` 机制部分传播但未闭合**：现场契约和 runtime 已有 `ResolutionView`、`InputResolution.as_view()`、`ResolvedSurface` 形状，但 FILE-205 仍冻结旧的八 import/两函数/三名称出口，Host 仍直接调用 `entry(surface)`；按 `.spec/OWNER-DIRECTIVES.md` 指令 2（未授权前禁止注入），相关实体入口当前为 SHELL。（`harmonica_eval/contract.py:390-413`、`:654-678`；`harmonica_eval/algorithms/runtime.py:65-131`、`:240-246`；`.spec/build/FILE-205-v1.md:57-75`、`:458-472`；`.spec/build/FILE-301-v1.md:190-204`；`.spec/OWNER-DIRECTIVES.md:50-87`）**不能称为已实现、已集成或已验收。**
- **`timing` 源码/BI 端口声明漂移**：live 铭牌只明确两份 mapped PCM 与 `notes.reference`（`harmonica_eval/algorithms/timing.py:20-31`），FILE-202 的 `run` 却固定读取两侧 `notes.*`，并允许空侧时退回 mapped PCM（`.spec/build/FILE-202-v1.md:168-185`）。两种口径都至少依赖 `notes.reference`，但精确 required 集尚未统一。
- **✅ `timing` payload 单位冲突已裁定并消除，链路统一为 `seconds`**：此前 live 源码与 FILE-202 要求旧的毫秒单位，并写出不在封闭词表内的旧单位值，而冻结的 10 值 `UNITS_VOCABULARY` 不含该值；负责人现已裁定统一用秒。FILE-202 已将偏差计算改为秒减秒，死区 `23.0 / 1000 = 0.023` 秒，payload 单位改为 `"seconds"`，键名同步为 `per_note_onset_sec` / `median_onset_sec` / `spread_sec`，参数同步为 `deviations_sec`；`n_notes_used` 是无量纲计数且 `n` 仍是秒值序列的样本数，名称无需改。`UNITS_VOCABULARY` 仍为 10 项且未改。（`.spec/build/FILE-202-v1.md:57-64`、`:119-152`、`:167-191`；`harmonica_eval/algorithms/timing.py:20-26`、`:60-116`、`:157-200`；`harmonica_eval/contract.py:228-269`）**连带残留已全部收口**（`tools/check_reachability.py:79-80` 正向表已同步为 `deviations_sec` / `per_note_onset_sec`；`.spec/prompts/COMP-C3/downstream.md:73-78` 任务书已改秒并列出实际 payload 键；`.spec/build/FILE-002-v1.md:352-353` 数据通路映射已指向 `median_onset_sec`）。★ **两张同名性质的表不可混淆**：`tools/check_reachability.py` 的 `PRODUCED_QUANTITIES` 是**正向可达性表**（登记每个产出量的合法来源，随改名同步）；`tools/check_plugin_contract.py:48-64` 的 `FORBIDDEN_PAYLOAD_FIELDS` 是**负向禁入表**（禁止框架代码/注解认识任何具体 payload 字段名，**不能**机械替换——它在改名后仍须锁旧名以防回退）。★ 负向表已按其穷举全部具体字段的意图**同时加入新 `_sec` 具名**（旧名锁历史、新名锁当前），否则改名后的新名可被框架合法引用、该守卫等于失效（`.spec/build/FILE-202-v1.md:57-64`、`:119-152`、`:167-191`；`harmonica_eval/algorithms/timing.py:20-26`、`:60-116`、`:157-200`；`harmonica_eval/contract.py:228-269`）
- **`pitch` 的未配对音计数缺口**：现场 docstring 明确指出 pitch 的逐音配对可能失败，却没有像 timing/dynamics 那样报告 `n_unpaired`；读者无法区分“整首都测了”和“只测了少数音”。（`harmonica_eval/algorithms/pitch.py:144-153`）
- **算法死循环无超时**：当前会把整个流程卡住；这是 v0.1 已知边界，不是已完成隔离。（`COMPONENTS.md:250-257`；`harmonica_eval/host/app.py:187-195`）
- **陈旧 downstream prompt 不可作为当前依赖/注册依据**：它把 pitch/dynamics 放在 WARPED、让 timing 消费 `warp_path`，且把注册动作写进 `algorithms/__init__.py`（`.spec/prompts/COMP-C3/downstream.md:42-92`）；这与当前源码和 FILE-200/201/202/203 不一致，只能作历史材料。（`.spec/build/FILE-200-v1.md:112-127`、`:163-172`；`harmonica_eval/algorithms/__init__.py:6-27`）
- **🔴 GC-204-04 与后续 optional 视图设计未统一**：GC-204-04 已关闭，裁定保持单参数 `entry(surface)` 并让插件自行判断 optional 缺失（`.spec/GATE-CHALLENGES-C3.md:157-183`）；当前契约/BI 又引入 `resolution` / `ResolutionView` / `ResolvedSurface`（`.spec/build/FILE-003-v1.md:162-180`；`harmonica_eval/algorithms/runtime.py:89-131`）。这不是新挑战 ID，而是已关闭路线之后发生的源码传播漂移；按 `.spec/OWNER-DIRECTIVES.md` 指令 2（未授权前禁止注入），相关入口当前为 SHELL。（`.spec/OWNER-DIRECTIVES.md:50-87`）**应先裁定或同步上游材料。**
- **【未裁定】C2 `Surface` 继承了 `AlgorithmDataContract`，因此暴露了一个返回 `None` 的 `resolution`，而不是不提供该属性。** 契约 Protocol 有该只读属性（`harmonica_eval/contract.py:654-678`），C2 `Surface` 继承该 Protocol，因此 `Surface().resolution` 为 `None`（`harmonica_eval/core/surface.py:112-145`）。是否由 C3 的 `ResolvedSurface` 组合适配、该适配器归谁负责，尚未裁定；按 `.spec/OWNER-DIRECTIVES.md` 指令 2（未授权前禁止注入），相关入口当前为 SHELL。（`harmonica_eval/algorithms/runtime.py:65-131`；`.spec/OWNER-DIRECTIVES.md:50-87`；`.spec/build/FILE-003-v1.md:173-191`）**不能称为端到端能力。**

## 端口 hop 的读取通道（2026-09-24 裁定）

`pitch.*` / `rms.*` / `chroma.*` 三族端口的帧跳**只有一个读取通道**：

```python
from ..contract import hop_of
PITCH_HOP_LENGTH = hop_of("pitch.reference")
```

★ **三个算法都不再自带 hop 常量**：

| 模块 | hop 来源 |
|---|---|
| `pitch.py` | `contract.hop_of("pitch.reference")` |
| `timing.py` | `surface.manifest().ports[*].hop_length` |
| `dynamics.py` | `_descriptor("rms.reference").hop_length` |

★ **为什么不直接 import `profile`**：FILE-201 §8 判据 G 的 `ALLOWED` 不含
`profile`（只允许 `__future__` / `math` / `statistics` / `time` / `typing` /
`numpy` / `contract`）；★ 而 **`contract` 本就在 `ALLOWED` 内**，故无需放宽判据。

★ **权威源仍是 `profile.PORT_INDEX`**；`contract.PORT_HOP_LENGTHS` 是它的
契约层只读转供。★ **改 `profile` 里的 hop 而不同步契约层，或反之，
都会被 `FILE-201` §8 的交叉核对判据抓到。**

★ `hop_of()` 对帧概念不适用的端口（`pcm.*` / `notes.*` / `warp_path`）
抛 `KeyError` —— 宁可报错，也不要让「0」被误当成「零帧跳」而静默算出错误帧号。
