# Axiom Evidence v0.2 机器契约草案

2026-11-07，基线为 dev 的 90d2593 及已核对的 S1–S3 审阅材料。状态为待审阅。本文与[机器登记](contract.json)定义 verification profile 的候选字节、身份和结果绑定。其余九项 AX-B01 核心义务仍按完整全集检查，所需真实执行和公共支持待补齐。P6 保持 closed / p6-not-evaluated。 [支持汇总与迁移演练](../evidence-v0.2-minimal-support-review.md)

## 字节、版本与身份

顶层精确使用登记的 document 成员，format 为 axiom-evidence，evidence_version 为 0.2，digest_algorithm 为 sha-256，obligation_profile 为 keyed-finite-table-verification / 0.2。本稿仅选择 verification。benchmark profile、额外执行模式以及新的独立 request / manifest / result 字节另行审定。读取器从受信的契约标识选定规则，不因输入中的版本串自动启用支持。

机器字节是 UTF-8 JCS 的 IR JSON 子集。对象键按 UTF-16 码元序排序，禁止重复解码键、非法 Unicode、number 和 null。整数均用规范非负十进制字符串，零为 0。保留名称原 Unicode 标量序列，无 BOM、额外空白或末尾 LF。严格入口比较原始字节，不以规范化修复后的字节代替原件。

摘要写作 sha256: 后接 64 位小写十六进制。artifact 的 content_digest 是实际原字节 SHA-256。IR 文档域 ID 沿 IR v0.2。tool、execution、obligation、trust、uncovered 条目按登记的域对 UTF8(domain) + NUL + JCS(definition) 计算 ID。完整 Evidence 对整个规范文档用 document 域计算 ID，既不内嵌该 ID，也不与原始摘要混用。义务 result 位于 definition 外，替换 result 会改变 Evidence 文档身份。

顶层 artifacts 按 content_digest 严格递增，tools、executions、obligations、trust、uncovered 按 id 严格递增。每个制品只登记一份 byte_length、format 和 format_version，同一制品可由多个角色引用。所有引用须解析至对应登记，禁止悬空引用和未引用制品。实际取得但长度或摘要不符时拒绝；独立路径缺少必要原件时报告 incomplete。

## Subject、工具与执行

| 部分 | 闭合成员及绑定 |
| --- | --- |
| 合法 subject | kind 固定 axiom-ir，ir_version 为 0.2，ir_artifact 指向规范 IR 原件，ir_document_digest 为独立重算的文档域 ID。semantics 恰含 name 和带 sha256: 前缀的 sha256，与已选 v0.2 IR 语义及 P2 绑定一致。 |
| 拒绝 subject | 恰含 kind: rejected-ir 与 artifact。artifact 指向原始候选，描述为 ir-candidate / 0.1。首版拒绝分支仅装配一项结构义务，trust 为空。结构义务的 definition 恰含 kind: ir-structure、expectation: check，subject 与顶层拒绝 subject 一致。 |
| tool | definition 恰含 artifact、name、roles、version。artifact 绑定实际工具制品，name 为稳定名称，version 为精确版本或不可变修订。roles 是严格递增的非空角色集合。producer 指向含 evidence-producer 的工具。 |
| execution | definition 恰含 kind、mode、tool、obligation、ordinal、provenance、rule、inputs、outputs、limits、result。obligation 绑定唯一目标 ID。ordinal 为该 Evidence 内从零开始连续的尝试顺序，参与 ID 计算，防止相同尝试被去重。顶层数组仍按 ID 排序。 |
| 规则与来源 | rule 引用 evidence-rule / 0.1 原件，且匹配登记的精确模式摘要。provenance 引用 execution-provenance / 0.1 原件，绑定执行来源材料的字节。该引用只提供身份绑定，生产使用前须另审实际采集格式和可信来源。 |
| 输入、输出、限额 | 引用恰含 role、artifact，按两者字典序严格递增，模式内每角色至多一次。限额恰含 name、unit、value，按 (name, unit) 严格递增，限额名称、单位及必需集合见登记。 |
| 执行结果 | 完成恰为 {kind: completed}，表示取得该模式所需的确定判定或完整推导。中止恰含 kind、code，后者为稳定的诊断标识。候选模式的中止 outputs 为空，伴随观察可随 provenance 保留。 |

kind 与 tool role 按[登记映射](contract.json)检查，每次执行都须持有该 kind 的角色。首版只给 normalize 和 prove 的三个模式定义可接受结果支持。其余登记角色保留精确映射，不能凭角色匹配取得新模式支持。

| 模式 | 完成执行的精确制品角色 |
| --- | --- |
| strict-ir-v0.2 | 输入 candidate。通过时 candidate 和输出 canonical-ir 引用同一 axiom-ir / 0.2 制品。拒绝时 candidate 为原始 ir-candidate。输出始终含 structure-observation，通过时还含 canonical-ir。 |
| core-empty-effects-v0.1 | 输入 canonical-ir、obligation-set（axiom-obligation-set / 0.2）及 generator-source / 0.1，输出 derivation（axiom-core-effect-derivation / 0.1）。 |
| core-field-origin-v0.1 | 输入同 S2，输出 derivation（axiom-core-field-origin-derivation / 0.1）。执行目标是单一输出字段。 |

## 义务、结果和独立核对

合法 IR 的 IR 派生 definitions 完全沿用 P2。checker 从实际 IR 重建全集，并加入实际信任义务。每个 trust 条目对应一个 trust-boundary / trust 定义，其 subject 恰含 kind: trust、category（同 trust definition）、scope（对应 trust ID）。trust 和 uncovered 的 definition 成员见登记。scope 建议使用闭合 {kind, ref}，分别允许引用 subject、artifact、tool、execution、obligation；mitigations 按 (kind, ref) 严格排序并引用实际 artifact 或 execution。scope 的解析及信任类别须在公开规则验收中逐项核对。 [信任规则基线](../axiom-evidence-v0.md#信任与未覆盖项)

| 结果 | 成员与检查 |
| --- | --- |
| S1 checked | execution 引用已完成的严格 normalize，artifacts 是其 inputs / outputs 摘要的有序去重并集。structure-observation（axiom-ir-structure-observation / 0.1）恰为 {kind: accepted, document: <IR 文档 ID>}。 |
| S1 failed | execution 引用已完成的严格拒绝。structure-observation 恰含 kind: rejected、reason 和 location。reason 仅为 noncanonical-ir、invalid-utf8、unknown-top-level-member。前两种 location 恰含 kind: candidate-bytes、offset、length，按原始字节定位。第三种恰含 kind: candidate-member 与单元素 path，元素是被拒绝的顶层成员。 |
| S2 / S3 proved | support 恰含 kind: kernel-replay、execution。引用完成的匹配 prove，其输入 IR 与 subject 相同，P2 全集须独立重建一致，内部 generator 字段匹配 generator-source 原字节摘要。随后按各自规则重演程序根或字段三根及闭包。 |
| unknown | attempts 是非空、严格递增的执行 ID 数组，均绑定同一目标及相符的中止原因。reason 映射见登记。本稿的 unavailable 指已调度后有记录的工具不可用。未确立 subject 时停止装配。 |
| trusted | trust 指向该 trust-boundary 目标对应的实际 trust 项。核心义务仍按 check 或 prove 的规则处理。 |

checked、failed、proved 的 assumptions 是按 trust ID 严格递增的实际依赖。S1 failed 的 counterexample 恰含 kind: structure-path、minimality: {kind: unreduced}、observed: {reason}、空 preconditions、空 worlds 和单项 trace。trace 在 location 的字段上加 artifact 指向原候选。独立路径须复现确定性拒绝和精确定位。可规范化但不规范的候选用首个不同字节或共同前缀结束位置，EOF 可用长度零表示。仅有诊断文本不足以完成支持。

完整结论在首版支持范围内采用以下规则。拒绝分支的结论为 structure_rejected，refs 为结构义务 ID。合法 verification 已具备全义务结果但有真实 unknown 时为 inconclusive，refs 为对应义务 ID。全部期望成立且无必需材料阻断时为 satisfied，refs 为空。缺义务或缺真实执行的装配停在文档形成前。独立 checker 依自身规则核对 P1、P2 与 S1–S3，保留 missing artifacts、剩余 trust 与 TCB。独立结果绑定新 Evidence 原始及文档域摘要，另有自身请求和 checker 身份。现有 v0.1 reader 按原支持集合拒绝本草案版本。 [ADR 0008](../../adr/0008-independent-checker-isolation-and-artifact-exchange.md#独立检查行为) · [ADR 0009](../../adr/0009-axiom-evidence-v0-drift-and-migration.md#决策)

## 本地向量

从仓库根运行：

```bash
python3 -I -B docs/evidence/evidence-v0.2-machine-contract/check_vectors.py
```

脚本复用本仓 Python JCS、P2 与 P3-E/F 对照入口。合成执行来源明确标记，真实 IR / P2 原件沿用冻结材料。三个完整的 S1 拒绝样例固定原始和文档域摘要；S1 通过与预算中止、S2、S3 两字段以单目标投影核对执行及义务 ID。五个投影送入整份文档校验时均因缺全集被拒绝。脚本同时检查 UTF-16 键序、非规范 JSON、重复成员、旧版本和域、错字节或缺制品、错角色、错预算、跨字段换绑、敏感行控制和两项 group 义务分别省略。

[固定摘要](fingerprints.json)由脚本的 --show-fingerprints 输出形成，正常核对只读。草案变化需审阅摘要差异后再更新。向量有意限定为固定材料，未覆盖任意输入读取、实际执行来源认证、完整 P1 独立重建、trust / uncovered 验收或 Evidence 迁移。公共入口、生产装配与独立 checker 仍按审定后的契约实现。
