"""Probe 23: FILE-100/FILE-300 freeze the module docstring line ranges.
Verify those ranges match the actual skeleton files."""
import pathlib, re
ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")

for name, bi in (("core/__init__.py","FILE-100-v1.md"), ("host/__init__.py","FILE-300-v1.md"),
                 ("__init__.py","FILE-001-v1.md")):
    p = ROOT/"harmonica_eval"/name
    lines = p.read_text().splitlines()
    print(f"=== {name}: total {len(lines)} lines ===")
    b = (ROOT/".spec/build"/bi).read_text().splitlines()
    for i,l in enumerate(b,1):
        if re.search(r"第\s*\d+[–\-—]\d+\s*行", l):
            print(f"  BI:{i}: {l.strip()[:150]}")

import re
print()
print("=== FILE-100 §4.1 claims 4 top-level AST nodes ===")
import ast
for name in ("core/__init__.py","host/__init__.py"):
    tree = ast.parse((ROOT/"harmonica_eval"/name).read_text())
    print(f"  {name}: {len(tree.body)} top-level nodes")
    for n in tree.body:
        print(f"     {type(n).__name__}")
