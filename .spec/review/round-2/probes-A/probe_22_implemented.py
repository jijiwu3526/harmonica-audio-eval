"""Probe 22: verify BIs that claim their target file is ALREADY implemented."""
import pathlib, re
ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
print("=== which BIs claim 'already implemented'? ===")
for f in sorted((ROOT/".spec/build").glob("FILE-*.md")):
    t = f.read_text()
    if "已实现" in t and ("核验" in t or "verif" in t.lower()):
        m = re.search(r"^.*已实现.*$", t, re.M)
        print(f"  {f.name}: {m.group(0).strip()[:120]}")
print()
print("=== actual NotImplementedError counts per skeleton file ===")
for f in sorted((ROOT/"harmonica_eval").rglob("*.py")):
    n = f.read_text().count("NotImplementedError")
    print(f"  {n:3}  {f.relative_to(ROOT)}")
