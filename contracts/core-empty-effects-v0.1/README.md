# 纯核心空效果推导 v0.1 独立材料

对应 [ADR 0023](../../docs/adr/0023-core-empty-effect-derivation.md)与[正式规则](../../docs/query/core-empty-effects-v0.1.md)。只服务内部结构推导、字节与拒绝验收；不是 Evidence、kernel support 或证明证书。

## 来源与生成

`scripts/p3_effect_derivation.py` 按闭合规则和作用域重建完整记录，使用 Kahn 队列处理共享图；生产 Rust 使用 P1 已检查的拓扑信息计算深度，并独立遍历构造。Python 不调用 Rust，不读取生产步骤或成功标志作为期望。完整 P1 类型正确性是明确输入前提；该脚本不冒充另一份完整 P1。

`scripts/generate-p3-effect-vectors.py` 复用原 26 份 IR / P2、P3-D 语义材料及既有容量 / 量化资源输入，共 88 份独立记录、46 个规则 ID，覆盖正式规则全部构造。原 26 份输入与独立 P2 集合摘要必须继续等于冻结清单。未新增数据或依赖，旧输入、规范、脚本原字节保留。

`records/*.jcs` 为规范完整记录；不手工编辑。`cases.tsv` 无表头，九列依次为案例名、仓库相对 IR 路径、IR raw SHA-256、仓库相对记录路径、记录 raw SHA-256、Steps、PremiseEdges、PathBytes、OutputBytes。生成器身份固定为 `sha256:` 后接 64 个 `a`，仅供合成验收，不声称是实际构建身份。`sources.json` 登记生成入口、规则、规范编码 helper 与来源清单的字节摘要。

```bash
python3 scripts/generate-p3-effect-vectors.py
python3 scripts/generate-p3-effect-vectors.py --check
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir effects::tests --locked --offline -- --nocapture
```

## 真实路径与负例

Rust 测试从真实 P1 / P2 生成记录，逐字节、摘要及四项用量核对独立向量，再导出到测试专用临时目录。`scripts/check-p3-effect-derivations.py` 读取这些实际字节，重建全部记录，并导出 28 类精确篡改供 Rust strict 再拒绝：七个绑定字段、format / version / rule_profile / root、步骤缺失 / 重复 / 逆序、未知成员、错误规则 / 路径 / anchor、前向引用、缺失 / 额外前提，以及 if / match_option / record / sum_where / join / group / noninterference 的指定前提缺失。额外空白另行拒绝。

七类合成坏树覆盖非空效果、节点隐藏能力、外部节点、死分支外部表达式、表达式隐藏成员、越界 bound 和 assume 读取 output。它们不是合法 P1 程序；Python 效果规则拒绝、Rust P1 拒绝与内部规则局部注入拒绝分别核对，不把损坏身份或语法输入当成程序数据反例。

资源测试包含四项精确预算 / 差一 / 零、累计溢出、IR JSON 字节 / 值上限、候选字节限制、5,000 层图和共享类型、超大容量与深有限量化。深图实际产生 10,006 步，不按数据容量或输入世界展开。旧 IR、错误集合 / 目标 / 生成器、规范化前数组换序与四个旧 query profile 的拒绝也单列。

成功后删除测试导出目录，失败保留诊断；生成材料检查已接入仓库门禁。实际命令与结论见[本批记录](../../docs/records/2026-10-08-p3e-validation.md)。本批不核验字段业务来源、非干扰、目标总性或外围效果，未接入 solver、公共 Evidence 或跨仓 checker。
