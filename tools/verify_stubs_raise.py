#!/usr/bin/env python3
"""verify_stubs_raise.py —— 验证空壳的"调用必炸"断言。

空壳的核心价值是：**被调用时一定抛错**。
若某个空壳函数静默返回 None，实现者可能误以为它已可用，
或把 None 当成合法返回值继续往下写 —— 这类错误极难发现。

用法：python3 tools/verify_stubs_raise.py
退出码：0 通过 / 1 有失效空壳
无随机性、无副作用（只读；调用空壳不产生任何状态）。

── 三类豁免（都有明确理由，不是放水）──────────────────────────
1. Protocol 方法    —— `contract.py` 里的 HostContract / AlgorithmDataContract /
                       UiProjectionPort 是**类型声明**，函数体用 `...` 是正确写法。
                       Protocol 不可实例化，永远不会被"调用"。
2. 冻结地基的实现    —— `contract.py` / `profile.py` 里少量函数**已经实现**
                       （如 AudioFormat.__post_init__ 的校验、
                        profile.assert_profile_integrity 的自检）。
                       它们不是空壳，本就不该抛 NotImplementedError。
3. __init__.py 等   —— 不定义可调用符号的文件自然无空壳。
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent

# 豁免 1：Protocol 声明（类型层，无运行时实体）
PROTOCOL_CLASSES = {"HostContract", "AlgorithmDataContract", "UiProjectionPort"}

# 豁免 2：已实现的冻结地基（非空壳）
GROUND_FILES = {"harmonica_eval/contract.py", "harmonica_eval/profile.py"}


def collect(path: pathlib.Path) -> tuple[list[str], list[str], list[str]]:
    """返回 (protocol_methods, ground_functions, shell_functions)。"""
    src = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(REPO))
    tree = ast.parse(src)
    protos, ground, shells = [], [], []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            is_proto = node.name in PROTOCOL_CLASSES
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name.startswith("__") and item.name.endswith("__"):
                    continue
                tag = f"{node.name}::{item.name}"
                (protos if is_proto else shells).append(tag)
        elif isinstance(node, ast.Module):
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name.startswith("__") and item.name.endswith("__"):
                    continue
                (ground if rel in GROUND_FILES else shells).append(f"<module>::{item.name}")

    return protos, ground, shells


def main() -> int:
    print("=" * 72)
    print('空壳"调用必炸"验证 · verify_stubs_raise.py')
    print("=" * 72)

    sys.path.insert(0, str(REPO))
    total_proto = total_ground = total_shell = ok = 0
    problems: list[str] = []

    for f in sorted((REPO / "harmonica_eval").rglob("*.py")):
        mod_name = str(f.relative_to(REPO).with_suffix("")).replace("/", ".")
        if mod_name.endswith(".__init__"):
            mod_name = mod_name[:-9]
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:
            problems.append(f"{mod_name}: import 失败 {exc}")
            continue

        protos, ground, shells = collect(f)
        total_proto += len(protos)
        total_ground += len(ground)
        total_shell += len(shells)

        for tag in shells:
            cls_name, _, fn_name = tag.partition("::")
            holder = mod if cls_name == "<module>" else getattr(mod, cls_name, None)
            if holder is None:
                problems.append(f"{f.relative_to(REPO)}::{tag} 符号不存在")
                continue
            obj = getattr(holder, fn_name, None)
            if obj is None:
                problems.append(f"{f.relative_to(REPO)}::{tag} 属性不存在")
                continue

            params = list(inspect.signature(obj).parameters.values())
            if cls_name != "<module>" and params and params[0].name in ("self", "cls"):
                # ★ 工具自身的一个 bug（实测暴露并已修）：
                # 通过类取到的是**未绑定函数**，其签名包含 self。
                # 若既在签名里算了 self、又显式再传一次 self，
                # 结果是 TypeError 而不是 NotImplementedError —— 纯假阳性。
                # 第一版因此报了 16 条"空壳失效"，全是它自己造成的。
                params = params[1:]
            args = [
                None for p in params
                if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD) and p.default is p.empty
            ]
            try:
                if cls_name != "<module>":
                    obj(None, *args)
                else:
                    obj(*args)
                problems.append(f"{f.relative_to(REPO)}::{tag} 未抛错 → 空壳失效")
            except NotImplementedError as exc:
                if "SHELL: FILE-" in str(exc):
                    ok += 1
                else:
                    problems.append(f"{f.relative_to(REPO)}::{tag} 抛错但缺 FILE-ID")
            except Exception as exc:
                problems.append(
                    f"{f.relative_to(REPO)}::{tag} 抛了 {type(exc).__name__}: "
                    f"{str(exc)[:60]}（应为 NotImplementedError）"
                )

    print(f"\n  豁免 1 Protocol 方法（类型声明，用 ... 正确）: {total_proto}")
    print(f"  豁免 2 已实现的地基函数                      : {total_ground}")
    print(f"  空壳函数                                     : {total_shell}")
    print(f"  其中正确抛 NotImplementedError 且带 FILE-ID  : {ok}")

    print()
    if problems:
        print(f"❌ {len(problems)} 条问题：")
        for p in problems[:30]:
            print("   -", p)
        return 1
    if total_shell and ok != total_shell:
        print(f"❌ 空壳 {total_shell} 个，仅 {ok} 个通过断言")
        return 1
    print("✅ 全部空壳的『调用必炸』断言成立")
    print("   → 它们不可能被误认为已实现，也不会静默返回 None")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
