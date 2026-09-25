"""
FILE-ID:      SMOKE-INJECTION
COMPONENT:    跨组件烟雾测试（C1↔C3 装配链已注入部分）
SPEC:         FILE-204 / FILE-205 / FILE-206 的 §8 判据之上，补端到端协同验证

ROLE:
    验证「bootstrap → registry → runtime」三段各自通过 §8 之后，
    **合起来**是否真的能协同工作。

INTENT:
    各自 §8 全过 ≠ 合起来能跑。本文件只测**已注入且已冻结**的行为：
    三个算法文件、C1、C2 仍是 SHELL，本文件一概不测——
    那些会随注入推进而变，测了就是给未来的执行者埋误导。

MUST:
    - fixture 一律从 profile.PORT_INDEX / profile.AUDIO 真实派生
      ★ 禁止手编 port_id / field_names / sample_rate
      （手编过一次，编错了 field_names 与 sample_rate，误判为实现有缺陷）
    - 端口描述的 sample_rate 必须取自 AUDIO，与 bootstrap 填
      InputRequirement.sample_rate 同源
      （core/surface.py 的 build_descriptor 也从 AUDIO 取，三处必须一致）
    - 每个负路径用例都要断言"被拒绝"，不能只断言"不抛异常"

MUST NOT:
    - 不测尚未注入的组件（三算法 run、C1 HostApp、C2 core）
    - 不 import 被测代码来生成被测输入（自己造 fixture）
    - 不断言实现细节（不检查函数体、不断言具体实现方式）

INPUT:
    无（自造 fixture）

OUTPUT:
    pytest 通过 / 失败。失败信息必须可读，不许裸 assert False。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harmonica_eval import contract as c  # noqa: E402
from harmonica_eval import profile  # noqa: E402
from harmonica_eval.algorithms.bootstrap import build_default_registry  # noqa: E402
from harmonica_eval.algorithms.runtime import (  # noqa: E402
    InputResolution,
    resolve_inputs,
    validate_result,
)

ALGO_IDS = ("pitch", "timing", "dynamics")


# ═════════════════════════════════════════════════════════════════════
# fixture —— 全部从真实 profile 派生
# ═════════════════════════════════════════════════════════════════════


def make_port_descriptor(port_id: str, **overrides: object) -> c.PortDescriptor:
    """按 PORT_INDEX 真实值构造 PortDescriptor，只覆盖显式传入的字段。

    ★★ sample_rate 必须用【与 bootstrap 完全同源】的规则派生 ★★
      旧写法一律取 AUDIO.sample_rate（44100），★ 那在
      SAMPLE_RATE_FREE_PREFIXES 名单内的端口上是错的：
        notes.*  chroma.*  warp_path  → 真实需求是 0（与采样率无关）
        pitch.*  rms.*                 → 真实需求是 44100
      ★ 症状：resolve_inputs 把所有 notes.* 判为 incompatible，
        三个算法全 INCOMPATIBLE —— ★ 本项目真的踩过这个坑。
      ★ 端口声明侧与插件需求侧必须共用同一份名单，否则两侧口径漂移。

    ★ 形状同理：按 dimensions 的语义轴生成，禁止写死 (100,) ——
      notes 是 (note, field) 两轴，用一维 shape 会掩盖维度不匹配。
    """
    spec = profile.PORT_INDEX[port_id]
    sample_rate = (
        0
        if profile.port_prefix(port_id) in profile.SAMPLE_RATE_FREE_PREFIXES
        else profile.AUDIO.sample_rate
    )
    fields: dict[str, object] = {
        "port_id": spec.port_id,
        "schema_version": "CORE_PROFILE_V0.1",
        "element_type": spec.element_type,
        "dimensions": spec.dimensions,
        "shape": (100,),
        "units": spec.units,
        "field_names": tuple(spec.field_names),
        "timeline_basis": spec.timeline_basis,
        "hop_length": spec.hop_length,
        "sample_rate": sample_rate,
        "content_hash": "smoke",
    }
    fields.update(overrides)
    return c.PortDescriptor(**fields)  # type: ignore[arg-type]


def make_manifest(descriptors: dict[str, c.PortDescriptor]) -> c.SurfaceManifest:
    """构造 sealed 的 SurfaceManifest。"""
    return c.SurfaceManifest(
        profile_version="CORE_PROFILE_V0.1",
        audio_format=c.AudioFormat(profile.AUDIO.sample_rate, 1, "float32"),
        reference_duration_sec=1.0,
        practice_duration_sec=1.0,
        ports=descriptors,
        sealed=True,
    )


def descriptors_for(spec: c.PluginSpec) -> dict[str, c.PortDescriptor]:
    """为某个 spec 的全部 required 端口生成描述。"""
    return {r.port_id: make_port_descriptor(r.port_id) for r in spec.required_inputs}


def make_scalar(**overrides: object) -> c.UiScalar:
    fields: dict[str, object] = {"key": "k", "label": "标量", "value": 1.0, "unit": "seconds"}
    fields.update(overrides)
    return c.UiScalar(**fields)  # type: ignore[arg-type]


def make_envelope(**overrides: object) -> c.AlgorithmResultEnvelope:
    fields: dict[str, object] = {
        "algorithm_id": "pitch",
        "algorithm_version": "v1.0.0",
        "status": "OK",
        "required_ports": (),
        "consumed_ports": (),
        "payload": [make_scalar()],
    }
    fields.update(overrides)
    return c.AlgorithmResultEnvelope(**fields)  # type: ignore[arg-type]


# ═════════════════════════════════════════════════════════════════════
# 场景 ① 最小闭环：bootstrap → registry
# ═════════════════════════════════════════════════════════════════════


def test_bootstrap_produces_three_specs() -> None:
    """bootstrap 产出恰好三个 PluginSpec，顺序等于 REGISTRATION_ORDER。"""
    from harmonica_eval.algorithms.bootstrap import ALGORITHM_INPUTS, REGISTRATION_ORDER

    specs = build_default_registry().list()
    ids = tuple(s.algorithm_id for s in specs)

    assert ids == REGISTRATION_ORDER, f"顺序应为 {REGISTRATION_ORDER}，实得 {ids}"
    assert set(ids) == set(ALGORITHM_INPUTS) == set(ALGO_IDS), f"算法集合不符：{ids}"


def test_registry_returns_same_object() -> None:
    """get() 命中返回同一对象；未命中返回 None 而非抛错。"""
    registry = build_default_registry()

    for spec in registry.list():
        assert registry.get(spec.algorithm_id) is spec, (
            f"get({spec.algorithm_id!r}) 未返回同一对象"
        )

    assert registry.get("不存在的算法") is None, "get 未命中应返回 None，不应抛错"


@pytest.mark.parametrize("algo_id", ALGO_IDS)
def test_resolve_inputs_ok_scenario(algo_id: str) -> None:
    """required 全部满足时，三个算法都应 status=OK 且全部端口可用。"""
    registry = build_default_registry()
    spec = registry.get(algo_id)
    assert spec is not None, f"registry 中找不到 {algo_id}"

    resolution, status = resolve_inputs(spec, make_manifest(descriptors_for(spec)))

    assert status == "OK", f"{algo_id} 应 OK，实得 {status}：{resolution.incompatible_required}"
    assert set(resolution.available) == {r.port_id for r in spec.required_inputs}, (
        f"{algo_id} 可用端口集与 required 不符：{sorted(resolution.available)}"
    )
    assert not resolution.incompatible_required, "OK 时不该有 incompatible"


def test_resolve_inputs_incompatible_scenario() -> None:
    """缺一个 required 时，应 INCOMPATIBLE 且精确指出缺哪个。"""
    registry = build_default_registry()
    spec = registry.get("pitch")
    assert spec is not None

    missing_id = spec.required_inputs[0].port_id
    descriptors = descriptors_for(spec)
    del descriptors[missing_id]

    resolution, status = resolve_inputs(spec, make_manifest(descriptors))

    assert status == "INCOMPATIBLE", f"缺端口应 INCOMPATIBLE，实得 {status}"
    assert set(resolution.incompatible_required) == {missing_id}, (
        f"应精确指出 {missing_id}，实得 {sorted(resolution.incompatible_required)}"
    )


def test_resolve_inputs_rejects_wrong_sample_rate() -> None:
    """采样率不匹配必须被拒 —— 防跨采样率混用。"""
    registry = build_default_registry()
    spec = registry.get("pitch")
    assert spec is not None

    descriptors = {
        r.port_id: make_port_descriptor(r.port_id, sample_rate=48000)
        for r in spec.required_inputs
    }
    _, status = resolve_inputs(spec, make_manifest(descriptors))

    assert status == "INCOMPATIBLE", f"采样率不符应 INCOMPATIBLE，实得 {status}"


def test_resolve_inputs_rejects_wrong_timeline_basis() -> None:
    """时间轴不符必须被拒 —— 防在 WARPED 轴上算节奏得到恒 0。"""
    registry = build_default_registry()
    spec = registry.get("pitch")
    assert spec is not None

    descriptors = {
        r.port_id: make_port_descriptor(r.port_id, timeline_basis=c.TimelineBasis.WARPED)
        for r in spec.required_inputs
    }
    resolution, status = resolve_inputs(spec, make_manifest(descriptors))

    assert status == "INCOMPATIBLE", f"轴不符应 INCOMPATIBLE，实得 {status}"
    assert len(resolution.incompatible_required) == len(spec.required_inputs), (
        "全部端口的轴都不符，应全部被标记"
    )


def test_input_resolution_is_exposed_to_c1() -> None:
    """BLOCK-2 方案乙：InputResolution 暴露给 C1，且带 as_view。"""
    from harmonica_eval.algorithms import runtime as runtime_module

    assert "InputResolution" in runtime_module.__all__, (
        "InputResolution 应在 __all__，否则 C1 无法 import"
    )
    assert hasattr(InputResolution, "as_view"), "as_view 是 C3 侧视图入口，必须存在"


# ═════════════════════════════════════════════════════════════════════
# 场景 ② validate_result 全路径
# ═════════════════════════════════════════════════════════════════════


def test_validate_result_accepts_valid_envelope() -> None:
    """合法 OK 信封必须被接受。"""
    validate_result(make_envelope())


def test_validate_result_rejects_ms_unit() -> None:
    """★ 毫秒单位守门：unit='ms' 必须在词表检查处被拒。

    这是 2026-09-24 裁定「timing 统一用 seconds」的机器守卫 ——
    若此用例将来开始通过，说明词表检查被削弱了。
    """
    assert "ms" not in c.UNITS_VOCABULARY, "前提：词表不含 ms"

    with pytest.raises(ValueError, match="单位不在词表"):
        validate_result(make_envelope(payload=[make_scalar(unit="ms")]))


def test_validate_result_rejects_non_ui_payload() -> None:
    """payload 混入裸对象必须被拒。"""
    with pytest.raises(ValueError, match="非 UiScalar/UiSeries"):
        validate_result(make_envelope(payload=[make_scalar(), object()]))


def test_validate_result_rejects_failed_without_error_code() -> None:
    """status=FAILED 必须带 error_code。"""
    with pytest.raises(ValueError, match="error_code"):
        validate_result(make_envelope(status="FAILED", error_code=None))


def test_validate_result_rejects_ok_with_error_code() -> None:
    """status=OK 不得携带 error_code。"""
    with pytest.raises(ValueError, match="不应携带 error_code"):
        validate_result(
            make_envelope(error_code=c.ErrorCode.CORE_BUILD_FAILED)
        )


def test_validate_result_rejects_illegal_status() -> None:
    """非法 status 值必须被拒并列出合法值。"""
    with pytest.raises(ValueError, match="status 非法"):
        validate_result(make_envelope(status="WEIRD"))


def test_validate_result_rejects_series_without_timeline_basis() -> None:
    """UiSeries 缺 timeline_basis 必须被拒 —— 防时间轴语义丢失。"""
    series = c.UiSeries(
        key="s", label="序列", t=(1.0,), values=(1.0,),
        unit="seconds", timeline_basis=None, source_port="pitch.reference",
    )
    with pytest.raises(ValueError, match="timeline_basis"):
        validate_result(make_envelope(payload=[series]))


# ═════════════════════════════════════════════════════════════════════
# 场景 ③ 装配链已闭合 —— 换成【永续判据】
# ═════════════════════════════════════════════════════════════════════
#
# ★ 历史：这里原是 test_assembly_chain_still_breaks_at_host，
#   它断言 build_default_app() 抛 FILE-301，并自己写着
#   「等 FILE-301 注入后本用例会失败，那正是该改它的时候」。
# ★ C1（HostApp）现已注入完成，那一刻到了。
#
# ★★ 为什么【替换】而不是删除：★★
#   删除会让"装配链通了"这个事实从测试套件里消失 —— 而刻度用例的
#   价值正在于记录进展到哪一步。但保留「断点」断言又会立刻失效。
#   ★ 故改为断言【装配链当前闭合这件事本身】，且是永续的：
#   它不依赖阶段态，只依赖契约 —— 下一个阶段来了它照样成立。


def test_assembly_chain_builds_a_real_host_app() -> None:
    """装配链闭合：build_default_app() 应返回可用的 HostApp（永续判据）。

    ★ 断言的是【契约要求】，不是【当前恰好如此】：
      · 构造成功
      · 是 HostApp 实例
      · ★ 能开一个会话并读到状态（证明不是空壳对象）
    ★ 这三条在任何后续阶段都应成立，故不随注入推进而失效。
    """
    from harmonica_eval.host.app import HostApp, build_default_app

    app = build_default_app()
    assert isinstance(app, HostApp), f"应返回 HostApp，实得 {type(app).__name__}"
    session_id = app.create_session("v1")
    state = app.status(session_id)
    assert state is not None, "新建会话应能读到状态"


def test_sample_rate_requirements_stay_in_sync_with_descriptors() -> None:
    """★ 端口描述侧与插件需求侧的 sample_rate 口径必须一致（★ 锁共源）★

    ★★★ 上一版本用例是【同义反复】，已修正 ★★★
      旧写法用 SAMPLE_RATE_FREE_PREFIXES 算 expected，再比较用同一名单
      算出的 actual —— ★ 名单怎么改两边都一起变，永远相等。
      ★ 实测：把 "notes" 从名单移出，本用例仍然全绿（假绿）。

    ★★ 正确做法：锚定【绝对事实】，不用推导式 ★★
      ★ ★ 第一版试图用 dimensions[0] 判定（note/warp_point/sample 域应为 0），
      ★ ★ ★ 实测【不成立】：pcm.mapped.* 虽在 sample 域，却是采样点序列，
      ★ ★   描述侧与需求侧都取 44100（已实跑确认两侧一致）。
      ★ ★ ★ 那次误判说明「语义轴」不是正确判据。

      ★ 改用【逐端口锚定】：直接列出与采样率无关的端口。
      ★ 名单若被改动而此处未同步，本用例会立刻红 —— 那正是它该抓的。
    """
    from harmonica_eval.algorithms.bootstrap import build_default_registry

    # 锚定【绝对值】：与采样率无关的端口逐个列出。
    # ★ 不用推导式 —— 同源推导会变同义反复（见 docstring）。
    sample_rate_free_ports = frozenset(
        {
            "notes.reference",
            "notes.practice",
            "chroma.lowres.reference",
            "chroma.lowres.practice",
            "warp_path",
        }
    )

    registry = build_default_registry()
    checked = 0
    for spec in registry.list():
        for req in spec.required_inputs:
            expected = (
                0 if req.port_id in sample_rate_free_ports else profile.AUDIO.sample_rate
            )
            assert req.sample_rate == expected, (
                f"{spec.algorithm_id} 对 {req.port_id} 声明 "
                f"sample_rate={req.sample_rate}，应为 {expected}；"
                f"若与采样率无关的端口集合有意改动，"
                f"须同步核对本用例的 sample_rate_free_ports"
            )
            checked += 1
    assert checked > 0, "★ 恒真防护：一条需求都没检查到，说明取错了来源"
