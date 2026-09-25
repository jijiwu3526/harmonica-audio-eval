"""探针 4: FILE-004 §8.8 命令 H 的 8 条防回退文本是否真的在 profile.py 里"""
import pathlib, subprocess
f = "harmonica_eval/profile.py"
src = pathlib.Path(f).read_text(encoding="utf-8")
needles = ["当前无算法消费","不保证两侧帧数相等","真值来自 MIDI velocity","按音配对，不是按轴配对",
           "明确不作为评分依据","节奏类指标","不许要求 Core 增加端口","算法适配 Core，不是 Core 适配算法"]
for n in needles:
    print(f"{'OK ' if n in src else 'MISS'} {n}")
# 关键: '不许要求 Core 增加端口' 与 '真值来自 MIDI velocity'
print()
print("profile.py 中 '不许' 出现处:", [i+1 for i,l in enumerate(src.splitlines()) if "不许" in l])
print("profile.py 中 'MIDI' 出现处:", [i+1 for i,l in enumerate(src.splitlines()) if "MIDI" in l])
print("profile.py 中 '不许要求' :", src.count("不许要求"))
# '契约要求 mono' 等错误消息逐字核对 (FILE-003 §5)
print()
print("contract.py 错误消息:")
c = pathlib.Path("harmonica_eval/contract.py").read_text(encoding="utf-8")
for m in ("契约要求 mono","契约要求 float32","no detail"):
    print(f"  {'OK ' if m in c else 'MISS'} {m}")
