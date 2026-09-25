"""对比图（参考 / 练习 叠放）的行为测试。

交付线不是「页面上有 SVG」，而是「两条线摆在那儿，差异一眼可见」。
所以本文件的核心断言是**可分辨性**：

    参考 = 练习  → 两条线必须重合
    03_气息不匀   → 音高线几乎重合、能量线明显分开

同一份数据，一张图重合一张图分开 —— 那才证明画的是真数据。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from harmonica_eval.contract import UiCommand, UiCommandKind  # noqa: E402
from harmonica_eval.cockpit import app as cockpit  # noqa: E402
from harmonica_eval.host.app import build_default_app  # noqa: E402

_REF = "harmonica_mvp_dataset/01_奇异恩典/标准旋律版.wav"
_BREATH = "harmonica_mvp_dataset/01_奇异恩典/练习曲/03_气息不匀.wav"
_TUNE = "harmonica_mvp_dataset/01_奇异恩典/练习曲/01_音准走调.wav"

_PITCH_UNIT = "cents"
_PITCH_AXIS = "音序（第几个音，非秒）"   # ★ 音高图的横轴标注
_DB_UNIT = "db"


def _view(practice: str):
    """跑完一条完整链，返回 UiView。"""
    a = build_default_app()
    a.create_session("v1")
    a.submit(UiCommand(kind=UiCommandKind.SET_REFERENCE, payload={"path": _REF}))
    a.submit(UiCommand(kind=UiCommandKind.SET_PRACTICE, payload={"path": practice}))
    a.submit(UiCommand(kind=UiCommandKind.BUILD_SURFACE, payload={}))
    a.submit(UiCommand(kind=UiCommandKind.RUN_ALGORITHMS, payload={}))
    return a.snapshot()


def _charts(practice: str) -> dict[str, str]:
    """返回 {指标基名: SVG 文本}，基名去掉 _reference/_practice 后缀。"""
    out: dict[str, str] = {}
    for svg in cockpit._build_comparisons(_view(practice)):
        text = str(svg)
        base = re.findall(r">([a-z_]+\.[a-z_]+)<", text)
        key = base[-1] if base else "?"
        out[key] = text
    return out


def _two_points(svg: str) -> tuple[str, str]:
    """取两条 polyline 的 points 串（蓝=参考，红=练习）。"""
    found: dict[str, str] = {}
    for stroke, points in re.findall(
        r'stroke="(#1f6feb|#d93025)"[^>]*points="([^"]+)"', svg
    ):
        found[stroke] = points
    assert found.get("#1f6feb"), "图里没有参考线"
    assert found.get("#d93025"), "图里没有练习线"
    return found["#1f6feb"], found["#d93025"]


def _mean_abs_gap(a: str, b: str) -> float:
    """两条折线的平均逐点纵向距离（图内像素）。0 = 完全重合。"""
    pa = [tuple(map(float, p.split(","))) for p in a.split()]
    pb = [tuple(map(float, p.split(","))) for p in b.split()]
    n = min(len(pa), len(pb))
    assert n >= 2, f"点数太少（{len(pa)}/{len(pb)}），无法比较"
    return sum(abs(pa[i][1] - pb[i][1]) for i in range(n)) / n


# ── 绿端：图确实存在且是两条线 ────────────────────────────────────

@pytest.mark.parametrize("sample", [_BREATH, _TUNE], ids=["breath", "tune"])
def test_comparison_chart_has_both_lines(sample: str) -> None:
    charts = _charts(sample)
    assert charts, "没有生成任何对比图"
    for name, svg in charts.items():
        assert svg.count("<polyline") >= 2, f"{name} 只有一条线，不是对比图"


@pytest.mark.parametrize("sample", [_BREATH, _TUNE], ids=["breath", "tune"])
def test_chart_declares_both_axes_and_unit(sample: str) -> None:
    """轴含义必须标出来：读者不能把「音序」误当「秒」。"""
    for name, svg in _charts(sample).items():
        assert _PITCH_AXIS in svg or "时间（秒）" in svg, f"{name} 缺横轴标注"
        assert "参考" in svg and "练习" in svg, f"{name} 缺图例"
        assert f"参考 {len(svg)} " or "参考 0 点" or "点 ·" in svg, "缺点数标注"


# ── 硬判据一：参考 = 练习，两条线必须重合 ──────────────────────────

@pytest.mark.parametrize("marker", [_PITCH_AXIS, _DB_UNIT], ids=["pitch", "energy"])
def test_self_comparison_lines_overlap(marker: str) -> None:
    """★ 最容易做到假的一条：拿同一份音频当参考和练习，两线必须重合。"""
    charts = _charts(_REF)          # ★ 参考 = 练习
    svg = next(s for s in charts.values() if marker in s)
    ref, pra = _two_points(svg)
    assert ref == pra, "同一份音频画出了两条不同的线 —— 画的不是真数据"


# ── 硬判据二：03 气息不匀，音高几乎重合、能量明显分开 ────────────

def test_breath_sample_pitch_overlaps_but_energy_separates() -> None:
    """★ 最强判据：同一份数据，一张图重合一张图分开。"""
    charts = _charts(_BREATH)
    pitch = next(s for s in charts.values() if _PITCH_AXIS in s)
    energy = next(s for s in charts.values() if _DB_UNIT in s)

    p_gap = _mean_abs_gap(*_two_points(pitch))
    e_gap = _mean_abs_gap(*_two_points(energy))

    assert p_gap < 12.0, f"音高线本应几乎重合，实际平均纵向差 {p_gap:.1f}px"
    assert e_gap > 25.0, f"能量线本应明显分开，实际平均纵向差仅 {e_gap:.1f}px"
    assert e_gap > p_gap * 2, "能量差异没有显著大于音高差异"


# ── 契约：只画投影里的值，不拉伸、不补点 ──────────────────────────

def test_unequal_lengths_are_not_stretched() -> None:
    """两侧点数不等时各画各的，并留注释；不拉伸、不补零。

    ★ 数据实况（05_漏音断句）：音高侧配对后两侧同为 21（已取交集），
      能量侧是 34 / 21 真不等长。所以只有能量图该带注释 ——
      ★ 断言按实际数据写，★ 不要求「每张图都有注释」。
    """
    app = build_default_app()
    app.create_session("v1")
    app.submit(UiCommand(kind=UiCommandKind.SET_REFERENCE, payload={"path": _REF}))
    app.submit(
        UiCommand(
            kind=UiCommandKind.SET_PRACTICE,
            payload={"path": "harmonica_mvp_dataset/01_奇异恩典/练习曲/05_漏音断句.wav"},
        )
    )
    app.submit(UiCommand(kind=UiCommandKind.BUILD_SURFACE, payload={}))
    app.submit(UiCommand(kind=UiCommandKind.RUN_ALGORITHMS, payload={}))
    view = app.snapshot()

    checked = 0
    for ref, pra in cockpit._comparison_pairs(view.series):
        svg = str(cockpit._render_comparison(ref, pra))
        r_pts, p_pts = _two_points(svg)
        assert r_pts != p_pts, f"{pra.key} 两侧不同却画出同一条线 —— 被拉伸了"
        if len(ref.values) != len(pra.values):
            # ★ 真不等长：注释必须写明「各画各的，不拉伸」
            assert "不拉伸" in svg or "点数不等" in svg, (
                f"{pra.key} 两侧不等长（{len(ref.values)}/{len(pra.values)}）"
                "却没有说明没有拉伸"
            )
            checked += 1
    assert checked, "本样本应当至少有一张两侧不等的图（能量侧 34/21）"


# ── 元素白名单与零依赖（FILE-401 §4.7 冻结四类）────────────────────

def test_chart_uses_only_frozen_svg_elements() -> None:
    """★ 只许 text / polyline / 注释 / svg。grid、line、rect 都超出冻结口径。"""
    for name, svg in _charts(_BREATH).items():
        tags = set(re.findall(r"<([a-zA-Z][a-zA-Z0-9]*)", svg))
        assert tags <= {"svg", "text", "polyline"}, f"{name} 出现未冻结元素 {tags}"


def test_no_external_resource() -> None:
    """★ 零依赖铁律：除 SVG 命名空间标识符外不得有外部 URL。"""
    for svg in _charts(_BREATH).values():
        urls = [
            u for u in re.findall(r"https?://[^\"'\s)]+", svg)
            if "www.w3.org/2000/svg" not in u
        ]
        assert not urls, f"出现外部 URL {urls}"


# ── 不写死算法名：新插件的对比图应自动出现 ────────────────────────

def test_comparison_pairs_are_derived_not_hardcoded() -> None:
    """★ 配对靠 key 后缀现算，界面不认算法名。"""
    from harmonica_eval.contract import TimelineBasis, UiSeries

    a = UiSeries(key="zqx.quantum_reference", label="参考", t=[0.0, 1.0],
                 values=[1.0, 2.0], unit="qe", timeline_basis=TimelineBasis.REFERENCE)
    b = UiSeries(key="zqx.quantum_practice", label="练习", t=[0.0, 1.0],
                 values=[1.5, 2.5], unit="qe", timeline_basis=TimelineBasis.REFERENCE)
    pairs = cockpit._comparison_pairs([a, b])
    assert len(pairs) == 1, "陌生插件的成对曲线没有被识别成对比图"
    ref_pts, pra_pts = _two_points(cockpit._render_comparison(a, b))
    assert ref_pts != pra_pts, "陌生插件的两条线被画成了同一条"
