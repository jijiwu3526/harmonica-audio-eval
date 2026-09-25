"""Probe 28: run FILE-100 §8 criterion A VERBATIM (lines 219-303 of the BI)."""
import ast, re, pathlib

FROZEN = ["ingest", "align", "features", "surface", "api"]
KEYS = ["FILE-ID:", "COMPONENT:", "SPEC:", "ROLE:", "INTENT:",
        "MUST:", "MUST NOT:", "INPUT:", "OUTPUT:", "BUILD-INSTRUCTION:"]

src = pathlib.Path("harmonica_eval/core/__init__.py").read_text(encoding="utf-8")

fails = []
def chk(label, fn):
    try:
        fn(); print(f"  PASS  {label}")
    except AssertionError as e:
        print(f"  FAIL  {label}  -> AssertionError: {e}")
        fails.append(label)
    except Exception as e:
        print(f"  ERR   {label}  -> {type(e).__name__}: {e}")
        fails.append(label)

chk("INV-100-9a len(src.splitlines())==53", lambda: (_ for _ in ()).throw(AssertionError(len(src.splitlines()))) if len(src.splitlines())!=53 else None)
chk("src.endswith('\"\"\"\\n')", lambda: (_ for _ in ()).throw(AssertionError(repr(src[-10:]))) if not src.endswith('"""\n') else None)
chk("not src.endswith('\\n\\n')", lambda: (_ for _ in ()).throw(AssertionError("trailing blank line")) if src.endswith('\n\n') else None)

tree = ast.parse(src)
chk("4 top-level nodes", lambda: (_ for _ in ()).throw(AssertionError(len(tree.body))) if len(tree.body)!=4 else None)
chk("body[0] is docstring Expr", lambda: None if (isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value,str)) else (_ for _ in ()).throw(AssertionError("no")))
chk("body[1] __future__ annotations", lambda: None if (isinstance(tree.body[1], ast.ImportFrom) and tree.body[1].module=="__future__" and tree.body[1].level==0 and [(a.name,a.asname) for a in tree.body[1].names]==[("annotations",None)]) else (_ for _ in ()).throw(AssertionError("no")))
chk("body[2] __all__ list of 5", lambda: None if (isinstance(tree.body[2],ast.Assign) and isinstance(tree.body[2].targets[0],ast.Name) and tree.body[2].targets[0].id=="__all__" and isinstance(tree.body[2].value,ast.List) and len(tree.body[2].value.elts)==5 and [e.value for e in tree.body[2].value.elts]==FROZEN) else (_ for _ in ()).throw(AssertionError([e.value for e in tree.body[2].value.elts])))
chk("body[3] bare string Expr", lambda: None if (isinstance(tree.body[3],ast.Expr) and isinstance(tree.body[3].value,ast.Constant) and isinstance(tree.body[3].value.value,str)) else (_ for _ in ()).throw(AssertionError("no")))
chk("import count == 1", lambda: (_ for _ in ()).throw(AssertionError(sum(1 for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))))) if sum(1 for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)))!=1 else None)
BANNED = {"FunctionDef","AsyncFunctionDef","ClassDef","If","Try","For","While","With","Lambda","Global","Nonlocal"}
chk("INV-100-1 zero logic", lambda: (_ for _ in ()).throw(AssertionError({type(n).__name__ for n in ast.walk(tree)} & BANNED)) if ({type(n).__name__ for n in ast.walk(tree)} & BANNED) else None)
chk("INV-100-3 no submodule import", lambda: [None for bad in FROZEN if f".{bad}" in src.replace("core."+bad,"")] and (_ for _ in ()).throw(AssertionError("leak")) or None)

doc = tree.body[0].value.value
chk("INV-100-8 doc non-empty", lambda: None if doc else (_ for _ in ()).throw(AssertionError("empty")))
chk("INV-100-8 len(doc.splitlines())==31", lambda: (_ for _ in ()).throw(AssertionError(len(doc.splitlines()))) if len(doc.splitlines())!=31 else None)
def keys_ok():
    pos=[doc.index(k) for k in KEYS]
    assert pos==sorted(pos) and len(set(pos))==10, pos
chk("INV-100-8 10 keys ordered", keys_ok)
chk("regex FILE-ID", lambda: None if re.search(r"^FILE-ID:\s+FILE-100\s*$",doc,re.M) else (_ for _ in ()).throw(AssertionError("no")))
chk("regex COMPONENT", lambda: None if re.search(r"^COMPONENT:\s+COMP-C2 Audio Core\s*$",doc,re.M) else (_ for _ in ()).throw(AssertionError("no")))
chk("regex OUTPUT __all__", lambda: None if re.search(r"^OUTPUT:\s*\n\s*__all__\s*$",doc,re.M) else (_ for _ in ()).throw(AssertionError("no")))

fac = tree.body[3].value.value
chk("facade core.<name> x5", lambda: [None for m in FROZEN if f"core.{m}" not in fac] and (_ for _ in ()).throw(AssertionError("missing")) or None)
chk("facade regex align", lambda: None if re.search(r"core\.align\s+→\s+warp_path",fac) else (_ for _ in ()).throw(AssertionError("no")))
chk("facade regex surface", lambda: None if re.search(r"core\.surface\s+→\s+pcm\.\*",fac) else (_ for _ in ()).throw(AssertionError("no")))
chk("facade regex api 7 ops", lambda: None if re.search(r"core\.api\s+→\s+CONTRACT-HOST-v1\s+的\s+7\s+个操作",fac) else (_ for _ in ()).throw(AssertionError("no")))
print()
print("FAILURES:", fails)
