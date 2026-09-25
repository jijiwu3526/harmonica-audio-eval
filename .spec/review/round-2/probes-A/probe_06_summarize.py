"""Probe 06: summarize_deviations return arity. FILE-201 §4.3 says 'exactly 5 keys'
but then specifies a body returning 4; skeleton signature takes only deviations_cents."""
import sys, inspect, pathlib, re
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
import harmonica_eval.algorithms.pitch as P

print("=== skeleton signature (frozen by SHELL, cannot change) ===")
print("  ", inspect.signature(P.summarize_deviations))
print("   params:", list(inspect.signature(P.summarize_deviations).parameters))
print("   -> sample_rate NOT a parameter")

print()
print("=== FILE-201 §4.3 text ===")
bi = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval/.spec/build/FILE-201-v1.md").read_text()
for ln in (237, 242, 243, 250, 251):
    pass
lines = bi.splitlines()
for i in range(236, 258):
    print(f"  {i+1}: {lines[i]}")

print()
print("=== contradiction summary ===")
print("  §4.3 heading says: '恰好 5 个键，一字不得增删'")
print("  §4.3 body code returns 4 keys (no sample_rate)")
print("  §4.3 then says: '若实现者选择让本函数直接收 sample_rate 并返回 5 键，也允许'")
print("  BUT skeleton signature is summarize_deviations(deviations_cents) -> object")
print("      -> 'also allowed' branch is IMPOSSIBLE without changing the frozen signature")
print("  AND run() must add sample_rate; is that stated? see §4.4")
for i in range(287, 345):
    if i < len(lines):
        print(f"  {i+1}: {lines[i]}")
