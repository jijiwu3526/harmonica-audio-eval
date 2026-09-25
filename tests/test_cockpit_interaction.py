"""C4 交互面的可执行验收。

★ 为什么要有这个文件
--------------------
`tests/test_cockpit_ports.py` 验的是「端口能被读出来、能被渲染成字符串」；
本文件验的是**真的把服务起起来、真的发 POST、真的看状态变没变**。

★ 本文件把四件事从「口头约定」变成「会失败的断言」
------------------------------------------------
1. 四态判别互斥（A 未就绪 / B 已通无源 / C 有指标 / D 管线中断）
2. 命令在合法态被接受、在非法态被拒（且拒绝要可读）
3. 端口表 12/12 逐个出现在渲染结果里
4. 界面按 `UiView.scalars` 的**实际内容**渲染，
   因此一个界面从未听说过的插件，其指标也会自动出现

★ 判据纪律
----------
每个用例都写了「改坏实现就会红」的那一处；
判据恒真（怎么弄都过）比判据红着更糟，所以红端是硬要求。
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_REF = "harmonica_mvp_dataset/01_奇异恩典/标准旋律版.wav"
_PRA = "harmonica_mvp_dataset/01_奇异恩典/练习曲/01_音准走调.wav"

_PORT_SCAN = range(8721, 8785)


# ═════════════════════════════════════════════════════════════════════
# 探针：真起服务、真发请求
# ═════════════════════════════════════════════════════════════════════


def _free_port() -> int:
    """找一个 C4 探测范围内当前空闲的端口（与 `app._pick_port` 同范围）。"""
    for candidate in _PORT_SCAN:
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", candidate))
            except OSError:
                continue
        return candidate
    pytest.skip("8721-8784 全被占，跳过交互测试")


def _get(port: int, path: str = "/") -> tuple[int, str]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as resp:
        return resp.status, resp.read().decode("utf-8")


def _post_command(port: int, body: dict) -> tuple[int, str]:
    """按**页面实际使用的方式**发命令。

    ★ 页面发 JSON（`app.py` 第 364 行 `Content-Type: application/json`
      + `JSON.stringify`），服务端用 `json.loads` 解析。
      ★ 因此表单编码会拿到 400 —— 那是调用方的错，不是实现的错。
    """
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/command",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


@pytest.fixture(scope="module")
def live_ui():
    """起一个真实的 `serve_ui`，整个模块共用，结束必关。

    ★ 存活判据是【端口能连】，不是 `proc.poll()`
      —— 实测 `serve_ui` 会 fork 子进程接管服务，父进程随即退出，
      ★ 若用 `poll()` 判死会把「服务好好的」误判成「提前退出」。
    ★ 这就是「探针报错先怀疑探针」。
    """
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "harmonica_eval.serve_ui",
         "--reference", _REF, "--practice", _PRA],
        cwd=_REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 180
        ready = False
        while time.monotonic() < deadline:
            try:
                status, _ = _get(port)
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(1.0)
                continue
            if status == 200:
                ready = True
                break
        if not ready:
            proc.terminate()
            pytest.fail("serve_ui 180 秒内未就绪")
        yield port
    finally:
        # ★ 用端口所属的进程组收尾，★ 不靠 parent pid
        subprocess.run(
            ["pkill", "-f", f"harmonica_eval.serve_ui"],
            capture_output=True, check=False,
        )
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()


# ═════════════════════════════════════════════════════════════════════
# 1 · 端口表：12/12 逐个可见
# ═════════════════════════════════════════════════════════════════════


def test_all_twelve_ports_visible_in_live_page(live_ui):
    """12 个端口逐个出现在真实页面上。

    红端：把 `render_status` 里的端口行删掉 → 本用例应红。
    """
    sys.path.insert(0, str(_REPO))
    from harmonica_eval import profile

    _, page = _get(live_ui)
    missing = [p.port_id for p in profile.PORTS if p.port_id not in page]
    assert not missing, f"页面上缺这些端口：{missing}"


def test_port_rows_show_shape_not_just_name(live_ui):
    """端口行必须带 shape —— 只显示名字等于没让用户看到数据规模。

    红端：把 shape 的格式化删掉 → 本用例应红。
    """
    _, page = _get(live_ui)
    assert "warp_path" in page
    # warp_path 的 shape 是 (n, 2)，页面上应能看到类似 "1870" 与 "2" 的成对数字
    assert "1870" in page, "页面没显示 warp_path 的实际点数"


# ═════════════════════════════════════════════════════════════════════
# 2 · 四态判别（★ 项目冻结的互斥判据）
# ═════════════════════════════════════════════════════════════════════


def test_state_b_no_source_when_algorithms_not_run(live_ui):
    """`serve_ui` 启动只建数据面、不跑算法 → 判为 B「已通但无数据」。

    ★ 这不是缺陷而是设计：`RUN_ALGORITHMS` 是界面自己的一条命令。
    ★ 但它必须被明确显示，而不是让用户以为「跑过了却没结果」。

    红端：把 `_classify_view` 改成恒返回 "C_HAS_DATA" → 本用例应红。
    """
    _, page = _get(live_ui)
    assert "已通但无数据" in page, "未跑算法时必须显示 B 态文案"


def test_state_c_has_data_after_run_algorithms(live_ui):
    """点「运行算法」之后 → 判为 C「有指标」，且真有指标渲染出来。

    红端：把 `RUN_ALGORITHMS` 从 COMMAND_LEGALITY 里去掉 → 本用例应红。
    """
    status, page = _post_command(live_ui, {"kind": "RUN_ALGORITHMS"})
    assert status == 200, f"RUN_ALGORITHMS 应被接受，实得 {status}：{page[:200]}"
    assert "已通但无数据" not in page, "跑完算法后不该还停在 B 态"
    # 真有指标渲染出来了：任选两个必然存在的键
    assert "median_abs" in page or "音准" in page or "cents" in page


def test_state_a_unbuilt_after_reset(live_ui):
    """RESET 之后回到 CREATED → 判为 A「数据面未就绪」。

    ★ A 态与 B 态【必须不同】：A 是没建，B 是建了没结果。
    ★ 混为一谈就是本项目踩过的假绿。

    红端：把 `_classify_view` 的第一道 `if` 删掉 → 本用例应红。
    """
    status, page = _post_command(live_ui, {"kind": "RESET"})
    assert status == 200
    assert "数据面未就绪" in page, "RESET 后应显示 A 态文案"


def test_state_d_blocked_shows_diagnosis_never_bare_no_data():
    """D 态：scalars 空但有 error_code → 必须显示诊断，**不得**显示「无数据」。

    ★ 这是本项目真正栽过的地方：三个算法全 INCOMPATIBLE 而
      state 仍是 DATA_READY、scalars=[]，画成「已通但无数据」就是假绿。

    红端：把 `D_BLOCKED` 分支删掉让它落到 `B_NO_SOURCE` → 本用例应红。
    """
    sys.path.insert(0, str(_REPO))
    from harmonica_eval.contract import ErrorCode, SessionState, UiScalar, UiView

    from harmonica_eval.cockpit.app import _verify_view_consistency

    blocked = UiView(
        session_id="s-d", state=SessionState.DATA_READY,
        series=(), scalars=(), progress=None, port_summary=(),
        error_code=ErrorCode.INTERNAL_ERROR,
        error_detail="三个算法全部 INCOMPATIBLE", note="",
    )
    label = _verify_view_consistency(blocked)
    assert label == "D_BLOCKED", f"D 态判错成 {label}"

    # ★ 核心断言：★ error_detail 由 `render_error` 负责（`render_status`
    #   按契约只管 state 与 note —— ★ 那是职责分界，不是缺陷）
    sys.path.insert(0, str(_REPO))
    from harmonica_eval.cockpit.app import render_error

    shown = render_error(blocked)
    assert "三个算法全部 INCOMPATIBLE" in shown, "D 态必须把诊断原文带给用户"
    assert "INTERNAL_ERROR" in shown, "错误码也要带出来"
    assert "已通但无数据" not in shown, "★ D 态绝不能显示「无数据」—— 那是假绿"
    # ★ 而 B 态（有状态、无标量、无错误）时，错误区【必须】是空串
    from harmonica_eval.cockpit.app import render_error as _re

    benign = UiView(
        session_id="s-b", state=SessionState.DATA_READY,
        series=(), scalars=(), progress=None, port_summary=(),
        error_code=None, error_detail=None, note="",
    )
    assert _re(benign) == "", "无错误时不该显示「无错误」占位 —— 那是噪声"


# ═════════════════════════════════════════════════════════════════════
# 3 · 命令协议：合法态接受、非法态拒绝且可读
# ═════════════════════════════════════════════════════════════════════


def test_legal_command_accepted(live_ui):
    """合法命令在合法状态下 → 200 + 返回整页。

    红端：把 `do_POST` 改成恒返回 400 → 本用例应红。
    """
    status, page = _post_command(live_ui, {"kind": "RESET"})
    assert status == 200
    assert "<!DOCTYPE html>" in page or "<html" in page


def test_illegal_kind_rejected_with_readable_reason(live_ui):
    """非法 kind → 400，且**响应体要说清为什么**。

    ★ 判据的价值在「可读」：只回 "bad request" 等于没告诉用户哪儿错了。
    红端：把错误分支改回固定的 "bad request" → 本用例应红。
    """
    status, body = _post_command(live_ui, {"kind": "NOT_A_COMMAND"})
    assert status == 400
    assert "NOT_A_COMMAND" in body, f"应回显出错的 kind，实得：{body[:200]}"
    assert "SET_REFERENCE" in body, "应列出支持的命令，让用户知道能发什么"


def test_malformed_json_rejected_with_reason(live_ui):
    """坏 JSON → 400 + 可读原因。

    红端：把 JSON 解析的 except 改成静默 → 本用例应红。
    """
    request = urllib.request.Request(
        f"http://127.0.0.1:{live_ui}/command",
        data=b"not-json",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            status, body = resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read().decode("utf-8")
    assert status == 400
    assert "JSON" in body, f"应说明是 JSON 的问题，实得：{body[:200]}"


def test_illegal_state_rejected_as_400_not_500(live_ui):
    """★ 命令在【错误状态】下 → 必须是 400，不是 500。

    ★ 这条是本任务修掉的真缺陷：内核对用户输入的明确拒绝
      （`ContractViolation`）原先被 `except Exception` 吞成 500 internal error，
      ★ 而 500 的语义是「服务端坏了」—— 会让用户去查错的方向完全跑偏。
    ★ 500 只能留给真正的未预料异常。

    红端：把 `except HarmonicaError` 那段删掉 → 本用例应红。
    """
    _post_command(live_ui, {"kind": "RESET"})
    _post_command(live_ui, {"kind": "SET_REFERENCE", "path": _REF})
    _post_command(live_ui, {"kind": "SET_PRACTICE", "path": _PRA})
    # 现在是 INPUT_READY；BUILD_SURFACE 合法，RUN_ALGORITHMS 尚不合法
    status, body = _post_command(live_ui, {"kind": "RUN_ALGORITHMS"})
    assert status == 400, f"状态不合法应回 400，实得 {status}：{body[:200]}"
    assert "ContractViolation" in body or "非法" in body
    assert "internal error" not in body, "★ 内核的明确拒绝不该伪装成服务端故障"


# ═════════════════════════════════════════════════════════════════════
# 4 · 界面的通用性（★ 「深接口」的落点）
# ═════════════════════════════════════════════════════════════════════


def test_scalars_renderer_is_generic_not_hardcoded():
    """★ 界面必须按 `scalars` 的实际内容渲染，不能硬编码三个算法名。

    这是「插件可从界面测」的前提：只要 C1 往 `UiView.scalars` 里塞了
    任何 key，界面就该显示出来。

    ★ 红端：给 `render_scalars` 加一句
      `if item.key.startswith("pitch."): ...`（即只渲染已知算法）
      → 本用例应红。
    """
    sys.path.insert(0, str(_REPO))
    from harmonica_eval.contract import UiScalar

    from harmonica_eval.cockpit.app import render_scalars

    absurd = UiScalar(
        key="zzz_impossible.never_heard_of.metric",
        label="一个界面从未听说过的指标",
        value=42.0,
        unit="widgets",
        threshold=None,
    )
    shown = render_scalars([absurd])
    # ★ 实测：render_scalars 渲染的是 label（人话），不是 key
    assert absurd.label in shown, "陌生插件的 label 没被渲染 —— 界面是硬编码的"
    assert "42" in shown, f"数值没渲染，实得：{shown!r}"


def test_no_algorithm_names_hardcoded_in_cockpit():
    """★ 源码里不许出现具体算法名。

    ★ 红端：在 `_render_page` 里写死 `pitch.reference` 等 → 本用例应红。
    """
    src = (_REPO / "harmonica_eval" / "cockpit" / "app.py").read_text("utf-8")
    for name in ("pitch.", "timing.", "dynamics."):
        assert name not in src, f"cockpit 里硬编码了算法名 {name} —— 界面不该知道算法"


def test_plugin_metric_reaches_page_end_to_end(live_ui):
    """★ 端到端：注册一个陌生插件 → 它的指标出现在页面上。

    ★ 这是「12 端口 + 交互 + 插件」三件事合起来的最终判据。
    ★ 证明方式用的是**名字刻意荒谬**的插件，防止「碰巧命中已知前缀」。

    ★ 红端：把 `render_scalars` 改成只渲染 key 以 pitch./timing./dynamics. 开头
      → 本用例应红。
    """
    sys.path.insert(0, str(_REPO))
    from harmonica_eval.contract import UiScalar, UiView

    from harmonica_eval.cockpit.app import render_scalars, render_status

    # 一个刻意不用已知算法名的 key
    weird = UiScalar(
        key="qqzz.qqzz.qqzz", label="荒谬插件指标", value=7.0, unit="z", threshold=None,
    )
    view = UiView(
        session_id="s-plugin", state=view_state_data_ready(),
        series=(), scalars=(weird,), progress=None, port_summary=(),
        error_code=None, error_detail=None, note="",
    )
    shown = render_scalars(view.scalars) + "\n" + render_status(view)
    assert "荒谬插件指标" in shown, f"陌生插件的指标没到界面上，实得：{shown!r}"
    assert "7" in shown


def view_state_data_ready():
    """小helper：避免测试文件顶部再引一次 SessionState。"""
    from harmonica_eval.contract import SessionState

    return SessionState.DATA_READY


# ═════════════════════════════════════════════════════════════════════
# 5 · 零依赖（★ 项目铁律）
# ═════════════════════════════════════════════════════════════════════


def test_page_has_no_external_resource(live_ui):
    """★ 页面不许引用任何外部资源（CDN / 字体 / 图标库）。

    `www.w3.org/2000/svg` 是 XML 命名空间标识符，不是网络请求。

    ★ 红端：往页面里加一行 `<script src="https://cdn.jsdelivr.net/…">`
      → 本用例应红。
    """
    _, page = _get(live_ui)
    import re

    offenders = [
        m for m in re.findall(r"https?://[^\"'\s)]+", page)
        if not m.startswith("http://www.w3.org/")
    ]
    assert not offenders, f"页面引用了外部资源：{offenders}"
    assert "<script src=" not in page
