'''
FILE-ID:      FILE-200
COMPONENT:    COMP-C3 Algorithm
SPEC:         contract.AlgorithmResultEnvelope · profile.PORTS · COMPONENTS.md@v2 §3

ROLE:
    算法注册表 —— 声明系统里存在哪些算法，以及每个算法需要哪些端口。

INTENT:
    **新增算法只改这个文件。** 这是「换算法不改核心」这一架构承诺的落点。

    C1 从本文件读取注册表并逐个调用；C2 完全不知道本文件存在。
    因此「加一个算法」的成本是：写一个模块 + 在这里加一行 ——
    不需要碰 Core 的任何一行代码。

MUST:
    - ALGORITHMS 是**唯一**的算法清单来源
    - 每个 AlgorithmSpec.required_ports 必须是 profile.PORTS 的子集
    - entry 必须可调用，且返回 contract.AlgorithmResultEnvelope

MUST NOT:
    - import core / host / cockpit（任何形式）
    - 在此处实现算法逻辑（只声明，不实现）
    - 声明 profile 中不存在的端口（会在启动时被判定为不可用）
    - 让注册表成为可变的（必须是冻结的元组）

INPUT:
    （无）

OUTPUT:
    ALGORITHMS —— tuple[AlgorithmSpec, ...]

BUILD-INSTRUCTION:
    .spec/build/FILE-200-v1.md
'''

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from ..contract import AlgorithmDataContract, AlgorithmResultEnvelope
from . import dynamics, pitch, timing


@dataclass(frozen=True)
class AlgorithmSpec:
    """一个算法的注册条目。"""

    algorithm_id: str
    """稳定标识，如 'pitch'。出现在结果信封里。"""

    version: str
    """算法版本。修改算法行为时应递增 —— 否则结果无法追溯。"""

    required_ports: Sequence[str]
    """本算法需要的端口。**必须**是 profile.PORTS 的子集。

    用途是**单向**的：C1 用它判断「数据面里有没有这些端口」，
    没有就跳过本算法（INCOMPATIBLE）。
    **绝不**因为某个算法缺端口就去让 C2 生成数据 —— 那是核心禁令。

    ★ 这是 `required_ports` 的**唯一权威**（G13 修正）。

    `AlgorithmResultEnvelope.required_ports` 是同一份事实的**运行时副本** ——
    它由 C1 从本字段填入信封，用于事后追溯"这次判定依据的是哪些端口"。

    ★ 第三轮修正（§20 盲审第二轮发现）：第一版我写"二者必须相等，
    且该相等关系由 `assert_registry_integrity()` 检查" —— **这句话是假的**。

    为什么假：`assert_registry_integrity()` 是 **import 期静态检查**，
    只读得到本元组的字段；而信封是**运行期**产物，静态检查够不着它。
    声称一个结构上不可能执行的检查，比不写更糟 ——
    它让读者以为这条一致性已被机械保证，从而不再人工核对。

    真实情况分两种，必须分开说清：

        a) C1 **填入**信封时：`required_ports` 必须**逐字复制**本字段
           （不得自行拼接、去重、重排序）。这是 C1 的实现约定，
           由 Build Instruction 与 Code Review 保证，**非**机械检查。
        b) 算法**自身**若也需要一份端口清单（例如 run() 内做断言）：
           它**不能** import 本模块（循环 import：
           本模块 `from . import dynamics, pitch, timing`）。
           故它只能写一份**镜像常量**，而镜像**没有任何机制保证同步**。

    对 (b) 的正确态度：**不要写镜像**。算法应在运行期从
    `surface.manifest()` 读取实际端口，只校验"我需要的在不在"，
    而不是硬编码一份可能与注册表分叉的名单。
    """

    entry: Callable[[AlgorithmDataContract], AlgorithmResultEnvelope]
    """算法入口。★ 签名已冻结（G3 修正）。

    第一版写的是 "Callable[..., AlgorithmResultEnvelope]" 并注明
    "实际签名由 Build Instruction 冻结" —— 但 Build Instruction 在
    `.spec/build/` 里，**盲审者与实现者都读不到**（那是冻结后才写的）。

    于是 C1 无法知道该传什么、怎么接 INCOMPATIBLE 判定。
    现已冻结为唯一形式：

        entry(surface: AlgorithmDataContract) -> AlgorithmResultEnvelope

    三个算法的 `run()` 本来就是这个签名 —— 契约只是追认了既成事实，
    并把它从"约定"提升为"可机械检查的约束"。

    实现约定：
        - **同步、纯函数**：不修改 surface，不持有跨会话状态
        - **不抛异常**：失败也返回信封（status='FAILED' + error_code）
          异常穿透会破坏 C1 的故障隔离（见 contract.AlgorithmError）
        - 返回的信封中 `algorithm_id` / `version` 必须与注册条目一致
    """

    label: str
    """给人看的中文短名。"""


def assert_registry_integrity() -> None:
    """注册表自检：**在 import 时执行**，让配置错误立刻暴露。

    检查：
      1. algorithm_id 无重复
      2. required_ports 全部存在于 profile.PORTS
         （否则该算法永远 INCOMPATIBLE —— 声明了一个没人会生成的数据）
      3. required_ports 非空（没有算法不需要数据面）
      4. algorithm_id 与各模块的 ALGORITHM_ID 一致，version 同理

    ★ 刻意**不检查**「每个端口都被某个算法消费」。

    为什么：端口存在有三种正当理由，只有第一种与算法直接相关：
        a) 被算法直接消费    —— pitch.* / rms.* / notes.reference
        b) 被 Core 内部消费  —— chroma.lowres.*，align 用它建立对齐；
                                同时保留在数据面里供审查者复现对齐过程
        c) 数据面保证（本仓自定，非宪章条文）—— pcm.warped.practice，算法可自行取用来做
                                特有预处理，即使当前没有算法用它

    若强行要求"端口必须被消费"，上面 b、c 两类会被误判为死端口而删除，
    结果是**对齐无法复现、算法失去自行预处理的能力** ——
    用一条看似严谨的规则毁掉两个设计保证。
    （实测：3 个端口属于 b/c 类。）

     ★ `MOLD BREAK` 后新增检查（§20 盲审情况 A）：

       5. `entry` 必须可调用，且签名与冻结形式一致
          （第一版只说"由 Build Instruction 冻结"，而那对实现者不可见）
       6. 每个算法必须声明**成对**的端口 ——
          `X.reference` 与 `X.practice` 要么都有、要么都没有。
          为什么：第一版 notes.* 只有 reference 侧，
          导致 dynamics 写出无法满足的 MUST。对称性是可机械检查的。
       7. 每个算法的 payload 键必须恰为 PAYLOAD_SCHEMAS 中列出的那些
          （"恰为"而非"包含" —— 多出的键会让 C1 校验器与 UI 投影
          对不上，且不会报错）

    失败即抛，不返回布尔值。
    """
    raise NotImplementedError("SHELL: FILE-200 待注入实现")


ALGORITHMS: tuple[AlgorithmSpec, ...] = (
    AlgorithmSpec(
        algorithm_id=pitch.ALGORITHM_ID,
        version=pitch.ALGORITHM_VERSION,
        required_ports=(
            "pitch.reference",
            "pitch.practice",
            "notes.reference",
            "notes.practice",
        ),
        entry=pitch.run,
        label="音准",
    ),
    AlgorithmSpec(
        algorithm_id=timing.ALGORITHM_ID,
        version=timing.ALGORITHM_VERSION,
        required_ports=(
            "pcm.mapped.reference",
            "pcm.mapped.practice",
            "notes.reference",
            "notes.practice",
        ),
        entry=timing.run,
        label="节奏",
    ),
    AlgorithmSpec(
        algorithm_id=dynamics.ALGORITHM_ID,
        version=dynamics.ALGORITHM_VERSION,
        required_ports=(
            "rms.reference",
            "rms.practice",
            "notes.reference",
            "notes.practice",
        ),
        entry=dynamics.run,
        label="力度",
    ),
)
"""系统里现有的三个算法。

`algorithm_id` / `version` 从各模块**导入**而非重抄 ——
两处写同一份事实迟早会不一致（这与 FIELD_LAYOUTS 是同一个教训）。

★★ MOLD BREAK 修正（§20 盲审情况 A）★★

第一版三个算法的 `required_ports` 是：
    pitch    → pitch.reference / pitch.practice
    timing   → pcm.mapped.* / notes.reference / warp_path
    dynamics → rms.reference / rms.practice

**但三者都声称"输出可定位到第几个音的结果"**，而只有 timing 声明了逐音索引。
pitch 和 dynamics 凭什么知道"第几个音"？第一版答不出来。
同时 `notes.*` 只有 reference 侧，练习侧完全没有逐音索引 ——
`dynamics` 因此写出了一条**无法满足的 MUST**（要求 WARPED 轴的 rms）。

两个独立盲审模型各自复现了这个冲突，说明它不是笔误，是**端口表的对称性破裂**。

修正后三个算法**都**声明 `notes.reference` + `notes.practice`：
    - pitch    用逐音索引把逐帧偏差聚合成"第 n 个音偏了多少音分"
    - timing   用 onset_sec 作两侧起音时刻的真值
    - dynamics 用逐音区间取能量，从而**按音配对**而非按时间轴配对

★ 第三轮修正（§20 盲审第二轮发现）：**从 timing 移除 `warp_path`。**

理由：timing 的整个要点是"不许做任何时间归一化"
（用归一化轴会把抢拍拖拍抹成 0），而 `warp_path` 按定义就是
DTW 对应关系 —— 拿它把练习时刻映射到参考钟**就是**归一化。
于是"声明需要它"与"不许用归一化映射"不可兼得，
唯一出路是"读而不用"，那又与「每个端口都必须能回答为什么需要它」相悖。

**实测确认：全项目没有任何算法消费 `warp_path`**（只有 core 生成它）。
它不是死端口 —— 它是**证据端口**：
保留在数据面里让审查者能重跑对齐、验证其余端口不是凭空来的
（见 profile 的 rationale 与 core/features.py 的说明）。
这与 `chroma.lowres.*` 属于同一类（"保留供复现，不作为计算输入"），
见下方 assert_registry_integrity 对"端口不被消费"的刻意豁免。"""


# ── 关于"节奏与力度用相反的轴"的沿革 ──
#
# 第一版：timing 用 REFERENCE、dynamics 用 WARPED，写作"刻意相反"。
# 第二轮：dynamics 的 WARPED 约束被证明**无法满足**（数据面里没有
#         WARPED 轴的 rms 端口），改为"按音配对"，删除其 AXIS 常量。
# 第三轮：timing 的 `timing.AXIS = REFERENCE` **保持不变** ——
#         它的理由是硬的（用 WARPED 会让抢拍拖拍恒为 0 且不报错），
#         与 dynamics 的取舍无关。两者不再构成"对称设计"，
#         因为 dynamics 的问题本来就不是"选哪条轴"。


PAYLOAD_SCHEMAS: Mapping[str, tuple[str, ...]] = {
    "pitch": (
        "per_note_cents",
        "median_abs_cents",
        "off_pitch_ratio",
        "n_notes_used",
        "sample_rate",
    ),
    "timing": (
        "per_note_onset_ms",
        "median_onset_ms",
        "spread_ms",
        "early_ratio",
        "late_ratio",
        "on_time_ratio",
        "n_notes_used",
        "n_unpaired",
    ),
    "dynamics": (
        "per_note_delta_db",
        "median_db",
        "spread_db",
        "n_notes_used",
        "n_unpaired",
    ),
}
"""★ 盲审发现的关键缺口（G4）：算法 payload 的字段名原先**没有任何冻结处**。

为什么必须有这张表：`AlgorithmResultEnvelope.payload` 是 `dict`，
三个算法模块只给了散文式描述（"中位偏差、离散度、抢拍/拖拍比例"），
而 `host/app.py` 要求"校验 schema 合法性"并据此产出 `ALGORITHM_RESULT_INVALID`。
**产出方与校验方之间没有共同事实来源** —— 校验器无从知道该查哪些键。

这**正是 `FIELD_LAYOUTS` 当初要消灭的那类缺陷**
（"不会报错、只会静默算错"），只是我第一版没把这条教训推广到 payload 层。

规则：
    - 键名表即**唯一权威**，算法实现与 C1 校验器都必须引用它
    - 每个算法 payload 的键必须**恰好**是表中列出的这些（不多不少）
    - `per_note_*` 是逐音序列，长度必须等于该次统计的 `n_notes_used`
    - `UiScalar.key` / `UiSeries.key` 的取值必须取自本表的键名，
      从而 `metrics.json` 与界面不会出现两套名字
"""
