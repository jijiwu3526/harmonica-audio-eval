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
import inspect
import os
import re
import subprocess
import sys
from pathlib import Path

# ★ 已授权注入文件从唯一真相源派生（不再在本文件维护副本）。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from authorized_impl import REPO_REL as _AUTHORIZED_REPO_REL  # noqa: E402
from authorized_impl import NOTES_BY_REPO_REL as _AUTHORIZED_NOTES  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "harmonica_eval"
CONSTITUTION = Path(
    "/Users/Apple/.dsh/attachments/v1/files/84/"
    "841401d7bf94ed17987bb506b14789c41110a894824f367edbf77271fcef3191/"
    "AI_Software_Foundry_Constitution_CN.md"
)
"""宪章原件路径。不在库内（它是外部权威输入），故写绝对路径。

若该路径不存在（换机器 / 附件被清理），检查⑪会**跳过**而非失败 ——
缺宪章不应该让整个空壳验证红掉，但也绝不假装检查过了。
"""

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
    "harmonica_eval/algorithms/registry.py",
    "harmonica_eval/algorithms/runtime.py",
    "harmonica_eval/algorithms/pitch.py",
    "harmonica_eval/algorithms/timing.py",
    "harmonica_eval/algorithms/dynamics.py",
    "harmonica_eval/host/__init__.py",
    "harmonica_eval/host/app.py",
    "harmonica_eval/cockpit/__init__.py",
    "harmonica_eval/cockpit/app.py",
    # ★ 2026-09-24 授权新增（负责人授权「派一个子智能体去做那个前端」）：
    #   preview.py —— C4 契约结构预览视图。BI = FILE-401-P-v1.md
    "harmonica_eval/cockpit/preview.py",
    # ★ 2026-09-24 授权新增（负责人裁定「局域网直接支持」+ 前端接线任务收口）：
    #   serve_ui.py —— 进程装配点，FILE-ID FILE-499。
    #   BI = FILE-400-v1.md:17「上游 = 包外装配方（进程装配点）… 调用 launch_cockpit(port)」
    # ★ 它不属于 C1/C2/C3/C4 任一层，故单列而不并入任一层的 rglob 目录。
    "harmonica_eval/serve_ui.py",
    # ★ 2026-09-24 授权新增（负责人授权「派子智能体注入」第 1 刀）：
    #   bootstrap.py —— 唯一物理装配根，构造 PluginSpec 并 register 即职责本体。
    #   BI = FILE-206-v1.md
    "harmonica_eval/algorithms/bootstrap.py",
    # ★ 2026-09-24 授权新增（负责人授权「接上前端启动入口」）：
    #   serve_ui.py —— 进程装配点。唯一同时 import host 与 cockpit 的配方；
    #   它是 FILE-002-v1.md:45「零 import」约束的**唯一例外出口**，且它不是 __main__。
    #   BI = FILE-400-v1.md:17「上游 = 包外装配方」+ FILE-002-v1.md:45/:47。
    "harmonica_eval/serve_ui.py",
]

# ★ 交叉校验：EXPECTED 是手工枚举的「应当存在的坑位」清单，
#   而 `harmonica_eval/` 下真实存在的 .py 集合只能由文件系统得出。
#   ★ 两者不等时立即报错 —— 新增文件若忘记登记进 EXPECTED，
#   ★ 它将完全不被本脚本检查（不查铭牌、不查依赖方向、不查签名），
#   ★ 那比「判据失败」更危险：失败会报警，看不见则不会。
# ★ 这条校验只在「实际文件集 ⊆ EXPECTED」时成立；
#   反向（EXPECTED 里有但文件不存在）由 ① 文件坑位 单独报缺失。
EXPECTED_SET = frozenset(EXPECTED)

SHELL_MARK = re.compile(r'NotImplementedError\("SHELL: FILE-\d+')
# ★ 铭牌正则：**全仓唯一形态**是「冒号紧跟 FILE-ID，值用空格对齐」——
#   即 `FILE-ID:      FILE-101`（ingest / host / cockpit / core / algorithms 共 22 处）。
# ★ 本正则【刻意严格】。曾一度放宽成 `FILE-ID\s*:\s*` 来「接受两种排版」，
#   那会让铭牌格式漂移无人可查；现改为「统一格式 + 收窄正则 + 独立格式判据」。
NAMEPLATE = re.compile(r"FILE-ID:\s*FILE-\d+")

# ★ 格式一致性判据：铭牌必须逐字采用 `FILE-ID:` 形态。
#   这是一条【永续判据】——不依赖任何特定文件，任何阶段都成立。
#   匹配「冒号前有空格」的异类写法（`FILE-ID      : FILE-xxx`）。
NAMEPLATE_MISALIGNED = re.compile(r"FILE-ID\s+:\s*FILE-\d+")

# ★ 与 NAMEPLATE 同一形态，但**带捕获组**——用于取出编号本身。
#   不复用 NAMEPLATE 是因为它没有捕获组（调用 .group(1) 会 IndexError）。
NAMEPLATE_VALUE = re.compile(r"FILE-ID:\s*(FILE-\d+)")

# 允许含实现的文件（地基，非空壳）
GROUND = {
    "harmonica_eval/contract.py",
    "harmonica_eval/profile.py",
    "harmonica_eval/__init__.py",
}

# ★ 已授权注入的实现文件（负责人明确授权后逐个加入）
# ★ ★ 本表不再在此维护 —— 它派生自 tools/authorized_impl.py（唯一真相源）。
# ★ 精确路径成员判断（下方 `if rel in GROUND`）——**不得放宽成目录或前缀匹配**，
# ★ 否则同目录下未授权的文件会被顺带放过。
# ★ 每个条目的「哪次授权、依据哪份 BI」在真相源里逐条记录，详见 §七。
GROUND_IMPL_NOTES = dict(_AUTHORIZED_NOTES)
GROUND |= set(_AUTHORIZED_REPO_REL)


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

    # ★ 交叉校验：实际存在的 .py 必须全部登记进 EXPECTED。
    #   未登记的文件不会被本脚本任何一节检查 —— 必须当作错误报出。
    actual = {
        str(p.relative_to(REPO))
        for p in PKG.rglob("*.py")
        if "__pycache__" not in p.parts
    }
    unregistered = sorted(actual - EXPECTED_SET)
    if unregistered:
        r.err(
            "以下 .py 未登记进 EXPECTED，verify_shell 完全不检查它们"
            "（不查铭牌 / 依赖方向 / 签名一致性）：\n    "
            + "\n    ".join(unregistered)
        )
    else:
        print(f"  ✅ 实际 {len(actual)} 个 .py 全部登记在 EXPECTED 内")


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
    misaligned = 0
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
        # ★ 格式一致性：铭牌必须用 `FILE-ID:` 形态（全仓唯一）。
        #   「冒号前有空格」的异类写法会让铭牌排版漂移无人可查。
        #   曾一度靠放宽 NAMEPLATE 来接受它 —— 那等于取消这条守卫，故拆成独立判据。
        if NAMEPLATE_MISALIGNED.search(src):
            misaligned += 1
            r.err(f"铭牌格式不一致（应为 `FILE-ID:      FILE-xxx`）: {rel}")
            print(f"  ❌ 格式不一致 {rel}")
    r.stats["有铭牌"] = stamped
    r.stats["铭牌格式一致"] = stamped - misaligned
    print(f"  {stamped}/{len(EXPECTED)} 个文件有 FILE-ID 铭牌")
    print(f"  {stamped - misaligned}/{len(EXPECTED)} 个文件铭牌格式一致")

    # ★ 可追溯性不变量：铭牌上的每个 FILE-ID 都必须有一份对应的 Build Instruction。
    #
    #   为什么必须有：铭牌的价值在于「一眼知道该填哪个文件、依据哪份 BI」。
    #   一个没有 BI 的编号让这条链断掉——实现者看得见 FILE-499，却找不到
    #   FILE-499-v1.md，于是只能自己发明上层设计（这正是 §22 列为硬失败的那一条）。
    #
    #   历史：serve_ui.py 的 FILE-499 曾长期无 BI。本仓 22 个编号「恰好都有」
    #   一直是巧合而非被守着——把编号改成 FILE-498，verify_shell 仍 rc=0。
    bi_backed = 0
    build_dir = REPO / ".spec" / "build"
    for rel in EXPECTED:
        p = REPO / rel
        if not p.exists():
            continue
        m = NAMEPLATE_VALUE.search(p.read_text(encoding="utf-8"))
        if m is None:
            continue
        fid = m.group(1)
        # FILE-499 → FILE-499-v1.md。存在任意版本后缀即算有 BI。
        if any(build_dir.glob(f"{fid}-v*.md")):
            bi_backed += 1
        else:
            r.err(f"FILE-ID {fid} 无对应 Build Instruction: {rel} → 期望 .spec/build/{fid}-v*.md")
            print(f"  ❌ 无 BI {rel}（{fid}）")
    r.stats["编号有 BI"] = bi_backed
    print(f"  {bi_backed}/{len(EXPECTED)} 个文件的 FILE-ID 有对应 BI")


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
        # ★★ 不变量 F 的判定线（FILE-002-v1.md:45/:47）★★
        #   「两者之间【零依赖、零 import、零调用】：本文件绝不 import cockpit，
        #     C4 绝不 import 本文件」，且「把 cockpit 从环境中整体移除后，
        #     本文件的 import 仍须成功」。
        # ★ 这两条此前只写在 docstring 里，全靠人记 —— 没有任何机器守卫。
        # ★ 实测：给 __main__.py 顶层加 `from .cockpit import launch_cockpit`
        #   语法正确、verify_shell 完全不报 —— 那条冻结不变量形同虚设。
        # ★ serve_ui.py 不在此列：它是该约束的**唯一例外出口**
        #   （FILE-400-v1.md:17「上游 = 包外装配方」），且它不是 __main__。
        "harmonica_eval/__main__.py": ("cockpit",),
        # ★ serve_ui.py 是【第三条消费者】（进程装配点），不属于 C1/C2/C3/C4 任一层。
        # ★ 按 FILE-400-v1.md:17，它的「装配点→C1(取 port)」与「装配点→C4(启动 UI)」
        # ★ 两条边是规格允许的 —— 这里【显式列出它不得碰的】，而不是给它整体豁免：
        # ★ 不得知道 algorithms / core，否则它就成了绕过深接口的后门。
        "harmonica_eval/serve_ui.py": ("core", "algorithms"),
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
                elif isinstance(node, ast.ImportFrom):
                    # ★ 相对导入（level > 0）时，被导入的【包】在 node.module，
                    # ★ node.names 里只是被导入的【名字】：
                    #     from ..algorithms.pitch import run
                    #       module='algorithms.pitch'   ← 要判定的包在这里
                    #       names=['run']
                    # ★ 只取 names 会把包名丢掉 —— 实测那样写时违规命中数 = 0，
                    # ★ 守卫形同虚设。裸导入（level=0、module=None）时才取 names。
                    if node.module:
                        mods = [node.module]
                    else:
                        mods = [a.name for a in node.names]
                for m in mods:
                    # ★★ 按【包路径段】判定，不看尾段 ★★
                    # 旧写法只比 m.split(".")[-1]，于是
                    #   'algorithms'            → 抓到
                    #   'algorithms.pitch'      → ★ 漏
                    #   'harmonica_eval.algorithms.pitch' → ★ 漏
                    # 实测过：给 core/ingest.py 注入 `from ..algorithms.pitch
                    # import run`，违规命中数 = 0 —— 那条守卫当时形同虚设。
                    # 这里对 '.' 切段后逐段比对，形态无关（裸包名 / 深层 / 相对）。
                    segments = set(m.split("."))
                    if segments & set(bad):
                        r.err(f"依赖方向违规: {rel} import 了 {m}")
                        print(f"  ❌ {rel} → {m}")
                        violations += 1
    r.stats["依赖检查文件数"] = checked
    if not violations:
        print(f"  ✅ {checked} 个文件，全部符合依赖方向")
        print("     └ 「换算法不改核心」现在是可自动验证的结构事实")
        print("     └ 不变量 F「__main__ 绝不 import cockpit」也已被机器守住")


def check_invariant_f_importable_without_cockpit(r: Report) -> None:
    """不变量 F 的**动态**一半：整体移除 cockpit 后 `__main__` 仍须可 import。

    FILE-002-v1.md:47 明文：「把 `cockpit` 从环境中整体移除后，
    本文件的 import 仍须成功」。静态依赖检查只能证明「没写 import 语句」，
    证不了「没有间接依赖」（例如 `__init__.py` 链式引入）。

    本检查用**子进程 + 临时重命名**实现，不污染工作区：
      1. 把 `harmonica_eval/cockpit` 改名为 `cockpit.__f_probe_moved__`
      2. 在子进程里 import `harmonica_eval.__main__`
      3. 改回原名（finally 保证一定还原）
    ★ 任何一步失败都必须还原，否则会留下半截工作区 —— 比判据失败更糟。

    ★★ 为什么要【子进程】而不是在本进程里 import ★★
      本进程此前可能已把 `harmonica_eval.cockpit.*` 放进 ``sys.modules``。
      若在本进程里试 import，`sys.modules` 命中缓存会返回旧对象，
      探测就会「假绿」—— 这正是 SHELL-STANDARD §七「校验恒真」的一族。
      子进程从干净的模块表起步，看到的是文件系统真相。
    """
    print()
    print("─" * 72)
    print("⑤b 不变量 F（整体移除 cockpit 后 __main__ 仍可 import）")
    print("─" * 72)
    cockpit_dir = REPO / "harmonica_eval" / "cockpit"
    moved_dir = REPO / "harmonica_eval" / "cockpit.__f_probe_moved__"
    if not cockpit_dir.is_dir():
        print("  ⏭  cockpit 目录不存在（不变量 F 本身要求它可被移除，跳过）")
        return
    if moved_dir.exists():
        r.err("不变量 F 探针残留：cockpit.__f_probe_moved__ 已存在，"
              "上一次探针未还原，请人工检查")
        print("  ❌ 探针残留，请人工检查")
        return

    # ★ 先确认移走之后【本进程】的模块缓存不会骗到子进程以外的东西：
    #   记录探针前 sys.modules 里与 cockpit 相关的条目，探针后比对是否被改动。
    before_modules = {k for k in sys.modules if "cockpit" in k}
    try:
        cockpit_dir.rename(moved_dir)
    except OSError as exc:
        r.err(f"不变量 F 探针：无法重命名 cockpit 目录：{exc}")
        print(f"  ❌ 重命名失败：{exc}")
        return

    try:
        proc = subprocess.run(
            [sys.executable, "-c",
             "import harmonica_eval.__main__ as m; print('IMPORT_OK')"],
            capture_output=True, text=True, cwd=str(REPO), timeout=60,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired:
        proc = None
    finally:
        # ★ 一定还原 —— 探针失败不得留下半截工作区。
        #   还原失败时【不 return】：先把事实报完整，再让调用方看到。
        try:
            moved_dir.rename(cockpit_dir)
        except OSError as exc:  # pragma: no cover - 只在文件系统异常时发生
            r.err(f"不变量 F 探针【还原失败】，cockpit 仍停留在 "
                  f"cockpit.__f_probe_moved__：{exc}")
            print(f"  ❌❌ 还原失败，请立即人工处理：{exc}")
            return

    # ★ 探针不得在本进程留下与 cockpit 相关的模块缓存变化：
    #   若有，说明探针期间有人在本进程 import 了 cockpit，
    #   后续检查可能读到「目录还不存在时的旧对象」→ 结论不可信。
    leaked = {k for k in sys.modules if "cockpit" in k} - before_modules
    if leaked:
        print(f"  ⚠️ 探针期间本进程新增了 {len(leaked)} 个 cockpit 模块缓存条目"
              f"（{sorted(leaked)[:3]}）")
        print("     └ 静态检查已在探针前完成，此处仅记录；"
              "若后续检查 import cockpit 失败，先查这一条")

    if proc is None:
        r.err("不变量 F 探针超时（60s），无法判定")
        print("  ❌ 探针超时")
        return
    if proc.returncode != 0 or "IMPORT_OK" not in proc.stdout:
        r.err("不变量 F 违反：整体移除 cockpit 后 __main__ 无法 import\n"
              + proc.stderr.strip()[:600])
        print("  ❌ 移除 cockpit 后 __main__ import 失败")
        print("     └ 这意味着无头通路依赖了界面组件，违反 FILE-002-v1.md:47")
        return
    print("  ✅ cockpit 整体移除后 __main__ 仍可 import（不变量 F 成立）")
    print("     └ 探针在子进程中执行，本进程模块缓存未被污染")


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


def check_contract_signatures(r: Report) -> None:
    """⑧ 契约与实现的签名一致性。

    ★ G8 修正（§20 盲审发现）：`HostContract.set_reference(uri)` 只有 1 个参数，
    而 `HostCore.set_reference(self, uri)` 实现的虽是同一件事，
    同协议里另外 5 个操作却**都**要 `session_id`。
    契约内部不自洽，实现者无法判断该往哪个会话登记。

    这类"契约说一套、另一边写另一套"的漂移不会报错 ——
    直到有人真的去调用才发现对不上。故机械检查：
    `core/api.py` 的 `HostCore` 每个方法签名必须与 `contract.HostContract`
    的同名方法**逐参数一致**。
    """
    print()
    print("─" * 72)
    print("⑧ 契约 ↔ 实现 签名一致性")
    print("─" * 72)

    import ast as _ast

    contract_path = PKG / "contract.py"
    api_path = PKG / "core" / "api.py"

    def method_params(path: Path, cls_name: str) -> dict[str, list[str]]:
        """返回类声明的公开方法及其参数名。

        契约面是 C1 可见的公开操作：名称以 ``_`` 开头的 dunder 与
        私有辅助（包括 ``__init__``、``_require``、``_set_uri``）不进入
        契约面。私有辅助可以合法存在，但不能因此被误报为契约外方法；
        反过来，公开方法仍必须与 HostContract 双向完全一致。
        """
        tree = _ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        out: dict[str, list[str]] = {}
        for node in _ast.walk(tree):
            if isinstance(node, _ast.ClassDef) and node.name == cls_name:
                for sub in node.body:
                    if (
                        isinstance(sub, (_ast.FunctionDef, _ast.AsyncFunctionDef))
                        and not sub.name.startswith("_")
                    ):
                        out[sub.name] = [a.arg for a in sub.args.args]
        return out

    proto = method_params(contract_path, "HostContract")
    impl = method_params(api_path, "HostCore")

    hits: list[str] = []
    for name, pparams in proto.items():
        if name not in impl:
            hits.append(f"HostCore 缺少契约方法 '{name}'")
            continue
        # 去掉 self 后逐参数比对
        ip = [p for p in impl[name] if p != "self"]
        pp = [p for p in pparams if p != "self"]
        if ip != pp:
            hits.append(
                f"'{name}' 签名不一致：契约 ({', '.join(pp)}) "
                f"vs 实现 ({', '.join(ip)})"
            )

    extra = set(impl) - set(proto)
    if extra:
        hits.append(
            f"HostCore 多出契约未声明的方法 {sorted(extra)}"
            "（宪章 §47.6 Silent Contract Mutation）"
        )

    for h in hits:
        print(f"  ❌ {h}")
        r.err(h)

    print(f"  比对了 {len(proto)} 个契约方法")
    if not hits:
        print("  ✅ 7 个方法签名逐参数一致，且无契约外方法")


def check_doc_port_count(r: Report) -> None:
    """⑨ 文档中的端口数与代码实际一致。

    ★ 被一次真实疏漏逼出来的：我把端口从 11 个加到 12 个（补 notes.practice），
    但 6 处 `.md` 仍写「11 个端口」。**文档与代码不一致**正是本项目
    反复批判的那类缺陷 —— 读文档的人会按错的数字做设计。

    本检查扫描 .md 里的「N 个端口」说法，与实际 len(profile.PORTS) 比对。
    """
    print()
    print("─" * 72)
    print("⑨ 文档 ↔ 代码 端口数一致")
    print("─" * 72)

    sys.path.insert(0, str(REPO))
    try:
        from harmonica_eval.profile import PORTS
    except Exception as exc:  # pragma: no cover
        msg = f"无法导入 profile 以取得端口数: {exc}"
        print(f"  ❌ {msg}")
        r.err(msg)
        return

    actual = len(PORTS)
    pattern = re.compile(r"(\d+)\s*个端口")
    hits: list[str] = []

    # ★ 第四类误报（本仓第四次踩"形式当实质"的坑，故明写在此）：
    #
    # 第一版把「N 个端口」一律当成"端口总数声明"，于是刷出 7 条误报。
    # 实测样例：FILE-004 的
    #     「本 profile：11 个端口为 `REFERENCE`，仅 `pcm.warped.practice` 为 WARPED」
    # **这句话完全正确** —— 它是"12 个里有 11 个用某条轴"的子集陈述，
    # 不是"全仓只有 11 个端口"。同理「产出 8 个端口」是在说某个生产者产出几个。
    #
    # 判据：只有当数字后面**紧跟表总量的词**（总/共/全部/一共/计 或位于
    # 「端口清单/端口总数」这类短语里）时，才当作总数声明。
    # 用**前瞻**实现，而不是看整行有没有别的词 —— 因为"为 REFERENCE"、
    # "产出"、"消费"这些限定语可能出现在数字**前后任意位置**，
    # 按整行判断会把真违规也一起放过。
    # ★ 第五类误报（同一类错误的第五次，全部记录在此以免后人重踩）：
    #   实测的两条剩余误报：
    #     (a) FILE-401「8721–8784 共 64 个端口全部 bind 失败」
    #         —— 这是 **TCP 端口**，与本仓的**数据端口**只是同名的两回事。
    #     (b) FILE-004「其余 11 个端口全部 float32」
    #         —— 12 个里除 warp_path 外其余 11 个，是**正确子集**；
    #            "全部"在这里修饰 dtype，不修饰端口总数。
    #
    #   修法：
    #   - 网络语境排除：数字前若出现 IP / bind / listen / 端口号区间（N–M）
    #     等线索，跳过。
    #   - "其余/其他/剩下" 开头的子集陈述，跳过。
    NET_CTX = re.compile(
        r"(?:127\.0\.0\.1|localhost|bind|listen|TCP|HTTP|端口号|\d+\s*[–\-—]\s*\d+)"
    )
    SUBSET_CTX = re.compile(r"(?:其余|其他|剩下|另外|其中|除[^，。]{0,12}外)")

    TOTAL_MARK = re.compile(
        r"(\d+)\s*个端口\s*(?:（[^）]*）)?\s*"
        r"(?=[，,。；;：:、]?\s*(?:总|共|全部|一共|计|清单|列表|数|$))"
    )

    # 历史叙述的标记词：这些内容在描述**过去的设计**（已撤回/曾/原先/v1），
    # 其中的数字是历史事实，不该被当作当前声明。
    # 例：COMPONENTS.md 的「## 0. 本版相对 v1 的四处自我纠错」表里
    #     「把 P000–P431（约 34 个端口）写进 L1 契约」—— 那是被撤回的旧方案。
    #
    # ★ 必须同时看**行**与**所在小节标题**：紧邻的标题常常是唯一的历史线索，
    #   而表格行本身可能一个历史词都没有（实测踩过这个坑）。
    HISTORICAL = ("曾", "原先", "第一版", "v1 ", "已撤回", "此前", "旧", "历史",
                  "自我纠错", "纠错", "撤回", "不再", "原名", "改名")
    HEADING_HISTORICAL = ("v1", "历史", "纠错", "撤回", "变更", "修订", "沿革")

    md_files = [
        p for p in REPO.rglob("*.md")
        if ".spec" not in p.parts
        and "harmonica_mvp_dataset" not in p.parts
        and "node_modules" not in p.parts
    ] + [
        p for p in (REPO / ".spec").rglob("*.md")
        if "BLIND-TEST-REPORT" not in p.name  # 报告里记录的是历史数字
    ]

    for path in md_files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        in_historical_section = False
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                # 进入/离开历史小节
                in_historical_section = any(
                    h in stripped for h in HEADING_HISTORICAL
                )
                continue
            if in_historical_section:
                continue
            if any(h in line for h in HISTORICAL):
                continue

            if NET_CTX.search(line) or SUBSET_CTX.search(line):
                continue
            for m in TOTAL_MARK.finditer(line):
                n = int(m.group(1))
                if n != actual:
                    rel = path.relative_to(REPO)
                    hits.append(f"{rel}: 说「{n} 个端口」，实际 {actual}")

    for h in hits:
        print(f"  ❌ {h}")
        r.err(h)

    print(f"  扫描了 {len(md_files)} 个 .md，实际端口数 = {actual}")
    if not hits:
        print("  ✅ 文档中的端口数与代码一致")


def check_plugin_contract_consistency(r: Report) -> None:
    """⑩ C3 插件契约自洽性 —— ★ C3 插件化后**取代**旧的
    「算法 payload 键名 ↔ 冻结表」检查。

    ── 为什么换掉，而不是直接删掉 ──
    旧检查⑩是被一次真实事故逼出来的：新增 `PAYLOAD_SCHEMAS` 时不知道
    `timing.py` 的 docstring 已写了另一套键名，于是**同一份事实有了两个
    互相冲突的来源**，实现者无法同时满足，而两者都不会在 import 时报错。
    这个教训（"共同事实来源"）依然有效，所以检查不能直接删。

    但插件化**从结构上消除了第二个来源**：
        旧：模块 docstring 声明键名  +  框架里 PAYLOAD_SCHEMAS 再声明一遍
        新：插件产出自描述的 `Sequence[UiScalar | UiSeries]`，
            key / label / unit 就在**对象本身**里，框架不再有第二份清单
    冲突的两个来源少了一个，检查自然要跟着换目标。

    ── 本检查现在验什么 ──
    验的是"插件契约本身没有自相矛盾"，具体四条：
      1. `UNITS_VOCABULARY` 覆盖插件产出的单位类别，且不含空串
      2. `UiScalar` / `UiSeries` 的字段与信封 `payload` 的类型注解一致
         （投影要靠"字段逐字相同"才成立，字段一变这条就红）
      3. `InputRequirement` 只有 port_id 必填（其余可默认 ⇒ 声明成本低）
      4. `PluginSpec` 存在且 required/optional 都是 tuple 类型注解
         （不是 list/可变容器 ⇒ 注册进来的 spec 是冻结的）

    ── 红/绿自证要求 ──
    每条检查都必须能"注入违规 → 变红 → 恢复 → 变绿"。
    """
    print()
    print("─" * 72)
    print("⑩ C3 插件契约自洽性（取代旧的 payload 键表检查）")
    print("─" * 72)

    sys.path.insert(0, str(REPO))
    try:
        import dataclasses as _dc

        from harmonica_eval import contract as _c
    except Exception as exc:
        msg = f"无法导入 contract: {exc}"
        print(f"  ❌ {msg}")
        r.err(msg)
        return

    issues: list[str] = []

    # 1) 单位词表
    units = _c.UNITS_VOCABULARY
    if "" in units:
        issues.append("UNITS_VOCABULARY 含空串（无法解释的数字）")
    for needed in ("cents", "ms" if "ms" in units else "seconds", "ratio", "count"):
        if needed not in units:
            issues.append(f"UNITS_VOCABULARY 缺 {needed!r}（插件要产出该单位）")

    # 2) payload 注解必须与 UiScalar/UiSeries 同构
    env_payload = {
        f.name: str(f.type) for f in _dc.fields(_c.AlgorithmResultEnvelope)
    }.get("payload", "")
    if "UiScalar" not in env_payload or "UiSeries" not in env_payload:
        issues.append(
            f"AlgorithmResultEnvelope.payload 注解不是 "
            f"Sequence[UiScalar | UiSeries]（实得 {env_payload!r}）"
        )

    # 3) InputRequirement 只有 port_id 必填
    req_fields = _dc.fields(_c.InputRequirement)
    mandatory = [
        f.name
        for f in req_fields
        if f.default is _dc.MISSING and f.default_factory is _dc.MISSING
    ]
    if mandatory != ["port_id"]:
        issues.append(
            f"InputRequirement 的必填字段应为恰好 ['port_id']，实得 {mandatory}"
        )

    # 4) PluginSpec 的 required/optional 必须是不可变容器注解
    spec_types = {
        f.name: str(f.type) for f in _dc.fields(_c.PluginSpec)
    }
    for name in ("required_inputs", "optional_inputs"):
        t = spec_types.get(name, "")
        if "tuple" not in t:
            issues.append(f"PluginSpec.{name} 注解应含 tuple（实得 {t!r}）")

    for i in issues:
        print(f"  ❌ {i}")
        r.err(i)

    print(f"  InputRequirement 字段 {len(req_fields)} 个（必填 {len(mandatory)}）")
    print(f"  UNITS_VOCABULARY {len(units)} 个值")
    if not issues:
        print("  ✅ 插件契约四条自洽")


def check_constitution_citations(r: Report) -> None:
    """⑪ 引用的宪章条款必须真实存在。

    ★ 被一次真实事故逼出来（由下往上核对代码时发现）：
    8 个文件里写着「宪章 §11 逃生口」，用来论证"数据面必须永远含两份
    aligned PCM"。但 —— **宪章 §11 是 Mission Threads**，
    且全文 **0 次**出现 `PCM` / `逃生` / `预处理`。

    即：那个引用是**伪造的**。设计保证本身合理，但它披了一件不属于它的
    权威外衣，并传播到 profile / contract / COMPONENTS / CONTRACTS /
    research / prompts 六处。

    为什么这比"写错数字"更严重：
      - 写错数字，读者一算就知道错；
      - 伪造引用**无法被机械反驳**，读者会默认"宪章说过"而不再核查；
      - 它把"我们的取舍"伪装成"上层要求"，从而免疫于正常质疑。

    §22 把「无法追溯到上层意图」列为硬失败。伪造引用是它的**反面伪装**：
    看起来可追溯，实则追溯到一个不存在的地方。
    """
    print()
    print("─" * 72)
    print("⑪ 宪章引用真实性")
    print("─" * 72)

    const = CONSTITUTION
    if not const.exists():
        print(f"  ⚠️  找不到宪章，跳过（{const}）")
        return

    text = const.read_text(encoding="utf-8")
    sections = {
        m.group(1): m.group(2).strip()
        for m in re.finditer(r"^# (\d+)\.\s*(.+)$", text, re.M)
    }

    cited: dict[str, set[str]] = {}
    for p in sorted(REPO.rglob("*")):
        if not p.is_file() or "__pycache__" in str(p) or "/.git/" in str(p):
            continue
        if p.suffix not in (".py", ".md", ".html", ".yaml", ".txt"):
            continue
        if "Constitution" in p.name:
            continue
        try:
            body = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # 只看"宪章 §N"这种明确指向宪章的引用，
        # 避免把 SPEC §5 / COMPONENTS §4.2 等本仓章节误判
        for m in re.finditer(r"宪章\s*§(\d+)", body):
            cited.setdefault(m.group(1), set()).add(
                str(p.relative_to(REPO))
            )

    # ★ 关于"伪引用"的可检查边界（诚实声明）：
    #
    # 第一版我试图用正则核对"每个 §N 后面的短语是否真在该章里"。
    # **它失败了** —— 中文散文里引用后面紧跟的常是**作者自己的评述**
    # 而非该章的原文，例如「宪章 §20 的要求，已作废」中的"已作废"
    # 是作者在说"我撤回了"，不是声称 §20 里有"已作废"。
    # 结果是大量误报（一次跑出 10+ 条假警报）。
    #
    # 结论：**任意引用的语义真伪无法用正则机械判定**，
    # 它需要人或有能力读原文的模型来核。硬要用正则会制造
    # 比它要防的问题更多的噪声 —— 而噪声会让这条检查被无视。
    #
    # 所以本检查只做两件**可靠**的事：
    #   (1) 章节存在性 —— 引用 §99 时必定报错（纯机械，零误报）
    #   (2) 已知伪引用回归 —— 把真实发生过的事故钉成回归用例，
    #       防止它悄悄复发（这也是本项目第三次同类教训的固定做法）
    #
    # 语义核对的责任落回 §23 跨层审计（人/强模型），工具不冒充它。

    KNOWN_FALSE_CITATION_PHRASES: tuple[tuple[str, str], ...] = (
        (
            "宪章 §11 逃生口",
            "§11 是 Mission Threads；宪章全文 0 次出现 PCM/逃生/预处理。"
            "该保证是本仓自定，应按其本来身份引用。",
        ),
        (
            "宪章 §11",
            "若与『逃生口』/『PCM 自行预处理』连用即为伪引用（见上）。",
        ),
    )

    regressions: list[str] = []
    SELF = Path(__file__).resolve()
    for p in sorted(REPO.rglob("*")):
        if not p.is_file() or "__pycache__" in str(p) or "/.git/" in str(p):
            continue
        if p.suffix not in (".py", ".md", ".html", ".yaml", ".txt"):
            continue
        if "Constitution" in p.name:
            continue
        # 本检查器自身必然要**提到**这个伪引用串（否则无法定义检查），
        # 故排除自己 —— 这是检查器与规则同源时的常规豁免。
        if p.resolve() == SELF:
            continue
        try:
            body = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # ★ 豁免词必须按**窗口**看，不能按**行**看。
        #
        # 第一版是逐行判断豁免词，于是自己踩了坑：本仓的记录文字是中文散文，
        # **会折行**。实测事故：
        #     L402: 我手写的「宪章 §11 逃生口」引用
        #     L403: 是**伪造的**，并传播到 6 个文件。
        # 豁免词「伪造」在 403 行，触发词在 402 行 —— 逐行判断必然误报。
        #
        # 这与检查⑬ 的误报是**同一类错误**：把"语义作用域"当成了"文本行"。
        # 修法：取命中行的前后各 2 行组成窗口，窗口内出现豁免词即放行。
        # 代价：一段真正违规的文字若恰好邻近"伪造"二字会被放过。
        # 接受该代价 —— 本检查的职责是**防止已修事故复发**，
        # 而不是做语义真伪判定（那件事已明确交给 §23 跨层审计，见上）。
        lines = body.splitlines()
        EXEMPT = ("伪造", "更正", "原写", "已作废", "本仓自定", "伪引用", "事故")
        for lineno, line in enumerate(lines, 1):
            if "宪章 §11" not in line:
                continue
            if not ("逃生" in line or "自行预处理" in line):
                continue
            window = "\n".join(lines[max(0, lineno - 3) : lineno + 2])
            if any(k in window for k in EXEMPT):
                continue
            regressions.append(
                f"{p.relative_to(REPO)}:{lineno} 复发伪引用「宪章 §11 逃生口」"
            )

    for g in regressions:
        print(f"  ❌ {g}")
        r.err(g)

    bad: list[str] = []
    for sec, files in cited.items():
        if sec not in sections:
            for f in sorted(files):
                bad.append(f"{f} 引用宪章 §{sec}，但宪章无此章")

    for b in bad:
        print(f"  ❌ {b}")
        r.err(b)

    if cited:
        print(f"  宪章 {len(sections)} 章；本仓引用了 "
              f"§{', §'.join(sorted(cited, key=int))}")
    if not bad:
        print("  ✅ 所有『宪章 §N』引用都落在宪章实际章节内")


def check_doc_symbol_drift(r: Report) -> None:
    """⑫ 文档里提到的类型名与状态值，必须真的存在于代码里。

    ★ 由下往上核对代码时发现的**一整类**漂移：

        COMPONENTS.md 写 `AlgorithmResultEnvelopeV1`（3 次）
                      `AnalysisDataSurfaceV1` / `SurfaceManifestV1`
                      `SurfaceHandle` / `SessionHandle`
                      → 代码里这些名字**全都不存在**

        COMPONENTS.md 写会话状态含 `RUNNING` / `RESULTS_READY`
                      → contract.SessionState 只有 6 个取值，没这两个

    为什么危险：文档是**实现者的输入**。名字对不上，
    实现者要么去找一个不存在的类型，要么自己发明一个 ——
    后者正是 §22 硬失败「Build Instruction 要求实现者自行做上层设计」。

    检查范围刻意收窄到**高置信度**信号：
      - 只查 `V1` 结尾的类型名（本仓已弃用该后缀风格）
      - 只查会话状态枚举值（有唯一权威 contract.SessionState）
    不做"文档里任意 CamelCase 都必须是代码符号"的宽检查 ——
    那会把 PCM / MIDI / STFT 这类通用词全部误报（实测会刷出 40+ 条噪声）。
    """
    print()
    print("─" * 72)
    print("⑫ 文档符号漂移")
    print("─" * 72)

    sys.path.insert(0, str(REPO))
    import harmonica_eval.contract as C

    issues: list[str] = []

    # ① 已弃用的 V1 后缀类型名
    for doc in sorted(REPO.glob("*.md")):
        body = doc.read_text(encoding="utf-8")
        for m in re.finditer(r"\b([A-Z][A-Za-z]+V1)\b", body):
            issues.append(
                f"{doc.name} 提到 {m.group(1)}，但代码里没有这个类型"
            )

    # ② 会话状态值 —— **只对 C1 章节**生效。
    #
    # 为什么必须限定范围：C2 章节的 state_model 写的是
    # `CREATED → INGESTING → CANONICALIZING → ALIGNING → MATERIALIZING`，
    # 那是 **Core 内部阶段**，而契约明说「C2 内部阶段不得外泄」——
    # 它们**本来就不该**出现在 SessionState 里。把它们报成错误是误报
    # （实测第一版就刷出 4 条这种假警报）。
    #
    # 真正要防的是 C1 章节：C1 的状态机**就是** SessionState，
    # 两者必须逐字一致，否则实现者会去实现一个不存在的状态。
    real_states = {s.name for s in C.SessionState}
    for doc in sorted(REPO.glob("*.md")):
        body = doc.read_text(encoding="utf-8")
        m = re.search(r"### COMP-C1.*?(?=\n### |\Z)", body, re.S)
        if not m:
            continue
        for sm in re.finditer(r"state_model:[^\n]*", m.group(0)):
            for tok in re.findall(r"\b([A-Z][A-Z_]{2,})\b", sm.group(0)):
                if tok in real_states or tok.endswith("_V1"):
                    continue
                issues.append(
                    f"{doc.name} 的 C1 state_model 含 {tok}，"
                    f"但 SessionState 无此取值（实际：{sorted(real_states)}）"
                )

    # 说明性输出：C2 内部阶段无代码对应物，这是**正确**的，不是缺陷
    c2 = re.search(r"### COMP-C2.*?(?=\n### |\Z)",
                   (REPO / "COMPONENTS.md").read_text(encoding="utf-8"), re.S)
    if c2:
        mm = re.search(r"state_model:[^\n]*", c2.group(0))
        if mm:
            print("  ℹ️  C2 内部阶段（刻意不进 SessionState，非缺陷）："
                  f"{mm.group(0).split(':', 1)[1].strip()[:64]}")

    for i in issues:
        print(f"  ❌ {i}")
        r.err(i)

    print(f"  SessionState 实际取值：{sorted(real_states)}")
    if not issues:
        print("  ✅ 文档符号与代码一致")


def check_registry_signature_consistency(r: Report) -> None:
    """⑬ 算法注册表声明的端口，必须真的能被该算法的入口函数拿到。

    ★ 由下往上核对代码时发现（走查 `algorithms/*.py` 的签名与 docstring）：

        `algorithms.ALGORITHMS` 声明 pitch 需要
            ('pitch.reference', 'pitch.practice', 'notes.reference', 'notes.practice')
        且 `algorithms/__init__.py` 的 MOLD BREAK 注记明写：
            "pitch 用逐音索引把逐帧偏差聚合成『第 n 个音偏了多少音分』"

        但 `pitch.py` 的 `compare_pitch_curves(ref_pitch, prac_pitch, sample_rate)`
        **没有 notes 参数**，docstring 却写"返回**逐音**的音分偏差"。
        `summarize_deviations(deviations_cents)` 同样只收一个参数。

        ⇒ 实现者被要求"聚合到第 n 个音"，却不被交给任何音符边界。
        他只能：(a) 自己发明音符切分（重做 features 的活），
        或 (b) 假装逐帧结果就是逐音结果（静默算错）。
        两条路都是 §22 硬失败。

    这个缺陷逃过了检查⑧：⑧ 只比对 `HostContract ↔ HostCore`，
    不涉及算法注册表。而"注册表说要什么"与"签名真的收了什么"
    之间的漂移，正是本仓反复吃亏的那一类。

    检查方式（刻意保守，只报高置信度）：
      对每个【具体算法模块】（结构判据：定义了 `run(...)`），
      若其中某个公开函数的 docstring 声称产出 `逐音`/`per_note` 结果，
      则同模块内**必须**有某个公开函数的形参名里出现音符边界类词根
      （note / onset / span / bound）—— 否则报错。

    ★ 第一版把词根收窄成只有 `note`，刷出 **1 条误报**：
        timing.py 的 `match_onsets(ref_onsets, prac_onsets, tolerance_sec)`
        **确实**接收了音符边界（起音时刻就是边界），只是变量名叫 onset 不叫 note。
      这正是本仓在检查⑪、⑫ 上重复吃过的亏：**过宽的检查制造噪声，
      过窄的检查漏掉真缺陷**。现按实际语义补齐词根，并在此记录该误报。

    ★ 第二版扫 `algorithms/*.py` 全部文件，又刷出 **1 条误报**：
        `bootstrap._requirement(port_id)` 的 docstring 在解释
        `sample_rate` 规则时提到「逐音索引」——那是**解释别人的规则**，
        不是它自己声称产出逐音；而 `_requirement` 只填 `InputRequirement`，
        本来就不该收音符边界。
      两处修正：
        ① 只检查定义了 `run(...)` 的**具体算法模块**（框架文件不在范围内，
           与 check_plugin_contract 同一判据）；
        ② 判据从「本模块任一 docstring 提到逐音」收紧为
           「**该函数自己**的 docstring 声称产出逐音」。
      ★ 未加任何豁免名单 —— 加豁免只会掩盖下一处同类问题。

    ★ 顺带修一处**报错信息误导**：原实现把 `path.name`（bootstrap.py）
      当成被指控的实现文件，而判据真正分析的是同目录下的算法模块，
      于是报错指向 `bootstrap.py`、正文却在说 `pitch.py` 的事。
      现改为列出【实际声称产出的函数名】，不再指错文件。

    为什么不是"检查 required_ports 每个端口都被用到"：
    那会误报 `warp_path`（证据端口，刻意不被消费）、
    以及 `run()` 内部读取的端口（它们经 `surface.read()` 动态取，签名里看不见）。
    """
    print()
    print("─" * 72)
    print("⑬ 算法注册表 ↔ 入口函数签名 一致性")
    print("─" * 72)

    import ast as _ast

    # 音符边界类词根。判据是**语义**（能不能拿到音符边界），不是命名风格。
    BOUNDARY_ROOTS = ("note", "onset", "span", "bound")

    alg_dir = PKG / "algorithms"
    hits: list[str] = []
    checked = 0

    # ★★ 只检查【具体算法模块】，框架文件不在范围内 ★★
    #   判别依据是**结构**：定义了算法入口 `run(...)` 的才是算法模块。
    #   与 check_plugin_contract 的 `_implements_algorithm_entry` 同一判据。
    #
    #   ★ 这一点是第三版才补上的 —— 前两版都扫 `algorithms/*.py` 全部文件，
    #   于是 bootstrap（装配根）与 runtime（框架）在它们的 docstring
    #   【解释规则时顺带提到「逐音」】时被误判成「声称产出逐音」。
    #   实测误报：bootstrap._requirement(port_id) 的 docstring 里
    #   为解释 sample_rate 规则提到 `notes.*` 逐音索引，
    #   而该函数只填 InputRequirement，本来就不该收音符边界。
    _FRAMEWORK_STEMS = {"__init__", "bootstrap", "registry", "runtime"}

    for path in sorted(alg_dir.glob("*.py")):
        if path.stem in _FRAMEWORK_STEMS:
            continue
        src = path.read_text(encoding="utf-8")
        tree = _ast.parse(src, filename=str(path))

        # 结构判据：定义了 run(...) 才是算法模块
        defines_entry = any(
            isinstance(node, _ast.FunctionDef) and node.name == "run"
            for node in tree.body
        )
        if not defines_entry:
            continue

        # ★ 只认「这个函数自己声称产出逐音」，而不是「本模块某处提到逐音」。
        #   ★ 前者是要交付的能力，后者可能只是解释规则的顺带提及。
        claims_per_note: set[str] = set()
        params_by_func: dict[str, list[str]] = {}
        # ★ 边界能力可以由【形参名】或【函数名】承载 ——
        #   两者都算「拿得到音符边界」。
        #   ★ 第四版才补上函数名这一路：实测 `match_onsets(ref_x, prac_x, …)`
        #   ★ 把形参改名后判据仍放行，而那个函数名 `match_onsets` 本身就说明
        #   ★ 它消费起音时刻 —— 形参改名不等于能力消失。★ 那次红端没抓到，
        #   ★ 正是这个洞。
        for node in tree.body:
            if not isinstance(node, _ast.FunctionDef):
                continue
            params_by_func[node.name] = [a.arg for a in node.args.args]
            ds = _ast.get_docstring(node) or ""
            if "逐音" in ds or "per_note" in ds:
                claims_per_note.add(node.name)

        if not claims_per_note:
            continue
        checked += 1

        has_note_param = any(
            any(root in p.lower() for root in BOUNDARY_ROOTS)
            for params in params_by_func.values()
            for p in params
        ) or any(
            # ★ 函数名也算边界能力的载体（见上方注释）
            any(root in fname.lower() for root in BOUNDARY_ROOTS)
            for fname in params_by_func
        )
        if not has_note_param:
            funcs = ", ".join(
                f"{n}({', '.join(p)})" for n, p in params_by_func.items()
            )
            # ★ 报「实际声称产出的函数名」而不是笼统的模块名 ——
            #   原实现报 path.name，在框架文件被误判时会指错文件。
            claimants = ", ".join(sorted(claims_per_note))
            hits.append(
                f"{path.name} 的 {claimants} docstring 声称产出『逐音』结果，"
                f"但该模块没有任何函数接收音符边界（note/onset/span/bound）—— "
                f"签名：{funcs}"
            )

    for h in hits:
        print(f"  ❌ {h}")
        r.err(h)

    print(f"  检查了 {checked} 个声称『逐音』输出的算法模块")
    if not hits:
        print("  ✅ 声称逐音输出的算法都能拿到音符边界")


def check_build_instruction_completeness(r: Report) -> None:
    """检查⑭：Build Instruction 的完整性（结构 + 无占位符残留）。

    ★ 判据不能是「标题必须逐字等于 `## N · 名称`」——
      **第一版就是这么写的，结果把 FILE-004 误判成"缺 10 节"**：
      它写的是 `## §1 归属与邻居`，节次齐全、内容还是全仓质量最高的一份
      （58 KB，12 个端口逐个规格化）。
      这与检查⑪（豁免词按**行**看，但中文散文**会折行**）、
      检查⑬（词根只认 `note`，漏了 `onset`）是**同一类错误**：
      **把"形式"当成了"实质"**。
      故本版只要求**节号出现**，不限定分隔符写法。
      这是本仓第三次踩同一个坑，故在此明写。

    第二类判据是**占位符残留**。本仓改用「骨架法」产出 Build Instruction ——
    先把模板结构写进磁盘，再让智能体逐节填充，好处是**部分成果也落盘**
    （此前 8 个智能体全部空手而死，一个字都没留下）。
    代价就是**可能留下没填的占位符**，所以必须有这道闸。
    实测该判据真的抓住了 FILE-101 / FILE-201（各 16 处残留）。
    """
    print()
    print("─" * 72)
    print("⑭ Build Instruction 完整性")
    print("─" * 72)

    bi_dir = REPO / ".spec" / "build"
    if not bi_dir.is_dir():
        print("  ⚠️  .spec/build/ 不存在，跳过")
        return

    # 只要求「第 N 节」的节号出现，允许 `## 1 ·` / `## §1 ` / `## 1.` 等写法
    sec_patterns = [
        re.compile(rf"^#{{1,3}}\s*§?\s*{n}\b", re.M) for n in range(1, 11)
    ]
    ph_pattern = re.compile(r"<待填[^>]*>")

    bi_bad: list[str] = []
    bi_ok = 0
    for p in sorted(bi_dir.glob("FILE-*-v1.md")):
        body = p.read_text(encoding="utf-8")
        missing = [
            n for n, pat in zip(range(1, 11), sec_patterns) if not pat.search(body)
        ]
        ph = len(ph_pattern.findall(body))
        issues: list[str] = []
        if missing:
            issues.append("缺节 " + "/".join(str(n) for n in missing))
        if ph:
            issues.append(f"占位符残留 {ph} 处")
        if len(body) < 4000:
            issues.append(f"过短（{len(body)} B）")
        if issues:
            bi_bad.append(f"{p.name}: " + "，".join(issues))
        else:
            bi_ok += 1

    for b in bi_bad:
        print(f"  ❌ {b}")
        r.err(b)

    total_bi = bi_ok + len(bi_bad)
    print(f"  合格 {bi_ok} / {total_bi} 份")
    if not bi_bad:
        print("  ✅ 全部 Build Instruction 结构完整、无占位符残留")


def check_bi_symbol_references(r: Report) -> None:
    """检查⑮：Build Instruction 引用的符号必须**真实存在**。

    ★ 为什么需要这条检查 —— 它抓住的是一类**最贵的错误**：

    FILE-103-v1.md 曾引用 6 个**不存在**的东西：
        ErrorCode.INVALID_AUDIO / PITCH_ESTIMATION_FAILED / PORT_NOT_FOUND
        MATERIALIZE.chroma_frame_length / chroma_hop_length
        MATERIALIZE.pitch_fmin / pitch_fmax
        harmonica_eval.core.profile / harmonica_eval.core.contract（模块不存在）

    危险性在于：Build Instruction 是**冻结产物**，开头写着
    「实现者**不得**修改本文件」。所以实现者会**照着不存在的东西写代码**，
    撞到 `AttributeError` / `ModuleNotFoundError` 后，
    最可能的反应是**怀疑自己**，而不是怀疑那份"冻结"的文档。

    这与检查⑪（伪造宪章引用）是同一族缺陷：
    **一句凭印象写下的判断，进了文档，随后看起来就像事实。**
    区别只是⑪伪造的是"外部权威"，本条伪造的是"内部符号"。

    检查方式（刻意保守，只报高置信度）：
      对每份 Build Instruction，提取 `ErrorCode.X` / `MATERIALIZE.X` /
      `AUDIO.X` / `ALIGN.X` / `FIELD_LAYOUTS['X']` 形态的引用，
      与代码里的真实成员比对；再检查 `harmonica_eval.core.*` 这种
      不存在的模块路径。

    豁免：说明性行（含「不存在」「是错的」「上一版」等更正标记）跳过 ——
      因为本文件的修正记录**必须**提到那些错误名字。
      ★ 注意用**窗口**而非单行判断：中文散文会折行（检查⑪ 的教训）。

    ★ 本检查第一版有 **2 处误报**，均已修正并记录在此（不掩盖）：
      (1) `AUDIO.__dataclass_params__` —— 这是 **dataclass 的真实协议属性**
          （`@dataclass(frozen=True)` 会生成它），FILE-004 用它断言 frozen，
          **完全正确**。修正：正则排除 dunder（`__x__`）。
      (2) `MATERIALIZE.rms_*` —— 这是**通配简写**（指 rms_frame_length 与
          rms_hop_length 两个字段），FILE-202 的写法是合理的。
          修正：结尾为 `_` 或以 `_` 收尾的片段视为通配，跳过。
      ⇒ 又一次印证：**把"形式"当"实质"是我这类检查器最容易犯的错**，
        与检查⑨（TCP 端口）、检查⑪（折行）是同一族。
    """
    print()
    print("─" * 72)
    print("⑮ Build Instruction 引用的符号是否存在")
    print("─" * 72)

    import harmonica_eval.contract as _c
    import harmonica_eval.profile as _p

    real: dict[str, set[str]] = {
        "ErrorCode": {e.name for e in _c.ErrorCode},
        "MATERIALIZE": set(_p.MATERIALIZE.__dataclass_fields__),
        "AUDIO": set(_p.AUDIO.__dataclass_fields__),
        "ALIGN": set(_p.ALIGN.__dataclass_fields__),
        "FIELD_LAYOUTS": set(_c.FIELD_LAYOUTS),
    }

    # 引用的正则形态。
    # `[a-zA-Z_]` 开头 + `[a-z_]` 后续，但**排除 dunder**（由 _is_wildcard 兜住）。
    ref_patterns = [
        (re.compile(r"ErrorCode\.([A-Z_]{3,})"), "ErrorCode"),
        (re.compile(r"MATERIALIZE\.([a-z_]{2,})"), "MATERIALIZE"),
        (re.compile(r"\bAUDIO\.([a-z_]{2,})"), "AUDIO"),
        (re.compile(r"\bALIGN\.([a-z_]{2,})"), "ALIGN"),
        (re.compile(r"FIELD_LAYOUTS\[['\"]([a-z_]+)['\"]\]"), "FIELD_LAYOUTS"),
    ]

    # ★ 扩展（本版新增，补上一个真实缺口）：
    #   扫描 `<module>.<function>()` 形态的引用，验证函数真的存在于那个模块。
    #
    #   为什么加：我在修 FILE-104 时，为了让派发表"看起来完整"，
    #   编造了 `core.surface.materialize_pcm_mapped` / `materialize_pcm_warped`
    #   两个**不存在**的函数名。检查⑮ 当时**没能抓住** ——
    #   因为它只认 ErrorCode/MATERIALIZE/AUDIO/ALIGN 那几种前缀。
    #   这类「模块路径 + 函数名」的编造是最容易发生的（看起来最合理），
    #   所以必须机械兜住。
    import importlib
    # ★ 必须同时匹配两种写法（第一版只匹配了带括号的那种，实测漏报）：
    #     `core.surface.materialize_pcm_mapped(...)`   ← 带括号调用
    #     `core.surface.materialize_pcm_mapped`        ← 反引号内的纯名字
    #   我当初编造函数名时写的正是**后者**（不带括号），
    #   所以只匹配 `\s*\(` 的版本**漏报了真实案例**。
    #   现在允许：紧跟 `(`，或紧跟反引号，或行尾。
    MODULE_FN = re.compile(
        r"(?:harmonica_eval\.)?(core|algorithms|host|cockpit)\.([a-z_][a-z0-9_]*)\."
        r"([a-z_][a-z0-9_]{2,})(?=\s*\(|`|\s*$|\s*[，。、）)])"
    )
    # ★ 误报排除（第一版实测抓到 1 处）：
    #   `harmonica_eval.core.__doc__.splitlines()` —— 正则会把
    #   `core` + `__doc__` + `splitlines` 当成「模块.模块.函数」，
    #   但中间那截是 **dunder 属性**，后面那个是**字符串方法**，
    #   跟"该包里有没有这个函数"毫无关系。
    #   判据：中间段以 `__` 开头即跳过（`mod` 为 dunder ⇒ 不是模块名）。
    #   这是本检查器的第 3 次同类误报（前两次见 ⑨ TCP 端口、⑪ 中文折行），
    #   根因仍是**把形式当实质**。
    # 端口/字段名里也有点，但那不是模块路径 —— 只认这 4 个已知包名

    def _module_functions(pkg: str) -> set[str] | None:
        """收集 `harmonica_eval.<pkg>.*` 下所有模块的公开函数名。"""
        base = REPO / "harmonica_eval" / pkg
        if not base.is_dir():
            return None
        names: set[str] = set()
        for py in base.rglob("*.py"):
            try:
                mod = importlib.import_module(
                    "harmonica_eval." + py.relative_to(REPO / "harmonica_eval")
                    .with_suffix("").as_posix().replace("/", ".")
                )
            except Exception:
                continue
            names |= {
                n for n, _ in inspect.getmembers(mod, inspect.isfunction)
                if not n.startswith("_")
            }
            names |= {
                n for n, _ in inspect.getmembers(mod, inspect.isclass)
                if not n.startswith("_")
            }
        return names

    _pkg_fns = {p: _module_functions(p) for p in ("core", "algorithms", "host", "cockpit")}

    # 不存在的模块路径（真实是包根的 profile / contract）
    bad_module = re.compile(r"harmonica_eval\.core\.(profile|contract)\b")
    # 更正标记（按窗口判断，防折行）
    EXEMPT = ("不存在", "是错的", "上一版", "ModuleNotFoundError", "更正",
              "原写", "伪造", "历史", "已作废", "编造", "我自己的错",
              "诚实记录", "缺口")

    def _skip(name: str) -> bool:
        """是否应跳过这个属性名（dunder / 通配简写）。"""
        if name.startswith("__") and name.endswith("__"):
            return True          # dunder：dataclass 协议等
        if name.endswith("_"):
            return True          # 通配简写，如 rms_ / chroma_
        return False

    bi_dir = REPO / ".spec" / "build"
    if not bi_dir.is_dir():
        print("  ⚠️  .spec/build/ 不存在，跳过")
        return

    hits: list[str] = []
    n_refs = 0

    for path in sorted(bi_dir.glob("FILE-*-v1.md")):
        body = path.read_text(encoding="utf-8")
        lines = body.splitlines()

        # ① 符号引用
        for lineno, line in enumerate(lines, 1):
            window = "\n".join(lines[max(0, lineno - 3) : lineno + 2])
            if any(k in window for k in EXEMPT):
                continue
            for pat, family in ref_patterns:
                for m in pat.finditer(line):
                    name = m.group(1)
                    if _skip(name):
                        continue
                    n_refs += 1
                    if name in real[family]:
                        continue
                    hits.append(
                        f"{path.name}:{lineno} 引用不存在的 {family}.{name}"
                    )

        # ② 模块路径
        for lineno, line in enumerate(lines, 1):
            window = "\n".join(lines[max(0, lineno - 3) : lineno + 2])
            if any(k in window for k in EXEMPT):
                continue
            for m in bad_module.finditer(line):
                hits.append(
                    f"{path.name}:{lineno} 引用不存在的模块 "
                    f"harmonica_eval.core.{m.group(1)}（真实位置是包根）"
                )

        # ③ ★ 新增：`<pkg>.<module>.<function>(` 形态 —— 函数真的存在吗
        for lineno, line in enumerate(lines, 1):
            window = "\n".join(lines[max(0, lineno - 3) : lineno + 2])
            if any(k in window for k in EXEMPT):
                continue
            for m in MODULE_FN.finditer(line):
                pkg, mod, fn = m.group(1), m.group(2), m.group(3)
                if mod.startswith("__") and mod.endswith("__"):
                    continue          # dunder 属性，不是子模块名
                known = _pkg_fns.get(pkg)
                if known is None:
                    continue
                n_refs += 1
                if fn in known:
                    continue
                hits.append(
                    f"{path.name}:{lineno} 引用不存在的函数 "
                    f"{pkg}.…{fn}()（该包下无此公开函数/类）"
                )

    for h in hits:
        print(f"  ❌ {h}")
        r.err(h)

    print(f"  检查了 {n_refs} 处符号引用（跨 {len(list(bi_dir.glob('FILE-*-v1.md')))} 份文档）")
    if not hits:
        print("  ✅ 全部引用的符号与模块真实存在")


def _balanced_parens(text: str, open_idx: int) -> str | None:
    """从 `text[open_idx] == '('` 起，返回配对括号内的子串（不含括号）。

    正确处理嵌套（`[` / `]` / `{` / `}` 与括号一起计数），
    这样 `Mapping[str, npt.NDArray]` 这类注解不会把签名提前截断。
    """
    if open_idx >= len(text) or text[open_idx] != "(":
        return None
    depth = 0
    for i in range(open_idx, len(text)):
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i]
    return None


def check_bi_skeleton_signatures(r: Report) -> None:
    """⑱：BI 声明的函数签名 vs 骨架真实签名 —— 参数名逐字比对。

    ★ 为什么需要这个检查：
    本仓已两次出现「BI 改了签名、骨架没跟着改」（或反过来）：
      · R2-A-1  给 write_metrics_json / render_report_markdown 加 URI 入参，
                骨架在下一轮被并发操作回退，BI 却保留 → 两边不一致
      · BLOCK-9 materialize_chroma 加 sample_rate，同批只改了骨架与 BI 之一
    实现者拿到的两份文件互相矛盾时，他只能猜 —— 而猜错不报错。

    口径：只比**参数名**，不比类型标注
    （BI 常写 `view: UiView`，骨架也写，但历史上有过只写 `view` 的写法，
     那种简写是合法的；参数**个数与顺序**才是有约束力的）。
    只检查 BI 里以 `### N.N ` + 反引号 + `name(args)` + 反引号
    形式**显式声明**了签名的函数；
    BI 用散文描述签名的不在此列（那由盲审覆盖）。
    """
    import ast
    import re as _re

    pairs = {
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

    def param_names(sig: str) -> list[str]:
        """抽参数名。

        ★ 必须只在**顶层**逗号处切分：`Mapping[str, npt.NDArray]` 里的逗号
        不是参数分隔符。本检查第一版用 `sig.split(",")`，
        于是 `assert_budget(ports: Mapping[str, npt.NDArray])` 被切成
        两个「参数」（`ports` 与 `npt.NDArray]`），报出假阳性 ——
        是 ⑱ 自己把这个 bug 报出来的。
        """
        parts: list[str] = []
        depth = 0
        cur = ""
        for ch in sig:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        if cur:
            parts.append(cur)
        out = []
        for part in parts:
            name = part.split(":")[0].split("=")[0].strip()
            if name and name not in ("self", "cls", "/", "*"):
                out.append(name)
        return out

    checked = 0
    for py_rel, md_rel in pairs.items():
        py = Path(py_rel)
        md = Path(md_rel)
        if not py.exists() or not md.exists():
            continue
        doc = md.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("__"):
                continue
            sk = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
            if not sk:
                continue
            # 标题形态：`### 4.3 `name(a, b) -> T`` —— 节号在名字之前
            # ★ 必须平衡括号：签名里可能有嵌套泛型
            #   （如 `assert_budget(ports: Mapping[str, npt.NDArray]) -> int`），
            #   用 `[^)]*` 会在内层 `]` 前的 `)` 上截断，把类型注解误当参数名。
            #   （本检查第一版就踩了这个坑，被 ⑱ 自己报了出来。）
            m = _re.search(
                r"\n#+ +[^\n`]*`" + _re.escape(node.name) + r"\s*\(",
                doc,
            )
            if not m:
                continue
            sig = _balanced_parens(doc, m.end() - 1)
            if sig is None:
                continue
            bi = param_names(sig)
            if not bi:
                continue
            checked += 1
            if sk != bi:
                r.err(
                    f"⑱ {py_rel}:{node.lineno} {node.name}() 骨架参数 {sk} "
                    f"≠ BI 声明 {bi}（{md_rel}）"
                )
    r.stats["⑱ 签名一致性"] = f"比对了 {checked} 处，全部一致"


def check_subprocess_checks(r: Report) -> None:
    """⑯⑰：把独立检查脚本挂进总检查。

    ★ 为什么这两个单独成脚本而不是内联：
    它们要能**被单独跑、单独注入回归验证**。
    方法论 §6.3 说「一个永远不会变红的检查等于没有检查」——
    本仓已经出现过两次「检查器自己坏了却报绿」：
      · check ⑮ 第一版漏掉裸反引号形态的伪符号
      · check_reachability.py 第一版正则匹配不到任何标题，
        12 处「检查」全是空转
    故这两个检查器的**回归注入**是它们存在的证据，见各自 docstring。
    """
    import subprocess

    for script, label in (
        ("tools/check_reachability.py", "⑯ 可达性审计"),
        ("tools/check_xref.py", "⑰ 交叉引用完整性"),
        ("tools/check_bi_scripts.py", "⑲ BI §8 脚本"),
        ("tools/check_counts.py", "㉑ 计数声明一致性"),
    ):
        path = Path(script)
        if not path.exists():
            r.err(f"{label}：脚本 {script} 不存在")
            continue
        proc = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        out = (proc.stdout or "").strip()
        # 把脚本自己的结论行转述进总报告
        summary = out.splitlines()[-1].strip() if out else "(无输出)"
        r.stats[label] = summary
        if proc.returncode != 0:
            for line in out.splitlines():
                if line.strip().startswith("❌"):
                    r.err(f"{label}：{line.strip()}")


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
    check_invariant_f_importable_without_cockpit(r)
    check_forbidden_on_host(r)
    check_no_shadowing(r)
    check_contract_signatures(r)
    check_doc_port_count(r)
    check_plugin_contract_consistency(r)
    check_constitution_citations(r)
    check_doc_symbol_drift(r)
    check_registry_signature_consistency(r)
    check_build_instruction_completeness(r)
    check_bi_symbol_references(r)
    # ⑯⑰ 是独立脚本（各自可单独跑、各自有 exit code）。
    # 它们检查的是**跨语句**的缺陷：可达性与交叉引用 ——
    # 这类缺陷每一句单独看都对，错在两句之间，读一遍发现不了。
    check_bi_skeleton_signatures(r)
    check_subprocess_checks(r)

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
