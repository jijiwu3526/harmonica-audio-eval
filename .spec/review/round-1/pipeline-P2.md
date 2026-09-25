# 管线审查 · 跨层贯通（P2）

> 审查者：独立数据管线审查者（未参与本仓设计，与设计者无共享历史）
> 仓库根：`/Users/Apple/Desktop/dsh-archive/harmonica-eval`
> 重点段落：**跨层贯通 —— 从入口到终点的完整调用序列**
> 审查方式：**只读**。未修改仓库任何既有文件。新增探针在
> `.spec/review/round-1/probes-pipeline-P2/`（未删除）。

---

## 0 · 审查锚点与并发编辑声明（必读）

本次审查期间，**仓库被另一个进程并发修改**。这不是猜测，是实测：
我在 10:13–10:22 之间观察到 `.spec/build/FILE-002-v1.md`、`FILE-104-v1.md`、
`FILE-200-v1.md`、`FILE-300-v1.md`、`harmonica_eval/host/__init__.py`、
`harmonica_eval/core/__init__.py` 的 mtime 持续前移，且内容反复改写（含一次回退）。

因此本报告的**所有结论都锚定在下面这一组哈希**上，避免与并发改动混淆：

```
锚点时间: 2026-09-24 10:24 (git HEAD 57ba80a)
1d6b0e8daa82  harmonica_eval/contract.py
18feaa46c99f  harmonica_eval/profile.py
1c0e5b089a00  harmonica_eval/__main__.py
7bb7870655bc  harmonica_eval/host/app.py
dddb4c66e2e1  harmonica_eval/host/__init__.py
6bf2792a8997  harmonica_eval/core/surface.py
5f870fee17f9  harmonica_eval/algorithms/__init__.py
a9f9007c1601  harmonica_eval/cockpit/app.py
9382417dd78a  .spec/build/FILE-002-v1.md
f994ea186358  .spec/build/FILE-104-v1.md
3d32649acfa8  .spec/build/FILE-200-v1.md
b46c60387a05  .spec/build/FILE-300-v1.md
9b0a28c0e291  .spec/build/FILE-301-v1.md
98236a21815c  .spec/build/FILE-400-v1.md
c7c84091439e  .spec/build/FILE-401-v1.md
08f60d30f8e6  SPEC.md
```

**对并发改动的处理**：凡我的原结论在锚点上已不成立者，一律**重写为当前事实**，
并注明「本版已变」。凡锚点上仍成立者，照原样保留。
**我不把并发修改本身当缺陷** —— 但其中一次修改引入了新的断点（见 F1、F3）。

**重要限定**：本仓全部实现体是 `raise NotImplementedError`。
故本审查**不把「函数没写」本身当缺陷** —— 那是本轮交付形态。
本审查判定的是：**契约/规格是否自洽到「实现者能把它接上」**，
以及**同一事实在两份文件里是否说的一样**。

**权威声明**（三处，且它们互相不总是一致 —— 这本身就是发现）：
`profile.py` / `contract.py`（可执行的事实源）；`SPEC.md`（AGENTS.md 明称唯一权威规格）；
`.spec/build/FILE-NNN-v1.md`（实现者逐字遵守的行为规格）。

---

## A · 完整链条（入口 → 终点），逐步标注生产者 / 消费者

| # | 调用 | 经过文件:行 | 端口 | 由谁生产 | 由谁消费 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | `python3 -m harmonica_eval --reference … --practice …` | `harmonica_eval/__main__.py:224` → `main()` `:150` | — | — | 人类/脚本/CI | PASS（入口存在） |
| 1 | `build_parser()` | `__main__.py:72` | — | FILE-002 | `main` | PASS（签名在） |
| 2 | `run_headless(ref, prac, out_path)` | `__main__.py:86` | — | FILE-002 | `main` | ★BREAK（F1） |
| 2a | └ 需取 C1 门面 `build_default_app` | FILE-002 §3 `:64,90` | — | **规格指定的 import 形式在运行期失败** | `run_headless` | ★BREAK |
| 3 | `build_default_app()`（composition root） | `harmonica_eval/host/app.py:243` | — | FILE-301 | `__main__` / cockpit | ★BREAK（F1，不可达） |
| 4 | `HostApp.create_session(profile_version)` | `host/app.py:124` | — | FILE-301 | `run_headless` | 未实现（契约在） |
| 5 | → `HostCore.create_session(profile_version)` | `harmonica_eval/core/api.py:57` | — | FILE-105 | C1 | 未实现（契约在） |
| 6 | `HostApp.set_reference / set_practice` | `host/app.py:143 / :155` | — | FILE-301 | C1 | 未实现 |
| 7 | → `HostCore.set_reference / set_practice` | `core/api.py:66 / :77` | — | FILE-105 | C1 | 未实现 |
| 8 | `HostApp.build_surface()` | `host/app.py:159` | — | FILE-301 | C1 | 未实现 |
| 9 | → `HostCore.build_surface(sid)` | `core/api.py:87` | — | FILE-105 | C1 | 未实现 |
| 9a | └ 阶段 INGEST → `ingest(uri)` | `harmonica_eval/core/ingest.py:96` | （不产端口） | `core.ingest` | align / features | 未实现；**无端口** |
| 9b | └ 阶段 ALIGN → `align(ref, prac)` | `harmonica_eval/core/align.py:122` | `warp_path` | `core.align`（`profile.py:253`） | **无人**（探针 4：0 个算法消费） | 名义生产者存在；证据端口 |
| 9c | └ 阶段 ALIGN 应产「两份对齐 PCM」 | FILE-105 §4.5 `:150` 要求；`core/align.py:107-109` 只返回 `warp_path` | `pcm.mapped.reference/practice`、`pcm.warped.practice` | **★未决**（FILE-104 §4.4 `:384-388` 明写未决） | `timing.run`（`algorithms/__init__.py:175-176`） | ★BREAK（F2） |
| 9d | └ 阶段 FEATURES → `materialize_pitch/rms/chroma/notes` | `core/features.py:63/80/91/104` | `pitch.*`、`rms.*`、`chroma.lowres.*`、`notes.*` | 派发表 `PRODUCER_DISPATCH`（FILE-104 `:364`） | `pitch.run` / `timing.run` / `dynamics.run` | ★BREAK（F3：与 INV-104-1 互斥） |
| 9e | └ 阶段 SURFACE → `build_surface(...)` | `core/surface.py:147` | 装配 + Seal + `content_hash` | FILE-104 | C1/C3 | 未实现 |
| 10 | `HostApp.run_algorithms(session_id)` | `host/app.py:179` | — | FILE-301 | `run_headless` | ★BREAK（F6：签名自相矛盾） |
| 10a | └ `check_compatibility` → manifest | `host/app.py:169` | — | FILE-301 | C1 | 未实现 |
| 10b | └ `pitch.run(surface)` | `harmonica_eval/algorithms/pitch.py:149` | 读 `pitch.*` + `notes.*` | 注册表 `:162-167` | C1 | 未实现 |
| 10c | └ `timing.run(surface)` | `algorithms/timing.py:195` | 读 `pcm.mapped.*` + `notes.*` | 注册表 `:174-179` | C1 | ★BREAK（`pcm.mapped.*` 未决，F2） |
| 10d | └ `dynamics.run(surface)` | `algorithms/dynamics.py:156` | 读 `rms.*` + `notes.*` | 注册表 `:186-191` | C1 | 未实现 |
| 11 | `HostApp.build_view(session_id)` | `host/app.py:210` | `UiView`（scalars/series） | FILE-301 | `__main__` / C4 | ★BREAK（payload→UiView 映射未冻结，F8） |
| 12 | `write_metrics_json(view, out_path)` | `__main__.py:132` | `metrics.json` | FILE-002 | 磁盘/CI | ★BREAK（`n_points` 无字段，F4） |
| 13 | `render_report_markdown(view)` | `__main__.py:113` | `report.md` | FILE-002 | 磁盘/CI | 未实现 |
| 14 | （可选）`launch_cockpit(port)` | `harmonica_eval/cockpit/__init__.py:43` | — | FILE-400 | 装配方 | ★BREAK（F5：常量名分叉） |
| 15 | └ `run_local_ui(port)` → `snapshot()`/`submit()` | `cockpit/app.py:77` | `UiView` / `UiCommand` | FILE-401 | 开发者 | ★BREAK（同上） |

### A.1 端口级「生产者 / 消费者」闭合表（探针 4 实测）

`profile.PORTS` 共 **12 个端口**。逐端口两侧归属：

| port_id | produced_by | 有对应生产函数？ | 被算法消费？ |
| --- | --- | --- | --- |
| `warp_path` | `core.align` | 名义上有 `align()`（返回它） | **否**（证据端口） |
| `pcm.mapped.reference` | `core.surface` | **★未决** | 是（timing） |
| `pcm.mapped.practice` | `core.surface` | **★未决** | 是（timing） |
| `pcm.warped.practice` | `core.surface` | **★未决** | 否（数据面保证） |
| `pitch.reference` | `core.features` | 名义上有 `materialize_pitch` | 是（pitch） |
| `pitch.practice` | `core.features` | 同上（**派发表已补，但与 INV 冲突**） | 是（pitch） |
| `rms.reference` | `core.features` | 名义上有 `materialize_rms` | 是（dynamics） |
| `rms.practice` | `core.features` | 同上（**同上冲突**） | 是（dynamics） |
| `chroma.lowres.reference` | `core.features` | 名义上有 `materialize_chroma` | 否（证据端口） |
| `chroma.lowres.practice` | `core.features` | 同上（**同上冲突**） | 否 |
| `notes.reference` | `core.features` | 名义上有 `materialize_notes` | 是（三个都） |
| `notes.practice` | `core.features` | 同上（**同上冲突**） | 是（三个都） |

**消费者侧**：`ALGORITHMS.required_ports` 无悬空声明（全部落在 `PORTS` 内，探针 4 实测）。
**无消费者**的端口（`warp_path` / `pcm.warped.practice` /
`chroma.lowres.reference` / `chroma.lowres.practice`，共四条）
在 `algorithms/__init__.py:127-139` 有 b/c 类豁免说明 —— 这一条**成立**，不算缺陷。

---

## B · 发现（FINDING）

### FINDING-1
```
严重度: blocker
位置:   .spec/build/FILE-002-v1.md:64,90,99,364 /
        .spec/build/FILE-300-v1.md:70,74,76 /
        harmonica_eval/host/__init__.py:33 / harmonica_eval/contract.py:490,936
问题:   进程入口够不到编排层（C1）。本版 FILE-002 已把 `.host` 加入允许 import，
        但唯一可行的 import 形式与它自己的 AST 白名单互斥，且被 FILE-300 禁止；
        contract.py 里仍无任何可驱动会话的符号。
证据:   锚点实测（三条独立证据）：
        ① 运行期：FILE-002 §3:64 规定「`.host`（`build_default_app`）」。
           实测 `from harmonica_eval.host import build_default_app`
             → ImportError: cannot import name 'build_default_app' from 'harmonica_eval.host'
           因为 host/__init__.py:33 只有 `__all__ = ["app"]`，并未 import app，
           `build_default_app` 不是包属性（探针 2 [C] 复现）。
        ② 唯一能跑的形式：`from harmonica_eval.host.app import build_default_app` → OK。
           但其 AST module key 是 `.host.app`，而 FILE-002 §8:364 的白名单是
             ALLOWED = {"__future__","argparse","json","sys","pathlib","typing",".contract",".host"}
           实测 `.host.app in ALLOWED` → **False**（探针附带验证）。
           ⇒ 能跑的写法违反 §8 断言；不违反的写法跑不起来。
        ③ FILE-300-v1.md:70「本文件最终 import 数量必须恰好为 0」，
           :74 禁止 `from . import app` / `from .app import HostApp`，
           :76 禁止「任何 re-export」。
           ⇒ FILE-002 想要的那个 `.host.build_default_app` 出口，
             被 FILE-300 明文禁止 —— 两份冻结规格直接冲突。
        ④ 探针 2 [A][B]：contract.__all__ 无任何会话驱动符号；
           HostContract / UiProjectionPort 都是 Protocol（不可实例化）；
           全仓唯一工厂 host/app.py:243 `build_default_app()`。
修法:   三份文件必须一起改，不能只改一份：
        (a) FILE-002 §8 的 ALLOWED 加入 `.host.app`（或改为按前缀匹配 `.host`），
            并允许 `from .host.app import build_default_app`；
        (b) FILE-300 放开一条 re-export 例外（或在 host/__init__.py 显式
            `from .app import build_default_app` 并同步 FILE-300 的 E2/E4 断言）；
        (c) 或改 FILE-002 §4.2，让 run_headless 接受一个由外部注入的 C1 门面
            （与 C4 的端口注入同构），从而完全不 import host。
```

### FINDING-2
```
严重度: blocker
位置:   .spec/build/FILE-104-v1.md:384-388,417,846 /
        harmonica_eval/profile.py:262-305 / harmonica_eval/core/surface.py:83-97 /
        harmonica_eval/core/align.py:122 / .spec/build/FILE-105-v1.md:150 /
        harmonica_eval/algorithms/timing.py:21
问题:   三个 pcm.* 端口（含契约明令「永远存在」的 pcm.mapped.*）的生产者是
        **明确的未决项**；FILE-104 本版已诚实标注「未决」并要求显式失败，
        这意味着数据面永远构建不成功 —— 主链路在此**必然断**。
证据:   锚点实测：
        FILE-104-v1.md:384-388 派发表中三行写「**★ 未决，见下**」；
        :388「★★ `pcm.*` 三个端口的生产者是一个真正的未决项，本文件不自行裁定。★★」；
        :417「实现者此刻应当做什么：`pcm.*` 三行留空并在 `generate_all_ports` 中抛
             `CoreBuildError(CORE_BUILD_FAILED)`，detail 写明
             `"pcm.* producer unresolved: see FILE-104 §4.4 ★未决"`」；
        :846「正确状态：`pcm.*` 的生产者是**未决项**」。
        三方冲突（FILE-104 :390-395 自述）：profile.py:268/281/295 写
          `produced_by="core.surface"`；FILE-105-v1.md:150 要求阶段 2 产出两份对齐 PCM；
          core/align.py:107-109 `align(reference, practice) -> NDArray` 只返回 warp_path。
        实测 core/surface.py 公开函数只有 build_descriptor/seal/generate_all_ports/
          assert_budget/build_surface —— 无任何函数生产 pcm.*（探针 1 [E]）。
        后果：timing.run（algorithms/timing.py:21 MUST 用 pcm.mapped.*）必然拿不到端口
          → 节奏维度（三个核心维度之一）必然失败。
修法:   由负责人裁定三选一（FILE-104 :403-412 已列出）：
        (A) core.surface 增补生产函数；(B) 改 profile.produced_by 指向真正做归一化的模块；
        (C) 认定 pcm.* 为证据端口且本轮不实现（需改冻结表）。
        在裁定前，管线**按规格就是不可构建**的 —— 这不是实现者能解决的问题。
```

### FINDING-3
```
严重度: blocker
位置:   .spec/build/FILE-104-v1.md:364-381（新派发表） vs :772（INV-104-1）/
        harmonica_eval/core/surface.py:83-97
问题:   本版新增的 `PRODUCER_DISPATCH` 派发表与同一文件冻结的 INV-104-1 字面量禁令
        **互斥**：派发表的键就是端口 id 字面量，而 INV-104-1 要求 surface.py 源码里
        这些字面量命中数为 0。实现者无法同时满足两条。
证据:   锚点实测：
        FILE-104-v1.md:364「模块级常量 `PRODUCER_DISPATCH: Mapping[str, Callable]`，
          **键 = `port_id`**，值 = 真实的生产者可调用对象」；
        :366「`PRODUCER_DISPATCH[port_id](...)`」；
        :376 表行 `| pitch.reference | core.features.materialize_pitch | (reference, sample_rate) |`
          —— 键 `pitch.reference` 与 `notes.reference` 等就是字面量。
        FILE-104-v1.md:772 INV-104-1「并在 `surface.py` 源码中检索
          "pcm.mapped" / "pitch." / "chroma." / "rms." / "notes." 五个字面量，
          命中数必须为 **0**」。
        ⇒ 派发表若写在 surface.py 内，INV-104-1 必红；若写在别处，
          则 FILE-104 §3 的 import 白名单不允许 surface.py 去 import 那个模块
          （§3 只允许 profile 与 contract）。
        实测 core/surface.py 中当前无 `PRODUCER_DISPATCH`（grep 无命中）。
修法:   二选一并同步修改：把 INV-104-1 的判据从「源码字面量」改为
        「运行期键集合 == set(profile.PORT_INDEX)」（该断言 :772 前半句已有），
        或把派发表移出 surface.py 并放开对应 import。
```

### FINDING-4
```
严重度: blocker
位置:   .spec/build/FILE-002-v1.md:148,260 / harmonica_eval/contract.py:724-744
问题:   FILE-002 要求 metrics.json 的每个 series 元素含 `n_points`，并明令禁止用
        len(values) 代替；但 contract.UiSeries 没有 n_points 字段，
        也没有任何「点数元信息」承载处。
证据:   锚点实测（探针 3 [A]）：
        contract.UiSeries 字段 = ['key','label','t','values','unit','timeline_basis','source_port']
        grep -c n_points harmonica_eval/contract.py → 0
        grep -c n_points .spec/build/FILE-002-v1.md → 5（要求仍在）
        FILE-002-v1.md:148 第 6 步：「每个元素键序固定为：key → label → unit →
          timeline_basis → n_points」；「n_points 取投影 UiSeries 的点数元信息（整型），
          不遍历、不统计 values」。
        FILE-002-v1.md:260 §5：「投影缺 n_points 之类的点数元信息 | 停止：
          **禁止**用 len(values) 遍历数值替代 | 停止并上报（§10）」。
        FILE-002-v1.md 自己的 §10 第 4 条预告了这个冲突。
修法:   在 contract.UiSeries 增加 `n_points: int`（并同步所有构造点与 FILE-401 渲染规格），
        或在 FILE-002 中明确 n_points := len(series.t) 并撤销 §5 的禁令。
        当前形态下 FILE-002 无法既满足 §4.3 又不违反 §5。
```

### FINDING-5
```
严重度: high
位置:   .spec/build/FILE-400-v1.md:50,90-96 / harmonica_eval/cockpit/app.py:49-56,266-281 /
        .spec/build/FILE-401-v1.md:18,150-155
问题:   C4 包入口（FILE-400）要求的 app 侧常量，与 app.py（FILE-401 冻结）的常量名分叉；
        且 FILE-400 自己规定「常量缺失或取值不符 → 停止上报」，故 launch_cockpit 按规格不可实现。
证据:   锚点实测（探针 3 [B]）：
        LOCAL_BIND_HOST        app.py has? True
        LOCAL_BIND_PORT        app.py has? False
        EXIT_OK                app.py has? True
        EXIT_STARTUP_FAILED    app.py has? False
        EXIT_SIGTERM           app.py has? False
        build_plots            app.py has? True
        app.py 实际公开常量 = ['COMMAND_LABELS','EXIT_OK','EXIT_START_FAILED','LOCAL_BIND_HOST']
        FILE-400-v1.md:50 要求 app 侧提供 LOCAL_BIND_HOST、LOCAL_BIND_PORT、EXIT_OK、
          EXIT_STARTUP_FAILED、EXIT_SIGTERM、build_plots。
        FILE-401-v1.md:18 与 app.py:55 定义的是 `EXIT_START_FAILED`（少一个 UP）；
        FILE-400 还引用 `POLL_INTERVAL_MS`（app.py 中不存在）。
        FILE-400-v1.md §5：「app 侧任一冻结常量缺失或取值不符 §4.2 → 不得就地兜底；
          转 §10 停止上报」。
修法:   统一常量名（建议以 FILE-401/app.py 为准，FILE-400 改引 EXIT_START_FAILED）。
        注意不能靠加别名绕过：FILE-401 的 INV-401-11 要求 app.__all__ 恰 14 项，
        加别名会破坏该断言 —— 必须改文档而不是加别名。
        同时补 LOCAL_BIND_PORT / POLL_INTERVAL_MS 的定义归属。
```

### FINDING-6
```
严重度: high
位置:   .spec/build/FILE-301-v1.md:119 vs :152,:190 / harmonica_eval/host/app.py:179,210
问题:   FILE-301 在同一份文件内对 run_algorithms / build_view 的签名自相矛盾：
        会话跟踪规则说「不带 session_id」，章节签名说「带 session_id」。
证据:   锚点实测：
        FILE-301-v1.md:119 会话跟踪规则：「run_algorithms()  → 用 C1 记住的 id」（无参数）
        FILE-301-v1.md:152：`run_algorithms(session_id: str) -> Sequence[AlgorithmResultEnvelope]`
        FILE-301-v1.md:190：`build_view(session_id: str) -> UiView`
        FILE-301-v1.md:117-120 整段都按「不带 session_id」写。
        壳件 harmonica_eval/host/app.py:179 / :210 采用了「带 session_id」的版本
        （host/app.py 类 docstring :91-103 又重申「不带」）。
修法:   二选一并全文统一：若 C1 单会话，则 §4.4/§4.6 签名去掉 session_id；
        若保留 session_id，则删掉 §4.1 的会话跟踪规则。
```

### FINDING-7
```
严重度: medium
位置:   harmonica_eval/contract.py:443,453-455 / .spec/build/FILE-104-v1.md:460,479-480 /
        harmonica_eval/profile.py:246-257,526
问题:   warp_path 的 read() 时间窗换算自相矛盾且实际不可用：
        contract 说按 units=="index" 用 hop 换算，而 warp_path.hop_length == 0（除零/恒零）；
        FILE-104 又给出 (n-1)*hop/sr 的上界公式，同样恒为 0。
证据:   锚点实测（探针 3 [C]）：
        warp_path.hop_length = 0，dimensions = ('warp_point','axis')
          → upper = (n-1)*0/sr = 0.0；任何 t1>0 的 warp_path 读取都抛 ContractViolation。
        contract.py:443「units == "index" → 秒 × sample_rate / hop_length → 索引」；
          hop=0 时该式无定义。
        contract.py:453-455「warp_path 特殊：时间窗按 reference_frame 换算后的秒值筛选」
          —— 与 :443 的 hop 口径并存，且同样需要 hop。
        FILE-104-v1.md:460 上界 `(n - 1) * hop / sr`；:479-480 空表上界取 max(0.0, …)。
        profile.py:526 又强制「不含 frame 维度的端口必须 hop_length == 0」，
          即 profile 的完整性检查与 read() 的换算需求互斥。
        实际影响有限：探针 4 确认无算法消费 warp_path（证据端口），
        故不阻塞主链路，但违反 contract 自己的「read 无副作用且不静默失败」承诺。
修法:   为 warp_path 冻结一条不含 hop 的窗口语义（如按 reference_frame 列
        = frame / sample_rate 直接筛行），并删除 contract.py:443 中 units=="index"
        一律用 hop 的规则，或对 hop==0 的端口单独定义换算。
```

### FINDING-8
```
严重度: medium
位置:   harmonica_eval/algorithms/__init__.py:247-289 / harmonica_eval/host/app.py:210 /
        .spec/build/FILE-301-v1.md:163 / .spec/build/FILE-200-v1.md:149
问题:   payload → UiScalar/UiSeries 的映射没有任何冻结处。
        PAYLOAD_SCHEMAS 只冻结「算法产出哪些键」，但没有表规定
        「哪个键变成哪个 UiScalar.key、什么 label、什么 unit、什么 threshold」，
        而 build_view 必须产出投影、FILE-002 又要求键名与 payload 一致。
证据:   锚点实测：
        algorithms/__init__.py:247-272 PAYLOAD_SCHEMAS 只列键名
          （如 pitch 的 per_note_cents / median_abs_cents / off_pitch_ratio /
            n_notes_used / sample_rate）。
        FILE-200-v1.md:149 只说「UiScalar.key / UiSeries.key 的取值必须取自本表的键名」，
          未规定「取哪几个、label/unit/threshold 从哪来」。
        FILE-301-v1.md:163 只要求 run_algorithms「结果必须校验 schema 合法性」；
          build_view 的规格（FILE-301 §4.6）只讲下采样与 timeline_basis。
        grep 这些 payload 键名于 .spec/build/FILE-301-v1.md → 0 命中。
修法:   新增一张冻结的 `PROJECTION_MAP: Mapping[algorithm_id, Sequence[UiScalarSpec/UiSeriesSpec]]`
        （含 key/label/unit/threshold/是否成曲线），放在 algorithms 或 contract，
        并让 FILE-301 build_view 与 FILE-002 都引用它。
```

### FINDING-9
```
严重度: medium
位置:   SPEC.md:45-55 / .spec/build/FILE-002-v1.md:142-150 / harmonica_eval/__main__.py:132
问题:   SPEC.md（AGENTS.md 明称唯一权威）定义的 metrics.json 结构与 FILE-002 冻结的
        schema 完全不同；且 SPEC §6 的分段（sections）在整条链路上无任何承载者。
证据:   锚点实测：
        SPEC.md:45-55 最小结构 = { meta{sr,duration_ref,…},
          alignment{mean_abs_warp_sec,tempo_ratio,confidence},
          global{pitch_cents_mae,in_tune_ratio,timing_mae_ms,energy_db_delta}, sections[...] }。
        FILE-002-v1.md:142-150 冻结的顶层键序 = schema_version → inputs → state →
          [error_code] → [error_detail] → scalars → series。
        两者字段集合几乎不相交（SPEC 的 meta.sr / alignment.* / global.* / sections
          在 FILE-002 schema 中均无对应）。
        SPEC.md §6「分段」在 harmonica_eval/ 下 grep `sections|分段` → 0 命中；
          FILE-002 也没有 sections 键。
修法:   由负责人裁定哪一份是 metrics.json 的权威；若以 SPEC 为准，需重写 FILE-002 §4.3；
        若以 FILE-002 为准，需更新 SPEC §3（SPEC 是权威文件，不能靠实现绕过）。
        并明确 sections 是否属于 v0.1 交付物。
```

### FINDING-10
```
严重度: low
位置:   harmonica_eval/algorithms/__init__.py:117,158,247 / .spec/build/FILE-200-v1.md:220-222
问题:   FILE-200 §4.5 要求模块末尾恰有一次 `assert_registry_integrity()` 调用
        （import 期副作用），但冻结壳件里没有这个调用点，只有函数定义。
证据:   锚点实测：
        algorithms/__init__.py:117 定义 assert_registry_integrity，:158 ALGORITHMS，
          :247 PAYLOAD_SCHEMAS；模块末尾无 `assert_registry_integrity()` 语句
          （grep 仅命中定义行与注释行）。
        FILE-200-v1.md:220-222「模块末尾必须恰有**一次**模块级语句
          assert_registry_integrity()，位置在所有定义之后」。
        对照：profile.py:571 有 `assert_profile_integrity()` 调用，机制在 profile 侧落实。
修法:   属实现期待补项（BUILD-INSTRUCTION §4.5 已写明），不是设计缺陷；
        但审查时须注意「注册表 import 期自检」当前**未生效**。
```

### FINDING-11
```
严重度: low
位置:   harmonica_eval/core/surface.py:107 vs harmonica_eval/profile.py:181 /
        .spec/build/FILE-104-v1.md:819
问题:   端口数量描述漂移（11 vs 12），同一事实多处不一致。
证据:   锚点实测：
        core/surface.py:107「实测 11 个端口在 120 s 音频下约 10–20 MB」
        FILE-104-v1.md:819「实测 11 个端口在 120 s 音频下约 10–20 MB」
        profile.py:181「预生成清单（**12 个端口**）在 120 s 音频下实测约 10–20 MB」
        实测 len(PORTS) == 12。
修法:   统一为 12；这是 MOLD BREAK 补 notes.practice 时漏改的两处。
```

### FINDING-12
```
严重度: low
位置:   .spec/build/FILE-102-v1.md:17,29
问题:   FILE-102 引用两个不存在的模块 pipeline.py / evaluator.py 作为 align 的下游。
证据:   锚点实测：
        FILE-102-v1.md:17「下游 | `pipeline.py`、`evaluator.py` 调用 align() …」
        FILE-102-v1.md:29「pipeline.py 和 evaluator.py 失去 warp_path …」
        `ls harmonica_eval/pipeline.py harmonica_eval/evaluator.py` → 两者都不存在。
        core/__init__.py:35-41 的公开面是 ingest/align/features/surface/api，无 pipeline/evaluator。
修法:   改写成真实下游（core/surface.generate_all_ports 与 core/api.build_surface 阶段 2）。
```

### FINDING-13
```
严重度: low
位置:   harmonica_eval/algorithms/pitch.py:136-144 / harmonica_eval/algorithms/__init__.py:247-254
问题:   pitch 的 payload 缺 n_unpaired，而 timing/dynamics 都有；配对失败数无处上报。
        作者已自行登记为已知缺口，此处只作确认与标注。
证据:   锚点实测：
        pitch.py:136-144「★ 已知缺口…timing 与 dynamics 的 payload 都含 n_unpaired…
          pitch 没有…按 §37 Gate Challenge 上报」。
        PAYLOAD_SCHEMAS['pitch']（algorithms/__init__.py:248-254）确无 n_unpaired；
        timing（:255-264）与 dynamics（:265-271）都有。
修法:   需改冻结表（接口变更），本轮按已登记缺口处理，不作为管线断点。
```

### FINDING-14
```
严重度: low（状态 SKIPPED，不是 PASS）
位置:   .spec/graph/overlay.json known_gaps GAP-6 / .spec/build/FILE-103-v1.md:72-103,387-389
问题:   SPEC §7.5 要求音高引擎选型必须有一次「用数据决定」的对照实验；
        实验未做，故「采样率/引擎」对最终音分指标的影响无法在本轮验证。
证据:   overlay.json GAP-6：「音高引擎选型未冻结，SPEC §7.5 要求的对照实验尚未进行」，
          current_default = "librosa.pyin（首选实现，非冻结选型）」。
        FILE-103-v1.md:93-94「首选实现 librosa.pyin / 是否冻结：不冻结」。
        实测环境：numpy 2.4.4 / scipy 1.17.1 / librosa 0.11.0 / soundfile 0.13.1 /
          torch 2.11.0 可用；**torchcrepe 未安装**。
修法:   不阻塞代码注入（overlay 明说 unblocks）；但「音准指标可信度」在本轮
        只能标 SKIPPED，不得标 PASS。
```

---

## C · 判定：这条管线能不能完整跑通？

**不能。**

理由（按断裂的先后顺序）：

1. **入口处就断（F1）**。`__main__.run_headless` 的规格要求它取 C1 门面，
   本版 FILE-002 已允许 import `.host`，但：
   - 规格指定的 `from .host import build_default_app` **运行期 ImportError**
     （`host/__init__.py:33` 只有 `__all__=["app"]`，不 import app）；
   - 唯一能跑的 `from .host.app import build_default_app` 的 AST key `.host.app`
     **不在** FILE-002 §8 自己的白名单里；
   - 而让 `.host` 导出它的做法被 FILE-300:70,74,76 明文禁止。
   **三份冻结文件互锁，没有一种写法能同时满足三者。**

2. **数据面装配层断（F2 + F3）**。即使入口打通，`build_surface` 也产不出数据面：
   - `pcm.mapped.reference` / `pcm.mapped.practice` / `pcm.warped.practice`
     的生产者被 FILE-104 本版明确标为**未决**，并规定必须抛 `CoreBuildError`
     （F2）。这意味着**按规格，数据面永远构建不成功**。
   - 直接后果：`timing.run` 的必需端口 `pcm.mapped.*` 永远不存在，
     **节奏维度（三个核心维度之一）必然失败**。
   - 新补的 `PRODUCER_DISPATCH` 派发表与同文件的 INV-104-1 字面量禁令互斥（F3），
     特征端口（8 个）的分派同样无法实现。

3. **结果出口断（F4 + F8）**。即使算法跑出 payload，`build_view` 产出的 `UiSeries`
   没有 `n_points` 字段，而 FILE-002 既要求写出它、又禁止用 `len(values)` 代替 ——
   `metrics.json` 无法按规格落盘（F4）；且 payload→UiView 的映射规则
   在全仓没有任何冻结处（F8）。

4. **C4 通路另有独立断点（F5）**：FILE-400 与 FILE-401/app.py 的常量名分叉，
   `launch_cockpit` 按自己的规格不可实现。该断点不阻塞无头链路（不变量 F 成立），
   但「宿主对外承诺的操作」在 C4 侧确有缺口。

**哪些环节我无法验证（如实标注，不报 PASS）**：

| 环节 | 状态 | 原因 |
| --- | --- | --- |
| 音高引擎选型对指标的影响 | **SKIPPED** | 对照实验未做（GAP-6）；torchcrepe 未安装（F14） |
| 真实音频端到端数值正确性 | **SKIPPED** | 全部实现体为 `raise NotImplementedError`；`data/in/` 为空，无输入样本 |
| `content_hash` 跨实现可比性 | **SKIPPED** | 无第二个实现，无法对照 |
| `build_view` 下采样是否 ≤ MAX_PROJECTION_POINTS | **SKIPPED** | 无实现，无投影样本可测 |
| `PRODUCER_DISPATCH` 运行期行为 | **SKIPPED** | 规格刚改、代码未写；无法验证是否真能闭合 |
| 现成机械检查 `tools/verify_shell.py` | **PASS（但不构成管线通）** | 退出码 0；它只验「壳件完整性与纯净度」，不验跨层可贯通性 |
| 全部 18 个模块 `import` | **PASS** | 探针实测 18/18 可 import |
| CLI 可执行到失败点 | **PASS（失败符合预期）** | `python3 -m harmonica_eval …` 退出码 1，stderr 为 `NotImplementedError: SHELL: FILE-002` |

**结论**：这是一套**契约层尚未闭合**的空壳系统。端口 id、字段顺序、错误码、
算法注册表这些「词表」层面做得相当严谨（`profile.assert_profile_integrity()` 实际生效，
检查 1–8 全过），但**从词表到执行的三条接缝全部断开**：
装配权（F1）、生产者分派（F2/F3）、结果出口字段（F4）。
按当前冻结文档直接注入实现，实现者会在 F1、F2/F3、F4 三处无解，
只能自行发明（正是 §22 硬失败所禁止的）。

**关于并发编辑的说明**：审查期间另一进程在持续改写规格。其中 FILE-104 的两处改动
（把 pcm.* 标为未决、补 PRODUCER_DISPATCH）**方向是诚实的** —— 它们把原先
「静默无人做」变成了「显式未决」。但 (a) 未决本身仍使管线不可构建；
(b) 新补的派发表与 INV-104-1 互斥；(c) FILE-002 的 `.host` 修正引入了新的 import 死锁。
故锚点上的判定仍是 REJECT。

---

## 探针清单（未删除）

| 文件 | 作用 | 输出 |
| --- | --- | --- |
| `.spec/review/round-1/probes-pipeline-P2/probe1_producer_dispatch.py` | produced_by 形态、importlib 解析、端口→生产者映射、14 个函数签名 vs 4 参约定 | `.out` |
| `.spec/review/round-1/probes-pipeline-P2/probe2_entry_closure.py` | `__main__` import 闭包、contract 有无会话驱动、C1 工厂位置、FILE-002/301 口径摘录 | `.out` |
| `.spec/review/round-1/probes-pipeline-P2/probe3_contract_vs_impl.py` | UiSeries 无 n_points、FILE-400 vs app.py 常量分叉、warp_path hop=0 换算 | `.out` |
| `.spec/review/round-1/probes-pipeline-P2/probe4_consumer_symmetry.py` | 12 端口的生产者/消费者两侧闭合表 | `.out` |

复现：
```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python3 .spec/review/round-1/probes-pipeline-P2/probe1_producer_dispatch.py
python3 .spec/review/round-1/probes-pipeline-P2/probe2_entry_closure.py
python3 .spec/review/round-1/probes-pipeline-P2/probe3_contract_vs_impl.py
python3 .spec/review/round-1/probes-pipeline-P2/probe4_consumer_symmetry.py
python3 tools/verify_shell.py   # 退出码 0；仅验壳件，不验贯通
```

---

## 状态汇总

| FINDING | 严重度 | 状态 |
| --- | --- | --- |
| F1 入口取 C1 门面：import 形式与白名单/FILE-300 三方互锁 | blocker | FAIL |
| F2 pcm.* 生产者「未决」→ 数据面按规格不可构建 | blocker | FAIL |
| F3 PRODUCER_DISPATCH 与 INV-104-1 字面量禁令互斥 | blocker | FAIL |
| F4 UiSeries 缺 n_points | blocker | FAIL |
| F5 FILE-400 vs FILE-401/app.py 常量分叉 | high | FAIL |
| F6 FILE-301 run_algorithms/build_view 签名自相矛盾 | high | FAIL |
| F7 warp_path read 时间窗 hop=0 | medium | FAIL |
| F8 payload→UiView 映射未冻结 | medium | FAIL |
| F9 SPEC §3 schema vs FILE-002 schema 漂移；sections 无承载 | medium | FAIL |
| F10 assert_registry_integrity 无 import 期调用 | low | FAIL（实现期待补） |
| F11 端口数 11 vs 12 漂移 | low | FAIL |
| F12 FILE-102 引用不存在的 pipeline.py/evaluator.py | low | FAIL |
| F13 pitch payload 缺 n_unpaired（已登记缺口） | low | FAIL（已知，接口变更） |
| F14 音高引擎对照实验未做 | low | **SKIPPED** |
| 18/18 模块可 import | — | PASS |
| `tools/verify_shell.py` 退出码 0 | — | PASS（仅壳件完整性） |
| 真实音频端到端数值正确性 | — | **SKIPPED**（无实现、无输入） |

**blocker 共 4 条：F1、F2、F3、F4。**

VERDICT: REJECT
