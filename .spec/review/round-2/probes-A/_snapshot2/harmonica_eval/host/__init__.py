'''
FILE-ID:      FILE-300
COMPONENT:    COMP-C1 Framework / Host
SPEC:         COMPONENTS.md@v2 §4 · contract.HostContract · PLAN.md@v2 §五

ROLE:
    C1 的包出口：声明 Framework / Host 的公开面。

INTENT:
    让「编排层对外提供什么」有一个可读的落点。
    全系统只有这一个包同时依赖 core 与 algorithms —— 这是刻意的：
    装配点必须唯一，否则「谁负责把算法接上数据面」就没有答案。

MUST:
    - 只声明公开面，不含逻辑

MUST NOT:
    - 在此处实现编排逻辑（属于 app.py）
    - re-export core / algorithms 的符号（会让 C1 的包入口变成隐藏装配点）

INPUT:
    （无）

OUTPUT:
    __all__

BUILD-INSTRUCTION:
    .spec/build/FILE-300-v1.md
'''

from __future__ import annotations

__all__ = ["app"]
"""Framework / Host 的公开子模块。

C1 是**唯一**允许同时 import core 与 algorithms 的包。
其余组件（尤其 core/）不得出现这类跨界 import ——
`tools/verify_shell.py` 的「依赖方向」段会机械检查这一点。
"""
