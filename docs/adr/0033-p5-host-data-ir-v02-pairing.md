# ADR 0033：P5 宿主封套与 IR v0.2 的版本配对

日期：2026-11-07。状态：Accepted。项目所有者接受本 ADR 并要求推进实现。

本文定义 AX-B01 的 P5 封套配对和生产 `check-fixture` 的绑定要求，供管线、宿主与独立复核实现者使用。范围限于 [ADR 0032](0032-ax-b01-p5-component-entry.md) 已接受的具体检查能力。完整 receipt、Evidence 迁移、生成器和执行器各有自己的验收入口。

## 背景

[现行制品契约](../../contracts/pipeline-artifacts-v0.1/README.md)固定 IR v0.1、宿主封套 v0.1 和 receipt v0.1。旧封套的 `ir_document_digest` 只提供摘要词法，旧结构检查器无法从它识别 IR 版本。旧 receipt 又明确拒绝 IR v0.2。原封套仅换摘要会产生形状合法但版本关系未经确认的字节。[旧读取器实测及新旧对照](../records/2026-11-07-ax-b01-p5-pairing-review.md)

## 版本配对

- 接收 `axiom-ir` `0.2` 的实际 canonical 字节和 `axiom-benchmark-data` `0.1` 原始字节，产生 `axiom-host-data` `0.2`。保留原五个字段 `format`、`format_version`、`ir_document_digest`、`role`、`tables`，由新版本值区分配对。旧 v0.1 字节、配对和拒绝规则继续按现行契约解析。
- `ir_document_digest` 是 `axiom-ir-v0.2:document` 域加 NUL 和 canonical IR 字节的 SHA-256。IR、夹具和宿主封套的制品引用各使用各自原始字节 SHA-256。接收端须取得实际 IR，分别重算制品摘要和文档 ID，并核对精确版本和角色。
- `role` 沿用 `input` / `output`。表按接口名、行按 IR 主键的 Unicode scalar 规则排列，JSON object 成员按 JCS 的 UTF-16 顺序。使用 UTF-8，禁止 BOM、前后空白和末尾 LF。首批值范围沿用 ADR 0032，黄金封套的数据来自已经过输出模式核验的原黄金夹具。
- 使用新封套的 P5 producer 和 P7 / P8 consumer 须分别声明支持的配对。旧 receipt / Evidence 格式和旧 Node profile 的验收记录继续适用于各自范围。后续为 IR v0.2 定义 receipt 配对与 Evidence 接续时按 [ADR 0009](0009-axiom-evidence-v0-drift-and-migration.md) 审阅。

## 生产 `check-fixture` 的绑定

每次转换绑定一个实际 case 和一种原始数据角色。输入和黄金输出分别记录执行，按所选 case 关联。P5 接受的角色和制品引用如下。

| 项目 | 绑定要求 |
| --- | --- |
| 选择及输入 | 绑定实际 `canonical-ir`、`benchmark-task` 清单和其所选 case 的原始夹具。使用清单核对任务、case、`input` 或 `golden` 槽位、原始角色与摘要。所选 case 和槽位进入 options，期望结论只用于外部验收 |
| 执行身份 | `kind=check-fixture`、已登记实际工具身份和 `fixture-checker` role，绑定配对规则、options 及检查和序列化上限。封套编码的字节上限与 ADR 0032 内部表值的输出预算分别记录 |
| 成功输出 | 输入转换引用一个 `host-input`，黄金转换引用一个 `golden-host-output`。两者均绑定真实封套的版本、长度和原始摘要。P8 用黄金封套比对 P7 实际输出 |
| 失败记录 | 记录原执行和稳定原因，失败的转换无宿主输出。绑定正确的实际输入违反 Pre 等具体条件可记录 P5 `invalid`。黄金制品不符模式、摘要或版本错配属于操作错误。预算不足记 `resource-exhausted`，能力不足记 `unsupported` |

同一 case 的必要转换均通过才可把 P5 记为完成，其他 case 的完成记录不可替代。可复用执行还须匹配精确 IR、清单、夹具、case、角色、工具、规则、options 和 limits。独立复核应重新检查原数据和转换字节，不能仅凭自报摘要承认成功。将具体拒绝纳入 Evidence `failed` 仍须关联可重放见证及实际完成的检查。操作错误或耗尽只进入规范允许的 `unknown` 或操作记录。P6 的义务、信任、assurance 和输入门控继续按 [ADR 0007](0007-first-verification-first-compilation-pipeline.md#验证门控)判断。

## 验收入口

按 [AX-B01 对照](../records/2026-11-07-ax-b01-p5-pairing-review.md)核对 `base`、`boundary` 的四份封套和旧版回归。组件验收覆盖 Unicode 字段名与主键的两种顺序、封套序列化预算边界、`invalid`、资源耗尽、同案不同角色以及重新计算外层摘要的错配。任一必要身份缺失、序列化中断或复算不一致时停止产生成功输出。生产验收另须接入实际工具身份、执行记录及独立重建。
