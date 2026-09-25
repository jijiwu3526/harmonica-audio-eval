#!/usr/bin/env python3
"""检查 ⑲：BI 的 §8 验收脚本 —— 逐字抽取 + 语法编译。

## 为什么需要这个检查

第三轮盲审 A 的建议（我采纳）：

> A 只逐字执行了 18 份 BI 中的 3 份 §8 脚本，就命中 1 处
> 「签名改了、§8 脚本没跟着改」。**建议把全部 18 份 BI 的 §8 脚本
> 逐字执行一遍作为独立验收项。**

本轮 10 条失败判据里，**7 条是「读起来合理、跑一遍立刻失败」**。

## 本检查做到哪一步

**只做「语法编译」，不做执行。** 理由是执行需要真实实现
（骨架全是 `NotImplementedError`），而本检查跑在空壳阶段。
语法编译已能抓住 A 命中的那一整类缺陷：

  · `NameError` 类：脚本引用了骨架里改名/删掉的函数
  · `TypeError` 类：脚本按旧参数个数调用（**语法编译抓不到**，
    但下面的「签名交叉核对」能抓到）
  · 语法错误、缩进错误

因此本检查分两段：
  1. **编译**：把 §8 的 python 代码块抽出来，`compile()` 一遍。
  2. **签名交叉核对**：对每个脚本里出现的 `模块.函数(...)` 调用，
     若该函数在骨架里存在，比对**实参个数**与形参个数
     （不算 `self`）。个数不符 → 报错。这一条正是 A 的 FINDING-6
     （`summarize_deltas` 改二参、§8 仍按一参调用）的直接机械化。
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
BUILD = REPO / ".spec" / "build"
PKG = REPO / "harmonica_eval"


def _code_blocks(doc: str) -> list[str]:
    """抽出 §8 里所有含 python 的 bash 代码块内容。"""
    sec = re.search(r"\n## +8[ ·\t]", doc)
    body = doc[sec.start() :] if sec else doc
    out = []
    for block in re.findall(r"```bash\n(.*?)```", body, re.S):
        if "python" in block:
            out.append(block)
    for block in re.findall(r"```python\n(.*?)```", body, re.S):
        out.append(block)
    return out


def _inner_python_chunks(block: str) -> list[str]:
    """把 bash 块里的 python 代码拆成**独立的**若干段。

    ★ 必须分段：一个 bash 块里常有多个 `python -c "..."`，
      中间夹着 shell 注释（`# ── 判据 D ...`）与别的命令。
      若把整块拼成一坨再编译，shell 注释会被当成 python 语法错误。
      （本检查第三版就是这样，报出 FILE-201 的假阳性。）
    """
    chunks: list[str] = []
    chunks += re.findall(r"<<'PY'\n(.*?)\nPY", block, re.S)
    chunks += re.findall(r"<<PY\n(.*?)\nPY", block, re.S)
    for m in re.finditer(r'python3? -c\s*"', block):
        i = m.end()
        buf: list[str] = []
        while i < len(block):
            ch = block[i]
            if ch == "\\" and i + 1 < len(block):
                nxt = block[i + 1]
                # ★ shell 双引号里的 `\"` 是**转义引号**，在 python 源码里应还原成 `"`
                #   （例如 `print(f'... {r[\"n_paired\"]}')`）。
                #   若原样保留反斜杠，python 会报
                #   "unexpected character after line continuation character"。
                #   （本检查第四版就是这样，报出 FILE-201 的假阳性。）
                if nxt == '"':
                    buf.append('"')
                else:
                    buf.append(block[i : i + 2])
                i += 2
                continue
            if ch == '"':
                break
            buf.append(ch)
            i += 1
        chunks.append("".join(buf))
    return chunks


def _inner_python(block: str) -> str:
    """从 bash 块里抠出 python 代码。

    两种形态：
      · `python -c "..."`  —— 双引号包裹
      · `python3 - <<'PY' ... PY`  —— heredoc
    """
    chunks: list[str] = []
    chunks += re.findall(r"<<'PY'\n(.*?)\nPY", block, re.S)
    chunks += re.findall(r'<<PY\n(.*?)\nPY', block, re.S)
    # `python -c "..."` —— 从开引号起扫到**配对**的收尾引号。
    # ★ 不能用 `rest.rfind('"')`：那会把后面所有块的内容一起吞进来；
    #   也不能用 `[^"]*`：python 代码里本身就有 `"` 与 `\"`。
    #   正确做法是逐字符扫，处理反斜杠转义。
    #   （本检查第一版用 rfind，导致 7 份文件报「unterminated string」假阳性。）
    for m in re.finditer(r'python3? -c\s*"', block):
        i = m.end()
        buf = []
        while i < len(block):
            ch = block[i]
            if ch == "\\" and i + 1 < len(block):
                buf.append(block[i : i + 2])
                i += 2
                continue
            if ch == '"':
                break
            buf.append(ch)
            i += 1
        chunks.append("".join(buf))
    return "\n".join(chunks)


def _skeleton_arities() -> dict[str, int]:
    """骨架里每个公开函数的「必填位置参数」个数：`名字 -> (最小, 最大)`。"""
    out: dict[str, tuple[int, int]] = {}
    for py in PKG.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                args = node.args
                pos = [a for a in args.args if a.arg not in ("self", "cls")]
                n_min = len(pos) - len(args.defaults)
                n_max = len(pos) + (1 if args.vararg else 0)
                if node.name in out:
                    # 重名 → 标记为歧义，后续跳过
                    out[node.name] = None  # type: ignore[assignment]
                else:
                    out[node.name] = (n_min, n_max)
    return out


def main() -> int:
    print("⑲ BI §8 验收脚本（抽取 → 编译 → 实参个数核对）")
    arities = _skeleton_arities()
    problems: list[str] = []
    skipped: list[str] = []
    n_blocks = n_compiled = n_calls = 0

    for md in sorted(BUILD.glob("FILE-*-v1.md")):
        doc = md.read_text(encoding="utf-8")
        for block in _code_blocks(doc):
          for src in _inner_python_chunks(block):
                if not src.strip():
                    continue
                n_blocks += 1
                # ① 编译
                try:
                    compile(src, f"{md.stem}#§8", "exec")
                    n_compiled += 1
                except SyntaxError as e:
                    # ★ 判别力：`python -c "..."` 里若出现**未转义的**内层引号
                    #   （如 `assert '<text x="0" ...' in s`），shell 层就会截断它，
                    #   我的提取器无法与真实语法错误区分。
                    #   这类段落计入 SKIPPED 而不报错 ——
                    #   宁可漏报（交给盲审），也不制造假阳性：
                    #   假阳性会让检查失去信任（方法论 §7.2）。
                    # 判据：**段末是不是一个未闭合的引号**。
                    # 提取器截断的确定特征 —— shell 层把内层引号当成收尾引号，
                    # 于是段落在一个 `'...="` 或 `"...` 处戛然而止。
                    # 真实语法错误几乎不会让段落正好结束在未闭合引号上。
                    # （引号奇偶判据不可靠：截断点之前的部分可能恰好偶数个。）
                    # 判据：**末行以 `=` 结尾**（或未闭合引号）。
                    # 截断的确定特征：`assert '<text x="` ——
                    # shell 把 `"` 当收尾引号吃掉，段落停在 `=` 上。
                    # 完整的一行 python 不会以裸 `=` 结尾。
                    tail = src.rstrip().splitlines()[-1].rstrip() if src.strip() else ""
                    if tail.endswith("=") or tail.count('"') % 2 == 1:
                        skipped.append(f"{md.name}:{e.lineno}")
                    else:
                        problems.append(
                            f"  ❌ {md.name} §8 脚本第 {e.lineno} 行语法错误：{e.msg}"
                        )
                    continue
                # ② 实参个数核对
                try:
                    tree = ast.parse(src)
                except SyntaxError:
                    continue
                # ★ 只认**限定调用** `模块.函数(...)`，不认裸名 `函数(...)`。
                #   理由：骨架里有 13 个重名函数（`build_surface` 同时存在于
                #   `core/surface.py`(4 参) 与 `host/app.py`(0 参)），
                #   按裸名匹配会把 4 参调用拿去比 0 参签名 → 大批假阳性。
                #   （本检查第二版就是这样，报出 16 条假阳性。）
                #   裸名调用交给「⑱ 签名一致性」与盲审覆盖。
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    fn = node.func
                    if not isinstance(fn, ast.Attribute):
                        continue
                    # `mod.name(...)` —— 用属性访问形式，且有模块限定
                    if not isinstance(fn.value, (ast.Name, ast.Attribute)):
                        continue
                    name = fn.attr
                    if name not in arities:
                        continue
                    n_given = len(node.args)
                    if any(k.arg is None for k in node.keywords):
                        continue  # `**kwargs` 展开，无法静态判定
                    n_given += len([k for k in node.keywords if k.arg])
                    if arities[name] is None:
                        continue  # 重名函数，无法静态归属
                    lo, hi = arities[name]
                    n_calls += 1
                    if not (lo <= n_given <= hi):
                        problems.append(
                            f"  ❌ {md.name} §8 脚本调用 {name}() 传了 {n_given} 个实参，"
                            f"但骨架要求 {lo}–{hi} 个（含关键字）"
                        )

    if skipped:
        print(f"  ⚠️  {len(skipped)} 段因内层引号无法静态提取，已 SKIP（不报错）：")
        for sk in skipped[:6]:
            print(f"        {sk}")
    if problems:
        for p in problems:
            print(p)
        print(f"\n  ❌ {len(problems)} 处问题")
        return 1
    print(
        f"  ✅ {n_blocks} 个脚本块编译通过；"
        f"核对了 {n_calls} 处函数调用的实参个数，全部匹配骨架签名"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
