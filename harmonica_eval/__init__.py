'''
FILE-ID:      FILE-001
COMPONENT:    COMP-PKG（包入口，本身不是组件）
SPEC:         SPEC.md@v2.1 · PLAN.md@v2 §四 · .spec/SHELL-STANDARD.md@v1
ROLE:
    harmonica_eval 包的出口：声明包版本与包的公开面（6 个子模块）。

INTENT:
    「这个包的公开面是什么」需要一个可读、可审的落点，而不是散在 import 惯例里。
    同时刻意保持**零子模块 import**：包导入期不加载任何组件，
    于是 import 顺序、循环依赖、以及某个组件尚未落地，都不会在这里爆炸。

MUST:
    - 只有三样东西：模块 docstring · __version__ · __all__
    - __all__ 与 PLAN.md §四 的文件清单一致（contract / profile / core / algorithms / host / cockpit）

MUST NOT:
    - import 任何子模块（本文件是包导入的第一个执行点，任何 import 都会外溢到全体使用者）
    - 定义函数 / 类 / 控制流
    - import numpy 或任何第三方库
    - 在此处 re-export 组件符号（会把包入口变成隐藏的装配点）

INPUT:
    （无）

OUTPUT:
    __version__ · __all__

BUILD-INSTRUCTION:
    .spec/build/FILE-001-v1.md
'''

__version__ = "0.1.0"
"""包版本。与**数据面身份无关** —— 数据面身份是 profile.PROFILE_VERSION。"""

__all__ = [
    "contract",
    "profile",
    "core",
    "algorithms",
    "host",
    "cockpit",
]
"""包的公开面：6 个子模块（PLAN.md §四）。

列的是**子模块名**而非符号名：`from harmonica_eval import *` 会加载它们，
而 `import harmonica_eval` 不会 —— 这正是本文件不写 import 语句的原因。
"""
