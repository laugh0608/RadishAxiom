# P3 query 编码范围审阅

日期：2026-10-05。状态：范围已接受，原提案留存。

项目所有者审阅后回复“确认，继续推进”。实施依据为 [ADR 0019](../adr/0019-map-filter-query-encoding.md) 与[正式编码规则](map-filter-query-v0.1.md)；以下保留当时建议和审阅取舍，动态实现状态见[当前状态](../status/current.md)。

用途：供项目所有者审阅 P2 之后首个真实查询生成组件的范围、目标与验收成本。不替代已接受的语义 / IR / P2 规范，不是完整 P3、Evidence 或 solver 验收。

## 建议决定

建议先交付 **P3-A：map / filter 单世界查询生成**。输入为 P1 的只读 IR v0.2 文档、与之严格匹配的 P2 ir-derived 全集及其中一个义务 ID；仅编码 `numeric-range` 与 `contract-guarantee`。整份图只接受 input / filter / map，公式接受核心表达式、forall_rows 和 lookup；暂不接受 lookup_join、group、exists_rows、count_where、sum_where。这是明确的内部组件支持集合，不是删除其他 P2 义务的新 profile。

每次请求先检查完整集合绑定，再核对 expectation / kind 和整份 IR 的功能支持。未支持义务、功能、绑定错误、资源拒绝分别返回可定位错误，不输出可消费的部分 query，不生成 `unknown` 或其他 Evidence 五态。非干扰契约可保留在 IR 中，但其义务不受支持，也不能成为单世界假设。全部 assume / guarantee 均扫描功能边界，不能依据本次目标跳过不支持的契约。

选择这一切片是为了直接覆盖 AX-B01 的正确、wrong-add、wrong-drop-zero 三份真实 IR，先验证从规范 IR / 义务到目标公式的关键路径。AX-B02 / B03 的 join / group、AX-B04 的双世界非干扰和其他七种 prove 义务后续分别审阅；不能称为完整 P3，也不能因此开启任何 target gate。

[覆盖清单与区分材料](p3-query-review/README.md)逐项列出当前 26 份 IR 的候选义务和未覆盖 ID；静态候选数不代表实际 query 已生成或预算可满足。

## 目标公式与求值边界

沿用 [ADR 0005](../adr/0005-first-verification-backend.md) 的有限槽位和 QF_UFLIA 路线。官方 [SMT-LIB QF_UFLIA 定义](https://smt-lib.org/logics-all.shtml#QF_UFLIA)允许无量词线性整数、自由排序及未解释函数。本切片只需 Bool、Int 和未解释 Text 排序；有限展开不能发出 SMT 量词，不引入字符串排序、非线性运算或机器整数回绕。

令 `WF` 为输入类型 / 容量 / 键唯一性；每个表达式携带 `(value, ok)`；`Pre` 为所有 assume 的 `ok ∧ value`。假设求值故障不能当作 true；这里不新增 Pre 可满足性或 WF 域上的 assume 全定义义务。Pre 不成立的输入不进入目标域，Pre 内的算术义务也仍使用这一目标域，不能静默改变 P2 语义。

| 目标 | 反例查询中的 violation |
| --- | --- |
| numeric-range | 对该规范路径的所有动态实例取析取：`Reach ∧ operandsOK ∧ ¬Within(mathematicalValue)` |
| contract-guarantee | `¬(ProgramOK ∧ formulaOK ∧ formulaValue)` |

查询最终断言 `WF ∧ Pre ∧ violation`。guarantee 使用完整实际程序输出，ProgramOK 包含图计算、容量和运行时类型故障，不把保守标签缺口当作运行时故障。每个输出必须由节点定义计算，不能是与程序无关的自由符号。

**禁止把 numeric-range 自身的 Within、包含该表达式的 nodeOK、全局 ProgramOK 或其他义务的假定成功加到该目标的前提。** 否则越界会先令前提为 false，形成循环论证。Reach 只包含进入该求值实例必要的条件：活动行、已完成的上游表、所选分支条件 / Option 标签等。子表达式先故障时，其父算术不再构成有效运算；子位置仍有自己的目标。严格求值的兄弟表达式不能相互屏蔽范围反例。

核心规则须在实施前写入新的编码规范并补独立期望：

- and / or 的全部操作数和 record 的全部字段严格求值；投影不会删除构造记录时其他字段的故障。if 只执行条件与所选分支，match_option 只执行 subject 与所选分支，Some 按 IR 的 de Bruijn 索引前插绑定。
- forall_rows 展开为全部活动行 body 的合取，ok 合取全部活动实例的 ok；空表为 true。它不是找到首个 false 后跳过其余故障的执行循环。本项作为本次明确审阅的故障传播约定，不能只由实现自行选择。
- lookup 使用完整活动槽位按复合键精确匹配，零匹配得到 None；None 不是零值记录。其参数与所引用表故障均传播，Some 才能观察载荷。
- 节点仅沿数据依赖传播故障；其他无关节点的故障不能屏蔽局部范围目标。guarantee 则要求整个程序执行成功。节点失败后下游不继续实际求值。

## 表、值与身份

输入每个声明容量 N 使用 N 个槽位，各自 active 与载荷。只对活动行约束值域和键唯一性；不要求槽位紧凑、按键排序或输入非空。零容量正常表示空表。未活动载荷不约束，所有读取受活动条件保护。Enum 使用有限 Int 标签，Fixed 使用与 scale 对应的整数系数，Option 使用标签和受保护的载荷，Record 按类型展开；值相等必须递归忽略 None 载荷。

filter / map 继承来源表的**表示槽位数**，不能截断到输出声明容量。filter 逐活动行求谓词，map 逐活动行求全部字段；实际活动数超过目标容量产生 node 故障，不先断言输出合法来排除输入。map 的键保留仍依据 P1 约束。

Text 只允许精确相等，不做 Unicode 归一化。不同字面值用不同常量并断言彼此不同；同一字面值共用常量。将来模型中新等价类需编码为互不相同且不撞字面值的合成 Unicode，并独立重放；本切片没有模型解码能力。

产出拟为不可变的内部 query 对象：SMT 字节 / raw SHA-256、IR raw 与文档域摘要、P2 集合 raw 摘要、目标 ID、语义摘要、编码 profile、solver 方言、生成器身份与符号映射。生成器身份必须显式绑定实现来源，不能用固定版本字符串冒充精确身份；调用方声明的摘要不是工具验收或 attestation。

拟为新编码 profile `axiom-p3-map-filter-query-v0.1` 与 query artifact `axiom-smtlib2-qf-uflia-query0.2`，均待接受后物化。旧 query 0.1 与 adapter 登记、Evidence / pipeline 的已绑定字节保持不变；当前组件可面向既有 cvc5 方言生成文本，但旧 adapter 接受新 artifact 的集成尚未授权或验收，不能直接套用旧结果。

生成使用类型化 SMT 表达式，用户名称通过规范路径 / 索引映射为稳定 ASCII 符号，不拼入语法。稳定顺序声明 / 定义，辅助项按依赖排列；一条最终 assert，一条末尾 check-sat，ASCII、LF、唯一末尾 LF。无注释、时间、路径、随机值、set-option、额外 model / proof 命令。相同绑定与实现身份在任何足够预算下生成相同字节；共享子式不能因文本内联而指数膨胀。

## 资源与失败

除 P1 / P2 预算外，调用方显式提供累计输入槽位、展开值单元、表达式实例、槽位比较、SMT 节点及输出字节上限。容量为任意长度十进制：先与预算比较，再转宿主索引；嵌套 forall / lookup 的乘积、复合值展开、两两键比较均先做有界计算，再分配。不能先构造大数组再检查，也不能通过减少容量、只用一行或省略某些实例来满足预算。

超限返回 ResourceLimit，保留目标和预算类别；不是 solver timeout，更不是 Evidence unknown。批量调用也不得把已生成子集标为完整 P3。实现验收覆盖每项精确上限 / 差一、零容量、超大容量、深绑定乘积、深图共享及输出容量小于来源容量。

## 必需验收与后续前置

| 交付 | 本切片验收 | 仍需后续完成 |
| --- | --- | --- |
| 查询语义 | 独立的小域具体求值与 query AST 解释比较；覆盖 WF / Pre / Reach / fault、算术与所有支持 op，不调用生产生成器制作期望 | 真正 solver 对文本解析 / 求解、独立模型重放及证明检查 |
| AX-B01 | 三份规范 IR 与真实 P2 ID 的确定性字节；正确候选的小域无反例、两个 wrong 的具体业务反例；不读取 expected outcome 决定公式 | 完整容量 solver 结果；invalid 在 P1 拒绝，timeout 仅在真实 P4 观察后记入 |
| 负例 | 错绑定 / ID / kind、缺失义务、unsupported、循环守卫、符号冲突、Text NFC / NFD、None 载荷、预算与 tamper 拒绝 | 旧 / 新公共 Evidence 的完整迁移与集成拒绝 |
| P4 | 本次不执行外部工具 | 精确 solver payload / adapter 验收、资源限制、stdout 协议、模型与 proof 绑定；执行另行授权 |
| P7 / P9 | 保留接口与责任边界 | 新 Evidence 格式、trust / concrete checks、独立 checker 支持和真实重放 / 证明链；跨仓另行授权 |

现有 query 文本检查只验证部分词法、括号与首尾命令，不能证明 SMT 语法或语义正确。新的内部 AST 检查也不独立证明编码健全。审阅材料中的手算例只区分错误公式，不是从 IR 生成 query 的动态验收，不计为 proved / failed。

## 待接受范围

接受后新增 ADR / 正式编码规则，按上述范围实现内部 Rust 组件及独立期望；不增加依赖、CLI、执行能力，不变更 P2 定义或旧公共绑定。不支持部分继续显式拒绝，完成后再审阅下一块。若接受前发现既有规范与严格故障传播冲突，先定位并解决规范边界，不在实现中静默补丁。

依据 [ADR 0016](../adr/0016-core-semantic-slice-entry.md) 与 [ADR 0018](../adr/0018-ir-derived-obligation-profile.md)，本审阅不自动授权 P3 生产实现。
