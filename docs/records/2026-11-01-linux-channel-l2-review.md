# 2026-11-01：诊断通道 L2 入口接线与静态验证

日期：2026-11-01（Asia/Shanghai）。状态：**L2 源码已完成本机有限验收；Linux 构建 / 执行和资格未取得**。实现职责见[L2 专题](../query/solver-linux-channel-l2.md)，顺位与停止线见[当前状态](../status/current.md)。此记录不是正式 Evidence、目标接受或执行许可。

## 起点与授权

项目所有者要求先提交本批 L1，再推进 L2 内部管道、FD 所有权、统一截止时间和最终退出入口接线 / 静态验证，暂不安装目标组件、构建 Linux 制品或创建 / 启动环境。

开始时 `dev` 相对本地 `origin/dev` 领先 6 笔，暂存区为空，工作树恰为 L1 的 19 路径。差异卫生 / 范围复核后精确提交为 **`5609e6a` — `feat(cvc5): 实现诊断通道 L1 源绑定与报告纯组件`**。提交后工作区干净，领先 7 笔；没有 fetch / push、身份变更、AI 署名、amend 或历史改写。随后修改均为本批 L2，未自动提交。

本批仅用已安装 Darwin Rust / Python / shell 工具做本机编译、静态检查、有限内存脚本测试和纯数据导出。没有运行 leaf main、完整采集 shell、镜像 applet、Linux ELF / syscall / 模拟器、真实 proc / cgroup 采集、Docker / OrbStack / VM / 长期服务或 solver；没有 target 取得 / 安装、Linux 编译 / 链接、镜像 / 容器 create / start、挂载、系统配置或远程操作。Cargo 产生宿主测试 harness / 库 / example 缓存，不是 Linux 制品。

## 实现与审阅结论

- 默认关闭的 `linux-channel-entry` feature / 私有 `axiom-linux-channel-init` leaf 接已有 Kernel 边界；原生 leaf 严格限 Linux musl / AArch64 LE LP64，其他目标固定拒绝 125。宿主全 feature 检查覆盖共同实现；无替代 backend 或 compile_error。根 Cargo 只加独立 `linux-channel` profile，未使用该 profile 构建，依赖 / lockfile 不变。
- 三条 CLOEXEC pipe 显式登记所有权；父侧 stdin 写端在 clone 前关闭，子 stdin 只见 EOF。外部 FD0 仅需已占用且永不读取，避免把非交互 runtime 的 null stdin 错当缺失能力；FD1 / FD2 校验 FIFO / 写方向并设非阻塞。子 stderr 最先重映射，失败前绝不向外部 FD2 写 AXCI；其余子尾段仍只走固定 raw syscall / exec，无任意命令入口。
- 唯一 t0 在自有入口首个 raw BOOTTIME 取得，先于 hook / 参数 / 输入绑定 / Report 分配；18 / 19.8 / 20 s 从同一 t0 派生。原监督 / 精确 pidfd 回收接 IO 进度与 ppoll，工作、清理、最后 200 ms 不续期，EINTR 不重试已消费 FD，无数字 / 组 kill fallback、线程、磁盘报告或新增 socket。
- 最多一帧待写，保留真实短写 offset；只对完整实际写出的 Chunk 计量和摘要。超额保留 cap 前缀 / cap+1 下界，不伪造 EOF。真实 ECHILD 与 EOF 分离；缺主退出的 ECHILD 同时保留 cause / errors，并选择失败，Rust / Python codec 均覆盖这一失败表示，未改公共协议 / ADR。
- Final 写入与 code 选择同一受界路径；帧不完整不追加另一份 Final。终端帧及其他对象保持存活，原生回调直接 raw exit，不先返回 / Drop / std flush。Final 之后的时钟超限仍使所选代码失败；外层必须以实际退出拒绝不符，完整 Final 本身不证明退出。
- 全局 allocator 仅在该 leaf 定义，正常转发已有 System；null 和 panic hook 走同一无日志 raw exit 125。构造 unsafe 契约要求失败函数不分配 / 不重入 / 不展开栈。null 注入在 GlobalAlloc 方法外执行，避免以测试 panic 违反其禁止展开契约；真实 OOM、PID 1 panic / allocator 与 main 前 CRT 行为未经验证。

本批入口绑定仍精确对应 **offline-source-binding-only**：50 源（旧 45 加 allocator / entry / entry tests / IO / leaf 五份 Rust 源），工具输入 null、native_build=not-accepted、两个 readiness=false。不是最终 target build inputs；L3 仍须明确版本 / scope 迁移与完整工具 / flags 绑定，不能直接交付此状态的源码构建。

## 留存与独立复核

[机器可读记录](cvc5-control-plane-2026-11-01/channel-l2-offline-validation.json)保存材料摘要、复核入口、七个脚本场景与有限结论。

1. 纯源导出保存在新目录 `.tmp/linux-channel-l2-2026-11-01-audited/`，包含 inputs.json、collector.sh、synthetic-report.bin。实际 input_binding 为 `sha256:56823d72244a0025d3cf62977d0ac6f74d3457ec9063033f942e08ea57f6e8c5`；正文仍为 9,717 bytes、`sha256:e1f884bc7762c5cd64a456b93785860810cd16ba21bb1a67a9bb5607a71f54ae`，未运行 / 改写。50 源由 Python 独立枚举复核；纯 codec 的 1,747-byte 样本全部 1,747 个截断前缀拒绝、7 种分块通过。
2. 脚本内核真实接收到的 write 原字节保存在新目录 `.tmp/linux-channel-l2-2026-11-01-scripted-audited/`：七份 .bin 与 cases.json。场景为 complete / eintr / prefix / missing-main / half-chunk / broken-final / late-clock。这些字节流不是直接拷 Encoder 待写缓冲；由同一生产 drive 经过有限 Model 实际写出。独立 Python 以 1 / 7 / 4096 bytes 分块复核全部七份，保留缺 Final 拒绝和 late-clock 的 Final=0 / scripted code=125 不符；这些 code 来自脚本状态，不是 Linux runtime 退出。
3. 上述导出和 L1 / L2 早期 reviewed 目录均保留，没有覆盖旧材料。以新检查器复核旧 `.tmp/linux-channel-l1-2026-11-01-reviewed/`，实际退出 1 / `source-inventory-shape`，因为源家族已从 45 变 50；没有改旧记录或摘要迁就当前源码。

两个样本家族的绑定不同且显式区分：纯源样本使用实际 inputs 摘要 / 真实正文摘要；脚本场景 run_id=07×32 / input=08×32 / collector=09×32，仅是有限测试绑定。二者均 runtime_exit_confirmed=false、qualification=not-established，不能登记为镜像 / 进程来源事实。

## 开发中失败及修正

- 第一轮旧测试模型没有跟随准备阶段的新顺序：fcntl 故障发生在 proc 空快照之后、时钟回退需跨新的前置 guard。实际测试返回 101（unexpected children snapshot / 未关闭的未知继承 FD）；只修正有限脚本的快照 / 时间序列，未放宽生产校验。synthetic stderr 的期望字节数 21 修为实际 20。
- 编译曾返回 101：新增测试遗漏 CString 导入，以及修改 flush 返回值时少一处 match 逗号；补正后原检查通过。Clippy 曾以 101 报 collapsible_if，合并控制流后继续使用 `-D warnings`，未加 allow。
- 审阅发现 stderr 首次 dup 前的失败可能向外部 FD2 报 AXCI；修正为 stderr 首接、失败静默 raw exit，增加实际子尾段调用序列回归。又发现终端 frame Vec 会在返回上层时析构，改为保留终端帧和同栈原生终端回调，未以 panic=abort 代替该出口。
- 新增“ECHILD 但缺主退出仍需导出真实失败事实”回归先实际失败（101 / report-invariant），随后 Rust / 独立 Python 同步允许仅有显式 cause / 非空 errors 的失败表示；继续拒绝成功代码和无错误的缺主退出。
- 首次显式脚本导出使用相对环境路径，Cargo 测试 cwd 为包目录，实际 101 / NotFound；该路径没有创建材料。改用已解析的仓库任务目录绝对路径，不创建额外包内 .tmp 或放宽新建检查。早期成功 reviewed 导出在后续 stdin / 精确 musl cfg 收口后保留，后续又将 output poll 的 ERR / HUP / NVAL 显式记为传输失败，并在传输已坏时改用受界 signal wait 继续回收，防止永久就绪 FD 忙轮询；新增回归通过。所有 reviewed / final 材料保留，最终仅以新 audited 目录对应当前源码。

## 实际验证

最终使用既有 `1.97.1-aarch64-apple-darwin` / Python 3.14.5：

- `RADISHAXIOM_CHANNEL_SCRIPTED_EXPORT=/Users/luobo/Code/RadishAxiom/.tmp/linux-channel-l2-2026-11-01-scripted-audited cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-solver-bootstrap-linux --all-targets --all-features --locked --offline --quiet`：**117 项通过**（新增 30 / 既有 87），无忽略；两个 0 项 harness 不计入测试数。Model 从不调用宿主 process / signal / Linux FD API；raw exit 用明确测试 panic 截获，非真实退出。
- `cargo +1.97.1-aarch64-apple-darwin fmt --all --check`、`cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings`：通过。
- `python3.14 -O scripts/test-linux-channel.py`：**16 项通过**，沿用语法检查和从真实正文提取的纯 AWK 合成过滤，没有调用整个正文；新增缺主退出 / ECHILD 的失败 / 成功篡改负例。
- `cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-solver-bootstrap-linux --example export_linux_channel_inputs --locked --offline -- .tmp/linux-channel-l2-2026-11-01-audited`；随后 `python3.14 scripts/check-linux-channel-inputs.py --synthetic .tmp/linux-channel-l2-2026-11-01-audited`：50 源绑定 / codec 样本互操作通过。
- `python3.14` 用 runpy 加载 scripts/test-linux-channel.py 并调用 `check_scripted_export('.tmp/linux-channel-l2-2026-11-01-scripted-audited')`：七份实际脚本流、三种分块通过，runtime / qualification 不升级。
- `python3.14 scripts/check-repo.py`：完整仓库检查通过（2,931 文件）；`git diff --check`、本批路径 / 引用 / 权限 / 留存摘要及 source binding 复核通过。最终局部复核为 22 个精确路径、380 处本地引用 / 锚点，普通文件 0644 / UTF-8 / LF、材料 / 方法摘要、feature / bin / profile 与空暂存区均通过；不把中间轮次相加为一次测试。

没有扩大到无变化的其他 crate 全量测试；workspace Clippy 已覆盖新 feature / bin / profile 与现有包的静态集成。没有触发 CI、真实 Linux syscall / 汇编 / target std / CRT / 链接 / allocator / BusyBox 验收、Mac 编排或独立语义 checker；不能从 117 项本机脚本测试推断真实 20 s 回收保证。

下一批先核定 L3 精确 Rust 1.97.1 Linux musl target 的来源 / 许可、安装目标、大小 / 时间 / 清理范围与完整输入 / 构建包装器计划。取得 / 安装、一次 Linux 构建、离线制品验收、交付挂载及真实一次诊断仍分别授权；原 C1 / G0 / E0 / E4、镜像 / 权限、无写别名和独立终止 / 存储硬限门禁均不变。无后台服务或新环境需要清理，宿主 Cargo 缓存和精确任务目录材料保留。本批 L2 未提交 / 未推送，`dev` 仍相对本地 `origin/dev` 领先 7 笔。
