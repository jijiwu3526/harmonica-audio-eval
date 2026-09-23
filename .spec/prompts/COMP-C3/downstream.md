# COMP-C3 · downstream.md

> 下行视图 / Generation Instruction（宪章 §14.2）
> 面向：负责 C3 的实现智能体
> 上游：`upstream.md`（本目录）· `contract.py` · `profile.py`

---

## 你负责的文件

```text
harmonica_eval/algorithms/__init__.py   包出口 + 算法注册
harmonica_eval/algorithms/pitch.py      音准对比
harmonica_eval/algorithms/timing.py     节奏对比
harmonica_eval/algorithms/dynamics.py   力度对比
```

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
| 音准 / 力度 | `pcm.warped.practice`（WARPED） | 用 mapped 轴 → 把时间错位误算成音准错 |

`UiSeries.timeline_basis` 字段就是为此存在的。**每条输出曲线都要声明自己在哪条轴上。**

---

## 各文件规格

### `__init__.py`

- 定义**算法注册表**：`ALGORITHMS: tuple[AlgorithmSpec, ...]`
- **新增算法只改这个文件**（这是「换算法不改核心」的落点）
- 每个 `AlgorithmSpec` 至少含：`algorithm_id` / `version` / `required_ports` / `entry`
- `required_ports` 必须是 `profile.PORTS` 的子集，否则该算法启动即 `INCOMPATIBLE`

### `pitch.py` — 音准

| 项 | 内容 |
| --- | --- |
| 消费端口 | `pitch.reference` · `pitch.practice` · `pcm.warped.practice` |
| 时间轴 | WARPED（音准关心"吹了什么"，不关心"何时吹"） |

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
| 消费端口 | `pcm.mapped.reference` · `pcm.mapped.practice` · `notes.reference` · `warp_path` |
| 时间轴 | **REFERENCE（强制）** |

必须产出的量：
- 逐音起音偏差（毫秒，带符号：正=拖，负=抢）
- 偏差的中位数与离散度
- 抢拍/拖拍比例

**这是全系统唯一必须用 REFERENCE 轴的算法。** 参考侧起音时刻从 `notes.reference` 取，
练习侧从 `pcm.mapped.practice` 的起音检测取——**两者都在源时间轴上**，不可换轴。

### `dynamics.py` — 力度

| 项 | 内容 |
| --- | --- |
| 消费端口 | `rms.reference` · `rms.practice` · `pcm.warped.practice` |
| 时间轴 | WARPED |

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
status             'OK' | 'FAILED' | 'INCOMPATIBLE'
required_ports     声明需要的端口（仅用于兼容性检查）
consumed_ports     实际读取了哪些端口（用于证据追溯）
payload            结果本体（形状由算法自定）
error_code         失败时的错误码
elapsed_sec        耗时
```

**`consumed_ports` 只用于追溯，绝不反向触发 Core 生成数据。**

---

## 交付前自检

- [ ] 4 个文件都有 `FILE-ID` 现场铭牌（9 字段完整）
- [ ] 所有函数体只有 `raise NotImplementedError("SHELL: FILE-0NN 待注入实现")`
- [ ] 无 `pass` / `...` / `return None` / 控制流
- [ ] `algorithms/` 未 import `core`/`host`/`cockpit`
- [ ] 每条输出曲线都声明了 `timeline_basis`
- [ ] 节奏算法用的是 REFERENCE 轴
- [ ] 音准算法**未**做 chroma 化
- [ ] `python3 -c "import harmonica_eval.algorithms"` 成功
