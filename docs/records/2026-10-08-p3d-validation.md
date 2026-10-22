# 2026-10-08 P3-D 本机组件验收

范围：项目所有者接受 [P3-D 审阅](../query/p3-row-coverage-review.md)后，按 [ADR 0022](../adr/0022-map-filter-row-coverage.md)增加 row-coverage 与显式 v0.4 profile。此记录用于实际验证与失败归因，不改变规范，也不代表 solver / proof 结果。

## 实现与材料

Ready 守卫容量前候选；目标关系为所选直接源行与实际输出的双向恰好一次全键匹配。map 按规范键字段投影支持重命名及键序变化，filter 的参考选择先于输出 active 构造；不额外求值谓词，不引入自由输出。N²K 比较成本在分配前核验，两方向流式计数，全部临时数组 / term / 边 / 字节继续受预算约束。

新材料含 60 文档、336 查询和 12,553 个目标 / 世界赋值。完整路径另核对 Ready、选择、期望键及活动输出；局部合成关系单独覆盖非法候选，不能当作合法程序反例。来源、生成入口、基线、局部变异与复现命令见 [v0.4 材料](../../contracts/map-filter-query-v0.4/README.md)。

## 已发生的验证与修复

实施前的 v0.3 比较通过，并从 `9b8f71f` 生产源码采集原 243 查询的摘要和六项用量。旧规范、材料、脚本及依赖字节保留。

首轮编译 exit 101：新 `tests/row_coverage.rs` 的 `include_str!` 沿用了上一层文件的相对路径，少一个 `..`，未运行新测试。修正为真实五层相对路径，不修改基线内容；原日志保留于 `/private/tmp/radishaxiom-p3d-precision.log`。此前一次只读搜索使用不存在的目录 glob，由 zsh 拒绝；改按真实文件读取，对实现无影响。

修正后的六项精准测试全部通过（129.42 秒），覆盖绑定 / 预算 / 规划溢出 / 深图及拒绝。完整有限比较通过 336 查询 / 12,553 赋值 / 3,016 个中间观察，区分三类观察变异；生产局部关系的 648 个合成赋值区分 12 类变异。旧 key-cardinality 规划算术回归通过。格式与 Clippy 通过。

workspace 实际 236 项通过、0 失败（runtime 56、Darwin store 3、digest 2、IR 175），其中 IR 单元测试 84 项、集成测试 91 项。四 profile 清单测试通过（193.71 秒）：v0.1 / v0.2 / v0.3 计数保持，v0.4 在既有 26 份 IR / 482 项义务中实际生成 151 查询，另有 1 项资源拒绝、197 项 UnsupportedKind、107 项 UnsupportedFeature 与 26 项 check；新增 12 条 row-coverage，其余 17 条新 kind 目标明确拒绝图功能。

已运行命令：

```bash
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir query::tests::row_coverage --locked --offline -- --nocapture
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline
./scripts/check-repo.sh
git diff --check
```

格式、Clippy、仓库检查和 diff 文本检查均通过。最终复核不改旧三版 query 规范 / 材料、冻结解释器或 Cargo 依赖。等待期间一次只读 `ps` 进程查询被沙盒拒绝（exit 127）；未提权，继续从既有测试会话及日志观察结果，不影响测试执行。

## 外部与工作区

未安装或升级依赖，未调用 solver、跨仓 checker、CI 或其他平台；未启动长期服务、push 或修改远程状态；验收后按项目所有者要求提交本批代码。effect-empty、field-origin、join / group、双世界、结构证书和 P4 / P7 / P9 保留各自范围。当前 `dev` 保留两个既有未推送提交，本批源码、材料及文档一并提交，精确身份以 Git 历史为准。

基线采集临时文件为 `/private/tmp/radishaxiom-p3d-v03-baseline.tsv`（已持久保存到新材料目录），运行日志为 `/private/tmp/radishaxiom-p3d-baseline-test.log`、`/private/tmp/radishaxiom-p3d-precision-2.log`、`/private/tmp/radishaxiom-p3d-workspace.log`。测试目录仅成功时自动删除，失败保留以便定位。
