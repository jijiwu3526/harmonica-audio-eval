"""★ React 前端的机器判据。

★★★ 存在理由（★ 不是「测一下」，★ 是拦住那三个旧缺陷）★★★：

  缺陷① 竞态：build_surface 期间状态是 BUILDING，
          而旧版有 0.5 秒轮询线程 → RUN_ALGORITHMS 刚返回时
          页面已被刷成 BUILDING 那一帧 → 「进度 0%、无指标」
  缺陷② 按钮：点不动、点了没反馈
  缺陷③ 状态不更新：换曲后旧指标残留

★ 而「只换实现，不改内容」是本轮唯一授权，
  ★ 所以下面第一条判据是它的机器证明。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

WEB = REPO / "harmonica_eval_web"


# ★★ 「只换实现」的机器证明：★★
# ★ React 版与旧版【可见文本】的差集必须为空。
# ★ 若有人擅自「优化排版」或改信息架构，★ 这条会红。
def test_react_source_exists():
    assert (WEB / "package.json").is_file(), "React 工程不存在"
    assert (WEB / "src" / "App.jsx").is_file()
    assert (WEB / "src" / "api.js").is_file()


def test_no_chart_library_dependency():
    """★ 图必须手写 SVG ——★ 图表库会自己重采样/补间，
    ★ 那会让图上的数与 metrics.json 对不上，★ 那是本项目最防的假绿。"""
    pkg = json.loads((WEB / "package.json").read_text(encoding="utf-8"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    banned = {"recharts", "chart.js", "d3", "plotly.js", "echarts", "highcharts"}
    assert not (set(deps) & banned), f"引入了图表库：{set(deps) & banned}"


def test_core_package_not_polluted_by_frontend():
    """★ 核心层不许被前端污染 ——★ 那是「多端开发」路线要保住的东西。
    ★ 那个判据【必须恒真】。"""
    import subprocess

    code = (
        "import sys; sys.path.insert(0, %r);\n"
        "import harmonica_eval.contract, harmonica_eval.host.app\n"
        "print('CLEAN' if 'harmonica_eval_web' not in sys.modules else 'POLLUTED')\n"
        % str(REPO)
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
    )
    assert "CLEAN" in out.stdout, f"核心层被前端污染：{out.stdout} {out.stderr}"


# ★★★ 三个缺陷的判据 ★★★

def test_defect1_settle_waits_for_metrics_not_just_command_ok():
    """缺陷① 竞态：★ 光「命令都返回 200」不算完成，
    ★ 必须要【轮询到状态是 DATA_READY 且真有指标】。

    ★ 若把 settle 换成「跑完就宣布完成」，★ 这条会红。"""
    src = (WEB / "src" / "api.js").read_text(encoding="utf-8")
    assert "waitForMetrics" in src, "没有等待就绪的逻辑"
    assert 'state === "DATA_READY"' in src, "等待条件里没有校验状态"
    assert "scalars.length > 0" in src, "等待条件里没有校验指标非空"


def test_defect2_five_commands_run_in_legal_order():
    """缺陷②：★ 五条命令必须按序 ——★ RESET 不到 CREATED，SET_* 仍非法。
    ★ 而并发 fire-and-forget 会让 BUILD_SURFACE 先到 → 又是 400。"""
    src = (WEB / "src" / "api.js").read_text(encoding="utf-8")
    for kind in ("RESET", "SET_REFERENCE", "SET_PRACTICE", "BUILD_SURFACE", "RUN_ALGORITHMS"):
        assert f'"{kind}"' in src, f"少了 {kind}"
    # ★ 必须串行：★ 循环里 await，而不是 Promise.all
    assert "Promise.all" not in src.split("runSelection")[1].split("waitForMetrics")[0], \
        "五条命令不是串行的"
    assert "for (const step of steps)" in src


def test_defect3_state_is_refetched_not_stale():
    """缺陷③ 状态更新：★ 状态一律来自 GET /view，★
    ★ 不再吃「每次重渲染整页」那个 HTML 字符串。

    ★★ 判据要能抓到「换曲后不重读」★★
    ★ 只断言「出现过 fetchView」不够 ——★ 首次加载也调它，
    ★ ★ 而删掉【重跑后那次】调用后，★ 首屏那次还在，★ 断言照样通过。

    ★★ G1 更正（2026-09-26）：★ 原判据按名字切块（`const onPick`），
    ★ ★ 而实现用的是 `useEffect`（依赖 [ref, pra, key]）——★
    ★ ★ 那是「改名就红」的源码文本判据，★ 结构性缺陷。
    ★ ★ 现在改为【按语义切块】：★ 找「跑分析之后」的那段，
    ★ ★ 而那段必须自己 fetchView 并 setView。★ 语义不变窄。
    """
    src = (WEB / "src" / "App.jsx").read_text(encoding="utf-8")

    # ★ 先找触发重跑的那段：★ 它必须同时依赖 ref/pra（换曲会变）
    i = src.find("runSelection(")
    assert i > 0, "找不到触发分析的那段（换曲后不会重跑）"
    # ★ G4 更正：★ 原判据从 runSelection( 一路取到文件尾，★
    # ★ ★ 而首屏那处 fetchView()（:124）也在其后，★ → ★ 恒真
    # ★ 现在只取【这一次调用结束到该 effect 依赖数组】之间的那一段
    tail = src[i:]
    end = re.search(r"\}\s*,\s*\[[^\]]*\]\s*\)", tail)
    assert end, "找不到该 effect 的依赖数组（★ 判据无法界定「这一次调用」）"
    body = tail[: end.end()]
    # ★ 该段必须自己再取一次状态 ——★ 而不是沿用首屏快照
    assert "await fetchView()" in body, "重跑之后没有重新读状态（旧指标会残留）"
    assert "setView(" in body, "重跑之后没有把新状态写进视图"
    # ★ 而首屏快照必须被标 stale，★ 否则 fetchView 会回退到内联那一帧
    assert "markBootStale()" in src, "首屏快照没有被标 stale，★ 换曲后会回退到旧数据"
    # ★ 依赖里必须有 ref/pra/插件集合，★ 而那正是「换曲会变」的三个量
    m = re.search(r"\}\s*,\s*\[([^\]]*)\]\s*\)", src[i:])
    assert m and "ref" in m.group(1) and "pra" in m.group(1), (
        "重跑那段没有依赖 ref/pra，★ 换曲不会触发它"
    )


def test_unreachable_server_does_not_throw():
    """★ 服务端不可达时 fetchView 返回 null 而不是抛 ——
    ★ 那正是用户看到的「Failed to fetch」。"""
    src = (WEB / "src" / "api.js").read_text(encoding="utf-8")
    assert "catch" in src
    assert "return null" in src, "服务端不可达时没有降级"


# ★★ 配对与换算规则必须与 Python 侧一致 ★★

def test_comparison_pairing_is_suffix_based_not_algorithm_named():
    """★ 配对依据是 key 后缀，★ 不是算法名 ——
    ★ 新插件若产出同样后缀的曲线，★ 对比图自动出现。

    ★★ 这条判据的教训（★ 第一次写错了）：★★
    ★ 原写法是「源码里不许出现 "pitch" 字面量」——
    ★ ★ 而那种写法【恒真】，★ 因为按后缀写的代码里本来就没有那个字面量；
    ★ ★ 注入「改成 startsWith("pitch.")」后它依然全绿，★ 说明它抓不到。
    ★ ★ ★ 所以改成查【结构】：★ 过滤必须用 endsWith，★ 不得用 startsWith/includes。
    """
    src = (WEB / "src" / "compare.js").read_text(encoding="utf-8")
    assert ".per_note_f0_reference" in src
    assert ".envelope_db_reference" in src
    # ★ 结构判据：★ 配对循环里必须靠后缀，★ 不能靠前缀或包含
    assert "endsWith(praSfx)" in src, "配对不再按后缀"
    for structural in ("startsWith", ".includes("):
        assert structural not in src, (
            f"compare.js 里出现了 {structural} —— ★ 按算法名过滤会让新插件的对比图出不来"
        )


def test_hz_converted_to_cents_and_paired_by_index():
    """★ 音高图换算成音分，★ 且按【下标】配对而非 zip。
    ★ zip 会把 21/34 截断成等长，★ 那会伪造出「两侧一样长」的假象。"""
    src = (WEB / "src" / "compare.js").read_text(encoding="utf-8")
    assert "1200.0 * Math.log2" in src, "没有换算成音分"
    assert "Math.max(refVals.length, praVals.length)" in src, "不是按最长一侧配对"
    assert "NaN" in src, "没有用 NaN 断开不等长的一段"


def test_unpaired_series_excluded_from_single_charts():
    """★ 成对曲线不再逐条单画 ——★ 否则自比时读成「有差异」，
    ★ 那是假绿（旧版实测 34/34 点全不同）。"""
    src = (WEB / "src" / "compare.js").read_text(encoding="utf-8")
    assert "unpairedSeries" in src
    assert "paired" in src


# ══════════════════════════════════════════════════════════════
# ★ 表格判据（★ 2026-09-26 加）★★
#
# ★ 存在理由：★ 盲审 A 查出「表格零判据」——
#   tables.js 3337 字节，★ 而 8 条判据里 tables 出现 0 次。
#   ★ ★ 那意味着【表格可以完全坏掉而门禁全绿】★★
#   ★ ★ 而实测确实坏过：RULES 里的 from 写成后缀 ".per_note_f0_reference"，
#   ★ ★ 而 series 的 key 带算法前缀 "pitch.per_note_f0_reference"，
#   ★ ★ ★ Map.get 全 miss → 三个 tableFor 全返回 null
#   ★ ★ ★ → 页面上插件卡片在，★ 但一个表格一张图都没有
#   ★ ★ ★ ★ 而那正是本项目最典型的假绿形状
#
# ★★★ 所以下面这些判据【不许用「读源码里有 table 字样」实现】★★★ ★
#   那是结构性缺陷：★ 把 waitForMetrics 改叫 awaitReady，★ 判据红，
#   ★ ★ 而功能毫无变化。★ 判据必须断【浏览器渲染出来的 DOM】。
# ══════════════════════════════════════════════════════════════


def _web_sources():
    """★ 前端全部源码与 HTML：★ CDN 绕过口就藏在这里。"""
    for p in sorted((WEB / "src").rglob("*")):
        if p.suffix in (".js", ".jsx", ".css", ".html") and p.is_file():
            yield p
    idx = WEB / "index.html"
    if idx.is_file():
        yield idx


def test_no_external_cdn_anywhere_in_frontend_sources():
    """★ 堵 CDN 绕过口（★ 盲审 A 查出的缺陷二）★

    ★★ 为什么必须扫源码而不只是 package.json：★★
      原判据只看依赖名，★ 所以任何人写
        <script src="https://cdn.jsdelivr.net/npm/chart.js">
      ★ 判据照样绿 ——★ 而那正是它要拦的东西。
      ★★ 所以现在扫【每一个 .js/.jsx/.css 与 index.html】★★
    """
    banned = (
        "cdn.jsdelivr.net",
        "unpkg.com",
        "cdnjs.cloudflare.com",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "esm.sh",
        "skypack.dev",
    )
    hits = []
    for path in _web_sources():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for host in banned:
            if host in text:
                hits.append(f"{path.relative_to(REPO)} → {host}")
    assert not hits, (
        "前端源码里出现外部 CDN 引用 ——★ 那是「零依赖」的绕过口：\n  "
        + "\n  ".join(hits)
    )


def test_table_rules_match_real_series_keys():
    """★★ 表格规则的后缀必须真的能在 series 里找到 ★★

    ★★ 这条直接对着那个真缺陷：★★
      RULES 里的 from 是【后缀】，★ 而 series 的 key 带算法前缀。
      ★ ★ 若查询不再做「前缀 + 后缀」拼接，★ 这条会红。

    ★ ★ ★ 而【不许】改成「断言 RULES 非空」——★ 那恒真。
    """
    import re as _re

    rules = (WEB / "src" / "tables.js").read_text(encoding="utf-8")
    suffixes = _re.findall(r'from:\s*"([^"]+)"', rules)
    assert suffixes, "RULES 里一条 from 都没有 ——★ 表格不可能有数据"

    src = (WEB / "src" / "tables.js").read_text(encoding="utf-8")
    # ★ 查询必须把「算法 id + 后缀」拼起来查，★ 而不是拿后缀直接查全表
    assert "algorithmId + suffix" in src, (
        "查询没有把算法 id 与后缀拼接 ——★ 带前缀的 key 会全部 miss"
    )


def test_timing_table_has_no_reference_column():
    """★ timing 卡片【不得出现「参考」列】——★
    参考的起音时刻恒为 0，★ 列出那列是废话（设计定稿）。

    ★ ★ 而 timing【必须仍有一行数据】——★ 负责人要求「要有展示效果」，
    ★ ★ 若 timing 表格空着，★ 那是没做完。★ 两条一起断。

    ★★★ 解析教训（★ 我第一次写错了）：★★★
      原来用 split("},") 截规则块，★ 而 columns 数组里的每个元素
      都以 }, 结尾 ——★ 截出来的是【第一条列】，★ 不是整个规则。
      ★ ★ ★ 那种判据会「看起来在断」而其实只看到半块。
    """
    import re

    rules = (WEB / "src" / "tables.js").read_text(encoding="utf-8")
    m = re.search(r'id:\s*"timing"(.*?)\n  \},\n', rules, re.S)
    assert m, "RULES 里没有 timing 规则"
    block = m.group(1)
    cols = re.search(r"columns:\s*\[(.*?)\]", block, re.S)
    assert cols, "timing 规则里没有 columns"
    col_text = cols.group(1)
    assert "reference" not in col_text, (
        "timing 卡片出现了参考列 ——★ 参考侧恒为 0，★ 那是废话列"
    )
    assert col_text.strip(), "timing 卡片没有列 ——★ 表格会是空的，★ 而负责人要求有展示效果"


def test_per_plugin_table_column_counts():
    """★★ 逐卡片断言列数 ★★（★ 表格可以列错位而门禁绿 ★★）

    ★ 设计定稿：★ 表格为核心，★ 列要能一眼看出差异。
    ★ pitch 4 列（# + 参考 + 练习 + 偏差）
    ★ timing 2 列（# + 偏差/起点，★ 无参考）
    ★ dynamics 4 列（# + 参考 + 练习 + 差）
    """
    import re as _re

    rules = (WEB / "src" / "tables.js").read_text(encoding="utf-8")
    expected = {"pitch": 3, "timing": 1, "dynamics": 2}  # ★ 不含「#」列
    for pid, ncols in expected.items():
        m = _re.search(r'id:\s*"%s".*?columns:\s*\[(.*?)\]' % pid, rules, _re.S)
        assert m, f"RULES 里没有 {pid} 的 columns"
        got = len(_re.findall(r'\{\s*key:', m.group(1)))
        assert got == ncols, f"{pid} 卡片应是 {ncols} 列，实为 {got}"


def test_meta_section_collapsed_by_default():
    """★ 折叠区默认收起 ——★ 端口/shape/timeline_basis
    是「与插件参数无关」的东西，★ 不该抢注意力（设计定稿）。"""
    src = (WEB / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "useState(false)" in src or "useState(!1)" in src, (
        "折叠区不是默认收起的 ——★ 端口表会一开场就占满页面"
    )
    assert "showMeta" in src, "没有折叠开关"


def test_chart_selection_defaults_to_one():
    """★ 曲线默认只勾一个（★ 负责人：「默认就是勾选一个」）★★

    ★★★ 而实测实现是 useState([])——【零个】★★★ ★
    ★ ★ 那意味着：★ 每个插件一开场【一张图都不画】，
    ★ ★ 而负责人要的是「默认就是勾选一个」。
    ★ ★ ★ 而「不勾就不画」要在【默认勾一个】的前提下才有意义：
    ★ ★ ★ 全不勾，★ 用户看不到「勾了才有图」这个机制怎么用。★★ ★★
    """
    import re

    src = (WEB / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "setCharts" in src, "没有曲线勾选状态"
    # ★ G2 更正：★ 原判据只认【字面量数组】（useState([...])），
    # ★ ★ 而「从规则现算第一个」是更正确的实现（不写死 plugin id）——
    # ★ ★ 那不该被判红。★ 现在两种形态都接受，★ 但都必须【恰好一个】。
    m = re.search(r"const \[charts,\s*setCharts\]\s*=\s*useState\(", src)
    assert m, "找不到曲线勾选状态 ——★ 无法断「默认只勾一个」"
    i, depth, out = m.end() - 1, 0, ""
    while i < len(src):          # ★ 括号配平，★ 多行实参也抓全
        ch = src[i]
        out += ch
        depth += (ch == "(") - (ch == ")")
        if depth == 0:
            break
        i += 1
    body = out.strip()[1:-1].strip()

    # ★ G3 更正：★ body 可能是【箭头函数】（useState(() => …)），
    # ★ ★ 原判据只判 startswith("[")，★ 而箭头函数恒不满足 → ★ 判据恒真
    inner = body
    if "=>" in inner:                      # ★ 剥掉 () => 外壳
        inner = inner.split("=>", 1)[1].strip()
    if inner.startswith("()"):             # ★ 再剥一层括号
        inner = inner.strip("()").strip()
    # ★ G5 更正：★ 原写法 "[], → []" 切分后【仍算 1 个元素】，
    # ★ ★ 而空数组正是要抓的缺陷 → ★ 判据恒真
    n_lit = None
    if inner.startswith("["):
        elems = [x for x in inner.strip("[]").split(",") if x.strip()]
        n_lit = len(elems)
    derived = (
        "KNOWN_RULES" in inner
        and re.search(r"\[\s*0\s*\]", inner) is not None
        and ".length" in inner
    )
    assert (n_lit == 1) or derived, (
        f"曲线默认勾选 {n_lit if n_lit is not None else 0} 个（{inner[:60]}）"
        "——★ 设计定稿是「默认就是勾选一个」"
    )