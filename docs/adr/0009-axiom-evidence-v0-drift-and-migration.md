# ADR 0009：Axiom Evidence v0.1 漂移收口与 v0.2 迁移边界

日期：2026-08-24

状态：Accepted

用途：处理 Axiom Evidence v0.1 义务生成位置表与已接受首域语义、Axiom IR 映射之间的漂移，并冻结不改写既有规范字节的版本化修正与迁移边界。

不包含：立即发布完整 Axiom Evidence v0.2、修改 v0.1 domain separator、跨版本复用结果、重放反例、检查 proof 真值、重算 conclusion 或发布 checker。

## 背景

[首域语义](../semantics/keyed-finite-table-semantics.md)要求 group 同时满足行覆盖与分组守恒；[Axiom IR v0.1](../ir/axiom-ir-v0.md)的 AX-B03 映射也要求每个输入事件都进入其账户组，并把分区覆盖、不相交与守恒列为内建义务。已经锁定的四题 bundle 据此为 group 分别生成 `row-coverage` 与 `group-conservation`。

[Axiom Evidence v0.1](../evidence/axiom-evidence-v0.md)的义务种类表允许 group `row-coverage`，完整集合章节也要求覆盖所有现行语义位置；但“v0.1 义务生成位置”表只在 filter、map 与 lookup_join 行中列出 `row-coverage`，没有显式列出 group。这会使独立实现可能生成两个不同的义务集合，属于义务完整性含义漂移，而不是排版差异。

同时复核锁定 bundle 生成器时发现，fixture tool 会形成 `replay-counterexample` execution，却只声明 `fixture-checker` 而没有声明 v0.1 已有的 `counterexample-replayer` role。这里不需要新增格式成员或 tag，但合成语料必须修正为使用既有 role，checker 不得通过角色别名放宽规则。

## 决策

1. Axiom Evidence v0.1 的现有规范文件保持原始字节不变。不得直接补写 group 行、改变 v0.1 domain separator，或把旧文档摘要下的 Evidence 原地解释为新语义。
2. 当前 checker 只对由首域语义、Axiom IR AX-B03 与锁定 bundle 共同确定的实现 profile 重建 group `row-coverage`；该行为必须在 checker 实现说明中标为受限 profile，不扩大为“所有 Evidence v0.1 读取器都已兼容”。
3. 锁定合成 bundle 的 generator 立即为执行 `replay-counterexample` 的 fixture tool 增加既有 `counterexample-replayer` role，并在生成期按 execution kind 检查精确 tool role。由此产生的新 tool、execution、trust、Evidence、request、manifest 与预期结果摘要必须沿完整 DAG 重算，旧摘要不得继续引用。
4. 下一次公共 Evidence 格式修正使用 `evidence_version: "0.2"` 和 obligation profile `version: "0.2"`。v0.2 必须显式把每个 group 节点的 `row-coverage` 与 `group-conservation` 分列，并固定 execution kind 到 tool role 的映射。
5. v0.1 到 v0.2 迁移必须严格解析源文档，按 v0.2 规则重新生成全部 obligation definition / ID、execution / tool 绑定、Evidence 文档摘要和独立结果。不得跨版本复用 `proved`、`checked` 或 `trusted` result；只有重新验证后才能形成目标状态。
6. 在 v0.2 规范、迁移器、正负例和一次完整迁移演练落地前，v0.1 继续是唯一可解析公共版本，checker 的支持声明必须同时列出该受限 profile 与上述漂移边界。

## 后果

- 既有 v0.1 规范摘要及其上游引用保持稳定，避免无提示改变已发布规范身份。
- 锁定合成 bundle 的内容摘要会因工具 role 修正而变化；这是对无效 fixture 的闭合修正，不是 solver、Node 或 checker 运行观察。
- group 覆盖的公共含义不会通过 checker 私有实现偷偷冻结；v0.2 仍需单独物化、审阅与迁移演练。
- state / support checker 可以严格要求 `replay-counterexample` 使用 `counterexample-replayer`，无需接受 `fixture-checker` alias 或默认成功 fallback。

## 验证要求

- bundle generator 必须拒绝 execution kind 与 tool role 不匹配；
- 重生成后的 28 个 bundle、source lock、readiness 反向引用和仓库级摘要门禁全部通过；
- 独立 checker 导入新的精确 contract identity，并以错误 tool role 负例形成稳定 `invalid-state-support`；
- v0.2 落地时必须增加 group 覆盖正例、遗漏负例、角色错配负例和 v0.1 → v0.2 摘要迁移记录。
