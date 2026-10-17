# E3 Linux syscall 与 FD 策略

日期：2026-10-17。状态：ADR 0029 Accepted 的符号级策略，未生成 BPF、未编译、未运行。用途：封闭[监督设计](solver-linux-supervision-design.md)的能力范围与 ABI 审查项；不是已验证适配 cvc5 的白名单，不是现有宿主资格。

## 策略原则

仅 Linux AArch64 原生 ABI，过滤器先验证 `AUDIT_ARCH_AARCH64`；不接受兼容 ABI、其他架构、未知 syscall 或不匹配参数。默认 `SECCOMP_RET_KILL_PROCESS`。安装前必须设置并核对 no-new-privileges；Docker 外层策略允许指定 bootstrap 设置，内层叠加过滤器不能扩大外层权限。现有默认 Docker seccomp 不替代本表。[Linux seccomp BPF](https://docs.kernel.org/userspace-api/seccomp_filter.html)、[Docker seccomp](https://docs.docker.com/engine/security/seccomp/)

S、B、W 分别为监督器、可信装载子进程、最终 solver。只允许 S 单次创建 B，B 只进行可信装载后成为 W；没有第三个任务、线程池或 sidecar。S/B 的固定路径读取是已接受代码的责任，不能声称 seccomp 能解引用 pathname 来实现内核路径白名单。

策略文件、生成器、AArch64 UAPI 来源、编译器与 BPF bytes 都须绑定摘要。下表固定 syscall 名称、作用域与谓词；数值编号、结构布局和 ioctl 编码从待接受的精确 UAPI 输入产生并审查，不能手抄另一架构常量。任何实现差异回到本策略审阅，不在探针失败后追加允许项。

## FD 生命周期

| 阶段 | FD 与能力 |
| --- | --- |
| S setup | Docker 控制输入 / 封套输出 / 紧急诊断；自有 cgroup / proc 只读 FD；CLI 只读 FD；memfd；timerfd；三根 child pipe；私有 AF_UNIX socketpair；唯一 child pidfd |
| B 最终过滤器安装前 | 完成 dup / close，固定 `0=child stdin`、`1=child stdout`、`2=child stderr`、`3=sealed ELF + CLOEXEC`、`4=私有 listener 交付 socket + CLOEXEC`；其余父 FD 全关闭 |
| B 安装过滤器后 | NEW_LISTENER 返回唯一 FD 5（若不是 5 即失败），只在 FD 4 用一次 SCM_RIGHTS 交付 FD 5；关闭 5、4 后只调用固定 execveat(3, empty, fixed argv, empty envp, AT_EMPTY_PATH) |
| W | exec 成功后 FD 3 由 CLOEXEC 关闭，只剩 0 / 1 / 2；拒绝新 FD 创建、复制、接收和过滤器修改。不能因 fd 数字空闲就恢复 bootstrap 能力 |
| S 运行期 | 关闭 CLI 路径 FD、memfd 写入端、无用 pipe 端和传递 socket；保留有限只读观测、timerfd、pidfd、listener、两流与控制 FD。再叠加禁止 open / create / clone 的运行过滤器 |

每个 FD 必须有唯一 ownership、固定角色和状态；dup3 / close / CLOEXEC 的失败不能忽略。S 不保存可传给 W 的第二个执行 FD；W 没有接收 SCM_RIGHTS 的接口。B 留在最终过滤器里的 `sendmsg(fd=4)` 仅用于可信启动：W 的 FD 4 已关闭，且其策略没有任何创建 / 复制 / 接收 FD 的路径；这项不变量必须单独负向验证，不能只看注释。

## W 固定允许集合

这是一套严格候选策略。若精确 CLI 的已接受启动需求不在表中，结果应是本 profile 不兼容，回到设计审阅；不能把崩溃 / ENOSYS 改写成成功。

| syscall 集合 | 必须匹配的限制 | 能力解释 |
| --- | --- | --- |
| `read` / `readv` | 仅 fd 0 | 只读原 query pipe；S 控制总长度 / 摘要 / EOF |
| `write` / `writev` | 仅 fd 1 或 2 | 原 solver 两流；S 对 N+1 超限独立终止 |
| `close` | fd 0–5；只有可信 B 使用 3–5 | 只撤销能力，不能创建新 FD |
| `fstat` | fd 0 / 1 / 2 | stdio pipe 元数据；不允许 pathname stat |
| `fcntl` | fd 0 / 1 / 2，命令仅 F_GETFL | 不允许 DUPFD、修改 flags / lock 或描述符继承 |
| `ioctl` | fd 0 / 1 / 2，请求仅 TCGETS | 对已绑定 pipe 的终端查询；保留内核 ENOTTY，不伪造 terminal |
| `brk`、`munmap` | 正常 ABI 参数 | 仅地址空间管理，受 cgroup 限额 |
| `mmap` | fd=-1、offset=0、MAP_PRIVATE 和 MAP_ANONYMOUS 必需；可选 MAP_NORESERVE；其他 flags 拒绝；prot 仅 NONE / READ / WRITE 组合 | 无文件映射、共享页或新可执行页；不接受 MAP_FIXED / HUGETLB |
| `mprotect` | prot 仅 NONE / READ / WRITE 组合 | 不增加 PROT_EXEC |
| `mremap` | flags 仅 0 或 MREMAP_MAYMOVE | 不允许 FIXED / DONTUNMAP |
| `madvise` | advice 仅 MADV_DONTNEED / MADV_FREE | 不取得外部文件或进程能力 |
| `rt_sigaction`、`rt_sigprocmask`、`rt_sigreturn`、`sigaltstack` | 匹配原生 AArch64 ABI / sigset 大小 | 仅进程内信号机制；不能发送信号给 S |
| `clock_gettime`、`clock_getres` | clock ID 仅 MONOTONIC / BOOTTIME / PROCESS_CPUTIME_ID / THREAD_CPUTIME_ID | 显式受信任内核时间；不允许改钟 |
| `getrusage` | who=RUSAGE_SELF 或 RUSAGE_THREAD | 自身资源观察，不代替 S 的资源事实 |
| `getpid`、`gettid`、`sched_yield` | 无扩展操作 | 自身标识 / 调度提示 |
| `futex` | 仅 PRIVATE 的 WAIT / WAKE / WAIT_BITSET / WAKE_BITSET；拒绝共享 / PI / 未列 flags | 单线程运行库机制，不授予新线程权限 |
| `set_tid_address`、`set_robust_list` | 原生 ABI，robust head 长度精确匹配 | 仅登记当前任务的内核清理状态，不允许 clone |
| `rseq` | 原生 UAPI 的固定结构长度、AArch64 signature；flags 仅注册 0 / UNREGISTER | 单任务运行库注册；不接受任意扩展布局 |
| `prlimit64` | pid=0，new_limit=NULL；resource 仅 AS / STACK / DATA | 只查自身，不修改限制 |
| `exit`、`exit_group` | 保留真实退出码 | 不填默认退出零 |

表中 readv / writev 的深层 iovec 由内核检查，BPF 不假装读取该数组；S 负责总量与期限。mmap / mremap / ioctl / futex 等参数按完整 ABI 宽度比较，明确符号扩展，不能只比较低 32 位后允许伪造高位参数。内核执行 ELF 装载本身不依赖给 W 开放用户态文件读取 syscall。

`execveat` 是唯一特殊分支：只在 fd=3、flags=AT_EMPTY_PATH 的形态返回 USER_NOTIF，其余形态 KILL；它**不在 W 的 ALLOW 集合**。S 只给可信 B 的初次固定调用一次 CONTINUE，之后每次通知均终止本次尝试。`execve` 永久 KILL。不能声称 AT_EMPTY_PATH 强制 path 为空；绝对路径会忽略 dirfd。[execveat 文档](https://man7.org/linux/man-pages/man2/execveat.2.html)

可信 B 安装最终过滤器之后还有一个固定启动分支：`sendmsg(fd=4, flags=MSG_NOSIGNAL)`，随后关闭 4/5；不允许 recvmsg、socket 或 dup。S 检查 listener ancillary data 数量 / 截断 / 消息绑定；传递不是通用 IPC 能力。

## 永久禁止与运行库不兼容

未列 syscall 默认 KILL，包括但不限于：

- 文件 / 新 FD：open / openat / openat2 / creat、newfstatat / statx / readlink、目录操作、dup / dup2 / dup3、pipe / pipe2、memfd_create、eventfd / timerfd / epoll 创建、recvmsg、pidfd_getfd、name_to_handle_at / open_by_handle_at。
- 网络：socket / socketpair / connect / bind / listen / accept、sendto / recvfrom；不把 network none 当作这些 syscall 已禁用。
- 进程 / 权限：clone / clone3 / fork / vfork、kill / tkill / tgkill / pidfd_send_signal、ptrace / process_vm_readv / process_vm_writev、setuid / capset、mount / umount / pivot_root / chroot / unshare / setns。
- 新执行和策略改写：execve、seccomp、prctl、BPF、perf_event_open、io_uring、userfaultfd、模块 / reboot / keyring。
- 未接受外部输入 / 全局状态：getrandom、gettimeofday / CLOCK_REALTIME、sysinfo、uname、读取 /etc、terminfo 或 /proc。不得因静态 libc / Editline 可能调用这些而预设兼容。

rseq、内存布局、stdio 查询和 futex 候选只表示设计允许范围，不表示精确 payload 已使用或能通过。`prctl` 禁止也意味着不能允许 W 叠加过滤器以改变 USER_NOTIF 路径；不得把“只能收紧过滤器”误认为对通知协调没有影响。[USER_NOTIF 的竞态与过滤器警告](https://man7.org/linux/man-pages/man2/seccomp_unotify.2.html)

## S / B 设置能力与最终收紧

| 阶段 | 额外允许能力 | 收紧点 |
| --- | --- | --- |
| S 最初设置 | 固定只读 openat / pread64 / read / fstat / fstatfs / readlinkat；读取本进程 namespace / cgroup 身份；固定 MFD_CLOEXEC / MFD_ALLOW_SEALING / MFD_EXEC 的 memfd_create、ftruncate、fcntl 的密封操作、有限 dup3 / close_range；pipe2 / socketpair、仅私有 peer 的 recvmsg / SCM_RIGHTS；timerfd_create / timerfd_settime；获取随机挑战；no-new-privileges / seccomp 安装 | 所有路径来自代码固定清单；不接受 Mac 提供的路径。无写文件、外部 socket、mount 或改 cgroup |
| S 创建 B | 单次原生 clone3，CLONE_PIDFD、SIGCHLD、无 CLONE_VM / THREAD / NEW*；返回 pidfd；无法创建则失败 | 不 fallback 到不同 clone / fork / helper；创建后封闭 clone 路径 |
| B 可信装载 | 调整固定 FD、阻塞信号、确认 no-new-privileges；seccomp NEW_LISTENER；最后按上述 FD 表发送 listener 并 execveat | 不读取 solver stdin、执行第三方代码或处理 pathname 请求；过滤器安装失败立即终止 |
| S 监督运行 | poll / ppoll、有界非阻塞 read / write、预打开 cgroup FD 的 lseek+read；固定 listener 的 NOTIF_RECV / ID_VALID / SEND；timerfd 读取；对唯一 pidfd 的 SIGKILL；waitid；exit_group | 不允许再次 open、clone、创建 FD、ADDFD、ptrace 或代 W 执行 syscall；只有首次可信装载通知可以 CONTINUE |

S 与 B 在设置阶段是明确 TCB，不能将其允许 open / clone 等误说成 solver 的能力。S 的 syscall 参数指向自己拥有的缓冲，所有尺寸 checked；固定读取清单包括本容器内核视图而非任意 /proc 树。运行期的 seccomp filter 如何精确绑定各 FD、clone3 结构如何由可信代码固定，须在对应 unsafe 审查表逐项对照；单凭 BPF 不能检验指针所指结构。

## 验收与不可替代的缺口

设计接受后先生成纯策略数据 / BPF 与单元反例，审查 arch、参数高位、未知 ioctl、过滤器叠加、FD 重用和一次性状态；不得假定解释器测试等同于内核执行。真实自有探针另行授权，须覆盖 W 绝对路径 exec、第二次 exec、伪造同号 FD、listener 丢失、超时中断和父进程死亡。

本表未给 syscall 编号、可执行配置或真实 binary；它冻结已接受的能力范围，ABI 编码与精确 CLI 适配仍需实施审阅 / E4 / E5。任何表外需求、结构版本不匹配、kernel 返回不支持或不可信首次阶段，都停止，不能设置一条更宽泛的 ALLOW 来通过。
