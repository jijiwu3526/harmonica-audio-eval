#!/usr/bin/env python3
"""P2-PROBE-2: 入口 __main__ 的依赖闭包能否够到 C1（编排层）？
FILE-002 §3 只允许 __main__ import `.contract`（外加标准库）。
FILE-002 §4.2 要求 run_headless 把两段输入"交给 C1 会话"并"取视图"。
问题：contract.py 里有没有任何会话驱动符号？宿主（C1）的可构造入口在哪？
只读，不修改仓库。"""
from __future__ import annotations
import ast, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
import harmonica_eval.contract as contract
import harmonica_eval.host.app as hostapp

print("=" * 72)
print("[A] contract.py 的 __all__（FILE-002 §3 声称它导出'会话驱动符号'）")
print("   ", list(contract.__all__))
driverish = [n for n in contract.__all__
             if any(k in n.lower() for k in ("driver","session_driver","app","core","factory","create","build_default"))]
print("    含 driver/app/core/factory 的名字:", driverish or "(无)")

print()
print("[B] contract 里可实例化的具体类（非 Protocol / 非 Enum / 非 dataclass 值类型）")
import inspect
for n in contract.__all__:
    o = getattr(contract, n)
    kind = ("Protocol" if getattr(o, "_is_protocol", False)
            else "Enum" if inspect.isclass(o) and issubclass(o, __import__("enum").Enum)
            else "class" if inspect.isclass(o) else type(o).__name__)
    if inspect.isclass(o):
        print(f"    {n:28s} {kind}")
print("    -> HostContract / UiProjectionPort 都是 Protocol（不可实例化）")
print("    -> 无任何 '会话驱动' 具体实现或工厂")

print()
print("[C] __main__.py 的真实 import 集合")
src = (REPO / "harmonica_eval/__main__.py").read_text(encoding="utf-8")
mods = set()
for node in ast.walk(ast.parse(src)):
    if isinstance(node, ast.Import):
        mods |= {a.name.split('.')[0] for a in node.names}
    elif isinstance(node, ast.ImportFrom):
        mods.add(("." * node.level) + (node.module or "") if node.level else (node.module or "").split(".")[0])
print("   ", sorted(mods))
print("    -> 只到 .contract；够不到 host.app（FILE-301 的 build_default_app）")

print()
print("[D] 宿主 C1 的可构造入口")
print("    host.app.build_default_app:", inspect.signature(hostapp.build_default_app))
print("    host.app.HostApp.__init__ :", inspect.signature(hostapp.HostApp.__init__))
print("    -> 唯一工厂在 host.app，而 FILE-002 §3 禁止 __main__ import 它")

print()
print("[E] FILE-002 与 FILE-301 的口径冲突（原文摘录）")
f002 = (REPO/".spec/build/FILE-002-v1.md").read_text(encoding="utf-8")
f301 = (REPO/".spec/build/FILE-301-v1.md").read_text(encoding="utf-8")
for label, txt, needle in (("FILE-002 §3 允许清单", f002, "本包内 | `.contract`"),
                           ("FILE-002 §3 禁止清单", f002, "本包内除 `.contract` 之外的任何模块"),
                           ("FILE-301 §4.2 build_default_app", f301, "本函数是 `__main__.py` 与 `cockpit` 的共同入口")):
    for ln in txt.splitlines():
        if needle in ln:
            print(f"    [{label}] {ln.strip()[:150]}")
