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
    # ── ① 校验 port（§5）────────────────────────────────────────
    #   ★ 校验失败必须【先失败、不启动服务】，所以这一步在延迟 import 之前。
    #   ★ 不吞异常：port 自己抛出的异常原样向上传播
    #     （刷新循环的处理是 app 的责任，不在本文件重复实现）。
    if port is None:
        raise TypeError(
            "launch_cockpit(port): port 为 None；"
            "C4 不构造 UiProjectionPort，必须由调用方注入（见本文件 MUST）"
        )
    for _name in ("snapshot", "submit"):
        if not callable(getattr(port, _name, None)):
            raise TypeError(
                f"launch_cockpit(port): port 缺可调用的 {_name}()；"
                "它必须实现 UiProjectionPort（见本文件 MUST）"
            )

    # ── ② 延迟 import app（§4.2 第 2 步）─────────────────────────
    #   ★★ 为什么必须放在函数体内：包导入期 import 子模块会造成
    #      导入顺序耦合与循环 import（见本文件 MUST NOT），
    #      且 §8 命令 A 断言导入后 sys.modules 里没有 .app。
    #   ★★ 这里【只】取符号并转发，不复制 app 的任何常量：
    #      绑定地址、端口探测、刷新周期、并发上限全在 app 侧（§4.2 第 3/4 步）。
    from . import app

    # ── ③ 启动并原样返回退出码（§4.2 第 3 步）───────────────────
    return app.run_local_ui(port)


__all__ = ["launch_cockpit"]
