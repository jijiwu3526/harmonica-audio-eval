'''
FILE-ID:      FILE-401
COMPONENT:    COMP-C4
SPEC:         SPEC.md@v2.1 §1（负责人裁定例外）· COMPONENTS.md@v2 §3 COMP-C4 · PLAN.md@v2 §五
ROLE:
    Mac 端开发者调试界面：把 C1 的只读投影画出来，并把 6 种意图下发回 C1。

INTENT:
    把「看一眼数据面长什么样」从「写脚本 + 打印数组」变成可操作的东西，
    同时**不让界面知识渗进内核**：界面只认 contract 里的 UiView / UiCommand，
    因此它可以被整个删掉而不影响 C1/C2/C3（不变量 F）。

MUST:
    - 只依赖 ..contract（UiView / UiScalar / UiSeries / UiCommand / UiCommandKind /
      UiProjectionPort）与 Python 标准库；UI 框架的选择留给实现者
    - 渲染时**不得重新计算任何东西**：投影里没有的，就是不显示的
    - 每条曲线必须读 UiSeries.timeline_basis 并把轴的含义标注在图上
    - 命令只走 UiProjectionPort.submit()，且只发 UiCommandKind 的 6 个成员
    - 只监听本机（LOCAL_BIND_HOST）；退出码只用 EXIT_OK / EXIT_START_FAILED

MUST NOT:
    - import core / algorithms / host 内部（任何形式，含延迟 import 与字符串导入）
    - 直接读数据面 / 读音频文件 / 做 DSP / 解析 payload 语义（D4：不解释算法内部）
    - 持有音频缓冲或持久状态（纯视图：退出即忘，崩溃/断开对会话零影响）
    - 在界面上发明新能力（"重新对齐""换个算法试试"都不行 —— 6 种之外一律不做）
    - 承担验收 / 测试职责（宪章 §36）

INPUT:
    由调用方注入的 UiProjectionPort（包出口 launch_cockpit 是唯一入口）

OUTPUT:
    屏幕上的视图（状态 / 标量 / 曲线 / 进度 / 错误）+ 经 submit() 下发的 UiCommand

BUILD-INSTRUCTION:
    .spec/build/FILE-401-v1.md
'''

from __future__ import annotations

from typing import Sequence

from ..contract import UiCommand, UiCommandKind, UiProjectionPort, UiScalar, UiSeries, UiView


# ═════════════════════════════════════════════════════════════════════
# 冻结的常量
# ═════════════════════════════════════════════════════════════════════

LOCAL_BIND_HOST = "127.0.0.1"
"""**只监听本机回环**。C4 是开发者调试视图，绝不监听公网（COMPONENTS.md §3 security_boundary）。"""

EXIT_OK = 0
"""界面正常关闭。"""

EXIT_START_FAILED = 2
"""界面启动失败（端口被占 / 本机绑定失败 / 投影端口不可用）。不吞、不重试。"""

COMMAND_LABELS: dict[UiCommandKind, str] = {
    UiCommandKind.SET_REFERENCE: "选择参考演奏",
    UiCommandKind.SET_PRACTICE: "选择练习演奏",
    UiCommandKind.BUILD_SURFACE: "构建数据面",
    UiCommandKind.RUN_ALGORITHMS: "运行算法",
    UiCommandKind.CANCEL: "取消",
    UiCommandKind.RESET: "重置会话",
}
"""6 种意图的中文按钮文案。

**刻意逐条穷举 UiCommandKind 的成员**：界面能表达的意图仅此 6 种，
这张表就是「没有第 7 个按钮」的可审查证据（改契约必须同步改这里）。
"""


# ═════════════════════════════════════════════════════════════════════
# 一 · 界面入口（本地）
# ═════════════════════════════════════════════════════════════════════

def run_local_ui(port: UiProjectionPort) -> int:
    """启动本机开发者界面并阻塞至其关闭，返回退出码。

    参数：
        port —— 调用方注入的 UiProjectionPort（C4 不构造它，见包出口 MUST）。

    契约：
        - 绑定恒为 LOCAL_BIND_HOST（本机回环），不监听公网
        - 整个界面状态都在内存里，退出即消失；**不写任何配置文件**
        - 界面存活期间只做两件事：port.snapshot() 取视图、port.submit() 下发意图
        - 投影端口不可用 / 绑定失败 → 返回 EXIT_START_FAILED，不抛堆栈给用户
        - 界面异常退出**不得**影响 C1 的会话：这是 Invariant F 的现场检验

    返回：EXIT_OK 或 EXIT_START_FAILED。
    """
    raise NotImplementedError("SHELL: FILE-401 待注入实现")


# ═════════════════════════════════════════════════════════════════════
# 二 · 视图渲染（只读投影）
# ═════════════════════════════════════════════════════════════════════

def render_status(view: UiView) -> str:
    """渲染会话状态行：state + session_id + note。

    参数：
        view —— C1 的投影。

    契约：
        - 只展示 view.state 与 view.note 的**原文**；不翻译成"进度 3/5"之类的推断
        - C1 只发布 SessionState 的 6 个值；界面不臆造子状态

    返回：一行文本（str）。
    """
    raise NotImplementedError("SHELL: FILE-401 待注入实现")


def render_scalars(scalars: Sequence[UiScalar]) -> str:
    """渲染标量指标区：label / value / unit（有 threshold 时并列写出）。

    参数：
        scalars —— 投影里的标量列表。

    契约：
        - **只陈述数值**：不判定合格与否、不配色成红绿、不下教学结论（SPEC §3）
        - threshold 存在时**并列**展示，让读者自己对照；不存在时不得自行补一个
        - 不合并同类项、不做统计（不重算任何量）

    返回：多行文本（str）。
    """
    raise NotImplementedError("SHELL: FILE-401 待注入实现")


def render_series_plot(series: UiSeries) -> object:
    """渲染一条曲线，并在图上标注它的时间轴含义。

    参数：
        series —— 已下采样的曲线（含 t / values / unit / timeline_basis）。

    契约：
        - **必须**读 series.timeline_basis 并把它标注在图上：
          REFERENCE = 源时间网格（抢拍拖拍可见）；
          WARPED = 归一化网格（抢拍拖拍已被抹掉）。
          轴的含义不标出来，用户会把 warped 轴上的图当成真实时间而误读节奏。
        - 纵轴单位取 series.unit，横轴是秒；两者都不得省略
        - **不重采样、不插值、不平滑**：投影已是最终形状，界面只画不改
        - 不解释曲线的算法来源（D4）；source_port 只作为追溯字段原样展示

    ★ G15 修正（§20 盲审发现）：返回类型第一版标注为 `str`，
    但本 docstring 又说"实现者可返回 SVG / HTML / 前端图表配置"。
    **标注与散文冲突** —— 实现者按标注返回 `str` 是合规的，
    按散文返回图表配置对象也是合规的，而调用方（`build_plots`）
    声明的是 `Sequence[str]`，两种实现里必有一种让调用方拿到非 str。

    修正为 `object`：**故意不指定具体类型**，因为框架选择确实留给实现者，
    契约强制不了。但把"不强制"写成 `str` 是错的 —— 那是**假装**有约束。
    调用方 `build_plots` 相应地也改为 `Sequence[object]`，
    并**不得**对元素做字符串操作（只能原样传递给前端）。
    """
    raise NotImplementedError("SHELL: FILE-401 待注入实现")


def render_progress(view: UiView) -> str:
    """渲染进度指示。

    参数：
        view —— C1 的投影；进度为 view.progress。

    契约：
        - progress 为 None ⇒ 显示"无进度信息"，**不得**自行估算或从 state 推断百分比
        - progress 的取值域由 C1 定义；界面只做显示，不做归一化或截断判断

    返回：一行文本（str）。
    """
    raise NotImplementedError("SHELL: FILE-401 待注入实现")


def render_error(view: UiView) -> str:
    """渲染错误区：error_code + error_detail。

    参数：
        view —— C1 的投影。

    契约：
        - 两者都为 None ⇒ 返回空串（不显示"无错误"占位）
        - 只展示 C1 归一化后的错误码与细节；**不打印堆栈、不推测原因、不给修复建议**
        - 不区分错误归属（哪个组件失败是 C1/C2/C3 的内部语义，界面不解释）

    返回：文本（str），无错误时为空串。
    """
    raise NotImplementedError("SHELL: FILE-401 待注入实现")


def build_plots(view: UiView) -> Sequence[object]:
    """把投影里的全部曲线渲染成一屏可展示的内容。

    参数：
        view —— C1 的投影。

    契约：
        - 每条曲线**逐一**交给 render_series_plot（时间轴标注在单条曲线内完成）
        - series 为空 ⇒ 返回空序列，不报错、不造图
        - 只读：本函数不修改 view，也不触发任何 C1 侧行为
        - ★ G15 修正：元素类型随 render_series_plot 改为 `object`。
          本函数**不得**对元素做字符串操作（拼接/切片/正则），
          只能原样收集后交给前端 —— 元素是什么由实现者的框架决定。

    返回：渲染结果的序列（与 view.series 一一对应、同序）。
    """
    raise NotImplementedError("SHELL: FILE-401 待注入实现")


# ═════════════════════════════════════════════════════════════════════
# 三 · 命令下发（只有 6 种意图）
# ═════════════════════════════════════════════════════════════════════

def build_command(kind: UiCommandKind, payload: dict | None = None) -> UiCommand:
    """把一次点击翻译成唯一一条 UiCommand。

    参数：
        kind    —— 只能取 UiCommandKind 的 6 个成员之一。
        payload —— 可选载荷；仅 SET_REFERENCE / SET_PRACTICE 用得到
                   （取自 solicit_asset_uri 返回的路径字符串），其余成员必须为 None。

    契约：
        - 映射是**恒等**的：界面不新增、不改写、不拆解意图（不发明新能力）
        - 界面不自造业务字段：payload 只装调用方已经拿到的东西（文件路径），不装推断值
        - CANCEL / RESET 等语义由 C1 校验；界面**不预判**状态是否合法，
          拒绝与否则由 C1 决定（界面不做"尽力而为"的补救）

    返回：UiCommand 实例。
    """
    raise NotImplementedError("SHELL: FILE-401 待注入实现")


def solicit_asset_uri(kind: UiCommandKind) -> str | None:
    """弹出本机文件选择框，取一段音频的**路径**。

    参数：
        kind —— 只能是 SET_REFERENCE 或 SET_PRACTICE（其余成员无载荷，调用即错误）。

    契约：
        - **只取路径字符串，不打开、不读取、不解码音频**（读文件是 C1/C2 的职责）
        - 用户取消 ⇒ 返回 None，且**不下发任何命令**（不产生半条意图）
        - 界面不校验文件是否可解码：不可读由 C1/C2 归一化为错误码后回显

    返回：绝对路径字符串；用户取消时为 None。
    """
    raise NotImplementedError("SHELL: FILE-401 待注入实现")


def submit_command(port: UiProjectionPort, command: UiCommand) -> None:
    """把一条意图经**唯一入口**下发。

    参数：
        port    —— C1 注入的 UiProjectionPort。
        command —— 由 build_command 构造的 UiCommand（6 种意图之一）。

    契约：
        - 只调用 port.submit()（唯一写路径）；**不得**直接访问 C1/C2/C3
        - 不在界面侧缓存或重放命令；不实现队列、重试、乐观更新
        - C1 拒绝命令（状态不合法）时，界面如实反映其返回的视图，不伪造已生效
        - 6 种之外无路径：没有自由格式的命令入口（见 COMMAND_LABELS）

    返回：None。
    """
    raise NotImplementedError("SHELL: FILE-401 待注入实现")


__all__ = [
    "LOCAL_BIND_HOST",
    "EXIT_OK",
    "EXIT_START_FAILED",
    "COMMAND_LABELS",
    "run_local_ui",
    "render_status",
    "render_scalars",
    "render_series_plot",
    "render_progress",
    "render_error",
    "build_plots",
    "build_command",
    "solicit_asset_uri",
    "submit_command",
]
