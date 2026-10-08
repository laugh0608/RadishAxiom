# 2026-10-08 P3-B 本机组件验收

用途：保存本次实施事实、失败修复与实际验证范围；不替代 [ADR 0020](../adr/0020-map-filter-node-totality.md)、[编码规则](../query/map-filter-query-v0.2.md)或[当前状态](../status/current.md)。

## 交付

项目所有者接受 [P3-B 精确审阅](../query/p3-node-totality-review.md)后，在原 Rust 查询入口增加显式 QueryProfile 与 totality。目标使用指定节点 ok，保留依赖故障而不混入无关节点 / guarantee；v0.1 支持与原查询字节保持。

P2 definition、ID、生成位置和集合保持原样，旧规则、v0.1 语义材料及其摘要绑定的 Python 源码没有改写。新来源与数据由 [v0.2 材料](../../contracts/map-filter-query-v0.2/README.md)记录。无新增依赖或 lockfile 变化。

## 实际验证

主机为已有工具链的 macOS arm64；使用显式 Rust `1.97.1-aarch64-apple-darwin`，所有 Cargo 验证使用已有依赖并离线执行。

| 验证 | 结果 |
| --- | --- |
| 改动前 P3-A 独立比较 | 原 68 查询 / 2,394 赋值通过；从实际输出采集兼容摘要基线 |
| P3-B 定向 Rust 回归 | 新增 5 项通过，含 profile / 绑定、篡改、预算、深图、unsupported 与无 guarantee |
| P3-B 独立语义比较 | 50 份文档、143 查询（60 totality、49 guarantee、34 range）、5,185 赋值、8 类错误语义变异通过 |
| 原两类兼容性 | 原 68 个查询在 v0.1 / v0.2 均核对改动前摘要；同一旧目标 SMT 字节相同而 profile 绑定不同 |
| 既有完整 P2 清单 | 两个 profile 都核对全部 26 份 IR / 482 项位置，结果见下表 |
| `cargo +1.97.1-aarch64-apple-darwin fmt --all --check` | 通过 |
| `cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings` | 通过 |
| `cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline` | 224 项通过：runtime 56、Darwin store 3、digest 2、IR 163 |
| `./scripts/check-repo.sh` 与 `git diff --check` | 通过；覆盖新旧材料生成一致性、链接和文本卫生 |

| profile | 实际查询 | 容量资源拒绝 | 未支持义务种类 | 文档功能拒绝 | check 义务 |
| --- | --- | --- | --- | --- | --- |
| v0.1 | 115 | 1 | 284 | 56 | 26 |
| v0.2 | 127 | 1 | 255 | 73 | 26 |

新增 12 条来自先前静态形状内的 totality；另外 17 条 totality 仍因整图功能范围拒绝。AX-B01 correct 与两个 wrong 各生成两个真实完整容量 totality 查询，小额样本均未发生节点故障；这不掩盖 wrong 的业务保证失败，也不证明完整域 totality。其他平台、实际 cvc5 / Node / Go checker、模型 / proof、Evidence 与完整 P3 均未验收。

## 首轮失败与修复

首轮定向测试退出 101：新增 `renamed-key` 合成样本未在键重命名后重新按字段名排序，P1 报 node 内容 ID 不匹配，尚未进入该样本 P3。独立样本生成器现先排序字段，再计算节点身份及输出绑定；未放宽生产 strict 检查，也未改动其算法。

修复后重新生成新 v0.2 材料，定向 5 项与完整 workspace 均通过。该失败是测试输入身份错误，不是 solver、生产 totality 结论或旧材料失效。首次失败导出的临时查询材料保留，成功运行的查询临时目录已由测试删除；不把临时目录当正式复现入口。

## 工作区与外部状态

本批在原 `dev` 上实施，包含先前未提交的三份审阅文档改动，没有覆盖任务外修改。验收完成时尚未暂存或提交；未 push 或创建 PR；未安装依赖、启动长期服务、修改系统、跨仓写入或调用真实 solver。完整测试日志与基线采集的临时副本留在任务临时目录，正式材料及复现入口已在仓库中。

下一步应审阅 key-cardinality / row-coverage 的成功与故障观察边界，尤其 filter 容量目标不能被 nodeOK 前提屏蔽；不据本批验收自动增加其余义务或外部执行范围。
