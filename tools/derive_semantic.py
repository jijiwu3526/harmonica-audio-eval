#!/usr/bin/env python3
"""由下往上：从**代码本身**推组件归属（语义版）。

与 tools/derive_clusters.py 的区别：
    derive_clusters.py  用**结构信号**（import 边 / 端口生产 / 契约符号足迹）
    derive_semantic.py  用**语义信号**（每个文件声明自己干什么、不干什么）

为什么需要语义版（这是一次真实的方法修正）：
    早先的机械推导结论是「空壳期代码不足以决定组件边界」，因为 import 图是空的
    （函数体全是 raise，没有任何 import 边）。
    ★ 但这个结论**过头了** —— 信号不在 import 边，而在 **docstring**。
    每个空壳文件的模块 docstring 都完整保留了：
        ROLE      这份代码干什么
        INTENT    为什么存在
        MUST      必须做到什么
        MUST NOT  明令不做什么
    这些是**完整的、可读的**，是合法的自下而上证据。
    当初把「不用 COMPONENT 铭牌（避免抄答案）」错误地扩大成了
    「整个 docstring 都不可用」—— 那是把洗澡水连孩子一起倒掉。

纪律：
    ★ 本工具**绝不读** `COMPONENT:` 那一行 —— 它是答案。
      先推，后与预设对比（对比在另一处做）。

用法：
    python3 tools/derive_semantic.py            # 人类可读报告
    python3 tools/derive_semantic.py --json     # 机器可读
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "harmonica_eval"

# 这些字段是「职责声明」——我们要抽的东西
ROLE_FIELDS = ("ROLE", "INTENT", "MUST", "MUST NOT", "INPUT", "OUTPUT")

# 铭牌字段 —— 只用来定位，**不参与推导**
NAMEPLATE_FIELDS = ("FILE-ID", "COMPONENT", "SPEC", "BUILD-INSTRUCTION")

# 词汇表：用于判断"共享词汇"（谁和谁说同一套话）
VOCAB_PATTERNS = {
    "port_ids": re.compile(r"\b([a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*)\b"),
    "constants": re.compile(r"\b([A-Z][A-Z0-9_]{3,})\b"),
    "symbols": re.compile(r"`([a-z_][a-z0-9_]*)\(\)`"),
}


def parse_module_docstring(src: str) -> str | None:
    """取模块级 docstring。"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    return ast.get_docstring(tree)


def split_nameplate(doc: str) -> dict[str, str]:
    """把 docstring 按 `FIELD:` 切成块。

    ★ 返回的 dict 里**会包含** COMPONENT，但调用方必须不读它。
      本函数不知道调用方会不会守纪律，所以纪律由 derive() 强制。
    """
    out: dict[str, list[str]] = {}
    cur = None
    for line in doc.splitlines():
        m = re.match(r"^\s*([A-Z][A-Z \-]*[A-Z])\s*:\s*(.*)$", line)
        if m:
            cur = m.group(1).strip()
            out.setdefault(cur, [])
            if m.group(2).strip():
                out[cur].append(m.group(2).strip())
        elif cur is not None:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def public_symbols(src: str) -> list[dict[str, str]]:
    """列出模块的公开函数与类（签名 + 各自 docstring 首句）。"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node) or ""
            first = doc.strip().splitlines()[0].strip() if doc.strip() else ""
            out.append({"kind": "fn", "name": node.name, "doc": first})
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node) or ""
            first = doc.strip().splitlines()[0].strip() if doc.strip() else ""
            out.append({"kind": "class", "name": node.name, "doc": first})
    return out


def module_constants(src: str) -> list[str]:
    """模块级大写常量名。"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            n = node.target.id
            if n.isupper():
                out.append(n)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    out.append(t.id)
    return sorted(set(out))


def extract_vocab(text: str) -> dict[str, set[str]]:
    """从文本抽"共享词汇"信号。"""
    out: dict[str, set[str]] = {}
    for key, pat in VOCAB_PATTERNS.items():
        out[key] = set(pat.findall(text))
    # 端口 id 过滤：必须含点，且左边是已知的端口族前缀样式
    out["port_ids"] = {
        p for p in out["port_ids"]
        if "." in p and not p.startswith(("raise", "self.", "np.", "os."))
    }
    return out


def derive() -> list[dict]:
    files = sorted(PKG.rglob("*.py"))
    rows = []
    for path in files:
        rel = path.relative_to(REPO).as_posix()
        src = path.read_text(encoding="utf-8")
        doc = parse_module_docstring(src)
        if not doc:
            continue
        plate = split_nameplate(doc)

        # ★ 纪律：这里**不读** plate["COMPONENT"]
        row = {
            "file": rel,
            "role": plate.get("ROLE", ""),
            "intent": plate.get("INTENT", ""),
            "must": plate.get("MUST", ""),
            "must_not": plate.get("MUST NOT", ""),
            "input": plate.get("INPUT", ""),
            "output": plate.get("OUTPUT", ""),
            "symbols": public_symbols(src),
            "constants": module_constants(src),
            "vocab": {k: sorted(v) for k, v in extract_vocab(doc).items()},
            # 供事后对比用（推导过程不参与）
            "_answer_component": plate.get("COMPONENT", ""),
            "_nameplate_file_id": plate.get("FILE-ID", ""),
        }
        rows.append(row)
    return rows


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def pairwise_affinity(rows: list[dict]) -> list[tuple[str, str, float, str]]:
    """两两文件的语义亲和度（基于共享词汇）。"""
    out = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            best, why = 0.0, []
            for key in ("port_ids", "constants"):
                sa, sb = set(a["vocab"][key]), set(b["vocab"][key])
                j = jaccard(sa, sb)
                if j > best:
                    best, why = j, [f"{key}: {sorted(sa & sb)[:6]}"]
                elif j == best and j > 0:
                    why.append(f"{key}: {sorted(sa & sb)[:6]}")
            if best > 0:
                out.append((a["file"], b["file"], round(best, 3), "; ".join(why)))
    out.sort(key=lambda x: -x[2])
    return out


def main() -> int:
    as_json = "--json" in sys.argv
    rows = derive()

    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print("=" * 78)
    print("语义自下而上推导 · 只读代码本身（跳过 COMPONENT 铭牌）")
    print("=" * 78)
    print(f"共 {len(rows)} 个文件带模块 docstring\n")

    for r in rows:
        print("─" * 78)
        print(f"■ {r['file']}")
        print(f"  ROLE     : {r['role'][:300] or '（无）'}")
        if r["intent"]:
            print(f"  INTENT   : {r['intent'][:300]}")
        if r["must"]:
            for ln in r["must"].splitlines():
                if ln.strip():
                    print(f"  MUST     : {ln.strip()[:200]}")
        if r["must_not"]:
            for ln in r["must_not"].splitlines():
                if ln.strip():
                    print(f"  MUST NOT : {ln.strip()[:200]}")
        print(f"  OUTPUT   : {r['output'][:200] or '（无）'}")
        if r["symbols"]:
            syms = ", ".join(f"{s['name']}()" if s["kind"] == "fn" else s["name"]
                             for s in r["symbols"])
            print(f"  公开符号 : {syms}")
        if r["constants"]:
            print(f"  常量     : {', '.join(r['constants'])}")
        print()

    print("=" * 78)
    print("共享词汇亲和度（前 25 对，基于端口 id 与常量名）")
    print("=" * 78)
    for a, b, score, why in pairwise_affinity(rows)[:25]:
        print(f"  {score:.3f}  {a.split('/')[-1]:<16} ↔ {b.split('/')[-1]:<16} {why[:70]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
