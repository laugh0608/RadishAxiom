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

项目处于设计到受控实现阶段。首域为有键有限表的确定性纯转换，语义、IR / Evidence 与机器契约已形成；分仓 Go checker 已有受限 profile 的离线复核和 CLI，主仓 Rust 已实现 checker runtime 的身份、归档、存储与结果消费组件。

完整 `raxc` 生产管线、产品 checker runtime 和 Agent 收益尚未验收，active runtime 为 0。Darwin 强隔离采用 ADR 0013 / 0014 的逐次 Hypervisor runner 方向；已有合成 Linux guest 观察，真实 checker 负载、产品化与公共身份迁移仍待完成。

现有材料可用于规范审阅与组件回归，尚无面向用户的完整编译运行入口。当前能力、近期顺位和停止线见[当前状态](docs/status/current.md)；核心闭环、运行能力和实验的完成标准见[开发目标与验收计划](docs/development-plan.md)。

## 文档

- [文档入口](docs/README.md)
- [机器契约入口](contracts/README.md)
- [产品定义与首批工作流](docs/product-definition.md)
- [开发目标与验收计划](docs/development-plan.md)
- [许可证与生态策略](docs/licensing-strategy.md)
- [仓库治理](docs/governance/repository-governance.md)
- [参与贡献](CONTRIBUTING.md)
- [社区行为准则](CODE_OF_CONDUCT.md)
- [安全策略](SECURITY.md)

## 仓库检查

Rust production workspace（工具链与依赖已验收并安装后）：

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo test --workspace --all-targets --locked --offline
```

先核对实际工具链是否为 `rust-toolchain.toml` 的精确版本；环境 override 会影响选择。当前 macOS arm64 主机的显式命令见[验证入口](docs/status/current.md#验证入口与本次审阅)。命令不授权自动安装工具链或依赖。

仓库级契约与文本门禁：

macOS、Linux 或 Git Bash：

```bash
./scripts/check-repo.sh
```

Windows PowerShell：

```powershell
pwsh ./scripts/check-repo.ps1
```

当前 `Candidate Quality` 仅聚合仓库检查，尚未运行 Rust 门禁；本地 Rust 验证与 CI 的实际覆盖分别报告，接入目标见[仓库治理](docs/governance/repository-governance.md#已有-rust-实现的待补门禁)。

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。第三方组件及精确依赖记录见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，仍遵循其各自许可证；项目名称与标识不因本许可证而获得商标授权。
