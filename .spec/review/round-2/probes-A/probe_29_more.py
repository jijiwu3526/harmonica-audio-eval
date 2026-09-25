import sys, pathlib, re
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
import harmonica_eval.host as H
import harmonica_eval as P

print("=== FILE-300: host/__init__ docstring keys + line claims ===")
b = (ROOT/".spec/build/FILE-300-v1.md").read_text().splitlines()
for i,l in enumerate(b,1):
    if "行" in l and re.search(r"\d+\s*[–\-—]\s*\d+", l): print(f"  BI:{i}: {l.strip()[:150]}")
    if "splitlines" in l or "len(" in l and "doc" in l: print(f"  BI:{i}: {l.strip()[:150]}")
print("  actual host/__init__ doc lines:", len(H.__doc__.splitlines()))
print("  actual file lines:", len((ROOT/'harmonica_eval/host/__init__.py').read_text().splitlines()))

print()
print("=== FILE-001: package __init__ claims ===")
b1 = (ROOT/".spec/build/FILE-001-v1.md").read_text().splitlines()
for i,l in enumerate(b1,1):
    if "splitlines" in l or "PUBLIC_SUBMODULES" in l and ("==" in l or "恰" in l):
        print(f"  BI:{i}: {l.strip()[:170]}")
print("  actual __version__ =", P.__version__)
print("  actual __all__ =", P.__all__)
print("  actual PUBLIC_SUBMODULES =", P.PUBLIC_SUBMODULES)

print()
print("=== FILE-004: claims '12 ports'? ===")
from harmonica_eval import profile
print("  actual len(PORTS) =", len(profile.PORTS))
b4 = (ROOT/".spec/build/FILE-004-v1.md").read_text()
for m in re.finditer(r"[^\n]*12 个端口[^\n]*", b4):
    print("  BI:", m.group(0).strip()[:150])
print()
print("  distinct produced_by:", sorted({p.produced_by for p in profile.PORTS}))
print("  FILE-004 INV-4-15/23 claim 'produced_by 只出现 3 个值':",
      len({p.produced_by for p in profile.PORTS})==3)
