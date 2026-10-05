# RadishAxiom 当前状态

更新日期：2026-10-05

用途：供日常协作者读取现状、顺位、停止线和验证入口。历史事实按需进入[截至 2026-09-03 的归档](../records/status-through-2026-09-03.md)。

## 当前阶段

项目处于设计到受控实现阶段，首域为有键有限表的确定性纯转换。核心能力与产品运行分别按[开发计划](../development-plan.md)验收；完整 `raxc` 管线、产品 runtime 与 Agent 收益尚未验收。

## 能力与证据边界

| 已形成 | 尚未形成 / 不代表 |
| --- | --- |
| 首域语义、IR / Evidence、pipeline / readiness 契约、28 个指定态 bundle | 真实生产管线、六平台执行 |
| P1 内部组件：v0.2 闭合结构 / 类型 / 图 / 契约、保守标签、完整规范文档 / strict / 身份；v0.1 既有子集及显式迁移，本机组件验收 | 完整 P1 生产阶段、Evidence / 管线集成、真实独立 checker 与六平台验收 |
| 独立 Go checker 的受限解析、义务重建、重放、结论与 CLI | 全语义、反例最小性；kernel / certificate 真值复核支持集合仍为空 |
| Rust runtime 的身份 / 选择、归档 / manifest、receipt、结果消费和 spawn plan；Darwin store 持久化与恢复 | 完整 installer / launcher、qualification、产品根安装、物理断电保证 |
| Darwin Go / Rust 部分工具验收，checker payload 不可变发布并登记 inactive | cvc5 / Node、完整 Linux 工具链及其他平台验收；active runtime 为 0 |
| ADR 0013–0015 与单主机合成 microguest 观察 | 真实负载、生产 runner / guest、公共身份迁移和签名；原 probe 未保留，不能宣称可重跑 |
| 三表示、两模型、四任务、72 个 trial bundle 预注册 | execution lock、完整实验装置、正式模型调用和收益结论 |

分仓与动态结果沿用历史记录，本次未重验。历史 producer claim 的独立证明数为 0；反例目标归因的静态疑点仍待复现，不据此判定历史结果失效。跨仓交接见[开发计划](../development-plan.md#独立-checker-语义验收与跨仓交接)，group 义务版本边界见 [ADR 0009](../adr/0009-axiom-evidence-v0-drift-and-migration.md)。

工具 pin 为 Rust `1.97.1` / Rust 2024、Go `go1.26.7`、cvc5 `1.3.4`、Node.js `24.19.0`；身份和实际验收分别见[工具登记](../../contracts/toolchain-adapters-v0.1/README.md)、[payload 验收](../../contracts/toolchain-payload-acceptance-v0.1/README.md)。runtime policy `0.3` 仍为 `specified-not-implemented`，制品以[精确登记](../../contracts/checker-runtime-payloads-v0.1/README.md)为准。

## 近期顺位

2026-09-29 按项目所有者要求调整为核心语义优先，依据见[阶段审阅记录](../records/2026-09-29-core-realignment.md)。现有来源取证与失败材料保留；完成取证不等于核心能力进展。

### 下一步

| 顺位 | 交付 | 完成或停止条件 |
| --- | --- | --- |
| 1：P1 真实语义组件 | [ADR 0016](../adr/0016-core-semantic-slice-entry.md) / [0017](../adr/0017-ir-v0.2-support-boundaries-and-migration.md)范围内已完成本机组件验收；[17 项矩阵](../ir/p1-support-boundary-review.md#必需验证矩阵对照)闭合结构、规范字节、身份与迁移回归 | 保留旧版未支持边界；不外推完整生产阶段、证明或跨平台验收 |
| 2：P2 真实义务生成（下一步） | 先审阅 ADR 0009 的生产义务 profile / 版本提案，明确新 IR 身份、group 覆盖 / 守恒、正负例与旧 Evidence 迁移，再取得接受后编码 | group 覆盖与守恒不得歧义；不读 expected outcome 驱动实现；版本阻断只作用于 P2 |
| 3：query 与纵向闭环 | P1–P2 后审阅 P3；明确 P4 / P7 / P9 与独立复核各自必要前置 | 沿用 AX-B01 正确、两个 wrong、invalid、timeout 和篡改验收；外部执行仍须独立授权 |

近期验收看真实输入能否产生规范输出与可定位拒绝，区分实现、指定态 fixture、独立复核与证明；不以提交数、测试数或来源包数量替代里程碑。每个切片结束复核下一项是否直接服务上述交付；新增前置必须解释具体依赖和停止条件。

### 当前切片与下一步（2026-10-05）

最近提交为 `986697e`（完整文档规范化 / strict / 文档身份）。后续不同范围 Int 有序比较、记录连接一致性修复，以及本轮 v0.2 规范 / 实现仍在工作区，尚未提交。项目所有者已接受四项版本边界，决定记录在 [ADR 0017](../adr/0017-ir-v0.2-support-boundaries-and-migration.md)。

[IR v0.2](../ir/axiom-ir-v0.2.md)与[新语义快照](../semantics/keyed-finite-table-semantics-v0.2.md)单独保存，旧规范与绑定字节保持不变。记录构造精确采用 name / expression，共用外层环境、检查全部字段并保留声明与实际标签；is_some 只作描述性简写；记录 eq / join 与复杂主键在 v0.2 明确拒绝。精确读取版本为 0.1 / 0.2，不能混用语义摘要或身份域。

[显式迁移](../ir/ir-v0.1-to-v0.2-migration.md)严格检查 v0.1 源，重算全部内容身份与引用，重新规范化并 strict 检查目标，返回工具 / 规则与两端身份记录。20 份源（含四题 12 候选）对照独立目标与每项映射，18 份导出负例定位预定拒绝边界；深记录 / 节点迁移及原始资源限制均已回归。独立期望和范围详见 [IR 组件](../../crates/axiom-ir/README.md)及[矩阵审阅](../ir/p1-support-boundary-review.md)。

本轮关闭的是 ADR 0016 / 0017 的 P1 内部组件本机范围；完整生产阶段、后端证明、独立 checker 和其他平台仍未验收。下一步进入 P2 的规范与 profile 设计审阅；本轮没有接受 Evidence v0.2、实现义务生成器或启动外部工具。来源取证与产品运行恢复条件不变。

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

- ADR 0016 / 0017 放行的 P1 内部组件已完成本机验收；完整生产阶段仍未验收。四项边界已在 v0.2 接受，不原地改写 v0.1。保守标签不等于非干扰；P2 编码须先接受明确义务 profile，新 IR 不能复用旧 Evidence 结果。
- Darwin payload 保持 `registered-inactive`、`NativeIsolationStatus = RequiredNotProven`。不能重标为 Linux，也不能静默将 native spawn 转为虚拟执行。
- 产品隔离继续遵循 ADR 0013–0015；不启用 native best-effort、root broker、URL boot 或 warm VM fallback，不自动放宽 memory / deadline。
- 来源接受、fetch / install、payload 执行、公共迁移、生产签名、qualification、激活和远程写入仍分别处理；历史授权不延续。
- 规范、IR / Evidence、被绑定 ADR 与实验原文字节不因整理改动。新义务、非空性或公共格式须单独审阅，Evidence v0.2 保留 ADR 0009 要求。
- 表面语法、公开 CLI / SDK、安装路径与最低支持矩阵尚未冻结；测试、结构检查、attestation 与独立 proof 分别报告。

## 验证入口与本次审阅

2026-10-05，在前轮 190 项回归基础上新增 12 项，覆盖 v0.2 记录类型 / 规范字节 / 标签 / 绑定、版本隔离、迁移和导出负例。20 份迁移对照含独立字节、文件 SHA-256、六类内容身份；旧候选不读取 expected outcome。5,000 层记录引用和 5,000 层节点链经真实 strict 源检查与迁移；42 层记录构造验证嵌套与预算。初次编译问题及修复见[审阅单](../ir/p1-support-boundary-review.md#验证与失败处理)。没有把类型、规范化或迁移结果写成公式 / 非干扰证明。宿主 Rust / Cargo `1.97.1`、`aarch64-apple-darwin` 已在本日核对，未下载或改变依赖；来源见[原验收记录](../checker-runtime-rust-first-slice-review.md)。

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

本轮实现已通过 workspace 格式、Clippy、202 项测试（runtime 56、Darwin store 3、digest 2、IR 141）；仓库检查包含类型、节点、契约、完整文档及 v0.2 兼容 / 负例独立向量的一致性检查。CI 未触发，其他平台及真实 checker / cvc5 / Node 未执行。后续按[工程门禁](../governance/repository-governance.md#rust-工程门禁)验证，契约检查不能替代 Rust 测试。

## 按需阅读

- [产品定义](../product-definition.md)、[开发目标与验收计划](../development-plan.md)
- [文档索引](../README.md)、[ADR 索引](../adr/README.md)、[机器契约索引](../../contracts/README.md)
- [协作与执行](../governance/agent-collaboration.md)、[仓库治理](../governance/repository-governance.md)
- [Darwin 强隔离审阅与历史观察](../checker-runtime-darwin-hard-isolation-review.md)
- [原状态与实施流水归档](../records/status-through-2026-09-03.md)
