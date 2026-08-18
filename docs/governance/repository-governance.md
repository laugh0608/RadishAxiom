# RadishAxiom 仓库治理

本文面向维护者、贡献者和自动化协作者，统一说明仓库内规则、GitHub 远程强制项及其演进方式。具体分支决策见 [ADR 0001](../adr/0001-branch-and-pr-governance.md)。

## 规则层级

发生冲突时按以下职责判断，不用低层文件覆盖高层边界：

1. `LICENSE` 与第三方许可证决定法律授权。
2. `SECURITY.md` 决定漏洞报告与披露方式。
3. `docs/product-definition.md` 决定产品长期定位和语义原则。
4. `docs/adr/` 决定已接受的长期架构与治理决策。
5. 本文决定仓库操作、PR、CI 和远程设置的一致口径。
6. `docs/status/current.md` 决定当前阶段、近期重点和当前验证入口。
7. `AGENTS.md` / `CLAUDE.md` 决定协作者在任务中的执行方式。
8. `.github/` 和 `scripts/` 实施可自动执行的门禁，不自行创造与文档冲突的新政策。

如果规则与实现不一致，应先判断哪一方已经过期，再在同一变更中统一修正；不得仅修改检查器来掩盖政策漂移。

## 仓库内治理资产

| 资产 | 职责 |
| --- | --- |
| `AGENTS.md` / `CLAUDE.md` | 长期协作、执行边界和 RadishAxiom 特有语义约束 |
| `CONTRIBUTING.md` | 面向外部贡献者的最小入口 |
| `CODE_OF_CONDUCT.md` | 社区讨论、审查和违规处理边界 |
| `SECURITY.md` | 私下漏洞报告与安全问题范围 |
| `.editorconfig` / `.gitattributes` / `.gitignore` | 编码、换行、生成物和本地状态边界 |
| `scripts/check-repo.*` | 无第三方依赖的本地与 CI 仓库基线 |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR 影响面、证据、风险和回流记录 |
| `.github/ISSUE_TEMPLATE/` | 缺陷复现、语义提案与安全报告分流 |
| `.github/workflows/pr-check.yml` | PR 自动检查和稳定聚合 context |
| `.github/rulesets/` | 远程 `master` 保护的声明式模板与运维说明 |
| `docs/adr/` | 已接受治理决策及理由 |

## 分支与提交

- `master` 是 GitHub 默认稳定主线；`dev` 是常态集成分支。
- 普通贡献进入 `dev`，阶段性稳定化和 hotfix 才进入 `master`。
- 主题分支使用 `feature/*`、`fix/*`、`docs/*`、`proposal/*`、`experiment/*`、`chore/*` 或 `hotfix/*`。
- 共享分支禁止 force push 和破坏性历史重写。
- 提交遵循 Conventional Commits；允许 Git 生成的正常 merge commit。
- 提交使用真实贡献者身份，不加入 AI 协作者署名。

## PR 审查重点

所有 PR 都应说明目标、范围、实际验证、未验证内容、风险和回滚。以下变化还必须额外说明：

| 变化 | 必需说明 |
| --- | --- |
| 表面语法 | 对规范化语义的唯一映射、歧义和迁移 |
| 类型 / 效果 / 契约 | 新验证义务、错误路径和兼容性 |
| Axiom IR | schema / version、规范化、序列化和消费者影响 |
| Axiom Evidence | 可复核性、完整性、版本和独立检查器影响 |
| 求解器 / 后端 | 假设、非确定性、资源限制和 `unknown` 传播 |
| 外部能力 / I/O | 权限、信任边界、失败模式和审计信息 |
| 验证状态 | `proved`、`checked`、`unknown`、`failed`、`trusted` 的准确迁移 |
| 安全或供应链 | 威胁、依赖来源、凭据与发布完整性 |

合并门禁验证实现满足已声明规范，不替代对规范本身的审查。

## Ruleset 基线

当前目标状态：

| 项目 | 策略 |
| --- | --- |
| 保护分支 | 仅 `master` |
| PR 要求 | 必须 |
| 删除 / force push | 禁止 |
| required context | `Candidate Quality` |
| strict / up-to-date | 启用 |
| review conversation | 必须解决 |
| 审批数 | 单人阶段为 `0` |
| CODEOWNERS | 暂不启用 |
| 合并方式 | merge commit、rebase merge |
| squash merge | 禁用 |
| 管理员 bypass | 仅 Pull Request 内 |
| commit signature | 暂不强制 |
| tag / release rules | 版本方案冻结后另行设计 |

远程 GitHub 设置才具有强制力；仓库模板负责审阅、复现和防止口径丢失。修改远程前后都应导出或读取实际状态，并确认没有创建重复 Ruleset。

## CI 契约

`Candidate Quality` 是 Ruleset 唯一绑定的稳定聚合 job。当前组件只有 `Repo Hygiene`，覆盖：

- 必需治理文件是否存在；
- UTF-8、BOM、LF、末尾换行与尾随空格；
- JSON 可解析性；
- Markdown 相对链接；
- 路径和大文件上限；
- `AGENTS.md` / `CLAUDE.md` 同步；
- Ruleset、PR workflow 与 required context 契约；
- PR diff 空白和 Conventional Commits。

技术栈冻结后，应按风险把以下组件逐步加入聚合，而不是把所有逻辑堆进一个难定位的 job：

- 解析器、类型与效果系统测试；
- Axiom IR schema 和规范化兼容性；
- 验证义务、反例和状态传播；
- Axiom Evidence 重放与独立检查；
- 参考解释器、代码生成和目标后端；
- 依赖、许可证和供应链安全；
- 跨平台或可复现构建。

## 变更同步矩阵

| 变更 | 必须同步检查 |
| --- | --- |
| 分支或合并策略 | ADR、本文、Ruleset README/JSON、PR 模板、协作文件 |
| required context 或 CI 组件 | workflow、Ruleset README/JSON、检查器、ADR |
| 当前阶段或验证入口 | `docs/status/current.md`、文档入口、协作文件中的稳定引用 |
| 语义或公共格式 | 产品定义、对应专题 / ADR、PR 影响面、兼容性测试 |
| 许可证或贡献授权 | `LICENSE`、许可策略、CONTRIBUTING、README |
| 安全报告边界 | SECURITY、PR 模板、相关威胁模型或运行手册 |

## 演进停止线

- 没有真实所有权结构时不创建装饰性 CODEOWNERS。
- 没有可稳定执行的检查时，不把占位 job 设为 required。
- 没有发布载体、版本与兼容性方案时，不创建自动发布和 tag 保护幻象。
- 不复制兄弟项目的语言栈、应用检查、平台脚本或业务风险清单。
- 不用更多文档替代自动化；稳定规则一旦可机器验证，应进入 `scripts/check-repo.py` 或后续正式检查组件。
