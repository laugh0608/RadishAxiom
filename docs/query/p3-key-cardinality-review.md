# map / filter 键、基数与覆盖目标审阅

日期：2026-10-08。状态：Accepted，项目所有者已接受精确范围；正式决定见 [ADR 0021](../adr/0021-map-filter-key-cardinality.md)，规则见 [v0.3](map-filter-query-v0.3.md)。

用途：供项目所有者与实现者确定 P3-B 之后的目标解释、兼容性及验收。本文保留接受时的设计推导；实施范围以 ADR 0021 / v0.3 为准，不改写 P2、IR 或 Evidence，也不代表新目标已证明成立。

## 建议切片

建议 **P3-C 先增加 map / filter 的 key-cardinality 查询**，沿用现有整图与表达式支持范围；row-coverage 同轮完成边界审阅，暂不加入生产支持。要解除的具体问题是：一个已完成逐行计算的目标，其键是否唯一、行数是否超出声明容量；尤其不能因目标自身容量失败而把该输入排除。

现有 [P2 规则](../evidence/ir-derived-obligations-v0.2.md)分别生成 totality、key-cardinality 与 row-coverage；[ADR 0020](../adr/0020-map-filter-node-totality.md)只接受了 totality 的 `WF ∧ Pre ∧ ¬OK(target)`。下一目标不能复制这个公式并换 kind。

[节点类型检查](../../crates/axiom-ir/src/nodes/typing.rs)要求 map 直接保留 / 重命名全部源键且容量相同，filter 保留键与记录类型、允许缩小容量；[实际编码器](../../crates/axiom-ir/src/query/encode.rs)在同一 `success` 列表中合取 source.ok、活动表达式 ok 与容量比较。因此现有 `Table.ok` 不能直接用作本目标前提。

## 目标与故障决定

令 n 为被绑定的非 input 节点，S 为其直接来源。定义 `Ready(n)` 为：S 按现行求值规则成功，且 n 的所有活动逐行表达式无故障；它**不包含 n 自身的容量检查**。来源成功沿用已有 source.ok，不增加“来源 key-cardinality 已 proved”假设。

仅在 Ready 成立时，`O*(n)` 表示容量检查前由实际节点定义形成的有限数学行候选：map 每个活动来源槽位得到一个完整记录，filter 保留且只保留谓词为 true 的活动来源槽位。O* 不是可对外返回的成功表，也不是可自由赋值的期望输出；超过容量仍导致实际节点失败。

建议接受：

```text
Ready(n) = OK(S) ∧ ∧活动表达式 ExprOK
Capacity(n) = Σi ite(active(O*_i), 1, 0) ≤ declaredCapacity(n)
Unique(n) = ∧i<j ((active(O*_i) ∧ active(O*_j)) ⇒
                  ¬∧k∈outputPrimaryKey Equal(O*_i[k], O*_j[k]))

key-cardinality violation = Ready(n) ∧ (¬Unique(n) ∨ ¬Capacity(n))
最终 assert = WF ∧ Pre ∧ violation
```

WF、Pre、值相等、严格 / 分支求值沿用 [v0.1](map-filter-query-v0.1.md) / [v0.2](map-filter-query-v0.2.md)。完整保留来源的表示槽位；计数看 active，不看分配槽位数。不约束非活动载荷，不引入输入非空性或排序要求。复合键必须比较全部键分量，Text 仍为精确相等，不做 Unicode 归一化。

需要接受的故障划分：

- **自身容量超限是本目标反例。** 不加 targetOK、ProgramOK、Capacity 或输出合法前提，否则出现循环排除。
- **来源或局部表达式失败时，不从无意义占位行推导键 / 行数反例。** 此时 Ready 为 false，totality 仍按 ADR 0020 报告节点无结果。新增目标无反例不代表节点或程序正确，完整义务集合不能删掉 totality / numeric-range。
- **无关节点、下游和 guarantee 不影响本目标。** guarantee 为 false 不能冒充基数或键失败。assume 则仍通过 Pre 限定有效输入。
- **来源容量失败也属于来源故障。** 接在失败 filter 后面的 identity map，totality 可失败，而其 key-cardinality 不据上游占位结果再造局部反例。这与 P3-B 的依赖故障传播有意区分。

另外两种可选解释均不采用：用 `¬OK(n)` 使所有故障重复归入 key-cardinality；用 `OK(n) ∧ ¬Capacity(n)` 把容量反例全部屏蔽。这里的 Ready 是定义可观察行候选的守卫，不是证明其他义务已成功，更不削弱实际节点的故障语义。

本提案首次明确该 kind 的 P3 故障观察规则，不改 P2 的 definition / ID / 位置。若接受前发现既有目标已经承诺另一种故障含义，应先作 P2 minor 版本决定；不能仅加 query profile 就在同一旧 ID 下替换一个已接受命题。旧 Evidence / checker 结果不作为本次目标解释或成功依据。

## 为什么暂不同时编码 row-coverage

P2 的 map / filter 覆盖相对于直接 S：map 的源键与输出键双射，filter 是其**实际 IR 谓词**选中的源键。它不自动表达业务希望保留哪些行，也不能从 correct / wrong 文件名推断。

在当前 P1 限制及忠实 map / filter 语义下，键保留和操作内建覆盖可由结构规则推导；具有真实语义反例的窄入口主要是 filter 容量。为 row-coverage 加一条恒假查询不能替代明确的操作规则、故障观察和独立复核路径。结构上可推导也不等于已经拥有 kernel / certificate 支持。

row-coverage 后续必须单独决定：对 O* 的操作关系检查，还是只对成功结果检查；来源 / 谓词故障如何与 totality 配合；独立路径如何检查没有丢行 / 添行 / 错谓词，而不复用生产输出关系自证。当前不决定其失败时的真值，不给它填结果，既有 P2 位置与 UnsupportedKind 保留。

以下是手算区分材料，不是程序运行、SMT 模型或 Evidence。S 有两行 `(a, 0), (b, 1)`，键为首列：

| 场景 | totality 反例 | 拟议 key-cardinality 反例 | 覆盖 / 业务含义 |
| --- | --- | --- | --- |
| filter true，容量 2 | false | false | 正常保留 a、b |
| filter true，容量 1 | true | true | O* 仍为 a、b，操作选择关系无丢行，但无成功输出表 |
| 上一失败 filter 后接 identity map | true | false | 来源未成功，不能使用占位下游行论证覆盖或基数 |
| map 非键字段活动算术越界 | true | false | 局部计算失败，range / totality 承担故障 |
| filter 改成值 > 0，容量 2；业务要求值 ≥ 0 | false | false | 内建操作覆盖可成立，业务保证遗漏 a |
| 正常节点配 false guarantee | false | false | 仅业务断言失败 |
| 将第二行静默截掉以满足容量 1 | 不作为合法实现结果 | 不能据此宣称修复 | 这是编码 / 执行变异材料，应被独立行结果核对拒绝 |

## 实现与版本方案

拟新增 `QueryProfile::MapFilterV0_3` / `axiom-p3-map-filter-query-v0.3`，支持原三类及 key-cardinality；已有两个 profile 不改变支持、拒绝、绑定或字节。artifact / 方言和现有 Rust 函数签名不变，仍通过同一显式 profile 入口。旧 profile 不隐式接受新 kind。

沿用既有 slots、布局、相等运算、容量计数及 typed SMT Arena。在目标节点保留容量检查之前的成功项，用于 Ready；旧 `ok` 的构造与 totality 不改。只在新增 kind 的请求中生成 Ready / Unique 的辅助项，保留原三类查询的 term 顺序与字节；不为所有节点创建第二份求值图，不重新求值谓词。

Unique 对实际派生的输出键进行比较，不用 P1 成功标志替代公式。只为目标节点增加两两比较；即使 map 当前可由结构约束推导唯一性，也不删除其 P2 位置、跳过请求或返回默认成功。没有 guarantee 的合法文档可请求；全部公式与图的功能扫描仍执行。

只读核对既有 [26 份 IR 清单](p3-query-review/materials.json)：共 29 项 key-cardinality，其中 12 项处于现有整图功能形状内，17 项受 join / group / 表聚合表达式等功能阻断。12 只是静态候选，新比较成本可能触发预算拒绝，不能预报它们都能生成。

## 预算与兼容性

目标的表示槽位数为 N、输出主键分量数为 K，SlotComparisons 增加 `N × (N − 1) / 2 × K`；先做有界运算并在循环 / 分配前检查，N 为 0 / 1 时新增比较为零。不按实际活动行数预估，不以输出容量代替继承槽位数。与既有输入唯一键、lookup 和 Text 字面类成本累计。

新增比较、布尔组合、引用边和字节分别进入现有 SmtNodes、ValueCells（适用的新分配）与 OutputBytes，不新增无上限缓存或预算类别。Ready 使用现有成功项，新增辅助 term 也计费。表达式实例规则不变，不降低声明容量或只验证一个键分量以满足预算。

新 profile 对原三类目标不额外计算输出键比较，避免改变它们的既有资源拒绝集合。旧 profile 规范、测试材料、P2 集合、旧 Evidence / pipeline / adapter 字节保持；新增材料独立保存。profile 绑定不同的查询不能因为 SMT 摘要相同而互换完整制品。

## 必需验收

| 范围 | 独立期望与判定 |
| --- | --- |
| 正常、零容量与稀疏槽位 | 活动计数 ≤ 容量、不同键；空表与未活动相同载荷不产生反例；map 键重命名不改变唯一性 |
| filter 容量 | 同一容量 2 → 1 节点，在 0 / 1 / 2 个选中行上分别 false / false / true；记录完整 O*，拒绝截断 |
| 故障归因 | 局部算术、filter 谓词、来源容量失败时 key-cardinality 反例为 false，而相应 totality 为 true；无关故障不屏蔽真实容量反例 |
| Pre 与业务区分 | WF 非法、Pre false / fault 不在目标域；错误业务谓词和 false guarantee 不冒充该目标反例 |
| 复合键 / Unicode | 两行仅一个键分量相同仍唯一；全部相同才冲突；非活动行不参与；Unicode NFC / NFD 不归一化 |
| 目标、profile 和身份 | 旧 profile 拒绝新 kind、错 IR / 集合 / ID / node 拒绝或精确重绑；换目标必须可区分；原三类字节 / 预算回归 |
| 资源 | 所有累计预算精确上限 / 差一；额外目标 N²K 成本、巨大容量、深图共享；先拒绝后分配、不生成部分查询 |
| AX-B01 | 三份原始完整容量 IR 的每个 key-cardinality 目标真实生成或明确拒绝，业务 wrong 不预设为键 / 基数失败 |

完整程序路径的独立具体解释须新增“直接来源成功 + 全部活动表达式成功时的容量前行候选”观察；旧解释器将容量失败归为 FAULT，不能把它当空表使用。新观察只服务独立测试，不放宽实际执行成功，不修改旧已绑定源码或材料。新 SMT 文本仍走既有独立解析器，并与人工锚定的有限表期望比较。

**唯一键负例的诚实边界：** P1 禁止 map 任意造键，filter 不造行，因此不能伪造一个通过 P1 的合法 map / filter 程序，声称它能从 WF 输入制造重复键。重复键 / 多键分量 / 活动守卫的正负例应在局部输出谓词层注入合成 O* 并验证；明确标为谓词单元检查。完整路径用合法复合键世界验证不误报；缺少 Unique 子式的变异在该受限合法程序域可能不可区分，不能虚报端到端变异覆盖或独立证明。

必须实际区分：额外 targetOK / ProgramOK 守卫、遗漏 Ready、用槽位数代替活动数、把 ≤ 改成 <、截断输出、遗漏容量、把 guarantee 失败归入本目标、替换目标与恒假 assert。局部唯一键谓词另区分把分量合取改为析取、遗漏活动守卫和忽略碰撞；不把局部注入结果当真实程序反例。

## 完成、停止与待接受事项

接受后再新增 ADR / v0.3 编码规则，实施上述一个 kind 的内部 Rust 扩展及独立材料，运行格式、Clippy、精准与 workspace 测试、仓库检查。成功标准是真实绑定输入到规范查询 / 可定位拒绝，完整有限语义与兼容矩阵通过；没有 solver、五态、proof 或独立 checker 结论。

若发现故障解释改变既有 P2 命题、需更改旧绑定材料、扩展图操作或实际执行外部工具，停止扩张并另行决策。row-coverage、effect-empty、field-origin、join / group、双世界及 P4 / P7 / P9 仍保留各自范围。

请求接受的精确选择是：**以 Ready 守卫容量前数学行候选，保留局部键 / 基数归因；只实现 key-cardinality，增加 v0.3 profile 与目标 N²K 预算；row-coverage 暂不加入生产支持。** 审阅阶段完成源码 / 规范与静态清单核对、手算区分和验收设计；后续实施事实另记于验收记录，不把提案当运行结果。
