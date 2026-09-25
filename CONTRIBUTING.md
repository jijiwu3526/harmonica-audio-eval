# 贡献指南

面向**第一次接触本项目、但会 Python** 的人。目标：半小时内交出第一个插件 PR。

本文每条命令都被实跑验证过。若某条跑不通，那是文档的错，请提 issue。

---

## 0 · 三条铁律（先看这个，能省你一小时）

1. **零依赖**：不引入框架、CDN、图表库。算法层只用 `numpy`（部分模块连它都不用，只用标准库 `math`/`statistics`）。
2. **不碰冻结契约**：`harmonica_eval/contract.py` 与 `harmonica_eval/profile.py` 是冻结契约，改它需要项目负责人重新裁定。**插件作者永远不需要动它们。**
3. **不写死**：`algorithms/bootstrap.py` 是**唯一装配根**，但**你不该改它**——见 §4。

---

## 1 · 环境

| 项 | 值 | 怎么确认 |
|---|---|---|
| Python | 3.13+ | `python3 -V` |
| 必需依赖 | `numpy` `scipy` `soundfile` `librosa` | `python3 -c "import numpy,scipy,soundfile,librosa"` |
| 可选 | `pytest`（跑测试要） | `python3 -c "import pytest"` |

**`torch` 不需要**——全仓零 import。
但 **`librosa` 需要**：`harmonica_eval/core/features.py:57` 在运行期 import 它，
调用点为 `librosa.pyin`（音高）与 `librosa.feature.chroma_stft`（音高向量）。
**算法层本身不依赖它**——`algorithms/pitch.py` 只用 `math` + `statistics`。

```bash
git clone <仓库地址>
cd <仓库根>          # 下列命令都从仓库根执行
python3 -c "import numpy, scipy, soundfile, librosa; print('依赖 OK')"
```

> **本项目实测版本**（不要求一致，只是给你一个下限参考）：
> Python 3.13.13 · numpy 2.4.4 · scipy 1.17.1 · soundfile 0.13.1 · librosa 0.11.0 · pytest 9.1.0

---

## 2 · 没有音频也能跑（重要）

**仓库不含音频**（体积 441M / 70 个 wav），所以 clone 下来**没有音频**。
但**插件契约与测试框架都在，不需要音频也能读懂与开发**。

若要运行验证，请自行造一段合成音频——它满足全部规格，且**不引入任何新依赖**：

```python
# 造两段符合规格的合成 WAV：44.1kHz / 单声道 / 45 秒 / -3 dBFS
# 练习版整体偏高 6% ≈ 100 cents，便于验证音高指标确实在动
import numpy as np, soundfile as sf

sr, dur = 44100, 45.0
t = np.arange(int(sr * dur)) / sr
for tag, detune in (("ref", 1.0), ("prac", 1.06)):
    f0 = 220.0 * detune
    sig = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in (1, 2, 3)).astype("float32")
    env = np.clip(0.5 * (1 + np.cos(2 * np.pi * 2 * t)), 0, 1)   # 每 0.5s 一个包络峰
    x = (0.3 * sig * env).astype("float32")
    x *= 0.707 / np.max(np.abs(x))                                # 归到 -3 dBFS
    sf.write(f"{tag}.wav", x, sr)
```

**预期结果**（本项目实跑所得）：

```bash
python3 -m harmonica_eval --reference ref.wav --practice prac.wav
# rc=0，data/out/metrics.json 产出 16 个指标
# 其中 pitch.median_abs_cents ≈ 100.0（你刻意偏了 6% = 100 cents）
```

> **如果你要提交自己准备的音频**：规格为 44100Hz / 单声道 / float32 / 45–120 秒 / peak −3 dBFS。
> **请在 PR 里说明来源与许可**——授权不明的素材不能进本仓库。

---

## 3 · 跑起来看看

```bash
# 无头：两个音频进去，16 个指标出来
PYTHONDONTWRITEBYTECODE=1 python3 -m harmonica_eval \
  --reference ref.wav --practice prac.wav

# 界面：起服务 → 选曲 → 出图
PYTHONDONTWRITEBYTECODE=1 python3 -m harmonica_eval.serve_ui \
  --reference ref.wav --practice prac.wav
# 浏览器会打开 http://127.0.0.1:8721/
# 不想自动开浏览器：DSH_NO_BROWSER=1 python3 -m harmonica_eval.serve_ui ...
```

界面会给出一个局域网地址，手机可访问。**麦克风录制不可用**——浏览器录音格式
（webm/opus/m4a）当前数据面读不了，且引入转换工具会违反零依赖铁律。
**用「选样本」代替「吹奏」**，这也是项目做界面时的取舍。

---

## 4 · ★ 写一个插件（核心）

### 4.1 三个文件要先读

| 文件 | 作用 |
|---|---|
| `.spec/PLUGIN-LAYOUT.md` | 插件布局规范（目录、命名、注册位置） |
| `.spec/build/FILE-204-v1.md` | `Registry` 契约（插件如何被发现） |
| `.spec/build/FILE-206-v1.md` | `PluginSpec` 契约（要声明什么） |
| `harmonica_eval/algorithms/bootstrap.py` | 装配根（**读，但别改**） |
| `tests/test_plugin_plugability.py` | 9 个用例，**照着它写就能过** |

### 4.2 注册方式：运行期注册，不是改源码

★ **先看清 `PluginSpec` 的真实签名**（★ 与 `tests/test_plugin_plugability.py:76` 一致）：

```python
PluginSpec(
    algorithm_id: str,                 # ← 不是 plugin_id
    algorithm_version: str,
    label: str,                        # ← 不是 display_name
    required_inputs: tuple[InputRequirement, ...],   # ← 不是 required_ports
    optional_inputs: tuple[InputRequirement, ...],
    entry: Callable[[AlgorithmDataContract], AlgorithmResultEnvelope],
)                                        # ← 不是 run
```

★ **`entry` 收的是数据面（`AlgorithmDataContract`）。**
★ 读端口要**两段**：`surface.read(port_id).data`——★ 漏掉 `.data` 会抛异常。

```python
from harmonica_eval.algorithms.registry import Registry
from harmonica_eval.contract import (
    PluginSpec, InputRequirement, AlgorithmResultEnvelope, UiScalar,
)

# ① 插件入口
def my_entry(surface) -> AlgorithmResultEnvelope:
    # ★★ 读端口是【两段】：surface.read(port_id).data
    # ★★ 漏掉 .data → AttributeError → status=FAILED
    ref_pitch = surface.read("pitch.reference").data
    my_value = float(ref_pitch.mean())
    return AlgorithmResultEnvelope(
        algorithm_id="my_algorithm",
        algorithm_version="1.0.0",
        status="OK",
        required_ports=("pitch.reference",),
        consumed_ports=("pitch.reference",),
        # ★ 指标放 payload，★ 不是 scalars=
        # ★★★ key 只写【指标名】，★ 投影层会自动加 "你的插件id." 前缀 ★★★
        # ★★ 若你写成 "my_algorithm.mean_value"，★ 出来会是双前缀
        payload=(UiScalar("mean_value", "我的指标", my_value, "db"),),
        error_code=None,
        error_detail=None,
    )

# ② 运行期注册：★ 要注册到【装配根产出的】registry 上
def register(registry: Registry) -> None:
    registry.register(PluginSpec(
        algorithm_id="my_algorithm",
        algorithm_version="1.0.0",
        label="我的算法",
        required_inputs=(InputRequirement(port_id="pitch.reference"),),
        optional_inputs=(),
        entry=my_entry,
    ))
```

### 4.2b ★★ 把它接进 HostApp（★ 最容易漏的一步）

★ **`build_default_app()` 会在内部自建 registry，★ 在它外面注册等于没注册。**

```python
from harmonica_eval.algorithms.bootstrap import build_default_registry
from harmonica_eval.core.api import HostCore
from harmonica_eval.host.app import HostApp

registry = build_default_registry()   # ★ 拿装配根产出的那个
register(registry)                     # ★ 在【它】上面注册
app = HostApp(core=HostCore(), registry=registry)   # ★ 自己构造 HostApp
```

★★ **★ 四个「看起来对但静默失败」的坑 ★★**
```
① ★ 少写 .data        → 抛 AttributeError，★ 指标不出现
② ★ 注册在 build_default_app() 外面 → ★ 无报错，★ 指标就是不出现
③ ★ key 写成全名      → 出来是 my_algorithm.my_algorithm.x，★ 双前缀
④ ★ 端口 id 写错      → 该算法 FAILED，★ 而其它插件照常跑，★ 你要读 error_detail 才看得见
★ ★ ★ 而 ② 最阴：★ 它【不报错】，★ 你只会以为插件没产出
```

★ **★ 最可靠的参照：`tests/test_plugin_plugability.py` 的 `_entry` 与 `_spec` ★★**
★ 那 9 个用例是本项目插件契约的可执行事实源，★ 拿不准就去读它。

### 4.3 三条硬性要求

1. **`key` 只写指标名，不要带插件前缀** —— ★ 投影层会自动加 `插件id.`（`host/app.py:544`）。★ 你写 `mean_value` → 出来是 `my_algorithm.mean_value`；★ 写全了会变成双前缀。界面按这个前缀分组显示。
2. **`required_inputs` 里的端口必须真实存在** —— 端口由数据面构建（`BUILD_SURFACE`）产生，插件只消费。★ 现成的有 12 个，清单见页面的「数据端口」表。
3. **`sample_rate` 是冻结规格** —— 端口的 `sample_rate` 恒为 44100，不要按实际音频的采样率假设。

### 4.4 为什么"不改 bootstrap 源码"也算插拔

项目有一条**退化守卫**：若你通过改 `bootstrap.py` 源码来注册插件（而不是运行期 `registry.register`），
`tests/test_plugin_plugability.py` 会失败。

守的是什么：架构承诺是**「不改内核源码也能容纳新插件」**。一旦允许改源码注册，
这个承诺就没了——而它正是本项目组件设计的核心（深接口、降低信息熵）。

**所以：不改源码，是设计要求，不是刁难。**

### 4.5 验证你的插件

```bash
# 1. 全量测试（你必须全绿）
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q

# 2. 单独跑插拔测试
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_plugin_plugability.py
```

---

## 5 · 提交前必跑的门禁（全部串行，不要并发）

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q                    # 测试
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_shell.py            # 文件铭牌/命名/冻结产物
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_counts.py            # 文档里的数量声明 vs 实际
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_plugin_contract.py   # 插件契约
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_injection_wiring.py  # 注入链
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_reachability.py      # 可达性
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_deliverable_hygiene.py
git diff --check
```

**必须串行**——这些门禁都写 `data/out`，并发跑会产生不存在的失败。

> `verify_shell.py` 里有一项检查「宪章引用真实性」，它依赖一个**不在库内**的外部文件。
> 你在自己机器上会看到 `⚠️ 找不到宪章，跳过` —— **这是正常的，不影响其余判据**。

---

## 6 · 常见坑（都是本项目真实踩过的）

1. **`app.submit(cmd)` 没有 `session_id` 参数** —— 签名是 `submit(self, command)`。会话 id 在 `UiView` 快照里。
   历史上多次在这一步写错签名。
2. **调用前要先 `create_session()`** —— 否则报「尚未创建会话」。
3. **`UiScalar` 没有 `timeline_basis` 参数** —— 那是 `UiSeries` 才有的。
4. **`str.strip("─ ")` 会吃掉结尾字母** —— `strip` 收的是**字符集**，`"pitch".strip("─ ")` 得到 `"tch"`。这类字符集陷阱会让断言恒假。
5. **返回类型可能是 `object` 而非 `str`** —— `build_plots` 的契约就是这样，不要假定是字符串。

> 第 4 条的教训：**断言要断言语义，探针也要断言语义。** 一个恒真的测试比红着更糟。

---

## 7 · 不该引入的东西

本项目只做「双音频对比 → 客观数值指标」。以下**一律不做**：

- 自然语言反馈生成、Agent、LLM 评价
- AI 审美评分、生成"理想演奏"
- UI 产品化、模型训练
- 任何 `SPEC.md` 未列出的特征维度

另：铁律 4「零噪声」——**不写"以后可能有用"的抽象层**，不加未被要求的配置项。
一个只被一处调用、且调用方全传默认值的参数，就是这种该删的东西。

---

## 8 · 遇到问题

- 规格问题（"该怎么做有歧义"）→ 提 issue 引用 `.spec/` 里对应文件
- 门禁失败但你觉得判据错了 → 提 issue，**不要改判据让它变绿**
- 想改冻结契约（`contract.py`）→ 先开 issue 讨论，不要直接 PR
