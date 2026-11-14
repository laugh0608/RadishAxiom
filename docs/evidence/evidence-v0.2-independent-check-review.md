# Evidence v0.2 机器字节与独立 checker 交接审阅

日期：2026-11-13（Asia/Shanghai）；2026-11-14 接续本仓 Rust 适配。交换草案基线为 `dev` 的 `ed4f4d0`，Rust 接续基线为 `bc25628`。所有者已确认 C1–C6 与下述 R1–R6 的本仓候选实施范围。

用途：供规范、生产读回与独立 checker 维护者审阅版本、来源、稳定中止事实和跨仓验收。本文及[机器包](evidence-v0.2-machine-contract/independent-check-v0.2/contract.json)是候选，未发布、未获产品运行资格。本仓 Rust 适配仍是显式候选入口；不包含分仓写入、真实 solver、公共发布、完整迁移或 P6 放行。P6 仍为 `closed / p6-not-evaluated`。

## C1 · 版本、字节与兼容

| 对象 | 本批候选 | 与旧材料的关系 |
| --- | --- | --- |
| Evidence | `axiom-evidence / 0.2`、verification profile `0.2` | 复用已审阅的基础域、S1–S3、D1–D5；四份既有完整合成 Evidence 原字节不变。 |
| 后端登记与批次 | backend review `0.2`、backend batch `0.2` | 从旧登记形成单独文件；batch 引用新登记的 raw 摘要，重新生成其身份，不改旧登记。 |
| 独立交换 | request / manifest / result 和 `keyed-finite-table-independent-check` 均为 `0.2` | 旧 `0.1` 的格式、域、fixture、读取器及 Rust runtime consumer 不变；无自动降级或版本别名。 |
| 重放中止 | `axiom-evidence-replay-interruption / 0.2` | 采用结构化 cause 与 component policy；旧 `0.1` Debug 中止不能直接转换。 |

规范字节沿用 Evidence 的 UTF-8 JCS 子集：禁止重复解码键、非法 Unicode、number、null、额外空白和末尾 LF；键按 UTF-16 码元排序，不做 Unicode 归一化。机器登记和 schema 使用便于审阅的 JSON 原字节，按 raw 摘要绑定，不要求它们自身是 JCS。

新域分别为 `axiom-independent-check-v0.2:request`、`:manifest`、`:check`、`:result`，均对 `UTF8(domain) + NUL + JCS(value)` 计算 SHA-256。manifest 的身份是完整 manifest 文档域摘要；request 的 `bundle_manifest` 引用该身份。`evidence`、`source_binding.batch`、`source_binding.backend_contract` 均为原字节摘要。result 同时引用 request / Evidence 的 raw 与文档域摘要。不得用一种摘要替代另一种。

manifest descriptor 的 `format` 在新版本明确使用 `[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*`，以表示已经存在的 `axiom-smtlib2-qf-uflia-query0.3`。这是一项具名的版本差异：旧 `0.1` 不允许点号，旧规则不修补。新格式仍拒绝大写、空段、路径和下划线；合法词法不代表某个格式已受语义支持。

固定输入与旧身份见机器包 `bindings`；本批生成器、源文件与新产物身份也登记于包内。旧 Rust 入口继续消费旧 backend 候选；R1–R6 新入口显式消费 batch / interruption v0.2。request / manifest / result 的交换检查仍由离线审阅工具执行，不是 Rust runtime consumer 或独立 checker 新协议接入。

## C2 · 调用方来源与无环绑定

request 在旧六项成员之外增加必需的闭合成员：

```json
"source_binding": {
  "kind": "backend-batch",
  "backend_contract": "sha256:<backend 原字节>",
  "batch": "sha256:<封存批次原字节>",
  "scope": "simulation"
}
```

没有后端执行的材料必须使用 `{kind: no-backend, scope: simulation}`，包括 S1 的结构拒绝和仅 S1–S3 的完整材料；仅允许基础登记的三个模式。此时不要求或合成 batch、合法 IR 或 P2。模式名不能单独决定分支：还须核对 execution 身份与顺序、kind／工具角色、目标种类、精确 rule 及输入输出角色。仍必须由调用方固定 request raw，预期 batch 必须为空。存在任一后端执行则必须选 backend-batch；把完整后端包改为 no-backend 并重算所有交换身份仍拒绝。

只读目录仍为 `request.jcs`、`manifest.jcs`、`blobs/sha256/<digest>`。manifest 新增 `backend-contract` 与 `source-batch` role，在 backend-batch 分支各恰好一次，在 no-backend 分支都不得出现；保留 evidence 恰好一次、digest 唯一、角色排序及 subject / evidence-artifact / normative-spec 的规则。新角色不能只以同名字段替代实际原件。

调用顺序：

1. 调用方从与 producer 分离的受信渠道取得预期 request raw 摘要、存在后端时的 batch raw 摘要，以及获准的候选契约身份；它们不由 bundle 内的自述文件授权。
2. 入口先限制 request / manifest 字节量，再核对 request raw pin，严格解析 request，检查 manifest 文档域 ID 与 source binding。取得 Evidence 后核对其实际 format、version、profile、摘要算法；manifest 必须逐项覆盖 Evidence 的制品描述并匹配 subject role，不能仅以 manifest 标签宣称版本或删除描述来隐藏缺件。两份清单都删掉一个仍被 execution／工具／捕获封套引用的原件也须拒绝；描述保留而字节缺失才进入缺件判定。工具、义务、信任、未覆盖项和 execution 身份分别重算，不以可解析的 ID 字符串代替绑定。
3. 先检查声明长度、总量和实际长度，再计算每份原件摘要；已知错字节优先于并存的缺件。缺件记录为不足，不联网或读取生产缓存补齐。
4. batch 必须绑定同一 IR 文档 ID、P2 原件、生产策略、全部后端 executions，按数值 ordinal 顺序列出；invocation 唯一，replay 紧随唯一同目标 solve。清单与 Evidence 对照，并将 invocation、生产策略、请求及上游 solve 对回已有捕获／重放封套；唯一 invocation 不等于它属于这次捕获。删除历史或错绑不能仅靠重算摘要绕过。

batch 不包含最终 Evidence 身份，避免循环；request 同时绑定 Evidence、manifest、batch 和契约，result 在外部绑定 request。`input-only-authority.json` 与临时导出的 `authority.json` 是合成装置的预期值记录，**不是生产授权来源**。重新封装 fixture 时自行生成 pin 只用于测试。

完整性只指这一封存批次，不证明世界上不存在其他执行。真实捕获入口、可信请求配置、接受记录、工具及宿主资格仍未闭合；仅增加 scope 字符串不得获得真实来源身份。本批只有 `simulation`，`qualified` 拒绝。

## C3 · 稳定中止事实与诊断

[中止 schema](evidence-v0.2-machine-contract/independent-check-v0.2/schemas/interruption.schema.json)固定 format、version、scope、generator、request、solve_execution、component_policy、stage、code、cause、diagnostic 十一项。每份记录仍由 replay provenance 引用，并经 execution 与 batch 绑定。

| cause | 允许的阶段／code | 核验要求 |
| --- | --- | --- |
| `resource-limit`，含 resource、limit | model / replay 的 `component-limit` | resource 必须属于该阶段；limit 为规范非负整数字符串，等于所绑定生产组件策略中的值。零表示显式零预算，不表示无限。 |
| `input-error`，含 artifact、reason | model 的 `model-decode`；replay 的 `replay-error` | model 支持 binding-mismatch / invalid-model；replay 支持 binding-mismatch / invalid-world / noncanonical-world。原件须属于该次输入闭包，并独立核对所声明类别。 |
| `unsupported`，含 feature | replay 的 `unsupported` | 首批闭合为 ir-version、obligation-kind、profile、semantic-feature。绑定精确组件版本及规则，不把其他错误猜成未支持。 |
| `component-error` | model 的 `model-decode`；replay 的 `replay-error` | 只表达具名组件的运行失败；必须有受信来源事实及运行信任，不能以 checker 未复现异常证明错误未发生，也不能凭自报通过。 |

[组件策略 schema](evidence-v0.2-machine-contract/independent-check-v0.2/schemas/component-policy.schema.json)绑定生产侧阶段及完整限额集合。model 首批为 candidate-bytes、decode-steps、integer-digits、text-bytes、value-cells、world-bytes；replay 首批为既有 ReplayResource 的十三项。单位与排序固定于 schema。缺项、多项、阶段或 limit 错配拒绝。未覆盖的组件错误或计数维度保留未支持，不能强制映射为已登记原因。

这里不伪造当前组件没有暴露的消耗计数。独立实现须核对生产策略的来源和因果事实；自己的预算只决定自身是否完成核验，不替代生产预算。若不能独立重现生产计数语义，须保留来源信任和明确不足，不能把自身耗尽写成原尝试耗尽。

diagnostic 为 `{kind: absent}` 或 `{kind: artifact, ref}`。附属原件仍受 manifest 字节限制和摘要核对，但文本不参与 code / cause 判定。它不得包含路径、凭据或真实输入。没有附件不阻断已齐备的结构化事实；声明了附件却缺少字节按缺件处理。Debug 文本既不被解析为事实，也不要求跨语言一致。

生产适配的后续验收须覆盖：错误枚举到登记原因的映射、模型阶段没有 world、重放阶段保留已取得 world、component policy 的真实采集、输入定位与来源绑定。C1–C6 首批仅提供结构及绑定向量；R1–R6 已接入下述 Rust 映射，但不修改原错误语义或把旧中止升级为新支持。

## R1–R6 · 本仓 Rust 适配（2026-11-14）

所有者确认本仓 Rust 适配、复审、相关验证及本地 `dev` 提交。

| 决定 | 实施边界 |
| --- | --- |
| R1 版本 | `readback_v02_with_backend` 保留 backend / batch / Debug interruption `0.1`；`readback_v02_with_backend_v02` 显式选择新登记及 batch / interruption `0.2`，复用原语义检查。输入版本串不选择受信契约，无混搭、降级或 Debug 转换。 |
| R2 来源 | 共用外部 batch raw pin、完整后端清单、数值顺序、invocation、请求、生产策略及父项核对；仅 simulation。无后端继续调用 `readback_v02`，额外提供 batch 拒绝，S1 拒绝输入无需合法 IR / P2。 |
| R3 中止 | `ReplayInterruptionV02::from_model_error` / `from_replay_error` 从类型化错误和调用输入生成中止及组件策略两份规范制品；调用方仍须将它们接入 provenance / execution / batch。序列化不是来源认证。 |
| R4 预算 | model 策略从绑定 request 的实际预算提取六项；replay 策略从生产 ReplayLimits 提取十三项，并与 execution 限额重建结果逐字比较。其余既有限额仍检查；零为零预算。consumer cap 不足返回本次 `ReviewError::Limit`，不能改写生产原因。 |
| R5 输入 | model 中止只有四项原输入，不生成 candidate / world；replay 中止保留六项输入，并重建 candidate / world。原因中的错误制品绑定到实际 response 或 world。diagnostic 可 absent，若引用则须有正确格式及摘要原件；文本不参与判定。 |
| R6 结果 | 保留 D1–D5 的历史、冲突及全部运行信任；返回本仓 Readback / policy，不生成独立四态回执，不改变旧 runtime consumer。 |

映射的明确上限：model 支持 Decode 阶段已登记六资源、`BindingMismatch` 与 `InvalidInput` / `LiteralClassConflict`；replay 支持十三资源、`WorldFormat` / `NonCanonicalWorld` 和四类 Unsupported 枚举。model 其余阶段／资源、replay 无法定位输入的 `BindingMismatch` / `Json`、嵌套 Model、未知义务、非规范 observation 及 Internal 等保留原错误，返回 `UnsupportedModelInterruption` / `UnsupportedReplayInterruption`。`component-error` 在协议中仍可表示，但本入口缺少独立受信运行事实，不生成或接受该支持；没有通用 fallback。

本仓读回重新调用同一 Rust 解码／重放组件，再比较结构化事实、原生产策略、引用及终态。这是生产侧一致性复核，不是独立 checker。模型无效、world 预算耗尽及 replay world 预算耗尽已有合成输入上的实际 Rust 调用；其他已登记错误类别的映射测试不等于每条路径已端到端发生。原容量和 solver 的 128 MiB / 6 s 不变。

离线 `wrap_packet(..., native_backend=True)` 显式接收原生新包；默认路径仍只重封装没有中止的旧包。新增三包的指纹固定于 [backend-structured-fingerprints.json](evidence-v0.2-machine-contract/backend-structured-fingerprints.json)，生成入口为 Rust `backend::tests::structured` 中的具名合成测试。Python 对照重放来源与 execution 的终态，并在原件缺失时仍核对已知 descriptor 的版本。输入错误按阶段指向实际 response 或 world，策略对回生产 request 或 execution。错误因果与生产计数由本仓 Rust 复现。正常测试只读这些指纹；变更输入时先审阅测试输出、结构与语义，再更新该独立基线。旧四包 Evidence、batch / 交换指纹及旧登记不变。

详细实施、失败记录与实际验证见[本仓 Rust 适配记录](../records/2026-11-14-evidence-structured-backend.md)。公共格式接受、独立 Go 验收和完整 M1 仍未完成。

## C4 · 历史、信任与独立结果

D1–D5 的聚合继续适用：保留每次 solve / replay 及其 host-runtime 信任；完成支持不被后次 unknown 覆盖；多个相容完成取最后一个；同目标 unsat 与有效反例冲突拒绝；全未决取最后求解链原因并引用全部匹配终态。合法 verification 的生产结论按 violated、inconclusive、satisfied 重算，缺全集不能装配。

result `0.2` 在原闭合成员之外必需 `scope: simulation`，新 check ID 使用 v0.2 域。每项 kind 的闭合 codes 见机器登记；新增 source-binding 等来源诊断，保留旧 code 含义。`verification-checked` 只表示该检查类别完成，不能独自证明逐义务覆盖。

聚合顺序仍为 rejected → incomplete → accepted-with-trust → accepted。带 refs 的结果列出该次选定 outcome 的全部 check ID，排序且非空。缺件、资源未完成、未支持规则或不允许的信任必须有相应 incomplete check；拒绝优先但不足事实仍保留。只有 rejected 允许无法形成受支持规范文档的 request / Evidence 使用文档域 ID unavailable；已有 raw 字节仍绑定。合法原件不得借 unavailable 隐藏身份，格式不合法原件也不得被强行赋予规范文档 ID。check 引用在所有四态中均须解析到实际 check，不允许悬空或自引用。

接受前须完成所有必需检查类别及全部义务支持核对，来源 identity check 在 backend-batch 分支引用 batch 与 backend 原件，在 no-backend 分支引用经核对确无后端执行的 Evidence；所有 check refs 都须在对应命名空间解析。`remaining_trust` 必须来自该 Evidence，逐条说明 scope 与剩余原因，不得凭类别许可消除信任。本候选尚未登记 trust 消除规则，接受时 remaining_trust 必须与 Evidence trust 全集一致；将来要消除依赖仍须另行登记独立支持与验收。attestation 的 backend / generator / host 依赖按原边界保留；certificate profile 集合为空。certificate-required 或任一未允许的剩余信任产生 incomplete，源 Evidence 不改写。

`accepted-with-trust` 不等于独立 proof。accepted 接受的是 Evidence 对自身结论的忠实表达，程序可能是 violated。simulation 的任何接受都不能当作实际 solver、真实来源、产品制品或 P6 接受。checker 未形成规范结果即崩溃或被外层终止时，只保留运行失败记录。

## C5–C6 · 交接包与验收分层

| 批次 | 本批材料／验收要求 | 尚未完成的边界 |
| --- | --- | --- |
| 本仓字节 | 五份 schema、新 backend 登记、最小完整 input-only 及 S1 结构拒绝合成 bundle、四态协议形状、六份中止记录、两个组件策略及字节负例。 | 协议形状样例不是 checker 执行回执；accepted-with-trust 等独立形状向量不与 input-only 包声明语义关联。 |
| 完整合成交接 | 复用 Rust 的 correct、wrong-add、wrong-drop-zero、pre-false 四包；重新形成 batch / request / manifest，保留 Evidence 原始及文档域身份。固定交换摘要、制品数量及总字节量。 | Rust 原候选读回和 Python 有限语义对照不构成分仓 Go 验收；没有 unsat 独立证明或真实来源认证。 |
| 分仓独立语义 | 精确提交与文件摘要导入规范、schema、黄金输入和期望；独立实现 parser、P1、P2、S1–S3、五类目标、全部历史与四态。测试 helpers 和生产源码不导入实现依赖。 | 本轮不写分仓，不复用旧 checker binary 身份、acceptance 或发布。 |
| 真实 M1／产品运行 | 九项真实后端结果及四项结构支持齐备，完成来源／工具／宿主资格后装配全 13 项与信任项；取得绑定同一新 Evidence 的独立结果。 | 继续按既有授权与实际能力验收。M2 的 group 两义务和 M3 历史迁移不被省略；原容量、128 MiB / 6 s、P6 门禁不变。 |

分仓必测矩阵：

- 缺义务、多余义务、跨目标换绑、删除历史、重复 invocation、错 solve 父项、来源缺失／篡改及三类信任 scope 错绑。
- WF / Pre 失败、五类目标的正反例与故障归因；保留“另一义务失败而声明目标成立”，包括 wrong-drop-zero 的 guarantee 失败但 row-coverage 成立。
- S1 精确结构拒绝；S2 的完整 P1 / P2 前提；S3 的值、控制、求值三根与缺口，不能因后端允许 attestation 免除这些重演。
- 四态、冲突优先级、未支持 certificate、消费政策不满足、缺件与错件并存；旧结果移植及旧域误用拒绝。
- parser／条目／世界／整数／语义步骤边界、确定性诊断和资源终止；原件与全 DAG 重算后仍须抵达预期拒绝位置。
- M1 完整新材料、M2 group 覆盖与守恒区分、M3 旧 timeout / failed / role。先验收部分边界不宣称完整迁移完成。

合成导出的 `bundle` 不包含 expected-result 文件；分仓真正运行后自行产生结果。四态协议形状单独存放，禁止作为实际回执导入。交接清单必须另记录分仓精确提交、构建、工具链、平台及实际结果；当前均待执行。

## 离线复现与停止线

```sh
python3 -I -B scripts/generate-evidence-exchange-review.py --check
python3 -I -B scripts/test-evidence-exchange-review.py
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir evidence_review:: --lib --locked --offline
./scripts/check-repo.sh
```

正常检查只读固定指纹。生成工具使用标准库和现有本仓审阅 helpers；这些复用仅用于本仓生成／检查材料，不允许独立 checker 链接或复制实现。JSON Schema 不代替跨字段、身份、语义或来源检查；本批 Python 工具不是生产 resolver，没有操作系统隔离或一般恶意输入安全声明。

需要重建完整交接目录时，选一个新的、已忽略 `.tmp` 子目录：

```sh
AXIOM_EXCHANGE_REVIEW_EXPORT="$PWD/.tmp/evidence-exchange-review-<new-batch>" \
  cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir \
  five_target_kinds_and_counterexample_attribution_match_independent_finite_semantics \
  --lib --locked --offline -- --nocapture
```

此模式显式重生成合成交换包，不覆盖已存在的题目目录；仍先核对原 Evidence 指纹及有限语义。新摘要须审阅后才用生成器 `--write --packet-dir <该目录>` 更新候选指纹；然后回到正常只读检查。fixture 的 artifact / bundle 字节预算由实际导出量形成，不改变 solver 或 launcher 上限，不声称独立 Go 已在该预算内运行。

本批事实、失败及验证结果见[实施记录](../records/2026-11-13-evidence-exchange-review.md)。公开前仍需正式格式审定、产品入口集成、真实来源、分仓独立验收及 ADR 0009 完整迁移，任何一项不得由本地通过代签。
