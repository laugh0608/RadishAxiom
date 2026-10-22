# ADR 0022：map / filter 行覆盖关系查询

日期：2026-10-08。状态：Accepted，项目所有者已接受 P3-D 精确方案并要求继续实施。

## 决定

按 [P3-D 审阅](../query/p3-row-coverage-review.md)，新增显式 `axiom-p3-map-filter-query-v0.4`，只扩展 map / filter 的 row-coverage。P2 definition / ID、IR 与既有查询 profile 不变。

Ready 为直接来源成功且全部活动局部表达式成功，不含自身容量。对真实容量前候选 O* 检查所选直接源行与实际输出的双向恰好一次键关系；最终反例式为 `WF ∧ Pre ∧ Ready ∧ ¬Coverage`。自身容量失败仍可观察操作关系，来源或局部表达式故障不从占位行制造反例。无关 / 下游 / guarantee 不参与目标，不能增加 targetOK 或 ProgramOK 守卫。精确规则见 [v0.4](../query/map-filter-query-v0.4.md)。

map 的期望键来自规范直接字段投影，允许键重命名及次序变化；filter 的参考选择来自实际谓词值，不能从输出活动位恢复。实际输出也不能由来源键替代。查询不引入自由输出，不返回硬编码 false；覆盖不含非键业务值相等。

## 资源和兼容

仅新目标累计 Ns × No × K SlotComparisons；两方向共享匹配计算，其他数组、节点、边和字节受现有预算约束。先有界预检再配对；表示规模使用完整继承槽位，不用输出声明容量降价。旧四类目标字节、符号和预算保持，旧 profile 继续拒绝 row-coverage。artifact、方言和 encode / check 签名不变。

## 证据和停止线

合法 map / filter 的行覆盖受操作规则约束。完整程序有限比较核对选择、期望键、完整输出及最终反例式；局部关系注入负责丢行、添行、重复、乱序和错误映射等负例。恒假查询在受限合法程序域可能不可区分，不能虚报端到端变异覆盖。

不新增结构证书、solver、五态或独立 checker 结果。结构证书需另行定义规则、格式和独立核验路径；effect-empty、field-origin、join / group、双世界及 P4 / P7 / P9 保留各自范围。若发现需改变既有 P2 命题、旧绑定材料或扩大外部执行，停止扩张并重新审阅。
