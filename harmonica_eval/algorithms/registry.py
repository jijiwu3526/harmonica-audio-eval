'''
FILE-ID:      FILE-204
COMPONENT:    COMP-C3 Algorithm
SPEC:         SPEC.md@v2.1 · 负责人冻结的 Registry 裁定 · SHELL-STANDARD v1
ROLE:
    显式算法注册表，只回答「系统里有哪些插件」；装配期注册，运行期只读。
INTENT:
    把插件清单收敛为单一、可审查的数据结构，避免目录扫描、entry-points
    与动态发现把运行结果变成隐式且不可复现的行为。
MUST:
    - 只提供 register / list / get 三个操作
    - list() 严格保持注册顺序，get(algorithm_id) 目标复杂度为 O(1)
    - register() 遇到重复 algorithm_id 必须显式报错
    - 只依赖 contract.PluginSpec，不依赖具体算法模块
MUST NOT:
    - 依赖 C2 / C1 / C4 内部模块
    - 扫描目录、读取 entry-points 或动态发现插件
    - 提供 unregister、enable / disable 或 compatible_with
    - 让 Registry 持有 Host / Session 的启停与兼容性决策
INPUT:
    装配期显式传入的 PluginSpec，以及查询时传入的 algorithm_id。
OUTPUT:
    注册后的 PluginSpec 保序 tuple、按 algorithm_id 查得的对象或 None。
BUILD-INSTRUCTION: .spec/build/FILE-204-v1.md
★★ 铭牌字段必须单行：解析器按行尾取该字段，续行会被并入同名字段。
★ 裁定：list() 返回 tuple 而不是 dict，因为 C1 的 run_algorithms 已冻结
「返回顺序与注册顺序一致」；dict 会打乱顺序，不能作为报告顺序的事实来源。
★ 裁定：register() 只做重复 algorithm_id 检查，因为这是唯一不需要 surface 的完整性检查；
surface 相关判断由 runtime 负责。
★ 裁定：故意不提供 unregister。插件在装配期注册一次，运行期不改；提供它就变成
动态管理，超出 v0.1 MVP。
★ 裁定：故意不提供 enable / disable。插件启停属于 Host / Session 配置，
Registry 只回答「有什么」，Host 回答「这次跑哪些」。
★ 裁定：故意不提供 compatible_with()。兼容检查需要 surface；Registry 不知道
surface，属于 runtime 的责任。
★ 存储裁定：以 algorithm_id 为键的映射承担 O(1) get，以保序序列承担 list；
两者必须同步维护，不能让 dict 成为顺序来源。

★ 实现裁定（负责人 2026-09-24 授权注入，FILE-204 §4/§5）：
    · 存储用**单个保序 dict** —— CPython 3.7+ 的 dict 保证插入序，
      因此「一个 dict 同时提供 O(1) get 与保序 list」，**不需要两份状态**。
      上面那条「两者必须同步维护」在此实现下由同一份状态天然满足；
      若真维护两份，反而制造了宪章 §5.6 禁止的静默分叉风险。
    · 本类**有状态**：register 会写入成员，用 __init__ 初始化为空表。
      MUST NOT 那条「不持有 Host / Session 决策」指的是**不持有决策**，
      不等于不可持有注册表自身的数据。
'''

from __future__ import annotations

from ..contract import ErrorCode, HarmonicaError, PluginSpec


__all__ = ["Registry"]


class Registry:
    """显式注册表：只登记 PluginSpec，不发现、不管理、不运行插件。

    本类是 v0.1 的最小集合。三个方法的边界刻意保持清晰：register 只接收
    装配期声明，list 只读出可复现的顺序，get 只按稳定标识查询。
    """

    __slots__ = ("_by_id",)

    def __init__(self) -> None:
        """建一个空注册表；顺序即后续 register 的调用顺序。"""
        self._by_id: dict[str, PluginSpec] = {}

    def register(self, spec: PluginSpec) -> None:
        """登记一个插件规格；重复 algorithm_id 必须显式失败。

        详细契约：接受单个 PluginSpec；已存在同一 algorithm_id 时抛出错误；
        成功后插件按本次调用顺序进入 list() 结果。

        ★ 错误码选择（实现裁定，FILE-204 未指定）：用 `INTERNAL_ERROR` 而非
        `PLUGIN_INCOMPATIBLE` —— 后者语义是「插件与数据面/环境不兼容」，
        而重复登记是**装配层的缺陷**（同一个 id 被注册两次），
        契约对 `INTERNAL_ERROR` 的定义正是「未分类失败路径，出现即视为缺陷」。
        ★ 若日后 `ErrorCode` 增补「DUPLICATE_REGISTRATION」之类，应改用它。
        """
        if spec.algorithm_id in self._by_id:
            raise HarmonicaError(
                ErrorCode.INTERNAL_ERROR,
                "重复的 algorithm_id：" + spec.algorithm_id,
                component="COMP-C3",
            )
        self._by_id[spec.algorithm_id] = spec

    def list(self) -> tuple[PluginSpec, ...]:
        """按注册顺序返回全部插件规格。

        详细契约：返回 tuple[PluginSpec, ...]，顺序与成功 register 的调用顺序一致；
        不返回 dict，不改变注册顺序，不携带运行期状态。
        """
        return tuple(self._by_id.values())

    def get(self, algorithm_id: str) -> PluginSpec | None:
        """按 algorithm_id 查询插件规格；未注册时返回 None。

        详细契约：algorithm_id 是不透明的稳定字符串；目标复杂度为 O(1)；
        找不到不抛异常，因为「没有这个插件」是可回答的查询结果。
        """
        return self._by_id.get(algorithm_id)
