# P4-A 请求 / 响应 / 模型解码本机验收

日期：2026-10-12。范围：[ADR 0025](../adr/0025-p4-request-response-model-decoding.md)与[正式规则](../query/p4-request-response-model-v0.1.md)接受的内部纯组件；本记录只报告本批实际观察，不替代规范或真实工具验收。

## 实际交付

`crates/axiom-ir/src/solver.rs` 提供请求规划、响应解析、模型到世界候选解码，以及请求 / 候选的严格重建比较。请求从不可变 IR v0.2、完整 ir-derived P2 和实际 query 重建绑定、全部自由符号、已知派生名称与完整输入类型布局；原 stdin 字节保持。工具 / acceptance 身份是声明，新内部 adapter 保持 `planned-not-calibrated`。

正常解析只接受显式固定文法，保留 unknown 及其可选模型而不形成 world。退出 / 外层终止 / 流完整性 / 字节上限优先于语义输出；缺项、重复、错 sort、未知成员、别名环与未支持 term 拒绝。世界只物化活动行 / Some 载荷，保留数学整数、Fixed / Enum / Record / Option、Text 精确相等及既有键序；非法活动值与重复键拒绝。候选没有 Evidence 五态、attempt、证明或具体目标反例结论。

## 验收材料与结果

- 新增 18 项 Rust 回归覆盖绑定、四个 profile / 五类原目标、帧 / 退出 / 终止、完整性、alias、辅助项、Text、活动 / 遮蔽载荷、类型 / 键、严格制品、预算与深度。
- 53 份既有 P3 合成 IR，各选择实际 guarantee 目标，独立 Python 从原 IR / 实际 SMT 重建符号、布局和完整接口空世界，逐字节核对请求伴随制品、响应观察与候选。Pre=false / fault 材料也只形成候选，不当成有效反例。
- 一份新的复合 IR 包含两接口、稀疏槽位、100 位整数、Fixed、非词法 Enum 成员序、嵌套 Option / Record、Unicode 和复合键。完整叶模型与手算完整语义值分别书写，独立路径核对原帧及交换定义顺序的帧；world / Text 映射字节相同，响应与整体候选摘要按原字节变化。
- Text atom 重命名、literal 冲突、合成字符串撞已知 literal，以及隐藏类不外部化分别核对；有限样例不声称还原模型中的原字符串。
- 新深度材料保留原自有材料的 5,002 个记录类型，图为直接输入输出。先复现逐层复制完整路径导致 Request / ValueCells 拒绝，再改为显式路径栈、只在叶 / Option 标签复制。最终请求布局与空 / 活动世界通过；活动 world 含 5,002 个 record 值，编码与销毁不依递归所有权。原深图字节没有改写，新材料不用于绕过原请求上限。
- 资源验证保留各阶段精确值 / 差一、巨大整数、深帧、输入 / 输出上限和累计溢出拒绝。模型语法、别名与排序逻辑收费不是 OS 墙钟或硬内存保证。

期望来源、再生成与独立检查入口见[合成材料](../../contracts/solver-model-v0.1/README.md)。这些 stdout 是合成协议材料，可以只满足文法与类型而不满足实际 query；本批没有将它们作为真实 solver model 或目标违反证据。

## AX-B01 的实际停止条件

三份原容量候选 / 四个 query profile 共实际生成 72 份已支持 query。P4-A 规划全部返回 `Request / StdinBytes` 资源拒绝，成功请求数为 0：每份 query 均超过沿用的 1,048,576 字节 stdin 上限。五类目标仍由原 P3 profile 生成并保留，未缩小容量、静默增限、追加命令或重用错误摘要。

这是新入口暴露的实际纵向阻断，不是 compiler 错误候选的反例，也不是 solver unknown。下一项须单独审阅查询尺寸 / 资源对应关系；P4-B 的纯重放设计可按自身依赖接续，但原容量 AX-B01 的真实尝试仍被阻断。

开发反馈中曾误用大小写用例名导致 AX-B01 集合未被选中，已改为实际 `ax-b01-*` 清单；选中后“至少有一份成功请求”的测试假设被实际尺寸拒绝推翻，最终验收固定为 72 份拒绝。Text 预算例也由空 literal 改为真实新类分配，覆盖非零收费。这些修正没有放宽生产限制或删除失败材料。

## 实际验证

宿主沿既有 macOS arm64 工具前提，使用显式 `1.97.1-aarch64-apple-darwin`；没有安装或升级依赖。

```bash
python3 scripts/generate-p4a-model-vectors.py --check
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline
./scripts/check-repo.sh
git diff --check
```

上述检查通过。最终 workspace 共 265 项测试通过：runtime 56、Darwin store 3、digest 2、IR 204（含本批 18 项）。旧 IR / P2 / query / 结构记录 / Evidence、工具登记、execution profile 与锁定材料的生成一致性检查通过；Rust 测试还核对旧查询字节与预算回归。仓库检查新增本批材料只读核验，没有放宽原检查。

最终完整 Rust 回归日志保留在本机已忽略的 `.tmp/p4a-validation/workspace-tests.log`；规范、生成入口、输入和期望都在仓库。独立检查临时目录成功后只清理本次创建的精确目录；失败时保留路径。开发中失败回归及对应原因记录于上文，不把有限核对计作形式证明。

## 兼容性、信任与外部状态

P4-A 只新增版本化内部请求 / 响应观察 / 世界候选，不迁移旧公共 Evidence、registry 或 adapter。完整 WF / 全部 Pre / 五类精确目标重放、真实 cvc5 校准 / 执行、proof / certificate、跨仓 checker、六平台和正式 Agent 实验均未执行。独立 Python 核对不是独立 checker 的证明链，合成进程退出观察不认证 stdout 来源。

本批仅本机代码 / 文档 / 合成材料与验证；没有新增依赖、改 lockfile、启动长期服务、修改系统或兄弟仓、提交、push、PR、tag / Release、发布、部署或外部消息。工作区在 `dev`，本批变更未暂存、未提交；相对本地 `origin/dev` 无 ahead / behind，未刷新远端。没有本任务遗留后台服务；本机验证日志保留供复核。
