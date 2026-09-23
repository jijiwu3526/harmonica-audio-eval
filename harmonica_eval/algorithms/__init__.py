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
from typing import Callable, Sequence

from ..contract import AlgorithmResultEnvelope
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
    """

    entry: Callable[..., AlgorithmResultEnvelope]
    """算法入口。实际签名由 Build Instruction 冻结。"""

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
        c) 宪章 §11 逃生口   —— pcm.warped.practice，算法可自行取用来做
                                特有预处理，即使当前没有算法用它

    若强行要求"端口必须被消费"，上面 b、c 两类会被误判为死端口而删除，
    结果是**对齐无法复现、算法失去自行预处理的能力** ——
    用一条看似严谨的规则毁掉两个设计保证。
    （实测：3 个端口属于 b/c 类。）

    失败即抛，不返回布尔值。
    """
    raise NotImplementedError("SHELL: FILE-200 待注入实现")


ALGORITHMS: tuple[AlgorithmSpec, ...] = (
    AlgorithmSpec(
        algorithm_id=pitch.ALGORITHM_ID,
        version=pitch.ALGORITHM_VERSION,
        required_ports=("pitch.reference", "pitch.practice"),
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
            "warp_path",
        ),
        entry=timing.run,
        label="节奏",
    ),
    AlgorithmSpec(
        algorithm_id=dynamics.ALGORITHM_ID,
        version=dynamics.ALGORITHM_VERSION,
        required_ports=("rms.reference", "rms.practice"),
        entry=dynamics.run,
        label="力度",
    ),
)
"""系统里现有的三个算法。

`algorithm_id` / `version` 从各模块**导入**而非重抄 ——
两处写同一份事实迟早会不一致（这与 FIELD_LAYOUTS 是同一个教训）。

注意 `timing` 需要 `pcm.mapped.*`（**保留源时间**的轴），
而 `pitch` / `dynamics` 只用逐帧特征。
这个差异不是偶然 —— 节奏必须在源时间轴上算，否则抢拍拖拍会被抹掉。"""
