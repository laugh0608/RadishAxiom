# RadishAxiom 当前状态

更新日期：2026-11-07（AX-B01 P5 内部组件与 L3 精确输入有限接受审阅）

用途：供日常协作者读取现状、顺位、停止线和验证入口。整体目标见[开发计划](../development-plan.md)，归属与任务来源见[能力专题地图](../topics.md)；历史流水见[整理前快照](../records/status-before-planning-alignment-2026-11-01.md)与[早期归档](../records/status-through-2026-09-03.md)。

## 当前阶段

项目处于设计到受控实现阶段，首域为有键有限表的确定性纯转换。核心能力与产品运行分别按[开发计划](../development-plan.md)验收；完整 `raxc` 管线、产品 runtime 与 Agent 收益尚未验收。

## 能力与证据边界

| 主线 | 已有基线与未关闭范围 | 任务 / 验收来源 |
| --- | --- | --- |
| 语义与 IR | P1 / P2 内部组件已有本机证据；不等于完整生产阶段或 Evidence v0.2 | [语义与义务来源](../topics.md#semantics-ir) |
| 验证管线 | 限定 P3、P4-A / B、紧凑表示和 AX-B01 P5 内部检查已有组件证据；真实 solver、完整 P0–P9 与四题闭环未验收 | [管线与反例来源](../topics.md#verification-pipeline) |
| Evidence / Checker | 格式、指定态制品与受限消费已有材料；生产声明、接受和独立证明分别判断 | [独立复核来源](../topics.md#independent-checker) |
| 运行交付 | F / C 及 L1 / L2 等已有本机或离线材料；L3 完整输入 / 包装器源码已有静态与合成验证；工具 / 宿主 / 实际执行资格未闭合 | [运行与交付来源](../topics.md#runtime-delivery) |
| 实验评估 | 三表示、两模型、四任务、72 个 trial bundle 已预注册；execution lock、完整装置、正式模型与收益未验收 | [实验来源](../topics.md#evaluation) |

分仓与动态结果沿用历史记录，本次未重验。历史 producer claim 的独立证明数为 0；反例目标归因的静态疑点仍待复现，不据此判定历史结果失效。跨仓交接见[开发计划](../development-plan.md#独立-checker-语义验收与跨仓交接)，group 义务版本边界见 [ADR 0009](../adr/0009-axiom-evidence-v0-drift-and-migration.md)。

工具 pin 为 Rust `1.97.1` / Rust 2024、Go `go1.26.7`、cvc5 `1.3.4`、Node.js `24.19.0`；身份和实际验收分别见[工具登记](../../contracts/toolchain-adapters-v0.1/README.md)、[payload 验收](../../contracts/toolchain-payload-acceptance-v0.1/README.md)。runtime policy `0.3` 仍为 `specified-not-implemented`，制品以[精确登记](../../contracts/checker-runtime-payloads-v0.1/README.md)为准。

## 近期顺位

核心主线优先推进 AX-B01 首个纵向切片。P5 纯组件和有界 solver 校准按各自的前置推进，C1、L3 和宿主资格归入运行交付。完整范围与退出标准按[开发计划](../development-plan.md#里程碑与完成标准)。原 P1 / P2 / query 顺位表保留在[日期化快照](../records/status-before-planning-alignment-2026-11-01.md#下一步)。

### 下一步

AX-B01 的 P5 内部检查已按 [ADR 0032（Accepted）](../adr/0032-ax-b01-p5-component-entry.md)实现。IR v0.2 路径通过 `base` / `boundary` 的独立表值对照，并依据实际前置条件拒绝 `invalid` 的 `orders:OX`。核心线接续先审阅 IR v0.2 与宿主封套的版本配对及生产 `check-fixture` 的绑定，P6 继续受原门控约束。 [样本与组件核对记录](../records/2026-11-07-ax-b01-p5-entry-review.md)

运行线恢复条件见下文“接下来的事项”。`--no-poly` 可作为后续单独评估的校准候选，任何选型变化须重审配置、实际依赖和工具身份。各切片的契约和验收从[专题地图](../topics.md)进入。

### 当前接续（2026-11-07）

PR #5 已以 `7c9d14c` 合入 `master` 并快进回流 `dev`。L3 精确输入审阅以 **`not-accepted`** 收口。目标归档与 66 文件清单重核通过，两份 Cargo 解析数据与锁定项一致。宿主观察绑定了 Rust driver、Python / `ctypes`、Apple Git 选择链及系统身份。恢复前仍需补齐精确来源 / 许可与限定宿主信任，单次 target 安装继续阻断。F2 已核对 AArch64 调用约定和 FD 所有权交接，三项宿主单测通过，目标编译及真实 syscall 仍待验。 [审阅决定与原字节引用](../records/2026-11-07-linux-channel-l3-input-acceptance-review.md)

后续已核对两项 Rust 工具来源。本机 `rustup 1.29.0` 匹配官方 Darwin arm64 发布摘要，实际加载的 `librustc_driver` 与已接受的 Rust `1.97.1` Darwin 组件成员逐块相等。L3 总体保持 `not-accepted`。 [来源核对记录](../records/2026-11-07-linux-channel-l3-rust-source-readback.md)

本机 Python `3.14.5` 已对回 Astral `20260510` Darwin arm64 发布制品与完整构建清单。两份发布资产的构建证明已验证，`_ctypes` 链到 libffi `3.4.6` 的静态构建，许可原文和随包年份差异已留存。真实构建前仍需固定或重核实际启动文件和字节码。 [Python 来源核对](../records/2026-11-07-linux-channel-l3-python-source-readback.md)

已在包装器的精简环境观察到 `/usr/bin/git` 执行 Xcode 27.2（27B52）内的 Apple Git-157。Apple 签名、安装收据及 Git 的 GPL v2 随包声明均已核对。源码快照前后已接入选择器和文件摘要检查，覆盖合成漂移与实机 Command Line Tools 选择拒绝。精确 Apple 源码缺口和快照期间宿主稳定约束仍由有限宿主信任审阅处理。 [Apple Git 执行链核对](../records/2026-11-07-linux-channel-l3-apple-git-readback.md) · [包装器检查](../query/solver-linux-channel-l3.md#native-捕获与一次包装器)

### 当前接续（2026-11-01）

G0 以证据不足结束，真实接线仍未放行。L1 / L2 的源绑定、报告与管道 / 截止 / 回收源码已完成原范围本机或离线验证；[L3](../query/solver-linux-channel-l3.md)现已实现私有 v0.2 纯生成 / sidecar 独立复核、native 编译捕获与有界 build / argv recorder，并完成宿主静态 / 合成验证。保留的 v0.1 当前为 53 源；native 拒绝 v0.1 / null / 漂移。没有真实完整 root、target 安装、Linux 制品或环境资格。空 Cargo home 的 workspace 解析缺口已用既有两份索引数据的精确绑定补正，不引入新的 normal 编译依赖。实现已提交为 `bb9d963`；实际命令和边界见[实现记录](../records/2026-11-01-linux-channel-l3-implementation.md)，全天提交与本次文档复核见[日终记录](../records/2026-11-01-closeout.md)；不从离线材料推导实际资格或执行授权。

### 日终交接（2026-11-01）

今天完成控制面方案 / G0 结束决定、最小诊断通道、镜像与权限离线核对、PID 1、构建交付方案、L1 / L2 / L3 源码和规划导航；11 笔实现 / 方案提交逐项见[日终回顾](../records/2026-11-01-closeout.md)。最后源码批 `bb9d963` 的 119 项 Rust、27 项新增 Python、16 项既有 Python 与互操作结果均是限定宿主 / 合成验证，不累加成 Linux 或 solver 验收。日终只补文档、核对源绑定与仓库检查，不重跑无变更代码，也不继续开发或外部执行。

### 历史日终交接（2026-10-27）

原文保留于[历史交接](../records/status-before-planning-alignment-2026-11-01.md#历史日终交接2026-10-27)，不覆盖下列当前顺位。

### 接下来的事项

恢复基线：C1 **500 / 500 文件、691,605,464 bytes** 已取得并独立复核；172 包内容、copyright 路径及 101 `.dsc` 关联已核对，历史三角色签名与五负例按明确接受的有限信任范围通过，旧失败保留，见[输入审阅](../records/2026-10-23-cvc5-c1-input-review.md)。20 个短时验签容器均已退出并删除，未安装、组装或执行 SDK / solver；验签宿主接受不能转用为构建资格。LibPoly [原草稿及发送接续](../records/2026-10-23-libpoly-upstream-clarification-draft.md)已发布，缺口仍待权威依据；C2 已交付离线配方、布局与事件检查，**C1 仍 not-accepted，build_ready=false**。

以下顺位用于恢复现有候选的运行交付，目标是在原资源限制下完成原容量 AX-B01 的真实 solver 校准。每批须有明确出口，历史批次的外部动作授权不随计划延续。

1. **取得 LibPoly 固定版本的许可澄清后，再作 C1 接受审阅。** [历史核对](../records/2026-10-23-libpoly-license-history.md)已收敛为整体许可冲突、Polyxx 覆盖与旧 `open_memstream.c` 来源授权三项；[issue #113](https://github.com/SRI-CSL/libpoly/issues/113)已按 10 月 27 日明确授权发送。后续依据须适用固定提交并覆盖这些缺口；不重复查同一历史、下载已匹配材料或把风险接受写成许可事实。未安排自动轮询，不自动追加消息。
2. **L3 保持阻断，收口剩余输入审阅。** 复用已核对的 target 归档、Rust 工具、Python 构建和 Apple Git 实际执行链。恢复时核定 target 发布清单的有限信任范围、Apple Git 的精确源码缺口、Cargo 解析数据来源 / 许可及固定宿主信任。新增来源链或信任假设先核定范围。 [Apple Git 剩余边界](../records/2026-11-07-linux-channel-l3-apple-git-readback.md#漂移时如何阻断)

   若接受条件闭合，**再单独核定并授权一次 target 安装**：列明原归档 cache 新副本、120 s / 新增磁盘观测 512 MiB、唯一 target / 元数据写入和失败保留 / 清理边界；安装后双向核对 66 文件、原五个 component / 三工具及元数据差异。真实安装观察齐备后，绑定执行前最终干净 commit 的完整树与五份 sidecar / 外部 review pin，生成并独立复核真实 v0.2 root；不能用 53 源选定闭包替代全树或把 `bb9d963` 预填成尚未发生构建的来源。此后一次 600 s / 512 MiB Linux 构建、L4 离线制品验收、L5 交付 / 挂载 / 诊断执行分别授权；不因为输入机制已有源码就跳过安装观察 / 工具接受，或创建环境试错。旧原包不重下，合成 root / 回执和 source-only v0.1 均不充作真实输入。C1 / G0 / E0 / E4、实际 std / CRT / allocator / syscall、proc / seccomp / bind、无写别名、独立终止 / 存储硬限仍未闭合。
3. **等待 C1 时，F2 可按明确边界继续静态审阅。** AArch64 调用约定和 FD 所有权交接已完成本轮有限静态复核。后续待核对目标工具链、outer setup policy、精确实例读回和 Mac adapter 接线，出口为具体问题修正或有限待验清单。Linux 目标构建、实际 syscall 与真实负向矩阵在工具 / 制品条件具备并获准后分别验证。 [F2 本轮范围](../records/2026-11-07-linux-channel-l3-input-acceptance-review.md#f2-小范围静态审阅)
4. **条件闭合后按原顺序进入实际路径。** C1 与构建环境资格闭合后，按[C3–C5](../query/solver-cvc5-build-candidate-plan.md#批次占用授权与停止线)先构建依赖、审阅实际 ABI / Editline 有序闭包和 manifest，再配置 / 构建主目标；C4 决定 E0，实际 E4 通过后才进入 E5 的最多八份校准及一次精确 wrong-add guarantee 尝试。保持原容量、128 MiB / 6 s 和旧四版字节 / 拒绝，不因不足增限或绕过门禁；这仍不等于完整 P0–P9 / Evidence / 独立 checker 验收。

### 当前接续（2026-10-17）

原组件、工具准备与来源补证序列见[日期化快照](../records/status-before-planning-alignment-2026-11-01.md#当前接续2026-10-17)；旧授权不延续。

### P4 接续（2026-10-13）

原 P4-A / B 组件事实与未覆盖范围见[日期化快照](../records/status-before-planning-alignment-2026-11-01.md#p4-接续2026-10-13)，不替代真实工具与完整管线验收。

### 暂缓工作与恢复条件

| 工作 | 保留状态 | 恢复条件 |
| --- | --- | --- |
| headers / GCC / Binutils 等新增来源取证 | 原包、失败与本机留存不动；[来源状态表](../checker-runtime-guest-source-build-review.md#rust-配方剩余输入状态)继续报告未闭合部分 | 指定真实构建 / 执行目标确实需要该输入，先提交有投入上限及结束决定的精确补证范围，再取得必要授权 |
| guest / runner 产品化与公共迁移 | ADR 0013–0015 有效，Darwin payload 保持 inactive；来源、容量、签名和许可尚未完整验收 | 重核成本与维护能力，明确最小批次及实际负载验收，分别完成工具 / 公共迁移 / 外部执行前置 |
| 备份增量与转移 | 后续批次有本机留存，异盘恢复未确认，见[日终材料状态](../records/2026-09-16-closeout.md#本机材料与外部影响) | 作为独立恢复任务指定目标与范围，不作为 P1 开工前置，不删除原材料 |

musl / MPFR / MPC / GMP 的既有限定来源决定保留；headers 的 GitHub 元数据报告 unsigned 且无签名载荷，GCC / Binutils 强认证缺口继续阻断相应产品构建，不能由暂缓任务解释为已接受。

已确认的 8,000 行自有新增生产 TCB 预警线、最多 10 人日合成装置投入及每周 4 小时维护预算见[产品化责任](../checker-runtime-productization-dependency-review.md#许可证与维护责任)。没有实际工时账，不声称已超支或仍有足够余额；恢复前先说明实际投入、剩余估算和唯一负责人的承受能力。一次取证失败后保留结果并决定停止、改选或另立信任决策，不自动串接下一条来源链。

Checker 语义线的目标归因、同域泛化与独立证明链仍待独立验收；不因本仓优先级调整自动授权跨仓工作。正式 Agent 实验、表面语法、SDK / IDE 与平台扩张仍后置。

## 当前停止线与待决策

- ADR 0027 与 query v0.5 / P4-A v0.2 已 Accepted，A–C 已完成本机组件验收。保持原容量、旧 profile 字节及 1 MiB；不启动真实 solver，不 push。紧凑字节与有限比较不代表实际求解、运行资源资格或证明。
- ADR 0028 D1–D3 与执行层设计范围已 Accepted；E1–E2 已完成纯组件与模拟验收，真实适配与运行资格尚未闭合。cvc5 Linux arm64 ZIP 静态检查通过但未 accepted，OrbStack 宿主仅选为候选；完整依赖 / 许可证、固定加载与能力限制、128 MiB / 6 s 资格尚未闭合。准备授权不扩大为安装、构建镜像、容器探针、solver 执行或系统配置。
- ADR 0029 D1–D3 已 Accepted；E3 离线组件已验收。ADR 0030 D1–D3 已 Accepted；F1 / F2、C0 与后续 C1 / C2 离线改动已提交。SDK 原包 / 内容及限定历史签名已核对，LibPoly 许可、SDK / 构建宿主接受、实际配置 / 链接输入与运行资格仍未闭合。不得用布局或事件检查宣称 SDK 已组装，也不得用 PID 1 / timerfd 的纸面方案宣称失联回收或 6 s 资格；不能以 USER_NOTIF 检查不可信 pathname 后放行。真实路径继续受 E0、ABI 审查、实际资格及精确执行授权约束。
- 精确 CLI 补证保持系统库和实际构建输入缺口，不因固定配方、许可文本或 CI success 转为 accepted。日志 403 路径停止，不自动申请上游管理权限、联系发布者、换工具或展开全工具链取证；执行层按 E0–E6 清单分别收口。
- P1、限定 P2 与 P3-A / B / C / D / E / F 已完成本机组件验收；完整生产阶段尚未验收。P3 进一步扩展须明确目标范围；新 IR / P2 / query 不能配给旧 Evidence 结果，完整 Evidence v0.2 仍须按 ADR 0009 补齐。
- P4-A 按 ADR 0025 已完成本机组件验收；没有真实 cvc5 校准。纯 parser / 世界候选不认证响应来源，不产生 attempt、反例或 Evidence 五态；旧四版 AX-B01 stdin 尺寸拒绝保持，新 v0.5 已通过字节门槛。
- P4-B 的 `target-violated` 只表示 WF / 全部 Pre 成立的这一有限输入违反精确目标；`target-not-violated` 不是普遍证明。资源、绑定和格式错误不产生部分成功制品；本仓 strict 重建不等于独立 checker。
- Darwin payload 保持 `registered-inactive`、`NativeIsolationStatus = RequiredNotProven`。不能重标为 Linux，也不能静默将 native spawn 转为虚拟执行。
- 产品隔离继续遵循 ADR 0013–0015；不启用 native best-effort、root broker、URL boot 或 warm VM fallback，不自动放宽 memory / deadline。
- 来源接受、fetch / install、payload 执行、公共迁移、生产签名、qualification、激活和远程写入仍分别处理；历史授权不延续。
- 规范、IR / Evidence、被绑定 ADR 与实验原文字节不因整理改动。新义务、非空性或公共格式须单独审阅，Evidence v0.2 保留 ADR 0009 要求。
- 表面语法、公开 CLI / SDK、安装路径与最低支持矩阵尚未冻结；测试、结构检查、attestation 与独立 proof 分别报告。

## 验证入口与本次审阅

原逐批测试、失败和环境记录保留于[验证快照](../records/status-before-planning-alignment-2026-11-01.md#验证入口与本次审阅)，规划整理的实际检查见[原记录](../records/2026-11-01-planning-alignment.md)，L3 实现验证见[实现记录](../records/2026-11-01-linux-channel-l3-implementation.md)，本次日终复核见[日终记录](../records/2026-11-01-closeout.md)。不同日期的测试数不相加，不推断本批重跑过未改实现。

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

## 按需阅读

- [产品定义](../product-definition.md)、[开发目标与验收计划](../development-plan.md)
- [文档索引](../README.md)、[ADR 索引](../adr/README.md)、[机器契约索引](../../contracts/README.md)
- [协作与执行](../governance/agent-collaboration.md)、[仓库治理](../governance/repository-governance.md)
- [Darwin 强隔离审阅与历史观察](../checker-runtime-darwin-hard-isolation-review.md)
- [原状态与实施流水归档](../records/status-through-2026-09-03.md)
