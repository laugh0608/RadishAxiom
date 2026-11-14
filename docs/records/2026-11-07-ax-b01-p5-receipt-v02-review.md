# AX-B01 P5 公开回执 v0.2 与生产工具接受核对

日期：2026-11-07。基线为 `dev` 的 `4520ce3` 加本批源码。

本记录供回执实现者和工具接受审阅者查阅。范围为 [ADR 0034](../adr/0034-p5-case-receipt-v02.md) 的单案 P5 部分回执，以及上一批本机候选的接受条件核对。

## 实际回执和独立对照

[Rust 入口](../../crates/axiom-ir/src/host_data/execution/receipt.rs)在同一次 P5 执行中组装公开回执。回执绑定实际 IR、任务、规则、工具、夹具、输出、预算及已执行的两个槽位或阻断状态。黄金未执行时没有黄金 attempt。新版 tool、attempt 和 cache key 使用独立域，工具接受、Evidence 与 P6 门控均按[当前公开契约](../../contracts/pipeline-artifacts-v0.2/README.md)编码。

[外部核对脚本](2026-11-07-ax-b01-p5-pairing/verify_receipt.py)通过实际本机示例生成 `base`、`boundary`、`invalid`、预算不足、缺少黄金、错案黄金和恰好满足预算的七份回执。Python 路径用固定 AX-B01 原始材料独立重建规范字节及各版本域 ID，逐字节核对并检查 JSON Schema。Rust 读回入口用原始材料验证七份回执，拒绝重算摘要及 ID 的跨案黄金替换、工具角色替换、工具接受升级、门控篡改和旧版输入。既有公开 v0.1 契约与回归入口保持原字节。Python 路径只覆盖指定样本，Rust 自身重建提供记录一致性检查。

```bash
cargo +1.97.1-aarch64-apple-darwin build --package radishaxiom-ir --example record_p5_fixture --locked --offline
python3.14 -I -B docs/records/2026-11-07-ax-b01-p5-pairing/verify_receipt.py target/debug/examples/record_p5_fixture
```

可在已有 JSON Schema 验证器的环境中加 `--schema contracts/pipeline-artifacts-v0.2/schemas/axiom-pipeline-receipt.schema.json`。本批使用本机已有的验证器执行了这一步。

## fixture-checker 接受条件

结论为 `not-accepted`。核对对象是上一批已留存的 [候选记录](2026-11-07-ax-b01-p5-pairing/case-tool-candidate.jcs)。新回执测试构建产生了自己的本机可执行制品，两者均无生产工具接受记录。

| 条件 | 实际证据及剩余项 |
| --- | --- |
| 源、规则、二进制身份 | 用 `git show 4520ce3:<path>` 对回冻结清单的全部 86 项。留存二进制长度 4,470,608 bytes 与 `sha256:f8bd89af3a9c844c35098b81493b296cc149d33bdf0b9e6a59d25aed2b1c2ec3` 匹配。规则和私有工具 ID 已绑定，生产登记须对实际选择的发布候选重新核定身份 |
| 构建工具与目标环境 | 本机 Rust `1.97.1` 的 Cargo、rustc 文件匹配候选记录。候选是 Darwin arm64 Mach-O，`otool -L` 只列直接依赖 `/usr/lib/libSystem.B.dylib`。仍须记录实际生产 target/profile、有效链接器和 SDK、Rust 标准库及加载边界，明确哪些由生产宿主保证 |
| 权利、来源与分发范围 | 源集合含仓库许可证及锁定构建材料。实际生产二进制所含组件的来源、许可归属及拟分发范围仍需针对所选制品登记，直接 Mach-O 依赖表不足以覆盖这些内容 |
| 行为与独立复核 | 本地候选已有七次同案执行和错案替换拒绝。新版回执路径另有七次实际记录及独立字节对照。生产候选还须重跑选定 profile 的拒绝矩阵并明确独立复核适用范围 |
| 正式接受 | 需要绑定确切制品、来源与规则、`fixture-checker` role、目标、调用与适用限制的接受记录及外部受信 pin。现有工具登记没有这份接受，回执中的 `tool.acceptance` 保持 `not-accepted` |

确认生产构建与运行边界后，再决定可接受的制品和适用范围。现有回执仅报告实际 P5 阶段，P6 仍受原门控约束。
