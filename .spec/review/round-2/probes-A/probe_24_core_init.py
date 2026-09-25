"""Probe 24: FILE-100 claims __all__ 5 submodules 'because profile.PORTS
produced_by covers these 5'. Verify against actual produced_by set."""
import sys, pathlib
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
from harmonica_eval import profile

print("=== distinct produced_by values in profile.PORTS ===")
pb = sorted({p.produced_by for p in profile.PORTS})
print("  ", pb)
print("   count:", len(pb))
print()
print("=== core/__init__ __all__ ===")
import harmonica_eval.core as C
print("  ", C.__all__)
print()
print("=== FILE-100 §4.5 says: __all__ declares 5 submodules 'because produced_by covers these 5' ===")
print("   produced_by covers:", pb)
print("   __all__ says      :", C.__all__)
print("   set(produced_by) == set(__all__)? ->", set(pb)==set(C.__all__))
print("   difference produced_by - __all__:", set(pb)-set(C.__all__))
print("   difference __all__ - produced_by:", set(C.__all__)-set(pb))
print()
print("=== docstring line count (FILE-100 INV: == 31) ===")
doc = C.__doc__
print("   len(doc.splitlines()) =", len(doc.splitlines()))
