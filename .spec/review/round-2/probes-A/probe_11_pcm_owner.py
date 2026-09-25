"""Probe 11: pcm.* producer adjudication -- is it consistent across ALL files?"""
import sys, pathlib
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
from harmonica_eval import profile

ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
print("=== profile.py: produced_by for pcm.* (CONFIG AUTHORITY) ===")
for p in profile.PORTS:
    if p.port_id.startswith("pcm"):
        print(f"  {p.port_id:24} produced_by={p.produced_by!r} basis={p.timeline_basis.value}")

print()
print("=== every file that claims to produce pcm.* ===")
pats = ["pcm.mapped", "pcm.warped"]
for f in sorted(list((ROOT/".spec/build").glob("FILE-*.md")) + [ROOT/"harmonica_eval/core/__init__.py"] +
                sorted((ROOT/"harmonica_eval").rglob("*.py"))):
    try: txt = f.read_text()
    except Exception: continue
    for i,l in enumerate(txt.splitlines(),1):
        if any(p in l for p in pats) and any(k in l for k in ("产出","生成","produced_by","生产","归属","装配","→")):
            print(f"  {f.relative_to(ROOT)}:{i}: {l.strip()[:140]}")

print()
print("=== FILE-102 align: does it produce any PCM? ===")
a = (ROOT/".spec/build/FILE-102-v1.md").read_text().splitlines()
for i,l in enumerate(a,1):
    if "PCM" in l or "pcm" in l:
        print(f"  {i}: {l.strip()[:150]}")
