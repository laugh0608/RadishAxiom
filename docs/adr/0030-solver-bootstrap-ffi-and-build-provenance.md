# ADR 0030：solver 原生 bootstrap 实施与构建来源

日期：2026-10-17。状态：Accepted，项目所有者于 2026-10-17 明确接受 D1–D3；F1 已提交为 `1a7ff38`，当前实施授权接续 F2 原生源码与 D3 C0 精确输入选择；不包含依赖下载 / 安装、Linux 制品或镜像构建、探针 / solver、系统修改或 push。本 ADR 不自动接受新工具、允许 `unsafe` 进入语义核心或授权 Linux 制品构建 / 外部执行 / 系统修改。用途：在 [ADR 0029](0029-solver-linux-supervision-and-capabilities.md) 和 E3 离线组件之后，选择真实原生入口的实施边界与 E0 证据不足时的接续方式。读者：项目所有者、实施者及验收者。

## 问题与现状

E3 已形成具体 ABI、W/S 纯策略、封套、cgroup 解析和模拟监督，提交为 `c489ec2`。但模拟对象混合 Mac/S 时钟和合成事实，不能直接改名变成真实执行能力。真实设置还必须处理 main 前标准库初始化、FD 重映射、listener 交接与收紧顺序、信号继承、通知 ioctl 的阻塞语义和进程退出时的非原子读回。

E0 的精确 cvc5 CLI 仍缺实际系统库 / 完整链接库存与来源到 binary 的关联。固定配方、归档摘要、CI 成功和发布时间相近均不能替代同一 CLI 的构建输入身份。此次[补证](../records/2026-10-17-cvc5-provenance-followup.md)的进展和失败必须保留，不因实施迫近而降低接受要求。

[具体实施方案](../query/solver-bootstrap-ffi-implementation-plan.md)列明顺序、原生安全前提、格式职责与批次；[独立审阅](../query/solver-bootstrap-ffi-review.md)记录对已接受纯模型的真实落地审查。以下决定是可分开接受的范围，不将其中一项接受推导为其余项授权。

## D1：实现宿主与复用边界

**已接受：Rust 2024 / pinned 1.97.1、静态 musl AArch64 候选，窄 raw-syscall adapter 与一个共享纯 core。**

- 新建私有 `solver-bootstrap-linux`，原生 `unsafe` 仅在该边界；`axiom-ir`、P4、simulation 与共享纯 core 继续禁止 unsafe，不链接 solver SDK。
- 从既有 E3 提取 `solver-supervision-core`，只共享 ABI、策略、wire 与 cgroup 纯规则；host 保留重导出与模拟类型，旧 bytes / golden / 拒绝行为不变。真实 Mac/S 驱动分别取得事实，不接受 `Synthetic*` 作为凭据。
- 载荷流式摘要在既有digest库增加增量接口并保持旧摘要；资源值由现有 `PROCESS_LIMITS` 的受审阅离线导出绑定，native 不接受运行时覆盖；新增两个私有 crate 与 path lockfile 变化只限这一复用边界。
- 精确 target std、musl/CRT、linker、compiler-builtins 及启动代码必须独立接受。没有新增第三方 Cargo crate不等于没有原生依赖；不自动安装任何工具。

主要影响：增加明确的原生 TCB、目标构建输入和局部 unsafe 审阅；std 启动发生在 main 前，不能用自有代码审阅覆盖它。选择此项只允许随后推进纯接口与原生源代码的受控实现；实际构建仍须工具链接受及精确范围授权，运行继续受 E0/E4 阻断。

备选是 no_std / 固定缓冲。它可减少初始化运行库，却需要新入口 / 栈 / TLS / 链接和大部分容器迁移审查，本轮不推荐并行维护。若 std 与原能力边界无法相容，停止并回到本决定，不静默改路线。

## D2：真实绑定、观察与阶段协议

**已接受：闭合启动描述、固定 S FD 映射、Mac/S 状态分离和有界退出过渡。**

- S 的 READY 前输入使用私有、有界、无路径 / 任意命令 / 资源覆盖的 `solver-bootstrap-start-v0.1`；描述绑定 request、query摘要、已接受payload、policy与预期image。Mac声明与S实际本地核验分开，不作自包含image摘要或“回显即认证”。
- 固定 S 21 角色映射，W/S 的实际过滤器 bytes 在执行前绑定；设置阶段先接listener、关闭冗余FD，最后安装S filter。首次CONTINUE状态先消费，仅发送一次；后续通知失败。
- Mac 保留 DM / δ 的因果计算，S只核对本地DL与挑战，真实捕获由私有事实入口构造。现有 simulation不改名复用。
- cgroup 与 waitid 的退出竞争可保留为明确过渡，原DL内至多两次读回；额外PID、资源事件、配置漂移及计数回退立即失败，全部原观察保留。最终成功仍要求真实reap、双EOF、S-only、runtime确认与精确删除。
- B在exec前没有handler并保持已接受的阻塞mask；mask跨exec保留这一事实列为实际CLI兼容性停止项。不自动清空mask、不扩大W syscall能力。

主要影响：新增内部启动输入及真实观察规则，改变的是真实适配方式，不是公共IR / Evidence、既有wire编码或模拟结果。必须补source混用、配置自引用、FD冲突、listener丢失、通知竞态、自然退出和deadline负例。若不接受退出过渡，初版仍可对读回竞争保守失败，不能宣称已有稳定快照能力。

## D3：E0 公开来源不足时的下一候选

**已接受：原发布CLI继续 not-accepted，另行准备同 pinned cvc5 版本的可追溯受控构建候选方案。**

本次补证不要求项目所有者用主观确认替代缺失事实，也不请求降低B1/B2。原CLI、摘要和缺口记录全部保留；新候选只在之后真正生成新bytes时登记独立工具身份，不覆盖或追认原CLI。

D3 先形成构建方案，并在随后 C0 选择精确输入：固定同一 cvc5 source commit、明确全部依赖 / patch / 系统库 / 编译器输入、消除浮动系统选择、保存link map / 对象清单 / copyright与实际构建关联、定义产物检查与E0本地使用接受范围。不得在方案中默认关闭某个功能来改变profile；任何编译选项变化及兼容影响逐项说明。包内SDK不进入运行镜像不等于可以忽略CLI中的静态依赖。这里要求闭合本次构建的实际输入和信任声明，不要求递归重建GCC或整个guest；工具链作为精确、已接受的受信任输入处理，避免无界取证。

这项选择会增加受审阅的候选构建工作和新的payload身份，但可使组成来源成为本项目可取得的证据。它**不授权下载 / 安装构建工具、编译cvc5、构建镜像、运行--version / solver或对外分发**。精确构建命令、工具输入、资源占用、输出与清理范围形成后，再请求对应动作授权；新CLI仍须独立E0接受、E4适配、E5原资源校准。

备选：维持原CLI为唯一候选，等待能绑定其摘要的发布者构建材料。该选择保持E0阻断，不自动联系上游、不重试已停止的管理员日志路径，也不以当前Ubuntu包或另一次作业替代历史事实。

## 不变项、顺位与验收

原容量、旧profile字节、1 MiB / 4 MiB / 64 KiB、128 MiB / swap0 / pids2、6 s与内部5 s / 1,000,000 steps不变。S、B、memfd、运行库和队列都计入原资源；不能以新来源或新实现宿主为由增限。E0工具接受、实际ABI/unsafe审查、E4资格和分别授权的真实动作继续独立。

F1 纯共享边界、启动描述、双端纯接口及 D3 候选方案已提交为 `1a7ff38`。项目所有者随后授权 F2 原生 wrapper / B 尾段 / S 驱动源码和 D3 C0 精确输入选择。本机脚本后端验证不能替代目标构建、编译输出审阅或真实内核资格；原生 backend 只适用于 Linux AArch64 LE LP64，尚无可执行入口。任何资格步骤均须先备齐可审阅源码/预期/制品/配置/命令/占用与清理，再请求相应外部动作。

本次接受不放宽现有策略；项目所有者先要求提交方案与补证、推进 F1 与 D3 方案，随后要求提交该批并接续 F2 与 C0。主代理主持设计与验收，具体实现继续委派gpt-6.1-sol / high。
