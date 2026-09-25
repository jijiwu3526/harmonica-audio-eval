"""Probe 14: FILE-401's UiSeries validation claim vs FILE-002's assertion duty."""
import pathlib
ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
b2 = (ROOT/".spec/build/FILE-002-v1.md").read_text().splitlines()
print("=== FILE-002 line 305 claims: '这是 C4 侧也做的校验，见 FILE-401 §4.x' ===")
print("  305:", b2[304].strip())
print()
b4 = (ROOT/".spec/build/FILE-401-v1.md").read_text().splitlines()
print("=== search FILE-401 for len(t)/len(values) validation of UiSeries ===")
hits = [(i+1,l) for i,l in enumerate(b4) if ("len(" in l and ("t)" in l or "values" in l)) or "长度" in l and "t" in l]
for i,l in hits[:25]:
    print(f"  {i}: {l.strip()[:150]}")
print()
print("=== search FILE-401 for 'n_points' ===")
for i,l in enumerate(b4,1):
    if "n_points" in l:
        print(f"  {i}: {l.strip()[:150]}")
print("  (none above => FILE-002's cross-reference to FILE-401 §4.x is unverifiable)")
