"""Probe 01: compare def signatures in skeleton vs signatures quoted in Build Instruction.

Reads only. Emits machine-checkable output.
"""
import ast, re, pathlib, sys

ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")

MAP = {
 "harmonica_eval/__init__.py": "FILE-001-v1.md",
 "harmonica_eval/__main__.py": "FILE-002-v1.md",
 "harmonica_eval/contract.py": "FILE-003-v1.md",
 "harmonica_eval/profile.py": "FILE-004-v1.md",
 "harmonica_eval/core/__init__.py": "FILE-100-v1.md",
 "harmonica_eval/core/ingest.py": "FILE-101-v1.md",
 "harmonica_eval/core/align.py": "FILE-102-v1.md",
 "harmonica_eval/core/features.py": "FILE-103-v1.md",
 "harmonica_eval/core/surface.py": "FILE-104-v1.md",
 "harmonica_eval/core/api.py": "FILE-105-v1.md",
 "harmonica_eval/algorithms/__init__.py": "FILE-200-v1.md",
 "harmonica_eval/algorithms/pitch.py": "FILE-201-v1.md",
 "harmonica_eval/algorithms/timing.py": "FILE-202-v1.md",
 "harmonica_eval/algorithms/dynamics.py": "FILE-203-v1.md",
 "harmonica_eval/host/__init__.py": "FILE-300-v1.md",
 "harmonica_eval/host/app.py": "FILE-301-v1.md",
 "harmonica_eval/cockpit/__init__.py": "FILE-400-v1.md",
 "harmonica_eval/cockpit/app.py": "FILE-401-v1.md",
}

def norm(s):
    return re.sub(r"\s+", "", s)

for src, bi in MAP.items():
    sp = ROOT / src
    bp = ROOT / ".spec/build" / bi
    tree = ast.parse(sp.read_text(encoding="utf-8"))
    skeleton = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            skeleton[node.name] = ast.unparse(node.args)
    text = bp.read_text(encoding="utf-8")
    print(f"\n===== {src}  <->  {bi} =====")
    print(f"  skeleton defs ({len(skeleton)}): {sorted(skeleton)}")
    # find backticked signature-looking strings in the BI
    quoted = set()
    for m in re.finditer(r"`([A-Za-z_][A-Za-z0-9_]*)\s*\(([^`()]*)\)\s*(?:->[^`]*)?`", text):
        quoted.add((m.group(1), norm(m.group(2))))
    for name in sorted(skeleton):
        sk = norm(skeleton[name])
        hits = sorted({q for (n, q) in quoted if n == name})
        if not hits:
            print(f"  [NO-QUOTED-SIG] {name}{skeleton[name]}")
        else:
            for h in hits:
                match = "OK " if h == sk else "MISMATCH"
                print(f"  [{match}] {name}: skeleton({sk!r}) vs BI({h!r})")
    # quoted names never defined in the skeleton
    missing = sorted({n for (n, q) in quoted if n not in skeleton and n not in dir(__builtins__)})
    print(f"  names quoted-with-parens not in skeleton: {missing}")
