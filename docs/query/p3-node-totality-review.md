# map / filter 剩余义务与节点总定义性切片审阅

日期：2026-10-08。状态：范围已接受，原提案留存。

项目所有者在本提案与实施询问后回复“接受，继续推进”。实施依据为 [ADR 0020](../adr/0020-map-filter-node-totality.md) 和[正式 v0.2 编码规则](map-filter-query-v0.2.md)；以下保留审阅时的建议与取舍，实际进度见[当前状态](../status/current.md)。

用途：供项目所有者和实现者决定 P3-A 之后的最小真实交付，区分结构依据、查询目标与独立验收。本文不替代已接受规范，不接受新 Evidence、solver 执行或完整 P3，也不代表下述查询已经实现。

## 建议决定与依据

建议下一切片为 **P3-B：map / filter 节点 totality 查询**，只增加一种目标，沿用 P3-A 的整图功能边界。要解除的不确定性是：指定非 input 节点在有效输入上是否能得到无故障的表结果，包括依赖故障、活动表达式故障与输出容量故障；不能依赖某个 guarantee 恰好覆盖它。

依据为 [P2 义务规则](../evidence/ir-derived-obligations-v0.2.md)、[IR v0.2 语义](../semantics/keyed-finite-table-semantics-v0.2.md)、[ADR 0019](../adr/0019-map-filter-query-encoding.md)与 [P3-A 编码规则](map-filter-query-v0.1.md)。P2 已生成节点 totality，但没有接受其 P3 查询编码；本提案不改变 P2 definition、ID、生成位置或全集。

实现依据已经存在：[节点类型检查](../../crates/axiom-ir/src/nodes/typing.rs)强制 map 的键直接保留 / 重命名和容量相等，允许 filter 缩小容量声明；[现有编码器](../../crates/axiom-ir/src/query/encode.rs)的 `Table.ok` 包含来源成功、活动表达式成功和输出容量检查。因此结构合法的 filter 仍可能对有效输入产生容量故障，不能以 P1 通过代替 totality。

## 五类剩余目标的处理

| 目标 | 已有结构依据与仍需回答的问题 | 本次建议 |
| --- | --- | --- |
| effect-empty | P1 闭合操作集合、`effects = []` 和纯表达式约束可支持语法规则推导；输入节点读取已物化值，不是外部 IO。仍需明确逐构造规则、工具信任与独立检查材料 | 后续走可核对的结构规则；不生成恒假查询冒充独立证明，不移除 P2 义务 |
| totality | DAG、类型、完整 Option 分支已由结构限制；算术越界、活动分支与容量必须结合有效输入求值 | 本切片新增查询；精确目标见下节 |
| key-cardinality | map 键双射与 filter 键保持在成功求值时可由结构规则及输入 WF 推导；filter 实际保留行数仍可能超过声明容量 | 后续单独编码容量目标并审阅键规则。不能用已经包含容量成功的 `nodeOK` 作容量反例前提，否则屏蔽自身失败 |
| row-coverage | map 一源行一输出、filter 按实际谓词选择，覆盖相对于直接 source。忠实执行错误业务谓词仍可能满足该内建目标 | 后续明确正常结果、求值故障和操作规则的复核路径；不能将业务 guarantee 的差异直接归因于 coverage，也不能用无约束自由输出制造反例 |
| field-origin | IR 中字段表达式与 P1 值标签 / 行控制标签可定位依赖；[保守流分析](../../crates/axiom-ir/src/nodes/flow.rs)明确不包含故障、总性或非干扰证明 | 后续先确定允许来源、控制依赖和标签约束的精确规则。标签缺口是分析线索；不自动构造具体反例，public 也不证明双世界等价 |

结构可推导不等于已有独立 certificate 支持；目前不为上述任何结构路径填 `proved`、`checked` 或 `trusted`。故障时覆盖 / 键目标是否观察部分数学结果，必须在它们各自切片明确，不能借本次 totality 决定顺带接受。

只读核对既有 [P3-A 静态清单](p3-query-review/materials.json)得下表。形状内表示整图符合 input / filter / map 与原表达式支持边界，未评估预算、生成新查询或求解：

| P2 kind | 26 份 IR 的位置数 | P3-A 功能形状内的位置数 |
| --- | --- | --- |
| effect-empty | 26 | 14 |
| totality | 29 | 12 |
| key-cardinality | 29 | 12 |
| row-coverage | 29 | 12 |
| field-origin | 161 | 98 |

12 个 totality 候选来自 AX-B01 三份 IR 各 2 个、AX-B04 correct 1 个 / wrong-sensitive-filter 2 个 / wrong-sensitive-priority 1 个、mixed-int-ranges 1 个和 records 1 个。AX-B04 的单世界节点目标不覆盖其非干扰目标；这些数字不表示实现完成度。

## 精确输入、目标域和归因

输入继续是 IR v0.2 CanonicalDocument、严格匹配的完整 ir-derived ObligationSet、一个目标 ID、显式生成器身份和 QueryLimits，另显式选择编码 profile。totality 必须定位到该集合内 `expectation = prove`、`subject.kind = node` 的非 input 节点；不接受独立拼装的 subject、节点名字或调用方成功标记。

令 `OK(n)` 表示按该 IR 求值节点 n 能得到正常表结果。拟接受的反例查询是：

```text
WF ∧ Pre ∧ ¬OK(target)

OK(input) = true                         // 输入合法性由 WF 约束
OK(n) = OK(source(n)) ∧ ExprOK(n) ∧ CapacityOK(n)
ExprOK(filter) = ∧i (active(source_i) ⇒ ok(predicate_i))
ExprOK(map) = ∧i,f (active(source_i) ⇒ ok(field_i,f))
CapacityOK(n) = count(active output slots of n) ≤ declared capacity(n)
```

WF 和 Pre 严格沿用 P3-A；Pre 是所有 assume 的 `ok ∧ value`。不为矛盾 Pre、空输入或 assume 故障新增非空性 / 可满足性义务。未活动槽位、未选择的 if / Option 分支不产生运行故障；严格求值的 and / or / record 字段依原规则传播故障。保留完整来源槽位数，不按输出容量截断。

上述局部展开仅在来源成功时具有实际求值意义；来源失败时目标没有结果，由 `OK(source) = false` 确定 `OK(n) = false`，其余符号占位值不构成已执行的下游计算。

需要明确接受以下归因边界：

1. **依赖故障保留。** 上游失败导致目标无结果时，目标 totality 也被违反。这是节点结果的总定义性，不是只归因本节点新引入的故障。反例后续应沿依赖记录根因，不能声称下游表达式实际执行并故障。
2. **无关故障不传播。** 独立节点或仅依赖目标的下游失败，不改变目标的 `OK`。不能用 `¬ProgramOK` 替代 `¬OK(target)`。
3. **业务断言与求值分开。** guarantee 为 false 或其公式自身故障，不改变已正常求值的目标节点；它们仍由 contract-guarantee / 对应范围目标承担。节点可以总定义但业务结果错误。
4. **禁止循环前提。** 不将 `OK(target)`、`ProgramOK`、输出容量合法、范围已成立或其他 prove 义务成功加为假设；也不加 `OK(source)` 前提来删除依赖故障输入。多个 totality 与 numeric-range 可以同时出现反例，不要求义务逻辑独立。

`OK(source) ∧ ¬LocalOK(target)` 是另一种“局部新故障”目标，会排除依赖故障，本提案不选择它；如将来需要该目标，必须单独决定，不能用同一个 P2 ID 静默更换语义。接受前若发现上述节点求值解释与既有 P2 目标冲突，应停止并走义务 minor 版本审阅，不能只升级 query profile 来掩盖目标变化。

## 支持、拒绝与兼容性

建议新增内部编码 profile `axiom-p3-map-filter-query-v0.2`，支持原两类目标及 totality；保留 `axiom-p3-map-filter-query-v0.1` 的两类支持集合和拒绝行为。query artifact 仍为 `axiom-smtlib2-qf-uflia-query0.2`，方言不变；profile 的增加不使旧 adapter / Evidence 能接受新产物。

在既有 `encode_query` / `check_query` 上增加显式的类型化 profile 参数，`QueryBinding` 保存实际选择；现有仓内调用点显式指定 v0.1，不增加平行编码入口，也不隐式选择 latest。该选择会改变内部 Rust 调用签名，应在实施批次同步所有调用点；未发布 CLI、SDK 或公共 Evidence 无新增接口。

同一 IR / P2 / 目标 / 生成器身份在 v0.1 下保留 SMT 字节和绑定；新 profile 对原两类目标不改变公式与 SMT 字节，仅 profile 绑定不同。调用方不能只比较 raw SMT 摘要判断两份完整产物相同。`check_query` 仍只做输入驱动的字节重建；它没有接收外部完整绑定的接口，不能声称已检查调用方提供的 profile 元数据。完整绑定消费仍留给后续集成。

整份图及全部 formula contract 的功能扫描不变：join / group / exists_rows / count_where / sum_where 继续拒绝；即使不支持功能位于与目标无关的节点或 guarantee 也不跳过。非干扰契约可保留，但不能充当单世界假设。旧 IR 不隐式迁移，非 prove 返回 NotProve，旧 profile 的 totality 与新 profile 的其余四类目标仍返回 UnsupportedKind；错绑定、未知 ID、功能和资源拒绝保持可区分。

只生成不可变 query，不生成 solver attempt、模型、五态、Evidence、执行许可或 proof。P2 集合、旧规范与已绑定材料保持原字节；新增验收材料单独保存，不通过重生成旧材料改变旧目标支持集合。

## 实现复用与资源边界

沿用现有 `Plan`、`Layouts`、类型化 SMT `Arena`、符号映射和 `Table.ok`。目标选取由目前的两类分支改为对受支持种类的显式匹配，避免把所有非 numeric-range 误当 guarantee；不另写表达式求值或表编码器。

目标节点在构图后取其 `ok` 并取反。无需增加自由输出、逐输出键两两比较或第二套预算。仍扫描并编码完整受支持文档的公式，保证新目标不绕过原功能 / 资源拒绝；公式计算结果不进入 totality 的 violation。没有 guarantee 的合法 IR 也必须能生成 totality 查询。

沿用所有累计资源类别及分配前检查，新增取反 / 目标项计入 SmtNodes 和 OutputBytes；资源用量不能写死为旧目标用量。零容量不删义务，超大容量先拒绝，深图共享不递归展开。任何预算耗尽返回 ResourceLimit，不产生部分查询或 solver unknown。

## 独立验收设计

复用现有 Rust 查询导出、[Python 具体解释器](../../scripts/p3_query_semantics.py)与 [SMT 文本解释器](../../scripts/check-p3-query-semantics.py)的不同实现路径。具体解释侧从实际表求值并判断目标是否为 FAULT，不能读取 Rust `Table.ok`、生产 AST 或只复制布尔展开作为唯一期望。新材料绑定真实规范 IR、完整 P2 集合和目标 ID；手算期望须先于新实现冻结。

| 必需材料 | 输入 / 变化 | 指定目标的预期 |
| --- | --- | --- |
| 正常与边界 | identity map、正常 filter、算术恰在上下界、保留键重命名 | totality 反例式为 false |
| 活动算术故障 | map 活动行加减越界；分别覆盖 Int 与 Fixed 系数 | 该节点反例式为 true，范围目标可同时为 true |
| 容量故障 | 输入容量 2、filter 输出容量 1、谓词 true；分别保留 1 行和 2 行 | 前者 false、后者 true；不得截断为一行 |
| 依赖故障 | filter 容量失败后接 identity map；目标分别指向两个节点 | 两者 true，下游原因是来源失败 |
| 无关节点故障 | 两个独立分支，一支正常、一支越界；交换 totality 目标 | 正常支 false、故障支 true；拒绝全局故障冒充目标归因 |
| 下游故障 | 正常目标后接故障节点 | 上游目标 false、下游目标 true |
| 分支可达性 | if / match_option 的未选分支越界；反转条件 / 标签 | 未选 false、选中 true；None 不读取载荷 |
| 严格求值 | map 构造记录的非投影兄弟字段故障；filter 的严格 and / or 子项故障 | 对应节点 true，不因结果看似可确定而跳过故障 |
| 非活动行与空表 | 稀疏 active 槽位、未活动非法载荷、零容量以及筛掉全部行后接含越界式 map | WF / Pre 满足时 false；不增加非空要求 |
| 输入与前置条件 | 重复输入键、活动值越界、Pre false、Pre 故障 | 最终反例式均 false，域外不等于程序已证明正确 |
| 契约区分 | 正常节点配 false guarantee 或故障 guarantee；另加无 guarantee 文档 | 节点 totality 均 false；前两者 guarantee 目标 true |
| 业务区分 | 非键字段错误但值在类型范围内；filter 忠实执行错误业务谓词 | 节点 totality 可为 false；用独立业务期望确认保证失败，不改归因 |
| 绑定与兼容 | 错 IR / P2 / ID、旧 profile 请求 totality、check kind、未支持功能、改名 / 换目标 / 篡改字节 | 按既有类别拒绝或重算精确身份；旧两类查询逐字节回归 |
| 预算与共享 | 各累计用量精确上限 / 差一、巨大容量、深图与重复共享 | 足够预算字节一致，超限拒绝，不省略实例 |

旧材料中的 `filter-capacity`、`independent-node-fault`、`pre-fault` 等可提供合成输入，但不能因为名称相似就算覆盖。例如 `record-sibling-fault` 当前故障在 guarantee 内，只能直接支持“契约故障不影响节点”区分；须新增故障确实在 map 字段内的材料。

语义变异至少包括：改用 `¬ProgramOK`、额外加 targetOK / sourceOK 前提、移除容量检查、忽略上游失败、把 guarantee false 算作节点故障、把目标换成另一节点、将最终 assert 改为 false。每类必须被至少一个独立世界区分；只通过生产 strict 重建不算独立语义拒绝。

AX-B01 correct / 两个 wrong 的所有 totality 位置须从原始完整容量 IR / P2 生成，并保留原 numeric-range / guarantee 回归。小域中的具体真值与完整容量查询生成分别报告；不能预设所有 wrong 都违反 totality，也不能把有限小域无反例写成 unsat。invalid 仍由 P1 拒绝，timeout 仍待真实 P4，篡改维持拒绝标准。

## 完成标准、停止条件与待接受范围

接受后新增 ADR 和正式 v0.2 编码规则，实施上述单目标扩展、显式 profile、独立材料与回归。完成须同时具备真实输入到查询 / 可定位拒绝、独立具体解释与实际 SMT 文本比较、全部目标区分 / 预算 / 兼容验证，并通过当前状态列出的 Rust 格式、Clippy、测试和仓库检查。无关 runtime 不因组件通过而改变状态。

遇到 P2 目标含义冲突、需修改旧绑定字节、需增加依赖或需运行外部 solver 时停止扩张并报告精确原因。独立期望与生产输出不一致必须先定位根因，不能更新期望使其迎合生产实现。

本次请求接受的是：**节点结果包含依赖故障的 totality 目标、v0.2 内部 profile 及同一 Rust 入口的扩展与上述验收**。effect-empty、key-cardinality、row-coverage、field-origin、join / group、双世界与 P4 / P7 / P9 不在实施范围。无安装、服务启动、跨仓、远程写入、发布或真实 solver 授权。

本轮仅进行了规范 / 源码审阅与静态清单计数；本节验收全部是后续实施要求，不是已取得的结果。

本轮文档验证：`./scripts/check-repo.sh` 通过（1587 个文件，包含未跟踪的新审阅文档），`git diff --check` 通过。未修改生产源码，未重跑 Rust 测试，未执行 solver、独立 checker 或远程动作。
