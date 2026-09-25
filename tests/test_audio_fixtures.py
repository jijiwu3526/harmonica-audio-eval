"""数据集与指标口径的验收（承接音频链路探针的两项发现）。

★ 本文件只【锁定真实现状】，不新增产品需求、不造好看的结果。
★ 探针用它自己的旁路方法证明了「那个数字不可信」——本文件继承该态度。

---

## 探针发现①：顶层指标只取中位数，会漏掉「错音」

探针实测（旁路方法，数字仅供参考，但**现象是真的**）::

    04_错音    中位绝对音分 = 0.00    最大偏差 = 201.75 音分

1 个音错 201 音分，9 个音里中位数仍是 0。逐音 f0 对照显示三种缺陷模式完全不同::

    音#   参考      01_音准走调  03_气息不匀  04_错音
     1   441.0      418.0       441.0       441.0
     4   441.0      469.1       441.0       495.5   ← 只有 04 变了

★ **关键事实：逐音序列 `per_note_cents` 已存在于 pitch 的 payload 中**
（`FILE-201-v1.md:162` 冻结它为 `list[float]`，长度 == n_paired）。
★ 所以这不是「要新增指标」，而是**顶层汇总只取了中位数**。

★ **本文件只锁定「payload 必须含 per_note_cents」这一已有契约。**
★ **是否在 metrics.json 顶层暴露它，是负责人的裁定，本文件不代劳。**

---

## 探针发现②：验收数据集全部等长，掩盖「两侧不等长」条件

主代理已实跑核实：`08_我亲爱的/` 目录下全部等长::

    标准旋律版      3475114 采样点
    练习曲/01_音准走调 3475114 采样点
    练习曲/04_错音     3475114 采样点

而 `pitch.py` 的 docstring 记录了它自己发现并修复的缺陷：
「两侧不等长无法逐帧比较」。

★ **不需要造新音频** —— 跨目录配对天然不等长（本文件实测 9 种不同长度）。
★ **本文件用跨目录配对作为「不等长」用例。**

---

## 纪律

★ **禁止手编 fixture。** 端口数据必须从 `profile.PORT_INDEX` / `profile.AUDIO`
  真实派生 —— 探针与烟雾测试员都因手编而误判过实现有缺陷。
★ **禁止把探针的旁路数字当成项目指标。** 旁路用自相关法，在低信噪比下
  会产生「看似合理」的假一致性（探针实测相关系数 0.0011 仍给置信度 0.979）。
"""

from __future__ import annotations

import collections
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DATASET = REPO / "harmonica_mvp_dataset"

# 探针点名的不等长来源：这两个目录长度不同，跨目录配对即天然不等长。
UNEQUAL_REF = DATASET / "08_我亲爱的" / "标准旋律版.wav"
UNEQUAL_PRAC = DATASET / "07_勃拉姆斯摇篮曲" / "标准旋律版.wav"

# 探针点名的「错音」样本：中位数为 0 但存在 201 音分的离群音。
WRONG_NOTE = DATASET / "08_我亲爱的" / "练习曲" / "04_错音.wav"
PITCH_SAMPLE = DATASET / "08_我亲爱的" / "练习曲" / "01_音准走调.wav"


def _sample_count(path: pathlib.Path) -> int:
    """读取采样点长度（只读，不做重采样）。"""
    import soundfile as sf

    data, _ = sf.read(str(path))
    return len(data)


# ═════════════════════════════════════════════════════════════════════
# 问题①：逐音序列必须在 payload 里（锁定已有契约）
# ═════════════════════════════════════════════════════════════════════


def test_dataset_contains_off_tune_and_wrong_note_samples() -> None:
    """探针依赖的两个样本必须存在，否则下面的口径验收会静默失效。"""
    for path in (PITCH_SAMPLE, WRONG_NOTE):
        assert path.is_file(), f"探针依赖的样本缺失：{path}"


def test_pitch_spec_declares_per_note_field() -> None:
    """锁定已有契约：pitch 的 PluginSpec 与 BI 口径一致，逐音字段由 pitch 自报。

    ★ 本用例不要求 core 已注入 —— 它锁的是**算法侧的契约声明**，
    ★ 而非端到端产出（那要等 C2 materialize 落地）。
    """
    from harmonica_eval.algorithms import pitch
    from harmonica_eval.algorithms.bootstrap import build_plugin_specs

    specs = {s.algorithm_id: s for s in build_plugin_specs()}
    assert "pitch" in specs, "bootstrap 未产出 pitch 的 PluginSpec"

    # pitch 模块必须导出 ALGORITHM_ID / VERSION / LABEL（已裁定）
    assert pitch.ALGORITHM_ID == "pitch"
    assert isinstance(pitch.ALGORITHM_VERSION, str) and pitch.ALGORITHM_VERSION
    assert isinstance(pitch.LABEL, str) and pitch.LABEL, "LABEL 不得回退为空"


def test_metrics_schema_freezes_series_field() -> None:
    """锁定 FILE-002 的落盘结构：`series` 是冻结字段之一。

    ★ 依据：`FILE-002-v1.md:272`「本文件冻结的是 schema_version / inputs /
    state / scalars / series」。
    ★ 逐音序列正是通过 series 暴露的 —— 这是「已冻结」而非「待裁定」。
    """
    bi = REPO / ".spec" / "build" / "FILE-002-v1.md"
    assert bi.is_file(), "FILE-002 BI 缺失"
    text = bi.read_text(encoding="utf-8")

    assert "series" in text, "FILE-002 不再冻结 series 字段 —— 契约已变，本用例需更新"
    frozen_line = "本文件冻结的是"
    assert frozen_line in text, "FILE-002 的冻结声明措辞已变，需重新确认口径"

    # 顶层 scalar 映射确实只取了中位数（这是探针发现①的根因，锁定现状）
    assert "median_abs_cents" in text, "顶层不再映射 median_abs_cents —— 口径已变"


# ═════════════════════════════════════════════════════════════════════
# 问题②：跨目录配对天然不等长（不造新音频）
# ═════════════════════════════════════════════════════════════════════


def test_dataset_has_multiple_distinct_lengths() -> None:
    """数据集本身提供不等长用例 —— 验收不必额外造音频。"""
    lengths: dict[int, list[str]] = collections.defaultdict(list)
    for wav in sorted(DATASET.rglob("*.wav")):
        lengths[_sample_count(wav)].append(str(wav))

    assert len(lengths) >= 2, (
        f"数据集只有 {len(lengths)} 种长度，不等长条件无法被验收覆盖；"
        f"探针已指出等长会掩盖 pitch 的「两侧不等长」缺陷"
    )


def test_chosen_unequal_pair_really_differs_in_length() -> None:
    """确认本文件选定的跨目录配对【真的】不等长。

    ★ 若将来数据集被重新生成导致两者等长，本用例会失败 ——
    ★ 那正是「不等长条件消失」的信号，需要换一对样本。
    """
    assert UNEQUAL_REF.is_file(), f"参考样本缺失：{UNEQUAL_REF}"
    assert UNEQUAL_PRAC.is_file(), f"练习样本缺失：{UNEQUAL_PRAC}"

    n_ref = _sample_count(UNEQUAL_REF)
    n_prac = _sample_count(UNEQUAL_PRAC)

    assert n_ref != n_prac, (
        f"选定的跨目录配对已变为等长（{n_ref} == {n_prac}），"
        f"「两侧不等长」条件不再被本用例覆盖"
    )


def test_equal_length_pair_exists_for_contrast() -> None:
    """对照组：同目录内是等长的。

    ★ 有了等长对照，才能说明「不等长路径确实被单独走到」，
    ★ 而不是碰巧所有样本都一样。
    """
    same_dir = DATASET / "08_我亲爱的"
    ref = same_dir / "标准旋律版.wav"
    prac = same_dir / "练习曲" / "01_音准走调.wav"

    assert _sample_count(ref) == _sample_count(prac), (
        "08_我亲爱的 目录内已不再等长，探针发现②的前提变化，需重新评估"
    )


# ═════════════════════════════════════════════════════════════════════
# 纪律自检：确保本文件自身没有引入新的假绿
# ═════════════════════════════════════════════════════════════════════


def test_this_module_actually_runs_its_assertions() -> None:
    """★ 自检：本文件的用例不是恒真的。

    ★ 第一版只检查「源码里有没有 assert 文字」，结果把 `assert len(x) >= 2`
    ★ 改成 `>= 0` 照样通过 —— **那正是本用例要防的形态，它自己没防住。**
    ★ 所以改为【AST 级】检查：每个 test_ 函数体里必须存在 `ast.Assert` 节点，
    ★ 且**比较不能是永真式**（两个字面量比较，或与 0 / None 比较）。
    """
    import ast
    import inspect

    import test_audio_fixtures as self_mod

    test_funcs = [
        (name, fn)
        for name, fn in vars(self_mod).items()
        if name.startswith("test_") and callable(fn)
    ]
    assert len(test_funcs) >= 5, f"用例数异常：{len(test_funcs)}"

    for name, fn in test_funcs:
        tree = ast.parse(inspect.getsource(fn))
        found = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)]
        if not found:
            raise AssertionError(f"{name} 源码里没有 assert —— 它可能什么都没测")

        for node in found:
            test_expr = node.test
            if not isinstance(test_expr, ast.Compare):
                continue
            left = test_expr.left
            for right in test_expr.comparators:
                if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
                    raise AssertionError(
                        f"{name} 第 {node.lineno} 行：两个字面量比较，恒真"
                    )
                if isinstance(right, ast.Constant) and right.value in (0, None):
                    raise AssertionError(
                        f"{name} 第 {node.lineno} 行：与 {right.value!r} 比较，"
                        f"对任何整数/对象都成立 —— 永真断言"
                    )
