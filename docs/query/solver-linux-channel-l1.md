# 诊断通道 L1：采集正文、离线输入与报告纯组件

日期：2026-11-01。状态：**L1 已实现并完成本机有限验证；build_ready=false / execution_ready=false**。用途：供实施者和审阅者理解[交付方案](solver-linux-channel-build-and-delivery-plan.md)的已实现部分与私有 v0.1 字节契约；实际命令、失败与观察见[本批记录](../records/2026-11-01-linux-channel-l1-review.md)。本文不接受镜像、工具 / 许可或真实运行资格，不授权采集 / Linux 执行；后续入口接线见 [L2](solver-linux-channel-l2.md)，历史 L1 验证数与材料不改写。当前 [L3](solver-linux-channel-l3.md)已提交为 `bb9d963`：保留的 v0.1 为 53 源，另有 v0.2 纯生成 / 独立复核与 native 捕获；本页 v0.1 契约不充作 native 构建输入。

## 已实现边界

| 落点 | 责任 |
| --- | --- |
| [inspect_linux_host.sh](../../scripts/cvc5-build-support/inspect_linux_host.sh) | 固定只读采集正文，无参数、外部脚本加载、写盘、网络、目录递归或重试；仅静态 / 合成审阅，尚未运行 |
| [channel_profile.rs](../../crates/solver-bootstrap-linux/src/channel_profile.rs) | 唯一类型化预算 / profile、内嵌正文原字节和读白名单；L1 仅归位同值常量；后续 L2 统一截止 / 控制流 |
| [channel_inputs.rs](../../crates/solver-bootstrap-linux/src/channel_inputs.rs) / [显式宿主导出](../../crates/solver-bootstrap-linux/examples/export_linux_channel_inputs.rs) | 编译期捕获固定源家族（L1 为 45 份、L2 为 50 份；当前 L3 为 53 份），导出新任务目录；不创建原生 binary 或调用 Kernel |
| [channel_report.rs](../../crates/solver-bootstrap-linux/src/channel_report.rs) / 私有 channel_json | 类型化控制值、有界 canonical ASCII JSON、Encoder / 增量 Decoder；无 OS / 文件 / 进程访问 |
| [check-linux-channel-inputs.py](../../scripts/check-linux-channel-inputs.py) / [channel_report.py](../../scripts/cvc5-build-support/channel_report.py) | 独立标准库输入复核与增量流解析，不从 Rust 导出推导固定预算，不产生资格或执行确认 |

这些 public 纯模块只为私有包的导出 / 测试提供数据接口；NativeKernel 和任意 syscall / CStr 执行能力仍不公开。L1 未改 Cargo；L2 新增默认关闭的专用 leaf target / feature / profile 与隐藏固定入口，未改依赖、lockfile、原 solver wire、Accepted ADR 或生产格式。

## 采集正文

正文原字节须为 UTF-8、无 BOM / NUL / CR、以 LF 结束、1..32,768 bytes；编译以 include_bytes 捕获，摘要包括末尾 LF、不包括未来 CString NUL，不 trim 或从运行参数载入。本批正文为 9,717 bytes，实际摘要见记录；后续任何改动都会改变输入绑定，旧导出不能按新源码通过。

正文仅调用固定镜像 BusyBox 的 ash / awk / head / od / stat / readlink / uname 及 shell 内建。已有固定配方配置包含这些 applet，但配置声明不是本机 applet 行为验收。初始环境、启动器 / 镜像来源、只读挂载、权限与 L2 接线的实际运行资格仍是前置。

- 检查 nofile=64，自身 status 中四 UID / GID、空附加组、NNP 与全部 cap 为零；读取自身 mountinfo、uid_map / gid_map、cgroup 和六种 namespace 链接，uname 不含 hostname。
- 只读取既定三份宿主 proc 绑定及 cgroup 根 controllers / subtree_control；type / events / memory / CPU / PID 限值只读取从自身 cgroup 行严格解析的非根路径，不读兄弟 / 其他工作负载内容、不枚举 cgroup。禁止 `..`、空段、非白名单字符与路径别名；要求 procfs / cgroup2 的文件系统身份及规定只读 / 私有绑定形状。
- 每个文件最多 head(cap+1)，上游原字节经 od 转十进制后送到内嵌纯 AWK 过滤器。过滤器按字节计量、拒绝 NUL / CR / 非 ASCII / 未结束 LF / 超额与非法格式，避免不同 awk 的 NUL 文本语义掩盖输入；终端控制字节不得出现在数据内冒充完整输入。
- 输出只有 `AXHC01` 制表符记录及固定字段。mountinfo 仅保留指定挂载的 ID / parent / dev / fs / 安全 root / ro；运行制品的任意 root 以 redacted 表示，绝不输出 source、super options、无关工作负载路径或原始失败行。未知格式、重复必要挂载、权限 / 读取 / 校验失败退出 125，只报固定错误类别。
- 空 controllers / subtree_control 列表必须显式输出 empty；不把空观察变成缺失或假零。内存 / swap / PID / CPU、domain、populated / frozen 与事件读取是观测及拒绝依据，不是硬资源生效证明。内核字段变化或未支持挂载形式会拒绝，不自动扩大白名单。

全局内部 18 s / 20 s 控制已在 L2 PID 1 源码接通，仍未经 Linux 执行；正文没有独立守护进程或额外期限。只读路径 / stat / canonical 检查不是跨进程原子快照、无写别名或宿主来源认证；实际输入的内核 / daemon / Mac 关联仍待执行前收口。不得把合成过滤通过当作真实 Linux 读取成功。

## 离线输入 v0.1

导出目录固定三个文件：`inputs.json`、与内嵌原字节相同的 `collector.sh`、明确命名的 `synthetic-report.bin`。输出目录及各文件必须新建，不覆盖旧成功 / 失败材料；不自动执行正文。inputs 为无空白 / 尾随的 canonical ASCII JSON，固定键序：

`format, version, scope, generator, target, profile, budgets, collector, collector_reads, source_set_digest, sources, build_inputs, native_build, build_ready, execution_ready`。

format 为 `radishaxiom-private-linux-channel-inputs`，version 为 `0.1`，**scope 为 offline-source-binding-only**。build_inputs 必须 null、native_build 为 not-accepted、两个 readiness 均 false。它只实现 L1 的源绑定，尚不含目标 std / 工具 / flags 的完整构建输入；不能直接充作交付方案中的最终构建 inputs。L3 已另行实现显式 v0.2 / scope 迁移并在 native 拒绝旧版；尚无真实完整 root，不能原地改本页布尔值升级。

sources 是固定有序源清单，行键为 path / bytes / digest：三包 src 的完整 .rs 家族、根 Cargo / pin、三包 Cargo、导出 example、正文和对应 Python 检查 / 测试入口。编译期原字节形成各行摘要及 source_set_digest；自身源码可以参与，生成输出自身与最终 ELF 不参与。复核器按当前仓库独立枚举同一源家族、拒绝 symlink / 缺失 / 新增 / 重排 / 大小 / 原字节变化，复用现有有界文件与 canonical JSON 检查，不改旧 checker。

input_binding 是整个 inputs 原字节的 SHA256；摘要统一为 `sha256:` + 64 位小写 hex。来源匹配不认证作者、工具、构建或执行。导出 example 中 run_id=07 重复 32 次、PID=42、payload=synthetic-only LF 都是合成固定值；sample 不得登记为 runtime 观察。独立复核的 `--synthetic` 只验证这一明确样本和协议拒绝，不接受任意实际运行来源。

## 私有报告 v0.1

沿交付方案的 20-byte Header、Start / Chunk / Final 顺序、stream 编号和原 2 MiB 总流额度实现；最多 8,192 帧，Chunk 1..4,096 bytes，Start 4 KiB、Final 32 KiB，stdout 数据 1.5 MiB、stderr 数据 64 KiB。发送数据前预留 Final 最大额度。Decoder 在 Header 后先拒绝超额长度，以最多一帧缓冲增量处理；错误后不能重新开始或补写出成功。

控制值无转义 / 非 ASCII / 浮点 / 负数 / 重复 / 未知字段、非规范整数或尾随字节；解析深度≤16、数组≤64、对象≤32。Start 固定键序 `format,version,binding,profile,budgets`；binding 固定为 `run_id,input_binding,collector_digest`。所有期望绑定由调用方事先提供，不能从收到的 Start 反向建立期望。

Final 固定键序为：

`binding,cause,child_pid,main_exit,exits,signals,errors,clone_attempted,no_children,observations_overflowed,stdout,stderr,clock,capture_failed,transport_failed,selected_exit_code`。

- cause 为 null 或 kind / signal / error；kind 仅 kernel / deadline / cancelled / signal / orphan / budget / capture / transport。错误保留受界 operation、kind 和 detail；不存任意异常消息、路径或输入行。
- main_exit / exits 保留 pid / uid / CLD code / status，signals 保留 pid / error；各事件数组≤64。真实主退出须对应退出列表第一次同 PID 事件；无 cause 时最多一次退出，防止同数值 PID 复用隐藏孤儿。创建、主退出和 ECHILD 声明相互约束；L2 补充：缺主退出的 ECHILD 只有同时保留 cause / 非空 errors 才能导出为失败，不能选择成功。协议校验并不认证声明是真实 syscall。
- stdout / stderr 固定 seen_bytes / exported_bytes / sha256 / prefix_only / eof。已导出长度与增量 Chunk 摘要必须匹配；前缀和 EOF / no_children 各自独立，不填补未知尾部。clock 固定 first / work / cleanup / final / last ns，拒绝回退、溢出和截止漂移。
- selected_exit_code 按类型化事实重算：deadline 124，已观察取消 128+signal，其他失败 / 不完整 125；完整无错时保留主退出。非法 signal / status 返回拒绝，不以整数溢出 panic 逃离纯组件。传输完整并不等于进程已退出，Python结果始终 runtime_exit_confirmed=false / qualification=not-established。

Encoder / Decoder 继续是纯协议组件；[L2](solver-linux-channel-l2.md)已将其接到单一脚本可测的 pipe / BOOTTIME / 回收 / capture / 最终 raw exit 源码，并设置 leaf panic / allocator 出口，但没有执行真实 Linux 路径。Mac 编排、Linux target 组件、制品构建 / 许可、镜像和实际 OS 验收继续分别处理。
