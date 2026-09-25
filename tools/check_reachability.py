#!/usr/bin/env python3
"""检查 ⑯：可达性审计 —— 「谁能看见什么」是否逐项对齐。

## 为什么需要这个检查

本仓反复出现同一族缺陷（已 4 次）：
**规格要求产出某个量，但产出者拿不到它。**

  F8      `meta.duration_*` / `alignment.*` —— 投影不携带，写盘方拿不到
  R2-A-1  `inputs` 的两个 URI          —— UiView 不携带，write_metrics_json 拿不到
  R2-A-2  `n_unpaired`                 —— compute_deviations 返回 list[float]，丢掉了
  R2-A-4  `profile.PROFILE_VERSION`    —— §3 禁止 import profile

这类缺陷**不会被"认真读一遍"发现** —— 因为每一句话单独看都对，
错在**两句话之间**。它需要的是机械核查：把「签名能拿到什么」
与「规格要求产出什么」逐项对表。

## 本检查做什么

1. 抽每个函数的**入参名集合**（骨架 = 权威）。
2. 抽该函数所在 BI 的**产出要求**里出现的量名。
3. 若某个量名在 BI 里被标为「产出/必须/输出」，
   但它既不在入参里、也不在投影可见字段里、也不在本函数能算出的东西里
   → 报「不可达」。

因为无法做完整的静态数据流分析，本检查采取**保守**策略：
只报**已知的高置信模式** —— 即 BI 文本里明确写了
「来自 X」「由 X 提供」「X 产出」而该 X 不在本函数的可达集合里。

宁可不报（漏报留给盲审），也不误报（误报会让检查失去信任）。
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent

# 投影（UiView / UiScalar / UiSeries）可见的字段全集 —— 任何拿到 view 的函数
# 都能读到这些。从 contract.py 实测抽取，不手抄。
def _projection_fields() -> set[str]:
    src = (REPO / "harmonica_eval" / "contract.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    want = {"UiView", "UiScalar", "UiSeries", "SurfaceManifest", "PortDescriptor"}
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in want:
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    out.add(stmt.target.id)
    return out


PROJECTION_FIELDS = _projection_fields()

# 骨架文件 ↔ Build Instruction
PAIRS = {
    "harmonica_eval/__main__.py": ".spec/build/FILE-002-v1.md",
    "harmonica_eval/core/ingest.py": ".spec/build/FILE-101-v1.md",
    "harmonica_eval/core/align.py": ".spec/build/FILE-102-v1.md",
    "harmonica_eval/core/features.py": ".spec/build/FILE-103-v1.md",
    "harmonica_eval/core/surface.py": ".spec/build/FILE-104-v1.md",
    "harmonica_eval/core/api.py": ".spec/build/FILE-105-v1.md",
    "harmonica_eval/algorithms/pitch.py": ".spec/build/FILE-201-v1.md",
    "harmonica_eval/algorithms/timing.py": ".spec/build/FILE-202-v1.md",
    "harmonica_eval/algorithms/dynamics.py": ".spec/build/FILE-203-v1.md",
    "harmonica_eval/host/app.py": ".spec/build/FILE-301-v1.md",
    "harmonica_eval/cockpit/app.py": ".spec/build/FILE-401-v1.md",
}

# 已知「产出要求」的量名 → 该量的合法来源集合。
# 只登记**已经裁定的**量，避免猜。
PRODUCED_QUANTITIES: dict[str, set[str]] = {
    # payload 键（FILE-200 的 PAYLOAD_SCHEMAS）—— 必须由算法产出
    "n_unpaired": {"n_unpaired", "matched", "pairs"},
    "n_notes_used": {"deviations_sec", "deltas_db", "per_note_cents"},
    "per_note_onset_sec": {"deviations_sec"},
    "per_note_delta_db": {"deltas_db"},
    "per_note_cents": {"per_note_cents", "deltas_db"},
    # 写盘/渲染需要的输入
    "reference_uri": {"reference_uri"},
    "practice_uri": {"practice_uri"},
    "out_path": {"out_path"},
    # 帧率换算需要的
    "rms_hop_length": {"rms_hop_length", "hop_length"},
    "sample_rate": {"sample_rate", "sr"},
}


def _params(fn: ast.FunctionDef) -> set[str]:
    args = list(fn.args.args) + list(fn.args.kwonlyargs)
    if fn.args.vararg:
        args.append(fn.args.vararg)
    return {a.arg for a in args if a.arg not in ("self", "cls")}


def main() -> int:
    print("⑯ 可达性审计（产出量是否在函数可达集合内）")
    problems: list[str] = []
    checked = 0

    for py_rel, md_rel in PAIRS.items():
        py = REPO / py_rel
        md = REPO / md_rel
        if not py.exists() or not md.exists():
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        doc = md.read_text(encoding="utf-8")

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("__"):
                continue
            params = _params(node)
            # 该函数在 BI 里的段落（从 `### ... name(` 到下一个 `###`）
            # ★ 标题形态实测为 `### 4.4 `name(` —— 节号在名字**之前**，
            #   故正则必须允许「### 后面跟任意非反引号字符，再跟名字」。
            #   本检查第一版要求名字紧跟 `### `，于是**一处都匹配不到**，
            #   12 处「检查」全部是空转 —— 一个永远不会变红的检查。
            #   这正是方法论 §6.3 警告的形态，而它发生在
            #   一个专门用来抓这类缺陷的检查器身上。
            m = re.search(
                r"\n#+ +[^\n`]*`?" + re.escape(node.name) + r"\s*\(", doc
            )
            if not m:
                continue
            seg_end = doc.find("\n### ", m.end())
            seg = doc[m.start() : seg_end if seg_end > 0 else len(doc)]

            for qty, sources in PRODUCED_QUANTITIES.items():
                # 该段是否声明要产出这个量
                if not re.search(r"`" + re.escape(qty) + r"`", seg):
                    continue
                checked += 1
                reachable = params | PROJECTION_FIELDS | sources
                if not (params & sources) and qty not in PROJECTION_FIELDS:
                    # 入参里没有任何来源 —— 只有在段内明确写了"产出/必须恰好产出"
                    # 时才报，避免把「只读引用」误判为「必须产出」
                    if re.search(
                        r"(必须恰好产出|必须产出|输出 dict key|产出该|写入)",
                        seg,
                    ):
                        problems.append(
                            f"  ❌ {py_rel}:{node.lineno} {node.name}() "
                            f"要求产出 `{qty}`，但入参 {sorted(params)} "
                            f"里没有来源（合法来源：{sorted(sources)}）"
                        )

    if problems:
        for p in problems:
            print(p)
        print(f"\n  ❌ {len(problems)} 处不可达")
        return 1
    print(f"  ✅ 检查了 {checked} 处产出声明，全部可达")
    return 0


if __name__ == "__main__":
    sys.exit(main())
