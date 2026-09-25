"""Probe 10: FILE-105 build_surface 4-stage chain vs actually-importable entries."""
import sys, inspect
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
import harmonica_eval.core.surface as S
import harmonica_eval.core.features as F

print("=== FILE-105 §3 declares api.py may import from core.surface: ONLY 'Surface' ===")
print("=== FILE-105 §3 declares api.py may import core.features/align/ingest as stage entries ===\n")

print("core.features public callables:")
for n in ("materialize_pitch","materialize_rms","materialize_chroma","materialize_notes"):
    print(f"   {n}{inspect.signature(getattr(F,n))}")
print("   -> ANY aggregate 'produce all 12 ports' entry?",
      [n for n in dir(F) if not n.startswith('_') and callable(getattr(F,n)) and 'all' in n.lower()] or "NONE")

print()
print("core.surface public callables:")
for n in ("build_descriptor","seal","generate_all_ports","assert_budget","build_surface"):
    print(f"   {n}{inspect.signature(getattr(S,n))}")
print("   Surface.__init__:", inspect.signature(S.Surface.__init__))

print()
print("=== FILE-105 §4.5 stage 3 says features entry produces ALL ports ===")
print("    but skeleton has 4 per-feature functions and NO aggregate entry.")
print("=== FILE-105 §4.5 stage 4 says surface entry assembles ===")
print("    build_surface() internally calls generate_all_ports() (FILE-104 §4.7 step 5),")
print("    which ITSELF produces all 12 ports including the 8 feature ports.")
print()
print("=> DOUBLE GENERATION: stage3 (features) and stage4 (surface.build_surface)")
print("   both claim to produce the same 8 feature ports.")
print("=> api.py imports only 'Surface' from core.surface; it cannot call generate_all_ports,")
print("   assert_budget, build_descriptor, or build_surface per FILE-105 §3 whitelist.")
