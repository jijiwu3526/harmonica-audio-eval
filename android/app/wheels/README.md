# android/app/wheels/ —— 装进 APK 的 wheel

★ ★ ★ **★ 这个目录里的文件【不进 git】★★ ★**
★ 与「音频不进 git」同理：二进制产物只留复算命令，★ 不入库。
★ 见仓库根 `.gitignore` 的 `android/app/wheels/*.whl`。

---

## 一、四个文件各是什么

| 文件 | 来源 | 作用 |
|---|---|---|
| `numpy-1.26.2-0-cp310-cp310-android_21_arm64_v8a.whl` | ★ **不是 Chaquopy 原版**，★ 是下面那个 manylinux wheel 重打包的 | numpy |
| `numpy-1.26.2-cp310-cp310-manylinux_2_17_aarch64.manylinux2014_aarch64.whl` | PyPI | ★ 重打包的**源** |
| `scipy-1.8.1-1-cp310-cp310-android_21_arm64_v8a.whl` | `chaquo.com/pypi-13.1/` | scipy |
| `soundfile-0.13.1-0-cp310-cp310-android_24_arm64_v8a.whl` | `chaquo.com/pypi-13.1/` | soundfile |

## 二、★ 为什么 numpy 要重打包（★ 2026-09-26 实测，不是推测）★

```
★ Chaquopy 官方仓库里那个 numpy 的 Android wheel 是【坏件】：
★   numpy/core/_multiarray_umath.so   2,791,008 字节
★   它引用 libc.so · libdl.so · libm.so · libopenblas.so
★   而那个 wheel 内 19 个 .so 里【没有一个是 BLAS】
★   → ImportError: dlopen failed: library "libopenblas.so" not found
★
★ 而「换 Chaquopy 的另一个 numpy 版本」换不掉：
★   仓库里 arm64_v8a 的 numpy wheel 只有 6 个（1.17.4 / 1.19.5 / 1.20.3 /
★   1.23.3 / 1.26.2），★ 实测【都缺 BLAS】。
```

**而 PyPI 的 aarch64 版是好的：**

```
numpy/core/_multiarray_umath.cpython-310-aarch64-linux-gnu.so   4,597,857 字节
numpy.libs/libopenblas64_p-r0-17488984.3.23.dev.so            25,804,257 字节
★ ★ ★ 【dlopen 要的库就在同一个 wheel 里】★★ ★
★ ★ 而那两个文件【不是同一个文件】——★ Chaquopy 版 2.79MB / PyPI 版 4.60MB
```

**而 pip 不认 manylinux tag：**

```
ERROR: numpy-1.26.2-...-manylinux_2_17_aarch64.manylinux2014_aarch64.whl
       is not a supported wheel on this platform.
```

**★ 而 pip 读的是 wheel 内部 WHEEL 的 Tag，不是文件名——★ 所以只改文件名不够。**

## 三、★ 改了什么（诚实边界）

**★ 只重写 `numpy-1.26.2.dist-info/WHEEL` 那一个文本条目里的两行：**
```
- Tag: cp310-cp310-manylinux_2_17_aarch64
- Tag: cp310-cp310-manylinux2014_aarch64
+ Tag: cp310-cp310-android_21_arm64_v8a
+ Tag: cp310-cp310-android_21_arm64_v8a
```

**★ 其余 993 个条目按原字节复制，★ 一个二进制都没动。★ ★ 而【没有重新编译】。**

**★ ★ ★ 而要诚实说清三件事 ★ ★ ★**
```
① 【改过 tag 的 wheel 不再是官方原样】——★ 这一点必须让后来人知道
② 【能不能真在 Android 上跑通，要装完才知道】
③ 【它不能修「二进制本身不兼容」那类问题】——★ 那要开 buildPython 现场编
```

## 四、复算命令

```bash
cd <仓库根>
B=https://chaquo.com/pypi-13.1
SRC=numpy-1.26.2-cp310-cp310-manylinux_2_17_aarch64.manylinux2014_aarch64.whl
mkdir -p android/app/wheels
[ -f "android/app/wheels/$SRC" ] || \
  curl -s -o "android/app/wheels/$SRC" "$B/numpy/$SRC"
for p in "scipy/1.8.1/scipy-1.8.1-1-cp310-cp310-android_21_arm64_v8a.whl" \
         "soundfile/0.13.1/soundfile-0.13.1-0-cp310-cp310-android_24_arm64_v8a.whl"; do
  curl -s -o "android/app/wheels/$(basename $p)" "$B/$p"
done
python3 android/repack_numpy_wheel.py
mv android/app/wheels/numpy-1.26.2-patched-cp310-cp310-android_21_arm64_v8a.whl \
   android/app/wheels/numpy-1.26.2-0-cp310-cp310-android_21_arm64_v8a.whl
```

★ ★ ★ **★ 而那个 `-0-` 不能省 ★ ★ ★**
```
★ pip 的 wheel 文件名规范是：
★   {name}-{version}(-{build})?-{python}-{abi}-{platform}.whl
★ 而 build 必须是【数字】——
★   ★ 所以「文件名里加 patched 便于辨识」会让 pip 直接拒绝：
★   ERROR: Invalid build number: patched in '...'
★ ★ ★ ★ ★ ★ 而【可辨识性靠这份文档与那个脚本，★ 不靠文件名】★★ ★
```

★ **校验产物：**
```bash
python3 -c "
import zipfile
z = zipfile.ZipFile('android/app/wheels/numpy-1.26.2-0-cp310-cp310-android_21_arm64_v8a.whl')
w = [n for n in z.namelist() if n.endswith('dist-info/WHEEL')][0]
print(z.read(w).decode())
print([n for n in z.namelist() if 'openblas' in n])"
```
