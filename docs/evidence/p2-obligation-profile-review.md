# P2 义务 profile、目标归因与版本范围审阅

审阅日期：2026-10-05

状态：2026-10-05 已接受。决定见 [ADR 0018](../adr/0018-ir-derived-obligation-profile.md)，正式规则见 [IR 派生义务 profile v0.2](ir-derived-obligations-v0.2.md)。以下保留接受时的方案与比较；不启用完整 Evidence v0.2 公共读取器。

用途：为 [ADR 0016](../adr/0016-core-semantic-slice-entry.md) 的下一项 P2 组件确定可实施、可独立重建的义务范围，形成项目所有者可接受的具体版本方案。读者为语义、IR、Evidence、生产生成器与独立 checker 协作者。

不包含：P2 Rust 实现、query / solver / target / checker 执行、证明结果、依赖变更、跨仓写入或旧规范重写。当前顺位见[当前状态](../status/current.md)。

## 建议决定

建议接受 **IR v0.2 的 P2「IR 派生义务」组件范围**，使用拟定的 obligation profile `keyed-finite-table-verification` / `0.2`、Evidence v0.2 obligation definition / 域和 `axiom-obligation-set` / `0.2`。义务集合必须显式标记 `scope: "ir-derived"`，只表示所有可由 IR 决定的义务位置已完整生成，不能冒充完整 verification Evidence。

该范围窄替代 ADR 0007 的 P2 必须同时具备实际 trust / concrete check 材料的组件顺序要求；不改变完整管线验收。后续 Evidence 装配仍必须从实际工具、执行、信任和 benchmark 输入重建并补齐全集合。对 obligation 的定义、身份或实际结果，不能用空 trust、占位 artifact、默认 checked 或伪造 unknown 补足。

接受后先物化本提案涉及的版本化规则、正负例和兼容材料，再实现内部 P2 生成器。**这不是接受完整 Evidence v0.2 公共解析 / 发布**：[ADR 0009](../adr/0009-axiom-evidence-v0-drift-and-migration.md)第 6 项要求的完整规范、迁移器、正负例和完整迁移演练仍须逐项完成；旧 Evidence v0.1 是当前唯一可解析公共 Evidence 版本。P2 输出不能送入旧 pipeline / checker 冒充兼容。

| 方案 | 影响 | 判断 |
| --- | --- | --- |
| 在 v0.1 中补 group 行并沿用旧 ID | 改变被摘要绑定的义务完整性；混淆旧 profile 与新 IR | 拒绝，违反 ADR 0009 |
| 先实现全部 Evidence v0.2、实际工具与独立迁移，再开始 P2 | 保持完整产品顺序，但把本组件不消费的 execution / result 重新作为前置 | 不作为本次建议；完整产品仍须完成这些工作 |
| 明确接受 v0.2 的 IR 派生范围，保留全 Evidence 门禁 | P2 可产生真实位置、definition、ID 与拒绝；完整结果另外验收 | 推荐；需要所有者接受该精确范围，不能由代码默选 |

## 本轮确认的缺口

| 来源 | 实际问题 | 提案中的处理 |
| --- | --- | --- |
| [Evidence v0.1 生成位置](axiom-evidence-v0.md#v01-义务生成位置)与 ADR 0009 | group 的 row-coverage 在表格中遗漏；锁定 bundle 的受限 profile 已生成它 | v0.2 对每个 group 分列 row-coverage 和 group-conservation，既不合并也不补改旧文档 |
| 同一位置表与[锁定生成器](../../scripts/checker_bundle_contracts/obligations.py) | count_where / sum_where 未在表格中点名，生成器已经对 node / contract 内二者生成 numeric-range | 新表精确列出六种有范围的表达式及 group 聚合；不能只扫描节点或 guarantee |
| [ADR 0007 P2](../adr/0007-first-verification-first-compilation-pipeline.md#p2完整义务生成) | 实际 trust、输入 artifact、宿主输出和黄金比较不能由 IR 独自确定 | 显式 scope 区分 IR 派生清单与后续完整 Evidence 集合；生成器不读取 expected outcome |
| [旧 anchor schema](../../scripts/pipeline_artifact_contracts/schemas.py) | node / contract / field 等 anchor 不包含整份 IR 文档身份；相同节点在不同 Pre 下仍有相同 node ID | 新 IR 派生 anchor 全部携带 ir_document_digest。旧格式依赖外层 Evidence 绑定及 cache 全键，不能仅凭此差异宣称旧实现不健全 |
| [P1 文档接口](../../crates/axiom-ir/README.md) | components.analysis 保留原输入位置；义务必须锚定规范 definition 路径 | P2 只从已核验规范 definition 生成路径，不使用原 pretty 数组位置 |
| group 与任务保证 | 错误的上游 map 可使后续 group 忠实地汇总错误中间表 | group 内建目标绑定其直接 source；业务原始账户 / 用量等式由 guarantee 单独判断，禁止把其他义务失败归到 group |

这些是规范与本仓材料审阅，不是对真实 Go checker 的动态结论。本轮没有读取或修改兄弟仓库，也没有以历史指定态 failed 断言驱动新清单。

## 拟定版本与身份

| 项目 | P2 提案的精确值 |
| --- | --- |
| 输入 | P1 的只读 CanonicalDocument，版本 0.2；绑定 [IR v0.2 语义快照](../semantics/keyed-finite-table-semantics-v0.2.md) |
| 旧 IR | 须先调用已实现的显式 v0.1 → v0.2 迁移；P2 不隐式迁移 |
| obligation profile | keyed-finite-table-verification / 0.2 |
| scope | ir-derived，必需且唯一；不接受省略或 full 的猜测值 |
| obligation definition | 恰好 expectation、kind、subject；不含 result、工具、状态或推导缓存 |
| obligation ID | SHA-256(UTF8("axiom-evidence-v0.2:obligation") + NUL + JCS(definition)) |
| 集合制品 | axiom-obligation-set / 0.2；按 ID 排序，内容摘要为原始规范字节 SHA-256，不额外发明集合域摘要 |
| 执行与结果 | 本组件不产生 execution、trust、五态、conclusion、receipt 或独立 accepted |

拟定集合顶层恰好为 format、format_version、ir_version、ir_artifact、ir_document_digest、semantics、obligation_profile、scope、obligations。ir_artifact 是规范 IR 原始字节摘要，ir_document_digest 是 IR 文档域摘要；semantics 的 sha256 明确使用带 `sha256:` 前缀的摘要；旧 obligation-set 与 IR header 都使用裸 hex 字符串，新集合不得混用。所有版本精确匹配，不透传未来版本。

IR 派生 subject 的闭合形状如下；每行都必须含 kind 与 ir_document_digest，后者必须等于集合绑定的完整 IR 身份：

| kind | 其他且仅有的成员 | 使用位置 |
| --- | --- | --- |
| document、program | 无 | ir-structure、effect-empty |
| node | id | totality、key-cardinality、row-coverage、group-conservation |
| contract | id | contract-guarantee、noninterference |
| node-path、contract-path | id、path | numeric-range；id 是包含它的节点 / 契约，path 从其规范 definition 根开始 |
| field | direction、interface、name | field-origin；direction 精确为 output，名称与类型从 IR 输出绑定解析 |

path 是非空字符串数组；对象成员用精确名称，数组下标用规范非负十进制字符串。不得用 JSON Pointer 转义串代替数组元素，不以诊断中的原输入位置生成路径。路径必须解析到该义务要求的 op 或聚合种类。同一子式在两个不同规范路径出现时生成两项；and 去重后只剩一个位置时只生成一项。所有定义在生成后核对唯一性，发现重复是内部错误，不能静默去重。

完整 IR 身份使 Pre、输出名称和上游语义都进入义务身份。代价是任何 IR 文档变化会重算全部 IR 派生义务 ID；这是本提案有意选择的兼容成本。profile 和结果仍不进入 definition；未来 benchmark 在同一 IR 下复用相同核心定义，增加自己的 check / trust 位置。该未来关系不启用 benchmark v0.2 或新 Evidence parser。

本范围一经接受，v0.2 的这些 IR 派生定义与身份规则即受版本约束。后续完整 Evidence 若需要改变同一目标的定义、拒绝集合或 ID 规则，必须另作 minor 版本决定，不能以「完整格式尚未启用」为由改写已接受的 P2 身份。

## 精确生成位置与目标

以下十类构成 ir-derived 的全部集合。ir-structure 的 expectation 为 check，其余为 prove；成功生成不为其中任何一项填结果。

| IR 位置 | 每处生成 | 目标与边界 |
| --- | --- | --- |
| 完整文档 | ir-structure、程序级 effect-empty 各一项 | 结构 / 绑定与纯核心效果；不按类型声明或每个节点重复发效果义务 |
| 每个非 input 节点 | totality、key-cardinality、row-coverage 各一项 | 分别绑定节点总定义、键唯一 / 容量、该操作的双向覆盖；group 也在此列 |
| 每个 group 节点 | group-conservation 一项 | 节点级联合覆盖全部聚合字段；与 row-coverage 分开，无聚合字段也保留该项 |
| node 与 formula contract 中每个 int_add、int_sub、fixed_add、fixed_sub、count_where、sum_where | numeric-range 一项 | 绑定规范表达式路径，包含 assume 和 guarantee、record.fields、全部分支 / 绑定中的位置 |
| 每个 group 的 count / sum 聚合字段 | numeric-range 一项 | 路径为 aggregates 的规范下标；结果范围来自输出字段，不从 fixture 推断 |
| 每个命名输出的每个顶层字段 | field-origin 一项 | 即使两个输出引用同一节点也按各自接口名分别生成；复合字段作为整体，不额外创造叶字段义务 |
| 每个 guarantee formula contract | contract-guarantee 一项 | 该公式在有效输入与实际输出上无故障且为 true；业务等式属于其原契约 |
| 每个 noninterference contract | noninterference 一项 | 绑定完整 contract；公开等价、输出行存在性、值与故障观察依现行语义 |

不为 assume 本身生成 contract-guarantee；不新增 Pre 可满足性、非空性或业务约束覆盖义务。输入的 WF / Pre、定义域、分支可达性和故障必须在后续目标公式中保留：不得把所有位置改成无条件求值，也不能因分支常量、容量为零、推导标签为 public 或某个局部检查已经通过而省略生成位置。

有效输入中的 Pre 要求 applicable assume 求值得到 true；求值故障不得当成已满足的前置条件。assume 内部仍生成范围位置，但不另加「所有 WF 输入都必须满足 assume 或使 assume 无故障」的加强条件。后续 query / replay 必须明确这一有效输入条件，不能把同一待证明范围假装成已由其他工具证明的假设。

row-coverage 按目标节点的直接输入解释：filter 是谓词选中且只选中的源键；map 是源键与输出键的双射；join 是左键覆盖且不多行 / 扇出；group 是直接 source 的分组键与输出键精确一致。连接唯一匹配、范围和故障还由相应义务处理，不能由 coverage 把未知默认成正常。

field-origin 不猜业务意图，也不把「与某个错误候选不同」作为谓词。它关联该字段的 IR 投影与标签 / 依赖约束；是否满足任务指定等式由 contract-guarantee 判断。P1 保守标签只是后续分析依据，标签缺口不能自动变成已重放反例，public 也不能自动成为非干扰 proved。

## group 覆盖、守恒与归因区分

令 S 是目标 group 的**直接 source 表**，k(s) 是其声明 keys 投影，M(k) = {s ∈ S | k(s) = k}，O 是该节点观察到的输出。整数 / Fixed 系数均使用数学值；输出字段类型、唯一键与容量另由结构、范围和 key-cardinality 约束。

- row-coverage：输出键集合恰为 {k(s) | s ∈ S}，不产生空组或遗漏非空组；每个源行依据其唯一键与 k(s) 属于且只属于一个组。
- group-conservation：每个现有输出组的 count / sum 字段分别等于 |M(k)| / 对 M(k) 的数学和；每个 count 字段的全局和等于 |S|，每个 sum 字段的全局和等于对应源字段总和。聚合字段集合为空时此项是空合取，仍保留义务位置；覆盖由前项负责。
- 二者合起来固定正确分区和聚合；不能用「总和相等」代替逐组等式，或因已有 coverage 就删掉 conservation。两项目标可以同时失败，不要求逻辑独立，但必须能够单独定位。

以下有限例使用仅含 sum 的合成 group：S 为 `(a, 2), (b, 0)`。它们是手工语义区分材料，不是已执行程序、Evidence 或 solver 反例：

| O / 变化 | coverage | conservation | 说明 |
| --- | --- | --- | --- |
| `(a, 2), (b, 0)` | true | true | 正常基线 |
| `(a, 2)` | false | true | 遗漏零用量组不会改变数学总和，coverage 不能省略 |
| `(a, 3), (b, 0)` | true | false | 键覆盖正确但聚合错误，conservation 不能省略 |
| `(a, 1), (b, 1)` | true | false | 全局和相同但逐组错误，不能只检查全局守恒 |
| 空 S、空 O | true | true | 不添加非空性要求 |

上游 map 若把全部账户改为同一键，再由 group 忠实分组，该 group 的两个内建目标可以成立，原账户保证却失败。类似地，先把 units 改为 1 再正确求和，group 针对改写后的 S 仍可守恒。AX-B03 两个 wrong 的图含这样的上游 map；这只能说明需要检查其精确 guarantee 目标，不能沿用某个既有 failed 标签判定目标必然失败。历史指定态材料保留，独立 checker 的真实归因另行验收。

## 完整 Evidence 后续必须补齐的内容

完整 verification 的义务集合是 IR 派生集合与**实际依赖 trust-boundary** 的精确并集；完整 benchmark 还包含具体 input-conformance、host-conformance、output-conformance。profile 装配必须核对这些材料及其来源，P2 的 scope 不提供省略许可。

execution kind → tool role 建议在 Evidence v0.2 以闭合表固定：normalize → ir-normalizer；generate-obligations → obligation-generator；prove → prover；check-certificate → certificate-checker；check-fixture → fixture-checker；execute-host → host-executor；compare-output → output-comparator；replay-counterexample → counterexample-replayer。producer 仍必须有 evidence-producer。多 role 可以显式并列，不能把 fixture-checker 当 replay role 的 alias。

五态、support、结论聚合、反例最小性和 assurance policy 不在本提案中放宽。未运行不等于 unknown；不存在真实 attempt 时不能构造 unknown result。IR 派生清单也不能生成 satisfied、开启 target gate 或成为独立 accepted。

## 兼容性与迁移计划

1. 旧语义 / IR / Evidence、pipeline、28 个 bundle、实验注册及对应摘要保持原字节。新 IR 已通过显式迁移形成独立身份，但这不等于 Evidence 已迁移。
2. 完整 Evidence 迁移器先严格读取源 v0.1、受支持的具名旧 profile 与全部必要源材料，检查身份、role、义务完整性及状态支持；源非法 / 缺失不能靠新规则修补。
3. 显式迁移源 IR；按目标规则重新生成全部 IR 派生义务。不能只改 version / 域、逐字符串替换 ID，或把旧 path 下标照搬到引用重绑后重新排序的 definition。
4. 旧结果、execution、trust assumptions、conclusion 与独立结果全部不得移植为目标成功状态。可保留相同原始工具 / 数据字节的 artifact digest，但新的 tool / execution 身份、目标绑定和结果必须重新核对；证明、有限检查和反例需要重新运行相应真实路径。
5. 目标完整 Evidence 只有在全部必需定义、支持与实际结果存在时才能形成。缺少新执行时迁移返回未完成诊断与明确缺项；不伪造 unknown / trusted，也不发布半份 Evidence。独立结果在新 Evidence 之外重新生成。
6. 最小完整演练须同时覆盖 group 两义务、角色错配拒绝、未知 / 失败状态保留、旧 ID / path / 结果复用拒绝和目标 strict 检查。指定态字节演练与真实动态检查分别留存；只有材料齐备才评估新公共 Evidence 读取支持。

本轮[兼容预览](p2-profile-review/compatibility.json)只列实际旧 bundle 的核心定义清单与拟定目标清单，核对来源字节 / 内容身份，不复制 result。它不是上述严格源状态检查、完整 Evidence 迁移器或迁移演练；不能据它解除 ADR 0009 的门禁。

## 实施与验收切片

接受后先形成正式的版本化 P2 派生规则与 obligation-set 结构，再实施真实 Rust 组件。入口只接受不可修改的 CanonicalDocument / 精确 profile 和显式资源预算；遍历规范 definition，返回只读定义、ID、排序和规范集合字节。可以共用 P1 的 JSON / 类型与自有 SHA-256，但独立期望和独立 checker 不得导入该生成器。

数量、累计 definition / path 字节与输出字节预算须在分配与输出前逐步检查；记录 / 节点引用按 DAG 处理，不递归展开共享前驱。不产生部分成功、不修改 IR、不在失败时删掉最后几项义务。义务生成完成只表示位置与身份完整，不表示目标成立或 query 编码已实现。

| 验收主题 | 必需材料 |
| --- | --- |
| 四题及同域新输入 | [清单索引](p2-profile-review/cases.json)和[逐项定义 / ID](p2-profile-review/obligations.tsv)，正确与 wrong 同等按结构生成 |
| 完整性拒绝 | [变异配方](p2-profile-review/negative-cases.json)：分别遗漏 group coverage / conservation、聚合范围、多余 / 重复、错型 expectation、错 anchor / path / 文档绑定、旧域、携带 result |
| 目标归因 | [group 区分材料](p2-profile-review/group-separation.json)：覆盖与守恒分别失败、总和相同但逐组错、上游错误与当前节点目标分开 |
| 规范与身份 | pretty / 原数组位置不影响目标路径；Unicode 不归一化；同型同路径但不同完整 IR 必须不同 ID；缺 NUL、旧域、definition 外 wrapper 不得等同 |
| 资源与失败 | 深图、深表达式、宽字段、义务数 / 字节上限；失败不得形成可消费集合 |
| 兼容与下游 | 旧定义与新定义重新生成对照；旧结果迁移禁止；新 scope 不被旧 Evidence / pipeline / checker 接受 |

审阅材料由[独立 Python 脚本](../../scripts/generate-p2-profile-review.py)生成，限定于既有已验收合成 IR，显式核对手工数量与有限区分例。它不是生产 P2、完整格式验证器或证明检查器，不能在未来运行时调用。生成器不读取基准 expected outcome 决定新义务、结果或目标真值。

21 份清单合计 315 项拟定义务。AX-B03 正确候选为 14 项，两个含额外 map 的 wrong 各为 17 项；三者均包含 group coverage、conservation 及两个聚合字段 / 两个契约聚合表达式的四项范围义务。这些计数只说明位置完整，不报告其真值。

## 已接受的范围

接受本提案意味着：允许物化上述 v0.2 P2 规则 / 集合及内部生成器；固定整份 IR 绑定、十类生成位置、group 两项目标和 role 映射；保留后续完整 Evidence 的 trust / concrete check 补齐、严格迁移与独立验收门禁。它不接受完整 Evidence v0.2 公共读取、P3 以后实施、跨仓 / 外部执行或新依赖。

这是 [ADR 0016 的 P2 专属入口](../adr/0016-core-semantic-slice-entry.md#第二切片p2义务生成组件)所要求的精确 profile 决定，也涉及根[协作约定](../../AGENTS.md)规定的公共格式、兼容性与语义归因范围。项目所有者在审阅本范围及实施询问后回复“确认，继续推进”。正式决定与规则已经物化；实施与验收状态以当前状态和组件文档为准。
