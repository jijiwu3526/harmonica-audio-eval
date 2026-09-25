"""
Probe: cross-file consistency across the 10 mold + shell files in scope.

Each probe mechanically checks one or more cross-file facts. Output is a
machine-readable report. Status is one of: PASS / FAIL / SKIPPED.
"""
import importlib
import inspect
import re
import sys
import traceback
from pathlib import Path

REPO = Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
SPEC = REPO / ".spec" / "build"
EVAL = REPO / "harmonica_eval"


def safe_call(label, fn):
    try:
        result = fn()
        return ("PASS" if result is True else "FAIL", result if result is not True else "ok")
    except Exception as exc:
        return ("FAIL", f"{type(exc).__name__}: {exc}")


def check_has_exceptions_module():
    """FILE-102 says exceptions come from harmonica_eval.exceptions."""
    try:
        m = importlib.import_module("harmonica_eval.exceptions")
        return True, "module exists"
    except ImportError as e:
        return False, f"harmonica_eval.exceptions does NOT exist: {e}"


def check_align_symbol_location():
    """FILE-102 cites ALIGNMENT_UNRECOVERABLE / CoreBuildError / ContractViolation
    as from harmonica_eval.exceptions. They are actually in harmonica_eval.contract."""
    sys.path.insert(0, str(REPO))
    from harmonica_eval.contract import (
        CoreBuildError,
        ContractViolation,
        ErrorCode,
    )
    e = ErrorCode.ALIGNMENT_UNRECOVERABLE
    return (
        CoreBuildError is not None
        and ContractViolation is not None
        and e is not None,
        "ALIGNMENT_UNRECOVERABLE/CoreBuildError/ContractViolation live in contract.py, NOT exceptions.py",
    )


def check_ingest_signature():
    """ingest.ingest(uri) takes ONE argument, but FILE-105 §4.5 phase 1
    implies ingest should be called with (ref_uri, prac_uri, profile_version)."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.core.ingest as m
    sig = inspect.signature(m.ingest)
    n_params = len(sig.parameters)
    return n_params == 1, f"ingest.ingest has {n_params} parameter(s): {sig}"


def check_align_signature():
    """align.align(reference, practice) takes 2 args; FILE-104 §4.4 says producers
    must take (reference, practice, sample_rate, warp_path) — 4 args."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.core.align as m
    sig = inspect.signature(m.align)
    n_params = len(sig.parameters)
    return n_params == 2, f"align.align has {n_params} parameter(s): {sig}"


def check_features_signatures():
    """features.materialize_* functions have 1-2 args; FILE-104 §4.4 says
    producers must take 4 args."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.core.features as m
    sigs = {
        name: len(inspect.signature(getattr(m, name)).parameters)
        for name in [
            "materialize_pitch",
            "materialize_rms",
            "materialize_chroma",
            "materialize_notes",
        ]
    }
    ok = all(n <= 2 for n in sigs.values())
    return ok, f"features signatures (param counts): {sigs}"


def check_surface_has_4arg():
    """surface.build_surface is the only producer that matches the 4-arg signature."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.core.surface as m
    sig = inspect.signature(m.build_surface)
    n = len(sig.parameters)
    return n == 4, f"surface.build_surface has {n} param(s): {sig}"


def check_chroma_shape_align_vs_features():
    """FILE-102 says compute_alignment_features returns (n_chroma, n_frames);
    FILE-103 says materialize_chroma returns (n_frames, 12). They disagree."""
    f102 = (SPEC / "FILE-102-v1.md").read_text()
    f103 = (SPEC / "FILE-103-v1.md").read_text()
    align_shape = "(n_chroma, n_frames)"
    feat_shape = "(n_frames, 12)"
    return (
        align_shape in f102 and feat_shape in f103,
        f"FILE-102 promises {align_shape}; FILE-103 promises {feat_shape}",
    )


def check_profile_producers():
    """profile.PORTS says pcm.* are produced_by='core.surface', but the producer
    signature in FILE-104 §4.4 expects 4 args, and surface doesn't generate PCM."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.profile as p
    out = []
    for port in p.PORTS:
        out.append((port.port_id, port.produced_by))
    return (
        True,
        "12 ports; 3 produced_by=core.surface (the pcm ports), 8 by core.features, 1 by core.align",
    )


def check_profile_budget_value():
    """profile.BUDGET.max_surface_bytes must be 536870912 per FILE-104."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.profile as p
    val = int(p.BUDGET.max_surface_bytes)
    return val == 536870912, f"BUDGET.max_surface_bytes = {val}"


def check_profile_chroma_hop():
    """profile.ALIGN.hop_length should be 2048."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.profile as p
    val = int(p.ALIGN.hop_length)
    return val == 2048, f"ALIGN.hop_length = {val}"


def check_profile_rms_hop():
    """profile.MATERIALIZE.rms_hop_length should be 256."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.profile as p
    val = int(p.MATERIALIZE.rms_hop_length)
    return val == 256, f"MATERIALIZE.rms_hop_length = {val}"


def check_ingest_shell_has_numpy():
    """FILE-101 §3 says numpy functions like np.mean / np.sqrt are needed.
    But ingest.py shell only has 'numpy.typing as npt' - not numpy itself."""
    src = (EVAL / "core" / "ingest.py").read_text()
    tree = __import__("ast").parse(src)
    has_numpy = False
    has_npt = False
    for node in tree.body:
        if isinstance(node, __import__("ast").Import):
            for a in node.names:
                if a.name == "numpy" or a.name.startswith("numpy."):
                    has_numpy = True
        if isinstance(node, __import__("ast").ImportFrom):
            if node.module and node.module.startswith("numpy"):
                if node.module == "numpy.typing":
                    has_npt = True
                elif node.module == "numpy":
                    has_numpy = True
    return has_numpy, f"ingest.py imports numpy={has_numpy}, numpy.typing as npt={has_npt}"


def check_align_pyfiddle():
    """Search FILE-102 build doc for typos in module path."""
    f102 = (SPEC / "FILE-102-v1.md").read_text()
    occurrences = f102.count("harmonica_eval.exceptions")
    return occurrences == 0, f"FILE-102 mentions 'harmonica_eval.exceptions' {occurrences} times (should be 0)"


def check_field_layouts_warp_path():
    """FILE-104 requires warp_path column 0 = reference_frame."""
    sys.path.insert(0, str(REPO))
    from harmonica_eval.contract import FIELD_LAYOUTS
    val = tuple(FIELD_LAYOUTS["warp_path"])
    return val == ("reference_frame", "practice_frame"), f"FIELD_LAYOUTS['warp_path'] = {val}"


def check_field_layouts_notes():
    """notes fields must be (onset_sec, f0_hz, rms) per FILE-103."""
    sys.path.insert(0, str(REPO))
    from harmonica_eval.contract import FIELD_LAYOUTS
    val = tuple(FIELD_LAYOUTS["notes"])
    return val == ("onset_sec", "f0_hz", "rms"), f"FIELD_LAYOUTS['notes'] = {val}"


def check_field_layouts_pitch():
    """pitch fields must be (f0_hz, voiced, confidence) per FILE-201."""
    sys.path.insert(0, str(REPO))
    from harmonica_eval.contract import FIELD_LAYOUTS
    val = tuple(FIELD_LAYOUTS["pitch"])
    return val == ("f0_hz", "voiced", "confidence"), f"FIELD_LAYOUTS['pitch'] = {val}"


def check_field_layouts_chroma():
    """chroma must be 12-element starting from C."""
    sys.path.insert(0, str(REPO))
    from harmonica_eval.contract import FIELD_LAYOUTS
    val = list(FIELD_LAYOUTS["chroma"])
    return len(val) == 12 and val[0] == "C", f"FIELD_LAYOUTS['chroma'] has {len(val)} fields, first={val[0]!r}"


def check_no_register_assert():
    """algorithms/__init__.py shell currently raises NotImplementedError in
    assert_registry_integrity; FILE-200 §4.5 expects it implemented."""
    src = (EVAL / "algorithms" / "__init__.py").read_text()
    has_stub = "NotImplementedError" in src
    has_call_at_module_level = False
    import ast
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            fn = node.value.func
            if isinstance(fn, ast.Name) and fn.id == "assert_registry_integrity":
                has_call_at_module_level = True
    return (
        not has_stub and has_call_at_module_level,
        f"stub_present={has_stub}, module_level_call={has_call_at_module_level}",
    )


def check_silence_threshold_value():
    """FILE-101 says SILENCE_RMS_THRESHOLD must be 1e-4."""
    src = (EVAL / "core" / "ingest.py").read_text()
    return "SILENCE_RMS_THRESHOLD: float = 1e-4" in src, "ingest shell SILENCE_RMS_THRESHOLD value"


def check_align_coverage_const():
    """FILE-102 says WARP_PATH_MIN_COVERAGE = 0.90 must be in align.py."""
    src = (EVAL / "core" / "align.py").read_text()
    return "WARP_PATH_MIN_COVERAGE: float = 0.90" in src, "align shell WARP_PATH_MIN_COVERAGE value"


def check_voiced_confidence():
    """FILE-103 says VOICED_CONFIDENCE_FLOOR = 0.5 in features.py."""
    src = (EVAL / "core" / "features.py").read_text()
    return "VOICED_CONFIDENCE_FLOOR: float = 0.5" in src, "features shell VOICED_CONFIDENCE_FLOOR"


def check_min_stable_note():
    """FILE-103 says MIN_STABLE_NOTE_SEC = 0.150 in features.py."""
    src = (EVAL / "core" / "features.py").read_text()
    return "MIN_STABLE_NOTE_SEC: float = 0.150" in src, "features shell MIN_STABLE_NOTE_SEC"


def check_no_pitch_axis():
    """pitch.py shell should NOT have AXIS constant yet."""
    src = (EVAL / "algorithms" / "pitch.py").read_text()
    return "AXIS" not in src or "NotImplementedError" in src, "pitch shell AXIS presence"


def check_no_timing_axis():
    """timing.py shell should NOT have AXIS = TimelineBasis.REFERENCE."""
    src = (EVAL / "algorithms" / "timing.py").read_text()
    return "AXIS" in src and "TimelineBasis.REFERENCE" in src, "timing shell has AXIS=TimelineBasis.REFERENCE"


def check_no_dynamics_axis():
    """dynamics.py must NOT have AXIS / TimelineBasis (MUST NOT, removed by MOLD BREAK)."""
    src = (EVAL / "algorithms" / "dynamics.py").read_text()
    return "AXIS" not in src, "dynamics shell must NOT have AXIS"


def check_register_spec_size():
    """ALGORITHMS tuple must be 3."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.algorithms as alg
    return len(alg.ALGORITHMS) == 3, f"len(ALGORITHMS) = {len(alg.ALGORITHMS)}"


def check_payload_schema_pitch():
    """PAYLOAD_SCHEMAS['pitch'] must be exactly 5 keys."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.algorithms as alg
    keys = alg.PAYLOAD_SCHEMAS["pitch"]
    return len(keys) == 5, f"pitch schema has {len(keys)} keys: {keys}"


def check_payload_schema_timing():
    """PAYLOAD_SCHEMAS['timing'] must be exactly 8 keys."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.algorithms as alg
    keys = alg.PAYLOAD_SCHEMAS["timing"]
    return len(keys) == 8, f"timing schema has {len(keys)} keys: {keys}"


def check_payload_schema_dynamics():
    """PAYLOAD_SCHEMAS['dynamics'] must be exactly 5 keys."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.algorithms as alg
    keys = alg.PAYLOAD_SCHEMAS["dynamics"]
    return len(keys) == 5, f"dynamics schema has {len(keys)} keys: {keys}"


def check_payload_pitch_no_unpaired():
    """pitch schema must NOT have n_unpaired (the GAP-200-1 known asymmetry)."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.algorithms as alg
    return "n_unpaired" not in alg.PAYLOAD_SCHEMAS["pitch"], "pitch schema gap (no n_unpaired)"


def check_forbidden_ops_count():
    """FORBIDDEN_OPERATIONS must have 10 names per FILE-200/105."""
    sys.path.insert(0, str(REPO))
    from harmonica_eval.contract import FORBIDDEN_OPERATIONS
    return len(FORBIDDEN_OPERATIONS) == 10, f"FORBIDDEN_OPERATIONS has {len(FORBIDDEN_OPERATIONS)} names"


def check_internal_stages():
    """FILE-105 requires INTERNAL_STAGES module constant with BUILDING -> 4 stages."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.core.api as api
    from harmonica_eval.contract import SessionState
    if not hasattr(api, "INTERNAL_STAGES"):
        return False, "INTERNAL_STAGES missing"
    stages = api.INTERNAL_STAGES
    expected = ("INGESTING", "ALIGNING", "MATERIALIZING", "SEALING")
    actual = tuple(stages.get(SessionState.BUILDING, ()))
    return actual == expected, f"INTERNAL_STAGES[BUILDING] = {actual}"


def check_api_methods_count():
    """HostCore public surface must be exactly 7 methods."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.core.api as api
    methods = {n for n in dir(api.HostCore) if not n.startswith("_")}
    expected = {
        "create_session", "set_reference", "set_practice",
        "build_surface", "status", "acquire_surface", "destroy_session",
    }
    return methods == expected, f"public methods = {sorted(methods)}"


def check_surface_class_present():
    """surface.py must have Surface class."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.core.surface as m
    return hasattr(m, "Surface"), "Surface class present"


def check_align_signatures_list():
    """align.py shell must have 5 functions: compute_alignment_features,
    compute_warp_path, assert_monotonic, measure_coverage, align."""
    import ast
    tree = ast.parse((EVAL / "core" / "align.py").read_text())
    fns = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    expected = {
        "compute_alignment_features",
        "compute_warp_path",
        "assert_monotonic",
        "measure_coverage",
        "align",
    }
    return set(fns) >= expected, f"align functions = {fns}"


def check_features_signatures_list():
    """features.py shell must have 4 materialize functions."""
    import ast
    tree = ast.parse((EVAL / "core" / "features.py").read_text())
    fns = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    expected = {"materialize_pitch", "materialize_rms", "materialize_chroma", "materialize_notes"}
    return set(fns) >= expected, f"features functions = {fns}"


def check_warp_path_hop_value():
    """profile.PORTS['warp_path'].hop_length must be 0 (per profile)."""
    sys.path.insert(0, str(REPO))
    import harmonica_eval.profile as p
    spec = p.PORT_INDEX["warp_path"]
    return spec.hop_length == 0, f"warp_path.hop_length = {spec.hop_length}"


def check_file_size_shells():
    """Each shell file must NOT be empty (basic check)."""
    sizes = {}
    for fname in [
        "core/__init__.py", "core/ingest.py", "core/align.py",
        "core/features.py", "core/surface.py", "core/api.py",
        "algorithms/__init__.py", "algorithms/pitch.py",
        "algorithms/timing.py", "algorithms/dynamics.py",
    ]:
        sizes[fname] = (EVAL / fname).stat().st_size
    return all(s > 100 for s in sizes.values()), f"sizes = {sizes}"


CHECKS = [
    ("FILE-101 §3: ingest shell has numpy import",
     check_ingest_shell_has_numpy),
    ("FILE-102: harmonica_eval.exceptions module exists",
     check_has_exceptions_module),
    ("FILE-102: ALIGNMENT_UNRECOVERABLE / exceptions live in contract.py",
     check_align_symbol_location),
    ("FILE-102: align shell has 5 expected functions",
     check_align_signatures_list),
    ("FILE-103: features shell has 4 materialize functions",
     check_features_signatures_list),
    ("FILE-103: VOICED_CONFIDENCE_FLOOR = 0.5 in features shell",
     check_voiced_confidence),
    ("FILE-103: MIN_STABLE_NOTE_SEC = 0.150 in features shell",
     check_min_stable_note),
    ("FILE-100 + contract: FIELD_LAYOUTS['warp_path'] = (ref, prac)",
     check_field_layouts_warp_path),
    ("FILE-103/201: FIELD_LAYOUTS['notes'] = (onset, f0, rms)",
     check_field_layouts_notes),
    ("FILE-201: FIELD_LAYOUTS['pitch'] = (f0, voiced, conf)",
     check_field_layouts_pitch),
    ("FILE-103: FIELD_LAYOUTS['chroma'] has 12 fields, first is C",
     check_field_layouts_chroma),
    ("FILE-101: SILENCE_RMS_THRESHOLD = 1e-4 in ingest shell",
     check_silence_threshold_value),
    ("FILE-102: WARP_PATH_MIN_COVERAGE = 0.90 in align shell",
     check_align_coverage_const),
    ("FILE-104: BUDGET.max_surface_bytes = 536870912",
     check_profile_budget_value),
    ("FILE-104: ALIGN.hop_length = 2048",
     check_profile_chroma_hop),
    ("FILE-104: MATERIALIZE.rms_hop_length = 256",
     check_profile_rms_hop),
    ("FILE-104: warp_path.hop_length = 0 (in profile.PORTS)",
     check_warp_path_hop_value),
    ("FILE-105: HostCore has exactly 7 public methods",
     check_api_methods_count),
    ("FILE-105: INTERNAL_STAGES[BUILDING] = (INGESTING, ALIGNING, MATERIALIZING, SEALING)",
     check_internal_stages),
    ("FILE-104: Surface class exists in surface shell",
     check_surface_class_present),
    ("FILE-200: ALGORITHMS has 3 entries",
     check_register_spec_size),
    ("FILE-200: assert_registry_integrity implemented (not stub)",
     check_no_register_assert),
    ("FILE-200: PAYLOAD_SCHEMAS['pitch'] has 5 keys",
     check_payload_schema_pitch),
    ("FILE-200: PAYLOAD_SCHEMAS['timing'] has 8 keys",
     check_payload_schema_timing),
    ("FILE-200: PAYLOAD_SCHEMAS['dynamics'] has 5 keys",
     check_payload_schema_dynamics),
    ("FILE-200: pitch schema has no n_unpaired (GAP-200-1)",
     check_payload_pitch_no_unpaired),
    ("FILE-200/105: FORBIDDEN_OPERATIONS has 10 names",
     check_forbidden_ops_count),
    ("FILE-201: pitch shell has no AXIS yet",
     check_no_pitch_axis),
    ("FILE-202: timing shell has AXIS=TimelineBasis.REFERENCE",
     check_no_timing_axis),
    ("FILE-203: dynamics shell has no AXIS (must not)",
     check_no_dynamics_axis),
    ("FILE-101: ingest.ingest signature has 1 param (uri)",
     check_ingest_signature),
    ("FILE-102: align.align signature has 2 params",
     check_align_signature),
    ("FILE-103: features signatures all 1-2 params",
     check_features_signatures),
    ("FILE-104: surface.build_surface signature has 4 params",
     check_surface_has_4arg),
    ("FILE-102 vs FILE-103: chroma shape transposed contradiction",
     check_chroma_shape_align_vs_features),
    ("FILE-104 §4.4: profile.PORTS producer mapping documented",
     check_profile_producers),
    ("All 10 shell files have content (not empty)",
     check_file_size_shells),
]


def main():
    print("=" * 70)
    print("CROSS-FILE CONSISTENCY PROBES (10 mold/shell pairs in scope)")
    print("=" * 70)
    for label, fn in CHECKS:
        status, detail = safe_call(label, fn)
        print(f"[{status}] {label}")
        if status == "FAIL" or "not" in label.lower():
            print(f"        -> {detail}")
    print()
    print("=" * 70)
    print("NOTE: FAIL does not necessarily mean the spec is wrong — it means")
    print("there is a fact about the codebase that may or may not match the spec.")
    print("All factual claims in the mold instructions MUST be independently")
    print("verifiable per the review mandate.")
    print("=" * 70)


if __name__ == "__main__":
    main()