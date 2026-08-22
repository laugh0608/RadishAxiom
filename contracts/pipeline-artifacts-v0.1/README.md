# Pipeline Artifact Contract v0.1

本目录是 [ADR 0007](../../docs/adr/0007-first-verification-first-compilation-pipeline.md) 的首批机器物化，并绑定现行首域语义、Axiom IR v0.1、Axiom Evidence v0.1 与 [Toolchain & Adapter Identity Registry v0.1](../toolchain-adapters-v0.1/README.md)。它固定：

- `axiom-obligation-set` `0.1`、`axiom-host-data` `0.1` 与 `axiom-pipeline-receipt` `0.1` 的闭合 JSON Schema；
- `cvc5-1.3.4-qf-uflia-v0.1` 下 SMT query 的 ASCII / LF 原始字节配置；
- `node-24-esm-keyed-finite-table-v0.1` 下 target module 的 UTF-8 / LF 原始字节配置；
- P0–P9 stage、attempt、tool、artifact、cache key、verification gate 与 final outcome 的内容身份规则；
- 一个 gate 打开的完整 receipt 与一个 cvc5 timeout、gate 阻断 P6–P8 的合法 partial receipt；
- 38 个结构、规范字节、顺序、版本、profile、tool、cache、gate 与 `not-run` 阻断关系负例及其稳定期望码。

`schemas/` 使用 [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12) 描述三类抽象 JSON 结构。JSON Schema 不验证原始字节是否 canonical、义务 / attempt / cache 的域摘要、数组规范顺序、tool 引用、gate 聚合或 stage 依赖；这些跨字段规则由本契约、黄金 fixture 和生成器共同固定，未来生产实现和独立 checker 仍须各自实现，不能把本生成器作为运行时依赖。

SMT query 和 target module 是原始文本制品，不伪装成 JSON Schema。当前生成器只验证首批 fixture 所需的可审阅字节配置和禁止项；它不是 SMT-LIB parser、ECMAScript parser、cvc5 adapter、Node launcher 或语义验证器。`policy.jcs`、`options.jcs` 与 `tool.txt` 是 receipt 身份闭合所需的合成支持制品，不代表完整 options / limits 公共契约已经冻结。

生成：

```bash
python3 scripts/generate-pipeline-artifact-contracts.py --write
```

只读校验：

```bash
python3 scripts/generate-pipeline-artifact-contracts.py --check
```

除本 README 外，本目录文件均由生成脚本维护，不接受手工修改。`.jcs`、`.smt2`、`.mjs` 和 `tool.txt` 的字节终止方式由各自 profile 固定；`contract.json`、schema 与 `fixtures/expected.json` 是带末尾换行的人类审阅 JSON。

本批 fixture 只使用 ASCII 合成值，并借用 AX-B01 的一个既有 canonical IR 身份形成最小结构切片。它不证明义务集合对 AX-B01 完整，不执行 solver 或 target，不生成完整 Axiom Evidence，也不覆盖 AX-B02–AX-B04、八个错误候选、host mismatch、artifact 篡改、certificate policy、进程崩溃或六平台字节一致性；这些由后续 checker bundle 与跨实现矩阵承载。
