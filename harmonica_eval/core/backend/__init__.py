'''
COMPONENT:    COMP-C2 Audio Core · backend（可移植特征后端）
SPEC:         profile.MATERIALIZE · profile.ALIGN

ROLE:
    numpy/scipy 自写的 librosa 等价实现，作为**无 librosa 环境的后端**。

INTENT:
    本项目要跑在 Android（arm64）上。librosa 拖 numba/llvmlite，Android 上
    没有 wheel —— 一条 `import librosa` 就能让整个阶段 3 停摆。

    故 chroma_stft 与 pyin 这两个**唯一**用到 librosa 的调用点，
    各有一份自写实现。本包只依赖 numpy + scipy（设备上已实测装好）。

    ★ 口径冻结：自写实现**不是**「近似替代」，而是同一条算法路径的
      numpy 复刻 —— 同样的帧数、同样的形状、同样的归一化方式。
      电脑（装 librosa）与手机（不装 librosa）跑的是**同一份调用代码**，
      差别只在 dispatch 选了哪条实现。

MUST NOT:
    - 依赖 librosa / numba / scikit-learn / 任何 Android 上没有的轮子
    - 改变 features.py 两个调用点的参数值与语义

INPUT:
    y: float 单声道波形
    sr / n_fft / hop_length / frame_length / fmin / fmax / center ...

OUTPUT:
    chroma_stft → ndarray (n_chroma, n_frames) float32
    pyin         → (f0, voiced_flag, voiced_prob) 三个 1-D 数组
'''

from __future__ import annotations

__all__ = ["chroma_stft", "pyin", "BACKEND_NAME"]

from .chroma import chroma_stft
from .pyin import pyin

BACKEND_NAME: str = "native"
"""自写后端的标识。dispatch 层用它标注当前走的是哪条实现。"""
