# AX-B01 原容量查询尺寸审阅

日期：2026-10-12。状态：本机只读诊断；不接受新 query / adapter / 资源 profile。

用途：解释 P4-A 的实际 stdin 拒绝，给项目所有者选择后续范围提供可重跑数据。本文不报告 solver 运行、求解时间、硬内存需求、语义等价证明或查询优化完成。

## 结论与下一步

AX-B01 原容量三候选、四个已接受 profile 共 72 份已支持查询，全部超过沿用的 1,048,576 字节 stdin 上限。完整字节实际为 **42,577,698–65,831,615**（约 **40.605–62.782 MiB**），P4-A 的拒绝有真实输入依据。

每个 term 及引用重复目标 ID 的 64 位摘要，缩短名字可节省约 81.0%–81.3% 原字节，但单独或再结合死定义移除、完全相同项共享仍不能降至原上限。因此不能把“去掉长名字”视为已经解决纵向阻断，也不能据此静默增限。

本次测量时建议先接受具体重放范围；随后 [ADR 0026](../adr/0026-p4-concrete-target-replay.md) / [P4-B 规则](p4-concrete-target-replay-v0.1.md)已接受并完成[本机验收](../records/2026-10-13-p4b-validation.md)。直接有限 world 的 WF / Pre / 目标解释不依赖 solver 请求尺寸；它补齐候选到精确违反的缺口，不代表原容量 solver 路径已打通。随后单独审阅新查询表示，仍保留原容量、原 profile 字节与旧资源登记。

## 实际输入与来源

- 生产源基线为 `b86eb33cb807238254262c593ea6365f5656bcd2`；本次没有修改 `query`、`solver` 或原规范 / fixture。
- 三个输入为现有 `ax-b01-correct`、`ax-b01-wrong-add`、`ax-b01-wrong-drop-zero` 的迁移 IR v0.2，两个表类型原声明容量均为 100。完整 IR / P2 raw、路径、目标、query raw 与 profile 逐项保存在[测量表](ax-b01-query-size-review/measurements.tsv)。
- profile v0.1 / v0.2 / v0.3 / v0.4 分别为 9 / 15 / 21 / 27 份，合计 72；原始 SMT raw digest 有 27 个不同值，旧目标跨 profile 字节相同但完整绑定不同。
- [只读入口](../../crates/axiom-ir/examples/inspect_ax_b01_queries.rs)实际调用既有 P1 / P2 / encode_query。P3 生成器身份使用与既有测试相同的合成 `sha256:` 加 64 个 `a`，仅为声明；尺寸不依赖它，不声称源码 attestation。
- 工具为本机既有 Rust `1.97.1-aarch64-apple-darwin`，使用 locked / offline；未安装依赖、执行 cvc5、改资源或触发 CI。

原 query 首尾、名字、全部自由符号、类型布局和目标均保持，测量入口只向 stdout 写 TSV，不输出改写 SMT 或规划执行请求。两次实际运行逐行核对 72 份原摘要及前 16 项基线测量一致，第二次增加相同项共享的尺寸估算。

## 尺寸构成与有界估算

原名字形如 `q<64hex>_tN`。short_names 将它估作 `tN`，原序号不变，每次出现减少 66 字节。live 从唯一 assert 沿零参数 define-fun 的有类型 DAG 反向标记可达定义，始终保留全部自由 symbol 声明、Text sort 与首尾命令。shared 将同 sort、相同运算符 / 常量及同一有序前提代表的定义合并到首次代表，使用紧凑代表编号；不同自由符号绝不合并。不交换参数、常量折叠、内联、改变活动位或推导新语义。

入口检查原定义编号连续、所有引用指向更早 term、只有一个 assert、自由声明数与真实 QuerySymbol 相同。估算只计算相应渲染的字节量；它没有生成新的 EncodedQuery、改变 query profile、校准模型文法或验证 solver 性能。

| 计数 / 估算列 | 最小字节 | 最大字节 | ≤ 1 MiB 的份数 |
| --- | ---: | ---: | ---: |
| 原 query_bytes | 42,577,698 | 65,831,615 | 0 / 72 |
| 仅 short_names_bytes | 7,947,828 | 12,450,353 | 0 / 72 |
| 仅 live_bytes | 8,618,733 | 32,741,211 | 0 / 72 |
| live_short_names_bytes | 1,690,383 | 6,242,343 | 0 / 72 |
| shared_short_names_bytes | 3,667,866 | 6,089,913 | 0 / 72 |
| shared_live_short_names_bytes | 1,423,748 | 4,741,435 | 0 / 72 |

全部 72 份各有 166,073–257,480 个原 term，名字出现 524,695–808,807 次。现有编码输出全体构造项，包括不被所选断言引用的 guarantee / 中间求值；相同类型化运算也没有全局共享。固定容量的输入键检查、lookup 和双向覆盖又带来槽位对比较，不能只靠序列化名字解决规模问题。

五类目标的区分如下；份数包含旧 profile 兼容重复，不把它计作独立语义用例数：

| 目标 | 份数 | 原 query_bytes | shared_live_short_names_bytes |
| --- | ---: | ---: | ---: |
| numeric-range | 24 | 42,634,592–42,792,417 | 1,460,828–2,504,310 |
| totality | 18 | 42,577,698–42,735,154 | 1,423,748–1,487,267 |
| key-cardinality | 12 | 50,414,431–50,579,189 | 2,129,692–2,193,948 |
| row-coverage | 6 | 65,636,840–65,831,615 | 4,669,191–4,741,435 |
| contract-guarantee | 12 | 42,577,947–42,735,403 | 3,064,582–3,091,370 |

## 可选择路径与停止线

| 路径 | 需要另外审阅的决定 | 当前判断 |
| --- | --- | --- |
| 新的紧凑查询 profile | 从根公式生成需要的 DAG、短名字 / 共享 / 小项编码和关系构造；精确确定性字节、符号来源 / 模型对应、预算、语义及旧版隔离验收 | 建议的后续尺寸方向；上述估算不足以确定最终方案，不能原地改四版 query 或自动接受新 profile |
| 新的执行资源 profile | 明确 stdin / stdout / 内存 / 时限，固定 payload 与实际校准 / 硬限制，保留旧 profile 身份 | 本次没有 solver 内存 / 时间数据；放宽 stdin 不能说明旧 128 MiB / 6 s 可承受，不能仅凭序列化尺寸接受 |
| 缩小 AX-B01 容量或删接口 / 义务 | 改变实际声明域与基准验收范围 | 不用于解除原容量阻断；新小域材料只能单独作为合成诊断 |
| P4-B 直接 world 重放 | 精确 WF / Pre、数学求值、五类目标、内部观察 / 预算与有限独立验收 | 可以先推进；不伪造 sat、request 或真实 attempt，不改变当前 solver 拒绝 |

新查询实现如果改变名字、项序或内容，必须显式新 profile / 规范摘要，并核对 P4 的请求 / 符号 / 派生项白名单及完整绑定；不能改完字节复用旧 raw digest。真实工具校准 / 执行、安装、服务与远程动作仍分别授权。本记录不授予其中任何一项。

## 复现与实际验证

```bash
mkdir -p .tmp/p4b-review
cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-ir --example inspect_ax_b01_queries --locked --offline > .tmp/p4b-review/ax-b01-query-sizes.tsv
cmp docs/query/ax-b01-query-size-review/measurements.tsv .tmp/p4b-review/ax-b01-query-sizes.tsv
```

测量表为 UTF-8 / TAB / LF，无敏感输入。raw SHA-256 为 `sha256:643fd0cabec7b25e141cf059bd2e3aa34f59252bfd4d403a7ce3fdaf3cca2b10`。复现的输入、生产基线、精确工具 / 参数和诊断入口均已保留；临时输出不作为唯一证据。记录不外推其他 IR、平台或 capacity。

诊断入口完成本机编译与 72 项实际生成 / DAG 核对；原测量与扩展测量的基线列逐项一致。后续文档 / 格式 / Clippy 与仓库检查结果由本批交接报告，生产测试已有 P4-A 265 项通过记录，不能把本次估算另算为 solver 或证明验收。
