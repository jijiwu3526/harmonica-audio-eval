# FILE-401-P — `harmonica_eval/cockpit/preview.py` + `preview.html`

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/cockpit/preview.py`、`harmonica_eval/cockpit/preview.html`
> 生成依据：`SPEC.md@v2.1 §1`（开发者调试视图例外条款）· `COMPONENTS.md` G14 ·
> `contract.py`（CONTRACT-UI-v2）· `.spec/OWNER-DIRECTIVES.md` 追加 A
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-401-P（铭牌内写作 `PREVIEW-401-P`） |
| 所属组件 | COMP-C4 Cockpit —— **契约结构预览视图**（非产品界面） |
| 层级 | L3（symbol / implementation） |
| 上游 | **无运行时上游**。它只读 `..contract` 的已冻结类型，不接受任何注入数据 |
| 下游 | 浏览器（`GET /` 返回 HTML，`GET /api/contract` 返回 JSON） |
| 同层邻居 | `app.py`（FILE-401，真实投影界面）· `__init__.py`（包出口） |

**你的权限**：只实现本文件。不得修改任何其他文件，不得修改契约，
不得新增端口，不得新增依赖。

### ★ 它与 `app.py` 的区别（两者同属 C4，职责不同）

| | `app.py`（FILE-401） | `preview.py`（本文件） |
| --- | --- | --- |
| 数据来源 | 由 C1 注入的 `UiProjectionPort` | **无会话**，只读契约类型定义 |
| 显示内容 | 会话状态 / 标量 / 曲线 / 进度 / 错误 | **契约结构**（单位 / 状态 / 命令 / 字段布局 / 类型） |
| 能否显示音频分析结果 | 注入后可以 | ★ **不能，也没有**——`FILE-002` 仍是 SHELL |
| 当前实现状态 | **SHELL**（未注入） | **已实现**（负责人 2026-09-24 授权创建） |

★ **`app.py` 尚未注入，而本文件已实现。这是刻意的**：
本文件的价值恰恰在于**不依赖任何未注入的实现**。

---

## 2 · 这个文件为什么存在

删掉它会坏掉什么：

1. **契约可用性的唯一检验手段。** 本视图回答一个问题：
   *如果现在接真数据，契约够不够画界面？* 答不上来，就无法在注入前发现契约缺字段。
2. **它已经发现了两件事**（见 §7 的 NOT_SHOWN），都是注入前发现、注入后返工成本会高得多的问题。
3. **它是未来真实界面的结构预览。** 布局、状态机形状、配色可先复用。

★ 它**不是**产品界面。`SPEC.md §1` 允许的是「开发者调试视图」，
明确**不是**「面向口琴学习者的成品界面」。

---

## 3 · 你能用的东西（依赖清单，封闭）

**可以 import**：
- Python 标准库（**穷举**）：
  `__future__.annotations` · `json` · `dataclasses.fields` ·
  `http.server.BaseHTTPRequestHandler` · `http.server.HTTPServer` ·
  `pathlib.Path` · `typing.Any` · `importlib.import_module`（仅用于 `_field_docs` 读源码）
- 本包内（**精确模块**）：`..contract` 的
  `COMMAND_EFFECTS` · `COMMAND_LEGALITY` · `FIELD_LAYOUTS` ·
  `UNITS_VOCABULARY` · `PortDescriptor` · `SessionState` ·
  `UiCommandKind` · `UiScalar` · `UiSeries` · `UiView`

**禁止 import**（★ 每条都有架构理由，不是风格偏好）：
- ★ `..profile` —— **绕过 G14 直连 C2**，见 §7 的 WHY_NO_PORTS
- ★ `..core` / `..host` / `..algorithms` —— C2 / C1 / C3 内部实现
- 任何第三方包（`numpy` / `scipy` / `librosa` / `soundfile` / `torch` 等）
- 任何 CDN / webfont / 外部 JS（前端侧同样零外链）

---

## 4 · 你要实现什么（行为规格）

### `build_contract_payload() -> dict`

- **输入**：无。全部数据来自 `..contract` 的模块级冻结常量。
- **输出**：可 JSON 序列化的 `dict`，键固定为：
  `units` · `states` · `commands` · `legality` · `field_layouts` ·
  `types` · `type_docs` · `not_shown` · `port_summary`
- **各键的口径（★ 引用常量名，不要抄数字）**：

| 键 | 内容 | 实测值 |
| --- | --- | --- |
| `units` | `sorted(UNITS_VOCABULARY)` | 10 |
| `states` | `[s.value for s in SessionState]` | 6 |
| `commands` | `[{kind, effect}]`，按 `UiCommandKind` 枚举序 | 6 |
| `legality` | `[{command, allowed_states}]`，来自 `COMMAND_LEGALITY` | 6 |
| `field_layouts` | `{k: list(v) for k, v in FIELD_LAYOUTS.items()}` | 4 组 |
| `types` | 四个 dataclass 的字段名 + 类型串 | `PortDescriptor` 11 / `UiView` 9 |
| `type_docs` | 各字段在源码中的属性 docstring | 同上 |
| `not_shown` | `{"ports": _ports_status()}` —— 缺口如实上报 | 见 §7 |
| `port_summary` | `_port_summary()` | ★ 恒为 `[]`，见 §4.2 |

### ★ 4.2 `_port_summary() -> list` —— 恒返回空，且这是正确的

- **不变量**：本函数**永远返回 `[]`**。
- **原因**：它只做「`UiView` 是否已有 `port_summary` 字段」的**能力探测**；
  真实值必须由 C1 在 `snapshot()` 时投影，而 **C1 仍是 SHELL**，无处投影。
- ★ **禁止**：为让页面"看起来完整"而伪造 12 个端口。
  **缺口必须如实显示。**

### `_ports_status() -> dict`

- **输出**：`{count, implemented, decided, reason, pending}`，其中
  - `count` 恒为 `12`（12 是端口数，不随状态变）
  - `implemented` = `"port_summary" in UiView.__dataclass_fields__`
  - `decided` = 裁定记录字符串（2026-09-24，通道已裁定）
  - `pending` 随 `implemented` 在两段文案间切换

### `_Handler.do_GET(self) -> None`

- `/` → 返回 `preview.html` 字节，`Content-Type: text/html; charset=utf-8`
- `/api/contract` → 返回 `json.dumps(build_contract_payload())` 字节，
  `Content-Type: application/json; charset=utf-8`
- 其它路径 → `self.send_error(404)` 并 `return`
- ★ 两个响应分支都**必须**设置 `Content-Length`（见 §6 INV-401P-4）

### `_Handler.log_message(self, fmt, *args) -> None`

- **函数体只有 docstring**（静默访问日志）。★ 零噪声，见 `AGENTS.md` 铁律 4。

### `main() -> None`

- 用 `HTTPServer((BIND_HOST, BIND_PORT), _Handler)` 启动
- `KeyboardInterrupt` → `server.shutdown()`
- 打印三行提示（地址 / 手机端预留说明 / Ctrl-C 退出）

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| 请求路径既非 `/` 也非 `/api/contract` | **显式失败**，不静默重定向 | `send_error(404)` |
| 端口被占用 | **显式失败**，不换端口、不重试 | `OSError`（不吞） |
| 收到 `KeyboardInterrupt` | 正常关闭 | 调 `server.shutdown()` 后返回 |
| `preview.html` 缺失 | **显式失败** | `FileNotFoundError`（不返回空页） |

★ 宪章 §5.6：禁止静默降级。
★ **不得**捕获异常后返回默认值页、不得自动改用备用端口。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-401P-1 | **只监听 `127.0.0.1`**，不默认监听公网 | §8 脚本 1 |
| INV-401P-2 | **零第三方依赖**：Python 侧无第三方 import，HTML 侧无外链 | §8 脚本 2、3 |
| INV-401P-3 | **不 import `profile`**（G14） | §8 脚本 2（AST 级） |
| INV-401P-4 | 两个端点可用且 `Content-Length` 正确 | §8 脚本 4 |
| INV-401P-5 | **12 端口缺口如实显示**，不伪造数据 | §8 脚本 5 |
| INV-401P-6 | 前向兼容：契约实施后本页**零改动**自动生效 | §8 脚本 6 |
| INV-401P-7 | 豁免机制仍生效（不被当成 SHELL 检查） | §8 脚本 7 |

---

## 7 · 边界（明确不做）

- 不显示任何**音频分析结果**（`FILE-002` 仍是 SHELL，没有结果可显示）
- 不做 DSP、不读音频文件、不解析 payload 语义
- 不在界面上发明契约里没有的东西
- 不默认监听公网（改 `BIND_HOST` 是**预留**，不是默认行为）

### ★ NOT_SHOWN：本页**当前不显示 12 个端口** —— 这是本视图的重要产出

**PORTS_CHANNEL_DECIDED —— 通道已裁定**

- **裁定**（负责人，2026-09-24）：**由 C1 在 `UiView` 里投影端口摘要**，
  C4 只消费 `UiView`，不直连 C2。
- **依据**：`COMPONENTS.md` G14 —— C4 的权威边界「只与 C1 通讯，不直连 C2/C3」。
- **WHY_NO_PORTS**：12 个端口由 C2 发布（`profile.py` 的 `PORTS`，FILE-004 /
  COMPONENT: COMP-CONFIG）。**C4 直接 import `profile` ＝ 绕过 G14 直连 C2**，
  比违反字面约束严重得多。
- 契约层已定义 `PortDescriptor`（11 字段）但**零实例**——
  它只是「端口长什么样」的类型定义，不是那 12 个端口本身。
- ★ **契约已实施**：`UiView` 已增 `port_summary: Sequence[PortDescriptor]`
  （CONTRACT-UI 已升 v2）。但**真实值仍为空**，因为 C1 仍是 SHELL。
  故 `implemented` 已是 `True`，而 `port_summary` 仍是 `[]` ——
  **这两个状态不同不是缺陷，是「通道已通、投影方未实现」的准确反映。**

★ 若你发现"不做这个就实现不了" → **不要做**，转 §10。

---

## 8 · 怎么验证你写对了

```bash
# 启动服务（另开终端）
PYTHONDONTWRITEBYTECODE=1 python3 -m harmonica_eval.cockpit.preview
```

★ 以下脚本可被 `tools/check_bi_scripts_exec.py` 抽取执行
（**必须是 bash 围栏内的 heredoc 或 `python -c`**）。

```bash
python3 - <<'PY'
import ast, pathlib
p = pathlib.Path("harmonica_eval/cockpit/preview.py")
tree = ast.parse(p.read_text(encoding="utf-8"))
mods = set()
for n in ast.walk(tree):
    if isinstance(n, ast.Import):
        mods.update(a.name for a in n.names)
    elif isinstance(n, ast.ImportFrom):
        base = n.module or ""
        mods.add(base)
        mods.update(f"{base}.{a.name}" for a in n.names)
banned = ("numpy", "scipy", "librosa", "soundfile", "torch")
hit = [m for m in mods if any(b in m for b in banned)]
assert not hit, f"第三方依赖泄漏: {hit}"
assert "profile" not in mods, f"违反 G14：import 了 profile -> {mods}"
assert "core" not in mods and "host" not in mods, f"跨层 import -> {mods}"
assert any("contract" in m for m in mods), "必须 import ..contract"
print("OK 只依赖 ..contract + 标准库，未 import profile")
PY
python3 - <<'PY'
import pathlib, re
t = pathlib.Path("harmonica_eval/cockpit/preview.py").read_text(encoding="utf-8")
m = re.search(r'^BIND_HOST\s*=\s*"([^"]+)"', t, re.M)
assert m, "未找到 BIND_HOST"
assert m.group(1) == "127.0.0.1", f"默认必须绑定本机回环，实为 {m.group(1)}"
print("OK BIND_HOST=127.0.0.1（不默认监听公网）")
PY
python3 - <<'PY'
import pathlib, re
t = pathlib.Path("harmonica_eval/cockpit/preview.html").read_text(encoding="utf-8")
bad = re.findall(r'https?://[^\s"\']+|//(?:cdn|unpkg|jsdelivr)\S*', t)
assert not bad, f"前端存在外部依赖: {bad}"
assert "viewport" in t, "缺 viewport meta（手机端不可用）"
print("OK 零外链 + 有 viewport meta")
PY
python3 - <<'PY'
import json, subprocess, sys, time, urllib.request, os, signal
port = 8765
proc = subprocess.Popen([sys.executable, "-m", "harmonica_eval.cockpit.preview"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
try:
    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/contract", timeout=1).read()
            break
        except Exception:
            time.sleep(0.25)
    else:
        raise AssertionError("服务未在 10 秒内就绪")
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as r:
        html = r.read()
        assert r.status == 200 and len(html) > 2000, f"GET / 异常: {r.status} {len(html)}"
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/contract", timeout=3) as r:
        assert r.headers.get("Content-Length") == str(len(r.read()))
        d = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/contract", timeout=3))
    assert len(d["units"]) == 10, d["units"]
    assert len(d["states"]) == 6 and len(d["commands"]) == 6
    print(f"OK 两端点可用：units={len(d['units'])} states={len(d['states'])} cmds={len(d['commands'])}")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
PY
python3 - <<'PY'
import json, subprocess, sys, time, urllib.request, os
port = 8765
proc = subprocess.Popen([sys.executable, "-m", "harmonica_eval.cockpit.preview"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
try:
    for _ in range(40):
        try:
            d = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/contract", timeout=1))
            break
        except Exception:
            time.sleep(0.25)
    else:
        raise AssertionError("服务未就绪")
    p = d["not_shown"]["ports"]
    assert p["count"] == 12, p
    assert isinstance(p["implemented"], bool), p
    assert d["port_summary"] == [], f"缺口必须如实留空，实为 {d['port_summary']}"
    print(f"OK 缺口如实显示：count={p['count']} implemented={p['implemented']} port_summary=[]")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
PY
python3 - <<'PY'
from harmonica_eval.contract import UiView
assert "port_summary" in UiView.__dataclass_fields__, "契约未实施"
src = open("harmonica_eval/cockpit/preview.py", encoding="utf-8").read()
assert "getattr(UiView" in src, "未用前向兼容读取（契约变动会致页面崩溃）"
print("OK 契约已实施且本页用前向兼容读取（未来字段变动零改动）")
PY
python3 - <<'PY'
import ast
import pathlib
import re

# ★ 用 AST 解析豁免名单本身，而不是匹配某一行字面量 ——
#   字面量匹配会在名单增删时立刻失效（本判据曾因 bootstrap/registry
#   加入名单而误报「豁免名单缺失」）。AST 方式与书写格式无关。
#
# ★★ 2026 修订：名单已统一到单一真相源 tools/authorized_impl.py 的
# ★★ AUTHORIZED_IMPL（原先散在 verify_stubs_raise.py 的
# ★★ AUTHORIZED_IMPL_FILES 顶层赋值）。判据随之指向真相源 ——
# ★★ 【判据跟形态走，而不是逼形态退回旧形状】。
path = pathlib.Path("tools/authorized_impl.py")
tree = ast.parse(path.read_text(encoding="utf-8"))

authorized: set[str] | None = None
for node in tree.body:
    # ★ 带类型注解的赋值是 ast.AnnAssign（truth source 用 Final[...] 声明），
    #   不带注解的才是 ast.Assign —— 两种都要认。
    target_name = None
    value_node = None
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        target_name, value_node = node.target.id, node.value
    elif isinstance(node, ast.Assign):
        for t_ in node.targets:
            if isinstance(t_, ast.Name):
                target_name, value_node = t_.id, node.value
                break
    if target_name != "AUTHORIZED_IMPL" or value_node is None:
        continue
    # 值是 MappingProxyType({...}) 调用 —— 取其唯一位置参数里的 dict 字面量
    if isinstance(value_node, ast.Call) and value_node.args:
        value_node = value_node.args[0]
    raw = ast.literal_eval(value_node)
    authorized = set(raw.keys()) if isinstance(raw, dict) else set(raw)
    break
assert authorized is not None, "authorized_impl.AUTHORIZED_IMPL 未定义"
assert "harmonica_eval/cockpit/preview.py" in authorized, sorted(authorized)
print("OK 豁免名单存在且含 preview.py：", len(authorized), "项")

# ★ 机制而非文本：必须存在「集合成员判断」，不得放宽成目录 / 前缀匹配
# ★★ 2026 修订：判据【不】绑死变量名。它要守的是两条语义：
# ★★   (a) 豁免集合派生自单一真相源（不是各自维护一份字面量）
# ★★   (b) 【豁免判定那几行】用 `in` 成员判断，不是 startswith / 目录前缀
# ★★ 注意：文件里别处（模块名、stdlib 判断）用 startswith 是合法的，
# ★★ 所以不能整体禁 startswith —— 只能守住「豁免判定」这一处。
vsrc = pathlib.Path("tools/verify_stubs_raise.py").read_text(encoding="utf-8")
assert "from authorized_impl import" in vsrc, "verify_stubs_raise 未从单一真相源派生豁免集合"

exempt_lines = [
    ln for ln in vsrc.splitlines()
    if ("AUTHORIZED_IMPL_FILES" in ln or "_AUTHORIZED_REPO_REL" in ln)
    and not ln.lstrip().startswith("#")
    and "★" not in ln          # 跳过铭牌/注释里的说明文字
    and "import" not in ln
    and not re.match(r"\s*\w+\s*=\s*set\(", ln)   # ★ 派生赋值本身不是判定行
]
assert exempt_lines, "找不到任何使用豁免集合的判定行"
for ln in exempt_lines:
    assert "startswith" not in ln, f"豁免判定不得用 startswith（会误放行 ingest_extra.py 之类）：{ln.strip()}"
    assert re.search(r"\bin\b", ln), f"豁免判定必须用 in 成员判断：{ln.strip()}"
print(f"OK 豁免派生自单一真相源，{len(exempt_lines)} 处判定均为集合成员判断")
for bad in ("startswith(\"harmonica_eval/cockpit", "startswith('harmonica_eval/cockpit",
            'rel[:len("harmonica_eval/cockpit")]', "rglob(\"*.py\") and \"cockpit\""):
    # ★ 本段读的是 tools/verify_stubs_raise.py，★ 该文件的源码变量名是 vsrc。
    # ★ 原写 `src` 是变量名串味——★ src 是上一个脚本（preview.py）的变量，
    # ★ 跨脚本不可见，★ 于是这里恒抛 NameError，★ 判据从未真正执行过这一句。
    assert bad not in vsrc, f"豁免被放宽成目录/前缀匹配：{bad}"
print("OK 豁免按精确路径生效，且为成员判断")

# ★★ 同一机制在 verify_shell.py 里也必须成立 ★★
#   实测事故：该文件用 `rel in GROUND` 精确成员判断，但**无人看守**——
#   把它改成 `rel.startswith("harmonica_eval")` 后 verify_shell 仍报「通过」，
#   因为没有任何判据在检查这件事。本段就是那个看守。
vs = pathlib.Path("tools/verify_shell.py")
vs_tree = ast.parse(vs.read_text(encoding="utf-8"))

# GROUND 与 GROUND_IMPL_NOTES 必须是【可静态还原】的集合，不得是拼接推导出来的。
# ★ 2026-09-24 修正（判据自身缺陷，非实现问题）：
#   verify_shell.py 的 GROUND_IMPL_NOTES 写作 dict(_AUTHORIZED_NOTES)、
#   GROUND 又用 |= set(_AUTHORIZED_REPO_REL) 并入真相源 ——
#   原判据 literal_eval(node.value) 直接抛
#   "malformed node or string on line 120: <ast.Name object>"。
# ★ 修法：沿「单参容器构造调用 → 模块级别名」逐层解引用，
#   终点必须是可 literal_eval 的字面量节点。
# ★ 判据跟形态走，而不是逼真相源退回旧形状。
def _module_assigns(tree: ast.Module) -> dict[str, ast.expr]:
    out: dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.setdefault(node.target.id, node.value)
        elif isinstance(node, ast.Assign):
            for t_ in node.targets:
                if isinstance(t_, ast.Name):
                    out.setdefault(t_.id, node.value)
    return out

def _resolve(node: ast.expr | None, assigns: dict[str, ast.expr]) -> object | None:
    """沿「单参构造调用 → 模块级别名」解引用，返回可 literal_eval 的值。"""
    seen: set[str] = set()
    cur = node
    while isinstance(cur, ast.Call) and cur.args and not cur.keywords:
        cur = cur.args[0]
        if isinstance(cur, ast.Name):
            if cur.id in seen:          # 别名环，停止
                return None
            seen.add(cur.id)
            cur = assigns.get(cur.id)
            if cur is None:
                return None
    if cur is None:
        return None
    try:
        return ast.literal_eval(cur)
    except (ValueError, TypeError):
        return None

vs_assigns = _module_assigns(vs_tree)
authorized_shell: set[str] = set()
# ★ 优先用 AST 静态还原；取不到时（真相源是 import 进来的别名）退回运行时求值。
# ★ ★ 两条路径都必须是【集合内容】而不是「某行字面量」——形态可变，语义不可变。
for key in ("GROUND", "GROUND_IMPL_NOTES"):
    val = _resolve(vs_assigns.get(key), vs_assigns)
    if val is None:
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location("_vs_probe", str(vs))
        _mod = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_mod)
        val = set(getattr(_mod, key))
    else:
        val = set(val)
    authorized_shell |= val
assert authorized_shell, "verify_shell.py 未定义 GROUND / GROUND_IMPL_NOTES"
assert "harmonica_eval/cockpit/preview.py" in authorized_shell, authorized_shell

# ★ 判定必须是成员判断：AST 级确认存在 `rel in GROUND` 形式的比较
vs_src = vs.read_text(encoding="utf-8")
member_judgements = [
    n for n in ast.walk(vs_tree)
    if isinstance(n, ast.Compare)
    and isinstance(n.left, ast.Name) and n.left.id == "rel"
    and any(isinstance(o, ast.Name) and o.id == "GROUND" for o in n.comparators)
    and any(isinstance(op, (ast.In,)) for op in n.ops)
]
assert member_judgements, "verify_shell.py 的豁免判定必须是 `rel in GROUND` 成员判断"

# ★ 不得放宽成目录 / 前缀匹配（AST 级：rel 不得参与 startswith / 切片）
for node in ast.walk(vs_tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "startswith":
            seg = ast.unparse(node.args[0]) if node.args else ""
            assert "rel" not in seg, f"豁免被放宽成前缀匹配：startswith({seg})"
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) \
            and node.value.id == "rel":
        raise AssertionError("豁免被放宽成切片匹配：rel[...]")

print("OK verify_shell.py 的豁免同样是精确路径成员判断")
PY
```

**验收判据**（可机械判定的，而非"看起来对"）：
- [ ] 脚本 1–3 全打印 `OK`（无第三方、无 `profile`、无外链、有 viewport）
- [ ] 脚本 4 打出 `units=10 states=6 cmds=6`
- [ ] 脚本 5 打出 `port_summary=[]`（缺口未被伪造）
- [ ] 脚本 6 确认契约已实施且本页用 `getattr` 前向兼容
- [ ] 脚本 7 确认豁免按精确路径生效
- [ ] ★ 启动服务后**人工**打开 `http://127.0.0.1:8765/`，确认状态机 SVG 与各卡片可渲染

★ 注：脚本 4 / 5 会起真实服务。**若 8765 被占用会抛 `OSError` —— 那是正确的显式失败**，
★ 不要为此改判据去吞异常。先 `lsof -ti :8765 | xargs kill` 清理。

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] 脚本 1–7 的真实输出（不得手写）
- [ ] 浏览器实际渲染的截图或描述（状态机 SVG + 卡片）
- [ ] `python3 -m py_compile preview.py` → exit 0
- [ ] ★ **若改动过 `preview.html` 的 CSS**：说明手机端窄屏如何折行
  （判据：`grid-template-columns: repeat(auto-fill, minmax(260px,1fr))`，
  触控目标 ≥ 44px，不依赖 hover）

---

## 10 · ★ 何时必须停止并上报（§22 硬失败对策）

**以下情况必须停止，提交 `MOLD BREAK`，不得自行设计：**

1. 你发现要显示 12 个端口**必须** import `profile` —— 那会违反 G14，
   **不得**自行放宽；上报即可（通道已裁定为 C1 投影）
2. 本文件与任何上游工件**冲突**
3. 你需要的依赖**不在 §3 清单里**
4. §4 的行为规格**不足以确定唯一实现**
5. 你认为 §4 的规格本身**是错的**

**上报格式**（宪章 §37 Gate Challenge）：
```
GATE CHALLENGE
- 相关 Requirement：
- 相关 Build Instruction 章节：
- 实际需要 vs 规格给出：
- 为什么冲突：
- 复现证据：
- 建议的上游处理位置：
```

**绝对禁止**：
- 先做一个"能跑的 workaround"，以后再说（§38 明文禁止）
- 伪造 12 个端口让页面"看起来完整"
- 用 AST 静态读 `profile.py` 来绕过 G14 的字面约束
- 静默缩小范围

---

## 附：本文件的冻结常量速查

| 常量 | 值 | 来源 |
| --- | --- | --- |
| `BIND_HOST` | `"127.0.0.1"` | 本文件 `:100` |
| `BIND_PORT` | `8765` | 本文件 `:101` |
| `UNITS_VOCABULARY` 长度 | 10 | `contract.py` |
| `SessionState` 成员数 | 6 | `contract.py` |
| `UiCommandKind` 成员数 | 6 | `contract.py` |
| `FIELD_LAYOUTS` 组数 | 4 | `contract.py` |
| `PortDescriptor` 字段数 | 11 | `contract.py` |
| `UiView` 字段数 | 9（含 `port_summary`） | `contract.py`（CONTRACT-UI-v2） |
| 端口数 | 12 | `profile.py` `PORTS`（★ **仅数值引用，本文件不 import**） |
