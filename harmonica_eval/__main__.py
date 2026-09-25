'''
FILE-ID:      FILE-002
COMPONENT:    COMP-PKG（包入口，本身不是组件）
SPEC:         SPEC.md@v2.1 §3（输出物）· PLAN.md@v2 §四/§六 · COMPONENTS.md@v2 §5 不变量 F
ROLE:
    无头命令行入口：两段音频 → 跑完整流程（建数据面 → 跑算法）→ 落 metrics.json 与数值报告。

INTENT:
    不变量 F 的验证载体。C4 缺席时全流程仍须跑通；因此**无头链路必须是可独立执行的**，
    不能挂在界面上。它是 PLAN.md §八 阶段 D「首次端到端出指标」那个交付物的入口。

MUST:
    - 用法：python3 -m harmonica_eval --reference 原曲.wav --practice 练习曲.wav
      [--out metrics.json]（缺省落点 data/out/metrics.json，见 DEFAULT_OUT_DIR）
    - 落两份产物：--out 指定的 metrics.json，以及与其同目录的 report.md（数值陈述）
    - 只消费 contract.UiView / UiScalar / UiSeries 作为结果视图（C1 的投影）
    - 全部失败走显式退出码；不静默降级、不伪造结果
    - 每一条曲线都带 timeline_basis，指标必须能被回答「它是什么、怎么算的、单位是什么」

MUST NOT:
    - import cockpit（或任何 UI 依赖）—— 这正是不变量 F 的判定线
    - 做 DSP、对齐、特征计算或任何数值处理（那是 C2/C3 的职责，本文件只做 argv、装配与落盘）
    - 重新计算或改写 C1 给的数值
    - 生成教学结论 / 自然语言反馈（SPEC §1：只到数值层）

INPUT:
    sys.argv（两段音频路径 + 输出路径）· C1 发布的会话状态与数值结果

OUTPUT:
    metrics.json 文件 · report.md 文件 · 进程退出码 int

BUILD-INSTRUCTION:
    .spec/build/FILE-002-v1.md
'''

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .contract import (
    ContractViolation,
    HarmonicaError,
    ErrorCode,
    SessionState,
    UiScalar,
    UiSeries,
    UiView,
)


# ═════════════════════════════════════════════════════════════════════
# 冻结的默认值
# ═════════════════════════════════════════════════════════════════════

DEFAULT_OUT_DIR = "data/out"
"""缺省输出目录。依据 SPEC.md §3：「单次分析产出（data/out/）」；目录不进 git。"""

DEFAULT_METRICS_FILENAME = "metrics.json"
"""--out 的缺省文件名，落在 DEFAULT_OUT_DIR 之下。"""

REPORT_FILENAME = "report.md"
"""数值报告的文件名。与 metrics.json 同目录（SPEC.md §3：单次分析产出两份）。"""

EXIT_OK = 0
"""全流程成功。"""

EXIT_FAILED = 1
"""运行期失败（输入不可读 / 构建失败 / 算法全部失败）。"""

EXIT_USAGE = 2
"""命令行用法错误（与 argparse 的约定一致，便于脚本区分「我调错了」与「它跑挂了」）。"""


# ═════════════════════════════════════════════════════════════════════
# 一 · 命令行入口
# ═════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器：--reference / --practice / --out。

    契约：
        - --reference 与 --practice 必填，语义为「参考演奏」与「练习演奏」（不可互换：
          节奏类指标的方向、bias 的正负号都取决于谁是参考）
        - --out 选填，缺省为 DEFAULT_METRICS_FILENAME
        - **接受 .wav 作为用法示意**；音频格式的实际解析归 C2 ingest，本文件不校验也不解码

    返回：argparse.ArgumentParser 实例。用法错误由 argparse 自行报错并以 EXIT_USAGE 退出。
    """
    parser = argparse.ArgumentParser(
        prog="python3 -m harmonica_eval",
        description=(
            "口琴双音频对比分析：给定参考演奏与练习演奏，"
            "输出客观数值指标（metrics.json + report.md）。"
        ),
        epilog=(
            "示例：\n"
            "  python3 -m harmonica_eval \\\n"
            "      --reference 原曲.wav --practice 练习曲.wav\n"
            "\n"
            "本入口是无头通路：界面缺席时全流程仍须跑通（不变量 F）。"
        ),
    )
    parser.add_argument(
        "--reference",
        required=True,
        metavar="原曲.wav",
        help="参考演奏路径（不可与 --practice 互换：节奏指标的方向取决于谁是参考）",
    )
    parser.add_argument(
        "--practice",
        required=True,
        metavar="练习曲.wav",
        help="练习演奏路径",
    )
    parser.add_argument(
        "--out",
        default=None,
        metavar="metrics.json",
        help=(
            "metrics.json 的落点。缺省为 "
            f"{DEFAULT_OUT_DIR}/{DEFAULT_METRICS_FILENAME}；"
            "其父目录同时决定 report.md 的位置"
        ),
    )
    return parser


def run_headless(
    reference_uri: str,
    practice_uri: str,
    out_path: Path,
) -> UiView:
    """无头跑完整流程，返回 C1 的最终投影视图。

    流程（PLAN.md §六）：登记两段输入 → 构建数据面（预生成 + Seal）→ 触发算法 → 取视图。
    本函数**不参与任何一步的计算**，只按契约调用 C1 并收敛状态。

    参数：
        reference_uri —— 参考演奏路径。
        practice_uri  —— 练习演奏路径。
        out_path      —— metrics.json 的落点（其父目录决定 report.md 的位置）。

    契约：
        - 返回构建成功后的 UiView（含 scalars / series / state）；
          典型失败态（state == FAILED）也**返回视图**，由调用方决定退出码。
        - 只允许在 state == DATA_READY 之后触发算法（契约硬 gate）。
        - 不捕获算法级失败：C1 负责归一化为 error_code，本函数如实转述。

    异常：
        OSError / ValueError —— 输出路径不可写等**进程级**失败，直接抛，不吞。
    """
    # ★ 本文件 MUST NOT「做 DSP、对齐、特征计算或任何数值处理」，
    # ★ 也 MUST NOT import core/host 内部去绕过 C1 —— 那是 C1 的门面职责。
    # ★ 唯一合法的装配入口是 C1 的包出口（launch_cockpit 同级的那一支）。
    from .host.app import build_default_app  # 局部导入：--help 路径不碰它

    app = build_default_app()
    session_id = app.create_session("v1")
    app.set_reference(session_id, reference_uri)
    app.set_practice(session_id, practice_uri)
    app.build_surface(session_id)
    app.run_algorithms(session_id)
    return app.build_view(session_id)


def render_report_markdown(
    view: UiView, reference_uri: str, practice_uri: str
) -> str:
    """把投影渲染成人类可读的**数值**报告文本（写进 report.md 的内容）。

    参数：
        view          —— C1 的投影，含 state / scalars / series 元信息 / error_*。
        reference_uri —— 本次运行的参考音频路径（原样字符串）。
        practice_uri  —— 本次运行的练习音频路径（原样字符串）。
                         两者由调用方 main 传入：投影 UiView 的 8 个字段里
                         **没有**任何字段携带 URI，故路径只能走参数。

    契约：
        - 只陈述数值：每条 UiScalar 输出「label = value unit」，
          有 threshold 时**并列**写出阈值，不判定「合格 / 不合格」
        - 每条 UiSeries 只列元信息（label / unit / timeline_basis / 采样点数），**不铺开数据点**
        - **只做格式化，不重算任何量**；投影里没有的，报告里也不出现
        - 不下教学结论、不生成自然语言反馈（SPEC §1）
        - error_code / error_detail 存在时，如实写出，不美化

    返回：Markdown 文本（str）。
    """
    lines: list[str] = ["# 口琴双音频对比 · 数值报告", ""]
    lines.append(describe_inputs(reference_uri, practice_uri))
    lines.append(f"会话状态：{view.state.name}")
    lines.append("")

    # error_code / error_detail 存在时如实写出，不美化（SPEC §1 只到数值层）。
    if view.error_code is not None:
        lines.append(f"错误码：{view.error_code}")
        if view.error_detail:
            lines.append(f"错误详情：{view.error_detail}")
        lines.append("")

    lines.append("## 标量指标")
    if not view.scalars:
        lines.append("（本次没有标量指标）")
    for scalar in view.scalars:
        # ★ 只陈述数值；有 threshold 时并列写出，但不判定「合格 / 不合格」。
        text = f"- {scalar.label} = {scalar.value}"
        if scalar.unit:
            text += f" {scalar.unit}"
        threshold = getattr(scalar, "threshold", None)
        if threshold is not None:
            text += f"（阈值 {threshold}）"
        lines.append(text)

    lines.append("")
    lines.append("## 曲线")
    if not view.series:
        lines.append("（本次没有曲线）")
    for curve in view.series:
        # ★ 每条曲线都必须写明轴语义 —— 否则图会被误读。
        lines.append(f"- {summarize_series([curve])}")

    return "\n".join(lines) + "\n"


def write_metrics_json(
    view: UiView, out_path: Path, reference_uri: str, practice_uri: str
) -> None:
    """把投影写成 metrics.json。

    参数：
        view          —— C1 的投影：会话状态 + 标量指标列表。
        out_path      —— 目标文件路径；父目录不存在时由实现创建。
        reference_uri —— 本次运行的参考音频路径（原样字符串），写入 inputs.reference。
        practice_uri  —— 本次运行的练习音频路径（原样字符串），写入 inputs.practice。
                         两者由调用方 main 传入：UiView 不携带 URI，
                         且本文件禁止 import core.*，无法另开通道去取。

    契约：
        - 只序列化投影里已有的量；键名与 contract.UiScalar.key / UiSeries.key 一致
        - **不重算、不补齐、不推断**缺失字段
        - 时间类数值一律带单位（秒）；不确定的量宁可不写，不写猜测值
        - 写失败（无权限 / 路径不可写）抛 OSError，由调用方决定退出码

    返回：None（副作用是落盘）。
    """
    # ★ 键名与 contract.UiScalar.key / UiSeries.key 一致；只序列化投影里已有的量。
    # ★ 不重算、不补齐、不推断缺失字段；顶层结构是 FILE-002 冻结的五项。
    payload: dict[str, object] = {
        "schema_version": "CONTRACT-UI-v2",
        "inputs": {"reference": reference_uri, "practice": practice_uri},
        "state": view.state.name,
        # ★★ 2026-09-25 修正（真实现缺陷）：FILE-002:499 冻结
        #   「失败也必须落两份产物（可读报告里如实写 error_code）」，
        #   而本 payload 此前【完全不写 error_code / error_detail】——
        #   失败信封落盘后，排查线索却不在产物里。判据 FILE-002 脚本8 正是
        #   断言 metrics.json 的 error_code 非空且与 report.md 一致。
        # ★ 只序列化投影里已有的量：两者皆 None 时不写这两个键（成功路径不变）。
        **(
            {}
            if view.error_code is None and view.error_detail is None
            else {
                "error_code": getattr(view.error_code, "value", view.error_code),
                "error_detail": view.error_detail,
            }
        ),
        "scalars": [
            {
                "key": scalar.key,
                "label": scalar.label,
                "value": scalar.value,
                "unit": scalar.unit,
            }
            for scalar in view.scalars
        ],
        # ★ 逐音序列走已冻结的 series 字段（已裁定：不新增顶层指标）。
        # ★★ 序列本体必须落盘：只写 n_points 会让「中位数掩盖离群音」无从判断
        #    （median=300 分不清「1 个音错 300」与「所有音错 300」）。
        # ★★ numpy 标量 json 不可序列化 → 一律转 Python 原生 float。
        "series": [
            {
                "key": curve.key,
                "label": curve.label,
                "unit": curve.unit,
                "timeline_basis": curve.timeline_basis.name,
                "source_port": curve.source_port,
                "n_points": len(curve.values),
                "t": [float(x) for x in curve.t],
                "values": [float(x) for x in curve.values],
            }
            for curve in view.series
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """进程入口：解析参数 → run_headless → 双落盘 → 退出码。

    参数：
        argv —— 参数序列（**不含程序名**）；None 表示取 sys.argv[1:]。
                显式传入是为了让同一入口能被测试或工具复用，而不必改 sys.argv。

    契约：
        - 成功 → EXIT_OK；运行期失败 → EXIT_FAILED；用法错误 → EXIT_USAGE
        - 无论成功失败，**不打印堆栈到 stdout**（可读报告走 report.md）
        - 绝不 import cockpit：本入口是 C4 缺席时的唯一通路（不变量 F）

    返回：退出码 int。
    """
    argv = list(sys.argv[1:] if argv is None else argv)

    # ★ --help / 用法错误全部由 argparse 自身处理，并在【任何业务调用前】退出。
    # ★ 这条顺序是硬要求：--help 不依赖算法实体实现（盲审 BLOCK-1）。
    parser = build_parser()
    args = parser.parse_args(argv)

    out_path = (
        Path(args.out)
        if args.out is not None
        else Path(DEFAULT_OUT_DIR) / DEFAULT_METRICS_FILENAME
    )

    # ★★ 用户输入错误的可读呈现（与下方「未产出指标」同构）★★
    #
    # ★ 验收实测：--reference /nonexistent.wav 时，异常从 host/app.py 冒泡到
    #   runpy，用户看到的是整段 traceback —— 泄漏内部路径与调用栈，
    #   而有用的信息（"输入路径不存在或不是普通文件"）被埋在最后一行。
    #
    # ★ 判据：★ 一个普通用户给了个错路径，不该看到 Python 调用栈。
    #
    # ★★ 但【只】收敛【受控失败】，绝不 catch 掉所有异常 ★★
    #   · HarmonicaError → contract.py:1046 自述「全部受控失败的基类。
    #     携带结构化上下文，便于 C1 归一化上报」
    #     → 契约层已判定这是【可预期的协议/数据面失败】，用户可修正，给单行诊断
    #   · 其余任何异常（AttributeError / KeyError / TypeError …）
    #     → 那是【内部缺陷】，traceback 是定位它的唯一线索，必须原样冒泡
    # ★ 判据：宁可看到 traceback，也不要看不到真缺陷的位置。
    #
    # ★★ 2026-09-25 修正（真实现缺陷，非判据过期）★★
    #   原先捕获 `ContractViolation`，但实测 10 秒音频（规格下限 45s）
    #   抛的是 `CoreBuildError` —— 二者是【兄弟类】，共同基类是
    #   `HarmonicaError`：`issubclass(CoreBuildError, ContractViolation)` 为 False。
    #   ★ 故数据面失败一路冒泡到 runpy，用户看到 33 行 Traceback，
    #     而有用的「时长 10.000s 短于下限 45.0s」被埋在末行。
    #   ★ 改为捕获其【声明的基类】而非猜某个子类，才与 docstring 的意图一致。
    try:
        view = run_headless(args.reference, args.practice, out_path)
    except HarmonicaError as err:
        # ★★ 2026-09-25 修正（真实现缺陷，非判据过期）：
        #   FILE-002:499 冻结「失败时照样走完第 4、5 步：失败也必须落两份产物
        #   （可读报告里如实写 error_code）」。而本分支原先直接 return，
        #   跳过了下面的双落盘 —— 实测 `--reference missing.wav` 时
        #   rc=1 但 /tmp/…/metrics.json 与 report.md 都不存在。
        #   ★ 失败也是一次完整的观测：那两份产物里有 error_code / error_detail，
        #   ★ 是排查线索；不写等于让调用方只剩一个裸退出码。
        # ★ 错误码【取异常自带的】，不硬编码 —— 否则「音频太短」会被
        #   如实写进 metrics.json 成 INPUT_UNREADABLE（读不了），
        #   而真相是 INPUT_TOO_SHORT（太短）：调用方据此给出不同修复动作。
        failed_view = UiView(
            session_id="-",
            state=SessionState.FAILED,
            scalars=(),
            series=(),
            error_code=err.code,
            error_detail=str(err),
            note="受控失败，未进入或未完成数据面",
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_metrics_json(failed_view, out_path, args.reference, args.practice)
        (out_path.parent / REPORT_FILENAME).write_text(
            render_report_markdown(failed_view, args.reference, args.practice),
            encoding="utf-8",
        )
        # ★ 提示语按错误码给【对应的修复动作】—— 统一说「检查路径」
        #   会让「音频太短」的用户去检查一个完全正常的路径。
        _hint = {
            ErrorCode.INPUT_TOO_SHORT: (
                "音频短于规格下限（见 docs/指标解读.md）"
                "，请改用更长的录音"
            ),
            ErrorCode.INPUT_SILENT: "音频为静音（无可测信号），请检查录音音量",
        }.get(
            err.code,
            "请检查两个音频路径是否为存在的普通 .wav 文件",
        )
        print(
            f"分析未完成，已按失败退出（error_code={err.code.value}）：{err}；{_hint}",
            file=sys.stderr,
        )
        return EXIT_FAILED

    # 本函数不参与任何一步的计算：只按契约调用 C1 并收敛状态。
    # ★ 失败态（state == FAILED）也返回视图，由本函数决定退出码 —— 如实转述，不美化。

    # 双落盘。写失败（OSError）在这里冒泡为进程级失败，不吞。
    write_metrics_json(view, out_path, args.reference, args.practice)
    report_path = out_path.parent / REPORT_FILENAME
    report_path.write_text(
        render_report_markdown(view, args.reference, args.practice),
        encoding="utf-8",
    )

    # ★★ 退出码判据：成功必须「真的产出了指标」★★
    #
    # ★ 这条判据是【假绿治理的核心】。此前只看 state == "DATA_READY"，
    # ★ 而 DATA_READY 的语义是「数据面就绪」—— 算法跑没跑、跑成功没成功，
    # ★ 它一概不反映。于是「三个算法全部 INCOMPATIBLE、指标为空」
    # ★ 也会返回 EXIT_OK，产物照样落盘，从外部完全看不出来
    # ★ （SHELL-STANDARD §七「假绿」的典型形态：命令成功、产物存在、内容是空的）。
    #
    # ★ 判据（两项都要满足）：
    #   1. scalars 或 series 至少有一项非空 —— 以【实际产出】为准，而非状态名。
    #      理由：SessionState 只有 CREATED/INPUT_READY/BUILDING/DATA_READY/FAILED/CLOSED，
    #      ★ 没有「算法已产出」这个独立态 —— 数据面就绪与算法完成共用 DATA_READY。
    #      ★ 所以拿 state 当成功判据在语义上就站不住，必须改用实际产出。
    #   2. view.error_code 为 None —— 有错误码时即便有部分指标也不算成功
    #
    # ★ 失败时仍落盘产物：那里面有 error_code / error_detail，是排查线索，
    # ★ 写出来比什么都不写有用。
    if view.error_code is None and (view.scalars or view.series):
        return EXIT_OK

    # ★ 走到这里说明「没算出来」。把原因写进 stderr ——
    # ★ ★ 绝不静默，否则调用方只看到 rc != 0 却不知为何。
    reasons: list[str] = [f"state={view.state.name}"]
    if not view.scalars and not view.series:
        reasons.append("scalars 与 series 均为空（未产出任何指标）")
    if view.error_code is not None:
        reasons.append(f"error_code={view.error_code}")
    if view.error_detail:
        reasons.append(f"error_detail={view.error_detail}")
    print("未产出指标，已按失败退出：" + "；".join(reasons), file=sys.stderr)
    return EXIT_FAILED


# ═════════════════════════════════════════════════════════════════════
# 二 · C4 缺席时的最小视图（投影契约的自足性检验）
# ═════════════════════════════════════════════════════════════════════

def summarize_series(series: Sequence[UiSeries]) -> str:
    """给一条曲线生成一行轴语义说明，用于报告与终端输出。

    参数：
        series —— C1 下采样后的曲线列表（每条含 unit 与 timeline_basis）。

    契约：
        - **必须写明 timeline_basis**：REFERENCE = 保留源时间（抢拍拖拍可见）；
          WARPED = 时间归一化（抢拍拖拍已被抹掉）。轴的含义不标出来，图就会被误读。
        - 只陈述 t 轴单位（秒）与点数，不重新采样、不统计 values

    返回：一行文本（str）。
    """
    if not series:
        return "（无曲线）"
    parts: list[str] = []
    for curve in series:
        basis = getattr(curve.timeline_basis, "name", str(curve.timeline_basis))
        # ★ 轴的含义必须标出来：REFERENCE 保留源时间（抢拍拖拍可见），
        # ★ WARPED 是时间归一化（抢拍拖拍已被抹掉）。不标就会被误读。
        meaning = {
            "REFERENCE": "保留源时间（抢拍拖拍可见）",
            "WARPED": "时间归一化（抢拍拖拍已被抹掉）",
        }.get(basis, "未标注")
        unit = curve.unit or ""
        parts.append(
            f"{curve.label}：{len(curve.values)} 点，t 轴单位秒，"
            f"轴语义 {basis}（{meaning}）"
            + (f"，数值单位 {unit}" if unit else "")
        )
    return "；".join(parts)


def describe_inputs(reference_uri: str, practice_uri: str) -> str:
    """生成两段输入的确认行，用于**落盘产物内**的可复现记录。

    参数：
        reference_uri / practice_uri —— 两段输入路径（原样，不解析、不打开）。

    契约：
        - 只记录路径字符串；**不读文件、不探测时长、不解析格式**（那是 C2 的 ingest）
        - 不写入音频内容本身（.gitignore：音频不进库）

    返回：一行文本（str）。
    """
    # ★ 只记录路径字符串；不读文件、不探测时长、不解析格式（那是 C2 的 ingest）。
    return f"输入：参考 = {reference_uri}；练习 = {practice_uri}"


__all__ = [
    "DEFAULT_OUT_DIR",
    "DEFAULT_METRICS_FILENAME",
    "REPORT_FILENAME",
    "EXIT_OK",
    "EXIT_FAILED",
    "EXIT_USAGE",
    "build_parser",
    "run_headless",
    "render_report_markdown",
    "write_metrics_json",
    "main",
    "summarize_series",
    "describe_inputs",
]


# ═════════════════════════════════════════════════════════════════════
# 三 · 进程入口保护
# ═════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    raise SystemExit(main())

