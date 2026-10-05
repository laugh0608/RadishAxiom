# RadishAxiom 当前状态

更新日期：2026-10-05

用途：供日常协作者读取现状、顺位、停止线和验证入口。历史事实按需进入[截至 2026-09-03 的归档](../records/status-through-2026-09-03.md)。

## 当前阶段

项目处于设计到受控实现阶段，首域为有键有限表的确定性纯转换。核心能力与产品运行分别按[开发计划](../development-plan.md)验收；完整 `raxc` 管线、产品 runtime 与 Agent 收益尚未验收。

## 能力与证据边界

| 已形成 | 尚未形成 / 不代表 |
| --- | --- |
| 首域语义、IR / Evidence、pipeline / readiness 契约、28 个指定态 bundle | 真实生产管线、六平台执行 |
| P1 内部组件：有界 Unicode JSON、类型声明身份、受限逐行表达式类型 / 规范化、节点结构 / 局部类型、DAG / 输出引用、节点内容身份、保守字段 / 控制标签、契约类型 / 接口及契约内容身份 | 表达式支持边界收口、完整文档身份与 P1 效果验收；P1 尚未完成 |
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
| 1：P1 真实语义组件 | [ADR 0016 已接受](../adr/0016-core-semantic-slice-entry.md)；现有支持范围内的契约类型 / 接口、纯操作集合及契约规范化 / 身份已接入；下一步组合完整文档规范字节 / 身份入口，并收口表达式未支持项 | 节点 / 契约身份成功不构成完整 IR 验收；四题及同域新输入、语义负例与独立期望通过后才能称 P1 完成 |
| 2：P2 真实义务生成 | 先闭合 ADR 0009 的生产义务 profile / 版本入口，再从 IR 生成完整义务及 ID | group 覆盖与守恒不得歧义；不读 expected outcome 驱动实现；版本阻断只作用于 P2 |
| 3：query 与纵向闭环 | P1–P2 后审阅 P3；明确 P4 / P7 / P9 与独立复核各自必要前置 | 沿用 AX-B01 正确、两个 wrong、invalid、timeout 和篡改验收；外部执行仍须独立授权 |

近期验收看真实输入能否产生规范输出与可定位拒绝，区分实现、指定态 fixture、独立复核与证明；不以提交数、测试数或来源包数量替代里程碑。每个切片结束复核下一项是否直接服务上述交付；新增前置必须解释具体依赖和停止条件。

### 当前切片与下一步（2026-10-05）

契约类型与接口切片已提交为 `ef766e5`（此前标签与控制依赖为 `8271fee`）。后续接入 `contracts::normalize_contracts`：同一次解析先检查全部原始节点 / 契约，再规范节点与契约 definition 并核对内容 ID，保留原输入诊断位置。formula 复用布尔 / 相等 / 加法规范重写，noninterference 按名称排序；绑定、查找键顺序、角色和类型保持不变。类型 / 节点 / 契约身份均已核对也不构成完整文档或公式 / 非干扰证明，详见 [IR 组件](../../crates/axiom-ir/README.md)。

下一切片组合完整 canonical IR 字节、strict canonical 检查与文档身份，并明确未支持拒绝边界。`record.fields` / `is_some` 机器形式、不同范围 Int 比较兼容性仍未确认，记录相等和复杂主键投影仍未支持；须在完整 P1 前审阅收口。遇到规范歧义只停相应部分，不猜测格式或把 Unsupported 改写为非法 IR。保守标签与契约类型 / 身份检查均不代表公式成立或非干扰证明。来源取证与产品运行工作的恢复条件不变。

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

- ADR 0016 仅放行内部组件；节点 / 契约身份成功也不能标记为完整 IR 验收。表达式未支持形式与复杂键投影须在完整 P1 前收口；保守标签不等于非干扰；完整文档身份与完整 P1 效果验收尚未完成。P2 义务版本与完整管线门禁保留。
- Darwin payload 保持 `registered-inactive`、`NativeIsolationStatus = RequiredNotProven`。不能重标为 Linux，也不能静默将 native spawn 转为虚拟执行。
- 产品隔离继续遵循 ADR 0013–0015；不启用 native best-effort、root broker、URL boot 或 warm VM fallback，不自动放宽 memory / deadline。
- 来源接受、fetch / install、payload 执行、公共迁移、生产签名、qualification、激活和远程写入仍分别处理；历史授权不延续。
- 规范、IR / Evidence、被绑定 ADR 与实验原文字节不因整理改动。新义务、非空性或公共格式须单独审阅，Evidence v0.2 保留 ADR 0009 要求。
- 表面语法、公开 CLI / SDK、安装路径与最低支持矩阵尚未冻结；测试、结构检查、attestation 与独立 proof 分别报告。

## 验证入口与本次审阅

2026-10-05，本轮契约身份切片新增 9 项测试：11 项 Python 独立向量逐字节核对 definition / ID；四题 12 个候选的 21 条契约经真实规范化入口核对现有身份，pretty / JCS 结果一致，同题契约不受实现变化影响。同域负例覆盖摘要域 / NUL / 换行 / wrapper、绑定 / 查找键 / 角色保留、Unicode 名称、重复 ID / 接口、规范化前的坏子式及原始深宽预算。此前类型、节点与标签回归继续保留，向量和支持范围见 [IR 组件](../../crates/axiom-ir/README.md)。未核准完整 P1、公式真值或非干扰。宿主 Rust / Cargo `1.97.1`、`aarch64-apple-darwin` 已在本日核对，未下载或改变依赖；工具来源见[原验收记录](../checker-runtime-rust-first-slice-review.md)，历史材料边界见 [9 月 29 日日终回顾](../records/2026-09-29-closeout.md)。

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

本轮实现已通过 workspace 格式、Clippy、175 项测试（runtime 56、Darwin store 3、digest 2、IR 114）；仓库检查包含类型、节点与新增契约独立向量的一致性检查。CI 未触发，其他平台及真实 checker / cvc5 / Node 未执行。后续按[工程门禁](../governance/repository-governance.md#rust-工程门禁)验证，契约检查不能替代 Rust 测试。

## 按需阅读

- [产品定义](../product-definition.md)、[开发目标与验收计划](../development-plan.md)
- [文档索引](../README.md)、[ADR 索引](../adr/README.md)、[机器契约索引](../../contracts/README.md)
- [协作与执行](../governance/agent-collaboration.md)、[仓库治理](../governance/repository-governance.md)
- [Darwin 强隔离审阅与历史观察](../checker-runtime-darwin-hard-isolation-review.md)
- [原状态与实施流水归档](../records/status-through-2026-09-03.md)
