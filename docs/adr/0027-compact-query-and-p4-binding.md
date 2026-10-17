# ADR 0027：紧凑查询与 P4 显式绑定

日期：2026-10-17。状态：Accepted，项目所有者于 2026-10-17 接受 D1–D3，并授权 A–C 实施与本机纯组件验收；不授权真实 solver。

用途：决定紧凑表示的版本、规范化边界、资源契约与 P4 接入范围，供项目所有者和实现者审阅。

不包含：新增语义命题、关系编码、执行资源扩容、真实工具校准、完整 Evidence 或独立证明链。

## 背景与审阅结论

[紧凑表示研究](../query/ax-b01-query-compaction-review.md)及[有限验收](../records/2026-10-17-query-compaction-validation.md)表明，保持 AX-B01 原容量 100、全部自由输入与原公式，72 条研究记录均可落入 1 MiB，最大 962,850 字节，余量 85,726 字节。这是表示可行性的依据，不是生产编码、模型打印或 128 MiB / 6 s 执行可行性的依据。

当前实现存在三个接入边界：`QueryBinding` 没有查询规则摘要；六项 `QueryUsage` 不单独反映规范化、共享查找和代入工作；P4 请求 v0.1 固定旧规则与旧 query 预算结构。直接在旧 renderer 中压缩或让旧 solver profile 接受新增 enum，会静默改变旧规范字节或支持集合。因此需要新 profile、明确的字节版本和拒绝矩阵。

## 决定

1. 新增 `axiom-p3-map-filter-query-v0.5`，仅继承 v0.4 的五类目标与整图支持边界。在原有类型 DAG 构造后进行恒等化简、相同项共享、可达裁剪、保序短名称和有界代入。不改变 WF / Pre / violation，不增加假设，不特判 AX-B01，不扩大 join / group / 聚合或双世界支持。
2. 新 profile 使用 artifact `axiom-smtlib2-qf-uflia-query0.3`，方言继续为 `SMT-LIB-2.6/QF_UFLIA`。v0.5 规则原文 raw digest 进入新 QueryBinding，并在 P4 请求中保留。旧四版继续使用 query0.2，原 bytes、symbols、六项 usage、绑定及拒绝行为不改。
3. 固定一种确定性表示，不开放调用方调节化简规则、名称宽度、代入阈值或降级方式。生产在 Rust DAG 中处理，不运行 Python，不先渲染旧的几十 MB 文本。旧原始构造收费保留，新增规范化与临时工作收费；任何不足均拒绝，不按预算选择另一个字节结果。
4. 新增内部 solver profile `axiom-p4-cvc5-1.3.4-query0.3-model-v0.1`，只接受 v0.5 / query0.3，生成请求 `axiom-p4-solver-request` v0.2。旧 profile 只接受原四版 / query0.2。双方不自动切换；不存在“试旧版、太大则压缩”的路径。
5. 模型文法和解码语义不扩张。symbols、layout、response observation 与 model-world candidate 的结构和解释未改变，保留各自 v0.1，通过精确 query / request 摘要区分新来源。P4 重建新名字、实际保留的派生项及完整 origin；unknown 仍不能解码 world。
6. 接入包括 P4-A 的纯请求规划、合成响应 / 模型、strict 重建，以及新候选经过既有 P4-B 的五类精确目标回归。P4-B 求值与观察格式不改；跨 profile 不能复用 request / model / candidate。候选的 world bytes 在对应赋值下保持，完整候选摘要因来源及名称改变而不同。
7. 继续使用原 stdin 1,048,576、stdout 4,194,304、stderr 65,536、外层 memory 134,217,728 字节与 deadline 6,000 ms；内部 solver 限值 1,000,000 steps / 5,000 ms 也不变。adapter 保持 `planned-not-calibrated`，不修改 registry、execution profile 或锁定实验材料。

精确规则分别见 [query v0.5](../query/map-filter-query-v0.5.md) 与 [P4-A v0.2](../query/p4-request-response-model-v0.2.md)。两份规则均已接受；实现绑定 Accepted 正文的精确摘要。后续正文变化也改变摘要，不能沿用旧身份。

## 选择与影响

| 选择 | 理由与代价 |
| --- | --- |
| query artifact 升至 0.3 | 旧 v0.2–v0.4 只增加 kind，已有目标字节相同；本次改变已有目标的规范表示。按 ADR 0003 显式区分字节版本，代价是 P4 及未来消费者必须新增精确支持项 |
| 请求升至 0.2，模型格式保留 0.1 | 请求增加 query 规则摘要与 compact 预算，闭合成员已变化；模型文法、候选成员及值解释没有变化，避免无依据地连带升级所有格式 |
| 完整 DAG 后规范化 | 复用已验收的语义构造与顺序，控制审阅面；仍需承担原 DAG 构造成本，不能声称按最终 1 MiB 占用内存 |
| 全部自由声明与保序重命名 | 保持输入完整性及 Text 类排序；没有被断言引用的输入仍必须出现在 sat 模型中，真实 solver 是否按当前参数完整打印仍待校准 |
| 不增关系编码或 WF 假设 | 可用有类型恒等式逐节点论证，不把正确性依赖转移到新增假设；不承诺任意程序都能压到 1 MiB |

新增内部分支和规则会增加需审阅的生产代码；有限动态比较不能认证编码器、证明公式等价或缩小独立 checker 的责任。当前没有接受新的公共 Evidence 语义或可信输入。

## 实施与验收分工

按下列顺序交付，主代理主持设计、边界复核和最终验收；明确实现任务委派 `gpt-6.1-sol`，推理强度 `high`。

| 批次 | 明确任务 | 验收与停止条件 |
| --- | --- | --- |
| A：query | 在既有 query 模块新增 v0.5 类型化规范化、固定渲染、规则绑定及资源记账；新增自有手算和负向材料 | 旧四版基线全部保持；独立解释实际新 SMT；原容量按五类目标全部测量；任何差异先定位，不改 oracle 或旧字节迁就实现 |
| B：P4-A | 新 profile / 请求 v0.2、显式配对、compact 预算绑定、重建符号及派生清单；复用模型 parser / decoder | 新旧交叉配对、规则 / 目标 / origin / budget 篡改拒绝；对应模型 world 相同；旧 P4 字节与错误回归保持 |
| C：整体验收 | 合成新模型接入既有 P4-B，扩展独立有限检查和预算压力材料 | 原容量三候选、完整 100 槽位与两种 wrong 区分；invalid、timeout / unknown、篡改路径不升级成功；格式、Clippy、workspace 测试及仓库检查通过 |

本稿不要求拆出重复管线或新 CLI。扩展既有入口时保留旧 limits / usage 的含义，使用类型化的新预算承载紧凑分支；旧调用的兼容包装不得隐式选择新 profile。实现可按稳定职责拆分大文件，不顺带重构语义编码。

合成 timeout 只测试协议与错误传播；不能作为真实超时 / OS 隔离验收。生产最大字节不能直接引用研究数字，必须重新报告；规范若导致原容量超限，停止并回到本决策审阅，不增加限值或缩容量。

## 已接受的范围

| 决定 | 项目所有者已接受的精确范围 |
| --- | --- |
| D1：表示与版本 | 接受固定 v0.5 规则、query0.3、完整自由声明与保序重命名；五类目标和原容量保持 |
| D2：预算与拒绝 | 接受原构造费用加新增 compact 预算，调用方显式给上限；无自动降级，无 solver 资源增限；后续按实际 Rust 用量报告成本 |
| D3：P4 接入与实施 | 接受新 solver profile / 请求 v0.2、旧模型格式与文法、P4-B 合成回归，并授权 A–C 的 Rust 实施与本机纯组件验收 |

项目所有者已一并接受 D1–D3。该接受不授权真实 solver、依赖变化、push / PR、远程写入、公共 Evidence、跨仓 checker 或正式 Agent 实验。
