# ADR 0007：首版验证优先编译管线与制品协议

日期：2026-08-22

状态：Accepted

用途：冻结 RadishAxiom 首版编译管线的阶段图、制品身份、验证门控、失败保留、缓存与离线重放规则，为独立 checker 的隔离边界和首个受控实现提供稳定生产路径。

读者：编译器、验证、代码生成、Evidence、宿主执行、独立 checker、基准、构建与发布维护者，以及审阅首版纵向闭环的协作者。

不包含：`.rax` 表面语法与 source-to-IR、Rust 模块结构、CLI 参数和数值退出码、独立 checker 的语言与实现、最终 certificate 格式、依赖安装、编译器骨架、发布打包或远程 artifact 服务。

## 背景与约束

[Axiom IR v0.1](../ir/axiom-ir-v0.md)已经冻结严格解析、规范化、内容寻址和结构拒绝；[Axiom Evidence v0.1](../evidence/axiom-evidence-v0.md)已经冻结 artifact、tool、execution、义务、五种状态和结论聚合；[ADR 0005](0005-first-verification-backend.md)选择一项义务一个 cvc5 1.3.4 独立进程；[ADR 0006](0006-first-target-runtime-and-execution-path.md)选择验证门控后的确定性 ECMAScript module 生成与 Node.js 24.19.0 独立执行。

管线必须组合这些决策，不能通过实现顺序改变其语义：

- 非规范输入不能在未知字段、错误引用、类型错误或非空效果被忽略后“修好”；
- `sat` model 不能直接成为 `failed`，`unsat` 不能因命令成功直接成为可独立证明；
- 任一必需核心义务为 `failed` / `unknown`、输入被拒绝或 assurance policy 未满足时，不能生成或执行目标程序；
- 生产 Evidence 必须完整、自洽且内容寻址，但不能冒充独立 checker 结果；
- 操作失败与具体语义失败必须分开，partial artifact 和历史 attempt 不能被后续成功覆盖。

Axiom Evidence v0.1 没有 `generate-query`、`generate-target` 或 `assemble-evidence` execution kind，也没有 `target-generator` tool role。本 ADR 不原地扩展已被语义、基准和实验绑定的 Evidence v0.1；查询编码、目标生成和装配过程由版本化的非证明性 pipeline receipt 记录，其输出制品仍通过现有 `prove` / `execute-host`、tool identity 与显式 trust 进入 Evidence。

## 候选管线模型

| 模型 | 优点 | 主要问题 | 结论 |
| --- | --- | --- | --- |
| 单体顺序命令 + 可变工作目录 | CLI 简单，原型代码量小 | 阶段边界、输入身份、缓存和早停结果容易隐藏；失败后难以证明实际消费了哪些字节 | 不采用 |
| 内容寻址的显式制品 DAG | 每个阶段输入、输出、工具和停止线可审阅；适合离线重放与独立 checker | 需要维护 artifact 格式、receipt 和引用完整性 | **采用** |
| 长驻 daemon / 增量 solver session | 可降低重复解析与求解成本 | 引入隐藏状态、跨请求缓存、并发与取消语义；违背一义务一进程和首版可重放边界 | 首版不采用 |

## 决策

首版生产管线采用稳定 profile `raxc-keyed-finite-table-pipeline-v0.1`，实现为**内容寻址、失败关闭、可离线重放的显式制品 DAG**。

profile 提供两个闭合 mode：

| mode | Evidence profile | 范围 |
| --- | --- | --- |
| `verification` | `keyed-finite-table-verification` `0.1` | canonical IR、完整核心义务、证明 / 反例、trust 与 verification Evidence；没有具体宿主执行 |
| `benchmark-node24` | `keyed-finite-table-benchmark` `0.1` | verification 全部内容，加版本化输入、Node target、宿主输出、黄金比较和 benchmark Evidence |

首版入口是 Axiom IR candidate bytes，不是 `.rax` source。未来 source-to-IR 只能作为本管线之前的独立阶段，输出 canonical Axiom IR 与摘要绑定的来源映射；它不能改变本 ADR 的下游身份、义务或门控。

每次 invocation 必须显式提供 mode、pipeline profile、assurance policy、语义摘要、IR / Evidence 精确版本、工具身份、adapter profile、资源限额和全部输入制品。没有隐式 default、`latest`、PATH 自动发现、网络下载或失败 fallback。

## 阶段图与停止线

```text
candidate bytes
  -> P0 capture / preflight
  -> P1 normalize + strict IR check
  -> P2 generate complete obligation set
  -> P3 encode one query per prove obligation
  -> P4 prove / classify / replay each obligation
          |
fixture bytes -> P5 strict input + golden check
          |
          +---- verification gate: all prove=proved, trust declared,
          |                        assurance policy accepted,
          |                        concrete input=checked
          v
        P6 generate deterministic Node ES module
          -> P7 execute one Node process per concrete input
          -> P8 decode + host/output compare
          -> P9 assemble canonical Evidence + pipeline receipt
```

P3 / P4 按 obligation ID 分叉，每项义务使用独立 cvc5 进程；P5 / P7 / P8 可按具体 fixture 分叉。并行调度只能影响伴随性能记录，不能影响 query、artifact、execution、义务、输出或 Evidence 的规范顺序。

### P0：捕获与工具预检

- 先按实际收到的原始字节计算 SHA-256，不做换行、编码或 JSON 重写；
- 解析显式 invocation contract，验证 profile、policy、tool、adapter、版本、digest 与 limits；
- 工具缺失、摘要 / 版本不匹配、配置含未知项或 artifact 无法解析时停止，不尝试系统 PATH 替代、自动安装或联网获取；
- P0 只形成 pipeline receipt 与原始 artifact，不形成证明或 `structure_rejected`。

### P1：规范化与严格 IR 检查

- 按 Axiom IR v0.1 的固定顺序解析、规范化、重算条目 ID、检查 DAG / 类型 / 效果 / 契约并生成 canonical IR；
- normalizer 只允许规范明确列出的表示归一化，不能删除未知字段、修补引用、缩小范围、添加默认值或改写语义；
- 具体且可重放的格式 / 结构错误产生 `rejected-ir` subject、`ir-structure: failed` 与 `structure_rejected` Evidence，之后所有阶段 `not-run`；
- 若因 timeout、资源耗尽、I/O 或工具错误无法判断输入是否合法，只形成 operational receipt，不得把“未完成解析”写成结构拒绝。

### P2：完整义务生成

- 从 canonical IR、精确语义摘要和 Evidence profile 生成完整 obligation definition 与 ID 集合；
- 内建义务、contract 义务、实际 trust 与 mode 所需 concrete check 位置必须遵循 Evidence v0.1，不按优化、候选结果或用户偏好合并 / 省略；
- obligation 集合按 ID 排序并形成 `axiom-obligation-set` `0.1` pipeline artifact；它是生产生成器输出，不替代独立 checker 从 IR 重建；
- 生成器 operational failure 意味着无法形成完整 Evidence，只保留 receipt 与已写 artifact，不为未生成义务伪造 `unknown`。

### P3：确定性 SMT-LIB 编码

- 每个 `prove` obligation 独立生成一个 `axiom-smtlib2-qf-uflia-query` `0.1` artifact，adapter profile 为 `cvc5-1.3.4-qf-uflia-v0.1`；
- 相同 canonical IR、obligation ID、语义摘要、adapter profile 和生成器 tool identity 必须产生逐字节相同的 UTF-8 / LF query，并恰有一个末尾 LF；
- query 禁止注释、绝对路径、时间、随机种子、主机信息、源 span、量化词、原生字符串、浮点、非线性算术和未登记 option；符号名只由稳定 obligation / anchor 身份派生；
- 声明、断言、model / proof 命令和辅助定义使用 adapter 规定的确定顺序。cvc5 invocation options 不隐式进入 query，必须另由 `prove` execution 与 receipt 绑定；
- Evidence v0.1 没有 `generate-query` execution kind，因此 P3 不冒充 `generate-obligations` 或 `prove`。query 作为真实 `prove` 输入和 `proved` support artifact 进入 Evidence，编码器正确性留在明确 generator trust 与后续独立重建边界。

### P4：后端尝试、certificate 与反例重放

- 每个义务以固定 query、cvc5 artifact、选项和 limits 启动一个新进程，原样捕获 stdout、stderr、退出状态、proof / model 和外层资源结果；
- `unsat` 按 assurance policy 选择 `certificate` 或透明 `backend-attestation` support。要求 certificate 时，不完整、缺失、含 trust step 或 checker 不支持必须是 `incomplete-certificate`，不得静默降格；
- `sat` model 先转换为完整 canonical world，再独立重放 `WF`、`Pre` 与目标违反；只有重放成功才能形成 `failed`，否则是 `unknown`；
- `unknown`、timeout、资源耗尽、崩溃、协议错误和不一致输出按 ADR 0005 失败关闭；
- 合法 IR 的全部必需核心义务都要产生真实 attempt / result。某项先得到 `failed` 或 `unknown` 不允许把其他未执行义务伪造成状态；若整个生产进程中断，只发布 partial receipt，恢复后按精确身份完成缺失 attempt 才能装配完整 Evidence。

### P5：具体输入与黄金制品检查

- `benchmark-node24` mode 严格读取 `axiom-benchmark-data` `0.1`，按 IR input / output 类型检查闭合字段、值、容量、键、外键、前置条件和黄金输出模式；
- 对每个实际执行 case 生成 `axiom-host-data` `0.1` envelope。顶层恰含 `format`、`format_version`、`ir_document_digest`、`role` 和 `tables`；`role` 只能是 `input` 或 `output`；
- `tables` 按接口名排序，每项恰含 `name` 与 `rows`；行按对应 IR 主键规范顺序排列，记录字段闭合。值按 ADR 0006 映射：Bool 用 JSON boolean，Int / Fixed 系数用规范十进制字符串，Text 用合法 Unicode string，Enum 用已声明 member，Option 用闭合 `none` / `some` tag；禁止 JSON number、`null`、未配对 surrogate、额外字段和隐式默认；
- benchmark input 到 host input、golden 到 host output 的转换必须形成 `check-fixture` execution 并绑定双方 artifact；转换失败或输入不符合产生可重放 `failed` / `input_rejected`，该 case 不进入目标生成或执行；
- input decoder 资源失败为 `unknown` 或 operational receipt，不得写成输入不符合。

### 验证门控

P6 只能在以下条件对相应 IR / case 打开：

1. canonical IR 已通过结构、类型、效果与 subject 绑定检查；
2. 完整义务集合已经生成，全部 `prove` obligation 都为 `proved`；
3. 每项实际 trust 已声明，proved support 满足显式 assurance policy；
4. 该 concrete input 的全部 `input-conformance` 为 `checked`；
5. 没有待完成、摘要不匹配或不可解析的 gate artifact。

`failed`、`unknown`、被拒绝输入、缺失 certificate、工具不可用或“预计应该通过”都不能开门。wrong candidate、backend-timeout scenario 和 invalid input scenario 不生成 Node module，也不执行宿主。gate 决策和决定它的 obligation / execution ID 必须进入 receipt。

### P6：确定性目标生成

- 从 canonical IR 生成 `axiom-node-esm`、profile `node-24-esm-keyed-finite-table-v0.1` 的单一自包含 `.mjs` artifact；
- 同一 IR 文档摘要、生成器 tool identity 与 target profile 产生逐字节相同的 UTF-8 / LF 源码，并恰有一个末尾 LF；
- 受限语法、`BigInt`、Unicode、表、codec、能力和许可证边界完全服从 ADR 0006；
- Evidence v0.1 不新增 `generate-target` execution。P6 的输入、输出、tool、options、limits 与结果进入 receipt；target module 作为 `execute-host` 输入，并由 `production-generator` trust 绑定生成器正确性；
- emitter 失败时可以发布已经完整的 verification Evidence，但不能伪造 benchmark Evidence 或 `execute-host` attempt。

### P7：Node 宿主执行

- 一个 target module 对一个 checked concrete input 启动一个全新 Node.js 24.19.0 进程；不复用 module cache、worker、daemon 或隐藏 session；
- 固定 Node artifact、invocation profile、Permission Model、环境清理、stdin、stdout、stderr、外层时限和资源限制；
- stdout 必须恰好是一个 canonical `axiom-host-data` output，无前后附加字节；stderr 与退出状态作为有界原始 artifact 保留；
- `execute-host` execution 绑定 module、host input、Node tool、limits 与全部输出。完成进程协议不自动等于 `checked`；
- unavailable、unsupported、timeout、resource exhaustion、operational error 与可归因语义故障按 ADR 0006 区分。

### P8：宿主与黄金比较

- 先严格解码 host output，再分别完成 `host-conformance` 与 `output-conformance`；
- 比较抽象值、闭合模式、键、行集合、字段与规范顺序，不以字符串日志或进程退出零代替；
- 具体且可重放的值 / fault 差异形成 `failed` 与 `implementation_inconsistent`；无法归因的 comparator I/O、资源或工具故障保持 `unknown` / `inconclusive`；
- output comparator 与 production generator 共享代码或规则时必须增加对应 trust，不能用同一 serializer 自证输出正确。

### P9：Evidence 与 receipt 装配

- 只在能够形成完整、闭合且引用一致的 Axiom Evidence v0.1 时写 Evidence；按规范重算 artifact、tool、execution、obligation、trust、uncovered、conclusion 和文档摘要；
- Evidence artifact 清单只包含被实际引用的字节制品，不能把整个工作目录、缓存或无关日志塞入报告；
- production self-check 只能检查格式与内部一致性，输出仍是生产结论，不得标记为独立 `accepted`；
- 先写临时字节、重读、重算摘要并完成规范检查，再原子发布到 content-addressed store。装配或最终校验失败时不发布半份 Evidence；
- receipt 无论成功、阻断或 operational failure 都可发布，但它不是 Evidence、proof support 或独立 checker 结果。

## Artifact 与 pipeline receipt

所有机器消费 artifact 的身份都是 `sha256:<raw bytes>` 加精确 `format` / `format_version`。路径、mtime、文件名、工作目录和“最近一次”不是身份。首版至少出现以下 artifact family：

| artifact | format / version | 生产或消费阶段 |
| --- | --- | --- |
| 原始 IR candidate | `axiom-ir-candidate` / `0.1` | P0 -> P1；非法时作为 rejected subject |
| canonical IR | `axiom-ir` / `0.1` | P1 -> 全部下游 |
| obligation set | `axiom-obligation-set` / `0.1` | P2 -> P3 / P9 |
| SMT query | `axiom-smtlib2-qf-uflia-query` / `0.1` | P3 -> P4 |
| 后端 stdout / stderr / proof / model | 按精确 cvc5、Alethe / CPC adapter 标识 | P4 -> replay / Evidence |
| benchmark data | `axiom-benchmark-data` / `0.1` | P5 |
| host envelope | `axiom-host-data` / `0.1` | P5 -> P7 / P8 |
| target module | `axiom-node-esm` / `node-24-esm-keyed-finite-table-v0.1` | P6 -> P7 |
| Axiom Evidence | `axiom-evidence` / `0.1` | P9 -> independent checker |
| pipeline receipt | `axiom-pipeline-receipt` / `0.1` | 全阶段伴随记录 |

`axiom-pipeline-receipt` 是闭合、canonical JSON、内容寻址的预稳定伴随格式。它至少绑定：pipeline profile / mode、assurance policy digest、输入 artifact、tool identity、adapter / options artifact、每个阶段的 kind / inputs / outputs / limits / result / dependency、全部 attempt、gate 决策和最终 outcome。receipt 不记录凭据、绝对路径、主机名、PID、时间戳或自由文本日志；这些只允许存在于另一个摘要绑定、默认不归档的本地诊断记录。

receipt stage result 只使用 `completed`、`invalid`、`not-run`、`timeout`、`resource-exhausted`、`unavailable`、`unsupported` 或 `error`。`not-run` 必须引用阻断它的 stage / gate，且只描述控制流，不能被映射成 Evidence `unknown`；Evidence 状态只能来自规范允许的真实 execution / result。

receipt 能说明生产管线声称做过什么，不能证明制品正确。独立 checker 可以把 receipt 当定位线索，但结论只能来自 canonical IR、Evidence、引用 artifact 与独立重建。

## 缓存、恢复与离线重放

缓存是不可变 artifact / execution store，不是可变“成功状态”。每个 cache key 至少包括 stage profile、精确 tool ID、全部输入 digest、options / adapter digest 和 limits；适用时还包括语义摘要、IR / Evidence 版本、obligation ID、assurance policy、cvc5 / Node artifact 和 target profile。

允许复用：

- 同一 raw candidate 与 normalizer identity 的 canonical IR；
- 同一 IR / 语义 / profile / obligation generator 的义务集合；
- 同一 obligation / adapter / generator 的 query；
- 同一 query / cvc5 / options / limits 的不可变 attempt；
- 同一 IR / target profile / generator 的 module，但只能在本次 gate 打开后取用；
- 同一 input / IR / fixture checker 的 concrete check；
- 同一 module / input / Node / invocation / limits 的 host execution；
- 同一实际 / 黄金 output 与 comparator identity 的比较结果。

禁止复用：

- 跨语义摘要、IR / Evidence 版本、未知 migration 或 tool identity 的 `proved` / `checked`；
- 只按文件路径、候选名、Git branch、时间、`latest` 或相似 query 推断的结果；
- 去掉旧 `unknown` / error 后伪装成同一次成功的可变记录；
- 从失败或未知义务绕过 gate 的旧 target module / host output；
- 不可取得原始字节、options、limits 或 tool artifact 的历史结论。

恢复必须从一个精确 receipt 与 content store 开始，验证所有现有 artifact 后只补齐 `not-run` / 缺失阶段；身份、policy 或 limits 改变时创建新 receipt，不原地改写。一次新 attempt 可以形成新的 Evidence 文档摘要，但旧 attempt / receipt 仍保持不可变。

完整离线重放包至少包含 canonical IR、Evidence、所有被引用 artifact、工具制品或可重建源码与摘要、adapter / policy / limits、pipeline receipt 和后续独立 checker 结果。缺少 artifact 时 checker 可以 `incomplete`，不能联网 fallback 后声称原包自足。

## 失败矩阵

| 发生位置 | 可发布结果 | 禁止行为 |
| --- | --- | --- |
| P0 工具 / 配置 / artifact 预检失败 | operational receipt | 自动安装、PATH / 网络 fallback |
| P1 可重放结构错误 | `structure_rejected` Evidence + receipt | 修补后继续、把类型错误当验证失败 |
| P1 资源 / 工具未完成 | operational receipt | 伪造结构拒绝 |
| P2 / P3 生成器失败 | partial receipt；无完整 Evidence | 为未生成义务 / query 伪造 `unknown` |
| P4 `sat` 且反例重放成功 | `violated` Evidence + receipt | 继续目标生成 / 执行 |
| P4 `unknown` / timeout / certificate 不完整 | `inconclusive` Evidence + receipt | 当作 proved、silent fallback、继续执行 |
| P5 输入不符合 | `input_rejected` Evidence + receipt | 把 invalid input 当程序失败、执行目标 |
| P6 emitter 失败 | verification Evidence（若已完整）+ operational receipt | 伪造 benchmark Evidence / host attempt |
| P7 / P8 操作失败 | `inconclusive` benchmark Evidence + receipt（若规范可表达） | 删除失败 attempt、默认成功 |
| P7 / P8 可重放宿主差异 | `implementation_inconsistent` Evidence + receipt | 降格为 warning 或业务违反 |
| P9 装配 / 自检失败 | receipt；不发布 Evidence | 发布部分或非规范 Evidence |

## 诊断与来源映射

- 每个机器诊断绑定 stage、稳定 code、相关 artifact digest 和可解析 IR / obligation / fixture / execution anchor；自由文本只作展示；
- source span、注释、Agent 轮次和显示名来自摘要绑定的 companion source map，不进入语义输入或 cache key；source map 摘要不匹配时拒绝映射但不改变 IR 结论；
- cvc5 / Node 原始 stderr 保留为有界 artifact，不从日志文本推断证明状态；
- 首批管线只处理合成语料，诊断、反例、receipt 与缓存不得包含凭据、真实秘密、绝对用户路径或环境变量值；
- 不同平台的非语义诊断可以不同，稳定 code、artifact、义务、结论和规范输出必须一致。

## 进入受控实现的验收条件

本 ADR 被接受不授权现在创建 Cargo workspace、安装 Rust / cvc5 / Node.js、编写 parser / emitter / runner 或执行正式模型实验。首个实现变更前仍须先冻结独立 checker 隔离边界，并同时满足：

1. `raxc-keyed-finite-table-pipeline-v0.1`、两个 mode、assurance policy 输入与全部 adapter profile 形成可审阅的机器契约；
2. `axiom-obligation-set`、SMT query、`axiom-host-data`、target module 与 pipeline receipt 的规范字节、格式版本、负向拒绝和摘要规则物化；
3. AX-B01 至 AX-B04 的 correct、八个 wrong candidate、invalid input、backend timeout、host mismatch 和 operational failure 都能画出唯一合法阶段图与停止线；
4. fixture 证明 wrong / unknown / invalid 路径没有 target module 或 `execute-host`，gate 篡改、缺失义务和伪造 cache hit 被拒绝；
5. 同一 IR / obligation 在 Linux、macOS、Windows 产生相同 canonical IR、obligation ID、query 和 target source 字节；
6. partial receipt、恢复、新 attempt、缓存复用和离线包能保留历史失败，不依赖网络或可变路径；
7. production Evidence 能通过自身格式检查，但项目验收只采用后续独立 checker 对 Evidence digest 的外部结果；
8. 精确 Rust 工具链、cvc5 / Node 制品、首批 crate、许可证、build script、native code 与生成产物授权边界完成 ADR 0004–0006 要求的审查。

## 风险与重新评估

- 显式 DAG 与 receipt 增加首版制品数量；收益是失败可追踪和离线重放，不能用可变临时目录重新隐藏边界。
- Evidence v0.1 未把 query / target generation 作为 execution；receipt 只能补足生产审计轨迹，不能提高证明等级。若独立 checker 需要这些阶段成为规范 Evidence，必须设计 Evidence v0.2，而不是塞入未知 kind。
- 每项义务一进程和完成全部真实 attempt 可能增加运行成本；性能问题先测量并进入 resource-performance uncovered，不改用隐藏增量 session。
- cache 可以传播旧实现缺陷；精确 tool / input / policy identity、不可变 artifact 和独立重建是最低缓解，不能把 cache hit 当证明。
- host envelope 是首域预稳定运输格式，不是新的通用数据协议；扩域、流式输入或外部效果必须另行版本化。

出现以下任一事实时，以新 ADR 重新评估阶段图或公共格式，而不是增加隐藏旁路：

- Evidence v0.1 无法对真实 pipeline failure 给出不夸大的完整结果，且 receipt 无法保持生产 / 独立边界；
- 一义务一进程在后续明确预算内无法完成四题，而受控 batch 方案能保留 query、attempt 和资源隔离；
- query 或 target source 无法跨平台生成相同字节，根因是阶段边界而非局部实现错误；
- host envelope 必须引入当前语义没有的值、默认、顺序或效果才能运行四题；
- 独立 checker 决策证明 production artifact 粒度不足以重建义务、重放反例或定位 generator trust；
- 离线包无法在不访问网络、不依赖原工作路径的情况下复核 Evidence。

修改首版阶段顺序、放宽验证门控、允许核心失败 / 未知后执行、使用长驻后端 session、引入路径 / 时间缓存身份、删除历史 attempt、把 receipt 当 proof support 或扩展 Evidence v0.1 的 kind / role，必须以新 ADR 替代本决策或先正式升级对应公共格式。

本管线引用的 Rust build、cvc5 adapter、Node target / invocation 和 Go checker build profile 已登记到 [Toolchain & Adapter Identity Registry v0.1](../../contracts/toolchain-adapters-v0.1/README.md)。obligation set、host data、SMT query、target module 与 pipeline receipt 的首批规范字节、schema、gate / cache / partial failure fixture 已物化到 [Pipeline Artifact Contract v0.1](../../contracts/pipeline-artifacts-v0.1/README.md)；两个契约仍不替代尚未冻结的完整 options / limits、全部场景矩阵或实际 adapter / launcher 实现。
