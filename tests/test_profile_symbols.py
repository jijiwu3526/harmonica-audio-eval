"""profile 顶层符号的防复发护栏。

★ **本文件的核心设计：全部断言走 AST 解析源码，不 import 被保护的那个符号。**

## 为什么不能 import

本项目发生过一次真实事故（profile.py 被完整重写，语法正常）：

    ★ 两个顶层符号被删 → core/surface.py、algorithms/bootstrap.py、
      tests/test_smoke_injection.py 全部 ImportError
    ★ profile.py 自身【语法正常】—— 所有「语法级」守卫都失效了
    ★ ★ ★ 而 test_smoke_injection.py 里的护栏依赖那两个符号，
      ★ ★ ★ 所以它跟着一起崩 —— 那一刻没有任何守卫发出信号

若本文件也 `import SAMPLE_RATE_FREE_PREFIXES`，事故重演时它会
跟着 ImportError，**所有守卫同时失效**——正是事故的形态。

所以这里一律用 `ast.parse` 读源码。符号消失时，测试会**因
「断言不成立」而红**，而不是因「无法 import」而崩。区别在于
前者指向真正的根因，后者只说「有东西坏了」。

## 断言清单

    A  名单是【字面量常量】—— 不是推导式
    B  内容锚定为 {"chroma", "warp_path", "notes"}
    C  ★ 反例锚定：pcm 【不在】名单里（hop==0 但不该免采样率）
    D  port_prefix 按「第一个点」切分，无点时返回原串
    E  两个符号都在 __all__ 里
    F  ★ 反向：__all__ 里每个名字都真实存在
    G  ★ 三方引用同源（profile / surface / bootstrap 不各写一份）
"""

from __future__ import annotations

import ast
import pathlib

import pytest

PROFILE_PY = pathlib.Path(__file__).resolve().parent.parent / "harmonica_eval" / "profile.py"
SURFACE_PY = pathlib.Path(__file__).resolve().parent.parent / "harmonica_eval" / "core" / "surface.py"
BOOTSTRAP_PY = (
    pathlib.Path(__file__).resolve().parent.parent
    / "harmonica_eval" / "algorithms" / "bootstrap.py"
)

EXPECTED_PREFIXES = frozenset({"chroma", "warp_path", "notes"})


def _tree(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _find_assignment(tree: ast.Module, name: str) -> ast.Assign | ast.AnnAssign:
    """取模块级对 `name` 的赋值节点。找不到就断言失败（而不是返回 None 让调用方踩空）。"""
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return node
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node
    raise AssertionError(f"profile.py 里找不到顶层赋值 {name} —— 符号被删了？")


def _all_names(tree: ast.Module) -> list[str]:
    node = _find_assignment(tree, "__all__")
    value = node.value
    assert isinstance(value, (ast.List, ast.Tuple)), "__all__ 必须是字面量列表/元组"
    out: list[str] = []
    for elt in value.elts:  # type: ignore[attr-defined]
        assert isinstance(elt, ast.Constant) and isinstance(elt.value, str), (
            "__all__ 每项必须是字符串字面量"
        )
        out.append(elt.value)
    return out


# ══════════════════════════════════════════════════════════════════
# A · 名单必须是字面量，不是推导式
# ══════════════════════════════════════════════════════════════════


def test_free_prefixes_is_a_literal_not_a_comprehension() -> None:
    """A：把名单改成推导式 → 红。

    推导式（`{p for p in PORTS if p.hop_length == 0}`）会把 pcm 错误地
    算进去 —— 那是 C 那条断言要防的实际后果。
    """
    node = _find_assignment(_tree(PROFILE_PY), "SAMPLE_RATE_FREE_PREFIXES")
    value = node.value
    assert not isinstance(value, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)), (
        "SAMPLE_RATE_FREE_PREFIXES 必须是字面量 —— "
        "推导式会把 pcm.mapped.* 也算进去（它 hop==0 但不该免采样率）"
    )


# ══════════════════════════════════════════════════════════════════
# B · 内容锚定
# ══════════════════════════════════════════════════════════════════


def test_free_prefixes_contents_are_exactly_the_three() -> None:
    """B：加 pcm / 删一个 / 加别的 → 各自都应红。"""
    node = _find_assignment(_tree(PROFILE_PY), "SAMPLE_RATE_FREE_PREFIXES")
    call = node.value
    assert isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "frozenset", (
        "应为 frozenset({...}) 字面量调用"
    )
    assert not call.args or isinstance(call.args[0], (ast.Set, ast.List, ast.Tuple)), "frozenset 的参数应是字面量集合"
    inner = call.args[0]
    got = {e.value for e in inner.elts}  # type: ignore[attr-defined]
    assert got == set(EXPECTED_PREFIXES), (
        f"名单内容应为 {sorted(EXPECTED_PREFIXES)}，实得 {sorted(got)}"
    )


# ══════════════════════════════════════════════════════════════════
# C · ★ 反例锚定 —— 本文件的核心
# ══════════════════════════════════════════════════════════════════


def test_pcm_is_excluded_because_it_is_a_sample_sequence() -> None:
    """C：★ pcm.mapped.* 的 hop 也是 0，但它【不在】名单里。

    理由：pcm.mapped.* 描述的是采样点序列本身，两侧都取 44100。
    若按「凡 hop==0 就免采样率」推导，会把它错误排除，
    `runtime.resolve_inputs` 的精确匹配会把它判为不可用。
    ★ 这条断言是为了让「用推导式重写名单」这个念头立刻失败。
    """
    assert "pcm" not in EXPECTED_PREFIXES, "pcm 不得进名单（采样点序列，两侧都取 44100）"

    # 同一事实必须在源码里也成立，而不只是测试里的期望值
    node = _find_assignment(_tree(PROFILE_PY), "SAMPLE_RATE_FREE_PREFIXES")
    call = node.value
    assert isinstance(call, ast.Call) and call.args
    names = {e.value for e in call.args[0].elts}  # type: ignore[union-attr]
    assert "pcm" not in names, "源码名单里出现了 pcm —— 与上面的理由矛盾"

    # 而 pcm.mapped.* 的 hop 确实为 0（所以「推导式」这条捷径才诱人）
    pcm_hops: set[object] = set()
    saw_pcm = False
    for node in _tree(PROFILE_PY).body:
        if not (isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "PORTS"):
            continue
        assert isinstance(node.value, ast.Tuple), "PORTS 应是字面量元组 —— 本测试的对照前提失效"
        for elt in node.value.elts:  # type: ignore[attr-defined]
            if not isinstance(elt, ast.Call) or not isinstance(elt.func, ast.Name):
                continue
            kw = {k.arg: k.value for k in elt.keywords}
            pid = ast.literal_eval(kw["port_id"]) if "port_id" in kw else ""
            if not pid.startswith("pcm."):
                continue
            saw_pcm = True
            if "hop_length" in kw:
                pcm_hops.add(ast.literal_eval(kw["hop_length"]))
    assert saw_pcm, "PORTS 里没有 pcm.* 条目 —— 本测试的对照前提失效，请重新核实"
    assert pcm_hops == {0}, (
        f"pcm.mapped.* 的 hop 应为 0（实测 {pcm_hops}）—— "
        "若前提变了，「hop==0 就免采样率」这条捷径就不再诱人，本断言需重新论证"
    )


# ══════════════════════════════════════════════════════════════════
# D · port_prefix 语义
# ══════════════════════════════════════════════════════════════════


def _port_prefix_fn(tree: ast.Module) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "port_prefix":
            return node
    raise AssertionError("profile.py 里找不到 port_prefix 函数 —— 符号被删了？")


def test_port_prefix_splits_on_first_dot() -> None:
    """D：改成 split('.') 或取错下标 → 应红。

    关键语义：`warp_path` 没有点，必须返回原串。名单里恰好有它，
    所以这个反例是真实会发生的，不是假想。
    """
    fn = _port_prefix_fn(_tree(PROFILE_PY))
    # ★ 只看可执行语句，不看 docstring —— 否则我写的说明文字会触发自己的断言
    stmts = [s for s in fn.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
    calls = [n for s in stmts for n in ast.walk(s) if isinstance(n, ast.Call)]
    methods = [c.func.attr for c in calls if isinstance(c.func, ast.Attribute)]
    assert "partition" in methods, (
        "port_prefix 应用 partition('.') —— split('.') 在无点时语义不同，"
        f"而 warp_path 正是无点的 port_id（实得调用：{methods}）"
    )
    assert "split" not in methods, "正文里不该出现 split —— 那会丢掉「无分隔符」这层语义"

    # 分隔符必须是单个点，且用 sep 分支区分「有分隔符 / 无分隔符」
    part = next(c for c in calls if isinstance(c.func, ast.Attribute) and c.func.attr == "partition")
    assert len(part.args) == 1 and ast.literal_eval(part.args[0]) == ".", "分隔符必须是 '.'"
    assigned: set[str] = set()
    for s in stmts:
        if isinstance(s, ast.Assign):
            for t in s.targets:
                if isinstance(t, ast.Name):
                    assigned.add(t.id)
                elif isinstance(t, (ast.Tuple, ast.List)):  # ★ head, sep, _tail = ... 是元组解包
                    assigned.update(e.id for e in t.elts if isinstance(e, ast.Name))
    assert "sep" in assigned, f"应通过 sep 区分「有分隔符 / 无分隔符」两种情况（实得 {assigned}）"


# ══════════════════════════════════════════════════════════════════
# E · 两个符号都在 __all__
# ══════════════════════════════════════════════════════════════════


def test_both_symbols_are_exported() -> None:
    """E：从 __all__ 删掉任一个 → 红。"""
    names = _all_names(_tree(PROFILE_PY))
    for required in ("SAMPLE_RATE_FREE_PREFIXES", "port_prefix"):
        assert required in names, f"{required} 必须在 __all__ 里（它被三方引用）"


# ══════════════════════════════════════════════════════════════════
# F · ★ 反向：__all__ 里的每个名字都真实存在
# ══════════════════════════════════════════════════════════════════


def test_every_dunder_all_name_is_actually_defined() -> None:
    """F：在 __all__ 写一个不存在的名字 → 红。

    这是「声明了但没有」的反向。本项目一直只查「用了但没定义」，
    这次事故属于另一侧：符号没定义，也没人声明。
    """
    tree = _tree(PROFILE_PY)
    defined: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            defined.update(t.id for t in targets if isinstance(t, ast.Name))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                defined.add(alias.asname or alias.name.split(".")[0])

    missing = [n for n in _all_names(tree) if n not in defined]
    assert not missing, f"__all__ 声明了但文件里找不到定义：{missing}"


# ══════════════════════════════════════════════════════════════════
# G · ★ 三方引用同源
# ══════════════════════════════════════════════════════════════════


def test_three_callers_reference_the_same_source() -> None:
    """G：改一侧的引用名 → 红。

    防止「一侧改名另一侧没跟」—— 事故当天就是三方同时 ImportError，
    而这里要的是**更早**、**只指一处**的信号。
    """
    surface_src = SURFACE_PY.read_text(encoding="utf-8")
    assert "profile.SAMPLE_RATE_FREE_PREFIXES" in surface_src, (
        "surface.py 必须引用 profile.SAMPLE_RATE_FREE_PREFIXES，不得本地再写一份名单"
    )
    # surface 侧那条 AnnAssign 的值应【就是】那个属性引用（不是副本、不是推导式）
    ref = next(
        n.value
        for n in _tree(SURFACE_PY).body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id == "_SAMPLE_RATE_FREE_PREFIXES"
    )
    assert isinstance(ref, ast.Attribute) and ref.attr == "SAMPLE_RATE_FREE_PREFIXES", (
        "surface.py 侧的名单必须是 profile 那个的属性引用（写成别的形态就会变成本地副本）"
    )
    assert isinstance(ref.value, ast.Name) and ref.value.id == "profile", (
        "引用主体必须是 profile 模块本身"
    )

    boot_src = BOOTSTRAP_PY.read_text(encoding="utf-8")
    for required in ("SAMPLE_RATE_FREE_PREFIXES", "port_prefix"):
        assert required in boot_src, f"bootstrap.py 必须从 profile import {required}"


# ══════════════════════════════════════════════════════════════════
# ★★ 最关键的一条：删掉符号，本文件仍能红（而不是跟着崩）
# ══════════════════════════════════════════════════════════════════


def test_guard_detects_missing_symbols_without_importing_them() -> None:
    """★ 证明护栏独立于被护对象。

    本测试自己构造一份「符号被删」的 profile 源码（字符串，不碰真文件），
    然后跑同样的 AST 断言 —— 断言必须**因缺失而失败**，
    而不是因为 import 不到而崩。
    """
    original = PROFILE_PY.read_text(encoding="utf-8")
    tree = ast.parse(original)
    doomed = {"SAMPLE_RATE_FREE_PREFIXES", "port_prefix"}

    def _declared_name(node: ast.stmt) -> str | None:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            return node.target.id
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    return t.id
        if isinstance(node, ast.FunctionDef):
            return node.name
        return None

    # 从 AST 里摘掉那两个顶层定义，得到「事故后」的源码
    kept = [n for n in tree.body if _declared_name(n) not in doomed]
    assert len(kept) == len(tree.body) - len(doomed), "没能摘掉全部目标定义 —— 本测试自身失效"
    tree.body = kept

    m_tree = ast.parse(ast.unparse(ast.fix_missing_locations(tree)))

    # ★ 关键：同样的查找必须【抛 AssertionError】，而不是让本测试崩
    raised: list[str] = []
    for symbol in sorted(doomed):
        try:
            _find_assignment(m_tree, symbol)
        except AssertionError:
            raised.append(symbol)
    assert set(raised) == doomed, (
        f"护栏只对 {sorted(raised)} 报警，应覆盖 {sorted(doomed)} —— "
        "那意味着真出事故时也没有信号"
    )

    # 而 __all__ 那条反向断言此刻应当【也红】（它仍声明着已消失的名字）
    with pytest.raises(AssertionError, match="定义"):
        _all_names_check(m_tree)


def _all_names_check(tree: ast.Module) -> list[str]:
    """F 那条断言的内联版：__all__ 里的名字若都不存在则抛错。"""
    names = _all_names(tree)
    defined: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            defined.update(t.id for t in targets if isinstance(t, ast.Name))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                defined.add(alias.asname or alias.name.split(".")[0])
    missing = [n for n in names if n not in defined]
    assert not missing, f"__all__ 声明了但文件里找不到定义：{missing}"
    return names
