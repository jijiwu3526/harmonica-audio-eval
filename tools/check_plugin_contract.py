#!/usr/bin/env python3
"""C3 插件契约架构检查器。

只写契约测试：不实现算法，不实现 Registry / Runtime，也不执行任何空壳。
默认检查仓库现状；``--inject <case>`` 只在内存中注入一个违规对象，
证明同一个检查函数会变红，并立即丢弃注入对象、恢复为内存中的干净基线。

用法：
    python3 tools/check_plugin_contract.py
    python3 tools/check_plugin_contract.py --inject core-import
    python3 tools/check_plugin_contract.py --inject all

退出码：
    默认模式：0 全部通过；1 发现违规。
    注入模式：0 不使用（故意注入过违规）；1 已按预期捕获注入，或自证失败。
"""

from __future__ import annotations

import argparse
import ast
import collections.abc
import copy
import dataclasses
import importlib
import math
import re
import sys
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "harmonica_eval"
ALGORITHMS_DIR = PKG / "algorithms"

# ★ 已授权注入文件从唯一真相源派生（不再在本文件维护副本）。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from authorized_impl import PKG_REL as _AUTHORIZED_PKG_REL  # noqa: E402

# ★ 契约类型是已实现地基；这里只 import 形状类型，不调用任何空壳。
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from harmonica_eval.contract import UiScalar, UiSeries  # noqa: E402

STATUS_VALUES = frozenset({"OK", "DEGRADED", "INCOMPATIBLE", "FAILED"})
REQUIRED_UNITS = frozenset({"cents", "db", "seconds", "ratio", "count"})
ALGORITHMS_PUBLIC_EXPORTS = frozenset({"InputRequirement", "PluginSpec", "Registry"})

# ★ 这些名字允许留在 docstring / 注释里作为历史记录；只有代码与注解命中才红。
# ★ 意图：穷举**全部具体 payload 字段名**（含无量纲的 n_notes_used / n_unpaired），
#   使框架代码永远不认识任何具体字段，payload 完全自描述。
#   故 2026-xx 改名 ms→sec 后，**新旧名都必须列入**：
#   旧名锁历史（防止回退），新名锁当前（防止框架认字段）。
#   只锁旧名会让改名后的新名可被框架合法引用，本检查等于失效。
FORBIDDEN_PAYLOAD_FIELDS = (
    "median_abs_cents",
    "median_onset_ms",
    "median_onset_sec",  # ★ 现名（ms→sec 裁定后）
    "median_db",
    "off_pitch_ratio",
    "per_note_cents",
    "per_note_onset_ms",
    "per_note_onset_sec",  # ★ 现名（ms→sec 裁定后）
    "per_note_delta_db",
    "early_ratio",
    "late_ratio",
    "on_time_ratio",
    "spread_ms",
    "spread_sec",  # ★ 现名（ms→sec 裁定后）
    "spread_db",
    "n_notes_used",
    "n_unpaired",
)
SHELL_MESSAGE = re.compile(r"SHELL: FILE-\d+ 待注入实现")
NUMBERS = ("①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩", "⑪")
PAYLOAD_TYPES: tuple[type, type] = (UiScalar, UiSeries)


@dataclass
class Outcome:
    """一个检查函数的可展示结果。"""

    errors: list[str]
    evidence: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def make_outcome(
    errors: Iterable[str] = (),
    evidence: Iterable[str] = (),
) -> Outcome:
    return Outcome(list(errors), list(evidence))


def parse_path(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def python_files(base: Path) -> list[Path]:
    return sorted(base.rglob("*.py"))


def algorithm_files() -> list[Path]:
    return sorted(ALGORITHMS_DIR.glob("*.py"))


# ★ 已授权注入的文件 —— 按**包内相对路径**判定，不是文件名 / 目录 / 前缀。
# ★ ★ 本表不再在此维护 —— 派生自 tools/authorized_impl.py（唯一真相源）；
# ★   「哪次授权、依据哪份 BI」在该文件里逐条记录，可查。
#   下方那句「algorithms/ 下其它文件仍逐个受空壳检查」已随注入推进过期：
#   ★ 现在 bootstrap / registry / runtime / pitch / timing / dynamics 六个都已授权，
#   ★ 真正仍受空壳检查的是 `algorithms/__init__.py`（门面，未注入）。
# ★ 已授权的文件**不被放弃检查**：它们仍在下方 `check_algorithm_shells`
#   的依赖方向扫描与 `run_normal_checks` 的框架面检查内，
#   且各自有对应 BI 的 §8 验收脚本逐条机械判定行为。
# ★ ★ 为什么不用 path.stem：同名文件放在不同目录会被一起放过。
#   例如将来若出现 `cockpit/registry.py`，用 stem 判定会连带豁免它 ——
#   那是「放宽成目录」之外的另一种漏网。相对路径不存在这种歧义。
AUTHORIZED_IMPLEMENTED_FILES: frozenset[str] = frozenset(_AUTHORIZED_PKG_REL)


def is_authorized_implemented(path: Path) -> bool:
    """是否属于已授权注入的文件。

    ★ 判定粒度是**包内相对路径**（`algorithms/bootstrap.py`），
      不是文件名（`bootstrap`）、不是目录、不是前缀。
      理由：同名文件位于不同目录时，文件名判定会连带豁免另一个。
    """
    try:
        rel = path.resolve().relative_to(PKG.resolve())
    except ValueError:
        return False
    return rel.as_posix() in AUTHORIZED_IMPLEMENTED_FILES


# 框架文件：不提供算法、不实现 run()、只做装配/登记/校验。
# ★ 判别依据是【结构特征】而不是名字清单：
#   具体算法模块必须实现算法入口（`def run(`），框架文件都不实现它。
# ★ ★ 为什么不按名字硬编码：bootstrap.py 是 GC-204-08「方案甲」裁定新增的
#   唯一物理装配根，它 import 具体算法但【不是】具体算法。
#   硬编码名字集合会漏掉任何后加入的框架文件 —— 那正是本条判据误报的原因。
# ★ ★ 依据：.spec/build/FILE-206-v1.md:361「装配根唯一性：只有本文件 import 具体算法」
_FRAMEWORK_STEMS = frozenset({"__init__"})


def _implements_algorithm_entry(path: Path) -> bool:
    """该模块是否定义了算法入口 `run(...)`。只看定义，不执行。"""
    try:
        tree = parse_path(path)
    except (OSError, SyntaxError, ValueError):
        return False
    return any(
        isinstance(node, ast.FunctionDef) and node.name == "run"
        for node in tree.body
    )


def concrete_algorithm_modules(files: Sequence[Path]) -> frozenset[str]:
    """具体算法模块 = 【自身实现了算法入口 run()】的算法层模块。

    ★ 框架文件（`__init__` / `registry` / `runtime` / `bootstrap`）都不定义
      `run()`，所以不会进入此集合；具体算法（pitch/timing/dynamics）都定义，
      所以必然进入。新增插件无需登记即自动受约束。
    ★ 判别是【精确模块名成员判断】，不依赖路径前缀，相似文件名不受影响。
    """
    return frozenset(
        p.stem for p in files if p.stem not in _FRAMEWORK_STEMS and _implements_algorithm_entry(p)
    )


def relative_import_base(path: Path, level: int) -> list[str]:
    """把相对 import 的 level 解析为仓库内模块包名，不执行 import。"""
    module_parts = list(path.relative_to(REPO).with_suffix("").parts)
    current_package = module_parts[:-1]
    if level <= 0:
        return []
    keep = max(0, len(current_package) - (level - 1))
    return current_package[:keep]


def import_targets(path: Path, node: ast.AST) -> list[tuple[int, str]]:
    """返回 import 节点涉及的所有目标模块（含 from X import Y 中的 Y）。"""
    if isinstance(node, ast.Import):
        return [(node.lineno, alias.name) for alias in node.names]

    if not isinstance(node, ast.ImportFrom):
        return []

    if node.level:
        base_parts = relative_import_base(path, node.level)
    else:
        base_parts = []

    if node.module:
        base_parts = base_parts + node.module.split(".")

    targets = [".".join(base_parts)] if base_parts else []
    targets.extend(
        ".".join(base_parts + [alias.name])
        for alias in node.names
        if base_parts
    )
    return [(node.lineno, target) for target in targets]


def targets_concrete_algorithm(
    target: str,
    concrete_names: frozenset[str],
) -> bool:
    parts = target.split(".")
    if "algorithms" not in parts:
        return False
    after_algorithms = parts[parts.index("algorithms") + 1 :]
    return any(name in after_algorithms for name in concrete_names)


def check_layer_has_no_concrete_algorithm_import(
    base: Path,
    concrete_names: frozenset[str],
    overrides: dict[Path, ast.AST] | None = None,
) -> Outcome:
    """core / host / cockpit 不得 import pitch、timing、dynamics 等实现。"""
    if not base.is_dir():
        return make_outcome([f"待扫描目录不存在：{base.relative_to(REPO)}"])

    paths = python_files(base)
    overrides = overrides or {}
    paths = sorted(set(paths) | set(overrides))
    if not paths:
        return make_outcome([f"目录没有任何 .py 文件：{base.relative_to(REPO)}"])

    errors: list[str] = []
    for path in paths:
        tree = overrides.get(path) or parse_path(path)
        for node in ast.walk(tree):
            for lineno, target in import_targets(path, node):
                if targets_concrete_algorithm(target, concrete_names):
                    errors.append(
                        f"{path.relative_to(REPO)}:{lineno} import 具体算法 {target}"
                    )

    return make_outcome(
        errors,
        [
            f"扫描 {len(paths)} 个文件；具体插件模块 = "
            f"{', '.join(sorted(concrete_names))}"
        ],
    )


def check_algorithms_have_no_reverse_imports(
    paths: Sequence[Path],
    overrides: dict[Path, ast.AST] | None = None,
) -> Outcome:
    """algorithms 只能向 contract 等地基依赖，不得反向依赖 C2/C1/C4。"""
    overrides = overrides or {}
    all_paths = sorted(set(paths) | set(overrides))
    if not all_paths:
        return make_outcome(["algorithms/ 下没有可扫描的 .py 文件"])

    forbidden = {"core", "host", "cockpit"}
    errors: list[str] = []
    for path in all_paths:
        tree = overrides.get(path) or parse_path(path)
        for node in ast.walk(tree):
            for lineno, target in import_targets(path, node):
                parts = set(target.split("."))
                bad = sorted(parts & forbidden)
                if bad:
                    errors.append(
                        f"{path.relative_to(REPO)}:{lineno} 反向 import "
                        f"{target}（命中 {', '.join(bad)}）"
                    )

    return make_outcome(
        errors,
        [f"扫描 algorithms/*.py 共 {len(all_paths)} 个文件"],
    )


def assignment_nodes(tree: ast.AST, wanted: str) -> list[ast.AST]:
    """找普通、注解、增强赋值以及命名表达式中的目标名。"""
    found: list[ast.AST] = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
            if isinstance(node.target, ast.Name):
                names.append(node.target.id)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                names.append(node.target.id)
        if wanted in names:
            found.append(node)
    return found


def assigned_literal(tree: ast.AST, name: str) -> object:
    nodes = assignment_nodes(tree, name)
    if len(nodes) != 1 or not isinstance(nodes[0], (ast.Assign, ast.AnnAssign)):
        raise ValueError(f"{name} 必须有且只有一个普通/注解赋值")
    value = nodes[0].value
    if value is None:
        raise ValueError(f"{name} 没有值")
    return ast.literal_eval(value)


def check_algorithms_public_surface(tree: ast.AST) -> Outcome:
    """框架出口不得保存算法表，__all__ 只能是三个稳定类型。"""
    errors: list[str] = []
    for forbidden_name in ("ALGORITHMS", "PAYLOAD_SCHEMAS"):
        if assignment_nodes(tree, forbidden_name):
            errors.append(f"algorithms/__init__.py 存在 {forbidden_name} 赋值")

    try:
        exports = assigned_literal(tree, "__all__")
    except (ValueError, TypeError, SyntaxError) as exc:
        errors.append(f"__all__ 不是可静态读取的字面量：{exc}")
        exports = None

    if isinstance(exports, (list, tuple)):
        if len(exports) != len(ALGORITHMS_PUBLIC_EXPORTS) or set(exports) != ALGORITHMS_PUBLIC_EXPORTS:
            errors.append(
                f"__all__ 必须恰好是 {sorted(ALGORITHMS_PUBLIC_EXPORTS)}，"
                f"实得 {list(exports)}"
            )
    elif exports is not None:
        errors.append(f"__all__ 必须是 list/tuple 字面量，实得 {type(exports).__name__}")

    return make_outcome(
        errors,
        ["只允许稳定类型出口：" + ", ".join(sorted(ALGORITHMS_PUBLIC_EXPORTS))],
    )


def check_host_has_no_algorithm_id_compare(
    trees: dict[Path, ast.AST],
) -> Outcome:
    """按指定 AST 规则：左操作数是 plugin_id/algorithm_id 的 Compare 全拒绝。"""
    identifiers = {"plugin_id", "algorithm_id"}
    errors: list[str] = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            if isinstance(node.left, ast.Name) and node.left.id in identifiers:
                errors.append(
                    f"{path.relative_to(REPO) if path.is_relative_to(REPO) else path}:"
                    f"{node.lineno} 出现按 {node.left.id} 比较的硬编码："
                    f"{ast.unparse(node)}"
                )
    return make_outcome(
        errors,
        [
            f"扫描 host/**/*.py 共 {len(trees)} 个文件；"
            "所有 Compare 的左侧 plugin_id / algorithm_id 命中数为 0"
        ]
        if not errors
        else [],
    )


class DropStringExpressions(ast.NodeTransformer):
    """删掉 docstring 与所有独立字符串表达式；ast.unparse 本身不会保留注释。"""

    def visit_Expr(self, node: ast.Expr) -> ast.AST | None:  # type: ignore[override]
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)


def executable_code(tree: ast.AST) -> str:
    cleaned = DropStringExpressions().visit(copy.deepcopy(tree))
    ast.fix_missing_locations(cleaned)
    return ast.unparse(cleaned)


def check_framework_has_no_payload_field_names(
    trees: dict[Path, ast.AST],
) -> Outcome:
    """精确检查代码与注解，绝不把 docstring / 注释里的历史键名算进去。"""
    errors: list[str] = []
    for path, tree in trees.items():
        code = executable_code(tree)
        for field_name in FORBIDDEN_PAYLOAD_FIELDS:
            if re.search(rf"\b{re.escape(field_name)}\b", code):
                errors.append(f"{path.as_posix()} 的代码/注解含 payload 字段 {field_name}")
    return make_outcome(
        errors,
        [
            f"扫描 {len(trees)} 个框架文件的代码与注解；"
            f"排除 docstring/注释后，{len(FORBIDDEN_PAYLOAD_FIELDS)} 个字段命中数为 0"
        ],
    )


def required_field_names(cls: type) -> list[str]:
    return [
        field.name
        for field in dataclasses.fields(cls)
        if field.default is dataclasses.MISSING
        and field.default_factory is dataclasses.MISSING
    ]


def check_input_requirement_fields(cls: type) -> Outcome:
    """InputRequirement 必须只有 port_id 缺少默认值。"""
    try:
        mandatory = required_field_names(cls)
    except TypeError as exc:
        return make_outcome([f"InputRequirement 不是 dataclass：{exc}"])

    if mandatory != ["port_id"]:
        return make_outcome(
            [f"必填字段应恰好是 ['port_id']，实得 {mandatory}"],
            [f"共 {len(dataclasses.fields(cls))} 个字段"],
        )
    return make_outcome(
        [],
        [
            f"共 {len(dataclasses.fields(cls))} 个字段，"
            f"唯一必填字段 = {mandatory}"
        ],
    )


def check_plugin_spec_tuple_annotations(cls: type) -> Outcome:
    """按要求检查 dataclass 字段注解字符串中是否含 tuple。"""
    try:
        annotations = {f.name: str(f.type) for f in dataclasses.fields(cls)}
    except TypeError as exc:
        return make_outcome([f"PluginSpec 不是 dataclass：{exc}"])

    errors: list[str] = []
    evidence: list[str] = []
    for name in ("required_inputs", "optional_inputs"):
        annotation = annotations.get(name)
        if annotation is None:
            errors.append(f"PluginSpec 缺字段 {name}")
            continue
        evidence.append(f"{name}: {annotation}")
        if "tuple" not in annotation:
            errors.append(f"PluginSpec.{name} 注解不含 tuple：{annotation!r}")
    return make_outcome(errors, evidence)


def check_units_vocabulary(units: typing.AbstractSet[str]) -> Outcome:
    missing = sorted(REQUIRED_UNITS - set(units))
    errors: list[str] = []
    if missing:
        errors.append(f"UNITS_VOCABULARY 缺单位：{missing}")
    if "" in units:
        errors.append('UNITS_VOCABULARY 含空串 ""')
    return make_outcome(
        errors,
        [f"词表值 = {', '.join(sorted(str(u) for u in units))}"],
    )


def meaningful_function_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    """函数 docstring 不算实现语句；其余每一行都必须由检查器明确承认。"""
    return [
        stmt
        for stmt in node.body
        if not (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        )
    ]


def shell_functions(tree: ast.AST) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    functions: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append((node.name, node))
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        for node in cls.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append((f"{cls.name}.{node.name}", node))
    return functions


def is_exact_shell_raise(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Raise) or stmt.cause is not None:
        return False
    exc = stmt.exc
    if not isinstance(exc, ast.Call) or exc.keywords:
        return False
    if not isinstance(exc.func, ast.Name) or exc.func.id != "NotImplementedError":
        return False
    if len(exc.args) != 1:
        return False
    arg = exc.args[0]
    return (
        isinstance(arg, ast.Constant)
        and isinstance(arg.value, str)
        and SHELL_MESSAGE.fullmatch(arg.value) is not None
    )


def check_algorithm_shells(trees: dict[Path, ast.AST]) -> Outcome:
    """所有顶层函数与类方法只能保留带 FILE-NNN 铭牌的单个 raise。

    ★ 例外（负责人 2026-09-24 授权注入）：`bootstrap` / `registry` 是
    唯一装配根与注册表本体，其实现是职责而非提前注入，**不适用空壳断言**。
    ★ 这两个文件**不被放弃检查** —— 它们仍受 §8 验收脚本
    （FILE-206 / FILE-204）逐条机械判定真实行为，
    且依赖方向与框架面检查照旧生效。此处只是不要求它们「调用必炸」。
    """
    errors: list[str] = []
    count = 0
    for path, tree in trees.items():
        if is_authorized_implemented(path):
            continue
        for qualified_name, node in shell_functions(tree):
            count += 1
            body = meaningful_function_body(node)
            if len(body) == 1 and is_exact_shell_raise(body[0]):
                continue

            forbidden = []
            if any(isinstance(stmt, ast.Pass) for stmt in body):
                forbidden.append("pass")
            if any(
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and stmt.value.value is Ellipsis
                for stmt in body
            ):
                forbidden.append("...")
            if any(isinstance(stmt, ast.Return) for stmt in body):
                forbidden.append("return")
            if any(isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)) for stmt in body):
                forbidden.append("赋值")
            detail = "、".join(forbidden) or "不是单一规范 raise"
            errors.append(
                f"{path.name}::{qualified_name} 第 {node.lineno} 行：{detail}"
            )

    return make_outcome(errors, [f"检查 {len(trees)} 个文件、{count} 个插件函数/方法"])


def collect_port_spec_ids(tree: ast.AST) -> set[str]:
    """纯 AST 收集 PORTS 里的 PortSpec.port_id，不 import profile。"""
    nodes = assignment_nodes(tree, "PORTS")
    if len(nodes) != 1 or not isinstance(nodes[0], (ast.Assign, ast.AnnAssign)):
        return set()
    value = nodes[0].value
    if value is None:
        return set()

    ids: set[str] = set()
    for node in ast.walk(value):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "PortSpec"
        ):
            continue
        for keyword in node.keywords:
            if keyword.arg == "port_id" and isinstance(keyword.value, ast.Constant):
                value = keyword.value.value
                if isinstance(value, str):
                    ids.add(value)
    return ids


def check_profile_has_notes_reference(tree: ast.AST) -> Outcome:
    """notes.reference 是三插件共同依赖的 B 级公共特征，必须留在封闭清单。"""
    ids = collect_port_spec_ids(tree)
    errors: list[str] = []
    if not ids:
        errors.append("无法从 AST 读取 profile.PORTS 的 PortSpec")
    elif "notes.reference" not in ids:
        errors.append("profile.PORTS 缺 notes.reference（会同时打断 pitch/timing/dynamics）")
    return make_outcome(
        errors,
        [
            f"AST 读到 {len(ids)} 个 PortSpec；"
            f"含 notes.reference={'notes.reference' in ids}"
        ],
    )


def check_envelope_shape(
    result: object,
    units: typing.AbstractSet[str],
    payload_types: tuple[type, type] = PAYLOAD_TYPES,
) -> list[str]:
    """纯函数形状检查；★ 不调用仍为空壳的 runtime.validate_result。"""
    errors: list[str] = []
    if not hasattr(result, "status"):
        return ["对象不是 AlgorithmResultEnvelope 形状：缺 status"]

    status = getattr(result, "status")
    if status not in STATUS_VALUES:
        errors.append(f"status={status!r} 不属于四值")

    payload = getattr(result, "payload", None)
    if not isinstance(payload, collections.abc.Sequence) or isinstance(payload, (str, bytes)):
        errors.append(f"payload 必须是序列，实得 {type(payload).__name__}")
    else:
        scalar_type, series_type = payload_types
        for index, item in enumerate(payload):
            # ★ 注解形状另由 contract.py AST 检查；这里只认识传入的 UI 元素类型。
            if isinstance(item, scalar_type):
                if item.unit not in units:
                    errors.append(f"payload[{index}].unit={item.unit!r} 不在词表")
            elif isinstance(item, series_type):
                if item.unit not in units:
                    errors.append(f"payload[{index}].unit={item.unit!r} 不在词表")
                if len(item.t) != len(item.values):
                    errors.append(
                        f"payload[{index}] UiSeries 长度不等："
                        f"len(t)={len(item.t)}, len(values)={len(item.values)}"
                    )
            else:
                errors.append(f"payload[{index}] 类型非法：{type(item).__name__}")

    coverage = getattr(result, "coverage", None)
    if coverage is not None:
        valid_number = (
            isinstance(coverage, (int, float))
            and not isinstance(coverage, bool)
            and math.isfinite(float(coverage))
            and 0.0 <= coverage <= 1.0
        )
        if not valid_number:
            errors.append(f"coverage={coverage!r} 不在有限数 0.0–1.0 内")

    warnings = getattr(result, "warnings", ())
    if not isinstance(warnings, tuple):
        errors.append(f"warnings 必须是 tuple，实得 {type(warnings).__name__}")
    elif status == "DEGRADED" and coverage is None and not warnings:
        errors.append("DEGRADED 的 coverage 与 warnings 皆为空")

    return errors


def make_probe_envelopes(contract: object) -> tuple[object, object]:
    """只用已实现契约类型造合法/非法信封，不调用任何算法。"""
    scalar_1 = contract.UiScalar(  # type: ignore[attr-defined]
        "fake.coverage",
        "假插件覆盖率",
        0.75,
        "ratio",
    )
    scalar_2 = contract.UiScalar(  # type: ignore[attr-defined]
        "fake.count",
        "假插件计数",
        2.0,
        "count",
    )
    series = contract.UiSeries(  # type: ignore[attr-defined]
        "fake.series",
        "假插件逐点结果",
        (0.0, 1.0),
        (0.1, 0.2),
        "seconds",
        contract.TimelineBasis.REFERENCE,  # type: ignore[attr-defined]
    )
    valid = contract.AlgorithmResultEnvelope(  # type: ignore[attr-defined]
        algorithm_id="fake.contract_probe",
        algorithm_version="0.0.0",
        status="DEGRADED",
        required_ports=(),
        consumed_ports=(),
        payload=(scalar_1, scalar_2, series),
        coverage=0.75,
        warnings=(),
    )
    invalid = dataclasses.replace(valid, coverage=None, warnings=())
    return valid, invalid


def check_zero_logic_annotation(contract_tree: ast.AST) -> Outcome:
    """★ 注解形状只靠 contract.py AST 判，不解析 future annotations 字符串。"""
    errors: list[str] = []
    envelope = next(
        (
            node
            for node in contract_tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "AlgorithmResultEnvelope"
        ),
        None,
    )
    payload_annotation = None
    if envelope is not None:
        for node in envelope.body:
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "payload"
            ):
                payload_annotation = node.annotation
                break
    payload_names = (
        {node.id for node in ast.walk(payload_annotation) if isinstance(node, ast.Name)}
        if payload_annotation is not None
        else set()
    )
    if not {"UiScalar", "UiSeries"} <= payload_names:
        errors.append(
            "AlgorithmResultEnvelope.payload 注解未直接引用 UiScalar | UiSeries："
            f"{ast.unparse(payload_annotation) if payload_annotation else '缺字段'}"
        )
    return make_outcome(
        errors,
        [
            "AST 注解 = "
            + (ast.unparse(payload_annotation) if payload_annotation else "缺字段")
        ],
    )


def check_zero_logic_projection(contract: object) -> Outcome:
    """证明 payload 直接使用 UI 类型，遍历不需要字段映射或中间转换。"""
    errors: list[str] = []
    evidence: list[str] = []

    scalar_fields = tuple(f.name for f in dataclasses.fields(contract.UiScalar))  # type: ignore[attr-defined]
    series_fields = tuple(f.name for f in dataclasses.fields(contract.UiSeries))  # type: ignore[attr-defined]
    expected_scalar = ("key", "label", "value", "unit", "threshold")
    expected_series = ("key", "label", "t", "values", "unit", "timeline_basis", "source_port")
    if scalar_fields != expected_scalar:
        errors.append(f"UiScalar 字段不是 {expected_scalar}，实得 {scalar_fields}")
    if series_fields != expected_series:
        errors.append(f"UiSeries 字段不是 {expected_series}，实得 {series_fields}")

    annotation_outcome = check_zero_logic_annotation(parse_path(PKG / "contract.py"))
    errors.extend(annotation_outcome.errors)

    valid, invalid = make_probe_envelopes(contract)
    valid_errors = check_envelope_shape(valid, contract.UNITS_VOCABULARY)  # type: ignore[attr-defined]
    if valid_errors:
        errors.append(f"合法 DEGRADED 信封被误拒：{valid_errors}")

    payload_lines: list[str] = []
    scalar_count = series_count = 0
    for item in valid.payload:  # type: ignore[attr-defined]
        if type(item) is contract.UiScalar:  # type: ignore[attr-defined]
            scalar_count += 1
            value_or_values = item.value
        elif type(item) is contract.UiSeries:  # type: ignore[attr-defined]
            series_count += 1
            value_or_values = item.values
        else:
            errors.append(f"payload 元素不是 UI 原类型：{type(item).__name__}")
            continue
        payload_lines.append(
            f"{item.key} | {item.label} | value-or-values={value_or_values} | unit={item.unit}"
        )
    if (scalar_count, series_count) != (2, 1):
        errors.append(f"payload 组成不是 2 scalar + 1 series，实得 {scalar_count}+{series_count}")

    invalid_errors = check_envelope_shape(invalid, contract.UNITS_VOCABULARY)  # type: ignore[attr-defined]
    if not any("DEGRADED" in error for error in invalid_errors):
        errors.append("无 coverage / warnings 的 DEGRADED 信封没有被拒绝")

    evidence.extend(
        [
            "UiScalar 字段 = " + ", ".join(scalar_fields),
            "UiSeries 字段 = " + ", ".join(series_fields),
            *annotation_outcome.evidence,
            "零逻辑遍历：",
            *[f"  · {line}" for line in payload_lines],
            "合法 DEGRADED：coverage=0.75，被接受",
            "非法 DEGRADED：" + "; ".join(invalid_errors),
        ]
    )
    return make_outcome(errors, evidence)


def contract_check(checker: Callable[[object], Outcome]) -> Outcome:
    try:
        if str(REPO) not in sys.path:
            sys.path.insert(0, str(REPO))
        contract = importlib.import_module("harmonica_eval.contract")
    except Exception as exc:
        return make_outcome([f"无法导入 harmonica_eval.contract：{type(exc).__name__}: {exc}"])
    return checker(contract)


def proof_contract_check(checker: Callable[[object], Outcome]) -> Outcome:
    return contract_check(checker)


def current_contract() -> object:
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    return importlib.import_module("harmonica_eval.contract")


def parse_override(source: str) -> ast.AST:
    return ast.parse(source)


def build_injection_proof(
    key: str,
) -> tuple[str, Outcome, Outcome]:
    """构造 (注入说明, 干净基线结果, 注入后结果)。"""
    alg_files = algorithm_files()
    concrete = concrete_algorithm_modules(alg_files)
    probe_name = next(iter(sorted(concrete)), "pitch")

    if key == "core-import":
        bad_path = PKG / "core" / "_injected_contract_probe.py"
        bad_tree = parse_override(
            f"from harmonica_eval.algorithms.{probe_name} import run"
        )
        clean = check_layer_has_no_concrete_algorithm_import(
            PKG / "core", concrete
        )
        bad = check_layer_has_no_concrete_algorithm_import(
            PKG / "core",
            concrete,
            overrides={bad_path: bad_tree},
        )
        return f"core/_injected_contract_probe.py import algorithms.{probe_name}", clean, bad

    if key == "host-import":
        bad_path = PKG / "host" / "_injected_contract_probe.py"
        bad_tree = parse_override(
            f"from harmonica_eval.algorithms.{probe_name} import run"
        )
        clean = check_layer_has_no_concrete_algorithm_import(
            PKG / "host", concrete
        )
        bad = check_layer_has_no_concrete_algorithm_import(
            PKG / "host",
            concrete,
            overrides={bad_path: bad_tree},
        )
        return f"host/_injected_contract_probe.py import algorithms.{probe_name}", clean, bad

    if key == "cockpit-import":
        bad_path = PKG / "cockpit" / "_injected_contract_probe.py"
        bad_tree = parse_override(
            f"from harmonica_eval.algorithms.{probe_name} import run"
        )
        clean = check_layer_has_no_concrete_algorithm_import(
            PKG / "cockpit", concrete
        )
        bad = check_layer_has_no_concrete_algorithm_import(
            PKG / "cockpit",
            concrete,
            overrides={bad_path: bad_tree},
        )
        return f"cockpit/_injected_contract_probe.py import algorithms.{probe_name}", clean, bad

    if key == "algorithm-reverse-import":
        base_path = next(
            (p for p in alg_files if p.name != "__init__.py"),
            PKG / "algorithms" / "_injected_contract_probe.py",
        )
        bad_tree = parse_override("from ..core import features")
        clean = check_algorithms_have_no_reverse_imports(alg_files)
        bad = check_algorithms_have_no_reverse_imports(
            alg_files, overrides={base_path: bad_tree}
        )
        return f"{base_path.name} 注入 from ..core import features", clean, bad

    if key == "payload-table":
        path = ALGORITHMS_DIR / "__init__.py"
        bad_tree = copy.deepcopy(parse_path(path))
        value = ast.Dict(keys=[], values=[])
        bad_tree.body.append(
            ast.Assign(
                targets=[ast.Name(id="PAYLOAD_SCHEMAS", ctx=ast.Store())],
                value=value,
                lineno=999,
            )
        )
        ast.fix_missing_locations(bad_tree)
        clean = check_algorithms_public_surface(parse_path(path))
        bad = check_algorithms_public_surface(bad_tree)
        return "algorithms/__init__.py 注入 PAYLOAD_SCHEMAS = {}", clean, bad

    if key == "host-id-compare":
        bad_path = PKG / "host" / "_injected_contract_probe.py"
        bad_tree = parse_override(
            'def choose(plugin_id):\n'
            '    if plugin_id == "pitch":\n'
            '        return True\n'
            '    return False\n'
        )
        paths = python_files(PKG / "host")
        clean = check_host_has_no_algorithm_id_compare(
            {path: parse_path(path) for path in paths}
        )
        bad = check_host_has_no_algorithm_id_compare(
            {path: parse_path(path) for path in paths} | {bad_path: bad_tree}
        )
        return 'host/_injected_contract_probe.py 注入 if plugin_id == "pitch"', clean, bad

    if key == "payload-field":
        bad_path = Path("<injected>/framework.py")
        bad_tree = parse_override(
            "PAYLOAD = {'median_abs_cents': 1.0}\n"
        )
        paths = [
            PKG / "contract.py",
            ALGORITHMS_DIR / "__init__.py",
            ALGORITHMS_DIR / "registry.py",
            ALGORITHMS_DIR / "runtime.py",
            *python_files(PKG / "host"),
            *python_files(PKG / "cockpit"),
        ]
        clean = check_framework_has_no_payload_field_names(
            {path: parse_path(path) for path in paths}
        )
        bad = check_framework_has_no_payload_field_names(
            {path: parse_path(path) for path in paths} | {bad_path: bad_tree}
        )
        return "内存框架模块的可执行字典引用 median_abs_cents（docstring 除外）", clean, bad

    if key == "input-required":
        clean_cls = current_contract().InputRequirement  # type: ignore[attr-defined]
        bad_cls = dataclasses.make_dataclass(
            "BadInputRequirement",
            [("port_id", str), ("schema_version", str)],
            frozen=True,
        )
        return (
            "内存 dataclass 把 schema_version 也改成无默认值",
            check_input_requirement_fields(clean_cls),
            check_input_requirement_fields(bad_cls),
        )

    if key == "plugin-tuple":
        clean_cls = current_contract().PluginSpec  # type: ignore[attr-defined]
        bad_cls = dataclasses.make_dataclass(
            "BadPluginSpec",
            [
                ("plugin_id", str),
                ("required_inputs", list),
                ("optional_inputs", list),
            ],
            frozen=True,
        )
        return (
            "内存 PluginSpec 把 required/optional 注解改为 list",
            check_plugin_spec_tuple_annotations(clean_cls),
            check_plugin_spec_tuple_annotations(bad_cls),
        )

    if key == "units":
        contract = current_contract()
        clean = check_units_vocabulary(contract.UNITS_VOCABULARY)  # type: ignore[attr-defined]
        bad = check_units_vocabulary(
            set(contract.UNITS_VOCABULARY) | {""}  # type: ignore[attr-defined]
        )
        return "内存词表追加空串 \"\"", clean, bad

    if key == "shell-body":
        trees = {path: parse_path(path) for path in alg_files}
        registry = ALGORITHMS_DIR / "registry.py"
        bad_tree = copy.deepcopy(trees[registry])
        first = next(
            node
            for node in ast.walk(bad_tree)
            if isinstance(node, ast.FunctionDef)
        )
        first.body = [ast.Return(value=ast.Constant(value=None))]
        ast.fix_missing_locations(bad_tree)
        return (
            "registry.py::Registry.register 注入 return None",
            check_algorithm_shells(trees),
            check_algorithm_shells(trees | {registry: bad_tree}),
        )

    if key == "projection-annotation":
        clean_tree = parse_path(PKG / "contract.py")
        bad_tree = copy.deepcopy(clean_tree)
        changed = False
        for node in ast.walk(bad_tree):
            if not (
                isinstance(node, ast.ClassDef)
                and node.name == "AlgorithmResultEnvelope"
            ):
                continue
            for field in node.body:
                if isinstance(field, ast.AnnAssign) and isinstance(field.target, ast.Name) and field.target.id == "payload":
                    field.annotation = ast.parse("Sequence[Mapping[str, object]]", mode="eval").body
                    changed = True
                    break
        ast.fix_missing_locations(bad_tree)
        if not changed:
            raise ValueError("无法在 contract AST 内存副本中定位 payload 注解")
        clean = check_zero_logic_annotation(clean_tree)
        bad = check_zero_logic_annotation(bad_tree)
        return "contract.py 内存 AST 把 payload 注解改为 Mapping[str, object]", clean, bad

    if key == "profile-notes":
        clean_tree = parse_path(PKG / "profile.py")
        bad_tree = copy.deepcopy(clean_tree)
        removed = False
        for node in ast.walk(bad_tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "PortSpec"
            ):
                continue
            if any(
                keyword.arg == "port_id"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value == "notes.reference"
                for keyword in node.keywords
            ):
                node.keywords = [
                    keyword
                    for keyword in node.keywords
                    if not (
                        keyword.arg == "port_id"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value == "notes.reference"
                    )
                ]
                removed = True
                break
        if not removed:
            raise ValueError("无法在 profile AST 内存副本中定位 notes.reference")
        return (
            "profile.py 内存 AST 副本移除 notes.reference 的 PortSpec",
            check_profile_has_notes_reference(clean_tree),
            check_profile_has_notes_reference(bad_tree),
        )

    if key == "degraded-evidence":
        contract = current_contract()
        valid, invalid = make_probe_envelopes(contract)
        return (
            "把 DEGRADED 信封的 coverage 置 None、warnings 置空 tuple",
            make_outcome(check_envelope_shape(valid, contract.UNITS_VOCABULARY)),  # type: ignore[attr-defined]
            make_outcome(check_envelope_shape(invalid, contract.UNITS_VOCABULARY)),  # type: ignore[attr-defined]
        )

    raise KeyError(key)


CASE_ORDER = (
    ("core-import", "① core 不依赖具体算法"),
    ("host-import", "② host 不依赖具体算法实现"),
    ("cockpit-import", "③ cockpit 不依赖具体算法实现"),
    ("algorithm-reverse-import", "④ algorithms 不反向依赖上层"),
    ("payload-table", "⑤ 框架无 algorithm_id → payload 表"),
    ("host-id-compare", "⑥ Host 无 plugin_id/algorithm_id 比较"),
    ("payload-field", "⑦ 框架代码/注解无具体 payload 字段"),
    ("input-required", "⑧ InputRequirement 仅 port_id 必填"),
    ("plugin-tuple", "⑨ PluginSpec 输入集合为 tuple 注解"),
    ("units", "⑩ 单位词表完整且无空串"),
    ("shell-body", "⑪ 插件文件保持精确空壳"),
    ("projection-annotation", "★ payload 注解零逻辑静态自证"),
    ("degraded-evidence", "★ 自描述 payload 与 DEGRADED 形状"),
    ("profile-notes", "⑫ profile.PORTS 保留 notes.reference"),
)
CASE_TITLES = dict(CASE_ORDER)
CASE_ALIASES = {str(index): key for index, (key, _) in enumerate(CASE_ORDER, 1)}


def run_normal_checks() -> int:
    print("C3 插件契约检查（只读；不调用 Registry / Runtime / 算法空壳）")
    alg_files = algorithm_files()
    concrete = concrete_algorithm_modules(alg_files)
    framework_paths = [
        PKG / "contract.py",
        ALGORITHMS_DIR / "__init__.py",
        ALGORITHMS_DIR / "registry.py",
        ALGORITHMS_DIR / "runtime.py",
        *python_files(PKG / "host"),
        *python_files(PKG / "cockpit"),
    ]
    framework_trees = {path: parse_path(path) for path in framework_paths}
    host_trees = {path: parse_path(path) for path in python_files(PKG / "host")}

    checks: list[tuple[str, str, Callable[[], Outcome]]] = [
        (
            NUMBERS[0],
            "core/ 不 import 任何具体算法插件",
            lambda: check_layer_has_no_concrete_algorithm_import(PKG / "core", concrete),
        ),
        (
            NUMBERS[1],
            "host/ 不 import 任何具体算法实现",
            lambda: check_layer_has_no_concrete_algorithm_import(PKG / "host", concrete),
        ),
        (
            NUMBERS[2],
            "cockpit/ 不 import 具体算法实现",
            lambda: check_layer_has_no_concrete_algorithm_import(PKG / "cockpit", concrete),
        ),
        (
            NUMBERS[3],
            "algorithms/ 不反向 import core / host / cockpit",
            lambda: check_algorithms_have_no_reverse_imports(alg_files),
        ),
        (
            NUMBERS[4],
            "框架无按 algorithm_id 索引 payload 的表",
            lambda: check_algorithms_public_surface(
                parse_path(ALGORITHMS_DIR / "__init__.py")
            ),
        ),
        (
            NUMBERS[5],
            "Host 无 if plugin_id/algorithm_id == ... 式硬编码",
            lambda: check_host_has_no_algorithm_id_compare(host_trees),
        ),
        (
            NUMBERS[6],
            "框架代码/注解不出现具体 payload 字段（不含插件实现）",
            lambda: check_framework_has_no_payload_field_names(framework_trees),
        ),
        (
            NUMBERS[7],
            "InputRequirement 恰好只有 port_id 必填",
            lambda: contract_check(
                lambda contract: check_input_requirement_fields(contract.InputRequirement)  # type: ignore[attr-defined]
            ),
        ),
        (
            NUMBERS[8],
            "PluginSpec 的输入集合是不可变 tuple 注解",
            lambda: contract_check(
                lambda contract: check_plugin_spec_tuple_annotations(contract.PluginSpec)  # type: ignore[attr-defined]
            ),
        ),
        (
            NUMBERS[9],
            "UNITS_VOCABULARY 完整且不含空串",
            lambda: contract_check(
                lambda contract: check_units_vocabulary(contract.UNITS_VOCABULARY)  # type: ignore[attr-defined]
            ),
        ),
        (
            NUMBERS[10],
            "插件文件保持精确空壳（bootstrap/registry 已授权注入，见函数 docstring）",
            lambda: check_algorithm_shells(
                {path: parse_path(path) for path in alg_files}
            ),
        ),
        (
            "★",
            "自描述 payload 的投影是零逻辑",
            lambda: contract_check(check_zero_logic_projection),
        ),
        (
            "⑫",
            "profile.PORTS 保留 notes.reference（B 级公共特征）",
            lambda: check_profile_has_notes_reference(parse_path(PKG / "profile.py")),
        ),
    ]

    outcomes: list[Outcome] = []
    for number, title, checker in checks:
        print()
        print("─" * 72)
        print(f"{number} {title}")
        print("─" * 72)
        try:
            outcome = checker()
        except Exception as exc:
            outcome = make_outcome(
                [f"检查器异常：{type(exc).__name__}: {exc}"]
            )
        for line in outcome.evidence:
            print(f"  · {line}")
        for error in outcome.errors:
            print(f"  ❌ {error}")
        if outcome.ok:
            print("  ✅ 通过")
        outcomes.append(outcome)

    passed = sum(outcome.ok for outcome in outcomes)
    total = len(outcomes)
    failed = total - passed
    print()
    print("─" * 72)
    print("汇总")
    print("─" * 72)
    print(f"  {'✅' if failed == 0 else '❌'} {passed}/{total} 条通过，{failed} 条失败")
    print("  结论：" + ("插件契约插口全部成立" if failed == 0 else "发现未放宽的架构违规"))
    return 0 if failed == 0 else 1


def run_injection(case: str) -> int:
    normalized = CASE_ALIASES.get(case, case)
    if normalized == "all":
        selected = [key for key, _ in CASE_ORDER]
    elif normalized in CASE_TITLES:
        selected = [normalized]
    else:
        available = ", ".join(key for key, _ in CASE_ORDER)
        print(f"未知注入 case：{case}\n可用：{available}, all, 1-14", file=sys.stderr)
        return 1

    print(f"C3 插件契约红/绿自证（仅内存注入：{', '.join(selected)}）")
    proof_ok = 0
    for key in selected:
        description, clean, bad = build_injection_proof(key)
        print()
        print("─" * 72)
        print(f"★ 红/绿自证：{CASE_TITLES[key]}")
        print("─" * 72)
        print(f"  注入：{description}")

        if bad.errors:
            for error in bad.errors:
                print(f"  ❌ [红] {error}")
        else:
            print("  ❌ [红] 自证失败：注入违规没有被检查器捕获")

        print("  恢复：丢弃注入对象，重新扫描干净内存基线")
        if clean.ok:
            for line in clean.evidence:
                print(f"  · {line}")
            print("  ✅ [绿] 恢复后通过")
        else:
            for error in clean.errors:
                print(f"  ❌ [绿未恢复] {error}")

        if bad.errors and clean.ok:
            proof_ok += 1

    print()
    print("─" * 72)
    print("红/绿自证汇总")
    print("─" * 72)
    print(f"  {'✅' if proof_ok == len(selected) else '❌'} {proof_ok}/{len(selected)} 条按预期完成变红并恢复变绿")
    print("  ★ 本命令故意注入过违规，因此按契约返回退出码 1；默认模式无违规时返回 0。")
    # ★ 注入模式只要按预期捕获并恢复也必须返回 1：它证明当前内存状态含过违规。
    # 自证失败同样返回 1，且上面的汇总会明确显示失败。
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inject",
        metavar="CASE",
        help="在内存中注入违规：case 名、1-14，或 all",
    )
    args = parser.parse_args(argv)
    if args.inject:
        return run_injection(args.inject)
    return run_normal_checks()


if __name__ == "__main__":
    sys.exit(main())
