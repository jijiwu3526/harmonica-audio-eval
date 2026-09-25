'''
FILE-ID:      FILE-400
COMPONENT:    COMP-C4
SPEC:         SPEC.md@v2.1 §1（负责人裁定例外）· COMPONENTS.md@v2 §3 COMP-C4 · PLAN.md@v2 §四/§五
ROLE:
    cockpit 包的出口：声明 C4 对外的**唯一**入口点 launch_cockpit()。

INTENT:
    界面系统必须能被整体删除而不影响内核（不变量 F）。
    把入口收成**一个**函数，C4 的边界在 import 层面就是一件事：
    调用方注入一个 UiProjectionPort，其余全部属于 C4 内部。

MUST:
    - 只暴露 launch_cockpit 一个入口点；app.py 的符号不作为包公开面
    - 端口由调用方注入（UiProjectionPort）；C4 不构造它、不 import C1
    - 界面只监听本机（见 app.LOCAL_BIND_HOST），不监听公网

MUST NOT:
    - import core / algorithms / host（任何形式，含延迟 import）
    - 在包导入期 import 子模块（含 .app）—— 避免 import 顺序耦合与循环 import
    - 持有音频缓冲、数据面缓冲或任何持久状态（纯视图）
    - 承担验收 / 测试职责（宪章 §36：验证是角色，不是产品件）

INPUT:
    由包外装配方注入的 UiProjectionPort（C1 提供）

OUTPUT:
    launch_cockpit() 的退出码（int）；界面本身只是本机进程内的开发者视图

BUILD-INSTRUCTION:
    .spec/build/FILE-400-v1.md
'''

from __future__ import annotations

from ..contract import UiProjectionPort


# ═════════════════════════════════════════════════════════════════════
# 一 · 唯一入口点
# ═════════════════════════════════════════════════════════════════════

def launch_cockpit(port: UiProjectionPort) -> int:
    """C4 的唯一对外入口点：启动本机开发者界面，阻塞至其关闭后返回退出码。

    参数：
        port —— C1 提供的 UiProjectionPort。**必须由调用方注入**：
                C4 不得 import C1，也不得自行构造该端口（见本文件 MUST / MUST NOT）。

    契约：
        - 只读：界面的一切显示都来自 port.snapshot()（见 app.build_plots）
        - 只写：界面的一切操作都经 port.submit()，且仅限 UiCommandKind 的 6 个成员
        - 无持久状态：进程退出即消失；界面崩溃或断开对 C1/C2/C3 的会话零影响
        - 绑定地址恒为本机（app.LOCAL_BIND_HOST），不得监听公网

    返回：退出码 int —— 正常关闭 / 启动失败两种结果，取值由 app 侧常量冻结。

    说明：本函数**阻塞**。它运行在哪个线程或进程，由包外装配方决定，
          C4 不假设也不管理进程模型。
    """
    raise NotImplementedError("SHELL: FILE-400 待注入实现")


__all__ = ["launch_cockpit"]
