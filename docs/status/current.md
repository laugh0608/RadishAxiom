# RadishAxiom 当前状态

更新日期：2026-08-20

## 当前阶段

项目处于首域语义、Axiom IR v0.1、Axiom Evidence v0.1、版本身份分层、四题版本化基准语料、Agent 对比实验预注册和 `raxc` 生产实现语言已经形成的设计阶段。当前目标是以已物化语料继续比较验证后端与目标运行时；在验收边界完成前不进入编译器实现或正式模型调用。

## 已确定

- 项目定位：面向 AI Agent 的验证优先语言与可信语义层。
- 命名：`.rax`、`raxc`、Axiom IR、Axiom Evidence。
- 核心原则：约束显式、信任可见、验证状态分层、证据可复核、小可信内核。
- 首个目标领域：有键有限表的确定性转换；核心纯且无外部副作用，首批基准覆盖净额计算、键连接、守恒聚合和敏感字段非干扰。
- 首域语义：受界值、闭合记录、公开主键、无序有限表、显式缺失、无回绕算术、恰好一次连接、守恒聚合、关系非干扰和核心效果 `∅`。
- Axiom IR v0.1：严格版本化的 canonical JSON、内容寻址 DAG、无名称绑定、稳定摘要、无损 pretty 投影、结构化差异和显式迁移；未知字段与版本严格拒绝。
- Axiom Evidence v0.1：canonical JSON 证据清单、内容寻址义务、五种不可互换状态、可重放反例、显式 trust / uncovered、确定性结论聚合和独立义务重建；生产报告不能自证。
- 有键有限表基准语料 v0.1：四个任务各有一个正确候选、两个错误候选、基础 / 边界 / 无效输入、黄金输出，以及正确、错误、后端超时和输入拒绝场景的 Expected Evidence 断言；生成结果与摘要可离线重现。
- Agent 表示与验证反馈对比实验预注册 v0.1：固定 SQL、普通 JSON plan 和 Axiom projection 三种表示，两个模型条件、72 个 trial bundle、配对反馈、确认阈值、预算与停止线；正式调用仍须 execution lock 和单独授权。
- 版本身份：项目发布采用 `YY.M.RELEASE` CalVer 与 `dev` / `test` / `release` 轨道；语言语义、Axiom IR、Axiom Evidence 和工具实现分别标识，CalVer 不表达兼容性。
- `raxc` 生产编译器实现语言：Rust 2024 edition 与精确固定的 stable 工具链；该选择不适用于独立 checker，也不冻结表面语法、验证后端或目标运行时。
- 许可证：Apache License 2.0，并形成开放基础层与商业化边界策略。
- 仓库治理：`master` 稳定主线、`dev` 日常集成、PR 门禁和合并后回流策略。
- 当前仓库级验证：`./scripts/check-repo.sh` 或 `pwsh ./scripts/check-repo.ps1`。

## 下一阶段决策

1. 比较验证后端，记录可信计算基、证书 / 重放能力、`unknown` 行为、资源边界、许可证和跨平台分发。
2. 比较目标运行时与执行路径，记录受界算术、文本、表、故障和宿主一致性边界。
3. 分别以受审阅决策冻结首版管线与独立 checker 隔离边界；满足 ADR 0002 和 ADR 0004 全部入口条件后再进入实现，工具链可用后才准备 Agent 实验 execution lock。

## 尚未冻结

- 表面语法；
- 独立 checker 的实现语言与具体实现；
- SMT、证明助手或其他验证后端；
- 解释执行、代码生成或双路径运行模型；
- Agent 实验的 execution lock、模型精确 revision、提示材料和 runner；
- 包管理、IDE、插件和发布载体；
- 首个具体产品版本、发布载体、发布记录与自动化；
- v1 后语言语义、Axiom IR、Axiom Evidence 及未来公共包的兼容性承诺。

在上述决策完成前，不为占位目的引入完整编译器骨架、运行时依赖、自动发布、CODEOWNERS 或技术栈专属 CI。

## 按需阅读

- [产品定义](../product-definition.md)
- [许可证与生态策略](../licensing-strategy.md)
- [仓库治理](../governance/repository-governance.md)
- [ADR 0001：分支、PR 与 Ruleset 治理](../adr/0001-branch-and-pr-governance.md)
- [ADR 0002：首个目标领域与基准任务](../adr/0002-first-target-domain-and-benchmarks.md)
- [ADR 0003：版本标识与兼容性分层](../adr/0003-version-identities-and-compatibility-layers.md)
- [ADR 0004：`raxc` 生产编译器实现语言](../adr/0004-raxc-production-implementation-language.md)
- [有键有限表转换：首版类型化语义](../semantics/keyed-finite-table-semantics.md)
- [Axiom IR v0.1：规范化形式与版本策略](../ir/axiom-ir-v0.md)
- [Axiom Evidence v0.1：证据模型与独立检查边界](../evidence/axiom-evidence-v0.md)
- [有键有限表基准语料库 v0.1](../benchmarks/keyed-finite-table-corpus-v0.md)
- [Agent 表示与验证反馈对比实验预注册 v0.1](../experiments/agent-representation-preregistration-v0.md)
- [面向 Agent 的语言设计：证据与开放问题](../research/agent-oriented-language-design-evidence.md)
