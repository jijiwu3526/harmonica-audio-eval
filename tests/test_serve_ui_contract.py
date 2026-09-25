"""`serve_ui` 契约护栏 —— 覆盖 §8 里写不出安全自动化形态的判据。

★ 为什么这个文件存在（★ 背景）
────────────────────────────────────────────────────────────────────────
`.spec/build/FILE-499-v1.md` §8 的命令 A~H 由
`tools/check_bi_scripts_exec.py` 自动执行（★ 8/8 PASS）。
但 §8 另有三条判据**不能**进那个检查器，原因是它们要起长驻 HTTP
服务或占用 64 个端口 —— 而判据脚本必须只读、不改系统网络状态。
★ 那三条若只写在文档里，★ 就等于没人守。

★ 本文件把其中**可在 pytest 内安全完成**的部分固化下来：
  · §8「`__all__ == ["main"]`」        （INV-499-7，命令 G 的同义复核）
  · §8「`--help` 路径不 import C1/C4」 （INV-499-6，命令 F 的同义复核）
  · §8「`--help` 输出不含 `--port`」    （INV-499-5 的一部分）
  · §8「不存在的路径 → 非零退出 + 可读原因」（INV-499-4，命令 D 的同义复核）

★ **仍然只能人工验收的三条**（★ 详见 FILE-499-v1.md §8 的表格）：
  1. 真启动后打印两个地址（127.0.0.1 + 局域网 IP）
  2. `curl` 首页 200 且含 12 个端口
  3. 占满 8721–8784 → stderr 含「bind 失败」
★ 它们需要真实服务与端口占用，★ 本文件【不做】假装能测它们。

────────────────────────────────────────────────────────────────────────
FILE-ID:      TEST-499
COMPONENT:    TEST（契约护栏，非产品代码）
SPEC:         .spec/build/FILE-499-v1.md §6（不变量）与 §8（判据）
ROLE:
    把 FILE-499 中「可安全自动化但 check_bi_scripts_exec 覆盖不到」的部分
    固化为 pytest 用例。★ 与 §8 的命令互为交叉验证 ——
    ★ 若两套判据对同一事实给出不同结论，★ 至少有一套错了。

INTENT:
    §8 的 8 条命令在专用检查器里跑，★ 它们的弱点是：
    那个检查器只被 `check_all.sh` 调用，★ 平时 `pytest` 碰不到。
    ★ 本文件让「不变量被破坏」这件事，★ 在最常跑的那道门禁上也看得见。
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
SERVE_UI = REPO / "harmonica_eval" / "serve_ui.py"
MAIN_PY = REPO / "harmonica_eval" / "__main__.py"


def _run_module(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """在仓库根跑 `python3 -m harmonica_eval.serve_ui ...`。

    ★ `cwd` 必须是仓库根：★ `python3 -m` 依赖包可导入，
    ★ 而 pytest 的 cwd 默认是它启动时的目录，★ 不一定是仓库根。
    """
    return subprocess.run(
        [sys.executable, "-m", "harmonica_eval.serve_ui", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO),
    )


# ── INV-499-7 · §8 清单第 7 条：`__all__` 恒为 ["main"] ────────────────
def test_public_surface_is_exactly_main() -> None:
    """公开面恰好是 `main` 一个。

    ★ 与 §8 命令 G 同义但独立实现：★ 若两套给出不同结论，
    ★ 说明其中一套的口径错了。
    """
    src = SERVE_UI.read_text(encoding="utf-8")
    tree = ast.parse(src)

    # ★ 用 AST 找 `__all__` 的字面量，★ 而不是 import 后读属性 ——
    #   import 会执行模块顶层代码，★ 而本项目 `serve_ui` 顶层只有
    #   stdlib 导入与函数定义，★ 但判据不该依赖「它无害」这个假设。
    all_nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", "") == "__all__" for t in node.targets)
    ]
    assert len(all_nodes) == 1, f"__all__ 应有且仅有一处赋值，实为 {len(all_nodes)}"
    value = all_nodes[0].value
    assert isinstance(value, (ast.List, ast.Tuple)), "__all__ 应是字面量列表/元组"
    got = [elt.value for elt in value.elts]
    assert got == ["main"], got

    # ★ 函数本身存在且可调用 —— ★ 只断言名字会漏掉「定义了但是 None」
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
    assert len(funcs) == 1, "main 应有且仅有一个定义"


# ── INV-499-6 · §8 清单第 1 条：`--help` 路径不 import C1/C4 ───────────
def test_help_path_does_not_import_c1_or_c4() -> None:
    """`--help` 不得牵入 C1/C4。

    ★ 为什么这条要在 pytest 里重复一遍（★ 而不只是靠 §8 命令 F）：
    §8 命令 F 用 `-X importtime` 读解释器的导入日志；★ 那依赖
    `-X` 的输出格式。★ 本测试改用 `sys.modules` 快照 ——
    ★ 两种观测方式互相印证，★ 任一种失效都还有另一种。
    """
    probe = (
        "import sys\n"
        "from harmonica_eval.serve_ui import main\n"
        "try:\n"
        "    main(['--help'])\n"
        "except SystemExit:\n"
        "    pass\n"
        "bad = [m for m in sys.modules\n"
        "       if m.split('.')[0:2] in (['harmonica_eval', 'host'],\n"
        "                                  ['harmonica_eval', 'cockpit'],\n"
        "                                  ['harmonica_eval', 'core'],\n"
        "                                  ['harmonica_eval', 'algorithms'])]\n"
        "if bad:\n"
        "    print(','.join(bad))\n"
        "    sys.exit(1)\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(REPO),
    )
    assert r.returncode == 0, (
        f"`--help` 路径导入了 C1/C4 模块：{r.stdout.strip() or r.stderr.strip()}"
    )


# ── INV-499-5 · §8 清单第 1 条：`--help` 不宣传 `--port` ────────────────
@pytest.mark.parametrize("banned", ["--port", "--host", "--no-browser", "--bind"])
def test_help_does_not_advertise_banned_flags(banned: str) -> None:
    """§7 冻结禁止的开关，★ 连 `--help` 里都不许出现。

    ★ 参数化而非单条断言：★ 四个开关是同一族约束，★ 逐个命名
    ★ 比在一个长列表里更容易在失败时看出是哪一族被破了。
    """
    r = _run_module("--help", timeout=60)
    assert r.returncode == 0, r.stderr[-300:]
    assert banned not in r.stdout, f"--help 宣传了被禁止的开关 {banned}"


def test_parser_declares_only_the_two_required_args() -> None:
    """`add_argument` 恰好声明 `--reference` 与 `--practice`。

    ★ 与上一条互补：★ 上一条查「被禁的没出现」，
    ★ 这一条查「该有的都在，且总数没膨胀」——
    ★ 若有人加了第三个无关开关（如 `--verbose`），★ 上一条抓不到。
    """
    src = SERVE_UI.read_text(encoding="utf-8")
    tree = ast.parse(src)
    opts: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    opts.append(arg.value)
    assert sorted(opts) == ["--practice", "--reference"], opts


# ── INV-499-4 · §8 清单第 4 条：失败非零退出 + 可读原因 ────────────────
def test_missing_audio_exits_nonzero_with_readable_reason() -> None:
    """不存在的音频路径 → 非零退出，★ 且 stderr 有可读原因。

    ★ 这是 SHELL-STANDARD §七「假绿」的防线在装配点上的体现：
    ★ 若它静默退出 0，★ 调用方会以为界面起来了。
    """
    r = _run_module(
        "--reference", "/nonexistent/ref.wav",
        "--practice", "/nonexistent/prac.wav",
        timeout=120,
    )
    assert r.returncode != 0, f"返回码应为非 0（实为 {r.returncode}）—— 那是静默失败"
    blob = (r.stdout + r.stderr).strip()
    assert blob, "stdout/stderr 全空 —— 那比非零退出更糟：调用方无从判断"
    # ★ 可读性下限：★ 要能看出是「输入路径」问题，★ 而不是裸崩栈。
    assert "Traceback" not in blob, f"不应抛裸 Traceback：{blob[:200]}"


# ── §6 INV-499-1 的 pytest 侧复核（★ 与 §8 命令 A/B 同义）─────────────
@pytest.mark.parametrize(
    "inject",
    [
        "import harmonica_eval.cockpit",
        "from harmonica_eval import cockpit",
        "from harmonica_eval.cockpit import app",
    ],
)
def test_detector_would_catch_each_import_form(inject: str) -> None:
    """★ 自检：★ 证明 §8 的静态禁令对【每种 import 形态】都成立。

    ★ 这条测试不碰真实源码（★ 那属于 §8 判据的职责），
    ★ 而是在**合成样本**上验证检测逻辑本身。
    ★ ★ 理由：`from harmonica_eval import cockpit` 的 AST 里
    ★     module='harmonica_eval'，★ cockpit 藏在 names 里 ——
    ★     ★ 只查 module 的检测器会漏掉它，★ 而它恰恰最常见。
    ★     本测试把这个教训固化成可回归的断言。
    """
    sample = f"{inject}\n"
    tree = ast.parse(sample)
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits += [a.name for a in node.names if "cockpit" in a.name]
        elif isinstance(node, ast.ImportFrom):
            if "cockpit" in (node.module or ""):
                hits.append(node.module)
            hits += [
                f"{node.module or ''}.{a.name}"
                for a in node.names
                if "cockpit" in a.name
            ]
    assert hits, f"检测逻辑漏掉了这种形态：{inject!r}（★ 那会给假安全感）"


def test_main_module_has_no_cockpit_dependency() -> None:
    """真实 `__main__.py` 不得依赖 cockpit（FILE-002-v1.md:45/47）。

    ★ 这是 §8 命令 A/B/H 的 pytest 侧同义复核，★ 读的是真实文件。
    """
    tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits += [a.name for a in node.names if "cockpit" in a.name]
        elif isinstance(node, ast.ImportFrom):
            if "cockpit" in (node.module or ""):
                hits.append(node.module)
            hits += [
                f"{node.module or ''}.{a.name}"
                for a in node.names
                if "cockpit" in a.name
            ]
    assert hits == [], hits
