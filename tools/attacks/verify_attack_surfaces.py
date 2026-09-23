#!/usr/bin/env python3
"""verify_attack_surfaces.py —— 把反方攻击清单从"断言"变成"可复现证据"。

宪章 §28：外部事实必须在 Freeze 前验证，不能只写在文档里。

本脚本用**最小可控实验**证明三条关键失效模式真实存在。
每条的结论都是「若偷懒实现，会得到什么错误结果」。

用法：python3 tools/attacks/verify_attack_surfaces.py
退出码：0 全部证实 / 1 有断言未获证实
无随机性、无副作用（不读音频、不写文件）。
"""

from __future__ import annotations

import math
import sys

import numpy as np


def hz_to_cents(f0: float, ref: float) -> float:
    return 1200.0 * math.log2(f0 / ref)


def hz_to_chroma_bin(f0: float) -> int:
    midi = 69 + 12 * math.log2(f0 / 440.0)
    return int(round(midi)) % 12


def attack_4_timing_warped_axis() -> bool:
    """ATK-4：节奏用 WARPED 轴 → 结果恒为 0 且不报错。"""
    print("─" * 72)
    print("ATK-4 · 节奏用 WARPED 轴")
    print("─" * 72)

    ref = np.array([0.0, 1.0, 2.0])
    prac = ref + 0.2  # 整体拖拍 200 ms

    d_true = (prac - ref) * 1000.0
    print(f"  场景：练习整体晚 200 ms")
    print(f"  正确做法（REFERENCE 轴逐音配对）: 中位 {np.median(d_true):.1f} ms")

    # WARPED：把练习线性拉伸到与参考等跨度、同起点
    p_span = prac[-1] - prac[0]
    r_span = ref[-1] - ref[0]
    prac_w = (prac - prac[0]) / p_span * r_span + ref[0]
    d_w = (prac_w - ref) * 1000.0
    print(f"  偷懒做法（WARPED 轴）          : 中位 {np.median(d_w):.1f} ms")

    ok = bool(np.allclose(d_w, 0.0)) and not np.allclose(d_true, 0.0)
    print(f"  {'✅ 证实' if ok else '❌ 未证实'}：整体拖拍被抹成 0，且无任何警告")
    print("     后果：一份「节奏完美」的报告被静默产出。")
    return ok


def attack_3_chroma_hides_octave() -> bool:
    """ATK-3：用 chroma 做音准 → 八度错误完全不可见。"""
    print()
    print("─" * 72)
    print("ATK-3 · 用 chroma 代替绝对音高")
    print("─" * 72)

    d5, d4 = 587.33, 293.66  # 实测案例：22.05 kHz 下 D5 被判成 D4
    cents = hz_to_cents(d4, d5)
    b5, b4 = hz_to_chroma_bin(d5), hz_to_chroma_bin(d4)
    names = "C C# D D# E F F# G G# A A# B".split()

    print(f"  真实 D5={d5:.2f} Hz，误判 D4={d4:.2f} Hz")
    print(f"  绝对音高比较: {cents:+.0f} 音分   ← 巨大错误，可见")
    print(f"  chroma 比较  : bin {b5}({names[b5]}) vs bin {b4}({names[b4]}) = 0 音分")

    ok = (b5 == b4) and abs(cents) >= 1200.0
    print(f"  {'✅ 证实' if ok else '❌ 未证实'}：低一个八度在 chroma 上完全不可见")
    print("     后果：pitch.py 的 MUST NOT「禁止 chroma 化」不是洁癖，是正确性要求。")
    return ok


def attack_1_silent_alignment_fallback() -> bool:
    """ATK-1：吞掉对齐失败、退化为逐点硬比 → 产出假指标。"""
    print()
    print("─" * 72)
    print("ATK-1 · 对齐失败后退化为逐点硬比")
    print("─" * 72)

    # 练习比参考慢一倍（同一首曲子的正常演奏差异）
    ref_onsets = np.array([0.0, 1.0, 2.0, 3.0])
    prac_onsets = ref_onsets * 2.0

    # 正确做法：先对齐（把练习时间轴映射回参考），再逐音比
    aligned = prac_onsets / 2.0
    d_aligned = (aligned - ref_onsets) * 1000.0

    # 偷懒做法：不对齐，直接逐点硬比
    d_naive = (prac_onsets - ref_onsets) * 1000.0

    print("  场景：练习速度是参考的一半（正常演奏差异，非错误）")
    print(f"  对齐后逐音比: {d_aligned}  ← 全 0，正确")
    print(f"  逐点硬比    : {d_naive}  ← 假偏差")
    print(f"  中位假偏差  : {np.median(d_naive):.0f} ms")

    ok = bool(np.allclose(d_aligned, 0.0)) and np.median(d_naive) > 100.0
    print(f"  {'✅ 证实' if ok else '❌ 未证实'}：不对齐会产出大规模假偏差，")
    print("     而流程本身「成功」结束 —— 报告上看不出任何异常。")
    return ok


def attack_5_frame_hop_confusion() -> bool:
    """ATK-5：帧移用错 → 时间刻度差 8×，不报错。"""
    print()
    print("─" * 72)
    print("ATK-5 · 帧移用错（G5 修正前的静默分叉）")
    print("─" * 72)

    sr = 44100
    pitch_hop = 2048   # MATERIALIZE.pitch_hop_length
    rms_hop = 256      # MATERIALIZE.rms_hop_length

    frame = 100        # 第 100 帧
    t_right = frame * pitch_hop / sr
    t_wrong = frame * rms_hop / sr

    print(f"  场景：把 pitch 端口的第 {frame} 帧换算成秒")
    print(f"  用 pitch_hop_length={pitch_hop}: {t_right:.3f} s   ← 正确")
    print(f"  用 rms_hop_length  ={rms_hop}: {t_wrong:.3f} s   ← 差 {t_right/t_wrong:.0f}×")

    ok = abs(t_right / t_wrong - 8.0) < 1e-6
    print(f"  {'✅ 证实' if ok else '❌ 未证实'}：两种猜法差 8×，且都不会报错")
    print("     → 这就是为什么每个端口必须自己声明 hop_length。")
    return ok


def main() -> int:
    print("=" * 72)
    print("攻击面验证 · 把反方攻击清单变成可复现证据（宪章 §28）")
    print("=" * 72)
    print()

    results = {
        "ATK-1 对齐失败静默降级": attack_1_silent_alignment_fallback(),
        "ATK-3 chroma 隐藏八度": attack_3_chroma_hides_octave(),
        "ATK-4 WARPED 轴抹掉节奏": attack_4_timing_warped_axis(),
        "ATK-5 帧移用错差 8×": attack_5_frame_hop_confusion(),
    }

    print()
    print("=" * 72)
    print("汇总")
    print("=" * 72)
    for k, v in results.items():
        print(f"  {'✅' if v else '❌'} {k}")
    failed = [k for k, v in results.items() if not v]
    print()
    if failed:
        print(f"❌ {len(failed)} 条断言未获证实：{failed}")
        return 1
    print("✅ 全部失效模式已在最小实验中得到证实")
    print("   → 这些不是理论担忧，而是偷懒实现会真实产生的结果")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
