# 2026-10-08 P3-C 本机组件验收

范围：项目所有者接受 [P3-C 审阅](../query/p3-key-cardinality-review.md)后，按 [ADR 0021](../adr/0021-map-filter-key-cardinality.md)增加 map / filter 的 key-cardinality 与显式 v0.3 profile。本文记录实际验证，不改变规范或声称 solver / proof 成立。

## 实现与有限语义

Ready 由来源成功和全部活动局部表达式成功组成，容量前候选使用同一真实求值图；自身容量失败进入目标，来源 / 局部故障由 totality / numeric-range 承担。完整输出键比较只为目标生成，按继承表示 N(N−1)/2 × K 提前收费。旧 profile、旧三类 term 顺序、字节、符号与预算保持。

独立路径实际比较 57 文档、243 查询、9,021 赋值，区分 10 类程序语义变异。AX-B01 三份候选使用完整原容量；小金额世界的 key-cardinality 均无反例，不能由 wrong 文件名推出该 kind 失败。容量前完整行观察与 Ready 已随材料持久保存。

既有 26 份 IR / 482 项义务逐项验收：v0.1 为 115 查询 / 1 资源拒绝 / 284 UnsupportedKind / 56 UnsupportedFeature / 26 check；v0.2 为 127 / 1 / 255 / 73 / 26；v0.3 为 139 / 1 / 226 / 90 / 26。新增 29 项 key-cardinality 请求中 12 项真实生成、17 项因整图功能边界拒绝，P2 集合字节与 ID 保留。

另在生产唯一键谓词上注入合成 O*，16 个赋值区分三类错误；这些重复键不声称能由合法 map / filter 程序产生。材料、基线来源与复现详见 [v0.3 材料](../../contracts/map-filter-query-v0.3/README.md)。

## 验证流水

实施前，原 143 查询 / 5,185 赋值测试通过并采集 `9f843ea` 生产实现的字节及六项预算。第一次命令误用包名 `axiom-ir`，Cargo 返回 exit 101、未运行测试；更正为仓库实际包名 `radishaxiom-ir` 后完成，未改依赖或工具。

首轮 Clippy 因新增预算算术使用 `n % 2 == 0` 触发 `manual_is_multiple_of` 返回 exit 101；按工具链建议改为 `n.is_multiple_of(2)`，不放宽检查或修改数学规则。

首轮新增 5 项精准 Rust 测试通过，完整有限比较耗时约 96 秒。随后补充规划器 0 / 1 / 多槽位与乘积 / 累计溢出回归，6 项新增回归全部通过。最终 `cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline` 共 230 项通过：runtime 56、Darwin store 3、digest 2、IR 169；零失败。既有三 profile 清单回归在全量运行中再次通过。

`cargo +1.97.1-aarch64-apple-darwin fmt --all --check`、`cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings`、`./scripts/check-repo.sh`（1,629 文件）及 `git diff --check` 通过。最终复核将遗漏 Ready 变异改为合法三操作数 assert 组合，避免单操作数布尔运算的表示歧义；独立期望不变，相关 243 查询 / 9,021 赋值及 10 类变异已另行复跑通过（约 93 秒），最终仓库检查再次通过。

## 外部与剩余边界

未调用 solver、模型、跨仓 checker、CI 或其他平台；没有安装依赖、运行长期服务、push 或修改远程状态。本批无五态或证明输出。row-coverage、effect-empty、field-origin、join / group、双世界和 P4 / P7 / P9 仍分别审阅。

全量测试日志保留于 `/private/tmp/radishaxiom-p3c.zC5hMw/workspace-tests.log`，最终精准复跑日志为同目录 `final-cardinality.log`。

临时基线采集文件保留于本机 `/private/tmp/radishaxiom-p3c-v02-baseline.tsv`；可复现基线已持久保存在新材料目录。当前 `dev` 保留先前未推送的 P3-B 提交，本批源码、材料及文档随 P3-C 实现提交，精确修订以 Git 历史为准。
