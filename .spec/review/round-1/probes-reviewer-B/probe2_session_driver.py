"""探针 2: FILE-002 要求从 .contract 导入'会话驱动符号'，contract.py 是否真的导出?"""
import ast, pathlib
src = pathlib.Path("harmonica_eval/contract.py").read_text(encoding="utf-8")
tree = ast.parse(src)
all_node = None
for node in tree.body:
    if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', None) == '__all__':
        all_node = node
exported = [e.value for e in all_node.value.elts]
print("contract.__all__ 数量:", len(exported))
print("exported =", exported)
candidates = [n for n in exported if any(k in n.lower() for k in ("session","driver","create","headless","hostapp","build_default","run"))]
print("可作'会话驱动面'的候选:", candidates)
