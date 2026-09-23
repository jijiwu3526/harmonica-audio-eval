# RECON — 环境侦察结论（已实测，可直接采信）

> 由主智能体在交付任务前实测。**这些不是猜测，是跑通的结果。**
> 子智能体应直接采用，不要重复试错。

## 1. 已就绪的环境

| 项 | 状态 |
| --- | --- |
| FluidSynth | ✅ `/opt/homebrew/bin/fluidsynth` v2.6.1（本次已 `brew install fluid-synth`） |
| SoundFont | ✅ `vendor/soundfonts/FluidR3Mono_GM.sf3`（23,712,790 B，RIFF SoundFont，已校验） |
| SoundFont 许可证 | ✅ `vendor/soundfonts/FluidR3Mono_License.md` → **MIT**（FluidR3 by Frank Wen © 2000-2002；Mono conversion by Michael Cowgill；MS_General adaptation by S. Christian Collins） |
| mido | ✅ 已装 |
| pretty_midi | ✅ 0.2.11.post0 |
| music21 | ✅ 10.5.0 |
| librosa / numpy / scipy / soundfile / matplotlib | ✅ 已装 |
| ffmpeg / ffprobe | ✅ `/opt/homebrew/bin` |

## 2. 网络通道（重要）

| 主机 | 可用性 |
| --- | --- |
| `www.mutopiaproject.org` | ✅ 直连可用 |
| `api.github.com` | ✅ 可用 |
| `raw.githubusercontent.com` | ❌ **超时不可用** |
| `codeload.github.com`（git clone 大仓） | ⚠️ VCSL 仓库约 3.9 GB，不要整仓 clone |

**下载 GitHub 文件必须走 API 原始内容通道：**

```bash
curl -sSL -H "Accept: application/vnd.github.raw" \
  -o <out> "https://api.github.com/repos/<owner>/<repo>/contents/<path>"
```

这是唯一验证过能下成大文件（23 MB SoundFont）的方式。

## 3. 10 首源 MIDI：已全部定位并实测下载成功

Mutopia 搜索页：`https://www.mutopiaproject.org/cgibin/make-table.cgi?searchingfor=<query>`
作品信息页：`https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=<id>`

| ID | 曲目 | Mutopia piece id | MIDI URL | 主旋律 track |
| --- | --- | --- | --- | --- |
| 01_amazing_grace | Amazing Grace | 1832 | `ftp/Traditional/amazing-mutopia/amazing-mutopia.mid` | t1（唯一音符轨，115 notes, 56–70） |
| 02_greensleeves | Greensleeves | 1247 | `ftp/Traditional/greensleeves/greensleeves.mid` | t1 `upper:one`（122 notes, 57–74） |
| 03_auld_lang_syne | Auld Lang Syne | 1121 | `ftp/HoretzkyF/horetzky31/horetzky31.mid` | t1（134 notes, 55–86） |
| 04_ode_to_joy | Ode to Joy | 528 | `ftp/BeethovenLv/ode/ode.mid` | t1 `upper`（121 notes, 61–74） |
| 05_first_noel | The First Noel | 1243 | `ftp/Traditional/first_noel/first_noel.mid` | t1 `upper`（130 notes, 57–74） |
| 06_home_sweet_home | Home, Sweet Home | 435 | `ftp/BishopHR/homeshome/homeshome.mid` | t1 `:mel`（75 notes, 65–77） |
| 07_brahms_lullaby | Wiegenlied | 1037 | `.../Wiegenlied/Wiegenlied-mids.zip` → member `Wiegenlied.mid` | t1 `mel`（54 notes, 63–75） |
| 08_caro_mio_ben | Caro Mio Ben | 22 | `ftp/GiordanoG/caromioben/caromioben.mid` | t1 `voice`（110 notes, 61–76） |
| 09_swanee_river | Old Folks at Home | 1641 | `ftp/FosterSC/oldfolks/oldfolks.mid` | t1 `Tema`（215 notes, 40–71）⚠️ 音域偏低且可能含装饰音 |
| 10_hard_times | Hard Times | 371 | `.../hardtimes/hardtimes-mids.zip` → member `hardtimes.mid` | t1 `up:VoiceI` 是钢琴右手，**不是**主旋律；需按 §六 规则重选（t3 `down:VoiceI` / 空名 t1 prog40 待判定） |

⚠️ **不要机械照抄上表的主旋律 track。** 必须按 BUILD_BRIEF §六 的规则实际判定，并把判定依据写进 `midi_analysis.json`。

## 4. 实测踩坑（务必避免）

1. ~~**Amazing Grace 原始 MIDI 全曲仅 72.0 s，但抽出的单声部主旋律只有 38.5 s** —— **低于 45 s 下限**。必须按 §十 从完整小节边界重复 verse，不得 crossfade。多数曲目都会遇到同类问题，**长度必须在抽完旋律后再校验**。~~

   > **⚠ 更正（v2）**：上条结论**错误**，已实测推翻。真实数据：
   > - 源 MIDI `length = 72.000 s`；melody 115 个音符，`melody.mid length = 72.401 s`。
   > - 抽出的主旋律**跨度 69.0 s**（首音 tick 154 → 末音 tick 26650；60 BPM / 384 ppq
   >   ⇒ 26650 tick = 69.40 s），**远高于 45 s 下限**，无需重复 verse。
   > - 交付音频实测 **72.802 s**（含 0.4 s 前导与 0.4 s 尾部静音 + 末音时值）。
   >
   > **错误根因**：把 `mido` 的 `msg.time` 当作**秒**读取，但它实际是 **ticks**。
   > 26496 tick ÷ 384 ppq = 69.0 拍，在 60 BPM 下即 69.0 s，不是 26 496 s 也不是 38.5 s。
   > **教训**：任何来自 MIDI 的时长数字，必须先确认单位（tick ↔ 秒）再下结论；
   > 且必须在**抽完旋律后**用 `MidiFile.length` 与「末音 tick × 拍长」双重校验。
   >
   > **对全局的影响**：§4 中依赖「多数曲目都会遇到同类问题」的推论**不再成立**。
   > 每首曲子的长度必须独立实测，不得套用此条。

2. **Mutopia 的 `lower` / `pianoLH` / `down:VoiceI` 是伴奏低音，`upper` / `pianoRH` 常是钢琴右手（含和弦）**。正确主旋律往往在名为 `mel` / `voice` / `Tema` / `:mel` 的轨，或需要从上层轨中做单声部化。
3. **FluidSynth 默认输出立体声**；必须用 `-F out.wav -r 44100` 后经 ffmpeg 转 `-ac 1`，或用 `-o audio.file.name` 配合后续转换。最终交付前一律 ffmpeg 归一为 `44100 Hz / mono / pcm_s16le`。
4. **GM Harmonica 的 program number 是 22**（0-based）；GM Acoustic Grand Piano 是 0。实测渲染成功。
5. **音色 109（Bagpipe）等非钢琴音色出现在部分源文件**，抽取旋律后必须显式改写 program，否则 `reference_melody.wav` 会带上奇怪音色。
6. **部分曲目 BPM 为 60**（Amazing Grace / Greensleeves / First Noel / Brahms / Swanee），落在目标区间内但偏慢；按 §九 决定是否调整，若调整三份 WAV 必须同步。
7. **`raw.githubusercontent.com` 不通**，只有 `api.github.com` 通（见 §2）。
8. **VCSL 仓库 3.9 GB**，不要 clone；按 §5 只取需要的 harmonica 采样，走 GitHub API contents 通道。

## 5. VCSL 口琴采样（已确认存在）

仓库 `sgossner/VCSL`，**CC0-1.0**，339★。已确认路径（含实际文件名）：

```
Aerophones/Free Aerophones/Harmonica-Hohner-Super64/...        (78 wav)
Aerophones/Free Aerophones/Harmonica-Hohner-Special20-C/...    (152 wav)
```

采样命名规律（实测）：

- Super64：`Hohner-Super64_<Articulation>_<rel_|>_<Note>.wav`，如 `Hohner-Super64_Normal _C4.wav`（注意 `Normal` 后**有个空格**）、`Hohner-Super64_Accented_C4.wav`、`..._rel_C4.wav`
- Special20：`Hohner-Special20-<Key>_<Articulation>_<Note>.wav`，如 `Hohner-Special20-F_Normal..._C4.wav`
- Articulation 含 `Normal` / `Accented` / `Soft` / `HandVib` / `Vib`
- 仓库根有 `LICENSE`（CC0-1.0）

音域覆盖 C2–C6（Super64），足够本数据集 MIDI 55–88 的需求。采样为**相对音高命名**（`rel_`），映射到绝对音高时**必须实测校验**，不要假设。

## 6. 已验证可用的渲染命令

```bash
SF=vendor/soundfonts/FluidR3Mono_GM.sf3
fluidsynth -ni -F out.wav -r 44100 -g 0.6 "$SF" input.mid
ffmpeg -y -i out.wav -ac 1 -ar 44100 -c:a pcm_s16le final.wav
```

> **⚠ 更正（v2）**：上述渲染链路（FluidSynth + GM SoundFont）**已整体废弃**。
> GM 的音色 22（Harmonica）实测听感过于电子化，负责人已否决。
> 现行走的是 **VCSL 真采样渲染器**（`harmonica_sampler.py`），见 §5。

实测（旧链路遗留数据，仅作历史记录）：`reference_full.wav` 74.5 s、`practice_harmonica.wav` 38.5 s。
其中 **38.5 s 系上述 tick/秒 单位误读所致，非真实时长**（真实为 72.802 s，见 §4）。


## 7. 主智能体已完成 / 未完成

**已完成**：环境安装、SoundFont 获取与校验、网络通道确认、10 首 MIDI 定位、10 首轨道结构实测、渲染链路冒烟测试、VCSL 路径确认。

**未完成（交给子智能体）**：旋律抽取与单声部化、长度补齐、转调、expected_notes.csv、三份 WAV 生成、QC（pitch sanity + waveform/pitch 图）、metadata/license/manifest、压力测试、可复现脚本。
