"""probe7: FILE-004 §3.3 行号地图 + assert_profile_integrity 实际检查数 + §8.8 防回退文本
"""
import pathlib, re

src = pathlib.Path("harmonica_eval/profile.py").read_text(encoding="utf-8")
L = src.splitlines()
print("profile.py 总行数:", len(L))

marks = [
    ("import 区", r"^(from|import) "),
    ("PROFILE_VERSION", r"^PROFILE_VERSION"),
    ("class AudioSpec", r"^class AudioSpec"),
    ("AUDIO =", r"^AUDIO"),
    ("class AlignSpec", r"^class AlignSpec"),
    ("ALIGN =", r"^ALIGN"),
    ("class MaterializeSpec", r"^class MaterializeSpec"),
    ("MATERIALIZE =", r"^MATERIALIZE"),
    ("class BudgetSpec", r"^class BudgetSpec"),
    ("BUDGET =", r"^BUDGET"),
    ("class PortSpec", r"^class PortSpec"),
    ("PORTS", r"^PORTS"),
    ("PORT_INDEX", r"^PORT_INDEX"),
    ("def assert_profile_integrity", r"^def assert_profile_integrity"),
    ("模块级调用 assert_profile_integrity()", r"^assert_profile_integrity\(\)"),
    ("__all__", r"^__all__"),
]
for name, pat in marks:
    hits = [i + 1 for i, l in enumerate(L) if re.match(pat, l)]
    print(f"{name:32s} -> lines {hits}")

# assert_profile_integrity 内部 raise 计数
start = next(i for i, l in enumerate(L) if l.startswith("def assert_profile_integrity"))
end = next((i for i in range(start + 1, len(L)) if L[i].startswith("assert_profile_integrity()")), len(L))
body = "\n".join(L[start:end])
raises = re.findall(r"raise ValueError", body)
print("\nassert_profile_integrity 定义行:", start + 1, "到", end)
print("体内 raise ValueError 次数:", len(raises))
print("docstring 是否称『六件事』:", "六件事" in body)

# §8.8 命令 H 的 8 条文本
needles = ["当前无算法消费", "不保证两侧帧数相等", "真值来自 MIDI velocity", "按音配对，不是按轴配对",
           "明确不作为评分依据", "节奏类指标", "不许要求 Core 增加端口", "算法适配 Core，不是 Core 适配算法"]
print("\n§8.8 命令 H 文本核对：")
for n in needles:
    print(("OK  " if n in src else "MISS"), n)

# §4.6 前缀口径：'warp' 还是 'warp_path'？
print("\nPORTS 前缀实测:", sorted({p.split('.')[0] for p in re.findall(r'port_id="([^"]+)"', src)}))
