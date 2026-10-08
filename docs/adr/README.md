# 架构决策记录

`docs/adr/` 保存拟议、已接受、已替代或已拒绝的长期技术与治理决策。ADR 记录“为什么这样决定”和稳定后果，不承载每日进度、临时任务清单或命令流水。

## 状态

- `Proposed`：正在讨论，尚不能作为实现依据。
- `Accepted`：已经采纳，代码、文档与治理配置必须保持一致。
- `Superseded`：已被后续 ADR 替代，并应链接替代项。
- `Rejected`：已评估但未采用，保留原因以避免重复讨论。

## 当前 ADR

- [ADR 0001：分支、PR 与 Ruleset 治理](0001-branch-and-pr-governance.md)
- [ADR 0002：首个目标领域与基准任务](0002-first-target-domain-and-benchmarks.md)
- [ADR 0003：版本标识与兼容性分层](0003-version-identities-and-compatibility-layers.md)
- [ADR 0004：`raxc` 生产编译器实现语言](0004-raxc-production-implementation-language.md)
- [ADR 0005：首个验证后端与失败关闭边界](0005-first-verification-backend.md)
- [ADR 0006：首个目标运行时与执行路径](0006-first-target-runtime-and-execution-path.md)
- [ADR 0007：首版验证优先编译管线与制品协议](0007-first-verification-first-compilation-pipeline.md)
- [ADR 0008：独立 checker 的实现语言、制品交换与隔离边界](0008-independent-checker-isolation-and-artifact-exchange.md)
- [ADR 0009：Axiom Evidence v0.1 漂移收口与 v0.2 迁移边界](0009-axiom-evidence-v0-drift-and-migration.md)
- [ADR 0010：独立 checker runtime payload 的持久发布与登记](0010-checker-runtime-payload-durable-registration.md)
- [ADR 0011：独立 checker runtime launcher、安装与激活边界](0011-checker-runtime-launcher-installation-and-activation.md)
- [ADR 0012：产品侧 checker runtime 宿主与持久化接口](0012-product-checker-runtime-host-and-persistence-interface.md)
- [ADR 0013：Darwin checker 强隔离宿主与虚拟执行边界](0013-darwin-checker-hard-isolation.md)
- [ADR 0014：Darwin App Sandbox container 与 runner 无状态边界](0014-darwin-app-sandbox-container-state.md)
- [ADR 0015：虚拟 checker 资源 profile 与宿主保证边界（Accepted）](0015-virtualized-checker-resource-profile.md)
- [ADR 0016：核心语义切片的分阶段实施入口（Accepted）](0016-core-semantic-slice-entry.md)
- [ADR 0017：IR v0.2 支持边界与显式迁移（Accepted）](0017-ir-v0.2-support-boundaries-and-migration.md)
- [ADR 0018：IR 派生义务 profile 与 P2 内部组件（Accepted）](0018-ir-derived-obligation-profile.md)
- [ADR 0019：map / filter 单世界查询生成（Accepted）](0019-map-filter-query-encoding.md)
- [ADR 0020：map / filter 节点总定义性查询（Accepted）](0020-map-filter-node-totality.md)
- [ADR 0021：map / filter 局部键与基数查询（Accepted）](0021-map-filter-key-cardinality.md)
- [ADR 0022：map / filter 行覆盖关系查询（Accepted）](0022-map-filter-row-coverage.md)
- [ADR 0023：纯核心空效果结构推导（Accepted）](0023-core-empty-effect-derivation.md)
