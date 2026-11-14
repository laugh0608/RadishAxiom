# Evidence v0.2 S1 结构检查结果支持审阅

日期为 2026-11-07，审阅基线为 `dev` 的 `4c3f6f0`。项目所有者已批准文末三条支持边界。本文细化 AX-B01 的 `ir-structure / check`，供生产记录与独立检查实现评审。外层规范 JSON、完整 profile 和公开读取仍由 Evidence v0.2 单独验收。P6 为 `closed / p6-not-evaluated`。 [AX-B01 契约审阅](ax-b01-evidence-v0.2-contract-review.md)

## 严格调用与材料绑定

S1 提议在 v0.2 的状态支持规则中，允许 `normalize` / `ir-normalizer` 以显式严格模式支撑 `ir-structure`。生产入口以 `check_canonical_document` 为基准。它完成支持范围内的 JSON、IR 结构、类型、引用和内容身份校验，再比较原始输入与重建的规范机器字节。严格成功还须核对返回的 IR 版本及语义快照与预选规则相同。P1 的通用入口可同时读 v0.1 和 v0.2，S1 的选择器因此须单独固定目标版本。 [P1 入口](../../crates/axiom-ir/src/document.rs) · [IR v0.2 规范](../ir/axiom-ir-v0.2.md)

| 绑定 | 复核要求 |
| --- | --- |
| 原始输入 | 绑定实际交给检查的字节、长度和 raw SHA-256。版本及语义由事前选择的 v0.2 严格规则固定。输入中出现旧版本或未知版本时，保留实际版本选择或诊断，不自动迁移。 |
| 规则与预算 | 固定严格模式、目标 IR 版本、语义快照及实际规则制品身份。绑定 `max_input_bytes`、`max_values`、`max_nesting` 三项。成员名计入值数，容器嵌套实际取配置与 P1 上限 128 的较小值。运行器的时限等外层限额另行记录。 |
| 执行与工具 | 引用实际 tool ID 及其精确制品和版本，角色须含 `ir-normalizer`。判定或中止须关联该次执行的输入、规则和预算，能够核对执行来源。角色与可执行文件摘要各自校验。 |
| 判定记录 | 完成的检查产出绑定本次执行材料的结构判定。通过时引用实际规范 IR 制品及文档域 ID。确定性拒绝时记录受支持规则、稳定原因和原输入定位。执行中止时记录可核对的尝试、阶段与原因。外层序列化和具体 tag 由后续契约定义。 |

通过时，原始输入和规范产物须逐字节相同。执行的输入和输出角色可共同指向一个制品描述，清单按原始摘要只登记一次。独立检查分别重算文件 raw SHA-256 与 `SHA-256(UTF8("axiom-ir-v0.2:document") || NUL || canonical bytes)`，按冻结的 P2 `document` subject 重建原义务 ID。AX-B01 correct 的 `ir-structure` ID 为 `sha256:b804c9369a2c23dec3b1459599f8ef81561d47ee8655cb19e002bfc87a70c61c`。 [P2 集合与身份规则](ir-derived-obligations-v0.2.md#版本与身份)

## 三种结果与 subject

| 本次执行 | 拟议结果支持 | subject 与后续处理 |
| --- | --- | --- |
| 严格检查完成并通过 | `checked` 引用已完成的 `normalize`、实际判定、全部输入和输出制品及适用 assumptions。 | 使用合法 `axiom-ir` subject 和原 P2 定义。只完成这项结构义务，完整 profile 仍须重建全集及其余结果。 |
| 严格检查完成并给出可独立复现的确定性拒绝 | `failed` 引用已完成的 `normalize` 和 `structure-path` 见证。建议将这种严格判定明确纳入 v0.2 的有限比较支持。`completed` 表示执行得出确定判定，结构是否通过由判定记录区分。 | 使用 `rejected-ir`，只绑定候选原始摘要。提议结构拒绝分支的唯一核心义务为 `ir-structure / check`，其 subject 以 `{kind: "rejected-ir", artifact: <原始摘要>}` 定位，按 v0.2 obligation 域重算 ID。独立复现拒绝后重算 `structure_rejected`。合法文档的 P2 ID、语义绑定和伪造的规范产物都不能填入拒绝 subject。 |
| 实际尝试中止，或有实际记录表明当前实现不支持该项 | `unknown` 要有非空 attempt 和相符的原因。首批区分 `resource-exhausted`、`timeout`、`unsupported` 与 `operational-error`。若独立核对只能确认记录结构，须继续保留执行来源缺口。 | 当结果可绑定到已经确立的合法 subject 时，保留义务未完成，聚合至少考虑 `inconclusive` 规则。若尝试在能分类原始候选前中止，保留绑定输入的尝试和未完成诊断，停止在 Evidence 装配前。 |

启动前的缺项或未调度只记缺项。已经提交给执行边界且有实际来源记录的启动故障，可以成为中止尝试。工具自报的错误文本不足以认证执行。重试须保留实际发生的前次尝试，按后次实际判定重新装配，不能改写前次状态。独立检查须有可核对的执行历史，才能判断是否遗漏已发生的尝试。S1 的 expectation 保持 `check`。 [v0.1 状态与结论](axiom-evidence-v0.md#五种状态)

### 首批可复现拒绝

首批只提议三种支持，均要求在所绑定规则和预算下到达对应检查。独立实现按规范复核原因与定位。错误内容 ID、类型和其他确定性 IR 拒绝可保留原生产诊断，进入公共 `failed` 支持前须补具体规则和负例。

| 拒绝事实 | 见证定位与重演 |
| --- | --- |
| 可规范化但原始字节非规范 | 对原件完成受支持的规范化，比较完整字节。定位为从零计数的首个不同字节，或较短一方的 EOF。重建出的规范字节只作比较材料。 |
| 无效 UTF-8 | 从原件重算第一个无效 UTF-8 序列的起点。在该例中直接核对原始字节，候选可以完全没有可解析的 JSON。 |
| 顶层未知成员 | 解析受预算约束的原件，按 v0.2 的闭合顶层成员集合核对所指成员，定位从原候选对象根起算。 |

`structure-path` 使用原候选摘要和可解析的字节区间或结构定位，`worlds=[]`、`preconditions=[]`，最小性为 `unreduced`。EOF 可用长度为零的区间，原始字节位置须落在候选长度范围内。失败 witness 和判定记录须指向同一原因与定位。解析器遍历顺序或日志措辞不进入见证身份。预算中止优先保留该次实际诊断，独立路径以更宽预算发现的结构问题需要另一条实际尝试。 [原始字节定位](axiom-evidence-v0.md#trace)

## 独立检查

独立路径首先从实际原字节校验长度、摘要和角色，识别严格规则与目标版本，再用自身的解析、类型、引用和规范化规则重做合法性及严格比较。通过时重算规范产物、文档域 ID、`ir-structure` ID 和支持引用。拒绝时以原候选重演明确的失败规则，校验见证、拒绝分支的义务和结论。对预算、时限和操作中止，核对该次尝试的绑定及可观察事实，保留独立路径无法复现的执行来源边界。

规则或原字节缺失、checker 支持不足或内部预算不足时，按独立结果协议报告不完整。摘要、角色、版本配对、支持或见证矛盾时拒绝。对 `structure_rejected` 的独立接受只确认拒绝结论有据。生产 P1 重跑用于本机取证，独立 checker 不导入生产 P1 作为自身判定。 [独立检查协议](../adr/0008-independent-checker-isolation-and-artifact-exchange.md#独立检查行为)

## 具体验收矩阵

基础原件为 [AX-B01 correct IR v0.2](../../crates/axiom-ir/tests/fixtures/v0.2/migrated/ax-b01-correct.jcs)，长 4,927 bytes，raw SHA-256 为 `9a62d3b9397f2db664786d64ad77b848a53c46e62186edc29d2c31f665db9f2a`。本轮对该原件及变异执行了只读的本机 P1 探测，探测用 `max_values=100000`、`max_nesting=128`，字节预算见下表。最后一列是待验收的公共支持判定。

| 用例 | 输入及预算 | 本机 P1 观察 | 公共支持期望 |
| --- | --- | --- | --- |
| S1-PASS | 原件，字节预算 4,927 | 严格通过，返回 v0.2，规范字节保持 | 满足绑定和独立检查后支持 `checked` |
| S1-LF | 原件追加一个 LF，字节预算 4,928 | `NonCanonical`，offset 4,927。非严格入口恢复原件 | 以修改后的原始摘要和首差字节支撑 `failed`，可形成 `structure_rejected` |
| S1-UTF8 | 字节 `7b ff`，字节预算 2 | `InvalidUtf8`，offset 1 | 确定性拒绝，见证只使用原字节 |
| S1-MEMBER | 在原件根的 `"nodes":` 前插入 `"metadata":true,`，字节预算 4,943 | `UnknownMember`，路径 `/metadata` | 确定性拒绝，独立检查闭合成员 |
| S1-CAP | 原件，字节预算 4,926 | `ResourceLimit(InputBytes)`，offset 4,926 | 保留真实中止。以其声称 `failed` 或 `structure_rejected` 时拒绝 |
| S1-LF-CAP | S1-LF 的同一输入，字节预算 4,927 | 先触发 `ResourceLimit(InputBytes)`，offset 4,927 | 保留该次中止。独立用较宽预算复现 LF 拒绝时保留两次尝试各自的身份 |
| S1-LEGACY | [规范 v0.1 correct](../../benchmarks/keyed-finite-table-v0.1/ax-b01/candidates/correct.ir.jcs)，字节预算等于该文件长度 | 通用 P1 严格通过，返回 v0.1 | v0.2 支持拒绝该配对，保留原版识别及显式迁移边界 |

S1-LF 的原始摘要为 `sha256:0f8220a6f3f8915341179a306bc75cbe4a9ee8a2af3e43faf7ff108ae7740d2f`。按上述拟议的拒绝义务 definition 与 v0.2 域计算，示例义务 ID 为 `sha256:7becb82401461021b65c292ba49c2d4deceb88885feec3ea5e4d6b0b9b3c7130`。S1-LF-CAP 输入摘要相同，执行预算不同，其实际中止不产生该拒绝义务结果。

待验收的契约变异应分别重算受影响的外层摘要和引用，以抵达实际规则检查：

| 变异 | 预期 |
| --- | --- |
| 将 LF 变异以修复后的摘要作合法 subject，或只把相同长度的其他候选换入 | 拒绝原始输入与 subject 或规范产物绑定 |
| 用 `check-fixture`、缺少 `ir-normalizer` 的 tool、P2 集合或 P5 回执替代严格执行 | 拒绝状态支持 |
| 重绑错误预算、非严格模式、其他规则或其他语义快照 | 拒绝调用与结果绑定 |
| 偏移错一字节、越界、替换错误原因、把失败见证移到另一候选，或给拒绝 subject 填合法文档 ID | 拒绝见证或义务身份 |
| 无 attempt、原因与执行诊断不一致、以资源耗尽或操作失败冒充确定性拒绝，或与已绑定的重试历史相比漏报旧尝试 | 拒绝不受支持的结果或执行历史 |
| 缺失原件与提供同摘要引用下的错误字节分别测试 | 前者使复核不完整，后者触发身份拒绝 |

## 审阅出口

2026-11-07，项目所有者明确批准三条 v0.2 支持边界。第一，严格通过支持 `checked`。第二，非规范字节、无效 UTF-8 和未知顶层成员经独立复现后支持 `failed`。第三，无法确立 subject 的中止停在 Evidence 装配前。具体机器编码、拒绝义务形状和独立实现随完整契约验收。旧 v0.1 的支持映射、规范字节和结果按原身份保存。迁移须按 ADR 0009 重建目标 IR、义务与执行结果。 [迁移边界](../adr/0009-axiom-evidence-v0-drift-and-migration.md#决策)

接续审阅 S2 的空效果重演规则，之后审阅 S3 的字段来源充分条件。本文的验证覆盖现有 P1/P2 和审阅材料，独立 v0.2 支持、迁移演练和公共验收矩阵仍待落地。 [S2 专项审阅](effect-empty-result-v0.2-review.md)
