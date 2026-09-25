#!/usr/bin/env python3
"""交付物洁净度检查：拒绝把智能体脚手架泄漏进仓库。

★ 起因（本轮实测事故）：子代理在写 `.spec/build/FILE-203-v1.md` 时，
把 `</think>DONE ...</tool_call>` 这类**智能体控制标记**写进了文档末尾。
文件仍然"看起来正常"（有内容、行数合理），但末行是垃圾。

这类污染的危险性在于它**不会让任何现有检查失败**：
- `check_bi_scripts` 只看代码块能否编译 → 纯文本垃圾不影响
- `check_counts` 只看数量声明 → 垃圾行里没有数量
- `verify_shell` 只看源码骨架 → 文档不在它的范围

所以必须有一条**专门**盯洁净度的检查。

本检查判定为污染的标记（任一命中即失败）：
- `<think>` / `</think>` / `<tool_call>` / `</tool_call>`
- `tool_call`（零宽字符变体，真实事故里就是这个形态）
- `DONE ` 单独成行（智能体完成标记，不该出现在交付物里）
- `I need to` / `Let me` 开头的英文思考体（可选，见下）
- `作为AI` / `作为一个AI` 等模型自指

扫描范围：所有 `.md` 与 `.py`，**排除** `.git/` 与 `_scratch/`
（`_scratch` 是参考实现快照，保留原始事故痕迹是有价值的考古证据，
但它也不该被本检查阻塞；`_snapshot*` 目录同理）。
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ★ 零宽 / 方向控制 / BOM 字符。真实事故里混入了 U+200B（零宽空格），
# 用肉眼和普通 grep 都看不见。注意：早先用 `re.compile("")` 来找它，
# 空模式在每个位置都匹配，导致对全仓报出 190 万处"污染" ——
# 那是**检查本身的 bug**，不是仓库脏。已改为按码位逐字符判定。
INVISIBLE = frozenset("‌‍⁠﻿")

# 不可见字符用一个显式字符类（单个 alternation），确保不会退化成空模式。
INVISIBLE_RX = re.compile("[‌‍⁠﻿]")

MARKERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("think 标签", re.compile(r"</?think>")),
    ("tool_call 标签", re.compile(r"</?tool_call>")),
    ("零宽/方向控制字符", INVISIBLE_RX),
    ("智能体完成标记", re.compile(r"^\s*DONE\s+\S", re.MULTILINE)),
    ("模型自指", re.compile(r"作为(?:一个)?AI|as an AI\b", re.IGNORECASE)),
    ("未闭合代码栅栏残留", re.compile(r"(?:tool|function)_call", re.MULTILINE)),
)

# 这些目录保留原始事故痕迹（考古价值），不纳入扫描。
SKIP_DIR_PARTS = {
    ".git",
    "_scratch",
    "__pycache__",
    "node_modules",
    "_snapshot",
    "_snapshot2",
}


def iter_files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for pat in ("*.md", "*.py"):
        for p in ROOT.rglob(pat):
            if any(part in SKIP_DIR_PARTS for part in p.relative_to(ROOT).parts):
                continue
            out.append(p)
    return sorted(out)


def main() -> int:
    files = iter_files()
    findings: list[str] = []
    for p in files:
        # ★ 排除本文件自身：它按定义包含所有被搜索的标记字面量
        # （以及用它们举例的说明文字）。不排除就会把自己报成污染。
        if p.resolve() == pathlib.Path(__file__).resolve():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = p.relative_to(ROOT)
        for name, rx in MARKERS:
            for m in rx.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                findings.append(f"  ❌ {rel}:{line_no} {name}：{m.group(0)[:40]!r}")

    print("交付物洁净度检查（智能体脚手架泄漏）")
    print("=" * 72)
    print(f"扫描文件：{len(files)} 个（.md + .py，排除 {', '.join(sorted(SKIP_DIR_PARTS))}）")
    print()
    if findings:
        print(f"发现 {len(findings)} 处污染：")
        print("\n".join(findings))
        print()
        print("  ★ 处置：这些是智能体控制标记泄漏进了交付物，")
        print("    任何现有检查都不会捕获它们，必须手工清除后复跑。")
        return 1

    print(f"  ✅ 洁净：{len(files)} 个文件均无智能体脚手架泄漏")
    return 0


if __name__ == "__main__":
    sys.exit(main())
