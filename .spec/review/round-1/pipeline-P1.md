# 管线审查报告 · 生产段（P1）

> 审查者：独立数据管线审查者（未参与本仓设计，无共享历史上下文）
> 仓库根：`/Users/Apple/Desktop/dsh-archive/harmonica-eval`
> 审查对象：**全部端口的「生产者侧」**（谁生产端口、生产得对不对）
> 审查方式：静态核对（权威声明 ↔ 模块签名 ↔ Build Instruction）＋ 只读探针
> 探针目录：`.spec/review/round-1/probes-pipeline-P1/`

---

## 0 · 权威声明与测量口径

- **端口权威声明**：`harmonica_eval/profile.py` 的 `PORTS`（12 个 `PortSpec`）+ `contract.FIELD_LAYOUTS`。
- **生产者权威声明**：`PortSpec.produced_by`（`profile.py:207`）。
- **生产约定权威声明**：`.spec/build/FILE-104-v1.md` §4.4（`surface.generate_all_ports`）。
- 实测（`python3`，探针输出见文末）：`PORTS` 12 个端口，`produced_by` 只出现 3 个值
  —— `core.align` / `core.surface` / `core.features`。

**结论先行**：这条管线**不能**从「音频文件」流到「最终评测指标」。
断点不止一处，且**第一断点就在生产段的调度层** —— 12 个端口没有任何一个能
被现有代码 + 全部 Build Instruction 唯一地生产出来。

---

## A · 完整链条（入口 → 终点），含生产者/消费者

| 序 | 环节 | 文件 | 端口 | 生产者 | 消费者 |
| --- | --- | --- | --- | --- | --- |
| 1 | 音频文件 | `真实录音数据集/**/*.mp3` | （无） | — | ingest |
| 2 | 解码 / 下混 / 重采样 | `harmonica_eval/core/ingest.py` | （不产端口） | `ingest(uri)` | `core/api.py:build_surface`（**假定**） |
| 3 | 时间对齐 | `harmonica_eval/core/align.py` | `warp_path` | `align(reference, practice)`（**无调用者**） | **无算法消费**（证据端口，设计豁免） |
| 4 | 特征物化（8 端口） | `harmonica_eval/core/features.py` | `pitch.*` / `rms.*` / `chroma.lowres.*` / `notes.*` | `materialize_*`（**签名不符生产约定**） | pitch / timing / dynamics |
| 5 | 对齐 PCM（3 端口） | `harmonica_eval/core/surface.py` | `pcm.mapped.reference` / `pcm.mapped.practice` / `pcm.warped.practice` | `PortSpec.produced_by="core.surface"`（**无对应函数**） | timing（`pcm.mapped.*`） |
| 6 | 装配 + Seal | `harmonica_eval/core/surface.py` | 全部 12 端口 | `build_surface(reference, practice, sample_rate, warp_path)`（**要求 warp_path 为入参**） | C1 `acquire_surface()` |
| 7 | 会话状态机 | `harmonica_eval/core/api.py:HostCore` | （不产端口） | — | C1 |
| 8 | 算法编排 | `harmonica_eval/host/app.py:HostApp` | （不产端口） | — | 3 个算法 |
| 9 | 算法执行 | `harmonica_eval/algorithms/{pitch,timing,dynamics}.py` | payload | `run(surface)` | `HostApp.run_algorithms` |
| 10 | 投影 | `HostApp.build_view` | `UiScalar` / `UiSeries` | **无生产者**（无 payload→投影映射） | `__main__` / cockpit |
| 11 | 落盘 | `harmonica_eval/__main__.py` | `metrics.json` + `report.md` | `write_metrics_json` | 人类 / CI |

**链条上找不到生产者或消费者的环节**（详见 B 段）：

- 环节 3：`align()` **没有任何调用者**（`FILE-102-v1.md:17` 指向不存在的
  `pipeline.py` / `evaluator.py`）。
- 环节 4：8 个端口**没有符合 `FILE-104` §4.4 四参约定的生产者**。
- 环节 5：`pcm.warped.practice` **没有任何模块声明会做时间归一化**
  （`FILE-104-v1.md:738` 明文「不做 `WARPED` 轴的 PCM 重采样」）。
- 环节 10：`SPEC.md:48-56` 要求的
  `alignment.{mean_abs_warp_sec,tempo_ratio,confidence}` 与
  `sections[]` / `global.pitch_cents_mae` 等指标**没有任何生产者**。
- 环节 11：`__main__.py` 依赖的「contract 导出的会话驱动符号」**不存在**。

---

## B · 发现（FINDING）

### FINDING-1

```
严重度: blocker
位置:   .spec/build/FILE-104-v1.md:330（约定）· .spec/build/FILE-104-v1.md:90（取模块）
        · harmonica_eval/profile.py:253,268,316（produced_by）· harmonica_eval/core/surface.py:94
问题:   12 个端口没有任何一个能被唯一生产 —— produced_by 只指名「模块」，
        而 FILE-104 冻结的四参生成者约定与三个生产者模块的实际函数签名全部对不上；
        且没有「端口 → 具体函数」的映射表。
证据:   profile.py:207 定义 `produced_by: str` 为「哪个模块负责生成它」；
        仅出现 3 个值（探针 P1-01 PASS）：
            core.align / core.features / core.surface
        但 PortSpec 字段清单（探针 P1-02②）里没有函数名/入口字段：
            ['port_id','units','dimensions','element_type','timeline_basis',
             'produced_by','rationale','field_names','hop_length']
        FILE-104-v1.md:330 冻结调用约定：
            「生成者可调用对象接收**位置参数 4 个**，顺序为
             (reference, practice, sample_rate, warp_path)，返回一个 numpy.ndarray」
        实测（探针 probe_dispatch_gap.py ①）：把该约定施加到 produced_by 指名的模块：
            warp_path               produced_by=core.align     4 参生成者=无
            pcm.mapped.reference    produced_by=core.surface   4 参生成者=['generate_all_ports','build_surface']
            pcm.mapped.practice     produced_by=core.surface   4 参生成者=['generate_all_ports','build_surface']
            pcm.warped.practice     produced_by=core.surface   4 参生成者=['generate_all_ports','build_surface']
            pitch.reference         produced_by=core.features  4 参生成者=无
            pitch.practice          produced_by=core.features  4 参生成者=无
            rms.reference           produced_by=core.features  4 参生成者=无
            rms.practice            produced_by=core.features  4 参生成者=无
            chroma.lowres.reference produced_by=core.features  4 参生成者=无
            chroma.lowres.practice  produced_by=core.features  4 参生成者=无
            notes.reference         produced_by=core.features  4 参生成者=无
            notes.practice          produced_by=core.features  4 参生成者=无
        core.features 的实际签名（探针 P1-02④）：
            materialize_pitch(samples, sample_rate)
            materialize_rms(samples)
            materialize_chroma(samples)
            materialize_notes(pitch, rms, sample_rate)
        core.align 的实际签名：
            align(reference, practice)  —— 2 参
        ★ 更坏：pcm.* 的 produced_by 指向 core.surface 自己，而 core.surface 中
        符合四参约定的两个符号之一就是 generate_all_ports —— 调度者本身。
        FILE-104-v1.md:328-329 又要求「实现不得在本文件内另写特征提取代码；
        只做一次查表调用」。若按下表查表，pcm.* 的生成者即 generate_all_ports
        → 无限递归。
修法:   在 profile 里增加「端口 → 具体可调用入口」的显式映射（例如
        `PortSpec.producer: str` 取 "core.features:materialize_pitch"），
        并为每个端口冻结一个统一的调用协议（带 port_id / 侧别的适配层），
        而不是把三个语义完全不同的函数硬塞进同一个四参签名。
```

### FINDING-2

```
严重度: blocker
位置:   harmonica_eval/profile.py:288-305（pcm.warped.practice 声明）
        · .spec/build/FILE-104-v1.md:738 · .spec/build/FILE-105-v1.md:150
问题:   `pcm.warped.practice` 声明了 produced_by="core.surface"，
        但没有任何模块声明会做「时间归一化 / 重采样到与参考等长」这一步 ——
        该端口没有生产者。同时两份 Build Instruction 互相矛盾：
        谁生产两份对齐 PCM，说法不一致。
证据:   profile.py:289-295：
            port_id="pcm.warped.practice", timeline_basis=TimelineBasis.WARPED,
            produced_by="core.surface"
        FILE-104-v1.md:738-739（surface 的 Build Instruction，明文越界声明）：
            「**不做 `WARPED` 轴的 PCM 重采样。** `pcm.warped.practice` 等端口的生成
              在 `produced_by` 指名的模块里；本文件不实现任何重采样算法。」
        → 但 produced_by 指名的正是本文件（core.surface）。自相矛盾。
        FILE-104-v1.md:712-713：
            「**不实现时间对齐、不计算 `warp_path`。** `warp_path` 是入参，
              由对齐阶段产出。」
        FILE-105-v1.md:150（api.py 的 Build Instruction，把这件事派给 ALIGN 阶段）：
            「阶段 2 `ALIGN`：……产出 = `TimelineBasis.REFERENCE` 网格与
              `TimelineBasis.WARPED` 网格上的两份对齐 PCM，以及 warp 路径点。」
        core/align.py:122-132 的 `align()` 返回的是 `warp_path` 一个值，
        文档字符串（align.py:39,98）也只声称产出 warp_path —— **不产 PCM**。
        实测（探针 P1-03）：core.surface 公开符号中无任何
        resample / stretch / warp 归一化函数。
修法:   二选一并写到唯一一份权威处：(a) 在 core.surface 增补一个显式的
        `materialize_warped_pcm(practice, warp_path, ...)` 并让 produced_by 指向它；
        或 (b) 改 produced_by 指向真正做归一化的模块，并同步修 FILE-105 的阶段表。
        无论哪种，`FILE-104:738` 的「本文件不做」必须与 produced_by 一致。
```

### FINDING-3

```
严重度: blocker
位置:   .spec/build/FILE-104-v1.md:330（四参约定）
        · harmonica_eval/core/features.py:104-118（materialize_notes 签名）
        · harmonica_eval/profile.py:412-444（notes.reference / notes.practice）
问题:   四参生成约定里没有 port_id、也没有「哪一侧（reference/practice）」，
        因此无法区分同一个生成者要为哪个端口、哪一侧生产数据；
        notes.* 还需要 pitch/rms 作为中间量，而中间量不在四参参数里。
证据:   profile.py:427-444 声明两个对称端口，二者 produced_by 同为 core.features：
            notes.reference  → produced_by="core.features"
            notes.practice   → produced_by="core.features"
        实测（probe_dispatch_gap.py ⑤）：两个端口的生成者可调用对象签名完全相同，
        返回值无法按 port_id 区分；唯一能让二者不同的信息（哪一侧）不在四参参数里。
        core/features.py:104-108 的 `materialize_notes` 需要先有中间量：
            def materialize_notes(pitch: npt.NDArray, rms: npt.NDArray, sample_rate: int)
        文档字符串（features.py:109-117）还写死为「生成**参考侧**逐音摘要」——
        练习侧没有对应用法，而 profile.py:437 声称 notes.practice 是
        「盲审补齐的对称项」。
        FILE-104-v1.md:330 的四参约定 `(reference, practice, sample_rate, warp_path)`
        既无 `port_id`，也无 `side`，更无 pitch/rms 中间量。
修法:   生产协议必须携带 `port_id`（或至少 `side`），并允许「中间量 → 端口」
        的分阶段物化；否则 notes.*（以及 pitch.*/rms.* 的左右侧）不可能被唯一生产。
```

### FINDING-4

```
严重度: high
位置:   .spec/build/FILE-200-v1.md:167,174（C2 检查口径）· harmonica_eval/profile.py:243
        · harmonica_eval/algorithms/__init__.py:117-155
问题:   `assert_registry_integrity()` 的 C2 用 `port in PORTS` 做成员测试，
        但 `PORTS` 是 `tuple[PortSpec, ...]` 而非字符串序列 ——
        对端名字符串做 `in` 恒为 False，于是**每个算法在 import 期都会判
        「required_ports 含不存在的端口」并抛 RuntimeError**，注册表直接 import 失败。
证据:   FILE-200-v1.md:167：
            | C2 | 每个 `required_ports` 中的每个端口 `port in PORTS` 为真 | `REGISTRY_INTEGRITY:C2:` |
        FILE-200-v1.md:174（把该写法冻结为唯一口径）：
            「**C2 口径**：用 `port in PORTS` 做成员测试（对 `Mapping` 是键成员，
              对名称序列是值成员），不依赖 `PORTS` 的具体容器类型」
        实测（探针 P1-05 FAIL）：
            PORTS 类型=tuple，元素类型=PortSpec
            12 个 port_id 全部 `in PORTS` = False
            >>> "pcm.mapped.reference" in PORTS -> False
        PORTS 定义见 profile.py:243：`PORTS: tuple[PortSpec, ...] = (...)`
修法:   改为 `port in PORT_INDEX`（profile.py:447 已有该 dict 投影），
        或 `port in {p.port_id for p in PORTS}`；并修正 FILE-200 §4.4 的冻结口径。
```

### FINDING-5

```
严重度: high
位置:   .spec/build/FILE-104-v1.md:682,952（INV-104-12）
        · harmonica_eval/profile.py:198-240（PortSpec 字段表）
问题:   INV-104-12 断言 `profile.PORT_INDEX[p].sample_rate`，但 `PortSpec`
        根本没有 `sample_rate` 字段 —— 该不变量按字面无法执行（AttributeError）。
        `sample_rate` 是 `PortDescriptor` 的字段，不是 `PortSpec` 的。
证据:   实测（探针 P1-04 FAIL）：
            PortSpec 字段 = ['port_id','units','dimensions','element_type',
                             'timeline_basis','produced_by','rationale',
                             'field_names','hop_length']
            PORT_INDEX['rms.practice'].sample_rate
            -> AttributeError: 'PortSpec' object has no attribute 'sample_rate'
        FILE-104-v1.md:682：
            `assert d.hop_length == profile.PORT_INDEX[p].hop_length
             and d.sample_rate == profile.PORT_INDEX[p].sample_rate`
        （其中注释还写「chroma/warp_path/notes 的 sample_rate 与 `PortSpec` 一致，均为 0」
         —— 进一步固化了这个不存在的字段）
        contract.py:309 的 `PortDescriptor.sample_rate` 才是真实字段。
修法:   把断言改为对本文档 §4.2「sample_rate 两条规则」的独立核验
        （前缀 ∈ {chroma, warp_path, notes} ⇒ 0，否则 == 传入 sr），
        或在 profile 侧真正补上 `sample_rate` 字段。二者取一，不得悬空。
```

### FINDING-6

```
严重度: high
位置:   .spec/build/FILE-105-v1.md:149 · .spec/build/FILE-101-v1.md:256
        · harmonica_eval/core/ingest.py:96
问题:   api.py 的 Build Instruction 以 **3 个实参** 调用 ingest，
        而 FILE-101 冻结的入口签名是 **1 个参数** `ingest(uri) -> NDArray`，
        且 ingest「不接收 session_id、不产生任何端口」。
        两者无法同时成立 —— 阶段 1 的调用点直接失败。
证据:   FILE-105-v1.md:149：
            「阶段 1 `INGEST`：调用 `harmonica_eval.core.ingest` 的入口，
              实参含 `(s.reference_uri, s.practice_uri, s.profile_version)`」
        FILE-101-v1.md:256（本模块唯一对外入口）：
            `### 4.5 ingest(uri) -> NDArray（**唯一对外入口**）`
        实测（探针 P1-06 FAIL）：
            inspect.signature(ingest) = (uri: 'str') -> 'npt.NDArray'  # 1 个参数
        FILE-101-v1.md:16 还明确：「它在构建流程里对参考与练习**各调用一次**
        `ingest(uri)`……本模块不接收 `session_id`……不产生任何端口」
        → 3 参调用与「不接收 session_id」也互相矛盾。
修法:   统一为「api 对 ingest 调用两次，每次单参」并在 FILE-105 阶段表里逐字写死，
        或改 FILE-101 的入口签名为三参并同步其 MUST NOT。
```

### FINDING-7

```
严重度: high
位置:   .spec/build/FILE-102-v1.md:17,29,42,170 · harmonica_eval/core/align.py:122
问题:   `align()` 没有任何调用者：FILE-102 指名其下游为 `pipeline.py` /
        `evaluator.py`（本仓不存在），并 import 不存在的 `harmonica_eval.exceptions`。
        api.py 虽被要求驱动 ALIGN 阶段，但从未冻结 align 阶段的入口签名。
证据:   实测（探针 P1-07 FAIL）：
            「除 align.py 自身外的调用点 = 无」
        FILE-102-v1.md:17：
            「下游 | `pipeline.py`、`evaluator.py` 调用 `align()` 获取 `warp_path` 用于后续评分」
        FILE-102-v1.md:42：
            「本包内：……`harmonica_eval.exceptions`（`CoreBuildError`、
              `ALIGNMENT_UNRECOVERABLE`、`ContractViolation`）」
        FILE-102-v1.md:170：
            `from harmonica_eval.exceptions import CoreBuildError, ContractViolation`
        实测（探针 P1-12 FAIL）：
            /Users/Apple/.../harmonica_eval/exceptions.py 存在 = False
        FILE-105-v1.md:150 只说「调用 `harmonica_eval.core.align` 的入口」，
        未冻结入口名/签名；core/align.py 的唯一完整入口是
        `align(reference, practice) -> NDArray`（align.py:122）。
修法:   在 FILE-105 中把阶段 2 的入口逐字冻结为
        `align(reference, practice) -> warp_path`，并把 FILE-102 的
        `harmonica_eval.exceptions` 全部改为 `harmonica_eval.contract`；
        删除对 `pipeline.py` / `evaluator.py` 的虚构引用。
```

### FINDING-8

```
严重度: blocker
位置:   harmonica_eval/algorithms/__init__.py:247-272（PAYLOAD_SCHEMAS）
        · SPEC.md:44-57（metrics.json 最小结构）
        · .spec/build/FILE-301-v1.md:190-206（build_view）
        · harmonica_eval/__main__.py:132-147
问题:   「最终评测指标」这一段没有生产者：SPEC §3 承诺的指标名
        （pitch_cents_mae / in_tune_ratio / timing_mae_ms / energy_db_delta /
        sections / alignment.*）与三个算法实际产出的 payload 键**完全不同**，
        且没有任何模块把 payload 映射成 UiScalar / UiSeries。
证据:   SPEC.md:48-56 要求 metrics.json 含：
            "alignment": {"mean_abs_warp_sec", "tempo_ratio", "confidence"}
            "global": {"pitch_cents_mae","in_tune_ratio","timing_mae_ms","energy_db_delta"}
            "sections": [...]
        实际 PAYLOAD_SCHEMAS（实测）：
            pitch    ('per_note_cents','median_abs_cents','off_pitch_ratio',
                      'n_notes_used','sample_rate')
            timing   ('per_note_onset_ms','median_onset_ms','spread_ms',
                      'early_ratio','late_ratio','on_time_ratio','n_notes_used','n_unpaired')
            dynamics ('per_note_delta_db','median_db','spread_db',
                      'n_notes_used','n_unpaired')
        → 无一个键与 SPEC §3 的指标名相同。
        实测（探针 P1-14 FAIL）：在 harmonica_eval/ 全树检索
            tempo_ratio / mean_abs_warp_sec / pitch_cents_mae → 全部 0 命中。
        FILE-301-v1.md:190-206 的 build_view 只规定「下采样 + 声明 timeline_basis」，
        **没有**规定 payload → UiScalar/UiSeries 的键映射（这是 spec 明确留白，
        但结果是没有任何生产者）。
        __main__.py:132-147 只序列化投影里已有的量（「不重算、不补齐、不推断」）
        —— 投影为空则 metrics.json 的 scalars/series 为空。
        → 即使前面全通，终点也只会落下一个空的指标集。
修法:   明确裁定 one of: (a) SPEC §3 的指标结构作废、以 payload 键为准（改 SPEC）；
        或 (b) 新增一个被冻结的「payload → UiScalar/UiSeries」映射表，
        由 HostApp.build_view 实现。当前两者都没有，属无生产者的终止环节。
```

### FINDING-9

```
严重度: high
位置:   .spec/build/FILE-203-v1.md:118-121,130,139-144
        · harmonica_eval/contract.py:397-471,370-394
问题:   dynamics 的 Build Instruction 使用了两个契约里不存在的访问方式：
        (1) `surface.rms.reference` 属性式访问 —— 契约只有 manifest()/read() 两个操作；
        (2) `AlgorithmResultEnvelope(status='FAILED', error=...)` ——
            信封没有 `error` 字段（是 error_code / error_detail）。
        按此规格实现必然 AttributeError / TypeError。
证据:   FILE-203-v1.md:118-121：
            「预期端口存在：
               - `surface.rms.reference`（`list[float]`）
               - `surface.rms.practice`（`list[float]`）
               - `surface.notes.reference`（`list[dict]`，含 `onset_sec`）
               - `surface.notes.practice`（`list[dict]`，含 `onset_sec`）」
        FILE-203-v1.md:130：
            「返回 `AlgorithmResultEnvelope(status='FAILED', error=<str>)`」
        FILE-203-v1.md:139-140：
            `AlgorithmResultEnvelope(status='FAILED', error='MISSING_RMS_PORT')`
        实测（探针 P1-11 / P1-10 FAIL）：
            AlgorithmDataContract 的公开操作 = ['manifest', 'read']
            AlgorithmResultEnvelope 字段 = ['algorithm_id','algorithm_version',
              'status','required_ports','consumed_ports','payload',
              'error_code','error_detail','elapsed_sec']   # 无 'error'
        contract.py:397-471 冻结 read(port_id, time_range)（不是属性访问）；
        contract.py:392-394 是 error_code / error_detail。
修法:   把 FILE-203 改为 `surface.read("rms.reference")` 等，并把 `error=`
        改为 `error_code=` + `error_detail=`；同步清除「list[float]」这类
        与 BufferView 不符的类型描述。
```

### FINDING-10

```
严重度: high
位置:   .spec/build/FILE-201-v1.md:297,357 · harmonica_eval/contract.py:380
问题:   pitch 的 Build Instruction 冻结 status 取值为 `"SUCCEEDED"`，
        而契约冻结的三元取值域是 `{'OK','FAILED','INCOMPATIBLE'}` ——
        实现者按冻结文档写出的信封会被 C1 的 schema 校验判为非法。
证据:   FILE-201-v1.md:297：
            `status = "SUCCEEDED" | "FAILED"`
        FILE-201-v1.md:357：
            「`run()` 两侧音全配不上 | **成功信封** | `status="SUCCEEDED"`，`n_notes_used=0`」
        实测（探针 P1-09 FAIL）：
            契约取值域 = ['FAILED','INCOMPATIBLE','OK']（contract.py:380：
            「'OK' | 'FAILED' | 'INCOMPATIBLE'」）
        FILE-301-v1.md:336 也逐字复述契约三元。
修法:   把 FILE-201 的 `"SUCCEEDED"` 全部改为 `"OK"`。
```

### FINDING-11

```
严重度: high
位置:   .spec/build/FILE-002-v1.md:63,68 · harmonica_eval/contract.py:951-969
        · harmonica_eval/__main__.py:42
问题:   `__main__.py` 的 Build Instruction 允许且依赖
        「`.contract` …… 及该模块导出的**会话驱动符号**」，
        但 contract.py 里**没有任何会话驱动符号**（无 HostApp、无驱动函数）——
        C1 的门面在 `harmonica_eval/host/app.py`，而 §3 又禁止 import host。
        `run_headless` 因此无法按契约调用 C1。
证据:   FILE-002-v1.md:63：
            「本包内 | `.contract`（`UiView` / `UiScalar` / `UiSeries` 及该模块
              导出的**会话驱动符号**） | 投影契约与 C1 会话驱动面」
        FILE-002-v1.md:68（禁止清单）：
            「本包内除 `.contract` 之外的任何模块（含 `__init__`、C2 / C3 的实现模块、
              任何 pipeline / ingest / align / features / metrics 实现模块）」
        实测（探针 P1-13 FAIL）：contract 的 39 个公开名字中，
        无任何 driver / session_driver / headless 符号；
        contract.py:951-969 的 `__all__` 亦无此类符号。
        harmonica_eval/__main__.py:42 只 import UiScalar / UiSeries / UiView。
        FILE-002-v1.md:126 的 run_headless 第 1 步要求「把两段 uri 交给 C1 会话」
        —— 而 C1 的唯一门面 HostApp 在 host 包里，被 §3 明文禁止 import。
修法:   要么在 contract 里正式定义并导出 C1 会话驱动面（协议/工厂），
        要么在 FILE-002 §3 允许 import `harmonica_eval.host`（并说明这是
        composition root），二者取一。
```

### FINDING-12

```
严重度: medium
位置:   .spec/build/FILE-103-v1.md:153-159（materialize_chroma 输出 (n_frames,12)）
        · .spec/build/FILE-102-v1.md:56（compute_alignment_features 输出 (n_chroma,n_frames)）
        · harmonica_eval/profile.py:372-397
问题:   「chroma」这个概念有两个互相转置的生产者：
        features.materialize_chroma 产 (n_frames, 12)（与端口 dimensions=("frame","bin") 一致），
        而 align.compute_alignment_features 产 (n_chroma, n_frames)；
        且 FILE-102 声称 chroma 由 features.py 提供，与 FILE-103 的归属说法不一致。
        两者都被称为「align 的 chroma 输入」，形状不一致。
证据:   FILE-103-v1.md:156：
            「**输出**：2-D `float32` ndarray，形状 `(n_frames, 12)`」
        FILE-102-v1.md:56：
            「**输出**：`float32` 2-D 数组，形状 `(n_chroma, n_frames)`；
              `n_chroma` = `profile.ALIGN.n_chroma`」
        FILE-102-v1.md:16（上游声明）：
            「`features.py` 提供 `compute_alignment_features` 的 chroma 获取函数」
        —— 但 `compute_alignment_features` 定义在 align.py（align.py:65），
        而 features.py 里对应的符号是 `materialize_chroma`（features.py:91）。
        profile.py:373-380 声明 `chroma.lowres.reference` dimensions=("frame","bin")，
        element_type float32 → 与 features 的 (n_frames,12) 一致，与 align 的转置不一致。
        注：chroma.lowres.* 是**证据端口**（无算法消费，设计豁免），
        故该转置**不**直接切断某条算法边；但它使「重跑对齐验证 warp_path」
        这一保留理由（profile.py:381-385）在数据形状上无法直接成立。
修法:   统一 chroma 的轴序为 (frame, bin)（与端口 dimensions / FIELD_LAYOUTS 一致），
        并明确 align 的私有特征由哪一个模块产出。
```

### FINDING-13

```
严重度: medium
位置:   .spec/build/FILE-301-v1.md:64,96-98 · harmonica_eval/core/api.py:50
问题:   host/app.py 的 Build Instruction 一方面**禁止 import `..core.*`**，
        另一方面又要求 `build_default_app()` 构造 `HostCore`（即 core/api.py 的类）
        —— 两条要求不可兼得，composition root 无法实现。
证据:   FILE-301-v1.md:64：
            「**禁止 import**：- `..core.*`（C1 只经 `HostContract` 与 C2 对话，
              不认其内部实现）」
        FILE-301-v1.md:96-98：
            「### 4.2 `build_default_app() -> HostApp`
             - 工厂函数：构造 `HostCore` 并注入 `HostApp`。」
        `HostCore` 定义在 harmonica_eval/core/api.py:50。
        FILE-301-v1.md:89 又说「`core` 是 COMP-C2 的 `HostContract` 实现（`HostCore`）」，
        即参数是外部注入的 —— 与 build_default_app 要自己构造相冲突。
修法:   明确 composition root 的归属：或在 FILE-301 §3 放开
        `..core.api`（且仅该模块），或把 build_default_app 移到 __main__ / cockpit
        这类允许同时看见 core 与 host 的装配点。
```

### FINDING-14

```
严重度: low
位置:   .spec/build/FILE-104-v1.md:718,973 · harmonica_eval/profile.py:181
问题:   端口数在文档间不一致：profile 与 CONTRACTS.md 都写 12，
        而 FILE-104 写「11 个端口」「11 行」。
证据:   profile.py:181：「依据：预生成清单（**12 个端口**）在 120 s 音频下实测约 10–20 MB」
        FILE-104-v1.md:718：「实测 11 个端口在 120 s 音频下约 10–20 MB」
        FILE-104-v1.md:973：「**每个端口的 content_hash 实测值表**：11 行」
        harmonica_eval/core/surface.py:107（已随壳件固化）：「实测 11 个端口在 120 s 音频下约 10–20 MB」
        实测：len(profile.PORTS) == 12。
修法:   把 FILE-104 与 surface.py 壳件中的「11」改为「12」
        （surface.py 已冻结，需作为 MOLD BREAK 处理）。
```

### FINDING-15

```
严重度: low
位置:   .spec/build/FILE-100-v1.md:111 · harmonica_eval/core/__init__.py:35-41
问题:   `core/__init__.py` 的公开面自检判据 B（`declared == produced`）
        按现有 `__all__` 与 `produced_by` 实际不成立：
        多出 `api` / `ingest` 两项（它们不生产端口）。
证据:   实测：
            declared (core.__all__) = ['align','api','features','ingest','surface']
            produced (produced_by)  = ['align','features','surface']
            declared == produced ? False
            declared - produced = ['api','ingest']
        FILE-100-v1.md:111 冻结：
            「定义 `declared = set(__all__)`；定义 `produced = {p.produced_by.split(".")[1]
              for p in profile.PORTS 中所有端口 if p.produced_by.startswith("core.")}`。
              必须 `declared == produced`。」
        FILE-100-v1.md:147 又写「`__all__` 声明 5 个子模块，是因为 `profile.PORTS`
        的 `produced_by` 覆盖这 5 个」—— 事实上只覆盖 3 个。
        core/__init__.py:44-49 的注释亦如此声称。
修法:   把判据 B 改为「produced ⊆ declared」并显式列出 api/ingest 为非生产者置，
        或把 api/ingest 从 `__all__` 移出并说明 C1 的入口仍是 core.api。
```

### FINDING-16 · SKIPPED（无法验证，不报 PASS）

```
严重度: —（信息项）
位置:   harmonica_eval/core/{ingest,align,features,surface,api}.py（全部函数体）
        · harmonica_eval/algorithms/{pitch,timing,dynamics}.py
        · harmonica_eval/host/app.py · harmonica_eval/cockpit/app.py
问题:   仓库当前**全部 74 个函数体均为 `raise NotImplementedError` 空壳**
        （tools/verify_stubs_raise.py: 74/74 正确抛错）。
        因此下列内容**无法验证**，既不能报 PASS 也不能报 FAIL：
          - 各生产者实际产出的 shape / dtype / 字段顺序 / hop_length / 时间轴基准
            是否与端口权威声明逐项一致（无运行时对象可测）；
          - 数值正确性（采样率是否真的 44100、f0 是否为绝对音高、RMS 是否为线性）；
          - `pcm.warped.practice` 的归一化是否真的「与参考等长」；
          - content_hash 的跨实现一致性。
        本报告所有结论均为**静态（声明 ↔ 签名 ↔ Build Instruction）**层面的
        可机械判定事实，不构成对数值实现的验证。
证据:   $ python3 tools/verify_stubs_raise.py
            ✅ 全部空壳的『调用必炸』断言成立（74 个空壳函数）
        $ python3 -c "import inspect, harmonica_eval.core.surface as m; \
            print([n for n,o in vars(m).items() if inspect.isfunction(o)])"
            → 全部为 (raise NotImplementedError) 空壳
修法:   在注入实现后，需以运行时探针重跑本轮 P1 的 shape/dtype/字段顺序核对；
        本轮无法给出这些项的 PASS。
```

---

## C · 判定：这条管线能不能完整跑通？

**不能。** 判定 **REJECT**。

理由（按链条顺序）：

1. **生产段的调度层就不成立（FINDING-1）**：12 个端口没有一个能由
   `produced_by` + FILE-104 的四参约定唯一生产。三个生产者模块里，
   `core.features` 的四个函数无一符合四参签名，`core.align` 的 `align()` 只有 2 参，
   而 `core.surface` 唯二符合者之一就是调度者自身（会递归）。
   这不是「某个端口有问题」，而是**没有端口 → 生产者的绑定**。

2. **有一个端口明确无人生产（FINDING-2）**：`pcm.warped.practice`。
   profile 说 `core.surface` 生产，FILE-104:738 说 `core.surface` 不做这件事，
   FILE-105:150 说 ALIGN 阶段生产，而 `align()` 只返回 warp_path。
   三份文件三个说法，实际没有任何函数做时间归一化。

3. **对称端口无法区分左右侧（FINDING-3）**：`notes.reference` 与
   `notes.practice` 的 produced_by 完全一样，生产协议里没有 side/port_id，
   且 notes 依赖 pitch/rms 中间量 —— 中间量不在参数表里。

4. **入口与调用点不匹配（FINDING-6/7）**：ingest 被要求按 3 参调用（实际 1 参）；
   `align()` 全仓无调用者，其文档指名的下游是不存在的 `pipeline.py` / `evaluator.py`，
   并 import 不存在的 `harmonica_eval.exceptions`。

5. **注册表在 import 期就炸（FINDING-4）**：C2 的 `port in PORTS`
   对 12 个 port_id 恒为 False → `assert_registry_integrity()` 抛
   `REGISTRY_INTEGRITY:C2` → `import harmonica_eval.algorithms` 失败，
   C1 拿不到算法清单。

6. **终点没有生产者（FINDING-8）**：SPEC §3 承诺的
   `alignment.*` / `global.*` / `sections[]` 指标名与算法 payload 键
   无任何对应，也没有 payload → UiScalar/UiSeries 的映射。
   投影恒为空 → metrics.json 的 scalars/series 为空。

7. **另有若干「按文档实现必炸」项（FINDING-5/9/10/11/13）**：
   不存在的 `PortSpec.sample_rate`、属性式 `surface.rms.reference`、
   信封的 `error=`、非法的 `status="SUCCEEDED"`、
   contract 里不存在的「会话驱动符号」、被禁止 import 却必须构造的 `HostCore`。

**能跑通的部分（不构成结论改变）**：
- 12 个端口的**声明侧**本身是自洽且可 import 的
  （`assert_profile_integrity()` 在 import 期通过）；
- `tools/verify_shell.py` / `verify_stubs_raise.py` / `build_virtual_graph.py`
  三个机械检查全部通过 —— 但它们只检查「壳件是否完整、是否必炸、文档引用是否可解析」，
  **不检查端口能否被生产**。这正是「机械检查通过 ≠ 管线通」的实例。
- 四个「证据端口」（`warp_path` / `pcm.warped.practice` /
  `chroma.lowres.*`）无算法消费是**设计明文豁免**的（algorithms/__init__.py:127-139），
  本身不是缺陷；缺陷是其中 `pcm.warped.practice` 连生产者都没有。

---

## 探针清单（未删除）

| 文件 | 作用 |
| --- | --- |
| `probes-pipeline-P1/probe_producer_chain.py` | 14 条生产段静态断言（P1-01…P1-14）；输出 3 PASS / 11 FAIL |
| `probes-pipeline-P1/probe_producer_chain.out` | 上述脚本的原始输出 |
| `probes-pipeline-P1/probe_dispatch_gap.py` | 专测「端口 → 生产者」绑定缺失；含递归风险与四参约定比对 |
| `probes-pipeline-P1/probe_dispatch_gap.out` | 上述脚本的原始输出 |

复现：

```bash
cd /Users/Apple/Desktop/dsh-archive/harmonica-eval
python3 .spec/review/round-1/probes-pipeline-P1/probe_producer_chain.py
python3 .spec/review/round-1/probes-pipeline-P1/probe_dispatch_gap.py
```

---

## 状态汇总

| 状态 | 条目 |
| --- | --- |
| FAIL | FINDING-1…15（共 15 条，其中 blocker 3 条、high 7 条、medium 3 条、low 2 条） |
| SKIPPED | FINDING-16（全部函数为空壳，shape/dtype/字段顺序/数值一致性无法验证） |
| PASS | 仅「端口声明侧自洽 + 三个机械检查通过」这一有限事实（见 C 段末） |

---

VERDICT: REJECT

blocker 清单（至少一条，实际三条）：

1. **FINDING-1** —— 12 个端口没有任何端口 → 生产者的绑定；
   `FILE-104` §4.4 的四参约定与 `core.features` / `core.align` 的全部函数签名不符，
   且 `pcm.*` 指向调度者自身（递归）。
2. **FINDING-2** —— `pcm.warped.practice` 无生产者：profile 归 `core.surface`、
   `FILE-104:738` 说 `core.surface` 不做、`FILE-105:150` 归 ALIGN 阶段，
   而 `align()` 只返回 `warp_path`。
3. **FINDING-8** —— 终点无生产者：`SPEC.md:48-56` 承诺的
   `alignment.*` / `global.*` / `sections[]` 指标与算法 `PAYLOAD_SCHEMAS` 无对应，
   也没有 payload → `UiScalar`/`UiSeries` 的映射，`metrics.json` 的指标集必为空。
