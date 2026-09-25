"""Probe 16: FILE-105 stage 3 (FEATURES) entry is undefined and its dataflow is wrong."""
import sys, inspect, pathlib
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
import harmonica_eval.core.features as F
import harmonica_eval.core.align as A
import harmonica_eval.core.surface as S

ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
b5 = (ROOT/".spec/build/FILE-105-v1.md").read_text().splitlines()

print("=== FILE-105 stage 2 / 3 / 4 (verbatim) ===")
for i in range(166, 186):
    print(f"  {i+1}: {b5[i].strip()[:170]}")

print()
print("=== stage 2 output type (what stage 3 receives as '实参') ===")
print("   align.align", inspect.signature(A.align), "-> NDArray (warp_path, int32 (N,2))")
print()
print("=== every callable in core.features and its FIRST parameter ===")
for n,o in vars(F).items():
    if callable(o) and getattr(o,'__module__',None)=='harmonica_eval.core.features':
        ps = list(inspect.signature(o).parameters)
        print(f"   {n}{inspect.signature(o)}   first_param={ps[0] if ps else None}")
print()
print("   => NO function takes 'warp_path' / '阶段 2 的产出' as first param.")
print("   => NO function returns 'profile 决定的全部端口缓冲'.")
print()
print("=== who actually produces all 12 ports? ===")
print("   core.surface.generate_all_ports(reference, practice, sample_rate, warp_path)")
print("   FILE-104 §4.7 step 5: build_surface() calls generate_all_ports() itself.")
print("   => stage 4 rebuilds ALL ports; stage 3's output has no consumer.")
print()
print("=== FILE-105 §3 whitelist: which core.surface names may api.py import? ===")
for i in range(50, 55):
    print(f"  {i+1}: {b5[i].strip()[:170]}")
print("   => only 'Surface'. build_surface / generate_all_ports are NOT importable by api.py.")
