#!/usr/bin/env python3
"""probe_dispatch_gap.py — 生产段的**调度层**审查探针。

问题：FILE-104 §4.4 冻结的生成约定是「每个端口的生成者由
`PortSpec.produced_by` 指名；生成者可调用对象接收 4 个位置参数
`(reference, practice, sample_rate, warp_path)` 并返回一个 ndarray」。

本探针检查：这三条约束在**现有代码 + 全部 Build Instruction** 下
是否足以唯一确定「谁生产哪个端口」。

只读，不修改任何文件。
"""

from __future__ import annotations

import importlib
import inspect
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

import harmonica_eval.profile as prof

WANT = ("reference", "practice", "sample_rate", "warp_path")


def callables_of(modpath: str):
    mod = importlib.import_module(modpath)
    out = {}
    if callable(mod):
        out["<module>"] = inspect.signature(mod)
    for name, obj in vars(mod).items():
        if name.startswith("_"):
            continue
        if inspect.isfunction(obj) and obj.__module__ == mod.__name__:
            out[name] = inspect.signature(obj)
    return out


print("=" * 72)
print("① 每个端口 —— produced_by 指名的模块里，有没有唯一一个 4 参生成者？")
print("=" * 72)

for spec in prof.PORTS:
    modpath = "harmonica_eval." + spec.produced_by
    try:
        sigs = callables_of(modpath)
    except Exception as exc:  # noqa: BLE001
        print(f"{spec.port_id:26s} {spec.produced_by:14s} import 失败: {exc!r}")
        continue
    matching = [
        n for n, s in sigs.items()
        if tuple(p.name for p in s.parameters.values()) == WANT
    ]
    print(
        f"{spec.port_id:26s} produced_by={spec.produced_by:14s} "
        f"4 参生成者={matching or '无'}"
    )

print()
print("=" * 72)
print("② profile 是否给出「端口 → 具体函数」的映射？")
print("=" * 72)
print("PortSpec 字段 =", list(prof.PortSpec.__dataclass_fields__))
print("ProfSpec 是否含函数名/入口字段 =", any(
    k in prof.PortSpec.__dataclass_fields__
    for k in ("producer", "entry", "generator", "callable", "func")
))
pb = (REPO / ".spec/build/FILE-104-v1.md").read_text(encoding="utf-8")
print("FILE-104 出现 'import_module' 次数 =", pb.count("import_module"))
print("FILE-104 是否给出端口→函数名表 =", bool(
    re.search(r"\|\s*`?\w+\.\w+`?\s*\|[^|]*\|\s*`?[a-z_]+\.[a-z_]+\.[a-z_]+`?\s*\|", pb)
))

print()
print("=" * 72)
print("③ 自指风险：pcm.* 的 produced_by='core.surface' 是谁？")
print("=" * 72)
surf = importlib.import_module("harmonica_eval.core.surface")
print("core.surface 的 4 参可调用者 =", [
    n for n, o in vars(surf).items()
    if inspect.isfunction(o) and o.__module__ == surf.__name__
    and tuple(p.name for p in inspect.signature(o).parameters.values()) == WANT
])
print("→ generate_all_ports 自己就在该列表里。它被规定为『汇总者』：")
print("   FILE-104 §4.4 步骤 3：「实现不得在本文件内另写特征提取代码；只做一次查表调用」")
print("   FILE-104 §4.4 步骤 4：「生成者可调用对象接收位置参数 4 个」")
print("   若 pcm.* 的生成者 = core.surface 的 4 参函数，则 generate_all_ports 调用自身 → 无限递归。")

print()
print("=" * 72)
print("④ 4 参约定能否驱动 features.py 的 4 个函数？")
print("=" * 72)
feat = importlib.import_module("harmonica_eval.core.features")
for n, o in vars(feat).items():
    if inspect.isfunction(o) and o.__module__ == feat.__name__:
        print(f"  features.{n}{inspect.signature(o)}")
print("  约定要求 (reference, practice, sample_rate, warp_path)：无一匹配。")
print("  且 notes.* 需要先有 pitch/rms 中间量、并区分 reference/practice 两侧，")
print("  但 4 参约定既无 port_id 也无侧别参数 → 无法区分生产目标是哪一侧。")

print()
print("=" * 72)
print("⑤ 谁生产 pcm.mapped.reference 与 pcm.mapped.practice 的区别？")
print("=" * 72)
print("profile: pcm.mapped.reference + pcm.mapped.practice 均为 produced_by='core.surface'")
print("FILE-104 §4.7 步骤 7：「对 ports.values() 中每个 ndarray 调用 seal(...)」")
print("→ 两个端口的生成者签名完全相同，返回值无法按 port_id 区分。")
print("→ 唯一能让二者不同的信息（哪一侧）不在 4 参参数里。")
