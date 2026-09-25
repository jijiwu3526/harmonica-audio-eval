"""Probe 32: FILE-002 §4.3/§4.4 corrected signatures vs the FROZEN skeleton."""
import ast, pathlib, re, inspect, sys
ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")

sk = ROOT/"harmonica_eval/__main__.py"
tree = ast.parse(sk.read_text())
sigs = {}
for n in tree.body:
    if isinstance(n, ast.FunctionDef):
        sigs[n.name] = ast.unparse(n.args)
print("=== SKELETON (frozen artifact) signatures ===")
for k in ("write_metrics_json","render_report_markdown","run_headless","main","describe_inputs","summarize_series"):
    print(f"   {k}({sigs.get(k)})")

print()
print("=== FILE-002 BI headings ===")
b = (ROOT/".spec/build/FILE-002-v1.md").read_text().splitlines()
for i,l in enumerate(b,1):
    if l.startswith("### 4.") and ("write_metrics_json" in l or "render_report_markdown" in l):
        print(f"   BI:{i}: {l}")

print()
print("=== FILE-002 §4.9 公开符号闭合表 ===")
start = next(i for i,l in enumerate(b) if l.startswith("### 4.9"))
for i in range(start, start+14):
    print(f"   BI:{i+1}: {b[i]}")

print()
print("=== import the skeleton and inspect live ===")
sys.path.insert(0, str(ROOT))
import harmonica_eval.__main__ as m
print("   write_metrics_json", inspect.signature(m.write_metrics_json))
print("   render_report_markdown", inspect.signature(m.render_report_markdown))
