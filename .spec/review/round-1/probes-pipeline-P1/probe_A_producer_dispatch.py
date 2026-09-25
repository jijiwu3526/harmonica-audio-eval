"""P1 probe A: 生产段 — produced_by 指向的模块/可调用对象是否存在、签名是否满足
FILE-104 §4.4 的 4 参调用约定。只读，不修改仓库。"""
import importlib, inspect, sys
sys.path.insert(0, ".")
from harmonica_eval import profile

print("== PORTS: produced_by -> 模块是否可解析 ==")
mods = {}
for p in profile.PORTS:
    if p.produced_by not in mods:
        try:
            m = importlib.import_module("harmonica_eval." + p.produced_by)
            mods[p.produced_by] = m
        except Exception as e:
            mods[p.produced_by] = e
    m = mods[p.produced_by]
    status = "OK module" if not isinstance(m, Exception) else f"IMPORT-FAIL {m!r}"
    print(f"  {p.port_id:26s} produced_by={p.produced_by:14s} {status}")

print()
print("== 该模块里有哪些『可作为生成者』的公开可调用对象（含 4 参约定检查）==")
for name, m in mods.items():
    if isinstance(m, Exception):
        continue
    print(f"-- {name} ({m.__file__})")
    found = False
    for fname, obj in vars(m).items():
        if fname.startswith("_"):
            continue
        if inspect.isfunction(obj) and getattr(obj, "__module__", "") == m.__name__:
            try:
                sig = str(inspect.signature(obj))
            except Exception as e:
                sig = f"<{e}>"
            ok4 = False
            try:
                ps = list(inspect.signature(obj).parameters.values())
                ok4 = len(ps) == 4
            except Exception:
                pass
            print(f"     {fname}{sig}   4-arg-convention={'YES' if ok4 else 'NO'}")
            found = True
    if not found:
        print("     (无模块级函数 —— 该模块无法充当 FILE-104 §4.4 的『生成者』)")
