# ANDROID_PIP_STUDY —— 在 Chaquopy 上装 PyPI 科学计算包：实测结论

> ★ 2026-09-26 全程实测。设备：emulator-5554（API 34 · arm64-v8a）。
> ★ 零核心代码改动：`harmonica_eval/**` 全程一行没动。

## 结论一句话

**PyPI 上没有为 aarch64-Android 编的 openblas / libffi / libsndfile；那些件在 Chaquopy 的 pip 索引里。**

---

## 一、最终形态：numpy / scipy / soundfile 在设备上全部加载成功

### 设备实测（`run.log` 原文，完整不截断）

```
[boot    ] Python 3.10.19 · aarch64 · Linux
[stage0  ] ■ 完成 解释器自检  耗时 0.00s
[stage1  ] numpy 1.26.2 ✓
[stage1  ]   路径 /data/data/com.harmonica.probe/files/chaquopy/AssetFinder/requirements/numpy/__init__.py
[stage1  ] scipy 1.8.1 ✓
[stage1  ] soundfile 0.13.1 ✓
[stage1  ]   能读的容器 = ['AIFF','AU','AVR','CAF','FLAC','HTK','IRCAM','MAT4','MAT5',
                            'MPC2K','NIST','OGG','PAF','PVF','RAW','RF64','SD2','SDS',
                            'SVX','VOC','W64','WAV','WAVEX','WVE','XI']
[stage1  ] librosa 未装（预期内：它拖 numba/llvmlite）：No module named 'librosa'
[stage1  ] ■ 完成 重依赖 numpy / scipy / soundfile  耗时 0.43s
[stage2  ] 输入 /data/user/0/com.harmonica.probe/files/ref.wav  4410044 字节
[stage2  ] ingest 返回 ndarray  耗时 0.03s
[stage2  ]   shape=(2205000,)  dtype=float32
[stage2  ]   峰值 = 0.7070
[stage2  ]   时长 ≈ 50.00 秒（按 44100 估）
[stage2  ] ■ 完成 内核 ingest 读音频  耗时 0.42s
[stage3  ] ✗ 失败  ModuleNotFoundError: No module named 'librosa'
          阻断点：features.py:57 的 import librosa
```

### pip 块的最终形态

```gradle
install 'numpy==1.26.2'
install 'soundfile==0.13.1'
install 'chaquopy-openblas'
install 'chaquopy-libgfortran'
install 'scipy'
install 'cffi'
install 'chaquopy-libffi'
install 'chaquopy-libsndfile'
install 'chaquopy-flac'
install 'chaquopy-libogg'
install 'chaquopy-libvorbis'
options '--no-deps'      // 不加这个，pip 会去拉 librosa
```

十一行，全部来自 `https://chaquo.com/pypi-13.1/`，零手工重打包。

---

## 二、那七个 chaquopy 包是什么（逐条实测 DT_NEEDED）

```
numpy/core/_multiarray_umath.so   2,791,008 字节   aarch64   machine=183
  NEEDED = libm.so · libpython3.10.so · libopenblas.so
           · libc++_shared.so · libdl.so · libc.so
  六个全是 Android 名字，零 glibc
  而它在设备上真的加载成功了 —— run.log「numpy 1.26.2 ✓」
  │
  ├── libopenblas.so     SONAME = libopenblas.so       8,766,736 字节
  │     NEEDED = libm.so · libgfortran.so.3 · libdl.so · libc.so
  │     METADATA: Requires-Dist: chaquopy-libgfortran (>=4.9)
  ├── libgfortran.so.3   SONAME = libgfortran.so.3     1,522,520 字节
  ├── libc++_shared.so   ← jniLibs 里的 NDK 件
  └── libm / libdl / libc / libpython3.10   ← 设备或 Chaquopy 自带

_cffi_backend.so  →  libffi.so  →  chaquopy-libffi

libsndfile.so   SONAME = libsndfile.so
  NEEDED = libFLAC.so · libogg.so · libvorbis.so
           · libvorbisenc.so · libm.so · libdl.so · libc.so
  ├── libFLAC.so        (chaquopy-flac)
  ├── libogg.so         (chaquopy-libogg)
  ├── libvorbis.so      (chaquopy-libvorbis)
  └── libvorbisenc.so   (chaquopy-libvorbis)
```

**这十个 so 落在 `files/chaquopy/AssetFinder/requirements/chaquopy/lib/`，不在 `lib/arm64-v8a/`。**
（设备 `ls` 实测：libFLAC.so · libFLAC++.so · libffi.so · libgfortran.so.3 ·
libogg.so · libopenblas.so · libsndfile.so · libvorbis.so · libvorbisenc.so · libvorbisfile.so）

---

## 三、六轮「补一个 → 跑 → 看新缺口」

| 轮次 | 装了什么 | 新的实测报错 | 缺的是 |
|---|---|---|---|
| 1 | openblas + libgfortran | `numpy 1.26.2 ✓` → `No module named 'scipy'` | scipy |
| 2 | + scipy | `scipy 1.8.1 ✓` → `No module named '_cffi_backend'` | cffi |
| 3 | + cffi | `dlopen failed: library "libffi.so" not found` | chaquopy-libffi |
| 4 | + chaquopy-libffi | `dlopen failed: library "libsndfile.so" not found` | chaquopy-libsndfile |
| 5 | + chaquopy-libsndfile | `libsndfile.so` 找到了 → `library "libFLAC.so" not found` | flac/ogg/vorbis |
| 6 | + flac + ogg + vorbis | **阶段 1 全绿 ✓✓✓** | —— |

**第 5→6 轮那一跳值得记：**

```
★ 报错把 libsndfile 自己的依赖原文写了出来：
★   needed by .../chaquopy/lib/libsndfile.so in namespace clns-6
★ ★ 而我只读了那一个 so 的 DT_NEEDED，就一次装了三个 ★ ★
★ ★ 【一次读全 DT_NEEDED】比【一轮补一个】快得多 ★ ★
```

---

## 四、被推翻过的结论

| 曾经的结论 | 现在的结论 |
|---|---|
| 「Chaquopy 仓库里没有独立的 openblas 包」 | **错。** 错因：在 `gradle-17.0.0.jar` 里 grep，而 pip 索引不在 jar 里。实测索引 133 个目录里有 `chaquopy-openblas` 等七个 |
| 「改 wheel 手工重打包是可���路线」 | **错。** 直接在 pip 块里写包名即可，索引里就是官方件 |
| 「需要找 libffi / libsndfile 的 Android 件」 | **不需要找。** 索引里就有 `chaquopy-libffi` / `chaquopy-libsndfile` |
| 「Chaquopy 17 能自动编译 sdist」 | 机制成立但**目标平台是宿主**（`macosx_26_0_arm64`），对 Android 无用。绕开这条路即可 |
| 「clns-6 不搜 `AssetFinder/requirements/`，所以 chaquopy 的 so 找不到」 | **错。** Chaquopy 自己有办法让它们被找到（它会抽取到 `chaquopy/lib/` 并让 dlopen 成功） |

---

## 五、机制层面的实测事实

| 事实 | 证据 |
|---|---|
| `options '--no-binary', 'numpy'` 会让 pip 取 sdist | `Downloading numpy-1.26.2.tar.gz` → `Building wheel for numpy: started → done`（64 秒） |
| 而 Chaquopy 编出来的目标是**宿主** | wheel tag = `macosx_26_0_arm64`；扩展后缀 = `.cpython-310-darwin.so` |
| 插件里没有交叉编译工具链 | `gradle-17.0.0.jar`：`ANDROID_NDK`/`toolchain`/`sysroot`/`clang`/`cc1` 全部 0 命中 |
| `pip_options` 是原样透传的 | `pip_install.py:117-132`：`self.pip_options + reqs`；`grep "no_binary"` → 0 命中 |
| `install` 不带版本约束会取最新版 | 取到 `numpy-2.2.6`，而它要 Python 3.11+，Chaquopy 17 用 3.10 → **必须 pin** |
| 编译带 Fortran 的包需要本机 gfortran | `meson.build:80:0: ERROR: Unknown compiler(s): [['gfortran'], …]`，本机一个都没有 |
| **`src/main/python/` 里的非 .py 文件会打进 `app.imy`** | 放入 `ref.wav` 后 `unzip -l app.imy` 里出现了 `ref.wav 4410044` |
| **但 `open()` 读它能成功，写到 CWD 不行** | `Errno 2 No such file` → 改用 `os.path.dirname(__file__)` 读成功后变成 `Errno 30 Read-only file system: '/ref.wav'` |
| **写文件必须用 `os.environ["HOME"]` 下的路径** | 官方文档原话；改后 `ingest` 成功 |
| **jniLibs 的同名 so 优先于 chaquopy 的** | 装上 chaquopy-openblas 后 APK 里 `lib/arm64-v8a/libopenblas.so` 仍是 25,804,257（我手工放的），删掉才成功 |

---

## 六、官方文档与实现的三处偏差

```
① android.html 的 wheel 例子：install("MyPackage-1.2.3-py2.py3-none-any.whl")
   而纯文件名相对 app/ 解析 —— 官方写的是"相对项目目录"，两者差一层
   而那两个例子都不含子目录 —— 照抄官方的人踩不到

② abiFilters 那节："There's no need to actually install the NDK, as all of
   Chaquopy's native libraries are already pre-compiled"
   而那句话是关于 Chaquopy 自己的库 —— 它没说 NDK 里有 libc++_shared.so
   而我们最后正是从 NDK 拿的 libc++_shared.so

③ os 节：读文件要用相对 os.environ["HOME"] 的路径（当前目录在 Android 上只读）
   而那正是 run.log 落盘失败的官方依据
```

---

## 七、还在等定夺的事

```
★ 阶段 3 停在 features.py:57 的 import librosa
★ 而【features.py 只用 librosa 两处】：
★   features.py:155  librosa.pyin(...)
★   features.py:227  librosa.feature.chroma_stft(...)
★ ★ 而 core/README.md:180 的原话是：
★   「而 librosa 那两处（pyin / chroma_stft）都能用 numpy 手写替换」
★ ★ ★ 而【那是核心代码，★ 本轮不许动】★ ★

★ 下一步三个选项：
★   ① 开始做 librosa 替代（chroma_stft 自写 + pyin 备选，双实现运行时选）
★   ② 先在电脑上把阶段 3 跑通，作为对照基线
★   ③ 其他
```

---

## 附：本轮的探针错（留档，因为它们是本项目最防的那类）

```
① 下载 wheel 时用 `grep ... | head -1` 取了 armeabi_v7a（32 位），
   而 ELF 解析器只按 64 位写 → struct.error
   → 先怀疑探针，重写时加了 EI_CLASS 断言

② 用包名猜 URL（`${f%%-*}`），拿到 313 字节的 404 页，还当成 wheel 存了
   → 打印索引里的真实 href 才看见「href 是相对同目录的纯文件名」

③ `ls AssetFinder/app/` 显示空目录 → 我据此判断「app.imy 里的文件不物化」
   → 而那是在 `am force-stop` 之后跑的，Chaquopy 还没解压；探针时序错了

④ `cp src/main/assets/ref.wav src/main/python/ref.wav` 报 No such file
   → 前一条命令 `cd` 失败，路径相对错了；而我据此以为文件不存在

⑤ 改完 probe.py 只看构建成功就装 APK
   → 而 `gradle` 在 jniLibs 变了之后 1 秒返回 SUCCESSFUL，packaging 根本没重跑
   → 必须 `clean assembleDebug` 才重跑；且判据要看设备上的模块能不能用

⑥ ★ 这一条最贵：我把「Chaquopy 17 用 buildPython 就地编」写成了结论，
   而它编出来的是 macOS 件 —— 编译目标平台这一层我完全没想到
```

**★ 以及我自己往这份文档里写进了 1,485 行装饰噪声（223KB），当场发现并丢弃重写。★★ ★**
