# 2026-11-01：诊断 PID 1 监督与回收启动器最小源码切片

日期：2026-11-01（Asia/Shanghai）。状态：**库内最小实现与本机静态 / 合成验证；无 Linux 制品、可执行 CLI 或环境执行**。用途：为项目所有者、实施者和审阅者留存[最小诊断通道](../query/solver-linux-management-channel-minimum-plan.md)的监督 / 回收实现、具体停止条件与接续范围。本文不是工具接受、OS qualification 或真实整树回收记录，现行顺位见[当前状态](../status/current.md)。

## 提交与本批范围

项目所有者要求先提交前批离线核对，再推进 PID 1 监督与回收启动器的最小实现和静态验证，暂不创建或启动环境。开始时为 `dev`、相对本地 `origin/dev` 领先 3 笔，恰为前批 11 个文件，暂存区为空。复核后精确提交为 **`c4aeeb9` — `feat(cvc5): 增加诊断镜像离线核对与权限审阅`**；提交后工作区干净、领先 4 笔。没有 fetch / push、身份更改、AI 署名或历史改写。

本批只改仓库源码 / 文档，使用已有 Rust 工具链执行格式、类型 / lint 和显式内存后端测试；另从前批已留存的 BusyBox 原包只读核对 daemonize 路径，并查阅固定上游 ABI / 信号参考。没有新增依赖、lockfile 改动或源码归档获取，没有 Linux 目标构建 / 链接、归档内 ELF / shell 执行、image pull / build、container create / start / exec、machine / 服务启动、solver 或远程写入。没有修改真实宿主配置、信号、挂载、权限或 cgroup；合成 syscall 从未转到主机 OS。

## 实现落点与真实职责

沿用 `solver-bootstrap-linux` 现有 `Kernel` / `Linux`、AArch64 布局、显式 `OwnedFd`、信号冻结和原生 backend，不引入第二套 syscall 汇编、libc、init 依赖或通用进程框架。现有 solver 的 clone 尾段绑定其 seccomp / listener / solver 参数，不能直接拿来启动诊断 shell；新尾段只承担这一固定诊断职责。原 W/S 策略、角色与接受门禁不变。

| 文件 | 本批职责 |
| --- | --- |
| [channel_init.rs](../../crates/solver-bootstrap-linux/src/channel_init.rs) | unsafe 私有库内入口、固定期限、主子进程 / 回收事实、单次 clone 与固定子尾段 |
| [syscall_channel.rs](../../crates/solver-bootstrap-linux/src/syscall_channel.rs) | 诊断身份、关闭继承 FD、pidfd_open、P_ALL wait、同步信号等待；无数值 PID kill 入口 |
| [syscall.rs](../../crates/solver-bootstrap-linux/src/syscall.rs) | 复用原 waitid 结果校验；原 P_PIDFD 路径仍用相同参数 / 判定，新增 P_ALL 分支区别 ECHILD / WNOHANG |
| [abi.rs](../../crates/solver-bootstrap-linux/src/abi.rs)、[lib.rs](../../crates/solver-bootstrap-linux/src/lib.rs) | 固定新增 syscall 号和私有模块注册；无公开执行 API、依赖或机器格式变化 |
| [channel_init_tests.rs](../../crates/solver-bootstrap-linux/src/channel_init_tests.rs) | 有限内存 syscall 模型、真实入口 / 尾段指针的正负例；无真实 fork / wait / signal |

这是已经编写完整控制流的库内源码入口，尚无可从外部调用的 CLI / main。未来入口必须绑定采集正文和制品，在单线程、私有 PID / proc namespace、无并行 fork / wait / auto-reap 的前提下调用，并在有界保存 Report 后立即 raw exit，不能返回长期服务或再启子进程。入口的局部身份检查不能证明以上全部前置；没有绕过它们的默认 accepted 配置。

## 收窄内部计时与回收设计

前批已经发现 BusyBox timeout 直接作为 PID 1 的信号问题。本批从同一已留存 BusyBox `1.37.0` 归档读取 `libbb/vfork_daemon_rexec.c`：9,299 bytes、SHA256 `5ad316d72cf37b76b9cf0dbc61b1ca6e73d5111f20c9c278a186288a505517e4`；其 daemonize 路径调用 setsid。因此不能用“给 timeout 外包父进程，再只 kill 进程组”代替回收。原归档仍是前批 SHA256 `3311dff32e746499f4df0d5df04d7eb396382d7e108bb9250e7b519b837043a4`；本批没有复制该上游实现到仓库或重新取得材料。

当前最小选择是 **PID 1 自己计时，直接启动采集子进程**，移除 timeout applet / grandchild watchdog。保持内部总额度 20 s，从首个 CLOCK_BOOTTIME 读数固定两个绝对截止：18 s 用于设置与采集，末 2 s 用于收束，不能从 clone、取消或重扫重新计算。仍保持 128 MiB / 16 PID、Mac 批次 90 s 等候选值；不是新增的实测时限或硬资源保证。

启动和退出路径：

1. 拒绝空 / 超过 32 KiB 的采集正文；核对 PID / TID=1、PPID=0，real / effective UID / GID 均为 65532、附加组为空和 no-new-privileges。关闭继承 FD≥3；stderr 必须为 pipe 并设置、读回非阻塞 / 写方向，避免子分支错误报告阻塞。
2. 复用原信号冻结：阻塞可阻塞信号，重置 / 读回所有 catchable disposition，禁用 altstack，检查原截止与时钟单调性。自身 children 清单必须为空；有既有子进程就结束，不将其当作本次创建。
3. 固定仅一次 raw clone(SIGCHLD)，其余参数全 0：私有 COW VM / files、无新 namespace / CLONE_VM / THREAD；不是 clone3 失败后的降级，没有 fork / 创建重试。父分支先保留 PID，立即在不 reap 的条件下 pidfd_open；失败保留已创建子进程与回收未知，要求未来入口退出，不改用数值 kill 或重试。PID 1 保留原角色，子分支必须是 PID>1、PPID=1，关闭 FD≥3、解除继承的阻塞掩码，固定 pathname exec `/bin/busybox`，argv 为 `busybox, sh, -c, <字面正文>`，env 仅 PATH / LANG=C / LC_ALL=C / TZ=UTC。不使用 shell 插值拼接 argv。
4. 子尾段不分配、不格式化、不运行 Drop / unwind / 用户 callback。失败只尝试一次 16-byte stderr 记录 `AXCI + LE syscall nr:i32 + raw result:u64`，然后 raw exit_group(126)；不回显 pathname 参数、正文或环境。该写可能部分完成 / 失败，不能当可靠或认证的错误传输；最终可执行入口和 Mac 捕获尚未接线。
5. 父进程同步消费取消 / SIGCHLD，检查绝对期限，使用非阻塞 waitid(P_ALL) 记录实际退出。主子进程 exit code / signal / core-dump 状态原样保留；取消 / 超时不能因同轮退出成功而被已观察的成功状态覆盖。意外被接管的孤儿是诊断失败，即使最终回收完成也不改成成功。
6. 收束时先通过创建时的 pidfd 终止尚未回收的主子进程。仅读取自身 `/proc/self/task/1/children`，检查 procfs / regular-file 身份，最多 256 bytes、15 个唯一规范 PID；逐个 pidfd_open / pidfd_send_signal，不广播负 PID、进程组或整个 namespace。再回收与重扫新接管后代；同一个尚未回收的 PID 不重复发信号，回收后清除已发信号记录，后续同数值 PID 必须重新取得 pidfd。
7. 仅实际 waitid 的 ECHILD 标记 `no_children`；空清单、kill 返回 0 / ESRCH、WNOHANG 无状态和主子进程退出均不替代它。清单与 pidfd_open 之间不 reap，在单一回收者且 SIGCHLD 非 IGN / NOCLDWAIT 前提下，已退出直接子进程保留为 zombie，PID 不能在该区间复用。该内核关联仍待目标验证。
8. 首个失败原因、真实主退出、各次回收 / 信号结果和所有有界关闭错误分别保留。各观察列表至多 64 项；溢出有显式标记并结束，不丢弃后恢复成功。时钟错误、期限、PID 绑定 / 权限错误或未确认 ECHILD 均保留未完成事实；关闭不会因 EINTR 重试同一 FD。所有返回后的 namespace teardown / Docker 退出确认仍是未来入口与 adapter 的职责。

`exit_code` 只用于未来诊断进程退出：已观察取消为 128+signal、工作截止 124、其他失败 / 不完整 125，否则保留主子进程实际退出。它不产生 Evidence 五态、`proved`、资格或接受记录。总期限内因内核阻塞无法恢复控制的情况仍可能存在；本机合成计时不能消除此限制。

## ABI 与信号参考

新增数值只读参照固定 Linux [v6.18 asm-generic/unistd.h](https://github.com/torvalds/linux/blob/v6.18/include/uapi/asm-generic/unistd.h)：rt_sigtimedwait137、getgroups158、getuid174 / geteuid175 / getgid176 / getegid177、pidfd_open434、clone220。原 AArch64 LP64 布局与 raw svc 边界不变；没有把它们加入 solver final filter。

同步等待 / 默认 disposition 的关系参照 [v6.18 kernel/signal.c](https://github.com/torvalds/linux/blob/v6.18/kernel/signal.c) 的 blocked-signal 路径及 [sigwaitinfo](https://man7.org/linux/man-pages/man2/sigwaitinfo.2.html)；不是要求给 PID 1 增加用户 handler / restorer。回收区分参照 [waitid](https://man7.org/linux/man-pages/man2/waitid.2.html) 和 [pidfd_open](https://man7.org/linux/man-pages/man2/pidfd_open.2.html)。自身 children 的枚举不跨其他工作负载，也不读取命令行 / environ。自身 children 依据 [proc_tid_children](https://man7.org/linux/man-pages/man5/proc_tid_children.5.html)：未冻结的清单可能遗漏存活项，且依赖 CONFIG_PROC_CHILDREN；代码只把它当有界候选，空清单不结束回收，以重扫和真实 ECHILD 收口，缺路径则失败。以上为上游参考，不是精确 OrbStack 内核源码 / patch / 配置、真实 procfs / seccomp / LSM 或 syscall 成功事实。

静态接线审阅还核对 [Moby 上游默认策略](https://github.com/moby/profiles/blob/main/seccomp/default_linux.go)：无 CAP_SYS_ADMIN 时 clone3 为 ENOSYS，普通 clone 按 namespace flags 筛选。本诊断源码因此在执行前固定选择 clone(SIGCHLD)，不修改默认 seccomp、不加 cap，不引入运行时多路线；它不改动 solver 既有 clone3 路径。该策略页是 2026-11-01 查阅的上游参考，未绑定本机 daemon 的实际版本 / 有效规则；不能据此宣布本机允许。raw clone 的返回 / 空栈 COW 规则参照 [clone](https://man7.org/linux/man-pages/man2/clone.2.html)，不是 libc wrapper。一次额外 arm64 process.c 参考网页返回 429 后未复试，不以其作为已取得源码证据。

## 实际验证与未覆盖范围

使用现有 `1.97.1-aarch64-apple-darwin` 工具链，实际执行：

- `cargo +1.97.1-aarch64-apple-darwin fmt --all --check`：通过。
- `cargo +1.97.1-aarch64-apple-darwin clippy -p radishaxiom-solver-bootstrap-linux --all-targets --all-features --locked --offline -- -D warnings`：通过。
- `cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-solver-bootstrap-linux --all-targets --locked --offline`：最终 69 项通过，无忽略项；其中 28 项为本批诊断启动器合成测试，41 项为既有 ABI / 设置 / child / 监督 / syscall 回归。没有将不同轮次测试数量相加。
- `python3.14 scripts/check-repo.py`：完整仓库检查通过，2,907 文件；`git diff --check` 通过。局部核对恰为本批 11 路径、16 处新增本地文档引用、UTF-8 / LF / 无尾随空格 / 普通文件 `0644` 与暂存区为空；无 manifest / lockfile / ADR / filter / fixture 变化。

合成范围包括：真实主退出 / 信号保留、取消与成功竞争、固定工作 / 最终截止及时钟回退、空清单不等于 ECHILD、接管后代重扫、PID 数值复用后重新绑定、pidfd 取得失败不降级、kill 的 ESRCH / EPERM 与 wait 的 EINTR、身份 / procfs / 清单 / 规模拒绝、观察超额、固定 raw clone 参数 / exec argv / 环境、子错误写失败后仅 raw exit。测试消费实际入口和子尾段的指针计划，不复制第二套生产监督器；没有真实内核后端。

首次精准测试编译因测试断言的 Option<u64> / Option<u16> 不匹配失败，已改正后完成精准与组件回归；没有改低断言或吞掉内核错误。静态审阅发现默认 seccomp 对 clone3 的条件后，诊断创建路径在执行前改为固定 raw clone；再完成上述最终 69 项回归与 lint，旧 solver clone3 回归仍通过。

未执行：Linux AArch64 编译 / 汇编 / 链接，真实 clone / exec / 信号 / proc children / pidfd / orphan / namespace teardown，目标资源 / 性能 / 时钟 / 超额 / D-state 负例，镜像或工具接受、采集 / Mac 编排、solver、CI 或独立语义 checker。现有 typed wrappers 在 Darwin 被类型检查，唯原有 svc backend 仍受精确目标 cfg 限制；本机测试不能声称已编译或运行该汇编。

## 接续与本批结束

本批出口是完整私有监督 / 回收源码路径和有限静态验证，下一切片先核定精确 Linux 构建 / 交付及可信采集正文绑定，再接有界报告和最终 raw exit、有限采集 / Mac 编排。不能用占位正文、未接受的 native binary 或 Docker 直接运行补入口；不自动下载工具链、构建镜像、给 cap、部署或试跑环境。

实际宿主读取权限、镜像 / launcher 的来源 / 许可接受、原 native 工具链与运行前置仍未闭合；C1 / E0 / E4、G0 / A1–A10 及 readiness 均不升级。原 APK shadow 差异、签名 / 构建关联缺口和既有失败材料不变，不重复整套来源清单。

本批不新增第三方包 / 二进制、依赖或公共格式，未修改 Accepted ADR、旧规则 / fixture 或 solver 资源额度。没有后台服务、Linux 进程、容器、machine 或卷需要清理；Cargo 本机缓存保留。源码 / 文档新改动不包含在 `c4aeeb9` 中，未自动提交或推送。
