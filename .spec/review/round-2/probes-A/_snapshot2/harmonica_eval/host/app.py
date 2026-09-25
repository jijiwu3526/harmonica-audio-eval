'''
FILE-ID:      FILE-301
COMPONENT:    COMP-C1 Framework / Host
SPEC:         contract.HostContract · contract.UiProjectionPort · contract.COMMAND_LEGALITY
              COMPONENTS.md@v2 §4 · SPEC.md@v2.1 §1

ROLE:
    应用生命周期 + 组件装配 + 算法编排 + 失败归一化 + 投影生成。
    全系统**唯一**的编排点。

INTENT:
    为什么 C1 必须存在（否则它会被当成多余的一层）：

    去掉 C1 后必然发生两件事之一：
        a) C2 得知道有哪些算法 → **深组件被破坏**，
           Core 变成插件需求的函数（正是负责人裁定要消灭的反模式）
        b) C4 直接调 C2/C3   → **界面进入计算路径**，
           UI 崩溃会污染数据面

    所以 C1 的职责是**具体的、不可省的**：
    持有会话、驱动状态机、调算法、归一化失败、产出投影。
    它**不是**转发层 —— 它拥有编排权，而编排权在全系统只此一处。

MUST:
    - 状态机单调推进，不可回退、不可跳过 DATA_READY
    - 算法**只能**在 DATA_READY 下触发
    - 兼容性检查是**单向**的（用 contract.COMMAND_LEGALITY 校验命令）
    - 单个算法失败**不影响**其他算法
    - 投影必须**已下采样**，且每条曲线声明 timeline_basis
    - C4 缺席时全流程仍能跑通（不变量 F）

MUST NOT:
    - 做任何信号处理（fft / pyin / stft / dtw / resample 一律禁止）
      —— 若你需要"算一下"，说明该逻辑属于 C2 或 C3
    - 因为某算法缺端口就去让 C2 生成数据（**核心禁令**）
    - 让算法异常穿透（必须捕获并转成 FAILED 信封）
    - 把不同 timeline_basis 的曲线放进同一个投影（会误导，见 UiSeries）

INPUT:
    （无 —— 本模块是装配点，被 __main__.py 或 cockpit 驱动）

OUTPUT:
    HostApp —— 同时实现 HostContract 的消费方与 UiProjectionPort

BUILD-INSTRUCTION:
    .spec/build/FILE-301-v1.md
'''

from __future__ import annotations

from typing import Mapping, Sequence

from ..contract import (
    AlgorithmResultEnvelope,
    SessionState,
    UiCommand,
    UiProjectionPort,
    UiView,
)

MAX_PROJECTION_POINTS: int = 2000
"""单条曲线在投影里的最大点数。

依据宪章 §44.12（Human Control Cockpit）：人类不得面对几十万个数据点。
120 s 音频在 hop=256 下有约 2 万个帧 —— 直接画出来既慢又无信息量。
下采样是**投影的职责**，不是界面的职责（界面不得重算）。
"""


class HostApp(UiProjectionPort):
    """编排层。持有会话、驱动状态机、调算法、产出投影。

    ★ 澄清（§20 盲审报告的 G8 有一半是误读，此处写清以免再被误读）：

    本类**不是** `HostContract` 的实现类，而是它的**消费方**。

        HostContract   —— C1 → C2 的接口，由 **C2** 实现（`core/api.py: HostCore`）
        UiProjectionPort —— C1 → C4 的接口，由**本类**实现

    故本类的方法集合**本来就不该**等于 HostContract 的 7 个操作 ——
    它额外拥有 `run_algorithms` / `check_compatibility` / `normalize_error` /
    `build_view` 这些**编排职责**，这恰恰是 C1 存在的理由
    （见本模块 INTENT：C1 不是转发层，它拥有编排权）。

    盲审者把"消费方"误当成"实现方"了。但它指出的**真问题**成立：
    `__main__.py` 的 `run_headless` 需要知道"登记输入"到底调谁 ——
    第一版没写清 C1 自己有没有会话跟踪 API。

    ── 冻结 C1 的会话跟踪职责（答上述问题）──

    C1 **持有** session_id，并且：

        create_session(profile_version)  → 调 C2 建会话，把 id 记在 C1 里
        set_reference(path) / set_practice(path)
                                         → 用 C1 记住的 id 调 C2
                                           （**不带 session_id 参数**）
        build_surface()                  → 同样用 C1 记住的 id
        run_algorithms()                 → 用 C1 记住的 id 取数据面并跑算法

    为什么 C1 这些方法**不带** session_id 而 C2 的带：
        C2 要支持**多会话**（它是通用核心，不该假设只有一个会话）；
        C1 在本产品里**只服务一个开发者、一个会话**（Mac 端调试工具）。
        把"当前会话"这个隐含状态**收在 C1**，而不是泄漏到 C2 的签名里。

    这与 G8 的修正**不矛盾**：`HostContract`（C2 的接口）必须显式传
    session_id，因为 C2 是多会话的；`HostApp`（C1 的门面）不需要，
    因为 C1 在一次运行里只有一个会话。

    ★ 若将来 C1 要支持多会话，`HostApp` 的方法**必须**加 session_id ——
    但那是一次契约变更，须由负责人裁定，不得由实现者自行"顺手加上"。
    """

    def __init__(self, core: object) -> None:
        """装配。C1 是**唯一**知道"有哪些实现"的地方。

        参数 core 是 COMP-C2 的 HostContract 实现。
        算法注册表来自 algorithms.ALGORITHMS（本模块 import 它 ——
        这是全系统唯一允许的跨界 import）。
        """
        raise NotImplementedError("SHELL: FILE-301 待注入实现")

    # ── ① 生命周期 ────────────────────────────────────────────

    def create_session(self, profile_version: str) -> str:
        """创建会话。状态 → CREATED。返回 session_id。

        C1 **记住**这个 id（见类 docstring 的会话跟踪说明），
        后续 set_reference / set_practice / build_surface / run_algorithms
        **不需要**再传它。
        """
        raise NotImplementedError("SHELL: FILE-301 待注入实现")

    def destroy_session(self, session_id: str) -> None:
        """销毁会话，释放资源。状态 → CLOSED。

        ★ 本方法**带** session_id，而其他编排方法不带 ——
        这不是笔误：销毁是可能发生在错误恢复路径上的操作，
        此时 C1 记住的 id 可能已经失效或需要显式指定要清理哪个会话。
        传参比依赖隐含状态更安全（清理路径上的异常会掩盖真实失败）。
        """
        raise NotImplementedError("SHELL: FILE-301 待注入实现")

    def set_reference(self, path: str) -> None:
        """登记参考演奏路径。用 C1 记住的会话。成功 → INPUT_READY。

        ★ 参数名是 `path`（不是 `uri`），且类型是 `str`。

        为什么与 C2 的 `uri` 不同名：C2 是通用核心，"uri" 允许未来
        扩展成非文件来源；C1 是本产品的门面，本轮**只接受文件路径**。
        两者语义不同（C1 的 path 会被 C1 校验存在性后再交给 C2），
        强行同名会让读者以为可以直接透传。
        """
        raise NotImplementedError("SHELL: FILE-301 待注入实现")

    def set_practice(self, path: str) -> None:
        """登记练习演奏路径。用 C1 记住的会话。成功 → INPUT_READY。"""
        raise NotImplementedError("SHELL: FILE-301 待注入实现")

    def build_surface(self) -> None:
        """构建数据面。用 C1 记住的会话。

        前置：状态 == INPUT_READY，否则抛 ContractViolation。
        这是**同步阻塞**调用（见 contract.UiView.progress 的 G9 说明）。
        """
        raise NotImplementedError("SHELL: FILE-301 待注入实现")

    # ── ② 编排 ────────────────────────────────────────────────

    def check_compatibility(self, algorithm_id: str) -> bool:
        """检查某算法的 required_ports 是否都在数据面 manifest 里。

        ★ **单向检查**：只判断"有没有"。
        缺失 → 该算法 INCOMPATIBLE，**其余算法照常运行**。
        **绝不**因为缺端口就去让 C2 生成数据 —— 那会让 Core 变成
        插件需求的函数，正是本架构要消灭的东西。
        """
        raise NotImplementedError("SHELL: FILE-301 待注入实现")

    def run_algorithms(self, session_id: str) -> Sequence[AlgorithmResultEnvelope]:
        """逐个运行算法并收集结果信封。

        前置：状态 == DATA_READY，否则抛 ContractViolation。

        关键行为：
            - 单个算法抛异常 → 捕获 → 转成 status='FAILED' 的信封
            - 单个算法失败**不中断**其余算法
            - 结果必须校验 schema 合法性（算法可能返回垃圾）
            - 已知缺口：算法死循环会**卡住此处**（v0.1 无超时机制）

        返回顺序应与 algorithms.ALGORITHMS 的声明顺序一致 ——
        否则报告的顺序会随运行变化，不可复现。
        """
        raise NotImplementedError("SHELL: FILE-301 待注入实现")

    # ── ③ 失败归一化 ──────────────────────────────────────────

    def normalize_error(self, exc: Exception) -> tuple[str, str]:
        """把异常转成 (error_code, 给开发者的一句话)。

        必须正确区分四种情况（对应 COMPONENTS.md §7 失败语义表）：
            构建失败        → 数据面**不存在**，算法不启动
            算法要未知端口  → 数据面有效，该算法 INCOMPATIBLE，其余正常
            算法崩溃        → 数据面有效，其余正常
            算法死循环      → 数据面有效，**整个流程卡住**（v0.1 缺口）
        """
        raise NotImplementedError("SHELL: FILE-301 待注入实现")

    # ── ④ 投影生成 ────────────────────────────────────────────

    def build_view(self, session_id: str) -> UiView:
        """把当前状态与算法结果转成 UiView。

        硬要求：
            - 时间序列**必须下采样**到 MAX_PROJECTION_POINTS 以内
            - 每条 UiSeries **必须**声明 timeline_basis
              （用错轴会让用户把 warped 轴上的图当成真实时间，
                从而误读抢拍拖拍）
            - **禁止**把不同 basis 的曲线放进同一个视图
            - UiScalar 只陈述数值与单位，**不下教学结论**（SPEC §1）
            - progress 取值域是 0.0–1.0（比例），None 表示无进度概念
        """
        raise NotImplementedError("SHELL: FILE-301 待注入实现")

    # ── ⑤ UiProjectionPort（C4 的唯一入口）────────────────────

    def snapshot(self) -> UiView:
        """取当前投影快照。**纯读取，无副作用**。"""
        raise NotImplementedError("SHELL: FILE-301 待注入实现")

    def submit(self, command: UiCommand) -> None:
        """下发一条用户意图。

        必须用 contract.COMMAND_LEGALITY 校验：
            合法   → 执行
            非法   → **拒绝，且不改变状态**（不许"尽力而为"）

        C4 可能不做置灰（那是 UI 优化），故**这里必须校验** ——
        界面不是可信输入源。
        """
        raise NotImplementedError("SHELL: FILE-301 待注入实现")


def build_default_app() -> HostApp:
    """装配默认配置的应用。供 __main__.py 与 cockpit 使用。

    这是 composition root：全系统唯一知道"用哪个 Core 实现、
    有哪些算法"的地方。
    """
    raise NotImplementedError("SHELL: FILE-301 待注入实现")
