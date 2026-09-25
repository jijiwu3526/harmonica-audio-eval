"""Probe 02: verify FILE-104 §4.4's claim that (produced_by, units, dimensions,
timeline_basis) yields exactly 7 distinct keys over the 12 ports, and that the
claimed 7 rows match reality."""
import sys, collections
sys.path.insert(0, "/Users/Apple/Desktop/dsh-archive/harmonica-eval")
from harmonica_eval import profile

keys = collections.OrderedDict()
for s in profile.PORTS:
    k = (s.produced_by, s.units, tuple(s.dimensions), s.timeline_basis)
    keys.setdefault(k, []).append(s.port_id)

print("n_ports            =", len(profile.PORTS))
print("n_distinct_keys    =", len(keys))
print("SPEC CLAIM         = 7  ->", "MATCH" if len(keys)==7 else "*** MISMATCH ***")
print()
for k, ports in keys.items():
    print(f"  {k}")
    print(f"      -> {ports}")
print()
print("--- claimed table in FILE-104 §4.4, transcribed ---")
CLAIMED = [
 ("core.align","index",("warp_point","axis"),"REFERENCE",["warp_path"],"core.align.align"),
 ("core.features","hz",("frame","field"),"REFERENCE",["pitch.reference","pitch.practice"],"materialize_pitch"),
 ("core.features","rms",("frame",),"REFERENCE",["rms.reference","rms.practice"],"materialize_rms"),
 ("core.features","chroma",("frame","bin"),"REFERENCE",["chroma.lowres.reference","chroma.lowres.practice"],"materialize_chroma"),
 ("core.features","index",("note","field"),"REFERENCE",["notes.reference","notes.practice"],"materialize_notes"),
 ("core.surface","amplitude",("sample",),"REFERENCE",["pcm.mapped.reference","pcm.mapped.practice"],"forward"),
 ("core.surface","amplitude",("sample",),"WARPED",["pcm.warped.practice"],"reindex"),
]
actual = {k: v for k, v in keys.items()}
print(f"{'claimed key':<70} {'in actual?':<12} claimed-ports-vs-actual")
ok = True
for pb, un, dim, tb, ports, prod in CLAIMED:
    k = (pb, un, dim, profile.TimelineBasis[tb])
    hit = k in actual
    same = hit and sorted(actual[k]) == sorted(ports)
    if not (hit and same): ok = False
    print(f"{str(k):<70} {str(hit):<12} {sorted(actual.get(k,[]))} vs {sorted(ports)} {'OK' if same else '*** DIFF ***'}")
print()
print("ALL 7 CLAIMED ROWS MATCH ACTUAL:", ok)
extra = [k for k in actual if k not in {(a,b,c,profile.TimelineBasis[d]) for a,b,c,d,_,_ in CLAIMED}]
print("actual keys NOT in claimed table:", extra)
