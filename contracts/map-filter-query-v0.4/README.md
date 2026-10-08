# map / filter query v0.4 独立验收材料

对应 [ADR 0022](../../docs/adr/0022-map-filter-row-coverage.md)与 [v0.4 规则](../../docs/query/map-filter-query-v0.4.md)。本目录服务有限动态检查和旧版兼容，不是 solver、Evidence 或证明材料。

## 生成与独立观察

`cases.json` 保存 60 文档、336 个 P2 目标及 12,553 个目标 / 世界赋值，复用 v0.3 全部 57 文档、243 目标及原世界。新增 select-none、wrong-business-predicate 和 composite-key-permutation 三份规范 IR；最后一份使用两整数键的重命名及键序置换，错误映射不能仅靠排序类型不匹配暴露。AX-B01 三候选保持原始完整容量。

`scripts/generate-p3-coverage-vectors.py` 生成规范输入、独立具体期望和 `coverage_observations`。`p3_coverage_semantics.py` 从实际 IR 的直接来源、字段投影、谓词及具体表达式计算 Ready、被选中的期望键、完整容量前候选；双向出现次数定义 Coverage。旧具体解释器和旧 manifest 原字节保留，来源闭包存于新 manifest。

Rust 从实际 P1 / P2 生成查询和符号映射；只在测试构建中导出已有 term 引用，包含 Ready、Selected、期望键和输出活动位 / 全部叶。`check-p3-coverage-semantics.py` 使用冻结严格 SMT 文本解析器，比较最终断言及中间观察；叶重建遵循记录字段顺序和 Option 标签，未活动载荷及 None 载荷不作为值比较。没有把生产观察当成具体期望。

合法 map / filter 的正确覆盖反例均为 false，因此最终断言一致不足以检验实现；选择、键投影和完整输出观察也必须相同。测试对错误选择、输出截断及错误键投影作三类观察变异，单独记录。没有宣称在合法程序域中杀死恒假覆盖查询。

## 局部关系与守卫

生产关系 helper 的三槽位两侧独立符号输入不加程序 WF；另有 Ready、targetOK、ProgramOK 合成布尔值。648 个赋值覆盖空、稀疏、换序、遗漏、额外、重复、同数量错键及部分键分量相同。两个键均为 Int，避免误用分量只能被类型检查拦截。

12 类局部变异分别为省略 Forward、省略 Backward、以存在代替恰好一次、遗漏键分量、任一分量相等、Match 恒真、按槽位位置配对、由输出活动位反推选择、省略 Ready、加入 targetOK、加入 ProgramOK、恒假违例。它们通过实际 SMT 的解释指令变异测试；这些候选关系不宣称来自合法 map / filter 程序。合法程序的 Unicode / 键重命名等路径与局部负例分别验收。

## 旧版与资源基线

`v0.3-baseline.tsv` 在修改 P3-D 生产代码前，从 `9b8f71f` 所含实现与原 57 文档采集；当时 243 查询 / 9,021 赋值比较通过。9 列为 case 名、P2 ID、SMT raw SHA-256、InputSlots、ValueCells、ExpressionInstances、SlotComparisons、SmtNodes、OutputBytes。测试生成器身份为 `sha256:` 后接 64 个 `a`。

基线来自 `query::tests::compare_semantics` 的逐查询输出，不由新材料生成器重写。当前测试对所有旧四类核对基线、v0.3 / v0.4 字节 / 符号 / 用量相同和 profile 绑定不同；v0.1 / v0.2 基线继续核对。生产摘要是兼容回归，不是独立语义证据或构建 attestation。

资源回归覆盖六项精确上限 / 差一、JSON 上限、继承两槽位且输出容量一的全键笛卡尔成本、预检先于布局分配、零 / 单槽位、平方 / 键数乘积 / 累计溢出、巨大容量、深量词、5,000 层图与类型；旧 IR、无 guarantee、功能拒绝与绑定篡改另有测试。

## 复现和边界

```bash
python3 scripts/generate-p3-coverage-vectors.py
python3 scripts/generate-p3-coverage-vectors.py --check
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir query::tests::row_coverage --locked --offline
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir --test query --locked --offline
```

仓库检查核对材料生成一致性；真实 Rust 路径以精准及 workspace 测试为准。成功清理测试专用导出目录，失败保留定位。实际本机结果与失败修复见[验收记录](../../docs/records/2026-10-08-p3d-validation.md)。其余义务、结构证书、独立 checker、solver、完整 Evidence 和其他平台未验收。
