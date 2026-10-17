# RadishAxiom 当前状态

更新日期：2026-10-17

用途：供日常协作者读取现状、顺位、停止线和验证入口。历史事实按需进入[截至 2026-09-03 的归档](../records/status-through-2026-09-03.md)。

## 当前阶段

项目处于设计到受控实现阶段，首域为有键有限表的确定性纯转换。核心能力与产品运行分别按[开发计划](../development-plan.md)验收；完整 `raxc` 管线、产品 runtime 与 Agent 收益尚未验收。

## 能力与证据边界

| 已形成 | 尚未形成 / 不代表 |
| --- | --- |
| 首域语义、IR / Evidence、pipeline / readiness 契约、28 个指定态 bundle | 真实生产管线、六平台执行 |
| P1 内部组件：v0.2 闭合结构 / 类型 / 图 / 契约、保守标签、完整规范文档 / strict / 身份；v0.1 既有子集及显式迁移，本机组件验收 | 完整 P1 生产阶段、Evidence / 管线集成、真实独立 checker 与六平台验收 |
| P2 内部组件：IR v0.2 的 ir-derived 全集、definition / ID / 规范字节、strict 完整性核对与预算拒绝，本机组件验收 | 完整 P2 生产阶段、实际 trust / concrete checks、Evidence v0.2 / query / 独立 checker 集成 |
| P3-A / B / C / D 内部组件：map / filter 五类真实查询；旧四版与 v0.5 紧凑 profile、规则绑定 / strict / 预算拒绝，本机组件验收 | 其他义务与图操作、完整 P3、真实 solver / 模型 / proof、Evidence 与独立 checker 集成 |
| P3-E 内部组件：全部 P1 v0.2 纯构造的空效果规则记录、P2 绑定、strict / 预算拒绝与独立有限核对，本机组件验收 | 公共 kernel / certificate support、五态、field-origin、完整 P3 / P4 或独立 checker 证明 |
| P3-F 内部组件：五种节点 / 逐行表达式的来源、保守标签、控制与求值上下文记录，完整绑定 / strict / 预算及独立有限核对，本机组件验收 | 公共 field-origin prove support、非干扰或具体反例、完整 P3 / P4 与独立 checker 证明 |
| P4-A 内部组件：新旧 profile 显式配对、请求规划 / 绑定 / 布局、合成协议与确定性世界候选；v0.5 原容量 AX-B01 落入 1 MiB，本机组件验收 | 真实 cvc5 校准 / 尝试、Evidence 与独立 checker；旧四版原容量请求仍受尺寸拒绝 |
| E1–E3 私有纯组件：模拟身份 / 计划 / 观察、控制与监督状态机、有界传输、具体 ABI 与离线 W / S 策略；本机模拟验收 | E0 工具接受、E3 宿主 / bootstrap 资格、真实 Docker adapter、镜像 / 探针 / solver 执行 |
| F1 私有纯组件：共享监督规则、增量摘要、闭合启动描述、Mac/S 双端声明与离线输入清单；本机纯组件验收 | 真实观察 / 认证捕获、完整 policy bundle、Linux 制品或工具 / 宿主接受 |
| F2 私有原生源码：类型化 syscall、FD 所有权、独立 B 尾段、S 准备 / 监督与 cgroup 原始观察 | 尚无可执行入口；本机脚本后端检查不等于目标汇编 / 链接审阅、真实 syscall 或 E0 / E4 资格 |
| P4-B 内部组件：直接 world / 绑定模型候选的 WF、全部 Pre 与五类精确目标重放，本机组件验收 | 真实 solver 尝试、完整 Evidence、独立 checker、普遍证明或反例最小性；新表示的实际求解资源尚未校准 |
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
| 3：query 与纵向闭环（下一步） | [ADR 0019](../adr/0019-map-filter-query-encoding.md)–[0022](../adr/0022-map-filter-row-coverage.md) 的 P3-A / B / C / D 已完成本机组件验收；[ADR 0023](../adr/0023-core-empty-effect-derivation.md) 的 P3-E 空效果结构组件也已完成本机验收；[ADR 0024](../adr/0024-core-field-origin-derivation.md) 的 P3-F 字段来源内部分析已实现；[ADR 0025（Accepted）](../adr/0025-p4-request-response-model-decoding.md) 的 P4-A 请求 / 响应 / 模型解码已完成本机组件验收；[ADR 0026（Accepted）](../adr/0026-p4-concrete-target-replay.md) 的 P4-B 有限具体目标重放已完成本机组件验收；AX-B01 紧凑表示已完成[本地研究验收](../records/2026-10-17-query-compaction-validation.md)；[ADR 0027（Accepted）](../adr/0027-compact-query-and-p4-binding.md)的 A–C 已完成[生产组件本机验收](../records/2026-10-17-compact-query-production-validation.md)，已完成[真实 solver 准备审阅](../records/2026-10-17-solver-preparation.md)，精确 CLI [补证](../records/2026-10-17-cvc5-cli-dependencies.md)和 E1–E2 [纯组件验收](../records/2026-10-17-solver-simulation-validation.md)已接续；E3 [D1–D3](../adr/0029-solver-linux-supervision-and-capabilities.md)已接受并提交，具体 ABI、内部传输及纯组件已完成[离线验收](../records/2026-10-17-solver-e3-components-validation.md)；真实 bootstrap / FFI [实施方案](../query/solver-bootstrap-ffi-implementation-plan.md)已形成；[ADR 0030（Accepted）](../adr/0030-solver-bootstrap-ffi-and-build-provenance.md) 的 D1–D3 已接受，F1 纯共享边界 / 启动描述已完成[本机验收](../records/2026-10-17-solver-f1-validation.md)，D3 [构建候选方案](../query/solver-cvc5-build-candidate-plan.md)已形成，E0 [后续补证](../records/2026-10-17-cvc5-provenance-followup.md)继续保留实际链接与来源关联缺口；未取得运行资格 | 完整 P3 / P4 未实现；保留 AX-B01 正确、两个 wrong、invalid、timeout 和篡改标准，外部执行独立授权 |

近期验收看真实输入能否产生规范输出与可定位拒绝，区分实现、指定态 fixture、独立复核与证明；不以提交数、测试数或来源包数量替代里程碑。每个切片结束复核下一项是否直接服务上述交付；新增前置必须解释具体依赖和停止条件。

### 日终交接（2026-10-08）

今日 P3-B–F 五笔实现已提交，最后一笔为 `e896341`；完整提交表、代码 / 文档核对和验收细节见[日终记录](../records/2026-10-08-closeout.md)。文档收尾另作本地提交，不推送；远端状态未刷新，最终提交号与工作区状态由交接消息报告。10 月 5 日记录作为[历史参考](../records/2026-10-05-closeout.md)保留。今晚到此收工。

v0.4 在既有 26 份 IR / 482 项义务中实际生成 151 查询；其余为 1 资源拒绝、197 UnsupportedKind、107 UnsupportedFeature 与 26 check。AX-B01 每份候选仍只有九项可生成 query。P3-E / F 增加内部结构记录，没有扩大 query 支持或公共 prove support；P3-F 的 758 份记录中 82 份有静态缺口、676 份无缺口，两者均不是证明或具体反例。

### 当前接续（2026-10-17）

AX-B01 [紧凑表示方案](../query/ax-b01-query-compaction-review.md)完成本地研究验收：保持原容量、旧四版字节与 1 MiB 上限，新研究表示的 72 条记录均为 265,107–962,850 字节。采用有类型公式恒等化简、共享、保序短名称与有界代入，没有改变关系编码或使用 WF 假设。12,553 次既有有限比较与 324 次原容量观察通过，见[测量与验收](../records/2026-10-17-query-compaction-validation.md)。

研究代码与材料已提交为 `f60d4c5`。[ADR 0027（Accepted）](../adr/0027-compact-query-and-p4-binding.md)、[query v0.5](../query/map-filter-query-v0.5.md)及 [P4-A v0.2](../query/p4-request-response-model-v0.2.md)已接受：新 artifact query0.3、查询规则摘要、独立 compact 预算与请求 v0.2；旧模型文法 / 候选格式不变。项目所有者已接受 D1 表示与版本、D2 预算与拒绝、D3 P4 接入与 Rust 实施范围；按 A–C 推进，由主代理主持验收，明确实现委派 gpt-6.1-sol / high。

Accepted 文档已提交为 `14a9693`。A–C 已完成 Rust 实现与本机验收：v0.5 / query0.3、新 solver profile / 请求 v0.2、七项 compact 预算与合成 P4-B 接续均已落地。原容量 27 个目标的新查询实际为 265,107–962,850 字节，全部保持 100 槽位与 501 个自由符号，最大余量 85,726 字节；790 条 corpus 记录的 12,553 次有限比较及 324 次原容量观察通过，见[生产验收](../records/2026-10-17-compact-query-production-validation.md)。

旧四版字节、原容量旧请求的尺寸拒绝和 1 MiB 上限保持；新字节可行不代表真实 solver、128 MiB / 6 s 资源可行、证明或完整 P4。实现与验收材料已提交为 `d055658`，未 push。

随后按项目所有者授权完成[solver 准备审阅](../records/2026-10-17-solver-preparation.md)：现有 OrbStack Linux arm64 Docker 宿主选为诊断候选，未取得运行资格；精确 cvc5 1.3.4 non-GPL static ZIP 已获取，摘要、包内路径和 CLI 静态 ELF 检查通过，完整依赖 / 许可证接受尚有缺口。[ADR 0028](../adr/0028-bounded-solver-calibration-entry.md)与[执行层设计](../query/solver-execution-preparation.md)已按 D1–D3 接受，限定最多八份校准加一次精确 wrong-add guarantee 尝试、显式 cgroup 内存范围和失败关闭路径。当前只完成准备，未安装或启动 solver、构建 / 启动容器或 VM、修改系统配置或远程状态。

项目所有者已接受 ADR 0028 三项决定，授权先提交准备材料，再推进精确 CLI 依赖 / 许可证补证与执行层实施清单；镜像构建、宿主负向探针和真实 solver 分别授权。已有 daemon 的能力报告不能代替 OS 限制、时限 / 清理和实际模型文法验证。

ADR 0028 与准备材料已提交为 `6593254`。随后完成[精确 CLI 补证](../records/2026-10-17-cvc5-cli-dependencies.md)：25 份来源材料、四项固定依赖配方、CaDiCaL / SymFPU / LibPoly 版本化许可及对应 arm64 发布作业已核对；发现 Editline / terminfo / glibc 链需补入库存。详细 CI 日志返回 403，实际系统库版本、完整链接清单及配方到 CLI 的认证关联仍未闭合，保持 not-accepted。已形成[执行层实施清单](../query/solver-execution-implementation-plan.md)：E1–E2 可作为后续纯组件切片，E0 工具接受及 E3 独立终止 / cgroup 能力是进入真实路径的硬门禁。本批补证和清单已提交为 `ff2e4ed`，没有编写真实 executor 或执行外部载荷。

随后按当前任务授权完成 E1–E2 [纯组件与模拟规则](../query/solver-diagnostic-simulation-v0.1.md)的实现及[本机验收](../records/2026-10-17-solver-simulation-validation.md)：新增私有 `solver-diagnostic-host`，所有身份、计划与观察固定 simulation；事件与流仅在内存处理。主代理主持设计与验收，明确实现委派 gpt-6.1-sol / high。原容量 wrong-add guarantee 以 962,642 字节 / 501 自由符号的请求贯穿合成捕获、原 P4 解码和 P4-B 精确目标重放；11 组导出由独立脚本核对。E0 / E3 保持硬门禁，没有真实接受、资格或认证捕获能力，也没有运行镜像、探针或 solver。实现及验收材料随后按项目所有者要求提交为 `a0150c6`。

本次继续 E3 设计收口，形成 [ADR 0029（Accepted）](../adr/0029-solver-linux-supervision-and-capabilities.md)、[监督设计](../query/solver-linux-supervision-design.md)和 [syscall 策略](../query/solver-linux-syscall-policy.md)：容器内 PID 1 监督器与唯一子进程共用原资源，READY / ARM 不续期，cgroup 只读观测与事后整树确认分层；发现仅匹配 execveat FD / AT_EMPTY_PATH 不能禁止绝对路径再次执行，新增 B6 装载门禁。具体信任增量和静态审阅见[本批记录](../records/2026-10-17-solver-e3-design-review.md)。项目所有者随后明确接受 D1–D3，并授权先提交本批设计，再推进具体 ABI、内部传输格式与离线纯组件 / 模拟测试。时钟误差界、内核 / runtime 能力与真实 syscall 适配均未取得资格；E0 和运行资格继续阻断真实路径。

Accepted E3 设计已提交为 `e2d36ce`。随后完成[具体 ABI](../query/solver-linux-abi-v0.1.md)、[内部封套](../query/solver-bootstrap-wire-v0.1.md)、[S 运行策略](../query/solver-supervisor-policy-v0.1.md)及[监督 / cgroup 模拟](../query/solver-supervisor-simulation-v0.1.md)。W / S 实际 cBPF bytes 经独立 Python 的 3,176 / 1,450 个有限案例核对；原容量 wrong-add 请求通过封套重组、完整模拟收束与原 P4-B 重放。详见[组件验收](../records/2026-10-17-solver-e3-components-validation.md)。本批实现与验收材料已提交为 `c489ec2`；没有创建真实 executor 或解除 E0 / 实际运行资格门禁。

随后按项目所有者授权形成[真实 bootstrap / FFI 方案](../query/solver-bootstrap-ffi-implementation-plan.md)与[独立实化审阅](../query/solver-bootstrap-ffi-review.md)：明确 listener 先交付后收紧、固定 FD / pipe 属性、Rust 启动与信号、Mac/S 分离、启动描述及 cgroup 退出过渡。新 [ADR 0030](../adr/0030-solver-bootstrap-ffi-and-build-provenance.md)已 Accepted；项目所有者明确接受 D1 原生宿主 / 共享 core、D2 真实绑定 / 观察、D3 可追溯构建候选方案，要求先提交本批方案与补证，再推进 F1 纯共享边界 / 启动描述及 D3 方案。E0 后续补证只补来源事实，不改变原 CLI 的 not-accepted；具体取得材料与验证见[本批记录](../records/2026-10-17-cvc5-provenance-followup.md)。本轮未实现可调用 FFI、改变依赖或生成 Linux 制品；整体方案审阅与验证见[验收记录](../records/2026-10-17-solver-bootstrap-plan-review.md)。

方案与补证已精确提交为 `f2ad466`。随后按当前授权完成 F1：新增私有纯 `solver-supervision-core`，提取 ABI / W/S 策略 / wire / cgroup 值解析；host 保留原接口与固定资源，模拟身份和观察继续隔离。闭合[启动描述](../query/solver-bootstrap-start-v0.1.md)、strict 请求规划、Mac/S 分离声明与截止计划、增量摘要和离线资源 / 策略输入已实现。原容量 query、旧封套与策略字节保持，实际回归及独立核对见[F1 验收](../records/2026-10-17-solver-f1-validation.md)。

F1 与 [D3 构建候选方案](../query/solver-cvc5-build-candidate-plan.md)已提交为 `1a7ff38`，F2 已提交为 `bf197ad`，C0 [SDK 元数据选择与验收](../records/2026-10-17-cvc5-c0-sdk-metadata.md)已按要求提交为 `c2ea5d0`，均未 push。F2 的[原生边界](../query/solver-bootstrap-native-boundary.md)与[监督实现](../query/solver-bootstrap-native-supervisor.md)仍只完成本机脚本后端检查。

项目所有者随后授权取得固定的五项源码归档及必要许可材料，继续完整源码、Production 配置和构建 patch 静态审阅。五项归档已取得并安全展开，四依赖摘要匹配固定配方；cvc5 的 7,066 个文件与已留存 Git tree 内容一致。完整源码揭示 CLI 的 `pyparsing` 和 GMP AArch64 汇编的 `m4` 需求，SDK 选择沿原快照补齐；配置与 patch 的结果、许可歧义及剩余条件见[本批验收](../records/2026-10-17-cvc5-c0-source-review.md)与[C0 专题](../query/solver-cvc5-c0-input-selection.md)。主代理主持设计与验收，具体工作委派 gpt-6.1-sol / high。`build_ready=false`；源码一致性不代表签名、包内容、许可或工具接受。没有下载 SDK 二进制包、安装、构建、运行探针 / solver、修改系统配置或 push；原容量、旧字节和资源限值保持。

### P4 接续（2026-10-13）

1. **P4-A 已提交并完成本机组件验收。** 提交为 `b86eb33`；[ADR 0025](../adr/0025-p4-request-response-model-decoding.md) / [规则](../query/p4-request-response-model-v0.1.md)的三个纯入口、完整绑定、模型子集、Text 类、世界候选与预算 / 拒绝通过本机验证，见[本批记录](../records/2026-10-12-p4a-validation.md)。该记录保留提交前事实，实际提交接续以本项为准。纯解析与候选解码不计作目标重放、真实尝试或证明。
2. **尺寸阻断已测量，保留原 query 与上限。** [尺寸审阅](../query/ax-b01-query-size-review.md)实际核对 72 份原容量查询为 42,577,698–65,831,615 字节；短名字、死定义移除和相同项共享的组合估算仍全部超过 1 MiB。新内部 adapter 保持 planned-not-calibrated，后续查询表示或资源 profile 分别审阅，不缩小容量、原地改字节或自动增限。unknown 可附模型但不解码 world，真实校准仍缺失。
3. **P4-B 已按接受范围完成本机组件验收。** [ADR 0026（Accepted）](../adr/0026-p4-concrete-target-replay.md) / [规则](../query/p4-concrete-target-replay-v0.1.md)落实为直接原 IR 求值、完整 WF / Pre、五类精确目标、来源绑定与 strict 观察。29,153 次既有有限目标观察及新增手算、深度、预算与篡改检查见[本批记录](../records/2026-10-13-p4b-validation.md)。AX-B01 原容量三个候选在同一有限输入上由 guarantee 区分，wrong-drop-zero 的内建 coverage 仍成立；直接 world 不声明来自 solver。
4. **保持单目标尝试与完整验证分开。** 真实 solver 校准 / 执行另须精确工具验收、adapter、执行宿主、硬资源限制和当前任务授权。join / group 查询、聚合契约、双世界非干扰、公共结构证明支持、完整 Evidence v0.2、跨仓 checker 与 P7 / P9 继续分别审阅。

上述查询表示审阅已由 2026-10-17 的本地研究、ADR 0027 接受及 A–C 生产组件验收接续；旧四版阻断保留，新 v0.5 的原容量字节门槛已通过。真实工具校准、资源变更与完整 Evidence 仍待各自决定，不自动启动 solver、安装依赖、写入远程或进入正式实验。

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
- ADR 0029 D1–D3 已 Accepted；E3 离线组件已验收。ADR 0030 D1–D3 已 Accepted；F1 / F2 与 C0 元数据批已提交。当前 C0 源码批只取得固定五归档并作静态配置 / patch / 许可审阅，SDK 包、签名信任、实际配置和输入接受仍未闭合；未授权安装、构建或真实运行。不得用 PID 1 / timerfd 的纸面方案宣称失联回收或 6 s 资格；也不得以 USER_NOTIF 检查不可信 pathname 后放行。真实路径继续受 E0、ABI 审查、实际运行资格和后续各项执行授权约束。
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

2026-10-17，E3 设计批次完成官方接口资料核对、有限时间握手算例与文档检查，见[设计审阅记录](../records/2026-10-17-solver-e3-design-review.md)。该设计批次未重跑 Rust workspace，也没有运行 Linux 探针、构建镜像或真实 solver。随后离线实现批次的实际验证见[组件验收](../records/2026-10-17-solver-e3-components-validation.md)。

2026-10-17，E1–E2 纯组件的本机验收、旧字节对照与独立模拟导出核对见[本批记录](../records/2026-10-17-solver-simulation-validation.md)。只检查模拟事实及其 P4 接续，不形成真实 solver、宿主资格或证明。

2026-10-17，真实 solver 准备批次完成只读宿主盘点、精确 ZIP 获取、标准库静态检查与合成负例；原包 / CLI 摘要、观察数据及可重跑入口见[准备记录](../records/2026-10-17-solver-preparation.md)。未运行任何真实 solver 或隔离探针，不外推工具 / 宿主接受。

同日精确 CLI 补证以标准库检查固定来源摘要 / Git blob、ELF sections 与配方 / CI 关联，并保留获取失败；结果与生成入口见[补证记录](../records/2026-10-17-cvc5-cli-dependencies.md)。本批不改变 Rust、依赖、旧规范或资源值，不将静态观察外推为运行验证。

2026-10-17，ADR 0027 的 A–C 实现通过格式、workspace Clippy 与完整 workspace 294 项测试，另一个默认 ignored 的旧产物导出测试单独执行通过；独立实际 Rust SMT 比较、18 份旧产物逐字节对照及仓库检查见[生产验收](../records/2026-10-17-compact-query-production-validation.md)。未启动 solver、其他平台、CI 或远程执行。

同日设计批次完成现有接口 / 版本 / 资源 / P4-B 来源路径审阅，仓库检查通过（2,620 文件）；规范随后 Accepted 并提交为 `14a9693`，实现绑定的规则正文保持该提交字节。

2026-10-17，紧凑表示研究脚本 22 项测试、72 条原容量记录 / 790 条四版语义记录的独立比较、精确 P4-B 回归、格式与 workspace Clippy 通过，详见[本批验收](../records/2026-10-17-query-compaction-validation.md)。本批没有重跑完整 workspace 测试、真实 solver、其他平台或 CI；该研究记录自身不代表生产 profile 接受或实现；后续状态以上述 ADR 0027 及生产验收为准。

2026-10-13，P4-B 新增 12 项 Rust 回归，完整 workspace 277 项测试、格式、Clippy 与仓库检查通过，见[本批验收](../records/2026-10-13-p4b-validation.md)。独立 Python 重建 29,153 次有限观察与完整见证；原容量 AX-B01、5,002 Record 类型、1,500 层故障依赖、13 类预算与篡改分别核对。本批没有真实 solver、其他平台、独立 checker、CI 或远程执行。

2026-10-12，P4-A 新增 18 项回归，workspace 共 265 项测试通过（runtime 56、Darwin store 3、digest 2、IR 204）；格式、Clippy、独立合成材料与仓库检查通过，见[本批验收](../records/2026-10-12-p4a-validation.md)。53 份既有合成 IR 的完整空世界与新复合 / 深度材料实际核对；AX-B01 三候选 / 四 profile 的 72 份 query 全部受 stdin 上限拒绝。真实 solver、其他平台、P4-B 与独立 checker 未运行，CI 未触发。

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
