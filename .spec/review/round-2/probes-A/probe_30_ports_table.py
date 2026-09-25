"""Probe 30: FILE-004 §4.7 port table vs actual profile.PORTS, field by field."""
import sys, pathlib, re
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
from harmonica_eval import profile

print("=== actual profile.PORTS (12) ===")
print(f"{'port_id':26} {'units':10} {'dims':22} {'elem':8} {'basis':10} {'hop':6} produced_by")
for p in profile.PORTS:
    print(f"{p.port_id:26} {p.units:10} {str(tuple(p.dimensions)):22} {p.element_type:8} {p.timeline_basis.value:10} {p.hop_length:<6} {p.produced_by}")
print()
print("=== FILE-004 §4.7 table rows (as written) ===")
b = (ROOT := pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval"))/".spec/build/FILE-004-v1.md"
lines = b.read_text().splitlines()
start = next(i for i,l in enumerate(lines) if l.startswith("### §4.7"))
for i in range(start, min(start+55, len(lines))):
    print(f"  {i+1}: {lines[i]}")
