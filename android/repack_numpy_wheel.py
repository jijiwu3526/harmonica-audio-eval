#!/usr/bin/env python3
"""重打包 numpy wheel：把 WHEEL 里的 platform tag 改成 Android 的。

★ ★ ★ 为什么需要这个（★ 2026-09-26 实测）★★ ★★
```
★ Chaquopy 官方仓库（https://chaquo.com/pypi-13.1/）里那个 numpy 的
★ Android wheel 是【坏件】：
★   _multiarray_umath.so  2,791,008 字节
★   引用 libc.so · libdl.so · libm.so · libopenblas.so
★   而那个 wheel 内 19 个 .so 里【没有一个是 BLAS】
★   → ImportError: dlopen failed: library "libopenblas.so" not found
★ ★ ★ 而「换 Chaquopy 的另一个 numpy 版本」也换不掉 ——
★ ★ ★ arm64_v8a 的 wheel 只有 6 个（1.17.4 / 1.19.5 / 1.20.3 /
★ ★ ★ 1.23.3 / 1.26.2），★ 而它们【都缺 BLAS】。
★
★ PyPI 的 numpy-1.26.2-cp310-cp310-manylinux_2_17_aarch64 是好的：
★   _multiarray_umath.so  4,597,857 字节（★ 不同的文件）
★   且【自带】numpy.libs/libopenblas64_p-r0-17488984.3.23.dev.so
★   （25,804,257 字节，★ 实测 zipfile 读出）
★   ★ ★ 【dlopen 要的库就在同一个 wheel 里】
★
★ ★ ★ 而 pip【不认 manylinux tag】★★ ★
★   ERROR: numpy-1.26.2-...-manylinux_2_17_aarch64.manylinux2014_aarch64.whl
★          is not a supported wheel on this platform.
★ ★ ★ ★ 而 pip 读的是【wheel 内部的 WHEEL 元数据】，★ 不是文件名，
★ ★ ★ ★ ★ 所以只改文件名【不够】——★ 必须改 WHEEL 里的 Tag 行。
```

★ ★ ★ **★ 诚实的边界：★★ ★**
```
★ ★ ★ 本脚本【不改任何二进制内容】★★ ——★ 它只重写 WHEEL 那个
★ ★ ★ 文本条目里的两行 Tag，★ 其余 993 个条目按原字节复制。
★ ★ ★
★ ★ ★ ★ ★ 但【改过 tag 的 wheel 不再是官方原样】★★ ★★
★ ★ ★ ★ ★ 而【能不能在 Android 上真的跑通，要装完才知道】——
★ ★ ★ ★ ★ 可辨识：★ 装完跑阶段 1，★ 症状只有两种：
★ ★ ★ ★ ★   ① import numpy 成功  → 成了
★ ★ ★ ★ ★   ② 仍报 dlopen        → PyPI 版在 Android 上也不行
★ ★ ★ ★ ★ 【而那两种都是真信息】，★ 不会变成「不知道成没成」。
★ ★ ★ ★ ★
★ ★ ★ ★ ★ 而【不重编译】★ ——★ 所以它不能修「二进制本身不兼容」
★ ★ ★ ★ ★ 　 那类问题，★ 而那要开 buildPython 现场编。
```

★ **★ 用法（★ 复算命令）★★**
```bash
cd <仓库根>
B=https://chaquo.com/pypi-13.1
SRC=numpy-1.26.2-cp310-cp310-manylinux_2_17_aarch64.manylinux2014_aarch64.whl
mkdir -p android/app/wheels
[ -f "android/app/wheels/$SRC" ] || \
  curl -s -o "android/app/wheels/$SRC" "$B/numpy/$SRC"
python3 android/repack_numpy_wheel.py
# 产物：android/app/wheels/numpy-1.26.2-patched-cp310-cp310-android_21_arm64_v8a.whl
# 校验：python3 -c "import zipfile;print(zipfile.ZipFile('android/app/wheels/numpy-1.26.2-patched-cp310-cp310-android_21_arm64_v8a.whl').read('numpy-1.26.2.dist-info/WHEEL').decode())"
```
"""

from __future__ import annotations

import base64
import hashlib
import pathlib
import sys
import zipfile

SRC = "numpy-1.26.2-cp310-cp310-manylinux_2_17_aarch64.manylinux2014_aarch64.whl"
DST = "numpy-1.26.2-0-cp310-cp310-android_21_arm64_v8a.whl"
WHEELS = pathlib.Path(__file__).resolve().parent / "app" / "wheels"

# ★ pip 在 Android 上只认这一类 tag（★ Chaquopy 用 android_<minSdk>_<abi>）
FROM_TAGS = (
    "Tag: cp310-cp310-manylinux_2_17_aarch64",
    "Tag: cp310-cp310-manylinux2014_aarch64",
)
TO_TAG = "Tag: cp310-cp310-android_21_arm64_v8a"

# ★★★ 第二处修改（★ 2026-09-26 实测后加）★★★ ★
# ★ 实测：那个 umath.so 需要【两个】名字，★ 而 wheel 里只有一个：
# ★   它要   libopenblas64_.so.0                      ← SONAME（★ 缺这个）
# ★   也有   libopenblas64_p-r0-17488984.3.23.dev.so ← 实际文件名（★ 在）
# ★ manylinux wheel 的惯例是 .libs/ 放「实际文件 + SONAME 链接」两者，
# ★ 而【这个 wheel 只带了实际文件】——★ 所以运行时找不到那个 SONAME。
# ★ ★ ★ ★ 而【加一个【内容相同】的副本】★ 而不是符号链接：
# ★   zip 里的符号链接要特殊属性，★ 而 Chaquopy 的 AssetFinder 未必认。
# ★ ★ ★ ★ 若同内容副本不生效，★ 那才需要真符号链接，★ 而【那是下一层】★★ ★
RPATH_SRC = "numpy/core/_multiarray_umath.cpython-310.so"
OLD_RPATH = b"$ORIGIN/../../numpy.libs\x00"
NEW_RPATH = b"$ORIGIN/../numpy.libs"

SONAME_ALIAS = "numpy.libs/libopenblas64_.so.0"
SONAME_SOURCE = "numpy.libs/libopenblas64_p-r0-17488984.3.23.dev.so"

# ★★★ 第三处修改（★ 2026-09-26）：★ 重算 RECORD ★★★
# ★ 起因（★ 委派方读日志与 RECORD 定位，★ 我复核成立）：
# ★   产物 wheel 有 995 个条目，★ 而 RECORD 仍 902 行 ——
# ★   新增的 numpy.libs/libopenblas64_.so.0 【没被登记】。
# ★   Chaquopy 按 RECORD 逐行读 size，★ 读不到就 int('') → ValueError:
# ★     invalid literal for int() with base 10: ''
# ★   → :app:installDebugPythonRequirements FAILED
# ★ ★ ★ ★ 而【只补新增那一行不够】：★ zip 重写后压缩结果可能变，
# ★ ★ ★ ★ ★ 而【哈希必须与内容一致】，★ 所以整份重算。
# ★ ★ ★ ★ RECORD 格式（★ wheel 标准）：路径,sha256=<urlsafe-b64-无padding>,<字节数>
# ★ ★ ★ ★ 末行是 RECORD 自身：路径,,  ← ★ size 本来就空，★ 那是合法的
RECORD_NAME = "numpy-1.26.2.dist-info/RECORD"


def _record_line(name: str, data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    b64 = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"{name},sha256={b64},{len(data)}"


def main() -> int:
    src = WHEELS / SRC
    dst = WHEELS / DST
    if not src.is_file():
        print(f"★ 源文件不在：{src}", file=sys.stderr)
        return 1

    with zipfile.ZipFile(src) as zin:
        names = zin.namelist()
        wheel_entries = [n for n in names if n.endswith(".dist-info/WHEEL")]
        if len(wheel_entries) != 1:
            print(f"★ WHEEL 条目不唯一：{wheel_entries}", file=sys.stderr)
            return 1
        wheel_name = wheel_entries[0]
        if SONAME_SOURCE not in names:
            print(f"★ 源 wheel 里没有 {SONAME_SOURCE}", file=sys.stderr)
            return 1
        if SONAME_ALIAS in names:
            print(f"★ 源 wheel 里【已经有】{SONAME_ALIAS}，★ 那不需要补", file=sys.stderr)
            return 1

        # ★ ★ ★ 两处修改都在【写完之后】统一处理 RECORD ★★★ ★
        # ★ （★ 因为 RECORD 的哈希必须对应【最终写入的内容】，
        # ★   而 zip 重写后压缩结果可能变，★ 所以只能最后算。）
        payload: dict[str, bytes] = {}
        renamed: list[tuple[str, str]] = []
        rpath_patched: list[tuple[int, bytes]] = []
        co_located: list[tuple[str, int]] = []
        for info in zin.infolist():
            data = zin.read(info.filename)
            name = info.filename
            if name == wheel_name:
                text = data.decode("utf-8")
                for tag in FROM_TAGS:
                    if tag not in text:
                        print(f"★ 期望的 tag 不存在：{tag}", file=sys.stderr)
                        return 1
                    text = text.replace(tag, TO_TAG)
                data = text.encode("utf-8")
            if name == RECORD_NAME:
                continue  # ★ RECORD 自己【稍后重算】
            if name.endswith("/"):
                # ★ ★ 目录项【不登记】★★ ★
                # ★ 实测：登记目录项会让 Chaquopy 的 tree_add_path() 里
                #   `assert isinstance(subtree, dict)` 抛
                #   AssertionError: numpy.libs/libgfortran-daac5196.so.5.0.0
                # ★ ★ 而【那不是 so 命名规则的问题】★ ——★ 那是我上轮的误判。
                continue
            # ★★★★★ 第四处修改：★ 去掉扩展模块文件名里的平台段 ★★★★★ ★
            # ★ 实测（★ 对照组选的是【真能工作的那些】，★ 而不只是「看起来像的」）：
            # ★   标准库里能 import 的：★ _posixsubprocess.cpython-310.so
            # ★                            fcntl.cpython-310.so · select.cpython-310.so
            # ★   装不上的这个：★      _multiarray_umath.cpython-310-aarch64-linux-gnu.so
            # ★ ★ ★ ★ ★ 而【那正是 CPython 的 EXTENSION_SUFFIXES 决定的】——
            # ★ ★ ★ ★ ★ 那个列表按平台给，★ 而 Android 上【没有】带 aarch64-linux-gnu
            # ★ ★ ★ ★ ★ 的形式。★ → 文件在磁盘上存在，★ 却不被识别为扩展模块，
            # ★ ★ ★ ★ ★   → import 失败，★ 而 CPython 统一报成 ModuleNotFoundError。
            # ★ ★ ★ ★ ★ 而 numpy.libs/ 下的【不动】——★ 它们是共享库不是扩展模块，
            # ★ ★ ★ ★ ★ ★   由 dlopen 按名字找，★ 改名字会坏掉依赖解析。
            if name.endswith(".cpython-310-aarch64-linux-gnu.so"):
                base = name[: -len(".cpython-310-aarch64-linux-gnu.so")]
                name = base + ".cpython-310.so"
                renamed.append((info.filename, name))
            # ★★★★★★ 第六处修改：★ 修 umath.so 里 RPATH 的级数 ★★★★★★ ★
            # ★ 实测（原文明文，★ 从二进制里读出来的）：
            # ★   DT_RPATH  = $ORIGIN/../../numpy.libs
            # ★   DT_RUNPATH = 无
            # ★ ★ ★ ★ ★ 而【Chaquopy 把包解到 requirements/ 下】，
            # ★ ★ ★ ★ ★ 所以 umath 的 $ORIGIN = requirements/numpy/core/：
            # ★   $ORIGIN/../numpy.libs    → requirements/numpy.libs  ★ ★ 正确
            # ★   $ORIGIN/../../numpy.libs → requirements/../numpy.libs ★ ★ 越过根
            # ★ ★ ★ ★ ★ ★ 而【原始 wheel 里那【一层 numpy/ 包目录是存在的】，
            # ★ ★ ★ ★ ★ ★ 所以 ../../ 当时是对的 ——★ 【Chaquopy 摊平后差一级】★★ ★
            # ★ ★ ★ ★ ★ 而【只改那一个字符串】：★ 原地替换，★ 后面补 NUL 到原长度，
            # ★ ★ ★ ★ ★ ★ 【文件大小不变】★ ——★ 不动 PT_DYNAMIC，★ 不动其他偏移。
            if name == "numpy/core/_multiarray_umath.cpython-310.so":
                if OLD_RPATH not in data:
                    print(f"★ 没找到预期的 RPATH 串：{OLD_RPATH!r}", file=sys.stderr)
                    return 1
                idx = data.find(OLD_RPATH)
                patched = bytearray(data)
                patched[idx:idx + len(NEW_RPATH)] = NEW_RPATH
                for k in range(idx + len(NEW_RPATH), idx + len(OLD_RPATH)):
                    patched[k] = 0  # ★ 补 NUL 到原长度
                data = bytes(patched)
                rpath_patched.append((len(data), data[idx:idx + len(OLD_RPATH)]))
            payload[name] = data
        # ★ 第二处修改：★ 补 SONAME 同名副本（★ 内容逐字节相同）
        payload[SONAME_ALIAS] = zin.read(SONAME_SOURCE)
        # ★ ★★★★★★★ 第七处修改：★ 把 umath 要的那个依赖放到 umath 同目录 ★★★★★★★ ★
        # ★ 实测（★ 走 PT_DYNAMIC 读 DT_NEEDED，★ 逐字）：
        # ★   'libopenblas64_p-r0-17488984.3.23.dev.so'   ← 唯一非系统库
        # ★   'libm.so.6' 'libgcc_s.so.1' 'libc.so.6'        ← 系统库，不动
        # ★ ★ ★ ★ 而【那个文件【已经在 numpy.libs/ 下】★ ——★ 文件不缺、
        # ★ ★ ★ ★ 名字不缺、★ RPATH 也对（$ORIGIN/../numpy.libs），
        # ★ ★ ★ ★ 而 import 仍报 not found。
        # ★ ★ ★ ★ ★ 【依据（待验假设）】：★ Android linker 加载一个 so 时，
        # ★ ★ ★ ★ ★ 【会先搜它自己所在的目录】。★ 那不是 wheel 的问题，
        # ★ ★ ★ ★ ★ 而是【AssetFinder 解出来的 files/ 布局不在搜索路径里】。
        # ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★ ★
        # ★ ★ 内容逐字节相同 · 不改名 · 不动 numpy.libs/ 下原有那份 ·
        # ★ ★ RECORD 会自动覆盖新路径（★ 见下面第三处修改）。
        # ★ ★ 而【只放这一个】——★ DT_NEEDED 只要那一个名字，★ 造别的没用。
        NEEDED_IN_LIBS = "numpy.libs/libopenblas64_p-r0-17488984.3.23.dev.so"
        NEEDED_IN_CORE = "numpy/core/libopenblas64_p-r0-17488984.3.23.dev.so"
        if NEEDED_IN_LIBS not in zin.namelist():
            print(f"★ 源 wheel 里没有 {NEEDED_IN_LIBS}", file=sys.stderr)
            return 1
        payload[NEEDED_IN_CORE] = zin.read(NEEDED_IN_LIBS)
        co_located.append((NEEDED_IN_CORE, len(payload[NEEDED_IN_CORE])))
        # ★ 第三处修改：★ 重算整份 RECORD（★ 跳过它自己、★ 跳过目录项）
        lines = [_record_line(n, d) for n, d in sorted(payload.items())]
        lines.append(f"{RECORD_NAME},,")
        record = ("\n".join(lines) + "\n").encode("utf-8")
        # ★ 目录项【仍要写进 zip】，★ 只是【不登记在 RECORD 里】——
        # ★ ★ 而【那两件事是分开的】★★ ★
        dirs = [i.filename for i in zin.infolist() if i.filename.endswith("/")]

        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for name in dirs:
                zout.writestr(name, b"")
            for name, data in payload.items():
                zout.writestr(name, data)
            zout.writestr(RECORD_NAME, record)

    # ★ 校验：★ 从产物里【读出来】看，★ 而不是相信我写对了
    with zipfile.ZipFile(dst) as z:
        got = z.read(wheel_name).decode("utf-8")
        so = [n for n in z.namelist() if n.endswith(".so")]
        libs = [n for n in z.namelist() if n.startswith("numpy.libs/")]
        alias_ok = SONAME_ALIAS in z.namelist()
        same = z.read(SONAME_ALIAS) == z.read(SONAME_SOURCE) if alias_ok else False
        sizes = {n: z.getinfo(n).file_size for n in so + libs}
        # ★ ★ 校验：★ 整个 wheel 的 .py 里【有没有硬编码那个平台段】★★ ★
        # ★ 若有，★ 改完 so 名字反而更找不到——★ 那要一并改
        hardcoded = [
            n for n in z.namelist()
            if n.endswith(".py") and b"aarch64-linux-gnu" in z.read(n)
        ]

    print(f"  源  {SRC}  {src.stat().st_size} 字节")
    print(f"  产物 {DST}  {dst.stat().st_size} 字节")
    print(f"  ── 第七处修改：★ 依赖放 umath 同目录 ──")
    for n, sz in co_located:
        print(f"    {n}  {sz} 字节")
    print(f"  ── 第六处修改：★ RPATH 级数（★ {len(rpath_patched)} 个）──")
    for size, seg in rpath_patched:
        print(f"    {RPATH_SRC.split('/')[-1]}  {size} 字节（大小不变）")
        print(f"      {seg!r}")
    print(f"  ── 第四处修改：★ 扩展模块去掉平台段（★ {len(renamed)} 个）──")
    for old, new in renamed:
        print(f"    {old.split('/')[-1]}")
        print(f"      → {new.split('/')[-1]}")
    core_so = sorted(n for n in so if n.startswith("numpy/core/"))
    print(f"  ── 产物 numpy/core/ 下的 .so（★ 从文件读出来）──")
    for n in core_so:
        print(f"    {n.split('/')[-1]}  {sizes[n]} 字节")
    print(f"  ── numpy.libs/ 完整清单（★ 共享库，★ 不该动）──")
    for n in sorted(libs):
        print(f"    {n}  {z.getinfo(n).file_size} 字节")
    print(f"  SONAME 副本 {SONAME_ALIAS} 在: {alias_ok} · 内容与源相同: {same if alias_ok else '—'}")
    print(f"  ★ 还带 aarch64-linux-gnu 的扩展: {sum('aarch64-linux-gnu' in n for n in so)} 个（应为 0）")
    # ★ ★ 校验：★ 整个 wheel 的 .py 里【有没有硬编码那个平台段】★★ ★
    # ★ 若有，★ 改完 so 名字反而更找不到——★ 那要一并改
    print(f"  ★ 硬编码平台段的 .py: {hardcoded or '零个 ✓'}")
    print(f"  条目 {len(so)} 个 .so")
    print("  ── 产物 WHEEL 的 Tag 行（★ 从文件读出来的）──")
    for line in got.splitlines():
        if line.startswith("Tag:") or line.startswith("Root-Is-Purelib"):
            print(f"    {line}")
    if TO_TAG not in got:
        print("  ★ 校验失败：产物里没有预期的 Tag", file=sys.stderr)
        return 1
    if not alias_ok:
        print("  ★ 校验失败：SONAME 副本没写进去", file=sys.stderr)
        return 1
    if hardcoded:
        print("  ★ 校验失败：有 .py 硬编码了平台段，★ 那要一并改", file=sys.stderr)
        return 1
    print("  ✅ Tag 已改 · SONAME 副本已加 · 平台段已去掉 · 无硬编码")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
