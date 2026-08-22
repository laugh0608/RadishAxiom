# RadishAxiom 当前状态

更新日期：2026-08-22

## 当前阶段

项目处于首域语义、Axiom IR v0.1、Axiom Evidence v0.1、版本身份分层、四题版本化基准语料、Agent 对比实验预注册、`raxc` 生产实现语言、首个验证后端、首个目标执行路径、首版编译管线和独立 checker 隔离边界都已经形成的设计到受控实现入口物化阶段。checker request / bundle / result 的首批结构契约、工具链 / adapter 元数据身份清单与首批 pipeline artifact 契约已经物化；当前目标是扩展完整 checker bundle 和跨实现语义矩阵，同时保留工具 payload 与许可证的未验收停止线。在实现就绪门禁完成前不进入编译器 / checker 实现或正式模型调用。

## 已确定

- 项目定位：面向 AI Agent 的验证优先语言与可信语义层。
- 命名：`.rax`、`raxc`、Axiom IR、Axiom Evidence。
- 核心原则：约束显式、信任可见、验证状态分层、证据可复核、小可信内核。
- 首个目标领域：有键有限表的确定性转换；核心纯且无外部副作用，首批基准覆盖净额计算、键连接、守恒聚合和敏感字段非干扰。
- 首域语义：受界值、闭合记录、公开主键、无序有限表、显式缺失、无回绕算术、恰好一次连接、守恒聚合、关系非干扰和核心效果 `∅`。
- Axiom IR v0.1：严格版本化的 canonical JSON、内容寻址 DAG、无名称绑定、稳定摘要、无损 pretty 投影、结构化差异和显式迁移；未知字段与版本严格拒绝。
- Axiom Evidence v0.1：canonical JSON 证据清单、内容寻址义务、五种不可互换状态、可重放反例、显式 trust / uncovered、确定性结论聚合和独立义务重建；生产报告不能自证。
- 有键有限表基准语料 v0.1：四个任务各有一个正确候选、两个错误候选、基础 / 边界 / 无效输入、黄金输出，以及正确、错误、后端超时和输入拒绝场景的 Expected Evidence 断言；生成结果与摘要可离线重现。
- Agent 表示与验证反馈对比实验预注册 v0.1：固定 SQL、普通 JSON plan 和 Axiom projection 三种表示，两个模型条件、72 个 trial bundle、配对反馈、确认阈值、预算与停止线；正式调用仍须 execution lock 和单独授权。
- 版本身份：项目发布采用 `YY.M.RELEASE` CalVer 与 `dev` / `test` / `release` 轨道；语言语义、Axiom IR、Axiom Evidence 和工具实现分别标识，CalVer 不表达兼容性。
- `raxc` 生产编译器实现语言：Rust 2024 edition 与精确固定的 Rust `1.97.1` stable 工具链；该选择不适用于独立 checker，也不冻结表面语法或目标运行时。
- 首个验证后端：cvc5 1.3.4 独立 CLI；首版使用受容量约束的量化词自由 QF_UFLIA 类编码，优先评估 Alethe certificate，保留透明 `backend-attestation`，model 必须重放为规范反例，`unknown` / 超时 / 资源耗尽 / 协议错误失败关闭；不通过 FFI 或 SDK 链接进 `raxc`。
- 首个目标执行路径：从 canonical Axiom IR 确定性生成受限 ECMAScript ES module，由 Node.js 24.19.0 LTS 独立进程一次执行一个制品；语义整数只用 `BigInt`、文本拒绝未配对 surrogate、表输出按规范键排序，禁止 npm、动态代码和隐式宿主能力；production generator、host runtime 与 codec trust 保持可见，宿主语义差异映射为 `implementation_inconsistent`，不可归因的操作失败保持 `inconclusive`。
- 首版编译管线：`raxc-keyed-finite-table-pipeline-v0.1` 内容寻址制品 DAG；固定 IR 规范化、完整义务、单义务 query / cvc5 attempt、反例重放、输入检查、验证门控、Node target、宿主比较与 Evidence 装配顺序；缓存只复用精确身份的不可变制品，partial failure 进入非证明性 receipt，核心 `failed` / `unknown` 与输入拒绝均阻断目标生成和执行。
- 独立 checker：Go 1.26 语言基线与 `go1.26.7` 精确工具链；与生产 Rust `raxc` 分仓、分依赖图、分发布流水线和分进程，禁止复用生产 parser、normalizer、义务生成器、解释器或 adapter；以只读内容寻址 bundle 离线交换制品，独立结果在 Evidence 外区分 `accepted`、`accepted-with-trust`、`incomplete` 和 `rejected`，certificate / backend attestation、剩余 trust、资源失败与 checker 自身可信基保持可见。
- Independent Check Contract v0.1：以 JSON Schema Draft 2020-12 描述 request / bundle manifest / result 抽象结构，并由独立生成器固定 JCS 字节、域摘要、check ID、闭合 code registry、四态聚合、一个严格 Evidence 拒绝 bundle 和 18 个结构 / 顺序 / 身份负例；当前只覆盖 ASCII fixture，不冒充完整 Unicode / JCS、Evidence 语义或 checker 实现。
- Toolchain & Adapter Identity Registry v0.1：固定 Rust `1.97.1`、Go `go1.26.7`、cvc5 `1.3.4`、Node.js `24.19.0` 的 source 与 Linux / macOS / Windows `amd64` / `arm64` 候选制品，登记官方来源、publisher 摘要、依赖审阅目标、许可证来源以及七个 build / adapter / target / invocation / pipeline / checker profile；全部 payload、archive 内容和许可证仍明确为 `not-accepted`，Rust 制品与 cvc5 source 摘要仍待权威元数据捕获。
- Pipeline Artifact Contract v0.1：以三个 JSON Schema 和两个原始文本 profile 固定 obligation set、host data、SMT query、target module 与 pipeline receipt 的首批结构和规范字节；包含 gate 打开的完整 receipt、cvc5 timeout 后阻断 P6–P8 的 partial receipt、域摘要 / tool / cache 身份及 38 个关键负例。当前只覆盖 ASCII 合成 fixture 和 AX-B01 最小结构切片，不冒充义务完整性、parser、solver、target 执行、Evidence 或跨平台结果。
- 许可证：Apache License 2.0，并形成开放基础层与商业化边界策略。
- 仓库治理：`master` 稳定主线、`dev` 日常集成、PR 门禁和合并后回流策略。
- 当前仓库级验证：`./scripts/check-repo.sh` 或 `pwsh ./scripts/check-repo.ps1`。

## 近期事项

1. 下一步建议只完成“完整 checker bundle 与跨实现矩阵”第一批：把 AX-B01 的 correct / wrong、invalid input、backend timeout、host mismatch、gate 绕过、义务遗漏和 artifact 篡改映射到唯一合法阶段图、bundle 成员、稳定结果与停止线；不实现 Rust emitter、cvc5 adapter、Node launcher 或 checker。
2. 第一批矩阵必须复用现有 IR / Evidence、Independent Check Contract、Pipeline Artifact Contract 与工具身份，不新造平行格式；每个场景显式区分 production receipt、Evidence 结论和 independent result，并固定不得出现的 target / host artifact。
3. 随后扩展 AX-B02 至 AX-B04、八个错误候选、certificate policy、资源失败、进程崩溃和 Linux / macOS / Windows `amd64` / `arm64` 字节一致性；矩阵闭环后再提出只覆盖严格 request / bundle 解析、摘要核对和一组拒绝 fixture 的受控实现切片。
4. 工具 payload 验收是并行但独立授权的供应链任务：只有明确允许下载后，才可在隔离临时目录中获取已登记 artifact、重算 SHA-256、验证可用签名 / 来源并盘点包内依赖与许可证；当前 registry 不能作为安装或执行许可。

实现就绪契约包审阅通过后，才能提出第一个仅覆盖严格 request / bundle 解析、摘要核对和一组拒绝 fixture 的受控实现切片；工具链可用且纵向门禁通过后才准备 Agent 实验 execution lock。

首域语义、Axiom IR、Axiom Evidence 与较早 ADR 中“后续技术决策尚未冻结”的文字属于其接受时的范围说明；现行实现语言、验证后端、目标执行、生产管线和独立 checker 口径分别以 ADR 0004–0008 为准。首域语义的原始摘要已被基准语料和 Agent 实验注册绑定，Axiom IR 规范的原始摘要也已被实验注册绑定，不能为同步阶段措辞而原地改写。

## 尚未冻结

- 表面语法；
- Axiom Evidence 的具体证明 certificate 格式与独立 checker 内部实现；
- Rust / Go / cvc5 / Node payload 的实际摘要 / 签名验收、包内依赖与许可证清单、cvc5 options 和 Node invocation limits，以及完整 checker bundle、跨实现语义矩阵与实现就绪清单；
- Agent 实验的 execution lock、模型精确 revision、提示材料和 runner；
- 包管理、IDE、插件和发布载体；
- 首个具体产品版本、发布载体、发布记录与自动化；
- v1 后语言语义、Axiom IR、Axiom Evidence 及未来公共包的兼容性承诺。

在上述决策完成前，不为占位目的引入完整编译器骨架、运行时依赖、自动发布、CODEOWNERS 或技术栈专属 CI。

## 按需阅读

- [产品定义](../product-definition.md)
- [许可证与生态策略](../licensing-strategy.md)
- [仓库治理](../governance/repository-governance.md)
- [ADR 0001：分支、PR 与 Ruleset 治理](../adr/0001-branch-and-pr-governance.md)
- [ADR 0002：首个目标领域与基准任务](../adr/0002-first-target-domain-and-benchmarks.md)
- [ADR 0003：版本标识与兼容性分层](../adr/0003-version-identities-and-compatibility-layers.md)
- [ADR 0004：`raxc` 生产编译器实现语言](../adr/0004-raxc-production-implementation-language.md)
- [ADR 0005：首个验证后端与失败关闭边界](../adr/0005-first-verification-backend.md)
- [ADR 0006：首个目标运行时与执行路径](../adr/0006-first-target-runtime-and-execution-path.md)
- [ADR 0007：首版验证优先编译管线与制品协议](../adr/0007-first-verification-first-compilation-pipeline.md)
- [ADR 0008：独立 checker 的实现语言、制品交换与隔离边界](../adr/0008-independent-checker-isolation-and-artifact-exchange.md)
- [Independent Check Contract v0.1](../../contracts/independent-check-v0.1/README.md)
- [Toolchain & Adapter Identity Registry v0.1](../../contracts/toolchain-adapters-v0.1/README.md)
- [Pipeline Artifact Contract v0.1](../../contracts/pipeline-artifacts-v0.1/README.md)
- [有键有限表转换：首版类型化语义](../semantics/keyed-finite-table-semantics.md)
- [Axiom IR v0.1：规范化形式与版本策略](../ir/axiom-ir-v0.md)
- [Axiom Evidence v0.1：证据模型与独立检查边界](../evidence/axiom-evidence-v0.md)
- [有键有限表基准语料库 v0.1](../benchmarks/keyed-finite-table-corpus-v0.md)
- [Agent 表示与验证反馈对比实验预注册 v0.1](../experiments/agent-representation-preregistration-v0.md)
- [面向 Agent 的语言设计：证据与开放问题](../research/agent-oriented-language-design-evidence.md)
