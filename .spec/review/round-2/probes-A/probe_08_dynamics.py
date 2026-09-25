"""Probe 08: FILE-203 internal contradictions -- envelope field names and notes repr."""
import sys, dataclasses, inspect
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
from harmonica_eval.contract import AlgorithmResultEnvelope, BufferView, PortDescriptor

print("=== AlgorithmResultEnvelope FIELDS (contract, authoritative) ===")
fields = [f.name for f in dataclasses.fields(AlgorithmResultEnvelope)]
print("  ", fields)
print("  has 'error'?      ->", "error" in fields)
print("  has 'error_code'? ->", "error_code" in fields)

print()
print("=== FILE-203 §5 failure table uses 'error=' kwarg ===")
import pathlib
bi = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval/.spec/build/FILE-203-v1.md").read_text().splitlines()
for i,l in enumerate(bi, 1):
    if "status='FAILED'" in l or "error=" in l:
        print(f"  {i}: {l.strip()[:150]}")

print()
print("=== instantiate envelope the way FILE-203 §5 writes it ===")
try:
    AlgorithmResultEnvelope(
        algorithm_id="dynamics", algorithm_version="1.0.0",
        status="FAILED", required_ports=(), consumed_ports=(),
        payload={}, error="MISSING_RMS_PORT")
    print("  constructed OK (unexpected)")
except TypeError as e:
    print("  TypeError ->", e)

print()
print("=== FILE-203 notes representation: list[dict] vs (n_note,3) ndarray ===")
for i,l in enumerate(bi,1):
    if "list[dict]" in l or "n_note, 3" in l or "onset_sec" in l and ("列" in l or "dict" in l):
        print(f"  {i}: {l.strip()[:160]}")

print()
print("=== skeleton dynamics.note_spans docstring ===")
import harmonica_eval.algorithms.dynamics as D
doc = D.note_spans.__doc__
print("  ", doc.strip().splitlines()[0])
print("  (skeleton param annotation:)", inspect.signature(D.note_spans))
