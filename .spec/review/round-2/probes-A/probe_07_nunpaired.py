"""Probe 07: is n_unpaired reachable in FILE-202 (timing) and FILE-203 (dynamics)?"""
import sys, inspect
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
import harmonica_eval.algorithms.timing as T
import harmonica_eval.algorithms.dynamics as D
from harmonica_eval.algorithms import PAYLOAD_SCHEMAS

print("=== FILE-202 timing: frozen skeleton signatures ===")
for fn in ("detect_onsets","match_onsets","compute_deviations","summarize_deviations","run"):
    print(f"  {fn}{inspect.signature(getattr(T, fn))}")
print()
print("  PAYLOAD_SCHEMAS['timing'] =", PAYLOAD_SCHEMAS["timing"])
print("  'n_unpaired' required in payload ->", "n_unpaired" in PAYLOAD_SCHEMAS["timing"])
print()
print("  FILE-202 §4.4 says n_unpaired '来自 match_onsets'.")
print("  But §4.5 run() flow is:")
print("      payload = summarize_deviations(compute_deviations(matched))")
print("  and §4.3 fixes compute_deviations(matched) -> list[float].")
print("  => summarize_deviations receives ONLY list[float]; match_onsets result is gone.")
print("  => n_unpaired has NO reachable channel into summarize_deviations.")
print()
print("=== FILE-203 dynamics: same question ===")
for fn in ("to_db","note_spans","align_by_note","compute_deltas","summarize_deltas","run"):
    print(f"  {fn}{inspect.signature(getattr(D, fn))}")
print()
print("  PAYLOAD_SCHEMAS['dynamics'] =", PAYLOAD_SCHEMAS["dynamics"])
print("  'n_unpaired' required ->", "n_unpaired" in PAYLOAD_SCHEMAS["dynamics"])
print()
print("  FILE-203 §summarize_deltas: 'n_unpaired = 在 run 层由 align_by_note 计算并回传, 此处接收'")
print("  But signature summarize_deltas(deltas_db) takes only deltas_db.")
print("  align_by_note -> list[tuple[float,float]]; compute_deltas -> list[float].")
print("  => '此处接收' is impossible: no parameter carries it.")
