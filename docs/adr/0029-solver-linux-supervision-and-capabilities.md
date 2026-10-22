# ADR 0029：solver Linux 监督与能力边界

日期：2026-10-17。状态：Accepted。项目所有者于 2026-10-17 明确接受 D1–D3，包括新增受信任监督代码、装载协调机制和内核 / runtime 退出确认前提，并授权具体 ABI、内部传输格式、离线纯组件与模拟测试。接受不代表工具或运行资格，不授权构建镜像、探针、solver 或系统修改。

用途：收口 [ADR 0028](0028-bounded-solver-calibration-entry.md)窄入口的 B4 独立终止与 B5 能力边界。读者为项目所有者及执行层审阅者；不改变公共 IR / Evidence、旧 query / P4 字节或 solver profile。

## 问题

E1–E2 已有纯模拟组件，但 Mac 定时器、停止 Docker CLI、`exec` 后消失的 bootstrap 都不能独立监督仍在 Linux 内运行的 solver。Docker 配置、容器状态和 cgroup 内核事实也不能相互替代。

另发现初稿中的装载约束不充分：`execveat(fd, path, ..., AT_EMPTY_PATH)` 仍可使用非空绝对路径，此时忽略 fd。只匹配 fd / flags 并依赖 CLOEXEC，不能证明仅执行一次。见 [Linux execveat 文档](https://man7.org/linux/man-pages/man2/execveat.2.html)。

## 已接受决定

### D1：容器内持续监督，范围不增额

采用同一专用 PID namespace / cgroup 内的两个单线程进程：PID 1 监督器 S，以及唯一子进程 B（可信装载阶段，随后成为 solver W）。不增加 sidecar、常驻 daemon、host broker、Docker init helper 或第二次 attempt。监督器、装载过程、memfd、缓冲和 solver 全计入既有 128 MiB；`pids.max=2` 是额外收紧，不增加原内存 / 时间预算。

S 使用 Linux 绝对到期 timerfd、非阻塞事件循环与 pidfd；不依赖 Mac 或 daemon 发来终止命令。到期先停止转发、发送 SIGKILL，再退出 PID 1；PID namespace init 终止使内核杀死 namespace 内其余进程。父监督器异常死亡同样触发该边界。这依赖 Linux 内核与调度继续工作，不能覆盖 VM / 内核停止运行的实时保证。[PID namespace 文档](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html)

### D2：剩余时间握手与可见事实分层

Mac 的 6,000 ms 窗口仍从首项执行控制操作开始。Linux READY 记录本地时钟，Mac 接收 READY 后用已经消耗的全局时间计算剩余预算，再发送绑定本次挑战的绝对 Linux deadline；消息延迟不能重新获得完整 6 秒。未收到有效 ARM 时不创建 solver 子进程；准备阶段的本地到期仅用于回收，不能认证已满足全局窗口。

cgroup 只读观测限定于 runtime 提供的私有 namespace 内本容器根；不写 cgroup、不挂入宿主控制目录、不依赖 `cgroup.kill` 写权限。要求 `memory.max=134217728`、`memory.swap.max=0`、`pids.max=2` 实际读回。OOM、子进程回收、PID 1 退出与容器删除分别记录；不能从内部 PID 1 宣称已读到整个 cgroup 为空。正常完成必须由已取得资格的内核 / runtime 终止路径和控制端最终状态共同确认，并且仍在 6 秒窗口内。

### D3：分阶段 syscall 策略与可信首次装载

采用封闭的三阶段能力表：监督器、可信装载子进程、solver；默认禁止未列 syscall，solver 不取得文件、网络、创建进程 / 线程、改权限、改 namespace 或安装新过滤器的能力。

首次 `execveat` 不用单纯 fd 匹配放行。由可信装载子进程安装 USER_NOTIF 过滤器，把 listener 交给 S；S 在不可回退的一次性装载状态中，只协调自己创建的可信 B 的固定调用。进入 solver 后不再有 CONTINUE 分支，第二次 exec 请求直接终止本次尝试。该方案依赖可信 B 在初次装载前不执行不可信代码、不处理 solver 输入、没有共享可写内存 / 并行线程或可改写参数的信号处理器。

USER_NOTIF **不能作为检查不可信 pathname 后放行的通用安全机制**；官方明确警告 CONTINUE 的 TOCTOU 风险。本决定只允许可信启动代码的同步，不读取目标 pathname 再作授权，也不代理 open / network。上述阶段不变量、listener 生命周期和过滤器不可替换性必须经实现审查与负向探针，否则 B6 装载门禁不闭合。[Linux USER_NOTIF 文档](https://man7.org/linux/man-pages/man2/seccomp_unotify.2.html)

## 后果与停止线

具体时间公式、失败矩阵、cgroup 事实与 ABI 清单见 [E3 设计](../query/solver-linux-supervision-design.md)，syscall 边界见[策略表](../query/solver-linux-syscall-policy.md)。这是已接受的单一设计，未把普通 OS 定时器声明为实时保证，也未声称当前 OrbStack 已支持所有所需接口。

代价是增加监督器、内部传输和一次性装载状态的 TCB，并占用原资源额度；若精确 CLI 因该占用或严格 syscall 表不能运行，记录失败，不增限或扩白名单。实现无法满足本决定时维持纯模拟状态，不自动切换其他装载 / 隔离方案。

E0 实际系统库、完整链接库存、许可接受与构建关联缺口继续阻断真实路径。D1–D3 已由项目所有者接受；仍须具体实现 / ABI 审查、已接受构建输入及分别授权的 E4 资格、E5 校准和 E6 单次尝试。接受设计不等于执行授权。
