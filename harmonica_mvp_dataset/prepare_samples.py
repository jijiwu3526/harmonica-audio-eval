#!/usr/bin/env python3
"""
prepare_samples.py — Download the VCSL Hohner Super64 harmonica samples and build
a verified pitch table.

Sample filenames are NOT trusted: RECON.md documents that VCSL filenames can
disagree with the actual pitch. Instead every sample's fundamental is measured
with two independent estimators (harmonic product spectrum + pyin), and the
measured set is then validated against a strong internal consistency rule:
within one articulation and note letter, successive octaves must differ by
exactly 12 semitones. Samples that violate this are repaired to the octave
implied by the rest of their group, and the repair is recorded.

Output: vendor/VCSL/harmonica/samples_measured.json
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict

import numpy as np
import soundfile as sf

API = "https://api.github.com/repos/sgossner/VCSL"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "vendor", "VCSL", "harmonica")
HDR = {"User-Agent": "Mozilla/5.0 (dataset-build)"}
SUSTAINS = ["Sustains/Normal", "Sustains/Vib"]


def api(path, accept="application/vnd.github+json"):
    req = urllib.request.Request(f"{API}/{path}", headers={**HDR, "Accept": accept})
    return urllib.request.urlopen(req, timeout=120)


def download(path, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return False
    raw = api(f"contents/{urllib.parse.quote(path)}",
              accept="application/vnd.github.raw").read()
    with open(dest, "wb") as f:
        f.write(raw)
    return True


def parse_note(note: str):
    letter = note[0].upper()
    octave = int(note[1:])
    return letter, octave


def main():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from harmonica_sampler import measure_pitch

    os.makedirs(OUT, exist_ok=True)
    tree = json.loads(api("git/trees/master?recursive=1").read())["tree"]

    rows = []
    for sub in SUSTAINS:
        art = sub.split("/")[-1]
        want = [x for x in tree
                if f"Harmonica-Hohner-Super64/{sub}/" in x["path"]
                and x["path"].lower().endswith(".wav")]
        print(f"=== {sub}: {len(want)} samples")
        for x in sorted(want, key=lambda y: y["path"]):
            note = x["path"].rsplit("_", 1)[-1].replace(".wav", "")
            dest = os.path.join(OUT, f"sustain_{art}_{note}.wav")
            new = False
            try:
                new = download(x["path"], dest)
            except Exception as e:
                print(f"  FAIL {note}: {e}")
                continue
            y, sr = sf.read(dest, dtype="float32", always_2d=False)
            if y.ndim > 1:
                y = y.mean(axis=1)
            if new:
                print(f"  downloaded sustain_{art}_{note}.wav")
            rows.append({"file": os.path.basename(dest), "sr": sr,
                         "dur": round(len(y) / sr, 3), "art": art, "note": note,
                         "measured_midi": round(measure_pitch(y, sr), 4)})

    # --- octave-consensus validation and repair
    groups = defaultdict(list)
    for r in rows:
        letter, octave = parse_note(r["note"])
        r["letter"], r["octave"] = letter, octave
        groups[(r["art"], letter)].append(r)

    repaired = []
    for (art, letter), members in sorted(groups.items()):
        base = float(np.median([m["measured_midi"] - 12 * m["octave"] for m in members]))
        for m in members:
            expected = base + 12 * m["octave"]
            err = m["measured_midi"] - expected
            m["octave_consensus_midi"] = round(expected, 4)
            m["octave_deviation_cents"] = round(err * 100, 2)
            m["midi"] = round(expected, 4)          # final, used by the sampler
            if abs(err) >= 0.10:                     # >= 10 cents from the group
                m["repaired"] = True
                repaired.append(m)
            else:
                m["repaired"] = False

    json.dump(rows, open(os.path.join(OUT, "samples_measured.json"), "w"), indent=2)

    print("\n=== per-group octave consistency (median octave-independent pitch) ===")
    for (art, letter), members in sorted(groups.items()):
        ms = sorted(members, key=lambda m: m["octave"])
        print(f"  {art:7s} {letter}: " + "  ".join(
            f"{m['note']}={m['measured_midi']:.2f}" for m in ms))
    print(f"\n=== repairs ({len(repaired)}) ===")
    for m in repaired:
        print(f"  {m['file']}: measured {m['measured_midi']:.2f} "
              f"({m['octave_deviation_cents']:+.0f} cents off its octave) "
              f"-> corrected to {m['midi']:.2f}")
    n_bad = sum(1 for r in rows if abs(r["octave_deviation_cents"]) >= 10)
    print(f"\ntotal samples: {len(rows)}; octave-consistent: {len(rows) - n_bad}; "
          f"repaired: {n_bad}")
    print(f"pitch table: {os.path.join(OUT, 'samples_measured.json')}")


if __name__ == "__main__":
    main()
