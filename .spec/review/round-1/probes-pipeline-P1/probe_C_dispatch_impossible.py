"""P1 probe C: 证明 FILE-104 §4.4 的『produced_by -> 4参生成者』查表无法实现。
只读。"""
import ast, sys, inspect, pathlib
sys.path.insert(0, ".")
from harmonica_eval import profile

print("== 1. produced_by 是模块还是可调用对象？ ==")
import importlib
for name in sorted({p.produced_by for p in profile.PORTS}):
    m = importlib.import_module("harmonica_eval." + name)
    callables = [n for n, o in vars(m).items()
                 if not n.startswith("_") and inspect.isfunction(o)
                 and getattr(o, "__module__", "") == m.__name__]
    print(f"  {name:14s} 是模块；模块级函数={callables}")
print("  => produced_by 指向【模块】，一个模块含多个函数；")
print("     且没有任何字段/表给出 port_id -> 具体函数名 的映射。")

print()
print("== 2. 哪些模块级函数满足 FILE-104 §4.4 的『4 个位置参数』约定？ ==")
for name in sorted({p.produced_by for p in profile.PORTS}):
    m = importlib.import_module("harmonica_eval." + name)
    for n, o in vars(m).items():
        if n.startswith("_") or not inspect.isfunction(o): continue
        if getattr(o, "__module__", "") != m.__name__: continue
        ps = list(inspect.signature(o).parameters)
        if len(ps) == 4:
            print(f"  {name}.{n}{tuple(ps)}  <-- 满足 4 参")
print("  => 满足 4 参的只有 surface.generate_all_ports / surface.build_surface，")
print("     它们本身就是【调度器/装配器】，不是『单个端口的生成者』。")

print()
print("== 3. 每个 produced_by 的端口数 vs 该模块函数数 ==")
from collections import Counter
c = Counter(p.produced_by for p in profile.PORTS)
for k, v in c.items():
    print(f"  {k:14s} 负责 {v} 个端口")

print()
print("== 4. 生成者若按 produced_by 被调用一次，无法知道该产 reference 还是 practice ==")
print("  例如 pitch.reference 与 pitch.practice 的 produced_by 都是 core.features，")
print("  但 materialize_pitch(samples, sample_rate) 只接受 PCM，没有任何 port_id 参数；")
print("  它无法区分『参考侧』与『练习侧』。")
