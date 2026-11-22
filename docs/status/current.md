# RadishAxiom 当前状态

更新日期：2026-11-22（AX-B01 G0 无盘首启宿主部署与凭据复核）

用途：供日常协作者读取现状、顺位、停止线和验证入口。整体目标见[开发计划](../development-plan.md)，归属与任务来源见[能力专题地图](../topics.md)；历史流水见[整理前快照](../records/status-before-planning-alignment-2026-11-01.md)与[早期归档](../records/status-through-2026-09-03.md)。

## 当前阶段

项目处于设计到受控实现阶段，首域为有键有限表的确定性纯转换。核心能力与产品运行分别按[开发计划](../development-plan.md)验收；完整 `raxc` 管线、产品 runtime 与 Agent 收益尚未验收。

## 能力与证据边界

| 主线 | 已有基线与未关闭范围 | 任务 / 验收来源 |
| --- | --- | --- |
| 语义与 IR | P1 / P2 内部组件已有本机证据；不等于完整生产阶段或 Evidence v0.2 | [语义与义务来源](../topics.md#semantics-ir) |
| 验证管线 | 限定 P3、P4-A / B 与紧凑表示已有组件证据，AX-B01 P5 已完成限定本机生产接受。真实 solver、P6 和完整 P0–P9 仍待验收 | [管线与反例来源](../topics.md#verification-pipeline) |
| Evidence / Checker | v0.1 有受限离线消费。v0.2 已完成合成 AX-B01 的 P1 / P2、S1–S3、P4-A、五类 P4-B、attestation 历史与消费策略、结论聚合和三类结构化中止验收。真实结果的独立验收、M1 和公共读取待完成 | [独立复核来源](../topics.md#independent-checker) |
| 运行交付 | F / C 及 L1 / L2 等已有本机或离线材料；诊断启动器已完成 L3 构建和 L4 离线制品验收，G0 与 L5 运行前条件待取得 | [运行与交付来源](../topics.md#runtime-delivery) |
| 实验评估 | 三表示、两模型、四任务、72 个 trial bundle 已预注册；execution lock、完整装置、正式模型与收益未验收 | [实验来源](../topics.md#evaluation) |

独立 checker 的产品制品与动态基线沿用历史记录。M1 的旧包已完成源码级核验，独立证明数为 0。合成 AX-B01 v0.2 完整包的五类精确归因已有独立验收。旧 v0.1 与首题以外的一般归因仍待复核。跨仓交接见[开发计划](../development-plan.md#独立-checker-语义验收与跨仓交接)，group 义务版本边界见 [ADR 0009](../adr/0009-axiom-evidence-v0-drift-and-migration.md)。

工具 pin 为 Rust `1.97.1` / Rust 2024、Go `go1.26.7`、cvc5 `1.3.4`、Node.js `24.19.0`；身份和实际验收分别见[工具登记](../../contracts/toolchain-adapters-v0.1/README.md)、[payload 验收](../../contracts/toolchain-payload-acceptance-v0.1/README.md)。runtime policy `0.3` 仍为 `specified-not-implemented`，制品以[精确登记](../../contracts/checker-runtime-payloads-v0.1/README.md)为准。

## 近期顺位

2026-11-10 所有者确认：**下一交付固定为 AX-B01 的实际验证结果、完整 Evidence 支持与独立复核**，随后接通完整 P0–P9；不以运行准备或来源取证数量代替语义成果。两级出口见[开发计划](../development-plan.md#里程碑与完成标准)与[首切片依赖](../axiom-pipeline-first-slice-dependency-review.md#收口顺序与两级出口2026-11-10)。

| 顺位 | 必须继续 | 必要阻塞 / 结束条件 |
| --- | --- | --- |
| 1 | 合成 AX-B01 独立结果支持已验收 | 五类精确重放、历史 / 信任 / 结论及具名三类中止均已复核。实际 Evidence 仍须按同一摘要逐义务独立核对。 [验收记录](../records/2026-11-22-ax-b01-checker-and-solver-path-review.md#合成-ax-b01-独立复核) |
| 2 | 唯一待审候选 `cvc5 1.3.4 / USE_POLY=OFF` 的 C1 固定输入已限定接受 | 诊断启动器已完成 L3 和 L4，G0 的专用 Linux AArch64 虚拟机获准单独评审。启动材料、私有根及资格待核，L5 等待镜像接受和实际权限证据。 [C1 接受](../records/2026-11-22-cvc5-no-poly-c1-acceptance.md) · [G0 宿主决定](../records/2026-11-22-ax-b01-g0-linux-host-decision.md) |
| 3 | 实际受限校准，再取得 AX-B01 全部结果 | 保持原容量及 128 MiB / 6 s；按 E0、E4–E6 和具体授权取真实结果。九项后端结果与四项结构类义务支持齐备后装配，独立核对精确目标、信任与同一 Evidence 摘要 |
| 4 | P6–P9 与首个真实纵向闭环 | 提前登记 Node P7 的来源、宿主和硬资源缺口；P4/P5 真结果不足时 P6 继续 closed。correct 全链、两个 wrong、invalid、真实 timeout 与篡改/门控拒绝按原契约验收 |

后置：通用 guest/runner 产品化、安装/更新与额外平台，非当前实际构建所需的来源链，新领域/IR 扩展，表面语法、SDK/IDE 与正式 Agent 实验。首条独立正向证明单列研究成果，不额外阻塞允许 attestation 的首个流程；独立复核仍必需，accepted-with-trust 不等于独立 proof，certificate-required 对缺支持材料仍拒绝。

投入控制：下一运行准备批次前盘清实际投入与剩余估算，沿用既有装置/维护预算；当前没有工时账，不声称已超支或尚有余额。每批对应 AX-B01 的一项必需输入或一次路径决定。已选定一个待审替代候选。取得资格后进入受限校准。若无合格路径，记录决定人、具体缺项与恢复条件，暂停运行准备。九项实际后端结果与四项结构支持齐备后，交给 Checker 对同一份 Evidence 逐义务复核，再按既有条件评审 P6。失败不得自动追加取证链、提高资源上限、缩小声明容量或开放 native 旁路。路径仍不可行时暂停该运行线，可独立完成的契约收尾不继续扩张为新语义功能。

原 P1/P2/query 顺位见[历史快照](../records/status-before-planning-alignment-2026-11-01.md#下一步)。11 月 10 日规划确认不改变 ADR、IR/Evidence/fixture 原字节、候选接受或执行授权；下述记录提供证据与恢复入口。

### AX-B01 当前交付

AX-B01 的 P5 已有输入检查、宿主封套 v0.2 和同案公开回执。所有者已批准精确 Darwin arm64 release 制品及本机 macOS 27.0.1（26A434）宿主范围。受保护入口从仓库外独立受信配置读取接受摘要，实际七案通过独立规范字节重建、Schema 与 Rust 读回。本地 P5 工具为 `accepted`，P6 保持 `closed / p6-not-evaluated`。Evidence 和 P7 / P8 各自审阅。 [本机生产接受](../records/2026-11-07-ax-b01-p5-darwin-release-review.md#本机生产接受)

Evidence v0.2 已记录所有者对 S1 结构结果边界、S2 空效果独立重演及 P1 / P2 前提、S3 字段来源首批范围及充分条件的批准。最小公共结果支持、独立检查矩阵与 ADR 0009 迁移演练方案待审。S1–S3 覆盖 AX-B01 的四项核心义务，完整迁移仍需要其余义务的实际结果及独立检查。 [义务与结果契约审阅](../evidence/ax-b01-evidence-v0.2-contract-review.md) · [汇总审阅](../evidence/evidence-v0.2-minimal-support-review.md)

verification 机器契约已有本仓 Rust 严格读回与 S1–S3 结果绑定，使用实际 IR 重建 P2 全集，并复用 P1、P3-E / F 重建。合成完整文档的字节与独立 Python 向量一致，缺义务的 AX-B01 部分材料被拒绝。公共读取仍须审定机器契约并完成 ADR 0009 的完整迁移演练和独立检查。 [机器契约及本仓读回](../evidence/evidence-v0.2-machine-contract/README.md)

ADR 0009 的 M1 已使用主仓 `CHK-PROOF-02` 精确源包复跑 Go checker 源码级严格检查，在旧策略下得到 `accepted-with-trust`。具名 IR 迁移重建了 13 项核心义务。S1–S3 已复跑本仓组件，九项后端目标已重生成精确查询与离线请求。缺合格的实际执行及新结果支持，目标 Evidence 装配停在迁移准备。 [M1 原件、逐项对照与阻断记录](../records/2026-11-07-ax-b01-evidence-m1-preflight.md)

九项后端结果与信任已有审阅稿和机器绑定候选，覆盖来源封套、attestation、精确反例与未决原因。离线投影使用既有 P4 合成导出，复核 12 份投影及 20 项拒绝用例。 [后端结果与信任审阅](../evidence/ax-b01-evidence-v0.2-backend-support-review.md) · [后端机器绑定候选](../evidence/evidence-v0.2-machine-contract/README.md#后端绑定候选)

11 月 13 日所有者已确认 [D1–D5 候选实施范围](../evidence/ax-b01-evidence-v0.2-backend-support-review.md#所有者确认的实施决定2026-11-13)。重放工具四类漏拒绝已修复；本仓新增外部固定批次 pin、全部运行信任、模式专属中止与历史聚合，完整合成 AX-B01 的 13 项核心义务和九项后端结果可严格读回。五类目标由 Python 有限语义另行核对；真实 solver、独立产品 checker、公共新字节接受及完整 M1 尚未完成，P6 仍关闭。来源事实与验证边界见[实施记录](../records/2026-11-13-evidence-backend-implementation.md)，修复前观察保留于[审查记录](../records/2026-11-13-evidence-backend-review.md)。

当天两仓提交与代码、文档对照见[11 月 14 日日终回顾](../records/2026-11-14-closeout.md)。

C1–C6 的[独立交换审阅](../evidence/evidence-v0.2-independent-check-review.md)已物化新 request / manifest / result、来源 pin、结构化中止及合成验收材料，旧 Evidence 与机器基线保持原字节。新包只标记 simulation；没有改写旧 runtime consumer、独立 checker 制品或公共门禁。复核与实际验证见[交换草案实施记录](../records/2026-11-13-evidence-exchange-review.md)。

11 月 14 日完成 R1–R6 本仓候选及复审。新 Rust 入口显式选择 batch / interruption v0.2，从类型化错误生成结构化事实、终态原因码与生产策略，保留旧入口和原指纹。合成验证覆盖 model／replay 资源中止、无效模型、终态及输入错绑和历史信任。真实来源、公共接受与完整迁移仍待验收。 [适配与复审记录](../records/2026-11-14-evidence-structured-backend.md)

分仓 `091c6163bb429ce201f7284797cdafc67e9ce47a` 完成首批合成交换验收。分仓 `ec3eb6fe7bee30a39030c9d6d27da7c72eb821d6` 独立核验 AX-B01 的 P1 / P2 共 13 项核心义务，拒绝错误的覆盖归因及同目标冲突。十个原生包中，缺历史运行信任与同目标冲突两包为 `rejected`，其余八包为 `incomplete`。该批重放使用绑定的具体世界。 [交换及语义验收记录](../records/2026-11-14-evidence-checker-v0.2-exchange.md)

分仓 `92960b77838b602135101164b63c7f2ac849da7c` 已独立从原始合成 SAT 重建符号来源、输入布局及规范世界。调用方提供充足 checker 预算时，三套 AX-B01 的 27 份 world 与 Text 等价类逐字节匹配；错绑拒绝，预算耗尽保留 `incomplete`。原交接请求保留原字节。 [P4-A 复审与预算断点](../records/2026-11-14-evidence-checker-v0.2-exchange.md#第三批合成-p4-a-独立解码复审)

分仓 `1d8a5d384fc15915e9a5af9a1006831696c348a4` 已独立复核三套合成 AX-B01 的 S1 结构判定、S2 空效果推导以及 S3 两项字段来源，共 12 项支持。范围为合法 subject 与公开标量片段。旧 v0.1 反例、一般构造及 rejected-ir 的独立失败重演仍按各自范围验收。 [S1–S3 验收记录](../records/2026-11-14-evidence-checker-v0.2-exchange.md#第四批合成-s1s3-独立支持)

分仓本地 `51d0a51` 与 `e4ff16f` 完成 P4-B 精确重放，以及 attestation 历史、消费侧信任策略、结论聚合与三类结构化中止的合成验收。14 个固定原包、32 个对照回执完成核对。十个原生交接包为 7 个 `accepted-with-trust`、2 个 `rejected`、1 个 `incomplete`。最后一包 `model-invalid` 在充足 Checker 请求预算下完成九条原因复核。真实 solver、产品 payload 接受和公共迁移继续按各自门禁处理。 [11 月 22 日交接与裁决](../records/2026-11-22-ax-b01-checker-and-solver-path-review.md)

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

<a id="下一步"></a>

### 接下来的事项

#### AX-B01 Evidence v0.2

**资格和实际结果齐备后恢复 M1。** AX-B01 correct 九项后端实际执行须覆盖相应制品、宿主和目标。以实际结果和 trust 装配全部 13 项核心义务，取得绑定新 Evidence 原始与文档域摘要的独立结果。再按 ADR 0009 补 M2 group 与 M3 旧历史的迁移、版本拒绝矩阵，进入公共读取审阅。P6 保持 `closed / p6-not-evaluated`。 [M1 阻断与恢复](../records/2026-11-07-ax-b01-evidence-m1-preflight.md#阻断与恢复顺序) · [ADR 0009](../adr/0009-axiom-evidence-v0-drift-and-migration.md)

#### Solver 与运行交付

共用证据基线：**500 / 500 文件、691,605,464 bytes** 已取得并独立复核。172 包内容、copyright 路径及 101 `.dsc` 关联已核对。历史三角色签名与五负例按有限信任范围通过，旧失败保留。20 个短时验签容器均已退出并删除，验签宿主的限定接受仅适用于该验签批次。C2 已交付离线配方、布局与事件检查，`build_ready=false`。原启用 Poly 候选的 C1 仍为 `not-accepted`。 [SDK 输入审阅](../records/2026-10-23-cvc5-c1-input-review.md) · [LibPoly 剩余许可缺口](../records/2026-10-23-libpoly-upstream-clarification-draft.md)

唯一待审路线为固定版本 cvc5 `1.3.4`、Linux AArch64 glibc Production 静态 CLI、`USE_POLY=OFF`。固定输入及其许可范围已获 C1 限定接受，用于本地诊断。实际构建等待 L3/G0 资格与单独授权；E0/E4/E5/E6 继续按序。 [C1 接受记录](../records/2026-11-22-cvc5-no-poly-c1-acceptance.md) · [候选离线入口](../query/solver-cvc5-no-poly-offline.md)

1. **原启用 Poly 的候选保留暂停。** 若未来重新审议该候选，须取得 LibPoly 固定版本的许可澄清后再作 C1 接受审阅。 [历史核对](../records/2026-10-23-libpoly-license-history.md)已收敛为整体许可冲突、Polyxx 覆盖与旧 `open_memstream.c` 来源授权三项；[issue #113](https://github.com/SRI-CSL/libpoly/issues/113)已按 10 月 27 日明确授权发送。后续依据须适用固定提交并覆盖这些缺口；不重复查同一历史、下载已匹配材料或把风险接受写成许可事实。未安排自动轮询，不自动追加消息。
2. **L3 构建与 L4 离线制品验收完成。** `cf49e07` 的真实 v0.2 root、五份 sidecar 和外部摘要通过独立复核。单次包装器退出 0，快照前后两次通过 `xcrun` 守卫，四个编译单元及链接完成，观测峰值 120,829,772 bytes。ELF 为 6,263,080 bytes，SHA-256 `a888541af00efe30f85ef4222f2914266d864d156045fc28dde90b45caaccbcc`。两轮失败回执和日志保留于本机忽略的 `.tmp/linux-channel-build-l3-01/records/` 和 `.tmp/linux-channel-build-l3-02/records/`。 [输入限定信任](../records/2026-11-22-linux-channel-l3-limited-trust.md)

   L4 核对了静态 AArch64 ELF、内嵌 root / 正文、启动与失败分支、329 个归档成员及对应许可材料。三个编译器临时对象沿用实测 argv、链接 trace 与 map 或抽取关系的关联，原始对象字节未留存。单文件 `runtime/` 与 `records/l4-acceptance.json` 位于本机忽略的 `.tmp/linux-channel-delivery/<ELF-SHA-256>/`。 [交付边界](../query/solver-linux-channel-build-and-delivery-plan.md#交付一个只读-runtime-目录)

   AX-B01 专用 Linux AArch64 虚拟机的首启配置对象已通过离线校验。`_raxcg0`、同名组（UID/GID `850`）、受保护目录及三个固定制品已部署。实际身份的路径、ACL、制品摘要和签名复核通过，普通开发身份七项写入均被拒绝。Darwin 进程仍带入四个额外组，原启动器的 `--preflight-paths` 拒绝执行。须固定满足原守卫的执行方式并通过完整预检，才评审一次实际首启。G0 维持 `evidence-insufficient-stop-before-wiring`，块与 inode 硬限、写别名和独立终止仍待真实资格。 [G0 宿主决定](../records/2026-11-22-ax-b01-g0-linux-host-decision.md) · [Alpine 发布验签](../records/2026-11-22-ax-b01-g0-alpine-release-signatures.md) · [无盘首启制品与离线复核](../records/2026-11-22-ax-b01-g0-diskless-first-boot.md) · [宿主部署与凭据复核](../records/2026-11-22-ax-b01-g0-diskless-host-deployment.md)

   L5 已复核本机固定 Alpine 镜像、L4 交付、BusyBox 入口，并复现 APK 唯一摘要差异的上游成像步骤。镜像仍为 `not-accepted`，实际权限、proc / seccomp / bind、单次诊断参数与清理范围待核定。实际执行、C3 / E0 / E4 仍按现有门禁分别授权。 [L5 运行前复核](../records/2026-11-22-linux-channel-g0-l5-preflight.md)
3. **F2 按实际依赖复用已有静态清单。** AArch64 调用约定和 FD 所有权交接已完成本轮有限静态复核。后续待核对目标工具链、outer setup policy、精确实例读回和 Mac adapter 接线，出口为具体问题修正或有限待验清单。Linux 目标构建、实际 syscall 与真实负向矩阵在工具 / 制品条件具备并获准后分别验证。 [F2 本轮范围](../records/2026-11-07-linux-channel-l3-input-acceptance-review.md#f2-小范围静态审阅)
4. **条件闭合后按原顺序进入实际路径。** C1 与构建环境资格闭合后，按[C3–C5](../query/solver-cvc5-build-candidate-plan.md#批次占用授权与停止线)先构建依赖、审阅实际 ABI / Editline 有序闭包和 manifest，再配置 / 构建主目标；C4 决定 E0，实际 E4 通过后才进入 E5 的最多八份校准，随后单独评审 E6 的一次精确 wrong-add guarantee 尝试。保持原容量、128 MiB / 6 s 和旧四版字节 / 拒绝，不因不足增限或绕过门禁；这仍不等于完整 P0–P9 / Evidence / 独立 checker 验收。

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
- ADR 0029 D1–D3 已 Accepted；E3 离线组件已验收。ADR 0030 D1–D3 已 Accepted；F1 / F2、C0 与后续 C1 / C2 离线改动已提交。无 Poly 候选的 C1 固定输入已限定接受，原 Poly 候选的 LibPoly 许可、两条路径的构建宿主、实际配置 / 链接输入与运行资格仍未闭合。不得用布局或事件检查宣称 SDK 已组装，也不得用 PID 1 / timerfd 的纸面方案宣称失联回收或 6 s 资格；不能以 USER_NOTIF 检查不可信 pathname 后放行。真实路径继续受 E0、ABI 审查、实际资格及精确执行授权约束。
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

原逐批测试、失败和环境记录保留于[验证快照](../records/status-before-planning-alignment-2026-11-01.md#验证入口与本次审阅)。L3 实现验证见[实现记录](../records/2026-11-01-linux-channel-l3-implementation.md)，本次复跑范围见[11 月 7 日日终记录](../records/2026-11-07-closeout.md#验证与留存)。各批测试数按当时执行范围解释。

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
