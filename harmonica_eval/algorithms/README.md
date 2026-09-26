> **本文是组件说明，不是权威。** 权威在 `.spec/` 与源码。
> 本文任何内容与它们冲突时以它们为准，并把冲突报给负责人。
>
> ★ **本文于 2026-09-26 按源码实况重写。** ★ 上一版通篇描述「三个算法全是纯 SHELL、
> 零实现、不能运行」，★ 而实测它们产出 16 个 scalars、rc=0。★ 那些段落已删除，★ 不再保留。

# C3 算法插件层

## ① 我是谁

C3 是**可插拔的算法层**：读只读数据面，算出一个独立能力，吐出自描述的结果信封。

它在整条链上的位置：

```
core/（C2 数据面）──▶ algorithms/（C3 本层）──▶ host/（C1 编排）──▶ cockpit/（C4 界面）
  产出 12 个端口          读端口、算指标            决定跑哪些插件        画表格与曲线
```

★ 换成一句话：**C3 是「能力」层，不是「数据」层，也不是「界面」层。**

★ **可移植性**：本层只依赖 `contract` / `profile` / `numpy` / 标准库，★ 无 threading、
multiprocessing、signal、subprocess。★ 换手机前端时**本层一行不用动**（见 `docs/多端开发与可复用路线.md`）。

---

## ② 我吃什么

三个插件的端口需求**实测如下**（由 `build_default_registry().list()` 读出，★ 非文档转述）：

| 算法 | 必需端口 | 可选 | v |
| --- | --- | --- | --- |
| `pitch` | `pitch.reference` · `pitch.practice` · `notes.reference` · `notes.practice` | 无 | 1.0.0 |
| `timing` | `pcm.mapped.reference` · `pcm.mapped.practice` · `notes.reference` | 无 | 1.0.0 |
| `dynamics` | `rms.reference` · `rms.practice` · `notes.reference` · `notes.practice` | 无 | 1.0.0 |

★ **三者都依赖 `notes.reference`** —— ★ 没有任何一个能只靠 A 级 PCM 跑起来。

★ **`timing` 刻意不含 `pcm.warped.practice`**：用 WARPED 轴算抢拍拖拍会把它们抹成 0 且不报错，
★ 那是构造性错误（`timing.py` 的 MUST NOT）。

★ **`dynamics` 也不含它**：`rms.*` 在 `profile.PORTS` 里都是 REFERENCE 轴，★ 原「用 WARPED 轴」
的要求无法满足（MOLD BREAK，见 `dynamics.py` 与 `contract.py:100-108` 的修正记录）。

★ **端口需求由谁声明**：`bootstrap.ALGORITHM_INPUTS` 是权威来源（`bootstrap.py:178`），
★ 其 `timeline_basis` / `element_type` / `required_fields` 从 `profile.PORT_INDEX` 派生，★ **不得硬编码**
——硬编码会产生第二份真相源。

★ **中文显示名 `LABEL`**：取自各算法模块的 `LABEL` 常量，装配根**不回退**
（`pitch`=音准 / `timing`=节奏 / `dynamics`=力度）。★ 模块缺 `LABEL` 即抛 `PLUGIN_INCOMPATIBLE`，
★ 不回退为 `algorithm_id`——回退后界面会把英文 ID 当中文名显示且**全程无报错**。

---

## ③ 我吐出什么

`AlgorithmResultEnvelope`，★ payload 是自描述的 `Sequence[UiScalar | UiSeries]`。

★ **实测一次完整运行的产出**（`05_漏音断句` vs 标准旋律版，rc=0）：

| 算法 | scalars | series |
| --- | --- | --- |
| `pitch` | 5 | 3（`per_note_cents` · `per_note_f0_reference` · `per_note_f0_practice`） |
| `timing` | 7 | 1（`per_note_onset_sec`） |
| `dynamics` | 4 | 2（`envelope_db_reference` · `envelope_db_practice`） |
| **合计** | **16** | **6** |

★ **曲线都是逐音的**（X 轴是音符序号或起音秒，★ 不是时间帧），★ 所以能直接铺成表格。

★ **`timing` 只有一条 series**，★ 因为它报的是**偏差量**——★ 参考自己的起音时刻是 0，
★ 天然没有「参考值」这一列。★ 界面因此不给它双列对比表。

**谁消费它：**
- `host` 把它并进 `UiView.scalars` / `series`，★ 界面从那里读
- `metrics.json` 是它的落盘形态（`__main__.py` 的无头入口产出）

★ **`_span_means_db`（`dynamics.py:169`）不是指标，是绘图辅助**：按音区间求平均 dB，供界面画能量包络。
它**与指标同源**——读的是同一条 `to_db(...)` 结果、同一份 `spans`，★ 所以「图上看到的能量」与
「指标算出的 `median_db`」必然一致。★ 这一点是本项目最防的那类假绿（画图若另算一份，图文会不符）。

★ 它的空区间返回 `0.0`，★ **界面必须跳过该点**——画 0 dB 会被读成「这个音完全无声」。

---

## ④ ★★ 我不做什么 ★★

★ **这一节决定换手机前端时哪些能扔。★**

| 我不做 | 因为 | 依据 |
| --- | --- | --- |
| **不做 DSP** | STFT / DTW / 音高检测全在 `core`，★ 这里只读端口 | `pitch.py:146` 的入口签名只收端口数据 |
| **不碰数据面存储** | 端口由 `core.surface` 拥有，★ 算法只读不写 | `runtime.py:152` `read()` 是委托 |
| **不做时间对齐** | `warp_path` 是 `core.align` 的产物 | `bootstrap.py` 端口需求里无对齐端口 |
| **不发现插件** | `Registry` 只有 `register`/`list`/`get` 三个方法，★ 没有任何扫描/发现逻辑 | `registry.py:66-104`（★ 全文只有这四个 `def`） |
| **不运行插件** | 同上——★ `Registry` 里没有 `run`/`execute` 任何执行路径 | `registry.py` 方法清单实测 |
| **不 import 上层** | 不反向依赖 `core`/`host`/`cockpit`，★ 也不横向认识别的算法 | `tools/check_plugin_contract.py` 判据①③④ |
| **不做界面** | 本层不知道 UI 存在，★ 界面是 C4 | `contract.py` 里 UI 类型与算法信封分离 |

★ **★ 最后两条正是「深组件 / 降低信息熵」的落点 ★★**

```
★ 「不发现插件」：★ Registry 是个【被动容器】，★ 往里放什么是装配者的事
★ 「不运行插件」：★ 它只回答【有什么】，★ 不回答【怎么跑】
★ ★ ★ 而这两条【加起来】才有意义：★ registry 不 import 具体算法（那是 bootstrap 的活）
★ ★ ★ ★ 【而整仓实测确实零 import】：
  grep -rn "from .pitch|from .timing|from .dynamics|algorithms\.(pitch|timing|dynamics)" \
    harmonica_eval/ --include=*.py | grep -v "algorithms/bootstrap.py"
  → 零命中（★ 唯一提到 "algorithms/dynamics.py" 的是 contract.py:104 的 MOLD BREAK 叙述，★ 不是 import）
★ ★ ★ ★ ★ 「唯一物理装配根」这条不变量【成立】，★ 而它由 bootstrap.py:59 单独承担
```

★ **插件作者要知道的两件事**：
```
① 你要 import 你的模块，★ 只能改 bootstrap.py（★ 那是唯一装配根）
② 但【改源码注册 ≠ 插件机制】，★ 那只是装配动作
   ★ 真正的机制是 Registry 在运行期可增删，★ 而退化守卫会抓到「删掉插件就指标消失」之外的伪造
   ★ 参考 tests/test_plugin_plugability.py（★ 10 用例）与 CONTRIBUTING.md 第 4 节
```

---

## ⑤ 装配权：为什么独立一个 bootstrap（负责人 BLOCK-1 裁定，方案甲）

裁定前的实况是**物理上无解**：

```
不变量甲  C1 是全系统唯一知道「有哪些实现」的地方
不变量乙  C1 跨界 import 的是契约层，不是某个具体算法实现模块
```

要 `registry.register(pitch/timing/dynamics)` 就必须 import 具体模块，而乙禁止 C1 这么做
——两条同时成立时装配链**写不出来**（原登记为 GC-204-08，已关闭）。

| 主体 | import 具体算法？ | 拿到什么 |
| --- | --- | --- |
| `bootstrap.py` | ★ **是，且仅此一处** | 自己 import 三个算法，构造并注册 |
| C1（`HostApp`） | **否** | 只接收 `bootstrap` 产出的 `Registry` |
| C2 / C4 | **否** | 只用 `contract` 的类型 |

★ **实测接通了**：`host/app.py:105` 接收 `Registry`，`:113` 强制它提供 `list()`。
★ 而 `host` 自己不 import 任何算法实现。

★ **插件清单的真相源**：`serve_ui.py:266-268` 从 `app._registry` 取 `algorithm_id` 注入界面，
★ 所以**注入一个陌生插件，界面的可选列表里就自动多一项**——★ 那是「可插拔」在界面上的可见形式。

---

## ⑥ 解析事实在谁手里（负责人 BLOCK-2 裁定，方案乙）

| 主体 | 拿得到 `InputResolution`？ | 用途 |
| --- | --- | --- |
| C1（Host） | ★ **是** | 比对 `consumed_ports ⊆ available` |
| 插件（算法） | **否** —— 只拿投影后的 `ResolutionView` | 读自己声明的端口 |

`validate_result` **不接收** resolution / manifest：它只管「信封自身是否自洽」，
而「信封声称消费的端口是否真的可用」由 C1 在调用点比对。★ 两者管的是不同事实。

★ `ResolvedSurface` 的 `manifest()` / `read()` / `resolution` **是真委托**（`runtime.py:148-164`），
★ 直接转发给 `self._surface`，不改变解析事实。

---

## ⑦ 懒加载（负责人 2026-09-25 授权）

`run_algorithms(session_id, only=None)`（`host/app.py:281`）的 `only` 传 `algorithm_id` 序列，
★ **只跑指定的**。实测：

```
POST /command {"kind":"RUN_ALGORITHMS","only":["pitch"]}  → 200
/view 里 scalars 分组 ['pitch'] · series 分组 ['pitch']
```

★ **`only` 是可选键**（`UI_PAYLOAD_KEYS[RUN_ALGORITHMS] = ("only",)`），★ 不传则跑全部。
★ 顺序**恒为会话快照顺序**，★ 不因 `only` 的次序而改变。

★ 两条边界行为：
```
only=[]                     → 抛错，★ 且消息是「未指定任何算法 id：only=[] 与注册表 [...] 无交集」
                               ★ ★ 而【不是】「注册表快照为空」——★ 那句话会让人去查注册表，★ 而那里没问题
only=["不存在的插件"]        → 抛错，★ 报出真名「未注册的算法 id：['不存在的插件']」
★ ★ ★ 不静默忽略——★ 静默会让界面显示「有指标」而其实跑了 0 个，★ 那是假绿
```

★ 契约规格见 `.spec/build/FILE-003-v1.md`（★ 那里明确写了**不属 §4.14「扩面冻结」范围**：
★ 冻结的是 `UiView` 字段的增删，★ 而 `UiView` 九个字段一个没动，★ 改的是命令载荷的键）。

★ **★ 而 `only` 【不属于本层】★★**
```python
# 实测：grep -n "only" harmonica_eval/algorithms/*.py  →  零命中
#      grep -n "only" harmonica_eval/host/app.py      →  :284 / :290 / :309
```
```
★ 本层【不知道】自己被不被跑；★ 那是 host 的决定
★ ★ 而本层对「只跑 pitch」这件事【毫无感知】——★ 它照样产出全部结果
★ ★ ★ 【所以「懒加载」是编排能力，★ 不是插件能力】
```

---

## ⑦ 之补 · ★「可插拔」的真实边界（★ 2026-09-26 实测复核）★★

★ **★ 本项目最容易被误解的一点，★ 写实比吹大有用 ★★**

```python
# 实测：Registry 的公开方法
from harmonica_eval.algorithms.registry import Registry
[m for m in dir(Registry) if not m.startswith('_')]   # → ['get', 'list', 'register']
inspect.signature(Registry.register)                     # → (self, spec: PluginSpec) -> None
```

★ **★ 三条边界，逐条实测 ★★**

```
① ★ 注册：★ 【可以】运行期 register(PluginSpec(...))
   ★ ★ 实测：★ 不改 bootstrap 源码，★ 注册一个陌生算法，
   ★ ★   它的指标（my_algorithm.mean_value）自动出现在页面上，
   ★ ★   分组列表变成 ['dynamics', 'my_algorithm', 'pitch', 'timing']
   ★ ★ ★ 而那条路径【已经通了】——★ 界面侧 render 是 for item in scalars

② ★ 注销：★ 【做不到】——★ Registry 【没有 unregister】
   ★ ★ ★ 所以「换插件」要【重启进程】重新装配
   ★ ★ ★ ★ 【不许】说「支持热插拔」——★ 那是假的
   ★ ★ ★ 而「注册表后来发生增删时，★ 正在运行的 k/N 进度不会倒退」
   ★ ★ ★   是靠 host 层【会话建立时对 registry.list() 做一次快照】实现的
   ★ ★ ★   （host/app.py 的分母 N 注释原文）

③ ★ 界面读不到插件清单：★ ★ 契约【不许给 UiView 加字段】
   ★ ★ ★ FILE-003-v1.md 的「有限扩面冻结记录」写明：
   ★ ★   后续任何 UiView 字段的增删须重新裁定，★ 不得援引本次先例
   ★ ★ ★ 而本次的 `only` 【不属于】那条冻结——★ 它改的是命令载荷的键
   ★ ★ ★ ★ 后果：★ 后来人若想「在页面上列出插件清单」，★ 会撞它
   ★ ★ ★ ★ 而现在的替代方案：★ 指标 key 的点号前缀就是插件 id
   ★ ★ ★   （界面按前缀分组，★ 注入陌生插件 → 它自己多出一组）
```

★ **★ 插件作者要记住的一句话 ★★**
```
★★ 「注册是运行期的，★ 注销要重启，★ 界面靠指标前缀认识插件」
★★ ★★ 而第三句是本项目【刻意】的设计取舍，★ 不是没做完
★★ ★★ 而它换来的正是「换个界面层也不用动内核」——★ 见 docs/多端开发与可复用路线.md
```

---

## ⑦ 之又补 · `_span_means_db`：★ 它【不参与指标计算】（★ 红绿实测）★

★ **★ 为什么单独记：★ 后来人看到它会以为「它参与算指标」★**

```python
# harmonica_eval/algorithms/dynamics.py:169
def _span_means_db(curve_db: object, spans: object) -> list[float]:
    """每个音区间内的【平均 dB】，供画能量包络用。
    与 `align_by_note` 读的是同一条 `to_db(...)` 结果、同一份 `spans`，
    所以「图上看到的能量」与「指标算出的 median_db」必然同源。
    ★ 空区间或无有效帧时返回 0.0；界面须跳过该点，
      画 0 dB 会被误读成「这个音完全无声」。
    """
```

★ **★ 红绿实测（★ 2026-09-26，★ 主代理亲手做）★★**
```
基线   01_音准走调 → 16 scalars
  pitch.median_abs_cents  105.000067
  dynamics.median_db       -0.207987
  timing.median_onset_sec   0.0
注入   把 out.append(sum(chunk)/len(chunk)) 改成 out.append(0.0)
       ★ 即「假装这个画图辅助彻底坏了」
重跑   16 scalars · scalars 集合相同 True · 全部数值逐位相同 True
结论   ★ 它【不参与指标计算】✓ —— 它只给界面提供逐音 dB
恢复   cmp 逐字节相同 ✓
```
★ **★ 而它【必须存在】的理由也在上条实测里 ★★**
```
★ 若没有它，界面要自己从 rms 端口重算一遍「每音平均 dB」
★ ★ 而那会造成「图上的能量」与「指标里的 median_db」【不同源】
★ ★ ★ 那正是本项目最防的那类假绿——★ 图与数对不上
★ ★ ★ 所以它存在的意义是【同源】，★ 不是【算数】
```

---

## ⑧ 12 条架构不变量

`tools/check_plugin_contract.py` 运行 **12 条编号守卫 + 1 条无编号 composite**（`CASE_ORDER` 把
composite 拆成两案显示为 14，★ 那不是第 13、14 条）。★ **当前实跑 13/13 通过，exit 0。**

★ **第 ⑪ 条「插件文件保持精确空壳」现在实际上【不守任何文件】，★ 这一点值得单独记：**
```
★ 上一版文档把它写成「三个算法全是空壳」——★ 错的
★ ★ 现在的实际状态（实测，遍历 algorithms/ 下全部 7 个 .py）：
  bootstrap / registry / runtime / pitch / timing / dynamics  六个【已授权，跳过空壳断言】
  algorithms/__init__.py                                      【未授权，但带 FILE 铭牌的函数 = 0 个】
★ ★ ★ ★ 而它【没有一个可注入的函数】——★ 它是纯 re-export 门面
  （__all__ 3 项：InputRequirement / PluginSpec / Registry），★ 所以判据⑪ 遍历不到它
★ ★ ★ ★ 授权名单派生自 tools/authorized_impl.py（唯一真相源），★ 按【包内相对路径】判定
★ ★ ★ 而 check_algorithm_shells 的 docstring 自述的例外只有 bootstrap / registry 两个
★ ★ ★ ★ ★ 而实际授权名单是六个——★ 那句 docstring 本身也落后了
```

★ 其余关键约束（均有 `check_plugin_contract.py` 对应判据）：

- 插件只依赖契约，不反向 import 上层，也不横向认识其它算法
- payload 自描述，★ 框架不维护按 `algorithm_id` 索引的字段表——★ 新算法不能靠改中央映射接入
- 算法不修改数据面、不跨会话持有端口指针、不依赖 process-global 可变单例；
  ★ 结果失败**隔离为信封**而非穿透异常
- `timing` 必须保留 REFERENCE 轴；★ `dynamics` 不能退回错误的 WARPED 轴代理；★ `pitch` 不能 chroma 化
- ★ **已知缺口**：v0.1 算法死循环**没有超时机制**，会卡住编排。★ 不得被本文隐去。

---

## ⑨ 文件索引

| 文件 | 行数 | 职责 | 现场依据 |
| --- | --- | --- | --- |
| `__init__.py` | 55 | 门面：只 re-export `Registry` / `PluginSpec` / `InputRequirement`（`__all__` 3 项） | ★ 纯 re-export，★ 无可注入函数 |
| `bootstrap.py` | 379 | **唯一物理装配根**：import 三个算法 → 构造 `PluginSpec` → register | `bootstrap.py:59`（`from . import dynamics, pitch, timing`） |
| `registry.py` | 104 | 被动容器：`register` / `list` / `get`。★ 不发现、不运行。★★ **没有 `unregister`** → 换插件要重启进程 | ★ 全文只有 `__init__` + 这三个 `def`；★ 详见「⑦ 之补 · 可插拔的真实边界」 |
| `runtime.py` | 399 | `InputResolution` · `resolve_inputs` · `validate_result` · `ResolvedSurface` 委托 | `runtime.py:148-164` |
| `pitch.py` | 465 | 绝对音高逐音比较 | `pitch.py:146` `compare_pitch_curves` |
| `timing.py` | 513 | 保留源时间轴的起音配对与抢拍/拖拍 | 见 `LABEL` 与端口需求节 |
| `dynamics.py` | 496 | 按音配对 RMS，以 dB 报差异 | `dynamics.py:169` `_span_means_db`（★ 绘图辅助） |

★ **合计 2411 行**，★ 占全项目 20%。

---

## ⑩ 已知的文档漂移（2026-09-26 复核时发现，供后来者参考）

★ 上一版（09-24 22:30）通篇描述 SHELL 时代，★ 以下每一句**实测均已不成立**：

| 旧文档说 | 实测 |
| --- | --- |
| 「三个算法本体全部是纯 SHELL，零实现，不能运行」 | ★ 全是假的：rc=0，16 个 scalars |
| 「Registry 与 runtime 也仍为空壳」 | ★ 假的：Registry 三方法已实现，runtime 委托已接通 |
| 「runtime 的 `InputResolution.as_view()` 等当前为 SHELL」 | ★ 假的：`ResolvedSurface` 三件套是真委托 |
| 「装配链仍未接通，bootstrap 没有任何文件 import」 | ★ 假的：`host/app.py:105` 接收 Registry |
| 「`pcm.warped.practice` 无算法消费」 | ★ **这句仍成立**（实测无插件要求它）——★ 保留它 |
| 行号锚点（`registry.py:49-78` 等） | ★ 全部错位：那些行现在是 import 与类型定义 |

★ **★ 教训（写给后来者）★★**
```
★ 上一版文档的每条断言都带 file:line，★ 看起来可核查
★ ★ 但那些行号在两天后就全部失效，★ 而【没人重新核过】
★ ★ ★ 「有出处」不等于「出处还对」——★ 行号会漂移，★ 引用它的文档不会自己失效
★ ★ ★ ★ 所以本文的每条实测结论都带【本次复核实测】标记，★ 而不带行号的地方我写清是实测来的
```
