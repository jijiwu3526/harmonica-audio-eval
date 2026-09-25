'''
FILE-ID:      FILE-104
COMPONENT:    COMP-C2 Audio Core
SPEC:         contract.AlgorithmDataContract · profile.PORTS · COMPONENTS.md@v2 §4.2

ROLE:
    把各模块产出的数据装配成一个**自描述、只读、已 Seal** 的数据面，
    并实现 CONTRACT-ALGORITHM-DATA-v1 的两个操作（manifest / read）。

INTENT:
    这是「深组件」的兑现处：算法只见 manifest + read 两个操作，
    **看不见 Core 内部的任何模块、DAG、缓存或存储策略**。
    Core 因此可以在不破坏任何算法的情况下重组内部实现。

MUST:
    - 由 profile.PORTS 驱动生成（穷举），不得硬编码端口名
    - Seal：所有数组 setflags(write=False)，Seal 后不可变
    - 为每个端口计算 content_hash（供同 build 回归断言）
    - read() 是**纯查表**：无副作用、不会失败于「算不出来」
    - 时长/尺寸校验：总字节超过 profile.BUDGET.max_surface_bytes → 构建失败

MUST NOT:
    - 暴露可写视图（writeable 必须为 False）
    - 在 read() 里触发任何计算（那会让 Core 变成算法需求的函数）
    - 端口不存在时返回空数组（必须抛 ContractViolation —— 空数组冒充成功
      是静默降级，违反宪章 §5.6）
    - 允许 Seal 后追加端口

INPUT:
    reference: float32 mono PCM
    practice:  float32 mono PCM
    sample_rate: int
    warp_path: int32[N, 2]

OUTPUT:
    Surface —— 实现 AlgorithmDataContract 的只读对象

BUILD-INSTRUCTION:
    .spec/build/FILE-104-v1.md
'''

from __future__ import annotations

import hashlib
import math
import types
from typing import Callable, Mapping

import numpy as np
import numpy.typing as npt

from .. import profile
from ..contract import (
    AlgorithmDataContract,
    AudioFormat,
    BufferView,
    ContractViolation,
    CoreBuildError,
    ErrorCode,
    FIELD_LAYOUTS,
    PortDescriptor,
    SurfaceManifest,
)
from .align import align
from .features import (
    materialize_chroma,
    materialize_notes,
    materialize_pitch,
    materialize_rms,
)


# ═════════════════════════════════════════════════════════════════════
# §4.0 冻结常量（实现必须在模块顶层定义，数值写死）
# ═════════════════════════════════════════════════════════════════════

# ★ 名单是单一真相源，在 profile（描述符侧与要求侧共用）。
# ★ 本模块名只作兼容别名 —— ★ 删掉它就等于让两侧口径漂移的入口。
_SAMPLE_RATE_FREE_PREFIXES: frozenset[str] = profile.SAMPLE_RATE_FREE_PREFIXES
_NOTES_FIELD_ONSET_SEC: int = 0        # FIELD_LAYOUTS["notes"] 中 "onset_sec" 的列号
_WARP_FIELD_REFERENCE_FRAME: int = 0   # FIELD_LAYOUTS["warp_path"] 中 "reference_frame"
_DURATION_ROUND_DIGITS: int = 6        # reference/practice 时长的小数位

CONTENT_HASH_MAGIC: bytes = b"harmonica-eval/surface/v1\x00"

# ★ 导入时核验列号常量与 FIELD_LAYOUTS 对得上（§4.0 硬要求）
assert FIELD_LAYOUTS["notes"][_NOTES_FIELD_ONSET_SEC] == "onset_sec"
assert (
    FIELD_LAYOUTS["warp_path"][_WARP_FIELD_REFERENCE_FRAME] == "reference_frame"
)


# ═════════════════════════════════════════════════════════════════════
# §4.1 派发表：结构键 → 真实生产者（键不得是端口 id 字面量）
# ═════════════════════════════════════════════════════════════════════

Key4 = tuple[str, str, tuple[str, ...], str]


def _key(spec) -> Key4:
    """从 PortSpec 取结构键。键取自字段，不是端口名字面量。

    ★ `timeline_basis` 取 `.value`（`'REFERENCE'`），**不是** `str()`
    （那是 `'TimelineBasis.REFERENCE'`）—— 用错会让派发表键集合不匹配。
    """
    return (
        spec.produced_by,
        spec.units,
        tuple(spec.dimensions),
        spec.timeline_basis.value,
    )


def _forward(side_samples: npt.NDArray, _spec) -> npt.NDArray:
    """core.surface 派发的 REFERENCE 侧：纯转发入参，零计算。"""
    return side_samples


def _warp_by_index(
    reference: npt.NDArray,
    practice: npt.NDArray,
    warp_path: npt.NDArray,
) -> npt.NDArray:
    """按 warp_path 把练习样本索引重排为参考长度的 WARPED 侧（非重采样）。

    口径严格取自 FILE-104 §4.4：
      - 输出长度 = ``len(reference)``；
      - 第 0 列 ``reference_frame`` 只用于在 warp_path 中选行；
      - 第 1 列 ``practice_frame`` 先换算为采样点索引，再索引 ``practice``。
    """
    hop = int(profile.ALIGN.hop_length)
    practice_col = FIELD_LAYOUTS["warp_path"].index("practice_frame")
    n_ref_samples = int(reference.shape[0])
    n_prac_samples = int(practice.shape[0])
    n_rows = int(warp_path.shape[0])
    if n_rows == 0 and n_ref_samples > 0:
        raise ContractViolation(
            code=ErrorCode.CORE_BUILD_FAILED,
            port_id="pcm.warped.practice",
            detail="warp_path is empty; warped length cannot be determined",
        )
    if n_prac_samples == 0 and n_ref_samples > 0:
        raise ContractViolation(
            code=ErrorCode.CORE_BUILD_FAILED,
            port_id="pcm.warped.practice",
            detail="practice side is empty; warped length cannot be determined",
        )

    # ★★ 越界必须【显式失败】，不得抛 numpy IndexError（§4.4 失败语义）★★
    # `practice_frame` 是【帧号】，被索引的 practice 是【采样点】序列；
    # 帧的起点 `帧号 * hop` 必须 < len(practice)，
    # 故合法帧号上界 = `(n_prac_samples - 1) // hop`。
    # ★ 缺这条校验时，越界会由 `practice[sample_j]` 抛 IndexError ——
    # ★ 那是「未校验」，不是「显式失败」。判据正是要抓这一条。
    #
    # ★★ 口径实证（2026-09-24）：n=3210572, hop=2048 → 上界 1567；
    #   而 align 特征矩阵实为 1569 帧、末帧索引 1568（起点 3211264 ≥ 3210572）。
    #   ★ 那多出来的帧是 librosa boundary='zeros' + padded=True 补出来的，
    #   ★ 其起点已越过真实音频末尾 —— 是【真越界】，不是公式口径差异。
    #   ★ 故本判据保持按采样点口径验；缺陷须在 align 侧修根因，不得放宽此处。
    max_practice_frame = (n_prac_samples - 1) // hop
    observed_max = int(warp_path[:, practice_col].max()) if n_rows > 0 else 0
    if observed_max > max_practice_frame:
        raise ContractViolation(
            code=ErrorCode.CORE_BUILD_FAILED,
            port_id="pcm.warped.practice",
            detail=(
                f"warp_path practice_frame {observed_max} exceeds max legal "
                f"frame {max_practice_frame} for {n_prac_samples} samples"
            ),
        )

    out = np.zeros(n_ref_samples, dtype=np.float32)
    for sample_i in range(n_ref_samples):
        ref_frame = min(sample_i // hop, n_rows - 1)
        practice_frame = int(warp_path[ref_frame, practice_col])
        sample_j = practice_frame * hop
        sample_j = min(max(sample_j, 0), n_prac_samples - 1)
        out[sample_i] = practice[sample_j]
    return out


PRODUCER_DISPATCH: Mapping[Key4, Callable] = types.MappingProxyType(
    {
        _key(spec): _forward
        for spec in profile.PORTS
        if spec.produced_by == "core.surface" and spec.timeline_basis.value == "REFERENCE"
    }
    | {
        _key(spec): _warp_by_index
        for spec in profile.PORTS
        if spec.produced_by == "core.surface" and spec.timeline_basis.value == "WARPED"
    }
    | {
        _key(spec): align
        for spec in profile.PORTS
        if spec.produced_by == "core.align"
    }
    | {
        _key(spec): materialize_pitch
        for spec in profile.PORTS
        if _key(spec)[1] == "hz"
    }
    | {
        _key(spec): materialize_rms
        for spec in profile.PORTS
        if _key(spec)[1] == "rms"
    }
    | {
        _key(spec): materialize_chroma
        for spec in profile.PORTS
        if _key(spec)[1] == "chroma"
    }
    | {
        _key(spec): materialize_notes
        for spec in profile.PORTS
        if _key(spec)[1] == "index" and tuple(spec.dimensions) == ("note", "field")
    }
)


def port_prefix(port_id: str) -> str:
    """端口前缀 = `port_id` 第一个点之前的部分。

    规格 §4.8：`pitch.reference` → `pitch`；`warp_path`（无点）→ 自身。
    """
    return port_id.split(".", 1)[0]


# ═════════════════════════════════════════════════════════════════════
# §4.2 build_descriptor
# ═════════════════════════════════════════════════════════════════════


def _content_hash(port_id: str, data: npt.NDArray) -> str:
    """§4.2 冻结的 content_hash 算法，逐字节照做，不得增删任何一次 update。"""
    h = hashlib.sha256()
    h.update(CONTENT_HASH_MAGIC)
    h.update(port_id.encode("utf-8"))
    h.update(str(data.dtype).encode("utf-8"))
    h.update(np.asarray(data.shape, dtype="<i8").tobytes())
    h.update(data.tobytes(order="C"))
    return h.hexdigest()


def build_descriptor(
    port_id: str,
    data: npt.NDArray,
    sample_rate: int,
) -> PortDescriptor:
    """为一个已生成的数据数组构造自描述头。

    字段来源逐项见 §4.2 表格。核心约束：
        shape 是**运行期实测值**（`data.shape`），严禁从 dimensions 反推
        schema_version 取 profile.PROFILE_VERSION，不写死字面量
        field_names 取自 contract.FIELD_LAYOUTS，不在本文件硬编码
    """
    spec = profile.PORT_INDEX[port_id]  # 不在 PORT_INDEX → KeyError（不捕获）

    # field_names 三条规则（按序判定，命中即停）
    dims = tuple(spec.dimensions)
    if len(dims) == 1:
        field_names: tuple[str, ...] = ()
    else:
        prefix = port_prefix(port_id)
        if prefix in FIELD_LAYOUTS:
            field_names = tuple(FIELD_LAYOUTS[prefix])
        else:
            raise ContractViolation(
                code=ErrorCode.CORE_BUILD_FAILED,
                port_id=port_id,
                detail="multi-dimensional port has no FIELD_LAYOUTS entry",
            )

    # sample_rate 两条规则（按序判定，命中即停）
    if port_prefix(port_id) in _SAMPLE_RATE_FREE_PREFIXES:
        sr_value = 0
    else:
        sr_value = int(sample_rate)

    return PortDescriptor(
        port_id=port_id,
        schema_version=profile.PROFILE_VERSION,
        element_type=str(data.dtype),
        dimensions=dims,
        shape=tuple(int(x) for x in data.shape),
        units=spec.units,
        field_names=field_names,
        timeline_basis=spec.timeline_basis,
        hop_length=int(spec.hop_length),
        sample_rate=sr_value,
        content_hash=_content_hash(port_id, data),
    )


# ═════════════════════════════════════════════════════════════════════
# §4.3 seal
# ═════════════════════════════════════════════════════════════════════


def seal(data: npt.NDArray) -> npt.NDArray:
    """把数组标记为只读，返回**同一对象**（不拷贝）。

    唯一一条语句 `setflags(write=False)`。幂等：已只读时重复调用不抛错。
    """
    data.setflags(write=False)
    return data


# ═════════════════════════════════════════════════════════════════════
# §4.4 generate_all_ports
# ═════════════════════════════════════════════════════════════════════


def generate_all_ports(
    reference: npt.NDArray,
    practice: npt.NDArray,
    sample_rate: int,
    warp_path: npt.NDArray,
) -> Mapping[str, npt.NDArray]:
    """按 profile.PORTS **穷举**生成全部端口数据。

    派发表用结构键 `(produced_by, units, dimensions, timeline_basis)`；
    中间量键是 `(结构键, side)` 二元组（BLOCK-10 更正：纯结构键会让
    练习侧覆盖参考侧，让 notes 静默拿到错侧的音高）。
    """
    if not profile.PORTS:
        return {}

    expected = set(profile.PORT_INDEX.keys())
    assert set(PRODUCER_DISPATCH) == {_key(s) for s in profile.PORTS}, (
        "PRODUCER_DISPATCH key set does not match profile.PORTS"
    )

    by_side = {"reference": reference, "practice": practice}
    # 中间量：键是 (结构键, side)
    buf: dict[tuple[Key4, str], npt.NDArray] = {}
    out: dict[str, npt.NDArray] = {}

    for spec in profile.PORTS:
        key = _key(spec)
        producer = PRODUCER_DISPATCH[key]

        if spec.produced_by == "core.surface":
            if spec.timeline_basis.value == "WARPED":
                # 输出以 reference 长度为准；practice_frame 只索引 practice。
                arr = _warp_by_index(reference, practice, warp_path)
            else:
                # 纯转发：零计算
                side = spec.port_id.rsplit(".", 1)[-1]
                arr = by_side[side]
        else:
            side = spec.port_id.rsplit(".", 1)[-1] if "." in spec.port_id else ""
            samples = by_side.get(side)
            if samples is None:
                # warp_path 没有侧别后缀，它同时要两侧
                arr = producer(reference, practice)
            else:
                hz_like = key[1] == "hz"
                chroma_like = key[1] == "chroma"
                rms_like = key[1] == "rms"
                note_like = key[1] == "index" and tuple(spec.dimensions) == (
                    "note",
                    "field",
                )
                if hz_like or chroma_like:
                    arr = producer(samples, sample_rate)
                elif rms_like:
                    arr = producer(samples)
                elif spec.timeline_basis.value == "WARPED":
                    # ★ pcm.warped.practice 走这里：它有 side 后缀，
                    #   所以进不了 :318 的 WARPED 分支（那是给 warp_path 这类
                    #   无侧别端口的）。但它仍需按 warp_path 重排索引，
                    #   调用形态是三参 (reference, practice, warp_path)。
                    arr = producer(reference, practice, warp_path)
                elif note_like:
                    # 中间量：同侧已产出的 pitch / rms（依赖顺序自检）
                    pkey = next(k for k in buf if k[1] == side and k[0][1] == "hz")
                    rkey = next(k for k in buf if k[1] == side and k[0][1] == "rms")
                    if pkey not in buf or rkey not in buf:
                        raise ContractViolation(
                            code=ErrorCode.CORE_BUILD_FAILED,
                            port_id=spec.port_id,
                            detail="intermediate quantity missing (dependency order)",
                        )
                    arr = producer(buf[pkey], buf[rkey], sample_rate)
                else:
                    arr = producer(samples, sample_rate)

        if not isinstance(arr, np.ndarray):
            raise ContractViolation(
                code=ErrorCode.CORE_BUILD_FAILED,
                port_id=spec.port_id,
                detail=f"producer returned {type(arr).__name__}, not ndarray",
            )
        if str(arr.dtype) != spec.element_type:
            raise ContractViolation(
                code=ErrorCode.CORE_BUILD_FAILED,
                port_id=spec.port_id,
                detail=f"dtype {arr.dtype} != profile {spec.element_type}",
            )
        if "." in spec.port_id and not spec.port_id.endswith("warp_path"):
            buf[(key, side)] = arr
        out[spec.port_id] = arr

    if set(out.keys()) != expected:
        raise ContractViolation(
            code=ErrorCode.CORE_BUILD_FAILED,
            port_id="",
            detail="generated port key set != profile.PORT_INDEX key set",
        )
    return out


# ═════════════════════════════════════════════════════════════════════
# §4.5 assert_budget
# ═════════════════════════════════════════════════════════════════════


def assert_budget(ports: Mapping[str, npt.NDArray]) -> int:
    """校验总字节不超过 profile.BUDGET.max_surface_bytes，返回总字节。

    精确口径：`sum(int(arr.nbytes))`。判定为**严格大于**。
    """
    total = 0
    for arr in ports.values():
        total += int(arr.nbytes)
    if total > profile.BUDGET.max_surface_bytes:
        # ★ FILE-104:671 冻结：total == 536870913 → 抛 `CoreBuildError`（见 §5）。
        # ★ 而 `CoreBuildError` 与 `ContractViolation` 【互不继承】——
        # ★   表面 code 都是 CORE_BUILD_FAILED，★ 但 `except` 分支不同，
        # ★   抛错类会让上层走错分支。
        # ★ 本函数是【构建期】校验（不在 Surface 的 read 路径上），
        # ★ 故按 §5「构建失败」语义抛 CoreBuildError。
        raise CoreBuildError(
            code=ErrorCode.CORE_BUILD_FAILED,
            port_id="",
            detail=(
                f"surface budget exceeded: {total} > "
                f"{profile.BUDGET.max_surface_bytes}"
            ),
        )
    return total


# ═════════════════════════════════════════════════════════════════════
# §4.6 Surface
# ═════════════════════════════════════════════════════════════════════


class Surface(AlgorithmDataContract):
    """只读数据面。实现 CONTRACT-ALGORITHM-DATA-v1 的**全部**能力。

    ★★★ 冻结要求：2 个操作 + 1 个状态属性 ★★★

    规格原文（.spec/build/FILE-003-v1.md:175）：

        「2 个纯查表操作（manifest() / read()）**+ 1 个只读状态属性
          `resolution`，不计入操作数**」

    ★★★ 关于 `resolution`：规格存在**两处矛盾** ★★★

    ```
    FILE-003-v1.md:175   「实现者：C2 产出的 Surface」
                        → 读作：Surface 应当实现它

    contract.py（AlgorithmDataContract 的 docstring）
                        「C2 的 Surface 不实现该属性；C3 的 runtime
                          薄适配器组合 C2 数据面与该只读视图后再交给单参 entry」
                        → 读作：Surface 不该实现它
    ```

    ★ ★ 这两条互斥，且都不是本文档能单方面裁定的：
    · 裁定「实现」→ 违反 contract.py 的边界说明
    · 裁定「不实现」→ 违反 FILE-003:175 的字面要求，且
      `Surface().resolution` 继续返回 None（Protocol 默认值）

    ★ ★ **已上报主代理请求裁定**。在裁定到达前，
    ★ ★ **本类不实现该属性**——理由：contract.py 的那段说明更具体
    ★ ★ （它讲清了「谁把 ResolutionView 交给插件」的机制，
    ★ ★ 而 FILE-003:175 只说「属性属于谁」，没说「值从哪来」）。
    ★ ★ 若裁定为「实现」，本类需增加一个构造期注入的 ResolutionView 槽位。
    """

    # `_data is None` 是唯一的失效哨兵：构造期 `data_map` 的合法类型是
    # Mapping；合法的空端口集是 `{}`，不会与 `None` 混淆。失效时清掉映射引用，
    # 让 stale 句柄不再持有全部端口数组。无需 generation：Surface 只由一次
    # build 产生，生命周期仅单向，且不存在重新激活路径。
    __slots__ = ("_manifest", "_data", "_resolution")

    def __init__(
        self,
        manifest_obj: SurfaceManifest,
        data_map: Mapping[str, npt.NDArray],
        resolution: object = None,
    ) -> None:
        object.__setattr__(self, "_manifest", manifest_obj)
        # ★★ 2026-09-25 修正（真实现缺陷，非判据过期）：
        #   FILE-104 §4.3 / INV-104-9 冻结「Seal 后不可追加端口」，
        #   而 seal() 只对**数组**做 setflags(write=False) —— data_map 这个
        #   dict 本身从未被封，实测 s._data["injected"] = … 竟然成功。
        #   ★ 数组只读 ≠ 容器只读：前者挡住改值，后者才挡住加端口。
        #   ★ 修法：types.MappingProxyType 封容器；数组的只读仍由 seal() 负责。
        #   ★ 精确成员语义不变 —— 已有端口照常可读，只是不能再加。
        object.__setattr__(self, "_data", types.MappingProxyType(dict(data_map)))
        object.__setattr__(self, "_resolution", resolution)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Surface is immutable after construction")

    def _invalidate(self) -> None:
        """使旧句柄不可读并解除其对端口数组的引用（幂等、内部专用）。"""
        if self._data is None:
            return
        object.__setattr__(self, "_data", None)

    def _assert_live(self) -> None:
        """读操作前的失效闸门。旧句柄不得继续暴露已释放的数据面。"""
        if self._data is None:
            raise ContractViolation(
                code=ErrorCode.INTERNAL_ERROR,
                detail="surface handle invalidated by destroy_session",
                component="COMP-C2",
            )

    def manifest(self) -> SurfaceManifest:
        """返回自描述清单，用于枚举端口并判断兼容性。

        ★ 返回的 `ports[*].shape` 是该端口实际数组的 `data.shape`
        （由 `build_descriptor` 填入），不是从 dimensions 推导的静态值。
        这正是「C1 向 C2 询问 shape」这条通道的载体 —— C1 无需新增方法。
        """
        self._assert_live()
        return self._manifest

    def read(
        self,
        port_id: str,
        time_range: tuple[float, float] | None = None,
    ) -> BufferView:
        """按键读取端口的（可选时间窗）只读视图。

        单位是秒，左闭右开 [t0, t1)；None ⇒ 整段。
        与帧坐标的换算由本实现负责（调用方不得自行乘除 hop）。
        端口不存在 → ContractViolation（绝不返回空视图冒充成功）
        会话已 destroy → 同样抛 ContractViolation（契约 INV-105-8）
        """
        self._assert_live()
        if port_id not in self._data:
            raise ContractViolation(
                code=ErrorCode.CORE_BUILD_FAILED,
                port_id=port_id,
                detail="port not in surface",
            )
        if self._manifest.sealed is False:
            raise ContractViolation(
                code=ErrorCode.CORE_BUILD_FAILED,
                port_id=port_id,
                detail="surface not sealed",
            )

        d = self._manifest.ports[port_id]
        arr = self._data[port_id]
        sr = int(self._manifest.audio_format.sample_rate)

        # ★ 端口时长上界：notes / warp_path 的末值可能远小于音频时长，
        # ★ 但**上界必须是音频时长**（空端口配满窗，让「没有音符」成为事实）
        dims = tuple(d.dimensions)
        note_like = "note" in dims
        warp_like = "warp_point" in dims
        if note_like and int(arr.shape[0]) > 0:
            col_onset = _NOTES_FIELD_ONSET_SEC
            upper = (
                float(np.nanmax(arr[:, col_onset]))
                if arr.shape[0] > 0
                else self._manifest.reference_duration_sec
            )
            upper = max(upper, self._manifest.reference_duration_sec)
        elif note_like:
            upper = self._manifest.reference_duration_sec
        elif warp_like:
            if int(arr.shape[0]) > 0:
                col_ref = _WARP_FIELD_REFERENCE_FRAME
                hop = int(profile.ALIGN.hop_length)
                upper = max(0.0, (int(arr.shape[0]) - 1) * hop / sr)
            else:
                upper = 0.0
        else:
            upper = float(
                max(
                    self._manifest.reference_duration_sec,
                    self._manifest.practice_duration_sec,
                )
            )

        if time_range is None:
            out = arr  # 不拷贝
        else:
            t0, t1 = time_range
            if not isinstance(t0, (int, float)) or not isinstance(t1, (int, float)):
                raise TypeError("time_range elements must be int or float")
            t0 = float(t0)
            t1 = float(t1)
            if t0 != t0 or t1 != t1:
                raise ContractViolation(
                    code=ErrorCode.CORE_BUILD_FAILED,
                    port_id=port_id,
                    detail="time_range contains NaN",
                )
            if t0 >= t1:
                raise ContractViolation(
                    code=ErrorCode.CORE_BUILD_FAILED,
                    port_id=port_id,
                    detail=f"zero or inverted window: [{t0}, {t1})",
                )
            if t0 < 0.0:
                raise ContractViolation(
                    code=ErrorCode.CORE_BUILD_FAILED,
                    port_id=port_id,
                    detail=f"negative t0: {t0}",
                )
            if t1 > upper:
                raise ContractViolation(
                    code=ErrorCode.CORE_BUILD_FAILED,
                    port_id=port_id,
                    detail=f"t1 {t1} exceeds port upper bound {upper}",
                )

            if note_like:
                # 行筛选：onset_sec ∈ [t0, t1)
                col = _NOTES_FIELD_ONSET_SEC
                mask = (arr[:, col] >= t0) & (arr[:, col] < t1)
                out = np.ascontiguousarray(arr[mask])
                out.setflags(write=False)
            elif warp_like:
                col = _WARP_FIELD_REFERENCE_FRAME
                hop = int(profile.ALIGN.hop_length)
                t = arr[:, col] * hop / sr
                mask = (t >= t0) & (t < t1)
                out = np.ascontiguousarray(arr[mask])
                out.setflags(write=False)
            elif "amplitude" in d.units:
                # 采样点网格：不需要 hop
                i0 = math.floor(t0 * sr)
                i1 = math.floor(t1 * sr)
                out = arr[i0:i1]  # 视图，不拷贝
            elif "frame" in dims:
                hop = int(d.hop_length)
                if hop <= 0:
                    raise ContractViolation(
                        code=ErrorCode.CORE_BUILD_FAILED,
                        port_id=port_id,
                        detail="frame port reached with hop_length <= 0",
                    )
                i0 = math.floor(t0 * sr / hop)
                i1 = math.floor(t1 * sr / hop)
                out = arr[i0:i1]  # 视图，不拷贝
            else:
                out = arr

        return BufferView(
            data=out,
            element_count=int(np.prod(out.shape)),
            element_type=str(out.dtype),
        )


# ═════════════════════════════════════════════════════════════════════
# §4.7 build_surface
# ═════════════════════════════════════════════════════════════════════


def build_surface(
    reference: npt.NDArray,
    practice: npt.NDArray,
    sample_rate: int,
    warp_path: npt.NDArray,
) -> Surface:
    """装配完整数据面并 Seal。

    步骤：校验输入（1–4）→ 生成全部端口（5）→ 校验预算（6）
        → 逐端口 Seal（7）→ 构造描述符与 manifest（8–10）→ 返回 Surface（11）

    **不得部分发布**：第 1–4 步的校验必须发生在生成之前，
    任何一步失败即抛错，数据面**不存在**。
    """
    # 1. 校验 sample_rate
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            detail=f"sample_rate must be positive int, got {sample_rate!r}",
        )
    if sample_rate != profile.AUDIO.sample_rate:
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            detail=(
                f"sample_rate {sample_rate} != profile "
                f"{profile.AUDIO.sample_rate}; resampling is forbidden"
            ),
        )
    # 2. 校验一维
    if reference.ndim != 1 or practice.ndim != 1:
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            detail="reference/practice must be 1-D (downmix happens in ingest)",
        )
    # 3. 校验 dtype
    if reference.dtype != np.float32 or practice.dtype != np.float32:
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            detail="reference/practice must be float32",
        )
    # 4. 校验 warp_path 形状
    if (
        warp_path.dtype != np.int32
        or warp_path.ndim != 2
        or warp_path.shape[1] != 2
    ):
        raise CoreBuildError(
            ErrorCode.CORE_BUILD_FAILED,
            detail="warp_path must be int32 with shape (N, 2)",
        )

    # 5–6. 生成 + 预算
    ports = generate_all_ports(reference, practice, sample_rate, warp_path)
    assert_budget(ports)

    # 7. 逐端口 Seal
    for spec in profile.PORTS:
        seal(ports[spec.port_id])

    # 8. 时长
    ref_dur = round(len(reference) / sample_rate, _DURATION_ROUND_DIGITS)
    prac_dur = round(len(practice) / sample_rate, _DURATION_ROUND_DIGITS)

    # 9. 描述符
    descriptors = {
        spec.port_id: build_descriptor(
            spec.port_id, ports[spec.port_id], sample_rate
        )
        for spec in profile.PORTS
    }

    # 10. manifest
    manifest_obj = SurfaceManifest(
        profile_version=profile.PROFILE_VERSION,
        audio_format=AudioFormat(
            sample_rate=int(sample_rate), channels=1, dtype="float32"
        ),
        reference_duration_sec=ref_dur,
        practice_duration_sec=prac_dur,
        ports=types.MappingProxyType(descriptors),
        sealed=True,
    )
    # 11. 返回
    return Surface(manifest_obj, ports)
