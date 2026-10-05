# IR 派生义务材料 v0.2

依据 [ADR 0018](../../docs/adr/0018-ir-derived-obligation-profile.md) 和[正式规则](../../docs/evidence/ir-derived-obligations-v0.2.md)。仅支持 `axiom-obligation-set` / `0.2`、`keyed-finite-table-verification` / `0.2`、`ir-derived`；不是完整 Evidence v0.2、benchmark、pipeline receipt 或独立 checker 结果。

## 文件与来源

- `sets/*.jcs`：26 份独立完整集合，合计 482 项定义。无 BOM / 空白 / 末尾换行；规范字节与 raw SHA-256 供 Rust 实际生成结果逐字节核对。
- [cases.tsv](cases.tsv)：无表头，九列为 case、仓库相对 IR 路径、IR 文档域摘要、IR raw 摘要、义务数、累计 definition 规范字节、累计 path JSON 数组规范字节、集合字节数、集合 raw 摘要。既有 21 份输入不复制，继续引用 P1 的已验收合成材料。
- `inputs/`：五份新增自有合成 IR：全部范围表达式与记录构造、只改 Pre、无聚合 group、同源多输出、100 层范围表达式。all-numeric 的 pretty 变体改变原数组 / 字段次序并重复可去重公式，但其规范身份不变。
- `negative/*.jcs` 与 [negative.tsv](negative.tsv)：29 份实际导出变异；TSV 三列为名称、基线 case、内部 Rust 错误类别。包括两个聚合范围分别遗漏、group 两义务分别遗漏、多余 / 重复 / 错 path / expectation / IR / 域、错误版本 / scope / header 与禁止结果。错误类别不属于公共状态码；缺少路径闭合或位置不匹配可能归为 UnexpectedObligation。
- [old-pipeline-rejections.tsv](old-pipeline-rejections.tsv)：旧 pipeline 验证入口对新集合、删新成员、再伪装旧版本的三种拒绝；脚本真实执行旧验证器，未修改其代码。
- [provenance.json](provenance.json)：接受状态、生成器 / 规则 / ADR 原始摘要和数量；不是签名或证明。

[审阅材料](../../docs/evidence/p2-profile-review/README.md)另保留 21 份 / 315 项逐定义清单、7 个有限 group 真值区分、10 个角色对照、12 份旧 / 新核心身份预览。旧状态不移植；兼容预览没有验证全部源 Evidence 状态，因此不是完整迁移器或 ADR 0009 的迁移演练。

## 再生成与真实消费

```bash
python3 scripts/generate-p2-profile-review.py
python3 scripts/generate-p2-profile-review.py --check
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir --test obligations --locked --offline
```

生成器复用项目自有独立 Python JSON / hashlib 规则，逐例数量由规范人工推导后固定，不调用 Rust 生产 helper、不读取 expected outcome 驱动清单。新增 IR 在 Rust 测试中先经过真实 P1 strict，之后才成为 P2 输入。计数、逐项定义 / ID、完整集合与 raw 摘要是独立期望；Rust strict 自身 round-trip 只是额外检查。

所有生成文件只通过脚本更新，README 手工维护。Rust 另在内存构造 5,000 层 DAG 和宽输出，手工计数期望，测试预算上限包含等号、差一失败与错误不返回部分集合。生成结果不证明任何义务成立，group 区分例没有运行 query / solver / host / replay。其他平台与真实独立 checker 未验收。
