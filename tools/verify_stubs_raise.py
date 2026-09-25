#!/usr/bin/env python3
"""verify_stubs_raise.py —— 验证空壳的"调用必炸"断言。

空壳的核心价值是：**被调用时一定抛错**。
若某个空壳函数静默返回 None，实现者可能误以为它已可用，
或把 None 当成合法返回值继续往下写 —— 这类错误极难发现。

用法：python3 tools/verify_stubs_raise.py
退出码：0 通过 / 1 有失效空壳
无随机性、无副作用（只读；调用空壳不产生任何状态）。

── 三类豁免（都有明确理由，不是放水）──────────────────────────
1. Protocol 成员    —— `contract.py` 里的 HostContract / AlgorithmDataContract /
                       UiProjectionPort 是**类型声明**，函数体用 `...` 是正确写法。
                       Protocol 不可实例化，永远不会被"调用"；property getter
                       也按同一口径豁免，但会在报告中单独列明。
2. 冻结地基的实现    —— `profile.py` 里的模块级自检已经实现；`contract.py` 的
                       契约类型值语义另按下方 AST 判据分类。
3. __init__.py 等   —— 不定义可调用符号的文件自然无空壳。

★★ 豁免 4：已授权的**真实现**文件（不适用"调用必炸"断言）——

`preview.py` 是负责人授权创建的**契约结构预览视图**；`bootstrap.py` /
`registry.py` 是 2026-09-24 授权注入的**装配根与注册表本体**。
它们是真实现而不是待注入的 SHELL。**但它们并未被放弃检查**：

- `preview.py` 适用 `check_authorized_imports()` 的 **C4 import 边界**
  （只允许 `..contract` + 标准库；禁任何 DSP / 音频 / 数据面 / 上层组件）。
- `bootstrap.py` / `registry.py` 适用 `check_layer_imports()` 的
  **装配层分层白名单** —— bootstrap 允许 import 具体算法与 `profile`
  （那正是 GC-204-08 裁定甲赋予它的职责）；`registry` 刻意**只允许
  `..contract`**，因为 FILE-204 铭牌要求它不依赖具体算法模块。

★ 任何一项判据失败同样使本脚本非 0 退出。

★ 豁免是**精确文件路径**（`rel in AUTHORIZED_IMPL_FILES`），
★ **不是目录或前缀匹配** —— `cockpit/` 与 `algorithms/` 下其它文件
★ （例如 `app.py`、`runtime.py`、`pitch.py`）仍逐个成员接受"调用必炸"检查。

★★ property 裁定：``property`` 是描述符，不是空壳函数本体。真正的待检查
对象是 ``property.fget`` / ``fset`` / ``fdel``。本脚本在 AST 枚举阶段先分类，
再取对应回调调用；绝不对 property 对象本身调用，也绝不靠吞掉 TypeError 混过。
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pathlib
import sys
from dataclasses import dataclass
from typing import Literal

# ★ 已授权注入文件从唯一真相源派生（不再在本文件维护副本）。
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from authorized_impl import REPO_REL as _AUTHORIZED_REPO_REL  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent

# 豁免 1：Protocol 声明（类型层，无运行时实体）
PROTOCOL_CLASSES = {"HostContract", "AlgorithmDataContract", "UiProjectionPort"}

# 豁免 2：已实现的冻结地基（profile.py 模块级自检；contract.py 类值语义另行判定）
GROUND_FILES = {"harmonica_eval/profile.py"}
CONTRACT_FILE = "harmonica_eval/contract.py"

# 豁免 4：负责人授权的**真实现**文件（不适用"调用必炸"断言）。
# ★ 精确路径，不是目录 / 前缀 —— cockpit/ 下其它文件仍逐个成员受检。
# ★ ★ 本表不再在此维护 —— 派生自 tools/authorized_impl.py（唯一真相源），
# ★   「哪次授权、依据哪份 BI」在真相源里逐条记录。
# ★ 它们不被放弃检查：改由 check_authorized_imports() 施加 import 边界判据。
AUTHORIZED_IMPL_FILES = set(_AUTHORIZED_REPO_REL)

# 豁免 4 的 import 边界判据：只允许标准库 + 本包契约层。
# ★ 禁止清单按"能力"而非按具体包穷举：任何音频/DSP/数据面/上层组件 import 都算越界。
AUTHORIZED_IMPL_ALLOWED = {"__future__", "..contract"}
# C4 允许的 Python 标准库（序列化 + 本机 HTTP + 路径 + 反射 + 类型）
AUTHORIZED_IMPL_STDLIB = {
    "dataclasses",
    "functools",
    "http",
    "html",
    "importlib",
    "inspect",
    "json",
    "mimetypes",
    "pathlib",
    "sys",
    "typing",
}
# 显式禁止的能力域（用于报错文案，判定本身靠"白名单外即违规"）
AUTHORIZED_IMPL_FORBIDDEN_HINT = {
    "numpy|librosa|scipy|soundfile|torch": "音频/DSP/数值计算",
    "..core|..host|..algorithms|.core|.host|.algorithms": "C2/C1/C3 内部实现",
    "..profile|.profile": "C2 发布的配置（绕过 G14 直连 C2）",
}

MemberKind = Literal["method", "getter", "setter", "deleter"]


@dataclass(frozen=True)
class Member:
    """一个待分类的类成员；kind 在 AST 枚举阶段确定。"""

    tag: str
    kind: MemberKind


def decorator_kind(node: ast.FunctionDef | ast.AsyncFunctionDef) -> MemberKind:
    """按装饰器语法分类方法与 property 回调。"""
    for decorator in reversed(node.decorator_list):
        if isinstance(decorator, ast.Name) and decorator.id == "property":
            return "getter"
        if isinstance(decorator, ast.Attribute) and decorator.attr in ("setter", "deleter"):
            return decorator.attr
    return "method"


def decorator_name(decorator: ast.expr) -> str | None:
    """返回装饰器（含调用形式）的末段名称；无法静态确定时返回 None。"""
    if isinstance(decorator, ast.Name):
        return decorator.id
    if isinstance(decorator, ast.Attribute):
        return decorator.attr
    if isinstance(decorator, ast.Call):
        return decorator_name(decorator.func)
    return None


def is_dataclass(node: ast.ClassDef) -> bool:
    """类是否由 dataclass 装饰（包括 alias.frozen 形式）。"""
    return any(decorator_name(item) == "dataclass" for item in node.decorator_list)


def is_frozen_dataclass(node: ast.ClassDef) -> bool:
    """类是否明确声明为 @dataclass(frozen=True)。"""
    for decorator in node.decorator_list:
        if decorator_name(decorator) != "dataclass":
            continue
        if any(
            keyword.arg == "frozen"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in decorator.keywords
        ):
            return True
    return False


def is_docstring_statement(node: ast.stmt) -> bool:
    """AST 首表达式是否为字符串表达式。"""
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def is_instance_field(node: ast.expr, class_fields: set[str]) -> bool:
    """节点是否为 self.<已声明字段>，不跟随更深的属性或方法调用。"""
    return (
        isinstance(node, ast.Attribute)
        and node.attr in class_fields
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def is_field_index_query(node: ast.expr, query: str, class_fields: set[str]) -> bool:
    """节点是否为 self.<字段>[query] 这种无副作用的只读索引。"""
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr in class_fields
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "self"
        and isinstance(node.slice, ast.Name)
        and node.slice.id == query
    )


def is_membership_query(node: ast.expr, query: str, class_fields: set[str]) -> bool:
    """节点是否为 query in self.<字段>（或其取反）的纯查询。"""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return is_membership_query(node.operand, query, class_fields)
    return (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and len(node.comparators) == 1
        and isinstance(node.ops[0], (ast.In, ast.NotIn))
        and isinstance(node.left, ast.Name)
        and node.left.id == query
        and is_instance_field(node.comparators[0], class_fields)
    )


def is_self_only(method: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """函数是否只接受 self，且没有可变参数或默认值。"""
    positional_args = method.args.posonlyargs + method.args.args
    return (
        len(positional_args) == 1
        and positional_args[0].arg == "self"
        and not method.args.defaults
        and method.args.vararg is None
        and method.args.kwarg is None
        and not method.args.kwonlyargs
    )


def has_shell_raise(method: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """函数是否仍只是约定的 SHELL 抛出。"""
    for node in ast.walk(method):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            message = node.exc.args[0] if node.exc.args else None
            if isinstance(message, ast.Constant) and isinstance(message.value, str):
                if "SHELL: FILE-" in message.value:
                    return True
    return False


def has_nontrivial_body(method: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """排除只有 docstring、pass、... 的声明，以及尚未注入的 SHELL。"""
    body = (
        method.body[1:]
        if method.body and is_docstring_statement(method.body[0])
        else method.body
    )
    if not body:
        return False
    if len(body) == 1 and isinstance(body[0], (ast.Pass, ast.Expr)):
        if isinstance(body[0], ast.Expr) and not isinstance(body[0].value, ast.Constant):
            return True
        return False
    if len(body) == 1 and isinstance(body[0], ast.Return):
        return body[0].value is not None and not isinstance(
            body[0].value, ast.Constant
        )
    return not has_shell_raise(method)


def has_self_field_reference(
    node: ast.AST,
    class_fields: set[str],
) -> bool:
    """节点树中是否引用 self 的一个已声明字段。"""
    return any(
        is_instance_field(item, class_fields)
        for item in ast.walk(node)
    )


def has_field_validation(
    method: ast.FunctionDef | ast.AsyncFunctionDef,
    class_fields: set[str],
) -> bool:
    """方法是否含有基于字段条件的显式拒绝分支。"""
    for item in method.body:
        if not isinstance(item, ast.If) or not has_self_field_reference(
            item.test, class_fields
        ):
            continue
        if any(isinstance(child, ast.Raise) for child in ast.walk(item)):
            return True
    return False


def annotation_is(node: ast.expr | None, name: str) -> bool:
    """静态比较简单类型注解；不求值任意表达式。"""
    if name == "None":
        return isinstance(node, ast.Constant) and node.value is None
    return isinstance(node, ast.Name) and node.id == name


def is_lifecycle_validation(
    method: ast.FunctionDef | ast.AsyncFunctionDef,
    class_fields: set[str],
) -> bool:
    """判定 __post_init__ 是否是真实的 dataclass 字段不变量钩子。"""
    return (
        isinstance(method, ast.FunctionDef)
        and is_self_only(method)
        and annotation_is(method.returns, "None")
        and has_nontrivial_body(method)
        and has_field_validation(method, class_fields)
    )


def is_string_expression(node: ast.expr) -> bool:
    """只把明显的字符串字面量、拼接、f-string 或格式化视作字符串结果。"""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return is_string_expression(node.left) and is_string_expression(node.right)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            return node.func.attr in {"join", "format"}
        if isinstance(node.func, ast.Name):
            return node.func.id in {"str", "format"}
    return False


def is_string_rendering(method: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """判定异常 __str__ 是否是真实的类型字符串语义。"""
    if not (
        isinstance(method, ast.FunctionDef)
        and is_self_only(method)
        and annotation_is(method.returns, "str")
        and has_nontrivial_body(method)
    ):
        return False
    returns = [item.value for item in method.body if isinstance(item, ast.Return)]
    return bool(returns) and all(
        value is not None and is_string_expression(value) for value in returns
    )


def is_read_only_field_query(
    method: ast.FunctionDef | ast.AsyncFunctionDef,
    class_fields: set[str],
) -> bool:
    """函数是否为 frozen dataclass 上的单参数、无副作用字段查询。"""
    if isinstance(method, ast.AsyncFunctionDef):
        return False
    positional_args = method.args.posonlyargs + method.args.args
    if (
        len(positional_args) != 2
        or positional_args[0].arg != "self"
        or method.args.defaults
        or method.args.vararg
        or method.args.kwarg
        or method.args.kwonlyargs
    ):
        return False

    query = positional_args[1].arg
    body = (
        method.body[1:]
        if method.body and is_docstring_statement(method.body[0])
        else method.body
    )
    if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
        return False
    value = body[0].value
    return (
        is_instance_field(value, class_fields)
        or is_field_index_query(value, query, class_fields)
        or is_membership_query(value, query, class_fields)
    )


def base_class_names(node: ast.ClassDef) -> set[str]:
    """收集类声明中的基类名称（不求值表达式）。"""
    return {
        base.id
        for base in node.bases
        if isinstance(base, ast.Name)
    }


def is_exception_subclass(node: ast.ClassDef) -> bool:
    """类是否显式继承 Exception/BaseException 的名字。"""
    return bool(base_class_names(node) & {"Exception", "BaseException"})


def is_contract_value_semantics(
    rel: str,
    node: ast.ClassDef,
    method: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """判定 contract.py 中非空壳的契约类型值语义。

    范围按“类型自身语义”而不是文件或方法名白名单划界：仅限 dataclass
    类型上的三种结构：

    1. ``__post_init__``：dataclass 构造生命周期钩子，负责字段不变量校验；
    2. frozen dataclass 上单一 ``self/query`` 入参、单一 ``return`` 的字段查询；
       返回值只能是 ``self.<已声明字段>``、``self.<字段>[query]`` 或
       ``query in/not in self.<字段>``，对应 ``ResolutionView.is_available``；
    3. 显式继承 ``Exception`` 的 dataclass 上的 ``__str__``：异常类型自身的
       字符串表现，不承载端口或业务行为。

    普通名称的 ``return 1``、赋值、调用、I/O、算法计算均不满足上述结构，
    仍按 SHELL 检查；非 dataclass、非 frozen 类型上的字段查询也不豁免。
    contract.py 的 dunder 不再被枚举器无条件跳过，否则 `__probe__` 会逃过检查。
    因而这不是对 contract.py 的文件级豁免。
    """
    if rel != CONTRACT_FILE or not is_dataclass(node):
        return False
    class_fields = {
        item.target.id
        for item in node.body
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
    }
    if method.name == "__post_init__" and is_lifecycle_validation(method, class_fields):
        return True
    if (
        method.name == "__str__"
        and is_exception_subclass(node)
        and is_string_rendering(method)
    ):
        return True
    if not is_frozen_dataclass(node):
        return False
    return is_read_only_field_query(method, class_fields)


def imported_modules(tree: ast.Module) -> list[str]:
    """收集模块级与函数内全部 import 的规范化名称（含相对层级）。"""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * (node.level or 0)
            module = node.module or ""
            if module:
                found.append(prefix + module)
            else:
                # `from .. import profile`：模块名在 alias 上，须逐个展开否则报错信息失真
                found.extend(prefix + alias.name for alias in node.names)
    return found


def classify_import(name: str, per_file: tuple[str, ...] = ()) -> str:
    """把一个 import 归类为 allowed / stdlib / forbidden。

    ★ `per_file` 是该文件自己的白名单前缀（见 AUTHORIZED_IMPL_ALLOWED_PREFIXES）。
      C3 的装配层文件（bootstrap / registry / runtime / pitch）各有不同的合法依赖，
      不能套用 C4 视图那条「只允许 ..contract + 标准库」的表。
    ★ 判定顺序：文件专属前缀 → 全局契约层 → 标准库 → forbidden（默认拒绝）。
    """
    if per_file and (name in per_file or any(
            name.startswith(p + ".") for p in per_file if p.startswith("."))):
        return "allowed"
    if name in AUTHORIZED_IMPL_ALLOWED:
        return "allowed"
    top = name.lstrip(".").split(".")[0]
    if not name.startswith(".") and top in AUTHORIZED_IMPL_STDLIB:
        return "stdlib"
    return "forbidden"


def check_authorized_imports(rel: str, tree: ast.Module, problems: list[str]) -> int:
    """★ 豁免 4 的降级判据：已授权实现文件必须守住 import 边界。

    这些文件不做"调用必炸"检查（它们是真实现），但**不是放水**：
    这里施加的是比 SHELL 更贴近其职责的边界判据——只允许
    `..contract` 与 Python 标准库。任何 DSP / 音频 / 数据面 / 上层组件
    import 都会让本脚本非 0 退出。

    白名单之外一律 forbidden（默认拒绝），因此新增依赖必然暴露。
    返回该文件 import 条目数，供汇总列明。
    """
    total = 0
    per_file = AUTHORIZED_IMPL_ALLOWED_PREFIXES.get(rel, ())
    for name in sorted(set(imported_modules(tree))):
        total += 1
        verdict = classify_import(name, per_file)
        if verdict == "forbidden":
            hint = ""
            for pattern, reason in AUTHORIZED_IMPL_FORBIDDEN_HINT.items():
                if any(part and part in name for part in pattern.split("|")):
                    hint = f"（疑似{reason}）"
                    break
            problems.append(
                f"{rel}::import {name} 越过已授权实现的边界{hint}"
                f"；只允许 ..contract 与 Python 标准库"
            )
    return total


# ★ 已授权注入的 C3 装配层文件各有**不同的** import 边界 ——
#   它们不是 C4 视图，不能套用「只允许 ..contract + 标准库」那条判据。
#   bootstrap 的职责本体就是 import 具体算法与 profile（GC-204-08 裁定甲）；
#   registry 按 FILE-204 铭牌「只依赖 contract.PluginSpec，不依赖具体算法模块」。
# ★ 仍非放水：各自的白名单之外一律 forbidden（默认拒绝）。
# ★ `imported_modules()` 返回的是**带相对层级前缀**的写法
#   （`..contract` / `.registry` / `..profile`），不是绝对模块名，
#   因此白名单也必须按同一写法登记，否则永远匹配不上。
AUTHORIZED_IMPL_ALLOWED_PREFIXES: dict[str, tuple[str, ...]] = {
    "harmonica_eval/algorithms/bootstrap.py": (
        ".registry",  # 同包：Registry
        ".runtime",  # 同包：InputResolution 等
        ".pitch", ".timing", ".dynamics",  # ★ 装配根的职责本体（GC-204-08 甲）
        "..profile",  # PORT_INDEX：派生 InputRequirement，不硬编码
        "..contract",  # PluginSpec / InputRequirement / 错误码
    ),
    "harmonica_eval/algorithms/registry.py": (
        "..contract",  # ★ 刻意不含 .pitch/.timing/.dynamics：
        #   FILE-204 铭牌 MUST「不依赖具体算法模块」，违反会立即变红
    ),
    "harmonica_eval/algorithms/runtime.py": (
        # ★ 2026-09-24 第 2 刀授权注入；BI = FILE-205-v1.md。
        #   runtime 是 C3 执行期校验层：解析输入、校验信封、提供只读视图。
        "..contract",  # InputRequirement / PluginSpec / ResolutionView / 错误码
        # ★ 刻意不含 .pitch/.timing/.dynamics/.registry：
        #   它对具体算法一无所知（插件自描述，runtime 只按契约校验）。
        "math",  # 纯数学校算（对数 / 阈值比较），非 DSP 库
        "dataclasses",  # InputResolution / ResolvedSurface 是 dataclass
    ),
    "harmonica_eval/algorithms/pitch.py": (
        # ★ 2026-09-24 第 3 刀授权注入；BI = FILE-201-v1.md。
        #   pitch 是 C3 的音准算法：按音配对比较参考/练习的 f0 曲线。
        "..contract",  # AlgorithmDataContract / AlgorithmResultEnvelope / UiScalar / UiSeries
        # ★ 刻意不含 .timing / .dynamics / .registry：
        #   算法互不知道对方存在（FILE-201 铭牌 MUST），违反会立即变红。
        "math",  # 音分换算（对数比），非 DSP 库
        "statistics",  # 中位数 / 离散度
    ),
    # ── 以下为第 4 刀（双音频端到端收尾）授权注入的文件 ──────────────
    # ★ 每条注明 BI；跨层禁止一律【刻意不列】，违反即变红。
    "harmonica_eval/core/ingest.py": (
        "..contract",  # ErrorCode / ContractViolation
        "..profile",  # AUDIO 采样率规格（FILE-101 §4.1）
        "numpy", "numpy.typing",
        "scipy.signal",  # 重采样
        "soundfile",  # WAV 解码
        "os.path",  # 路径处理
    ),
    "harmonica_eval/core/align.py": (
        "..contract",
        "..profile",  # PROFILE.AUDIO.sample_rate：STFT 频率轴必须传真实采样率
        "numpy", "numpy.typing",
        "scipy.signal",  # STFT（FILE-102 §3：不用 librosa 做对齐）
        "scipy.spatial.distance",  # cdist 帧间距离
        "gc",  # FILE-102 INV-102-7：回溯后释放距离矩阵
    ),
    "harmonica_eval/core/features.py": (
        "..contract",
        "..profile",  # PORT_INDEX：端口声明是特征物化的唯一依据
        "numpy", "numpy.typing",
        # ★ librosa：FILE-103 §3 允许 chroma / pyin 走 librosa
        #   （与 FILE-102 对齐层的「不用 librosa」不矛盾——不同层、不同职责）
        "librosa",
    ),
    "harmonica_eval/core/surface.py": (
        "..contract",
        "..profile",  # ★ `from .. import profile`（module=None、名字在 names 里）
        ".align", ".features",  # 同层：物化 12 端口时消费对齐与特征
        "numpy", "numpy.typing", "math", "hashlib", "types", "typing",
    ),
    "harmonica_eval/core/api.py": (
        "..contract",
        "..profile",  # PROFILE_VERSION / 端口完整性校验
        ".surface", ".align", ".ingest",  # 同层：门面组装 Surface / 数据面就位检测
        "dataclasses", "typing", "uuid",
    ),
    "harmonica_eval/algorithms/timing.py": (
        # ★ BI = FILE-202-v1.md。刻意不含 .pitch/.dynamics：
        #   算法互不知道对方存在。
        "..contract", "math", "numpy", "time",
    ),
    "harmonica_eval/algorithms/dynamics.py": (
        # ★ BI = FILE-203-v1.md。刻意不含 .pitch/.timing：
        #   notes 坐标由 dynamics 自己从 rms 端口切，不问别的算法。
        "..contract", "collections.abc", "math", "numpy", "statistics", "typing",
    ),
    "harmonica_eval/host/app.py": (
        # ★ BI = FILE-301-v1.md。C1 编排层：只消费框架，不认识具体算法。
        "..contract",
        "..algorithms.bootstrap",  # ★ GC-204-08 甲：唯一物理装配根
        "..algorithms.registry",   # Registry 是数据容器，非具体算法
        "..algorithms.runtime",    # ResolvedSurface / resolve_inputs / validate_result
        "..core.api",              # HostCore：数据面门面
        "pathlib", "typing",
        # ★ 刻意不含 ..algorithms.pitch / .timing / .dynamics
        #   ——GC-204-08 冻结：Host 不得 import 具体算法模块。
        #   verify_shell 另有 AST 级检查（按「是否定义 run()」判别），双保险。
    ),
    "harmonica_eval/__main__.py": (
        # ★ BI = FILE-002-v1.md。刻意不含 .cockpit：
        #   FILE-002:45「两者之间零依赖、零 import、零调用」
        ".contract",  # `from .contract import ...`（同包顶层）
        ".host.app",  # build_default_app
        "argparse", "json", "pathlib", "sys", "typing",
    ),
    "harmonica_eval/cockpit/app.py": (
        # ★ BI = FILE-401-v1.md。C4 只读投影：它看得见 UiView，看不见数据面。
        "..contract",
        # ★ Python 标准库：序列化 + 本机 HTTP + 进程控制 + 浏览器唤起
        "html", "http.server", "json", "os", "signal",
        "socket", "subprocess", "sys", "threading", "time", "typing",
        "urllib.parse", "webbrowser",
        # ★ 刻意不含 ..core / ..algorithms / ..host
        #   ——数据面细节不得进入前端。
    ),
    "harmonica_eval/cockpit/__init__.py": (
        "..contract",
        ".app",  # 同包：转调 launch_cockpit
    ),
    "harmonica_eval/serve_ui.py": (
        # ★ FILE-400:17「上游 = 包外装配方（进程装配点）」。
        #   它【不属于 C1/C2/C3/C4 任一层】，是 FILE-002:45 那条零 import
        #   约束的【唯一合法出口】，而它不是 __main__。
        "host.app",  # 取 UiProjectionPort 实现（C1 提供）
        ".host.app",  # ★ 局部 import：`from .host.app import build_default_app`
        ".cockpit",  # 启动 C4（launch_cockpit）
        "argparse", "sys",
        # ★ 刻意不含 ..core / ..algorithms
        #   ——否则它就是绕过 12 端口深接口的后门。
    ),
}
"""已授权注入文件的 import 白名单前缀（精确路径 → 允许前缀元组）。

★ 白名单之外一律 forbidden —— 新增依赖必然暴露。
★ `registry` 刻意只允许 contract：FILE-204 铭牌 MUST
  「只依赖 contract.PluginSpec，不依赖具体算法模块」，
  若它 import 了 pitch/timing/dynamics，本判据会立即变红。
★ `runtime` 同理只允许 contract + 纯数学/容器标准库
  （FILE-205：执行期校验层，对具体算法一无所知）。
"""


def check_layer_imports(rel: str, tree: ast.Module, problems: list[str]) -> int:
    """对装配层已授权文件施加各自的 import 边界（默认拒绝）。"""
    allowed = AUTHORIZED_IMPL_ALLOWED_PREFIXES[rel]
    total = 0
    for name in sorted(set(imported_modules(tree))):
        total += 1
        if name.startswith("__future__"):
            continue
        # ★ 相对写法按「前缀 + '.' 边界」匹配，避免 `.registry` 误配 `.registry_extra`
        if any(name == p or name.startswith(p + ".") for p in allowed):
            continue
        # ★ 顶层模块（无点）**不再无条件放行** —— 那会让 `import numpy`
        #   之类的 DSP 库从白名单眼皮底下溜过去，豁免就变成了放弃检查。
        #   标准库必须由该文件的白名单**显式登记**（默认拒绝）。
        if "." not in name.rstrip(".") and name in allowed:
            continue
        problems.append(
            f"{rel}::import {name} 不在该层白名单内"
            f"；本文件只允许 {' / '.join(allowed)}"
        )
    return total


def _body_raises_not_implemented(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """★ 函数体里是否有任何 `raise NotImplementedError`（带不带 FILE-ID 都算）。

    ★ 这是「待注入空壳」的可靠信号：已实现的函数不会抛它。
    ★★ 必须逐个 raise 节点 AST 判定，不许用「文件里出现过该字符串」粗筛 ——
    ★★ docstring 里提到 SHELL 的已实现函数会被误判成空壳。
    ★★ 带不带 `SHELL: FILE-` 前缀都算：裸的 `NotImplementedError`
    ★★   同样表示「这里本该有实现却没写」，★ 空壳检查必须盯上它
    ★★   （由 check_shell 报「抛错但缺 FILE-ID」）。
    """
    for node in ast.walk(fn):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        # NotImplementedError(...) / NotImplementedError("…") / 名字引用
        target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
        name = getattr(target, "id", None) or getattr(target, "attr", None)
        if name == "NotImplementedError":
            return True
    return False


def collect(path: pathlib.Path) -> tuple[list[Member], list[Member], list[Member]]:
    """返回 (protocol_members, ground_functions, shell_members)。"""
    src = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(REPO))
    tree = ast.parse(src)
    protos: list[Member] = []
    ground: list[Member] = []
    shells: list[Member] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            is_proto = node.name in PROTOCOL_CLASSES
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if is_contract_value_semantics(rel, node, item):
                    ground.append(
                        Member(tag=f"{node.name}::{item.name}", kind=decorator_kind(item))
                    )
                    continue
                if (
                    item.name.startswith("__")
                    and item.name.endswith("__")
                    and (rel != CONTRACT_FILE or is_proto)
                ):
                    continue
                member = Member(
                    tag=f"{node.name}::{item.name}",
                    kind=decorator_kind(item),
                )
                if is_proto:
                    protos.append(member)
                elif rel in AUTHORIZED_IMPL_FILES:
                    ground.append(member)
                else:
                    shells.append(member)
        elif isinstance(node, ast.Module):
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if (
                    item.name.startswith("__")
                    and item.name.endswith("__")
                    and rel != CONTRACT_FILE
                ):
                    continue
                member = Member(tag=f"<module>::{item.name}", kind="method")
                # ★★ contract.py 的【模块级函数】绝大多数是已实现的冻结契约
                #   （hop_of / wire_shape 之类），本就不该含 SHELL。
                # ★★ 此前只给 profile.py 开了豁免，contract.py 被漏掉 →
                #   hop_of 被 collect() 归入 shells，再由 check_shell() 用
                #   None 试调参数 → KeyError 被误判成「空壳失效」。
                # ★★ ★★ 豁免的判据是【函数体没有任何 NotImplementedError 抛出】★★
                # ★★ —— 那是「真实现」的可靠信号：
                #   · 已实现函数：没有 NotImplementedError → 豁免（正确）
                #   · 待注入空壳：有 NotImplementedError → 仍受 check_shell 盯上
                # ★★ ★ 反过来用「没含 SHELL 标记」会放过裸的 NotImplementedError
                # ★★ ★ （红端实证：contract.py 里放裸 NotImplementedError 会被放过）
                if (
                    rel in GROUND_FILES
                    or rel in AUTHORIZED_IMPL_FILES
                    or (rel == CONTRACT_FILE and not _body_raises_not_implemented(item))
                ):
                    ground.append(member)
                else:
                    shells.append(member)

    return protos, ground, shells


def callback_for_property(
    descriptor: property,
    kind: Literal["getter", "setter", "deleter"],
) -> object | None:
    """★ 只取 property 描述符的对应回调，绝不把 descriptor 本身当函数调用。"""
    callbacks = {
        "getter": descriptor.fget,
        "setter": descriptor.fset,
        "deleter": descriptor.fdel,
    }
    # ★ 键集合只含三种回调种类，非法 kind 必须显式失败，不能用 get 蒙混。
    if kind not in callbacks:
        raise ValueError(f"不是 property 回调种类：{kind}")
    return callbacks[kind]


def check_shell(
    path: pathlib.Path,
    mod: object,
    member: Member,
    problems: list[str],
    mutable_properties: list[str],
) -> bool:
    """检查一个待注入成员；返回它是否满足正确 SHELL 断言。"""
    rel = path.relative_to(REPO)
    cls_name, _, member_name = member.tag.partition("::")
    holder = mod if cls_name == "<module>" else getattr(mod, cls_name, None)
    if holder is None:
        problems.append(f"{rel}::{member.tag} 符号不存在")
        return False

    raw = getattr(holder, member_name, None)
    if raw is None:
        problems.append(f"{rel}::{member.tag} 属性不存在")
        return False

    if member.kind == "method":
        if isinstance(raw, property):
            problems.append(
                f"{rel}::{member.tag} AST 分类为方法，但运行时是 property 描述符"
            )
            return False
        target = raw
        pass_self = cls_name != "<module>"
    else:
        if not isinstance(raw, property):
            problems.append(
                f"{rel}::{member.tag} AST 分类为属性 {member.kind}，"
                f"但运行时对象是 {type(raw).__name__}，不是 property"
            )
            return False
        target = callback_for_property(raw, member.kind)
        if target is None:
            problems.append(f"{rel}::{member.tag} property.{member.kind} 回调不存在")
            return False
        pass_self = cls_name != "<module>"
        if member.kind in ("setter", "deleter"):
            # ★ 项目原则上不应有可写属性；仍调用回调完成检查，但同时报告设计问题。
            mutable_properties.append(f"{rel}::{member.tag}（property.{member.kind} 非 None）")
            problems.append(f"{rel}::{member.tag} 发现可写/可变属性 —— 这是设计问题")

    try:
        params = list(inspect.signature(target).parameters.values())
    except (TypeError, ValueError) as exc:
        problems.append(f"{rel}::{member.tag} 无法取得可调用签名：{exc}")
        return False

    if pass_self and params and params[0].name in ("self", "cls"):
        # ★ 通过类取得的是未绑定函数，其签名包含 self/cls。
        # 若既在签名里算了它、又显式再传一次，TypeError 会伪装成空壳失效。
        params = params[1:]
    args = [
        None
        for param in params
        if param.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        and param.default is inspect.Parameter.empty
    ]

    try:
        if pass_self:
            target(None, *args)
        else:
            target(*args)
    except NotImplementedError as exc:
        if "SHELL: FILE-" in str(exc):
            return True
        problems.append(f"{rel}::{member.tag} 抛错但缺 FILE-ID")
        return False
    except Exception as exc:
        problems.append(
            f"{rel}::{member.tag} 抛了 {type(exc).__name__}: "
            f"{str(exc)[:60]}（应为 NotImplementedError）"
        )
        return False

    problems.append(f"{rel}::{member.tag} 未抛错 → 空壳失效")
    return False


def main() -> int:
    print("=" * 72)
    print('空壳"调用必炸"验证 · verify_stubs_raise.py')
    print("=" * 72)

    sys.path.insert(0, str(REPO))
    protocol_members: list[tuple[pathlib.Path, Member]] = []
    ground: list[Member] = []
    shells: list[tuple[pathlib.Path, Member]] = []
    problems: list[str] = []
    mutable_properties: list[str] = []
    property_outcomes: list[tuple[pathlib.Path, Member, bool]] = []
    method_ok = 0
    authorized_files: list[tuple[str, int]] = []

    for path in sorted((REPO / "harmonica_eval").rglob("*.py")):
        rel = str(path.relative_to(REPO))
        mod_name = str(path.relative_to(REPO).with_suffix("")).replace("/", ".")
        if mod_name.endswith(".__init__"):
            mod_name = mod_name[:-9]
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:
            problems.append(f"{mod_name}: import 失败 {exc}")
            continue

        # ★ 豁免 4：授权实现文件改施 import 边界判据（不放弃检查）
        if rel in AUTHORIZED_IMPL_FILES:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            # ★ 装配层文件各有自己的白名单（bootstrap 要 import 具体算法；
            #   registry 刻意只许 contract）——不能套用 C4 那条统一判据。
            checker = (
                check_layer_imports
                if rel in AUTHORIZED_IMPL_ALLOWED_PREFIXES
                else check_authorized_imports
            )
            count = checker(rel, tree, problems)
            authorized_files.append((rel, count))

        protos, ground_members, shell_members = collect(path)
        protocol_members.extend((path, member) for member in protos)
        ground.extend(ground_members)
        for member in shell_members:
            passed = check_shell(path, mod, member, problems, mutable_properties)
            shells.append((path, member))
            if member.kind == "method" and passed:
                method_ok += 1
            if member.kind != "method":
                property_outcomes.append((path, member, passed))

    method_total = sum(member.kind == "method" for _, member in shells)
    getter_total = sum(member.kind == "getter" for _, member in shells)
    setter_total = sum(member.kind == "setter" for _, member in shells)
    deleter_total = sum(member.kind == "deleter" for _, member in shells)
    getter_ok = sum(
        member.kind == "getter" and passed for _, member, passed in property_outcomes
    )
    setter_ok = sum(
        member.kind == "setter" and passed for _, member, passed in property_outcomes
    )
    deleter_ok = sum(
        member.kind == "deleter" and passed for _, member, passed in property_outcomes
    )

    protocol_methods = sum(member.kind == "method" for _, member in protocol_members)
    protocol_getters = sum(member.kind == "getter" for _, member in protocol_members)
    protocol_setters = sum(member.kind == "setter" for _, member in protocol_members)
    protocol_deleters = sum(member.kind == "deleter" for _, member in protocol_members)

    print(
        f"\n  豁免 1 Protocol 成员（类型声明，用 ... 正确）: "
        f"{protocol_methods} 个方法 / {protocol_getters} 个属性 getter / "
        f"{protocol_setters} 个属性 setter / {protocol_deleters} 个属性 deleter"
    )
    print(
        "  豁免 2 已实现的地基成员（模块函数 + 契约值语义）         : "
        f"{len(ground)}"
    )
    if authorized_files:
        print(
            "  豁免 4 已授权实现（不适用调用必炸，改受 import 边界判据）:"
        )
        for rel, count in authorized_files:
            print(f"   - {rel}：{count} 条 import 全部核对（白名单外即违规）")
    print(
        f"  待验证空壳                                      : "
        f"{method_total} 个方法 / {getter_total} 个属性 getter / "
        f"{setter_total} 个属性 setter / {deleter_total} 个属性 deleter"
    )
    print(
        f"  其中正确抛 NotImplementedError 且带 FILE-ID      : "
        f"{method_ok} 个方法 / {getter_ok} 个属性 getter / "
        f"{setter_ok} 个属性 setter / {deleter_ok} 个属性 deleter"
    )

    print("\n  属性明细（method 与 property 描述符分开报告）")
    for path, member in protocol_members:
        if member.kind != "method":
            print(
                f"   - {path.relative_to(REPO)}::{member.tag} · "
                f"属性 {member.kind} · Protocol 声明豁免，已计入"
            )
    for path, member, passed in property_outcomes:
        state = "正确 SHELL" if passed else "未通过"
        print(
            f"   - {path.relative_to(REPO)}::{member.tag} · "
            f"属性 {member.kind} · {state}"
        )
    if not any(member.kind != "method" for _, member in protocol_members) and not property_outcomes:
        print("   （无）")

    if mutable_properties:
        print("\n  ★ 可写/可变属性（设计问题）")
        for item in mutable_properties:
            print(f"   - {item}")

    print()
    if problems:
        print(f"❌ {len(problems)} 条问题：")
        for problem in problems[:30]:
            print("   -", problem)
        return 1
    if method_total + getter_total + setter_total + deleter_total and (
        method_ok + getter_ok + setter_ok + deleter_ok
        != method_total + getter_total + setter_total + deleter_total
    ):
        print("❌ 存在未满足『调用必炸』断言的空壳")
        return 1
    print("✅ 全部空壳的『调用必炸』断言成立")
    print("   → 普通方法与 property 回调都不可能静默返回，也不会把 descriptor 当函数调用")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
