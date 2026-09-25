"""Probe 04: verify existence of every dotted symbol referenced in the BIs."""
import sys, importlib, re, pathlib
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")

ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")

def resolve(dotted):
    parts = dotted.split(".")
    for i in range(len(parts), 0, -1):
        mod = ".".join(parts[:i])
        try:
            obj = importlib.import_module(mod)
        except Exception:
            continue
        try:
            for p in parts[i:]:
                obj = getattr(obj, p)
            return True, None
        except AttributeError as e:
            return False, f"module {mod} ok but attr missing: {e}"
    return False, f"no importable prefix in {dotted}"

TARGETS = [
 # FILE-203 dynamics
 ("FILE-203", "harmonica_eval.core.ingest.SILENCE_RMS_THRESHOLD"),
 ("FILE-203", "harmonica_eval.core.ingest.frame"),
 # FILE-203 skeleton-quoted shapes
 ("FILE-203", "harmonica_eval.core.ingest.SILENCE_RMS_THRESHOLD"),
 # FILE-200 registry
 ("FILE-200", "harmonica_eval.algorithms.pitch.ALGORITHM_ID"),
 ("FILE-200", "harmonica_eval.algorithms.timing.ALGORITHM_ID"),
 ("FILE-200", "harmonica_eval.algorithms.dynamics.ALGORITHM_ID"),
 ("FILE-200", "harmonica_eval.algorithms.pitch.ALGORITHM_VERSION"),
 ("FILE-200", "harmonica_eval.algorithms.timing.ALGORITHM_VERSION"),
 ("FILE-200", "harmonica_eval.algorithms.dynamics.ALGORITHM_VERSION"),
 ("FILE-200", "harmonica_eval.algorithms.pitch.run"),
 ("FILE-200", "harmonica_eval.algorithms.timing.run"),
 ("FILE-200", "harmonica_eval.algorithms.dynamics.run"),
 # FILE-301 host app
 ("FILE-301", "harmonica_eval.host.app.build_default_app"),
 ("FILE-301", "harmonica_eval.host.build_default_app"),
 ("FILE-301", "harmonica_eval.host.app.HostApp"),
 # FILE-400 cockpit
 ("FILE-400", "harmonica_eval.cockpit.app.LOCAL_BIND_HOST"),
 ("FILE-400", "harmonica_eval.cockpit.app.run_local_ui"),
 ("FILE-400", "harmonica_eval.cockpit.launch_cockpit"),
 # FILE-104 surface
 ("FILE-104", "harmonica_eval.core.surface.generate_all_ports"),
 ("FILE-104", "harmonica_eval.core.surface.port_prefix"),
 ("FILE-104", "harmonica_eval.core.surface.build_surface"),
 ("FILE-104", "harmonica_eval.core.surface.Surface"),
 # FILE-105
 ("FILE-105", "harmonica_eval.core.api.HostCore"),
 ("FILE-105", "harmonica_eval.core.api.INTERNAL_STAGES"),
 # contract / profile
 ("FILE-003", "harmonica_eval.contract.UI_PAYLOAD_KEYS"),
 ("FILE-004", "harmonica_eval.profile.PORT_INDEX"),
]
print(f"{'BI':<10} {'symbol':<62} {'status'}")
print("-"*100)
for bi, sym in TARGETS:
    ok, err = resolve(sym)
    print(f"{bi:<10} {sym:<62} {'OK' if ok else 'MISSING -> '+str(err)}")
