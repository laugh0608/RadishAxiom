# RadishAxiom 产品定义

## 定位

RadishAxiom 是面向 AI Agent 的验证优先语言与可信语义层。项目关注的核心问题不是创造一种新奇语法，而是缩小程序表达中的歧义和隐含状态，使 Agent 生成的程序能够被类型检查、约束验证、反例分析和独立审计。

项目标语：

> Constraints in. Evidence out.

## 稳定命名

| 对象 | 名称 |
| --- | --- |
| 项目与仓库 | `RadishAxiom` |
| 规划子域名 | `axiom.radishx.com` |
| 语言源文件 | `.rax` |
| 编译器 | `raxc` |
| 核心中间表示 | Axiom IR |
| 验证报告 | Axiom Evidence |

`.axiom` 暂不作为主源文件扩展名；未来只有在出现独立的人类规范文件或项目清单需求时再重新评估。

## 核心原则

1. **正确性相对于规范成立**：编译器证明实现满足已声明约束，但不得把约束本身自动等同于真实意图。
2. **所有信任必须可见**：外部调用、求解器假设、未验证代码和运行时依赖必须进入显式信任清单。
3. **验证状态不得二值化**：至少区分 `proved`、`checked`、`unknown`、`failed` 和 `trusted`。
4. **副作用必须显式**：文件、网络、时间、随机性、共享状态和外部能力不能隐藏在普通调用中。
5. **规范化优先于语法偏好**：同一语义应尽量只有一种规范表示；文本语法只是语义模型的投影。
6. **失败应产生证据**：验证失败优先输出最小失败约束、反例和可追踪执行路径。

## 初始边界

首个可行版本选择“有键有限表的确定性转换”：程序接收具有显式模式与键约束的有限输入表，以无外部副作用的确定性转换产生有限输出表。首批能力和基准边界见 [ADR 0002：首个目标领域与基准任务](adr/0002-first-target-domain-and-benchmarks.md)。该领域打通以下闭环：

1. 解析或接收结构化程序；
2. 生成规范化 Axiom IR；
3. 完成基础类型和效果检查；
4. 生成并求解验证义务；
5. 输出 Axiom Evidence；
6. 对失败条件给出反例；
7. 生成或解释执行一个现有目标运行时可承载的程序。

首版不把外部数据获取与持久化纳入转换核心，也不追求通用语言、完整 IDE、包管理生态、宏系统、任意元编程或不受约束的并发模型。

## 与 Radish 家族的关系

- RadishAxiom 不替代 RadishMind 的模型、Agent、工具编排和评测平台职责。
- RadishMind 可以成为 RadishAxiom 的 Agent 接入与评测方，但不是语言语义真相源。
- Radish、RadishFlow、RadishCatalyst 和 RadishLex 可以在未来提供真实领域案例，但不作为首个原型的强制依赖。
- RadishX 负责家族公开入口；`axiom.radishx.com` 只有在形成稳定公开产品后才进入部署。

## 许可证策略

- RadishAxiom 的原创代码、文档与配置采用 Apache License 2.0。
- 允许个人与组织使用、修改、分发和商业集成，以降低编译器、Axiom IR、验证器、SDK 与后端适配器的采用门槛。
- 第三方组件继续遵循其各自的许可证；项目名称、Logo 与其他品牌标识不因 Apache License 2.0 而获得商标授权。
- 未来的托管验证服务、企业连接器、合规策略包、认证与支持可以独立提供商业服务，无需收紧开放核心的许可证。

开放基础层、商业化边界、用户产物、品牌认证和外部贡献治理的长期原则见[许可证与生态策略](licensing-strategy.md)。

## 已冻结的实现宿主边界

生产 `raxc` 使用 Rust 2024 edition 与精确固定的 stable 工具链，具体理由、约束和重新评估条件见 [ADR 0004：`raxc` 生产编译器实现语言](adr/0004-raxc-production-implementation-language.md)。该决定不适用于独立 checker，也不冻结表面语法、目标运行时或首版编译管线。

## 已冻结的首个验证后端边界

首个验证后端采用 cvc5 1.3.4 的独立命令行程序，通过版本化、可摘要、可限时的子进程边界承载量化词自由的受界义务。`unsat` 的证明 support、`sat` model 的反例重放、`unknown` 与操作失败的关闭规则，以及许可证和重新评估边界见 [ADR 0005：首个验证后端与失败关闭边界](adr/0005-first-verification-backend.md)。该决定不选择最终证明证书格式、独立 checker、目标运行时、编译管线或表面语法。

## 已冻结的首个目标执行边界

首个目标运行时采用 Node.js 24.19.0 LTS 的独立命令行程序，首条执行路径从 canonical Axiom IR 确定性生成受限 ECMAScript ES module，并在静态核心义务和具体输入检查全部通过后一次一进程执行。数学整数、精确文本、表顺序、codec、host conformance、`implementation_inconsistent`、操作失败、权限、许可证与重新评估边界见 [ADR 0006：首个目标运行时与执行路径](adr/0006-first-target-runtime-and-execution-path.md)。该决定不选择首版编译管线、独立 checker、表面语法或发布载体。

## 尚未冻结的决策

- 表面语法；
- Axiom Evidence 的具体证明证书格式与独立检查器实现；
- 首版编译管线的阶段、制品与失败协议；
