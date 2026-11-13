# Axiom Evidence v0.2 机器契约草案

2026-11-07，基线为 dev 的 90d2593 及已核对的 S1–S3 审阅材料。状态为待审阅。本文与[机器登记](contract.json)定义 verification profile 的候选字节、身份和结果绑定。其余九项 AX-B01 核心义务仍按完整全集检查，所需真实执行和公共支持待补齐。P6 保持 closed / p6-not-evaluated。 [支持汇总与迁移演练](../evidence-v0.2-minimal-support-review.md)

2026-11-13 接续：所有者确认 C1–C6 后，新增[独立交换 v0.2 审阅](../evidence-v0.2-independent-check-review.md)及[单独候选机器包](independent-check-v0.2/contract.json)，包含新来源绑定、结构化中止与离线交接材料。本页原登记、旧指纹及 Rust 接口不变；新交换检查不代表公共接受或分仓验收。

## 字节、版本与身份

顶层精确使用登记的 document 成员，format 为 axiom-evidence，evidence_version 为 0.2，digest_algorithm 为 sha-256，obligation_profile 为 keyed-finite-table-verification / 0.2。本稿仅选择 verification。benchmark profile、额外执行模式以及新的独立 request / manifest / result 字节另行审定。读取器从受信的契约标识选定规则，不因输入中的版本串自动启用支持。

机器字节是 UTF-8 JCS 的 IR JSON 子集。对象键按 UTF-16 码元序排序，禁止重复解码键、非法 Unicode、number 和 null。整数均用规范非负十进制字符串，零为 0。保留名称原 Unicode 标量序列，无 BOM、额外空白或末尾 LF。严格入口比较原始字节，不以规范化修复后的字节代替原件。

摘要写作 sha256: 后接 64 位小写十六进制。artifact 的 content_digest 是实际原字节 SHA-256。IR 文档域 ID 沿 IR v0.2。tool、execution、obligation、trust、uncovered 条目按登记的域对 UTF8(domain) + NUL + JCS(definition) 计算 ID。完整 Evidence 对整个规范文档用 document 域计算 ID，既不内嵌该 ID，也不与原始摘要混用。义务 result 位于 definition 外，替换 result 会改变 Evidence 文档身份。

顶层 artifacts 按 content_digest 严格递增，tools、executions、obligations、trust、uncovered 按 id 严格递增。每个制品只登记一份 byte_length、format 和 format_version，同一制品可由多个角色引用。所有引用须解析至对应登记，禁止悬空引用和未引用制品。实际取得但长度或摘要不符时拒绝；独立路径缺少必要原件时报告 incomplete。

## Subject、工具与执行

| 部分 | 闭合成员及绑定 |
| --- | --- |
| 合法 subject | kind 固定 axiom-ir，ir_version 为 0.2，ir_artifact 指向规范 IR 原件，ir_document_digest 为独立重算的文档域 ID。semantics 恰含 name 和带 sha256: 前缀的 sha256，与已选 v0.2 IR 语义及 P2 绑定一致。 |
| 拒绝 subject | 恰含 kind: rejected-ir 与 artifact。artifact 指向原始候选，描述为 ir-candidate / 0.1。首版拒绝分支仅装配一项结构义务，trust 为空。结构义务的 definition 恰含 kind: ir-structure、expectation: check，subject 与顶层拒绝 subject 一致。 |
| tool | definition 恰含 artifact、name、roles、version。artifact 绑定实际工具制品，name 为稳定名称，version 为精确版本或不可变修订。roles 是严格递增的非空角色集合。producer 指向含 evidence-producer 的工具。 |
| execution | definition 恰含 kind、mode、tool、obligation、ordinal、provenance、rule、inputs、outputs、limits、result。obligation 绑定唯一目标 ID。ordinal 为该 Evidence 内从零开始连续的尝试顺序，参与 ID 计算，防止相同尝试被去重。顶层数组仍按 ID 排序。 |
| 规则与来源 | rule 引用 evidence-rule / 0.1 原件，且匹配登记的精确模式摘要。provenance 引用 execution-provenance / 0.1 原件，绑定执行来源材料的字节。该引用只提供身份绑定，生产使用前须另审实际采集格式和可信来源。 |
| 输入、输出、限额 | 引用恰含 role、artifact，按两者字典序严格递增，模式内每角色至多一次。限额恰含 name、unit、value，按 (name, unit) 严格递增，限额名称、单位及必需集合见登记。 |
| 执行结果 | 完成恰为 {kind: completed}，表示取得该模式所需的确定判定或完整推导。中止恰含 kind、code，后者为稳定的诊断标识。候选模式的中止 outputs 为空，伴随观察可随 provenance 保留。 |

kind 与 tool role 按[登记映射](contract.json)检查，每次执行都须持有该 kind 的角色。首版只给 normalize 和 prove 的三个模式定义可接受结果支持。其余登记角色保留精确映射，不能凭角色匹配取得新模式支持。

| 模式 | 完成执行的精确制品角色 |
| --- | --- |
| strict-ir-v0.2 | 输入 candidate。通过时 candidate 和输出 canonical-ir 引用同一 axiom-ir / 0.2 制品。拒绝时 candidate 为原始 ir-candidate。输出始终含 structure-observation，通过时还含 canonical-ir。 |
| core-empty-effects-v0.1 | 输入 canonical-ir、obligation-set（axiom-obligation-set / 0.2）及 generator-source / 0.1，输出 derivation（axiom-core-effect-derivation / 0.1）。 |
| core-field-origin-v0.1 | 输入同 S2，输出 derivation（axiom-core-field-origin-derivation / 0.1）。执行目标是单一输出字段。 |

## 义务、结果和独立核对

合法 IR 的 IR 派生 definitions 完全沿用 P2。checker 从实际 IR 重建全集，并加入实际信任义务。每个 trust 条目对应一个 trust-boundary / trust 定义，其 subject 恰含 kind: trust、category（同 trust definition）、scope（对应 trust ID）。trust 和 uncovered 的 definition 成员见登记。scope 建议使用闭合 {kind, ref}，分别允许引用 subject、artifact、tool、execution、obligation；mitigations 按 (kind, ref) 严格排序并引用实际 artifact 或 execution。scope 的解析及信任类别须在公开规则验收中逐项核对。 [信任规则基线](../axiom-evidence-v0.md#信任与未覆盖项)

| 结果 | 成员与检查 |
| --- | --- |
| S1 checked | execution 引用已完成的严格 normalize，artifacts 是其 inputs / outputs 摘要的有序去重并集。structure-observation（axiom-ir-structure-observation / 0.1）恰为 {kind: accepted, document: <IR 文档 ID>}。 |
| S1 failed | execution 引用已完成的严格拒绝。structure-observation 恰含 kind: rejected、reason 和 location。reason 仅为 noncanonical-ir、invalid-utf8、unknown-top-level-member。前两种 location 恰含 kind: candidate-bytes、offset、length，按原始字节定位。第三种恰含 kind: candidate-member 与单元素 path，元素是被拒绝的顶层成员。 |
| S2 / S3 proved | support 恰含 kind: kernel-replay、execution。引用完成的匹配 prove，其输入 IR 与 subject 相同，P2 全集须独立重建一致，内部 generator 字段匹配 generator-source 原字节摘要。随后按各自规则重演程序根或字段三根及闭包。 |
| unknown | attempts 是非空、严格递增的执行 ID 数组，均绑定同一目标及相符的中止原因。reason 映射见登记。本稿的 unavailable 指已调度后有记录的工具不可用。未确立 subject 时停止装配。 |
| trusted | trust 指向该 trust-boundary 目标对应的实际 trust 项。核心义务仍按 check 或 prove 的规则处理。 |

checked、failed、proved 的 assumptions 是按 trust ID 严格递增的实际依赖。S1 failed 的 counterexample 恰含 kind: structure-path、minimality: {kind: unreduced}、observed: {reason}、空 preconditions、空 worlds 和单项 trace。trace 在 location 的字段上加 artifact 指向原候选。独立路径须复现确定性拒绝和精确定位。非规范字节以首个不同字节或共同前缀结束位置为起点。无效 UTF-8 以首个无效序列的起点定位。原件内的定位长度为一字节，EOF 为零。仅有诊断文本不足以完成支持。

完整结论在首版支持范围内采用以下规则。拒绝分支的结论为 structure_rejected，refs 为结构义务 ID。合法 verification 已具备全义务结果但有真实 unknown 时为 inconclusive，refs 为对应义务 ID。全部期望成立且无必需材料阻断时为 satisfied，refs 为空。缺义务或缺真实执行的装配停在文档形成前。独立 checker 依自身规则核对 P1、P2 与 S1–S3，保留 missing artifacts、剩余 trust 与 TCB。独立结果绑定新 Evidence 原始及文档域摘要，另有自身请求和 checker 身份。现有 v0.1 reader 按原支持集合拒绝本草案版本。 [ADR 0008](../../adr/0008-independent-checker-isolation-and-artifact-exchange.md#独立检查行为) · [ADR 0009](../../adr/0009-axiom-evidence-v0-drift-and-migration.md#决策)

## 本地向量

从仓库根运行：

```bash
python3 -I -B docs/evidence/evidence-v0.2-machine-contract/check_vectors.py
```

脚本复用本仓 Python JCS、P2 与 P3-E/F 对照入口。合成执行来源明确标记，真实 IR / P2 原件沿用冻结材料。三个完整的 S1 拒绝样例固定原始和文档域摘要；S1 通过与预算中止、S2、S3 两字段以单目标投影核对执行及义务 ID。五个投影送入整份文档校验时均因缺全集被拒绝。脚本同时检查 UTF-16 键序、非规范 JSON、重复成员、旧版本和域、错字节或缺制品、错角色、错预算、跨字段换绑、敏感行控制和两项 group 义务分别省略。

[固定摘要](fingerprints.json)由脚本的 --show-fingerprints 输出形成，正常核对只读。草案变化需审阅摘要差异后再更新。Python 向量有意限定为固定材料。

## Rust 本地读回

本仓的 `evidence_review::readback_v02` 显式读取候选 verification 文档。调用方提供字节、只读摘要解析器和 `ReviewLimits`。入口检查规范字节、制品、条目身份、角色、执行顺序和限额，按实际 IR 重建 P2 全集，再从记录绑定重做 S1 检查和 S2 / S3 推导。实际执行及其中止的来源材料由独立信任边界核实。读回返回两种文档摘要，错误保留发生阶段及缺失制品。合法 AX-B01 的部分义务集在进入结果检查前拒绝。 [Rust 入口](../../../crates/axiom-ir/src/evidence_review.rs)

Rust 定向测试通过 Python 的 --rust-vectors 只读输出取得相同的三个完整拒绝样例、五个 AX-B01 部分样例，以及两份仅含 input 的完整合成文档，分别核对 checked、proved 和已确立 subject 的资源中止。负例核对旧版本、非规范字节、错角色、缺失 / 错误制品、错结论、重算执行身份后的跨字段错绑，以及公开值但敏感行控制的字段。公共入口、生产 Evidence 装配、实际执行认证、独立 checker 与完整迁移演练仍须分别验收。

```bash
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir evidence_review::tests --lib --locked --offline
```

## 后端绑定候选

[后端登记](backend.json)把 [B1–B3 审阅](../ax-b01-evidence-v0.2-backend-support-review.md)具体化为来源封套、执行模式和结果引用。它使用本页的 Evidence 域、执行成员、ID 与排序规则。离线投影只有一项 P2 义务、一次求解及其可选重放、所用工具和信任条目。投影单独计算原始 SHA-256，用于比对向量。完整 Evidence 的义务全集、trust-boundary 条目及结论仍由正式入口验收。基础登记保留 S1–S3 原字节；后端模式通过显式本地候选入口扩展。

2026-11-13 所有者已确认 [D1–D5](../ax-b01-evidence-v0.2-backend-support-review.md#所有者确认的实施决定2026-11-13)。重放工具四类漏拒绝已修复；原 12 个投影指纹不变，拒绝用例增至 20 项。旧脚本仍只检查固定投影；完整合成文档、来源批次、信任与历史由下述 Rust 候选入口验证。此前观察留存于[审查记录](../../records/2026-11-13-evidence-backend-review.md)，不得把修复后的结果覆盖回历史记录。

| 对象 | 闭合绑定 |
| --- | --- |
| `axiom-evidence-backend-capture / 0.1` | `invocation` 标识实际调度尝试，由采集端分配并与精确请求绑定。 `launch` 指向归档、执行文件、接受记录、依赖清单、宿主、监督器、策略和资格。正常运行须从实际执行和加载观察核对这些引用。 `observation` 指向原始捕获原件，`proof_policy` 记录此次生产策略，`terminal` 由同一次捕获及严格协议观察重建。 |
| 流引用 | `complete` 或 `prefix` 恰含 `kind`、`artifact`，分别引用完整流或已取得的前缀。确无流时用 `{kind: absent}`，并由捕获原因支撑。只有成功退出、完整流和清理齐全的运行可提供正常响应。 |
| `p4-solver-response-v0.2` | `prove`／`prover`，provenance 引用上述封套原字节。输入角色、格式和预算见登记。有效 response 的 request、stdout、stderr 与封套及实际请求字节交叉核对。 `completed` 时输出唯一 response；`interrupted` 时无正常输出，保留带原因的捕获原件。归档和接受摘要与 P4 请求匹配，工具条目绑定实际 CLI。工具缺失的分支只引用已登记的预期制品，并须有可核对的已调度失败记录。 |
| `axiom-evidence-backend-replay-source / 0.1` | 独立的 replay invocation，绑定求解 execution ID、重放原件与终态。来源端对回放工具、重放请求与实际尝试提供外部核验。相同 stdout 或 world 不能替代具体 solve execution。 |
| `p4-target-replay-v0.1` | `replay-counterexample`／`counterexample-replayer`，仅接同目标的 `sat`。完成须具备模型候选、规范 world 及完整 P4-B 观察。若实际重放任务在模型解码阶段中止，使用 `inputs_before_world`，禁止合成 world 或 target-replay 输出；到达重放后中止则保留实际输入及诊断原件。 |

规范封套的 raw 摘要由验证端用独立受信的 invocation 绑定核对。启动和重放来源须可验证，封套内的 `scope` 与身份声明只参与绑定。离线脚本先验证既有 Rust 合成导出，再单独生成并提供模拟环境的预期 pin。所有样例的 scope 为 `simulation`，改写为 `qualified` 会被拒绝。真实观察原件格式、外部来源配置、重放认证和实际工具资格属于后续实现验收。 [既有模拟导出及其检查器](../../../scripts/check-solver-simulation-export.py)

### 结果投影

- `proved / backend-attestation` 的四个引用按登记闭合。只接受绑定正常 `unsat` 的求解 execution。首批审阅候选保留 `proof-backend`、`production-generator`、`host-runtime` 三项实际依赖，scope 分别绑定 solver tool、生成该查询的执行上下文和受控运行上下文。求解 execution 的 request 绑定 generator 原件、query 规则和同一目标。独立路径若确立查询对反例的覆盖，才可按 B1 规则缓解 generator trust。独立请求要求证书或未允许任一剩余 trust 时，产生策略不完整判定。
- `failed` 的候选 counterexample 使用 `target-replay` tag，含 `{kind: unreduced}`、一个与模型候选逐字节一致的规范 world、全部已满足的 assume ID，以及同一观察的 `result.witness`。trace 恰含两步，先 `{kind: obligation, ref}` 绑定精确义务，再 `{kind: replay-observation, artifact}` 绑定观察原件。独立 checker 须直接重做 WF、全部 Pre 和指定目标后核对投影。
- `unknown` 的 reason 按登记的阶段终态和原因表产生。已完整取得的 `unknown` 协议帧、已完成但未发现目标违反的 replay，或生产侧 `certificate-required` 收到 `unsat` 却缺可接受证书，均可引用已完成的组件 execution。终态只表示该组件实际完成了相应工作。若多个尝试实际发生，候选按最后一次尝试的可核对终态选择 reason，引用同目标同原因的终态执行，保留全部历史 executions；单次离线投影尚未覆盖多次尝试的整体聚合。

### 离线复核

从仓库根运行，给导出指定新的 .tmp 子目录。

```sh
out=".tmp/evidence-backend-vectors-$(uuidgen)"
cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-solver-diagnostic-host \
  --example export_simulation_observations --locked --offline -- "$out"
python3 -I -B docs/evidence/evidence-v0.2-machine-contract/check_backend_vectors.py "$out"
```

[固定指纹](backend-fingerprints.json)由同一脚本加 `--show-fingerprints` 输出。12 份投影覆盖实际生成的 P4 合成字节，包括原容量 AX-B01-wrong-add 的 guarantee、未见违例的有限重放、后端 unknown、证书策略、截断、清理故障与内存／期限归因。20 项负例核对缺独立来源 pin、重算身份后改写来源或宿主、归档冒充 CLI、错角色、旧 attestation 挪用、目标换绑、错上游执行、丢 Pre 或 trust，以及摘要和原件缺失。脚本只验证合成投影，实际执行来源、完整 M1 及公共读回仍待验收。P6 为 `closed / p6-not-evaluated`。

### 完整文档的本地候选读回（2026-11-13）

`readback_v02_with_backend` 复用基础读回，显式接收 `BackendReviewContext`。旧 `readback_v02` 不会隐式启用后端来源。新增登记位于 `backend.json.local_readback`，限 `simulation`；`qualified` 等范围拒绝。所有接受、资格、可执行文件和 captured-source 在测试中均为明确合成字节，引用闭包不代表真实资格认证。

批次先按 `ReviewLimits.evidence_json.max_input_bytes` 检查原件长度，再计算摘要和解析，避免超限输入消耗完整摘要扫描成本。

调用方传入规范 `batch` 原件及 Evidence 外固定的 `expected_batch_digest`，另传消费侧 `ProofPolicy`、有序信任类别允许集和本机 solver / replay 组件资源上限。batch 绑定本版 backend 登记原始摘要、精确 subject / P2、生产策略和全部后端 executions，按整数 ordinal 排序。每项包含 execution ID、唯一 invocation、provenance、request 和 upstream。execution ID 进一步绑定目标、工具、规则、预算及输入输出；replay 必须在后端清单中紧跟同目标 solve。清单不包含最终 Evidence 摘要，避免循环。删除历史再重编号或换批次必须同时违背外部固定 pin，不能凭 producer 自填新 pin 通过。

`capture_observation` 记录已调度 / 已启动、实际 stdin、完整 / 前缀 / absent 流、观察长度、exit、cleanup、资源事件及耗时；完整空流仍不同于 absent。同一时间的事件按登记顺序判定，保留最先原因。固定外层 128 MiB / 6 s 及原传输限额不变；这里只核对记录，不实现强制执行或资格检查。请求、响应、模型、world 和重放由现有 P4 组件重建；模型解码前中止无 world，到达重放后的中止保留真实输入与具名诊断。诊断 `detail` 绑定本地组件版本的完整 Debug 文本，尚不是公共稳定错误协议。

每个 solve / replay 都必须存在精确 execution scope 的 host-runtime，包括 unknown 和已被后续支持取代的历史。允许 attestation 的 unsat 另需 solver tool scope 的 proof-backend 与 solve execution scope 的 production-generator。全部 trust 参与 trust-boundary 义务和消费政策检查。生产 certificate-required 产生 unknown；消费 certificate-required 对已有 attestation 返回本地 `BackendPolicyStatus::Incomplete`。`TrustAllowed` 只说明本地允许集满足，**不是**独立四态、来源接受或 P6 放行；缺原件保留 `MissingArtifact`，已知矛盾返回结构化错误，不伪造独立结果。

聚合按 D4：完成支持不被后次 unknown 覆盖；多个相容完成支持取最后一个，同目标 unsat 与有效反例冲突则拒绝；全未决取最后求解链 reason 并引用所有匹配终态，保留其他历史。完整 P2 和 trust-boundary 全集必须齐备，结论按 failed、unknown、全部满足依次重算。读回返回 Evidence 两类摘要及 batch / backend 契约摘要，尚未形成新的独立 request / manifest / result。

```sh
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir evidence_review:: --lib --locked --offline
```

测试源码构造完整合成包，复用 `check_vectors.py --backend-core <IR>` 生成 S1–S3 前缀；该前缀不是合法完整 Evidence。Rust 测试随后补全部后端结果、信任、制品和结论。`check_backend_readback.py` 从 stdin 接收测试包，用已有 Python 有限解释器核对五类目标、两种 wrong 归因及 Pre 拒绝，并验证生产结果不一致会被拒绝；它不认证 batch、不复核 unsat，也不是分仓独立 checker。四份完整测试包的两类 Evidence 摘要、批次及契约摘要固定在 [backend-readback-fingerprints.json](backend-readback-fingerprints.json)，正常测试只读核对；修改字节需先审阅差异再更新该候选基线。生成入口、验证范围和仍待完成的交接见[实施记录](../../records/2026-11-13-evidence-backend-implementation.md)。
