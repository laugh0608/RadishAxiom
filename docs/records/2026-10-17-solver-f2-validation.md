# F2 原生源码与 D3 C0 输入选择验收

日期：2026-10-17（Asia/Shanghai）。用途：记录本批提交、源码审阅、本机脚本后端检查、兼容性与未覆盖边界；读者为项目所有者、实施者与后续资格验收者。本文不接受 Linux 制品、cvc5、宿主或真实尝试，不替代正式专题。

## 授权与基线

项目所有者要求先提交 F1 实现、验收材料与 D3 构建候选方案，再推进 F2 原生实现和 D3 C0 精确输入选择；主代理主持设计与验收，具体实现委派 `gpt-6.1-sol / high`。原容量、旧字节和资源限值保持；不下载或安装依赖、不构建 Linux 制品或镜像、不运行探针或 solver、不修改系统配置、不 push。

启动时 `dev` 位于 `f2ad466`、相对本地 `origin/dev` ahead 3；工作树为前批 F1 / D3 的 43 条精确路径。复核后提交为 **`1a7ff38` — `feat(solver): 实现 F1 共享监督与启动声明`**（Git 识别迁移后为 42 文件），提交后工作树干净，ahead 4。本批 F2 / C0 以该提交为基线，后续修改保留未提交。没有刷新远端。

## 源码交付与边界

- 私有 `solver-bootstrap-linux` 实现明确 FD 所有权、固定 ABI / 类型化 syscall、受目标限制的 raw backend、准备 / 监督驱动与独立 B 尾段；生产依赖只有既有 digest / supervision core 的 path 依赖，host 仅为测试依赖。Cargo.lock 只增加这个本地 package，无外部包版本改变。
- [原生边界](../query/solver-bootstrap-native-boundary.md)记录固定 UAPI 来源、布局、unsafe 前提、错误、信号与 child 尾段。真实 backend 只在 Linux AArch64 LE LP64 存在；Darwin 检查同一类型化实现与显式脚本后端。没有 `main`、公开执行入口、libc fallback 或 accepted 占位配置。
- [监督实现](../query/solver-bootstrap-native-supervisor.md)记录 S0–S7、FD / deadline / 控制与真实读取结构。真实本地读取类型不接受 Synthetic 对象；结构本身合法不等于已取得任何真实观察。预期 boot / namespace / mountinfo 属于待实现的受信任实例读回，不能预嵌为静态 E4 模板或从 READY 自我认证。
- 新 `AXBCMD01` 离线输入复用原十二项参数常量，原 `SolverRequest::argument_tokens()` 和参数 bytes 不变；独立清单与 F1 四文件格式分开。native 只消费构建绑定输入，不从 Start / ARM 接收 argv 或资源覆盖。原 F1 输入仍明确 `outer_setup_policy=not-established`、`native_build=not-accepted`。
- 共享 core 新增严格的 cgroup 值解析入口，让退出过渡检查前先验证全部配置 / 事件，再判断成员；旧 `ParsedCgroup::parse` 正文及错误次序不变。只有同一唯一 child 的明确退出变化能触发一次额外读取，失败和首次原始读取均保留。

## 设计审阅中修复的边界

1. raw `ppoll` 的 timespec 是可写输入输出，不能借用不可变 Rust 对象；现以独占缓冲传递，并用脚本实际写回检查。
2. listener 交付 socket 的 `POLLIN|POLLHUP` 必须先接收队列内唯一消息；首次 CONTINUE 后，最后过滤线程退出 / reap 导致的 listener HUP 与第二通知分开。pidfd 回收后移出轮询，不用 readable 冒充 reap。
3. QueryEnd 后任何完整或部分控制字节均拒绝；控制读取 EINTR 不代表已确认 quiet。截止、控制丢失和额外通知不能让位于正常输出或最终成功。
4. child 参数 / filter / 重映射来源在 READY 前冻结，成功或失败路径都有唯一 FD 清理归属；先保存真实 child / pidfd 再做可能失败的映射 / 关闭，不重试 clone 或 CONTINUE。关闭错误与原始失败分别保留。
5. cgroup 配置漂移、frozen / populated、严格数字、所有事件与计数回退先于退出过渡；不得通过重读覆盖异常。原始逐文件字节、完成标志、读区间及前后 child 事实有界留存。
6. setup 新增的 `getdents64`、`F_DUPFD_CLOEXEC` 与 `getppid` 明确列入未来外层能力要求；W/S final filter 不扩展。目标 std / musl / CRT / allocator 的实际能力仍未闭合。

## D3 C0 的实际结果

[C0 专题](../query/solver-cvc5-c0-input-selection.md)及[输入记录](solver-cvc5-c0-2026-10-17/input-selection.json)固定 cvc5 完整 commit 与四项依赖配方 / tag / commit，实际原包摘要仍为 null。本轮重核 29 份既有留存观察。Debian 12 bookworm / 20230612T000000Z / arm64 只作为单一 SDK 来源候选；16 组包角色的版本、文件、传递依赖、许可与配置 / patch 仍 unresolved。

固定快照 Release 元数据的只读请求受沙盒网络权限阻断；后续元数据请求在等待批准 1062 秒后由主代理中断收口，没有成功执行输出，目标目录复核不存在。没有重试该路径或取得依赖包。当前 Debian 页面不作为历史快照版本证据。检查结果是 `draft_consistent=true / build_ready=false`，11 项负例通过；生成器和检查器共享草案数据，不是独立来源认证。C0 **未闭合**，本批不进入 C1–C5。

## 验证与结果

最终 workspace 全目标测试 **441 项通过、0 项失败、1 项按原设置忽略**，其中原生脚本后端 41 项；文档测试另有 3 项通过。最终格式检查、workspace 全目标 / 全 feature Clippy（`-D warnings`）均通过。[机器结果](solver-f2-2026-10-17/offline-results.json)记录实际计数、独立复核输出、32 份改动源码 / 脚本输入及本地日志摘要；它只记录本机有限检查，不是 Axiom Evidence 或原生资格。已完成的独立核对如下：

- 对照提交 `1a7ff38` 的 2,052 份既有 crates / contracts / Cargo / toolchain 文件，2,047 份字节不变。五个变化仅为 workspace / lock 中本地 package、IR 常量可见性、host 模块登记和 core 新 cgroup 值入口；既有契约、旧 query / P4 与资源定义未改。
- 新导出的 13 份 E3 材料与前批逐字节相同，包括原容量 wrong-add query（962,642 bytes / 501 自由符号）、request / response / candidate / world / replay、双向 wire、两流与 W/S cBPF。原容量合成闭环仍接原 P4-B，未运行 solver。
- F1 的 inputs.json、worker.cbpf.bin、supervisor.cbpf.bin 三份数据与前批相同；manifest 因真实源码 / Cargo 输入变化而重新导出，旧 manifest 不被改写。独立核对 22 份当前源码及 3,176 / 1,450 个 W/S 有限策略案例。
- AXBCMD01 为 251 bytes / 十二参数；新独立复核器核对 10 份编译捕获来源、严格解码与固定参数，5 项正负例通过。既有 F1 复核器 9 项及 E3 复核器 6 项也通过。
- 初次格式检查在并行收尾的一处空格格式失败；保留 `.tmp/solver-f2-2026-10-17/fmt.log`。统一格式后最终检查通过，未放宽 lint 或检查入口。

主要复跑入口（输出目录必须尚不存在）：

```bash
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline
cargo +1.97.1-aarch64-apple-darwin test --workspace --doc --locked --offline
cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-solver-diagnostic-host --example solver_bootstrap_manifest --locked --offline -- .tmp/solver-f2-manifest-new
cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-solver-diagnostic-host --example solver_bootstrap_command --locked --offline -- .tmp/solver-f2-command-new
cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-solver-diagnostic-host --example export_e3_offline --locked --offline -- .tmp/solver-f2-e3-new
python3 scripts/check-solver-bootstrap-inputs.py .tmp/solver-f2-manifest-new
python3 scripts/check-solver-bootstrap-command.py .tmp/solver-f2-command-new
python3 scripts/check-solver-e3-offline.py .tmp/solver-f2-e3-new
python3 scripts/test-solver-bootstrap-inputs.py
python3 scripts/test-solver-bootstrap-command.py
python3 scripts/test-solver-e3-offline.py
python3 scripts/check-cvc5-c0-input-selection.py
python3 scripts/test-cvc5-c0-input-selection.py
./scripts/check-repo.sh
```

C0 检查依赖两份已提交来源索引及原 `.tmp` 留存材料；缺失时明确失败，不能把索引摘要当原字节。F2 最终导出分别保留于 `.tmp/solver-f2-bootstrap-manifest-final`、`.tmp/solver-f2-command-final`、`.tmp/solver-f2-e3-offline-final`。生成入口和脚本后端合成输入全部在源码中，临时日志不冒充持久归档。


## 工作区收口

仓库级检查与 `git diff --check` 通过，已复核 tracked diff、暂存区及全部未跟踪路径。当前 `dev` 保持 `1a7ff38`、相对本地 `origin/dev` ahead 4；F2 / C0 改动未暂存、未提交，暂存区为空，没有刷新远端或 push。新增文件均属于原生源码 / 检查、离线命令输入、C0 选择与本批文档 / 记录，没有缓存、原包、可执行制品或权限变化进入交付。

## 未运行与停止线

没有执行 Linux 目标编译 / 链接 / 汇编输出审阅、真实 syscall / 内核策略安装、容器 / VM、镜像、探针、solver、系统配置、远程写入或 push。没有新增第三方 Rust 依赖、下载 / 安装构建输入或常驻进程。任务日志和离线导出保留于忽略的 `.tmp/solver-f2-*` 目录；可重跑生成入口、合成输入与检查代码属于源码交付。

F2 是原生源码和有限脚本检查，尚未建立真实 bootstrap 资格。目标工具链、outer setup policy、精确实例读回 / Mac adapter、E0 CLI 接受、E4 能力与时限 / 失联 / 清理资格仍阻断真实路径。D3 C0 的候选精确输入选择不代表下载、签名接受、构建或新 payload。原 CLI 保持 not-accepted；128 MiB / 6 s、信号 mask 与原参数的实际兼容必须另验，不产生 `proved`、正常 P4 capture 或 Evidence 状态。
