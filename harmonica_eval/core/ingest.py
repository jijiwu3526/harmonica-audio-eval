'''
FILE-ID:      FILE-101
COMPONENT:    COMP-C2 Audio Core
SPEC:         profile.AUDIO · COMPONENTS.md@v2 §3 · SPEC.md@v2.1 §2

ROLE:
    把任意可解码音频文件变成全系统统一的 PCM 表示。

INTENT:
    全系统只应有一处决定「什么算标准输入」。若各模块各自解码/重采样，
    采样率与声道数就会在不同路径上不一致 —— 而实测证明采样率会
    直接改变音高判定的结果（22.05 kHz 下 D5 被判成 D4，恰好 −1200 音分）。
    故标准化必须收敛到单一入口。

MUST:
    - 解码 → 下混单声道 → 重采样到 profile.AUDIO.sample_rate → float32
    - 校验时长落在 [min_duration_sec, max_duration_sec]，超出则**拒绝**
    - 校验非静音（整段 RMS 低于阈值 → INPUT_SILENT）
    - 失败抛 CoreBuildError，携带 contract.ErrorCode

MUST NOT:
    - 归一化音量（会破坏力度信息，而力度是算法要比较的量之一）
    - 去噪 / 增强 / 压缩动态（同上，且属于本项目边界之外）
    - 静默截断超长音频（必须拒绝，让调用方知道输入不合格）

★ 依赖边界（★ 本节解释为何本文件 import soundfile 合规）：
    - FILE-101-v1.md 把「解码 + 解码失败分类」定为本文件的【独有职责】，
      并要求采样率转换是【全系统唯一转换点】—— ★ ★ 音频 I/O 属本层职责，
      故本文件 `import soundfile`（:43）是规格要求，★ 而非违规。
    - ★ 对照：`FILE-104-v1.md:138` 的「禁止 import 任何音频 I/O 或解码库：
      soundfile、librosa、audioread…」位于该 BI 的【本文件依赖禁令】清单内，
      目标文件是 `core/surface.py`，★ ★ 不是全 core 层的通用禁令。
    - ★ core 各文件依赖面不同，不可把某一文件的禁令推广到全层。
    - 因为「顺便」而计算任何特征（特征属于 features.py）

INPUT:
    uri: str —— 音频文件路径

OUTPUT:
    (samples, sample_rate) —— float32 / mono / profile.AUDIO.sample_rate

BUILD-INSTRUCTION:
    .spec/build/FILE-101-v1.md
'''

from __future__ import annotations

import os.path

import numpy as np
import numpy.typing as npt
import soundfile
from scipy.signal import resample_poly

from ..contract import CoreBuildError, ErrorCode
from ..profile import AUDIO

SILENCE_RMS_THRESHOLD: float = 1e-4
"""判定「整段静音」的 RMS 阈值。

取 1e-4（约 −80 dBFS）而非严格 0：真实录音总有底噪，
严格判 0 会让"录了一段寂静"被当成有效输入。
单位：线性幅度（float32 归一化到 ±1.0 的刻度）。
"""


def decode_to_mono(uri: str) -> tuple[npt.NDArray, int]:
    """解码音频文件为单声道浮点数组（**源采样率，不重采样**）。

    返回 (samples, native_sample_rate)。

    为什么分成两步而不是一次做完：重采样是**有损且需要理由**的操作，
    把它与解码分开，可以让审查者看出「到底有没有发生重采样、从多少到多少」。

    下混用**算术平均**（`mean(axis=1)`）而非「只取第 0 声道」——
    后者会静默丢弃其他声道的信息，而用户以为整个文件被分析了。

    失败：
        文件不可读 / 格式不支持 → CoreBuildError(INPUT_UNREADABLE)
    """
    if not isinstance(uri, str) or not uri:
        raise CoreBuildError(
            ErrorCode.INPUT_UNREADABLE, f"uri 必须是非空字符串，得到 {type(uri).__name__}"
        )
    if not os.path.isfile(uri):
        raise CoreBuildError(ErrorCode.INPUT_UNREADABLE, f"路径不存在或不是普通文件：{uri}")

    try:
        with soundfile.SoundFile(uri) as sf:
            # SoundFile 实例的属性是 .samplerate；.info 是模块级函数的属性。
            native_sr = int(sf.samplerate)
            # always_2d=True：否则单声道返回一维、多声道返回二维，
            # 下混要写两个分支（规格明令禁止的分叉）。
            data = sf.read(frames=-1, dtype="float32", always_2d=True)
    except (soundfile.LibsndfileError, OSError, RuntimeError) as exc:
        raise CoreBuildError(
            ErrorCode.INPUT_UNREADABLE, f"解码失败：{uri}（{exc}）"
        ) from exc

    if native_sr <= 0:
        raise CoreBuildError(
            ErrorCode.INPUT_UNREADABLE, f"源采样率非法：{native_sr}（{uri}）"
        )

    # 对声道维取算术平均；单声道时是恒等操作。
    mono = data.mean(axis=1)
    # 不在此清理 NaN/inf —— 由 §4.4 的 RMS 计算暴露（规格 §4.4 已知缺口）。
    return np.ascontiguousarray(mono, dtype=np.float32), native_sr


def resample_to_profile(samples: npt.NDArray, native_sr: int) -> npt.NDArray:
    """把音频重采样到 profile.AUDIO.sample_rate。

    **不得下调采样率。** profile.AUDIO.sample_rate 的注释记录了实测原因：
    22.05 kHz 下 f0 会被判低八度（−1200 音分），这是结果的成因，不是优化项。
    native_sr == 目标采样率时直接返回副本（恒等变换，不引入损失）。

    用**多相滤波**（resample_poly）而非 FFT 法：FFT 法假设信号周期延拓，
    在文件首尾引入边界效应，而本仓对首尾各 0.4 s 静音有明确规格。
    """
    if native_sr <= 0:
        raise CoreBuildError(
            ErrorCode.INPUT_UNREADABLE, f"源采样率非法：{native_sr}"
        )
    if samples.ndim != 1:
        # 编程错误，不是用户输入错误
        raise ValueError(f"samples 必须是 1 维，实得 ndim={samples.ndim}")
    if samples.size == 0:
        return np.ascontiguousarray(samples, dtype=np.float32)

    if native_sr == AUDIO.sample_rate:
        # 恒等：返回副本，不经过滤波器
        return np.ascontiguousarray(samples, dtype=np.float32)

    # up/down 传原始整数，resample_poly 内部会约分；不手工约分。
    # 输出长度以库的行为为准（ceil(len * up / down)），不 pad/trim 凑整。
    out = resample_poly(samples, AUDIO.sample_rate, native_sr)
    return np.ascontiguousarray(out, dtype=np.float32)


def validate_duration(n_samples: int, sample_rate: int) -> float:
    """校验时长落在 profile.AUDIO 的允许区间，返回时长（秒）。

    阈值**必须**引用 AUDIO 常量，不写字面量（否则规格改了这里不会跟着改）。
    比较用 `<` 与 `>`，**不是** `<=` / `>=`：区间为**闭区间** [45.0, 120.0]，
    恰好 45.0 s 与恰好 120.0 s 是合法的。

    失败：
        短于 min_duration_sec → CoreBuildError(INPUT_TOO_SHORT)
        长于 max_duration_sec → CoreBuildError(INPUT_TOO_LONG)

    **超出上限必须拒绝，不得静默截断** —— 截断会让分析结果对应到一个
    用户并不知道的时间范围，而他以为整首都分析过了。
    """
    if sample_rate <= 0:
        # 编程错误
        raise ValueError(f"sample_rate 必须为正，实得 {sample_rate}")

    duration = n_samples / sample_rate
    if duration < AUDIO.min_duration_sec:
        raise CoreBuildError(
            ErrorCode.INPUT_TOO_SHORT,
            f"时长 {duration:.3f}s 短于下限 {AUDIO.min_duration_sec}s"
            f"（{n_samples} 样本 @ {sample_rate} Hz）",
        )
    if duration > AUDIO.max_duration_sec:
        raise CoreBuildError(
            ErrorCode.INPUT_TOO_LONG,
            f"时长 {duration:.3f}s 超过上限 {AUDIO.max_duration_sec}s"
            f"（{n_samples} 样本 @ {sample_rate} Hz）—— 拒绝截断",
        )
    return float(duration)


def assert_not_silent(samples: npt.NDArray) -> float:
    """校验整段非静音，返回整段 RMS。

    **必须先转 float64 再平方**：float32 平方在大动态范围下会累积误差，
    而本函数结果要与 1e-4 这个**绝对值**比较。

    用**整段** RMS 而非分帧：本函数只回答「这段录音整体是不是空的」，
    局部静音是**合法的**（乐句之间就有静音），属于算法层的分析对象。

    比较用 `<` 而非 `<=`：恰好等于阈值是合法的（语义如此；
    但从 float32 输入出发该值几乎不可达，见 FILE-101 §4.4 的说明）。

    失败：
        RMS < SILENCE_RMS_THRESHOLD → CoreBuildError(INPUT_SILENT)
    """
    if samples.size == 0:
        # mean(空) 产生 NaN 与警告；先判空直接抛
        raise CoreBuildError(ErrorCode.INPUT_SILENT, "空数组无 RMS，判为静音")

    rms = float(np.sqrt(np.mean(np.square(samples.astype(np.float64)))))
    if rms < SILENCE_RMS_THRESHOLD:
        raise CoreBuildError(
            ErrorCode.INPUT_SILENT,
            f"整段 RMS {rms:.3e} 低于阈值 {SILENCE_RMS_THRESHOLD:.3e}"
            f"（线性幅度，非 dBFS）",
        )
    return rms


def ingest(uri: str) -> npt.NDArray:
    """完整标准化流程：解码 → 下混 → 重采样 → 校验 → 返回 float32 mono。

    这是本模块唯一的对外入口。前四个函数是它的步骤分解，
    分开是为了让审查者能单独验证每一步（尤其是重采样与校验）。

    步骤顺序是规格的一部分：先重采样（才知道源采样率），再校验时长
    （用**重采样后**的长度与 AUDIO.sample_rate，即「最终产物的时长」）。

    失败：抛 CoreBuildError，code 取 INPUT_UNREADABLE / INPUT_TOO_SHORT /
        INPUT_TOO_LONG / INPUT_SILENT
    """
    samples, native_sr = decode_to_mono(uri)
    samples = resample_to_profile(samples, native_sr)
    validate_duration(samples.shape[0], AUDIO.sample_rate)
    assert_not_silent(samples)
    return samples
