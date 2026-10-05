# Axiom IR 内部组件

本 crate 承载 [ADR 0016](../../docs/adr/0016-core-semantic-slice-entry.md) 的 P1 实施。当前实现 [IR v0.1](../../docs/ir/axiom-ir-v0.md) 的 JSON 字节边界、类型声明身份、受限表达式类型 / 规范化、节点与契约分析及内容身份，并重建保守字段 / 控制标签；已组合现有支持范围内的完整 IR 规范字节、strict canonical 检查和文档身份。表达式支持尚未收口，P1 尚未完成；不提供 CLI、Evidence 或执行门控。

## 输入与输出

`json::canonicalize_json(bytes, limits)` 接受有界 UTF-8 JSON，禁止 number / null，拒绝重复解码成员名、非法语法和未配对 surrogate。输出按 UTF-16 code unit 排序对象成员，采用最小字符串转义，无 BOM、额外空白或末尾换行。数组顺序与字符串内容保持原样，不做 NFC、大小写折叠或十进制字符串改写。

该函数返回 `Ok` 仅表示 JSON 子集的解析与编码成功。例如 `true`、`{}`、名称中的转义控制字符、`"-0"` 和未知 IR 字段都可以通过 JSON 层；领域约束由后续步骤检查。不能将此函数输出标成已经验收的 canonical IR 或 Evidence。

`declarations::decode_type_declarations(bytes, limits)` 从同一 candidate 输入解码类型声明，检查：

- 顶层精确成员、IR `0.1`、语义名称 / 摘要、`sha-256`、空效果及顶层数组形状。
- enum / record / table 声明与全部七种内联值类型的闭合结构、标签，以及字段 / 枚举成员 / 主键名称唯一性。名称按规范拒绝空串、C0 `U+0000..001F` 和 C1 `U+0080..009F`，不扩展为其他 Unicode 类别过滤。
- 整数规范词法、非负 scale / capacity 和 `lower <= upper`。`integer::Integer` 保留完整十进制文本并精确比较，不转换为固定宽度整数或浮点数；尚不提供算术运算。
- ID 的词法与同类声明重复 ID、按类别解析引用、包括 `Option` 内部引用的记录无环性，以及存在、公开、非可选标量主键。

返回 `UnverifiedTypeDeclarations`：**尚未重算内容 ID，也不验收整个 IR**。`nodes` / `contracts` / `outputs` 只检查数组形状，不检查元素、基数、引用或语义；无 input / output 的材料也可能完成声明解码。其后须经过下述声明规范化 / 身份核对，并继续完成表达式 / 节点类型与效果、转换 DAG / 可达性、契约与输出接口检查。所有解码数组暂保留原序；enum 成员和主键顺序始终有语义，不能排序或去重。没有第二种声明文件格式或独立成功码。

`normalization::normalize_type_declarations(bytes, limits)` 复用声明解码，继续规范记录字段的 Unicode scalar 顺序，为每项 definition 生成 JCS 字节，按 IR v0.1 的对应类型域、NUL、definition 重算 SHA-256，并核对输入 ID。错误 ID 会返回 `ContentIdMismatch`，带原数组位置、输入 ID 和重算 ID；不会替换错误 ID、重写引用或静默去重。枚举成员和主键保留有语义的顺序，三类声明最终各自按 ID 排列。

成功返回只读的 `NormalizedTypeDeclarations`，分别保留规范类型化定义、规范 definition 字节与已核对的 ID。它只覆盖类型声明，不包含规范完整文档、文档摘要、节点 / 契约身份或完整 P1 成功信号；未检查范围与声明解码相同。这里没有 strict canonical 完整文档模式；可安全重排的数组、空白及转义差异仍可接受。

`expressions::RowTypeChecker` 只从 `NormalizedTypeDeclarations` 构造，`infer(expression_bytes, limits, scope)` 推导一个既有逐行表达式的 `ValueType`。`RowScope` 为无绑定、单行或双行；记录 ID 须解析到已核验声明，双行初始顺序为 `[left_row, right_row]`，`match_option.some` 在索引 0 插入内部值。此内部 API 不定义新文件格式，也不接受调用方缓存的推导类型或标签。

支持字面 bool / int / fixed / text / enum、`none` / `some`、`bound` / `field`、布尔组合、受限相等与数值比较、加减、`if` 和 `match_option`。检查闭合成员、数学字面值范围、绑定边界、声明引用、操作数 / 分支类型和 fixed scale；两个分支、全部布尔操作数均须检查，不按常量结果跳过。`Int` 加减要求两操作数类型相同，`Fixed` 加减要求操作数与结果 scale 相同，允许显式声明独立结果范围。**即使 `1 + 1` 的结果类型写为 `Int[0,0]`，本层也只推导该类型；不能代替后续范围义务。**

失败区分 JSON / 结构错误、明确的类型错误、调用上下文缺少记录，以及 `Unsupported`。本轮支持边界如下，未修改冻结规范或添加猜测格式：

- `forall_rows` / `exists_rows` / `lookup` / `count_where` / `sum_where` 是契约专用操作，逐行上下文明确拒绝。
- `record.fields` 的元素机器结构、`is_some` 的机器形式仍需精确规范确认，返回 `UnspecifiedForm`。
- 记录及可选记录的相等不在本组件支持范围内；不同范围的 `Int` 数值比较暂返回 `MixedIntComparison`，保留类型兼容性审阅，不将未支持直接标为非法 IR。相等仍要求完全相同类型；同 scale 的 fixed 数值比较已支持。

类型成功不代表总性、算术范围、敏感性 / 控制依赖或非干扰成立。`infer` 不求值、不做表达式规范化 / 摘要、不验证节点图、键保持、容量关系或契约接口。

`RowTypeChecker::normalize(expression_bytes, limits, scope)` 先复用上述类型检查，保留对原始所有分支 / 操作数的拒绝，再对已支持表达式执行 IR 明确要求的规范化：递归展平同类 and / or，按子表达式 JCS 字节排序 / 去重，单项折叠；排序 eq 两侧以及二元 int_add / fixed_add 的操作数。加法不去重或重结合，比较 / 减法 / 分支 / 绑定顺序保持不变，不做常量求值、不扩大结果范围。成功返回只读 `NormalizedRowExpression` 的类型与规范字节；没有独立表达式摘要，也不处理契约表达式。支持集合与 `infer` 相同，规范化不能抹去非法或未支持的子式。

`RowTypeChecker::analyze_labels(expression_bytes, limits, scope)` 先完成相同的类型 / 支持范围检查，再返回只读 `RowLabelAnalysis` 的类型与保守标签。字面值与 none 不读取字段；字段访问累计父值的选择依赖和字段声明标签；布尔、算术、比较、分支和 Option 操作合并全部已读依赖。`match_option.some` 的绑定移位与类型检查一致，不能因条件恒定、两分支相同或 `x - x` 而删去依赖。直接读取行的公开字段不包含敏感兄弟字段；整体记录值、条件产生的复合值会使用内容摘要，允许比最小语义依赖更保守。

`nodes::analyze_node_graph(bytes, limits)` 从完整 candidate bytes 复用同一次有界 JSON 解析、声明规范化 / 身份核对和 `RowTypeChecker`，检查：

- input / filter / map / lookup_join / group 的闭合节点结构、节点 ID 词法与唯一性、已核验表类型、全部前驱引用，以及 input port 和 output 名称唯一性。至少一个输入与命名输出；输出只能引用节点。
- filter 谓词为 Bool，输出记录与主键不变、容量不增；map / lookup_join 投影恰好覆盖输出字段，逐项推导类型与输出声明完全一致。map 单行环境为 `[source_row]`，join 为 `[left_row, right_row]`，容量等于源表 / 左表容量。
- map / join 主键投影支持直接读取源行 / 左行键字段的保留与一一重命名，拒绝非键、右行键和重复 / 遗漏源键。复杂键表达式返回 `UnsupportedKeyExpression`，不推测其逐值保持性；这一支持范围仍须在完整 P1 前收口。
- join pairs 非空、闭合、无重复，字段存在且类型完全相同；不要求连接字段是右主键，不宣称恰好一次匹配。
- group keys 按输出主键顺序解析，源字段必须公开、非可选、可作为键，且与输出字段同类型。键与 aggregate 名称不冲突、共同恰好覆盖输出记录；count 遵循现行语义的 `Int[0, N]` 声明类型，sum 只接受非可选 Int 或同 scale Fixed，允许独立结果范围。容量不得大于源表，实际计数、求和与输出容量能否满足仍留给后续义务。
- 迭代检查 DAG 与可达性：拒绝循环及不能到达命名输出的非 input 死节点，允许未使用的 input、共享前驱与多个命名输出引用同一节点。环错误定位真实成环边，不把环的下游误报为环边。

成功返回只读 `NodeGraphAnalysis`，包含已核验声明、原输入顺序的节点分析摘要、输出引用及拓扑索引。索引始终指向原 `nodes` 数组，join 前驱顺序保留 `[left, right]`；它不返回 canonical 节点 definition。**该分析入口不重算节点内容 ID，契约仍只检查数组形状**；表达式规范化 / 节点身份另由下述入口处理，保守标签摘要见下文；完整效果、契约及文档身份仍未验收，不能据此开放完整 IR 成功入口。

`nodes::normalize_node_graph(bytes, limits)` 在同一次解析中先完成全部节点图分析，然后按拓扑顺序规范逐行表达式、map / join 的 fields、join 的 pairs 和 group 的 aggregates；group keys 保留有语义的顺序。按 `axiom-ir-v0.1:node`、NUL、definition JCS 字节重算各节点 ID，错误返回 `NodeError::ContentIdMismatch`，携带原数组位置、输入 ID 与重算 ID；不改写错误 ID 或下游引用，不静默共享重复节点或删除死节点。结构非法 / 类型错误 / 未支持仍在规范化前按原位置报告。

成功返回 `NormalizedNodeGraph`，`nodes()` 按 ID 排列并只读提供已核对 ID 和规范 definition 字节；`analysis()` 保留原输入顺序的图分析，索引不指向前者的规范数组。此入口完成现有表达式支持范围内的节点内容身份，**不返回完整规范文档 / 文档摘要，不验收契约、非干扰或完整效果**。复杂键投影仍受原分析入口的支持限制；表达式支持边界及完整 P1 仍待收口。

两个节点入口都在全部结构 / 类型检查后按拓扑顺序重建 `NodeGraphAnalysis::node_flows()`，结果与原 `nodes` 数组一一对应：

- `row_control()` 表示决定行存在性 / 成员集合的保守标签。input 行存在性按首版模型为 public；filter 合并谓词标签，map 保留前驱控制标签，join 合并两侧控制及 pairs 字段标签，group 继承源控制并计入分组键依赖。
- `field_labels()` 按 Unicode scalar 字段序给出声明与推导标签的上确界。map 从表达式重算，join 额外计入匹配依赖；group 的 count 包含成员控制，sum 还包含源字段标签。声明为 public 不能抹去上游推导的 sensitive，声明为 sensitive 也不会因表达式是常量而被降密。filter 只改变控制摘要，保留字段值摘要。
- `label_gaps()` 给出输出声明低于推导标签的字段及原输入 JSON Pointer。它是后续义务的分析提示，不是正式义务、反例或 `failed`；不会据此把 AX-B04 wrong 候选改判为结构非法。filter 导致的敏感行存在性可以没有字段标签缺口，调用方必须同时查看控制摘要。

复合字段跨节点取整体内容摘要，join 匹配控制保守影响全部投影字段；因此可能产生待后续验证消解的额外依赖。标签为 public 或缺口为空均不能证明非干扰：契约选择的输入 / 输出、前置条件、故障与正常结束的可观察性、总性和范围义务尚未接入。本层不执行外部能力、不生成证明，也不扩大现有表达式支持范围或新增公共 IR 字段。

`contracts::analyze_contracts(bytes, limits)` 使用同一次有界解析，先完成上述节点结构 / 类型 / 标签分析，再检查全部契约。它不调用节点内容身份入口，节点与契约 ID 仍只核验词法和唯一性；结果不能作为完整 IR 验收凭证。

- formula 只接受 assume / guarantee，顶层公式必须为 Bool、初始绑定为空。assume 只可引用 input，guarantee 可引用 input 与命名 output；不存在内部节点引用语法。接口从已检查图构造，不能由调用方提供缓存或额外隐式表。
- `forall_rows` / `exists_rows` 为 body 插入目标行，body 必须为 Bool。`lookup` 不插入行，按目标主键顺序和完全相同类型检查全部 keys，返回目标 `Option<Record>`；可继续由 `match_option` 显式处理。查找是否存在不由类型层判定。
- `count_where` / `sum_where` 在 predicate 与 value 中插入目标行，predicate 必须为 Bool。count 结果须为 Int；sum 的 value 须为非可选 Int / Fixed，结果分别为 Int / 同 scale Fixed。声明范围独立保留，不因容量或空集合扩大范围；计数与数学和（包括零）能否落入声明范围仍是后续义务。
- 所有标量类型规则与逐行入口共用，嵌套量词 / Option 绑定统一移位并在分支结束后恢复。即使表容量为零、条件恒定或某个布尔操作数已决定结果，也不跳过子式检查。逐行入口继续拒绝这五种契约表操作。
- noninterference 的 inputs / outputs 必须分别非空、唯一并解析到对应接口。这里只检查策略结构；它不是普通 Bool 公式，不按字段白名单或节点标签判定其成立。
- 契约 definition、接口引用和表操作均为闭合结构。拒绝重复契约 ID、未知 kind / role / 成员、非空顶层 effects，以及文件、网络、随机或环境等未知操作。支持范围内的图和契约仅包含已定义的纯核心操作；未支持形式继续返回 Unsupported，不能据此外推为完整效果或 P1 验收。

成功返回只读 `ContractAnalysis`，保留 `graph()` 与原 contracts 顺序的 `contracts()`；每项给出 supplied ID、契约种类及按接口类别 / 名称排序、去除重复读取的 `interfaces()`。接口中的 node 索引指向原 nodes 数组。名称按 Unicode scalar 精确比较，不合并 NFC / NFD 或相同拼写的 input / output；接口数组的分析排序不构成契约 definition 规范化。

`ContractError` 分开保存 JSON / 声明、节点、表达式、契约结构和契约内容 ID 错误，保留原字节位置或 JSON Pointer。空契约数组与恒为 false 的 Bool 公式可以结构合法；分析不判断契约可满足性、公式真值或非干扰，不求值、不生成义务、不输出 canonical 契约 / 文档，也不核验契约内容 ID。

`contracts::normalize_contracts(bytes, limits)` 在同一次有界解析中先完成全部原始节点与契约分析，再复用节点规范化 / 身份路径，并规范契约 definition、按 `axiom-ir-v0.1:contract` 域、NUL 和 JCS 字节重算 ID。formula 递归复用现有布尔 / 相等 / 加法规范重写；量词、查找键顺序、绑定索引、分支位置、结果类型与角色均保留。noninterference 的 inputs / outputs 分别按 Unicode scalar 名称序排列。原始坏成员、越界 / 不可见子式与 Unsupported 必须先拒绝，不能被布尔去重隐藏；重复契约 ID / 接口名也不会静默去重。

成功返回只读 `NormalizedContracts`：`analysis()` 保留原节点 / 契约数组索引，`nodes()` 与 `contracts()` 各按已核对的 ID 排序、包含规范 definition 字节，声明身份可从分析图读取。内容 ID 不匹配报告原 `/contracts/<index>/id`、输入 ID 与重算 ID，不改 ID、不重写引用、不合并仅逻辑等价的公式。节点身份错误同样拒绝，空契约数组也不绕过节点身份核对。该局部入口不生成完整 canonical IR、strict canonical 检查或文档摘要；文档组合由下一入口完成，现有表达式未支持边界继续适用。

`document::normalize_document(bytes, limits)` 在同一次有界解析中执行全部现有组件检查与身份核对，然后直接组合已核对的类型、节点和契约 definition 字节。五类内容数组各按 ID 排序，outputs 按 Unicode scalar 名称排序；对象 / 字符串复用同一个 JCS 编码器。没有第二套 definition 序列化规则，也不重新解析组件字节。成功返回只读 `CanonicalDocument`，包含 `canonical_bytes()`、`document_id()` 与 `components()`；分析索引仍指向原始输入，不随规范数组重排。原输入表示不同可以得到同样规范字节，但原位置分析不必相等。

文档 ID 对 `axiom-ir-v0.1:document`、NUL 与完整规范字节计算，区别于文件原始 SHA-256，不内嵌到 IR 自身。规范机器字节无 BOM、额外空白或末尾换行。`document::check_canonical_document(bytes, limits)` 完成相同检查后严格比较原输入；有表示差异时返回 `DocumentError::NonCanonical { offset }`，定位首个不同 UTF-8 字节或共同前缀结束处。JSON、结构、身份、Unsupported 和资源错误保留为 `DocumentError::Ir` 内的原组件诊断，优先于格式差异；严格模式不会把修复后的字节作为成功结果返回。

两个文档入口只处理已有支持范围，所有未支持项继续明确拒绝，不产生文档成功结果。恒 false 契约、wrong 候选或范围未证明仍可能结构合法；规范字节与摘要不证明公式、非干扰、任务意图或安全执行。尚未接受的机器形式 / 类型兼容性与未支持的记录相等 / 复杂键投影须在完整 P1 验收前收口；没有凭这些函数绕过后续义务生成、证明或 target gate 的入口。

## 资源与诊断

调用方必须显式提供 `JsonLimits`，没有无限预算的默认入口：

- `max_input_bytes` 在 UTF-8 解码前检查，约束输入、解码字符串总量和规范输出字节量；本子集输出不长于合法输入。
- `max_values` 计数所有值及对象成员名，限制树分配与宽对象排序规模。
- `max_nesting` 限制同时打开的数组 / 对象层数，实际不超过实现上限 128；标量不消耗层数。解析、编码和树销毁均受此上限约束。

错误包含类别及原输入的零基字节位置。非法输入与 `ResourceLimit` 分开；先遇到预算限制时只报告未完成处理，不推断输入是否合法。对象重复键指向第二次出现的成员名。此内部诊断尚未映射为 pipeline stage result。

声明层复用同一有界 JSON parser；JSON 错误及资源错误原样保留，领域错误给出类别和指向原输入的 JSON Pointer。类型引用图使用迭代队列检测循环，不沿声明引用递归；多表共享记录时复用字段索引，避免反复扫描宽记录。名称、整数和类型不读取环境或外部工具。

这些是组件规模限制，不是 OS 硬内存 / 时限隔离，也不保证宿主分配失败可恢复。UTF-8 检查、字符串处理和编码按输入规模进行；对象排序按成员数量及键长度消耗资源。

规范化继续使用同一输入预算，逐项编码 definition 和域分离摘要，不递归展开引用。结果保留类型化定义和规范字节，内存会高于仅解码；总量受原输入规模约束，但不把 `max_input_bytes` 解释为硬内存配额。

表达式复用有界 JSON 解析，按运算职责拆分递归局部状态，并以 128 层 JSON 对象（127 层 Option）、最深算术 / 布尔 / 分支路径回归栈边界；未提高测试线程栈。绑定整数先校验规范词法，超过机器索引范围时必然也超过有限绑定环境，报告绑定越界。声明查询使用有序 ID / 字段索引，枚举成员集合索引在 checker 构造时生成一次。输入预算不包含已装入的声明和索引所占内存；仍不提供 OS 硬配额或可恢复分配失败保证。

节点入口对整个 candidate 使用一份输入 / 值数 / 嵌套预算，嵌入表达式不重新编码或独立放宽深度预算。`NodeError` 保留 JSON 原字节位置、声明错误、表达式错误 / 未支持原因及原数组位置的 JSON Pointer。节点引用使用有序索引，拓扑与反向可达性遍历使用迭代队列 / 栈，每个节点至多两个前驱；图深度不消耗 Rust 调用栈。解析树、声明、图与辅助索引会同时占用内存，输入预算仍不是 OS 硬内存保证。

表达式规范化沿已受 128 层 JSON 上限约束的树递归，不沿节点引用递归；排序使用规范字节作比较键，布尔展平移动子项。规范化不增加表达式的规范字节量，但排序临时字节、规范 definition 与输入树会共同占用内存；预算耗尽必须在去重 / 折叠前报告，不能靠结果较小绕过原输入限制。

标签分析复用原始有界表达式树，先完整检查再推导，不在规范化后跳过原分支。记录内容标签通过反向引用队列迭代汇总，不递归展开类型 DAG；Option 形状递归仍受声明 / 表达式 JSON 深度约束。input 共享同一记录声明的不可变字段摘要，filter 与源节点共享字段摘要，只独立保存控制标签；map / join / group 的字段数由显式定义约束。摘要、绑定栈和原树的内存仍在解析预算之外累计，不提供硬资源隔离。

契约入口不重新解析嵌入公式或放宽其 JSON 预算；接口索引只从同一次分析的图构造一次，量词和 Option 共用有界绑定栈，引用集合按公式实际读取去重。没有按容量遍历表或展开全称公式，超机器范围的数学容量仍作为规范文本保留。新增回归覆盖 122 层量词、120 层 sum 和 40 层 lookup / match 嵌套，以及原始字节 / 值数 / 深度预算拒绝。

契约规范化在同一已检查树上进行，不再次解析图或向表达式分配独立预算；沿用节点 / 表达式规范器，额外保存契约 definition 字节与身份。61 层嵌套布尔组合及 10,000 个重复操作数的契约回归确认先约束原始深宽，再执行去重；规范结果较小不绕过资源拒绝。

文档组合沿用整份输入预算，输出只由已规范 definition 与已检查的其余成员组成，规范字节量不增长；完整输出、文档摘要输入和组件分析会同时占用内存，仍不是硬内存配额。strict 比较按字节扫描，不把 Unicode 字符位置当作字节偏移。122 层量词和 10,000 个重复契约操作数经完整入口回归，较小预算仍先拒绝原始深宽。

## 实现与验收边界

Rust 2024，`publish = false`，仅自有代码与标准库、禁止 unsafe，无第三方依赖、build script、过程宏或 native / FFI。唯一直接依赖为本地 `radishaxiom-digest 0.0.0`，其 [SHA-256 实现](../digest/README.md)由既有 runtime 提取，共享算法而不依赖 runtime 的产品能力。与 runtime 的 ASCII 闭合文档 parser 分开；不改变旧 runtime 协议，不让独立 Go checker 复用生产实现。

测试期望来自人工推导的规范向量、Unicode 标量与转义的数学对应关系，以及仓库既有的四题 12 个 candidate；不调用生产 helper 生成期望。`correct` / `wrong` 候选同样参与 JSON / 声明层回归，不据标签判定算法。负例覆盖语法、无效 UTF-8、代理对、解码重名、截断、规模、版本、声明闭合结构、数值范围、引用和键约束。数学整数比较还与小范围机器整数逐对对照，并使用人工排列的大整数检验精度边界；5,000 层合成记录引用分别验证无环和成环路径。声明测试中的合成 ID 仅满足词法，明确不当作真实内容摘要。

规范化测试另外使用 [Python 独立身份向量](tests/fixtures/type-identities/README.md)，逐字节比较 definition 和 ID；改变对象 / 声明 / 字段排序与转义仍得到同一结果，改变有语义的顺序或内容则拒绝旧 ID。遗漏域名、遗漏 NUL、错误域名、末尾换行与把 ID 包进摘要均有独立负例；仓库检查会重算生成一致性。SHA-256 的通用已知向量在共享包保留，不能把共享生产摘要实现当作独立 checker。

表达式测试包含人工构造的类型期望、深度 / 字面值 / 分支 / 绑定 / 未支持负例，以及四题 12 个候选中的全部 31 个逐行表达式；其期望来自既有输出字段声明和 filter 的 Bool 要求。用于提取表达式与上下文的 fixture 代码仅在测试中存在，不是生产节点解析器，不能把 31 个表达式通过外推为节点图通过。错误算法候选的表达式同样可以类型正确。

节点测试通过真实 `analyze_node_graph` 入口回归四题 12 个候选的 pretty / JCS 输入，不读取 expected outcome。新增同域合成输入的名称、类型、错误类别和定位期望由规范人工推导，覆盖改名、乱序、投影错配、引用 / 环 / 死节点、连接、分组、容量、预算和未支持传播；5,000 层链验证无环 / 成环行为，448 个小图组合以独立布尔传递闭包核对生产图算法。测试 builder 的摘要 helper 仅为合成输入构造类型 ID，不产生测试期望；声明身份正确性仍由独立 Python 向量验收。合成节点 ID 仅满足词法，明确不作为内容身份或完整 P1 通过证据。

[表达式 / 节点独立向量](tests/fixtures/node-identities/README.md) 逐例指定规范表达式结构，并以 Python `json` / `hashlib` 生成节点 definition 与身份期望，纳入仓库生成一致性检查。测试覆盖五类节点、JCS 字节顺序与 Unicode scalar 数组顺序、布尔规范化及幂等性、错误摘要域 / NUL / 换行 / wrapper、原位置诊断、深宽边界与不允许的重写；四题 12 个候选另通过真实节点规范化核对现有 ID，不以类型通过或重新生成 fixture 替代身份核对。

标签切片新增 11 项人工期望回归，覆盖所有已支持运算类别、常量 / 相同分支仍保留读取依赖、Option 绑定移位、嵌套记录、声明不足的跨节点传播、两侧 join 匹配控制、filter → map → group 的 count / sum、分组键的上游依赖，以及 5,000 层记录引用。最深表达式回归也执行标签分析；现有四题 12 个候选继续经过节点入口，AX-B04 三个候选另外核对控制摘要、priority 字段和原位置缺口。这里只验收保守分析，没有运行非干扰求解或独立 checker。

契约切片新增 17 项人工期望回归：四题 12 个候选的 21 条契约均经实际入口检查，pretty / JCS 得到相同分析；同域材料覆盖接口可见性、Unicode 名称与原数组索引、复合主键顺序、嵌套绑定及其恢复、聚合类型 / scale、零容量表和不含零的结果范围、闭合成员、外部操作拒绝、未支持与资源错误。字段、类型和错误路径期望不由生产推导器生成；这些测试不代表公式成立、非干扰证明或契约身份验收。

契约身份切片另增 9 项回归：[11 项独立契约向量](tests/fixtures/contract-identities/README.md) 逐字节核对 definition 与 ID，覆盖五类表操作中的规范化、绑定 / 键 / 角色保留、Unicode 名称、幂等性和摘要域负例。四题 12 个候选的 21 条契约通过真实身份入口，并确认同题候选的实现变化不改变接口契约 ID。坏子式、重复成员 / ID / 接口、节点身份错误与资源失败仍定位到原输入。身份正确与恒 false 公式、未证明范围或错误算法并不矛盾，这些测试不生成证明或完整 IR 凭证。

文档切片另增 10 项回归：[六个独立完整文档向量](tests/fixtures/document-identities/README.md) 核对类型 / 节点 / 契约组合、顶层排序、规范字节及文档身份。四题 12 个候选逐字节匹配已有 `.ir.jcs`，摘要匹配既有 `task.json` 的文档域摘要，pretty 输入通过规范化而被 strict 拒绝。覆盖仅 JSON 规范化仍不满足 IR 规范、转义 / 空白 / 换行、首个字节差异、输出名称 / 主键顺序变化、禁止内嵌文档摘要、原数组分析位置、结构 / 身份 / 未支持错误，以及原始字节 / 深宽预算。不同范围 Int 的 eq 类型错误与有序比较 Unsupported 分别断言，不扩大现有支持范围。

已安装并验收的宿主工具可按仓库约定离线执行：

```bash
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir --locked --offline
```

完整 workspace 验证见[当前状态](../../docs/status/current.md#验证入口与本次审阅)。测试不是形式证明；未运行平台不能据此声称字节一致性已验收。
