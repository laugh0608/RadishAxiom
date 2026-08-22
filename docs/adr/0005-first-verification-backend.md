# ADR 0005：首个验证后端与失败关闭边界

日期：2026-08-22

状态：Accepted

用途：比较并冻结 RadishAxiom 首个验证后端、首版义务编码约束、Axiom Evidence 映射和失败关闭边界，为后续目标运行时与编译管线决策提供稳定的验证能力边界。

读者：语义、验证、Evidence、编译器、独立 checker、构建与发布维护者，以及审阅首版可信计算基的协作者。

不包含：独立 checker 的实现语言或具体实现、最终证明证书格式、目标运行时、首版编译管线、`.rax` 表面语法、后端 adapter、依赖安装或编译器骨架。

## 背景与判定方法

[ADR 0002](0002-first-target-domain-and-benchmarks.md)、[首域语义](../semantics/keyed-finite-table-semantics.md)、[Axiom IR v0.1](../ir/axiom-ir-v0.md)、[Axiom Evidence v0.1](../evidence/axiom-evidence-v0.md)和[四题版本化语料](../benchmarks/keyed-finite-table-corpus-v0.md)已经先于后端冻结。验证后端必须回答由这些规范产生的义务，不能反向削弱范围、连接、守恒、非干扰、效果或五种 Evidence 状态。

首版验证把待证明性质 `Goal` 转换为满足性查询 `WF ∧ Pre ∧ ¬Goal`：

- `unsat` 只能支撑“在列出的假设成立时不存在反例”；能否独立确认取决于证明 support；
- `sat` 只产生候选 model，必须转换为满足 `WF` / `Pre` 且可重放的 Axiom counterexample 后才能成为 `failed`；
- `unknown`、超时、资源耗尽、崩溃、协议错误和不完整证书都不能变成成功。

首域的表容量是类型的一部分，程序图有限且无递归。首版义务编码因此以容量为界展开行槽位、存在位、键比较、分组和双世界，不引入量化词。受界 `Int` / `Fixed` 使用带范围约束的 SMT 数学整数；`Text` 首版只有精确相等，使用 uninterpreted sort 与相等关系，不调用宿主 locale、Unicode 规范化或求解器字符串扩展。枚举、可选值、闭合记录和行存在性使用有限 tag、布尔量与字段变量表达。

该编码目标属于 QF_UFLIA 类能力；具体 SMT-LIB query 的规范字节、命名和降级规则仍须在编译管线设计中冻结。量化词、原生字符串、集合、bag、递归函数、浮点和非线性算术不是首版后端入口要求，不能为了方便形成第二语义源。

比较对象为 cvc5、Z3 和 Lean 4。cvc5 与 Z3 代表自动 SMT 路径；Lean 4 代表由小内核检查证明项的证明助手路径。比较是基于现行规范与截至决策日的官方资料作出的设计判断，没有运行求解器或声称四题已经通过。

## 候选比较

| 维度 | cvc5 | Z3 | Lean 4 |
| --- | --- | --- | --- |
| QF_UFLIA 类自动求解 | 原生 SMT-LIB，满足 | 原生 SMT-LIB，满足 | 可表达，但需要单独形式化和证明自动化层 |
| `sat` model 与反例候选 | 支持 model / value 查询 | 支持成熟 model API | 不以 SMT model 搜索为默认工作流 |
| `unsat` 独立 support | 可输出 CPC、Alethe、LFSC；Alethe 当前覆盖 EUF 与线性算术 | 可输出 proof object / clause log，但官方仍列出理论组合、外部验证器和自检查 fallback 等开放项 | 明确证明项由小 kernel 检查，并存在独立 kernel 实现 |
| 不完整证明可见性 | CPC checker 会把 trust step 报为 `incomplete`；Alethe checker 路径可独立运行 | 内建检查仍可能调用 Z3 回查，不能视为独立 | 需审计 axioms、`sorry` 与 native evaluation；证明生成成本高 |
| `unknown` 与资源控制 | `sat` / `unsat` / `unknown` 分离；有 time / resource limit 和 reason | `unknown`、timeout、rlimit 与 reason 可用 | 依赖 heartbeat、进程预算和策略约定，不是统一 SMT 结果协议 |
| 进程隔离 | 稳定 CLI 与 SMT-LIB 输入，适合一次义务一进程 | 稳定 CLI 与 SMT-LIB 输入，同样适合 | CLI 可隔离，但需引入 Lean 工程、库和生成层 |
| 跨平台 | Linux、macOS、Windows 可构建；官方发布多平台制品 | 官方发布 Linux、macOS、Windows 多架构制品 | 支持主流平台，但工具链与库版本需共同锁定 |
| 许可证与供应链 | modified BSD；必须选择非 GPL build，并审查 GMP / MPFR 等随附依赖 | MIT；原生二进制仍需单独登记 | Apache-2.0；库、工具链与频繁版本演进扩大锁定面 |
| 首版维护成本 | 单一外部 CLI；证书与 model 都在同一后端 | 单一外部 CLI，集成低，但独立 proof support 不足 | 形式化层、自动化、库和 counterexample 路径成本最高 |

cvc5 的官方文档说明其内部证明演算为 CPC，并可输出 CPC、Alethe 和 LFSC；Alethe 当前覆盖 uninterpreted functions 与线性算术，正好包含首版编码的核心理论。[Proof Production](https://cvc5.github.io/docs/latest/proofs/proofs.html)、[Alethe](https://cvc5.github.io/docs/latest/proofs/output_alethe.html)

CPC 由外部 Ethos checker 检查，但官方同时明确：未被签名覆盖的规则会变成 trust step，Ethos 应返回 `incomplete` 而不是 `correct`。因此“生成了证明文件”不是完整 certificate 的充分条件。[CPC](https://cvc5.github.io/docs/latest/proofs/output_cpc.html)

cvc5 的每次检查可配置时间和资源上限；达到安全点后返回带 explanation 的 `unknown`，而整体进程时限可能直接终止进程。RadishAxiom 仍需在外层设置硬时限，不能只依赖后端软时限。[Resource limits](https://cvc5.github.io/docs/latest/resource-limits.html)、[unknown 输出](https://cvc5.github.io/docs/latest/output-tags.html#incomplete)

Z3 在首版逻辑、model、平台和维护成熟度上完全可用，许可证也更简单；但其官方 release notes 仍把高效外部 proof validator、理论组合验证与端到端 proof bridge 列为开放方向，并说明内建 fallback 会再次调用 Z3。这适合 `backend-attestation`，不满足本项目优先缩小 proof-backend trust 的目标。[Z3 proof notes](https://github.com/Z3Prover/z3/blob/master/RELEASE_NOTES.md)、[Z3 parameters](https://microsoft.github.io/z3guide/programming/Parameters/)、[MIT 与发布入口](https://github.com/Z3Prover/z3)

Lean 4 的显式证明项和小 kernel 最接近长期独立复核目标，官方也说明 tactic 产生的项最终由 kernel 检查；但首版还需要自动 model 搜索、四种数据反例和 SMT-LIB 子进程边界。现在选择 Lean 会把“首个后端”扩大为形式化库与自动化工程，提前耦合 checker 路线。[Lean kernel](https://lean-lang.org/doc/reference/latest/Elaboration-and-Compilation/#the-kernel)、[验证 Lean 证明](https://lean-lang.org/doc/reference/latest/ValidatingProofs/)、[Apache-2.0 与发布入口](https://github.com/leanprover/lean4)

## 决策

选择 **cvc5 1.3.4 的独立命令行程序**作为首个验证后端评估基线。

选择只覆盖以下范围：

1. `raxc` 按容量生成确定性的量化词自由 SMT-LIB 2 query；默认目标能力为 QF_UFLIA 类。cvc5 必须启用 `--safe-mode=safe`、严格解析、model / proof 生产和显式资源限制，实际选项集由版本化 adapter 契约固定。
2. 每个义务使用独立 cvc5 进程，不复用隐藏的增量 session；query、标准输出、标准错误、退出状态、后端版本、二进制摘要、选项与资源预算全部绑定为 Evidence artifact / execution。
3. 后端通过 stdin / stdout / stderr 和版本化 adapter 契约隔离；不得把 cvc5、cvc5 Rust binding、C++ SDK 或原生库链接进 `raxc`。
4. 首版只接受精确的 stable release、精确 artifact digest 和显式选项；`latest`、nightly、系统 PATH 上未识别版本和自动下载均拒绝。
5. 采用官方非 GPL build 或经审阅的 `--no-gpl` 可复现构建。cvc5 本体为 modified BSD；GMP、MPFR、CaDiCaL、SymFPU、编译器 runtime 和可选组件必须按实际制品逐项登记。带 `-gpl` 的发布制品不进入默认开放基础层。

截至本决策日，cvc5 1.3.4 是当前 stable release，并说明 CPC proof 可由 Ethos 0.2.3 检查；safe mode 用于排除没有完整 proof / model support 的能力。它是首次原型的精确基线，不授权自动跟随未来版本。[cvc5 1.3.4 release](https://github.com/cvc5/cvc5/releases/tag/cvc5-1.3.4)、[release notes](https://github.com/cvc5/cvc5/blob/cvc5-1.3.4/NEWS.md)、[许可证与第三方组件](https://github.com/cvc5/cvc5/blob/cvc5-1.3.4/COPYING)、[平台与构建](https://cvc5.github.io/docs/cvc5-1.3.4/installation/installation.html)

Z3 保留为首选替代方案和未来差分比较候选，但不是 cvc5 返回 `unknown` 后的静默 fallback。Lean 4 保留为 checker、kernel replay 或高保证证明路径的候选，本 ADR 不选择其角色。后续若运行多个后端，每次 attempt 必须分别保留；新结果不能删除先前的 `unknown`、超时或失败记录。

## 四个基准的后端映射

| 基准 | 主要编码 | `unsat` 目标 | `sat` 候选见证 |
| --- | --- | --- | --- |
| AX-B01 净额 | 单世界行槽位、状态 tag、线性加减与范围 | 覆盖、减法、范围、键、总性 | `single-row` 算术或丢行 world |
| AX-B02 连接 | 左右槽位、键相等、pairwise 匹配计数 | 恰好一次、无扇出 / 丢行、字段来源 | `missing-key` 或 `row-pair` world |
| AX-B03 聚合 | 槽位分组关系、有限 `ite` 和、计数与守恒 | 分区、计数、和、全局守恒、范围 | `group` world 与差额 |
| AX-B04 非干扰 | 两个公开等价 world、敏感字段独立变量 | 输出行、键、公开字段和终止关系相等 | `paired-input` worlds 或字段路径 |

所有表槽位都受 IR 容量约束；无语义行序只用于编码，不得进入可观察结果。求解器对 uninterpreted Text 产生的等价类必须被确定性映射为不与现有 literal 冲突的合成 Unicode scalar 序列，再由独立 counterexample replayer 检查相等 / 不等关系、`WF`、`Pre` 和目标违反。无法完成该映射时不得输出 `failed`。

## Axiom Evidence 映射

### `unsat`

- 外部 checker 对绑定 query 的完整证明 artifact 接受，且不存在 hole、trust step、未知规则或未绑定 side condition 时，可使用 `certificate` support；独立结果只能描述实际检查范围。
- 只有 cvc5 的 `unsat`、内部 `check-proofs`、unsat core 或含 trust step 的证明时，生产侧可按 Evidence v0.1 使用 `backend-attestation`，并显式列出 `proof-backend` trust；独立 checker 不得声称检查了证明真值。
- 要求 certificate 的策略下，缺失、不兼容、被篡改或不完整的 proof artifact 必须产生 `incomplete-certificate` / `incomplete`，不能自动降格为“独立接受”。

Alethe 是首选 certificate 互操作候选，因为当前官方覆盖 EUF 与线性算术，并存在多个重建 / checker 路径；CPC 用于忠实保留 cvc5 推理并作为备选。最终格式、checker、规则集和隔离边界仍由后续独立 checker 决策冻结。

### `sat`

- model 只是反例候选，不能直接支撑 `failed`；
- adapter 必须构造完整 canonical world，重放 `WF` / `Pre`、目标违反和 trace，并按 Evidence 规则标记 `reduced` 或经证明的 `proved-minimal`；
- model 缺字段、使用不可重建值、违反前置条件、无法重放或只来自 `unknown` 时，结果为 `unknown`，不得修补成反例；
- cvc5 自身 `check-models` 只能是同一后端的诊断，不能替代 Axiom counterexample replay。

### `unknown` 与操作失败

- 后端返回 `unknown` 时，按真实 explanation 映射为 `timeout`、`resource-exhausted`、`unsupported` 或 `indeterminate`；
- 外层硬时限终止进程为 `timeout`，明确内存 / 资源上限终止为 `resource-exhausted`；
- 二进制缺失或不可执行为 `backend-unavailable`；版本、协议、退出码、输出解析、崩溃或 I/O 错误为 `operational-error`；
- 证书要求未完成为 `incomplete-certificate`；
- 非零退出、空输出、同时出现冲突状态或 stdout 中有未声明内容必须失败关闭，命令退出零也不能代替结构化状态检查。

## 进入受控原型的验收条件

本 ADR 被接受不授权现在安装 cvc5、创建 adapter 或进入编译器实现。后续只有同时满足以下条件，才可在独立授权下开始验证后端原型：

1. 目标运行时与执行路径、首版编译管线、独立 checker 隔离边界继续按 ADR 0002 / 0004 的顺序完成决策；
2. cvc5 1.3.4 的精确非 GPL 制品、SHA-256、来源、签名 / 校验信息、完整依赖和许可证清单通过审阅；
3. SMT-LIB query 规范冻结同一 IR / obligation 到同一字节，并拒绝量化词、字符串扩展、浮点、非线性算术、隐藏随机性和未登记选项；
4. AX-B01 至 AX-B04 每题至少一个代表性核心义务产生无 trust step / hole 的完整 proof artifact，并由生产进程之外的 checker 接受；
5. 八个错误候选的 model 都能转换、缩减并重放为规范要求的 counterexample；伪造、缺失、Pre 不成立和不可重放 model 被拒绝；
6. 四个 timeout 场景、资源耗尽、进程崩溃、版本不匹配、畸形输出、缺失证书和 checker 不支持均保持真实 `unknown` / `incomplete`；
7. Linux、macOS 和 Windows 运行相同 query 字节得到兼容状态；证明原始字节可以因工具身份不同而不同，但结论、义务绑定和规范反例不得依赖平台迭代、locale 或路径；
8. Evidence 同时展示 `certificate` 与 `backend-attestation` 的差异，生产报告不能冒充独立结果，独立 checker 不复用生产义务生成器。

这些条件是未来原型入口，不是已经取得的实验结果。编译器实现入口仍须满足 ADR 0002 与 ADR 0004 的全部其余条件。

## 风险与重新评估

- 容量展开可能产生较大 query 或 proof；资源失败必须保持 `unknown`，不得偷偷切换到量化编码或减小容量。
- cvc5、proof printer、Alethe / CPC checker 和签名都可能有同源缺陷；certificate 缩小但不会消除可信计算基。
- 非 GPL build 仍包含具有各自义务的第三方组件；许可证兼容不等于供应链已经审计。
- solver model 不是 Axiom world；确定性重建与独立重放是 `failed` 的必要条件。

出现以下任一事实时，以新 ADR 重新比较 cvc5、Z3、Lean 或其他候选，而不是增加隐藏 fallback：

- 四题所需的 QF_UFLIA 子集无法在 safe / proof-producing 配置中稳定求解，或至少一种核心义务长期无法生成无 trust step / hole 的可检查证明；
- model 无法无损重建 AX-B01 至 AX-B04 要求的单行、双行、分组或成对 world；
- 受审阅资源预算下，四题正确与错误候选持续大面积 `unknown`，根因是后端或证明格式而非错误编码；
- Linux、macOS、Windows 无法获得许可证可接受、可摘要且行为一致的受支持制品；
- 必需功能只能通过 FFI、GPL build、网络服务、未固定 nightly 或无法审计的原生依赖提供；
- cvc5、证书格式或 checker 的版本变化破坏既有 Evidence 重放，且显式迁移不能保留绑定与拒绝边界；
- Z3 或证明助手路径后来能以更小可信计算基、完整证书和可接受成本覆盖同一四题。

修改首个验证后端、允许默认 FFI / SDK 链接、允许 silent fallback、把 `unknown` 当成功、取消 model 重放或允许不完整证明冒充 certificate，必须以新 ADR 替代本决策。只升级精确 cvc5 patch 版本仍须单独进行语义、proof、model、平台、许可证和供应链复验；通过后可更新本 ADR 的实现基线，不自动改变首域语义或 Evidence 格式。
