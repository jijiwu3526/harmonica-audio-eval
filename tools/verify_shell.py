#!/usr/bin/env python3
"""verify_shell.py —— 空壳完整性与纯净度验证。

回答两个问题：
  1. 结构完整性：每个文件都在、都能 import、都有现场铭牌
  2. 纯净度：没有实现代码混进来（本轮只造空壳）

用法：python3 tools/verify_shell.py
退出码：0 通过 / 1 有违规
无随机性、无副作用（只读）。
"""

from __future__ import annotations

import ast
import importlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "harmonica_eval"

# 本轮交付的 18 个文件（PLAN.md §四）
EXPECTED = [
    "harmonica_eval/__init__.py",
    "harmonica_eval/__main__.py",
    "harmonica_eval/contract.py",
    "harmonica_eval/profile.py",
    "harmonica_eval/core/__init__.py",
    "harmonica_eval/core/ingest.py",
    "harmonica_eval/core/align.py",
    "harmonica_eval/core/features.py",
    "harmonica_eval/core/surface.py",
    "harmonica_eval/core/api.py",
    "harmonica_eval/algorithms/__init__.py",
    "harmonica_eval/algorithms/pitch.py",
    "harmonica_eval/algorithms/timing.py",
    "harmonica_eval/algorithms/dynamics.py",
    "harmonica_eval/host/__init__.py",
    "harmonica_eval/host/app.py",
    "harmonica_eval/cockpit/__init__.py",
    "harmonica_eval/cockpit/app.py",
]

SHELL_MARK = re.compile(r'NotImplementedError\("SHELL: FILE-\d+')
NAMEPLATE = re.compile(r"FILE-ID:\s*FILE-\d+")

# 允许含实现的文件（地基，非空壳）
GROUND = {
    "harmonica_eval/contract.py",
    "harmonica_eval/profile.py",
    "harmonica_eval/__init__.py",
}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.stats: dict[str, int] = {}

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def check_existence(r: Report) -> None:
    print("─" * 72)
    print("① 文件坑位（宪章 §17：Freeze 前必须存在）")
    print("─" * 72)
    missing, present = [], 0
    for rel in EXPECTED:
        p = REPO / rel
        if p.exists():
            present += 1
            print(f"  ✅ {rel}")
        else:
            missing.append(rel)
            print(f"  ❌ {rel}  ← 缺失")
    r.stats["文件存在"] = present
    r.stats["文件总数"] = len(EXPECTED)
    for m in missing:
        r.err(f"文件缺失: {m}")


def check_imports(r: Report) -> None:
    print()
    print("─" * 72)
    print("② 可加载性（空壳必须能 import，否则下游无法开工）")
    print("─" * 72)
    sys.path.insert(0, str(REPO))
    ok, failed = 0, []
    for rel in EXPECTED:
        mod = rel.replace("/", ".").removesuffix(".py")
        if mod.endswith(".__init__"):
            mod = mod.removesuffix(".__init__")
        try:
            importlib.import_module(mod)
            ok += 1
            print(f"  ✅ {mod}")
        except Exception as exc:
            failed.append((mod, f"{type(exc).__name__}: {exc}"))
            print(f"  ❌ {mod}  ← {type(exc).__name__}: {exc}")
    r.stats["可 import"] = ok
    for mod, e in failed:
        r.err(f"import 失败: {mod} → {e}")


def check_nameplate(r: Report) -> None:
    print()
    print("─" * 72)
    print("③ 现场铭牌（宪章 §18）")
    print("─" * 72)
    stamped = 0
    for rel in EXPECTED:
        p = REPO / rel
        if not p.exists():
            continue
        src = p.read_text(encoding="utf-8")
        if NAMEPLATE.search(src):
            stamped += 1
        else:
            r.err(f"缺现场铭牌 FILE-ID: {rel}")
            print(f"  ❌ {rel}")
    r.stats["有铭牌"] = stamped
    print(f"  {stamped}/{len(EXPECTED)} 个文件有 FILE-ID 铭牌")


def check_shell_purity(r: Report) -> None:
    """核心检查：空壳文件里不许有实现代码。"""
    print()
    print("─" * 72)
    print("④ 空壳纯净度（本轮只造空壳，不写实现）")
    print("─" * 72)
    total_fn, total_shell = 0, 0
    for rel in EXPECTED:
        if rel in GROUND:
            continue
        p = REPO / rel
        if not p.exists():
            continue
        src = p.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:
            r.err(f"语法错误: {rel} → {exc}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            total_fn += 1
            body = [
                n for n in node.body
                if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                        and isinstance(n.value.value, str))
            ]
            if len(body) == 1 and isinstance(body[0], ast.Raise):
                seg = ast.get_source_segment(src, body[0]) or ""
                if SHELL_MARK.search(seg):
                    total_shell += 1
                    continue
            r.err(
                f"实现代码泄漏: {rel}::{node.name} "
                f"(第 {node.lineno} 行，函数体不是空壳)"
            )
            print(f"  ❌ {rel}::{node.name}  第 {node.lineno} 行有实现")

        # 禁止 pass / ... / return None 作为唯一函数体
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for n in node.body:
                    if isinstance(n, ast.Pass):
                        r.err(f"空壳禁用 pass: {rel}::{node.name}")
                    if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) \
                            and n.value.value is Ellipsis:
                        r.err(f"空壳禁用 ...: {rel}::{node.name}")

    r.stats["函数总数"] = total_fn
    r.stats["空壳函数"] = total_shell
    print(f"  函数 {total_shell}/{total_fn} 是规范空壳")
    if total_fn and total_shell != total_fn:
        r.warn(f"{total_fn - total_shell} 个函数未按空壳规范书写")


def check_layer_direction(r: Report) -> None:
    """依赖方向：这是「换算法不改核心」能否自动验证的关键。"""
    print()
    print("─" * 72)
    print("⑤ 依赖方向（core 不得知道算法的存在）")
    print("─" * 72)
    forbidden = {
        "harmonica_eval/core": ("algorithms", "host", "cockpit"),
        "harmonica_eval/algorithms": ("core", "host", "cockpit"),
        "harmonica_eval/cockpit": ("core", "algorithms", "host"),
        "harmonica_eval/contract.py": ("core", "host", "algorithms", "cockpit"),
        "harmonica_eval/profile.py": ("core", "host", "algorithms", "cockpit"),
    }
    violations = 0
    checked = 0
    for layer, bad in forbidden.items():
        base = REPO / layer
        files = sorted(base.rglob("*.py")) if base.is_dir() else [base]
        for f in files:
            if not f.exists():
                continue
            checked += 1
            src = f.read_text(encoding="utf-8")
            rel = f.relative_to(REPO)
            for node in ast.walk(ast.parse(src)):
                mods: list[str] = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods = [node.module]
                for m in mods:
                    tail = m.split(".")[-1]
                    if tail in bad or any(m.endswith(f".{b}") for b in bad):
                        r.err(f"依赖方向违规: {rel} import 了 {m}")
                        print(f"  ❌ {rel} → {m}")
                        violations += 1
    r.stats["依赖检查文件数"] = checked
    if not violations:
        print(f"  ✅ {checked} 个文件，全部符合依赖方向")
        print("     └ 「换算法不改核心」现在是可自动验证的结构事实")


def check_forbidden_on_host(r: Report) -> None:
    """CONTRACT-HOST-v1 上不得出现算法语义的方法名。"""
    print()
    print("─" * 72)
    print("⑥ Host 禁名单（编排权不得泄漏进 Core）")
    print("─" * 72)
    sys.path.insert(0, str(REPO))
    try:
        from harmonica_eval.contract import FORBIDDEN_OPERATIONS
    except Exception as exc:
        r.err(f"无法读取 FORBIDDEN_OPERATIONS: {exc}")
        return

    surface = REPO / "harmonica_eval/core"
    hits = 0
    for f in sorted(surface.rglob("*.py")):
        src = f.read_text(encoding="utf-8")
        for name in FORBIDDEN_OPERATIONS:
            if re.search(rf"\bdef\s+{re.escape(name)}\s*\(", src):
                r.err(f"禁名单违规: {f.relative_to(REPO)} 定义了 {name}()")
                print(f"  ❌ {f.relative_to(REPO)}::{name}()")
                hits += 1
    if not hits:
        print(f"  ✅ core/ 未出现禁名单中的 {len(FORBIDDEN_OPERATIONS)} 个方法")


def main() -> int:
    print("=" * 72)
    print("空壳验证 · verify_shell.py")
    print("=" * 72)
    r = Report()
    check_existence(r)
    check_imports(r)
    check_nameplate(r)
    check_shell_purity(r)
    check_layer_direction(r)
    check_forbidden_on_host(r)

    print()
    print("=" * 72)
    print("汇总")
    print("=" * 72)
    for k, v in r.stats.items():
        print(f"  {k}: {v}")
    print()
    if r.warnings:
        print(f"⚠ 警告 {len(r.warnings)} 条：")
        for w in r.warnings:
            print(f"   - {w}")
    if r.errors:
        print(f"❌ 违规 {len(r.errors)} 条：")
        for e in r.errors[:40]:
            print(f"   - {e}")
        if len(r.errors) > 40:
            print(f"   … 另有 {len(r.errors) - 40} 条")
        print()
        print("结论：未通过")
        return 1
    print("✅ 结论：通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
