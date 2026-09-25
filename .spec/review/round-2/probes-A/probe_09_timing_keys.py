"""Probe 09: FILE-202 §4.4 says all three ratios sum to 1.0, but the denominators
differ (n vs n_notes_used semantics), and compute_deviations drops unpaired.
Also check FILE-002's early/late/on_time -> scalars expectation."""
import sys
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
import pathlib

bi = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval/.spec/build/FILE-202-v1.md").read_text().splitlines()
print("=== FILE-202 §4.4 ratio definitions (verbatim lines 128-152) ===")
for i in range(127, 153):
    print(f"  {i+1}: {bi[i]}")

print()
print("=== FILE-002 scalars expectations: does anything consume early/late/on_time? ===")
b2 = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval/.spec/build/FILE-002-v1.md").read_text().splitlines()
for i,l in enumerate(b2,1):
    if "early_ratio" in l or "late_ratio" in l or "on_time" in l or "median_onset_ms" in l:
        print(f"  {i}: {l.strip()[:160]}")
