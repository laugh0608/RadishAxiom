# ADR 0019：map / filter 单世界查询生成

日期：2026-10-05

状态：Accepted

## 背景与接受

P1 / P2 内部组件已完成本机验收。[P3 审阅](../query/p3-query-encoding-review.md)明确了有限槽位、故障守卫、两类目标、资源拒绝与未支持范围。2026-10-05，项目所有者在该精确方案及实施询问后回复“确认，继续推进”，接受本决定、正式规则与内部 Rust 实现。

本决定满足 ADR 0016 / 0018 的 P3 单独审阅要求，只接受 P3-A 内部切片，不宣称完整 P3 或完整管线。旧 ADR 与格式的绑定原文不修改。

## 决定

1. 输入为 IR v0.2 CanonicalDocument、与之严格匹配的完整 ir-derived ObligationSet 及一个目标 ID。仅支持 numeric-range / contract-guarantee；其他义务保留在 P2 全集中并显式拒绝请求。
2. 整份图仅支持 input / filter / map，全部公式支持核心表达式、forall_rows、lookup；join / group / exists_rows / count_where / sum_where 明确拒绝。非干扰契约不构成单世界假设，其义务仍未支持。
3. 查询断言 WF ∧ Pre ∧ violation。算术目标使用实际可达性、操作数成功和数学结果越界，不能预先假定自身范围或全局程序成功。保证目标要求完整程序与该公式无故障且为 true。and / or / record / forall_rows 严格传播所有活动子实例的故障；if / match_option 仅传播所选分支。
4. 声明容量完整展开；不对输入排序或要求非空，不约束未活动载荷。filter / map 保留来源槽位数，输出容量违规进入故障，不能截断模型。Text 精确相等、Option 保护载荷，数值使用数学 Int。
5. 编码 profile 为 axiom-p3-map-filter-query-v0.1；query artifact 标识为 axiom-smtlib2-qf-uflia-query0.2。只读内部产物绑定 IR / P2 / 目标 / 语义 / profile / 方言 / 生成器身份及符号映射，不生成 Evidence、五态或执行许可。
6. 复用现有 Rust crate、JSON 与摘要，只用既有依赖。显式累计预算在分配 / 展开前检查；资源耗尽不伪装 solver unknown。规则与具体字节顺序见[编码规范](../query/map-filter-query-v0.1.md)。

## 验收与停止线

独立具体解释和 SMT 文本解释在合成小域比较，覆盖全部支持表达式、两个目标及故障 / 可达性 / Pre。AX-B01 三份完整容量查询须从真实规范 IR 与 P2 ID 生成；小域观察与完整容量 solver 结论分别报告。覆盖错绑定 / ID / kind、unsupported、预算、Unicode、None、循环守卫和篡改拒绝。

旧 query 0.1、adapter、Evidence 与 pipeline 字节保持原样。新 artifact 与旧 adapter 的公共集成、完整 Evidence v0.2、独立 checker、真实 cvc5 / Node、跨仓、依赖 / 系统修改、远程写入和发布均另行处理。本次没有额外外部执行授权，不用静态检查或内部 round-trip 冒充证明。
