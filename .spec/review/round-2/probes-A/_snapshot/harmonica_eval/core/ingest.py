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
    - 因为「顺便」而计算任何特征（特征属于 features.py）

INPUT:
    uri: str —— 音频文件路径

OUTPUT:
    (samples, sample_rate) —— float32 / mono / profile.AUDIO.sample_rate

BUILD-INSTRUCTION:
    .spec/build/FILE-101-v1.md
'''

from __future__ import annotations

import numpy.typing as npt

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

    失败：
        文件不可读 / 格式不支持 → CoreBuildError(INPUT_UNREADABLE)
    """
    raise NotImplementedError("SHELL: FILE-101 待注入实现")


def resample_to_profile(samples: npt.NDArray, native_sr: int) -> npt.NDArray:
    """把音频重采样到 profile.AUDIO.sample_rate。

    **不得下调采样率。** profile.AUDIO.sample_rate 的注释记录了实测原因：
    22.05 kHz 下 f0 会被判低八度（−1200 音分），这是结果的成因，不是优化项。
    native_sr == 目标采样率时应当直接返回（不引入重采样损失）。
    """
    raise NotImplementedError("SHELL: FILE-101 待注入实现")


def validate_duration(n_samples: int, sample_rate: int) -> float:
    """校验时长落在 profile.AUDIO 的允许区间，返回时长（秒）。

    失败：
        短于 min_duration_sec → CoreBuildError(INPUT_TOO_SHORT)
        长于 max_duration_sec → CoreBuildError(INPUT_TOO_LONG)

    **超出上限必须拒绝，不得静默截断** —— 截断会让分析结果对应到一个
    用户并不知道的时间范围，而他以为整首都分析过了。
    """
    raise NotImplementedError("SHELL: FILE-101 待注入实现")


def assert_not_silent(samples: npt.NDArray) -> float:
    """校验整段非静音，返回整段 RMS。

    失败：
        RMS < SILENCE_RMS_THRESHOLD → CoreBuildError(INPUT_SILENT)
    """
    raise NotImplementedError("SHELL: FILE-101 待注入实现")


def ingest(uri: str) -> npt.NDArray:
    """完整标准化流程：解码 → 下混 → 重采样 → 校验 → 返回 float32 mono。

    这是本模块唯一的对外入口。前四个函数是它的步骤分解，
    分开是为了让审查者能单独验证每一步（尤其是重采样与校验）。

    失败：抛 CoreBuildError，code 取 INPUT_UNREADABLE / INPUT_TOO_SHORT /
        INPUT_TOO_LONG / INPUT_SILENT
    """
    raise NotImplementedError("SHELL: FILE-101 待注入实现")
