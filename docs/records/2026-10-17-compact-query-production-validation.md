# 2026-10-17 紧凑查询与 P4 接入本机验收

用途：记录 [ADR 0027](../adr/0027-compact-query-and-p4-binding.md) A–C 的实际 Rust 实现、生产字节、独立有限比较及兼容性边界。研究阶段的选择与未通过首版保留在[研究验收](2026-10-17-query-compaction-validation.md)。

## 范围与版本

项目所有者接受 D1–D3 后，先将 ADR 0027、query v0.5、P4-A v0.2 标为 Accepted，连同路由共六份文档提交为 `14a9693297333cf1bfec115d73e9ab4ec9247c8a`。本批从该基线开始；`dev` 相对本地 `origin/dev` ahead 4，没有刷新远端。研究代码先前已提交为 `f60d4c5`。

主代理主持规范解释、生产实现审阅、资源收费修正和最终验收；A query、B P4 与 C 独立验收实现分别委派 `gpt-6.1-sol` / `high`，共用当前 `dev`，没有建立新分支或 worktree。

- A：新增显式 `MapFilterV0_5` / query0.3，绑定 Accepted 查询规则摘要。在 Rust 的有类型 DAG 内执行固定恒等化简、共享、裁剪、保序短名和有界代入；生产不调用 Python，不先生成旧大 SMT 文本。
- 旧 `QueryLimits` / 六项 `QueryUsage` 保留。新 `QueryBudgets` 要求显式 `CompactQueryLimits`，新增七项收费及阶段化拒绝；不足不返回部分制品、不自动选择另一种表示。原构造成本仍计入原账本，输出字节按实际新表示计入。
- B：新增 `Cvc5Query0_3ModelV0_1`，只配 v0.5 / query0.3；请求 v0.2 绑定 `query_rules` 与 `limits.component.query={base,compact}`。旧 profile 只配旧四版。沿用模型 parser、Text 类、symbols / layout / response / candidate v0.1，按实际新名称重建完整自由与派生符号。
- C：实际新模型通过 `ReplayWorldInput::ModelCandidate` 进入既有 P4-B；重放生产求值器未改。扩展既有诊断 example 与独立 Python 检查，读取实际 Rust 导出的 SMT、symbols、origin 和资源用量。

没有修改 IR / P2 / Evidence 语义、输入容量、solver registry / execution profile、依赖或 lockfile；旧规范和本批 Accepted 规则正文保持。没有新增公开 CLI 或关系编码。

## 实际产物与有限检查

AX-B01 三候选各九个受支持目标，共 27 条新 profile 记录；原输入容量均为 100，每份保持 501 个自由符号。实际新 SMT 为 **265,107–962,850 字节**，最大值距离 stdin **1,048,576** 上限有 **85,726** 字节余量。新 P4 规划逐一成功；旧四版的 72 条原容量请求仍因原字节超限拒绝。

27 个原查询绑定产生 24 个不同的新 SMT raw digest；不同来源可能压到相同字节，不能只按新 raw 去重语义检查。corpus 也按原查询绑定保留各自 symbols / origin，重复项先核对世界与精确目标期望，再复用解释结果。

独立路径解释实际 Rust 字节，并对照直接 IR 解释与冻结期望；研究原型只用于规范字节与完整名称映射的交叉对照，不用于计算新 SMT 的期望值。AX-B01 的 27 × 12 = 324 次公式、槽位恢复与精确目标观察全部通过，31 次断言常量变异及五类映射篡改被发现。满 100 行、反序、inactive 载荷、Unicode、Pre 不成立、重复键和两个 wrong 均包含在材料中。

完整 corpus 的 790 条记录按 336 个原查询绑定完成 12,553 次公式比较与槽位恢复，439 次常量变异、一次算术变异及五类映射篡改被发现；147 份不同新 SMT 为 94–962,850 字节。实际 Rust 字节与研究规范表示在全部 27 / 336 个原绑定上逐项一致。

持久材料为 [AX 测量](../query/compact-query-production-validation/ax-measurements.tsv)、[AX 摘要](../query/compact-query-production-validation/ax-summary.json)、[corpus 测量](../query/compact-query-production-validation/corpus-measurements.tsv)及 [corpus 摘要](../query/compact-query-production-validation/corpus-summary.json)。主代理核对两组数据与最终检查输出逐字节一致，34 / 94 个源码及材料绑定均匹配当前文件。临时完整 SMT 和映射保留在 `.tmp/compact-query-production/`；不是仅凭临时目录给出结论。

## 资源与拒绝

AX-B01 本次 Rust 实际用量的逐项最大值如下；各列可能来自不同目标，不能合成一条查询的实际用量。

| compact 资源 | 实际最大值 | 本机诊断显式上限 |
| --- | ---: | ---: |
| normalized_nodes | 80,068 | 1,000,000 |
| normalized_edges | 195,061 | 5,000,000 |
| scratch_cells | 3,661,688 | 100,000,000 |
| work_steps | 29,266,631 | 2,000,000,000 |
| temporary_bytes | 3,532,914 | 1,000,000,000 |
| integer_digits | 6 | 4,096 |
| dag_depth | 120 | 100,000 |

corpus 的整数位数最大值为 101，其他六项最大值与上表相同。这些是显式本机诊断预算与逻辑计量，不是调用默认值或 OS 峰值内存测量。完整 base / compact 配置保存于摘要；旧文本导出的 100,000,000 输出诊断上限只用于测量旧大 SMT，新导出仍为 1 MiB。P4 的 stdin / stdout / stderr、128 MiB / 6 s 及内部求解器限值未改。

新增回归覆盖七项预算 exact / one-less、零预算、原构造与渲染阶段、任意精度整数及位数增长、高扇出、深 DAG、共享哈希碰撞的中断、固定代入成本与高度边界。新预算缺失或误配旧 profile、规则 / 目标 / origin / 预算篡改、未知旧名或被删除派生项、缺失自由项、Text 冲突、无效输入与跨来源绑定均拒绝；unknown、timeout、非成功退出和输出截断沿用原先优先级，不升级为成功模型。

## 模型与旧版兼容性

新旧对应模型的 world bytes、Text / Option 复合值与全部 origin 一致；定义顺序或 Text atom 名称置换不改变规范世界。44 项手算目标结果通过新候选路径核对；同一候选 world 的直接重放结果字节一致，来源摘要不同。还对照原手算世界的 outcome，保持 Pre 拒绝、wrong-add 与 wrong-drop-zero 的业务 guarantee 区分；后者内建 coverage 仍可成立。

从 `git archive 14a9693` 的独立旧源码快照导出 minimal、unicode-literals、composite 三组 query / symbols / layout / request / response / candidate，共 18 份旧字节。主代理在最终源码再次导出并逐文件比较，全部一致；冻结摘要和显式导出入口保存在 [legacy.rs](../../crates/axiom-ir/src/solver/tests/legacy.rs)。日常测试不写基线文件，导出测试默认 ignored，已由主代理明确单独运行通过。

旧四版完整语义 / 字节回归、72 条旧原容量尺寸拒绝，以及原始 manifest 的大 SMT 摘要、声明、完整 symbols 也被实际核对。没有为重复取得相同证据再运行一次无 flag 的完整旧 corpus 导出。主代理另核对 1,878 份既有规范、契约与 lockfile 和 Accepted 基线逐字节一致；历史研究说明仅增加后续验收路由，未改绑定规则。

## 修正与复核

主代理审阅发现临时单元初始化、字节复制及排序操作应完整计入工作量，补齐收费并将排序计数改为 checked arithmetic；最终导出在这些修正和格式化之后重新生成。最终源码中的整数运算与资源累加溢出均通过显式拒绝处理，哈希本身的 wrapping 运算不作为资源计数。

验收代码有三处假设已修正：新 SMT raw 数不必等于旧绑定数；任意未锚定 Text 的原始字符串不应要求在模型类规范化后逐字节保留，因此比较候选世界的直接重放及原世界的 outcome；摘要材料名称不可复用世界标签变量。前述中间失败、被中断的诊断导出留在 `.tmp/`，最终生产字节与检查均重新运行，不把失败结果算作通过。没有修改冻结语义 oracle 来迁就生产实现。

## 复现与工程检查

本机工具为 Rust `1.97.1-aarch64-apple-darwin` 与 Python `3.14.5`；Rust 命令均 locked / offline。以下输出目录必须不存在；旧 manifest 与研究缓存可按[研究记录](2026-10-17-query-compaction-validation.md#复现命令)先生成，缓存的输入、源码、SMT、完整映射和冻结测量摘要由检查入口重核。

```bash
cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-ir --example export_query_compaction_inputs --locked --offline -- --production .tmp/compact-query-production/reproduce-ax
cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-ir --example export_query_compaction_inputs --locked --offline -- --production --corpus .tmp/compact-query-production/reproduce-corpus
python3 scripts/check-compact-query-production.py .tmp/compact-query-production/reproduce-ax/manifest.json .tmp/ax-b01-compaction/input/manifest.json .tmp/ax-b01-compaction/final-ax .tmp/compact-query-production/reproduce-ax-check
python3 scripts/check-compact-query-production.py .tmp/compact-query-production/reproduce-corpus/manifest.json .tmp/ax-b01-compaction/corpus-input/manifest.json .tmp/ax-b01-compaction/final-corpus .tmp/compact-query-production/reproduce-corpus-check
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline
./scripts/check-repo.sh
git diff --check
```

格式、workspace Clippy 与完整 workspace 测试通过：共 294 项（runtime 56、Darwin store 3、digest 2、IR 233），零失败；另一个默认 ignored 的旧产物导出测试已单独运行通过，不重复计入 294。新增 17 项 Rust 回归覆盖 query 9 项、P4 5 项、候选重放 2 项与旧产物摘要 1 项。仓库检查通过，共核对 2,634 文件；`git diff --check` 通过。

## 结论与未覆盖边界

A–C 已完成本机组件验收。这里只验收本机内部组件；新表示解除本批 AX-B01 的字节阻断，不代表任意输入都能压入 1 MiB。adapter 仍为 `planned-not-calibrated`，没有真实模型打印、128 MiB / 6 s 资源可行性、OS 硬隔离、形式等价证明、完整 Evidence 或跨仓独立 checker 验收。

本批没有启动真实 solver、安装依赖、执行其他平台 / CI、push、创建 PR、写入远程或运行正式 Agent 实验；不产生 attempt 或 `proved`。Accepted 文档已提交，A–C 实现与本记录尚未提交或暂存。所有任务临时材料保留，没有清理既有失败或来源材料。本批 `.tmp/compact-query-production/` 约 79 MiB，独立旧源码及产物快照约 84 MiB，原研究材料约 2.6 GiB；最终文件系统大小随诊断日志可能小幅变化。
