# map / filter query v0.2 独立验收材料

对应 [ADR 0020](../../docs/adr/0020-map-filter-node-totality.md)与[增量编码规则](../../docs/query/map-filter-query-v0.2.md)。本目录保存 P3-B 的独立有限期望、合成 IR 与旧版字节回归基线；不是 Evidence、solver 结果或证明。

## 内容与来源

`cases.json` 包含 50 个文档用例、143 个真实 P2 目标、5,185 组目标 / 世界赋值。40 个文档复用 v0.1 原有 IR 与世界，另新增 10 个文档，包含无 guarantee、false guarantee、节点内严格 and / or、Option 分支、下游故障、容量对照、键 / 接口改名及节点内记录兄弟故障。AX-B01 三个候选使用原完整容量，不缩小或复制来源 IR。

`inputs/` 保存新增的 10 份规范 IR；`resource-inputs/` 保存三个合法但 P3 不支持的 guarantee（exists_rows / count_where / sum_where）及超大输入容量。拒绝测试经过真实 P1 / P2，不能靠坏身份在更早阶段失败冒充功能拒绝。原 5,000 层类型 / 图与深量词材料直接引用 v0.1。

独立生成入口是 `scripts/generate-p3-totality-vectors.py`；复用冻结的旧 IR / P2 材料生成函数和具体表解释器。`p3_totality_semantics.py` 只增加指定节点的具体值 / FAULT 观察；没有读取 Rust 或生产 SMT AST。手算锚点另核对范围边界、容量、依赖、空表、契约区分、Option、键重命名及小额 AX-B01 的总定义性，不读取基准 expected outcome。源码、规则、旧材料和各 IR 摘要存于 manifest。

Rust 测试从实际 CanonicalDocument / 完整 ObligationSet 生成查询，导出 SMT 和符号映射。`check-p3-totality-semantics.py` 复用原独立 SMT 文本解析器，逐赋值同时比较冻结期望和具体重算。8 类变异中，targetOK / sourceOK 守卫、去掉容量、忽略来源与恒假目标修改实际 SMT 的解释指令；全局故障、guarantee 故障和错目标通过实际不同目标查询结果的错误组合区分。它们是有限语义变异检查，不是真实 solver 的变异运行或形式证明。

## 旧版兼容基线

`v0.1-baseline.tsv` 四列为 case 名、目标 ID、SMT raw SHA-256、字节数。它在本次生产实现修改前，使用 `a62653d` 所含 P3-A 生产源码及原 40 用例采集，入口为 `query::tests::actual_smt_text_matches_independent_concrete_semantics` 的逐查询输出；生成器身份为测试合成值 `sha256:` 后接 64 个 `a`。该次原 68 查询 / 2,394 赋值比较通过。

采集按原 cases / targets 顺序，逐项记录 `case.name`、P2 target ID、EncodedQuery 的 artifact_digest 与 bytes.len；输入精确来自未修改的 `contracts/map-filter-query-v0.1/cases.json`。当前共享测试入口 `query::tests::compare_semantics` 重算并核对所有基线目标，同时检查 v0.1 / v0.2 的原目标都保留字节。基线不由新生成器重写；若出现差异须先调查，不可用重新采集掩盖回归。

这些生产摘要只支持字节兼容回归，不是独立语义期望或 attestation；独立语义证据仍来自具体 IR 与 SMT 文本的不同实现路径。v0.1 原材料及其绑定的 Python 源码保持原字节。

## 复现与边界

```bash
python3 scripts/generate-p3-totality-vectors.py
python3 scripts/generate-p3-totality-vectors.py --check
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir query::tests --locked --offline
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir --test query --locked --offline
```

仓库检查只读核对新旧材料一致性。在本机测试预算下，既有 482 项 P2 清单于 v0.2 实际生成 127 条查询、1 项容量资源拒绝、255 项未支持义务、73 项文档功能拒绝及 26 项 check；原 v0.1 计数不变。

Rust 验收还覆盖显式 profile 支持 / 拒绝、完整 P2 清单、绑定 / 目标 / 字节篡改、源身份、顺序归一化、六项预算精确上限 / 差一、旧 IR 拒绝与无 guarantee。成功时删除本次测试临时目录，失败保留用于定位。

不调用 solver，不产生证明、模型或执行许可；有限无反例不能报告 unsat。真正 solver、独立 checker、完整 Evidence v0.2、其他义务 / 图操作 / 双世界以及其他平台仍需分别验收。
