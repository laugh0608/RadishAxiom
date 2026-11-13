# AX-B01 Evidence v0.2 后端结果与信任审阅

2026-11-07，基线为 `dev` 的 `dd21754`。2026-11-13 所有者已确认 D1–D5 的候选实施选择；新机器字节与公共支持仍待审。范围为 verification profile 下 AX-B01 的五类、九项后端义务。S1–S3 的已批准边界继续适用。P6 为 `closed / p6-not-evaluated`。 [九项精确目标](ax-b01-evidence-v0.2-contract-review.md#精确义务与现有材料) · [M1 原件与逐项对照](../records/2026-11-07-ax-b01-evidence-m1-preflight.md)

M1 的九份请求由 query v0.5 / query0.3 与 P4-A v0.2 生成，使用合成工具身份。最宽的一份为 960,250 bytes，原容量和 1,048,576 bytes stdin 上限均保留。以下规则用于审阅未来实际结果的装配与独立检查。本仓已增加只接 simulation 批次的 Rust 候选读回；独立 checker 和公共支持集不变。 [P4-A 精确配对](../query/p4-request-response-model-v0.2.md#精确支持矩阵) · [当前机器登记](evidence-v0.2-machine-contract/contract.json)

<a id="待所有者确认的决定2026-11-13"></a>

## 所有者确认的实施决定（2026-11-13）

用途：把 B1–B3 的待决语义、信任和机器集成选择收敛为可审阅范围。以下 D1–D5 **已由所有者确认，用于本仓候选实现与离线验证**；新生成的机器字节仍待审，不是公共规范发布、实际工具接受或执行授权。此前探针的事实保留于[审查记录](../records/2026-11-13-evidence-backend-review.md)，本次实现及验证见[实施记录](../records/2026-11-13-evidence-backend-implementation.md)。

B1–B3 作为候选实现基础；旧单目标投影仍不承担完整 Evidence 验收。本仓候选已补来源批次输入、重放工具严格检查、未决结果运行信任、多次尝试和模式专属中止规则；真实来源资格与独立产品验收继续分开。已接受的 ADR 0008 四态、ADR 0009 迁移要求、原容量和资源限额无需重新选择。

### D1 · 正向结果允许 attestation，保留三类实际信任

首批按 B1 实施：实际、完整、来源合格的 `unsat`，仅在生产策略允许时形成 `proved / backend-attestation`。首批保留 `proof-backend`、`production-generator` 和实际采集 / 运行所依赖的 `host-runtime`，按精确 scope 引用；不提供默认全允许的消费策略。只有独立请求明确允许全部剩余信任时，独立接受上限才是 `accepted-with-trust`。

只重建 IR / P2、匹配 query 摘要或跑有限对照，不能解除 generator 的反例覆盖假设。生产策略为 `certificate-required` 而没有可接受证书时，产生有实际 attempt 的 `unknown / incomplete-certificate`；消费侧改用该策略时，已有 attestation Evidence 保持原样，独立结果为 `incomplete`。

影响：首题流程可以在独立证书 profile 尚为空时继续，但交付仍带显式信任，不计为独立正向 proof。若选择“首题必须具备独立 certificate”，需先实现并独立验收证书规则，将增加当前中间交付的前置；本次不建议更改该规划。

### D2 · 求解、重放和完整尝试清单由独立受信入口绑定

由**受控采集 / 调度端**提供求解与重放原件，由**调用方独立配置的验证入口**固定本批来源摘要；Evidence producer 只消费这些材料，不能自行签发自己要通过的预期摘要。这里的独立是相对于 producer 的信任分离，不声明采集端脱离宿主 TCB，也不假定自动具备签名或远程认证。

绑定范围至少包括：本批精确 subject / P2、生产策略、每个 invocation 的请求、目标、工具、规则、预算、来源封套 raw 摘要、调度顺序，以及 replay 到 solve 的唯一上游关系。采集端应结束并封存一个明确批次的完整尝试清单；仅比较 Evidence 内连续 ordinal 无法发现“删掉失败再重新编号”。原件缺失按实际阶段停止装配或产生独立 `incomplete`，已知身份矛盾拒绝，不以信任声明代替缺原件。

清单是本批边界内的完整性声明，不声称掌握历史上一切执行。为避免摘要循环，先固定请求与捕获，再生成 execution 身份及封存清单，最后装配 Evidence；清单不反向包含最终 Evidence 摘要。独立消费入口再同时绑定清单与 Evidence。需要进入公共 request / manifest 的新字段须按 ADR 0008 版本化，当前不能私加到 v0.1。

同时确认：`unknown` 也保留实际依赖的运行来源信任。首批不增加 `unknown.assumptions`，将这些依赖登记在顶层 trust，以各 solve / replay execution 为 scope，并生成对应 trust-boundary 义务。`failed` 的来源涉及 solve 和 replay 时，两者的实际依赖分别登记；仅有一条 solve scope 的 trust 不能默认覆盖 replay。独立结果对全部未缓解 trust 执行政策检查。

影响：新增的是批次来源接口及信任覆盖要求，不能直接沿用 P5 的接受回执为 solver 背书；模拟 pin 仍只用于模拟。若只接受 producer 自填 pin 或不封存批次清单，就无法兑现来源独立性或历史完整性，本审阅不建议接受该路径。具体真实宿主、采集工具与资格仍单独审阅。

### D3 · 反例采用精确目标重放投影，失败不外推

B2 的首批边界为：只接来源合格 `sat` 的模型；经 P4-A 解码及 P4-B 对 WF、全部 Pre 和**指定目标**重放为 `target-violated`，才支持 `failed`。投影采用现有候选的 `target-replay`、一个规范 world、全部已满足 assume ID、原观察 witness、两步 trace 和 `unreduced`。独立 checker 必须自己求值，不能复制生产观察结论。

WF / Pre 被拒绝或目标未违反时，按 B3 保留 `unknown / indeterminate`；world 结构错误、解码错误与运行失败按各自原因处理。`wrong-drop-zero` 的 guarantee 失败不构成 filter coverage 失败。直接提供 world 的内部对照入口继续可用，但不扩展为首批公共反例来源。

影响：明确了 `failed` 的来源与公共投影字节方向，不修改五类目标的语义，也不宣称最小反例或程序所有目标均失败。若要接受直接 world、多个 world 或新的最小性声明，需要另审来源及字节，而非复用本批批准。

### D4 · 多次尝试按求解链聚合，完成支持与未决历史分开

首批只支持批次内有明确调度顺序的串行尝试；每次 solve 及其 replay 构成一条尝试链，replay 不能误算为另一次求解。ordinal 作为规范非负整数比较，不能按字符串字典序决定先后；不同目标的最后一次执行不相互覆盖。

按以下规则实现并验证聚合：

| 同一目标的历史 | 已确认结果 |
| --- | --- |
| timeout → 合格 unsat，且策略允许 attestation | `proved`，结果引用完成支持；timeout 与全部来源仍保留。 |
| 合格 unsat → timeout | 仍保留已有可用的 `proved`；后次未决不自动撤销有效支持。若后续材料实际否定来源或资格，转入拒绝 / 调查。 |
| 多次未知或中止，始终没有可用完成支持 | 用最后一条实际尝试链的终态确定 reason；attempts 引用该目标与该 reason 相符的终态执行，其他历史 executions 全部保留。 |
| 多个相容的可用完成支持 | 确定性选择最后一个匹配支持作为 result 引用，其余完成执行仍保留。 |
| 同目标合格 unsat 与有效 `target-violated` 并存 | 保留原件并停止正常装配，进入矛盾调查；收到声称正常的包时独立拒绝，不择一、也不降格成普通 unknown。 |
| sat 但 WF / Pre 不成立，或目标未违反 | 本身不是目标反例，也不能与 unsat 自动构成上项逻辑矛盾；保留未决链和诊断。 |

完整合法文档仍按 `failed → violated`、否则 `unknown → inconclusive`、否则全部期望成立才 `satisfied` 聚合；缺义务或缺真实尝试停在装配前。独立四态另外计算。

影响：补充了原稿没有唯一确定的“完成后又失败”行为，结果及文档身份会随保留的历史而变。另一选择是“一律以最后一次运行覆盖结果”，会丢弃先前仍有效支持，也无法单靠覆盖规则解决互相矛盾的完成支持，因此不建议采用。

### D5 · 保留既有模式字节，按后端模式补齐机器契约

本次实现范围限定为 verification 候选的后端接入，继续保留 S1–S3 与旧版本的原规则：

| 集成项 | 已确认方案 |
| --- | --- |
| 中止结果 | S1–S3 保留现有 `timeout/resource-exhausted/unsupported/error/unavailable` 的 kind 与映射；后端模式使用候选的 `{kind: interrupted, code}` 并按 backend 原因表判定。统一入口按 mode 分派，不能全局重写旧状态。 |
| 来源制品 descriptor | S1–S3 继续 `execution-provenance / 0.1`；后端分别使用 `axiom-evidence-backend-capture / 0.1` 与 `axiom-evidence-backend-replay-source / 0.1`。实际格式由模式严格匹配，不把所有 JSON 冒充同一 provenance 类型。 |
| 内层引用闭包 | 逐项核对封套、request、response、模型、world、replay、generator 及规则原件；摘要存在不等于原件可得。原始流按实际 bytes 登记，未知成员、非法角色和格式错配拒绝。所有 descriptor 唯一、引用可解析，无未引用制品。 |
| 无流与中止重放 | 分别实现 `complete/prefix/absent`，空完整流不等于 absent；仅受控调度失败可支撑 tool-unavailable。按 `inputs_before_world` 处理真实解码中止，不合成 world；资源中止保留真实阶段与原因。 |
| 兼容与公开 | 后端候选及新来源材料先物化、固定字节并跑正负例，再接入 Rust 和分仓交接。保留现有指纹作为历史基线，变更须逐项解释；公共 v0.2 读取仍待 ADR 0009 完整迁移与独立验收。 |

影响：需要扩展模式解析、制品闭包、来源接口和结果聚合，不能只把 backend.json 两个模式名加入白名单。相较于统一改写 S1–S3 字节，按模式扩展可保留已有兼容边界；独立 request / manifest / result 的新版本仍须具名审定。

### 确认范围与本仓实现

所有者确认按 D1–D5 推荐方案推进，先补重放工具拒绝回归并修复检查器，再按顺序完成本仓候选实现与离线验证。授权只覆盖上述语义 / 信任 / 集成选择；**不代表新生成的机器字节已接受**，不包含跨仓写入、真实 solver / 安装 / 宿主资格、P6 放行、commit 或远程操作。

重放工具四类缺口已先复现拒绝回归失败，再修正检查器；旧 12 份投影指纹不变。D2 / D5 的来源接口和模式字节、D4 的聚合及完整合成文档已接入 Rust。当前接口只接 simulation；受信 pin 由调用方在 Evidence 外提供，测试自建 pin 仅用于合成验证，不能认证真实采集端。新字节、公共验证矩阵及独立跨仓验收仍待后续审定。

## 从请求到观察

| 层次 | 必须绑定的原件与事实 |
| --- | --- |
| 目标 | 规范 IR 原始及文档域摘要、精确语义、完整 P2 集合原字节、唯一 obligation ID 和 definition。相同 SMT 字节可共享原始制品摘要，目标、请求与实际执行仍分别绑定。 |
| 查询与请求 | query v0.5 的原始 stdin、查询规则与实际 generator 来源；P4-A v0.2 请求原件，绑定同一目标、symbols、layout、adapter、工具、参数顺序与内外预算。query 的生成来源留在制品链中，执行使用既有 `prove` / `prover`。 |
| 实际执行 | 精确接受记录、实际执行文件原字节及 digest、与请求内 payload 的对应、完整加载闭包、宿主资格、实际启动器／监督器及政策、唯一进程调用身份和开始／结束事实。请求的 `tool.payload_digest` 沿 P4 规则绑定归档，Evidence tool 的 artifact 对回实际启动的可执行文件，两者各自核验。来源通过独立受信的登记与真实捕获入口核对，报告者自填的摘要或同名资格字段只用于定位材料。 |
| 传输与协议 | 实际发送的 query 后 EOF、stdout 和 stderr 的原件、完整性、退出、外层终止、资源事件与清理事实。完整流和截断前缀分别寻址。协议观察由同一真实捕获重建，保留 request digest。P4-A 的 `planned-not-calibrated` 原字节保留，真实资格另外绑定。 |
| 重放 | `sat` 的合法模型经 P4-A 解码到规范候选和 world。实际 `replay-counterexample` / `counterexample-replayer` 绑定自己的规则、工具、预算、同一 IR／P2／目标、上游实际 solve 执行以及请求、响应、模型候选、world 和 P4-B 观察。多个运行取得相同 stdout 时仍须确认精确来源。 |

每次尝试保留完整的实际阶段、稳定原因和执行身份。只允许固定工具、一目标一进程、原十二项参数及既有预算。stdin、stdout、stderr 上限分别为 1,048,576、4,194,304、65,536 bytes，外层为 134,217,728 bytes／6,000 ms，内部为 1,000,000 steps／5,000 ms。资格须覆盖实际配置与运行范围。缺失退出、流不完整、来源不可核实或清理未完成时，正常协议结果不进入结果支持。已有真实失败原因优先于后续收尾，其他事实仍留存。当前 `Simulation*` 记录和 P5 接受回执各有自己的适用范围。 [ADR 0005](../adr/0005-first-verification-backend.md#决策) · [ADR 0007 P4](../adr/0007-first-verification-first-compilation-pipeline.md#p4后端尝试certificate-与反例重放) · [模拟记录边界](../query/solver-diagnostic-simulation-v0.1.md)

## B1 · 正向结果与信任

提议仅在完整真实捕获按 P4-A 严格解码为 `unsat`，且生产策略明确允许该 support 时，进入 `proved / backend-attestation`。沿用 `execution`、`query`、`response`、`trust` 四个绑定引用的形状。request 与捕获材料由同一 execution 的制品闭包提供。执行引用精确匹配的目标和规则。命题为 `WF ∧ Pre ∧ ¬Goal` 不可满足，生产声明的适用范围由目标定义及其实际 assumptions 决定。 [旧版 attestation 形状](axiom-evidence-v0.md#proved) · [后端命题](../adr/0005-first-verification-backend.md#背景与判定方法)

| 信任类别 | 候选范围 | 独立核对后的处理 |
| --- | --- | --- |
| `proof-backend` | 以实际 prover tool 为 scope。声明仅覆盖该精确后端对已绑定 query 的 `unsat` 健全性。support 的 trust ID 必须进入该 result 的 assumptions。 | 检查接受记录、工具、请求、响应及 scope 绑定，保留为剩余 trust。 |
| `production-generator` | 当独立路径未建立 query 对精确目标的覆盖时，绑定实际 query generator 制品及规则，声明每个满足 WF、Pre 且违反目标的世界都能在该查询中形成满足赋值。 | P1、P2 重建、摘要相等和有限对照各有自己的检查范围。独立路径只有确立上述覆盖方向，才可消除这一条依赖。 |
| `host-runtime` 及其他实际假设 | 采集、启动、资源和清理仍依赖的宿主或执行来源，按实际使用的 execution 及适用范围声明。 | 逐项记录已核实的事实、剩余假设与允许策略。信任条目不能代替缺失的捕获原件、资格或可核对的绑定。 |

每一项实际 trust 形成单独的 `trust-boundary` 义务，并由结果的 assumptions 引用其精确 ID。独立 checker 自身的 parser、规则与密码学实现记录在其 TCB。完整 attestation 在 `attestation-allowed` 且 request 显式允许所有剩余 trust 时，独立结果至多为 `accepted-with-trust`。checker 使用 `certificate-required` 或剩余信任越出允许集时，结果为 `incomplete`。checker 不运行 solver，后端自检的 proof 不计独立证书检查。当前可接受的独立 certificate profile 为空。生产策略要求证书而实际尝试未获完整可接受证书时，拟保留 `unknown / incomplete-certificate`；独立策略拒绝接受已有 attestation 时，源 Evidence 与生产结果保留原样。 [ADR 0008 策略与信任](../adr/0008-independent-checker-isolation-and-artifact-exchange.md#certificateattestation-与-trust-分级)

## B2 · 可重放的反例

拟议首批 `failed` 仅接实际 `sat` 的模型来源。P4-B 须从完整 world 重做类型、值域、容量、键、全部 Pre 及精确目标，得到 `target-violated`。完成的 replay execution 支撑 `failed`。保留全部满足的 assume ID、有类型的一个规范 world、同一目标的确定性见证和可解析 trace，最小性为 `unreduced`。公开反例投影建议由 P4-B 的目标见证派生，精确 tag、trace 字节及与观察原件的逐项一致性在机器登记评审确定。独立 checker 从同一 world 和 IR 独立求值，不用生产输出的 ok、Ready、fault 或缓存见证决定结论。直接提供 world 的已有入口用于独立对照，若作为公共执行来源须另审其来源契约。 [P4-B 来源与目标](../query/p4-concrete-target-replay-v0.1.md#入口与来源) · [见证结构](axiom-evidence-v0.md#反例与见证)

| 目标 | 独立复现的关键区别 |
| --- | --- |
| `numeric-range` | 精确 anchor / path 存在可达动态实例，操作数成功且数学值越界。guarantee 内位置另检查 ProgramOK。父位置和兄弟故障各自归因。 |
| `totality` | 精确目标节点无结果，保留局部故障、容量失败或真实依赖传播链。 |
| `key-cardinality` | 仅从 Ready 的容量前实际候选检查重复键或容量，不用失败后的输出替代。 |
| `row-coverage` | 在 Ready 下核对同节点直接输入／输出的双向键关系和谓词。别的目标违反、正确筛除行或错误保证均不能作本目标见证。 |
| `contract-guarantee` | 指定 guarantee 的 ProgramOK、公式求值与真假分别重做，保留精确故障或 false 见证。 |

## B3 · 未决、失败原因与装配

| 已发生且可认证的观察 | 拟议的结果原因 |
| --- | --- |
| 完整 `unknown` 协议帧 | `indeterminate`。可选模型只作为原始观察保留。 |
| `sat` 解码后的 world 或 Pre 被真实重放拒绝，或所选目标未被违反 | `indeterminate`，保留具体阶段、P4-B 观察及各原件。 |
| 受控外层实际到期 | `timeout`，保留实际计时和终止证据。 |
| 可信内存、流上限或确定性组件预算耗尽 | `resource-exhausted`，保留具体资源与阶段；退出码 137 或 stderr 文本不足以确认 OOM。 |
| 有受控调度与启动失败事实，登记工具无法取得 | `backend-unavailable`。P0 预检拦截或未调度的目标记录为缺项。 |
| 运行中止、退出异常、流不全、协议或模型解码错误、清理异常 | `operational-error`，除非更早已有可核实的外层原因。 |
| 实际尝试遇到明确、版本化的不支持边界 | `unsupported`，留存阶段和拒绝原因。 |
| 生产策略要求证书，真实尝试的证书缺失、不完整或无可用检查规则 | `incomplete-certificate`，禁止切换到 attestation。 |

所有 `unknown` 都引用同一目标的真实非空 attempts。提议仍未取得完成支持时，以最后一次实际尝试的可核对终态确定 reason，引用该目标与此原因相符的终态执行，按 ID 排序。其余尝试仍留在 executions。成功捕获 `sat` 后重放失败、收到 `unsat` 后证书不足等情形，各阶段的结果和原件分别保留。后端模式须单独登记结果、阶段与摘要引用，S1–S3 中止规则继续使用现有映射。实际后续运行若最终完成，仍保留全部历史 executions。仅有计划、缺失来源、模拟数据或未执行时，装配停在报告／receipt。包声称存在且能取得的字节、身份或目标与声明冲突时，独立检查拒绝该包。 [旧版状态语义](axiom-evidence-v0.md#unknown) · [P4-A 响应边界](../query/p4-request-response-model-v0.2.md#响应与候选的兼容边界)

完整 verification 必须先具备全义务及实际 trust。对合法 IR，拟沿原聚合优先级，任一核心反例使生产结论为 `violated`，refs 为全部决定性的 failed 义务 ID。否则必需义务为 unknown 时为 `inconclusive`，refs 为相应义务 ID。全部达到期待状态才为 `satisfied`。同一目标若出现相互矛盾的完成支持，先保留原始执行并调查，禁止择一形成报告。独立检查按自身四态和 request 策略重算，证据拒绝优先于共存的缺项，两者均保留。 [结论基线](axiom-evidence-v0.md#结论聚合) · [ADR 0008 独立聚合](../adr/0008-independent-checker-isolation-and-artifact-exchange.md#独立结果协议)

## 验收矩阵与实施顺序

| 审阅用例 | 预期 |
| --- | --- |
| 使用旧 `CHK-PROOF-02` 的 `unsat`、旧 proof trust 或旧 companion，重算外层 ID 后挂到新义务 | 拒绝。按新目标、请求、捕获及信任重新核对，旧包只保留源历史。 |
| 同一 query 字节换绑其他目标、P2、语义、generator 或 request | 拒绝精确绑定。 |
| 以归档摘要冒充实际 CLI；改变实际参数、预算、宿主、加载闭包或采集来源；把 simulation 改标签 | 拒绝来源与资格。已知缺失和实际漂移分开报告。 |
| 合格 attestation；删除 scope、proof trust 或实际依赖的 generator trust；调用方改为 certificate-required | 第一项仅在策略允许时为 `accepted-with-trust`；缺实际依赖或错绑拒绝；严格策略为 `incomplete`。 |
| `sat` 但 world 不满足 Pre、错 replay target 或只给 model；wrong-drop-zero 的 guarantee 失败但 filter coverage 成立 | 真实未重演成功时保留未决原因；宣称 `failed` 的材料不能通过独立复现。 |
| 完整 `sat` 文本与清理失败并存；先 OOM 后 deadline；exit 137 无 OOM 证据；纯 `unknown` 带模型 | 不形成可用 world 或证明，保留实际失败及优先原因。 |
| 错角色、错误摘要、缺原件、未启动假 attempt、只完成四项或遗漏历史执行 | 角色及已知矛盾拒绝；checker 缺必要原件为 `incomplete`；目标缺实际尝试时停在 Evidence 装配前。 |

1. 审定 B1–B3 的支持、信任与结论规则后，先定稿执行来源的闭合字节、后端模式与反例投影，再接入生产严格读回和独立规则。用现有 P4 对照、合成捕获和重新绑定的负例验证，分开留存结果。
2. 运行线沿 C1／C2、L3／L4／L5 及 E0／E4 的现有前置恢复。ADR 0028 下的 E5 最多八份小查询及一次原容量 wrong-add guarantee，仅提供校准和诊断观察。AX-B01 correct 九项进入生产执行需要覆盖该批制品、宿主和目标的单独范围，及匹配的信任政策。 [运行恢复顺位](../status/current.md#接下来的事项) · [ADR 0028](../adr/0028-bounded-solver-calibration-entry.md#决定)
3. 新执行齐备后再组装 M1，按新 request 和 manifest 运行独立 checker，并交付绑定新 Evidence 两类摘要的结果。按 ADR 0009 完成迁移拒绝矩阵与兼容性验收后再审定公共读取。当前 M1 为未完成，P6 保持关闭。 [ADR 0009](../adr/0009-axiom-evidence-v0-drift-and-migration.md#决策)

接续的机器绑定候选已用 P4 合成导出核对来源封套、后端与重放模式、attestation 和反例投影。该候选及向量随 B1–B3 审阅。 [后端绑定候选与重跑](evidence-v0.2-machine-contract/README.md#后端绑定候选)
