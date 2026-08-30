# 实现就绪契约

`contracts/` 保存由已接受规范和 ADR 物化出的版本化机器契约、canonical fixture、负向样例与黄金摘要。这里的文件用于跨实现交换和进入实现前验收，不是生产编译器或独立 checker 源码。

当前契约：

- [Independent Check Contract v0.1](independent-check-v0.1/README.md)：ADR 0008 的 request、bundle manifest、独立 result、摘要和结构拒绝样例。
- [Execution Profile Contract v0.1](execution-profiles-v0.1/README.md)：cvc5 / Node / Go checker 的允许 invocation、职责分离 limits、进程结果边界和空 certificate 能力矩阵。
- [Toolchain & Adapter Identity Registry v0.1](toolchain-adapters-v0.1/README.md)：ADR 0004–0008 的精确工具版本、六平台候选制品、官方元数据、供应链停止线与 profile 身份。
- [Toolchain Payload Acceptance v0.1](toolchain-payload-acceptance-v0.1/README.md)：逐 payload 绑定 publisher / 项目摘要、只读 archive 观察、vendor / 许可证清单、签名状态与受限最终 acceptance；当前仅接受 Go `go1.26.7` macOS arm64 host 与 source。
- [Checker Runtime Payload Registration v0.1](checker-runtime-payloads-v0.1/README.md)：绑定 checker source、target、artifact / provenance / acceptance、候选 / durable provider、字节 retention / fetch 与登记状态机；当前 source 的 distribution package 已完成临时候选直传与独立回读，GitHub immutable releases 设置已只读确认关闭且 Release 未物化，active runtime 为 0。
- [Pipeline Artifact Contract v0.1](pipeline-artifacts-v0.1/README.md)：ADR 0007 的 obligation set、host data、SMT query、target module、pipeline receipt、gate / cache / partial failure 结构与负例。
- [Implementation Readiness Contract v0.1](implementation-readiness-v0.1/README.md)：统一四题 benchmark、P0–P9、gate / cache / receipt、Evidence、独立检查与实现停止线的版本化场景矩阵。
- [Keyed Finite Table Checker Bundle Contract v0.1](keyed-finite-table-checker-bundles-v0.1/README.md)：把 readiness 稳定场景 ID 物化为 20 个完整 benchmark bundle、5 个跨契约 bundle、3 个缺失 / 篡改 / 省略负例及独立预期结果。

每个子目录必须说明规范来源、生成入口、手工维护边界和仍未覆盖的语义。生成文件不得手工修改，也不得因 schema 校验通过就声称完整 Evidence 已被独立复核。
