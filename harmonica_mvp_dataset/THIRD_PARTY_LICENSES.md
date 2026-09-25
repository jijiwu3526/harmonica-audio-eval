# 第三方许可

本数据集不含任何商业录音。全部素材均为公有领域或开放许可。

## 乐谱 / MIDI 来源 —— Mutopia Project

<https://www.mutopiaproject.org/>

- 站点许可：<https://www.mutopiaproject.org/legal.html>
- 逐曲许可记录在各曲的 `来源与许可.txt` 与 `metadata.json`。
  本数据集的曲子为**公有领域**或**知识共享 署名-相同方式共享 3.0**。

## 口琴采样 —— VCSL（Versilian Community Sample Library）

<https://github.com/sgossner/VCSL> — **许可：CC0-1.0**

- 使用的采样：`Aerophones/Free Aerophones/Harmonica-Hohner-Super64/Sustains/{Normal,Vib}`
- 采样文件的音高由本项目独立测量与校验，未依赖文件名
  （见 `prepare_samples.py` 与 `samples_measured.json`）。

## 渲染音频

本数据集所有 WAV 均为**离线合成**，使用上述口琴采样渲染 MIDI 而来。
数据集中没有钢琴，也没有任何演奏录音，因此不涉及演奏者或录音版权。

## 工具

librosa（ISC）、mido（MIT）、NumPy（BSD-3-Clause）、SciPy（BSD-3-Clause）、
SoundFile（BSD-3-Clause）、Matplotlib（PSF-based）。
