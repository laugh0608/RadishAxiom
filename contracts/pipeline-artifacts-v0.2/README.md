# Pipeline Receipt v0.2 的 P5 范围

依据 [ADR 0034](../../docs/adr/0034-p5-case-receipt-v02.md)支持 `benchmark-node24` 下单一 case 的 P5 部分回执。生成和精确材料重建入口是 Rust 的 [record_p5_receipt / check_p5_receipt](../../crates/axiom-ir/src/host_data/execution/receipt.rs)，仓库中的 `record_p5_fixture` 示例提供本地调用入口。[结构 schema](schemas/axiom-pipeline-receipt.schema.json)手工维护，结构检查用于配合原始材料重建。旧 v0.1 契约按自身版本读取。

机器字节使用 IR v0.2 同一规范 JSON 编码，字符串按 UTF-8 写入，对象字段按 UTF-16 排序，整数和长度为十进制字符串，正文无 BOM、额外空白或末尾 LF。摘要字段为小写 `sha256:` 加 64 位十六进制。引用制品的 SHA-256 对实际原始字节计算，`ir.document_id` 则是 IR 的文档域 ID。

| 回执部分 | 绑定 |
| --- | --- |
| `ir` | 实际 canonical IR v0.2 制品、文档 ID 和精确语义摘要 |
| `artifacts` | 按 `content_digest` 排序的实际 IR、清单、规则、工具、已尝试的夹具及成功输出。每个摘要只有一个长度和格式描述 |
| `tool` | 实际制品、不可变修订和 `fixture-checker` 角色。观察路径为 `not-accepted`，显式接受路径附外部受信接受记录引用 |
| `attempts` | 实际输入执行优先，随后是已执行的黄金检查。输入引用的角色固定为 `benchmark-task`、`canonical-ir`、`fixture`，输出角色为对应的 `host-input` 或 `golden-host-output` |
| `p5` | case、实际清单、按执行顺序排列的 attempt ID 和阶段结果。黄金缺失或预检失败时保留输入 attempt，黄金不占 attempt |
| `outcome` | P5 同案两槽成功为 `partial`，其余为 `blocked`。当前 `evidence.kind` 为 `not-assembled`，门控为 `closed` / `p6-not-evaluated` |

内容 ID 的公式为 `SHA-256(domain || NUL || canonical JSON)`。工具 ID 使用 `axiom-pipeline-v0.2:tool` 和完整 `tool.definition`。attempt ID 使用 `axiom-pipeline-v0.2:attempt` 和完整 attempt definition。cache key 使用 `axiom-pipeline-v0.2:cache-key`，基于 attempt 的 `inputs`、`kind`、`limits`、`options`、`rule`、`tool` 六个字段。cache key 记录等价输入，当前入口每次实际执行转换。

重建从调用方已绑定的工具、canonical IR、清单、case、夹具字节和预算出发。先核对待查回执的长度和原始摘要，再从同一请求重建并比较完整字节。篡改后重新散列也须通过该比较。该入口检查记录与执行重建的一致性，历史执行来源另有观察证据。本机观察的结果、独立样本对照及生产接受条件见[实际核对记录](../../docs/records/2026-11-07-ax-b01-p5-receipt-v02-review.md)。

## P5 工具接受记录 v0.1

`record_p5_receipt_with_acceptance` 与 `check_p5_receipt_with_acceptance` 要求调用方从受信配置取得接受记录的原始 SHA-256，同时提供接受记录和构建来源原字节。回执、随回执分发的材料及执行者自报的摘要均不能提供这个信任根。接受记录上限为 8 KiB，构建来源上限为 1 MiB，两者均须非空。来源由批准者事前审阅，运行时按接受记录校验其原始字节摘要。

接受记录采用上文的规范 JSON 编码，成员恰为下表所列。实现从调用参数和固定契约独立重建完整记录，校验摘要与规范原字节后才执行 P5。

| 成员 | 值 |
| --- | --- |
| `format`、`format_version` | `axiom-p5-tool-acceptance`、`0.1` |
| `artifact`、`tool` | 实际可执行制品的原始 SHA-256 与回执 v0.2 工具域 ID |
| `target`、`build_profile`、`invocation` | `aarch64-apple-darwin`、`release`、`record-p5-fixture-cli-v0.1` |
| `pipeline_profile`、`role` | `raxc-keyed-finite-table-pipeline-v0.2`、`fixture-checker` |
| `rule`、`ir`、`task`、`provenance` | 固定 P5 规则、实际 canonical IR、实际任务清单、经批准的构建来源各自的原始 SHA-256 |
| `limits` | [Darwin release 固定预算](../../crates/axiom-ir/src/host_data/execution/receipt/acceptance.rs)，与 attempt 使用同一结构。调用可降低 `envelope_bytes`，其余上限必须精确匹配 |

通过后，`tool.acceptance` 为 `{"artifact":"sha256:…","kind":"accepted"}`。回执登记 `axiom-p5-tool-acceptance` 与 `radishaxiom-p5-darwin-build` v0.1 制品，后者由接受记录的 `provenance` 引用。接受状态独立于每次尝试的结果，工具 ID、attempt ID 和 cache key 的定义保持原样。原入口继续生成相同的 `not-accepted` 字节，并拒绝含接受声明的回执。v0.1 契约继续使用各自版本。

本机示例在 Darwin arm64 release 上提供 `receipt-accepted` 和 `receipt-check-accepted`。参数沿用各自的 `receipt` / `receipt-check`，末尾依次附 `ACCEPTANCE_FILE TRUSTED_ACCEPTANCE_SHA PROVENANCE_FILE`。批准者还须保证受保护路径上的制品就是实际启动的制品，宿主及加载边界满足审批范围。示例的自读和库的字节重建只检查所提供材料与执行结果的一致性，生产批准和启动来源由调用方负责。工具接受不会改变 P6 门控、Evidence 状态或独立 checker 的接受范围。
