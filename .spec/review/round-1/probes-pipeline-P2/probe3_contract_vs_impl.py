#!/usr/bin/env python3
"""P2-PROBE-3: 契约承诺 vs 实现承载体 —— 逐项对照。
(a) FILE-002 要写 metrics.json 的 series.n_points，contract.UiSeries 有没有这个字段？
(b) FILE-400 launch_cockpit 要求的 app 侧常量，cockpit/app.py 有没有？
(c) FILE-104 read() 对 warp_path 用 hop_length 换算时长上界，而 warp_path.hop_length==0
只读，不修改仓库。"""
from __future__ import annotations
import dataclasses, inspect, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
import harmonica_eval.contract as contract
import harmonica_eval.cockpit.app as capp
import harmonica_eval.profile as profile

print("=" * 72)
print("[A] FILE-002 §4.3 第 6 步要求 series 元素含 n_points（点数元信息）")
fields = [f.name for f in dataclasses.fields(contract.UiSeries)]
print("    contract.UiSeries 字段:", fields)
print("    'n_points' in fields ?", "n_points" in fields)
f002 = (REPO/".spec/build/FILE-002-v1.md").read_text(encoding="utf-8")
for ln in f002.splitlines():
    if "n_points" in ln:
        print("    FILE-002:", ln.strip()[:140])
print("    FILE-002 §5 明确禁止用 len(values) 替代 ->")
for ln in f002.splitlines():
    if "禁止" in ln and "len(values)" in ln:
        print("      ", ln.strip()[:140])

print()
print("[B] FILE-400 launch_cockpit 需要 app 侧的 6 个符号")
need = ["LOCAL_BIND_HOST","LOCAL_BIND_PORT","EXIT_OK","EXIT_STARTUP_FAILED","EXIT_SIGTERM","build_plots"]
for n in need:
    print(f"    {n:22s} app.py has? {hasattr(capp,n)}")
print("    app.py 实际公开常量:", [n for n in dir(capp) if n.isupper()])
print("    FILE-401 §4.2 冻结的 app 侧常量名:", "LOCAL_BIND_HOST / EXIT_OK / EXIT_START_FAILED / COMMAND_LABELS")
print("    -> 命名分叉: EXIT_STARTUP_FAILED(FILE-400) vs EXIT_START_FAILED(FILE-401/app.py)")

print()
print("[C] FILE-104 read() warp_path 时长上界 = (n-1)*hop/sr，warp_path.hop_length 实际值")
wp = profile.PORT_INDEX["warp_path"]
print("    warp_path.hop_length =", wp.hop_length, " dimensions =", tuple(wp.dimensions))
print("    -> upper = (n-1)*0/sr = 0.0；任何 t1>0 的 warp_path 读取都抛 ContractViolation")
print("    FILE-104 原文:")
f104 = (REPO/".spec/build/FILE-104-v1.md").read_text(encoding="utf-8")
for ln in f104.splitlines():
    if "warp_path` | 见下方" in ln or "(n - 1) * hop / sr" in ln:
        print("      ", ln.strip()[:150])

print()
print("[D] contract 承诺 'warp_path 时间窗按 reference_frame 换算' —— 需要 hop，但 hop=0")
c = (REPO/"harmonica_eval/contract.py").read_text(encoding="utf-8").splitlines()
for i,l in enumerate(c,1):
    if 453 <= i <= 456:
        print(f"      contract.py:{i}: {l.strip()}")
