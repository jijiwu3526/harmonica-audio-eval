#!/usr/bin/env python3
"""检查 ⑰：交叉引用完整性 —— 每个 `FILE-NNN §X.Y` 都指向真实存在的节。

## 为什么需要这个检查

盲审 probe 14 发现 `FILE-002:305` 写「见 FILE-401 §4.x」——
`§4.x` **不是可查的节号**，FILE-401 里根本没有这个节。
这类「指向空气的引用」有两种危害：

1. 实现者按图索骥找不到，只能自己猜 —— 而猜出来的口径**无法被审查**。
2. 它看起来像是"已有依据"，于是**读者不再深究**。
   这比"没写"更糟：没写至少是诚实的缺口。

本检查是**零误报**的：节号存在与否是可机械判定的，
不像「可达性」那样需要数据流推断。

## 口径

- 扫描 `.spec/build/FILE-*.md` 与 `SPEC.md` / `COMPONENTS.md`。
- 抽取所有形如 `FILE-1xx §N` / `FILE-1xx §N.M` / `FILE-2xx §N.M.K` 的引用。
- 目标文件的**真实节标题**用 `^#+ +N(.M)*` 抽取。
- 引用不在真实节集合里 → 报错。
- 允许 `§N.M` 匹配到 `§N.M.K`（引用粗一级是合法的，例如
  「见 FILE-401 §4.7」而实际标题是 `### 4.7 xxx`；也允许反过来引用小节）。
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent

# 被引用的目标文件 → 实际路径
TARGETS: dict[str, pathlib.Path] = {
    "SPEC.md": REPO / "SPEC.md",
    "COMPONENTS.md": REPO / "COMPONENTS.md",
}
for _f in sorted((REPO / ".spec" / "build").glob("FILE-*-v1.md")):
    TARGETS[_f.stem.split("-v1")[0]] = _f

# 源文件：所有 BI + 顶层规格
SOURCES = sorted((REPO / ".spec" / "build").glob("FILE-*-v1.md")) + [
    REPO / "SPEC.md",
    REPO / "COMPONENTS.md",
]


def sections_of(path: pathlib.Path) -> set[str]:
    """抽真实节号集合。`## 5 · 失败语义` → {'5'}；`### 4.7 x` → {'4.7'}。"""
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        # ★ 两种节号写法都要认：
        #   `## 4 · 标题`     —— FILE-1xx / FILE-2xx 等
        #   `### §4.1 \`sym\`` —— FILE-0xx（contract/profile）用 § 前缀
        # 本检查第一版只认第一种，于是把 FILE-004 的 `### §4.1` 当成不存在，
        # 误报 FILE-002:162 的合法引用为「指向空气」。
        m = re.match(r"^#+ +(?:§)?(\d+(?:\.\d+)*)", line)
        if m:
            out.add(m.group(1))
    return out


# `FILE-401 §4.7` / `FILE-202-v1.md §4.4` / `FILE-002:305` 之后紧跟的 §
REF = re.compile(r"(FILE-\d{3})(?:-v1)?(?:\.md)?[^\n§]{0,12}?§(\d+(?:\.\d+)*)")


def main() -> int:
    print("⑰ 交叉引用完整性（每个 FILE-NNN §X.Y 都指向真实节）")
    secs = {name: sections_of(p) for name, p in TARGETS.items() if p.exists()}
    problems: list[str] = list(check_duplicate_sections())
    checked = 0

    for src in SOURCES:
        if not src.exists():
            continue
        for lineno, line in enumerate(
            src.read_text(encoding="utf-8").splitlines(), 1
        ):
            for m in REF.finditer(line):
                target, sec = m.group(1), m.group(2)
                if target not in secs:
                    continue
                checked += 1
                real = secs[target]
                # 精确命中，或引用了某真实节的前缀（粗一级引用）
                ok = sec in real or any(
                    r.startswith(sec + ".") for r in real
                )
                if not ok:
                    problems.append(
                        f"  ❌ {src.name}:{lineno} 引用 `{target} §{sec}`，"
                        f"但该文件没有这个节"
                        f"（真实节号示例：{sorted(real)[:8]}…）"
                    )

    if problems:
        for p in problems:
            print(p)
        print(f"\n  ❌ {len(problems)} 处交叉引用缺陷（悬空引用 / 重号节）")
        return 1
    print(f"  ✅ 检查了 {checked} 处跨文件节引用，全部命中真实节")
    return 0


def check_duplicate_sections() -> list[str]:
    """同一份 BI 里不得有重号小节。

    ★ 为什么需要：第三轮盲审 A 的 FINDING-12 —— FILE-104 里
    `### 4.1` 出现两次（第二次是 §4.8 的位置），两次标题逐字相同，
    于是「见 §4.1」无法判定指向。这类缺陷**不影响阅读**，
    只让交叉引用失效，所以人工复核容易漏掉，必须机械化。
    """
    problems: list[str] = []
    for md in sorted((REPO / ".spec" / "build").glob("FILE-*-v1.md")):
        seen: dict[str, list[int]] = {}
        for i, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            m = re.match(r"^(#{2,4}) +(?:§)?(\d+(?:\.\d+)*)\b", line)
            if not m:
                continue
            seen.setdefault(m.group(2), []).append(i)
        for sec, lines in seen.items():
            if len(lines) > 1:
                problems.append(f"{md.name} 节号 §{sec} 重复出现在行 {lines}")
    return problems

if __name__ == "__main__":
    sys.exit(main())





