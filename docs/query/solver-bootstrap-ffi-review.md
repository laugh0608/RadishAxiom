# Linux bootstrap / FFI 独立可行性审阅

日期：2026-10-17。状态：设计审阅输入；建议由新 ADR 决定，本文不修改 ADR 0029 Accepted 规则。范围：真实 Linux AArch64 bootstrap 的源码、ABI、时序、ownership 与后续验收设计。没有新增可调用 FFI、crate、制品、依赖、镜像、探针或真实 solver 执行。

审阅对象为 [独立监督设计](solver-linux-supervision-design.md)、[syscall 策略](solver-linux-syscall-policy.md)、[ABI v0.1](solver-linux-abi-v0.1.md)、[S 策略](solver-supervisor-policy-v0.1.md)及 `e3_supervisor` / `e3_cgroup` / `e3_wire` 纯组件。结论是存在可继续细化的窄实现路径，但纯模型一致性尚不能支持真实 setup 可行、精确 payload 兼容、E0 完整或 E4 / E5 通过。

## 必须在实现前闭合的顺序与 ownership

| 项目 | 缺口或具体失败 | 建议实现约束 |
| --- | --- | --- |
| B 的 FD 重映射 | 任意顺序逐项 `dup3` 可能覆盖另一个未使用源；`src==dst` 会失败；不关闭高位继承 FD 则 NEW_LISTENER 不一定返回 5 | fork 前形成显式重映射计划，源都置于不与 0..4 目标重叠的保留槽；子进程 `dup3` 后关闭原源及全部无用高位 FD，最后只剩 0..4。0/1/2 清除 CLOEXEC，3/4 设置 CLOEXEC。禁止靠“通常从 3 起分配”推导精确角色。保留槽的占用、数量及有界关闭计划进入审阅 |
| S 的设置收紧 | S 最终策略禁止 `recvmsg`、`seccomp`、`fcntl`；先安装它再收 listener 必然失败 | 先完成 listener 交付与 ancillary 检查、绑定全部 21 个运行角色、关闭设置 FD、完成非阻塞属性核验，最后安装 S 最终过滤器，再执行首次 CONTINUE。收 listener 期间也运行 deadline / pidfd / 控制输入事件循环 |
| 父端冗余句柄 | 留下 child stdout/stderr 的写端会永久阻止 EOF；留 child stdin 的读端会破坏 EPIPE；留下 memfd 使“唯一执行对象能力”不闭合 | clone 成功后 S 立即关闭全部 child 端与自身 CLI / memfd；B 关闭全部 parent 端。每个 FD 是进程局部 ownership，不把 fork 后两份整数视为一个 Rust owner。S 收到 listener 前后都不能持有给 W 的第二执行 FD |
| listener 交付 | stream socket 的短 payload、截断 ancillary、重复消息或 EOF 可导致错绑定 / FD 泄漏 | 冻结 socket 类型与消息边界；推荐私有 `SOCK_SEQPACKET` 的单个小型记录。S 使用 `MSG_DONTWAIT|MSG_CMSG_CLOEXEC`，验证 payload 全长、消息绑定、恰一 SCM_RIGHTS、无额外 cmsg、无 `MSG_TRUNC/MSG_CTRUNC`；任何失败先接管并关闭已实际取得的 FD，再失败。B 单次 sendmsg 必须完整成功；不重发 SCM_RIGHTS |
| 关闭错误 | 通用“EINTR 重试”套在 close 会关闭复用的角色号；RAII 隐式 Drop 隐藏关闭错误 | 每次显式关闭先消费 owner，Linux close 错误保留原 errno 并失败，不再对同一数值重试。收紧后不创建 FD，已关闭角色仍在 BPF 数字表中不等于可以重新使用 |

`dup3` 的相同 FD 错误、descriptor flags 与 open-file-description flags 必须区分；`O_NONBLOCK` 不会由 CLOEXEC 提供。[dup 文档](https://man7.org/linux/man-pages/man2/dup3.2.html)说明这两种 flags 的区别。[close 文档](https://man7.org/linux/man-pages/man2/close.2.html)说明 Linux 提前释放 FD，因此失败后不重试。收到的 FD 的 CLOEXEC 要由接收方指定，不能假设继承发送方 descriptor flags。[recvmsg 文档](https://man7.org/linux/man-pages/man2/recvmsg.2.html)、[UNIX ancillary 规则](https://man7.org/linux/man-pages/man7/unix.7.html)

## clone3、Rust 与信号

Accepted `clone3` 的 `stack=0/stack_size=0`、无 CLONE_VM 是父栈的写时复制分支；没有要求另造子栈。若未来改为新栈，不能让普通 Rust 调用帧在新栈上继续返回，必须另行审阅入口跳板。pidfd 输出存储只由父分支接管；clone 返回后，先建立 child / pidfd ownership，再执行任何可能失败的读回与状态判断；不能等完整 cgroup 核验成功才记录清理目标。`clone3` 失败不换 fork，不把 EINTR 放进通用重试器。[clone3 文档](https://man7.org/linux/man-pages/man2/clone3.2.html)

B 从返回零的分支进入 `-> !` 尾段，只接受 fork 前冻结的标量、指针和计划；不分配、不加锁、不格式化、不 panic、不执行用户 handler、不构造会隐式关闭整个父资源集合的 Drop 路径，不调用 std 的退出清理。exec 失败只作固定、受策略允许的失败退出，不能返回父状态机。参数数组及其 NUL 终止内容在 fork 前固定；Vec 的缓冲在 clone 之后不在 B 内重分配，S 对自身写时复制副本的更新不改变 B 的参数。Rust 官方 `pre_exec` 的安全说明可作为 fork 子分支限制的审阅输入，但它不证明自写 raw clone 适配正确。[CommandExt](https://doc.rust-lang.org/std/os/unix/process/trait.CommandExt.html)

信号是显式决策项。阻塞 mask 会跨 exec 保留；阻塞 SIGBUS / SIGFPE / SIGILL / SIGSEGV 后发生同步故障也存在未定义行为边界。[sigprocmask 文档](https://man7.org/linux/man-pages/man2/rt_sigprocmask.2.html) 当前 Accepted B 的“阻塞信号、无用户 handler”不能静默解释为 W 启动时 mask 已清空。可选路径为：

- 保留 B/W 继承的精确 mask，并把精确 solver 对该状态的兼容性列入未通过项；这最少改变旧规则。
- 新 ADR 明确接受 B 在执行前恢复冻结的 W mask，先消除继承的 Rust handlers / altstack 和未接受的忽略状态，再恢复 mask；无并发 handler 修改首次参数的前提必须重新闭合。SIGCHLD 必须能 waitid，不接受 `SIG_IGN` / `SA_NOCLDWAIT` 导致自动回收。

只写“单线程 Rust”不足以证明“无 handler”。精确 Rust `1.97.1` 的 Unix init 会检查 stdio，在缺失流时尝试 `/dev/null` 修补，默认忽略 SIGPIPE，并初始化 stack-overflow 机制；源码中的 Linux 分支涉及 SIGSEGV / SIGBUS、altstack 与内存映射。这些是 bootstrap startup TCB，必须进入外层设置策略与精确目标源码审阅，不能把它们漏在 main 之前。[1.97.1 Unix init](https://raw.githubusercontent.com/rust-lang/rust/1.97.1/library/std/src/sys/pal/unix/mod.rs)、[1.97.1 stack overflow](https://raw.githubusercontent.com/rust-lang/rust/1.97.1/library/std/src/sys/pal/unix/stack_overflow.rs) 本次网页读取不是 Rust 安装包、std / musl / linker 的原字节或摘要接受。

## listener 阻塞与一次性执行

不能把 `SECCOMP_IOCTL_NOTIF_RECV` 当作普通非阻塞 read。每次 RECV 前清零请求区；仅有一个 reader；在本轮 deadline、控制失联、pidfd 退出、listener HUP/ERR 均未要求停止后，首次有效 POLLIN 才调用一次 RECV，不作 drain。RECV / ID_VALID 失败即关闭正常成功路径，不对过期通知循环领取；一次性状态消费先于 SEND，SEND 包括 EINTR 在内的任何失败都不重试。首次 CONTINUE 后新 POLLIN 即违规并 kill，不必第二次 RECV。[通知文档](https://man7.org/linux/man-pages/man2/seccomp_unotify.2.html)

对固定 Linux v6.12 源码的有限推论：`seccomp_notify_ioctl` 调用 RECV 时不传 `file->f_flags`；`recv_wait_event` 依赖请求计数或 filter users，普通 O_NONBLOCK 不能令该 ioctl 非阻塞。单 reader 尚未消费的首次 POLLIN 对应一个请求计数；目标在领取前死亡时可得到 ENOENT，源码也在 users 归零时结束等待。由此支持“一次就绪 → 一次首次 RECV”设计，**没有证明实际 runtime kernel 一致或系统调用物理耗时上界**。核对实际内核源码 / 补丁与 E4 负向资格仍必需；不增加通知线程或依赖 O_NONBLOCK 修补。[v6.12 seccomp.c](https://raw.githubusercontent.com/torvalds/linux/v6.12/kernel/seccomp.c) 仅读取实现判断控制流，不复制 GPL 内核实现到项目。

## cgroup、载荷和有界收尾

1. **稳定快照与退出过渡分开。** `cgroup.procs` 不列 zombie，多个 cgroup 文件、pidfd 与 waitid 没有统一原子快照。现模拟在 `child_reaped=false` 时要求成员 `[1,child]`，自然退出可使这项要求与真实观察竞态。保守首实现可把竞争直接判失败，保留 Accepted 规则；若要接纳正常竞争，必须新设计明确记录全部原读回、前后子状态与区间，在原 DL 内至多两次有界读回后，只把稳定阶段送入既有判定。额外 PID、未知成员、资源事件与计数回退立即失败，不借重读丢事实或重置基线。最终 reap 后再取 S-only 读回。[cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)
2. **12 槽不能替代对象认证。** 固定清单为 memory.max / memory.swap.max / memory.events / memory.events.local / memory.current / memory.peak / memory.oom.group / pids.max / pids.current / pids.events / cgroup.procs / cgroup.events。设置阶段核对固定目录、cgroup2 文件系统、只读打开属性、namespace 与本进程归属；对现非 root UID 不可读、缺字段、cgroup 不合格直接停止，不创建权限修复、宿主 broker 或挂载。配置、镜像和 cgroup namespace 根本身均不是“独立叶 cgroup 已实测”的证明。
3. **同一字节对象与内存预算。** CLI 以有界块读取、复制至 memfd 并累计 digest；短写按实际字节前进，EOF / N+1 / 长度不符拒绝；全部写完后密封并读回 seals，成功前不交给 B。拒绝 script / PT_INTERP；只读镜像、已验收 manifest 与 memfd 密封分别承担来源、内容绑定和禁止修改责任。MFD_EXEC 被内核策略拒绝即停止。[memfd 执行策略](https://docs.kernel.org/userspace-api/mfd_noexec.html) 原 ELF 页面、memfd 与 S/B/W 同计 128 MiB，不能靠流式复制宣称必能容纳。
4. **S 非阻塞，W stdio 属性单独冻结。** 若所有 `pipe2` 一律用 NONBLOCK，W 的 0/1/2 也成为非阻塞，CLI 可收到 EAGAIN。应固定 W 三端为阻塞、S 三端为非阻塞；pipe 两端是不同 open file descriptions，但 fork / dup 对同一端共享 flags。设置时完成 F_SETFL 并读回，收紧后不再改。不得把 1 MiB query 一次写入 pipe 后才读输出；同时处理短读写、两流、控制背压和 deadline。[pipe 创建](https://man7.org/linux/man-pages/man2/pipe.2.html)、[pipe 语义](https://man7.org/linux/man-pages/man7/pipe.7.html)
5. **有界 syscall 次数不能推成硬实时。** 部分 read/write、EINTR、EAGAIN 回到同一循环核对 DL，单轮固定预算；输出只在 `write` 成功字节后前移，write=0 不无界忙循环。文件 / cgroup 读取、缺页和内核等待仍非硬实时；O_NONBLOCK 对普通文件不提供所需保证。[open 语义](https://man7.org/linux/man-pages/man2/open.2.html)、[read](https://man7.org/linux/man-pages/man2/read.2.html)、[write](https://man7.org/linux/man-pages/man2/write.2.html) 不把 timerfd 可读当成已终止或已清理。
6. **回收不是 pidfd 可读。** waitid 使用精确 P_PIDFD / WEXITED / WNOHANG；每次预清零 siginfo，返回零且 `si_pid=0` 只是尚无可回收状态。只有成功取得匹配 child 的退出事实才消费 reap owner；ECHILD 等异常不能填默认成功。EOF 与退出可乱序，分别记账；原 DL 前收齐 EOF、reap、S-only、封套发送完成和外层 runtime / 删除确认才正常发布。[waitid 文档](https://man7.org/linux/man-pages/man2/waitid.2.html) 真实适配前仍须固定 AArch64 siginfo / stat / statfs 的上游布局、尺寸、对齐和实际读取字段；当前文档的未完成审阅项不能用 macOS 本机 libc 类型或无来源字节偏移代替。

## std / raw syscall 与复用决策建议

| 方案 | 收益 | 新增审阅与停止项 |
| --- | --- | --- |
| Rust 2024 / 1.97.1 static-musl std，加私有 raw syscall 适配 | 可复用安全 Rust 的摘要、codec 与受界结构；B 和 S 的关键 syscall 寄存器形态可精确控制；无新增第三方 Rust crate 也可形成窄边界 | 精确 `aarch64-unknown-linux-musl` 目标 std、musl、crt、linker、compiler-builtins 与许可证均需接受；std 是原生传递依赖。main 前 startup、内存分配器、signal、panic 与退出路径必须审阅。S 收紧期用 raw IO / BOOTTIME、预分配缓冲与 raw exit_group；不能返回 main 让 std 清理触发表外 syscall |
| no_std / 固定缓冲 | 缩小 runtime、分配器与 handlers 的信任面 | 新增 `_start`、入口栈 / auxv / TLS / 对齐 / 链接、panic / compiler-builtins 审阅；现 Vec / BTreeMap codec 与 parser 需真正改造。不是简单加 no_std 属性；此轮范围与风险显著增加 |

建议首实现候选用前者，但 **“没有新增 Cargo 依赖”不等于“没有需要接受的 native dependency”**。raw syscall 只放显式 AArch64/Linux adapter，所有受限制参数用完整 u64 构造，errno 识别 raw `-4095..-1`，不能混用 libc `-1 + TLS errno`；asm 的读写 / clobber / memory effects 必须与真实 syscall 相符，不能标为 pure / nomem / readonly。[Rust asm 规则](https://doc.rust-lang.org/reference/inline-assembly.html) 若用 libc syscall 符号替代 asm，同样需要精确 libc、可变参数类型、errno 与 register 扩展审阅，不能因此省略 FFI 边界。

最小复用建议是提取一个私有、安全 Rust 纯 core，承载 ABI 常量、BPF 生成 / 独立解释、wire codec、cgroup 解析及唯一资源常量；原 host 用 re-export 保持旧入口与字节。资源单一事实源迁移要有“旧值、旧字节与现拒绝行为不变”的精准核对，不让 bootstrap 通过 host 反向依赖整个 IR。

`SimulationSupervisor` 及 `Synthetic*` 来源保持 host 内。该模型把 Mac 与 S 放在同一对象，`arm()` 要求先由 `make_arm(mac_receive_ns, ...)` 设置本地 `self.arm`，真实 S 不拥有 Mac 接收时刻；不能直接把类型更名充当真实状态机。真实协议应显式拆 Mac 的 DM / δ 推导与 S 的一次性、挑战绑定、DL≤准备上限、now<DL 接收检查。若决定暂不迁移 core，则本批只冻结未来复用边界，不能复制第二份策略 / codec / 资源常量冒充最小实现。

另有启动前绑定问题：READY 自带 attempt/request/policy/image 等绑定，S 必须在输出 READY 前取得唯一、闭合、受界启动描述符，不能等 ARM 才得知本次 request，也不能从任意环境或 pathname 推测。描述符应由可信 Mac 在精确 create 时绑定，不带路径或任意 solver argv。已登记 manifest 绑定 bootstrap / CLI 原字节；最终 image digest 由外层绑定，不能要求镜像内文件包含自身最终 image digest，形成不可满足的自引用。具体编码、长度与宿主声明 / S 本地核验责任由新设计冻结。

## 本次证据级别与后续否决点

本文仅做仓库源码与公开上游文档 / 源码的静态设计审阅。网页可读取不等于已捕获下载原字节或许可证完整接受；源码推论不等于内核执行或形式证明。未来验收至少应针对 FD 任意排列 / src==dst / 中途关闭失败、短 ancillary / 截断 / listener 丢失、B 提前死、S 在交付中到期、首次 RECV 竞态、第二通知、自然退出快照竞争、W 阻塞 stdio、部分 I/O / EOF / EPIPE、waitid 尚无状态以及 S 终态未写完进行独立负向覆盖。

E0、精确内核 / 工具链 / ELF 接受、外层设置策略、unsafe 逐处审查、E4 环境资格、E5 精确 payload 兼容和原 128 MiB / 6 s 限制均继续阻断；本次没有运行它们，也没有改宽任何 Accepted 过滤器。
