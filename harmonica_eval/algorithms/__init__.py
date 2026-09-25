'''
FILE-ID:      FILE-200
COMPONENT:    COMP-C3 Algorithm
SPEC:         SPEC.md@v2.1 · contract.PluginSpec · contract.InputRequirement · COMPONENTS.md@v2 §3

ROLE:
    插件契约的类型出口与 re-export；只说明算法应遵守什么形状，不保存算法清单。

INTENT:
    ★ 新增算法不得修改本文件。算法由 host/app.py 的装配点逐个调用
      Registry.register；新算法只在该处增加一次注册，不反向改写算法框架。

    旧版把算法清单、具体实现和字段映射一起塞在本文件，令框架知道每个算法是谁，
    迫使框架文件随算法增长。这里只保留稳定类型出口，避免这一反向依赖。

MUST:
    - 显式 re-export Registry、PluginSpec、InputRequirement
    - __all__ 完整列出且仅列出上述三个公开符号
    - 插件规格与输入需求只由 contract 定义，不得在此另造同义类型
    - 文档与注释使用中文，重要裁定用 ★ 标记

MUST NOT:
    - 依赖 core、host、cockpit，破坏 C3 的依赖方向
    - 依赖具体实现模块（.pitch / .timing / .dynamics）：
      框架一旦认识具体算法，新增算法就又必须修改本文件
    - 保存算法清单、具体入口或按算法标识索引的 payload 字段映射
    - 保留已删除结构的兼容别名或弃用提示

WHY:
    ★ 旧的按算法标识索引 payload 字段名映射存在，是因为信封的
      Mapping[str, Any] 不自带键名，而宿主曾以中央表校验结果。插件现已产出
      自描述的 Sequence[UiScalar | UiSeries]，字段名随对象一起传递；框架
      不再需要预知算法键名，因此中央映射是框架认识具体算法的根源，已移除。

    ★ 旧自检函数依赖旧清单逐项比对入口、端口与 payload 表，无法在只做
      类型出口后保持职责单一，故删除。重复 algorithm_id 的唯一性由 Registry
      自身负责，算法包不再复刻这一检查。

INPUT:
    ..contract 的 PluginSpec / InputRequirement；.registry 的 Registry

OUTPUT:
    Registry · PluginSpec · InputRequirement
    以及仅含以上三个名称的 __all__

BUILD-INSTRUCTION:
    .spec/build/FILE-200-v1.md
'''

from __future__ import annotations

from ..contract import InputRequirement, PluginSpec
from .registry import Registry

__all__: list[str] = ["InputRequirement", "PluginSpec", "Registry"]
