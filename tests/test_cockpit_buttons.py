"""按钮可用性与点击反馈的判据（负责人 2026-09-25 指出「按钮点不动」后新增）。

判据围绕三件事：
1. 按钮的可用态与当前状态一致 —— 从 `COMMAND_LEGALITY` 现算，不写死；
2. 不可用按钮用 `aria-disabled` 而非 HTML `disabled`（后者不可聚焦，
   键盘与读屏用户因此拿不到「为什么不能点」）；
3. 任何一次点击都在页面上留下反馈 —— 400 的原因不能只躺在响应体里。
"""

from __future__ import annotations

import re

import pytest

from harmonica_eval.cockpit import app
from harmonica_eval.contract import COMMAND_LEGALITY, SessionState, UiCommandKind


# ── 一、可用态由当前状态现算，而非写死 ──────────────────────────────


def test_availability_matches_legality_table_for_every_state() -> None:
    """每个状态下，6 个命令的可用性必须与冻结的合法性表逐条相符。"""
    for state in SessionState:
        got = app._command_availability(state)
        assert set(got) == set(app.COMMAND_LABELS), "6 个命令一个都不能少"
        for kind, (ok, _reason) in got.items():
            expected = state in (COMMAND_LEGALITY.get(kind) or frozenset())
            assert ok is expected, (
                f"{kind.value} 在 {state.value} 的可用性应为 {expected}，实得 {ok}"
            )


def test_availability_is_not_hardcoded_across_states() -> None:
    """红端：若实现把可用态写死成「全部可点」，这里必须红。"""
    created = app._command_availability(SessionState.CREATED)
    data_ready = app._command_availability(SessionState.DATA_READY)

    # 同一批命令，两个状态下的可用性必须【不同】——写死做不到这一点
    assert {k for k, (ok, _) in created.items() if ok} != {
        k for k, (ok, _) in data_ready.items() if ok
    }
    # 具体地：CREATED 下 BUILD_SURFACE 不合法，DATA_READY 下 RUN_ALGORITHMS 才合法
    assert created[UiCommandKind.BUILD_SURFACE][0] is False
    assert data_ready[UiCommandKind.RUN_ALGORITHMS][0] is True


# ── 二、不可用必须「可感知且可解释」 ────────────────────────────────


def test_blocked_command_explains_why_and_what_to_do() -> None:
    """不可用的命令要说出两件事：为什么现在不行、现在该先做什么。"""
    availability = app._command_availability(SessionState.DATA_READY)
    ok, reason = availability[UiCommandKind.BUILD_SURFACE]
    assert ok is False
    assert "DATA_READY" in reason, "要说清当前状态"
    assert "重置会话" in reason, "要指出接下来该做什么"


def test_every_blocked_command_carries_a_reason() -> None:
    """不允许出现「置灰但无解释」——那等于把问题推回给用户。"""
    for state in SessionState:
        for kind, (ok, reason) in app._command_availability(state).items():
            if not ok:
                assert reason, f"{kind.value} 在 {state.value} 不可点却没有原因"


# ── 三、渲染形态：aria-disabled 而非 disabled ──────────────────────


def _render(state: SessionState) -> str:
    return app._render_buttons(app._command_availability(state))


def test_blocked_buttons_use_aria_disabled_not_html_disabled() -> None:
    """红端：改用 HTML `disabled` 会让键盘/读屏用户拿不到原因，必须红。"""
    html = _render(SessionState.DATA_READY)
    assert 'aria-disabled="true"' in html
    # 去掉 aria- 之后不应再有裸 disabled 属性
    assert not re.search(r"<button[^>]*\sdisabled(\s|=|>)", html)


def test_blocked_button_is_linked_to_its_reason() -> None:
    """不可用按钮要通过 aria-describedby 指向它的原因。"""
    html = _render(SessionState.DATA_READY)
    for kind, (ok, _) in app._command_availability(SessionState.DATA_READY).items():
        if not ok:
            assert f'aria-describedby="why-{kind.value}"' in html
            assert f'id="why-{kind.value}"' in html


def test_available_buttons_carry_no_blocked_markers() -> None:
    """可点按钮不应带置灰标记或原因段落。"""
    html = _render(SessionState.CREATED)
    ok_kinds = [k for k, (ok, _) in app._command_availability(SessionState.CREATED).items() if ok]
    for kind in ok_kinds:
        m = re.search(rf'<button[^>]*data-kind="{kind.value}"[^>]*>', html)
        assert m, f"{kind.value} 的按钮没渲染出来"
        assert "aria-disabled" not in m.group(0)
        assert f'id="why-{kind.value}"' not in html


# ── 四、反馈区：点任何按钮都留痕 ────────────────────────────────────


def test_page_renders_feedback_region_and_live_region() -> None:
    """反馈区要在页面上，且是 aria-live，读屏也能听到。"""
    from harmonica_eval.host.app import build_default_app

    port = build_default_app()
    page = app._render_page(port)
    assert 'id="cmd-feedback"' in page
    assert 'aria-live="polite"' in page
    assert 'role="status"' in page


def test_page_injects_command_labels_for_feedback_text() -> None:
    """反馈文案要用中文命令名，所以页面要带上映射表。"""
    from harmonica_eval.host.app import build_default_app

    page = app._render_page(build_default_app())
    assert "var COMMAND_LABELS" in page
    for kind in app.COMMAND_LABELS:
        assert kind.value in page


def test_blocked_click_is_handled_in_js_not_silently() -> None:
    """JS 里要点名处理不可用按钮：就地给原因，而不是什么都不做。"""
    from harmonica_eval.host.app import build_default_app

    page = app._render_page(build_default_app())
    assert "aria-disabled" in page, "JS 必须读 aria-disabled 才能分流"
    assert "cmd-feedback" in page


# ── 五、畸形载荷给可读错误，不再 500 ────────────────────────────────


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"path": ""}, {"path": 123}, {"wrong": "x"}],
)
def test_malformed_payload_gives_readable_error_not_assertion(payload) -> None:
    """红端：这五种原先抛 AssertionError → 穿透成 500「internal error」。"""
    with pytest.raises(Exception) as info:
        app.build_command(UiCommandKind.SET_REFERENCE, payload)
    assert "AssertionError" not in type(info.value).__name__
    assert "路径" in str(info.value) or "path" in str(info.value)


def test_valid_payload_still_accepted() -> None:
    """收紧校验不能误伤合法输入。"""
    cmd = app.build_command(UiCommandKind.SET_REFERENCE, {"path": "a.wav"})
    assert cmd.kind is UiCommandKind.SET_REFERENCE
    assert cmd.payload == {"path": "a.wav"}


def test_non_path_commands_need_no_payload() -> None:
    """CANCEL / RESET 等仍不接受载荷——本次改动不得放宽这一点。"""
    for kind in (
        UiCommandKind.BUILD_SURFACE,
        UiCommandKind.RUN_ALGORITHMS,
        UiCommandKind.CANCEL,
        UiCommandKind.RESET,
    ):
        assert app.build_command(kind).payload == {}


# ── 六、公开面未被扩张 ──────────────────────────────────────────────


def test_public_surface_still_fourteen() -> None:
    """FILE-401:80 冻结 `app.__all__` 恰 14 项；新增的私有符号不得进去。"""
    assert len(app.__all__) == 14
    for name in ("_render_buttons", "_command_availability"):
        assert name not in app.__all__
