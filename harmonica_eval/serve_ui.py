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

★ **★ 不弹系统浏览器：★ 用环境变量，不加 CLI 开关 ★★**
  `DSH_NO_BROWSER=1 python3 -m harmonica_eval.serve_ui --reference … --practice …`

  ★ ★ 为什么不用 `--no-open-browser` 之类的开关：★ §7 明文禁止 ——
  · §7 边界：「不提供 `--port` / `--host` / `--no-browser` 等任何额外开关」
    （AGENTS.md 铁律 4「零噪声」）
  · §8 判据把 `--no-browser` 写进 `banned` 集合，`--help` 里出现即红
  ★ ★ ★ 而环境变量不新增命令行配置面，★ 是进程级约定而非「开关」

  ★ 默认行为不变：不设该变量时仍自动打开浏览器
  （`FILE-401-v1.md:185` §4.4 第 8 步明文要求「随后 `webbrowser.open(该 URL)`」）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

__all__ = ["main"]

# ── 数据集清单 ────────────────────────────────────────────────────────
# ★ 浏览器拿不到文件系统，★ 所以「选曲列表」必须由本层扫出来给界面。
# ★ 位置与形态依据 FILE-499-v1.md §6；★ 落在 data/out/ 与其它结论同处。
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DATASET_DIR = _REPO_ROOT / "harmonica_mvp_dataset"
_INVENTORY_JSON = _REPO_ROOT / "data" / "out" / "dataset_inventory.json"


def _sort_key(name: str) -> tuple[int, int, str]:
    """曲名目录排序键：数字前缀按【数值】排，无前缀的排后面。

    ★ 目录名形如 `01_奇异恩典`；★ 若按字符串排，`10_艰难时光` 会排在
    `02_绿袖子` 前面（'1' < '2'），★ 那是错的。
    """
    head = name.split("_", 1)[0]
    if head.isdigit():
        return (0, int(head), name)
    return (1, 0, name)


def scan_dataset(root: Path = _DATASET_DIR) -> dict:
    """扫数据集，产出【按曲子分组】的清单。

    契约（FILE-499-v1.md §6）：
    - 路径全部**相对仓库根**，因为 `set_reference(uri)` 吃的就是它；
      绝对路径换机即失效，清单会不可复现。
    - **只收 `.wav`**；质检图 PNG 与乐谱 midi 不进清单。
    - **不写死任何文件名**：扫到什么算什么。
    - 空目录（如 `_download` / `data`）被过滤，但**过滤项要报出来** ——
      静默过滤会让「我扫到 12 个而界面只有 10 个」变成谜。
    """
    songs: list[dict] = []
    skipped: list[dict] = []

    if not root.is_dir():
        return {"root": root.name, "songs": [], "skipped": [
            {"name": root.name, "reason": "数据集目录不存在"}],
            "song_count": 0, "wav_count": 0}

    for song_dir in sorted((p for p in root.iterdir() if p.is_dir()),
                           key=lambda p: _sort_key(p.name)):
        original = song_dir / "原曲_完整版.wav"
        melody = song_dir / "标准旋律版.wav"
        practice_dir = song_dir / "练习曲"
        practices = (
            sorted(p for p in practice_dir.iterdir()
                   if p.is_file() and p.suffix.lower() == ".wav")
            if practice_dir.is_dir() else []
        )
        if not (original.is_file() or melody.is_file() or practices):
            skipped.append({"name": song_dir.name,
                            "reason": "目录内无 .wav 文件",
                            "relative": str(song_dir.relative_to(_REPO_ROOT))})
            continue
        songs.append({
            "name": song_dir.name,
            "title": (song_dir.name.split("_", 1)[-1]
                      if "_" in song_dir.name else song_dir.name),
            "original": (str(original.relative_to(_REPO_ROOT))
                         if original.is_file() else None),
            "melody_version": (str(melody.relative_to(_REPO_ROOT))
                               if melody.is_file() else None),
            "practice": [{"name": p.stem,
                          "path": str(p.relative_to(_REPO_ROOT))}
                         for p in practices],
        })

    return {
        "root": str(root.relative_to(_REPO_ROOT)),
        "songs": songs,
        "skipped": skipped,
        "song_count": len(songs),
        # ★ 只数真实存在的条目：原曲 + 旋律版 + 练习曲。
        # ★ 曾经写成 `1 + bool(...) + bool(...) + len(...)`，★ 那个 1
        # ★ 会给每首曲子白加一个（10 首 → 70 变 80），★ 已修。
        "wav_count": sum(
            len([p for p in (s["original"], s["melody_version"]) if p])
            + len(s["practice"])
            for s in songs
        ),
    }


def _write_inventory(inventory: dict) -> Path:
    """把清单落盘，供 C4 读取。返回落盘路径。"""
    _INVENTORY_JSON.parent.mkdir(parents=True, exist_ok=True)
    _INVENTORY_JSON.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return _INVENTORY_JSON


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

    # ① 扫数据集并落盘清单。
    #    ★ 浏览器拿不到文件系统，★ 所以「选曲列表」只能由本层给。
    #    ★ 顺序不可调换：清单要在界面起来之前备好。
    inventory = scan_dataset()
    inventory_path = _write_inventory(inventory)
    print(f"数据集清单：{inventory['song_count']} 首曲子 / "
          f"{inventory['wav_count']} 个音频 → "
          f"{inventory_path.relative_to(_REPO_ROOT)}", file=sys.stderr)
    for item in inventory["skipped"]:
        print(f"  跳过目录 {item['name']}：{item['reason']}"
              "（无音频，不列入界面）", file=sys.stderr)

    # ② 装配 C1 —— 它同时就是 UiProjectionPort 的实现（host/app.py:88）。
    app = build_default_app()

    # ③ 建会话并把两端音频装进去。
    session_id = app.create_session("v1")
    app.set_reference(session_id, reference_uri)
    app.set_practice(session_id, practice_uri)

    # ④ 构建数据面（12 个端口）。
    app.build_surface(session_id)

    # ⑤ 运行算法。★ 缺这一步界面必然无指标：`build_surface` 只产出 12 个端口，
    #    标量指标要等 `run_algorithms`。此前只建了数据面就启动界面，
    #    导致首屏「标量指标」与「曲线」两节皆空、四态判别落进
    #    B_NO_SOURCE「已通但无数据」——★ 那不是设计取舍，是漏调一次。
    #    裁定：启动即跑算法（打开就有指标），界面上的「运行算法」按钮保留，
    #    供数据面重建后再次运行。
    app.run_algorithms(session_id)

    # ④b 把已注册算法 id 交给界面。★ 懒加载之后「没勾的插件」不在
    #      view 里，★ 而若勾选列表也从 view 推，★ 那就永远勾不上。
    #      装配处是唯一合法知道 registry 的位置，★ 界面自己拿不到。
    try:
        from .cockpit.app import set_plugin_ids
    except ImportError:                      # pragma: no cover - C4 不可用时上面已抛
        set_plugin_ids = None
    if set_plugin_ids is not None:
        registry = getattr(app, "_registry", None)
        if registry is not None:
            set_plugin_ids([spec.algorithm_id for spec in registry.list()])

    # ⑤ 交出端口，启动界面，阻塞至其关闭。
    #    ★ 不传端口号：端口由 C4 自行在 8721–8784 探测（app._pick_port）。
    return launch_cockpit(port=app)


if __name__ == "__main__":
    raise SystemExit(main())
