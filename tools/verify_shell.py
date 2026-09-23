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
        tree = _ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        out: dict[str, list[str]] = {}
        for node in _ast.walk(tree):
            if isinstance(node, _ast.ClassDef) and node.name == cls_name:
                for sub in node.body:
                    if isinstance(sub, _ast.FunctionDef):
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


def check_timing_payload_consistency(r: Report) -> None:
    """⑩ 算法模块的 payload 键名与冻结表一致。

    ★ 被一次真实事故逼出来的（§20 盲审第二轮发现）：
    我新增 `PAYLOAD_SCHEMAS` 时，不知道 `timing.py` 正文的 docstring
    已经写了另一套键名（`median_ms` / `mad_ms` / `n_matched` / `n_unmatched`）。
    于是**同一份事实有了两个互相冲突的来源**：
      - 模块说"我产出这些键"
      - 注册表说"必须恰好产出那些键"
    实现者无法同时满足，而两者都不会在 import 时报错。

    这与 `FIELD_LAYOUTS` 是**同一个教训的第三次出现**
    （前两次：`hop_length` 未声明、端口对称性破裂）。
    故用机械检查兜住：模块 OUTPUT 段声明的键必须与注册表逐字一致。
    """
    print()
    print("─" * 72)
    print("⑩ 算法 payload 键名 ↔ 冻结表")
    print("─" * 72)

    sys.path.insert(0, str(REPO))
    try:
        from harmonica_eval.algorithms import PAYLOAD_SCHEMAS
    except Exception as exc:
        msg = f"无法导入 PAYLOAD_SCHEMAS: {exc}"
        print(f"  ❌ {msg}")
        r.err(msg)
        return

    hits: list[str] = []
    for algo, keys in PAYLOAD_SCHEMAS.items():
        path = PKG / "algorithms" / f"{algo}.py"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")

        # 找 "现统一到冻结表" 之类的清单块（我们冻结的写法）
        blocks = re.findall(
            r"冻结表的\s*\d+\s*个键：(.*?)\n\s*\"\"\"", text, re.S
        )
        if not blocks:
            continue  # 该模块尚未采用显式清单写法
        declared = re.findall(r"^\s+(\w+)\s{2,}", blocks[0], re.M)
        if declared != list(keys):
            hits.append(
                f"{algo}.py 声明的键 {declared} "
                f"与 PAYLOAD_SCHEMAS 的 {list(keys)} 不一致"
            )

    for h in hits:
        print(f"  ❌ {h}")
        r.err(h)

    print(f"  检查了 {len(PAYLOAD_SCHEMAS)} 个算法的 payload 键表")
    if not hits:
        print("  ✅ 模块声明与冻结表逐字一致")


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
      对每个算法，若其入口模块里**存在**某个公开函数的 docstring
      声称产出 `逐音`/`per_note` 结果，则同模块内**必须**有某个公开函数
      的形参名里出现音符边界类词根（note / onset / span / bound）——
      否则报错。

    ★ 第一版把词根收窄成只有 `note`，刷出 **1 条误报**：
        timing.py 的 `match_onsets(ref_onsets, prac_onsets, tolerance_sec)`
        **确实**接收了音符边界（起音时刻就是边界），只是变量名叫 onset 不叫 note。
      这正是本仓在检查⑪、⑫ 上重复吃过的亏：**过宽的检查制造噪声，
      过窄的检查漏掉真缺陷**。现按实际语义补齐词根，并在此记录该误报。

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

    for path in sorted(alg_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        src = path.read_text(encoding="utf-8")
        tree = _ast.parse(src, filename=str(path))

        claims_per_note = False
        params_by_func: dict[str, list[str]] = {}
        for node in tree.body:
            if not isinstance(node, _ast.FunctionDef):
                continue
            params_by_func[node.name] = [a.arg for a in node.args.args]
            ds = _ast.get_docstring(node) or ""
            if "逐音" in ds or "per_note" in ds:
                claims_per_note = True

        if not claims_per_note:
            continue
        checked += 1

        has_note_param = any(
            any(root in p.lower() for root in BOUNDARY_ROOTS)
            for params in params_by_func.values()
            for p in params
        )
        if not has_note_param:
            funcs = ", ".join(
                f"{n}({', '.join(p)})" for n, p in params_by_func.items()
            )
            hits.append(
                f"{path.name} 的 docstring 声称产出『逐音』结果，"
                f"但没有任何函数接收音符边界（note/onset/span/bound）—— "
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
    # 不存在的模块路径（真实是包根的 profile / contract）
    bad_module = re.compile(r"harmonica_eval\.core\.(profile|contract)\b")
    # 更正标记（按窗口判断，防折行）
    EXEMPT = ("不存在", "是错的", "上一版", "ModuleNotFoundError", "更正",
              "原写", "伪造", "历史", "已作废")

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

    for h in hits:
        print(f"  ❌ {h}")
        r.err(h)

    print(f"  检查了 {n_refs} 处符号引用（跨 {len(list(bi_dir.glob('FILE-*-v1.md')))} 份文档）")
    if not hits:
        print("  ✅ 全部引用的符号与模块真实存在")


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
    check_contract_signatures(r)
    check_doc_port_count(r)
    check_timing_payload_consistency(r)
    check_constitution_citations(r)
    check_doc_symbol_drift(r)
    check_registry_signature_consistency(r)
    check_build_instruction_completeness(r)
    check_bi_symbol_references(r)

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
