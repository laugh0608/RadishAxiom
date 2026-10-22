# F2 原生 syscall 与 B 尾段边界

日期：2026-10-17。用途：审查 `solver-bootstrap-linux` 的原生调用、布局、所有权与 clone 子分支；读者为 F2 实施者及 unsafe 审阅者。不包含运行资格、已接受 CLI、完整外层 setup filter、Linux 制品、镜像或真实内核观察。上层设置 / 监督职责另见 [F2 实化](solver-bootstrap-ffi-implementation-plan.md)及原生实现文件；本页不替代 ADR 0030 或既有 W/S 策略。

## 实现与平台边界

私有库没有 `main`、公开执行 API 或默认 accepted 配置。`NativeKernel` 只在 `target_os=linux`、`target_arch=aarch64`、`target_endian=little`、`target_pointer_width=64` 四条件同时成立时存在。其他平台没有原生 backend 或 libc / fork fallback。typed wrappers、设置、监督及 child 尾段仍在 Darwin 编译；测试显式选择 scripted `Kernel`。只有 `svc 0` 汇编块受目标 cfg 限制，不能用本机类型检查声称已编译 Linux 汇编、链接 musl 或执行内核。

crate 使用 `deny(unsafe_op_in_unsafe_fn)`。局部 unsafe 注释逐处列出缓冲区和生命周期。crate 级 `allow(dead_code)` 只因本批是没有可运行入口的源码交付，私有原生组件尚未从可执行入口可达；其他 lint 不因此放宽。`Kernel` / `Call` 和任意寄存器入口均不对外公开；内部 `call` 仍为 unsafe，safe API 不接受原始指针。指针只从本次调用拥有的 slice、固定布局对象、`CStr` 或 parent 预冻结对象构造。

原生汇编通过 x8 传 syscall 编号、x0..x5 传完整 `u64` 参数，x0 为输入输出。`svc` 不声明 `nomem`、`pure` 或 `readonly`；`nostack` 只说明汇编自身不改变用户栈。返回寄存器落在 `-4095..=-1` 时按完整 64 位二补码解出 errno，保留操作名与 errno；不会把 libc 的 `-1 + TLS errno` 规则混进来。短 IO、EINTR、EAGAIN、EPIPE、ESRCH 等由上层明确处理，不在 wrapper 内隐含重试。单次 clone、SCM_RIGHTS 发送和通知 CONTINUE 尤其不能自动重试。

raw `ppoll` 与 libc wrapper 的区别已经落实：剩余 timespec 为 `&mut` 独占可写对象，kernel 可以写回剩余时间；见 [poll(2) C library/kernel differences](https://man7.org/linux/man-pages/man2/poll.2.html)。scripted 测试实际写入这个受借用缓冲区，但不能代替真实 ppoll 观察。

## ABI 来源与布局

既有 syscall / seccomp 数值及 W/S 策略复用 [core ABI](../../crates/solver-supervision-core/src/abi.rs)和 [core policy](../../crates/solver-supervision-core/src/policy.rs)，不复制 golden 或另建规则。新 native `repr(C)` 布局与 core 的纯值编解码分离；seccomp notification / response 继续使用原来的字节 codec，native 不把纯 Rust 值转为 FFI。

以下来源固定 Linux **v6.12**。2026-10-17 经公开上游网页只读核对；没有保存头文件原字节、下载依赖、接受编译器或生成全套绑定。只记录 ABI 数值 / 字段事实，不复制内核实现。UAPI 来源声明 GPL-2.0 WITH Linux-syscall-note；`include/linux/socket.h` 为 GPL-2.0，仅核对用户 msghdr / ancillary 布局与数值。原有来源与例外范围见 [具体 ABI](solver-linux-abi-v0.1.md)。

| 来源 | native 使用事实 |
| --- | --- |
| [asm-generic/stat.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/stat.h) | 原生 LP64 `stat`，不是 libc 私有 stat 或 32 位 stat64 |
| [asm-generic/statfs.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/statfs.h) | 64 位 `__statfs_word` 与 fsid 两个 i32 |
| [asm-generic/siginfo.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/siginfo.h) | 128 字节 siginfo，SIGCHLD union 和 CLD_* |
| [asm-generic/signal.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/signal.h)、[arm64 signal.h](https://github.com/torvalds/linux/blob/v6.12/arch/arm64/include/uapi/asm/signal.h) | kernel sigset 8 字节；arm64 定义 SA_RESTORER，所以 kernel sigaction 包含 restorer 字段；stack_t 布局 |
| [sched.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/sched.h) | clone_args VER2 与 CLONE_PIDFD |
| [time_types.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/time_types.h)、[poll.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/poll.h) | 原生 64 位 timespec / itimerspec 和 pollfd |
| [socket.h](https://github.com/torvalds/linux/blob/v6.12/include/linux/socket.h)、[uio.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/uio.h) | user_msghdr（不是 kernel msghdr）、iovec 与 cmsghdr |
| [syscall.tbl](https://github.com/torvalds/linux/blob/v6.12/scripts/syscall.tbl)、[fcntl.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/fcntl.h) | getdents64 / getppid 编号与 F_DUPFD_CLOEXEC；外层 setup 显式列项 |
| [filter.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/filter.h) | sock_filter / sock_fprog；逐字段复制现有生成器输出 |

下表全部为 AArch64 LP64 LE，单位字节。名称对应 native Rust 字段；未使用字段也明确保留，避免省略导致偏移漂移。

| 对象 | size / align | 全部字段 offset |
| --- | --- | --- |
| `Stat` | 128 / 8 | dev0、ino8、mode16、nlink20、uid24、gid28、rdev32、pad1:40、size48、blksize56、pad2:60、blocks64、atime72、atime_nsec80、mtime88、mtime_nsec96、ctime104、ctime_nsec112、unused[2]120 |
| `StatFs` | 120 / 8 | kind0、bsize8、blocks16、bfree24、bavail32、files40、ffree48、fsid[2]56、namelen64、frsize72、flags80、spare[4]88 |
| `SigInfo` | 128 / 8 | 原始 bytes0；signo:i32@0、errno:i32@4、code:i32@8、union 对齐 padding12..15；SIGCHLD pid:i32@16、uid:u32@20、status:i32@24、padding28..31、utime:i64@32、stime:i64@40；其余原样保留 |
| `CloneArgs` | 88 / 8 | flags0、pidfd8、child_tid16、parent_tid24、exit_signal32、stack40、stack_size48、tls56、set_tid64、set_tid_size72、cgroup80（均 u64） |
| `SigAction` | 32 / 8 | handler0、flags8、restorer16、mask24（均 u64） |
| `AltStack` | 24 / 8 | pointer:u64@0、flags:i32@8、padding:u32@12、size:u64@16 |
| `Timespec` / `Itimer` | 16 / 8；32 / 8 | sec:i64@0、nsec:i64@8；interval0、value16 |
| `PollFd` | 8 / 4 | fd:i32@0、events:i16@4、revents:i16@6 |
| `Iovec` | 16 / 8 | base:u64@0、len:u64@8 |
| `MsgHdr` | 56 / 8 | name:u64@0、namelen:i32@8、pad:u32@12、iov:u64@16、iovlen:u64@24、control:u64@32、controllen:u64@40、flags:u32@48、tail:u32@52 |
| `Ancillary` | 24 / 8 | len:u64@0（20）、level:i32@8（SOL_SOCKET1）、type:i32@12（SCM_RIGHTS1）、fd:i32@16、padding20..23 |
| `SockFilter` / `SockFprog` | 8 / 4；16 / 8 | code:u16@0、jt:u8@2、jf:u8@3、k:u32@4；len:u16@0、pad[6]2、filter:u64@8 |

测试核对 size / align 与关键 offset；其余字段由同一 `repr(C)` 连续固定宽度顺序决定。未来精确目标构建仍需在目标平台核对全部布局与工具链输入，Darwin 的布局测试不接受目标 libc/CRT，也不代替原生探针。

## FD、信号与 B 尾段

`OwnedFd` 不实现 Copy / Clone / Drop；每个关闭或转移显式消费 owner。关闭即使返回 EINTR 也不再次关闭同号 FD，避免 Linux 已释放后误关复用句柄。父侧 fixed-role `duplicate` 拒绝 src==dst，拒绝替换仍打开的目标；调用者在相同角色时直接保持原 owner。继承 0/1/2 只允许通过同一个 `Linux` 实例接管一次；设置代码在开始阶段核对完整 inventory，不能把 safe 形状验证当 FD 来源认证。

可信设置使用 `F_DUPFD_CLOEXEC=1030` 把 B 的五个固定来源先复制到不与 0..4 冲突的 >=6 槽，再在 B 中依次 dup3 到 0/1/2/3/4。这与固定 FD 表一同受构建绑定；不是不可信输入给出的任意 remap。`getdents64=61` 仅用于固定 `/proc/self/fd` 目录的有界只读 inventory。`getppid=173` 另用于核对 namespace PID 1 的 parent 为 0；它同样只在 setup 使用。这三项是本轮明确列出的 **setup 能力要求**，都不加入既有 W/S final filter；完整 outer setup policy 仍未形成或接受。读取目录采用独占字节缓冲，解析字段不把未对齐目录项 cast 为 Rust 引用。

parent 创建 SOCK_SEQPACKET 的唯一入口固定 AF_UNIX1、type=SOCK_SEQPACKET5|CLOEXEC、protocol0；这一可信构造和唯一 owner 传递是 FD4 socket 类型的依据。fstat 的 socket mode 本身不能区分 SEQPACKET 与其他 socket 类型。parent 冻结前三个源 pipe 的 dev / ino，B 重映射后逐一核对相同身份、FIFO mode、访问方向、阻塞属性与无 CLOEXEC；ELF 与 socket 使用 CLOEXEC。close_range(5,UINT_MAX,0) 只在所有五个目标建立后执行，关掉其余父 FD、scratch 与第二执行 FD，随后 lowest-free listener 才必须等于 5。

parent 在 clone 前阻塞所有可阻塞的 64 个 kernel 信号（精确 mask 排除 SIGKILL9、SIGSTOP19），逐一重置并读回全部 catchable disposition 为 SIG_DFL，包含 SIGPIPE、SIGCHLD、SIGSEGV、SIGBUS；禁用并读回 altstack，最后读回精确 mask。没有 SA_NOCLDWAIT / SIG_IGN。该 mask 跨 exec 保留，solver 对它和同步故障信号的兼容性仍是未验证停止项。循环核对原 DL 和前次 BOOTTIME，拒绝时钟倒退，末尾读回及 clone 前再次读取 BOOTTIME；不会冻结新期限或重试 clone。

clone3 仅一次，args size88、flags仅 CLONE_PIDFD0x1000、exit_signal17、stack0，其他字段全0；不共享 VM / FILES / THREAD / handler，不创建 namespace，无 fork / clone 降级。成功父分支先保留 pid 与唯一 pidfd，再显式关闭本侧 scratch；失败、EINTR 或后续设置失败不得重建另一子进程。

child 直接进入独立 `child_tail -> !`，使用 parent 的 COW 栈和预冻结 Box / 静态缓冲；不执行 allocation / lock / std IO / Drop / panic / unwind / 任意用户 callback。局部结构与固定 register 参数只调用 raw backend。W/B 最终策略逐字段来自既有 worker_policy；不改 golden。listener 必须为 FD5，只 sendmsg 一次固定八字节 `AXB-LST1` 加一枚 FD5，成功后关闭 5/4，然后固定 execveat(3,empty-path,argv,empty-env,AT_EMPTY_PATH)。失败只 raw exit_group，不返回 Rust 清理或改用 pathname。

S 使用单次非阻塞 recvmsg，MSG_DONTWAIT|MSG_CMSG_CLOEXEC；先建立每个实际收到 FD 的 owner，再检查固定 payload、短消息、TRUNC / CTRUNC、控制头和恰一个 FD。拒绝时逐一关闭全部收到的 owner，保留关闭错误；不能用拒绝消息当泄漏 FD 的理由。接收缓冲固定 1024 字节，内核不能放入缓冲的 rights 依 Linux SCM_RIGHTS 规则由内核关闭；依赖该内核行为属于未验证实际环境边界。

## 独立 command 输入

新增 host `bootstrap_command` 与显式 example `solver_bootstrap_command`，从原 `axiom-ir::solver::ARGUMENT_TOKENS` 同一常量导出，旧 SolverRequest 方法与 token 字节不变。唯一 API 可见性增量是该常量成为私有 crate 的 `pub const`；不会让 Start / ARM / Mac 临时输入改变 argv。

`command.bin` 固定 `AXBCMD01`（8 byte）+ BE u32 argc12 + 十二份 BE u32 长度及 ASCII token，无 NUL、控制字符、转义、尾随，token 长1..128且以 `--` 开头，整体<=4096。native configuration 必须先与未来构建绑定的 raw digest 相等，才把 tokens 交给 `FrozenChildArguments`；仅解析通过不认证“已接受参数”。argv0 固定 `cvc5`，尾随 NULL，envp 只有 NULL，pathname 是非 NULL 的空 C 字符串。

导出写到新 `.tmp/<name>` 目录，产生 `command.bin` 与 `manifest.json`；不覆盖旧目录。manifest 包含生成入口、实际编译捕获的源码 / Cargo 输入摘要、command 长度和摘要，固定 `scope=offline-command-inputs-only`、`native_build=not-accepted`。它与原 F1 四文件格式 / source 列表分开；源码捕获使源变化后的重导出摘要自然变化，不是接受记录或完整 policy bundle。[独立复核器](../../scripts/check-solver-bootstrap-command.py)复用既有有界文件 / 来源清单检查，自行解码 AXBCMD01 并对照审阅固定的十二项参数，不从 Rust 或导出推导期望值；[负例](../../scripts/test-solver-bootstrap-command.py)覆盖全部截断、版本 / 长度 / 尾随、参数漂移、重算摘要后篡改及来源 / 范围声明。

## 已验证与未闭合

本批 scripted 测试针对 raw errno 全范围、高位不截断、短 IO / EINTR、ppoll 写回、关闭不重试、occupied dup、异常 fstat / waitid、损坏 / 多 FD listener 清理、CONTINUE 编码、单次 clone3 / COW flags、固定 argv 指针、remap 顺序与错误 listener 立即终止。child 尾段的测试 backend 用 test-only panic 逃离 raw exit 的 `-> !`；生产 backend 没有此路径。所有这些结论均是显式脚本的有限检查，不能宣称内核实际返回过这些数据。

仍未闭合：Linux AArch64 asm 的目标编译与链接、精确 Rust/std/musl/CRT/compiler-builtins/linker 接受、所有 native UAPI 的实际内核探针、outer setup filter、E0 CLI 接受、E4 宿主资格、E5 原资源与真实 solver 兼容。stdio flags、listener nonblocking 与通知 ioctl 竞态、exec前mask、128 MiB / 6 s 下的时限与回收都不能由 Darwin scripted 测试升级为 accepted。无下载 / 安装、Linux binary 或镜像构建、探针、solver、系统修改、push 或远程动作。
