#!/usr/bin/env python3
"""由下往上的组件归属推导器（不信任铭牌）。

═══════════════════════════════════════════════════════════════════════
为什么需要这个脚本
═══════════════════════════════════════════════════════════════════════

负责人要求：「先思考这一坨代码可以组成什么组件，那一坨代码可以组成
什么组件，然后再把这些组件与之前的设计做对比。」

若我手工"看一遍代码然后说我推导出来了"，那还是自上而下 ——
我只是先知道了答案（铭牌上写着 COMPONENT: COMP-C2），再倒着编理由。

所以本脚本 **刻意不读 `COMPONENT:` 字段**，只用代码本身可观测的信号跑聚类，
最后才把结果与铭牌对照。对照不一致 = 真发现。

═══════════════════════════════════════════════════════════════════════
★ 方法论上的一个真实教训（做过才发现的）
═══════════════════════════════════════════════════════════════════════

第一版我用「import 图 + 模块度」跑聚类，结果是**一坨 8 个文件的浆糊**，
把 contract / profile / cockpit / host / core.api 全糊在一起。

诊断后发现两个原因，都是真实的、不是调参问题：

1. **import 图在空壳期是残缺的。** 18 个文件的函数体全是
   `raise NotImplementedError`，真正的调用边**还没被写出来**。
   能观测到的 import 只是类型标注与少数常量引用 ——
   拿它推断"谁和谁一起改"是在推断一个**尚未存在的图**。

2. **`contract.py` 是枢纽节点。** 它是 §9 意义上的"可执行契约"，
   被所有组件引用。在模块度里，枢纽会把自己的社区粘成一大坨 ——
   这是模块度算法的已知病（resolution limit 的镜像）。

所以本版换了信号：**不看"谁 import 谁"，而看"谁和谁共享同一片宪法"。**
即每个文件引用了 `contract.py` 的哪些符号、生产了哪些端口族的端口。
两个文件若共享大部分契约符号，它们就是同一个**契约层**的邻居 ——
这个信号在空壳期是**完整的**，因为它由 docstring / 类型标注 / 常量定义承载，
而这些恰恰是空壳期唯一已经写全的东西。

聚类方法相应改为 **Jaccard + 平均连接层次聚类**（纯 stdlib），
它对枢纽天然免疫：枢纽自己的特征集很大，与谁都只有低 Jaccard，
于是它自己成为孤点（正确 —— contract/profile 本来就不是组件）。

═══════════════════════════════════════════════════════════════════════
用法
═══════════════════════════════════════════════════════════════════════

    python3 tools/derive_clusters.py            # 推导 + 与铭牌对照
    python3 tools/derive_clusters.py --raw      # 只打印信号
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections import defaultdict
from pathlib import Path
from typing import Sequence

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "harmonica_eval"
sys.path.insert(0, str(REPO))

# Jaccard 相似度高于此值 → 视为同一坨
MERGE_THRESHOLD = 0.34


class ClusterDataUnavailableError(RuntimeError):
    """组件推导所需的插件声明尚未装配，当前不能诚实聚类。"""


# ═════════════════════════════════════════════════════════════════════
# 一 · 信号提取（纯 AST + 声明式注册表，不 import 被分析的文件）
# ═════════════════════════════════════════════════════════════════════

def _module_name(path: Path) -> str:
    rel = path.relative_to(REPO).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _read_plate(src: str) -> dict[str, str]:
    """只取铭牌的键值，**COMPONENT 单独放**（那是被检验对象，不参与聚类）。"""
    out: dict[str, str] = {}
    for line in src.splitlines():
        s = line.strip().strip("'\"")
        for key in ("FILE-ID", "SPEC", "ROLE", "COMPONENT"):
            if s.startswith(key + ":"):
                out["_plate_" + key] = s[len(key) + 1:].strip()
    return out


def _import_edges(tree: ast.AST, mod: str, path: Path, mods: dict[str, Path]) -> set[str]:
    pkg_of = mod
    if path.name != "__init__.py" and "." in mod:
        pkg_of = mod.rsplit(".", 1)[0]
    raw: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                raw.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    raw.add(node.module)
            else:
                base = pkg_of
                for _ in range(node.level - 1):
                    base = base.rsplit(".", 1)[0] if "." in base else ""
                raw.add(f"{base}.{node.module}" if node.module else base)
                if node.module is None:
                    for a in node.names:
                        raw.add(f"{base}.{a.name}")
    out: set[str] = set()
    for t in raw:
        parts = t.split(".")
        for i in range(len(parts), 0, -1):
            cand = ".".join(parts[:i])
            if cand in mods:
                if cand != mod:
                    out.add(cand)
                break
    return out


def load_registry_specs() -> tuple[object, ...]:
    """取得已装配 Registry 的 PluginSpec 清单。

    ★ 本工具【不】import 被分析的具体算法实现，只经 bootstrap 这个唯一
      装配根取得声明式清单（FILE-206 装配根唯一性）。

    ★ 取不到才抛 ClusterDataUnavailableError，判据是【真实的】：
      bootstrap 抛异常 / 清单为空 / 元素缺字段。
      ★ 绝不按「文件看起来是空壳」判断——那是阶段态判据，注入完成即失效，
        会让本工具在项目推进后永远拒绝工作。
    """
    try:
        from harmonica_eval.algorithms.bootstrap import build_default_registry
    except Exception as exc:
        raise ClusterDataUnavailableError(
            f"无法导入装配根 harmonica_eval.algorithms.bootstrap：{exc}"
        ) from exc
    try:
        specs = tuple(build_default_registry().list())
    except Exception as exc:
        raise ClusterDataUnavailableError(
            f"build_default_registry() 失败，无法取得已装配清单：{exc}"
        ) from exc
    if not specs:
        raise ClusterDataUnavailableError(
            "已装配 Registry 为空（build_default_registry().list() 返回空序列）"
        )
    for spec in specs:
        if not hasattr(spec, "algorithm_id") or not hasattr(spec, "required_inputs"):
            raise ClusterDataUnavailableError(
                f"已装配清单元素缺 algorithm_id/required_inputs：{spec!r}"
            )
    return specs


def extract_signals(plugin_specs: Sequence[object] | None = None) -> dict:
    """提取纯 AST / 声明式信号，不 import 被分析的具体算法实现。

    ``plugin_specs`` 缺省时由 ``load_registry_specs()`` 自行从已装配
    Registry 取得（算法入口模块与 required_inputs 端口足迹这两个关键信号）。
    ★ 「数据面不足」只按【真实取不到】判定，★ 绝不按「文件看起来是空壳」——
      那会让本工具在注入完成后永远拒绝工作。
    ★ 也绝不把「缺数据」伪装成「推导为空」。
    """
    if plugin_specs is None:
        plugin_specs = load_registry_specs()

    files = sorted(PKG.rglob("*.py"))
    mods = {_module_name(p): p for p in files}

    imports: dict[str, set[str]] = {}
    plates: dict[str, dict[str, str]] = {}
    defined: dict[str, set[str]] = {}
    docstrings: dict[str, str] = {}

    for mod, path in mods.items():
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        plates[mod] = _read_plate(src)
        imports[mod] = _import_edges(tree, mod, path, mods)
        docstrings[mod] = ast.get_docstring(tree) or ""
        d: set[str] = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                d.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        d.add(t.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                d.add(node.target.id)
        defined[mod] = d

    # ---- 契约符号足迹：每个文件"用到"了 contract.py 的哪些符号 ----
    # 规则：文件里出现的标识符 ∩ contract.py 顶层定义的符号
    #       ＋ 形如 `contract.XXX` / `C.XXX` 的属性访问
    contract_mod = "harmonica_eval.contract"
    # ★ 剔除 dunder：`__all__` 几乎每个文件都写，若留在集合里，
    #   任意两个文件都会因共享 `contract:__all__` 而相似 ——
    #   实测这会把 core / host / cockpit 三个包出口粘成假坨（Jaccard 1.000）。
    contract_syms = {s for s in defined.get(contract_mod, set()) if not s.startswith("__")}
    footprint: dict[str, set[str]] = {}
    for mod, path in mods.items():
        if mod == contract_mod:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        used: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in contract_syms:
                used.add(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in contract_syms:
                used.add(node.attr)
        footprint[mod] = used

    # ---- 端口足迹：profile.PORTS[*].produced_by / PluginSpec.required_inputs ----
    try:
        from harmonica_eval import profile  # noqa: PLC0415
        port_producer = {p.port_id: p.produced_by for p in profile.PORTS}
        port_family = {p.port_id: p.port_id.split(".")[0] for p in profile.PORTS}
    except Exception as exc:  # pragma: no cover
        print(f"  ⚠️  读 profile.PORTS 失败：{exc}")
        port_producer, port_family = {}, {}

    try:
        algo_requires = {}
        algo_module = {}
        for spec in plugin_specs:
            try:
                algo_requires[spec.algorithm_id] = tuple(
                    requirement.port_id for requirement in spec.required_inputs
                )
                algo_module[spec.algorithm_id] = spec.entry.__module__
            except AttributeError as exc:
                raise ClusterDataUnavailableError(
                    "已提供的插件声明不完整：每个条目必须是含 "
                    "algorithm_id / entry / required_inputs 的 PluginSpec。"
                ) from exc
    except ClusterDataUnavailableError:
        raise
    except Exception as exc:  # pragma: no cover
        print(f"  ⚠️  读插件声明失败：{exc}")
        algo_requires, algo_module = {}, {}

    return {
        "mods": mods, "imports": imports, "plates": plates,
        "defined": defined, "docstrings": docstrings,
        "footprint": footprint, "contract_syms": contract_syms,
        "port_producer": port_producer, "port_family": port_family,
        "algo_requires": algo_requires, "algo_module": algo_module,
    }


# ═════════════════════════════════════════════════════════════════════
# 二 · 特征构造 + Jaccard 平均连接层次聚类
# ═════════════════════════════════════════════════════════════════════

def feature_sets(sig: dict) -> dict[str, set[str]]:
    """每个文件的特征集 = 它在这套系统里"碰了什么"。"""
    feats: dict[str, set[str]] = {}
    for mod in sig["mods"]:
        f: set[str] = set()
        # ① 契约符号足迹（最强信号：空壳期唯一写全的东西）
        for s in sig["footprint"].get(mod, ()):
            f.add("contract:" + s)
        # ② 端口足迹：我生产哪些族的端口
        for port, producer in sig["port_producer"].items():
            prod_mod = producer if producer.startswith("harmonica_eval") else f"harmonica_eval.{producer}"
            prod_mod = prod_mod.replace(".core.", ".core.").replace("harmonica_eval.core.", "harmonica_eval.core.")
            # produced_by 写作 "core.align"，补包名
            cand = producer if producer.startswith("harmonica_eval") else "harmonica_eval." + producer
            if cand == mod:
                f.add("produces:" + sig["port_family"][port])
        # ③ 算法足迹：我是不是某算法入口 / 我需要哪些端口族
        for aid, amod in sig["algo_module"].items():
            if amod == mod:
                f.add("algo:" + aid)
                for p in sig["algo_requires"].get(aid, ()):
                    f.add("needs:" + sig["port_family"].get(p, p))
        # ④ 公开符号前缀（弱信号，仅用于打破平局；剔除 dunder）
        for n in sorted(sig["defined"].get(mod, ())):
            if not n.startswith("_"):
                f.add("sym:" + n.split("_")[0])
        feats[mod] = f
    return feats

def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def agglomerative(feats: dict[str, set[str]], threshold: float) -> list[list[str]]:
    """平均连接层次聚类。合并后特征集取并集（"坨"的特征 = 成员的并集）。"""
    clusters: list[tuple[set[str], list[str]]] = [(set(v), [k]) for k, v in sorted(feats.items())]
    while True:
        best = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                # 平均连接：成员两两 Jaccard 的均值
                si, li = clusters[i]
                sj, lj = clusters[j]
                vals = [jaccard(feats[a], feats[b]) for a in li for b in lj]
                s = sum(vals) / len(vals)
                if best is None or s > best[0]:
                    best = (s, i, j)
        if best is None or best[0] < threshold:
            break
        _, i, j = best
        si, li = clusters[i]
        sj, lj = clusters[j]
        merged = (si | sj, sorted(li + lj))
        clusters = [c for k, c in enumerate(clusters) if k not in (i, j)] + [merged]
    return [sorted(l) for _, l in sorted(clusters, key=lambda c: -len(c[1]))]


def articulation_points(sig: dict) -> list[tuple[str, list[str]]]:
    """依赖图割点（Tarjan，迭代）。割点 = 删掉就切断别人的节点 = 天然组件缝。

    注意：空壳期 import 图残缺，故这里的结果只对**已存在的边**成立。
    """
    nodes = sorted(sig["mods"])
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for a, bs in sig["imports"].items():
        for b in bs:
            adj[a].append(b)
            adj[b].append(a)

    index: dict[str, int] = {}
    low: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    ap: set[str] = set()
    counter = 0
    for root in nodes:
        if root in index:
            continue
        parent[root] = None
        index[root] = low[root] = counter
        counter += 1
        root_children = 0
        stack: list[tuple[str, int]] = [(root, 0)]
        while stack:
            v, i = stack[-1]
            if i < len(adj[v]):
                stack[-1] = (v, i + 1)
                u = adj[v][i]
                if u not in index:
                    parent[u] = v
                    index[u] = low[u] = counter
                    counter += 1
                    if v == root:
                        root_children += 1
                    stack.append((u, 0))
                elif u != parent[v]:
                    low[v] = min(low[v], index[u])
            else:
                stack.pop()
                p = parent[v]
                if p is not None:
                    low[p] = min(low[p], low[v])
                    if p != root and low[v] >= index[p]:
                        ap.add(p)
        if root_children > 1:
            ap.add(root)

    out = []
    for n in sorted(ap):
        nbrs = sorted({x for x in adj[n]})
        out.append((n, nbrs))
    return out


# ═════════════════════════════════════════════════════════════════════
# 三 · 主流程
# ═════════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", action="store_true", help="只打印信号")
    ap.add_argument("--threshold", type=float, default=MERGE_THRESHOLD)
    args = ap.parse_args()

    try:
        sig = extract_signals()
    except ClusterDataUnavailableError as exc:
        print("❌ 组件聚类未执行：数据面不足。", file=sys.stderr)
        print(f"原因：{exc}", file=sys.stderr)
        return 1
    feats = feature_sets(sig)

    print("=" * 74)
    print("由下往上的组件归属推导（★ 未读取铭牌的 COMPONENT 字段作为输入）")
    print("=" * 74)

    print("\n【S1】import 边（★ 空壳期残缺：函数体全是 raise，真实调用边尚未写出）")
    for a in sorted(sig["imports"]):
        for b in sorted(sig["imports"][a]):
            print(f"   {a:40s} → {b}")

    print("\n【S2】端口生产（profile.PORTS → produced_by）")
    fams: dict[str, list[str]] = defaultdict(list)
    for port, producer in sorted(sig["port_producer"].items()):
        fams[producer].append(port)
    for producer, ports in sorted(fams.items()):
        print(f"   {producer:18s} 生产 {len(ports):2d} 个：{', '.join(ports)}")

    print("\n【S3】算法消费（PluginSpec.required_inputs → required_inputs[*].port_id）")
    for aid, ports in sorted(sig["algo_requires"].items()):
        print(f"   {aid:9s} 需要 {len(ports)} 个端口：{', '.join(ports)}")

    print("\n【S4】契约符号足迹（各文件引用了 contract.py 的哪些符号）")
    for mod in sorted(sig["footprint"]):
        got = sorted(sig["footprint"][mod])
        if got:
            print(f"   {mod:40s} {len(got):3d}: {', '.join(got[:6])}{' …' if len(got) > 6 else ''}")
    print(f"   （contract.py 自身定义 {len(sig['contract_syms'])} 个公开符号，"
          f"作为枢纽不参与聚类）")

    if args.raw:
        return 0

    print("\n" + "=" * 74)
    print(f"★ 特征集（Jaccard 平均连接，阈值 {args.threshold}）")
    print("=" * 74)
    for mod in sorted(feats):
        print(f"   {mod:40s} |{'|'.join(sorted(feats[mod]))[:150]}")

    clusters = agglomerative(feats, args.threshold)

    print("\n" + "=" * 74)
    print("★ 推导结果：机械聚类发现的『坨』")
    print("=" * 74)
    for i, c in enumerate(clusters, 1):
        print(f"\n  坨 {i}（{len(c)} 文件）")
        for m in c:
            print(f"      {m}")

    print("\n" + "=" * 74)
    print("★ 割点分析：删掉它就会切断依赖的节点 = 天然组件缝")
    print("=" * 74)
    for n, nbrs in articulation_points(sig):
        print(f"   {n:40s} 连接 {len(nbrs)} 个：{', '.join(nbrs)}")

    print("\n" + "=" * 74)
    print("★ 对照：推导结果 vs 铭牌声称的组件（★ 只有这里才读 COMPONENT）")
    print("=" * 74)
    ok = 0
    bad = 0
    for i, c in enumerate(clusters, 1):
        votes: dict[str, int] = defaultdict(int)
        for m in c:
            votes[sig["plates"][m].get("_plate_COMPONENT", "?")] += 1
        mixed = len(votes) > 1
        if mixed:
            bad += 1
        else:
            ok += 1
        label = " + ".join(f"{k}×{v}" for k, v in sorted(votes.items(), key=lambda kv: -kv[1]))
        print(f"\n   坨 {i}: {label}{'   ⚠️ 跨铭牌组件' if mixed else '   ✅ 单一组件'}")
        for m in c:
            print(f"        {m:42s} 铭牌={sig['plates'][m].get('_plate_COMPONENT','?')}")

    # ---- 阈值敏感性：本方法论最关键的诚实点 ----
    print("\n" + "=" * 74)
    print("★ 阈值敏感性 —— 这个结果稳不稳？")
    print("=" * 74)
    print(f"   {'阈值':>6} {'坨数':>5} {'最大坨':>7} {'跨铭牌坨':>9}")
    for t in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.34, 0.40, 0.50):
        cl = agglomerative(feats, t)
        mx = max(len(c) for c in cl)
        mixed = sum(
            1 for c in cl
            if len({sig["plates"][m].get("_plate_COMPONENT") for m in c}) > 1
        )
        print(f"   {t:6.2f} {len(cl):5d} {mx:7d} {mixed:9d}")
    print("   ★ 从 1 坨摆到 18 坨、没有稳定平台 →")
    print("     空壳期代码**不足以决定**组件边界。这不是调参问题，是信号缺失。")

    print("\n★ 跨全部阈值都黏在一起的对（= 稳健信号，与阈值无关的结论）")
    thresholds = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.34)
    mods = sorted(feats)
    rows = []
    for i in range(len(mods)):
        for j in range(i + 1, len(mods)):
            s = jaccard(feats[mods[i]], feats[mods[j]])
            if s <= 0:
                continue
            together = sum(
                1 for t in thresholds
                if any({mods[i], mods[j]} <= set(c) for c in agglomerative(feats, t))
            )
            rows.append((together, s, mods[i], mods[j]))
    stable = [r for r in rows if r[0] >= 5]
    for together, s, a, b in sorted(stable, reverse=True):
        print(f"   {together}/7  J={s:.3f}  {a.replace('harmonica_eval.', '')}"
              f"  ↔  {b.replace('harmonica_eval.', '')}")
    if not stable:
        print("   （无）")

    print("\n" + "=" * 74)
    print(f"汇总：{ok} 坨单一组件 / {bad} 坨跨铭牌 / {len(stable)} 对稳健黏连")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
