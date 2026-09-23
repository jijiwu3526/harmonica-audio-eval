# 计划书 —— 口琴双音频对比分析 · 空壳铸造

> 本文件是**执行计划**，不是规格。规格权威仍是 `SPEC.md`。
> 目的：让负责人一眼看懂「要造哪些文件、每个文件干什么、谁连谁」。

---

## 一、我要做什么（一句话）

造一个**完整但空的代码结构**：文件全在、职责全定、提示词全写，**一行实现都没有**。
审查通过后打 `CAST-FREEZE`，再派智能体把代码注入进去。

---

## 二、执行流程（7 步）

| 步 | 做什么 | 谁做 | 状态 |
| --- | --- | --- | --- |
| 1 | 冻结接口（4 组件边界 + 契约） | 我（L1） | ✅ 已完成 |
| 2 | 写 4 份 `downstream.md`（下行视图） | 我（L1） | 下一步 |
| 3 | 每组件产 File Contract + Build Instruction + **空壳文件** | 4 个子智能体（L2） | 待做 |
| 4 | 合并 + 机械验证（能 import / stub 可加载 / 无逻辑） | 我 | 待做 |
| 5 | **独立盲审**：不看设计意图，只看空壳能否推出实现 | 另一个智能体 | 待做 |
| 6 | 审查通过 → 打 `tag CAST-FREEZE-v1.0` | 我 | 待做 |
| 7 | 派工注入代码，逐个把「虚拟件」换成「真实件」 | 多个子智能体（L3） | 待做 |

**关键**：第 6 步不能省。没有 Freeze 就注入代码 = 让实现者即兴发挥，等于没设计。

---

## 三、组件总览（4 个）

| 组件 | 一句话职责 | 文件数 |
| --- | --- | --- |
| **契约层** | 四个组件共用的边界词汇（不是组件，是分界线） | 6 |
| **C2 Audio Core** | 把两段音频编译成一份只读分析数据面 | 10 |
| **C1 Framework / Host** | 接文件、起任务、编排算法、把结果交给界面 | 6 |
| **C3 Algorithm** | 从数据面读数据，返回客观指标 | 5 |
| **C4 Web Cockpit** | 开发者调试界面（Mac，只给开发者） | 4 |
| 入口 + 配置 | 无头命令行入口 + 冻结的 profile 定义 | 4 |

合计 **35 个文件**。

---

## 四、文件清单

### 契约层 `harmonica_eval/contract/`

```text
__init__.py          契约出口，集中 re-export
session.py           会话状态 + 时间基准（两轴分离）+ 音频格式
errors.py            错误码 + 异常层次（12 个码，标明归属与后果）
host.py              C1→C2 的 7 个操作 + 10 个禁止出现的方法名
data_surface.py      C3→数据面的 2 个操作 + 4 条端口不变量
ui.py                C1↔C4 的投影与命令（C4 只能表达 6 种意图）
```

### 配置 `harmonica_eval/profile/`

```text
__init__.py          profile 出口
v0_1.py              CORE_PROFILE_V0.1：对齐参数、端口定义、预算上限（全部冻结值）
```

### C2 Audio Core `harmonica_eval/core/` ← **唯一核心**

```text
__init__.py          包出口
api.py               对外门面，实现 CONTRACT-HOST-v1 的 7 个操作
ingest.py            解码 → 下混单声道 → 重采样 → float32（标准化）
align.py             低分辨率 chroma + DTW → warp path（必须 hop≥2048）
warp.py              应用 warp path：把一个时间轴映射到另一个
features.py          RMS 能量包络 + 低分辨率 chroma（物化，极小）
spectrum.py          STFT/Mel/CQT（只冻结定义，按需现算）
cache.py             按需计算 + LRU 缓存（不预存派生数据）
store.py             只读 memmap 后备存储（落盘与跨进程共享）
surface.py           数据面装配 + Seal + manifest（自描述清单）
```

### C1 Framework / Host `harmonica_eval/host/`

```text
__init__.py          包出口
app.py               应用生命周期：创建/销毁会话、装配组件
session.py           会话状态机（6 状态单调推进，不可跳过 DATA_READY）
orchestrator.py      算法编排（全系统唯一的编排点）
registry.py          算法注册表（新增算法不改处理流程）
projections.py       生成 UI 投影（必须下采样，避免人类面对几千个文件）
```

### C3 Algorithm `harmonica_eval/algorithms/`

```text
__init__.py          包出口
base.py              算法协议 + 结果信封 + 兼容性检查（单向）
pitch.py             音准：绝对音高误差、走音比例
timing.py            节奏：起音偏差（必须在保留源时间的轴上算）
dynamics.py          力度：逐音能量差
```

> `registry.py` 与 `pitch.py` 的注册关系由 C1 装配，故 `core/` **不得 import** `algorithms/`。

### C4 Web Cockpit `harmonica_eval/cockpit/`

```text
__init__.py          包出口
app.py               界面入口（Mac，只给开发者）
views.py             波形 / 曲线 / 叠加展示（只读投影）
controls.py          命令下发（选文件、运行、取消）
```

### 入口

```text
__init__.py          包出口
__main__.py          无头命令行入口（C4 缺席时仍能跑通全流程）
```

---

## 五、连接关系（谁连谁）

```text
        使用者（开发者）
              │
              ▼
        C4 cockpit ──── UiCommand（6 种意图）────┐
              ▲                                   │
              │ UiView（只读投影，已下采样）        │
              │                                   ▼
        C1 host ────────────────────────────► C2 core
              │  CONTRACT-HOST-v1（7 操作）        │
              │                                    │ Seal 后只读
              │  编排（唯一编排点）                  ▼
              └──────────────► C3 algorithms ──────┘
                   CONTRACT-ALGORITHM-DATA-v1（2 操作）
```

### 依赖方向（可自动检查，违反即报错）

```text
contract/   ← 被所有人依赖，它自己不依赖任何东西
profile/    ← 只被 core/ 依赖
core/       ← 只依赖 contract/ + profile/     禁止 import host/ algorithms/ cockpit/
algorithms/ ← 只依赖 contract/                禁止 import core/ 内部
host/       ← 可依赖 contract/ core/ algorithms/   （装配点，唯一允许跨界）
cockpit/    ← 只依赖 contract/                禁止直连 core/ algorithms/
```

**为什么要这样切**：只要 `core/` 不 import `algorithms/`，
"换算法不用改核心"就是一条可以**自动验证的结构事实**，而不是靠自觉维持的纪律。

---

## 六、数据怎么流（关闭 OC1 后的裁定）

```text
原始音频
   │  ① ingest：解码 → mono → 44100Hz → float32
   ▼
标准化 PCM
   │  ② align：低分辨率 chroma(hop≥2048) → DTW → warp path
   ▼
warp path（165 KB）  ← 真正必须物化的东西
   │  ③ features：RMS 包络 + 低分辨率 chroma（小，物化）
   │  ④ surface：装配 + Seal（自描述清单）
   ▼
分析数据面（只读）
   │  ⑤ 算法按需读取；频谱类现算（65 ms/档），算完进 LRU，不预存
   ▼
算法结果 → 投影 → 界面
```

**内存预算**：常驻 < 2 MB，峰值约 140 MB（120 秒音频）。
对比原设计（预存 3 档频谱 + hop=512 对齐）约 1.0 GB。

---

## 七、交付节奏（你什么时候能看到东西）

| 阶段 | 你会看到 | 预计 |
| --- | --- | --- |
| A | 4 份 `downstream.md` + 4 个组件的文件模具 | 本轮 |
| B | **完整空壳**（35 个文件，可 import，无逻辑）+ 盲审报告 | 紧随 |
| C | `CAST-FREEZE-v1.0` 标签 | 审查通过后 |
| D | **C4 界面可点开**（对着虚拟 C1 的夹具投影跑） | 注入第一站 |
| E | C2 核心真实可用（能把两段音频变成数据面） | 注入第二站 |
| F | C1 编排 + C3 三个算法打通 → **首次端到端出指标** | 注入完成 |

**为什么 D 在 C2 前面**：C4 只依赖 UI 契约（已冻结），可以对着**虚拟 C1** 先跑起来。
这样你能最早看到能点的东西，而核心还在造——这正是铸造厂「虚拟件先顶上」的用法。

---

## 八、我不做的事（边界）

- 不做自然语言反馈 / Agent 评价 / 教学结论（只到数值层）
- 不做面向终端用户的产品界面（C4 只给开发者，Mac 端）
- 不做模型训练
- 不引入 HDF5 / Zarr（手机端无可用绑定）
- 不在 Freeze 前写任何实现代码

---

## 九、风险与已知缺口（不隐瞒）

| # | 风险 | 现状 |
| --- | --- | --- |
| 1 | 算法死循环会卡住整个流程 | **v0.1 无解**，超时机制留待 v0.2 |
| 2 | 实测均在 Mac 完成 | 手机端（iOS jetsam / Android LMK）**未测** |
| 3 | 对齐精度未用真实音乐验证 | 目前只用合成 chroma 测过规模 |
| 4 | 目前只有 1 首曲子的数据集 | 剩 9 首待批量建（等你听完第 1 首） |
| 5 | 空壳审查可能发现设计缺陷 | 若发现 → `MOLD BREAK`，回到虚拟世界改，**不带病开铸** |
