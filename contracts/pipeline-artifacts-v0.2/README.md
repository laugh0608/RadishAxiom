# Pipeline Receipt v0.2 的 P5 范围

依据 [ADR 0034](../../docs/adr/0034-p5-case-receipt-v02.md)支持 `benchmark-node24` 下单一 case 的 P5 部分回执。生成和精确材料重建入口是 Rust 的 [record_p5_receipt / check_p5_receipt](../../crates/axiom-ir/src/host_data/execution/receipt.rs)，仓库中的 `record_p5_fixture` 示例提供本地调用入口。[结构 schema](schemas/axiom-pipeline-receipt.schema.json)手工维护，结构检查用于配合原始材料重建。旧 v0.1 契约按自身版本读取。

机器字节使用 IR v0.2 同一规范 JSON 编码，字符串按 UTF-8 写入，对象字段按 UTF-16 排序，整数和长度为十进制字符串，正文无 BOM、额外空白或末尾 LF。摘要字段为小写 `sha256:` 加 64 位十六进制。引用制品的 SHA-256 对实际原始字节计算，`ir.document_id` 则是 IR 的文档域 ID。

| 回执部分 | 绑定 |
| --- | --- |
| `ir` | 实际 canonical IR v0.2 制品、文档 ID 和精确语义摘要 |
| `artifacts` | 按 `content_digest` 排序的实际 IR、清单、规则、工具、已尝试的夹具及成功输出。每个摘要只有一个长度和格式描述 |
| `tool` | 实际候选制品、不可变修订、`fixture-checker` 角色。当前支持的工具接受值为 `not-accepted` |
| `attempts` | 实际输入执行优先，随后是已执行的黄金检查。输入引用的角色固定为 `benchmark-task`、`canonical-ir`、`fixture`，输出角色为对应的 `host-input` 或 `golden-host-output` |
| `p5` | case、实际清单、按执行顺序排列的 attempt ID 和阶段结果。黄金缺失或预检失败时保留输入 attempt，黄金不占 attempt |
| `outcome` | P5 同案两槽成功为 `partial`，其余为 `blocked`。当前 `evidence.kind` 为 `not-assembled`，门控为 `closed` / `p6-not-evaluated` |

内容 ID 的公式为 `SHA-256(domain || NUL || canonical JSON)`。工具 ID 使用 `axiom-pipeline-v0.2:tool` 和完整 `tool.definition`。attempt ID 使用 `axiom-pipeline-v0.2:attempt` 和完整 attempt definition。cache key 使用 `axiom-pipeline-v0.2:cache-key`，基于 attempt 的 `inputs`、`kind`、`limits`、`options`、`rule`、`tool` 六个字段。cache key 记录等价输入，当前入口每次实际执行转换。

重建从调用方已绑定的工具、canonical IR、清单、case、夹具字节和预算出发。先核对待查回执的长度和原始摘要，再从同一请求重建并比较完整字节。篡改后重新散列也须通过该比较。该入口检查记录与执行重建的一致性，历史执行来源另有观察证据。本机观察的结果、独立样本对照及生产接受条件见[实际核对记录](../../docs/records/2026-11-07-ax-b01-p5-receipt-v02-review.md)。

目前公开契约只装配 P5 的实际尝试，生产工具接受、其余阶段、恢复、Evidence 装配和独立 checker 验收仍待各自的实现及接受。
