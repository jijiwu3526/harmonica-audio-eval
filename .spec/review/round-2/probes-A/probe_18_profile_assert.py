"""Probe 18: FILE-105 requires `profile.PROFILE_VERSION` in stage 1,
but §3 forbids importing harmonica_eval.profile."""
import pathlib
ROOT = pathlib.Path("/Users/Apple/Desktop/dsh-archive/harmonica-eval")
b5 = (ROOT/".spec/build/FILE-105-v1.md").read_text().splitlines()

print("=== FILE-105:53 whitelist (6 import sources, profile NOT among them) ===")
for i in (51,52,53,54):
    print(f"  {i+1}: {b5[i].strip()[:180]}")
print()
print("=== FILE-105:59 explicit named ban ===")
print(f"  60: {b5[59].strip()[:260]}")
print()
print("=== FILE-105:164 REQUIRES profile.PROFILE_VERSION ===")
print(f"  164: {b5[163].strip()[:260]}")
print()
print("=== FILE-105:331 restates the ban ===")
print(f"  331: {b5[330].strip()[:260]}")
print()
print("=== also: whitelist says '恰 6 条 import 的来源' -- count actual listed sources ===")
import re
# collect sources listed in the whitelist block lines 46-55
block = "\n".join(b5[45:56])
print(block)
print()
print("CONTENTION: line 164's assert needs profile.PROFILE_VERSION; no import path is whitelisted.")
