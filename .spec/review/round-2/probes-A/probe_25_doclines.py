"""Probe 25: FILE-100 freezes docstring as 'lines 1-31' and INV asserts
len(__doc__.splitlines()) == 31. Measure reality."""
import sys, pathlib
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
import harmonica_eval.core as C
import ast

p = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval/harmonica_eval/core/__init__.py")
lines = p.read_text().splitlines()

print("=== raw file: quote delimiters ===")
print("  line 1 :", repr(lines[0]))
print("  line 30:", repr(lines[29]))
print("  line 31:", repr(lines[30]))
print("  line 32:", repr(lines[31]))
print()
tree = ast.parse(p.read_text())
docnode = tree.body[0]
print("=== AST docstring node ===")
print("  node lineno:", docnode.lineno, " end_lineno:", docnode.end_lineno)
raw = docnode.value.value
print("  len(raw.splitlines()) =", len(raw.splitlines()))
print("  len(raw.split('\\n')) =", len(raw.split("\n")))
print()
print("=== C.__doc__ (runtime) ===")
print("  len(C.__doc__.splitlines()) =", len(C.__doc__.splitlines()))
print()
print("=== FILE-100 spec claims ===")
b = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval/.spec/build/FILE-100-v1.md").read_text().splitlines()
for i,l in enumerate(b,1):
    if "== 31" in l or "第 1–31 行" in l or "31" in l:
        print(f"  BI:{i}: {l.strip()[:170]}")
print()
print("=== §8 verification code for this invariant ===")
for i in range(268, 292):
    print(f"  BI:{i+1}: {b[i]}")
