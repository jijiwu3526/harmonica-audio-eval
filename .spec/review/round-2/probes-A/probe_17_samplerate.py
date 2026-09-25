"""Probe 17: api.py must pass sample_rate to align/features/surface, but is
forbidden to import profile, and ingest(uri) returns only samples."""
import sys, inspect, pathlib
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
import harmonica_eval.core.ingest as I
import harmonica_eval.core.surface as S
import harmonica_eval.core.features as F

ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
print("=== ingest public return types (skeleton, frozen) ===")
for n in ("decode_to_mono","resample_to_profile","validate_duration","assert_not_silent","ingest"):
    print(f"   {n}{inspect.signature(getattr(I,n))}")
print()
print("   ingest() -> NDArray  => returns ONLY samples. No sample_rate, no AudioFormat.")
print()
print("=== who needs sample_rate downstream? ===")
for n in ("build_surface","generate_all_ports","build_descriptor"):
    print(f"   surface.{n}{inspect.signature(getattr(S,n))}")
print(f"   features.materialize_pitch{inspect.signature(F.materialize_pitch)}")
print(f"   features.materialize_notes{inspect.signature(F.materialize_notes)}")
print()
print("=== FILE-105 stage 1 claims ingest yields 'PCM 与其 AudioFormat' ===")
b5 = (ROOT/".spec/build/FILE-105-v1.md").read_text().splitlines()
for i in range(158, 168):
    print(f"  {i+1}: {b5[i].strip()[:175]}")
print()
print("=== FILE-105 forbids importing profile ===")
for i,l in enumerate(b5,1):
    if "profile" in l and ("禁止" in l or "不 import" in l or "禁入" in l):
        print(f"  {i}: {l.strip()[:200]}")
print()
print("=== FILE-105 §4.10 constant table: does it state where sr comes from? ===")
for i,l in enumerate(b5,1):
    if "采样率" in l or "sample_rate" in l:
        print(f"  {i}: {l.strip()[:190]}")
