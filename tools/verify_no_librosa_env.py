"""模拟「设备上没有 librosa」：把它从 import 里挡掉，跑完整 features 端口。

这是 Android 场景的真实复现 —— 设备上 numpy/scipy/soundfile 都在，
唯独 librosa 装不上。判据是：挡住 librosa 之后，features.py 的四个
materialize_* 仍能产出与 librosa 后端**形状相同**的端口。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ★ 在 import 任何东西之前把 librosa 挡在门外，模拟设备
import builtins  # noqa: E402

_real_import = builtins.__import__


def _blocked_import(name, *args, **kwargs):
    if name == "librosa" or name.startswith("librosa."):
        raise ModuleNotFoundError("No module named 'librosa' (simulated Android)")
    return _real_import(name, *args, **kwargs)


builtins.__import__ = _blocked_import

try:
    import librosa  # noqa: F401
    print("FAIL: librosa 居然 import 成功了，模拟没生效")
    raise SystemExit(2)
except ModuleNotFoundError as e:
    print(f"librosa 已被挡住: {e}")

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from harmonica_eval.core import features  # noqa: E402

print("ACTIVE_BACKEND:", features.ACTIVE_BACKEND)
print("REASON      :", features.ACTIVE_BACKEND_REASON)
assert features.ACTIVE_BACKEND == "native", "librosa 不可用时必须落到自写后端"

wav = sorted((ROOT / "harmonica_mvp_dataset").rglob("*.wav"))[0]
y, sr = sf.read(str(wav), dtype="float32", always_2d=False)
if y.ndim > 1:
    y = y.mean(axis=1).astype(np.float32)
y = np.ascontiguousarray(y[: 44100 * 12], dtype=np.float32)
print(f"\n输入: {wav.relative_to(ROOT)} 前 12s  n={len(y)}  sr={sr}")

pitch = features.materialize_pitch(y, sr)
rms = features.materialize_rms(y)
chroma = features.materialize_chroma(y, sr)
notes = features.materialize_notes(pitch, rms, sr)

print(f"  pitch  {pitch.shape} {pitch.dtype}   （应 (n_frames, 3)）")
print(f"  rms    {rms.shape} {rms.dtype}")
print(f"  chroma {chroma.shape} {chroma.dtype}   （应 (n_frames, 12)）")
print(f"  notes  {notes.shape} {notes.dtype}   （应 (n_notes, 3)）")

# 与 features._frame_count 的声明口径对拍（帧数必须自洽）
n_expected = features._frame_count(
    len(y), features.MATERIALIZE.pitch_frame_length,
    features.MATERIALIZE.pitch_hop_length)
assert pitch.shape[0] == n_expected, (pitch.shape, n_expected)
# ★ 注意 pitch 与 chroma 的帧数本就差 1（259 vs 258）：两者 n_fft/frame_length
#   都是 2048，但 features.materialize_pitch 把 pyin 的 259 帧按
#   min(len(f0), n_frames) 截到 258（frozen 逻辑，见 features.py:180）。
#   ★ 这不是自写后端引入的偏差 —— librosa 后端同样是 258/259。
#   本脚本只断言「形状合法 + 无 NaN + 未发声帧 f0==0」；
#   逐帧对齐由 tools/verify_backend_equivalence.py 的判据3 负责。
assert np.isfinite(pitch).all(), "pitch 端口含 NaN/inf"
assert np.isfinite(chroma).all(), "chroma 端口含 NaN/inf"
assert not (pitch[:, 0] < 0).any(), "f0 出现负值"
voiced = pitch[:, 1] > 0.5
assert (pitch[~voiced, 0] == 0).all(), "未发声帧的 f0 必须为 0"
print("\n全部断言通过：帧数自洽、无 NaN/inf、未发声帧 f0==0")

# ══ 端口级对拍：把同一段音频在 librosa 后端下再跑一遍，逐元素比 ══
# 后端必须是「透明」的：换后端只许有数值舍入级差异，不许改变端口形状或取值。
import importlib  # noqa: E402

np.save("/tmp/_parity_y.npy", y)

code = r'''
import sys, numpy as np
sys.path.insert(0, %r)
import importlib.util as iu
from harmonica_eval.core import features
assert features.ACTIVE_BACKEND == "librosa", features.ACTIVE_BACKEND
y = np.load("/tmp/_parity_y.npy"); sr = 44100
p = features.materialize_pitch(y, sr); c = features.materialize_chroma(y, sr)
n = features.materialize_notes(p, features.materialize_rms(y), sr)
np.savez("/tmp/_parity_lib.npz", p=p, c=c, n=n)
''' % (str(ROOT),)
import subprocess  # noqa: E402
subprocess.run([sys.executable, "-c", code], check=True)

lib = np.load("/tmp/_parity_lib.npz")
for port, native_arr in (("pitch", pitch), ("chroma", chroma), ("notes", notes)):
    ref = lib[port[0] if len(port) == 1 else "p" if port == "pitch"
              else "c" if port == "chroma" else "n"]
    assert ref.shape == native_arr.shape, f"{port} 形状不同: {ref.shape} vs {native_arr.shape}"
    d = float(np.abs(ref.astype(np.float64) - native_arr.astype(np.float64)).max())
    print(f"  端口 {port:7s} 形状 {str(ref.shape):12s} 两后端 max|Δ| = {d:.3e}")
    assert d < 1e-3, f"{port} 差异过大: {d}"

print("\n端口级对拍通过：两后端形状完全相同，数值差异在 float32 舍入量级。")
