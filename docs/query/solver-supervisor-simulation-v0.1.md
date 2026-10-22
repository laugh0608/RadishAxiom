# E3 监督与 cgroup 纯模拟 v0.1

日期：2026-10-17。用途：说明 ADR 0029 D1–D3 的监督状态机与只读 cgroup 观察的纯实现接口。目标读者：监督器、传输和 P4 适配的实现者及审阅者。不包含真实 syscall、文件读取、容器操作、宿主资格、时钟误差资格或精确 CLI 的安全接受。

规范依据为[Linux 监督设计](solver-linux-supervision-design.md)与[syscall 策略](solver-linux-syscall-policy.md)。实现位于 `crates/solver-diagnostic-host/src/e3_supervisor.rs` 与 `e3_cgroup.rs`；无来源认证含义的 cgroup 字节解析提取至 `crates/solver-supervision-core/src/cgroup.rs`，合成观测构造与生命周期仍留在 host。输入均为显式合成观测，输出均为 `SimulationAction`。`scope()` 固定 `simulation`，`real_execution()` 固定 `blocked-E0-and-runtime-qualification`。没有接受调用方布尔值、观测样本或模拟通过来解除门禁的接口。

## 时钟与因果握手

所有时刻为同一系统内的 `u64` 纳秒，不把 Mac 与 Linux 的绝对时钟相减。`mac_create_start_ns` 表示首项 create 操作之前；`linux_entry_ns` 表示进入 S 自有代码。两者各自 checked 加 6,000,000,000 得到 DM 与准备上限；溢出拒绝。

`ready(nowL, observation)` 只能在 Preparing 状态调用一次，要求 cgroup 读回仅 PID 1，并将 `Lr`、准备上限、boot / PID namespace / 配置摘要封入 READY。request / policy / image / attempt / nonce 复用内部传输的 `BootstrapBinding`。配置同时固定 daemon、container、boot、PID namespace 与 cgroup namespace 身份。

`make_arm(Mr, ready, len, digest)` 检查 READY 的所有绑定，计算 `R=DM-Mr-declared_clock_error_ns`，要求 checked、严格正数；再 checked 计算 `DL=Lr+R`，要求不晚于准备上限。`declared_clock_error_ns` 只是显式合成输入，零值也不表示真实时钟存在零误差资格。len / digest 必须匹配配置中与 immutable 请求绑定的 expected query；状态机保留同一 ARM offer，禁止再次发 offer、替换 deadline 或续期。

`arm(nowL, binding, arm)` 只接收该 offer 一次，要求 `nowL<DL`。`query_complete` 对实际完整 bytes 重新计算 SHA-256，核对长度、摘要、绑定与 1 MiB 上限后才返回 `CloneOnce`，不缓存另一份 query。实际 decoder 的 query chunk 累计与结束标记由传输层处理；不能用此方法为部分 query 创建子进程。

所有提供 `nowL` 的正常事件要求时刻非递减且严格小于当前期限；READY 前使用准备上限，ARM 后使用 DL。创建意图、clone 返回、首次执行许可、reap、S final 均重新检查。外层状态与删除确认要求 Mac 时刻非递减且严格小于 DM。相等即失败。缺失观测、算术失败、时间回退与过期均永久封闭正常路径；没有宽限期。

## 唯一子进程与首次执行

`clone_returned` 接收唯一 `SyntheticChildToken { pid, pidfd_identity }`：PID 必须大于 1，不透明 pidfd identity 非零；它不是操作系统 FD。回读成员必须恰为 PID 1 和同一 child，`pids.current=2`。clone 返回已知 token 后即使发现过期或读回错误，停止动作仍保留该精确 token；不会用一个可重用数字 PID 重新定位进程。

listener 交付要求同一 binding / child、恰一 FD、没有 ancillary truncation，且只能交付一次。首次通知要求：

- 当前处于 AwaitingExec，listener 已交付；
- 非零且 synthetic `id_valid` 的 notification ID；
- 同一 child token、原生 AArch64 audit arch、AArch64 `execveat` syscall number、通知 flags 为零；
- 完整 64 位 FD 为 3、完整 64 位 flags 为 `AT_EMPTY_PATH`；
- pathname / argv / envp 指针与配置中 fork 前准备的固定值完全一致。

实现不解引用任何指针，也不把 pathname 的用户态检查当作无竞态保证。指针匹配依赖可信首次 bootstrap 的设计前提；真实 ABI、内存生命周期与过滤器审阅仍阻断真实执行。

状态在返回唯一 `ContinueOnce` 之前不可逆进入 ContinueConsumed。`continue_send_result(false)` 永久失败，不重试；重复通知、后续 W 的任何 exec 通知、无效 ID、不同 child、参数高位伪造与 listener 丢失均失败。返回动作只表达模拟意图，没有执行权限。

## cgroup 固定读取与解析

`SyntheticCgroupObservation::parse` 是外部建立观测的唯一入口；字段只读。每份完整文件非空、至多 4,096 bytes，ASCII、末尾 LF、不含 CR；数字只接受无符号十进制，checked 解析至 `u64`，拒绝 `max`、符号、空白扩张与溢出。PID checked 转 `u32`。固定字段可乱序，但必须恰好各出现一次；缺失、重复和未知字段都拒绝。内核增加字段需要重新审阅解析契约，不能静默忽略。

| 文件 | 固定内容或字段 |
| --- | --- |
| `memory.max` | 134217728 |
| `memory.swap.max` | 0 |
| `pids.max` | 2 |
| `memory.events` / `memory.events.local` | `low high max oom oom_kill oom_group_kill` 六项 |
| `memory.current` / `memory.peak` | `u64`；current 不大于 peak |
| `memory.oom.group` | 只记录 0 / 1，不修改 |
| `pids.current` | 与可见成员数量一致 |
| `pids.events` | `max` |
| `cgroup.procs` | 至多两条、非零、不重复；PID 1 必须存在 |
| `cgroup.events` | `populated=1`、`frozen=0` |

阶段成员分别恰为 `[1]`、`[1, child]`、reap 后 `[1]`。S 存活时不伪造 `populated=0`。`memory.current` 允许超过 max 的内核暂时超额事实，不把配置上限误当采样恒定不变量。

同一时间线的观察区间必须满足 `start<=end`，后一次 start 不早于前一次 end；观测 end 不晚于提交事件的 nowL，也不早于 Linux entry。所有身份必须相同；全部 memory 事件计数、pids max 计数和 memory peak 不回退；层级 memory 事件不小于同次 local 事件。`memory.oom.group` 的值不要求固定为 1，但同一容器的前后读回必须稳定，变化视为配置漂移。正常监督路径观察到 max / oom / oom_kill / oom_group_kill 或 pids max 的正增量（或新容器基线已经非零）即 Resource 失败，保留最新原始观测，不继续发布正常结果。S 准备阶段同样计入原资源预算，基线非零不能被相减抹去。

## OOM 的观察与未知

`observe_oom(before, after, child_killed, DL)` 在同一身份与非回退计数上计算 local max / oom / kill 与层级 kill 增量。possible event interval 保守取前一观察 start 至后一观察 end，因为各字段读取不是原子快照，不声称计数具有精确内核事件时刻。

只有 child 被杀且 local max、oom、oom_kill 都有增量，才返回 `LocalMemoryAssociatedNotExclusive`：这是有本地证据的关联，仍不能排除同时的全局压力。只有层级 kill、独立 kill 或不能关联 child 时返回 `CauseUnresolved`。仅 exit 137 / SIGKILL 而没有计数增量返回 `NoObservedKillIncrement`，不归因为本地 128 MiB 限额。

观察区间跨过 DL 时返回 `OrderUnresolved`；检测顺序不能变成事件因果顺序。只有整个区间严格早于 DL 才是 BeforeDeadline，整个区间从 DL 或之后开始才是 AtOrAfterDeadline。监督器或 listener 丢失保留 `final_cgroup_missing=true`；不从早期观测推算最后一次计数，也不补零。

## 终态与清理

Control EOF、协议错、deadline、资源或输出超限、reap 失败、listener 丢失和 S 崩溃均保存首个失败原因。`stop_action()` 返回停止 stdin、对已绑定且未 reap child 的 synthetic kill 意图和 S 退出意图；它们不执行任何系统操作。S 已丢失时只标记 `rely_on_pid_namespace_teardown`，不虚构死去 S 还能发送 kill。失败后仍可记录同一目标的外层退出与删除确认，但这些清理事实不恢复 completion；迟到或时间回退使 `cleanup_timing_valid=false`，不能把最终清理已记录说成按时清理。

正常本地 final 必须同时具备一次 CONTINUE 发送成功、stdout EOF、stderr EOF、唯一 child reap、同一 cgroup 只剩 S；不能只根据 exit 状态生成 final。接着必须在 DM 前取得同一身份的 `Running=false / init_pid=0 / restart_count=0`，再取得精确身份删除后置确认。缺失、矛盾、删除未确认、只有 remove 而没有退出事实和晚清理均失败。

`SimulationCompletion` 的整树依据固定为 `pidns-init-exit-and-runtime-state`；不声称读取了事后空 cgroup。该对象只供模拟 P4 适配继续验证 solver 结果，子进程非零退出仍保留原始状态，不能自动产生正常候选。只有完整清理且 `Exited(0)` 时，派生的 `normal_response_eligible` 才为 true；调用方应从监督器读取此派生判断，再交给既有 P4 检查路径。对象不表示真实执行、工具接受、宿主资格或形式证明。

## 验证范围

`tests/e3_supervisor.rs` 覆盖正向完整模拟、checked 溢出、时钟回退、期限相等、绑定重放、query 缺字节 / 错摘要、一次 clone / exec、高位参数、CONTINUE 发送失败、EOF / final 缺失、目标矛盾、资源事件、固定文件字段反例、计数回退、OOM 区间重叠与 exit 137 歧义。它检验纯状态与解析契约，不代替 E4 动态探针或真实 runtime / ABI / 精确 CLI 的资格。
