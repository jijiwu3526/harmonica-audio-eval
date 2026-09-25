"""Probe 05: compare every algorithm's per-function return keys declared in its BI
against algorithms.PAYLOAD_SCHEMAS (the declared sole authority)."""
import sys
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
from harmonica_eval.algorithms import PAYLOAD_SCHEMAS

print("=== PAYLOAD_SCHEMAS (authority) ===")
for k, v in PAYLOAD_SCHEMAS.items():
    print(f"  {k:10} n={len(v)}  {v}")

print()
print("=== FILE-201 §4.2 compare_pitch_curves declared return ===")
print("  {'per_note_cents','n_paired','n_unpaired'}  (3 keys)")
print("  'n_paired' in PAYLOAD_SCHEMAS['pitch']? ->", "n_paired" in PAYLOAD_SCHEMAS["pitch"])
print("  'n_unpaired' in PAYLOAD_SCHEMAS['pitch']? ->", "n_unpaired" in PAYLOAD_SCHEMAS["pitch"])
print("  => FILE-201 §4.3 summarize_deviations must convert n_paired -> n_notes_used")

print()
print("=== FILE-201 §4.3 summarize_deviations declared return ===")
print("  keys = PAYLOAD_SCHEMAS['pitch'] =", PAYLOAD_SCHEMAS["pitch"])
print("  'n_unpaired' present in pitch schema? ->", "n_unpaired" in PAYLOAD_SCHEMAS["pitch"])

print()
print("=== cross-check: does the skeleton pitch.py docstring agree? ===")
import pathlib, re
sk = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval/harmonica_eval/algorithms/pitch.py").read_text()
for m in re.finditer(r"^\s*(per_note_cents|median_abs_cents|off_pitch_ratio|n_notes_used|sample_rate|n_paired|n_unpaired)\b.*$", sk, re.M):
    print("   skeleton:", m.group(0).strip()[:100])
