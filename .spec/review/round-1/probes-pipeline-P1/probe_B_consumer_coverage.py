"""P1 probe B: 消费段 — required_ports 是否都存在；端口是否都有消费者。只读。"""
import sys; sys.path.insert(0, ".")
from harmonica_eval import profile
from harmonica_eval.algorithms import ALGORITHMS

port_ids = set(profile.PORT_INDEX)
print("== 每个算法的 required_ports 是否都在权威清单里 ==")
consumed = set()
for a in ALGORITHMS:
    miss = [p for p in a.required_ports if p not in port_ids]
    print(f"  {a.algorithm_id:9s} required={tuple(a.required_ports)}")
    print(f"            missing_from_profile={miss}")
    consumed |= set(a.required_ports)

print()
print("== 端口 -> 消费者 / 生产者 ==")
for p in profile.PORTS:
    cons = [a.algorithm_id for a in ALGORITHMS if p.port_id in a.required_ports]
    print(f"  {p.port_id:26s} produced_by={p.produced_by:14s} consumers={cons if cons else 'NONE'}")

print()
print("== 无算法消费者的端口 ==")
print("  ", sorted(port_ids - consumed))
