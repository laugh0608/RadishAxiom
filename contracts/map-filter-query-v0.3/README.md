# map / filter query v0.3 独立验收材料

对应 [ADR 0021](../../docs/adr/0021-map-filter-key-cardinality.md)及 [v0.3 规则](../../docs/query/map-filter-query-v0.3.md)。材料用于 P3-C 有限语义与兼容回归，不是 Evidence、solver 结果或证明。

## 输入与独立期望

`cases.json` 保存 57 份文档、243 个真实 P2 目标、9,021 个目标 / 世界赋值，包含原 v0.2 全部 50 文档和 143 目标。7 份新增规范 IR 位于 `inputs/`：容量零、稀疏选择、谓词故障配小容量、Pre false / fault、无关故障配目标容量失败、复合键与 Unicode。AX-B01 三份原完整容量 IR 直接引用旧路径；wrong 名称不预设键 / 基数违例。

生成入口 `scripts/generate-p3-cardinality-vectors.py` 使用冻结的 IR / P2 构造与解释器；新的 `p3_cardinality_semantics.py` 从具体来源结果及局部表达式定义独立计算容量前行。`prepared_observations` 保存每个目标 / 世界的 Ready 和完整行候选；失败用 ready=false、rows=null 表示，不能冒充空表。该观察在 WF 非法或 Pre 不成立时也可记录，但只在 WF / Pre 成立时用于违例判定。

手算锚点核对 filter 的活动行计数、来源失败后下游无局部反例、局部故障、无关节点、Pre 排除和复合键。规范、源码及继承来源闭包摘要存于 manifest。旧 v0.1 / v0.2 绑定源码与材料不改。

Rust 从真实 P1 / P2 生成 SMT，导出完整字节及符号映射；`check-p3-cardinality-semantics.py` 使用旧独立严格 SMT 解析器与新具体观察逐世界比对。10 类程序变异包括 targetOK 守卫、ProgramOK 守卫、遗漏 Ready、以槽位数计数、严格小于容量、截断输出、遗漏容量、保证失败归因、错目标及恒假 assert。ProgramOK、保证失败和错目标使用真实查询列的错误组合；其余改变实际 SMT 的解释指令。不是 solver 变异执行。

## 唯一键谓词的独立单元层

合法 map / filter 不从 WF 输入产生重复键，因此不宣称完整程序杀死“忽略 Unique”变异。Rust 单元测试直接调用同一生产 `output_unique`，对两槽位、两主键分量构造合成 O*，导出 SMT 供 Python 独立解释。16 个赋值覆盖活动组合、单分量相同、完整碰撞及 NFC / NFD 不同；三类变异为全分量合取改析取、遗漏活动守卫、忽略碰撞。没有程序输入 WF 守卫，也不把合成碰撞称为程序反例。

## 兼容与预算基线

`v0.2-baseline.tsv` 在修改 P3-C 生产源码之前，从提交 `9f843ea` 的 v0.2 实现及原 50 用例采集。9 列依次为 case 名、P2 目标 ID、SMT raw SHA-256、InputSlots、ValueCells、ExpressionInstances、SlotComparisons、SmtNodes、OutputBytes。采集前的 143 查询 / 5,185 赋值测试通过，使用测试生成器身份 `sha256:` 后接 64 个 `a`。

采集入口是共享 `query::tests::compare_semantics` 的逐目标 `EncodedQuery` 输出；基线不由新材料生成器重写。当前测试核对全 143 行目标的摘要和六项预算，以及 v0.2 / v0.3 的字节、符号和不同 profile 绑定；原 68 个 v0.1 目标继续核对其既有基线。生产摘要仅表示兼容回归，不是独立语义证据或构建 attestation。

六项预算精确值 / 差一、JSON 上限、容量 1 继承两槽位的 N²K 收费、0 / 1 槽位、累计费用和宿主算术溢出均有回归。布局预算为零而比较预算不足时，先返回 SlotComparisons，验证预检在槽位分配前发生。5,000 层图 / 类型、深量词、巨大容量和未支持表达式复用旧材料；没有 guarantee 仍可请求。

## 复现

```bash
python3 scripts/generate-p3-cardinality-vectors.py
python3 scripts/generate-p3-cardinality-vectors.py --check
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir query::tests::cardinality --locked --offline
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir --test query --locked --offline
```

既有 26 份 IR / 482 项义务在测试预算下实际得到 139 查询、1 项资源拒绝、226 项 UnsupportedKind、90 项 UnsupportedFeature 和 26 项 check。新增 key-cardinality 的 29 项中 12 项生成、17 项整图功能拒绝，旧 profile 计数不变。

仓库检查只读核对材料一致性。测试成功删除各自的临时导出目录，失败保留定位；本机验收事实见[验证记录](../../docs/records/2026-10-08-p3c-validation.md)。row-coverage 等其余义务、其他图操作、真实 solver / checker、Evidence 集成及其他平台未验收。
