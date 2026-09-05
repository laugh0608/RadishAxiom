# RadishAxiom 文档

用途：按任务导航正式规范、开发目标、实现记录与机器契约。读者为项目协作者；本索引不承载当前顺位、授权或完整实施流水。

`docs/` 是正式文档源。日常任务先读当前状态，再进入相关专题；记录仅在追溯事实时读取。

## 默认入口

| 任务 | 入口 |
| --- | --- |
| 现状、下一步、停止线、验证命令 | [当前状态](status/current.md) |
| 产品定位、首批工作流与价值验收 | [产品定义](product-definition.md) |
| 核心闭环、运行能力、证明覆盖与实验验收 | [开发目标与验收计划](development-plan.md) |
| 工作区、授权、实施、验证、实验留存与交接 | [Agent 协作与执行规则](governance/agent-collaboration.md) |
| 分支、PR、CI 与 Rulesets | [仓库治理](governance/repository-governance.md) |
| 开放核心、用户产物与商业边界 | [许可证与生态策略](licensing-strategy.md) |
| 长期决策及其替代关系 | [ADR 索引](adr/README.md) |

## 正式规范与实验

- [首域类型化语义](semantics/keyed-finite-table-semantics.md)：值、表、转换、契约、效果和信任边界。
- [Axiom IR v0.1](ir/axiom-ir-v0.md)：canonical JSON、内容身份、DAG、投影与迁移。
- [Axiom Evidence v0.1](evidence/axiom-evidence-v0.md)：义务、五态、反例、trust 与结论。
- [Evidence 验证说明](evidence/axiom-evidence-v0-validation.md)：现有规范验证与检查边界。
- [四题基准语料](benchmarks/keyed-finite-table-corpus-v0.md)：任务、候选、合成数据和预期断言。
- [Agent 实验预注册](experiments/agent-representation-preregistration-v0.md)：三表示、配对反馈、执行锁、评分与停止规则。
- [语言设计研究备忘](research/agent-oriented-language-design-evidence.md)：外部研究、限制与待验证假设；不替代正式规范。

已被摘要绑定的规范和实验材料不得为同步阶段措辞而直接改写。Evidence v0.1 的已知 group 义务漂移与 v0.2 迁移见 ADR 0009。

## 实现架构导航

| 边界 | 决策 |
| --- | --- |
| 首域、版本、生产实现语言 | [ADR 0002](adr/0002-first-target-domain-and-benchmarks.md)、[0003](adr/0003-version-identities-and-compatibility-layers.md)、[0004](adr/0004-raxc-production-implementation-language.md) |
| 验证后端、目标执行、生产管线 | [ADR 0005](adr/0005-first-verification-backend.md)、[0006](adr/0006-first-target-runtime-and-execution-path.md)、[0007](adr/0007-first-verification-first-compilation-pipeline.md) |
| 独立 checker 与 Evidence 迁移 | [ADR 0008](adr/0008-independent-checker-isolation-and-artifact-exchange.md)、[0009](adr/0009-axiom-evidence-v0-drift-and-migration.md) |
| payload 发布、launcher、产品宿主 | [ADR 0010](adr/0010-checker-runtime-payload-durable-registration.md)、[0011](adr/0011-checker-runtime-launcher-installation-and-activation.md)、[0012](adr/0012-product-checker-runtime-host-and-persistence-interface.md) |
| Darwin 强隔离与 container 状态 | [ADR 0013](adr/0013-darwin-checker-hard-isolation.md)、[0014](adr/0014-darwin-app-sandbox-container-state.md) |

ADR 定义决策和重评条件，不表示相关生产能力已完成；实现进度由当前状态维护。

## 机器契约

[契约总入口](../contracts/README.md)说明生成入口、指定态材料与实现证据的区别。

- [Independent Check](../contracts/independent-check-v0.1/README.md)：request / bundle / result。
- [Execution Profiles](../contracts/execution-profiles-v0.1/README.md)：options、limits 与 certificate 支持边界。
- [Toolchain & Adapter Registry](../contracts/toolchain-adapters-v0.1/README.md)：精确工具与候选 payload。
- [Toolchain Payload Acceptance](../contracts/toolchain-payload-acceptance-v0.1/README.md)：逐制品来源与局部验收。
- [Checker Runtime Payload Registration](../contracts/checker-runtime-payloads-v0.1/README.md)：payload 身份、登记、安装与激活契约。
- [Pipeline Artifacts](../contracts/pipeline-artifacts-v0.1/README.md)：义务、query、target、receipt 与失败门控。
- [Implementation Readiness](../contracts/implementation-readiness-v0.1/README.md)：实现入口与场景矩阵。
- [Checker Bundles](../contracts/keyed-finite-table-checker-bundles-v0.1/README.md)：完整指定态离线 bundle 与预期结果。

## 按需读取的切片审阅与历史记录

下列审阅单保存相应切片的事实、验证和当时边界，不承载统一的当前顺位，也不延续历史授权。

| 主题 | 记录 |
| --- | --- |
| Rust 初始身份 / 选择、USTAR、receipt | [首切片](checker-runtime-rust-first-slice-review.md)、[USTAR](checker-runtime-rust-ustar-slice-review.md)、[receipt](checker-runtime-rust-receipt-slice-review.md) |
| store 与 Darwin 文件系统 | [最小事务](checker-runtime-rust-store-slice-review.md)、[原语审阅](checker-runtime-darwin-filesystem-review.md)、[Darwin store](checker-runtime-darwin-store-slice-review.md) |
| qualification / attempt、result、manifest、spawn plan | [证据持久化](checker-runtime-evidence-store-slice-review.md)、[result consumer](checker-runtime-result-consumer-slice-review.md)、[manifest parser](checker-runtime-manifest-parser-slice-review.md)、[spawn plan](checker-runtime-spawn-plan-slice-review.md) |
| process 与隔离可行性 | [native process](checker-runtime-darwin-process-isolation-review.md)、[强隔离与 synthetic Linux 观察](checker-runtime-darwin-hard-isolation-review.md) |
| 早期状态、完整批次身份与实施流水 | [截至 2026-09-03 的原状态归档](records/status-through-2026-09-03.md) |

架构 probe 的历史观察与可重跑材料分别判断；强隔离审阅单已注明原 probe 源码未留存的复现缺口。

## 仓库入口

- [AGENTS.md](../AGENTS.md) / [CLAUDE.md](../CLAUDE.md)：逐字一致的启动规则与任务路由。
- [CONTRIBUTING](../CONTRIBUTING.md)、[行为准则](../CODE_OF_CONDUCT.md)、[安全报告](../SECURITY.md)。
- [PR 模板](../.github/PULL_REQUEST_TEMPLATE.md)、[Ruleset 说明](../.github/rulesets/README.md)、[分支治理 ADR 0001](adr/0001-branch-and-pr-governance.md)。
