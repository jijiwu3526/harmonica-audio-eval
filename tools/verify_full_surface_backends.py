"""★ 判据 4/5：屏蔽 librosa，跑完整 12 端口的数据面，与装了 librosa 那次对拍。

判据4（对抗判据 —— 防「两边根本没各自算」）：
    屏蔽 librosa 强制走自写后端，跑 `build_surface` 生成**全部 12 个端口**，
    逐端口检查「非空 + 形状 + content_hash」，并与 librosa 后端那一次逐个对比。

    ★ 判据**不是**「hash 必须相同」——chroma 残差 1e-6 在 float32 下可能
      造成个别 bit 不同，那是可解释的浮点口径差。
    ★ 判据是「12 个端口全部非空且形状正确」，hash 不同则**如实报告**，
      绝不调实现去凑。

判据5：
    `sys.modules['librosa'] = None` 之后 `import harmonica_eval.core.features`
    必须成功 —— features.py 顶层任何地方碰到 librosa 就红。

用法: python3 tools/verify_full_surface_backends.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SR = 44100


# ══════════════════════════════════════════════════════════════════════
# 子进程内跑一遍 build_surface，把结果落成 JSON。
# 为什么要子进程：librosa 一旦被 import 进本进程，sys.modules 里就再也去不掉了。
# ══════════════════════════════════════════════════════════════════════
_CHILD = r'''
import builtins, json, os, sys
sys.path.insert(0, %(root)r)

BLOCK = os.environ.get("BLOCK_LIBROSA") == "1"

if BLOCK:
    _real = builtins.__import__
    def _blocked(name, *a, **kw):
        if name == "librosa" or name.startswith("librosa."):
            raise ModuleNotFoundError("No module named 'librosa' (simulated Android)")
        return _real(name, *a, **kw)
    builtins.__import__ = _blocked
    sys.modules["librosa"] = None      # ★ 判据5 的形态：模块位置直接置 None

import numpy as np
import soundfile as sf

from harmonica_eval import profile
from harmonica_eval.core import features, surface, align

SR = 44100
# 后端自证：记录走的是哪条
backend = features.ACTIVE_BACKEND

wavs = sorted((root_path := __import__("pathlib").Path(%(root)r) .joinpath("harmonica_mvp_dataset")).rglob("*.wav"))
ref_p, prac_p = wavs[0], wavs[3] if len(wavs) > 3 else wavs[1]

def load(p):
    y, sr = sf.read(str(p), dtype="float32", always_2d=False)
    if y.ndim > 1: y = y.mean(axis=1, dtype=np.float32)
    # ★ 只取 20 s：DTW 代价矩阵是 N²×8B（hop=2048 时 20s→431 帧→1.5 MB），
    #   整段 72 s 会到 855 MB。两后端用**同一段切片**，对拍才成立。
    y = y[: %(secs)d * SR]
    return np.ascontiguousarray(y, dtype=np.float32)

reference, practice = load(ref_p), load(prac_p)
sr = SR

# warp_path：align 侧走同一条 core 路径（align 本身不依赖 librosa，
# 但 features 的 chroma 端口会 —— 所以它同样是「12 端口」的一部分）。
ref_feat = align.compute_alignment_features(reference)
prac_feat = align.compute_alignment_features(practice)
warp = align.compute_warp_path(ref_feat, prac_feat)

srf = surface.build_surface(reference, practice, sr, warp)

ports = {}
for spec in profile.PORTS:
    pid = spec.port_id
    # ★ read() 返回的是 contract.BufferView（只读借用视图），数组在 .data 里，
    #   且 writeable=False —— 直接 astype 会拿到只读代理。复制一份再统计。
    view = srf.read(pid)
    arr = np.array(view.data, copy=True)
    d = srf.manifest().ports[pid]
    ports[pid] = {
        "shape": [int(x) for x in arr.shape],
        "dtype": str(arr.dtype),
        "content_hash": d.content_hash,
        "n_elements": int(arr.size),
        "all_zero": bool(arr.size == 0 or not np.any(arr)),
        "has_nan": bool(np.isnan(arr.astype(np.float64)).any()) if arr.dtype.kind == "f" else False,
        "max_abs": float(np.abs(arr.astype(np.float64)).max()) if arr.size else 0.0,
    }

print("@@JSON@@" + json.dumps({"backend": backend, "n_ports": len(ports), "ports": ports}))
''' % {"root": str(ROOT), "secs": 20}


def run_child(block: bool) -> dict:
    env = dict(**__import__("os").environ)
    env["BLOCK_LIBROSA"] = "1" if block else "0"
    env["PYTHONWARNINGS"] = "ignore"
    p = subprocess.run([sys.executable, "-c", _CHILD], capture_output=True,
                       text=True, env=env, timeout=7200)
    if p.returncode != 0:
        print(p.stdout[-4000:])
        print(p.stderr[-4000:], file=sys.stderr)
        raise SystemExit(f"子进程失败 (BLOCK_LIBROSA={env['BLOCK_LIBROSA']}) rc={p.returncode}")
    for line in p.stdout.splitlines():
        if line.startswith("@@JSON@@"):
            return json.loads(line[len("@@JSON@@"):])
    print(p.stdout[-4000:])
    raise SystemExit("子进程没输出 @@JSON@@")


def main() -> int:
    print("=" * 96)
    print("判据5：sys.modules['librosa']=None 后 import features")
    cmd = (f"python3 -c \"import sys; sys.path.insert(0,{str(ROOT)!r}); "
           f"sys.modules['librosa']=None; import harmonica_eval.core.features as F; "
           f"print('ACTIVE_BACKEND =', F.ACTIVE_BACKEND)\"")
    print(f"  命令: {cmd}")
    p = subprocess.run([sys.executable, "-c",
                        f"import sys; sys.path.insert(0,{str(ROOT)!r}); "
                        f"sys.modules['librosa']=None; "
                        f"import harmonica_eval.core.features as F; "
                        f"print('ACTIVE_BACKEND =', F.ACTIVE_BACKEND)"],
                       capture_output=True, text=True, timeout=600)
    print("  " + (p.stdout.strip() or "(无输出)"))
    if p.returncode != 0:
        print("  " + p.stderr.strip()[-2000:])
    ok5 = p.returncode == 0
    print(f"  [{'PASS' if ok5 else 'FAIL'}] 判据5：import features 在无 librosa 下成功")

    print("=" * 96)
    print("判据4：屏蔽 librosa 跑完整 12 端口，与 librosa 版对拍")
    print("  (每次 build_surface 在独立子进程里跑 —— librosa 一旦 import 就去不掉)")
    native = run_child(block=True)
    librosa_res = run_child(block=False)

    print(f"\n  native 后端自证 : ACTIVE_BACKEND = {native['backend']}")
    print(f"  librosa 后端自证: ACTIVE_BACKEND = {librosa_res['backend']}")
    assert native["backend"] == "native", f"屏蔽后仍报 {native['backend']}，屏蔽没生效"
    assert librosa_res["backend"] == "librosa", f"未屏蔽却报 {librosa_res['backend']}"

    np_ = native["n_ports"]
    print(f"\n  端口数: native {np_} / librosa {librosa_res['n_ports']}（profile 声明 "
          f"{len(__import__('harmonica_eval.profile', fromlist=['x']).PORTS)}）")

    hdr = f"  {'port_id':26s} {'shape':>18s} {'非空':>5s} {'全零':>5s} {'NaN':>5s} {'hash(librosa)':>18s} {'hash(native)':>18s} 同?"
    print("\n" + hdr)
    print("  " + "-" * (len(hdr) - 2))

    failures = []
    same_hash, diff_hash = [], []
    for pid in librosa_res["ports"]:
        a = librosa_res["ports"][pid]
        b = native["ports"].get(pid)
        if b is None:
            failures.append(f"{pid}: native 缺失该端口")
            print(f"  {pid:26s} {'缺失':>18s}")
            continue
        nonempty = b["n_elements"] > 0 and not b["all_zero"]
        no_nan = not b["has_nan"]
        same = a["content_hash"] == b["content_hash"]
        (same_hash if same else diff_hash).append(pid)
        shape_ok = a["shape"] == b["shape"]
        print(f"  {pid:26s} {str(tuple(b['shape'])):>18s} "
              f"{'OK' if nonempty else '空!':>5s} {'是!' if b['all_zero'] else '否':>5s} "
              f"{'有!' if b['has_nan'] else '无':>5s} "
              f"{a['content_hash'][:16]:>18s} {b['content_hash'][:16]:>18s} {'✓' if same else '✗'}")
        if not nonempty:
            failures.append(f"{pid}: native 端口为空或全零 (n={b['n_elements']})")
        if not no_nan:
            failures.append(f"{pid}: native 端口含 NaN")
        if not shape_ok:
            failures.append(f"{pid}: 形状不一致 librosa={a['shape']} native={b['shape']}")

    print(f"\n  hash 相同: {len(same_hash)}/{np_}  {same_hash}")
    print(f"  hash 不同: {len(diff_hash)}/{np_}  {diff_hash}")
    for pid in diff_hash:
        a, b = librosa_res["ports"][pid], native["ports"][pid]
        print(f"    {pid}: max|Δ| 相关 —— librosa max_abs={a['max_abs']:.6e} native max_abs={b['max_abs']:.6e}")

    ok4 = not failures
    print(f"\n  [{'PASS' if ok4 else 'FAIL'}] 判据4：12 个端口全部非空 + 形状正确（hash 不作为判据）")
    for f in failures:
        print("    -", f)

    print("=" * 96)
    if not (ok4 and ok5):
        return 1
    print("判据4、判据5 全部取得。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
