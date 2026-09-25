"""Probe 31: FILE-104 internal contradictions (name counts, types import, top-level assert)."""
import pathlib, re
ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
b = (ROOT/".spec/build/FILE-104-v1.md").read_text().splitlines()

print("=== §3: 'profile 的 6 个名字' -- count the names actually listed ===")
for i in range(88, 92):
    print(f"  {i+1}: {b[i]}")
m = re.search(r"`harmonica_eval\.profile` 的 \*\*(\d+) 个名字\*\*：(.+?)。", "\n".join(b[86:93]), re.S)
if m:
    claimed = int(m.group(1)); names = re.findall(r"`([A-Z_]+)`", m.group(2))
    print(f"  claimed = {claimed}; listed = {len(names)} -> {names}")
    print(f"  MATCH: {claimed == len(names)}")

print()
print("=== §3: contract name count ===")
for i in range(83, 88):
    print(f"  {i+1}: {b[i]}")
mm = re.search(r"的 \*\*(\d+) 个名字\*\*，一个不多：\s*\n?\s*(.+?)；", "\n".join(b[82:90]), re.S)
if mm:
    claimed=int(mm.group(1)); names=re.findall(r"`([A-Za-z_]+)`", mm.group(2))
    print(f"  claimed = {claimed}; listed = {len(names)} -> {names}")

print()
print("=== 'types' in §3 allowed import list? ===")
allowed = "\n".join(b[70:92])
print("   'types' appears in §3 block:", "`types`" in allowed or "import types" in allowed)
print("   §3 exhaustiveness claim:", [l.strip() for l in b if "穷举" in l and "清单" in l][:2])
print()
print("=== §4.7 step 12 REQUIRES import types ===")
for i in range(793, 799):
    print(f"  {i+1}: {b[i]}")

print()
print("=== §3 forbids non-declaration top-level statements; §4.0 REQUIRES import-time assert ===")
for i in range(119, 123):
    print(f"  {i+1}: {b[i]}")
for i in range(138, 143):
    print(f"  {i+1}: {b[i]}")
