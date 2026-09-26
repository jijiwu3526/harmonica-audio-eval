# C1 Framework / Host

> 本文件描述**当前代码的真实状态**，2026-09-26 逐条实读校验。
> 凡与旧版本描述不符之处以本文为准；**全部冲突列在第 ⑧ 节，未被静默删掉。**

---

## ① 我是谁

`harmonica_eval/host/` 是 **C1 编排层**——全系统**唯一**同时依赖 `core` 与 `algorithms` 的包。

```
UI（cockpit）──命令──▶ C1 Host ──数据面──▶ C2 core ──▶ C3 algorithms
                       （本组件）         12 个端口     pitch/timing/dynamics
```

★ **为什么装配点必须唯一**：若 core 与 algorithms 各自去接对方，
「谁负责把算法接到数据面上」就没有唯一答案，端口需求也就无人核账。

**规格**：`COMPONENTS.md` §3–§7；`FILE-300-v1.md`（包出口）、`FILE-301-v1.md`（实现）。

---

## ② 我吃什么

```python
from harmonica_eval.host.app import build_default_app

app = build_default_app()
session_id = app.create_session("v1")      # profile_version
app.set_reference(session_id, uri)         # uri = 仓库相对路径
app.set_practice(session_id, uri)
app.build_surface(session_id)              # 产出 12 个端口
app.run_algorithms(session_id)             # 或 run_algorithms(session_id, only=[...])
```

| 输入 | 形状 | 说明 |
|---|---|---|
| `profile_version` | `str` | 记入会话，实测用 `"v1"` |
| `uri` | `str` | **仓库相对路径** |
| `only` | `Sequence[str] \| None` | 算法 id 序列；`None` = 全部 |

★ **为什么必须是相对路径**：`set_reference` 存的就是这个字符串，
它会原样进 `metrics.json` 与界面下拉框的可选值。写成绝对路径，
别人 clone 下来就选不到曲子。

---

## ③ 我吐出什么

| 产物 | 形状 | 谁消费 |
|---|---|---|
| `snapshot()` | `UiView`（9 字段） | cockpit 的 `GET /view` |
| `run_algorithms()` | `Sequence[AlgorithmResultEnvelope]` | C1 自己（转 scalars/series） |
| 状态机 | `SessionState` | 决定哪些命令此刻合法 |

★ **`snapshot()` 不接收 session_id**（`app.py:663`，反射实测）：

```python
def snapshot(self) -> UiView:      # ← 无 session_id 参数
```

这是**刻意窄化**：`UiProjectionPort` 的契约是「一个前台看一个会话」，
所以 session_id 住在 `UiView` 里，端口上就不必再收一遍。

★ **C4 可缺席**：Host 不导入 cockpit。删掉界面不影响无头流程。
（`FILE-301-v1.md` §4.7；`tools/check_plugin_contract.py` 第②条机器守）

---

## ④ ★ 我不做什么 ★

**这一节决定换手机前端时哪些代码能扔、哪些绝对不能动。**

### 我不读音频文件

```
ingest 在 C2 core（core/ingest.py）
★ 换平台只改 core/ingest，★ host 一行不动
```

### 我不做 DSP

```
STFT / DTW / 音高检测 / 能量包络 —— 全在 core 与 algorithms
★ host 只负责【按顺序调用】与【把结果转成投影】
```

### 我不碰界面

```
★ host 只实现 UiProjectionPort（snapshot / submit 两个方法）
★ 它不知道 cockpit 存在
★ ★ 而这条是「换前端不影响核心」的根据
```

### ★ 我不知道有哪些具体算法

**这是本组件的核心设计，也是多端路线的根据。**

`app.py` 的全部 import（48–74 行）：

```python
from ..algorithms.registry import Registry      # 注册表
from ..algorithms.runtime  import ...           # 解析
from ..contract import ...                      # 契约
from ..core.api import HostCore                 # 数据面
```

**没有 `from ..algorithms.pitch import ...`，没有 timing，没有 dynamics。**

算法从哪来？`bootstrap.py` 是全系统**唯一** import 具体算法模块的位置，
它装配好 `Registry` 交给 Host。Host 只接收成品。

```python
# app.py docstring 原文
分母 N 在会话建立时对 registry.list() 做一次快照，
之后整个会话固定使用该快照。
```

★ **所以「注入一个内核从未听过的算法」不需要改 host 任何一行。**
★ `tools/check_plugin_contract.py` 第②条机器守这一条。

### 我不静默吞错

```
实测：only=["不存在插件"] → 未注册的算法 id：['不存在插件']
```

**报真名，不忽略。** 静默会让调用方以为「跑过了」——那是最该避免的假绿。

### ★ 我【不】做指标计算（★ 附实测依据）

```
grep -cE "median_abs_cents|off_pitch|onset_deviation|envelope_db" host/app.py
→ 0
grep -cE "numpy|scipy|librosa" host/app.py
→ 0
```

★ **host/app.py 里既没有指标 key 的字面量，也没有任何重计算库。**
★ 它只调用 `_run_one`（`app.py:347`）拿回信封，再交给 `_project_results`
★ （`app.py:552`）转成 scalars / series——**指标怎么算，host 无从得知。**

### ★ 逐条边界的 file:line（★ 便于复核，★ 便于后人验）

| 我不做 | 依据 |
|---|---|
| 不读音频 | `set_reference`（`app.py`）只存字符串，读取在 `core/ingest.py` |
| 不做 DSP | `app.py` 零 `numpy`/`scipy`/`librosa` 引用（实测 0） |
| 不做指标计算 | 零指标 key 字面量（实测 0）；`_run_one` 只调算法 |
| 不碰界面 | `cockpit` 在 `app.py` 只出现于注释（`:39`、`:785`），**零 import** |
| 不知道具体算法 | 无 `from ..algorithms.pitch/timing/dynamics`（实测 0） |
| 不静默吞错 | `only` 校验失败即抛 `HarmonicaError`，报出真名 |

★ **★ 而「不缓存算法结果」这条【不成立】，★ 别写进文档 ★★**
```
★ host 确实有 _results 字段（:121 初始化、:344 赋值）
★ ★ 而 build_view 走 _project_results(self._results)（:562）
★ ★ ★ 所以【snapshot 依赖它】——★ 它不是「不存在的缓存」，★ 而是投影的输入
★ ★ ★ ★ 写成「host 不缓存结果」会是【假陈述】
```

---

## ⑤ `only`：懒加载（2026-09-26 新增）

`run_algorithms(session_id, only=None)` —— **不勾选的插件根本不跑**。

### 它解决什么

界面允许多选插件；不选的不该付计算代价，更不该出现在 `/view` 结果里。

### 它怎么被触发

```bash
curl -X POST http://127.0.0.1:8721/command \
  -H 'Content-Type: application/json' \
  -d '{"kind":"RUN_ALGORITHMS","only":["pitch"]}'
```

### ★ 三条不变量（★ 本轮实测，非转述）

| # | 语义 | 实测结果 |
|---|---|---|
| ① | **真懒加载**：不勾的不进结果 | `only=["pitch"]` → 结果分组仅 `pitch` |
| ② | **顺序恒为会话快照顺序** | `["dynamics","pitch"]` → 首个 key 仍是 `pitch.median_abs_cents` |
| ③ | **传不存在的 id 报真名** | → `未注册的算法 id：['不存在插件']` |

**两条边界**：

```
only=None  → 全部三个 · progress = 1.0
only=[]    → 未指定任何算法 id：only=[] 与注册表 ['pitch','timing','dynamics'] 无交集
```

★ **`only=[]` 那句【不是】「注册表快照为空」——★ 两种成因必须分开报**：

```
· 快照里一个算法都没有 → 装配坏了，★ 该查 bootstrap
· 快照有但被筛没了    → 请求侧给错，★ 该查请求
★ ★ 混用会让调用方去查注册表，★ 而那里根本没问题
```

### 分母 N 变了

```
★ N = 本次实际要跑的算法数，★ 而非注册表总数
★ ★ 否则勾一个插件时，★ 进度会永远显示 1/3
★ 实测：only=["pitch"] → progress = 1.0（★ 而非 1/3）
```

### 向后兼容

```
★ FILE-301 冻结的 run_algorithms(session_id) 仍完全有效
★ （only 有默认值，★ 位置参数未变）
★ ★ 而 verify_shell 实测能抓到骨架参数变化（注入 bogus_extra → 红）
```

### 两条不变量有判据守着（★ 实现对 + 判据在守，★ 两个例子）

| 不变量 | 判据 | 文件 |
|---|---|---|
| 执行次序恒为会话快照顺序，不因 `only` 书写次序改变 | `test_only_order_does_not_change_execution_order` | `tests/test_plugin_plugability.py:229` |
| `only=[]` 的诊断不得把责任推给注册表 | `test_empty_only_does_not_blame_the_registry` | `tests/test_error_paths.py:355` |

★ **为什么把它们列进文档**：判据与实现【同源】才可信。
★ 而这项目前有大量「实现正确但无判据」的段落（见 ⑧ 节第 9 条），
★ 本组件是少数能说清「谁在守」的。

### 授权与规格落点（★ 引规格原文，不自编理由）

```
FILE-003-v1.md:267   「UI_PAYLOAD_KEYS[RUN_ALGORITHMS] 的 only（2026-09-25 负责人授权新增）」
FILE-003-v1.md:275   「二者共用同一句『注册表快照为空』会让调用方查错方向」
FILE-301-v1.md:241   「run_algorithms(session_id, only=None)」
FILE-301-v1.md:243   「负责人裁定『这契约允许改动』，用于懒加载」

★ ★ 而「为什么不算扩面」★ 规格里已写明（FILE-003-v1.md:270）：
  不属 §4.14 末尾「扩面冻结」的范围——那条冻结的是 UiView 字段的增删，
  而 UiView 九个字段一个没动；此次改的是命令载荷的键。
★ ★ ★ 引用规格，★ 而不要在本文件重新论证一遍
```

---

## ⑤·二 ★ 嵌进别人界面：完整调用清单（★ 本次实跑）★★

★ **★ 这一节回答「负责人要的那个形态」：★★**
```
★ 「可复用的形态就是嵌进别人的界面里，★ 音频的话给磁盘路径」
★ ★ ★ 而 host 就是那个界面。★ 下面这段是【实跑输出】★ ★ ★
```

```python
from harmonica_eval.host.app import build_default_app

app = build_default_app()
sid = app.create_session("v1")                 # 返回会话 id
app.set_reference(sid, REF)                    # ★ 磁盘路径（仓库相对）
app.set_practice(sid, PRA)
app.build_surface(sid)                         # 产出 12 个端口
res = app.run_algorithms(sid, only=["pitch"])  # ★ 懒加载：只跑 pitch
v = app.snapshot()                             # UiView 9 字段
```

★ **★ 实测输出（★ 逐行摘自真实运行）★★**
```
1) create_session -> 0a2b2e928941…
2) run_algorithms(only=['pitch']) -> 1 个结果
   state= DATA_READY · scalars= 5 · series= 3 · ports= 12
   分组= ['pitch']
   pitch.median_abs_cents = 105.00006693667117
3) submit(RUN_ALGORITHMS only=[pitch,dynamics])
   state= DATA_READY · scalars= 9
   分组= ['dynamics', 'pitch']
```

★ **★ 两条等价入口（★ 反射实测，★ 没有第三条）★★**

| 入口 | 用法 | 谁在用 |
|---|---|---|
| 直接调方法 | `app.set_reference(sid, uri)` | 无头脚本、批量跑 |
| 走 `submit` | `app.submit(UiCommand(kind=..., payload={...}))` | cockpit（界面） |

```python
# ★ HostApp 上【没有】cancel() 与 reset() 方法（反射实测返回「不存在」）
# ★ 所以「取消」与「重置」只能通过 submit(UiCommand(...)) 表达
# ★ 而那正是 UiProjectionPort 只有两个方法的原因
```

★ **★ 而「嵌进去」时【不需要】的东西 ★★**
```
✗ 不需要 import cockpit      —— host/app.py 里 cockpit 只出现在注释（:39、:785），零 import
✗ 不需要起 HTTP 服务        —— 那是 serve_ui 与 cockpit 的事
✗ 不需要知道有哪些算法      —— 插件清单在 bootstrap 装配时注入
★ ★ ★ 而第三条正是「深接口」的落点：★ 换一个 UI，★ 算法侧一行不改
```

---

## ⑥ 故障隔离

```python
return self._incompatible_envelope(...)   # 端口不兼容
except Exception as exc: ...              # 兜住
```

**一个算法炸了，不阻断其余算法。** 出错的归一化为失败信封，其余照常。

★ **失败是静默的**（不影响别人）——**要查原因需主动读 `error_detail`**，
不读会漏掉。算法死循环会卡住流程，是 v0.1 已知缺口（无超时）。

---

## ⑦ 关键不变量（沿用旧文，仍然成立）

- **状态门**：算法只能在 `DATA_READY` 触发；`CANCEL` / `RESET` 允许回退。
- **单向兼容性**：C1 绝不因插件缺端口而要求 C2 生成数据。
- **投影纯显示**：C1 下采样曲线，但每条必须带 `timeline_basis`；
  不混时间轴、不生成教学结论。
- **UI 不可信**：`submit` 以 `COMMAND_LEGALITY` 校验，非法命令拒绝且不改状态。

---

## ⑧ ★ 文档冲突清单（★ 旧文档 → 实测，★ 未静默删除）

| # | 旧文档原文 | 实测 | 处置 |
|---|---|---|---|
| 1 | 「`HostApp` 构造、生命周期…**仍是 SHELL**；`build_default_app` **也未实现**」 | 反射实测八个方法全部存在且有真实签名；`build_default_app` 正常返回实例 | **已废止的阶段态**，删除 |
| 2 | 「`bootstrap.py` **没有被任何模块 import**」 | `build_default_app()` 返回的对象带完整 registry，算法实跑通过 | **已废止**，删除 |
| 3 | 「入口相关**仍为 SHELL**，注入前不得把它写成已交付行为」 | `python3 -m harmonica_eval --reference … --practice …` 实跑 rc=0，产出 16 指标 | **已废止**，删除 |
| 4 | 通篇未提 `run_algorithms` 的 `only` | `(self, session_id, only=None)` | 新增第 ⑤ 节 |
| 5 | 未提懒加载与「不勾不跑」 | 只跑的进结果，不跑的完全不进 | 新增第 ⑤ 节 |
| 6 | 未提 N=0 的两种成因要分开报 | 两句不同消息 | 新增第 ⑤ 节 |
| 7 | **无「我不做什么」一节** | —— | 新增第 ④ 节（本文主要目的） |
| 8 | 未写 `snapshot` 是否带 session_id | **不带**（`app.py:663`） | 已在第 ③ 节写明 |

★ **第 1、2、3 条是同一类病**：`【已注入】` 仍被写成 `【待注入】`。
★ 那批阶段态描述早已不成立，留着会让人以为系统是空壳。

### 仍然 OPEN 的未决项（旧文这部分是对的，保留）

- 🔴 **GC-204-01**：`HostApp` 隐式使用记住的 id，与 `HostContract` 要求显式传 id 冲突。**未裁定，阻塞 Cast Freeze。**
- 🔴 **`ResolutionView` 未接入 C1**：`as_view()` / `manifest()` / `read()` / `resolution` 仍是 SHELL。
- **平滑进度无来源**：`UiView.progress` 在构建期只能粗粒度；需契约变更。
- **算法死循环无超时**：v0.1 已知缺口。
- **多会话未裁定**：README 不替负责人选 A/B/C。

---

## ⑨ 换手机前端时的处置清单

依据 `docs/多端开发与可复用路线.md` 实测（核心 7233 行 / 前端 2737 行）：

```
【可以整个扔掉，不影响算法】
  harmonica_eval/cockpit/**     界面实现
  harmonica_eval_web/**         React 前端
  harmonica_eval/serve_ui.py    进程装配

【必须保留，一行不改】
  harmonica_eval/host/**        本组件
  harmonica_eval/core/**        数据面
  harmonica_eval/algorithms/**  插件
  harmonica_eval/contract.py    契约
  harmonica_eval/profile.py     端口规格

【换平台需要改的（只有 ingest）】
  core/ingest.py 的 soundfile 调用
  → Android MediaExtractor / iOS AVAudioFile
  → 换法是【抽成一个函数】，★ 而 host 不感知这件事
```

★ **12 个端口跨端可行**，因为它们是纯数据、无平台句柄、时间轴显式——
★ 这正是本组件只做编排、不碰数据表示带来的好处。
