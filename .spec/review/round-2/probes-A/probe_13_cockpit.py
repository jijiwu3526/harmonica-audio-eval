"""Probe 13: FILE-400/401 vs skeleton; and FILE-401's claim about UiSeries validation."""
import sys, inspect, pathlib
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
import harmonica_eval.cockpit as C
import harmonica_eval.cockpit.app as CA

ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
print("=== FILE-400 skeleton: cockpit/__init__ exports ===")
print("   launch_cockpit", inspect.signature(C.launch_cockpit))
print("   __all__ =", C.__all__)
print()
print("=== FILE-401 skeleton: cockpit/app.py callables ===")
for n,o in vars(CA).items():
    if callable(o) and getattr(o,'__module__',None)=='harmonica_eval.cockpit.app':
        try: sig = inspect.signature(o)
        except Exception: sig = '?'
        print(f"   {n}{sig}")
print("   __all__ =", getattr(CA,'__all__','<none>'))
print()
print("=== does app expose run_local_ui? (FILE-400 §4.2 launch_cockpit must delegate) ===")
print("   run_local_ui present:", hasattr(CA,'run_local_ui'))
print("   LOCAL_BIND_HOST present:", hasattr(CA,'LOCAL_BIND_HOST'))
print()
print("=== FILE-400 §4.2 text ===")
l = (ROOT/".spec/build/FILE-400-v1.md").read_text().splitlines()
for i in range(70, 118):
    print(f"  {i+1}: {l[i]}")
