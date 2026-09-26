"""两后端等价性验证（chroma_stft / pyin）。

在装了 librosa 的电脑上，跑**同一段输入**的 librosa 路径与自写路径，
量化差异并对三条判据给出通过/不通过。

判据（★ 不因结果不好而放宽）:
    1. chroma: Pearson r > 0.95
    2. pyin  : 双方都判 voiced 的帧上，median |Δcents| < 50
    3. 两后端**帧数完全相同**（硬要求）

用法: python3 tools/verify_backend_equivalence.py [--quick]
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import librosa  # noqa: E402  (验证脚本需要它作为参照后端)

from harmonica_eval.core.backend.chroma import chroma_stft as native_chroma  # noqa: E402
from harmonica_eval.core.backend.pyin import pyin as native_pyin  # noqa: E402
from harmonica_eval.profile import ALIGN, MATERIALIZE  # noqa: E402

# ══ 判据阈值（★ 冻结：只报结果，不因结果不好而调宽）══
CHROMA_CORR_MIN = 0.95
PYIN_MEDIAN_CENTS_MAX = 50.0

SR = 44100


def load(path: Path) -> np.ndarray:
    """读成 float32 单声道 44.1 kHz（与 ingest 的标准化目标一致）。"""
    y, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1, dtype=np.float32)
    if sr != SR:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(int(sr), SR)
        y = resample_poly(y, SR // g, int(sr) // g).astype(np.float32)
    return np.ascontiguousarray(y, dtype=np.float32)


def synth(seed: int, n_sec: float) -> np.ndarray:
    """现造一段 44100 Hz mono 测试音频（谐波口琴音 + 静音 + 噪声段）。

    固定种子 ⇒ 可复现。三个音刻意跨一个八度，覆盖 chroma 的八度折叠
    与 pyin 的次谐波歧义；静音段用来暴露 0/0 与空数组边界。
    """
    rng = np.random.default_rng(seed)
    n = int(SR * n_sec)
    t = np.arange(n, dtype=np.float64) / SR
    y = np.zeros(n, dtype=np.float64)

    # (占空比起点, 占空比终点, 基频, 振幅) —— C4 / G4 / C5 / D5，覆盖口琴实际音域。
    # 时刻按总长等比缩放，短输入也不会越界。
    notes = [(0.05, 0.21, 261.63, 0.5), (0.25, 0.42, 392.00, 0.4),
             (0.46, 0.63, 523.25, 0.45), (0.67, 0.84, 587.33, 0.35)]
    for frac0, frac1, f0, amp in notes:
        start, end = frac0 * n_sec, frac1 * n_sec
        m = (t >= start) & (t < end)
        sig = np.zeros(n)
        # 口琴接近方波：前 8 次谐波
        for k in range(1, 9):
            sig += (amp / k) * np.sin(2 * np.pi * f0 * k * t)
        # 起音/收音包络，避免边界不连续
        env = np.ones(n)
        atk = max(1, int(0.03 * SR))
        rel = max(1, int(0.08 * SR))
        s, e = int(start * SR), min(n, int(end * SR))
        if e - s <= atk + rel:
            atk = rel = max(1, (e - s) // 4)
        env[s:s + atk] = np.linspace(0, 1, atk)
        env[e - rel:e] = np.linspace(1, 0, rel)
        y[m] += sig[m] * env[m]

    # 尾部 12% 纯静音（末帧必须是 0，不能 NaN）
    y[int(n * 0.88):] = 0.0
    # 前 2.5% 极低电平噪声（近静音但非零）
    y[: max(1, int(0.025 * n))] = rng.normal(0, 1e-5, max(1, int(0.025 * n)))
    return np.clip(y, -1.0, 1.0).astype(np.float32)


def compare_chroma(y: np.ndarray) -> dict:
    kw = dict(y=y, sr=SR, n_fft=MATERIALIZE.frame_length,
              hop_length=ALIGN.hop_length, n_chroma=12,
              tuning=0.0, norm=np.inf, center=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ref = librosa.feature.chroma_stft(**kw)
        got = native_chroma(**kw)
    ref = np.asarray(ref, dtype=np.float64)
    got = np.asarray(got, dtype=np.float64)
    return {
        "ref_shape": ref.shape, "got_shape": got.shape,
        "frames_equal": ref.shape == got.shape,
        "shape_head_equal": ref.shape[0] == got.shape[0],
        "max_abs_diff": float(np.abs(ref - got).max()) if ref.shape == got.shape else float("nan"),
        "mean_abs_diff": float(np.abs(ref - got).mean()) if ref.shape == got.shape else float("nan"),
        "pearson_r": (float(np.corrcoef(ref.ravel(), got.ravel())[0, 1])
                      if ref.shape == got.shape else float("nan")),
    }


def compare_pyin(y: np.ndarray) -> dict:
    kw = dict(y=y, sr=SR, fmin=MATERIALIZE.fmin_hz, fmax=MATERIALIZE.fmax_hz,
              frame_length=MATERIALIZE.pitch_frame_length,
              hop_length=MATERIALIZE.pitch_hop_length, center=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ref = librosa.pyin(**kw)
        got = native_pyin(**kw)

    shapes_eq = all(a.shape == b.shape for a, b in zip(ref, got))
    f0r, vf_r, vp_r = ref
    f0g, vf_g, vp_g = got

    both = vf_r & vf_g
    n_both = int(both.sum())
    if n_both and shapes_eq:
        cents = np.abs(1200.0 * np.log2(f0g[both] / f0r[both]))
        med = float(np.median(cents))
        p95 = float(np.percentile(cents, 95))
        mx = float(cents.max())
        n_over = int((cents > PYIN_MEDIAN_CENTS_MAX).sum())
    else:
        med = p95 = mx = float("nan")
        n_over = -1

    return {
        "ref_shapes": [a.shape for a in ref],
        "got_shapes": [a.shape for a in got],
        "shapes_equal": shapes_eq,
        "n_frames": int(f0r.shape[0]),
        "n_both_voiced": n_both,
        "median_cents": med,
        "p95_cents": p95,
        "max_cents": mx,
        "n_frames_over_50c": n_over,
        "voiced_flag_agreement": float((vf_r == vf_g).mean()) if shapes_eq else float("nan"),
        "voiced_prob_max_abs_diff": float(np.abs(vp_r - vp_g).max()) if shapes_eq else float("nan"),
        "nan_count_native": int(np.isnan(f0g).sum()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="只跑 2 段（3.2s 合成 + 1 段短实测切片）")
    args = ap.parse_args()

    cases: list[tuple[str, np.ndarray]] = []
    cases.append(("synth#0 12s (seed=0)", synth(0, 12.0)))
    cases.append(("synth#7 8s (seed=7)", synth(7, 8.0)))

    wavs = sorted((ROOT / "harmonica_mvp_dataset").rglob("*.wav"))
    if wavs:
        # 取 2 段真实录音；用切片把 pyin 的 O(帧数 × 候选数) 成本压住
        real = wavs[0]
        cases.append((f"real {real.relative_to(ROOT)} (前 12s)",
                      load(real)[: 12 * SR]))
        if len(wavs) > 3:
            real2 = wavs[3]
            cases.append((f"real {real2.relative_to(ROOT)} (前 12s)",
                          load(real2)[: 12 * SR]))
    if args.quick:
        cases = cases[:3]

    failures: list[str] = []
    for name, y in cases:
        print("=" * 78)
        print(f"CASE  {name}   n={len(y)}  ({len(y)/SR:.2f}s @ {SR} Hz)")
        ch = compare_chroma(y)
        py = compare_pyin(y)

        ok_frames = ch["frames_equal"] and py["shapes_equal"]
        ok_corr = ch["pearson_r"] > CHROMA_CORR_MIN
        ok_cents = (py["n_both_voiced"] > 0) and (py["median_cents"] < PYIN_MEDIAN_CENTS_MAX)

        print(f"  chroma  librosa{list(ch['ref_shape'])}  native{list(ch['got_shape'])}")
        print(f"          max|Δ|={ch['max_abs_diff']:.3e}  mean|Δ|={ch['mean_abs_diff']:.3e}"
              f"  pearson r={ch['pearson_r']:.9f}")
        print(f"  pyin    librosa{py['ref_shapes']}  native{py['got_shapes']}")
        print(f"          both-voiced={py['n_both_voiced']}/{py['n_frames']}"
              f"  median|Δcents|={py['median_cents']:.4f}"
              f"  p95={py['p95_cents']:.4f}  max={py['max_cents']:.4f}"
              f"  >50c帧={py['n_frames_over_50c']}")
        print(f"          voiced_flag 一致率={py['voiced_flag_agreement']*100:.3f}%"
              f"  voiced_prob max|Δ|={py['voiced_prob_max_abs_diff']:.3e}")
        print(f"  native f0 NaN 数={py['nan_count_native']}（librosa 同样会给出 NaN，"
              f"由 features.py 的 nan_to_num 归零）")

        for ok, label, detail in (
            (ok_corr, "判据1 chroma Pearson r > 0.95", f"实测 {ch['pearson_r']:.9f}"),
            (ok_cents, "判据2 pyin median |Δcents| < 50", f"实测 {py['median_cents']:.4f}"),
            (ok_frames, "判据3 两后端帧数完全相同",
             f"chroma {list(ch['ref_shape'])} vs {list(ch['got_shape'])}; "
             f"pyin {py['ref_shapes']} vs {py['got_shapes']}"),
        ):
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}  —  {detail}")
            if not ok:
                failures.append(f"{name}: {label} ({detail})")

    print("=" * 78)
    if failures:
        print("判据未全部取得：")
        for f in failures:
            print("  -", f)
        return 1
    print("三条判据全部取得。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
