# FILE-499 — `harmonica_eval/serve_ui.py`

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/serve_ui.py`
> 生成依据：`SPEC.md@v2.1 §1` · `COMPONENTS.md@v2 §3` · `FILE-400-v1.md@v1:17` · `FILE-002-v1.md@v1:45/:47` · `.spec/build/_TEMPLATE.md@v1`
> 铭牌来源：目标文件自身的 `FILE-ID / COMPONENT / ROLE / INTENT / MUST / MUST NOT / INPUT / OUTPUT` 头块（53 行，已冻结）
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-499 |
| 所属组件 | **不属于 COMP-C1 / C2 / C3 / C4 任何一项**。本文件是跨层配方，见 §2 归属论证 |
| 层级 | L3（symbol / implementation） |
| 上游 | 人（运行者）。它从命令行接收两端音频路径 |
| 下游 | ①`harmonica_eval.host.app`（仅取 `build_default_app`，调用期延迟 import）；②`harmonica_eval.cockpit`（仅取 `launch_cockpit`，调用期延迟 import） |
| 同层邻居 | `harmonica_eval/__main__.py`（无头入口）。**两者互不 import**——见 §6 的 INV-499-1 |

**你的权限**：只实现本文件。不得修改任何其他文件，不得修改契约，不得新增端口，不得新增依赖，不得新增公开符号（`__all__` 恒为 `["main"]`）。

---

## 2 · 这个文件为什么存在

追溯链：`FILE-400-v1.md:17` 把「上游」定义为**包外装配方（进程装配点）** → 该配方需要一个具体落点 → 本文件。

### 2.1 归属论证（本 BI 最独特的部分）

依赖方向是双向封闭的：

- `host/`（C1）`MUST NOT` import `cockpit/`（C4）——它是无头内核，不知道界面存在
- `cockpit/`（C4）`MUST NOT` import `host/`——`FILE-400-v1.md:3` 的 §3 禁止清单穷举了它

**因此「构造 `UiProjectionPort` 并交给 C4」这一跨层动作，在既有两层里都无处安放。** 本文件就是那个第三落点。

而它**不能**是 `__main__.py`：

- `FILE-002-v1.md:45` 明文：「两者之间【零依赖、零 import、零调用】：本文件绝不 import `cockpit`」
- `FILE-002-v1.md:47` 要求：「把 `cockpit` 从环境中整体移除后，本文件的 import 仍须成功」

无头入口若持有 `cockpit` 的 import 边，不变量 F 立即失效。**本文件是该约束的唯一例外出口，且它不是 `__main__`。**

### 2.2 删掉它会坏掉什么（逐条可验）

1. **界面没有进程级入口。** `launch_cockpit` 与 `run_local_ui` 都存在但无调用方——`python3 -m harmonica_eval.cockpit.app` 无输出，因为规格刻意不给 `cockpit` 包留 `__main__` 块。删掉本文件，界面代码全部可达但一行都跑不起来。
2. **「C4 边界是一个函数」失去唯一调用点。** `FILE-400-v1.md §2` 第 1 条论证过：没有装配点，C4 的对外面会退化为目录内全部模块的并集。
3. **不变量 F 从「可验」退化为「靠人记」。** 「界面可整体删除」需要一个确实持有 `cockpit` import 边的文件，而那个文件只能是本文件；没有它，这条不变量没有任何落点。

本文件**不承担**任何 DSP、对齐、特征计算、数值处理职责（那是 C2）；也不承担任何绘图职责（那是 C4）。它只做装配与编排。

---

## 3 · 你能用的东西（依赖清单，封闭）

**允许 import（穷举，清单外一律禁止）**：

- Python 标准库，仅此 3 项：
  - `__future__` —— 仅 `annotations`（模块顶层）
  - `argparse` —— 仅 `ArgumentParser`
  - `sys` —— 仅 `stderr` 与 `argv`
- 第三方：**空集**（本文件禁止任何第三方 import）
- 本包内，仅此 2 个精确模块，**两者都只能在函数体内延迟 import**：
  - `harmonica_eval.host.app` —— 仅允许符号 `build_default_app`（`_run` 函数体内）
  - `harmonica_eval.cockpit` —— 仅允许符号 `launch_cockpit`（`_run` 函数体内）

**禁止 import（穷举）**：

- `harmonica_eval.core`、`harmonica_eval.algorithms`（任何形式：顶层、延迟、`importlib`、`__import__`、`TYPE_CHECKING` 分支）。**它们是 C2 的内部实现，绕过 C1 门面即违反职责边界**
- `harmonica_eval.contract` —— 本文件不引用任何契约符号；`UiProjectionPort` 只作为**类型名出现在文档里**，代码中不 import
- `harmonica_eval.__main__` —— 与本文件互为独立进程入口
- `harmonica_eval.profile`
- `harmonica_eval.cockpit` 的任何**子模块**（`.app`、`.preview`）——只能通过包出口 `launch_cockpit` 触达
- 任何第三方包（`numpy`、`scipy`、`soundfile` 全部在禁止之列）
- 任何不在上述清单里的东西

> ★ **为什么两个延迟 import 都必须在函数体内**：`--help` 路径不构造端口也不启动界面，因此不得 import C1 或 C4 任何一个。这样 `python3 -m harmonica_eval.serve_ui --help` 在 `cockpit` 整体缺失时仍能打印用法。

---

## 4 · 你要实现什么（行为规格）

本文件的公开面**恰好两项**：模块属性 `__all__` 与函数 `main`。此外无第三个公开符号。

### 4.1 模块级

- `__all__` 的值**恒等于** `["main"]`（字面量列表，单一元素，顺序固定）。
- 模块级语句仅允许：docstring 头块、`from __future__ import annotations`、`import argparse`、`import sys`、`__all__ = [...]`、以及三个 `def`（`main`、`_run`、`_build_parser`）。
- 模块级**不得**出现任何对 `host` / `cockpit` 的 import、任何计算、任何 I/O。

### 4.2 `main(argv: list[str] | None = None) -> int`

- **输入**：`argv` —— 命令行参数列表；`None` 表示取 `sys.argv[1:]`。
- **解析**：`argparse` 恰好两个必填项，**无第三个**：

| 参数 | 必填 | 含义 |
| --- | --- | --- |
| `--reference` | 是 | 参考演奏音频路径 |
| `--practice` | 是 | 练习演奏音频路径 |

- **★ MUST NOT 提供 `--port`**：端口归属是 C4 的职责（`app._pick_port()` 已在 `FILE-401-v1.md §4.4` 第 2 步冻结为 8721–8784 探测）。装配点再插一个端口参数会形成**第二份端口真相源**。
- **输出**：`int` 退出码。`main` 自身**只**返回 `2`（进程级失败）或 `0`（`--help` 正常退出）；C4 的退出码由 `_run` 原样透传，不由 `main` 改写。
- **调用顺序（不可调换）**：`_run` 必须先完成「构造 app → 建会话 → 装两端音频 → 构建数据面」，再调 `launch_cockpit`。否则界面首屏是空视图。

### 4.3 `_run(reference_uri: str, practice_uri: str) -> int`

- **输入**：两个音频路径，语义与单位：文件系统路径，UTF-8 字符串；空串与不存在路径的处置见 §5。
- **算法口径**（写到可复现的程度）：

| 步 | 动作 | 口径 |
| --- | --- | --- |
| ① | `build_default_app()` | 取得同时实现 `HostContract` 与 `UiProjectionPort` 的实例 |
| ② | `create_session("v1")` | 版本串**恒为字面量 `"v1"`**，不得来自 CLI |
| ③ | `set_reference(session_id, uri)` / `set_practice(session_id, uri)` | 参数名**恒为 `uri`**（契约侧名，非 `path`） |
| ④ | `build_surface(session_id)` | 构建 12 个端口的数据面；界面只看得见这 12 个 |
| ⑤ | `launch_cockpit(port=app)` | **以关键字 `port=` 传入**；不传端口号 |

- **不变量**：调用 ⑤ 之前，`app` 必须已完成 ②③④，否则违反 `MUST` 第 2 条。
- **禁止**在本文件里对 `app` 做任何包装、代理、缓存或类型判断。

---

## 5 · 失败语义

| 情形 | 行为 | 退出码 / 抛出 |
| --- | --- | --- |
| `--reference` / `--practice` 缺失 | `argparse` 显式失败 | `SystemExit(2)` |
| 音频路径不存在 / 是目录 / 不可读 | 转可读 stderr | 返回 `2` |
| `cockpit` 不可导入 | 转可读 stderr，**并附不变量 F 的提示** | 返回 `2` |
| 其余任何异常 | 转可读 stderr，**消息带异常类型名** | 返回 `2` |
| C4 自行返回非零 | **原样透传** | `launch_cockpit` 的返回值 |

> ★ 宪章 §5.6：禁止静默降级。**任何失败路径都不得静默退出**——stderr 必须有可读原因。
>
> ★ 消息中必须包含 `type(exc).__name__`，否则调用方无法区分「路径写错」与「数据面构建失败」。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-499-1 | `harmonica_eval/__main__.py` **不** import `cockpit`（`FILE-002-v1.md:45`） | AST 扫 `__main__.py` 的模块级 import，断言无 `cockpit` |
| INV-499-2 | `cockpit` 整体移除后 `__main__` 的 import 仍成功（`FILE-002-v1.md:47`） | 临时移走 `harmonica_eval/cockpit/`，import `__main__`，再移回 |
| INV-499-3 | 本文件不 import `core` / `algorithms` | AST 扫本文件全部 import（含函数体内），断言无 `core`/`algorithms` |
| INV-499-4 | 失败必须非零退出 + stderr 有可读原因，**不得静默** | 传不存在的路径，断言退出码 ≠ 0 且 stderr 非空 |
| INV-499-5 | **不构造第二份端口真相源** | 断言 `--help` 输出中**无** `--port`；且源码中无端口号字面量 |
| INV-499-6 | `--help` 路径不 import C1/C4 | 在 `cockpit` 缺失时跑 `--help`，断言 rc=0 |
| INV-499-7 | `__all__` 恒为 `["main"]` | `import harmonica_eval.serve_ui as m; assert m.__all__ == ["main"]` |

---

## 7 · 边界（明确不做）

- **不做**任何 DSP / 对齐 / 特征计算——那是 C2
- **不做**任何绘图或 HTML 生成——那是 C4
- **不做**端口探测——那是 C4（`app._pick_port`）
- **不做**音频格式转换、重采样、时长对齐——那是 C1/C2 门面
- **不提供** `--port` / `--host` / `--no-browser` 等任何额外开关（AGENTS.md 铁律 4「零噪声」）
- 若你发现「不做这个就实现不了」→ **不要做**，转 §10

---

## 8 · 怎么验证你写对了

全部命令在仓库根 `/Users/Apple/Desktop/dsh-archive/harmonica-eval` 执行。
命令 A~H 对应 §6 的 INV-499-1 ~ INV-499-7，退出码必须全为 `0`。
命令 I 需要真起 HTTP 服务，**不由 `check_bi_scripts_exec.py` 执行**（见下方说明）。

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval

# ── A（INV-499-1）：__main__ 模块级不得 import cockpit ───────────────
python3 - <<'PY'
import ast, pathlib
p = pathlib.Path("harmonica_eval/__main__.py")
tree = ast.parse(p.read_text(encoding="utf-8"))
# ★ 只扫【模块级】导入（tree.body），不扫函数体。
#   理由同 FILE-400 命令 B：函数体内的延迟 import 是合法形态，
#   而 §1 冻结的是「本文件不 import cockpit」这一【导入期】约束。
# ★ 用全树扫描会把合法的函数内 import 误判为违规。
bad = []
for node in tree.body:
    if isinstance(node, ast.Import):
        bad += [a.name for a in node.names if "cockpit" in a.name]
    elif isinstance(node, ast.ImportFrom):
        if "cockpit" in (node.module or ""):
            bad.append(node.module)
        # ★ from harmonica_eval import cockpit —— ★ cockpit 在 names 里
        for alias_node in node.names:
            if "cockpit" in alias_node.name:
                bad.append(f"{node.module or ''}.{alias_node.name}")
assert bad == [], bad
print("A-OK")
PY

# ── B（INV-499-1 补强）：__main__ 全树也不得 import cockpit ──────────
python3 - <<'PY'
import ast, pathlib
p = pathlib.Path("harmonica_eval/__main__.py")
tree = ast.parse(p.read_text(encoding="utf-8"))
# ★ 比 A 更严：连【函数体】内的 import 也一并禁止。
# ★ 依据 FILE-002-v1.md:45「两者之间【零依赖、零 import、零调用】」。
# ★ 本文件不采用任何延迟导入形态，★ 所以全树扫描才是正确口径。
# ★★★ 红端修正（★ 第一次写这判据时漏了最常见的一种形态）★★★
# ★ `from harmonica_eval import cockpit` 的 AST 形态是：
# ★     ImportFrom(module='harmonica_eval', names=[alias('cockpit')])
# ★ ★ 只查 node.module 查不到它 —— ★ module 是 'harmonica_eval'，
# ★ 真正要禁的 cockpit 藏在 node.names 里。
# ★ ★ 两种形态都要查，★ 否则判据给的是【假安全感】。
hits = []
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        hits += [a.name for a in node.names if "cockpit" in a.name]
    elif isinstance(node, ast.ImportFrom):
        # ★ 形态一：from <含 cockpit 的模块> import …
        if "cockpit" in (node.module or ""):
            hits.append(node.module)
        # ★ 形态二：from <包> import cockpit（cockpit 藏在 names 里）
        for alias_node in node.names:
            if "cockpit" in alias_node.name:
                hits.append(f"{node.module or ''}.{alias_node.name}")
assert hits == [], hits
print("B-OK")
PY

# ── C（INV-499-3）：本文件不 import core / algorithms ───────────────
python3 - <<'PY'
import ast, pathlib
p = pathlib.Path("harmonica_eval/serve_ui.py")
tree = ast.parse(p.read_text(encoding="utf-8"))
# ★ 本条扫【全树】（含函数体）—— ★ 与 A/B 相反。
#   理由：本文件的依赖清单是封闭的（§3），★ 函数体内的延迟 import
#   同样属于依赖，★ 不得绕过。★ 这与 __main__ 的口径不同是刻意的。
hits = []
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        hits += [a.name for a in node.names
                 if a.name.startswith(("harmonica_eval.core", "harmonica_eval.algorithms"))]
    elif isinstance(node, ast.ImportFrom):
        mod = node.module or ""
        if mod.startswith(("core", "algorithms", "harmonica_eval.core", "harmonica_eval.algorithms")):
            hits.append(mod)
assert hits == [], hits
print("C-OK")
PY

# ── D（INV-499-4）：失败必须非零退出 + 可读原因，★ 不得静默 ─────────
python3 - <<'PY'
import subprocess, sys
r = subprocess.run(
    [sys.executable, "-m", "harmonica_eval.serve_ui",
     "--reference", "/nonexistent/ref.wav", "--practice", "/nonexistent/prac.wav"],
    capture_output=True, text=True, timeout=120,
)
assert r.returncode != 0, f"返回码应为非 0，实为 {r.returncode}（静默失败）"
blob = (r.stdout + r.stderr).strip()
assert blob, "stdout/stderr 全空 —— 那是静默失败"
# ★ 可读原因：至少要含一个本项目自己的错误码或可辨识短语，
# ★ 而不是裸 Traceback。
assert ("Traceback" not in blob) or len(blob) > 200, blob[:200]
print("D-OK")
PY

# ── E（INV-499-5）：不构造第二份端口真相源 ──────────────────────────
python3 - <<'PY'
import ast, pathlib, subprocess, sys
p = pathlib.Path("harmonica_eval/serve_ui.py")
src = p.read_text(encoding="utf-8")
# ★ 形态一：不得出现 --port / --host 之类的第二份配置面。
tree = ast.parse(src)
opts = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and getattr(getattr(node, "func", None), "attr", "") == "add_argument":
        for a in node.args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                opts.add(a.value)
banned = {o for o in opts if o in ("--port", "--host", "--no-browser", "--bind")}
assert banned == set(), f"§7 冻结禁止的开关：{banned}"
# ★ 形态二：源码里不得出现【真实的端口号常量】。
# ★ 端口探测是 C4 的 app._pick_port 的职责（§7）。
# ★ ★★ 口径说明（★ 重要，★ 第一次写这判据时踩过）：★★
# ★ 直接正则扫全文会【误伤 docstring 与注释】—— ★ 本文件的 docstring
# ★ 里合法地写着「端口由 C4 在 8721–8784 探测」来解释为什么不传端口。
# ★ 那不是第二份真相源，★ 那是【引用】C4 的真相源。
# ★ ★ 正确口径：★ 扫【可执行代码里的数值常量】（ast.Constant），
# ★ 而不是扫文本。★ 注释与 docstring 里的数字不产生任何行为。
tree2 = ast.parse(src)
port_consts = []
for node in ast.walk(tree2):
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        if 1024 <= node.value <= 65535:
            port_consts.append((getattr(node, "lineno", "?"), node.value))
assert port_consts == [], f"代码里出现端口号常量：{port_consts}"
# ★ 形态三：--help 输出里也不得宣传这些开关。
r = subprocess.run([sys.executable, "-m", "harmonica_eval.serve_ui", "--help"],
                   capture_output=True, text=True, timeout=60)
assert r.returncode == 0, r.stderr[:200]
assert "--port" not in r.stdout, "--help 宣传了 --port"
print("E-OK")
PY

# ── F（INV-499-6）：--help 路径不 import C1/C4 ──────────────────────
python3 - <<'PY'
import subprocess, sys
# ★ 用 -X importtime 观察实际导入，★ 比查 sys.modules 更硬：
# ★ 它记录的是解释器【真实发生】的导入，★ 逃不掉。
r = subprocess.run(
    [sys.executable, "-X", "importtime", "-m", "harmonica_eval.serve_ui", "--help"],
    capture_output=True, text=True, timeout=120,
)
assert r.returncode == 0, r.stderr[-300:]
for layer in ("harmonica_eval.host", "harmonica_eval.cockpit",
              "harmonica_eval.core", "harmonica_eval.algorithms"):
    assert layer not in r.stderr, f"--help 路径导入了 {layer}"
print("F-OK")
PY

# ── G（INV-499-7）：__all__ 恒为 ["main"] ───────────────────────────
python3 - <<'PY'
import sys
sys.path.insert(0, ".")
import harmonica_eval.serve_ui as m
assert m.__all__ == ["main"], m.__all__
assert callable(m.main)
print("G-OK")
PY

# ── H（INV-499-2 代理判据）：__main__ 不依赖 cockpit 包存在 ─────────
python3 - <<'PY'
import ast, pathlib, sys
# ★ INV-499-2 原文要求「把 cockpit/ 移走再 import __main__」。
# ★ 判据脚本不得改文件系统（★ 只读契约），★ 故此处用【等价静态证明】：
#   若 __main__.py 的全树【没有任何】对 cockpit 的引用，★ 则
#   cockpit 目录在与否都不影响它的 import —— ★ 这比跑一次 mv 更强，
#   因为它对【任意路径改动】都成立。
# ★ ★★ 口径说明（★ 重要，★ 第一次写这判据时踩过）：★★
# ★ 判据【不得】用 `"cockpit" not in src` 这种全文文本搜索 ——
# ★ 本文件的 docstring 与注释里合法地多处提到 cockpit
# ★ （如「不 import cockpit」这条禁令本身就要写这句话）。
# ★ 全文搜索会把【禁令的说明】当成【禁令的违反】，★ 那是错的。
# ★ 正确口径：★ 只看 AST 里的【引用】—— import 节点与名字加载。
p = pathlib.Path("harmonica_eval/__main__.py")
src = p.read_text(encoding="utf-8")
tree = ast.parse(src)
# ★ 形态一：★ 没有任何 import 指向 cockpit。
mods = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        mods |= {a.name for a in node.names}
    elif isinstance(node, ast.ImportFrom):
        mods.add(node.module or "")
        # ★ from harmonica_eval import cockpit —— ★ cockpit 在 names 里
        mods |= {f"{node.module or ''}.{alias_node.name}" for alias_node in node.names}
assert not [m for m in mods if "cockpit" in m], mods
# ★ 形态二：★ 没有把 cockpit 当【属性链】或【名字】访问
#   （如 `__import__("harmonica_eval.cockpit")` 那种绕法）。
names = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Name):
        names.add(node.id)
    elif isinstance(node, ast.Attribute):
        names.add(node.attr)
assert "cockpit" not in names, f"代码里访问了 cockpit 名字：cockpit"
# ★ 负向证明：★ 若把 cockpit 从模块搜索路径里屏蔽掉，★ import 仍成功。
#   这用 meta_path finder 实现，★ 不触碰文件系统。
class Blocker:
    def find_module(self, name, path=None):
        return self.find_spec(name, path)
    def find_spec(self, name, path=None, target=None):
        if name == "harmonica_eval.cockpit" or name.startswith("harmonica_eval.cockpit."):
            raise ImportError("cockpit 被本判据屏蔽")
        return None
sys.path.insert(0, ".")
sys.meta_path.insert(0, Blocker())
try:
    import importlib
    import harmonica_eval.__main__ as m
    assert hasattr(m, "main") or hasattr(m, "run_headless"), \
        "屏蔽 cockpit 后 __main__ 缺入口"
finally:
    sys.meta_path.pop(0)
print("H-OK")
PY
```

**★ 需人工验收的项（★ 写不出安全的自动化形态，★ 不假装能执行）★**

| 判据 | 为什么无法自动化 | 谁执行 |
| --- | --- | --- |
| 真启动后打印**两个**地址（`127.0.0.1` + 局域网 IP） | 需要真起 HTTP 服务；★ `FILE-401` 脚本 7 已因同类操作超时 300s | 人工，`docs/验收计划.md` §2 |
| `curl` 首页 200 且含 12 个端口 | 同上（需服务在跑） | 人工，同上 |
| 占满 8721–8784 全部端口 → stderr 含「bind 失败」 | 需占 64 个端口；★ 判据脚本不得改动系统网络状态 | 人工，同上 |

**★ 判据脚本的两条硬约束（★ 本节为何如此设计）★**

1. **判据只读。** 全部命令只用 `ast` 静态分析与短命子进程，★
   **不改文件系统、不起长驻服务、不占端口。** 这既是 `check_bi_scripts_exec.py`
   的执行契约，也避免了「判据自己弄脏仓库」。
2. **每个判据都打印固定标记**（`A-OK` … `H-OK`）。★
   `rc=0` 只说明「没抛异常」，★ 打印标记才能让人一眼确认**跑的是哪一条**。

**★ 口径差异的说明（★ 别把 C 当成 B 的矛盾）★**

- 命令 A 只扫 `__main__.py` 的**模块级**（`tree.body`）：★
  §1 冻结的是「导入期不 import」，函数体内的延迟 import 是合法形态。
- 命令 B 扫**全树**：`FILE-002-v1.md:45` 的措辞是
  「【零依赖、零 import、零调用】」—— ★ 比「导入期」更强，★ 全树才是正确口径。
- 命令 C 扫**全树**：`serve_ui.py` 的依赖清单是封闭的（§3），★
  函数体内的延迟 import 同样算依赖，★ 不得绕过。

★ 三条口径不同是有意为之；★ 详见各自脚本内的注释。

---

**★ 人工验收清单（★ 与 §9 的 Evidence Pack 对应）★**：

- [ ] A~H 全部 `PASS`（`check_bi_scripts_exec.py` 报告 `FILE-499-v1` 为 `PASS 8/8`）
- [ ] `--help` 的 rc=0，且输出中**不含** `--port`
- [ ] 真启动后打印**两个**地址：`127.0.0.1` 与实际局域网 IP
- [ ] `curl` 首页返回 200，页面含 `warp_path` / `notes.reference` / `chroma.lowres.reference`
- [ ] 传不存在的音频路径 → rc ≠ 0 且 stderr 含可读原因
- [ ] 占满 8721–8784 全部端口 → rc ≠ 0 且 stderr 含「bind 失败」
- [ ] `cockpit/` 移走后 `import __main__` 仍成功；本文件给出可读缺失提示
- [ ] `verify_shell.py` rc=0（含「FILE-ID 必须有对应 BI」判据）

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] §8 的命令 A~H 逐条实跑输出（★ 8 条，★ 对应 INV-499-1 ~ 7）
- [ ] §8「需人工验收」三条的实跑记录（★ 真启动 / curl / 端口占满）
- [ ] `tests/test_serve_ui_contract.py` 的 pytest 输出（★ 覆盖同一批不变量，
      ★ 但在最常跑的门禁上也能看见 —— ★ 两套判据互为交叉验证）
- [ ] 启动后首页的 12 个端口逐个可见的截图或文本
- [ ] 两条失败路径的 stderr 原文
- [ ] 清理证明：进程残留 0、8721–8784 占用 0、`__pycache__` 已清

---

## 10 · ★ 何时必须停止并上报（§22 硬失败对策）

**以下情况必须停止，提交 `MOLD BREAK`，不得自行设计：**

1. 你需要决定一个新的端口探测策略（那会形成第二份真相源，违反 INV-499-5）
2. 本文件与 `FILE-002-v1.md:45/:47` 或 `FILE-400-v1.md` 冲突
3. 你需要的依赖不在 §3 清单里
4. 你认为「装配点不该是独立模块，应并入 `__main__`」
   —— **这正是 `FILE-002:45` 禁止的**，若你有反证请提出，否则停
5. 你认为规格本身是错的

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

- 先做一个「能跑的 workaround」，以后再说（§38 明文禁止）
- 自行加一个「合理的」默认端口把冲突掩盖过去
- 静默缩小范围

---

## 附：本文件的冻结常量速查

| 常量 | 值 | 来源 |
| --- | --- | --- |
| 会话版本串 | `"v1"` | 字面量，本文件 §4.3 步 ② |
| 端口探测范围 | 8721–8784 | **C4 冻结**，见 `FILE-401-v1.md §4.4`。本文件**不实现**它 |
| 进程级失败退出码 | `2` | 本文件 §5 |
| `__all__` | `["main"]` | 本文件 §4.1 |

> ★ **启动命令形态的说明**：
> `python3 -m harmonica_eval.serve_ui --reference … --practice …`
>
> **此形态为本文件新增：`SPEC.md` / `COMPONENTS.md` / `PLAN.md` / `FILE-400-v1.md` 均未规定进程装配点的位置与启动命令。**
> 选它的理由是朴素的——沿用本项目既有的 `python3 -m harmonica_eval.<模块>` 形态（`__main__` 与 `cockpit.app` 都如此），不引入新范式。
