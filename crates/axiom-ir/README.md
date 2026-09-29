# Axiom IR 内部组件

本 crate 承载 [ADR 0016](../../docs/adr/0016-core-semantic-slice-entry.md) 的 P1 实施。当前实现 [IR v0.1](../../docs/ir/axiom-ir-v0.md) 的 JSON 字节边界、类型声明解码及声明规范化 / 内容身份核对；没有完整 IR 成功入口，也不提供 CLI。

## 输入与输出

`json::canonicalize_json(bytes, limits)` 接受有界 UTF-8 JSON，禁止 number / null，拒绝重复解码成员名、非法语法和未配对 surrogate。输出按 UTF-16 code unit 排序对象成员，采用最小字符串转义，无 BOM、额外空白或末尾换行。数组顺序与字符串内容保持原样，不做 NFC、大小写折叠或十进制字符串改写。

该函数返回 `Ok` 仅表示 JSON 子集的解析与编码成功。例如 `true`、`{}`、名称中的转义控制字符、`"-0"` 和未知 IR 字段都可以通过 JSON 层；领域约束由后续步骤检查。不能将此函数输出标成已经验收的 canonical IR 或 Evidence。

`declarations::decode_type_declarations(bytes, limits)` 从同一 candidate 输入解码类型声明，检查：

- 顶层精确成员、IR `0.1`、语义名称 / 摘要、`sha-256`、空效果及顶层数组形状。
- enum / record / table 声明与全部七种内联值类型的闭合结构、标签，以及字段 / 枚举成员 / 主键名称唯一性。名称按规范拒绝空串、C0 `U+0000..001F` 和 C1 `U+0080..009F`，不扩展为其他 Unicode 类别过滤。
- 整数规范词法、非负 scale / capacity 和 `lower <= upper`。`integer::Integer` 保留完整十进制文本并精确比较，不转换为固定宽度整数或浮点数；尚不提供算术运算。
- ID 的词法与同类声明重复 ID、按类别解析引用、包括 `Option` 内部引用的记录无环性，以及存在、公开、非可选标量主键。

返回 `UnverifiedTypeDeclarations`：**尚未重算内容 ID，也不验收整个 IR**。`nodes` / `contracts` / `outputs` 只检查数组形状，不检查元素、基数、引用或语义；无 input / output 的材料也可能完成声明解码。其后须经过下述声明规范化 / 身份核对，并继续完成表达式 / 节点类型与效果、转换 DAG / 可达性、契约与输出接口检查。所有解码数组暂保留原序；enum 成员和主键顺序始终有语义，不能排序或去重。没有第二种声明文件格式或独立成功码。

`normalization::normalize_type_declarations(bytes, limits)` 复用声明解码，继续规范记录字段的 Unicode scalar 顺序，为每项 definition 生成 JCS 字节，按 IR v0.1 的对应类型域、NUL、definition 重算 SHA-256，并核对输入 ID。错误 ID 会返回 `ContentIdMismatch`，带原数组位置、输入 ID 和重算 ID；不会替换错误 ID、重写引用或静默去重。枚举成员和主键保留有语义的顺序，三类声明最终各自按 ID 排列。

成功返回只读的 `NormalizedTypeDeclarations`，分别保留规范类型化定义、规范 definition 字节与已核对的 ID。它只覆盖类型声明，不包含规范完整文档、文档摘要、节点 / 契约身份或完整 P1 成功信号；未检查范围与声明解码相同。这里没有 strict canonical 完整文档模式；可安全重排的数组、空白及转义差异仍可接受。

## 资源与诊断

调用方必须显式提供 `JsonLimits`，没有无限预算的默认入口：

- `max_input_bytes` 在 UTF-8 解码前检查，约束输入、解码字符串总量和规范输出字节量；本子集输出不长于合法输入。
- `max_values` 计数所有值及对象成员名，限制树分配与宽对象排序规模。
- `max_nesting` 限制同时打开的数组 / 对象层数，实际不超过实现上限 128；标量不消耗层数。解析、编码和树销毁均受此上限约束。

错误包含类别及原输入的零基字节位置。非法输入与 `ResourceLimit` 分开；先遇到预算限制时只报告未完成处理，不推断输入是否合法。对象重复键指向第二次出现的成员名。此内部诊断尚未映射为 pipeline stage result。

声明层复用同一有界 JSON parser；JSON 错误及资源错误原样保留，领域错误给出类别和指向原输入的 JSON Pointer。类型引用图使用迭代队列检测循环，不沿声明引用递归；多表共享记录时复用字段索引，避免反复扫描宽记录。名称、整数和类型不读取环境或外部工具。

这些是组件规模限制，不是 OS 硬内存 / 时限隔离，也不保证宿主分配失败可恢复。UTF-8 检查、字符串处理和编码按输入规模进行；对象排序按成员数量及键长度消耗资源。

规范化继续使用同一输入预算，逐项编码 definition 和域分离摘要，不递归展开引用。结果保留类型化定义和规范字节，内存会高于仅解码；总量受原输入规模约束，但不把 `max_input_bytes` 解释为硬内存配额。

## 实现与验收边界

Rust 2024，`publish = false`，仅自有代码与标准库、禁止 unsafe，无第三方依赖、build script、过程宏或 native / FFI。唯一直接依赖为本地 `radishaxiom-digest 0.0.0`，其 [SHA-256 实现](../digest/README.md)由既有 runtime 提取，共享算法而不依赖 runtime 的产品能力。与 runtime 的 ASCII 闭合文档 parser 分开；不改变旧 runtime 协议，不让独立 Go checker 复用生产实现。

测试期望来自人工推导的规范向量、Unicode 标量与转义的数学对应关系，以及仓库既有的四题 12 个 candidate；不调用生产 helper 生成期望。`correct` / `wrong` 候选同样参与 JSON / 声明层回归，不据标签判定算法。负例覆盖语法、无效 UTF-8、代理对、解码重名、截断、规模、版本、声明闭合结构、数值范围、引用和键约束。数学整数比较还与小范围机器整数逐对对照，并使用人工排列的大整数检验精度边界；5,000 层合成记录引用分别验证无环和成环路径。声明测试中的合成 ID 仅满足词法，明确不当作真实内容摘要。

规范化测试另外使用 [Python 独立身份向量](tests/fixtures/type-identities/README.md)，逐字节比较 definition 和 ID；改变对象 / 声明 / 字段排序与转义仍得到同一结果，改变有语义的顺序或内容则拒绝旧 ID。遗漏域名、遗漏 NUL、错误域名、末尾换行与把 ID 包进摘要均有独立负例；仓库检查会重算生成一致性。SHA-256 的通用已知向量在共享包保留，不能把共享生产摘要实现当作独立 checker。

已安装并验收的宿主工具可按仓库约定离线执行：

```bash
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir --locked --offline
```

完整 workspace 验证见[当前状态](../../docs/status/current.md#验证入口与本次审阅)。测试不是形式证明；未运行平台不能据此声称字节一致性已验收。
