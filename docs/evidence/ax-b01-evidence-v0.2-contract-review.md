# AX-B01 Evidence v0.2 义务与结果契约审阅

日期为 2026-11-07，基线为 `dev` 的 `86d5511`。状态为待审阅。本文核对 AX-B01 的 IR 派生义务与现有材料，提出公共结果支持的最小接入范围。公开 Evidence v0.2 的格式、支持规则与迁移须另行验收。当前 P6 为 `closed / p6-not-evaluated`。

## 精确义务与现有材料

下表以 [AX-B01 correct 的规范 IR v0.2](../../crates/axiom-ir/tests/fixtures/v0.2/migrated/ax-b01-correct.jcs)和[冻结的 P2 集合](../../contracts/ir-derived-obligations-v0.2/sets/ax-b01-correct.jcs)为准。IR 文档 ID 为 `sha256:90d876b9fdd533944e09f4274ba4aaa313d179454427e60eca81575707054f0b`，集合原始摘要为 `sha256:5edf309363ddb36f219a317e2cb714ba0673669c26f1b376368f22c9d327356f`。表中的义务 ID 省略统一前缀 `sha256:`。filter、map、guarantee 分别指该 IR 的唯一对应节点或契约。所有路径从对应规范 definition 根起算。

| 义务 | 精确位置 | 义务 ID | 现有材料 | 待审接入与可声明结果 |
| --- | --- | --- | --- | --- |
| `ir-structure` | 完整文档 | `b804c9369a2c23dec3b1459599f8ef81561d47ee8655cb19e002bfc87a70c61c` | P1 严格规范检查、IR 原字节 | `normalize` / `ir-normalizer`，满足结构支持后可为 `checked` |
| `effect-empty` | 整个程序 | `64bd44f0489b89d0912ce46e659f393de494341a5c960cf23f9efb7698308a70` | P3-E 空效果推导 | `prove` / `prover`，待审空效果规则的 `kernel-replay` |
| `field-origin` | output `net_orders.order_id` | `4f97f098d0782f88070ab89ced9749d603fe316f79c826f828b3561ce51711f5` | P3-F 来源与标签 DAG，值来自 `orders.order_id` | `prove` / `prover`，待审字段来源规则的 `kernel-replay` |
| `field-origin` | output `net_orders.net_cents` | `e4b0331b7d9caf004b695af957e6e2751bed2d666515634d7295e4f72847671a` | P3-F 来源与标签 DAG，值依赖 `subtotal_cents` 与 `discount_cents` | `prove` / `prover`，待审字段来源规则的 `kernel-replay` |
| `totality` | filter 节点的定义性 | `b0f12d6e03c05cac501416db5ca46057516deac9424b67e0fc6daebdee7a37b2` | 逐目标查询与重放入口 | 后端目标路径 |
| `totality` | map 节点的定义性 | `1dcc3305a589ba2161b387d07e4425a6e1a7034c69243f1746e1222c96bd16e1` | 逐目标查询与重放入口 | 后端目标路径 |
| `key-cardinality` | filter 节点的键唯一与容量 | `8a608c25a3ced58efe17ffb31da0530567f983433216e35d36e2d59018b89139` | 逐目标查询与重放入口 | 后端目标路径 |
| `key-cardinality` | map 节点的键唯一与容量 | `a00fdcf35d10acef443b7eb69e523c18c58a01eabd51276149a76836b4e73c43` | 逐目标查询与重放入口 | 后端目标路径 |
| `row-coverage` | filter 与直接输入中满足其谓词的行 | `75e9b6af0c3b16aa52e86368827296be09f8cf62a7ce5f591e678537d7fc268a` | 逐目标查询与重放入口 | 后端目标路径 |
| `row-coverage` | map 与其直接输入的键双射 | `c088c2a05d5c0930521fcacf0815478872eba324a619b57402e15e2f36a923f1` | 逐目标查询与重放入口 | 后端目标路径 |
| `numeric-range` | map 的 `["fields","0","expression"]`，生成净额的减法 | `34666d2deebb7e41afbddac07401ca9a5fdbdaca16e90269bec3e161f607a782` | 逐目标查询与重放入口 | 后端目标路径 |
| `numeric-range` | guarantee 的 `["expression","body","then","some","right"]`，比较右侧的减法 | `4b054af797c1b1120822d43785d28047b9983cbde862d3cbcea13580ac7ffaba` | 逐目标查询与重放入口 | 后端目标路径 |
| `contract-guarantee` | 唯一 guarantee，约束结算订单的输出存在性和净额及未结算订单的输出缺失 | `b4ad73cf180f6a36803686d8b04f1449131f8650314d0d8fb23f0362cb94c759` | 逐目标查询与重放入口 | 后端目标路径 |

两个 wrong 候选各有 13 项和相同的 kind 计数，必须使用各自 IR 和全集绑定。AX-B01 没有 group 节点，group 的兼容验收另用 AX-B03。13 项只覆盖 `ir-derived`，完整 verification 还要纳入实际依赖的 `trust-boundary`，benchmark 再纳入具体 input、host、output conformance。P5 的受保护回执和夹具检查器身份可供具体检查契约审阅。 [两份 wrong 的集合与摘要](../../contracts/ir-derived-obligations-v0.2/cases.tsv) · [P2 完整集合规则](ir-derived-obligations-v0.2.md#完整-evidence-后续必须补齐的内容) · [P5 接受范围](../records/2026-11-07-ax-b01-p5-darwin-release-review.md#本机生产接受)

### 后端目标路径

三份候选各九个目标已有生产编码器的 v0.5 / query0.3 测量及 P4-A v0.2 请求规划。测量表以 IR raw、全集 raw 和目标 ID 关联精确查询摘要及符号映射。两个目标即使查询字节相同，也须分别核对绑定。P4-B 按完整 WF、适用 Pre 和精确目标重放有界 world。当前有编码、请求、有限语义对照及合成重放材料，公共结果支持仍待审阅，真实 solver 尚未校准。 [生产测量](../query/compact-query-production-validation/ax-measurements.tsv) · [P4-A 配对](../query/p4-request-response-model-v0.2.md) · [P4-B 规则](../query/p4-concrete-target-replay-v0.1.md)

| 可声明结果 | 所需执行和材料 |
| --- | --- |
| `proved` | `prove` / `prover` 绑定精确目标、实际查询、请求、工具、预算、响应和受控执行来源。若后续批准 `backend-attestation`，只有真实且绑定的 `unsat` 和明确的 proof-backend trust 才能支撑生产声明。要求证书时还须绑定受支持证书及真实 `check-certificate` / `certificate-checker` 执行。现有校准入口仅记录后端观察。 |
| `failed` | `replay-counterexample` / `counterexample-replayer` 实际完成精确重放，保留 IR、全集、目标、world、适用 Pre、预算、规则、观察及见证。若来自 `sat`，还须保留请求、响应、模型与 world 的解码链。直接提供 world 的路径只声明实际有限重放来源。 |
| `unknown` | 已发生且绑定该目标的尝试，连同可核对的原因和非空 attempt 引用。支持规则须区分后端未知、超时、资源不足、操作错误和无法获得精确可重放见证。未启动时记录缺项。 |

所有九项的 expectation 均为 `prove`。`checked` 和 `trusted` 对这些目标均不合法。`target-not-violated` 只覆盖当前 world。wrong-drop-zero 可违反业务 guarantee，同时满足相对于实际谓词的内建 row-coverage，反例必须归到被重放的目标。 [有限归因材料](../records/2026-10-17-query-compaction-validation.md) · [校准停止线](../adr/0028-bounded-solver-calibration-entry.md) · [五态与支持](axiom-evidence-v0.md#五种状态)

## 四个结构目标的接入决定

**S1 · ir-structure。** 生产已有 `check_canonical_document`。它验证结构、类型、绑定和原始规范字节，产出不可变 CanonicalDocument。对合法 subject，建议在 v0.2 明确允许 `normalize` / `ir-normalizer` 以严格模式支撑 `checked`，执行绑定原始输入、精确语义、规则 / 工具、预算、规范产物及文档域 ID。独立路径重读实际字节并重算身份。旧 v0.1 的 `checked` 支持列表未列 `normalize`，锁定合成生成器用 `check-fixture` 记录这项检查。建议只在新版本声明新的支持关系。对真正拒绝的候选，另行固定 `rejected-ir` 分支及 `structure-path` 的实际复核规则，复现确定性拒绝后才能给 `failed`。资源或工具故障只有实际 attempt 才可支撑 `unknown`。严格模式必须检查原始输入并拒绝非规范字节，即使 normalize 能从该输入生成另一份合法制品。 [P1 入口](../../crates/axiom-ir/src/document.rs) · [旧合成执行生成](../../scripts/checker_bundle_contracts/evidence.py) · [v0.1 subject 与结果](axiom-evidence-v0.md)

**S2 · effect-empty。** `derive_empty_effects` 与 `check_empty_effects` 已支持 IR、P2 全集、目标、语义及生成器身份绑定。correct 记录有 54 步，最终程序根为索引 53，两个 wrong 各有同目标类型的记录。建议 `prove` / `prover` 在完成实际推导后关联记录原字节、规则身份和预算。待独立规则直接从 IR 重演程序根、全部必需前提和空效果声明，并明确 P1 完整类型 / 结构等信任前提，才接入 `proved` 的 `kernel-replay`。纯核心空效果的范围止于程序语义，运行器、系统调用与工具进程的效果分别列入各自边界。 [推导规则](../query/core-empty-effects-v0.1.md) · [正确候选的内部记录](../../contracts/core-empty-effects-v0.1/records/ax-b01-correct.jcs)

**S3 · field-origin。** 两份 correct 记录各有 38 个导出步骤，保留各自 `value` 根和 `control`、`evaluation` 根，`gaps=[]`。两字段的值来源不同，行选择都经由对 `orders.state` 的筛选。两个 wrong 候选的对应记录也无缺口。建议将 `prove` / `prover` 的结构重演作为候选路线。先明确原 P2 目标的可判定充分条件，再要求独立实现按实际输出接口、字段、三根、带角色的依赖边和标签重建闭包。空缺口只能作为该充分条件的候选材料。它无法区分加法与减法的业务错误，也无法证明动态无故障或双世界非干扰。发现 gap 时保留静态判断，`failed` 仍须可重放的精确见证。 [字段来源规则](../query/core-field-origin-v0.1.md) · [order_id 记录](../../contracts/core-field-origin-v0.1/records/ax-b01-correct-000.jcs) · [net_cents 记录](../../contracts/core-field-origin-v0.1/records/ax-b01-correct-001.jcs) · [三候选记录索引](../../contracts/core-field-origin-v0.1/cases.tsv)

S1–S3 都需要明示 execution 的输入、输出、规则、实际工具身份和预算。内部生成器字段只标记所提供的源码摘要。生产 strict 重建与 Python 有限核对属于现有组件材料。四项目标当前均无公共 v0.2 结果可填。空效果和字段来源三项的 `failed` 需要各自可复核的见证，现有 P4-B 不支持这些目标。实际证明尝试若未得出结论，只能在有目标绑定和可核对原因时给 `unknown`。若证明接入要求修改已接受的 P2 目标或身份，按既有规则另作版本决定。 [P2 身份约束](ir-derived-obligations-v0.2.md#版本与身份)

## 角色与迁移边界

延用 P2 后续要求的闭合映射。工具可显式声明多个角色，每个 execution 按 kind 逐项校验。生产 Evidence 的工具另须具备 `evidence-producer`，独立检查使用单独的 checker 身份及结果。 [既有闭合映射](ir-derived-obligations-v0.2.md#完整-evidence-后续必须补齐的内容) · [独立复核边界](../adr/0008-independent-checker-isolation-and-artifact-exchange.md#独立性与可信计算基)

| execution kind | 必需 tool role | execution kind | 必需 tool role |
| --- | --- | --- | --- |
| `normalize` | `ir-normalizer` | `generate-obligations` | `obligation-generator` |
| `prove` | `prover` | `check-certificate` | `certificate-checker` |
| `check-fixture` | `fixture-checker` | `execute-host` | `host-executor` |
| `compare-output` | `output-comparator` | `replay-counterexample` | `counterexample-replayer` |

1. 先严格读取 v0.1 源字节及具名源 profile，核对规范身份、完整义务、角色、状态支持和实际引用。保留 v0.1 规范、域及锁定材料原字节。group 的旧受限实现 profile 只按其精确身份识别。
2. 显式迁移 IR。以目标 IR 的规范路径、语义和完整 profile 重建全部 definitions 与 ID。公共 Evidence 用 `evidence_version: "0.2"`、义务 profile `version: "0.2"`。每个 group 节点分别生成 `row-coverage` 与 `group-conservation`。IR 派生 ID 遵循已冻结的 v0.2 域规则。
3. 从新目标实际执行或独立复核重建工具 / execution 绑定、trust、结果、结论与 Evidence 摘要，再生成绑定新摘要的独立结果。相同工具或数据原字节可以沿用原始制品摘要。旧 `proved`、`checked`、`trusted` 不进入新结果，历史 `failed`、`unknown` 与 attempts 保留在源记录，目标状态由实际新材料确定。
4. 缺少必要执行、规则支持或信任材料时，迁移返回未完成及精确缺项。最小完整演练应覆盖 AX-B01 精确目标重绑以及 AX-B03 的两项 group 义务，留存源 / 目标摘要与新独立结果。在规范、迁移器、正负例和完整演练验收前，v0.1 仍是唯一可解析的公共版本。 [ADR 0009](../adr/0009-axiom-evidence-v0-drift-and-migration.md) · [P2 兼容预览](p2-profile-review/compatibility.json)

## 拒绝用例与审阅出口

以下为待实现的公共契约验收用例。对语义、状态或角色负例，应重算受影响的外层身份与引用，让输入抵达目标检查。保留独立的原始摘要负例。

| 用例 | 变异或对照 | 预期 |
| --- | --- | --- |
| 旧新混配 | 改版本或域后复用旧 IR、旧目标 ID、重排前路径、旧结果或旧独立结果。源文档缺失或旧角色错配时尝试由迁移器修补 | 严格拒绝对应的源或目标绑定。仅缺目标新执行时报告迁移未完成及缺项 |
| 全集与 group | AX-B01 删一项或用另一候选同 kind 目标替换。AX-B03 从同时含两项的正例分别删除或合并 group 覆盖与守恒 | 独立重建全集并拒绝。含零值组的缺组例可守恒但覆盖失败，键正确而聚合值错的例只违反守恒 |
| 角色错配 | 用 `fixture-checker` 执行 `replay-counterexample`，或以 `obligation-generator` 执行 `prove` | 拒绝状态支持。多角色正例须显式包含该 execution 所需的角色 |
| 结构与原字节 | 在可规范化的 IR 后加空白，拿规范化后的摘要支撑原输入的 `checked`。用 P5 回执或仅有 P2 集合替代结构检查。把预算耗尽包装成 `structure_rejected` | 拒绝 `checked` 或确定性结构失败声明。结构拒绝分支须可复核原始候选和实际诊断 |
| 空效果 | 删除必需前提、替换根或使用另一 IR 的合法推导，重算记录摘要后声明 `proved` | 重演失败或目标绑定不符，拒绝证明支持 |
| 字段来源 | 交换两个字段的记录，删掉选择 / 求值边或保留 gap 节点却清空 gap 列表。仅凭无 gap 推导业务净额正确，或凭 gap 声明泄漏 `failed` | 拒绝绑定、闭包或状态支持；需独立核对被声明的精确性质 |
| 后端与归因 | 将相同 SMT 字节的另一目标响应换入。用 `sat` 模型、Pre 不成立的 world 或只违反 guarantee 的 world 支撑 filter coverage 的 `failed` | 拒绝错误目标绑定或无有效精确重放的 `failed` |
| 结论与门控 | 无 attempt 却填 `unknown`，用 `trusted` 或 `checked` 完成 `prove`，把裸 `unsat` 或 P5 `accepted` 用作全义务满足 / 开 P6 的依据 | 拒绝无支持结果或错误结论。独立检查按完整 profile 重算，真实但不充分的尝试按其实际级别保留 |

S1 的三条支持边界、S2 的独立重演及 P1 / P2 前提、S3 的首批范围及充分条件均已获所有者批准。最小公共支持、独立检查矩阵和 ADR 0009 演练方案进入汇总审阅。运行线继续受既有 P4、宿主和工具门槛约束。 [S1 决定](ir-structure-result-v0.2-review.md#审阅出口) · [S2 决定](effect-empty-result-v0.2-review.md#审阅出口) · [S3 决定](field-origin-result-v0.2-review.md#审阅出口) · [汇总审阅](evidence-v0.2-minimal-support-review.md)
