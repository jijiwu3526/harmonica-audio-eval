#!/usr/bin/env python3
"""检查 ``_scratch/harmonica_eval`` 是否仍是主包的陈旧副本。

这个检查刻意不 ``import`` 任何一个 ``harmonica_eval``：它必须在参考实现
可能无法导入时仍然能工作。它只读取文本、用 :mod:`ast` 做静态分析，并把
差异变成非零退出码。

用法::

    python3 tools/check_scratch_freshness.py

退出码：0 表示没有检测到漂移；1 表示副本缺失/陈旧/无法解析；2 表示用法或
检查器自身出错。
"""

from __future__ import annotations

import ast
import difflib
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MAIN_CONTRACT = REPO_ROOT / "harmonica_eval" / "contract.py"
SCRATCH_CONTRACT = REPO_ROOT / "_scratch" / "harmonica_eval" / "contract.py"

# 从主包 contract.py 的顶层类定义自动得到契约类型，而不是维护一份容易
# 再次漂移的硬编码名单。这样未来新增 InputRequirement、PluginSpec 或其他
# 公开契约类时，检查器会立即逐个点名报告。


@dataclass(frozen=True)
class ContractInfo:
    """从 ``contract.py`` 提取出的静态事实。"""

    path: Path
    lines: list[str]
    contract_types: set[str]
    top_level_names: set[str]
    parse_error: str | None = None


def read_contract(path: Path) -> ContractInfo:
    """读取并静态分析契约文件；不执行其中的 Python。"""

    if not path.is_file():
        return ContractInfo(
            path=path,
            lines=[],
            contract_types=set(),
            top_level_names=set(),
            parse_error=f"文件不存在：{path}",
        )

    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        return ContractInfo(
            path=path,
            lines=[],
            contract_types=set(),
            top_level_names=set(),
            parse_error=f"无法读取/解析 {path}：{exc}",
        )

    top_level_types = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }
    top_level_names: set[str] = set(top_level_types)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_level_names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            top_level_names.update(
                target.id for target in targets if isinstance(target, ast.Name)
            )

    return ContractInfo(
        path=path,
        lines=text.splitlines(),
        contract_types=top_level_types,
        top_level_names=top_level_names,
    )


def diff_line_counts(main_lines: list[str], scratch_lines: list[str]) -> tuple[int, int, int]:
    """返回 (差异行总数, 仅主包行数, 仅 scratch 行数)。

    这里使用标准库的 ``difflib``，不调用外部 ``diff`` 命令；因此检查器在
    Windows、CI 和只读审查环境中也能执行。差异总数按统一 diff 中实际出现
    的删除行与新增行相加计算。
    """

    additions = deletions = 0
    matcher = difflib.SequenceMatcher(a=main_lines, b=scratch_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            deletions += i2 - i1
            additions += j2 - j1
        elif tag == "delete":
            deletions += i2 - i1
        elif tag == "insert":
            additions += j2 - j1
    return additions + deletions, deletions, additions


def print_symbol_report(main: ContractInfo, scratch: ContractInfo) -> None:
    """打印主包有而参考副本没有的公开契约类型。"""

    missing = sorted(main.contract_types - scratch.contract_types)
    extra = sorted(scratch.contract_types - main.contract_types)
    print("\n契约类型（主包 → scratch）：")
    print(f"  主包发现：{len(main.contract_types)}")
    print(f"  scratch 发现：{len(scratch.contract_types)}")
    if missing:
        print("  ★ 主包有、scratch 缺少（这是陈旧的直接证据）：")
        for name in missing:
            print(f"    - {name}")
    else:
        print("  ★ 主包有、scratch 缺少：无")
    if extra:
        print("  scratch 有、主包没有（需人工确认是否参考实现扩展）：")
        for name in extra:
            print(f"    + {name}")
    else:
        print("  scratch 有、主包没有：无")


def main() -> int:
    print("=" * 72)
    print("scratch freshness 检查 · 只读静态分析，不 import harmonica_eval")
    print("=" * 72)
    print(f"主包契约：{MAIN_CONTRACT.relative_to(REPO_ROOT)}")
    print(f"参考副本：{SCRATCH_CONTRACT.relative_to(REPO_ROOT)}")

    main_info = read_contract(MAIN_CONTRACT)
    scratch_info = read_contract(SCRATCH_CONTRACT)
    if main_info.parse_error or scratch_info.parse_error:
        for info in (main_info, scratch_info):
            if info.parse_error:
                print(f"❌ {info.parse_error}")
        return 1

    total, removed, added = diff_line_counts(main_info.lines, scratch_info.lines)
    print("\ncontract.py 文本差异：")
    print(f"  主包行数：{len(main_info.lines)}")
    print(f"  scratch 行数：{len(scratch_info.lines)}")
    print(f"  ★ 差异行数：{total}（主包有 {removed} 行，scratch 有 {added} 行）")

    print_symbol_report(main_info, scratch_info)

    missing_types = sorted(main_info.contract_types - scratch_info.contract_types)
    if total or missing_types:
        print("\n❌ FAIL：scratch 与主包存在契约漂移，不能用 scratch 证明主包行为。")
        print("   正确用途：主包=契约/架构；scratch=参考实现端到端运行。")
        return 1

    print("\n✅ PASS：contract.py 无文本漂移，主包契约类型均已存在于 scratch。")
    print("   注意：这只证明 contract.py 这一层；不证明 scratch 的行为实现等同主包。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as exc:
        print(f"❌ 检查器自身失败：{exc}", file=sys.stderr)
        raise SystemExit(2)
