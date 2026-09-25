"""探针 5: FILE-401 要求保留 9 段 section 分隔线与全部 docstring；数一数 app.py 的分隔线"""
import pathlib, re
src = pathlib.Path("harmonica_eval/cockpit/app.py").read_text(encoding="utf-8")
seps = re.findall(r"# ═{20,}\n# [一二三四五六七八九十]+ · [^\n]*\n# ═{20,}", src)
print("『═══ 标题 ═══』完整三行式分隔线数量:", len(seps))
open_style = re.findall(r"# ═{20,}\n# [^\n]+\n", src)
print("『═══ + 标题』(下行无封底)数量:", len(open_style))
for s in open_style: print("   ", s.strip().split("\n")[-1][:50])
# docstring 数量(含模块 docstring)
import ast
tree = ast.parse(src)
n_doc = 0
for node in ast.walk(tree):
    if isinstance(node, (ast.Module, ast.FunctionDef)):
        if ast.get_docstring(node): n_doc += 1
print("模块+函数 docstring 数:", n_doc, "(函数数:", len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]), ")")
