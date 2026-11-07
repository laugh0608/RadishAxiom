# ADR 0034：IR v0.2 管线回执的 P5 用例关联

日期：2026-11-07。状态：Proposed。

本文供管线实施者、回执消费者和独立复核者评审 IR v0.2 的回执版本与 P5 用例绑定。范围是 P5 的输入和黄金数据检查、失败归因及向后续阶段交接。完整 P0–P9、Evidence 迁移、公开工具接受和宿主执行各按其契约验收。

## 背景

[ADR 0033](0033-p5-host-data-ir-v02-pairing.md)接受 IR v0.2 与宿主封套 v0.2 的配对，要求分别绑定同一用例的输入与黄金转换。[既有 receipt v0.1](../../contracts/pipeline-artifacts-v0.1/README.md)固定 IR v0.1 和 Evidence v0.1，阶段结果还要求与最后一次 attempt 一致。新用例关联需要同时检查两个不同槽位，且可能在第二次实际执行前缺少材料。旧读取器的版本和阶段规则不能表达这些差异。

## 拟议版本边界

- 新配对使用 `axiom-pipeline-receipt` v0.2、`raxc-keyed-finite-table-pipeline-v0.2`、IR v0.2 和 `axiom-host-data` v0.2。首批审阅范围为 `benchmark-node24` 模式的 P5 接续。旧 profile、回执、schema、生成器和规范字节各按原规则读取，跨版本默认拒绝。
- 回执绑定实际 IR 制品 SHA-256、IR 文档域 ID 和语义摘要。采用明确的 Evidence 关联状态。没有 Evidence 时记 `evidence: {kind: "not-assembled"}`，只有独立的 Evidence 版本审阅完成后才定义精确制品引用。遵守 [ADR 0009](0009-axiom-evidence-v0-drift-and-migration.md)，旧 `checked`、`proved` 或 `trusted` 结果不随回执迁移。
- 新回执的 tool、attempt 和 cache key 各自使用版本化的管线域。工具 ID 建议用 `axiom-pipeline-v0.2:tool`，attempt 与 cache key 对应 `axiom-pipeline-v0.2:attempt` 和 `axiom-pipeline-v0.2:cache-key`。私有观察的工具 ID、历史 Evidence 工具 ID 和新版回执身份分别重算，不能按同名工具或相同制品摘要替换 ID。

## P5 记录与交接

每个 case 以 canonical IR 制品及文档 ID、任务清单原始摘要和用例名确定身份。阶段通过有序引用关联实际 `check-fixture` attempt，输入先于黄金。attempt 记录槽位、所消费的原始制品、实际工具及其 `fixture-checker` role、规则摘要、options、limits、结果及真实输出。case 汇总引用这些定义，避免另存一份可独立编辑的工具和结果。

只有同一 case 下两个必要槽位都完成，且实际输入、清单、规则、工具、预算及各自输出均能按精确绑定复核时，P5 才能交接一对封套。P6 仍检查 [ADR 0007](0007-first-verification-first-compilation-pipeline.md#验证门控)的完整义务、trust 和 assurance 条件。各种未完成路径须分别表示。

| 情形 | 应保留的记录 |
| --- | --- |
| 输入未通过 | 真实输入 attempt 及其原因，黄金无 attempt |
| 输入通过、黄金缺失或预检失败 | 已完成输入 attempt 及其封套，黄金槽位阻断，case 无可交接封套对 |
| 黄金执行失败 | 保留输入与黄金两个真实 attempt，黄金无输出，case 记录其具体原因 |
| 输入及黄金通过 | 同案的两个实际执行与两个精确输出引用 |

若后续允许恢复，新的 attempt 绑定实际执行与顺序，旧失败记录保留。不能用同一文件名、最近一次执行或另一 case 的黄金结果补齐。资源耗尽、未尝试和实际输入拒绝分别处理。仅有私有记录、未验证工具身份或缺失原始制品时，生产回执的相应部分仍未完成。

## 实施与验收入口

本批使用 [私有用例记录与独立重建](../records/2026-11-07-ax-b01-p5-case-review.md)评估上述关联。接受版本边界后，再物化 v0.2 回执规范、格式检查器及生成入口，并用正式工具接受记录绑定生产身份。验收至少覆盖 `base` / `boundary`、`invalid`、资源耗尽、黄金缺失和预检失败、跨版本、角色错配、篡改后重新计算摘要的跨 case 替换，以及旧版字节回归。独立路径依据固定源制品重建结果。完整回执和 Evidence 的接受继续遵循各自标准。
