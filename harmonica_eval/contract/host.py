'''
FILE-ID: FILE-014
COMPONENT: COMP-CONTRACT（跨组件契约层）
SPEC: COMPONENTS.md@v2 §4.1 · §7

ROLE:
    CONTRACT-HOST-v1 的操作签名声明。**纯 Protocol，无实现**。

INTENT:
    把「C1 能对 C2 说什么」钉死为 7 个操作，从而获得三个结构性保证：
      1. C2 的接口极小（深组件）
      2. 算法执行的编排权明确属于 C1
      3. 依赖方向可自动检查（core/ 不得 import algorithms/）

MUST:
    - 只声明 7 个操作，不多不少
    - 每个操作写明前置条件、后置条件、失败后果
    - 明确列出**禁止出现**的操作（见下 FORBIDDEN）

MUST NOT:
    - 出现 align() / fft() / generate_pitch_input() / prepare_for_*()
      / generate_plugin_requirement() 这类"算法泄漏进 Core"的操作
      —— 它们的存在即意味着 Core 获得了算法知识，深组件被破坏
    - 让 C1 通过句柄访问 C2 内部符号

INPUT:
    （无）

OUTPUT:
    HostContract（Protocol，7 个操作）

BUILD-INSTRUCTION:
    .spec/build/FILE-014-v1.md

DEPENDS-ON-OC1:
    **部分依赖。** 决定的 5 个操作与数据面形态无关；
    但 acquire_surface() 的**返回类型**（SurfaceHandle 的具体形态）
    取决于 OC1，故此处只以 Protocol 占位，不定义其结构。
'''

from __future__ import annotations

from typing import Protocol

from .session import SessionState


class HostContract(Protocol):
    """C1 → C2 的全部对话能力。

    实现者：COMP-C2 Audio Core。
    调用者：COMP-C1 Framework / Host。
    """

    # ── 生命周期 ────────────────────────────────────────────────

    def create_session(self, profile_version: str) -> str:
        """创建一个分析会话，返回 session_id。

        profile_version 必须显式传入 —— 没有它，「同一对输入」不成立
        （数据面内容是 (reference, practice, profile_version) 的函数）。
        """
        ...

    def set_reference(self, uri: str) -> None:
        """登记参考演奏。不触发解码或计算。"""
        ...

    def set_practice(self, uri: str) -> None:
        """登记学习者演奏。不触发解码或计算。"""
        ...

    def destroy_session(self, session_id: str) -> None:
        """销毁会话并释放全部资源。

        之后任何使用旧句柄的行为都是 ContractViolation。
        """
        ...

    # ── 构建 ────────────────────────────────────────────────────

    def build_surface(self, session_id: str) -> None:
        """构建并 Seal 数据面。

        前置：两段资产均已登记（状态 == INPUT_READY）。
        后置：状态 == DATA_READY，数据面不可变。
        失败：抛 CoreBuildError，状态 → FAILED，**不得部分发布**，
              资源全部释放，且**未触发任何算法**。

        注意：本操作**不接收任何算法信息**。它不知道谁会来读。
        """
        ...

    # ── 观察 ────────────────────────────────────────────────────

    def status(self, session_id: str) -> SessionState:
        """返回会话状态。

        **只返回 SessionState 的六个值之一**；C2 的内部阶段
        （INGESTING / ALIGNING / MATERIALIZING / …）不得外泄。
        """
        ...

    # ── 取用 ────────────────────────────────────────────────────

    def acquire_surface(self, session_id: str) -> object:
        """取得数据面的只读访问句柄。

        前置：状态 == DATA_READY，否则 ContractViolation。
        返回：一个实现 CONTRACT-ALGORITHM-DATA-v1 的句柄
              （**具体形态取决于 OC1，此处不定义**）。
        所有权：句柄有效期至 destroy_session。
        """
        ...


# ─────────────────────────────────────────────────────────────────────
# 禁止出现的操作（作为可执行的检查清单，供 Inspector General 使用）
# ─────────────────────────────────────────────────────────────────────

FORBIDDEN_OPERATIONS: tuple[str, ...] = (
    "align",
    "fft",
    "stft",
    "compute_pitch_input",
    "generate_pitch_input",
    "generate_plugin_requirement",
    "prepare_for_pitch",
    "prepare_for_timing",
    "register_algorithm",
    "list_algorithms",
)
"""CONTRACT-HOST-v1 上**绝不允许**出现的方法名。

判据：若 C1 需要调用其中任何一个，说明编排权或算法知识泄漏进了 Core。
出现即视为契约违规（宪章 §47.6 Silent Contract Mutation）。
"""
