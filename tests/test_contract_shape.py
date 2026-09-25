"""冻结契约的形状测试：只读取声明数据，不调用任何 SHELL 实现。"""

from __future__ import annotations

import re
from collections.abc import Mapping

from harmonica_eval import contract, profile


EXPECTED_PORT_IDS = frozenset(
    {
        "warp_path",
        "pcm.mapped.reference",
        "pcm.mapped.practice",
        "pcm.warped.practice",
        "pitch.reference",
        "pitch.practice",
        "rms.reference",
        "rms.practice",
        "chroma.lowres.reference",
        "chroma.lowres.practice",
        "notes.reference",
        "notes.practice",
    }
)

EXPECTED_FIELD_LAYOUTS = {
    "warp_path": ("reference_frame", "practice_frame"),
    "pitch": ("f0_hz", "voiced", "confidence"),
    "notes": ("onset_sec", "f0_hz", "rms"),
    "chroma": ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"),
}

EXPECTED_UNITS = frozenset(
    {
        "amplitude",
        "chroma",
        "hz",
        "index",
        "rms",
        "cents",
        "seconds",
        "db",
        "ratio",
        "count",
    }
)

EXPECTED_SESSION_STATES = frozenset(
    {
        "CREATED",
        "INPUT_READY",
        "BUILDING",
        "DATA_READY",
        "FAILED",
        "CLOSED",
    }
)

INTERNAL_STAGE_NAMES = frozenset(
    {"INGESTING", "ALIGNING", "BUILDING_PORTS"}
)

STATE_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*\b")
STABLE_STATES = frozenset(contract.SessionState) - {contract.SessionState.BUILDING}


def test_port_inventory_is_exactly_twelve_frozen_ids() -> None:
    """锁定十二个端口的封闭清单，防止偷偷增加或替换端口。"""
    actual_ids = {port.port_id for port in profile.PORTS}

    assert len(profile.PORTS) == 12
    assert actual_ids == EXPECTED_PORT_IDS


def test_field_layouts_and_profile_fields_are_frozen_and_consistent() -> None:
    """锁定字段布局，并确保每个多维端口按同一契约顺序声明字段。"""
    assert dict(contract.FIELD_LAYOUTS) == EXPECTED_FIELD_LAYOUTS

    for port in profile.PORTS:
        if len(port.dimensions) <= 1:
            assert tuple(port.field_names) == (), port.port_id
            continue

        category = port.port_id.split(".")[0]
        assert tuple(port.field_names) == tuple(contract.FIELD_LAYOUTS[category]), (
            port.port_id
        )


def test_units_vocabulary_is_exact_ten_and_excludes_ms() -> None:
    """锁定十个受控单位，并持续拒绝未获裁定的毫秒单位。"""
    assert len(contract.UNITS_VOCABULARY) == 10
    assert set(contract.UNITS_VOCABULARY) == EXPECTED_UNITS
    assert "ms" not in contract.UNITS_VOCABULARY


def test_session_state_is_exactly_six_external_values() -> None:
    """锁定六个外部状态，禁止 C2 内部阶段泄漏到公开枚举。"""
    actual_states = {state.value for state in contract.SessionState}

    assert len(contract.SessionState) == 6
    assert actual_states == EXPECTED_SESSION_STATES
    assert actual_states.isdisjoint(INTERNAL_STAGE_NAMES)


def test_command_effects_have_only_legal_targets_and_stable_cancel_reset() -> None:
    """锁定命令目的态的合法性，并保护 CANCEL、RESET 的稳定态语义。"""
    assert isinstance(contract.COMMAND_EFFECTS, Mapping)
    assert set(contract.COMMAND_EFFECTS) == set(contract.UiCommandKind)
    assert set(contract.COMMAND_LEGALITY) == set(contract.UiCommandKind)

    legal_states = {state.value for state in contract.SessionState}
    for sources in contract.COMMAND_LEGALITY.values():
        assert all(isinstance(state, contract.SessionState) for state in sources)

    expected_targets = {
        contract.UiCommandKind.SET_REFERENCE: frozenset({"INPUT_READY"}),
        contract.UiCommandKind.SET_PRACTICE: frozenset({"INPUT_READY"}),
        contract.UiCommandKind.BUILD_SURFACE: frozenset(
            {"BUILDING", "DATA_READY"}
        ),
        contract.UiCommandKind.RUN_ALGORITHMS: frozenset({"DATA_READY"}),
        contract.UiCommandKind.RESET: frozenset({"CREATED"}),
    }
    for command, expected in expected_targets.items():
        effect = contract.COMMAND_EFFECTS[command]
        assert isinstance(effect, str) and effect.strip()
        assert set(STATE_TOKEN.findall(effect)) == expected, command

    cancel_effect = contract.COMMAND_EFFECTS[contract.UiCommandKind.CANCEL]
    cancel_targets = set(STATE_TOKEN.findall(cancel_effect))
    assert "稳定态" in cancel_effect
    assert cancel_targets <= legal_states
    assert cancel_targets <= {state.value for state in STABLE_STATES}
    assert "FAILED" not in cancel_targets

    reset_targets = set(
        STATE_TOKEN.findall(contract.COMMAND_EFFECTS[contract.UiCommandKind.RESET])
    )
    assert reset_targets <= legal_states
    assert reset_targets <= {state.value for state in STABLE_STATES}
