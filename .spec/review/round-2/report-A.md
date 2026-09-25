# 盲审报告 A

> 审查对象：`harmonica-eval` 空壳（18 个 `harmonica_eval/**/*.py` 骨架 + 18 份 `.spec/build/FILE-*-v1.md`）
> 信息集：**仅**骨架源码 + 对应 BI。未参考实现、未参考 round-1 结论。
> 方法：每条结论均先写探针脚本、再真实执行、再抄录真实 stdout。全部探针与输出在
> `.spec/review/round-2/probes-A/`（`probe_01..probe_52` 及 `*_output.txt`）。

---

## 0 · 审查锚点

### 0.1 重要前提：审查期间仓库被并发修改

本次审查进行中，**仓库被第三方并发改写**。可复现证据：

```
$ python3 /tmp/cmp.py        # 对比会话开始时的 hash 与当前 hash
  harmonica_eval/__init__.py                    SAME
  harmonica_eval/__main__.py                    *** CHANGED ***
  harmonica_eval/algorithms/dynamics.py         *** CHANGED ***
  harmonica_eval/algorithms/timing.py           *** CHANGED ***
  ...（其余 14 个骨架 SAME）
```

同时 `.spec/build/FILE-002/004/100/102/104/105/200/201/202/203/301/400-v1.md`
与 `SPEC.md` 亦被改写（`git status --porcelain` 显示 13 个 `M`）。

**处理方式**：为消除竞态，我在 `2026-09-24 11:35:17` 冻结了一份不可变快照，本报告
**所有行号与结论均以该快照为准**：

```
.spec/review/round-2/probes-A/_snapshot2/harmonica_eval/**.py     (18 个骨架)
.spec/review/round-2/probes-A/_snapshot2/specs/FILE-*-v1.md       (18 份 BI)
.spec/review/round-2/probes-A/_snapshot2/specs/SPEC.md
```

> 注意：快照中的 BI 已经包含若干「第三轮盲审 A 的 probe NN」字样 —— 即在我审查过程中，
> 维护者已按我的探针结果就地修改了部分文件。**这些修改本身又引入了新缺陷**（见 FINDING-5、FINDING-6）。

### 0.2 骨架 sha256（快照时刻）

```
3b6f3af502b03980ab4d4713f85396925062513b51a46e7ee79134594f5e3ca2  harmonica_eval/__init__.py
4f96d1f9408235e757573beca45a8c736884ef5af0807f4685779c3523eb821a  harmonica_eval/__main__.py
5f870fee17f9410465866c9c09fce2b6f5c06f9a7d001c31d8a8a241b9f193b6  harmonica_eval/algorithms/__init__.py
64e3e20df25676366403c3c09f1182742ebbff0362768a852181e8ef9fd7abe7  harmonica_eval/algorithms/dynamics.py
f914e5fe34612a470382f62f2b56ad1e0f593bb194b3c9f35becde3483e91c7e  harmonica_eval/algorithms/pitch.py
63b9152ee0b05cc542acf4b13293d74035956602c9b91e7fa5b25d8dbf2083ef  harmonica_eval/algorithms/timing.py
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

### 0.3 BI / 上位规格 sha256（快照时刻）

```
21e7b35683da24a23a376b27278f2526502c03eb270284d35c226d369be0c10f  FILE-001-v1.md
c672d97d4a9b9fb4982553e01dbf7c237aef3ab4efede735bae46076a67e7bee  FILE-002-v1.md
97d2024932421c1ba2624c1a141b95c276e1ae7f6a3ac3fd3e7d559e65098f0b  FILE-003-v1.md
03ac55ca06890603ce90761b2b53b466b8480368b0103c5f56480649913b524b  FILE-004-v1.md
3b8fd737de9cbea855438a5267f07dee0c39d834f3494d51c8cdd66435041d71  FILE-100-v1.md
f60faab69c32152d708d5848510899046ce612c6f0d5ed983df44b9970d9ccdd  FILE-101-v1.md
b8d66d0a4b203077efaffc7d9f76dd7920fc577d2e51fe70ab6c432dbba12b8d  FILE-102-v1.md
78b15fa3be5158578c803fd05ef2a5bdf92dc8dd76b47d3f5480a2fec07061f6  FILE-103-v1.md
d9cd652ede87bec3bc19f4afb38c9af4454c405b61ab47021a5019baeff17606  FILE-104-v1.md
e7b939f842422ad3ba049a07016cb8618a961d322cc5aa2a62bb26b194bd9952  FILE-105-v1.md
3d32649acfa8b2cc6d7cf6a01b70181560de7cd63c5fdff5effbbb55cd34b9aa  FILE-200-v1.md
11cd0d315784db718c4d5fa1684b692ea61d34f305852c377ac4754b29ab8a80  FILE-201-v1.md
e7457b09433f4f1f26796d83acd09685e65bb9cc937811fec0829f061cf049fa  FILE-202-v1.md
ec374969cffb6358159b2644968479fbddaaafa31bbb49aaa4adad4e75f2bc96  FILE-203-v1.md
b46c60387a052f17ce8ed9088c2fffa5140c0f36f57d96798da809a428a6b77e  FILE-300-v1.md
bd062eea3967f698f373046b4bc573964d5a6fb243d4432b04d38791e61a86c0  FILE-301-v1.md
3778c59c8a68eb70ee94b67de05a4ad4bdcff0e581401a7fa5179e4e624b61a2  FILE-400-v1.md
c7c84091439ee199539a33f7854f550f47e41bd5d0ffc37bd0e0aab98def78f4  FILE-401-v1.md
c42a1c9db72483554c82bf72c698781be4948c2b8ce5a80794d6fe5909106a56  SPEC.md
c7689593274cd33596ff80fe5bf7fdd0179212dddf0ddbeef48d91f134531a24  COMPONENTS.md
642b6d7870d5229cf7bc653c7fd55650d7f3b94d487e138367cf8b574a4988eb  CONTRACTS.md
```

**事实基准（唯一权威）**：`contract.py` 与 `profile.py` 的字面内容。凡 BI 与之冲突，一律以这两个文件为准。

---

## 1 · 结论

```
VERDICT: REJECT
```

理由：存在 **8 个 blocker**。其中至少 3 个是「实现者无论怎么写都必然错」的死结
（FINDING-1 判据 B 恒假、FINDING-4 stage-3 无入口、FINDING-5 `note_spans` 除零），
其余为「照抄规格即 `TypeError`」（FINDING-3 `error=`、FINDING-6 §8 自检脚本）。

**特别说明（负责人已裁定的两处）**：
- `pcm.*` 三个端口的生产者归属 —— **自洽且已落地**（见 §3.1 的正面验证）。
- `metrics.json` 结构 —— **本次审查中已被并发修复而落地**（见 §3.2 与 FINDING-2）。
  但同一批并发修复**新引入**了 FINDING-5、FINDING-6 两个缺陷。

---

## 2 · 发现清单

### FINDING-1

```
严重度: blocker
位置:   .spec/build/FILE-100-v1.md:111, :185, :338, :369, :383
        （实测对象 harmonica_eval/core/__init__.py，骨架 sha 662b736d…）
问题:   FILE-100 把「core 包公开面 == profile.PORTS 的 produced_by 所指模块」写成
        可机械判定的验收判据 B，但该等式在真实配置下**恒为假**，实现者无论怎么写都
        无法让判据 B 通过。
证据:   按 BI:335-340 逐字执行判据 B（探针 probe_26 / probe_34 / probe_40）：
          $ python3 -c "... declared = set(core.__all__); produced = {...} ..."
          declared = ['align', 'api', 'features', 'ingest', 'surface']
          produced = ['align', 'features', 'surface']
          equal    = False
        差异根因（profile.py 为唯一权威，12 个端口的 produced_by 实测取值）：
          $ python3 -c "print(sorted({p.produced_by for p in profile.PORTS}))"
          ['core.align', 'core.features', 'core.surface']
        `ingest` 与 `api` 在 12 个端口里**没有任何一个**端口由它们产出 ——
        ingest 是阶段 1（产 PCM 但不登记为端口），api 是门面（不产端口）。
        故 `declared` 必为 5 元素、`produced` 必为 3 元素，`declared == produced`
        永假。BI:369 更把「判据 B 退出码为 0」列为验收清单项。
修法:   二者取一，且必须同步改 BI 的 §8 脚本、INV-100-4（:185）、验收清单（:369/:383）：
        (a) 把判据 B 改为 `produced <= declared`（子集判定）——
            `ingest`/`api` 是「有公开面但不产端口」的模块，集合相等本就不该成立；或
        (b) 保留相等语义，但把 `produced` 的来源改为「模块名清单」而非
            `produced_by`（例如新增一份 `PUBLIC_SUBMODULES` 与 `produced_by` 的双向映射），
            并同步修改 `profile.py`。
        推荐 (a)：它不改冻结配置，且与 FILE-100 的 `__all__` 5 元素冻结值自洽。
```

---

### FINDING-2

```
严重度: blocker（本次审查期间已被并发修复；此处记录沿革与残留）
位置:   .spec/build/FILE-002-v1.md:199, :288, :325, :351, :375
        （实测对象 harmonica_eval/__main__.py）
问题:   `metrics.json` 的 `inputs` 与 `report.md` 的「参考/练习」两行都需要 URI，
        而 `UiView` 不携带 URI，原冻结签名 `(view, out_path)` / `(view)` 下无通道可取。
        经并发修复后**已落地**，但需独立确认「裁定是否真的生效」。
证据:   【修复前】探针 probe_03：`write_metrics_json(view, out_path)` 与
        `render_report_markdown(view)`；`dataclasses.fields(UiView)` 实测为
          ['session_id','state','series','scalars','progress','error_code','error_detail','note']
        —— 无任何 URI / ref / practice / path 字段；而 BI:266 要求
        `inputs = {"reference": <reference_uri 原样>, "practice": <practice_uri 原样>}`。
        【修复后】探针 probe_40 / probe_47（快照2）：
          skeleton write_metrics_json: (view, out_path, reference_uri: str, practice_uri: str) -> None
          skeleton render_report_markdown: (view, reference_uri: str, practice_uri: str) -> str
          BI:199  ### 4.3 `write_metrics_json(view: UiView, out_path: Path, reference_uri: str, practice_uri: str) -> None`
          BI:325  ### 4.4 `render_report_markdown(view: UiView, reference_uri: str, practice_uri: str) -> str`
          -> AGREE: True
        BI:288 与 BI:351 亦已同步为「取自本函数的入参」。
        结论：**`metrics.json` 结构裁定已真实落地**（骨架与 BI 逐字一致，且不新增
        任何数据通道、不改 contract.py）。
修法:   无（已修复）。但须注意：同一批并发修复引入了 FINDING-5 与 FINDING-6。
```

---

### FINDING-3

```
严重度: blocker
位置:   .spec/build/FILE-203-v1.md:193-194（失败语义表）、:191
        （实测对象 harmonica_eval/contract.py 的 AlgorithmResultEnvelope）
问题:   FILE-203 的失败语义表要求用 `error=<str>` 关键字构造信封，但
        `AlgorithmResultEnvelope` **没有** `error` 字段，照抄即 `TypeError`。
证据:   探针 probe_34 / probe_40：
          $ python3 -c "AlgorithmResultEnvelope(..., error='X')"
          'error=' REJECTED -> AlgorithmResultEnvelope.__init__() got an unexpected keyword argument 'error'
          envelope fields: ['algorithm_id','algorithm_version','status','required_ports',
                            'consumed_ports','payload','error_code','error_detail','elapsed_sec']
        契约（唯一权威）只认 `error_code` / `error_detail`。
        注：BI:191 已就地更正了**表头**的 `error=<str>`，但**表体与 §4.4 流程**
        （:194 的失败分支）仍留有旧写法，属「改一半」。
修法:   把 FILE-203 中所有 `error=<str>` / `error=` 一律改为
        `error_code=<ErrorCode 成员>, error_detail=<str>`，
        与 FILE-201:304-305、FILE-202 的失败分支写法对齐。
```

---

### FINDING-4

```
严重度: blocker
位置:   .spec/build/FILE-105-v1.md:195（阶段 3）
        （实测对象 harmonica_eval/core/features.py、core/surface.py）
问题:   FILE-105 的四阶段链不可实现：阶段 3 声称「调用 core.features 的入口，
        实参 = 阶段 2 的产出（warp_path），产出 = profile 决定的全部端口缓冲」，
        但 core.features **没有任何聚合入口**，且阶段 3 的产出**没有消费者**
        （阶段 4 自己会重新生成全部 12 个端口）。
证据:   探针 probe_41：
          $ python3 -c "import harmonica_eval.core.features as F; print([n for n in dir(F) if not n.startswith('_')])"
          ['MIN_STABLE_NOTE_SEC','VOICED_CONFIDENCE_FLOOR','annotations',
           'materialize_chroma','materialize_notes','materialize_pitch','materialize_rms','npt']
          聚合入口（produce-all-ports）：NONE
        四个 features 函数实测签名均以 `samples` / `pitch` 打头，**没有一个**接受
        `warp_path`：`materialize_pitch(samples, sample_rate)`、
        `materialize_rms(samples)`、`materialize_chroma(samples)`、
        `materialize_notes(pitch, rms, sample_rate)`。
        而阶段 4 的入口实测为
          build_surface(reference, practice, sample_rate, warp_path) -> Surface
        且 FILE-104 §4.7 第 5 步规定 `build_surface` **内部**调用
          generate_all_ports(reference, practice, sample_rate, warp_path) -> Mapping[str, NDArray]
        —— 即阶段 4 会**重新生成全部 12 个端口**（含阶段 3 声称要产的那 8 个特征端口）。
        ⇒ 阶段 3 的输入对不上任何入口、输出无消费者；两个阶段做同一件事，
          且阶段 3 的产物被丢弃（违反 FILE-105:203「不得部分发布」之外的语义重复）。
修法:   二者取一：
        (a) 删除阶段 3，把四阶段改为三阶段（INGEST → ALIGN → SURFACE），
            并在 §4.9 的 `INTERNAL_STAGES` 常量同步删除 `"MATERIALIZING"`
            （该常量当前值实测为 `("INGESTING","ALIGNING","MATERIALIZING","SEALING")`）；或
        (b) 明确阶段 3 是**语义分组**而非一次调用（即「阶段 3 的逻辑发生在
            `generate_all_ports` 内部」），并显式写出阶段 3 **不产生**独立返回值、
            阶段 4 的实参是 `(阶段1 的两路 PCM, sample_rate, 阶段2 的 warp_path)`。
        无论哪种，都必须补上 `sample_rate` 的来源（见 FINDING-7）。
```

---

### FINDING-5

```
严重度: blocker（**并发修复新引入**）
位置:   .spec/build/FILE-203-v1.md:77, :94, :96, :97, :165, :168
        （实测对象 harmonica_eval/algorithms/dynamics.py、harmonica_eval/profile.py）
问题:   FILE-203 新版 `note_spans(notes, rms_hop_length, sample_rate)` 要求
        `rms_hop_length` 由调用方传入，但**全文从未说明它从哪来**；
        而实现者手上唯一的描述符是 `notes.*` 的，其 `hop_length` 恒为 **0**
        —— 照抄冻结公式即 `ZeroDivisionError`。
证据:   探针 probe_36 / probe_38：
          $ python3 -c "print([ (p.port_id, p.hop_length) for p in profile.PORTS ])"
            notes.reference          hop_length=0
            notes.practice           hop_length=0
            rms.reference            hop_length=256
            rms.practice             hop_length=256
          $ python3 -c "int(round(1.5 * 44100 / 0))"
            ZeroDivisionError: float division by zero
          $ python3 -c "int(round(1.5 * 44100 / 256))"
            258
        FILE-203:160-161 只告诉实现者持有 **notes** 的描述符
        （「列号必须用 `descriptor.field_names.index("onset_sec")` 查」），
        其 `hop_length` 为 0；`rms_hop_length` 在 :165/:168 被当作**已绑定的
        局部变量**直接使用，但全文 5 处命中（:77/:93/:94/:165/:168）**没有一处**
        给出取值路径。且 FILE-203 §3（:42-54）的 import 白名单**不含**
        `harmonica_eval.profile`，故不能取 `MATERIALIZE.rms_hop_length`。
        合法来源其实存在（`PortDescriptor.hop_length`，实测字段表含 `hop_length`），
        但 BI 未写，实现者只能猜 —— 猜 `notes` 的 0 即崩溃。
        ★ 同一处还残留**旧帧率数字**：:96 写「`frame(onset_sec_last) + 100`（默认 1 秒）」，
          :97 重复「`[frame(onset), frame(onset)+100]`」。按新公式
          `1 秒 = round(44100/256) = 172` 帧，**不是 100** ——
          即 BI 一边声明「禁止写死任何帧率数字（原 `100` 已删除）」(:95)，
          一边在两行后继续使用 `100`。
修法:   (a) 在 :165/:168 显式写出 `rms_hop_length` 的取法：
            `rms_hop_length = surface.manifest().ports["rms.reference"].hop_length`
            （或让 `note_spans` 改收 `descriptor` 并断言其前缀为 `rms`）；
        (b) 把 :96/:97 的 `+ 100` 改为
            `+ int(round(sample_rate / rms_hop_length))`（或直接写 `+ 172` 并注明
            它是本 profile 下 1 秒的帧数），并删除 :95 的「原 100 已删除」表述
            或使其与 :96/:97 一致。
```

---

### FINDING-6

```
严重度: high（**并发修复新引入**）
位置:   .spec/build/FILE-203-v1.md:129, :253
        （实测对象 harmonica_eval/algorithms/dynamics.py）
问题:   FILE-203 把 `summarize_deltas` 的签名改为 `(deltas_db, n_unpaired)`
        二参，却**没有同步修改同文件 §8 的自检代码** —— 那段代码仍按一参调用，
        实现者照它跑必然 `TypeError`。
证据:   探针 probe_35：
          FILE-203:129  ### `summarize_deltas(deltas_db, n_unpaired) -> dict`
          FILE-203:253  s = summarize_deltas([3.0, -1.0, 2.0])
          $ python3 -c "from harmonica_eval.algorithms.dynamics import summarize_deltas; summarize_deltas([3.0,-1.0,2.0])"
            TypeError -> summarize_deltas() missing 1 required positional argument: 'n_unpaired'
          actual signature: (deltas_db: 'object', n_unpaired: 'int') -> 'object'
        §8 是 BI 明确标注的「验收判据（可机械判定）」，其自检脚本必须可跑通。
修法:   把 :253 改为 `s = summarize_deltas([3.0, -1.0, 2.0], 0)`，
        并补一条 `assert s['n_unpaired'] == 0`；
        同时检查 FILE-202 §8 是否有同型残留（`summarize_deviations` 亦已改为二参）。
```

---

### FINDING-7

```
严重度: high
位置:   .spec/build/FILE-105-v1.md:149-151, :177, :195-196
        （实测对象 harmonica_eval/core/ingest.py、core/surface.py）
问题:   `sample_rate` 在 C2 门面里**无合法来源**，而阶段 3/4 都强制需要它。
证据:   探针 probe_50：
          $ python3 -c "import inspect, harmonica_eval.core.ingest as I; print(inspect.signature(I.ingest))"
          (uri: 'str') -> 'npt.NDArray'
        —— `ingest` 只返回 PCM，**不返回** `AudioFormat`。
        但 FILE-105:150-151 写「产出 = 两路规范化后的 mono/`float32` PCM **与其
        `AudioFormat`**」（与实测不符）；
        而阶段 4 的入口 `build_surface(reference, practice, sample_rate, warp_path)`
        需要 `int sample_rate`（实测签名），`materialize_pitch(samples, sample_rate)`、
        `materialize_notes(pitch, rms, sample_rate)` 亦然。
        FILE-105:177 只声明「采样率不由本文件假设：`ingest` 返回的 PCM 已按
        `profile.AUDIO.sample_rate` 规范化」，但**没有任何一步把它绑定成变量**；
        FILE-105:59 又把 `harmonica_eval.profile` 列入**具名禁入**
        （`profile` 解析责任在阶段模块）。⇒ 门面拿不到 `sample_rate`。
        ★ 交叉核对：阶段模块**确实**被允许 import profile
        （FILE-101:62 `from ..profile import AUDIO`、FILE-102:43、FILE-103:40），
          故「责任在阶段模块」这句是真的；但**门面自己**要用它调 `build_surface`，
          这一环缺规格。
修法:   (a) 在阶段 1 之后显式写出 `sample_rate` 的取法（例如
            `sample_rate = int(surface_manifest.audio_format.sample_rate)` 不行 ——
            此时还没有 surface；可行写法是
            `from ..profile import AUDIO` 并**把它加入 §3 白名单**，或
            `from ..core.ingest import ingest, SAMPLE_RATE` 若该常量存在），
            并同步修正 :59 的禁入清单与 :342 的「不读取 `AUDIO.max_duration_sec` …」表述；或
        (b) 把阶段 3/4 的实参改为「由阶段模块自行从 profile 取采样率」，
            并删去门面对 `sample_rate` 的传递要求。
        无论哪种，都要把 :150-151 的「与其 `AudioFormat`」改为与
        `ingest(uri) -> npt.NDArray` 一致的表述。
```

---

### FINDING-8

```
严重度: high
位置:   .spec/build/FILE-104-v1.md:121-122 vs :140-142
问题:   FILE-104 同一文件内自相矛盾：§3 禁止模块顶层出现任何非声明语句
        （「不得有函数调用」），§4.0 却**强制要求**在模块导入时执行断言。
证据:   探针 probe_31 / probe_39：
          FILE-104:121  - 禁止在模块顶层执行任何非声明语句（除 `__all__` 赋值外，不得有函数调用、
          FILE-104:122    常量计算、文件读取）。
          FILE-104:140  实现**必须**在模块导入时用一次断言核验（`assert FIELD_LAYOUTS["notes"][0] == "onset_sec"`
          FILE-104:141  与 `assert FIELD_LAYOUTS["warp_path"][0] == "reference_frame"`），
          FILE-104:142  核验失败即 `ImportError` 级别缺陷，**不得**静默继续。
        `assert` 是语句、且其条件是函数/下标调用 —— 正是 :121 所禁。
        （此矛盾与 FINDING-9 同源：两者都是「§3 清单写死后被后文需求打破」。）
修法:   二者取一：
        (a) 把 :121 的禁令收窄为「禁止**除契约核验断言之外**的非声明语句」，
            并明确允许这两条 `assert`；或
        (b) 删去 :140-142 的强制断言，改为「由 §8 判据静态核验」。
        推荐 (a)：导入期核验是 FILE-104 自己论证过的价值（「不得静默继续」）。
```

---

### FINDING-9

```
严重度: medium
位置:   .spec/build/FILE-104-v1.md:87-88 vs :796-797
问题:   §3 声明依赖清单「必须**穷举**，不许出现「等」「之类」」，但清单里
        **没有 `types`**，§4.7 第 12 步却**强制**要求 `import types`。
证据:   探针 probe_31 / probe_39 / probe_51：
          FILE-104:87   - `harmonica_eval.profile` 的 **6 个名字**：
          FILE-104:88   `PORTS`、`PORT_INDEX`、`BUDGET`、`AUDIO`、`ALIGN`、`MATERIALIZE`、`PROFILE_VERSION`。
          FILE-104:796  `import types`；这是标准库，属于 §3 允许清单的补充，
          FILE-104:797  实现**必须**在模块顶部写 `import types`（不得在函数体内做局部 import）。
        同一 §3 的穷举性声明（探针输出原文）：
          「★ 本清单必须**穷举**，不许出现「等」「之类」。」
        ⇒ 「属于 §3 允许清单的补充」这句话**否定了 §3 的穷举性**，两份表述互斥。
修法:   把 `types`（仅 `MappingProxyType`）写入 §3 的标准库白名单，
        并删除 :796 的「属于 §3 允许清单的补充」这一自我豁免表述。
```

---

### FINDING-10

```
严重度: medium
位置:   .spec/build/FILE-104-v1.md:87-88
问题:   §3 写「`harmonica_eval.profile` 的 **6 个名字**」，实际列出 **7 个**。
证据:   探针 probe_31（正则抽取 + 计数）：
          claimed = 6; listed = 7 -> ['PORTS','PORT_INDEX','BUDGET','AUDIO',
                                      'ALIGN','MATERIALIZE','PROFILE_VERSION']
          MATCH: False
        同段的 contract 名单计数是**对的**（claimed = 8; listed = 8），
        说明这是 profile 一处的独立笔误，不是系统性偏差。
修法:   把 :87 的 `6` 改为 `7`。
```

---

### FINDING-11

```
严重度: medium
位置:   .spec/build/FILE-104-v1.md:92 vs :330-338
问题:   §3 仍把生产者签名约定写成**四个参数**的旧版口径，而 §4.4 已明确
        把同一句话标为「上一版原文（已作废）」「不可满足」。
证据:   探针 probe_39：
          FILE-104:91   或由 `harmonica_eval/core/` 内的直接模块 import 取得；取到的可调用对象签名约定为
          FILE-104:92   `(reference, practice, sample_rate, warp_path) -> NDArray`。
        §4.4 实测签名（骨架冻结，唯一权威）：
          materialize_pitch(samples, sample_rate)      2 参
          materialize_rms(samples)                     1 参
          materialize_chroma(samples)                  1 参
          materialize_notes(pitch, rms, sample_rate)   3 参
          align(reference, practice)                   2 参
        即 §3 那句 `(reference, practice, sample_rate, warp_path)` **不匹配任何一个**
        真实生产者；而 §4.4 的派发表（:406-412）已给出正确实参。
        §4.4 只作废了**自己那段**的旧文，没有回头修 §3。
修法:   删除 :92 的签名约定句，改为
        「各生产者的实参见 §4.4 冻结派发表；本文件不假设统一签名」。
```

---

### FINDING-12

```
严重度: medium
位置:   .spec/build/FILE-104-v1.md:160 vs :180（标题重号）
问题:   同一文件内两个不同小节共用编号 `4.1`，且两次标题**逐字相同**。
证据:   探针 probe_31 / probe_39（grep 原文）：
          FILE-104:160  ### 4.1 `port_prefix(port_id: str) -> str`
          FILE-104:180  ### 4.8 `port_prefix(port_id: str) -> str`
        另实测：`port_prefix` 在骨架 `core/surface.py` 中**不存在**
        （探针 probe_04：`core.surface.port_prefix` → MISSING），
        它是 BI 自定的**文件内私有助手** —— 这本身允许，但
        同一符号被赋两个节号，会让「见 §4.1」/「见 §4.8」的交叉引用无法判定指向。
修法:   把 :160 的小节改为正确编号（按前后文应为 §4.1 的位置留给首个公开函数，
        实际该处内容是 §4.0 的冻结数字清单被误置），并把 :180 保持为 §4.8；
        或把两处合并为一节。
```

---

### FINDING-13

```
严重度: medium
位置:   .spec/build/FILE-201-v1.md:240-241 vs :252-254
问题:   §4.3 先冻结「**恰好 5 个键，一字不得增删**」，随后又说本函数只返回
        **前 4 个键**、并额外允许「直接收 `sample_rate` 返回 5 键」的第二种实现。
        后半句在**冻结签名**下不可满足。
证据:   探针 probe_40：
          FILE-201:241  **恰好 5 个键，一字不得增删**：
          FILE-201:252  故本函数返回**前 4 个键**，由 `run()` 补上 `sample_rate` 得到完整 5 键。
          FILE-201:253  若实现者选择让本函数直接收 `sample_rate` 并返回 5 键，**也允许**
          FILE-201:254  （两种都不违反契约），但**必须在文档里写清选了哪种**。
        骨架冻结签名（唯一权威，探针 probe_34）：
          summarize_deviations(deviations_cents: 'object') -> 'object'
        —— **没有** `sample_rate` 形参，故 :253 的分支不可能实现；
        实现者若照 :253 尝试，只能改签名（= 接口变更）或从别处取采样率（无来源）。
        真正自洽的是 :314-315（`run()` 第 5 步补键）。
修法:   删除 :253-254 的「也允许」分支，把 :252 定为唯一口径；
        并把 :241 的「恰好 5 个键」限定为「**payload** 恰好 5 键」，
        与 :252 的「本函数返回前 4 键」在措辞上区分开（当前两句读起来互斥）。
```

---

### FINDING-14

```
严重度: medium
位置:   .spec/build/FILE-201-v1.md:163-164 vs algorithms/__init__.py 的 PAYLOAD_SCHEMAS['pitch']
问题:   `compare_pitch_curves` 的返回 dict 含 `n_paired` / `n_unpaired` 两个键，
        而 `PAYLOAD_SCHEMAS['pitch']` 里**没有**这两个键 —— 该值算出来后无处安放。
证据:   探针 probe_40 / probe_52：
          PAYLOAD_SCHEMAS['pitch'] = ('per_note_cents','median_abs_cents',
                                      'off_pitch_ratio','n_notes_used','sample_rate')
          FILE-201:163  "n_paired": int,                 # 成功配对的音数
          FILE-201:164  "n_unpaired": int,               # 未能配对的音数（★ 见下"已知缺口"）
        FILE-200:509 明确禁止为 `pitch` 补 `n_unpaired`：
          「你**想动** `PAYLOAD_SCHEMAS` —— 包括为 `pitch` 补 `n_unpaired`（`GAP-200-1`）
            …冻结表的变更属接口变更。」
        FILE-201:220-233 已**如实披露**该缺口，并要求「按 §37 Gate Challenge 上报」。
        ⇒ 这是**已披露**的缺陷，不是隐瞒。但它仍然使实现者面对一个
          「必须返回、但契约拒收」的中间量，属真实的规格-契约冲突。
修法:   保留披露，但补一句可执行的收尾口径，例如
        「`run()` 装信封时**丢弃** `n_paired` / `n_unpaired`（不写入 payload），
          并在 `error_detail` 之外不做任何上报；缺口登记于 `GAP-200-1`」。
        （当前 :231-232 已接近此意，但只提了 `n_unpaired`，未提 `n_paired`。）
```

---

### FINDING-15

```
严重度: medium
位置:   .spec/build/FILE-202-v1.md:175
问题:   §4.5 流程伪码写 `descriptor.timeline_basis is AXIS(REFERENCE)`，
        其中 `AXIS(...)` 这个写法在**整个仓库里不存在**。
证据:   探针 probe_46：
          $ python3 -c "扫描快照全部 .py 中 'AXIS(' 的出现"
          python files containing 'AXIS(':  NONE
        `timing.py` 实测确实有 `AXIS`，但它是一个**模块级常量**而非可调用对象：
          timing.py:51  AXIS: TimelineBasis = TimelineBasis.REFERENCE
        故 `AXIS(REFERENCE)` 会 `TypeError: 'TimelineBasis' object is not callable`；
        正确写法是 `descriptor.timeline_basis is AXIS`（常量直接比较）。
修法:   把 :175 改为 `descriptor.timeline_basis is AXIS`，
        并同步检查 §5 失败语义表与 §8 自检脚本中的同型写法。
```

---

### FINDING-16

```
严重度: medium
位置:   .spec/build/FILE-201-v1.md:312（对照 :151 的类型声明）
问题:   §4.4 流程把 `surface.read(...)` 的返回值直接赋给 `ref_pitch`，
        但 §4.2 声明 `ref_pitch` 是 `NDArray`，而 `read()` 实测返回 `BufferView`；
        FILE-201 全文**没有一处**提到需要取 `.data` 解包。
证据:   探针 probe_43 / probe_45：
          contract.py:411  def read(self, port_id: str, time_range=None) -> BufferView
          FILE-201:312  3. `ref_pitch = surface.read("pitch.reference")`，其余三个同理
          FILE-201:151  | `ref_pitch` | `NDArray` | `(n_frames_ref, 3)` | ...
          FILE-201 全文 ".data" 命中数 = 0
          FILE-201 全文 "BufferView" 命中数 = 0
        对照：FILE-203 **有**写这一步（探针 probe_45）：
          FILE-203:161  `read()` 返回 `BufferView`，取 `.data` 得 ndarray；
          FILE-203:91   …（`notes.*` 端口的 `read().data`）
        同一套 C3 规格里，FILE-203 写了、FILE-201/FILE-202 没写。
        实现者若照 FILE-201 字面写，会把 `BufferView` 当 ndarray 用
        （后续 `res["per_note_cents"]` 等操作行为不可预期）。
修法:   在 FILE-201:312 改为
        `ref_pitch = surface.read("pitch.reference").data`，其余三个同理；
        并在 FILE-202 的 §4.5 流程（notes/pcm 端口读取）补同一句。
```

---

### FINDING-17

```
严重度: low
位置:   .spec/build/FILE-100-v1.md:132, :279, :436
        （实测对象 harmonica_eval/core/__init__.py，骨架 sha 662b736d…）
问题:   FILE-100 把 `len(core.__doc__.splitlines()) == 31` 同时写成不变量、
        §8 判据脚本的断言、以及冻结表的一行；但实测为 **30**，
        且该断言在**未改动的骨架上**即失败 —— 实现者无法通过。
证据:   逐字执行 FILE-100 §8 判据 A（探针 probe_28），20 项中 19 项 PASS：
          PASS  INV-100-9a len(src.splitlines())==53
          FAIL  INV-100-8 len(doc.splitlines())==31  -> AssertionError: 30
          FAILURES: ['INV-100-8 len(doc.splitlines())==31']
        根因（探针 probe_28 同时验证）：`src.splitlines()` 确为 **53**（BI 要求 53，PASS），
        而 docstring **值**的行数是 30。BI:436 的冻结表写「docstring 行数 `31` | 行 1–31」——
        它把「源码第 1–31 行」与「docstring 值的 30 行」混为一谈
        （`end_lineno=31` 含 `"""` 定界行，`splitlines()` 不含）。
修法:   把 :132 / :279 / :436 三处的 `31` 一律改为 `30`，
        并把 :436 的「行 1–31」说明改为「源码行 1–31（含定界符）；值 30 行」。
```

---

### FINDING-18

```
严重度: low
位置:   .spec/build/FILE-002-v1.md:370, :643
问题:   §4.3 第 6 步已就地更正 `n_points` 不是 `UiSeries` 字段，但同一文件
        §4.4 的单行格式说明与 §10 的「不足以确定唯一实现」清单仍按**旧前提**表述。
证据:   探针 probe_40（grep 原文）：
          FILE-002:370  - `<n>` = 该 `UiSeries` 的点数元信息（整型，`str(n)`）。
          FILE-002:643  4. §4 的行为规格**不足以确定唯一实现**（例如：`UiSeries` 不暴露点数元信息，而 §5 已禁止用 `len(values)` 替代）。
        而 §4.3 第 6 步（:303-313）已冻结 `n_points = len(s.t)`，
        并实测 `hasattr(UiSeries,"n_points")` 为 False、全仓命中数 0。
        ⇒ :370 仍叫实现者去读一个不存在的「元信息」；:643 仍把已解决项列为未决。
修法:   把 :370 改为「`<n>` = `len(s.t)`（本文件算出的派生子，见 §4.3 第 6 步）」；
        把 :643 的第 4 项删除或改为「已解决（见 §4.3 第 6 步）」。
```

---

### FINDING-19

```
严重度: low
位置:   .spec/build/FILE-002-v1.md:411
问题:   §4.9 同一句话里先写「**四个** `raise NotImplementedError` 占位」，
        紧跟的括号里却列出 **5 个**函数名并写「共 5 处」。
证据:   探针 probe_40：
          FILE-002:411  四个 `raise NotImplementedError("SHELL: FILE-002 待注入实现")` 占位
                        （`build_parser` / `run_headless` / `render_report_markdown` /
                         `write_metrics_json` / `main`，共 5 处）必须被真实实现替换。
        实测骨架 `__main__.py` 的 `NotImplementedError` 计数 = **7**
        （探针 probe_22 的计数清单），与「4」和「5」都不符 ——
        说明该句的三处数字没有一个经过核对。
修法:   把「四个」改为「五个」（或按实测 7 处改写），并让括号内的函数名清单
        与实测计数一致。
```

---

### FINDING-20

```
严重度: low
位置:   .spec/build/FILE-105-v1.md:51
问题:   §3 写「本包内（穷举，恰 **6** 条 import 的来源）」，实际只列出 **5** 个模块。
证据:   探针 probe_48（正则抽取该段全部 `harmonica_eval.<path>`）：
          module paths named: ['contract','core.surface','core.ingest','core.align','core.features']
          -> distinct import sources implied: 5
          claimed: 6   actual: 5   MISMATCH
        同一段的「标准库（穷举，恰 4 个模块）」（:45）经核对为**正确**
        （`__future__` / `typing` / `uuid` / `dataclasses` 恰 4 个），
        说明这是本包一处的独立计数错误。
修法:   把 :51 的 `6` 改为 `5`；若原本打算把 `harmonica_eval.profile` 列入
        （用于 FINDING-7 的 `sample_rate`），则改为 `6` 并**实际把 profile 加进白名单**，
        同时删除 :59 与 :342 的相应禁入表述。
```

---

## 3 · 已独立验证的裁定（正面结论）

### 3.1 `pcm.*` 三个端口的生产者归属 —— **自洽且已落地**

```
验证: 探针 probe_11 / probe_30 / probe_41
  $ python3 -c "print([(p.port_id, p.produced_by) for p in profile.PORTS if p.port_id.startswith('pcm')])"
    pcm.mapped.reference   produced_by='core.surface'
    pcm.mapped.practice    produced_by='core.surface'
    pcm.warped.practice    produced_by='core.surface'
  FILE-105:189-191（裁定后同步文本）：
    pcm.mapped.reference / pcm.mapped.practice —— 阶段 4（core.surface）纯转发阶段 1 的规范化 PCM（零计算）
    pcm.warped.practice —— 阶段 4 按 warp_path 做索引重排
  FILE-104 §4.4 派发表（:388-412）与之一致。
结论: **三个 pcm.* 端口全部归属 core.surface，profile 冻结值未被改动，
      无第二生产者，裁定真实落地。**
      （另：FILE-104 §4.4 声称的「实测 7 个结构键」经 probe_02 逐行核对 ——
        ALL 7 CLAIMED ROWS MATCH ACTUAL: True，无多余键、无遗漏键。）
```

### 3.2 `metrics.json` 结构 —— **已落地**（但见沿革）

```
验证: 探针 probe_03（修复前，不落地）→ probe_40 / probe_47（修复后，落地）
  修复后骨架与 BI 逐字一致：
    write_metrics_json(view, out_path, reference_uri: str, practice_uri: str) -> None
    render_report_markdown(view, reference_uri: str, practice_uri: str) -> str
  且未新增任何数据通道、未改 contract.py 一行。
结论: **裁定真实落地。** 但同一批并发修复引入了 FINDING-5（note_spans 除零）
      与 FINDING-6（§8 自检代码未同步）。
```

---

## 4 · 未能验证的项

| # | 项 | 状态 | 原因 |
| --- | --- | --- | --- |
| 1 | `FILE-001` 全部不变量 | **PARTIAL** | 已核 `PUBLIC_SUBMODULES`（实测 6 元素含 `cockpit`，与 BI:186/:241 一致）、`__version__`、`__all__`；其余行号级冻结表未逐项跑 |
| 2 | `FILE-003`（`contract.py`）| **SKIPPED** | `contract.py` 是权威本身（非待实现骨架，0 处 `NotImplementedError`），BI 仅描述既有内容；未逐行核对 BI 与源码的字段级一致性 |
| 3 | `FILE-004`（`profile.py`）| **PARTIAL** | 已核 12 端口全表（probe_30：字段级逐行比对，全部 MATCH）、7 个结构键（probe_02）、`produced_by` 三值、`max_surface_bytes`；`assert_profile_integrity()` 的「检查六件事」docstring 与 1–5/7/8 编号错位已发现但**未**升级为独立 FINDING（属 docstring 措辞，未证明会致实现者写错） |
| 4 | `FILE-101`（`ingest.py`）| **PARTIAL** | 已核 `ingest(uri)` 单参签名（probe_50）、`SILENCE_RMS_THRESHOLD` 存在性；`decode_to_mono` / `resample_to_profile` / `validate_duration` / `assert_not_silent` 的数值口径未逐条验证 |
| 5 | `FILE-102`（`align.py`）| **PARTIAL** | 已核 `align(reference, practice)` 2 参、返回 `NDArray`（probe_41）；DTW 数值口径（`ALIGN.hop_length` / `n_chroma` / `band_rad` / `global_constraints`）未验证 |
| 6 | `FILE-103`（`features.py`）| **PARTIAL** | 已核 4 个公开符号 + 2 个常量、无聚合入口（probe_41）；各 `materialize_*` 的数值口径未验证 |
| 7 | `FILE-200`（`algorithms/__init__.py`）| **PARTIAL** | 已核 `PAYLOAD_SCHEMAS` 三键及逐字键序、`ALGORITHMS` 的 `required_ports`、`assert_registry_integrity()` 的静态检查集；C7 运行期语义未验证 |
| 8 | `FILE-300`（`host/__init__.py`）| **PARTIAL** | 已核 `__doc__` 行数（实测 28）、文件行数（实测 39）、`__all__`；BI 的 E2/E4 约束细节未逐条跑 |
| 9 | `FILE-400`（`cockpit/__init__.py`）| **DONE** | 已核 `__all__ = ['launch_cockpit']`；BI:93-105 正确撤回不存在的 `LOCAL_BIND_PORT` / `POLL_INTERVAL_MS` |
| 10 | `FILE-401`（`cockpit/app.py`）| **PARTIAL** | 已核公开符号集合、`assert len(series.t) == len(series.values)` 三处校验（probe_14）；`UNKNOWN` 轴分支与 FILE-002 的张力（`TimelineBasis` 只有 2 值，FILE-401:131/:250/:274/:491/:657 却要求渲染 `UNKNOWN（'<原值>'，无法判定轴含义）`）已发现，**未**升级为 FINDING（FILE-002 §5 与 FILE-401 分属不同组件的失败策略，尚不足以断定必错） |
| 11 | 全部 BI 的 §8 自检脚本 | **PARTIAL** | 仅逐字执行了 FILE-100 的判据 A（probe_28）与判据 B（probe_26）、FILE-203 的 `summarize_deltas` 片段（probe_35）。其余 15 份 BI 的自检脚本**未**逐字执行 —— 基于 FINDING-6 的教训，这些脚本很可能还有同型残留 |

### 未验证项的风险提示

FINDING-6 表明「签名改了、§8 自检脚本没跟着改」是一种**系统性**失误模式。
建议在修复本轮 blocker 后，把**全部 18 份 BI 的 §8 脚本逐字执行一遍**作为独立验收项 ——
本次审查只覆盖了其中 3 份，就命中 1 处。

---

## 5 · 统计

| 严重度 | 数量 | 编号 |
| --- | --- | --- |
| blocker | 4 | 1, 3, 4, 5 |
| high | 3 | 6, 7, 8 |
| medium | 8 | 9, 10, 11, 12, 13, 14, 15, 16 |
| low | 4 | 17, 18, 19, 20 |
| （已修复） | 1 | 2 —— 审查期间被并发修复，保留编号以保持与探针输出的可追溯性 |

**合计 20 条**（其中 19 条待处理，1 条已修复）。

**探针清单**（全部位于 `.spec/review/round-2/probes-A/`）：
`probe_01`…`probe_52`，各附 `_output.txt`；快照 `_snapshot/`、`_snapshot2/`；
基线 `_baseline_now.txt`。共 48 份输出文件。

---

## 6 · 三句话总结

**最致命的问题是 FILE-100 的验收判据 B 恒为假**（`declared` 5 元素 vs `produced` 3 元素，
`ingest`/`api` 在 12 个端口里没有任何 `produced_by` 指向它们），实现者无论怎么写都无法通过自己 BI 的验收脚本。
**其次是 C2 四阶段链断裂**：阶段 3 声称调 `core.features` 的聚合入口、实参为 `warp_path`，但该入口不存在（4 个函数都以 `samples` 打头），且阶段 4 的 `build_surface` 内部会重新生成全部 12 个端口，使阶段 3 的产物无消费者；同时 `sample_rate` 在门面层无合法来源（`ingest` 只返回 PCM，`profile` 又被禁入）。
**此外，本次审查期间维护者的并发修复在 FILE-203 中新引入了两个缺陷**：`note_spans` 要求传入的 `rms_hop_length` 全文未给出来源（而实现者手上的 `notes` 描述符 `hop_length` 恒为 0，照公式即 `ZeroDivisionError`），以及 `summarize_deltas` 改二参后 §8 自检代码仍按一参调用（实测 `TypeError`）。
