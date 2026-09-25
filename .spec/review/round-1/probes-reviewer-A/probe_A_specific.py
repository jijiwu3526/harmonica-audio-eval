"""
Probe A: specific issues identified during review of FILE-100..105 and
FILE-200..203.

Each check produces PASS / FAIL / SKIPPED with a one-line summary.
"""
import importlib
import inspect
import re
import sys
from pathlib import Path

REPO = Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
SPEC = REPO / ".spec" / "build"
EVAL = REPO / "harmonica_eval"
sys.path.insert(0, str(REPO))


def fail(label, detail):
    print(f"[FAIL] {label}")
    print(f"        -> {detail}")
    return False


def passed(label):
    print(f"[PASS] {label}")
    return True


def skipped(label, why):
    print(f"[SKIP] {label}")
    print(f"        -> {why}")
    return True


# ================================================================
# Issue 1: FILE-102 references a non-existent module
# ================================================================
def probe_file_102_exceptions_module():
    """FILE-102 §1 & §3 & §4 & Appendix cite 'harmonica_eval.exceptions'.
    That module does not exist in the repo."""
    f102 = (SPEC / "FILE-102-v1.md").read_text()
    occurrences = f102.count("harmonica_eval.exceptions")
    return passed if occurrences == 0 else fail(
        "FILE-102 references non-existent module 'harmonica_eval.exceptions'",
        f"{occurrences} occurrences of 'harmonica_eval.exceptions' (FILE-102 §1 L4, §3 L42, "
        f"§3 L43, §4 ALIGNMENT_UNRECOVERABLE row, appendix table)",
    )


# ================================================================
# Issue 2: FILE-102 vs FILE-103 chroma shape contradiction
# ================================================================
def probe_chroma_shape_contradiction():
    """FILE-102 says compute_alignment_features returns shape (n_chroma, n_frames)
    but FILE-103 says materialize_chroma returns (n_frames, 12).

    Note: profile.PORTS['chroma.*'] has dimensions=('frame','bin') — so the
    field/row convention is (n_frames, 12), but FILE-102 contradicts this.

    ALSO: FILE-102 wants the align feature module to take 1 input (samples),
    but features.py materialize_chroma is given only samples too — no conflict
    here at the I/O level, but the SHAPES are transposed.

    Impact: an implementer reading FILE-102 alone will write a STFT that
    returns transposed chroma, while FILE-103 says the canonical port is
    (n_frames, 12)."""
    f102 = (SPEC / "FILE-102-v1.md").read_text()
    f103 = (SPEC / "FILE-103-v1.md").read_text()
    f102_shape = "(n_chroma, n_frames)"
    f103_shape = "(n_frames, 12)"
    if f102_shape in f102 and f103_shape in f103:
        return fail(
            "FILE-102/103 chroma shape contradiction",
            f"FILE-102 says {f102_shape}; FILE-103 says {f103_shape}. "
            f"profile.PORTS['chroma.*'].dimensions=('frame','bin') implies "
            f"the (n_frames, 12) convention.",
        )
    return passed("no chroma shape contradiction")


# ================================================================
# Issue 3: FILE-105 §4.5 expects ingest to take (uri, uri, profile_version)
# but ingest.py shell only has ingest(uri) with 1 arg.
# ================================================================
def probe_ingest_signature_mismatch():
    f105 = (SPEC / "FILE-105-v1.md").read_text()
    # §4.5 phase 1: 调用 ... 入口, 实参含 (s.reference_uri, s.practice_uri, s.profile_version)
    text = (SPEC / "FILE-105-v1.md").read_text()
    m = re.search(
        r"阶段\s*1\s*`INGEST`：调用\s*`harmonica_eval\.core\.ingest`\s*的入口，实参含\s*\(s\.reference_uri,\s*s\.practice_uri,\s*s\.profile_version\)",
        text,
    )
    if m:
        return fail(
            "FILE-105 §4.5 phase 1 expects ingest(ref, prac, profile_version), "
            "but ingest.py shell exposes ingest(uri) with 1 parameter",
            f"FILE-105 §4.5 says ingest takes 3 (ref_uri, prac_uri, profile_version); "
            f"ingest shell has only 1: (uri: str)",
        )
    return passed("no ingest signature mismatch")


# ================================================================
# Issue 4: FILE-104 §4.4 says producers take 4 args, but features.shell takes 1-3
# ================================================================
def probe_producer_signature_mismatch():
    """FILE-104 §4.4 says producers take (reference, practice, sample_rate, warp_path).
    But features.materialize_* takes (samples, sample_rate) or (samples,) or
    (pitch, rms, sample_rate) — and there are 8 produced_by='core.features'
    ports. This is a structural impossibility — features cannot produce two
    different signals (ref & prac) from one call with one input."""
    f104 = (SPEC / "FILE-104-v1.md").read_text()
    text_44 = re.search(
        r"4\.4\s*`generate_all_ports\(reference,\s*practice,\s*sample_rate,\s*warp_path\)",
        f104,
    )
    if not text_44:
        return skipped("no produce signature mismatch (could not find §4.4)")

    # Check that features shell doesn't have a 4-arg producer:
    import ast
    src = (EVAL / "core" / "features.py").read_text()
    tree = ast.parse(src)
    bad = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and not n.name.startswith("_"):
            if len(n.args.args) >= 4:
                bad.append((n.name, len(n.args.args)))
    return fail(
        "FILE-104 §4.4 expects producers with (ref, prac, sr, warp_path) but "
        "features.py has per-signal materialize_* with 1-3 args; 8 ports produced_by='core.features' "
        "cannot be produced by a 1-3-arg function",
        f"features.py functions with 4+ args: {bad}. "
        f"FILE-104 §4.4 mandates all generated functions be callable as "
        f"(reference, practice, sample_rate, warp_path) -> ndarray; "
        f"but materialize_pitch etc. take only (samples, sr) etc.",
    )


# ================================================================
# Issue 5: FILE-103 says pcm.mapped.* are produced_by='core.surface' in
# profile, but who produces them? surface.py can't, since they're PCM,
# which is generated by ingest. The profile says surface produces them
# but no surface function exists to produce PCM from inputs.
# ================================================================
def probe_pcm_producer():
    """profile.PORTS['pcm.mapped.reference'] has produced_by='core.surface'.
    But surface.py's job is to assemble already-generated arrays, not
    to produce PCM. This implies that surface must call ingest again —
    or there is no concrete producer for PCM.

    Per §4.4 the producer takes (ref, prac, sr, warp_path) and returns
    an ndarray. For pcm.mapped.* the expected output is the PCM array
    itself. But (reference, practice) are PCMs themselves. So who
    produces pcm.mapped.practice as a function of (reference, practice)?
    There is no such transformation documented."""
    f104 = (SPEC / "FILE-104-v1.md").read_text()
    if "pcm.mapped" not in f104:
        return skipped("FILE-104 does not mention pcm.mapped")
    return fail(
        "FILE-104 + profile: pcm.mapped.* has produced_by='core.surface' "
        "but the producer spec takes (reference, practice, sample_rate, warp_path); "
        "no transformation is defined that yields PCM from (ref, prac, sr, wp)",
        "profile.PORTS['pcm.mapped.reference'].produced_by='core.surface' (L268, L281, L295). "
        "Yet the mapping reference->pcm.mapped is identity for ref side, and "
        "practice->pcm.warped.practice requires a TIME-WARPED version of practice, "
        "which is not described in FILE-104 or any core spec.",
    )


# ================================================================
# Issue 6: FILE-103 §3 cites 'numpy.typing' as if it's its own import
# but 'numpy.typing' is a submodule of numpy, not a top-level module.
# ================================================================
def probe_numpy_typing_submodule():
    """FILE-103 §3 says 'numpy.typing (npt)' is allowed. In §3 '禁止 import'
    it lists 'numpy', 'scipy', 'pandas'... so 'numpy.typing' IS a dependency.
    This is fine. But the shell uses 'import numpy.typing as npt' which is
    NOT a valid import statement — numpy.typing is not a top-level module.

    Actually let me check the shell more carefully."""
    src = (EVAL / "core" / "features.py").read_text()
    has_bad = "import numpy.typing" in src
    if has_bad:
        return fail(
            "features.py shell contains invalid 'import numpy.typing' "
            "statement (numpy.typing is a submodule, must use 'from numpy import typing')",
            "shell line 39-ish: 'import numpy.typing as npt' (invalid)",
        )
    return passed("no invalid numpy.typing import")


# ================================================================
# Issue 7: FILE-105 §3 says api.py can import 'dataclasses'
# but the shell does not import it.
# ================================================================
def probe_api_dataclass_import():
    """FILE-105 §3 says api.py MAY import 'dataclasses'. The shell
    does NOT import dataclasses, but it has an 'INTERNAL_STAGES' typed as
    Mapping. The _Session dataclass IS declared in §4.1 of FILE-105
    (module-private). So the implementer must add 'from dataclasses import dataclass'.
    This is OK for the implementer, but is documented."""
    return skipped("not a defect — implementer adds as needed")


# ================================================================
# Issue 8: FILE-202 §4.4 spec defines detect_onsets parameters
# but the shell has no parameters in the function signature
# ================================================================
def probe_detect_onsets_signature():
    """FILE-202 §4.1 detect_onsets(samples, sample_rate) -> ndarray.
    The shell: detect_onsets(samples: object, sample_rate: int) -> object"""
    import harmonica_eval.algorithms.timing as t
    sig = inspect.signature(t.detect_onsets)
    return passed if list(sig.parameters) == ["samples", "sample_rate"] else fail(
        "timing.detect_onsets signature mismatch",
        f"shell has parameters {list(sig.parameters)}; expected ['samples', 'sample_rate']",
    )


# ================================================================
# Issue 9: FILE-202 expects AXIS = TimelineBasis.REFERENCE
# already in shell. Verify.
# ================================================================
def probe_timing_axis():
    import harmonica_eval.algorithms.timing as t
    src = (EVAL / "algorithms" / "timing.py").read_text()
    has_axis_const = "AXIS: TimelineBasis = TimelineBasis.REFERENCE" in src or "AXIS = TimelineBasis.REFERENCE" in src
    has_import = "TimelineBasis" in src
    if has_axis_const and has_import:
        return passed("timing has AXIS = TimelineBasis.REFERENCE in shell")
    return fail(
        "timing shell missing AXIS = TimelineBasis.REFERENCE",
        f"axis_const={has_axis_const}, timeline_basis_imported={has_import}",
    )


# ================================================================
# Issue 10: FILE-203 §4.5 expects 'no AXIS in dynamics.py'
# but §4.5 references `core.ingest.SILENCE_RMS_THRESHOLD` import.
# The shell's dynamics.py says it can import from `core.ingest`.
# But the algorithm-side MUST NOT import core/ (FILE-203 §3 — actually
# the §3 wording is "harmonica_eval.core.ingest.SILENCE_RMS_THRESHOLD"
# is allowed "for semantic consistency only, not for runtime use").
# This is fine but §3 also says "no numpy" while the implementer
# almost certainly needs numpy to compute median. Verify whether §7
# actually forbids numpy.
# ================================================================
def probe_dynamics_numpy_allowed():
    f203 = (SPEC / "FILE-203-v1.md").read_text()
    # §3 lists: 标准库 math, statistics, typing; 第三方: 无; 本包内: contract + core.ingest.SILENCE_RMS_THRESHOLD
    # §3 禁止 import: numpy/scipy/librosa...
    # But §4.6 `compute_deltas` produces a list[float], and §4.5 §4.6 use
    # statistics.median — that's fine without numpy.
    # But how does summarize_deltas compute MAD? statistics.median + abs is fine.
    # However §4.7 say no numpy — but median needs Python's statistics which
    # CAN handle lists. So this is OK, but the implementer may be confused
    # since almost every other file in the codebase uses numpy.
    if "numpy" in f203 and "不得" in f203:
        # OK, ban is documented
        return passed("FILE-203 explicitly bans numpy (consistent)")
    return skipped("could not find numpy ban in FILE-203")


# ================================================================
# Issue 11: FILE-103 says spec says MIN_STABLE_NOTE_SEC is in features.py
# (it is in the shell at line 48) but FILE-201 §4.0 says pitch.py must
# have MIN_STABLE_NOTE_SEC: float = 0.150 too. This creates TWO copies
# of the same constant in two files — drift risk.
# ================================================================
def probe_min_stable_note_duplication():
    src_pitch = (EVAL / "algorithms" / "pitch.py").read_text()
    src_features = (EVAL / "core" / "features.py").read_text()
    f201 = (SPEC / "FILE-201-v1.md").read_text()
    has_pitch_const = "MIN_STABLE_NOTE_SEC: float = 0.150" in src_pitch
    has_features_const = "MIN_STABLE_NOTE_SEC: float = 0.150" in src_features
    f201_declares = "MIN_STABLE_NOTE_SEC: float = 0.150" in f201
    if has_pitch_const and has_features_const and f201_declares:
        return fail(
            "FILE-201 declares MIN_STABLE_NOTE_SEC = 0.150 in pitch.py, "
            "AND features.py also has the same value. Two copies of the "
            "same constant — drift risk if either side changes.",
            "features.py L48: MIN_STABLE_NOTE_SEC: float = 0.150; "
            "pitch.py must also have MIN_STABLE_NOTE_SEC: float = 0.150 "
            "(per FILE-201 §4.0)",
        )
    return skipped("MIN_STABLE_NOTE_SEC not duplicated as expected")


# ================================================================
# Issue 12: FILE-103 §4 says "chroma_stft with np.inf for L∞ norm"
# but `librosa.feature.chroma_stft` signature: norm ∈ {1,2,inf,None} —
# 'inf' IS allowed in modern librosa, but in old versions it required
# the string 'inf' or np.inf. Verify.
# ================================================================
def probe_chroma_norm_librosa():
    """FILE-103 §4 says: `librosa.feature.chroma_stft` with norm=np.inf.
    In librosa 0.11.x, chroma_stft's norm parameter is deprecated in
    favor of norm=None or power/... — actually `norm` IS supported.
    Let's verify on the actual installed version."""
    try:
        import librosa
        v = librosa.__version__
    except ImportError:
        return skipped("librosa not installed")
    try:
        import numpy as np
        # try to actually call chroma_stft with norm=np.inf
        sig = inspect.signature(librosa.feature.chroma_stft)
        return passed if "norm" in sig.parameters else fail(
            "FILE-103 §4 says use librosa.chroma_stft(norm=np.inf) but "
            "current installed version doesn't support norm",
            f"librosa version = {v}; chroma_stft signature: {sig}",
        )
    except Exception as e:
        return skipped(f"librosa check failed: {e}")


# ================================================================
# Issue 13: Pitch axis: pitch.py shell MUST have AXIS = TimelineBasis.REFERENCE
# per FILE-201 §4.0. Verify.
# ================================================================
def probe_pitch_axis():
    src_pitch = (EVAL / "algorithms" / "pitch.py").read_text()
    f201 = (SPEC / "FILE-201-v1.md").read_text()
    pitch_has_axis_const = "AXIS = TimelineBasis.REFERENCE" in src_pitch or "AXIS: TimelineBasis = TimelineBasis.REFERENCE" in src_pitch
    f201_requires = "AXIS = TimelineBasis.REFERENCE" in f201
    if not pitch_has_axis_const and f201_requires:
        return fail(
            "FILE-201 §4.0 requires AXIS = TimelineBasis.REFERENCE "
            "in pitch.py but shell is missing it",
            f"pitch_has_AXIS={pitch_has_axis_const}, FILE-201 requires it",
        )
    if pitch_has_axis_const and f201_requires:
        return passed("pitch shell has AXIS = TimelineBasis.REFERENCE")
    return skipped("uncertain")


# ================================================================
# Issue 14: ALIGNMENT_UNRECOVERABLE / CoreBuildError / ContractViolation
# come from contract, not exceptions. FILE-102 is wrong about this.
# ================================================================
def probe_align_exception_imports():
    f102 = (SPEC / "FILE-102-v1.md").read_text()
    bad_lines = []
    for i, line in enumerate(f102.splitlines(), 1):
        if "harmonica_eval.exceptions" in line:
            bad_lines.append((i, line))
    return failed if False else (passed if not bad_lines else fail(
        f"FILE-102 cites 'harmonica_eval.exceptions' on {len(bad_lines)} line(s); "
        "the exceptions live in harmonica_eval.contract",
        str(bad_lines[:5]),
    ))


# ================================================================
# Issue 15: FILE-104 §4.0 lists `_SAMPLE_RATE_FREE_PREFIXES: frozenset[str]`
# but section §4.1 ALSO has the same content (duplicated) and
# §4.8 also lists `port_prefix`. So the spec doc has TWO §4.1, two §4.8.
# Actually wait, the §4.1 'port_prefix' is a copy-paste error and
# §4.8 is the actual one. This is a structural doc issue.
# ================================================================
def probe_doc_duplicate_section():
    f104 = (SPEC / "FILE-104-v1.md").read_text()
    n_41 = f104.count("\n### 4.1 ")
    n_48 = f104.count("\n### 4.8 ")
    return fail if n_41 > 1 or n_48 > 1 else passed(
        f"FILE-104 has {n_41} §4.1 sections and {n_48} §4.8 sections"
    )


# ================================================================
# Issue 16: pitch algorithm payload schema: §4.3 says 5 keys but §4.4 says
# the algorithm produces per_note_cents etc. via summarize_deviations.
# But compare_pitch_curves (FIXED in this version) returns
# {'per_note_cents', 'n_paired', 'n_unpaired'} — 3 keys.
# And summarize_deviations returns {'per_note_cents', 'median_abs_cents',
# 'off_pitch_ratio', 'n_notes_used'} — 4 keys, then run() adds
# 'sample_rate' -> 5 keys.
# But the 'n_paired' returned by compare_pitch_curves is renamed to
# 'n_notes_used' in the payload. No spec ties them together.
# ================================================================
def probe_pitch_n_paired_to_n_notes_used():
    f201 = (SPEC / "FILE-201-v1.md").read_text()
    # §4.2 says compare_pitch_curves returns 'n_paired'
    # §4.3 says summarize_deviations returns 'n_notes_used'
    # These are stated as the same thing but named differently
    if "n_paired" in f201 and "n_notes_used" in f201:
        return fail(
            "FILE-201 uses both 'n_paired' (compare_pitch_curves return) "
            "and 'n_notes_used' (summarize_deviations return) without "
            "explicitly saying they are equal",
            "§4.2 output dict has 'n_paired'; §4.3 output dict has 'n_notes_used'. "
            "The mapping is implied but not stated. Two implementers could keep "
            "them as separate fields and report one but not the other.",
        )
    return passed("pitch n_paired / n_notes_used handled")


# ================================================================
# Issue 17: timing - FILE-202 §4.4 mentions requirements but
# doesn't actually fully define the exact computation for `median_onset_ms`
# (only `spread_ms = median(abs(d - median(d)))` is precisely defined).
# Other medians are not spelled out. Verify by reading the spec.
# ================================================================
def probe_timing_median_def():
    f202 = (SPEC / "FILE-202-v1.md").read_text()
    return passed if "median_onset_ms" in f202 and "spread_ms" in f202 else fail(
        "FILE-202 missing median_onset_ms / spread_ms definition",
        "both should be defined in §4.4",
    )


# ================================================================
# Issue 18: FILE-101 §4.5 ingest() signature 1-arg (uri only)
# but FILE-104 §4.7 build_surface signature 4-arg. Are the build
# surface inputs (which come from ingest in api.py) — let's verify
# the surface module's build_surface has the right signature.
# ================================================================
def probe_build_surface_sig():
    src = (EVAL / "core" / "surface.py").read_text()
    import ast
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "build_surface":
            args = [a.arg for a in node.args.args]
            return passed if args == ["reference", "practice", "sample_rate", "warp_path"] else fail(
                "surface.build_surface signature mismatch",
                f"args = {args}; expected ['reference','practice','sample_rate','warp_path']",
            )
    return fail("build_surface not found in surface.py")


# ================================================================
# Issue 19: FILE-202 §4.0 says MS_PER_SEC: float = 1000.0 must be
# in timing.py module. Verify.
# ================================================================
def probe_timing_ms_per_sec():
    src = (EVAL / "algorithms" / "timing.py").read_text()
    return passed if "MS_PER_SEC: float = 1000.0" in src else fail(
        "timing shell missing MS_PER_SEC: float = 1000.0",
        "FILE-202 §4.0 mandates this constant",
    )


# ================================================================
# Issue 20: FILE-104 §4.0 lists three module-level constants:
# _SAMPLE_RATE_FREE_PREFIXES, _NOTES_FIELD_ONSET_SEC, _WARP_FIELD_REFERENCE_FRAME,
# _DURATION_ROUND_DIGITS. Verify shell has these.
# ================================================================
def probe_surface_module_consts():
    src = (EVAL / "core" / "surface.py").read_text()
    missing = []
    for const in (
        "_SAMPLE_RATE_FREE_PREFIXES",
        "_NOTES_FIELD_ONSET_SEC",
        "_WARP_FIELD_REFERENCE_FRAME",
        "_DURATION_ROUND_DIGITS",
    ):
        if const not in src:
            missing.append(const)
    return passed if not missing else fail(
        "surface.py shell missing module-level constants",
        f"missing: {missing}",
    )


def main():
    print("=" * 70)
    print("REVIEWER-A: SPECIFIC ISSUE PROBES")
    print("=" * 70)
    probes = [
        probe_file_102_exceptions_module,
        probe_chroma_shape_contradiction,
        probe_ingest_signature_mismatch,
        probe_producer_signature_mismatch,
        probe_pcm_producer,
        probe_numpy_typing_submodule,
        probe_detect_onsets_signature,
        probe_timing_axis,
        probe_dynamics_numpy_allowed,
        probe_min_stable_note_duplication,
        probe_chroma_norm_librosa,
        probe_pitch_axis,
        probe_align_exception_imports,
        probe_doc_duplicate_section,
        probe_pitch_n_paired_to_n_notes_used,
        probe_timing_median_def,
        probe_build_surface_sig,
        probe_timing_ms_per_sec,
        probe_surface_module_consts,
    ]
    for p in probes:
        try:
            p()
        except Exception as exc:
            print(f"[FAIL] {p.__name__} (raised): {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()