# 字段来源推导 v0.1

状态：Accepted，依据 [ADR 0024](../adr/0024-core-field-origin-derivation.md)。供内部实现和独立有限核验使用，不定义公共证明支持、动态故障判断或非干扰证明。

## 输入与版本

`OriginProfile::CoreFieldOriginV0_1` 对应 `axiom-core-field-origin-v0.1`；记录 format 为 `axiom-core-field-origin-derivation`，format_version 为 `0.1`。输入为完整规范 IR v0.2、不可变匹配的 ir-derived P2、field-origin 目标 ID、已有 GeneratorIdentity 和显式预算。拒绝旧 IR、错误绑定、未知目标、其他 kind，不隐式迁移或改变 P2 全集。

GeneratorIdentity 只复用显式摘要值的词法校验，不认证调用方声明的源码或构建身份。

完整 P1 类型、闭合形状、绑定及身份是输入前提。推导独立读取实际 IR，不用 NodeFlowAnalysis 的标签或缺口作为答案。公式契约不属于字段来源闭包；全文档身份仍绑定它们和未引用节点。

## 记录与顺序

记录顶层恰有 binding、format、format_version、gaps、roots、rule_profile、steps、target。binding 恰为 generator、ir_artifact、ir_document_digest、ir_version、obligation、obligation_set_artifact、semantics，意义沿用空效果记录。target 恰为 interface、name、node、record_type。roots 恰为 control、evaluation、value，值为步骤下标字符串。gaps 为所有保留的 gap 步骤下标，递增排列；它可能包含只由 evaluation 或 control 边可达的上游缺口，不能全部解释成目标字段的值来源。

每个 step 恰为 anchor、gap、item、labels、path、premises、rule：

- anchor 为 kind / id；kind 是 record-type、table-type、node 或 output，id 是相应内容 ID 或输出接口名。path 从对应规范 definition 起，output / 合成整节点判断用空路径。item 为关联字段名，否则空串；input 的 port 路径与 item 联合定位输入字段。
- labels 恰为 declared、inferred、propagated、type_summary，均为 public / sensitive。没有声明的辅助判断取 declared=public；evaluation 判断全部标签为 public，不由其前提推断无故障或公开性。
- premises 是有序的 `{role, step}`；role 为 value、selection、evaluation、declaration。step 必须小于当前下标；允许同一步承担不同角色，不隐式合并。
- gap 是 Bool。只有新表达式构造字段或 map / join / group 的派生字段判断比较 declared 与 inferred；input / filter、类型声明与辅助判断不创造 gap。

所有对象使用 JCS、无额外空白或末尾 LF；整数下标为规范十进制字符串，Unicode 不规范化。先按依赖深度再按 ID 构造 record 声明，字段按规范顺序；table 声明按 ID；节点按依赖深度再按 ID。表达式按本规则的子项顺序后序构造。最终追加 output.field，然后从三个根逆向取全部角色边的闭包，按原步骤顺序压紧编号，排除其他步骤。无关节点与声明可在受预算构建中出现，但不得出现在导出闭包。

## 类型、值形状与标签

两级标签取上确界 `join`。类型摘要 TS：标量为 public；Option 取 inner 的 TS；Record 取所有字段 `declared join TS(field type)`。记录类型依赖是共享 DAG，不递归展开 Record。`decl.field` 引用嵌套 Record 声明（如有），`decl.record` 引用全部字段声明，`decl.table` 引用 Record 声明。

表达式内部保留 Scalar、Record 和 Option 形状。Record 保存类型、选择标签和可选逐字段摘要；无逐字段摘要时，其整体摘要仅在 declared 标志为 true 时加入 TS。Option 保存选择标签及内部形状。整体标签为选择标签与内容摘要的 join。类型、声明与形状可从 IR、规则和前提重建，不另加冗余类型树。

`expr.*` 的 propagated 为整体标签。`field.assign` 的 declared 为输出字段声明，inferred 为表达式整体标签（join 还加入匹配标签），type_summary 为 TS，propagated 为三者 join；gap 当且仅当 declared=public 且 inferred=sensitive。`expr.record-field` 的 propagated 仅为 declared join 表达式整体标签，不额外加入 TS，保持现有 P1 记录构造规则；同样保留本地声明缺口作为分析判断，不改变 P1 接受集合。

input 字段 propagated=declared join TS；filter 字段沿用来源 propagated，不新增缺口。根字段为 Record / Option 仍只绑定原顶层义务。不能用“复合类型含 sensitive”本身替代派生表达式的 inferred 来创造缺口。

## 表达式规则

规则名为 `expr.` 加原 op，另有 `expr.record-field` 和 `binding.some`。仅允许 P1 逐行操作，契约表操作不进入本组件表达式规则。

| 操作 | 子项与来源规则 |
| --- | --- |
| literal_bool / literal_int / literal_fixed / literal_text / literal_enum | public，无输入字段来源；literal 的类型和值由绑定 IR 定义 |
| none | 按 type 建立 declared=false 的形状，选择标签 public，不读取内载荷 |
| some | value 为内部形状，外层 Option 选择标签 public |
| bound | 引用精确 de Bruijn 绑定，保留该值形状；来源行记录初始选择标签 public，逐字段摘要来自前驱字段 |
| field | 先 record；精确所选字段为 value 前提，记录选择来源为 selection，record 整体为 evaluation，字段声明为 declaration；结果按字段类型建立 declared=true 形状，选择标签为记录选择标签 join 所选字段摘要 |
| record | fields 规范序逐个 expression，再 expr.record-field；整体为逐字段摘要 join，选择标签 public；全部子项留在求值上下文 |
| if | condition、then、else；合并三者整体标签，按 result_type 建 declared=false 形状；条件为 selection，双方为 value，三者为 evaluation，不折叠相同或死分支 |
| match_option | subject、none、binding.some、some；Some 内部形状加入 Option 外层选择标签后前插绑定；整体合并 subject 与两分支，按 result_type 建 declared=false 形状 |
| not | value |
| and / or / int_add / fixed_add | values 原规范顺序，严格纳入全部操作数 |
| eq / lt / le / gt / ge / int_sub / fixed_sub | left、right |

Scalar 操作合并操作数整体标签。选择与求值前提保留语法潜在依赖，不判断动态 Reach、数学范围或两个分支均被执行。直接投影不把兄弟字段归为值依赖，但严格构造的兄弟仍能经 evaluation 边追溯。P1 的条件整体摘要与嵌套父标签保守传播保持，不宣称最小来源集合。

## 节点与根

每个节点保留字段步骤、control、evaluation 与 record。`node.record` 用 value 引用全部字段，用 evaluation 引用节点上下文，便于读取整个源记录；其选择标签为 public，行控制独立传递。

| 节点 | 规则与顺序 |
| --- | --- |
| input | input.field 按声明字段序，引用字段 / 表声明；input.control=public；input.evaluation 引用表声明；node.record |
| filter | predicate；filter.control 合并 source.control 与谓词整体标签；filter.field 逐字段透传；filter.evaluation 引用来源上下文和谓词；node.record |
| map | map.control 透传 source.control；fields 逐个表达式与 field.assign；map.evaluation 引用来源上下文和全部字段判断（进而包含表达式）；node.record |
| lookup_join | join.pair 逐对合并左右字段；join.match 合并两侧 control 与全部 pairs；join.control 引用 match；fields 按左右作用域逐个表达式与 field.assign，inferred 加 match；join.evaluation 引用两侧上下文、match 及全部字段判断；node.record |
| group | group.control 合并来源 control 与所有组键来源；keys 依序 field.assign（inferred=源字段），aggregates 依序 field.assign（count inferred=control，sum 再 join 源字段）；group.evaluation 引用来源上下文与全部键 / 聚合字段；node.record |

map / join / group 字段均保留类型声明和确切 IR 路径；控制用 selection 边，普通字段来源用 value 边。group count 无输入值字段并非来源缺失，其来源是参与集合。join 匹配合法性、group 覆盖 / 守恒仍由其他目标验证。

`output.field` 位于 output anchor，以 item 指定目标字段，用 value 引用其节点字段，用 declaration 引用字段声明。roots.value 指向该步骤；其余两根指向实际节点的 control / evaluation。别名不合并目标。

## 预算、拒绝与证据层级

OriginLimits 显式包含 IR JSON、Steps、PremiseEdges、Descriptors、PathBytes、OutputBytes；上限含等号，checked 累加溢出等于资源拒绝。Steps / PremiseEdges / PathBytes 计受控构建中所有步骤、边及路径 JCS 字节，不因最终剪枝退费；Descriptors 计声明 / 图索引、字段映射、值形状 / 绑定与闭包数组的工作单元；OutputBytes 为完整最终记录。每类分配前收费，构建失败不返回部分记录。Descriptors 的固定计数为：6 × Record 声明数 + 2 × Table 声明数 + 5 × 节点数 + 每个声明字段 1 + 每个字段经 Option 解包后的 Record 引用 1；每个节点再加 2 和输出字段数，非 input 节点再加作用域数（join 为 2，其余为 1）；逐行表达式每次构造 1，some 额外 1，record 额外 1 加字段数，match_option 额外 2；最后加 3 × 构建步骤数作为闭包数组预算。此计数由独立材料核对，不是 OS 内存字节或硬资源保证。

strict 先检查外来字节上限，再从完整输入重建并逐字节比较；额外成员、遗漏路径 / 边 / gap、错序、错误引用、错误规则或绑定均不能被修补后接受。InvalidConstruct、版本 / 绑定 / kind / 未知目标、JSON、资源、非规范字节分别报告。

独立 Python 路径从 IR / P2 重建标签、形状与规则步骤；有限正例、手算区别与变异核对不替代完整 P1、形式证明或跨仓 checker。完整记录与无缺口分别统计，真实反例为零。没有缺口仅支持本静态规则，没有公共五态、prove support 或执行门控。
