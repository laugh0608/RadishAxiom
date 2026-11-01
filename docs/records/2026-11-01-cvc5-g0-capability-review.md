# 2026-11-01：G0 现有宿主能力盘点与结束决定

日期：2026-11-01（Asia/Shanghai）。状态：**有限盘点结束，证据不足，不进入真实接线**。用途：留存[控制面方案 G0](../query/solver-local-cvc5-control-plane-plan.md#结论与直接出口)在当前已有入口下的实际观察、缺口和恢复条件；供实施者和项目所有者追溯。本文不认证 Linux 能力，不提供新环境或探针授权，不改变 ADR 0031 的信任 / 资源 / 接受要求。实际筛选材料见 [G0 观察](cvc5-control-plane-2026-11-01/g0-observation.json)。

## 授权、提交与工作区

项目所有者明确要求先提交工作区更改，再推进下一批。开始时在 `dev`，暂存区为空，工作区恰有上一批 8 个文件改动；复核范围和差异卫生后，精确暂存并提交为 **`25ef314` — `docs(cvc5): 核定控制面接线方案与真实资格边界`**，未更改身份、追加 AI 署名或 push。提交后工作区干净，相对本地 `origin/dev` 领先 1 笔；没有 fetch 或核对实时远端。

随后按 G0 只盘点现有入口、宿主报告和明确的共享视图，不创建 / 启动 machine、容器或服务，不设置配置、挂载、quota 或权限，不安装 / 下载工具。没有执行 SDK、compiler、solver、调试 shell 或任何 Linux 命令；未从“推进下一批”推导更换平台或扩大信任范围。

## 实际命令与留存方式

先检查本机 CLI 帮助，再用其公开的只读子命令。除最初直接返回的 `orb --help` / `orbctl --help` 外，版本、后续帮助、list、config get 和 Docker info 均由已有 Python `3.14.5` 的 `subprocess.run(..., capture_output=True, text=True, timeout=8)` 调用；全部成功，没有超时、失败重试或遗留进程。未执行帮助里展示的创建 / 启动示例。

| 命令 / 查询 | 实际结果 | 不能外推 |
| --- | --- | --- |
| `orb --help`、`orbctl --help`、`orbctl run --help` | `orb` / `run` 在指定或默认 machine 内执行命令；debug 面向容器。已检查的公开帮助没有提供 Docker VM 宿主 shell 入口 | 不是证明 OrbStack 绝无其他内部或管理员通道；不能随意执行默认 `orb uname` 取得报告 |
| `orbctl version` | `2.2.5 (2020500)`；commit 原文留在观察 JSON | CLI 身份不是宿主 / SDK / 工具接受或来源认证 |
| `orbctl list --help` 后执行 `orbctl list --format json` | 退出 0，stdout 为 `[]`，没有已登记 Linux machine | 不创建 machine，也不借用历史停止 VM / 兄弟项目环境 |
| `orbctl docker --help`、`orbctl docker volume --help` | 扩展命令为 migrate / volume；volume 只列 clone / export / import | 没有从已检查命令找到可直接复用的独立宿主控制面；不运行 volume 命令试错 |
| `docker info --format '{{json .}}'` | 同一 daemon ID，Linux `7.2.12-orbstack-00394-gbecdd6130068`、cgroup v2 / cgroupfs、`overlayfs` / containerd snapshotter；`Containers=0`、`ContainersRunning=0` | 无现存容器可复用；不能将 daemon 报告改称 Linux 实例读回 |
| `orbctl config get memory_mib`、`cpu` | 分别 `16384`、`10`；daemon 另报 `MemTotal=16818991104`、`NCPU=10` | 配置容量不说明 8 GiB 构建可用、监督预留、峰值和资格已通过；没有调整设置 |
| `orbctl config get mount_hide_shared` | `false` | 此项不是防写或取消共享机制 |
| Python `Path.stat` / `os.access`，仅 5 个已知路径 | `~/OrbStack`、其 docker / volumes / containers 目录及已知 daemon socket 路径存在；保留类型、UID / GID、模式和本调用上下文的 access 返回 | 未列出卷 / 容器内容、未写文件；目录 access 不代表子对象权限，也不代表普通宿主进程实际防写资格 |

实际命令、退出结果和筛选字段保存在观察 JSON；复核可按其中 `method`、`help_observations`、`config_reports` 及 `docker.command` 重取新报告，必须另存批次，不覆盖历史。完整 help / daemon 响应和完整配置未留存，不能追认其摘要。没有读取代理、credentials、用户程序或完整环境。

筛选观察文件 SHA256 为 `06107902f38bdd8c2b099040790dce427b6c6b9fcff0091798df4e76a1405d04`；只绑定已保留的字段与摘录，不认证未取得的 Linux 状态。

路径查询的 `caller_uid=501`，所有 `os.access(..., W_OK)` 都返回 false，包括模式 `0700` 且同属 501 的顶层目录和已成功使用的 daemon socket。**只保留这些调用上下文结果，不把它们当成所有普通宿主进程不可写 / 不可控制的证据**；沙盒、文件共享实现和 socket 访问规则均可能影响解释。本批没有用写入尝试验证防护，也没有以 sandbox 拒绝追认产品资格。

## 官方边界与本批判断

OrbStack 的[原生文件视图](https://docs.orbstack.dev/features/native-files)说明容器 / 卷内容可经 macOS 访问和修改；[卷与挂载](https://docs.orbstack.dev/docker/file-sharing)确认卷位于 Linux 侧而仍可从 Mac 使用。因此，“Linux 私有 named volume”不能仅凭存放位置排除 macOS 写别名。真实候选须另外证明其具体根没有未受控写视图。

[设置文档](https://docs.orbstack.dev/settings#hide-orbstack-volume)说明 `mount_hide_shared` 仅隐藏 Desktop / Finder 入口，`~/OrbStack` 仍可访问，不能把开启它作为冻结方案。[架构文档](https://docs.orbstack.dev/architecture)区分 Docker engine 和 Linux machines；[命令文档](https://docs.orbstack.dev/machines/commands)的 `run` 作用于 machine。结合本机 list 为空及零容器，本批在已检查入口内没有可用于 G0 Linux 读回的执行上下文。

上面是官方接口与本机只读观察的组合判断，**不是对任意 OrbStack 存储或内部通道的不可行性证明**。没有测出底层文件系统、块 / inode hard quota、独占发布机制或直接 cgroup 终止权限；不以 API 功能、上层目录模式或没有写入成功来代替它们。

## G0 各项结果与停止决定

| G0 项目 | 本批结果 | 恢复需要的精确输入 / 事实 |
| --- | --- | --- |
| 精确宿主与管理通道 | daemon / CLI 报告已记录；已检查入口内未取得 Linux 管理上下文 | 指定现有且可使用的 Linux 管理入口、目标实例 / 权限和只读命令范围；必须能核对与当前 Docker 宿主的关系，不能只提供另一台 Linux 的报告 |
| 私有存储、块 / inode 硬限 | 未取得底层文件系统与可受控根，不选择 backend | 同一宿主的精确候选根、实际文件系统 / 挂载 / quota 能力及允许访问主体；不能用新卷名代替机制 |
| 写别名与管理权限 | 原生共享视图存在；无具体冻结根与防写证据 | 处理 macOS 共享视图、daemon 管理能力、继承 FD / 映射及辅助写入者的具体防护；需要扩大 trusted 范围时先作明确决定 |
| 独立终止、PID / inode / 时间 | 尚无 Linux 控制面读回与强制资格材料，所有参数保持未核定 | 精确工作 cgroup / 外围 watchdog 权限与资源分配，PID / inode 候选数值和时间依据，再单独安排真实负向资格 |

G0 本轮出口为 **`evidence-insufficient-stop-before-wiring`**：有限盘点已经结束，正向资格没有通过。保留 `build_ready=false`、`execution_ready=false` 和原 v0.1 / v0.2 边界；不写控制器、不组装 SDK、不配置文件系统、不安装工具、不起特权服务，也不自动创建诊断容器或 machine。没有为消耗原建议 0.5 人日而继续扩大查询，且没有可靠人工工时账，不把短时命令耗时换算为人日。

**不再把重跑 list / info 或增加模拟作为默认下一批。** 恢复本路线须先提供上述现有管理入口与候选根；如果现有环境没有这些条件，就需要另行核定新检查 / 管理通道的精确目标、权限、工具身份、占用、时限和清理，并确认其外部影响 / 信任范围后再实施。本批不替项目所有者选择新平台或放宽边界。等待期间的 F2 有限静态审阅仍按当前状态作为独立可选切片，不在本批越界实施。

LibPoly 许可、C1、组装差异、环境资格、构建授权、C4 / E0、E4 / E5 均保持原门禁；本批没有查询上游答复或发送消息。新观察只缩小“已有入口是否足够”的不确定性，不计作 solver / 产品核心能力或 A1–A10 实际验收进展。

## 验证与交接

本批只改接续文档与只读观察，不改代码、依赖、lockfile、机器契约、Accepted ADR 或冻结规则 / 配方。不另跑无变化的 Rust / cvc5 Python 组件回归；仓库检查的内置项目照常执行。

| 实际验证 | 结果 |
| --- | --- |
| `python3.14 scripts/check-repo.py` | 完整通过，2,893 文件；沿用已定位的 Python 3.14.5，不重新调用已知不兼容的默认 3.9，不修改检查器 |
| `git diff --check` | 通过；完整跟踪差异已复核，未跟踪记录另核文本卫生 |
| 局部只读核对 | 8 个文件范围正确、暂存区为空；新增本地路径 / 锚点、UTF-8 / LF / 换行 / 尾随空格、非执行权限、观察摘要 / scope / false 状态及前后 daemon 关键身份一致性通过 |

前批已提交为 `25ef314`，本批结果在该提交之后形成，最终未提交路径和本地领先状态由交接消息报告；前批提交授权不自动扩为 push 或本批提交。没有后台进程、需要清理的实例或临时卷；已有材料、配置和外部状态未修改。
