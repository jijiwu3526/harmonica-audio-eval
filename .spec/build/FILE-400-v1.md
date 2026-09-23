# FILE-400 — `harmonica_eval/cockpit/__init__.py`

> BUILD-INSTRUCTION v1 · 目标文件：`harmonica_eval/cockpit/__init__.py`
> 生成依据：`SPEC.md@v2.1 §1`（负责人裁定例外）· `COMPONENTS.md@v2 §3 COMP-C4` · `PLAN.md@v2 §四/§五` · `.spec/build/_TEMPLATE.md@v1`
> 铭牌来源：目标文件自身的 `FILE-ID / COMPONENT / ROLE / INTENT / MUST / MUST NOT / INPUT / OUTPUT` 头块（64 行，已冻结）
> ★ 本文件是**冻结产物**（宪章 §30）。实现者**不得**修改本文件。

---

## 1 · 你是谁，你在哪

| 项 | 值 |
| --- | --- |
| 文件 ID | FILE-400 |
| 所属组件 | COMP-C4（cockpit，开发者界面） |
| 层级 | L3（symbol / implementation） |
| 上游 | 包外装配方（进程装配点）。它构造一个 C1 提供的 `UiProjectionPort` 实例，并调用 `launch_cockpit(port)` |
| 下游 | ①`harmonica_eval.contract`（仅取类型 `UiProjectionPort`，导入期）；②`harmonica_eval.cockpit.app`（仅取常量与绘图函数，调用期延迟 import） |
| 同层邻居 | `harmonica_eval/cockpit/` 目录内的其余模块（`app` 以及该组件其它文件）。本文件**在包导入期不 import 其中任何一个** |

**你的权限**：只实现本文件（就地替换第 61 行的 `raise NotImplementedError`，并保持文件头块与 `__all__` 的语义不变）。不得修改任何其他文件，不得修改契约，不得新增端口，不得新增依赖，不得新增公开符号。

---

## 2 · 这个文件为什么存在

追溯链：`SPEC.md@v2.1 §1` 的负责人裁定例外 → 不变量 F「界面系统必须能被整体删除而不影响内核」→ `COMPONENTS.md@v2 §3 COMP-C4` → 本文件。

**删掉它会坏掉什么**（逐条可验）：

1. **C4 的边界从「一件事」退化为「一组模块」。** 没有本文件，装配方必须知道 C4 内部有几个模块、哪个模块里的哪个函数才是入口，于是 C4 的对外面 = 目录内全部模块的并集。删除 C4 时，装配点需要改动的行数从 1 行变成 N 行，不变量 F 失去「一个函数即边界」这一机械锚点。
2. **导入期耦合立刻出现。** 若入口被搬进任一子模块（例如 `app.py`），则任何 `import harmonica_eval.cockpit.app` 都会连带拉入该子模块的全部 import 图；界面代码与内核代码的 import 顺序耦合、循环 import 由此产生，`MUST NOT` 第 2 条（导入期不 import 子模块）无法成立。
3. **零耦合不变量失去唯一可检查的落点。** 本文件是全仓库唯一一处「C4 与内核接触面」的声明处。删掉它，「C4 不 import core / algorithms / host」这句话就分散到目录内每个文件，`§8` 的机械判据（导入 `harmonica_eval.cockpit` 后 `sys.modules` 不含内核包）无处挂载。
4. **端口注入的契约无处声明。** 入口签名 `launch_cockpit(port: UiProjectionPort) -> int` 是「C4 不构造端口、端口由调用方注入」这句话的唯一机械表达；删掉它，C4 就有机会自行构造端口，从而反向依赖 C1。

本文件**不承担**任何计算、任何验收、任何持久化职责；它只声明并实现一个入口点。

---

## 3 · 你能用的东西（依赖清单，封闭）

**允许 import（穷举，清单外一律禁止）**：

- Python 标准库，仅此 2 项：
  - `__future__` —— 仅 `annotations`
  - `typing` —— 仅当需要类型标注辅助名时使用；**本文件实现不需要它**（签名所需类型来自 `contract`）
- 第三方：**空集**（本文件禁止任何第三方 import）
- 本包内，仅此 2 个精确模块：
  - `harmonica_eval.contract` —— 仅允许符号 `UiProjectionPort`（导入期，模块顶层）
  - `harmonica_eval.cockpit.app` —— 仅允许符号 `LOCAL_BIND_HOST`、`LOCAL_BIND_PORT`、`EXIT_OK`、`EXIT_STARTUP_FAILED`、`EXIT_SIGTERM`、`build_plots`（**只能在 `launch_cockpit` 函数体内延迟 import**）

**禁止 import（穷举）**：

- `harmonica_eval.core`、`harmonica_eval.algorithms`、`harmonica_eval.host`（任何形式：顶层、延迟、`importlib`、`__import__`、`TYPE_CHECKING` 分支）
- `harmonica_eval.cockpit` 的任何子模块在**包导入期**被 import（含 `.app`、含 `from . import app`）
- `harmonica_eval` 下除本 §3 清单所列模块以外的任何模块
- 任何第三方包（`numpy`、`scipy`、`soundfile`、`fastapi`、`flask`、`uvicorn`、`websockets`、`matplotlib`、`pytest` 全部在禁止之列）
- 任何不在上述清单里的东西

---

## 4 · 你要实现什么（行为规格）

本文件的公开面**恰好两项**：模块属性 `__all__` 与函数 `launch_cockpit`。此外无第三个公开符号。

### 4.1 模块级

- `__all__` 的值**恒等于** `["launch_cockpit"]`（字面量列表，单一元素，顺序固定）。
- 模块级语句仅允许：docstring 头块、`from __future__ import annotations`、`from ..contract import UiProjectionPort`、`def launch_cockpit`、`__all__ = [...]`。模块级不得出现任何其他赋值、任何计算、任何 I/O、任何子模块 import。

### 4.2 `launch_cockpit(port: UiProjectionPort) -> int`

- **输入**：`port` —— 由包外装配方注入的 `UiProjectionPort` 实例。
  - `port is None` → 显式失败，见 §5。
  - 其余取值：只做**结构性检查**——`port` 必须具有可调用的属性 `snapshot` 与 `submit`；二者任一缺失或不可调用 → 显式失败，见 §5。
  - **禁止**对 `port` 做具体类检查（不得 `isinstance(port, ...)` 指向 C1 的任何具体类型），因为那要求 import C1。
  - **禁止**在函数内构造、包装、缓存、复制 `port`。
- **输出**：`int` 退出码。取值域**恰好**为下表的三个值，且**只允许**以常量名引用，不得在源码中写字面量数字：

| 结果 | 返回表达式 | 冻结值 | 触发条件 |
| --- | --- | --- | --- |
| 正常关闭 | `app.EXIT_OK` | `0` | 用户关闭窗口、Ctrl-C（SIGINT）、界面正常退出 |
| 启动失败 | `app.EXIT_STARTUP_FAILED` | `2` | 端口被占用、绑定失败、非本机绑定被拒 |
| 被强制终止 | `app.EXIT_SIGTERM` | `143` | 进程收到 SIGTERM |

- **算法口径**（写到「另一个实现者能复现同一数字」的程度）：
  1. 校验 `port`（§5 规则）。校验失败即返回前抛异常，不启动任何服务。
  2. 延迟 import：`from . import app`。取 `app.LOCAL_BIND_HOST`、`app.LOCAL_BIND_PORT`、`app.build_plots` 及其余三个退出码常量。
  3. 绑定的地址**恒为** `app.LOCAL_BIND_HOST`，冻结值 `"127.0.0.1"`；端口**恒为** `app.LOCAL_BIND_PORT`，冻结值 `8770`。绑定失败**不得**重试、**不得**改用其他端口、**不得**退回 `"0.0.0.0"`。
  4. 界面刷新周期**恒为** `app.POLL_INTERVAL_MS`，冻结值 `250`（单位：毫秒）。刷新动作 = 调用 `port.snapshot()` 一次，把返回的投影交给 `app.build_plots` 渲染。
  5. **并发上限**：任一时刻未完成的 `port.snapshot()` 调用数 ≤ `1`。慢快照不得导致调用堆叠。
  6. **写路径**：界面产生的每个操作经 `port.submit(cmd)` 发出，`cmd` 的 `kind` **必须**是 `harmonica_eval.contract.UiCommandKind` 的成员；该枚举成员数**冻结为 6**。不得新增、改名、绕过或子类化该枚举。
  7. 本函数**阻塞**：从启动界面到界面关闭期间不返回。进程模型（线程 / 子进程）由包外装配方决定，本函数不创建进程、不创建线程池、不管理线程生命周期。
  8. 正常关闭路径必须关闭监听套接字后再返回。
  9. **单位与容差**：本文件不含任何浮点运算，故无浮点容差常量；任何浮点比较不得出现在本文件。唯一带单位的常量是 `POLL_INTERVAL_MS`（毫秒）。
- **边界**：`port is None` → §5；`port` 缺属性 → §5；`app` 侧常量缺失或取值不等于本 §4.2 表 → §10 停止上报；`snapshot()` 返回空投影 → 按原样交给 `build_plots`，**不得**替换为默认视图；`snapshot()` 抛异常 → §5；`submit()` 抛异常 → §5；同一进程内第二次调用 `launch_cockpit` → 允许，且两次调用之间不得共享任何状态（本文件无模块级可变状态）。
- **不变量（返回后必须为真）**：监听套接字已关闭；模块级名字集合与调用前完全一致；`port` 未被本文件替换或包装。

---

## 5 · 失败语义

| 情形 | 行为 | 抛出/返回 |
| --- | --- | --- |
| `port is None` | 显式失败，立即抛异常，不启动服务 | `TypeError` |
| `port` 缺 `snapshot` 或 `submit`，或二者不可调用 | 显式失败，立即抛异常，不启动服务 | `TypeError` |
| `port.snapshot()` 抛异常 | **不吞异常、不返回默认值、不显示空视图掩盖**；异常原样向上传播，终止刷新循环 | 原异常类型向上传播 |
| `port.submit()` 抛异常 | **不吞异常、不重试、不静默丢弃该命令**；异常原样向上传播 | 原异常类型向上传播 |
| 监听端口被占用 | 不重试、不改端口 | 返回 `app.EXIT_STARTUP_FAILED`（`2`），且向 stderr 写恰好一行失败原因 |
| 绑定地址非 `127.0.0.1`（例如被改成 `0.0.0.0`） | 拒绝启动 | 返回 `app.EXIT_STARTUP_FAILED`（`2`） |
| 用户关闭窗口 / SIGINT | 视为正常关闭，关闭套接字后返回 | 返回 `app.EXIT_OK`（`0`） |
| 进程收到 SIGTERM | 关闭套接字后返回 | 返回 `app.EXIT_SIGTERM`（`143`） |
| `app` 侧任一冻结常量缺失或取值不符 §4.2 | **不得**就地兜底；转 §10 停止上报 | 不适用（停止上报） |

★ 宪章 §5.6：禁止静默降级。任何「算不出来就返回默认值」「快照失败就给空视图」「提交失败就丢掉」的实现一律判失败。本文件**不存在**任何默认值回退分支。

---

## 6 · 必须满足的不变量

| ID | 不变量 | 怎么验 |
| --- | --- | --- |
| INV-400-1 | `__all__ == ["launch_cockpit"]`，且模块公开符号**恰好**为它一个 | `python -c` 断言 `c.__all__ == ["launch_cockpit"]` 且 `[n for n in vars(c) if not n.startswith("_")]` 去掉 `annotations` 后等于 `["UiProjectionPort", "launch_cockpit"]` |
| INV-400-2 | 签名恒为 `(port) -> int`，且为同步函数 | `inspect.signature` 参数名列表 `== ["port"]`；`inspect.iscoroutinefunction(...) is False` |
| INV-400-3 | **C4 与内核零耦合**：import `harmonica_eval.cockpit` 之后，`sys.modules` 中不出现 `harmonica_eval.core` / `harmonica_eval.algorithms` / `harmonica_eval.host` 及其任何子模块 | §8 命令 A 的机械断言 |
| INV-400-4 | **删掉 C4 内核仍须跑通**：整个 `harmonica_eval/cockpit/` 目录被移走后，内核（core / algorithms / host）测试全绿 | §8 命令 C |
| INV-400-5 | 导入期零子模块：import 包之后 `sys.modules` 不含 `harmonica_eval.cockpit.app` | §8 命令 A |
| INV-400-6 | 端口注入：源码中不存在 `UiProjectionPort(` 的实例化调用，不存在对 C1 具体类型的 `isinstance` 检查 | §8 命令 B 的 AST 断言 |
| INV-400-7 | 只监听本机：`app.LOCAL_BIND_HOST == "127.0.0.1"`，且 cockpit 包内源码不出现字符串 `"0.0.0.0"` 与 `"::"` | §8 命令 D |
| INV-400-8 | 无持久状态：模块级名字集合固定（docstring / `annotations` / `UiProjectionPort` / `launch_cockpit` / `__all__`），无模块级可变容器、无文件写入、无缓存 | §8 命令 B 的 AST 断言（模块级无 `Assign` 目标为 `list/dict/set` 字面量，`__all__` 除外） |
| INV-400-9 | 不参与计算路径：cockpit 包内不 import `numpy` / `scipy` / `soundfile`，不调用任何指标函数 | §8 命令 E |
| INV-400-10 | 不承担验收职责：cockpit 包内不 import `pytest`，不定义 `test_*` 函数 | §8 命令 E |
| INV-400-11 | 退出码三值封闭：返回表达式只引用常量名，源码中不出现 `0` / `2` / `143` 作为返回值 | §8 命令 B 的 AST 断言 |
| INV-400-12 | 刷新周期与绑定常量唯一来源：`250`、`8770`、`"127.0.0.1"` 只出现在 `app.py`；本文件只引用常量名 | §8 命令 B 的 AST 断言（本文件常量池中不含这三个字面量） |

---

## 7 · 边界（明确不做）

- 不在本文件实现 HTTP / WebSocket 服务、静态资源、页面渲染 —— 这些属于 COMP-C4 的其它文件，由各自的 Build Instruction 冻结。
- 不在本文件实现任何数值计算、指标、单位换算、阈值判定 —— 一切显示内容来自 `port.snapshot()`，一切操作经 `port.submit()`。
- 不在本文件定义退出码、绑定地址、端口、刷新周期的**数值**；这三个数值的唯一来源是 `app.py`。本文件只引用常量名。
- 不新增 CLI 参数、不新增环境变量、不新增配置文件、不新增第二个入口点。
- 不做认证、授权、多用户、会话持久化、录制回放、日志文件。
- 不监听公网、不做端口自动探测、不做端口重试。
- 不修改 `harmonica_eval/contract.py`、不新增 `UiCommandKind` 成员、不新增错误码。
- 不写测试（宪章 §36：验证是角色，不是产品件）。
- 若你发现「不做其中某一条就实现不了」 → **不要做**，转 §10。

**★ C4 与内核零耦合（机械分析证实）—— 本文件的中心约束：**

C4 不参与任何计算路径，只消费 C1 计算完成后给出的结果投影。因此：本文件与 `core` / `algorithms` / `host` 的耦合度**恒为 0**，不是「弱耦合」，而是**不存在 import 边**。这条约束的机械表达就是 INV-400-3 与 INV-400-4 两条，其中 INV-400-4 是本项目的锚点不变量：

> **删掉整个 C4，内核仍须跑通。**

任何使 INV-400-4 失败的实现，无论功能多完整，一律判失败。

---

## 8 · 怎么验证你写对了

全部命令在仓库根 `/Users/Apple/Desktop/dsh-archive/harmonica-eval` 执行。每条命令的退出码必须为 `0`。

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval

# ── 命令 A：导入期纯净性 + 零内核耦合 + 公开面 ──────────────────────
python - <<'PY'
import sys, inspect
sys.path.insert(0, ".")
import harmonica_eval.cockpit as c
assert c.__all__ == ["launch_cockpit"], c.__all__
assert callable(c.launch_cockpit)
assert list(inspect.signature(c.launch_cockpit).parameters) == ["port"]
assert inspect.iscoroutinefunction(c.launch_cockpit) is False
public = [n for n in vars(c) if not n.startswith("_")]
assert public == ["UiProjectionPort", "launch_cockpit"], public
forbidden = [m for m in sys.modules
             if m.startswith(("harmonica_eval.core", "harmonica_eval.algorithms", "harmonica_eval.host"))]
assert forbidden == [], forbidden
assert "harmonica_eval.cockpit.app" not in sys.modules
print("A-OK")
PY

# ── 命令 B：AST 级静态禁令（字面量 / 实例化 / 模块级状态） ──────────
python - <<'PY'
import ast, pathlib
p = pathlib.Path("harmonica_eval/cockpit/__init__.py")
tree = ast.parse(p.read_text(encoding="utf-8"))
src = p.read_text(encoding="utf-8")
mods = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        mods.update(a.name for a in node.names)
    elif isinstance(node, ast.ImportFrom):
        mods.add(("." * node.level) + (node.module or ""))
assert mods <= {"__future__", "..contract", ".app"}, mods
assert not [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == "UiProjectionPort"]
for lit in ("0", "2", "143", "250", "8770", "127.0.0.1", "0.0.0.0"):
    assert f'"{lit}"' not in src and f"'{lit}'" not in src, lit
for node in tree.body:
    if isinstance(node, ast.Assign):
        assert [t.id for t in node.targets] == ["__all__"]
assert "return 0" not in src and "return 2" not in src and "return 143" not in src
print("B-OK")
PY

# ── 命令 C：★ 删掉 C4，内核仍须跑通（锚点不变量） ───────────────────
set -euo pipefail
STASH="$(mktemp -d)"
trap 'mv "$STASH/cockpit" harmonica_eval/cockpit' EXIT
KERNEL=""
for d in harmonica_eval/core harmonica_eval/algorithms harmonica_eval/host; do
  [ -d "$d" ] && KERNEL="$KERNEL $d"
done
[ -n "$KERNEL" ] || { echo "MOLD BREAK: 内核包路径未冻结，无法执行 INV-400-4"; exit 1; }
mv harmonica_eval/cockpit "$STASH/cockpit"
python -m pytest $KERNEL -q
mv "$STASH/cockpit" harmonica_eval/cockpit
trap - EXIT
test -d harmonica_eval/cockpit

# ── 命令 D：app 侧冻结常量（数值唯一来源） ─────────────────────────
python - <<'PY'
import sys; sys.path.insert(0, ".")
from harmonica_eval.cockpit import app
assert app.LOCAL_BIND_HOST == "127.0.0.1", app.LOCAL_BIND_HOST
assert app.LOCAL_BIND_PORT == 8770, app.LOCAL_BIND_PORT
assert app.POLL_INTERVAL_MS == 250, app.POLL_INTERVAL_MS
assert app.EXIT_OK == 0 and app.EXIT_STARTUP_FAILED == 2 and app.EXIT_SIGTERM == 143
from harmonica_eval.contract import UiCommandKind
assert len(list(UiCommandKind)) == 6, len(list(UiCommandKind))
print("D-OK")
PY

# ── 命令 E：无计算路径 / 无验收职责 / 无公网绑定 ────────────────────
! grep -rnE "^\s*(import|from)\s+(numpy|scipy|soundfile|pytest)\b" harmonica_eval/cockpit/
! grep -rnE "0\.0\.0\.0|def test_" harmonica_eval/cockpit/
grep -rn "launch_cockpit" --include=*.py . | grep -v "^./harmonica_eval/cockpit/"

# ── 命令 F：内核全绿 + C4 自身可导入 ───────────────────────────────
python -c "import sys; sys.path.insert(0,'.'); from harmonica_eval.cockpit import launch_cockpit; print(callable(launch_cockpit))"
python -m pytest -q
```

**验收判据**（机械判定，非「看起来对」）：

- [ ] 命令 A 输出 `A-OK`，退出码 `0`；其中 `forbidden == []` 与 `"harmonica_eval.cockpit.app" not in sys.modules` 两条断言通过。
- [ ] 命令 B 输出 `B-OK`，退出码 `0`；即：AST 的 import 集合恰为 `{"__future__", "..contract", ".app"}`，源码常量池不含 `0/2/143/250/8770/127.0.0.1/0.0.0.0` 任一者。
- [ ] 命令 C 退出码 `0`：`cockpit/` 被移走期间内核 pytest 全绿（**INV-400-4**），且恢复后 `test -d harmonica_eval/cockpit` 为真。
- [ ] 命令 D 输出 `D-OK`，退出码 `0`：三个退出码、绑定地址、端口、刷新周期、`UiCommandKind` 成员数 6 全部相符。
- [ ] 命令 E 退出码 `0`：cockpit 包内无 `numpy/scipy/soundfile/pytest` import、无 `0.0.0.0`、无 `def test_`；且 `launch_cockpit` 在 cockpit 包外只被装配方引用，无其它内核模块引用它。
- [ ] 命令 F 退出码 `0`：`callable(launch_cockpit)` 打印 `True`，全仓 pytest 全绿。
- [ ] 运行期抽查：以 `port=None` 调用 `launch_cockpit` 抛 `TypeError`，且未建立任何监听套接字（`launch_cockpit(None)` 一行断言即可）。

---

## 9 · 完成后提交什么证据（§36 Evidence Pack）

- [ ] 目标文件：`harmonica_eval/cockpit/__init__.py`（仅替换 SHELL 实现，头块与 `__all__` 语义不变）
- [ ] `data/out/FILE-400/asserts-A.txt` —— 命令 A 的完整 stdout/stderr 与退出码
- [ ] `data/out/FILE-400/ast-scan-B.txt` —— 命令 B 的完整输出与退出码
- [ ] `data/out/FILE-400/kernel-without-c4.txt` —— 命令 C 的 pytest 输出（含移走/恢复两行时间戳），证明 **INV-400-4**
- [ ] `data/out/FILE-400/constants-D.txt` —— 命令 D 的完整输出与退出码
- [ ] `data/out/FILE-400/import-graph-E.txt` —— 命令 E 的输出，含 cockpit 包外对 `launch_cockpit` 的全部引用行
- [ ] `data/out/FILE-400/pytest-full-F.txt` —— 命令 F 的全仓 pytest 输出
- [ ] `data/out/FILE-400/typeerror-none.txt` —— `launch_cockpit(None)` 的异常类型与 traceback
- [ ] `git diff --stat` 输出 —— 证明改动**只**落在 `harmonica_eval/cockpit/__init__.py` 一个文件
- [ ] 数值证据说明：本文件零浮点运算，故**不**产出黄金向量对比；产出的是 A–F 六条命令的退出码集合，全部为 `0`

---

## 10 · ★ 何时必须停止并上报（§22 硬失败对策）

**以下情况必须停止，提交 `MOLD BREAK`，不得自行设计：**

1. 你发现本文件**需要做上层设计**才能实现（需要决定一个新阈值、新口径、新端口、新错误码、新公开符号）。
2. 本文件与任何上游工件**冲突**（`SPEC.md@v2.1` / `COMPONENTS.md@v2` / `PLAN.md@v2` / 目标文件头块铭牌）。
3. 你需要的依赖**不在 §3 清单里**（例如实现需要 `fastapi`、`websockets`、`numpy`、`typing.Protocol` 之外的任何第三方件）。
4. §4 的行为规格**不足以确定唯一实现**。
5. 你认为 §4 的规格本身**是错的**。

**本文件专属的停止触发条件（任一命中即停）：**

6. `app.py` 中不存在 `LOCAL_BIND_HOST` / `LOCAL_BIND_PORT` / `POLL_INTERVAL_MS` / `EXIT_OK` / `EXIT_STARTUP_FAILED` / `EXIT_SIGTERM`，或取值不等于 `"127.0.0.1"` / `8770` / `250` / `0` / `2` / `143`。
7. `UiCommandKind` 的成员数不等于 `6`，或界面需要第 7 个成员。
8. 实现要求 C4 构造、缓存或包装 `UiProjectionPort`，或要求 import C1 的任何具体类型。
9. 实现要求把 `launch_cockpit` 之外的第二项放进 `__all__`。
10. 实现要求把绑定地址改为非 `127.0.0.1`，或要求端口重试 / 自动选端口。
11. 内核包路径（`harmonica_eval/core`、`harmonica_eval/algorithms`、`harmonica_eval/host`）全部不存在，导致 INV-400-4 无法机械验证。

**上报格式一（口径 / 契约冲突，宪章 §37 Gate Challenge）：**

```
GATE CHALLENGE
- 相关 Requirement：
- 相关 Build Instruction 章节：
- 实际需要 vs 规格给出：
- 为什么冲突：
- 复现证据：
- 建议的上游处理位置：
```

**上报格式二（规格不足以唯一实现，§22 MOLD BREAK）：**

```
MOLD BREAK
- 阻塞点：<§4 哪一条无法唯一确定>
- 我尝试过的解读：<列出 2 条以上互斥解读>
- 为什么不能自行选择：<该决定属于设计层，不属于实现层>
- 复现证据：<命令 + 输出>
- 需要的上游裁定：<具体要冻结哪个值/哪个口径>
- 涉及文件：.spec/build/FILE-400-v1.md
```

**绝对禁止**：

- 先做一个「能跑的 workaround」，以后再说（§38 明文禁止）。
- 自行在代码里加一个「合理的」默认值（默认端口、默认退出码、默认空视图）把冲突掩盖过去。
- 静默缩小范围（「这个分支我先不实现」）。
- 为了让 `§8` 的命令通过而修改 `app.py` / `contract.py` / 测试文件。

---

## 附：本文件的冻结常量速查

| 常量 | 值 | 来源 |
| --- | --- | --- |
| `app.LOCAL_BIND_HOST` | `"127.0.0.1"` | 目标文件铭牌 MUST 第 3 条 + `COMPONENTS.md@v2 §3 COMP-C4` |
| `app.LOCAL_BIND_PORT` | `8770` | 本文件 §4.2 冻结（`app.py` 为唯一数值来源） |
| `app.POLL_INTERVAL_MS` | `250`（毫秒） | 本文件 §4.2 冻结（`app.py` 为唯一数值来源） |
| `app.EXIT_OK` | `0` | 目标文件 docstring「取值由 app 侧常量冻结」+ 本文件 §4.2 |
| `app.EXIT_STARTUP_FAILED` | `2` | 同上 |
| `app.EXIT_SIGTERM` | `143` | 同上 |
| `UiCommandKind` 成员数 | `6` | 目标文件 docstring「仅限 UiCommandKind 的 6 个成员」 |
| `__all__` | `["launch_cockpit"]` | 目标文件第 64 行（已冻结） |
| 浮点容差 | 不存在 | 本文件零浮点运算 |
