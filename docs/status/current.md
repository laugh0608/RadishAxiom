# RadishAxiom 当前状态

更新日期：2026-08-23

## 当前阶段

项目处于首域语义、Axiom IR v0.1、Axiom Evidence v0.1、版本身份分层、四题版本化基准语料、Agent 对比实验预注册、`raxc` 生产实现语言、首个验证后端、首个目标执行路径、首版编译管线和独立 checker 隔离边界都已经形成的设计到受控实现阶段。checker request / bundle / result 的结构契约、工具链 / adapter 元数据身份清单、pipeline artifact 契约、实现就绪场景矩阵、四题完整 checker 离线 bundle，以及 cvc5 / Node / checker 的 options / limits 与 certificate 空能力矩阵已经物化。Go `go1.26.7` macOS arm64 host/source 两个精确 payload 已完成局部供应链验收；独立 Git 仓库 `RadishAxiomChecker` 已形成严格 request / manifest 解析、只读 bundle 布局与摘要核对的首个实现切片，并以精确工具链完成 macOS arm64 局部测试。下一阶段先冻结协议所需的不可变源码快照 SHA-256 身份，再进入 Axiom IR 严格结构解析；当前结果仍不代表完整 checker、Evidence / obligation 语义、`proved` 结论或六平台运行证据。

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
- 独立 checker 首个实现切片：单独 Git 仓库与 Go module `radishaxiom-independent-checker-go`，初始提交身份为 `edc55e3c37e7106d18a8046b0a289a6d6c354035`；只使用 Go 标准库，自有字节级 JSON/JCS 层拒绝重复 member、非法 UTF-8、非规范字节与未知字段，request / manifest / profile / limit set 闭合解析，bundle 只读核对普通文件、路径别名、长度、SHA-256 与 request 绑定。Git commit 仅作为开发来源记录，不能替代 result 契约要求的 `sha256:<不可变源码快照>`；该快照的规范化表示仍待冻结。
- Independent Check Contract v0.1：以 JSON Schema Draft 2020-12 描述 request / bundle manifest / result 抽象结构，并由独立生成器固定 JCS 字节、域摘要、check ID、闭合 code registry、四态聚合、一个严格 Evidence 拒绝 bundle 和 18 个结构 / 顺序 / 身份负例；当前只覆盖 ASCII fixture，不冒充完整 Unicode / JCS、Evidence 语义或 checker 实现。
- Toolchain & Adapter Identity Registry v0.1：固定 Rust `1.97.1`、Go `go1.26.7`、cvc5 `1.3.4`、Node.js `24.19.0` 的 source 与 Linux / macOS / Windows `amd64` / `arm64` 候选制品，登记官方来源、publisher 摘要、依赖审阅目标、许可证来源以及七个 build / adapter / target / invocation / pipeline / checker profile；Go macOS arm64 host/source 两项绑定版本化 acceptance record，其余 payload 保持 `not-accepted`，Rust 制品与 cvc5 source 摘要仍待权威元数据捕获。
- Toolchain Payload Acceptance v0.1：Go `go1.26.7` macOS arm64 host 64,772,572 bytes 与 source 34,150,794 bytes 的项目重算 SHA-256 均匹配 publisher 记录；只读检查 16,701 / 16,675 个 archive member，路径、重复项、类型、链接、setuid/setgid、权限/owner/mtime 和顶层布局通过，host/source 的 `VERSION`、`LICENSE`、`PATENTS`、36 项许可证/专利清单、3 份 vendor manifest 与 17 个模块一致。两项仅接受为 `accepted-for-controlled-build-input`，签名保持 `not-verified-no-signature-input`，不授权安装或执行。
- Execution Profile Contract v0.1：以单一 canonical manifest 固定 cvc5 `1.3.4` QF_UFLIA、Node.js `24.19.0` invocation 与 Go checker 的允许参数、清空环境、stdin / stdout framing、内部与外层资源边界、checker 七项确定性计数和结果形成停止线；Alethe / CPC 仅列为候选，受支持 certificate profile 集合为 0，proof / attestation 结论反向引用既有权威场景而不复制第二套 outcome、trust 或 code。
- Pipeline Artifact Contract v0.1：以三个 JSON Schema 和两个原始文本 profile 固定 obligation set、host data、SMT query、target module 与 pipeline receipt 的首批结构和规范字节；包含 gate 打开的完整 receipt、cvc5 timeout 后阻断 P6–P8 的 partial receipt、域摘要 / tool / cache 身份及 38 个关键负例。当前只覆盖 ASCII 合成 fixture 和 AX-B01 最小结构切片，不冒充义务完整性、parser、solver、target 执行、Evidence 或跨平台结果。
- Implementation Readiness Contract v0.1：以 canonical manifest 和 JSON Schema 统一 20 个 benchmark、ADR 0008 的 16 个 `CHK-*` 及 10 个 pipeline / readiness 场景，逐行固定输入、P0–P9、gate、artifact role、receipt、Evidence、独立结果 / 进程、trust / uncovered 与六平台注册适用范围；59 条 benchmark / ADR 来源要求全部具有反向场景覆盖，并以 13 个负例拒绝 gate 绕过、义务遗漏、artifact 篡改、伪造 cache hit、缺失 bundle 后错误接受、attestation 越权、错误结论聚合、进程失败伪装结果及未知 member / version / profile。全部场景保持 `specified`，`observed` 为 0。
- Keyed Finite Table Checker Bundle Contract v0.1：从 readiness 的稳定 ID 物化 20 个 benchmark、5 个跨契约场景和 3 个负例；每个目录仅含 request、manifest 与内容寻址 blob，完整绑定 IR、义务、pipeline receipt、Axiom Evidence、独立预期结果及 10 类 check ID。正确 / 错误 / 非法输入 / timeout、host mismatch、certificate required / attestation allowed、checker 内部资源不足与进程外层失败均保持独立聚合；全部仍为 `specified`，不冒充 checker、solver、Node 或六平台执行。
- 许可证：Apache License 2.0，并形成开放基础层与商业化边界策略。
- 仓库治理：`master` 稳定主线、`dev` 日常集成、PR 门禁和合并后回流策略。
- 当前仓库级验证：`./scripts/check-repo.sh` 或 `pwsh ./scripts/check-repo.ps1`。

## 今日进展（2026-08-23）

1. 将原 2063 行的 Pipeline Artifact Contract 生成器按公共编码、fixture 构造、校验、负例、Schema 和输出编排拆分为私有模块，保留原命令入口；拆分后 53 个生成文件及 contract 登记的 52 个原始字节摘要未变化。
2. 建立 `contracts/implementation-readiness-v0.1/` 与零第三方依赖生成入口，原始摘要绑定四题语料、首域语义、Axiom IR / Evidence、Independent Check Contract、Pipeline Artifact Contract、工具身份注册表及 ADR 0007 / 0008。
3. 物化 46 行 canonical 场景矩阵和 59 条来源覆盖：20 个 benchmark、16 个 `CHK-*`、10 个 pipeline / readiness 路径；重叠验收要求只通过 `source_refs` / `coverage` 映射，不复制第二套结果。
4. 每行固定 P0–P9、gate、artifact role、receipt、Evidence、独立 result / process、trust / uncovered 和平台注册适用范围；全部为 `specified`，`observed_scenarios` 为 0。wrong、`unknown`、invalid 及 P0 工具未验收路径明确禁止 target module、host output 与 `execute-host`。
5. 同批生成 JSON Schema、canonical manifest、域摘要、原始字节摘要及 13 个非法组合负例；Pipeline 专项、Readiness 专项和仓库级检查均通过。
6. 建立 `contracts/keyed-finite-table-checker-bundles-v0.1/` 与零第三方依赖生成入口，从 readiness manifest 的稳定场景 ID 生成 20 个 benchmark bundle、5 个跨契约 bundle 和 3 个缺失 / 篡改 / 省略负例。
7. 为四题 canonical IR 重建完整 benchmark obligation set，逐项物化节点总性 / 键基数、算术与聚合范围、row coverage、输出字段来源、guarantee / noninterference、具体输入、宿主输出、黄金比较及 trust-boundary；Evidence 状态、反例 world、attempt、receipt 和结论保持摘要闭合。
8. `CHK-CONCRETE-01` 将 host mismatch 保持为 `implementation_inconsistent`，`CHK-PROOF-01` / `02` 分别固定 certificate-required 的 `incomplete` 与 attestation-allowed 的 `accepted-with-trust`，`CHK-RESOURCE-01` 使用请求内 step budget 形成 `incomplete`，`CHK-PROCESS-01` 只生成外层进程失败而不伪造四态结果。
9. 每个 bundle 只物化 manifest 列出的普通 blob；request、manifest、Evidence、receipt、独立结果、条目和 check ID 均可离线重算，预期结果保持在输入 bundle 之外。readiness 的 20 个 benchmark 行已从 `specified-not-materialized` 收口为 `complete`，证据等级仍为 `specified`。
10. Checker Bundle、Independent Check、Pipeline Artifact、Implementation Readiness、Toolchain Registry、Benchmark Corpus 专项生成检查、JSON Schema Draft 2020-12 校验和仓库级 776 文件检查均已通过。
11. 建立 `contracts/execution-profiles-v0.1/` 与零第三方依赖生成入口；单一 manifest 物化 3 个执行 profile、5 个职责分离 limit set、5 个 canonical 投影、27 个逐字段 / 边界负例和来源摘要。
12. cvc5 profile 固定 safe / strict / QF_UFLIA、model / proof 生产与内部检查、`rlimit-per` / `tlimit-per` 和外层 stream / wall / memory 上限，拒绝路径参数、环境继承、随机 seed 与未登记 option；Node profile 固定 Permission Model、目标模块摘要解析只读 grant、BigInt / UTF-8 codec、进程 / 输出限制和能力 denylist。
13. checker profile 为 request 七项 limit 固定 parser、摘要、IR / obligation、replay、certificate、wall-clock 与逻辑内存的计数位置；`CHK-RESOURCE-01` 只允许内部检测后形成规范结果，`CHK-PROCESS-01` 的外层 kill / crash / 截断只能形成进程失败记录。certificate 支持集合保持为空，`CHK-PROOF-01` / `02` 继续作为唯一结论权威。
14. cvc5 / Node registry profile 更新为 `specified-not-materialized`，不改变 payload 的 `not-accepted`；28 个 checker bundle 全部新增 Execution Profile manifest normative blob 与 contract 来源绑定，摘要链按 registry → pipeline → readiness → execution profiles → bundles 顺序重算。
15. Toolchain Registry、Pipeline Artifact、Implementation Readiness、Execution Profile、Checker Bundle 专项重放、3 份 JSON Schema Draft 2020-12 校验、28 个 bundle profile blob 绑定检查和仓库级 848 文件检查均通过；全部仍为 `specified`，没有产生工具运行观察。
16. 从 registry 登记的官方 HTTPS URL 下载 Go `go1.26.7` macOS arm64 host 与 source 到隔离临时目录；host 单连接中断后断点续传，source 低速连接停止后按官方 Range 能力补齐连续区间。两项最终字节数和项目重算 SHA-256 都与 publisher 记录完全一致，没有安装或执行归档内容。
17. 新增 `scripts/inspect-toolchain-tar.py`，不释放 archive 即拒绝绝对 / 非规范 / 越界 / 重复路径、越界链接、特殊文件和 setuid/setgid，记录全成员元数据摘要、布局、必需文件、许可证/专利与 vendor module 清单；host/source 分别观察 16,701 / 16,675 个成员，链接与特殊文件均为 0。
18. 建立 `contracts/toolchain-payload-acceptance-v0.1/`：两份脱离绝对路径的观察、两份逐 payload acceptance record、registry / inspector 摘要绑定、两份 Draft 2020-12 schema 和 7 个负例；Go host/source 的许可证与依赖清单一致，最终作用域明确排除安装、执行、签名验证、源码可复现性、checker 正确性、跨平台等价和具体分发法律判断。
19. Toolchain Registry、Payload Acceptance、Pipeline Artifact、Implementation Readiness、Execution Profile 与 Checker Bundle 的完整摘要 DAG 已按顺序重算和重放；两份新 schema 通过 Draft 2020-12 校验，仓库级 866 文件检查通过。128 MiB 隔离下载目录及其中 13 个归档、分段和临时检查文件已经精确删除。
20. 在主仓库之外建立独立 Git 仓库 `RadishAxiomChecker`，固定 Apache-2.0、`go 1.26.0`、`toolchain go1.26.7`、`GOTOOLCHAIN=local` / `CGO_ENABLED=0` 使用方式和零第三方依赖边界；没有建立 submodule、相对 module 依赖、remote 或发布流水线。
21. 实现自有字节级严格 JSON/JCS、request / manifest / digest / profile / limit set 闭合解析，以及 bundle 目录只读 resolver；拒绝重复 member、非法 UTF-8、非规范 JSON、未知字段 / 版本 / profile、路径别名、symlink、非普通文件、未列出或缺失 artifact、长度 / SHA-256 不符和 request 绑定不符。
22. 导入 Independent Check Contract 的正负例与 28 个指定态 checker bundle，提交来源锁和原始摘要；测试覆盖 25 个身份层可解析场景，以及 artifact missing、digest mismatch、resource limit 三个当前切片可判定的拒绝路径。完整 IR、obligation、Evidence、certificate、结果装配和累计资源核算保持未实现。
23. 将已验收的 Go `go1.26.7` macOS arm64 host 精确解包到隔离临时前缀，以 `GOTOOLCHAIN=local`、`CGO_ENABLED=0` 运行 `go test -count=1 ./...` 与 `go vet ./...`，两项通过；临时工具链、归档和缓存随后精确删除，本机默认 Go 仍为 `go1.26.3`，没有修改 `mise`、PATH 或全局配置。
24. checker 初始历史拆为仓库边界 `d889be26c60146011a8d2ded05327737d5a76003`、严格 parser `b37b7c3253c50c2f2ef18f12e7fb628169426cd2` 和 bundle 语料 `edc55e3c37e7106d18a8046b0a289a6d6c354035` 三个可审阅提交；当前工作树干净且没有 remote。Git tree `cc12e8bac7a1d9a75dc605184b60a46ce63128ef` 只用于 Git 内部追溯，不冒充协议 SHA-256 源码身份。

本日没有安装任何工具或修改本机 Go 环境；只在隔离临时前缀执行已验收的 Go `go1.26.7` 和 checker 局部测试，随后删除临时工具链。没有执行 solver、Node、生产编译器或正式模型调用，没有构建发布 binary、生成独立 checker result、创建 remote、push、发布或产生六平台运行证据。

## 下一事项（2026-08-24）

下一主项是先冻结独立 checker 的不可变源码快照身份，再扩展 Axiom IR v0.1 严格结构 parser 小切片。继续遵守 Go checker 与生产 Rust `raxc` 分仓、分依赖图、分发布流水线和禁止复用生产 parser / normalizer 的 ADR 0008 边界。

1. 定义 `checker.source` 的规范输入集合、路径排序、文件类型 / mode、长度与原始字节编码、排除项和版本号，以可重放 canonical manifest 计算 SHA-256；Git commit 只作来源关联，不能直接填入 digest 字段，也不要求先创建 remote。
2. 为源码身份加入独立仓库门禁：干净 checkout 必须重算同一 manifest 与摘要，未跟踪源文件、symlink、生成漂移和 module / toolchain 身份不一致必须失败关闭；暂不构建 binary 或填写 `checker.artifact`。
3. 身份门禁稳定后，只实现 Axiom IR v0.1 的 canonical JSON 结构、闭合版本 / tag、内容寻址节点与 domain digest 核对，复用现有严格字节层但不复用生产实现；输入使用 28 个 bundle 已锁定 IR blob，并加入结构与摘要负例。
4. obligation 重建、Evidence 语义、certificate、四态 result、累计 wall-clock / 逻辑内存核算和 CLI 仍分别后置；cvc5、Node、Rust 与其余 Go 平台 payload 按真实实现依赖顺位验收。

完成标准：源码快照表示有版本化规范、实现、负例和可重放摘要，Axiom IR parser 对声明范围内的成功与拒绝路径形成小而完整的实现切片；现有生成器、28 个 bundle、checker 测试和两个仓库门禁继续通过。测试通过只形成实现检查证据，不升级为 `proved` 或六平台结论。

## 后续顺位

1. Go host/source 局部供应链门禁与 checker request / bundle parser 小切片已经通过；下一步先冻结 `checker.source` 的可重放 SHA-256 源码快照身份，不把 Git 对象 ID 或 payload acceptance 当成协议身份。
2. 源码身份稳定后扩展 Axiom IR 严格结构解析，再按小切片推进 obligation / Evidence 的独立重建；远程仓库创建、依赖安装、push、发布与部署仍分别授权。
3. cvc5、Node、Rust payload 与六平台原生结果按实现依赖逐批验收；certificate profile 只有在格式、checker、完整规则覆盖和 trust step 政策独立通过后才可加入非空支持集合。
4. 工具链可用且实现入口验证通过后，才准备 Agent 实验 execution lock 和正式模型调用。

首域语义、Axiom IR、Axiom Evidence 与较早 ADR 中“后续技术决策尚未冻结”的文字属于其接受时的范围说明；现行实现语言、验证后端、目标执行、生产管线和独立 checker 口径分别以 ADR 0004–0008 为准。首域语义的原始摘要已被基准语料和 Agent 实验注册绑定，Axiom IR 规范的原始摘要也已被实验注册绑定，不能为同步阶段措辞而原地改写。

## 尚未冻结

- 表面语法；
- Axiom Evidence 的具体证明 certificate 格式，以及独立 checker 的源码快照、Axiom IR / obligation / Evidence / result、累计资源核算和 CLI 实现；
- Rust / cvc5 / Node、其余 Go 平台 payload 的实际摘要 / 签名验收、包内依赖与许可证清单，Go host/source 的 publisher 签名与源码可复现性，首个受支持 certificate 格式 / checker / 规则覆盖，以及真实跨实现 / 跨平台语义结果；
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
- [Execution Profile Contract v0.1](../../contracts/execution-profiles-v0.1/README.md)
- [Toolchain & Adapter Identity Registry v0.1](../../contracts/toolchain-adapters-v0.1/README.md)
- [Pipeline Artifact Contract v0.1](../../contracts/pipeline-artifacts-v0.1/README.md)
- [Implementation Readiness Contract v0.1](../../contracts/implementation-readiness-v0.1/README.md)
- [Keyed Finite Table Checker Bundle Contract v0.1](../../contracts/keyed-finite-table-checker-bundles-v0.1/README.md)
- [有键有限表转换：首版类型化语义](../semantics/keyed-finite-table-semantics.md)
- [Axiom IR v0.1：规范化形式与版本策略](../ir/axiom-ir-v0.md)
- [Axiom Evidence v0.1：证据模型与独立检查边界](../evidence/axiom-evidence-v0.md)
- [有键有限表基准语料库 v0.1](../benchmarks/keyed-finite-table-corpus-v0.md)
- [Agent 表示与验证反馈对比实验预注册 v0.1](../experiments/agent-representation-preregistration-v0.md)
- [面向 Agent 的语言设计：证据与开放问题](../research/agent-oriented-language-design-evidence.md)
