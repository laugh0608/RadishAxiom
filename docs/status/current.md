# RadishAxiom 当前状态

更新日期：2026-09-29

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

Rust 工程门禁已完成本地与真实 CI 的成功 / 失败传播验收；普通 `dev` push 仍不自动触发 CI。kernel / Debian / Rust Linux 来源诊断尚未形成完整 source lock、真实安装或构建验收。

[ADR 0015（Accepted）](../adr/0015-virtualized-checker-resource-profile.md)确认 guest 128 MiB 硬限及宿主总内存无等价硬保证；8,000 行预警线、最多 10 人日和每周 4 小时投入已确认，项目所有者负责 runtime 与 kernel / init，详见[维护责任](../checker-runtime-productization-dependency-review.md#许可证与维护责任)。

### 下一步

以下承接 9 月 25 日日终顺位；9 月 29 日已完成 GMP 工具源码审阅、v3 编排及已授权的六步真实诊断，见[第三次实际记录](../records/rust-linux-input-review/gmp-verification-attempt3-2026-09-29.md)。此前提交与复核见[日终记录](../records/2026-09-25-closeout.md)。

已接受的限定范围：[musl 固定来源](../records/rust-linux-input-review/musl-source-acceptance-review-2026-09-16.md)、[MPFR 固定来源](../records/rust-linux-input-review/mpfr-source-acceptance-review-2026-09-25.md)、[MPC 限定 Debian 归档来源](../records/rust-linux-input-review/mpc-source-acceptance-review-2026-09-25.md)、[GMP 限定官方分发来源](../records/rust-linux-input-review/gmp-source-acceptance-review-2026-09-29.md)。MPFR / GMP 六项真实诊断已完成；MPC 上游作者签名仍未验证。GMP 仅接受固定字节在所持材料时点的官方 HTTPS 分发来源并附到期钥签名关系；钥匙仍已到期，历史有效性与全渠道撤销 / 最新性未建立。限定声明不转移给其他输入。

1. **补 headers 认证、制作过程与许可。** [固定包核对](../records/rust-linux-input-review/linux-headers-inputs-2026-09-25.md)的共有内容 / 链接及 AArch64 866 项投影一致。[9 月 29 日全文与制作过程审阅](../records/rust-linux-input-review/linux-headers-review-2026-09-29.md)已读回 38 路径 / 34 对象并重算旧盘点：866 项中 97 项无 SPDX 标记，另 11 项标记不含 syscall 例外字样；制作脚本额外依赖 `../linux`、打包未固定 tag，补丁版本链尚不完整。下一步已准备两个固定 GitHub ref / commit 元数据请求，待当前任务精确授权；没有执行请求或验签。原 kernel 导出、完整许可、实际安装和来源接受仍未闭合。
2. **保留 GCC / Binutils 阻断并补其他独立材料。** [GCC](../records/rust-linux-input-review/gcc-key-content-review-2026-09-25.md)目标子钥绑定及反向认证仍声明 SHA-1；[Binutils](../records/rust-linux-input-review/binutils-source-routes-2026-09-25.md)未取得强自认证，Debian 候选与精确配方整包不等价。均不启用弱摘要兼容、不替换版本 / 格式或忽略认证包。后续按[剩余路线](../records/rust-linux-input-review/musl-remaining-sources-2026-09-16.md)补发布构建关联、Rust 公钥 / 宿主库、kernel 原始 tag / 最终链接；完整 source lock 与[隔离安装](../checker-runtime-linux-install-slice-review.md)不得越过未闭合来源，改变信任规则或验收对象须单独审阅确认。
3. **核对备份转移与后续增量。** 9 月 16 日的 60.4 MiB 快照不含后续 MPC / MPFR / GCC / Binutils / GMP / headers 增量，后续各批已有独立本机留存。9 月 16 日日终检查时 Downloads 原三个交付文件不在原路径，项目内最终包摘要一致；9 月 29 日未重查位置，待核实目标副本并补增量，不声称异盘恢复已完成。见[日终材料状态](../records/2026-09-16-closeout.md#本机材料与外部影响)；备份转移不新增为密码学门槛。

以上是顺位，不是新下载、验签、安装或自动任务授权。历史各批请求 / 执行授权均已结束，精确事实留在各批记录；9 月 29 日四项获取与另行确认的第三次 GMP 诊断均已执行完毕，不延续为重复请求或新的运行权限。

[AX-B01 首切片依赖审阅](../axiom-pipeline-first-slice-dependency-review.md)已列 P0–P9 前置；cvc5 / Node 来源与外层硬限制仍需独立闭合。纯设计不必等待产品安装 / 激活，生产实现遵守 ADR 0007 全部入口或正式替代决策。

Checker 语义线先核实目标归因，再验收同域泛化、独立证明链和结果解释；不改变上述 runtime 前置。后续补规范负例、资源曲线和装置审计，入口通过后锁定并另行授权 Agent 实验；语法、跨域、SDK / IDE、平台与商业扩张后置。

## 当前停止线与待决策

- 当前 Darwin Mach-O payload 保持 `registered-inactive`，`NativeIsolationStatus = RequiredNotProven`。不能重标为 Linux artifact，也不能从现行 native `CheckerSpawnPlan` 静默转为虚拟执行。
- 真实 fetch / install、payload 执行、产品绝对根、生产签名 / entitlement、qualification、激活、发布与远程写入仍分别验证、分别授权。历史记录中的授权不延续为新任务权限。
- 不采用 native best-effort、root broker、Virtualization URL 或 warm VM fallback；不自动放宽 memory / deadline。公共身份与资源含义无法闭合时保持阻断，按 ADR 0013 重新决策。
- 合成 guest 已验证的只是单主机可行性；原 probe source / binary 未保留，不能凭摘要宣称可独立复现。后续实验应先落实可留存输入与重跑入口。
- kernel / certificate 支持集合仍为空；attestation、结构验证、内容摘要、动态测试和独立 proof 分别报告。前置条件非空性、新义务与新实验指标是待设计项，不进入当前正式状态或评分规则。
- 首域语义、IR、Evidence、既有 ADR 和实验注册的摘要绑定原文不因阶段措辞而改写；语义 / 公共格式迁移单独审阅，Evidence v0.2 保留 ADR 0009 要求。
- 产品发布版本、公开 CLI / SDK、表面语法、安装路径、最低支持矩阵及 v1 后兼容承诺仍未冻结。不创建占位编译器骨架、自动发布或装饰性治理入口；已有 Rust 实现的工程门禁以实际 CI 验收为准。

## 验证入口与本次审阅

2026-09-29 headers 本地审阅：GMP 来源决定已提交为 `84bd6f8`；随后完成全文声明盘点和制作脚本静态阅读，新增 11 项与既有相关检查合计 63 项通过。旧盘点重算一致，新报告重放逐字节一致，仓库与差异检查通过；诊断与待授权取证范围见[本轮记录](../records/rust-linux-input-review/linux-headers-review-2026-09-29.md)。没有新增下载、上游执行或来源接受。

2026-09-29 来源审阅：GMP v3 编排与六步结果已提交为 `0a55dcb`。本轮核对输入库 50 路径 / 40 对象与结果库 7 路径 / 7 对象，完整输入盘点、准备报告及六步重放均与原记录一致；项目所有者随后明确确认该精确原包的限定官方分发声明，已同步为接受；钥匙到期、历史有效性未建立及撤销缺口保持不变。来源 / 安装专题已同步实际结果，仓库检查通过；没有新增下载或真实工具执行。

2026-09-29：四项获取、源码 / 61 项补丁审阅及 v3 候选已提交为 `f3811cb`。v3 准备阶段 113 项检查通过，历史失败 / 候选报告重算一致；随后按另行授权完成六步真实 GnuPG 诊断、45 条日志重放和 7 对象留存恢复，v3 的 15 项检查复跑通过。仓库检查与 `git diff --check` 通过。未运行 Rust / CI 或产品构建，来源状态不变；详见[真实结果与边界](../records/rust-linux-input-review/gmp-verification-attempt3-2026-09-29.md)。

2026-09-25 日终：工作区诊断与失败重放已提交为 `14d12a8`。本轮对照今日代码同步来源 / 安装 / 产品化文档，MPFR 六步及 GMP 两次失败的离线导出重算均逐字节一致；各批实际测试与日终检查分别见[收尾记录](../records/2026-09-25-closeout.md#日终验证与交接)。今日 GMP 最新批次的 7 项合成检查、17 条日志重放及 8 对象留存恢复已通过，真实整批仍为失败；原包验签 / 负例未执行，来源未接受，headers 仍未认证。今晚仅文档收尾，无新增下载、容器、验签、安装或推送。

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
