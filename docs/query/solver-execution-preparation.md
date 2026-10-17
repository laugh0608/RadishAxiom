# P4 真实 solver 窄入口执行层设计

日期：2026-10-17。状态：设计范围随 [ADR 0028（Accepted）](../adr/0028-bounded-solver-calibration-entry.md)接受；具体实现清单与验收材料另行形成，不是已实现接口、工具接受或执行许可。

用途：把既有纯 P4 请求接到可归因、可拒绝的真实诊断。事实与缺口见[准备记录](../records/2026-10-17-solver-preparation.md)，不在本稿重复宿主动态状态。

## 输入与信任边界

执行层只接收已 strict 重建的 immutable `SolverRequest`，不接收 shell 字符串、任意 argv、环境变量、工作目录或命令路径。生产实现宿主仍是 Rust；P4 组件继续不启动进程。新增执行控制与 Linux bootstrap 各自保持窄职责，不引入通用作业系统。

现有 `SolverToolIdentity` 只检查平台及摘要形状，不能认证接受记录或实际二进制。执行层必须核对以下全部输入：

| 输入 | 必须核对的内容 |
| --- | --- |
| 请求 | 新 solver profile、query0.3 / v0.5、P4 与 query 规则摘要、IR / P2 / 目标、symbols / layout、完整 budgets、stdin 长度与 raw digest |
| 工具 | 登记 ZIP 摘要、精确成员 `cvc5-Linux-arm64-static/bin/cvc5` 摘要、正式接受记录及其适用平台 / 依赖 / 许可证范围；静态观察不能充当接受记录 |
| 执行器 | Rust controller / bootstrap 来源、构建工具与参数、二进制摘要、系统调用策略摘要；构建输入未接受时不构建 |
| 镜像 | 独立的最小 scratch rootfs，仅含已接受 CLI 与 bootstrap；固定本地不可变 image ID / 内容摘要，无 shell、包管理器、SDK、JNI 或 JAR；完整文件清单与配置参与绑定 |
| 宿主 | 显式 `orbstack` context 对应的 daemon 身份、Linux arm64、kernel / runc、cgroup 与能力资格记录；不得跟随用户随后改变的当前 context |

所有摘要都核对实际字节；只比较名称、标签、`--version` 文本或工具路径不够。请求中的 payload 与 acceptance 摘要必须按最终接受契约核对，不能用合成测试身份启动。公共 acceptance 生成器目前不支持 cvc5；后续若扩展，须同时审阅 schema、生成器、负例及旧字节回归，不手改生成 JSON 冒充已验收。

## 控制路径与隔离方案

建议使用固定 Docker CLI 子命令集合管理精确容器 ID，命令以参数数组调用；Docker CLI 本身的路径 / 摘要、daemon 及 runtime 都进入本地可信边界。显式 context，清除 `DOCKER_HOST` 等环境覆盖，控制端仅保留所需连接配置，不向工作进程传递凭据；任一 daemon 身份不符即拒绝。无自动 pull、build、context 创建或服务启动。

每次 create / attach / start / inspect / wait / kill / remove 都有外层剩余时限，控制输出有独立小预算；不能用无界 Docker 日志作为 solver 流。`Tty=false`，stdout / stderr 分离，stdin 精确 query 后 EOF，解析数据流前核对 Docker transport 帧，禁止把控制端 stderr 混入 solver stderr。未来实现须先锁定实际使用的 CLI 子命令、配置与传输处理；仅有本文不能声称执行器已可调用。

容器配置要求：非特权 UID、全部 capability drop、no-new-privileges、只读 rootfs、独立 PID / mount / network namespace、无 host namespace / bind mount / volume / Docker socket / device / credential、无 restart / healthcheck / init helper。network none 与只读 rootfs 只是外层配置，不等于禁止网络 syscall 或文件读取。不得使用 `--privileged` 或为了读取 cgroup 而挂入宿主控制目录。

最小 bootstrap 是显式受信任代码：打开固定 CLI，核对完整字节并复制进 sealed memfd，关闭非必要 FD，在限制生效后以 `execveat` 装载同一已固定对象，`envp=[]`；复制、校验与加载计入同一资源窗口。不得校验一个路径后再按可变化路径执行。执行 FD 为 CLOEXEC，过滤器仅允许该 FD 的一次装载形态；执行后不得通过新打开 / 复制 FD 恢复执行能力。此路径的内核 / runtime 支持尚未验证，失败不得退回普通路径执行。

bootstrap 在进入 solver 前装载 AArch64 syscall 白名单：只容许必要的匿名内存、信号、时钟、退出及指定 stdio I/O，禁止文件访问、socket、进程 / 线程创建、mount、ptrace、权限与 namespace 变化、再次加载程序及未知 syscall。清除附加 FD 与环境。具体白名单须从精确静态 payload 的运行需求审阅后固定，并用合成探针验证；不能根据失败日志自动扩充。默认 Docker seccomp 是通用策略，不作为本方案的最终策略。[Docker seccomp 文档](https://docs.docker.com/engine/security/seccomp/)

若 payload 初始化依赖文件、额外 syscall 或线程而当前方案不允许，保留失败并回到设计审阅；不因是官方静态包就假设无外部能力。

## 资源范围与时间线

| 资源 | 固定值与执行要求 |
| --- | --- |
| stdin | 1,048,576 bytes；进入外部执行前校验长度 / 摘要，只发送请求原文 |
| stdout / stderr | 4,194,304 / 65,536 bytes；并发持续读取；探测到上限后的下一字节立即触发终止，最多保留有界前缀与截断标记，不排空无界流 |
| 内部 solver | 原十二参数保持，包括 `--rlimit-per=1000000` 与 `--tlimit-per=5000`；不是外层资源保证 |
| 内存 | cgroup v2 `memory.max=134217728`、`memory.swap.max=0`；包含 bootstrap、CLI memfd、solver、后代及内核按该 cgroup 收费的内存；不是“solver heap 128 MiB 再加 bootstrap” |
| 生命周期 | 6,000 ms 单调时钟，从第一项执行控制操作开始，包含 create / setup、加载、stdin、求解、模型输出、进程 / 流收尾与无遗留确认；准备已接受静态镜像和纯 query 编码在窗口外，分别记录 |
| 后代与重入 | 无 solver 子进程 / 线程创建权限；另设 pids 上限作为纵深限制，值须在负向探针方案中冻结，不因需要线程静默放宽；同一容器一次运行、无 restart、无并行 attempts |

Docker 对 memory / swap 的配置须核对容器实际值；仅 `docker info` 返回支持不足。期望配置使 memory+swap 总量等于内存值，但仍以 Linux `memory.swap.max=0` 的实际读回与负向探针为准。[Docker 资源文档](https://docs.docker.com/engine/containers/resource_constraints/)

控制进程、daemon 与 VM 内存不在该 cgroup；P3 compact 的逻辑预算也不是 OS 内存限额。Linux `memory.max` 有暂时超额语义，不能把采样峰值包装成绝对瞬时上界；该解释已由 ADR 0028 D2 接受。[内核资源语义](https://docs.kernel.org/admin-guide/cgroup-v2.html)

超限或时限到达时终止整个受控树，收集已界定字节与退出 / OOM / cgroup 观察；不能只杀 Mac Docker 客户端。优先要求实际 runtime 的整树终止与回收路径通过验证；`cgroup.kill` 的内核能力不等于当前 Docker API 已提供这项保证。没有可用且已验收的路径即不能启动 solver。cleanup 超出 6 s 或无法确认树为空时记为超时 / 隔离失败，阻断后续尝试，不把超时后退出改写为成功；不宣称普通 OS 是实时系统。

OOM 必须来自受信任的容器状态与可归因内核事件，不能凭 exit 137 或 stderr 猜测。原始失败、各终止观察及缺失状态分别保留，由既有 P4 失败优先级处理。

## 合成宿主资格探针（待授权执行）

先用自有小程序验证执行层，不加载 cvc5。探针输入、二进制与预期均固定并绑定；任何一项失败停止，不能转 best-effort。

| 检查 | 必须取得的观察 |
| --- | --- |
| 身份 / 配置 | 错镜像、错 CLI、错接受记录、错宿主、环境注入与 argv / stdin 篡改在 solver 启动前拒绝 |
| 加载 | 校验后替换路径不能改变被执行字节；无法二次 exec、打开文件或读取额外 FD；环境为空 |
| syscall / namespace | 文件读写、网络、fork / clone、ptrace、权限提升与 namespace 变化均被拒绝；不会访问宿主资源 |
| memory / swap | 实际限值读回；内存压力触发可归因限制，不能逃出 cgroup；swap 禁用；收尾无后代 |
| 流 | stdout / stderr 恰等与差一、双流并发、提前 EOF、坏 transport 帧、控制端失败与截断均保持绑定和失败；无死锁 |
| 时间 / 清理 | 启动挂起、无限循环、输出阻塞、忽略信号、controller 中断与 daemon 失联分别有可观察终止 / 失败；不能确认清理时不再执行 |

daemon 失联后的外部进程回收不能只靠客户端定时器。未来实现须交付独立于 Mac 客户端存活的已验证兜底终止机制，且该机制自身开销计入明确范围；否则 D2 时限资格不成立。本稿不通过加一个尚未设计的 watchdog 声称问题已解决。

## 真实校准与单目标清单（待另行授权）

八份校准输入均为自有合成 IR 经既有 P1 / P2 / v0.5 编码和 P4 规划生成，执行前冻结具体 bytes / digest / 期望，不手写替换生产 query。每份只一个目标、一个新进程；不能在运行中补发 SMT 命令。

| 编号 | 覆盖目的 | 可接受观察 |
| --- | --- | --- |
| C1 | Bool 自由输入和一个易于手算的违反目标 | sat 完整模型，既有 decoder 与 P4-B 对应手算 |
| C2 | Int 正 / 零 / 负与大整数叶 | 合法整数文法，无浮点或范围修补，完整模型可重放 |
| C3 | Text literal、相同 / 不同类 | 现行 atom / as 子集及 literal 锚点，直接世界比较一致 |
| C4 | 未被断言使用的自由声明 | sat 仍有全部自由定义，缺项直接失败 |
| C5 | inactive 槽位与 Option None 内叶 | 模型完整性与遮蔽外部化按现行规则处理 |
| C6 | Record / Fixed / Enum / 多层 Option | 完整布局、类型和确定性世界可重放 |
| C7 | 保留 define-fun 与内联项混合 | 实际派生打印被现行精确清单 / 文法接受；不能扩白名单 |
| C8 | 自有手算不可满足查询 | unsat 单帧；不是证明，不要求输出 proof artifact |

校准中得到 unknown / timeout / memory / 畸形打印时原样保留并停止目标尝试；不修改参数追求预期状态。真实 unknown 能否稳定触发不作为这八份成功前提，超时与失败传播先用合成探针覆盖，不能报告为真实 solver unknown 已校准。`--produce-proofs` / `--check-proofs` 不等于导出证书。

八份校准通过且获单目标执行授权后，只尝试以下一项，仍不重试：

- IR：`crates/axiom-ir/tests/fixtures/v0.2/migrated/ax-b01-wrong-add.jcs`，raw `sha256:10e99922b4fe1c1490703b6e61dcc13e810b6dbfd5ffa1a444314a7d201fc970`。
- 精确 contract-guarantee：`sha256:4916b2ef17b43cab21bff8ae87433922c60fbf86fb72fc52972e06964584476e`。
- v0.5 query raw：`sha256:5ba58e0d9754c3448f299ce4d9be2060c2d91d829253ec3e4a170e0d4d07a85a`，962,642 bytes，原容量 100 / 501 自由符号；来源为[生产测量](compact-query-production-validation/ax-measurements.tsv)。执行前重建全绑定，不能仅凭该摘要复用请求。
- sat 时真实模型经原 decoder、`ReplayWorldInput::ModelCandidate`、完整 WF / 全部 Pre / 精确目标重放，并用独立有限路径核对实际世界。若目标未违反则诊断不一致并停止，不以候选名字代替答案。unsat / unknown / 资源失败均保留为该次实际观察，不冒充 checked / proved，也不扩大运行清单。

## 输出与实施顺序

未来本地观察至少绑定 request / query / tool / acceptance / executor / image / host qualification 摘要、参数与预算、两流完整字节或有界截断前缀及其摘要、实际 exit / outer termination / OOM 依据、时间窗口、清理结果。完整流和截断前缀的摘要不得同名混用；进程未启动也要记录准确失败阶段。主机名、路径、容器 ID 等运行定位只进本地诊断，不混入 query、公共 Evidence 或既有规范制品。

这些观察是待实施的本地版本化格式，尚未冻结 schema；在实现前先交付闭合字段、失败优先级映射、序列化与篡改测试。只有来源已认证、退出与流完整且无外层失败的结果才可送入 P4 正常路径；拒绝不能通过手工修 stdout 转成成功。

后续依次完成：精确制品接受缺口 → 执行层与观察格式审阅 / 纯组件实现 → bootstrap / 镜像构建的明确授权 → 合成资格探针授权与验收 → 八份真实校准授权 → 一次精确目标授权。每一步先形成可审阅清单，预计运行时间按实际实现再报告；当前没有可执行器和资格依据，不编造完成时长或作出执行承诺。
