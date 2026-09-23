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
    - __all__ 只列**真实存在于本模块命名空间**的名字

MUST NOT:
    - import 任何子模块（本文件是包导入的第一个执行点，任何 import 都会外溢到全体使用者）
    - **在 __all__ 里列子模块名**：本文件不 import 它们，故它们不是本模块的属性，
      列进去会让 `from harmonica_eval import *` 抛 AttributeError
      —— 那是**假声明**，比不声明更糟（★ 由 C4 智能体盲审发现）
    - 定义函数 / 类 / 控制流
    - import numpy 或任何第三方库
    - 在此处 re-export 组件符号（会把包入口变成隐藏的装配点）

INPUT:
    （无）

OUTPUT:
    __version__ · __all__ · PUBLIC_SUBMODULES

BUILD-INSTRUCTION:
    .spec/build/FILE-001-v1.md
'''

__version__ = "0.1.0"
"""包版本。与**数据面身份无关** —— 数据面身份是 profile.PROFILE_VERSION。"""

__all__: list[str] = []
"""本模块的导出面。**刻意为空。**

为什么不列子模块：本文件不 import 它们（见 MUST NOT），
所以 `contract` / `core` 等**不是本模块的属性**。
把它们写进 `__all__` 会让 `from harmonica_eval import *` 抛
`AttributeError: module 'harmonica_eval' has no attribute 'core'`
—— 空壳审查时实测确认过。

要声明「哪些子模块属于公开面」，用下面的 `PUBLIC_SUBMODULES`：
它是**文档性常量**，不是 import 指令，因此不会破坏「包导入期零加载」。
"""

PUBLIC_SUBMODULES: tuple[str, ...] = (
    "contract",
    "profile",
    "core",
    "algorithms",
    "host",
    "cockpit",
)
"""包的公开子模块清单（PLAN.md §四）。

`cockpit` 虽然**可缺席**（不变量 F：删掉它内核仍须跑通），
但仍列在这里 —— 因为「公开面」描述的是**设计上的一等公民**，
不是「当前磁盘上存在什么」。缺席与否是实现形态，不是接口形态。
"""
