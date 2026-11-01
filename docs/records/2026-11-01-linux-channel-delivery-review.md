# 2026-11-01：诊断启动器目标构建与交付方案核定

日期：2026-11-01（Asia/Shanghai）。状态：**方案核定与本机只读观察完成；尚未实施 / 安装 / 构建 / 交付挂载**。用途：供项目所有者、实施者和审阅者核查本批提交、构建候选、报告 / 退出判断和实际验证。现行设计只见[目标构建与交付方案](../query/solver-linux-channel-build-and-delivery-plan.md)，顺位只见[当前状态](../status/current.md)；本文不接受工具、许可或运行资格。

## 提交与实际范围

项目所有者要求先提交 PID 1 启动器更改，再核定精确 Linux 目标构建与交付方案，明确采集正文绑定、报告导出和最终退出入口，暂不创建或启动环境。启动时 `dev` 相对本地 `origin/dev` 领先 4 笔、暂存区为空，恰为前批 11 路径；复核差异与卫生后精确提交 **`be8c620` — `feat(cvc5): 实现诊断 PID 1 监督与回收组件`**，提交后工作区干净、领先 5 笔。

本批只读取已有源码 / 正式方案 / 指定宿主工具元数据、核对三份已有工具文件摘要、查阅必要官方参考并编写方案 / 记录。没有修改源码 / Cargo / lockfile / ADR / filter / fixture，没有 fetch / push、Git 身份变更、AI 署名或历史改写；没有 target 组件取得 / 安装、交叉构建 / 链接、镜像拉取 / 构建、container create / start / exec、machine / 长期服务启动、launcher / collector / solver 执行或远程状态写入。

## 真实候选观察与留存

机器可读观察为 [channel-build-input-candidate.json](cvc5-control-plane-2026-11-01/channel-build-input-candidate.json)，字段来源为明确 CLI、文件长度 / SHA256 和前批 rootfs 库存，而非推断的安装状态。version 原始双流存入已忽略的 `.tmp/linux-channel-delivery-review-2026-11-01/`，共 819 bytes；原日志、既有安装文件和所有前批材料保留，未复制工具二进制到仓库。每次版本调用独立捕获、8 s / 单流 64 KiB 上限、退出码均 0。

| 只读入口 | 实际结果 |
| --- | --- |
| 已安装 sysroot 的 `bin/rustc --version --verbose` | Rust 1.97.1 / aarch64-apple-darwin；commit `8bab26f4f68e0e26f0bb7960be334d5b520ea452`，LLVM 22.1.6 |
| 同一 sysroot 的 `bin/cargo --version --verbose` | Cargo 1.97.1；commit `c980f4866141969fab6254a680546a277789d6f0`；只据必要字段登记，不保存 / 传播宿主完整环境 |
| 同一 sysroot 的 `lib/rustlib/aarch64-apple-darwin/bin/rust-lld -flavor gnu --version` | LLD 22.1.6，LLVM commit `dcc3606807c989700e0ac1cac18c31741bcd40d9` |
| `rustup target list --installed --toolchain 1.97.1-aarch64-apple-darwin` | 只有 `aarch64-apple-darwin`；Linux musl target 目录及 component manifest 均不存在 |
| `rustup component list --installed --toolchain 1.97.1-aarch64-apple-darwin` | 宿主 cargo / clippy / rust-std / rustc / rustfmt；不含 Linux target std |
| 已安装 rustc 的 `-C help` | 确认候选 flags 家族存在，没有编译 / 链接任何输入；不证明参数组合或实际输出成立 |
| 六份 Cargo / pin 文件和前批 rootfs 库存 | 原字节摘要绑定到 `be8c620`；`/mnt` 为既有空目录 `0:0 / 0755`，未实际绑定或测执行权限 |

三份已有普通文件（均非 symlink）按原字节登记：rustc 412,504 bytes / SHA256 `210df6794001b73ec3d453878707fa1e0bdcb63c427024a6e6574bbe5615a4da`；cargo 31,867,672 bytes / `7672ead309d505577c018fff2cafb3433601f073e38cbe87359ac1f7b944bbf5`；rust-lld 130,977,488 bytes / `8f5fe507df7232eac0a610c12a5d11f3202205235f710eb98c6c78df6d3f548d`。摘要只绑定现存宿主文件，未核对其全部 dylib / 安装包 / 发布者签名；不能将曾用于 Darwin 组件检查的宿主工具接受扩为 Linux std / CRT / 链接输入接受。

## 方案中的具体判断

- **目标与交付。** 固定 Rust 1.97.1、aarch64-unknown-linux-musl、已有 bundled rust-lld 的 GNU flavor、静态非 PIE ET_EXEC；新 binary / feature / profile 都是待实施声明。仅将单个接受后的 ELF 放入 runtime 目录，只读挂到既有 `/mnt`，records / 来源 / 归属文件不挂入容器；不构建派生镜像或挂整个源码树。Mac 同用户写别名和共享源关联仍须收口，readonly / chmod 不是冻结证明。
- **正文与来源。** 从唯一受审正文原字节 include_bytes 捕获，明确 LF / 末尾 LF / CString NUL 的摘要边界；生成输入绑定源快照、工具 / flags / 类型化 profile，最终外置 manifest 再绑定 ELF，避免自产物自摘要。Mac 从事先登记输入取得期望值，不能照抄收到的 Start；正文不从 Docker argv / stdin / 环境载入。
- **报告输出。** 现有 run 的子 stdout / stderr 直接继承不能承载独立终端控制记录。未来必须让 PID 1 独占外部 FD1，子输出走内部 pipe / 有界 Chunk，Start / Final 由 PID 1 编码；AXCI 只是子 stderr 数据，不能冒充 Final。私有 v0.1 header、序号、control / stream 类型、预算和拒绝已具体化，但本批不创建 codec 或公共 schema。
- **时间与退出。** 将原 20 s 内的末 2 s 细分为 1.8 s 回收、0.2 s 最终导出；首 t0 要移到 Report 分配前，不在 run 重新起算。Final 只能报告 selected_exit_code 与此前观察，不能预言自身已退出；无论导出是否成功都须 raw exit，正常路径不得 return / Drop / std flush。原 main 前 CRT / std 时间继续由 Mac 外部总截止覆盖，未取得实际保证。
- **异常终止。** 不能把 panic=abort 当成 PID 1 的退出证明。方案明确专用 binary 的无 IO raw-exit panic hook，以及仅将 System 分配失败变为 raw exit 的最小 GlobalAlloc 包装；未实现，不影响其他 binary / 当前库。精确 std / musl / System 启动、同步故障、hook / allocator 接线和无分配退出的源码 / 链接 / 合成故障验证未完成时仍不接真实入口。
- **下一切片。** 先 L1 正文 / 输入绑定与报告纯组件，再 L2 受界管道 / 回收 / 最终入口源码；L3 单 target 组件取得 / 安装、L4 一次构建 / 离线验收、L5 一次诊断执行分别按明确范围推进。不要用空正文、改 tag、放宽 ELF 或运行环境试错补来源 / 权限缺口。

只作固定数值 / 最坏预算算术复核：8,192 帧 × 20-byte header，加 Start 4 KiB / Final 32 KiB / collector stdout 1.5 MiB / stderr 64 KiB，为 1,839,104 bytes，低于原外部 stdout 2 MiB；18 s + 1.8 s + 0.2 s = 20 s。该计算不是内存 / 性能 / 时限或数据可读性的实际验收。外部 stderr 64 KiB、Mac 新增运行记录 8 MiB、128 MiB / 16 PID / 90 s 等原通道额度保持；预建制品 / target 组件的新增存储在方案中另列，不塞入运行记录预算或宣称零新增状态。

## 参考与失败留存

查阅官方 Rust 目标与 codegen / Cargo 环境文档、精确 Rust 1.97.1 target / musl base / CRT 选择源码，以及 Docker bind 文档；引用均归入方案对应段落。Rust 当前 std 文档展示的版本为 1.99.1，只用于稳定接口方向，不作为 1.97.1 的实际实现 / 工具输入接受；精确 panic / allocator / CRT 源码仍是后续前置。Cargo cargo-targets 参考网页一次返回 400 / Timeout fetching，未重试、不声称已取得该页内容；required-features 的行为仍须后续 manifest 实施和宿主全 feature 检查验证。没有下载新的源码归档、组件包或许可证正文，也没有把网页片段复制成第三方源码。

## 实际验证与结束状态

实际验证如下：

- `python3.14 scripts/check-repo.py`：完整仓库检查通过，2,910 文件；`git diff --check` 通过。
- 局部核对通过：恰为本批 6 个文档 / 观察路径、15 处新增本地引用及锚点可解析、UTF-8 / LF / 无尾随空格 / 普通文件 `0644`、暂存区为空；无代码、Cargo / lockfile、ADR、filter 或 fixture 变化。
- 独立重算观察 JSON 与实际 CLI 原双流、六份基线输入、三份现存工具文件的长度 / SHA256 一致；5 个实际版本调用退出 0、原双流合计 819 bytes。缺失 target / 未生成入口和正文、未构建 / 未创建环境及全部 readiness=false 均与本批范围一致。
- 重算候选帧字节和时间分配得到 1,839,104 bytes / 20,000 ms，与方案一致；不是生产 codec、时钟行为或资源验收测试。

未重跑无改动的 69 项 Rust 组件测试或此前镜像 20 项检查；其历史结果保留，不能写成本批重新运行。未运行 Linux 构建、目标 ELF / collector、真实管道 / 信号 / allocator / raw exit、Mac adapter、solver、CI 或独立程序语义 checker。

方案切片到此结束：已将目标、工具缺口、正文身份、交付目录、独占报告流和最终入口具体化；**目标组件 / 制品 / 交付 / 执行均未接受，build_ready=false / execution_ready=false**。原 C1 / E0 / E4、G0 / A1–A10 和许可缺口不升级。没有 native 二进制、采集正文 / codec / allocator / binary target 或未来 runtime 目录生成，没有后台进程或环境需要清理；只读观察原日志与前批材料保留。本批文档 / 观察新改动未包含在 `be8c620`，未自动提交或推送。
