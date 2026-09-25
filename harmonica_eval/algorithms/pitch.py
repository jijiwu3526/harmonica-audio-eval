'''
FILE-ID:      FILE-201
COMPONENT:    COMP-C3 Algorithm
SPEC:         SPEC.md@v2.1 §7 · contract.FIELD_LAYOUTS['pitch'] · profile.PORTS

ROLE:
    音准对比：比较参考与练习的**绝对音高**，输出可定位到具体音的偏差。

INTENT:
    音准是口琴学习者最直接的反馈维度，也是本项目唯一有明确量化阈值的维度
    （规格 §7：稳定音 ≤50 音分）。

    ★ 本算法**必须**用绝对音高，禁止 chroma 化。
    chroma 是八度不变的 —— 用它做音准会把「低了一个八度」判成完全正确。
    实测佐证：同一段音频在 22.05 kHz 下 f0 被判低八度（恰好 −1200 音分），
    若用 chroma 这个错误将完全不可见。

MUST:
    - 导出 ALGORITHM_ID / ALGORITHM_VERSION / LABEL
      （★ LABEL 是中文显示名，负责人 2026-09-24 裁定；
        bootstrap 用它填 PluginSpec.label，**不得回退为 algorithm_id**）
    - 消费 pitch.reference / pitch.practice / notes.reference / notes.practice
    - 产出逐音误差（音分，可定位到第几个音）
    - 只在 voiced 且时长 ≥ MIN_STABLE_NOTE_SEC 的音上统计
    - 报告采样率（它是结果的成因，必须随结果一起记录）
    - 失败也返回 AlgorithmResultEnvelope（不抛异常穿透到 C1）

MUST NOT:
    - chroma 化（见上，会把八度错误隐藏掉）
    - **按帧号直接对齐两侧**（见下方 compare_pitch_curves 的长注记：
      REFERENCE 轴不保证帧号对齐）
    - 用 mapped 轴（音准关心"吹了什么"，不关心"何时吹" —— 那是 timing 的事）
    - 在未发声帧上计算误差（那些帧没有音高，不是"音高错"）
    - 输出教学结论（"你这里偏低了"）—— 只到数值层（SPEC §1）

INPUT:
    surface: AlgorithmDataContract（只读）

OUTPUT:
    AlgorithmResultEnvelope，payload 含：
        逐音偏差（音分）、走音比例、中位绝对误差、采样率

BUILD-INSTRUCTION:
    .spec/build/FILE-201-v1.md
'''

from __future__ import annotations

import math
import statistics

from ..contract import (
    FIELD_LAYOUTS,
    AlgorithmDataContract,
    AlgorithmResultEnvelope,
    TimelineBasis,
    UiScalar,
    UiSeries,
    hop_of,
)

ALGORITHM_ID: str = "pitch"
ALGORITHM_VERSION: str = "1.0.0"
LABEL: str = "音准"
"""中文显示名。★ 术语取自 `SPEC.md` §5「音高 / 音准（cents）」——
本算法产出的是音分误差，故取「音准」而非「音高」。"""

MAX_CENTS_DEVIATION: float = 50.0
"""稳定音的容许偏差（音分）。来自 SPEC.md §7，不是工程估计值。

超过它即计入「走音比例」。注意这是**判据**，不是"完美线"——
它回答"这个音算不算准"，不回答"有多好"。
"""

MIN_STABLE_NOTE_SEC: float = 0.150
"""参与统计的最短音长（秒）。与 core.features.MIN_STABLE_NOTE_SEC 同义。

短音的音高估计不可靠，纳入统计会引入噪声而非信号。
"""

PITCH_HOP_LENGTH: int = hop_of("pitch.reference")
"""`pitch.*` 端口的帧跳（采样点）—— **从契约层真相源读取**。

★ **2026-09-24 更正**：本文件此前自带 `PITCH_HOP_LENGTH = 2048`，
★ 那与 `profile.PORT_INDEX['pitch.reference'].hop_length` 是**同一事实两处定义**，
★ 迟早漂移。
★ **负责人 2026-09-24 裁定「放进 contract」** —— 现已改为从 `..contract`
★ 导入 `hop_of`，并以 `PITCH_HOP_LENGTH = hop_of("pitch.reference")` 取得。

★ **为什么不 import profile 直接取**：FILE-201 §8 判据 G 的 `ALLOWED` 不含
  `profile`（只允许 `__future__` / `math` / `statistics` / `time` / `typing` /
  `numpy` / `contract`）；★ 而 `contract` 已在 `ALLOWED` 内，
  ★ **判据 G 本就允许读 `contract` —— 不需要放宽任何判据**。

★ **`ALLOWED` 含 `contract` 这一事实是本改法成立的前提**，
★ 已由 `FILE-201-v1.md:575` 核实。
★ **对 timing / dynamics 的对照**：
```
timing.py     不带 hop 常量 → 从 surface.manifest() 取
dynamics.py   不带 hop 常量 → _descriptor("rms.reference").hop_length
本文件        ★ 同样不带 —— 从 contract.hop_of() 取
★ 三者现在都不复制 hop 值
```

★ **因此正确修法不是放宽本模块的 import 面，而是二选一**：
```
① 把 hop 放进 `contract` —— ★ 判据 G 【已经允许】import contract
   ★ 且 contract 本就是冻结的共享层（runtime 也在读它）
   ★ ★ 这样三处记载变一处，符合负责人「降低信息熵」的要求
② 放宽判据 G 的 ALLOWED 加入 profile
★ ★ 两条都要改 FILE-201，本任务无权改 → 列为「需主代理派修」
```

★ **在裁定落地前的现状（风险敞口）**：
```
权威源   profile.PORT_INDEX['pitch.reference'].hop_length = 2048
本文件   PITCH_HOP_LENGTH = 2048     ← 与权威源同值，但【是复制】
★ 两处若漂移，★ 没有任何判据会报红
"""

PITCH_REQUIRED_PORTS: tuple[str, ...] = (
    'pitch.reference', 'pitch.practice', 'notes.reference', 'notes.practice',
)
"""本算法声明的四个必需端口。

★ 与 `bootstrap.ALGORITHM_INPUTS['pitch']` 逐字相同。
★ **为什么不在这里 import bootstrap 取它**：FILE-201 §8 判据 G 的 `ALLOWED`
  不含 `bootstrap`（判据 G 自己 import 它只是为了读数，不在受检文件内）。
★ 按判据 G 的 import 面冻结，本模块只能自带这份清单。
★ **判据 A 会机械核对两者一致** —— 若 bootstrap 侧改动而此处未同步，判据 A 变红。
"""


def hz_to_cents(f0_hz: float, ref_hz: float) -> float:
    """把频率比换算成音分。1200 音分 = 一个八度。

    公式：1200 * log2(f0 / ref)
    未发声（任一为 0）时**不得**调用 —— 调用方须先用 voiced 过滤。
    """
    # ★ 实现（FILE-201 §4.1，2026-09-24 授权注入）。
    # 纯数学校算，故用标准库 math.log2 —— 不引入 numpy，
    # 保持本模块「零第三方依赖」（FILE-201 §8 判据 G 会检查 import 面）。
    return 1200.0 * math.log2(f0_hz / ref_hz)


def compare_pitch_curves(
    ref_pitch: object,
    prac_pitch: object,
    ref_notes: object,
    prac_notes: object,
    sample_rate: int,
) -> object:
    """逐音比较两侧音高，返回逐音的音分偏差。

    ★★ 由下往上核对代码时修正（原表述是错的）★★

    原文写：「两条曲线同轴（都是 REFERENCE），故可直接逐帧相减」。
    **这个推理不成立。** `TimelineBasis.REFERENCE` 的含义是
    「保留源时间、未被时间归一化」，它**不**蕴含「两侧帧号一一对应」。

    参考与练习是**两段独立录音**，时长各自落在
    `[profile.AUDIO.min_duration_sec, max_duration_sec]` 区间内。
    `pitch.*` 的帧数 = 时长 / `MATERIALIZE.pitch_hop_length`，
    故两侧 n_frames **默认不相等**，逐帧相减无定义。

    为什么这个缺陷一直没暴露：本数据集 01 的全部 wav 都是同一渲染器
    批量产出、长度恰好全是 72.802 s（1568 帧），于是"恰好等长"掩盖了它。
    换一首演奏时长不同的练习曲（这正是真实使用场景）立刻崩。

    正确做法：用两侧各自的 `notes.*` 的 `onset_sec` 建立对应，
    **按音配对**后再比较。这也是 `ALGORITHMS` 声明 pitch 需要
    `notes.reference` + `notes.practice` 的真正理由 ——
    原先的论证只讲到"为了能标注第几个音"（可定位），
    没讲到"不等长根本无法比较"（可比较）。论证不完整，
    所以本函数的签名一直漏掉了这两个参数。

    配对规则：
        - 按音序配对（第 n 个音对第 n 个音），与 dynamics.align_by_note 同口径
        - 配不上的音（一侧多出 / 缺少）单独记账，不参与偏差统计
        - 每对音内部**只在两侧都 voiced 的帧上**求偏差
    一侧有声一侧无声是**漏音/多音**（属于另一类问题），
    不是"音高偏差"，混进来会污染音准统计。

    voiced 处理：未发声帧的 f0_hz 为 0，其 cents 偏差**无定义**
    （`hz_to_cents` 明令不得在任一为 0 时调用）。实现须先按 voiced 过滤。

    实现须引用 contract.FIELD_LAYOUTS['pitch'] 解释 (f0_hz, voiced, confidence)、
    引用 contract.FIELD_LAYOUTS['notes'] 解释 (onset_sec, f0_hz, rms)，
    **不得**另行硬编码字段位置。

    ★ 实现（FILE-201 §4.2，2026-09-24 授权注入）：
      按 `onset_sec` 把每个音映射到帧区间（hop = sample_rate / hop_length），
      区间内**只在两侧都 voiced 的帧**上求 1200*log2 比值，再取该音的中位数
      作为这一音的偏差。配不上的音只记账，不进偏差统计。
    """
    pitch_fields = FIELD_LAYOUTS['pitch']
    notes_fields = FIELD_LAYOUTS['notes']
    f0_i = pitch_fields.index('f0_hz')
    voiced_i = pitch_fields.index('voiced')
    onset_i = notes_fields.index('onset_sec')

    def spans(notes: object, n_frames: int) -> list[tuple[int, int]]:
        """逐音的帧区间列表；用后一音的 onset 作为本音终点。"""
        out: list[tuple[int, int]] = []
        count = len(notes)
        for i in range(count):
            start = int(float(notes[i][onset_i]) * sample_rate / PITCH_HOP_LENGTH)
            if i + 1 < count:
                end = int(float(notes[i + 1][onset_i]) * sample_rate / PITCH_HOP_LENGTH)
            else:
                end = n_frames
            out.append((max(0, start), max(start + 1, min(end, n_frames))))
        return out

    ref_spans = spans(ref_notes, len(ref_pitch))
    prac_spans = spans(prac_notes, len(prac_pitch))

    def note_median_cents(curve: object, span: tuple[int, int], ref_hz: float) -> float | None:
        """一个音内的中位音分偏差；该音没有可用帧时返回 None。"""
        start, end = span
        vals: list[float] = []
        for row in curve[start:end]:
            if not bool(row[voiced_i]):
                continue
            f0 = float(row[f0_i])
            if f0 <= 0.0 or ref_hz <= 0.0:
                continue
            vals.append(1200.0 * math.log2(f0 / ref_hz))
        if not vals:
            return None
        vals.sort()
        mid = len(vals) // 2
        return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0

    per_note: list[float] = []
    onsets: list[float] = []
    n_paired = 0
    n_unpaired = abs(len(ref_spans) - len(prac_spans))
    # ★ FILE-201 §4.2 第 4 项：帧数不足 150 ms 的短音一律丢弃 ——
    #   短音的音高估计不可靠，纳入统计会引入噪声而非信号（SPEC.md §7.3）。
    min_frames = MIN_STABLE_NOTE_SEC * sample_rate / PITCH_HOP_LENGTH
    for idx in range(min(len(ref_spans), len(prac_spans))):
        ref_hz = float(ref_notes[idx][notes_fields.index('f0_hz')])
        ref_len = ref_spans[idx][1] - ref_spans[idx][0]
        prac_len = prac_spans[idx][1] - prac_spans[idx][0]
        if ref_len < min_frames or prac_len < min_frames:
            n_unpaired += 1
            continue
        c_ref = note_median_cents(ref_pitch, ref_spans[idx], ref_hz)
        c_prac = note_median_cents(prac_pitch, prac_spans[idx], ref_hz)
        if c_ref is None or c_prac is None:
            n_unpaired += 1
            continue
        n_paired += 1
        per_note.append(c_prac - c_ref)
        onsets.append(float(ref_notes[idx][onset_i]))

    return {
        'per_note_cents': per_note,
        'onset_sec': onsets,
        'n_paired': n_paired,
        'n_unpaired': n_unpaired,
    }


def summarize_deviations(deviations_cents: object) -> object:
    """把**已按音聚合好的**逐音偏差序列汇总成可上报的指标。

    ★ 入参 `deviations_cents` 是 `compare_pitch_curves` 产出的结果 ——
    音与音的切分（note/onset 边界）由**那个**函数完成，本函数不再切音。
    ★ 措辞澄清：本函数不负责「哪个音对应哪个音」，只负责把已配对好的
    逐音偏差聚合成标量指标。


    ★ 键名的**唯一权威**是插件自己产出的 `UiScalar` / `UiSeries` 对象的
    `key` 字段；框架不再维护第二份键名清单。

    例如可产出如下指标（用于说明应产出什么，不是从某张表抄录）：
        per_note_cents      逐音音分偏差（带符号），长度 == n_notes_used
        median_abs_cents    中位绝对偏差
        off_pitch_ratio     超过 MAX_CENTS_DEVIATION 的音占比
        n_notes_used        参与统计的音数（**必须报告**）
        sample_rate         采样率（结果的成因，不是元数据）

    除逐音序列外，每个指标最终会成为一个 `UiScalar`
    （带 `key` / `label` / `value` / `unit`）；`per_note_cents` 的逐音序列
    则是一个 `UiSeries`（`t` 放 `onset_sec`、`values` 放偏差、
    `timeline_basis=REFERENCE`）。

    ⚠ `off_pitch_ratio` 的分母是 `n_notes_used`，故两者必须一起读：
    只报比例的话，「全曲 115 个音里 58 个走音」与
    「12 个音里 6 个走音」会得到同一个数字。

    ★ 已知缺口（由下往上核对发现，如实记录不掩盖）：
    timing 与 dynamics 的 payload 都含 `n_unpaired`（未能配对的音数），
    **pitch 没有**。而 pitch 的配对同样会失败（漏音/多音/音数不等），
    配不上的音同样被排除在统计之外 —— 排除数量却无处报告。
    后果：读者无法分辨「整首都测了」与「只测上了少数几个音」。

    根因（历史归因）是当时的 payload 键名冻结表由人工维护、三份各自演化，
    缺少对称性约束；修它当时需要改冻结表（接口变更），故按 §37 Gate Challenge
    上报，见本文件 BUILD-INSTRUCTION 的 §10。现在 payload 自描述，该表已删除，
    「人工维护会分叉」的问题从结构上消失。

    ★ 实现（FILE-201 §4.3，2026-09-24 授权注入）：
      中位数用 `statistics.median`（标准库，判据 G 允许），不自己实现排序取中。
      走音判定用 `> MAX_CENTS_DEVIATION`（**严格大于**），故恰好等于阈值判为准。
    """
    values = [float(v) for v in deviations_cents]
    n_used = len(values)
    if n_used == 0:
        return {
            'per_note_cents': [],
            'median_abs_cents': 0.0,
            'off_pitch_ratio': 0.0,
            'n_notes_used': 0,
        }
    abs_values = sorted(abs(v) for v in values)
    off = sum(1 for v in abs_values if v > MAX_CENTS_DEVIATION)
    return {
        'per_note_cents': values,
        'median_abs_cents': float(statistics.median(abs_values)),
        'off_pitch_ratio': off / n_used,
        'n_notes_used': n_used,
    }


def run(surface: AlgorithmDataContract) -> AlgorithmResultEnvelope:
    """算法入口。

    流程：读端口 → 比较 → 汇总 → 装信封。

    必须记录 sample_rate —— 它是结果的成因，不是元数据。
    实测：22.05 kHz 下 D5 被判成 D4（−1200 音分）。
    拿到一份没有采样率的音准报告，无法判断它是否可信。

    失败：返回 status='FAILED' 的信封，error_code 取 AlgorithmError 对应码。
    **不抛异常** —— 算法失败不应穿透到 C1，否则故障无法隔离。

    ★ 实现（FILE-201 §4.4，2026-09-24 授权注入）：
      整个流程包在 try 里；任何异常都收进 FAILED 信封（判据 F 验的就是这条）。
      payload 的 unit 全部取自 UNITS_VOCABULARY —— runtime 第 3 刀已实跑证明
      `unit='ms'` 会被 validate_result 明确拒绝，故此处绝不能自造单位。
      ★ 本函数按音配对取 f0_hz，故不消费 chroma、不消费任何 WARPED 端口
      （判据 G 会用 AST 检查这一点）。
    """
    try:
        manifest = surface.manifest()
        ref_pitch = surface.read('pitch.reference').data
        prac_pitch = surface.read('pitch.practice').data
        ref_notes = surface.read('notes.reference').data
        prac_notes = surface.read('notes.practice').data

        compared = compare_pitch_curves(
            ref_pitch, prac_pitch, ref_notes, prac_notes,
            manifest.audio_format.sample_rate,
        )
        summary = summarize_deviations(compared['per_note_cents'])

        payload = (
            UiSeries(
                key='per_note_cents',
                label='逐音音分偏差',
                t=compared['onset_sec'],
                values=summary['per_note_cents'],
                unit='cents',
                timeline_basis=TimelineBasis.REFERENCE,
                source_port='pitch.reference',
            ),
            UiScalar('median_abs_cents', '中位绝对偏差',
                     summary['median_abs_cents'], 'cents'),
            UiScalar('off_pitch_ratio', '走音比例',
                     summary['off_pitch_ratio'], 'ratio'),
            UiScalar('n_notes_used', '参与统计的音数',
                     float(summary['n_notes_used']), 'count'),
            UiScalar('n_unpaired', '未能配对的音数',
                     float(compared['n_unpaired']), 'count'),
            UiScalar('sample_rate', '采样率',
                     float(manifest.audio_format.sample_rate), 'hz'),
        )
        return AlgorithmResultEnvelope(
            algorithm_id=ALGORITHM_ID,
            algorithm_version=ALGORITHM_VERSION,
            status='OK',
            required_ports=PITCH_REQUIRED_PORTS,
            consumed_ports=PITCH_REQUIRED_PORTS,
            payload=payload,
            error_code=None,
            error_detail=None,
            elapsed_sec=None,
            coverage=None,
            warnings=(),
        )
    except Exception as exc:  # noqa: BLE001 — ★ 判据 F：异常必须收进信封，不得穿透
        return AlgorithmResultEnvelope(
            algorithm_id=ALGORITHM_ID,
            algorithm_version=ALGORITHM_VERSION,
            status='FAILED',
            required_ports=PITCH_REQUIRED_PORTS,
            consumed_ports=(),
            payload=(),
            error_code='ALGORITHM_FAILED',
            error_detail=f'{type(exc).__name__}: {exc}',
            elapsed_sec=None,
            coverage=None,
            warnings=(),
        )
