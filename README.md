# harmonica-eval

口琴**双音频对比**分析：参考演奏 vs 练习演奏 → **客观数值指标**与对比图谱。

两段音频进去，16 个数字出来。没有自然语言评价，没有 AI 打分，没有「你吹得不够好」——
只有「中位绝对偏差 105.0 cents」「走音比例 0.85」这类可复现、可对拍的数。

---

## 快速上手

```bash
# 依赖（实测版本：Python 3.13 · numpy 2.4.4 · scipy 1.17.1 · soundfile 0.13.1 · librosa 0.11.0）
python3 -c "import numpy, scipy, soundfile, librosa; print('依赖 OK')"

# 无头运行：两个音频 → 16 个指标 → data/out/metrics.json
PYTHONDONTWRITEBYTECODE=1 python3 -m harmonica_eval \
  --reference  <参考音频.wav> \
  --practice   <练习音频.wav>
```

**音频规格**：44100Hz / 单声道 / 45–120 秒 / peak −3 dBFS。

> 仓库**不含音频**。要立刻跑通，见 [`CONTRIBUTING.md` §2](CONTRIBUTING.md#2--没有音频也能跑重要)——
> 里面有一段 10 行的 numpy 代码，能造出符合规格的合成音频（零额外依赖）。

---

## 界面

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m harmonica_eval.serve_ui \
  --reference <参考音频.wav> --practice <练习音频.wav>
# → http://127.0.0.1:8721/  +  一个局域网地址（手机可访问）
```

页面上能做的事：

- **选曲**：从数据集下拉选择（按曲名分组），不手打路径
- **出图**：音高叠放（横轴=音序）、能量叠放（横轴=时间），参考=蓝 / 练习=红
- **看数**：16 个指标，按插件分组
- **换插件**：任何新插件的指标会自动出现在页面上——**界面代码一行不用改**

不想自动开浏览器：`DSH_NO_BROWSER=1` 前缀即可。

> **麦克风录制不可用**：浏览器录音格式（webm/opus/m4a）当前数据面读不了，
> 而引入转换工具会违反零依赖铁律。**用「选样本」代替「吹奏」**，这也是刻意的取舍。

---

## 指标（16 个，按插件分组）

| 插件 | 指标 |
|---|---|
| `pitch` | 中位绝对偏差(cents)、走音比例、参与统计音数、未配对音数、采样率 |
| `timing` | 中位起音偏差(s)、起音偏差离散度、抢拍比例、拖拍比例、死区内比例、参与统计音数、未配对音数 |
| `dynamics` | 中位能量差(dB)、离散度(MAD)、参与统计音数、未配对音数 |

每个数字的口径与计算方式见 [`docs/指标解读.md`](docs/指标解读.md)。

---

## 贡献插件

**见 [`CONTRIBUTING.md`](CONTRIBUTING.md)** —— 目标是半小时内交出第一个插件 PR。

一句话版本：写一个函数产出指标，**运行期** `registry.register(PluginSpec(...))`，
不改 `bootstrap.py` 源码（那条退化守卫在测它），然后跑 `tests/test_plugin_plugability.py`。

---

## 边界

- ✅ 双音频对比 → 客观数值指标 + 对比图谱
- ❌ 自然语言反馈生成 / Agent / LLM 评价
- ❌ AI 审美评分、生成「理想演奏」、模型训练
- ❌ 任何 `SPEC.md` 未列出的特征维度

**为什么界面长这样**：cockpit 是**契约可视图**，不是产品界面。它的职责是
「让内核算出的东西可见」——指标按插件分组、图按数据面真实端口画，
都是为了让架构的可插拔性**可被检验**，而不是为了好看。

---

## 结构

```
harmonica-eval/
├── SPEC.md                    权威规格（唯一，先读这个）
├── CONTRIBUTING.md            ★ 插件贡献指南
├── .spec/                     规格包
│   ├── build/FILE-NNN-v1.md   每个文件的 Build Instruction（冻结产物）
│   └── PLUGIN-LAYOUT.md       插件布局规范
├── harmonica_eval/
│   ├── contract.py            ★ 冻结契约（插件作者永远不需要动）
│   ├── profile.py             ★ 冻结规格（音频规格在此）
│   ├── core/                  C1 数据面：ingest / align / features / surface
│   ├── algorithms/            插件：pitch / timing / dynamics / bootstrap
│   ├── host/                  HostApp 编排
│   └── cockpit/               契约可视图（HTTP + 内联 SVG，零依赖）
├── tools/                     门禁
├── tests/                     165 个测试
└── data/{ref,in,out}/         参考音频 / 待测音频 / 结果
```

---

## 门禁

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q      # 165 passed
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_shell.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_counts.py
PYTHONDONTWRITEBYTECODE=1 bash tools/check_all.sh   # ★ 必须串行跑
```

**必须串行**——这些都写 `data/out`，并发跑会产生不存在的失败。

---

## 已知限制（如实列出）

- **仓库不含音频**（441M），运行样例需自备或用合成音频
- **麦克风不可用**（格式不兼容，见上）
- **未在真机验证过**：`core` 与 `algorithms` 层的 Android/iOS 可移植性是**读代码得出的结论**，
  未在真机安装运行过。详见 [`docs/手机可移植性评估.md`](docs/手机可移植性评估.md)
- **`verify_shell.py` 有一项检查依赖库外文件**，缺失时自动跳过并提示（不影响其余判据）

---

## 读这个

- `SPEC.md` — 权威规格
- `CONTRIBUTING.md` — 想加功能/插件，从这里开始
- `docs/验收计划.md` — 验收标准与当前状态
- `docs/架构图.md` — 分层与数据流
