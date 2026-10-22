# ADR 0018：IR 派生义务 profile 与 P2 内部组件

日期：2026-10-05

状态：Accepted

用途：落实 ADR 0016 要求的精确 P2 profile 决定，允许先交付只消费规范 IR 的义务生成组件。

## 背景与接受

[P2 审阅](../evidence/p2-obligation-profile-review.md)已经给出 21 份 IR、315 项独立定义、group 目标区分、兼容预览及新身份的成本。2026-10-05，项目所有者在审阅“显式 ir-derived 范围、v0.2 身份与 group 两项目标”及实施询问后回复“确认，继续推进”，接受本决定及对应规范物化、内部生成器实现。

本决定窄替代 ADR 0007 P2 组件必须同时消费实际 trust / concrete check 的顺序要求，并完成 ADR 0016 允许的更窄 profile 审阅入口。完整管线仍须补齐所有位置与实际支持；不修改这些旧 ADR 的绑定原文。

## 决定

1. [IR 派生义务 profile v0.2](../evidence/ir-derived-obligations-v0.2.md)是正式真相源。输入精确为 IR v0.2 CanonicalDocument，profile 为 keyed-finite-table-verification / 0.2，集合为 axiom-obligation-set / 0.2，必需 scope 为 ir-derived。
2. definition 恰为 expectation / kind / subject。所有 IR anchor 带完整 ir_document_digest；ID 使用 axiom-evidence-v0.2:obligation、NUL 与 definition JCS。每次 IR 变化重算全部 IR 派生 ID。集合只使用 raw SHA-256，不增加域摘要。
3. 固定十类义务、六种范围表达式、全部 node / assume / guarantee 路径、group 聚合、命名输出顶层字段和契约位置。group coverage 与 conservation 分开生成；前者固定直接 source 的分区覆盖，后者包含逐组与全局聚合等式，不代替任务 guarantee。
4. 内部 Rust 组件复用既有 JSON、只读 P1 文档和自有摘要，不新增依赖、CLI 或执行能力。strict 入口重建完整集合并核对规范字节；结果只表示定义 / 位置 / 身份一致。
5. 规范中的八项 execution → tool role 映射固定供后续完整 Evidence 使用，producer 必须有 evidence-producer。当前组件不产生 execution、trust、五态、conclusion 或独立接受结果。
6. 新定义与身份受版本约束，不能因完整 Evidence 尚未启用而静默改写。旧格式、IR / Evidence / pipeline / bundle 与实验注册保留原字节。旧结果不得随新 ID 沿用。

## 兼容与后续门禁

这不是接受完整 Evidence v0.2 公共解析或发布。ADR 0009 第 6 项的完整规范、严格迁移器、正负例与完整迁移演练仍未完成；兼容预览仅比对核心定义，不能解除门禁。完整 verification 必须是本集合与实际 trust-boundary 的并集；benchmark 再补具体输入、宿主和黄金比较。

P3 仍须在 query 目标编码边界明确后单独审阅。跨仓、solver / Node / checker 执行、依赖变更、安装、远程写入和发布均不在本次范围。

## 验收与停止线

以独立材料核对定义 / ID / 整体字节；四题正确与 wrong 一律按结构生成，不读取 expected outcome。负例覆盖遗漏 / 多余 / 重复、错目标 / 路径 / 绑定 / 域、旧版本及禁止 result，资源回归覆盖深图、深表达式、宽输出和累计预算。分别报告本机组件、指定态材料、真实独立 checker 与形式证明。

发现规范歧义或范围变化时停止受影响部分并记录，不以默认成功、伪 unknown 或删除义务补足。失败不返回可消费的部分集合。
