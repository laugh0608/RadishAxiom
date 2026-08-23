# 实现就绪契约

`contracts/` 保存由已接受规范和 ADR 物化出的版本化机器契约、canonical fixture、负向样例与黄金摘要。这里的文件用于跨实现交换和进入实现前验收，不是生产编译器或独立 checker 源码。

当前契约：

- [Independent Check Contract v0.1](independent-check-v0.1/README.md)：ADR 0008 的 request、bundle manifest、独立 result、摘要和结构拒绝样例。
- [Toolchain & Adapter Identity Registry v0.1](toolchain-adapters-v0.1/README.md)：ADR 0004–0008 的精确工具版本、六平台候选制品、官方元数据、供应链停止线与 profile 身份。
- [Pipeline Artifact Contract v0.1](pipeline-artifacts-v0.1/README.md)：ADR 0007 的 obligation set、host data、SMT query、target module、pipeline receipt、gate / cache / partial failure 结构与负例。
- [Implementation Readiness Contract v0.1](implementation-readiness-v0.1/README.md)：统一四题 benchmark、P0–P9、gate / cache / receipt、Evidence、独立检查与实现停止线的版本化场景矩阵。

每个子目录必须说明规范来源、生成入口、手工维护边界和仍未覆盖的语义。生成文件不得手工修改，也不得因 schema 校验通过就声称完整 Evidence 已被独立复核。
