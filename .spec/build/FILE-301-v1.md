# FILE-301 — host/app.py

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/host/app.py`
> 生成依据：`contract.py`（HostContract / UiProjectionPort / UiView / UiScalar /
> UiSeries / UiCommand / UiCommandKind / COMMAND_LEGALITY / COMMAND_EFFECTS /
> UI_PAYLOAD_KEYS / SessionState / ErrorCode / AlgorithmResultEnvelope）·
> `COMPONENTS.md §3 COMP-C1 / §5 不变量` · `SPEC.md §1` · `PLAN.md `
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-301 |
| 所属组件 | COMP-C1 Framework / Host |
| 层级 | L3（symbol / implementation） |
| 上游 | `__main__.py`（无头）或 `cockpit`（有界面）驱动 |
| 下游 | C2 经 `HostContract`（**只经契约**）；C3 经 `algorithms.ALGORITHMS` |
| 同层邻居 | `host/__init__.py`（包出口，无逻辑） |

### ★ 先弄清你的身份（这一条曾导致盲审误读）

本类**不是** `HostContract` 的实现类，而是它的**消费方**：

```
HostContract       C1 → C2 的接口，由 **C2** 实现（core/api.py: HostCore）
UiProjectionPort   C1 → C4 的接口，由**本类**实现
```

所以 `HostApp` 的方法集合**本来就不该**等于 `HostContract` 的 7 个操作。
它额外拥有 `run_algorithms` / `check_compatibility` / `normalize_error` /
`build_view` —— 这恰恰是 C1 存在的理由（它拥有编排权，不是转发层）。

**你的权限**：只实现本文件。不得修改 `contract.py` / `profile.py` /
`core/*` / `algorithms/*`，不得新增端口，不得新增第三方依赖。

---

## 2 · 这个文件为什么存在

去掉它会必然发生两件事之一：

1. **C2 得知道有哪些算法** → 深组件被破坏，Core 变成插件需求的函数
   （正是负责人裁定要消灭的反模式）
2. **C4 直接调 C2/C3** → 界面进入计算路径，UI 崩溃会污染数据面

所以 C1 的职责是具体的、不可省的：持有会话、驱动状态机、调算法、
归一化失败、产出投影。删掉本文件，全系统没有任何地方知道
"先建数据面、再跑算法、再出视图"这个顺序。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：
- 标准库：`time`（`perf_counter`）, `pathlib`（`Path`）, `typing`
- 第三方：无（**不引入任何第三方**）
- 本包内：`..contract`（上面列出的全部类型与常量）、`..algorithms.ALGORITHMS`
  —— ★ 这是**全系统唯一允许的跨界 import**（C1 是装配点，它必须知道有哪些算法）

**禁止 import**：
- `..core.*`（C1 只经 `HostContract` 与 C2 对话，不认其内部实现）
- `..cockpit.*`（不变量 F：C4 缺席时本文件必须照常工作）
- **任何信号处理库**：`numpy` / `scipy` / `librosa` / `soundfile` 一律禁止
  （见 §7）

---

## 4 · 你要实现什么（行为规格）

### 4.0 模块常量

```python
MAX_PROJECTION_POINTS: int = 2000
```

依据：人类不得面对几十万个数据点。120 s 音频在 hop=256 下有约 2 万帧。
**下采样是投影的职责，不是界面的职责**（界面不得重算）。

**不要写端口清单镜像常量**：C1 需要的端口信息来自
`algorithms.ALGORITHMS[i].required_ports` 与 `surface.manifest()`。

---

### 4.1 `__init__(self, core: object) -> None`

- `core` 是 COMP-C2 的 `HostContract` 实现（`HostCore`）。
- **本方法是全系统唯一的装配点**。算法注册表来自
  `algorithms.ALGORITHMS`（不是参数，是 import）。
- 内部状态至少需：当前 `session_id`（`str | None`）、当前 `SessionState`、
  最近一次 `UiView` 的相关字段、以及核心句柄。
- **不得**在 `__init__` 里创建会话或触碰文件系统。

### 4.2 `build_default_app() -> HostApp`

- 工厂函数：构造 `HostCore` 并注入 `HostApp`。
- 本函数是 `__main__.py` 与 `cockpit` 的共同入口。

---

### 4.3 生命周期（①）

| 方法 | 前置 | 效果 | 返回 |
| --- | --- | --- | --- |
| `create_session(profile_version: str) -> str` | 无 | 调 C2 建会话；**C1 记住** id；状态 → `CREATED` | `session_id` |
| `destroy_session(session_id: str) -> None` | 任意 | 调 C2 销毁；状态 → `CLOSED` | `None` |
| `set_reference(path: str) -> None` | `CREATED`/`INPUT_READY` | 校验路径存在 → 交给 C2；状态 → `INPUT_READY` | `None` |
| `set_practice(path: str) -> None` | `CREATED`/`INPUT_READY` | 同上 | `None` |
| `build_surface() -> None` | `INPUT_READY` | 状态 → `BUILDING` → 调 C2 构建 → 成功则 `DATA_READY` | `None` |

**★ 会话跟踪规则（必须逐字遵守）**：

```
create_session(profile_version)        → 调 C2 建会话，把 id 记在 C1 里
set_reference(path) / set_practice(path) → 用 C1 记住的 id 调 C2（**不带** session_id）
build_surface()                        → 同样用 C1 记住的 id
run_algorithms()                       → 用 C1 记住的 id
destroy_session(session_id)            → ★ **带** session_id
```

为什么只有 `destroy_session` 带：销毁可能发生在**错误恢复路径**上，
此时 C1 记住的 id 可能已失效。传参比依赖隐含状态更安全
（清理路径上的异常会掩盖真实失败）。

为什么 C2 的方法带 session_id 而 C1 的不带：C2 要支持**多会话**；
C1 在本产品里只服务一个开发者、一个会话。把"当前会话"这个隐含状态
**收在 C1**，不泄漏到 C1 自己的门面签名里。

**★ 若将来 C1 要支持多会话，本类的方法必须加 `session_id` ——
但那是契约变更，须由负责人裁定，实现者不得自行"顺手加上"。**

**★ 参数名是 `path`（不是 `uri`）且类型 `str`**：
C2 是通用核心，"uri" 允许未来扩展成非文件来源；C1 是本产品的门面，
本轮只接受文件路径。C1 会先校验存在性再交给 C2，故强行同名会让读者
以为可以直接透传。

**`build_surface()` 是同步阻塞调用**（见 `contract.UiView.progress`
的 G9 说明）。不得改成后台线程 —— 那会让状态机出现并发窗口。

---

### 4.4 编排（②）

#### `check_compatibility(algorithm_id: str) -> bool`

- 取该算法的 `required_ports`，逐个查 `surface.manifest().ports`。
- **单向检查**：只判断"有没有"。缺失 → 返回 `False`。
- **绝不**因为缺端口就去让 C2 生成数据（**核心禁令**）。

#### `run_algorithms(session_id: str) -> Sequence[AlgorithmResultEnvelope]`

- **前置**：状态 == `DATA_READY`，否则抛 `ContractViolation`。
- **顺序**：遍历 `algorithms.ALGORITHMS`，逐个调用其 `entry(surface)`。
  返回顺序**必须**与注册表声明顺序一致 ——
  否则报告顺序会随运行变化，不可复现。
- **故障隔离**（不变量 D）：
  - 单个算法抛异常 → 捕获 → 转成 `status='FAILED'` 的信封
  - 单个算法失败**不中断**其余算法
  - 不兼容的算法 → `status='INCOMPATIBLE'`，其余照常
- **结果必须校验**：算法可能返回垃圾（非 `AlgorithmResultEnvelope`、
  payload 缺键、键多于 schema）。非法 → 转成 `FAILED` 信封，
  但**不得**因校验失败而放弃其他算法。
- **★ 已知缺口（不隐瞒）**：算法死循环会**卡在此处**，
  v0.1 无超时机制。要在 §10 上报，不要自作主张加线程/信号超时。

---

### 4.5 失败归一化（③）

#### `normalize_error(exc: Exception) -> tuple[str, str]`

返回 `(error_code, 给开发者的一句话)`。必须正确区分四种情况：

| 情况 | 数据面 | 其他算法 |
| --- | --- | --- |
| 构建失败 | **不存在** | 不启动 |
| 算法要未知端口 | 有效 | 正常（该算法 `INCOMPATIBLE`） |
| 算法崩溃 | 有效 | 正常 |
| 算法死循环 | 有效 | ★ **整个流程卡住**（v0.1 缺口） |

`error_code` 取自 `contract.ErrorCode` 的取值。
**不得**把内部堆栈或文件系统细节泄漏给一句话描述。

---

### 4.6 投影生成（④）

#### `build_view(session_id: str) -> UiView`

**硬要求**（逐条都必须满足）：

1. 时间序列**必须下采样**到 `MAX_PROJECTION_POINTS` 以内
2. 每条 `UiSeries` **必须**声明 `timeline_basis`
   （用错轴会让用户把 warped 轴上的图当成真实时间，从而误读抢拍拖拍）
3. **禁止**把不同 `timeline_basis` 的曲线放进同一个视图
4. `UiScalar` 只陈述数值与单位，**不下教学结论**（SPEC §1）
5. `progress` 取值域是 `0.0–1.0`（比例），`None` 表示无进度概念
6. 失败态也要**返回视图**（`state == FAILED` 时带 `error_code` / `error_detail`），
   不得抛异常 —— 调用方（`__main__.py`）靠视图决定退出码

★ **关于 `progress` 的粒度**（已知限制，不要"优化"掉）：
它是**粗粒度**的 —— 只在状态切换时更新。
平滑进度需要 Core 在计算中途回调，**那是契约变更**。
见 `.spec/graph/overlay.json` 的 `GAP-3`。

---

### 4.7 UiProjectionPort（⑤）—— C4 的唯一入口

#### `snapshot() -> UiView`
- **纯读取，无副作用**。不得触发任何计算或状态推进。

#### `submit(command: UiCommand) -> None`
- 必须用 `contract.COMMAND_LEGALITY` 校验当前状态是否允许该命令：
  - 合法 → 执行
  - **非法 → 拒绝，且不改变状态**（不许"尽力而为"）
- 命令效果见 `contract.COMMAND_EFFECTS`。特别注意：
  - `CANCEL` 的语义由 `COMMAND_EFFECTS` 定义（**不要自行发明**）
  - `RESET` 的目标状态是 `CREATED`
- C4 可能不做置灰（那是 UI 优化），故**这里必须校验** ——
  **界面不是可信输入源**。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| 前置状态不满足（如未 `DATA_READY` 就跑算法） | 显式拒绝 | `ContractViolation` |
| 非法命令 | 拒绝且**不改变状态** | `ContractViolation` |
| 输入路径不存在 | 显式失败 | `ContractViolation` |
| C2 构建失败 | 状态 → `FAILED`，**不重试、不降级、不伪造结果** | 状态 + 视图 |
| 算法抛异常 | 捕获 → `FAILED` 信封 | 返回信封，不抛 |
| 算法返回垃圾 | 捕获 → `FAILED` 信封 | 返回信封，不抛 |
| C4 缺席 | **无影响**（不变量 F） | — |

★ **禁止**：用 `except Exception: pass` 吞掉错误；失败时返回上一次的
成功视图冒充当前结果；"先构建个空数据面让流程跑下去"。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-301-1 | 状态单调推进，不回退不跳过 | 非法序列必须抛 `ContractViolation` |
| INV-301-2 | 算法**只能**在 `DATA_READY` 触发 | 在 `BUILDING` 下触发 → 必须抛 |
| INV-301-3 | 单个算法失败不影响其他算法 | 注入一个必炸算法，其余仍返回 `OK` |
| INV-301-4 | `run_algorithms` 返回顺序 == 注册表顺序 | 两次运行顺序一致 |
| INV-301-5 | 投影每条曲线 ≤ `MAX_PROJECTION_POINTS` | 构造超长输入验证 |
| INV-301-6 | 投影内所有曲线的 `timeline_basis` 一致 | 断言 |
| INV-301-7 | C4 缺席时全流程跑通 | 不 import cockpit，跑 `__main__` |
| INV-301-8 | `snapshot()` 无副作用 | 连调两次，状态与结果不变 |
| INV-301-9 | 非法命令不改变状态 | 逐个非法命令验证 |

---

## 7 · 边界（明确不做）

- **不做任何信号处理**：`fft` / `pyin` / `stft` / `dtw` / `resample`
  一律禁止。**若你需要"算一下"，说明该逻辑属于 C2 或 C3** —— 转 §10。
- **不因为某算法缺端口就让 C2 生成数据**（核心禁令）
- **不读端口缓冲区内容**（`surface.read()` 不归 C1 调）
- **不实现算法**；不判断算法对错
- **不生成教学结论 / 自然语言反馈**（SPEC §1：只到数值层）
- **不 import `cockpit`**
- 不写用户数据、不访问网络

---

## 8 · 怎么验证你写对了

```bash
python3 tools/verify_shell.py             # 空壳期：应通过
python3 tools/verify_stubs_raise.py       # 空壳期：74/74
python3 tools/build_virtual_graph.py --check
python3 -m harmonica_eval --reference <a.wav> --practice <b.wav>   # 端到端
```

**验收判据**：
- [ ] 非法状态序列每个都抛 `ContractViolation`（列出实际输出）
- [ ] 注入必炸算法后，其余算法仍返回 `OK`
- [ ] 两次 `run_algorithms` 结果顺序一致
- [ ] `grep -rn "numpy\|scipy\|librosa" harmonica_eval/host/` 为空
- [ ] `grep -rn "cockpit" harmonica_eval/host/` 为空
- [ ] C4 缺席下 `python3 -m harmonica_eval` 能跑通

---

## 9 · 完成后提交什么证据（§36）

- [ ] 非法状态序列的实际异常输出
- [ ] 故障注入测试的实际结果（哪些算法 `OK`、哪个 `FAILED`）
- [ ] 投影下采样的**实际点数**（证明 ≤ 2000）
- [ ] `import` 禁区的 grep 结果（空）
- [ ] 端到端跑通的命令与输出

---

## 10 · ★ 何时必须停止并上报

**必须停止的情形**：

1. 你发现需要**新增一个契约方法或字段**才能实现
2. 你认为应该给算法加**超时机制**（GAP-1：需要契约变更 ——
   谁负责 kill、超时算哪种 `ErrorCode`，都是设计决定）
3. 你认为应该让 `progress` 变成**平滑进度**（GAP-3：需要 Core 回调）
4. 你需要 C1 支持**多会话**（须加 `session_id` 参数，是契约变更）
5. 你需要 import 任何信号处理库
6. 你发现 §4 的规格**不足以确定唯一实现**

**上报格式**（宪章 §37）：
```
GATE CHALLENGE
- 相关 Requirement：
- 相关 Build Instruction 章节：
- 实际需要 vs 规格给出：
- 为什么冲突：
- 复现证据：
- 建议的上游处理位置：
```

**绝对禁止**：先做 workaround（§38）；自行加"合理"默认值；
静默缩小范围。

---

## 附：冻结常量速查

| 常量 | 值 | 来源 |
| --- | --- | --- |
| `MAX_PROJECTION_POINTS` | `2000` | 本文件 4.0 |
| `SessionState` 取值 | `CREATED / INPUT_READY / BUILDING / DATA_READY / FAILED / CLOSED` | `contract.py`（**只有 6 个**） |
| `AlgorithmResultEnvelope.status` | `'OK' / 'FAILED' / 'INCOMPATIBLE'` | `contract.py` |
| `COMMAND_LEGALITY` | 6 条命令的合法状态集 | `contract.py` |
| `COMMAND_EFFECTS` | 命令效果映射（含 `CANCEL` / `RESET→CREATED`） | `contract.py` |
| `UI_PAYLOAD_KEYS` | UI 载荷键映射 | `contract.py` |
