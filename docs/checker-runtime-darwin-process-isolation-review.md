# Checker runtime Darwin process isolation 原语审阅单

状态：当前主机的公开 spawn / 观察原语已形成合成证据，但现行 isolation / hard-memory 契约不可由其完整实现
审阅日期：2026-09-02

## 目标与结论

本审阅承接 [immutable spawn plan 切片](checker-runtime-spawn-plan-slice-review.md)，只判断 Darwin 当前公开原语能否承载 [ADR 0011](adr/0011-checker-runtime-launcher-installation-and-activation.md)、[ADR 0012](adr/0012-product-checker-runtime-host-and-persistence-interface.md) 与 Execution Profile Contract v0.1 已冻结的进程边界。所有动态观察只运行自行编译的合成 helper，并只写 `/private/tmp` 下的精确临时目录；没有执行 checker、读取产品根、修改系统配置 / 权限或写远程状态。

结论不是“Darwin launcher 已可实现”：

- exact path spawn、argv / 空环境、EOF stdin、stdout / stderr pipe、descriptor working directory、独立 process group、外层 deadline kill、直接子进程 reap 和运行中 executable path 观察都有公开原语，并已在当前主机形成合成证据；
- stream cap 与 deadline 可以由受信任父进程用 nonblocking I/O、单调时钟、process-group signal 和 `wait4` 实现，但仍需扩展当前只含文件系统能力的私有 FFI；
- Darwin 公开 `posix_spawn` attribute 没有 per-child rlimit 或 sandbox attribute；legacy `sandbox_init` 已被 SDK 标为 deprecated / no longer supported；正式 App Sandbox 会引入签名、entitlement、产品打包和继承关系，不是当前 spawn adapter 的局部实现细节；
- 现行 `128 MiB` outer working-memory **hard limit** 没有得到可用实现：`RLIMIT_RSS` 只是 `RLIMIT_AS` alias 且系统手册描述为内存压力下的回收偏好，当前 helper 对 `128 MiB` 的 `RLIMIT_AS` / `RLIMIT_RSS` / `RLIMIT_DATA` 均返回 `EINVAL`；`task_set_phys_footprint_limit` 又因内核 privilege 检查返回 `KERN_NO_ACCESS`；
- process group 不是不可逃逸的 process tree 容器，子进程可通过新 session / process group 脱离；`wait4` 也只能可靠回收直接子进程；
- `posix_spawn` 仍按路径解析 executable，Darwin 没有供本路径使用的 `fexecve` / `execveat`。spawn 前后 path、device / inode、length / digest 与 `proc_pidpath` 可检测大量漂移，但不能在同 UID 对手可并发替换路径的威胁模型下关闭 lookup TOCTOU。

因此 `NativeIsolationStatus` 必须继续保持 `RequiredNotProven`，当前不能创建可被 qualification 或 product invocation 使用的 native adapter，也不能推进真实 checker 执行或 activation。

## 审阅环境

| 项目 | 当前观察 |
| --- | --- |
| 主机 | macOS `26.6.2` build `25G83`，Darwin `25.6.0` arm64 |
| 开发工具 | Xcode `26.6` build `17F113` |
| SDK | macOS SDK `26.5` |
| Rust ABI 来源 | 已验收且已锁定的 `libc = 0.2.189`；本审阅没有新增或升级依赖 |
| 动态输入 | 自行编译的 C helper、合成 empty working directory、空 environment、pipe 与短时 sleep |
| 未触及 | checker / payload、真实 bundle、产品根、qualification、activation、网络、系统 entitlement / 权限与远程状态 |

这只是在上述单一 OS / SDK / hardware 组合上的证据，不外推为其他 macOS 版本、Intel、其他文件系统或六平台结论。

## 可承载的外层进程能力

### Spawn 与 descriptor boundary

公开 `spawn.h` 可以形成以下窄边界：

- `posix_spawn` 只接收已解析的 absolute executable path，不使用 `posix_spawnp` 或 `PATH`；
- `argv` 和 `envp` 由调用者显式传入；空 `envp` 的 helper 实际观察到零环境项；
- file actions 将预创建的 pipe 绑定到 stdin / stdout / stderr，父进程关闭 stdin writer 后，子进程实际观察到立即 EOF；
- macOS 26 的 `posix_spawn_file_actions_addfchdir` 可用已打开的 empty directory descriptor 设置 cwd；当前 helper 观察到精确工作目录；macOS 10.15–26 的 `_np` 旧入口虽仍在 SDK，但已被新名称替代，产品最低系统版本尚未在本审阅冻结；
- `POSIX_SPAWN_CLOEXEC_DEFAULT` 与显式 file actions 可以缩小意外 descriptor 继承；`POSIX_SPAWN_SETPGROUP` 可为 direct child 创建独立 process group。

exact `libc 0.2.189` 已绑定 `posix_spawn`、标准 file actions、spawn flags / process group、`poll` / `kqueue`、`killpg`、`wait4`、`proc_pidpath` 与 `proc_pid_rusage`。它尚未绑定 macOS 26 的 `addfchdir` 新入口；若实施，仍需在窄平台 wrapper 中增加一个已核对 SDK ABI 的声明，而不是在 safe core 手写调用。

### Stream、deadline、kill 与 reap

当前合成 helper 已证明父进程可以：

1. 分别取得 bounded stdout / stderr 字节；
2. 在 child 仍存活时用 `proc_pidpath` 观察 executable path；
3. 让 child 成为自己的 process-group leader；
4. 在 50 ms 后对该 group 发送 `SIGKILL`；
5. 用 `wait4` 回收 direct child，并得到 signal termination 与 `rusage`。

生产实现若获授权，必须同时 drain 两个 nonblocking stream，达到任一 cap 时先把本次调用归类为 outer failure，再终止 / reap；不能先阻塞等待进程退出，也不能保留前缀 stdout 供 result consumer 使用。deadline 必须使用单调时钟，并把 timeout、kill 失败、reap 失败与 stream failure 保持为不同的内部诊断事实，最终只映射到既有有界 outer failure 分类。

这些原语只证明 direct child 和没有主动逃离 group 的 descendants 可被 group signal 覆盖。它们不构成 macOS Job Object、subreaper 或不可逃逸 process tree，也不证明非合作 checker 无法遗留进程。

### 运行中与 spawn 后 executable 观察

`proc_pidpath` 在 helper 存活期间返回了实际 absolute path；父进程也可以在调用前后用既有 descriptor store 能力重开 slot executable，核对普通文件、owner / mode、device / inode、length、Mach-O target 与 SHA-256。`proc_pid_rusage` 可观察 physical footprint / peak 指标，`wait4` 可提供 direct-child 最终 usage。

这些都是检测和计量原语，不是 path execution 的原子身份绑定。当前 SDK 的 `posix_spawn` 接口没有 executable fd 参数；`POSIX_SPAWN_START_SUSPENDED` 最多提供“子进程开始用户代码前观察”的时序窗口，也没有把进程已装载 vnode 直接绑定到登记 SHA-256。现有 preflight / postflight 仍应保留，但不能声称已消除同 UID 并发替换的 TOCTOU。

## 无法满足的现行边界

### Network 与 filesystem isolation

当前 SDK `sandbox.h` 明确声明整个 header deprecated，并要求采用 App Sandbox；`sandbox_init` 与 named profile 又被标为 `No longer supported`。因此不能把 `kSBXProfileNoNetwork`、`kSBXProfileNoWrite` 或私有 profile 作为生产 fallback。

[Apple App Sandbox](https://developer.apple.com/documentation/security/app-sandbox?changes=_4) 是 entitlement 驱动、由内核执行的静态能力边界。[Enabling App Sandbox](https://developer.apple.com/library/archive/documentation/Miscellaneous/Reference/EntitlementKeyReference/Chapters/EnablingAppSandbox.html) 与[在 sandboxed app 中嵌入 command-line tool](https://developer.apple.com/documentation/xcode/embedding-a-helper-tool-in-a-sandboxed-app)又要求被继承 sandbox 的 child target 使用 `com.apple.security.app-sandbox` 与 `com.apple.security.inherit`，并进入产品签名 / 嵌入流程。

这意味着当前独立发布的 standalone checker binary 不能仅靠一个 spawn flag 获得已证明的 no-network / readonly-bundle / empty-working-directory-only 边界。采用 App Sandbox 至少会改变：

- launcher / checker 的签名与 entitlement 身份；
- executable 是直接 payload、受信任 trampoline 还是嵌入 helper；
- bundle 与工作目录如何通过 static entitlement 或用户选择 / security-scoped grant 暴露；
- qualification acceptance 是否必须绑定签名与 entitlement；
- distribution、installation receipt、runtime TCB 和重新验证范围。

这些都超出当前 `0.3` policy 的局部平台实现，必须先做替代设计与身份迁移分析。

### `128 MiB` hard working-memory limit

Darwin SDK 把 `RLIMIT_RSS` 定义为 `RLIMIT_AS` 的 source-compatibility alias。当前系统 `getrlimit(2)` 手册又把它描述为内存紧张时系统优先从超限进程回收内存的偏好，不是确定性 fatal physical-footprint boundary。

合成 helper 的精确结果是：

```text
RLIMIT_AS 128 MiB   -> EINVAL
RLIMIT_RSS 128 MiB  -> EINVAL
RLIMIT_DATA 128 MiB -> EINVAL
RLIMIT_AS 1 GiB     -> EINVAL
RLIMIT_AS 1 TiB     -> accepted
```

这与当前动态链接进程的既有虚拟地址空间一致，也说明 `RLIMIT_AS` 即使可设置，也不能作为 `128 MiB` physical working-memory hard limit。公开 `posix_spawnattr_set*` 列表同时没有 per-child rlimit 入口；受信任 trampoline 在 `exec` 前调用 `setrlimit` 也无法把本机观察到的 128 MiB 配置变成有效边界。

SDK 虽声明 `task_set_phys_footprint_limit`，但当前普通 helper 对自身设置 `128 MiB` 返回 `KERN_NO_ACCESS (8)`。Apple 开源 XNU 的[对应入口](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/kern/task.c#L7114-L7138)先执行 `proc_check_footprint_priv`，失败统一返回 `KERN_NO_ACCESS`，并注明该调用可能应被废弃；公开 privilege 表把这一能力列为 [`PRIV_VM_FOOTPRINT_LIMIT`](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/priv.h)。普通产品进程不能把头文件中可见的函数声明当作已授权能力。

`proc_pid_rusage` 周期采样再 kill 只能形成 observation-based overshoot boundary：采样间隔内可能已经超过限制，分配失败与内存压力行为也不确定。它可以辅助诊断和 postflight 计量，但不能满足现行 machine contract 的 hard limit。

## 对设计与下一步的影响

当前有两层不同问题，不能由同一个“先写 adapter”任务掩盖：

1. **可实现但尚未授权的外层 supervisor**：exact spawn、descriptor cwd、empty env / stdin、双 stream cap、单调 deadline、process-group kill、direct-child reap、`proc_pidpath` / rusage observation。它可以复用 exact `libc 0.2.189`，不需要新增 registry dependency，但会新增 process FFI / `unsafe`、平台测试 helper 与 workspace 组件或扩大既有平台 crate 职责。按当前停止线必须另行授权；完成后仍只能保持 `RequiredNotProven`，不能执行真实 checker。
2. **必须先决策的强隔离**：App Sandbox / 签名打包、hard physical-memory enforcement、不可逃逸 process-tree containment 和 executable path TOCTOU。若选择降低为 best-effort observation，会弱化 ADR / Execution Profile / launcher policy 的既有 hard boundary并触发公共身份迁移；若选择特权 broker、系统 service、虚拟化或新的 signed helper 架构，则涉及新可信基、系统权限 / 配置、产品打包与发布身份。两类方案都不是本审阅可自行决定的实现细节。

在所有者选择并授权前：

- 不新增 native process crate，不扩大 filesystem-only FFI，不修改 policy / public format；
- 不把 `proc_pid_rusage` polling、`RLIMIT_RSS` 或 legacy sandbox 写成 hard enforcement；
- 不运行真实 checker，不创建 qualification，不选择 inactive payload，不推进 activation；
- active runtime 保持 0，launcher policy 保持 `specified-not-implemented`。

## 合成验证与清理

本审阅实际运行：

```text
xcrun clang -std=c17 -Wall -Wextra -Werror -O2 <synthetic-helper.c>
<helper> <synthetic-empty-working-directory>
```

关键观察：

```text
observed executable path = exact helper path
child process group       = child pid
cwd                       = synthetic empty working directory
environment count         = 0
stdin bytes               = 0
stdout / stderr           = independently captured
normal child              = exit 0 and wait4 reaped
deadline child            = SIGKILL and wait4 reaped
task footprint limit      = KERN_NO_ACCESS
```

helper source、binary 与 empty working directory 只用于本次研究，复核后从精确 `/private/tmp/radishaxiom-darwin-process-review-20260902` 删除。没有把临时程序、绝对路径、PID 或运行输出加入机器契约、canonical artifact 或产品日志格式。
