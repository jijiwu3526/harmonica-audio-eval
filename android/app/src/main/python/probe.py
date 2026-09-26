"""手机探针：验证「harmonica_eval 能不能在 arm64 上跑起来」。

★ 负责人原话：「带足够的日志接口，★ 要不问题出在哪都不知道」
★ ★ ★ 而本文件就是那个日志接口的实现：★ 每阶段独立计时、输入摘要、
★ 输出形状、完整 traceback、落盘可 adb pull。

★ 阶段 0：Python 解释器活着吗
★ 阶段 1：重依赖装上了吗（★ 最可能卡住的一环）
★ 阶段 2：我们的内核能读音频吗（★ 只到 ingest，★ 不碰 librosa）
★ 阶段 3：12 个端口能不能物化（★ 那才回答「手机能不能吃下这份内核」）
"""

from __future__ import annotations

import io
import os
import platform
import sys
import time
import traceback
from datetime import datetime

# ★ 日志落盘位置。
# ★ ★ ★ 2026-09-26 实测更正：★ 原先写的是相对路径 "run.log"，
# ★ ★ ★ 而 Chaquopy 的工作目录是【根目录 /】，★ 且 / 在 Android 上【只读】：
# ★ ★ ★     touch: '/run.log': Read-only file system
# ★ ★ ★ 于是每次 open("run.log","a") 都抛 OSError，★ 而那个 except 又把它吞掉 ——
# ★ ★ ★ 【于是"写不进去"变成了"看不见"】，★ 而 logcat 里明明有完整日志。
# ★ ★ ★ ★ ★ 那正是负责人那句「带足够的日志接口」的字面缺口。
# ★ ★ ★ 改用 $HOME：★ 设备上实测 HOME=/data/user/0/com.harmonica.probe
# ★ ★ ★ 那是 app 私有目录，★ 可写，★ 而 debuggable 时 run-as 读得到。
LOG_NAME = os.path.join(os.environ.get("HOME", "."), "run.log")

_lines: list[str] = []
# ★ 落盘失败要说出来。★ 原先的 except OSError: pass 把「写不进去」变成
# 「看不见」——★ 而那正是本项目最防的假绿：★ logcat 里有完整日志，
# ★ 而负责人 adb pull 时只看到一个「日志文件读不到」。
# ★ 保留 except（★ 它防的是「日志写不进去就让主流程挂掉」，★ 那是好设计），
# ★ 但【失败必须可见】。
_log_write_error: str | None = None


def _stamp() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log(stage: str, msg: str) -> None:
    """一条日志：时间戳 + 阶段名 + 正文。★ 同时进内存与文件。"""
    global _log_write_error
    line = f"[{_stamp()}] [{stage:8s}] {msg}"
    _lines.append(line)
    try:
        with open(LOG_NAME, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        # ★ 只报一次，★ 不刷屏；★ 而它必须出现在 logcat 与界面里。
        if _log_write_error is None:
            _log_write_error = f"{type(exc).__name__}: {exc}"
            try:
                print(f"[{_stamp()}] [logerr  ] ★ 日志落盘失败："
                      f"{_log_write_error} ★ 目标 {LOG_NAME}")
            except Exception:
                pass
    try:
        print(line)
    except Exception:
        pass


def flush_log() -> None:
    """把内存里的行重新写一遍文件。★ 供 Java 侧主动调用。

    ★ 2026-09-26 更正：★ 原实现直接 open(...,"w") 而不捕获异常，
    ★ 而路径不可写时它会抛 ——★ 界面上就只看到一个 null。
    ★ 现在：★ 失败也要报出来，★ 且不吞掉。
    """
    try:
        with open(LOG_NAME, "w", encoding="utf-8") as fh:
            fh.write("\n".join(_lines) + "\n")
    except OSError as exc:
        try:
            print(f"[{_stamp()}] [logerr  ] ★ flush_log 失败："
                  f"{type(exc).__name__}: {exc} ★ 目标 {LOG_NAME}")
        except Exception:
            pass


def read_log() -> str:
    try:
        with open(LOG_NAME, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        return (f"★ 日志文件读不到：{type(exc).__name__}: {exc}"
                f" ★ 目标 {LOG_NAME}")


class Stage:
    """一个阶段的开始/结束/耗时。★ 异常必须带完整 traceback。"""

    def __init__(self, name: str, title: str) -> None:
        self.name = name
        self.title = title
        self.t0 = 0.0

    def __enter__(self) -> "Stage":
        self.t0 = time.time()
        log(self.name, f"▶ 开始 {self.title}")
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        dt = time.time() - self.t0
        if exc_type is None:
            log(self.name, f"■ 完成 {self.title}  耗时 {dt:.2f}s")
            return False
        # ★ 完整 traceback，★ 不能只打 e.message ——★ 那是「不知道哪出错」的直接成因
        log(self.name, f"✗ 失败 {self.title}  耗时 {dt:.2f}s")
        log(self.name, f"  异常类型 {exc_type.__name__}: {exc}")
        for line in traceback.format_exception(exc_type, exc, tb):
            for l in line.rstrip().splitlines():
                log(self.name, "  " + l)
        return True  # ★ 吞掉异常，★ 让后面的阶段仍能跑


def run() -> None:
    _lines.clear()
    try:
        os.remove(LOG_NAME)
    except OSError:
        pass

    log("boot", f"Python {sys.version.split()[0]} · {platform.machine()} · {platform.system()}")
    log("boot", f"sys.executable = {sys.executable}")
    log("boot", f"可执行位 = {os.access(sys.executable, os.X_OK)}")
    log("boot", f"线程数上限 = {__import__('os').cpu_count()} 核")
    # ★ 手机上的关键事实：★ 16 KB 页设备要 Python 3.13+（Chaquopy 官方说明）
    log("boot", f"初始日志文件 = {os.path.abspath(LOG_NAME)}")

    # ── 阶段 0：解释器 ───────────────────────────────────────────
    with Stage("stage0", "解释器自检"):
        log("stage0", "hello from python")
        log("stage0", f"sys.path 前三 = {sys.path[:3]}")

    # ── 阶段 1：重依赖 ───────────────────────────────────────────
    with Stage("stage1", "重依赖 numpy / scipy / soundfile"):
        import numpy
        log("stage1", f"numpy {numpy.__version__} ✓")
        log("stage1", f"  路径 {numpy.__file__}")

        import scipy
        log("stage1", f"scipy {scipy.__version__} ✓")

        import soundfile as sf
        log("stage1", f"soundfile {sf.__version__} ✓")
        fmts = sf.available_formats()
        log("stage1", f"  能读的容器 = {sorted(fmts)}")

        # ★ librosa 故意不装。★ 这里【主动】探测并记录，★
        # ★ 让「没装」成为一条【可见的日志】而不是一句失败。
        try:
            import librosa  # noqa: F401
            log("stage1", f"librosa {librosa.__version__} （★ 装了，★ 但这不是本任务的目标）")
        except ImportError as exc:
            log("stage1", f"librosa 未装（★ 预期内：★ 它拖 numba/llvmlite）：{exc}")

    # ── 阶段 2：内核读音频 ───────────────────────────────────────
    ref_pcm: list = []
    with Stage("stage2", "内核 ingest 读音频"):
        from harmonica_eval.core import ingest

        # ★ 把 assets 里的 wav 落到 app 私有目录，★ 因为 ingest 读文件系统路径
        # ★ （实测签名 ingest(uri: str) -> npt.NDArray，★ 返回的是裸数组而非对象）
        # ★ 2026-09-26 设备实测修正（★★ 两次探针错，★ 判据都是这条）：★★ ★
        # ★  os.getcwd() 在 Chaquopy 下是 '/'，★ 而根目录【只读】——
        # ★    OSError: [Errno 30] Read-only file system: '/ref.wav'
        # ★  （★ 上一版用 os.getcwd() 时报的是 Errno 2 No such file，
        # ★    那是【读不到】；★ 现在【读得到】了，★ 只剩【写不进去】）
        # ★ 而读【本来就没问题】：★ Chaquopy 的 AssetFinder 对 open() 做了虚拟化，
        # ★   所以 src 仍用 __file__ 同目录 ★ ——★ 那 4.4MB 的 wav 能 open 成功
        src = os.path.join(os.path.dirname(__file__), "ref.wav")
        # ★ 官方文档原话：Don't pass a simple filename to functions which write
        # ★ a file… use a path relative to os.environ["HOME"]
        home = os.environ.get("HOME") or "."
        dst = os.path.join(home, "ref.wav")
        if not os.path.exists(dst):
            with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
                fdst.write(fsrc.read())
        size = os.path.getsize(dst)
        log("stage2", f"输入 {dst}  {size} 字节")

        t = time.time()
        pcm = ingest.ingest(dst)
        dt = time.time() - t
        ref_pcm.append(pcm)
        # ★ 输出形状摘要 ——★ 「几行几列」比「成功」有用得多
        log("stage2", f"ingest 返回 {type(pcm).__name__}  耗时 {dt:.2f}s")
        log("stage2", f"  shape={getattr(pcm, 'shape', None)}  dtype={getattr(pcm, 'dtype', None)}")
        import numpy as _np
        log("stage2", f"  峰值 = {float(_np.max(_np.abs(pcm))):.4f}")
        log("stage2", f"  时长 ≈ {len(pcm)/44100:.2f} 秒（按 44100 估）")

    # ── 阶段 3：12 个端口 ─────────────────────────────────────────
    with Stage("stage3", "align + build_surface 物化 12 个端口"):
        import numpy as _np
        from harmonica_eval.core import align as _align
        from harmonica_eval.core import surface as _surface
        from harmonica_eval.profile import PORTS, MATERIALIZE

        sr = MATERIALIZE.sample_rate if hasattr(MATERIALIZE, "sample_rate") else 44100
        log("stage3", f"sample_rate 取自 profile = {sr}")
        log("stage3", f"profile 声明 {len(PORTS)} 个端口")

        # ★ 练习侧用参考轻微失谐，★ 造出「有差异」的情形
        # ★ 而若两边完全相同，★ DTW 会退化成对角线，★ 测不出东西。
        practice = ref_pcm[0] * 1.0
        log("stage3", f"练习侧复用参考（★ 先验「相同输入能否跑通」★ 不追求数值差异）")

        log("stage3", "★ align 在电脑上就要十几秒，★ 手机上更慢。★ 别以为卡死")
        t = time.time()
        warp_path = _align.align(ref_pcm[0], practice)
        log("stage3", f"align 完成  耗时 {time.time()-t:.2f}s")
        log("stage3", f"  warp_path shape={getattr(warp_path,'shape',None)} dtype={getattr(warp_path,'dtype',None)}")

        log("stage3", "★ 下面 build_surface 会算全部 12 个端口，★ 电脑上 13.5 秒")
        t = time.time()
        built = _surface.build_surface(ref_pcm[0], practice, sr, warp_path)
        log("stage3", f"build_surface 完成  耗时 {time.time()-t:.2f}s")
        log("stage3", f"  返回 {type(built).__name__}")

        # ★★ 这才是本任务真正要回答的：★★ ★ 12 个端口有没有真的产出
        got = []
        for p in PORTS:
            pid = p.port_id
            try:
                val = built.read(pid)
                # ★ read() 的返回形态不固定（数组 / 结构体 / 元组），
                # ★ 所以形状要【逐类探测】，★ 否则满屏 shape=None 等于没打
                shape = getattr(val, "shape", None)
                size = getattr(val, "size", None)
                extra = ""
                # ★★ 2026-09-26 修正：★ surface.read() 返回的是 BufferView
                # ★★ （contract.py:382），★ 而它【没有 shape / size】——
                # ★★ 三个字段是 data / element_count / element_type。
                # ★★ 不加这个分支，★ 12 行会全落到 else，★ 端口形状打不出来。
                if shape is None and size is None and hasattr(val, "element_count"):
                    shape = getattr(val.data, "shape", None)
                    size = val.element_count
                    extra = "  BufferView 元素类型=%s" % (val.element_type,)
                elif shape is None and size is None:
                    if isinstance(val, tuple):
                        extra = "  tuple len=%d  元素类型=%s" % (
                            len(val), [type(v).__name__ for v in val][:4])
                    elif isinstance(val, dict):
                        extra = "  dict keys=%s" % list(val)[:5]
                    elif isinstance(val, list):
                        extra = "  list len=%d" % len(val)
                    else:
                        fields = getattr(type(val), "__dataclass_fields__", None)
                        if fields:
                            inner = {}
                            for fn in list(fields)[:6]:
                                try:
                                    inner[fn] = getattr(val, fn)
                                except Exception:
                                    inner[fn] = "★读不了"
                            extra = "  dataclass %s" % {
                                k: (getattr(v, "shape", v)) for k, v in inner.items()}
                        else:
                            extra = "  %s" % type(val).__name__
                got.append(pid)
                log("stage3", f"  ✓ {pid:26s} {type(val).__name__:12s} shape={shape} size={size}{extra}")
            except Exception as exc:
                log("stage3", f"  ✗ {pid:26s} {type(exc).__name__}: {str(exc)[:70]}")
        log("stage3", f"★ 端口产出 {len(got)}/{len(PORTS)}：★ {got}")

        # ★ manifest 若有，★ 一并记下来（★ 那是端口的权威清单）
        try:
            mf = built.manifest()
            log("stage3", f"manifest 类型 {type(mf).__name__}  条目 {len(mf) if hasattr(mf,'__len__') else '★ 未知'}")
        except Exception as exc:
            log("stage3", f"manifest 读取失败（★ 非致命）：{type(exc).__name__}: {str(exc)[:60]}")

    # ── 收尾 ────────────────────────────────────────────────────
    log("done", "★ 全部阶段结束。★ 拉日志：")
    log("done", "  adb exec-out run-as com.harmonica.probe cat files/run.log > run.log")
    flush_log()


if __name__ == "__main__":
    run()
