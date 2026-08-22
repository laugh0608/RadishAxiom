# ADR 0004：`raxc` 生产编译器实现语言

日期：2026-08-20

状态：Accepted

用途：比较并冻结 `raxc` 生产编译器的实现语言，为后续验证后端、目标运行时和编译管线决策提供稳定宿主边界。

读者：编译器、验证、Evidence、构建与发布维护者，以及审阅首版工具链可信边界的协作者。

不包含：独立 checker 的实现语言、`.rax` 表面语法、验证后端、证明证书、目标运行时、发布平台清单、编译器骨架或实现计划。

## 背景与判定方法

[ADR 0002](0002-first-target-domain-and-benchmarks.md)、[首域语义](../semantics/keyed-finite-table-semantics.md)、[Axiom IR v0.1](../ir/axiom-ir-v0.md)和[Axiom Evidence v0.1](../evidence/axiom-evidence-v0.md)已经先于技术栈冻结。实现语言必须忠实承载受界数学算术、精确文本、闭合记录、内容寻址 DAG、canonical JSON、五种 Evidence 状态、可重放反例与显式 `unknown`，不能让宿主溢出、哈希迭代顺序、locale、隐式空值或异常吞噬成为第二语义源。

比较对象为 Rust、OCaml、F# 和 Go。评分 1–5，5 表示更适合首版生产 `raxc`；“维护成本”中 5 表示成本最低。确定性、类型安全与四个基准是正确性门槛，权重为 2；其余权重为 1。评分是基于现行规范和官方资料的设计判断，不是尚未执行的性能基准。

| 维度 | 权重 | Rust | OCaml | F# | Go |
| --- | ---: | ---: | ---: | ---: | ---: |
| 确定性与规范化能力 | 2 | 5 | 4 | 4 | 3 |
| 类型安全与语义建模 | 2 | 5 | 5 | 5 | 3 |
| 跨平台 | 1 | 5 | 4 | 5 | 5 |
| 构建与分发 | 1 | 4 | 3 | 3 | 5 |
| 验证后端互操作 | 1 | 4 | 5 | 5 | 4 |
| 独立 checker 隔离 | 1 | 4 | 4 | 4 | 4 |
| 许可证与供应链 | 1 | 4 | 3 | 4 | 5 |
| 维护成本 | 1 | 4 | 3 | 3 | 5 |
| 四个基准承载能力 | 2 | 5 | 5 | 5 | 4 |
| 加权合计 |  | **55** | 50 | 52 | 48 |

checker 隔离主要取决于进程、协议、代码和规则生成边界，而不是宿主语言，因此四者没有自动优势。任一候选若让 checker 复用生产规范化器或义务生成器，都不符合 Evidence 规范。

## 候选分析

### Rust

Rust 的 `enum`、`Option` / `Result` 和模式匹配适合闭合 IR、义务、状态与反例模型；标准库提供按键顺序迭代的 `BTreeMap` 和显式失败的 `checked_*` 算术。有效 `str` 是 UTF-8，便于在入口拒绝非法 Unicode 后实现 scalar 语义。官方 Tier 1 覆盖主流 Linux、macOS 和 Windows 宿主，Cargo 以 `Cargo.lock` 固定精确依赖并可 vendor 源码，适合交付原生 CLI。[语言类型](https://doc.rust-lang.org/book/ch06-00-enums.html)、[有序映射](https://doc.rust-lang.org/std/collections/struct.BTreeMap.html)、[检查算术](https://doc.rust-lang.org/std/primitive.i64.html#method.checked_add)、[平台分级](https://doc.rust-lang.org/rustc/platform-support.html)、[依赖锁](https://doc.rust-lang.org/cargo/guide/cargo-toml-vs-cargo-lock.html)

限制是 Rust 不自动保证规范字节或可复现二进制：JCS 的 UTF-16 属性名顺序仍需专用比较器，普通 `HashMap`、普通整数运算和 serializer 默认值不得进入规范路径；数学整数、JSON/JCS 和 SHA-256 仍可能需要第三方 crate。C FFI 是显式 `unsafe` 边界，求解器原生库会增加 ABI、打包和可信计算基成本。因此首选版本化子进程协议，FFI 只作为后续受审阅例外。[FFI 边界](https://doc.rust-lang.org/reference/items/external-blocks.html)、[子进程控制](https://doc.rust-lang.org/std/process/struct.Command.html)、[官方双许可证](https://rust-lang.org/policies/licenses/)

### OCaml

OCaml 的 variant、record、模式匹配和模块系统最贴近编译器数据结构；`ocamlopt` 可产出原生可执行文件，官方 C 接口和 Z3 的 OCaml binding 使验证器接线直接，opam 也能锁定传递依赖。[类型与模式匹配](https://ocaml.org/docs/basic-data-types)、[原生目标](https://ocaml.org/tools/native-target)、[C 接口](https://ocaml.org/manual/intfc.html)、[opam lock](https://opam.ocaml.org/doc/man/opam-lock.html)

主要代价是默认 `int` 在 OCaml 5 原生目标上为 63 位，`string` 是字节序列；数学整数、Unicode scalar、JCS、SHA-256 和严格 JSON 都需要额外实现或依赖。原生编译限于 64 位目标，Windows 工具链和跨平台打包路径比 Rust / Go 更重。核心采用 LGPL-2.1-or-later 加 OCaml linking exception，允许分发但比项目首选的宽松依赖增加合规说明；opam 包仍须逐项审计。[许可证原文](https://github.com/ocaml/ocaml/blob/trunk/LICENSE)

### F#

F# 的 discriminated union、record 与模式匹配同样适合闭合语义；.NET 标准库自带 `BigInteger`、加密和成熟 JSON 基础，Z3 提供官方 .NET binding，P/Invoke 和子进程路径都成熟。F# / .NET 可在 Linux、macOS、Windows 开发和运行，F# 源码及主要 .NET 源码采用 MIT。[判别联合](https://learn.microsoft.com/en-us/dotnet/fsharp/language-reference/discriminated-unions)、[P/Invoke](https://learn.microsoft.com/en-us/dotnet/standard/native-interop/pinvoke)、[F# 许可证](https://github.com/dotnet/fsharp/blob/main/License.txt)、[.NET 许可说明](https://github.com/dotnet/core/blob/main/license-information.md)

代价集中在分发与运行时边界：self-contained single-file 体积较大且按 OS / 架构发布，原生库可能需要额外提取；Native AOT 又有 trimming、动态加载和反射限制。`System.String` 以 UTF-16 表示，仍须拒绝未配对 surrogate 并区分 JCS 顺序与语言 scalar 顺序。NuGet 能锁定依赖，但 F# 维护者池、AOT 兼容性和运行时发布矩阵使首版成本高于 Rust。[单文件发布](https://learn.microsoft.com/en-us/dotnet/core/deploying/single-file/overview)、[Native AOT 限制](https://learn.microsoft.com/en-us/dotnet/core/deploying/native-aot/)、[NuGet locked mode](https://learn.microsoft.com/en-us/nuget/reference/errors-and-warnings/nu1512)

### Go

Go 的工具链、交叉编译、单可执行文件和标准库覆盖最有利于维护与分发；`math/big`、SHA-256、JSON、模块校验与 vendoring 可减少依赖面，Go 本身采用 BSD 风格许可证。[语言规范](https://go.dev/ref/spec)、[模块与 vendoring](https://go.dev/ref/mod)、[许可证原文](https://go.dev/LICENSE)

但 Go 没有闭合代数数据类型与穷尽模式匹配，IR tag、Evidence 状态和反例变体需要依靠接口、tag 与手写拒绝分支维持不变量。语言规范明确 map 迭代顺序未定义，整数与 Unicode 输入也必须额外封装。通过 cgo 接入原生求解器会增加交叉编译要求。它能承载首版，但更容易把本应由类型系统保证的闭合性降为测试约定。[cgo 跨编译边界](https://go.dev/src/cmd/cgo/doc.go)

## 四个基准的承载能力

| 候选 | AX-B01 受界净额 | AX-B02 恰好一次连接 | AX-B03 守恒聚合 | AX-B04 非干扰 |
| --- | --- | --- | --- | --- |
| Rust | enum / newtype 与检查算术直接表达 | 有序键类型、`Result` 和显式重复 / 缺失见证 | 有序分组、数学和后检查范围 | 闭合依赖图与关系义务可穷尽匹配 |
| OCaml | variant 与显式数值库可表达 | `Map` / variant 适合基数结果 | `Map` fold 与任意精度库可表达 | 代数数据与模块边界自然 |
| F# | DU 与 `BigInteger` 直接表达 | `Map`、option / result 适合连接结果 | 不可变集合与数学整数直接 | DU 与集合运算适合成对世界 |
| Go | 需专用数值类型与检查 helper | 需 tag 结果和规范排序 | 必须排序 map 结果并禁止隐式回绕 | 依赖图可做，但闭合性主要靠验证代码 |

这说明四题不会把任一候选结构性排除；Rust 的优势是四种义务在同一实现中都不需要牺牲类型闭合性或原生分发。此处没有运行候选编译器或模型实验，不能把承载判断表述为实现已通过基准。

## 决策

选择 **Rust 2024 edition 的 stable 工具链**实现生产 `raxc`。首次实现基线精确固定为 **Rust `1.97.1`**；截至 2026-08-22，`1.98.0` 刚于两天前发布，本次不自动采用，后续升级仍须单独审阅。`1.97.1` 是修复已知 LLVM miscompilation 的 stable patch；补丁修复不代表本项目已经执行过编译或语义验证。[Rust 1.97.1](https://blog.rust-lang.org/2026/07/16/Rust-1.97.1/)、[Rust 1.98.0](https://blog.rust-lang.org/releases/1.98.0/)

适用范围包括：未来的 source-to-IR 前端、Axiom IR 规范化与严格检查、类型 / 效果检查、义务生成、验证后端适配、反例缩减、Axiom Evidence 生产、诊断来源映射，以及由 `raxc` 直接承载的宿主输出适配。具体模块划分须由实现设计决定，本 ADR 不授权提前创建骨架。

以下内容不由本决策选择：

- 独立 checker 的语言与实现；checker 不得依赖 `raxc` 的规范化、类型检查、义务生成、Evidence 聚合或后端适配代码；
- `.rax` 表面语法、解析器生成器和 Agent projection；
- SMT / 证明助手 / 模型检查等验证后端；
- 解释执行、代码生成或双路径目标运行时；
- 用户生成程序的语言、运行时或许可证。

验证后端默认通过版本化、可摘要、可限时的子进程协议与 `raxc` 隔离。该边界不选择任何后端；若未来改用原生 FFI，必须单独说明证书、崩溃、ABI、资源、许可证和 `unsafe` 对可信计算基的影响。

## 工具链与依赖政策

1. 实现入口只使用精确固定的 stable Rust 工具链和 Rust 2024 edition；禁止 nightly feature。首次实现变更必须提交工具链固定文件，升级单独审阅。
2. `Cargo.lock` 必须提交并由 Cargo 维护；CI / 发布使用 locked mode。Git 依赖必须固定不可变 revision，禁止 branch、`latest`、floating version 或未登记 registry。
3. 标准库足够时不新增 crate。每项生产依赖都要记录用途、精确解析版本、来源、许可证、维护状态、build script / proc macro / native code、替代方案和进入生成产物的影响。
4. 默认只接受与 Apache-2.0 开放基础层兼容的宽松许可证；copyleft、source-available、专有条款、未知许可证或原生再分发要求必须单独进行许可审查。发布前生成第三方许可清单，并能从 lock 与校验信息恢复审阅过的源码集合。
5. 规范化、类型、义务与 Evidence 核心 crate 禁止 `unsafe`；FFI、平台能力和性能特化只能位于显式 adapter，逐处说明安全不变量并接受额外测试与审阅。
6. 规范路径禁止依赖 `HashMap` 迭代、默认整数溢出、浮点数、locale、时钟或随机性。使用规范比较器、有序结构、数学整数或检查算术，并以同一抽象制品的跨进程 / 跨平台黄金字节验证。
7. 后端 SDK、原生求解器和宿主运行时不是 `raxc` 核心依赖。任何把它们静态或动态链接进 `raxc` 的提案都必须在相应后端 / 运行时决策中重新审查供应链与分发边界。

## 风险与缓解

- Rust 所有权与生命周期会增加前期学习和编译成本；以不可变值、明确拥有关系和小型领域模块控制复杂度，不为绕过借用检查引入共享可变状态。
- Rust 类型安全不等于语义正确；JCS、Unicode、摘要、义务完整性和状态聚合仍必须由正例、负例、交叉实现与 checker 拒绝路径验证。
- 第三方 crate 与 proc macro 扩大供应链和构建时执行面；依赖最小化、锁定、许可清单和源码审计是进入发布的条件。
- 原生求解器绑定可能引入 `unsafe`、崩溃和跨平台打包差异；首选子进程失败关闭，并把超时、资源耗尽和不可用映射为真实 `unknown` / 操作性失败。
- 后续若也为 checker 选择 Rust，可能形成同源缺陷；该选择必须另立决策，且不能共享生产语义实现。

## 进入实现的验收条件

本 ADR 被接受不表示现在可以编写编译器。首个 `raxc` 实现变更前必须同时满足：

1. ADR 0002 的全部进入实现条件保持满足；验证后端、至少一个目标运行时和首版编译管线分别完成比较并以受审阅决策冻结。
2. 独立 checker 的代码隔离、义务重建、制品交换和结果绑定边界已经冻结；checker 语言仍由独立决策选择。
3. 精确 Rust stable 工具链、初始支持目标和升级规则已固定；各目标能运行同一规范化与负向测试，不以交叉编译成功代替运行验证。
4. 首批依赖提案通过本 ADR 的版本、许可证、build script、native code 和替代方案审查；未安装依赖或生成 lockfile 不能冒充验收。
5. 测试计划逐项映射 AX-B01 至 AX-B04、IR 必需矩阵、Evidence 验证矩阵、错误候选、`unknown`、实现不一致和 checker 拒绝路径。
6. 评审确认语义核心不依赖 `unsafe`、宿主默认溢出、无序迭代、locale、隐式 Unicode 规范化、外部网络或生产数据。

在这些条件满足前，仓库继续处于设计阶段；本 ADR 只消除“生产编译器实现语言”这一项未知。

## 重新评估条件

出现以下任一事实时，以新 ADR 重新比较，而不是在实现中堆叠 fallback：

- 同一抽象 IR / Evidence 无法在计划支持的 Linux、macOS、Windows 目标规范化为相同字节，或同一 IR 无法生成相同的义务定义集合，且根因是 Rust 工具链或必需库的不可替代行为；工具与 artifact 身份等规范要求的平台差异不计入此条件；
- 已选验证后端只能通过另一候选的稳定官方 API 提供必需证书、取消和资源控制，版本化子进程协议又无法满足 Evidence 边界；
- 规范化、类型、义务或 Evidence 核心必须引入无法隔离的 `unsafe`、不兼容许可证或不可审计原生依赖；
- 四个基准纵向切片证明 Rust 实现的复杂度主要来自语言阻抗，而 OCaml / F# 的受控 spike 能显著缩小可信实现与依赖面；
- 首次公开发布前无法形成至少两名能够审阅 Rust 语义核心的维护者，或冻结后的构建 / CI 预算连续两个评测周期超出届时明确门槛；
- Rust 的平台支持、许可证或供应链机制发生与 Apache-2.0 开放基础层不兼容的实质变化。

性能偏好、单次构建缓慢、某个 crate 更方便或 checker 另选语言，本身不触发更换。

## 后果与变更要求

收益是生产编译器获得闭合数据建模、显式失败、受控 `unsafe`、主流平台原生分发和可锁定依赖的统一基础；代价是需要承担 Rust 学习 / 编译成本，并自行证明规范化而不能依赖 serializer 或集合默认值。

修改 `raxc` 生产实现语言、允许 nightly 进入正式构建、允许核心 `unsafe`、取消依赖锁定或让独立 checker 复用生产语义实现，必须以新 ADR 替代本决策。改变 checker、表面语法、验证后端或目标运行时而保持这些边界，不自动替代本 ADR，但仍需各自决策与兼容性验证。

Rust `1.97.1` 的六平台候选 URL、源码、摘要状态、许可证来源与 build profile 已登记到 [Toolchain & Adapter Identity Registry v0.1](../../contracts/toolchain-adapters-v0.1/README.md)。登记不等于 payload、签名、包内组件或许可证已经验收；Rust 摘要未从 publisher manifest 捕获前仍禁止进入构建门禁。
