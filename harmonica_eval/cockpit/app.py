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
    COMMAND_LEGALITY,
    ErrorCode,
    HarmonicaError,
    SessionState,
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

_INVENTORY_CACHE: dict | None = None
_INVENTORY_LOCK = threading.Lock()
"""数据集清单的进程侧缓存。★ 清单在一次运行内不变，★ 所以只扫一次；
写点唯一（`_dataset_json` 的首次调用），★ 不与 `_PAGE` 共享锁。"""


def _dataset_json() -> str:
    """返回数据集清单的 JSON 文本（进程侧现扫，带一次缓存）。

    ★ 为什么需要它：★ 浏览器读不到文件系统，★ 所以「曲子里有哪些音频」
    只能由进程交给页面。★ 清单从 `serve_ui.scan_dataset` 取真实返回，
    ★ 页面不写死任何曲名或路径 ——★ 否则「清单准了但界面上是另一套」。
    """
    global _INVENTORY_CACHE
    with _INVENTORY_LOCK:
        if _INVENTORY_CACHE is None:
            from ..serve_ui import scan_dataset      # 延迟：避免包导入期拉数据集
            _INVENTORY_CACHE = scan_dataset()
        return json.dumps(_INVENTORY_CACHE, ensure_ascii=False)


def _render_song_picker() -> str:
    """渲染按曲子分组的两个下拉框（参考 / 练习），★ 清单**首屏内嵌**。

    为什么首屏内嵌而不是「空壳 + fetch 填」：
      ★ 空壳下拉【看起来完全可用】而实际是空的，★ 用户点下去才发现选不了。
        那比「没有下拉」更伤——★ 那是假绿的一种形态。
      ★ 内嵌后不执行 JS 也看得到清单，★ curl 就能验，★ 弱网/脚本被禁时仍可用。
      ★ 端点仍保留：★ 它给「清单变了要刷新」用，★ 不再是首屏的必要条件。

    结构决策（★ 负责人「选择那一个歌曲」）：
      - `<optgroup label="奇异恩典">` —— 人看的是曲名，★ 编号只用于排序
      - `value` 是完整路径 —— 那是命令要吃的
      - ★ 参考与练习【可以不同曲】—— ★ 所以两个下拉各自独立分组，
        ★ 不用「先选参考曲，再由它驱动练习」的单向依赖。
        （那会让「拿 A 曲当参考、B 曲当练习」无法表达，★ 而那是合法用法。）

    ★ 清单逐条来自 `_dataset_json()`（进程侧 `scan_dataset()` 的真实返回），
    ★ 渲染层不写死任何曲名或路径。
    """
    inv = json.loads(_dataset_json())
    ref_rows: list[str] = []
    prac_rows: list[str] = []
    for song in inv.get("songs", []):
        title = song.get("title") or song.get("name") or ""
        opts: list[str] = []
        if song.get("original"):
            opts.append(
                f'<option value="{html.escape(song["original"], quote=True)}">'
                f'{html.escape(title)} · 原曲</option>'
            )
        if song.get("melody_version"):
            opts.append(
                f'<option value="{html.escape(song["melody_version"], quote=True)}">'
                f'{html.escape(title)} · 标准旋律版</option>'
            )
        if opts:
            ref_rows.append(
                f'<optgroup label="{html.escape(title, quote=True)}">'
                + "".join(opts) + "</optgroup>"
            )
        p_opts = [
            f'<option value="{html.escape(p["path"], quote=True)}">'
            f'{html.escape(title)} · {html.escape(p["name"])}</option>'
            for p in song.get("practice", [])
        ]
        prac_dir = ""
        if song.get("practice"):
            prac_dir = str(song["practice"][0]["path"]).rsplit("/", 1)[0]
        if p_opts:
            # ★ data-title / data-dir 供页面 JS 标「（与参考同曲）」——
            #   ★ label 会被 JS 改写，★ 所以原始曲名与目录要另存一份。
            prac_rows.append(
                f'<optgroup label="{html.escape(title, quote=True)}" '
                f'data-title="{html.escape(title, quote=True)}" '
                f'data-dir="{html.escape(prac_dir, quote=True)}">'
                + "".join(p_opts) + "</optgroup>"
            )
    empty = '<option value="">— 清单为空 —</option>'
    return (
        '<label for="ref-select">选择参考演奏（原曲或标准旋律版）</label>'
        '<select id="ref-select" style="width:100%;padding:10px;min-height:44px">'
        + (empty if not ref_rows else "".join(ref_rows))
        + "</select>"
        '<label for="practice-select">选择练习演奏（模拟吹奏的那一条）</label>'
        '<select id="practice-select" '
        'style="width:100%;padding:10px;min-height:44px">'
        + (empty if not prac_rows else "".join(prac_rows))
        + "</select>"
    )


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


def _command_availability(
    state: SessionState,
) -> dict[UiCommandKind, tuple[bool, str]]:
    """按当前状态算出 6 个命令各自「此刻能否执行」，并给出不可用的原因。

    契约：
    - 合法性表来自 `COMMAND_LEGALITY`（冻结契约），**不在界面另写一份**
    - 每个不可用项都要能回答「为什么现在不能点」与「接下来该做什么」；
      只置灰不解释，等于把问题推回给用户
    - 界面只改【怎么呈现】，不改四态判别的语义
    """
    out: dict[UiCommandKind, tuple[bool, str]] = {}
    for kind in COMMAND_LABELS:
        legal_states = COMMAND_LEGALITY.get(kind) or frozenset()
        if state in legal_states:
            out[kind] = (True, "")
            continue
        # 不可用：说清当前状态，并指向「现在能做的那件事」
        reachable = [
            COMMAND_LABELS[k] for k in COMMAND_LABELS
            if state in (COMMAND_LEGALITY.get(k) or frozenset())
        ]
        hint = f"当前状态 {state.value} 下不可用；现在能做：" + "、".join(reachable)
        out[kind] = (False, hint)
    return out


def _render_buttons(availability: dict[UiCommandKind, tuple[bool, str]]) -> str:
    """渲染 6 个命令按钮，按钮的可用态与说明都由当前状态现算。

    可用性设计（依据 NN/g「Why Disabled Buttons Hurt UX」与 WAI-ARIA）：
    - 不可用按钮用 `aria-disabled="true"` 而**不是** HTML `disabled`。
      原生 `disabled` 不可聚焦，键盘与读屏用户因此拿不到「为什么不能点」。
    - 原因写在 `title` 与可见的 `aria-describedby` 目标里，鼠标悬停/读屏都能取到。
    - 事件不在渲染期绑定：点击时若不可用，**就地给出原因**并就地反馈，
      而不是让点击毫无反应。
    """
    parts: list[str] = []
    for kind, (ok, reason) in availability.items():
        label = html.escape(COMMAND_LABELS[kind], quote=True)
        desc_id = f"why-{kind.value}"
        aria = "" if ok else f' aria-disabled="true" aria-describedby="{desc_id}"'
        cls = "" if ok else ' class="is-blocked"'
        parts.append(
            f'<button data-kind="{html.escape(kind.value, quote=True)}"{cls}{aria}>'
            f"{label}</button>"
        )
        if not ok:
            parts.append(
                f'<p id="{desc_id}" class="why">{html.escape(reason, quote=True)}</p>'
            )
    return "".join(parts)


def _render_page(port: UiProjectionPort) -> str:
    """把 UiView 渲染成完整 HTML 文档（§4.6）。`snapshot()` 恰好调用一次。"""
    view = port.snapshot()
    err = render_error(view)
    availability = _command_availability(view.state)
    buttons = _render_buttons(availability)
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
        # ★ 不可用按钮：置灰但【不隐藏】。原因就在按钮下方，可悬停/读屏取到。
        "button.is-blocked{opacity:.45;cursor:not-allowed}",
        "button.is-blocked:hover{opacity:.7}",
        ".why{margin:2px 0 8px;padding:6px 8px;background:#fff8e1;"
        "border-left:3px solid #f9a825;font-size:.78rem;color:#5d4037}",
        # ★ 反馈区：任何一次点击都在这里留下痕迹（aria-live 让读屏也能听到）。
        ".feedback{min-height:1.6em;margin:6px 0;padding:6px 8px;font-size:.85rem;"
        "border-left:3px solid #bbb;background:#fff}",
        ".feedback.is-ok{border-left-color:#2e7d32;background:#f1f8e9}",
        ".feedback.is-warn{border-left-color:#ef6c00;background:#fff3e0}",
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
        # ★ 按 key 前缀分组：前缀即 algorithm_id，★ 分组现算不写死。
        # ★ 新插件接入后它那一组会自己出现 —— 这就是可插拔在界面上的可见形式。
        "<p>下列数字由各插件算出，按 <code>算法.指标名</code> 分组；"
        "新插件接入后其分组自动出现。</p>",
        "<pre>"
        + html.escape(_render_scalars_by_plugin(view.scalars), quote=True)
        + "</pre>",
        "<h2>数据端口</h2>",
        "<pre>" + html.escape(_render_ports(view), quote=True) + "</pre>",
        "<h2>对比图</h2>",
        # ★ 参考与练习叠在同一坐标系 —— 差异一眼可见，而不是让人心算。
        # ★ 配对键现算（"<算法>.<指标>" 后缀去 _reference/_practice），
        # ★ 新插件接入后它的对比图自动出现；不按算法名写死。
        "".join(str(item) for item in _build_comparisons(view)),
        "<h2>曲线</h2>",
        # ★ 单条图只画【没有配对同伴】的那些。
        # ★ ★ ★ 原因：成对曲线已在上面的对比图里叠放过一次，
        # ★ ★ ★ 若这里再逐条画一遍，同一对数据会出现两张图 ——
        # ★ ★ ★ 而单条图各自算 Y 轴范围，★ 相同数据会被画到不同纵坐标上，
        # ★ ★ ★ 自比时表现为「两条线不重合」的假绿（实测 34/34 点全不同）。
        # ★ ★ ★ 所以这里只画【未配对】的曲线（`_unpaired_series`）；
        # ★ ★ ★ 筛选是展示层的事，★ `build_plots` 本身仍严格一一对应
        # ★ ★ ★ （FILE-401 §4.12 冻结的输出契约），★ 两者分工不混。
        "".join(
            str(render_series_plot(item)) for item in _unpaired_series(view)
        ),
        "<h2>进度</h2>",
        "<pre>" + html.escape(render_progress(view), quote=True) + "</pre>",
    ]
    if err:
        parts += ["<h2>错误</h2>", "<pre>" + html.escape(err, quote=True) + "</pre>"]
    parts += [
        "<h2>命令</h2>", buttons,
        # ★ 内联反馈区：任何一次点击都在这里留下痕迹。
        #   先前 400 的原因只躺在 HTTP 响应体里，页面既不显示也不更新，
        #   用户点完像没点过 —— 那是「按钮点不动」的真正来源。
        '<p id="cmd-feedback" class="feedback" role="status" aria-live="polite"></p>',
        # ★ 选曲面板：★ 曲子是选择单位，不是 70 个 wav 文件名。
        #   label 给人看（曲名 + 角色），value 给命令吃（完整路径）。
        #   optgroup 按曲名分组 —— 平铺 70 条没法用。
        #   ★ 清单来自 /dataset（进程侧 scan_dataset 的真实返回），
        #   ★ 页面不写死任何曲名或路径。
        "<h2>选择音频</h2>",
        '<p class="hint">从下拉里选，'
        '不必手打路径。清单来自 <code>/dataset</code>。</p>',
        _render_song_picker(),
        # 路径输入：移动端 Safari 不支持 window.prompt，故用真实输入框。
        # ★ 仍只服务 SET_REFERENCE / SET_PRACTICE 两种意图，不新增第 7 种能力。
        # ★ 下拉选中会填进它；★ 它保留是为了「清单外的路径」也能用。
        '<label for="path-input">音频路径（下拉选中的会填到这里；仅选择参考/练习时需要）</label>',
        '<input id="path-input" type="text" inputmode="url" '
        'style="width:100%;padding:10px;min-height:44px;font-size:1rem">',
        "<script>",
        # ★ 命令中文名注入页面，★ 反馈文案用真名而不是枚举值。
        #   仍然零外部依赖：这是内联字面量，不是引入脚本。
        "var COMMAND_LABELS = {"
        + ",".join(
            f'"{html.escape(kind.value, quote=True)}":'
            f'"{html.escape(COMMAND_LABELS[kind], quote=True)}"'
            for kind in COMMAND_LABELS
        )
        + "};",
        # ★ 清单已【首屏内嵌】（服务端渲染），★ 所以这里不再 fetch。
        #   ★ 若还走「空壳 + fetch 填」，那个下拉【看起来可用而实际是空的】——
        #     用户点下去才发现选不了，★ 那比「没有下拉」更伤（假绿的一种形态）。
        #   ★ JS 只做一件事：【选中即填 path-input】+ 同曲提示。
        "function fillFromSelect(id){",
        "  var sel = document.getElementById(id);",
        "  if (sel && sel.value) document.getElementById('path-input').value = sel.value;",
        "  return sel;",
        "}",
        "function hintSameSong(){",
        "  var r = document.getElementById('ref-select');",
        "  var p = document.getElementById('practice-select');",
        "  if (!r || !p) return;",
        "  var refDir = r.value ? r.value.split('/').slice(0,-1).join('/') : '';",
        "  Array.prototype.forEach.call(p.querySelectorAll('optgroup'), function(g){",
        "    var same = (g.getAttribute('data-dir') || '') === refDir;",
        "    g.label = same ? (g.getAttribute('data-title') || '') + '（与参考同曲）'",
        "                    : (g.getAttribute('data-title') || '');",
        "  });",
        "}",
        # ★ 死锁的来由（三路改动单独都对，合起来堵死主流程）：
        #   · serve_ui 启动即 run_algorithms → 状态恒为 DATA_READY
        #   · SET_REFERENCE/SET_PRACTICE 只在 {CREATED, INPUT_READY} 合法
        #   · 按钮按 COMMAND_LEGALITY 现算可用性 → 那两个按钮永远置灰
        # ★ 所以下拉框能选、却送不进去。唯一合法出路是【先 RESET】。
        #
        # ★ 为什么必须【串行】而不是并发发出五条：
        #   服务端是 ThreadingHTTPServer（app.py:51），并发 POST 落到不同线程，
        #   ★ 到达顺序不保证 —— BUILD_SURFACE 可能先于 SET_REFERENCE 到达，
        #   ★ 那就又是 400。顺序是【承重】的，不是碰巧。
        #
        # ★ 为什么不在每步之间 reload：
        #   do_POST 第 8-9 步每次都重渲染并返回新页面（app.py:1398-1402），
        #   ★ 但那会清掉下拉框的当前选择 —— 而「只换一个下拉、另一个不动」
        #   ★ 恰恰依赖另一个还留着原值。所以只在【全部成功后】reload 一次。
        "function postCommand(body){",
        "  return fetch('/command', {method:'POST',",
        "    headers:{'Content-Type':'application/json'},",
        "    body: JSON.stringify(body)}).then(function(r){",
        "    return r.text().then(function(t){ return {ok:r.ok, text:t}; });",
        "  });",
        "}",
        # ★ 等到【真有指标】再刷新页面。
        #   判据是「DATA_READY 且标量区已出现」，★ 而不是「跑完就刷」——
        #   ★ 后者会撞上轮询线程的 BUILDING 帧（见 runSelection 里的说明）。
        #   ★ 超时才刷：★ 宁可让用户看见当前这一帧，★ 也不要永远转圈。
        "function settle(attempt){",
        "  var n = attempt || 0;",
        "  if (n > 60){ location.reload(); return; }",
        "  fetch('/', {cache:'no-store'}).then(function(r){ return r.text(); })",
        "    .then(function(t){",
        "      var ready = t.indexOf('DATA_READY') >= 0",
        "                 && t.indexOf('中位绝对偏差') >= 0;",
        "      if (ready){ location.reload(); return; }",
        "      setTimeout(function(){ settle(n + 1); }, 500);",
        "    }).catch(function(){",
        "      setTimeout(function(){ settle(n + 1); }, 500);",
        "    });",
        "}",
        "function runSelection(refPath, praPath){",
        "  var fb = document.getElementById('cmd-feedback');",
        "  var steps = [",
        "    {kind:'RESET'},",
        "    {kind:'SET_REFERENCE', path: refPath},",
        "    {kind:'SET_PRACTICE',  path: praPath},",
        "    {kind:'BUILD_SURFACE'},",
        "    {kind:'RUN_ALGORITHMS'}",
        "  ];",
        "  var i = 0;",
        "  fb.textContent = '正在按所选音频重新分析…';",
        "  fb.className = 'feedback';",
        "  function step(){",
        "    if (i >= steps.length){",
        # ★ ★ 跑完不能【立刻 reload】—— ★ 这是一个实测出来的竞态：
        #   · 服务端有 0.5 秒一次的轮询线程（_poll_loop，app.py:114/409）
        #   · 它随时取一次 snapshot() 重渲染 _PAGE
        #   · 而 build_surface 途中状态是 BUILDING
        #   ★ 所以 RUN_ALGORITHMS 刚返回时，_PAGE 可能已被轮询线程
        #   ★ 刷成了 BUILDING 那一帧 —— ★ 此刻 reload 会把用户丢到
        #   ★ 一个「进度 0%、无指标」的页面，而那【看起来像跑失败了】。
        # ★ 所以这里【轮询到 DATA_READY 且有指标】再 reload。
        "      settle();",
        "      return;",
        "    }",
        "    var s = steps[i++];",
        "    var body = {kind: s.kind};",
        "    if (s.path) body.path = s.path;",
        "    postCommand(body).then(function(res){",
        "      if (!res.ok){",
        # ★ 任一步被拒就停：★ 继续发只会让后面的步骤在错的状态上再错一次。
        "        fb.textContent = (COMMAND_LABELS[s.kind] || s.kind) + '：' + res.text;",
        "        fb.className = 'feedback is-warn';",
        "        return;",
        "      }",
        "      step();",
        "    }).catch(function(e){",
        "      fb.textContent = '命令未能送达服务端：' + e;",
        "      fb.className = 'feedback is-warn';",
        "    });",
        "  }",
        "  step();",
        "}",
        # ★ 「只改一个下拉」怎么处理：每次 change 都重读【两个】下拉的现值，
        #   把参考与练习各发一次。另一个的值还在（本次页面内没 reload 就没丢），
        #   ★ 所以换一个曲子不必重选另一个。无需在服务端记「上次选了什么」——
        #   ★ 那样要动冻结契约，而这里纯客户端就够。
        "function saveSelection(){",
        "  try {",
        "    var r = document.getElementById('ref-select');",
        "    var p = document.getElementById('practice-select');",
        "    if (r && r.value) localStorage.setItem('harmonica.ref', r.value);",
        "    if (p && p.value) localStorage.setItem('harmonica.practice', p.value);",
        "  } catch (e) { /* ★ 隐私模式下 localStorage 可能抛；★ 那就不记忆，★ 不影响主流程 */ }",
        "}",
        "['ref-select','practice-select'].forEach(function(id){",
        "  var sel = document.getElementById(id);",
        "  if (!sel) return;",
        "  sel.addEventListener('change', function(){",
        "    if (!sel.value) return;",
        "    fillFromSelect(id);",
        "    hintSameSong();",
        "    saveSelection();",
        "    var r = document.getElementById('ref-select');",
        "    var p = document.getElementById('practice-select');",
        # ★ 两端都有值才跑：★ 只选了一端就去分析，★ 那不是双音频对比。
        "    if (!r || !p || !r.value || !p.value){",
        "      var fb0 = document.getElementById('cmd-feedback');",
        "      fb0.textContent = '已选参考；再选一条练习曲就会自动开始对比';",
        "      fb0.className = 'feedback';",
        "      return;",
        "    }",
        "    runSelection(r.value, p.value);",
        "  });",
        "});",
        # ★ 刷新后把上次选的两端恢复回下拉框。
        #   为什么需要：整轮成功后要 reload，★ 而 reload 会把 <select> 复位到第一项；
        #   ★ 若不恢复，★ 用户下一次只改一个下拉时，★ 另一个会被悄悄换成第一首。
        #   ★ 那是「看起来没变、其实换了曲子」——★ 又是一种假绿。
        #   ★ 用 localStorage 而非服务端记忆：★ 纯客户端，★ 不动冻结契约。
        "try {",
        "  ['harmonica.ref','harmonica.practice'].forEach(function(k){",
        "    var id = (k === 'harmonica.ref') ? 'ref-select' : 'practice-select';",
        "    var sel = document.getElementById(id);",
        "    var v = localStorage.getItem(k);",
        "    if (sel && v){",
        "      for (var i=0; i<sel.options.length; i++){",
        "        if (sel.options[i].value === v){ sel.selectedIndex = i; break; }",
        "      }",
        "    }",
        "  });",
        "  fillFromSelect('ref-select');",
        "  fillFromSelect('practice-select');",
        "  hintSameSong();",
        "} catch (e) { /* ★ 同上：★ 记忆失败不影响主流程 */ }",
        "document.querySelectorAll('button').forEach(function(b){",
        "  b.addEventListener('click', function(){",
        "    var fb = document.getElementById('cmd-feedback');",
        "    var kind = b.dataset.kind;",
        "    if (b.getAttribute('aria-disabled') === 'true') {",
        "      var why = document.getElementById('why-' + kind);",
        "      fb.textContent = (COMMAND_LABELS[kind] || kind) + '：' +",
        "                       ((why && why.textContent) || '当前状态不可执行');",
        "      fb.className = 'feedback is-warn';",
        "      return;",
        "    }",
        "    var body = {kind: kind};",
        "    if (kind === 'SET_REFERENCE' || kind === 'SET_PRACTICE') {",
        "      var f = document.getElementById('path-input');",
        "      var p = (f && f.value) ? f.value.trim() : '';",
        "      if (!p) {",
        "        fb.textContent = '请先在下方填入音频路径';",
        "        fb.className = 'feedback is-warn';",
        "        return;",
        "      }",
        "      body.path = p;",
        "    }",
        "    fb.textContent = (COMMAND_LABELS[kind] || kind) + '：执行中…';",
        "    fb.className = 'feedback';",
        "    fetch('/command', {method:'POST', headers:{'Content-Type':'application/json'},",
        "      body: JSON.stringify(body)}).then(function(r){",
        "        return r.text().then(function(t){ return {ok: r.ok, text: t}; });",
        "      }).then(function(res){",
        "        if (res.ok) {",
        "          fb.textContent = (COMMAND_LABELS[kind] || kind) + '：已执行';",
        "          fb.className = 'feedback is-ok';",
        "        } else {",
        "          fb.textContent = (COMMAND_LABELS[kind] || kind) + '：' + res.text;",
        "          fb.className = 'feedback is-warn';",
        "        }",
        "        return fetch('/');",
        "      }).then(function(){",
        "        if (kind !== 'RESET' && kind !== 'CANCEL') { return; }",
        "        location.reload();",
        "      }).catch(function(e){",
        "        fb.textContent = '命令未能送达服务端：' + e;",
        "        fb.className = 'feedback is-warn';",
        "      });",
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


def _render_scalars_by_plugin(scalars: Sequence[UiScalar]) -> str:
    """按 **指标 key 的前缀**把标量分组渲染，每组一个标题。

    为什么要分组：`UiScalar.key` 的前缀就是产出它的 `algorithm_id`
    （`pitch.median_abs_cents` / `timing.…` / `dynamics.…`）。
    把前缀显示出来，读者才知道这些数字**不是写死的**，而是逐个插件算出来的；
    任何新插件接入后，它的那一组会自己出现，无需改界面。

    契约：
        - **前缀一律现算**：以第一个 `.` 切分，★ 绝不枚举已知算法名
        - 顺序：按组内首条指标在 `scalars` 中的出现次序，★ 不排序不改写
        - 只做展示分组，★ **不重算、不合并、不统计**（与 render_scalars 同约束）
        - 无点号的 key（若将来出现）归入「（无前缀）」组，★ 不丢弃

    返回：多行文本（str）。
    """
    order: list[str] = []
    grouped: dict[str, list[UiScalar]] = {}
    for item in scalars:
        head = item.key.split(".", 1)[0] if "." in item.key else "（无前缀）"
        if head not in grouped:
            grouped[head] = []
            order.append(head)
        grouped[head].append(item)

    lines: list[str] = []
    for head in order:
        block = grouped[head]
        lines.append(f"── {head}（{len(block)} 项）")
        # ★ 表格而非纯文本行：16 行 pre 堆着最难扫，而「哪个数字异常」正是
        # ★ 读者来这个页面的目的。三列对齐，阈值并列（不判定合格与否）。
        lines.append("  指标".ljust(34) + "值".rjust(14) + "  阈值")
        for item in block:
            name = item.label if item.label else item.key
            value = f"{item.value:.{_SCALAR_VALUE_DECIMALS}f} {item.unit}".rstrip()
            if item.threshold is None:
                thr = "—"
            else:
                thr = f"{item.threshold:.{_THRESHOLD_DECIMALS}f} {item.unit}"
            lines.append("  " + name[:32].ljust(32) + value.rjust(14) + "  " + thr)
        lines.append("")
    return "\n".join(lines).rstrip()


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
        - ★ 输出恒与 `view.series` **一一对应且同序**，★ 不做筛选。
          「已配对的曲线不再单画」是**展示层**的选择，★ 属 `_render_page`；
          若在本函数内筛选，★ 同一对数据会在两张图上按各自的 Y 轴范围绘制，
          ★ 自比时表现为假绿。

    返回：渲染结果的序列（与 view.series 一一对应、同序）。
    """
    return [render_series_plot(item) for item in view.series]


def _unpaired_series(view: UiView) -> list[UiSeries]:
    """挑出【没有配对同伴】的曲线 —— 供展示层决定画哪些单条图。

    成对曲线已由 `_build_comparisons` 叠在同一坐标系画过一次；
    单条图各自计算 Y 轴范围，★ 若把同一对数据再逐条单画，
    相同数值会落到不同纵坐标上，★ 自比时读成「有差异」——★ 那是假绿。

    配对依据是 key 的 `_reference` / `_practice` 后缀（见 `_comparison_pairs`），
    **现算**，★ 不按算法名写死。

    返回：未被配对的曲线列表（保持 `view.series` 原序）；★ 本函数只读。
    """
    items = list(view.series)
    paired = {
        key
        for ref, pra in _comparison_pairs(items)
        for key in (ref.key, pra.key)
    }
    return [item for item in items if item.key not in paired]


# ═════════════════════════════════════════════════════════════════════
# 参考 / 练习 对比图（把两条曲线画在同一坐标系里）
# ═════════════════════════════════════════════════════════════════════

_COMPARISON_SUFFIXES = (("_reference", "_practice"), ("_ref", "_prac"))


def _comparison_pairs(series: Sequence[UiSeries]) -> list[tuple[UiSeries, UiSeries]]:
    """把投影里的曲线配成「参考 / 练习」对。

    配对依据是 key 的 `_reference` / `_practice` 后缀，**现算**：
    新插件若产出同样成对后缀的曲线，对比图自动出现，界面不写死算法名。

    `build_plots` 的契约是「与 view.series 一一对应」，那是单曲线视图；
    对比图是另一种视图，故独立成函数，不改 `build_plots`。
    """
    by_key = {item.key: item for item in series}
    pairs: list[tuple[UiSeries, UiSeries]] = []
    seen: set[str] = set()
    for item in series:
        for ref_sfx, pra_sfx in _COMPARISON_SUFFIXES:
            if item.key.endswith(pra_sfx):
                base = item.key[: -len(pra_sfx)]
                other = by_key.get(base + ref_sfx)
                if other is not None and base not in seen:
                    seen.add(base)
                    pairs.append((other, item))
                break
    return pairs


def _build_comparisons(view: UiView) -> list[object]:
    """为每一对「参考 / 练习」曲线生成一张叠放图。"""
    return [_render_comparison(ref, pra) for ref, pra in _comparison_pairs(view.series)]


def _render_comparison(reference: UiSeries, practice: UiSeries) -> str:
    """把两条曲线画进同一坐标系，输出 SVG 字符串。

    与 `render_series_plot` 同样的纪律：
    - **只画投影里的值**：不重算、不插值、不平滑、不补点。
    - 两条线长度不等时**只画各自有的部分**，不拉伸、不对齐、不补零 ——
      05_漏音断句 的音数 34/35 就是真实信息，抹平反而是撒谎。
    - 元素只用 `<text>` / `<polyline>` / 注释（FILE-401 §4.7 冻结四类）。
      没有 grid/line/rect，所以刻度用文字标注极值而非画线。
    """
    width, height = 760, 300
    # 绘图区（留出左侧单位、右侧图例、上下标注）
    x0, x1 = 64.0, width - 132.0
    y0, y1 = 56.0, height - 58.0

    unit = practice.unit or "（无单位）"
    ref_vals = [v for v in reference.values if v == v and v not in (float("inf"), float("-inf"))]
    pra_vals = [v for v in practice.values if v == v and v not in (float("inf"), float("-inf"))]
    finite = ref_vals + pra_vals
    if finite:
        lo, hi = min(finite), max(finite)
    else:
        lo = hi = 0.0

    # ★ f0 是绝对频率（hz）。直接画 hz 在低频区会【放大】差异：
    #   ★ 03_气息不匀 的音高只差约 48 Hz，★ 而 200 Hz 的基频上那是巨大的
    #   ★ 垂直距离 ——★ 读者会以为音高差很多，★ 而实际上它几乎没动。
    # ★ 所以音高图统一换算成【音分】：1200*log2(f_practice/f_reference)，
    # ★ 与 pitch.per_note_cents 同算法同语义，★ 0 = 完全准，100 = 一个半音。
    # ★ ★ 换算按【下标】配对而非 zip：★ 两侧长度不同时 zip 会截断成等长，
    # ★ ★ 那会伪造出一个「两侧一样长」的假象（05_漏音断句 21/34）。
    # ★ ★ 所以短的一侧原长、长的补 NaN，★ NaN 段在折线里被断开。
    is_f0 = unit == "hz" and ref_vals and pra_vals
    if is_f0:
        import math

        n = max(len(ref_vals), len(pra_vals))
        cents_line: list[float] = []
        ref_line: list[float] = []
        for i in range(n):
            a_hz = ref_vals[i] if i < len(ref_vals) else None
            b_hz = pra_vals[i] if i < len(pra_vals) else None
            if a_hz is None or b_hz is None or a_hz <= 0.0 or b_hz <= 0.0:
                ref_line.append(float("nan"))
                cents_line.append(float("nan"))
                continue
            ref_line.append(0.0)
            cents_line.append(1200.0 * math.log2(b_hz / a_hz))
        pra_line = cents_line
        usable = [c for c in cents_line if c == c]
        if usable:
            lo, hi = min(usable), max(usable)
        else:
            lo = hi = 0.0
        y_label = "音分（0=准，100=一个半音）"
        x_label = "音序（第几个音，非秒）"
    else:
        ref_line = ref_vals
        pra_line = pra_vals
        y_label = unit
        x_label = "时间（秒）"

    def _x(index: int, total: int) -> float:
        return x0 if total <= 1 else x0 + (x1 - x0) * index / (total - 1)

    def _y(value: float) -> float:
        if hi == lo:
            return (y0 + y1) / 2
        return y1 - (y1 - y0) * (value - lo) / (hi - lo)

    def _polyline(values: Sequence[float], stroke: str) -> str:
        points = " ".join(
            f"{_x(i, len(values)):.2f},{_y(v):.2f}" for i, v in enumerate(values)
            if v == v and v not in (float("inf"), float("-inf"))
        )
        if not points:
            return ""
        return (f'<polyline fill="none" stroke="{stroke}" stroke-width="1.6" '
                f'points="{points}"/>')

    base = reference.key
    for sfx, _ in _COMPARISON_SUFFIXES:
        if base.endswith(sfx):
            base = base[: -len(sfx)]
            break

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<text x="8" y="20">{html.escape(y_label)}</text>',
        f'<text x="{x0}" y="{height - 8}">{html.escape(x_label)}</text>',
        f'<text x="8" y="40">参考 {len(reference.values)} 点 · '
        f'练习 {len(practice.values)} 点</text>',
        # 零线（音分图的 0 = 完全准；能量图仅作参考线）
        f'<text x="{x1 + 6}" y="{_y(lo) + 4:.1f}">{lo:.1f}</text>',
        f'<text x="{x1 + 6}" y="{_y(hi) + 4:.1f}">{hi:.1f}</text>',
        _polyline(ref_line, "#1f6feb"),
        _polyline(pra_line, "#d93025"),
        # 图例：两个色块说明哪条是谁（无 rect，用文字 + 颜色名）
        f'<text x="{x1 + 6}" y="{y0 - 10}" fill="#1f6feb">— 参考</text>',
        f'<text x="{x1 + 6}" y="{y0 + 4}" fill="#d93025">— 练习</text>',
        f'<text x="8" y="{height - 24}">{html.escape(base)}</text>',
    ]
    if len(reference.values) != len(practice.values):
        parts.append(
            f'<!-- 两侧点数不等（{len(reference.values)} vs {len(practice.values)}），'
            f'各画各的，不拉伸 -->')
    parts.append("</svg>")
    return "".join(parts)


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
    # ★ 下面三处原为 assert：缺 path / 键名不对 / path 不是非空字符串时，
    #   AssertionError 会穿过 do_POST 的两个 except 落到 500「internal error」。
    #   而这三种都是**用户输入不合法**，内核已给了明确说法
    #   （「命令载荷键名或数量不符合契约」），不该以服务端故障的形式出现。
    #   改抛 HarmonicaError，让 do_POST 走 400 那条可读路径。
    if not isinstance(payload, dict):
        raise HarmonicaError(
            ErrorCode.INTERNAL_ERROR,
            f"{COMMAND_LABELS[kind]} 需要一个 path 字段（音频路径）",
        )
    if set(payload.keys()) != {"path"}:
        raise HarmonicaError(
            ErrorCode.INTERNAL_ERROR,
            f"{COMMAND_LABELS[kind]} 的载荷只接受 path 键，"
            f"实得 {sorted(payload.keys())}",
        )
    path = payload["path"]
    if not isinstance(path, str) or not path.strip() or "\x00" in path:
        raise HarmonicaError(
            ErrorCode.INTERNAL_ERROR,
            f"{COMMAND_LABELS[kind]} 的 path 必须是非空字符串",
        )
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

        def _respond(
            self, code: int, body: str, content_type: str = _HTML_CONTENT_TYPE
        ) -> None:
            """写一个响应（锁外取 `_PAGE`，不在响应期持锁）。

            `content_type` 只在只读 JSON 端点处不同；★ 默认仍是 HTML，
            ★ 所以首页与命令响应的行为【逐字节不变】。
            """
            raw = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/dataset":
                # ★ 只读端点：★ 浏览器读不到文件系统，★ 所以数据集清单
                #   必须由进程侧交给页面。★ 与首页同属 do_GET 的既有分流，
                #   不是新机制；★ 只 GET，不接受任何参数、不改变任何状态。
                self._respond(200, _dataset_json(), content_type="application/json")
                return
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
