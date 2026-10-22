# 纯核心字段来源推导 v0.1 独立材料

对应 [ADR 0024](../../docs/adr/0024-core-field-origin-derivation.md) 与[正式规则](../../docs/query/core-field-origin-v0.1.md)。材料只支持内部分析记录的有限核对，不是公共证明、真实反例或独立 checker support。

- 130 份 IR：复用空效果材料的 88 份输入，新增 42 份自有合成输入；全部使用合成数据。原 26 份 IR / P2 的 raw 摘要与完整身份另按冻结清单核对。
- 758 份逐 field-origin 目标的规范记录，含原 161 个位置；覆盖 46 个规则 ID。676 份无静态缺口，82 份保留静态缺口；无缺口不是非干扰证明，有缺口不是泄漏反例。
- 42 个手算区分例覆盖值 / 行控制 / 选择 / 求值上下文、常量后的上游缺口、复合类型摘要、记录兄弟故障、分支、Option 绑定移位、join / group、零 / 巨大容量与 Pre=false。
- 生产测试导出实际 Rust 字节，独立 Python 从 IR / P2 重建并比对；双方拒绝 43 类绑定、目标、规则、标签、角色边、引用、缺口与非规范字节篡改。

`cases.tsv` 每行依次为 case 名、IR 路径、IR raw、目标 ID、记录路径、记录 raw、构建 Steps、PremiseEdges、Descriptors、PathBytes、OutputBytes、导出缺口数。前四项构建用量不因最终剪枝退费；输出字节为导出闭包。`hand-checks.json` 为手算期望，`sources.json` 绑定生成与核验入口及规范来源。规范记录无末尾 LF，不接受手工修补。测试生成器身份固定为 `sha256:` 加 64 个 `a`，仅作合成绑定，不声称对应实际编译源码。

```bash
python3 scripts/generate-p3-origin-vectors.py
python3 scripts/generate-p3-origin-vectors.py --check
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir origins::tests --locked --offline -- --nocapture
```

第一条只重建本目录的自有材料，第二条只读核对；Rust 测试调用 `scripts/check-p3-origin-derivations.py` 检查实际导出并生成临时变异，成功后清理其专用目录。两条生产 / 独立路径不共享标签分析或规则实现，只沿用冻结 P2 / 规范 JSON 工具生成身份。

完整 P1 结构 / 类型正确性仍是前提。节点标签与原 P1 的比较是兼容性回归，不是独立期望；expr.record-field 的局部判断额外显式记录构造字段的声明比较，既不改变 P1 接受集合，也不把缺口伪装为运行故障。深 5,000 层图与类型、预算精确值 / 差一 / 溢出、旧版 / profile 隔离和局部规则拒绝由 Rust 测试另行验证。
