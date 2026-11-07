# 能力专题地图

日期：2026-11-01。用途：将整体目标、长期能力、现有子专题与实施 / 验收来源连接起来。读者为项目所有者、实现者与复核者；本文不定义语义、信任、公共格式、运行资格或新的执行授权，也不复制任务结果。

[产品定义](product-definition.md)与[开发目标与验收计划](development-plan.md)承载整体规划；本页是五条能力主线的归属地图；[当前状态](status/current.md)只维护当前顺位、阻塞和停止线。逻辑层级不要求目录搬迁：规范、ADR、实施方案和独立材料继续保留原路径。P、E、F、C、G、L 与 A1–A10 均保留原义；阶段、切片与验收矩阵不是平行产品主线。

每个子专题有一个主要归属，协同只引用合同。以下列出当前主链与已形成基线的正式来源；历史细案继续从[文档索引](README.md)按需查阅。规范是标准，实施清单是任务范围，records 是实际结果；设计接受、离线验证、工具 / 宿主资格、真实运行、独立检查及证明分别判断。

<a id="semantics-ir"></a>

## 语义、IR 与义务

目标：把有键有限表的纯转换表达为有类型、可规范化、可明确拒绝的候选及义务。拥有语义、身份、义务定义和版本迁移；不以解析或结构通过宣称证明成立。验证管线和独立 Checker 消费这些契约，不复制另一份语义。

| 子专题 / 设计来源 | 实施与验收来源 | 协同 |
| --- | --- | --- |
| [首域语义 v0.2](semantics/keyed-finite-table-semantics-v0.2.md)、[IR v0.2](ir/axiom-ir-v0.2.md) | P1；[支持边界与矩阵](ir/p1-support-boundary-review.md)、[显式迁移](ir/ir-v0.1-to-v0.2-migration.md) | 管线输入、独立复核 |
| [IR 派生义务 v0.2](evidence/ir-derived-obligations-v0.2.md) | P2；[义务审阅](evidence/p2-obligation-profile-review.md)、[独立材料](../contracts/ir-derived-obligations-v0.2/README.md) | 查询编码、Evidence |
| [规范质量与资源可行性](development-plan.md#规范质量与资源可行性) | 原计划中的后续诊断与规范审查，正式变化须另行版本化决定 | 实验评估、管线 |

完成条件沿原版本 / 矩阵，覆盖正常、拒绝、迁移及独立期望；已绑定原文字节保持。P1 / P2 内部组件完成不等于完整生产阶段或 Evidence v0.2 已交付。

<a id="verification-pipeline"></a>

## 验证管线与反例

目标：从真实候选经义务、查询、求解与目标重放取得可采取行动的结果。拥有 P0–P9 的逻辑衔接、故障归因和原容量验收；工具来源与执行资格依赖运行交付，证明复核依赖独立 Checker。准备工作必须说明解除哪个直接阻断，不自动扩为无期限的来源研究。

| 子专题 / 设计来源 | 实施与验收来源 | 协同 |
| --- | --- | --- |
| [AX-B01 首切片依赖](axiom-pipeline-first-slice-dependency-review.md) | 原 P0–P9 与首个纵向验收集合；[整体里程碑](development-plan.md#里程碑与完成标准) | 所有主线 |
| [map / filter 查询 v0.5](query/map-filter-query-v0.5.md)及原四版 | P3-A–D；[紧凑表示绑定 ADR 0027](adr/0027-compact-query-and-p4-binding.md)、原独立材料与版本配对 | 语义与义务、P4 |
| [空效果结构推导](query/core-empty-effects-v0.1.md)、[字段来源](query/core-field-origin-v0.1.md) | P3-E / F；原规则、独立材料及有限观察范围 | 语义与标签 |
| [P4-A v0.2](query/p4-request-response-model-v0.2.md)、[P4-B 重放](query/p4-concrete-target-replay-v0.1.md) | 原模型解析 / 具体重放矩阵；[P4-B 本机证据](records/2026-10-13-p4b-validation.md) | solver 执行、独立 Checker |
| [窄入口执行清单](query/solver-execution-implementation-plan.md) | E0–E6 的逻辑入口与退出；E3 所需宿主 / 原生实现由运行交付提供，E5 的原容量校准保持原范围 | 运行交付 |

完成需逐层区分真实工具、有限重放、完整制品与独立证明；旧尺寸拒绝、资源限制、错误 / timeout / 篡改路径仍按原合同。一次校准不能代签完整四题或 P0–P9。

<a id="independent-checker"></a>

## Evidence 与独立 Checker

目标：使结果可导出、可定位并由独立路径复核。拥有公共 Evidence 语义、版本边界与跨仓交接要求；Checker 实现由其仓库负责，本次不跨仓修改或复制完整能力矩阵。

| 子专题 / 设计来源 | 实施与验收来源 | 协同 |
| --- | --- | --- |
| [Evidence v0.1](evidence/axiom-evidence-v0.md)、[验证说明](evidence/axiom-evidence-v0-validation.md) | [ADR 0009 迁移边界](adr/0009-axiom-evidence-v0-drift-and-migration.md)；新旧义务、格式与旧结果不得混配 | 语义、管线 |
| [独立 Checker 交接](development-plan.md#独立-checker-语义验收与跨仓交接) | 原计划中的目标归因、同域新题、正向证明与结果解释；实现状态沿其指向的独立仓库维护 | 运行交付、实验评估 |
| [结果消费切片](checker-runtime-result-consumer-slice-review.md) | 原消费范围及程序结论 / 接受状态 / 覆盖 / 外层运行保证的分开验收 | 产品 runtime |

生产 `proved`、Evidence 接受、结构一致、后端声明与独立证明不可合并。源码或文档改变不自动重绑既有 payload / Release / acceptance；新制品另行验收。

<a id="runtime-delivery"></a>

## 运行资格与产品交付

目标：让指定工具和 Checker 通过可维护的来源、安装、隔离、故障处理与持久化路径服务产品。拥有宿主、工具与制品资格，不能用安装、离线方案或模拟结果代替真实负载与语义验收。

| 子专题 / 设计来源 | 实施与验收来源 | 协同 |
| --- | --- | --- |
| [Checker 产品化依赖](checker-runtime-productization-dependency-review.md) | 来源、维护、资源与真实容量矩阵；[Darwin 隔离](checker-runtime-darwin-hard-isolation-review.md)与 ADR 0013–0015 仍为原决策 | 独立 Checker |
| [安装切片](checker-runtime-linux-install-slice-review.md)、[持久化切片](checker-runtime-evidence-store-slice-review.md) | 原 payload / launcher / store / receipt 范围及[精确登记](../contracts/checker-runtime-payloads-v0.1/README.md) | 结果消费 |
| [bootstrap / FFI](query/solver-bootstrap-ffi-implementation-plan.md) | F1 / F2 及原生、FD / syscall、目标构建与实际负向矩阵 | 管线 E3 |
| [cvc5 构建候选](query/solver-cvc5-build-candidate-plan.md)、[输入准备](query/solver-cvc5-input-preparation.md) | C0–C5；[阶段计划](query/solver-local-cvc5-phase-plan.md)与[A1–A10](query/solver-local-cvc5-build-provenance-review.md#必需验收矩阵) | 管线 E0 / E4 |
| [控制面与冻结](query/solver-local-cvc5-control-plane-plan.md) | G0 盘点与真实负向资格；实际结果沿原记录，未闭合项不因新通道方案而升级 | C 构建、E 执行 |
| [最小 Linux 管理通道](query/solver-linux-management-channel-minimum-plan.md)、[目标构建与交付](query/solver-linux-channel-build-and-delivery-plan.md) | L1 / L2 / [L3](query/solver-linux-channel-l3.md)等原切片，源绑定、完整输入、目标产物与环境执行分开 | G0 观察，不代替独立终止或存储资格 |

原配方、原绑定和公共迁移边界保持；当前直接工作仍由 current 排序。LibPoly 澄清、C1 接受、真实环境、E0 / E4 和执行授权是不同条件，不用索引整理替其中任何一项放行。

<a id="evaluation"></a>

## 实验评估与用户反馈

目标：验证表达与反馈对 Agent 和维护者的实际帮助。拥有预注册、装置与人类观察的评价方法，不反向修改正式语义，也不以模型自述、测试数或取证数量计算产品完成度。

| 子专题 / 设计来源 | 实施与验收来源 | 协同 |
| --- | --- | --- |
| [首域四题语料](benchmarks/keyed-finite-table-corpus-v0.md)、[Agent 预注册](experiments/agent-representation-preregistration-v0.md) | 原 execution lock、H1 / H4、模型 / 任务分层与失败保留；正式任务与后续泛化材料分别管理 | 管线、Checker |
| [装置与人类反馈](development-plan.md#agent-装置与人类反馈) | 原装置审计、合成失败场景与结果定位依据，不改 `strict_success` | 产品结果消费 |

只有对应注册 / 样本 / 版本范围内的实际证据能支撑结论；正式模型调用、跨模型或跨领域验证另行确认。历史注册与绑定字节不因导航改动而更新。

## 任务来源与维护

实施清单中的既有切片保留任务范围、依赖和验收标准，实际结果引用 records；current 摘录当前动作与阻塞，地图不维护完成勾选。新任务先指向本页一个主要归属，并声明具体来源文件；无真实新合同就不新建平行任务库。完整规则见[协作专题](governance/agent-collaboration.md#planning-hierarchy)。
