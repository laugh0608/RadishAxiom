# ADR 0020：map / filter 节点总定义性查询

日期：2026-10-08。状态：Accepted。

## 背景与接受

P3-A 已支持 numeric-range 与 contract-guarantee，但不能直接查询一个指定节点的总定义性。[剩余义务审阅](../query/p3-node-totality-review.md)区分了五类候选目标、依赖故障和局部故障、结构规则与查询的责任。项目所有者审阅该精确方案后回复“接受，继续推进”，接受本 P3-B 内部切片及验收范围。

## 决定

1. 在同一查询入口中增加 totality，目标为 `WF ∧ Pre ∧ ¬OK(target)`。OK 是节点按 IR 得到正常表结果：来源、活动表达式及声明容量均成功。依赖故障使目标无结果；无关节点、下游和 guarantee 自身故障不改变该目标。
2. 目标绑定现有 P2 的 node subject，不修改 definition、ID、生成位置或完整集合。不把 sourceOK、targetOK、ProgramOK、已成立范围或容量加入反例前提，不将局部新故障解释替换到同一义务上。
3. 增加显式 `QueryProfile::MapFilterV0_2`，保留 `MapFilterV0_1`。新 profile 支持原两类及 totality，旧 profile 保留原支持与拒绝。内部 encode / check API 显式接收 profile；绑定保存实际 profile，不猜 latest。
4. 复用 P3-A 的图 / 表达式支持、类型化 SMT、槽位、求值、确定性字节与累计预算。整份图和全部 formula 仍检查功能及预算；没有 guarantee 的合法文档也可请求 totality。
5. artifact / 方言保持不变，旧 profile 字节回归；同一旧目标在两个 profile 的 SMT 相同、profile 绑定不同。旧 adapter、Evidence 与 pipeline 不因此接受新产物。

正式增量规则见[查询编码 v0.2](../query/map-filter-query-v0.2.md)。本决定仅扩展 ADR 0019 的内部组件支持，不替代其余已绑定规则或完整管线门禁。

## 验收与边界

真实 Rust 查询与独立具体 IR / SMT 文本解释比较，包含算术、容量、依赖 / 无关 / 下游故障、严格与惰性分支、域外输入、Pre、空表、契约区分、键重命名、无 guarantee、语义变异、预算与身份拒绝。AX-B01 三个候选使用原完整容量 IR 和真实 P2 ID，具体小域与查询生成分别报告。

旧查询字节基线只证明回归兼容，不是独立语义期望。有限比较不代表完整域 unsat、solver 接受或证明。其余义务、join / group、双世界、P4 / P7 / P9、跨仓、外部执行、依赖变更和远程动作均不在本决定授权范围。
