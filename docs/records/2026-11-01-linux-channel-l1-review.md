# 2026-11-01：诊断通道 L1 源绑定与报告纯组件验证

日期：2026-11-01（Asia/Shanghai）。状态：**L1 已完成本机有限验收；非 Linux 执行 / 工具或 OS 资格**。用途：留存本批提交、实施、静态 / 合成验证及未覆盖边界；私有格式和实现职责见[L1 专题](../query/solver-linux-channel-l1.md)，实施接续见[当前状态](../status/current.md)。

## 起点与范围

项目所有者要求先提交构建 / 交付方案，再推进 L1 采集正文、输入绑定与报告纯组件的实现 / 静态验证，暂不安装目标组件、构建 Linux 制品或创建 / 启动环境。开始时 `dev` 相对本地 `origin/dev` 领先 5 笔，暂存区为空，恰为前批六文件；复核后精确提交为 **`2e5da3a` — `docs(cvc5): 核定诊断启动器目标构建与交付方案`**。提交后工作区干净、领先 6 笔；没有 fetch / push、身份变更、AI 署名或历史改写。

本批实现仅新增固定采集文本、纯绑定 / 报告组件和测试 / 独立复核路径。新增模块的数据 API 不公开 NativeKernel / syscall / 原生执行能力；原 channel_init 只将同值常量改为引用单一 profile，未接入新正文、IO、预算细分或终端出口。没有修改 Cargo / lockfile、第三方依赖、Accepted ADR、既有 W/S / solver wire / fixture 或 solver 资源额度。

实际仅执行已有 Darwin 工具链的格式、lint、host 测试 / 纯导出、Python 标准库检查和 `/bin/sh -n`；合成过滤使用**从实际正文提取的纯 AWK 程序**，输入全为自有构造的十进制字节。没有运行整个采集 shell、镜像 BusyBox / loader、真实 proc / cgroup 读取、Linux syscall / ELF、target 组件取得 / 安装、Linux 编译 / 链接、镜像 / 容器 / machine / 服务、solver 或远程动作。

## 具体实现与真实观察

- 正文覆盖既定只读 / 身份 / 限值白名单，原字节 9,717 bytes，SHA256 `e1f884bc7762c5cd64a456b93785860810cd16ba21bb1a67a9bb5607a71f54ae`。使用 head(cap+1) 与 od 字节流，使内嵌 AWK 能严格拒绝 NUL / 截断 LF / 超额；mountinfo 只输出受限字段，测试中的 private path / source / super-option credential 不出现在输出。空 controller 列表显式报告 empty，未知输入 / 读取错误不补零或改走别处。
- 内嵌原字节、profile / 预算、23 条受界读取声明及 45 份编译捕获源形成离线输入。独立 checker 另枚举源家族并核对当前字节，严格拒绝路径 / 数值 / 来源 / scope 漂移；没有把 source matching 当成 publisher / 工具接受。
- 纯 Rust Encoder / 增量 Decoder 与独立 Python 解析器落实 Header / Start / Chunk / Final、规范 JSON、外部期望绑定、序号 / 单流 / 总量 / 控制预留、真实退出声明、前缀 / EOF / ECHILD 区分及失败退出码校验。不会从解析出 Final 推断 runtime 已退出或许可 / 资格成立。
- 实际显式宿主导出到新目录 `.tmp/linux-channel-l1-2026-11-01-reviewed/`，含 inputs.json、collector.sh、synthetic-report.bin；所有较早导出及拒绝材料仍保留，没有覆盖旧输出。当前 input_binding 为 `sha256:422301097d4bd0fffcb1f5e8f148ffecca44ebd749f3bfe325378d2dbf262d70`。工具输入为 null、native_build=not-accepted、readiness 均 false；这不是最终 target build inputs。
- [机器可读验证记录](cvc5-control-plane-2026-11-01/channel-l1-offline-validation.json)保存实际输入 / 入口摘要及互操作范围。Rust 产生的 1,747-byte **合成**样本经独立 Python 消费，1,747 个截断前缀全部拒绝，7 种分块方式均还原唯一 synthetic-only LF 数据。run_id=07×32 / PID=42 不来自 runtime，runtime_exit_confirmed 始终 false。

对白名单 / 字段含义，只沿既有固定 BusyBox 配方配置及必要官方 [cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) / [mountinfo](https://man7.org/linux/man-pages/man5/proc_pid_mountinfo.5.html) 参考核对；既有配置声明包含 ash / awk / head / od / stat / readlink / uname，不是精确镜像 applet 的真实运行验证。不取得新源码归档、安装包或依赖，不重复前批工具链取证；Mac awk 合成结果不认证 BusyBox awk 行为。

## 已保留的失败与修正

1. 首轮 Python 源绑定夹具经过 macOS 的临时目录 symlink，被既有正式读取器拒绝。只修正本任务夹具为 resolved 私有目录，未放宽 symlink 检查；伪造源和 symlink 拒绝负例继续通过。
2. Clippy 报测试中的可合并 if；调整该测试控制流后原 `-D warnings` 通过，未加 allow 或降级检查。
3. 审阅发现报告可以用重复的同数值主 PID 事件隐藏额外回收。先加入回归并观察失败，再收紧“无 cause 最多一个退出”；Python 独立路径同样拒绝，实际 PID 复用 / 孤儿仍保留为失败事件而非归并成功。
4. 空 controllers / subtree_control 原来没有输出记录；先用合成回归得到失败，再改为显式 empty 并拒绝多行列表。此时对旧真实导出复核，实际返回 `collector-binding` / 退出 1；保留旧目录，在新目录重新导出，没有改摘要迁就旧正文。
5. 非法类型化 signal=255 触发纯组件整数溢出；先用回归观察 panic，再将非法 signal / status 的选择限制为失败代码且编码拒绝，保留原输入错误，未把无效值包装成正常退出。

这些失败 / 修正均发生在本批开发状态，未修改历史已提交记录或冻结制品；最终复核只对应 reviewed 目录和当前源码。

## 实际验证

使用已有 `1.97.1-aarch64-apple-darwin` 工具链，最终实际执行：

- `cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-solver-bootstrap-linux --all-targets --locked --offline`：87 项通过、无忽略项，其中本批 18 项 / 既有 69 项；example 测试 harness 为 0 项，不计入新增测试。
- 同一工具链 `fmt --all --check` 与本包 `clippy --all-targets --all-features --locked --offline -- -D warnings`：通过。
- `python3.14 -O scripts/test-linux-channel.py`：15 项通过，包含语法检查、真实内嵌纯 AWK 的合成正负例、协议与 source / scope 篡改拒绝。`-O` 没有移除正式入口的 require 检查。
- `cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-solver-bootstrap-linux --example export_linux_channel_inputs --locked --offline -- .tmp/linux-channel-l1-2026-11-01-reviewed`：成功生成纯离线导出；没有 Linux target 或 collector 调用。
- `python3.14 scripts/check-linux-channel-inputs.py --synthetic .tmp/linux-channel-l1-2026-11-01-reviewed`：45 份源 / 原字节绑定通过；Rust 样本的 1,747 个截断前缀拒绝和 7 种分块互操作通过，runtime_exit_confirmed / readiness 均 false。
- `python3.14 scripts/check-repo.py`：完整仓库检查通过，2,923 文件；`git diff --check` 通过。局部核对通过：本批 19 路径、23 处差异行中的本地引用 / 锚点、UTF-8 / LF / 无尾随空格 / 普通文件 `0644`、源 / 方法 / 实际导出摘要与机器记录一致、暂存区为空。

中间轮次不累加为一次测试计数。未扩大到无变化的完整 workspace / 其他平台回归；原包内设置、B 尾段、W/S 监督与 syscall 的 69 项既有测试已在同一次本机组件回归中覆盖。

没有 Linux 目标 std / CRT / 汇编 / 链接验证，也未运行 collector、真实 pipe / BOOTTIME / 内存 / raw exit、Mac adapter、solver、CI 或独立语义 checker。L2 必须继续接单一 t0、内部 pipe / FD、非阻塞传输 / 回收、200 ms 预留、panic / allocator 和最终 raw exit；不能直接把现有 run 加采集脚本当独占报告入口。本批的常量归位未改变旧 run 的 18 / 20 s 行为。

build_ready / execution_ready、镜像 / 许可、C1 / E0 / E4、G0 / A1–A10 实际资格不升级。没有后台服务、Linux 环境或卷需要清理；Cargo 缓存与任务专用导出 / 失败材料保留。本批新改动不在 `2e5da3a` 中，未自动提交或推送。
