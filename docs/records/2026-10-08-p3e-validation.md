# 2026-10-08 P3-E 本机组件验收

范围：项目所有者接受[接续审阅](../query/p3-structural-obligations-and-p4-review.md)中的 P3-E 范围后，按 [ADR 0023](../adr/0023-core-empty-effect-derivation.md)实现纯核心空效果结构推导。field-origin 与 P4 未纳入本批实施。

## 实现与证据

生产入口为 `effects::derive_empty_effects` / `check_empty_effects`，使用显式 `CoreV0_1` profile、完整 P1 / P2 绑定、已有 GeneratorIdentity 和四项累计预算。完整构造后序推导、接口与前驱引用、空声明 / 全文档根进入规范记录；不展开表容量或共享前驱。没有五态、kernel / certificate support 或执行门控。

独立向量为 88 份记录，覆盖 46 个规则 ID，包括原 26 份 IR / P2 和 query 不支持的纯构造。Python 规则重建与 Rust 完整字节 / 摘要 / 用量一致；28 类记录变异由两条路径拒绝，七类合成坏树分别由独立规则、P1 与局部规则拒绝。P1 完整类型正确性仍是输入前提，不把有限材料核对外推为完整独立证明。

五项定向测试通过，第二轮耗时 1.88 秒；资源、旧版本、绑定与顺序测试均通过。深 5,000 层图实际 10,006 步；巨大容量与量化不展开为输入世界。首轮实现编译、精准测试及 Clippy 均通过，复核后去除一份不必要的临时输出索引数组，并增加独立坏树在 Rust 规则中的拒绝核对；再次精准测试通过，没有通过放宽规范或预算消除失败。

初始只读定位曾包含不存在的猜测路径，由 rg / head 报错；改按真实目录读取，无文件写入或验证结论影响。

## 命令与最终结果

```bash
python3 scripts/generate-p3-effect-vectors.py --check
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir effects::tests --locked --offline -- --nocapture
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline
./scripts/check-repo.sh
git diff --check
```

精准、格式、Clippy、仓库检查与 diff 文本检查全部通过；workspace 共 241 项通过、0 失败（runtime 56、Darwin store 3、digest 2、IR 180，其中 IR 单元 89、集成 91）。旧四 profile 清单测试通过，耗时 193.95 秒。仓库检查包含本批生成一致性，共检查 1,746 个文件。旧 IR / P2 / query 规范及材料、依赖与 lockfile 的精确路径 diff 均为空。

## 外部状态与留存

未安装依赖、启动服务、调用 solver / Node / 跨仓 checker、触发 CI、修改远程状态或执行其他平台。验收结束时 P3-D 已提交为 `a008520`，本批及此前接续审阅未提交，`dev` 保留三个既有未推送提交；随后项目所有者要求先提交工作区更改再继续，本批据此提交。没有 push 授权。

日志保留于 `/private/tmp/radishaxiom-p3e-precision.log`、`/private/tmp/radishaxiom-p3e-precision-2.log`、`/private/tmp/radishaxiom-p3e-workspace.log`。独立材料生成入口与复现方式见[材料说明](../../contracts/core-empty-effects-v0.1/README.md)。旧规范、锁定材料、query 与依赖字节不改。
