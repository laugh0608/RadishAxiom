# ADR 0001：分支、PR 与 Ruleset 治理

日期：2026-08-18

状态：Accepted

## 背景

RadishAxiom 是语言、Axiom IR、验证器与 Axiom Evidence 的公共基础设施。当前仓库仍处于定义阶段，如果长期直接在 `master` 累积提交，稳定语义、实验方案和治理调整会混在同一条线上，也无法为外部贡献提供清晰的审查与兼容性门禁。

五个 Radish 兄弟项目已经验证了“日常集成分支、稳定主线、PR 门禁、默认分支合并后回流”的基本拓扑。本项目采用相同原则，但根据语言基础设施的特点，把语义、信任、Evidence 与兼容性审查作为独立约束，不复用兄弟项目的应用层检查清单和实现细节。

## 决策

### 分支职责

- `master`：GitHub 默认分支和稳定主线，只通过 Pull Request 接收变更。
- `dev`：常态开发与集成分支，承接普通功能、文档、规范、治理和实验收口。
- `feature/*`：实现边界清楚的功能。
- `fix/*`：非紧急缺陷修复。
- `docs/*`：不改变实现行为的文档工作。
- `proposal/*`：语法、语义、IR、Evidence 或公共协议提案。
- `experiment/*`：后端、求解器、目标运行时或评测原型；实验结论不自动成为正式语义。
- `chore/*`：仓库、脚本、CI、依赖和治理工作。
- `hotfix/*`：仅用于必须直接修复稳定主线的问题。

### 开发与合并拓扑

普通变更以 `topic -> dev -> master -> dev` 形成闭环：

1. 主题分支默认向 `dev` 发起 PR；单人连续开发可直接进入 `dev`，但仍须执行本地验证。
2. 阶段性语义、工具链或治理基线稳定后，从 `dev` 向 `master` 发起 PR。
3. `dev -> master` 优先使用 merge commit，以保留阶段边界和可快进回流的祖先关系。
4. 仓库允许 rebase merge，但使用后必须接受提交 SHA 改变，并以普通 merge 把 `master` 回流到 `dev`。
5. 禁用 squash merge；项目依赖可审计的提交粒度，贡献者应在合并前整理提交历史。
6. 任何进入 `master` 的阶段 PR 或 hotfix PR 合并后，都必须在下一轮 `dev` 开发前完成 `master -> dev` 回流。
7. 共享 `dev` 不通过 rebase、reset 或 force push 伪造同步状态。

回流后应确认：

```bash
git merge-base --is-ancestor origin/master dev
git rev-list --left-right --count origin/master...dev
```

第一条必须成功，第二条左侧计数必须为 `0`。

### Pull Request 规则

- `master` 禁止直接 push、force push 和删除。
- 所有 `master` 变更必须通过 PR，并解决全部 review conversation。
- `master` PR 必须通过 strict/up-to-date 的 `Candidate Quality` 聚合检查。
- 单人维护阶段不要求额外批准；有稳定的第二位维护者后再提升为至少一名批准者。
- 语义、IR、Evidence、验证状态或信任边界变化必须说明兼容性、迁移、失败模式和独立检查影响。
- 只有测试或动态检查证据时，不得把结果表述为形式证明。
- 管理员绕过仅限 Pull Request 内，不开放直接 push 绕过。

### CI 与 required context

远程 Ruleset 只绑定稳定 context `Candidate Quality`。当前它聚合无第三方依赖的 `Repo Hygiene`；实现技术栈冻结后，编译、测试、静态分析、语义兼容、Evidence 独立检查和供应链检查作为组件加入聚合 job，而不频繁更换远程 required context。

Conventional Commits 由仓库检查器对 PR commit range 执行，不在 Ruleset 中添加提交信息正则，避免与 GitHub 自动生成的 merge commit 冲突。

### `dev` 的阶段性保护

当前单人维护阶段不保护 `dev`，普通 push 不自动触发 CI；目标为 `dev` 的 PR 会运行完整 PR 检查，供外部贡献和并行工作使用。

满足任一条件时重新评估 `dev` Ruleset：

- 有两名或以上稳定维护者；
- 持续接受外部代码贡献；
- 多个自动化协作者并行写入共享分支；
- 曾因绕过检查导致语义、治理或构建基线回归。

### 暂不启用的规则

- 暂不创建 CODEOWNERS，也不要求 code owner review；当前没有真实的多人所有权结构。
- 暂不要求签名提交；跨平台签名、密钥恢复与机器人身份方案尚未建立。
- 暂不创建 tag Ruleset 或自动发布；版本、兼容性和发布载体尚未冻结。
- 不把 `main` 作为模板中的备用匹配；默认分支若迁移，必须通过新的治理变更显式完成。

## 远程落地

仓库中的 JSON 只是声明式模板，不会自动修改 GitHub。启用顺序、现状核对和回滚要求见 [Ruleset 说明](../../.github/rulesets/README.md)。远程设置写入属于独立管理动作，必须先确认仓库、Ruleset ID、required context 已实际产生以及 Merge options 的精确差异。

## 后果

收益：

- 稳定主线、实验开发和外部贡献边界明确；
- `master` 始终回到下一轮 `dev` 的祖先链；
- required context 可以在检查组件增长时保持稳定；
- 语义、信任和证据变化在合并前获得显式审查；
- 单人阶段不会被虚假的自我审批流程阻塞。

代价：

- 阶段性合并后多一次强制回流和拓扑确认；
- 禁用 squash 后，贡献者必须维护可审计的提交历史；
- Ruleset、工作流、PR 模板、检查器与文档需要同步维护；
- 在 `dev` 未保护阶段，直接提交者必须承担本地验证责任。

## 变更要求

调整分支职责、合并方式、required context、审批数、bypass、CODEOWNERS、签名或发布规则时，必须同步更新本 ADR、仓库治理文档、Ruleset 模板与说明、PR 模板、工作流和协作文件。
