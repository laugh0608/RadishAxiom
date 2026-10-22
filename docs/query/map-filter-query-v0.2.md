# map / filter 查询编码 v0.2

状态：Accepted，依据 [ADR 0020](../adr/0020-map-filter-node-totality.md)。供内部 Rust 查询实现与独立验收使用；不定义 solver 执行、模型、Evidence 或证明协议。

## 版本与共同规则

`QueryProfile::MapFilterV0_1` 对应 `axiom-p3-map-filter-query-v0.1`；`MapFilterV0_2` 对应 `axiom-p3-map-filter-query-v0.2`。encode / check 的 profile 参数必须显式提供，QueryBinding 保存实际选择。artifact 仍为 `axiom-smtlib2-qf-uflia-query0.2`，方言仍为 `SMT-LIB-2.6/QF_UFLIA`。

本规范是 [v0.1 编码规则](map-filter-query-v0.1.md)的增量：值、表、WF / Pre、表达式求值、Reach、规范 SMT 字节、绑定和全部累计预算均沿用。v0.1 继续只支持 numeric-range / contract-guarantee；v0.2 额外支持 totality。原两类的目标公式及 SMT 字节在两个 profile 相同，profile 绑定不同；不得仅凭相同 raw SMT 摘要替换完整绑定。

新 profile 不扩展整份 IR 的功能范围，仍只接受 input / filter / map 与既有 26 个表达式操作。全部 formula 都经过功能扫描和资源计数，包括与本次节点目标无关的 guarantee。非干扰契约不是单世界假设，相关目标仍不支持。

## totality

目标必须来自严格绑定的完整 P2 ir-derived 集合，kind 为 totality、expectation 为 prove、subject 为该 IR 内非 input 节点。不新增 P2 位置或身份规则，不接受调用方伪造的局部集合或成功标记。

每个节点携带既有表编码的 `ok`。input 的 ok 为 true，合法输入由 WF 限制。filter / map 的 ok 为来源 ok、所有活动表达式 ok 及实际输出活动数不超过声明容量的合取。保留来源表示槽位，不截断为输出容量。无活动实例的表达式成功为空合取，零容量是合法输入域。

唯一最终断言为：

```text
WF ∧ Pre ∧ ¬OK(target)
```

依赖故障传播为目标无结果，下游占位值不代表实际求值；不额外添加 sourceOK 前提。无关节点或下游故障不传播回目标，不用 ProgramOK 替代目标 ok。guarantee 的真假和自身故障不进入 totality，即使该文档没有 guarantee 也能查询节点。assume 仍通过其 ok 与 true 共同限定 Pre。

禁止将 targetOK、ProgramOK、目标容量合法、范围已成立或其他义务成功加入前提。多个节点 totality 与 numeric-range 可以同时出现反例；这不表示每个节点都新引入一次运行故障。标签缺口不属于本目标的运行故障。

## 字节、预算与拒绝

构图、契约求值、WF 与 Pre 的生成顺序沿用 v0.1。在其目标分派位置，totality 获取目标表 ok，再生成一个 not term；其余两类保持原顺序。之后仍按 WF、Pre、最终合取、assert 和 check-sat 的既定顺序完成。相同输入和 profile 在足够预算下生成相同字节。

无新增预算类别；新增 term / 引用及完整输出计入 SmtNodes / OutputBytes，所有数组和展开仍在分配前检查。输入规模、深引用、未选分支及未支持契约不因 totality 而绕过现有预算。

旧 profile 请求 totality、新 profile 请求其他未支持 prove kind 均返回 UnsupportedKind；check kind 返回 NotProve，错误绑定 / 未知 ID / 功能与资源拒绝保留原类别。strict 字节核对从显式 profile 和其他输入重建，不能声称核验了未作为入参提供的外部 profile 元数据。完整制品绑定消费继续由后续集成负责。

只返回只读 EncodedQuery 或明确错误；不产生 solver 状态、Evidence 五态、proof、模型或执行许可。旧材料与 P2 全集保留，不重用旧 Evidence 结果。验收矩阵及停止条件见[已接受审阅](p3-node-totality-review.md)。
