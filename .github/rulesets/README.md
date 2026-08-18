# GitHub Rulesets

本目录保存可审阅的 GitHub Ruleset 模板。文件进入 Git 仓库并不等于远程规则已经启用；任何创建或更新远程 Ruleset 的操作都必须单独确认目标仓库、现有规则和变更范围。

## 当前模板

`master-protection.json` 只保护当前稳定主线 `master`：

- 禁止删除和 non-fast-forward 更新；
- 所有变更必须通过 Pull Request；
- 要求解决所有 review conversation；
- 要求严格且最新的 `Candidate Quality` 状态检查；
- 允许 merge commit 与 rebase merge，禁用 squash merge；
- 单人维护阶段审批数为 `0`，不要求 CODEOWNERS；
- 管理员只可在 Pull Request 内绕过，不开放直接 push。

模板刻意不包含提交信息 Ruleset。Conventional Commits 由仓库检查器在 PR commit range 内校验，从而避免 GitHub 自动生成的 merge commit 与远端正则规则发生冲突。

## `dev` 策略

`dev` 是日常集成分支，当前单人阶段不启用强制 Ruleset：

- 直接 push 仍须先执行风险匹配的本地验证；
- 目标为 `dev` 的 PR 自动运行 `PR Checks`，用于外部贡献和并行分支反馈；
- 当稳定维护者达到两人、开始持续接受外部贡献，或出现绕过检查造成的实际问题时，再启用 `dev` 保护；
- 每次 `master` 合并后，必须在下一轮开发前把 `master` 回流到 `dev`。

## 启用顺序

1. 将治理文件与工作流合入并推送到 `master`。
2. 从最新 `master` 创建并推送 `dev`。
3. 手动运行一次 `PR Checks`，或通过测试 PR 确认 `Candidate Quality` context 已产生。
4. 在 GitHub Merge options 中启用 merge commit 与 rebase merge，关闭 squash merge。
5. 复核远程当前 Rulesets，确认没有同范围冲突规则。
6. 通过 GitHub Settings 或 REST API 创建本模板对应的 Ruleset。
7. 用非默认分支发起测试 PR，确认直接 push、force push、会话解决和 required check 行为符合预期。

创建新 Ruleset 的示例：

```bash
gh api repos/laugh0608/RadishAxiom/rulesets \
  --method POST \
  --input .github/rulesets/master-protection.json
```

已有 Ruleset 时必须读取其 ID，并使用精确的 `PUT /repos/{owner}/{repo}/rulesets/{ruleset_id}` 更新，不要重复创建同范围规则。

## 演进原则

- Ruleset 只绑定稳定聚合 context `Candidate Quality`；新增编译器、验证器、兼容性或安全检查时，把组件接入聚合 job，不频繁修改远端 required context。
- CODEOWNERS 和至少一名审批者只在形成真实多人评审安排后启用。
- 不要求线性历史，因为阶段性 `dev -> master` 使用 merge commit 保留拓扑闭环。
- 不默认要求签名提交；建立可跨平台执行的签名与密钥恢复流程后再评估。
- 稳定版本发布和签名 tag 规则在版本方案冻结后单独设计，不提前与分支 Ruleset 混合。
- Ruleset、工作流、ADR、PR 模板与治理文档的口径必须同步变更。
