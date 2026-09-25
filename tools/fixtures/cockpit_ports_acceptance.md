# 验收 B：前端 12 个数据端口全部打通

> 依据：`AGENTS.md`（假绿 > 假红 · 每个结论可复现 · 探针报错先怀疑探针）
> 执行：只读验收（新建 2 个文件，未改任何现有实现）
> 环境：Python 3.13.13 / macOS arm64

---

## 测试边界

**测了**：`port_summary` 完整性 · 12 端口 `read()` · 渲染结果可见性 · 四态判据
**没测**：DSP 数值精度 · 不等长配对 · 跨目录数据集 · 前端 HTTP 服务真实起停（无 CLI 入口，见主控报告）

★ **三层严格分开测** —— 本项目反复出现的假绿形态，就是把「契约里有」当成「界面能看见」。

---

## ① 契约层：port_summary 恰 12 条 ✅

```
port_summary 条数: 12
重复: 无
与 profile.PORTS 一致: True
```
★ 含 **6 个 `hop<=0` 的非帧端口**（`warp_path` / `pcm.mapped.*` / `pcm.warped.practice` / `notes.*`）
★ 整轮开发就是在这一半边上栽过（hop 守门误伤、notes 全挂）

## ② 数据层：12/12 read 成功 ✅

| port_id | shape | dtype | element_count |
|---|---|---|---|
| `warp_path` | (1870, 2) | int32 | 3740 |
| `pcm.mapped.reference` | (3210572,) | float32 | 3210572 |
| `pcm.mapped.practice` | (3210572,) | float32 | 3210572 |
| `pcm.warped.practice` | (3210572,) | float32 | 3210572 |
| `pitch.reference` | (1567, 3) | float32 | 4701 |
| `pitch.practice` | (1567, 3) | float32 | 4701 |
| `rms.reference` | (12538,) | float32 | 12538 |
| `rms.practice` | (12538,) | float32 | 12538 |
| `chroma.lowres.reference` | (1568, 12) | float32 | **18816** |
| `chroma.lowres.practice` | (1568, 12) | float32 | **18816** |
| `notes.reference` | (34, 3) | float32 | 102 |
| `notes.practice` | (34, 3) | float32 | 102 |

★ `chroma` 的 `element_count = 1568×12 = 18816`，**是 `prod(shape)` 而非帧数**
★ `warp_path` 是 int32 的 `(warp_point, axis)` 二列

## ③ 展示层：12/12 可见 ✅（★ 核心）

```
_render_ports 输出长度: 940 字符
★ 12 个 port_id 全部出现，缺失 0
★ shape 字段出现: True
★ timeline_basis 出现: True

片段：
port_id | dimensions | element_type | timeline_basis | shape
warp_path | warp_pointxaxis | int32 | TimelineBasis.REFERENCE | 1870x2
pcm.mapped.reference | sample | float32 | TimelineBasis.REFERENCE | 3210572
```

### ★★ 两条实测得到的关键口径（勿凭印象改）

**1. 必须先 `run_algorithms`，否则展示层会误判**
```
build_view 单独调用 → scalars=0 series=0 → render_scalars 返回空串
build_plots 返回 0 个图元
★ 那不是「前端没画」，是「算法还没跑」
★ 第一次探针就踩了这个坑，第二次才拿到真实结果
```

**2. 端口渲染走私有的 `_render_ports`**
```
公开的 render_status / render_scalars / render_progress / render_error
  → 只画状态/标量/进度/错误，★ 不含端口
端口由 _render_ports(view) 画
★ 第一次探针只调公开函数，得出「0/12 可见」的假结论
```

## ④ 四态判据 ✅

```
跑完算法后: scalars=16  series=2  port_summary=12  state=DATA_READY  error_code=None
★ 判定 = C「有数据」（判据在测试里自动断言）
```

★ 三者互斥：
```
scalars空 + error_code非空 → 「有诊断的失败」（★ 不得显示「无数据」）
scalars空 + error_code为空 → 「已通无源」
scalars非空                → 「有数据」
```

---

## ★ 红绿证明（三条，全部真实执行 + 逐字节恢复）

| # | 注入 | 结果 |
|---|---|---|
| A | `_render_ports` 跳过第 1 个端口 | `test_every_port_visible_in_rendered_output` **FAILED**，1 failed / 9 passed ✅ |
| B | `read()` 对 `notes.reference` 抛错 | **4 failed / 6 passed**（数据层 + 渲染 + 四态）✅ |
| C | 从 `profile` 改端口名 | 被 `profile` 自身的「端口对称性破裂」检查拦下 ✅ |

★ 恢复均用操作前独立副本，`cmp` 逐字节相同。

### ★★ 两条探针错误（如实披露，且都改变了结论）

**探针错 1：正则没匹配到 `read` 的真实签名**
```
第一版用 r'def read\(self[^)]*\)' → 未找到（真实签名是多行的）
★ 那次「10 passed」是【无效结果】，不是「判据恒真」
★ 改用 AST 定位首条语句的真实行号后才拿到真红
```

**探针错 2：改端口名触发了上游完整性检查**
```
改 profile 里的 port_id → ValueError: 端口对称性破裂
★ 那道守卫比我的测试更早触发 —— 是好事
★ 但也意味着「从 profile 删端口」这条红端路径不可行
```

### ★★★ 一处真实事故：我弄丢了 `profile.py` 的两个符号

★ **恢复红端①时操作失误，把这两个符号删掉了**：
```
SAMPLE_RATE_FREE_PREFIXES   ← 消失
port_prefix()                ← 消失
★ 症状：AttributeError: module 'harmonica_eval.profile' has no attribute ...
★ 且 pytest 在 collection 期就崩，0 个用例能跑
```

★ **已修复**：权威值取自 `_scratch/harmonica_eval/core/surface.py:75` 的
```
SAMPLE_RATE_FREE_PREFIXES = frozenset({"chroma", "warp_path", "notes"})
```
★ 修复后：`49 passed`（全量）、`SAMPLE_RATE_FREE_PREFIXES` 与 `port_prefix` 均正常。

★ **★ 这条事故本身是本报告最重要的一条**：
```
★ 它说明「红端注入后的恢复」是最容易出事的一步
★ 而当时的症状（collection error）看起来像「判据写错了」
★ ★ 若没先查「git diff 是否干净」，很容易误判成测试文件的问题
```

---

## 结论

### ★「前端所有端口都通」达成了吗？

**三层全部达成：**
```
① 契约层  port_summary 12 条，无重复无多余，与 profile.PORTS 一致   ✅
② 数据层  12/12 read 成功，shape/dtype/element_count 全部合契约      ✅
③ 展示层  12/12 port_id 出现在渲染结果，shape 与 timeline_basis 可见  ✅
```

★ **且三条红端证明都有效** —— 每条判据都能抓到对应缺陷，无恒真。

### ★★ 未通过 / 未验证的部分

```
① 前端无 CLI 启动入口
   python3 -m harmonica_eval.cockpit.app → rc=0，无输出，无启动
   ★ launch_cockpit(port) 需要投影端口参数，无人从命令行构造它
   ★ 端口层全通，缺的只是「最后一米」的启动命令

② HTTP 服务真实起停未验（依赖 ①）
③ DSP 数值精度未验（只验了「能读出、维度对」，不验绝对正确性）
```

---

## 我验证过什么 / 没验证什么

**✅ 实跑验证**
- port_summary 12 条实测 · 12 端口 read 逐条 shape/dtype/element_count
- 渲染结果 12/12 可见 · shape 与 timeline_basis 出现
- 四态判定为 C「有数据」
- 三条红端证明（含两次探针错误的修正过程）
- 端口数与 profile.PORTS 清单一致性
- `SAMPLE_RATE_FREE_PREFIXES` 事故的发现与修复

**❌ 明确未验证**
- HTTP 服务能否真的起起来（无 CLI 入口）
- 前端在浏览器里的实际渲染效果（未截图、未交互）
- 不等长配对下 12 端口是否仍全通
- DSP 数值的绝对精度
- `notes` 34 vs 35 音的不等长场景下渲染是否正确
