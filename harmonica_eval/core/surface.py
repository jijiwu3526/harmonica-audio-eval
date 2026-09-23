'''
FILE-ID:      FILE-104
COMPONENT:    COMP-C2 Audio Core
SPEC:         contract.AlgorithmDataContract · profile.PORTS · COMPONENTS.md@v2 §4.2

ROLE:
    把各模块产出的数据装配成一个**自描述、只读、已 Seal** 的数据面，
    并实现 CONTRACT-ALGORITHM-DATA-v1 的两个操作（manifest / read）。

INTENT:
    这是「深组件」的兑现处：算法只见 manifest + read 两个操作，
    **看不见 Core 内部的任何模块、DAG、缓存或存储策略**。
    Core 因此可以在不破坏任何算法的情况下重组内部实现。

MUST:
    - 由 profile.PORTS 驱动生成（穷举），不得硬编码端口名
    - Seal：所有数组 setflags(write=False)，Seal 后不可变
    - 为每个端口计算 content_hash（供同 build 回归断言）
    - read() 是**纯查表**：无副作用、不会失败于「算不出来」
    - 时长/尺寸校验：总字节超过 profile.BUDGET.max_surface_bytes → 构建失败

MUST NOT:
    - 暴露可写视图（writeable 必须为 False）
    - 在 read() 里触发任何计算（那会让 Core 变成算法需求的函数）
    - 端口不存在时返回空数组（必须抛 ContractViolation —— 空数组冒充成功
      是静默降级，违反宪章 §5.6）
    - 允许 Seal 后追加端口

INPUT:
    reference: float32 mono PCM
    practice:  float32 mono PCM
    sample_rate: int
    warp_path: int32[N, 2]

OUTPUT:
    Surface —— 实现 AlgorithmDataContract 的只读对象

BUILD-INSTRUCTION:
    .spec/build/FILE-104-v1.md
'''

from __future__ import annotations

from typing import Mapping

import numpy.typing as npt

from ..contract import (
    AlgorithmDataContract,
    AudioFormat,
    BufferView,
    PortDescriptor,
    SurfaceManifest,
)


def build_descriptor(
    port_id: str,
    data: npt.NDArray,
    sample_rate: int,
) -> PortDescriptor:
    """为一个已生成的数据数组构造自描述头。

    必须填的字段（缺一即为缺陷）：
        field_names   —— 多维度端口取自 contract.FIELD_LAYOUTS，
                         **不得**另行硬编码（那正是 FIELD_LAYOUTS 要消灭的重复）
        timeline_basis —— 取自 profile.PORT_INDEX[port_id]，必填语义
        sample_rate   —— 与采样率无关的端口（chroma / index 类）填 0
        content_hash  —— 内容指纹，用于同 build 回归断言
    """
    raise NotImplementedError("SHELL: FILE-104 待注入实现")


def seal(data: npt.NDArray) -> npt.NDArray:
    """把数组标记为只读，返回同一对象（不拷贝）。

    Seal 后任何写入尝试都应抛 ValueError（numpy 的行为）。
    这是「数据面不可变」的**执行机制**，不是文档承诺。
    """
    raise NotImplementedError("SHELL: FILE-104 待注入实现")


def generate_all_ports(
    reference: npt.NDArray,
    practice: npt.NDArray,
    sample_rate: int,
    warp_path: npt.NDArray,
) -> Mapping[str, npt.NDArray]:
    """按 profile.PORTS **穷举**生成全部端口数据。

    返回 {port_id: ndarray}，键集合必须与 profile.PORT_INDEX 完全一致 ——
    多一个或少一个都是缺陷（端口清单是封闭的）。

    实现提示：profile.PortSpec.produced_by 指明每个端口该由哪个模块生成，
    本函数负责调用它们并汇总，而不是自己实现特征提取。
    """
    raise NotImplementedError("SHELL: FILE-104 待注入实现")


def assert_budget(ports: Mapping[str, npt.NDArray]) -> int:
    """校验数据面总字节不超过 profile.BUDGET.max_surface_bytes，返回总字节。

    失败：抛 CoreBuildError(CORE_BUILD_FAILED)

    为什么预算故意宽松（512 MB）：本轮是快速原型验证，内存优化**不属于**
    本轮目标（负责人裁定：Mac 先行，先跑通）。放宽是为了让实现者
    不必为省内存牺牲正确性。实测 11 个端口在 120 s 音频下约 10–20 MB。
    """
    raise NotImplementedError("SHELL: FILE-104 待注入实现")


class Surface(AlgorithmDataContract):
    """只读数据面。实现 CONTRACT-ALGORITHM-DATA-v1 的**全部**能力。

    这是算法能看到的整个世界 —— 只有两个操作。
    它的深度来自「实现可以任意复杂，接口只有两个」。
    """

    def manifest(self) -> SurfaceManifest:
        """返回自描述清单，用于枚举端口并判断兼容性。

        算法只允许通过本方法的返回值了解数据面；
        **不得**假设任何未在清单中声明的端口存在。
        """
        raise NotImplementedError("SHELL: FILE-104 待注入实现")

    def read(
        self,
        port_id: str,
        time_range: tuple[float, float] | None = None,
    ) -> BufferView:
        """按键读取端口的（可选时间窗）只读视图。

        语义（契约已冻结，逐条实现）：
            单位是**秒**，左闭右开 [t0, t1)；None ⇒ 整段
            与帧坐标的换算由**实现**负责（调用方不得自行乘除 hop）
            端口不存在     → ContractViolation
            t0 >= t1 或越界 → ContractViolation
            **绝不返回空视图冒充成功**

        返回保证：data.flags.writeable is False；多维端口的第二维顺序
        与 descriptor.field_names 一致。
        """
        raise NotImplementedError("SHELL: FILE-104 待注入实现")


def build_surface(
    reference: npt.NDArray,
    practice: npt.NDArray,
    sample_rate: int,
    warp_path: npt.NDArray,
) -> Surface:
    """装配完整数据面并 Seal。

    步骤：生成全部端口 → 校验预算 → 逐端口 Seal → 构造 Surface。

    **不得部分发布**：任一步失败即抛 CoreBuildError，且已分配的资源
    由调用方（api.py）负责释放，数据面**不存在**。
    """
    raise NotImplementedError("SHELL: FILE-104 待注入实现")
