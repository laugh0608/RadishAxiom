# RadishAxiom 文档

`docs/` 是 RadishAxiom 的正式设计与决策入口。新会话先读取当前状态，再按任务进入产品、治理、ADR 或后续专题文档，不默认展开全部资料。

## 默认入口

- [当前状态](status/current.md)：当前阶段、已确定事项、下一批决策与验证入口。
- [产品定义](product-definition.md)：项目定位、命名、边界与首个里程碑。
- [许可证与生态策略](licensing-strategy.md)：开放基础层、商业化边界与长期贡献治理。
- [仓库治理](governance/repository-governance.md)：协作、Git、PR、CI 与 GitHub Rulesets 的统一口径。
- [ADR 索引](adr/README.md)：已经接受或废弃的长期决策。

## 仓库级入口

- [`AGENTS.md`](../AGENTS.md) / [`CLAUDE.md`](../CLAUDE.md)：人工与 AI 协作约定，两份文件必须完全一致。
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

## 进入实现前待补齐

进入实现前，还需要补齐：

- 验证状态、信任边界与 Axiom Evidence 格式；
- 编译管线与目标运行时选择；
- 基准任务、反例和评测方法。
