# RadishAxiom 文档

`docs/` 是 RadishAxiom 的正式设计与决策入口。新会话先读取当前状态，再按任务进入产品、治理、ADR 或后续专题文档，不默认展开全部资料。

## 默认入口

- [当前状态](status/current.md)：当前阶段、已确定事项、明日事项、后续顺位、临时门禁与验证入口。
- [Agent 协作与执行规则](governance/agent-collaboration.md)：根入口之外按需读取的工作区、授权、实施、验证与交接细则。
- [产品定义](product-definition.md)：项目定位、命名、边界与首个里程碑。
- [许可证与生态策略](licensing-strategy.md)：开放基础层、商业化边界与长期贡献治理。
- [仓库治理](governance/repository-governance.md)：协作、Git、PR、CI 与 GitHub Rulesets 的统一口径。
- [ADR 索引](adr/README.md)：已经接受或废弃的长期决策。

## 仓库级入口

- [`AGENTS.md`](../AGENTS.md) / [`CLAUDE.md`](../CLAUDE.md)：启动级长期约束与任务路由，两份文件必须完全一致。
- [`CONTRIBUTING.md`](../CONTRIBUTING.md)：外部贡献流程与正确性要求。
- [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md)：社区讨论、审查与行为边界。
- [`SECURITY.md`](../SECURITY.md)：安全问题范围与私下报告方式。
- [PR 模板](../.github/PULL_REQUEST_TEMPLATE.md)：语义、信任、Evidence、验证与回流检查清单。
- [Ruleset 说明](../.github/rulesets/README.md)：远程保护模板与启用顺序。

## 研究备忘

- [面向 Agent 的语言设计：证据与开放问题](research/agent-oriented-language-design-evidence.md)：外部证据、证据限制、项目假设与最小实验要求；不作为正式语法或技术栈规范。

## 正式设计规范

- [有键有限表转换：首版类型化语义](semantics/keyed-finite-table-semantics.md)：首个目标领域的值、表、转换、契约、效果、失败、反例与信任边界。
- [Axiom IR v0.1：规范化形式与版本策略](ir/axiom-ir-v0.md)：规范化数据模型、canonical JSON、内容寻址、人类投影、语义差异与版本演进。
- [Axiom Evidence v0.1：证据模型与独立检查边界](evidence/axiom-evidence-v0.md)：义务身份、五种状态、反例、信任清单、结论聚合与独立复核。
- [ADR 0009：Axiom Evidence v0.1 漂移收口与 v0.2 迁移边界](adr/0009-axiom-evidence-v0-drift-and-migration.md)：冻结 v0.1 原始规范字节，记录 group 覆盖遗漏，并限定后续 v0.2 修正与摘要迁移。
- [ADR 0010：独立 checker runtime payload 的持久发布与登记](adr/0010-checker-runtime-payload-durable-registration.md)：选择 GitHub immutable Release asset，冻结专用 tag / distribution package、登记状态机、独立回读与 append-only replacement；当前精确 asset 已不可变发布并登记为 `registered-inactive`。
- [ADR 0011：独立 checker runtime launcher、安装与激活边界](adr/0011-checker-runtime-launcher-installation-and-activation.md)：冻结 active-only 精确目标选择、content-addressed 原子安装、三条 qualification companion、每次调用身份复核和外层失败不形成四态的边界。
- [ADR 0012：产品侧 checker runtime 宿主与持久化接口](adr/0012-product-checker-runtime-host-and-persistence-interface.md)：选择主仓 Rust 生产图中的内部 runtime 组件，冻结无网络安装核心、版本化 store 能力、单一 Rust result consumer 和独立 checker parser 隔离边界。
- [Checker runtime 首个 Rust 纵向切片审阅单](checker-runtime-rust-first-slice-review.md)：核对精确 `1.97.1` 来源、standalone / rustup component 身份缝隙、零第三方依赖选择，并记录首个 workspace / identity / target selection 实现、验证门禁与下一次授权停止线。
- [Checker runtime Rust 严格 USTAR 切片审阅单](checker-runtime-rust-ustar-slice-review.md)：记录 extraction-free 内外层归档清单实现、确定性 header profile、Python oracle 漂移收口、验证矩阵与安装停止线。
- [Checker runtime Rust installation receipt 切片审阅单](checker-runtime-rust-receipt-slice-review.md)：记录纯内存 canonical receipt 构造 / 重读、provider / registration / slot 身份绑定、跨实现黄金字节与 store 停止线。
- [Checker runtime Rust store 最小事务切片审阅单](checker-runtime-rust-store-slice-review.md)：记录 target lock、owned staging、exact publish / read / recovery、跨实现 tree digest，以及生产原生文件系统竞态停止线。
- [Checker runtime Darwin 生产文件系统边界审阅单](checker-runtime-darwin-filesystem-review.md)：记录 no-replace / descriptor-relative / full-sync 原语、威胁模型、私有平台 crate 与 `libc` 依赖选择、原生并发 / crash 矩阵和实施授权停止线。
- [有键有限表基准语料库 v0.1](benchmarks/keyed-finite-table-corpus-v0.md)：四个基准的生成目录、任务身份、合成数据、正确 / 错误候选和 Expected Evidence 断言。
- [Agent 表示与验证反馈对比实验预注册 v0.1](experiments/agent-representation-preregistration-v0.md)：三种表示、两种模型条件、配对反馈、指标、阈值、预算和停止规则。

## 机器契约与生成制品

- [实现就绪契约入口](../contracts/README.md)：由已接受规范和 ADR 生成的机器 schema、canonical fixture、负向样例与黄金摘要；这些制品不替代正式语义，也不表示生产实现已经完成。
- [Independent Check Contract v0.1](../contracts/independent-check-v0.1/README.md)：独立 checker request / bundle / result 的首批结构契约、严格拒绝 bundle 与负向矩阵。
- [Execution Profile Contract v0.1](../contracts/execution-profiles-v0.1/README.md)：cvc5 / Node / Go checker 的允许参数、内部与外层资源限制、结果形成边界和 certificate 空能力停止线。
- [Toolchain & Adapter Identity Registry v0.1](../contracts/toolchain-adapters-v0.1/README.md)：Rust / Go / cvc5 / Node 的精确版本、六平台候选制品、官方摘要来源、逐制品供应链状态和执行 profile 身份。
- [Toolchain Payload Acceptance v0.1](../contracts/toolchain-payload-acceptance-v0.1/README.md)：Go `go1.26.7` macOS arm64 host/source 与 Rust `1.97.1` rustup component/source 的摘要重算、只读 archive 观察、依赖 / 许可证库存、签名停止线与局部 acceptance。
- [Checker Runtime Payload Registration v0.1](../contracts/checker-runtime-payloads-v0.1/README.md)：闭合 checker source、target、artifact / provenance / acceptance、retention / fetch / 重新验证，以及 launcher / 安装 / qualification / 激活策略；当前 Rust 已实现 registry identity / target selection、严格内外层 USTAR 清单、installation receipt 与 Unix 临时根 store 最小事务，生产文件系统适配和完整 launcher policy 仍未实现，active runtime 为 0。
- [Pipeline Artifact Contract v0.1](../contracts/pipeline-artifacts-v0.1/README.md)：obligation set、host data、SMT query、target module 与 pipeline receipt 的首批规范字节、身份、gate / cache / partial failure 契约。
- [Implementation Readiness Contract v0.1](../contracts/implementation-readiness-v0.1/README.md)：20 个 benchmark、16 个 CHK-* 与 pipeline / readiness 路径的统一实现入口矩阵、来源覆盖和负向拒绝契约。
- [Keyed Finite Table Checker Bundle Contract v0.1](../contracts/keyed-finite-table-checker-bundles-v0.1/README.md)：28 个 readiness 场景的完整离线 bundle、Axiom Evidence、receipt、独立预期结果、进程失败边界与负例摘要链。

## 受控实现进展与下一入口

实现语言、验证后端、目标执行、生产管线和独立 checker 的架构决策已经确定，首批交换格式、身份契约、执行 profile 与 28 个离线 bundle 已进入仓库门禁。独立 checker 已在外部隔离仓库完成从严格 request / bundle、`checker.source`、锁定 Axiom IR / Evidence 检查，到有限执行、反例重放、output / proof support 审计、production conclusion 重算、四态聚合、canonical codec、累计资源、唯一产品 CLI，以及 payload 确定性候选归档的闭合路径；Checker Runtime Payload Registration v0.1 进一步固定 source → artifact / provenance / acceptance / candidate archive 及 retention / fetch / 重新验证边界，但当前 active runtime 仍为 0。

- 当前阶段、精确实现范围、下一事项与停止线统一以[当前状态](status/current.md)为准，不在文档索引复制易漂移的源码摘要或提交身份；
- 当前 `checker.source = sha256:401158...e3999` 的自包含 distribution 已完成精确构建、payload / distribution acceptance、不可变发布、发布后独立回读与 `registered-inactive` 登记；launcher policy、产品实现宿主与持久化接口均已冻结，依赖无关的一致性核心已形成；Rust `1.97.1` 的 rustup component/source payload 验收、当前用户级五组件安装，以及零第三方依赖的单 crate workspace、strict policy / record identity、target selection、extraction-free USTAR、installation receipt 与 Unix 临时根 store 最小事务切片均已完成，生产文件系统适配、真实 checker 安装与激活仍分别验证和授权；
- Go `go1.26.7` macOS arm64 host/source 与 Rust `1.97.1` macOS arm64 rustup component/source 已完成局部 payload 验收；Rust standalone、cvc5、Node 与其余平台仍须按真实实现依赖顺位完成摘要、签名 / 来源、包内依赖与许可证验收。
