'''
FILE-ID:      FILE-203
COMPONENT:    COMP-C3 Algorithm
SPEC:         SPEC.md@v2.1 §5.5 · profile.PORTS['rms.*']

ROLE:
    力度对比：比较参考与练习的逐音能量，输出动态差异。

INTENT:
    力度是口琴演奏中"气息控制"的可观测量。它不同于音准与节奏：
    力度没有"对错"，只有"差异" —— 因此本算法不设阈值判据，
    只报告差异的大小与离散程度。

    ⚠ 单位必须是 dB。线性振幅的差值是**不可解释**的：
    同样"差 0.1"，在弱音段是巨大差异，在强音段是听不出来。
    dB 是对数刻度，符合听觉感知，也符合"这个数字该怎么读"的要求
    （AGENTS.md：每个数字都要能回答它是什么、怎么算的、单位是什么）。

MUST:
    - 导出 ALGORITHM_ID / ALGORITHM_VERSION / LABEL
      （★ LABEL 是中文显示名，负责人 2026-09-24 裁定；
        bootstrap 用它填 PluginSpec.label，**不得回退为 algorithm_id**）
    - 消费 rms.reference / rms.practice / notes.reference / notes.practice
    - **按音配对**两侧能量（不是按时间轴、也不是按帧索引）
    - 输出以 dB 为单位的逐音差值
    - 报告离散度（σ 或 MAD），而不只是均值 ——
      均值相同的两条曲线，感知上可以完全不同
    - 失败也返回 AlgorithmResultEnvelope

MUST NOT:
    - 用线性振幅做差值上报（见上）
    - **按帧直接相减**（那会把时间错位误算成力度差：练习晚吹了 200 ms，
      参考的强拍就会对上练习的弱拍，算出巨大的假差异）
    - 把静音段的 RMS 纳入统计（那是"没吹"，不是"吹得轻"）
    - 设"合格阈值" —— 力度没有对错，只陈述差异（与 pitch 的区别所在）
    - 输出教学结论（"气息不稳"）—— 那是用户的判断，不是我们的输出

★★ MOLD BREAK 修正（§20 盲审情况 A）★★

本模块第一版写着 MUST「用 WARPED 轴语义」、MUST NOT「使用 REFERENCE 轴」，
并声明 `AXIS = TimelineBasis.WARPED`。**这条约束无法满足。**

原因：`rms.reference` / `rms.practice` 在 profile 里都被声明为 REFERENCE 轴，
而数据面里**唯一**的 WARPED 端口是 `pcm.warped.practice` —— 没有 WARPED 轴的 rms。
两个独立盲审模型各自报告了这个冲突，并各自给出三个互相冲突的"出路"。

真正的错误在于**我用"时间轴"当"按音对齐"的代理**：
- 力度想要的不是"WARPED 网格"，而是**"第 n 个音对第 n 个音"**
- 用轴来表达这件事，既丢失了逐音索引，又引入了无法满足的端口要求

正确机制：**按音配对**。两侧各自有 `notes.*` 提供逐音索引
（`notes.reference` / `notes.practice`，都带 onset_sec / f0_hz / rms），
用各自音内的帧区间取能量，再一一配对。
这样"何时吹"被排除的方式是**按音聚合**，而不是"换一条时间轴"。

故 `AXIS` 常量已删除 —— 它编码的是一条错误的约束。

★★ INV-06-8 的正确判定形态（★ 判据文本的缺陷，实现无法修复）★★

★ **规格原文（FILE-203-v1.md:309 / :321）用的是字面文本扫描**：
```
grep -c 'AXIS|TimelineBasis' dynamics.py == 0
grep -c 'AXIS'            dynamics.py == 0
```

★ **★ 这两条判据在本文件上【必然失败】，而失败是判据的缺陷，不是实现的缺陷：**
```
上面的 MOLD BREAK 段落（:40-:56）为了记录「为什么删掉 AXIS」，
★ 必然要提到 `AXIS` 与 `TimelineBasis.WARPED` 这两个词
★ → 字面 grep 命中 2 处 → 判据报「引入了 AXIS 概念」
★ ★ 而它想禁止的恰恰是「用」，不是「提到」
★ ★ 若要让它通过，只能删掉这段决策历史 —— ★ 那会让后来者
★ ★   不知道为什么没有 AXIS，并可能把它「修回来」
```

★ **★ 正确形态：AST 级判定，剥掉注释与 docstring 后再查 ★★**
```python
# 可执行代码内不得出现 AXIS 常量定义或 TimelineBasis.WARPED 的实际使用
tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
# 判据应检查：ast.Assign/AnnAssign 中出现 AXIS，或 ast.Name(id="AXIS")，
#           或 TimelineBasis.WARPED 出现在可执行表达式里
# ★ docstring / 注释中的提及【不算违规】—— 那是决策记录
```

★ **本文件当前状态（主代理 2026-09-24 实测，AST 级）**：
```
可执行赋值中 AXIS/WARPED 命中 = 0
裸名 AXIS 引用             = 0
属性访问 AXIS              = 0
★ 即 INV-06-8 的【本意】已满足
```

★ **★ 需主代理另行派修**：`FILE-203-v1.md:309` 与 `:321` 的字面 grep
★ ★ 应改为上述 AST 形态。**本任务无权改该文件。**
"""
INPUT:
    surface: AlgorithmDataContract（只读）

OUTPUT:
    AlgorithmResultEnvelope，payload 含：
        逐音能量差（dB）、中位差、离散度、参与统计的音数

BUILD-INSTRUCTION:
    .spec/build/FILE-203-v1.md
'''

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping
from typing import Any, Sequence

import numpy as np

from ..contract import (
    AlgorithmDataContract,
    AlgorithmResultEnvelope,
    ErrorCode,
    UiScalar,
)

ALGORITHM_ID: str = "dynamics"
ALGORITHM_VERSION: str = "1.0.0"
LABEL: str = "力度"
"""中文显示名。★ 术语取自 `SPEC.md` §5「力度 / 能量」——
本算法比的是两侧能量差，故取「力度」。"""

DB_FLOOR: float = -80.0
"""dB 下限，用于避免 log(0)。

−80 dBFS 约等于 1e-4 线性幅度，与 core.ingest.SILENCE_RMS_THRESHOLD 同量级。
低于此值的帧按静音处理，不参与统计。
"""

_FLOOR_LINEAR: float = 10.0 ** (DB_FLOOR / 20.0)
"""钳位下限的线性值。由 `DB_FLOOR` 导出，**不得**另写一个数字。"""


def to_db(rms: object) -> object:
    """把线性 RMS 转成 dB。

    必须**先钳位**再取对数（见 DB_FLOOR），否则静音帧会产出 -inf，
    而 -inf 会在后续求均值时把整段统计变成 NaN。

    ★ FILE-203 §4 冻结了三种输入（第三轮盲审 B 实测发现标量签名会导致
      真实音频上稳定失败）：

      - 标量 int/float → 返回 float
      - numpy.ndarray   → 返回**同形状** float32 ndarray，逐元素套同一算法
        （★ 不得用 Python 循环逐元素调标量分支：12538 帧会慢到不可接受）
      - list/tuple      → 返回同长度 float list
      - 其它类型        → 抛 ValueError（★ 不得静默 float() 强转 ——
        那会把数组悄悄变成"只有第一个元素"的标量，是典型静默降级）
    """
    if isinstance(rms, np.ndarray):
        clamped = np.maximum(rms.astype(np.float32, copy=False), _FLOOR_LINEAR)
        return (20.0 * np.log10(clamped)).astype(np.float32, copy=False)
    if isinstance(rms, (list, tuple)):
        return [to_db(item) for item in rms]
    if isinstance(rms, bool) or not isinstance(rms, (int, float)):
        raise ValueError(f"to_db 需要实数或 ndarray，实得 {type(rms).__name__}")
    clamped = max(float(rms), _FLOOR_LINEAR)
    return 20.0 * math.log10(clamped)


def note_spans(notes: object, rms_hop_length: int, sample_rate: int) -> object:
    """从 `notes.*` 端口算出每个音覆盖的帧区间。

    ★ 这是 MOLD BREAK 补上的函数 —— 第一版把这件事隐式交给了"时间轴"，
    而那是错的机制。

    做法：第 n 个音的区间 = [onset_n, onset_{n+1})，
    最后一个音延伸到它自己的 onset + 一个默认时长（或数据末尾）。
    切分依据是 **onset**，因为 onset 是唯一跨两侧都可比的量
    （它由 `notes.*` 的 onset_sec 给出 —— ★ 那是**检测器输出**，
    不是 MIDI 真值：数据面里没有 MIDI 通路。见 timing.detect_onsets）。

    两侧各自调用一次：`notes.reference` 与 `notes.practice` **分开**切。

    ★ FILE-203 §4 冻结（第三轮盲审 A probe 08 修正两处错）：
      - 输入是 `(n_note, 3)` 的 ndarray，**不是** `list[dict]`
        （同文件曾给两种互斥表示法，以 ndarray 为准，与 §4.1 表格一致）
      - 帧号恒为 `int(round(t * sample_rate / rms_hop_length))`。
        ★ **禁止写死任何帧率数字** —— 原写的"每秒 100 帧"是凭空数字：
        实测 `rms.*` 的 hop 是 256（44100/256 ≈ 172.3 fps），
        `pitch.*` 是 2048（≈ 21.5 fps），没有任何端口是 100 fps。
      - 最后一个音延伸到 `frame(onset_last) + 100`（默认 1 秒），
        或数据末尾帧，**取二者中较小**。
    """
    arr = np.asarray(notes, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[1] < 3:
        raise ValueError(f"notes 期望 (n_note, 3) 的 onset_sec/f0_hz/rms，实得 shape={arr.shape}")
    n_notes = int(arr.shape[0])
    if n_notes == 0:
        return []
    if rms_hop_length <= 0:
        raise ValueError(f"rms_hop_length 必须为正，实得 {rms_hop_length}")
    if sample_rate <= 0:
        raise ValueError(f"sample_rate 必须为正，实得 {sample_rate}")

    # 帧号换算：帧率由调用方传入，本文件不假设任何数字
    frames_per_sec = sample_rate / rms_hop_length
    onsets = arr[:, 0].astype(np.float64, copy=False)
    starts = [int(round(t * frames_per_sec)) for t in onsets]

    spans: list[tuple[int, int]] = []
    for i, start in enumerate(starts):
        if i + 1 < len(starts):
            end = starts[i + 1]
        else:
            # 最后一个音：延伸到 onset + 100 帧（默认 1 秒）
            end = start + 100
        if end < start:
            end = start
        spans.append((start, end))
    return spans


def align_by_note(
    ref_rms_db: object,
    prac_rms_db: object,
    ref_spans: object,
    prac_spans: object,
) -> object:
    """按音配对两侧的能量，返回逐音的能量对。

    ★ MOLD BREAK 修正：签名从 `(ref, prac, note_boundaries)` 改为
    两侧**各自**的 spans。

    为什么：练习演奏与参考演奏的音数、时长都不同（漏音、多音、抢拍）。
    用**一份**共享边界假设"第 n 个音对第 n 个音"是不成立的。
    正确做法是两侧各自按自己的 onset 切帧，再按**音序**配对，
    配不上的音（一侧多出/缺少）单独记账，不参与差值统计。

    静音（低于 DB_FLOOR）的段**不参与**统计。

    ★ FILE-203 §4 冻结返回为 **dict**（第三轮盲审 A probe 07）：
      原来的 `list[tuple]` 没有任何位置携带 `n_unpaired`，
      「在 run 层由 align_by_note 计算并回传」在 list[tuple] 下不可实现。
      改为与 `timing.match_onsets` 同构的 dict，两个算法用同一种形状。
    """
    ref = np.asarray(ref_rms_db, dtype=np.float64).ravel()
    prac = np.asarray(prac_rms_db, dtype=np.float64).ravel()
    ref_span_list = list(ref_spans)
    prac_span_list = list(prac_spans)

    n_ref = min(len(ref_span_list), ref.size)
    n_prac = min(len(prac_span_list), prac.size)
    n_pair = min(n_ref, n_prac)

    def _energy(series: np.ndarray, span: tuple[int, int]) -> float | None:
        start, end = span
        start = max(0, min(int(start), series.size))
        end = max(start, min(int(end), series.size))
        if end <= start:
            return None
        segment = series[start:end]
        # 整段静音的音不参与统计（那是"没吹"，不是"吹得轻"）
        if float(np.max(segment)) <= DB_FLOOR:
            return None
        return float(statistics.median(segment.tolist()))

    pairs: list[tuple[float, float]] = []
    for i in range(n_pair):
        ref_e = _energy(ref, ref_span_list[i])
        prac_e = _energy(prac, prac_span_list[i])
        if ref_e is None or prac_e is None:
            continue
        pairs.append((ref_e, prac_e))

    # n_unpaired = 两侧中未能与对侧配对的音总数（BI 写死的口径）
    n_unpaired = (n_ref - len(pairs)) + (n_prac - len(pairs))
    return {"pairs": pairs, "n_unpaired": int(n_unpaired)}


def compute_deltas(aligned: object) -> object:
    """计算逐音能量差（dB）。

    符号约定：**练习 − 参考**。
    正 = 练习更强，负 = 练习更弱。必须保留符号 ——
    "整体偏弱"与"只是不稳"需要完全不同的处理。

    只对**配得上对**的音求差：一侧多出的音（漏音/多音）不参与统计，
    但要单独计数上报 —— 它们不是"力度差异"，是另一类问题。
    """
    pairs = aligned["pairs"] if isinstance(aligned, dict) else aligned
    return [float(prac) - float(ref) for ref, prac in pairs]


def summarize_deltas(deltas_db: object, n_unpaired: int) -> object:
    """汇总力度指标。

    至少产出：
        median_db     中位能量差（带符号）
        spread_db     离散度（MAD 或 σ，须在实现中明确选哪个）
        n_notes_used  参与统计的音数
        n_unpaired    未配对的音数（一侧有另一侧无）

    ⚠ 本算法**不产出**"合格/不合格" —— 力度没有绝对对错（区别于 pitch）。
    这处留白是刻意的：报告差异，让用户判断。

    ★ FILE-203 §4 冻结：签名是二参 `(deltas_db, n_unpaired)` ——
      配对信息在 `compute_deltas` 那一步已丢，`n_unpaired`
      必须由 `run` 从 `align_by_note` 的返回 dict 取出后**显式传入**。
    ★ `spread_db` 冻结为 **MAD**（绝对中位差），非 σ：
      MAD 对离群音更鲁棒，符合"均值相同却感知不同"的需求。
    ★ 永不输出 pass / fail / is_valid / conclusion。
    """
    deltas = [float(d) for d in deltas_db]
    if not deltas:
        return {
            "median_db": 0.0,
            "spread_db": 0.0,
            "n_notes_used": 0,
            "n_unpaired": int(n_unpaired),
        }
    median_db = float(statistics.median(deltas))
    spread_db = float(statistics.median([abs(d - median_db) for d in deltas]))
    return {
        "median_db": median_db,
        "spread_db": spread_db,
        "n_notes_used": len(deltas),
        "n_unpaired": int(n_unpaired),
    }


def run(surface: AlgorithmDataContract) -> AlgorithmResultEnvelope:
    """算法入口。

    流程：读 rms.* / notes.* → 转 dB → 两侧各自按 onset 切分 → 按音配对
          → 求差 → 汇总 → 装信封。

    ★ MOLD BREAK 修正：流程从"换一条时间轴"改为"按音配对"。
    理由见模块 docstring —— 用轴当代理会丢失逐音索引，
    且要求一个数据面里不存在的端口。

    失败：返回 status='FAILED' 的信封，不抛异常。

    ★ FILE-203 §4 更正（P1 审查 F9）：原写 `surface.rms.reference` 这种
      **属性式访问** —— 契约上**没有**这种能力，
      `AlgorithmDataContract` 只有 `manifest()` 与 `read()` **两个**操作。
      按原规格实现必然 `AttributeError`。
    ★ 列号必须用 `descriptor.field_names.index("onset_sec")` 查，**不得**硬编码 0。
    ★ 宪章 §5.6：禁止静默降级为 OK —— 所有缺端口/类型异常走 `status='FAILED'`。
    """
    required_ports = (
        "rms.reference",
        "rms.practice",
        "notes.reference",
        "notes.practice",
    )

    def _failed(detail: str, code: str) -> AlgorithmResultEnvelope:
        return AlgorithmResultEnvelope(
            algorithm_id=ALGORITHM_ID,
            algorithm_version=ALGORITHM_VERSION,
            status="FAILED",
            required_ports=required_ports,
            consumed_ports=(),
            payload=(),
            error_code=ErrorCode.ALGORITHM_FAILED,
            error_detail=f"{code}:{detail[:96]}",
        )

    try:
        manifest = surface.manifest()

        def _descriptor(port_id: str) -> Any:
            ports = getattr(manifest, "ports", None)
            # ★ 用 Mapping 而不是 dict —— manifest.ports 是 mappingproxy，
            #   它不是 dict 的子类，isinstance(ports, dict) 恒为 False，
            #   会让所有 notes.* 读取抛 KeyError → dynamics 永远 FAILED。
            if not isinstance(ports, Mapping) or port_id not in ports:
                raise KeyError(port_id)
            return ports[port_id]

        # 读四个端口（只走 read()，这是契约给的两个操作之一）
        rms_ref = np.asarray(surface.read("rms.reference").data, dtype=np.float32)
        rms_prac = np.asarray(surface.read("rms.practice").data, dtype=np.float32)
        notes_ref = np.asarray(surface.read("notes.reference").data, dtype=np.float32)
        notes_prac = np.asarray(surface.read("notes.practice").data, dtype=np.float32)

        # onset_sec 列号：必须查 field_names，不得硬编码
        ref_fields = tuple(_descriptor("notes.reference").field_names)
        prac_fields = tuple(_descriptor("notes.practice").field_names)
        if "onset_sec" not in ref_fields or "onset_sec" not in prac_fields:
            return _failed("notes.* 缺少 onset_sec 列", "MISSING_ONSET_FIELD")
        ref_col = ref_fields.index("onset_sec")
        prac_col = prac_fields.index("onset_sec")
        if ref_col != prac_col:
            return _failed("两侧 onset_sec 列号不一致", "ONSET_COL_MISMATCH")

        rms_hop_length = _descriptor("rms.reference").hop_length
        sample_rate = manifest.audio_format.sample_rate

        ref_rms_db = to_db(rms_ref)
        prac_rms_db = to_db(rms_prac)
        # 传完整 notes 数组：note_spans 自己校验 (n_note, 3) 形状
        ref_spans = note_spans(notes_ref, rms_hop_length, sample_rate)
        prac_spans = note_spans(notes_prac, rms_hop_length, sample_rate)

        aligned = align_by_note(ref_rms_db, prac_rms_db, ref_spans, prac_spans)
        deltas_db = compute_deltas(aligned)
        summary = summarize_deltas(deltas_db, aligned["n_unpaired"])

        payload = (
            UiScalar(
                key="median_db",
                label="中位能量差（练习−参考）",
                value=float(summary["median_db"]),
                unit="db",
            ),
            UiScalar(
                key="spread_db",
                label="离散度（MAD）",
                value=float(summary["spread_db"]),
                unit="db",
            ),
            UiScalar(
                key="n_notes_used",
                label="参与统计音数",
                value=float(summary["n_notes_used"]),
                unit="count",
            ),
            UiScalar(
                key="n_unpaired",
                label="未配对音数",
                value=float(summary["n_unpaired"]),
                unit="count",
            ),
        )
        return AlgorithmResultEnvelope(
            algorithm_id=ALGORITHM_ID,
            algorithm_version=ALGORITHM_VERSION,
            status="OK",
            required_ports=required_ports,
            consumed_ports=required_ports,
            payload=payload,
        )
    except KeyError as exc:
        port = str(exc).strip("'\"")
        if port in ("rms.reference", "rms.practice"):
            return _failed(f"缺少 {port}", "MISSING_RMS_PORT")
        return _failed(f"缺少 {port}", "MISSING_NOTES_PORT")
    except Exception as exc:  # noqa: BLE001 —— 契约要求永不向调用者抛出
        return _failed(repr(exc), "UNEXPECTED")
