# RadishAxiom 当前状态

更新日期：2026-08-23

## 当前阶段

项目处于首域语义、Axiom IR v0.1、Axiom Evidence v0.1、版本身份分层、四题版本化基准语料、Agent 对比实验预注册、`raxc` 生产实现语言、首个验证后端、首个目标执行路径、首版编译管线和独立 checker 隔离边界都已经形成的设计到受控实现入口物化阶段。checker request / bundle / result 的首批结构契约、工具链 / adapter 元数据身份清单、首批 pipeline artifact 契约与实现就绪场景矩阵已经物化；当前目标是依据统一矩阵扩展完整 checker 离线 bundle 和跨契约语义 fixture，同时保留工具 payload、许可证、完整 options / limits 与真实跨平台执行的未验收停止线。在全部实现就绪门禁完成并取得单独授权前不进入编译器 / checker 实现或正式模型调用。

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
- Implementation Readiness Contract v0.1：以 canonical manifest 和 JSON Schema 统一 20 个 benchmark、ADR 0008 的 16 个 `CHK-*` 及 10 个 pipeline / readiness 场景，逐行固定输入、P0–P9、gate、artifact role、receipt、Evidence、独立结果 / 进程、trust / uncovered 与六平台注册适用范围；59 条 benchmark / ADR 来源要求全部具有反向场景覆盖，并以 13 个负例拒绝 gate 绕过、义务遗漏、artifact 篡改、伪造 cache hit、缺失 bundle 后错误接受、attestation 越权、错误结论聚合、进程失败伪装结果及未知 member / version / profile。全部场景保持 `specified`，`observed` 为 0。
- 许可证：Apache License 2.0，并形成开放基础层与商业化边界策略。
- 仓库治理：`master` 稳定主线、`dev` 日常集成、PR 门禁和合并后回流策略。
- 当前仓库级验证：`./scripts/check-repo.sh` 或 `pwsh ./scripts/check-repo.ps1`。

## 今日进展（2026-08-23）

1. 将原 2063 行的 Pipeline Artifact Contract 生成器按公共编码、fixture 构造、校验、负例、Schema 和输出编排拆分为私有模块，保留原命令入口；拆分后 53 个生成文件及 contract 登记的 52 个原始字节摘要未变化。
2. 建立 `contracts/implementation-readiness-v0.1/` 与零第三方依赖生成入口，原始摘要绑定四题语料、首域语义、Axiom IR / Evidence、Independent Check Contract、Pipeline Artifact Contract、工具身份注册表及 ADR 0007 / 0008。
3. 物化 46 行 canonical 场景矩阵和 59 条来源覆盖：20 个 benchmark、16 个 `CHK-*`、10 个 pipeline / readiness 路径；重叠验收要求只通过 `source_refs` / `coverage` 映射，不复制第二套结果。
4. 每行固定 P0–P9、gate、artifact role、receipt、Evidence、独立 result / process、trust / uncovered 和平台注册适用范围；全部为 `specified`，`observed_scenarios` 为 0。wrong、`unknown`、invalid 及 P0 工具未验收路径明确禁止 target module、host output 与 `execute-host`。
5. 同批生成 JSON Schema、canonical manifest、域摘要、原始字节摘要及 13 个非法组合负例；Pipeline 专项、Readiness 专项和仓库级检查均通过。

本日没有下载或安装 Rust、Go、cvc5、Node payload，没有创建编译器 / checker 工程，没有执行 solver、Node、checker 或正式模型调用，也没有产生六平台运行证据。

## 明日事项（2026-08-24）

明日主项是依据已验收矩阵物化“有键有限表完整 checker 离线 bundle v0.1”，先让 AX-B01 至 AX-B04 的规范 IR、完整 obligation、Expected Evidence、pipeline artifact 引用、checker request / manifest / result 形成同一生成入口和唯一摘要链；这些仍是指定的离线验收 fixture，不冒充生产工具执行记录。

1. 建立版本化 bundle contract 与零第三方依赖生成器，从 readiness manifest 的稳定场景 ID 取用输入和预期，不重抄 benchmark、Evidence 或 `CHK-*` 结论。
2. 覆盖四题正确、八个错误、invalid input 与 backend timeout，补入 `CHK-CONCRETE-01` host mismatch、`CHK-PROOF-01` / `02` certificate policy、`CHK-RESOURCE-01` 和 `CHK-PROCESS-01` 所需的跨契约 artifact；missing / tampered / omitted 只作为负例。
3. 每个 bundle 只包含 manifest 列出的只读普通 blob，固定 byte length、SHA-256、format / role、Evidence digest、request check ID 和预期 independent outcome / code；禁止路径 fallback、网络补齐、symlink 或生产 cache 引用。
4. production receipt、Axiom Evidence 与 independent result 继续分别生成和校验；checker process failure 只形成外层运行失败 fixture，不写成四态 result。certificate 不可用时保留 `incomplete`，attestation 最多 `accepted-with-trust`。
5. 保持 `specified` / `observed` 分层并增加跨契约负例，至少拒绝 Evidence / IR / artifact 篡改、义务遗漏、bundle 缺失、host mismatch 错聚合、certificate 越权和旧 digest 引用。

明日完成标准：四题及上述跨契约行都能由 readiness scenario ID 解析到唯一 bundle / 期望结果；全部 blob 摘要、check ID、Evidence 结论、trust / uncovered 与拒绝码可离线重放；生成器、负例、文档链接及仓库级检查全部通过。

明日仍不下载或安装工具 payload，不创建生产编译器或 checker 工程，不执行 solver、Node、checker 或正式模型调用；工具供应链、完整 options / limits、真实六平台结果和首次实现授权继续保持停止线。

## 后续顺位

1. 工具 payload 验收作为独立授权的供应链任务，在隔离临时目录中重算 SHA-256、验证可用签名 / 来源并盘点包内依赖与许可证；当前 registry 不能作为安装或执行许可。
2. 完整 bundle 形成后冻结 cvc5 options、Node invocation limits、checker resource limits 与 certificate 能力矩阵，并将其纳入同一 readiness profile。
3. 场景矩阵、完整 bundle、options / limits 和供应链门禁审阅通过后，再提出 checker 严格 request / bundle 解析、摘要核对和拒绝路径的受控实现任务；远程仓库、依赖安装、push、发布与部署仍分别授权。
4. 工具链可用且实现入口验证通过后，才准备 Agent 实验 execution lock 和正式模型调用。

首域语义、Axiom IR、Axiom Evidence 与较早 ADR 中“后续技术决策尚未冻结”的文字属于其接受时的范围说明；现行实现语言、验证后端、目标执行、生产管线和独立 checker 口径分别以 ADR 0004–0008 为准。首域语义的原始摘要已被基准语料和 Agent 实验注册绑定，Axiom IR 规范的原始摘要也已被实验注册绑定，不能为同步阶段措辞而原地改写。

## 尚未冻结

- 表面语法；
- Axiom Evidence 的具体证明 certificate 格式与独立 checker 内部实现；
- Rust / Go / cvc5 / Node payload 的实际摘要 / 签名验收、包内依赖与许可证清单、cvc5 options、Node invocation limits、完整 checker bundle、certificate 能力与真实跨实现 / 跨平台语义结果；
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
- [Implementation Readiness Contract v0.1](../../contracts/implementation-readiness-v0.1/README.md)
- [有键有限表转换：首版类型化语义](../semantics/keyed-finite-table-semantics.md)
- [Axiom IR v0.1：规范化形式与版本策略](../ir/axiom-ir-v0.md)
- [Axiom Evidence v0.1：证据模型与独立检查边界](../evidence/axiom-evidence-v0.md)
- [有键有限表基准语料库 v0.1](../benchmarks/keyed-finite-table-corpus-v0.md)
- [Agent 表示与验证反馈对比实验预注册 v0.1](../experiments/agent-representation-preregistration-v0.md)
- [面向 Agent 的语言设计：证据与开放问题](../research/agent-oriented-language-design-evidence.md)
