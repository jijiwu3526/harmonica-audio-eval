"""Probe 12: FILE-002 §4.5 summarize_series still says '<n> = 点数元信息',
which is the SAME stale wording that §4.3 :293-309 explicitly corrects."""
import pathlib
p = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval/.spec/build/FILE-002-v1.md")
lines = p.read_text().splitlines()
print("=== §4.3 correction (line 303-309) ===")
for i in range(302, 310):
    print(f"  {i+1}: {lines[i]}")
print()
print("=== §4.5 summarize_series (line 334-345) -- NOT corrected ===")
for i in range(333, 346):
    print(f"  {i+1}: {lines[i]}")
print()
print("=== §10 escalation item 4 (line 639) still cites the corrected premise ===")
print(f"  639: {lines[638]}")
print()
print("=== CONTRADICTION ===")
print("  §4.3 :303-309 freezes: n_points = len(s.t); forbids 'estimate by other means'.")
print("  §4.5 :366 still says: '<n> = 该 UiSeries 的点数元信息（整型，str(n)）'")
print("  §4.5 :367 still says: '只读元信息'")
print("  UiSeries has NO 'n_points' field -> '点数元信息' does not exist.")
print("  => A literal reader of §4.5 is again told to read a nonexistent field.")
