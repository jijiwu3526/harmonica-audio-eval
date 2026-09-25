# COMP-C2 · downstream.md

> 下行视图 / Generation Instruction（宪章 §14.2）
> 面向：负责 C2 的实现智能体
> 上游：`upstream.md`（本目录）· `contract.py` · `profile.py`

---

## 你负责的文件

```text
harmonica_eval/core/__init__.py    包出口
harmonica_eval/core/ingest.py      解码 → 单声道 → 44100Hz → float32
harmonica_eval/core/align.py       低分辨率对齐 → warp_path
harmonica_eval/core/features.py    音高曲线 + RMS 包络 + chroma + 逐音摘要
harmonica_eval/core/surface.py     按 profile 预生成全部端口 + Seal + 清单
harmonica_eval/core/api.py         门面：CONTRACT-HOST-v1 的 7 个操作
```

## 铁律（违反即驳回）

1. **禁止 import** `host` / `algorithms` / `cockpit`（任何形式，含延迟 import）
2. **禁止**出现算法概念（音准算法、节奏算法、力度算法）
   - 端口名 `pitch.reference` 是**数据**名，允许
   - `compute_pitch_for_algorithm()` 这类是**算法**名，禁止
3. **端口清单由 `profile.PORTS` 驱动**，不得硬编码端口名列表
4. **`read()` 必须无副作用**：不触发计算、不会失败于"算不出来"
5. `build_surface()` 是**一次性预生成**，不是惰性求值

## 为什么是预生成（负责人裁定，不可推翻）

不要把 Core 造成"按算法要求现算数据"的服务。理由：

> 惰性计算要活下来，**必须**定义一套协商协议
> （特征声明→解析→版本→缓存失效→失败语义）。
> 一旦有了那套协议，**Core 的外部接口就成了插件需求的函数**——
> 这正是「深组件」要消灭的东西。

**所以**：Seal 时数据面里已有算法要的一切。算法若需额外数据，
**从 PCM 自己算**（`pcm.mapped.*` 永远在数据面里），不许要求 Core 增加端口。

---

## 各文件规格

### `ingest.py`

| 项 | 内容 |
| --- | --- |
| 输入 | 一个文件路径（wav/flac/mp3…） |
| 输出 | 标准化 PCM：mono / 44100 Hz / float32 |
| 参数 | `profile.AUDIO` |
| 失败 | `INPUT_UNREADABLE` / `INPUT_TOO_SHORT` / `INPUT_SILENT` → 抛 `CoreBuildError` |

必须做：解码、下混单声道、重采样到 44100、转 float32。
必须检查时长在 `[min_duration_sec, max_duration_sec]`，**超出则拒绝，不静默截断**。
必须检查非静音（RMS 低于阈值 → `INPUT_SILENT`）。

**不许**归一化音量（会破坏力度信息）、不许去噪、不许做任何增强。

### `align.py`

| 项 | 内容 |
| --- | --- |
| 输入 | 参考 PCM + 练习 PCM |
| 输出 | `warp_path`：`int32[N, 2]`，每行 `(参考帧索引, 练习帧索引)` |
| 参数 | `profile.ALIGN` |

必须做：算低分辨率 chroma（`hop_length=2048`）→ DTW → 回溯路径。

**关键约束（实测得来，别改）**：
- `hop_length` **不得**小于 2048。实测 120 s 音频：hop=512 → DTW 代价矩阵 **855 MB**；hop=2048 → **53 MB**（降 16×，平方反比）
- 代价矩阵是 **float64**（librosa 行为），故占用是 `N²×8B`，不是 4B
- `global_constraints=True` **不减少**矩阵分配，只约束路径、降低耗时
- 得到路径后**立即释放**代价矩阵（不要返回它、不要存起来）
- 必须验证路径**单调**（参考索引单调不减）；违反 → `ALIGNMENT_UNRECOVERABLE`
- 无法建立有效映射时 → 抛 `ALIGNMENT_UNRECOVERABLE`，
  **严禁**静默退化为"逐点硬比"（宪章 §5.6）

### `features.py`

生成四个端口族：`pitch.*` / `rms.*` / `chroma.lowres.*` / `notes.*`（各自成对）。
参数见 `profile.MATERIALIZE`。

| 输出 | 形状 | 说明 |
| --- | --- | --- |
| `pitch.*` | `(frame, field)` | field = `[f0_hz, voiced, confidence]`；未发声帧 f0 置 0 且 voiced=0 |
| `rms.*` | `(frame,)` | 逐帧 RMS 能量 |
| `chroma.lowres.*` | `(frame, 12)` | 仅供对齐与复现，**明确不作评分依据**（chroma 八度不变） |
| `notes.reference` / `notes.practice` | `(note, field)` | field = `[onset_sec, f0_hz, rms]`；逐音摘要（两侧对称） |

**音高必须绝对音高，不得 chroma 化。** 实测：采样率 22.05 kHz 会把 D5 判成 D4
（恰好 −1200 音分），故必须按 `profile.AUDIO.sample_rate` 运行，且**不得**降采样。

### `surface.py`

- 按 `profile.PORTS` **穷举**生成全部 12 个端口
- 生成后 **Seal**：所有数组 `setflags(write=False)`
- 计算每个端口的 `content_hash`（用于同 build 回归断言）
- 产出 `SurfaceManifest`
- 实现 `AlgorithmDataContract`（`manifest()` / `read()`）

**`read()` 语义**：纯查表。
- `time_range=None` → 整段
- 端口不存在 → 抛 `ContractViolation`，**不得**返回空数组
- 返回 `BufferView`，其 `data` 必须不可写

### `api.py`

实现 `contract.HostContract` 的 **7 个操作**，不多不少：

```text
create_session / set_reference / set_practice / build_surface
status / acquire_surface / destroy_session
```

**正常流程状态单调推进**：`CREATED → INPUT_READY → BUILDING → DATA_READY`，
不跳过 `DATA_READY`；任一状态可 → `FAILED`，结束 → `CLOSED`。
`CANCEL` / `RESET` 是管理操作，允许回退到稳定态。
**C2 不负责会话状态机，此处为越界描述；状态编排由 C1 负责。**

`status()` **只返回 `SessionState` 的六个值之一**；内部阶段
（INGESTING / ALIGNING / BUILDING_PORTS…）**不得外泄**。

`build_surface()` 失败时：状态 → `FAILED`，**不得部分发布**，
资源全部释放，且**未触发任何算法**。

---

## 交付前自检

- [ ] 6 个文件都有 `FILE-ID` 现场铭牌（9 字段完整）
- [ ] 所有函数体只有 `raise NotImplementedError("SHELL: FILE-0NN 待注入实现")`
- [ ] 无 `pass` / `...` / `return None` / 控制流
- [ ] `core/` 未 import `host`/`algorithms`/`cockpit`
- [ ] 未定义 `FORBIDDEN_OPERATIONS` 中的任何方法名
- [ ] `python3 -c "import harmonica_eval.core"` 成功
