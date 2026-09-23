# COMP-C1 · downstream.md

> 下行视图 / Generation Instruction（宪章 §14.2）
> 面向：负责 C1 的实现智能体
> 上游：`upstream.md`（本目录）· `contract.py` · `profile.py`

---

## 你负责的文件

```text
harmonica_eval/host/__init__.py   包出口
harmonica_eval/host/app.py        生命周期 + 装配 + 编排（全系统唯一编排点）
```

## 铁律（违反即驳回）

1. **C1 不做任何信号处理。** 不许出现 fft / pyin / stft / dtw / 重采样。
   若你需要"算一下"，说明该逻辑属于 C2 或 C3。
2. **编排权只能在这里。** C2 不知道有哪些算法，C3 不知道彼此存在——
   把它们接起来是 C1 的**唯一**理由。
3. C1 是**唯一**允许同时 import core + algorithms 的地方。

## 为什么 C1 必须存在（否则会被当成多余的一层）

去掉 C1 后必然发生两件事：

- C2 得知道有哪些算法 → **深组件被破坏**，Core 变成插件需求的函数
- 或者 C4 直接调 C2/C3 → **界面进入计算路径**，UI 崩溃会污染数据面

所以 C1 的职责是**具体的**：持有会话、驱动状态机、调算法、归一化失败、
产出投影。它不是转发层。

---

## 文件规格

### `app.py`

这一个文件承担五种职责，按顺序实现：

#### ① 生命周期

持有 C2 的 `HostContract` 实现，驱动状态机：

```text
create_session(profile_version) → 持有 session_id
set_reference(uri) / set_practice(uri) → 登记输入
build_surface() → 触发预生成（C2 侧）
destroy_session() → 释放
```

**状态机约束**：单调推进，不可回退，不可跳过 `DATA_READY`。
算法**只能**在 `DATA_READY` 下触发；其他状态调用 → 抛 `ContractViolation`。

#### ② 装配（composition root）

C1 是**唯一**知道"有哪些实现"的地方：
- 实例化 C2 的具体实现
- 从 `algorithms.ALGORITHMS` 读取算法注册表
- 把数据面句柄交给各算法

**C2 不得知道算法的存在；C3 不得知道彼此存在。**
这个约束的机械验证方式：`core/` 不 import `algorithms/`（`tools/verify_shell.py` 会检查）。

#### ③ 编排

对每个算法：
1. **兼容性检查**：`required_ports` 是否都在 `manifest.ports` 里？
   - 缺失 → 该算法 `INCOMPATIBLE`，**其余算法照常运行**
   - **绝不**因为某算法缺数据就去让 C2 生成
2. 调用算法，传入数据面句柄
3. 校验返回的 `AlgorithmResultEnvelope`（schema 合法性）
4. 归一化失败：算法抛异常 → 捕获 → 转成 `ALGORITHM_FAILED` 信封
5. 收集结果，**单个算法失败不影响其他**

#### ④ 失败归一化

把 `HarmonicaError` 转成用户可见的错误信息。
必须区分：

| 情况 | 数据面 | 其他算法 |
| --- | --- | --- |
| 构建失败 | **不存在** | 不启动 |
| 算法要求未知端口 | 有效 | 正常 |
| 算法崩溃 | 有效 | 正常 |
| **算法死循环** | 有效 | **会卡住（v0.1 已知缺口，无超时机制）** |

#### ⑤ 投影生成

把结果转成 `UiView`（`contract.py`）。

**必须下采样**（宪章 §44.12：人类不得面对几千个文件/几十万数据点）。
投影要求：
- 时间序列降到**可绘制的点数**（建议 ≤ 2000 点/条）
- 每条 `UiSeries` **必须声明 `timeline_basis`**
- `UiScalar` **只陈述数值与单位，不下教学结论**

---

## 与 C4 的边界

C1 通过 `UiProjectionPort`（两个操作：`snapshot()` / `submit()`）与 C4 通讯。

`submit(command)` 收到 `UiCommand` 后必须**校验**：
- `SET_REFERENCE` / `SET_PRACTICE`：仅在 `CREATED`/`INPUT_READY` 下合法
- `BUILD_SURFACE`：仅在 `INPUT_READY` 下合法
- `RUN_ALGORITHMS`：仅在 `DATA_READY` 下合法
- 状态不合法 → **拒绝**，不改状态（不许"尽力而为"）

**C4 不能凭界面发明内核能力**——`UiCommandKind` 只有 6 个值，这是硬边界。

---

## 交付前自检

- [ ] 2 个文件都有 `FILE-ID` 现场铭牌（9 字段完整）
- [ ] 所有函数体只有 `raise NotImplementedError("SHELL: FILE-0NN 待注入实现")`
- [ ] 无 `pass` / `...` / `return None` / 控制流
- [ ] `host/` **未**出现任何 DSP 调用（fft/pyin/stft/dtw/resample）
- [ ] 兼容性检查是**单向**的（只判断有无，不触发生成）
- [ ] 单算法失败不影响其他算法
- [ ] 投影已下采样，且每条曲线声明了 `timeline_basis`
- [ ] `python3 -c "import harmonica_eval.host"` 成功
