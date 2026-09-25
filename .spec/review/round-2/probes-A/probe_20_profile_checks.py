"""Probe 20: profile.py docstring says '检查六件事' but the body has 7 checks
numbered 1,2,3,4,5,7,8 (no 6). Is the docstring frozen by FILE-004?"""
import pathlib, re
ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
sk = (ROOT/"harmonica_eval/profile.py").read_text().splitlines()

print("=== skeleton profile.py: docstring claim ===")
for i in range(450, 468):
    print(f"  {i+1}: {sk[i]}")
print()
print("=== actual check comments in body ===")
for i,l in enumerate(sk,1):
    if re.search(r"#\s*检查\s*\d", l):
        print(f"  {i}: {l.strip()}")
print()
print("=== FILE-004 spec: does it freeze the docstring verbatim? ===")
b4 = (ROOT/".spec/build/FILE-004-v1.md").read_text().splitlines()
for i,l in enumerate(b4,1):
    if "六件事" in l or "逐字" in l and "docstring" in l or "检查六" in l:
        print(f"  {i}: {l.strip()[:180]}")
print()
print("=== FILE-004 §4.10 assert_profile_integrity check count ===")
for i,l in enumerate(b4,1):
    if re.match(r"^\s*\d+\.\s", l) and i>270 and i<300:
        print(f"  {i}: {l.strip()[:170]}")
