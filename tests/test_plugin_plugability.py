"""插件可插拔性验收测试。

依据：`.spec/GATE-CHALLENGES-C3.md` GC-204-08 已关闭裁定（方案甲·独立装配根）。

裁定原文（决定本测试如何定义「插拔」）：

    负责人裁定 BLOCK-1 = 方案甲（独立装配根）。
    「知道所有实现」这一职责从 C1 移到一个专属位置：
    bootstrap 独占具体算法的 import，Host 只接收已构造好的 Registry。
    这样要求甲对 Host 继续成立（它确实不 import 具体算法），
    而「谁负责装配」变成一个可审查的、单点的物理事实。

★ 因此本项目「插拔」的定义是：
  甲（动态扩展）—— 能接入一个 bootstrap 不知道的插件，
                  且【不修改 bootstrap.py 一行源码】。
  未含「热拔卸」—— Registry 无 unregister，且裁定从未要求。

★ 「不修改 bootstrap 源码」这一条是本测试的硬判据：
  若实现退化为「往 REGISTRATION_ORDER 里加一行」，本测试必须失败。

本测试【不】测「register 不报错」—— 那不构成插拔。
它测的是：新插件的指标真的进入 build_view，且原插件指标逐字节不变。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harmonica_eval import profile
from harmonica_eval.algorithms import bootstrap
from harmonica_eval.algorithms.registry import Registry
from harmonica_eval.contract import (
    AlgorithmResultEnvelope,
    ContractViolation,
    InputRequirement,
    PluginSpec,
    UiScalar,
)
from harmonica_eval.core.api import HostCore
from harmonica_eval.host.app import HostApp

# ★ 参考音频取自仓库自带数据集；不存在则整组跳过（不静默通过）
REF = "harmonica_mvp_dataset/01_奇异恩典/标准旋律版.wav"
PRAC = "harmonica_mvp_dataset/01_奇异恩典/练习曲/03_气息不匀.wav"

pytestmark = pytest.mark.skipif(
    not (Path(REF).exists() and Path(PRAC).exists()),
    reason="参考音频不存在，本组验收无法执行",
)


def _entry(algorithm_id: str):
    """造一个最简单的合法 entry：不消费任何端口，产出 42.0。"""

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


def _spec(algorithm_id: str, required_inputs=()) -> PluginSpec:
    return PluginSpec(
        algorithm_id=algorithm_id,
        algorithm_version="1.0.0",
        label="验收探针",
        required_inputs=tuple(required_inputs),
        optional_inputs=(),
        entry=_entry(algorithm_id),
    )


def _run_all(registry: Registry):
    """真实跑一遍：建会话 → 灌音频 → 建面 → 跑算法 → 投影视图。"""
    app = HostApp(core=HostCore(), registry=registry)
    sid = app.create_session("v1")
    app.set_reference(sid, REF)
    app.set_practice(sid, PRAC)
    app.build_surface(sid)
    envelopes = app.run_algorithms(sid)
    view = app.build_view(sid)
    return (
        {s.key: s.value for s in view.scalars},
        {e.algorithm_id: e.status for e in envelopes},
    )


# ── A1 插：能接入 bootstrap 不知道的插件 ────────────────────────


def test_bootstrap_is_unaware_of_probe_plugin():
    """★ 前提断言：bootstrap 源码里【没有】probe。

    ★ 若实现退化为「往 REGISTRATION_ORDER 加一行」，本断言会失败 ——
    ★ 那就不是插拔，是改代码。"""
    assert "probe" not in bootstrap.REGISTRATION_ORDER
    assert "probe" not in bootstrap.ALGORITHM_INPUTS


def test_register_new_plugin_without_touching_bootstrap():
    """★ A1 绿端：注册后 bootstrap 产出的流程里出现它。"""
    registry = bootstrap.build_default_registry()
    before = {s.algorithm_id for s in registry.list()}
    assert "probe" not in before

    registry.register(_spec("probe"))
    after = {s.algorithm_id for s in registry.list()}
    assert "probe" in after
    assert before <= after, "★ 插入不得挤掉原有插件"


def test_new_plugin_actually_runs_and_emits_metric():
    """★ A1 核心：新插件的指标真的进入 build_view。

    ★ 这才是「插拔」，不是「register 不报错」。"""
    registry = bootstrap.build_default_registry()
    registry.register(_spec("probe"))

    scalars, statuses = _run_all(registry)

    assert statuses.get("probe") == "OK", f"★ 探针未成功运行：{statuses}"
    assert "probe.probe.value" in scalars, f"★ 探针指标未进入视图：{sorted(scalars)}"
    assert scalars["probe.probe.value"] == 42.0


# ── A3 隔离性 ──────────────────────────────────────────────────


def test_inserting_plugin_does_not_disturb_existing_ones():
    """★ A3：插入后原插件的指标【逐字节不变】。

    ★ 「方向一致」不算通过，要数值完全相同。"""
    base, _ = _run_all(bootstrap.build_default_registry())
    assert base, "★ 基线为空，后续比对无意义"

    registry = bootstrap.build_default_registry()
    registry.register(_spec("probe"))
    after, _ = _run_all(registry)

    changed = {k: (base[k], after[k]) for k in base if base[k] != after.get(k)}
    assert not changed, f"★ 插入污染了原有指标：{changed}"


def test_run_is_deterministic_across_two_identical_runs():
    """★ 确定性：同配置两次跑，指标完全相同。

    ★ 防「顺序或随机性影响结果」。"""
    first, _ = _run_all(bootstrap.build_default_registry())
    second, _ = _run_all(bootstrap.build_default_registry())
    assert first == second, "★ 同配置两次运行结果不同"


# ── 红端：插拔必须【能坏】才可信 ───────────────────────────────


def test_duplicate_registration_is_rejected():
    """★ 红端①：重复 algorithm_id 必须显式报错。

    ★ 否则后注册的会静默顶掉先注册的 —— 那是静默降级。"""
    registry = bootstrap.build_default_registry()
    registry.register(_spec("probe"))
    with pytest.raises(Exception) as exc:
        registry.register(_spec("probe"))
    assert "probe" in str(exc.value).lower() or isinstance(exc.value, Exception)


def test_plugin_with_unmet_port_requirement_is_incompatible_not_crash():
    """★ 红端②：端口需求不满足 → 该插件 INCOMPATIBLE，系统不崩。

    ★ 要求它被【标记】而不是【让整个流程失败】或【静默消失】。"""
    port = profile.PORT_INDEX["pitch.reference"]
    bad_req = InputRequirement(
        port_id="pitch.reference",
        timeline_basis=port.timeline_basis,
        element_type=port.element_type,
        required_fields=("绝对不存在的字段",),
        sample_rate=99999,  # 与 profile 的 44100 不符
    )
    registry = bootstrap.build_default_registry()
    registry.register(_spec("badplug", (bad_req,)))

    scalars, statuses = _run_all(registry)

    assert statuses.get("badplug") == "INCOMPATIBLE", f"★ 应标 INCOMPATIBLE：{statuses}"
    assert "badplug.badplug.value" not in scalars, "★ 不兼容的插件不得产出指标"
    # ★ 系统仍能跑出其它插件的结果
    assert any(k.startswith("pitch.") for k in scalars), "★ 系统被拖垮了"


def test_empty_registry_is_rejected_gracefully():
    """★ 红端③：拔光全部插件 → 显式拒绝，不崩溃。

    ★ Registry 没有 unregister，「拔」的等价形态是「不注册」。
    ★ 全部不注册时，系统应显式报错而非段错误或静默返回空。"""
    with pytest.raises(ContractViolation) as exc:
        _run_all(Registry())
    assert "注册表" in str(exc.value), f"★ 报错信息应可读：{exc.value}"


# ── 未覆盖的，明确记录而非假装通过 ──────────────────────────────


def test_unregister_does_not_exist_by_design():
    """★ 记录一个【已知缺口】而不是假装它存在。

    ★ GC-204-08 裁定从未要求热拔卸；本测试把这个事实钉住，
    ★ 若将来有人加了 unregister，本测试会失败并提醒更新本文件。"""
    public = {n for n in dir(Registry) if not n.startswith("_")}
    assert "unregister" not in public, (
        "★ Registry 出现了 unregister —— 请更新 docs/验收计划.md 的 A2 定义"
    )
    assert public == {"register", "list", "get"}, f"★ Registry 公开面变了：{public}"


# ★★★ 缺陷 2（盲审 A 审出）：★ 「顺序恒为快照顺序」【此前无判据】 ★★★
def test_only_order_does_not_change_execution_order() -> None:
    """`only` 的书写次序不得改变执行次序。

    ★ docstring 承诺「顺序恒为会话快照顺序，★ 不因 only 的次序而改变」，
    ★ ★ 而那条承诺此前【没有任何判据守着】——★ 实现正确 + 判据缺失
    ★ ★ 是本项目最常见的形态：★ 改坏了也不会红。
    ★ ★ ★ 判据必须针对【结果顺序】，★ 而不是「代码里有没有那句注释」。
    """
    from harmonica_eval.host.app import build_default_app

    def _run(only):
        app = build_default_app()
        sid = app.create_session("v1")
        app.set_reference(sid, REF)
        app.set_practice(sid, PRAC)
        app.build_surface(sid)
        envelopes = app.run_algorithms(sid, only=only)
        return [env.algorithm_id for env in envelopes]

    forward = _run(["pitch", "timing"])
    reverse = _run(["timing", "pitch"])
    full = _run(None)

    # ★★★ 关键：★ 必须与【完整快照】逐字相等，★ 而不只是 forward == reverse ★★★
    # ★★★ 而「forward == reverse」是【不够】的：★★★ ★★★
    # ★★★ 若实现改成「按 only 首元素排」，★ 正序反序【都会】变成
    # ★★★ 同一个次序，★ 那个断言照样通过 ——★ 判据恒真。★★★ ★★★
    # ★★★ 所以锚点是 full：★ 它是唯一与 only 次序无关的量。★★★ ★★★
    assert full == ["pitch", "timing", "dynamics"], (
        f"会话快照顺序变了：{full}"
    )
    # ★ 筛选后不可能等于 full（少跑了 dynamics），★ 所以比的是【子序列】
    def _subseq(small, big):
        it = iter(big)
        return all(item in it for item in small)

    assert _subseq(forward, full), (
        f"筛选后次序不是快照顺序的子序列：{forward} vs {full}"
    )
    assert forward == reverse, (
        f"only 次序改变了执行次序：{forward} vs {reverse}"
    )
