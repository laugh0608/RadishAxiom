# S 运行期策略纯模型 v0.1

日期：2026-10-17。用途：把 [E3 syscall 与 FD 策略](solver-linux-syscall-policy.md)的 S 运行期收紧为固定 FD 映射、纯 cBPF 字节生成和独立寄存器语义判定。读者：bootstrap 实现者与策略审阅者。本文不提供真实过滤器安装、Linux 程序、宿主配置或 solver 兼容性结论。

实现为 `crates/solver-supervision-core/src/policy/supervisor.rs`，host 的 `e3_policy` 保留重导出；精准测试为 `crates/solver-diagnostic-host/tests/e3_supervisor_policy.rs`。它复用父模块的有界指令生成器与独立解释器；S 的规则和语义谓词分别编写，均不继承 B/W 的规则表。ABI 符号来自 [Linux ABI v0.1](solver-linux-abi-v0.1.md)固定的 Linux v6.12 AArch64 小端输入，不能替代真实平台尺寸核验。

## 阶段与角色

此模型只表示 S 完成设置、单次创建 B、收紧到监督运行阶段之后的候选策略。设置阶段的路径读取、memfd、pipe / socketpair、clone3、过滤器安装等不在其允许集合。绝对 timerfd 已在先前阶段安装，运行阶段没有重置 timer 或续期能力。

`SupervisorFdRoles` 固定以下 21 个角色；构造 `SupervisorRuntimePolicy` 时校验完整映射。前三项必须恰为 0 / 1 / 2；所有 FD 必须在 0–i32::MAX 且互不相同。负 FD 的 u64 表示、超出有符号原生 FD 范围、高位宽输入或任何角色别名直接拒绝。角色为已有能力的数值绑定，不创建 FD，不接受路径。

| 角色 | 数量 | 运行能力 |
| --- | --- | --- |
| `control_input` | 1，固定 0 | 读取 Mac 控制封套 |
| `envelope_output` | 1，固定 1 | 写出 S 封套 |
| `diagnostic_output` | 1，固定 2 | 有界紧急诊断写出 |
| `child_stdin` | 1 | 写出已绑定 query |
| `child_stdout` / `child_stderr` | 各 1 | 读取 W 原始两流 |
| `timer` | 1 | 读取先前安装的绝对 BOOTTIME timerfd |
| `pidfd` | 1 | 对唯一子进程 SIGKILL 与非阻塞 waitid |
| `listener` | 1 | 读取 / 回答首次装载通知及检查通知 ID |
| `cgroup` | 恰 12 | 固定自有只读观测 FD，rewind + read |

12 个观测槽由未来可信设置入口一次性绑定具体对象与用途；这里的 fd 数字不证明对象类型、namespace 或文件来源。未来设置入口必须在安装运行策略前核验每个角色的 ownership、只读属性与固定清单，关闭无用设置 FD；不能把任意新路径或重复对象填进槽位来扩展能力。读回字段、解析预算与身份核对继续由 cgroup 组件和真实 FFI 负责。

21 的来源为标准 3 + child pipe 3 + timer / pidfd / listener 3 + cgroup 12；不是可增长的运行期列表。构造函数只接收固定数组，已构造策略只提供不可变角色引用。

## 闭合允许集合

所有比较均使用完整 u64 原始参数；不只比较低 32 位，不把带高位的参数规范化成合法小值。先检查 `AUDIT_ARCH_AARCH64`；其他架构或未知 syscall 默认 KILL_PROCESS。下表未限制的指针 / 长度参数仍由可信 S 构造及内核检查，不能据此声称它们已经过深层 BPF 验证。

| syscall | 精确寄存器条件 |
| --- | --- |
| `read` | fd 属于 control input、child stdout / stderr、timer 或 12 个 cgroup 槽 |
| `write` | fd 属于 envelope output、diagnostic output 或 child stdin |
| `lseek` | fd 属于 cgroup；offset=0、whence=SEEK_SET |
| `close` | fd 属于全部 21 个角色；不允许宽泛数字范围 |
| `ppoll` | nfds 在 1–21；sigmask=NULL、sigsetsize=8 |
| `clock_gettime` / `clock_getres` | clock ID 仅 CLOCK_BOOTTIME=7 |
| `pidfd_send_signal` | fd 恰为唯一 pidfd；signal=SIGKILL=9、info=NULL、flags=0 |
| `waitid` | idtype=P_PIDFD=3，id 恰为唯一 pidfd；options=WEXITED\|WNOHANG=5；rusage=NULL |
| `ioctl` | fd 恰为 listener；request 仅 NOTIF_RECV、NOTIF_SEND、NOTIF_ID_VALID |
| `brk` / `munmap` | 原生 ABI 地址空间操作；仍计入同一 cgroup |
| `mmap` | prot 仅 0 / READ / WRITE / READ\|WRITE；flags 恰 PRIVATE\|ANONYMOUS，可额外 NORESERVE；fd 为完整 u64::MAX，即原生 -1；offset=0 |
| `mprotect` | prot 仅 0 / READ / WRITE / READ\|WRITE |
| `mremap` | flags 仅 0 或 MAYMOVE |
| `madvise` | advice 仅 DONTNEED 或 FREE |
| `exit` / `exit_group` | 原生退出；不改写退出码 |

这是明确列出的 S 自身内存 / 退出子集，没有自动接纳 W 的运行库调用或 B 的可信执行分支。没有 readv / writev、fcntl / fstat、sendmsg / recvmsg、execve / execveat、open / create、新 FD、clone / thread、dup、network、seccomp / prctl、ptrace、BPF / io_uring 或 ADDFD。某个真实 S 若需要表外 syscall，应回到策略审阅；不能由动态失败自动加白名单。

## BPF 无法建立的事实

`ppoll` 只检查 count 和外围参数；BPF 不解引用 `pollfd[]`，不能验证数组内每个 fd / events、数组长度、指针有效性或 timeout 内容。单独的 ppoll 不会创建或读写另一个 FD；相关 read / write / ioctl 仍只能作用于已登记的能力。可信 S 必须只构造自己的固定 poll 数组，受控处理 ready events，并在每次循环先核对不可续期的期限。nfds=0 被额外拒绝，不把无 FD 的纯等待当作监督循环。

`read` / `write` 的 buffer 与长度、cgroup 字段内容、waitid 的 siginfo 指针、时钟输出地址、内存区间和 syscall 结构不由 cBPF 深检。未来可信 FFI 须保证指针有效、内存 ownership、缓冲预算、非阻塞与部分读写记账；禁止通过宽泛指针参数声称 BPF 验证了深层对象。

listener 的 ioctl 仅封闭命令集合与 FD。NOTIF_SEND 指针所指的响应 ID、flags、CONTINUE 次数与一次性状态不是 BPF 可读数据；未来可信 S 必须按[监督设计](solver-linux-supervision-design.md)先消费一次性状态，再发送一次 CONTINUE，发送失败不重试。后续通知一律失败；ADDFD 在字节策略中也无允许分支。纯策略不能独自证明首次执行可信，也不认证 fd 确为 listener。

pidfd 数字来自可信设置，不通过可复用 PID 搜索子进程。`waitid` 固定 WNOHANG 避免等待子进程退出；这不证明系统调用耗时、内核即时回收或 6 秒物理清理。SIGKILL、S 的 PID 1 生命周期与外层 runtime 确认仍需独立状态机和真实平台资格。

## 接口与离线验收

`SupervisorRuntimePolicy::new(roles)` 拒绝非法角色映射；`compile()` 返回 `OfflinePolicy`。`semantic_action(&SeccompData)` 是另一条直接按寄存器判断的实现，不读取规则、生成字节或解释器结果。输出动作仅 ALLOW / KILL_PROCESS，没有 USER_NOTIF 或隐式默认允许。相同固定映射生成相同字节；不同映射必须重新绑定策略 digest。

测试比较每个具体 FD 的读 / 写 / 关闭 / rewind 权限，改变固定映射验证不依赖连续数字；逐项伪造已约束参数的高 32 位，覆盖未知架构、poll 数量 / sigset、非唯一 pidfd、其他信号、waitid options、通知 ioctl 尺寸改变与 ADDFD、不可执行内存 flags、未知 syscall 和拒绝继承的 W/B 能力。另对 -1–512 的合成 syscall 编号比较生成策略与独立谓词。

测试执行的是纯 Rust 字节模型，没有安装过滤器、调用 Linux syscall、打开真实 FD、创建线程 / 进程或读取系统环境。解释器与谓词一致只能支撑本组件的动态检查；不能升级为内核验证、S 可运行性、solver 适配、Accepted / Qualified 或 E4 已通过。真实 FFI、过滤器叠加、FD 复用 / 关闭生命周期与内核结构约束保持未验证。
