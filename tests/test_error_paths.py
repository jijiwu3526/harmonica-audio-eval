"""错误路径与边界验收 —— 补上「异常分支零覆盖」这个缺口。

★ 本文件只锁定【已存在的错误契约】，不新增需求、不改实现。
★ `harmonica_eval/` 零改动是铁律：若测试暴露实现缺陷，写 xfail 并报告，
★ 绝不改实现让测试变绿。

---

## 为什么补这个

`core/ingest.py` 有 11 处 raise、覆盖 4 个 `ErrorCode` 与 2 类编程错误，
而在此之前 `tests/` 只引用过 `INCOMPATIBLE` 一个码 —— **错误分支零覆盖**。

★ 本项目反复栽在同两件事上：
  · 假绿：曾出现 `rc=0` 但 `scalars=[]`
  · 静默丢弃：三个算法全 `INCOMPATIBLE` 却被 `status not in (OK, DEGRADED)`
    过滤掉，用户只看到空结果
★ ★ 而这些路径现在没有一条被测试守着 —— 改错错误码不会有任何门禁变红。

---

## 判据口径

★ **错误码 + 可读原因** 双断言。
★ 只断言「抛了异常」不够：`崩栈也是抛异常`，那不构成可用的错误路径。
★ 所以每条 `CoreBuildError` 都同时断言 `.code` 与消息里的人类可读片段。
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import numpy as np
import pytest
import soundfile

from harmonica_eval.contract import CoreBuildError, ErrorCode
from harmonica_eval.core import ingest
from harmonica_eval.profile import AUDIO

REPO = pathlib.Path(__file__).resolve().parent.parent
DATASET = REPO / "harmonica_mvp_dataset"
REFERENCE = DATASET / "01_奇异恩典" / "标准旋律版.wav"
PRACTICE = DATASET / "01_奇异恩典" / "练习曲" / "01_音准走调.wav"


def _write_tone(path: pathlib.Path, duration: float, *, sr: int = 44100,
                amplitude: float = 0.3) -> pathlib.Path:
    """造一段单音正弦（够响以通过非静音门限）。"""
    n = int(round(sr * duration))
    t = np.arange(n, dtype=np.float64) / sr
    sf = (amplitude * np.sin(2.0 * np.pi * 440.0 * t)).astype(np.float32)
    soundfile.write(str(path), sf, sr)
    return path


# ── ① decode_to_mono 的 4 处 raise ───────────────────────────────────────

def test_uri_must_be_nonempty_string(tmp_path: pathlib.Path) -> None:
    """:82 —— uri 非字符串或空串 → INPUT_UNREADABLE。"""
    for bad in (None, 123, "", b"/tmp/x"):
        with pytest.raises(CoreBuildError) as ei:
            ingest.decode_to_mono(bad)  # type: ignore[arg-type]
        assert ei.value.code is ErrorCode.INPUT_UNREADABLE
        assert "uri" in str(ei.value)


def test_missing_path_is_unreadable(tmp_path: pathlib.Path) -> None:
    """:86 —— 路径不存在 → INPUT_UNREADABLE（同码，不同因）。"""
    ghost = tmp_path / "no_such_file.wav"
    with pytest.raises(CoreBuildError) as ei:
        ingest.decode_to_mono(str(ghost))
    assert ei.value.code is ErrorCode.INPUT_UNREADABLE
    assert "路径不存在" in str(ei.value)


def test_directory_is_not_a_regular_file(tmp_path: pathlib.Path) -> None:
    """:86 —— 路径存在但是目录 → 同码不同因。★ 与「不存在」是两个场景。"""
    with pytest.raises(CoreBuildError) as ei:
        ingest.decode_to_mono(str(tmp_path))
    assert ei.value.code is ErrorCode.INPUT_UNREADABLE
    assert "不是普通文件" in str(ei.value)


def test_undecodable_file_is_unreadable(tmp_path: pathlib.Path) -> None:
    """:96 —— 文件存在但解不开（扩展名对、内容不是音频）→ INPUT_UNREADABLE。"""
    junk = tmp_path / "fake.wav"
    junk.write_bytes(b"this is definitely not a RIFF/WAVE payload")
    with pytest.raises(CoreBuildError) as ei:
        ingest.decode_to_mono(str(junk))
    assert ei.value.code is ErrorCode.INPUT_UNREADABLE
    assert "解码失败" in str(ei.value)


def test_nonpositive_native_sample_rate_is_unreadable(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """:101 —— 源采样率 ≤ 0 → INPUT_UNREADABLE。★ 需伪造 soundfile 返回值。

    ★ `SoundFile` 是【被调用的类】（`with soundfile.SoundFile(uri) as sf`），
    ★ 所以替身必须接受 uri 参数 —— ★ 第一版写成无参 `__init__`，
    ★ 实测报 `_Fake() takes no arguments`，★ 那是探针错不是实现错。
    """
    real_soundfile = ingest.soundfile.SoundFile

    class _Fake:
        samplerate = 0

        def __init__(self, uri, *args, **kwargs):  # noqa: D107
            self.uri = uri

        def __enter__(self):  # noqa: D105
            return self

        def __exit__(self, *exc):  # noqa: D105
            return False

        def read(self, frames: int, dtype: str, always_2d: bool):
            return np.zeros((10, 1), dtype=np.float32)

    existing = _write_tone(tmp_path / "ok.wav", 50.0)
    monkeypatch.setattr(ingest.soundfile, "SoundFile", _Fake)
    assert ingest.soundfile.SoundFile is not real_soundfile

    with pytest.raises(CoreBuildError) as ei:
        ingest.decode_to_mono(str(existing))
    assert ei.value.code is ErrorCode.INPUT_UNREADABLE
    assert "采样率非法" in str(ei.value)
    # ★ 替身不碰文件系统，原文件必须原样存在
    assert existing.exists()


# ── ② resample_to_profile 的 2 处 raise ─────────────────────────────────

def test_resample_rejects_nonpositive_source_rate() -> None:
    """:122 —— native_sr ≤ 0 → INPUT_UNREADABLE。"""
    x = np.zeros(16, dtype=np.float32)
    with pytest.raises(CoreBuildError) as ei:
        ingest.resample_to_profile(x, 0)
    assert ei.value.code is ErrorCode.INPUT_UNREADABLE
    assert "采样率非法" in str(ei.value)


def test_resample_rejects_multidimensional_samples() -> None:
    """:127 —— samples 非一维 → ValueError（编程错误，非用户输入错误）。"""
    x = np.zeros((4, 2), dtype=np.float32)
    with pytest.raises(ValueError) as ei:
        ingest.resample_to_profile(x, 44100)
    assert "1 维" in str(ei.value)
    assert "ndim=2" in str(ei.value)
    # ★ 编程错误不得被包成 CoreBuildError —— 那会掩盖调用方 bug
    assert not isinstance(ei.value, CoreBuildError)


# ── ③ validate_duration 的 3 处 raise ───────────────────────────────────

def test_validate_duration_rejects_nonpositive_rate() -> None:
    """:157 —— sample_rate ≤ 0 → ValueError。"""
    with pytest.raises(ValueError) as ei:
        ingest.validate_duration(44100, 0)
    assert "必须为正" in str(ei.value)
    assert not isinstance(ei.value, CoreBuildError)


def test_too_short_is_input_too_short() -> None:
    """:161 —— 短于下限 → INPUT_TOO_SHORT。"""
    n = int(AUDIO.min_duration_sec * AUDIO.sample_rate) - AUDIO.sample_rate
    with pytest.raises(CoreBuildError) as ei:
        ingest.validate_duration(n, AUDIO.sample_rate)
    assert ei.value.code is ErrorCode.INPUT_TOO_SHORT
    assert "短于下限" in str(ei.value)


def test_too_long_is_input_too_long() -> None:
    """:166 —— 长于上限 → INPUT_TOO_LONG。★ 消息须含「拒绝截断」。"""
    n = int(AUDIO.max_duration_sec * AUDIO.sample_rate) + AUDIO.sample_rate
    with pytest.raises(CoreBuildError) as ei:
        ingest.validate_duration(n, AUDIO.sample_rate)
    assert ei.value.code is ErrorCode.INPUT_TOO_LONG
    assert "超过上限" in str(ei.value)
    assert "拒绝截断" in str(ei.value)


# ── ④ assert_not_silent 的 2 处 raise ───────────────────────────────────

def test_empty_array_is_treated_as_silent() -> None:
    """:192 —— 空数组 → INPUT_SILENT（先判空，避免 mean 产生 NaN）。"""
    with pytest.raises(CoreBuildError) as ei:
        ingest.assert_not_silent(np.zeros(0, dtype=np.float32))
    assert ei.value.code is ErrorCode.INPUT_SILENT
    assert "空数组" in str(ei.value)


def test_quiet_audio_below_threshold_is_silent(tmp_path: pathlib.Path) -> None:
    """:196 —— RMS < 1e-4 → INPUT_SILENT。"""
    quiet = np.full(44100, 1e-6, dtype=np.float32)  # RMS=1e-6 < 1e-4
    with pytest.raises(CoreBuildError) as ei:
        ingest.assert_not_silent(quiet)
    assert ei.value.code is ErrorCode.INPUT_SILENT
    assert "低于阈值" in str(ei.value)
    assert "非 dBFS" in str(ei.value)  # 单位必须写明，否则会被误读成 dB


# ── ⑤ 边界值：闭区间两端都要测（★ 只测一侧等于没测）────────────────────

def test_exact_minimum_duration_is_accepted(tmp_path: pathlib.Path) -> None:
    """恰好下限合法 —— 比较用 `<` 而非 `<=`，区间是闭区间。"""
    p = _write_tone(tmp_path / "min.wav", AUDIO.min_duration_sec)
    out = ingest.ingest(str(p))
    assert out.dtype == np.float32
    assert out.ndim == 1


def test_just_under_minimum_is_rejected(tmp_path: pathlib.Path) -> None:
    """下限外侧被拒。"""
    p = _write_tone(tmp_path / "under.wav", AUDIO.min_duration_sec - 1.0)
    with pytest.raises(CoreBuildError) as ei:
        ingest.ingest(str(p))
    assert ei.value.code is ErrorCode.INPUT_TOO_SHORT


def test_exact_maximum_duration_is_accepted(tmp_path: pathlib.Path) -> None:
    """恰好上限合法 —— 静默截断会让结果对应到用户不知道的范围。"""
    p = _write_tone(tmp_path / "max.wav", AUDIO.max_duration_sec)
    out = ingest.ingest(str(p))
    assert out.shape[0] == pytest.approx(
        AUDIO.max_duration_sec * AUDIO.sample_rate, rel=1e-3
    )


def test_just_over_maximum_is_rejected(tmp_path: pathlib.Path) -> None:
    """上限外侧被拒，且消息说明是「拒绝截断」而非截断。"""
    p = _write_tone(tmp_path / "over.wav", AUDIO.max_duration_sec + 1.0)
    with pytest.raises(CoreBuildError) as ei:
        ingest.ingest(str(p))
    assert ei.value.code is ErrorCode.INPUT_TOO_LONG
    assert "拒绝截断" in str(ei.value)


# ── ⑥ 端到端错误路径：rc≠0 【且】原因可读 ─────────────────────────────

def _run_main(*args: str, timeout: int = 280) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harmonica_eval", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO),
    )


def test_cli_missing_reference_fails_readably() -> None:
    """不存在的参考曲 → 非零退出，且 stderr 有人能看懂的话。

    ★ 只断言 rc≠0 不合格 —— 崩栈也是 rc≠0。★ 本条同时断言
      「不是 Traceback」与「含中文原因」。
    """
    proc = _run_main(
        "--reference", str(REPO / "no_such_reference.wav"),
        "--practice", str(PRACTICE),
    )
    assert proc.returncode != 0, "缺失输入必须非零退出"
    blob = proc.stdout + proc.stderr
    assert "Traceback" not in blob, "崩栈不是可用的错误路径"
    assert "不存在" in blob or "不是普通文件" in blob


def test_cli_missing_practice_fails_readably() -> None:
    """缺失练习曲侧同样必须可读地失败。"""
    proc = _run_main(
        "--reference", str(REFERENCE),
        "--practice", str(REPO / "no_such_practice.wav"),
    )
    assert proc.returncode != 0
    blob = proc.stdout + proc.stderr
    assert "Traceback" not in blob
    assert "不存在" in blob or "不是普通文件" in blob


def test_cli_too_short_audio_fails_readably(tmp_path: pathlib.Path) -> None:
    """过短音频在【端到端】也必须被拒 —— ★ 不只是在 ingest 单测里成立。

    ★★ 历史留档（★ 不是判据）：2026-09-25 本条曾为 `xfail(strict=True)` ★★
    当时实测：`python3 -m harmonica_eval --reference <10s> --practice <10s>`
    返回 rc=1，但 stderr 是 **33 行完整 Traceback** —— 数据面
    `CoreBuildError(INPUT_TOO_SHORT)` 在 CLI 层没有单独捕获，
    用户看到的是「程序崩了」而不是「音频太短」。

    ★★ 该缺陷已修（`__main__.py` 加了 `except HarmonicaError`）★★
    2026-09-25 复测：rc=1、stderr 仅 1 行、无 Traceback。
    故移除 xfail，★ 断言原样保留 —— ★ 它们现在是【永续判据】，
    ★ 任何人再把异常捕获去掉，本条立刻红。
    """
    short = _write_tone(tmp_path / "short.wav", 10.0)
    proc = _run_main("--reference", str(short), "--practice", str(PRACTICE))

    assert proc.returncode != 0, "过短音频必须非零退出"
    blob = proc.stdout + proc.stderr
    # ★ 错误码与原因确实在
    assert "INPUT_TOO_SHORT" in blob or "短于下限" in blob
    # ★★ 不崩栈（★ 这一条当年正是缺陷本体）
    assert "Traceback" not in blob, (
        "数据面错误未被 CLI 层单独捕获，用户拿到 Traceback "
        "而不是「音频太短」"
    )


def test_cli_error_output_has_no_traceback(tmp_path: pathlib.Path) -> None:
    """把「不崩栈」单独钉成一条：★ 与上面那条分工，便于精确定位。"""
    short = _write_tone(tmp_path / "short.wav", 10.0)
    proc = _run_main("--reference", str(short), "--practice", str(PRACTICE))
    assert proc.returncode != 0
    assert "Traceback" not in (proc.stdout + proc.stderr)


# ── ⑦ 防假绿：rc=0 时必有指标（★ 永续判据）────────────────────────────

def test_success_exit_requires_nonempty_metrics() -> None:
    """`__main__.py` 的 EXIT_OK 判据：error_code 为空【且】有指标。

    ★ 这条锁的是曾真实发生过的假绿：state==DATA_READY 而 scalars 为空。
    ★ 它是【永续判据】—— 任何阶段都成立，不依赖「注入还没做」这类阶段态。
    """
    proc = _run_main("--reference", str(REFERENCE), "--practice", str(PRACTICE))
    assert proc.returncode == 0, proc.stdout + proc.stderr

    import json

    out = REPO / "data" / "out" / "metrics.json"
    assert out.exists(), "rc=0 必须落盘 metrics.json"
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc.get("error_code") is None
    # ★ 关键：rc=0 与「有指标」必须同时成立
    assert doc.get("scalars"), "rc=0 但无标量 = 假绿"
    assert doc.get("series"), "rc=0 但无序列 = 假绿"


def test_exit_ok_never_coexists_with_error_code() -> None:
    """成功态与错误态互斥 —— ★ 防止「有指标但同时报错误」那种混合态。"""
    proc = _run_main("--reference", str(REFERENCE), "--practice", str(PRACTICE))
    assert proc.returncode == 0

    import json

    doc = json.loads(
        (REPO / "data" / "out" / "metrics.json").read_text(encoding="utf-8")
    )
    assert doc.get("error_code") is None and doc.get("error_detail") is None


# ★★★ 缺陷 1（盲审 A 审出）：★ only=[] 的诊断【不得】指向注册表 ★★★
def test_empty_only_does_not_blame_the_registry() -> None:
    """`only=[]` 的报错必须指对方向。

    ★ 「N=0」有两个互不相同的成因：
      · 会话快照里一个算法都没有 → 装配坏了，该查 bootstrap
      · 快照有算法但 only 筛没了   → 调用方传了空集合，该查请求
    ★ ★ 两者共用同一句「注册表快照为空」时，★ 后者会让调用方去查注册表，
    ★ ★ 而那里根本没问题 ——★ 那是最该避免的一类误导。
    """
    sys.path.insert(0, str(REPO))
    from harmonica_eval.contract import (
        ContractViolation, UiCommand, UiCommandKind,
    )
    from harmonica_eval.host.app import build_default_app

    app = build_default_app()
    sid = app.create_session("v1")
    app.set_reference(sid, str(REFERENCE))
    app.set_practice(sid, str(PRACTICE))
    app.build_surface(sid)

    with pytest.raises(ContractViolation) as excinfo:
        app.run_algorithms(sid, only=[])
    message = str(excinfo.value)

    # ★ 注册表里明明有三个算法，★ 所以「注册表快照为空」这句【与事实相反】
    assert "注册表快照为空" not in message, (
        f"only=[] 误报成注册表为空：{message}"
    )
    # ★ 而消息要能指对方向：说清是「没指定 id」以及注册表实际有什么
    assert "未指定任何算法 id" in message, f"消息未指对方向：{message}"
    for name in ("pitch", "timing", "dynamics"):
        assert name in message, f"消息没报出注册表实有的 {name}：{message}"
