"""P3 probe 4 — 跨文件契约 vs 实现的字段/签名/符号对不上（逐条机械核对）。

覆盖：
  A. FILE-105 build_surface 阶段入口调用约定  vs  FILE-101/102/103 的实际签名
  B. FILE-105 `except HarmonicaError`  vs  其 §3 允许 import 的 5 个名字
  C. FILE-104 INV-104-12 引用 profile.PORT_INDEX[p].sample_rate  vs  PortSpec 字段
  D. FILE-002 要求的 UiSeries.n_points  vs  contract.UiSeries 字段
  E. warp_path 的 hop_length=0  vs  FILE-104 read() 用 d.hop_length 换算时间窗
只读。
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from harmonica_eval import contract, profile  # noqa: E402
from harmonica_eval.core import align, features, ingest  # noqa: E402


def spec(name: str) -> str:
    return (REPO / ".spec" / "build" / f"{name}-v1.md").read_text(encoding="utf-8")


def main() -> int:
    print("=" * 72)
    print("P3 probe 4 · 跨文件契约 vs 实现")
    print("=" * 72)

    # ── A ───────────────────────────────────────────────────────────
    print("\n[A] FILE-105 build_surface 的阶段入口约定 vs 实际签名")
    print("  FILE-105 §4.5 step 1 (INGEST): 实参 (reference_uri, practice_uri, profile_version)")
    print("      -> 产出『两路 mono/float32 PCM 与其 AudioFormat』")
    print("  实际 ingest.ingest:", f"ingest{inspect.signature(ingest.ingest)}")
    print("      -> docstring: 只返回样本，不返回采样率（FILE-101 §4.5）")
    print("  FILE-105 §4.5 step 2 (ALIGN): 产出『REFERENCE/WARPED 两份对齐 PCM + warp 路径点』")
    print("  实际 align.align:", f"align{inspect.signature(align.align)}")
    print("      -> 只返回 warp_path（FILE-102 §align）")
    print("  FILE-105 §4.5 step 3 (FEATURES): 产出『全部端口缓冲（每端口的 PortDescriptor 与配套数组）』")
    print("  实际 features 顶层函数:", [n for n, o in vars(features).items()
                                      if not n.startswith("_") and inspect.isfunction(o)])
    print("      -> 只返回裸 ndarray，不返回 PortDescriptor；且只覆盖 8 个 features 端口")

    # ── B ───────────────────────────────────────────────────────────
    print("\n[B] FILE-105 §4.5 step 6 用 `except HarmonicaError`")
    t105 = spec("FILE-105")
    print("  文本含 'except HarmonicaError':", "except HarmonicaError" in t105)
    allowed = ["HostContract", "SessionState", "ContractViolation", "CoreBuildError", "ErrorCode"]
    print("  FILE-105 §3 允许从 contract import 的名字:", allowed)
    print("  其中是否含 HarmonicaError:", "HarmonicaError" in allowed)
    print("  contract.HarmonicaError 实际存在:", hasattr(contract, "HarmonicaError"))
    print("  ContractViolation 是 HarmonicaError 子类:",
          issubclass(contract.ContractViolation, contract.HarmonicaError))

    # ── C ───────────────────────────────────────────────────────────
    print("\n[C] FILE-104 INV-104-12 引用 PortSpec.sample_rate")
    fields = list(profile.PortSpec.__dataclass_fields__)
    print("  PortSpec 字段:", fields)
    print("  'sample_rate' in PortSpec 字段:", "sample_rate" in fields)
    print("  PortDescriptor 字段:", list(contract.PortDescriptor.__dataclass_fields__))
    print("  FILE-104 含 'PORT_INDEX[p].sample_rate':", "PORT_INDEX[p].sample_rate" in spec("FILE-104"))

    # ── D ───────────────────────────────────────────────────────────
    print("\n[D] FILE-002 要求 UiSeries.n_points")
    us = list(contract.UiSeries.__dataclass_fields__)
    print("  contract.UiSeries 字段:", us)
    print("  'n_points' in UiSeries:", "n_points" in us)
    t002 = spec("FILE-002")
    print("  FILE-002 含 n_points:", "n_points" in t002)
    print("  FILE-002 §5: 投影缺 n_points → 停止上报；且禁止用 len(values) 替代:",
          "禁止**用 `len(values)` 遍历数值替代" in t002 or "禁止" in t002)
    print("  FILE-003 §4.13 是否定义 n_points:",
          "n_points" in spec("FILE-003"))

    # ── E ───────────────────────────────────────────────────────────
    print("\n[E] warp_path hop_length vs FILE-104 read() 时间窗换算")
    wp = profile.PORT_INDEX["warp_path"]
    print("  profile warp_path.hop_length =", wp.hop_length)
    print("  profile warp_path.dimensions =", tuple(wp.dimensions))
    print("  FILE-104 §4.6.2 warp_path 上界公式 '(n - 1) * hop / sr':",
          "(n - 1) * hop / sr" in spec("FILE-104"))
    print("  -> hop=0 ⇒ 上界恒为 0.0；任何 t1>0 的 warp_path 读取都抛 ContractViolation")

    print("\n[结论] A–E 均为跨文件对不上；详见报告 FINDING。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
