# RadishAxiom 当前状态

更新日期：2026-08-18

## 当前阶段

项目处于定义与仓库治理初始化阶段。当前目标是冻结产品边界、协作规则和可演进的验证门禁，为后续选择首个目标领域与语义核心提供稳定地基。

## 已确定

- 项目定位：面向 AI Agent 的验证优先语言与可信语义层。
- 命名：`.rax`、`raxc`、Axiom IR、Axiom Evidence。
- 核心原则：约束显式、信任可见、验证状态分层、证据可复核、小可信内核。
- 许可证：Apache License 2.0，并形成开放基础层与商业化边界策略。
- 仓库治理：`master` 稳定主线、`dev` 日常集成、PR 门禁和合并后回流策略。
- 当前仓库级验证：`./scripts/check-repo.sh` 或 `pwsh ./scripts/check-repo.ps1`。

## 下一阶段决策

1. 选择首个边界清楚的目标领域和基准任务。
2. 定义类型化语义、效果与信任边界的最小闭环。
3. 定义 Axiom IR 的规范化形式与版本策略。
4. 定义 Axiom Evidence 的最小格式、状态语义和独立检查边界。
5. 比较实现语言、验证后端与目标运行时，再冻结首个工具链。

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
- [面向 Agent 的语言设计：证据与开放问题](../research/agent-oriented-language-design-evidence.md)
