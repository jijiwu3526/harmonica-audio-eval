"""P1 probe F: warp_path 既作入参又作产物；终端指标无生产者。只读。"""
import pathlib, sys
sys.path.insert(0,'.')
from harmonica_eval import profile, contract

print("== 1. warp_path：build_surface 的入参 vs generate_all_ports 的产物 ==")
s = pathlib.Path('.spec/build/FILE-104-v1.md').read_text(encoding='utf-8').splitlines()
for i,l in enumerate(s,1):
    if 'warp_path: int32[N, 2]' in l or ('warp_path` 是入参' in l) or ('core.align.align' in l) or ('ports = generate_all_ports' in l) or ('校验 `warp_path.dtype' in l):
        print(f"  FILE-104 L{i}: {l.strip()[:120]}")

print()
print("== 2. warp_path 的 hop_length（换算 reference_frame 用）==")
wp = profile.PORT_INDEX['warp_path']
print(f"  profile.PORT_INDEX['warp_path'].hop_length = {wp.hop_length}")
print("  profile.py:526 强制：非 frame 维端口 hop_length 必须 == 0")
print("  contract.py:443 换算规则：units=='index' -> 秒*sample_rate/hop_length")
print("  contract.py:429 明令：换算依据是该端口自己的 hop_length（不是 ALIGN.hop_length）")
print("  => warp_path.reference_frame 实际落在 ALIGN.hop_length=2048 的 chroma 栅格上，")
print("     但端口只能声明 hop=0 -> 秒<->reference_frame 换算除零/无定义。")

print()
print("== 3. 终端指标：SPEC §3 要求 vs 生产者 ==")
spec = pathlib.Path('SPEC.md').read_text(encoding='utf-8').splitlines()
for i,l in enumerate(spec,1):
    if any(k in l for k in ('mean_abs_warp_sec','pitch_cents_mae','sections')):
        print(f"  SPEC.md L{i}: {l.strip()[:110]}")
from harmonica_eval.algorithms import PAYLOAD_SCHEMAS
pk = {k for v in PAYLOAD_SCHEMAS.values() for k in v}
need = {'mean_abs_warp_sec','tempo_ratio','confidence','pitch_cents_mae','in_tune_ratio','timing_mae_ms','energy_db_delta'}
print("  payload 键:", sorted(pk))
print("  SPEC 要求但无 payload 生产者:", sorted(need - pk))

print()
print("== 4. align 的真实消费者 ==")
import re, subprocess
out = subprocess.run(['grep','-rn','align(','--include=*.py','harmonica_eval/'],capture_output=True,text=True).stdout
for l in out.splitlines():
    print("  ", l)
