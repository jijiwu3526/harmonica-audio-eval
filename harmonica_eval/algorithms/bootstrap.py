'''
FILE-ID:      FILE-206
COMPONENT:    COMP-C3 Algorithm
SPEC:         SPEC.md@v2.1 · contract.PluginSpec · algorithms.registry.Registry
              · SHELL-STANDARD v1

ROLE:
    **唯一物理装配根**：全系统唯一一处 import 具体算法实现模块的地方。

INTENT:
    关闭 GC-204-08（原为 OPEN · 阻塞插件迁移）的不变量冲突。

    ★ 冲突原貌（负责人裁定前的实况）：
      不变量甲：「C1 是全系统唯一知道『有哪些实现』的地方」
      不变量乙：「C1 跨界 import 的是契约层，不是某个具体算法实现模块」
      两条同时成立时，`registry.register(pitch/timing/dynamics)` 在物理上
      无法书写 —— 要构造 PluginSpec 就必须 import 具体模块，而 C1 被禁止。
      换句话说：**没有第三个地方承担装配，装配链就不存在。**

    ★ 本文件把「知道所有实现」这一职责**从 C1 移到一个专属位置**：
      bootstrap 独占具体算法的 import，C1（Host）只接收已构造好的 Registry。
      这样不变量乙对 C1 继续成立（它确实不 import 具体算法），
      而「谁负责装配」变成一个可审查的、单点的物理事实。

MUST:
    - 是全系统唯一 import dynamics / pitch / timing 具体模块的位置
    - 只做「import → 构造 PluginSpec → register」，不做任何算法逻辑
    - 注册顺序即 list() 顺序，是报告顺序的事实来源，不得在别处重排
    - 只依赖 ..contract 与同包 registry / runtime

MUST NOT:
    - 被 core / host / cockpit import（它们只接收已构造的 Registry）
    - 扫描目录、读取 entry-points 或动态发现插件（与 Registry 同禁令）
    - 在此处运行算法、读端口、做 DSP 或解释 payload
    - 提供 unregister / enable / disable（运行期改插件集合属 Host 职责）
    - 在本文件里重新定义 PluginSpec 或复制注册顺序的第二份来源

INPUT:
    无入参。注册清单与**端口需求声明**都在本文件内（v0.1 固定三个算法）——
    `REGISTRATION_ORDER` 是顺序来源，`ALGORITHM_INPUTS` 是端口需求来源。
    ★ 两者均为**声明**（数据），不构造 PluginSpec、不调 register；
      那些是函数体职责，留待注入授权。

OUTPUT:
    Registry —— 已按本文件声明顺序装好三个 PluginSpec 的注册表。

BUILD-INSTRUCTION: .spec/build/FILE-206-v1.md
★★ 铭牌字段必须单行：解析器按行尾取该字段，续行会被并入同名字段。
★ 本文件是负责人 BLOCK-1 裁定（方案甲）后**新铸的组件**（该 BI 含 §8 可执行验收脚本）。
★ 已关闭的挑战 GC-204-08（台账 `.spec/GATE-CHALLENGES-C3.md` 状态 CLOSED）。
★ 裁定方案甲：bootstrap 是全系统唯一 import 具体算法模块的位置，
Host 只接收本文件产出的已装配 Registry，不再 import 具体算法。
'''

from __future__ import annotations

from ..contract import ContractViolation, ErrorCode, InputRequirement, PluginSpec
from ..profile import AUDIO, PORT_INDEX, SAMPLE_RATE_FREE_PREFIXES, port_prefix
from . import dynamics, pitch, timing
from .registry import Registry


__all__ = [
    "ALGORITHM_INPUTS",
    "REGISTRATION_ORDER",
    "build_default_registry",
    "build_plugin_specs",
]


# ═════════════════════════════════════════════════════════════════════
# 冻结的装配顺序
# ═════════════════════════════════════════════════════════════════════

REGISTRATION_ORDER: tuple[str, ...] = ("pitch", "timing", "dynamics")
"""**插件的规范运行顺序**，也是 `Registry.list()` 的结果顺序。

★ 选这个顺序的理由（可审查）：
  pitch 先跑 —— 它按音配对，是 timing 的前置；timing 再跑 —— 它用
  notes.reference 的起音时刻，依赖 pitch 产出的音边界；dynamics 最后 ——
  它读 mapped 轴的幅度统计，不依赖前两者的结果。

★ 这是**唯一**的顺序来源。Registry 只保序不排序；C1 的
  `run_algorithms` 按 `Registry.list()` 遍历，因此改这里就改报告顺序，
  改别处不生效。
"""


# ═════════════════════════════════════════════════════════════════════
# 冻结的端口需求声明（方案甲：装配根集中声明）
# ═════════════════════════════════════════════════════════════════════

# ★ 负责人 2026-09-24 裁定：`PluginSpec` 由本文件**集中声明**（方案甲）。
#
# ★ 裁定理由（三条，勿删）：
#   1. 与刚关闭的 GC-204-08 完全一致 —— 本文件的职责原文（`host/app.py:114`）
#      就是「唯一知道有哪些实现的地方」。端口需求属于「实现需要什么」，
#      天然是装配根的知识。
#   2. 选乙（各算法自导出 `SPEC`）会让装配知识重新分散，
#      等于把刚关闭的装配权冲突换个位置 reintroduce。
#   3. 「新增算法不改 bootstrap」这个优势已由 `FILE-206-v1.md` §8.3
#      机器守住（全仓恰好一处 import 具体算法）；新增算法确实要改本文件，
#      但那本来就是装配根该做的事。
#
# ★ **本节只声明「哪个算法需要哪些端口」，不构造 PluginSpec、不调 register。**
#   那些是函数体的职责，留待注入授权后实现（见下方 SHELL 函数）。
#
# ★ **取值来源**：逐条摘自各算法模块 docstring 的 MUST 条款，
#   并在每条后标注出处行号 —— 这些 docstring 由 `verify_stubs_raise` 守护，
#   是冻结产物；本节不得凭记忆改写。
#
# ★ `pcm.warped.practice` **刻意不出现在 timing 的需求里**：
#   `timing.py:30` 的 MUST NOT 明文「使用 pcm.warped.practice 或任何
#   WARPED 轴数据（会抹掉本算法要测的东西）」。全文仅此一处提及，
#   是**禁止**而非消费。故它既不进 required 也不进 optional。
#
# ★ `InputRequirement` 的 `required_fields` / `timeline_basis` / `element_type`
#   **不在本节硬编码** —— 它们在 `profile.PORT_SPECS` 里有权威值。
#   硬编码会产生第二份真相源，端口演进时必然漂移。
#   实现时应从 `profile.PORT_INDEX[port_id]` 派生；本节只冻结**端口集合**。

PITCH_REQUIRED_PORTS: tuple[str, ...] = (
    "pitch.reference",      # pitch.py:19
    "pitch.practice",      # pitch.py:19
    "notes.reference",     # pitch.py:19
    "notes.practice",      # pitch.py:19
)
"""`pitch` 的必需端口 —— 摘自 `harmonica_eval/algorithms/pitch.py:19`：

> MUST: 消费 pitch.reference / pitch.practice / notes.reference / notes.practice

★ 按音配对，因此同时需要两侧的音级端口与逐音索引端口。
"""

TIMING_REQUIRED_PORTS: tuple[str, ...] = (
    "pcm.mapped.reference",    # timing.py:21
    "pcm.mapped.practice",     # timing.py:21
    "notes.reference",         # timing.py:22
)
"""`timing` 的必需端口 —— 摘自 `harmonica_eval/algorithms/timing.py:21-22`：

> MUST: 用 pcm.mapped.reference / pcm.mapped.practice（**两者都是 REFERENCE 轴**）
>       参考侧起音时刻取自 notes.reference（同一轴上）

★ ★ **刻意不含 `pcm.warped.practice`** —— `timing.py:30` 的 MUST NOT 明文禁止：

> MUST NOT: 使用 pcm.warped.practice 或任何 WARPED 轴数据
>           （会抹掉本算法要测的东西）

★ 理由见 `timing.py:13-15`：WARPED 轴把练习拉伸到与参考等长，
★ **抢拍拖拍在这个操作里被抹掉了，且看起来一切正常** ——
★ 这是「不会报错、只会给出错误答案」的陷阱。把它列进依赖等于要求它存在。
"""

DYNAMICS_REQUIRED_PORTS: tuple[str, ...] = (
    "rms.reference",       # dynamics.py:20
    "rms.practice",       # dynamics.py:20
    "notes.reference",    # dynamics.py:20
    "notes.practice",     # dynamics.py:20
)
"""`dynamics` 的必需端口 —— 摘自 `harmonica_eval/algorithms/dynamics.py:20`：

> MUST: 消费 rms.reference / rms.practice / notes.reference / notes.practice

★ ★ **本条是 MOLD BREAK 修正后的结论**（`dynamics.py:37-49` 原文）：

> 本模块第一版写着 MUST「用 WARPED 轴语义」、MUST NOT「使用 REFERENCE 轴」，
> 并声明 `AXIS = TimelineBasis.WARPED`。**这条约束无法满足。**
> 原因：`rms.reference` / `rms.practice` 在 profile 里都被声明为 REFERENCE 轴，
> 而数据面里**唯一**的 WARPED 端口是 `pcm.warped.practice` —— 没有 WARPED 轴的 rms。
> ……正确机制：**按音配对**。两侧各自有 `notes.*` 提供逐音索引。

★ 因此 `dynamics` **不消费** `pcm.warped.practice`（虽它是数据面唯一的 WARPED 端口），
★ `AXIS` 常量已随之删除。实现时不得依据旧版文档恢复 WARPED 语义。
"""


ALGORITHM_INPUTS: dict[str, tuple[str, ...]] = {
    "pitch": PITCH_REQUIRED_PORTS,
    "timing": TIMING_REQUIRED_PORTS,
    "dynamics": DYNAMICS_REQUIRED_PORTS,
}
"""`algorithm_id` → 其必需端口的权威映射（方案甲的唯一来源）。

★ **本表是端口需求的唯一真相源。** `FILE-201` 判据 A 所需的
  `PluginSpec.required_inputs` 在实现时**只能**从本表派生。

★ 键集合与 `REGISTRATION_ORDER` 恒等 —— 实现时必须校验二者一致，
  不一致即视为装配层缺陷（漏声明或多声明算法）。

★ `optional_inputs` v0.1 **全部为空**：三个算法当前都没有
  「缺失也能出正确结果」的端口。将来若有，**在本表之外另立**
  `ALGORITHM_OPTIONAL_INPUTS`，不得混入本表。
"""


# ★ 实现时按 algorithm_id 找到对应模块（装配根独占这个映射的依据）。
_ALGORITHM_MODULES = {
    "pitch": pitch,
    "timing": timing,
    "dynamics": dynamics,
}
"""`algorithm_id` → 算法模块。**唯一**依据是模块自己的 `ALGORITHM_ID` 常量，
`_check_declarations` 会逐条核对，不一致即抛错。"""


def _label_of(module: object, algorithm_id: str) -> str:
    """取算法模块的 `LABEL` 常量（中文显示名）。

    ★ 负责人 2026-09-24 裁定：三个算法模块各导出 `LABEL`，
    ★ 装配根据此填 `PluginSpec.label`。

    ★ **缺 `LABEL` 即抛错，不回退为 `algorithm_id`。**
    ★ 理由：静默回退是宪章 §5.6「禁止静默降级」反对的 ——
    ★ 回退后界面会把英文 ID 当中文名显示，**全程无任何报错**，
    ★ 等发现时已经流到用户眼前。宁可装配失败，也不要静默给出错误文案。
    """
    label = getattr(module, "LABEL", None)
    if not isinstance(label, str) or not label:
        raise ContractViolation(
            ErrorCode.PLUGIN_INCOMPATIBLE,
            f"算法模块缺少 LABEL 常量：{algorithm_id} 未导出中文显示名"
            f"（负责人 2026-09-24 裁定要求各算法自报 LABEL，"
            f"不得由装配根回退为 algorithm_id）",
            component="bootstrap",
        )
    return label


def _check_declarations() -> None:
    """校验冻结声明彼此自洽，不自洽即抛错而非静默补齐。

    三条必须成立（FILE-206 §4.1 不变量）：
      1. `ALGORITHM_INPUTS` 的键集合 == `REGISTRATION_ORDER`（不多、不少、不漏）
      2. 三个模块的 `ALGORITHM_ID` 与 `REGISTRATION_ORDER` 逐位一致
         （防某模块被换掉而装配清单还指着旧 id）
      3. `ALGORITHM_INPUTS` 声明的端口全部存在于 `profile.PORT_INDEX`
         （防声明了不存在的端口 —— 那是静默产出坏 Spec 的路径）
    """
    declared = set(ALGORITHM_INPUTS)
    ordered = set(REGISTRATION_ORDER)
    if declared != ordered:
        raise ContractViolation(
            ErrorCode.PLUGIN_INCOMPATIBLE,
            f"端口需求声明与注册顺序不一致：仅在 ALGORITHM_INPUTS={sorted(declared - ordered)}"
            f"，仅在 REGISTRATION_ORDER={sorted(ordered - declared)}",
            component="bootstrap",
        )

    module_ids = {name: mod.ALGORITHM_ID for name, mod in _ALGORITHM_MODULES.items()}
    expected = dict(zip(REGISTRATION_ORDER, REGISTRATION_ORDER, strict=True))
    if module_ids != expected:
        raise ContractViolation(
            ErrorCode.PLUGIN_INCOMPATIBLE,
            f"模块的 ALGORITHM_ID 与装配清单不一致：实得 {module_ids}，应得 {expected}",
            component="bootstrap",
        )

    for algorithm_id, port_ids in ALGORITHM_INPUTS.items():
        unknown = [pid for pid in port_ids if pid not in PORT_INDEX]
        if unknown:
            raise ContractViolation(
                ErrorCode.PLUGIN_INCOMPATIBLE,
                f"{algorithm_id} 声明了不存在的端口：{unknown}",
                port_id=unknown[0],
                component="bootstrap",
            )


def _requirement(port_id: str) -> InputRequirement:
    """从 `profile.PORT_INDEX` 派生一个 `InputRequirement`。

    ★ 逐字段来源（★ 不得在本文件硬编码，否则产生第二份真相源）：

    | `InputRequirement` 字段 | 来源                                     |
    |------------------------|------------------------------------------|
    | `port_id`              | 入参（来自 `ALGORITHM_INPUTS`）         |
    | `schema_version`       | 契约层默认值 `'*'`                       |
    | `timeline_basis`       | `PORT_INDEX[port_id].timeline_basis`     |
    | `element_type`         | `PORT_INDEX[port_id].element_type`       |
    | `required_fields`      | `tuple(PORT_INDEX[port_id].field_names)` |
    | `sample_rate`          | 见下方「与采样率无关的端口」规则          |

    ★ `schema_version` 用契约层默认值而非 `PROFILE_VERSION`：
    `contract.py:552-560` 明写「当前 12 个端口的 schema_version 全部等于
    `CORE_PROFILE_V0.1`，即它承载的是 profile 版本，不是逐端口的语义版本
    …… 绝大多数插件应当用默认值 `'*'`」，且 `PortSpec` **没有**该字段 ——
    硬编一个值反而是第二份真相源。

    ★ `sample_rate` 从 `AUDIO`（全局音频规格）取而非从 `PortSpec` 取：
    `PortSpec` 同样没有该字段，且采样率是全局属性（44100）不是逐端口属性。

    ★★ **例外：与采样率无关的端口必须填 0，不是 44100。★★**
    `notes.*`（按音索引表）、`chroma.*`、`warp_path.*` 描述符侧按
    `FILE-104:175` 的 `_SAMPLE_RATE_FREE_PREFIXES` 填 0；此处若填 44100，
    `runtime.resolve_inputs` 第 6 项的【精确匹配】会把它们判为不可用 ——
    **症状是三个算法全部 `INCOMPATIBLE: notes.*`，metrics.json 出不了 scalars。**
    ★ 判定必须与描述符侧【同一份名单】，否则两侧口径漂移。

    ★★ 措辞更正（本次注入附带）★★
    本函数只派生 `InputRequirement`，**不产出任何按音结果**。
    上面「按音索引表」是在解释 `notes.*` 端口为何属于「与采样率无关」那一类，
    而非声称本函数输出按音数据。此前写作「逐音索引表」会被 `verify_shell`
    的「docstring 声称产出『逐音』结果」检查读成能力承诺，故改为「按音索引表」。
    """
    spec = PORT_INDEX[port_id]
    if port_prefix(port_id) in SAMPLE_RATE_FREE_PREFIXES:
        req_sample_rate = 0
    else:
        req_sample_rate = AUDIO.sample_rate
    return InputRequirement(
        port_id=port_id,
        timeline_basis=spec.timeline_basis,
        element_type=spec.element_type,
        required_fields=tuple(spec.field_names),
        sample_rate=req_sample_rate,
    )


def build_plugin_specs() -> tuple[PluginSpec, ...]:
    """按 `REGISTRATION_ORDER` 构造三个 PluginSpec（尚未注册）。

    详细契约：返回顺序与 `REGISTRATION_ORDER` 严格一致；每个 PluginSpec 的
    `entry` 指向对应算法模块的公开入口。

    ★ **`required_inputs` 的权威来源是本文件的 `ALGORITHM_INPUTS`**（方案甲，
      负责人 2026-09-24 裁定，FILE-206 §4.5）——**不得**从算法模块读取，
      也不得在此凭记忆编造；每条 `InputRequirement` 由 `_requirement()` 从
      `profile.PORT_INDEX` 派生，避免硬编码产生第二份真相源。

    ★ 实现时必须校验 `set(ALGORITHM_INPUTS) == set(REGISTRATION_ORDER)`，
      不一致即抛错而非静默补齐（见 `_check_declarations`）。

    ★ `optional_inputs` v0.1 恒为空：三个算法当前都没有
      「缺失也能出正确结果」的端口（`ALGORITHM_INPUTS` docstring 已冻结此结论）。
      将来若有，**另立** `ALGORITHM_OPTIONAL_INPUTS`，不得混入本表。
    """
    _check_declarations()

    specs: list[PluginSpec] = []
    for algorithm_id in REGISTRATION_ORDER:
        module = _ALGORITHM_MODULES[algorithm_id]
        specs.append(
            PluginSpec(
                algorithm_id=module.ALGORITHM_ID,
                algorithm_version=module.ALGORITHM_VERSION,
                # ★ `label` 是契约层「给人看的中文短名，UI 直接显示」。
                # ★ 负责人 2026-09-24 裁定：三个算法模块各导出 `LABEL` 常量。
                # ★ ★ **缺 `LABEL` 直接抛错，不回退为 `algorithm_id`** ——
                # ★ ★ 静默回退正是宪章 §5.6「禁止静默降级」反对的：
                # ★ ★ 界面会把英文 ID 当中文名显示，而没有任何报错。
                label=_label_of(module, algorithm_id),
                required_inputs=tuple(
                    _requirement(pid) for pid in ALGORITHM_INPUTS[algorithm_id]
                ),
                optional_inputs=(),
                entry=module.run,
            )
        )
    return tuple(specs)


def build_default_registry() -> Registry:
    """构造已装好全部内置插件的 Registry，作为 Host 的唯一装配入口。

    详细契约：返回的 Registry 依次含 pitch / timing / dynamics 三个
    PluginSpec，顺序与 `REGISTRATION_ORDER` 一致；重复 algorithm_id 必须由
    `Registry.register` 显式报错，bootstrap 不得吞掉。

    ★ 边界：只返回 Registry。Host 拿到它之后**不再** import 任何具体算法；
    这正是本文件存在的意义（关闭 GC-204-08 的不变量冲突）。

    """
    registry = Registry()
    # ★ **不得**用 try/except 包裹 register，也不得静默跳过重复项 ——
    #   重复 `algorithm_id` 是装配层缺陷，必须让它显式冒泡。
    for spec in build_plugin_specs():
        registry.register(spec)
    return registry
