"""Probe 26: run FILE-100 §8 criterion B VERBATIM (copied from the BI)."""
import harmonica_eval.core as core
import harmonica_eval.profile as profile

def _iter_ports(p):
    if isinstance(p, dict):
        return list(p.values())
    return list(p)

def _field(obj, name):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)

def _names(v):
    if isinstance(v, str):
        return [v]
    return [x for x in v]

declared = set(core.__all__)
produced = set()
for port in _iter_ports(profile.PORTS):
    for pb in _names(_field(port, "produced_by")):
        assert isinstance(pb, str), pb
        if pb.startswith("core."):
            produced.add(pb.split(".")[1])

print("declared =", sorted(declared))
print("produced =", sorted(produced))
assert declared == produced, (sorted(declared), sorted(produced))
assert core.__all__ == ["ingest", "align", "features", "surface", "api"], core.__all__
print("PASS 判据B declared == produced ==", sorted(declared))
