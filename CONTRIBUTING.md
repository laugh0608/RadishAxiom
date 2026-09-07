# 参与 RadishAxiom

感谢你参与 RadishAxiom。项目仍处于定义与治理初始化阶段，当前贡献的首要目标是建立清晰、可复核且长期兼容的语义基础，而不是快速扩张表面语法或工具数量。

## 开始之前

建议按以下顺序阅读：

1. [当前状态](docs/status/current.md)
2. [产品定义](docs/product-definition.md)
3. [仓库治理](docs/governance/repository-governance.md)
4. 与改动直接相关的专题文档

安全问题不要创建公开 Issue，请遵循 [SECURITY.md](SECURITY.md)。
参与讨论和审查时同时遵循[社区行为准则](CODE_OF_CONDUCT.md)。

## 贡献类型

- 缺陷修复：说明可复现输入、实际结果和期望结果。
- 语义或规范提案：说明要消除的歧义、形式化边界、兼容性和反例。
- 工具链改进：说明对编译器、IR、Evidence、检查器或后端的影响。
- 文档与示例：必须与正式语义一致，不以示例暗示尚未实现的保证。
- 测试与评测：同时考虑正例、负例、边界条件和错误规范。

重大语义、信任边界、公共格式或架构变化应先形成 Issue、设计讨论或 ADR，再进入实现。小型修复和不改变正式边界的文档改进可以直接提交 PR。

## 分支与 PR

- `master` 是受保护的稳定主线。
- `dev` 是日常开发与集成分支；项目所有者或已授权维护者串行推进普通任务时直接在 `dev` 开发和提交。
- 外部贡献、并行写入、确有隔离价值的高风险改动或明确需要评审时，从主题分支向 `dev` 发起 PR。
- 需要主题分支时，使用 `feature/*`、`fix/*`、`docs/*`、`proposal/*`、`experiment/*` 或 `chore/*`；Agent 不因默认流程自动创建 `codex/*` 分支或额外 worktree。
- 只有阶段性稳定化或 hotfix 才向 `master` 发起 PR。
- 不向 `master` 直接 push，不 force push 共享分支。

完整拓扑和合并规则见 [ADR 0001](docs/adr/0001-branch-and-pr-governance.md)。

## 提交信息

提交使用 Conventional Commits：

```text
feat(parser): 支持显式效果声明
fix(evidence): 保留未知验证义务
docs(semantics): 澄清 trusted 边界
chore(repo): 完善仓库治理基线
```

允许的常用类型为 `feat`、`fix`、`docs`、`refactor`、`test`、`chore`、`ci`、`build`、`perf`、`revert`。提交必须使用贡献者自己的 Git 身份，不添加 AI 协作者署名。

## 正确性与证据要求

- “通过测试”不能表述为“已经证明”。
- “实现满足规范”不能表述为“规范等同于真实意图”。
- 新增求解器假设、外部调用、运行时依赖、未验证代码或可信输入时，必须把它们写入信任边界。
- 验证结果必须区分 `proved`、`checked`、`unknown`、`failed` 和 `trusted`，不得压缩成单一成功布尔值。
- Axiom IR 或 Axiom Evidence 变化必须说明版本、兼容性、迁移和独立检查影响。
- 失败路径应尽可能提供最小失败约束、反例或可追踪路径。

## 本地验证

当前无第三方依赖的仓库级入口为：

```bash
./scripts/check-repo.sh
```

Windows PowerShell：

```powershell
pwsh ./scripts/check-repo.ps1
```

实现技术栈冻结后，PR 还必须执行与改动范围匹配的格式化、静态分析、测试、兼容性和独立 Evidence 检查。PR 描述只记录真实执行过的命令，并明确列出未验证范围。

## 许可证

除非另有明确书面约定，贡献以项目的 [Apache License 2.0](LICENSE) 提交并分发。提交贡献即表示你有权提供相关内容；第三方代码、数据、模型、字体与资产必须标明来源并遵守各自许可证。
