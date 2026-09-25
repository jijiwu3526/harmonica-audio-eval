"""P3 probe 2 — 进程入口可达性：__main__.py 被允许 import 的东西，够不够驱动 C1？

依据 FILE-002 §3（允许 import 的封闭清单）与 contract.py 的实际导出面。
只读。
"""
from __future__ import annotations

import ast
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

ALLOWED_FILE002 = {"__future__", "argparse", "json", "sys", "pathlib", "typing", ".contract"}


def main() -> int:
    print("=" * 72)
    print("P3 probe 2 · 进程入口可达性（FILE-002 → C1）")
    print("=" * 72)

    src = (REPO / "harmonica_eval" / "__main__.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add(("." * node.level) + (node.module or "") if node.level else (node.module or "").split(".")[0])

    print("\n[1] __main__.py 实际 import：", sorted(mods))
    print("    FILE-002 §3 允许清单：", sorted(ALLOWED_FILE002))
    print("    越界：", sorted(mods - ALLOWED_FILE002) or "无")

    # contract.py 是否导出任何「会话驱动面」
    import harmonica_eval.contract as c

    names = [n for n in dir(c) if not n.startswith("_")]
    driver_like = [
        n for n in names
        if any(k in n.lower() for k in ("driver", "facade", "app", "core", "session", "run", "build_default", "host"))
    ]
    print("\n[2] contract.py 公开符号总数：", len(names))
    print("    其中像「会话驱动面」的名字：", driver_like or "无")

    # HostContract 是 Protocol（纯声明），UiProjectionPort 也是
    import inspect
    protos = [n for n in names if inspect.isclass(getattr(c, n)) and getattr(getattr(c, n), "_is_protocol", False)]
    print("    contract 中的 Protocol（纯声明，无实现）：", protos)

    print("\n[3] run_headless 规格要求的两步（FILE-002 §4.2）：")
    print("    1. 把 reference/practice 交给 C1 会话（登记）")
    print("    2. 构建数据面（预生成 + Seal）→ 等 DATA_READY")
    print("    这两步需要一个可调用的 C1 门面（HostApp / build_default_app）。")
    print("    C1 门面位于 harmonica_eval/host/app.py —— 但 FILE-002 §3 禁止 import host。")
    print("    contract.py 不导出任何 C1 门面或会话驱动符号（只有 Protocol 与 dataclass）。")

    # 谁调用了 build_default_app / HostApp
    print("\n[4] 全仓搜索 build_default_app / HostApp 的调用点（非 .spec 文档）")
    hits = []
    for py in (REPO / "harmonica_eval").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if "build_default_app" in line or "HostApp" in line:
                hits.append(f"{py.relative_to(REPO)}:{i}: {line.strip()[:100]}")
    for h in hits:
        print("    ", h)
    callers = [h for h in hits if "host/app.py" not in h]
    print("    非 host/app.py 的引用点：", callers or "无（没有任何调用方）")

    print("\n[结论]")
    print("    入口 → C1 的边在「FILE-002 只准 import .contract」与")
    print("    「C1 门面住在 host/app.py」之间断开：contract 无驱动面，")
    print("    host 被禁止 import，build_default_app 无人调用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
