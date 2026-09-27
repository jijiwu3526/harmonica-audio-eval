# 交接：Android 端打包与设备适配

> **读者**：接手「Android 端打包与设备适配」的人。
> **本文不讲界面。** 本仓库铁律：**不做 UI / 不做产品化**。这里只讲**内核在安卓上怎么跑、怎么构建、怎么排查**。
> **写于**：2026-09-27。
> **本文里的每个数字都来自实测**。凡是我没亲自跑过的，写「未验证」。

---

## 0. 先读这三条，否则会白干

1. **`harmonica_eval/**` 一行都不许改。** 内核是冻结资产。
2. **`android/app/src/main/python/probe.py` 不许改。** 它的四阶段是**判据的一部分**——你改了就没人能对照「改之前/之后」了。
3. **不许跑任何 git 写命令**（不 add / 不 commit / 不 checkout / 不 reset）。看状态用 `git status --porcelain`。

---

## 1. 五分钟跑通（逐条可复制）

### 1.1 前置条件

| 东西 | 本机实测值 | 怎么确认 |
|---|---|---|
| JDK | 17 | `java -version` |
| Gradle | 9.5.1（homebrew） | `gradle --version` |
| Android SDK | `sdk.dir` 指向 `/Users/Apple/Library/Android/sdk` | 看 `android/local.properties` |
| adb | 37.0.0 | `adb version` |
| 构建期 Python | **必须是 3.10** | 见下 |

**构建期 Python 是个硬约束。** `android/app/build.gradle:67` 写死了绝对路径：

```gradle
buildPython("/Users/Apple/miniconda3/envs/pythonprojectastudy/bin/python3.10")
```

实测（2026-09-27）：

```
$ /Users/Apple/miniconda3/envs/pythonprojectastudy/bin/python3.10 -V
Python 3.10.20
```

> **★ 换机器时最容易卡住的一步。** `app/build.gradle:56-66` 记了原因：开了 pip 块，Chaquopy 就要求构建期有对应版本的 Python，**而它按标准命令名去找 `python3.13` 然后 `python3`**——本机默认只有 3.13，两个都不是 3.10，于是报 `Couldn't find Python 3.10`。
> **★ 而且 Chaquopy 17.0 仓库的 arm64_v8a wheel 只有 cp310 能同时装下 numpy / scipy / soundfile**（实测索引里 numpy 有 cp39/cp310/cp311/cp312，但 scipy 与 soundfile 没那么全）。所以 `version = "3.10"` 是**被仓库内容逼出来的**，不是选来的。

### 1.2 设备（两台任选）

```bash
adb devices -l
```

两台的规格：

| 代号 | 型号 | API | ABI | 核 | 本文是否实跑过 |
|---|---|---|---|---|---|
| `a83b8ad` | PJD110 · OnePlus · Android 16 | 36 | arm64-v8a | 8 | **否**——本文写作时不在 adb 列表里 |
| `emulator-5554` | Pixel_7_API_34 | 34 | arm64-v8a | 4 | **是**——本文所有实测都在它上面 |

实测：

```
$ adb devices -l
List of devices attached
emulator-5554          device product:sdk_gphone64_arm64 model:sdk_gphone64_arm64 device:emu64a transport_id:19

$ adb -s emulator-5554 shell getprop ro.product.model
sdk_gphone64_arm64
$ adb -s emulator-5554 shell getprop ro.build.version.sdk
34
$ adb -s emulator-5554 shell getprop ro.product.cpu.abilist
arm64-v8a
$ adb -s emulator-5554 shell nproc
4
$ adb -s emulator-5554 shell getconf PAGE_SIZE
4096        ← 4KB 页，★ 所以不需要为 16KB 兼容强制 3.13+
```

**★ 两台都只有 arm64-v8a，与 `abiFilters` 一致。** `a83b8ad` 的数是引用清单里 2026-09-26 的实测，本文**未复跑**。

### 1.3 构建（★ 必须是 clean）

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval/android
gradle clean assembleDebug
```

**★ 判据是 APK 的 mtime 变了，不是 `BUILD SUCCESSFUL`。**

实测对照（2026-09-27，改完 `jniLibs` 之后）：

```
# 不带 clean
$ gradle assembleDebug
BUILD SUCCESSFUL in 1s
43 actionable tasks: 43 up-to-date
$ stat -f "%Sm" app/build/outputs/apk/debug/app-debug.apk
Sep 26 20:02:32 2026        ← 没变！packaging 根本没重跑

# 带 clean
$ gradle clean assembleDebug
BUILD SUCCESSFUL in 24s
45 actionable tasks: 45 executed
$ stat -f "%Sm" app/build/outputs/apk/debug/app-debug.apk
Sep 27 08:58:48 2026        ← 变了，这才算数
```

**★ `BUILD SUCCESSFUL in 1s` + `8 executed` / `43 up-to-date` 是假绿。** 判定方法固定用这一条：

```bash
stat -f "%Sm %z" app/build/outputs/apk/debug/app-debug.apk
```

### 1.4 安装 + 启动（★ 不要用 monkey）

```bash
adb -s <device> install -r android/app/build/outputs/apk/debug/app-debug.apk
adb -s <device> shell am start -n com.harmonica.probe/.MainActivity
```

实测：

```
$ adb -s emulator-5554 install -r android/app/build/outputs/apk/debug/app-debug.apk
Performing Streamed Install
Success

$ adb -s emulator-5554 shell am start -n com.harmonica.probe/.MainActivity
Starting: Intent { cmp=com.harmonica.probe/.MainActivity }
```

**★ 不要用 monkey。** 实测（2026-09-27，模拟器）：

```
$ adb -s emulator-5554 shell am force-stop com.harmonica.probe
$ adb -s emulator-5554 shell monkey -p com.harmonica.probe -c android.intent.category.LAUNCHER 1
 arg: "-p" ...
data="com.harmonica.probe"
** SYS_KEYS has no physical keys but with factor 2.0%.
        ↑ 没有 "Events injected: 1"  ← monkey 根本没注入事件

$ adb -s emulator-5554 shell dumpsys activity activities | grep topResumedActivity
topResumedActivity=ActivityRecord{... com.google.android.apps.nexuslauncher/.NexusLauncherActivity ...}
        ↑ App 根本没起来，停在桌面

$ adb -s emulator-5554 shell am start -n com.harmonica.probe/.MainActivity   # 换 am start
$ adb -s emulator-5554 shell dumpsys window | grep mCurrentFocus
  mCurrentFocus=Window{... com.harmonica.probe/com.harmonica.probe.MainActivity}
        ↑ 起来了
```

**★ monkey 失败看起来像「App 坏了」，其实是启动器的问题。** 遇到「App 起不来」先换 `am start` 再怀疑别的。

### 1.5 点按钮 + 拉日志

```bash
# 1) 看按钮在屏幕上的位置（★ 见 §7.5，别信 enabled/clickable）
adb -s <device> shell uiautomator dump /sdcard/ui.xml
adb -s <device> shell cat /sdcard/ui.xml | tr '>' '>\n' | grep Button

# 2) 点它。坐标从上面 dump 的 bounds 中心算
adb -s <device> shell input tap <x> <y>

# 3) ★ 判据：logcat 里出现「★ onClick 被调用」
adb -s <device> logcat -d | grep "★ onClick 被调用"

# 4) 拉 Python 侧完整日志
adb -s <device> logcat -d | grep "python.stdout"

# 5) ★ 落盘那份（见 §7.8 关于 base64 的更正）
adb -s <device> shell "run-as com.harmonica.probe base64 files/run.log" | base64 -d > run.log
```

实测按钮 bounds（模拟器 1080x2400）：

```xml
<node index="1" text="运行探针（阶段 0→3）" class="android.widget.Button" clickable="true" enabled="true"
      bounds="[63,301][1017,427]" />
<node index="2" class="android.view.View" resource-id="android:id/statusBarBackground" bounds="[0,0][1080,136]" />
```

中心 → `input tap 540 364`。实测响应：

```
09-27 08:56:47.188  9741  9741 I HarmonicaProbe: ★ onClick 被调用  按钮 enabled=true clickable=true
09-27 08:56:47.192  9741  9741 I HarmonicaProbe: startProbe 进入  按钮已置灰（★ 只有跑探针期间才这样）
09-27 08:56:47.195  9741  9836 I HarmonicaProbe: Python.getInstance() 成功  isStarted=true
09-27 08:56:47.259  9741  9836 I HarmonicaProbe: ★ getModule("probe") 成功  ★ 探针模块确实在，★ 要开始跑了
```

### 1.6 判据：12/12 端口

```bash
adb -s <device> logcat -d | grep "python.stdout" | grep "端口产出"
```

实测（模拟器，2026-09-27）：

```
[08:58:06.771] [stage3  ] ★ 端口产出 12/12：★ ['warp_path', 'pcm.mapped.reference', 'pcm.mapped.practice',
  'pcm.warped.practice', 'pitch.reference', 'pitch.practice', 'rms.reference', 'rms.practice',
  'chroma.lowres.reference', 'chroma.lowres.practice', 'notes.reference', 'notes.practice']
```

**看到这行 = 目标达成。** 跑通。

---

## 2. 架构：Chaquopy 怎么把 Python 塞进 APK

### 2.1 插件与版本（`android/build.gradle` + `app/build.gradle`）

```gradle
classpath 'com.android.tools.build:gradle:8.7.3'
classpath 'com.chaquo.python:gradle:17.0.0'
```

`app/build.gradle` 的 `android {}` 块：

| 项 | 值 | 说明 |
|---|---|---|
| `compileSdk` | 35 | |
| `minSdk` | 24 | |
| `targetSdk` | **35** | ★ 这个数字会强制 edge-to-edge，见 §7.5 |
| `abiFilters` | `arm64-v8a` | 全 ABI 会让 APK 翻数倍 |
| `debuggable` | `true` | ★ **硬要求**：`run-as` 靠它才能读到 app 私有目录 |
| `noCompress 'wav'` | | 4.4MB 的 wav 放在 assets 里 |
| Chaquopy `version` | `3.10` | 设备实测 `Python 3.10.19` |

**★ 本工程零 androidx 依赖**（`MainActivity extends android.app.Activity`）。Insets 走平台 API：API 30+ 用 `WindowInsets.getInsets(Type.systemBars())`，minSdk 24 的老设备走 `getSystemWindowInset*()` 分支。

### 2.2 APK 里有什么

实测 `unzip -l app-debug.apk`（APK 共 57 MB）：

```
lib/arm64-v8a/libpython3.10.so        3,484,592   ← CPython 本体
lib/arm64-v8a/libchaquopy_java.so       154,688   ← Java↔Python 桥
lib/arm64-v8a/libc++_shared.so        1,794,776   ← ★ 手工从 NDK 放的，见下
lib/arm64-v8a/libcrypto_python.so     3,721,048
lib/arm64-v8a/libsqlite3_python.so      886,520
lib/arm64-v8a/libssl_python.so          623,736
assets/chaquopy/app.imy             4,077,005   ← 你的 src/main/python/
assets/chaquopy/requirements-common.imy 33,141,679  ← ★ pip 装的那些包
assets/chaquopy/requirements-arm64-v8a.imy     22
assets/chaquopy/stdlib-arm64-v8a.imy  1,496,644   ← 标准库
assets/chaquopy/stdlib-common.imy    3,133,069
assets/chaquopy/bootstrap.imy          442,590
assets/chaquopy/build.json               1,833
assets/ref.wav                        4,410,044
```

`build.json` 里能直接读出 Python 版本与所有 assets 的 sha1：

```json
{
  "assets": { "app.imy": "2beab2084fdb7504145a556f579f75f51d649827", ... },
  "extract_packages": [],
  "python_version": "3.10"
}
```

**★ `.imy` 是 zip。** 非 `.py` 文件放进 `src/main/python/` 也会被打进 `app.imy`——实测 `ref.wav 4410044` 就在里面。

### 2.3 requirements 落在哪：`chaquopy { defaultConfig { pip { ... } } }`

`app/build.gradle:42-229` 的 pip 块**全部是包名，不是 whl 文件名**：

```gradle
chaquopy {
  defaultConfig {
    version = "3.10"
    buildPython("/Users/Apple/miniconda3/envs/pythonprojectastudy/bin/python3.10")
    pip {
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
      options '--no-deps'
      install 'harmonica-eval @ file://' + new File(rootDir, '..').absolutePath
    }
  }
}
```

**★ 三个容易搞错的点（都是实测踩出来的）：**

1. **pip 块挂在 `defaultConfig` 下面，不在 `chaquopy` 顶层。** 挂错层报 `Could not find method pip()`。依据：`javap` 读 `ChaquopyExtension`，`getDefaultConfig()` 返回 `PythonExtension`，`getPip()` 在它上面。
2. **`--no-deps` 必须有。** 不加它 pip 会去解析并拉 librosa。
3. **最后一行装本仓库包本体。** 实测 pip 在 Chaquopy 的构建 env 里**没有把 `[phone]` extras 的约束合并进来**（它仍按主 dependencies 解析，报的是 `scipy>=1.10` 而不是想装的 1.8）。所以改成**直接点名三个包 + `--no-deps`**，版本下限照 pyproject 的 phone 组。

### 2.4 `AssetFinder` 是什么

**Chaquopy 把 APK 里的 assets 虚拟成一个文件系统。** `import` 到的每个模块，其实来自 `files/chaquopy/AssetFinder/` 下的真实路径。

设备实测（`run.log` 的 `sys.path` 前三行）：

```
/data/data/com.harmonica.probe/files/chaquopy/AssetFinder/app
/data/data/com.harmonica.probe/files/chaquopy/AssetFinder/requirements
/data/data/com.harmonica.probe/files/chaquopy/AssetFinder/stdlib-arm64-v8a
```

对应关系：

| AssetFinder 目录 | 来自 APK 的 | 装了什么 |
|---|---|---|
| `app/` | `app.imy` | `src/main/python/` 的内容（`probe.py`、`ref.wav`） |
| `requirements/` | `requirements-common.imy` + `requirements-arm64-v8a.imy` | pip 块的十个包 |
| `stdlib-arm64-v8a/` | `stdlib-*.imy` | CPython 标准库 |
| `bootstrap-native/` | `bootstrap.imy` + 散装 `.so` | 启动期必须先 import 的扩展 |

设备实测 `app/` 与 `requirements/chaquopy/lib/` 的内容（经 `run-as` 读）：

```
$ adb -s <dev> shell "run-as com.harmonica.probe sh -c 'ls files/chaquopy/AssetFinder/app/'"
ref.wav

$ adb -s <dev> shell "run-as com.harmonica.probe sh -c 'ls files/chaquopy/AssetFinder/requirements/chaquopy/lib/'"
libFLAC++.so   libFLAC.so       libffi.so          libgfortran.so.3
libogg.so      libopenblas.so   libsndfile.so      libvorbis.so
libvorbisenc.so                libvorbisfile.so
```

**★ 这十个 so 在 `requirements/chaquopy/lib/`，不在 `lib/arm64-v8a/`。** 这是 §7.1 排查的关键。

**★ App 是首次启动时才解压的。** `am force-stop` 之后立刻去 `ls AssetFinder/app/` 会看到空目录——那是**探针时序错了**，不是「assets 没物化」。所以查文件之前先确认 App 起来过。

**★ 设备上没有独立 python 可执行。** 实测：

```
$ adb -s emulator-5554 shell "which python python3; ls /system/bin | grep -i python"
（空）
```

Chaquopy 是嵌入式的：`sys.executable` 报的是 `/system/bin/app_process64`（借 Android 的 app_process 启动 CPython）。

### 2.5 工作目录是 `/`，而 `/` 只读

**★ 这是安卓移植里最容易让人「看不见问题」的一条。**

设备实测 `run.log` 第一行组：

```
[boot    ] 初始日志文件 = /data/user/0/com.harmonica.probe/files/run.log
```

`os.getcwd()` 在 Chaquopy 下是 `/`，而根目录只读，于是：

| 写法 | 症状 |
|---|---|
| `open("run.log", "a")` | `OSError: [Errno 30] Read-only file system: '/run.log'` |
| `open("/ref.wav", "wb")` | `OSError: [Errno 30] Read-only file system: '/ref.wav'` |
| `open(os.getcwd()+"/x")` | `OSError: [Errno 2] No such file or directory` ← 上一版；**是「读不到」不是「写不进去」** |

**★ 但「读 assets」是 OK 的**——Chaquopy 对 `open()` 做了虚拟化。所以 `src/main/python/ref.wav` 用 `os.path.dirname(__file__)` 读**能成功**，`probe.py:179` 就是这么做的。

**写文件一律用 `os.environ["HOME"]` 下的相对路径。** 设备实测 `HOME=/data/user/0/com.harmonica.probe`，那是 app 私有目录，可写，debuggable 时 `run-as` 读得到。

**★ 而且失败的 except 绝不能 `pass`。** `probe.py:55-63` 的设计是：保留 `except OSError`（防止「日志写不进去」拖垮主流程），但**把失败打出来**。原先 `except OSError: pass` 造成的后果是——logcat 里明明有完整日志，而负责人 adb pull 时只看到一个「日志文件读不到」，**"写不进去"变成了"看不见"**。

---

## 3. 依赖链：为什么必须是 Android 件

### 3.1 那四个包各自为什么需要

| 包 | 为什么需要 |
|---|---|
| `numpy==1.26.2` | 全部端口的载体 |
| `soundfile==0.13.1` | `ingest` 读 wav |
| `chaquopy-openblas` | ★ `numpy/core/_multiarray_umath.so` 的 `DT_NEEDED` 里有 `libopenblas.so` |
| `chaquopy-libgfortran` | ★ `libopenblas.so` 的 `DT_NEEDED` 里有 `libgfortran.so.3` |

**实测的依赖链**（从二进制里读 `DT_NEEDED`，不是抄文档）：

```
numpy/core/_multiarray_umath.so (2,791,008 字节, aarch64, machine=183)
  NEEDED = libm.so · libpython3.10.so · libopenblas.so · libc++_shared.so · libdl.so · libc.so
  ↑ 六个全是 Android 名字，零 glibc
  │
  ├─ libopenblas.so     SONAME = libopenblas.so       8,766,736 字节
  │     NEEDED = libm.so · libgfortran.so.3 · libdl.so · libc.so
  │     METADATA: Requires-Dist: chaquopy-libgfortran (>=4.9)
  ├─ libgfortran.so.3   SONAME = libgfortran.so.3     1,522,520 字节
  │
  ├─ libc++_shared.so   ← jniLibs 里的 NDK 件（1,794,776 字节）
  └─ libm / libdl / libc / libpython3.10  ← 设备 / Chaquopy 自带
```

**★ 所以四件套是闭合的：**

```
_umath.so → libopenblas.so → libgfortran.so.3 → libm / libdl / libc（设备自带）
```

（scipy / cffi / soundfile 那几支的完整 `DT_NEEDED` 树在 `android/app/src/main/jniLibs/README.md`。）

### 3.2 为什么必须是 Android 件（★ 本节最核心）

**★ 一句话：文件名是症状，ABI 家族才是病。**

我今天（2026-09-27）自己把 PyPI 那个 manylinux wheel 的 ELF 拉出来读了 `DT_NEEDED`：

```
PyPI manylinux aarch64 numpy umath.so:
   NEEDED: libm.so.6
   NEEDED: libgcc_s.so.1
   NEEDED: libc.so.6

PyPI manylinux aarch64 numpy.libs/libopenblas64_...so:
   NEEDED: libm.so.6
   NEEDED: libpthread.so.0
   NEEDED: libgfortran-daac5196.so.5.0.0
   NEEDED: libc.so.6
   SONAME: libopenblas64_p-r0-17488984.3.23.dev.so
```

而**设备上只有** `libm.so` / `libc.so` / `libpthread.so`——**无 `.6` / `.0`**。那是 bionic 的命名。

**★ 同一个 `.so` 不可能既是 glibc 又是 bionic。** 所以：

- 改**文件名** → 没用（`DT_NEEDED` 是绝对引用）
- 改 **SONAME** → 没用（改的是自己叫什么，不是找谁）
- 改 **RPATH** → 没用（RPATH 管「去哪找」，不管「找到的能不能用」）
- 改 **tag 让 pip 认** → 能装上，**运行时照样 dlopen 失败**

**★ 唯一的解是重编译。** 而重编译这条路在本项目里也堵着——见 §8 结论 ①。

### 3.3 Chaquopy 官方索引

**★ `https://chaquo.com/pypi-13.1/` 里有全部原生库的 Android 件。** 实测索引 134 个目录。

实测（2026-09-27 直接 curl）：

```
$ curl -s "https://chaquo.com/pypi-13.1/chaquopy-openblas/" | grep -oE 'href="[^"]*arm64_v8a\.whl"'
href="chaquopy_openblas-0.2.20-5-py3-none-android_21_arm64_v8a.whl"

$ curl -s "https://chaquo.com/pypi-13.1/chaquopy-libgfortran/" | grep -oE 'href="[^"]*arm64_v8a\.whl"'
href="chaquopy_libgfortran-4.9-0-py3-none-android_21_arm64_v8a.whl"
```

**★ 十个包全在索引里，零手工重打包。** 完整清单与 sha256 在 `android/app/src/main/jniLibs/README.md`。

### 3.4 ★ 一个必须知道的坏件

**★ Chaquopy 仓库里那个 numpy 的 Android wheel 是坏件。** 它要 `libopenblas.so`，而 wheel 里 19 个 `.so` 里**没有一个是 BLAS** → `ImportError: dlopen failed: library "libopenblas.so" not found`。

**换版本换不掉**（引用清单的说法，2026-09-26 实测：arm64_v8a 只有 6 个，都缺 BLAS）。

**★ 但那个「6 个」的数已经过时。** 我今天（2026-09-27）重数了一遍：

```
$ curl -s "https://chaquo.com/pypi-13.1/numpy/" | grep -oE 'href="[^"]*arm64_v8a\.whl"' | wc -l
     11          ← arm64_v8a 件总数（引用清单说 6）
$ curl -s "https://chaquo.com/pypi-13.1/numpy/" | grep -oE 'href="[^"]*\.whl"' | wc -l
     40          ← 全部件
```

实际列表（`head -10`）：

```
numpy-1.17.4-3-cp38-cp38-android_21_arm64_v8a.whl
numpy-1.19.5-0-cp38-cp38-android_21_arm64_v8a.whl
numpy-1.20.3-0-cp39-cp39-android_21_arm64_v8a.whl
numpy-1.23.3-0-cp39-cp39-android_21_arm64_v8a.whl
numpy-1.23.3-0-cp310-cp310-android_21_arm64_v8a.whl
numpy-1.23.3-0-cp311-cp311-android_21_arm64_v8a.whl
numpy-1.26.2-0-cp39-cp39-android_21_arm64_v8a.whl
numpy-1.26.2-0-cp310-cp310-android_21_arm64_v8a.whl
numpy-1.26.2-0-cp311-cp311-android_21_arm64_v8a.whl
numpy-1.26.2-0-cp312-cp312-android_21_arm64_v8a.whl
...
```

**★ 上游会加件，所以「6 个都缺 BLAS」这个枚举随时可能过期。** **别把它当不变量**——要判断某个版本行不行，**只认一条判据：装完跑阶段 1，看 `numpy 1.x.y ✓` 有没有打出来**。症状只有两种（成 / 仍 dlopen），**都是真信息**。

**解法**：加 `chaquopy-openblas` + `chaquopy-libgfortran` 把缺口补上（§3.1）。**这才是本项目实际用的路。**

### 3.5 `libc++_shared.so` —— 唯一手工放的 .so

```
来自：本机 NDK 27.1.12297006
     toolchains/llvm/prebuilt/darwin-x86_64/sysroot/usr/lib/aarch64-linux-android/
处理：逐字节复制，未修改
实测：SONAME = libc++_shared.so
     NEEDED = libc.so · libm.so · libdl.so     ← 全是 Android 名字
```

**官方文档说「不需要装 NDK」——而那句话是关于 Chaquopy 自己的库。** Chaquopy 的 `abiFilters` 那节原文是 "There's no need to actually install the NDK, as all of Chaquopy's native libraries are already pre-compiled"——它没说 NDK 里有 `libc++_shared.so`，而我们最后正是从 NDK 拿的。

**★ 不许删它。** `numpy` 的 `DT_NEEDED` 里明确有它。

**★ 不许往 `jniLibs/` 里加同名 so。** 实测：**同名的以 jniLibs 优先。** 之前手工放的 25,804,257 字节的 glibc `libopenblas.so` 正是这样把 Chaquopy 的好件（8,766,736 字节）挡掉了。已删除，**勿恢复**。

---

## 4. 探针四阶段

文件：`android/app/src/main/python/probe.py`（**不许改**）。

### 4.1 每阶段在验什么

| 阶段 | 验什么 | 失败意味着 |
|---|---|---|
| **0** 解释器自检 | CPython 活了吗、`sys.path` 对不对 | 解释器没起来 / 版本不匹配 |
| **1** numpy/scipy/soundfile 全 import | ★ **最可能卡住的一环**：原生库齐不齐、ABI 对不对 | 缺 so / glibc 件 / tag 不认 |
| **2** ingest 读 50 秒音频 | 内核能读文件吗（只到 ingest，不碰 librosa） | assets 读不到 / HOME 写不进去 |
| **3** align + build_surface 物化 12/12 端口 | ★ **这才是本任务真正要回答的** | 数值/算法层的问题 |

每个阶段独立计时、异常带**完整 traceback**（`probe.py:110-121`），且**吞掉异常让后面阶段仍能跑**（`return True`）。所以「阶段 1 挂了」不会掩盖阶段 2 的独立问题。

### 4.2 真机正常输出（2026-09-26 实测，API 36 / 8 核）

```
阶段 0 解释器自检                              0.00s
阶段 1 numpy/scipy/soundfile 全部 import        0.47s
阶段 2 ingest 读 50 秒音频 shape=(2205000,) float32 峰值 0.7070   0.52s
阶段 3 align + build_surface 物化 12/12 端口   11.43s
    ├─ align         2.37s
    └─ build_surface 9.06s
```

### 4.3 模拟器（4 核）本次实测

```
$ adb -s emulator-5554 logcat -d | grep "python.stdout"   # 2026-09-27
[08:56:47.269] [stage0  ] ■ 完成 解释器自检  耗时 0.00s
[08:56:49.412] [stage1  ] ■ 完成 重依赖 numpy / scipy / soundfile  耗时 2.14s
[08:56:52.556] [stage2  ] ■ 完成 内核 ingest 读音频  耗时 3.14s
[08:58:06.772] [stage3  ] ■ 完成 align + build_surface 物化 12 个端口  耗时 74.22s
    ├─ align         11.41s
    └─ build_surface 62.78s
```

**★ 阶段 3 在模拟器上本次跑了 74.22s，而引用清单里写的是 11.70s。** 见 §8 结论 ⑤——**模拟器数字不能当基线**。

### 4.4 电脑对照（arm64 Mac · Python 3.13.13）

```
numpy 2.4.4 · scipy 1.17.1 · librosa 0.11.0
阶段 3 align 1.30s + build_surface 8.09s = 9.42s
峰值 RSS ≈ 620 MB
```

**★ 注意 `probe.py:217` 和 `:223` 的两行提示是错的**：

```python
log("stage3", "★ align 在电脑上就要十几秒，★ 手机上更慢。★ 别以为卡死")
log("stage3", "★ 下面 build_surface 会算全部 12 个端口，★ 电脑上 13.5 秒")
```

实测 align **1.30s**、build_surface **8.09s**。**★ 拿这两句当「卡死阈值」会判错。** （按红线我没改这个文件。）

### 4.5 设备性能对照表

| 环境 | 阶段 3 | 峰值内存 |
|---|---|---|
| 真机 API 36 / 8 核 | 11.43s | VmHWM ≈ **422 MB** |
| 模拟器 API 34 / 4 核 | 11.70s（引用值）**/ 74.22s（本次实测）** | VmHWM **341,500 kB → 401,584 kB**（本次实测） |
| 电脑 | 9.42s | ≈ 620 MB RSS |

**★ 真机 VmHWM 的取法**（方法本身要记下来，否则取不到真值）：

```bash
adb -s <dev> shell pidof com.harmonica.probe
adb -s <dev> shell cat /proc/<pid>/status | grep VmHWM
```

**★ 必须核对 `ETIME` 覆盖了运行全程。** `VmHWM` 是**历史峰值**，进程刚起来时读它只会拿到解释器启动那一小段的峰值（本次实测：点了按钮 30 秒后读是 340,628 kB，跑完再读是 401,584 kB）。读早了会低估。

**★ 模拟器 4 核 vs 真机 8 核**：模拟器数字还会被宿主 gradle / Xcode 占 CPU 干扰，所以**性能基线只认真机**。

---

## 5. 12 个端口

### 5.1 名字 / shape / 含义

**三处逐项相同，手机与电脑一致**（2026-09-27 模拟器实测 + 2026-09-26 真机实测 + 电脑基线）：

| # | port_id | shape | dtype | 含义 |
|---|---|---|---|---|
| 1 | `warp_path` | `(1083, 2)` | int32 | DTW 对齐路径：每行一对 (参考索引, 练习索引) |
| 2 | `pcm.mapped.reference` | `(2205000,)` | float32 | 参考侧 PCM（映射后） |
| 3 | `pcm.mapped.practice` | `(2205000,)` | float32 | 练习侧 PCM（映射后） |
| 4 | `pcm.warped.practice` | `(2205000,)` | float32 | 练习侧沿 warp_path 拉伸后的 PCM |
| 5 | `pitch.reference` | `(1076, 3)` | float32 | 参考侧基频轨迹 |
| 6 | `pitch.practice` | `(1076, 3)` | float32 | 练习侧基频轨迹 |
| 7 | `rms.reference` | `(8610,)` | float32 | 参考侧 RMS 包络 |
| 8 | `rms.practice` | `(8610,)` | float32 | 练习侧 RMS 包络 |
| 9 | `chroma.lowres.reference` | `(1077, 12)` | float32 | 参考侧低分辨率 chroma（12 音级） |
| 10 | `chroma.lowres.practice` | `(1077, 12)` | float32 | 练习侧低分辨率 chroma |
| 11 | `notes.reference` | `(25, 3)` | float32 | 参考侧音高聚合 |
| 12 | `notes.practice` | `(25, 3)` | float32 | 练习侧音高聚合 |

参考 2205000 = 50.000s × 44100 Hz。

### 5.2 ★ `surface.read()` 返回 `BufferView`，它没有 shape

`harmonica_eval/contract.py:382` 定义的 `BufferView` 是 frozen dataclass，字段只有三个：

```python
@dataclass(frozen=True)
class BufferView:
    data: npt.NDArray[Any] = field(repr=False)
    element_count: int
    element_type: str
```

**★ 没有 `shape`，也没有 `size`。** `probe.py:244-247` 有专门的分支处理这件事：

```python
if shape is None and size is None and hasattr(val, "element_count"):
    shape = getattr(val.data, "shape", None)     # ★ shape 在 val.data 上
    size = val.element_count
```

**★ 你要拿 shape，用 `val.data.shape`，不是 `val.shape`。**

设备实测输出长这样（注意 `size` 是**元素数**，不是字节）：

```
[08:58:06.762] [stage3  ]   ✓ warp_path                  BufferView   shape=(1083, 2) size=2166  BufferView 元素类型=int32
[08:58:06.762] [stage3  ]   ✓ pcm.mapped.reference       BufferView   shape=(2205000,) size=2205000  BufferView 元素类型=float32
[08:58:06.763] [stage3  ]   ✓ pitch.reference            BufferView   shape=(1076, 3) size=3228  BufferView 元素类型=float32
...
```

### 5.3 `manifest()` 也读了

```
[08:58:06.772] [stage3  ] manifest 类型 SurfaceManifest  条目 ★ 未知
```

`★ 未知` 是**正常的**——`SurfaceManifest` 没有 `__len__`，`probe.py:278` 的 `hasattr(mf,'__len__')` 为 False。电脑基线实测是 12 条 / `sealed=True` / `CORE_PROFILE_V0.1` / `AudioFormat(44100, 1, 'float32')`。

### 5.4 ★ 阶段 3 验的是「能否跑通」，不是「数值正确」

`probe.py:214` 的注释说「练习侧用参考**轻微失谐**」，**而实际代码是**：

```python
practice = ref_pcm[0] * 1.0     # ★ 完全相同，无失谐
```

**★ 两侧完全相同，DTW 退化成对角线。** 作为「能否跑通」的先验没问题，**但不能用它验数值正确性**。

---

## 6. 构建与安装

### 6.1 三个坑

**★ 坑 1：必须 `clean assembleDebug`。** 见 §1.3。

**★ 坑 2：不要用 monkey 启动。** 见 §1.4。

**★ 坑 3：拉 run.log 用 base64。** 见 §7.8（含我今天的实测更正）。

### 6.2 完整命令链

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval/android

# 1) 构建
gradle clean assembleDebug
stat -f "%Sm %z" app/build/outputs/apk/debug/app-debug.apk      # ★ 判据

# 2) 装
adb -s <device> install -r app/build/outputs/apk/debug/app-debug.apk

# 3) 启（★ 不要 monkey）
adb -s <device> shell am start -n com.harmonica.probe/.MainActivity

# 4) 判据 A：Java 侧活了
adb -s <device> logcat -d | grep -E "onCreate 进入|Python.start\(\) 成功"
#   实测输出：
#   I HarmonicaProbe: onCreate 进入  pid=9741  sdk=34  release=14  model=sdk_gphone64_arm64
#   I HarmonicaProbe: Python.start() 之前 isStarted=false
#   I HarmonicaProbe: Python.start() 成功返回  isStarted=true

# 5) 找按钮位置
adb -s <device> shell uiautomator dump /sdcard/ui.xml
adb -s <device> shell cat /sdcard/ui.xml | tr '>' '>\n' | grep Button

# 6) 点它
adb -s <device> shell input tap <x> <y>

# 7) 判据 B：点击送到了
adb -s <device> logcat -d | grep "★ onClick 被调用"

# 8) 判据 C：12/12
adb -s <device> logcat -d | grep "python.stdout" | grep "端口产出"

# 9) 落盘日志
adb -s <device> shell "run-as com.harmonica.probe base64 files/run.log" | base64 -d > run.log
```

### 6.3 判据清单（三条缺一不可）

| # | 判据 | 命令 | 期望 |
|---|---|---|---|
| A | APK 是新的 | `stat -f "%Sm" app/build/outputs/apk/debug/app-debug.apk` | mtime 是刚才 |
| B | 进程 + Python 活了 | `logcat -d \| grep "Python.start() 成功返回"` | 有这行 |
| C | **12/12 端口** | `logcat -d \| grep python.stdout \| grep 端口产出` | `★ 端口产出 12/12` |

**★ 只看 `BUILD SUCCESSFUL` 不算数。**（§1.3 实测）

---

## 7. 排查手册

### 7.1 dlopen 找不到 so

**症状**

```
ImportError: dlopen failed: library "libopenblas.so" not found
ImportError: dlopen failed: library "libffi.so" not found: needed by .../requirements/_cffi_backend.so in namespace clns-6
OSError: cannot load library 'libsndfile.so': dlopen failed
```

**★ 排查顺序（★ 一次读全 DT_NEEDED，别一轮补一个）**

```bash
# 1) 先看缺的 so 到底在不在
adb -s <dev> shell "run-as com.harmonica.probe sh -c 'ls files/chaquopy/AssetFinder/requirements/chaquopy/lib/'"
#    期望看到：libFLAC++ libFLAC libffi libgfortran.so.3 libogg libopenblas libsndfile libvorbis libvorbisenc libvorbisfile

# 2) ★ 一次读全那个 so 自己的 DT_NEEDED，再一次性装齐
#    （把上一步输出里的报错行展开——Chaquopy 会把 needed by ... 原文打出来）
```

实测六轮补齐的过程（**一次装齐比一轮补一个快得多**）：

| 轮 | 装了什么 | 新报错 | 缺的是 |
|---|---|---|---|
| 1 | openblas + libgfortran | `No module named 'scipy'` | scipy |
| 2 | + scipy | `No module named '_cffi_backend'` | cffi |
| 3 | + cffi | `dlopen: library "libffi.so" not found` | chaquopy-libffi |
| 4 | + chaquopy-libffi | `dlopen: library "libsndfile.so" not found` | chaquopy-libsndfile |
| 5 | + chaquopy-libsndfile | `library "libFLAC.so" not found` | flac / ogg / vorbis |
| 6 | + flac + ogg + vorbis | **阶段 1 全绿 ✓✓✓** | —— |

**★ 第 5→6 轮那一跳值得记**：报错把 `libsndfile.so` 自己的依赖原文写了出来，读那一个 so 的 `DT_NEEDED` 就一次装了三个。

**最可能的原因排序**

1. **pip 块少写了一行。** 这是 6 轮里 5 轮的原因。
2. **jniLibs 里有同名 so 把好件挡掉了。**（§3.5）
3. **App 没起来过，AssetFinder 还没解压。**（§2.4）
4. 装的是 glibc 件（见 §7.4）。

### 7.2 `RECORD int('')`

**症状**

```
ValueError: invalid literal for int() with base 10: ''
→ :app:installDebugPythonRequirements FAILED
```

**原因**：Chaquopy **按 RECORD 逐行读 size**。你往 wheel 里加了文件却没登记，就读不到 size → `int('')`。

**★ 三个连带条件：**

```
① RECORD 里必须包含所有新增条目
② ★ 哈希必须与【最终写入的内容】一致 —— zip 重写后压缩结果可能变，★ 所以【整份重算】
③ ★ 目录项【不登记】—— 登记目录项会让 Chaquopy 的 tree_add_path() 里
   `assert isinstance(subtree, dict)` 抛 AssertionError
   （★ 而那不是 so 命名规则的问题）
```

**★ 参考实现**：`android/repack_numpy_wheel.py` 的 `_record_line()` / `main()` 里那段。**RECORD 格式**：`<路径>,sha256=<urlsafe-b64-无padding>,<字节数>`，末行是 `RECORD` 自身 `路径,,`（size 本来就空，**那是合法的**）。

**★ 判断：先跑 `clean` 排除增量，再用 `repack_numpy_wheel.py` 里那套重算。**

### 7.3 扩展名带平台段不被认

**症状**：文件**在磁盘上存在**，却 `ModuleNotFoundError`——CPython 统一报成这个，看起来像「包没装」。

**原因**：**是 CPython 的 `EXTENSION_SUFFIXES` 决定的。** 那个列表按平台给，**而 Android 上没有**带 `aarch64-linux-gnu` 的形式。

**实测对照**（对照组选的是**真能工作的那些**，而不只是「看起来像的」）：

```
标准库里能 import 的：  _posixsubprocess.cpython-310.so
                       fcntl.cpython-310.so · select.cpython-310.so
装不上的这个：         _multiarray_umath.cpython-310-aarch64-linux-gnu.so
                        ↑ 就是这个破的
```

**★ 修法**：去掉文件名里的平台段（`repack_numpy_wheel.py` 第四处修改）。**★ 而 `numpy.libs/` 下的不动**——它们是共享库不是扩展模块，由 dlopen 按名字找，改名字会坏掉依赖解析。

**★ 还要查有没有 .py 硬编码了那个平台段**（`repack_numpy_wheel.py` 里有这条校验，命中就报「校验失败」）。

### 7.4 glibc vs bionic

**症状**：装得上、跑不了，`dlopen` 报找不到 `libc.so.6` / `libm.so.6` / `libpthread.so.0`。

**★ 根因一句话**：**文件名是症状，ABI 家族才是病。**

**自己验（不用信任何人）**：

```bash
# 把 .so 拉出来读 DT_NEEDED
adb -s <dev> shell "run-as com.harmonica.probe base64 files/chaquopy/AssetFinder/requirements/chaquopy/lib/libopenblas.so" \
  | base64 -d > /tmp/libopenblas.so
# 然后读它的 DT_NEEDED（readelf / objdump / 手写 struct 解析都行）
```

**判据**：`NEEDED` 里出现 `.so.6` / `.so.0` / `libgfortran-<hash>.so.5.0.0` 这类**带版本后缀**的名字 = glibc 件 = **在 Android 上必然失败**。

**★ 改文件名 / 改 SONAME / 改 RPATH 都改不了它内部对 `libc.so.6` 的引用。** 唯一的解是重编译，而重编译这条路在 Chaquopy 17 上是堵的（§8 结论 ①）。

**★ 正确做法只有一条**：从 `https://chaquo.com/pypi-13.1/` 取官方 Android 件。

**★ pip 报 `is not a supported wheel on this platform` 时要注意**：**pip 读的是 wheel 内部 `WHEEL` 的 `Tag`，不是文件名**——所以只改文件名是不够的。

### 7.5 按钮点不动

**★ 这条曾经最费时间，因为「证据」是假的。**

**★ 关键事实：`uiautomator` 报 `enabled=true clickable=true`，说的是【控件在视图树里】，不是【在屏幕上】。两条证据摆一起才对。**

**★ 根因两层：**

**① 真机状态栏 frame 盖住了按钮**

```
真机   a83b8ad / PJD110 / API 36 / 1440x3168
       状态栏      frame=[0,0][1440,160]
       标题 TextView bounds=[24,32][1416,141]   ← 整条都在状态栏底下
       按钮       bounds=[24,141][1416,333]    ← 顶 141 < 160，★ 被盖 19px
       而 taps 实测：按钮正中 (720,237) 敲下去，logcat 里
         「★ onClick 被调用」零命中 ——★ 点击被系统栏吃掉了

模拟器 emulator-5554 / Pixel_7 / API 34 / 1080x2400   ← 我今天实测
       状态栏  bounds=[0,0][1080,136]
       按钮    bounds=[63,301][1017,427]              ← 顶 301 > 136
```

**★ 为什么模拟器看不出来**：那个布局在模拟器上按钮顶边 301 > 136，躲过去了。**差很多像素，这就是「模拟器全绿、真机全废」的全部原因。**

**② `Theme.Material.Light` 带不透明 ActionBar，也压在内容上**

```
android:id/action_bar bounds = [0,160][1440,384]     ← 真机 dump
action_bar_root bounds 与 content 同区域
```

**★ 哪怕把 padding 加足，按钮仍会藏在 ActionBar 底下。只修 insets 是治了上面漏了下面。**

**★ 而「让系统不 overlay」这条路本来是死的：**

```
$ adb shell dumpsys window
  mAttrs pfl=... EDGE_TO_EDGE_ENFORCED
```

`targetSdk 35` 起系统**强制** edge-to-edge，**而 `decorFitsSystemWindows(true)` 在这个 flag 下不生效**。这是实测读出来的，不是推测。

**★ 修法（已落地）**

1. `root.setOnApplyWindowInsetsListener` 取 `systemBars() | displayCutout()` 的**实测值**；
2. **padding 取 `max(设计值, 系统给的)` 而不是相加**——相加会让「本来就不盖」的设备凭空多出一块空白；
3. 主题改 `Theme.Material.Light.NoActionBar`（`AndroidManifest.xml:22`）。

**修后按钮 bounds `[96,269][1344,461]`，顶边 269 > 160。**

**★ 判据：logcat 里出现「★ onClick 被调用」（TAG=`HarmonicaProbe`）。** 那是「点击到底送没送到」唯一无法伪造的证据——有了它，logcat 静默就只可能是「点击没送到」，而不再是两种可能。

**★ 排查模板**：

```bash
# A) 控件在不在视图树里
adb -s <dev> shell uiautomator dump /sdcard/ui.xml
adb -s <dev> shell cat /sdcard/ui.xml | tr '>' '>\n' | grep -E "Button|statusBarBackground|action_bar"

# B) 状态栏盖到哪
adb -s <dev> shell cat /sdcard/ui.xml | tr '>' '>\n' | grep statusBarBackground

# C) 平台有没有强制 edge-to-edge
adb -s <dev> shell dumpsys window | grep -i EDGE_TO_EDGE

# D) 点击到底送没送到（★ 决定性）
adb -s <dev> shell input tap <x> <y>; adb -s <dev> logcat -d | grep "★ onClick 被调用"
```

**★ MainActivity 的 `diag()` 会把这四条一起写进 logcat 与 `files/ui_state.txt`**（含 `getGlobalVisibleRect`），`onCreate` 结束和每次 `onResume` 都会打一次。

### 7.6 monkey 启动失败

见 §1.4。**一句话：用 `am start -n`，不要用 monkey。**

**★ monkey 在模拟器上会 `VM exiting with result code -5`（引用清单里的实测），我今天这次它连 `Events injected: 1` 都没打，App 停在桌面。两种都是启动器的问题，看起来却像「App 坏了」。**

### 7.7 gradle 增量不重跑

见 §1.3。**一句话：永远 `clean assembleDebug`，判据看 APK mtime。**

**★ 顺带一条**：`Couldn't find Python 3.10` 也是这一类——构建期找不到 3.10 时 pip 块会整块失败。解法在 §1.1（`buildPython` 指绝对路径）。

### 7.8 `adb exec-out` 拉二进制

**★ 引用清单说「必须 base64，adb exec-out 对二进制会截断」。**

**★ 我今天（2026-09-27）实测的更正——这个说法在 adb 37.0.0 / API 34 上没有复现：**

```
$ adb -s emulator-5554 exec-out run-as com.harmonica.probe cat files/run.log | wc -c
   2619
$ adb -s emulator-5554 shell "run-as com.harmonica.probe base64 files/run.log" | base64 -d | wc -c
   2619
$ diff <(plain) <(decoded) && echo IDENTICAL
IDENTICAL

# 二进制也一样
$ adb -s emulator-5554 exec-out run-as com.harmonica.probe cat files/ref.wav | wc -c
  4410044
$ adb -s emulator-5554 shell "run-as com.harmonica.probe base64 files/ref.wav" | base64 -d | wc -c
  4410044
$ wc -c < android/app/src/main/python/ref.wav
  4410044
```

**结论：`exec-out` 在这个版本上没有截断。但 base64 路线仍然推荐**，因为①它对 adb 版本不敏感，②它能发现「`run-as` 失败返回了错误文本」而不是静默给你半截文件。

**★ 但 base64 有个坑：设备上的 `base64` 是 toybox 版，参数和 macOS 不同。**

```
$ adb -s emulator-5554 shell "toybox base64 --help"
usage: base64 [-di] [-w COLUMNS] [FILE...]     ← 读文件用位置参数，不支持 -i/-o
```

**★ 正确写法（实测通过）**：

```bash
adb -s <dev> shell "run-as com.harmonica.probe base64 files/run.log" | base64 -d > run.log
```

**★ 错误写法（实测失败）**：

```bash
# ✗ 会报 base64: invalid argument —— 那不是 adb 的错，是本地 macOS 的 base64 在解码
adb -s <dev> exec-out run-as com.harmonica.probe sh -c 'base64 files/run.log' > /tmp/x.b64
base64 -d /tmp/x.b64
```

### 7.9 日志写不进去 / 看不到

**症状**：logcat 里明明有完整日志，但 `run-as ... cat files/run.log` 读不到。

**原因与修法**：见 §2.5。**★ 关键是这个 except 绝不能 `pass`。**

### 7.10 阶段 3 特别慢

**先分清是「慢」还是「卡死」。**

```bash
# ★ 必须核对 ETIME 覆盖了运行全程（§4.5）
adb -s <dev> shell cat /proc/<pid>/status | grep -E "VmHWM|VmRSS"
```

**★ 模拟器数字不可信**（§8 结论 ④⑤）。**性能判断只认真机。** 真机稳定在 11.43s（align 2.37s + build_surface 9.06s）。

**★ 电脑基线的成本分布**（做性能优化时看这个）：

| 生产者 | 单侧耗时 | 说明 |
|---|---|---|
| `materialize_pitch` | 3.41 s | pYIN，两侧各一次 → 约 6.8 s，**占 84%** |
| `materialize_notes` | 3.03 s | 音高+rms 聚合 |
| `_warp_by_index` | 0.63 s | 2205000 次 **Python 单层循环** |
| `materialize_rms` | 0.04 s | |
| `materialize_chroma` | 0.02 s | |

**★ 所以优化的主战场是 pYIN**，`chroma_stft` + `rms` 合计只占 0.06 s。

**★ 别在计时的同时开 `tracemalloc`。** 它会把 `align.compute_warp_path` 里那个 1083×1083 的**纯 Python 双重循环**放大 13 倍——实测 1.30s 被量成 17.7s。**那是方法上的错，不是项目的问题。**

---

## 8. ★ 已被推翻的结论（最值钱的一节）

**★ 这一节的目的是让你别重走。以下每条都有人走通过一遍。**

### ① 「开 `buildPython` 现场编 Android wheel」——作废

```
★ Chaquopy 17 编译 sdist 出来的是【宿主平台的件】
★ 实测 tag = macosx_26_0_arm64
★ 扩展后缀 = .cpython-310-darwin.so
```

**机制成立**（`options '--no-binary', 'numpy'` 确实让 pip 取 sdist 并现场编，实测 `Building wheel for numpy: started → done` 64 秒），**但目标是宿主**。

插件里没有交叉编译工具链——`gradle-17.0.0.jar` 里 `ANDROID_NDK` / `toolchain` / `sysroot` / `clang` / `cc1` **全部 0 命中**。

**★ 整条「开 buildPython 现场编 Android wheel」的路作废。** 官方件才是路（§3.3）。

**★ 诚实边界**：`buildPython` 那一行**不是没用**——它是因为 pip 块需要构建期 Python 才加的（§1.1），跟「现场编 Android wheel」是两回事。别把这两件事混起来。

### ② 「改文件名 / tag 让 pip 认就行」——作废

```
★ PyPI 的 aarch64 wheel 是 manylinux（glibc）
★ 引用 libm.so.6 / libc.so.6 / libpthread.so.0
★ 而设备上只有 libm.so / libc.so / libpthread.so
★ ★ 【同一个 so 不可能既是 glibc 又是 bionic】★★
★ → 【文件名是症状，ABI 家族才是病】
```

**★ 我今天自己读了那个 wheel 的 `DT_NEEDED` 复核**（§3.2）——`libm.so.6` / `libgcc_s.so.1` / `libc.so.6` 三个，`libopenblas` 那个还有 `libpthread.so.0` + `libgfortran-daac5196.so.5.0.0`。**四个全是 glibc 命名。**

**改文件名 / SONAME / RPATH 都改不了内部对 `libc.so.6` 的引用。只有重编能解，而重编被 ① 堵着。**

**★ 推论**：看到 `.so.6` / `.so.0` 这类带版本后缀的 `DT_NEEDED`，直接判死，别往下试。

### ③ 「librosa 装不上，所以手机跑不了」——已被复刻替代

```
librosa 装不上（拖 numba/llvmlite）
→ 已由 core/backend/ 用 numpy/scipy 复刻替代

实测：4 段真实录音上 pyin median|Δcents| = 0.0
      12 端口 10/12 content_hash 逐字节相同
      另 2 个 chroma 端口仅末位舍入（Pearson r 仍为 1.000000000000）
```

**★ librosa 现在是「预期内没装」，`probe.py:159-163` 主动探测并记录**：

```
[stage1  ] librosa 未装（★ 预期内：★ 它拖 numba/llvmlite）：No module named 'librosa'
```

**★ 这行日志出现 = 正常。** 出现别慌。

**★ 边界（电脑基线实测）**：`librosa 0.11.0` 的 pyin 里有 `np.random` 采样（Viterbi 起始分布），**跨版本不保证逐位一致**。手机替代实现产出不同 `content_hash` 是**可解释的**（算法不同），**不是 bug**——但必须显式承认，不能假装一致。

### ④ 「手机上慢 8 倍」——不成立

```
★ 那是模拟器 4 核 + 宿主 gradle 占 CPU
```

**真机 11.43s vs 电脑 9.42s**，差距是 21%，不是 8 倍。

**★ 性能对比只认真机。**

### ⑤ 「阶段 3 = 66.68s」——不成立

```
★ 模拟器抖 9.88s–80.07s，真机稳定在 11.43s
```

**★ 我今天的实测又一次落在区间里**：

```
模拟器本次：align 11.41s + build_surface 62.78s = 74.22s
引用清单：  模拟器 11.70s · 真机 11.43s
```

**★ 62.78s 落在 9.88–80.07s 区间内。** 模拟器的数字**没有稳定的基线值**，报的时候要连「哪台、几核、宿主负载」一起报。

---

## 9. 接下来能做什么

**★ 前提**：不越过「不做 UI / 不做产品化」这条铁律。下面每条都不涉及界面。

### 9.1 立刻能做的（低风险、高信息量）

**① 在真机 `a83b8ad` 上重跑一遍，刷新真机基线**

引用清单里的真机数是 2026-09-26 的。本文所有实测都在模拟器上做的（真机不在 adb 列表里）。**跑一遍把 11.43s / 422MB 这两个数复核一遍。**

```bash
adb -s a83b8ad install -r android/app/build/outputs/apk/debug/app-debug.apk
adb -s a83b8ad shell am start -n com.harmonica.probe/.MainActivity
adb -s a83b8ad logcat -d | grep "python.stdout" | grep 端口产出
adb -s a83b8ad shell "run-as com.harmonica.probe base64 files/run.log" | base64 -d > real_device.log
# 内存（★ 核对 ETIME 覆盖全程）
PID=$(adb -s a83b8ad shell pidof com.harmonica.probe | tr -d '\r')
adb -s a83b8ad shell cat /proc/$PID/status | grep VmHWM
```

**② 补上 `spec/2048` 之外的 ABI / minSdk 覆盖**

现在 `abiFilters` 只有 `arm64-v8a`，`minSdk 24`。**如果接手的机器上要覆盖更多设备**，先量清楚代价再动：全 ABI 会让 APK 翻数倍。**未验证**（本文没测过其它 ABI）。

**③ 把 §7 的排查表做成一个只读脚本**

本节八条排查项每条都是「命令 → 期望输出 → 不符时的下一步」。**写成脚本能省大量重复劳动。**（本仓库铁律第 4 条：零噪声，**不加未被要求的配置项/日志/兼容分支**——所以只做只读诊断，不加运行时开关。）

### 9.2 需要动内核的（先问负责人）

**④ 阶段 3 的 pYIN 优化**

电脑基线：`materialize_pitch` 占 84%（§7.10）。**`harmonica_eval/**` 是冻结的**——动它要负责人明确答复。

**⑤ 音频输入替换掉固定的 `ref.wav`**

`probe.py:179` 读的是 APK 里那个写死的 `ref.wav`。**要接真实录音需要改 `probe.py`——而它不许改。** 所以这条路要先解冻，或者新写一个探针文件（**不覆盖 `probe.py`**，让原判据保持可用）。

### 9.3 明确不要做的

| 别做 | 为什么 |
|---|---|
| 加 UI / 界面设计 | **铁律。** 仓库明令禁止 UI / 产品化。 |
| 改 `harmonica_eval/**` | 冻结资产。 |
| 改 `probe.py` | 四阶段是判据的一部分。 |
| 跑 git 写命令 | 看状态用 `git status --porcelain`。 |
| 恢复 `jniLibs/arm64-v8a/libopenblas.so` | ★ 已证明在设备上不可用，且**会挡掉 Chaquopy 的好件**（同名以 jniLibs 优先）。 |
| 删 `jniLibs/arm64-v8a/libc++_shared.so` | `numpy` 的 `DT_NEEDED` 里明确有它。 |
| 用 monkey 启动 | 会让「App 坏了」和「启动器坏了」混淆。 |
| 在计时的同时开 `tracemalloc` | 把 align 放大 13 倍。 |
| 把 wheel / so 加进 git | 二进制产物不进 git（`.gitignore` 已排除）。 |
| 拿模拟器数字当性能基线 | 4 核 + 宿主负载，方差巨大。 |

---

## 10. 附：文件地图

| 文件 | 作用 | 能改吗 |
|---|---|---|
| `android/app/build.gradle` | pip 块、SDK/ABI、buildPython 路径 | 能（依赖出问题改这里） |
| `android/build.gradle` | AGP 8.7.3 + Chaquopy 17.0.0 | 能 |
| `android/app/src/main/python/probe.py` | ★ 四阶段判据 | **不能** |
| `android/app/src/main/java/.../MainActivity.java` | 启 Python、取模块、insets 修法 | 能（但 insets 那段别乱动） |
| `android/app/src/main/AndroidManifest.xml` | ★ 主题必须是 `NoActionBar` | 能（别换回带 ActionBar 的） |
| `android/app/src/main/jniLibs/arm64-v8a/libc++_shared.so` | NDK 逐字节复制 | **不能删** |
| `android/app/src/main/jniLibs/README.md` | ★ 十个 so 的来源、sha256、依赖树、复算命令 | 能（加新 so 时更新） |
| `android/app/wheels/README.md` | 早期手工重打包路线的记录（**已作废，但有留档价值**） | 能 |
| `android/repack_numpy_wheel.py` | RECORD 重算 / tag 改写 / RPATH / 平台段的参考实现 | 能 |
| `android/ANDROID_PIP_STUDY.md` | ★ 六轮补齐的完整过程 + 被推翻的结论 | 能 |
| `_scratch/STAGE3_BASELINE_REPORT.md` | 电脑基线（含内存口径警告） | 能 |
| `harmonica_eval/**` | 内核 | **不能** |
