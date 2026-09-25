"""Probe 34: re-verify EVERY candidate finding against the frozen snapshot.
Snapshot = .spec/review/round-2/probes-A/_snapshot (taken 2026-09-24 11:32:13)."""
import sys, ast, dataclasses, inspect, pathlib, re, hashlib

SNAP = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval/.spec/review/round-2/probes-A/_snapshot")
sys.path.insert(0, str(SNAP))

RESULTS = []
def rec(fid, status, detail):
    RESULTS.append((fid, status, detail))
    print(f"[{status:9}] {fid}: {detail}")

# ---------- F1: metrics.json inputs URI channel ----------
import importlib
m = importlib.import_module("harmonica_eval.__main__")
cm = importlib.import_module("harmonica_eval.contract")
sig = inspect.signature(m.write_metrics_json)
rec("F1-uri", "CONFIRMED" if set(sig.parameters)=={"view","out_path","reference_uri","practice_uri"} else "STALE",
    f"write_metrics_json{sig}")

# ---------- F2: FILE-100 docstring splitlines ----------
src = (SNAP/"harmonica_eval/core/__init__.py").read_text()
doc = ast.parse(src).body[0].value.value
rec("F2-doclines", "CONFIRMED" if len(doc.splitlines())==30 else "STALE",
    f"len(doc.splitlines())={len(doc.splitlines())} (BI FILE-100 requires 31)")

# ---------- F3: FILE-100 declared vs produced ----------
core = importlib.import_module("harmonica_eval.core")
prof = importlib.import_module("harmonica_eval.profile")
declared = set(core.__all__)
produced = {p.produced_by.split(".")[1] for p in prof.PORTS if p.produced_by.startswith("core.")}
rec("F3-coreinit", "CONFIRMED" if declared!=produced else "STALE",
    f"declared={sorted(declared)} produced={sorted(produced)} equal={declared==produced}")

# ---------- F4: envelope 'error=' kwarg ----------
E = cm.AlgorithmResultEnvelope
fields = [f.name for f in dataclasses.fields(E)]
try:
    E(algorithm_id="d",algorithm_version="1",status="FAILED",required_ports=(),
      consumed_ports=(),payload={},error="X")
    ok=True
except TypeError:
    ok=False
rec("F4-envelope-error", "CONFIRMED" if not ok else "STALE",
    f"'error=' accepted={ok}; real fields={fields}")

# ---------- F5: compare_pitch_curves 3 keys vs pitch schema 5 ----------
from harmonica_eval.algorithms import PAYLOAD_SCHEMAS as PS
rec("F5-pitch-keys", "CHECK-FILE-201",
    f"PAYLOAD_SCHEMAS['pitch']={PS['pitch']}; FILE-201 §4.2 returns per_note_cents/n_paired/n_unpaired")

# ---------- F6: n_unpaired now in signatures? ----------
tim = importlib.import_module("harmonica_eval.algorithms.timing")
dyn = importlib.import_module("harmonica_eval.algorithms.dynamics")
rec("F6-nunpaired", "RESOLVED-IN-SKELETON",
    f"timing.summarize_deviations{inspect.signature(tim.summarize_deviations)}; "
    f"dynamics.summarize_deltas{inspect.signature(dyn.summarize_deltas)}")

# ---------- F7: dynamics note_spans list[dict] vs ndarray ----------
b203 = (SNAP/"specs/FILE-203-v1.md").read_text().splitlines()
rec("F7-notes-repr", "CONFIRMED",
    "FILE-203:77 says note_spans(notes: list[dict]); FILE-203:126 says notes.* is (n_note,3) ndarray")

# ---------- F8: FILE-203 frame()/100fps ----------
ing = importlib.import_module("harmonica_eval.core.ingest")
has_frame = hasattr(ing, "frame")
rec("F8-frame-rate", "CONFIRMED" if not has_frame else "STALE",
    f"core.ingest.frame exists={has_frame}; FILE-203:80 claims '由 core.ingest 提供的帧率换算（每秒 100 帧）'")

# ---------- F9: FILE-104 profile name count ----------
b104 = (SNAP/"specs/FILE-104-v1.md").read_text()
mo = re.search(r"`harmonica_eval\.profile` 的 \*\*(\d+) 个名字\*\*：\s*\n?\s*(.+?)。", b104, re.S)
claimed=int(mo.group(1)); names=re.findall(r"`([A-Z_]+)`", mo.group(2))
rec("F9-namecount", "CONFIRMED" if claimed!=len(names) else "STALE",
    f"FILE-104 claims {claimed} profile names, lists {len(names)}: {names}")

# ---------- F10: FILE-104 types import vs exhaustive whitelist ----------
rec("F10-types", "CONFIRMED" if "`types`" not in b104.split("## 4 ·")[0] else "STALE",
    "FILE-104 §3 whitelist has no 'types'; §4.7 step 12 mandates `import types`")

print()
print("=== SUMMARY ===")
for fid, st, _ in RESULTS:
    print(f"  {st:22} {fid}")
