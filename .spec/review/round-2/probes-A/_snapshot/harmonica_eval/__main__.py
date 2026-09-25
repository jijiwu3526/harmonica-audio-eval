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
from pathlib import Path
from typing import Sequence

from .contract import UiScalar, UiSeries, UiView


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
    raise NotImplementedError("SHELL: FILE-002 待注入实现")


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
    raise NotImplementedError("SHELL: FILE-002 待注入实现")


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
    raise NotImplementedError("SHELL: FILE-002 待注入实现")


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
    raise NotImplementedError("SHELL: FILE-002 待注入实现")


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
    raise NotImplementedError("SHELL: FILE-002 待注入实现")


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
    raise NotImplementedError("SHELL: FILE-002 待注入实现")


def describe_inputs(reference_uri: str, practice_uri: str) -> str:
    """生成两段输入的确认行，用于**落盘产物内**的可复现记录。

    参数：
        reference_uri / practice_uri —— 两段输入路径（原样，不解析、不打开）。

    契约：
        - 只记录路径字符串；**不读文件、不探测时长、不解析格式**（那是 C2 的 ingest）
        - 不写入音频内容本身（.gitignore：音频不进库）

    返回：一行文本（str）。
    """
    raise NotImplementedError("SHELL: FILE-002 待注入实现")


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

