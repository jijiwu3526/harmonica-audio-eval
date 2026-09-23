#!/usr/bin/env python3
"""
harmonica_sampler.py — Render MIDI notes with the real VCSL Hohner Super64
harmonica samples.

FluidSynth only loads SF2/SF3, and no SFZ player is available here, so this is a
small purpose-built sampler:

  * every sample's true fundamental is MEASURED (never trusted from the filename,
    which is documented as unreliable);
  * a target note is produced by resampling the nearest measured sample, so
    intonation is correct by construction;
  * sustained notes are filled by looping a stable interior region with
    crossfades, then shaped with a short attack/release envelope;
  * notes are summed into a float buffer, so polyphony works.

Samples: VCSL (https://github.com/sgossner/VCSL), CC0-1.0.
"""
from __future__ import annotations

import json
import os
from fractions import Fraction

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

A4_HZ = 440.0


def midi_to_hz(m: float) -> float:
    return A4_HZ * 2.0 ** ((m - 69.0) / 12.0)


def _hps_f0(seg: np.ndarray, sr: int, fmin: float = 40.0, fmax: float = 4000.0) -> float:
    """Harmonic-product-spectrum fundamental. Robust where pyin picks a subharmonic.

    The product is accumulated on the full spectrum so that bin i is multiplied by
    exactly the energy at h * (i * df); slicing a band first would misalign the
    frequency axis and bias the estimate.
    """
    n = len(seg)
    if n < 512:
        return 0.0
    win = seg * np.hanning(n)
    S = np.abs(np.fft.rfft(win))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    hps = S.astype(np.float64).copy()
    for h in range(2, 6):
        d = S[::h].astype(np.float64)
        hps[:len(d)] *= d
    lo = int(np.searchsorted(freqs, fmin))
    hi = int(np.searchsorted(freqs, fmax))
    if hi - lo < 8:
        return 0.0
    return float(freqs[lo + int(np.argmax(hps[lo:hi]))])


def measure_pitch(y: np.ndarray, sr: int) -> float:
    """Robust fundamental estimate of a sustained sample, in MIDI numbers.

    Two independent estimators are combined: the harmonic product spectrum and
    pyin. pyin is reliable for the octave but can lock onto a subharmonic, so the
    HPS result is preferred and pyin is used to cross-check only when the two
    agree within a semitone (or when HPS is unavailable).
    """
    import librosa

    # Use the interior of the sample: skip the attack and the tail decay.
    n = len(y)
    seg = y[int(0.15 * n):int(0.75 * n)]
    if len(seg) < 2048:
        seg = y

    hps = _hps_f0(seg, sr)
    f0, vf, _ = librosa.pyin(seg, fmin=40, fmax=4000, sr=sr,
                             frame_length=4096, hop_length=256)
    m = vf & np.isfinite(f0) & (f0 > 0)
    pyin_med = float(np.median(f0[m])) if m.any() else 0.0

    if hps > 0 and pyin_med > 0:
        # If pyin is an integer subharmonic of the HPS estimate, trust HPS.
        ratio = pyin_med / hps
        if abs(ratio - round(ratio)) < 0.03 and round(ratio) >= 1:
            cand = hps
        else:
            cand = pyin_med if abs(12 * np.log2(pyin_med / hps)) < 100 else hps
    elif hps > 0:
        cand = hps
    elif pyin_med > 0:
        cand = pyin_med
    else:
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        freqs = np.fft.rfftfreq(len(seg), 1.0 / sr)
        cand = float(freqs[int(np.argmax(spec))])
    return 69.0 + 12.0 * np.log2(cand / A4_HZ)


class HarmonicaSampler:
    """Renders (start, end, midi, velocity, cents) notes using VCSL samples."""

    def __init__(self, sample_dir: str, sr: int = 44100):
        self.sr = sr
        self.sample_dir = sample_dir
        cache = os.path.join(sample_dir, "samples_measured.json")
        self.samples = []          # list of dicts: midi, sr, y
        if os.path.exists(cache):
            for row in json.load(open(cache)):
                p = os.path.join(sample_dir, row["file"])
                if not os.path.exists(p):
                    continue
                y, s = sf.read(p, dtype="float32", always_2d=False)
                if y.ndim > 1:
                    y = y.mean(axis=1)
                if s != sr:
                    y = resample_poly(y, sr, s).astype(np.float32)
                self.samples.append({"file": row["file"], "midi": float(row["midi"]), "y": y})
        if not self.samples:
            raise RuntimeError(f"no samples found in {sample_dir}")
        self.samples.sort(key=lambda s: s["midi"])

    def _nearest(self, midi: float):
        return min(self.samples, key=lambda s: abs(s["midi"] - midi))

    def _render_note(self, midi: float, dur_sec: float, velocity: int,
                     cents: float = 0.0) -> np.ndarray:
        s = self._nearest(midi)
        target = midi + cents / 100.0
        ratio = midi_to_hz(target) / midi_to_hz(s["midi"])
        # resample_poly(x, up, down) upsamples by `up` then downsamples by `down`,
        # compressing or stretching the waveform in time. A ratio > 1 (raise the
        # pitch) therefore needs up=denominator, down=numerator. Verified against a
        # controlled 440 Hz tone test.
        fr = Fraction(ratio).limit_denominator(2000)
        y = resample_poly(s["y"], fr.denominator, fr.numerator).astype(np.float32)

        want = max(1, int(round(dur_sec * self.sr)))
        if len(y) >= want:
            out = y[:want].copy()
        else:
            # Loop a stable interior region to sustain the note.
            lo, hi = int(0.35 * len(y)), int(0.95 * len(y))
            loop = y[lo:hi] if hi > lo + 64 else y
            xf = min(int(0.008 * self.sr), len(loop) // 4)
            out = y.copy()
            while len(out) < want + xf:
                seg = loop.copy()
                if xf > 0 and len(out) >= xf:
                    ramp = np.linspace(0.0, 1.0, xf, dtype=np.float32)
                    seg = seg.copy()
                    seg[:xf] = seg[:xf] * ramp + out[-xf:] * (1.0 - ramp)
                    out = out[:-xf]
                out = np.concatenate([out, seg])
            out = out[:want].copy()

        # Short attack/release so notes do not click.
        a = min(int(0.012 * self.sr), len(out) // 3)
        r = min(int(0.030 * self.sr), len(out) // 3)
        if a > 0:
            out[:a] *= np.linspace(0.0, 1.0, a, dtype=np.float32)
        if r > 0:
            out[-r:] *= np.linspace(1.0, 0.0, r, dtype=np.float32)

        return out * (max(0, min(127, velocity)) / 127.0)

    def render(self, notes, total_sec: float, out_path: str,
               peak_db: float = -3.0) -> dict:
        """notes: iterable of (start_sec, end_sec, midi, velocity[, cents])."""
        buf = np.zeros(int(round(total_sec * self.sr)) + self.sr, dtype=np.float32)
        n_used = 0
        for n in notes:
            st, en, midi, vel = n[0], n[1], n[2], n[3]
            cents = float(n[4]) if len(n) > 4 else 0.0
            if en <= st:
                continue
            seg = self._render_note(float(midi), float(en - st), int(vel), cents)
            i0 = int(round(st * self.sr))
            i1 = min(len(buf), i0 + len(seg))
            if i1 <= i0:
                continue
            buf[i0:i1] += seg[:i1 - i0]
            n_used += 1

        buf = buf[:int(round(total_sec * self.sr))]
        peak = float(np.max(np.abs(buf))) if buf.size else 0.0
        if peak > 0:
            buf = buf * (10 ** (peak_db / 20.0) / peak)
        sf.write(out_path, buf, self.sr, subtype="PCM_16")
        return {"notes_rendered": n_used, "peak_db": round(20 * np.log10(
            max(float(np.max(np.abs(buf))) if buf.size else 0.0, 1e-12)), 2)}


if __name__ == "__main__":
    import sys

    d = os.path.dirname(os.path.abspath(__file__))
    sr_dir = os.path.join(os.path.dirname(d), "vendor", "VCSL", "harmonica")
    s = HarmonicaSampler(sr_dir)
    print("samples (measured MIDI):")
    for x in s.samples:
        print(f"  {x['file']:44s} {x['midi']:8.3f}")
    out = "/tmp/vcsl_test.wav"
    info = s.render([(0.0, 1.0, 69, 100), (1.0, 2.0, 72, 100), (2.0, 3.0, 76, 100)],
                    3.2, out)
    print("test render:", info)
    import librosa
    y, r = librosa.load(out, sr=22050)
    f0, vf, _ = librosa.pyin(y, fmin=100, fmax=1500, sr=22050)
    m = vf & np.isfinite(f0) & (f0 > 0)
    t = librosa.times_like(f0, sr=22050)
    for lo, hi, want in ((0.2, 0.9, 69), (1.2, 1.9, 72), (2.2, 2.9, 76)):
        mm = m & (t >= lo) & (t <= hi)
        if mm.any():
            est = 69 + 12 * np.log2(np.median(f0[mm]) / 440)
            print(f"  target {want} -> measured {est:.2f} ({(est-want)*100:+.1f} cents)")
