# 纯核心空效果推导 v0.1

状态：Accepted，依据 [ADR 0023](../adr/0023-core-empty-effect-derivation.md)。用途：定义内部空效果推导记录、规则、顺序、预算及验收；不是 Evidence、证明证书或 solver query。

## 输入、结果与信任

只接受 P1 IR v0.2 CanonicalDocument、不可变完整 ir-derived P2 集合中原 effect-empty / prove / program 目标与显式生成器源码摘要。版本、IR raw / document digest、集合或目标不符须拒绝，旧 IR 不隐式迁移。P1 负责完整类型、绑定、闭合结构与内容身份；本组件再按明确构造检查效果推导所需形状、作用域及前提，不求值也不假设其他义务成立。

结果的 format 为 `axiom-core-effect-derivation`，format_version 为 `0.1`，rule_profile 为 `axiom-core-empty-effects-v0.1`。顶层恰含 binding、format、format_version、root、rule_profile、steps。binding 恰含 generator、ir_artifact、ir_document_digest、ir_version、obligation、obligation_set_artifact、semantics；摘要均带 `sha256:`，ir_version 为 `0.2`，semantics 为 IR v0.2 语义快照摘要，generator 为调用方源码摘要，不能解释为构建 attestation。

每个 step 恰含 anchor、path、premises、rule。anchor 恰含 id、kind，kind 为 node / output / contract / document，id 分别是节点 ID、输出名称、契约 ID、完整文档 ID。path 是从规范 definition 根出发的字符串数组；output 从对应输出条目出发，document 从 IR 根出发。premises 是先前步骤的零基规范十进制字符串，允许同一前提因不同角色重复出现；root 为最终 program 步骤索引。step 不另造内容 ID，所有路径与索引通过整份记录摘要绑定。

规范字节使用现有 IR JSON 子集：UTF-8 / JCS 对象键排序、无 BOM / 多余空白 / 末尾换行、无 number / null；数组顺序按下文固定。制品摘要是完整原始字节 SHA-256，不增加摘要域。无 result、status、execution、trusted 输入标记或可打开执行门控的字段。

## 闭合规则与顺序

规则 ID 为下表精确值，`expr.<op>` 的后缀只能是表中枚举的 op。规则步骤在全部前提之后生成。每个语法出现位置各生成一步，不能因重复表达式、零容量、Pre false 或分支不可达省略。

| 规则 | 按顺序的前提与要求 |
| --- | --- |
| expr.literal_bool / literal_int / literal_fixed / literal_text / literal_enum / none | 无前提；精确字面或类型元数据由 P1 核验，不执行能力 |
| expr.bound | 无前提；index 必须小于当前绑定数 |
| expr.field | record 表达式；字段解析与类型依赖 P1 输入前提 |
| expr.some / not | value 表达式 |
| expr.and / or / int_add / fixed_add | values 的全部元素，规范数组次序 |
| expr.eq / lt / le / gt / ge / int_sub / fixed_sub | left、right |
| expr.if | condition、then、else，全部纳入静态效果 |
| expr.match_option | subject、none、some；仅 some 增加一个绑定 |
| expr.record | fields 数组中每个 expression；字段之间不引入绑定 |
| expr.forall_rows / exists_rows | table 的 interface 规则、body；body 增加行绑定 |
| expr.lookup | table 的 interface 规则、keys 依次；keys 不增加绑定 |
| expr.count_where | table 的 interface 规则、predicate；predicate 增加行绑定 |
| expr.sum_where | table 的 interface 规则、predicate、value；后二者各增加行绑定 |
| interface.input / output | 精确命名 input 节点 / output 步骤；仅契约可用，assume 只准 input |
| node.input | 无前提；已物化显式输入，不是 IO |
| node.filter | source 节点、predicate（初始一个绑定） |
| node.map | source 节点、各 fields.expression（初始一个绑定） |
| node.lookup_join | left、right 节点、各 join.pair、各 fields.expression（初始两个绑定，沿 IR 的索引语义） |
| join.pair | 无前提；pairs 元素闭合且字段引用由 P1 核验 |
| node.group | source 节点、各 group.key、各 group.count / group.sum |
| group.key / group.count / group.sum | 无前提；精确源字段 / 名称形状及类型依赖 P1，无隐式读取 |
| output.bind | 对应 node 步骤 |
| contract.assume / guarantee | expression（初始无绑定） |
| contract.noninterference | inputs 对应节点依数组序、outputs 对应 output 步骤依数组序；不证明双世界关系 |
| effects.empty | 无前提；IR effects 恰为空数组 |
| program.empty | effects.empty、全部 node 按 ID 序、全部 output 按名称序、全部 contract 按 ID 序 |

节点按依赖深度、再按节点 ID 排序，input 深度为零，其他为最大前驱深度加一；前驱同节点仍保留不同角色前提。节点内部按上表作表达式后序遍历。全部节点之后生成 output.bind（规范名称序），再生成契约（规范 ID 序），最后 effects.empty 与 program.empty。接口查找使用显式输入 / 输出名称，不解析为宿主路径或外部资源。

每种构造均检查本层精确成员集合；record.fields、join.pairs、group.keys / aggregates、table 引用同样闭合。未知规则、成员、tag、非空效果或不合法作用域拒绝；完整类型元数据不重复实现另一套类型检查器。不从任意 JSON 子对象是否带 op 推断遍历范围。

## 资源、strict 与验收

调用方显式提供 IR JSON 预算与 Steps、PremiseEdges、PathBytes、OutputBytes 四项累计上限。Steps 每次入表收费；PremiseEdges 在临时前提数组添加之前收费，包含重复角色边及最终 program 全集边；PathBytes 为每个 step.path 规范 JSON 数组长度之和，在复制路径前收费；OutputBytes 为完整规范记录字节数，先计数再分配最终输出。等号可接受，checked arithmetic 溢出即资源拒绝，不产生部分成功。

解析、节点 / 接口索引与最多 JSON 128 层的表达式工作栈受 IR JSON 大小约束；图深度用迭代拓扑处理，不递归展开前驱。步骤保存引用或预算约束的路径 / 边，类型与输入字段不展开。预算不等于 OS hard memory，也不保证 OOM 可恢复。

strict 先限制候选字节，再从相同可信输入完整重建并逐字节比较；任何未知版本、错误绑定、遗漏 / 重复 / 额外步骤、错误引用 / 路径 / 规则、顺序或空白改变均拒绝。无需先修复候选 JSON；生产重建不是独立证明。

独立 Python 路径读取规范 IR / P2 原字节及其身份，按本表重建期望记录，核对 Rust 完整字节和摘要，并对推导步骤及绑定作变异拒绝。其 P1 类型正确性前提必须保留；效果负例不能仅以生产拒绝标志作为独立期望。材料覆盖现有 26 份 IR、补充构造、非空 / 未知能力、遗漏子树、错误前提、共享深图、大容量与预算边界。动态材料检查、生产 strict、完整 P1 与正式独立 checker 分别报告。
