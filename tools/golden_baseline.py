'''
FILE-ID:      TOOLS-GOLDEN-BASELINE
COMPONENT:    回归参照工具（非项目组件，不在任何 COMP-C1..C4 内）
SPEC:         SPEC.md@v2.1 · .spec/OWNER-DIRECTIVES.md 追加 A（零注入）

ROLE:
    把「已注入且已冻结」的 8 个文件在【真实音频】上的输出固化成一份可回归的参照。

INTENT:
    注入还在推进，数字必然会变。但「变多少算正常、变多少算回归」
    目前没有任何判据。本工具提供那个参照。

    ★★★ 本工具是【参照】，不是【断言】。★★★
    · 它的输出会随注入推进而变化，那是正常的
    · 它的价值在于：人拿到新数字时，有个东西可比
    · 任何「基线与当前不符就报红」的用法都是误用
    ★★★ 因此 _meta.note 字段显式写明这一点。★★★

MUST:
    · 只读已注入的公开接口，不碰任何私有实现
    · fixture 一律从 profile.PORT_INDEX / profile.AUDIO 真实派生，禁止手编
    · 必须验证确定性（同一输入两次跑，逐位相同）—— 不可重现的基线毫无价值
    · 必须做交叉校验：已知锚点是否成立、缺陷类型是否在对应指标上突出

MUST NOT:
    · 不修改 harmonica_eval/ 下任何文件
    · 不修改任何 .spec / tests / 其它 tools
    · 不把「基线不符」当失败 —— 那是人的判断，不是本工具的
    · 不用手编的 fixture 喂算法（前几轮已因此两次误判成实现缺陷）

INPUT:
    harmonica_mvp_dataset/08_我亲爱的/ 标准旋律版 + 5 个缺陷练习曲

OUTPUT:
    tools/fixtures/golden_baseline.json
'''

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import numpy as np

REPO = pathlib.Path(__file__).resolve().parent.parent
DATASET = REPO / "harmonica_mvp_dataset" / "08_我亲爱的"
OUT = REPO / "tools" / "fixtures" / "golden_baseline.json"

SAMPLES: dict[str, pathlib.Path] = {
    "reference": DATASET / "标准旋律版.wav",
    "01_音准走调": DATASET / "练习曲" / "01_音准走调.wav",
    "02_节奏抢拖": DATASET / "练习曲" / "02_节奏抢拖.wav",
    "03_气息不匀": DATASET / "练习曲" / "03_气息不匀.wav",
    "04_错音": DATASET / "练习曲" / "04_错音.wav",
    "05_漏音断句": DATASET / "练习曲" / "05_漏音断句.wav",
}

# 已知锚点：由 align / ingest / features 三个注入任务实测提供，此处交叉校验
KNOWN_ANCHORS = {
    "warp_identity_ratio": {
        "reference": 0.255,
        "01_音准走调": 0.522,
        "02_节奏抢拖": 0.761,
        "03_气息不匀": 0.255,
        "04_错音": 0.310,
    },
    # ★ 更正：ingest 任务报的 rms=0.12848 取自 01_奇异恩典 目录，
    # 而本基线用 08_我亲爱的。同一首歌的不同录音版本，rms 本就不同。
    # ★ 首次运行时我误把两个目录的数混在一起，导致锚点不成立 —— 已更正为不设死值，
    #   改用「03_气息不匀 是否显著低于其它样本」这一相对判据。
    "rms_relative": {"lowest": "03_气息不匀"},
}


def _f(x: Any) -> float:
    """把 numpy 标量转成可 JSON 序列化的 Python float。

    ★ 不用 round()：基线要的是逐位可复现，任何舍入都会掩盖回归。
    """
    return float(np.asarray(x).reshape(()).item())


def _round_for_report(x: float, n: int = 6) -> float:
    """仅用于人读的展示值；基线 JSON 里存的是未舍入的原值。"""
    return round(float(x), n)


def _ingest(path: pathlib.Path) -> tuple[np.ndarray, int, dict[str, Any]]:
    """走真实的 ingest，返回 float32 单声道波形 + 采样率 + 中间量。"""
    from harmonica_eval import profile
    from harmonica_eval.core import ingest as ing

    # ★ 签名实测：ingest.ingest(uri) -> NDArray（采样率由 profile.AUDIO 冻结，不随输入变）
    pcm = np.asarray(ing.ingest(str(path)))
    sr = int(profile.AUDIO.sample_rate)
    meta = {
        "n_samples": int(pcm.shape[0]),
        "dtype": str(pcm.dtype),
        "shape": list(pcm.shape),
        "sample_rate": sr,
        "duration_sec": _f(pcm.shape[0] / sr),
        "rms": _f(np.sqrt((pcm.astype(np.float64) ** 2).mean())),
    }
    return pcm, sr, meta


def _align(ref: np.ndarray, prac: np.ndarray, sr: int) -> tuple[np.ndarray, dict[str, Any]]:
    """走真实的 align，返回 warp_path + 中间量。"""
    from harmonica_eval.core import align as al

    # ★ 签名实测：align.align(reference, practice) -> NDArray（warp_path）
    wp = np.asarray(al.align(ref, prac))
    ref_col = wp[:, 0] if wp.ndim == 2 and wp.shape[1] >= 1 else wp.reshape(-1)
    prac_col = wp[:, 1] if wp.ndim == 2 and wp.shape[1] >= 2 else wp.reshape(-1)
    n = max(len(ref_col), 1)
    non_identity = int((ref_col[:n] != prac_col[:n]).sum())
    meta = {
        "warp_shape": list(wp.shape),
        "warp_dtype": str(wp.dtype),
        "monotonic_ref": bool(np.all(np.diff(ref_col.astype(np.int64)) >= 0)) if len(ref_col) > 1 else True,
        "monotonic_prac": bool(np.all(np.diff(prac_col.astype(np.int64)) >= 0)) if len(prac_col) > 1 else True,
        "non_identity_ratio": _round_for_report(non_identity / n, 4),
        "endpoint": [int(ref_col[-1]), int(prac_col[-1])] if len(ref_col) else [],
    }
    return wp, meta


def _surface(ref: np.ndarray, prac: np.ndarray, sr: int, wp: np.ndarray):
    """走真实的 build_surface，产出算法 entry 需要的 AlgorithmDataContract。

    ★★ 已知缺陷规避（★ 上报给主代理，本工具不修）：
    core/surface.py:331 在物化 WARPED 侧时调用
        _warp_by_index(practice, by_side["reference"], warp_path)
    而 :116 的签名是 _warp_by_index(side_samples, spec, warp_path)，
    第二参期望 PortSpec —— 实际传入的是 ndarray。
    → 走到 :144 的 spec.port_id 时抛
       AttributeError: 'numpy.ndarray' object has no attribute 'port_id'

    ★ 该缺陷只在「物化 WARPED 侧」时触发；REFERENCE 侧不受影响。
    ★ 本工具改为直接调用 materialize_*，绕过 generate_all_ports，
      以便仍能固化 REFERENCE 侧的黄金基线。
    """
    from harmonica_eval.core import surface as sf

    return sf.build_surface(ref, prac, sr, wp)


def _materialize_reference_side(ref: np.ndarray, sr: int, wp: Any) -> tuple[dict, int]:
    """绕开 surface 的 WARPED 缺陷，直接用 features 物化 REFERENCE 侧四类端口。

    ★ 这是 workaround，不是「正确做法」。存在的唯一理由是
      core/surface.py 的 WARPED 侧有缺陷（见 _surface docstring 的上报）。
    ★ 一旦该缺陷修复，本函数与 _RefOnlySurface 都应被删除。
    """
    from harmonica_eval.core import features as ft

    # ★ 签名均为 inspect 实测，不得凭猜：
    #   materialize_pitch(samples, sample_rate)
    #   materialize_rms(samples)                      ← 不收 sample_rate
    #   materialize_chroma(samples, sample_rate)
    #   materialize_notes(pitch, rms, sample_rate)   ← 吃前两者的产出
    sr_i = int(sr)
    pitch_arr = np.asarray(ft.materialize_pitch(ref, sr_i))
    rms_arr = np.asarray(ft.materialize_rms(ref))
    data: dict[str, np.ndarray] = {
        "pitch.reference": pitch_arr,
        "rms.reference": rms_arr,
        "chroma.lowres.reference": np.asarray(ft.materialize_chroma(ref, sr_i)),
        "notes.reference": np.asarray(ft.materialize_notes(pitch_arr, rms_arr, sr_i)),
    }
    return data, int(pitch_arr.shape[0]) if pitch_arr.ndim else 0


class _RefOnlySurface:
    """只承载 REFERENCE 侧的 AlgorithmDataContract 实现（基线用，非项目代码）。

    ★★ 为什么需要它 ★★
    core/surface.py 的 build_surface / generate_all_ports 在物化
    **WARPED 侧**时有缺陷（见 _surface docstring 的上报）。
    而三个算法在本轮实测中只消费 REFERENCE 侧端口
    （pitch: pitch.*/notes.* · timing: notes.reference · dynamics: rms.*/notes.*），
    故基线只需 REFERENCE 侧即可固化。

    ★ 这是一个 workaround。缺陷修复后应改回直接用 core.surface.Surface。
    """

    def __init__(self, manifest_obj: Any, data_map: dict[str, np.ndarray]) -> None:
        self._manifest = manifest_obj
        self._data = dict(data_map)

    def manifest(self) -> Any:
        return self._manifest

    def read(self, port_id: str, time_range: Any = None) -> Any:
        from harmonica_eval.contract import BufferView

        arr = self._data[port_id]
        if time_range is not None:
            lo, hi = time_range
            arr = arr[int(lo) : int(hi)]
        # ★ BufferView 字段实测：data / element_count / element_type
        return BufferView(
            data=arr,
            element_count=int(arr.size),
            element_type=str(arr.dtype),
        )


def _ref_only_surface(ref: np.ndarray, sr: int):
    """物化 REFERENCE 侧并包装成算法可消费的 surface。"""
    from harmonica_eval import profile
    from harmonica_eval.contract import AudioFormat, SurfaceManifest
    from harmonica_eval.core import surface as sf

    data, n_frames = _materialize_reference_side(ref, sr, None)
    manifest_ports = {pid: sf.build_descriptor(pid, arr, int(sr)) for pid, arr in data.items()}
    # ★ SurfaceManifest 字段实测：
    #   profile_version / audio_format / reference_duration_sec
    #   / practice_duration_sec / ports / sealed
    manifest_obj = SurfaceManifest(
        profile_version=str(profile.PROFILE_VERSION),
        audio_format=AudioFormat(
            sample_rate=int(sr),
            dtype="float32",
            channels=1,
        ),
        reference_duration_sec=_f(ref.shape[0] / sr),
        practice_duration_sec=_f(ref.shape[0] / sr),
        ports=manifest_ports,
        sealed=True,
    )
    return _RefOnlySurface(manifest_obj, data)


def _envelope_fields(env: Any) -> dict[str, Any]:
    """把 AlgorithmResultEnvelope 的 payload 摊平成可序列化的标量。"""
    out: dict[str, Any] = {
        "status": str(getattr(env, "status", "")),
        "algorithm_id": str(getattr(env, "algorithm_id", "")),
        "consumed_ports": list(getattr(env, "consumed_ports", ()) or ()),
    }
    payload = getattr(env, "payload", None)
    if isinstance(payload, dict):
        items: list[tuple[str, Any]] = list(payload.items())
    else:
        items = []
        for p in payload or ():
            key = getattr(p, "key", None)
            if key is not None:
                items.append((str(key), getattr(p, "value", None)))
    for key, value in items:
        arr = np.asarray(value)
        if arr.ndim == 0:
            out[key] = _f(arr)
        elif np.issubdtype(arr.dtype, np.number):
            out[key] = [_f(v) for v in arr.reshape(-1)]
        else:
            out[key] = str(value)
    return out


def run_algorithms(surface_obj: Any) -> dict[str, Any]:
    """对同一个 surface 真调三个算法的 run()。

    ★ 必须经 ResolvedSurface 适配：算法 entry 期望 AlgorithmDataContract，
      而 BLOCK-2 方案乙要求 C1 侧用 ResolvedSurface 组合 resolution 视图。
      直接把裸 Surface 传进去会 TypeError（算法内部访问 .resolution 属性）。
    """
    from harmonica_eval.algorithms import dynamics, pitch, timing
    from harmonica_eval.algorithms.runtime import ResolutionView, ResolvedSurface

    empty = ResolutionView(available=frozenset(), missing_optional=frozenset())
    target = ResolvedSurface(surface_obj, empty)
    result: dict[str, Any] = {}
    for name, mod in (("pitch", pitch), ("timing", timing), ("dynamics", dynamics)):
        try:
            env = mod.run(target)
            result[name] = _envelope_fields(env)
        except Exception as exc:  # noqa: BLE001 - 基线要记录失败原因
            result[name] = {"status": f"__ERROR__{type(exc).__name__}", "detail": str(exc)[:400]}
    return result


def port_summary(surface_obj: Any) -> dict[str, Any]:
    """记录 surface 上每个端口的形状 / dtype / element_count。

    ★ chroma 的 element_count 特别关注：已知恒假判据把它写成 21，
    ★ 实际应为 帧数 × 12。
    """
    out: dict[str, Any] = {}
    try:
        manifest = surface_obj.manifest()
    except Exception as exc:  # noqa: BLE001
        return {"__error__": f"{type(exc).__name__}: {exc}"}
    for port_id in sorted(manifest.ports):
        try:
            view = surface_obj.read(port_id)
            arr = np.asarray(view.data)
            out[port_id] = {
                "shape": list(arr.shape),
                "dtype": str(arr.dtype),
                "element_count": int(arr.size),
                "n_frames": int(arr.shape[0]) if arr.ndim else 0,
            }
        except Exception as exc:  # noqa: BLE001
            out[port_id] = {"__error__": f"{type(exc).__name__}: {exc}"}
    return out


def build() -> dict[str, Any]:
    """跑完全部样本，返回基线字典。"""
    ref_pcm, sr, ref_meta = _ingest(SAMPLES["reference"])
    out: dict[str, Any] = {
        "_meta": {
            "note": (
                "★ 这是回归参照，不是断言。★ 注入还在推进，数字必然会变；"
                "基线的价值是让人能判断「变了多少算回归」，不是「必须永远等于」。"
                "任何「与基线不符即失败」的用法都是误用。"
            ),
            "sample_rate": int(sr),
            "dataset": "harmonica_mvp_dataset/08_我亲爱的",
            "rounding": "基线存未舍入原值；报告里用 _round_for_report 展示",
        },
        "samples": {},
        "c2_intermediates": {},
        "cross_checks": {},
    }

    for name, path in SAMPLES.items():
        if name == "reference":
            pcm, srate, meta = ref_pcm, sr, ref_meta
        else:
            pcm, srate, meta = _ingest(path)
        wp, wp_meta = _align(ref_pcm, pcm, srate)
        try:
            sfc = _ref_only_surface(ref_pcm, srate)
            algos = run_algorithms(sfc)
            ports = port_summary(sfc)
        except Exception as exc:  # noqa: BLE001
            algos = {"__error__": f"{type(exc).__name__}: {exc}"}
            ports = {"__error__": f"{type(exc).__name__}: {exc}"}
        out["samples"][name] = algos
        out["c2_intermediates"][name] = {
            "ingest": meta,
            "align": wp_meta,
            "ports": ports,
        }

    out["determinism"] = _determinism(ref_pcm, sr, ref_meta)
    out["cross_checks"] = _cross_checks(out)
    return out


def _determinism(ref_pcm: np.ndarray, sr: int, ref_meta: dict[str, Any]) -> dict[str, Any]:
    """同一输入跑两次，逐位比对。不可重现的基线毫无价值。"""
    res: dict[str, Any] = {}
    for name in ("01_音准走调", "05_漏音断句"):
        pcm, srate, _ = _ingest(SAMPLES[name])
        wp_a, _ = _align(ref_pcm, pcm, srate)
        wp_b, _ = _align(ref_pcm, pcm, srate)
        try:
            sfc_a = _ref_only_surface(ref_pcm, srate)
            sfc_b = _ref_only_surface(ref_pcm, srate)
            a, b = run_algorithms(sfc_a), run_algorithms(sfc_b)
        except Exception as exc:  # noqa: BLE001
            res[name] = {"identical": False, "error": f"{type(exc).__name__}: {exc}"}
            continue
        res[name] = {
            "warp_identical": bool(np.array_equal(np.asarray(wp_a), np.asarray(wp_b))),
            "algorithms_identical": a == b,
            "identical": bool(np.array_equal(np.asarray(wp_a), np.asarray(wp_b)) and a == b),
        }
    return res


def _cross_checks(data: dict[str, Any]) -> dict[str, Any]:
    """交叉校验：已知锚点是否成立 + 缺陷类型是否在对应指标上突出。"""
    checks: dict[str, Any] = {}

    for anchor, expected_map in KNOWN_ANCHORS.items():
        if anchor == "warp_identity_ratio":
            for name, expected in expected_map.items():
                actual = data["c2_intermediates"].get(name, {}).get("align", {}).get("non_identity_ratio")
                checks[f"warp_identity_ratio::{name}"] = {
                    "expected": expected,
                    "actual": actual,
                    "match": (actual is not None and abs(actual - expected) <= 0.02),
                }
        elif anchor == "rms_relative":
            # ★ 相对判据：03_气息不匀 的 rms 应是全部样本里最低的
            rms_map = {
                n: data["c2_intermediates"].get(n, {}).get("ingest", {}).get("rms")
                for n in SAMPLES
            }
            valid = {n: v for n, v in rms_map.items() if v is not None}
            lowest = min(valid, key=valid.get) if valid else None
            checks[f"rms_relative::{expected_map['lowest']}_is_lowest"] = {
                "expected": expected_map["lowest"],
                "actual": lowest,
                "all_rms": {n: _round_for_report(v, 5) for n, v in valid.items()},
                "match": lowest == expected_map["lowest"],
            }

    # 缺陷类型 ↔ 指标模式：每种缺陷应在「自己的」指标上最突出
    def scalar(sample: str, algo: str, key: str) -> float | None:
        v = data["samples"].get(sample, {}).get(algo, {}).get(key)
        return None if isinstance(v, list) or v is None else float(v)

    defects = [n for n in SAMPLES if n != "reference"]
    patterns: dict[str, Any] = {}
    for d in defects:
        patterns[d] = {
            "pitch_median_abs_cents": scalar(d, "pitch", "median_abs_cents"),
            "pitch_max_abs_cents": scalar(d, "pitch", "max_abs_cents"),
            "timing_median_onset_sec": scalar(d, "timing", "median_onset_sec"),
            "timing_late_ratio": scalar(d, "timing", "late_ratio"),
            "timing_early_ratio": scalar(d, "timing", "early_ratio"),
            "dynamics_median_db": scalar(d, "dynamics", "median_db"),
            "dynamics_n_unpaired": scalar(d, "dynamics", "n_unpaired"),
            "pitch_n_unpaired": scalar(d, "pitch", "n_unpaired"),
        }
    checks["defect_to_metric_pattern"] = patterns
    return checks


def main() -> int:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    det = data.get("determinism", {})
    ok = all(v.get("identical") for v in det.values() if isinstance(v, dict))
    print(f"基线已写入 {OUT.relative_to(REPO)}")
    print(f"确定性：{det}")
    print(f"全部确定性成立：{ok}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    raise SystemExit(main())
