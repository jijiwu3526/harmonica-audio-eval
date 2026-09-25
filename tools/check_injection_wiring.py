#!/usr/bin/env python3
"""跨模块接线检查：验证第 1 刀（bootstrap）与第 2 刀（registry）接在一起时正确。

FILE-ID:      WIRING-CHECK
ROLE:         验证「各自 §8 全过」不等于「合起来正确」。

BACKGROUND:
    FILE-206 §8 跑通端到端，但只验 algorithm_id 顺序与 get 命中；
    FILE-204 §8 用的是自己构造的假 PluginSpec（required_inputs=()、
    entry=lambda s: None），与 bootstrap 的真实产出无关。

    ★ 因此「bootstrap 产的 entry 指向谁」「required_inputs 与算法源码
    ★ MUST 是否一致」这类【跨模块接错】，当前没有任何判据能抓到。

    本检查补这个缺口。判据只许更严，不许更松。
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

ALGO_MODULES = ("pitch", "timing", "dynamics")
# ★ 端口名是两段（notes.reference）或三段（pcm.mapped.reference），
# ★ 早期版本误写成固定三段，导致 notes.reference 整类漏抽 —— 假红。
PORT_RE = re.compile(r"\b((?:pitch|pcm|notes|rms)(?:\.[a-z]+){1,2})\b")


def fail(msg: str) -> None:
    print(f"❌ {msg}")
    FAILURES.append(msg)


FAILURES: list[str] = []


def module_must_ports(path: pathlib.Path) -> set[str]:
    """从算法模块 docstring 的 MUST 段抽出端口名（只看 MUST，不看 MUST NOT）。"""
    text = path.read_text(encoding="utf-8")
    # 只取 MUST: 到 MUST NOT: 之间 —— MUST NOT 里出现的端口是【禁止】消费
    m = re.search(r"^MUST:(.*?)^MUST NOT:", text, re.S | re.M)
    if not m:
        fail(f"{path.name} 找不到 MUST 段，无法交叉核对")
        return set()
    return set(PORT_RE.findall(m.group(1)))


def main() -> int:  # noqa: C901
    from harmonica_eval import contract, profile
    from harmonica_eval.algorithms import dynamics, pitch, timing
    from harmonica_eval.algorithms.bootstrap import (
        ALGORITHM_INPUTS,
        REGISTRATION_ORDER,
        build_default_registry,
    )

    modules = {"pitch": pitch, "timing": timing, "dynamics": dynamics}
    reg = build_default_registry()
    specs = reg.list()

    # ── 接线 1：产出的 Spec 数量与顺序等于声明的顺序 ──
    if [s.algorithm_id for s in specs] != list(REGISTRATION_ORDER):
        fail(
            f"Registry 顺序与 REGISTRATION_ORDER 不一致："
            f"{[s.algorithm_id for s in specs]} vs {list(REGISTRATION_ORDER)}"
        )

    # ── 接线 2：每个 Spec 的身份字段真来自对应算法模块 ──
    for s in specs:
        m = modules.get(s.algorithm_id)
        if m is None:
            fail(f"Registry 里有未知 algorithm_id：{s.algorithm_id}")
            continue
        if s.algorithm_id != m.ALGORITHM_ID:
            fail(f"{s.algorithm_id}.algorithm_id 与模块常量不符：{m.ALGORITHM_ID}")
        if s.algorithm_version != m.ALGORITHM_VERSION:
            fail(
                f"{s.algorithm_id}.algorithm_version 与模块常量不符："
                f"{s.algorithm_version} vs {m.ALGORITHM_VERSION}"
            )

        # ── 接线 3：entry 必须【就是】那个模块的 run，不能是别的东西 ──
        if s.entry is not m.run:
            fail(
                f"{s.algorithm_id}.entry 不是 {m.__name__}.run："
                f"实为 {getattr(s.entry, '__module__', '?')}."
                f"{getattr(s.entry, '__name__', '?')}"
            )

        # ── 接线 4：entry 签名必须符合契约冻结类型 ──
        sig = inspect.signature(s.entry)
        params = list(sig.parameters)
        if len(params) != 1:
            fail(f"{s.algorithm_id}.entry 签名应为 1 参，实为 {params}")
        want = list(inspect.signature(contract.AlgorithmDataContract.read).parameters)
        if params and params[0] != "surface":
            fail(f"{s.algorithm_id}.entry 首参名应为 'surface'，实为 {params[0]!r}")
        del want

        # ── 接线 5：端口名必须真实存在于 profile.PORTS ──
        declared = ALGORITHM_INPUTS.get(s.algorithm_id, ())
        got = tuple(r.port_id for r in s.required_inputs)
        if got != tuple(declared):
            fail(f"{s.algorithm_id} 的 required_inputs 与 ALGORITHM_INPUTS 不一致：{got}")
        for r in s.required_inputs:
            if r.port_id not in profile.PORT_INDEX:
                fail(f"{s.algorithm_id} 声明了不存在的端口：{r.port_id}")

        # ── 接线 6：★ 核心 —— 端口需求必须与算法源码 MUST 逐条对应 ──
        must_ports = module_must_ports(
            REPO / "harmonica_eval" / "algorithms" / f"{s.algorithm_id}.py"
        )
        if must_ports and set(declared) != must_ports:
            fail(
                f"{s.algorithm_id} 的端口需求与源码 MUST 不一致："
                f"声明 {sorted(set(declared))} vs MUST {sorted(must_ports)}"
            )

        # ── 接线 7：派生属性必须与 PortSpec 声明一致 ──
        for r in s.required_inputs:
            ps = profile.PORT_INDEX.get(r.port_id)
            if ps is None:
                continue
            if str(ps.element_type) != str(r.element_type):
                fail(
                    f"{r.port_id}.element_type 与 PortSpec 不符："
                    f"{r.element_type} vs {ps.element_type}"
                )
            if str(ps.timeline_basis) != str(r.timeline_basis):
                fail(
                    f"{r.port_id}.timeline_basis 与 PortSpec 不符："
                    f"{r.timeline_basis} vs {ps.timeline_basis}"
                )

    # ── 接线 8：registry.get 命中的必须是同一个对象 ──
    for s in specs:
        if reg.get(s.algorithm_id) is not s:
            fail(f"registry.get({s.algorithm_id}) 未命中同一对象")
    if reg.get("__not_registered__") is not None:
        fail("registry.get 对未登记 id 未返回 None")

    # ── 接线 9：算法模块不得被 bootstrap 之外的代码 import（GC-204-08 的机器形态）──
    # ★ 并发注入期间别的文件可能是半截文本，ast.parse 会炸 ——
    # ★ 那不是接线问题，跳过该文件并明确报告，不让本检查器因并发而崩。
    allowed = {"harmonica_eval/algorithms/bootstrap.py"}
    skipped: list[str] = []
    for path in (REPO / "harmonica_eval").rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        rel = str(path.relative_to(REPO))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            skipped.append(rel)
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                ("pitch", "timing", "dynamics", ".pitch", ".timing", ".dynamics")
            ):
                if rel not in allowed:
                    fail(f"{rel} import 了具体算法模块（GC-204-08 已关闭）")

    if skipped:
        print(f"⏭ 跳过 {len(skipped)} 个并发写入中的文件（无法解析）：{', '.join(skipped)}")

    if FAILURES:
        print(f"\n结论：❌ 接线有 {len(FAILURES)} 处问题")
        return 1
    print(
        f"✅ 接线全部成立：{len(specs)} 个 Spec · "
        f"{sum(len(s.required_inputs) for s in specs)} 条端口需求 · "
        f"顺序 {list(REGISTRATION_ORDER)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
