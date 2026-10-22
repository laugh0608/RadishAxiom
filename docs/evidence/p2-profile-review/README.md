# P2 profile 审阅配套材料

状态：审阅范围已按 [ADR 0018](../../adr/0018-ir-derived-obligation-profile.md) 接受；[审阅正文](../p2-obligation-profile-review.md)保留决策过程。本目录为审阅与兼容预览，生产组件使用的正负例另见[版本化材料](../../../contracts/ir-derived-obligations-v0.2/README.md)。本目录不是 Evidence、完整迁移结果或独立 checker 观察。

## 文件与来源

| 文件 | 内容 |
| --- | --- |
| [cases.json](cases.json) | 21 份已经过 P1 验收的合成 v0.2 IR 路径、原始字节 / 文档摘要、按类别数量；绑定提案与生成器原文字节 |
| [obligations.tsv](obligations.tsv) | 无表头，三列：case、拟定 obligation ID、definition JCS；每个 case 内按 ID 排序 |
| [negative-cases.json](negative-cases.json) | 对指定基线清单的 14 份变异配方；replacement 的 ID 按改后 definition 重算，摘要负例除外；拒绝描述不是公共诊断码 |
| [group-separation.json](group-separation.json) | 7 份有限数学区分例；key 是分组键，合成 source 列表不是带完整主键 / 类型的机器输入 world，不能直接作为 Evidence 见证 |
| [role-cases.json](role-cases.json) | 8 个 kind / role 正例和 2 个 role 不匹配例；不表示工具实际执行 |
| [compatibility.json](compatibility.json) | 四题 12 份旧 bundle 核心 ID 与拟定新核心 ID 清单、精确源 blob 路径 / 摘要；不导出旧 result，也不声称逐路径一一映射 |

所有输入为项目自有合成材料。21 份输入包括四题 12 候选、七份独立完整文档、引用同拼写字符串专用源的迁移结果，以及 v0.2 记录构造文档。范围位置由合成 IR 的规范 definition 遍历得到；数量按正文位置表人工复核，生成器固定逐例总数。

兼容预览实际读取锁定 v0.1 bundle 的 Evidence 字节，核对 raw / document / obligation 身份，只提取核心 definition。它不检查全部旧 result 支持、反例重放、trust 或结论真值，因此不是严格 Evidence 迁移器。所有旧 / 新核心 ID 不同；旧状态、证明、缓存、许可和独立结果不得因清单数量相同而转移。

## 生成与验证边界

```bash
python3 scripts/generate-p2-profile-review.py
python3 scripts/generate-p2-profile-review.py --check
```

[生成器](../../../scripts/generate-p2-profile-review.py)使用 Python 标准库及已有独立 JCS helper，不调用 Rust 生产 helper、不运行外部工具、不读取 expected outcome 决定拟定义务或有限目标真假。写本目录及版本化 P2 材料目录，旧候选、bundle、规范与身份保持不变。

`--check` 复核输入身份、21 份清单的数量 / 唯一性 / 生成一致性、14 个变异配方确实改变基线、7 个手工真值区分例和 10 个角色对照。它不执行 Rust P2 拒绝入口；Rust 测试另外实际消费版本化正负例，不能把本脚本返回零当作组件完成。仓库检查调用该模式。

修改提案或生成器后重新生成材料，不能手工修补 JSON / TSV 以通过一致性检查。角色表和完整迁移计划的接受与执行边界以正文及 ADR 0009 / 0016 为准。
