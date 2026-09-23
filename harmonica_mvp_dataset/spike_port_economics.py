#!/usr/bin/env python3
"""SPIKE-PORT-ECONOMICS — 每个候选端口「预加工」到底值不值？

背景：SPIKE-CORE-MEMORY 测出——3 分钟音频的 STFT 幅度谱
  计算耗时仅 ~0.34 s，但存储要 ~127 MB。
这个比例非常糟糕。本脚本量化"存 vs 现算"的经济性，
用来回答 CORE_PROFILE_V0.1 该包含哪些端口。

判据：
  省下的时间 / 占用的内存  = 每 MB 换回多少毫秒
  这个比值越低，越不值得预加工。

结论将直接支持 profile 推荐（见输出与报告）。
本脚本无随机性，固定输入。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf

DATASET = Path(__file__).resolve().parent
SONG_DIR = DATASET / "01_奇异恩典"
REF_WAV = SONG_DIR / "原曲_完整版.wav"
OUT_DIR = DATASET.parent / "data" / "out"

SR = 44100
DT = np.float32
ITEM = np.dtype(DT).itemsize


def load(path: Path) -> np.ndarray:
    y, nat = sf.read(str(path), dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    if nat != SR:
        idx = np.linspace(0, len(y) - 1, int(round(len(y) * SR / nat)))
        y = np.interp(idx, np.arange(len(y)), y).astype(DT)
    return np.ascontiguousarray(y, dtype=DT)


def t_of(fn, *a, repeat: int = 3, **kw) -> tuple[float, object]:
    """返回 (最好一次耗时秒, 最后一个结果)。"""
    best = float("inf")
    out = None
    for _ in range(repeat):
        t = time.perf_counter()
        out = fn(*a, **kw)
        best = min(best, time.perf_counter() - t)
    return best, out


def stft_mag(y, n_fft, hop):
    from numpy.lib.stride_tricks import sliding_window_view
    win = np.hanning(n_fft).astype(DT)
    if len(y) < n_fft:
        y = np.pad(y, (0, n_fft - len(y)))
    fr = sliding_window_view(y, n_fft)[::hop]
    return np.abs(np.fft.rfft(fr * win, axis=1)).astype(DT)


def rms_envelope(y, hop):
    n = len(y) // hop
    fr = y[: n * hop].reshape(n, hop)
    return np.sqrt((fr ** 2).mean(axis=1)).astype(DT)


def chroma_lowres(y, hop):
    """低分辨率 chroma（模拟 5 Hz 对齐特征），用 STFT 折叠。"""
    n_fft = 4096
    S = np.abs(np.fft.rfft(
        np.lib.stride_tricks.sliding_window_view(y, n_fft)[::hop] *
        np.hanning(n_fft).astype(DT), axis=1))
    freqs = np.fft.rfftfreq(n_fft, 1 / SR)
    with np.errstate(divide="ignore"):
        midi = 69 + 12 * np.log2(np.maximum(freqs, 1e-6) / 440.0)
    pc = np.mod(np.round(midi).astype(int), 12)
    valid = (freqs > 55) & (freqs < 2000)
    out = np.zeros((S.shape[0], 12), dtype=DT)
    for k in range(12):
        sel = valid & (pc == k)
        if sel.any():
            out[:, k] = S[:, sel].sum(axis=1)
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not REF_WAV.exists():
        print(f"缺少输入: {REF_WAV}")
        return 2

    y = load(REF_WAV)
    dur = len(y) / SR
    print(f"输入: {dur:.3f} s @ {SR} Hz mono float32")
    print(f"PCM 一份 = {y.nbytes/1e6:.1f} MB\n")

    # 候选端口：(名称, 计算函数, 单信号字节数计算, 说明)
    cands = []

    def add(name, fn, size_fn, note):
        cands.append((name, fn, size_fn, note))

    add("幅度谱 2048/512", lambda s: stft_mag(s, 2048, 512),
        lambda L: (1 + L // 512) * (2048 // 2 + 1) * ITEM,
        "通用分析主力，算法通常需要")
    add("幅度谱 1024/256", lambda s: stft_mag(s, 1024, 256),
        lambda L: (1 + L // 256) * (1024 // 2 + 1) * ITEM, "高时间分辨率")
    add("幅度谱 4096/1024", lambda s: stft_mag(s, 4096, 1024),
        lambda L: (1 + L // 1024) * (4096 // 2 + 1) * ITEM, "高频率分辨率")
    add("RMS 能量包络 @512", lambda s: rms_envelope(s, 512),
        lambda L: (L // 512) * ITEM, "节奏/气息，极小")
    add("低分辨率 chroma @5Hz", lambda s: chroma_lowres(s, int(SR / 5)),
        lambda L: (L // int(SR / 5)) * 12 * ITEM, "对齐专用，极小")

    rows = []
    print(f"{'端口':<22}{'单信号':>10}{'双信号':>10}{'重算耗时':>10}{'MB/秒省下':>11}  判断")
    print("-" * 82)
    for name, fn, size_fn, note in cands:
        sec, _ = t_of(fn, y)
        size = size_fn(len(y))
        two = 2 * size
        saved_ms = sec * 1000
        mb = two / 1e6
        ratio = mb / max(saved_ms, 1e-9)   # MB per ms saved
        # 判据：为省 1 毫秒要付出多少 MB。
        #   极小  → 无论如何都该预加工（内存几乎免费）
        #   中等  → 仅当有多个消费者复用同一端口才划算
        #   大    → v0.1 只有一个算法实例，不值得
        if ratio < 0.05:
            verdict = "值得（内存几乎免费）"
        elif ratio < 0.5:
            verdict = "仅多消费者时值得"
        else:
            verdict = "不值得（单消费者）"
        # 时间盈亏平衡点：需要多少个消费者同时复用它才回本
        break_even = None
        rows.append({
            "port": name, "one_signal_mb": round(size / 1e6, 3),
            "two_signal_mb": round(two / 1e6, 3),
            "recompute_ms": round(saved_ms, 2),
            "mb_per_ms_saved": round(ratio, 4),
            "verdict": verdict, "note": note,
        })
        print(f"{name:<22}{size/1e6:>9.3f}M{two/1e6:>9.3f}M"
              f"{saved_ms:>9.1f}ms{ratio:>11.3f}  {verdict}")

    # 汇总
    pcm3 = 3 * y.nbytes
    print("\n" + "=" * 82)
    print("结论")
    print("=" * 82)
    print(f"底座 aligned PCM ×3 = {pcm3/1e6:.1f} MB（任何 profile 都必须有）")

    keep = [r for r in rows if r["verdict"].startswith("值得")]
    multi = [r for r in rows if r["verdict"].startswith("仅多消费者")]
    drop = [r for r in rows if r["verdict"].startswith("不值得")]

    print(f"\n必须预加工（小，且定义需统一）：")
    for r in keep:
        print(f"  + {r['port']:<22} {r['two_signal_mb']:>7.3f} MB"
              f"  省 {r['recompute_ms']:>6.1f} ms/次")
    tot_keep = sum(r["two_signal_mb"] for r in keep) * 1e6
    print(f"  小计 {tot_keep/1e6:.3f} MB")

    print(f"\n仅当多个算法复用同一端口时才预加工：")
    for r in multi:
        print(f"  ? {r['port']:<22} {r['two_signal_mb']:>7.3f} MB"
              f"  省 {r['recompute_ms']:>6.1f} ms/次")
    tot_multi = sum(r["two_signal_mb"] for r in multi) * 1e6

    print(f"\nv0.1 不值得预加工（只有一个算法实例，现算更快且不占内存）：")
    for r in drop:
        print(f"  - {r['port']:<22} {r['two_signal_mb']:>7.3f} MB"
              f"  但现算只需 {r['recompute_ms']:>6.1f} ms")

    total_small = pcm3 + tot_keep
    total_multi = pcm3 + tot_keep + tot_multi
    payload = {
        "spike": "PORT-ECONOMICS",
        "input": {"file": REF_WAV.name, "duration_sec": round(dur, 3), "sr": SR},
        "pcm_base_3x_mb": round(pcm3 / 1e6, 1),
        "ports": rows,
        "recommendation": {
            "must_have": "aligned PCM ×3 (mapped ref, mapped practice, warped practice)",
            "precompute": [r["port"] for r in keep],
            "precompute_only_if_multi_consumer": [r["port"] for r in multi],
            "let_algorithms_recompute": [r["port"] for r in drop],
            "recommended_profile_mb": round(total_small / 1e6, 1),
            "with_multi_consumer_tiers_mb": round(total_multi / 1e6, 1),
        },
    }
    (OUT_DIR / "spike_port_economics.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n推荐 profile 规模 ≈ {total_small/1e6:.1f} MB（本首 {dur:.1f}s 音频）")
    print(f"若含多消费者端口 ≈ {total_multi/1e6:.1f} MB")
    print(f"已写出 {OUT_DIR/'spike_port_economics.json'}")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
