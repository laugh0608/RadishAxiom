# 2026-11-01：本地 cvc5 控制面与真实资格方案审阅

日期：2026-11-01（Asia/Shanghai）。用途：留存本批代码 / 文档核对、只读宿主观察、完成边界和结束决定，供后续实施者追溯。不提供执行授权，不是工具接受、OS qualification、正式 Evidence 或程序证明。现行方案见[控制面接线专题](../query/solver-local-cvc5-control-plane-plan.md)，统一顺位见[当前状态](../status/current.md)。

## 范围与起点

项目所有者在了解当日建议后要求按计划推进，本批范围为控制面 / 输入冻结的方案核定、真实验收矩阵、成本与停止条件，以及相关文档和仓库检查。未把该要求扩成真实接线、SDK 组装、容器 / VM 启动、探针、构建、solver、提交或远程操作。

开始时 `git status --short --branch` 为 `## dev...origin/dev`，暂存区、工作树与未跟踪文件均无改动；基线 HEAD `5c3c450`。这是相对本地跟踪引用的状态，没有 fetch 或核对实时远端。

最小事实链为当前状态、开发计划、ADR 0031、阶段计划、v0.2 离线规则、接线设计与 A1–A10；实现侧核对现有 Python 入口 / 阶段 / 事件 / 截获 / 链接材料，以及 F2 的 FD 与 setup 边界。未展开兄弟项目、完整工具链来源研究或正式实验。

## 已形成的具体结果

- 新专题承接已有阶段计划的后续细节，给出固定宿主候选、权限与写入口、收束 / 盘点 / 发布 / 消费顺序、具体复用函数与拟修改位置。旧专题和索引只增加导航与接续，不建立第二套接受规则。
- 明确现有 `check_declarations` 认证不了 `frozen` 等声明，构建可写的 `capture_link.py` 观察不是外围收据，现有 `link_materials.check` 也没有实际 map / trace 或完整隐式输入验收能力。它们保留原私有 / 离线职责。
- A3 / A4 / A7 / A8 的执行矩阵列明正例、宿主替换、可写别名、继承写 FD / 映射、延迟后代、记录伪造、挂载遮盖、资源超额及失联 / daemon 故障的注入主体、预期、拒绝时点和留证 / 清理条件；**这些资格均未运行**。
- 原 4–8 人日低置信度估算拆为接线 2–4、资格 1.5–3、独立来源复核 0.5–1 人日；G0 另建议最多 0.5 人日等效投入到明确结束决定。没有可靠历史工时账，不把建议写成已耗时或批准额度，不承诺维护预算足够。

阶段计划已为 16,000 bytes，旧接线设计为 22,504 bytes；将本次完整接线职责单列到同一 query 专题目录，并从原入口引用，避免继续把历史实现与未来资格细节叠入旧文档。没有修改根入口、Accepted ADR、公共规范、机器契约或被实现摘要绑定的 v0.2 离线规则正文。

## 只读宿主观察与复核边界

实际执行 `docker context show` 和 `docker info --format '{{json .}}'`，每条通过 Python `subprocess.run` 设置 8 秒超时、捕获输出；初次用于判断，随后重复一次筛选并独占写入[留存 JSON](cvc5-control-plane-2026-11-01/host-observation.json)。两次筛选结果一致。只保存其中 `method` 和 `reported` 指定的字段；完整 daemon 响应未留存，不宣称已绑定未保留原文。所有调用只读，没有改变 context、启动服务 / 容器或选择已有镜像。

复跑入口是 JSON 的 `method.commands`，按 `reported` 的键筛选第二条命令的 JSON 输出。应另存新日期 / 批次，不覆盖本文件；本报告既不是可变宿主的永久身份，也不认证当前真实隔离实例。

筛选留存文件 SHA256 为 `aa938a3c38a8505153fcd6a25d1aa8afeb4bd550ea94c5d7b261f5428f39ffba`；该摘要只绑定本文件，不代表未留存的完整 daemon 响应或实际宿主状态。

| 观察 | 本批结果与限制 |
| --- | --- |
| context / daemon | `orbstack`；ID 与 10 月 17 日相同，server `29.8.2`；不据此继承旧资格 |
| 架构 / 内核 | `aarch64`；`7.2.12-orbstack-00394-gbecdd6130068`，不同于历史 `7.2.9-orbstack-00391-g2b298d05fbd4` |
| cgroup | v2 / cgroupfs，daemon 报告 memory / swap / pids 支持；没有实例读回、强制负例或 kill / 回收观察 |
| 存储 | `overlayfs`、`io.containerd.snapshotter.v1`；没有底层文件系统、quota、独占权限、实际卷或预留证据，不推断为 overlay2 / XFS |
| runtime | `runc` 为默认值；未查询 / 接受实际执行 binary、镜像、SDK 或 UID 映射 |

依据官方 [Docker 卷](https://docs.docker.com/engine/storage/volumes/)和 [daemon 安全](https://docs.docker.com/engine/security/)说明，方案保留多挂载写入口与管理 API 权限审阅。官方 [cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)、[quota](https://www.kernel.org/doc/html/latest/filesystems/quota.html)及 [Docker run](https://docs.docker.com/reference/cli/docker/container/run/#set-storage-driver-options-per-container---storage-opt)用于核对接口职责，不作为本机能力证据。一次 XFS 专题网页请求返回不可访问，未以其内容得出结论，也未因此继续追索另一套存储路线。

本批未读取 LibPoly issue 最新答复、发送消息或重跑许可历史核对。仓库的许可待接受状态保持，不断言上游目前是否已有新回复。

## 验证

| 实际检查 | 结果与边界 |
| --- | --- |
| `./scripts/check-repo.sh` | 首次退出 1：登录 shell 的 `python3` 优先命中 Xcode Python 3.9，已有生成器的 `dict[…] \| list[…]` 类型表达式报 `TypeError`，launcher 的 `TypeAlias` 导入亦失败；不是本批文档造成的语义漂移 |
| 解释器定位 | `type -a python3 python3.11 python3.12 python3.13 python3.14` 找到现有 mise Python；`python3.14 --version` 为 `3.14.5`，未安装或修改 PATH / 系统配置 |
| `python3.14 scripts/check-repo.py` | 通过，2,891 文件；调用同一完整检查器，保留生成一致性、契约与内置 launcher 检查，没有跳过失败项目或修改兼容代码 |
| `git diff --check` | 通过；新增未跟踪文件另核文本卫生，最终完整差异及路径复核后交接 |
| 局部只读复核 | 8 个修改 / 新增文件范围准确、暂存区为空；30 处新增本地链接 / 锚点、UTF-8 / LF / 末尾换行 / 尾随空格、非执行权限、观察摘要及 false 状态均通过 |

没有代码 / 依赖变化，未另跑 Rust 或 cvc5 Python 组件回归；仓库检查内置项目按上述命令执行。没有 Linux 目标构建、真实 syscall / OS 资格、A1–A10 全矩阵、SDK 组装 / 配置 / 编译 / 链接、solver、CI 或独立程序语义 checker 运行。

## 结束决定与交接

本批方案与资格设计交付结束。**目前不能给真实接线开工结论**：底层存储与块 / inode 硬限、独占写权限、独立于 daemon 的终止通道、PID / inode / 时间参数未闭合。下一批只按 G0 核定这些现有能力；有证据才细化接线，证据不足则精确交接，不自动安装后端、起特权服务、扩信任、增限或加模拟。

G0 的检查程序 / 权限 / 时限 / 留存 / 清理须先具体化，再取得需要的执行授权；这不延续历史授权。C1 许可、组装差异、真实环境资格、每批执行授权、C4 / E0、E4 / E5 仍分别成立。旧 v0.1 默认、冻结配方 / 规则和拒绝保持，`build_ready=false`，原容量 / 1 MiB 与 solver 128 MiB / 6 s 不变。

没有新增依赖或修改 lockfile、实现、机器契约；没有系统 / 权限变更、安装、容器 / VM 启动、远程写入、提交或 push。本批没有后台进程或待清理运行实例，新增宿主观察为筛选后的持久文档材料；已有包与失败材料未动。最终工作区状态由交接消息报告。
