# Solver 原生设置与监督源码边界

日期：2026-10-17。用途：说明 [ADR 0030](../adr/0030-solver-bootstrap-ffi-and-build-provenance.md) F2 的设置、监督、输入和观察实现及有限验证。读者：原生实现者、主审者与后续 E4 资格实施者。本文不接受工具或构建输入，不提供可运行 CLI、镜像配方、系统设置或真实执行记录。

私有实现位于 [solver-bootstrap-linux](../../crates/solver-bootstrap-linux/src/lib.rs)。原生调用与 B 尾段的 ABI、局部 unsafe 和未闭合的目标验证见[原生边界](solver-bootstrap-native-boundary.md)；实施顺序仍以[FFI 方案](solver-bootstrap-ffi-implementation-plan.md)为准。Darwin 编译真实类型化前端；只有精确 Linux AArch64 LE 配置具有 native backend。测试的 scripted backend 只操作本次测试拥有的内存，不调用宿主内核，也没有其他平台执行 fallback。

## 输入来源与停止线

`configuration::OfflineConfiguration::from_export` 消费实际 F1 四件套与其显式期望原始摘要。manifest 作为经审阅后固定的 opaque bytes 比较摘要，**不声称完成 manifest schema 或来源认证**；其来源清单与文件间绑定由 F1 导出器及独立检查路径核对。`inputs.json` 采用闭合、有序、受界数字解析，核对已有 wire 常量、固定 FD 角色及实际 W/S filter bytes；资源从导出字节取得，没有 native 侧独立可漂移的 `PROCESS_LIMITS` 默认值，也不能由启动描述覆盖。

固定十二参数另用 `AXBCMD01` 构建材料：八字节 magic、BE uint32 `argc=12`，随后十二项 BE uint32 长度与 ASCII token。单项 1..128 bytes，全部以 `--` 开头且只含可打印非空白 ASCII；总长至多 4096 bytes，拒绝 NUL、控制字符、截断和尾随数据。host 导出读取 `SolverRequest::argument_tokens()` 使用的同一 `ARGUMENT_TOKENS`，固定 `argv[0]=cvc5`，没有 native 参数副本。独立 command manifest 绑定生成入口与来源；原 F1 四文件格式不变。

`BuildMaterial` 声明将来经审阅固定的 CLI 路径、长度 / 原始摘要、UID/GID、policy bundle、配置和 CLI 接受记录身份。`ExpectedLocalInstance` 单独声明 boot、namespace 与 mountinfo 的本次实例期望摘要。namespace inode 和 mount ID 会随创建变化，**不是构建时常量或 E4 模板能够自带的事实**；将来 Mac/runtime 必须提供可信的实例读回与绑定机制，不能从 S 的 READY 自抄期望值。当前没有实现该来源机制、已接受 native 构建配置或完整 outer setup policy。

这些类型与所有执行函数均为 crate-private；没有 binary target、公共构造执行能力、默认伪 manifest 或由布尔值解除 E0/E4 的入口。上述摘要相等只表示声明与本地字节匹配。E0、精确工具链 / CRT / std / musl、outer setup policy、实例来源、E4 和外部动作授权仍共同阻断真实入口。

## 设置与资源所有权

| 阶段 | 实际调用与检查 |
| --- | --- |
| S0 | 第一项自有时间读取为 BOOTTIME；checked 计算原准备绝对期限，创建 / 固定 timer 13 并按绝对时间设定。核对 PID/TID=1、PPID=0、单线程、全部 UID/GID 非 root、五组 capability 全零、NNP syscall 和 proc 读回、boot、五个 namespace、cgroup 归属、mountinfo 与完整继承 FD 清单。没有修复权限或配置的分支。 |
| S1 | 固定目录及十二文件核对 cgroup2、只读 mount / open 属性、设备 / 文件系统身份、类型和唯一 inode；固定到 20..31。CLI 同一只读 FD 核对长度和只读属性；memfd 显式 `ftruncate` 固定长度，以 16 KiB 单块处理短读 / 短写与增量摘要，拒绝 EOF 长度差和 N+1，再检查 ELF 与 seals 读回。 |
| S1 内存 / FD 冻结 | 三 pipe 只把 S 端 10/11/12 设 NONBLOCK，B 端 40/41/42 保持 blocking；控制 0/1/2 为 NONBLOCK。创建私有 seqpacket socketpair，以有界 `getrandom(GRND_NONBLOCK)` 填满 32-byte nonce。READY 前准备 query 容量、B 的固定 argv/filter/消息及五个独占 scratch FD。 |
| S2 | 复用 core READY / ARM / query codec 与分离握手；保留 S 的原期限，ARM 只能收窄。S 内完整接收并核对 query 长度 / 原始摘要，不预填无人读取的 stdin pipe。QueryEnd 后任何控制字节，包括不足一个 header 的字节，都失败。 |
| S3 | 原 DL 前核对、冻结信号并单次 clone。父分支先记录真实 child 与 pidfd owner，再关闭所有 scratch；随后固定 pidfd 14，关闭父侧全部 B stdio/socket 端与 ELF FD。失败与未完成 query 的退出均有明确 owner 清理。 |
| S4 / S5 | 有界轮询后仅接收一次 listener；socket 的 IN 与 HUP 共存时先接收已排队消息。下层先接管所有收到 FD，再核对整条消息、截断和恰一 FD。固定 listener 15、关闭交付 socket，核对完整 21 角色后才安装原 S filter。 |

ELF 检查限定 ELF64 / little-endian / AArch64、受界 program header、文件范围、非 W+X 可执行映射、入口位于可执行 LOAD、无解释器、无 dynamic segment 和无可执行 GNU_STACK。对 dynamic segment 的保守拒绝也排除需要该段的 static PIE，未据此扩展支持范围。每次有界复制、header 读取和 seals 操作均核对同一个准备期限；静态检查不能代替精确 CLI 接受或资源适用性。

`Resources` 和 `FrozenChild` 使用显式 ownership，没有靠 Drop 自动关闭 raw FD。close 消费一次，即使 EINTR 也不按同一数字重试。prepare 的错误保留 primary、所有已取得资源的清理错误及已读取的 cgroup 原事实；固定文件 / inventory 的读取错误与同时发生的 close 错误一并保留。

## 通知、传输与退出

S 最终过滤器安装后，只在 listener 一次 readiness 后执行一次 RECV；先检查期限、控制丢失和 child 退出。核对 notification 的 child、flags、AArch64、execveat 及全部六个原始参数，其中空路径 / argv / envp 指针来自 clone 前已冻结的对象。ID_VALID 后再次检查控制输入与原 DL，再把 `ExecGrant` 从 Awaiting 不可逆变为 Consumed，最多一次 SEND CONTINUE。SEND 失败不能恢复状态，后续 POLLIN 直接失败，不再 RECV 第二条通知。

S6 对 stdin 短写按成功字节前进，完整写入后唯一关闭 stdin；stdout / stderr 各自计数、保留原 bytes，使用 N+1 读取识别超限，零写、EINTR、EAGAIN、EOF、错误和背压分别处理。封套复用 core 的单 pending frame，不在背压期间继续入队；pending 时不轮询可能已 HUP 的输出 pipe，避免无进展轮询。每轮轮询和处理后核对同一 DL，期限与控制失联优先于正常数据。

`waitid(P_PIDFD,WEXITED|WNOHANG)` 的无状态与真实退出分开。只有匹配的真实退出才记录 Reaped；完成 reap 后不再把 pidfd 加入轮询。运行中的 listener HUP 失败；W 真实退出 / reap 与 listener HUP 同轮出现时保留退出事实并继续排空两流，后续移除 listener 轮询。最终必须具有完整 query 写入、真实 reap、两流 EOF 和最终 S-only cgroup，才排队 ChildExit / Final；Final 的部分写入仍受原 DL 约束。

内部 `NativeOutcome` 仅表示本地协议完成，没有正常 P4 / authenticated capture 转换。`NativeFailure` 保留首错、child 状态、kill / wait 的实际结果、每次 close 错误以及全部已存 cgroup 读回；未取得退出状态保持 Running，不补写成功 reap。错误路径在 FD2 关闭前只尝试一次最多 128-byte 非阻塞紧急诊断，包含固定操作上下文与原 errno，部分写入 / 错误也保存在 report。它不是可靠错误传输或持久化原始观察的保证；完整跨进程失败捕获仍须由未来 Mac/runtime 接线。预留的内部终止形式最终 raw `exit_group`，没有回到 main 做标准库退出清理的生产入口。

## 原生观察与退出竞争

`NativeCgroupRead` 保存十二份原始文件字节、逐文件 BOOTTIME 区间、每文件读取完整标记及前后 child 状态。部分读取或错误也保留，不用后一次覆盖前一次。所有相邻时钟读数比较，文件内部的倒退不能被较早 start 掩盖。

core 新增 `ParsedCgroup::parse_values` / `ParsedCgroupValues::check_stage`，先严格检查全部字段，再单独核对生命周期成员 / count；原 `ParsedCgroup::parse` 路径和首错顺序保留。cgroup.events 的 populated/frozen、所有语法 / 配置、oom.group、资源事件和计数 / peak 回退均在考虑重读前检查，不能因先遇到 Membership 错误而遗漏。

只有原样本前后表明确实是唯一 child 退出、members 仍只可能为 `[1]` / `[1,child]`、pids.current 只可能为 1 / 2 的竞争，才允许原 DL 内一次额外读回；这次过渡样本也成为计数 / 配置基线。额外 PID、事件、漂移、回退和非成员字段损坏立即失败。总共只存设置基线、CONTINUE 后样本、最终样本及最多一次过渡重读四份；容量不是无界增长的替代。无法稳定核对就失败，不把过渡改写为成功稳定观察。

## 已执行与未执行的验证

Darwin pinned Rust 1.97.1 离线测试实际编译上述前端、typed wrappers 和 native ABI 结构。闭世界 setup backend 运行完整 prepare，模拟真实 FD 分配与同 open file description flags、短读 / 短写、合成静态 ELF、proc / namespace / cgroup；覆盖期限、CLI 摘要、解释器、seals、额外 FD、NNP 和双重清理错误。完整 run 脚本使用真实 FrozenChild 指针贯穿 READY 到 Final；S filter 安装的真实 SockFprog bytes 与现策略比较，安装后每个 typed syscall 的全部参数再经现 S semantic predicate 检查。

负例包括通知替换 / 第二通知、SEND 失败不可重试、交付 IN|HUP、reap 后 HUP、QueryEnd 后 partial 控制字节、控制检查 EINTR、短写 / EAGAIN / 零写 / N+1、无 wait 状态、原始失败观察保存，以及退出竞争时全部非成员字段的无 LF / 加号 / 重复、冻结、资源事件、配置漂移和计数回退。core 新接口另有与旧稳定解析的对照测试。

这些是明确 scripted 的动态检查与静态审阅，不是 Linux 内核、真实 CRT/std 初始化、内核耗时、CLI 信号 mask 兼容性或 128 MiB / 6 s 可行性的验证。本批没有 Linux 目标编译、镜像、探针、solver、系统改动或远程动作；未取得目标构建输入 / E0 / E4 资格。原 1 MiB / 4 MiB / 64 KiB、128 MiB / swap0 / pids2、6 s 及内部 solver 限额不变。
