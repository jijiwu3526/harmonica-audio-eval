"""P3 probe 1 — 端口生产者覆盖：profile.PORTS[*].produced_by 是否每一个都能落到一个真实可调用对象。

只读。不修改仓库任何既有文件。
"""
from __future__ import annotations

import importlib
import inspect
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from harmonica_eval import profile  # noqa: E402


def main() -> int:
    print("=" * 72)
    print("P3 probe 1 · 端口生产者覆盖")
    print("=" * 72)

    # 1) produced_by 取值分布
    by_producer: dict[str, list[str]] = {}
    for spec in profile.PORTS:
        by_producer.setdefault(spec.produced_by, []).append(spec.port_id)
    print("\n[1] produced_by → 端口")
    for prod, pids in sorted(by_producer.items()):
        print(f"    {prod:16s} ({len(pids)}): {pids}")

    # 2) 每个 produced_by 模块是否存在、是否真的导出了生成函数
    print("\n[2] produced_by 模块可导入性 / 生产者可调用性")
    unresolved = []
    for prod, pids in sorted(by_producer.items()):
        modname = "harmonica_eval." + prod  # core.surface → harmonica_eval.core.surface
        try:
            mod = importlib.import_module(modname)
        except Exception as exc:  # noqa: BLE001
            print(f"    {prod:16s} -> 模块不可导入: {type(exc).__name__}: {exc}")
            unresolved.append((prod, pids, "module-missing"))
            continue
        public = [
            (n, o)
            for n, o in vars(mod).items()
            if not n.startswith("_") and (inspect.isfunction(o) or inspect.isclass(o))
            and getattr(o, "__module__", "") == modname
        ]
        print(f"    {prod:16s} -> {modname} 可导入；本模块定义的可调用: {[n for n, _ in public]}")

    # 3) pcm.* 的生产者指向 core.surface 自身；检查 surface 是否有产 pcm 的函数
    print("\n[3] pcm.* 的生产者是不是 core.surface 自己？")
    surf = importlib.import_module("harmonica_eval.core.surface")
    surf_funcs = [
        n for n, o in vars(surf).items()
        if not n.startswith("_") and inspect.isfunction(o) and getattr(o, "__module__", "") == surf.__name__
    ]
    print(f"    core/surface.py 顶层函数: {surf_funcs}")
    print("    profile 声明 pcm.* 的 produced_by =", sorted({p.produced_by for p in profile.PORTS if p.port_id.startswith('pcm.')}))
    print("    -> 生产者模块 = core.surface（即 surface.py 自身）")
    pcm_hits = [n for n in surf_funcs if "pcm" in n.lower() or "warp" in n.lower() or "map" in n.lower()]
    print(f"    surface.py 中名字含 pcm/warp/map 的函数: {pcm_hits}")

    # 4) 全仓搜索任何能产出 pcm.mapped.* / pcm.warped.practice 的候选函数
    print("\n[4] 全仓（harmonica_eval/）搜索 pcm 生产者候选")
    cand = []
    for py in (REPO / "harmonica_eval").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "def " not in text:
            continue
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("def ") and any(k in s.lower() for k in ("warp", "map_pcm", "apply", "stretch", "interp", "resample")):
                cand.append(f"{py.relative_to(REPO)}:{s}")
    for c in cand:
        print("    ", c)
    if not cand:
        print("     (无任何候选)")

    print("\n[结论]")
    print(f"    produced_by 取值 {len(by_producer)} 个；其中 core.surface 被声明为 pcm.* 的生产者，")
    print("    但 FILE-104 明令 surface.py 不得实现 PCM 生产、且不得硬编码端口名；")
    print("    其余模块（features/align）均不导出 pcm.* 生产者。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
