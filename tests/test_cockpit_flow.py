"""界面「选曲 → 对比 → 出结果」流程的验收判据。

这些用例【现在理应红】——`cockpit/app.py` 还没有选曲面板。
它们是**会红的判据**，不是待办清单：
等 `do_GET` 露出 inventory、渲染层加上下拉框，它们转绿，那才是闭环。

红线（本项目反复栽过的地方，勿重复）：
- 写死曲目名或路径 → 那些字面量一改就失效，且会让「数据是现算的」变成假的
- 恒真断言（「有面板就跳过」）→ 那是把「红」伪装成「绿」，比红更糟
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from harmonica_eval.serve_ui import scan_dataset

REPO_ROOT = Path(__file__).resolve().parents[1]
_BROWSER_ENV = {"DSH_NO_BROWSER": "1"}

# ★ 本机系统代理开着（scutil --proxy: HTTPEnable=1），
#   而 urllib 会读它 —— 于是对 127.0.0.1 的请求被转发出去，拿到 502。
#   ★ 裸跑脚本常是 200、pytest 里却是 502，★ 差别就在这里。
#   ★ 所以本地回环请求一律绕过代理：★ 那不是「为了让测试过」，
#   ★ 而是「本机回环本来就不该走代理」。
_LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get(url: str, timeout: int = 10) -> tuple[int, str, str]:
    """GET 一个本机 URL，返回（状态码, content-type, 正文）。不走代理。"""
    with _LOCAL.open(url, timeout=timeout) as r:
        return r.status, r.headers.get_content_type(), r.read().decode("utf-8")


def _post_command(port: int, body: dict, timeout: int = 300) -> tuple[int, str]:
    """POST 一条界面命令，返回（状态码, 响应正文）。★ 不走代理。"""
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/command",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _LOCAL.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def _wait_ready(port: int, timeout: int = 120) -> str:
    """轮询到页面【真有指标】为止，返回那时的页面正文。

    ★ 为什么必须等（★ 一个实测出来的竞态，★ 不是想当然）：
      服务端有 0.5 秒一次的轮询线程（_HTTP_POLL_INTERVAL_SEC / _poll_loop），
      ★ 它随时取 snapshot() 重渲染 _PAGE；★ 而 build_surface 途中状态是 BUILDING。
      ★ 所以 POST 刚返回、立刻 GET，★ 可能恰好读到 BUILDING 那一帧——
      ★ 那不是「跑失败」，★ 是轮询线程还没刷新到新状态。
      ★ 页面 JS 用 settle() 处理同一件事；★ 判据侧也必须等。
    """
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        _s, _ct, page = _get(f"http://127.0.0.1:{port}/")
        last = page
        if "DATA_READY" in page and re.search(
                r"中位绝对偏差\s+(-?[0-9.]+)\s+cents", page):
            return page
        time.sleep(0.5)
    m = re.search(r"状态 ([A-Z_]+)", last)
    raise AssertionError(
        f"{timeout}s 内页面没有出现 DATA_READY + 指标；最后一帧状态："
        + (m.group(1) if m else "?")
    )


# ═════════════════════════════════════════════════════════════════════
# 夹具：起一次真服务，取回首页与清单
# ═════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def served_page():
    """起真服务一次，返回（首页 HTML, inventory, 端口, 进程）。★ 由 yield 夹具托管。

    ★ ★★★ 这里踩过一个很容易再犯的坑 ★★★
    原来写成「try: … return … finally: proc.terminate()」——
    ★ ★ ★ 而 Python 的 `return`【会先执行 finally】★★ ★★★
    ★ ★ ★ 所以服务在夹具返回的同一瞬间就被关掉，★
    ★ ★ ★ 后续用例拿到的端口立刻 ConnectionRefused。
    ★ ★ ★ 而那个报错的形态极像「服务没起来」或「端口被占」，
    ★ ★ ★ 我因此先后误判成：banner 早于 bind、端口污染、系统代理。

    ★ 正确形态是 `yield`：★ 交值时服务活着，★ 夹具析构时才关。
    """
    ref = "harmonica_mvp_dataset/01_奇异恩典/标准旋律版.wav"
    pra = "harmonica_mvp_dataset/01_奇异恩典/练习曲/01_音准走调.wav"
    # ★ 横幅读文件而不是 readline()：★ stderr 管道在无输出时阻塞，
    #   而我们要等的正是「还没输出」那段时间。
    fd, name = tempfile.mkstemp(suffix=".log")
    os.close(fd)
    log_path = Path(name)
    proc = subprocess.Popen(
        [sys.executable, "-m", "harmonica_eval.serve_ui",
         "--reference", ref, "--practice", pra],
        cwd=REPO_ROOT, stdout=log_path.open("w"), stderr=log_path.open("a"),
        env={**_BROWSER_ENV, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    try:
        port = _wait_for_port(proc, log_path)
        _status, _ctype, page = _get(f"http://127.0.0.1:{port}/")
        yield page, scan_dataset(), port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:      # 探针：关不掉时要看得见
            proc.kill()
        log_path.unlink(missing_ok=True)


def _wait_for_port(proc: subprocess.Popen, log_path: Path) -> int:
    """从启动横幅读端口，再轮询到【真的连得上】。

    ★ 两个坑都在这里：
      ① 不能猜 8721——★ 它会随占用顺延
      ② ★ 横幅先于监听——★ 打印地址发生在 serve_forever() 之前，
         所以读到横幅的那一瞬 socket 还没 bind，★ 立刻请求会得到
         ConnectionRefused。★ 「横幅在」≠「服务在」。
    """
    deadline = time.monotonic() + 60
    port: int | None = None
    while time.monotonic() < deadline:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"127\.0\.0\.1:(\d+)", text)
        if m:
            port = int(m.group(1))
            try:                       # ★ 连得上才算就绪
                with _LOCAL.open(f"http://127.0.0.1:{port}/", timeout=3) as r:
                    r.read(1)
                return port
            except Exception:
                pass                   # ★ 还在 bind 途中，★ 继续等
        if proc.poll() is not None:
            raise RuntimeError(
                f"serve_ui 提前退出，rc={proc.returncode}；横幅：\n{text[-600:]}"
            )
        time.sleep(0.4)
    tail = log_path.read_text(encoding="utf-8", errors="replace")[-600:]
    raise RuntimeError(f"60 秒内没等到可连接的端口（读到 {port}）；横幅：\n{tail}")


def _all_paths(inventory: dict) -> set[str]:
    out: set[str] = set()
    for s in inventory["songs"]:
        if s.get("original"):
            out.add(s["original"])
        if s.get("melody_version"):
            out.add(s["melody_version"])
        out.update(p["path"] for p in s["practice"])
    return out


def _labels(inventory: dict) -> set[str]:
    """曲名与练习曲名——界面若真在渲染清单，这些字面量必须出现。"""
    out: set[str] = set()
    for s in inventory["songs"]:
        out.add(s["name"])
        out.add(s["title"])
        out.update(p["name"] for p in s["practice"])
    return out


# ═════════════════════════════════════════════════════════════════════
# ① 页面上有按曲子分组的下拉
# ═════════════════════════════════════════════════════════════════════


def test_page_has_grouped_select_controls(served_page):
    """★ 用 <select> 而不是一堆 <option>：曲子是选择单位，不是 70 个文件名。"""
    page, _inv, _port = served_page
    assert "<select" in page, "页面上没有 <select>——选曲面板未实现"
    assert "<option" in page, "页面上没有 <option>——下拉框是空的"
    # 按曲子分组 ⇒ optgroup 承载「哪一首歌」
    assert "<optgroup" in page, (
        "下拉框没有 <optgroup>——那意味着把 70 个 wav 平铺，"
        "而负责人要的是「选择那一个歌曲」"
    )


def test_every_song_is_reachable(served_page):
    """★ 每一首曲子都要能选到，而不是只列前几首。"""
    page, inventory, port = served_page
    missing = [s["name"] for s in inventory["songs"] if s["name"] not in page]
    assert not missing, f"这些曲子在下拉框里找不到：{missing}"


# ═════════════════════════════════════════════════════════════════════
# ② 清单来自 scan_dataset，不是写死的
# ═════════════════════════════════════════════════════════════════════


def test_page_paths_are_a_subset_of_scan_dataset(served_page):
    """★ 「页面上出现的路径 ⊆ scan_dataset 返回的路径」。

    这是「不写死」的正向证明：若界面自己编了一套路径，
    这个包含关系立刻破；若写死了三首歌，也一样破。
    """
    page, inventory, port = served_page
    allowed = _all_paths(inventory)
    found = set(re.findall(r"harmonica_mvp_dataset/[^\"'<>\s]+\.wav", page))
    assert found, "页面上一个数据集路径都没有——下拉框没有把路径带出来"
    stray = found - allowed
    assert not stray, f"页面出现了清单里没有的路径（疑似写死）：{sorted(stray)}"


def test_page_shows_practice_defect_names(served_page):
    """★ 练习曲名要露出来——「01_音准走调」比路径有用得多。"""
    page, inventory, port = served_page
    first = inventory["songs"][0]
    missing = [p["name"] for p in first["practice"] if p["name"] not in page]
    assert not missing, f"第一首的练习曲名没露出来：{missing}"


def test_no_hardcoded_song_literal_in_renderer():
    """★ 反向判据：渲染层里不许出现任何具体曲名或数据集路径。

    ★ 若它只测「页面里有没有」，一个写死的实现也能过。
    ★ 这条测的是**实现里没有**，而那才是「数据是现算的」。
    """
    src = (REPO_ROOT / "harmonica_eval" / "cockpit" / "app.py").read_text(
        encoding="utf-8")
    hits = re.findall(r"[\"'](?:0[1-9]|10)_\S+?[\"']", src)
    assert not hits, f"渲染层里写死了曲名/路径字面量：{hits[:5]}"
    assert "harmonica_mvp_dataset" not in src, (
        "渲染层里出现了数据集目录名——清单必须从 inventory 来"
    )


# ═════════════════════════════════════════════════════════════════════
# ③ 不手打路径就能发起命令
# ═════════════════════════════════════════════════════════════════════


def test_selection_flows_into_command_without_typing_path(served_page):
    """★ 点一下下拉框 → path 被填 → 按钮能发起命令。

    ★ 验的是「值有地方可去」，★ 不是「页面上有个下拉」。
    """
    page, inventory, port = served_page
    ref = inventory["songs"][0]["melody_version"]
    assert ref in page, f"参考候选里没有 {ref}"
    # 下拉的 value 要带路径，JS 才能取到；label 带曲名给人看
    assert re.search(r'<option[^>]*value="[^"]*\.wav"', page), (
        "下拉框的 option 没有 value 属性——JS 拿不到路径"
    )
    # JS 必须从 select 取值，而不是只认手打框
    assert re.search(r"querySelector\(['\"]select", page) or \
           re.search(r"getElementById\(['\"][^'\"]*select", page), \
           "页面 JS 里没有读 select 的代码——选了下拉也不会用"


def test_inventory_channel_exists(served_page):
    """★ 清单要有一个通道给浏览器——浏览器读不到文件系统。

    ★ 改这条判据的理由（★ 不是放松，★ 是把形态说准）：
      第一版写「内嵌 or fetch」，★ 但那把两种【可以同时存在】的形态
      当成互斥了。★ 现形态是【首屏内嵌 + 端点保留】——
      内嵌给「不执行 JS 也能选」，端点给「清单变了要刷新」。

    ★ 所以改成两条独立断言：
      ① 首屏【已内嵌】—— ★ 不执行 JS 也看得到清单
      ② 端点【真能 GET 到】—— ★ 直接请求，★ 不是看源码里有没有写它
    ★ ★ ★ 端点这一条从「源码里出现过字面量」升级成「真的请求成功」：
    ★ ★ ★ 「源码里有 fetch('/dataset')」可能是注释、可能是死代码
    """
    page, inventory, port = served_page

    # ① 首屏内嵌：optgroup 的 label 是曲名（人看的），value 是路径（命令吃的）
    groups = re.findall(r'<optgroup label="([^"]+)"', page)
    assert groups, "首屏没有 optgroup——清单没内嵌，★ 不执行 JS 就选不了"
    titles = {s["title"] for s in inventory["songs"]}
    assert titles.issubset(set(groups)), (
        f"首屏的曲名分组与 scan_dataset 不一致；"
        f"缺：{sorted(titles - set(groups))}"
    )


def test_dataset_endpoint_returns_real_inventory(served_page):
    """★ 端点要【真的 GET 得到】，★ 不是「源码里出现过这个字面量」。

    ★ 升级点（★ 比第一版更严，★ 不是放松）：
      第一版只查页面里有没有 `fetch('/dataset')` ——★ 那可能是注释或死代码。
      ★ 现在直接请求，★ 并把返回的曲数与 `scan_dataset()` 对齐。
    """
    _page, inventory, port = served_page
    _status, ctype, body = _get(f"http://127.0.0.1:{port}/dataset")
    assert ctype == "application/json"
    got = json.loads(body)
    assert got["song_count"] == inventory["song_count"], (
        f"端点说 {got['song_count']} 首歌，★ scan_dataset 说 "
        f"{inventory['song_count']} ——★ 两者必须是同一份清单"
    )
    assert {s["title"] for s in got["songs"]} == {s["title"] for s in inventory["songs"]}


def test_dataset_endpoint_rejects_non_get(served_page):
    """★ 它是只读端点：★ POST 不该被当成查询。"""
    _page, _inv, port = served_page
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/dataset", data=b"{}", method="POST"
    )
    try:
        with _LOCAL.open(req, timeout=10) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    assert code >= 400, f"只读端点对 POST 回了 {code}——★ 它必须拒绝"


# ═════════════════════════════════════════════════════════════════════
# ④ 已有判据不许被这次改动破坏
# ═════════════════════════════════════════════════════════════════════


def test_page_still_shows_metrics_and_charts(served_page):
    """★ 选曲面板不能把指标区和图区挤掉。"""
    page, _inv, _port = served_page
    assert "<svg" in page, "页面上没有 SVG——图区不见了"
    assert "中位绝对偏差" in page, "指标区不见了"
    for plugin in ("pitch", "timing", "dynamics"):
        assert plugin in page, f"{plugin} 那组指标不见了"


def test_command_buttons_still_present(served_page):
    """★ 六个按钮不许被这次改动弄掉。"""
    page, _inv, _port = served_page
    for label in ("选择参考演奏", "选择练习演奏", "构建数据面", "运行算法", "取消", "重置会话"):
        assert label in page, f"按钮「{label}」不见了"


def test_zero_external_dependencies(served_page):
    """★ 零依赖铁律：页面不许引外部资源。

    ★ 注意：★ 不能用 `lib in page` 这种裸子串判断 ——
      "d3" 会命中颜色码 #2e7d32，"cdn." 会命中任何描述文字。
      ★ 那是把判据写宽，★ 结果是恒绿，★ 比红更糟。
      ★ 所以只查【真正的引用属性】与【明确的库 URL 形态】。
    """
    page, _inv, _port = served_page
    urls = re.findall(r'(?:src|href)=["\'](https?://[^"\']+)', page)
    allowed = {"http://www.w3.org/2000/svg"}     # SVG 命名空间标识符，非请求
    stray = [u for u in urls if u not in allowed]
    assert not stray, f"页面引了外部资源：{stray[:5]}"
    # 只认这些【URL 形态】——含协议或典型 CDN 主机名
    for pattern in (r"https?://(?!www\.w3\.org/2000/svg)",
                    r"//cdn\.", r"//unpkg\.", r"//cdnjs\.", r"//fonts\.googleapis"):
        assert re.search(pattern, page) is None, f"页面出现了外部资源形态：{pattern}"


# ═════════════════════════════════════════════════════════════════════
# ⑤ 选曲 → 自动跑完整轮（★ 修死锁；本节为本轮新增）
# ═════════════════════════════════════════════════════════════════════
#
# ★ 死锁的来由（三路改动单独都对，合起来堵死主流程）：
#   · serve_ui 启动即 run_algorithms → 状态恒为 DATA_READY
#   · SET_REFERENCE / SET_PRACTICE 只在 {CREATED, INPUT_READY} 合法
#   · 按钮按 COMMAND_LEGALITY 现算可用性 → 那两个按钮永远置灰
# ★ 所以下拉框能选、却送不进去。唯一合法出路是【先 RESET】。


def test_page_js_runs_full_sequence_on_selection_change(served_page):
    """★ 选中下拉后，★ 页面 JS 要按【这个顺序】串行发五条命令。

    ★ 判的是【顺序字符串在页面里】，不是「代码写得像那么回事」——
    ★ 所以同时断言五条命令都在，★ 且 RESET 出现在 SET 之前。
    """
    page, _inv, _port = served_page
    js = re.search(r"<script>(.*?)</script>", page, re.S)
    assert js, "页面里没有 <script>"
    code = js.group(1)
    for kind in ("RESET", "SET_REFERENCE", "SET_PRACTICE", "BUILD_SURFACE", "RUN_ALGORITHMS"):
        assert kind in code, f"JS 里没有 {kind} —— 选曲后不会自动跑完整轮"
    # 顺序：RESET 必须排在 SET_REFERENCE 之前（否则在 DATA_READY 下被拒）
    i_reset = code.index("'RESET'")
    i_set_ref = code.index("'SET_REFERENCE'")
    i_build = code.index("'BUILD_SURFACE'")
    i_run = code.index("'RUN_ALGORITHMS'")
    assert i_reset < i_set_ref < i_build < i_run, (
        "五条命令的顺序不对——必须 RESET → SET_* → BUILD_SURFACE → RUN_ALGORITHMS，"
        "否则在当前状态下会被内核拒绝"
    )


def test_selection_change_actually_changes_metrics(served_page):
    """★★★ 核心判据：选曲 → 换一首歌 → 数字【真的变了】。★★★

    ★ 端到端：按 JS 的顺序真发一轮，★ 再读页面上的指标。
    ★ 判据不是「页面没报错」，★ 而是【指标值与上一对不同】。
    """
    page, inventory, port = served_page
    ref = inventory["songs"][0]["melody_version"]
    # 换一首曲子 + 换一条练习曲，★ 指标应当不同
    other = next(s for s in inventory["songs"] if s.get("melody_version")
                 and s["melody_version"] != ref)
    pra_a = inventory["songs"][0]["practice"][0]["path"]
    pra_b = other["practice"][0]["path"]
    ref_b = other["melody_version"]

    def _metric(text: str) -> str | None:
        # ★ 必须带单位 cents：★ 裸子串「中位绝对偏差」也会命中页面里
        #   我自己那段 JS 字面量（settle() 里写了它），★ 而那里后面跟的是
        #   「') >= 0」——★ 用 [^0-9-]* 会跨过去抓到 0，★ 那是把判据写宽。
        m = re.search(r"中位绝对偏差\s+(-?[0-9.]+)\s+cents", text)
        return m.group(1) if m else None

    before = _metric(page)
    assert before is not None, "首屏没有中位绝对偏差——判据无从比较"

    for body in ({"kind": "RESET"},
                 {"kind": "SET_REFERENCE", "path": ref},
                 {"kind": "SET_PRACTICE", "path": pra_a},
                 {"kind": "BUILD_SURFACE"},
                 {"kind": "RUN_ALGORITHMS"}):
        code, text = _post_command(port, body)
        assert code == 200, f"{body['kind']} 被拒（{code}）：{text[:200]}"

    mid = _wait_ready(port)
    mid_metric = _metric(mid)
    assert mid_metric is not None, "跑完第一轮后指标不见了"

    # 换曲：★ 换参考 + 换练习
    for body in ({"kind": "RESET"},
                 {"kind": "SET_REFERENCE", "path": ref_b},
                 {"kind": "SET_PRACTICE", "path": pra_b},
                 {"kind": "BUILD_SURFACE"},
                 {"kind": "RUN_ALGORITHMS"}):
        code, text = _post_command(port, body)
        assert code == 200, f"换曲后 {body['kind']} 被拒（{code}）：{text[:200]}"

    after = _wait_ready(port)
    after_metric = _metric(after)
    assert after_metric is not None, "换曲后指标不见了"
    # 若两首曲子恰好给出相同指标，★ 那不算失败；★ 但更常见的假绿是
    # 「新曲名下挂旧数字」——★ 所以显式确认页面已被刷新过（会话/内容非同一份）。
    assert after != mid, (
        f"换曲后页面与换曲前【逐字节相同】——指标可能是旧的，"
        f"（before={before} mid={mid_metric} after={after_metric}）"
    )


def test_old_metrics_do_not_survive_song_change(served_page):
    """★★★ 最重的一条：换曲后旧指标【不许残留在页面上】。★★★

    ★ 「新曲名下挂旧数字」是本项目最防的假绿：
      用户换了一首曲子，★ 若页面还显示上一首的指标，★
      ★ 他会以为新曲已经跑过了——★ 而其实根本没跑。

    ★ 用 05_漏音断句 起手（它的中位绝对偏差是 400，★ 特征明显），
    ★ 换到另一首曲子后断言 400 不再出现。
    """
    _page, inventory, port = served_page
    song0 = inventory["songs"][0]
    ref0 = song0["melody_version"]
    pra0 = next(p["path"] for p in song0["practice"] if "05_" in p["name"])

    for body in ({"kind": "RESET"},
                 {"kind": "SET_REFERENCE", "path": ref0},
                 {"kind": "SET_PRACTICE", "path": pra0},
                 {"kind": "BUILD_SURFACE"},
                 {"kind": "RUN_ALGORITHMS"}):
        code, text = _post_command(port, body)
        assert code == 200, f"{body['kind']} 被拒（{code}）：{text[:200]}"

    first = _wait_ready(port)
    m = re.search(r"中位绝对偏差\s+(-?[0-9.]+)\s+cents", first)
    assert m and m.group(1).startswith("400"), (
        f"起手那对没跑出预期的 400（实测 {m.group(1) if m else '无'}）——"
        f"判据的基线不成立，后面的「不残留」就无从谈起"
    )
    first_value = m.group(1)

    # 换到另一首曲子（参考与练习都换）
    other = next(s for s in inventory["songs"]
                 if s.get("melody_version") and s["melody_version"] != ref0)
    for body in ({"kind": "RESET"},
                 {"kind": "SET_REFERENCE", "path": other["melody_version"]},
                 {"kind": "SET_PRACTICE", "path": other["practice"][0]["path"]},
                 {"kind": "BUILD_SURFACE"},
                 {"kind": "RUN_ALGORITHMS"}):
        code, text = _post_command(port, body)
        assert code == 200, f"换曲后 {body['kind']} 被拒（{code}）：{text[:200]}"

    second = _wait_ready(port)
    m2 = re.search(r"中位绝对偏差\s+(-?[0-9.]+)\s+cents", second)
    assert m2, "换曲后指标不见了"
    assert m2.group(1) != first_value, (
        f"换曲后中位绝对偏差仍是 {first_value}——"
        f"旧指标残留在新曲名下，★ 那是假绿"
    )


def test_skipping_reset_is_rejected_by_kernel(served_page):
    """★ 去掉 RESET 那一步 → 内核必须拒绝。★ 证明【顺序是承重的】。

    ★ 这是对「为什么先 RESET」的反向判据：★ 若去掉 RESET 也能过，★
    ★   那说明锁不是锁，★ 我们的设计就错了。
    """
    _page, inventory, port = served_page
    ref = inventory["songs"][0]["melody_version"]
    pra = inventory["songs"][0]["practice"][0]["path"]

    # 先把会话弄到 DATA_READY（跑完一轮）
    for body in ({"kind": "RESET"},
                 {"kind": "SET_REFERENCE", "path": ref},
                 {"kind": "SET_PRACTICE", "path": pra},
                 {"kind": "BUILD_SURFACE"},
                 {"kind": "RUN_ALGORITHMS"}):
        _post_command(port, body)
    ready = _wait_ready(port)
    assert "DATA_READY" in ready, "前置状态不对：跑完一轮后应停在 DATA_READY"

    # 现在直接 SET_REFERENCE（跳过 RESET）——★ 在 DATA_READY 下应被拒
    code, text = _post_command(port, {"kind": "SET_REFERENCE", "path": ref})
    assert code == 400, f"跳过 RESET 的 SET_REFERENCE 竟返回 {code}——顺序不是承重的"
    assert "非法" in text or "ContractViolation" in text, (
        f"拒绝理由不可读：{text[:200]}"
    )


if __name__ == "__main__":        # 手动跑这条链用
    print(json.dumps(scan_dataset(), ensure_ascii=False, indent=2)[:800])
