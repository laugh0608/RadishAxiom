# RadishAxiom 文档

`docs/` 是 RadishAxiom 的正式设计与决策入口。新会话先读取当前状态，再按任务进入产品、治理、ADR 或后续专题文档，不默认展开全部资料。

## 默认入口

- [当前状态](status/current.md)：当前阶段、已确定事项、明日事项、后续顺位、临时门禁与验证入口。
- [Agent 协作与执行规则](governance/agent-collaboration.md)：根入口之外按需读取的工作区、授权、实施、验证与交接细则。
- [产品定义](product-definition.md)：项目定位、命名、边界与首个里程碑。
- [许可证与生态策略](licensing-strategy.md)：开放基础层、商业化边界与长期贡献治理。
- [仓库治理](governance/repository-governance.md)：协作、Git、PR、CI 与 GitHub Rulesets 的统一口径。
- [ADR 索引](adr/README.md)：已经接受或废弃的长期决策。

## 仓库级入口

- [`AGENTS.md`](../AGENTS.md) / [`CLAUDE.md`](../CLAUDE.md)：启动级长期约束与任务路由，两份文件必须完全一致。
- [`CONTRIBUTING.md`](../CONTRIBUTING.md)：外部贡献流程与正确性要求。
- [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md)：社区讨论、审查与行为边界。
- [`SECURITY.md`](../SECURITY.md)：安全问题范围与私下报告方式。
- [PR 模板](../.github/PULL_REQUEST_TEMPLATE.md)：语义、信任、Evidence、验证与回流检查清单。
- [Ruleset 说明](../.github/rulesets/README.md)：远程保护模板与启用顺序。

## 研究备忘

- [面向 Agent 的语言设计：证据与开放问题](research/agent-oriented-language-design-evidence.md)：外部证据、证据限制、项目假设与最小实验要求；不作为正式语法或技术栈规范。

## 正式设计规范

- [有键有限表转换：首版类型化语义](semantics/keyed-finite-table-semantics.md)：首个目标领域的值、表、转换、契约、效果、失败、反例与信任边界。
- [Axiom IR v0.1：规范化形式与版本策略](ir/axiom-ir-v0.md)：规范化数据模型、canonical JSON、内容寻址、人类投影、语义差异与版本演进。
- [Axiom Evidence v0.1：证据模型与独立检查边界](evidence/axiom-evidence-v0.md)：义务身份、五种状态、反例、信任清单、结论聚合与独立复核。
- [ADR 0009：Axiom Evidence v0.1 漂移收口与 v0.2 迁移边界](adr/0009-axiom-evidence-v0-drift-and-migration.md)：冻结 v0.1 原始规范字节，记录 group 覆盖遗漏，并限定后续 v0.2 修正与摘要迁移。
- [有键有限表基准语料库 v0.1](benchmarks/keyed-finite-table-corpus-v0.md)：四个基准的生成目录、任务身份、合成数据、正确 / 错误候选和 Expected Evidence 断言。
- [Agent 表示与验证反馈对比实验预注册 v0.1](experiments/agent-representation-preregistration-v0.md)：三种表示、两种模型条件、配对反馈、指标、阈值、预算和停止规则。

## 机器契约与生成制品

- [实现就绪契约入口](../contracts/README.md)：由已接受规范和 ADR 生成的机器 schema、canonical fixture、负向样例与黄金摘要；这些制品不替代正式语义，也不表示生产实现已经完成。
- [Independent Check Contract v0.1](../contracts/independent-check-v0.1/README.md)：独立 checker request / bundle / result 的首批结构契约、严格拒绝 bundle 与负向矩阵。
- [Execution Profile Contract v0.1](../contracts/execution-profiles-v0.1/README.md)：cvc5 / Node / Go checker 的允许参数、内部与外层资源限制、结果形成边界和 certificate 空能力停止线。
- [Toolchain & Adapter Identity Registry v0.1](../contracts/toolchain-adapters-v0.1/README.md)：Rust / Go / cvc5 / Node 的精确版本、六平台候选制品、官方摘要来源、逐制品供应链状态和执行 profile 身份。
- [Toolchain Payload Acceptance v0.1](../contracts/toolchain-payload-acceptance-v0.1/README.md)：Go `go1.26.7` macOS arm64 host/source 的摘要重算、只读 archive 观察、vendor / 许可证清单、签名停止线与局部 acceptance。
- [Pipeline Artifact Contract v0.1](../contracts/pipeline-artifacts-v0.1/README.md)：obligation set、host data、SMT query、target module 与 pipeline receipt 的首批规范字节、身份、gate / cache / partial failure 契约。
- [Implementation Readiness Contract v0.1](../contracts/implementation-readiness-v0.1/README.md)：20 个 benchmark、16 个 CHK-* 与 pipeline / readiness 路径的统一实现入口矩阵、来源覆盖和负向拒绝契约。
- [Keyed Finite Table Checker Bundle Contract v0.1](../contracts/keyed-finite-table-checker-bundles-v0.1/README.md)：28 个 readiness 场景的完整离线 bundle、Axiom Evidence、receipt、独立预期结果、进程失败边界与负例摘要链。

## 受控实现进展与下一入口

实现语言、验证后端、目标执行、生产管线和独立 checker 的架构决策已经确定，首批交换格式、身份契约、执行 profile 与 28 个离线 bundle 已进入仓库门禁。独立 checker 已在外部隔离仓库完成严格 request / manifest、只读 bundle、`checker.source`、锁定 Axiom IR profile 的结构与类型良构、Axiom Evidence 结构与身份、obligation completeness、state / support、counterexample 有限 world / `WF`，以及 concrete input artifact / `Pre`；这些结果不代表 IR DAG 执行、非输入目标反例、host / golden output、proof / attestation、结论重算或独立结论已经完成。

- 当前阶段、精确实现范围、下一事项与停止线统一以[当前状态](status/current.md)为准，不在文档索引复制易漂移的源码摘要或提交身份；
- 下一受控入口是 IR DAG 有限解释与非输入目标 counterexample replay，之后才依次进入 host / golden output 比较、proof support 真值检查和 conclusion recompute；
- Go `go1.26.7` macOS arm64 host/source 已完成局部 payload 验收；cvc5、Node、Rust 与其余平台仍须按真实实现依赖顺位完成摘要、签名 / 来源、包内依赖与许可证验收。
