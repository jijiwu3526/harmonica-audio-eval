'''
FILE-ID:      FILE-100
COMPONENT:    COMP-C2 Audio Core
SPEC:         COMPONENTS.md@v2 §3 · PLAN.md@v2 §四 · SPEC.md@v2.1 §5/§6

ROLE:
    C2 的包出口：声明 Audio Core 的公开面。

INTENT:
    让「Audio Core 对外提供什么」有一个可读的落点。
    C1 只应通过本文件导出的门面与 Core 对话，不得深入子模块 ——
    这样 Core 内部如何切分模块，对 C1 与 C3 都是不可见的（深组件）。

MUST:
    - 只声明公开面，不含逻辑
    - 公开面必须与 profile.PORTS 的 produced_by 所指模块一致

MUST NOT:
    - import host / algorithms / cockpit（任何形式）
    - 在包导入期做重量级 import（numpy 之外不加载重型依赖）
    - 在此处 re-export 子模块的内部符号

INPUT:
    （无）

OUTPUT:
    __all__

BUILD-INSTRUCTION:
    .spec/build/FILE-100-v1.md
'''

from __future__ import annotations

__all__ = [
    "ingest",
    "align",
    "features",
    "surface",
    "api",
]
"""Audio Core 的公开子模块。

对应 profile.PORTS 里各端口的 produced_by：
    core.ingest    → 标准化 PCM（不产出端口，是前置步骤）
    core.align     → warp_path
    core.features  → pitch.* / rms.* / chroma.lowres.* / notes.*
    core.surface   → pcm.* （装配 + Seal）
    core.api       → CONTRACT-HOST-v1 的 7 个操作

**C1 只应 import `core.api`。** 其余子模块的公开只是为了可测试性与可审查性，
不是给 C1 或 C3 直接调用的入口。
"""
