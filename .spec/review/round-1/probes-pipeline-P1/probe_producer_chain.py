#!/usr/bin/env python3
"""probe_producer_chain.py — 生产段（P1）审查探针。

只读探针：不修改仓库任何既有文件。逐条验证「谁生产端口」这一段的
可机械判定事实。每条输出 PASS / FAIL / SKIPPED。

运行：
    cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
    python3 .spec/review/round-1/probes-pipeline-P1/probe_producer_chain.py
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
import sys

sys.path.insert(0, str(REPO))

import harmonica_eval.profile as prof
from harmonica_eval import contract as c

RESULTS: list[tuple[str, str, str]] = []


def rec(tag: str, status: str, detail: str) -> None:
    RESULTS.append((tag, status, detail))
    print(f"[{status}] {tag}\n        {detail}")


# ── P1-01 · produced_by 只出现 3 个模块 ───────────────────────────────
producers = sorted({s.produced_by for s in prof.PORTS})
rec(
    "P1-01 produced_by 取值集合",
    "PASS" if producers == ["core.align", "core.features", "core.surface"] else "FAIL",
    f"实际 = {producers}",
)

# ── P1-02 · 生产者模块是否是可调用的 4 参数生成者 ──────────────────────
# FILE-104 §4.4 步骤 3/4 冻结：produced_by 指名的模块，其可调用对象
# 接收 4 个位置参数 (reference, practice, sample_rate, warp_path)。
want = ("reference", "practice", "sample_rate", "warp_path")
four_arg: list[str] = []
for pb in producers:
    try:
        mod = importlib.import_module("harmonica_eval." + pb)
    except Exception as exc:  # noqa: BLE001
        rec(f"P1-02 import {pb}", "FAIL", f"import 失败: {exc!r}")
        continue
    if callable(mod):
        four_arg.append(f"{pb}（模块本身可调用）")
    for name, obj in vars(mod).items():
        if name.startswith("_"):
            continue
        if inspect.isfunction(obj) and obj.__module__ == mod.__name__:
            sig = inspect.signature(obj)
            names = tuple(p.name for p in sig.parameters.values())
            if names == want:
                four_arg.append(f"{pb}.{name}")
rec(
    "P1-02 produced_by 指名的 4 参数生成者",
    "PASS" if four_arg else "FAIL",
    f"找到 {four_arg or '无'}；但 profile 声明 12 个端口需要 3 个生产者模块",
)

# ── P1-03 · pcm.warped.practice 的生产者 ─────────────────────────────
# profile 声明 produced_by="core.surface"；FILE-104 §7 第 738 行明文
# 「不做 WARPED 轴的 PCM 重采样 —— 在 produced_by 指名的模块里」，
# 而 core.surface 的公开符号里没有任何重采样/时间归一化函数。
surf = importlib.import_module("harmonica_eval.core.surface")
surf_syms = [n for n in vars(surf) if not n.startswith("_")]
stretch = [n for n in surf_syms if any(k in n.lower() for k in ("warp", "resample", "stretch", "map"))]
rec(
    "P1-03 pcm.warped.practice 的生产者函数存在性",
    "PASS" if stretch else "FAIL",
    f"port 声明 produced_by='core.surface'；core.surface 公开符号 = {surf_syms}；"
    f"疑似生产函数 = {stretch or '无'}",
)

# ── P1-04 · PortSpec 是否声明 sample_rate（INV-104-12 引用它）────────
has_sr = hasattr(prof.PortSpec, "sample_rate") or hasattr(prof.PORTS[0], "sample_rate")
rec(
    "P1-04 PortSpec.sample_rate 属性存在性",
    "PASS" if has_sr else "FAIL",
    f"PortSpec 字段 = {list(prof.PortSpec.__dataclass_fields__)}；"
    f"FILE-104 INV-104-12 断言 profile.PORT_INDEX[p].sample_rate",
)

# ── P1-05 · FILE-200 C2：`port in PORTS` 成员测试 ────────────────────
# PORTS 是 tuple[PortSpec, ...]；对端名字符串做 in 得 False。
all_ids = [p.port_id for p in prof.PORTS]
member_ok = all((pid in prof.PORTS) for pid in all_ids)
rec(
    "P1-05 `port in PORTS`（FILE-200 C2 冻结口径）",
    "PASS" if member_ok else "FAIL",
    f"12 个 port_id 全部 `in PORTS` = {member_ok}；"
    f"PORTS 类型={type(prof.PORTS).__name__}，元素类型={type(prof.PORTS[0]).__name__}",
)

# ── P1-06 · ingest 入口签名 vs FILE-105 调用实参 ─────────────────────
ing = importlib.import_module("harmonica_eval.core.ingest")
sig = inspect.signature(ing.ingest)
rec(
    "P1-06 ingest 签名 vs FILE-105 三实参调用",
    "PASS" if len(sig.parameters) >= 3 else "FAIL",
    f"实际签名 ingest{sig}（1 个参数）；FILE-105:149 以 "
    f"(reference_uri, practice_uri, profile_version) 三个实参调用",
)

# ── P1-07 · align 的调用者 ───────────────────────────────────────────
callers: list[str] = []
for py in (REPO / "harmonica_eval").rglob("*.py"):
    if "__pycache__" in str(py):
        continue
    src = py.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id == "align":
                callers.append(str(py.relative_to(REPO)))
            if isinstance(f, ast.Attribute) and f.attr == "align":
                callers.append(str(py.relative_to(REPO)))
# align.py 自己的 docstring 提及不算调用者
real = [x for x in callers if x != "harmonica_eval/core/align.py"]
rec(
    "P1-07 align() 的调用者",
    "PASS" if real else "FAIL",
    f"除 align.py 自身外的调用点 = {real or '无'}；"
    f"FILE-105:150 只说「调用 align 的入口」，未冻结其签名",
)

# ── P1-08 · warp_path 的消费者 ──────────────────────────────────────
import harmonica_eval.algorithms as algos

consumed: dict[str, list[str]] = {}
for a in algos.ALGORITHMS:
    for p in a.required_ports:
        consumed.setdefault(p, []).append(a.algorithm_id)
orphan = [s.port_id for s in prof.PORTS if s.port_id not in consumed]
rec(
    "P1-08 无算法消费者的端口",
    "PASS" if not orphan else "FAIL",
    f"未被任何算法 required_ports 声明的端口 = {orphan}",
)

# ── P1-09 · AlgorithmResultEnvelope.status 取值域 ───────────────────
valid = {"OK", "FAILED", "INCOMPATIBLE"}
f201 = (REPO / ".spec/build/FILE-201-v1.md").read_text(encoding="utf-8")
uses_succeeded = '"SUCCEEDED"' in f201 or "'SUCCEEDED'" in f201
rec(
    "P1-09 FILE-201 的 status 取值 vs 契约冻结三元",
    "PASS" if not uses_succeeded else "FAIL",
    f"契约取值域={sorted(valid)}（contract.py:380）；"
    f"FILE-201-v1.md 出现 'SUCCEEDED' = {uses_succeeded}",
)

# ── P1-10 · AlgorithmResultEnvelope 是否有 `error` 字段 ─────────────
env_fields = list(c.AlgorithmResultEnvelope.__dataclass_fields__)
rec(
    "P1-10 FILE-203 使用的 envelope.error= 字段",
    "PASS" if "error" in env_fields else "FAIL",
    f"契约字段 = {env_fields}；FILE-203-v1.md:130/139 构造 "
    f"AlgorithmResultEnvelope(status='FAILED', error=...)",
)

# ── P1-11 · 算法如何访问端口（surface.rms.reference 属性 vs read()）──
contract_ops = [n for n in vars(c.AlgorithmDataContract) if not n.startswith("_")]
rec(
    "P1-11 FILE-203 `surface.rms.reference` 属性式访问",
    "PASS" if "rms" in contract_ops else "FAIL",
    f"契约只有 {contract_ops} 两个操作；FILE-203-v1.md:118-121 用 "
    f"surface.rms.reference / surface.notes.practice 属性式访问",
)

# ── P1-12 · harmonica_eval.exceptions 模块是否存在 ──────────────────
rec(
    "P1-12 FILE-102 引用的 harmonica_eval.exceptions",
    "PASS" if (REPO / "harmonica_eval/exceptions.py").exists() else "FAIL",
    f"{REPO / 'harmonica_eval/exceptions.py'} 存在 = "
    f"{(REPO / 'harmonica_eval/exceptions.py').exists()}；"
    f"FILE-102 第 42/170 行 import 它",
)

# ── P1-13 · contract 是否导出「会话驱动符号」 ───────────────────────
driver = [n for n in vars(c) if any(k in n.lower() for k in ("driver", "session_driver", "headless"))]
rec(
    "P1-13 FILE-002 依赖的 contract『会话驱动符号』",
    "PASS" if driver else "FAIL",
    f"contract 中的疑似会话驱动符号 = {driver or '无'}；"
    f"FILE-002 §3 允许 import『.contract 及该模块导出的会话驱动符号』",
)

# ── P1-14 · SPEC §3 承诺的指标是否有生产者 ──────────────────────────
spec_metrics = ["tempo_ratio", "mean_abs_warp_sec", "pitch_cents_mae"]
found = {}
for m in spec_metrics:
    hits = []
    for py in (REPO / "harmonica_eval").rglob("*.py"):
        if "__pycache__" in str(py) or m in py.read_text(encoding="utf-8"):
            hits.append(str(py.relative_to(REPO)))
    found[m] = hits
rec(
    "P1-14 SPEC §3 指标的生产者",
    "PASS" if all(found.values()) else "FAIL",
    f"{found}",
)

print()
print("=" * 72)
fail = [r for r in RESULTS if r[1] == "FAIL"]
print(f"合计 {len(RESULTS)} 条：PASS {len(RESULTS) - len(fail)} · FAIL {len(fail)}")
for tag, _, _ in fail:
    print("  FAIL:", tag)
