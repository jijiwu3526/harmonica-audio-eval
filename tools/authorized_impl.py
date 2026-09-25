"""已授权注入文件的唯一真相源（SHELL-STANDARD §七）。

本模块只做一件事：把「哪个文件被授权注入实现」这件事**只写一遍**，
其余检查器从此处派生，不再各自维护副本。

三处检查器此前各有一份（`verify_shell.GROUND_IMPL_NOTES`、
`verify_stubs_raise.AUTHORIZED_IMPL_FILES`、
`check_plugin_contract.AUTHORIZED_IMPLEMENTED_FILES`）。
三份内容相同、**路径基准不同**，改一处忘另两处就会漂移 ——
这正是本文件存在的原因。

三种基准（不要混用，也不要互相转换）：

* ``REPO_REL``     —— 相对仓库根，如 ``harmonica_eval/core/ingest.py``
* ``PKG_REL``      —— 相对 ``harmonica_eval`` 包，如 ``core/ingest.py``
* ``BASENAME``     —— 文件名，如 ``ingest.py``（仅用于**报告文案**，
  绝不用于判定；见 ``FORBIDDEN_MATCH_NOTE``）

授权依据格式：每条必须能回答「哪次授权、依据哪份 BI」。
无依据的条目不允许写入本表 —— 登记一个说不清来历的文件，
等于把架构约束的后门打开。

判定一律用**精确集合成员判断**（``in``），不得放宽成 ``startswith``
或目录前缀 —— 否则同目录下未授权的文件会被顺带放过。
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

# ---------------------------------------------------------------------------
# 真相源：以「相对仓库根的路径」为唯一书写形式
# ---------------------------------------------------------------------------

AUTHORIZED_IMPL: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        # ── C4 调试投影 ────────────────────────────────────────────────
        "harmonica_eval/cockpit/preview.py": (
            "负责人授权「派一个子智能体去做那个前端」；BI = FILE-401-P-v1.md"
        ),
        "harmonica_eval/cockpit/__init__.py": (
            "C4 包出口 launch_cockpit(...)，BI = FILE-401-v1.md:16 明文列为上游"
        ),
        "harmonica_eval/cockpit/app.py": (
            "负责人授权「继续派子智能体」并裁定「局域网直接支持」；"
            "C4 调试投影（非产品界面，见 AGENTS.md 铁律 2）；BI = FILE-400-v1.md"
        ),
        # ── 进程装配点（跨 C1/C4 之上，不属于任何一层）──────────────────
        "harmonica_eval/serve_ui.py": (
            "负责人授权「接上前端启动入口」；唯一同时 import host 与 cockpit 的"
            "进程装配配方；BI = FILE-400-v1.md:17「上游 = 包外装配方」+ "
            "FILE-002-v1.md:45 的唯一例外出口（它不是 __main__）"
        ),
        # ── C3 插件装配（第 1、2 刀）────────────────────────────────────
        "harmonica_eval/algorithms/bootstrap.py": (
            "负责人授权「派子智能体注入」第 1 刀；唯一物理装配根；BI = FILE-206-v1.md"
        ),
        "harmonica_eval/algorithms/registry.py": (
            "负责人授权「派子智能体注入」第 2 刀；注册表本体；BI = FILE-204-v1.md"
        ),
        "harmonica_eval/algorithms/runtime.py": (
            "负责人授权「派子智能体注入」第 2 刀；输入解析与结果校验；"
            "BI = FILE-205-v1.md"
        ),
        # ── C3 三算法（第 3、4 刀）────────────────────────────────────
        "harmonica_eval/algorithms/pitch.py": (
            "负责人授权「派子智能体注入」第 3 刀（音准）；BI = FILE-201-v1.md"
        ),
        "harmonica_eval/algorithms/timing.py": (
            "负责人授权「派子智能体注入」第 3 刀（节奏）；BI = FILE-202-v1.md"
        ),
        "harmonica_eval/algorithms/dynamics.py": (
            "负责人授权「派子智能体注入」第 3 刀（力度）；BI = FILE-203-v1.md"
        ),
        # ── C2 数据面 ─────────────────────────────────────────────────
        "harmonica_eval/core/ingest.py": (
            "负责人授权「继续派子智能体」；读 WAV、重采样、格式校验；"
            "BI = FILE-101-v1.md"
        ),
        "harmonica_eval/core/align.py": (
            "负责人授权「继续派子智能体」；DTW 对齐产出 warp_path；"
            "BI = FILE-102-v1.md"
        ),
        "harmonica_eval/core/features.py": (
            "负责人授权「继续派子智能体」；物化 pitch/rms/chroma/notes 四类特征；"
            "BI = FILE-103-v1.md"
        ),
        "harmonica_eval/core/surface.py": (
            "负责人授权「继续派子智能体」；12 端口物化与 seal；BI = FILE-104-v1.md"
        ),
        "harmonica_eval/core/api.py": (
            "负责人授权「继续派子智能体」；HostContract 唯一对外门面；"
            "BI = FILE-105-v1.md"
        ),
        # ── C1 编排与入口 ─────────────────────────────────────────────
        "harmonica_eval/host/app.py": (
            "负责人授权「继续派子智能体」；编排层，装配链闭合点；BI = FILE-301-v1.md"
        ),
        "harmonica_eval/__main__.py": (
            "负责人授权入口层；无头通路，出 metrics.json + report.md；"
            "BI = FILE-002-v1.md"
        ),
    }
)

# ---------------------------------------------------------------------------
# 三种基准的派生视图
# ---------------------------------------------------------------------------

REPO_REL: Final[frozenset[str]] = frozenset(AUTHORIZED_IMPL)

_PKG_PREFIX = "harmonica_eval/"

PKG_REL: Final[frozenset[str]] = frozenset(
    path[len(_PKG_PREFIX) :] for path in AUTHORIZED_IMPL
)

BASENAMES: Final[frozenset[str]] = frozenset(
    path.rsplit("/", 1)[-1] for path in AUTHORIZED_IMPL
)

#: 带授权依据的「仓库根相对路径 → 依据」映射（`verify_shell` 用它出文案）
NOTES_BY_REPO_REL: Final[MappingProxyType[str, str]] = AUTHORIZED_IMPL

#: 带授权依据的「包相对路径 → 依据」映射（`check_plugin_contract` 用它）
NOTES_BY_PKG_REL: Final[MappingProxyType[str, str]] = MappingProxyType(
    {path[len(_PKG_PREFIX) :]: note for path, note in AUTHORIZED_IMPL.items()}
)


# ---------------------------------------------------------------------------
# 判定辅助（统一在此，避免各检查器各写一遍、各写错一遍）
# ---------------------------------------------------------------------------


def is_authorized_repo_rel(rel: str) -> bool:
    """`rel` 是否为已授权文件（`rel` 须为仓库根相对路径）。

    ★ 精确成员判断。不接受目录、``..``、或任何前缀。
    """
    return rel in REPO_REL


def is_authorized_pkg_rel(rel: str) -> bool:
    """`rel` 是否为已授权文件（`rel` 须为包内相对路径，如 ``core/ingest.py``）。"""
    return rel in PKG_REL


def authorization_note(rel: str) -> str:
    """返回该路径的授权依据；未授权则抛错（不允许静默返回空串）。"""
    for table in (AUTHORIZED_IMPL, NOTES_BY_PKG_REL):
        if rel in table:
            return table[rel]
    raise KeyError(
        f"未授权的实现文件：{rel!r}。"
        " 若确已获授权，先在 tools/authorized_impl.py 登记依据（哪次授权、哪份 BI）。"
    )


FORBIDDEN_MATCH_NOTE: Final[str] = (
    "★ 不得用 basename / stem / startswith 判定："
    "同名文件放在不同目录会被一起放过"
    "（例如将来出现 cockpit/ingest.py 会被 algorithms 侧豁免连带放过）；"
    "相对路径不存在这种歧义。"
)
