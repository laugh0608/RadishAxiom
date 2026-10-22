# IR v0.2 兼容与拒绝材料

本目录对应 [ADR 0017](../../../../../docs/adr/0017-ir-v0.2-support-boundaries-and-migration.md)、[IR v0.2](../../../../../docs/ir/axiom-ir-v0.2.md) 与[迁移规则 1](../../../../../docs/ir/ir-v0.1-to-v0.2-migration.md)。材料全部为自有合成或既有合成候选；没有真实业务输入，也不构成 Evidence、证明或运行许可。

## 独立来源与留存

[生成器](../../../../../scripts/generate-ir-v02-vectors.py)仅用 Python 标准库和既有独立 JCS helper，不调用 Rust parser、normalizer、类型推导或迁移器，不读取 expected outcome 决定成功。目标按声明依赖递归重建并记忆，Rust 生产迁移使用已验证图的拓扑队列；两者分别重新规范化因类型 ID 改变而排序变化的表达式。

生成与一致性检查：

```bash
python3 scripts/generate-ir-v02-vectors.py
python3 scripts/generate-ir-v02-vectors.py --check
```

生成器核对两端语义原文、Rust pin 和规范绑定；`--check` 已接入仓库检查。它只写本目录，不覆盖任何旧候选或旧规范。当前规则名为 `axiom-ir-0.1-to-0.2`，版本为 `1`；组件工具为 `radishaxiom-ir 0.0.0`，归档实际迁移还须记录具体构建 / 仓库修订。

## 迁移对照

- `migrations.tsv` 无表头，七列为案例名、仓库相对源路径、本目录相对目标路径、源文档域 ID、目标文档域 ID、源文件 SHA-256、目标文件 SHA-256。20 份源包含四题 12 个 candidate、七份独立完整文档及一份摘要同拼写文本的专用源。
- `mappings.tsv` 无表头，四列为案例名、内容类别、源 ID、目标 ID。类别顺序为 enum-type、record-type、table-type、node、contract，每类按源 ID 排序；完整文档 ID 另见上一清单。
- `migrated/` 是逐字节目标期望；保留 wrong 算法的结构，不伪造验证失败。
- `references-source.jcs` / `preserved-text.txt` 将合法旧 ID 放进端口名、输出名和 Text 字面量，确认只重写引用位置；新增枚举使重绑前后的 and 子式排序确实改变。

Rust [迁移回归](../../migration.rs)对每份源执行 strict 检查和真实迁移，核对全部字节、每项映射、两端文档域及文件摘要，再经目标 normalizer / strict 重验。非法、非规范、资源不足或错误源版本不得生成成功结果；v0.2 输入不作为幂等迁移成功。

## 记录构造与负例

`records.jcs` / `records-input.json` 是同一 v0.2 抽象文档的规范 / 乱序表示，覆盖四种记录声明、map、嵌套记录与 Option、契约量词 / match 绑定、公开字段读取及敏感兄弟字段。字段与布尔子式的重排、去重期望由明确结构给出。`records-document-id.txt`、`record-ids.tsv` 保存独立身份；`record-expressions.tsv` 五列为名称、原表达式 JSON、期望规范 JSON、类型 JSON、保守标签。

`negative.tsv` 的三列为相对文件名、内部诊断类别、原输入 JSON Pointer；18 份 `negative/` 文档覆盖缺失 / 重复 / 未知字段、额外成员、旧 value 拼写、错型、悬空记录、无字段绑定、读取公开字段时隐藏的坏子式、三层记录相等边界、记录连接、复杂同值键，以及版本 / 语义混搭。语义负例独立重算被修改 definition 的 ID，避免旧摘要先失败而掩盖所需拒绝。诊断类别是本组件测试约定，不新增公共 pipeline 错误协议。

额外[组件回归](../../../src/version/tests.rs)覆盖声明标签、嵌套构造、深度和输入预算、两版本诊断差异，以及 5,000 层记录引用和 5,000 层节点链的迁移。压力输入的生产摘要 helper 只构造输入，不作为独立身份期望。

本材料可用于后续独立实现对照；尚未导入或执行真实 Go checker，也未验证其他平台。新 IR 身份不能复用旧 Evidence / bundle 的结果。
