# E3 AArch64 Linux ABI v0.1 与离线过滤器

日期：2026-10-17。用途：给 [ADR 0029](../adr/0029-solver-linux-supervision-and-capabilities.md) 已接受策略提供具体数值、结构偏移、来源与纯组件复核入口。读者：实施者、ABI 与可信代码审阅者。不包含 syscall 调用、FFI、镜像、内核安装测试、solver 兼容结论或真实执行资格。

## 范围与来源

只选择 AArch64 原生 64 位小端 ABI；不是当前 Mac 的宿主 ABI。所有寄存器参数都保存原始 `u64`。`SeccompData` 是纯值，不能当作 `repr(C)` 或指针。默认 KILL_PROCESS，仅 execveat 特定分支为 USER_NOTIF。实现位于 `crates/solver-diagnostic-host/src/e3_abi.rs`、`e3_policy.rs`；监督运行过滤器另见[具体策略](solver-supervisor-policy-v0.1.md)。

下列链接固定 Linux **v6.12 tag**，2026-10-17 通过官方上游源码页面逐项只读核对。这里记录必要 ABI 数值事实和字段摘要，没有复制整套头文件、上游函数或生成绑定，也未下载/保存原头文件字节，故没有宣称上游文件 raw digest。数值来源与本仓库生成 bytes 的摘要必须区分。未来 Linux 构建接受仍须绑定实际完整源码、编译器、目标与精确内核配置；网页核对不替代它。

| 来源 | 本批映射内容 | SPDX / 使用范围 |
| --- | --- | --- |
| [arm64 unistd.h](https://github.com/torvalds/linux/blob/v6.12/arch/arm64/include/uapi/asm/unistd.h)、[Makefile.syscalls](https://github.com/torvalds/linux/blob/v6.12/arch/arm64/kernel/Makefile.syscalls)、[syscall.tbl](https://github.com/torvalds/linux/blob/v6.12/scripts/syscall.tbl) | 原生 arm64 包含生成的 `asm/unistd_64.h`；表的 common / 64 项，加 arm64 的 renameat / rlimit / memfd_secret ABI 选择。不是声称直接包含旧 asm-generic unistd | 表与 UAPI 为 GPL-2.0 WITH Linux-syscall-note；Makefile 为 GPL-2.0，仅核对生成规则 |
| [seccomp.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/seccomp.h)、[ioctl.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/ioctl.h) | action、通知结构、ioctl 编码与 CONTINUE 警告 | GPL-2.0 WITH Linux-syscall-note；只登记 ABI |
| [filter.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/filter.h)、[bpf_common.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/bpf_common.h) | sock_filter / sock_fprog 与 cBPF opcode | GPL-2.0 WITH Linux-syscall-note；不复制宏实现 |
| [mman-common.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/mman-common.h)、[mman.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/mman.h)、[linux/mman.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/mman.h) | protection、anonymous/private/noreserve、mremap、madvise | GPL-2.0 WITH Linux-syscall-note |
| [asm-generic/fcntl.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/fcntl.h)、[linux/fcntl.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/fcntl.h)、[ioctls.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/ioctls.h) | F_GETFL、flags / seals / AT_EMPTY_PATH、TCGETS | GPL-2.0 WITH Linux-syscall-note |
| [time.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/time.h)、[time_types.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/time_types.h)、[timerfd.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/timerfd.h) | clock ID、时间布局与 timerfd flags | GPL-2.0 WITH Linux-syscall-note |
| [resource.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/resource.h)、[asm-generic/resource.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/resource.h)、[futex.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/futex.h) | getrusage / prlimit64、PRIVATE futex 与 robust head | GPL-2.0 WITH Linux-syscall-note |
| [rseq.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/rseq.h) | rseq 大小 / 对齐 / 字段、UNREGISTER | GPL-2.0+ WITH Linux-syscall-note |
| [sched.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/sched.h)、[memfd.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/memfd.h)、[wait.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/wait.h)、[fs.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/fs.h)、[asm-generic/signal.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/signal.h) | clone3、memfd、waitid、SEEK_SET、SIGKILL / sigset | GPL-2.0 WITH Linux-syscall-note |
| [include/linux/socket.h](https://github.com/torvalds/linux/blob/v6.12/include/linux/socket.h) | 用户 syscall 的 user_msghdr / cmsghdr、SCM_RIGHTS、MSG_NOSIGNAL | GPL-2.0；仅读取布局和数值事实，不复制内核实现 |
| [prctl.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/prctl.h)、[asm-generic/socket.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/asm-generic/socket.h) | no-new-privileges、SOL_SOCKET 的设置审查值 | GPL-2.0 WITH Linux-syscall-note |

[Linux-syscall-note](https://github.com/torvalds/linux/blob/v6.12/LICENSES/exceptions/Linux-syscall-note) 是上游 UAPI 的 syscall 使用例外；本批不据此把其他 GPL 内核代码复制进用户程序，也不改变本项目许可证或生成产物许可。

`RSEQ_SIG=0xd428bc00` 的补充来源是内核维护者固定提交 [1ba3b5dc14923021f7815ea0b63baa34a3e1a998 的 rseq-arm64.h](https://kernel.googlesource.com/pub/scm/linux/kernel/git/abelloni/linux/+/1ba3b5dc14923021f7815ea0b63baa34a3e1a998/tools/testing/selftests/rseq/rseq-arm64.h)。它声明 LGPL-2.1 OR MIT；本批只记录数值事实，不复制汇编/宏，不把该文件伪称 v6.12 UAPI。小端下 signature 的数据值与代码值相同。v6.12 `linux/rseq.h` 本身没有定义架构 signature。

audit arch 的拼式补充核对自内核维护者固定提交 [71b500afd2f7336f5b6c6026f2af546fc079be26 的 audit.h](https://kernel.googlesource.com/pub/scm/linux/kernel/git/nathan/linux/+/71b500afd2f7336f5b6c6026f2af546fc079be26/include/uapi/linux/audit.h)，该页面报告 blob `14a1c1fe013acecb12ea6bf81690965421baa7ff`（这是 Git blob 身份，不是 raw SHA-256）。它声明 GPL-2.0 WITH Linux-syscall-note。另据 [v6.12 elf-em.h](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/elf-em.h) 的 EM_AARCH64=183 得到下面固定值。v6.12 audit.h 的本次网页获取超时，因此明确保留此来源版本差别；不伪称已保存/校验该 tag 的 audit 原字节，未来精确构建输入接受仍阻断。

## syscall 编号清单

以下是 W/B 最终过滤器与 S 运行过滤器实际使用项，均来自上述 syscall.tbl 的原生项。表外编号没有隐含 ALLOW；`nr` 的负值、未知号、带 `0x40000000` 的 x32 形态均无法命中任何规则。

| 编号 | syscall | 编号 | syscall |
| --- | --- | --- | --- |
| 25 | fcntl | 29 | ioctl |
| 57 | close | 62 | lseek |
| 63 | read | 64 | write |
| 65 | readv | 66 | writev |
| 73 | ppoll | 80 | fstat |
| 93 | exit | 94 | exit_group |
| 95 | waitid | 96 | set_tid_address |
| 98 | futex | 99 | set_robust_list |
| 113 | clock_gettime | 114 | clock_getres |
| 124 | sched_yield | 132 | sigaltstack |
| 134 | rt_sigaction | 135 | rt_sigprocmask |
| 139 | rt_sigreturn | 165 | getrusage |
| 172 | getpid | 178 | gettid |
| 211 | sendmsg | 214 | brk |
| 215 | munmap | 216 | mremap |
| 222 | mmap | 226 | mprotect |
| 233 | madvise | 261 | prlimit64 |
| 281 | execveat | 293 | rseq |
| 424 | pidfd_send_signal | — | — |

setup 审查另需：dup3=24、fstatfs=44、ftruncate=46、openat=56、pipe2=59、pread64=67、readlinkat=78、timerfd_create=85、timerfd_settime=86、prctl=167、socketpair=199、recvmsg=212、seccomp=277、getrandom=278、memfd_create=279、clone3=435、close_range=436。它们**没有**因此进入任一最终过滤器；本批没有生成 setup filter 或可调用 setup。

## 原始参数规范与数值

每一条受限参数按整个 `u64` 相等比较。非负固定 int / flags / FD 只接受零扩展；要求 -1 的 mmap fd 只接受 `0xffffffffffffffff`。`0x00000000ffffffff` 被拒绝，即使 Linux 的某些 int 参数实际会截断低位。这个较严格的内部策略已按 D3 实施范围审阅，不代表任一 libc / CLI 已兼容。指针和未列限制的 address / size / exit code 保留原值，不假装 BPF 解引用或验证全部用户 ABI 深层对象。

| 参数组 | 数值和限制 |
| --- | --- |
| audit arch | AArch64 小端 64 位 `0xc00000b7`；EM_AARCH64=183，加 64-bit `0x80000000`、little-endian `0x40000000` |
| actions | KILL_PROCESS=`0x80000000`、USER_NOTIF=`0x7fc00000`、ALLOW=`0x7fff0000`，不使用 ERRNO / TRACE / LOG 兜底 |
| stdio | read/readv fd0；write/writev fd1/2；fstat/fcntl/ioctl fd0/1/2；F_GETFL=3；TCGETS=`0x5401` |
| memory | prot∈{0,1,2,3}；MAP_PRIVATE=2、MAP_ANONYMOUS=`0x20`，必须同时出现；可选 NORESERVE=`0x4000`；mmap fd=-1、offset=0；mremap flags∈{0,1}；madvise advice∈{4,8} |
| signal | rt_sigaction / rt_sigprocmask sigsetsize=8；sigprocmask how∈{0,1,2}；不检查指针所指 handler / mask |
| clocks | MONOTONIC=1、PROCESS_CPUTIME_ID=2、THREAD_CPUTIME_ID=3、BOOTTIME=7；拒绝 REALTIME=0 |
| resources | RUSAGE_SELF=0、RUSAGE_THREAD=1；CHILDREN=-1 两种寄存器表示均拒绝。prlimit64 pid=0、resource∈{AS9,STACK3,DATA2}、new_limit=0 |
| futex | PRIVATE=`0x80`；操作仅 WAIT0、WAKE1、WAIT_BITSET9、WAKE_BITSET10，即128/129/137/138；不含 REALTIME=`0x100` 或 PI |
| runtime registration | robust head len=24；rseq len=32、flags∈{0,UNREGISTER1}、signature=`0xd428bc00` |
| 可信 B 尾段 | sendmsg fd4、MSG_NOSIGNAL=`0x4000`；close fd0..5；execveat fd3、AT_EMPTY_PATH=`0x1000` 仅返回 USER_NOTIF |

execveat 的 pathname / argv / envp 指针不由 BPF 解释；绝对路径也只是触发通知，绝不 ALLOW。S 的一次性可信 B 协调与 FD 生命周期另行约束：它们不能从上述数值过滤器自行推出。W 中 fd4/5 不存在，且没有 create / dup / recvmsg 路径；过滤器本身不提供“sendmsg 仅调用一次”的有状态保证。

## 布局和 ioctl 编码

以下 offset / size 单位均为 byte，按 AArch64 LP64 小端推导；不是当前 Rust 编译目标的 `size_of` 声明。`e3_abi` 对 seccomp_data / notif 只用显式 slice 读写，拒绝尺寸不同。通知尺寸查询结果必须精确为80/24/64；不接受扩展布局后继续解释旧尾部。

| 对象 | 大小 / 对齐 | 字段偏移 |
| --- | --- | --- |
| seccomp_data | 64 / 8 | nr:i32@0、arch:u32@4、instruction_pointer:u64@8、args[6]:u64@16（每项8） |
| seccomp_notif | 80 / 8 | id:u64@0、pid:u32@8、flags:u32@12、data@16 |
| seccomp_notif_resp | 24 / 8 | id:u64@0、val:i64@8、error:i32@16、flags:u32@20；CONTINUE=1，正常协调只用 id、val0、error0、flags1 |
| seccomp_notif_sizes | 6 / 2 | notif:u16@0、resp:u16@2、data:u16@4 |
| sock_filter | 8 / 4 | code:u16@0、jt:u8@2、jf:u8@3、k:u32@4 |
| sock_fprog | 16 / 8 | len:u16@0、padding@2..7、filter pointer:u64@8 |
| clone_args VER2 | 88 / 8 | 11个 aligned_u64 依次为 flags@0、pidfd@8、child_tid@16、parent_tid@24、exit_signal@32、stack@40、stack_size@48、tls@56、set_tid@64、set_tid_size@72、cgroup@80 |
| __kernel_timespec | 16 / 8 | tv_sec:i64@0、tv_nsec:i64@8 |
| __kernel_itimerspec | 32 / 8 | it_interval@0、it_value@16 |
| user_msghdr | 56 / 8 | name pointer@0、namelen:i32@8、padding@12、iov pointer@16、iovlen:u64@24、control pointer@32、controllen:u64@40、flags:u32@48、tail padding@52 |
| iovec | 16 / 8 | base pointer@0、len:u64@8 |
| cmsghdr | 16 / 8 | len:u64@0、level:i32@8、type:i32@12；一枚 fd 的 payload:i32@16，CMSG_LEN=20、CMSG_SPACE=24 |
| robust_list_head | 24 / 8 | next pointer@0、futex_offset:i64@8、pending pointer@16 |
| rseq | 32 / 32 | cpu_id_start:u32@0、cpu_id:u32@4、rseq_cs:u64@8、flags:u32@16、node_id:u32@20、mm_cid:u32@24、end@28；tail对齐至32 |

通知 ioctl 由 generic `_IOC` 生成：nr占8位、type占8位、size占14位、dir占2位；shift为0/8/16/30，WRITE=1、READ=2、magic=`!`=`0x21`。RECV=`_IOWR(0,80)=0xc0502100`；SEND=`_IOWR(1,24)=0xc0182101`；ID_VALID=`_IOW(2,8)=0x40082102`。ADDFD=`0x40182103` 与 SET_FLAGS=`0x40082104` 均不允许。TCGETS 是独立固定值，不能把任意同 type 或 size 请求视为等价。

## setup 的具体审查输入与停止项

此表是未来可信 bootstrap 的 ABI 审查清单，**未实现**设置 syscall、外层 Docker 策略或 FFI。纯组件没有调用它们。

| 设置动作 | 具体固定值与待审查对象 |
| --- | --- |
| clone3 | args size=88，flags仅 CLONE_PIDFD=`0x1000`；exit_signal=SIGCHLD17；pidfd字段指向父进程自有有效 i32；其他字段全0，不共享VM、files、signal handlers、线程或新namespace；只创建一次，EINTR不再次创建 |
| memfd | flags=MFD_CLOEXEC1\|ALLOW_SEALING2\|EXEC16=`0x13`；ftruncate绑定完整ELF长度；F_ADD_SEALS=1033，F_GET_SEALS=1034；WRITE8\|GROW4\|SHRINK2\|SEAL1=`0xf`；写入完整并读回密封；不 fallback 到 pathname或少flag |
| 固定FD | O_CLOEXEC=`0x80000`、O_NONBLOCK=`0x800`；dup3按明确ownership完成0..4绑定，保证无第二执行FD；安装NEW_LISTENER后FD必须5，其他返回失败 |
| seccomp安装 | no-new-privileges PR_SET_NO_NEW_PRIVS=38、值1且核对；seccomp SET_MODE_FILTER=1、NEW_LISTENER=8；sock_fprog计数和指针生命周期显式审阅；没有安装接口存在于本crate |
| timerfd | CLOCK_BOOTTIME7；create CLOEXEC\|NONBLOCK=`0x80800`；settime flags=TFD_TIMER_ABSTIME1；interval两个i64为0、value为checked绝对秒/纳秒；拒绝负值、nsec≥1e9与溢出；每次read为8byte到期计数 |
| pidfd | 来自唯一clone3结果，不按PID重新寻找；运行期 pidfd_send_signal 固定fd、SIGKILL9、info=NULL、flags0；waitid P_PIDFD3、同fd、options=WEXITED4\|WNOHANG1=5，rusage=NULL |
| SCM_RIGHTS | AF_UNIX1；SCM_RIGHTS1、SOL_SOCKET1；sendmsg参数flags=MSG_NOSIGNAL；消息payload绑定本次listener交付，ancillary恰一FD；MSG_CTRUNC8或额外控制消息失败；收到的fd必须有唯一ownership，CMSG alignment为8，不把内核msghdr当user_msghdr |

未来 unsafe 审阅还必须验证：单线程 fork 后栈/分配器约束；指针有效期与alias；内核返回errno与部分读写/EINTR；syscall寄存器与返回值宽度；siginfo / stat / statfs 的读取布局；NULL与空字符串区别；CLOEXEC、close失败和重复关闭；rseq存储的32对齐；通知ID校验先后与不可逆消费；没有并行信号handler改写初次exec参数。此清单未完成即保留E3执行阻断。

## 生成与复核边界

`worker_policy()` 从固定规则生成782条cBPF。编码为逐条8byte LE `code,jt,jf,k`，没有本机内存重解释。固定SHA-256：`2f5ff64bffb3b8cd438049d8f33d6ce86f9d3c72f4d61add5eba7da056a04e8f`，长度6256byte。变化必须重新审阅策略与golden，不能只更新预期摘要消除失败。

生成器只使用 `LD W ABS=0x20`、`JEQ K=0x15`、`JA=0x05`、`RET K=0x06`。完整64位等值由高低两次32位比较实现。分支经向前JA跳板解决8位conditional offset限制，总数≤4096。独立Rust解释器先验证**全部**指令、load边界/对齐、跳转和action，再执行，最多程序长度步；不因不可达而接受未知操作。

`semantic_worker_decision` 不读取规则表或解释器指令，直接按原始寄存器匹配。精准测试包含正例、逐参数逐bit突变、架构/x32、未知syscall、参数高位、禁止的新FD路径、绝对路径exec仍只通知、损坏/不可达坏指令、精确尺寸和golden摘要。根级独立脚本额外解释导出的实际bytes。上述均是离线 `checked`；未运行内核过滤器，未证明内核安装可行、实际payload兼容、FD生命周期已建立或真实环境有资格。
