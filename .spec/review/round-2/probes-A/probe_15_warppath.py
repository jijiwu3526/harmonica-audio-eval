"""Probe 15: warp_path is BOTH an input parameter of generate_all_ports
AND a row in PRODUCER_DISPATCH that calls core.align.align(reference, practice)."""
import pathlib
ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
b = (ROOT/".spec/build/FILE-104-v1.md").read_text().splitlines()

print("=== generate_all_ports signature (skeleton, frozen) ===")
print("   generate_all_ports(reference, practice, sample_rate, warp_path)")
print("   -> warp_path is an INPUT")
print()
print("=== but §4.4 dispatch table has a row producing warp_path ===")
for i,l in enumerate(b,1):
    if "core.align" in l and ("warp_path" in l or "align.align" in l):
        print(f"  {i}: {l.strip()[:200]}")
print()
print("=== §4.4 step 3: '每个端口的生成者由 produced_by 指名' ===")
for i in range(316, 332):
    print(f"  {i+1}: {b[i].strip()[:170]}")
print()
print("=== §4.4 boundary: warp_path (0,2) empty -> '不抛错，由 produced_by 指名的生成者决定行为' ===")
for i,l in enumerate(b,1):
    if "(0, 2)" in l and "warp_path" in l:
        print(f"  {i}: {l.strip()[:200]}")
print()
print("=== CONTRADICTION ===")
print("  If the dispatch row for core.align RE-COMPUTES warp_path from (reference, practice),")
print("  then the warp_path INPUT parameter is dead -- and the caller's alignment")
print("  (api.py stage 2, and FILE-105's 'warp_path from stage 2') is discarded.")
print("  If instead the row forwards the input, the dispatch row is not a producer.")
print("  FILE-104 never says which. Both readings are consistent with the text.")
print()
print("=== what does FILE-105 say about who supplies warp_path to stage 4? ===")
b5 = (ROOT/".spec/build/FILE-105-v1.md").read_text().splitlines()
for i,l in enumerate(b5,1):
    if "warp_path" in l or "阶段 2" in l and "阶段 4" in l:
        print(f"  {i}: {l.strip()[:200]}")
