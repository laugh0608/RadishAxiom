# RadishAxiom 当前状态

更新日期：2026-09-25

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

Rust 工程门禁已完成本地与真实 CI 的成功 / 失败传播验收；普通 `dev` push 仍不自动触发 CI。资源与维护决策已收口；kernel / Debian / Rust Linux 来源诊断尚未形成完整 source lock、真实安装或构建验收。此前批次交接见 [2026-09-16 日终回顾](../records/2026-09-16-closeout.md)；本批完成 [MPFR 六项真实离线验签](../records/rust-linux-input-review/mpfr-verification-entry-2026-09-25.md#本次授权与真实执行结果)，所有正负例符合预期，六个容器已清理；[固定原包来源审阅](../records/rust-linux-input-review/mpfr-source-acceptance-review-2026-09-25.md)已完成，项目所有者已确认限定声明，该精确原包的限定来源接受通过。

[ADR 0015（Accepted）](../adr/0015-virtualized-checker-resource-profile.md)确认 guest 128 MiB 硬限及宿主总内存无等价硬保证；8,000 行预警线、最多 10 人日和每周 4 小时投入已确认，项目所有者统一负责 runtime 与 kernel / init。细节以[维护责任](../checker-runtime-productization-dependency-review.md#许可证与维护责任)为准。

### 下一步

musl 两角色真实验签及[固定原包的限定来源验收](../records/rust-linux-input-review/musl-source-acceptance-review-2026-09-16.md)已完成，范围限于已确认工具 / 宿主与公钥材料时点。MPC / MPFR 原包、签名及公钥已取得并结构盘点；MPFR 已完成六项真实验签与限定来源接受；MPC 的[限定归档来源声明](../records/rust-linux-input-review/mpc-source-acceptance-review-2026-09-25.md)已获确认，上游作者签名仍未验证。早前材料事实见[原包核对](../records/rust-linux-input-review/mpc-mpfr-inputs-2026-09-16.md)和[公钥审阅](../records/rust-linux-input-review/mpc-mpfr-key-inputs-2026-09-16.md)。

1. **补齐 Binutils 强摘要自认证前置。** [固定 2.44 原包](../records/rust-linux-input-review/binutils-inputs-2026-09-25.md)及[公钥 / 内容盘点](../records/rust-linux-input-review/binutils-key-content-review-2026-09-25.md)已留存并离线重放：28,449 个文件完成逻辑库存，许可只完成选读；公钥完整指纹匹配签名声明，但 UID 自认证和子钥绑定均声明 SHA-1，尚未满足既有强摘要规则。下一步寻找同指纹更新材料及发布者绑定，再形成真实验签切片；没有运行 Binutils GnuPG 或接受其来源，不启用弱摘要兼容，不替换 `.gz`、`with-gold` 或相邻版本。随后依照[剩余路线](../records/rust-linux-input-review/musl-remaining-sources-2026-09-16.md)补 GCC / GMP / headers、发布构建关联、Rust 公钥与宿主库、kernel 原始 tag / 最终链接，再收口[隔离安装切片](../checker-runtime-linux-install-slice-review.md)。
2. **并行核对备份转移与增量。** 9 月 16 日交付的 60.4 MiB 固定快照包不含后续 MPC / MPFR 原包、公钥及本次 MPC 刷新材料；这些增量及本次 Binutils 原包、公钥与内容盘点已有独立本机留存。该日日终 Downloads 三个交付文件已不在原路径，项目内最终包摘要仍一致；待核实目标副本，再补后续增量，不据此声称异盘恢复已完成。详见[日终材料状态](../records/2026-09-16-closeout.md#本机材料与外部影响)。备份转移不新增为本地来源审阅的密码学门槛。

这些是后续顺位，不是自动任务或新的下载、执行、安装授权。MPC 三项公开材料、Binutils 原包批三项及后续公告 / 公钥批三项获取均已分别确认并完成，不延续为新取钥或密码学执行授权。9 月 25 日本次六项执行授权已完成，不延续为重复运行、安装或 MPC 的执行授权；MPFR 限定来源决定另见上述已确认审阅。

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

2026-09-25：准备阶段 **103 项**合成 / 回归检查通过；随后六项真实 GnuPG 诊断符合预期，六个容器均已删除，45 条命令及六项判定离线重放一致。新增导出方法 **7 项**合成检查通过；执行方法未修改，未重跑此前 103 项、Rust / CI 或产品构建。来源审阅轮另行重算导出与三份归档，身份页面指纹 / 链接匹配，没有重新执行密码学。另完成 MPC 三项有界 HTTPS 获取、18 路径增量恢复与既有 Debian 九项 / 66 条命令离线复核；公钥解析 9 项合成回归与仓库 1,187 文件检查通过，没有重跑 GnuPG。本次确认 MPC 限定来源，并完成 Binutils 三对象获取、原包摘要对应及从留存目录恢复复核，新增 5 项与复用 18 项回归及仓库 1,192 文件检查通过。后续 Binutils 公钥 / 内容批完成三项获取、38 路径增量恢复、库存及导出重放，26 项合成 / 回归及仓库 1,202 文件检查通过，未运行密码学。详情见[MPFR 记录](../records/rust-linux-input-review/mpfr-verification-entry-2026-09-25.md#本次授权与真实执行结果)；诊断尚未接入默认仓库门禁。此前 musl 限定验收与备份边界见[9 月 16 日日终记录](../records/2026-09-16-closeout.md#日终验证与交接)。

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

2026-09-06 的 Rust 本地 61 项测试与 CI 成功 / 失败传播属于[历史验收](../records/2026-09-06-closeout.md#ci-与早前本地验证)，本日未重验。工程门禁与独立诊断的范围见[仓库治理](../governance/repository-governance.md#rust-工程门禁)；测试与来源诊断不构成产品 qualification 或独立证明。

## 按需阅读

- [产品定义](../product-definition.md)、[开发目标与验收计划](../development-plan.md)
- [文档索引](../README.md)、[ADR 索引](../adr/README.md)、[机器契约索引](../../contracts/README.md)
- [协作与执行](../governance/agent-collaboration.md)、[仓库治理](../governance/repository-governance.md)
- [Darwin 强隔离审阅与历史观察](../checker-runtime-darwin-hard-isolation-review.md)
- [原状态与实施流水归档](../records/status-through-2026-09-03.md)
