# Axiom IR 内部组件

本 crate 承载 [ADR 0016](../../docs/adr/0016-core-semantic-slice-entry.md) 的 P1 实施。当前实现 [IR v0.1](../../docs/ir/axiom-ir-v0.md) 的 JSON 字节边界、类型声明解码 / 身份核对、受限逐行表达式类型检查及节点图分析；没有完整 IR 成功入口，也不提供 CLI。

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

类型成功不代表总性、算术范围、敏感性 / 控制依赖或非干扰成立。本层不求值、不做表达式规范化 / 摘要、不验证节点图、键保持、容量关系或契约接口；完整 P1 仍须收口上述支持边界及后续节点、契约与文档身份。

`nodes::analyze_node_graph(bytes, limits)` 从完整 candidate bytes 复用同一次有界 JSON 解析、声明规范化 / 身份核对和 `RowTypeChecker`，检查：

- input / filter / map / lookup_join / group 的闭合节点结构、节点 ID 词法与唯一性、已核验表类型、全部前驱引用，以及 input port 和 output 名称唯一性。至少一个输入与命名输出；输出只能引用节点。
- filter 谓词为 Bool，输出记录与主键不变、容量不增；map / lookup_join 投影恰好覆盖输出字段，逐项推导类型与输出声明完全一致。map 单行环境为 `[source_row]`，join 为 `[left_row, right_row]`，容量等于源表 / 左表容量。
- map / join 主键投影支持直接读取源行 / 左行键字段的保留与一一重命名，拒绝非键、右行键和重复 / 遗漏源键。复杂键表达式返回 `UnsupportedKeyExpression`，不推测其逐值保持性；这一支持范围仍须在完整 P1 前收口。
- join pairs 非空、闭合、无重复，字段存在且类型完全相同；不要求连接字段是右主键，不宣称恰好一次匹配。
- group keys 按输出主键顺序解析，源字段必须公开、非可选、可作为键，且与输出字段同类型。键与 aggregate 名称不冲突、共同恰好覆盖输出记录；count 遵循现行语义的 `Int[0, N]` 声明类型，sum 只接受非可选 Int 或同 scale Fixed，允许独立结果范围。容量不得大于源表，实际计数、求和与输出容量能否满足仍留给后续义务。
- 迭代检查 DAG 与可达性：拒绝循环及不能到达命名输出的非 input 死节点，允许未使用的 input、共享前驱与多个命名输出引用同一节点。环错误定位真实成环边，不把环的下游误报为环边。

成功返回只读 `NodeGraphAnalysis`，包含已核验声明、原输入顺序的节点分析摘要、输出引用及拓扑索引。索引始终指向原 `nodes` 数组，join 前驱顺序保留 `[left, right]`；它不返回 canonical 节点 definition。**节点 ID 尚未按内容重算，契约仍只检查数组形状**；重复 definition 的规范化 / 身份核对、表达式规范化、标签 / 控制依赖、完整效果和契约接口及文档身份均未验收，不能据此开放完整 IR 成功入口。

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

## 实现与验收边界

Rust 2024，`publish = false`，仅自有代码与标准库、禁止 unsafe，无第三方依赖、build script、过程宏或 native / FFI。唯一直接依赖为本地 `radishaxiom-digest 0.0.0`，其 [SHA-256 实现](../digest/README.md)由既有 runtime 提取，共享算法而不依赖 runtime 的产品能力。与 runtime 的 ASCII 闭合文档 parser 分开；不改变旧 runtime 协议，不让独立 Go checker 复用生产实现。

测试期望来自人工推导的规范向量、Unicode 标量与转义的数学对应关系，以及仓库既有的四题 12 个 candidate；不调用生产 helper 生成期望。`correct` / `wrong` 候选同样参与 JSON / 声明层回归，不据标签判定算法。负例覆盖语法、无效 UTF-8、代理对、解码重名、截断、规模、版本、声明闭合结构、数值范围、引用和键约束。数学整数比较还与小范围机器整数逐对对照，并使用人工排列的大整数检验精度边界；5,000 层合成记录引用分别验证无环和成环路径。声明测试中的合成 ID 仅满足词法，明确不当作真实内容摘要。

规范化测试另外使用 [Python 独立身份向量](tests/fixtures/type-identities/README.md)，逐字节比较 definition 和 ID；改变对象 / 声明 / 字段排序与转义仍得到同一结果，改变有语义的顺序或内容则拒绝旧 ID。遗漏域名、遗漏 NUL、错误域名、末尾换行与把 ID 包进摘要均有独立负例；仓库检查会重算生成一致性。SHA-256 的通用已知向量在共享包保留，不能把共享生产摘要实现当作独立 checker。

表达式测试包含人工构造的类型期望、深度 / 字面值 / 分支 / 绑定 / 未支持负例，以及四题 12 个候选中的全部 31 个逐行表达式；其期望来自既有输出字段声明和 filter 的 Bool 要求。用于提取表达式与上下文的 fixture 代码仅在测试中存在，不是生产节点解析器，不能把 31 个表达式通过外推为节点图通过。错误算法候选的表达式同样可以类型正确。

节点测试通过真实 `analyze_node_graph` 入口回归四题 12 个候选的 pretty / JCS 输入，不读取 expected outcome。新增同域合成输入的名称、类型、错误类别和定位期望由规范人工推导，覆盖改名、乱序、投影错配、引用 / 环 / 死节点、连接、分组、容量、预算和未支持传播；5,000 层链验证无环 / 成环行为，448 个小图组合以独立布尔传递闭包核对生产图算法。测试 builder 的摘要 helper 仅为合成输入构造类型 ID，不产生测试期望；声明身份正确性仍由独立 Python 向量验收。合成节点 ID 仅满足词法，明确不作为内容身份或完整 P1 通过证据。

已安装并验收的宿主工具可按仓库约定离线执行：

```bash
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir --locked --offline
```

完整 workspace 验证见[当前状态](../../docs/status/current.md#验证入口与本次审阅)。测试不是形式证明；未运行平台不能据此声称字节一致性已验收。
