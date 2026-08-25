# RadishAxiom 当前状态

更新日期：2026-08-25

## 当前阶段

项目处于首域语义、Axiom IR v0.1、Axiom Evidence v0.1、版本身份分层、四题版本化基准语料、Agent 对比实验预注册、`raxc` 生产实现语言、首个验证后端、首个目标执行路径、首版编译管线和独立 checker 隔离边界都已经形成的设计到受控实现阶段。checker request / bundle / result 的结构契约、工具链 / adapter 元数据身份清单、pipeline artifact 契约、实现就绪场景矩阵、四题完整 checker 离线 bundle，以及 cvc5 / Node / checker 的 options / limits 与 certificate 空能力矩阵已经物化。Go `go1.26.7` macOS arm64 host/source 两个精确 payload 已完成局部供应链验收；独立 Git 仓库 `RadishAxiomChecker` 已形成严格 request / manifest、只读 bundle、`checker.source`、Axiom IR v0.1 严格结构与类型良构、Axiom Evidence v0.1 严格结构与身份、独立 obligation definition / ID 集合重建、expectation / 五态 / execution / tool / attempt / trust / support 闭合检查、counterexample 有限 world 与 `WF` 检查、concrete input artifact 重建和 assume / `Pre` 求值、锁定有限 IR DAG 的确定性执行和 proof-failure 目标重放、host / golden output artifact 重建与三方独立比较，以及 proof support artifact 真值审计与空 kernel / certificate 能力边界。20 个 `failed` counterexample 条目已按真实语义边界全部动态收口；213 个 producer `proved` claim 也已区分为 65 个 attestation-only 与 148 个缺少可检查材料的 kernel claim，独立证明数保持为 0。下一阶段进入生产 Evidence conclusion 的确定性重算与精确 refs 比对；当前结果不检查 counterexample minimality，不代表 kernel rule 或 certificate 已验真、backend attestation 已升级为独立 proof、独立四态 result 已形成，也不代表六平台运行证据。

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
- 独立 checker 首个实现切片：单独 Git 仓库与 Go module `radishaxiom.dev/independent-checker-go`，初始提交身份为 `edc55e3c37e7106d18a8046b0a289a6d6c354035`；只使用 Go 标准库，自有字节级 JSON/JCS 层拒绝重复 member、非法 UTF-8、非规范字节与未知字段，request / manifest / profile / limit set 闭合解析，bundle 只读核对普通文件、路径别名、长度、SHA-256 与 request 绑定。
- 独立 checker 源码快照身份 v0.1：闭合输入为除根 `.git` metadata 和 manifest 自身 sidecar 外的全部非目录 entry；路径限制为可移植 ASCII 组件并按 UTF-8 原始字节排序，只接受 `0644` / `0755` 普通文件，记录原始 byte length 与 SHA-256，并精确锁定 module、Go 语言基线和 toolchain 声明。canonical manifest 当前覆盖 649 个文件、176,903 bytes，`checker.source` 为 `sha256:56394aa8ec205b2980d9866af85fd449cc7a6949cb34715829f612b2704f4811`；Git commit / tree 只作来源追溯，不能替代该身份。
- 独立 checker Axiom IR v0.1 严格结构与类型良构 profile：先由 bundle 层核对 raw content SHA-256，再由自有严格 JSON/JCS 层解析 IR；当前闭合接受 28 个 bundle 实际使用的 4 类 value type、5 类 node、18 类 expression、2 类 contract 与 2 类 aggregate tag，核对全部 definition domain ID、声明 / 接口引用、节点 DAG / 可达性和完整文档 domain digest。enum / record / table 独立索引同时核对 field 类型 / 标签与 primary key；expression 类型器核对无名称环境、字段、操作数、分支、table binder 和 Bool 顶层；node 关系检查核对 filter、projection、join pair、group key / aggregate、主键与 capacity。成功仍只返回身份与顶层计数，不形成 obligation、Evidence 状态语义或四态结果。
- 独立 checker Axiom Evidence v0.1 严格结构与身份 profile：bundle 层先行核对 raw content SHA-256 和资源边界，再由 checker 自有 strict JSON/JCS 与 SHA-256 解析 28 个锁定场景实际使用的 13 个顶层 member、闭合 subject / profile / entry / result / support / counterexample / trust / uncovered / conclusion tag；独立重算 tool、execution、obligation、trust、uncovered definition ID 和完整 Evidence document domain digest，建立 artifact / tool / execution / obligation / trust / IR document 的直接引用索引，并分别绑定 Axiom IR raw content 与 document domain digest。25 个身份有效场景覆盖 25 份唯一 Evidence 与 12 份唯一 IR；成功只返回身份与顶层计数，不判断 obligation 完整性、五态或 conclusion。
- 独立 checker obligation completeness profile：Axiom IR parser 保留按规范 ID 顺序形成的 node / contract definition、输入 / 输出接口与输出字段，由 checker 自身生成 document / program、非 input node、numeric expression / aggregate、row coverage / group conservation、field origin、guarantee / noninterference 静态义务；Evidence profile、显式 `host-input` / `host-output` / `golden-output` execution I/O 边界和 trust entry 只决定对应 benchmark / trust definition。所有 definition 用 checker 自有 canonical encoder 与 `axiom-evidence-v0.1:obligation` 域重算 ID，不读取生产 `axiom-obligation-set` 作为真相。25 个身份有效场景中 24 个集合精确匹配，`chk-obligation-01` 以缺少 `numeric-range` 得到 `obligation-mismatch`；成功仍不判断五态、support、replay 或 conclusion。
- 独立 checker state / support profile：按 obligation expectation 精确限制 `proved`、`checked`、`unknown`、`failed` 与 `trusted`，逐项检查 execution kind / result、tool role、attempt reason、artifact I/O 闭包、proof query / response、backend trust assumption 和 trust category；`replay-counterexample` 只接受 `counterexample-replayer`，不为旧 fixture 角色提供 alias。24 个 obligation-complete 场景通过，状态关系负例稳定得到 `invalid-state-support`；成功只确认声明边界自洽，不验证 kernel rule、backend attestation、反例或具体数据内容为真，也不重算 conclusion。
- 独立 checker counterexample world / `WF` profile：IR parser 保留 enum 声明顺序、闭合 record / table、input / output interface 与 assume contract ID，Evidence parser 保留 `failed` counterexample、precondition 与 world；`VerifyCounterexampleWorlds` 独立检查 world 数量、接口锚定、`bool` / `int` / `text` / `enum` 值、整数范围、闭合字段、容量、主键唯一性与规范顺序。24 个 state / support 完整场景通过；四个 input-conformance 失败场景允许呈现预期的非 `WF` / `Pre` 输入，其他失败反例必须 `WF`。成功仍不解析绑定 concrete artifact、不求值 `Pre` 或程序，也不验证目标违反、trace、公开等价、minimality 或 conclusion。
- 独立 checker concrete input artifact / `Pre` profile：bundle verifier 只重开 manifest 已登记制品并再次核对文件身份、长度与 raw SHA-256；checker 严格解析 12 份唯一 `axiom-benchmark-data` `0.1` host input，按 benchmark 与 IR input interface 重建完整类型化 world，独立检查 role、闭合 table / row / field、scalar、范围、容量、主键与规范顺序。assume 求值只闭合锁定语料实际使用的 field / bound、Bool / Int、`le`、`forall_rows`、`lookup` 与 `match_option` 子集，并受步骤和逻辑内存限制；24 个 state / support / world 场景全部通过，四个 `invalid-input` 分别得到两个 `Pre` 失败和两个 `WF` 失败，Evidence witness world 必须与 artifact 投影一致。成功仍不执行 transform node，也不验证非输入目标违反、host / golden output、proof、conclusion 或 result。
- 独立 checker finite IR execution / counterexample target replay profile：复用 concrete input 的类型化 value / record / table、无名称表达式环境、相等与范围语义，闭合执行锁定语料实际使用的 5 类 node、18 类 expression 和 2 类 aggregate；按稳定 DFS 拓扑顺序执行并在每个节点后重检 table 声明、容量、键唯一性、规范顺序和整数范围，步骤、逻辑内存、非唯一 lookup / join 与语义范围失败均失败关闭。`VerifyCounterexampleTargets` 独立绑定 trace、observed、obligation 与 required field / key，重放 contract-guarantee、noninterference、key-cardinality、field-origin、row-coverage 和 group-conservation 六类实际目标；8 个 `prove + failed` proof target 全部得到真实违反，paired-input 非干扰按 IR 标签和受保护公开输出核对公开等价，9 个 input-conformance 条目继续由既有路径负责，3 个 host / output mismatch 条目由 concrete output profile 负责。成功不检查 minimality、proof support、conclusion 或 result。
- 独立 checker concrete output comparison profile：`axiom-benchmark-data` input / output 复用同一严格 envelope、scalar、record 与 table decoder，同时区分数据 envelope role 与 Evidence execution I/O role；output artifact 必须重建为完整 `WF` IR output world。checker 对相关 `host-input` 自身执行有限 IR，保持 semantic、host / actual 与 golden 三个来源；9 条相关 host execution 中 8 条正确路径满足 semantic = host，故障路径满足 semantic = golden ≠ actual，7 条 checked comparison 相等且 1 条 failed comparison 真实不等。该不等 comparison 的 3 个 failed entry 分别核对自身 subject、trace、observed actual / expected 与 input witness；unknown 不升级，生产 Node target 不执行。成功不检查 minimality、proof support、conclusion 或 result。
- 独立 checker proof support 真值与能力边界 profile：`InspectProofSupports` 重新打开并复算 obligation-set、QF_UFLIA query、cvc5 response 与 prover tool artifact 身份；生产 obligation-set 只能与已独立检查的 Evidence obligations、IR 双摘要、semantics 和 profile 精确比较，不能反向充当义务真相源。query 只核对闭合 ASCII SMT envelope、logic 与单次 status command，response 只核对精确 `sat` / `unsat` / `unknown` frame；`TargetInObligationSet` 与 `QueryTheoremVerified` 分开，后者在当前材料下恒为 false。24 个前置完整场景共 213 个 producer `proved` claim：65 个 backend attestation 精确绑定 execution、tool 和 `proof-backend` trust，148 个 `kernel-replay` 因 kernel rule / certificate 能力集合为空而全部形成 `missing-proof-material`；`certificate-required` 下另有 12 个 attestation 缺少证明材料，合计 160 个缺失项，独立证明数为 0。该审计成功不是独立接受结果，也不重算 conclusion。
- Independent Check Contract v0.1：以 JSON Schema Draft 2020-12 描述 request / bundle manifest / result 抽象结构，并由独立生成器固定 JCS 字节、域摘要、check ID、闭合 code registry、四态聚合、一个严格 Evidence 拒绝 bundle 和 18 个结构 / 顺序 / 身份负例；当前只覆盖 ASCII fixture，不冒充完整 Unicode / JCS、Evidence 语义或 checker 实现。
- Toolchain & Adapter Identity Registry v0.1：固定 Rust `1.97.1`、Go `go1.26.7`、cvc5 `1.3.4`、Node.js `24.19.0` 的 source 与 Linux / macOS / Windows `amd64` / `arm64` 候选制品，登记官方来源、publisher 摘要、依赖审阅目标、许可证来源以及七个 build / adapter / target / invocation / pipeline / checker profile；Go macOS arm64 host/source 两项绑定版本化 acceptance record，其余 payload 保持 `not-accepted`，Rust 制品与 cvc5 source 摘要仍待权威元数据捕获。
- Toolchain Payload Acceptance v0.1：Go `go1.26.7` macOS arm64 host 64,772,572 bytes 与 source 34,150,794 bytes 的项目重算 SHA-256 均匹配 publisher 记录；只读检查 16,701 / 16,675 个 archive member，路径、重复项、类型、链接、setuid/setgid、权限/owner/mtime 和顶层布局通过，host/source 的 `VERSION`、`LICENSE`、`PATENTS`、36 项许可证/专利清单、3 份 vendor manifest 与 17 个模块一致。两项仅接受为 `accepted-for-controlled-build-input`，签名保持 `not-verified-no-signature-input`，不授权安装或执行。
- Execution Profile Contract v0.1：以单一 canonical manifest 固定 cvc5 `1.3.4` QF_UFLIA、Node.js `24.19.0` invocation 与 Go checker 的允许参数、清空环境、stdin / stdout framing、内部与外层资源边界、checker 七项确定性计数和结果形成停止线；Alethe / CPC 仅列为候选，受支持 certificate profile 集合为 0，proof / attestation 结论反向引用既有权威场景而不复制第二套 outcome、trust 或 code。
- Pipeline Artifact Contract v0.1：以三个 JSON Schema 和两个原始文本 profile 固定 obligation set、host data、SMT query、target module 与 pipeline receipt 的首批结构和规范字节；包含 gate 打开的完整 receipt、cvc5 timeout 后阻断 P6–P8 的 partial receipt、域摘要 / tool / cache 身份及 38 个关键负例。当前只覆盖 ASCII 合成 fixture 和 AX-B01 最小结构切片，不冒充义务完整性、parser、solver、target 执行、Evidence 或跨平台结果。
- Implementation Readiness Contract v0.1：以 canonical manifest 和 JSON Schema 统一 20 个 benchmark、ADR 0008 的 16 个 `CHK-*` 及 10 个 pipeline / readiness 场景，逐行固定输入、P0–P9、gate、artifact role、receipt、Evidence、独立结果 / 进程、trust / uncovered 与六平台注册适用范围；59 条 benchmark / ADR 来源要求全部具有反向场景覆盖，并以 13 个负例拒绝 gate 绕过、义务遗漏、artifact 篡改、伪造 cache hit、缺失 bundle 后错误接受、attestation 越权、错误结论聚合、进程失败伪装结果及未知 member / version / profile。全部场景保持 `specified`，`observed` 为 0。
- Keyed Finite Table Checker Bundle Contract v0.1：从 readiness 的稳定 ID 物化 20 个 benchmark、5 个跨契约场景和 3 个负例；每个目录仅含 request、manifest 与内容寻址 blob，完整绑定 IR、义务、pipeline receipt、Axiom Evidence、独立预期结果及 10 类 check ID。fixture tool 已按既有 v0.1 角色精确声明 `counterexample-replayer`，生成器会拒绝 execution kind / tool role 错配；当前 `contract.json` 原始 SHA-256 为 `a349152cb2f838cf5acfaa66ef1676554f6d5f453d07314b3cc1b8c5579c7974`。正确 / 错误 / 非法输入 / timeout、host mismatch、certificate required / attestation allowed、checker 内部资源不足与进程外层失败均保持独立聚合；全部仍为 `specified`，不冒充 checker、solver、Node 或六平台执行。
- 许可证：Apache License 2.0，并形成开放基础层与商业化边界策略。
- 仓库治理：`master` 稳定主线、`dev` 日常集成、PR 门禁和合并后回流策略。
- 当前仓库级验证：`./scripts/check-repo.sh` 或 `pwsh ./scripts/check-repo.ps1`。

## 前序进展（截至 2026-08-24）

1. 盘点并冻结 28 个 checker bundle 实际使用的 Axiom Evidence v0.1 闭合 profile：13 个顶层 member、2 个 obligation profile、tool / execution / obligation / trust / uncovered definition domain、五种 result、两种 proof support、五种 counterexample、直接引用目标与确定性数组顺序；范围外组合继续失败关闭。
2. 在独立 checker 新增零第三方依赖 `internal/axiomevidence`，只使用 checker 自有 `strictjson`、canonical bytes、SHA-256 与闭合 tagged union；没有导入、复制或生成生产 Evidence parser、聚合器、义务生成器、反例重放器或测试 helper。
3. parser 逐项重算 tool、execution、obligation、trust、uncovered definition ID 和完整 Evidence document domain digest；obligation `result` 不进入 obligation ID，map 只用于摘要查找，不参与规范输出、摘要或拒绝顺序。
4. 建立 artifact、tool、execution、obligation、trust 与 IR document 的直接引用索引，拒绝悬空 producer / artifact / execution / obligation / trust、歧义 conclusion ref、错误 producer role 和 subject 外 IR document；subject artifact 必须解析到 `axiom-ir` `0.1`，并分别绑定独立 IR parser 的 raw content 与 document domain digest。
5. counterexample 当前只闭合解析锁定语料的五种 kind、`reduced` minimality、document / obligation / observation trace、world / table / record 结构、`enum` / `int` / `text` value 和两种 observed；不重放 world、`WF` / `Pre`、失败义务、公开等价或最小性。
6. 25 个身份有效场景全部完成 Evidence raw / document identity 与 IR subject 双摘要核对，覆盖 25 份唯一 Evidence 和 12 份唯一 IR；`chk-bundle-01`、`chk-digest-01`、`chk-resource-01` 继续在 artifact missing、raw digest、resource limit 层先行拒绝。
7. 新增未知顶层 member / version / support tag、非规范 artifact / conclusion ref 顺序、definition ID 漂移、悬空 producer、错误 subject artifact、Evidence document digest 与 IR subject 绑定不匹配负例；结构成功不判断 expectation / 五态、support 语义、obligation 完整性或 conclusion 正确性。
8. 新增 `docs/axiom-evidence-structure-v0.1.md` 并更新 checker README，明确锁定 artifact 清单中 options / policy 可由 receipt 间接绑定；当前 parser 只保证直接引用闭合，未读取 receipt，也不冒充 artifact graph 最终消费检查。
9. `checker.source` 重放为 619 个文件、170,987 bytes manifest 与 `sha256:45084c7cb2f4d0834fd3c8b1bd760140bc821fef5d280dffe6d3e0ce8cd2c8ca`。以本机 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0`、`GOPROXY=off` 和隔离 cache 运行源码身份专项门禁、全量 `go test -count=1 ./...`、`go vet ./...`、脚本语法与 `go list -m all`，全部通过且 module 集合只有 checker 自身；这不是精确 `go1.26.7` 或六平台证据。
10. 本切片没有安装依赖、执行 solver / Node / 生产编译器、构建 binary、生成 `checker.artifact` / 独立 result、创建 remote、push、发布或部署。checker 实现提交为 `2aaa3ab02ff8203155e2d156727478d3da086a85`、tree 为 `e879b69f184fc7b28dad0017ea25c274beaff820`；Git 身份只作来源追溯，不替代 `checker.source` 或协议摘要。
11. 从首域语义、Axiom IR、Axiom Evidence 与 12 份唯一 IR 独立盘点 verification / benchmark 义务生成位置；node、contract、expression path、interface、field、artifact 与 trust anchor 均由 checker 自有模型表达，没有读取、解析或导入生产 `axiom-obligation-set` 来形成期待集合。
12. Axiom IR parser 现在保留 canonical node / contract definition 与确定性接口 / 字段投影，生成 `ir-structure`、`effect-empty`、非 input node 的 `totality` / `key-cardinality`、四类转换的 `row-coverage`、group `group-conservation`、numeric expression / aggregate path、output field origin 和 contract 义务；group 覆盖与守恒保持两项不可合并义务。
13. Evidence parser 将 obligation definition 解码为结果无关的闭合 anchor union，并保留 profile、execution I/O 与 trust category。benchmark 的具体义务只从唯一 `host-input`、`host-output`、`golden-output` role 和 IR interface 生成；role 与 execution / tool / result 的语义配对明确留给下一切片。
14. `VerifyObligationCompleteness` 对每个独立 definition 重放 canonical bytes 与 obligation domain ID，再与 Evidence 集合精确比较；缺失、多余、错误 expectation、kind、anchor、path 和重复 definition 统一得到新登记的 `obligation-mismatch`，map 不参与规范输出或拒绝顺序。
15. 28 个锁定 bundle 中 24 个身份有效且非 obligation-negative 场景通过完整性比较，`chk-obligation-01` 从结构有效推进为缺少一个规范 `numeric-range` 的明确拒绝；`chk-bundle-01`、`chk-digest-01`、`chk-resource-01` 继续在 artifact missing、raw digest、resource limit 前置层拒绝。
16. 新增多余义务、expectation / path / anchor 漂移、同 anchor 冲突 expectation、非规范 obligation 顺序和 100 次重建稳定性负例；结构 / 身份正负例、12 份唯一 IR 及原有 bundle 门禁保持原结论。
17. 新增 `docs/axiom-evidence-obligation-completeness-v0.1.md` 并同步 checker README / 结构说明，明确 trust entry 一一对应不等于真实依赖已经完备，benchmark I/O role 只形成义务边界而不提前冒充 state / support 或 concrete replay。
18. `checker.source` 重放为 623 个文件、171,771 bytes manifest 与 `sha256:309aec52bdea5f5049502e408e08172185f742de56aaf3f7a1769867d25e5bac`。在真实 checker 以本机 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0`、`GOPROXY=off` 和隔离 cache 运行全量 `go test -count=1 ./...`、`go vet ./...`、源码身份门禁、脚本语法与 `go list -m all`，全部通过且 module 集合只有 checker 自身；实现提交为 `57f7431480a4f49faaba7cfc2b5fcec975a0edaa`、tree 为 `5ba0eb3c000bef599f7c33959b9e8769212eb961`。这不是精确 `go1.26.7` 或六平台证据。
19. 复核时确认 Axiom Evidence v0.1 的“义务生成位置”表没有显式列出 group `row-coverage`，而首域语义、Axiom IR AX-B03 映射和既有锁定 bundle 一致要求 group 同时具有覆盖与守恒义务。为避免原地改写已被摘要 DAG 绑定的公共规范，本切片只对锁定 profile 声明支持并记录该文档漂移；扩大 profile 或冻结新 Evidence 版本前必须以版本化修正和摘要迁移收口。
20. 截至 obligation completeness 子切片没有安装依赖、修改公共格式字节或重生成锁定 bundle，没有执行 solver / Node / 生产编译器、构建 binary、生成 `checker.artifact` / 独立 result、创建 remote、push、发布或部署。
21. 接受 [ADR 0009](../adr/0009-axiom-evidence-v0-drift-and-migration.md)：Axiom Evidence v0.1 原始规范字节保持不变，group `row-coverage` 与 execution kind / tool role 的公共修正在 v0.2 显式版本化；v0.1 → v0.2 必须重建 obligation、execution / tool、Evidence 与独立结果摘要，不跨版本复用 `proved`、`checked` 或 `trusted`。
22. 修正 checker bundle generator：形成 `replay-counterexample` execution 的 fixture tool 增加既有 `counterexample-replayer` role，生成期按全部 execution kind 检查精确 tool role；checker 不接受 `fixture-checker` alias 或默认成功 fallback。
23. 按完整内容寻址 DAG 重生成 558 个 bundle contract 文件并精确导入 checker；28 个场景的结构语义与 `specified` 状态未变，`contract.json` 原始 SHA-256 更新为 `a349152cb2f838cf5acfaa66ef1676554f6d5f453d07314b3cc1b8c5579c7974`。这次摘要迁移只修正无效 fixture 角色，不是 solver、Node、checker 或六平台运行观察。
24. Evidence parser 现在保留 artifact、tool、execution、obligation result、proof support、counterexample、attempt 与 trust 的状态关系输入；state / support validator 按稳定 ID 顺序检查 expectation / 五态矩阵、execution 完成状态、tool role、attempt reason、artifact I/O 闭包、query / response、backend trust assumption 和 trust category。
25. `proved` 只接受当前 profile 的 completed `prove` 边界及 `kernel-replay` / `backend-attestation` 精确引用，`checked` 按义务种类绑定 `check-fixture` / `execute-host` / `compare-output` 与制品闭包，`unknown` 的 reason 与 attempt result 必须对应，`failed` 只接受对应 completed replay / compare 边界，`trusted` 只完成同一 trust 的 `trust-boundary`。
26. 24 个 obligation-complete 场景逐项通过 state / support；`chk-bundle-01`、`chk-digest-01`、`chk-resource-01` 与 `chk-obligation-01` 继续保持前置拒绝优先级。新增 expectation / state 错配、缺失 support、错误 tool role、execution 未完成、attempt reason 漂移、attestation trust 缺失、response 漂移、checked artifact 遗漏、trusted scope 错配和 failed execution kind 错配 10 类负例，以及 100 次稳定重放。
27. 新增 checker `docs/axiom-evidence-state-support-v0.1.md`，并同步 README、Evidence 结构与 obligation completeness 说明；明确本切片只验证声明边界闭合，不检查 kernel rule、backend attestation、certificate、反例或 concrete data 真值，不重算 conclusion，也不形成独立四态 result。
28. `checker.source` 重放为 626 个文件、172,361 bytes manifest 与 `sha256:3a664b7158921a871bc9b4f39293b5b1017d09131190edfa93d6670a4a6ec211`。以本机 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0`、`GOPROXY=off` 和隔离 cache 运行全量 `go test -count=1 ./...`、`go vet ./...`、源码身份门禁、脚本语法、`go list -m all`、`gofmt -l .` 与差异卫生检查，全部通过且 module 集合只有 checker 自身；这不是精确 `go1.26.7` 或六平台证据。
29. 本 state / support 子切片没有安装依赖、执行 solver / Node / 生产编译器、构建 binary、生成 `checker.artifact` / 独立 result、创建 remote、push、发布或部署。checker 实现提交为 `f273ca3a0768fea96637771269f63582f0e70ce8`、tree 为 `bce5bb22725b0e6e184cc1f317296d626ab75f0e`；Git 身份只作来源追溯，不替代 `checker.source` 或协议摘要。
30. 盘点 24 个 state / support 完整场景中的 20 个 `failed` counterexample：覆盖 `single-row`、`row-pair`、`paired-input`、`missing-key` 与 `group`，实际值包含 enum、int 与 text；同时保留规范要求的 bool 支持。四个 invalid-input 场景的 witness 本来就可能违反 `WF` 或 `Pre`，不能与核心、宿主或输出失败反例使用同一“必须良构”规则。
31. Axiom IR parser 现在保留 enum member 声明顺序、record / table 定义、input / output table map 与 assume contract ID；具体数据模型以同一组类型定义表达 value、record、table 与 world，不另建绕过 IR 声明的 schema 口径。
32. Axiom Evidence parser 不再丢弃 `failed` counterexample、precondition 或 world，并补齐 `bool` value；复制与完整性路径保留完整 counterexample，避免状态检查后丢失重放输入。
33. 新增 `VerifyCounterexampleWorlds`：先绑定 Evidence subject IR，再按稳定 obligation ID 检查 counterexample kind 对应的 world 数量、precondition 是否来自 IR assume，以及每个 world 的接口、record / field、值类型与范围、enum 名义类型 / member、table capacity、主键唯一性和 canonical key order。除 input-conformance 失败外，反例 world 必须 `WF`；拒绝统一登记为 `counterexample-invalid`。
34. 24 个 obligation-complete / state-support 场景继续通过 counterexample world / `WF` 检查，四个 invalid-input 场景继续以其预期的非良构或 `Pre` 违反输入通过该层；`chk-bundle-01`、`chk-digest-01`、`chk-resource-01` 与 `chk-obligation-01` 保持更早拒绝优先级。
35. 新增 world 数量、未知接口、整数越界、未知 enum member、字段缺失、record 类型漂移、重复主键、缺少完整 assume 集和非 assume precondition 九类拒绝；合成 IR 测试另覆盖 bool / int / text / enum、enum 声明序主键、容量、逆序键、重复键和值 kind 漂移，并完成 100 次稳定重放。
36. 新增 checker `docs/axiom-evidence-counterexample-worlds-v0.1.md`，同步 README 与 Evidence 结构说明；明确当前 world 是 Evidence 内嵌有限投影，完整 host input 仍须在下一切片从绑定 artifact 重建，不能用部分 world 自证输入完整性或 `Pre`。
37. `checker.source` 重放为 631 个文件、173,357 bytes manifest 与 `sha256:68c589adf8a304398c9aec993622c62eb77c1af5bd83d7a5019b0fb0a8fdafe4`。以本机 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0`、`GOPROXY=off` 和隔离 cache 运行全量 `go test -count=1 ./...`、`go vet ./...`、源码身份门禁、脚本语法、`go list -m all`、`gofmt -l .` 与差异卫生检查，全部通过且 module 集合只有 checker 自身；这不是精确 `go1.26.7` 或六平台证据。
38. 本 counterexample world / `WF` 子切片没有安装依赖、执行 solver / Node / 生产编译器、构建 binary、生成 `checker.artifact` / 独立 result、创建 remote、push、发布或部署。checker 实现提交为 `517245714cd20436f7dcb7bec6f33020b43ec807`、tree 为 `9ce28e9f74019e0cfedf101351c8e53934e53e86`；Git 身份只作来源追溯，不替代 `checker.source` 或协议摘要，主仓库只同步状态文档与索引。
39. 从 24 个 state / support / world 完整场景盘点出 12 份唯一 host-input artifact 和 12 份唯一 IR；artifact role 分为 8 份 `input` 与 4 份 `invalid-input`。assume 实际子集只出现在 AX-B01 / B02，分别覆盖逐行整数上界与主键 lookup 存在性；AX-B03 / B04 的 invalid 输入由主键重复直接违反 `WF`。
40. checker strict JSON 增加面向外部数据制品的严格 document 入口：允许合法 JSON 空白、member 重排和 escape，但继续拒绝 duplicate member、BOM、非法 UTF-8、number / `null` 与资源超限；canonical request、manifest、IR 与 Evidence 入口保持原字节级要求。bundle verifier 增加 manifest 内 artifact 的受约束重开，重读时再次核对文件身份、长度与 raw SHA-256，防止前置验证后的路径或内容漂移。
41. 新增 `axiomir` concrete benchmark data 解码、完整 input world 重建、`WF` 与 assume / `Pre` 求值，并由 `axiomevidence.VerifyConcreteInputs` 将 execution 的全部 host-input 集、artifact 声明、benchmark、IR、obligation result 和 counterexample witness 严格绑定。`checked` 只接受 `input` 且 `WF ∧ Pre`；`failed` 只接受 `invalid-input` 且具有真实 `WF` 或 `Pre` 失败，关系不成立稳定得到 `concrete-check-mismatch`。
42. 24 个 state / support / world 完整场景全部进入 concrete input 检查，12 份唯一 artifact 完整重建；四个 invalid 场景稳定分类为 AX-B01 / B02 的 `Pre` 失败与 AX-B03 / B04 的 `WF` 失败。负例覆盖 artifact format / version / role / execution 绑定、digest、缺失或多余 table / field、scalar / enum、容量 / 主键顺序、world 投影、逻辑内存和步骤限制，并对 B02 invalid 完成 100 次稳定重放。
43. `checker.source` 随本切片和日终文档澄清重放为 637 个文件、174,521 bytes manifest 与 `sha256:cb892c672816b99f6e4d7a1c09ea0374c0f21e574fe2907fa99e9fae5cf5be92`。以本机 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0`、`GOPROXY=off` 和隔离 cache 运行全量 `go test -count=1 ./...`、`go vet ./...`、源码身份门禁、脚本语法与 `go list -m all`，全部通过且 module 集合只有 checker 自身；这不是精确 `go1.26.7` 或六平台证据。
44. 本 concrete input / `Pre` 子切片没有安装依赖、执行 solver / Node / 生产编译器、构建 binary、生成 `checker.artifact` / 独立 result、创建 remote、push、发布或部署。主仓库只形成一次日终文档提交；checker 的实现、说明与源码身份继续作为同一未提交切片保留，等待明日先行审阅和提交。Git 工作树或提交状态不替代 `checker.source` 或协议摘要。
45. 日终按顺序复核主仓库与 checker 今日各 4 个已提交变更及当前 concrete input / `Pre` 差异，确认 ADR 0009、锁定 bundle 角色迁移、Evidence 分层实现和主状态一致；早期 checker state / support 与 obligation completeness 说明补充后续 world / concrete 层入口，concrete input 说明澄清 strict JSON parser 与 profile decoder 的职责。21 台 UTM 虚拟机均已确认停止，没有删除虚拟机或快照。

## 昨日进展（2026-08-23）

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
25. 在 checker 仓库冻结 `checker.source` v0.1：输入集合不读取 Git index / ignore / remote，除根 `.git` metadata 与精确 manifest sidecar 外覆盖全部非目录 entry；目录只用于遍历，路径使用可移植 ASCII 组件和 UTF-8 byte order，文件只接受普通 `0644` / `0755`，长度与 SHA-256 均覆盖未经文本或换行转换的原始字节。
26. 新增零第三方依赖 `internal/sourceidentity`、canonical manifest sidecar 和 check / update 门禁；595 个输入文件形成 166,489 bytes manifest 与 `checker.source` `sha256:587e6d68e90e703cae786d4e382f2b627fb9e3468f29e1d3831bd703bf70699c`。负例覆盖未跟踪文件、原始字节 / mode / 生成漂移、module / Go / toolchain 身份变化、非可移植路径、symlink、自引用和 Git worktree metadata 排除。
27. 以本机默认 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0` 和隔离临时 cache 运行源码身份专项门禁、`go test -count=1 ./...`、`go vet ./...`、脚本语法检查与 `GOPROXY=off go list -m all`，全部通过且 module 集合只有 checker 自身；这不是精确 `go1.26.7` 或六平台证据。提交 `f975e731cc3cdc236b4cffd542c9446724517396` 与 tree `799aff7601ad4c10c7b2047f7051aeea58552889` 只作来源追溯，checker 工作树干净且仍无 remote。
28. 在 checker 自有 `strictjson` 上增加从已接受 Value 重放 canonical bytes 的无 number / `null` 编码路径；Axiom IR parser 逐项闭合检查顶层、声明、节点、表达式、输出与契约，并用 6 个固定 domain 对 definition 与完整文档重算 SHA-256，不导入或复制生产 Rust parser / normalizer。
29. 28 个锁定 bundle 中 25 个身份有效场景进入 IR parser，覆盖 12 份唯一 IR；`chk-bundle-01`、`chk-digest-01`、`chk-resource-01` 继续分别在 artifact missing、raw content digest 和 resource limit 层先行拒绝。12 份 IR 的 document domain digest 全部与既有锁定外部记录一致，错误候选保持结构良构而未被误拒绝。
30. 新增未知 member / version / tag、语义数组非规范顺序、definition domain ID 漂移、悬空输出节点引用和 document domain digest 不匹配负例；完整类型推导、字段覆盖、键 / 容量 / 控制依赖、obligation、Evidence、certificate、result 与 CLI 均未进入本切片。
31. `checker.source` 随实现重放为 605 个文件、168,322 bytes manifest 与 `sha256:05a6f75f4802ffad7370441530e27b7dcb497e0e5575c41be73e149d630e457a`。以本机 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0`、`GOPROXY=off` 和隔离 cache 运行全量 test / vet、源码身份门禁、脚本语法与 module 列表均通过；提交 `df65635d8bdecbb0513a7e2c6a881410c5ffcf90`、tree `37c1a29ec87c8ba4c1815b35f674c78bf2057e87` 只作来源追溯，checker 工作树干净、没有 remote，也没有精确 `go1.26.7` 或六平台新证据。
32. 将 Axiom IR parser 原来只作存在性查找的 enum / record / table map 收紧为闭合声明索引：value type 使用未导出 `valueKind`，record field 保存 label 与完整 type，table 保存 capacity、record type 与有序 primary key；map 只用于查找，不参与规范输出或摘要顺序。
33. table 构造现在拒绝空 / 重复 / 不存在 / `sensitive` primary key，并要求 key type 属于当前非可选 `bool` / `int` / `text` / `enum` 集合；12 份唯一 IR 的五种实际主键均为 `public text`。新增重新计算 definition domain ID 的完整最小 IR 正负例，分别覆盖四种可键类型、空 / 重复 enum、悬空 enum / record、字段缺失 / 重复、未知标签、错误整数范围和不受支持 `option`。
34. `checker.source` 重放为 606 个文件、168,514 bytes manifest 与 `sha256:9b6f7052b1bf186ed93a27063e6bab5ac94e4af4527bc9066b4084761cf12ac7`。以本机 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0`、`GOPROXY=off` 和隔离 cache 运行全量 test / vet、源码身份门禁、脚本语法与 module 列表均通过；提交 `d36621ed94437b60f8ce289702e4bdf792d5d72b`、tree `a06c26841151e600549cc7a6c4a72022f19db3ab` 只作来源追溯，checker 工作树干净且仍无 remote。
35. 为锁定 18 个 expression op 增加独立返回类型推导：基础类型保留完整 Int 范围与名义 enum ID，table row / `lookup` 只在内部形成 `Record` / `Option<Record>`；`bound` 使用无名称环境，`field` 核对 record 与字段，Bool / 相等 / 比较 / 整数算术、`if` / `match_option`、table binder / lookup / count / sum 均失败关闭核对操作数、分支和结果类型。
36. filter / map 按单个前驱声明 record 建立 `[source_row]`，lookup join projection 建立 `[left_row, right_row]`，formula 顶层环境为空；filter predicate 与 formula 顶层必须为 Bool，map / join 的每个 projection expression 必须可独立推导。重算 definition domain ID 的合成负例覆盖缺失字段、record / bound operand、Bool / `eq` / `le` / 算术 / 分支、`match_option`、lookup key arity / type、量词 / 聚合 predicate、sum value 和 node table scope；25 个身份有效场景与 12 份唯一 IR 全部保持良构通过。
37. `checker.source` 重放为 608 个文件、168,903 bytes manifest 与 `sha256:eeedfdbaa9e87773e388ca24428ae6a94b943b3918ab2ede9d4ba39ef5052852`。以本机 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0`、`GOPROXY=off` 和隔离 cache 运行全量 test / vet 与源码身份门禁均通过；提交 `a1d5b97f25044fb56418be70c9d8cc7275942508`、tree `35eee8d2cdd1f9e1aff3831b7bb5af93583b8159` 只作来源追溯，checker 工作树干净且仍无 remote。
38. node parser 不再丢弃 projection field name、lookup join pair、group key 与 aggregate 声明；独立关系检查按 canonical node ID 顺序核对 filter record / primary key / capacity，map / join projection 闭合与等型、主键直接保存 / 重命名和容量，以及 join pair 两侧字段存在与完整等型。`wrong-region-join` 的非键等型 pair 继续保持静态良构，“恰好一个右匹配”没有被错误提前假设或拒绝。
39. group 关系检查要求 keys 按顺序恰好等于输出 primary key、源字段 `public` 且可键、输出 key 等型、keys / aggregates 闭合覆盖 record、capacity 不超过输入；当前 `count` 固定 `Int[0, source_capacity]`，`sum` 只收口当前 profile 的非可选 Int 类型关系。重算全部受影响 definition domain ID 的合成正负例覆盖 4 类变换节点和 26 个失败关闭关系，25 个身份有效场景 / 12 份唯一 IR 全部保持通过。
40. `checker.source` 重放为 610 个文件、169,280 bytes manifest 与 `sha256:66859a2587068f64f8b4c94040deaccdc3439ee5507efce3326c28b8ae51845a`。以本机 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0`、`GOPROXY=off` 和隔离 cache 运行全量 test / vet 与源码身份门禁均通过；提交 `777df21ef23fd7586a2bf80183a01a7a2c6da950`、tree `ed28e141b974e7dc7da44e2160f5819977ad93b6` 只作来源追溯，checker 工作树干净且仍无 remote。

本日没有安装任何工具或修改本机 Go 环境；先在隔离临时前缀执行已验收的 Go `go1.26.7` 和 checker parser 局部测试并删除临时工具链，后续 checker 实现切片只使用本机默认 Go `go1.26.3` 与隔离临时 cache。没有执行 solver、Node、生产编译器或正式模型调用，没有构建发布 binary、生成 `checker.artifact` 或独立 checker result、创建 remote、push、发布或产生六平台运行证据。

本次文档收口前已复核双仓今日已提交历史与当前未提交差异：主仓库的契约 / payload 物化和 checker 状态提交，与 checker 的仓库边界、严格 request / bundle、锁定语料、`checker.source`、Axiom IR / Evidence 分层检查及 concrete input / `Pre` 实现逐项一致。checker `README.md` 与相关实现说明已覆盖实际边界；主仓库规范、机器契约 README 与 ADR 0008 没有因本切片产生公共语义或格式变更，保持不动。

## 今日进展（2026-08-25）

1. 日初核对双仓状态：主仓 `dev` 与 `origin/dev` 同步且工作树干净；checker `dev` 无 remote，保留上一日完整 concrete input / `Pre` 未提交切片，没有通过 reset、checkout 或清理命令制造基线。
2. 复核上一切片实现、说明、source identity 与全量门禁后，将 concrete input / `WF` / `Pre` 作为独立主题提交为 `9aa1646d4d01ca3d995773f25862e7c1a11acd28`，使 IR 执行从可追溯干净基线开始。
3. 重新按 Evidence obligation expectation 与 counterexample kind 盘点 20 个 `failed` 条目，纠正原计划“16 个非 input-conformance 反例”的错误口径：实际为 9 个 input-conformance 条目、8 个 `prove + failed` proof target 和 3 个 host / output mismatch 条目。前两类进入本日既有与新增检查路径，后三项按停止线留给 output comparison。
4. 将原 input-only evaluator 收口为共享 concrete evaluator，继续使用同一套类型化 value / record / table、De Bruijn bound 环境、相等、名义 enum、数学整数与范围语义；没有建立第二套 runtime schema 或放宽 `WF` / `Pre`。
5. 新增确定性 IR DAG 执行：覆盖锁定 5 类 node、18 类 expression 与 count / sum 两类 aggregate，按稳定 DFS 拓扑顺序处理与序列化顺序无关的 DAG，并在每个中间 table 后重新检查声明 record、字段、类型 / 范围、容量、主键唯一性和 canonical order。
6. 执行路径对算术溢出、join 零匹配 / 多匹配、输入 port / 前驱 / projection 漂移、未闭合字段、步骤与逻辑内存超限失败关闭；只有明确的语义执行失败可参与反例目标判定，资源或内部错误不能伪装成目标违反。
7. 新增六类 target replay：contract-guarantee、noninterference、key-cardinality、field-origin、row-coverage 与 group-conservation；严格绑定 Evidence trace、observed obligation、required field / key 与 IR obligation。8 个实际 proof target 全部独立重放为违反，paired-input 非干扰按 IR 标签和受保护公开输出同时核对公开等价。
8. 正确候选回归在全部锁定 `checked` host input 上执行，不以 golden output 自证；负例覆盖序列化节点倒序、绑定漂移、字段遗漏、group sum 源字段漂移、算术越界、目标不再违反、trace / observed / public input 漂移及两类资源耗尽，既有 24 个完整场景和前置拒绝顺位保持不变。
9. 新增 checker target replay 专题说明并同步 README、concrete input 与 counterexample world 边界；host / golden comparison、minimality、proof / attestation、conclusion / result 继续明确在本切片之外。
10. `checker.source` 重放为 643 个文件、175,710 bytes manifest 与 `sha256:155469e8e9c915cfc4cbb22a1bce6daadd431c86810b9dc44b74289d0c025be5`。以本机 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0`、`GOPROXY=off` 和隔离 cache 运行全量 `go test -count=1 ./...`、`go vet ./...`、源码身份门禁、脚本语法、`go list -m all`、`gofmt -l .` 与差异卫生检查，全部通过且 module 集合只有 checker 自身；这不是精确 `go1.26.7` 或六平台证据。
11. IR execution / target replay 提交为 `1f86de4d67d1c079d5fc20f77637caa9ef2299a4`、tree 为 `d0ff69b0b817b2e010b0ab284f496417d1583227`；checker 工作树干净且仍无 remote。Git 身份只作来源追溯，不替代 `checker.source` 或协议摘要。
12. 本日没有安装或升级依赖，没有执行 solver、Node、生产编译器或正式模型调用，没有构建发布 binary、生成 `checker.artifact` / 独立 result、创建 remote、push、发布或部署，也没有产生新的精确 `go1.26.7` 或六平台运行证据。
13. 从 24 个前置完整场景盘点 output 动态闭包：锁定 output data envelope 统一为 `role = golden-output`，但 Evidence execution 另以 `host-output`、`actual-output` 与 `golden-output` 区分语义身份；两层 role 不能互相替代或猜测。
14. 将 benchmark-data decoder 收口为同一方向化入口：input / output 共用严格 JSON、benchmark ID、Bool / Int / Text / 名义 Enum、record 与 table 解码，仅按所选 IR interface 集和允许 envelope role 分流；没有复制第二套 output codec。
15. 新增完整 output world 检查与无损相等关系：要求恰好完整 output interface，继续检查字段闭包、类型 / 整数范围、容量、主键唯一性和 canonical order；比较保留 interface、record type、field、value kind、enum identity 与显式数组顺序。
16. 新增 `VerifyConcreteOutputs`：从 output obligation 和 execution 图重建决定集合，追溯 actual 的 completed host producer，对每个相关 `host-input` 运行 checker 自身有限 IR，再分别核对 semantic、host / actual 与 golden；生产 target module 只核对边界，不执行。
17. 四题正确候选形成 8 条 host execution 和 7 条 checked comparison，全部满足 semantic = host = golden；`CHK-CONCRETE-01` 的故障 host execution 满足 semantic = golden ≠ actual。内容去重后共读取 8 个 output artifact，unknown output obligation 保持未决定，没有被升级。
18. `CHK-CONCRETE-01` 的一条真实不等 comparison 分别重放 3 个 failed entry：逐项核对 host / output subject、两步 trace、observed actual / expected、唯一 input-world witness 与 host producer，不能用 comparator `completed`、Evidence `failed` 或 raw bytes 不同自证。
19. 负例覆盖 output artifact format / envelope role、execute / compare I/O、checked host 输出对调、checked golden 替换、failed actual / expected 交换、trace / subject / witness 漂移、checked / failed 混用、raw digest、逻辑内存与 semantic step；关键 output 集成连续 20 次稳定通过，既有早期拒绝顺位保持不变。
20. 新增 checker concrete output comparison 专题说明，并同步 README、state / support、concrete input 与 target replay 的方法停止线；minimality、proof / attestation、conclusion / result 仍明确在本切片之外。
21. `checker.source` 重放为 646 个文件、176,310 bytes manifest 与 `sha256:d8496c37c6dacd282749b583ee99d2ec992c240700dee3374a2ad3901f531448`。以本机 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0`、`GOPROXY=off` 和隔离 cache 运行全量 `go test -count=1 ./...`、`go vet ./...`、20 次关键重放、源码身份门禁、脚本语法、`go list -m all`、`gofmt -l .` 与差异卫生检查，全部通过且 module 集合只有 checker 自身；这不是精确 `go1.26.7` 或六平台证据。
22. concrete output comparison 提交为 `99765b564bcf3f3d4548bac68f739b389d149840`、tree 为 `6339d65eb9f39c82b4d9512b27830d9da5cd6d24`；checker 工作树干净且仍无 remote。Git 身份只作来源追溯，不替代 `checker.source` 或协议摘要。
23. 盘点 24 个前置完整场景的全部 proof support：共 213 个 producer `proved` claim，其中 148 个为 `kernel-replay`、65 个为 `backend-attestation`；20 个场景存在完成的 prove execution，四个 backend-timeout 场景没有 `proved`，既有 timeout / failed / checked / trusted 状态没有被新路径改写。
24. Evidence parser 不再丢弃 prover tool 的 artifact / name / immutable version 和 trust 的精确 scope；`InspectProofSupports` 按 obligation ID 稳定排序，重新核对每项 proved→execution→tool / role 关系，并通过 `bundle.Verified.ReadArtifact` 重开共享 obligation-set、query、response 与 tool artifact，逐一复算 raw SHA-256。
25. 生产 `axiom-obligation-set` 仍不参与独立 obligation 生成；只有在 completeness 已通过后，才核对其 IR raw / document 双摘要、semantics、profile、全部 definition / domain ID、排序和基数与已检查集合完全一致。query inspector 只接受闭合 QF_UFLIA ASCII envelope、平衡括号、有限顶层 command 和唯一 `check-sat`；cvc5 response 只接受单个精确 status frame，不解释 SMT term 或把 status 当证明。
26. checker 源码内显式能力集合保持 `KernelRuleProfiles = []`、`CertificateProfiles = []`。148 个 `kernel-replay` 全部以 `kernel-replay-material-unavailable` 形成缺失材料，wrong 场景共享 response 为 `sat` 时也不会因 producer tag 而升级；65 个 backend attestation 只确认 query / response / execution / tool / trust 闭包并保留 backend trust，独立证明计数恒为 0。
27. proof-support 子策略分类与既有场景一致：`attestation-allowed` 下 53 个 claim 可作为 attestation-only 继续并保留 trust；`CHK-PROOF-01` 的 12 个 attestation 在 `certificate-required` 下明确缺少材料。加上 148 个无可重放材料的 kernel claim，共 160 个 `MissingProofMaterial`；审计方法返回成功不等于所有 claim 已证明。
28. 新增 obligation-set format / IR subject、query logic / 重复 status command、response status、attestation trust scope、proved execution、raw digest、缺失 reader、逻辑内存与 semantic step 漂移负例；另以 wrong 场景锁定 `sat + kernel-replay` 失败关闭，并连续 100 次确认 finding / artifact / trust 的确定性顺序。24 个场景总回归精确锁定 213 / 65 / 148 / 53 / 160 口径。
29. 新增 checker proof support 专题说明并同步 README；`checker.source` 重放为 649 个文件、176,902 bytes manifest 与 `sha256:884a786f5be9533bba28e456f2b9173b3235dc6ff5d70282fe7814e65fe7dbb1`。以本机 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0`、`GOPROXY=off` 和隔离 cache 运行全量 `go test ./...`、`go vet ./...`、源码身份门禁与差异卫生检查全部通过；提交为 `068ae7e956987c490ee95d832e6a2e9e09938b81`、tree 为 `230b73eb9501c1b1d235c11beb8ce827384c43a9`，checker 工作树干净且仍无 remote。本切片没有运行 cvc5、Node 或生产 compiler，没有生成 checker binary、`checker.artifact`、独立 result 或六平台证据。
30. 日终逐项复核本日已有开发提交：checker 的 concrete input / `Pre`、有限 IR target replay、concrete output comparison 与 proof support 四笔实现提交，以及主仓对应三笔状态提交，代码、测试、专题说明与当前阶段口径一致；没有发现需要修改公共 Axiom IR、Axiom Evidence、Independent Check Contract、ADR 或机器契约的语义 / 格式漂移。
31. checker 早期专题说明仍把后续调用链停在 concrete output，且 proof support 负例清单漏记代码已覆盖的 `proved` execution 绑定漂移；现已同步 Evidence 结构、obligation completeness、state / support、concrete output 与 proof support 五份说明，重放 `checker.source` 为 649 个文件、176,903 bytes manifest 与 `sha256:56394aa8ec205b2980d9866af85fd449cc7a6949cb34715829f612b2704f4811`。文档提交为 `ab9f4ed9e63c87bc57f012ff32a047b6710b590d`、tree 为 `f700b086af9c7d2dff898c2ec1abbcd19ab745c2`；Git 身份只作来源追溯。
32. 日终以本机 Go `go1.26.3`、`GOTOOLCHAIN=local`、`CGO_ENABLED=0`、`GOPROXY=off` 和隔离 cache 复跑 checker 全量 `go test -count=1 ./...`、`go vet ./...`、源码身份门禁与差异卫生检查，全部通过；checker `dev` 工作树干净且仍无 remote。没有安装或升级依赖，没有执行 solver、Node、生产编译器或正式模型调用，没有构建 binary、生成 `checker.artifact` / 独立 result、push、发布、部署或形成新的精确 `go1.26.7` / 六平台证据。

## 下一事项（2026-08-26）

具体输入、有限 IR、失败目标、host / golden output 与 proof support 真值边界已经形成干净提交。下一步进入生产 Axiom Evidence `conclusion` 的确定性重算与精确 refs 比对；重点是不抄录 producer conclusion，也不把 Evidence conclusion 与独立 checker 四态 result 混为一层。

1. 盘点并保留 24 个前置完整场景的 producer conclusion kind / refs，锁定当前真实分布：7 个 `satisfied`、4 个 `input_rejected`、8 个 `violated`、4 个 `inconclusive`、1 个 `implementation_inconsistent`；`structure_rejected` 规则继续闭合实现但不得用无法形成有效 Document 的前置拒绝伪造正例。
2. 按规范优先级从已经检查的 obligation definition / state、failed target / comparison 与 execution 完成状态重算 conclusion：结构失败优先，其次 input rejection、host / output inconsistency、其余核心违反、unknown / 未完成 / 缺失，最后才是 satisfied。已重放 failure 必须优先于并存 unknown，但 unknown attempt 仍保留在 Evidence。
3. 独立形成决定性 ref 集并按 `(kind, value)` 稳定排序：input failure 只引用对应 input-conformance obligation，implementation inconsistency 引用 host / output failed obligation，其他 violation 引用其 failed obligation，inconclusive 引用全部阻断 obligation / execution；`satisfied` refs 必须为空。
4. 将重算 kind 与 refs 和 producer conclusion 精确比较；任何种类、遗漏、多余、错类、错值、排序或优先级漂移都使用 Independent Check Contract 已冻结的 `conclusion-mismatch` 失败关闭，不通过 warning、fallback 或读取 expected result 继续。
5. 增加六类 conclusion、failure + unknown 优先级、refs 交叉绑定、生产 conclusion 篡改、资源边界与重复运行负例；保持 proof audit 的 0 个独立 proof、65 个 attestation 和 160 个 missing material 不被 conclusion `satisfied` 隐藏。

停止线：本切片只重算并比较生产 Evidence conclusion，不聚合 `accepted` / `accepted-with-trust` / `incomplete` / `rejected` 独立结果，不生成 checks / TCB / checker identity companion，不修改公共 Evidence / result / code 格式，不检查 minimality，也不执行 solver、生产 Node target 或生产编译器。

完成标准：24 个前置完整场景的 conclusion kind 与精确 refs 全部由 checker 自身按规范优先级重算并匹配；结论篡改稳定得到 `conclusion-mismatch`，producer `satisfied` 不会覆盖 proof support missing / remaining trust；全量 test / vet、`checker.source` 与主仓库级门禁继续通过。

## 后续顺位

1. Go host/source 局部供应链门禁、checker request / bundle parser、`checker.source` v0.1、当前锁定 Axiom IR 结构 / 类型良构与有限执行、Axiom Evidence 结构 / 身份、obligation completeness、state / support、counterexample world / `WF`、concrete input / `Pre`、8 个 proof-failure target replay、host / golden output comparison 与 proof support 真值边界已经通过；下一步推进 production conclusion recompute，Git 对象 ID 与 payload acceptance 继续不能冒充协议源码身份。
2. production conclusion 精确重算之后再进入独立 check outcome、remaining trust / missing artifact 与四态 result 聚合；当前离线双仓工作不需要 checker remote，远程仓库创建、依赖安装、push、发布与部署仍分别提醒并授权。
3. cvc5、Node、Rust payload 与六平台原生结果按实现依赖逐批验收；certificate profile 只有在格式、checker、完整规则覆盖和 trust step 政策独立通过后才可加入非空支持集合。
4. 工具链可用且实现入口验证通过后，才准备 Agent 实验 execution lock 和正式模型调用。

首域语义、Axiom IR、Axiom Evidence 与较早 ADR 中“后续技术决策尚未冻结”的文字属于其接受时的范围说明；现行实现语言、验证后端、目标执行、生产管线和独立 checker 口径分别以 ADR 0004–0008 为准。首域语义的原始摘要已被基准语料和 Agent 实验注册绑定，Axiom IR 规范的原始摘要也已被实验注册绑定，不能为同步阶段措辞而原地改写。

## 尚未冻结

- 表面语法；
- Axiom Evidence 的具体证明 certificate 格式、非空 kernel / certificate 能力，以及独立 checker 的 conclusion / result、累计资源核算、`checker.artifact` 和 CLI 实现；
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
- [ADR 0009：Axiom Evidence v0.1 漂移收口与 v0.2 迁移边界](../adr/0009-axiom-evidence-v0-drift-and-migration.md)
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
