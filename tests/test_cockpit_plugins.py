"""丙方案的回归护栏：界面按**指标 key 前缀**分组，★ 分组现算而非写死。

裁定背景（负责人原话）
--------------------
「我们架构的优越性质是要在那个界面上显示出来的。」

本文件锁住那件「显示」必须是**真的**：

    往 Registry 注册一个内核从未听说过的插件 →
    它的指标分组【自己】出现在界面上，★ 界面代码一行没改。

若有人把分组写死成 ``["pitch", "timing", "dynamics"]``，本文件会红。

为什么不给 `UiView` 加 `plugin_summary` 字段
----------------------------------------
`.spec/build/FILE-003-v1.md:252-255` 明文冻结：本次扩面是**唯一一次**以
「补通道缺失」为由对 `UiView` 的扩面，后续任何字段增删**须重新裁定**，
「上次也是加字段」不是理由。所以本方案只消费既有的 `UiView.scalars`。

不测什么
--------
★ 不测「register 不报错」—— 那不构成插拔。
★ 不测「页面列出了三个插件名」—— 那可以是写死的字符串。
本文件只测一件事：**插件列表跟着 Registry 变。**
"""

from __future__ import annotations

import pytest

from harmonica_eval.algorithms.registry import Registry
from harmonica_eval.algorithms.bootstrap import build_default_registry
from harmonica_eval.cockpit import app as cockpit
from harmonica_eval.core.api import HostCore
from harmonica_eval.host.app import HostApp

REF = "harmonica_mvp_dataset/01_奇异恩典/标准旋律版.wav"
PRAC = "harmonica_mvp_dataset/01_奇异恩典/练习曲/01_音准走调.wav"

# 一个刻意难看的名字：若实现里存在任何「已知算法名」白名单，它会立刻露馅。
ALIEN_ID = "zqx_mystery_probe"


def _entry(algorithm_id: str):
    """造一个最简单的合法 entry：不消费任何端口，产出 42.0。

    ★ 形态照抄 `tests/test_plugin_plugability.py`，★ 不自创。
    """
    from harmonica_eval.contract import AlgorithmResultEnvelope, UiScalar

    def _run(_surface):
        return AlgorithmResultEnvelope(
            algorithm_id=algorithm_id,
            algorithm_version="1.0.0",
            status="OK",
            required_ports=(),
            consumed_ports=(),
            payload=(UiScalar(f"{algorithm_id}.value", "探针值", 42.0, "count"),),
            error_code=None,
            error_detail=None,
        )

    return _run


def _alien_spec():
    from harmonica_eval.contract import PluginSpec

    return PluginSpec(
        algorithm_id=ALIEN_ID,
        algorithm_version="1.0.0",
        label="陌生探针",
        required_inputs=(),
        optional_inputs=(),
        entry=_entry(ALIEN_ID),
    )


def _run_pipeline(registry: Registry):
    """真实走整条链：建会话 → 灌音频 → 建面 → 跑算法 → 投影视图 → 渲染。"""
    app = HostApp(core=HostCore(), registry=registry)
    sid = app.create_session("v1")
    app.set_reference(sid, REF)
    app.set_practice(sid, PRAC)
    app.build_surface(sid)
    app.run_algorithms(sid)
    view = app.build_view(sid)
    return view, cockpit._render_scalars_by_plugin(view.scalars)


@pytest.fixture(scope="module")
def baseline_view():
    """未注册陌生插件时的基线。"""
    return _run_pipeline(build_default_registry())


# ── 基线：三个内置插件各自成一组 ────────────────────────────────


def test_baseline_groups_come_from_key_prefix(baseline_view):
    """★ 分组标题来自 key 前缀，★ 而不是某处枚举的算法名。"""
    _, rendered = baseline_view
    heads = [ln[3:].strip() for ln in rendered.splitlines() if ln.startswith("── ")]
    assert heads, "应至少有一组"
    # 前缀即 algorithm_id —— 逐条从 scalars 现算核对
    expected = []
    for item in baseline_view[0].scalars:
        head = item.key.split(".", 1)[0]
        if head not in expected:
            expected.append(head)
    assert [h.split("（")[0] for h in heads] == expected


def test_builtin_groups_present(baseline_view):
    _, rendered = baseline_view
    for name in ("pitch", "timing", "dynamics"):
        assert f"── {name}" in rendered, f"基线应有 {name} 组"


def test_group_item_count_matches_group_size(baseline_view):
    """★ 组标题里的「N 项」是数出来的，★ 不是写死的。"""
    _, rendered = baseline_view
    counts = {}
    for item in baseline_view[0].scalars:
        counts[item.key.split(".", 1)[0]] = counts.get(item.key.split(".", 1)[0], 0) + 1
    for head, n in counts.items():
        assert f"── {head}（{n} 项）" in rendered


# ── 核心：注入陌生插件，它那一组自己出现 ─────────────────────────


def test_alien_plugin_group_appears_without_ui_change():
    """★★★ 本文件的核心断言。

    往 Registry 注册一个内核从未听说过的插件 → 它那一组自己出现在渲染结果里，
    ★ 界面代码一行未改。
    """
    registry = build_default_registry()
    assert ALIEN_ID not in [s.algorithm_id for s in registry.list()]

    registry.register(_alien_spec())
    view, rendered = _run_pipeline(registry)

    # 该插件的指标确实进来了（若它报 INCOMPATIBLE，则不应有 scalar）
    keys = [s.key for s in view.scalars]
    alien_keys = [k for k in keys if k.startswith(ALIEN_ID + ".")]
    if alien_keys:
        assert f"── {ALIEN_ID}" in rendered, "陌生插件的分组必须自己出现"
    else:
        # 该探针未产出指标 → 仍不得凭空出现一个空组
        assert f"── {ALIEN_ID}" not in rendered


def test_group_count_follows_registry_not_a_literal():
    """★ 分组数随 Registry 变，★ 而不是固定三段。"""
    registry = build_default_registry()
    before_view, before = _run_pipeline(registry)
    before_heads = {ln[3:].strip().split("（")[0] for ln in before.splitlines() if ln.startswith("── ")}

    registry.register(_alien_spec())
    _, after = _run_pipeline(registry)
    after_heads = {ln[3:].strip().split("（")[0] for ln in after.splitlines() if ln.startswith("── ")}

    # 无论探针是否产出指标，★ 分组集合都【不得】因写死而恒为三个内置名
    assert after_heads != {"pitch", "timing", "dynamics"} or not ALIEN_ID.startswith("zqx")


# ── 红端护栏：写死分组标题会被本文件抓到 ─────────────────────────


def test_hardcoded_group_names_would_be_detectable(monkeypatch):
    """把分组渲染换成写死三个名字 → 本断言应能分辨。

    ★ 这里不断言「实现是写死的」，★ 而是断言【写死的结果与现算的结果不同】——
    这样将来谁把实现改成写死，★ 上面的前缀核对会立刻红。
    """
    from harmonica_eval.contract import UiScalar

    scalars = [
        UiScalar(key="pitch.a", label="A", value=1.0, unit=""),
        UiScalar(key="brand_new_plugin.b", label="B", value=2.0, unit=""),
    ]
    rendered = cockpit._render_scalars_by_plugin(scalars)
    assert "── pitch" in rendered
    assert "── brand_new_plugin" in rendered
    # 写死实现只会产出 pitch / timing / dynamics 三组
    assert "── timing" not in rendered
    assert "── dynamics" not in rendered


def test_key_without_dot_is_not_dropped():
    """无点号的 key 归入「（无前缀）」，★ 不静默丢弃。"""
    from harmonica_eval.contract import UiScalar

    scalars = [
        UiScalar(key="lonely", label="独苗", value=1.0, unit=""),
    ]
    rendered = cockpit._render_scalars_by_plugin(scalars)
    assert "（无前缀）" in rendered
    assert "独苗" in rendered
