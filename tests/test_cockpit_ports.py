"""验收 B：前端 12 个数据端口全部打通。

本文件守三条**互不相同**的判据 —— 不可用其中一条的通过来论证另一条：

* 契约层：``UiView.port_summary`` 恰有 12 条，无重复无多余
* 数据层：12 个端口的 ``read()`` 逐个不抛异常，且 shape/dtype 合契约
* 展示层：12 个 ``port_id`` 全部出现在渲染结果里（★ 这才是「前端通」）

★ 为什么三层要分开测：本项目在注入推进中反复出现的假绿形态，
★ 就是「manifest 里有」被当成了「界面能看见」。

★ 两条实测得到的口径，勿凭印象改：
  · ``build_view`` 单独调用时 scalars/series 为空 —— 必须先 ``run_algorithms``。
    展示层因此必须先跑算法，否则会误判成「前端什么都不画」。
  · 端口渲染函数是私有的 ``cockpit.app._render_ports``；
    公开的 ``render_*`` 系列只画状态/标量/进度/错误，不含端口。
"""

from __future__ import annotations

import sys
import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from harmonica_eval import profile
from harmonica_eval.cockpit import app as cockpit_app
from harmonica_eval.host.app import build_default_app

REFERENCE = "harmonica_mvp_dataset/01_奇异恩典/标准旋律版.wav"
PRACTICE = "harmonica_mvp_dataset/01_奇异恩典/练习曲/01_音准走调.wav"

# ★ fixture 全部从 profile / 真实音频派生，禁止手编
EXPECTED_PORT_IDS = frozenset(p.port_id for p in profile.PORTS)


@pytest.fixture(scope="module")
def built_session():
    """跑完整主链：建会话 → 读音频 → 建数据面 → 跑算法 → 出视图。

    ★ 必须调 ``run_algorithms``，否则 view.scalars 为空，
    ★ 展示层会误判为「前端没画东西」。
    """
    app = build_default_app()
    sid = app.create_session("v1")
    app.set_reference(sid, REFERENCE)
    app.set_practice(sid, PRACTICE)
    app.build_surface(sid)
    app.run_algorithms(sid)
    return app, sid, app.build_view(sid)


# ── 契约层 ────────────────────────────────────────────────────────────

def test_port_summary_has_exactly_twelve(built_session):
    """守「契约层」：port_summary 恰 12 条，无重复、无多余。"""
    _, _, view = built_session
    ids = [d.port_id for d in view.port_summary]
    assert len(ids) == 12, f"期望 12 条，实得 {len(ids)}"
    assert len(set(ids)) == len(ids), "port_summary 里有重复项"
    assert set(ids) == EXPECTED_PORT_IDS, "port_summary 与 profile.PORTS 不一致"


def test_port_summary_covers_non_frame_ports(built_session):
    """守「契约层」：hop<=0 的 6 个非帧端口也在清单里。

    ★ 历史上整轮开发就是在这一半边上栽过（hop 守门误伤 / notes 全挂）。
    """
    _, _, view = built_session
    ids = {d.port_id for d in view.port_summary}
    non_frame = {
        p.port_id for p in profile.PORTS if p.hop_length <= 0
    }
    assert non_frame, "profile 里已无非帧端口，本用例失效，请复核"
    assert non_frame <= ids, f"非帧端口缺失：{non_frame - ids}"


# ── 数据层 ────────────────────────────────────────────────────────────

def test_every_port_read_returns_data(built_session):
    """守「数据层」：12 个端口逐个 read() 不抛异常。"""
    app, sid, _ = built_session
    surface = app.acquire_surface(sid)
    failures = []
    for p in profile.PORTS:
        try:
            surface.read(p.port_id)
        except Exception as exc:  # noqa: BLE001 — 验收要看到全部失败而非首个
            failures.append(f"{p.port_id}: {type(exc).__name__}: {exc}")
    assert not failures, "以下端口 read 失败：\n" + "\n".join(failures)


def test_read_shape_matches_declared_dimensions(built_session):
    """守「数据层」：read 的 shape 长度与 dimensions 轴数一致，dtype 合 element_type。"""
    app, sid, _ = built_session
    surface = app.acquire_surface(sid)
    for p in profile.PORTS:
        view = surface.read(p.port_id)
        assert len(view.data.shape) == len(p.dimensions), (
            f"{p.port_id}: shape 维数 {view.data.shape} 与 "
            f"dimensions {p.dimensions} 的轴数不符"
        )
        assert view.data.dtype == p.element_type, (
            f"{p.port_id}: dtype {view.data.dtype} ≠ element_type {p.element_type}"
        )


def test_chroma_element_count_is_product_not_frame_count(built_session):
    """守「数据层」：chroma 的 element_count 是 prod(shape)，★ 不是帧数。

    ★ 历史上有判据把 21（帧数）当 element_count，那是恒假判据。
    """
    import numpy as np

    app, sid, _ = built_session
    surface = app.acquire_surface(sid)
    for p in profile.PORTS:
        if not p.port_id.startswith("chroma"):
            continue
        view = surface.read(p.port_id)
        assert view.element_count == int(np.prod(view.data.shape)), (
            f"{p.port_id}: element_count={view.element_count} "
            f"≠ prod(shape)={int(np.prod(view.data.shape))}"
        )


def test_warp_path_is_int32_two_axis(built_session):
    """守「数据层」：warp_path 是 int32 的 (warp_point, axis) 二列。"""
    import numpy as np

    app, sid, _ = built_session
    surface = app.acquire_surface(sid)
    view = surface.read("warp_path")
    assert view.data.dtype == np.int32, f"warp_path dtype={view.data.dtype}"
    assert view.data.ndim == 2 and view.data.shape[1] == 2, (
        f"warp_path shape={view.data.shape}，期望 (warp_point, 2)"
    )


# ── 展示层（★ 核心）──────────────────────────────────────────────────

def test_every_port_visible_in_rendered_output(built_session):
    """★★★ 守「展示层」：12 个 port_id 全部出现在渲染结果里。★ ★★

    ★ 这是「前端通」的唯一判据 —— 契约里有、数据能读，都不等于界面能看见。
    ★ 端口渲染走私有的 ``_render_ports``；公开的 ``render_*`` 不含端口。
    """
    _, _, view = built_session
    html = cockpit_app._render_ports(view)
    missing = [pid for pid in EXPECTED_PORT_IDS if pid not in html]
    assert not missing, f"渲染结果里看不到这些端口：{missing}"


def test_rendered_output_shows_shape_and_timeline_basis(built_session):
    """守「展示层」：不只画名字，shape 与 timeline_basis 也要能看到。"""
    _, _, view = built_session
    html = cockpit_app._render_ports(view)
    assert "shape" in html.lower(), "渲染结果里没有 shape 信息"
    assert "REFERENCE" in html or "WARPED" in html, "渲染结果里没有 timeline_basis"


def test_all_render_sections_produce_output(built_session):
    """守「展示层」：主链跑完后各渲染段都应有内容（★ 空串=假绿）。"""
    _, _, view = built_session
    assert cockpit_app.render_status(view), "render_status 返回空"
    assert cockpit_app.render_scalars(view.scalars), "render_scalars 返回空"
    assert cockpit_app.render_progress(view), "render_progress 返回空"
    assert view.port_summary, "port_summary 为空"


# ── 四态判据（★ 防假绿）──────────────────────────────────────────────

def test_four_state_discrimination(built_session):
    """守「四态」：三者互斥，主链通时应判「C 有数据」。

    ★ 若将来指标为空且带诊断，判据会自动要求前端显示诊断而非「无数据」。
    """
    _, _, view = built_session
    has_data = bool(view.scalars or view.series)
    has_error = view.error_code is not None
    if has_data:
        assert not has_error, "既有数据又有 error_code —— 状态自相矛盾"
        state = "C 有数据"
    elif has_error:
        state = "D 有诊断的失败"
    else:
        state = "B 已通无源"
    assert state == "C 有数据", f"主链已通却判为「{state}」"
