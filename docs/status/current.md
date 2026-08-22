# RadishAxiom 当前状态

更新日期：2026-08-22

## 当前阶段

项目处于首域语义、Axiom IR v0.1、Axiom Evidence v0.1、版本身份分层、四题版本化基准语料、Agent 对比实验预注册、`raxc` 生产实现语言、首个验证后端和首个目标执行路径已经形成的设计阶段。当前目标是冻结首版编译管线的阶段、制品与失败协议；在验收边界完成前不进入编译器实现或正式模型调用。

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
- `raxc` 生产编译器实现语言：Rust 2024 edition 与精确固定的 stable 工具链；该选择不适用于独立 checker，也不冻结表面语法或目标运行时。
- 首个验证后端：cvc5 1.3.4 独立 CLI；首版使用受容量约束的量化词自由 QF_UFLIA 类编码，优先评估 Alethe certificate，保留透明 `backend-attestation`，model 必须重放为规范反例，`unknown` / 超时 / 资源耗尽 / 协议错误失败关闭；不通过 FFI 或 SDK 链接进 `raxc`。
- 首个目标执行路径：从 canonical Axiom IR 确定性生成受限 ECMAScript ES module，由 Node.js 24.19.0 LTS 独立进程一次执行一个制品；语义整数只用 `BigInt`、文本拒绝未配对 surrogate、表输出按规范键排序，禁止 npm、动态代码和隐式宿主能力；production generator、host runtime 与 codec trust 保持可见，宿主语义差异映射为 `implementation_inconsistent`，不可归因的操作失败保持 `inconclusive`。
- 许可证：Apache License 2.0，并形成开放基础层与商业化边界策略。
- 仓库治理：`master` 稳定主线、`dev` 日常集成、PR 门禁和合并后回流策略。
- 当前仓库级验证：`./scripts/check-repo.sh` 或 `pwsh ./scripts/check-repo.ps1`。

## 近期事项

1. 下一步建议只完成“首版编译管线”的正式设计与决策，不安装 Rust、cvc5 或 Node.js 依赖，不编写 parser、normalizer、obligation generator、emitter、runner 或编译器骨架。
2. 管线必须从受审阅的输入制品开始，冻结 strict decode / canonicalize、IR structure / type / effect check、义务生成、cvc5 attempt、certificate / model 处理、Node target 生成、验证门控、host execution、output compare 和 Evidence assembly 的精确先后与停止线。
3. 明确每个阶段的输入 / 输出 artifact、内容身份、工具 role、缓存与重放条件、诊断来源映射、资源失败和 partial artifact 保留规则；生产 Evidence 不能自证，生成程序不得在核心义务 `failed` / `unknown` 或输入被拒绝后执行。该决策不自动选择独立 checker、表面语法或实现模块结构。

编译管线决策审阅通过后，再冻结独立 checker 隔离边界。只有 ADR 0002、ADR 0004、ADR 0005 与 ADR 0006 的全部入口条件满足后才进入实现；工具链可用后才准备 Agent 实验 execution lock。

首域语义、Axiom IR、Axiom Evidence 与 ADR 0004 / ADR 0005 中早于后续技术决策的“实现语言 / 验证后端 / 目标运行时尚未冻结”属于其接受时的范围说明；现行实现语言、首个验证后端与首个目标执行口径分别以 ADR 0004、ADR 0005、ADR 0006 为准。首域语义的原始摘要已被基准语料和 Agent 实验注册绑定，Axiom IR 规范的原始摘要也已被实验注册绑定，不能为同步阶段措辞而原地改写。

## 尚未冻结

- 表面语法；
- 独立 checker 的实现语言与具体实现；
- 首版编译管线的阶段、制品与失败协议；
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
- [ADR 0005：首个验证后端与失败关闭边界](../adr/0005-first-verification-backend.md)
- [ADR 0006：首个目标运行时与执行路径](../adr/0006-first-target-runtime-and-execution-path.md)
- [有键有限表转换：首版类型化语义](../semantics/keyed-finite-table-semantics.md)
- [Axiom IR v0.1：规范化形式与版本策略](../ir/axiom-ir-v0.md)
- [Axiom Evidence v0.1：证据模型与独立检查边界](../evidence/axiom-evidence-v0.md)
- [有键有限表基准语料库 v0.1](../benchmarks/keyed-finite-table-corpus-v0.md)
- [Agent 表示与验证反馈对比实验预注册 v0.1](../experiments/agent-representation-preregistration-v0.md)
- [面向 Agent 的语言设计：证据与开放问题](../research/agent-oriented-language-design-evidence.md)
