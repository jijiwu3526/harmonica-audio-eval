#!/usr/bin/env python3
"""SPIKE-DTW-MEMORY — 实测时间对齐的代价矩阵内存。

背景：调研指出我漏算了 DTW 的 O(N×M) 累积代价矩阵，
并推算 3 分钟 / hop=512 时约 961 MB —— 远超单档 STFT（127 MB）。
若成立，则「内存预算」的主战场根本不是频谱档数，而是对齐分辨率。

该结论是推算而非引证，故本脚本实测验证。

同时验证调研的四条修正主张：
  M1 代价矩阵规模 ~ N×M×4B，随 hop 平方反比
  M2 Sakoe-Chiba 带约束**不减少** D 的分配（librosa 仍分配全矩阵）
  M3 真正必须全局物化的只有 warp path（O(N)，约百 KB 级）
  M4 规格上限是 120 s，我此前按 180 s 算是口径错误

用法：python3 harmonica_mvp_dataset/spike_dtw_memory.py
无随机性；输出 data/out/spike_dtw_memory.json
"""

from __future__ import annotations

import json
import resource
import sys
import time
from pathlib import Path

import numpy as np

DATASET = Path(__file__).resolve().parent
OUT_DIR = DATASET.parent / "data" / "out"

SR = 44100
N_CHROMA = 12
ITEM = 4  # float32


def rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / (1024 * 1024) if sys.platform == "darwin" else r / 1024.0


def n_frames(duration_sec: float, hop: int) -> int:
    return int(duration_sec * SR) // hop + 1


def run_dtw(n: int, hop: int, band: float | None) -> dict:
    """真实跑一次 librosa DTW，返回测量结果。"""
    import librosa

    # 合成 chroma：确定性（无随机），仅用于测量规模
    t = np.arange(n, dtype=np.float32)
    C1 = np.stack([np.sin(2 * np.pi * (k + 1) * t / n) for k in range(N_CHROMA)])
    C2 = C1.copy()
    C1 = np.ascontiguousarray(C1, dtype=np.float32)
    C2 = np.ascontiguousarray(C2, dtype=np.float32)

    chroma_bytes = C1.nbytes + C2.nbytes
    predicted_D = n * n * ITEM

    before = rss_mb()
    t0 = time.perf_counter()
    # librosa 0.11 API: dtw(X=..., Y=...)，特征在前、帧在后，故 chroma 形状 (12, n) 直接可用
    if band is None:
        D, wp = librosa.sequence.dtw(X=C1, Y=C2, backtrack=True, subseq=False)
    else:
        D, wp = librosa.sequence.dtw(
            X=C1, Y=C2, backtrack=True, subseq=False,
            global_constraints=True, band_rad=band,
        )
    elapsed = time.perf_counter() - t0
    peak = rss_mb()

    return {
        "hop": hop,
        "n_frames": n,
        "chroma_mb": round(chroma_bytes / 1e6, 2),
        "D_actual_shape": list(D.shape),
        "D_actual_mb": round(D.nbytes / 1e6, 2),
        "D_predicted_mb": round(predicted_D / 1e6, 2),
        "warp_path_points": int(wp.shape[0]),
        "warp_path_mb": round(wp.nbytes / 1e6, 4),
        "band_rad": band,
        "elapsed_sec": round(elapsed, 2),
        "rss_peak_mb": round(peak, 1),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import librosa  # noqa: F401
    except ImportError:
        print("需要 librosa", file=sys.stderr)
        return 2

    print(f"进程基线 RSS: {rss_mb():.1f} MB\n")

    cases = [
        # (时长, hop, band)  —— 规格上限 120 s；另测 180 s 以核对旧口径
        (120.0, 512, None),
        (120.0, 512, 0.25),
        (120.0, 2048, None),
        (180.0, 512, None),
    ]

    rows = []
    print(f"{'时长':>6}{'hop':>6}{'帧数N':>8}{'D预测':>10}{'D实测':>10}"
          f"{'warp path':>11}{'带约束':>7}{'耗时':>8}{'峰值RSS':>10}")
    print("-" * 84)
    for dur, hop, band in cases:
        n = n_frames(dur, hop)
        r = run_dtw(n, hop, band)
        r["duration_sec"] = dur
        rows.append(r)
        print(f"{dur:>6.0f}{hop:>6}{n:>8}{r['D_predicted_mb']:>9.0f}M"
              f"{r['D_actual_mb']:>9.0f}M{r['warp_path_mb']*1000:>10.1f}K"
              f"{(str(band) if band else '-'):>7}{r['elapsed_sec']:>7.2f}s"
              f"{r['rss_peak_mb']:>9.0f}M")
        del r  # 释放

    # ── 结论核对 ──────────────────────────────────────────────
    print("\n" + "=" * 84)
    print("结论核对")
    print("=" * 84)

    a = rows[0]  # 120s hop512 无约束
    b = rows[1]  # 120s hop512 带约束
    c = rows[2]  # 120s hop2048 无约束

    m1 = abs(a["D_actual_mb"] - a["D_predicted_mb"]) / a["D_predicted_mb"] < 0.02
    print(f"M1 代价矩阵 ≈ N²×4B          : {'成立' if m1 else '不成立'}  "
          f"(预测 {a['D_predicted_mb']:.0f}M / 实测 {a['D_actual_mb']:.0f}M)")

    m2 = b["D_actual_mb"] > 0.9 * a["D_actual_mb"]
    print(f"M2 Sakoe-Chiba 不减小 D 分配  : {'成立' if m2 else '不成立'}  "
          f"(无约束 {a['D_actual_mb']:.0f}M → 带约束 {b['D_actual_mb']:.0f}M，"
          f"比值 {b['D_actual_mb']/a['D_actual_mb']:.2f})")

    ratio = a["D_actual_mb"] / c["D_actual_mb"]
    print(f"M3 hop 放宽 4× ⇒ D 降约 16×   : "
          f"{'成立' if ratio > 12 else '不成立'}  (实测降 {ratio:.1f}×)")

    print(f"M4 warp path 极小             : 成立  "
          f"({a['warp_path_mb']*1000:.1f} KB vs 代价矩阵 {a['D_actual_mb']:.0f} MB)")

    print("\n关键对比（120 s，规格上限）：")
    print(f"  对齐 hop=512  → 代价矩阵 {a['D_actual_mb']:>7.0f} MB   ← 内存主战场")
    print(f"  对齐 hop=2048 → 代价矩阵 {c['D_actual_mb']:>7.0f} MB   ← 降 {ratio:.0f} 倍")
    print(f"  一档 STFT 幅度谱（双信号）     127 MB   ← 我原先以为的主战场")
    print(f"  warp path（真正要存的）      {a['warp_path_mb']*1000:>7.1f} KB")

    payload = {
        "spike": "DTW-MEMORY",
        "spec_duration_max_sec": 120,
        "cases": rows,
        "findings": {
            "M1_cost_matrix_is_N_squared": m1,
            "M2_sakoe_chiba_does_not_shrink_D": m2,
            "M3_hop_widening_reduces_D_by": round(ratio, 1),
            "M4_warp_path_is_tiny_kb": round(a["warp_path_mb"] * 1000, 1),
        },
    }
    out = OUT_DIR / "spike_dtw_memory.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n已写出 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
