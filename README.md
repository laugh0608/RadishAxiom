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

项目处于设计到受控实现阶段。首域语义、Axiom IR / Evidence、工具链与 pipeline artifact 契约已经冻结；独立 Go checker 已在分仓完成严格离线 bundle 检查、四态 canonical result、累计资源、产品 CLI 和首个 macOS arm64 payload 的不可变发布与 `registered-inactive` 登记。主仓已建立精确 Rust `1.97.1`、Rust 2024 产品 workspace，闭合 checker runtime policy / record 身份、qualification / product registration selection、extraction-free 的严格内外层 USTAR、两层业务 manifest、canonical installation receipt、单一 result consumer、immutable spawn plan 与外层 result-or-failure 排他状态机；Darwin store 已通过唯一 exact `libc 0.2.189` 私有平台 binding 实现 descriptor-relative containment、no-replace slot / qualification publication、append-only attempt、full-sync、真实进程并发与 crash recovery。Darwin 原生 spawn / isolation、真实安装、runtime companion 与激活仍未完成。

当前阶段、已确定事项、今日进展、下一事项与后续顺位见[当前状态](docs/status/current.md)。

## 文档

- [文档入口](docs/README.md)
- [机器契约入口](contracts/README.md)
- [产品定义](docs/product-definition.md)
- [许可证与生态策略](docs/licensing-strategy.md)
- [仓库治理](docs/governance/repository-governance.md)
- [参与贡献](CONTRIBUTING.md)
- [社区行为准则](CODE_OF_CONDUCT.md)
- [安全策略](SECURITY.md)

## 仓库检查

Rust production workspace：

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-targets
```

仓库级契约与文本门禁：

macOS、Linux 或 Git Bash：

```bash
./scripts/check-repo.sh
```

Windows PowerShell：

```powershell
pwsh ./scripts/check-repo.ps1
```

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。第三方组件及精确依赖记录见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，仍遵循其各自许可证；项目名称与标识不因本许可证而获得商标授权。
