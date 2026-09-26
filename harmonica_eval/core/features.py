'''
FILE-ID:      FILE-103
COMPONENT:    COMP-C2 Audio Core
SPEC:         profile.MATERIALIZE · profile.PORTS · contract.FIELD_LAYOUTS

ROLE:
    预生成算法所需的全部逐帧/逐音特征：音高曲线、能量包络、低分辨率 chroma、
    逐音摘要。

INTENT:
    「Core 预生成」这一架构裁定的**落地处**。

    为什么不惰性现算（负责人裁定，不可推翻）：
        惰性计算要活下来必须定义一套协商协议
        （特征声明 → 解析 → 版本 → 缓存失效 → 算失败的语义）。
        一旦有了那套协议，**Core 的外部接口就成了插件需求的函数** ——
        正是「深组件」要消灭的反模式。
    故：**在 Seal 时把算法要的一切都算好。** 算法若需要额外数据，
    从 pcm.mapped.* 自己算，不许要求 Core 增加端口。

MUST:
    - 严格按 profile.PORTS 生成，端口名为键、形状与 dtype 与声明一致
    - 多维度端口的**字段顺序必须**取自 contract.FIELD_LAYOUTS（见下）
    - 音高必须是**绝对音高**（Hz），不得 chroma 化
    - 未发声帧的 f0 置 0 且 voiced=0（不要用 NaN —— 它会污染后续统计）

★ 依赖边界（★ 本节解释为何本文件 import librosa 合规）：
    - FILE-103-v1.md §3 的第三方允许清单明列：`numpy`、`numpy.typing`、
      `librosa`（0.11.0）—— ★ 故本文件 `import librosa`（:46）合规。
    - ★ 对照：`FILE-104-v1.md:138` 写有「禁止 import 任何音频 I/O 或解码库：
      soundfile、librosa、audioread…」，★ 但那一条位于 FILE-104 的
      【本文件依赖禁令】清单内，★ 约束目标是 `core/surface.py` 一个文件，
      ★ ★ 不是「整个 core 层的通用禁令」。
    - ★ core 各文件依赖面不同：align 只用 numpy+scipy（FILE-102 §3）、
      ingest 用 soundfile 解码（FILE-101 定其为独有职责）。
      ★ ★ 不可把某一文件的禁令推广到全层。
    - ★★ 2026-09-26 追加：librosa 拖 numba/llvmlite，Android 上没有 wheel，
      一条 `import librosa` 就能让整条阶段 3 停摆。故本文件改为**后端分派**
      （见下方 ACTIVE_BACKEND）：有 librosa 走 librosa，没有走
      `core.backend` 的 numpy/scipy 自写实现。两条路径的函数签名与返回值
      形状完全一致 ⇒「电脑上跑」与「手机上跑」是同一份代码的不同后端。
      ★ 两个调用点（pyin / chroma_stft）的参数值与语义一字未动。

MUST NOT:
    - 硬编码端口名列表（必须由 profile.PORTS 驱动）
    - 降采样后算音高（实测：22.05 kHz 下 D5 被判成 D4，恰好 −1200 音分）
    - chroma 化音高（chroma 八度不变，会把差一个八度的错音判成正确）
    - 在未发声帧上给出 f0 猜测值（宁可为 0 + voiced=0）

INPUT:
    samples: float32 mono PCM
    sample_rate: int

OUTPUT:
    各端口的 ndarray，键为 profile 中的 port_id

BUILD-INSTRUCTION:
    .spec/build/FILE-103-v1.md
'''

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from ..contract import FIELD_LAYOUTS, CoreBuildError, ErrorCode
from ..profile import ALIGN, AUDIO, MATERIALIZE
from .backend import chroma_stft as _native_chroma_stft
from .backend import pyin as _native_pyin

# ★★ 后端分派（★ 2026-09-26，★ 为了让 features 能在没有 librosa 的机器上跑）★★
#
# 目标平台是 Android：librosa 拖 numba/llvmlite，设备上没有 wheel，
# 探针跑阶段 3 时就倒在下面这个 `import librosa` 上 —— 一个模块拖垮整条阶段 3。
#
# 做法：**有 librosa 用 librosa，没有用自写实现。**
#   - `core.backend.chroma.chroma_stft` —— numpy/scipy 复刻 librosa 的
#     功率谱 → 12 音级高斯滤波器组 → norm=inf 归一化。
#   - `core.backend.pyin.pyin` —— numpy/scipy 复刻 pYIN：
#     差分函数 → 累积均值归一 → 抛物线插值 → 阈值下降候选 → Viterbi。
#
# ★ 两条路径的函数签名、参数语义、返回值形状**完全一致**：
#   chroma_stft → (n_chroma, n_frames) float32
#   pyin         → (f0, voiced_flag, voiced_prob)，三个 1-D、每帧一个值
#   故换机器换的是后端，不是语义。
#
# ★ 显式环境变量覆盖：设 DSH_FEATURE_BACKEND=native 强制走自写、
#   =librosa 强制走 librosa（用于对拍；缺 librosa 时设 librosa 会显式失败，
#   ★ 而不是悄悄退回自写 —— 静默退会把「没验证过」伪装成「跑通了」）。
import os as _os

_BACKEND_ENV = "DSH_FEATURE_BACKEND"
_backend_request = _os.environ.get(_BACKEND_ENV, "").strip().lower()

_librosa = None
if _backend_request != "native":
    try:
        import librosa as _librosa  # type: ignore[no-redef]
    except Exception:  # ★ ImportError 之外也兜住（librosa 的 import 链很重）
        if _backend_request == "librosa":
            raise
        _librosa = None

if _librosa is not None:
    ACTIVE_BACKEND: str = "librosa"

    def _pyin(**kwargs):
        """逐帧基频（librosa 后端）。签名与 core.backend.pyin.pyin 一致。"""
        return _librosa.pyin(**kwargs)

    def _chroma_stft(**kwargs):
        """12 音级能量（librosa 后端）。签名与 core.backend.chroma.chroma_stft 一致。"""
        return _librosa.feature.chroma_stft(**kwargs)

else:
    ACTIVE_BACKEND: str = "native"
    _pyin = _native_pyin
    _chroma_stft = _native_chroma_stft

ACTIVE_BACKEND_REASON: str = (
    f"DSH_FEATURE_BACKEND={_backend_request}" if _backend_request
    else ("import librosa 成功" if _librosa is not None
          else "import librosa 失败（Android/无 librosa 环境）→ 自写后端")
)
"""当前生效的后端与判定理由。**只用于诊断与对拍，不参与任何数值决策。**"""

MIN_STABLE_NOTE_SEC: float = 0.150
"""参与音准统计的最短音长（秒）。

短于此的音，周期数太少，f0 估计不可靠 —— 把它算进"走音比例"
会引入噪声而非信号。规格 §7 的「稳定音」即指达到此长度的音。
"""

VOICED_CONFIDENCE_FLOOR: float = 0.5
"""低于此置信度的帧视为未发声。

具体量纲由实现选用的估计器决定（如 pYIN 的 voiced_prob）。
这里只冻结**下游可依赖的语义**：confidence < floor ⇒ voiced == 0。
"""


def _reject_nonfinite(values: npt.NDArray, what: str) -> None:
    """非有限输入显式失败（§5），禁止让 NaN 污染下游统计。"""
    if not np.isfinite(values).all():
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            f"{what} 含 NaN 或 inf —— 显式失败，不降级",
        )


def _check_rate(sample_rate: int) -> None:
    if sample_rate <= 0:
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            f"sample_rate 必须为正，得到 {sample_rate}",
        )


def _as_mono_float32(samples: npt.NDArray, what: str) -> npt.NDArray:
    """规整成 1-D float32，并做非有限检查。"""
    _reject_nonfinite(samples, what)
    out = np.asarray(samples, dtype=np.float32)
    if out.ndim != 1:
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            f"{what} 必须是 1-D 单声道，得到 {out.ndim}-D",
        )
    return out


def _frame_count(n_samples: int, frame_length: int, hop_length: int) -> int:
    """帧数 = 1 + (n - frame) // hop；不足一帧时按补零语义产出 1 帧（§5）。

    ★ 帧数完全由「输入长度 ÷ 帧移」导出，**不写死任何 fps 数字**。
    实测 rms hop=256 → 172.3 fps、pitch hop=2048 → 21.5 fps，
    没有一个端口是 100 fps（FILE-203:361 的「100 Hz」是陈旧残留）。
    """
    if n_samples < frame_length:
        return 1
    return 1 + (n_samples - frame_length) // hop_length


def _rect_frames(x: npt.NDArray, n_frames: int, frame_length: int,
                 hop_length: int) -> npt.NDArray:
    """按矩形窗切帧并补齐到 n_frames 帧（不足处补零）。"""
    need = frame_length + (n_frames - 1) * hop_length
    if len(x) < need:
        x = np.pad(x, (0, need - len(x)))
    idx = np.arange(frame_length)[None, :] + hop_length * np.arange(n_frames)[:, None]
    return x[idx]


def materialize_pitch(samples: npt.NDArray, sample_rate: int) -> npt.NDArray:
    """生成逐帧音高曲线，形状 (n_frames, n_fields)。

    字段顺序 = contract.FIELD_LAYOUTS['pitch'] = (f0_hz, voiced, confidence)。

    ⚠ 绝对音高，不是 chroma。这是硬要求：
    chroma 是八度不变的，用它做音准会把「低了一个八度」判成完全正确。

    ⚠ 必须在 profile.AUDIO.sample_rate 上运行。不得为了速度降采样 ——
    实测证据：22.05 kHz 下同一段音频的 D5 会被判成 D4（−1200 音分）。

    未发声帧：f0_hz = 0, voiced = 0, confidence 如实报告。
    **不要用 NaN** —— 它会静默污染中位数/均值等后续统计。
    """
    _check_rate(sample_rate)
    x = _as_mono_float32(samples, "materialize_pitch 的 samples")
    n_fields = len(FIELD_LAYOUTS["pitch"])
    if x.size == 0:
        return np.zeros((0, n_fields), dtype=np.float32)

    n_frames = _frame_count(x.size, MATERIALIZE.pitch_frame_length,
                            MATERIALIZE.pitch_hop_length)
    try:
        # ★ 帧长须 ≥ 2×hop，否则 librosa 内部会告警；此处按 profile 声明，
        #   而非自选参数（§7「不引入未被 MATERIALIZE 声明的参数」）。
        # ★★ 调用点语义未动：只把 `librosa.pyin` 换成后端分派出的 `_pyin`，
        #   参数值、center、阈值口径全部保持原样（见 ACTIVE_BACKEND 说明）。
        f0, voiced_flag, voiced_prob = _pyin(
            y=x,
            sr=sample_rate,
            fmin=MATERIALIZE.fmin_hz,
            fmax=MATERIALIZE.fmax_hz,
            frame_length=MATERIALIZE.pitch_frame_length,
            hop_length=MATERIALIZE.pitch_hop_length,
            center=True,
        )
    except Exception as exc:  # 估计器内部失败 → 显式失败（§5）
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            f"pyin 估计失败：{exc}",
        ) from exc

    f0 = np.nan_to_num(np.asarray(f0, dtype=np.float64), nan=0.0,
                       posinf=0.0, neginf=0.0)
    prob = np.nan_to_num(np.asarray(voiced_prob, dtype=np.float64), nan=0.0,
                         posinf=1.0, neginf=0.0)
    prob = np.clip(prob, 0.0, 1.0)
    # ★ 阈值口径冻结：confidence >= floor ⇒ voiced == 1（等号视为发声）。
    voiced = (prob >= VOICED_CONFIDENCE_FLOOR).astype(np.float64)
    # ★ 未发声帧的 f0 强制 0 —— 绝不让估计器的猜测值漏出去（§7）。
    f0 = np.where(voiced > 0, f0, 0.0)

    n = min(len(f0), n_frames)
    out = np.zeros((n_frames, n_fields), dtype=np.float32)
    out[:n, 0] = f0[:n]
    out[:n, 1] = voiced[:n]
    out[:n, 2] = prob[:n]
    return out


def materialize_rms(samples: npt.NDArray) -> npt.NDArray:
    """生成逐帧 RMS 能量包络，形状 (n_frames,)。

    窗长/帧移取 profile.MATERIALIZE.rms_frame_length / rms_hop_length
    （刻意比音高窗密，以保留起音瞬态）。

    单位：线性 RMS。**不要在这里转 dB** —— 转 dB 是算法侧的表达选择。
    """
    x = _as_mono_float32(samples, "materialize_rms 的 samples")
    if x.size == 0:
        return np.zeros((0,), dtype=np.float32)

    n_frames = _frame_count(x.size, MATERIALIZE.rms_frame_length,
                            MATERIALIZE.rms_hop_length)
    frames = _rect_frames(x, n_frames, MATERIALIZE.rms_frame_length,
                          MATERIALIZE.rms_hop_length)
    out = np.sqrt(np.mean(np.square(frames.astype(np.float64)), axis=1))
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def materialize_chroma(samples: npt.NDArray, sample_rate: int) -> npt.NDArray:
    """生成低分辨率 chroma，形状 (n_frames, 12)。

    字段顺序 = contract.FIELD_LAYOUTS['chroma']，**bin 0 = C**（不是 A）。
    这个起点同样有歧义，故一并冻结。

    ⚠ 本端口的用途是**对齐与可复现**，明确**不作为评分依据**：
    chroma 八度不变，无法区分 C4 与 C5。
    保留在数据面里是为了让审查者能重跑对齐、验证 warp_path 不是凭空来的。
    """
    _check_rate(sample_rate)
    x = _as_mono_float32(samples, "materialize_chroma 的 samples")
    n_chroma = len(FIELD_LAYOUTS["chroma"])
    if x.size == 0:
        return np.zeros((0, n_chroma), dtype=np.float32)

    try:
        # ★ sr 必传：漏传会用 librosa 默认的 22050，频率轴整体错一倍且不报错。
        #   帧移取 ALIGN.hop_length（与 chroma.lowres.* 声明的 hop_length 一致）。
        # ★★ 调用点语义未动：只把 `librosa.feature.chroma_stft` 换成后端分派
        #   出的 `_chroma_stft`，参数值与返回形状口径保持原样。
        out = _chroma_stft(
            y=x,
            sr=sample_rate,
            n_fft=MATERIALIZE.frame_length,
            hop_length=ALIGN.hop_length,
            n_chroma=n_chroma,
            tuning=0.0,
            norm=np.inf,
            center=True,
        )
    except Exception as exc:
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            f"chroma_stft 失败：{exc}",
        ) from exc

    out = np.asarray(out, dtype=np.float32)
    if out.ndim != 2 or out.shape[0] != n_chroma:
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            f"chroma 输出形状异常：{out.shape}",
        )
    out = np.nan_to_num(out.T, nan=0.0, posinf=0.0, neginf=0.0)
    # ★ 静音帧整行为 0，不参与归一化（否则 0/0 → NaN）。
    norm = np.max(np.abs(out), axis=1, keepdims=True)
    live = norm[:, 0] > 0.0
    out[live] /= norm[live]
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def materialize_notes(
    pitch: npt.NDArray,
    rms: npt.NDArray,
    sample_rate: int,
) -> npt.NDArray:
    """生成参考侧逐音摘要，形状 (n_notes, n_fields)。

    字段顺序 = contract.FIELD_LAYOUTS['notes'] = (onset_sec, f0_hz, rms)。

    为什么需要它：它让算法能按**音**而不是按**帧**组织结果，
    从而输出「第 7 个音偏低 40 音分」这种**可定位**的结论，
    而不是「整体音准误差 40 音分」这种无法行动的数字。

    只对 voiced 且连续时长 ≥ MIN_STABLE_NOTE_SEC 的片段成音。
    """
    _check_rate(sample_rate)
    p = np.asarray(pitch, dtype=np.float32)
    r = np.asarray(rms, dtype=np.float32)
    n_fields = len(FIELD_LAYOUTS["notes"])

    if p.ndim != 2 or p.shape[1] != len(FIELD_LAYOUTS["pitch"]):
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            f"pitch 形状不符：{p.shape}（应为 (n_frames, "
            f"{len(FIELD_LAYOUTS['pitch'])}）",
        )
    if r.ndim != 1:
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            f"rms 必须 1-D，得到 {r.ndim}-D",
        )
    _reject_nonfinite(p, "materialize_notes 的 pitch")
    _reject_nonfinite(r, "materialize_notes 的 rms")

    # ★ §5 判定按序：无片段时**不检查 rms**（纯静音是合法输入，不该报错）。
    if p.shape[0] == 0:
        return np.zeros((0, n_fields), dtype=np.float32)

    hop = MATERIALIZE.pitch_hop_length
    rms_hop = MATERIALIZE.rms_hop_length
    voiced = p[:, 1] > 0.5
    if not voiced.any():
        return np.zeros((0, n_fields), dtype=np.float32)
    if r.size == 0:
        # ★ 有音却无能量帧 ⇒ 数据面自相矛盾，显式失败（§5 第 2 条）。
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            "rms 为空但 pitch 含有发声片段 —— 数据面自相矛盾",
        )

    # 1) voiced 列上的连续段切分
    edges = np.flatnonzero(np.diff(voiced.astype(np.int8)) != 0) + 1
    starts = np.concatenate(([0], edges))
    ends = np.concatenate((starts[1:], [len(voiced)]))
    rows = []
    for s, e in zip(starts, ends):
        if not voiced[s]:
            continue
        # 2) 片段时长 = 帧数 × pitch_hop ÷ sr；3) 丢弃 < MIN_STABLE_NOTE_SEC
        dur = (e - s) * hop / sample_rate
        if dur < MIN_STABLE_NOTE_SEC:
            continue
        # 4) onset 取首帧时间；f0 取片段内 voiced 帧中位数
        onset = s * hop / sample_rate
        f0_med = float(np.median(p[s:e, 0]))
        #    rms 取「时间上被片段覆盖」的帧的中位数（两侧帧移不同，按时间对齐）
        t0 = s * hop / sample_rate
        t1 = e * hop / sample_rate
        j = np.flatnonzero((np.arange(r.size) * rms_hop / sample_rate >= t0)
                           & (np.arange(r.size) * rms_hop / sample_rate < t1))
        if j.size == 0:
            # 片段短于 rms 帧移 → 取最近的一帧，不填充 0（§5 禁止用 0 掩盖）
            j = np.array([int(np.clip(round(t0 * sample_rate / rms_hop),
                                     0, r.size - 1))])
        rows.append((onset, f0_med, float(np.median(r[j]))))

    # 5) 按 onset 升序
    rows.sort(key=lambda t: t[0])
    if not rows:
        return np.zeros((0, n_fields), dtype=np.float32)
    return np.asarray(rows, dtype=np.float32)
