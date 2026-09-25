#!/usr/bin/env python3
"""检查 BI 中数量声明与当前 Python 结构是否一致。

★ 口径分两层：

1. **发现层**：扩大句式识别（“恰好 / 恰 / 共 / 总共 / 长度为 / 仅 / 只”）
   以及裸写的 “N 个操作 / 端口 / 字段 / 键 …”。
2. **判定层**：只有“文档文件 + 行号 + 明确结构来源”能连上的声明才判 PASS/FAIL。
   其余一律输出 ``SKIPPED``，绝不拿邻近列表或历史更正块猜数。

这比旧版多覆盖的根因是：旧版只把数字后面的“紧邻列表项数”当事实来源；
现在改为按声明的语义接 AST、常量元组、枚举成员、Protocol 方法或
``profile.PORTS``。因此“共 N 个端口”接 ``len(profile.PORTS)``，
“恰 N 个操作”接对应 Protocol 的方法数，数字错了就会红。
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import re
import sys
from collections import defaultdict

REPO = pathlib.Path(__file__).resolve().parent.parent
BUILD = REPO / ".spec" / "build"

NUMBER = r"(?:\d+|[一二两三四五六七八九十百]+)"
COUNT_NOUNS = (
    r"个|条|项|键|值|成员|字段|操作|方法|函数|符号|模块|语句|节点|行|名字|端口|"
    r"异常类|枚举|算法|命令|按钮|阶段|状态|音级|文件|公开面|入口|元素|常量元组|类型注记"
)
STRONG_PREFIX = r"恰(?:好)?|共|总共|总计|长度为|长度恰为|仅(?:有|含|这)|只(?:有|含|允许|列|是)|穷举"
DISCOVERY = re.compile(
    rf"(?:{STRONG_PREFIX})\s*({NUMBER})\s*(?:{COUNT_NOUNS})"
    rf"|(?<!第)\b({NUMBER})\s*个(?:操作|端口|字段|元素|键|名字|模块|语句|成员|异常类|函数|方法|阶段|状态|命令|按钮|音级|文件|入口)\b"
)
SKIP_MARKERS = (
    "原写", "改成", "更正", "上一版", "已作废", "本版冻结", "本版更正",
    "本版修正", "本版已", "本版明确", "本版口径", "本版不变", "本版强制",
    "本版才", "本版为", "本版规定", "本版新增", "本版另", "本版执行",
    "本版仍", "本版将", "本版取消", "本版允许", "本版要求", "本版删除",
    "本版只", "本版明确", "本版全", "本版同步", "本版写", "本版不",
)


@dataclasses.dataclass(frozen=True)
class Rule:
    """一条可机械判定的数量声明。

    ★ `line_no` 指向文档中**含该数量声明的行**。但文档会被重写，
    行号会漂移 —— 本轮重铸 FILE-200 / 同步 FILE-003 后，
    25 条 Rule 全部失配，全是"行号漂移"而非"声明错了"。
    因此 `locate` 字段允许按**内容**重新定位：给一个必须出现在该行的
    稳定子串（通常是反引号包起来的标识符）。
    定位顺序：先试 `line_no`；若该行不含 `locate`，再在全文里找
    **唯一**含 `locate` 的行；仍找不到才报错。
    唯一性很重要：找不到和多处匹配都算失败，避免"随便挑一行"蒙混过关。
    """

    filename: str
    line_no: int
    label: str
    claim: re.Pattern[str]
    source_key: str
    locate: str = ""


RULES = (
    # ★ FILE-001：包公开子模块接 AST 赋值元组。
    Rule("FILE-001-v1.md", 186, "PUBLIC_SUBMODULES", re.compile(r"恰好含\s*(\d+)\s*个名字"), "public_submodules"),
    # ★ FILE-002：入口导出面、SHELL 占位、UiSeries 字段接 AST。
    Rule("FILE-002-v1.md", 75, "contract.Protocol", re.compile(r"(\d+)\s*个\s*`Protocol`"), "contract_protocols"),
    Rule("FILE-002-v1.md", 78, "contract.Enum", re.compile(r"(\d+)\s*个\s*`Enum`"), "contract_enums"),
    Rule("FILE-002-v1.md", 78, "contract.dataclass", re.compile(r"`Enum`、(\d+)\s*个\s*`dataclass`"), "contract_dataclasses"),
    Rule("FILE-002-v1.md", 78, "contract.异常类", re.compile(r"`dataclass`、(\d+)\s*个异常类"), "contract_exceptions"),
    Rule("FILE-002-v1.md", 78, "contract.常量元组", re.compile(r"异常类、(\d+)\s*个常量元组"), "contract_constant_tuples"),
    Rule("FILE-002-v1.md", 396, "UiSeries 字段", re.compile(r"字段恰好\s*(\d+)\s*个"), "ui_series_fields", "`contract.UiSeries` 的字段恰好 7 个 ——"),
    # ★ 2026-09-25 三处锚点 -1：FILE-002 的报告格式块净减 1 行
    #   （原「- 参考：」「- 练习：」两行合并为「输入：」一行），
    #   该块位于这三个锚点之前，故其后锚点整体上移一行。
    Rule("FILE-002-v1.md", 472, "UiSeries 字段（重申）", re.compile(r"字段恰好\s*(\d+)\s*个"), "ui_series_fields", "`contract.UiSeries` 的字段恰好 7 个："),
    Rule("FILE-002-v1.md", 513, "__main__.__all__", re.compile(r"恰好\*\*为以下\s*(\d+)\s*项"), "main_all", "`__all__` 必须**恰好**为以下 13 项"),
    # ★ FILE-002 的 SHELL 占位判据：原为阶段态（「共 7 处」），注入完成即失效
    #   （check_counts 报「声明 7，实际 0」）。已改为永续形态「必须为 0」——
    #   注入前 7≠0 红、注入后 0=0 绿，任何阶段都成立。
    # ★ 两条重复规则合并为一条：它们指向同一句话、同一个数字，重复只会双份漂移。
    Rule("FILE-002-v1.md", 517, "SHELL 占位（永续：必须为 0）", re.compile(r"SHELL 占位数\s*=\s*(\d+)"), "main_shells", "SHELL 占位数 = 0"),
    # ★ FILE-003：契约常量、枚举、异常族与 Protocol 操作全部接 AST。
    Rule("FILE-003-v1.md", 45, "contract 标准库依赖", re.compile(r"共\s*(\d+)\s*个"), "contract_stdlib_imports"),
    Rule("FILE-003-v1.md", 50, "contract 第三方依赖", re.compile(r"共\s*(\d+)\s*个"), "contract_thirdparty_imports"),
    Rule("FILE-003-v1.md", 122, "FIELD_LAYOUTS 键", re.compile(r"全部\s*(\d+)\s*键"), "field_layouts"),
    Rule("FILE-003-v1.md", 126, "chroma 音级", re.compile(r"(\d+)\s*个音级"), "chroma_pitch_classes"),
    Rule("FILE-003-v1.md", 136, "UNITS_VOCABULARY", re.compile(r"穷举\s*(\d+)\s*个合法值"), "units_vocabulary"),
    Rule("FILE-003-v1.md", 161, "CORE_REQUIRED_PORTS", re.compile(r"全部\s*(\d+)\s*项"), "core_required_ports"),
    Rule("FILE-003-v1.md", 171, "ErrorCode 枚举", re.compile(r"ErrorCode`\s*的\s*(\d+)\s*个"), "error_codes", "`ErrorCode` 的 12 个"),
    Rule("FILE-003-v1.md", 173, "AlgorithmDataContract 操作", re.compile(r"(\d+)\s*个纯查表操作"), "algorithm_data_ops", "4.9 AlgorithmDataContract"),
    Rule("FILE-003-v1.md", 198, "HostContract 操作", re.compile(r"，\s*(\d+)\s*操作"), "host_ops", "4.10 HostContract"),
    Rule("FILE-003-v1.md", 210, "FORBIDDEN_OPERATIONS", re.compile(r"穷举（(\d+)\s*项）"), "forbidden_operations", "`FORBIDDEN_OPERATIONS` 穷举（10 项）"),
    Rule("FILE-003-v1.md", 214, "ErrorCode 标题", re.compile(r"Enum，\s*(\d+)\s*值"), "error_codes", "4.11 ErrorCode"),
    Rule("FILE-003-v1.md", 233, "HarmonicaError 异常子类", re.compile(r"（(\d+)\s*个异常类"), "harmonica_error_subclasses", "4.12 HarmonicaError 族"),
    Rule("FILE-003-v1.md", 261, "UiCommandKind", re.compile(r"Enum，\s*(\d+)\s*值"), "ui_command_kinds", "`UiCommandKind`（Enum，6 值）"),
    Rule("FILE-003-v1.md", 267, "UiProjectionPort 操作", re.compile(r"，\s*(\d+)\s*操作"), "ui_projection_ops", "4.15 UiProjectionPort"),
    Rule("FILE-003-v1.md", 315, "FIELD_LAYOUTS（INV）", re.compile(r"恰\s*(\d+)\s*键"), "field_layouts", "| INV-003-4 | `FIELD_LAYOUTS` 封闭且顺序冻结：恰 4 键"),
    Rule("FILE-003-v1.md", 316, "UNITS_VOCABULARY（INV）", re.compile(r"恰\s*(\d+)\s*个元素"), "units_vocabulary", "`UNITS_VOCABULARY` 封闭：恰"),
    Rule("FILE-003-v1.md", 316, "CORE_REQUIRED_PORTS（INV）", re.compile(r"恰\s*(\d+)\s*项"), "core_required_ports", "`UNITS_VOCABULARY` 封闭：恰"),
    Rule("FILE-003-v1.md", 316, "FORBIDDEN_OPERATIONS（INV）", re.compile(r"恰\s*(\d+)\s*项且含"), "forbidden_operations", "`UNITS_VOCABULARY` 封闭：恰"),
    Rule("FILE-003-v1.md", 77, "SessionState", re.compile(r"Enum，\s*(\d+)\s*值"), "session_states", "### 4.1 SessionState"),
    Rule("FILE-003-v1.md", 97, "TimelineBasis", re.compile(r"Enum，\s*(\d+)\s*值"), "timeline_bases", "### 4.2 TimelineBasis"),
    Rule("FILE-003-v1.md", 319, "AlgorithmDataContract（INV）", re.compile(r"恰\s*(\d+)\s*个操作"), "algorithm_data_ops", "| INV-003-8 |"),
    Rule("FILE-003-v1.md", 320, "HostContract（INV）", re.compile(r"恰\s*(\d+)\s*个操作"), "host_ops", "| INV-003-9 |"),
    Rule("FILE-003-v1.md", 322, "ErrorCode（INV）", re.compile(r"恰\s*(\d+)\s*值"), "error_codes", "| INV-003-11 |"),
    # ★ FILE-004：import 节点、profile 端口、配置字段和 __all__。
    Rule("FILE-004-v1.md", 56, "profile import 语句", re.compile(r"共\s*(\d+)\s*条语句"), "profile_imports"),
    Rule("FILE-004-v1.md", 58, "profile 标准库 import", re.compile(r"恰好\s*(\d+)\s*条"), "profile_stdlib_imports"),
    Rule("FILE-004-v1.md", 64, "profile 本包 import", re.compile(r"恰好\s*(\d+)\s*条"), "profile_local_imports"),
    Rule("FILE-004-v1.md", 232, "profile.PORTS", re.compile(r"长度\*\*恰好\s*(\d+)"), "ports"),
    Rule("FILE-004-v1.md", 258, "PORT_INDEX 键", re.compile(r"键为\s*(\d+)\s*个"), "port_index"),
    Rule("FILE-004-v1.md", 297, "profile.__all__", re.compile(r"恰好\s*(\d+)\s*个"), "profile_all"),
    Rule("FILE-004-v1.md", 348, "profile 配置 dataclass", re.compile(r"(五个)类"), "profile_config_dataclasses"),
    # ★ 含 PortSpec（9 字段）：与 :378 的 config_classes 五类一致；断言 5+4+7+2+9=27
    Rule("FILE-004-v1.md", 349, "profile 配置字段", re.compile(r"字段数\s*`=\s*5\s*\+\s*4\s*\+\s*7\s*\+\s*2\s*\+\s*9\s*=\s*(\d+)`"), "profile_config_fields"),
    Rule("FILE-004-v1.md", 350, "profile 端口表", re.compile(r"§4\.7 的\s*(\d+)\s*行全表"), "ports"),
    Rule("FILE-004-v1.md", 351, "profile import（INV）", re.compile(r"只有\s*(\d+)\s*条"), "profile_imports"),
    Rule("FILE-004-v1.md", 362, "produced_by 类别", re.compile(r"取自\s*(\d+)\s*个值"), "produced_by_kinds"),
    Rule("FILE-004-v1.md", 371, "profile.__all__（INV）", re.compile(r"恰好\s*(\d+)\s*个名字"), "profile_all"),
    Rule("FILE-004-v1.md", 371, "profile.__all__ 存在性（INV）", re.compile(r"`__all__` 恰好\s*(\d+)\s*个名字"), "profile_all"),
    # ★ FILE-100：冻结壳件的结构常量。
    Rule("FILE-100-v1.md", 23, "core 文件行数", re.compile(r"冻结\*\*的：(\d+)\s*行"), "core_lines"),
    Rule("FILE-100-v1.md", 23, "core 顶层 AST 节点", re.compile(r"行、\s*(\d+)\s*个顶层 AST 节点"), "core_top_nodes"),
    Rule("FILE-100-v1.md", 23, "core import 语句", re.compile(r"节点、\s*(\d+)\s*条 import 语句"), "core_imports"),
    Rule("FILE-100-v1.md", 23, "core.__all__", re.compile(r"语句、`__all__` 含\s*(\d+)\s*个元素"), "core_all"),
    Rule("FILE-100-v1.md", 65, "core 顶层节点（标题）", re.compile(r"冻结为\s*(\d+)\s*个 AST 节点"), "core_top_nodes"),
    Rule("FILE-100-v1.md", 74, "core 行数（口径）", re.compile(r"等于\s*(\d+)"), "core_lines"),
    Rule("FILE-100-v1.md", 84, "core import（口径）", re.compile(r"\)\s*==\s*(\d+)"), "core_imports"),
    Rule("FILE-100-v1.md", 101, "core.__all__（口径）", re.compile(r"len\(value\.elts\)\s*==\s*(\d+)"), "core_all"),
    Rule("FILE-100-v1.md", 138, "core docstring 冻结键", re.compile(r"下列\s*(\d+)\s*个键"), "core_doc_keys"),
    Rule("FILE-100-v1.md", 178, "core 门面说明行", re.compile(r"`core\.<name>`\s*(\d+)\s*行"), "core_facade_lines"),
    Rule("FILE-100-v1.md", 224, "core import（INV）", re.compile(r"恰好\s*(\d+)\s*条 import"), "core_imports"),
    Rule("FILE-100-v1.md", 227, "core.__all__（INV）", re.compile(r"恰好\s*(\d+)\s*个"), "core_all"),
    Rule("FILE-100-v1.md", 230, "core docstring 键（INV）", re.compile(r"含\s*(\d+)\s*个冻结键"), "core_doc_keys"),
    Rule("FILE-100-v1.md", 231, "core 冻结行数（INV）", re.compile(r"文件\s*(\d+)\s*行"), "core_lines"),
    Rule("FILE-100-v1.md", 231, "core 冻结节点（INV）", re.compile(r"行、\s*(\d+)\s*个顶层节点"), "core_top_nodes"),
    # ★ FILE-105 的依赖清单描述“应实现结构”，当前 skeleton 尚未 import；不能拿现状硬比，跳过。
    # ★ FILE-103：总端口与本文件生产端口数。
    Rule("FILE-103-v1.md", 21, "profile 端口总数", re.compile(r"声明\s*(\d+)\s*个端口"), "ports"),
    Rule("FILE-103-v1.md", 21, "features 生产端口", re.compile(r"其中\s*\*\*(\d+)\s*个端口由本文件生产"), "features_ports"),
    # ★ C3 插件化后：ALGORITHMS 与 PAYLOAD_SCHEMAS 已删除
    # （注册表不再硬绑具体算法；payload 改为自描述 Sequence[UiScalar|UiSeries]）。
    # 旧的 5 条 Rule 因此全部作废，替换为以**新契约**为事实来源的规则。
    # ★ FILE-200 的重写版在 §4.3 用中文数词"恰好是这三个名字"表述（刻意不用"恰 N"，
    # 以免再造一个随命名变动而失效的数量陷阱）。因此这里把判据挂到 §8.2 的
    # **可执行断言**上 —— `assert len(A.__all__) == 3` 才是真正会被机械判定的那一句。
    Rule("FILE-200-v1.md", 210, "algorithms.__all__", re.compile(r"assert len\(A\.__all__\) ==\s*(\d+)"), "algorithms_all"),
    Rule("FILE-203-v1.md", 229, "AlgorithmResultEnvelope 字段", re.compile(r"它的\s*(\d+)\s*个字段"), "result_envelope_fields"),
    # ★ FILE-204：§4 正文刻意用中文数词（"三个空方法"），因为那些是散文不是断言。
    # 可机械判定的数字在文末"事实表"里，用的是阿拉伯数字 —— 挂在那里。
    Rule("FILE-204-v1.md", 409, "PluginSpec 字段", re.compile(r"`PluginSpec` 字段数 \|\s*(\d+)"), "plugin_spec_fields", "`PluginSpec` 字段数 |"),
    Rule("FILE-204-v1.md", 410, "InputRequirement 字段", re.compile(r"`InputRequirement` 字段数 \|\s*(\d+)"), "input_requirement_fields", "`InputRequirement` 字段数 |"),
    # Registry 操作数：事实表里以 `register`/`list`/`get` 三项列出。
    Rule("FILE-204-v1.md", 96, "Registry 操作数", re.compile(r"`register`、`list`、`get`\s*([零一两三四五六七八九十]+)\s*个操作"), "registry_ops", "- **公开操作**"),
    # ★ FILE-300 / FILE-400：包公开面。
    Rule("FILE-300-v1.md", 93, "host.__all__", re.compile(r"恰好\s*(\d+)\s*个元素"), "host_all"),
    Rule("FILE-400-v1.md", 64, "cockpit 公开面", re.compile(r"恰好(两)项"), "cockpit_public_surface"),
    # ★ FILE-401：依赖、契约符号、公开面、按钮表。
    Rule("FILE-401-v1.md", 61, "app 允许标准库模块", re.compile(r"共\s*(\d+)\s*条"), "app_allowed_stdlib"),
    Rule("FILE-401-v1.md", 80, "app contract 符号", re.compile(r"恰好\s*(\d+)\s*个符号"), "app_contract_symbols"),
    Rule("FILE-401-v1.md", 115, "app.__all__", re.compile(r"`__all__` 恰为\s*(\d+)\s*项"), "app_all"),
    Rule("FILE-401-v1.md", 161, "COMMAND_LABELS", re.compile(r"恰好\s*(\d+)\s*项"), "command_labels"),
    Rule("FILE-401-v1.md", 227, "命令按钮", re.compile(r"恰好\s*(\d+)\s*个\*\*按钮"), "command_labels"),
    Rule("FILE-401-v1.md", 576, "COMMAND_LABELS（验收）", re.compile(r"恰\s*(\d+)\s*项"), "command_labels"),
    Rule("FILE-401-v1.md", 1010, "app.__all__（验收）", re.compile(r"恰\s*(\d+)\s*项"), "app_all"),
)

# 没有数字捕获的规则用固定值；它们只用于检查结构声明。
FIXED_CLAIMS = {"cockpit_all": 1, "profile_config_dataclasses": 5, "cockpit_public_surface": 2}


def parse(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def class_node(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise KeyError(f"class {name} not found")


def assigned_value(tree: ast.Module, name: str) -> ast.expr:
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            return node.value
    raise KeyError(f"assignment {name} not found")


def collection_length(node: ast.expr | None) -> int:
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return len(node.elts)
    if isinstance(node, ast.Dict):
        return len(node.keys)
    if isinstance(node, ast.DictComp):
        ports = assigned_value(parse(REPO / "harmonica_eval" / "profile.py"), "PORTS")
        return collection_length(ports)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "frozenset":
        return collection_length(node.args[0]) if node.args else 0
    if node is None:
        return 0
    raise TypeError(ast.dump(node, include_attributes=False))


def import_modules(tree: ast.Module) -> list[str]:
    result: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            result.append(("." * node.level) + (node.module or ""))
    return result


def top_import_count(tree: ast.Module) -> int:
    return sum(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)


def is_dataclass(node: ast.ClassDef) -> bool:
    return any(
        (isinstance(d, ast.Name) and d.id == "dataclass")
        or (isinstance(d, ast.Attribute) and d.attr == "dataclass")
        or (isinstance(d, ast.Call) and (
            (isinstance(d.func, ast.Name) and d.func.id == "dataclass")
            or (isinstance(d.func, ast.Attribute) and d.func.attr == "dataclass")
        ))
        for d in node.decorator_list
    )


def class_fields(node: ast.ClassDef) -> int:
    return sum(isinstance(child, (ast.Assign, ast.AnnAssign)) for child in node.body)


def enum_members(node: ast.ClassDef) -> int:
    return sum(
        isinstance(child, ast.Assign)
        and len(child.targets) == 1
        and isinstance(child.targets[0], ast.Name)
        for child in node.body
    )


def class_methods(node: ast.ClassDef) -> list[str]:
    return [
        child.name
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def protocol_operations(node: ast.ClassDef) -> int:
    """Protocol 的公开操作数；@property 是只读状态面，不计为操作。"""
    return sum(
        isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not child.name.startswith("_")
        and not any(
            isinstance(decorator, ast.Name) and decorator.id == "property"
            for decorator in child.decorator_list
        )
        for child in node.body
    )


def public_class_methods(node: ast.ClassDef) -> int:
    return sum(not name.startswith("_") for name in class_methods(node))


def constant_tuple_count(tree: ast.Module) -> int:
    count = 0
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        annotation = node.annotation
        if isinstance(annotation, ast.Subscript) and ast.unparse(annotation.value).endswith("tuple"):
            count += 1
    return count


def shell_raise_count(tree: ast.Module) -> int:
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        call = node.exc
        if isinstance(call, ast.Call) and call.args:
            value = call.args[0]
            if isinstance(value, ast.Constant) and isinstance(value.value, str) and "SHELL" in value.value:
                count += 1
    return count


def produced_by_kinds(tree: ast.Module) -> int:
    value = assigned_value(tree, "PORTS")
    if not isinstance(value, ast.Tuple):
        raise TypeError("PORTS is not a tuple literal")
    kinds: set[str] = set()
    for call in value.elts:
        if not isinstance(call, ast.Call):
            continue
        for kw in call.keywords:
            if kw.arg == "produced_by" and isinstance(kw.value, ast.Constant):
                kinds.add(str(kw.value.value))
    return len(kinds)


def features_port_count(tree: ast.Module) -> int:
    value = assigned_value(tree, "PORTS")
    assert isinstance(value, ast.Tuple)
    return sum(
        isinstance(call, ast.Call)
        and any(kw.arg == "produced_by" and isinstance(kw.value, ast.Constant) and kw.value.value == "core.features" for kw in call.keywords)
        for call in value.elts
    )


def payload_counts(tree: ast.Module) -> dict[str, int]:
    """★ 已作废：PAYLOAD_SCHEMAS 在 C3 插件化中被删除。

    保留此函数仅为让 git 历史能说明"为什么删"：payload 字段名曾经
    需要一张按 algorithm_id 索引的冻结表，那张表住在框架里，导致框架
    必须认识每一个具体算法。现在 payload 是自描述的
    `Sequence[UiScalar | UiSeries]`，字段名随对象走，表不再需要。
    调用方 build_counts() 已不再引用它。
    """
    value = assigned_value(tree, "PAYLOAD_SCHEMAS")
    assert isinstance(value, ast.Dict)
    return {str(k.value): collection_length(v) for k, v in zip(value.keys, value.values, strict=True)}


def build_counts() -> dict[str, int]:
    contract = parse(REPO / "harmonica_eval" / "contract.py")
    profile = parse(REPO / "harmonica_eval" / "profile.py")
    algorithms = parse(REPO / "harmonica_eval" / "algorithms" / "__init__.py")
    root = parse(REPO / "harmonica_eval" / "__init__.py")
    core = parse(REPO / "harmonica_eval" / "core" / "__init__.py")
    main = parse(REPO / "harmonica_eval" / "__main__.py")
    align = parse(REPO / "harmonica_eval" / "core" / "align.py")
    cockpit_init = parse(REPO / "harmonica_eval" / "cockpit" / "__init__.py")
    app = parse(REPO / "harmonica_eval" / "cockpit" / "app.py")
    host = parse(REPO / "harmonica_eval" / "host" / "__init__.py")

    contract_imports = import_modules(contract)
    stdlib = {"__future__", "dataclasses", "enum", "typing"}
    third_party = {"numpy", "numpy.typing"}
    profile_imports = import_modules(profile)
    profile_std = {m.lstrip(".") for m in profile_imports} & stdlib
    profile_local = {m for m in profile_imports if m.startswith(".")}
    app_standard_names = {
        "__future__", "os", "sys", "json", "html", "socket", "http.server",
        "socketserver", "threading", "subprocess", "webbrowser", "typing",
        "urllib.parse", "time", "signal",
    }
    # ★ 只数【模块级】那一行 from ..contract import … ★
    # 用 ast.walk 会把函数体内的延迟 import 也算进来（cockpit/app.py 有两处
    # `from ..contract import SessionState`），而 FILE-401:80 判的正是
    # 「写成目标文件里【那一行】原样」的符号集合 —— 那是模块级 import。
    # 延迟 import 是函数实现细节，不在该判据的语义范围内。
    app_contract_imports: set[str] = set()
    for node in app.body:
        if isinstance(node, ast.ImportFrom) and node.module == "contract" and node.level == 2:
            app_contract_imports.update(alias.name for alias in node.names)

    protocols = [n for n in contract.body if isinstance(n, ast.ClassDef) and any(
        isinstance(d, ast.Name) and d.id == "Protocol" for d in n.bases
    )]
    enums = [n for n in contract.body if isinstance(n, ast.ClassDef) and any(
        isinstance(d, ast.Name) and d.id == "Enum" for d in n.bases
    )]
    dataclasses_ = [n for n in contract.body if isinstance(n, ast.ClassDef) and is_dataclass(n) and n.name != "HarmonicaError"]
    exceptions = [n for n in contract.body if isinstance(n, ast.ClassDef) and any(
        (isinstance(b, ast.Name) and b.id.endswith("Exception"))
        or (isinstance(b, ast.Name) and b.id == "HarmonicaError")
        for b in n.bases
    )]

    # ★ 必须含 PortSpec：FILE-004 INV-4-02 要求「五个 Spec 类的每个字段带单位与依据」，
    #   PortSpec 的 hop_length / max bytes 等字段同样带单位，属该不变量覆盖范围。
    #   漏掉它会使 check_counts 对 PortSpec 的任何字段变化完全失明（假绿）。
    config_classes = [class_node(profile, n) for n in ("AudioSpec", "AlignSpec", "MaterializeSpec", "BudgetSpec", "PortSpec")]
    core_doc = ast.get_docstring(core) or ""
    core_doc_keys = {
        "FILE-ID:", "COMPONENT:", "SPEC:", "ROLE:", "INTENT:", "MUST:",
        "MUST NOT:", "INPUT:", "OUTPUT:", "BUILD-INSTRUCTION:",
    }
    core_expressions = [n.value.value for n in core.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)]
    facade_text = core_expressions[1] if len(core_expressions) > 1 else ""
    facade_lines = sum(bool(re.match(r"\s*core\.[A-Za-z_]+\s*→", line)) for line in facade_text.splitlines())

    cockpit_all = collection_length(assigned_value(cockpit_init, "__all__"))
    cockpit_public = cockpit_all + sum(
        isinstance(n, ast.FunctionDef) and not n.name.startswith("_") for n in cockpit_init.body
    )

    return {
        "public_submodules": collection_length(assigned_value(root, "PUBLIC_SUBMODULES")),
        "contract_protocols": len(protocols),
        "contract_enums": len(enums),
        "contract_dataclasses": len(dataclasses_),
        "contract_exceptions": len(exceptions),
        "contract_constant_tuples": constant_tuple_count(contract),
        "ui_series_fields": class_fields(class_node(contract, "UiSeries")),
        "main_all": collection_length(assigned_value(main, "__all__")),
        "main_shells": shell_raise_count(main),
        "contract_stdlib_imports": len(set(contract_imports) & stdlib),
        "contract_thirdparty_imports": len(set(contract_imports) & third_party),
        "field_layouts": collection_length(assigned_value(contract, "FIELD_LAYOUTS")),
        "chroma_pitch_classes": collection_length(
            next(
                value
                for value in assigned_value(contract, "FIELD_LAYOUTS").values
                if isinstance(value, ast.Tuple)
                and any(isinstance(e, ast.Constant) and e.value == "C#" for e in value.elts)
            )
        ),
        "units_vocabulary": collection_length(assigned_value(contract, "UNITS_VOCABULARY")),
        "core_required_ports": collection_length(assigned_value(contract, "CORE_REQUIRED_PORTS")),
        "error_codes": enum_members(class_node(contract, "ErrorCode")),
        "algorithm_data_ops": protocol_operations(class_node(contract, "AlgorithmDataContract")),
        "host_ops": protocol_operations(class_node(contract, "HostContract")),
        "forbidden_operations": collection_length(assigned_value(contract, "FORBIDDEN_OPERATIONS")),
        "harmonica_error_subclasses": len(exceptions) - 1,
        "session_states": enum_members(class_node(contract, "SessionState")),
        "timeline_bases": enum_members(class_node(contract, "TimelineBasis")),
        "ui_command_kinds": enum_members(class_node(contract, "UiCommandKind")),
        "ui_projection_ops": protocol_operations(class_node(contract, "UiProjectionPort")),
        "profile_imports": top_import_count(profile),
        "profile_stdlib_imports": len(profile_std),
        "profile_local_imports": len(profile_local),
        "ports": collection_length(assigned_value(profile, "PORTS")),
        "port_index": collection_length(assigned_value(profile, "PORT_INDEX")),
        "profile_all": collection_length(assigned_value(profile, "__all__")),
        "profile_config_dataclasses": sum(is_dataclass(n) for n in profile.body if isinstance(n, ast.ClassDef)),
        "profile_config_fields": sum(class_fields(n) for n in config_classes),
        "profile_operational_fields": sum(class_fields(n) for n in config_classes if n.name != "BudgetSpec"),
        "produced_by_kinds": produced_by_kinds(profile),
        "core_lines": len((REPO / "harmonica_eval" / "core" / "__init__.py").read_text(encoding="utf-8").splitlines()),
        "core_top_nodes": len(core.body),
        "core_imports": top_import_count(core),
        "core_all": collection_length(assigned_value(core, "__all__")),
        "core_doc_keys": sum(key in core_doc for key in core_doc_keys),
        "core_facade_lines": facade_lines,
        "features_ports": features_port_count(profile),
        "algorithms_all": collection_length(assigned_value(algorithms, "__all__")),
        "registry_ops": len([
            n for n in ("register", "list", "get")
            if any(
                isinstance(node, ast.FunctionDef) and node.name == n
                for node in ast.walk(
                    parse(REPO / "harmonica_eval" / "algorithms" / "registry.py")
                )
            )
        ]),
        "plugin_spec_fields": class_fields(class_node(contract, "PluginSpec")),
        "input_requirement_fields": class_fields(class_node(contract, "InputRequirement")),
        "result_envelope_fields": class_fields(class_node(contract, "AlgorithmResultEnvelope")),
        "host_all": collection_length(assigned_value(host, "__all__")),
        "cockpit_public_surface": cockpit_public,
        "cockpit_all": cockpit_all,
        "app_allowed_stdlib": len(app_standard_names),
        "app_contract_symbols": len(app_contract_imports),
        "app_all": collection_length(assigned_value(app, "__all__")),
        "command_labels": collection_length(assigned_value(app, "COMMAND_LABELS")),
    }


CN_DIGITS = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def cn_to_int(text: str) -> int:
    """把 1–99 的中文数词转成整数（覆盖规格文档实际用到的范围）。"""
    text = text.strip()
    if not text:
        raise ValueError("空数词")
    if "十" not in text:
        if len(text) == 1:
            return CN_DIGITS[text]
        raise ValueError(f"不支持的数词：{text}")
    head, _, tail = text.partition("十")
    tens = CN_DIGITS[head] if head else 1
    ones = CN_DIGITS[tail] if tail else 0
    return tens * 10 + ones


def claim_value(rule: Rule, text: str) -> int:
    if rule.source_key in FIXED_CLAIMS:
        return FIXED_CLAIMS[rule.source_key]
    match = rule.claim.search(text)
    if not match:
        raise ValueError(f"claim pattern no longer matches: {rule.claim.pattern}")
    groups = [value for value in match.groups() if value]
    if not groups:
        raise ValueError(f"claim has no count: {match.group(0)}")
    first = groups[0]
    # ★ 规格正文常用中文数词（"三个操作"），散文里比阿拉伯数字更自然。
    # 两种都接受 —— 关键是要读到**同一个数量**，不是拘泥写法。
    if first.isdigit():
        return int(first)
    return cn_to_int(first)


def _rules_ast() -> tuple[ast.Tuple, list[str]]:
    """从当前源文件解析 ``RULES``，不依赖模块导入阶段已经构造成功。"""
    path = pathlib.Path(__file__).resolve()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return ast.Tuple(elts=[], ctx=ast.Load()), [f"无法解析 {path.name}：{exc}"]

    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "RULES"
            for target in node.targets
        ):
            if isinstance(node.value, ast.Tuple):
                return node.value, []
            return ast.Tuple(elts=[], ctx=ast.Load()), [
                f"RULES（源文件第 {node.lineno} 行）不是元组字面量"
            ]
    return ast.Tuple(elts=[], ctx=ast.Load()), ["源文件中找不到 RULES 赋值"]


def _string_constant(node: ast.AST, label: str, index: int, errors: list[str]) -> str:
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        errors.append(f"Rule #{index} 的 {label} 不是字符串常量（第 {getattr(node, 'lineno', '?')} 行）")
        return ""
    return node.value


def _stable_locate(locate: str) -> bool:
    """锚点应以反引号代码、INV 编号、章节号或稳定列表标记开头。"""
    return bool(
        locate.startswith("`")
        or locate.startswith("INV-")
        or re.match(r"^#{2,6} \d+(?:\.\d+)* \S", locate)
        or re.match(r"^\d+(?:\.\d+)* [A-Za-z_]", locate)
        or locate.startswith(("- **", "| INV-"))
    )


def _locate_line(rule: Rule, lines: list[str]) -> tuple[int, list[str]]:
    """用锚点唯一定位；行号只校准提示，不参与回退。"""
    if not rule.locate:
        return rule.line_no, []

    found = [i for i, line in enumerate(lines, 1) if rule.locate in line]
    if len(found) != 1:
        return 0, [
            f"{rule.filename} {rule.label}：锚点 {rule.locate!r} "
            f"匹配 {len(found)} 行（{found[:4]}），无法唯一定位"
        ]
    return found[0], []


def _locate_by_shape(rule: Rule, lines: list[str]) -> tuple[int, list[str]]:
    """用「剥掉括注后的稳定部分 + 声明正则」联合定位。

    ★ 背景：某些锚点把**被核对的数字本身**写进了定位串
    （例如 `` `UiCommandKind`（Enum，6 值）``）。那个数字一旦被改错，
    锚点就再也定位不到声明 —— 检查器只能报「无法唯一定位」，
    ★ 而真正的问题（数量不符）反而永远跑不出来。

    ★ 本函数**只用于让数量核对跑得起来**，绝不用于消除锚点错误本身：
    ★ 放宽定位一律在输出里显式标注，锚点仍照旧报错。

    ★ 之所以要**联合** ``claim`` 正则：剥掉括注后 `` `UiCommandKind` ``
    往往在文档里出现多次；只有同时要求该行能匹配「Enum，N 值」这类
    声明形状，才能唯一落到真正的声明行。
    """
    if not rule.locate:
        return 0, []
    head = re.sub(r"（[^）]*）", "", rule.locate)   # 去掉全角括注
    head = re.sub(r"\(.*?\)", "", head)           # 去掉半角括注
    head = re.sub(r"[，,]\s*[^，,]*$", "", head)   # 去掉尾部描述
    head = head.strip()
    if not head or head == rule.locate:
        return 0, []
    # ★ 只接受仍然稳定的定位键（反引号符号 / INV 编号 / 章节号 / 列表标记）
    if not (
        head.startswith("`")
        or head.startswith("INV-")
        or re.match(r"^#{2,6} \d+(?:\.\d+)* \S", head)
        or re.match(r"^\d+(?:\.\d+)* [A-Za-z_]", head)
        or head.startswith(("- **", "| INV-"))
    ):
        return 0, []
    found = [
        i
        for i, line in enumerate(lines, 1)
        if head in line and rule.claim.search(line)
    ]
    if len(found) != 1:
        return 0, []
    return found[0], []


def _is_anchor_error(message: str) -> bool:
    """区分「定位/漂移」与「结构性」异常。

    结构性异常（RULES 解析不出、不是 ``Rule(...)`` 调用、参数非法、目标文件读不到）
    会让下面的数量核对**失去运行基础**，必须硬停；
    定位/漂移只影响「找到哪一行」，**不影响「能不能核对数量」** ——
    ★ 所以它绝不能阻断数量核对，否则真实数量错误会被定位失败的措辞淹没。
    """
    if "无法读取目标文档" in message:
        return False
    return "锚点" in message or "行号已漂移" in message


def _relaxed_locate(locate: str) -> str:
    """★ 已由 _locate_by_shape 取代（联合 claim 正则才能唯一定位）。保留占位以防误引用。"""
    raise NotImplementedError("SUPERSEDED: 请改用 _locate_by_shape")


def self_check() -> tuple[int, list[str], list[str]]:
    """用 AST 审计规则结构、source_key 和锚点唯一性。"""
    rules_node, errors = _rules_ast()
    elements = rules_node.elts
    if not elements:
        errors.append("RULES 元组没有元素")
        return 0, errors, []

    try:
        count_keys = set(build_counts())
    except (OSError, SyntaxError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"无法取得 build_counts() 的事实键：{type(exc).__name__}: {exc}")
        count_keys = set()

    seen: dict[tuple[str, ...], list[int]] = defaultdict(list)
    warnings: list[str] = []
    for index, element in enumerate(elements, 1):
        if not (
            isinstance(element, ast.Call)
            and isinstance(element.func, ast.Name)
            and element.func.id == "Rule"
        ):
            errors.append(f"Rule #{index}（第 {getattr(element, 'lineno', '?')} 行）不是 Rule(...) 调用")
            continue
        if len(element.args) not in (5, 6) or element.keywords:
            errors.append(
                f"Rule #{index} 参数非法：位置参数 {len(element.args)} 个、"
                f"关键字参数 {len(element.keywords)} 个（只允许 5 或 6 个位置参数）"
            )
            continue

        filename = _string_constant(element.args[0], "filename", index, errors)
        label_value = _string_constant(element.args[2], "label", index, errors)
        source_key = _string_constant(element.args[4], "source_key", index, errors)
        line_node = element.args[1]
        line_no = line_node.value if isinstance(line_node, ast.Constant) else None
        claim = element.args[3]
        locate = element.args[5] if len(element.args) == 6 else ast.Constant(value="")
        claim_is_compile = (
            isinstance(claim, ast.Call)
            and isinstance(claim.func, ast.Attribute)
            and isinstance(claim.func.value, ast.Name)
            and claim.func.value.id == "re"
            and claim.func.attr == "compile"
            and len(claim.args) == 1
            and isinstance(claim.args[0], ast.Constant)
            and isinstance(claim.args[0].value, str)
        )
        if not claim_is_compile:
            errors.append(f"Rule #{index} 的 claim 不是 re.compile(<字符串字面量>)")
        if not isinstance(line_node, ast.Constant) or not isinstance(line_no, int) or isinstance(line_no, bool):
            errors.append(f"Rule #{index} 的 line_no 不是整数字面量")
        elif claim_is_compile and isinstance(locate, ast.Constant):
            # 同一坐标可承载两个互补的正则；这里只抓整条声明被复制的情况。
            signature = (
                filename,
                line_no,
                source_key,
                label_value,
                claim.args[0].value,
                locate.value,
            )
            seen[signature].append(index)

        if len(element.args) == 6:
            locate = _string_constant(element.args[5], "locate", index, errors)
            if locate and not _stable_locate(locate):
                warnings.append(
                    f"Rule #{index} 的 locate 看起来不像稳定标识符（建议以反引号、"
                    f"INV-、章节号或稳定列表标记开头）：{locate!r}"
                )
            if locate and not isinstance(element.args[0], ast.Constant):
                continue
            if locate and isinstance(element.args[0], ast.Constant):
                try:
                    lines = (BUILD / element.args[0].value).read_text(encoding="utf-8").splitlines()
                except OSError as exc:
                    errors.append(f"Rule #{index} 无法读取目标文档：{exc}")
                else:
                    found = [i for i, line in enumerate(lines, 1) if locate in line]
                    if len(found) != 1:
                        errors.append(
                            f"Rule #{index}（{element.args[0].value} {element.args[2].value}）："
                            f"锚点 {locate!r} 匹配 {len(found)} 行"
                            f"（{found[:4]}），无法唯一定位"
                        )
                    elif (
                        isinstance(line_node, ast.Constant)
                        and isinstance(line_no, int)
                        and found[0] != line_no
                    ):
                        errors.append(
                            f"Rule #{index}（{element.args[0].value} {element.args[2].value}）："
                            f"行号已漂移，记录 {line_no}，锚点实际位于 {found[0]}"
                        )
        elif element.args[5:]:
            errors.append(f"Rule #{index} 的 locate 未提供，依赖默认值可接受，但不可附带多余参数")

        if source_key and count_keys and source_key not in count_keys:
            errors.append(f"Rule #{index} 的 source_key {source_key!r} 不存在于 build_counts() 返回键")

    for signature, indexes in seen.items():
        if len(indexes) > 1:
            filename, line_no, source_key, *_ = signature
            errors.append(
                f"重复 Rule：{filename}:{line_no} / {source_key!r}，"
                f"完整声明对应 Rule {indexes}"
            )

    return len(elements), errors, warnings


def main() -> int:
    if sys.argv[1:] == ["--self-check"]:
        count, errors, warnings = self_check()
        if errors:
            print(f"❌ Rule 自检失败：{count} 条 Rule，{len(errors)} 个异常")
            for error in errors:
                print(f"  ❌ {error}")
            for warning in warnings:
                print(f"  ⚠️ {warning}")
            return 1
        anchored = sum(len(element.args) == 6 for element in _rules_ast()[0].elts)
        print(
            f"✅ {count} 条 Rule 结构合法，0 个异常"
            f"（{anchored} 条锚定全部唯一，{count - anchored} 条未锚定）"
        )
        for warning in warnings:
            print(f"  ⚠️ {warning}")
        return 0
    if sys.argv[1:]:
        print(f"❌ 未知参数：{' '.join(sys.argv[1:])}；仅支持 --self-check")
        return 2

    rule_count, rule_errors, rule_warnings = self_check()
    # ★ 关键分流：结构性异常让数量核对失去运行基础，必须硬停；
    # ★ 定位/漂移只影响「找到哪一行」，**不能阻断数量核对**。
    # ★ 否则「锚点匹配 0 行」会掩盖真正的数量错误 —— 那是「检查没报到真正的问题」。
    anchor_errors = [error for error in rule_errors if _is_anchor_error(error)]
    structural_errors = [error for error in rule_errors if not _is_anchor_error(error)]

    if structural_errors:
        print(f"❌ Rule 自检结构性失败：{rule_count} 条 Rule，{len(structural_errors)} 个异常")
        for error in structural_errors:
            print(f"  ❌ {error}")
        for warning in rule_warnings:
            print(f"  ⚠️ {warning}")
        return 1

    if anchor_errors:
        print(
            f"⚠️ Rule 锚点待处理：{rule_count} 条 Rule，{len(anchor_errors)} 条锚点/漂移异常"
            f"（★ 不阻断下方数量核对 —— 定位问题不应掩盖数量错误）"
        )
        for error in anchor_errors:
            print(f"  ⚠️ {error}")

    print("㉑ BI 数量声明一致性（文档声明 vs AST / 枚举 / 常量）")
    problems: list[str] = []
    drifted: list[str] = []
    skipped: list[str] = []
    # ★ 锚点失效但用稳定部分完成数量核对的规则（锚点本身仍需修正）
    anchored_by_relaxation: list[str] = []
    # ★ 锚点彻底失效、**本轮未能核对数量**的规则（绝不能计入「通过」）
    unable_to_check: list[str] = []
    checked = 0
    unanchored = 0

    try:
        actual = build_counts()
    except (OSError, SyntaxError, KeyError, TypeError, ValueError) as exc:
        print(f"  ❌ 无法建立结构事实：{type(exc).__name__}: {exc}")
        return 1

    for rule in RULES:
        path = BUILD / rule.filename
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            problems.append(f"  ❌ {rule.filename} 无法读取：{exc}")
            continue
        # ★ 锚点必须唯一定位；行号只是漂移提示，绝不作为错误锚点的回退。
        located_line, locate_errors = _locate_line(rule, lines)
        if locate_errors:
            # ★ 锚点里写死了被核对的数字时，数字一改锚点就失效。
            # ★ 此时用「剥掉括注后的稳定部分 + 声明正则」再定位一次，
            # ★ 让数量核对仍能跑起来 —— 目的是【暴露真实数量错误】，
            # ★ 不是消除锚点错误（后者照旧照报）。
            shape_line, _ = _locate_by_shape(rule, lines)
            if shape_line:
                anchored_by_relaxation.append(
                    f"  ⚠️ {rule.filename}:{rule.line_no} {rule.label}："
                    f"锚点 {rule.locate!r} 失效，已按「稳定部分 + 声明形状」"
                    f"定位到第 {shape_line} 行核对数量（★ 锚点本身仍需修正）"
                )
                located_line = shape_line
            else:
                problems.extend(f"  ❌ {error}" for error in locate_errors)
                unable_to_check.append(f"{rule.label}（{rule.source_key}）")
                continue
        if rule.locate and located_line != rule.line_no:
            drifted.append(
                f"  ⚠️ {rule.filename}:{rule.line_no} {rule.label}："
                f"行号已漂移，锚点实际位于 {located_line}（已用锚点行判定）"
            )
        if not rule.locate:
            unanchored += 1
            if not 0 < located_line <= len(lines):
                problems.append(
                    f"  ❌ {rule.filename}:{rule.line_no} {rule.label}："
                    f"行号越界且未锚定"
                )
                continue
        text = lines[located_line - 1]
        try:
            claimed = claim_value(rule, text)
            expected = actual[rule.source_key]
        except (ValueError, KeyError) as exc:
            problems.append(f"  ❌ {rule.filename}:{rule.line_no} {rule.label}：{exc}")
            continue
        checked += 1
        if claimed != expected:
            problems.append(
                f"  ❌ {rule.filename}:{rule.line_no} {rule.label}："
                f"声明 {claimed}，实际 {expected}（来源 {rule.source_key}）\n"
                f"       {text.strip()[:140]}"
            )

    covered = {(rule.filename, rule.line_no) for rule in RULES}
    for md in sorted(BUILD.glob("FILE-*-v1.md")):
        in_fence = False
        lines = md.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence or any(marker in line for marker in SKIP_MARKERS):
                continue
            match = DISCOVERY.search(line)
            if match and (md.name, i) not in covered:
                label = match.group(0).strip()
                skipped.append(f"  ⏭ {md.name}:{i} {label} —— 无显式结构映射，不能机械判定")

    if anchored_by_relaxation:
        print("\n锚点失效但已完成数量核对（★ 锚点本身仍需修正）")
        for item in anchored_by_relaxation:
            print(item)

    if drifted:
        print("\n锚定行号漂移（已用锚点行判定）")
        for item in drifted:
            print(item)

    if skipped:
        print("\nSKIPPED（无显式结构映射，不猜数）")
        skipped_by_file: dict[str, list[str]] = {}
        for item in skipped:
            filename = item.split()[1].split(":", 1)[0]
            skipped_by_file.setdefault(filename, []).append(item)
        for filename in sorted(skipped_by_file):
            print(f"  {filename}：{len(skipped_by_file[filename])} 处")
            for item in skipped_by_file[filename]:
                print(item)

    # ★ 「未能核对」绝不能被当成「通过」——它既不是一致，也不是不一致，是【没测到】。
    if unable_to_check:
        print()
        for item in unable_to_check:
            print(f"  ❌ 未能核对数量（锚点彻底失效）：{item}")
        print(
            f"\n  ❌ {len(unable_to_check) + len(problems)} 处问题"
            f"（核对 {checked} 条可判定声明；未能核对 {len(unable_to_check)} 条；"
            f"SKIPPED {len(skipped)} 处；未锚定 {unanchored} 条；行号漂移 {len(drifted)} 条）"
        )
        return 1
    if problems:
        print()
        for problem in problems:
            print(problem)
        print(f"\n  ❌ {len(problems)} 处问题（核对 {checked} 条可判定声明；SKIPPED {len(skipped)} 处；未锚定 {unanchored} 条；行号漂移 {len(drifted)} 条）")
        return 1
    print(f"\n  ✅ 核对了 {checked} 条可机械判定数量声明，全部一致；SKIPPED {len(skipped)} 处；未锚定 {unanchored} 条；行号漂移 {len(drifted)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
