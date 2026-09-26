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


def _get_view(port: int, timeout: int = 10) -> dict:
    """GET /view，拿结构化状态快照。不走代理。

    ★ 为什么加这个（★ 2026-09-26）：
      React 版首屏是 <div id="root">，★ 指标由浏览器执行 JS 后从 /view 拉，
      ★ 所以【页面 HTML 里本来就没有指标文本】。
      ★ 而「指标算出来了」这件事本身没变，★ 变的是【它出现在哪个可观测面】。
    ★ ★ ★ 所以判据改读 /view，★ 断的仍是同一件事：
           state == DATA_READY 且 scalars 里真有 pitch.median_abs_cents
      ★ ★ ★ 而【不是】改去查 React 源码里有那行字——★ 那是把判据写宽
    """
    _s, _ct, body = _get(f"http://127.0.0.1:{port}/view", timeout=timeout)
    return json.loads(body)


def _scalar_value(view: dict, key: str) -> float | None:
    """从 /view 快照里取某个标量的值；不在则 None。"""
    for item in view.get("scalars", []):
        if item.get("key") == key:
            return float(item["value"])
    return None


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

    ★ ★ 2026-09-26：就绪判据改读 /view 的 scalars。
      改前用正则 r"中位绝对偏差\\s+(-?[0-9.]+)\\s+cents" 扫【页面正文】。
      ★ ★ ★ 而 React 版首屏是空 div，★ 那条正则【永远匹配不上】——
      ★ ★ ★ 于是夹具超时，★ 连带把 8 条本可照常的判据一起拖红。
      ★ ★ ★ ★ 而「指标算出来了」这件事没变，★ 只是它不再出现在首屏 HTML 里。
      ★ ★ ★ ★ 断的语义一字未变：DATA_READY 且 pitch.median_abs_cents 有值。
    """
    deadline = time.monotonic() + timeout
    last_state = "?"
    while time.monotonic() < deadline:
        try:
            view = _get_view(port)
        except (OSError, ValueError):
            time.sleep(0.5)
            continue
        last_state = view.get("state", "?")
        pitch = _scalar_value(view, "pitch.median_abs_cents")
        if view.get("state") == "DATA_READY" and pitch is not None:
            return f"状态 DATA_READY · pitch.median_abs_cents={pitch}"
        time.sleep(0.5)
    raise AssertionError(
        f"{timeout}s 内 /view 没有出现 DATA_READY + 指标；最后一帧状态："
        f"{last_state}"
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
    # ★ ★ 2026-09-26：_port 现在【真的要用上了】—— 断的语义是
    #   「选曲面板没把指标区和图区挤掉」。而 React 版把两者都搬到了
    #   /view 的 scalars 与 series 里，★ 那才是 React 版真正呈现它们的地方。
    #   ★ ★★ 改读 /view，★ 断的仍是同一件事：
    #   ★ ★★ 三个插件的指标都还在（不是只剩 pitch），★ 且有曲线可画。
    #   ★ ★ ★ 而不是「页面 HTML 里有 <svg>」——★ 那在 React 版里恒为 0。
    view = _get_view(_port)
    groups = {s["key"].split(".")[0] for s in view.get("scalars", [])}
    for plugin in ("pitch", "timing", "dynamics"):
        assert plugin in groups, f"{plugin} 那组指标不见了（/view 实得 {sorted(groups)}）"
    # 图区：★ 至少要有两条成对曲线，★ 否则「有曲线可画」这句就不成立
    pairs = {}
    for s in view.get("series", []):
        pairs.setdefault(s["key"], 0)
    assert any("_reference" in k for k in pairs), f"没有参考侧曲线：{sorted(pairs)}"
    assert any("_practice" in k for k in pairs), f"没有练习侧曲线：{sorted(pairs)}"


def test_command_buttons_still_present(served_page):
    """★ 六个按钮不许被这次改动弄掉。"""
    page, _inv, _port = served_page
    # ★ ★ 2026-09-26：本判据【故意保持红】，★ 记录原因，★ 防止后人"顺手修好"★★
    #
    #   ★ 它断的语义是「六个意图都在页面上」。★ 而其中三个已被负责人明令删除：
    #       「选择参考演奏」「选择练习演奏」「构建数据面」
    #   ★ ★ ★ 删它们的理由（2026-09-25）：★ 启动后状态恒为 DATA_READY，
    #   ★ ★ ★ 而 SET_REFERENCE / SET_PRACTICE 只在 {CREATED, INPUT_READY} 合法、
    #   ★ ★ ★ BUILD_SURFACE 只在 {INPUT_READY} 合法 ——★ 那三个按钮【永远置灰】。
    #   ★ ★ ★ 负责人原话：「你这个自己都报错，★ 你让我怎么搞啊」。
    #   ★ ★ ★ 能力没丢：★ 下拉框选中后由 runSelection 依次发
    #   ★ ★ ★ RESET → SET_REFERENCE → SET_PRACTICE → BUILD_SURFACE → RUN_ALGORITHMS。
    #   ★ ★ ★ ★★ 所以那三个命令仍在被发，★ 只是不再由按钮呈现。
    #
    #   ★ ★★ 为什么不把它改绿（★ 两条路都更糟）★★
    #     甲 把断言改成「那三个不许在」→ ★ 那是把判据的语义【整个倒过来】，
    #   ★   ★ 以后任何人重新加回那三个按钮，★ 这条判据都不会响
    #     乙 改成从 /view 或 React 源码里找那六个字样 → ★ 那是查源码文本，
    #   ★   ★ 本项目反复踩的坑：★ 把 waitForMetrics 改叫 awaitReady，
    #   ★   ★ 判据就红了，★ 而功能毫无变化
    #   ★ ★ ★★ 两条都违反「改形态不许变窄」。★ 所以保留红，★ 并在此说明。
    #
    #   ★ 解封条件：★ 负责人裁定那三个按钮【应当回到界面上】，
    #   ★ ★ ★ ★ 或者本判据被重写成断「六种意图都有合法触发路径」——
    #   ★ ★ ★ ★ 而后者才是它本来该断的（★ 那五个 kind 全部可达）。
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

    # ★ ★ 2026-09-26：指标改从 /view 读（★ 而不是扫页面正文）
    #   语义一字未改：「换曲后指标与上一对不同」才是本判据要断的事。
    #   ★ 而页面正文在 React 版里【没有指标文本】，★ 那是可观测面变了。
    #   ★ ★ ★ 而原来的 _metric(text) 那个「扫正文取数字」的局部函数已删：
    #   ★ ★ ★ 它扫的那段文本在 React 版里恒为空，★ 留着只会诱导后人误用
    #   ★ ★ ★ ——★ 「页面上有指标」已不是本判据要断的事，★ 「/view 里有」才是。
    before = _scalar_value(_get_view(port), "pitch.median_abs_cents")
    assert before is not None, "/view 里没有 pitch.median_abs_cents——判据无从比较"

    for body in ({"kind": "RESET"},
                 {"kind": "SET_REFERENCE", "path": ref},
                 {"kind": "SET_PRACTICE", "path": pra_a},
                 {"kind": "BUILD_SURFACE"},
                 {"kind": "RUN_ALGORITHMS"}):
        code, text = _post_command(port, body)
        assert code == 200, f"{body['kind']} 被拒（{code}）：{text[:200]}"

    mid_view = _get_view(port)
    mid = _scalar_value(mid_view, "pitch.median_abs_cents")
    assert mid is not None, "跑完第一轮后指标不见了"

    # 换曲：★ 换参考 + 换练习
    for body in ({"kind": "RESET"},
                 {"kind": "SET_REFERENCE", "path": ref_b},
                 {"kind": "SET_PRACTICE", "path": pra_b},
                 {"kind": "BUILD_SURFACE"},
                 {"kind": "RUN_ALGORITHMS"}):
        code, text = _post_command(port, body)
        assert code == 200, f"换曲后 {body['kind']} 被拒（{code}）：{text[:200]}"

    _wait_ready(port)
    after_view = _get_view(port)
    after = _scalar_value(after_view, "pitch.median_abs_cents")
    assert after is not None, "换曲后指标不见了"
    # ★ ★ 2026-09-26：这一条原判据比的是【两段页面文本是否逐字节不同】。
    #   ★ 而「换了曲子」本就应当产出不同的指标，★ 所以这才是它真正要断的语义。
    #   ★ ★ ★ 改后【更严】：★ 现在断的是「scalars 里的数值真的不同」，
    #   ★ ★ ★ 而不是「两段文本不完全一样」——★ 后者可能被无关注册符号差异满足。
    #   ★ 而「同一份快照原样返回」这种假绿，★ 新的写法照样会红。
    assert after != mid, (
        f"换曲后指标与换曲前【完全相同】——指标可能是旧的，"
        f"（mid={mid} after={after}）"
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

    _wait_ready(port)
    # ★ ★ 2026-09-26：改读 /view（★ 原来是扫页面正文里的指标文本）。
    #   断的语义一字未改：起手必须是 400，★ 否则「不残留」无从谈起。
    #   ★ 而 base-line 那个 startswith("400") 刻意保留 —— ★ 它断的是
    #   ★ 「05_漏音断句 确实跑出了它特征性的 400」，★ 而不是在比两个任意值。
    first_value = _scalar_value(_get_view(port), "pitch.median_abs_cents")
    assert first_value is not None and str(first_value).startswith("400"), (
        f"起手那对没跑出预期的 400（实测 {first_value}）——"
        f"判据的基线不成立，后面的「不残留」就无从谈起"
    )

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

    _wait_ready(port)
    second_value = _scalar_value(_get_view(port), "pitch.median_abs_cents")
    assert second_value is not None, "换曲后指标不见了"
    assert second_value != first_value, (
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
