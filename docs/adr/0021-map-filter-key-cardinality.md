# ADR 0021：map / filter 局部键与基数查询

日期：2026-10-08。状态：Accepted，项目所有者已接受 P3-C 精确范围。

## 背景与决定

[P3-C 审阅](../query/p3-key-cardinality-review.md)区分节点无结果和局部键 / 基数违例。沿用 P2 的 key-cardinality definition / ID，新增显式 `axiom-p3-map-filter-query-v0.3`，只扩展 map / filter 的 key-cardinality；原有 numeric-range、contract-guarantee、totality 保留。此前未接受该 kind 的其他 P3 故障命题。

以直接来源成功及所有活动局部表达式成功组成 Ready；其不包含目标自身容量。Ready 成立时，按真实节点操作形成容量检查前数学行候选 O*。查询反例为 `WF ∧ Pre ∧ Ready ∧ (¬Unique(O*) ∨ ¬Capacity(O*))`。完整规则见 [v0.3 规范](../query/map-filter-query-v0.3.md)。

自身容量超限可被观察；来源或局部表达式故障由 totality / numeric-range 承担。无关节点、下游及 guarantee 不屏蔽或制造本目标违例。不能加 targetOK、ProgramOK 或输出合法性前提循环排除反例。O* 不成为实际成功输出，执行的容量故障保持。

## 兼容与资源

旧 profile 不接受新 kind，旧三类目标在任何 profile 下保持 SMT 字节、符号与预算。artifact / 方言不改，profile 是完整绑定的一部分。仅新 kind 为目标增加两两输出键比较，在分配之前累计 `N(N−1)/2 × K` SlotComparisons，N 为继承表示槽位数，不是输出容量；算术溢出拒绝。其他新数组、term、引用边、字节仍受现有预算约束。

## 证据边界与后续

有效 map / filter 不从 WF 输入制造重复键；不能伪造这种程序反例。独立具体解释负责完整路径的有限核对；合成 O* 注入只负责唯一键谓词单元检查，分别报告。检查通过不等于 solver、证明或独立 checker 结果。

row-coverage 暂不支持，尚须决定故障观察、操作关系及独立规则。effect-empty、field-origin、join / group、双世界和 P4 / P7 / P9 均不在本决定内。没有外部工具执行、依赖安装或远程操作授权。
