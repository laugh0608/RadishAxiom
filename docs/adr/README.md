# 架构决策记录

`docs/adr/` 保存已经接受或明确废弃的长期技术与治理决策。ADR 记录“为什么这样决定”和稳定后果，不承载每日进度、临时任务清单或命令流水。

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
