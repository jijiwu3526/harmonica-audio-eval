# BUILD BRIEF — 口琴 MVP 黄金测试集（原始任务书）

> 本文件为项目负责人下达的原始任务书，**逐字保留**，不得擅自降低验收标准。

# 任务：构建 10 首口琴音频检测 MVP 黄金测试集

你是一个具有联网搜索、文件下载、Python、FFmpeg、Git 和音频处理能力的数据工程智能体。

你的任务不是训练神经网络，而是为一个“口琴演奏检测/辅导”项目构建一套小而干净、完全可复现的测试数据集。

最终必须交付 10 首歌曲。

核心目标是让开发者能够用这套数据验证：

* FFT pitch detection
* autocorrelation
* YIN
* pYIN
* MPM
* onset detection
* note segmentation
* MIDI/audio alignment
* DTW
* 演奏音高和标准旋律比较

不要训练任何新模型。

---

# 一、数据集最终定义

每一首歌曲必须至少产生下面这些文件：

```text
01_amazing_grace/
    source.mid
    melody.mid

    reference_full.wav
    reference_melody.wav
    practice_harmonica.wav

    expected_notes.csv
    metadata.json

    source_license.txt
```

解释：

`source.mid`

从合法公开来源获得的原始 MIDI。

`melody.mid`

从 source.mid 中抽取出的单声部主旋律。

这是整个数据集真正的 Ground Truth。

`reference_full.wav`

完整 MIDI 渲染得到的“原曲参考版”。

尽量保留伴奏和旋律。

用途：

测试“用户口琴演奏 vs 原曲”的粗粒度音频对齐。

`reference_melody.wav`

只使用 melody.mid 渲染的标准旋律。

乐器使用 piano、sine 或其他简单清晰音色。

用途：

测试最理想情况下的旋律匹配。

`practice_harmonica.wav`

使用完全相同的 melody.mid，用 harmonica 音色重新渲染。

它必须和 melody.mid：

* 音符完全一致
* onset 完全一致
* duration 基本一致
* tempo 完全一致

只有乐器音色发生变化。

这是第一阶段最重要的测试文件。

---

# 二、只收集以下 10 首

优先顺序如下：

1. Amazing Grace
2. Greensleeves
3. Auld Lang Syne
4. Ode to Joy
5. The First Noel
6. Home, Sweet Home
7. Wiegenlied / Brahms' Lullaby
8. Caro Mio Ben
9. The Old Folks at Home / Swanee River
10. Hard Times Come Again No More

选择这些曲子的原因：

* 旋律明确
* 大量是传统曲目或公共领域作品
* MIDI 容易获得
* 主旋律容易抽取
* 音符变化适中
* 接近真正歌曲，而不是音阶练习
* 长度足够
* 后续容易找到真人演奏版

如果某一首无法获得许可明确的 MIDI，可以替换，但必须满足：

1. Public Domain、CC0、CC-BY 或 CC-BY-SA；
2. 有 MIDI；
3. 有清楚的旋律；
4. 可以产生至少约 45 秒的测试片段。

禁止使用许可不明确的 MIDI。

---

# 三、数据来源

## 来源 A：Mutopia Project

这是首选曲谱和 MIDI 来源。

搜索上面的 10 首歌曲。

每首进入具体作品页面后：

下载：

* MIDI
* PDF 乐谱（如果存在）
* LilyPond 文件（如果方便）

同时保存：

* 曲名
* Composer
* Arranger
* Source
* Copyright / License
* 原始作品页面地址

不要只保存 MIDI。

必须同时保存许可信息。

---

# 四、音色来源

按下面优先级执行。

## 方案 1：快速 MVP

安装：

* FluidSynth
* FluidR3 / MuseScore General SoundFont

使用 General MIDI：

```text
Acoustic Grand Piano
```

生成：

```text
reference_full.wav
reference_melody.wav
```

然后使用 GM 的：

```text
Harmonica
```

生成：

```text
practice_harmonica.wav
```

这个版本的目标不是模拟完美真人口琴，而是先验证：

“同样的音符经过完全不同音色以后，现有算法还能不能正确识别和对齐？”

这是必须完成的最低版本。

---

# 五、第二优先级口琴渲染

如果运行环境允许，再使用：

Versilian Community Sample Library（VCSL）

重点寻找：

```text
Aerophones/
Free Aerophones/
Harmonica-Hohner-Super64
```

以及：

```text
Harmonica-Hohner-Special20-C
```

VCSL 为 CC0 音源。

优先使用真实 harmonica samples 重新渲染：

```text
practice_harmonica_vcsl.wav
```

不要覆盖原来的：

```text
practice_harmonica.wav
```

两个都保留。

这样以后可以比较：

```text
GM Harmonica
vs
VCSL sampled Harmonica
```

对检测算法的影响。

---

# 六、MIDI 清洗

这是整个任务最重要的一步。

不要直接把整个 MIDI 当作 Ground Truth。

必须抽取主旋律。

使用：

```text
pretty_midi
mido
music21
```

任选其一或组合使用。

首先分析 MIDI：

输出：

```text
track number
instrument
program
number of notes
pitch min
pitch max
polyphony ratio
duration
```

生成：

```text
midi_analysis.json
```

然后寻找主旋律 track。

优先规则：

1. 名称中包含 Voice / Vocal / Melody / Lead；
2. 单声部比例最高；
3. 音域符合正常旋律；
4. note density 合理；
5. 和乐谱主旋律一致。

禁止简单地：

“始终取 MIDI 中最高的那个音”。

因为钢琴右手和和弦会导致错误。

---

# 七、把主旋律变成真正的单声部

最终：

```text
melody.mid
```

必须满足：

```text
最大同时发声音符数 = 1
```

允许极短 overlap：

```text
< 30 ms
```

超过 30 ms 必须处理。

处理原则：

如果是同一个旋律 voice：

结束前一个 note：

```text
previous.end = next.start
```

不要让两个旋律音长时间重叠。

去掉：

```text
drums
chords
bass
accompaniment
ornamental duplicate notes
```

---

# 八、控制音域

第一期不要故意给算法制造特别变态的音域。

目标旋律范围优先：

```text
MIDI 60–84
```

即大约：

```text
C4–C6
```

允许扩展到：

```text
MIDI 55–88
```

如果原曲超出范围：

进行整数半音 transpose。

例如：

```text
transpose_semitones = +2
```

必须写进 metadata。

不要改变旋律相对音程。

---

# 九、控制速度

目标：

```text
60–140 BPM
```

优先：

```text
70–120 BPM
```

如果歌曲极快或者极慢，可以调整整体 tempo。

但必须：

1. reference
2. melody
3. harmonica

同时改变。

metadata 中记录：

```json
{
    "original_bpm": 72,
    "test_bpm": 90,
    "tempo_scale": 1.25
}
```

---

# 十、控制音频长度

每条测试音频目标：

```text
45–120 秒
```

优先：

```text
60–90 秒
```

不要只做 5 秒、10 秒的小样本。

如果歌曲太长：

按照小节或者乐句边界裁剪。

不要从一个 note 中间切断。

如果歌曲太短：

允许重复 verse / melody。

例如：

```text
verse 1
verse 2
```

但重复必须从完整小节边界开始。

不要使用 crossfade。

因为 crossfade 会破坏 onset Ground Truth。

---

# 十一、生成 expected_notes.csv

必须从：

```text
melody.mid
```

直接生成。

不能从音频反推。

格式：

```csv
note_index,start_sec,end_sec,duration_sec,midi_pitch,note_name,frequency_hz,velocity
0,0.500,1.000,0.500,60,C4,261.626,90
1,1.000,1.500,0.500,62,D4,293.665,90
2,1.500,2.250,0.750,64,E4,329.628,90
```

frequency：

使用：

```text
A4 = 440 Hz
```

公式：

```text
frequency = 440 * 2 ^ ((midi - 69) / 12)
```

时间必须考虑：

```text
tempo map
tempo changes
ticks per beat
```

不能简单假设整个 MIDI 一个 BPM。

---

# 十二、音频统一规格

最终算法测试 WAV 全部转换为：

```text
WAV
PCM signed 16-bit
44.1 kHz
mono
```

即：

```text
44100 Hz
1 channel
16 bit
```

不要把 MP3 作为最终测试文件。

原始 MP3 / OGG 如果存在：

保存在：

```text
_raw/
```

最终测试统一为 WAV。

---

# 十三、响度处理

不要做复杂 mastering。

仅做：

1. 防止 clipping；
2. 统一到大致一致的音量。

目标：

```text
peak <= -1 dBFS
```

优先：

```text
-3 dBFS
```

不要：

* compressor
* limiter 重压
* aggressive noise reduction
* excessive EQ
* reverb

第一阶段需要尽可能干净的信号。

---

# 十四、静音处理

开头保留：

```text
0.3–0.5 秒
```

静音。

结尾保留：

```text
0.3–0.5 秒
```

静音。

不要：

```text
开头 5 秒静音
结尾 10 秒静音
```

歌曲内部的正常休止必须保留。

---

# 十五、生成三个核心 WAV

每首歌曲必须生成：

## A

```text
reference_full.wav
```

完整 MIDI arrangement。

## B

```text
reference_melody.wav
```

只有 melody.mid。

音色：

```text
piano
```

或者非常干净的简单音色。

## C

```text
practice_harmonica.wav
```

同一个 melody.mid。

音色：

```text
harmonica
```

关键原则：

B 和 C：

```text
note sequence
tempo
onset
duration
```

必须完全来自同一个 melody.mid。

---

# 十六、强制做 Alignment Sanity Check

生成 WAV 后不要直接认为成功。

必须自动验证。

读取：

```text
expected_notes.csv
practice_harmonica.wav
```

运行一个基础 pitch detector。

可以用：

```text
librosa.pyin
```

或者：

```text
aubio pitch
```

这一步只用于 QC，不作为 Ground Truth。

Ground Truth 永远是 MIDI。

检查：

对于持续时间：

```text
>= 150 ms
```

的音符：

在 note 中间区域：

```text
20%–80%
```

检测到的 median F0。

转成 MIDI：

```text
estimated_midi =
69 + 12 * log2(f0 / 440)
```

计算 cents error。

目标：

至少：

```text
90%
```

的稳定音符满足：

```text
abs(error) < 50 cents
```

如果失败：

优先判断：

1. harmonica sample mapping 错；
2. MIDI transpose 错；
3. SoundFont program 错；
4. octave mapping 错；
5. audio render 错。

不要静默接受失败文件。

---

# 十七、自动生成 waveform QA

每一首生成：

```text
qa_waveform.png
```

显示：

```text
practice_harmonica.wav waveform
```

以及：

```text
expected note boundaries
```

另外生成：

```text
qa_pitch.png
```

横轴：

```text
time
```

纵轴：

```text
MIDI pitch
```

同时画：

```text
expected MIDI
estimated F0
```

这是给开发者快速肉眼检查数据用的。

---

# 十八、metadata.json

每首歌生成：

```json
{
  "id": "01_amazing_grace",
  "title": "Amazing Grace",
  "composer": "Traditional",

  "source_site": "Mutopia Project",
  "source_page": "...",
  "license": "...",

  "original_midi": "source.mid",
  "melody_midi": "melody.mid",

  "transpose_semitones": 0,

  "original_bpm": 90,
  "test_bpm": 90,

  "duration_sec": 78.52,

  "sample_rate": 44100,
  "channels": 1,
  "bit_depth": 16,

  "reference_renderer": "FluidSynth",
  "reference_soundfont": "...",

  "harmonica_renderer": "FluidSynth/VCSL",
  "harmonica_source": "...",

  "number_of_notes": 123,

  "min_midi": 60,
  "max_midi": 79,

  "a4_hz": 440
}
```

---

# 十九、保存许可证

每一首都必须有：

```text
source_license.txt
```

里面保存：

```text
歌曲来源
作品页面
MIDI 来源
License
作者
Arranger
下载日期
```

同时项目根目录保存：

```text
THIRD_PARTY_LICENSES.md
```

记录：

* Mutopia
* MIDI
* FluidR3 / MuseScore General
* VCSL

对应许可证。

不要只记录“free”。

必须保存具体 license。

---

# 二十、不要做这些事情

禁止：

* 从 Spotify 下载歌曲
* 从 Apple Music 下载歌曲
* 从 QQ 音乐下载歌曲
* 从网易云下载歌曲
* 从 YouTube 非授权抓 MP3
* 使用来源不明的 MIDI 网站
* 使用来源不明的 SoundFont
* 把版权不明的商业歌曲放进数据集

这个测试集必须可以在以后：

```text
开发
测试
Git repository
内部 benchmark
```

中重复使用。

---

# 二十一、额外真实口琴压力测试

完成核心 10 首以后，再做一个：

```text
real_harmonica_stress_test/
```

这部分不算进核心 10 首。

到 Wikimedia Commons：

搜索：

```text
Sounds of harmonicas
```

优先检查：

```text
Train.ogg
Big River1.ogg
Marineband1.ogg
IrishTunes.ogg
```

只能下载页面明确显示：

```text
Public Domain
CC0
CC-BY
CC-BY-SA
```

的文件。

保存：

```text
original
converted WAV
license
metadata
```

统一转换成：

```text
44.1 kHz
mono
16-bit WAV
```

这些真实音频不要求有 Ground Truth MIDI。

用途只是测试：

```text
算法面对真人口琴是否立刻崩掉
```

不要把它们和核心黄金测试集混在一起。

---

# 二十二、最终目录

最终必须返回：

```text
harmonica_mvp_dataset/
│
├── README.md
├── dataset_manifest.csv
├── THIRD_PARTY_LICENSES.md
├── rejected_candidates.csv
│
├── 01_amazing_grace/
├── 02_greensleeves/
├── 03_auld_lang_syne/
├── 04_ode_to_joy/
├── 05_first_noel/
├── 06_home_sweet_home/
├── 07_brahms_lullaby/
├── 08_caro_mio_ben/
├── 09_swanee_river/
├── 10_hard_times/
│
└── real_harmonica_stress_test/
```

---

# 二十三、dataset_manifest.csv

生成：

```csv
id,title,duration_sec,notes,min_midi,max_midi,bpm,transpose,license,reference_full,reference_melody,practice_harmonica
01,Amazing Grace,78.5,123,60,79,90,0,CC-BY-SA,...
```

---

# 二十四、Rejected 数据也要记录

如果找到候选但拒绝：

写到：

```text
rejected_candidates.csv
```

例如：

```csv
title,url,reason
Song A,...,copyright unclear
Song B,...,melody cannot be isolated
Song C,...,duration too short
Song D,...,severe polyphony
```

这样后面不用重复踩坑。

---

# 二十五、最终验收标准

任务只有满足下面全部条件才能算完成：

```text
核心歌曲数量 = 10
```

每首：

```text
45 <= duration <= 120 sec
```

每首都有：

```text
source.mid
melody.mid
reference_full.wav
reference_melody.wav
practice_harmonica.wav
expected_notes.csv
metadata.json
source_license.txt
```

`melody.mid`：

```text
单声部
```

所有最终 WAV：

```text
44100 Hz
mono
PCM 16-bit
```

所有：

```text
expected_notes.csv
```

必须直接从：

```text
melody.mid
```

生成。

所有音频必须通过：

```text
duration check
sample-rate check
clipping check
pitch sanity check
```

任何失败：

修复或替换。

禁止为了凑够 10 条而降低验收标准。

---

# 二十六、最后返回给我的报告

任务完成后不要只回复“完成”。

返回：

## Dataset Summary

用表格列出 10 首：

```text
Title
Duration
Notes
Pitch range
BPM
Transpose
License
QC result
```

## Failed / Rejected

说明：

```text
哪些数据被拒绝
为什么
用了什么替代
```

## File Tree

打印最终目录树。

## Reproduction

给出：

```text
setup.sh
build_dataset.py
requirements.txt
```

确保我未来删除整个生成数据集以后，可以运行：

```bash
python build_dataset.py
```

重新获得同样的数据集。

尽量做到 deterministic。

如果需要随机数：

固定：

```text
seed = 42
```

---

# 二十七、原则

这个阶段的目标不是建立一个“真实世界大数据集”。

目标是建立一个：

```text
小
干净
长一些
严格配对
Ground Truth 明确
可以重复生成
可以立即拿来 benchmark
```

的数据集。

宁可：

```text
10 条非常可靠的数据
```

也不要：

```text
1000 条来源、旋律、版权、对齐全部不清楚的数据
```

执行任务直到实际文件和 QC 结果都生成完成，不要只给方案。
