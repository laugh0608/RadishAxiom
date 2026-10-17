# 真实 bootstrap / FFI 实施方案

日期：2026-10-17。状态：[ADR 0030](../adr/0030-solver-bootstrap-ffi-and-build-provenance.md) D1–D3 已 Accepted；F1 已完成[纯组件本机验收](../records/2026-10-17-solver-f1-validation.md)，D3 构建候选方案已形成；二者已提交为 `1a7ff38`，当前授权接续 F2 原生源码与 D3 C0 精确输入选择。用途：把已接受的 E3 能力边界落实为可审阅的模块、设置顺序、资源所有权、构建输入和验收批次。读者：项目所有者、原生实现者与验收者。本文不是运行资格、工具接受记录、可执行容器配方或对外分发许可。

## 不变项与本批范围

沿用 ADR 0028 / 0029：原容量、旧 query / P4 字节和配对、十二项 solver 参数、stdin 1 MiB、stdout 4 MiB、stderr 64 KiB、同一 cgroup 128 MiB / swap 0 / pids 2、Mac 全局 6 s 与 solver 内部 5 s / 1,000,000 steps 不变。没有因 S、sealed ELF、标准库、队列或工具接受缺口而另加额度。初始方案批交付方案、源码接口核对及 E0 补证；当前接续 F2 原生源代码与 D3 C0 输入选择。原生代码只通过本机脚本后端实施检查，不开放公共执行入口、不下载或安装依赖、不构建 Linux binary / 镜像、不运行探针或 solver。

E3 纯组件已提交为 `c489ec2`。它们是模拟与离线检查，不是可直接改名使用的真实执行器：`SimulationSupervisor` 同时持有 Mac 和 Linux 合成时钟，`arm()` 要求先由同一对象 `make_arm()` 产生提议；真实 S 无法取得 Mac 接收时刻。Synthetic child / pointer / cgroup 事实也不能成为真实凭据。真实路径必须在各自进程取得事实，并保留来源边界。

## D1 候选结构与原生边界

推荐第一版使用 Rust 2024 / 仓库 pinned `1.97.1`，候选目标为 `aarch64-unknown-linux-musl` 的静态 ELF；这只选择候选构建方式，不宣称该目标工具链已接受或最终 ELF 无动态依赖。S 的自有 OS 调用集中在小型 AArch64 raw-syscall 模块；不向 IR、P4 或 simulation crate 开放 `unsafe`，不链接 cvc5 SDK。

| 拟议模块 | 责任与允许依赖 | 禁止混入 |
| --- | --- | --- |
| 私有 `solver-supervision-core` | 从现有 E3 提取 ABI 值编码、wire 编解码、cgroup 纯解析和策略生成；仍 `forbid(unsafe_code)`，复用 `radishaxiom-digest` | OS、实际资格、IR / query 求值；把字段合法性包装成认证 |
| 现有 `solver-diagnostic-host` | 保留 synthetic 身份 / 状态机和 Mac 计划接口；对外保留现有 E3 模块的重导出，继续既有离线验收 | 给模拟完成对象增加升级为真实执行的开关 |
| 私有 `solver-bootstrap-linux` | S 设置 / 监督及 B 固定装载；真实 backend 限精确 Linux AArch64 LE LP64，类型化 wrapper / 驱动可在 Darwin 用脚本后端编译检查；原生句柄、局部 FFI 与本地观察 | shell、任意 argv / 路径、通用执行回调、线程池或其他架构 fallback |
| 后续 Mac adapter | 从既有 SolverRequest / E0 接受记录 / E4 资格构造启动描述；按 DM 驱动精确 runtime / container ID，消费真实捕获 | 在纯 core 里 spawn Docker；用正常 response 掩盖清理失败 |

F1 提取只整理本节共享规则，未拆整个 IR 或 runtime。原 wire 字节、W/S cBPF golden 和旧模拟结果必须逐字保持；真实生命周期另由 Mac 状态与 S 状态驱动，与既有模拟参考作共同事件矩阵比较。共享低层规则，不共享虚构观察来源。新增两个私有 crate 的 path 依赖及 Cargo.lock 改动已随 D1 接受；F1 仅新增纯 core，原生 crate 在 F2 新增；没有新增或升级第三方 Rust crate。

F1 已在既有 `radishaxiom-digest` 内增加增量输入状态，复用同一压缩函数并让旧接口委托它；分块与旧摘要字节一致性须持续核对，不另建第二个 SHA 实现。复制只保留一个受界块，不额外保存完整ELF缓冲；原文件页和memfd仍按内核记账，不宣称只占一份。

原 `PROCESS_LIMITS` 仍是 query / P4 资源源。Linux 侧固定资源及 W/S 策略由受审阅的显式离线导出入口生成输入清单，带规则 / 源码 / 输入摘要；提取后的 pure codec 接收类型化预算，host 从既有常量传入，native 仅接受构建时生成的固定版本。不得从启动描述覆盖数值，不能手抄一套可独立演变的默认值。导出不是 Cargo build.rs 中的下载 / 自动执行；生成输入纳入制品清单并作双向一致性检查。

F1 已将纯实现提取至 [solver-supervision-core](../../crates/solver-supervision-core/README.md)，host 保留旧入口和固定预算包装；增量摘要复用既有 digest。闭合启动描述、strict 请求规划与双端接口详见[启动声明 v0.1](solver-bootstrap-start-v0.1.md)。这些接口只处理声明、字节和时间输入，不取得真实观察或执行能力。

### F1 离线资源 / 策略输入

host 的 `bootstrap_manifest::export_offline_inputs()` 与显式 example `solver_bootstrap_manifest` 生成四份文件：`manifest.json`、`inputs.json`、`worker.cbpf.bin`、`supervisor.cbpf.bin`。输出必须写入新建的 `.tmp/<name>` 目录，不覆盖已有结果；库函数本身没有文件访问。清单格式为 `solver-bootstrap-resource-policy-inputs-v0.1`，资源、协议预算、固定 21 FD 角色和 W/S 实际 bytes 均参与绑定。

`manifest.json` 保存生成入口、22 项实际编译时通过 `include_bytes!` 捕获的源码 / Cargo 输入之路径、长度与 SHA-256、有序来源清单摘要，以及另外三份文件的长度 / 摘要；这是生成相关的局部来源清单，不是完整编译器或原生 binary 来源认证。源码摘要不把本 manifest bytes 自身作为输入，避免循环。`inputs.json` 只导出原 `PROCESS_LIMITS`、原 E3 监督值与 wire 协议常量，输入清单不是运行时资源覆盖入口。

`check_offline_inputs` 对本次编译的资源 / 源码 / 策略作双向一致性核对；[独立 Python 复核](../../scripts/check-solver-bootstrap-inputs.py)另核对固定资源、角色、来源字节及原 W/S golden，并复用独立 E3 有限语义检查。源码改变后旧导出仍代表旧编译捕获，但不能通过当前源码一致性检查；须在新目录重新导出，不能改摘要迁就旧材料。

此清单固定 `scope=offline-pure-inputs-only`、`outer_setup_policy=not-established`、`native_build=not-accepted`。外层设置策略尚未形成，故本清单不是启动描述所要求的完整 `policy_bundle`，不能拿其摘要直接补成已接受策略、镜像或 Linux 制品；CLI / 工具链 / E4 接受仍独立。

### std / musl 的真实代价

Rust `std` 的初始化发生在自有 `main` 之前。[精确 1.97.1 Unix 初始化源码](https://raw.githubusercontent.com/rust-lang/rust/1.97.1/library/std/src/sys/pal/unix/mod.rs)包含标准 FD 检查、SIGPIPE 处置及栈溢出初始化；[对应实现](https://raw.githubusercontent.com/rust-lang/rust/1.97.1/library/std/src/sys/pal/unix/stack_overflow.rs)需要纳入启动调用审阅。它们和 musl / CRT / allocator / compiler-builtins 都是构建与运行信任输入，不因没有第三方 Cargo 依赖而消失。

候选条件：运行时必须提供真实 0/1/2；关闭 FD 的修补分支不应在合格路径触发。外层 setup policy 必须按精确启动代码审查实际调用，未列清即停止，不使用 unconfined。自有代码第一项建立 BOOTTIME 准备期限，但不能把 Rust/CRT 之前的时间声称已受本地 timer 保护；Mac DM 始终覆盖整个启动。S 严格阶段不调用 std 文件 / 时间 / 格式化日志接口，不创建线程；终止走 raw `exit_group`，不返回 `main` 触发标准库清理。必要堆分配和分配失败按原内存与失败关闭处理，不能称现有 Vec/BTreeMap 代码为无分配实现。

备选 `no_std` / 固定缓冲会减少标准库初始化，却新增 `_start`、栈对齐、auxv / TLS、allocator 替代、compiler-builtins、链接脚本与所有动态容器迁移的责任。本批不同时维护两套路径。若精确 std 启动与严格能力不能相容，退回设计决定，不自动改成 no_std 或追加 syscall。

## D2 启动绑定与双端职责

### 闭合启动描述，避免 READY 的输入空缺

现有 wire 先由 S 发 READY，故 request / policy / image 等绑定不能等收到 ARM 才得知。提议增加私有 `solver-bootstrap-start-v0.1` 启动描述，经 Docker create 的固定 S argv 数组提供；不改变 solver W 的十二参数或现有 wire 格式。

拟议入口只有固定 bootstrap 路径、固定参数名和一个有界描述值；最多 4,096 个 UTF-8 bytes，只含版本、attempt、request digest、query 长度 / raw digest、policy bundle digest、预期 image digest、CLI 接受记录 digest 与启动配置 digest。所有 digest 精确形状，长度 checked，未知 / 重复字段或附加参数拒绝。它不接受路径、命令、环境、原 query、资源覆盖或任意 solver argv。F1 编码固定为单个无空白 ASCII JSON 对象，下表顺序即键顺序；禁止重复/未知键、转义、额外空白、BOM、尾随数据，uint32 用无前导零的十进制。所有摘要为 `sha256:` 加 64 位小写 hex，attempt 为 64 位小写 hex；解析后必须按同一规则重编码逐字相等。F1 已按此闭合规则实现及反例核对，它仍是私有启动输入，不是公共接受 schema。

| 键（顺序固定） | 类型 / 绑定 |
| --- | --- |
| `format` | 固定 `solver-bootstrap-start-v0.1` |
| `attempt` | 32-byte 尝试标识的 hex，映射 wire attempt |
| `request` | 既有完整 SolverRequest bytes 的 raw digest |
| `query_bytes` | 1..1,048,576 的 uint32，必须等于 request 绑定的实际输入长度 |
| `query_digest` | 实际 SMT bytes 的 raw digest |
| `policy_bundle` | 独立版本化策略清单摘要，清单包含准确 W/S cBPF bytes、固定 FD map 与外层 setup policy 摘要 |
| `image` | 受信任 Mac 已登记的最终 OCI image 身份 |
| `cli_acceptance` | 通过审阅的精确 CLI 本地使用接受记录摘要；形状检查不认证该记录 |
| `configuration` | 规范化固定容器配置/角色/资源模板摘要，排除描述本身、attempt/nonce及本摘要字段，避免循环；动态 request 单独绑定 |

Mac 在生成描述前 strict 重建 SolverRequest，查验精确 E0 接受与 E4 资格并绑定固定工具 / runtime；S 核对描述、构建内固定 CLI digest / argv profile / policy 和实际本地资源后才 READY。S 生成 nonce，Mac ARM 必须回显。**S 回显的 image / request / acceptance digest 是受信任 Mac 声明，不是 S 独立认证了 daemon 镜像或许可证。**传输匹配不改变这一事实。

构建 manifest 绑定源码、生成策略、CLI、工具链、链接输入、固定路径 / 参数和配置模板；最终 image digest 由未来构建后独立登记。不可把最终 image digest 预嵌到同一 image 再要求自包含摘要相等。启动描述注入已接受最终 ID，Mac 对 runtime readback 负责；S 校验其可观察的文件与资源。缺任一来源时停在创建之前。

### Mac 与 S 的状态分离

- Mac 保存 M0 / DM、资格中的 δ、READY 接收 Mr 与因果公式，计算一次 ARM；它必须在 DM 前确认实际退出、精确 ID 删除及后置状态。
- S 只保存本地 entry / prep deadline / Lr / DL，校验一次 ARM、绑定 / nonce、`nowL < DL <= prep_deadline`、query 长度 / digest；不能伪造 Mr 或在收到 ARM 时重算期限。
- 真实成功只由私有认证捕获入口构造，至少绑定 request、E0 接受、bootstrap / image / policy、E4 资格、两端时间、双流完整性、真实 waitid、S final、runtime 退出与删除事实。E1–E3 simulation 类型没有构造权限。
- 观察缺失、清理未确认或时间线矛盾时保存失败事实，禁止正常 P4 响应和下一 attempt；仍可把真实 bytes 用于诊断，但不能赋予成功资格。

## 具体设置与收紧顺序

下列顺序为待实现的唯一候选，不是可直接执行的命令列表。每个本地循环前后核对原期限，每次读写有固定上界，系统调用耗时仍依赖实际内核资格；非阻塞 flag 不构成物理实时保证。

| 步骤 | 动作 / 取得事实 | 出口条件 |
| --- | --- | --- |
| S0 | 精确 CRT / std 启动；自有代码先建 BOOTTIME timer，再检查进程为 PID 1、单线程、UID/GID、capability、no-new-privileges、namespace / boot、继承 FD | 错对象 / 身份 / 资源不修复；准备失败退出 |
| S1 | 用固定路径取得只读 CLI、cgroup 与内核身份；核对 stat / filesystem / mount 来源；将 S0 timer 固定到运行槽，创建三 pipe、私有 socketpair、sealed ELF；准备固定参数与所有缓冲 | CLI 实际 bytes / ELF / seal、完整 FD inventory、配置基线必须吻合 |
| S2 | 固定配置后发一次 READY；接一次 ARM；非阻塞收齐 query，重算长度 / digest；query 保留在 S，未给 B 读取 | 未完成 / 超时不创建 B；不把 query 预写入可能填满的无人读取 pipe |
| S3 | 移除继承的 std handler / altstack，冻结 disposition 与 mask；使用 S1 已预分配的 B 只读参数与 FD 重映射表；重新检查 DL；单次 clone3 返回唯一 child 与 pidfd；父分支立即接管 child / pidfd，关闭自身 child pipe 端与 CLI / ELF 句柄 | 不重试创建；无 CLONE_VM/FILES/THREAD；父子各持明确副本，关闭失败仍保留回收目标 |
| B1 | raw 固定重映射至 0..4，关闭所有其他父句柄；确认 0/1/2 为正确 pipe、3 sealed ELF CLOEXEC、4 交付 socket CLOEXEC | 不分配、不记录动态日志、不读 query、不调用第三方代码 |
| B2 | 核对 no-new-privileges；安装 W/B 最终 filter，listener 必须是 FD 5；一次 sendmsg 交付，成功后关闭 5/4；固定 execveat | 失败 raw exit；不重发 ancillary、不重新安装 filter 或改用路径执行 |
| S4 | 设置循环先接收并核对 listener / 绑定 / 截断 / 恰一个 FD；固定其角色；关闭 socket 与其余设置 FD，核对父侧已无 child pipe 端和 ELF FD；核对运行角色 | 此时不能已装 S 最终 filter：它禁止 recvmsg / dup / fcntl / seccomp |
| S5 | 核对实际 FD 角色与预先冻结的固定映射相同，核对离线 S filter bytes / 摘要，完成最终收紧；轮询 listener / pidfd / timer / control；验证唯一首次调用 | 先不可逆消费 CONTINUE，再发一次；任何失败不重试 |
| S6 | 循环写 query、读两流、处理 deadline / 控制丢失 / pidfd / cgroup；query 全部写入后关闭 W stdin | 控制连接继续保留；超限 N+1 原样判失败，不截断为完整 |
| S7 | waitid 精确回收、双 EOF、最终 S-only cgroup；发送终态并 raw exit | 最终帧不能抢在退出和流完整之前；背压不延长 DL |
| M7 | Mac 验证绑定终态、同一 runtime 的 init 退出 / 无重启与整树依据，按精确 ID 删除并读回 | 全部在原 DM 内完成才接 P4；不得把 remove / 查无容器单独当回收证据 |

### FD 与信号的具体约束

首实现候选固定 S 映射为控制 0/1/2、child stdin/stdout/stderr 10/11/12、timer 13、pidfd 14、listener 15、12 个 cgroup 槽 20..31，与已离线测试的映射一致。S/W 实际安装的 bytes 均可在构建输入中冻结，其摘要共同进入 policy bundle；不能拿生成器摘要代替过滤器 bytes。READY 前只取得准备阶段的角色，14/15 是固定预留目标；clone / recvmsg 的实际返回 FD 在 setup 中显式移至目标并核验，不宣称 READY 时已经拥有 pidfd/listener。目标冲突、无可用临时槽或角色无法核对就失败，不改变映射重算一个未经绑定的策略。全部运行角色就绪后才安装 S filter / CONTINUE；今后如需动态映射，另行设计实例 bytes 绑定，不在本版本隐式支持。

`pipe2(O_NONBLOCK)` 会设置两端的状态，不能让 W 被动继承不期望的 EAGAIN 行为。候选为 pipe 先 CLOEXEC，设置阶段只把 S 使用的三个 pipe 端设为 O_NONBLOCK；B 的 0/1/2 保持阻塞 pipe，且 exec 前清 CLOEXEC。两端是不同 open file description，需实际验证；S 的控制输入、封套输出、紧急诊断也须非阻塞。每个 FD 只有一个 owner，raw 子分支避免 Rust Drop 自动重复关闭。

交付socket固定为私有AF_UNIX SOCK_SEQPACKET；B只发一个小型固定记录，S使用MSG_DONTWAIT和MSG_CMSG_CLOEXEC，核对整条payload、MSG_TRUNC/MSG_CTRUNC及恰一SCM_RIGHTS。所有实际收到的FD先建立所有权再校验，不以拒绝消息为由泄漏多余FD；任何不完整发送不重试。

B 重映射先将所有源安全移到不与 0..4 冲突的自有临时槽，再依次 dup3，处理 src==dst 的明确情况；最后关闭高位槽。禁止提前关掉后续仍需用的源。不得把输入的任意 FD 列表当映射指令。NEW_LISTENER=5 依赖 0..4 恰被占用且其他 FD 已关闭；返回其他值直接失败。

信号沿已接受 B 边界：S 在 clone 前通过受审阅的原生 sigaction / sigaltstack 操作移除 std 的 SIGSEGV/SIGBUS handler 与 altstack，将继承的 SIGPIPE 忽略等状态恢复为固定默认 disposition，再核对并冻结精确 mask、阻塞可阻塞信号；B 不保留可执行的 std 信号 handler，SIGCHLD 不设 SIG_IGN / SA_NOCLDWAIT，以便显式 waitid。B 将屏蔽集带入 W，Linux exec 保留屏蔽集；这成为精确 CLI 兼容性停止项，不在本批自动清空 mask。SIGKILL 无法被屏蔽。同步故障信号被屏蔽时的行为也是必须否决不安全实现的边界，不能靠 mask 假定 Rust 错误可恢复。未来如需修改 W 的初始 mask，须单独审阅，不以“恢复默认”掩盖行为变化。[signal(7)](https://man7.org/linux/man-pages/man7/signal.7.html)

### syscall 与内存安全审查表

| 类别 | 必须建立的不变量 | 错误与重试 |
| --- | --- | --- |
| raw syscall | AArch64 Linux 参数 / 返回寄存器、完整宽度、负 errno 范围、asm 内存副作用；不标错误的 nomem / pure；仅特定 wrapper 暴露安全接口 | errno 保留原始值和操作阶段，不泛化 retry-everything |
| clone3 | 单线程无 allocator 锁持有；参数 size / flags 固定；独立地址空间、继承栈；child 分支不返回普通执行路径，不分配 / unwind | EINTR 或不确定返回不再创建；失败清理既有自有资源 |
| buffers / structs | 先补齐精确 AArch64 siginfo / stat / statfs 的来源、布局和字段；对齐和尺寸按目标 ABI，不把 pure值强转 repr(C)；内核写入缓冲不能别名；输出清零再调用，检查返回尺寸 | 未初始化尾部不读取、不落日志；尺寸不符失败 |
| memfd / hash | 从同一已打开文件完整读入、hash并写入，sealed对象与核对bytes一致；短读、变长、seal读取必须处理 | 不重开路径补读；不去掉MFD_EXEC或seal；不从未接受payload得出接受 |
| SCM_RIGHTS | 固定单条消息、数据绑定、CMSG边界/对齐、恰一FD、MSG_CTRUNC及多余消息拒绝；取得的所有FD有回收归属 | sendmsg不确定成功不重发；recv错误走失败；不得遗留附带FD |
| read / write | 返回 n≤请求长度；partial推进offset；0、EAGAIN、EINTR、EOF分开；每轮有预算、回到deadline检查 | EINTR仅在无成功字节时按原deadline重入；不无界排空，不busy-loop |
| close | 消费一次ownership后调用，保存错误；Linux close错误可能已释放编号 | 不对同一数字盲目重试，避免关闭复用的新FD；以失败/退出处理 |
| pidfd / waitid | 固定唯一pidfd；WNOHANG，清零siginfo；si_pid=0表示暂无退出，真实code/status单独解释 | pidfd readable不等于已reap；不以exit137猜OOM |
| notification | 恰一reader；请求buffer清零；先readiness再一次RECV；ID / child / arch / syscall / pointers / DL全部匹配 | CONTINUE状态先消费且SEND最多一次；失败无正常响应 |

`close` 的一次消费规则依据 [Linux close(2)](https://man7.org/linux/man-pages/man2/close.2.html)；它不是“忽略关闭错误”。raw clone 及 child 栈约束仍须结合精确编译输出检查，[clone(2)](https://man7.org/linux/man-pages/man2/clone.2.html)不能替代 Rust ABI 审阅。

### listener 读取与 cgroup 退出过渡

随机挑战固定使用受审阅的 `getrandom(..., GRND_NONBLOCK)`、恰 32 bytes 和有界短读记账；EAGAIN、不可用或期限内不完整直接失败，不改用时间戳、零值或会等熵池的模式。此前准备模型中的随机值不能证明真实随机来源。[getrandom(2)](https://man7.org/linux/man-pages/man2/getrandom.2.html)

listener 的 RECV ioctl 不因设置 O_NONBLOCK 自动变为非阻塞。固定 Linux v6.12 [seccomp.c](https://raw.githubusercontent.com/torvalds/linux/v6.12/kernel/seccomp.c) 的请求计数 / users 逻辑支持单 reader 一次 POLLIN 后一次 RECV 的有限推论；这仍须绑定实际 kernel 补丁和 E4 负例。禁止无条件循环 RECV，优先处理 timer / pidfd / HUP，ENOENT / EINTR 关闭正常路径。一次 CONTINUE 后，后续通知可直接触发失败终止，不再读第二个请求或授权。内核源码核对不等于实际环境的耗时保证。

cgroup 文件与 waitid 不是原子快照，`cgroup.procs` 还不列 zombie。[cgroup v2 说明](https://docs.kernel.org/admin-guide/cgroup-v2.html)因此不能被解释为“每次读取都瞬时等于两个任务”。候选适配器在原期限内保存逐文件读取区间及前后 pidfd / waitid 事实：正常稳定样本仍须精确符合现行 parser；若只有唯一 child 正在退出的过渡迹象，允许最多一次额外读取，保留第一次原始事实，直到真实 reap 后取得 S-only 最终样本。缺文件、额外 PID、配置漂移、计数回退或资源故障立即失败，不能借重读覆盖它们。无法稳定核对即失败，不把过渡记录改成稳定观察。

这是 D2 已接受、尚未完成真实运行验证的观察适配规则；本批不修改既有 synthetic parser / 状态机、不使旧反例从拒绝变成成功。实现必须补进程在每个读取边界退出的负例，证明额外读取不续期、不丢事实、不掩盖资源事件。F1 不据此放宽旧模拟判定；实际退出观察实现与资格仍留在后续批次。

## 构建与容器配置的可审阅产物

未来构建输入必须形成闭合清单：自有源码与生成入口 / inputs、Rust编译器及target std实际包、musl/CRT/compiler-builtins/链接器、固定UAPI、全部链接对象与许可、CLI精确bytes及E0接受记录、构建命令 / flags / 环境 / 离线依赖、ELF静态检查结果。`--target`或文件名不是静态链接证明；必须检查 PT_INTERP / DT_NEEDED、arch、entry、segment与可执行栈、符号和link map。可复现构建是可验证目标，不在还未构建时宣称成立。

启动描述只进入固定的 create COMMAND/ARG 数组；[Docker create](https://docs.docker.com/reference/cli/docker/container/create/) 本身也会创建外部状态，当前没有调用。候选镜像是只读 scratch 内容：唯一 bootstrap、精确已接受CLI及必要自有manifest/归属材料；无shell、包管理器、额外daemon或健康检查。固定非root UID/GID、空capability/no-new-privileges、私有PID/cgroup namespace、network none、readonly rootfs、无host bind/volume/device/socket、无restart/init helper、既有memory/swap/pids值。runtime提供的/proc与只读cgroup视图需核对来源和权限；非root读不了不修改权限。

外层setup policy与S/W最终policy分别绑定摘要，组合必须不屏蔽首个USER_NOTIF或意外提供fallback。固定路径读取属于可信代码，cBPF无法解析pathname。真实字段化容器配置、精确Docker命令数组、工具/context/daemon/runtime/image ID、预计时长/占用、失败保留目录及精确ID清理方案，须在将来申请对应动作之前全部填实；本批不生成含占位摘要的“可运行”脚本。

## 分批实施与验收

| 顺位 | 可交付物 | 完成证据 / 下一门禁 |
| --- | --- | --- |
| F1：决定与纯共享边界（已完成纯组件验收） | 最小 core、闭合启动描述、Mac/S 分离接口、增量摘要及离线资源 / 策略输入；保留旧字节与重导出 | [本机验收](../records/2026-10-17-solver-f1-validation.md)覆盖旧 golden、原容量流程、损坏描述、截止与来源混用负例；无 OS 能力 |
| F2：原生源与静态构建审阅 | [原生边界](solver-bootstrap-native-boundary.md)与[监督实现](solver-bootstrap-native-supervisor.md)已形成私有源码与本机脚本后端检查；目标工具 / 实例来源及构建输入尚未接受 | [验收记录](../records/2026-10-17-solver-f2-validation.md)分别报告实际有限检查与未运行项；目标编译 / 汇编 / 链接审阅仍待工具接受与授权，编译不能计运行资格 |
| F3：E0与制品配置 | 本批补证形成可重跑材料；原CLI缺口不闭合则保持not-accepted；按已接受D3先交受控构建候选方案 | 新payload另登记并验收，不覆盖旧identity；不自动下载/安装工具或构建CLI |
| F4：资格方案与授权材料 | 固定探针源码/预期/制品/配置/范围/清理；时间/失联/通知/退出竞态/资源/流矩阵 | 镜像构建和E4探针分别授权，随后才可能E5校准和E6单次wrong-add |

F1/F2 的具体实现由 gpt-6.1-sol / high 承担，主代理主持设计与最终验收。项目所有者已要求先提交 F1 实现、验收与 D3 方案，再推进 F2 原生实现和 C0 精确输入选择；提交 `1a7ff38` 已完成。F2 保持私有源代码与脚本后端验收范围，不生成可执行入口或带占位资格的构建脚本。E0接受与运行资格必须在任何solver路径打开之前闭合，未取得资格时即使源可编译也只能保持不可运行状态。

D3 已形成[同版本 cvc5 可追溯构建候选方案](solver-cvc5-build-candidate-plan.md)，保持原 CLI 未接受状态，列明精确输入缺项、构建选项比较、隔离查找 / 缓存、对象与 link map 留证和 C0–C5 顺序。它不授权下载、安装、编译或执行。
