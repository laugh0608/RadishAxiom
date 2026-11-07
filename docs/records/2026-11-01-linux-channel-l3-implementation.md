# 2026-11-01：L3 v0.2 输入、native 捕获与有界包装器实现

日期：2026-11-01（Asia/Shanghai）。状态：**源码 / 宿主静态与合成验证完成；没有真实完整 root、target 安装、Linux 制品或环境执行**。设计与字段以 [L3 专题](../query/solver-linux-channel-l3.md#v02-实现接口与静态出口)为准，顺位只见[当前状态](../status/current.md)。这是实施记录，不是工具接受、构建资格、正式 Evidence 或运行证明。

## 工作区与范围

本次从干净 `dev` / `c4143473ce2826f61c0b13fb8c8c74ca4dbd30bb` 开始，相对本地 origin/dev 无 ahead / behind。L3 方案提交 `40af60c` 后已有规划导航整理提交，本批沿用其文档路由，不覆盖导航。用户授权实现 v0.2 纯生成 / 独立复核、native 捕获、有界包装器和静态验证；明确不安装 target、构建 Linux 制品或创建 / 启动环境。本批未自动提交 / 推送、fetch、切分支、修改 Git 身份或重写历史；最终源码 commit 仍待本批提交后登记。

- Rust 沿现有 channel_inputs / export example 实现 v0.2 request / root 与 native_binding，保留 v0.1 严格导出。source-only root、null、错误 scope / ref / 源摘要均不能进入 native。
- native 仅在既有精确 Linux musl AArch64 cfg 捕获 `RADISHAXIOM_LINUX_CHANNEL_INPUTS`，prepare 使用同一宿主可测验证逻辑；runtime 不再生成 source-only 输入，不读取 inputs 环境 / 路径。wire v0.1 与 collector 原字节不变。
- 扩展现有独立 Python checker，新增 scripts/build-linux-channel.py（固定计划 / 唯一 build / 内部 recorder）及 scripts/test-linux-channel-build.py。选定源从 50 增至 53：新包装器 / 测试，以及此前已被 checker 调用却漏列的 bootstrap checker。没有 Cargo / lockfile / 工具 pin / 依赖 / 公共格式变化。
- 实现五份 sidecar 引用、外部 source commit / review digest pin、源全树和实际文件复核；合成安装 / 接受仅在明确 synthetic 纯调用中可用，生产 CLI / wrapper 拒绝。安装 / 解析回执仍属于被有限审阅的信任输入；checker 不认证它们的历史真实性、发布者、Mach-O 加载关系或系统资格。
- wrapper 只消费预先生成的 root，完整 Git blob 快照、固定 argv / 环境 / flags、祖先 Cargo 配置拒绝、normal 图与 metadata 核对、一次编译、真实 rustc argv 记录及前后复核均进入同一截止。未知形式 / 单位 / 路径、配置注入、超额、取消、短写 / ENOSPC、非零退出或停止未确认都失败；失败保留，不重试、不安装、不执行产物、不自动清理。

## 宿主发现与根因修正

使用已有 Cargo / rustc 的绝对路径、最小环境、显式 `aarch64-apple-darwin` 和任务专用新 Cargo home / target 进行短时离线验证：

1. 空 Cargo home 的 `metadata --no-deps --format-version 1 --locked --offline --filter-platform aarch64-apple-darwin` 退出 0，stdout 17,306 bytes、stderr 空。
2. 同一空 home 的 `check --package radishaxiom-digest --target aarch64-apple-darwin --locked --offline` 退出 101：Cargo 仍需解析 workspace 中 Darwin store 的 `libc`，报告 no matching package。没有去掉 offline 或联网重试，没有产生这一请求的编译单位。保留四次真实 rustc 只读 probe argv；包含不带 target / flags 的 host probe，以及把 flags 放在 target 选项之前的 target probe。recorder 已据此修正，不假定 flags 必须位于尾部。
3. 只复制已有的两份索引数据到另一新任务 home 后，Darwin digest check 退出 0。随后用同一 home / 新 target 完成 digest 的 **Darwin rlib** 构建（profile=linux-channel，target 明确为 aarch64-apple-darwin），记录真实编译 argv。该 profile 名称不把 Darwin 产物变为 Linux。没有复制 `.crate` 或解包源，实际 normal 编译依赖仍未扩展。

精确源数据只读于现有用户 Cargo registry；副本仅在忽略任务目录，未提交第三方数据、回写这两份原索引或安装依赖：

| 既有文件（共同前缀 `/Users/luobo/.cargo/registry/index/index.crates.io-1949cf8c6b5b557f/`） | bytes | SHA256 |
| --- | ---: | --- |
| config.json | 76 | 5b943a2c6f7eb743f7308aba07bdbb47d9ae44aafecd832d7f15df186afbafb3 |
| .cache/li/bc/libc | 84,005 | 0c0c0edd0d15a477311bebab5f7b35d68767bb2ebeea274f85404cd2921c498a |

这修正 L3 原方案“全新空 Cargo home 足够”的遗漏，保持七包完整快照和三个 path 包的正常编译闭包。tool-inventory 现在明确 cargo_resolution 的两个固定目标及源摘要；独立 checker 检查 registry URL、cache 格式、唯一锁定 0.2.189 项 / checksum / 非 yanked，wrapper create-new 复制并在构建后复核。未来特定接受必须覆盖这些元数据的来源 / 许可与信任，不能将本次宿主通过写成接受决定；不新增 SDK、注册表编译依赖或第二套 Cargo workspace。

## 实际验证

以下均使用已安装的 `1.97.1-aarch64-apple-darwin` 和 Python 3.14，不依赖默认 1.96.0，不安装组件：

- `cargo +1.97.1-aarch64-apple-darwin fmt --all --check`：通过。
- `cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings`：通过。
- `cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-solver-bootstrap-linux --all-targets --all-features --locked --offline`：119 项 Rust 通过（本批新增 2 项输入边界；bin / example harness 均 0 项），没有运行 native main 或 Linux syscall。
- `python3.14 scripts/test-linux-channel-build.py`：27 项通过。覆盖全五份引用、外部 review pin、旧版 / null / scope / readiness、重新摘要后的伪接受 / 计划 / 源漂移、66 文件及多余文件、receipt / 工具 / registry 数据漂移、symlink / parser 上限、配置存在、图 / profile、实际生成 recorder 的短时合成执行与 64 条上限、共享截止、取消、输出 / 任务 / map 超限、短写 / ENOSPC、真实关闭 stdio 的遗留子进程 / 未知组及 cleanup 主因保留、脚本 Git blob 快照和固定 argv 拒绝。
- `python3.14 scripts/test-linux-channel.py`：既有 16 项通过，含 collector 内嵌 AWK 的合成输入测试；没有执行完整 collector。
- 同一真实 Rust export example 以纯 v0.1 和 `--v02` 合成 request 导出；Python 独立复核原字节相等，53 源绑定及 v0.2 五份合成清单通过。v0.2 synthetic-report 仍为 1,747 bytes：7 种分片和全部 1,747 个截断前缀检查通过；runtime_exit_confirmed=false、synthetic=true、readiness=false。没有把合成文件作为实际安装 / 接受回执。
- 从实际 native 入口抽取同一 include_bytes / env 捕获表达式，仅以 Darwin rustc `--emit=metadata` 编译最小 lib：缺变量与缺文件均退出 1，捕获合成文件退出 0。不执行输出，不视为 Linux native cfg / ABI / 链接通过。
- Python 字节编译、`./scripts/check-repo.sh`、`git diff --check` 与最后路径 / 状态核对通过。精确材料摘要与最后结果见[机器记录](cvc5-control-plane-2026-11-01/channel-l3-implementation-results.json)。

首轮 fmt 报格式差异，Clippy 报新增测试的 collapsible_if；均修正后重跑通过，没有豁免检查。原空 Cargo home 失败是已保留并修正的输入遗漏，不被后续通过覆盖。最终审阅另修正了先 reap 组长、后按数值 PGID 清理的身份风险：保留 waitid(WNOWAIT) 的未回收组长，默认 SIGCHLD / 单一 waiter 前提下，仅在身份仍被持有时使用 libproc 枚举 / 停止组；组长回收后不再发组信号。新增真实短时 fork / 关闭 stdio / 留子进程测试，成功检测并停止原组。首轮未知组模拟暴露 ResourceWarning，已修正错误路径对已知组长的回收，并以 ResourceWarning 作为错误重跑通过。libproc ABI 依据本机 MacOSX27.0.sdk 的 libproc.h / sys/proc_info.h，只读取声明；未复制 SDK。其 OS / ctypes 解析仍需未来有限宿主接受，不能把本次测试升级为独立终止。失败里的数值 PID / PGID 仅作诊断，不授权事后复用发信号。

## 留存与未覆盖范围

忽略目录 `.tmp/linux-channel-l3-implementation-20261101-a/` 保留初始合成 bundle、捕获宏三案、空 home 失败、host metadata、两份索引副本和 Darwin check / rlib / argv 日志；最终复核材料另留 `.tmp/linux-channel-l3-implementation-20261101-final-audited/`，先前 final 目录保留为身份修正前的中间验证。单元测试只清理自己创建的 tempfile 目录；没有清理旧来源、全局缓存或失败。没有留后台进程；包装器对未知存活状态的拒绝不等于独立终止证明。

未执行 target add / remove、rustup cache 预填、目标归档解包、Linux cargo build / linker / ELF / collector / solver、Docker / OrbStack / VM / mount / 长期服务、系统权限 / 配置或远程写入。既有 target 缺席不从本次宿主检查升级成任何安装状态；没有新的安装观察、有限输入接受或真实完整 root。

600 s / 512 MiB 是受信宿主下的截止与观测，Popen / IO / SIGKILL / wait 依赖宿主，停止确认最多另观察 1 s；不构成 RSS / 块 / inode 硬限或独立终止。实际 Linux Cargo probe / 全编译 argv、std / CRT / dylib / allocator / syscall、最终 map / why-extract / ELF / 许可证对应及 L4 / L5 仍待分别核定。C1 / LibPoly、E0 / E4、G0 / A1–A10、镜像 / 权限 / 无写别名 / 存储硬限与 solver 停止线保持。后续先复核并提交本批，再审阅精确输入及单 target 安装范围，不自动触发安装或构建。


日终提交接续：上述 13 文件已按项目所有者要求提交为 `bb9d963b38273bfd9ec7aefe69cc13417a4a8f34`。本记录与机器观察中的“未提交 / final_implementation_commit=null”保留其生成时状态，不回填历史原字节；现行来源与日终文档复核见[日终记录](2026-11-01-closeout.md)。没有因提交而取得真实 inputs / 安装 / 构建资格。
