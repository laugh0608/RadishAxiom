# RadishAxiom 当前状态

更新日期：2026-11-01（本次仅整理规划导航，技术事实沿用原记录）

用途：供日常协作者读取现状、顺位、停止线和验证入口。整体目标见[开发计划](../development-plan.md)，归属与任务来源见[能力专题地图](../topics.md)；历史流水见[整理前快照](../records/status-before-planning-alignment-2026-11-01.md)与[早期归档](../records/status-through-2026-09-03.md)。

## 当前阶段

项目处于设计到受控实现阶段，首域为有键有限表的确定性纯转换。核心能力与产品运行分别按[开发计划](../development-plan.md)验收；完整 `raxc` 管线、产品 runtime 与 Agent 收益尚未验收。

## 能力与证据边界

| 主线 | 已有基线与未关闭范围 | 任务 / 验收来源 |
| --- | --- | --- |
| 语义与 IR | P1 / P2 内部组件已有本机证据；不等于完整生产阶段或 Evidence v0.2 | [语义与义务来源](../topics.md#semantics-ir) |
| 验证管线 | 限定 P3、P4-A / B 与紧凑表示已有组件证据；真实 solver、完整 P0–P9 与四题闭环未验收 | [管线与反例来源](../topics.md#verification-pipeline) |
| Evidence / Checker | 格式、指定态制品与受限消费已有材料；生产声明、接受和独立证明分别判断 | [独立复核来源](../topics.md#independent-checker) |
| 运行交付 | F / C 及 L1 / L2 等已有本机或离线材料；L3 仍为方案，工具 / 宿主 / 实际执行资格未闭合 | [运行与交付来源](../topics.md#runtime-delivery) |
| 实验评估 | 三表示、两模型、四任务、72 个 trial bundle 已预注册；execution lock、完整装置、正式模型与收益未验收 | [实验来源](../topics.md#evaluation) |

分仓与动态结果沿用历史记录，本次未重验。历史 producer claim 的独立证明数为 0；反例目标归因的静态疑点仍待复现，不据此判定历史结果失效。跨仓交接见[开发计划](../development-plan.md#独立-checker-语义验收与跨仓交接)，group 义务版本边界见 [ADR 0009](../adr/0009-axiom-evidence-v0-drift-and-migration.md)。

工具 pin 为 Rust `1.97.1` / Rust 2024、Go `go1.26.7`、cvc5 `1.3.4`、Node.js `24.19.0`；身份和实际验收分别见[工具登记](../../contracts/toolchain-adapters-v0.1/README.md)、[payload 验收](../../contracts/toolchain-payload-acceptance-v0.1/README.md)。runtime policy `0.3` 仍为 `specified-not-implemented`，制品以[精确登记](../../contracts/checker-runtime-payloads-v0.1/README.md)为准。

## 近期顺位

核心语义优先，实际工作服务原容量 AX-B01 的有界 solver 校准；完整范围与退出标准按开发计划，来源准备不代替产品进展。原 P1 / P2 / query 顺位表已保留在[日期化快照](../records/status-before-planning-alignment-2026-11-01.md#下一步)。

### 下一步

直接后续见下文“接下来的事项”；各 P / E / F / C / G / L 切片的合同和验收从[地图](../topics.md)进入，不新增并行任务库。

### 当前接续（2026-11-01）

G0 以证据不足结束，真实接线仍未放行。L1 / L2 的源绑定、报告与管道 / 截止 / 回收源码已完成原范围本机或离线验证；当前仍为 50 源 v0.1 / offline-source-binding-only，工具输入 null、readiness=false。[L3](../query/solver-linux-channel-l3.md)已核定精确 target / 完整输入方案并重核已有原包，尚未实现 v0.2 / 包装器、安装 target 或构建 Linux 制品。详细序列与证据见[整理前快照](../records/status-before-planning-alignment-2026-11-01.md#当前接续2026-11-01)及[L3 记录](../records/2026-11-01-linux-channel-l3-review.md)。不从离线材料推导实际资格或执行授权。

### 历史日终交接（2026-10-27）

原文保留于[历史交接](../records/status-before-planning-alignment-2026-11-01.md#历史日终交接2026-10-27)，不覆盖下列当前顺位。

### 接下来的事项

恢复基线：C1 **500 / 500 文件、691,605,464 bytes** 已取得并独立复核；172 包内容、copyright 路径及 101 `.dsc` 关联已核对，历史三角色签名与五负例按明确接受的有限信任范围通过，旧失败保留，见[输入审阅](../records/2026-10-23-cvc5-c1-input-review.md)。20 个短时验签容器均已退出并删除，未安装、组装或执行 SDK / solver；验签宿主接受不能转用为构建资格。LibPoly [原草稿及发送接续](../records/2026-10-23-libpoly-upstream-clarification-draft.md)已发布，缺口仍待权威依据；C2 已交付离线配方、布局与事件检查，**C1 仍 not-accepted，build_ready=false**。

下一次恢复时，先围绕“让原容量 AX-B01 在原资源限制下取得真实 solver 校准”核对以下直接前置；每批只有明确出口，不将来源清单扩展为无期限的工具链研究。这里保存建议，不延续历史批次的外部动作授权。

1. **取得 LibPoly 固定版本的许可澄清后，再作 C1 接受审阅。** [历史核对](../records/2026-10-23-libpoly-license-history.md)已收敛为整体许可冲突、Polyxx 覆盖与旧 `open_memstream.c` 来源授权三项；[issue #113](https://github.com/SRI-CSL/libpoly/issues/113)已按 10 月 27 日明确授权发送。后续依据须适用固定提交并覆盖这些缺口；不重复查同一历史、下载已匹配材料或把风险接受写成许可事实。未安排自动轮询，不自动追加消息。
2. **L3 方案已核定，下一源码切片为 v0.2 纯输入 / 独立复核、native 捕获与有界包装器。** 按 [L3](../query/solver-linux-channel-l3.md)实施私有版本 / scope 迁移、sidecar 摘要绑定和实际 argv / 预算 / 取消拒绝测试；现行 50 源 v0.1 不能当完整 inputs，也不在原生入口 fallback。精确 target 旧原包已留存 / 重核，不重复下载；实际安装观察和特定工具 / 宿主 / 许可接受齐备前，不生成真实完整 root。组件安装、一次 Linux 构建、离线制品验收、交付挂载与执行分别授权；本轮不安装、不构建或创建 / 启动环境。保留实际 std / CRT / dylib / allocator / syscall、宿主权限 / proc / seccomp / bind、无写别名与独立终止 / 存储硬限，以及 C1 / G0 / E0 / E4 / solver 门禁。
3. **等待 C1 时，可继续 F2 的静态边界审阅。** 核对目标工具链、AArch64 汇编 / ABI、unsafe 与 FD 所有权，以及 outer setup policy、精确实例读回和 Mac adapter 接线；出口是具体问题修正或有限待验清单。既有本机 441 项测试不等于 Linux 目标构建 / 实际 syscall 验收；工具 / 制品条件具备并获准后再执行目标构建和真实负向矩阵。
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

原逐批测试、失败和环境记录保留于[验证快照](../records/status-before-planning-alignment-2026-11-01.md#验证入口与本次审阅)，本次规划整理的实际检查见[本批记录](../records/2026-11-01-planning-alignment.md)。不同日期的测试数不相加，不推断本批重跑过未改实现。

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
