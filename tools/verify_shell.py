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
    """CONTRACT-HOST-v1 上不得出现算法语义的方法名。

    ★ 检查范围是**类方法**，不是模块级函数。

    为什么（这是本工具第一版的缺陷，实测暴露）：
        禁名单说的是「**CONTRACT-HOST-v1 上**绝不允许出现的方法名」——
        它约束的是 Core 暴露给 C1 的**门面**。
        而 `core/align.py` 里的模块级函数 `align()` 是 Core 的**内部实现**，
        完全合法：C1 不该调用它，但 Core 自己必须能对齐。

        第一版用 `def align(` 全局 grep，于是把合法的内部函数也判成违规 ——
        **检查工具的假阳性会让真正的违规淹没在噪声里**，比不检查更糟。
    """
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

    # 只在「实现 HostContract 的类」里找禁名单方法
    hits = 0
    classes_checked = 0
    for f in sorted((REPO / "harmonica_eval/core").rglob("*.py")):
        src = f.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            bases = [ast.unparse(b) for b in cls.bases]
            # 门面类：显式继承 HostContract 的类
            is_host_impl = any("HostContract" in b for b in bases)
            classes_checked += 1
            for item in cls.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name in FORBIDDEN_OPERATIONS:
                    tag = "Host 契约实现" if is_host_impl else f"类 {cls.name}"
                    r.err(
                        f"禁名单违规: {f.relative_to(REPO)}::{cls.name}.{item.name}() "
                        f"（{tag}）"
                    )
                    print(f"  ❌ {f.relative_to(REPO)}::{cls.name}.{item.name}()")
                    hits += 1

    print(f"  检查了 {classes_checked} 个类的方法集合")
    if not hits:
        print(f"  ✅ 未出现禁名单中的 {len(FORBIDDEN_OPERATIONS)} 个方法名")
        print("     （模块级内部函数不计入 —— 它们不是 C1 能看到的面）")


def check_no_shadowing(r: Report) -> None:
    """⑦ 同名重复定义检测。

    ★ 这条检查是被一次**真实事故**逼出来的：
    我在修 §20 盲审缺陷时，给 contract.py 追加了一段代码，
    末尾误留了一个 `class SessionState(str, Enum):` 头。
    Python **不报错** —— 后一个定义静默**遮蔽**了前一个（真）定义，
    import 照常成功，而 `SessionState` 变成了一个空枚举。

    这正是本项目反复出现的同一类缺陷：**不报错，只静默算错**。
    与 FIELD_LAYOUTS、hop_length、端口对称性属于同一族，
    故用机械检查兜住。

    检查范围：同一文件内，模块级 class / def 名是否重复。
    """
    print()
    print("─" * 72)
    print("⑦ 重复定义（静默遮蔽检测）")
    print("─" * 72)

    hits: list[str] = []
    checked = 0

    for rel in EXPECTED:
        path = REPO / rel
        if not path.exists():
            continue
        checked += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        seen: dict[str, int] = {}
        for node in tree.body:  # 只看模块级
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in seen:
                    hits.append(
                        f"{rel}: '{node.name}' 在第 {seen[node.name]} 行与 "
                        f"第 {node.lineno} 行重复定义"
                        "（后者会静默遮蔽前者，import 不报错）"
                    )
                else:
                    seen[node.name] = node.lineno

    for h in hits:
        print(f"  ❌ {h}")
        r.err(h)

    print(f"  检查了 {checked} 个文件的模块级定义")
    if not hits:
        print("  ✅ 无重复定义（不存在静默遮蔽）")


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
    check_no_shadowing(r)

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
