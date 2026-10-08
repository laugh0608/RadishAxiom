# RadishAxiom 当前状态

更新日期：2026-10-08

用途：供日常协作者读取现状、顺位、停止线和验证入口。历史事实按需进入[截至 2026-09-03 的归档](../records/status-through-2026-09-03.md)。

## 当前阶段

项目处于设计到受控实现阶段，首域为有键有限表的确定性纯转换。核心能力与产品运行分别按[开发计划](../development-plan.md)验收；完整 `raxc` 管线、产品 runtime 与 Agent 收益尚未验收。

## 能力与证据边界

| 已形成 | 尚未形成 / 不代表 |
| --- | --- |
| 首域语义、IR / Evidence、pipeline / readiness 契约、28 个指定态 bundle | 真实生产管线、六平台执行 |
| P1 内部组件：v0.2 闭合结构 / 类型 / 图 / 契约、保守标签、完整规范文档 / strict / 身份；v0.1 既有子集及显式迁移，本机组件验收 | 完整 P1 生产阶段、Evidence / 管线集成、真实独立 checker 与六平台验收 |
| P2 内部组件：IR v0.2 的 ir-derived 全集、definition / ID / 规范字节、strict 完整性核对与预算拒绝，本机组件验收 | 完整 P2 生产阶段、实际 trust / concrete checks、Evidence v0.2 / query / 独立 checker 集成 |
| P3-A / B / C / D 内部组件：map / filter 的 numeric-range / contract-guarantee / totality / key-cardinality / row-coverage 真实查询、显式 profile、绑定 / strict / 预算拒绝，本机组件验收 | 其他义务与图操作、完整 P3、真实 solver / 模型 / proof、Evidence 与独立 checker 集成 |
| P3-E 内部组件：全部 P1 v0.2 纯构造的空效果规则记录、P2 绑定、strict / 预算拒绝与独立有限核对，本机组件验收 | 公共 kernel / certificate support、五态、field-origin、完整 P3 / P4 或独立 checker 证明 |
| P3-F 内部组件：五种节点 / 逐行表达式的来源、保守标签、控制与求值上下文记录，完整绑定 / strict / 预算及独立有限核对，本机组件验收 | 公共 field-origin prove support、非干扰或具体反例、完整 P3 / P4 与独立 checker 证明 |
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
| 2：P2 真实义务生成 | [ADR 0018](../adr/0018-ir-derived-obligation-profile.md) / [规则](../evidence/ir-derived-obligations-v0.2.md)已接受并完成本机内部组件验收；26 份 IR / 482 项定义与 29 份负例实际核对 | 只交付显式 ir-derived 全集；group 覆盖 / 守恒分开；保留完整 Evidence 门禁 |
| 3：query 与纵向闭环（下一步） | [ADR 0019](../adr/0019-map-filter-query-encoding.md)–[0022](../adr/0022-map-filter-row-coverage.md) 的 P3-A / B / C / D 已完成本机组件验收；[ADR 0023](../adr/0023-core-empty-effect-derivation.md) 的 P3-E 空效果结构组件也已完成本机验收；[ADR 0024](../adr/0024-core-field-origin-derivation.md) 的 P3-F 字段来源内部分析已实现，下一项审阅 P4-A 精确请求 / 响应 / 模型解码范围 | 完整 P3 未实现；保留 AX-B01 正确、两个 wrong、invalid、timeout 和篡改标准，外部执行独立授权 |

近期验收看真实输入能否产生规范输出与可定位拒绝，区分实现、指定态 fixture、独立复核与证明；不以提交数、测试数或来源包数量替代里程碑。每个切片结束复核下一项是否直接服务上述交付；新增前置必须解释具体依赖和停止条件。

### 日终交接（2026-10-05）

P1 `ed39e3b`、P2 `5142d70` 与 P3-A `2f4510c` 已提交并完成本机内部组件验收。P3-A 只支持 map / filter 的 numeric-range / contract-guarantee，不产生五态、证明或执行许可。全天提交、覆盖数字与代码 / 文档核对见[日终记录](../records/2026-10-05-closeout.md)；精确 API 与支持边界见 [IR 组件](../../crates/axiom-ir/README.md)。今晚到此收工。

### 当前接续（2026-10-08）

1. P3-E 已提交为 `47e3ff9`，P3-D 为 `a008520`，P3-C 为 `9b8f71f`，P3-B 为 `9f843ea`；当前 `dev` 领先 `origin/dev` 四个提交，未推送。P3-D 的双向全键关系与旧 query 兼容结果见[该批验收](../records/2026-10-08-p3d-validation.md)。
2. v0.4 对既有 26 份 IR / 482 项义务生成 151 查询，另有 1 资源拒绝、197 UnsupportedKind、107 UnsupportedFeature 与 26 check。结构记录不改变该 query 清单，AX-B01 每份候选仍只有九项可生成 query；不能据此声明完整验证。
3. P3-E 按 [ADR 0023](../adr/0023-core-empty-effect-derivation.md)完成 88 份记录 / 46 个规则与 28 类篡改、七类坏树拒绝，见[本机验收](../records/2026-10-08-p3e-validation.md)。它不提供公共 kernel support 或五态。
4. P3-F 已按接受的 [ADR 0024](../adr/0024-core-field-origin-derivation.md) / [正式规则](../query/core-field-origin-v0.1.md)实现：覆盖五种节点与逐行表达式，来源 / 标签 / 行控制 / 求值上下文分别推导，导出目标闭包；完整 P1 / P2 绑定、五项预算与 strict。130 份 IR / 758 份记录（含原 161 项 field-origin）覆盖 46 个规则；42 个手算区分例和 43 类篡改核对通过。82 份记录保留静态缺口，676 份无缺口，两者均不是证明或反例。源码、材料与文档未提交；[本批验收](../records/2026-10-08-p3f-validation.md)记录完整本机结果。
5. 下一步按[接续审阅](../query/field-origin-and-p4-interface-review.md)细化 P4-A 的请求 / 响应文法、模型解码与 world 表示，然后接受精确实施范围；P4-B 再处理五类具体目标重放。旧 cvc5 配置已有 dump-models，优先审阅保留 query 字节的对应关系；没有实际模型材料，不宣称后端已验收。单目标尝试与完整验证分开，两批均未自动获得实施或真实执行授权。
6. 来源规则不猜业务意图。wrong-drop-zero 忠实执行错误谓词时内建 coverage 可成立，业务保留要求由 guarantee 定位；此前[依赖审阅](../axiom-pipeline-first-slice-dependency-review.md)已校正文档归因，旧规范与锁定材料保持。

join / group 查询、聚合契约、双世界非干扰与 P4 / P7 / P9 分别审阅；真实 solver、跨仓 checker、新 Evidence 集成及外部执行继续保留各自门禁。本批不自动授权安装、启动、远程写入或正式实验。

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

- P1、限定 P2 与 P3-A / B / C / D / E / F 已完成本机组件验收；完整生产阶段尚未验收。P3 进一步扩展须明确目标范围；新 IR / P2 / query 不能配给旧 Evidence 结果，完整 Evidence v0.2 仍须按 ADR 0009 补齐。
- Darwin payload 保持 `registered-inactive`、`NativeIsolationStatus = RequiredNotProven`。不能重标为 Linux，也不能静默将 native spawn 转为虚拟执行。
- 产品隔离继续遵循 ADR 0013–0015；不启用 native best-effort、root broker、URL boot 或 warm VM fallback，不自动放宽 memory / deadline。
- 来源接受、fetch / install、payload 执行、公共迁移、生产签名、qualification、激活和远程写入仍分别处理；历史授权不延续。
- 规范、IR / Evidence、被绑定 ADR 与实验原文字节不因整理改动。新义务、非空性或公共格式须单独审阅，Evidence v0.2 保留 ADR 0009 要求。
- 表面语法、公开 CLI / SDK、安装路径与最低支持矩阵尚未冻结；测试、结构检查、attestation 与独立 proof 分别报告。

## 验证入口与本次审阅

2026-10-08，P3-F 新增 6 项 Rust 回归通过，workspace 共 247 项测试通过（runtime 56、Darwin store 3、digest 2、IR 186）；格式、Clippy 与仓库检查通过。旧规范、候选、锁定 bundle、runtime 与依赖字节保留，没有安装或升级依赖。

P3 具体 IR / SMT 比对属于有限动态检查，不是 solver 结果或形式证明；生产 strict 重建不能替代独立路径。P2 group 区分与角色表仍不是实际 role / checker 执行结果。

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

P3-F 本机验证见[本批验收](../records/2026-10-08-p3f-validation.md)，P3-E 见[前批验收](../records/2026-10-08-p3e-validation.md)，P3-D 见[前批记录](../records/2026-10-08-p3d-validation.md)，P3-C 见[前批验收](../records/2026-10-08-p3c-validation.md)，P3-B 见[历史验收](../records/2026-10-08-p3b-validation.md)，P3-A 历史见[10 月 5 日记录](../records/2026-10-05-closeout.md)；保留全部既有契约 / IR / P2 材料及旧入口隔离。CI 未触发，其他平台及真实 checker / cvc5 / Node 未执行。后续按[工程门禁](../governance/repository-governance.md#rust-工程门禁)验证，契约检查不能替代 Rust 测试。

## 按需阅读

- [产品定义](../product-definition.md)、[开发目标与验收计划](../development-plan.md)
- [文档索引](../README.md)、[ADR 索引](../adr/README.md)、[机器契约索引](../../contracts/README.md)
- [协作与执行](../governance/agent-collaboration.md)、[仓库治理](../governance/repository-governance.md)
- [Darwin 强隔离审阅与历史观察](../checker-runtime-darwin-hard-isolation-review.md)
- [原状态与实施流水归档](../records/status-through-2026-09-03.md)
