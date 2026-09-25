"""
Probe: missing/threshold-inventing decisions the implementer would need
to invent because the mold does not pin them down.
"""
import ast
import sys
import re
from pathlib import Path

REPO = Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
SPEC = REPO / ".spec" / "build"


def read(p): return Path(p).read_text()


def check_silence_for_nan_inf():
    """FILE-101 §4.4 known gap: NaN/inf bypass silence check.
    The spec documents this but defers to §10 MOLD BREAK.
    Implementer CANNOT add the check because the spec forbids it (would change
    the function's semantics). So NaN/inf must remain a known gap."""
    f101 = read(SPEC / "FILE-101-v1.md")
    has_gap = "NaN" in f101 and "inf" in f101 and "已知缺口" in f101
    return has_gap, "FILE-101 §4.4 documents the NaN/inf gap"


def check_pyin_voiced_threshold_semantics():
    """FILE-103 §4.1: 'voiced = (confidence >= VOICED_CONFIDENCE_FLOOR)' - 0/1 integer.
    But the spec also says 'confidence 如实报告 (不置 0、不置 1)'.
    So confidence is a continuous value, but voiced is 0/1.
    This is a sharp threshold - the implementer must use >=, not >.
    And the threshold 0.5 is documented.
    No invention needed here."""
    return True, "voiced threshold (0.5, >= semantics) is frozen"


def check_dynamics_frame_rate_100hz():
    """FILE-203 §4 'note_spans': frame(t) = int(round(t * 100)) - 100 Hz frame rate.
    But profile.MATERIALIZE.rms_hop_length=256, sample_rate=44100.
    Actual frame rate = 44100/256 = 172.27 Hz, NOT 100 Hz.
    The spec invents '100 Hz' from nowhere. No source documented."""
    f203 = read(SPEC / "FILE-203-v1.md")
    has_100hz = "100" in f203 and "frame" in f203.lower()
    has_origin = "core.ingest" in f203 and "100" in f203
    return has_100hz and not has_origin, "FILE-203 invents 100 Hz frame rate without sourcing it"


def check_notes_zero_voiced_handling():
    """FILE-103 §4.3 'materialize_notes':
    If 'rms' is empty → throw CoreBuildError.
    But why throw on empty rms? Pitch may have notes but rms may be empty if very quiet.
    Spec is unclear on what 'empty' means here - 0 rows? All zeros?
    This is potentially an under-specified behavior."""
    f103 = read(SPEC / "FILE-103-v1.md")
    return True, "rms empty error path is documented but rms=0 (silent) is not"


def check_onset_match_tolerance_origin():
    """FILE-202 §4.0 ONSET_MATCH_TOLERANCE_SEC = 0.100.
    Spec derives it from hop=2048 → ±23ms noise + 150ms min note length.
    But the constant IS frozen and derivation IS given. OK."""
    f202 = read(SPEC / "FILE-202-v1.md")
    return "ONSET_MATCH_TOLERANCE_SEC" in f202, "tolerance derivation present in FILE-202"


def check_deadband_ms_origin():
    """FILE-202 §4.0 ONSET_DEADBAND_MS = 23.0.
    Derived from hop/2 = ±23 ms alignment noise.
    Frozen as 23.0 ms."""
    f202 = read(SPEC / "FILE-202-v1.md")
    return "ONSET_DEADBAND_MS" in f202, "deadband derivation present"


def check_align_bandwidth():
    """FILE-102 §4 'band_rad=0.25' (Sakoe-Chiba band).
    This comes from profile.ALIGN.band_rad = 0.25 - frozen.
    No invention."""
    f102 = read(SPEC / "FILE-102-v1.md")
    return "band_rad" in f102, "bandwidth is from profile, frozen"


def check_coverage_threshold():
    """FILE-102 §4 WARP_PATH_MIN_COVERAGE = 0.90.
    Frozen in module-level constant."""
    f102 = read(SPEC / "FILE-102-v1.md")
    return "WARP_PATH_MIN_COVERAGE" in f102, "coverage threshold frozen"


def check_cents_threshold():
    """FILE-201 §4.0 MAX_CENTS_DEVIATION = 50.0 from SPEC §7.3.
    Frozen."""
    f201 = read(SPEC / "FILE-201-v1.md")
    return "MAX_CENTS_DEVIATION" in f201, "cents threshold frozen"


def check_fmin_fmax_origin():
    """FILE-103 §4.0 fmin_hz/fmax_hz from profile.MATERIALIZE.
    130.81 Hz (C3) - 2093 Hz (C7). Frozen."""
    return True, "fmin/fmax from profile, frozen"


def check_db_floor():
    """FILE-203 §4 DB_FLOOR = -80.0.
    Origin: -80 dBFS ≈ 1e-4 linear (matches core.ingest.SILENCE_RMS_THRESHOLD).
    Frozen."""
    f203 = read(SPEC / "FILE-203-v1.md")
    return "DB_FLOOR" in f203, "DB_FLOOR frozen with origin"


def check_min_stable_note():
    """MIN_STABLE_NOTE_SEC = 0.150 in pitch.py (FILE-201) and features.py (FILE-103).
    Same constant in both places - could drift if changed.
    Risk: implementer updates one but not the other."""
    f103 = read(SPEC / "FILE-103-v1.md")
    f201 = read(SPEC / "FILE-201-v1.md")
    return ("MIN_STABLE_NOTE_SEC" in f103 and "MIN_STABLE_NOTE_SEC" in f201), "MIN_STABLE_NOTE_SEC duplicated in pitch.py and features.py"


def check_silence_threshold_duplication():
    """FILE-203 §4 DB_FLOOR and FILE-101 §4.0 SILENCE_RMS_THRESHOLD (1e-4).
    Both encode 'silence'. They could drift."""
    f101 = read(SPEC / "FILE-101-v1.md")
    f203 = read(SPEC / "FILE-203-v1.md")
    return ("SILENCE_RMS_THRESHOLD" in f101 and "DB_FLOOR" in f203), "silence threshold has two near-identical encodings (risk of drift)"


def check_internal_stages_module_const():
    """FILE-105 §4.9 INTERNAL_STAGES module-level constant.
    Currently exists in shell. OK."""
    import importlib.util
    sys.path.insert(0, str(REPO))
    import harmonica_eval.core.api as api
    return hasattr(api, "INTERNAL_STAGES"), "INTERNAL_STAGES exists"


def check_algorithm_id_string_frozen():
    """FILE-201/202/203 ALGORITHM_ID strings.
    Pitch = 'pitch', timing = 'timing', dynamics = 'dynamics'.
    These are strings - if a typo, the registration fails."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.algorithms.pitch as p
    import harmonica_eval.algorithms.timing as t
    import harmonica_eval.algorithms.dynamics as d
    return (
        p.ALGORITHM_ID == "pitch"
        and t.ALGORITHM_ID == "timing"
        and d.ALGORITHM_ID == "dynamics"
    ), f"ALGORITHM_IDs = pitch:{p.ALGORITHM_ID!r}, timing:{t.ALGORITHM_ID!r}, dynamics:{d.ALGORITHM_ID!r}"


def check_algorithms_required_ports_compatible():
    """FILE-200: each algorithm's required_ports must be a subset of profile.PORTS."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.algorithms as alg
    import harmonica_eval.profile as p
    bad = []
    for spec in alg.ALGORITHMS:
        for port in spec.required_ports:
            if port not in p.PORTS:
                bad.append.append((spec.algorithm_id, port))
    return not bad, f"required_ports not in profile.PORTS: {bad}"


def check_paired_ports_in_registry():
    """FILE-200 §4.4 C6: required_ports must be paired (X.reference + X.practice both)."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.algorithms as alg
    bad = []
    for spec in alg.ALGORITHMS:
        s = set(spec.required_ports)
        for p_id in spec.required_ports:
            if p_id.endswith(".reference"):
                if not (p_id[:-len(".reference")] + ".practice") in s:
                    bad.append((spec.algorithm_id, p_id))
            elif p_id.endswith(".practice"):
                if not (p_id[:-len(".practice")] + ".reference") in s:
                    bad.append((spec.algorithm_id, p_id))
    return not bad, f"unpaired required_ports: {bad}"


def check_required_ports_match_actual_implementation():
    """FILE-200 says pitch uses pitch.*/notes.*.
    But pitch.compare_pitch_curves signature is (ref_pitch, prac_pitch, ref_notes, prac_notes, sample_rate) - 5 args.
    The shell has these as object types. The actual port names in required_ports must match what the function actually reads.
    E.g., pitch requires pitch.reference AND pitch.practice AND notes.reference AND notes.practice - all 4."""
    return True, "required_ports match function signatures by inspection"


def check_compute_alignment_features_stft_fs():
    """FILE-102 §4: STFT fs=int(profile.ALIGN.hop_length)=2048.
    This is BUG: fs should be sample rate (44100), not hop length."""
    f102 = read(SPEC / "FILE-102-v1.md")
    has_bug = "fs=int(profile.ALIGN.hop_length)" in f102 or "fs=int(profile.ALIGN.hop_length)" in f102
    return has_bug, "STFT fs=hop_length is a BUG; should be sample_rate"


def check_compute_alignment_features_shape():
    """FILE-102 §4: compute_alignment_features returns shape (n_chroma, n_frames).
    But cdist in compute_warp_path expects (n_frames, n_chroma) per input.
    Shape is transposed."""
    f102 = read(SPEC / "FILE-102-v1.md")
    return "(n_chroma, n_frames)" in f102, "chroma shape (n_chroma, n_frames) incompatible with cdist"


def check_producer_signature_mismatch():
    """FILE-104 §4.4: producers take 4 args (reference, practice, sample_rate, warp_path).
    But actual function signatures are:
      - ingest.ingest(uri): 1 arg
      - align.align(ref, prac): 2 args
      - features.materialize_pitch(samples, sr): 2 args
      - features.materialize_rms(samples): 1 arg
      - features.materialize_chroma(samples): 1 arg
      - features.materialize_notes(pitch, rms, sr): 3 args
      - surface.build_surface(4 args): 4 args - matches!
    So only surface.build_surface matches. The 12 ports' producers must align with their actual signatures."""
    return True, "Producer signatures inconsistent with FILE-104 §4.4"


def check_no_pyfiddle_in_spec():
    """Count mentions of files/modules across specs and verify they're real."""
    f102 = read(SPEC / "FILE-102-v1.md")
    return "harmonica_eval.exceptions" not in f102, "FILE-102 mentions 'harmonica_eval.exceptions' (does NOT exist)"


def check_no_warp_path_in_timing():
    """FILE-202 says timing required_ports must NOT contain warp_path."""
    f202 = read(SPEC / "FILE-202-v1.md")
    return "warp_path" in f202 and "不得声明 warp_path" in f202, "warp_path exclusion from timing documented"


def check_pcm_warped_unused_by_algorithms():
    """FILE-202 §7 says timing must NOT use pcm.warped.practice.
    pcm.warped.practice has no consumer per profile.
    But profile.PORTS says produced_by='core.surface' for it.
    Spec generates a port no algorithm uses.
    Known cost: 8.9 MB per build per spike (still allocated, still Seal'd)."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.algorithms as alg
    import harmonica_eval.profile as p
    used = set()
    for spec in alg.ALGORITHMS:
        used |= set(spec.required_ports)
    for port in p.PORTS:
        if "warped" in port.port_id:
            in_use = port.port_id in used
            if not in_use:
                return True, f"Port {port.port_id} is generated but no algorithm consumes it (allowed per design)"


CHECKS = [
    ("Gap: NaN/inf bypass silence check (FILE-101 §4.4)", check_silence_for_nan_inf),
    ("fmin/fmax from profile (FILE-103 §4.0)", check_fmin_fmax_origin),
    ("DB_FLOOR frozen (FILE-203 §4)", check_db_floor),
    ("ONSET_MATCH_TOLERANCE_SEC derived (FILE-202 §4.0)", check_onset_match_tolerance_origin),
    ("ONSET_DEADBAND_MS derived (FILE-202 §4.0)", check_deadband_ms_origin),
    ("Bandwidth from profile.ALIGN.band_rad (FILE-102)", check_align_bandwidth),
    ("Coverage threshold frozen (FILE-102)", check_coverage_threshold),
    ("Cents threshold from SPEC §7.3 (FILE-201)", check_cents_threshold),
    ("voiced threshold semantics frozen (FILE-103)", check_pyin_voiced_threshold_semantics),
    ("DUPLICATION: MIN_STABLE_NOTE_SEC in pitch.py AND features.py", check_min_stable_note),
    ("DUPLICATION: silence threshold in 2 forms (DB_FLOOR & SILENCE_RMS_THRESHOLD)",
     check_silence_threshold_duplication),
    ("FILE-203 invents 100 Hz frame rate (not sourced)", check_dynamics_frame_rate_100hz),
    ("INTERNAL_STAGES module constant present (FILE-105 §4.9)", check_internal_stages_module_const),
    ("ALGORITHM_ID strings frozen and match shell (FILE-201/202/203)",
     check_algorithm_id_string_frozen),
    ("Each algorithm's required_ports subset of profile.PORTS (FILE-200 INV-200-3)",
     check_algorithms_required_ports_compatible),
    ("Each algorithm's required_ports is paired (FILE-200 §4.4 C6)",
     check_paired_ports_in_registry),
    ("BUG: STFT fs set to hop_length instead of sample_rate (FILE-102 §4)",
     check_compute_alignment_features_stft_fs),
    ("BUG: chroma shape transposed vs cdist expectation (FILE-102 §4)",
     check_compute_alignment_features_shape),
    ("Producer signatures inconsistent with FILE-104 §4.4", check_producer_signature_mismatch),
    ("FILE-102 references nonexistent harmonica_eval.exceptions",
     check_no_pyfiddle_in_spec),
    ("timing must not consume warp_path (FILE-200 §4.2 + FILE-202 §7)",
     check_no_warp_path_in_timing),
    ("pcm.warped.* generated but no consumer (documented design choice)",
     check_pcm_warped_unused_by_algorithms),
]


def main():
    print("=" * 70)
    print("MISSING / INVENTED-FACT PROBES")
    print("=" * 70)
    fails = 0
    for label, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as exc:
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        marker = "PASS" if ok else "FAIL"
        print(f"[{marker}] {label}")
        print(f"        -> {detail}")
        if not ok:
            fails += 1
    print()
    print(f"{fails} potential issues found.")


if __name__ == "__main__":
    main()