'''
FILE-ID: FILE-015
COMPONENT: COMP-CONTRACT（跨组件契约层）
SPEC: COMPONENTS.md@v2 §4.2

ROLE:
    CONTRACT-ALGORITHM-DATA-v1 的操作签名声明。**纯 Protocol，无实现**。

INTENT:
    算法侧看到的**全部世界**只有两个操作：
        manifest()  —— 问「有哪些数据」
        read(...)   —— 读「我要的那份」

    这是「接口极小、实现极深」的最终落点：
    算法不需要知道 C2 内部有任何模块、DAG、存储后端或缓存策略。

MUST:
    - 只声明 2 个操作
    - 返回类型必须自描述（含单位、时间基准、采样率）
    - 明确所有权与生命周期

MUST NOT:
    - 出现任何"请求生成数据"的操作
      —— 兼容性检查是**单向**的：算法声明需要什么，只用来判断
      「有没有」；缺失即 INCOMPATIBLE，**绝不反推 C2 去生成**。
      这是整套设计的良心所在。
    - 允许写入：Seal 后任何角色都无写权限

INPUT:
    （无）

OUTPUT:
    AlgorithmDataContract（Protocol，2 个操作）

BUILD-INSTRUCTION:
    .spec/build/FILE-015-v1.md

DEPENDS-ON-OC1:
    **强依赖。** manifest/read 的返回类型与 read 的副作用语义
    （是否触发计算、是否可能失败、是否分块）**完全由 OC1 决定**：

        全内存物化  → read 立即返回 ndarray
        mmap/磁盘   → read 返回分块视图，需暴露"是否在内存"
        惰性计算    → read 有副作用（会触发计算），且可能失败
        流式        → 可能根本没有 read(port_id, range)，而是 iter_chunks()

    故本文件**只冻结"存在两个操作"这一结构**，
    **不冻结其签名细节**，待 OC1 裁定后由 L2 补齐。
'''

from __future__ import annotations

from typing import Any, Protocol, Sequence


class AlgorithmDataContract(Protocol):
    """算法 → 数据面的全部访问能力。

    实现者：COMP-C2 产出的数据面句柄。
    调用者：COMP-C3 各算法。

    所有权：所有数据归 C2 所有。借用方**不得**修改、**不得**释放、
    **不得**跨会话持有指针。
    """

    def manifest(self) -> Any:
        """返回自描述清单，用于枚举端口并判断兼容性。

        返回类型待 OC1 裁定（草稿见 .spec/draft/DRAFT-FILE-010-types.py
        的 SurfaceManifest，**仅供参考，不得引用**）。

        算法只允许通过本方法的返回值了解数据面；
        不得假设任何未在清单中声明的端口存在。
        """
        ...

    def read(self, port_id: str, time_range: Any = None) -> Any:
        """按键读取一个端口（可选时间窗）的只读视图。

        参数与返回类型待 OC1 裁定。此处只冻结语义约束：

        - time_range 为 None ⇒ 整段
        - 坐标含义由该端口声明的 timeline_basis 决定
        - 读不到的端口 ⇒ 抛错，**不得**返回空数组冒充成功
        - 不得返回可写视图
        """
        ...


REQUIRED_PORT_INVARIANTS: tuple[str, ...] = (
    "端口必须声明 timeline_basis（REFERENCE 或 WARPED）",
    "端口必须声明 sample_rate（它是结果的成因，不是元数据）",
    "端口必须声明 units 与 dimensions",
    "数据面必须始终含两份 aligned PCM（mapped + warped）——宪章 §11 逃生口",
)
"""无论 OC1 如何裁定，这些端口级不变量都必须成立。"""
