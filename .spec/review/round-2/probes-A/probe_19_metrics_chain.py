"""Probe 19: end-to-end reachability of every metrics.json scalars key."""
import sys
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
from harmonica_eval.algorithms import PAYLOAD_SCHEMAS
from harmonica_eval.contract import UiScalar

allkeys = set()
for v in PAYLOAD_SCHEMAS.values(): allkeys |= set(v)
print("=== union of PAYLOAD_SCHEMAS keys ===")
print("  ", sorted(allkeys))
print()
print("=== FILE-200 rule: UiScalar.key must be drawn from PAYLOAD_SCHEMAS keys ===")
print("   'UiScalar.key / UiSeries.key 的取值必须取自本表的键名'")
print()
print("=== who builds UiScalars? FILE-301 build_view ===")
import pathlib
ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
b3 = (ROOT/".spec/build/FILE-301-v1.md").read_text().splitlines()
hits=[(i+1,l) for i,l in enumerate(b3) if "UiScalar" in l or "scalar" in l.lower()]
for i,l in hits: print(f"   FILE-301:{i}: {l.strip()[:170]}")
print()
print("=== does FILE-301 specify WHICH keys become scalars / thresholds? ===")
for i,l in enumerate(b3,1):
    if "threshold" in l or "阈值" in l:
        print(f"   FILE-301:{i}: {l.strip()[:170]}")
print()
print("=== FILE-002 §4.3 step5: threshold '原样写出' -- who sets it? ===")
b2 = (ROOT/".spec/build/FILE-002-v1.md").read_text().splitlines()
for i,l in enumerate(b2,1):
    if "threshold" in l:
        print(f"   FILE-002:{i}: {l.strip()[:170]}")
