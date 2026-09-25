"""Probe 27: run FILE-100 §8's docstring invariant assertion VERBATIM."""
import ast, re, pathlib
src = pathlib.Path("harmonica_eval/core/__init__.py").read_text()
tree = ast.parse(src)
doc = tree.body[0].value.value
print("assert doc ->", bool(doc))
print("len(doc.splitlines()) =", len(doc.splitlines()))
try:
    assert len(doc.splitlines()) == 31, len(doc.splitlines())
    print("PASS len==31")
except AssertionError as e:
    print("FAIL AssertionError:", e)
    print("  FILE-100:279 requires exactly 31; actual is", len(doc.splitlines()))
    print("  FILE-100:132 states the same invariant.")
    print("  FILE-100:436 freeze table: 'docstring 行数 | 31 | 行 1–31'")
    print("  Reality: AST node spans lines 1-31 (end_lineno=31), so the SOURCE")
    print("  occupies 31 lines, but the docstring VALUE has 30 lines")
    print("  (opening ''' and closing ''' are delimiters, not content).")
    print("  => the two readings are conflated in the BI; the assertion as written fails.")
