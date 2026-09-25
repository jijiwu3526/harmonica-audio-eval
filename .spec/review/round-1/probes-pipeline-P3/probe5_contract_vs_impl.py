"""P3 probe 5 — 跨文件字段/签名/枚举/能力对不上（第二批，逐条机械核对）。

覆盖：
  F. FILE-002 write_metrics_json 要写 inputs(reference/practice)，但签名只收 (view, out_path)
  G. FILE-201 用 status="SUCCEEDED"，contract 的取值域是 'OK'/'FAILED'/'INCOMPATIBLE'
  H. FILE-203 用 surface.rms.reference 属性访问 + envelope(error=...)，
     而 contract 的 AlgorithmDataContract 只有 manifest/read，envelope 无 error 字段
  I. FILE-203 期望 notes.* 是 list[dict]；contract.FIELD_LAYOUTS['notes'] 是 3 列 ndarray
  J. FILE-203 summarize_deltas 产 4 键；PAYLOAD_SCHEMAS['dynamics'] 冻结 5 键
  K. FILE-202 用 except HarmonicaError，但 §3 允许清单里没有它
  L. C1 build_view 要造 UiSeries(t, values)，但算法 payload 里没有任何时间坐标，
     且 FILE-301 §7 禁止 C1 读数据面
  M. 缺失模块：FILE-102 允许 import harmonica_eval.exceptions（不存在）
  N. assert_registry_integrity 的模块级调用缺失（FILE-200 §4.5 要求恰一次）
只读。
"""
from __future__ import annotations

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from harmonica_eval import contract  # noqa: E402
from harmonica_eval.algorithms import PAYLOAD_SCHEMAS  # noqa: E402

BUILD = REPO / ".spec" / "build"


def spec(n: str) -> list[str]:
    return (BUILD / f"{n}-v1.md").read_text(encoding="utf-8").splitlines()


def show(title: str, lines: list[str], needles: tuple[str, ...]) -> None:
    print(f"\n[{title}]")
    for i, ln in enumerate(lines, 1):
        if any(n in ln for n in needles):
            print(f"    {i}: {ln.strip()[:160]}")


def main() -> int:
    print("=" * 72)
    print("P3 probe 5 · 跨文件字段/签名/枚举/能力对不上（第二批）")
    print("=" * 72)

    s002 = spec("FILE-002")
    s201 = spec("FILE-201")
    s202 = spec("FILE-202")
    s203 = spec("FILE-203")
    s301 = spec("FILE-301")
    s102 = spec("FILE-102")
    s200 = spec("FILE-200")

    show("F · FILE-002 inputs vs write_metrics_json 签名", s002,
         ('"inputs"', "`inputs`", "def write_metrics_json", "reference_uri", "practice_uri"))
    print("    contract.UiView 字段:", list(contract.UiView.__dataclass_fields__))
    print("    -> UiView 不含 reference/practice；签名也不收 → inputs 无法按 §4.3 step3 写出")

    show("G · FILE-201 status 字面量", s201, ('status             =', 'status="SUCCEEDED"'))
    print("    contract 冻结取值域:", contract.AlgorithmResultEnvelope.__dataclass_fields__["status"].__doc__)

    show("H · FILE-203 surface.<port> 属性访问 / envelope(error=...)", s203,
         ("surface.rms.reference", "surface.notes.reference", "error="))
    print("    contract.AlgorithmDataContract 公开成员:", [n for n in dir(contract.AlgorithmDataContract) if not n.startswith("_")])
    print("    contract.AlgorithmResultEnvelope 字段:", list(contract.AlgorithmResultEnvelope.__dataclass_fields__))

    show("I · FILE-203 期望 notes.* 是 list[dict]", s203, ("list[dict]", "每项 dict"))
    print("    contract.FIELD_LAYOUTS['notes'] =", contract.FIELD_LAYOUTS["notes"])
    print("    contract.PortDescriptor.dimensions 示例（notes）见 profile.PORT_INDEX")

    show("J · FILE-203 summarize 输出键 vs PAYLOAD_SCHEMAS", s203, ("输出 dict key",))
    print("    PAYLOAD_SCHEMAS['dynamics'] =", PAYLOAD_SCHEMAS["dynamics"])
    print("    FILE-203 全段静音分支 payload 键:", re.findall(r"payload=\{[^}]*\}", "\n".join(s203)))

    show("K · FILE-202 except HarmonicaError vs §3 允许清单", s202, ("except HarmonicaError", "AlgorithmError"))

    show("L · FILE-301 build_view 的 series 规则", s301, ("UiSeries", "timeline_basis", "不读端口缓冲区"))
    print("    PAYLOAD_SCHEMAS 全键（有无时间坐标）:")
    for k, v in PAYLOAD_SCHEMAS.items():
        print(f"        {k}: {v}")
    print("    -> 无 onset_sec / 绝对时刻；UiSeries 需要 t: Sequence[float]")

    print("\n[M · 缺失模块（FILE-102 §3 允许清单 / §8 验证脚本）]")
    for i, ln in enumerate(s102, 1):
        if "exceptions" in ln:
            print(f"    {i}: {ln.strip()[:150]}")
    for m in ("exceptions", "pipeline", "evaluator", "score"):
        print(f"    harmonica_eval/{m}.py 存在:", (REPO / "harmonica_eval" / f"{m}.py").exists())

    print("\n[N · assert_registry_integrity 模块级调用]")
    alg = (REPO / "harmonica_eval" / "algorithms" / "__init__.py").read_text(encoding="utf-8")
    print("    模块末尾出现独立调用 'assert_registry_integrity()':",
          bool(re.search(r"^assert_registry_integrity\(\)\s*$", alg, re.M)))
    for i, ln in enumerate(s200, 1):
        if "恰有**一次**模块级语句" in ln or "模块末尾必须恰有" in ln:
            print(f"    FILE-200:{i}: {ln.strip()[:150]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
