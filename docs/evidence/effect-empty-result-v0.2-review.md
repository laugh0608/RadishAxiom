# Evidence v0.2 S2 空效果独立重演审阅

日期为 2026-11-07，审阅基线为 `dev` 的 `bd1bbe6`。项目所有者已批准 S2 的独立重演及 P1 / P2 前提。本文给出 AX-B01 `effect-empty / prove / program` 接入 `kernel-replay` 的支持边界，供生产记录和独立 checker 实现评审。现有 P3-E 是内部推导，公共支持须单独验收。P6 为 `closed / p6-not-evaluated`。 [AX-B01 契约审阅](ax-b01-evidence-v0.2-contract-review.md) · [ADR 0023](../adr/0023-core-empty-effect-derivation.md)

## 目标与执行材料

目标是同一份规范 IR v0.2 所描述的整个纯核心程序的能力效果为空。论证从闭合规则出发。字面值、绑定、已物化输入等叶子无外部能力，复合表达式、表变换、接口和契约的前提也都为空效果时，组合步骤保持空效果。程序根检查空效果声明并合并整个文档的前提。该规则覆盖故障可能发生的纯计算，算术范围、总性、业务保证和非干扰分别由其义务判断。输入的实际取得、解码、运行器和系统能力按各自边界记录。 [IR v0.2](../ir/axiom-ir-v0.2.md) · [首域语义](../semantics/keyed-finite-table-semantics-v0.2.md) · [空效果闭合规则](../query/core-empty-effects-v0.1.md#闭合规则与顺序)

| 绑定 | 拟议核对要求 |
| --- | --- |
| subject 与目标 | 合法 `axiom-ir` subject 绑定实际规范 IR 原字节、IR 文档域 ID 和精确语义快照。目标必须是同一文档的唯一 `effect-empty / prove / program`，保持已接受的定义和 ID。完整 `ir-derived` P2 集合是待对比的制品，由 checker 从 IR 重建。 |
| 规则与执行 | 选定 `axiom-core-empty-effects-v0.1`，绑定规则文件原字节和摘要、执行限额、实际 tool ID、工具制品和精确版本。执行 kind 为 `prove`，所用工具须显式具有 `prover` 角色。 |
| 完成产物 | 完成的 `prove` 关联实际 IR、完整 P2 集合、目标及原始 `axiom-core-effect-derivation` v0.1 字节。按原始摘要解析并校验制品长度、格式和版本。内部 `generator` 与该执行所绑定的生成器源码身份一致，工具制品及运行来源另行核对。 |
| 预算 | 绑定 IR JSON 字节、值数和嵌套上限，以及 `Steps`、`PremiseEdges`、`PathBytes`、`OutputBytes`。按规则复核累计用量，包含重复角色边和最终根的前提。checker 自身的限额另行执行和报告。 |

候选公共规则沿用 `kernel-replay` 引用实际执行，由该执行追溯推导产物和完整输入。正式支持验收后，生产侧可在上述执行完成且材料完整时声明有对应 support 的 `proved`。独立结果须另按下述规则产生。仅有推导、测试向量或生成器身份字符串时，材料停留在原有层级。 [Evidence 支持变体](axiom-evidence-v0.md#proved) · [P2 义务身份](ir-derived-obligations-v0.2.md#版本与身份)

## P1 前提与可信边界

建议把独立确立 P1 作为 S2 的必需检查。checker 先针对本次同一 IR 原字节独立完成 S1 严格检查，包括闭合结构、规范表示、版本和语义绑定、类型与字段、作用域、引用和 DAG、声明及文档内容身份。随后独立重建 P2 全集和目标。S1 的 `checked` 是可核对的生产记录。独立路径必须获得自己的检查结果，不能从记录中的状态标记推定前提成立。候选若只具有独立的效果规则重建，P1 或 P2 覆盖不足时，S2 独立支持为 `incomplete`，不进入 `passed`。 [S1 已批准边界](ir-structure-result-v0.2-review.md#审阅出口) · [独立性与检查顺序](../adr/0008-independent-checker-isolation-and-artifact-exchange.md#独立检查行为)

生产记录应明确依赖 P1 对实际 IR 的严格解码、类型、结构和身份检查，列出适用的 `decoder-normalizer` 等信任项及其制品、规则和执行范围。独立重建能缓解对生产实现的依赖。独立结果仍须报告实际 checker 的 parser、规范编码、SHA-256 和规则解释等可信计算基，以及实际仍需依赖的声明。P3-E 的 Python 对照依赖完整 P1 类型正确性，继续作为有此前提的有限规则核对。 [Evidence 信任项](axiom-evidence-v0.md#trust) · [独立 checker 可信计算基](../adr/0008-independent-checker-isolation-and-artifact-exchange.md#独立性与可信计算基)

本轮用 AX-B01 correct 做了精确区分。把 map 的 `net_cents` 减法左操作数替换为 `{"op":"literal_bool","value":true}`，重算 map 节点 ID、更新输出引用并按 ID 重新排序节点。变异 IR 的 raw SHA-256 为 `8639416a6791dea1399d6e258264a7092eb15777209e1e9ddde3ca3a067ce84e`。现有 Python 路径从该变异重建 P2 和空效果记录，仍生成 `program.empty`，严格 P1 则在 `/nodes/2/definition/fields/0/expression` 返回 `ExpectedInt`。因此即使空效果推导在字节上可重建，此候选也无法确立合法 subject，S2 不能组装成功。类型错误也不自动进入 S1 已批准的三类 `failed` 支持。 [有限重建入口](../../scripts/p3_effect_derivation.py) · [严格 P1 入口](../../crates/axiom-ir/src/document.rs)

## 独立重演步骤

1. 解析并校验 Evidence 引用、制品原字节、规则和执行绑定。确认本地支持精确规则版本、`prove` / `prover` 角色和预算。按上节确立同一 IR 的 P1 / P2 前提。独立 checker 自己生成期望步骤，不以产物的根、前提或 producer 成功值作为遍历依据。
2. 从完整 IR 提取节点和依赖。按依赖深度、再按节点 ID 的规范顺序重建各节点。对每个表达式位置按规则后序遍历，核对闭合构造、anchor、规范 path、绑定深度和全部有序前提。即使分支不可达、表容量为零或 Pre 恒假，也要覆盖其语法位置。对共享节点保留所需的角色引用，避免递归展开和错误去重。
3. 在全部节点之后按名称重建 output，再按契约 ID 重建 assume、guarantee 和 noninterference 对应步骤。接口引用解析为已绑定的 input 或 output，assume 只允许 input。独立确认声明为 `effects: []` 并生成 `effects.empty`。
4. 最后生成唯一的 `program.empty`，anchor 是该完整文档，path 为空。有序前提为 `effects.empty`、按 ID 的全部节点、按名称的全部输出、按 ID 的全部契约。根与节点构造顺序不同，不能用只从输出可达的节点子图代替全集。
5. 重算规范字节、根索引、步骤、前提和用量，与实际产物完整比较。拒绝遗漏、多余、重复、错序、前向引用和未知成员，即使重新散列后的外层引用一致。重演只能使用 checker 自己的规则实现。 [ADR 0008 独立实现边界](../adr/0008-independent-checker-isolation-and-artifact-exchange.md#允许共享与禁止共享)

AX-B01 correct 的实际内部推导为 54 步、60 条前提边、1,699 path bytes、10,838 output bytes。目标 ID 为 `sha256:64bd44f0489b89d0912ce46e659f393de494341a5c960cf23f9efb7698308a70`，记录 raw SHA-256 为 `21d5fc31759bfaea4ad44c9144d281922beb82d3f510b904f9def4403f9bdcc1`。程序根为 `53`，前提 `[52,5,13,0,14,22,51]` 依次对应空声明、filter、map、input、命名输出、assume 和 guarantee。两个 wrong 候选也各有匹配的完整空效果推导，它们的业务义务仍分别判定。 [记录原字节](../../contracts/core-empty-effects-v0.1/records/ax-b01-correct.jcs) · [三候选及预算索引](../../contracts/core-empty-effects-v0.1/cases.tsv)

## 结果与验收用例

候选 `kernel-replay` 只有在独立重演通过后才给该项 `passed`。产物或支持规则缺失、checker 自身预算不足时按实际缺项报告 `incomplete`，已知绑定或重演矛盾则拒绝。生产执行资源耗尽或中止，只有实际绑定的尝试和相符原因才可给 `unknown`，未执行时记录缺项。损坏的推导或非法 IR 不能作为合法 subject 上的 `effect-empty failed` 见证。当前 S2 未定义该目标的公共失败重放支持，也不使用 `checked` 或 `trusted` 完成 `prove`。 [五态与独立接受](axiom-evidence-v0.md#五种状态)

下表的公共期望待实现验收。语义或状态变异要重算受影响的外层摘要及引用，使其抵达目标检查。保留独立的制品摘要错配用例。

| 用例 | 输入或变异 | 预期 |
| --- | --- | --- |
| S2-PASS | 正确及两个 wrong 各自的 IR、完整 P2、目标和记录，使用本身预算与实际执行绑定 | 各自重建程序根。只确认空效果，业务保证单独核对 |
| S2-ROOT | 将 correct 根索引从 `53` 换成真实存在的 `52` | 拒绝，`effects.empty` 缺少全程序前提 |
| S2-EDGE | 从程序根删去 guarantee 前提，或省略未被输出引用的节点。另测跳过死分支、`match_option` 分支或量化表达式 | 拒绝不完整前提、顺序或作用域。所有规定的语法位置均须重演 |
| S2-BIND | 以 wrong-add 的完整有效内部记录冒充 correct，另测替换 P2 全集、目标、规则或语义绑定 | 拒绝，重建的文档、全集、目标与执行材料必须一致 |
| S2-TYPE | 使用已重绑 ID 的布尔减法变异及可重建的内部推导 | 严格 P1 阻断合法 subject。效果重建成功不进入 `passed` |
| S2-CAPABILITY | 在 `effects` 添加能力，或在不会选择的分支放入外部调用 | 拒绝非法输入或不支持的规则。不得据此生成合法 subject 的数据反例 |
| S2-SUPPORT | 以只有 `fixture-checker` 角色的工具提交 `prove`，或只提供 `effects: []`、测试记录或 P5 回执 | 拒绝角色或结果支持 |
| S2-BUDGET | 四项累计上限分别等于用量及差一，保留检查器预算与执行预算的区别 | 精确边界通过，生产差一保留中止，独立预算不足为 `incomplete`。若提交的完成产物已超所绑定执行预算，则拒绝支持 |
| S2-ABSENT | 分别测试缺少推导原件、缺少已声明的规则实现、同一摘要下返回错误原字节 | 前两种不完整，错误原字节触发身份拒绝 |

本轮运行了既有五项 P3-E 定向测试，其中包含 88 份内部记录、28 类记录变异和 7 类坏树核对。另用 AX-B01 核对了根替换、删除 guarantee 前提、跨候选记录替换和已重绑的类型变异。后者分别执行了 Python 有条件重建与本机 Rust P1 严格检查。临时探测产物已清理。测试分母和规则复现入口见[内部材料说明](../../contracts/core-empty-effects-v0.1/README.md)。

## 审阅出口

2026-11-07，项目所有者批准 S2 独立重演及 P1 / P2 前提。S2 支持绑定实际 `prove` 执行、明确规则及完整产物。checker 须先独立确立同一原始 IR 的 P1、重建 P2，效果规则自身的有限复核按 `incomplete` 边界处理。公共格式、独立实现和验收随汇总契约推进。旧 v0.1 结果按原身份保存，迁移仍须按 ADR 0009 重新绑定与执行。 [公共支持汇总](evidence-v0.2-minimal-support-review.md) · [迁移要求](../adr/0009-axiom-evidence-v0-drift-and-migration.md#决策)
