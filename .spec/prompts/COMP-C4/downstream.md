# COMP-C4 · downstream.md

> 下行视图 / Generation Instruction（宪章 §14.2）
> 面向：负责 C4 的实现智能体
> 上游：`upstream.md`（本目录）· `contract.py`

---

## 你负责的文件

```text
harmonica_eval/cockpit/__init__.py   包出口
harmonica_eval/cockpit/app.py        开发者调试界面（Mac）
```

## 边界（负责人已裁定，不可自行扩大）

| | 产品化 UI（**禁止**） | C4（**允许**） |
| --- | --- | --- |
| 服务对象 | 终端用户（口琴学习者） | **开发者** |
| 运行环境 | 手机端成品 | **Mac 端** |
| 阶段 | 远期产品 | v0.1 调试期 |

**平台路线**：Mac 端先行 → 核心调试完毕 → 再移植手机端。

## 铁律（违反即驳回）

1. **禁止 import** `core` / `algorithms`（任何形式）
   - C4 只见 C1 给的投影，**永远看不到数据面**
2. **禁止**做 DSP、禁止读文件、禁止解释算法内部
3. **禁止**持有音频缓冲或持久状态（纯视图）
4. **禁止**把 C4 做成验收工具（宪章 §36：验证是角色，不是产品件）

## 为什么 C4 必须能缺席

删除 C4 后，C1/C2/C3 必须仍能无头跑通（Invariant F）。
这不是美学要求，而是**架构检验**：如果删掉界面系统就跑不了，
说明计算逻辑泄漏进了 UI。

**C4 是四个组件中唯一不被任何未决项阻塞的**——
因为它只见投影，不见数据面。

---

## 文件规格

### `__init__.py`

包出口。声明 C4 对外只暴露一个入口点（供 `__main__.py` 选择性启动）。

### `app.py`

承担三件事：

#### ① 界面入口

启动一个**本地**开发者界面。UI 框架选择**留给实现者**，
但必须满足：
- 只在 Mac 本地运行（不监听公网）
- **可被删除而不影响内核**（不得被 C1/C2/C3 import）
- 不引入需要模型的依赖（本轮不做训练/推理）

#### ② 视图渲染（只读投影）

消费 `contract.UiView`，渲染：

| 元素 | 数据来源 |
| --- | --- |
| 状态显示 | `UiView.state` |
| 数值指标 | `UiView.scalars`（含单位与可选阈值） |
| 曲线 | `UiView.series`（**已下采样**） |
| 进度 | `UiView.progress` |
| 错误 | `UiView.error_code` / `error_detail` |

**渲染时不得重新计算任何东西。** 投影里没有的，就是不该显示的。

**画曲线时必须读 `UiSeries.timeline_basis` 并标注在图上**——
否则用户会把 warped 轴上的图当成真实时间，从而误读抢拍拖拍。

#### ③ 命令下发

通过 `UiProjectionPort.submit()` 发送 `UiCommand`：

```text
SET_REFERENCE / SET_PRACTICE / BUILD_SURFACE
RUN_ALGORITHMS / CANCEL / RESET
```

界面能表达的意图**仅此 6 种**。不许在界面里发明新能力
（例如"重新对齐""换个算法试试"——这些若需要，必须先在 C1/C3 侧定义）。

---

## 投影契约要点（`contract.py`）

```text
UiProjectionPort   只有两个操作：snapshot() / submit()
UiView             session_id / state / series / scalars / progress / error_*
UiSeries           key / label / t / values / unit / timeline_basis / source_port
UiScalar           key / label / value / unit / threshold
UiCommand          kind（6 种）+ payload
```

**C4 不得反向访问 C1/C2/C3 内部。** 唯一入口是 `UiProjectionPort`。

---

## 交付前自检

- [ ] 2 个文件都有 `FILE-ID` 现场铭牌（9 字段完整）
- [ ] 所有函数体只有 `raise NotImplementedError("SHELL: FILE-0NN 待注入实现")`
- [ ] 无 `pass` / `...` / `return None` / 控制流
- [ ] `cockpit/` **未** import `core` / `algorithms` / `host` 内部
- [ ] 未出现任何 DSP 调用
- [ ] 界面只表达 6 种命令，未发明新能力
- [ ] 曲线渲染会标注 `timeline_basis`
- [ ] `python3 -c "import harmonica_eval.cockpit"` 成功
