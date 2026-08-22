# ADR 0006：首个目标运行时与执行路径

日期：2026-08-22

状态：Accepted

用途：比较并冻结 RadishAxiom 首个目标运行时、宿主执行模型、数据承载、Axiom Evidence 映射和失败关闭边界，为首版编译管线与独立 checker 决策提供稳定执行目标。

读者：语义、编译器、代码生成、Evidence、宿主执行、构建与发布维护者，以及审阅首版纵向闭环可信边界的协作者。

不包含：首版编译管线的阶段与制品契约、独立 checker 的实现、`.rax` 表面语法、目标代码 emitter、运行时安装、包管理、产品发布载体或实现骨架。

## 背景与判定方法

[ADR 0002](0002-first-target-domain-and-benchmarks.md)、[首域语义](../semantics/keyed-finite-table-semantics.md)、[Axiom IR v0.1](../ir/axiom-ir-v0.md)、[Axiom Evidence v0.1](../evidence/axiom-evidence-v0.md)和[四题版本化语料](../benchmarks/keyed-finite-table-corpus-v0.md)已经冻结了执行必须忠实承载的边界：受界数学整数、有限 Unicode scalar value 序列、显式 `Option`、闭合记录、无序有限表、确定性聚合、核心效果 `∅`、运行故障以及具体输入上的 host / output conformance。

目标执行不能反向引入 IEEE 754 数值、locale、Unicode 规范化、哈希迭代顺序、隐式 `null` 或隐藏能力。静态核心义务已经 `proved` 也不证明生成器或宿主运行时正确；具体宿主执行只能形成 `checked`，并继续显式列出 `production-generator`、`host-runtime`、`decoder-normalizer` trust 和 `host-fidelity-for-all-inputs` uncovered。

比较对象为：

1. 从 Axiom IR 生成受限 ECMAScript module，由 Node.js 独立进程执行；
2. 在生产 `raxc` 内以 Rust 直接解释 Axiom IR；
3. 生成 WebAssembly，由 Wasmtime 独立进程执行。

评分 1–5，5 表示更适合首版；正确性相关维度权重为 2。评分基于现行规范、AX-B01 至 AX-B04 和截至决策日的官方资料，是设计判断，不是尚未运行的性能或兼容性实验。

| 维度 | 权重 | Node.js 代码生成 | Rust 原生解释 | Wasmtime / WebAssembly |
| --- | ---: | ---: | ---: | ---: |
| 数学整数与精确文本 | 2 | 4 | 4 | 2 |
| 无序表与确定性聚合 | 2 | 4 | 5 | 3 |
| 输入 / 输出编解码忠实度 | 2 | 4 | 4 | 2 |
| 故障隔离与效果收缩 | 2 | 4 | 3 | 5 |
| host conformance 的实现区分度 | 2 | 5 | 2 | 4 |
| 跨平台与分发 | 1 | 5 | 5 | 5 |
| 许可证与供应链 | 1 | 3 | 4 | 3 |
| 首版范围与维护成本 | 1 | 4 | 5 | 2 |
| 四个基准承载能力 | 2 | 5 | 5 | 3 |
| 加权合计 |  | **64** | 60 | 48 |

## 候选分析

### Node.js 代码生成

ECMAScript `BigInt` 对任意位宽整数提供精确数学运算，能直接承载 `Int` 与 `Fixed` 的系数；语义整数仍以规范十进制字符串进出 JSON，不能经过 `Number`。ECMAScript `String` 是 UTF-16 code unit 序列，允许未配对 surrogate，因此入口和出口都必须以 `String.prototype.isWellFormed()` 或等价逐 code unit 检查拒绝非法文本；有效字符串的精确相等可以忠实对应 scalar 序列相等，但禁止 `normalize`、`localeCompare` 和 locale 大小写操作。[ECMAScript BigInt](https://tc39.es/ecma262/2025/multipage/ecmascript-data-types-and-values.html#sec-ecmascript-language-types-bigint-type)、[ECMAScript String](https://tc39.es/ecma262/2025/multipage/ecmascript-data-types-and-values.html#sec-ecmascript-language-types-string-type)、[`isWellFormed`](https://tc39.es/ecma262/2025/multipage/text-processing.html#sec-string.prototype.iswellformed)

`Map` / `Set` 与 object 的迭代规则不能成为表语义。生成程序必须以显式键比较、重复键拒绝、确定性分组和规范主键排序外部化结果；表的输入顺序不得影响输出。`BigInt` 不能由普通 JSON serializer 直接承载，因此目标数据 codec 必须沿用 Axiom 的十进制字符串、显式 tag 和闭合字段规则，而不是依赖 `JSON.stringify` 的默认值转换。

Node.js 提供 Linux、macOS 与 Windows 的官方制品和 LTS 生命周期。Node.js 24 已进入 LTS，24.19.0 是决策日最新的 24.x LTS patch；该精确版本可作为受控原型基线。[Node.js release schedule](https://nodejs.org/en/about/previous-releases)、[Node.js 24.19.0](https://nodejs.org/en/blog/release/v24.19.0)

Node.js 24 的 Permission Model 已稳定，可限制文件系统、子进程、worker、native addon、WASI 和 inspector 等能力；但官方明确把它定义为面向可信代码的“安全带”，不能抵抗恶意代码。RadishAxiom 只能把它作为纵深减灾，不能用它消除 `host-runtime` trust 或替代外层进程、资源与网络隔离。[Node.js 24 Permission Model](https://nodejs.org/download/release/v24.19.0/docs/api/permissions.html)

代价是引入 V8、Node 标准库与随附第三方组件，并需要维护受限代码生成、严格 codec 和 LTS 升级矩阵。Node.js 主体使用 MIT，实际官方制品包含多种第三方许可证，仍须按精确制品登记，而不能只记录“MIT”。[Node.js 24.19.0 LICENSE](https://github.com/nodejs/node/blob/v24.19.0/LICENSE)

### Rust 原生解释

生产 `raxc` 已选择 Rust。原生解释器可复用闭合类型模型、有效 UTF-8 字符串和按键顺序迭代的 `BTreeMap`，不需要第二个运行时，首版实现和分发成本最低。[Rust `str`](https://doc.rust-lang.org/std/primitive.str.html)、[Rust `BTreeMap`](https://doc.rust-lang.org/std/collections/struct.BTreeMap.html)

主要问题不是承载能力，而是可信边界：解释器与 IR normalizer、义务生成器、Evidence producer 同处生产语言和产品进程，容易让 host conformance 退化为同一实现对自己的动态复述。它仍需要数学整数、严格数据 codec、故障隔离和独立输出比较，并不能因“少一个运行时”删除 `production-generator` / `host-runtime` trust。它适合以后作为差分参考执行器，但不作为首个对外目标路径。

### Wasmtime / WebAssembly

WebAssembly 的显式导入和隔离内存提供最清楚的能力沙箱；Wasmtime 主要支持 Linux、macOS 和 Windows，也能按 fuel / epoch 等运行时机制控制执行。[WebAssembly security](https://webassembly.org/docs/security/)、[Wasmtime security](https://docs.wasmtime.dev/security.html)、[Wasmtime platform support](https://docs.wasmtime.dev/stability-platform-support.html)

但 WebAssembly Core 的数值载体主要是 `i32`、`i64`、`f32`、`f64`，不能直接表示规范的数学整数；文本、闭合记录、表、任意精度加减和 canonical JSON 还需要自定义内存 ABI 与目标运行库。[WebAssembly core types](https://webassembly.github.io/spec/core/syntax/types.html)

这会让首版同时承担编译后端、big integer、内存管理、codec、WASI / component 边界和 Wasmtime 供应链，超出四题纵向切片所需范围。WebAssembly 保留为后续便携沙箱目标，不作为首条执行路径。

### 受控双路径

Rust 解释与 Node.js 代码生成同时落地可以提供差分信号，但也会同时建立两套 evaluator、故障模型和跨平台矩阵。首版尚未证明一条路径能忠实跑通四题，此时双路径增加的主要是实现与审阅面积。只有首条路径满足本文验收条件后，差分解释器才作为独立提案进入，不作为失败后的静默 fallback。

## 决策

选择 **Node.js 24.19.0 LTS 独立命令行程序**作为首个目标运行时基线；选择 **确定性 ECMAScript ES module 代码生成 + 一次执行一个独立 Node.js 进程**作为首条执行路径。

目标 profile 稳定命名为 `node-24-esm-keyed-finite-table-v0.1`。该名称描述首域执行能力，不是语言语义、Axiom IR、Axiom Evidence 或产品版本。初始 adapter 只接受精确的 Node.js 24.19.0；patch、major、发行制品或 invocation 变化必须显式复验，不能按 `node`、`24`、`lts` 或系统 PATH 上任意版本自动放行。

首版不实现生产 Rust 解释器，不同时维护双执行路径，也不在 Node.js 不可用或失败时自动切换其他运行时。目标运行时失败不会触发重新验证、修改输入或改变程序语义。

## 生成与执行边界

首版编译管线必须在后续 ADR 中细化以下顺序，但不得改变其安全门：

1. 严格解析并规范化 Axiom IR，完成输入制品的结构、类型、容量、键、外键和前置条件检查；
2. 生成并完成全部必需核心义务；任一必需义务为 `failed` / `unknown`、证书策略未满足或输入被拒绝时，不启动目标运行时；
3. 从已绑定的 canonical Axiom IR 确定性生成一个自包含 `.mjs` 制品；同一 IR 摘要、生成器身份和 target profile 必须产生逐字节相同的 UTF-8 / LF 源码；
4. 由 host executor 以固定参数启动一个 Node.js 进程，通过 stdin 传入一个已验证、版本化的数据 envelope，通过 stdout 接收唯一输出 envelope；stderr 只承载有界诊断；
5. 严格解码宿主输出，分别完成 `host-conformance` 与 `output-conformance`，再由 Evidence 规则聚合结论。

生成模块不得使用 npm package、动态 `import`、`eval` / `Function`、native addon、WASI、FFI、子进程、worker、文件、数据库、网络、环境变量、时钟、随机源、locale 或隐式全局状态。首版允许的宿主能力只有读取当前进程 stdin、向 stdout 写一个结果和向 stderr 写有界稳定诊断；模块之外的启动器负责时限、资源上限、环境清理和可用的平台隔离。

Node Permission Model 必须以拒绝式配置启用，并只授予加载精确生成模块所需的最小文件读取范围；它不替代外层隔离。入口文件路径、符号链接、`NODE_OPTIONS`、V8 flags、启动参数和继承 file descriptor 必须由 host executor 固定或清理，不能从未受信输入继承。

生成源码、Node 二进制、invocation profile、输入、stdout、stderr、退出状态、资源限制和宿主输出都必须按摘要绑定到 Evidence。目标程序不嵌入 Node.js、npm 依赖或可复用 RadishAxiom runtime；若后续需要把模板或运行库复制进用户生成产物，必须先完成单独的许可证与供应链决策。

## 数据与宿主语义映射

首个 target profile 只承载 `axiom-benchmark-data` v0.1 所表示的 AX-B01 至 AX-B04 数据抽象值；编译管线必须为实际宿主输入 / 输出 envelope 冻结独立版本和闭合成员集合，但不得创造第二套值语义。

| Axiom 值 | Node.js 运行表示 | 必需边界 |
| --- | --- | --- |
| `Bool` | `boolean` | 只接受 `true` / `false` |
| `Int` | `bigint` | 由规范十进制字符串构造；每次结果检查声明范围；禁止 `Number` 语义算术 |
| `Fixed` | 表示系数的 `bigint` + 静态 scale | 不用浮点，不隐式转换 scale，输出系数仍为十进制字符串 |
| `Text` | well-formed ECMAScript `string` | 拒绝未配对 surrogate；只做精确相等与 scalar 规范排序；不规范化或 locale 比较 |
| `Enum` | 闭合 tag / member | 未知类型或 member 拒绝，不以自由字符串透传 |
| `Option<T>` | 显式 `none` / `some` tag | 禁止以 `null`、`undefined`、缺字段或 truthy / falsy 表示 |
| `Record` | 由生成代码控制的闭合字段值 | 缺失、额外、重复字段或原型继承值拒绝 |
| `Table<R,K,N>` | 不暴露顺序语义的有限行集合 | 检查容量和重复键；join 恰好一次；group 使用显式键；输出按规范主键排序 |

输入与输出 JSON 禁止 JSON number 和 `null`；全部语义整数、scale、容量与计数继续使用规范十进制字符串。解析前必须拒绝重复 object member，解析后必须拒绝未知字段、非法 Unicode、非规范十进制、错误 tag、额外 / 缺失字段、重复表名和重复主键。普通 `JSON.parse` 会丢失重复成员信息，不能单独构成合格的边界 decoder。

数组索引、缓冲区长度和运行时资源计数可以使用宿主机器数值，但不能进入 Axiom 可观察值。若声明容量、实际输入或生成源码超过 target profile 的显式宿主上限，结果是 `unsupported` 或资源失败，不得截断、改写范围或切换到 `Number`。

## Axiom Evidence 与失败关闭

### 正常执行

- 生成器正确性保持 `production-generator` trust；Node / V8 / 标准库行为保持 `host-runtime` trust；输入与输出 codec 保持 `decoder-normalizer` trust。
- `execute-host` 必须引用精确 target module、输入、Node tool identity、limits 和全部原始输出制品；完成只说明进程协议结束，不能自动产生 `checked`。
- `host-conformance` 针对绑定的 IR、具体输入、运行故障或实际宿主输出；`output-conformance` 另行比较严格解码后的实际输出与模式 / 黄金制品。
- 两项检查成功都只产生 `checked`；`host-fidelity-for-all-inputs` 继续作为 uncovered，不能因四题 fixture 通过而删除。

### `implementation_inconsistent`

当核心义务全部 `proved`、具体输入已经通过检查，而目标执行出现以下可重放差异时，相关 host / output check 为 `failed`，Evidence 结论必须为 `implementation_inconsistent`：

- 运行结果值、行集合、字段、键、聚合或规范输出与绑定语义 / 黄金结果不同；
- 输出 envelope 畸形、包含额外输出、非法文本、JSON number / `null`、非规范整数、未知 tag、额外 / 缺失字段或重复键；
- 对已证明总定义的有效输入发生可稳定归因于生成程序或运行时语义的异常、越界、缺失匹配或其他运行故障；
- 生成程序尝试未声明能力，且记录证明是目标程序违反已证明的效果 `∅`，而不是启动器误配置。

`failed` 仍必须有绑定具体输入、观察值 / 故障和完成的比较或重放 execution。仅有非零退出码、自由文本 stack trace 或猜测不能支撑实现不一致。

### `inconclusive`

以下情况默认映射为真实 execution failure 与 `unknown`，结论为 `inconclusive`：

- Node 二进制缺失、不可执行、版本 / 摘要 / profile 不匹配；
- 无法启动进程、管道 I/O 失败、外层时限、资源耗尽或宿主平台不支持要求的隔离；
- 崩溃、非零退出、空 stdout、协议损坏或权限错误尚不能稳定区分为生成程序缺陷还是执行环境故障；
- target profile 的容量、源码大小或其他显式宿主上限不满足。

后续独立重放若能把原始 attempt 绑定为上节的具体语义差异，可以在新的 Evidence 中产生 `implementation_inconsistent`；原始 `unknown` attempt 仍须保留。运行时错误不得自动重试成成功，Node 不可用时也不得静默使用 Rust 解释器、另一个 Node 版本或远程服务。

## 依赖、分发与升级政策

1. Node.js 是外部 `host-runtime`，不链接进 `raxc`，不进入 Cargo 依赖，也不由 `raxc` 自动下载或安装。
2. 受控原型只接受来自已登记来源的精确官方制品或经审阅的可复现构建；记录原始文件 SHA-256、签名 / 校验来源、目标 OS / 架构、Node / V8 版本、完整 LICENSE 和随附第三方组件。
3. 首版目标程序没有 `package.json`、lockfile、npm registry、安装脚本或第三方 JavaScript package；`npx`、CDN、网络 import 和运行时下载一律禁止。
4. Linux、macOS、Windows 必须运行同一生成源码与输入字节，产生相同规范输出值和错误分类；原生 Node 二进制摘要、平台隔离实现与非语义诊断可以不同，但必须显式绑定。
5. Node 24 patch 升级须逐项重跑 codec、权限、故障和四题矩阵，并更新精确制品身份；不能因同属 24.x 或 LTS 自动兼容。切换 major、改用非 LTS、放宽受限 ECMAScript 子集或改变执行模型必须重新审阅本 ADR。
6. Node 24 进入 EOL 前必须完成升级或替代决策；EOL runtime、来源不明的系统 Node 或缺少安全维护的制品不能进入发布支持矩阵。

## 进入受控原型的验收条件

本 ADR 被接受不授权现在安装 Node.js、创建 emitter、加入 Rust crate 或编写运行时。后续只有同时满足以下条件，才可在独立授权下开始目标执行原型：

1. 首版编译管线和独立 checker 的制品、隔离、义务重建与 Evidence 边界已按 ADR 0002 / 0004 / 0005 的顺序冻结；
2. Node.js 24.19.0 在 Linux、macOS、Windows 目标上的精确官方制品、摘要、来源、签名 / 校验与完整许可证清单通过审阅；
3. target module、invocation profile、数据 envelope、稳定故障码、stdout / stderr 限额和 host limit 均版本化并可按摘要绑定；
4. 输入 / 输出 decoder 负向矩阵覆盖重复 JSON member、JSON number、`null`、未配对 surrogate、非规范整数、错误 enum / option、原型继承、额外 / 缺失字段、重复表 / 键和容量超限；
5. 生成器只接受 canonical Axiom IR，并在不同宿主上对同一 IR 产生逐字节相同源码；源码检查能拒绝未登记语法、API、动态代码、import 与隐藏能力；
6. AX-B01 至 AX-B04 的 correct candidate 对 base / boundary 输入产生与 golden 抽象值一致的规范输出；invalid input 在启动 Node 前拒绝；核心 `failed` / `unknown` 时没有 host execution；
7. 故障注入分别证明输出差异、畸形输出、已证明程序的语义 fault 和未声明能力尝试进入 `implementation_inconsistent`，而 unavailable、timeout、resource exhaustion、平台 unsupported 与不可归因 operational error 保持 `inconclusive`；
8. Evidence 精确绑定生成器、目标源码、Node、invocation、输入、输出、limits 与比较，并保留 `production-generator`、`host-runtime`、`decoder-normalizer` trust 和 `host-fidelity-for-all-inputs` uncovered；
9. 生成产物不嵌入会把项目或第三方许可证义务意外传递给用户程序的 runtime / template；若做不到，先完成单独的生成代码授权边界决策。

这些条件是未来原型入口，不是已经取得的运行结果。编译器实现仍须满足 ADR 0002 与 ADR 0004 的全部其余入口条件。

## 风险与重新评估

- ECMAScript 字符串允许未配对 surrogate，普通 JSON parser 又不能发现重复 member；严格的原始字节 parser 与双向 codec 测试是正确性门槛。
- Node.js 具备远超核心效果 `∅` 的宿主能力，Permission Model 也不是恶意代码沙箱；受限生成子集、固定 launcher、外层隔离与显式 trust 缺一不可。
- 生成器和输出 comparator 可能共享同一错误；独立 checker 必须重建必要边界，且 production report 不能自证。
- Node 官方二进制包含大量第三方组件；外部进程减少链接耦合，但不会自动缩小供应链审计范围。
- 精确 LTS pin 会带来定期安全升级成本；升级必须保留旧 Evidence 的工具身份和可重放性。

出现以下任一事实时，以新 ADR 重新比较 Node.js、Rust 解释、Wasmtime 或其他候选，而不是增加隐藏 fallback：

- 四题无法在禁止 `Number` 语义算术、locale、动态代码和第三方 package 的受限 ECMAScript 子集中忠实实现；
- Node 的 Unicode、BigInt、module、权限或序列化行为导致跨平台语义 / 规范输出不一致，且严格 adapter 无法隔离；
- 首版必须引入 npm package、native addon、运行时网络或不可审计模板才能完成；
- 受控资源预算下，Node 启动、内存或分发成本连续超出后续明确门槛，而 Rust / Wasmtime spike 能以更小可信边界覆盖同一四题；
- Node 24 无法在 EOL 前迁移到受支持版本，或官方制品 / 许可证 / 平台支持发生不兼容变化；
- Wasmtime / Component Model 后续能够直接承载所需数学整数与数据边界，且显著缩小 host trust 与跨平台维护面；
- 生产生成器与 Node 路径不能提供足够独立的 host conformance，受控双路径能以明确成本改进缺陷发现。

修改首个目标运行时、改为解释执行或默认双路径、允许 silent fallback、允许 `Number` 承载语义整数、允许 npm / 动态代码 / 隐式宿主能力、取消精确 runtime identity 或放宽失败关闭规则，必须以新 ADR 替代本决策。
