# map / filter query v0.3：局部键与基数

状态：Accepted，依据 [ADR 0021](../adr/0021-map-filter-key-cardinality.md)。用途：规定 P3-C 查询命题、绑定与预算；不规定 solver、Evidence 或 checker 证明状态。

## 版本和支持集合

显式 profile `axiom-p3-map-filter-query-v0.3` 在 [v0.2](map-filter-query-v0.2.md) 上只新增 key-cardinality。IR v0.2、P2 ir-derived、整图功能扫描与拒绝规则不变。artifact 仍为 `axiom-smtlib2-qf-uflia-query0.2`，方言仍为 `SMT-LIB-2.6/QF_UFLIA`。旧 profile 拒绝新 kind；同一 SMT 摘要不使不同 profile 的完整绑定可互换。

## 目标解释

对绑定的非 input 节点 n 及直接来源 S：

```text
Ready(n) = OK(S) ∧ ∧i (active(S_i) ⇒ ExprOK(n, S_i))
Capacity(n) = Σi ite(active(O*_i), 1, 0) ≤ declaredCapacity(n)
Unique(n) = ∧i<j ((active(O*_i) ∧ active(O*_j)) ⇒
                  ¬∧k∈outputPrimaryKey Equal(O*_i[k], O*_j[k]))
violation = Ready(n) ∧ (¬Unique(n) ∨ ¬Capacity(n))
assert = WF ∧ Pre ∧ violation
```

map 的 ExprOK 合取该行全部字段表达式；filter 是实际谓词的求值成功。保持既有严格 / 分支求值、依赖故障和精确值相等。Ready 不含自身容量检查。O* 是真实节点逐行定义的容量前候选：map 保持来源活动位并使用计算字段，filter 使用来源活动位与实际谓词值合取。候选保留全部继承槽位，不截断；只计活动行。O* 不是可自由赋值的输出，也不改变运行语义：容量超限仍无成功表。

仅 Ready 成立时观察候选。来源失败（包括来源容量）或活动局部表达式失败使该目标无反例；这不表示 totality 成立。目标容量失败产生反例。无关 / 下游故障及 guarantee 不参与；assume 通过 Pre 参与，Pre false / fault 排除输入。不能加 targetOK、ProgramOK、Capacity 或输出 WF 守卫。所有输出主键分量参与比较，非活动载荷不受约束，Text 不做 Unicode 归一化。

## 编码与预算

使用同一求值图、已求值局部成功项、实际派生字段、活动位和容量比较。只在请求该 kind 时创建目标 Ready / Unique / violation；其他目标保持 term 顺序、字节、符号和预算，不增加输出比较。

在布局、表槽位及比较循环分配前，按目标继承槽位数 N 和主键分量数 K 预收 `N(N−1)/2 × K` SlotComparisons，与输入键、lookup 和 Text 比较累计。N = 0 / 1 时为零，有界算术失败必须拒绝，不能按输出容量降价。谓词临时 term 数组计入 ValueCells；SMT 节点及操作数边计入 SmtNodes；输出计入 OutputBytes。所有精确预算及差一边界均验收；无部分成功查询。

## 验收和未覆盖范围

新材料在 `contracts/map-filter-query-v0.3`，使用独立具体来源成功与容量前行观察，严格解析真实 Rust SMT 并逐世界比较。旧 v0.1 / v0.2 材料保持原字节，旧三类查询与实施前摘要及六类预算回归。

合法 map / filter 的结构限制排除 WF 输入产生重复键。重复键、活动守卫、复合键合取的负例仅在生产唯一键谓词上注入合成 O* 并独立解释实际 SMT；完整程序用合法复合键和 Unicode 世界验证不误报。忽略 Unique 在合法受限域可能不可区分，不宣称端到端变异覆盖。

有限语义检查、strict 重建、solver 结果、形式证明和独立 checker 结果不得互换。row-coverage、effect-empty、field-origin 及新增图操作仍为 UnsupportedKind / UnsupportedFeature；不填成功结果。
