# 第三方许可汇总

> ★ 本表只记录本仓库当前实际使用的组件。版本为 2026-09-27 本机
> macOS arm64 环境实测值；Python 条目取自已安装 distribution metadata，
> 系统条目取自 Homebrew JSON metadata。第三方依赖的传递依赖由 pip 元数据管理，
> 不因本项目直接 import 就冒充为项目顶层依赖。

## 1. Python 依赖

| 组件名 | 版本 | 必需性 / 用途 | 许可类型（metadata 实读） | 许可文件 / metadata 来源 |
| --- | --- | --- | --- | --- |
| NumPy (`numpy`) | 2.4.4 | 必需；核心数组与类型 | `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`（`License-Expression`） | `/Users/Apple/miniconda3/lib/python3.13/site-packages/numpy-2.4.4.dist-info/licenses/LICENSE.txt` |
| SoundFile (`soundfile`) | 0.13.1 | 必需；WAV/FLAC 音频读写 | `BSD 3-Clause License` | `/Users/Apple/miniconda3/lib/python3.13/site-packages/soundfile-0.13.1.dist-info/LICENSE` |
| librosa | 0.11.0 | 必需；pYIN 音高质检与 DTW 内存实验 | `ISC` | `/Users/Apple/miniconda3/lib/python3.13/site-packages/librosa-0.11.0.dist-info/LICENSE.md` |
| SciPy | 1.17.1 | 必需；采样重采样 | BSD 3-Clause（许可文件首段为 SciPy BSD 三条款） | `/Users/Apple/miniconda3/lib/python3.13/site-packages/scipy-1.17.1.dist-info/LICENSE.txt` |
| Matplotlib | 3.10.9 | **可选**；数据集波形/音高质检图 | Matplotlib License Agreement（自带样式 PSF-like 许可；文件同时列出随包字体/组件的附加许可） | `/Users/Apple/miniconda3/lib/python3.13/site-packages/matplotlib-3.10.9.dist-info/LICENSE` |
| Mido (`mido`) | 1.3.3 | 必需；MIDI 解析与构建 | `MIT` | `/Users/Apple/miniconda3/lib/python3.13/site-packages/mido-1.3.3.dist-info/LICENSE` |

> ★ 不列入顶层依赖：`pretty_midi` 0.2.11.post0 与 `torchcrepe` 未安装，
> 且当前项目 Python 代码没有 `import`；前者在旧调查/构建记录中出现，后者在
> `SPEC.md §7` 中只是待对照的引擎候选。因此不为“可能有用”预装。

## 2. 数据集素材

### 2.1 逐曲 Mutopia MIDI

| 组件名 | 版本 / 获取日期 | 许可类型 | 许可文件 / 来源路径 |
| --- | --- | --- | --- |
| Mutopia MIDI — 奇异恩典（Amazing Grace） | 获取 2026-09-23 | CC BY-SA 3.0 | `harmonica_mvp_dataset/01_奇异恩典/来源与许可.txt`；站点说明 <https://www.mutopiaproject.org/legal.html> |
| Mutopia MIDI — 绿袖子（Greensleeves） | 获取 2026-09-23 | Public Domain | `harmonica_mvp_dataset/02_绿袖子/来源与许可.txt`；站点说明同上 |
| Mutopia MIDI — 友谊地久天长（Auld Lang Syne） | 获取 2026-09-23 | Public Domain | `harmonica_mvp_dataset/03_友谊地久天长/来源与许可.txt`；站点说明同上 |
| Mutopia MIDI — 欢乐颂（Ode to Joy） | 获取 2026-09-23 | Public Domain | `harmonica_mvp_dataset/04_欢乐颂/来源与许可.txt`；站点说明同上 |
| Mutopia MIDI — 圣诞佳音（The First Noel） | 获取 2026-09-23 | Public Domain | `harmonica_mvp_dataset/05_圣诞佳音/来源与许可.txt`；站点说明同上 |
| Mutopia MIDI — 甜蜜的家（Home, Sweet Home） | 获取 2026-09-23 | Public Domain | `harmonica_mvp_dataset/06_甜蜜的家/来源与许可.txt`；站点说明同上 |
| Mutopia MIDI — 勃拉姆斯摇篮曲（Wiegenlied） | 获取 2026-09-23 | Public Domain | `harmonica_mvp_dataset/07_勃拉姆斯摇篮曲/来源与许可.txt`；站点说明同上 |
| Mutopia MIDI — 我亲爱的（Caro Mio Ben） | 获取 2026-09-23 | Public Domain | `harmonica_mvp_dataset/08_我亲爱的/来源与许可.txt`；站点说明同上 |
| Mutopia MIDI — 故乡的亲人（The Old Folks at Home） | 获取 2026-09-23 | CC BY-SA 3.0 | `harmonica_mvp_dataset/09_故乡的亲人/来源与许可.txt`；站点说明同上 |
| Mutopia MIDI — 艰难时光（Hard Times Come Again No More） | 获取 2026-09-23 | Public Domain | `harmonica_mvp_dataset/10_艰难时光/来源与许可.txt`；站点说明同上 |

### 2.2 采样与 SoundFont

| 组件名 | 版本 | 许可类型 | 许可文件 / 来源路径 |
| --- | --- | --- | --- |
| VCSL Hohner Super64 真实口琴采样 | 未标注（下载内容无 Git tag 记录） | CC0-1.0 | 10 份 `harmonica_mvp_dataset/*/来源与许可.txt` 的末尾“使用 VCSL（CC0-1.0）”记录；上游 <https://github.com/sgossner/VCSL> |
| FluidR3 / FluidR3Mono / MS_General SoundFont | `MS_General.sf2` alpha 1，2018-03-01；原 FluidR3 2000–2002 | MIT；衍生版须保留许可与致谢 | `vendor/soundfonts/FluidR3Mono_License.md`（内含原始 README 与完整 MIT `COPYING`） |

> ★ FluidR3Mono 是历史候选渲染链路。`build/RECON.md` 已记录 FluidSynth + GM
> SoundFont 链路整体废弃；当前 `harmonica_mvp_dataset/build_dataset.py` 使用
> `HarmonicaSampler` 离线渲染 VCSL，代码中没有 `ffmpeg` / `fluidsynth` 调用。
> 本表仍保留该已入库素材的许可义务。

## 3. 系统依赖

| 组件名 | 本机版本 | 必需性 / 当前用途 | 许可类型（Homebrew metadata） | 许可文件 / 来源路径 |
| --- | --- | --- | --- | --- |
| FFmpeg (`ffmpeg`) | 8.1.1 | 历史音频解码/转码链路；当前 Python 源码未直接调用 | Homebrew formula: `GPL-3.0-or-later`（其安装文件声明主体 LGPL-2.1-or-later，启用可选 GPL 组件后组合构建为 GPL） | `/opt/homebrew/Cellar/ffmpeg/8.1.1/LICENSE.md`；metadata 来源 `brew info --json=v2 ffmpeg` |
| FluidSynth (`fluid-synth`) | 2.6.1 | 历史 MIDI 渲染器；当前 Python 源码未直接调用 | Homebrew formula: `LGPL-2.1-or-later` | `/opt/homebrew/Cellar/fluid-synth/2.6.1/LICENSE`；metadata 来源 `brew info --json=v2 fluid-synth` |

## 4. 许可核对方法

- **Python 组件**：在仓库根执行 `python3 -c "import importlib.metadata as m; ..."`，
  读取 `Version`、`License`、`License-Expression`、`License-File` 及 distribution 内的
  许可文件；不是依据在线记忆填写。
- **数据素材**：逐个读取 `harmonica_mvp_dataset/*/来源与许可.txt`；VCSL 与十首 MIDI
  的结论均可由这些文件直接复核。
- **系统组件**：执行 `ffmpeg -version`、`fluidsynth --version` 与
  `brew info --json=v2 <formula>`，并读取对应 Cellar 许可文件。
- **本文件不是法律意见**；再分发时应携带上述许可文本并遵守各自署名、
  相同方式共享或源码提供条件。
