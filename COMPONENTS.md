# COMPONENTS — 组件总核验表 (v2)

> 归属：`SPEC.md` 之下。**本文件是自用工作记录（downstream 视图）**，不是给 L0 阅读的文档。
> L0 阅读版见 `docs/for-owner/组件设计-人类视图.html`。
>
> 依据：`AI_Software_Foundry_Constitution_CN.md`（下称"宪章"）。
> 关键遵循条款：§8 组件粒度 · §9 Virtual Component 可执行契约 · §12 顶层信息防火墙 ·
> §14 双视图 · §35 `Real ⊑ Virtual` · §43 Brownfield · §47 反模式

---

## 0. 本版相对 v1 的四处自我纠错

| # | v1 的问题 | 违反条款 | v2 的处理 |
| --- | --- | --- | --- |
| 1 | 把 `P000–P431`（约 34 个端口）写进 L1 契约 | §8 停止下钻判据：L1 应停在 Component。端口清单是 **C2 的内部设计**（L2 领域） | 端口目录降为 **C2 内部产物**；L1 契约只承诺"一份自描述只读数据面 + aligned PCM" |
| 2 | 用 7 栏散文表格描述组件 | §9：Virtual Component 必须是**可执行契约**，含 `virtual_behavior` 等字段；散文表格属 §47.12 Document Theater | 改为宪章规定的 YAML schema，逐字段填实 |
| 3 | 把"检验站"当作待裁决项之一 | §36 + §20 + §6-L5：验证是**铸造厂的角色**，不是产品组件 | 移出组件表，归入铸造厂角色体系 |
| 4 | 遗留 6 个未决裁决点 | §31：Freeze 前 `Critical unresolved design questions = 0` | 5 项在 L1/L2 归位后**消解**；1 项升级为 L0 决策 |

---

## 1. 口径

**Component = 可以独立建立契约的责任单元**（宪章 §8）。

**停止下钻判据**（宪章 §6-L1）：*当一个组件已经可以作为黑盒被独立承包，另一个模型只看它的契约就能继续完成内部设计时，L1 应停止下钻。*

以下**不是组件**（各自归位）：

| 被剔除项 | 归位 | 依据 |
| --- | --- | --- |
| 端口目录 `P000–P431` | **C2 内部设计**（L2） | §8 停止下钻 |
| Canonicalizer / Alignment / Materializer / Port Store / Foundry | C2 内部模块 | 外部不可见 ⇒ 无独立契约 |
| 算法执行编排 | **C1 的职责**（非组件） | 见 §3 保证 G2 |
| Asset Manager / Result Store | C1 会话内状态 + C2 内部 | 同上 |
| 动态插件系统（`.dylib`/扫描/ABI discovery/版本协商） | v0.1 不做 | 用户裁定。★ C3 插件化后此裁定**不变且更有约束力**：v0.1 的"插件"只表示"遵守统一契约、显式 `Registry.register`、可由 Host/UI 按 id 选择的逻辑算法组件"，**不涉及任何动态装载机制**。目录扫描、entry-points、热加载、进程隔离全部永不做 |
| **检验站（评测台）** | **铸造厂 L5 验证角色 + Evidence** | §36、§20、§6-L5 |
| `chroma_cens` / DTW / CREPE / pyin 具体算法 | **C2、C3 的内部选型**（L2） | §43：冻结行为，不冻结结构 |

---

## 2. 拓扑（4 组件 / 2 契约 / 1 配置）

```text
                 ┌───────────────────────────┐
                 │  C1  Framework / Host      │
                 │  生命周期 · 编排 · 状态      │
                 └────┬─────────────────┬────┘
      CONTRACT-HOST-v1│                 │UI Command / UI View
                      │                 │
                      ▼                 ▼
        ┌──────────────────────┐   ┌────────────────┐
        │  C2  Audio Core      │   │ C4 Dev Cockpit │
        │  （唯一核心）          │   │  只读投影        │
        │                      │   └────────────────┘
        │  内部全隐藏：          │
        │   标准化 / 对齐 /      │
        │   数据面生成 / 端口目录  │
        └──────────┬───────────┘
                   │ CONTRACT-ALGORITHM-DATA-v1
                   │ （只读 · Seal 后不可变）
                   ▼
        ┌──────────────────────┐
        │  C3  Algorithm        │
        │  v0.1 仅一个实例       │
        └──────────────────────┘

配置输入（不是组件）：CORE_PROFILE_V0.1 —— 决定 C2 生成什么
```

**关键 gate**：C3 永远不得在 `DATA_READY` 之前触发。
`DATA_READY` = *完整数据面已按 profile 构造并 Seal*，**不是**"YIN 要的数据好了"。

---

## 3. 四个 Virtual Component（宪章 §9 schema）

### COMP-C1 — Framework / Host

```yaml
component_id: COMP-C1
purpose: 承接平台与人类意图，驱动一次完整分析会话，把结果交给 UI
responsibilities:
  - 应用生命周期；文件/麦克风接入（平台能力）
  - 创建/销毁会话；驱动运行；发布状态
  - 算法执行编排（决定跑哪些算法实例、按什么顺序）
  - 把平台与内部异常归一化为统一错误码
  - 作为 composition root 完成 C2/C3 的装配
non_responsibilities:
  - 不做 DSP；不做对齐；不解析数据面内部结构
  - 不实现算法；不判断算法对错；不读端口内容
  - 不持有 C2/C3 内部符号（只传不透明句柄）
requires: []
provides:
  - CONTRACT-HOST-v1（对 C2 的调用方）
  - UI Command / UI View（对 C4 的服务方）
inputs: [用户命令, 平台回调（文件 URL / 权限）]
outputs: [会话状态, UI 可视化投影, 对 C2 的调用]
assumptions:
  - 平台能提供可读的文件字节流或麦克风采样
  - 单机、单会话串行；v0.1 不要求并发多会话
guarantees:
  - G1 状态单调推进，不跳过 DATA_READY 直接触发算法
  - G2 编排逻辑只存在于 C1；C2 与 C3 互相不可见
  - G3 任何失败都归一化为显式错误码，不泄漏内部异常/堆栈
state_model: CREATED → INPUT_READY → BUILDING → DATA_READY → CLOSED
             （任一状态可 → FAILED）
★ 更正：原写 …DATA_READY → RUNNING → RESULTS_READY → CLOSED，
  但 contract.SessionState 只有 6 个取值，**没有** RUNNING / RESULTS_READY。
  算法运行结果体现在 AlgorithmResultEnvelope.status，不是会话状态 ——
  故「跑算法」不产生新会话状态。
invariants:
  - INV-C1-1 不读取端口缓冲区内容
  - INV-C1-2 不 import C3 的算法实现模块（只依赖契约）
  - INV-C1-3 删除 C4 后，C1/C2/C3 仍能无头跑通
failure_modes:
  - 文件不可读 / 权限拒绝 → FAILED + 原因码
  - 「用户取消」不属失败：若指会话 `CANCEL`，按 `COMMAND_EFFECTS` 转移、不产生 `ErrorCode`、状态不是 `FAILED`；若指文件选择对话框取消，则不进入本组件，也不产生 `ErrorCode`
  - C2 构建失败 → FAILED，如实上报，不重试、不降级、不伪造结果
recovery_semantics: 会话不可续；重新 create_session 从头开始。v0.1 不做断点续算
side_effects: 读取平台文件；占用会话资源；不写用户数据
performance_budget: "待 SPIKE 测量（见 §6）；v0.1 目标是零 DSP 开销，仅编排与状态"
resource_budget: "O(1) 业务状态 + 句柄；不持有音频数据"
security_boundary: 唯一允许接触平台文件系统与权限的组件；C2/C3 默认无文件与网络访问
dependencies: → C2（必须）；→ C4（可选）
acceptance_scenarios:
  - AS-C1-1 正常两段音频 → DATA_READY，各算法各自返回 status='OK' 的信封
  - AS-C1-2 C4 缺席时同一条 Mission Thread 仍完成
  - AS-C1-3 C2 构建失败 → FAILED，且未触发任何算法
virtual_behavior: |
  以脚本化状态机替代真实平台：按固定脚本推进状态，音频资产用夹具字节流。
  C2 用虚拟件（返回固定合成数据面），C3 用虚拟件（返回固定结果信封）。
  可在零真实 DSP 下跑通完整 Mission Thread。
```

### COMP-C2 — Audio Core（唯一核心）

```yaml
component_id: COMP-C2
purpose: 把两段输入音频编译成一份完整、不可变、与算法无关的标准分析数据面
responsibilities:
  - 接收两段原始音频并标准化（采样率/声道/数值表示/时间原点）
  - 建立两段之间的时间映射
  - 实体化两套对齐表示：保留源时间（mapped）+ 时间归一化（warped）
  - 按 CORE_PROFILE_V0.1 固定 DAG **全量**生成数据面
  - Seal 后提供只读、自描述的受控访问
non_responsibilities:
  - 不做 UI；不做教学评分；不判断吹得好不好
  - 不实现任何具体音高算法
  - 不知道有哪些算法被装载；不知道算法是否存在
  - 不持久化 UI 状态
requires: [两段音频资产（不可变）, core_profile_version]
provides:
  - CONTRACT-HOST-v1（状态 / 句柄）
  - CONTRACT-ALGORITHM-DATA-v1（只读自描述数据面）
inputs: [Reference AudioAsset, Practice AudioAsset, core_profile_version]
outputs: [Surface（实现 AlgorithmDataContract 的只读对象，不可变逻辑数据空间）]
assumptions:
  - 两段音频内容为同一首曲子的两次演奏（这是产品前提，不校验）
  - 输入为可解码的常见音频格式
  - 单进程内访问；v0.1 不做跨进程共享数据面
guarantees:
  - G4 数据面内容仅是 (reference, practice, profile_version) 的函数，与算法装载完全无关
  - G5 数据面 Seal 后不可变；任何角色都无写权限
  - G6 数据面**始终**包含两份 aligned PCM（mapped + warped）作为通用底座
  - G7 数据面自描述：外部通过 manifest 枚举端口，无需预知端口清单
  - G8 输出符合 CORE_PROFILE_V0.1 的冻结契约（schema/维度/单位/时间基准/采样率）
  - G9 任何改变时间坐标的内部操作都记录在案，不静默 trim
state_model: CREATED → INGESTING → CANONICALIZING → ALIGNING → MATERIALIZING
             → BUILDING_SURFACE → SEALING → DATA_READY / FAILED → CLOSED
             （这些状态**不向 C1 暴露**；C1 只看到 INPUT_READY / BUILDING / DATA_READY）
invariants:
  - INV-C2-1 profile 未变 + 输入未变 ⇒ 数据面内容不变（同 build）
  - INV-C2-2 端口一经 Seal 不可写
  - INV-C2-3 不 import C1/C3/C4 的任何符号
failure_modes:
  - 输入不可解码 / 过短 / 静音 → CORE_BUILD_FAILED
  - 对齐无法建立有效映射 → CORE_BUILD_FAILED
  - 构建中断 → CORE_BUILD_FAILED
recovery_semantics: |
  不发布 DATA_READY，不触发任何算法，不保留半成品数据面；资源全部释放。
  重建须新建会话。
side_effects: 计算资源占用；可选落盘缓存（不得改变语义）
performance_budget: "**已实测**（§10）：3 分钟音频构建 0.34 s；profile 规模 95.5 MB。手机端待真机复测"
resource_budget: "**已实测**（§10）：底座+小特征共 95.5 MB（3 分钟）。手机端待真机复测；mmap 后备存储已非必需"
security_boundary: 无网络；只读访问输入资产；不接触平台文件选择器
dependencies: 无（不得依赖 C1/C3/C4）
acceptance_scenarios:
  - AS-C2-1 装 0 个算法与装 N 个算法，数据面端口清单与各端口 content_hash 一致
  - AS-C2-2 profile 版本变化 ⇒ 数据面变化（证明 profile 在因果链上）
  - AS-C2-3 端口 schema/维度/单位/时间基准/采样率全部可校验
  - AS-C2-4 输入静音 ⇒ CORE_BUILD_FAILED 且无 DATA_READY
virtual_behavior: |
  用确定性合成数据面替代真实 DSP：按 profile 生成形状正确、内容已知的端口
  （正弦 PCM、常量谱、递增能量）。下游可在真实 DSP 存在前完成端到端验证。
  虚拟件必须遵守同一 manifest 契约，故可作为 Real ⊑ Virtual 的对照基准。
```

### COMP-C3 — Algorithm

```yaml
component_id: COMP-C3
purpose: 消费标准数据面，返回标准算法结果
responsibilities:
  - 从数据面读取自己需要的端口
  - 完成一个独立算法能力
  - 返回 AlgorithmResultEnvelope
  - 自报本次实际消费了哪些端口（consumed_ports）
non_responsibilities:
  - 不管理音频生命周期；不做对齐；不碰 UI/平台 API
  - 不请求 C2 生成新数据
  - 不访问文件系统固定路径；不访问网络
  - 不修改任何端口数据
requires: [只读数据面视图]
provides: [AlgorithmResultEnvelope]
inputs: [PortDescriptor + BufferView + timeline_basis + sample_rate]
outputs: [AlgorithmResultEnvelope]
assumptions:
  - 所需端口已在 manifest 中声明且存在（否则不启动）
  - 数据面在其运行期间保持有效（Seal 后不可变，故天然成立）
  - 不被保证 UI 线程；不假设调用时序
guarantees:
  - G10 只读；绝不修改数据面
  - G11 不依赖 C2/C1 内部符号，只依赖契约
  - G12 失败被隔离：自身 FAILED 不影响数据面与其他算法
  - G13 声明 required_inputs / optional_inputs 仅用于兼容性检查，
        绝不反向触发 C2 生成数据
state_model: 无独立状态机。算法是**无状态**的：
             entry(surface) 一次调用内完成，结果状态体现在
             AlgorithmResultEnvelope.status ∈
             {'OK','DEGRADED','INCOMPATIBLE','FAILED'}
★ 更正：原写 CREATED → COMPATIBILITY_CHECKED → RUNNING → RESULTS_SUBMITTED/FAILED。
  但代码里没有这些状态，也没有算法状态机 —— C3 的插件契约
  （PluginSpec）只有 algorithm_id/algorithm_version/label/required_inputs/
  optional_inputs/entry 六个字段，全部是**声明**，不含任何生命周期状态。
★ C3 插件化补充：status 域由 3 值扩为 4 值，新增 DEGRADED，
  用于表达"optional 输入缺失导致只提供部分能力"。它不是新状态机，
  只是让"少算了"这件事在结果里有正式位置可写，不再被迫报 OK。
invariants:
  - INV-C3-1 不持有跨越会话生命周期的端口指针
  - INV-C3-2 不依赖 process-global 可变单例
  - INV-C3-3 结果符合声明的 result_schema
  - ★ INV-C3-4 payload 必须是自描述的 Sequence[UiScalar | UiSeries]，
        不得返回裸 dict —— 裸 dict 需要框架侧维护一张按 algorithm_id
        索引的字段名表，那张表会让框架必须认识每一个具体算法，
        从而使"新增算法必须改框架文件"（本组件 v1 的实际缺陷）
  - ★ INV-C3-5 status == 'DEGRADED' 时必须伴随 coverage 非空或
        warnings 非空；否则判 ALGORITHM_RESULT_INVALID
        （把"不许偷偷少算"变成可机械验证的断言）
failure_modes:
  - 崩溃 / 死循环 / NaN / 非法 schema / 无界内存 / 超大结果
recovery_semantics: |
  v0.1 最小实现：异常捕获 + schema 校验 + 结果大小上限。
  **超时与内存硬上限明确留待 v0.2**（当前死循环算法会卡住 Rack —— 已知缺口，不隐瞒）
side_effects: 计算资源占用
performance_budget: "未测；v0.2 需要每算法超时预算"
resource_budget: "未测；v0.2 需要每算法内存上限"
security_boundary: 无文件系统、无网络、无 UI；只读数据面
dependencies: 只依赖契约。`algorithms/` 可依赖契约，`core/` 不得 import `algorithms/`（在 C1 装配）
acceptance_scenarios:
  - AS-C3-1 同一数据面上两个算法可并存且结果可比对
  - AS-C3-2 故障注入（崩溃/NaN/超大结果）后数据面与其他算法仍有效
  - AS-C3-3 声明不存在的端口 ⇒ INCOMPATIBLE，且 C2 未重新生成任何数据
virtual_behavior: |
  返回固定形状的结果信封（如常量音高曲线），用于端到端验证结果通路。
  虚拟算法与真实算法遵守同一 envelope 契约。
```

### COMP-C4 — Developer Cockpit（Mac 本机开发者视图）

> ★ **命名更正（由下往上核对代码时发现）**：
> 本节标题原为 **"Web Cockpit"**，但代码与负责人裁定都不是 Web：
> - `cockpit/__init__.py`：入口 `launch_cockpit()`，产出是「**本机进程内的开发者视图**」
> - `cockpit/app.py`：自称「**Mac 端开发者调试界面**」，函数名 `run_local_ui`
> - 负责人裁定：「Mac 端上面只用给开发者看，会把核心彻底调试完，再移到手机端」
>
> `web` 是 v1 设想的残留。**组件边界没变，只是名字** ——
> 但名字会误导实现者去找 Web 框架、加 HTTP 服务，那是 SPEC §1 边界禁止的。
> 手机端是未来事项，不在 v0.1 范围。

```yaml
component_id: COMP-C4
purpose: 人类操作与观察界面
responsibilities: [文件选择与运行控制, 波形/曲线/叠加展示, 算法参数调试]
non_responsibilities:
  - 不进入音频计算热路径；不保存 Core 状态
  - 不执行 DSP；不直接读数据面；不解释算法内部
requires: [C1 发布的会话状态与可视化投影]
provides: [UI Command]
inputs: [会话状态, 可视化投影]
outputs: [UI Command]
assumptions: [运行于 Mac 开发/测试环境；v0.1 不面向终端用户]
guarantees:
  - G14 只与 C1 通讯，不直连 C2/C3
  - G15 其崩溃或断开不影响已 Seal 的数据面与已产出的结果
state_model: 无持久状态（纯视图）
invariants: [INV-C4-1 不持有音频或数据面缓冲]
failure_modes: [UI 崩溃 / 断开]
recovery_semantics: 重新加载 UI 并重新订阅 C1 状态；会话不受影响
side_effects: 无
performance_budget: 投影数据量受限（由 C1 提供的下采样投影决定）
resource_budget: 不持有音频缓冲
security_boundary: 不接触文件系统与网络（经 C1 代理）
dependencies: → C1（唯一）
acceptance_scenarios:
  - AS-C4-1 删除 C4 后 Mission Thread 仍完成（不变量 F）
virtual_behavior: 静态页面 + 脚本化命令序列；可在无真实 C1 时用夹具状态渲染
```

---

## 4. 两条契约 + 一份配置

### 4.1 CONTRACT-HOST-v1（C1 ↔ C2）

| 项 | 内容 |
| --- | --- |
| 操作 | `create_session(profile_version)` / `set_reference(asset)` / `set_practice(asset)` / `build_surface()` / `status()` / `acquire_surface()` / `destroy_session()` |
| 暴露状态 | `CREATED` / `INPUT_READY` / `BUILDING` / `DATA_READY` / `FAILED` / `CLOSED`（C1 不需知道内部阶段） |
| 禁止 | `align()` / `fft()` / `generate_pitch_input()` / `prepare_for_*()` / `generate_plugin_requirement()` |
| 必须包含 | `core_profile_version` —— 没有它"同一对输入"不成立 |
| 资源所有权 | Core 拥有 Core 缓冲；`AlgorithmDataContract` 句柄有效期至 `destroy_session` |

### 4.2 CONTRACT-ALGORITHM-DATA-v1（C2 ↔ C3）—— 本版深化

**接口只有两个操作**（这是"深组件"的落点）：

```text
AlgorithmDataContract.manifest()    → SurfaceManifest     # 自描述，列出端口
AlgorithmDataContract.read(port_id, range) → BufferView    # 零拷贝或分块视图
```

| 项 | 内容 |
| --- | --- |
| `PortDescriptor` | `port_id, schema_version, element_type, dimensions, shape, units, field_names, timeline_basis, hop_length, sample_rate, content_hash`（11 个） |
| `BufferView` | `data, element_count, element_type`（3 个）——★ **无 `stride` 字段**；视图连续性由 `data` 自身 strides 表达 |
| 强制保证 | 两份 **aligned PCM** 永远存在（mapped + warped）——本仓自定保证，算法可自行做特有预处理 |
| `timeline_basis` | 每端口必须声明：参考时间轴 / 归一化时间轴 |
| **必须包含 `sample_rate`** | 实测依据：同一段音频在 22.05 kHz 下 pYIN 把 D5 判成 D4（恰好 −1200 音分），44.1 kHz 下正常。**采样率是算法结果的成因，不是元数据** |
| 内存规则 | Core 拥有 Core 数据；算法只可借用，不得释放、不得修改、不得跨会话保存指针；结果所有权移交 Result 侧 |
| 兼容性 | ★ C3 插件化后，插件声明的是 `InputRequirement`（含时间轴 / dtype / 字段 / 采样率等**语义**约束），不只是端口名存在与否；缺 `required_inputs` 任一条即 `INCOMPATIBLE`，**绝不反推 C2 生成**。`optional_inputs` 缺失允许运行，但须 `DEGRADED` 并在 warnings / coverage 中如实说明 |

### 4.3 CORE_PROFILE_V0.1（配置，不是组件）

**这是本版最重要的收敛**：宪章要求"全量生成"，但**"全量"是相对于冻结 profile 的，不是相对于想象的**。
profile 定义多少，就全量生成多少。于是"必须全量生成"与"手机跑得动"不再冲突——
**它是 L0/L1 的 trade-off，而不是教义冲突。**

v0.1 profile（**已由 SPIKE 裁定**，见 §6/§10）：

```text
输入标准化：mono / float32 / 44100 Hz
对齐表示：mapped（源时间保留）+ warped（时间归一化）
通用底座：aligned PCM ×2（强制，且永远存在）
小特征端口（预加工）：RMS 能量包络、低分辨率 chroma
频谱类端口：**冻结定义**（n_fft / hop / window / 单位 / 时间基准）
            但**不预存字节**；按需实体化 + 缓存
```

**核心机制：冻结定义 ≠ 预存字节。**

| | 冻结定义（契约） | 按需实体化（实现） |
| --- | --- | --- |
| 内容 | "本系统的幅度谱 = 2048/512/Hann" | 何时真正算出并缓存字节 |
| 作用 | 保证跨算法**可比** | 保证内存不随 profile 膨胀 |
| 归属 | L1 契约 | L2 实现自由 |

**实测依据**：预存一档频谱占 51 MB 只省 65 ms；3 分钟尺度**每省 1 秒付 778 MB**。
故"预存"被实测淘汰，"冻结定义"独立成立并已足够。

（v1 草案里的"三档 STFT + 三档 frame bank + flux + zero crossing"是**照着算法采购单归纳的愿望清单**，
属于 L2 越权，已撤回。它应由 L2 在测得预算后按需提出——§10 已给出这个测量。）


---

## 5. 不变量与验证

| ID | 不变量 | 验证方式 | 层级 |
| --- | --- | --- | --- |
| **A** | 同一输入 + 同一 profile ⇒ 数据面与算法装载无关 | 装 0 个 vs 装 N 个算法，比对端口清单 + content_hash（同 build） | 契约 |
| **B** | 换算法 ⇒ Core 0 修改 | 依赖方向测试：`core/` 不得 import `algorithms/` | 契约 |
| **C** | 新增算法不改处理 DAG | ★ **已从"约定"变成可机械判定**：新增插件只允许写 `algorithms/<name>/` 与在**物理装配根 `algorithms/bootstrap.py`** 装配点多一行 `registry.register(...)`（2026-09-24 裁定，GC-204-08 已 CLOSED）；`core/` 与 `host/` 均不得 import 具体算法实现模块；框架不得出现按 algorithm_id 索引的 payload 字段表。三条全部可由 AST 静态判定，见 `tools/check_plugin_contract.py` | 契约 |
| **D** | 任一算法失败不影响数据面与其他算法 | 故障注入（崩溃/NaN/超大结果/死循环） | 契约 |
| **E** | **每个端口产出符合其冻结契约** | schema/维度/单位/时间基准/采样率校验 + 黄金向量 | 契约 |
| **F** | 删除 C4，其余三件仍跑通 | 无头 Mission Thread | 系统 |
| **G** | **`Real(C) ⊑ Virtual(C)`** | 同一 Mission Thread 分别在虚拟件/真实件上运行，外部可观察行为一致 | 实现（宪章 §35） |

> **A 与 E 的关系（v1 曾混淆）**：A 是"同一 build 两次运行一致"的**回归断言**，
> 不能作为跨实现、跨平台的验收标准——浮点 FFT 换库版本或换架构不会 bit-identical。
> 真正检验"模具合格"的是 **E**；A 是 E 的加强特例。

---

## 6. 资源预算（**已实测**，见 §10）

3 分钟音频、44.1 kHz、mono、float32 的解析估算与实测对照：

| 项 | 单信号 | 说明 |
| --- | --- | --- |
| PCM（1 份） | 31.8 MB | 180 s × 44100 × 4 B |
| PCM ×3（mapped ref/prac + warped prac） | 95.3 MB | ref-warped ≡ mapped ref |
| STFT 幅度（n_fft=2048, hop=512, float32） | 63.6 MB | 15504 帧 × 1025 bin × 4 B |
| STFT 幅度双信号 | 127.1 MB | |
| STFT **复数**双信号（若需相位） | 254.2 MB | hop 减半则翻倍 |

**实测确认**（§10）：数据面字节数是纯算术量，估算与实测偏差 −0.0%，可信。

**⚠ 更正（负责人裁定）**：原「频谱只冻结定义、按需实体化」**已否决**。
理由：惰性计算要求 Core 为算法现场算数据，**必须附带一套协商协议**
（特征声明→解析→版本→缓存失效→失败语义）；一旦有了那套协议，
**Core 的外部接口就成了插件需求的函数**——正是要避免的反模式。

**现行裁定**：
> **Core 预生成。端口清单封闭（写死在 profile）。**
> 算法适配 Core，不是 Core 适配算法。
> 算法若需额外数据，**从数据面里的 PCM 自己算**，不许要求 Core 提供。

实测数字（127 MB / 65 ms）**仍然有效**，但用途降级为**选一个参数**（对齐分辨率），
不再参与架构决策。

**澄清（L0 已提出该疑问）**：profile 预加工**不是转码成不同文件格式**，而是同一时间轴上的
不同**数值视图**（幅度频谱 / 能量包络 / CQT / Mel / chroma…）。
且因两份 aligned PCM 永远存在，**profile 只决定"快不快"，不决定"能不能"**——
算法永远可以拿 PCM 现场自算。profile 不可替代的价值在于**统一口径**。

**关键推论**：既然要统一的是**口径（定义）**而非**字节（存储）**，
那么"冻结定义 + 按需实体化"同时满足宪章 §9 契约要求与内存约束，
**不牺牲任何保证**。这是本版最重要的设计收敛。

---

## 7. 失败语义（三类完全隔离）

| 失败 | 归属 | 系统状态 | 数据面 | 其他算法 |
| --- | --- | --- | --- | --- |
| 输入不可解码 / 过短 / 静音 | C2 | `CORE_BUILD_FAILED` | 不存在 | 不启动 |
| 对齐无法建立有效映射 | C2 | `CORE_BUILD_FAILED` | 不存在 | 不启动 |
| 算法要求未知端口 | C1 判定 | `PLUGIN_INCOMPATIBLE` | **有效** | 正常运行 |
| 算法崩溃 / 非法结果 | C3 | 该算法 `FAILED` | **有效** | 正常运行 |
| 算法死循环 | C3 | **未解决**（v0.2 超时） | 有效 | **会卡住** |
| UI 断开 | C4 | 会话继续 | 有效 | 正常 |

---

## 8. 未决项（升级给 L0 或留待 L2）

| # | 项 | 归属 | 状态 |
| --- | --- | --- | --- |
| 1 | ~~**CORE_PROFILE_V0.1 的端口规模**~~ | L1 | **已实测收敛**，见 §6 与 §10。裁定：底座 PCM + 小特征；频谱类**只冻结定义、按需实体化** |
| 2 | 资源与延迟预算数值 | L1 | **已实测**（Mac）。手机端真机验证仍待做 |
| 3 | 是否需要相位（决定内存翻倍） | L2 | **已折叠**：相位不预存，需要者从 PCM 现算 |
| 4 | 对齐算法选型 | **L2**（C2 内部） | 已消解：L1 只承诺"产出有效映射"，方法由 profile 钉住 |
| 5 | 端口精确参数（n_fft/hop/window） | **L2**（C2 内部） | 已消解：定义由 profile 冻结，实体化时机由实现定 |
| 6 | ~~`SPEC.md` §5/§7 仍写死具体算法~~ | L0 | **已裁定并执行**：负责人选「重写：只冻结行为，不冻结结构」。§5/§7 已改为行为契约，具体算法降为 L2 实现选型。仓库现在只有一个权威分层：SPEC 管行为，COMPONENTS 管结构与契约 |

---

## 9. 本次已消解 vs 仍阻塞

**已消解**：端口目录层级错位、契约形式不合规、验证角色错位、SPEC 算法焊死、
对齐选型归属、端口参数归属、C4 定位、检验站定位、**Core 资源预算（已实测）**。

**Freeze 条件（宪章 §31）现状**：本机（Mac）层面逐条已满足。
**唯一保留边界**：实测在 Mac 完成，手机端需真机复测；这是 v0.1 的已知验证缺口，
不是设计未决问题。

---

## 10. SPIKE 实测结果（补 §6 的账）

脚本：`harmonica_mvp_dataset/spike_core_memory.py`、`harmonica_mvp_dataset/spike_port_economics.py`
输出：`data/out/spike_core_memory.json`、`data/out/spike_port_economics.json`
输入：第 1 首真实口琴音频 72.802 s @ 44.1 kHz mono float32（无随机性，固定路径）

### 11.1 解析估算 = 实测（字节数）

| profile（180 s 外推） | 估算 | 实测 | 偏差 |
| --- | --- | --- | --- |
| 最小（1 档谱） | 222.4 MB | 222.3 MB | −0.0% |
| 中等（3 档谱） | 476.7 MB | 476.5 MB | −0.0% |
| 愿望清单 | 1493.0 MB | 1492.8 MB | −0.0% |

**结论**：数据面字节数是纯算术量，估算可信。真正的信息在下一节。

### 11.2 关键发现：预存频谱的经济性极差

| 端口 | 双信号占用（72.8 s） | 现算耗时 | MB / 省下 1 ms |
| --- | --- | --- | --- |
| 幅度谱 2048/512 | 51.4 MB | 65 ms | **0.79** |
| 幅度谱 1024/256 | 51.5 MB | 65 ms | 0.79 |
| 幅度谱 4096/1024 | 51.4 MB | 65 ms | 0.79 |
| RMS 能量包络 | 0.05 MB | 0.9 ms | 0.053 |
| 低分辨率 chroma | 0.035 MB | 6 ms | 0.006 |

3 分钟尺度：**每省 1 秒需付 778 MB**。这是荒谬的交易。

### 11.3 由此得到的 profile 裁定（替代 v2 草案）

> **`CORE_PROFILE_V0.1` = aligned PCM ×2 + RMS 能量包络 + 低分辨率 chroma**
> 频谱类端口**只冻结定义（n_fft/hop/window），按需实体化并缓存**。

- 规模：3 分钟音频约 **95.5 MB**（原"最小"222 MB → 降 57%）
- 构建耗时：**0.34 s**（3 分钟）
- **不牺牲任何保证**：可比性来自"冻结定义"，而非"预存字节"。
  即宪章 §9 的契约可以只声明 *语义*，实体化时机属实现自由。

### 11.4 诚实边界

- 测的是 **Core 数据面构建成本**，**不是算法成本**。
- 本机为 Mac；**手机端未测**。
- 真实音频为单声道口琴独奏（无伴奏），多声部混合场景未覆盖。

---

---

## 11. 信息熵账本（"深组件"的量化）

| | v1 | v2 |
| --- | --- | --- |
| 读者须记住的**组件** | 4（+8 个伪组件） | **4** |
| 读者须记住的**契约** | 2（但其中 1 份枚举 ~34 端口） | **2**（每份 2–7 个操作） |
| 算法侧接口操作数 | ~34 端口逐一理解 | **2**（manifest / read） |
| 须记住的**配置** | 0（隐含） | **1**（`CORE_PROFILE_V0.1`） |
| L1 层未决问题 | 6 | **0**（已全部消解或实测收敛） |
| **L1 认知负荷合计** | ~48 项 | **~9 项** |

**深组件的判据**：C2 的外部接口 = 7 个 Host 操作 + 2 个数据面操作；
而其内部（标准化 + 对齐 + 双表示实体化 + profile 驱动的数据面生成 + 端口存储）全部隐藏。
**接口小、实现深** —— 这是宪章 §8/§9 与"降低信息熵"的共同落点。
