# cockpit — 界面层（可弃）

> **一句话**：C4 是口琴双音频对比的**界面投影层**。它把 C1 发布的快照画成人能读的东西，
> 并把人的动作翻译成命令交回 C1。它**不碰音频、不做 DSP、不认识任何具体算法**。

★ **本文档是全项目对「多端移植」影响最大的一份。** 下面 §4 回答那个大问题：
**换手机前端时，这些代码能全扔吗？**

★ **本文是索引，不是权威。** 权威在 `.spec/` 与源码铭牌。
★ 本文任何内容与它们冲突时以它们为准，并把冲突报给负责人。

---

## 1 · 我是谁

```
位置：C1（host，算法与数据面） ←→ C4（cockpit，本目录） ←→ 人
      C4 只通过 UiProjectionPort 与 C1 说话
```

| 文件 | 行数 | 是什么 |
|---|---|---|
| `cockpit/app.py` | 1892 | HTTP 服务 + 静态资源 + JSON 端点 |
| `cockpit/__init__.py` | 89 | 公开面：`__all__` 与 `launch_cockpit` |
| `cockpit/preview.py` | — | 契约**结构**预览页（非产品界面、非本包入口） |
| `serve_ui.py` | 276 | 进程装配点：建会话 → 装两端音频 → 建数据面 → 起服务 |
| `__main__.py` | 520 | 无头 CLI 入口 |

★ **三个可弃文件合计 2688 行**，★ 而核心（`contract` + `profile` + `core` + `algorithms` + `host/app`）
★ 是 7301 行，★ 合计 9989。
★ **即「界面 27% / 核心 73%」**（2688/9989 = 27%）——★ 这正是负责人「大部分代码不用换」的依据。

★ 前端源码不在本包内，在 `harmonica_eval_web/`（React + Vite，6 个源文件 730 行）。
★ **本包不 import 它**，★ 只在运行时从磁盘取它的构建产物（`app.py:246`）。

### 无头入口

C4 缺席时，正式无头入口仍是 `harmonica_eval/__main__.py`：接收参考与练习两段音频，
驱动「建数据面 → 跑算法」的完整流程，并落盘 `metrics.json` 与同目录的 `report.md`。
未指定 `--out` 时缺省落点是 `data/out/metrics.json`。入口只消费 C1 发布的 `UiView` 投影，
**不做 DSP、不导入 cockpit**。五个缺陷样本均 rc=0 并落盘 `metrics.json`（16 scalars + series）。

---

## 2 · 我吃什么

| 输入 | 来自 | 说明 |
|---|---|---|
| `UiProjectionPort` | `serve_ui` 注入的 `HostApp` | ★ **只有两个方法，见 §4** |
| `/dataset` | 本目录扫数据集 | 10 首曲子 / 70 个 wav / `plugins` 清单 |
| 浏览器请求 | 人 | `GET /`、`GET /view`、`GET /dataset`、`POST /command` |

★ **不读音频、不解析 WAV、不 import 具体算法、不持有注册表。**

---

## 3 · 我吐出什么

| 出 | 格式 | 消费方 |
|---|---|---|
| `GET /view` | `UiView` 的 JSON（**9 个字段**） | React 前端 |
| `GET /dataset` | 曲名分组 + 路径 + `plugins` | React 前端 |
| `POST /command` | 收 `UiCommand`，执行后返回页面 | 人 / 前端 |

★ `UiView` 九字段（`dataclasses.fields(UiView)` 实测）：
```
session_id · state · series · scalars · progress
port_summary · error_code · error_detail · note
```

### 插件懒加载（2026-09-25 负责人裁定后新增）

```bash
POST /command {"kind":"RUN_ALGORITHMS","only":["pitch"]}
→ /view 里 scalars 分组 ['pitch']、series 分组 ['pitch']
```

★ **判据是「`/view` 里没有」，不是「界面没显示」。** 后者是伪懒加载。
★ `only=[]` 报「未指定任何算法 id：…与注册表 [...] 无交集」，
★ **不会**谎称「注册表快照为空」（那曾是一个真缺陷，已修）。
★ 传不存在的 id 报「未注册的算法 id：['…']」——**不静默忽略**。

---

## 4 · ★ 我不做什么 ★

### 4.1 换手机前端时，这些能全扔吗？

★★★ **能扔界面，不能扔契约。★★★

```
可弃（2688 行）                  不可弃
────────────────────────────    ──────────────────────────
cockpit/app.py     1892 行      UiProjectionPort 的两个方法
serve_ui.py         276 行      UiView 的九个字段
__main__.py         520 行      UiCommand 的六个 kind
                                  COMMAND_LEGALITY 的状态约束
```

★ **实测证据**（`inspect` 跑出来的，非转述）：
```python
UiProjectionPort 公开方法 = ['snapshot', 'submit']   → 2 个
  snapshot (self) -> UiView
  submit   (self, command: UiCommand) -> None
app.__all__ = 14 项
```

★★ **★ 换前端时唯一要守住的是这两个签名与语义 ★★**
```
★ ★ 改了它们，C4 就得直连 C2，★ 那违背 G14：
★ ★ 「C1 不得为补全信息而让 C4 直连 C2」
★ ★ ★ 而那正是「深组件 / 降低信息熵」这个决定【兑现的地方】
★ ★ ★ ★ 手机前端（Swift / Kotlin / React Native）只要能表达
★★ ★★      snapshot() → 九字段 JSON
★★ ★★      submit(command) → 无返回值
★★ ★★ 那核心 7301 行【一行不用改】
★★ ★★ 而 2688 行界面 + 730 行 React【全部可以重写】
```

★ **注意 `submit` 没有 `session_id` 参数**——★ session_id 在 `UiView` 快照里。
★ 端口是「一个前台看一个会话」的刻意窄化，★ 而那正是「深接口」的样子。

### 4.2 本层的其他边界

```
❌ 不 import 任何具体算法（pitch / timing / dynamics 一律不认识）
❌ 不持有 Registry 或注册表快照
❌ 不做 DSP、不读 WAV、不碰采样点
❌ 不发明第 7 种命令（六个 kind 是冻结的）
❌ 不用 HTML disabled 属性（它不可聚焦，读屏拿不到原因）→ 用 aria-disabled
❌ 不给某个具体算法写特例（分组按 key 前缀现算，★ 不写死三段）
❌ 不引入图表库（会自己重采样，★ 让图上的数与 metrics.json 对不上）
```

★ **监听边界**：恒绑 `LOCAL_BIND_HOST = "0.0.0.0"`。
★ 负责人裁定「直接支持局域网访问，这只是测试，没有安全问题」，
★ 故不加认证、不做 CORS、不设 Cookie。

---

## 5 · ★ 两条实测教训（★ 别再踩）★

### 5.1 MIME 给错 → 页面白，而门禁全绿

```
改前：/assets/index-*.js  →  Content-Type: text/html
改后：/assets/index-*.js  →  Content-Type: text/javascript; charset=utf-8
       /assets/index-*.css →  Content-Type: text/css; charset=utf-8
```

★ 浏览器对 `<script type="module">` 的 MIME 校验极严，★ 收到 `text/html`
★ **直接拒绝执行** → `<div id="root">` 永远是空的。

★★ 而当时的表现是：**端点全通、HTTP 200、`/view` 正常，而页面全白。★★
★★ 那正是「门禁全绿而功能全坏」的一个实例。★★
★★ **所以「端点 200」不是证据，「浏览器里渲染出内容」才是。**

★ **实测：首屏 HTML 约 12 KB，★ 但里面【没有】`<select>` / `<optgroup>` / `<table>`**
★（各 0 个）。★ 那些由浏览器执行 JS 后从 `/view` 与 `/dataset` 拉取。
★ **所以「首屏没有下拉框」是 React 的正常形态，★ 不是「选曲面板没实现」。**

### 5.2 三个死按钮曾被删（能力没丢）

```
曾有 6 个按钮：选择参考演奏 / 选择练习演奏 / 构建数据面 / 运行算法 / 取消 / 重置会话
★ 前三个在 DATA_READY 下永远置灰（COMMAND_LEGALITY 不含该状态）
★ ★ 负责人明令删除（★ 原话「你这个自己都报错，★ 你让我怎么搞啊」）
★ ★ 而那五条命令仍由下拉框的 change 事件串行下发 ——★ 能力没丢，★ 只是不由按钮呈现
```

★ **教训**：界面元素可以删，★ **但删之前先确认能力有别的入口。**

---

## 6 · 旧文与代码的冲突（★ 本轮实测，★ 已按代码/裁定为准修正 ★）

| # | 旧文写的 | 代码/裁定实际是 |
|---|---|---|
| 1 | 「**零依赖铁律**：无 npm、无 CDN、无外部字体、无图表库、无 `<script src>`、无 `<link>`」（旧 :58） | ★ **2026-09-25 负责人裁定：前端允许依赖。** 现为 Vite + React，`index.html` 确有 `<script type="module">` 与 `<link>` |
| 2 | 「【规格内部冲突 · 仍未裁定】C4『不得加入 HTTP』与 FILE-401 冲突」（旧 :114） | ★ **已裁定**（同上）。HTTP 是现状，★ 且 FILE-401 冻结的正是本机 HTTP 方案 |
| 3 | 讲 `runSelection(ref, pra)` 在 Python 侧（旧 :65） | ★ 现在在 `harmonica_eval_web/src/api.js:24`；Python 侧只发 `POST /command` |
| 4 | `app.py` 1605 行 | ★ **实测 1892 行**（React 改造后增长） |
| 5 | 「🔴 GC-204-01：C1 session API 尚未统一」 | ★ 已统一：`submit(self, command)` **无 session_id**（session_id 在 `UiView` 快照里） |
| 6 | 「✅ GC-204-08 已关闭」 | ★ 仍成立：C4 不 import 具体算法、不持有注册表 |

★ **第 1、2 条是「已废止的阶段态」**——★ 写在这里是为了让后来者知道
★ **它们曾经存在，且已被裁定推翻。**

---

## 7 · 怎么验证这一层

```bash
# 起服务（不自动开浏览器）
DSH_NO_BROWSER=1 python3 -m harmonica_eval.serve_ui \
  --reference harmonica_mvp_dataset/01_奇异恩典/标准旋律版.wav \
  --practice  harmonica_mvp_dataset/01_奇异恩典/练习曲/05_漏音断句.wav
```

★ 端口从 8721 起顺延，★ **不要只探测 8721**（★ 历史上栽过四次）。

```bash
curl -s http://127.0.0.1:<端口>/view | python3 -m json.tool | head -20
curl -s -X POST http://127.0.0.1:<端口>/command \
  -H 'Content-Type: application/json' \
  -d '{"kind":"RUN_ALGORITHMS","only":["pitch"]}'
```

★ 前端改动后要重建：`cd harmonica_eval_web && npm run build`。
★ **`dist/` 不入库**，★ 所以 clone 下来必须先构建，★ 否则界面回落到旧字符串页
★（★ 那个回落是刻意留的降级路径，★ 而它会掩盖「React 版根本没跑」这件事）。

---

## 8 · 相关规格

- [`FILE-400-v1.md`](../../.spec/build/FILE-400-v1.md) — C4 公开面（`__all__` 与 `launch_cockpit`）
- [`FILE-401-v1.md`](../../.spec/build/FILE-401-v1.md) — 本层实现骨架
- [`FILE-499-v1.md`](../../.spec/build/FILE-499-v1.md) — 进程装配（`serve_ui`）
- [`FILE-003-v1.md`](../../.spec/build/FILE-003-v1.md) — 契约（含 `UI_PAYLOAD_KEYS[RUN_ALGORITHMS]` 的 `only`）
- [`docs/多端开发与可复用路线.md`](../../docs/多端开发与可复用路线.md) — 负责人对多端方向的裁定
