"""进程装配点：构造 `UiProjectionPort` 并启动 C4 开发者视图。

FILE-ID:      FILE-499（进程装配点；不是 C1/C2/C3/C4 任何一层）
COMPONENT    : 进程装配层（跨层配方，位于 C1 与 C4 之上）
ROLE         : 唯一同时 import `host`（取 `UiProjectionPort`）与 `cockpit`（启动 UI）的模块
INTENT       : `FILE-400-v1.md:17` 规定「上游 = 包外装配方（进程装配点）。
                它构造一个 C1 提供的 `UiProjectionPort` 实例，并调用
                `launch_cockpit(port)`」。本文件就是那个配方。

★ **本模块不属于 C1 / C2 / C3 / C4 任何一层。**
  `host/`（C1）不 import `cockpit/`（C4）；`cockpit/`（C4）不 import `host/`。
  跨层的那一步只能由本文件完成 —— 这正是 FILE-400 把它列为「上游」的原因。

────────────────────────────────────────────────────────────────────────

MUST
  1. 构造一个实现了 `UiProjectionPort` 的实例（由 `host.app.build_default_app()` 提供）
     并作为参数注入 `cockpit.launch_cockpit(port)`。C4 不构造端口，端口由调用方注入。
  2. 在启动界面【之前】完成会话建立与数据面构建，否则界面打开是空视图。
  3. 把 `launch_cockpit` 返回的退出码原样作为本进程的退出码。
  4. 进程级失败（音频缺失、路径不可写、cockpit 不可导入）必须以非零退出码
     并在 stderr 给出**可读原因**，不得静默退出。

MUST NOT
  1. 不得让 `harmonica_eval/__main__.py` import `cockpit`。
     `FILE-002-v1.md:45` 明文：「两者之间【零依赖、零 import、零调用】：
     本文件绝不 import `cockpit`，C4 绝不 import 本文件」，
     且 `:47` 要求「把 `cockpit` 从环境中整体移除后，`__main__` 的 import 仍须成功」。
     ★ 本文件是该约束的**唯一例外出口**，且它不是 `__main__`。
  2. 不得做 DSP、对齐、特征计算或任何数值处理 —— 那是 C2 的职责。
     本文件只做装配与编排。
  3. 不得吞掉异常。失败要么原样抛出，要么转成可读的 stderr + 非零退出码。
  4. 不得 import `harmonica_eval.contract` 之外的契约层符号以外的东西，
     不得直接 import `core` / `algorithms` 内部模块绕过 C1 门面。

INPUT
  命令行：``--reference`` / ``--practice``（必填）
OUTPUT
  进程退出码：C4 的 `EXIT_OK` / `EXIT_START_FAILED`（由 `launch_cockpit` 返回）
  监听端口：由 C4 自行在 8721–8784 探测第一个可 bind 的端口
  ★ 本文件【不提供】--port 参数：端口归属是 C4 的职责
  ★ （`app._pick_port()` 已在规格 §4.4 第 2 步冻结为 8721–8784 探测），
  ★   装配点再插一个端口参数会形成第二份端口真相源。
  进程退出码：C4 的 `EXIT_OK` / `EXIT_START_FAILED`（由 `launch_cockpit` 返回）
────────────────────────────────────────────────────────────────────────

★ **启动命令的形态说明**
  `python3 -m harmonica_eval.serve_ui --reference 原曲.wav --practice 练习曲.wav`
  ★ ★ **此形态为本文件新增：规格（`SPEC.md` / `COMPONENTS.md` / `PLAN.md` /
  ★ ★   `FILE-400-v1.md`）均未规定进程装配点的位置与启动命令。**
  ★ ★ 选它的理由是朴素的 —— 沿用本项目既有的 `python3 -m harmonica_eval.<模块>`
  ★ ★   形态（`__main__` 与 `cockpit.app` 都如此），不引入新范式。
"""

from __future__ import annotations

import argparse
import sys

__all__ = ["main"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m harmonica_eval.serve_ui",
        description=(
            "启动本机开发者视图（C4）。"
            "本模块是进程装配点：构造 UiProjectionPort 并调用 launch_cockpit。"
        ),
    )
    parser.add_argument("--reference", required=True, help="参考演奏音频路径")
    parser.add_argument("--practice", required=True, help="练习演奏音频路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    """装配并启动 C4 开发者视图；返回退出码。

    参数：
        argv —— 命令行参数；``None`` 表示取 ``sys.argv[1:]``。

    返回：
        C4 的退出码。进程级失败时返回非零，并在 stderr 给出可读原因。

    异常：
        ★ 本函数【不吞异常】。`FileNotFoundError` / `CoreBuildError` 等
          由下面 `_run` 转成可读 stderr + 非零退出码；
          真正无法归类的异常原样向上传播（让调用方看到完整栈）。
    """
    args = _build_parser().parse_args(argv)
    try:
        return _run(args.reference, args.practice)
    except (FileNotFoundError, IsADirectoryError, PermissionError) as exc:
        print(f"无法启动界面：{exc}", file=sys.stderr)
        return 2
    except ImportError as exc:
        print(
            f"无法启动界面：缺少界面组件（{exc}）。\n"
            "提示：按不变量 F，界面可整体删除而不影响内核；"
            "本入口需要 `harmonica_eval.cockpit` 存在。",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # noqa: BLE001 —— 归类为「进程级失败」
        # ★ 必须给可读原因，不是崩栈。类型名带进消息，便于定位。
        print(f"无法启动界面：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def _run(reference_uri: str, practice_uri: str) -> int:
    """完成装配、建会话、构建数据面，然后启动 C4。

    ★ 顺序不可调换：端口必须先准备好数据面，否则界面首屏是空的。
    """
    # 局部 import：`--help` 路径不碰 C1 与 C4（与 `__main__.py` 同理）。
    from .host.app import build_default_app

    try:
        from .cockpit import launch_cockpit
    except ImportError as exc:
        raise ImportError(f"harmonica_eval.cockpit 不可用：{exc}") from exc

    # ① 装配 C1 —— 它同时就是 UiProjectionPort 的实现（host/app.py:88）。
    app = build_default_app()

    # ② 建会话并把两端音频装进去。
    session_id = app.create_session("v1")
    app.set_reference(session_id, reference_uri)
    app.set_practice(session_id, practice_uri)

    # ③ 构建数据面（12 个端口）。界面只看得见这 12 个端口。
    app.build_surface(session_id)

    # ④ 交出端口，启动界面，阻塞至其关闭。
    #    ★ 不传端口号：端口由 C4 自行在 8721–8784 探测（app._pick_port）。
    return launch_cockpit(port=app)


if __name__ == "__main__":
    raise SystemExit(main())
