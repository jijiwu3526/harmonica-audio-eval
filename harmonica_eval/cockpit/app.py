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
    - 绑定 LOCAL_BIND_HOST（默认 0.0.0.0，含局域网以便手机访问；本机开发工具，非生产服务）；
      退出码只用 EXIT_OK / EXIT_START_FAILED

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

import html
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Sequence
from urllib.parse import urlparse

from ..contract import (
    HarmonicaError,
    UiCommand,
    UiCommandKind,
    UiProjectionPort,
    UiScalar,
    UiSeries,
    UiView,
)


# ═════════════════════════════════════════════════════════════════════
# 冻结的常量
# ═════════════════════════════════════════════════════════════════════

LOCAL_BIND_HOST = "0.0.0.0"
"""**监听地址**。负责人裁定「直接支持局域网访问，这只是测试，没有安全问题」。

★ 绑 `0.0.0.0` = 监听所有网卡，手机在同一局域网内可直接访问。
★ ★ 但 `0.0.0.0` 是【监听地址】不是【访问地址】——
★ ★ 浏览器不能用它打开页面，故 `run_local_ui` 会另行探测并打印
★ ★   本机回环地址与局域网实际 IP 两个可点击 URL（见 `_lan_ip` 与启动日志）。
★ ★ 想只限本机时，把本常量改回 `"127.0.0.1"` 即可，其余代码不变。
"""

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

# ── §4.0 冻结的模块私有常量（不得进 __all__）─────────────────────────

_HTTP_PORT_DEFAULT = 8721
"""首选监听端口。探测范围 8721–8784（`_HTTP_PORT_MAX_PROBES = 64`）。"""

_HTTP_PORT_MAX_PROBES = 64
"""端口探测上限。"""

_PORT_PROBE_TIMEOUT_SEC = 0.25
"""单个端口的 bind 探测超时（秒）。"""

_HTTP_POLL_INTERVAL_SEC = 0.5
"""轮询线程两次 `snapshot()` 之间的间隔（秒）。"""

_HTTP_MAX_VIEW_BYTES = 1000000
"""POST body 字节上限。"""

_SCALAR_VALUE_DECIMALS = 6
"""`render_scalars` 中 value 的小数位数。"""

_THRESHOLD_DECIMALS = 6
"""`render_scalars` 中 threshold 的小数位数。与 value 一致，禁止两处不同。"""

_PROGRESS_PERCENT_DECIMALS = 1
"""`render_progress` 的百分数小数位数。"""

_NO_PROGRESS_TEXT = "无进度信息"
"""`progress is None` 时的整行文案。"""

_NO_NOTE_TEXT = "（无）"
"""`note` 去空白后为空时的占位。"""

_AXIS_NOTE_REFERENCE = "REFERENCE（源时间网格：以参考演奏时钟为刻度，抢拍拖拍在此可见）"
"""REFERENCE 曲线的轴标注，逐字冻结。"""

_AXIS_NOTE_WARPED = "WARPED（归一化网格：已拉伸到与参考等长，抢拍拖拍已被抹掉）"
"""WARPED 曲线的轴标注，逐字冻结。"""

_AXIS_NOTE_UNKNOWN_FMT = "UNKNOWN（{basis!r}，无法判定轴含义）"
"""其余 timeline_basis 取值的轴标注模板。"""

_SVG_WIDTH = 720
"""SVG 画布宽（像素）。"""

_SVG_HEIGHT = 240
"""SVG 画布高（像素）。"""

_HTML_CONTENT_TYPE = "text/html; charset=utf-8"
"""页面响应的 Content-Type，逐字冻结。"""

_BROWSER_SUPPRESSED = os.environ.get("DSH_NO_BROWSER", "") not in ("", "0")
"""★ 进程启动时【一次性】读 `DSH_NO_BROWSER`；非空且非 "0" 则不拉起系统浏览器。

★ 为什么读环境变量而不给 `run_local_ui` 加参数：
  `FILE-401-v1.md:172` 把签名 `run_local_ui(port) -> int` 逐字冻结，
  加参数会破那条不变量。而 §4.4 第 8 步要求「随后 `webbrowser.open(该 URL)`」，
  在该步前加一个条件判断【不改变默认行为】，也不动签名。

★ 为什么不是 CLI 开关：`FILE-499-v1.md:160` 明文
  「不提供 `--port` / `--host` / `--no-browser` 等任何额外开关」（铁律 4 零噪声），
  且其 §8 判据把 `--no-browser` 列进 banned 集合。
  ★ 环境变量是进程级约定，不新增命令行配置面。
"""

# ── INV-401-8：模块级可变全局【恰两个】────────────────────────────────

_PAGE_LOCK = threading.Lock()
"""保护 `_PAGE` 的普通锁。锁内只读写一个 `str` 引用。"""

_PAGE = ""
"""最近一次渲染的页面。写点只有 `run_local_ui` 首屏与 `_make_handler` 的 POST 响应。"""


# ═════════════════════════════════════════════════════════════════════
# 一 · 界面入口（本地）
# ═════════════════════════════════════════════════════════════════════

def run_local_ui(port: UiProjectionPort) -> int:
    """启动本机开发者界面并阻塞至其关闭，返回退出码。

    参数：
        port —— 调用方注入的 UiProjectionPort（C4 不构造它，见包出口 MUST）。

    契约：
        - 绑定恒为 LOCAL_BIND_HOST（默认 `0.0.0.0` = 监听所有网卡，以便手机等
          局域网设备访问）。★★ 这不是生产服务：进程退出即消失、不写任何持久
          状态、只服务于本机开发调试。★★ 浏览器**不能**用 `0.0.0.0` 访问 ——
          真实地址（`127.0.0.1` 与局域网 IP）由启动横幅打印。
        - 整个界面状态都在内存里，退出即消失；**不写任何配置文件**
        - 界面存活期间只做两件事：port.snapshot() 取视图、port.submit() 下发意图
        - 投影端口不可用 / 绑定失败 → 返回 EXIT_START_FAILED，不抛堆栈给用户
        - 界面异常退出**不得**影响 C1 的会话：这是 Invariant F 的现场检验
        - ★★ `snapshot()` 的成本语义（实测后写明，★ 原规格未规定）★★
          本模块对 `snapshot()` 的调用频率是 0.5 秒一次（`_HTTP_POLL_INTERVAL_SEC`），
          另加首屏一次、每次 POST 响应一次。它**不**知道也不关心 C1 侧 `snapshot()`
          是纯查表还是触发重算 —— 那是 C1 的内部语义，界面无权解释。
          ★ 代价：若 C1 的 `snapshot()` 是重算而非查表，0.5 秒轮询会放大其成本。
          ★ 该问题已上报负责人，**不在本文件解决**（改轮询间隔需先有 C1 侧成本实测）。
        - ★★ 手机端 / 局域网：负责人已裁定「直接支持」★★
          `LOCAL_BIND_HOST` 恒为 `0.0.0.0`（监听所有网卡），启动时探测并打印
          本机回环与局域网实际 IP 两个 URL。手机与本机在同一局域网即可直接打开。
          ★ 零依赖铁律不变：不因「让手机能用」而引入 npm / CDN / 图表库。

    返回：EXIT_OK 或 EXIT_START_FAILED。
    """
    global _PAGE
    server = None
    try:
        # 第 1 步 · 端口形状检查
        assert hasattr(port, "snapshot") and hasattr(port, "submit")

        # 第 2 步 · 选定端口（探测 8721–8784）
        actual_port = _pick_port()
        if actual_port is None:
            raise OSError(f"127.0.0.1 上 {_HTTP_PORT_DEFAULT}–"
                          f"{_HTTP_PORT_DEFAULT + _HTTP_PORT_MAX_PROBES - 1} 全部 bind 失败")

        # 第 3 步 · 建服务器
        server = _make_server(actual_port, port)

        # 第 4 步 · 注册退出信号（只在主线程）
        signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
        signal.signal(signal.SIGINT, _raise_keyboard_interrupt)

        # 第 6 步 · 首屏
        with _PAGE_LOCK:
            _PAGE = _render_page(port)

        # 第 7 步 · 启动轮询线程
        threading.Thread(target=_poll_loop, args=(port,), daemon=True).start()

        # 第 8 步 · 打印可访问 URL 并拉起系统浏览器
        # ★ 监听地址 0.0.0.0 不可直接访问，故打印本机回环 + 局域网实际 IP
        for url in _access_urls(actual_port):
            sys.stderr.write(url + "\n")
        if not _BROWSER_SUPPRESSED:
            try:
                webbrowser.open(f"http://127.0.0.1:{actual_port}/")
            except Exception:
                pass          # 降级路径之一：URL 已在 stderr，有替代路径

        # 第 9 步 · 阻塞
        server.serve_forever()
    except KeyboardInterrupt:
        # 第 10 步 · 正常关闭。不下发 CANCEL / RESET（不变量 F）
        if server is not None:
            server.server_close()
        return EXIT_OK
    except Exception as exc:
        # 第 11 步 · 启动失败：一行 stderr，不写堆栈
        sys.stderr.write(f"界面启动失败：{type(exc).__name__}: {exc}\n")
        if server is not None:
            server.server_close()
        return EXIT_START_FAILED
    return EXIT_OK


def _pick_port() -> int | None:
    """在 8721–8784 上探测第一个可 bind 的端口（§4.4 第 2 步）。

    返回：实际端口号；全部失败时返回 `None`（由调用方归约为启动失败）。
    """
    for candidate in range(_HTTP_PORT_DEFAULT,
                           _HTTP_PORT_DEFAULT + _HTTP_PORT_MAX_PROBES):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.settimeout(_PORT_PROBE_TIMEOUT_SEC)
            probe.bind((LOCAL_BIND_HOST, candidate))
            return candidate
        except OSError:
            continue
        finally:
            probe.close()
    return None


def _make_server(actual_port: int, port: UiProjectionPort) -> ThreadingHTTPServer:
    """建服务器（§4.4 第 3 步）。`port` 由处理器类的闭包捕获。"""
    server = ThreadingHTTPServer((LOCAL_BIND_HOST, actual_port), _make_handler(port))
    server.allow_reuse_address = True
    server.daemon_threads = True
    return server


def _raise_keyboard_interrupt(signum, frame) -> None:
    """信号处理器体只做一件事：把信号翻译成 KeyboardInterrupt。"""
    raise KeyboardInterrupt


def _lan_ip() -> str | None:
    """探测本机在局域网中的实际 IP（★ 不发包，只让内核选路）。

    ★ 监听地址 `0.0.0.0` 只是「收下所有网卡」，不能直接用浏览器打开，
    ★ 所以必须另探一个真实地址。探测失败（无网卡 / 无路由）返回 `None`。
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))     # 保留 TEST-NET-1 段，不产生流量
        address = probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()
    return address if address != "0.0.0.0" else None


def _access_urls(actual_port: int) -> list[str]:
    """列出真正可访问的 URL：本机回环 + 局域网 IP（若探测得到）。"""
    urls = [f"http://127.0.0.1:{actual_port}/"]
    lan = _lan_ip()
    if lan is not None:
        urls.append(f"http://{lan}:{actual_port}/")
    return urls


def _poll_loop(port: UiProjectionPort) -> None:
    """轮询线程（§4.5）：先睡后取，异常留痕但循环继续。"""
    global _PAGE
    while True:
        time.sleep(_HTTP_POLL_INTERVAL_SEC)
        try:
            port.snapshot()          # 第 2 步：取一次快照（失败则本轮结束）
            page = _render_page(port)   # 第 3 步：重新取快照渲染
            with _PAGE_LOCK:
                _PAGE = page         # 锁内只写一个 str 引用
        except Exception as exc:
            sys.stderr.write(f"界面轮询失败：{type(exc).__name__}: {exc}\n")


def _render_page(port: UiProjectionPort) -> str:
    """把 UiView 渲染成完整 HTML 文档（§4.6）。`snapshot()` 恰好调用一次。"""
    view = port.snapshot()
    err = render_error(view)
    buttons = "".join(
        f'<button data-kind="{html.escape(kind.value, quote=True)}">'
        f'{html.escape(COMMAND_LABELS[kind], quote=True)}</button>'
        for kind in COMMAND_LABELS
    )
    parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>口琴数据面调试视图</title>",
        "<style>body{font-family:monospace;background:#fafafa;padding:16px;margin:0}",
        "h1{font-size:1.25rem}h2{font-size:1rem;margin-top:1.2rem}",
        "pre{background:#fff;border:1px solid #ddd;padding:8px;white-space:pre-wrap;"
        "overflow-x:auto;font-size:.8rem}",
        "button{margin:4px 6px 4px 0;padding:10px 14px;font-size:1rem;"
        "min-height:44px;cursor:pointer}",
        "svg{max-width:100%;height:auto}",
        "/* 手机端：窄屏时按钮铺满、字号略缩；仍零依赖（无框架、无 CDN） */",
        "@media (max-width:600px){body{padding:8px}",
        "button{width:100%;margin:4px 0}pre{font-size:.72rem}}",
        "</style>",
        "</head><body>",
        "<h1>口琴数据面调试视图</h1>",
        "<pre>" + html.escape(render_status(view), quote=True) + "</pre>",
        "<h2>状态判别</h2>",
        "<pre>" + html.escape(_render_diagnosis(view), quote=True) + "</pre>",
        "<h2>标量指标</h2>",
        "<pre>" + html.escape(render_scalars(view.scalars), quote=True) + "</pre>",
        "<h2>数据端口</h2>",
        "<pre>" + html.escape(_render_ports(view), quote=True) + "</pre>",
        "<h2>曲线</h2>",
        "".join(str(item) for item in build_plots(view)),   # SVG 原样嵌入
        "<h2>进度</h2>",
        "<pre>" + html.escape(render_progress(view), quote=True) + "</pre>",
    ]
    if err:
        parts += ["<h2>错误</h2>", "<pre>" + html.escape(err, quote=True) + "</pre>"]
    parts += [
        "<h2>命令</h2>", buttons,
        # 路径输入：移动端 Safari 不支持 window.prompt，故用真实输入框。
        # ★ 仍只服务 SET_REFERENCE / SET_PRACTICE 两种意图，不新增第 7 种能力。
        '<label for="path-input">音频路径（仅选择参考/练习时需要）</label>',
        '<input id="path-input" type="text" inputmode="url" '
        'style="width:100%;padding:10px;min-height:44px;font-size:1rem">',
        "<script>",
        "document.querySelectorAll('button').forEach(function(b){",
        "  b.addEventListener('click', function(){",
        "    var body = {kind: b.dataset.kind};",
        "    if (b.dataset.kind === 'SET_REFERENCE' || b.dataset.kind === 'SET_PRACTICE') {",
        "      var f = document.getElementById('path-input');",
        "      var p = (f && f.value) ? f.value.trim() : '';",
        "      if (!p) { return; }",
        "      body.path = p;",
        "    }",
        "    fetch('/command', {method:'POST', headers:{'Content-Type':'application/json'},",
        "      body: JSON.stringify(body)}).then(function(r){ return r.text(); })",
        "      .then(function(h){ document.open(); document.write(h); document.close(); });",
        "  });",
        "});",
        "</script>",
        "</body></html>",
    ]
    return "\n".join(parts)


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
    session_id = view.session_id
    assert ("\n" not in session_id and "\r" not in session_id
            and "|" not in session_id)
    note_text = view.note.replace("\n", " ").replace("\r", " ").strip()
    if not note_text:
        note_text = _NO_NOTE_TEXT
    # ★ 用 .value 而非 f"{view.state}"：SessionState 是 str 混入枚举，
    # 但 Python 3.11+ 的 Enum.__str__ 返回 "SessionState.DATA_READY"，
    # 而规格 §4.8 要求「枚举的值」且 §8 判据断言输出恰为 "DATA_READY"。
    return f"会话 {session_id} | 状态 {view.state.value} | 说明 {note_text}"


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
    lines = []
    for item in scalars:
        value_str = f"{item.value:.{_SCALAR_VALUE_DECIMALS}f}"
        if item.threshold is None:
            if item.unit != "":
                lines.append(f"{item.label}：{value_str} {item.unit}")
            else:
                lines.append(f"{item.label}：{value_str}")
        else:
            thr_str = f"{item.threshold:.{_THRESHOLD_DECIMALS}f}"
            if item.unit != "":
                lines.append(
                    f"{item.label}：{value_str} {item.unit}（阈值 {thr_str} {item.unit}）")
            else:
                lines.append(f"{item.label}：{value_str}（阈值 {thr_str}）")
    return "\n".join(lines)


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
    assert len(series.t) == len(series.values)
    basis = series.timeline_basis
    if basis == "REFERENCE":
        axis_note = _AXIS_NOTE_REFERENCE
    elif basis == "WARPED":
        axis_note = _AXIS_NOTE_WARPED
    else:
        axis_note = _AXIS_NOTE_UNKNOWN_FMT.format(basis=basis)

    unit_text = series.unit if series.unit != "" else "（无单位）"
    texts = [
        '<text x="0" y="20">', html.escape(unit_text, quote=True), "</text>",
        '<text x="0" y="236">时间（秒）</text>',
        '<text x="0" y="254">', html.escape(axis_note, quote=True), "</text>",
        '<text x="0" y="272">',
        html.escape(f"{series.label} [{series.key}]", quote=True), "</text>",
    ]
    if series.source_port is not None:
        texts += [
            '<text x="0" y="290">',
            html.escape(f"source_port={series.source_port}", quote=True), "</text>",
        ]

    n = len(series.t)
    finite_values = [v for v in series.values
                     if not (v != v or v in (float("inf"), float("-inf")))]
    if finite_values:
        lo, hi = min(finite_values), max(finite_values)
    else:
        lo = hi = 0.0

    def _coord(index: int, value: float) -> tuple[float, float]:
        """横纵坐标：横按索引均分，纵按有限值极值线性映射（§4.7 第 7/9 步）。"""
        x = 0.0 if n == 1 else float(_SVG_WIDTH) * index / (n - 1)
        if not finite_values:
            y = 120.0
        elif hi == lo:
            y = 120.0
        else:
            y = 232.0 - 224.0 * (value - lo) / (hi - lo)
        return x, y

    # 切段：非有限点是切点，左右两段不连线；长度 1 的段不输出折线。
    segments: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    for index, value in enumerate(series.values):
        if value != value or value in (float("inf"), float("-inf")):
            if current:
                segments.append(current)
                current = []
            continue
        current.append(_coord(index, value))
    if current:
        segments.append(current)

    omitted = n - len(finite_values)
    polys = []
    for segment in segments:
        if len(segment) < 2:
            continue
        points = " ".join(f"{x:.3f},{y:.3f}" for x, y in segment)
        polys.append(f'<polyline fill="none" stroke="#333" stroke-width="1" points="{points}"/>')

    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{_SVG_WIDTH}" '
            f'height="{_SVG_HEIGHT}" viewBox="0 0 {_SVG_WIDTH} {_SVG_HEIGHT}">')
    return (head + "".join(texts) + "".join(polys)
            + f"<!-- omitted: {omitted} -->" + "</svg>")


def render_progress(view: UiView) -> str:
    """渲染进度指示。

    参数：
        view —— C1 的投影；进度为 view.progress。

    契约：
        - progress 为 None ⇒ 显示"无进度信息"，**不得**自行估算或从 state 推断百分比
        - progress 的取值域由 C1 定义；界面只做显示，不做归一化或截断判断

    返回：一行文本（str）。
    """
    if view.progress is None:
        return _NO_PROGRESS_TEXT
    percent = view.progress * 100.0
    return f"构建进度 {percent:.{_PROGRESS_PERCENT_DECIMALS}f}%"


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
    if view.error_code is None and view.error_detail is None:
        return ""
    code_text = view.error_code if view.error_code is not None else "（无）"
    text = f"错误 {code_text}"
    if view.error_detail is not None:
        text += "\n" + view.error_detail
    return text


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
        - ★ 本函数**只画值**不画结构：`port_summary` 的结构由 preview.py
          （契约定义视图）负责，本模块只画运行时的就绪状态（见 render_ports）。

    返回：渲染结果的序列（与 view.series 一一对应、同序）。
    """
    return [render_series_plot(item) for item in view.series]


# ═════════════════════════════════════════════════════════════════════
# 二 · 四态判别 + 端口就绪表（★ 防假绿）
# ═════════════════════════════════════════════════════════════════════

def _classify_view(view: UiView) -> str:
    """判别投影处于哪一态，返回四者之一的标签（★ 只判别，不修数据）。

    四态互斥且穷尽，判据全部来自 UiView 字段本身，不做任何推断：

    | 返回值        | 条件                                    | 含义 |
    | ---          | ---                                     | --- |
    | `A_UNBUILT`  | `state` 非 `DATA_READY`                 | 数据面尚未就绪 |
    | `D_BLOCKED`  | 无标量 且 `error_code`/`error_detail` 有值 | 管线断了，界面必须显示诊断 |
    | `B_NO_SOURCE`| 无标量 且 两个错误字段皆 `None`          | 已通但无数据 |
    | `C_HAS_DATA` | 有标量                                  | 有真实指标 |

    ★★ 为什么要单独的 D 态（★ 来自一次真实的假绿）★★
    ```
    实测曾出现：三个算法全部 INCOMPATIBLE，state 仍是 DATA_READY，
    scalars=[] series=[]，而 error_detail 里有明确诊断。
    ★ 若按「无标量 ⇒ B 已通无源」画，就把「三个算法全挂」画成了「正常但没数据」
    ★ 若按「有诊断 ⇒ C 有数据」画，就是假绿
    ★ 所以「无数据」有两种截然不同的含义，必须分开显示
    ```

    ★ 这三条互斥判据被 `verify_view_consistency` 逐条断言守住。
    """
    from ..contract import SessionState
    if view.state != SessionState.DATA_READY:
        return "A_UNBUILT"
    has_error = view.error_code is not None or view.error_detail is not None
    if not view.scalars:
        return "D_BLOCKED" if has_error else "B_NO_SOURCE"
    return "C_HAS_DATA"


def _verify_view_consistency(view: UiView) -> str:
    """对 `classify_view` 的四态判据做运行时自证，返回该态标签。

    ★ 用途：把「四态互斥」从口头约定变成可执行的断言 ——
    界面每次渲染前都调它，判据变了就在这里炸，而不是静默画错。
    """
    label = _classify_view(view)
    from ..contract import SessionState
    has_error = view.error_code is not None or view.error_detail is not None
    # 三者互斥：同一次调用不可能同时满足两个标签的前置条件
    if label == "C_HAS_DATA":
        assert len(view.scalars) > 0, "C_HAS_DATA 要求有标量"
    elif label == "D_BLOCKED":
        assert not view.scalars and has_error, "D_BLOCKED 要求无标量且有诊断"
    elif label == "B_NO_SOURCE":
        assert not view.scalars and not has_error, "B_NO_SOURCE 要求无标量且无诊断"
    else:
        assert view.state != SessionState.DATA_READY, "A_UNBUILT 要求未就绪"
    return label


def _render_ports(view: UiView) -> str:
    """渲染 12 个数据端口的就绪表：运行时事实，不是结构定义。

    列：`port_id | dimensions | element_type | timeline_basis | shape`
    ★ 刻意**不画**「是否就绪」为推断列 —— 就绪与否由 `view.error_detail` 给出，
    界面不逐端口猜测（那会是发明能力）。空 `port_summary` → 返回空串。
    """
    if not view.port_summary:
        return ""
    lines = ["port_id | dimensions | element_type | timeline_basis | shape"]
    for desc in view.port_summary:
        shape = "x".join(str(d) for d in desc.shape) if desc.shape else ""
        lines.append(
            f"{desc.port_id} | {'x'.join(desc.dimensions)} | "
            f"{desc.element_type} | {desc.timeline_basis} | {shape}")
    return "\n".join(lines)


def _render_diagnosis(view: UiView) -> str:
    """渲染四态标签与（仅 D 态时）诊断原文。

    ★ D 态（管线断了）必须显示诊断，且**不得**显示「无数据」这类占位 ——
    这是防假绿的第一道视觉关：一眼能看出「算法没跑出指标」而不是「本来就没数据」。
    """
    label = _verify_view_consistency(view)
    if label == "D_BLOCKED":
        return f"管线中断：{view.error_code or '（无）'}\n{view.error_detail or ''}"
    if label == "B_NO_SOURCE":
        return "已通但无数据"
    if label == "C_HAS_DATA":
        return "有指标"
    return "数据面未就绪"


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
    assert kind in COMMAND_LABELS
    needs_path = kind in (UiCommandKind.SET_REFERENCE, UiCommandKind.SET_PRACTICE)
    if not needs_path:
        assert payload is None or payload == {}
        return UiCommand(kind=kind, payload={})
    assert isinstance(payload, dict)
    assert set(payload.keys()) == {"path"}
    path = payload["path"]
    assert isinstance(path, str) and len(path) > 0 and "\x00" not in path
    return UiCommand(kind=kind, payload={"path": path})


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
    assert kind in (UiCommandKind.SET_REFERENCE, UiCommandKind.SET_PRACTICE)
    argv = ["osascript", "-e",
            'POSIX path of (choose file with prompt "选择音频文件")']
    try:
        completed = subprocess.run(argv, capture_output=True, text=True)
    except OSError as exc:
        assert False, f"osascript 不可用（{exc}）"
    if completed.returncode != 0:
        return None
    path = completed.stdout.strip()
    if not path:
        return None
    assert os.path.isabs(path)
    return os.path.abspath(path)


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
    assert isinstance(command, UiCommand)
    assert command.kind in COMMAND_LABELS
    needs_path = command.kind in (UiCommandKind.SET_REFERENCE,
                                   UiCommandKind.SET_PRACTICE)
    expected_keys = ("path",) if needs_path else ()
    assert set(command.payload.keys()) == set(expected_keys)
    if needs_path:
        path = command.payload["path"]
        assert isinstance(path, str) and len(path) > 0
    port.submit(command)


# ═════════════════════════════════════════════════════════════════════
# 四 · HTTP 请求处理器（模块私有，不进 __all__）
# ═════════════════════════════════════════════════════════════════════

def _make_handler(port: UiProjectionPort) -> type:
    """现造 `BaseHTTPRequestHandler` 子类，`port` 以闭包捕获（§4.16）。"""
    global _PAGE

    class _Handler(BaseHTTPRequestHandler):
        """唯一的写路径在 `do_POST` 第 7 步，且它复用 `submit_command`。"""

        def log_message(self, fmt, *args) -> None:
            """静音：界面不写日志文件，stderr 由调用方按需使用。"""

        def _respond(self, code: int, body: str) -> None:
            """写一个 HTML 响应（锁外取 `_PAGE`，不在响应期持锁）。"""
            raw = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", _HTML_CONTENT_TYPE)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path != "/":
                self._respond(404, "not found")
                return
            with _PAGE_LOCK:
                page = _PAGE          # 锁内只读一个 str 引用
            self._respond(200, page)

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/command":
                self._respond(404, "not found")
                return
            # 第 2 步：Content-Length 校验
            raw_len = self.headers.get("Content-Length")
            try:
                length = int(raw_len)
            except (TypeError, ValueError):
                self._respond(400, "bad request：Content-Length 缺失或不是整数")
                return
            if length <= 0 or length > _HTTP_MAX_VIEW_BYTES:
                self._respond(400, f"bad request：Content-Length 须在 1..{_HTTP_MAX_VIEW_BYTES}，实得 {length}")
                return
            # 第 3 步：读满并解 UTF-8
            raw = self.rfile.read(length)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                self._respond(400, "bad request：请求体不是合法 UTF-8")
                return
            # 第 4 步：JSON 且必须是 dict
            try:
                data = json.loads(text)
            except ValueError as exc:
                self._respond(400, f"bad request：请求体不是合法 JSON（{exc}）")
                return
            if not isinstance(data, dict):
                self._respond(400, f"bad request：请求体须是 JSON 对象，实得 {type(data).__name__}")
                return
            # 第 5 步：kind 必须是 6 个枚举值之一
            raw_kind = data.get("kind")
            if not isinstance(raw_kind, str) or raw_kind not in {
                    k.value for k in UiCommandKind}:
                self._respond(
                    400,
                    f"bad request：kind={raw_kind!r} 不是界面支持的 6 种意图之一"
                    f"（{'/'.join(k.value for k in UiCommandKind)}）",
                )
                return
            # 第 6 步：还原枚举与载荷
            kind = UiCommandKind(raw_kind)
            payload = {"path": data["path"]} if "path" in data else None
            # 第 7 步：复用两个公开函数（不自己拼 UiCommand、不自己调 submit）
            #   ★ 分两类：内核主动拒绝（可预期，用户改输入即可）→ 400
            #     未预料的异常（真 bug）→ 500，并保留完整类型名便于定位
            try:
                command = build_command(kind, payload)
                submit_command(port, command)
            except HarmonicaError as exc:
                # 契约里已定义的错误（ContractViolation / CoreBuildError /
                # AlgorithmError）。它们是内核对用户输入的明确拒绝，
                # ★ 不是服务端故障 —— 回 400 并把原话带给用户。
                sys.stderr.write(
                    f"界面命令被内核拒绝：{type(exc).__name__}: {exc}\n"
                )
                self._respond(
                    400, f"{type(exc).__name__}：{exc}"
                )
                return
            except Exception as exc:
                sys.stderr.write(f"界面命令失败：{type(exc).__name__}: {exc}\n")
                self._respond(500, "internal error")
                return
            # 第 8 步：重渲染并返回；第 9 步：写锁在渲染之外
            page = _render_page(port)
            with _PAGE_LOCK:
                _PAGE = page
            self._respond(200, page)

        def _method_not_allowed(self) -> None:
            self._respond(405, "method not allowed")

        do_PUT = _method_not_allowed
        do_DELETE = _method_not_allowed
        do_PATCH = _method_not_allowed

    return _Handler


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
