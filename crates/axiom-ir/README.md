# Axiom IR 内部组件

本 crate 承载 [ADR 0016](../../docs/adr/0016-core-semantic-slice-entry.md) 的 P1 实施。当前只实现 [IR v0.1](../../docs/ir/axiom-ir-v0.md#json-与标量规范化) 的 JSON 字节边界；没有完整 IR 成功入口，也不提供 CLI。

## 输入与输出

`json::canonicalize_json(bytes, limits)` 接受有界 UTF-8 JSON，禁止 number / null，拒绝重复解码成员名、非法语法和未配对 surrogate。输出按 UTF-16 code unit 排序对象成员，采用最小字符串转义，无 BOM、额外空白或末尾换行。数组顺序与字符串内容保持原样，不做 NFC、大小写折叠或十进制字符串改写。

返回 `Ok` 仅表示该 JSON 子集的解析与编码成功。例如 `true`、`{}`、名称中的转义控制字符、`"-0"` 和未知 IR 字段都可以通过本层；它们是否为合法 IR 仍须领域层判定。当前未实现精确成员、版本 / 语义摘要、名称约束、数学整数、类型 / 效果、引用 / DAG、契约结构、规范数组排序和内容身份。不能将此函数输出标成已经验收的 canonical IR 或 Evidence。

## 资源与诊断

调用方必须显式提供 `JsonLimits`，没有无限预算的默认入口：

- `max_input_bytes` 在 UTF-8 解码前检查，约束输入、解码字符串总量和规范输出字节量；本子集输出不长于合法输入。
- `max_values` 计数所有值及对象成员名，限制树分配与宽对象排序规模。
- `max_nesting` 限制同时打开的数组 / 对象层数，实际不超过实现上限 128；标量不消耗层数。解析、编码和树销毁均受此上限约束。

错误包含类别及原输入的零基字节位置。非法输入与 `ResourceLimit` 分开；先遇到预算限制时只报告未完成处理，不推断输入是否合法。对象重复键指向第二次出现的成员名。此内部诊断尚未映射为 pipeline stage result。

这些是组件规模限制，不是 OS 硬内存 / 时限隔离，也不保证宿主分配失败可恢复。UTF-8 检查、字符串处理和编码按输入规模进行；对象排序按成员数量及键长度消耗资源。

## 实现与验收边界

Rust 2024，`publish = false`，仅标准库、禁止 unsafe，无第三方依赖、build script、过程宏或 native / FFI。与 runtime 的 ASCII 闭合文档 parser 分开：这里处理完整 Unicode JSON，未来用于 IR 类型检查；不更改旧 runtime 的协议或信任边界，不让独立 checker 复用生产实现。

测试期望来自人工推导的规范向量、Unicode 标量与转义的数学对应关系，以及仓库既有的四题 12 个 candidate `.ir.jcs`；不调用生产 helper 生成期望。`correct` / `wrong` 候选同样只做 JSON 层回归，不据标签判定算法。负例覆盖语法、无效 UTF-8、代理对、解码重名、截断和规模边界。

已安装并验收的宿主工具可按仓库约定离线执行：

```bash
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir --locked --offline
```

完整 workspace 验证见[当前状态](../../docs/status/current.md#验证入口与本次审阅)。测试不是形式证明；未运行平台不能据此声称字节一致性已验收。
