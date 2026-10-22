# 2026-10-17 AX-B01 查询紧凑表示本机验收

用途：保存本批研究选择、实际执行、复现入口和边界，供项目所有者及后续实现者复核。

不包含：正式 query / solver profile 接受、真实 solver 尝试、完整管线、形式证明或运行资源资格验收。方案与等价性论证见[设计审阅](../query/ax-b01-query-compaction-review.md)。

## 输入与改动范围

- 生产源码基线：`4b53136bdf69e260ab7a9f33b8e4039ec906ce9a`。开始时 `dev` 工作区干净，相对本地 `origin/dev` ahead 2；没有刷新远端。
- 新增一个 Rust 诊断 example、Python 研究变换器、其单元测试及主代理独立验收入口。生产 `src/`、原规范、四版 profile、fixture、依赖与 lockfile 均未修改。
- 原容量导出：三候选容量均为 100；72 条 profile / target 记录、27 份不同 SMT，共 1,336,867,439 字节原 SMT。逐项核对旧[测量表](../query/ax-b01-query-size-review/measurements.tsv)的 IR / P2 / query 摘要、尺寸与完整自由声明。
- 四版语义材料导出：分别 68 / 143 / 243 / 336 条查询记录，共 790 条、336 份不同 SMT。相同 raw query 的世界与该目标期望逐项相同后才复用检查结果，不把 profile 重复项算成新的语义用例。
- 工具：本机已安装的 Rust `1.97.1-aarch64-apple-darwin`、Python `3.14.5`；Rust 命令均 locked / offline。没有安装、网络获取、真实 solver 或外部写入。

## 选择过程与未通过的首版

首版采用类型化恒等规则、共享、可达裁剪、小常量与单次使用项内联，自由名称至少六位。实际 60 / 72 条记录小于等于 1 MiB；三个 guarantee 各在四个 profile 重复，共 12 条仍超限，最大 1,285,306 字节。首版的有限语义、完整符号映射与原容量重放检查通过，尺寸门槛未通过。

主代理进一步检查了有界文本表示成本。单纯把单次使用内联放宽至 4,096 字节 / 高度 32，correct guarantee 仍为 1,238,634 字节，因此没有采用增大该阈值的方案。最终保留 128 字节 / 高度 8，选择自适应短名称与局部成本有利的小项代入；没有增加语义恒等规则或 WF 假设。

| guarantee 候选 | 首版 | 仅自适应短名称 | 仅多次使用小项代入 | 组合 |
| --- | ---: | ---: | ---: | ---: |
| correct | 1,280,838 | 1,212,081 | 1,196,535 | 960,250 |
| wrong-add | 1,285,306 | 1,215,948 | 1,202,415 | 962,642 |
| wrong-drop-zero | 1,284,038 | 1,214,681 | 1,199,735 | 962,850 |

这三份组合产物已由正式研究入口逐字节对照试验产物。四种表示都保留 501 个原自由符号；每种选择由研究预算中的 `min_free_name_digits`（6 / 1）及 `inline_multiuse_bytes`（0 / 32）显式控制。首版可用当前源码重建，不依赖只剩摘要的临时原型。

## 独立验收方法

主代理检查两个子任务的实际源码，亲自运行研究测试与独立验收。子代理只修改已指定的 example / 原型 / 单元测试文件；设计、规则选择、独立比较脚本和文档由主代理负责。

独立路径复用既有 `check-p3-query-semantics.py` 的类型化 SMT 解释器；只对短名称做机械双射以适配原解释器的词法要求，不使用原型 parser / 化简器计算期望。它同时解释原字节与新字节，对照既有冻结期望及直接解释 IR 的 Python 语义。每份不同 query 实际执行两次变换并比较新字节和映射。

从完整短名赋值、sort 与原 `SymbolOrigin` 恢复全部输入槽位，再比较活动世界；不删除 inactive、None 内部叶或 Text literal。该检查是合成符号赋值的布局对应，不是新的 P4-A 响应 parser 或真实 solver 模型校准。缺自由项、错 sort、错 origin、重复新名称和交换新名称的五类映射变异另行拒绝；常真 / 常假目标与加法改减法使用独立世界发现。

原容量材料为每份不同 query 的 12 个合成世界：空表、净值零 / 非零、未选择行、wrong-add 溢出、Pre 不成立、活动值越界、重复键、inactive 无效载荷、精确 Unicode 区分、满 100 行和满容量反序。额外对照 P4-B 的独立目标观察，确认 wrong-drop-zero 的业务 guarantee 可以违反，而其内建 row-coverage 仍成立；不混淆两种目标。

## 最终实际结果

**本次研究的字节可行性与有限语义验收通过。** 原容量 72 / 72 条记录的新表示为 265,107–962,850 字节，最大值距离 1,048,576 上限还有 85,726 字节（约 8.18%）。这只解除研究方案的字节疑问，既有生产请求仍被原尺寸拒绝。

| 目标 | 含 profile 重复的记录数 | 最小字节 | 最大字节 |
| --- | ---: | ---: | ---: |
| numeric-range | 24 | 274,860 | 527,034 |
| totality | 18 | 265,107 | 277,158 |
| key-cardinality | 12 | 489,539 | 498,986 |
| row-coverage | 6 | 722,453 | 734,131 |
| contract-guarantee | 12 | 960,250 | 962,850 |

原容量 27 份不同 query × 12 世界 = 324 次独立公式比较、槽位映射和精确目标观察全部通过；31 次常量目标变异被发现。四版材料共 790 条记录 / 336 份不同 query，在确认重复项的世界与期望相同后，实际比较 12,553 次赋值及槽位恢复，439 次常量目标变异与 1 次数学运算变异被发现。每组都拒绝五类映射篡改；这些次数是观察分母，不是证明数。

所有不同 query 都实际重复生成两次并核对字节与完整映射。最终源码另用首版参数重建 27 份原容量研究结果，全部 raw digest 与首版实测一致。

持久材料：

- [原容量最终测量](../query/ax-b01-query-compaction-review/ax-measurements.tsv)与[摘要 / 源码绑定](../query/ax-b01-query-compaction-review/ax-summary.json)。
- [四版材料最终测量](../query/ax-b01-query-compaction-review/corpus-measurements.tsv)与[摘要 / 源码绑定](../query/ax-b01-query-compaction-review/corpus-summary.json)。
- [首版原容量测量](../query/ax-b01-query-compaction-review/first-pass-ax-measurements.tsv)，保留未通过的尺寸结果。

摘要保存输入 manifest raw digest、研究预算、实际分母和源文件摘要；逐 query 的详细临时统计不重复入库，规范新字节的 raw digest 与尺寸逐行保留在 TSV。新增材料均为自有源码或既有合成输入的派生结果。

## 复现命令

下列目录必须尚不存在；需要重跑时使用新的任务子目录。大 SMT、映射和临时 binary 留在已忽略的 `.tmp/` / `target/`；持久结果表、源码、合成输入和复现命令足以重新生成，不把临时目录作为唯一证据。

```bash
mkdir -p .tmp
cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-ir --example export_query_compaction_inputs --locked --offline -- .tmp/ax-b01-compaction/input
cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-ir --example export_query_compaction_inputs --locked --offline -- --corpus .tmp/ax-b01-compaction/corpus-input
python3 scripts/test-query-compaction-prototype.py
python3 scripts/check-query-compaction.py .tmp/ax-b01-compaction/input/manifest.json .tmp/ax-b01-compaction/final-ax
python3 scripts/check-query-compaction.py .tmp/ax-b01-compaction/corpus-input/manifest.json .tmp/ax-b01-compaction/final-corpus
cmp docs/query/ax-b01-query-compaction-review/ax-measurements.tsv .tmp/ax-b01-compaction/final-ax/measurements.tsv
cmp docs/query/ax-b01-query-compaction-review/corpus-measurements.tsv .tmp/ax-b01-compaction/final-corpus/measurements.tsv
```

首版完整比较可用同一验收命令增加 `--baseline-representation` 并换新输出目录。仅重建某份表示可用 `query_compaction_prototype.py INPUT --output NEW_SMT --metadata NEW_JSON`；首版再显式传 `--min-free-name-digits 6 --inline-multiuse-bytes 0`，单项试验分别传 1 / 0 或 6 / 32。输出路径必须不同且不存在；不形成生产请求。

## 实际工程检查与保留边界

已执行通过：

```bash
cargo +1.97.1-aarch64-apple-darwin check -p radishaxiom-ir --example export_query_compaction_inputs --locked --offline
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir --lib replay::tests::original_ax_b01_and_hand_distinctions_match_exact_independent_witnesses --locked --offline
./scripts/check-repo.sh
git diff --check
```

研究脚本 22 项测试通过，包括完整手写字节、Bool / Int / Text 手算、6,000 层链、20,000 元合取、45,000 个自由符号的超 1 MiB 报告、输入 / 输出 / 项 / 边 / 深度 / 数字预算与既有文件保护。Rust 精确目标回归为 1 项通过；它保留原 P4-B 行为，不表示紧凑表示已接入 P4-A。example 构建曾出现不阻断的 xcrun SDK 定位警告；最终命令均成功。

本批没有重跑完整 workspace 测试，没有真实 cvc5、跨平台、独立 checker、CI、运行时硬内存 / deadline 或模型打印验收。数学论证、有限动态观察、原型测试、生产组件和形式证明分别报告；不产生 `proved`、attempt 或 Evidence。

进入生产实现仍需接受新的确定性 query profile 及 P4-A 显式接入范围，在 Rust 有类型 DAG 内实现规则并重新验收生产预算 / strict / 绑定。现有四版原容量请求的 stdin 拒绝保持，不因研究结果改写历史。

本批收口时全部改动未暂存、未提交；`dev` 仍相对本地 `origin/dev` ahead 2，没有 push 或其他远程动作。未启动长期进程。任务临时材料保留在 `.tmp/ax-b01-compaction/`，约 2.79 GB；持久材料已按上文保留，未自动删除已有文件。
