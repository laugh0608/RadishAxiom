# RadishAxiom 当前状态

更新日期：2026-09-06

用途：供日常协作者读取现状、顺位、停止线和验证入口。历史事实按需进入[截至 2026-09-03 的归档](../records/status-through-2026-09-03.md)。

## 当前阶段

项目处于设计到受控实现阶段。首域为有键有限表的确定性纯转换；语义、Axiom IR / Evidence v0.1、四题基准、Agent 实验预注册及实现架构已有正式定义。主仓已实现 checker runtime 的基础组件，独立 Go checker 已形成受限 profile 的离线复核与 CLI；完整 `raxc` 生产管线、产品 checker runtime 和 Agent 收益尚未验收。

核心闭环与产品运行分别按[开发计划](../development-plan.md)验收；规划不替代 ADR 或执行授权。

## 能力与证据边界

| 领域 | 已形成 | 尚未形成 / 不代表 |
| --- | --- | --- |
| 规范与机器契约 | 语义、IR / Evidence、pipeline、execution profile、readiness 与 28 个指定态离线 bundle | 通用语言、完整生产管线、六平台真实执行 |
| 独立 Go checker | 独立解析、义务重建、状态 / support 检查、有限执行、反例与具体输出重放、结论重算、四态 codec、累计资源与唯一 CLI | 全语义支持、kernel / certificate 真值复核、counterexample minimality |
| Rust runtime core | policy / registration / selection、严格内外层 USTAR 与业务 manifest、receipt、result consumer、immutable spawn plan 与外层排他状态机 | 完整 installer / launcher；manifest 检查不含 provenance / acceptance 正文语义消费 |
| Darwin store | descriptor-relative containment、no-replace、full-sync、qualification / attempt 持久化、真实进程并发与 crash recovery | qualification 判定、物理断电保证、产品根安装 |
| 工具与 payload | Go macOS arm64 host/source、Rust macOS arm64 rustup component/source 局部验收；checker Darwin payload 不可变发布并登记 inactive | Rust standalone、cvc5 / Node、其他平台验收；active runtime 仍为 0 |
| 隔离 | ADR 0013 / 0014 接受逐次 signed App-Sandboxed Hypervisor runner；单主机 synthetic Linux microguest 可行性有动态观察 | 真实 checker / bundle、production runner / guest TCB、公共身份迁移、生产签名及 qualification |
| Agent 价值 | SQL / JSON / Axiom 三表示、两模型、四任务、72 个 trial bundle 的预注册 | execution lock、完整装置、正式模型调用与收益结论 |

分仓、发布与动态事实沿用既有记录，本次未重验；受限 checker profile 仍须遵循 [ADR 0009](../adr/0009-axiom-evidence-v0-drift-and-migration.md) 的 group 义务漂移与 Evidence v0.2 迁移边界。

历史锁定场景曾完成 20 个 `failed` 条目的动态检查；213 个 producer `proved` claim 分为 65 个 attestation-only 与 148 个材料不足的 kernel claim，独立证明数为 0。原 25 个结果层场景为 22 个 `accepted-with-trust`、2 个 `incomplete`、1 个 `rejected`，不代表生产证明能力。2026-09-05 静态审阅提出部分反例目标归因的待复现疑点，尚未据此判定历史结果失效；跨仓验收见[开发计划](../development-plan.md#独立-checker-语义验收与跨仓交接)。

精确工具为 Rust `1.97.1` / Rust 2024、Go `go1.26.7`、cvc5 `1.3.4`、Node.js `24.19.0`；逐项来源见[工具登记](../../contracts/toolchain-adapters-v0.1/README.md)和[payload 验收](../../contracts/toolchain-payload-acceptance-v0.1/README.md)。policy 为 `0.3` / `specified-not-implemented`；精确 payload 身份以[登记契约](../../contracts/checker-runtime-payloads-v0.1/README.md)及其 canonical record 为准。

## 近期顺位

Rust 工程门禁已完成本地与真实 CI 的成功 / 失败传播验收，见下文记录；普通 `dev` push 仍不自动触发 CI。下一顺位为：

1. **审阅资源 ADR 草案并闭合维护投入。** 项目所有者已确认另立虚拟执行 profile 的起草方向：[ADR 0015（Proposed）](../adr/0015-virtualized-checker-resource-profile.md)明确 guest 128 MiB 硬限、宿主总内存无等价硬保证、排他选择与迁移闭包。草案尚未替代 Accepted ADR，不能原地重解释 v0.1。[产品化依赖审阅](../checker-runtime-productization-dependency-review.md)中的维护负责人、预算和具体来源仍待确认或验收。
2. **补齐构建来源并审阅 archive 检查入口版本化。** [实际核验记录](../records/linux-6.18.49-source-review/README.md)已盘点固定 Debian 12 arm64 镜像的 413 个包条目，取得 Linux `6.18.49` 源包并完成压缩摘要匹配、未压缩 tar 的固定完整指纹签名核验；首次公钥缺 UID 导致的失败也已保留。镜像缺少 `flex` / `bison` / `bc`，Rust 为 `1.96.1`，尚不能作为候选 `1.97.1` init builder。下一步形成精确缺失依赖及来源清单，审阅 archive 检查入口版本化（旧入口摘要已绑定历史 acceptance），再完成源码文件 / 许可证库存与工具来源验收；当前不是完整 source lock。[来源与构建审阅](../checker-runtime-guest-source-build-review.md)继续约束 Rust init 建议与 Linux checker 交接。ADR 正式接受后提出公共迁移和可留存合成装置；构建、真实负载与 cold 矩阵另行授权。

[AX-B01 首切片依赖审阅](../axiom-pipeline-first-slice-dependency-review.md)已列出 P0–P9 前置；cvc5 / Node 自身的来源与外层硬限制仍需独立闭合。纯设计无需等待产品安装 / 激活，生产实现遵守 ADR 0007 全部入口或正式替代决策。

Checker 语义线先核实目标归因，再验收同域泛化、独立证明链和结果解释；不改变上述 runtime 前置。后续补规范负例、资源曲线和装置审计，工具与实现入口通过后锁定并另行授权 Agent 实验；语法、跨域、SDK / IDE、平台与商业扩张后置。

## 当前停止线与待决策

- 当前 Darwin Mach-O payload 保持 `registered-inactive`，`NativeIsolationStatus = RequiredNotProven`。不能重标为 Linux artifact，也不能从现行 native `CheckerSpawnPlan` 静默转为虚拟执行。
- 真实 fetch / install、payload 执行、产品绝对根、生产签名 / entitlement、qualification、激活、发布与远程写入仍分别验证、分别授权。历史记录中的授权不延续为新任务权限。
- 不采用 native best-effort、root broker、Virtualization URL 或 warm VM fallback；不自动放宽 memory / deadline。公共身份与资源含义无法闭合时保持阻断，按 ADR 0013 重新决策。
- 合成 guest 已验证的只是单主机可行性；原 probe source / binary 未保留，不能凭摘要宣称可独立复现。后续实验应先落实可留存输入与重跑入口。
- kernel / certificate 支持集合仍为空；attestation、结构验证、内容摘要、动态测试和独立 proof 分别报告。前置条件非空性、新义务与新实验指标是待设计项，不进入当前正式状态或评分规则。
- 首域语义、IR、Evidence、既有 ADR 和实验注册的摘要绑定原文不因阶段措辞而改写；语义 / 公共格式迁移单独审阅，Evidence v0.2 保留 ADR 0009 要求。
- 产品发布版本、公开 CLI / SDK、表面语法、安装路径、最低支持矩阵及 v1 后兼容承诺仍未冻结。不创建占位编译器骨架、自动发布或装饰性治理入口；已有 Rust 实现的工程门禁以实际 CI 验收为准。

## 验证入口与本次审阅

仓库级契约、生成一致性与文本检查：

```bash
./scripts/check-repo.sh
```

当前已验收的 macOS arm64 主机使用显式工具链，避免 `RUSTUP_TOOLCHAIN=1.96.0` 覆盖 pin：

```bash
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline
```

命令以工具和依赖已验收安装为前提，不授权下载；其他平台先确认精确工具与执行范围。

2026-09-06 本地通过 Rust 格式 / Clippy、61 项测试、YAML / shell 检查、125 种聚合状态、7 种 workflow 退化修改及真实失败测试的阻断验证；仓库门禁通过 969 个文件，diff 卫生通过。授权后的真实 CI 结果为：

| 提交与运行 | 实际平台 | 结果 |
| --- | --- | --- |
| `cf0be91` / [首跑](https://github.com/laugh0608/RadishAxiom/actions/runs/34030049866) | macOS 15.7.9；image `20260829.0321.1` | 工具准备、格式 / Clippy 通过；独占 rename 返回 `EINVAL`，core 为 50 通过、8 失败；Cargo 退出 101，聚合正确退出 1 |
| `e600e181cd15fc0675b6c9638a755f405f55dc54` / [验收运行](https://github.com/laugh0608/RadishAxiom/actions/runs/34030297501) | macOS 26.6.2 / `25G83`；image `20260831.0337.3` | 精确工具准备、格式 / Clippy、58 项 core 与 3 项 Darwin 测试均通过，无忽略项；三个组件和聚合全部成功 |

修正只调整 CI runner，未放宽 flags 或跳过测试。成功与失败传播记录共同完成工程回归入口验收，不代表最低系统矩阵、产品 qualification 或独立证明能力。未执行真实 checker、cvc5、Node、Hypervisor 或模型实验。工程门禁来源与边界见[仓库治理](../governance/repository-governance.md#rust-工程门禁)。

## 按需阅读

- [产品定义](../product-definition.md)、[开发目标与验收计划](../development-plan.md)
- [文档索引](../README.md)、[ADR 索引](../adr/README.md)、[机器契约索引](../../contracts/README.md)
- [协作与执行](../governance/agent-collaboration.md)、[仓库治理](../governance/repository-governance.md)
- [Darwin 强隔离审阅与历史观察](../checker-runtime-darwin-hard-isolation-review.md)
- [原状态与实施流水归档](../records/status-through-2026-09-03.md)
