"""探针 1: FILE-400/401 模引用的 app 侧常量与符号是否存在于空壳 app.py"""
import ast, pathlib
src = pathlib.Path("harmonica_eval/cockpit/app.py").read_text(encoding="utf-8")
tree = ast.parse(src)
names, fns = set(), set()
for node in tree.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name):
                names.add(t.id)
    if isinstance(node, ast.FunctionDef):
        fns.add(node.name)
required_by_400 = ["LOCAL_BIND_HOST","LOCAL_BIND_PORT","EXIT_OK","EXIT_STARTUP_FAILED","EXIT_SIGTERM","POLL_INTERVAL_MS"]
print("app.py 模块级赋值名:", sorted(names))
print("FILE-400 §3/§4.2 要求 app 侧存在但缺失:", [n for n in required_by_400 if n not in names])
required_by_401 = ["COMMAND_LABELS","run_local_ui","render_status","render_scalars","render_series_plot",
                   "render_progress","render_error","build_plots","build_command","solicit_asset_uri","submit_command"]
print("FILE-401 14 公开符号缺失:", [n for n in required_by_401 if n not in names and n not in fns])
allu = None
m = [n for n in ast.walk(tree) if isinstance(n, ast.Assign) and getattr(n.targets[0],'id',None)=='__all__']
print("app.__all__ 当前项数:", len(m[0].value.elts) if m else None)
