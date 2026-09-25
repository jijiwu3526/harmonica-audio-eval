# COMP-C3 · downstream.md

> 下行视图 / Generation Instruction（宪章 §14.2）
> 面向：负责 C3 的实现智能体
> 上游：`upstream.md`（本目录）· `contract.py` · `profile.py`

---

## 你负责的文件

```text
harmonica_eval/algorithms/__init__.py   包出口（只 re-export，★ 不做算法注册）
harmonica_eval/algorithms/pitch.py      音准对比
harmonica_eval/algorithms/timing.py     节奏对比
harmonica_eval/algorithms/dynamics.py   力度对比
```

★ `__init__.py` 的当前职责是**只 re-export 三个名字**：
`Registry` / `PluginSpec` / `InputRequirement`（`__all__` 恰好这 3 项）。
★ **注册发生在 C1 的装配点**，不是在这里 —— 见下方「`__init__.py`」小节。

## 铁律（违反即驳回）

1. **禁止 import** `core` 内部模块 / `host` / `cockpit`
   （只能 import `..contract`）
2. **禁止请求 Core 生成数据**。数据面是只读且封闭的；
   需要额外数据就**从 `pcm.mapped.*` 自己算**
3. **禁止返回教学结论**（"你这里吹得太急了"）。只到数值层
4. 失败**也必须返回** `AlgorithmResultEnvelope`，不许抛异常穿透到 C1

## 最重要的一条：时间轴不能搞错

`SPEC.md` §5.5 要求两轴分离。**拿错轴是构造性错误，不是精度问题**：

| 指标类型 | 必须用哪条轴 | 用错的后果 |
| --- | --- | --- |
| **节奏**（起音偏差/抢拖） | `pcm.mapped.practice`（REFERENCE） | 用 warped 轴 → 抢拍拖拍**被抹掉**，永远报 0 |
| 音准 / 力度 | **按音配对**（见下） | 按帧相减 → 把时间错位误算成音准差 / 力度差 |

`UiSeries.timeline_basis` 字段就是为此存在的。**每条输出曲线都要声明自己在哪条轴上。**

★★ **MOLD BREAK 修正（两轴分离不足以表达音准/力度）★★

上表原写作「音准/力度用 `pcm.warped.practice`（WARPED）」。**这条约束无法满足。**

原因：`rms.reference` / `rms.practice` 在 `profile.py` 里都被声明为 REFERENCE 轴，
而数据面里**唯一**的 WARPED 端口是 `pcm.warped.practice` —— **没有 WARPED 轴的 rms**。
音准侧同理：`pitch.reference` / `pitch.practice` 声明的是 REFERENCE 轴，
`TimelineBasis.REFERENCE` 的含义是「保留源时间、未被时间归一化」，
**它不蕴含「两侧帧号一一对应」**（详见 `pitch.py` 的
`compare_pitch_curves` 长注记）。两个独立盲审模型各自报告了这个冲突。

真正的错误在于**用「时间轴」当「按音对齐」的代理**：
- 音准/力度要的不是「换一条轴」，而是**「第 n 个音对第 n 个音」**
- 用轴表达这件事，既丢失了逐音索引，又引入了无法满足的端口要求

**正确机制：按音配对。** 两侧各自有 `notes.reference` / `notes.practice`
提供逐音索引（`FIELD_LAYOUTS["notes"]` = `("onset_sec","f0_hz","rms")`），
用各自音内的帧区间取音高/能量，再一一配对。
这样「何时吹」被排除的方式是**按音聚合**，而不是**换一条时间轴**。

★ **`AXIS` 常量已从 `dynamics.py` 删除** —— 它编码的是一条错误的约束。
★ 只有 `timing.py` 保留 `AXIS = TimelineBasis.REFERENCE`，因为它确实需要那根轴。

---

## 各文件规格

### `__init__.py`

- **只 re-export**：`Registry` / `PluginSpec` / `InputRequirement`，`__all__` 恰好这 3 项
- **不保留中央算法清单常量**（旧 `ALGORITHMS` / `PAYLOAD_SCHEMAS` 已删除）
- **不在这里注册插件** —— `register` 发生在 `algorithms/bootstrap.py`（见下）
- ★ **装配根的物理位置已裁定**（`GC-204-08` CLOSED，方案甲，2026-09-24）：
  唯一物理装配根是 `harmonica_eval/algorithms/bootstrap.py`（Build Instruction：`FILE-206-v1.md`）——
  它是全系统**唯一** import 具体算法模块的位置，产出已装配 `Registry`；
  `HostApp` 只接收该 Registry，自身不 import 具体算法。
  ★ 各算法模块**只导出常量与纯函数**，注册序列由 bootstrap 集中声明（端口需求也是，见 `ALGORITHM_INPUTS`）。
- 每个 `PluginSpec` 至少含：`algorithm_id` / `algorithm_version` / `required_inputs` / `optional_inputs` / `entry`
  （★ 2026-09-24 负责人 BLOCK-4 裁定：原名 `plugin_id` / `version` 已改名为
  `algorithm_id` / `algorithm_version`，与 `AlgorithmResultEnvelope` 的身份字段对齐）
- `required_inputs` 声明的端口必须是 `profile.PORTS` 的子集，否则该算法启动即 `INCOMPATIBLE`

### `pitch.py` — 音准

| 项 | 内容 |
| --- | --- |
| 消费端口 | `pitch.reference` · `pitch.practice` · `notes.reference` · `notes.practice` |
| 对齐方式 | **按音配对**（两侧各自用 `notes.*` 的逐音索引，再一一对应） |
| 曲线声明 | `timeline_basis=REFERENCE`（声明的是「保留源时间」，**不是**「帧号对齐」） |

必须产出的量：
- 逐音音高误差（音分）
- **走音比例**：误差超过阈值的音占比
- 中位绝对误差

**阈值来源**：`≤50 音分`（规格 §7）。这是**稳定音**的判据。
只在 voiced 且有足够时长的音上计算；短于 150 ms 的音**不参与统计**（估计不可靠）。

**禁止 chroma 化**：chroma 八度不变，会把差一个八度的错音判成正确。

### `timing.py` — 节奏

| 项 | 内容 |
| --- | --- |
| 消费端口 | `pcm.mapped.reference` · `pcm.mapped.practice` · `notes.reference`（参考侧起音）
| 时间轴 | **REFERENCE（强制）** · **不读 `warp_path`、不读任何 WARPED 端口** |

必须产出的量：
- 逐音起音偏差（**秒**，带符号：正=拖，负=抢）——payload 键 `per_note_onset_sec`，`unit="seconds"`
  （★ 负责人裁定：timing 链路统一用 seconds；词表 `UNITS_VOCABULARY` 不含 `ms`，
  用 `unit="ms"` 会被 `runtime.validate_result` 拒绝）
- 偏差的中位数与离散度（`median_onset_sec` / `spread_sec`）
- 抢拍/拖拍比例（`early_ratio` / `late_ratio` / `on_time_ratio`）

**这是全系统唯一必须用 REFERENCE 轴的算法。** 两侧起音时刻分别从 `notes.reference` / `notes.practice` 取，
练习侧从 `pcm.mapped.practice` 的起音检测取——**两者都在源时间轴上**，不可换轴。

### `dynamics.py` — 力度

| 项 | 内容 |
| --- | --- |
| 消费端口 | `rms.reference` · `rms.practice` · `notes.reference` · `notes.practice` |
| 对齐方式 | **按音配对**（用各自音内的帧区间取 RMS，再一一对应） |
| 曲线声明 | `timeline_basis=REFERENCE` |

必须产出的量：
- 逐音能量差（dB）
- 能量差的离散度（σ）

**单位必须是 dB**，不是线性振幅——线性差的数值不可解释。

---

## 结果信封

每个算法返回 `contract.AlgorithmResultEnvelope`：

```text
algorithm_id       算法标识
algorithm_version  版本
status             'OK' | 'DEGRADED' | 'INCOMPATIBLE' | 'FAILED'
required_ports     声明需要的端口（仅用于兼容性检查）
consumed_ports     实际读取了哪些端口（用于证据追溯）
payload            自描述的 Sequence[UiScalar | UiSeries]
error_code         失败或不兼容时的错误码
elapsed_sec        耗时
coverage           覆盖比例（DEGRADED 至少配合 coverage 或 warnings 给出证据）
warnings           人可读告警元组
```

**`consumed_ports` 只用于追溯，绝不反向触发 Core 生成数据。**

---

## 交付前自检

- [ ] 4 个文件都有 `FILE-ID` 现场铭牌（9 字段完整）
- [ ] 所有函数体只有 `raise NotImplementedError("SHELL: FILE-0NN 待注入实现")`
- [ ] 无 `pass` / `...` / `return None` / 控制流
- [ ] `algorithms/` 未 import `core`/`host`/`cockpit`
- [ ] 每条输出曲线都声明了 `timeline_basis`
- [ ] 节奏算法用的是 REFERENCE 轴，且**未读 `warp_path`**
- [ ] 音准/力度算法是**按音配对**，不是按帧相减、也不是换轴
- [ ] 音准算法**未**做 chroma 化
- [ ] `python3 -c "import harmonica_eval.algorithms"` 成功
- [ ] `python3 -c "from harmonica_eval.algorithms import Registry, PluginSpec, InputRequirement"` 成功
