"""probe6: FILE-300 附录引用的行号与内容逐条核对
引用: host/__init__.py:33 / __init__.py:52-59 / verify_shell.py:205-211
      contract.py:490-569 (HostContract 7 ops) / contract.py:936-948 (UiProjectionPort 2 ops)
"""
import pathlib

def line(p, n):
    return pathlib.Path(p).read_text(encoding="utf-8").splitlines()[n - 1]

def span(p, a, b):
    L = pathlib.Path(p).read_text(encoding="utf-8").splitlines()
    return list(enumerate(L[a - 1:b], start=a))

print("== host/__init__.py:33 ==")
print(line("harmonica_eval/host/__init__.py", 33))

print("\n== harmonica_eval/__init__.py:52-59 ==")
for i, l in span("harmonica_eval/__init__.py", 52, 59):
    print(i, l)

print("\n== tools/verify_shell.py:200-215 ==")
for i, l in span("tools/verify_shell.py", 200, 215):
    print(i, l)

print("\n== contract.py:490-569 中的 class/def ==")
for i, l in span("harmonica_eval/contract.py", 490, 569):
    if l.startswith(("class ", "    def ", "def ")):
        print(i, l)

print("\n== contract.py:930-955 中的 class/def/__all__ ==")
for i, l in span("harmonica_eval/contract.py", 930, 955):
    if l.startswith(("class ", "    def ", "def ", "__all__")):
        print(i, l)
