"""P1 probe E: 空壳完整性 + FILE-104 门禁与 §4.4 派发表的字面冲突。只读。"""
import ast, pathlib, re
root = pathlib.Path('harmonica_eval')
print("== 1. 每个 .py 是否都是空壳（函数体全 raise NotImplementedError）==")
for p in sorted(root.rglob('*.py')):
    t = ast.parse(p.read_text(encoding='utf-8'))
    funcs = [n for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    stub = 0
    for f in funcs:
        body = [s for s in f.body if not isinstance(s, ast.Expr) or not isinstance(s.value, ast.Constant)]
        if len(body)==1 and isinstance(body[0], ast.Raise):
            r = body[0].exc
            nm = getattr(getattr(r,'func',None),'id',None) or getattr(getattr(r,'func',None),'attr',None)
            if nm == 'NotImplementedError': stub += 1
    print(f"  {str(p):46s} funcs={len(funcs):2d} stubs={stub:2d}")

print()
print("== 2. FILE-104 门禁 4（禁端口字面量） vs §4.4 要求 PRODUCER_DISPATCH 键=port_id ==")
s = pathlib.Path('.spec/build/FILE-104-v1.md').read_text(encoding='utf-8')
for ln, line in enumerate(s.splitlines(), 1):
    if 'no-hardcoded-port-ids' in line or '端口 ID 字面量' in line or 'PRODUCER_DISPATCH' in line:
        print(f"  L{ln}: {line.strip()[:150]}")

print()
print("== 3. 若按 §4.4 写死派发表，源码必然出现这些字面量 ==")
for lit in ['pcm.mapped','pcm.warped','pitch.','chroma.','rms.','notes.','warp_path.']:
    print(f"  '{lit}' 是 §4.4 派发表键的必然子串 -> 会命中门禁 4")
