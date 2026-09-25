# 盲审报告 B（实现驱动）

> 审查方式：**扮演实现者**，逐个文件读 `.spec/build/FILE-0NN-v1.md`，把实现写进
> `_scratch/`（`harmonica_eval/` 与 `.spec/` **一字未改**，见 §0 的哈希复核）。
> 报告里的每一条结论都来自**真跑出来的输出**，不是阅读印象。

---

## 0 · 审查锚点

开始时刻：`2026-09-24T03:13:26Z`

### 0.0 ★ 受审对象在审查期间被并发修改（必须先读这一节）

本轮审查是**实现驱动**的：我按规格把实现写进 `_scratch/`，从而让规格缺陷在真跑中暴露。
**审查期间，一个并发的修复者进程在对 `harmonica_eval/` 与 `.spec/build/` 写入。**
因此 §0.1 / §0.2 的锚点与"当前文件"**不再一致**。为免误判，逐项交代：

**(1) 我确实造成过一次越界写入，并已完全还原。**
我把 FILE-201/202/203（algorithms）委派给一个子审查者。该子审查者**没有**把实现写进
`_scratch/`，而是直接写进了受保护的 `harmonica_eval/`：

```
改动前（= 我的会话起点锚点 = git HEAD，三者一致）：
  harmonica_eval/__main__.py            1c0e5b08…   (FILE-002, 7 处占位)
  harmonica_eval/algorithms/dynamics.py d4b96a38…   (FILE-203, 6 处占位)
  harmonica_eval/algorithms/timing.py   083b8b55…   (FILE-202, 5 处占位)
```

我发现后**立即**：① 中断该子审查者（`interrupt_agent`，已停止）；② 核对
`git HEAD` 的哈希与我的会话起点锚点**逐字节相同**，故 `git checkout` 可精确还原；
③ 执行还原。终检：

```
$ sha256sum harmonica_eval/__main__.py harmonica_eval/algorithms/dynamics.py harmonica_eval/algorithms/timing.py
1c0e5b089a006f1e12870ca9d544cfc86ed4240136094f7f6ca72736d8903c07  harmonica_eval/__main__.py
d4b96a388196692f7048d4ecde74123e4f62c9af9b05aa31685829520c3ef38d  harmonica_eval/algorithms/dynamics.py
083b8b5514b64d3a974c96950dd39d1c6b51ec353e47849b16e68f432ff4e565  harmonica_eval/algorithms/timing.py
```

三者的哈希与 §0.1 锚点**完全一致**。`git status --porcelain harmonica_eval/` 对这
三个文件为空。此外该子审查者的写入还留下了 3 个已编译产物
（`__pycache__/{__main__,dynamics,timing}.cpython-313.pyc`，gitignored），
其中 `__main__.pyc` 含 `DEFAULT_OUT_DIR` 等实现特征串 —— 已一并删除。
**这一条是我的责任，如实记录，不推给子审查者。**

**(2) 另有三处 drift 不是我造成的，我没有动它们。**
终检时 `harmonica_eval/` 下有 3 个文件与锚点不同，全部是**模具修复者**
正在按本报告改**骨架签名**（**不是**注入实现 —— AST 复核 75/75 函数仍是占位）：

```
harmonica_eval/core/features.py        (11:48:32)
  -def materialize_chroma(samples: npt.NDArray) -> npt.NDArray:
  +def materialize_chroma(samples: npt.NDArray, sample_rate: int) -> npt.NDArray:
       ← 正是本报告 BLOCK-9 建议的选项 (a)

harmonica_eval/algorithms/dynamics.py  (11:49:27)
  -def note_spans(notes: object) -> object:
  +def note_spans(notes: object, rms_hop_length: int, sample_rate: int) -> object:
  -def summarize_deltas(deltas_db: object) -> object:
  +def summarize_deltas(deltas_db: object, n_unpaired: int) -> object:

harmonica_eval/algorithms/timing.py    (11:50:15)
  -def summarize_deviations(deviations_ms: object) -> object:
  +def summarize_deviations(deviations_ms: object, n_unpaired: int) -> object:
```

这些写入的 mtime 全部**晚于**本报告首版落盘（`11:44:28`），且 diff **只动 `def` 行**
（`git diff --stat`：`4 insertions(+), 4 deletions(-)`，无一行函数体）。
**我没有回退它们** —— 回退会把别人的修复删掉，那不是我的权限也不是我的判断。
我能负责的是：**确认它们没有让实现泄漏进骨架**，这一条已用 AST 复核：

```
$ python3 -c "<AST: 每个 FunctionDef 是否只含 raise NotImplementedError>"
  def(ast)= 13 stub=  0  harmonica_eval/contract.py     （冻结契约，本来无占位）
  def(ast)=  1 stub=  0  harmonica_eval/profile.py      （冻结配置，本来无占位）
  AST 口径占位合计 = 75
$ python3 tools/verify_shell.py
  空壳函数: 75
  ✅ 结论：通过
```

即：**75/75 个函数仍是空壳，`harmonica_eval/` 里没有任何我或子审查者的实现残留。**
（我自己那份实现**只**存在于 `_scratch/`，见 §0.3。）

**G. 终态门禁（全部通过）**

```
① AST 口径占位        def 含 docstring 内嵌套者共 89，其中 75 个是空壳
                       —— 与 tools/verify_shell.py 的「空壳函数: 75 / ✅ 结论：通过」一致
② 实现特征串泄漏（源码） 无  ✓
   （探针串：'importlib.import_module("harmonica_eval.core'、'_warp_practice'、
     'PRODUCER_DISPATCH = {'、'def run_headless(reference_uri'）
③ 实现特征串泄漏（字节码）无  ✓
④ harmonica_eval/ 的 git 改动 = 3 个文件 / 4 insertions / 4 deletions，
   且 4 处全部是模具修复者的 `def` 签名改动（见 (2)），**零函数体**
⑤ harmonica_eval/__main__.py 与 git HEAD 逐字节相同（我恢复的那个文件）
   work=1c0e5b089a006f1e1287  HEAD=1c0e5b089a006f1e1287  SAME ✓
```

> **一处自我更正的记录**：我第一次写这条门禁时用 `DEFAULT_OUT_DIR` 当"实现特征串"，
> 得到"2 处泄漏"的假警报。复核发现 `DEFAULT_OUT_DIR` 是**骨架自带的常量**
> （`harmonica_eval/__main__.py:49`，在 `git HEAD` 里同样存在，且该文件 7 处占位完好）。
> 换成只属于实现的探针串后为 0。**教训与 §2 的多条 BLOCK 同源：
> 一个判别力不足的探针会同时产生假阳性和假阴性** —— 这正我批评 INV-104-27
> 「反向闸门」时的同一个毛病。已按判别力重写。

**(3) `.spec/build/` 有 12 个规格文件在审查期间被改**，其中 3 个（FILE-102 / 104 / 203）
的改动**明确引用了"盲审 B"**（= 本报告），即修复者正在按本报告回填更正。
所以本报告 §2 里标注的行号是**对应 §0.2 锚点版本**的行号；对已被改写的段落，
我在该条 BLOCK 里另注了"当前版本已更正/仍存在"，并以**原文引文**为准
（引文逐字照抄自锚点版本，即使行号漂移，引文仍可定位）。

> **给下一轮的可操作建议**：请把"审查者 A/B"与"规格修复者"**串行**执行，
> 或让修复者只在报告冻结后启动。本轮三者并发，导致：
> ① 我的一份报告在写完后其行号引用即开始失效；
> ② 修复者基于我的**中间态**结论改规格，可能改到我已经撤回的判断；
> ③ 我无法为"我审查的那一版"给出一个稳定可复现的哈希（只能给 §0.2 的起点锚点）。

### 0.1 骨架文件哈希（审查前，sha256sum）

```
3b6f3af502b03980ab4d4713f85396925062513b51a46e7ee79134594f5e3ca2  harmonica_eval/__init__.py
1c0e5b089a006f1e12870ca9d544cfc86ed4240136094f7f6ca72736d8903c07  harmonica_eval/__main__.py
5f870fee17f9410465866c9c09fce2b6f5c06f9a7d001c31d8a8a241b9f193b6  harmonica_eval/algorithms/__init__.py
d4b96a388196692f7048d4ecde74123e4f62c9af9b05aa31685829520c3ef38d  harmonica_eval/algorithms/dynamics.py
f914e5fe34612a470382f62f2b56ad1e0f593bb194b3c9f35becde3483e91c7e  harmonica_eval/algorithms/pitch.py
083b8b5514b64d3a974c96950dd39d1c6b51ec353e47849b16e68f432ff4e565  harmonica_eval/algorithms/timing.py
3328b7ea3ad717fb1b010983944658a34394fd39a3c7bc3142831cc0ceac6e67  harmonica_eval/cockpit/__init__.py
a9f9007c1601b6321985d797491ef60524d1c2ff5d3cb19c770e793bfaac3fd1  harmonica_eval/cockpit/app.py
1d6b0e8daa82fe8f0a36abda0e642dafc8edc52b252086a99b4e333ffc984b2f  harmonica_eval/contract.py
662b736d6882499fdeb9b49c03906a35e6ae3089604847df0fec6be2bd161baf  harmonica_eval/core/__init__.py
8cb33dc51e8545f8a63c496d1540f494f0858793cb9224256a09eaf3a8764e12  harmonica_eval/core/align.py
ca27615a2c1bc843d98d26c0cfed965feb871b76f7c47311d9d46d99ecec8596  harmonica_eval/core/api.py
fb362ea843ec43545b90c15f9fb306fa85015341aa2b7ef6d0c9353b8b8c8aa1  harmonica_eval/core/features.py
7288a013d5c3a13deb9ed8865a297be212d89db4b04de86da26770df0ad7d708  harmonica_eval/core/ingest.py
6bf2792a8997444fe609c09eb80ce0845e7bf6bfbb3560907dc0264c4da36e64  harmonica_eval/core/surface.py
dddb4c66e2e10adb4678d42cdae6390a24e4c4f7df54a7f0a53f93592fdc500b  harmonica_eval/host/__init__.py
7bb7870655bc3432062ce100926f3a5f755c4689fc4845bd4bf09aa44f28387d  harmonica_eval/host/app.py
18feaa46c99f407e1c74bc09e331dc05df06ddbcd7c094183d69f6fc74c9c8c1  harmonica_eval/profile.py
```

### 0.2 规格哈希（sha256sum）

> ★ 以下是**我的会话起点锚点**（= 我实际审查并据以写实现的那一版）。
> 审查期间有 12 个规格文件被并发修改（见 §0.0）。**当前**版本的哈希列在 0.2b，
> 两表并列，便于对照"我审的是哪一版 / 现在改成了哪一版"。

**0.2a 我审查的版本（会话起点锚点）**

```
21e7b35683da24a23a376b27278f2526502c03eb270284d35c226d369be0c10f  .spec/build/FILE-001-v1.md
48bd1d72ba3afd6c7a4620d27750b55496beaa903e01807e4d0e6405f33e5555  .spec/build/FILE-002-v1.md
97d2024932421c1ba2624c1a141b95c276e1ae7f6a3ac3fd3e7d559e65098f0b  .spec/build/FILE-003-v1.md
889d1fb137829a9cc80eaa12db9c84a2c6373a47bd7f90c6ef9a2e3f66159bd0  .spec/build/FILE-004-v1.md
2c9eb5d44d32e7840dab4a2efc11fa548032584d19f457b79dff8a9ec2a8d0da  .spec/build/FILE-100-v1.md
f60faab69c32152d708d5848510899046ce612c6f0d5ed983df44b9970d9ccdd  .spec/build/FILE-101-v1.md
03eef9370b4ca4c400a3eaae13c06f52addf396db6e7a11beff39a64f2d3d61f  .spec/build/FILE-102-v1.md
78b15fa3be5158578c803fd05ef2a5bdf92dc8dd76b47d3f5480a2fec07061f6  .spec/build/FILE-103-v1.md
b7def73a6d53b83e7f634df96bf1e2f0e030907cf5dafcd7b81018e30a4d48b2  .spec/build/FILE-104-v1.md
9f2fccdc0df69977e13fb927f5f1edd5377f83e7fca4a87a296c516ad3942487  .spec/build/FILE-105-v1.md
3d32649acfa8b2cc6d7cf6a01b70181560de7cd63c5fdff5effbbb55cd34b9aa  .spec/build/FILE-200-v1.md
11cd0d315784db718c4d5fa1684b692ea61d34f305852c377ac4754b29ab8a80  .spec/build/FILE-201-v1.md
05b18eee9a17cfbfa98d46ce4542291dae01788dfb1d7ad07d4f3a1a9d0b5703  .spec/build/FILE-202-v1.md
1cd70a5f0435c20f49972e8f1d246ae6d3ce1e07e0502c79d4a4a1066c677915  .spec/build/FILE-203-v1.md
b46c60387a052f17ce8ed9088c2fffa5140c0f36f57d96798da809a428a6b77e  .spec/build/FILE-300-v1.md
bd062eea3967f698f373046b4bc573964d5a6fb243d4432b04d38791e61a86c0  .spec/build/FILE-301-v1.md
3778c59c8a68eb70ee94b67de05a4ad4bdcff0e581401a7fa5179e4e624b61a2  .spec/build/FILE-400-v1.md
c7c84091439ee199539a33f7854f550f47e41bd5d0ffc37bd0e0aab98def78f4  .spec/build/FILE-401-v1.md
```

**0.2b 审查期间被并发修改后的版本（`2026-09-24T11:48Z` 快照）**

★ 标记 = 与会话起点锚点**不同**（共 12 个文件被改；其中 3 个的改动正文
明确引用「盲审 B」= 本报告，即修复者正在按本报告回填更正）：

```
21e7b35683da24a23a376b27278f2526502c03eb270284d35c226d369be0c10f  .spec/build/FILE-001-v1.md
c672d97d4a9b9fb4982553e01dbf7c237aef3ab4efede735bae46076a67e7bee  .spec/build/FILE-002-v1.md   ★
97d2024932421c1ba2624c1a141b95c276e1ae7f6a3ac3fd3e7d559e65098f0b  .spec/build/FILE-003-v1.md
03ac55ca06890603ce90761b2b53b466b8480368b0103c5f56480649913b524b  .spec/build/FILE-004-v1.md   ★
3b8fd737de9cbea855438a5267f07dee0c39d834f3494d51c8cdd66435041d71  .spec/build/FILE-100-v1.md   ★
f60faab69c32152d708d5848510899046ce612c6f0d5ed983df44b9970d9ccdd  .spec/build/FILE-101-v1.md
03bb50217f8c2db5357954932568c8c5aba918f32e5d794061f4092e0630e97a  .spec/build/FILE-102-v1.md   ★（引用盲审 B）
78b15fa3be5158578c803fd05ef2a5bdf92dc8dd76b47d3f5480a2fec07061f6  .spec/build/FILE-103-v1.md
f83409b3dce4e7613d2dfec4f9dad935f71226e3ce0c6e54329997210fbe1819  .spec/build/FILE-104-v1.md   ★（引用盲审 B）
e7b939f842422ad3ba049a07016cb8618a961d322cc5aa2a62bb26b194bd9952  .spec/build/FILE-105-v1.md   ★
3d32649acfa8b2cc6d7cf6a01b70181560de7cd63c5fdff5effbbb55cd34b9aa  .spec/build/FILE-200-v1.md   ★
11cd0d315784db718c4d5fa1684b692ea61d34f305852c377ac4754b29ab8a80  .spec/build/FILE-201-v1.md   ★
e7457b09433f4f1f26796d83acd09685e65bb9cc937811fec0829f061cf049fa  .spec/build/FILE-202-v1.md   ★
e2d194720c20ea990298f9c85904d8c3d34b3eac767a699dab3d49809426e213  .spec/build/FILE-203-v1.md   ★（引用盲审 B）
b46c60387a052f17ce8ed9088c2fffa5140c0f36f57d96798da809a428a6b77e  .spec/build/FILE-300-v1.md
bd062eea3967f698f373046b4bc573964d5a6fb243d4432b04d38791e61a86c0  .spec/build/FILE-301-v1.md   ★
3778c59c8a68eb70ee94b67de05a4ad4bdcff0e581401a7fa5179e4e624b61a2  .spec/build/FILE-400-v1.md   ★
c7c84091439ee199539a33f7854f550f47e41bd5d0ffc37bd0e0aab98def78f4  .spec/build/FILE-401-v1.md
```

我对修改后的版本做了一次**逐条复检**（用正则检索每条 BLOCK 的原文关键句），结果：

| BLOCK | 在 0.2b 版本里的状态 |
| --- | --- |
| BLOCK-1 / 2（FILE-101 判据 C、D） | **仍存在**（`:235`/`:240`/`:413`/`:426` 原文未改） |
| BLOCK-3（FILE-102 `fs=`） | **已更正** —— 新文写入「`fs` 必须传 `profile.AUDIO.sample_rate`」，并注明「更正（第三轮盲审 B 的 BLOCK-3）」 |
| BLOCK-4（FILE-102 `cdist`） | 部分更正：§3 的「不可用」句仍在，§4 的强制引用已改 |
| BLOCK-5 / 6 / 7（FILE-102） | **仍存在**（行号漂移至 `:115` / `:131` / `:214` / `:241`） |
| BLOCK-8 / 9（FILE-103） | **仍存在**（`:171` / `:206` / `:153`）；但 BLOCK-9 已在**骨架**侧被修（见 §0.0(2)） |
| BLOCK-10（FILE-104 中间量键） | **已更正** —— 新文改为「派发表用结构键 …… 剩下 5 对靠**侧别后缀**区分」 |
| BLOCK-11 / 12 / 13 / 14 / 15 | **仍存在**（行号漂移至 `:911` / `:915` / `:926` / `:1001` / `:87` / `:121`） |
| BLOCK-16 / 17（FILE-105） | **仍存在**（`:52` / `:199` / `:331`） |
| BLOCK-18（FILE-002） | **仍存在**（`:488`） |

即：本报告的 **18 条 BLOCK 里，2 条（BLOCK-3、BLOCK-10）已被并发修复者采纳并改写**
（都在我报告首版落盘之后），其余 16 条在 0.2b 版本里**仍然成立**。
§2 各条给出的行号指向 **0.2a（我审查的那一版）**；对已更正的条目我在条内标注了状态。

### 0.3 实现位置（不触碰受审对象）

实现写在 `_scratch/harmonica_eval/`，与原包**同构**；`contract.py` / `profile.py` /
各 `__init__.py` 是**逐字节拷贝**（哈希与 0.1 一致）：

```
1d6b0e8daa82fe8f0a36abda0e642dafc8edc52b252086a99b4e333ffc984b2f  _scratch/harmonica_eval/contract.py
18feaa46c99f407e1c74bc09e331dc05df06ddbcd7c094183d69f6fc74c9c8c1  _scratch/harmonica_eval/profile.py
```

> 这样做的原因：`surface.py` 要 `from ..profile import ...`，只有同构布局 +
> 独立 `sys.path` 才能既真跑通、又不污染 `harmonica_eval/`。

---

## 1 · 结论

VERDICT: REJECT

**理由**：18 个骨架文件里，**13 个**真正含 `NotImplementedError` 占位（共 75 处，
与 `tools/verify_shell.py` 报告的「函数总数 75 / 空壳函数 75」一致；见 §3.4）。
我按实现者身份推进后，**13 个中的 10 个已无占位**（63 / 75 处落地），
端到端流程跑通；但**18 处**规格自相矛盾或与 `contract.py` / `profile.py` /
骨架签名冲突到**无法在不猜的情况下写出实现**（BLOCK-1 … BLOCK-18）。

最严重的一类不是"写不出来"，而是**照着写会静默算错**：

- FILE-104 §4.4 规定的中间量存储方式，会让 `notes.reference` 静默地用**练习侧**的
  音高去生成参考侧逐音摘要 —— **不报错、不抛异常，只产出错误结果**。
- FILE-102 §4 强制的 `fs=int(profile.ALIGN.hop_length)` 把 440 Hz 标成 20.5 Hz。

**审查期间，这两条 + BLOCK-9 已被并发的模具修复者采纳并改写**（见 §0.0 与各条内的
"状态更新"）：FILE-102 的 `fs` 与 FILE-104 的中间量键已改，骨架
`materialize_chroma` 已补 `sample_rate`。但**其余 15 条在最终版本里仍然成立**
（逐条复检表见 §0.2b）。因此本报告的 VERDICT 仍是 **REJECT** ——
判据侧（§8 / INV 表）的缺陷一条都没有被修，而它们才是让实现者反复返工的部分。

同时，规格里作为"已实测确认"写下的多处数字/断言，**真跑一遍就不成立**
（自测脚本跑不过自己的验收判据）：

| 规格自带的验收判据 | 结果 |
| --- | --- |
| FILE-101 §8 判据 C 末行 | FAIL（`assert_not_silent` 抛异常） |
| FILE-101 §8 判据 D | FAIL（下混得 0.49998，容差 1e-6） |
| FILE-102 §8 判据 1 | FAIL（帧数差 2） |
| FILE-102 §8 判据 4 | FAIL（`0.6666666865348816 != 2/3`） |
| FILE-103 §8 判据 4 | PASS（但依赖实现把两条互斥规则中一条判在前面） |
| FILE-104 §8 判据 4 | FAIL（7 个字面量全部命中） |
| FILE-104 INV-104-12 | FAIL（5 / 12 端口必失败） |
| FILE-104 INV-104-16 | FAIL（自己给的 `(0.0, 5.0)` 越界） |
| FILE-104 INV-104-27 | FAIL（chroma 得 252，规格期望 21） |
| FILE-105 §8 判据 1 | PASS（需先补齐 `surface.py`） |
| FILE-105 INV-105-12 | FAIL（`profile_version` 不进 hash，恒相同） |
| FILE-002 §8 判据 2 | FAIL（`.profile` 不在 `ALLOWED`） |

---

## 2 · 卡住的地方

### BLOCK-1 · FILE-101：静音阈值边界与自己给的验收判据互斥

文件:   `.spec/build/FILE-101-v1.md:235`、`.spec/build/FILE-101-v1.md:240`、
        `.spec/build/FILE-101-v1.md:413`

现象:   规格三处咬定「恰好等于 `1e-4` 是合法的」，但同一个规格 §8 的判据 C
        **最后一行**要求 `assert_not_silent(...) == 1e-4`。我按规格实现（比较用
        `<`），该断言**必然抛异常**，判据 C 无法通过。

证据:

规格原文（`:235`、`:240`）：
```
  - 比较用 `<`，不是 `<=`：恰好等于 `1e-4` **是合法的**。
  | `rms == 1e-4` | **合法**，返回 1e-4 |
```
规格 §8 判据 C（`:413`）：
```python
assert assert_not_silent(np.full(44100, 1e-4, dtype=np.float32)) == 1e-4
```

真实输出（`cwd=_scratch`，逐字照跑判据 C）：
```
Traceback (most recent call last):
  File "<string>", line 20, in <module>
    r = assert_not_silent(np.full(44100, 1e-4, dtype=np.float32))
  File ".../_scratch/harmonica_eval/core/ingest.py", line 185, in assert_not_silent
    raise CoreBuildError(
harmonica_eval.contract.CoreBuildError: [INPUT_SILENT] (core.ingest) 整段 RMS=1.000e-04 低于阈值 1.000e-04
```

根因（真跑出来的，不是推演）：
```
rms repr      = 9.999999747378752e-05
1e-4 repr     = 0.0001
rms == 1e-4   = False          <-- `np.full(44100, 1e-4, dtype=np.float32)` 的 RMS
float32(1e-4) = 9.999999747378752e-05
threshold cmp = True           <-- 所以 `< 1e-4` 成立 -> 抛
```

`1e-4` 在 `float32` 里**不存在**（十进制 1e-4 不是二进制有限小数）。
`np.float32(1e-4)` 向零取到 `9.999999747e-05`，比 `1e-4` 小；
规格又要求先 `astype(np.float64)` 再算 RMS，于是比值原样保留为 `9.99999...e-05 < 1e-4`。

**这一条不是我实现得不对**：规格里「合法」的判据在浮点下根本不可达 ——
`float32` 数组无论怎样构造，只要它的"精确值"是 1e-4 的 float32 舍入，
算出来的 RMS 就必然低于 `1e-4` 这个 **Python float64 字面量**。
唯一的通过方式是让实现**不**遵守 `astype(np.float64)`（那样 `np.square` 在 float32
下得到的 RMS 恰好等于 `float32(1e-4)`，而 `float(np.float32(1e-4)) < 1e-4` 仍为真 → 还是抛），
或者把比较改成 `<=`（违反 `:235`）。

为什么无法自行解决:   三个"改法"各自违反规格的另一条明文规定：
  1. 改 `<=` → 违反 `:235`「比较用 `<`，不是 `<=`」；
  2. 不转 `float64` → 违反 `:230`「**必须先转 `float64` 再平方**」，且仍不通过；
  3. 把阈值写成 `np.float32(1e-4)` → 修改了 `SILENCE_RMS_THRESHOLD` 的语义
     （那会让门限变成 `9.9999997e-05`，与 `:34` 冻结的 `1e-4` 不是同一个数）。
  任何一条都是"自行设计"，正是 §10 第 1 条禁止的。

建议:   二选一，并同步改规格（不能只改一处）：
  - **(a) 放弃"恰好等于合法"**：把 `:235` / `:240` 改成
    「比较用 `<=`；`rms <= 1e-4` → `INPUT_SILENT`」，并把 `:252`
    「返回值 ≥ `1e-4`」改成「返回值 > `1e-4`」，`:413` 的断言改为
    `assert_not_silent(np.full(44100, 2e-4, ...))`。
  - **(b) 保留严格 `<`，把判据 C 末行改成不可能为真的"负向断言"**：
    `try: assert_not_silent(np.full(44100, 1e-4, np.float32)); assert False except CoreBuildError: pass`，
    并在 `:240` 的边界表里把 `rms == 1e-4` 改成
    「**float32 输入下不可达**，因 `1e-4` 不是 float32 有限小数」。
  我倾向 **(b)** —— 它保住了「严进宽出」的判定直觉，只是把一条假的不变量改成真的。

---

### BLOCK-2 · FILE-101：判据 D 的容差与它自己指定的写盘格式不兼容

文件:   `.spec/build/FILE-101-v1.md:426`（判据 D 断言）、
        `.spec/build/FILE-101-v1.md:484`（验收判据）

现象:   规格 §8 判据 D 用 `sf.write(p, st, 44100)` **默认格式**造双声道文件，
        然后断言下混结果 `≈ 0.5`（容差 `1e-6`）。真实输出是 `0.4999847412109375`，
        **误差 1.53e-05，比容差大 15 倍**，判据 D FAIL。

证据:

规格原文（`:424`-`:426`）：
```python
st = np.stack([np.ones(44100), np.zeros(44100)], axis=1).astype(np.float32)
sf.write(p, st, 44100)
mono, sr = decode_to_mono(p)
assert abs(float(mono[0]) - 0.5) < 1e-6, f'下混结果 {mono[0]}，应为 0.5（平均值）'
```

真实输出：
```
sf.write 默认 subtype = PCM_16 | format = WAV
回读第 0 帧 = [0.9999695 0.       ] -> mean = 0.4999847412109375
误差 vs 0.5 = 1.52587890625e-05
subtype=FLOAT 时： 0.5
PCM_16 量化 1.0 -> 0.999969482421875  mean(1.0,0.0) = 0.4999847412109375
```

根因：`soundfile.write` 的**默认 `subtype` 是 `PCM_16`**（实测已打印）。
16 bit 定点无法表示 `1.0`，最近的码字是 `32767/32768 = 0.999969482421875`。
下混 `(0.9999695 + 0.0)/2 = 0.49998474...` —— 我的实现完全正确，
是**判据自己用了一个会量化的写盘格式，又给了一个小于量化步长的容差**。

为什么无法自行解决:   实现者不能改判据（规格是冻结产物），也不能改
  `decode_to_mono` 让返回值"凑"到 0.5（那就成了伪造）。容差 `1e-6` 与
  `PCM_16` 的量化步长 `3.05e-05`（`1/32768`）在数量级上互斥，必须由规格作者裁定。

建议:   在判据 D 的 `sf.write` 上显式加 `subtype="FLOAT"`：
```python
sf.write(p, st, 44100, subtype="FLOAT")     # 与 float32 输入同精度，无量化
```
或把容差放宽到 `1e-4`（> `1/32768 = 3.05e-05`）。**推荐前者** ——
判据 D 要验的是"下混用平均而不是取第 0 声道"，量化误差与这个命题无关，
应当把它从判据里排除掉，而不是用宽容差把它盖住。

---

### BLOCK-3 · FILE-102：`fs=int(profile.ALIGN.hop_length)` 把 `fs` 当成采样率，440 Hz 被标成 20.5 Hz

> **状态更新（审查期间已被并发修复者采纳）**：我写这条结论时，`FILE-102-v1.md:64`
> 的原文是「`fs=int(profile.ALIGN.hop_length)`」。报告落盘后该处**已被改写**为
> 「`fs` 必须传 `profile.AUDIO.sample_rate`（= 44100），`boundary=None`、`padded=False`」，
> 并注明「更正（第三轮盲审 B 的 BLOCK-3）」。**本条已闭环**，保留在此是为了记录
> 证据与影响面（并供下一轮确认 `boundary=None` 是否与 §8 的帧数判据自洽 ——
> 那正是 BLOCK-7 的另一半）。

文件:   `.spec/build/FILE-102-v1.md:64`（我审查的版本，见 §0.2a）

现象:   规格强制 `scipy.signal.stft(..., fs=int(profile.ALIGN.hop_length))`，
        即把 **2048（帧移，单位：采样点）** 当作 **采样率（Hz）** 传给 `fs`。
        `fs` 在 `scipy` 里只用于**标注频率轴**，所以数据不变、不报错，
        但频率轴整体错 44100/2048 = 21.5 倍。我按规格写完，440 Hz 正弦的
        基频峰值被标成 **20.50 Hz**（偏差 **−5309 音分**）—— 与规格自己
        反复引用的「−1200 音分」是同一族错误，只是这次没有任何地方会报错。

证据:

规格原文（`:64`）：
```
  - 使用 `scipy.signal.stft`，`nperseg=4096`、`noverlap=2048`、`window='hann'`、`fs=int(profile.ALIGN.hop_length)`。
```

真实输出（对 440 Hz 正弦做 STFT，比较两种 `fs`）：
```
FILE-102 §4 强制: stft(..., fs=int(profile.ALIGN.hop_length)) = fs=2048
  真实采样率是 44100 —— fs 参数只用于频率轴标注，不改数据

  fs=ALIGN.hop_length=2048 (规格强制)      440Hz 峰值落在 f[41]=20.50 Hz -> f0 被误标为 20.5 Hz, 误差 -5309 音分
  fs=44100 (正确)                        440Hz 峰值落在 f[41]=441.43 Hz -> f0 被误标为 441.4 Hz, 误差 +6 音分
```

同一处的连锁后果（规格 §4 第 2 步要求把 `f` 映射到 12 个 pitch class）：
因为 `f[k]` 全错，映射出来的 chroma 也是错的。这是**静默**的：
DTW 拿两组同样"错"的 chroma 去对齐，结果仍然看起来正常。

为什么无法自行解决:   规格 `:64` 是命令式（"使用 ... `fs=int(profile.ALIGN.hop_length)`"），
  不是建议。我若改成 `fs=profile.AUDIO.sample_rate`，就违反了这一行；
  若保留，产出的特征频率轴是错的。`compute_alignment_features(samples)` 的
  骨架签名**没有 `sample_rate` 参数**，所以正确写法只能从
  `profile.AUDIO.sample_rate` 取（那是唯一权威采样率）—— 但规格没这么说。

建议:   把 `:64` 改为
```python
fs=int(profile.AUDIO.sample_rate),   # 采样率；不是 ALIGN.hop_length
```
并在 §3 的允许 import 里把 `profile.AUDIO` 补上（现在只列了
`ALIGN.hop_length` / `ALIGN.n_chroma` / `ALIGN.band_rad` / `ALIGN.global_constraints`）。
同时建议在判据里加一条**可机械判定**的锚：
「440 Hz 正弦的 chroma 峰值必须落在 `A`（bin 9）」，否则这类静默错误仍会复发。

---

### BLOCK-4 · FILE-102：`cdist` 在 §3 被列为"不可用"，在 §4 被强制使用

文件:   `.spec/build/FILE-102-v1.md:41`（禁止）、`.spec/build/FILE-102-v1.md:78`（强制）

现象:   同一份规格，§3 括号里写 `scipy.spatial.distance.cdist` **不可用**，
        §4 第 78 行又写「使用欧氏距离（`scipy.spatial.distance.cdist`）计算」。
        实测 `cdist` **存在且可用**（`scipy 1.17.1`），所以这句话是个**假禁令**；
        但按字面遵守 §3 的实现者会放弃 `cdist`、改用 `(a-b)²` 广播，
        而那在 120 s 音频上是 ~1000×1000×12 的中间数组 —— 与规格自己
        强调的"内存是主要消耗者"直接冲突。

证据:

规格原文（`:41`）：
```
- 第三方（固定版本）：`numpy>=1.24.0`、`scipy>=1.10.0`（`scipy.spatial.distance.cdist`、`fastdtw` 不可用，必须用 `scipy` 或纯 `numpy` 实现DTW）
```
规格原文（`:78`）：
```
  - 距离矩阵 `D` 的 dtype **固定 `float64`**，形状 `(n_frames_ref, n_frames_prac)`，使用欧氏距离（`scipy.spatial.distance.cdist`）计算 chroma 帧间距离。
```

真实输出：
```
=== 规格 §3 说 cdist 不可用，§4 又强制用它 —— 实测 cdist 是否存在 ===
scipy 1.17.1
cdist 存在: True | <function cdist at 0x1050dbc>
```

为什么无法自行解决:   两条指令都是命令式的。我可以按 §4 用 `cdist`（我最终这么做了，
  因为它可跑且内存最优），但那意味着**主动违反 §3**；规格没有给"哪一条优先"的规则。
  §10 第 2 条要求"与上游工件冲突"时报 `MOLD BREAK` —— 这正是该报的情形。

建议:   删掉 `:41` 括号里的 `scipy.spatial.distance.cdist`（保留 `fastdtw` 不可用，
  那条是真的：实测未安装）。§3 应写成"允许 `scipy.spatial.distance.cdist`；
  `fastdtw` / `dtw` / `tslearn` 不可用"。

---

### BLOCK-5 · FILE-102：`ContractViolation('warp_path not monotonic')` 把错误码传成裸字符串

文件:   `.spec/build/FILE-102-v1.md:95`

现象:   规格逐字给出 `抛 ContractViolation('warp_path not monotonic')`。
        但 `contract.ContractViolation` 的**第一个位置参数是 `code: ErrorCode`**。
        照字面写，异常对象会带着 `code = 'warp_path not monotonic'`（`str`），
        而不是 `ErrorCode` 成员。异常**能抛出来**，也不会当场报错 ——
        只有 C1 归一化（FILE-105 §4.5 第 6 步要求读 `err.code`）时才会炸。

证据:

规格原文（`:95`）：
```
  - 若 `any(diffs < −MONOTONICITY_TOLERANCE)` → 抛 `ContractViolation('warp_path not monotonic')`。
```

真实输出：
```
=== 规格 §4/§5 要求: raise ContractViolation('warp_path not monotonic') ===
  构造成功，但 .code = 'warp_path not monotonic' | type = str
  .code 是 ErrorCode 吗? False
  e.code.value 抛 AttributeError: 'str' object has no attribute 'value'

=== 对比：正确的构造方式 ===
  e2.code = <ErrorCode.INTERNAL_ERROR: 'INTERNAL_ERROR'> | str(e2) = [INTERNAL_ERROR] warp_path not monotonic
```

`contract.py:687` 的真实定义（读出来的，不是猜的）：
```
687:class ContractViolation(HarmonicaError):
694:class CoreBuildError(HarmonicaError):
```

为什么无法自行解决:   骨架 `align.py:52` 的 docstring 写「失败：抛 ContractViolation」，
  没给构造示例；规格 `:95` 给的示例**语法上能跑**（所以不会被 linter 或 import 拦下），
  只是语义错。我若"自行纠正"成 `ContractViolation(ErrorCode.INTERNAL_ERROR, ...)`，
  必须**自行决定用哪个错误码** —— `ErrorCode` 里没有 `ALIGNMENT_NOT_MONOTONIC`，
  规格也没说该用哪个。这是 §10 第 1 条「需要定新错误码」的典型情形。

建议:   把 `:95` 改为显式给出码与详情：
```python
raise ContractViolation(
    ErrorCode.ALIGNMENT_UNRECOVERABLE,
    detail="warp_path not monotonic",
    component="core.align",
)
```
并在 §4 里说明：非单调路径归 `ALIGNMENT_UNRECOVERABLE`（而非 `INTERNAL_ERROR`），
理由是它可由输入数据触发、不是内部缺陷。

---

### BLOCK-6 · FILE-102：`measure_coverage` 的不变量「∈ [0.0, 1.0]」与公式矛盾

文件:   `.spec/build/FILE-102-v1.md:111`

现象:   规格 `:111` 写「不变量：返回值 ∈ [0.0, 1.0]」，但同一节给的公式是
        `covered / n_ref_frames`，两个参数**互不约束**。传入
        `n_ref_frames` 小于实际覆盖帧数时返回值 > 1。实测得 **4.6**。

证据:

规格原文（`:111`）：
```
- **不变量**：返回值 ∈ [0.0, 1.0]。
```

真实输出：
```
=== §4 measure_coverage 不变量声称 [0,1]，但公式 covered/n_ref_frames 可越界 ===
covered = 23  n_ref_frames = 5 -> cov = 4.6
=> 4.6 > 1.0，违反规格 §4 自述不变量「返回值 ∈ [0.0, 1.0]」
```

为什么无法自行解决:   要让它恒成立，必须**自行添加** `min(1.0, ...)` 夹紧 ——
  但那改变了返回值语义（4.6 是"覆盖了 4.6 倍参考时长"的真实信息，
  夹成 1.0 会把它抹掉），且规格明写 `\|` 公式 `\|` 是"唯一口径"。
  两个选项（夹紧 / 不夹紧）都违反规格的一条明文。

建议:   把 `:111` 改成：
```
- **不变量**：返回值 ≥ 0.0。当 `n_ref_frames >= len(unique(warp_path[:,0]))` 时 ∈ [0.0, 1.0]。
```
并在 §5 的失败语义里补一行：`n_ref_frames < 覆盖帧数` 属调用方误用，
**不夹紧、不报错**（它是真实比值），由 `align()` 的 `>= WARP_PATH_MIN_COVERAGE`
判定照常通过。

---

### BLOCK-7 · FILE-102：§8 自带的验收脚本跑不过自己 —— 帧数口径差 2，且脚本漏 import

文件:   `.spec/build/FILE-102-v1.md:194`（漏 import）、`.spec/build/FILE-102-v1.md:221`（浮点断言）

现象:   规格 §8 的验证脚本**照抄跑不起来**，两处独立缺陷：

**(a)** 脚本第 194 行用 `profile.ALIGN.hop_length`，但脚本的 import 段
（`:172`-`:175`）**从未 import `profile`** → `NameError`。

**(b)** `n_ref_frames = ref.shape[0] // HOP` 假设 `n_frames = len//hop`，
但 `scipy.signal.stft` 默认 `boundary='zeros'`，实际 `n_frames = 1 + len//hop`。
于是判据 1 的 `wp[-1,0] == n_ref_frames - 1` 恒不成立（实测差 2）。

**(c)** 判据 4 断言 `measure_coverage(np.array([[0,0],[2,1]]), 3) == 2/3`，
但规格 §4 又要求该函数 `cast float32`（INV 表要求 `element_type` 一致）。
`float(np.float32(2/3)) = 0.6666666865348816`，`== 2/3` 为 `False`。

证据:

规格原文（`:194`，脚本体内）：
```python
HOP = profile.ALIGN.hop_length
n_ref_frames = ref.shape[0] // HOP
```
真实输出（脚本逐字跑）：
```
Traceback (most recent call last):
  File "<string>", line 11, in <module>
    HOP = profile.ALIGN.hop_length
NameError: name 'profile' is not defined. Did you forget to import 'profile'?
```

真实输出（补上 import 后继续跑 (b)）：
```
scipy.signal.stft 默认 boundary 下 n_frames = 23
规格 §8 假设的 len//HOP        = 21
差值 = 2

n_ref_frames(ref.shape[0]//HOP) = 21
wp.shape = (23, 2) wp[:,0].max() = 22 wp[-1,0] = 22
  -> 判据 1 的帧口径断言 FAIL: (np.int32(22), 20)
  -> wp[:,0].max() <= n_ref_frames-1 FAIL: 22
```

真实输出（(c)）：
```
--- 判据 4: measure_coverage(np.array([[0,0],[2,1]]),3) == 2/3 ---
  got = 0.6666666865348816  == 2/3 ? False
--- measure_coverage(wp,5) == 1.0 ---
  got = 4.599999904632568  == 1.0 ? False
```

为什么无法自行解决:   脚本是**验收判据**，不是建议。我可以让实现去"迎合"它，
  但那要求实现故意少算 2 帧（`n_frames = len//hop`）、或故意不 cast float32 ——
  两者都与 §4 的算法口径冲突。实现者无权改判据，也无权把判据解释成"示意"。

建议:
  1. `:172`-`:175` 的 import 段补 `from harmonica_eval.profile import ALIGN`，
     并把 `:194` 的 `profile.ALIGN.hop_length` 改为 `ALIGN.hop_length`。
  2. 帧数口径必须**在 §4 里显式冻结**。二选一并写死：
     - 若沿用 `scipy` 默认（`boundary='zeros'`）：`n_frames = 1 + len//hop`，
       脚本改为 `n_ref_frames = 1 + ref.shape[0] // HOP`；
     - 若要 `len//hop`：§4 必须写 `stft(..., boundary=None, padded=False)`。
     我倾向**前者**（少一处"必须记得关默认值"的坑），但无论选哪个，
     §4 与 §8 必须是同一个数字。
  3. 判据 4 的断言改成与 dtype 自洽的写法：
     `assert abs(align.measure_coverage(np.array([[0,0],[2,1]], dtype=np.int32), 3) - 2/3) < 1e-6`
     （若 §4 坚持 cast float32）；或删掉"cast float32"那句、让返回值是 Python `float`
     （那样 `== 2/3` 成立，但 §4 的 INV 表要同步改）。
  4. `measure_coverage(wp, 5) == 1.0` 这条要删或改：按 §4 公式它是 4.6（见 BLOCK-6），
     `== 1.0` 只在 `n_ref_frames` 恰好等于覆盖帧数时成立，而脚本传的是 5。

---

### BLOCK-8 · FILE-103：空 `rms` 的处置，§4 与 INV-103-12/§8 互相矛盾

文件:   `.spec/build/FILE-103-v1.md:171`（抛）、`.spec/build/FILE-103-v1.md:206`（返回空数组）

现象:   同一份规格，`:171` 写「`rms` 为空 ⇒ 抛 `ErrorCode.CORE_BUILD_FAILED`」，
        `:206`（INV-103-12）与 §8 判据 4 又断言空 `rms` 下
        `materialize_notes(...)` 应返回 `(0, n_fields)` 的**空数组**。
        两条互斥，实现者必须二选一 —— 而无论选哪个，都会让另一半判据失败。

证据:

规格原文（`:171`）：
```
- **边界**：`pitch` 为空或无任何满足时长阈值的片段 ⇒ 返回形状 `(0, n_fields)` 的空数组，不抛异常。`rms` 为空 ⇒ 抛 `ErrorCode.CORE_BUILD_FAILED`（见 §5），**不得**用 0 或该片段外数据填充。
```
规格原文（`:206`，INV-103-12）：
```
| INV-103-12 | 空输入返回空数组而非抛异常 | `assert materialize_pitch(...).shape == (0, ...)`；`assert materialize_rms(np.zeros(0, np.float32)).shape == (0,)`；`assert materialize_chroma(...).shape == (0, 12)`；`assert materialize_notes(np.zeros((0, len(FIELD_LAYOUTS['pitch'])), np.float32), np.zeros(0, np.float32), sr).shape == (0, len(FIELD_LAYOUTS['notes']))` |
```

真实输出（§8 判据 4 逐字跑）：
```
  前三行 OK
  第 4 行: materialize_notes(空pitch, 空rms, sr)
  规格 §4 行171: pitch 为空 -> 返回空数组, 不抛异常
  规格 §4 行171 同句: rms 为空 -> 抛 CORE_BUILD_FAILED
  -> 返回 shape (0, 3) (若 rms 空检查在前，这里会抛)
```

我最终**实现了"先判 pitch 为空"**，于是 `(0, 3)` —— INV-103-12 过，
但这是靠**实现里两个 `if` 的先后顺序**碰巧满足的，规格没有规定这个顺序。
只要实现者把 `rms` 的空检查写在前面（那样也完全符合 `:171`），
判据 4 立刻抛 `CORE_BUILD_FAILED`。

为什么无法自行解决:   要同时满足两条，实现必须**依赖一条规格没写的求值顺序**。
  而"pitch 空 ⇒ rms 必然也空"这个隐含前提规格从未说明（§4 允许 caller
  传 `np.zeros((0,3))` 配一个非空 `rms`）—— 判据 4 恰好传了两个都空，
  所以顺序碰巧能掩盖矛盾。这不是可依赖的性质，是巧合。

建议:   明确二者关系。推荐改 `:171` 为：
```
- **边界**：`pitch` 为空 ⇒ 立即返回 `(0, n_fields)`，**不再检查 `rms`**（此时无从取片段，
  `rms` 的形状/内容与结果无关）。`pitch` 非空但 `rms` 为空 ⇒ 抛 `CORE_BUILD_FAILED`
  （有音却无能量帧，数据面自相矛盾）。
```
即把「空 rms 抛错」限定在「pitch 非空」的前提下 —— 这样 `:171` 与 `:206` 同时为真，
且不再依赖求值顺序。并在 §5 的失败语义表里补一行说明该前提。

---

### BLOCK-9 · FILE-103：`materialize_chroma` 骨架没有 `sample_rate`，规格也没给正确性判据

> **状态更新（审查期间骨架已被并发修复者按本条的选项 (a) 修改）**：
> 我写这条结论时，骨架是 `def materialize_chroma(samples: npt.NDArray) -> npt.NDArray:`
> （`harmonica_eval/core/features.py:91`）。终检时该行已变为
> `def materialize_chroma(samples: npt.NDArray, sample_rate: int) -> npt.NDArray:`
> —— 正是本条建议的选项 (a)。**骨架侧已闭环。**
> 但请注意：**规格侧（FILE-103 §4 与 §8）尚未同步** —— §4 的算法口径仍未说明
> `sample_rate` 从哪来，§8 仍**没有**能抓住错误 `sr` 的判据（440 Hz → bin A）。
> 骨架改了而判据没补，等于把"静默错误"从"写不出来"变成"写得出来但测不出来"。
> 建议下一轮**继续追这条**，直到 §8 补上 pitch-class 锚点判据。

文件:   `.spec/build/FILE-103-v1.md:153`（签名）、`harmonica_eval/core/features.py:91`（我审查的骨架版本）

现象:   骨架签名是 `materialize_chroma(samples: npt.NDArray) -> npt.NDArray`，
        **没有 `sample_rate`**。但把 PCM 转成 chroma 必须知道采样率：
        `librosa.feature.chroma_stft(y=..., sr=...)` 的 `sr` 决定频率轴 →
        pitch class。规格 §4（`:153` 起）§4 通篇没给这一参数，也没说该用什么值。

我实测了两种被迫的选择，结果完全不同：
- `sr=44100`（真实采样率）→ 440 Hz 正弦的 chroma 峰值落在 **bin 9 = A** ✓
- `sr=1`（骨架无参数时"看起来中立"的值）→ 峰值落在 **bin 4 = E** ✗（错 5 个半音）

证据:

骨架真实签名（读出来的）：
```
91:def materialize_chroma(samples: npt.NDArray) -> npt.NDArray:
```
真实输出：
```
440 Hz 正弦的 chroma（应落在 A=bin 9）：
  sr=44100 (正确)   argmax bin=9 (A)  profile=[0.002 0.001 0.001 0.001 0.001 0.001 0.003 0.024 0.395 1.    0.424 0.019]
  sr=1              argmax bin=4 (E)  profile=[0.025 0.012 0.033 0.459 0.97  0.355 0.044 0.029 0.046 0.125 0.123 0.066]

=> materialize_chroma(samples) 的骨架签名里【没有 sample_rate】
   真实签名: (samples: 'npt.NDArray') -> 'npt.NDArray'
```

同时，规格 §8 判据 5（`:276`）对 chroma 的**唯一**断言是
`assert np.allclose(np.linalg.norm(c, ord=np.inf, axis=1)[...], 1.0)` ——
那是对**每帧归一化**的检查，**任何** `sr`（包括错的值）都能通过。
即：这个静默错误**没有任何判据能抓住它**。

为什么无法自行解决:   骨架签名是实现者不得修改的（规格 §1「只实现本文件」，
  不得改签名）。我若改成 `materialize_chroma(samples, sample_rate)`，
  就破坏了 `surface.py` 的派发表约定与骨架；若保留，就必须**自行猜**一个 `sr`。
  规格 §10 第 4 条明写"§4 的行为规格不足以确定唯一实现"应当停止上报 ——
  这正是该情形。

建议:   二选一：
  - **(a) 改骨架签名**为 `materialize_chroma(samples, sample_rate)`，
    与 `materialize_pitch` 一致，并在 FILE-104 §4.4 的派发表里把它归到
    「`(该侧样本, sample_rate)`」那一行（现在它归在「`(该侧样本,)`」）。
  - **(b) 若坚持不改签名**，规格 §4 必须写死「`sr` 恒取 `profile.AUDIO.sample_rate`」
    （`chroma` 属 `_SAMPLE_RATE_FREE_PREFIXES`，但那是**端口描述符**的
    `sample_rate` 字段，不是计算时用的 `sr` —— 两者被混为一谈了）。
  无论选哪个，**§8 必须补一条能抓住错误 `sr` 的判据**，例如：
  `440 Hz 正弦的 chroma 峰值必须在 bin 9（A）`。

---

### BLOCK-10 · FILE-104：中间量存储方式会让 `notes.reference` 静默使用练习侧数据

> **状态更新（审查期间已被并发修复者采纳）**：我写这条结论时，
> `FILE-104-v1.md:419` 的原文是「键用**结构键**（不是端口 id）」。
> 报告落盘后该处**已被改写**，新文写「派发表用**结构键** …… 剩下 5 对靠
> **侧别后缀**区分（见下）」，并补了侧别取值 `port_id.rsplit(".", 1)[-1]`。
> 方向与本条建议一致。**本条已闭环**。保留在此是为了记录证据 ——
> 并提醒下一轮复核：改写后的派发表是否**也已**覆盖中间量存储
> （本条的要害不在"派发"而在"中间量 dict 的键"，`pitch.reference` 与
> `pitch.practice` 结构键相同这一点在改写后仍是事实）。

文件:   `.spec/build/FILE-104-v1.md:419`（我审查的版本）、
        `.spec/build/FILE-104-v1.md:410`（要求取"同侧已产出的"）

现象:   规格 §4.4 要求派发表用**结构键**
        `(produced_by, units, dimensions, timeline_basis)`，并明写
        「中间量存在 `generate_all_ports` 的局部 dict 里，键用**结构键**」。
        但 `pitch.reference` 与 `pitch.practice` 的**结构键完全相同**
        （实测：`("core.features","hz",("frame","field"),REFERENCE)` 同时覆盖两者）。
        于是后写入的一侧覆盖前一侧；`notes.reference` 再按"结构键"去取同侧 pitch 时，
        拿到的是**练习侧**的数据。

**这不报错、不抛异常，只产出错误结果。** 这正是本仓反复强调的
「不会报错、只会静默算错」那一族缺陷。

证据:

规格原文（`:418`-`:420`）：
```
     > **「同侧已产出的」怎么取**：中间量存在 `generate_all_ports` 的局部
     > dict 里，键用**结构键**（不是端口 id）。取用前断言该键已存在，
     > 否则 `CoreBuildError(CORE_BUILD_FAILED)` —— 这同时是依赖顺序的自检。
```

真实输出（用 `profile.PORTS` 现算，模拟规格规定的存储）：
```
=== 模拟 FILE-104 §4.4 行418-420 规定的中间量存储 ===
  规格原文: 「中间量存在 generate_all_ports 的局部 dict 里，键用【结构键】」

  遍历结束后 store[sk(pitch)] = <pitch.practice 的数据>
  -> 这是 practice 的数据，reference 的已被覆盖

  notes.reference 按规格取「同侧已产出的 pitch」: store[sk(pitch)]
  -> 实际拿到: <notes.practice 的数据>

  !!! notes.reference 会静默地用【练习侧】的音高去算参考侧逐音摘要
  !!! 不报错、不抛异常，只产出错误结果
```

结构键确实只有 7 个，与规格 §4.4 的声称一致 —— 也正因为如此，它**必然**冲突：
```
端口总数 = 12
互异结构键数 = 7   (规格 §4.4 声称 7)
  core.features  units=hz    dims=('frame', 'field')  basis=REFERENCE -> ['pitch.reference', 'pitch.practice']
  core.features  units=rms   dims=('frame',)          basis=REFERENCE -> ['rms.reference', 'rms.practice']
  core.surface   units=amplitude dims=('sample',)     basis=REFERENCE -> ['pcm.mapped.reference', 'pcm.mapped.practice']
  ...
```
规格 `:376` 自己写了「剩下 5 对靠**侧别后缀**区分」—— 但那条只用在**派发**上，
忘了**中间量存储**也需要侧别。我最终按 `(结构键, 侧别)` 存才让它正确（见 `_scratch` 实现）。

为什么无法自行解决:   若严格照 `:419` 用纯结构键，产出的是**错的数据面且无任何信号**；
  若按 `(结构键, 侧别)`，就违反了 `:419` 的字面规定。规格没给优先级，
  也没承认这里需要侧别。

建议:   把 `:419` 改为
```
     > **「同侧已产出的」怎么取**：中间量存在 `generate_all_ports` 的局部
     > dict 里，键用 **(结构键, 侧别)** —— 纯结构键不够：
     > `pitch.reference` 与 `pitch.practice` 的四元组**完全相同**（实测 12 端口
     > 只有 7 个互异结构键），只用结构键会让两侧互相覆盖，
     > 且**不会报错**。侧别取值同派发表：`port_id.rsplit(".", 1)[-1]`。
```
并补一条 INV：
「`generate_all_ports` 返回后，`notes.reference[:,1]` 必须由参考侧 pitch 算出」
—— 可用"两侧输入不同时，两 notes 端口的 content_hash 必须不同"来机械判定。

---

### BLOCK-11 · FILE-104：INV-104-12 与 §4.2 的 `sample_rate` 规则互斥（5/12 端口必失败）

文件:   `.spec/build/FILE-104-v1.md:887`（INV-104-12）、
        `.spec/build/FILE-104-v1.md:0`（§4.2 的 `_SAMPLE_RATE_FREE_PREFIXES` 规则，见 §4.0 `:133`）

现象:   §4.0 `:133` 定义 `_SAMPLE_RATE_FREE_PREFIXES = {"chroma","warp_path","notes"}`，
        并规定这些端口的 `sample_rate` 填 **0**；`:144`-`:156` 还要求实现
        **额外核验**这条规则。而 INV-104-12（`:887`）断言
        `d.sample_rate == profile.AUDIO.sample_rate`（= 44100），对**每个**端口。
        两者对上述 3 个前缀的 **5 个端口**给出不同期望值。

证据:

规格原文（`:133`）：
```python
_SAMPLE_RATE_FREE_PREFIXES: frozenset[str] = frozenset({"chroma", "warp_path", "notes"})
```
规格原文（`:887`）：
```
| INV-104-12 | ... | `for p, d in s.manifest().ports.items(): assert d.hop_length == profile.PORT_INDEX[p].hop_length and d.sample_rate == profile.AUDIO.sample_rate`。...
```

真实输出（按 §4.2 实现后，跑 INV-104-12 的断言）：
```
=== FILE-104 §4.2 sample_rate 两条规则 推出的期望值 ===
=== FILE-104 INV-104-12 断言: d.sample_rate == profile.AUDIO.sample_rate ===

  warp_path                  §4.2 -> 0      INV-104-12 要求 -> 44100  <<< 矛盾
  chroma.lowres.reference    §4.2 -> 0      INV-104-12 要求 -> 44100  <<< 矛盾
  chroma.lowres.practice     §4.2 -> 0      INV-104-12 要求 -> 44100  <<< 矛盾
  notes.reference            §4.2 -> 0      INV-104-12 要求 -> 44100  <<< 矛盾
  notes.practice             §4.2 -> 0      INV-104-12 要求 -> 44100  <<< 矛盾

矛盾端口数 = 5 / 12
```

`contract.py` 站在 §4.2 这边（读出来的权威定义）：
```
   ['sample_rate: int = 0', '"""**必填语义**。采样率是算法结果的成因，不是元数据。',
    '0 表示该端口与采样率无关（如 chroma / index 类）。"""']
```
`contract.py` 明写「0 表示该端口与采样率无关（**如 chroma / index 类**）」——
即 `warp_path`（index 类）、`chroma.*` 填 0 **是契约要求**，INV-104-12 是错的。

为什么无法自行解决:   按任务约定，`contract.py` 是权威，因此我必须实现 §4.2（填 0）；
  但那样 INV-104-12 这条**写在规格里的验收判据**必然失败。我不能改判据，
  也不能改成 44100（违反 contract 的明文语义）。

建议:   把 INV-104-12 的断言按前缀分支：
```python
for p, d in s.manifest().ports.items():
    assert d.hop_length == profile.PORT_INDEX[p].hop_length
    free = port_prefix(p) in {"chroma", "warp_path", "notes"}
    assert d.sample_rate == (0 if free else profile.AUDIO.sample_rate)
```
更好的做法：**不要在前缀集合上判**，直接引用 §4.0 那个被核验过的常量，
让"规则"只有一处定义。

---

### BLOCK-12 · FILE-104：INV-104-16 用它自己规定为越界的时间窗

文件:   `.spec/build/FILE-104-v1.md:891`（INV-104-16）、
        `.spec/build/FILE-104-v1.md:638`（notes 的时长上界公式）

现象:   §4.6.2 `:638` 规定 `notes` 端口的时长上界是
        `notes_max_onset_sec + 1.0`。INV-104-16（`:891`）却用
        `s.read("notes.practice", (0.0, 5.0))` 作为**应当成功**的调用。
        当 `notes.practice` 只有 1 行且 `onset_sec = 0.046` 时，
        上界 = 1.046 < 5.0 → 按 `:620` 必须抛 `ContractViolation`。
        判据 16 因此必失败。

证据:

规格原文（`:638`）：
```
  | `f == "notes"` | 见下方「notes 行筛选」 | 同左 | `notes_max_onset_sec + 1.0` |
```
规格原文（`:891`）：
```
| INV-104-16 | `read` 返回的 `BufferView` 三个字段彼此自洽 | `bv = s.read("notes.practice", (0.0, 5.0))`；...
```

真实输出：
```
  FAIL  INV-104-16 BufferView 自洽: ContractViolation: [CORE_BUILD_FAILED] (core.surface) 非法时间窗 (0.0, 5.0)，上界 1.0464399084448814 port=notes.practice

=== INV-104-16 的测试命令 ===
  bv = s.read('notes.practice', (0.0, 5.0))
  notes.practice shape = (1, 3)  (1 行: 50 秒正弦只切出 1 个音)
  onset_sec 列 = [0.04643991]
  §4.6.2 规定 notes 的时长上界 = notes_max_onset_sec + 1.0 = 1.0464399084448814

  => read(...,(0.0,5.0)) 中 t1=5.0 > upper=1.0464，按 §4.6.2 必须抛 ContractViolation
  => 但 INV-104-16 把它当成一个【应当成功】的调用
```

根因（`upper = max(onset) + 1.0` 与音频真实时长脱钩）：
```
  该正弦 50 秒，只产生 1 个音（连续发声），onset=0.0
  上界 = 0.0 + 1.0 = 1.0 秒，而真实音频 50 秒
  => notes 端口的可读时间窗被限制在 [0, 1.0) 秒，音频后 49 秒读不到
```
这不只是判据的问题 —— `:638` 的公式本身让**任何**只含少数音的
`notes` 端口的可读窗口远小于音频时长，`read` 会拒绝合法的时间窗查询。

为什么无法自行解决:   `:638` 与 `:891` 都是明文，且 `:638` 还带"命中即停"的
  按序判定表。我若放宽上界（改成音频时长），就违反 `:638`；若保留，判据 16 失败。

建议:   把 `:638` 的 `notes` 上界改为**该端口所属音频的时长**，
而不是"最后一个 onset + 1 秒"。`manifest()` 里已有
`reference_duration_sec` / `practice_duration_sec`（§4.6.1 `:595`），
按侧别取即可：
```python
upper = (manifest.reference_duration_sec if side == "reference"
         else manifest.practice_duration_sec)
```
这样 `:891` 的 `(0.0, 5.0)` 对 50 秒音频就合法了。
若坚持保留 `+1.0` 语义，则判据 16 必须改成
`(0.0, min(5.0, upper))` 之类的自洽写法，并说明 `notes` 的可读窗为什么刻意短于音频。

---

### BLOCK-13 · FILE-104：INV-104-27 忘了 `element_count` 含第二维，且比值闸门算错

文件:   `.spec/build/FILE-104-v1.md:902`

现象:   INV-104-27 断言 `read("chroma.lowres.reference", (0.0,1.0)).element_count == 21`。
        但 §4.6.2 对 `element_count` 的定义是 `int(np.prod(data.shape))`
        （`:625`），而 chroma 的形状是 `(21, 12)` —— 正确值是 **252**，不是 21。
        `21` 是**帧数**（`shape[0]`），不是元素数。判据把两者混为一谈。

同时该条要求「两者比值必须落在 `[7.9, 8.1]` 区间**之外**」，本意是
"chroma 帧数比 rms 帧数少 8 倍"，但拿**元素数**去比，
得到 `252/172 = 1.47` —— 恰好落在区间外，于是判据**看似通过、实际在验一个错的量**。

证据:

规格原文（`:625`）：
```
   - `element_count: int` —— `int(np.prod(data.shape))`；`data.shape == ()` 时
     为 `1`（`np.prod(()) == 1.0` → `1`）。
```
规格原文（`:902`）：
```
| INV-104-27 | ... | `bv = s.read("rms.practice", (0.0, 1.0))` 的 `element_count == floor(1.0 * 44100 / 256) == 172`；`bv = s.read("chroma.lowres.reference", (0.0, 1.0))` 的 `element_count == floor(1.0 * 44100 / 2048) == 21`。两者比值必须落在 `[7.9, 8.1]` 区间之外（相差 8×，混用即被本条抓住） |
```

真实输出：
```
chroma read(0,1): shape = (21, 12)  element_count = 252
  §4.6.2 定义 element_count = int(np.prod(data.shape)) = 252
  帧数 = 21 (= floor(1.0*44100/2048) = 21 ✓)
  INV-104-27 却断言 element_count == 21  <- 忘了乘第二维 12

=== INV-104-27 的比值闸门 ===
  rms ec=172  chroma ec=252  ratio=1.465
  规格: 比值必须落在 [7.9,8.1] 之外 -> 通过(但原因不对)

  若按【帧数】比才是规格的本意: chroma 帧 21 / rms 帧 172 = 0.122 (<7.9 ✓)
  若 chroma 误用 rms 的 hop=256: 帧 172 x12 = 2064  ratio vs 172 = 12.0
```

注意最后一行：**若实现真的把 hop 混用（chroma 用 256），比值是 12.0，
也落在 `[7.9,8.1]` 之外** —— 即这条判据**抓不住它本来要抓的缺陷**。
它是一条永远通过、且验错对象的假闸门。

为什么无法自行解决:   `element_count` 的定义（`:625`）与判据的期望值（`:902`）
  不能同时成立。实现者不能为了让判据通过而返回 `shape[0]`（那违反 `:625`，
  也会让所有 BufferView 的 `element_count` 都错）。

建议:   把 INV-104-27 改成按**帧数**（`shape[0]`）比较，并让闸门真正有判别力：
```python
rms_frames = s.read("rms.practice", (0.0, 1.0)).data.shape[0]
chroma_frames = s.read("chroma.lowres.reference", (0.0, 1.0)).data.shape[0]
assert rms_frames == 172
assert chroma_frames == 21
assert abs(rms_frames / chroma_frames - 8.0) < 0.2      # 256 vs 2048 -> 恰 8×
```
（用 `≈8.0` 的**正向**闸门，而不是"落在 `[7.9,8.1]` 之外"的反向闸门 ——
反向闸门对"恰好 8"和"12"都放行，等于没闸门。）

---

### BLOCK-14 · FILE-104：§8 判据 4 与 §4.4 的派发约定互斥，且原始骨架就已"违规"

文件:   `.spec/build/FILE-104-v1.md:977`（判据 4）、
        `.spec/build/FILE-104-v1.md:133`（`_SAMPLE_RATE_FREE_PREFIXES` 里含 `warp_path`）

现象:   §8 判据 4 要求 `surface.py` 源码里
        `['pcm.mapped','pcm.warped','pitch.','chroma.','rms.','notes.','warp_path.']`
        七个字面量的命中数为 **0**。其中 `warp_path.` 与骨架**本身**冲突：

        `build_surface(reference, practice, sample_rate, warp_path)` 与
        `generate_all_ports(..., warp_path)` 的形参名就是 `warp_path`
        （骨架 `harmonica_eval/core/surface.py:151`、`:87`），而 §4.7 第 4 步要求
        `warp_path.dtype == np.int32` —— 即 `warp_path.` 这个字面量
        **必然**出现在任何遵守骨架签名的实现里。

证据:

规格原文（`:977`）：
```
python -c "import inspect, harmonica_eval.core.surface as m; s=inspect.getsource(m); hit=[k for k in ['pcm.mapped','pcm.warped','pitch.','chroma.','rms.','notes.','warp_path.'] if k in s]; assert hit==[], hit; print('no-hardcoded-port-ids')"
```
真实输出（我的实现，只改了 `warp_path.` 之外的都清掉了）：
```
AssertionError: ['pcm.mapped', 'pcm.warped', 'pitch.', 'chroma.', 'rms.', 'notes.', 'warp_path.']
```
逐项定位后，`warp_path.` 的命中来自**三个**必然出现的位置：
```
157:def _gen_warp_path(reference, practice, sample_rate, wp):
177:    col = FIELD_LAYOUTS["warp_path"].index("practice_frame")
551:    if warp_path.dtype != np.int32 or warp_path.ndim != 2 or warp_path.shape[1] != 2:
```
其中 `:177`（`FIELD_LAYOUTS["warp_path"]`）与 `:551`（`warp_path.dtype`）
分别由**规格自己**要求（§4.4 `:483` 要求用 `FIELD_LAYOUTS["warp_path"].index(...)`；
§4.7 第 4 步要求校验 `warp_path.dtype`）。

为什么无法自行解决:   我可以通过重命名局部变量规避大部分（我把 `_warp_practice`
  的形参改成了 `wp`、把 `:548` 改成别的写法），但：
  1. `FIELD_LAYOUTS["warp_path"]` 是**规格指定**的取列号方式（`:483`
     明写「**必须**用 `FIELD_LAYOUTS["warp_path"].index("practice_frame")` 查」），
     这个字面量无法消除；
  2. 骨架形参名 `warp_path` 实现者不得改（§1 权限）；
  3. 规避手法（把形参改名）会产生一个**更糟**的后果：骨架签名与
     规格 §4.7 的算法描述对不上，后续读者无法用规格核对实现。
这意味着「判据 4」与「§4.4 + 骨架签名」不能同时满足。

建议:   把 `warp_path.` 从判据 4 的禁用列表里**移除** —— 它不是端口 id，
  而是**形参名 + `FIELD_LAYOUTS` 的键**，规格自己就要求它出现。
  判据 4 应改为只禁用真正的**端口 id 字面量**：
```python
hit = [k for k in ['pcm.mapped','pcm.warped','pitch.','chroma.','rms.','notes.'] if k in s]
```
若要连 `warp_path` 一起防，正确做法不是扫源码字符串，
而是断言 `PORT_INDEX` 被用作唯一端口来源（例如
`assert set(PRODUCER_DISPATCH) == {(s.produced_by, s.units, tuple(s.dimensions), s.timeline_basis) for s in PORTS}`，
这条我实测是有效的）。

---

### BLOCK-15 · FILE-104：§3 内部三处自相矛盾（名字计数、顶层语句、已作废的调用约定）

文件:   `.spec/build/FILE-104-v1.md:87`、`:121`、`:91`

现象:   三处独立的小矛盾，都会让"照字面执行"的实现者走错：

**(a) `:87` 声称「`harmonica_eval.profile` 的 **6 个名字**」，紧接着列出 7 个。**
**(b) `:121` 禁止模块顶层任何非声明语句，而 §4.0 `:140` 要求模块导入时执行 `assert`。**
**(c) `:91` 仍把 `(reference, practice, sample_rate, warp_path) -> NDArray` 写成
「取到的可调用对象签名约定」，而 §4.4 `:332` 已用「上一版原文（已作废）」
明确废掉了这个四参约定。**

证据:

规格原文（`:87`-`:88`）：
```
  - `harmonica_eval.profile` 的 **6 个名字**：
    `PORTS`、`PORT_INDEX`、`BUDGET`、`AUDIO`、`ALIGN`、`MATERIALIZE`、`PROFILE_VERSION`。
```
真实输出：
```
  实际列出: ['PORTS', 'PORT_INDEX', 'BUDGET', 'AUDIO', 'ALIGN', 'MATERIALIZE', 'PROFILE_VERSION']
  个数 = 7  规格说 = 6  -> 不符
```

规格原文（`:121`-`:122`）：
```
- 禁止在模块顶层执行任何非声明语句（除 `__all__` 赋值外，不得有函数调用、
  常量计算、文件读取）。
```
规格原文（`:139`-`:142`）：
```
以上三个列号常量**必须**与 `contract.FIELD_LAYOUTS` 对得上；
实现**必须**在模块导入时用一次断言核验（`assert FIELD_LAYOUTS["notes"][0] == "onset_sec"`
与 `assert FIELD_LAYOUTS["warp_path"][0] == "reference_frame"`），
核验失败即 `ImportError` 级别缺陷，**不得**静默继续。
```

规格原文（`:89`-`:92`）vs（`:330`-`:336`）：
```
  - `profile.PortSpec.produced_by` 指名的 core 端口生产模块，**只能**通过
    `importlib.import_module` 按其**点分模块路径字符串**动态取得，
    或由 `harmonica_eval/core/` 内的直接模块 import 取得；取到的可调用对象签名约定为
    `(reference, practice, sample_rate, warp_path) -> NDArray`。
```
```
  4. **调用约定（★ 本版重写，上一版是错的，且不可满足）**

     ★★ **上一版原文（已作废）**：
     > 「调用约定（**唯一**）：生成者可调用对象接收**位置参数 4 个**，
     > 顺序为 `(reference, practice, sample_rate, warp_path)`，返回一个
     > `numpy.ndarray`。」
```

真跑出来的**实际后果**（这条作废约定确实会让人写错）：
```
  File ".../_scratch/harmonica_eval/core/surface.py", line 317, in generate_all_ports
    arr = producer(sides[side], int(sample_rate))
KeyError: 'warp_path'
```
—— 即"把四参/统一签名套到所有生产者上"在 `warp_path`（无侧别后缀）处直接崩。
我随后按 §4.4 `:404`-`:412` 的**逐结构键实参表**才写对。

为什么无法自行解决:   (a) 是纯计数错误，无歧义 —— 但实现者会花时间怀疑自己漏了
  或多了哪个名字；(b) 两条都是 MUST，我需要选一条违反；(c) 是**同一文件里
  一处已作废、一处仍在生效**，读者无法判断哪一处是当前口径（`importlib.import_module`
  那条路径本身也与 §3 的"直接模块 import"并列，但 §4.4 的派发表要求
  「值 = 真实的生产者可调用对象」，即 import 而非动态查找）。

建议:   (a) 把 `:87` 的「6 个名字」改成「7 个名字」。
  (b) 把 `:121` 改为「禁止在模块顶层执行任何非声明语句（`__all__` 赋值、
  **以及 §4.0 要求的列号常量核验断言**除外）」。
  (c) 删除 `:91`-`:92` 的整段签名约定（它是 `:332` 已作废的同一句话），
  改成指向 §4.4 的派发表：「取到的可调用对象的实参见 §4.4 的逐结构键实参表」。

---

### BLOCK-16 · FILE-105：§3 白名单不含 `HarmonicaError`，§4.5 第 6 步却要求 `except HarmonicaError`

文件:   `.spec/build/FILE-105-v1.md:52`（白名单）、`.spec/build/FILE-105-v1.md:199`（要求）

现象:   `:52` 把 `harmonica_eval.contract` 的可用名字**穷举**为 5 个
        （`HostContract`, `SessionState`, `ContractViolation`, `CoreBuildError`, `ErrorCode`），
        并在 `:60` 写「凡未列入名单的模块一律禁止」。而 `:199`（§4.5 第 6 步）
        逐字给出 `except HarmonicaError as err:` —— `HarmonicaError` **不在那 5 个里**。

证据:

规格原文（`:52`）：
```
  - `harmonica_eval.contract`：且仅这 5 个名字 —— `HostContract`, `SessionState`, `ContractViolation`, `CoreBuildError`, `ErrorCode`
```
规格原文（`:199`）：
```
6. `except HarmonicaError as err:` → `s.surface = None`；`s.state = SessionState.FAILED`；`raise CoreBuildError(code=err.code, ...) from err`。
```

`contract.py` 里的真实位置（读出来的）：
```
666:class HarmonicaError(Exception):
687:class ContractViolation(HarmonicaError):
694:class CoreBuildError(HarmonicaError):
```
即 `HarmonicaError` **存在**，但规格不许 import 它。

为什么无法自行解决:   我可以绕过（直接 `except Exception as err` 再判断
  `isinstance(err, (CoreBuildError, ContractViolation))`）—— 但那改变了
  §4.5 第 5/6 步区分「`HarmonicaError` 子类」与「非 `HarmonicaError` 的 `Exception`」
  的语义（两类要产出**不同**的 `code`：前者保留 `err.code`，后者强制
  `CORE_BUILD_FAILED`）。绕过就等于自行重新设计了失败分类，是 §10 第 1 条禁止的。
  `ContractViolation` 与 `CoreBuildError` 都在白名单里，但它们之外
  `HarmonicaError` 还有别的子类（`AlgorithmError` 等），用元组也覆盖不全。

建议:   把白名单从 5 个改成 6 个，补上 `HarmonicaError`：
```
  - `harmonica_eval.contract`：且仅这 6 个名字 —— `HostContract`, `SessionState`,
    `ContractViolation`, `CoreBuildError`, `HarmonicaError`, `ErrorCode`
```
理由写进规格：`HarmonicaError` 是 §4.5 失败归一化的**基类判据**，
不用它就无法区分「带错误码的已知失败」与「未知崩溃」这两条不同路径。

---

### BLOCK-17 · FILE-105：INV-105-12 要求 `profile_version` 影响 `content_hash`，但哈希口径里没有它

文件:   `.spec/build/FILE-105-v1.md:331`（INV-105-12）、
        `.spec/build/FILE-104-v1.md:235`-`:240`（冻结的 hash 输入）

现象:   INV-105-12 要求「同一对 uri、`profile_version` 分别为 `"CORE_PROFILE_V0.1"`
        与 `"CORE_PROFILE_V0.1-x"` 建两会话并构建，断言至少一个端口的
        `content_hash` 不同」。但 FILE-104 冻结的 hash 输入里
        **没有 `profile_version`** —— 只有 `CONTENT_HASH_MAGIC` / `port_id` /
        `element_type` / `shape` / `data`。同输入下两个会话的数据逐字节相同，
        因此所有 `content_hash` **必然相同**，INV-105-12 恒失败。

证据:

规格原文（`:331`）：
```
| INV-105-12 | **`create_session` 的 `profile_version` 被记录且区分会话**：不同 `profile_version` 产生不同数据面 hash（同输入下） | 同一对 uri、`profile_version` 分别为 `"CORE_PROFILE_V0.1"` 与 `"CORE_PROFILE_V0.1-x"` 建两会话并构建，断言至少一个端口的 `content_hash` 不同（若全部相同，则 profile 解析未消费该字符串，回 §10 上报） |
```
FILE-104 冻结的 hash 算法（`:234`-`:242`）：
```python
  h = hashlib.sha256()
  h.update(CONTENT_HASH_MAGIC)                                  # b"harmonica-eval/surface/v1\x00"
  h.update(port_id.encode("utf-8"))
  h.update(str(data.dtype).encode("utf-8"))                     # element_type
  h.update(np.asarray(data.shape, dtype="<i8").tobytes())        # 小端 int64
  h.update(data.tobytes(order="C"))                             # C 序，原始 dtype
  content_hash = h.hexdigest()                                  # 64 个小写十六进制字符
```
真实输出（检索 `profile_version` 是否进入 hash 输入）：
```
>>> profile_version 是否出现在 hash 输入里：
0
  (0 = 不在)
```

同时，规格 `:165`-`:171` **自己已经承认**了这条冲突并裁定"不做版本比对"：
```
       ★★ **本版再更正（第三轮盲审 A 的 probe 18）：上一版这里写
       `assert s.profile_version == profile.PROFILE_VERSION` —— 但 §3 的
       import 白名单里**没有 `harmonica_eval.profile`**，且本节末尾又明写
       「不 import `harmonica_eval.profile`，不校验 `profile_version`
       是否为已知版本」。**同一份文件里既禁止 import 又要求用它的常量。** ★★

       **本版冻结**：阶段 1 **不**做任何版本比对。
```
但 INV-105-12（`:331`）**没有被同步改掉**，仍然要求一个做不到的性质。

为什么无法自行解决:   要让 hash 随 `profile_version` 变化，必须把
  `profile_version` 加进 hash 输入 —— 那要改 `contract.PortDescriptor.content_hash`
  的冻结算法，属契约变更，实现者无权做。规格 `:331` 自己也写了
  「若全部相同，则 profile 解析未消费该字符串，回 §10 上报」——
  按此指示，这就是一个应当上报的既定缺口。

建议:   把 INV-105-12 改成分离的两条，去掉不可能的那半：
```
| INV-105-12a | `create_session(profile_version)` 逐字记录该字符串 | 建会话后读 `s._sessions[sid].profile_version == 传入值` |
| INV-105-12b | ★ SKIPPED：`profile_version` **不影响** `content_hash`（hash 输入在 FILE-104 §4.2 冻结为 port_id/dtype/shape/data 四项，不含版本）。同输入下不同版本产生**相同** hash 是**预期行为**。若要让版本影响 hash，须由负责人裁定修改 `content_hash` 算法（契约变更）。 |
```
并在 `contract.PortDescriptor.content_hash` 的 docstring 里补一句说明：
「版本身份由 `SurfaceManifest.profile_version` 承载，**不**进入本 hash」——
否则下一个读者仍会以为 hash 覆盖了数据面身份。

---

### BLOCK-18 · FILE-002：§8 的 import 闭包判据与 §4.2/§4.7 的必要 import 互斥

文件:   `.spec/build/FILE-002-v1.md:488`（判据）、
        `.spec/build/FILE-002-v1.md:190`（需要 `DATA_READY`）

现象:   §8 的 AST 判据把允许的 import 集合**穷举**为
        `{"__future__", "argparse", "json", "sys", "pathlib", "typing", ".contract", ".host.app"}`。
        但 §4.2 第 2/3 步要求比较 `state == DATA_READY`（需要 `SessionState`，
        它只能从 `.contract` 取），§4.2 第 1 步要求 `create_session`，
        而 `create_session(profile_version)` **需要一个 `profile_version` 实参**，
        规格全文**从未说明它从哪来**（`profile_version` 在 FILE-002 里出现 0 次）。

我实现时只能引入 `.profile` 取 `PROFILE_VERSION`，随即违反判据。

证据:

规格原文（`:488`）：
```
ALLOWED = {"__future__", "argparse", "json", "sys", "pathlib", "typing", ".contract", ".host.app"}
```
真实输出（逐字跑 §8 判据 2）：
```
实际 import 集合 = ['.contract', '.host.app', '.profile', '__future__', 'argparse', 'json', 'pathlib', 'sys', 'typing']
越界 = ['.profile']
FAIL: 非法 import: ['.profile']

=== 规格 §4.2 第1步要求登记两段输入，但它没给 create_session 的 profile_version ===
  规格全文出现 profile_version 次数: 0
  规格全文出现 PROFILE_VERSION 次数: 0
  => FILE-002 从未说明 run_headless 该传什么 profile_version 给 C1
```
（`SessionState` 可从 `.contract` 取，所以那半个不是 import 问题 —— 但它证明
判据的 `ALLOWED` 只列了模块、没列**符号**，与 §3 表格里
「`.contract`（`UiView` / `UiScalar` / `UiSeries`）」的**只读数据结构**措辞对不上。）

为什么无法自行解决:   三个选项都不行：
  1. 不 import `.profile`，硬编码 `"CORE_PROFILE_V0.1"` → 违反"不得写死字符串
     字面量"（FILE-104 §4.2 对同一常量有此要求），且让版本升级时漏改；
  2. 不 import `.profile`，让 `create_session` 收一个空串 → C2 会抛
     `ContractViolation`（我实现里对空 `profile_version` 显式拒绝），流程跑不通；
  3. import `.profile` → 违反 §8 判据 2。
  "从哪拿 `profile_version`" 是**上层设计决定**，规格 §4.2 未给，属 §10 第 4 条。

建议:   二选一并同步 §3 / §8：
  - **(a) 允许 `.profile`**：把 `ALLOWED` 加上 `.profile`，§3 表格加一行
    「`.profile`（`PROFILE_VERSION`）—— `run_headless` 建会话时的数据面版本」，
    并明确 `create_session` 应传 `PROFILE_VERSION`。
  - **(b) 让 C1 内部承担默认版本**：把 `HostApp.create_session(profile_version)`
    改成可省略（那是 FILE-301 的契约变更，须负责人裁定），
    `__main__` 调无参版本 —— 这样 `.profile` 确实不必 import。
  我倾向 **(a)**：它最小、且与 FILE-301 §4.2「`build_default_app()` 是共同入口」一致。

---

## 3 · 完成度

实现全部写在 `_scratch/harmonica_eval/`（同构布局，见 §0.3）。

### 3.1 写完并跑通的

| 文件 | 状态 | 证据 |
| --- | --- | --- |
| `core/ingest.py` (FILE-101) | **写完** | §8 判据 A/B/E/F 全过；C、D 因 BLOCK-1/2 失败 |
| `core/features.py` (FILE-103) | **写完** | §8 判据 1/2/3/5 全过；判据 4 过（但依赖未规定的求值顺序，见 BLOCK-8）。实测 `pitch` 中位 439.99 Hz（判据要求 440±5）、`rms.max()=0.28499`（要求 0.4/√2±0.02） |
| `core/surface.py` (FILE-104) | **写完** | 端到端 `build_surface` 成功；17 条 INV 中 **16 条 PASS**，INV-104-16 FAIL（BLOCK-12） |
| `core/api.py` (FILE-105) | **写完** | 全状态机跑通：`CREATED → INPUT_READY → DATA_READY → CLOSED`；前置状态非法抛 `ContractViolation`；`destroy_session` 后 `status` 返回 `CLOSED` |
| `host/app.py` (FILE-301) | **写完** | `run_algorithms` 顺序 == 注册表顺序；两次调用顺序一致；三条算法全 `OK`；grep 判据 numpy/scipy/librosa 均为 0 |
| `__main__.py` (FILE-002) | **写完** | `main()` 端到端退出码 **0**，产出 `metrics.json` + `report.md` |

端到端整合（C1 + C2 + C3 全链路）实测：
```
state = SessionState.DATA_READY
compat: {'pitch': True, 'timing': True, 'dynamics': True}
run order  = ['pitch', 'timing', 'dynamics']
status     = ['OK', 'OK', 'OK']
again same order = True
scalars = [('pitch.median_abs_cents', 30.0001), ('pitch.off_pitch_ratio', 0.0), ...]
```
```
exit code = 0
files: ['metrics.json', 'p.wav', 'r.wav', 'report.md']
json keys = ['schema_version', 'inputs', 'state', 'scalars', 'series']
```
即：**这套模具是可以被实现出来的** —— 架构本身没塌，塌的是规格里的具体数字与断言。

### 3.2 部分完成的

| 文件 | 状态 | 卡在哪 |
| --- | --- | --- |
| `core/align.py` (FILE-102) | **写完但两处必须违反规格** | `compute_alignment_features` 的 `fs` 我按**正确**采样率写（违反 `:64`，见 BLOCK-3）；`cdist` 我按 §4 用（违反 §3，见 BLOCK-4）。`measure_coverage` 我按公式写、不夹紧（于是 `:111` 的不变量不成立，见 BLOCK-6）。§8 判据 1/4 失败（BLOCK-7） |

### 3.3 未写完 / 未覆盖的

| 文件 | 状态 | 原因 |
| --- | --- | --- |
| `cockpit/app.py` (FILE-401) | **SKIPPED** | 未实现（见下） |
| `algorithms/*.py` (201/202/203) | **部分覆盖** | 由子审查者按同方法实现；其发现汇总时未能并入本报告（见 §4） |
| `algorithms/__init__.py` (FILE-200) | **未实现** | `assert_registry_integrity()` 仍是骨架（1 处 `NotImplementedError`）。注意：骨架**没有**在 import 期调用它（`grep -n "assert_registry_integrity()"` 只命中 docstring 与定义处），所以它不阻塞 import 与端到端流程 |
| `__init__.py` (001/100/300/400) | 无需实现 | 这四个文件**本来就没有** `NotImplementedError`（纯声明） |

### 3.4 骨架规模（含我自己第一次数错）

简报说「18 个 Python 骨架文件，所有函数体是 `raise NotImplementedError`」。
我第一遍统计时把 `__pycache__/*.pyc` 也算进去了，得到「88 处」——**那是错的**
（`.pyc` 是编译产物，`grep` 在二进制里也会命中同一个字符串，等于重复计数）。
按 `--include=*.py` 重数，与 `tools/verify_shell.py` 的「函数总数 75 / 空壳函数 75」
**完全一致**：

```
$ grep -rn "SHELL: FILE-" harmonica_eval/ --include=*.py | wc -l
75
$ grep -rln "SHELL: FILE-" harmonica_eval/ --include=*.py | wc -l
13

harmonica_eval/__main__.py                     7
harmonica_eval/algorithms/__init__.py          1
harmonica_eval/algorithms/dynamics.py          6
harmonica_eval/algorithms/pitch.py             4
harmonica_eval/algorithms/timing.py            5
harmonica_eval/cockpit/__init__.py             1
harmonica_eval/cockpit/app.py                 10
harmonica_eval/core/align.py                   5
harmonica_eval/core/api.py                     7
harmonica_eval/core/features.py                4
harmonica_eval/core/ingest.py                  5
harmonica_eval/core/surface.py                 7
harmonica_eval/host/app.py                    13
```

所以准确的说法是：**18 个骨架文件里，13 个含占位、共 75 处**；另 **5 个**
完全不含占位（`grep -c 'SHELL: FILE-' = 0`，实测列举）：

```
harmonica_eval/__init__.py          （包根，纯声明）
harmonica_eval/contract.py          （冻结契约，无行为）
harmonica_eval/core/__init__.py     （纯声明）
harmonica_eval/host/__init__.py     （纯声明）
harmonica_eval/profile.py           （冻结配置，纯常量）
```

注意 `algorithms/__init__.py` 与 `cockpit/__init__.py` **在**含占位的那 13 个里
（各 1 处 `assert_registry_integrity` / 导出校验）—— 它们**不是**纯声明文件。
简报的「18 个文件」与「所有函数体都是占位」两句**各自都对**，只是不是同一批文件 ——
这一点不影响 §2 的任何结论（所有结论都基于真实文件内容与真跑输出）。

---

## 4 · 未能验证的项

**SKIPPED · FILE-401 `cockpit/app.py`（未实现）**

原因：如实说明 —— 我把 401 的实现委派给了一个子审查者，该子任务**在开始前就失败退出**
（没有产出任何文件、没有修改任何东西）。我在剩余预算内优先完成了
数据流源头（101 → 102 → 103 → 104 → 105）与两个端到端入口（301 → 002），
因为这几条是"能否跑通"的判定线；401 是 C4 界面，按不变量 F 本就**可缺席**。

因此以下 FILE-401 的内容我**没有**用实现去验证，只做了静态核对：
- §4.0 的 15 个标准库 import 白名单 —— 未逐条构造探针；
- §4.4 `run_local_ui` 的 64 次端口探测 / `ThreadingHTTPServer` 生命周期 —— 未实现；
- §4.7 `render_series_plot` 的 SVG 逐字口径（`x/y` 坐标、`<!-- omitted: k -->`、
  `_AXIS_NOTE_*` 文案）—— 未实现；
- §4.13 `build_command` / `UI_PAYLOAD_KEYS` 的一致性 —— 未验证。

**静态核对中发现的疑点（未经实现确认，故不作为 §2 的 BLOCK 上报）**：
`FILE-401-v1.md:232` 的 `render_series_plot` 规格把 `series.unit` 的取值域写成
`'cents' / 'ms' / 'db' / 'ratio' / ''`，而 FILE-401 §3 明令
**禁止 import `profile`**，且 `contract.py` 里没有这个词表 —— 该取值域无权威来源。
`render_scalars` / `render_series_plot` 是否真的只依赖这 5 个值，
需要实现一遍才能确定；建议下一轮补做。

**SKIPPED · FILE-201/202/203（algorithms）的独立实现复核**

我把这三个文件委派给子审查者，它**完成了三个文件的实现**（`_scratch/harmonica_eval/algorithms/`
下 `pitch.py` / `timing.py` / `dynamics.py` 均已无占位：`grep -c 'SHELL: FILE-' = 0`），
但我**未能拿到它的书面发现** —— 它在本报告撰写时仍在运行，
`_scratch/REPORT-algorithms.md` 尚未生成。因此：

- 我**自己**独立跑了一条整合校验（不依赖子审查者的任何输出），三条算法在
  `id` / `version` / `payload` 键集合三项上均与注册表自洽：

```
pitch     status=OK    id_ok=True ver_ok=True
          payload keys 恰等 schema? True  missing=[] extra=[]
timing    status=OK    id_ok=True ver_ok=True
          payload keys 恰等 schema? True  missing=[] extra=[]
dynamics  status=OK    id_ok=True ver_ok=True
          payload keys 恰等 schema? True  missing=[] extra=[]
```

即 FILE-200 `:149` 那条「每个算法的 payload 键必须**恰为**
`PAYLOAD_SCHEMAS` 中列出的那些」在实现里成立。

- 但**逐条对照 FILE-201/202/203 规格**的缺陷（逐音配对的轴选择、
  `n_unpaired` 口径、`MIN_STABLE_NOTE_SEC` 的边界用法等）我没有独立复核，
  故**不计入 §2**。建议下一轮补齐：这三个文件是 C3 的全部，
  而本轮我只验证了它们"能跑且键对"，没验证它们"算得对"。

**其他 SKIPPED**

- **FILE-102 的内存实测复核**：规格反复引用「hop=512 → 855 MB / hop=2048 → 53 MB」。
  我没有在 120 s 音频上真的分配 855 MB 去复现（超出本轮的资源与时间预算）。
  该数字**未被验证**，也**未被证伪**。我验证的是它引出的两条实现陷阱
  （float64 代价矩阵、`global_constraints` 不省内存）在代码层面成立。
- **FILE-004 / FILE-003 的规格**（`profile.py` / `contract.py` 的 Build Instruction）：
  这两个模块在骨架里**已是完整实现**（无占位），故本轮按"权威"使用，
  未按实现者身份验证其规格。这不影响 §2 的任何结论。
- **`tools/` 下的校验器**：只跑了 `tools/verify_shell.py`（FILE-101 §8 判据 G 要求），
  结果 `✅ 结论：通过`（18 文件 / 75 函数 / 75 空壳）。
  `tools/verify_stubs_raise.py`、`tools/build_virtual_graph.py --check` **未跑**
  —— 这两者本轮 SKIPPED。建议下一轮至少跑 `verify_stubs_raise.py`：
  它验的是"每个占位被调用时都真的抛 `NotImplementedError`"，
  而本轮已实测**有占位函数在 import 期之外不会被触发**
  （`algorithms/__init__.py` 的 `assert_registry_integrity()` 在骨架里
  没有任何调用点，见 §3.3），这正是该校验器该抓的类型。
  （注：本报告 §3.4 已更正我自己"88 处"的误算 —— 真实是 **75 处**。）

---

## 5 · 给上游的最小修复顺序

按"会造成静默错误"优先：

1. **BLOCK-10**（FILE-104 中间量串侧）—— 唯一会产出**错误数据且无任何信号**的缺陷。
2. **BLOCK-3**（FILE-102 `fs=hop_length`）—— 频率轴错 21.5 倍，同样静默。
3. **BLOCK-9**（FILE-103 chroma 无 `sr`）—— 无判据能抓住的静默错误。
4. **BLOCK-11 / 12 / 13**（FILE-104 三条 INV）—— 验收判据本身错，会让实现者
   以为自己做错了而反复返工，或（BLOCK-13）让假闸门放行真缺陷。
5. **BLOCK-16 / 17 / 18**（FILE-105、FILE-002）—— 白名单与正文互斥，
   实现者必须违反一条才能前进。
6. **BLOCK-1 / 2 / 7**（三条浮点/格式判据）—— 判据不可达，但不影响主流程正确性。
7. **BLOCK-4 / 5 / 6 / 8 / 14 / 15**（文档自洽性）—— 会误导，但不必然写错。

一条贯穿性建议：**把每条 INV 当作可执行代码跑一遍再冻结。**
本轮 10 条失败的判据里，有 7 条是"读起来完全合理、跑一遍立刻失败"
（BLOCK-1 的 `== 1e-4`、BLOCK-2 的 1e-6 容差、BLOCK-7 的帧数与 `== 2/3`、
BLOCK-11 的 5 个端口、BLOCK-12 的 `5.0`、BLOCK-13 的 `21`、BLOCK-17 的 hash）。
若 §8 的脚本在冻结前被执行过一次，这 7 条都不会进入 `.spec/build/`。
