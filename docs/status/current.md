# RadishAxiom 当前状态

更新日期：2026-09-10

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

Rust 工程门禁已完成本地与真实 CI 的成功 / 失败传播验收；普通 `dev` push 仍不自动触发 CI。2026-09-06 的提交与核对结论见[日终回顾](../records/2026-09-06-closeout.md)。kernel / Debian 来源及 Rust Linux 输入均已有诊断留存，尚未形成完整 source lock、真实安装或构建验收。

### 当前推进事项（2026-09-10）

1. **资源与维护决策已收口。** [ADR 0015（Accepted）](../adr/0015-virtualized-checker-resource-profile.md)已确认 guest 128 MiB 硬限及宿主总内存无等价硬保证；8,000 行预警线、最多 10 人日和每周 4 小时投入已确认，项目所有者为 runtime 与 kernel / init 的唯一维护负责人。[详细责任与边界](../checker-runtime-productization-dependency-review.md#许可证与维护责任)已同步；公共迁移、来源及真实执行门禁继续有效。
2. **补齐剩余来源证据。** Rust / LLVM、固定 musl-cross-make 配方及 [musl 1.2.5 原包](../records/rust-linux-input-review/musl-source-2026-09-10.md)已有诊断，四份 patch 以 `fuzz=0` 应用成功；原包签名与公钥自认证的 SHA-1 仍被严格条件拒绝。Debian trixie 链已诊断通过，项目所有者已[确认仅限该原包的有条件信任方案](../records/rust-linux-input-review/musl-debian-auth-2026-09-10.md#项目所有者确认与执行顺位)。指纹页面、精确 keyring 包及[两份公钥 / archive 公告](../records/rust-linux-input-review/musl-key-status-2026-09-10.md)已取得，公钥与包内字节一致；公告不覆盖 stable release，未验证公告签名。下一步审阅来源明确的最小验证环境，再复核指定时点的签名 / 密钥状态并补持久材料。`acceptance = not-assessed`，不能据此安装。其他六项依赖、发布构建关联、宿主库 / loader / 符号版本、Rust 公钥策略、kernel 原始 tag 与最终链接继续待办。
3. **补齐安装执行前置。** [隔离安装切片审阅](../checker-runtime-linux-install-slice-review.md)已固定镜像、新前缀、精确三包 / 四 component、命令、权限、时限、日志与清理；要求核对旧 manifest 删除边界、两包间状态，并禁用 `ldconfig`。按分段方案核对实际模拟与两包间文件状态；来源前置满足后再申请安装，有限执行另列。完整 source lock、公共迁移、签名 / VM 和产品运行继续分别验收与授权。

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

2026-09-10：Rust GNU 14 个 ELF、255 份 Rust 文本、340 份 musl-cross-make 文件及 musl 原包 2,697 文件已有诊断；原包批次 8 项、Debian 链 9 项合成检查通过，签名拒绝及失败流水留存。完整 Sources / 原包链已复算，与留存 JSON 一致。后续两批分别取得页面 / keyring 包、两公钥 / 公告；首轮连接失败和重试 HTTP 200 均留存。两公钥 ASCII 与解码字节匹配包内文件及旧导出摘要，只读镜像身份仍一致；没有完成新密码学验签。公钥原文已留存仓库，Sources、原包、网页及 `.deb` 仍依赖缓存。本批未运行容器、Rust / CI、安装或构建。详见 [Debian 链与信任审阅](../records/rust-linux-input-review/musl-debian-auth-2026-09-10.md)、[页面 / 包补证](../records/rust-linux-input-review/musl-trust-inputs-2026-09-10.md)及[公钥 / 公告补证](../records/rust-linux-input-review/musl-key-status-2026-09-10.md)。

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

2026-09-06 的 Rust 本地 61 项测试与 CI 成功 / 失败传播已经验收；macOS 15 的 `EINVAL` 失败及 macOS 26.6.2 的成功运行均留在[日终记录](../records/2026-09-06-closeout.md#ci-与早前本地验证)。日终仓库门禁通过 1,034 个文件（含 source-tar / Debian 来源链的 27 项合成检查），另行通过库存 6 项与 Rust 输入诊断 8 项检查。日终未重跑 Rust、CI、真实归档核验、安装或产品执行；这些诊断不构成产品 qualification 或独立证明。工程门禁来源与边界见[仓库治理](../governance/repository-governance.md#rust-工程门禁)。

## 按需阅读

- [产品定义](../product-definition.md)、[开发目标与验收计划](../development-plan.md)
- [文档索引](../README.md)、[ADR 索引](../adr/README.md)、[机器契约索引](../../contracts/README.md)
- [协作与执行](../governance/agent-collaboration.md)、[仓库治理](../governance/repository-governance.md)
- [Darwin 强隔离审阅与历史观察](../checker-runtime-darwin-hard-isolation-review.md)
- [原状态与实施流水归档](../records/status-through-2026-09-03.md)
