# jniLibs 与 chaquopy 原生库 —— 来源、指纹、复算命令

> ★ **二进制产物不进 git**（与「音频不进 git」同理）。本文件记录来源，让后来人能复算。
> ★ 2026-09-26 实测：靠下面这七个 chaquopy wheel，numpy/scipy/soundfile 在设备上全部加载成功。

---

## 一、`app/src/main/jniLibs/arm64-v8a/`（打进 APK 的 `lib/arm64-v8a/`）

### 1. `libc++_shared.so`（1,794,776 字节）★ **必须保留**

```
★ 来自：本机 NDK 27.1.12297006
★   toolchains/llvm/prebuilt/darwin-x86_64/sysroot/usr/lib/aarch64-linux-android/
★ 处理：逐字节复制，未修改（cmp 核过）
★ 实测：SONAME = libc++_shared.so
★       NEEDED = libc.so · libm.so · libdl.so     ← 全是 Android 名字
★ ★ 设备实测：它从报错的序列里消失了 —— 那就是它生效的证据 ★ ★
★ 官方文档说「不需要装 NDK」★ ——★ 而那句话是关于 Chaquopy 自己的库 ★ ★
★ 　 而我们最后正是从 NDK 拿的 libc++_shared.so ★ ★
```

### 2. ~~`libopenblas.so`（25,804,257 字节）~~ ★ **已删除，勿恢复**

```
★ 来自：PyPI numpy wheel 内，只改了文件名
★ 实测：NEEDED = libm.so.6 · libpthread.so.0 · libgfortran-daac5196.so.5.0.0 · libc.so.6
★ ★ ★ 【它是 glibc 编的】——★ 设备上无 .so.6 / .so.0，★ 必然加载失败 ★ ★ ★
★ ★ ★ ★ 而【它在 APK 里会【把 chaquopy 的那个挡掉】】★★★★ ★
★ ★ 实测经过：装上 chaquopy-openblas 后，APK 里 lib/arm64-v8a/libopenblas.so
★ ★ 仍是 25,804,257 字节（我手工放的那个），而不是 chaquopy 的 8,766,736
★ ★ ★ ★ → 结论：【同名的以 jniLibs 优先】★★★ ★
★ ★ 删掉它之后，设备上 numpy 1.26.2 ✓ scipy 1.8.1 ✓ soundfile 0.13.1 ✓
```

---

## 二、`chaquopy-*` wheel（★ 缺口的那十块，★ 装进 AssetFinder）

**★ 这些 so 不在 `lib/arm64-v8a/`，★ 而在 `files/chaquopy/AssetFinder/requirements/chaquopy/lib/`。★★ ★**

设备实测 `ls` 输出（十个 so 全在那个目录里）：

```
libFLAC.so    libFLAC++.so   libffi.so     libgfortran.so.3
libogg.so     libopenblas.so libsndfile.so libvorbis.so
libvorbisenc.so              libvorbisfile.so
```

**★ 来源：`https://chaquo.com/pypi-13.1/<包名>/`（★ arm64_v8a 件）★★ ★**

| wheel | 字节 | sha256（前 32） |
|---|---:|---|
| `chaquopy_openblas-0.2.20-5-py3-none-android_21_arm64_v8a.whl` | 4,342,777 | `1e8e67a4f9e2fcde384890678bafbf7f` |
| `chaquopy_libgfortran-4.9-0-py3-none-android_21_arm64_v8a.whl` | 495,679 | `0b4caed1147f2a19707d4ba730afea57` |
| `chaquopy_libffi-3.3-1-py3-none-android_21_arm64_v8a.whl` | 35,618 | `dc60147da7a265a29515b968edf989d3` |
| `chaquopy_libsndfile-1.0.28-0-py3-none-android_21_arm64_v8a.whl` | 273,973 | `7615fb3f70852cc589b89b8c24e413f8` |
| `chaquopy_flac-1.3.3-0-py3-none-android_21_arm64_v8a.whl` | 426,053 | `531809959c017383a9c22e1861422590` |
| `chaquopy_libogg-1.3.4-0-py3-none-android_21_arm64_v8a.whl` | 23,705 | `49e5312de6c4b0af1c67226322e905a3` |
| `chaquopy_libvorbis-1.3.7-0-py3-none-android_21_arm64_v8a.whl` | 234,886 | `773c0795c54ad055e0cafcb74f99f696` |

**★ pip 块里只写包名，★ 不写 whl 绝对路径（★ 索引里就有）★★ ★**

### 依赖链（★ 全部自己读 DT_NEEDED，★ 不是抄文档）

```
numpy/core/_multiarray_umath.so (2,791,008 字节, aarch64, machine=183)
  NEEDED = libm.so · libpython3.10.so · libopenblas.so · libc++_shared.so · libdl.so · libc.so
  ★ ★ 六个全是 Android 名字，★ 零 glibc ★ ★
  ★ ★ 而【它在设备上真的加载成功了】—— run.log: "numpy 1.26.2 ✓" ★ ★
  │
  ├─ libopenblas.so        SONAME = libopenblas.so        8,766,736 字节
  │    NEEDED = libm.so · libgfortran.so.3 · libdl.so · libc.so   ★ 全 Android 名字 ★
  │    METADATA: Requires-Dist: chaquopy-libgfortran (>=4.9)
  ├─ libgfortran.so.3      SONAME = libgfortran.so.3      1,522,520 字节
  │
  ├─ libc++_shared.so      ← jniLibs 的 NDK 件
  └─ libm / libdl / libc / libpython3.10  ← 设备 / Chaquopy 自带

_cffi_backend.so  →  libffi.so

soundfile / _soundfile.so  →  libsndfile.so
                              NEEDED = libFLAC.so · libogg.so · libvorbis.so
                                       · libvorbisenc.so · libm.so · libdl.so · libc.so
                              ├─ libFLAC.so
                              ├─ libogg.so
                              ├─ libvorbis.so      → libogg.so
                              └─ libvorbisenc.so  → libogg.so · libm.so
```

### 复算命令

```bash
cd <仓库根>
for p in chaquopy-openblas chaquopy-libgfortran chaquopy-libffi \
         chaquopy-libsndfile chaquopy-flac chaquopy-libogg chaquopy-libvorbis; do
  B="https://chaquo.com/pypi-13.1/$p"
  F=$(curl -s "$B/" | grep -oE 'href="[^"]*android_21_arm64_v8a\.whl"' \
      | head -1 | sed 's/href="//;s/"//')
  curl -s -o "/tmp/$F" "$B/$F"
  shasum -a 256 "/tmp/$F"
done
```

---

## 三、★ 三个被删的 wheel 的指纹（★ 早期手工重打包路线，★ 已被 chaquopy 官方件取代）

```
numpy-1.26.2-0-cp310-cp310-android_21_arm64_v8a.whl
    4,987,182 字节  sha256 faa4bc08359820b2c3ba79bc60545c9bc4cd02f120da9fab5988bd1881865603
scipy-1.8.1-1-cp310-cp310-android_21_arm64_v8a.whl
    20,348,183 字节  sha256 e09bea5e6150c455027b5d3f57983658732474db9022ae83f3d483aed2b1b092
soundfile-0.13.1-0-cp310-cp310-android_24_arm64_v8a.whl
    26,824 字节      sha256 182eba9cf3ee082b8dc0aece4a3a4f11d62c177f5941f06434c0f59118155c67
```

**★ 来源都是 `https://chaquo.com/pypi-13.1/`。**
**★ 而【它们【没有】被装进 APK】——★ ★**
**★ 现在用的是 pip 直接从索引取的那几个。★★ ★**
（★ 本项目的结论：**绕开 whl 手工重打包，直接在 pip 块里写包名**★★ ★）

---

## 四、★ 不许做的事

```
★ 不许往 jniLibs/ 里【加同名 so】——★ 实测：★ 同名的以 jniLibs 优先，
★ 　 而我那个 glibc 的 libopenblas.so 正是这样【把 chaquopy 的好件挡掉了】★★ ★
★ 不许【恢复】那个 25,804,257 字节的 libopenblas.so ——★ 它已被证明在设备上不可用 ★ ★
★ 不许【删 libc++_shared.so】——★ numpy 的 DT_NEEDED 里明确有它 ★ ★
★ 不许把这些二进制【加进 git】
★ 不许【在 pip 块里写 whl 绝对路径】——★ 索引里就有官方件，★ 包名即可
```
