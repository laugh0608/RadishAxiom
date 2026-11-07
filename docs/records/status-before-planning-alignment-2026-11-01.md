# 2026-11-01 规划整理前的当前状态快照

本文件保存规划导航整理前的原始状态正文，仅将相对链接重定位。所有“当前”“下一步”“今晚”与授权叙述均按原批次日期理解，不提供新的执行指令。现行顺位与停止线见[当前状态](../status/current.md)，整理与验证见[本批记录](2026-11-01-planning-alignment.md)。

---

# RadishAxiom 当前状态

更新日期：2026-11-01

用途：供日常协作者读取现状、顺位、停止线和验证入口。历史事实按需进入[截至 2026-09-03 的归档](status-through-2026-09-03.md)。

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

2026-09-29 按项目所有者要求调整为核心语义优先，依据见[阶段审阅记录](2026-09-29-core-realignment.md)。现有来源取证与失败材料保留；完成取证不等于核心能力进展。

### 下一步

| 顺位 | 交付 | 完成或停止条件 |
| --- | --- | --- |
| 1：P1 真实语义组件 | [ADR 0016](../adr/0016-core-semantic-slice-entry.md) / [0017](../adr/0017-ir-v0.2-support-boundaries-and-migration.md)范围内已完成本机组件验收；[17 项矩阵](../ir/p1-support-boundary-review.md#必需验证矩阵对照)闭合结构、规范字节、身份与迁移回归 | 保留旧版未支持边界；不外推完整生产阶段、证明或跨平台验收 |
| 2：P2 真实义务生成 | [ADR 0018](../adr/0018-ir-derived-obligation-profile.md) / [规则](../evidence/ir-derived-obligations-v0.2.md)已接受并完成本机内部组件验收；26 份 IR / 482 项定义与 29 份负例实际核对 | 只交付显式 ir-derived 全集；group 覆盖 / 守恒分开；保留完整 Evidence 门禁 |
| 3：query 与纵向闭环（下一步） | [ADR 0019](../adr/0019-map-filter-query-encoding.md)–[0022](../adr/0022-map-filter-row-coverage.md) 的 P3-A / B / C / D 已完成本机组件验收；[ADR 0023](../adr/0023-core-empty-effect-derivation.md) 的 P3-E 空效果结构组件也已完成本机验收；[ADR 0024](../adr/0024-core-field-origin-derivation.md) 的 P3-F 字段来源内部分析已实现；[ADR 0025（Accepted）](../adr/0025-p4-request-response-model-decoding.md) 的 P4-A 请求 / 响应 / 模型解码已完成本机组件验收；[ADR 0026（Accepted）](../adr/0026-p4-concrete-target-replay.md) 的 P4-B 有限具体目标重放已完成本机组件验收；AX-B01 紧凑表示已完成[本地研究验收](2026-10-17-query-compaction-validation.md)；[ADR 0027（Accepted）](../adr/0027-compact-query-and-p4-binding.md)的 A–C 已完成[生产组件本机验收](2026-10-17-compact-query-production-validation.md)，已完成[真实 solver 准备审阅](2026-10-17-solver-preparation.md)，精确 CLI [补证](2026-10-17-cvc5-cli-dependencies.md)和 E1–E2 [纯组件验收](2026-10-17-solver-simulation-validation.md)已接续；E3 [D1–D3](../adr/0029-solver-linux-supervision-and-capabilities.md)已接受并提交，具体 ABI、内部传输及纯组件已完成[离线验收](2026-10-17-solver-e3-components-validation.md)；真实 bootstrap / FFI [实施方案](../query/solver-bootstrap-ffi-implementation-plan.md)已形成；[ADR 0030（Accepted）](../adr/0030-solver-bootstrap-ffi-and-build-provenance.md) 的 D1–D3 已接受，F1 纯共享边界 / 启动描述已完成[本机验收](2026-10-17-solver-f1-validation.md)，D3 [构建候选方案](../query/solver-cvc5-build-candidate-plan.md)已形成，E0 [后续补证](2026-10-17-cvc5-provenance-followup.md)继续保留实际链接与来源关联缺口；未取得运行资格 | 完整 P3 / P4 未实现；保留 AX-B01 正确、两个 wrong、invalid、timeout 和篡改标准，外部执行独立授权 |

近期验收看真实输入能否产生规范输出与可定位拒绝，区分实现、指定态 fixture、独立复核与证明；不以提交数、测试数或来源包数量替代里程碑。每个切片结束复核下一项是否直接服务上述交付；新增前置必须解释具体依赖和停止条件。

### 当前接续（2026-11-01）

按项目所有者要求完成[控制面 / 冻结与真实资格方案](../query/solver-local-cvc5-control-plane-plan.md)，随后精确提交 8 个文件为 `25ef314`，未 push；方案事实见[前批记录](2026-11-01-cvc5-control-plane-review.md)。只读 Docker 报告内核已由历史 `7.2.9` 变为 `7.2.12`，存储为 `overlayfs` / containerd snapshotter；不是新实例资格。

随后按要求推进 [G0 有限能力盘点](2026-11-01-cvc5-g0-capability-review.md)，结果为**证据不足，接线暂停**：`orbctl list --format json` 为 `[]`，Docker 总容器数 / 运行数均为 0；在已检查入口内未取得 Linux 管理上下文。macOS 原生共享视图存在，但其具体写别名防护未验证；存储硬限 / 独占写权限 / 独立终止及 PID / inode / 时间参数仍未闭合。不再重复 list / info 或追加模拟；恢复须先指定现有 Linux 管理入口与候选根，或另作新检查通道的精确范围决定。未创建 / 启动环境、组装、构建、探针或运行 solver，C1 / E0 / E4 与 readiness=false 保持；未查询上游许可答复。

G0 随后按明确要求提交为 `e507d78`，未 push；[新 Linux 通道最小方案](../query/solver-linux-management-channel-minimum-plan.md)已完成静态核定，推荐同一 daemon 的一次性非 root 只读诊断容器，明确权限、128 MiB / 0.5 CPU / 16 PID / 90 s 等候选额度及精确 CID 清理。只读核对了本机精确 Alpine arm64 镜像元数据，来源 / 许可 / applet 与有界编排尚未接受；不因镜像已存在而运行。该通道依赖 daemon 回收，不解决独立终止或存储硬限；未接受诊断例外、创建环境或提高 G0 / A1–A10 资格，见[本批记录](2026-11-01-linux-channel-minimum-review.md)。

最小方案已提交为 `aa162af`，未 push。随后[离线核对](2026-11-01-linux-channel-offline-review.md)闭合所选 index → arm64 manifest / config / layer 字节链，独立比较原 minirootfs 与镜像 514 项相对树一致，16 包 / 10 配方版本及许可声明一致；保留 APK shadow 校验差异、SBOM 来源记录和未认证构建声明。源码参考收敛了 mountinfo / cgroup 读取范围，但未绑定实际 `7.2.12-orbstack` 权限；并发现 BusyBox timeout 直接作为容器 PID 1 不能提供原设想的内部强杀保证，方案已限定 PID 1 监督 / 回收与非 PID 1 子进程拓扑。新增仅离线检查 / 独立树比较入口与合成测试，没有创建 / 启动环境、实现启动器或升级镜像 / 执行接受。

离线核对已提交为 `c4aeeb9`，未 push；随后完成[诊断 PID 1 库内源码切片](2026-11-01-linux-channel-init-review.md)，复用现有 Rust syscall / FD / 信号边界。PID 1 固定 BOOTTIME 总 20 s（工作 / 设置 18 s、收束 2 s），直接启动非 PID 1 采集子进程，取消 / 超时用精确 pidfd，接管后代逐项绑定、回收与重扫，仅实际 ECHILD 标记无子进程。移除 BusyBox timeout 依赖，保留真实主退出、首错与未确认回收。没有 CLI / Linux 制品 / 采集及 Mac 编排接线或环境执行，实际工具 / 权限 / 资源资格仍未取得。

PID 1 更改已提交为 `be8c620`，未 push；随后核定[目标构建与交付方案](../query/solver-linux-channel-build-and-delivery-plan.md)：Rust 1.97.1 / Linux musl AArch64 静态非 PIE、已有 bundled rust-lld，内嵌正文原字节与独立输入绑定，单文件 runtime 目录只读挂既有 `/mnt`。本机实际只有 Darwin target std，Linux 组件未安装；现有子流直接继承须改为内部管道、PID 1 独占外部帧报告，并在原 20 s 内预留最终导出与 raw exit，另审 panic / 分配失败出口。详见[本批记录](2026-11-01-linux-channel-delivery-review.md)；没有实现这些新接线、取得 / 安装组件、构建 / 挂载制品或创建 / 启动环境。

交付方案已提交为 `2e5da3a`，未 push；随后 [L1](../query/solver-linux-channel-l1.md)形成固定只读采集正文、单一 profile、45 源离线输入绑定、Rust 报告 codec 与独立 Python 输入 / 流复核。实际纯导出与合成互操作见[本批记录](2026-11-01-linux-channel-l1-review.md)，scope 仅 offline-source-binding-only，工具输入 null、readiness=false；正文仅做语法 / 合成过滤，未运行。该批尚未接 L2；后续实现见下方，目标安装 / Linux 构建与全部实际资格仍未接受。

L1 已提交为 `5609e6a`，未 push；随后 [L2](../query/solver-linux-channel-l2.md)接通内部三条 pipe / 显式 FD 所有权、唯一首 t0、18 / 19.8 / 20 s 截止、非阻塞帧传输与精确回收、终端 raw exit，以及默认关闭 leaf 的 panic / allocator 出口。现行 50 源输入仍是 offline-source-binding-only / 工具 null / readiness=false。宿主全目标 / 全 feature 117 项与独立脚本流复核见[本批记录](2026-11-01-linux-channel-l2-review.md)；没有运行正文、Linux syscall、目标安装 / 构建、创建 / 启动环境或扩大资格。

L2 已提交为 `5dab738`，未 push；随后 [L3](../query/solver-linux-channel-l3.md)核定精确 target / 完整输入方案。旧 musl target 原包 29,062,284 bytes / `49ff0879…cab5d31` 已重新核对，7 目录 / 78 文件及 66 项 payload 与旧库存完全相等，不重新下载；target 仍未安装。方案明确 cache / .partial 先前存在即停、单组件 120 s / 512 MiB 与精确卸载，完整 v0.2 root 通过独立清单绑定实际安装、工具 / 来源接受及 workspace 快照，保留现行 v0.1 拒绝。具体参数 / 方法 / 未覆盖范围见[本批记录](2026-11-01-linux-channel-l3-review.md)。未实现 v0.2 / 包装器、安装组件、构建 Linux 制品或创建 / 启动环境，readiness=false。

### 历史日终交接（2026-10-27）

今日截至 `2c3f82b` 共 4 笔提交：布局边界修正与 C2 缺口审阅、ADR 0031 D1–D3 接受、阶段拆分与有限计划、私有 v0.2 离线实现。完整提交表、代码 / 文档核对和分批验证见[日终记录](2026-10-27-closeout.md)；[10 月 23 日日终](2026-10-23-closeout.md)保留为历史。

v0.2 只形成阶段声明、目标级链接截获、留存材料与独立有限核对，须显式选择；默认 v0.1、旧冻结字节及拒绝保持。真实控制面、冻结和完整链接组成尚未完成，C1 / E0 / E4 及 A1–A10 实际资格不升级。LibPoly issue #113 已按本日授权发送，发送不等于许可澄清。今晚完成文档提交后停止，不 push、不组装、构建或运行 solver；最终文档提交号和工作区状态由交接消息报告。

### 接下来的事项

恢复基线：C1 **500 / 500 文件、691,605,464 bytes** 已取得并独立复核；172 包内容、copyright 路径及 101 `.dsc` 关联已核对，历史三角色签名与五负例按明确接受的有限信任范围通过，旧失败保留，见[输入审阅](2026-10-23-cvc5-c1-input-review.md)。20 个短时验签容器均已退出并删除，未安装、组装或执行 SDK / solver；验签宿主接受不能转用为构建资格。LibPoly [原草稿及发送接续](2026-10-23-libpoly-upstream-clarification-draft.md)已发布，缺口仍待权威依据；C2 已交付离线配方、布局与事件检查，**C1 仍 not-accepted，build_ready=false**。

下一次恢复时，先围绕“让原容量 AX-B01 在原资源限制下取得真实 solver 校准”核对以下直接前置；每批只有明确出口，不将来源清单扩展为无期限的工具链研究。这里保存建议，不延续历史批次的外部动作授权。

1. **取得 LibPoly 固定版本的许可澄清后，再作 C1 接受审阅。** [历史核对](2026-10-23-libpoly-license-history.md)已收敛为整体许可冲突、Polyxx 覆盖与旧 `open_memstream.c` 来源授权三项；[issue #113](https://github.com/SRI-CSL/libpoly/issues/113)已按 10 月 27 日明确授权发送。后续依据须适用固定提交并覆盖这些缺口；不重复查同一历史、下载已匹配材料或把风险接受写成许可事实。未安排自动轮询，不自动追加消息。
2. **L3 方案已核定，下一源码切片为 v0.2 纯输入 / 独立复核、native 捕获与有界包装器。** 按 [L3](../query/solver-linux-channel-l3.md)实施私有版本 / scope 迁移、sidecar 摘要绑定和实际 argv / 预算 / 取消拒绝测试；现行 50 源 v0.1 不能当完整 inputs，也不在原生入口 fallback。精确 target 旧原包已留存 / 重核，不重复下载；实际安装观察和特定工具 / 宿主 / 许可接受齐备前，不生成真实完整 root。组件安装、一次 Linux 构建、离线制品验收、交付挂载与执行分别授权；本轮不安装、不构建或创建 / 启动环境。保留实际 std / CRT / dylib / allocator / syscall、宿主权限 / proc / seccomp / bind、无写别名与独立终止 / 存储硬限，以及 C1 / G0 / E0 / E4 / solver 门禁。
3. **等待 C1 时，可继续 F2 的静态边界审阅。** 核对目标工具链、AArch64 汇编 / ABI、unsafe 与 FD 所有权，以及 outer setup policy、精确实例读回和 Mac adapter 接线；出口是具体问题修正或有限待验清单。既有本机 441 项测试不等于 Linux 目标构建 / 实际 syscall 验收；工具 / 制品条件具备并获准后再执行目标构建和真实负向矩阵。
4. **条件闭合后按原顺序进入实际路径。** C1 与构建环境资格闭合后，按[C3–C5](../query/solver-cvc5-build-candidate-plan.md#批次占用授权与停止线)先构建依赖、审阅实际 ABI / Editline 有序闭包和 manifest，再配置 / 构建主目标；C4 决定 E0，实际 E4 通过后才进入 E5 的最多八份校准及一次精确 wrong-add guarantee 尝试。保持原容量、128 MiB / 6 s 和旧四版字节 / 拒绝，不因不足增限或绕过门禁；这仍不等于完整 P0–P9 / Evidence / 独立 checker 验收。

### 当前接续（2026-10-17）

AX-B01 [紧凑表示方案](../query/ax-b01-query-compaction-review.md)完成本地研究验收：保持原容量、旧四版字节与 1 MiB 上限，新研究表示的 72 条记录均为 265,107–962,850 字节。采用有类型公式恒等化简、共享、保序短名称与有界代入，没有改变关系编码或使用 WF 假设。12,553 次既有有限比较与 324 次原容量观察通过，见[测量与验收](2026-10-17-query-compaction-validation.md)。

研究代码与材料已提交为 `f60d4c5`。[ADR 0027（Accepted）](../adr/0027-compact-query-and-p4-binding.md)、[query v0.5](../query/map-filter-query-v0.5.md)及 [P4-A v0.2](../query/p4-request-response-model-v0.2.md)已接受：新 artifact query0.3、查询规则摘要、独立 compact 预算与请求 v0.2；旧模型文法 / 候选格式不变。项目所有者已接受 D1 表示与版本、D2 预算与拒绝、D3 P4 接入与 Rust 实施范围；按 A–C 推进，由主代理主持验收，明确实现委派 gpt-6.1-sol / high。

Accepted 文档已提交为 `14a9693`。A–C 已完成 Rust 实现与本机验收：v0.5 / query0.3、新 solver profile / 请求 v0.2、七项 compact 预算与合成 P4-B 接续均已落地。原容量 27 个目标的新查询实际为 265,107–962,850 字节，全部保持 100 槽位与 501 个自由符号，最大余量 85,726 字节；790 条 corpus 记录的 12,553 次有限比较及 324 次原容量观察通过，见[生产验收](2026-10-17-compact-query-production-validation.md)。

旧四版字节、原容量旧请求的尺寸拒绝和 1 MiB 上限保持；新字节可行不代表真实 solver、128 MiB / 6 s 资源可行、证明或完整 P4。实现与验收材料已提交为 `d055658`，未 push。

随后按项目所有者授权完成[solver 准备审阅](2026-10-17-solver-preparation.md)：现有 OrbStack Linux arm64 Docker 宿主选为诊断候选，未取得运行资格；精确 cvc5 1.3.4 non-GPL static ZIP 已获取，摘要、包内路径和 CLI 静态 ELF 检查通过，完整依赖 / 许可证接受尚有缺口。[ADR 0028](../adr/0028-bounded-solver-calibration-entry.md)与[执行层设计](../query/solver-execution-preparation.md)已按 D1–D3 接受，限定最多八份校准加一次精确 wrong-add guarantee 尝试、显式 cgroup 内存范围和失败关闭路径。当前只完成准备，未安装或启动 solver、构建 / 启动容器或 VM、修改系统配置或远程状态。

项目所有者已接受 ADR 0028 三项决定，授权先提交准备材料，再推进精确 CLI 依赖 / 许可证补证与执行层实施清单；镜像构建、宿主负向探针和真实 solver 分别授权。已有 daemon 的能力报告不能代替 OS 限制、时限 / 清理和实际模型文法验证。

ADR 0028 与准备材料已提交为 `6593254`。随后完成[精确 CLI 补证](2026-10-17-cvc5-cli-dependencies.md)：25 份来源材料、四项固定依赖配方、CaDiCaL / SymFPU / LibPoly 版本化许可及对应 arm64 发布作业已核对；发现 Editline / terminfo / glibc 链需补入库存。详细 CI 日志返回 403，实际系统库版本、完整链接清单及配方到 CLI 的认证关联仍未闭合，保持 not-accepted。已形成[执行层实施清单](../query/solver-execution-implementation-plan.md)：E1–E2 可作为后续纯组件切片，E0 工具接受及 E3 独立终止 / cgroup 能力是进入真实路径的硬门禁。本批补证和清单已提交为 `ff2e4ed`，没有编写真实 executor 或执行外部载荷。

随后按当前任务授权完成 E1–E2 [纯组件与模拟规则](../query/solver-diagnostic-simulation-v0.1.md)的实现及[本机验收](2026-10-17-solver-simulation-validation.md)：新增私有 `solver-diagnostic-host`，所有身份、计划与观察固定 simulation；事件与流仅在内存处理。主代理主持设计与验收，明确实现委派 gpt-6.1-sol / high。原容量 wrong-add guarantee 以 962,642 字节 / 501 自由符号的请求贯穿合成捕获、原 P4 解码和 P4-B 精确目标重放；11 组导出由独立脚本核对。E0 / E3 保持硬门禁，没有真实接受、资格或认证捕获能力，也没有运行镜像、探针或 solver。实现及验收材料随后按项目所有者要求提交为 `a0150c6`。

本次继续 E3 设计收口，形成 [ADR 0029（Accepted）](../adr/0029-solver-linux-supervision-and-capabilities.md)、[监督设计](../query/solver-linux-supervision-design.md)和 [syscall 策略](../query/solver-linux-syscall-policy.md)：容器内 PID 1 监督器与唯一子进程共用原资源，READY / ARM 不续期，cgroup 只读观测与事后整树确认分层；发现仅匹配 execveat FD / AT_EMPTY_PATH 不能禁止绝对路径再次执行，新增 B6 装载门禁。具体信任增量和静态审阅见[本批记录](2026-10-17-solver-e3-design-review.md)。项目所有者随后明确接受 D1–D3，并授权先提交本批设计，再推进具体 ABI、内部传输格式与离线纯组件 / 模拟测试。时钟误差界、内核 / runtime 能力与真实 syscall 适配均未取得资格；E0 和运行资格继续阻断真实路径。

Accepted E3 设计已提交为 `e2d36ce`。随后完成[具体 ABI](../query/solver-linux-abi-v0.1.md)、[内部封套](../query/solver-bootstrap-wire-v0.1.md)、[S 运行策略](../query/solver-supervisor-policy-v0.1.md)及[监督 / cgroup 模拟](../query/solver-supervisor-simulation-v0.1.md)。W / S 实际 cBPF bytes 经独立 Python 的 3,176 / 1,450 个有限案例核对；原容量 wrong-add 请求通过封套重组、完整模拟收束与原 P4-B 重放。详见[组件验收](2026-10-17-solver-e3-components-validation.md)。本批实现与验收材料已提交为 `c489ec2`；没有创建真实 executor 或解除 E0 / 实际运行资格门禁。

随后按项目所有者授权形成[真实 bootstrap / FFI 方案](../query/solver-bootstrap-ffi-implementation-plan.md)与[独立实化审阅](../query/solver-bootstrap-ffi-review.md)：明确 listener 先交付后收紧、固定 FD / pipe 属性、Rust 启动与信号、Mac/S 分离、启动描述及 cgroup 退出过渡。新 [ADR 0030](../adr/0030-solver-bootstrap-ffi-and-build-provenance.md)已 Accepted；项目所有者明确接受 D1 原生宿主 / 共享 core、D2 真实绑定 / 观察、D3 可追溯构建候选方案，要求先提交本批方案与补证，再推进 F1 纯共享边界 / 启动描述及 D3 方案。E0 后续补证只补来源事实，不改变原 CLI 的 not-accepted；具体取得材料与验证见[本批记录](2026-10-17-cvc5-provenance-followup.md)。本轮未实现可调用 FFI、改变依赖或生成 Linux 制品；整体方案审阅与验证见[验收记录](2026-10-17-solver-bootstrap-plan-review.md)。

方案与补证已精确提交为 `f2ad466`。随后按当前授权完成 F1：新增私有纯 `solver-supervision-core`，提取 ABI / W/S 策略 / wire / cgroup 值解析；host 保留原接口与固定资源，模拟身份和观察继续隔离。闭合[启动描述](../query/solver-bootstrap-start-v0.1.md)、strict 请求规划、Mac/S 分离声明与截止计划、增量摘要和离线资源 / 策略输入已实现。原容量 query、旧封套与策略字节保持，实际回归及独立核对见[F1 验收](2026-10-17-solver-f1-validation.md)。

F1 与 [D3 构建候选方案](../query/solver-cvc5-build-candidate-plan.md)已提交为 `1a7ff38`，F2 已提交为 `bf197ad`，C0 [SDK 元数据选择与验收](2026-10-17-cvc5-c0-sdk-metadata.md)已按要求提交为 `c2ea5d0`，均未 push。F2 的[原生边界](../query/solver-bootstrap-native-boundary.md)与[监督实现](../query/solver-bootstrap-native-supervisor.md)仍只完成本机脚本后端检查。

项目所有者随后授权取得固定的五项源码归档及必要许可材料，继续完整源码、Production 配置和构建 patch 静态审阅。五项归档已取得并安全展开，四依赖摘要匹配固定配方；cvc5 的 7,066 个文件与已留存 Git tree 内容一致。完整源码揭示 CLI 的 `pyparsing` 和 GMP AArch64 汇编的 `m4` 需求，SDK 选择沿原快照补齐；配置与 patch 的结果、许可歧义及剩余条件见[本批验收](2026-10-17-cvc5-c0-source-review.md)与[C0 专题](../query/solver-cvc5-c0-input-selection.md)。主代理主持设计与验收，具体工作委派 gpt-6.1-sol / high。本批已提交为 `ec56fc7`。`build_ready=false`；源码一致性不代表签名、包内容、许可或工具接受。没有下载 SDK 二进制包、安装、构建、运行探针 / solver、修改系统配置或 push；原容量、旧字节和资源限值保持。

### P4 接续（2026-10-13）

1. **P4-A 已提交并完成本机组件验收。** 提交为 `b86eb33`；[ADR 0025](../adr/0025-p4-request-response-model-decoding.md) / [规则](../query/p4-request-response-model-v0.1.md)的三个纯入口、完整绑定、模型子集、Text 类、世界候选与预算 / 拒绝通过本机验证，见[本批记录](2026-10-12-p4a-validation.md)。该记录保留提交前事实，实际提交接续以本项为准。纯解析与候选解码不计作目标重放、真实尝试或证明。
2. **尺寸阻断已测量，保留原 query 与上限。** [尺寸审阅](../query/ax-b01-query-size-review.md)实际核对 72 份原容量查询为 42,577,698–65,831,615 字节；短名字、死定义移除和相同项共享的组合估算仍全部超过 1 MiB。新内部 adapter 保持 planned-not-calibrated，后续查询表示或资源 profile 分别审阅，不缩小容量、原地改字节或自动增限。unknown 可附模型但不解码 world，真实校准仍缺失。
3. **P4-B 已按接受范围完成本机组件验收。** [ADR 0026（Accepted）](../adr/0026-p4-concrete-target-replay.md) / [规则](../query/p4-concrete-target-replay-v0.1.md)落实为直接原 IR 求值、完整 WF / Pre、五类精确目标、来源绑定与 strict 观察。29,153 次既有有限目标观察及新增手算、深度、预算与篡改检查见[本批记录](2026-10-13-p4b-validation.md)。AX-B01 原容量三个候选在同一有限输入上由 guarantee 区分，wrong-drop-zero 的内建 coverage 仍成立；直接 world 不声明来自 solver。
4. **保持单目标尝试与完整验证分开。** 真实 solver 校准 / 执行另须精确工具验收、adapter、执行宿主、硬资源限制和当前任务授权。join / group 查询、聚合契约、双世界非干扰、公共结构证明支持、完整 Evidence v0.2、跨仓 checker 与 P7 / P9 继续分别审阅。

上述查询表示审阅已由 2026-10-17 的本地研究、ADR 0027 接受及 A–C 生产组件验收接续；旧四版阻断保留，新 v0.5 的原容量字节门槛已通过。真实工具校准、资源变更与完整 Evidence 仍待各自决定，不自动启动 solver、安装依赖、写入远程或进入正式实验。

### 暂缓工作与恢复条件

| 工作 | 保留状态 | 恢复条件 |
| --- | --- | --- |
| headers / GCC / Binutils 等新增来源取证 | 原包、失败与本机留存不动；[来源状态表](../checker-runtime-guest-source-build-review.md#rust-配方剩余输入状态)继续报告未闭合部分 | 指定真实构建 / 执行目标确实需要该输入，先提交有投入上限及结束决定的精确补证范围，再取得必要授权 |
| guest / runner 产品化与公共迁移 | ADR 0013–0015 有效，Darwin payload 保持 inactive；来源、容量、签名和许可尚未完整验收 | 重核成本与维护能力，明确最小批次及实际负载验收，分别完成工具 / 公共迁移 / 外部执行前置 |
| 备份增量与转移 | 后续批次有本机留存，异盘恢复未确认，见[日终材料状态](2026-09-16-closeout.md#本机材料与外部影响) | 作为独立恢复任务指定目标与范围，不作为 P1 开工前置，不删除原材料 |

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

2026-11-01，L2 已提交为 `5dab738`；随后 L3 核定方案并仅重核指定已有原字节：musl target 全归档 / 66 payload、发行与安装清单投影、四工具字节、255 份旧源码文本 / 许可元数据和精确 linker help。只读诊断、计划 / 材料交叉核对和完整仓库检查见[本批记录](2026-11-01-linux-channel-l3-review.md)。没有改 Rust / Cargo / lockfile，未重跑无变化的 Rust 测试；无取得 / 安装组件、Linux 构建或环境动作，现行绑定 / readiness / 实际资格不升级。

2026-11-01，L1 已提交为 `5609e6a`；随后 L2 源码接线完成：受影响包全目标 / 全 feature 本机 117 项（新增 30 / 既有 87）、Python 合成 16 项、格式及 workspace 全 feature Clippy 通过；50 源导出 / 旧样本互操作及七份脚本后端实际流的独立 Python 复核通过。仓库与留存核对、命令 / 失败和有限信任范围见[本批记录](2026-11-01-linux-channel-l2-review.md)。没有执行 Linux / collector、目标安装 / 构建或创建 / 启动环境；L2 新改动未自动提交 / 推送，readiness / 实际资格不升级。

2026-11-01，交付方案已提交为 `2e5da3a`；随后 L1 正文 / 源绑定 / 纯 codec 完成：受影响包本机 87 项（新增 18 / 既有 69）、Python 合成 15 项、格式与全 feature Clippy 通过；45 源绑定及 Rust → Python 样本 1,747 个截断拒绝 / 7 种分块互操作通过；仓库检查通过（2,923 文件）、差异卫生及局部引用 / 留存绑定通过。实际命令和失败见[本批记录](2026-11-01-linux-channel-l1-review.md)。未运行采集正文、镜像 applet 或 Linux syscall，未安装目标组件、构建 Linux 制品或创建 / 启动环境，readiness / 实际资格不升级。

2026-11-01，PID 1 更改已提交为 `be8c620`；随后只读核对已安装宿主工具 / 缺失 Linux target、三份工具原字节及已有挂载点，完成目标构建 / 交付、正文绑定、报告与最终退出方案。完整仓库检查通过（2,910 文件），差异卫生、局部引用 / 观察绑定与预算算术核对通过；实际命令、来源 / 失败与未实施边界见[本批记录](2026-11-01-linux-channel-delivery-review.md)。未改源码或重跑 Rust 组件测试，未取得 / 安装目标组件、构建制品、挂载或启动环境。

2026-11-01，离线核对已提交为 `c4aeeb9`；随后实现诊断 PID 1 的私有监督 / 回收入口、最少 syscall 扩展及合成正负例。受影响 crate 全目标 69 项通过（本批 28 / 既有 41），格式与全 feature Clippy 通过，完整仓库检查通过（2,907 文件），差异卫生及局部引用 / 范围核对通过。实际命令和未接 CLI / 目标制品边界见[本批记录](2026-11-01-linux-channel-init-review.md)。没有运行真实 Linux syscall、创建 / 启动环境、构建镜像或 solver，不提高实际资格。

2026-11-01，最小方案已提交为 `aa162af`；随后新增只读离线 OCI / APK / ELF 检查、独立原始 rootfs 相对树比较及合成拒绝测试。20 项合成测试和 Python 3.14.5 完整仓库检查通过（2,903 文件），镜像实际检查保留差异并退出 2，独立相对树比较退出 0；差异卫生与局部引用 / 观察绑定通过。实际输入、来源 / 许可矩阵、权限参考、PID 1 超时缺口和未创建环境范围见[本批记录](2026-11-01-linux-channel-offline-review.md)。未运行 Linux 载荷、资格、构建或 solver，未接受镜像 / 权限或新增程序证明。

2026-11-01，G0 已精确提交为 `e507d78`；随后完成新通道最小方案及必要的本机 image list / inspect 只读元数据核对。Python 3.14.5 完整仓库检查通过（2,896 文件），差异卫生与局部引用 / 观察核对通过；静态方案、镜像 / 读取权限前置和未创建环境边界见[本批记录](2026-11-01-linux-channel-minimum-review.md)。未接受镜像 / applet、诊断执行或新信任，未运行资格 / 构建 / solver。

2026-11-01，前批方案已提交为 `25ef314`；随后完成 G0 本机 CLI / 配置、daemon 与明确共享路径的只读盘点，并核对官方文件视图边界。Python 3.14.5 的完整仓库检查通过（2,893 文件），差异卫生及局部观察 / 引用核对通过，见 [G0 记录](2026-11-01-cvc5-g0-capability-review.md)；无 Linux 实例读回或真实资格，不提高 A1–A10 状态。

2026-11-01，完成控制面方案与现有代码静态核对、只读 `docker context show` / `docker info` 筛选留存及官方接口资料核对。默认 Python 3.9 导致首轮仓库检查失败，使用现有 Python 3.14.5 调用同一完整检查器后通过（2,891 文件），差异卫生通过，见[本批记录](2026-11-01-cvc5-control-plane-review.md)。未修改实现、依赖、机器契约、Accepted ADR 或冻结规则 / 配方，未另跑 Rust / cvc5 Python 组件回归，未运行 Linux 资格、组装、构建或 solver；A1–A10 实际资格不升级。

2026-10-27 日终，对照全天四笔提交审阅并同步九份文档；仓库检查通过（2,888 文件），差异卫生与新旧配方 / 方法 / 规则引用身份核对通过。未重跑无改动的实现测试，也未执行真实构建或运行资格；详细结果见[日终记录](2026-10-27-closeout.md)。

2026-10-27，v0.2 离线阶段切片完成 28 项阶段 / 截获测试、35 项链接材料测试、33 项旧配方与 40 项布局 / 事件回归；完整原输入重核、新配方 / 布局 / 合成材料 CLI、独立导出与旧拒绝核对见[本批记录](2026-10-27-cvc5-offline-phases.md)。保留真实资格、许可与执行停止线。

2026-10-27，ADR 0031 与配套阶段 / 验收专题先形成 Proposed 草案，随后 D1–D3 由项目所有者明确接受；核对限定替代位置、信任、保证减少、必要库重复与旧版隔离；文档仓库检查通过（2,872 文件），`git diff --check` 通过。该草案批未修改实现、机器契约、旧配方或既有 Accepted ADR，未重跑代码测试，也未执行 A1–A10 未来验收；不将文档检查计为构建或运行资格。

2026-10-27，C2 边界修正后 40 项布局 / 事件检查、33 项配方回归通过；真实原输入经原预检重核，新旧完整布局一致，仍返回离线候选退出码 2 / 三个 readiness=false。仓库检查通过（2,870 文件），`git diff --check` 通过；新增负例的修正前失败及一次相对路径调用拒绝见[本批记录](2026-10-27-cvc5-c2-boundary-review.md)。未重跑 Rust 或 Linux 运行资格；本批唯一外部写入是明确授权的 LibPoly issue #113。

2026-10-23，C1 获取批次 70 项下载器测试及 500 项独立原字节核对通过；内容审阅完成 25 项扫描器 / 9 项状态解析器测试、374 项真实内容扫描和完整 12 步历史签名验证（含五负例），见[输入审阅](2026-10-23-cvc5-c1-input-review.md)。C2 [配方批次](2026-10-23-cvc5-c2-offline-entry.md)33 项新增 / 47 项既有测试通过；后续[布局与事件批次](2026-10-23-cvc5-c2-execution-review.md)36 项新增 / 33 项回归通过，仓库检查通过（2,868 文件）。计数按批次报告，不相加为一次全量运行。日终只改文档，实际复核见[本日回顾](2026-10-23-closeout.md)；未重跑无改动的 Rust，也未安装、组装或执行 SDK / solver。

2026-10-22，本批离线清单、构建输入预检与实际拒绝、既有 C0 / 独立 SDK / 五源码重核结果见[本批记录](2026-10-22-cvc5-c1-c2-preparation.md)。不包含密码学验签、实际包内容 / ABI / CMake / 构建或真实 solver 验证。

2026-10-17，最近的 F2 实现验证为 workspace 全目标 441 项通过、1 项按原设置忽略，文档测试另有 3 项通过；格式与全 feature Clippy 通过，见[F2 验收](2026-10-17-solver-f2-validation.md)。后续 C0 不修改 Rust，最终源码 / 配置 / patch / 元数据检查共 147 项 Python 测试通过，见[C0 验收](2026-10-17-cvc5-c0-source-review.md)。这些计数来自不同批次，不相加作为一次完整运行；日终文档复核与实际检查见[日终记录](2026-10-17-closeout.md)。

2026-10-17，E3 设计批次完成官方接口资料核对、有限时间握手算例与文档检查，见[设计审阅记录](2026-10-17-solver-e3-design-review.md)。该设计批次未重跑 Rust workspace，也没有运行 Linux 探针、构建镜像或真实 solver。随后离线实现批次的实际验证见[组件验收](2026-10-17-solver-e3-components-validation.md)。

2026-10-17，E1–E2 纯组件的本机验收、旧字节对照与独立模拟导出核对见[本批记录](2026-10-17-solver-simulation-validation.md)。只检查模拟事实及其 P4 接续，不形成真实 solver、宿主资格或证明。

2026-10-17，真实 solver 准备批次完成只读宿主盘点、精确 ZIP 获取、标准库静态检查与合成负例；原包 / CLI 摘要、观察数据及可重跑入口见[准备记录](2026-10-17-solver-preparation.md)。未运行任何真实 solver 或隔离探针，不外推工具 / 宿主接受。

同日精确 CLI 补证以标准库检查固定来源摘要 / Git blob、ELF sections 与配方 / CI 关联，并保留获取失败；结果与生成入口见[补证记录](2026-10-17-cvc5-cli-dependencies.md)。本批不改变 Rust、依赖、旧规范或资源值，不将静态观察外推为运行验证。

2026-10-17，ADR 0027 的 A–C 实现通过格式、workspace Clippy 与完整 workspace 294 项测试，另一个默认 ignored 的旧产物导出测试单独执行通过；独立实际 Rust SMT 比较、18 份旧产物逐字节对照及仓库检查见[生产验收](2026-10-17-compact-query-production-validation.md)。未启动 solver、其他平台、CI 或远程执行。

同日设计批次完成现有接口 / 版本 / 资源 / P4-B 来源路径审阅，仓库检查通过（2,620 文件）；规范随后 Accepted 并提交为 `14a9693`，实现绑定的规则正文保持该提交字节。

2026-10-17，紧凑表示研究脚本 22 项测试、72 条原容量记录 / 790 条四版语义记录的独立比较、精确 P4-B 回归、格式与 workspace Clippy 通过，详见[本批验收](2026-10-17-query-compaction-validation.md)。本批没有重跑完整 workspace 测试、真实 solver、其他平台或 CI；该研究记录自身不代表生产 profile 接受或实现；后续状态以上述 ADR 0027 及生产验收为准。

2026-10-13，P4-B 新增 12 项 Rust 回归，完整 workspace 277 项测试、格式、Clippy 与仓库检查通过，见[本批验收](2026-10-13-p4b-validation.md)。独立 Python 重建 29,153 次有限观察与完整见证；原容量 AX-B01、5,002 Record 类型、1,500 层故障依赖、13 类预算与篡改分别核对。本批没有真实 solver、其他平台、独立 checker、CI 或远程执行。

2026-10-12，P4-A 新增 18 项回归，workspace 共 265 项测试通过（runtime 56、Darwin store 3、digest 2、IR 204）；格式、Clippy、独立合成材料与仓库检查通过，见[本批验收](2026-10-12-p4a-validation.md)。53 份既有合成 IR 的完整空世界与新复合 / 深度材料实际核对；AX-B01 三候选 / 四 profile 的 72 份 query 全部受 stdin 上限拒绝。真实 solver、其他平台、P4-B 与独立 checker 未运行，CI 未触发。

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

P3-F 本机验证见[本批验收](2026-10-08-p3f-validation.md)，P3-E 见[前批验收](2026-10-08-p3e-validation.md)，P3-D 见[前批记录](2026-10-08-p3d-validation.md)，P3-C 见[前批验收](2026-10-08-p3c-validation.md)，P3-B 见[历史验收](2026-10-08-p3b-validation.md)，P3-A 历史见[10 月 5 日记录](2026-10-05-closeout.md)；保留全部既有契约 / IR / P2 材料及旧入口隔离。CI 未触发，其他平台及真实 checker / cvc5 / Node 未执行。后续按[工程门禁](../governance/repository-governance.md#rust-工程门禁)验证，契约检查不能替代 Rust 测试。

## 按需阅读

- [产品定义](../product-definition.md)、[开发目标与验收计划](../development-plan.md)
- [文档索引](../README.md)、[ADR 索引](../adr/README.md)、[机器契约索引](../../contracts/README.md)
- [协作与执行](../governance/agent-collaboration.md)、[仓库治理](../governance/repository-governance.md)
- [Darwin 强隔离审阅与历史观察](../checker-runtime-darwin-hard-isolation-review.md)
- [原状态与实施流水归档](status-through-2026-09-03.md)
