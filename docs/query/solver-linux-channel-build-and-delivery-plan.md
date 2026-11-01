# 诊断 Linux 启动器：目标构建、交付与最终入口方案

日期：2026-11-01。状态：**方案已静态核定；实施候选，build_ready=false / execution_ready=false**。用途：向项目所有者、实施者和审阅者明确[最小通道](solver-linux-management-channel-minimum-plan.md)的精确目标、采集正文绑定、输出所有权与退出路径。本页不接受工具 / 许可证 / 宿主资格，不提供已经可运行的构建或容器命令，不授权安装、构建、交付挂载或环境执行。实际盘点和验证见[本批记录](../records/2026-11-01-linux-channel-delivery-review.md)，现行顺位见[当前状态](../status/current.md)。

方案随后提交为 `2e5da3a`；按项目所有者的下一批授权，[L1](solver-linux-channel-l1.md)已实现真实采集正文、45 源输入绑定与 Rust / Python 报告纯组件，并完成本机静态 / 合成验证。L1 导出的 scope 仅为 offline-source-binding-only，完整目标工具 / flags 尚未绑定，不替代本页最终构建 inputs。L2 管道 / 首截止 / 最终退出仍未接线；没有执行采集正文或新增 Linux 制品 / 环境。

## 唯一候选与当前缺口

沿既有 [Rust / musl 候选](solver-bootstrap-ffi-implementation-plan.md#d1-候选结构与原生边界)，选择 **macOS AArch64 上的 Rust 1.97.1，交叉构建 aarch64-unknown-linux-musl 的静态非 PIE AArch64 LE ELF**。不引入新 Linux 构建容器、GCC / SDK、QEMU、动态 libc 或 no_std 第二路线；原 cvc5 glibc 路线不变。用已有 bundled rust-lld 的 GNU flavor，交付为已审 Alpine 候选内的只读附加文件，不构建派生镜像。

[本机观察](../records/cvc5-control-plane-2026-11-01/channel-build-input-candidate.json)实际确认：

| 层次 | 本机事实 / 不能外推 |
| --- | --- |
| 编译器宿主 | `1.97.1-aarch64-apple-darwin`，rustc commit `8bab26f4f68e0e26f0bb7960be334d5b520ea452`；Cargo commit `c980f4866141969fab6254a680546a277789d6f0` |
| 链接器候选 | 已有 `rust-lld 22.1.6`，LLVM commit `dcc3606807c989700e0ac1cac18c31741bcd40d9`；三份宿主工具实际文件的长度 / SHA256 已留存，不等于发布者认证或其动态库闭包接受 |
| 目标组件 | 已安装 target 只有 `aarch64-apple-darwin`；Linux musl target 目录与安装 manifest 均不存在。不能运行 rustup 安装，也不能据 `--target` 字符串宣称可以离线构建 |
| 方案核定时源码 | `be8c620` 只有库内监督 / 回收入口，不把该提交写成可执行制品来源。随后 L1 正文 / 纯组件见页首接续；native binary / IO / 最终入口仍未实现 |
| 镜像 | 仍为前批固定 index / arm64 manifest；留存 rootfs 的 `/mnt` 是 `0:0 / 0755` 空目录。镜像 / 许可与宿主读取资格仍未接受 |

目标选择依据是 [Rust 目标说明](https://doc.rust-lang.org/rustc/platform-support/aarch64-unknown-linux-musl.html)与精确 [1.97.1 target](https://github.com/rust-lang/rust/blob/1.97.1/compiler/rustc_target/src/spec/targets/aarch64_unknown_linux_musl.rs)。后者声明静态 CRT 默认与 musl 1.2.5 描述，但不是本机缺失组件的实际包库存、构建认证或许可结论。所需组件须另作**仅这个版本 / target 的有限取得与接受**，不恢复整套 Rust / GCC 来源研究；缺字节、来源 / 许可或链接闭包就停在构建前。

## 目标构建输入与参数

未来在同一 workspace 的 `radishaxiom-solver-bootstrap-linux` 包添加 `axiom-linux-channel-init` binary，入口拟置 `src/bin/linux_channel_init.rs`，显式 `required-features=["linux-channel-entry"]`、默认 feature 关闭、`test=false / bench=false`。库只向这个 leaf binary 提供受同一 feature 和精确 Linux AArch64 LE LP64 cfg 约束的隐藏入口，不开放任意 CStr / argv 执行 API。普通宿主全 feature 检查仍须通过：非目标 binary 只能固定拒绝并退出 125，不能产生 Linux 报告、调用原生 backend 或模拟成功；真正目标入口及其逻辑必须继续可用 scripted backend 做本机检查。禁止用 compile_error 迫使仓库放宽现有宿主全 feature 检查。

仅构建指定 package / bin / feature / target / profile，使用 `--locked --offline --jobs 1 --verbose --verbose`，留存真实编译 / 链接调用；不构建 examples、测试、工作区全体、solver 或 dev-dependency 路径。实际 normal Cargo 闭包是本包、`solver-supervision-core` 与 `digest`，均为已有 path 依赖；以实际 Cargo 元数据和编译 / 链接调用重核，不因 Cargo.lock 还有其他包就声称它们都进入二进制，也不忽略传递的 std / CRT 输入。

拟新增仅供本 binary 使用的 `linux-channel` profile（不改全局 release / 测试默认）：`inherits=release, opt-level=2, codegen-units=1, lto=false, panic=abort, overflow-checks=true, debug=1, strip=none, incremental=false`。精确 linker 是当前 sysroot 下 `lib/rustlib/aarch64-apple-darwin/bin/rust-lld`，禁止以 PATH 中的 ld / cc 替代。flags 必须作为结构化数组经受控 CARGO_ENCODED_RUSTFLAGS 传递，候选固定如下，表中输出目录在生成具体构建计划时解析为新建任务目录的绝对路径：

| 项 | 候选值 |
| --- | --- |
| 目标代码 | `-C target-cpu=generic`、`-C target-feature=+crt-static`、`-C relocation-model=static`、`-C prefer-dynamic=no` |
| 链接输入 | `-C link-self-contained=yes`、`-C linker=<已绑定 rust-lld 绝对路径>`、`-C linker-flavor=ld.lld` |
| 最终链接 | 分别传 `-C link-arg=-static`、`-C link-arg=-no-pie`、`-C link-arg=-z`、`-C link-arg=noexecstack`、`-C link-arg=--trace`、`-C link-arg=-Map=<任务输出>/link.map` |

以上不是可直接执行的占位命令。既有 rustc 的 `-C help` 已确认选项名称，flags 的组合、CRT 选择和最终 ELF 仍未构建验证。精确 [1.97.1 musl base](https://github.com/rust-lang/rust/blob/1.97.1/compiler/rustc_target/src/spec/base/linux_musl.rs)及 [CRT 选择](https://github.com/rust-lang/rust/blob/1.97.1/compiler/rustc_target/src/spec/crt_objects.rs)只支持候选方向；不能把 bundled CRT 与 Alpine rootfs 中的 musl 当作同一已接受来源。失败不得自动改 PIE、加系统库或换 linker。

构建调用前必须封闭以下输入：

- **源码快照。** 最终入口实现后的精确 commit，加全部实际三包源码 / Cargo 文件、Cargo.lock、rust-toolchain、采集原字节、生成器、生成输入及各自长度 / SHA256；拒绝脏源码、缺文件、目录外 symlink 或事后改写。当前 `be8c620` 只是基线，不预填未来源码 / ELF 摘要。
- **目标组件与链接闭包。** 精确版本发行 manifest / target 包及其原字节摘要和有限接受依据，真实 rust-std rlib、musl / CRT / compiler-builtins / panic runtime / allocator 与链接器输入 / 许可。先重用已有且完全匹配的审阅材料，再仅补这一组件的缺项；不推定 version 字符串等于包认证。所有链接输入记录解析后的真实路径、原字节与 archive member；map / trace 的无歧义关联不足就拒绝制品。
- **环境与副作用。** 直接调用已绑定的 cargo / rustc；审阅并隔离 Cargo 的逐级配置与 CARGO_HOME，关闭继承的 RUSTFLAGS、wrapper、runner、target linker 和动态加载注入；只传固定 PATH / locale / 任务输出及必要精确工具路径。不复制凭据或宿主完整环境。不引入 build.rs 网络 / 下载、任意 build script 或外部生成工具。`--offline` 不能代替构建输入封闭。
- **有限占用。** 候选一次构建、jobs=1、600 s 单调总期限；任务根（含生成、build / delivery 副本与 records）输出观测上限 512 MiB，单 ELF 16 MiB、map 8 MiB、双流日志合计 4 MiB。它们是未来包装器的停止 / 留存条件，Mac 文件计量和进程组取消不构成已验收的 RSS / 块 / inode 硬限，不能冒充原 Linux 构建或 solver 资格。实测超额、工具失败或不能精确停止就保存结果结束，不增限重试。

目标组件安装的精确候选动作是 `rustup target add --toolchain 1.97.1-aarch64-apple-darwin aarch64-unknown-linux-musl`，本批未执行。执行前另行绑定 installer 的实际版本 / 原字节、发行 manifest、仅这一 target 的归档及解包清单；候选原包上限 128 MiB、解包 512 MiB、一次安装请求 120 s，实际取得 / 安装影响和接受范围须先明确授权。Rustup 可能写 target 目录、component manifest / components 与下载缓存，不能把它称为仓库内无副作用操作；完成后须与已审归档逐文件核对再允许构建。失败保留原包 / 日志 / 部分状态，不重复安装或手删 sysroot；后续清理只可另按授权用精确 target remove，不卸载整个 toolchain 或删除全局缓存。该组件 / 缓存不属于上述 build 任务根的 512 MiB，须单独计量，不能在额度里漏记。

构建后独立检查 ELF64 LE / AArch64 / **ET_EXEC**，无 PT_INTERP、DT_NEEDED、RPATH / RUNPATH、可写且可执行 LOAD，GNU_STACK 明确不可执行；entry 与 segment / section / archive member 关联一致。核对所有权 / 模式及库内 native svc / raw child / panic / 分配失败出口实际链接可达性。旧 cvc5 ZIP 检查器和原镜像检查器不为此放宽；复用有界解析能力时保留各自类型 / 来源语义。参数或 linker 退出 0 不能代替这些检查，不能接受动态 / PIE 输出“先跑一次”。

## 采集正文与构建绑定

唯一正文现置 `scripts/cvc5-build-support/inspect_linux_host.sh`，由后续 L1 创建并仅做静态 / 合成验证，未运行。正文为 UTF-8 无 BOM、LF、末尾 LF、无 NUL，1..32,768 bytes；SHA256 对**含末尾 LF 的原字节**计算，不含之后的 CString NUL。拒绝编码 / 行尾漂移，不 trim、不重新转义或从运行态环境取脚本。

L1 的 `channel_profile.rs` 作为单一类型化常量来源，承载现有期限、PID / 字节 / 帧预算及 profile 版本，编译期以 include_bytes 捕获正文；复用既有 digest 在父侧核对 / 计算相同原字节，再只构造一次 CString 传给私有 run。正文不从 argv、stdin、宿主挂载或 report 反向载入；子分支继续固定 `/bin/busybox` 和 `busybox, sh, -c, <已绑定字面正文>`。先实现并审阅真实白名单采集 / 脱敏 / 有界读取与失败处理，不将 printf 占位程序封成可接受制品。

最终构建输入应由显式离线生成器从同一次源快照导出版本化 `inputs.json`（≤1 MiB）：有序源码清单、正文 profile / 长度 / raw SHA256、类型化预算、目标 / flags / 工具输入身份和采集白名单。该文件只绑定声明，不可覆盖代码常量；独立 checker 对源码 / 正文 / 数值双向核对。其 raw SHA256 是 `input_binding`，编译期捕获同一原文件；Start / Final 仅报告该摘要及实际内嵌正文摘要，Mac 必须与**事先登记**的输入比对，不能把收到的摘要当期望值。

生成输入不得含自身摘要、最终 ELF / build manifest / 容器 CID 摘要，避免自引用。最终外置 `build-manifest.json` 再绑定 `input_binding`、实际 ELF、link map / trace、许可证 / 来源材料与实际构建结果；接受记录独立引用其原字节摘要，不在生成 manifest 中伪填 accepted。源码变更、正文换行变更、工具 / flags 或 profile 变化均需重生成、重建、重核与登记，旧制品不原地替换。

## 交付：一个只读 runtime 目录

候选交付根为新建、已解析的仓库任务专用目录 `.tmp/linux-channel-delivery/<实际制品摘要>/`，不在本批创建。只读挂载的 `runtime/` **仅含普通文件 `axiom-linux-channel-init`**，文件候选 mode 0555 / 目录 0555；其余 `inputs.json`、build manifest、link map / 日志、LICENSE / 第三方归属及接受材料置于未挂载的 `records/`，不进入容器可读面。只改变本任务副本的模式，不 chmod 工具链 / 仓库或全局路径。ELF 不嵌入用户程序，不扩展本仓许可证；静态运行时组成与必要归属仍逐项接受。

将该目录显式 bind 到候选镜像既有空目录 `/mnt`，readonly、rprivate、禁止递归子挂载（bind-recursive=disabled），不使用 -v / source 自动创建，不覆盖原 BusyBox / loader 或挂整仓库 / SDK。entrypoint 固定 `/mnt/axiom-linux-channel-init`；执行参数只有 `--run-id` 和 64 位小写 hex 的公开关联标识，不能传正文、路径、资源覆盖、用户命令或环境。该标识不是 secret、授权令牌或来源认证。

Mac 在 create 前检查 resolved source 祖先、无 symlink / 未知条目、单个普通文件、大小 / 模式 / 摘要与接受记录；只接受可与该 daemon 的共享源关联的路径，拒绝路径自动翻译的未知情况。create 后按精确 CID 读回 image index / 所选平台、entrypoint / args、mount source / destination / 只读 / propagation、用户 / 无附加组 / 无 cap / namespace / 内存和日志配置，不符不启动。`/mnt` 的存在来自留存 rootfs，不是本机 bind 可读 / 可执行 / noexec / userns 映射的运行资格。

readonly bind 只能限制诊断者写入，不能阻止 Mac 同用户的写别名 / 替换。**独占无并行写入与可信宿主 / daemon 是这次有限诊断的执行前置**，需要明确接受与实际关联；chmod、前后摘要相同或持有 Mac FD 不等于 Linux 不可变挂载认证，不能据此取得 G0 冻结 / quota 资格。不能接受这一范围时保持不交付，不自动改派生镜像、提权或更改宿主权限。清理仍只针对已确认停止、身份一致的单个 CID；不删原镜像、build / delivery 材料或全局卷，不 prune。此方案不承担 daemon 失联时的独立回收。

## 报告导出：PID 1 独占外部 stdout

现有 run 让子进程继承 stdout / stderr，不能简单在它返回后追加 JSON。未来入口须先核定身份并关闭未知继承 FD，再创建专用 stdin / stdout / stderr pipe：子 stdin 为已关闭写端的 EOF，子 stdout / stderr 仅接内部 pipe；PID 1 独占外部 FD1。子尾段通过现有 typed FD / raw dup 边界重映射 0/1/2，关闭其他句柄；其 `AXCI` 只作为内部 stderr 的原字节诊断，不是顶层 Final。未来必须重构现有 close_range 的时序，不能让 run 再关闭这些已拥有的 pipe。

父侧使用现有 ppoll / BOOTTIME / wait / signal 边界，固定小缓冲、有界待写帧、非阻塞读写，统一驱动采集、取消、主退出、回收与导出。只写了一半的帧必须从真实 offset 继续；不能丢弃半帧再追加 Final。不得增加线程、后台传输服务、磁盘报告文件、额外 socket 或修改 solver 旧 wire。外部 stderr 仅为 ≤64 KiB 的非权威紧急诊断，不作为机器报告入口，不输出环境或未筛选宿主内容。

拟议私有报告 v0.1 的唯一外部流为以下二进制封装，尚未实现或冻结为公共格式：

| 层 | 精确候选 |
| --- | --- |
| Header（20 bytes） | magic ASCII `AXCHN001`（8）；BE u32 sequence；u8 kind；u8 stream；BE u16 reserved=0；BE u32 payload_bytes |
| 顺序 | sequence 从 0 连续递增、不回绕；kind=1 Start 恰一次且最先，2 Chunk 零或多次，3 Final 恰一次且最后；最多 8,192 帧；Final 后任何字节拒绝 |
| stream | Start / Final 为 0；Chunk 的 1=collector stdout、2=collector stderr；未知 kind / stream / reserved 拒绝；Chunk payload 为 1..4,096 原字节，不作文本重解释 |
| 控制 payload | Start ≤4 KiB，Final ≤32 KiB；受界规范 ASCII JSON，固定字段顺序、固定 enum / 操作名（≤64 bytes）、十进制整数 / bool / null / 有界列表；无浮点、转义、未知 / 重复键、BOM 或尾随空白。采集数据只在 Chunk，不能注入控制字段 |
| 字节预算 | 外部完整 stdout 流仍 ≤2 MiB，包含所有 header / control / 两类 Chunk；collector stdout ≤1.5 MiB、stderr ≤64 KiB。8,192×20 + 4 KiB + 32 KiB + 1.5 MiB + 64 KiB = 1,839,104 bytes，低于原 2 MiB；为控制帧预留额度，不把 framing 作为增限理由 |

Start 必须绑定 `format=radishaxiom-private-linux-channel-report`、`version=0.1`、run_id、input_binding、内嵌正文 SHA256 / profile 与固定预算；Mac 独立按已登记 build manifest、具体 CID / 配置及预期 run_id 比对。Start 不嵌最终 ELF 自身摘要，不声称独立认证 image / 许可 / namespace。只有上述关联完整才能解释后续观察；不是正式 Evidence 或 solver 结果。

本协议及 inputs / build manifest 的摘要字段统一为 `sha256:` 加 64 位小写 hex，run_id 则是无前缀的 64 位小写 hex；不得在收到数据后隐式补前缀、大小写或换行。原本机候选观察 JSON 使用其独立版本的无前缀摘要，不直接充当本协议输入。

Final 保留：同一绑定；首个原因 / child_pid / main_exit；全部有界 exits / signals / errors（各≤64）、clone_attempted、no_children、observations_overflowed；两类流的已见长度、实际导出前缀长度 / SHA256、prefix_only / EOF；固定绝对截止 / 最后 BOOTTIME；采集 / 传输失败和 **selected_exit_code**。主退出含 pid / uid / CLD code / status，不把 signal 改写成正常退出。只对已导出的完整 Chunk 序列摘要，未知完整长度则记录下界 / 未完成，不伪造丢失尾部的摘要。仅 ECHILD 赋值 no_children，EOF 另行记录，二者不可互代。

超额 / 解析 / 取消 / IO 错误先停止工作、保留首错并进入收束；保存实际前缀与短写 / errno，不能重置流、重新发送 Start 或以空数组冒充完整。Final 不含 `pid1_exited=true`：它是在退出前发出的选择和观察，不可能证明随后已经 raw exit。Mac 还须看到完整流 / EOF、相符的 runtime 退出、配置与精确 CID 清理观察；客户端退出或代码 0 不能代替这些事实。缺 / 截断 / 篡改 / 多份 Final、退出不符或未回收均是失败 / 未取得，不升级资格。

## 最终入口与不延长期限的退出

拟议 leaf main 只做精确目标路由，库内入口保持不返回：

1. Rust / CRT 到达自有入口后，**首个 raw BOOTTIME** 建立唯一 t0，再做参数检查、预算 / 预分配、正文 / input_binding、身份与 pipe 准备。修改现有 Report::new 先于首时钟的顺序，不在进入 run 时重新取新预算。CRT / std 的 main 前初始化不在这一 20 s 内，Mac 原批次单调 90 s 必须覆盖它；两种时钟不直接相减。
2. 从同一 t0 派生 work=t0+18 s、cleanup=t0+19.8 s、final=t0+20 s；末 200 ms 在原 2 s 收束内为 Final / 退出预留，不延长内部或 Mac 期限。这是候选安排，不是保证 200 ms 足够的实测结论。
3. run 改为接收同一受界预算 / 已拥有 IO / 只读绑定，所有错误走同一收束；仍仅一次 fixed clone(SIGCHLD)，无启动重试、数字 PID kill、资源覆盖或错误后的新子进程。最后只在有剩余期限且前序帧完整时导出 Final。
4. 全部流与终端帧均完整时使用原 Report 选择的代码；最终写失败、EOF / 前缀 / 绑定不完整或时钟 / 观察超额不得退出 0。保留原原因及主退出，所选退出码按诊断优先级失败关闭（125；已观察取消 / 工作截止仍保留其对应状态），不能把传输失败掩盖成采集成功。
5. 无论 Final 是否可写，最终直接复用原 `Linux::exit_group(code) -> !`；不返回 main，不执行标准库退出 / Drop、atexit、flush 或新增清理循环。仅未确认的后代不再隐写为 reap，PID namespace teardown 和 daemon wait / remove 另行观察；raw exit 尝试也不等于已取得退出确认。

不能只用 `panic=abort` 声称 PID 1 必然终止。拟议 binary 私有 [panic hook](https://doc.rust-lang.org/std/panic/fn.set_hook.html) 不格式化、不锁日志或尝试报告，只 raw exit_group(125)；零分配的失败路径不做 IO。另在**该专用目标 binary**设置最小 [GlobalAlloc](https://doc.rust-lang.org/std/alloc/trait.GlobalAlloc.html) 包装，正常调用已有 std System 的 alloc / alloc_zeroed / realloc / dealloc，分配返回 null 时立即 raw exit_group(125)，不进入默认 OOM 输出 / abort 路径、不重试分配。它不替换 allocator 算法，不影响 workspace 其他 binary / 库；其 unsafe 转发、零分配退出、启动期可达性和目标 std / System 真实行为必须专门审阅 / 合成故障注入并纳入链接闭包，未完成不接真实入口。main 前信号 / 栈溢出 / 同步故障仍须按精确 std / CRT 输入核查，不凭 hook 宣称所有故障可捕获；缺 Final 必须由 Mac 报为未完成并执行其有界精确清理。当前 std API 网页不是本机精确 1.97.1 源码或接受记录。

## 实施顺序、验收与停止线

文件落点沿现有包 / 支持目录设置；L1 的已实现部分见专题，L2 / 最终构建部分仍为候选，不另开 runner 或第二套配置入口：

| 拟议文件 | 边界 |
| --- | --- |
| `crates/solver-bootstrap-linux/src/channel_profile.rs` | 唯一类型化预算、profile、include_bytes 正文与固定构建输入 |
| 同目录 `channel_report.rs` | 有界报告值 / codec，供脚本后端及入口共同使用，不访问 OS |
| 同目录 `channel_entry.rs` | 持有原生 backend 的私有入口、IO / 期限驱动、终端导出 / raw exit，保持 Kernel 不公开 |
| `src/bin/linux_channel_init.rs`（相对同包） | leaf main 与仅此 binary 的 `#[global_allocator]` 绑定；不得将该全局属性加到 lib.rs 或通用库静态初始化中，失败路径实现经受 feature / target 约束的隐藏桥接复用 |
| 同包 `examples/export_linux_channel_inputs.rs` | 显式离线纯导出，不导出执行能力、不自动下载 / 构建 Linux；输出新任务目录 |
| `scripts/check-linux-channel-inputs.py`、`scripts/cvc5-build-support/channel_report.py` | 独立输入复核与 Mac 纯流解析；由既定 inspect_linux_host.py 编排调用，不另设通用执行 CLI |

| 切片 | 必需出口 / 限定范围 |
| --- | --- |
| L1：绑定与报告纯组件 | 真实采集正文审阅、单一 profile / 源码绑定生成与独立复核；Header / Start / Chunk / Final codec 与预算；全截断、未知 / 重复 / 尾随、序号、绑定漂移与 prefix / EOF / ECHILD 区分。只用合成输入，不启动采集 shell |
| L2：入口接线源码 | 内部 pipe / FD 所有权、首 t0 与 200 ms 预留、非阻塞 IO / 回收统一循环、raw 退出 / panic / allocator 失败路径；全目标宿主检查及 scripted partial write / EAGAIN / EINTR / EPIPE / 取消 / 并发退出 / PID 复用 / 报告截断 / 分配失败。不得换 backend 或放宽现有检查 |
| L3：有限工具输入与构建审阅 | 单独列明 Rust 1.97.1 Linux musl target 组件的精确取得 / 安装目标、来源 / 许可、大小 / 时间及清理方式，再获得授权。先形成完整输入与构建包装器计划，随后分别授权安装与一次交叉构建；不把本页当安装指令 |
| L4：实际制品离线验收 | 构建 / 链接 / ELF / 来源 / 许可和正文绑定独立核对，登记实际制品及单文件 runtime 目录；不创建镜像 / 容器，不在 Mac / Linux / 模拟器执行产物。静态通过仍不是运行资格 |
| L5：执行前收口 | 精确宿主权限 / proc / seccomp、Mac 共享源 / 无写别名、限额和单 CID 配置 / 清理范围闭合后，才提交真实一次诊断的完整参数与许可范围。缺任一前置不 create / start，不提权 / 加依赖 / 换镜像补救 |

本方案核定批次只做设计和既有工具只读观察；后续 L1 授权及实现见上方接续与专题，不授权 L2 或任何目标安装 / 构建 / 交付执行。原 C1 / E0 / E4、G0 / A1–A10、镜像 / 许可接受和 readiness 不变；后续授权按明确动作与目标分别处理，不因方案写成具体路径就自动生效。
