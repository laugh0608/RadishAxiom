# ADR 0023：纯核心空效果结构推导

日期：2026-10-08。状态：Accepted，项目所有者已接受 P3-E 精确范围并要求继续开发。

## 决定

按[接续审阅](../query/p3-structural-obligations-and-p4-review.md)，在现有 IR crate 内新增空效果推导入口，覆盖全部 P1 v0.2 纯构造。输入为不可变 CanonicalDocument、完整且匹配的 ir-derived ObligationSet、effect-empty 目标、显式生成器身份和预算。

组件按闭合规则重建全部节点、表达式、契约、接口与空效果声明，生成确定的版本化内部记录；记录绑定完整 IR / P2 / 目标与规则 profile。精确规则及字节见[空效果推导 v0.1](../query/core-empty-effects-v0.1.md)。生产 strict 重建与独立 Python 有限核验分别报告；不复用 P1 成功布尔值作为整个推导，不构造恒假 SMT。

旧 IR / P2 定义和身份、四版 query、Evidence 与 adapter 字节保持。生成器身份复用已有只读 GeneratorIdentity 值，不复用 EncodedQuery。表容量不展开，图共享不展开，全部临时步骤 / 前提 / 路径与输出受预算约束。

## 信任与停止线

完整 P1 结构、类型与内容身份正确性是明确输入前提；独立验收另重建本批效果规则、引用、全集及绑定，不宣称替代完整 P1 或跨仓 checker。纯性不蕴含总性、覆盖、契约真假、字段来源、非干扰或外围进程无副作用。

内部记录没有五态、proof / kernel support、execution 或门控许可。接入 kernel-replay、完整 Evidence v0.2 或独立 checker 需要各自格式与真实执行验收；本决定不修改旧 ADR 0007 的公共生产路径。field-origin、P4 工具执行、依赖安装、跨仓与远程动作不在范围内。
