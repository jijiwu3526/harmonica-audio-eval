#!/usr/bin/env python3
"""P2-PROBE-4: 端口的生产者/消费者两侧是否都有人。
- 生产者侧: profile.produced_by 指向的模块里有没有对应的生产函数（见 probe1）
- 消费者侧: ALGORITHMS.required_ports 覆盖了哪些端口
只读，不修改仓库。"""
from __future__ import annotations
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
import harmonica_eval.profile as profile
import harmonica_eval.algorithms as alg

allp = [s.port_id for s in profile.PORTS]
consumed = set()
for spec in alg.ALGORITHMS:
    consumed |= set(spec.required_ports)

print("=" * 72)
print("端口清单（12）与两侧归属：")
print(f"{'port_id':28s} {'produced_by':14s} 被算法消费?")
for pid in allp:
    s = profile.PORT_INDEX[pid]
    print(f"  {pid:26s} {s.produced_by:14s} {'YES' if pid in consumed else 'no '}")
print()
print("无算法消费（须有 b/c 类理由）:", [p for p in allp if p not in consumed])
print()
print("ALGORITHMS.required_ports 里但不在 PORTS 里的（悬空声明）:",
      sorted(consumed - set(allp)) or "(无)")
print()
print("消费者侧每个算法的入口:")
for spec in alg.ALGORITHMS:
    print(f"  {spec.algorithm_id:10s} entry={spec.entry.__module__}.{spec.entry.__name__} required={list(spec.required_ports)}")
