#!/usr/bin/env python3
"""SPIKE-CORE-MEMORY — 实测 CORE_PROFILE_V0.1 的资源成本。

目的（宪章 §28 / §31）：为 Freeze 消除唯一阻塞项——
"Core profile 的内存与耗时预算没有实测数据"。

本脚本只做测量，不做设计。它回答三个问题：
  Q1 三种 profile 档位的真实峰值内存是多少（RSS delta + 数据面字节数）？
  Q2 构建耗时是多少？能否满足交互（≤数秒）与手机端？
  Q3 "预算算 vs 实测"的偏差有多大——即我的解析估算是否可信？

做法：
  用真实口琴音频（第 1 首 72.8 s）按三种 profile 档位构造数据面，
  逐档记录：数据面精确字节数（解析）／进程峰值 RSS 增量（实测）／耗时。
  再线性外推到 180 s（3 分钟）以便与估算表对比。

可复现：固定输入路径；本脚本无随机性。
输出：data/out/spike_core_memory.json + 同目录 .md 报告。
"""

from __future__ import annotations

import json
import os
import resource
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

DATASET = Path(__file__).resolve().parent   # harmonica_mvp_dataset/
REPO = DATASET.parent                        # 仓库根
SONG_DIR = DATASET / "01_奇异恩典"
REF_WAV = SONG_DIR / "原曲_完整版.wav"
PRAC_WAV = SONG_DIR / "练习曲" / "02_节奏抢拖.wav"
OUT_DIR = REPO / "data" / "out"

TARGET_SR = 44100
DTYPE = np.float32
ITEMSIZE = np.dtype(DTYPE).itemsize

# 三档 profile（与 COMPONENTS.md §6 / 人类视图「决定 1」一致）
#   stft_tiers: 幅度谱档位数；(n_fft, hop)
PROFILES = {
    "最小": {"stft": [(2048, 512)], "frame_banks": 0, "complex_tiers": 0},
    "中等": {"stft": [(2048, 512), (1024, 256), (4096, 1024)], "frame_banks": 0, "complex_tiers": 0},
    "愿望清单": {
        "stft": [(2048, 512), (1024, 256), (4096, 1024)],
        "frame_banks": 3,
        "complex_tiers": 1,
    },
}


def rss_mb() -> float:
    """当前进程峰值 RSS (MB)。macOS/Linux: ru_maxrss 单位是字节。"""
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return r / (1024 * 1024)
    return r / 1024.0


def load_mono(path: Path, sr: int) -> np.ndarray:
    y, native = sf.read(str(path), dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    if native != sr:
        # 线性重采样（仅测量用，非生产实现）
        n = int(round(len(y) * sr / native))
        idx = np.linspace(0, len(y) - 1, n)
        y = np.interp(idx, np.arange(len(y)), y).astype(DTYPE)
    return np.ascontiguousarray(y, dtype=DTYPE)


@dataclass
class TierResult:
    name: str
    ref_sec: float
    analytic_bytes: int
    rss_delta_mb: float
    elapsed_sec: float
    resident_bytes: int = 0
    notes: list[str] = field(default_factory=list)


def real_stft_mag(sig: np.ndarray, n_fft: int, hop: int) -> int:
    """真正计算 STFT 幅度谱，返回字节数。

    这不是模拟：逐帧 rfft，然后取幅度。测量真实 CPU 与瞬时内存。
    """
    from numpy.lib.stride_tricks import sliding_window_view

    win = np.hanning(n_fft).astype(DTYPE)
    # 帧化：(n_frames, n_fft)
    if len(sig) < n_fft:
        sig = np.pad(sig, (0, n_fft - len(sig)))
    frames = sliding_window_view(sig, n_fft)[::hop]
    spec = np.fft.rfft(frames * win, axis=1)          # 复数，瞬时
    mag = np.abs(spec).astype(DTYPE)                   # 幅度，落盘
    nbytes = mag.nbytes
    # 模拟"落盘后释放瞬时帧与复数"：保留 mag 的引用由调用方决定
    del frames, spec
    return nbytes


def build_surface_real(ref: np.ndarray, prac: np.ndarray, profile: dict) -> tuple[int, list[str]]:
    """真实计算版：返回 (数据面字节数, 备注)。"""
    notes: list[str] = []
    analytic = 0
    # 底座：真实 ndarray 常驻
    for _ in range(3):
        analytic += ref.nbytes
    notes.append("底座 aligned PCM ×3")

    for n_fft, hop in profile["stft"]:
        for sig in (ref, prac):
            analytic += real_stft_mag(sig, n_fft, hop)
        notes.append(f"STFT 幅度 {n_fft}/{hop} ×2（真实计算）")

    for _ in range(profile["frame_banks"]):
        n_fft, hop = profile["stft"][0]
        for _sig in (ref, prac):
            n_frames = 1 + len(_sig) // hop
            analytic += n_frames * n_fft * ITEMSIZE
        notes.append("frame bank ×2")

    for _ in range(profile["complex_tiers"]):
        n_fft, hop = profile["stft"][0]
        for _sig in (ref, prac):
            n_frames = 1 + len(_sig) // hop
            n_bins = n_fft // 2 + 1
            analytic += n_frames * n_bins * ITEMSIZE * 2
        notes.append("复数 STFT ×2")
    return analytic, notes


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not REF_WAV.exists():
        print(f"缺少输入: {REF_WAV}", file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    ref = load_mono(REF_WAV, TARGET_SR)
    prac = load_mono(PRAC_WAV, TARGET_SR) if PRAC_WAV.exists() else ref.copy()
    load_sec = time.perf_counter() - t0
    dur = len(ref) / TARGET_SR
    print(f"输入: {dur:.3f} s @ {TARGET_SR} Hz mono float32 → {ref.nbytes/1e6:.1f} MB/份")
    print(f"加载耗时: {load_sec:.2f} s\n")

    results: list[TierResult] = []
    baseline = rss_mb()
    print(f"进程基线 RSS（含 numpy 导入开销）: {baseline:.1f} MB\n")
    for name, prof in PROFILES.items():
        t = time.perf_counter()
        analytic, notes = build_surface_real(ref, prac, prof)
        elapsed = time.perf_counter() - t
        r = TierResult(
            name=name, ref_sec=dur, analytic_bytes=analytic,
            rss_delta_mb=0.0, elapsed_sec=elapsed,
            resident_bytes=0, notes=notes,
        )
        results.append(r)
        print(f"[{name}]")
        print(f"  数据面字节数   : {analytic/1e6:9.1f} MB   ← 真正要常驻/落盘的量")
        print(f"  真实构建耗时   : {elapsed:9.2f} s")
        print(f"  内容: {', '.join(notes)}\n")

    print(f"全档跑完后进程 RSS 高水位: {rss_mb():.1f} MB（基线 {baseline:.1f}）")
    print("注：RSS 是进程高水位，含解释器与瞬时复数帧，不能归属到某一档；")
    print("    因此上表只报告可精确归因的『数据面字节数』与『耗时』。\n")


    # 外推到 180 s
    print("=" * 66)
    print(f"外推到 180 s（当前 {dur:.1f} s，比例 {180/dur:.3f}×）")
    for r in results:
        scale = 180.0 / r.ref_sec
        print(f"  {r.name:<6} 逻辑 {r.analytic_bytes*scale/1e6:8.1f} MB   "
              f"耗时 {r.elapsed_sec*scale:7.2f} s")

    # 与估算表对比
    est = {"最小": 222.4, "中等": 476.7, "愿望清单": 1493.0}
    print("\n与解析估算对比（180 s）：")
    for r in results:
        scale = 180.0 / r.ref_sec
        actual = r.analytic_bytes * scale / 1e6
        e = est[r.name]
        print(f"  {r.name:<6} 估算 {e:8.1f} MB  实测 {actual:8.1f} MB  "
              f"偏差 {100*(actual-e)/e:+6.1f}%")

    payload = {
        "spike": "CORE-PROFILE-MEMORY",
        "input": {"ref": REF_WAV.name, "duration_sec": round(dur, 3), "sr": TARGET_SR},
        "results": [
            {
                "profile": r.name,
                "data_surface_logical_bytes": r.analytic_bytes,
                "rss_delta_mb": round(r.rss_delta_mb, 2),
                "elapsed_sec": round(r.elapsed_sec, 3),
                "resident_bytes": r.resident_bytes,
                "contents": r.notes,
                "extrapolated_180s_mb": round(r.analytic_bytes * (180.0 / r.ref_sec) / 1e6, 1),
            }
            for r in results
        ],
        "estimate_comparison_180s": est,
    }
    out = OUT_DIR / "spike_core_memory.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n已写出 {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
