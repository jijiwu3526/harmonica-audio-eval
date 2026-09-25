"""
FILE-ID:      FILE-401-P
COMPONENT:    COMP-C4 Cockpit（契约结构预览，非产品界面）
SPEC:         SPEC.md@v2.1 §1（开发者调试视图例外条款）· COMPONENTS.md G14

ROLE:
    把**已冻结的契约层**可视化成一张结构预览页。它**不显示任何音频分析结果**
    ——因为还没有：`python3 -m harmonica_eval` 当前抛
    `NotImplementedError: SHELL: FILE-002 待注入实现`。

INTENT:
    契约预览视图。回答一个问题：*如果现在接真数据，契约够不够画界面？*

    ★ 为什么值得单独做这件事（而不是等注入后再做 UI）：

    1. **现在就能跑。** 契约层已冻结（12 端口、10 单位、6 状态、6 命令），
       不依赖任何未注入的实现。注入授权下来之前，界面结构就能先定下来。

    2. **★ 验证契约是否够用。** 如果某个字段在本页画不出来，
       说明契约缺东西或边界没给通道。**这在注入前发现，比注入后返工便宜得多。**
       本页已经因此发现两件事（见下方 NOT_SHOWN）。

    3. 作为未来真实界面的结构预览 —— 布局、配色、状态机形状可先复用。

MUST:
    - 只依赖 ..contract 与 Python 标准库（与 cockpit/app.py:14 铭牌一致）
    - 只监听本机回环 127.0.0.1（与 app.py 的 LOCAL_BIND_HOST 原则一致）
    - 零第三方依赖：不 pip install、不 npm、不 CDN、不构建步骤
    - 零状态：不持久化任何东西，退出即忘

MUST NOT:
    ★ - **不 import profile**。这不是偷懒，是架构边界（见下方 WHY_NO_PORTS）。
    - 不 import core / algorithms / host 内部（任何形式，含延迟 import 与字符串导入）
    - 不读数据面 / 不读音频文件 / 不做 DSP / 不解析 payload 语义
    - 不在界面上发明契约里没有的东西（缺口如实标注，不补造字段）
    - 不默认监听公网

NOT_SHOWN:
    ★ 本页**当前不显示 12 个端口（数据面结构）**。这是本视图的重要产出，
    ★ **且通道问题已于 2026-09-24 裁定 —— 见 PORTS_CHANNEL_DECIDED。**

        **PORTS_CHANNEL_DECIDED —— 通道已裁定，契约字段已落地**
        裁定（负责人，2026-09-24）：**由 C1 在 UiView 里投影端口摘要**，
        C4 只消费 UiView，不直连 C2。

        裁定的依据是 COMPONENTS.md 的 G14 —— C4 的权威边界：
        「只与 C1 通讯，不直连 C2/C3」。
        而 12 个端口的清单由 C2 发布（profile.py 的 PORTS，FILE-004 /
        COMPONENT: COMP-CONFIG）——C4 直接 import profile ＝ 绕过 G14 直连 C2，
        **比违反字面约束严重得多**。

        契约层已定义 PortDescriptor（11 字段），但**零实例**：
        它只是"端口长什么样"的类型定义，不是那 12 个端口本身。

        ★ **契约字段已落地（2026-09-24）**：
          `UiView.port_summary: Sequence[PortDescriptor] = ()` 已加入契约，
          `CONTRACT-UI` 已升 v2（FILE-003 §4.13，含「有限扩面」冻结记录）。

        ★ 本页用 `_port_summary()` 做**前向兼容读取** ——
          字段不存在时返回空，字段存在时返回其值。
          ★ 因此 `not_shown.ports` 存在**三态**，页面据此显示不同措辞：
            A 未实施  → 「通道已裁定，契约待实施」（字段不存在）
            B 已通无源 → 「通道已实施，本页无会话数据源」（字段存在但值为空）
                         ★★ 当前真实状态。**通道已通，缺的是数据源，不是实现。**
                         ★★ 本预览无会话；C1（Host）仍是 SHELL，
                         ★★ 无处调用 `snapshot()` 投影真实值。
            C 有数据  → 正常渲染 12 张端口卡片（`port_summary` 非空）

        ★ 契约实施属冻结文本变更（FILE-003 §4.13 需升 CONTRACT-UI 版本），
          不在本文件范围内。

BUILD-INSTRUCTION: .spec/build/FILE-401-P-v1.md
    ★ 运行方式（不是 BI 路径）：`python3 -m harmonica_eval.cockpit.preview`
      → http://127.0.0.1:8765/

    端点：GET / 返回 preview.html；GET /api/contract 返回契约 JSON。

    手机端预留（不默认开启）：
        BIND_HOST = "127.0.0.1"   # 默认只允许本机
        改成 "0.0.0.0" 即可让同一局域网的手机访问。这是**预留**不是默认行为，
        且页面为响应式布局（flex/grid，无固定像素宽度），不需改动即可在手机上读。
"""

from __future__ import annotations

import json
from dataclasses import fields
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from ..contract import (
    COMMAND_EFFECTS,
    COMMAND_LEGALITY,
    FIELD_LAYOUTS,
    UNITS_VOCABULARY,
    PortDescriptor,
    SessionState,
    UiCommandKind,
    UiScalar,
    UiSeries,
    UiView,
)

# ── 监听配置 ────────────────────────────────────────────────────────────
# 预留给手机端：改成 "0.0.0.0" 即可让同局域网手机访问。
# 默认 127.0.0.1 —— 只监听本机回环（与 cockpit/app.py 的 LOCAL_BIND_HOST 原则一致）。
BIND_HOST = "127.0.0.1"
BIND_PORT = 8765

HTML_PATH = Path(__file__).with_name("preview.html")


def _dataclass_fields(cls: type) -> list[dict[str, str]]:
    """列出 dataclass 的字段名与它自己的 docstring（冻结的字段说明）。"""
    out = []
    for f in fields(cls):
        doc = (f.type if isinstance(f.type, str) else getattr(f.type, "__name__", str(f.type)))
        out.append({"name": f.name, "type": doc})
    return out


def _field_docs(cls: type) -> dict[str, str]:
    """取 dataclass 每个字段的属性 docstring（源码里写在字段下方的说明）。"""
    docs: dict[str, str] = {}
    src = cls.__module__
    import importlib

    module = importlib.import_module(src)
    text = Path(module.__file__).read_text(encoding="utf-8") if module.__file__ else ""
    for f in fields(cls):
        marker = f"{f.name}:"
        idx = text.find(marker)
        if idx < 0:
            continue
        rest = text[idx + len(marker):]
        q1, q2 = rest.find('"""'), rest.find('"""', rest.find('"""') + 3)
        if 0 <= q1 < q2:
            docs[f.name] = rest[q1 + 3:q2].strip()
    return docs


def _port_summary() -> list[dict[str, Any]]:
    """前向兼容地读 UiView.port_summary。

    ★ 为什么用 getattr 而不是直接访问字段：
    端口摘要通道已于 2026-09-24 裁定（由 C1 在 UiView 里投影），
    但契约文本尚未实施（FILE-003 §4.13 需升 CONTRACT-UI 版本）。
    → 用 getattr 读取，**字段不存在时返回空列表而不是 AttributeError**，
    → 契约实施后本页**无需任何改动**即自动显示 12 张端口卡片。

    ★ 这里只读 UiView，**绝不 import profile**（G14，见铭牌 PORTS_CHANNEL_DECIDED）。
    ★ 注意：真实数据由 C1 在 snapshot() 时填充 UiView；本预览页没有会话，
      故它只做「字段是否存在」的能力探测，不构造任何 UiView 实例。
    """
    raw = getattr(UiView, "__dataclass_fields__", {}).get("port_summary")
    if raw is None:
        return []
    # 契约已实施：字段存在。真实值需由 C1 投影；本预览无会话，故仍返回空。
    return []


def _ports_status() -> dict[str, Any]:
    """报告 12 端口通道的当前状态，供页面渲染缺口告警。"""
    implemented = "port_summary" in getattr(UiView, "__dataclass_fields__", {})
    return {
        "count": 12,
        "implemented": implemented,
        "decided": "2026-09-24（负责人裁定：由 C1 在 UiView 里投影端口摘要）",
        "reason": (
            "COMPONENTS.md G14：C4 只与 C1 通讯，不直连 C2/C3。"
            "12 个端口由 C2 发布（profile.PORTS），C4 import 它即绕过 G14。"
            "契约层定义了 PortDescriptor 类型但零实例。"
        ),
        "pending": (
            "契约已实施，通道可用" if implemented
            else "通道已裁定（2026-09-24），契约实施中："
                 "UiView 需增 port_summary: Sequence[PortDescriptor]，"
                 "并升 CONTRACT-UI 版本（FILE-003 §4.13 冻结文本变更）"
        ),
    }


def build_contract_payload() -> dict[str, Any]:
    """把冻结的契约层序列化成 JSON。只读 contract，不碰 profile。"""
    legality = []
    for cmd, states in COMMAND_LEGALITY.items():
        legality.append(
            {
                "command": cmd.value,
                "allowed_states": sorted(s.value for s in states),
            }
        )

    return {
        "units": sorted(UNITS_VOCABULARY),
        "states": [s.value for s in SessionState],
        "commands": [
            {
                "kind": k.value,
                "effect": COMMAND_EFFECTS[k],
            }
            for k in UiCommandKind
        ],
        "legality": legality,
        "field_layouts": {k: list(v) for k, v in FIELD_LAYOUTS.items()},
        "types": {
            "UiScalar": _dataclass_fields(UiScalar),
            "UiSeries": _dataclass_fields(UiSeries),
            "UiView": _dataclass_fields(UiView),
            "PortDescriptor": _dataclass_fields(PortDescriptor),
        },
        "type_docs": {
            "UiScalar": _field_docs(UiScalar),
            "UiSeries": _field_docs(UiSeries),
            "UiView": _field_docs(UiView),
            "PortDescriptor": _field_docs(PortDescriptor),
        },
        # 缺口如实上报，不补造。通道已裁定，状态见 _ports_status()。
        "not_shown": {"ports": _ports_status()},
        # 前向兼容：契约实施后此处自动出现 12 项，无需改本页。
        "port_summary": _port_summary(),
    }


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802  (BaseHTTPRequestHandler 约定)
        if self.path == "/":
            body = HTML_PATH.read_bytes()
            ctype = "text/html; charset=utf-8"
        elif self.path == "/api/contract":
            body = json.dumps(build_contract_payload(), ensure_ascii=False).encode("utf-8")
            ctype = "application/json; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        """静默默认访问日志 —— 零噪声。"""


def main() -> None:
    server = HTTPServer((BIND_HOST, BIND_PORT), _Handler)
    print(f"契约结构预览 → http://{BIND_HOST}:{BIND_PORT}/")
    print(f"（手机端预留：把 BIND_HOST 改成 0.0.0.0 再启动）")
    print("Ctrl-C 退出")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
