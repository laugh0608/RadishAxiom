# RadishAxiom

**面向 AI Agent 的验证优先语言与可信语义层**

> Constraints in. Evidence out.

RadishAxiom 是 Radish 家族中面向 AI Agent 的语言与可信语义项目。它将约束、类型、效果和验证义务置于语言核心，由编译器审计程序并输出可复核的证据，而不是只生成可执行产物。

## 命名

- 项目与仓库：`RadishAxiom`
- 规划子域名：`axiom.radishx.com`
- 语言源文件：`.rax`
- 编译器：`raxc`
- 核心中间表示：Axiom IR
- 验证报告：Axiom Evidence

## 设计方向

- 语义先于表面语法：先冻结类型化语义与验证边界，再决定书写形式。
- 约束显式：前置条件、后置条件、不变量、效果和信任边界进入正式语义。
- 编译器即审计员：编译结果必须区分已证明、已检查、未知、失败与受信任假设。
- 证据可复核：验证输出采用稳定、机器可读并可独立检查的形式。
- 人机分层：Agent 使用规范化表示，人类通过稳定投影、语义差异和反例审阅系统。
- 小可信内核：优先缩小需要无条件信任的实现与外部依赖范围。

## 当前状态

项目处于设计阶段。生产 `raxc` 已选择 Rust，首个验证后端已选择独立进程运行的 cvc5 1.3.4；目标运行时、首版编译管线和独立 checker 仍未冻结。在这些入口条件完成前，不进入编译器实现。

当前阶段、已确定事项与近期安排见[当前状态](docs/status/current.md)。

## 文档

- [文档入口](docs/README.md)
- [产品定义](docs/product-definition.md)
- [许可证与生态策略](docs/licensing-strategy.md)
- [仓库治理](docs/governance/repository-governance.md)
- [参与贡献](CONTRIBUTING.md)
- [社区行为准则](CODE_OF_CONDUCT.md)
- [安全策略](SECURITY.md)

## 仓库检查

macOS、Linux 或 Git Bash：

```bash
./scripts/check-repo.sh
```

Windows PowerShell：

```powershell
pwsh ./scripts/check-repo.ps1
```

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。第三方组件仍遵循其各自的许可证；项目名称与标识不因本许可证而获得商标授权。
