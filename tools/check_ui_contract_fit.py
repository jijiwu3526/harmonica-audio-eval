#!/usr/bin/env python3
"""UI 契约可绘制性检查 —— 「真数据到来前，契约够不够画界面？」

FILE-ID:      TOOL-UI-FIT
COMPONENT:    工具层（不属于 C1/C2/C3/C4 任一组件）
SPEC:         SPEC.md@v2.1 §1（开发者调试视图例外条款）· contract.py（冻结）

ROLE:
    在 C1 注入并投影真实数据**之前**，用一份由契约真实构造的样本数据
    回答一个具体问题：**如果 C1 明天投影真实值，前端能画出来吗？**

INTENT:
    `cockpit/preview.py` 存在的意义是「验证契约是否够用」。
    但它只读契约的**类型**，读不到**数据**，所以它无法回答
    「每个字段在前端都有去处吗」。

    ★ 本工具补上这一环：它拿一份**完整的 UiView 样本**逐字段核对，
    ★ 找出「契约投影了但前端不用」与「前端要但契约没给」两类缺口。

    ★ **缺口的发现成本**：注入后返工 ≫ 注入前发现。
    ★ 这正是 preview 视图「在注入前发现，比注入后返工便宜」的落地。

MUST:
    - 只读 contract.py / profile.py / 样本 JSON，零写入（除自身报告）
    - 样本必须由**契约真实构造**，不得凭空编造字段
    - 判据只许更严：缺一个字段就报错，不许「大部分字段有就放过」
    - 失败必须以非零退出码报告

MUST NOT:
    - 不得修改样本让它通过（那是掩盖缺口）
    - 不得放宽契约要求来让检查变绿
    - 不得引入第三方依赖
    - 不得 import C1/C2/C3 的实现模块（只读 contract / profile）

INPUT:
    tools/fixtures/ui_sample.json（样本，由 profile.PORTS + contract 真实派生）

OUTPUT:
    逐项核对结果；缺口清单；非零退出码表示存在缺口

BUILD-INSTRUCTION:
    本文件是工具，非组件实现。契约变更时同步更新 SAMPLE_SCHEMA。
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harmonica_eval import contract as c  # noqa: E402
from harmonica_eval import profile  # noqa: E402

SAMPLE = REPO / "tools" / "fixtures" / "ui_sample.json"

# ★ 裁定（2026-09-24）：C1 只向 C4 投影 PortDescriptor 的 5 字段子集。
# ★ 理由：其余 6 个是 C2 实现细节，经 C1 转手全量投影等于换了个手泄漏 C2 内部。
PROJECTED_PORT_FIELDS = ("port_id", "units", "dimensions", "shape", "timeline_basis")

# ★ 由 contract.py:1231 约定：UI 载荷的键名不得增删。
UI_SCALAR_FIELDS = tuple(c.UiScalar.__dataclass_fields__)
UI_SERIES_FIELDS = tuple(c.UiSeries.__dataclass_fields__)
UI_VIEW_FIELDS = tuple(c.UiView.__dataclass_fields__)


def _fail(problems: list[str], msg: str) -> None:
    problems.append(msg)


def check_scalar_shape(scalars: list, problems: list[str]) -> None:
    """UiScalar 每个字段都必须出现在样本里。"""
    for idx, sc in enumerate(scalars):
        missing = set(UI_SCALAR_FIELDS) - set(sc)
        extra = set(sc) - set(UI_SCALAR_FIELDS)
        if missing:
            _fail(problems, f"scalars[{idx}] 缺字段 {sorted(missing)}")
        if extra:
            _fail(problems, f"scalars[{idx}] 有契约外字段 {sorted(extra)}")


def check_series_shape(series: list, problems: list[str]) -> None:
    """UiSeries 每个字段都必须出现在样本里。"""
    for idx, se in enumerate(series):
        missing = set(UI_SERIES_FIELDS) - set(se)
        extra = set(se) - set(UI_SERIES_FIELDS)
        if missing:
            _fail(problems, f"series[{idx}] 缺字段 {sorted(missing)}")
        if extra:
            _fail(problems, f"series[{idx}] 有契约外字段 {sorted(extra)}")
        # timeline_basis 必须是契约枚举的合法值
        basis = se.get("timeline_basis")
        legal = {b.value for b in c.TimelineBasis}
        if basis not in legal:
            _fail(problems, f"series[{idx}].timeline_basis={basis!r} 不在 {sorted(legal)}")


def check_view_shape(view: dict, problems: list[str]) -> None:
    """UiView 顶层每个字段都必须存在。"""
    missing = set(UI_VIEW_FIELDS) - set(view)
    if missing:
        _fail(problems, f"UiView 缺字段 {sorted(missing)}")


def check_units_covered(scalars: list, problems: list[str]) -> None:
    """★ 10 个受控单位必须全部在样本里出现——否则有单位没有任何展示位置。"""
    used = {s.get("unit") for s in scalars}
    used |= {s.get("unit") for s in JSON_SAMPLE.get("series", [])}
    uncovered = set(c.UNITS_VOCABULARY) - used
    if uncovered:
        _fail(problems, f"这些受控单位在样本中无任何展示位置: {sorted(uncovered)}")
    illegal = used - set(c.UNITS_VOCABULARY)
    if illegal:
        _fail(problems, f"样本用了词表外的单位: {sorted(illegal)}")


def check_states_covered(scalars: list, problems: list[str]) -> None:
    """★ 6 个会话状态必须全部可被前端处理。"""
    declared = {s.value for s in c.SessionState}
    # 状态以 st_<STATE> 形式的标量样本表示可处理性
    seen = {s["key"][3:] for s in scalars if str(s.get("key", "")).startswith("st_")}
    uncovered = declared - seen
    if uncovered:
        _fail(problems, f"这些会话状态在样本中无处理位置: {sorted(uncovered)}")


def check_ports(view: dict, problems: list[str]) -> None:
    """★ 12 个端口必须全部投影，且只投影裁定的 5 个字段。"""
    ps = view.get("port_summary") or []
    declared = {p.port_id for p in profile.PORTS}
    got = {p.get("port_id") for p in ps}
    missing = declared - got
    if missing:
        _fail(problems, f"这些端口未出现在 port_summary: {sorted(missing)}")
    if got - declared:
        _fail(problems, f"port_summary 含 profile 中不存在的端口: {sorted(got - declared)}")
    for idx, p in enumerate(ps):
        if not isinstance(p, dict):
            _fail(problems, f"port_summary[{idx}] 不是对象")
            continue
        extra = set(p) - set(PROJECTED_PORT_FIELDS)
        if extra:
            _fail(problems, f"port_summary[{idx}] 投影了裁定外字段 {sorted(extra)}")
        for f in PROJECTED_PORT_FIELDS:
            if f not in p:
                _fail(problems, f"port_summary[{idx}] 缺字段 {f}")


def check_shape_derivable(problems: list[str]) -> None:
    """★ 契约缺口探测：`PortDescriptor.shape` 在 `PortSpec` 里没有对应字段。

    ★ 只检查**投影子集**（`PROJECTED_PORT_FIELDS`）内的字段。

    早先版本比对 `PortDescriptor` 全部 11 个字段，于是把
    `content_hash` / `sample_rate` / `schema_version` 也报成缺口 ——
    ★ 那是**误报**：那 3 个字段已由 2026-09-24 裁定**不投影**
    （它们是 C2 实现细节，全量投影等于换手泄漏，见 contract.py 的
    `UiView.port_summary` 冻结说明）。

    ★ 真缺口只有 `shape`：它是**运行期事实**（帧数依赖音频时长与 hop），
    静态 profile 给不出，**也不得**从 `dimensions` 语义名反推。
    → 裁定方案「C1 向 C2 询问」，载体是现成的
    `Surface.manifest().ports[*].shape`，**不新增 port 操作**。

    本检查的职责是验证「该裁定在契约层有据可依」，因此：
    · 若 `shape` 仍无来源说明 → 报缺口
    · 若已裁定且载体存在 → 确认通过（不再报）
    """
    spec_fields = set(profile.PortSpec.__dataclass_fields__)

    # ★ 只看投影子集，不看 PortDescriptor 全部字段
    unbacked_projected = set(PROJECTED_PORT_FIELDS) - spec_fields

    # 已裁定不投影的字段（列出以免有人误加回投影子集）
    intentionally_not_projected = {
        "schema_version", "element_type", "field_names",
        "hop_length", "sample_rate", "content_hash",
    }
    leaked = set(PROJECTED_PORT_FIELDS) & intentionally_not_projected
    if leaked:
        _fail(problems, f"投影子集含已裁定不投影的字段：{sorted(leaked)}")

    # ★ shape 是唯一真缺口：必须有「C1 向 C2 询问」的契约层依据
    if "shape" in unbacked_projected:
        if not _contract_documents_shape_source():
            _fail(
                problems,
                "★ 契约缺口：投影子集含 'shape'，但 PortSpec 无此字段，"
                "且契约层未写明「C1 向 C2 询问」的来源裁定"
                "（应记入 PortDescriptor.shape 的 docstring）",
            )
        else:
            print("  · shape 已由契约层裁定「C1 向 C2 询问」"
                  "（Surface.manifest().ports[*].shape），不新增 port 操作 ✅")


def _contract_documents_shape_source() -> bool:
    """契约层是否已写明 `shape` 的来源裁定。

    ★ 判据是**语义**：docstring 必须同时说清
      · shape 是运行期事实、不在 PortSpec
      · 由 C1 经 manifest() 向 C2 询问
    ★ 不绑死具体措辞（否则改个词就假红 —— 那正是脚本 7 栽过的坑）。
    """
    doc = c.PortDescriptor.__doc__ or ""
    if _safe_source(c.PortDescriptor):
        # 字段级 docstring 就在类源码里，一并纳入
        doc += " " + inspect.getsource(c.PortDescriptor)
    hay = doc
    return (
        ("shape" in hay)
        and ("运行期" in hay or "运行期事实" in hay)
        and ("C1" in hay)
        and ("C2" in hay)
        and ("manifest" in hay)
    )


def _safe_source(obj: object) -> bool:
    try:
        inspect.getsource(obj)
        return True
    except (OSError, TypeError):
        return False


def main() -> int:
    global JSON_SAMPLE
    print("⑳ UI 契约可绘制性 —— 真数据到来前，契约够不够画界面？")
    print("=" * 68)
    if not SAMPLE.is_file():
        print(f"❌ 样本不存在：{SAMPLE}")
        return 1
    JSON_SAMPLE = json.loads(SAMPLE.read_text(encoding="utf-8"))
    problems: list[str] = []

    check_view_shape(JSON_SAMPLE, problems)
    scalars = JSON_SAMPLE.get("scalars") or []
    series = JSON_SAMPLE.get("series") or []
    check_scalar_shape(scalars, problems)
    check_series_shape(series, problems)
    check_units_covered(scalars, problems)
    check_states_covered(scalars, problems)
    check_ports(JSON_SAMPLE, problems)
    check_shape_derivable(problems)

    print(f"  样本：scalars={len(scalars)} series={len(series)} "
          f"port_summary={len(JSON_SAMPLE.get('port_summary') or [])}")
    print(f"  契约：UiView={len(UI_VIEW_FIELDS)} 字段 · "
          f"UiScalar={len(UI_SCALAR_FIELDS)} · UiSeries={len(UI_SERIES_FIELDS)} · "
          f"PortDescriptor 投影子集={len(PROJECTED_PORT_FIELDS)}")
    print(f"  单位词表={len(c.UNITS_VOCABULARY)} · 会话状态={len(list(c.SessionState))} · "
          f"端口={len(profile.PORTS)}")

    if problems:
        print(f"\n❌ 发现 {len(problems)} 处缺口：")
        for p in problems:
            print(f"   · {p}")
        print("\n结论：契约**尚不足以**无摩擦驱动前端 —— 见上方缺口清单。")
        return 1
    print("\n✅ 契约足以驱动前端：每个字段都有来源与去处，"
          "每个单位与状态都有展示位置，12 个端口全部投影且只投影裁定字段。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
