# RadishAxiom 当前状态

更新日期：2026-08-20

## 当前阶段

项目处于目标领域已确定、语义与证据边界待冻结的设计阶段。当前目标是围绕首个目标领域补齐类型化语义、Axiom IR、Axiom Evidence 与可复现实验设计；在这些边界完成前不进入编译器实现。

## 已确定

- 项目定位：面向 AI Agent 的验证优先语言与可信语义层。
- 命名：`.rax`、`raxc`、Axiom IR、Axiom Evidence。
- 核心原则：约束显式、信任可见、验证状态分层、证据可复核、小可信内核。
- 首个目标领域：有键有限表的确定性转换；核心纯且无外部副作用，首批基准覆盖净额计算、键连接、守恒聚合和敏感字段非干扰。
- 许可证：Apache License 2.0，并形成开放基础层与商业化边界策略。
- 仓库治理：`master` 稳定主线、`dev` 日常集成、PR 门禁和合并后回流策略。
- 当前仓库级验证：`./scripts/check-repo.sh` 或 `pwsh ./scripts/check-repo.ps1`。

## 下一阶段决策

1. 定义有键有限表转换的类型化语义、效果与信任边界。
2. 定义 Axiom IR 的规范化形式与版本策略。
3. 定义 Axiom Evidence 的最小格式、状态语义和独立检查边界。
4. 物化 ADR 0002 的版本化基准语料库，并预注册 Agent 对比实验条件。
5. 比较实现语言、验证后端与目标运行时，再冻结首个工具链并进入实现。

## 尚未冻结

- 表面语法；
- 编译器实现语言；
- SMT、证明助手或其他验证后端；
- 解释执行、代码生成或双路径运行模型；
- 包管理、IDE、插件和发布载体；
- 稳定版本号与兼容性承诺。

在上述决策完成前，不为占位目的引入完整编译器骨架、运行时依赖、自动发布、CODEOWNERS 或技术栈专属 CI。

## 按需阅读

- [产品定义](../product-definition.md)
- [许可证与生态策略](../licensing-strategy.md)
- [仓库治理](../governance/repository-governance.md)
- [ADR 0001：分支、PR 与 Ruleset 治理](../adr/0001-branch-and-pr-governance.md)
- [ADR 0002：首个目标领域与基准任务](../adr/0002-first-target-domain-and-benchmarks.md)
- [面向 Agent 的语言设计：证据与开放问题](../research/agent-oriented-language-design-evidence.md)
