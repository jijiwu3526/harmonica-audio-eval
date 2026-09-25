#!/usr/bin/env python3
"""检查 ⑳：把 18 份 BI 的 §8 验收脚本**真的跑一遍**。

## 为什么需要这个检查

第三轮盲审 A 的系统性建议（我采纳）：

> A 只逐字执行了 18 份 BI 中的 3 份 §8 脚本，就命中 1 处
> 「签名改了、§8 脚本没跟着改」。**建议把全部 18 份 BI 的 §8 脚本
> 逐字执行一遍作为独立验收项。**

审查者 B 的另一条：

> 本轮 10 条失败的判据里，有 **7 条是「读起来完全合理、跑一遍立刻失败」**。
> 若 §8 的脚本在冻结前被执行过一次，这 7 条都不会进入 `.spec/build/`。

⑲ 只做「编译 + 实参个数」，抓不到"能编译但断言为假"。本检查补上执行。

## 状态

  PASS        —— 成功抽取、compile() 通过、脚本退出码 0
  SYNTAX_FAIL —— 成功抽取，但脚本自身无法 compile()
  EXTRACT_FAIL—— Markdown/Bash 边界不完整，无法得到完整源码
  EXEC_FAIL   —— compile() 通过，但脚本退出码非 0（打印尾部 stderr）

★ `SYNTAX_FAIL` 与 `EXTRACT_FAIL` 严格分开：前者是脚本自身语法坏，
  后者是工具没切开边界；两者都不得伪装成执行失败。

## 怎么执行

本检查从**仓库根目录**启动每个抽取出的 Python 脚本，因此被测的
`harmonica_eval/` 始终是工作区当前代码，而不是 `_scratch/` 中的参考副本。
这是审查阶段需要的语义：SHELL 的 `NotImplementedError` 必须暴露为
`EXEC_FAIL`，不能拿旧参考实现把失败遮住。

`_scratch/harmonica_eval/` 仍原样保留，供其它审计/理想行为对照使用；本检查
既不写入它，也不把它加入脚本的导入路径。脚本所需音频仍可经 `REF` / `PRA`
环境变量显式注入。
"""

from __future__ import annotations

import os
import pathlib
import re
import signal
import subprocess
import sys
from dataclasses import dataclass

REPO = pathlib.Path(__file__).resolve().parent.parent
BUILD = REPO / ".spec" / "build"
DATASET = REPO / "harmonica_mvp_dataset" / "01_奇异恩典"

_SECTION_RE = re.compile(r"^## +§?8(?:[ ·\t].*)?$", re.M)
_NEXT_SECTION_RE = re.compile(r"^## +§?9(?:[ ·\t].*)?$", re.M)
_FENCE_RE = re.compile(r"^```([^\n]*)$\n(.*?)^```[ \t]*$", re.M | re.S)
_C_COMMAND_RE = re.compile(r"(?:^|[;&|]\s*)python3?\s+-c\s+\"")
_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
# 跨行 python -c 的外层结束形式：独占一行（允许缩进），或紧贴行尾的
# print('...')" / ...)"。不能把源码内普通字符串里的 " 当成结束符。
_C_TERMINATOR_RE = re.compile(r"(?:^[\t ]*\"|[\)\]\}][\t ]*\")[\t ]*$")


@dataclass
class Script:
    index: int
    source: str
    line: int
    error: str = ""


def _section_8(doc: str) -> str:
    """返回 §8 正文；在 §9 前截断，兼容 ``## 8`` 与 ``## §8``。"""
    start = _SECTION_RE.search(doc)
    if not start:
        return ""
    body = doc[start.end() :]
    end = _NEXT_SECTION_RE.search(body)
    return body[: end.start()] if end else body


def _fenced_bash_blocks(doc: str) -> list[tuple[int, str]]:
    """返回 §8 中 bash 围栏的 [(源码首行文档行号, 内容), ...]。"""
    start = _SECTION_RE.search(doc)
    if not start:
        return []
    body = _section_8(doc)
    out: list[tuple[int, str]] = []
    for match in _FENCE_RE.finditer(body):
        if match.group(1).strip().lower() != "bash":
            continue
        line = doc.count("\n", 0, start.end() + match.start(2)) + 1
        out.append((line, match.group(2)))
    return out


def _looks_like_terminator(line: str, delimiter: str) -> bool:
    """带缩进的 heredoc 终止行也可带 ``| tee`` 等管道后缀。"""
    stripped = line.strip()
    if not stripped or any(char in stripped for char in ";`$"):
        return False
    parts = stripped.split(None, 1)
    return bool(parts) and parts[0] == delimiter


def _take_heredoc(
    lines: list[str], i: int, start_line: int, chunks: list[Script]
) -> int:
    """从 heredoc 命令行开始抽一段源码；返回下一条待扫描行。"""
    heredoc = _HEREDOC_RE.search(lines[i])
    if not heredoc:
        return i + 1
    delimiter = heredoc.group(2)
    body: list[str] = []
    cursor = i + 1
    while (
        cursor < len(lines)
        and lines[cursor].rstrip("\r\n") != delimiter
        and not _looks_like_terminator(lines[cursor], delimiter)
    ):
        body.append(lines[cursor])
        cursor += 1
    if cursor == len(lines):
        chunks.append(
            Script(
                index=len(chunks) + 1,
                source="",
                line=start_line + i + 1,
                error=f"heredoc {delimiter!r} 缺少结束标记",
            )
        )
        return cursor
    source = "".join(body).rstrip("\r\n")
    if source.strip():
        chunks.append(
            Script(index=len(chunks) + 1, source=source, line=start_line + i + 1)
        )
    return cursor + 1


def _take_c_command(
    lines: list[str], i: int, start_line: int, chunks: list[Script]
) -> int:
    """从 python -c 命令行开始抽一段源码；返回下一条待扫描行。"""
    match = _C_COMMAND_RE.search(lines[i])
    if not match:
        return i + 1
    content = lines[i][match.end() :].rstrip("\r\n")
    closing = content.rfind('"')

    # shell 的反斜杠续行：python -c "第一行；\
    # 第二行" 传给 Python 前会接成一行。FILE-103 使用此形态。
    if closing < 0 and content.endswith("\\"):
        continued = [content[:-1]]
        cursor = i + 1
        while cursor < len(lines):
            current = lines[cursor].rstrip("\r\n")
            closing = current.rfind('"')
            if closing >= 0:
                continued.append(current[:closing])
                break
            continued.append(current[:-1] if current.endswith("\\") else current)
            cursor += 1
        source = "\n".join(continued).replace('\\"', '"')
        if closing >= 0 and source.strip():
            chunks.append(
                Script(
                    index=len(chunks) + 1,
                    source=source,
                    line=start_line + i + 1,
                )
            )
            return cursor + 1
        chunks.append(
            Script(
                index=len(chunks) + 1,
                source="",
                line=start_line + i + 1,
                error="python -c 的反斜杠续行缺少外层结束引号",
            )
        )
        return cursor

    # 单行命令：最后一个双引号是外层结束符；shell 转义的 \" 还原为 "。
    if content.strip() and closing >= 0:
        source = content[:closing].replace('\\"', '"')
        if source.strip():
            chunks.append(
                Script(
                    index=len(chunks) + 1,
                    source=source,
                    line=start_line + i + 1,
                )
            )
        return i + 1

    # ★ 跨行命令：结束边界取行边界，不逐字符追下一个 "。
    #   Python 源码可合法含 HTML/JSON 双引号（FILE-401 的 '<text x="0"...'）。
    body: list[str] = []
    cursor = i + 1
    while cursor < len(lines) and not _C_TERMINATOR_RE.search(lines[cursor]):
        body.append(lines[cursor].rstrip("\r\n"))
        cursor += 1
    if cursor == len(lines):
        chunks.append(
            Script(
                index=len(chunks) + 1,
                source="",
                line=start_line + i + 1,
                error="python -c 缺少独占一行的外层结束引号",
            )
        )
        return cursor
    source = "\n".join(body)
    # 跨行 shell 双引号里，\" 仍是 shell 转义；Python 源码收到的是普通 "。
    source = source.replace('\\"', '"')
    if source.strip():
        chunks.append(
            Script(index=len(chunks) + 1, source=source, line=start_line + i + 1)
        )
    return cursor + 1


def _python_chunks(block: str, start_line: int) -> list[Script]:
    """按文档顺序抽一个 bash 围栏中的 heredoc 与 ``python -c``。

    ★ 二者可以混在同一围栏（FILE-101 / 104 / 201 均如此），必须同一遍扫描。
    """
    lines = block.splitlines(keepends=True)
    chunks: list[Script] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].lstrip()
        if stripped.startswith("#"):
            i += 1
            continue
        if "<<" in lines[i] and "python" in lines[i].lower():
            i = _take_heredoc(lines, i, start_line, chunks)
        else:
            i = _take_c_command(lines, i, start_line, chunks)
    return chunks


def _inner_python_chunks(block: str) -> list[str]:
    """兼容旧调用：返回成功抽出的源码；抽取失败不在这里静默吞掉。"""
    return [script.source for script in _python_chunks(block, 1) if script.source.strip()]


def _kill_process_group(proc: subprocess.Popen) -> None:
    """杀掉判据的【整个进程组】，而不只是直接子进程。

    判据内部会 ``os.fork()`` 起服务子进程；``Popen.kill()`` 只发给直接子进程，
    fork 出来的孙进程会被 reparent 到 init 并继续占端口。``killpg`` 才能一次
    收干净。信号顺序 SIGTERM → SIGKILL：前者让判据有机会跑自己的 handler，
    后者保证不留下任何进程。两次都是【幂等】的。
    """
    try:
        pgid = os.getpgid(proc.pid)
    except (ProcessLookupError, PermissionError, OSError):
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            return
        try:
            proc.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            continue


def _lsof_listeners(port: int) -> list[int]:
    """返回监听 ``port`` 的 PID 列表；lsof 不可用时返回空（不猜）。"""
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    pids: list[int] = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) > 1 and parts[1].isdigit():
            pids.append(int(parts[1]))
    return pids


def _ppid_of(pid: int) -> int | None:
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "ppid="], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return int(out) if out.isdigit() else None


def sweep_orphans(ports: range, dry_run: bool = False) -> list[tuple[int, int]]:
    """清理「本工具的历史孤儿」：占用探测端口、且父进程已死（PPID=1）的进程。

    ★ 为什么只用 PPID 判别：实测孤儿进程的命令行是 ``python3 -c <内联源码>``，
      既不含仓库路径也不含 ``launch_cockpit``，★ 所以「按命令行特征认领」会漏；
      而「父进程已死」是孤儿的定义，且实测能区分两者：
      孤儿 PPID=1  vs  别人正在用的服务 PPID=<真实父进程>。
    ★ 宁可漏杀不可误杀 —— 别人主动起的服务绝不能被本工具杀掉。
    """
    swept: list[tuple[int, int]] = []
    for port in ports:
        for pid in _lsof_listeners(port):
            ppid = _ppid_of(pid)
            if ppid != 1:
                continue  # 父进程健在 → 可能是别人在用，不碰
            print(f"  ⚠️ 清理孤儿进程 pid={pid} port={port}（PPID=1）")
            swept.append((port, pid))
            if not dry_run:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
    return swept


def _scripts(md: pathlib.Path) -> list[Script]:
    """返回 §8 中按文档顺序排列的全部 Python 脚本。"""
    doc = md.read_text(encoding="utf-8")
    scripts: list[Script] = []
    for block_line, block in _fenced_bash_blocks(doc):
        scripts.extend(_python_chunks(block, block_line))
    for index, script in enumerate(scripts, 1):
        script.index = index
    return scripts


def main() -> int:
    print("⑳ BI §8 验收脚本 —— 抽取 → 语法预检 → 真的跑一遍（对工作区）")

    # ★ 兜底：清掉上一次遗留的孤儿服务。进程组 + killpg 已能杜绝新孤儿，
    #   但若本工具曾被 SIGKILL 杀死（父侧无法执行任何清理），仍可能留下。
    #   两条防线都要有 —— 这是「失败环已断」与「大概率已断」的区别。
    dry = "--dry-run-sweep" in sys.argv
    swept = sweep_orphans(range(8721, 8785), dry_run=dry)
    if swept:
        verb = "将清理" if dry else "已清理"
        print(f"  （{verb} {len(swept)} 个历史孤儿监听进程）")

    results: dict[str, list[tuple[int, str, str]]] = {}
    for md in sorted(BUILD.glob("FILE-*-v1.md")):
        rows: list[tuple[int, str, str]] = []
        for script in _scripts(md):
            if script.error:
                rows.append((script.index, "EXTRACT_FAIL", f"L{script.line}: {script.error}"))
                continue
            try:
                compile(script.source, f"{md.stem}#§8-script{script.index}", "exec")
            except SyntaxError as exc:
                detail = f"L{exc.lineno or '?'}: {exc.msg}"
                rows.append((script.index, "SYNTAX_FAIL", detail))
                continue

            # ★ 每个判据跑在自己的【进程组】里（start_new_session=True）。
            #   理由：判据内部会 os.fork() 起服务子进程（如 FILE-401 脚本 7），
            #   而 subprocess.run 超时只 kill【直接子进程】—— 孙进程会被 reparent
            #   到 init 并继续占着 8721–8784，于是下一轮 _pick_port 探不到端口，
            #   判据卡在轮询里再次超时。这是一个【自我复现的失败环】。
            #   实测：无进程组残留 1 个孙进程；有进程组 + killpg 残留 0 个。
            #   macOS 无 prctl(PR_SET_PDEATHSIG)，★ 这是父侧唯一可靠的兜底。
            proc = None
            try:
                # 有些判据要求调用方通过环境变量注入真实音频路径
                # （如 FILE-105 的 REF / PRA）；这是契约的一部分。
                env = dict(os.environ)
                env.setdefault("REF", str(DATASET / "原曲_完整版.wav"))
                env.setdefault("PRA", str(DATASET / "练习曲" / "01_音准走调.wav"))
                proc = subprocess.Popen(
                    [sys.executable, "-c", script.source],
                    cwd=str(REPO),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=True,
                )
                try:
                    stdout, stderr = proc.communicate(timeout=300)
                except subprocess.TimeoutExpired:
                    _kill_process_group(proc)
                    stdout, stderr = proc.communicate()
                    rows.append((script.index, "EXEC_FAIL", "超时 300s"))
                    continue
            except OSError as exc:
                rows.append((script.index, "EXEC_FAIL", f"启动失败: {exc}"))
                continue
            if proc.returncode == 0:
                rows.append((script.index, "PASS", ""))
            else:
                tail = (stderr or stdout or "").strip().splitlines()
                rows.append((script.index, "EXEC_FAIL", tail[-1][:160] if tail else ""))
        results[md.stem] = rows

    names = ("PASS", "SYNTAX_FAIL", "EXTRACT_FAIL", "EXEC_FAIL")
    counts = {name: 0 for name in names}
    for rows in results.values():
        for _, status, _ in rows:
            counts[status] += 1

    for stem, rows in results.items():
        passed = sum(1 for _, status, _ in rows if status == "PASS")
        problems = [row for row in rows if row[1] != "PASS"]
        if not rows:
            # ★ 空集通过必须显式警告：0/0 与「4 个脚本全过」在视觉上无法区分，
            # 而 0/0 恰恰意味着「本文件的验收判据一台机器都不会执行」。
            # 这不是失败（写不出可抽取脚本是事实，不是缺陷），但绝不能显示 ✅。
            print(f"  ⚠️ {stem:<16} 无机器验收判据（0 个可抽取脚本）")
            continue
        flag = "✅" if not problems else "❌"
        print(f"  {flag} {stem:<16} PASS {passed}/{len(rows)}")
        for idx, status, msg in problems:
            print(f"        · 脚本{idx}: {status} {msg}")

    print("\n  合计 " + " / ".join(f"{name} {counts[name]}" for name in names))
    uncovered = sorted(stem for stem, rows in results.items() if not rows)
    if uncovered:
        print(
            f"  ⚠️  {len(uncovered)} 份 BI 没有任何可抽取的验收脚本，"
            f"其 §8 判据当前零机器执行：{' '.join(uncovered)}"
        )
        print(
            "     （这不是失败——写不出可抽取脚本是事实。但它意味着这些文件的"
            "验收判据需要人工执行，不会被任何检查器发现回归。）"
        )
    if counts["SYNTAX_FAIL"] or counts["EXTRACT_FAIL"]:
        print("  ★ 语法错与抽取错已分开：前者看脚本源码，后者看 Markdown/Bash 边界。")
    if counts["EXEC_FAIL"]:
        print("  ⚠️  EXEC_FAIL 的每一条都要人看：可能是 SHELL 未注入，也可能是判据错。")
    return 1 if any(counts[name] for name in names[1:4]) else 0


if __name__ == "__main__":
    sys.exit(main())
