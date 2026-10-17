# P4 窄入口执行层实施清单

日期：2026-10-17。状态：实施规划，依据 [ADR 0028（Accepted）](../adr/0028-bounded-solver-calibration-entry.md)及[执行设计](solver-execution-preparation.md)。读者为项目所有者与实现者；本文不授权编写后直接运行 executor，也不表示闭合格式和 syscall 策略已经冻结。

本清单最初随精确 CLI 补证提交为 `ff2e4ed`；随后项目所有者授权 E1–E2 纯组件与模拟测试，具体内部类型和边界以[模拟规则](solver-diagnostic-simulation-v0.1.md)为准。下文真实执行类型仍是待 E0 / E3 闭合的设计目标，不能把模拟记录解释为这些能力。原容量、query / P4 旧字节、十二项参数、stdin 1 MiB、stdout 4 MiB、stderr 64 KiB、内存 128 MiB、外层 6 s、内部 5 s / 1,000,000 steps 全部保持。

## 已有入口与复用范围

- `crates/axiom-ir/src/solver.rs` 已提供 immutable SolverRequest、strict 重建、响应与候选；`SolverToolIdentity::new` 只核对形状，不能承担真实工具认证。
- `SolverResponseInput` 能承载 request digest、两流 bytes / complete、`ProcessExit` 与 `OuterTermination`；执行层须认证这些观察。P4 现有失败优先级和模型文法直接复用，不新增“宽松真实 solver”入口。
- P4-B 沿 `ReplayWorldInput::ModelCandidate` 重建世界、完整 WF / Pre 和精确目标，复用既有求值语义；不依赖 solver 派生项回答目标。
- `checker-runtime/src/spawn.rs` 是 checker 的指定态 plan / policy 路径，不能借它的资格或资源口径启动 cvc5；不修改 checker 激活、Darwin store 或公共 runtime policy。
- 现有 `axiom-ir` 全 crate `forbid(unsafe_code)` 且不含 OS spawn。私有 `crates/solver-diagnostic-host` 承载本次纯内存模拟控制，只有现有工作区 path 依赖；不在其中重写 IR、query、模型或通用调度框架，也没有实际副作用入口。

## 分批实施与交付门禁

| 批次 | 精确交付 | 完成证据 / 停止线 |
| --- | --- | --- |
| E0：工具身份与接受闭合 | 先闭合[补证 B1–B3](../records/2026-10-17-cvc5-cli-dependencies.md#剩余缺口与有界接续)；给出精确 ZIP / CLI / 完整库存 / 许可来源 / 接受范围；审阅 cvc5 acceptance schema 与生成器扩展 | 当前阻断。来源观察不得冒充 acceptance；旧接受记录字节保持，新增格式需正负例 |
| E1：纯执行计划 / 观察格式 | 定义下表类型与闭合本地记录；从同一 SolverRequest 生成执行计划，strict 检查身份、资源、argv、stdin；不启动外部进程 | 纯组件可先实施，但真实路径须 E0。固定字节、篡改拒绝、失败优先级和预算测试通过 |
| E2：控制端与传输 | 新私有 crate 中分开 identity / observation / controller / transport；参数数组、精确 Docker CLI / context / daemon / image 身份，独立控制诊断流，单次容器状态机 | 先用内存 / 自有模拟传输覆盖控制失败、乱序帧、双流边界与中断；模拟不计宿主资格 |
| E3：Linux bootstrap 与兜底终止设计收口 | 固定 ELF 装载、空环境、FD、权限、syscall 白名单、资源读回和独立终止机制；提交具体 Linux ABI / unsafe 审阅表 | 下节 B4 / B5 未闭合前不宣称可构建、可执行；不自动增线程、开放文件 / 网络或退回路径 exec |
| E4：精确构建与宿主资格 | 先列 Linux arm64 Rust 工具 / 依赖接受与构建 recipe，再生成最小镜像；随后运行自有负向探针矩阵 | 构建、镜像写入与容器探针均须另行精确授权；当前禁止。任何宿主配置缺口报告，不修改系统或启用 privileged |
| E5：八份真实校准 | 先生成并冻结 C1–C8 输入、完整请求、期望与清理清单，再分别用同一执行器 / host qualification 运行 | 当前禁止。任何身份、模型文法、完整性或资源失败停止；不追加选项 / 修改 parser 求通过 |
| E6：一次目标尝试 | 校准通过后冻结原容量 wrong-add contract-guarantee 请求，单次运行并接既有 P4-B 与独立有限世界核对 | 当前禁止且须单独授权；目标与 query 摘要沿执行设计，成功也不升级 proved / Evidence |

E1–E3 是最小私有执行切片，不扩大到 installer、产品 launcher、公开 CLI / SDK、六平台或全 P0–P9。涉及新 crate / 本地依赖的 lockfile 变化，应在实施授权中明列；不借实施清单自动安装新 crate 或 Linux 工具链。

## E1 的具体接口与记录清单

下列是真实执行的拟议内部类型与责任，实施前以具体字段稿和正负例审阅，不向现行公共格式追加成员。本次只实现显式 `SimulationIdentity` / `SimulationPlan` / `SimulationObservation`，不构造真实接受、宿主资格或认证捕获类型。

| 类型 / 记录 | 必须承载 | 必须拒绝 |
| --- | --- | --- |
| `AcceptedSolverPayload` | archive raw、CLI member / raw、实际依赖库存与许可证来源、acceptance raw / scope、平台 | 仅形状合法但不存在 / 不适用的接受记录；SDK / 其他 CLI 摘要替换 |
| `SolverHostQualification` | 选定 daemon / kernel / runtime / image / bootstrap / 策略 / 工具摘要及负向探针结果 | 只拿 docker info、历史主机或另一镜像作资格；未知 / 未通过项 |
| `SolverExecutionPlan` | immutable request raw、完整身份链、argv 顺序、stdin raw / bytes、所有固定资源、一次运行状态 | 任意参数、shell、环境、路径、隐式默认、current context 跟随和容量缩减 |
| `CapturedSolverResponse` | 来自同一已启动计划的完整 stdout / stderr、各自摘要、exit、外层终止、完成与清理认证 | 把纯 parser 的合成 `SolverResponseInput` 标为真实；调用方随意声称 exited=0 |
| 本地失败观察 | request / plan raw、失败阶段、实际启动与否、完整流或截断前缀的区别、所有终止信号、可归因 OOM / 时间 / 清理状态 | 用日志猜 OOM、丢弃早期失败、截断摘要冒充完整流、清理失败仍继续 |

E1 首先冻结本地观察的 format / version、闭合字段、canonical JSON、大小预算、摘要域以及枚举映射；复用现有 JSON / digest 能力。运行定位信息（容器 ID、路径、宿主信息）仅进入本地诊断，不改变规范 query 或既有请求。身份型记录和运行定位分开绑定，缺失信息显式 unknown，不能填默认成功。

纯测试至少包含：新旧 profile 错配、acceptance / CLI / host / image / request 任一摘要漂移；预算恰等 / 差一 / 溢出；同 stdout 对应不同 exit / truncation / request 不同身份；OOM 与 timeout / stream limit 同时发生时所有事实保留且沿既有主要失败优先级；失败流不能物化候选；正常模型逐字节交给原 P4 decoder。

## E2 状态机与边界

计划校验 → create → attach → start → 发送 stdin / EOF 与并发捕获 → wait / inspect → 终止或正常收尾 → 确认空树与清理 → 发布本地观察。每个状态都绑定精确容器 ID 和剩余单调时限；不使用名字模糊匹配、重试、restart、pull 或自动切换宿主。

未来真实 Docker CLI 子命令及参数模板应在 E2 内集中维护；本次只提供类型化模拟意图，不生成 E3 尚未冻结的可执行 create 配方。真实 create 不得传 shell、host mount、设备或秘密。stdout / stderr 的 transport 与 Docker 控制日志必须分开，坏帧 / 断连 / 缺退出事件失败。控制命令自身有界，停止客户端不能替代容器终止；不得让 cleanup 的失败被解析出来的 sat 覆盖。

默认不新增第三方 Rust 依赖；若现有标准库不能可靠处理期限 / I/O / OS 接口，先提出最小依赖或 FFI 审阅，不私下引入 runtime。纯 IR crate 的 unsafe 禁止保持；原生调用仅能落在明确的 Linux bootstrap 边界，列明 ABI、内存安全前提和架构限制。

## E3 必须先解决的两个执行缺口

| 缺口 | 必须形成的具体决定 | 对实施的影响 |
| --- | --- | --- |
| B4：控制端失联后的终止 | 单纯 bootstrap exec 替换自己加 Mac 定时器，不能认证客户端 / daemon 失联后的 Linux 兜底。需提交最小受信任监督机制的拓扑、存活条件、计时起点、终止树与退出观察 | 不能用待实现 watchdog 当作已有保证。若引入额外进程或扩大 TCB，先明确其代码、资源归属和可观察性；仍只有一个 solver attempt |
| B5：实际 cgroup / syscall 能力 | 明确在当前非 privileged Docker 路径中如何读回 memory / swap、获得可信 OOM 和整树清理结果，以及如何验证 sealed memfd / execveat / seccomp / 空 env | 若必须挂载宿主控制目录、改变系统配置或放宽 solver 能力，则停止并回到设计审阅；默认 Docker seccomp 不够 |

Linux ABI 清单须至少覆盖 memfd / seal、固定 FD 的 execveat、FD 清理、UID / capability / no-new-privileges、seccomp 装载、计时 / 信号与终止观察；具体 allowlist 在 E3 提交时冻结。CLI 已发现 Editline / terminfo / glibc 线索，不能假设“静态链接即不调用文件接口”。实际需要能力但 profile 禁止时记录失败，不自动开放。

时限资格必须覆盖真实启动 / 捕获 / 终止路径；只能做到“超时后最终回收”时不报告 6 s 成功。Linux cgroup 的已接受记账口径不取消内核暂时超额语义，也不把 daemon / VM / Mac 开销计入 128 MiB。

## 后续授权清单与当前交接

补证与清单已提交为 `ff2e4ed`，随后 E1–E2 纯组件与模拟测试获得单独授权；实现由 gpt-6.1-sol / high 承担，主代理主持设计与验收。E0 剩余材料和 E3 两项设计缺口继续作为真实路径硬门禁；本次没有镜像、探针、solver、系统配置或 push 授权。

在镜像构建、探针或 solver 授权前，必须交付具体制品 / 容器配置、精确命令与目标、预计持续时间与占用、失败保留目录和按精确 ID 清理办法；此时才申请对应外部动作。当前不列可直接复制运行的 docker 命令，避免尚未合格的组合被误当成已验收执行配方。
