"""Probe 21: FILE-401 requires an 'UNKNOWN' timeline_basis branch, but
contract.TimelineBasis is a closed 2-value enum and FILE-002 §5 says
out-of-range basis => stop & report."""
import sys, pathlib
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
from harmonica_eval.contract import TimelineBasis

ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
print("=== contract.TimelineBasis members (closed) ===")
print("  ", [m.value for m in TimelineBasis])
print("   'UNKNOWN' member exists:", any(m.value=="UNKNOWN" for m in TimelineBasis))
print()
b4 = (ROOT/".spec/build/FILE-401-v1.md").read_text().splitlines()
print("=== FILE-401 mentions of UNKNOWN / unknown basis ===")
for i,l in enumerate(b4,1):
    if "UNKNOWN" in l:
        print(f"  {i}: {l.strip()[:200]}")
print()
print("=== FILE-401 §4.7 render_series_plot basis handling ===")
for i in range(231, 285):
    print(f"  {i+1}: {b4[i].strip()[:175]}")
