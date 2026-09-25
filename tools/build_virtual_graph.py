#!/usr/bin/env python3
"""生成 Virtual System Graph（宪章 §10 / §44.2）。

═══════════════════════════════════════════════════════════════════════
为什么是「生成」而不是「手写」
═══════════════════════════════════════════════════════════════════════

本仓库刚发生过一次事故：我手写的「宪章 §11 逃生口」引用是**伪造的**，
并传播到 6 个文件。手写的结构化事实会**静默漂移**，而且无法机械反驳。

所以这张图的原则是：

    **能从代码推导的，一律推导；只有代码里不存在的，才允许手写。**

代码里**存在**的（推导）：
    - 有哪些文件、各自属于哪个组件（读铭牌的 COMPONENT 字段）
    - 端口清单与生产者（读 profile.PORTS）
    - 算法依赖关系（需要装配后的插件声明；当前数据面不足时显式失败）
    - 每个文件的公开符号（ast 解析）

代码里**不存在**的（手写 overlay）：
    - Mission Threads（§11：它是虚拟图的一部分，但不是代码）
    - 组件意图为什么存在（§41：追溯到 Product Intent）

overlay 单独放 `.spec/graph/overlay.json`，与生成物分开 ——
这样"哪些是我推导的、哪些是我声称的"一眼可辨。

═══════════════════════════════════════════════════════════════════════
宪章 §44.2 要求同时管三类关系
═══════════════════════════════════════════════════════════════════════

    Decomposition Tree   → 它属于谁？        decomposition
    Dependency DAG       → 谁依赖谁？        dependency
    Traceability Graph   → 为什么存在？      traceability

用法：
    python3 tools/build_virtual_graph.py            # 生成
    python3 tools/build_virtual_graph.py --check    # 只校验，不写
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Sequence

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "harmonica_eval"
OUT = REPO / ".spec" / "graph" / "virtual-system-graph.json"
OVERLAY = REPO / ".spec" / "graph" / "overlay.json"

sys.path.insert(0, str(REPO))


class GraphDataUnavailableError(RuntimeError):
    """生成依赖图所需的插件装配数据尚不可读。"""


# ═════════════════════════════════════════════════════════════════════
# 一 · 从代码推导
# ═════════════════════════════════════════════════════════════════════

def _nameplate(src: str) -> dict[str, str]:
    """从文件顶部的现场铭牌（§18）里抠出字段。

    ★ 铭牌头可能用 ''' 或 \"\"\"；字段名与冒号之间也可能有空格
      （serve_ui.py 写 COMPONENT␣␣: 而 host/app.py 写 COMPONENT:）。
      ★ 所以两种引号都试，且键名前允许空格。
    """
    m = re.match(r"'''(.*?)'''", src, re.S) or re.match(r'"""(.*?)"""', src, re.S)
    if not m:
        return {}
    body = m.group(1)
    out: dict[str, str] = {}
    for key in ("FILE-ID", "COMPONENT", "SPEC", "ROLE", "BUILD-INSTRUCTION"):
        # ★ 字段值到【下一个真字段名】为止（§18 十字段），不是到任意大写行为止。
        #   旧式 (?=\n[A-Z][A-Z /-]*:|\Z) 会把续行吞进同名字段——「★ 裁定：…」
        #   这类说明行不含新字段名，于是一路吃到文末，产出 800+ 字的假「路径」。
        mm = re.search(
            rf"^[ \t]*{key}[ \t]*:[ \t]*(.+?)(?=\n[ \t]*(?:FILE-ID|COMPONENT|SPEC|ROLE|"
            rf"INTENT|MUST|MUST NOT|INPUT|OUTPUT|BUILD-INSTRUCTION)[ \t]*:|\Z)",
            body, re.M | re.S,
        )
        if mm:
            # ★ 取【首个非空行】作为字段值。
            #   §18 允许两种写法：「KEY: 值」同行，或「KEY:」后换行缩进写值；
            #   也允许值之后跟说明行。整段拼接会让 validate() 拿 800 字
            #   文字当路径（ENAMETOOLONG），而只取首行会漏掉换行写法（空值）。
            lines = [ln.strip() for ln in mm.group(1).splitlines() if ln.strip()]
            out[key] = lines[0] if lines else ""
    return out


def _public_symbols(path: Path) -> list[str]:
    """该文件顶层定义的公开符号（函数 / 类 / 常量）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not n.name.startswith("_"):
                out.append(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and not t.id.startswith("_"):
                    out.append(t.id)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            if not n.target.id.startswith("_"):
                out.append(n.target.id)
    return sorted(set(out))


def _internal_imports(path: Path) -> list[str]:
    """该文件对本包其他模块的 import（相对 import 解析成包路径）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    deps: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level:
            base = path.parent
            for _ in range(n.level - 1):
                base = base.parent
            target = base / (n.module.replace(".", "/") if n.module else "")
            try:
                rel = target.relative_to(REPO)
                deps.add(str(rel).replace("/", "."))
            except ValueError:
                pass
        elif isinstance(n, ast.ImportFrom) and n.module and "harmonica" in n.module:
            deps.add(n.module)
    return sorted(deps)


def build_decomposition() -> dict:
    """Decomposition Tree：System → Component → File。"""
    comp_files: dict[str, list[dict]] = {}
    unassigned: list[str] = []

    for p in sorted(PKG.rglob("*.py")):
        if "__pycache__" in str(p):
            continue
        src = p.read_text(encoding="utf-8")
        plate = _nameplate(src)
        comp = plate.get("COMPONENT", "").strip()
        # 铭牌里组件名带括号说明（如「COMP-PKG（包入口，本身不是组件）」），
        # 取第一个空格/括号前的 token 作为组件 ID
        comp_id = re.split(r"[（( ]", comp)[0] if comp else ""
        if not comp_id:
            unassigned.append(str(p.relative_to(REPO)))
            continue
        comp_files.setdefault(comp_id, []).append({
            "file_id": plate.get("FILE-ID", "?"),
            "path": str(p.relative_to(REPO)),
            "role": plate.get("ROLE", ""),
            "build_instruction": plate.get("BUILD-INSTRUCTION", ""),
            "public_symbols": _public_symbols(p),
        })

    return {
        "system": "harmonica-eval",
        "components": [
            {
                "component_id": cid,
                "is_component": not any(
                    k in cid for k in ("PKG", "CONFIG", "CONTRACT")
                ),
                "file_count": len(fs),
                "files": fs,
            }
            for cid, fs in sorted(comp_files.items())
        ],
        "unassigned_files": unassigned,
    }


def load_registry_specs() -> tuple[object, ...]:
    """取得已装配 Registry 的 PluginSpec 清单。

    ★ 本工具【不】import 具体算法实现，只经 bootstrap 这个唯一装配根取得
      声明式清单（FILE-206 装配根唯一性）。

    ★ 取不到才抛 GraphDataUnavailableError，判据是【真实的】：
      bootstrap 抛异常 / 清单为空 / 元素缺字段。
      ★ 绝不按「文件看起来是空壳」判断——那是阶段态判据，注入完成即失效，
        会让本工具在项目推进后永远拒绝工作。
    """
    try:
        from harmonica_eval.algorithms.bootstrap import build_default_registry
    except Exception as exc:
        raise GraphDataUnavailableError(
            f"无法导入装配根 harmonica_eval.algorithms.bootstrap：{exc}"
        ) from exc
    try:
        specs = tuple(build_default_registry().list())
    except Exception as exc:
        raise GraphDataUnavailableError(
            f"build_default_registry() 失败，无法取得已装配清单：{exc}"
        ) from exc
    if not specs:
        raise GraphDataUnavailableError(
            "已装配 Registry 为空（build_default_registry().list() 返回空序列）"
        )
    for spec in specs:
        if not hasattr(spec, "algorithm_id") or not hasattr(spec, "required_inputs"):
            raise GraphDataUnavailableError(
                f"已装配清单元素缺 algorithm_id/required_inputs：{spec!r}"
            )
    return specs


def build_dependency(plugin_specs: Sequence[object] | None = None) -> dict:
    """Dependency DAG：文件级 import + 端口级生产/消费。

    ★ C3 插件化后，算法清单不再由框架静态保存。本工具需要装配后 Registry
      中每个 ``PluginSpec`` 的 ``required_inputs``；缺省时由
      ``load_registry_specs()`` 自行取得（不 import 具体算法实现）。

    ★ 「数据面不足」只按【真实取不到】判定，见 load_registry_specs 的说明。
      ★ 绝不按「文件看起来是空壳」判断——那会让本工具在注入完成后
        永远拒绝工作。

    ``plugin_specs`` 是给测试与库调用方保留的显式输入。
    """
    if plugin_specs is None:
        plugin_specs = load_registry_specs()

    edges: list[dict] = []
    for p in sorted(PKG.rglob("*.py")):
        if "__pycache__" in str(p):
            continue
        for d in _internal_imports(p):
            edges.append({
                "from": str(p.relative_to(REPO)),
                "to": d.replace(".", "/") + ".py",
                "kind": "import",
            })

    import harmonica_eval.profile as prof

    consumers: dict[str, list[str]] = {}
    algorithm_rows: list[dict] = []
    for spec in plugin_specs:
        try:
            algorithm_id = spec.algorithm_id
            version = spec.algorithm_version
            requirements = spec.required_inputs
            required_ports = tuple(
                requirement.port_id for requirement in requirements
            )
        except Exception as exc:
            raise GraphDataUnavailableError(
                "已提供的插件声明不完整或不可读，无法生成依赖图；"
                "每个条目必须是含 algorithm_id/algorithm_version/required_inputs 的 PluginSpec，"
                "且 required_inputs 必须逐项提供 port_id。"
            ) from exc
        for port_id in required_ports:
            consumers.setdefault(port_id, []).append(algorithm_id)
        algorithm_rows.append({
            "algorithm_id": algorithm_id,
            "version": version,
            "required_ports": list(required_ports),
        })

    ports = []
    for s in prof.PORTS:
        ports.append({
            "port_id": s.port_id,
            "produced_by": s.produced_by,
            "timeline_basis": getattr(s.timeline_basis, "value", str(s.timeline_basis)),
            "units": s.units,
            "hop_length": s.hop_length,
            "consumed_by": consumers.get(s.port_id, []),
            "is_evidence_only": not consumers.get(s.port_id),
        })

    return {
        "import_edges": edges,
        "ports": ports,
        "algorithms": algorithm_rows,
        "profile_version": prof.PROFILE_VERSION,
    }


# ═════════════════════════════════════════════════════════════════════
# 二 · 手写 overlay（代码里不存在的事实）
# ═════════════════════════════════════════════════════════════════════

def load_overlay() -> dict:
    if not OVERLAY.exists():
        return {"mission_threads": [], "component_intent": {}}
    return json.loads(OVERLAY.read_text(encoding="utf-8"))


# ═════════════════════════════════════════════════════════════════════
# 三 · 校验
# ═════════════════════════════════════════════════════════════════════

def validate(graph: dict) -> list[str]:
    """图自身的完整性。返回问题列表（空 = 通过）。"""
    problems: list[str] = []

    # ① 每个文件都必须归属一个组件（§17：文件身份明确）
    if graph["decomposition"]["unassigned_files"]:
        problems.append(
            f"有文件未归属组件: {graph['decomposition']['unassigned_files']}"
        )

    # ② 每个文件的 BUILD-INSTRUCTION 都必须真实存在（§30 阻断项）
    for c in graph["decomposition"]["components"]:
        for f in c["files"]:
            bi = f.get("build_instruction", "")
            if bi and not (REPO / bi).exists():
                problems.append(f"{f['path']} 的 Build Instruction 不存在: {bi}")

    # ③ 每个端口的 produced_by 都必须是真实存在的模块
    valid_producers = {"core.ingest", "core.align", "core.features", "core.surface"}
    for p in graph["dependency"]["ports"]:
        if p["produced_by"] not in valid_producers:
            problems.append(
                f"端口 {p['port_id']} 的 produced_by={p['produced_by']} 不是已知模块"
            )

    # ④ 算法声明的每个端口都必须真实存在（否则永远 INCOMPATIBLE）
    known = {p["port_id"] for p in graph["dependency"]["ports"]}
    for a in graph["dependency"]["algorithms"]:
        for port in a["required_ports"]:
            if port not in known:
                problems.append(
                    f"算法 {a['algorithm_id']} 声明了不存在的端口 {port}"
                )

    # ⑤ Mission Thread 引用的组件必须存在
    known_comps = {c["component_id"] for c in graph["decomposition"]["components"]}
    for mt in graph["traceability"].get("mission_threads", []):
        for cid in mt.get("components", []):
            if cid not in known_comps:
                problems.append(f"{mt.get('id','?')} 引用了不存在的组件 {cid}")

    return problems


def main() -> int:
    check_only = "--check" in sys.argv

    try:
        graph = {
            "schema": "virtual-system-graph/v1",
            "generated_by": "tools/build_virtual_graph.py",
            "note": (
                "★ 本文件由脚本生成，不要手改 —— 手改会在下次生成时丢失。"
                "能从代码推导的都推导；只有代码里不存在的才写在 overlay.json。"
            ),
            "decomposition": build_decomposition(),
            "dependency": build_dependency(),
            "traceability": load_overlay(),
        }
    except GraphDataUnavailableError as exc:
        print("❌ Virtual System Graph 未生成：数据面不足。", file=sys.stderr)
        print(f"原因：{exc}", file=sys.stderr)
        print("恢复条件：让 harmonica_eval.algorithms.bootstrap 的 "
              "build_default_registry() 能返回非空 PluginSpec 清单。"
              "本次未写入任何图文件。", file=sys.stderr)
        return 1

    problems = validate(graph)

    print("=" * 72)
    print("Virtual System Graph（宪章 §10 / §44.2）")
    print("=" * 72)
    print()
    print("① Decomposition Tree —— 它属于谁？")
    for c in graph["decomposition"]["components"]:
        tag = "组件" if c["is_component"] else "非组件"
        print(f"   {c['component_id']:34s} {c['file_count']:2d} 文件  [{tag}]")
    print()
    print("② Dependency DAG —— 谁依赖谁？")
    d = graph["dependency"]
    print(f"   端口 {len(d['ports'])} 个，其中证据端口（无算法消费）"
          f" {sum(1 for p in d['ports'] if p['is_evidence_only'])} 个")
    print(f"   算法 {len(d['algorithms'])} 个")
    print(f"   文件级 import 边 {len(d['import_edges'])} 条")
    print()
    print("③ Traceability Graph —— 为什么存在？")
    t = graph["traceability"]
    print(f"   Mission Threads {len(t.get('mission_threads', []))} 条")
    print(f"   组件意图说明 {len(t.get('component_intent', {}))} 个")

    if problems:
        print()
        print("─" * 72)
        for p in problems:
            print(f"  ❌ {p}")
        print("─" * 72)
        print(f"❌ 校验未通过（{len(problems)} 项）")
        return 1

    print()
    print("✅ 图校验通过")

    if not check_only:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(
            json.dumps(graph, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"   已写入 {OUT.relative_to(REPO)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
