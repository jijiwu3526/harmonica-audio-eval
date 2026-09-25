"""探针 3: 各模引用的行号逐条核对"""
import pathlib
def lines(p): return pathlib.Path(p).read_text(encoding="utf-8").splitlines()
checks = [
    ("harmonica_eval/__main__.py", [49,52,55,58,61,64]),
    ("harmonica_eval/host/__init__.py", [33]),
    ("harmonica_eval/contract.py", [490,569,936,948]),
    ("tools/verify_shell.py", [205,211]),
    ("harmonica_eval/cockpit/app.py", [61]),
]
for path, lns in checks:
    L = lines(path)
    for n in lns:
        print(f"{path}:{n}: {L[n-1][:76]}")
# FILE-400 说 launch_cockpit 在第 61 行有 raise；确认
L = lines("harmonica_eval/cockpit/__init__.py")
print("cockpit/__init__.py:61:", L[60])
# FILE-004 引用 profile.py 行号区间
L = lines("harmonica_eval/profile.py")
for n in (44,54,56,64,85,92,123,130,167,174,191,198,240,243,445,447,451,568,571,574,580):
    print(f"profile.py:{n}: {L[n-1][:70]}")
