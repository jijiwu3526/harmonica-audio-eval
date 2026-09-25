#!/usr/bin/env python3
"""P2-PROBE-1: 端口 -> 生产者 的分派链是否闭合。
检查：profile.PortSpec.produced_by 能否解析为一个可调用对象；
是否存在 (port_id -> producer) 的映射；生产者的真实签名是否符合
FILE-104 §4.4 冻结的 4 参约定 (reference, practice, sample_rate, warp_path)。
只读，不修改仓库。"""
from __future__ import annotations
import importlib, inspect, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

import harmonica_eval.profile as profile
from harmonica_eval.core import align, features, surface

print("=" * 72)
print("[A] produced_by 的值形态（模块名 or 函数名？）")
vals = sorted({s.produced_by for s in profile.PORTS})
for v in vals:
    print(f"    {v!r}  ports={[s.port_id for s in profile.PORTS if s.produced_by==v]}")

print()
print("[B] importlib.import_module(produced_by) —— 按 FILE-104 §3 的字面口径")
for v in vals:
    try:
        m = importlib.import_module(v)
        print(f"    import_module({v!r}) -> {m!r}  callable={callable(m)}")
    except Exception as e:
        print(f"    import_module({v!r}) -> {type(e).__name__}: {e}")

print()
print("[C] 是否存在 (port_id -> producer callable) 映射？")
for mod in (align, features, surface):
    hits = [n for n in dir(mod) if "PRODUCER" in n.upper() or "MAP" in n.upper()]
    print(f"    {mod.__name__}: {hits or '(无映射常量)'}")
print("    profile.PortSpec 字段:", [f for f in profile.PortSpec.__dataclass_fields__])
print("    -> PortSpec 只有 produced_by（模块名），没有 producer 函数名/入口字段")

print()
print("[D] 所有候选生产者函数的真实签名 vs FILE-104 §4.4 冻结的 4 参约定")
WANT = ("reference", "practice", "sample_rate", "warp_path")
cands = []
for mod in (align, features, surface):
    for n, fn in vars(mod).items():
        if inspect.isfunction(fn) and not n.startswith("_"):
            cands.append((mod.__name__, n, fn))
for mn, n, fn in sorted(cands):
    sig = inspect.signature(fn)
    params = tuple(sig.parameters)
    ok = params == WANT
    print(f"    {'MATCH' if ok else 'no   '} {mn}.{n}{sig}")
print(f"    冻结约定: {WANT}")
print(f"    匹配数: {sum(1 for mn,n,fn in cands if tuple(inspect.signature(fn).parameters)==WANT)}"
      f" / {len(cands)}")

print()
print("[E] 12 个端口里，哪个模块/函数真的会产出 pcm.mapped.* / pcm.warped.practice？")
for pid in ("pcm.mapped.reference", "pcm.mapped.practice", "pcm.warped.practice"):
    spec = profile.PORT_INDEX[pid]
    print(f"    {pid}: produced_by={spec.produced_by!r}")
print("    core.align.align 的返回:", inspect.signature(align.align), "-> 只有 warp_path（FILE-102 §align）")
print("    core.features 的 4 个函数只覆盖 pitch/rms/chroma/notes，无 pcm.*")
print("    -> pcm.mapped.* / pcm.warped.practice 在模块里没有对应生产函数")
