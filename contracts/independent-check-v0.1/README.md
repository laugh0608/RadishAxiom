# Independent Check Contract v0.1

本目录是 [ADR 0008](../../docs/adr/0008-independent-checker-isolation-and-artifact-exchange.md) 的首批机器物化，固定：

- `axiom-check-request` `0.1`；
- `axiom-check-bundle-manifest` `0.1`；
- `axiom-independent-check-result` `0.1`；
- request / manifest / check / result 的域摘要；
- 一组可离线复算的严格 Evidence 拒绝 bundle；
- request、manifest 和 result 的结构、顺序、身份与聚合负例。

`schemas/` 使用 [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12) 描述抽象 JSON 结构。JSON Schema 不验证原始字节是否为 JCS、数组是否按项目规范排序、域摘要、artifact byte length / digest、check ID 或四态聚合；这些跨字段规则由本契约、黄金 fixture 和生成器共同固定，未来 checker 仍须独立实现，不能把本生成器作为运行时依赖。

`fixtures/strict-evidence-rejection/` 使用 canonical request 和 manifest 包装一个内容为 `{}` 的合成 Evidence blob。该 Evidence 故意缺少 v0.1 必需字段，预期独立结果是绑定原始字节的 `rejected`；fixture 不声称已经存在完整 production Evidence、证明证书或 checker 执行。

生成：

```bash
python3 scripts/generate-independent-check-contracts.py --write
```

只读校验：

```bash
python3 scripts/generate-independent-check-contracts.py --check
```

除本 README 外，本目录文件均由生成脚本维护，不接受手工修改。`.jcs` 与 blob 没有末尾换行，这是规范机器字节要求；schema、目录清单和负例索引是带末尾换行的人类审阅 JSON。

为避免依赖不完整的 Python JCS 近似，本批生成器有意只生成 ASCII fixture；它不覆盖合法非 ASCII scalar、UTF-16 member 排序或完整 RFC 8785 向量。当前也不包含完整 Axiom Evidence 正例、义务重建、counterexample / concrete replay、certificate checker、生产工具制品或六平台运行结果。这些仍由当前状态中的后续实现就绪批次承载。
