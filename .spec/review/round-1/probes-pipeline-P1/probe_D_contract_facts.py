"""P1 probe D: 契约内部事实核对（read 换算、warp_path hop、notes units、status 取值）。
只读。"""
import sys; sys.path.insert(0,'.')
from harmonica_eval import profile, contract

print("== 1. warp_path 的 hop_length 与 read() 的 index 换算规则 ==")
wp = profile.PORT_INDEX["warp_path"]
print(f"  warp_path: units={wp.units!r} dimensions={tuple(wp.dimensions)} hop_length={wp.hop_length}")
print("  contract.py:443 规则: units=='index' -> 秒*sample_rate/hop_length")
print("  hop_length=0 => 除零；contract 只说 warp_path 按 reference_frame 换算后的秒值筛选，")
print("  未给出该用哪个 hop（且 contract.py:429 明令调用方不得用 ALIGN.hop_length）。")

print()
print("== 2. notes.* units 与字段语义 ==")
n = profile.PORT_INDEX["notes.reference"]
print(f"  notes.reference: units={n.units!r} fields={tuple(n.field_names)} hop={n.hop_length}")
print("  字段是 (秒, Hz, RMS)，但 units 声明为 'index' —— 单位与内容不符。")

print()
print("== 3. contract 允许的 envelope.status 取值 vs 算法 BUILD-INSTRUCTION ==")
print("  contract.py:380  docstring: 'OK' | 'FAILED' | 'INCOMPATIBLE'")
print("  FILE-201:297      status = \"SUCCEEDED\" | \"FAILED\"   <-- SUCCEEDED 不在契约取值内")
print("  FILE-203:129      status='OK'                        <-- 与契约一致")
print("  pitch.py:158      'status=FAILED 的信封'（未提成功取值）")

print()
print("== 4. 无消费者的端口（含设计豁免）==")
from harmonica_eval.algorithms import ALGORITHMS
consumed = {p for a in ALGORITHMS for p in a.required_ports}
for p in profile.PORTS:
    if p.port_id not in consumed:
        print(f"  {p.port_id:26s} produced_by={p.produced_by}")

print()
print("== 5. SPEC §3 要求的 metrics 键 是否有生产者 ==")
spec_keys = ["mean_abs_warp_sec","tempo_ratio","confidence",
             "pitch_cents_mae","in_tune_ratio","timing_mae_ms","energy_db_delta"]
from harmonica_eval.algorithms import PAYLOAD_SCHEMAS
payload_keys = {k for v in PAYLOAD_SCHEMAS.values() for k in v}
print("  SPEC 键:", spec_keys)
print("  算法 payload 键:", sorted(payload_keys))
print("  SPEC 键中在 payload 里的:", sorted(set(spec_keys) & payload_keys))
print("  => 无生产者:", sorted(set(spec_keys) - payload_keys))
