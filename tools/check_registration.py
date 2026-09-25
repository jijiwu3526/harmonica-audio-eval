"""登记守卫：未跟踪的新 .py 必须在授权真相源里【先登记、后存在】（SHELL-STANDARD §七）。

问题
----
本项目发生过三次同一循环：注入或新建一个 ``harmonica_eval/**/*.py`` →
忘了在 ``tools/authorized_impl.py`` 登记 → ``verify_shell`` 报「实现代码泄漏」
→ 才补登记。三次的发现方式都是「人专门跑了一次门禁」。

本守卫把发现时机提前：文件一旦出现在工作区、还没登记，门禁就红。

判定
----
``git status --porcelain`` 中状态为 ``??``（未跟踪）且后缀为 ``.py`` 的
``harmonica_eval/`` 下文件，**每一个**都必须在
:mod:`tools.authorized_impl` 的 ``REPO_REL`` 里有【精确路径】条目。

精确匹配，不接受 ``startswith`` / 目录前缀 / 正则
------------------------------------------------
反例：``harmonica_eval/core/ingest_extra.py`` 照抄 ``ingest.py`` 的实现，
前缀匹配会把它当成 ``ingest`` 放行 —— 而它是个未登记的新文件。
放行就是假绿，所以本判据用集合成员判断（``in``）。

边界情形（逐条说明理由）
------------------------
``a`` ``__init__.py``
    **被扫**。``harmonica_eval/cockpit/__init__.py`` 是包出口
    ``launch_cockpit(...)``，是 C4 的公开面之一，确实需要登记与依据。
    本仓的 ``__init__.py`` 都在 ``REPO_REL`` 或 ``verify_shell.GROUND`` 里，
    扫它不会产生噪声。若将来某个 ``__init__.py`` 确实不承载实现，
    应当由登记决定（登记它并写明依据），而不是靠扫��规则静默放过。

``b`` 非 ``.py`` 文件（``.md`` / ``.html`` / ``.json`` / ``.toml``）
    **不扫**。它们不承载可执行实现，登记它们只会制造噪声。
    当前工作区有 5 个这样的未跟踪文件（README / preview.html）。

``c`` 临时产物（``.tmp`` / ``.pyc`` / ``__pycache__/`` / ``.tmpdir/``）
    **不扫**，但 ``__pycache__`` 本身要排除（见 ``_EXCLUDED_DIRS``）。
    ★ 隐藏路径【必须】在扫描范围内：``.tmpdir`` 是隐藏目录，
      按 ``harmonica_eval/*.py`` 这类模式找文件会漏掉它。
      本项目踩过这个坑（cockpit/.app.py.*.tmpdir 里的半截文件没被 hygiene 发现），
      所以这里用 ``git status --porcelain`` 读 git 自己的输出 ——
      git 会报出隐藏路径下的文件，不依赖 glob。

``d`` git 不可用（无仓库 / CI 未 checkout）
    **跳过并显式打印原因，退出码 0**。
    理由：守卫的职责是「在有版本控制的工作区里提前发现漏登记」。
    没有 git 时我们无法知道哪些文件是「新出现的」，此时红灯是噪声。
    但必须**打印**跳过原因 —— 静默失效会让这道守卫变成摆设。
    ★ 退出码用 0 而非 2：``check_all.sh`` 里 check 类是「非 0 即阻塞」，
      在无 git 的环境里让它阻塞整套门禁是错的。

``e`` 已被 git 跟踪、但后来新增实现的文件
    **不归本守卫管**。那是 :mod:`tools.verify_shell` 的职责
    （它扫「已登记但出现实现」的方向）。
    本守卫只管「未登记却已存在」这一个方向，两者互补不重叠。

与 verify_shell 的分工
---------------------
===================== ========================== ==========================
方向                   工具                      失败含义
===================== ========================== ==========================
已登记 → 出现实现      ``verify_shell.py``        授权过但实现漏改/白名单过期
未登记 → 文件已存在    本守卫                     授权流程漏了一步
===================== ========================== ==========================
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "tools"))

from authorized_impl import REPO_REL  # noqa: E402

_SCAN_PREFIX = "harmonica_eval/"

#: 这些目录不参与扫描（临时产物）。注意 ``.tmpdir`` 也算 ——
#: 它是隐藏的临时目录，本项目踩过「隐藏路径漏检」的坑。
_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {"__pycache__", ".git", ".tmpdir", ".pytest_cache", ".mypy_cache"}
)


def _untracked_python_files() -> list[str] | None:
    """返回未跟踪的 ``harmonica_eval/**/*.py``；git 不可用时返回 ``None``。

    刻意用 ``git status --porcelain`` 而不是 ``Path.rglob``：
    git 的输出包含隐藏路径下的文件（``.tmpdir/…``），
    而 ``rglob`` 在多数配置下会漏掉隐藏目录 —— 那是本项目踩过的坑。

    ★ 不用 ``rglob`` 的另一个理由：它会把 ``__pycache__`` 里的
    ``.pyc`` 混进来，也会踩到解析器正在写的临时文件。
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", _SCAN_PREFIX],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as err:
        print(f"★ 跳过：无法执行 git（{err.__class__.__name__}: {err}）")
        return None
    if proc.returncode != 0:
        # ★ 不静默失效：打印 stderr，退出码 0（见模块 docstring 边界 d）
        detail = (proc.stderr or "").strip().splitlines()
        head = detail[0] if detail else f"git 退出码 {proc.returncode}"
        print(f"★ 跳过：git status 不可用（{head}）")
        return None

    found: list[str] = []
    for line in proc.stdout.splitlines():
        if not line.startswith("?? "):
            continue  # 只关心未跟踪；已跟踪的归 verify_shell
        path = line[3:].strip().strip('"')
        if not path.endswith(".py"):
            continue  # 边界 b：非 .py 不扫
        parts = set(path.split("/"))
        if parts & _EXCLUDED_DIRS:
            continue  # 边界 c：临时产物
        found.append(path)
    return sorted(found)


def main() -> int:
    untracked = _untracked_python_files()
    if untracked is None:
        return 0  # 边界 d：无 git 时跳过，且已打印原因

    registered = REPO_REL
    missing = [p for p in untracked if p not in registered]

    if not untracked:
        print("✅ 未跟踪的 .py 文件：0 个")
        return 0

    if not missing:
        print(
            f"✅ 未跟踪 .py 共 {len(untracked)} 个，全部已在 "
            f"tools/authorized_impl.py 登记（精确路径）"
        )
        for p in untracked:
            print(f"   · {p}")
        return 0

    print(f"❌ 发现 {len(missing)} 个未登记的新文件（已存在于工作区，但不在授权真相源里）")
    print()
    for p in missing:
        print(f"   ❌ {p}")
    print()
    print("   这类文件会让 verify_shell 报「实现代码泄漏」——")
    print("   而那要到专门跑一次门禁才会被发现。")
    print()
    print("   若确已获授权，先在 tools/authorized_impl.py 登记：")
    print("     · 键为【仓库根相对路径】（与现存条目同格式）")
    print("     · 值为「哪次授权 + 依据哪份 BI」——无依据的条目不允许写入")
    print()
    print("   ★ 判定用精确路径匹配，不用 startswith：")
    print("     core/ingest_extra.py 照抄 ingest 的实现时，前缀匹配会放行它。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
