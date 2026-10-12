# P4-A 请求、响应与模型解码 v0.1

日期：2026-10-12。状态：Accepted，依据 [ADR 0025](../adr/0025-p4-request-response-model-decoding.md)。

用途：固定 P4-A 的内部输入输出、query0.2 adapter 对应关系、模型子集、确定性世界表示、资源和验收，供项目所有者与实现者审阅。

不包含：进程启动、实际工具校准、P4-B 的 WF / Pre / 目标重放、完整 Evidence、公共 proof support、独立 checker 或执行许可。本规则只接受内部纯组件，不表示实现或真实执行已验收。

## 现状与选择依据

`EncodedQuery` 已有不可变 bytes、raw digest、完整 `QueryBinding` 与 `QuerySymbol`；`SymbolOrigin::Input` 保存 port / slot / component，component 按记录规范字段序深度优先展开，Option 标签占一叶。它们可作为解码入口，但不包含可直接信任的调用方 world。

旧 [execution profile](../../contracts/execution-profiles-v0.1/fixtures/positive/cvc5-1.3.4-qf-uflia-v0.1.jcs)已有 produce / dump / check models 和 produce / check proofs。P3 四版 query 都使用 artifact `axiom-smtlib2-qf-uflia-query0.2`，与旧 adapter 的公共对应关系未闭合。本稿只新建内部对应关系，不修改旧绑定文件。

2026-10-12 只读核对 cvc5 官方 1.3.4 材料得到以下静态依据：

| 材料 | 可支持的判断 | 不能据此声称 |
| --- | --- | --- |
| [command_executor.cpp](https://raw.githubusercontent.com/cvc5/cvc5/cvc5-1.3.4/src/main/command_executor.cpp)，`doCommandSingleton` | dump-models 在 sat 或 unknown 且解释为 INCOMPLETE 时触发 GetModelCommand；本批无需追加 get-model；produce-proofs 与 dump-proofs 的触发分开 | 本机 stdout、退出码、性能或隔离已经验收 |
| [smt_options.toml](https://raw.githubusercontent.com/cvc5/cvc5/cvc5-1.3.4/src/options/smt_options.toml)，`modelCoresMode` | model-cores 默认 NONE；启用其他模式可能仅保留部分变量，不能满足本批完整符号要求 | 默认模式一定输出本查询所有自由符号 |
| [1.3.4 options](https://cvc5.github.io/docs/cvc5-1.3.4/options.html)，Printing Module | model-u-print 默认 none，不声明未解释元素；其他打印模式是不同文法 | 本批 Text atom 子集已覆盖精确 payload 的全部打印行为 |

上述可访问版本化 URL 只作设计引用，不作为运行时依赖、payload 认证或 source digest。未复制第三方源码或样例；下文例子均为自有合成材料。模型 body、注释、辅助定义和异常路径仍需在后续真实工具校准中逐项核对。

## 显式支持与三个入口

内部 profile 为 `axiom-p4-cvc5-1.3.4-query0.2-model-v0.1`，支持以下显式 query profile，拒绝未知字符串和旧 query0.1：

- `axiom-p3-map-filter-query-v0.1`；
- `axiom-p3-map-filter-query-v0.2`；
- `axiom-p3-map-filter-query-v0.3`；
- `axiom-p3-map-filter-query-v0.4`。

目标支持集合仍由原 query profile 决定：numeric-range、contract-guarantee、以及在原版本增加的 totality、key-cardinality、row-coverage。join / group、聚合和双世界继续沿原 query 错误拒绝，P3-E / F 记录不当作 SMT query。

| 入口 | 输入 | 成功输出 |
| --- | --- | --- |
| `plan_solver_request` | profile、IR v0.2 CanonicalDocument、完整 P2、目标 ID、EncodedQuery、原 GeneratorIdentity、工具身份、预算 | 不可变 SolverRequest、精确 stdin bytes、重建符号 / 类型布局与资源用量 |
| `parse_solver_response` | SolverRequest、绑定该请求的有界 stdout / stderr、流完成标记、进程退出 / 外层终止观察 | SatModel、UnsatResponse 或 UnknownResponse；内部观察均保留请求与响应摘要 |
| `decode_model_world` | 同一不可变 SolverRequest 与 SatModel | 完整 ModelWorldCandidate、Text 类映射、规范 bytes / raw digest 与资源用量 |

错误带阶段、分类、资源名或原输入路径 / 符号 / 字节位置。资源错误、query 未支持、协议错误和非法活动输入分别保留，不伪装成 solver unknown。解析 / 解码按请求中不可变预算执行，不接受另给的更宽限制；各阶段报告自己的用量，重新调用不重解释前次结果。解码只接受与同一 request raw digest 绑定的 SatModel；unknown 附带模型仍不能进入该入口。

生产实现复用现有 crate 的 JSON、Integer、P1 类型对象和 digest。协议 tokenizer、别名求值与世界物化按职责拆分，不建立通用 runner 或任意 SMT 求值器。布局从相同编码入口和类型定义重建；P1 / P2 / query 依赖须显式记录，本仓组件不等于跨仓独立检查。

## 请求绑定与闭合表示

规划先用原 profile / document / set / target / generator / query budgets 重建 query，比较 bytes、binding 和完整符号 origin / sort；不能仅比较 SMT 摘要。完整 P2 已由不可变构造入口重建；document raw / document 域、P2 raw、目标与语义必须匹配。输入预算不足时拒绝，不用较小容量重建。

请求成员使用现有 canonical JSON 口径：对象按 JCS 键序，数组按下表规则，数学数值为规范十进制字符串，末尾无 LF，未知 / 缺失 / 重复成员拒绝。raw digest 为 `sha256:` 加 64 位小写十六进制，对精确 bytes 计算，不把文档域身份当 raw digest。请求不内嵌自身摘要以免自引用。

| 请求成员 | 精确内容 |
| --- | --- |
| `format` / `version` | `axiom-p4-solver-request` / `0.1` |
| `profile` / `protocol_rules` | 上述新内部 profile / 本规则精确原文的 raw digest |
| `query` | 闭合 `{artifact_type, dialect, encoding_profile, raw_digest, byte_length}`；artifact / dialect 沿原 query 常量，byte_length 为完整 stdin 长度 |
| `binding` | 闭合 `{ir_artifact, ir_document_digest, obligation_set_artifact, obligation, semantics_digest, generator_source}`，逐项沿原 QueryBinding |
| `symbols` / `layout` | 下述两个精确规范制品的 raw digest；制品在 SolverRequest 中不可变保留 |
| `tool` | 闭合 `{name, version, platform, payload_digest, acceptance_record_digest}`；name / version 为 cvc5-cli / 1.3.4，platform 从现有六平台集合选择，两个摘要必须合法且显式提供 |
| `adapter` | 闭合 `{status, base_execution_profile, base_execution_profile_digest, argument_tokens, stdin}`；status 固定 `planned-not-calibrated`，base 固定旧 cvc5 profile 及其精确 raw digest，stdin 固定 `query-bytes-then-eof` |
| `limits` | 闭合 `{tool_internal, process_outer, component}`，精确集合见资源节；所有值参与请求摘要 |

工具摘要是调用方声明的目标身份，不由纯组件认证是否存在、已验收或实际被执行。真实执行层必须另核验 payload、acceptance、platform、adapter 与 OS 保证；不能因请求有这些字段自动授权。测试可用明确标为合成的身份，不写入正式 registry。

`argument_tokens` 保留旧 profile 的字面参数序，将两项 limit-option 展开为 `--rlimit-per=1000000`、`--tlimit-per=5000`。不接受调用方参数、路径、环境或命令字符串，不追加 get-model、echo、reason-unknown 或 proof 命令。本批不增加 model-cores / model-u-print 选项；真实默认输出超出子集时另审阅 profile，不用 option 注入补救。

符号制品 format 为 `axiom-p4-query-symbols`、version 为 `0.1`，闭合 `{format, version, query_raw_digest, symbols, derived}`：

- symbols 按完整名称的 Unicode scalar 字典序排列；每项闭合 `{name, sort, origin}`。sort 为 Bool / Int / Text；origin 为 `{kind:"input", interface, slot, component}` 或 `{kind:"text-literal", value}`；slot 为非负十进制字符串，component 为 `active` 或非负十进制字符串。
- derived 为精确 query 中已知 define-fun 零参数名称 / sort 的完整清单，按名称排序；每项闭合 `{name, sort}`。它由受信任的编码输出重建，不能按名称前缀任意放行。模型中可以省略这些派生项，出现时须检查；不把它们视为自由输入或重放值。

布局制品 format 为 `axiom-p4-input-layout`、version 为 `0.1`，闭合 `{format, version, ir_artifact, query_raw_digest, inputs}`。inputs 按 port 名排序，每项闭合 `{interface, node, table_type, record_type, capacity, primary_key, components}`。node / table_type / record_type ID 与容量 / 主键顺序取实际 IR；components 按深度优先叶序，每项闭合 `{index, path, role, sort, value_type}`：path 为记录字段名数组；role 为 `value` 或 `option-tag`；option-tag 的 value_type 为对应 Option，value 的 value_type 为原规范叶类型 definition。多层 Option 在相同字段 path 的不同 component index 上区分，所有 Option 标签先于自身内值。

布局与符号必须逐槽位精确对应，包含全部输入节点、零容量接口、活动位和未活动载荷；不依赖 port 名或字段名硬编码推测列位置。完整 IR 身份仍绑定未被目标读取的节点 / 契约。

## 响应封装、失败优先级与帧

纯组件接收内存中的有界字节，不读文件或开启进程。调用方提供以下闭合观察：request raw digest、stdout / stderr 精确 bytes、两流 complete / truncated、exit（exited code / signaled code / unavailable）、outer termination（none / deadline / memory / stdout-limit / stderr-limit / crash / unavailable）。这些都是待执行层认证的观察，不是 parser 的来源保证。

响应观察的规范记录闭合为 `{format, version, request, stdout, stderr, exit, outer_termination}`，format 为 `axiom-p4-solver-response-observation`、version 为 `0.1`。request 为请求 raw digest；stdout / stderr 各为 `{raw_digest, byte_length, complete}`，complete 是 boolean，byte_length 为规范非负十进制字符串。exit 是 `{kind:"exited", code}`、`{kind:"signaled", code}` 或 `{kind:"unavailable"}`，code 为规范非负十进制字符串；不能将缺失退出状态当成 exited=0。outer_termination 是上述已知字符串之一。记录不内嵌 stdout / stderr、自己的摘要或派生语义结果；原始流是外部绑定字节，不改写后复用原摘要。

记录的规范摘要区分“同 stdout、不同请求 / 退出 / stderr”。不把日志字符串当可信终止原因，不从 stderr 中的 sat / timeout 等词推导状态。正常结果中保留该不可变记录及摘要；拒绝路径保留有界诊断与原观察，不生成伪成功记录。

判定先验证绑定，再检查字节边界并记录外层终止 / 非零退出 / 流不完整，最后才解析状态与模型。绑定错误为主要拒绝原因；绑定正确时，已报告的外层终止优先于非零退出、流超限 / 不完整及协议错误。可同时保留多个诊断；任何硬失败都不能产生 SatModel / UnsatResponse 的成功结果。真实外层原因不得被二次 UTF-8 或 parser 错误覆盖；输出超限的诊断只记录长度 / 摘要，不复制超限 bytes。

正常路径要求 exited code 0、两流 complete、无 outer termination；stderr 是有界 UTF-8 诊断，可以非空，不承载语义状态。正常路径的非 UTF-8 stdout / stderr、未知控制字符、截断与冲突拒绝。

词法允许 ASCII 空格、TAB、CR、LF；`;` 至 CR / LF / EOF 的行注释是 trivia，注释字节计入 stream / token-byte 预算且不解释内容。状态必须是第一个非 trivia token，大小写精确；只允许一个状态、至多一个模型帧和完整 EOF：

```text
response := "sat" model EOF
          | "unsat" EOF
          | "unknown" [model] EOF
model    := "(" definition* ")"
```

不接受 `(model ...)` 包装、success、echo、额外状态、额外帧或 `(error ...)` 作为成功输出。unknown 的可选模型遵守同一文法与成员 / 类型 / 别名规则，但不要求所有自由符号齐全；无模型或不完整模型都只能返回 UnknownResponse。unknown 后的损坏帧记录协议诊断及原状态，不能升级为 sat 或无诊断成功。

unsat 是后端响应观察，不是 proved；本批既不收 proof 帧也不填 backend-attestation。尚未启动工具不形成 attempt；合成 exited=0 只用于纯组件测试。

## 模型文法与完整性

```text
definition := "(" "define-fun" name "(" ")" sort value ")"
sort       := "Bool" | "Int" | "Text"
Bool-value := "true" | "false" | same-sort-alias
Int-value  := numeral | "(" "-" positive-numeral ")" | same-sort-alias
Text-value := text-atom | "(" "as" text-atom "Text" ")" | same-sort-alias
numeral    := "0" | [1-9][0-9]*
positive-numeral := [1-9][0-9]*
text-atom  := "@Text_" numeral
```

name / alias 必须来自请求中精确的自由或派生名称清单；QuerySymbol 当前由编码器生成 ASCII 名称。拒绝带参数定义、任意额外名称、声明新 sort / datatype / function、quoted symbol、字符串 literal、Real / 浮点 / bit-vector、带正号或前导零数字、裸 `-1`、`(- 0)`、算术 / ite / let / lambda / 量词等其他 term。未知 token 以字节位置拒绝，不执行或交给宿主解释。

只支持 typed Text atom，并将裸 / as 形式的同 atom 归为同类；不依 atom 编号推出任何字符串值。该命名子集是已接受的内部支持范围，未校准其与实际 printer 的全部对应关系。其他未解释元素打印模式须另建 profile。

所有定义名称全局唯一；声明 sort 必须与请求清单一致；value 文法按声明 sort 验证。同 sort alias 可前向引用，但必须在模型内有定义，终点必须是该 sort 的常量；未知 alias、跨 sort、直接 / 间接循环拒绝。用显式栈 / 访问状态及缓存消解，共享链不反复展开；定义顺序不影响结果。派生项出现时也逐项检查，不忽略未被输入引用的坏定义；它们的值不认证原 SMT 计算，也不作为程序重放答案。

sat 中每个自由 QuerySymbol 必须恰好有一项定义并能消解，包括全部 Text literal、inactive 槽位与 None 的全部内部叶；缺项即拒绝，不使用 solver completion、默认值或任意类来补齐。派生项可省略，只因它们不承载自由输入；新 profile 不因此省略任何活动位或叶。

## Text 等价类与确定性替换

Text 映射在完整自由符号模型上执行，不只扫描最终活动行。步骤如下：

1. 消解所有自由 Text QuerySymbol，按终点 atom 划分等价类；alias 表示同一值。派生项不参与类编号，打印顺序和 atom 编号不进入 world 身份。
2. SymbolOrigin::TextLiteral 将其类锚定到原精确 Unicode literal，包括编码器显式声明的空 Text。不同 literal 若落入同一类，返回 `LiteralClassConflict`；不合并字符串、做 Unicode 规范化或按模型名称补猜 literal。
3. 无 literal 的类按该类自由 QuerySymbol 完整名称的最小值排序，使用 Unicode scalar 字典序。槽位是否活动不改变编号规则。
4. 对第 i 个新类，从 `@axiom-text:i:0` 开始递增最后一个规范十进制数，选择不在所有已知 literal 或此前分配集合中的首个字符串；i 从 0 开始。每次候选构造 / 检索计入解码步骤与 Text 字节预算，溢出或预算不足拒绝，不返回部分映射。
5. 只在物化的 Text 叶写入结果字符串；None / inactive 载荷不外部化。伴随映射只保留实际物化叶读取的新类，symbols 只列这些活动叶所引用的自由名称，按全局类序排列；未物化类仍参与确定性编号，但不导出其值 / 名称。映射项为 `{symbols, text}`，不保存易变 atom 名作为世界语义。

合成映射只保留本域的精确相等与不同已知 literal 的区分，不声称还原求解器的原字符串。Text 不支持额外顺序 / 长度 / locale 语义；将来增加此类构造必须另审阅解码算法。

手算例：已知 literal 集合含 `""`、`"é"`、`"@axiom-text:0:0"`。自由符号 s1 / s3 共享未锚定类，s2 单独一类，且 s1 < s2 < s3；第一类分配 `@axiom-text:0:1`，第二类分配 `@axiom-text:1:0`。互换定义顺序、统一重命名 Text atom 或通过 alias 定义 s3，完整 world 与伴随映射相同；将不同 literal 合并时拒绝。s1 / s2 / s3 仅是本段手算符号，不放宽生产名称白名单。

## 世界候选、类型检查与外部化

根据布局按原 capacity 的全部槽位读取 active 与 components。所有槽位的模型叶都先完成文法 / sort / 完整性检查；只在 active=true 时物化整行，Option 只在 tag=true 时物化内值。对 inactive 行与 None 遮蔽的叶不检查 IR 数值范围 / Enum 序号，也不将遮蔽值放入候选、伴随诊断或日志；缺失和错误 sort 仍拒绝。

物化规则：Bool 使用精确 boolean；Int 按任意精度数学整数；Fixed 使用同整数系数及原类型 scale，无浮点换算；Enum 的活动整数索引须在原成员序范围内，输出原 enum ID / 成员；Record 按完整规范字段序递归物化并携带实际 record ID；Option 输出显式 None / Some。活动 Int / Fixed 越界、Enum 非法或布局不符返回路径定位诊断，不调整数值或截断行。

检查所有接口的完整闭合类型、容量与键唯一性。行按原 primary_key 顺序逐分量比较：Bool false < true，Int / 同 scale Fixed 用数学整数序，Enum 按成员声明序，Text 按 Unicode scalar 字典序。重复键拒绝，排序不去重；不按十进制字符串或模型槽位顺序排序。不同 input port 指向等价数据仍是独立接口，不合并。零容量或零活动行输出空表，不能省略接口。

外键和全部 assume 是完整 WF / Pre 的组成部分，在 P4-B 直接解释原 IR 时统一检查。本批类型 / 范围 / 键检查不标为完整 WF；不执行转换、评估 guarantee 或判断目标违反。候选名称、全局故障位或模型里的派生值不能决定 failed。

候选制品遵循同一 canonical JSON 口径，format 为 `axiom-p4-model-world-candidate`、version 为 `0.1`，闭合成员为 `{format, version, request, response, world, text_classes}`。request / response 是各自精确记录的 raw digest；候选没有 proved / checked / unknown / failed / trusted 字段。

`world` 为按输入 port 名排序的数组；每项闭合 `{interface, table_type, rows}`，rows 按上述键序排列，空表使用空数组。`text_classes` 按全局新类编号序排列，只包括实际物化叶读取的无 literal 类，项为 `{symbols, text}`；symbols 是这些活动叶所引用的自由名称按规范序排列。world / text_classes 有各自可取出的规范字节和 raw digest，整体候选另有 raw digest。同一请求下，模型打印顺序 / atom 重命名不改变 world / text_classes 字节；响应 raw 摘要改变时整体候选摘要正常改变，不能错误要求整体候选同身份。

值为以下闭合 tagged union；数值不使用 JSON number，boolean 使用 JSON boolean：

| kind | 完整成员 | 取值 |
| --- | --- | --- |
| bool | `{kind, value}` | value 为 boolean |
| int | `{kind, value}` | value 为规范有符号数学十进制字符串 |
| fixed | `{kind, scale, coefficient}` | 两个数均为规范十进制字符串，scale 取原类型 |
| text | `{kind, value}` | 精确 Unicode string |
| enum | `{kind, enum_type, member}` | 原类型 ID 与声明成员 |
| none | `{kind}` | 无内部载荷 |
| some | `{kind, value}` | 精确对应内类型的 tagged value |
| record | `{kind, record_type, fields}` | fields 按字段名排序，项为 `{name, value}`，恰好完整闭合字段 |

这是内部候选格式，借用现行语义的值与键序，不能直接作为 Evidence v0.2 的 public counterexample 或重解释 v0.1。后续 Evidence 接入须按 ADR 0009 另行接受。

## 预算与失败收费

请求保留旧指定态资源值：tool_internal 的 semantic_steps=1000000、wall_clock_ms=5000；process_outer 的 stdin_bytes=1048576、stdout_bytes=4194304、stderr_bytes=65536、wall_clock_ms=6000、working_memory_bytes=134217728。这些值是规划，不是已施加的 OS 保证；P3 可生成超过 stdin 上限的 query，但 P4-A 对该请求须拒绝，不能临时增限。

component 有下表全部成员及 `query`，所有标量都是非负规范十进制字符串，调用方显式提供，不设隐式 default。query 闭合为 `{ir_json, max_input_slots, max_value_cells, max_expression_instances, max_slot_comparisons, max_smt_nodes, max_output_bytes}`，ir_json 闭合为 `{max_input_bytes, max_values, max_nesting}`，逐项对应原 P3 QueryLimits / IR JsonLimits；它们也参与请求绑定。tool_internal 闭合为 `{semantic_steps, wall_clock_ms}`；process_outer 闭合为 `{stdin_bytes, stdout_bytes, stderr_bytes, wall_clock_ms, working_memory_bytes}`。零值可用于 component 拒绝边界测试，不自动解释为无限；tool_internal / process_outer 是前述固定值，本 profile 不允许调用方放宽。

| 成员 | 计费单位与时机 |
| --- | --- |
| `request_bytes` / `response_bytes` / `symbol_bytes` / `layout_bytes` | 规范输出 bytes，编码前估算 / 检查长度，再分配 |
| `tokens` / `token_bytes` / `syntax_nodes` / `syntax_depth` | token 数、含注释的累计词法 bytes、AST 节点与操作数边、最大括号深度；复制 / push 前收费 |
| `integer_digits` | 单个整数 magnitude 的最大十进制位数；包含模型、计数和 atom 序号，不转为固定宽度载体 |
| `definitions` / `alias_edges` | 累计定义与别名边，插入表 / 缓存前收费 |
| `layout_items` / `input_slots` / `value_cells` | 类型 DAG 与描述项、全部槽位、布局 / 消解 / 物化节点及边，展开或复制前收费 |
| `decode_steps` | 遍历、消解、排序比较、Text 候选构造 / 查找与键比较；每次操作前收费 |
| `text_bytes` / `world_bytes` / `candidate_bytes` | 合成字符串与所有规范输出累计字节；包含 UTF-8、JSON escaping、接口和类型 ID |

计数先 checked_add / checked_mul，溢出与超限均 ResourceLimit，带具体阶段 / 资源；失败没有部分成功制品。大容量在任何槽位展开前与 input_slots / 原 query limits 检查；复合记录共享 DAG，不枚举所有类型路径或世界。别名使用有界图，释放 AST / 值不依恶意深递归；显式栈也收费。排序比较和负路径要有预算，不能仅限制返回数据大小。

固定文法实现使用流式 token，不建立递归 AST：token_bytes 对完整 stdout 长度收费（含 trivia），每个 token 在返回前保守计 syntax_nodes 的一个节点和一条边，syntax_depth 取最大括号深度。IntegerDigits 取单值最大 magnitude / atom 序号位数。Text 类与世界行排序均使用可中止的索引归并，复制索引 / 项和比较前收费；ValueCells 包括复制字符串字节、容器项、缓存、物化节点 / 边及两次规范编码的显式工作栈，不声称精确宿主分配字节。

component 预算仅描述逻辑资源，不保证真实墙钟或峰值内存。响应必须已由将来执行层流式施加 process_outer 上限；纯组件再次核对长度，不能用“输入已在内存”放开字节限制。

## 必需验收矩阵

下表是必需验证要求；实际运行结果在本批验收记录中单独报告，不能从本表推导能力或测试数。

| 材料 | 应取得的结果 |
| --- | --- |
| AX-B01 correct / 两个 wrong 的实际 IR / P2 / 可生成目标，四个 query profile | 请求逐项绑定，原 query bytes / digest / symbols / usage 保持；候选名称不决定结果 |
| 相同 query 字节但不同 profile / generator / P2 / target / budget / payload | 请求身份按实际绑定区分；错配输入拒绝 |
| 旧 query0.1 / 旧 adapter / 未知 profile / 缺 acceptance 身份 / 未支持图 | 定位拒绝，不复用相邻 profile 或旧摘要 |
| sat、unsat、unknown 无模型、unknown 带模型 | 精确状态帧；仅完整 sat model 可解码，unknown 永不形成 world |
| 重复状态 / 重复帧 / error / 尾部垃圾 / invalid UTF-8 / 缺括号 / 截断标记 | 拒绝且保留位置、stream / exit 原因 |
| sat 文本 + 非零退出 / signal / deadline / memory / output-limit / unavailable | 硬失败优先，不由 sat 或 stderr 日志覆盖；组合原因可追溯 |
| 大于机器宽度整数、负数、Bool、Enum、Fixed、嵌套 Record / Option | 与独立手算类型布局和活动值一致；数学值不截断 |
| 缺自由符号、重复定义、未知额外名称、错 sort、别名循环 / 缺终点 / 跨 sort | 拒绝，含 inactive / None 载荷也不豁免完整性 |
| 多层共享 / 前向 alias、已知派生名称可选存在、定义次序交换 | 常量消解一致且有界；派生值不作为转换输出，未知坏辅助成员拒绝 |
| Text literal 锚定、冲突、新类、合成名撞 literal、atom 重命名 | 精确等价关系、无碰撞、world / 映射身份稳定；整体候选保留不同响应摘要 |
| 稀疏活动槽位、零容量、空表、多 port、不相关输入 | 完整接口保留，按语义键序外部化，未激活载荷不泄入 world |
| inactive / None 中越界整数或非法 Enum，活动叶的同值 | 遮蔽时允许文法有效的载荷；活动时范围拒绝，缺项 / 错 sort 两者均拒绝 |
| 数字主键 -10 / -2 / 2 / 10、Enum 非词法成员序、Unicode / 复合键 | 数学 / 成员 / scalar / 原主键序正确；重复键拒绝不去重 |
| world 类型检查通过但外键 / Pre 不成立，目标之外故障 | P4-A 只给候选与已做检查；后续 P4-B 按精确原因拒绝，不提前给反例状态 |
| 每项预算精确值 / 差一、深 / 宽输入、累计溢出、巨大容量 | 拒绝发生在对应分配 / 操作之前，无部分输出或隐藏放宽 |
| 请求 / 响应 / 布局 / world 的篡改与未知版本 | 生产严格重建和独立检查区分并拒绝，原规范 / fixture 不漂移 |

独立材料至少包括手写的完整期望与独立 Python 解码 / 排序对照；不能用 Rust 输出或同一个 helper 同时生成模型和唯一期望。真实 IR / P2 生成输入与合成 stdout 分别标识来源；测试不调用真实 solver。后续必须分别报告“协议解析一致”“候选类型 / 键检查通过”“真实重放反例”“真实工具校准”，前两项不能计入后两项。

## 完成、交接与停止条件

完成三个真实纯入口、版本化规范输出、上述风险匹配验收，并运行显式已安装工具链的格式、Clippy、workspace 测试与仓库检查。规范接受与组件验收分别报告；未通过实际验证前不报告 P4-A 已完成。

下一切片为 P4-B：直接解释原 IR，重放 WF / 全部 Pre 与五类精确目标，保留“其他目标失败但本目标成立”的区分例，单独审阅其范围。真实 cvc5 校准 / 执行还需精确 payload / 许可验收、new adapter、执行宿主、OS hard memory / deadline 与当前任务授权；公共 Evidence、proof support、跨仓和正式实验门禁继续保留。
