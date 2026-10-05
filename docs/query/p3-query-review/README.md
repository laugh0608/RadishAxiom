# P3 查询编码审阅材料

状态：范围已由 [ADR 0019](../../adr/0019-map-filter-query-encoding.md) 接受；本目录仍是静态审阅材料，不是 solver 执行、Evidence 或独立证明。实际组件材料见[查询验收](../../../contracts/map-filter-query-v0.1/README.md)。

[审阅正文](../p3-query-encoding-review.md)提出首个 map / filter、numeric-range / contract-guarantee 内部切片。[materials.json](materials.json)绑定正文、生成入口、26 份现有 IR 与实际 P2 集合，并逐项列出全部 482 个义务 ID 的静态分类。candidate-by-shape-only 只表示本提案功能边界内的候选；没有评估展开预算，也不表示 query 已生成。其余义务没有从 P2 集合删除。

材料另含 22 个标量区分和 6 个资源区分。标量例独立于 Rust，检查显式布尔 / 整数等式与手写期望，包含故障、Pre、Reach、循环守卫、Text、Option 和两个 AX-B01 业务错误的示意。资源例仅检查分配前的有界乘积与容量拒绝。它们不消费 IR 求值、不生成 SMT、不复用历史 expected outcome，也不能替代后续 IR 具体解释器与 SMT AST 解释器的差分验收。

本仓自有合成材料，无新第三方代码、依赖、实际输入或工具调用。

```bash
python3 scripts/generate-p3-query-review.py
python3 scripts/generate-p3-query-review.py --check
```

修改设计后重新生成并审阅字节差异；仓库检查使用只读 `--check`，不自动修复漂移。P2 规范与旧绑定保持原字节。
