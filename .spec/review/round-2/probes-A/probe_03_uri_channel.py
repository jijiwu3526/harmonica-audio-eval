"""Probe 03: can write_metrics_json / render_report_markdown obtain the input URIs
required by FILE-002 §4.3 step 3 and §4.4 lines 309-310?

Enumerate every reachable channel from the frozen signature.
"""
import sys, dataclasses, inspect
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
from harmonica_eval import contract

print("=== FILE-002 frozen signatures (skeleton, authoritative) ===")
import harmonica_eval.__main__ as m
for fn in ("write_metrics_json", "render_report_markdown", "run_headless", "describe_inputs", "main"):
    print(f"  {fn}{inspect.signature(getattr(m, fn))}")

print()
print("=== UiView fields (contract.py, authoritative) ===")
fields = [f.name for f in dataclasses.fields(contract.UiView)]
print("  ", fields)
cands = [n for n in fields if any(k in n.lower() for k in ("ref","prac","uri","path","input","file","name"))]
print("   URI-bearing candidates in UiView:", cands or "NONE")

print()
print("=== UiScalar / UiSeries fields ===")
print("   UiScalar:", [f.name for f in dataclasses.fields(contract.UiScalar)])
print("   UiSeries:", [f.name for f in dataclasses.fields(contract.UiSeries)])

print()
print("=== Does the string 'reference_uri' appear in UiView or any projection type? ===")
for c in (contract.UiView, contract.UiScalar, contract.UiSeries):
    src = inspect.getsource(c)
    print(f"   {c.__name__}: {'YES' if 'reference_uri' in src else 'no'}")

print()
print("=== CONCLUSION ===")
print("  write_metrics_json(view, out_path) is REQUIRED (FILE-002:266) to emit")
print("  {'reference': <reference_uri>, 'practice': <practice_uri>}.")
print("  Reachable args:", inspect.signature(m.write_metrics_json).parameters.keys())
print("  UiView URI carriers:", cands or "NONE")
print("  => channel exists:", bool(cands) or "out_path" in cands)
