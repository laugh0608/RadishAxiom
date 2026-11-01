# 诊断通道 L2：内部管道、统一期限与最终退出

日期：2026-11-01。状态：**入口源码已接线并完成宿主静态 / 脚本后端验证；未取得 Linux 构建或运行资格**。本页承接[交付方案](solver-linux-channel-build-and-delivery-plan.md)与[L1 私有绑定 / 报告](solver-linux-channel-l1.md)，实际命令、失败与材料见[本批记录](../records/2026-11-01-linux-channel-l2-review.md)。不授权安装 target、构建 Linux 制品、挂载或创建 / 启动环境。

## 单一入口与来源边界

同一私有包新增默认关闭的 `linux-channel-entry` feature 和 `axiom-linux-channel-init` binary（`test=false / bench=false`），入口为 [linux_channel_init.rs](../../crates/solver-bootstrap-linux/src/bin/linux_channel_init.rs)。只有 Linux / musl / AArch64 / little endian / LP64 编译分支接已有 NativeKernel；其他目标的 leaf main 固定退出 125，不生成 Linux 观察。宿主全 feature 检查覆盖全部监督 / IO / 分配包装实现，不增加模拟 NativeKernel 或 compile_error。

[统一入口](../../crates/solver-bootstrap-linux/src/channel_entry.rs)只解析 `--run-id <64 位小写 hex>`，内嵌固定正文，不开放 argv / 任意 CStr / syscall 执行 API。库内 Kernel 继续私有。默认宿主导出仍只生成三份纯数据，不调用该 binary。

本批入口消费的 input_binding **精确对应现行 offline-source-binding-only inputs**：50 源（L1 的 45 源加本批五份 Rust 源），build_inputs=null、native_build=not-accepted、两个 readiness=false。它不是最终工具 / flags 绑定，也没有资格升级开关。完整目标输入仍须 L3 明确版本 / scope 迁移；此源码状态不得直接登记为可交付构建。Cargo 中加入已核定的独立 `linux-channel` profile，不改变普通 release / test 默认、依赖和 lockfile；尚未使用该 profile 构建。

## FD 所有权与子尾段

[Io](../../crates/solver-bootstrap-linux/src/channel_io.rs)只持有显式 OwnedFd，无隐式 FD Drop；同一准备、监督、收束和终端路径没有第二套配置或 runner。

| 角色 | PID 1 | 子进程 |
| --- | --- | --- |
| 外部 FD0 / FD1 / FD2 | FD0 只检查已占用且从不读取；FD1 / FD2 检查 FIFO / 写方向并设非阻塞，借用至 raw exit。只有 PID 1 写外部 FD1 | clone 时短暂继承，执行前全部被内部端点替换；不把外部流交给采集器 |
| stdin pipe | 持有读端；写端在 clone 前关闭，关闭错误停止启动 | dup 到 0，始终 EOF |
| stdout pipe | 非阻塞读端；clone 后关闭父侧子写端 | 写端 dup 到 1；允许受管道背压约束 |
| stderr pipe | 非阻塞读端；clone 后关闭父侧子写端 | 预设非阻塞的写端**先 dup 到 2**；之后才做其他可能报告错误的 raw 调用 |
| pidfd / proc snapshot | 复用原监督器；按唯一 token 显式关闭，EINTR 不重试已消费 FD | 不继承至 exec |

先核定 PID / UID / NNP、关闭未知继承 FD≥3、冻结信号并排除已有子进程，再创建三条 CLOEXEC pipe。所有权取得一项就登记一项，任一准备失败关闭已取得的精确端点，不 clone；仅一次 fixed clone(SIGCHLD)。父侧关闭子端点后、任何 wait 之前绑定精确 pidfd。pidfd 失败保留已知 child_pid 与未知回收，不改用数字 / 进程组 / namespace 广播 kill。

子尾段只用既有 raw syscall 边界：先接 stderr，再验证子 PID / PPID、接 stdin / stdout、关闭 FD≥3、清空掩码、核对同一 work 截止、固定 exec `/bin/busybox sh -c <内嵌正文>` 与封闭环境。第一步 stderr dup 失败时静默 raw exit 126；之后失败才尝试写一次 16-byte AXCI 到内部 stderr，再 raw exit 126，无 exec 重试或 shell fallback。AXCI 仅是 stream=2 的不透明 Chunk，不能注入外部控制帧。没有新增外部 stderr 日志。

## 统一期限、传输与回收

自有入口的首个 raw BOOTTIME 在参数、hook、绑定、CString、Report / Vec 分配之前取得。Budget 只创建一次，所有阶段沿用：work=t0+18 s、cleanup=t0+19.8 s、final=t0+20 s；检查溢出和每次已读时钟回退。准备消耗不重置 t0，最后 200 ms 包含在原 20 s 内。main 前 CRT / std 初始化仍由外层 Mac 原 90 s 期限覆盖；没有以两种时钟相减认证时限。

工作和收束复用原监督器、同步 signal wait / waitid / pidfd 与 ppoll。非阻塞传输最多保留一帧，真实 offset 随写入推进；EAGAIN 只等待，EINTR 留存错误并停止工作，在原截止内继续同一帧；EPIPE / 零写 / 非法返回使流失败，不重发 Start 或在半帧后追加 Final。每轮读取量有界并轮换 stdout / stderr，持续可读的子流不能跳过取消、时钟或回收。output poll 的 ERR / HUP / NVAL 显式失败；传输已坏时只用受界 signal wait 继续回收，避免坏 FD 永久就绪的忙轮询。没有线程、后台服务、磁盘报告或新 socket。

只在完整 Chunk 实际写出后累计 exported_bytes / SHA256。cap+1 只形成已见长度下界，保存可导出的受限前缀、关闭超额读端、EOF=false，不伪造尾部摘要。达到清理截止后显式关闭剩余父端点；如还有待写帧，只在最终截止内从原 offset 补完，前序完整后才冻结 Final。无法补完则缺 Final、非零退出。

主退出、取消、工作截止和错误都进入既有精确 pidfd 回收 / 接管子进程重扫；没有在传输失败后重启子进程。**只有实际 ECHILD 设置 no_children，管道 EOF 独立记录**。ECHILD 但主退出事件缺失是可导出的失败：保留 no_children=true / main_exit=null / 首错与 errors，不能选择成功。Rust / 独立 Python codec 同步约束这一失败表示；键、版本和正常报告字节规则不变，不升级为公共格式或资格事实。

## 终端边界

Final 绑定同一输入，保留真实 Report / capture / transport 与截止观察，按既定规则选择代码。取消 / 工作截止优先保留；其他不完整 / 传输错误失败关闭为 125。Final 冻结后新取消、write / poll / clock 错误会使终端发送失败，不能重建第二份 Final。完整 Final 后时钟过期仍选择失败，即便已写出的 Final 选择为 0；外层必须拒绝这种退出不符。

终端帧的 Vec 和其他报告对象保持存活，原生 terminal 回调在同一栈上直接调用现有 `Linux::exit_group(code) -> !`，不先返回到 main、析构局部缓冲、std exit / flush 或 atexit。只有显式脚本后端测试的终端回调返回值以供检查；不向外公开该内部能力。

leaf binary 独占 `#[global_allocator]`；[最小包装](../../crates/solver-bootstrap-linux/src/channel_allocator.rs)逐项转发 System 的 alloc / alloc_zeroed / realloc / dealloc，null 直接走 raw exit 125。构造要求失败函数不分配、不重入、不展开栈；panic hook 使用同一零 IO 终端桥。空指针注入在 GlobalAlloc 方法外完成，绝不让测试 panic 穿过 GlobalAlloc 的禁止展开边界。正常 System 转发和脚本 raw exit 单独测试；未发生真实 OOM，也未安装宿主全局 allocator 或改变其他 binary。

## 有限验证与后续停止线

宿主全目标 / 全 feature 测试覆盖旧 87 项和新增 30 项，含短写 / EAGAIN / EINTR / EPIPE、半 Chunk / Final、取消与并发退出、cap+1、FD 取得 / 关闭失败、PID 复用、EOF / ECHILD 分离、清理 / 最终截止和 raw 退出。显式测试导出七份脚本内核实际写出的流，经独立 Python 解析，保留缺 Final 和 Final / 所选代码不符的负例；这些文件全是合成材料，runtime_exit_confirmed=false。具体数字、摘要和命令以记录为准。

尚未验证 Linux target 的 std / CRT / 汇编 / 链接闭包、真实 pipe / BOOTTIME / 信号 / raw exit / allocator、精确镜像 BusyBox 行为、proc / seccomp / bind 权限、Mac adapter 或 daemon 清理。panic hook 不能认证所有同步故障 / 栈溢出 / main 前失败；200 ms 足够性也没有实测保证。完整 Final 不证明 PID 1 已退出或 namespace 后代已销毁。

L2 已提交为 `5dab738`；[L3](solver-linux-channel-l3.md)已核定精确 target、完整输入与包装器方案并重核旧原包，尚未安装或实现 v0.2。下一源码切片先实现纯绑定 / 独立复核、native 捕获和包装器静态验证；取得 / 安装、一次 Linux 构建、离线制品验收、交付和真实执行分别授权。C1 / E0 / E4、G0 / A1–A10、镜像 / 权限 / 来源与独立终止 / 存储硬限缺口均保留，不创建环境试错。
