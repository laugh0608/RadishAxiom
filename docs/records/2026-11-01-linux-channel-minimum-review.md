# 2026-11-01：新 Linux 管理通道最小方案审阅

日期：2026-11-01（Asia/Shanghai）。状态：**静态方案完成，环境未创建**。用途：记录项目所有者要求提交 G0 后，对新通道的权限、资源和清理所作的有限核定。供后续实施 / 审阅者追溯；本文不是镜像 / 工具接受、执行授权、OS qualification 或程序 Evidence。现行方案见[最小通道专题](../query/solver-linux-management-channel-minimum-plan.md)，统一顺位见[当前状态](../status/current.md)。

## 当前任务范围与提交

项目所有者明确要求：“先提交本批 G0 更改，再核定新 Linux 管理通道的最小方案，明确权限、资源占用和清理方式，暂不创建环境。”本批据此只提交已完成 G0 改动并进行静态方案 / 必要只读镜像元数据核对，没有将核定扩大为执行或接受新信任。

开始时 `dev` 相对本地 `origin/dev` 领先 1 笔，工作区为前批 8 个文件，暂存区为空。复核状态、范围、差异卫生和两份未跟踪记录后，精确暂存并提交为 **`e507d78` — `docs(cvc5): 记录 G0 能力盘点与接线停止条件`**。提交后工作区干净，领先 2 笔；未修改 Git 身份、添加 AI 署名、amend、fetch 或 push。授权提交的是已形成的 G0 内容，本批新方案在该提交之后形成。

读取链限 G0 事实、控制面方案、协作 / 许可边界及必要官方接口。未重复 G0 的 list / config / daemon 宿主盘点，未查询 LibPoly 回复，不扩展其他平台或兄弟项目。

## 候选、实际观察与未验证范围

最小方案推荐同一 daemon 的**一次性非 root 只读诊断容器**，先 create 后核对配置，再一次 start / 有界采集 / 精确清理。不推荐新建 machine / SSH 或 privileged 宿主 shell。当前只定义候选；它不能写 cgroup / quota、不能冻结存储，且依赖 daemon 回收，因此不能冒充已完成的管理控制面或独立终止资格。

实际只读命令为 `docker image ls --no-trunc --format '{{json .}}'` 与对精确 Alpine ID 的 `docker image inspect`，均经现有 Python `3.14.5` 的 `subprocess.run(..., capture_output=True, text=True, timeout=8)` 调用，退出 0。image list 成功调用两次，用于筛选和紧凑核对，没有因失败自动重试。未保留其他业务镜像名称、完整 inspect、环境变量值或凭据。

| 保留的观察 | 实际结果与限制 |
| --- | --- |
| 本机 image list | 39 条；通用基础候选为无 tag 的 Debian 与 `alpine:3.23.5`。不是完整来源 / 接受库存 |
| 精确候选 ID | `sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40`，Linux / arm64；按 ID 固定，tag 只作观察 |
| 报告大小 / 层 | 14,468,568 bytes，一个 RootFS diff ID；不是压缩下载大小、独占磁盘成本或源码对应证明 |
| 配置 | Entrypoint / Volumes / Healthcheck 未声明，Cmd 为 `/bin/sh`，WorkingDir 为 `/`，User 未声明；执行候选须显式覆盖默认 root / 命令 |
| 其他配置字段 | 环境键值条目数 1、labels 数 0；未核定具体环境、applet、loader 或 timeout，不能写成已接受执行范围 |

筛选实际字段留在[镜像候选观察](cvc5-control-plane-2026-11-01/channel-image-candidate.json)；其中记录命令、目标及没有验收的项目。复取时必须另存新批次，不能覆盖本次观察或把 image ID、RepoDigest 与 diff ID 当成可互换身份。完整原始响应未留存，不声明其摘要或 registry 认证。没有 image save / export / pull / build，也没有创建容器。

筛选文件 SHA256 为 `2d6d2bd22959b77f1f590f2a4cb1a1ac7abd61ba0e34ea1435d757e5c555d3f9`；摘要只绑定这些元数据，不认证镜像内容或来源。

## 核定的具体边界

| 项目 | 本批形成的设计 |
| --- | --- |
| 权限 | `65532:65532`、capabilities 空、no-new-privileges、保留 daemon user remap、私有 PID / mount / IPC / UTS；只候选共享 cgroup namespace 的读可见性，不给宿主 PID、root、socket 或设备 |
| 只读输入 | 固定 Linux boot ID、filesystems、PID 1 mountinfo 与只读 cgroup 树；仅白名单和自身实例资源字段，不递归扫描工作负载。路径来源 / namespace 不明或权限拒绝即停止，不加特权 |
| 资源 / 输出 | 候选 128 MiB / swap 0、0.5 CPU、16 PID、64 FD；stdout 2 MiB / stderr 64 KiB、Mac 记录 8 MiB；不设卷 / 用户 tmpfs 或工作区，默认 runtime 挂载须读回计入资源，不运行构建 / solver |
| 时间 | 内部 timeout 候选 20 s，整批单调 90 s，第 50 s 前停止工作，后 40 s 用于有界管理请求和清理；不是 daemon 故障下的必达保证 |
| 清理 | 完整 CID / daemon / 本批 label / image 绑定；停住并留证后仅移除该实例，读回不存在；不删镜像 / 原材料、不 prune、不按名称误杀、不 force remove 或重启 daemon |
| 失败 | 流 / 身份 / 挂载 / 资源错误保留首错，超时也按可能仍在运行处理；清理未确认则未知残留、阻断新实例，不自动重试 / 换路线 |

资源数值属于待审执行候选，不是已批准额度或实际资格。镜像来源 / 包许可、完整采集脚本 / 编排、真实路径映射、内置 timeout 和限额尚未验收；Docker 自身元数据 / inode 写入没有已验收硬 quota，Mac RSS 未实测。方案显式保留这些限制；要求与构建同等硬磁盘和独立终止时，本候选仍不能执行。没有把只读诊断当成 ADR 0031 的默认豁免或自动接受新信任。

未来拟新增的采集 / 编排文件只在方案中定位，本批没有创建实现或测试占位。下一批可在不创建环境的范围内先审阅精确镜像内容 / 来源 / 许可和有界实现，完成实际参数与正负例后，再就精确诊断动作、资源和清理取得执行授权。诊断结果只用于决定具体存储 / 管理权限的后续可行性，不升级 G0、A1–A10、C1 / E0 / E4。

## 官方接口核对

核对 Docker [create](https://docs.docker.com/reference/cli/docker/container/create/) / [start](https://docs.docker.com/reference/cli/docker/container/start/)的分离、[run](https://docs.docker.com/reference/cli/docker/container/run/)的候选配置和 [bind mount](https://docs.docker.com/engine/storage/bind-mounts/)的只读 / source 约束；配置方向不代表本机已通过。OrbStack [file sharing](https://docs.orbstack.dev/docker/file-sharing)用于保留 Mac / Linux 路径来源问题，[isolated machines](https://docs.orbstack.dev/machines/isolated)用于区分新建 machine 与原 Docker 宿主权限，未选择该替代路线。一次 Docker logging 文档请求不可访问，未依赖其内容，也未扩大研究；`log-driver=none` 仍须在将来实际配置 / 内容审阅中核对。

另核对内核 [proc 文档](https://www.kernel.org/doc/html/latest/filesystems/proc.html)的其他进程信息权限：非 root 读取宿主 PID 1 mountinfo 不能仅凭 mode / bind 成功认定可用，作为执行前独立阻断，不自动加 cap、改 root 或改成宿主 shell。一次上游 proc 实现源码网页请求超时，未引用未取得的代码，也不以通用文档代替目标内核验证。

## 验证与交接

本批只改相关专题、当前状态 / 索引和静态审阅记录；没有实现、依赖 / lockfile、机器契约、Accepted ADR 或冻结规则 / 配方变化。不另跑无变化的 Rust / cvc5 Python 组件回归；仓库检查内置项目照常执行。

| 实际验证 | 结果与边界 |
| --- | --- |
| `python3.14 scripts/check-repo.py` | 完整通过，2,896 文件；使用已定位的 Python 3.14.5，无安装 / PATH 或检查器修改 |
| `git diff --check` | 通过；跟踪差异完整复核，未跟踪文件另核文本卫生 |
| 局部只读核对 | 8 个文件范围与空暂存区、18 处新增本地路径 / 锚点、UTF-8 / LF / 末尾换行 / 尾随空格、非执行权限、镜像 ID / 观察摘要及 not-accepted / false 状态通过 |

上述结果只是文档 / 元数据一致性，不是采集脚本测试、镜像内容 / 来源接受、真实路径 / 权限、timeout、配额或清理资格。

没有创建 / 启动 machine、容器、服务或探针，没有系统 / 权限 / quota / mount / 全局设置变更，也没有删除数据、运行 SDK / compiler / solver 或写入远程。没有新增后台进程、卷或需回收的运行实例；新增观察为筛选后的持久文档材料。前批 G0 已提交为 `e507d78`，本批方案未包含在该提交；最终工作区与未推送状态由交接消息报告。
