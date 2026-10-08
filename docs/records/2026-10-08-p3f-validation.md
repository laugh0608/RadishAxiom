# 2026-10-08 P3-F 本机组件验收

范围：项目所有者接受[字段来源提案](../query/field-origin-and-p4-interface-review.md)并要求继续实施后，按 [ADR 0024](../adr/0024-core-field-origin-derivation.md)实现内部结构分析。P4、公共 support 与真实外部执行未纳入本批。

## 实际能力与边界

`origins::derive_field_origin` / `check_field_origin` 从完整规范 IR / P2 重建五种节点与逐行表达式的来源、保守标签、行控制和求值上下文，绑定原 field-origin 目标与显式生成器身份。带角色前提的共享 DAG 导出三个根的闭包，不展开类型引用、所有来源路径或容量世界。完整 P1 类型 / 身份仍是明确前提。

独立材料共 130 份 IR / 758 份记录，包含原 26 份 IR 的 161 个位置及 42 份新增合成输入，覆盖 46 个规则。676 份无静态缺口，82 份保留缺口；这两类都不是公共证明、关系非干扰结论或具体反例。42 个手算区分例和 43 类记录篡改由独立路径检查，Rust 对实际导出及相同变异逐项核对。

五项累计用量包含构建步骤、角色边、描述符、路径与最终字节，独立 Python 按固定计数核对。深 5,000 层图 / 类型、共享引用、巨大容量、预算精确值 / 差一 / 零 / 溢出、IR JSON 限额、旧 IR 与 query / effect profile 隔离另由 Rust 回归覆盖。原 P1 逐节点标签与缺口一致性只作兼容性回归，独立期望不读取生产标签结果。

## 验证过程与最终结果

首次组件编译及原 666 份记录比对通过。补充合成材料时，一份“无关缺口”输入含未输出的死节点，被 P1 正确拒绝为 DeadNode；修正为另一个命名输出保留该分支，再验证目标闭包隔离，没有放宽 P1。随后兼容性测试的文档数量断言误写为 131，实际冻结清单为 130；所有标签判断已通过，修正计数后重跑。首轮 Clippy 报两处参数过多，将缺口判断集中到闭合规则入口、去掉冗余布尔参数后通过，没有抑制检查。

首次只读定位曾包含不存在的 `nodes/operators.rs` 路径，rg 报错；改按实际模块读取，无文件或结论影响。

```bash
python3 scripts/generate-p3-origin-vectors.py --check
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir origins::tests --locked --offline -- --nocapture
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline
./scripts/check-repo.sh
git diff --check
```

六项 P3-F 精准回归通过，耗时 5.66 秒，独立材料 / 五项预算 / 手算与篡改一致。完整 workspace 共 247 项通过、0 失败（runtime 56、Darwin store 3、digest 2、IR 186，其中 IR 单元 95、集成 91）。旧四版 query 清单回归通过，耗时 186.94 秒。格式与 Clippy 通过；仓库检查通过，共检查 2,564 个文件，包含全部新生成材料和文本 / 链接。旧 IR / P2 / query / effect 规范、材料、实现及依赖与 lockfile 的精确路径 diff 为空。

## 外部状态与留存

未安装 / 升级依赖、启动服务、调用 solver / Node / 跨仓 checker、触发 CI 或修改远程状态。本批未提交；`dev` 仍有四个既有未推送提交，最近一次为 P3-E `47e3ff9`。其他平台未执行。

过程与结果日志保留在 `/private/tmp/radishaxiom-p3f-first.log`、`radishaxiom-p3f-expanded.log`、`radishaxiom-p3f-expanded-2.log`、`radishaxiom-p3f-precision.log`、`radishaxiom-p3f-precision-2.log`、`radishaxiom-p3f-clippy.log`、`radishaxiom-p3f-clippy-2.log`、`radishaxiom-p3f-workspace.log` 、`radishaxiom-p3f-clippy-final.log`、`radishaxiom-p3f-repo.log` 与 `radishaxiom-p3f-repo-final.log`，均位于 `/private/tmp`。失败测试的专用临时导出目录保留用于追溯；成功测试清理其自建目录。可重跑源码、输入与期望保存在[版本化材料](../../contracts/core-field-origin-v0.1/README.md)。
