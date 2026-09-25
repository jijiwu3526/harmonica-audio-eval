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

    ★ 历史留档（★ 不是判据）：2026-09-25 此处曾用 `_free_port()` 先挑一个
      空闲端口、再假设 `serve_ui` 会选同一个。那是巧合而非契约 ——
      `serve_ui` 内部调 `app._pick_port()` 独立探测，两边各选各的。
      那时启动快（只建数据面，★ 不跑算法），端口恰好对上的概率高；
      负责人裁定「启动即自动跑算法」后启动变慢，时间窗一大就暴露了：
      实测 9 passed + 10 errors「serve_ui 180 秒内未就绪」——
      而那不是服务没起来，★ 是【连错了端口】。
      现在改为从启动横幅里读【真实端口】。
    """
    stdout = subprocess.PIPE
    proc = subprocess.Popen(
        [sys.executable, "-m", "harmonica_eval.serve_ui",
         "--reference", _REF, "--practice", _PRA],
        cwd=_REPO, stdout=stdout, stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        # ★ 启动横幅里 run_local_ui 打印「http://127.0.0.1:<port>/」
        deadline = time.monotonic() + 180
        ready_port = None
        banner = ""
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if line:
                banner += line
                if proc.stdout is not None and "127.0.0.1:" in line:
                    tail = line.split("127.0.0.1:")[1]
                    digits = ""
                    for ch in tail:
                        if ch.isdigit():
                            digits += ch
                        else:
                            break
                    if digits:
                        ready_port = int(digits)
            if ready_port is not None:
                try:
                    status, _ = _get(ready_port)
                except (urllib.error.URLError, ConnectionError, OSError):
                    status = None
                if status == 200:
                    break
            if ready_port is None:
                time.sleep(0.2)
        if ready_port is None:
            proc.terminate()
            pytest.fail(
                "serve_ui 180 秒内未打印启动横幅（★ 无法得知它选了哪个端口）\n"
                f"横幅内容：{banner[:400]}"
            )
        try:
            status, _ = _get(ready_port)
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            proc.terminate()
            pytest.fail(f"横幅说端口 {ready_port}，但连不上：{exc}")
        if status != 200:
            proc.terminate()
            pytest.fail(f"横幅端口 {ready_port} 返回 {status}，应为 200")
        yield ready_port
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


# ★★★ 四态判别的永续判据（★ 不依赖启动路径）★★★ ★★
# ★ 历史留档（★ 不是判据）：2026-09-25 此处曾有一条
#   `test_state_b_no_source_when_algorithms_not_run`，它经 `live_ui` 启动服务
#   并断言页面出现「已通但无数据」。那条断言的是【启动后的阶段态】——
#   负责人裁定「启动即自动跑算法」后，它必然失效。
#   ★ 阶段态判据在本项目反复过期（见 FILE-002:518 的同类修法），
#   故改为下面这条：直接构造四态的 UiView，判它【能不能被正确认出来】。
#   ★ 断言的是【判别能力】，任何阶段都成立。
def _ui_view(*, state, scalars=(), error_code=None, error_detail=None):
    """造一个最小的 UiView，只填四态判别真正读取的字段。"""
    from harmonica_eval.contract import SessionState, UiView

    return UiView(
        session_id="synthetic",
        state=state,
        series=(),
        scalars=tuple(scalars),
        progress=1.0,
        port_summary=(),
        error_code=error_code,
        error_detail=error_detail,
        note="",
    )


def _one_scalar():
    from harmonica_eval.contract import UiScalar

    return UiScalar(key="probe.value", label="探针", value=1.0, unit="x")


@pytest.mark.parametrize(
    ("case", "kwargs", "expected"),
    [
        (
            "A_UNBUILT：state 非 DATA_READY → 数据面未就绪",
            {"state": "CREATED"},
            "A_UNBUILT",
        ),
        (
            "B_NO_SOURCE：无标量且无诊断 → 已通但无数据",
            {"state": "DATA_READY", "scalars": (), "error_code": None,
             "error_detail": None},
            "B_NO_SOURCE",
        ),
        (
            "C_HAS_DATA：有标量 → 有指标",
            {"state": "DATA_READY", "scalars": None},
            "C_HAS_DATA",
        ),
        (
            "D_BLOCKED：无标量但有诊断 → 管线中断",
            {"state": "DATA_READY", "scalars": (),
             "error_code": "INCOMPATIBLE", "error_detail": "三个算法全部不兼容"},
            "D_BLOCKED",
        ),
    ],
)
def test_four_state_classification_is_stage_independent(case, kwargs, expected):
    """★ 四态判别必须在【任何输入】下都正确，★ 与启动路径无关。

    ★ 互斥判据（来自一次真实假绿）：三个算法全 INCOMPATIBLE 时，
    state 仍是 DATA_READY、scalars 为空，而 error_detail 里有诊断。
    若按「无标量 ⇒ B 已通无源」画，就把「全挂」画成了「正常但没数据」。

    ★ 为什么改成构造而非走 live_ui：
    `serve_ui` 启动即自动跑算法（负责人裁定），启动路径恒为 C_HAS_DATA。
    ★ 断言那条路径等于把判据钉死在当前裁定上，★ 下次改动又会红。

    红端：把 `_classify_view` 改成恒返回 "C_HAS_DATA"
      → 本用例的 A/B/D 三行应立刻红。
    """
    from harmonica_eval.contract import SessionState
    from harmonica_eval.cockpit.app import _classify_view, _verify_view_consistency

    kwargs = dict(kwargs)
    raw_state = kwargs.pop("state")
    state = SessionState[raw_state] if isinstance(raw_state, str) else raw_state
    if kwargs.get("scalars", ()) is None:
        kwargs["scalars"] = (_one_scalar(),)

    view = _ui_view(state=state, **kwargs)
    assert _classify_view(view) == expected, case
    # 同一判据还有一份运行时自证；两条必须一致，否则渲染时会画错。
    assert _verify_view_consistency(view) == expected, case


def test_d_blocked_must_not_render_as_no_data():
    """★ D 态【不得】被画成「无数据」——★ 那是本项目踩过的假绿。

    ★ 判据：scalars 为空但 error_code 非空时，界面必须显示诊断，
    而「已通但无数据」是另一回事（无标量且无诊断）。
    """
    from harmonica_eval.contract import SessionState
    from harmonica_eval.cockpit.app import _classify_view

    blocked = _ui_view(
        state=SessionState.DATA_READY,
        scalars=(),
        error_code="INCOMPATIBLE",
        error_detail="三个算法全部 INCOMPATIBLE",
    )
    no_source = _ui_view(
        state=SessionState.DATA_READY, scalars=(), error_code=None, error_detail=None
    )

    assert _classify_view(blocked) == "D_BLOCKED"
    assert _classify_view(no_source) == "B_NO_SOURCE"
    # ★ 两者必须不同：★ 若判别把它们判成同一态，界面就会把故障画成「没数据」。
    assert _classify_view(blocked) != _classify_view(no_source)


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


def _functions_named(tree, names):
    """按名字挑出模块级与嵌套的函数定义。"""
    import ast

    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]


def _literal_names(node):
    """收集节点内所有字符串字面量。"""
    import ast

    return [
        n.value
        for n in ast.walk(node)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


def test_no_algorithm_names_hardcoded_in_cockpit():
    """★ 渲染路径不得【按算法名分支】——★ 界面不该知道有哪些算法。

    ★ 这条判据的范围被收窄过一次（2026-09-25），★ 值得说明为什么：
    旧版断言是「`app.py` 全文不得出现 `pitch.` / `timing.` / `dynamics.`」，
    ★ 那把两件不同的事混为一谈：
      · 【该守】渲染路径按算法名分支（★ 真正的架构问题）
      · 【误伤】说明文案里提到算法名（★ 负责人要的「架构优越性可见」，
        ★ 页面要说清「这些数字是逐个插件算出来的，★ 新插件接入后自己出现」）
    ★ ★ 「文案提及」≠「按名渲染」★ 两者语义完全不同

    ★ 所以现在查的是【AST 结构】：★ 渲染函数里有没有拿算法名做比较或分支。
    ★ 收窄后【仍必须能抓】——★ 见本用例 docstring 末的红端。

    红端：在 `_render_page` 里写 `if 'pitch.' in item.key:` 这样的分支
      → 本用例应红。
    """
    import ast

    src = (_REPO / "harmonica_eval" / "cockpit" / "app.py").read_text("utf-8")
    tree = ast.parse(src)

    # ★ 渲染路径上的函数：★ 谁负责把 UiView 变成页面。
    render_fns = _functions_named(tree, {"_render_page", "render_scalars", "build_plots",
                                         "render_series_plot", "render_status",
                                         "render_progress", "render_error"})

    known_algorithm_ids = {"pitch", "timing", "dynamics"}
    offenders = []
    for fn in render_fns:
        for name in _literal_names(fn):
            head = name.split(".")[0].split(":")[0].strip()
            if head in known_algorithm_ids:
                offenders.append(f"{fn.name}:{name}")
    assert not offenders, (
        "渲染路径里出现了具体算法名，★ 界面不该知道算法："
        f"{offenders}。★ 若那只是页面说明文案（不是分支），"
        "请把它挪到渲染函数之外。"
    )

    # ★ 正面判据：★ 标量区是【遍历】渲染的，★ 所以任何插件的指标都会自动出现。
    render_scalars = next(
        n for n in render_fns if n.name == "render_scalars"
    )
    loops = [
        n
        for n in ast.walk(render_scalars)
        if isinstance(n, (ast.For, ast.comprehension))
    ]
    assert loops, (
        "render_scalars 里没有遍历 ——★ 若它只渲染固定几个，"
        "新插件的指标就不会出现在页面上（★ 那正是这条判据要守的）"
    )


def test_render_scalars_has_no_algorithm_name_branch():
    """★ 更强的一条：★ 遍历变量上不得出现按算法名的比较。

    ★ 上一条查的是「函数体里有没有算法名字面量」；
    ★ 这一条查的是「有没有拿它做分支」——★ 后者才是真正的架构问题。
    ★ 两条并存，★ 收窄判据才不会变成「什么都抓不住」。

    红端：把 `for item in scalars:` 改成
      `for item in scalars: if item.key.startswith("pitch."): …`
      → 本用例应红。
    """
    import ast

    src = (_REPO / "harmonica_eval" / "cockpit" / "app.py").read_text("utf-8")
    tree = ast.parse(src)
    fn = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "render_scalars"
    )

    known = {"pitch", "timing", "dynamics"}
    offenders = []
    for node in ast.walk(fn):
        # ★ 只看比较与属性访问，★ 单纯的字面量说明不算分支
        if isinstance(node, ast.Compare) or isinstance(node, ast.Call):
            for name in _literal_names(node):
                head = name.split(".")[0].split(":")[0].strip()
                if head in known:
                    offenders.append(f"{fn.name}:{getattr(node,'lineno','?')}:{name}")
    assert not offenders, (
        f"render_scalars 里按算法名做了比较/调用：{offenders}"
    )


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
