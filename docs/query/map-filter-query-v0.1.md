# map / filter 查询编码 v0.1

状态：Accepted，依据 [ADR 0019](../adr/0019-map-filter-query-encoding.md)。本文件是 P3-A 内部查询组件的正式编码规则，供实现与验收使用；不定义完整 Evidence、solver 执行协议、模型解码或证明检查。

## 版本、输入与支持集合

编码 profile 为 `axiom-p3-map-filter-query-v0.1`，artifact 标识为 `axiom-smtlib2-qf-uflia-query0.2`，方言标识为 `SMT-LIB-2.6/QF_UFLIA`。这些标识属于本内部组件；旧 query 0.1 / adapter / pipeline / Evidence 不因此接受新输入。

`encode_query` 接受不可变 IR v0.2 CanonicalDocument、不可变 P2 ir-derived ObligationSet、其目标 ID、显式生成器源码摘要和 QueryLimits。P2 集合只能通过完整生成或 strict 重建构造；P3 核对集合的 IR raw 与文档域摘要，利用其私有字段 / 只读 API 保持完整性，不接受调用方拼装的条目列表、缓存类型或 expected outcome。

只编码 `numeric-range` 与 `contract-guarantee`。check 义务返回 NotProve，其他 prove 类型返回 UnsupportedKind，不删除 P2 位置或赋予成功状态。整份节点图须仅含 input / filter / map，全部公式须仅含以下 26 个操作：

- literal_bool / literal_int / literal_fixed / literal_text / literal_enum；
- bound / field / none / some / record；
- not / and / or / eq / lt / le / gt / ge；
- int_add / int_sub / fixed_add / fixed_sub；
- if / match_option / forall_rows / lookup。

group、lookup_join、exists_rows、count_where、sum_where 返回 UnsupportedFeature，携带内容 anchor 和功能名；即使位于未选择的契约也拒绝。非干扰契约保留，但既不编码双世界目标，也不将其作为假设。IR v0.1 不隐式迁移。

## 值和表

Bool 对应 SMT Bool；Int 和 Fixed 系数对应数学 Int，Fixed 不按宿主浮点换算；Enum 按其有语义的成员顺序映射为从零开始的 Int 标签。Text 对应无限未解释排序，仅有精确相等。所有不同 Text 字面值互不相等，视觉相同的 NFC / NFD 不合并。

Record 按规范字段的 Unicode scalar 顺序展开，Option 先放 Bool 标签，再放内值。复合值使用平坦数组与布局引用；字段投影是切片，Option 的 Some 载荷从下一位置开始。None 的占位载荷使用 false / 0 / 空 Text / 递归 None，不要求占位载荷满足内类型值域，也不能从 None 读取它。Option 相等先比较标签，只有 Some 才比较内值；记录相等仍遵循 IR v0.2 的禁止规则。

每个输入的声明容量 N 完整表示为 N 个槽位：一个 active Bool 和完整行载荷。WF 只在 active 时约束字段范围、Enum 标签和嵌套 Some 载荷；只对同时活动的两行约束复合主键不同。不要求活动位紧凑、键排序、输入非空或所有槽位载荷合法。容量零为普通空表。

filter / map 的表示槽位数继承来源，不截断到输出声明容量。filter 严格计算每个活动行谓词，map 严格计算每个活动行全部字段。节点成功等于来源成功、全部活动求值成功及实际输出活动数不超过声明容量。键保持由 P1 的直接投影约束及输入 WF 保证；不另加“输出合法”的全局假设来排除故障输入。

## 求值、可达性与目标

每次符号求值返回数学值 / 复合值和 `ok`。符号构造会遍历未选分支，但该分支的故障只有在实际 Reach 下可观察：

| 操作 | ok 与 Reach |
| --- | --- |
| and / or / record | 全部操作数 / 字段严格成功，兄弟故障不能屏蔽其他兄弟的范围目标 |
| field | 保留被投影记录构造的完整 ok |
| if | 条件成功且所选分支成功；分支 Reach 包含条件 ok 与真假 |
| match_option | subject 成功且所选分支成功；Some 绑定前插为 de Bruijn 0 |
| 算术 | 两操作数成功且数学结果在显式 result_type 内；不采用回绕、饱和或扩大类型 |
| forall_rows | 表成功且所有活动 body 成功；值是全部活动 body 的合取，空表为 true；不在首个 false 后跳过其他故障 |
| lookup | 表成功后计算所有键；零匹配为 None，一次匹配为 Some；表与键故障传播 |

转换节点的逐行 Reach 包含直接来源表成功与行 active；节点自己的成功不进入其内部范围前提。全称 body 另包含所引用表成功与行 active；lookup 键的 Reach 包含所引用表成功。图按依赖完成求值；不相关节点的故障不能屏蔽另一个节点内的范围目标。

`Pre` 是全部 assume 的 `ok ∧ value` 合取，仅引用输入。Pre 故障不当作 true；不新增 Pre 可满足性、输入非空性或 WF 域上的 assume 全定义义务。assume 内范围目标仍受最终 Pre 约束，因此可能因该 assume 故障被排除；这是当前 P2 目标域，不能在本编码中换成另一项义务。

`ProgramOK` 合取全部节点成功。guarantee 在整个程序完成后观察，故其内部范围实例的 Reach 以 ProgramOK 为前提；程序失败本身由 contract-guarantee 的目标捕获。保守敏感标签缺口不是运行时故障。

目标严格绑定 P2 definition 的 anchor 与规范 path：

- numeric-range：对该路径的全部动态实例取 `Reach ∧ operandsOK ∧ ¬Within(mathematicalValue)` 的析取。不得加上目标自身的 Within、包含该位置的 nodeOK 或假定其他义务已证明。一个子表达式已故障时父算术不构成有效运算；子位置仍独立检查。零实例的析取为 false，义务本身不删除。
- contract-guarantee：`¬(ProgramOK ∧ formulaOK ∧ formulaValue)`。全部命名输出来自实际节点定义，不能使用无约束的“期望输出”自由变量。既不预先断言 guarantee，也不预先断言 ProgramOK。

唯一最终断言为 `WF ∧ Pre ∧ violation`，其中 WF 包含 Text 字面类互异。sat 的含义仍只是待解码 / 重放的候选；本组件不运行 solver，也不把生成成功映射为 sat / unsat 或 Evidence 五态。

## 确定性字节和绑定

查询使用类型化、仅向前引用既有节点的 SMT DAG。首行 `(set-logic QF_UFLIA)`，其次 `(declare-sort Text 0)`，然后是常量声明或零参数 define-fun，最后一条 assert 与一条 check-sat。每条命令一行，ASCII / LF、唯一末尾 LF；无注释、路径、时间、set-option、模型 / 证明请求或外部命令。负整数写为 `(- magnitude)`，不写负 numeral atom。

每个 term 的符号恰为 `q` + 目标 ID 的 64 位 hex + `_t` + 从零开始的规范十进制序号。前两项固定 false / true；Text 字面值集合加入空串后按 Unicode scalar 顺序声明。输入 / 节点按依赖深度、再按 ID 排序处理；每表按槽位序，每行按规范字段展开。契约按 ID 顺序；表达式按规范结构的固定子项次序生成。and / or 的零参数结果使用固定 true / false，单参数直接引用；其他项保留确定性创建顺序，不以 solver 简化结果决定字节。

记录布局按声明依赖、ID 及字段序确定；辅助内存布局编号不写入 SMT。定义只引用已有 term，不递归内联 DAG。相同规范输入、目标与实现，在任何足够预算下生成相同字节；原始输入数组顺序不影响结果。

只读 `EncodedQuery` 保留规范字节、raw SHA-256、绑定、符号映射与实际累计用量。绑定包含 IR raw、IR 文档域、P2 集合 raw、目标 ID、语义摘要、固定 profile / artifact / 方言及生成器源码摘要。生成器摘要由调用方显式提供规范 `sha256:` 值；它是来源声明，不是身份认证或构建验收，不能以 crate `0.0.0` 替代。

符号映射的 Input origin 含接口名、槽位及 component：None 表示活动位，其余为按上述记录 / Option 规则展开的叶序号。Text origin 保留精确字面值。源码身份变化可以只改变绑定而不改变 SMT；消费方必须同时检查字节与绑定。`check_query` 从指定 IR / P2 / 目标重建并逐字节比较，拒绝首个差异，不修复、排序或容忍额外命令；这是内部重建核对，不是独立 checker。

## 预算与错误

所有预算由调用方显式提供，无无限默认值。JsonLimits 用于规范 IR 和目标 definition 的有界读取；其余预算上限包含等号，checked 加乘溢出等同资源拒绝：

| 预算 / 用量 | 精确计数 |
| --- | --- |
| InputSlots | 所有输入声明容量之和；先按十进制长度 / 字典序与上限比较，再转宿主 usize |
| ValueCells | 已建立的布局项与记录字段描述项、叶排序数组元素、实际新分配的值 / 槽位元素，以及所复制数值上下界 / SMT 整数字面文本字节；共享切片不重复计数；单个布局展开长度也不得超过此上限 |
| ExpressionInstances | 所有节点与全部公式表达式按表示槽位数展开的 op 次数；分支双方计数，forall body 乘槽位数，零槽位 body 为零 |
| SlotComparisons | 输入两两槽位对 × 主键数、每个 lookup 实例 × 表槽位数 × 主键数，以及 Text 字面值两两互异比较数 |
| SmtNodes | term 节点数加操作数引用边数；固定 false / true 也计数 |
| OutputBytes | 完整 SMT 字节总量，包括首尾命令与末尾 LF，完整分配前计数 |

容量、嵌套实例乘积、输入键比较和 Text 类比较先预算，再展开；每份值与 SMT 操作数数组分配前核对相应累计量。记录引用和节点 DAG 使用迭代拓扑 / 平坦表示，JSON 表达式递归仍受既有 128 层上限约束。名字、引用索引和原 P1 / P2 对象还受输入规模约束，预算不是 OS 硬内存 / 时限，也不保证宿主 OOM 可恢复。

ResourceLimit 携带预算类别和目标 ID；与绑定、版本、未知目标、NotProve、UnsupportedKind、UnsupportedFeature、JSON、非规范字节与内部不变量错误分别报告。失败不返回部分 query。不能以少算槽位、删除位置或伪 unknown 满足预算。

## 验收边界

[独立材料](../../contracts/map-filter-query-v0.1/README.md)包含合成 IR、有限输入、逐目标期望和一个手算字节向量。Rust 测试真实生成 SMT；独立 Python 路径解析 / 类型检查并解释实际文本，与具体 IR 求值比较。Python 的两条解释路径不调用生产编码器、solver 或旧结果标签；它们仍是有限动态检查，不是形式证明。

P3-A 不完成其他七种 prove 目标、完整 P3、P4、P7 / P9、Evidence v0.2 或真实 checker / solver 验收。下一步必须按具体缺口审阅，不用本切片扩大外部授权。
