# 2026-10-13 P4-B 有限具体目标重放验收

用途：记录项目所有者于 10 月 12 日接受 [ADR 0026](../adr/0026-p4-concrete-target-replay.md) 后的实施与 10 月 13 日接续验收，供维护者复核。本记录不报告真实 solver、完整 Evidence、形式证明或产品管线完成。

## 实际交付

生产入口为 `replay::replay_target` / `check_target_replay`，规则为 [P4-B v0.1](../query/p4-concrete-target-replay-v0.1.md)。从实际 IR v0.2 / 完整 P2 / 精确目标及直接 world 或绑定模型候选重建来源、WF、全部 Pre 和五类目标观察；直接世界路径不生成 SMT，也不受 solver 请求尺寸门禁替代语义判断。

复用 P1 不可变类型、图与规范表达式、P2 不可变完整集合、已有数学整数比较和 JCS 字符串编码。新十进制加减、平坦值、实际求值、容量前关系及故障归因位于 `crates/axiom-ir/src/replay/`；模型路径只用 P4-A strict 重建验证来源一致性。没有依赖变更或 solver / 进程执行入口。

重放记录保存完整绑定、规则 raw、world raw、来源、显式 limits、实际收费与确定性首见证。`target-violated` 仅表示这份 WF / Pre 合法输入违反所选目标；`target-not-violated` 不能外推普遍成立。预算、格式、绑定与未支持错误没有部分成功制品。

## 实际有限材料与判定

| 材料 | 核对内容 / 结果 |
| --- | --- |
| P3 四版既有 207 个 case 条目 | 29,153 次有限目标观察与完整见证逐字节匹配独立 Python；四版分别为 2,394 / 5,185 / 9,021 / 12,553 次。重复出现的旧 case 不是新增语义覆盖 |
| 新增手算 / 合成材料 | 45 次精确目标观察匹配，包括原 AX-B01 三候选、两个独立 guarantee、声明的 lookup 外键式 assume、巨大容量与复合值 |
| 数学值与求值路径 | 80,802 次小整数加减对照宿主安全小域；100 位进退位 / 正负抵消手算；既有 Fixed、Option / Some 环境移位、严格兄弟、未选分支与子故障范围位置 |
| 输入拒绝 | 范围、Enum 成员、容量与重复键分别 input-rejected；非规范行序、整数词法、错序 / 缺失字段、重复对象成员、number / null、UTF-8 / surrogate / 转义与 BOM 分别拒绝 |
| 深度 | 5,002 个 Record 类型的实际活动世界；1,500 层依赖链定位原 range 根因。解析、值、cause 与观察编码 / 销毁使用平坦索引；不以宿主调用栈展开这些链 |
| 来源 | 合成 SatModel / candidate 与直接同世界得到相同语义观察、不同制品身份；模型打印顺序 / Text atom 改名不改变 world，响应与候选身份仍不同；错响应 / 错目标拒绝，unknown 无 SatModel |
| 资源 | 13 类预算各自精确值、差一与累计溢出；长 Text 公共前缀、10,001 位整数拒绝；巨大声明容量不展开槽位；输出先构建有界编码序列并计数后分配 |
| 局部关系材料 | 仅测试中向实际关系函数注入重复键、遗漏、额外、重复次数与复合键差异；双向恰好一次和 NFC / NFD 区分通过。这不是完整合法程序产生的覆盖反例 |
| 未支持功能 | join / group 图，以及保证公式未选分支中的 exists_rows，均在 world / 执行前拒绝 |
| strict 与独立变异 | 生产 strict 拒绝绑定、world、目标、来源、预算和见证改动；独立 Python 重建 P2 / 绑定 / 有限见证，并实际拒绝 10 类制品或输入篡改 |

AX-B01 的三个原 IR、全部表容量 100 与既有 query 字节保持。在同一输入中，已结算 `a` 的 subtotal / discount 为 10 / 10，已结算 `b` 为 20 / 5，待处理 `c` 为 8 / 0：

| 候选 | 手算输出 | guarantee | 内建 coverage |
| --- | --- | --- | --- |
| correct | `a:0, b:15` | 当前输入未违反 | 当前输入未违反 |
| wrong-add | `a:20, b:25` | 当前输入违反 | 当前输入未违反 |
| wrong-drop-zero | `b:15` | 当前输入违反 | 当前输入未违反 |

原 P3 材料另核对自身容量超限但覆盖完整、Ready false、不相关 / 上下游失败、其他 guarantee false、Pre false / fault 等区别，避免把一个全局失败位当作所有目标的答案。

## 可重跑入口与独立性

- `scripts/generate-p4b-replay-vectors.py <目录>` 读取四版原 IR / world / target；复用既有自有 `p3_query_semantics.py` 值解释，并以 `p4b_replay_semantics.py` 增补动态 context、首见证与容量前目标观察。
- `scripts/generate-p4b-hand-vectors.py <目录>` 生成手算、深度和拒绝材料；复用既有合成 IR 构造入口与 P4-A 独立手写复合值，不修改原输入。
- `scripts/check-p4b-replay.py <目录> --mutations` 从导出的 IR / P2 / world / 调用参数核对观察，测试负责导出并实际调用。Python 不导入 Rust replay 或 SMT；费用只核对输入 limits、上限和输出字节，生产费用的精确边界由 Rust 回归核对。该脚本仅验收测试中有限支持材料，不是通用独立 checker。
- Rust `replay` 测试实际调用这些脚本并逐字节比较完整观察 / 见证，不把生成器输出不加比较地当成功。

```bash
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir replay --lib --locked --offline
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline
./scripts/check-repo.sh
```

P4-B 新增 12 项 Rust 回归通过；完整 workspace 共 **277 项**通过（runtime 56、Darwin store 3、digest 2、IR 216）。格式、Clippy（含全部 targets / features，warnings 为错误）与仓库检查通过，仓库检查覆盖 2,606 个文件。输入临时索引收费收尾后，最终 P4-B 12 项回归和 Clippy 再次通过；其他模块字节未变。完整日志保存在忽略目录 `.tmp/p4b-validation/`，复现不依赖日志独有数据。

开发过程中补齐了中断时缺少的输入 / 目标 / 输出模块，并修正编译接口、测试值复制与 Clippy 问题；故障结果没有通过放宽检查隐藏。资源复核将完整功能扫描、图缓存和输出编码工作接入预算，预算差一继续返回 ResourceLimit。原规范 / IR / P2 / query / P4-A / lockfile 没有修改。

## 外部影响与接续

没有执行真实 cvc5、安装 / 更新依赖、启动后台服务、修改系统、跨仓写入、push、PR、发布或触发 CI。其他平台、真实独立 checker、完整 Evidence v0.2、反例最小性与正式 Agent 实验未验收；有限动态核对和生产 strict 不升级为证明。

验收时工作位于 `dev`；前批 P4-A 提交 `b86eb33` 保留。本记录验收时，本批 P4-B、原会话尺寸诊断及文档尚未暂存、提交或推送；本地 `origin/dev` 未刷新。忽略目录 `.tmp/p4b-validation/` 保存本机验证日志；测试专用系统临时目录使用合成数据，失败材料及深度 / 手算材料可留存，生成源码已纳入本批可审阅文件。

下一项审阅 AX-B01 新查询表示的精确范围与等价性 / 模型布局验收，保留[尺寸诊断](../query/ax-b01-query-size-review.md)的 1 MiB stdin 阻断；真实工具校准、资源改变和完整 Evidence 另行决定。无需先扩大 join / group、结构证明支持或产品 runtime 才能审阅该阻断。
