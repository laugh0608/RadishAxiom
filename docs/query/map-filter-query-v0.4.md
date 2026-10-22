# map / filter query v0.4：双向行覆盖

状态：Accepted，依据 [ADR 0022](../adr/0022-map-filter-row-coverage.md)。用途：规定 P3-D 行覆盖命题、版本兼容、预算与验收；不规定 solver、Evidence 或证明状态。

## 版本与目标

显式 profile `axiom-p3-map-filter-query-v0.4` 在 [v0.3](map-filter-query-v0.3.md) 上只增加 row-coverage。IR v0.2、完整 ir-derived P2 集合、整图功能扫描与拒绝保持；artifact 仍为 `axiom-smtlib2-qf-uflia-query0.2`，方言仍为 `SMT-LIB-2.6/QF_UFLIA`。三个旧 profile 不接受新 kind，原四类目标在新旧 profile 的字节、符号与六项资源用量相同；完整 profile 绑定仍不同。

对绑定的非 input 节点 n，S 为直接来源的实际表；Ready 为 OK(S) 及所有活动局部表达式成功，map 包含全部字段、filter 包含实际谓词，排除自身容量。O* 是真实操作派生的容量前候选，不是运行成功输出或自由变量，不截断到声明容量。

```text
map:    Selected_i = active(S_i)
filter: Selected_i = active(S_i) ∧ predicateValue(S_i)
Match_ij = ∧k Equal(ExpectedKey(S_i)[k], ActualKey(O*_j)[k])
Forward = ∧i (Selected_i ⇒ Σj ite(active(O*_j) ∧ Match_ij, 1, 0) = 1)
Backward = ∧j (active(O*_j) ⇒ Σi ite(Selected_i ∧ Match_ij, 1, 0) = 1)
Coverage = Forward ∧ Backward
assert = WF ∧ Pre ∧ Ready ∧ ¬Coverage
```

map 的 ExpectedKey 按输出 primary_key 顺序，从每个键的规范直接字段投影读取对应来源字段；filter 使用来源的对应键字段。全部分量参与，允许重命名及键序变化；不能以同名字段、槽位下标、相同总行数或单向存在替代。Text 精确相等，不归一化 Unicode。不比较非键字段业务值。表无序，活动槽位可稀疏，空来源 / 空选择 / 空输出正常，非活动载荷不参与。

参考选择从 source.active / 已求值谓词保存，不反推输出 active；实际输出键读取派生字段，不以期望键替代。谓词不重新求值。图及表达式的成功、严格 / 分支求值沿用旧规范。

## 故障与归因

Ready false 时不观察占位输出，totality / numeric-range 仍报告相应故障。自身容量超限不排除关系检查：正确保留两行而容量为一，覆盖无反例而 totality / key-cardinality 有反例；静默截断破坏覆盖。来源容量失败使下游 Ready false。

不加 targetOK、ProgramOK、输出唯一性或其他义务已成立的前提。无关节点、下游及 guarantee 不制造或屏蔽违例；Pre false / fault 排除输入。覆盖针对实际 IR 谓词与直接来源，不保证业务期望，非键字段错误由相应范围 / guarantee 处理。

## 编码、资源与独立验收

只为新 kind 的目标保存选择及键映射、构造双向关系，复用同一派生表。旧四类不增加输出关系项或改变 term 顺序。Ns、No 为来源与输出完整表示规模，K 为主键数；在布局 / 槽位展开前有界核验并累计 Ns × No × K SlotComparisons，当前两侧均为继承 N。两方向共享键匹配计算；实现可流式累计两方向计数，无需存储完整矩阵。比较临时数组、选择和计数数组计入 ValueCells，节点及操作数边计入 SmtNodes，最终字节计入 OutputBytes；乘积和累计溢出均拒绝。零规模不创建伪比较，无部分查询。

完整路径逐世界核对真实 SMT 最终断言，并通过仅测试构建可见的 term 引用导出核对 Ready、Selected、期望键和完整活动输出；该诊断不进入公共 API、生产制品或预算语义。Python 具体解释不读取生产选择 / 输出定义作为期望。

生产关系 helper 的两侧独立合成输入负责覆盖负例，区分单向、存在代替恰好一次、遗漏键分量、错误键映射、输出反推选择、错误谓词、截断、按槽位对齐、错误成功守卫及恒假违例。明确区分局部注入、编码变异和完整程序结果：合法 map / filter 不从 WF 输入任意丢行、造行或造键；无反例不能证明实现正确，不宣称完整程序能区分恒假覆盖查询。

材料在 `contracts/map-filter-query-v0.4`；旧规范、材料与独立脚本保持原字节。仅本机有限动态检查，不产生 solver / proof / checker 结论。row-coverage 之外的未支持 kind、join / group、聚合、双世界以及完整 Evidence 仍按既有边界拒绝。
