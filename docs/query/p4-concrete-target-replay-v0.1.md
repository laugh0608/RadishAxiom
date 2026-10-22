# P4-B 具体输入与精确目标重放 v0.1

日期：2026-10-12。状态：Accepted，依据 [ADR 0026](../adr/0026-p4-concrete-target-replay.md)，项目所有者已接受精确范围。

用途：供项目所有者审阅 P4-B 的精确范围，并供接受后的内部 Rust 重放器及独立有限验收使用。本文不定义真实工具执行、完整 Evidence、证明支持、反例最小化、独立 checker 或产品运行时。

## 规范来源与支持集合

输入为不可变 P1 IR v0.2 CanonicalDocument、完整匹配的 P2 `keyed-finite-table-verification/0.2` / `ir-derived` 集合及原目标 ID。保持[语义快照](../semantics/keyed-finite-table-semantics-v0.2.md)、[IR v0.2](../ir/axiom-ir-v0.2.md)、[P2](../evidence/ir-derived-obligations-v0.2.md)及 P3 [v0.1](map-filter-query-v0.1.md)–[v0.4](map-filter-query-v0.4.md)的目标命题与身份；不删除旧义务，不添加输入非空、Pre 可满足性或其他目标已成立的假设。

显式 profile 为 `axiom-p4-map-filter-replay-v0.1`。仅支持 prove expectation 的 numeric-range、totality、key-cardinality、row-coverage、contract-guarantee。check 返回 NotProve，其他 kind 返回 UnsupportedKind，旧 IR 须显式迁移。节点仅 input / filter / map，表达式与现有 P3 相同：

- literal_bool / literal_int / literal_fixed / literal_text / literal_enum；
- bound / field / none / some / record；
- not / and / or / eq / lt / le / gt / ge；
- int_add / int_sub / fixed_add / fixed_sub；
- if / match_option / forall_rows / lookup。

在执行输入 / 目标前扫描完整节点与全部 formula，未选分支、无关节点或契约仍不能隐藏 unsupported。lookup_join、group、exists_rows、count_where、sum_where 拒绝并定位 anchor / 功能。noninterference 契约保留身份，不当单世界 Pre 或 guarantee，也不为其产生结论。field-origin / effect-empty 结构记录及保守标签缺口不构成运行故障。

## 入口与来源

`replay_target` 接受显式 profile、`ReplayInput` 与 `ReplayLimits`，返回只读 `TargetReplayObservation` 或错误。`check_target_replay` 用相同实际输入重建观察并逐字节比较，不导入任意外部成功对象。输入至少包含 document、obligations、obligation_id、generator 和以下唯一 world 来源之一：

| 来源 | 输入与核验 | 观察可声明的事实 |
| --- | --- | --- |
| provided-world | 直接提供有界规范 world bytes，由本入口计算 raw digest | 这份有限输入的实际重放；没有 query、响应或 solver 来源声明 |
| model-candidate | 同一不可变 SolverRequest、SatModel、ModelWorldCandidate | 严格重建候选；核对请求与模型 / 候选，以及 query binding 中的 IR raw / 文档域、完整 P2 raw、目标 ID、语义和实际 query profile |

model-candidate 路径调用既有 P4-A strict 候选核验，只用于来源 / 解码一致性，不用于目标求值。request 由 P4-A 不可变入口构造，不能从任意摘要或调用方 origin 拼装；unknown / unsat 没有 SatModel，不进入该路径。直接提供 world 不必先生成 SMT 或通过 stdin 上限，不能给它添加虚构 request / response 身份。

重放器源码身份沿用规范 `sha256:` GeneratorIdentity 的词法检查；它是声明，不是构建或来源认证。模型路径中的 P3 generator 与重放器 generator 分别保留，不因名称相近要求它们相同或合并。

拒绝次序为：profile / IR / 完整 P2 绑定、目标 expectation / kind / subject、整图支持扫描、来源绑定、world 格式 / 资源、WF、Pre、实际目标观察。前置拒绝不产生目标结论。严格记录比对前先检查候选记录字节上限；任何重建失败均保留真实原因。

## world 格式与输入检查

复用 [P4-A world](p4-request-response-model-v0.1.md#世界候选类型检查与外部化) 的抽象表示，不新建槽位或第二套世界格式。world 是 `{interface, table_type, rows}` 项数组，按 port 名排序，恰好包含全部实际 input 接口，包括空表和未被目标读取的输入。rows 是完整活动行，不含 active 位、模型槽号或 None 内载荷；table_type 必须来自该接口原节点。

值使用 bool / int / fixed / text / enum / none / some / record 的既有闭合 tagged 表示。数学整数为规范十进制字符串，Fixed scale 与 Enum / Record 类型 ID 精确匹配原类型。record.fields 恰好完整、按字段名排序；Some 的 value 递归符合原内类型，None 没有 value。Text 精确 Unicode，不做 NFC、大小写或 locale 变换；额外、重复、缺失成员、number、null、未知 tag、错误类型身份和坏整数词法为 WorldFormat 拒绝，不能补值或修复。Enum member 是 string，是否属于原枚举在 WF 中检查。

对象按 JCS 键序，UTF-8、无 BOM / 空白 / 末尾 LF；先核对词法字节、接口及字段数组的规范序。行的主键顺序在 WF 阶段核对，非法值使键不可比较时只返回对应输入拒绝，不声称世界已经通过全部规范检查。解析与规范编码使用平坦值 arena 和显式栈，world 深度预算与 IR JSON 深度分开，不将现有递归文档 parser 的 128 层上限当成所有世界的上限。类型引用无环；深 Record 的读取、编码和销毁均不得沿递归所有权展开。

WF 重新检查全部活动值范围 / 声明成员、行数不超过原容量及完整主键唯一。先按接口、规范行及深度优先字段序检查值；再查容量、主键顺序和唯一性，拒绝时选择首个见证。行顺序使用 Bool、数学数值、Enum 原成员序、Unicode scalar Text 的原语义顺序；降序为 NonCanonicalWorld，邻接等键为 input-rejected，不通过排序或去重修复。容量作为数学整数比较实际行数，不转换为预分配大小，也不按声明容量生成 inactive 行。排序只核对规范外部化，不给程序可观察行位置。

符合 world 结构但数值超范围、容量超限或重复键返回 input-rejected 观察并停止，携带接口、对应行 / 字段及真实原因；格式错误是错误返回，不伪装成合法输入上的目标违反。结构中的未知 Enum member 为输入拒绝，不能变成合法枚举零值。

IR v0.2 没有独立外键声明成员，外键由 assume 中的 forall_rows / lookup / match_option 公式表达。完成上述模式检查后逐项求值全部 assume；缺失引用使该公式 false / fault，进入 Pre 拒绝。不要从静态表类型或另一份材料推导没有声明的外键约束。WF 与 Pre 都不认证现实输入事实。

## 数学值与真实求值

使用自有有界十进制加减和已有 Integer 比较，或同等的现有依赖能力；不新增依赖、宿主浮点、固定宽度回绕或饱和。算术先求数学结果，再比较原 result_type；预算不够求出结果时返回 ResourceLimit，不能当成范围故障。Fixed 只计算同 scale 系数。通用 eq 只接受 P1 已允许的完全同型标量 / Option；不发明记录通用相等、Text 顺序或隐式转换。

P1 类型、规范表达式和图对象可以复用，必须在实现说明中列明依赖。运行值、故障与目标观察直接由原 IR 求出；不得调用 encode_query / SMT 解释器判真，不读取 SatModel 的派生输出，也不把 P3 的生产 ok / Ready 当期望。

每个表达式结果为值或故障；故障保留原 anchor、规范 path 和根因。严格构造必须完成各个适用兄弟的求值，收集所选 numeric-range 的可达实例，不能以首个兄弟故障停止其他兄弟：

| 构造 | 求值与可达性 |
| --- | --- |
| and / or / record | 所有操作数 / 字段严格求值；false / true 不短路，字段兄弟故障使整个 record 故障 |
| field / some / not / 二元比较与算术 | 严格求其操作数；field 保留完整记录构造的成功要求，不只读取被投影字段 |
| if | 先条件，只求实际 then / else；条件故障时没有分支实例 |
| match_option | 先 subject，只求实际 None / Some；Some 载荷前插为 de Bruijn 0，其余环境移位 |
| forall_rows | 引用成功表后求全部活动 body；首个 false 不跳过其他 body，空表值 true，任何 body 故障使公式故障 |
| lookup | 引用表成功后严格求全部 keys；按全部原主键分量匹配，零行为 None，一行为 Some；不对失败表读取占位行 |

图按依赖深度、再按节点 ID 处理，输入 / 中间表使用实际有限行，不展开所有声明槽位。input 来自已检查世界；map 对来源每行计算全部字段，filter 对每行计算一次实际谓词并保存结果。来源失败则本节点失败，不执行来源占位行。每个非 input 节点保存局部 Ready、容量前实际候选 O* 及自身成功；Ready 只含来源和全部活动局部求值成功，自身容量检查单独决定节点能否产生成功表。O* 不截断，不作成功输出使用。

ProgramOK 合取全部节点成功，包括没有命名输出的节点。全部 assume 仅引用输入，按契约 ID 求值并记录 false / fault；即使一个 assume false，仍完成其他适用 assume 的严格观察。Pre 为全部 assume 成功且 true，空集合为 true。Pre 不成立时不重放转换目标；不把其中的范围故障升级为有效输入反例。

所有 guarantee 的 range 位置仍有原身份，但动态实例只有 ProgramOK 成立时可达。所选 guarantee 在 ProgramOK 成立后求其公式；其他 guarantee 的真假 / 故障不改写所选目标。为某 guarantee 或节点观察而跳过不适用公式，不改变整图功能扫描与 P2 完整性。

## 五类目标与精确归因

只在 WF / Pre 成立后观察所选目标。原 subject 的 anchor / path 必须精确解析到原 IR 位置，不用输出字段名、源代码位置或候选名称代替。

| 目标 | 违反条件与必须保留的区别 |
| --- | --- |
| numeric-range | 所选 anchor / path 的某个真实动态实例满足 Reach、全部操作数成功、数学结果不在原 result_type 范围。父算术的操作数已故障时不制造父违例；子范围位置可独立违反。零实例或未选分支不违反；严格兄弟故障不屏蔽当前位置。guarantee 内实例另要求 ProgramOK |
| totality | 所选非 input 节点没有结果，包括依赖故障传播和自身容量失败。不能额外要求来源成功；无关 / 下游节点或 guarantee 故障不构成该目标违反 |
| key-cardinality | Ready 成立且 O* 的全部主键不唯一或行数超过原容量。自身容量不进入 Ready；来源 / 局部表达式故障使该关系不适用，不能把其故障当重复键或容量违例 |
| row-coverage | Ready 成立且双向恰好一次键覆盖不成立。独立按原 IR 的源选择与键映射得到期望键，按 O* 实际字段读取输出键，所有键分量参与；不从输出反推选择，不按槽号或总行数比较 |
| contract-guarantee | `¬(ProgramOK ∧ formulaOK ∧ formulaValue)`。程序失败按原目标规则构成该 guarantee 的违例，原因注明 program-fault；公式 fault / false 分别记录。禁止用全局故障代替节点或其他 guarantee 的精确目标 |

coverage 的 map 期望键从每个输出键字段的原直接来源投影取得，允许重命名和键序变化；filter 期望键来自实际谓词选中的直接 source。Forward 要求每个所选源键恰好匹配一个实际输出行，Backward 要求每个实际输出键恰好匹配一个所选源行。空来源 / 选择 / 输出正常；重复出现次数不能降为集合相等。

容量前候选只在 Ready 成立时用于关系观察。正确保留两行但输出容量为一：totality / key-cardinality 可以违反，coverage 不违反；截断才破坏覆盖。来源容量失败使下游 Ready false；无关或下游失败不屏蔽本地观察。

wrong-add 的业务数学等式由 guarantee 区分，wrong-drop-zero 忠实执行错误谓词时内建 coverage 可以成立，业务保留由原 guarantee 区分。静态字段来源合法、标签有缺口、另一个目标失败均不能改变这一归因。

## 内部观察、身份与诊断

制品 format 为 `axiom-p4-target-replay-observation`，version 为 `0.1`，遵循同一 JCS / 数字字符串 / 无 LF 规则。顶层闭合成员为 `{format, version, profile, rule_digest, binding, source, world_raw_digest, limits, result, usage}`。摘要取精确规范字节，不内嵌自身摘要。

- binding 闭合为 `{ir_artifact, ir_document_digest, obligation_set_artifact, obligation, semantics_digest, generator}`；摘要与身份从实际输入重建，generator 为声明的源码摘要。rule_digest 绑定接受时本文原始 UTF-8 字节。
- source 的 provided-world 形状为 `{kind:"provided-world"}`；model-candidate 为 `{kind:"model-candidate", request, response, candidate, query, query_profile, query_generator}`，分别使用实际不可变制品摘要 / 原绑定，不将来源声明当认证。
- world_raw_digest 对实际 world bytes 计算；输入整数 / Text / 行集合改变会改变它。input-rejected 保留这份无效输入的身份，不宣称其通过 WF；相同 world 的不同模型响应仍有不同 source / 整体观察身份。
- limits 恰含下一节列出的资源成员及 ir_json；usage 只含资源成员，数值表示本次实际收费 / 最大值，不能用静态上限填用量。ir_json 限制读取原 IR / 目标 definition 的 JSON，不重复生成 P1 / P2 耗费。

result 是以下四类闭合 tagged 对象之一。location 闭合为 `{anchor, path, context}`；anchor 是 IR 内容 ID，path 是 P2 相同规则的字符串数组。context 按由外到内的实际表遍历 / 逐行作用域序列排列，每项闭合 `{node, key}`；node 是所遍历表的实际节点 ID，key 按该表原主键顺序使用有类型标量值。Some 环境绑定不新增表遍历项，其选择由原 path 与外层输入确定；不输出临时槽号作为世界语义。

| result.kind | 其他且仅有成员 | 含义 |
| --- | --- | --- |
| input-rejected | interface、rows、path、reason | rows 为对应规范行序号的字符串数组；path 为值路径；reason 为 range、enum-member、capacity 或 duplicate-key。只报告规范检查次序下第一见证，不执行程序 |
| pre-rejected | contract、reason、location | reason 为 false 或 fault，location 对 false 指向公式根，对 fault 指向根因。按契约 ID、规范动态求值顺序选择第一个拒绝见证 |
| target-not-violated | observation | 当前有限世界没有所选违例；不声明普遍正确 |
| target-violated | witness | WF / 全部 Pre 成立，实际所选违反的确定性首个见证；不产生 Evidence failed 或证明支持 |

observation 与 witness 按目标种类闭合：

| 目标 | observation | witness |
| --- | --- | --- |
| numeric-range | `{kind, instances}`，instances 是实际所选位置实例数 | `{kind, location, operands, mathematical_value, result_type}`；operands 和结果用原 int / fixed tagged 值，越范围结果仍保留数学值 |
| totality | `{kind, node, ok:true}` | `{kind, node, cause}`；cause 为 `{kind:"range", location}`、`{kind:"capacity", node, actual_rows, declared_capacity}` 或 `{kind:"dependency", node, source, cause}`；依赖链迭代编码 / 释放，不吞根因 |
| key-cardinality | `{kind, node, ready, unique, capacity}`；Ready false 时用 `{kind, node, ready:false, cause}`，不读取 O* | `{kind, node, reason, rows, key}` 或 `{kind, node, reason, actual_rows, declared_capacity}`，reason 分别为 duplicate-key / capacity；两者均不成立时先重复键、再容量 |
| row-coverage | `{kind, node, ready, forward, backward}`；Ready false 时用 `{kind, node, ready:false, cause}` | `{kind, node, direction, key, matches}`，direction 为 forward / backward，matches 为规范整数；先规范源键序、再输出键序选择首个非一次匹配 |
| contract-guarantee | `{kind, contract, program_ok:true, formula_ok:true, value:true}` | `{kind, contract, reason, cause}`，reason 为 program-fault / formula-fault / false；false 的 cause 为公式根 location，其他为上述根因 / location |

kind 取对应 P2 原 kind 字符串。没有 body 实例的 numeric-range 不填伪 operands。动态父实例在操作数故障时不算一次有效运算；instances 统计实际到达该位置的调用，见证另要求操作数成功。Bool 成员是真 bool，序号 / 数量 / 容量为规范十进制字符串。cause 只使用已声明的 range / capacity / dependency；结构、unsupported 与预算是错误返回，不伪装成运行故障。首个范围 / 公式故障依原规范子项序和表键序选择；program-fault 依节点的依赖深度 / ID 顺序选择首个失败节点。确定性首见证不声明最小性。

target-not-violated 只限当前输入，包括范围零实例或关系 Ready false 的观察；Ready false 不代表 totality 成立。若所选目标实际违反，不能用另一项 true 覆盖它。记录检查严格重建全部结果、见证、绑定、来源和预算，首个字节差异拒绝；这是生产路径复核，不是独立证明。

## 预算与终止

调用方提供全部上限，不设无限 default；上限包含等号，checked 加乘溢出为资源拒绝，费用先于分配 / 复制 / 执行。ir_json 使用既有 JsonLimits。其余 limits / usage 使用以下同名成员：

| 成员 | 计数方式 |
| --- | --- |
| world_bytes | 原 world 输入字节数，解析前观察；model 路径另受原 P4-A 不可变预算限制 |
| world_nodes / world_depth | 解析的标量 / tagged / 容器节点累计数、最大 JSON 结构深度；专用迭代读取，不复用 IR 深度上限 |
| type_items | 读取的类型 DAG 节点、字段 / 键描述项，建立索引前累计 |
| rows | 各实际输入 / 中间候选行数组中新分配的项累计数；共享行引用仍为数组项收费，不展开声明容量 |
| value_cells | 平坦值节点、字段边、环境 / 工作栈 / 缓存 / 排序索引项及复制的字符串字节累计数；共享不可变值本体不重复复制收费 |
| evaluation_steps | 实际调用的表达式 op、节点 / 契约检查、任务栈步骤累计数；循环操作前收费 |
| comparisons | WF 键、lookup、目标键关系和排序的实际标量分量比较累计数；不得只计成功匹配或返回结果 |
| integer_digits | 单个范围 / 输入 / 中间数学整数 magnitude 与必要序号的最大位数；构造 / 复制前检查 |
| digit_work | 数字加减 / 比较逐位工作累计数，至少按实际访问位数收费；超预算不是算术故障 |
| text_bytes | 读取 / 复制 / 对比 Text 的 UTF-8 工作累计字节数；长公共前缀不能只按一次比较收费 |
| path_bytes | 新复制的 location / 值路径及动态上下文规范字节累计数，不按所有类型路径重复展开 |
| output_bytes | 最终完整观察的规范字节数，两遍迭代计数后分配；拒绝无部分成功记录 |

逐行值共享类型 DAG，图按拓扑缓存一次真实结果；不能枚举所有世界、无限展开路径或为大声明容量预分配。深记录 / 图、上下文、规范编码和根因链使用显式有界栈，销毁不沿输入构造递归展开。表达式的静态 JSON 深度仍受 P1 原预算约束。重放预算不能当 OS 硬内存或墙钟保证，不承诺宿主 OOM 可恢复。

错误区分 unsupported profile / IR、BindingMismatch、UnknownObligation、NotProve、UnsupportedKind、UnsupportedFeature、WorldFormat、NonCanonicalWorld / Observation、ResourceLimit 与内部不变量；带阶段、资源或可定位字节 / anchor / path。预算耗尽没有 target-not-violated 或 unknown 结果，真实执行层的未知状态也不被本组件制造。

## 必须完成的合成与本机验收

| 材料 | 判定 |
| --- | --- |
| 原 AX-B01 三候选、原容量 100、全部适用五类目标 | 直接有限 world 实际重放；wrong-add / wrong-drop-zero 的 guarantee 手算区分，coverage 归因保持，不从名字判定 |
| 既有 P3 四版有限输入 / 目标清单 | 转为原 tagged world，生产实际观察与 Python 从原 IR 的具体解释一致；只声称有限输入核对 |
| P4-A 合成 SatModel / candidate、打印顺序 / Text atom 重命名 | 同 world 语义观察一致，来源 / 整体摘要分别保留；unknown 不得形成模型路径输入 |
| 空表、零容量、多接口、Record / Option、100 位数 / Fixed / Enum / Unicode | 完整 WF / Pre，None 不读载荷，数值 / 键顺序与手算一致 |
| 外键 assume、Pre=false / fault、重复键 / 范围 / 容量无效 | 输入或 Pre 拒绝，无目标违反状态，不自动修复 |
| 无关 / 下游故障、另一个 guarantee false、上游依赖故障 | 选定节点 / guarantee 精确归因；“其他目标失败而本目标成立”分别验收 |
| and / or / record 严格兄弟、field 构造兄弟故障、if / match 未选故障 | 真 Reach，不短路、不把子故障归给父算术；Some 环境移位核对 |
| Ready false、目标自身容量超限、容量前两行与空选择 | 关系不读占位值，不加 targetOK / ProgramOK 守卫，不截断 |
| 复合键 / 重命名 / 换序、重复出现、NFC / NFD | 所有键分量与双向恰好一次；生产关系函数在仅测试构建中接受独立局部材料核对负例 |
| 深度 5,002 Record、深图、巨大声明容量与小实际 world | 有界迭代解析 / 求值 / 编码 / 销毁；不通过缩小原容量或放宽原 query 限制达成 |
| 精确预算 / 差一 / 溢出、巨大整数 / Text 前缀 | 可定位资源拒绝，数字或资源耗尽不变成语义 fault |
| 改 world / target / source / Pre / witness / budget、旧 profile / 格式 | 生产 strict 与独立有限核验拒绝，各自作用清楚，旧制品字节保持 |

独立 Python 路径直接解释原 IR，不导入 Rust replay / SMT，复用已有自有具体解释时说明其有限支持，并补足 typed world、外键 Pre、动态位置与精确见证的检查。手算例必须另行书写，不能只由重放器生成自己的期望。原 P3 的完整程序与局部关系材料分别标识：P1 合法 map / filter 不任意丢行或造重复键，无覆盖违例不证明生产实现正确。

本切片未验证真实 solver 输出、完整 Evidence、独立 checker、其他平台、最小反例、生产 gate / runtime 或正式 Agent 收益。AX-B01 stdin 尺寸阻断保持，另行审阅新的查询表示或资源 profile，不由本草案接受。
