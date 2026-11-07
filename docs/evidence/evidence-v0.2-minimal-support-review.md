# Evidence v0.2 最小公共结果支持与迁移演练审阅

日期为 2026-11-07，基线为 `dev` 的 `90d2593`。状态为待审阅。本文汇总已批准的 S1–S3 结果边界，提出公共契约、独立 checker 和迁移演练的验收矩阵。P6 为 `closed / p6-not-evaluated`。 [AX-B01 义务与材料](ax-b01-evidence-v0.2-contract-review.md) · [ADR 0009](../adr/0009-axiom-evidence-v0-drift-and-migration.md)

## 公共结果支持

拟议入口显式选择 `evidence_version: "0.2"`、义务 profile `version: "0.2"` 和精确 IR / 语义版本。沿用闭合 JCS、规范十进制字符串、排序和唯一性要求。义务 ID 沿已冻结的 v0.2 规则，按 definition 计算。建议 tool、execution、trust、uncovered 和 Evidence document 各用 `axiom-evidence-v0.2:<kind>` 重新计算身份，制品仍以原始字节 SHA-256 寻址。具体成员、角色引用编码、版本域和独立请求 / 结果版本随公共格式审定。v0.1 的读取器继续只按其精确支持集合工作。 [旧格式与域](axiom-evidence-v0.md#json规范字节与内容标识) · [P2 义务身份](ir-derived-obligations-v0.2.md#版本与身份)

| 义务 / 条件 | 允许的生产结果 | 必需的执行与支持 |
| --- | --- | --- |
| S1 合法 `ir-structure / check` | `checked` | 严格 `normalize` / `ir-normalizer` 完成并通过。绑定原始 IR、精确规则和预算、实际工具、规范产物和文档域 ID。原始输入与规范产物逐字节一致。 |
| S1 三类确定性拒绝 | `failed`，聚合为 `structure_rejected` | 严格 `normalize` 完成并记录拒绝。独立复现非规范字节、无效 UTF-8 或未知顶层成员之一，`structure-path` 绑定原候选及定位。拒绝分支按候选 raw 摘要单独重建结构义务，合法 IR 的文档域身份与 P2 全集不适用。 |
| S2 `effect-empty / prove / program` | `proved`，支持为 `kernel-replay` | 实际完成的 `prove` / `prover` 绑定规则、预算、同一 IR、P2 全集、目标与内部推导原件。独立路径先确立 P1、重建 P2，再重演 `program.empty` 的全部有序前提。 |
| S3 `field-origin / prove` | `proved`，支持为 `kernel-replay` | 实际完成的 `prove` / `prover` 绑定精确输出接口及字段、同一 IR、P2 全集、规则、预算和内部记录。首批限 `input/filter/map` 图的公开顶层标量。独立重建三根闭包，确认值和行控制满足公开条件、闭包无 gap，保留全部求值前提。 |
| 已确立 subject 上的真实中止或未能证明 | `unknown` | 保留真实且与目标、原因相符的非空 attempt 引用。gap 或控制条件不满足可说明实际证明尝试未完成，须保留原诊断。未确立 subject 时停在 Evidence 装配前，未调度时记录缺项。 |
| 单独的 `trust-boundary` 义务 | `trusted` | 绑定具体 trust 项、实际适用范围和验证策略。核心 `check` 与 `prove` 各按其期望状态判断。 |

执行 `completed` 表示该次执行获得确定结果，S1 通过与拒绝由绑定的判定区分。S2 和 S3 的公共失败重放未纳入首批支持。类型不成立、推导损坏或静态 gap 都不能作为这两项的 `failed`。已发生的尝试在重试后仍保留，新的结果关联新的实际执行。 [S1 决定](ir-structure-result-v0.2-review.md#审阅出口) · [S2 决定](effect-empty-result-v0.2-review.md#审阅出口) · [S3 决定](field-origin-result-v0.2-review.md#审阅出口)

| execution kind | 必需 tool role | execution kind | 必需 tool role |
| --- | --- | --- | --- |
| `normalize` | `ir-normalizer` | `generate-obligations` | `obligation-generator` |
| `prove` | `prover` | `check-certificate` | `certificate-checker` |
| `check-fixture` | `fixture-checker` | `execute-host` | `host-executor` |
| `compare-output` | `output-comparator` | `replay-counterexample` | `counterexample-replayer` |

角色表是闭合集合。工具可显式多角色，producer 另须具备 `evidence-producer`。角色匹配之后仍须验证该执行能支撑精确目标与结果。AX-B01 的 13 项 IR 派生义务中，S1–S3 覆盖四项。其余九项仍需要各自结果支持及实际执行。完整 verification 另含实际依赖的信任义务，benchmark 再包含具体输入、宿主和输出检查。缺必要执行时保留迁移缺项，禁止发布部分全集。P5 夹具接受和本批支持均不开放 P6。 [完整 profile 要求](ir-derived-obligations-v0.2.md#完整-evidence-后续必须补齐的内容)

## 独立检查矩阵

| 检查 | 独立动作 | 通过与阻断边界 |
| --- | --- | --- |
| 解析和身份 | 严格解析版本、profile、闭合成员、排序和规范字节。重算引用、长度、制品 raw 摘要、条目及文档域 ID。 | 发现确定矛盾即拒绝。已识别且必要的制品暂不可得时记 `incomplete`。 |
| subject 和全集 | checker 自行严格解析 IR、重算 P1 结构、类型、绑定和身份，再生成完整义务集合。拒绝分支从原始候选重建结构义务。 | 拒绝版本配对、缺项、多余、重复或错目标。对 S2 / S3 缺独立 P1 或 P2 时保留 `incomplete`。 |
| 状态与执行 | 核对角色、规则、工具身份、实际执行与预算、假设和输出引用，逐项判断支持是否适用于对应义务。 | 错配拒绝。执行缺失不能伪装为 `unknown`。已绑定真实尝试的诊断须与声明原因一致。 |
| S1 具体检查 | 原字节严格通过时重算规范字节与身份。拒绝时复现绑定预算下的具体规则、原因及原件定位。 | 匹配才完成该项核验。生产中止或 checker 自身不足预算都不能充当确定性拒绝。 |
| S2 证明支持 | 从实际 IR 重建空声明、全部节点 / 输出 / 契约的有序前提和最终程序根，比较推导原件。 | 重演全程序并匹配才为 `passed`。只核对效果记录而未独立确立 P1 / P2 为 `incomplete`。 |
| S3 证明支持 | 重建每字段独立的值、控制和求值三根闭包、角色边及 gap，核对首批形状和充分条件。 | 记录一致后还要检查控制标签与缺口条件。成立才为 `passed`。正确记录在支持范围外时保留不足；把它声明为已满足该规则则拒绝。 |
| 结论与独立结果 | 按完整 profile 重算结论，生成绑定新 Evidence 原始摘要和文档域 ID 的独立结果，记录 checker 身份、TCB、缺项和剩余信任。 | 确定拒绝优先于并存的缺项。必需核验未完成为 `incomplete`。只有核验完成、政策允许全部剩余信任时才可接受，分别记录 `accepted` 或 `accepted-with-trust`。 |

独立实现按 ADR 0008 使用自己的规则、解析器和义务重建。生产严格检查、内部 Python 核对和独立公开结果分别留证。checker 在形成规范结果前崩溃或被外层终止时，保留外层执行故障记录。后端 attestation 政策不解除 S2 / S3 的独立前提。独立接受可以确认如实报告的结构拒绝，生产结论仍为 `structure_rejected`。 [独立核验与聚合](../adr/0008-independent-checker-isolation-and-artifact-exchange.md#独立结果协议)

## ADR 0009 迁移演练

### 输入与出口

| 轨道 | 固定源及目标 | 验收出口 |
| --- | --- | --- |
| M1 完整 verification 演练 | 提议从 `CHK-PROOF-02` 的 v0.1 verification bundle 开始。源 Evidence raw 为 `sha256:b519aef5b208d8ef93d7559a000c56ab78eb59f99dca95ae6a7f58264c964e4d`，源策略为 `attestation-allowed`。subject 是 AX-B01 correct。目标为同任务的 v0.2 verification，重建全部 13 项核心义务及实际信任项。 | 源按原策略严格验收，目标用新材料形成完整规范 Evidence，并取得绑定新摘要的独立结果。四项支持闭合只代表完成 S1–S3；九项缺真实可用结果时迁移报告未完成。 [源请求](../../contracts/keyed-finite-table-checker-bundles-v0.1/s/chk-proof-02/bundle/request.jcs) · [目标 P2](../../contracts/ir-derived-obligations-v0.2/sets/ax-b01-correct.jcs) |
| M2 group 完整性与归因 | `AX-B03-CORRECT` 的锁定 v0.1 benchmark bundle 与目标 AX-B03 correct IR / P2。源 Evidence raw 为 `sha256:0af2358d01a5a710c7d94721d78b0635e0038df8a4442b0223a88e9673ee9900`。保留具名旧实现 profile 的 group 覆盖行为。 | 目标全集含 14 项核心义务，group 的 `row-coverage` 和 `group-conservation` 分别重建、分别删改测试。用已有有限区分例验收归因。该轨道先验收义务与拒绝边界，完整 benchmark 装配须有相应真实材料。 [旧 bundle](../../contracts/keyed-finite-table-checker-bundles-v0.1/s/ax-b03-correct/bundle/manifest.jcs) · [目标 P2](../../contracts/ir-derived-obligations-v0.2/sets/ax-b03-correct.jcs) · [group 区分例](p2-profile-review/group-separation.json) |
| M3 历史状态与角色 | 以 `AX-B01-BACKEND-TIMEOUT` 与 `AX-B01-WRONG-ADD` 检查历史 `unknown`、`failed` 和 replay role。 | 源历史逐项留存，目标结果只由新材料决定。旧结果、attempt 和反例引用被移植时拒绝。 [超时源](../../contracts/keyed-finite-table-checker-bundles-v0.1/s/ax-b01-backend-timeout/bundle/manifest.jcs) · [错误候选源](../../contracts/keyed-finite-table-checker-bundles-v0.1/s/ax-b01-wrong-add/bundle/manifest.jcs) |

三个轨道的旧 bundle 都是锁定的指定态材料。须先通过源契约的严格检查，再用作演练输入。旧指定结果不充当观察。兼容预览中 AX-B01 / AX-B03 correct 的核心清单取自各自 backend-timeout bundle。每个 timeout bundle 与同题 correct bundle 使用同一主体 IR，Evidence 与 profile 身份仍须按选定输入核对。M1 保持源 verification profile，按目标版本重建完整义务。 [旧 bundle 范围](../../contracts/keyed-finite-table-checker-bundles-v0.1/README.md) · [兼容预览](p2-profile-review/compatibility.json)

### 执行顺序与留存

1. 冻结源 request、manifest、Evidence 原字节、具名 profile 和 artifact 闭包。严格校验源格式、摘要、义务、角色、状态支持、信任和实际适用策略。源非法时拒绝，必要来源缺失时停止并列缺项。保存严格源检查的实际结果。
2. 显式调用具名 IR 迁移规则。保存源与目标 IR raw / 文档域摘要、语义绑定和迁移记录。按新规范路径独立重建完整目标 definitions 和 ID，包括 group 的两项独立义务、实际信任和所选 profile 的额外义务。
3. 使用实际新执行重建 tools、executions、结果、trust 和 conclusion。相同原始制品可保留原始内容摘要，条目身份和引用按目标规则重算。旧 `proved`、`checked`、`trusted` 禁止移植，历史 `unknown`、`failed` 和 attempts 留在源历史。缺新材料时保留明确的未完成迁移记录。
4. 完整目标形成后做 strict 读回，以新 request 和只读 bundle 运行独立 checker。迁移记录分别留存源 / 目标 Evidence raw 和文档域摘要、规则与执行身份、义务定义对照、新 request / manifest 与独立结果摘要，并记录实际信任和缺项。指定态演练与真实观察分开留存。

M2 的两个 group 目标须绑定同一目标节点，却有不同 ID。以直接 source `(a,2),(b,0)` 对照，遗漏 `b` 可守恒但覆盖失败，键齐全而聚合值错可覆盖通过但守恒失败。该对照用于验收目标区分，完整反例仍须采用合法带类型的 world 和精确重放。 [目标区分规则](ir-derived-obligations-v0.2.md#group-覆盖守恒与归因区分)

## 拒绝用例

对语义、状态或角色变异重算受影响的条目和外层引用，保证样本能到达目标检查。摘要负例保留错配。以下为待执行的公共验收矩阵。

| 用例 | 变异与预期 |
| --- | --- |
| M-VERSION | 旧 reader 读取 v0.2。或只改版本号、混用旧域、新旧 IR / profile、复制旧义务 ID 或排序前的规范路径。按版本或目标身份拒绝。 |
| M-RESULT | 把源 `proved`、`checked`、`trusted` 重挂到新的目标。另测挪用旧失败见证、超时 attempt 或独立结果。拒绝支持和新文档绑定。 |
| M-ROLE | 在源与目标分别以只有 `fixture-checker` 的工具提交 `replay-counterexample`，以只有 `evidence-producer` 的工具提交 `prove`。按角色拒绝，角色错配预期抵达 `invalid-state-support`。 |
| M-GROUP | 从具有两项目标的正例分别删除覆盖、守恒，或把其中一项替换成另一项。拒绝全集不符。已有 P2 负例作为独立期望。 [P2 负例索引](../../contracts/ir-derived-obligations-v0.2/negative.tsv) |
| M-STRUCTURE | 用修复后的 IR 替换 S1 原件。另测错误首差偏移、证据仅含 P5 回执、预算耗尽冒充结构拒绝。拒绝具体支持。 |
| M-EFFECT | S2 用空声明替换程序根、删 guarantee 前提、绑定另一候选或省略独立 P1 / P2。篡改拒绝，真实核验前提缺失为不完整。 |
| M-ORIGIN | S3 跨字段重绑、删除控制 / 求值边、清空 gap 或用公开值标签遮掉敏感行控制。拒绝重演不一致或不成立的支持。 |
| M-MISSING | 缺少目标真实执行时迁移报告未完成。另测 checker 缺制品与同摘要引用下的错误原字节，分别为不完整和身份拒绝。 |
| M-CONCLUSION | 用四项 S1–S3 成功填满 13 项或用 P5 接受开启 P6。另测删除真实中止历史、用无 attempt 的 `unknown` 填缺项。拒绝全集、支持或聚合错误。 |

本轮只核对旧源 Evidence 摘要和 profile、目标 P2 身份及材料链接，运行现有 IR 迁移和义务测试。公共 Evidence v0.2 规范、严格迁移器、独立支持和实际完整演练仍是后续验收项。旧公共读取支持以 ADR 0009 为准。

接续草案已将 verification 的字节、身份、执行、制品和结果绑定写入机器登记并配套离线向量，待审定后接入生产路径。 [机器契约草案](evidence-v0.2-machine-contract/README.md)

M1 已严格核验主仓源包并完成目标 IR、P2 全集和九份离线请求重建。演练保留未完成，阻断项按实际执行和独立验收分别记录。 [M1 迁移准备记录](../records/2026-11-07-ax-b01-evidence-m1-preflight.md)
