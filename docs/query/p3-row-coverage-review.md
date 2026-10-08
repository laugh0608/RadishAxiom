# map / filter 行覆盖目标审阅

日期：2026-10-08。状态：Accepted，项目所有者已要求按本精确方案继续实施；正式规则见 [ADR 0022](../adr/0022-map-filter-row-coverage.md) / [v0.4](map-filter-query-v0.4.md)。

用途：供项目所有者与实现者决定 P3-C 后的 row-coverage 观察语义、实现路径及验收边界。本文保留接受时的审阅推导；实施以 ADR 0022 / v0.4 为准，不改变已接受的 P2 或 IR，不宣布目标已证明成立。

## 结论与建议切片

建议 **P3-D 增加 map / filter 的 row-coverage 显式关系查询**，使用容量前候选 O* 与 Ready 守卫，新增显式 v0.4 profile。关系必须从直接来源的选择条件与实际派生输出两侧构造，不硬编码 false，不引入自由输出让 solver 自选错误答案。

暂不新建结构证书或独立 checker 协议。结构证书是后续减少平凡查询成本的合理路径，但需要规则身份、推导前提、闭合证书格式、独立核验及结果支持策略；本轮不把 P1 检查结果包装成证明证书。

这项能力的价值是完整表达和绑定一个现存 P2 目标，并提供可被局部关系变异击穿的编码与验收路径。它不是新增业务检测能力；在忠实 map / filter 语义及现有键限制下，覆盖应由操作规则成立。即便未来 solver 返回 unsat，也不能据此宣称编码器正确或业务保证成立。

## 已核对的约束

- [P2 规则](../evidence/ir-derived-obligations-v0.2.md#精确生成位置与目标)规定直接来源上的双向覆盖：filter 为实际谓词选中且只选中的源键，map 为源键与输出键双射。目标不是原始输入、最终输出或业务希望保留的集合。
- [IR v0.2 语义](../semantics/keyed-finite-table-semantics-v0.2.md#筛选)规定 filter 不造行、记录及键不变；map 对每个源行构造一个记录，并直接保留或一一重命名全部源键。
- [P1 类型检查](../../crates/axiom-ir/src/nodes/typing.rs)实际核对这些字段、类型、键投影与容量形状。它不执行表达式或证明容量 / 覆盖结果。
- [当前编码器](../../crates/axiom-ir/src/query/encode.rs)使用继承槽位，filter 形成 `source.active ∧ predicate.value`，map 保持来源活动位并构造全部字段；实际成功还合取来源、局部表达式与容量。
- [ADR 0021](../adr/0021-map-filter-key-cardinality.md)仅接受 key-cardinality 的 Ready / O* 观察；不能自动把该决定视为 row-coverage 已获语义授权。旧 profile 仍拒绝 row-coverage。

既有 [26 份 IR 清单](p3-query-review/materials.json)中有 29 个 row-coverage 位置。沿用当前整图功能扫描时，12 个具备支持形状，17 个被 join / group / 聚合表达式等阻断。静态复核的 12 个位置为：AX-B01 三份候选各 2 个、AX-B04 correct 1 个 / wrong-sensitive-filter 2 个 / wrong-sensitive-priority 1 个、mixed-int-ranges 1 个、records 1 个。这里只计算形状和预算成本，未运行新目标编码。

## 故障观察的精确建议

对目标节点 n、其直接来源 S 和容量前行候选 O*：

```text
Ready(n) = OK(S) ∧ 所有活动局部表达式均成功
violation = Ready(n) ∧ ¬Coverage(S, O*, n)
assert = WF ∧ Pre ∧ violation
```

map 的局部表达式包括全部字段，而非只检查键；filter 包括每个活动来源行的实际谓词。O* 由真实 IR 操作派生，保留全部继承槽位，不能截断到目标容量。O* 不成为运行成功输出。来源故障或局部表达式故障时，不用占位值制造覆盖反例；totality / numeric-range 仍承担相应失败。

目标自己的容量失败不进入 Ready：只要逐行计算完成，仍能检查操作的行关系。正确保留两行而声明容量为一时，coverage 无反例，key-cardinality 与 totality 有反例；静默截断为一行会破坏覆盖关系，不能冒充容量修复。来源容量失败属于来源故障，下游不再用占位行推导新的局部覆盖违例。

不加 targetOK、ProgramOK、输出键唯一或“其他义务已经证明”的前提。无关节点、下游与 guarantee 不改变本目标；Pre false / fault 仍排除输入。不新增非空性、Pre 可满足性或业务意图假设。

另一合理解释是只在目标成功时观察 `OK(n) ∧ ¬Coverage`。它不观察容量超限时的候选关系，因而对“截断候选但仍报告容量失败”的错误可能无判别力。本提案不采用该解释；这正是实施前需要明确接受的语义选择。

## 双向关系，而不是槽位位置相等

令来源表示槽位为 S_i，输出候选为 O*_j。两侧都用实际 active，不假定紧凑排列、稳定行序或相同槽位编号。

- map：`Selected_i = active(S_i)`。从规范 IR 的直接键字段投影逐项读取输出键到来源键的映射，形成期望键向量 ExpectedKey(S_i)。支持重命名及主键分量次序变化，不能按字段名相同或下标相同猜对应。
- filter：`Selected_i = active(S_i) ∧ p(S_i)`。p 是该节点的实际 IR 谓词值；期望键按输出主键顺序直接来自 S_i。
- `Match_ij` 比较 ExpectedKey(S_i) 与实际派生输出键 Key(O*_j) 的**全部分量**。Text 精确相等，不做 Unicode 归一化。

建议具体关系为：

```text
Forward = ∧i (Selected_i ⇒ Σj ite(active(O*_j) ∧ Match_ij, 1, 0) = 1)
Backward = ∧j (active(O*_j) ⇒ Σi ite(Selected_i ∧ Match_ij, 1, 0) = 1)
Coverage = Forward ∧ Backward
```

双向“恰好一次”给出所选源行与候选输出行的双射：遗漏、额外行和重复行均能在局部关系层区分。不以仅行数相等、单向存在或某一主键分量相等替代。对现行良构有键表，这与 P2 的操作覆盖目标一致；重复行的合成注入可同时违反 key-cardinality，不要求两目标互斥。

没有被选中的源行不需要输出；空来源 / 无选中行与空 O* 满足关系。未活动载荷完全不参与。非键字段值不进入 Coverage；map 计算了错误的业务金额却仍保留键时，范围或 guarantee 应负责，不能把完整记录相等偷加到 coverage。

参考选择必须在合成输出 active 之前由 source.active / 实际谓词值保存，不能反过来从输出活动位或已生成的输出键集合恢复“期望”。匹配读取实际输出字段，也不能直接把来源键当作输出键来省略核对。现有表达式值可以共享，不能重新求值形成另一套可达性口径。

## 手算区分与可信边界

以下是数学示例，非运行程序、SMT 模型或 Evidence。直接 S 为 `(a, 0), (b, 1)`；除特别标注外 Ready / WF / Pre 为 true：

| 场景 | Coverage | 覆盖反例式 | 归因 |
| --- | --- | --- | --- |
| map 正确保留两键，输出行换序 | true | false | 表无序，不能按槽位位置误报 |
| filter `value > 0`，O* 仅有 b | true | false | 忠实执行实际谓词；不保证业务原本想要 `>= 0` |
| filter true，O* 为 a、b，声明容量 1 | true | false | totality / key-cardinality 承担容量失败 |
| 同上但错误截断 O* 为 a | false | true | 合成编码变异；遗漏选中的 b |
| filter `value > 0`，错误 O* 为 a、b | false | true | 多保留未选中的 a |
| map 错把 b 改成 c，仍有两行 | false | true | 同行数不等于覆盖 |
| map 输出 a、a、b | false | true | 重复行同时可违反键唯一性 |
| 来源或任一活动局部表达式故障 | 不观察 | false | totality 仍可失败；不把占位结果当空表 |
| 正常节点配 false guarantee | true | false | 业务断言与内建覆盖分开 |
| Pre false / fault | 不进入目标域 | false | 不加强假设的全定义性 |

合法 map / filter 不存在“任意造键、丢掉选中行或制造额外行”的操作入口。因此上述非法候选只能用于**局部关系谓词或编码器变异测试**，不能称为通过 P1 的真实程序反例。完整路径主要验证正确操作不误报，以及故障 / Pre / 绑定的边界。

完全删除 Coverage 并返回 false，在这个受限合法程序域可能与正确查询无法区分。必须以生产关系 helper 的合成双侧输入和编码变异检验其敏感性，明确分开报告；不能宣称合法程序端到端测试已经杀死恒假查询。生产 strict 重建仍非独立核验，有限具体解释仍非形式证明。

## 实现、版本与预算方案

建议新增 `QueryProfile::MapFilterV0_4` / `axiom-p3-map-filter-query-v0.4`，支持已有四类及 row-coverage；前三个 profile 不扩大集合，原四类的 SMT 字节、符号与预算保持。artifact、方言、P2 definition / ID 和现有 encode / check 函数签名不变。不能借此启用旧 Evidence、adapter 或 checker。

只为新 kind 的目标保存来源选择与键映射，复用真实派生槽位；不为全部节点创建第二份表或表达式求值图。Ready 可复用 P3-C 的语义，但不得改变旧目标 term 顺序和资源拒绝集合。

设两侧表示规模为 Ns、No，键分量数为 K，预收 `Ns × No × K` SlotComparisons；两方向共享匹配项，只收一次字段比较，计数和逻辑项另收 SmtNodes / ValueCells。当前 map / filter 的 Ns = No = 继承 N，不用声明输出容量降价。全部乘积及累计加法在任何配对循环和矩阵分配之前有界核验；矩阵 / 临时数组、节点 / 操作数边、输出字节都必须计入现有预算，不新增无界缓存。

现有形状候选中，AX-B01 / AX-B04 的 N=100、K=1，每个目标新增 10,000 次槽位分量比较；mixed-int-ranges / records 的 N=3、K=1，各新增 9 次。还需叠加既有输入唯一键、lookup、Text 成本及 SMT / 字节开销。12 个形状候选不等于已通过资源门禁，不提前声明最终可生成数量。

结构证书路径暂后置：未来至少要独立核验 IR / P2 绑定、直接来源、键映射双射、谓词与 Ready 规则，以及证书版本 / 资源 / 篡改拒绝；不能复用生产编码器的“成功”标志自证。若实施发现必须改 P2 命题、增加自由期望输出或共享同一错误关系才能完成验收，应停止扩张并重评路线。

## 必需验收与停止线

1. **完整 IR 路径：** 原有材料及 AX-B01 全容量三候选；空表、零容量、稀疏槽位、全部 / 部分 / 无选择、键重命名及复合键顺序、Unicode、共享深图、无 guarantee、错业务谓词与 false guarantee。
2. **故障：** 活动 map 非键字段故障、filter 谓词故障、来源容量故障、目标自身容量失败、无关 / 下游故障、Pre false / fault。完整路径保留相应 totality / key-cardinality 对照，不能只看 coverage 恒 false。
3. **独立观察：** Python 从实际 IR 与具体来源计算 Selected、期望键及完整 O*；测试专用导出核对选择 / 输出观察和最终 SMT，避免只比较最终恒 false 掩盖共同错误。原冻结解释器与 manifest 不改。
4. **局部关系：** 调用生产关系 helper 注入两侧独立合成数据，覆盖遗漏、额外、重复、换序、同数量错键、复合键单分量相同、非活动载荷、全空、键排列；不加输入 WF 将负例过滤掉。
5. **变异：** 去掉 Forward / Backward、把等于一改为存在、只比较一个键分量、用分量析取、把 Match 恒真、以输出 active 反推 Selected、使用错误谓词 / 键投影、截断输出、按槽位下标配对、丢 Ready、额外 targetOK / ProgramOK、恒假目标。仅在相应合成关系 / 故障观察中可区分的项目单列，不能虚报真实程序覆盖。
6. **绑定与资源：** profile / IR / 集合 / 目标 / node / 字节篡改、旧 profile 拒绝、原四类字节与全部用量基线、整图未支持拒绝；六类预算精确值 / 差一、N²K 预检、巨大容量和算术溢出、不返回部分查询。
7. **门禁：** 格式、Clippy、精准与 workspace 测试、仓库检查；报告实际查询和拒绝数量，不预填成功。无 solver、证书、五态、跨仓或其他平台结论。

本方案已接受，正式规则见 ADR 0022 / v0.4，实际实施验收见 [P3-D 记录](../records/2026-10-08-p3d-validation.md)。effect-empty、field-origin、join / group、双世界、结构证书格式、完整 Evidence 和 P4 / P7 / P9 均不包含在该实施范围。

已接受的精确选择：**只增加 map / filter 的 row-coverage；以 Ready 守卫容量前 O*，显式构造所选直接源行与实际候选输出的双向恰好一次键关系；使用 v0.4 profile 与目标 N²K 预算，并把局部负例、完整程序观察和证明边界分别验收。**
