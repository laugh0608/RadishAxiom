# map / filter query v0.1 独立验收材料

对应 [ADR 0019](../../docs/adr/0019-map-filter-query-encoding.md) 与[正式编码规则](../../docs/query/map-filter-query-v0.1.md)。本目录包含合成 IR、有限输入世界、逐目标布尔期望及一个手算 SMT 字节向量；不是 Evidence、solver 模型、证明或完整 P3 profile。

## 内容与来源

- `inputs/`：37 份合成 IR v0.2 规范文档；AX-B01 的正确 / 两个 wrong 直接引用原有迁移输入，不复制或缩小容量。
- `cases.json`：40 个文档用例、68 项真实 P2 目标、2,394 组目标 / 世界赋值期望。包含源码摘要、IR raw 摘要、definition / ID、全部 26 个支持 op 的覆盖集。Int / Fixed 使用 Python 数学整数，模型输入均合成。
- `expected/minimal.smt2`：零容量输入、恒真 guarantee 的七项 SMT DAG，由规则手算后编码目标 ID，独立于生产输出。
- `resource-inputs/`：60 层二槽位 forall 的展开拒绝，以及 5,000 层记录引用和 5,000 层转换图的正常迭代处理；不把它们展开成大规模具体世界。

期望生成复用既有独立 IR 身份 / 规范字节与 P2 definition 工具。语义期望由 `scripts/p3_query_semantics.py` 的具体表解释生成，并用 AX-B01 业务区分、故障 / 死分支 / Pre 等手算性质另行锚定；不读历史 expected outcome，不调用 Rust 生成器。

Rust 测试对每个规范文档实际完成 P1 / P2 / P3，并将 SMT 文本与符号映射写入本次独占临时目录。`scripts/check-p3-query-semantics.py` 独立解析 / 类型检查实际 SMT 文本并解释每个赋值，与冻结期望和具体 IR 重算同时比较。另核对加法变减法、恒假目标两种合法语法篡改会被区分，Text 字面类合并会被查询拒绝。成功删除本次目录；失败保留精确路径供诊断。测试用生成器摘要为明确的合成声明，不是实际构建身份。

None 内载荷可不满足内类型范围；不活动行可含越界数值 / Enum 标签。材料包含这些世界，以及稀疏槽位、输入顺序、重复键、Pre false / fault、if / Option 分支、严格布尔和记录故障、输出容量更小、嵌套绑定、100 位整数、Unicode 与符号名称隔离。有限材料仍不能穷举完整输入域。

## 复现

```bash
python3 scripts/generate-p3-query-vectors.py
python3 scripts/generate-p3-query-vectors.py --check
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir query::tests --locked --offline
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir --test query --locked --offline
```

仓库检查只读核对材料一致性，不执行 solver。Rust 测试使用已安装 Python 3 标准库，不下载或安装依赖。实际 SMT 临时输出不提交；只有小型手算字节向量进入版本控制。

既有 P2 清单的 482 项位置全部保留。在测试预算下，115 项实际生成 query，1 项因超大输入容量拒绝，56 项被文档功能边界阻断，284 项属其他 prove 类型，26 项为 check。这与初始审阅的 116 项静态候选不同，不能把超预算项计作生成成功。

本材料不验证真实 cvc5 的语法接受 / 求解、任意 Text 模型类解码、独立反例重放、证明证书、Evidence v0.2 或六平台；这些结论不得由有限解释比对外推。
