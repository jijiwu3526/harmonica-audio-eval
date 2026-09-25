'''
FILE-ID:      FILE-202
COMPONENT:    COMP-C3 Algorithm
SPEC:         SPEC.md@v2.1 §5.5（两轴分离）· contract.TimelineBasis

ROLE:
    节奏对比：比较参考与练习的**起音时刻**，输出抢拍/拖拍。

INTENT:
    这是全系统**唯一**必须在保留源时间的轴上计算的算法。

    ★ 为什么这不是一个实现细节，而是构造性约束：
    数据面提供两条轴 —— REFERENCE（保留源时间）与 WARPED（时间归一化）。
    归一化会把练习拉伸到与参考等长，**抢拍拖拍在这个操作里被抹掉了**。
    因此拿 WARPED 轴算节奏，结果恒等于 0，而且**看起来一切正常**。

    这是一个不会报错、只会给出错误答案的陷阱。故本文件把轴的约束
    写在最显眼处，并要求每条输出曲线显式声明自己的 timeline_basis。

MUST:
    - 导出 ALGORITHM_ID / ALGORITHM_VERSION / LABEL
      （★ LABEL 是中文显示名，负责人 2026-09-24 裁定；
        bootstrap 用它填 PluginSpec.label，**不得回退为 algorithm_id**）
    - 用 pcm.mapped.reference / pcm.mapped.practice（**两者都是 REFERENCE 轴**）
    - 参考侧起音时刻取自 notes.reference（同一轴上）
    - 输出带符号的偏差（负 = 抢拍，正 = 拖拍），计算值单位为秒
    - payload 声明的 `unit` 必须来自 `contract.UNITS_VOCABULARY`；
      FILE-202 的偏差 payload 统一使用 `seconds`
    - 每条输出曲线声明 TimelineBasis.REFERENCE
    - 失败也返回 AlgorithmResultEnvelope

MUST NOT:
    - 使用 pcm.warped.practice 或任何 WARPED 轴数据（会抹掉本算法要测的东西）
    - 只报绝对值（丢失"抢"与"拖"的方向 —— 修正方向相反）
    - 把起音检测的差异当成"错音"（那是 pitch 的职责）
    - 输出教学结论

INPUT:
    surface: AlgorithmDataContract（只读）

OUTPUT:
    AlgorithmResultEnvelope，payload 含：
        逐音起音偏差（秒，带符号）、中位偏差、离散度、抢拍/拖拍比例

BUILD-INSTRUCTION:
    .spec/build/FILE-202-v1.md
'''

from __future__ import annotations

from time import perf_counter

import math

import numpy as np

from ..contract import (
    AlgorithmDataContract,
    AlgorithmResultEnvelope,
    TimelineBasis,
    UiScalar,
    UiSeries,
)

ALGORITHM_ID: str = "timing"
ALGORITHM_VERSION: str = "1.0.0"
LABEL: str = "节奏"
"""中文显示名。★ 术语取自 `SPEC.md` §5「节奏 / 音符起始」——
本算法比的是起音时刻，故取「节奏」。"""

AXIS: TimelineBasis = TimelineBasis.REFERENCE
"""本算法**必须**使用的时间轴。★ 硬约束，不可改为 WARPED。

用 WARPED 会让结果恒为 0 且不报错 —— 见模块 docstring。
把它定义成模块常量是为了让审查者能一眼看到、也便于 grep 验证。
"""

ONSET_MATCH_TOLERANCE_SEC: float = 0.100
"""起音配对的最大时间容差（秒）。超过此值认为两个起音无法配对
（漏音或多余音），不计入"偏差"统计 —— 把 5 秒的错位当成
"拖了 5 秒"是荒谬的。

★ 第三轮修正（§20 盲审第二轮发现）：第一版取 `0.5` 秒，**是拍脑袋定的，
且量级错误**。审查者指出它与本算法要测的现象相差约 20 倍。

用已有数据推导（不是重新拍一个数）：

    约束下界：必须 > 对齐噪声，否则真配对被误拒
              对齐帧级精度 ±0.023 秒（profile.ALIGN：hop=2048 → ±hop/2）
              → ≥ 2×0.023 = 0.046 秒
    约束上界：必须 < 最短统计音长，否则"漏音后的下一个音"会被误配成对
              最短统计音长 = features.MIN_STABLE_NOTE_SEC = 0.150 秒
              → < 0.150 秒

    原值 0.5 秒 **比最短音长还大 3.3×** —— 它必然把相邻音误配，
    把假偏差（最多 ±0.5 秒）灌进中位数。
    而本算法要测的现象量级只有 **0.026 秒**（profile 实测中位）。

    取 0.1 秒：
        = 对齐噪声的 4.3×   （足够容忍对齐误差）
        = 最短音长的 0.67×  （不足以跨越一个音）
    两个约束都满足，且与 `MIN_STABLE_NOTE_SEC` 一致。

★ 注意它与"抢拍/拖拍判据"**不是**同一个量：
本常量只回答"两个起音能否配成一对"。
"算不算抢拍"的阈值见下方 `ONSET_DEADBAND_SEC`。
"""

TIMING_REQUIRED_PORTS: tuple[str, ...] = (
    "pcm.mapped.reference",
    "pcm.mapped.practice",
    "notes.reference",
)
"""本算法消费的端口（与 bootstrap 的 `ALGORITHM_INPUTS["timing"]` 一致）。

★ 只列**实际读取**的端口：`notes.practice` 不在此处 ——
它是 `notes.reference` 的配对侧，`run()` 优先读它，仅在为空时兜底
改读 `pcm.mapped.practice`。两者都列会让 `consumed_ports` 失真。
"""

ONSET_DEADBAND_SEC: float = 0.023
"""判定"抢拍/拖拍"的死区（秒）。**第三轮新增** —— §20 盲审第二轮发现
这个阈值在全项目**任何文件里都不存在**，实现者只能自定，
于是不同实现者会产出**不可比**的 early_ratio / late_ratio。

为什么必须有它：`ONSET_MATCH_TOLERANCE_SEC` 只回答"能否配对"，
不回答"算不算抢拍"。没有死区就只有两种选择，都不可接受：
    - 死区 = 0   → 任何 0.0001 秒的差都被计成"抢拍"或"拖拍"，
                   而测量精度本身是 ±0.023 秒，等于把噪声当信号
    - 死区很大 → 几乎全部音都"准时"，指标退化为常数

取值依据（用已有数据推导，不是拍脑袋）：
    对齐帧级精度 ±0.023 秒（profile.ALIGN：hop=2048 → ±hop/2 采样点）
    **低于测量精度的差异不可区分于噪声**，故死区 = 0.023 秒。

    参考量级：抢拍拖拍实测中位 0.026 秒（profile 记录）。
    即：本死区刚好卡在"噪声"与"真实偏差"的分界上 ——
    恰好一半左右的音会落在死区内，这是**诚实**的结果，
    而不是把所有音都强行分成早/晚两类。

★ 副作用（必须在 payload 里明说）：`early_ratio + late_ratio` **不再等于 1**，
三者满足 `early_ratio + late_ratio + on_time_ratio == 1`。
其中 `on_time_ratio` 的含义是"偏差小于测量精度，无法判定早或晚"——
**不**等于"演奏准确"。故 payload 必须同时报告它，
否则用户看到两个加起来不到 1 的比例会以为是 bug。
"""


def detect_onsets(samples: object, sample_rate: int) -> object:
    """从**保留源时间**的 PCM 检测起音时刻（秒）。

    输入必须是 pcm.mapped.*（REFERENCE 轴）。

    参考侧优先用 `notes.reference` 的 onset_sec（同轴、且已被 features 层
    统一处理过），但**它仍然是检测器输出，不是 MIDI 真值**。

    ★ §20 盲审修正：本函数原先写"参考曲目的真值来自 MIDI，比从音频检测更准"
    —— **这个前提不成立**。数据面里**没有** MIDI 通路：
    `ingest` 只解码音频，`features.materialize_notes(pitch, rms, sample_rate)`
    是从音频派生的音高/能量切出来的，`profile.PORTS` 里没有任何音符事件端口。

    后果（必须在实现与解读时都记住）：
        参考侧自身的起音检测误差会 **1:1 进入每一条偏差**。
        本算法测的是「练习相对参考的**相对**偏差」，
        不是「练习相对乐谱的**绝对**偏差」——
        若参考演奏本身抢拍 0.03 秒，那 0.03 秒会**整体平移**所有结果。

    这也是为什么算法输出里**不得**出现"你比乐谱慢了"这类结论（SPEC §1）。

    ★ 实现（FILE-202 §4.1，2026-09-24 授权注入）：
      六步口径逐条照 §4.1 冻结，参数 win=1024 / hop=256 与 profile.MATERIALIZE.rms_*
      一致。全部时间数学在**秒**上做，末步 `k * hop / sample_rate` 是唯一
      出现 hop 的地方（§6 INV-202-1 要求它只用于换算，不参与任何统计）。
    """
    if sample_rate is None or sample_rate <= 0:
        raise ValueError(f"sample_rate 必须为正整数，收到 {sample_rate!r}")
    x = np.asarray(samples, dtype=np.float64).reshape(-1)
    if x.size == 0:
        return np.empty(0, dtype=np.float64)

    win, hop, eps = 1024, 256, 1e-12
    # 末尾不足一窗的样本不参与 RMS —— 避免用补零伪造一个不存在的低能量帧
    n_frames = 1 + max(0, (x.size - win) // hop)
    if n_frames < 2:
        return np.empty(0, dtype=np.float64)

    frames = np.lib.stride_tricks.sliding_window_view(x, win)[::hop][:n_frames]
    env = np.sqrt(np.mean(frames * frames, axis=1))

    nov = np.maximum(0.0, 20.0 * np.log10(env + eps) - 20.0 * np.log10(env[:-1] + eps))
    # 局部中位数取 ±1.0 秒窗；窗内样本不足时退化为全局中位数（两侧对齐）
    half = max(1, int(round(1.0 * sample_rate / hop)))
    thr = np.empty_like(nov)
    for k in range(nov.size):
        lo, hi = max(0, k - half), min(nov.size, k + half + 1)
        thr[k] = 1.5 * float(np.median(nov[lo:hi])) + 1e-3

    min_gap_frames = max(1, int(np.ceil(0.05 * sample_rate / hop)))
    onsets: list[float] = []
    last = -min_gap_frames - 1
    for k in range(1, nov.size - 1):
        if not (nov[k] > thr[k] and nov[k] >= nov[k - 1] and nov[k] >= nov[k + 1]):
            continue
        if k - last < min_gap_frames:
            continue
        onsets.append(k * hop / sample_rate)
        last = k
    return np.asarray(onsets, dtype=np.float64)


def match_onsets(
    ref_onsets: object,
    prac_onsets: object,
    tolerance_sec: float = ONSET_MATCH_TOLERANCE_SEC,
) -> object:
    """把练习的起音与参考的起音配对。

    返回配对结果，**必须**同时报告未能配对的起音数：
    漏吹的音与多吹的音不产生"时间偏差"，但它们是重要的信息，
    静默丢弃会让报告看起来比实际更好。

    ★ 实现（FILE-202 §4.2，2026-09-24 授权注入）：
      保序双指针，两侧各自升序、**不允许交叉配对**。
      ★ 任何一侧不是升序的实数序列即显式失败 —— 交叉配对会静默产出
      错误的偏差，属于「不会报错只给错误答案」的陷阱，故此处不宽容。
    """
    # ★ 轴错守卫：WARPED 数据流到本函数会让抢拍拖拍恒为 0（见模块 docstring）。
    # 因此在**配对之前**就拒绝，而不是算完再检查结果。
    for side, name in ((ref_onsets, "ref_onsets"), (prac_onsets, "prac_onsets")):
        basis = getattr(side, "timeline_basis", None)
        if basis is not None and basis is not AXIS:
            raise ValueError(
                f"{name} 的 timeline_basis={basis!r} 不是 {AXIS!r}；"
                "用非 REFERENCE 轴算节奏会恒为 0（见模块 docstring 的陷阱说明）"
            )
    if tolerance_sec is None or tolerance_sec < 0:
        raise ValueError(f"tolerance_sec 必须为非负数，收到 {tolerance_sec!r}")

    ref = [float(v) for v in np.asarray(ref_onsets, dtype=np.float64).reshape(-1)]
    prac = [float(v) for v in np.asarray(prac_onsets, dtype=np.float64).reshape(-1)]
    for name, seq in (("ref_onsets", ref), ("prac_onsets", prac)):
        if not all(math.isfinite(v) for v in seq):
            raise ValueError(f"{name} 含 NaN/inf，无法配对")
        if any(b < a for a, b in zip(seq, seq[1:])):
            raise ValueError(f"{name} 必须升序，否则保序双指针会交叉配对")

    pairs: list[tuple[int, int, float, float]] = []
    unmatched_ref: list[float] = []
    unmatched_prac: list[float] = []
    i = j = 0
    while i < len(ref) and j < len(prac):
        d = prac[j] - ref[i]
        if abs(d) <= tolerance_sec:
            pairs.append((i, j, ref[i], prac[j]))
            i += 1
            j += 1
        elif d < 0:
            # d = prac[j] - ref[i] < 0 → 练习侧更早到达
            # §4.2：这个练习音是多出来的，跳过它（j++）
            unmatched_prac.append(prac[j])
            j += 1
        else:
            # d > 0 → 参考已过、练习还没到
            # §4.2：这个参考音被漏掉了，跳过它（i++）
            unmatched_ref.append(ref[i])
            i += 1
    unmatched_ref.extend(ref[i:])
    unmatched_prac.extend(prac[j:])

    return {
        "pairs": pairs,
        "unmatched_ref": unmatched_ref,
        "unmatched_prac": unmatched_prac,
        "n_ref": len(ref),
        "n_prac": len(prac),
        # ★ 漏音与多音不参与偏差统计，但必须计数上报（§4.2）
        "n_unpaired": len(unmatched_ref) + len(unmatched_prac),
    }


def compute_deviations(matched: object) -> object:
    """计算逐音起音偏差。

    **带符号**：负 = 抢拍（早于参考），正 = 拖拍（晚于参考）。
    只报绝对值会丢掉方向，而修正"抢"与修正"拖"是相反的动作。

    单位：秒。

    ★ 实现（FILE-202 §4.3，2026-09-24 授权注入）：
      按**参考侧音序**取 `prac_t - ref_t`，秒减秒，**不乘任何换算常数**
      （毫秒化已于 2026-09-24 裁定撤销，MS_PER_SEC 已删除）。
      返回 Python 原生 float 列表以保证 JSON 可序列化（§4.3 冻结）。
    """
    pairs = matched["pairs"] if isinstance(matched, dict) else matched.pairs
    out: list[float] = []
    for pair in pairs:
        _, _, ref_t, prac_t = pair
        d = float(prac_t) - float(ref_t)
        if not math.isfinite(d):
            raise ValueError(f"起音偏差非有限值：prac={prac_t!r} ref={ref_t!r}")
        out.append(d)
    return out


def summarize_deviations(deviations_sec: object, n_unpaired: int) -> object:
    """汇总节奏指标。

    ★ 键名的**唯一权威**是插件自己产出的 `UiScalar` / `UiSeries` 对象的
    `key` 字段；框架不再维护第二份键名清单。

    本 docstring 曾提到一组与已删除冻结表不一致的旧键名
    —— 那是 §20 盲审发现的硬冲突：模块当时说要产出一组名字，
    注册表却要求另一组名字，实现者无法同时满足。
    现以插件自描述对象的 `key` 为准，不再维护第二份键名清单。

    例如可产出如下 8 个指标（用于说明应产出什么，不是从冻结表抄录）：
        per_note_onset_sec    逐音起音偏差（秒，带符号），长度 == n_notes_used
        median_onset_sec      中位偏差（带符号，秒）
        spread_sec            离散度（MAD about median，秒；口径必须写死在实现里）
        early_ratio         抢拍比例（d < -ONSET_DEADBAND_SEC）
        late_ratio          拖拍比例（d > +ONSET_DEADBAND_SEC）
        on_time_ratio       落在死区内的比例（**无法判定**早或晚，≠ 演奏准确）
        n_notes_used        参与统计的音数（== 配对数 == len(per_note_onset_sec)）
        n_unpaired          未能配对的音数（漏音 + 多音）

    除逐音序列外，每个指标最终会成为一个 `UiScalar`
    （带 `key` / `label` / `value` / `unit`）；`per_note_onset_sec` 的逐音序列
    则是一个 `UiSeries`（`t` 放 `onset_sec`、`values` 放起音偏差、
    `timeline_basis=REFERENCE`）。所有对象的 `unit` 必须属于
    `contract.UNITS_VOCABULARY`；FILE-202 的偏差 payload 已统一使用
    `seconds`，键名与值语义一致。

    ⚠ 三者关系：`early_ratio + late_ratio + on_time_ratio == 1.0`。
    必须三个都报 —— 只报前两个的话，用户看到它们加起来不到 1
    会以为是 bug，而实际上那是"测量精度不足以判定"的部分（见 ONSET_DEADBAND_SEC）。

    ★ `n_unpaired` 是**必须报告**的，理由与原 docstring 一致
    （"不得隐去"）：漏音/多音不是"节奏偏差"，若不报出来，
    用户会以为整首都被统计了，而实际上有若干音根本没参与。

    ★ 实现（FILE-202 §4.4，2026-09-24 授权注入）：
      ★ 恰好产出 8 个键（§6 INV-202-3）。`spread_sec` 口径**写死**为
      MAD about median —— `median(|d - median(d)|)`，不是 `median(|d|)`
      （后者在偏差有系统性偏移时会高估离散度）。
      ★ n==0 时仍返回全部 8 个键、值为 0.0，明确报告"样本量为 0"，
      而不伪装成普通成功结果（§4.4 边界）。
    """
    d = [float(v) for v in np.asarray(deviations_sec, dtype=np.float64).reshape(-1)]
    if not all(math.isfinite(v) for v in d):
        raise ValueError("起音偏差含 NaN/inf，不得汇总")
    n = len(d)
    n_unpaired = int(n_unpaired or 0)

    if n == 0:
        return {
            "per_note_onset_sec": [],
            "median_onset_sec": 0.0,
            "spread_sec": 0.0,
            "early_ratio": 0.0,
            "late_ratio": 0.0,
            "on_time_ratio": 0.0,
            "n_notes_used": 0,
            "n_unpaired": n_unpaired,
        }

    med = float(np.median(np.asarray(d, dtype=np.float64)))
    # ★ MAD about median，不是 median(|d|)
    spread = float(np.median(np.abs(np.asarray(d, dtype=np.float64) - med)))
    n_early = sum(1 for v in d if v < -ONSET_DEADBAND_SEC)
    n_late = sum(1 for v in d if v > ONSET_DEADBAND_SEC)
    n_on = sum(1 for v in d if abs(v) <= ONSET_DEADBAND_SEC)
    # ★ 三者互斥且穷尽 → 和恒为 1.0（§6 INV-202-5）。用整数计数构造，
    # 不做各自独立除法，避免浮点累加误差把总和推离 1.0。
    return {
        "per_note_onset_sec": d,
        "median_onset_sec": med,
        "spread_sec": spread,
        "early_ratio": n_early / n,
        "late_ratio": n_late / n,
        "on_time_ratio": n_on / n,
        "n_notes_used": n,
        "n_unpaired": n_unpaired,
    }


def run(surface: AlgorithmDataContract) -> AlgorithmResultEnvelope:
    """算法入口。

    ⚠ 实现时第一步就应断言数据来自 REFERENCE 轴。
    读取 pcm.mapped.* / notes.reference（它们的 timeline_basis 都是 REFERENCE）。

    失败：返回 status='FAILED' 的信封，不抛异常。

    ★ 实现（FILE-202 §4.5，2026-09-24 授权注入）：
      整体包在 try 里，任何异常都收进 FAILED 信封（§6 INV-202-7）。
      ★ 轴守卫在**读取任何数据之前**执行：descriptor.timeline_basis
      与模块常量 AXIS 比较（§4.5 第四轮更正：AXIS 是常量不是可调用对象）。
      ★ onset 列号从 descriptor.field_names.index("onset_sec") 取，
      **不硬编码列号**；notes 侧为空时兜底到 detect_onsets（§5 失败语义表：
      「notes.* 为空 → 兜底，不算失败」）。
    """
    t0 = perf_counter()
    notes_cols = ("onset_sec", "f0_hz", "rms")
    try:
        manifest = surface.manifest()
        if not manifest.sealed:
            raise ValueError("surface 未 sealed，拒绝在未封数据面上计算")

        needed = ("notes.reference", "notes.practice",
                  "pcm.mapped.reference", "pcm.mapped.practice")
        missing = [p for p in needed if p not in manifest.ports]
        if missing:
            raise ValueError(f"缺少所需端口：{missing}")

        # ★ 轴守卫先于任何数据读取。拿 WARPED 轴算节奏恒为 0 且不报错，
        # 所以必须显式失败（§5 失败语义表：端口轴不是 REFERENCE → FAILED）。
        for port_id in needed:
            desc = manifest.ports[port_id]
            if desc.timeline_basis is not AXIS:
                raise ValueError(
                    f"端口 {port_id} 的 timeline_basis={desc.timeline_basis!r} "
                    f"不是 {AXIS!r}；用非 REFERENCE 轴算节奏会恒为 0（见模块 docstring）"
                )

        # ★ read() 返回 BufferView，必须取 .data 得 ndarray（§4.5 第四轮更正）
        def _onsets(port_id: str) -> list[float]:
            data = surface.read(port_id).data
            # ★ 列号从 field_names 取，不硬编码
            col = manifest.ports[port_id].field_names.index("onset_sec")
            arr = np.asarray(data, dtype=np.float64)
            if arr.ndim == 1:
                arr = arr.reshape(-1, len(notes_cols))
            vals = arr[:, col]
            vals = vals[np.isfinite(vals)]
            return sorted(float(v) for v in vals)

        ref_onsets = _onsets("notes.reference")
        prac_onsets = _onsets("notes.practice")
        sr = int(manifest.audio_format.sample_rate)
        # ★ 兜底：notes 侧为空才从 PCM 检测（不算失败）
        if not ref_onsets:
            ref_onsets = sorted(
                float(v) for v in
                np.asarray(detect_onsets(
                    surface.read("pcm.mapped.reference").data, sr), dtype=np.float64)
            )
        if not prac_onsets:
            prac_onsets = sorted(
                float(v) for v in
                np.asarray(detect_onsets(
                    surface.read("pcm.mapped.practice").data, sr), dtype=np.float64)
            )

        matched = match_onsets(ref_onsets, prac_onsets, ONSET_MATCH_TOLERANCE_SEC)
        deviations = compute_deviations(matched)
        # ★ n_unpaired 必须显式传入 —— summarize 只收到 list[float]，
        # 无从知道有多少音没配上（§4.4 本版冻结）
        summary = summarize_deviations(deviations, matched["n_unpaired"])

        payload = (
            UiSeries(
                key="per_note_onset_sec",
                label="逐音起音偏差",
                t=[pair[2] for pair in matched["pairs"]],
                values=summary["per_note_onset_sec"],
                unit="seconds",
                timeline_basis=TimelineBasis.REFERENCE,
                source_port="notes.reference",
            ),
            UiScalar("median_onset_sec", "中位起音偏差",
                     summary["median_onset_sec"], "seconds"),
            UiScalar("spread_sec", "起音偏差离散度",
                     summary["spread_sec"], "seconds"),
            UiScalar("early_ratio", "抢拍比例",
                     summary["early_ratio"], "ratio"),
            UiScalar("late_ratio", "拖拍比例",
                     summary["late_ratio"], "ratio"),
            UiScalar("on_time_ratio", "死区内比例",
                     summary["on_time_ratio"], "ratio"),
            UiScalar("n_notes_used", "参与统计的音数",
                     float(summary["n_notes_used"]), "count"),
            UiScalar("n_unpaired", "未能配对的音数",
                     float(summary["n_unpaired"]), "count"),
        )
        # ★ 三比例和恒为 1.0（§6 INV-202-5），n>0 时断言
        if summary["n_notes_used"] > 0:
            total = (summary["early_ratio"] + summary["late_ratio"]
                     + summary["on_time_ratio"])
            if abs(total - 1.0) > 1e-9:
                raise ValueError(f"三比例之和 {total!r} 偏离 1.0（容差 1e-9）")

        return AlgorithmResultEnvelope(
            algorithm_id=ALGORITHM_ID,
            algorithm_version=ALGORITHM_VERSION,
            status="OK",
            required_ports=TIMING_REQUIRED_PORTS,
            consumed_ports=TIMING_REQUIRED_PORTS,
            payload=payload,
            elapsed_sec=perf_counter() - t0,
        )
    except Exception as exc:  # ★ 不抛异常到调用方（§6 INV-202-7）
        return AlgorithmResultEnvelope(
            algorithm_id=ALGORITHM_ID,
            algorithm_version=ALGORITHM_VERSION,
            status="FAILED",
            required_ports=TIMING_REQUIRED_PORTS,
            consumed_ports=(),
            # ★ 失败信封 payload 必须为 () —— 不伪造全零指标（§4.5）
            payload=(),
            error_code="ALGORITHM_FAILED",
            error_detail=f"{type(exc).__name__}: {exc}",
            elapsed_sec=perf_counter() - t0,
        )
