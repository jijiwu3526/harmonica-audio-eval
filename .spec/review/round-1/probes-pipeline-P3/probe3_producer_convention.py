"""P3 probe 3 — 生产者调用约定 vs 实际生产者签名（端口生成能否落地）。

对照：
  - FILE-104 §4.4 step 3/4：每个端口的生成者由 PortSpec.produced_by 指名，
    "只做一次查表调用"；调用约定唯一：可调用对象接收 4 个位置参数
    (reference, practice, sample_rate, warp_path) -> NDArray。
  - FILE-104 INV-104-1：surface.py 源码中不得出现 pcm.mapped / pitch. / chroma. /
    rms. / notes. 等端口 id 字面量。
  - profile.PORTS：produced_by 是**模块路径字符串**（"core.features" 等），不是可调用名。
只读。
"""
from __future__ import annotations

import importlib
import inspect
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from harmonica_eval import profile  # noqa: E402


def sig_of(func) -> str:
    return f"{func.__name__}{inspect.signature(func)}"


def main() -> int:
    print("=" * 72)
    print("P3 probe 3 · 生产者调用约定 vs 实际生产者签名")
    print("=" * 72)

    print("\n[1] profile 声明的 produced_by 是模块路径，不是可调用名：")
    for spec in profile.PORTS:
        print(f"    {spec.port_id:26s} produced_by={spec.produced_by!r}")

    print("\n[2] 各生产者模块里，能生成端口数据的候选函数签名：")
    expected_conv = "(reference, practice, sample_rate, warp_path) -> NDArray"
    print(f"    FILE-104 §4.4 step 4 冻结的调用约定: {expected_conv}")
    for modname, funcs in (
        ("harmonica_eval.core.features", ["materialize_pitch", "materialize_rms", "materialize_chroma", "materialize_notes"]),
        ("harmonica_eval.core.align", ["align", "compute_alignment_features", "compute_warp_path"]),
        ("harmonica_eval.core.surface", ["generate_all_ports", "build_surface"]),
    ):
        mod = importlib.import_module(modname)
        for fn in funcs:
            obj = getattr(mod, fn, None)
            if obj is None:
                print(f"    !! {modname}.{fn} 不存在")
                continue
            print(f"    {modname.split('.')[-1]:9s}.{sig_of(obj)}")

    print("\n[3] 8 个 produced_by='core.features' 的端口 → 4 个函数，且没有任何映射表")
    feats = [p.port_id for p in profile.PORTS if p.produced_by == "core.features"]
    print(f"    端口数 {len(feats)}: {feats}")
    print("    core/features.py 顶层可调用:", [
        n for n, o in vars(importlib.import_module("harmonica_eval.core.features")).items()
        if not n.startswith("_") and inspect.isfunction(o)
    ])
    print("    profile.PortSpec 字段:", [f for f in profile.PortSpec.__dataclass_fields__])
    print("    -> PortSpec 没有任何字段把 port_id 映射到具体函数；")
    print("       produced_by 只到模块粒度（'core.features' 覆盖 8 个端口）。")

    print("\n[4] 逐端口检查：4 参数调用约定是否可能满足")
    problems = []
    # materialize_notes(pitch, rms, sample_rate) 需要 pitch/rms —— 4 参里没有
    problems.append("materialize_notes(pitch, rms, sample_rate)：需要 pitch/rms 两个**中间特征**，"
                    "而 4 参约定只给 (reference, practice, sample_rate, warp_path)，"
                    "无 pitch/rms → notes.* 无法按该约定生成")
    problems.append("materialize_pitch(samples, sample_rate) / materialize_rms(samples)："
                    "只接受**一路** samples，而 4 参约定同时给 reference 与 practice，"
                    "无法区分该产出 pitch.reference 还是 pitch.practice")
    problems.append("align.align(reference, practice)：只接受 2 参，与 4 参约定不符")
    problems.append("pcm.mapped.* / pcm.warped.practice 的 produced_by='core.surface'："
                    "指向 surface.py 自身，而 FILE-104 §7 明令该文件不实现 PCM 生成/重采样")
    for p in problems:
        print("    -", p)

    print("\n[5] FILE-104 的禁止条款（INV-104-1 / §7）")
    txt = (REPO / ".spec" / "build" / "FILE-104-v1.md").read_text(encoding="utf-8")
    for needle in ("不得**硬编码端口名", "不实现任何特征提取", "不做 `WARPED` 轴的 PCM 重采样", "不做音频解码、重采样、下混"):
        print(f"    含 {needle!r}: {needle.replace('**','') in txt}")

    print("\n[结论]")
    print("    生产者解析到「模块」为止，没有任何 port_id → 可调用对象的映射表；")
    print("    8 个 features 端口共用 4 个签名不同的函数，且 notes.* 需要的中间特征")
    print("    不在冻结调用约定里；pcm.* 的生产者模块被明令禁止生产 PCM。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
