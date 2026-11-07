# Evidence v0.2 S3 字段来源结果支持审阅

日期为 2026-11-07，基线为 `dev` 的 `01688f9`。状态为待审阅。本文给出 AX-B01 两项 `field-origin / prove` 的候选充分条件、独立重演与拒绝矩阵。S2 空效果仍待审定，两项支持分别评审。P6 为 `closed / p6-not-evaluated`。 [AX-B01 契约审阅](ax-b01-evidence-v0.2-contract-review.md) · [ADR 0024](../adr/0024-core-field-origin-derivation.md)

## 待证明的静态性质

原 P2 目标绑定某个命名输出的顶层字段及完整 IR。候选规则要证明该字段的值依赖可以按精确的 IR 投影与闭合构造追溯，且在固定标签规则下满足所声明的约束。来源可为输入字段、字面值或合法表达式；字面值无需伪造输入祖先。值选择、行存在性控制和求值上下文按各自含义重建。业务净额等式由 guarantee 判断，故障和双世界非干扰各有独立义务。 [P2 目标定义](ir-derived-obligations-v0.2.md#精确生成位置与目标) · [首域标签与来源](../semantics/keyed-finite-table-semantics-v0.2.md)

建议首批公开支持范围限定为由 `input`、`filter` 和 `map` 组成的完整图中的 `public` 顶层标量输出字段。限定的是可用证明支持，P2 仍生成原全集。满足以下条件的目标才进入候选 `kernel-replay`：

1. 独立 checker 从实际规范 IR 原字节确立 P1，重建完整 P2 集合和精确字段目标。确认顶层字段、输出接口、关联节点、记录类型和声明标签均匹配；同一节点的输出别名各自有目标。
2. 以闭合 P3-F 规则重建完整推导和三个根的引用闭包。沿值和选择边核对每项依赖确实来自 IR 中的合法引用或闭合表达式。声明边核对类型及标签，求值边保留严格求值涉及的上下文。归因按规则解释边的用途，求值子图中出现的字段不会自动成为目标的值来源。
3. 从重建的输入声明、构造和前提计算各步标签。首批要求目标声明为 `public`，值根的推导和传播标签为 `public`，行控制根的传播标签也为 `public`，三根完整闭包中无静态缺口。保留 evaluation 根及其所有边，其标签是规则的固定摘要，不能用来判定故障或非干扰。

该充分条件依赖规则对静态值和选择依赖的保守传播。input 的字段解析到明确的声明和已物化输入。filter 透传字段且把谓词标签合入行控制。map 的字段沿自身表达式计算来源及标签，继承来源行控制，并保留对各字段判断的求值边。表达式按规则保留分支、条件、绑定和全部必需操作数。按类型、节点 DAG 和表达式构造分别重演，可检查这三类前提如何闭合。该审阅不以保守上界推断最小来源集合，也不引入任务字段白名单。超出首批支持范围或条件不足时保留原义务和已有诊断，待补充规则。若后续需要改变原目标含义或身份，按既有规则另作版本决定。 [字段来源推导规则](../query/core-field-origin-v0.1.md) · [P2 版本约束](ir-derived-obligations-v0.2.md#版本与身份)

## 执行绑定、独立重演与信任

| 对象 | 拟议核对要求 |
| --- | --- |
| IR / P2 / 目标 | 绑定规范 IR raw SHA-256、文档域 ID、语义快照、完整 `ir-derived` P2 raw SHA-256、目标 ID，以及 `direction=output`、接口和字段。独立路径重建全集和目标定义。 |
| 工具 / 规则 / 产物 | `prove` 引用显式具备 `prover` 角色的实际工具身份，绑定 `axiom-core-field-origin-v0.1` 规则文件摘要和实际 `axiom-core-field-origin-derivation` v0.1 原字节。内部 `generator` 与绑定的生成器源码身份一致，工具制品和实际运行来源另核对。 |
| 预算 | 绑定 IR JSON 上限与 `Steps`、`PremiseEdges`、`Descriptors`、`PathBytes`、`OutputBytes`。前三类构建用量及路径费用按剪枝前累计，输出字节按最终闭包。等号通过，差一或累计溢出保留资源中止。checker 限额独立记录。 |
| 独立前提 | checker 使用自己的 parser、类型规则、绑定与内容身份检查确立 P1，并重建 P2。P3-F 的现有 Python 核对以 P1 为前提，属于内部规则验证。若独立 P1 或 P2 缺失，该项独立支持为 `incomplete`。 |

独立路径先确定选定规则与目标，再按依赖深度和 ID 建立类型及节点索引，重算声明、推导、传播标签及复合类型摘要。重建目标 `output.field` 的值根，以及实际节点的 control 和 evaluation 根。按角色遍历三根的全部前提，从完整构建结果保留精确闭包、依原顺序压紧索引，重算每个 gap 及有序 `gaps`。将完整重建的规范字节与提交的原字节比较，同时核对各预算用量。闭包外的公式契约和未引用节点仍由 IR 身份绑定。

生产记录须列出实际依赖的信任项。结构和标签传播可独立重算，字段的现实敏感性分类与输入来源仍来自任务所有者或外部声明，按实际范围绑定 `sensitivity-classification`、`input-origin` 等项目。独立结果还须报告 checker 的规范编码、SHA-256 和规则解释等可信计算基。 [Evidence 信任模型](axiom-evidence-v0.md#trust) · [独立检查与职责](../adr/0008-independent-checker-isolation-and-artifact-exchange.md#独立检查行为)

## AX-B01 与区分材料

| 目标 | 规范来源及位置 | correct 记录 |
| --- | --- | --- |
| `net_orders.order_id` | 通过 filter 透传 `orders.order_id`。map 的规范路径为 `["fields","1","expression"]`。 | 目标 ID `sha256:4f97f098d0782f88070ab89ced9749d603fe316f79c826f828b3561ce51711f5`，值根 `37` 引用步骤 `35`。 [原始记录](../../contracts/core-field-origin-v0.1/records/ax-b01-correct-000.jcs) |
| `net_orders.net_cents` | 在 `["fields","0","expression"]` 对经 filter 传入的 `subtotal_cents` 和 `discount_cents` 做减法。 | 目标 ID `sha256:e4b0331b7d9caf004b695af957e6e2751bed2d666515634d7295e4f72847671a`，值根 `37` 引用步骤 `32`。 [原始记录](../../contracts/core-field-origin-v0.1/records/ax-b01-correct-001.jcs) |

correct 两份记录各 38 个导出步骤。行控制根 `26` 经筛选谓词读取 `orders.state`，求值根 `36` 保留两项 map 字段的求值判断。三候选各两项目标的值与控制根传播标签均为 `public`，且无静态缺口，分别使用自身的 IR、全集和目标身份。wrong-add 与 correct 的来源输入可以相同，wrong-drop-zero 的行筛选不同，业务反例归到精确 guarantee 及实际重放。 [三候选材料索引](../../contracts/core-field-origin-v0.1/cases.tsv) · [目标归因对照](../records/2026-10-17-query-compaction-validation.md)

| 对照 | 本机核对 | 审阅结论 |
| --- | --- | --- |
| 敏感筛选 `out.result` | `gaps=[]`、值根 `public`、控制根 `sensitive` | 三根记录可以有效。首批证明支持不通过控制条件。 [原始记录](../../contracts/core-field-origin-v0.1/records/origin-sensitive-filter-001.jcs) |
| `x-x` 的兄弟字段缺口 | `out.id` 值根为 `public`，闭包仍含 `result` 的 gap `37`，由求值上下文带入 | 该缺口不能归为 `out.id` 的值依赖，也不能据此声明泄漏 `failed`。 [原始记录](../../contracts/core-field-origin-v0.1/records/origin-x-minus-x-001.jcs) |
| 严格构造中的未读兄弟 | `out.result` 值与控制根均为 `public` 且无 gap，记录仍保留未投影兄弟字段的 `expr.int_add` | 必须保留严格求值前提。静态记录只陈述该语法上下文，故障判定另行取得。 [原始记录](../../contracts/core-field-origin-v0.1/records/origin-unread-sibling-fault-000.jcs) |

## 结果与验收矩阵

待公开规则验收后，完成且满足充分条件的 `prove` 才能支撑生产 `proved` 与对应 `kernel-replay` 引用。独立结果以实际重演和剩余信任边界判定。完整记录若带 gap、超出首批范围或未满足静态充分条件，保留精确原因。只有实际且绑定目标的未完成证明尝试才能支持 `unknown`，未启动时记录缺项。当前没有适用该目标的公共反例重放路径，静态 gap、另一个目标的反例和损坏的支持材料均不能形成 `failed`。 [五态与结果支持](axiom-evidence-v0.md#五种状态) · [P4-B 目标范围](../query/p4-concrete-target-replay-v0.1.md#规范来源与支持集合)

以下公共验收待实现。语义和角色负例重算受影响的外层摘要与引用，保留单独的原始摘要错配用例。

| 用例 | 输入或变异 | 预期 |
| --- | --- | --- |
| S3-PASS | 三个 AX-B01 候选各两个目标，绑定各自执行 | 独立重建三根与闭包，通过首批静态条件。业务保证独立验收 |
| S3-TARGET | 交换两字段记录并重绑头部，或把同源输出别名合并成一个目标 | 拒绝字段根、精确绑定或义务全集不一致 |
| S3-ROLE-EDGE | 从筛选控制删选择边，从 map 求值删兄弟字段边，或替换 `selection` / `evaluation` 角色 | 拒绝重建不一致，角色不可互换 |
| S3-CONTROL | 敏感筛选的记录保持 `gaps=[]`，以公开值根声称满足首批支持。另测把控制摘要改为 `public` | 首例保留未满足条件。篡改摘要则拒绝推导 |
| S3-GAP | 保留步骤中的 gap，却清空索引。另测把 `x-x` 的保守 gap 直接声明为反例 | 分别拒绝缺口记录不一致与无实际精确见证的 `failed` |
| S3-CONTEXT | 省略未读兄弟的求值前提，或用 evaluation 根标签声称程序无故障 | 拒绝缺失前提或越界声明 |
| S3-PREMISE | 只提交 P1 成功标记、用生产 P2 清单替代独立重建，或使用其他文档的真实前提 | 缺独立前提时不完整，已知错绑时拒绝 |
| S3-EXEC | 以 `fixture-checker` 冒充 `prover`，提交合成记录充作实际执行，或提供超出绑定预算的完成产物 | 拒绝工具、执行或预算支持。实际生产中止与独立检查预算不足按各自结果记录 |

本轮重新核对了六份 AX-B01 目标记录及三种语义对照。独立 Python 入口拒绝四个针对性变异，包括重绑头部后的跨字段替换、删除选择边、删除求值边及清除求值缺口索引。既有 P3-F 定向测试覆盖 758 份内部记录和 43 类记录变异。这些是内部材料核对。 [独立材料和复现命令](../../contracts/core-field-origin-v0.1/README.md)

## 审阅出口

待审定首批范围与三条充分条件，尤其是公开字段的值与行控制须同时为 `public`，以及仅在求值闭包中出现的 gap 对首批支持的阻断。之后可将 S1、S2、S3 分别审定的边界汇入最小公共结果支持矩阵，再按 ADR 0009 确认实施和迁移演练。 [迁移边界](../adr/0009-axiom-evidence-v0-drift-and-migration.md#决策)
