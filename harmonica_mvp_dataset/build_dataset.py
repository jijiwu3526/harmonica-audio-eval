#!/usr/bin/env python3
"""
build_dataset.py — 构建 10 首口琴 MVP 金标准测试集。

设计要点
--------
1) **全部音频都是口琴。** 原曲、标准旋律版、所有练习曲，一律使用 VCSL 的
   Hohner Super64 真实口琴采样渲染（见 harmonica_sampler.py）。没有钢琴。
2) **一版原曲 + 多个练习曲。** 每首歌产出完整版、标准旋律版，以及 5 个练习曲。
3) **练习曲要真的糟糕，但必须可对齐。** 每个练习曲只在一个维度上严重偏离，
   并且：
     - 音符序列与总数不变（漏音变体除外，它的删除有记录）；
     - 总时长与标准旋律版完全一致；
     - 不产生音符重排或相互吞并（抖动按音符自身时长设上限）。
   这样"对齐算法"永远能把两版对上，同时指标能看出演奏有多差。
4) **真值是 MIDI，永不是音频。** 所有注入的偏差都记录在练习曲标注里，
   因此对比算法可以对着已知答案打分。

目录结构（中文分类）
--------------------
    01_奇异恩典/
        原曲_完整版.wav
        标准旋律版.wav
        练习曲/
            01_音准走调.wav
            02_节奏抢拖.wav
            03_气息不匀.wav
            04_错音.wav
            05_漏音断句.wav
        乐谱与标注/
            source.mid  melody.mid  expected_notes.csv
            practice_variants.json  metadata.json  midi_analysis.json
        质检图/
            qa_waveform.png  qa_pitch.png
        来源与许可.txt

用法
----
    python build_dataset.py                 # 全部
    python build_dataset.py --only 01       # 只做第一首
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict

import mido
import numpy as np
import soundfile as sf

SEED = 42

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
DL = os.path.join(HERE, "_download")
SOURCES = os.path.join(HERE, "sources.json")
VCSL_DIR = os.path.join(PARENT, "vendor", "VCSL", "harmonica")
LISTEN = os.path.join(PARENT, "listen")

A4_HZ = 440.0
MIDI_LO, MIDI_HI = 60, 84
MIDI_ALLOW_LO, MIDI_ALLOW_HI = 55, 88
DUR_LO, DUR_HI = 45.0, 120.0
DUR_PREF_LO, DUR_PREF_HI = 60.0, 90.0
LEAD_SEC, TAIL_SEC = 0.4, 0.4
MAX_OVERLAP_SEC = 0.030
PEAK_TARGET_DB = -3.0
SR = 44100
GM_HARMONICA = 22
PYIN_SR = 22050

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# 中文曲名
CN_TITLE = {
    "01_amazing_grace": "奇异恩典",
    "02_greensleeves": "绿袖子",
    "03_auld_lang_syne": "友谊地久天长",
    "04_ode_to_joy": "欢乐颂",
    "05_first_noel": "圣诞佳音",
    "06_home_sweet_home": "甜蜜的家",
    "07_brahms_lullaby": "勃拉姆斯摇篮曲",
    "08_caro_mio_ben": "我亲爱的",
    "09_swanee_river": "故乡的亲人",
    "10_hard_times": "艰难时光",
}

# 练习曲：目录名 -> (中文文件名, 维度说明)
VARIANTS = [
    ("01_offpitch", "01_音准走调", "音准：整体走调，每个音偏离标准音高很多"),
    ("02_timing", "02_节奏抢拖", "节奏：抢拍与拖拍，进音时机不稳"),
    ("03_dynamics", "03_气息不匀", "力度：气息控制失败，忽强忽弱且有音几乎听不见"),
    ("04_wrongnotes", "04_错音", "音高：吹错孔位，部分音高了或低了若干半音"),
    ("05_dropouts", "05_漏音断句", "完整性：漏吹若干音，乐句出现断裂"),
]


def midi_name(m: int) -> str:
    return f"{NOTE_NAMES[int(m) % 12]}{int(m) // 12 - 1}"


def hz(m: float) -> float:
    return A4_HZ * 2.0 ** ((m - 69.0) / 12.0)


def db(x: float) -> float:
    return 20.0 * np.log10(max(x, 1e-12))


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


# ---- MIDI 读取 ---------------------------------------------------------------
def load_midi(path: str) -> mido.MidiFile:
    return mido.MidiFile(path)


def tempo_map(mid: mido.MidiFile):
    ev = []
    for tr in mid.tracks:
        t = 0
        for msg in tr:
            t += msg.time
            if msg.type == "set_tempo":
                ev.append((t, msg.tempo))
    if not ev:
        return [(0, 500000)]
    ev.sort()
    if ev[0][0] != 0:
        ev.insert(0, (0, ev[0][1]))
    return ev


def tick_to_sec(tick: float, tpb: int, tempos) -> float:
    sec, last, cur = 0.0, 0, tempos[0][1]
    for at, tempo in tempos:
        if at >= tick:
            break
        sec += (at - last) / tpb * (cur / 1e6)
        last, cur = at, tempo
    sec += (tick - last) / tpb * (cur / 1e6)
    return sec


def sec_to_tick(sec: float, tpb: int, tempos) -> int:
    if len(tempos) == 1:
        return int(round(sec * tpb * 1e6 / tempos[0][1]))
    lo, hi = 0, 10 ** 9
    while lo < hi:
        mid = (lo + hi) // 2
        if tick_to_sec(mid, tpb, tempos) < sec:
            lo = mid + 1
        else:
            hi = mid
    return lo


def signed_sec_to_tick(delta_sec: float, tpb: int, tempos) -> int:
    if len(tempos) == 1:
        return int(round(delta_sec * tpb * 1e6 / tempos[0][1]))
    return sec_to_tick(delta_sec, tpb, tempos) if delta_sec >= 0 \
        else -sec_to_tick(-delta_sec, tpb, tempos)


def read_track(track) -> dict:
    t = 0
    pend = defaultdict(list)
    notes = []
    names, progs = [], []
    for msg in track:
        t += msg.time
        if msg.type == "track_name":
            names.append(msg.name)
        elif msg.type == "program_change":
            progs.append(msg.program)
        elif msg.type == "note_on" and msg.velocity > 0:
            pend[msg.note].append((t, msg.velocity))
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            if pend[msg.note]:
                st, vel = pend[msg.note].pop(0)
                if t > st:
                    notes.append((st, t, msg.note, vel))
    notes.sort(key=lambda n: (n[0], -n[2]))
    return {"notes": notes, "names": names, "programs": progs}


def polyphony(notes):
    if not notes:
        return 0, 0.0
    ev = []
    for st, en, p, v in notes:
        ev.append((st, 1))
        ev.append((en, -1))
    ev.sort()
    cur = mx = 0
    poly = total = 0.0
    prev = None
    for t, d in ev:
        if prev is not None:
            total += t - prev
            if cur > 1:
                poly += t - prev
        cur += d
        mx = max(mx, cur)
        prev = t
    return mx, (poly / total if total else 0.0)


# ---- 旋律提取 ----------------------------------------------------------------
def cluster_onsets(notes, tol_ticks):
    out, i = [], 0
    while i < len(notes):
        grp = [notes[i]]
        j = i
        while j + 1 < len(notes) and notes[j + 1][0] - notes[i][0] <= tol_ticks:
            j += 1
            grp.append(notes[j])
        out.append(grp)
        i = j + 1
    return out


def enforce_mono(notes, max_overlap_ticks):
    notes = sorted(notes, key=lambda n: (n[0], -n[2]))
    out = []
    for st, en, p, v in notes:
        if out and st < out[-1][1]:
            out[-1] = (out[-1][0], st, out[-1][2], out[-1][3])
        if out and st < out[-1][0]:
            continue
        out.append((st, en, p, v))
    return [n for n in out if n[1] > n[0]]


def choose_melody(mid, spec, tps):
    analysis = []
    for i, tr in enumerate(mid.tracks):
        r = read_track(tr)
        mx, poly = polyphony(r["notes"])
        pitches = [n[2] for n in r["notes"]]
        analysis.append({
            "track": i, "names": r["names"], "programs": sorted(set(r["programs"])),
            "n_notes": len(r["notes"]),
            "min_pitch": min(pitches) if pitches else None,
            "max_pitch": max(pitches) if pitches else None,
            "max_simultaneous": mx, "polyphony_ratio": round(poly, 3),
        })

    idx, mode = spec["track"], spec["mode"]
    tr = read_track(mid.tracks[idx])
    notes = tr["notes"]

    if mode == "topvoice":
        tol = int(round(tps * 0.020))
        clusters = cluster_onsets(notes, tol)
        picked = [max(c, key=lambda n: n[2]) for c in clusters]
        rationale = (
            f"第 {idx} 轨（名称={tr['names']}，音色号={sorted(set(tr['programs']))}）是"
            f"多声部谱表（最大同时发声={polyphony(notes)[0]}）。记谱的高声部/女高音声部"
            f"承载旋律，因此取每个起音簇的最高音（容差 20ms，共 {len(clusters)} 簇）。"
            f"已与 Mutopia 的 LilyPond 原谱逐音核对。"
        )
    else:
        picked = notes
        rationale = (
            f"第 {idx} 轨（名称={tr['names']}，音色号={sorted(set(tr['programs']))}）"
            f"本身即为单声部（最大同时发声={polyphony(notes)[0]}），就是记谱的旋律线。"
        )

    mono = enforce_mono(picked, int(round(tps * MAX_OVERLAP_SEC)))
    return mono, analysis, rationale


# ---- 音域 / 速度 / 时长 ------------------------------------------------------
def transpose_shift(pitches):
    lo, hi = min(pitches), max(pitches)
    for allowed in ((MIDI_LO, MIDI_HI), (MIDI_ALLOW_LO, MIDI_ALLOW_HI)):
        a, b = allowed
        s_lo, s_hi = a - lo, b - hi
        if s_lo <= s_hi:
            if s_lo <= 0 <= s_hi:
                return 0, allowed
            return int(s_lo if s_lo > 0 else s_hi), allowed
    return 0, (MIDI_ALLOW_LO, MIDI_ALLOW_HI)


def bar_ticks(mid, tpb):
    for tr in mid.tracks:
        for msg in tr:
            if msg.type == "time_signature":
                return int(tpb * 4 * msg.numerator / msg.denominator)
    return tpb * 4


def decide_repeats(seg_sec):
    best, best_score = None, None
    for n in range(1, 17):
        total = n * seg_sec + LEAD_SEC + TAIL_SEC
        if total > DUR_HI:
            break
        if total < DUR_LO:
            continue
        score = (0, n) if DUR_PREF_LO <= total <= DUR_PREF_HI else (
            min(abs(total - DUR_PREF_LO), abs(total - DUR_PREF_HI)), n)
        if best_score is None or score < best_score:
            best, best_score = n, score
    return best


# ---- MIDI 写出（真值文件） ---------------------------------------------------
def write_midi(tracks, tpb, path, bpm, time_sig=(4, 4)):
    mid = mido.MidiFile(type=1, ticks_per_beat=tpb)
    cond = mido.MidiTrack()
    mid.tracks.append(cond)
    cond.append(mido.MetaMessage("set_tempo", tempo=int(round(60e6 / bpm)), time=0))
    cond.append(mido.MetaMessage("time_signature", numerator=time_sig[0],
                                 denominator=time_sig[1], time=0))
    for t in tracks:
        tr = mido.MidiTrack()
        mid.tracks.append(tr)
        tr.append(mido.MetaMessage("track_name", name=t["name"], time=0))
        tr.append(mido.Message("program_change", program=t["program"], channel=0, time=0))
        ev = []
        for st, en, p, v in t["notes"]:
            ev.append((int(st), 2, int(p), int(v)))
            ev.append((int(en), 1, int(p), 0))
        ev.sort(key=lambda e: (e[0], e[1]))
        last = 0
        for tick, prio, p, v in ev:
            d = tick - last
            last = tick
            tr.append(mido.Message("note_on" if prio == 2 else "note_off",
                                   note=p, velocity=v, channel=0, time=d))
        tr.append(mido.MetaMessage("end_of_track", time=0))
    mid.save(path)


def repeat_notes(seg_notes, seg_len, n_rep, offset):
    out = []
    for r in range(n_rep):
        shift = offset + r * seg_len
        for st, en, p, v in seg_notes:
            out.append((st + shift, en + shift, p, v))
    return out


# ---- 练习曲变体：严重偏离，但可对齐 ------------------------------------------
def jitter_legato_boundaries(notes, tpb, tempos, rng, drift_frac=0.055):
    """Shift note onsets on legato material while preserving everything that matters.

    The extracted melodies are fully legato: note i ends exactly where note i+1
    begins (100% of gaps are <= 2.7 ms), so an onset and the previous offset are
    the *same* boundary. Moving onsets independently would create overlaps and
    silently drop notes.

    So the shared boundaries are moved instead. That keeps, exactly:
      * the note count and the note order,
      * strict monophony (no overlap, no gap),
      * the total duration (first onset and final offset stay fixed).
    Each boundary may only move far enough that its two adjacent notes both keep
    at least a quarter of their original length, so short ornaments survive.
    """
    n = len(notes)
    if n < 2:
        return list(notes), []

    orig = [x[0] for x in notes] + [notes[-1][1]]     # n + 1 boundaries
    durs = [notes[i][1] - notes[i][0] for i in range(n)]
    floor_ticks = int(round(tpb * 0.020 * (60e6 / tempos[0][1]) / 60.0))  # 20 ms
    min_dur = [max(int(0.25 * d), floor_ticks) for d in durs]
    span = max(1, orig[-1] - orig[0])

    new = list(orig)
    for i in range(1, n):                              # internal boundaries only
        dur_sec = tick_to_sec(min(durs[i - 1], durs[i]), tpb, tempos)
        cap = min(0.090, 0.30 * dur_sec)
        jitter = float(rng.uniform(-cap, cap))
        frac = (orig[i] - orig[0]) / span
        shift = signed_sec_to_tick(jitter - drift_frac * frac, tpb, tempos)

        # Note i-1 is [new[i-1], new[i]] and note i is [new[i], new[i+1]], so the
        # boundary may move only while both neighbours keep at least min_dur.
        lo = new[i - 1] + min_dur[i - 1]
        hi = orig[i + 1] - min_dur[i]
        if hi < lo:
            new[i] = orig[i]                           # no room: leave it alone
        else:
            new[i] = min(max(orig[i] + shift, lo), hi)

    out = [(new[i], new[i + 1], notes[i][2], notes[i][3]) for i in range(n)]
    labels = []
    for i in range(n):
        labels.append({"音序号": i,
                       "标准起音秒": round(tick_to_sec(orig[i], tpb, tempos), 4),
                       "实际起音秒": round(tick_to_sec(new[i], tpb, tempos), 4),
                       "注入起音偏移秒": round(tick_to_sec(new[i], tpb, tempos) -
                                               tick_to_sec(orig[i], tpb, tempos), 4),
                       "标准音高": notes[i][2]})
    return out, labels


def build_variant(kind, notes, tpb, tempos, seed):
    """返回 (notes, labels)。notes 为 (st_tick, en_tick, midi, velocity[, cents])。"""
    rng = np.random.RandomState(seed)
    notes = [list(n) for n in notes]
    labels = []
    cents = [0.0] * len(notes)

    if kind == "01_offpitch":
        # 整体走调：大多数音偏离 45~115 音分。仍然落在同一个音级附近，
        # 所以"音高检测"应当报出正确音名、但音分偏差极大 —— 这正是要测的。
        for i, n in enumerate(notes):
            if rng.rand() < 0.85:
                mag = float(rng.uniform(45, 115))
                c = mag * (1 if rng.rand() < 0.68 else -1)   # 偏高的居多，像吹奏偏紧
            else:
                c = float(rng.uniform(-25, 25))
            cents[i] = c
            labels.append({"音序号": i,
                           "标准起音秒": round(tick_to_sec(n[0], tpb, tempos), 4),
                           "标准音高": n[2], "注入音分偏差": round(c, 1)})

    elif kind == "02_timing":
        # 抢拍/拖拍：保序抖动，音符数与次序严格不变，总时长不变。
        notes, labels = jitter_legato_boundaries(notes, tpb, tempos, rng)
        cents = [0.0] * len(notes)

    elif kind == "03_dynamics":
        # 气息不匀：力度在 0.18~1.35 倍之间剧烈起伏，并有若干音几乎听不见。
        for i, n in enumerate(notes):
            base = float(rng.uniform(0.30, 1.35))
            if rng.rand() < 0.10:
                base = float(rng.uniform(0.12, 0.25))     # 几乎没声音
            v = int(max(3, min(127, round(n[3] * base))))
            labels.append({"音序号": i,
                           "标准起音秒": round(tick_to_sec(n[0], tpb, tempos), 4),
                           "标准音高": n[2], "标准力度": n[3],
                           "实际力度": v, "力度倍率": round(base, 3)})
            n[3] = v

    elif kind == "04_wrongnotes":
        # 错音：在足够长的音上，约 15% 吹错 1~3 个半音。
        elig = [i for i, n in enumerate(notes)
                if tick_to_sec(n[1] - n[0], tpb, tempos) >= 0.150]
        n_wrong = max(1, int(round(0.15 * len(elig)))) if elig else 0
        chosen = sorted(rng.choice(elig, size=min(n_wrong, len(elig)),
                                   replace=False).tolist()) if elig else []
        for i in chosen:
            n = notes[i]
            step = int(rng.choice([-3, -2, -1, 1, 2, 3]))
            labels.append({"音序号": i,
                           "标准起音秒": round(tick_to_sec(n[0], tpb, tempos), 4),
                           "时长秒": round(tick_to_sec(n[1] - n[0], tpb, tempos), 4),
                           "标准音高": n[2], "实际音高": n[2] + step,
                           "注入半音误差": step, "注入音分误差": step * 100})
            n[2] = int(np.clip(n[2] + step, 21, 108))

    elif kind == "05_dropouts":
        # 漏音断句：约 12% 的音被漏掉，成组出现，形成断裂乐句。
        drop = set()
        i = 0
        while i < len(notes):
            if rng.rand() < 0.12:
                run = int(rng.choice([1, 1, 2, 3]))
                for k in range(run):
                    if i + k < len(notes):
                        drop.add(i + k)
                i += run
                continue
            i += 1
        keep = []
        for i, n in enumerate(notes):
            if i in drop:
                labels.append({"音序号": i,
                               "标准起音秒": round(tick_to_sec(n[0], tpb, tempos), 4),
                               "时长秒": round(tick_to_sec(n[1] - n[0], tpb, tempos), 4),
                               "标准音高": n[2], "处理": "漏吹（删除）"})
            else:
                keep.append(n)
        notes = keep
        cents = [0.0] * len(notes)

    else:
        raise ValueError(f"未知变体 {kind}")

    return [tuple(n) for n in notes], cents, labels


# ---- 真值音符表 --------------------------------------------------------------
def expected_rows(notes, tpb, tempos):
    rows = []
    for i, (st, en, p, v) in enumerate(sorted(notes, key=lambda n: n[0])):
        s, e = tick_to_sec(st, tpb, tempos), tick_to_sec(en, tpb, tempos)
        rows.append({
            "音序号": i, "起音秒": round(s, 4), "结束秒": round(e, 4),
            "时长秒": round(e - s, 4), "MIDI音高": p, "音名": midi_name(p),
            "频率Hz": round(hz(p), 6), "力度": v,
        })
    return rows


def write_csv(rows, path):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ---- 质检 --------------------------------------------------------------------
def _setup_cjk_font():
    """Use an installed CJK font so the QA plots render Chinese labels."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt

    available = {f.name for f in fm.fontManager.ttflist}
    for c in ("Hiragino Sans GB", "PingFang HK", "PingFang SC", "Arial Unicode MS",
              "Heiti TC", "STHeiti", "Songti SC"):
        if c in available:
            plt.rcParams["font.sans-serif"] = [c]
            break
    plt.rcParams["axes.unicode_minus"] = False


def qc_pitch(wav_path, rows):
    """Pitch sanity check on the clean reference render.

    Runs at the file's native 44.1 kHz. pYIN at 22.05 kHz intermittently locks
    onto the subharmonic of D5/B4 (reporting exactly one octave low), which is an
    analyser artefact rather than an audio defect; see research notes.
    """
    import librosa

    y, sr = librosa.load(wav_path, sr=None, mono=True)
    pitches = [r["MIDI音高"] for r in rows]
    fmin = max(55.0, float(hz(min(pitches) - 5)))
    fmax = min(float(sr) / 2 - 100, float(hz(max(pitches) + 5)))
    f0, vflag, _ = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr,
                                frame_length=2048, hop_length=256)
    times = librosa.times_like(f0, sr=sr, hop_length=256)
    stable = [r for r in rows if r["时长秒"] >= 0.150]
    errs = []
    for r in stable:
        s = r["起音秒"] + 0.2 * r["时长秒"]
        e = r["起音秒"] + 0.8 * r["时长秒"]
        m = (times >= s) & (times <= e) & vflag & np.isfinite(f0) & (f0 > 0)
        if not m.any():
            errs.append(None)
            continue
        est = 69 + 12 * np.log2(float(np.median(f0[m])) / A4_HZ)
        errs.append((est - r["MIDI音高"]) * 100.0)
    got = [e for e in errs if e is not None]
    ok = sum(1 for e in got if abs(e) < 50)
    return {"稳定音数": len(stable), "检出数": len(got), "50音分内": ok,
            "通过率": round(ok / len(stable), 4) if stable else 0.0,
            "音分误差中位数": round(float(np.median([abs(e) for e in got])), 2) if got else None,
            "八度误判数": sum(1 for e in got if abs(abs(e) - 1200) < 50),
            "通过": bool(stable) and ok / len(stable) >= 0.90}


def verify_injections(wav_path, rows, kind, labels):
    """确认注入的偏差在渲染音频里真的可测。"""
    import librosa

    pitches = [r["MIDI音高"] for r in rows]
    y, sr = librosa.load(wav_path, sr=None, mono=True)
    f0, vflag, _ = librosa.pyin(y, fmin=max(55.0, float(hz(min(pitches) - 5))),
                                fmax=min(float(sr) / 2 - 100,
                                         float(hz(max(pitches) + 5))),
                                sr=sr, frame_length=2048, hop_length=256)
    times = librosa.times_like(f0, sr=sr, hop_length=256)

    def est_for(r, pad_lo=0.3, pad_hi=0.8):
        s = r["起音秒"] + pad_lo * r["时长秒"]
        e = r["起音秒"] + pad_hi * r["时长秒"]
        m = (times >= s) & (times <= e) & vflag & np.isfinite(f0) & (f0 > 0)
        if not m.any():
            return None
        return 69 + 12 * np.log2(float(np.median(f0[m])) / A4_HZ)

    if kind == "01_offpitch":
        diffs = []
        for l in labels:
            r = rows[l["音序号"]]
            if r["时长秒"] < 0.150:
                continue
            est = est_for(r)
            if est is None:
                continue
            measured = (est - r["MIDI音高"]) * 100.0
            diffs.append(measured - l["注入音分偏差"])
        if not diffs:
            return {"检查数": 0}
        return {"检查数": len(diffs),
                "注入量与实测差的中位绝对值音分": round(float(np.median(np.abs(diffs))), 2),
                "最大绝对误差音分": round(float(np.max(np.abs(diffs))), 2)}
    if kind == "04_wrongnotes":
        hit = 0
        for l in labels:
            r = rows[l["音序号"]]
            est = est_for(r)
            if est is None:
                continue
            if abs((est - l["实际音高"]) * 100) < 50:
                hit += 1
        return {"检查数": len(labels), "实测与错音一致数": hit}
    return {}


def qa_plots(wav_path, rows, out_wave, out_pitch, title):
    _setup_cjk_font()
    import matplotlib.pyplot as plt
    import librosa

    y, sr = librosa.load(wav_path, sr=None, mono=True)
    t = np.arange(len(y)) / sr

    fig, ax = plt.subplots(figsize=(14, 3.2))
    ax.plot(t, y, linewidth=0.4, color="#333")
    for r in rows:
        ax.axvline(r["起音秒"], color="#d33", alpha=0.35, linewidth=0.5)
    ax.set_xlabel("时间 (秒)")
    ax.set_ylabel("振幅")
    ax.set_title(f"{title} — 波形与标准起音位置")
    fig.tight_layout()
    fig.savefig(out_wave, dpi=110)
    plt.close(fig)

    pitches = [r["MIDI音高"] for r in rows]
    f0, vflag, _ = librosa.pyin(y, fmin=max(55.0, float(hz(min(pitches) - 5))),
                                fmax=min(float(sr) / 2 - 100,
                                         float(hz(max(pitches) + 5))),
                                sr=sr, frame_length=2048, hop_length=256)
    tt = librosa.times_like(f0, sr=sr, hop_length=256)
    est = 69 + 12 * np.log2(np.where((f0 > 0) & vflag, f0, np.nan) / A4_HZ)

    fig, ax = plt.subplots(figsize=(14, 4.2))
    # The detected-pitch dots are dense and would paint over the reference. Draw
    # them first, with the expected segments on top at a high zorder, so both are
    # visible in the saved image.
    ax.plot(tt, est, ".", markersize=1.6, color="#1f6feb", label="检出音高 (pyin)",
            zorder=2)
    for r in rows:
        ax.plot([r["起音秒"], r["结束秒"]], [r["MIDI音高"]] * 2,
                color="#d33", linewidth=2.2, solid_capstyle="butt", zorder=3,
                label="标准音高 (MIDI)" if r["音序号"] == 0 else None)
    ax.set_xlabel("时间 (秒)")
    ax.set_ylabel("MIDI 音高")
    ax.set_title(f"{title} — 标准音高与检出音高")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_pitch, dpi=110)
    plt.close(fig)


# ---- 下载 --------------------------------------------------------------------
def fetch(url, dest, timeout=180):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (dataset-build)"})
    data = urllib.request.urlopen(req, timeout=timeout).read()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)
    return dest


def get_source_midi(spec):
    if spec["zip_url"]:
        zpath = os.path.join(DL, spec["id"] + ".zip")
        fetch(spec["zip_url"], zpath)
        return zipfile.ZipFile(zpath).read(spec["zip_member"])
    p = os.path.join(DL, spec["id"] + ".mid")
    fetch(spec["midi_url"], p)
    return open(p, "rb").read()


# ---- 单首构建 ----------------------------------------------------------------
def build_song(spec, midi_bytes, sampler, out_root):
    sid = spec["id"]
    cn = CN_TITLE.get(sid, spec["title"])
    d = os.path.join(out_root, f"{sid[:2]}_{cn}")
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(os.path.join(d, "练习曲"))
    os.makedirs(os.path.join(d, "乐谱与标注"))
    os.makedirs(os.path.join(d, "质检图"))

    src_path = os.path.join(d, "乐谱与标注", "source.mid")
    with open(src_path, "wb") as f:
        f.write(midi_bytes)

    mid = load_midi(src_path)
    tpb = mid.ticks_per_beat
    tempos = tempo_map(mid)
    orig_bpm = 60e6 / tempos[0][1]
    tps = tpb * orig_bpm / 60.0

    mono, analysis, rationale = choose_melody(mid, spec, tps)
    shift, allowed = transpose_shift([n[2] for n in mono])
    mono_t = [(st, en, p + shift, v) for st, en, p, v in mono]

    bar = bar_ticks(mid, tpb)
    t0 = (min(n[0] for n in mono_t) // bar) * bar
    t1 = ((max(n[1] for n in mono_t) + bar - 1) // bar) * bar
    seg_len = t1 - t0
    seg_notes = [(st - t0, en - t0, p, v) for st, en, p, v in mono_t if t0 <= st and en <= t1]
    seg_sec = tick_to_sec(seg_len, tpb, tempos)

    n_rep = decide_repeats(seg_sec)
    if n_rep is None:
        raise RuntimeError(f"{sid}: 无法满足 {DUR_LO}-{DUR_HI}s（段长 {seg_sec:.2f}s）")

    lead = sec_to_tick(LEAD_SEC, tpb, tempos)
    tail = sec_to_tick(TAIL_SEC, tpb, tempos)
    melody_final = repeat_notes(seg_notes, seg_len, n_rep, lead)

    # 完整版：所有声部都用真实口琴采样渲染
    full_notes_sec = []
    for i, tr in enumerate(mid.tracks):
        r = read_track(tr)
        if not r["notes"]:
            continue
        sel = [(st, en, p + shift, v) for st, en, p, v in r["notes"] if t0 <= st and en <= t1]
        if not sel:
            continue
        full_notes_sec += repeat_notes([(st - t0, en - t0, p, v) for st, en, p, v in sel],
                                       seg_len, n_rep, lead)

    mel_end = max((en for _, en, _, _ in melody_final), default=lead)
    full_end = max((en for _, en, _, _ in full_notes_sec), default=lead)
    total_ticks = max(mel_end, full_end) + tail
    total_sec = tick_to_sec(total_ticks, tpb, tempos)

    rows = expected_rows(melody_final, tpb, tempos)
    write_csv(rows, os.path.join(d, "乐谱与标注", "expected_notes.csv"))

    mel_path = os.path.join(d, "乐谱与标注", "melody.mid")
    write_midi([{"name": "melody", "program": GM_HARMONICA, "notes": melody_final}],
               tpb, mel_path, orig_bpm)

    def to_sec(notes):
        return [(tick_to_sec(st, tpb, tempos), tick_to_sec(en, tpb, tempos), p, v)
                for st, en, p, v in notes]

    ref_full_wav = os.path.join(d, "原曲_完整版.wav")
    ref_mel_wav = os.path.join(d, "标准旋律版.wav")
    sampler.render(to_sec(full_notes_sec), total_sec, ref_full_wav, PEAK_TARGET_DB)
    sampler.render(to_sec(melody_final), total_sec, ref_mel_wav, PEAK_TARGET_DB)

    # 练习曲
    variants_meta = {}
    for vi, (kind, cn_name, desc) in enumerate(VARIANTS):
        vnotes, vcents, labels = build_variant(kind, melody_final, tpb, tempos,
                                               seed=SEED + 1000 * vi + int(sid[:2]))
        vnotes_sec = [(tick_to_sec(st, tpb, tempos), tick_to_sec(en, tpb, tempos), p, v, c)
                      for (st, en, p, v), c in zip(vnotes, vcents)]
        wav = os.path.join(d, "练习曲", f"{cn_name}.wav")
        sampler.render(vnotes_sec, total_sec, wav, PEAK_TARGET_DB)
        entry = {"文件": f"练习曲/{cn_name}.wav", "维度": desc,
                 "音数": len(vnotes), "偏差记录数": len(labels),
                 "音频": wav_info(wav), "偏差": labels}
        entry["偏差可测性"] = verify_injections(wav, rows, kind, labels)
        variants_meta[kind] = entry

    qc = qc_pitch(ref_mel_wav, rows)
    qa_plots(ref_mel_wav, rows, os.path.join(d, "质检图", "qa_waveform.png"),
             os.path.join(d, "质检图", "qa_pitch.png"), f"{sid[:2]} {cn}")

    pitches = [r["MIDI音高"] for r in rows]
    duration = wav_info(ref_mel_wav)["时长秒"]
    metadata = {
        "编号": sid[:2], "曲名": cn, "英文曲名": spec["title"],
        "作曲": spec["composer"], "编配": spec.get("arranger"),
        "原始编制": spec.get("instrument"),
        "来源站点": "Mutopia Project", "来源页面": spec["page"], "许可": spec["license"],
        "全部音频均为口琴": True,
        "音色": "VCSL Hohner Super64 真实采样（CC0-1.0）",
        "旋律轨选择": {"模式": spec["mode"], "源轨": spec["track"], "依据": rationale},
        "移调半音": shift,
        "音域策略": {"优先": [MIDI_LO, MIDI_HI], "实际": list(allowed)},
        "原始速度BPM": round(orig_bpm, 3), "测试速度BPM": round(orig_bpm, 3),
        "小节ticks": bar, "重复遍数": n_rep, "段长秒": round(seg_sec, 3),
        "时长秒": duration, "前导静音秒": LEAD_SEC, "尾部静音秒": TAIL_SEC,
        "采样率": SR, "声道": 1, "位深": 16, "峰值dBFS": PEAK_TARGET_DB,
        "音数": len(rows), "最低音": midi_name(min(pitches)), "最高音": midi_name(max(pitches)),
        "最低MIDI": min(pitches), "最高MIDI": max(pitches),
        "文件": {"原曲": "原曲_完整版.wav", "标准旋律": "标准旋律版.wav",
                 "练习曲": [f"练习曲/{c}.wav" for _, c, _ in VARIANTS],
                 "真值MIDI": "乐谱与标注/melody.mid",
                 "真值音符表": "乐谱与标注/expected_notes.csv"},
        "质检": qc,
    }
    with open(os.path.join(d, "乐谱与标注", "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    with open(os.path.join(d, "乐谱与标注", "practice_variants.json"), "w",
              encoding="utf-8") as f:
        json.dump({
            "编号": sid[:2], "曲名": cn, "随机种子": SEED,
            "说明": "真值永远是 melody.mid。每个练习曲只在一个维度上严重偏离，"
                    "总时长与标准旋律版一致，音符次序不变，因此始终可对齐。"
                    "偏差栏是基准答案，不是对 expected_notes.csv 的修正。",
            "练习曲": variants_meta,
        }, f, indent=2, ensure_ascii=False)

    with open(os.path.join(d, "乐谱与标注", "midi_analysis.json"), "w",
              encoding="utf-8") as f:
        json.dump({"编号": sid[:2], "每拍ticks": tpb, "原始BPM": round(orig_bpm, 3),
                   "轨道分析": analysis,
                   "旋律判定": {"源轨": spec["track"], "模式": spec["mode"],
                                "依据": rationale},
                   "结果": {"音数": len(rows), "最低MIDI": min(pitches),
                            "最高MIDI": max(pitches), "移调": shift,
                            "重复遍数": n_rep, "时长秒": duration}},
                  f, indent=2, ensure_ascii=False)

    with open(os.path.join(d, "来源与许可.txt"), "w", encoding="utf-8") as f:
        f.write(f"""曲名：      {cn}（{spec['title']}）
作曲：      {spec['composer']}
编配：      {spec.get('arranger') or '无'}
来源站点：  Mutopia Project（https://www.mutopiaproject.org/）
来源页面：  {spec['page']}
原始编制：  {spec.get('instrument') or '无'}
许可：      {spec['license']}
MIDI 地址： {spec['midi_url'] or spec['zip_url']}
            {('（压缩包内文件：' + spec['zip_member'] + '）') if spec.get('zip_member') else ''}
获取日期：  {json.load(open(SOURCES, encoding='utf-8')).get('retrieved')}

许可说明见 https://www.mutopiaproject.org/legal.html
本 MIDI 按上述许可再分发。

本目录下所有 WAV 均由该 MIDI 离线合成，使用 VCSL（CC0-1.0）的
Hohner Super64 真实口琴采样，音色为口琴。数据集中不含钢琴。
""")

    return metadata, qc, variants_meta


def wav_info(path):
    y, sr = sf.read(path, dtype="float32", always_2d=False)
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    return {"采样率": sr, "声道": 1 if y.ndim == 1 else y.shape[1],
            "时长秒": round(len(y) / sr, 3), "峰值dBFS": round(db(peak), 2)}


# ---- 汇总输出 ----------------------------------------------------------------
def write_manifest(metas, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["编号", "曲名", "时长秒", "音数", "最低音", "最高音", "BPM",
                    "移调", "许可", "练习曲数", "质检"])
        for m in metas:
            w.writerow([m["编号"], m["曲名"], m["时长秒"], m["音数"],
                        m["最低音"], m["最高音"], m["测试速度BPM"], m["移调半音"],
                        m["许可"], len(m["文件"]["练习曲"]),
                        "通过" if m["质检"]["通过"] else "不通过"])


def write_readme(metas, path):
    lines = [
        "# 口琴 MVP 金标准测试集",
        "",
        "10 首严格配对的曲子，用于验证音高检测（FFT / 自相关 / YIN / pYIN / MPM）、",
        "起音检测、音符切分、MIDI 与音频对齐、DTW，以及演奏与参考版本的对比。",
        "",
        "**全部音频都是口琴。** 原曲、标准旋律版、所有练习曲，一律使用 VCSL 的",
        "Hohner Super64 真实口琴采样渲染。数据集里没有钢琴。",
        "",
        "**真值永远是 MIDI，绝不是音频。**",
        "",
        "## 目录结构",
        "",
        "```",
        "01_奇异恩典/",
        "    原曲_完整版.wav            完整编配（口琴）",
        "    标准旋律版.wav             单声部旋律（口琴），同时是干净基准",
        "    练习曲/",
        "        01_音准走调.wav        整体走调",
        "        02_节奏抢拖.wav        抢拍拖拍",
        "        03_气息不匀.wav        力度忽强忽弱",
        "        04_错音.wav            吹错孔位",
        "        05_漏音断句.wav        漏吹成句",
        "    乐谱与标注/",
        "        source.mid             原始 Mutopia MIDI",
        "        melody.mid             提取出的单声部旋律  <-- 真值",
        "        expected_notes.csv     由 melody.mid 导出",
        "        practice_variants.json 每个练习曲注入的偏差（基准答案）",
        "        metadata.json          来源、移调、速度、质检",
        "        midi_analysis.json     逐轨分析与旋律判定依据",
        "    质检图/",
        "        qa_waveform.png        波形与标准起音位置",
        "        qa_pitch.png           标准音高与检出音高",
        "    来源与许可.txt",
        "```",
        "",
        "## 练习曲的设计原则",
        "",
        "每个练习曲只在一个维度上严重偏离，并且保证仍然可对齐：",
        "",
        "1. **总时长与标准旋律版完全一致**，对齐算法不会遇到长度歧义；",
        "2. **音符次序不变**（漏音除外，其删除有完整记录），不会重排或互相吞并；",
        "3. **抖动按音符自身时长设上限**，短倚音不会被吃掉；",
        "4. 注入的偏差全部记录在 `practice_variants.json`，可用于给对比算法打分。",
        "",
        "## 复现",
        "",
        "```bash",
        "bash setup.sh                     # 依赖",
        "python prepare_samples.py         # 下载并校验口琴采样",
        "python build_dataset.py           # 重建全部",
        "python build_dataset.py --only 01 # 重建单首",
        "```",
        "",
        "固定随机种子：`seed = 42`。音频为离线合成，非录音。",
        "",
        "## 曲目",
        "",
        "| 编号 | 曲名 | 时长(秒) | 音数 | 音域 | BPM | 移调 | 许可 | 质检 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m in metas:
        lines.append(
            f"| {m['编号']} | {m['曲名']} | {m['时长秒']} | {m['音数']} | "
            f"{m['最低音']}-{m['最高音']} | {m['测试速度BPM']:g} | "
            f"{m['移调半音']:+d} | {m['许可']} | "
            f"{'通过' if m['质检']['通过'] else '不通过'}"
            f"（{m['质检']['通过率']:.0%}） |")
    lines += [
        "",
        "## 构建说明",
        "",
        "- 旋律提取按负责人简报：优先使用有明确命名的旋律轨；多声部谱表取记谱的",
        "  高声部/女高音声部（已与 Mutopia 的 LilyPond 原谱逐音核对），绝不盲目取最高轨。",
        "  逐首依据见 `midi_analysis.json`。",
        "- `melody.mid` 严格单声部（重叠 < 30ms）。",
        "- 音域按整半音移调进 MIDI 60-84；音程关系与移调量都记录在 `metadata.json`。",
        "- 过短的曲子按小节边界重复（无交叉淡化）以达到 45-120 秒。",
        "- 所有 WAV：44100 Hz、单声道、PCM 16 位，峰值归一化到约 -3 dBFS。",
        "- 0.4 秒前导与尾部静音**包含在** `melody.mid` 内，因此 `expected_notes.csv` 与音频严格对应。",
        "",
        "## 质检",
        "",
        "每首在 `标准旋律版.wav` 上做自动音高校验：对每个 ≥150ms 的音，取该音",
        "20%-80% 区间的 pyin 中位频率，须与 MIDI 音高相差 50 音分以内，且通过率 ≥90%。",
        "音准走调变体额外验证注入的音分偏差确实能在渲染音频中测出。",
        "",
        "另见 `dataset_manifest.csv` 与 `THIRD_PARTY_LICENSES.md`。",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_third_party(path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("""# 第三方许可

本数据集不含任何商业录音。全部素材均为公有领域或开放许可。

## 乐谱 / MIDI 来源 —— Mutopia Project

<https://www.mutopiaproject.org/>

- 站点许可：<https://www.mutopiaproject.org/legal.html>
- 逐曲许可记录在各曲的 `来源与许可.txt` 与 `metadata.json`。
  本数据集的曲子为**公有领域**或**知识共享 署名-相同方式共享 3.0**。

## 口琴采样 —— VCSL（Versilian Community Sample Library）

<https://github.com/sgossner/VCSL> — **许可：CC0-1.0**

- 使用的采样：`Aerophones/Free Aerophones/Harmonica-Hohner-Super64/Sustains/{Normal,Vib}`
- 采样文件的音高由本项目独立测量与校验，未依赖文件名
  （见 `prepare_samples.py` 与 `samples_measured.json`）。

## 渲染音频

本数据集所有 WAV 均为**离线合成**，使用上述口琴采样渲染 MIDI 而来。
数据集中没有钢琴，也没有任何演奏录音，因此不涉及演奏者或录音版权。

## 工具

librosa（ISC）、mido（MIT）、NumPy（BSD-3-Clause）、SciPy（BSD-3-Clause）、
SoundFile（BSD-3-Clause）、Matplotlib（PSF-based）。
""")


# ---- 主流程 ------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只构建编号以此开头的曲子")
    args = ap.parse_args()

    if not os.path.exists(os.path.join(VCSL_DIR, "samples_measured.json")):
        sys.exit(f"缺少口琴采样音高表：{VCSL_DIR}\n请先运行：python prepare_samples.py")
    sys.path.insert(0, HERE)
    from harmonica_sampler import HarmonicaSampler

    sampler = HarmonicaSampler(VCSL_DIR, sr=SR)
    log(f"已加载口琴采样 {len(sampler.samples)} 个")

    os.makedirs(DL, exist_ok=True)
    songs = json.load(open(SOURCES, encoding="utf-8"))["songs"]
    if args.only:
        songs = [s for s in songs if s["id"].startswith(args.only)]
        if not songs:
            sys.exit(f"没有匹配 --only {args.only} 的曲子")

    metas, failures = [], []
    for spec in songs:
        cn = CN_TITLE.get(spec["id"], spec["title"])
        log(f"=== {spec['id'][:2]} {cn}（{spec['title']}）")
        try:
            m, qc, _ = build_song(spec, get_source_midi(spec), sampler, HERE)
            metas.append(m)
            log(f"{'通过' if qc['通过'] else '不通过'} 时长={m['时长秒']}s "
                f"音数={m['音数']} 音域={m['最低音']}-{m['最高音']} "
                f"移调={m['移调半音']:+d} 重复={m['重复遍数']} "
                f"质检={qc['通过率']:.0%}（音分误差中位数={qc['音分误差中位数']}）")
        except Exception as e:
            log(f"错误 {type(e).__name__}: {e}")
            failures.append((spec["id"], f"{type(e).__name__}: {e}"))

    if not args.only:
        if metas:
            write_manifest(metas, os.path.join(HERE, "dataset_manifest.csv"))
            write_third_party(os.path.join(HERE, "THIRD_PARTY_LICENSES.md"))
            write_readme(metas, os.path.join(HERE, "README.md"))
        # 试听目录：扁平复制，中文文件名
        if os.path.isdir(LISTEN):
            shutil.rmtree(LISTEN)
        os.makedirs(LISTEN)
        for m in metas:
            d = os.path.join(HERE, f"{m['编号']}_{m['曲名']}")
            shutil.copy(os.path.join(d, "原曲_完整版.wav"),
                        os.path.join(LISTEN, f"{m['编号']}_{m['曲名']}_原曲.wav"))
            shutil.copy(os.path.join(d, "标准旋律版.wav"),
                        os.path.join(LISTEN, f"{m['编号']}_{m['曲名']}_标准旋律版.wav"))
            for _, cn_name, _ in VARIANTS:
                shutil.copy(os.path.join(d, "练习曲", f"{cn_name}.wav"),
                            os.path.join(LISTEN, f"{m['编号']}_{m['曲名']}_{cn_name}.wav"))

    print("\n===== 汇总 =====")
    for m in metas:
        print(f"{m['编号']} {m['曲名']:12s} {m['时长秒']:7.2f}s {m['音数']:4d}音 "
              f"{m['最低音']:>4s}-{m['最高音']:<4s} {m['测试速度BPM']:6.1f}BPM "
              f"{m['移调半音']:+3d} {'通过' if m['质检']['通过'] else '不通过'}")
    if failures:
        print("\n失败：")
        for sid, err in failures:
            print(f"  {sid}: {err}")
    allpass = len(metas) == 10 and all(m["质检"]["通过"] for m in metas) and not failures
    print(f"\n已构建 {len(metas)}/10；质检全通过："
          f"{all(m['质检']['通过'] for m in metas) if metas else False}")
    return 0 if allpass else 1


if __name__ == "__main__":
    sys.exit(main())
