# 本地 cvc5：新 Linux 管理通道的最小方案

日期：2026-11-01。状态：**仅完成静态方案核定；推荐一次性只读诊断通道，未接受镜像、未创建环境、未授权执行**。用途：在 [G0 现有入口不足](../records/2026-11-01-cvc5-g0-capability-review.md)后，给出唯一下一候选的权限、资源、退出 / 清理与停止条件。读者为项目所有者、实施者和审阅者。本文只解决如何取得必要 Linux 读回，不提供常驻控制服务、构建或 solver 入口，不扩张 [ADR 0031](../adr/0031-local-cvc5-build-provenance-boundary.md)的信任 / 接受范围。现行顺位见[当前状态](../status/current.md)，实际静态核对见[本批记录](../records/2026-11-01-linux-channel-minimum-review.md)。

后续[离线核对](../records/2026-11-01-linux-channel-offline-review.md)已完成所选平台字节链、原 minirootfs 514 项相对树、16 包 / 10 配方的版本 / 许可声明及参考内核读取路径核对；APK shadow 校验差异和 SBOM 来源记录区分均保留。**仍未接受镜像或实际权限，且发现直接作为 PID 1 的 BusyBox timeout 不能提供原设想的内部强杀保证**；下文启动拓扑与根 cgroup 文件范围据此修正。没有创建或启动环境。

## 核定结论与选项

推荐在**同一 OrbStack Docker daemon** 上，另经授权创建最多一个短时、非 root、无 capabilities 的只读诊断容器。它只读固定的 Linux 内核 / 挂载 / cgroup 元数据并导出有界报告，随后停止并移除精确实例。使用 Docker 创建后，先检查未启动实例的配置，再启动固定采集命令；不进入交互式 shell，不开放 SSH / 端口，不安装服务。

这是新管理通道的第一步，**不是已经具备冻结、quota 设置或独立整树终止的管理器**。该步骤仍依赖 daemon 创建 / 回收，不能用于证明 daemon 失联时的独立终止。若读回表明未来管理器必须取得新的写权限或私有存储，这些目标再按实际对象给出精确方案和授权，不在本通道里逐步增加权限。

| 方案 | 本次判断 |
| --- | --- |
| 一次性非 root、只读诊断容器 | 推荐为唯一候选：同一 daemon、固定本机镜像、少量只读挂载、无持久卷；新增状态限一个可精确回收的实例 |
| 新建 OrbStack Linux machine / SSH 服务 | 暂不选：引入新的 rootfs、账户 / 服务、网络与持久磁盘，machine 内 root 也不能自动等同 Docker 宿主的管理权限；不直接解决原生文件视图与同宿主关联 |
| privileged 容器、宿主 `/` / socket 挂载、nsenter 宿主 shell | 不选：为少量读回授予可修改宿主的宽泛能力，不符合本步最小权限；失败不得自动切换此路 |

本方案允许把“诊断路径可用”“仍缺材料”或“所需权限超出范围”作为一次结束决定，不保证能仅凭这一容器闭合全部 G0。观察失败就保留具体原因，不重试、换镜像、加 cap 或另起机器。

## 固定目标与工具接受前置

目标仍为 G0 留存的 `orbstack` context / daemon `ad69e9f6-8215-4c61-96df-1178e1368456`、Linux AArch64。实际执行前重新核对 context / daemon / kernel；变化就停止重评，不沿用历史 boot 或 namespace 身份。

本机已有 `alpine:3.23.5` 被选为**待审诊断镜像候选**。只读元数据见[留存](../records/cvc5-control-plane-2026-11-01/channel-image-candidate.json)：image ID `sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40`，Linux / arm64，reported size 14,468,568 bytes，单个 RootFS diff ID；配置未声明 volume / healthcheck / entrypoint，默认命令为 `/bin/sh`。不借用另外的业务镜像或较大的 Debian 候选，不按 tag 启动，不 pull / build 镜像。

**元数据不是来源、许可或内容验收。** image ID、RepoDigest 与 layer diff ID 分别保留，不能因值相同就混同 config、manifest、index 或原始 blob 身份。执行前须限定审阅该精确镜像的导出内容、平台 manifest / 来源关联、实际包版本 / 来源 / 许可证，以及 BusyBox / loader 等将执行字节。未审阅软件不能仅因“本机已有”接受。若需要获取来源材料、导出制品或新增依赖，先列精确输入、留存大小和授权范围；不恢复全工具链取证。

实际离线链现已定位：原 Id 为多平台 index，arm64/v8 manifest 为 `d858bb5442632a31bd4bca6c5e601dbe6b536fd7942092ea6a08a0a95805693c`，config 为 `1087dfd14fa77fe3bd102f39d42ee9c7e183876bd1a65f38fe2c18198ae976b4`；[实际检查](../records/cvc5-control-plane-2026-11-01/image-offline-inspection.json)保留其余摘要、两份执行文件、初始 PATH 和库依赖。固定上游 rootfs 与镜像的相对树一致，但没有验证发布者签名或完整构建认证，不从数据核对直接转为 accepted。

采集器拟置 `scripts/cvc5-build-support/inspect_linux_host.sh`，只调用固定镜像内经审阅的 BusyBox applet；Mac 编排拟置同目录 `inspect_linux_host.py`，使用现有 Python 标准库和固定 Docker CLI。**本批不创建这两个代码文件。** 执行前须实现并审阅有界读取、固定 argv / 环境、输出解析、期限、精确 CID 和失败留存；核对 applet / timeout 在该版本的行为。脚本、镜像、CLI 身份和完整参数全部绑定后再请求一次执行授权，不发含占位 digest 的可运行命令。

## 权限与输入的闭合范围

| 能力 | 固定候选配置与必须读回的事实 |
| --- | --- |
| 身份 | 显式 `65532:65532`、无附加组、`--cap-drop=ALL`、`no-new-privileges`；保留 daemon user namespace 策略，不使用 `--userns=host` 解除 remap。记录实际 UID / GID / 映射，缺权限就结束，不改 root |
| 执行 | 只执行自有采集器及已审 applet；显式覆盖 image 默认入口 / 命令，使用 `env -i` 的闭合环境（仅 PATH、LANG、LC_ALL、TZ）。首个 applet / loader 在清环境前已经启动，故须先核定 image / create 的有效环境，拒绝加载器注入及未知键，不能仅凭 `env -i` 追认。无 TTY、无交互 stdin、无 init / healthcheck 隐含载荷、无后台任务或任意用户命令 |
| 网络 / 设备 | `network=none`、IPC `none`、不映射端口、不传额外设备 / credentials / agent / daemon socket；不继承宿主环境。不关闭默认 seccomp，不给 mount / ptrace / BPF 能力 |
| namespace | 保留私有 PID / mount / IPC / UTS；仅候选 `cgroupns=host` 用于读实际 cgroup 路径，明确增加 cgroup 层级可见性。不能据此声称进入宿主 PID / mount namespace；若 daemon 策略不允许，拒绝而非关闭 user namespace 或启用 privileged |
| 文件系统 | rootfs 只读，无 volume、无额外用户 tmpfs / `/dev/shm`；默认 `/dev` 等 runtime 挂载须逐项读回并计入资源，不能称为完全无 tmpfs 或零可写状态。不挂宿主 `/`、`/usr`、用户目录、SDK、源码、构建树或整个 `/proc`。采集脚本作为固定 argv 的字面代码传入，不挂整仓库，不用 shell 插值组装 Docker 命令 |
| 记录 | 报告只经有界 stdout / stderr 传到 Mac；`log-driver=none` 避免 daemon 再复制工具日志。Mac 另存本批配置、CID、退出 / 清理结果与报告；无容器内持久输出目录 |

容器外的 Docker 客户端仍持有 daemon 管理能力；诊断进程不持有该 socket。剩余信任为精确镜像 / applet、自有采集与编排、Docker CLI / daemon、OrbStack 与内核；不能抵御恶意管理员或把同用户进程自动视为可信。报告中的 Linux 路径和身份属于事实材料，不是宿主 root 授权。

### 只读挂载和采集白名单

宿主 source 由 daemon 解析；OrbStack 存在 Mac 路径共享，因此**不能只凭 source 字符串认定它来自 Linux**。下列均为候选固定 source；使用显式 `--mount type=bind,readonly`，禁止 `-v` 和自动创建 source。目录挂载要求 `rprivate`、显式递归只读；不支持或读回不符即停止，不用默认 best-effort 替代。

| Linux source → 诊断路径 | 只准读取的内容 / 大小上限 | 不能推出的结论 |
| --- | --- | --- |
| `/proc/sys/kernel/random/boot_id` → `/host-observe/boot-id` | 一行 boot ID，4 KiB | boot 相同不能单独证明根 / namespace / 挂载相同 |
| `/proc/filesystems` → `/host-observe/filesystems` | 内核登记的文件系统类型，64 KiB | 支持某类型不代表候选根已用该类型或已启用 quota |
| `/proc/1/mountinfo` → `/host-observe/init-mountinfo` | 同一 Linux 宿主 PID 1 的挂载信息，最多 1 MiB；只导出根、cgroup 及与后续明确候选根相关的非敏感字段 | PID 1 的 mount namespace 不一定等于 daemon 的；这份报告不能独立定位全部实际存储。身份 / 来源不明就报告缺口，不切 `--pid=host` 或读取任意 PID |
| `/sys/fs/cgroup` → `/host-observe/cgroup` | 根层只读 controllers / subtree_control 等定义在根的文件及挂载属性；type / events 与非根限值只在已核对的**本诊断实例非根 cgroup**读取，合计最多 256 KiB，不递归枚举其他工作负载 | 参考实现将 cgroup.type / events 标为 NOT_ON_ROOT，不能要求真正根层存在，也不能把任意 ENOENT 当正常。存在 / 可读不等于可写或 kill 生效；不试写 limits、kill 或建目录 |

此外只读容器自己的 `/proc/self/mountinfo`、`cgroup`、`uid_map`、`gid_map` 和 namespace 链接、固定 uname / 身份字段；逐项记录真实读取错误。对 `/host-observe` 的挂载类型、read-only 与 source 关联交叉核对，拒绝 regular file 冒充 procfs、未知中间链接、缺挂载、source 自动创建或与目标内核不符。绑定不同文件仍不构成一次原子快照，报告采集顺序和时间窗口。

挂载报告只保留上述目标对应的 mount ID / parent ID、设备号、文件系统类型、root / mountpoint 和只读标志；不保留任意 source、super options、其他工作负载路径或未筛选原文，以免带入网络挂载凭据 / 私有路径。错误只报告字段和原因，不回显原行或完整环境；格式不认识就拒绝，不保存“方便以后分析”的完整宿主快照。

非 root 读取宿主 PID 1 mountinfo 可能被内核权限拒绝，source 也可能不按预期映射；本方案不假设它一定可用。**权限拒绝就是本候选的有限结果，不加 `CAP_SYS_PTRACE`、不改宿主权限或 bind 整个 host root。** 不读取进程命令行 / environ、凭据、文件内容库存或未知设备。

内核 [proc 文档](https://www.kernel.org/doc/html/latest/filesystems/proc.html)明确区分自身与其他进程信息的权限要求。执行前须沿目标内核 / runtime 的固定路径核清这一单文件绑定的实际读取条件；目前未取得该依据，不能以文件 mode 或 bind 成功假定可读，也不安排一次预期会失败的试跑。若必需更改 UID / capability 或导入新的宿主采集服务，结束本候选的实施准备，另作精确权限 / 信任范围决定，不能在一次授权内自动提权。

后续 v6.18 固定源码参考显示：mountinfo 是 `S_IRUGO` 文件，其 `mountinfo_open → mounts_open_common` 并无统一 ptrace 检查；进程目录的 hidepid / permission 与对已绑定单文件的 open 是不同环节。因此不能从通用文档直接断言需要 CAP_SYS_PTRACE。boot_id / filesystems 参考入口为只读，cgroup 文件权限按方法生成；精确 `7.2.12-orbstack` 的实现 / LSM、source 解析与真实挂载关联尚未取得，不把 v6.18 当成本机资格。

本步不挂 `/var/lib/docker` / 任意现有卷来猜测存储根，也不调用 quota 设置或挂载操作。它只能提供文件系统 / cgroup 拓扑线索；实际候选根的 statfs / hard quota / 防写及独立控制授权仍须在对象明确后收口。

## 资源占用与时间预算

以下是待执行审阅的**候选上限**，没有实测或资格保证；不重解释原构建 8 GiB / 20 GiB / 5,400 s，也不改变 solver 128 MiB / 6 s。诊断期间不运行构建或 solver，不把它变成长期树外辅助服务。

| 项目 | 候选数值、作用范围与限制 |
| --- | --- |
| 数量 / 寿命 | 最多一个新容器、一次启动，无 restart policy、无自动重试；正常目标为数秒内完成，整个批次最多 90 s（含创建、读回、采集和清理请求） |
| Linux 内存 / swap | `memory=128 MiB`，memory-swap 总额同为 128 MiB，即候选 swap 0；启动后读实际 cgroup 限值 / events。不能将 Docker 参数存在当作已强制 |
| CPU / 进程 / FD | `cpus=0.5`，`pids-limit=16`，`nofile=64:64`；计入启动器 / timeout / shell / applet 的全部进程与线程。除已审监督 / 计时 / 回收子进程外不派生后台任务，不并行扫描；超额 / OOM / 被拒绝即失败，不增限重跑 |
| 文件写入 | rootfs 只读、无新卷 / 用户 tmpfs、采集器不写盘，默认 runtime tmpfs 等计入内存。Docker 仍创建容器元数据 / writable layer 对象，`read-only` 不等于零磁盘或零 inode；这部分没有已验收硬 quota。执行前须说明并接受该有限诊断新增状态的计量 / 停止边界，不能冒充构建硬磁盘资格 |
| 镜像 / 数据 | 使用已在本机的固定候选，不复制 / pull 镜像；reported 14,468,568 bytes 不是实际独占磁盘占用。输出 stdout ≤2 MiB、stderr ≤64 KiB；Mac 新增记录总额 ≤8 MiB，超限保留已有字节与 overflow，不伪称完整 |
| 内部 / 外部期限 | 内部 20 s 保持候选目标，但 BusyBox timeout 不能直接位于 PID 1 并用同 namespace watchdog 强杀自身；必须按下文修正启动拓扑，再验证实际语义。Mac 同一单调 90 s 截止、单次管理请求 8 s、启动 / 输出采集 20 s 均不续期，不是当前资格保证 |
| 清理预留 | 最迟在第 50 s 停止工作，后 40 s 留给精确 CID 的 kill / wait / remove / inspect，每项仍受剩余总期限约束。不承诺 daemon 无响应时能在 90 s 清空：届时必须报告未知残留、禁止新实例，不能重启 daemon 来“修复” |
| Mac 端 | 一个有界编排 / 捕获进程，常驻缓存只保留上述流上限，不缓存整个镜像 / 宿主文件；自身 RSS / daemon 元数据占用尚未实测，不宣称端到端内存硬限已验收 |

本通道的收窄在于运行已审只读采集器，没有不可信构建负载，也不接受其输出为完整资格；它仍需明确接受镜像来源、诊断元数据计量和 daemon 故障下无法独立确认清理的限制。若要求执行前就具备与构建相同的块 / inode 硬限及独立终止，当前候选不能提供，保持不执行，不把该限制静默当豁免。

### 内部超时启动拓扑的必需修正

精确 BusyBox `1.37.0` 源码显示 timeout 以 grandchild watchdog 监控原 PID，再在原 PID exec 目标。结合 [PID namespace 信号规则](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html)，直接将这条 exec 链放在容器 PID 1 时，同 namespace watchdog 的 SIGKILL 不能成为强制期限。该结果是静态审阅，不是本机故障复现；原直接入口方向保持停止。

最小修正限定为自有启动器保留 PID 1 的监督 / 回收角色，将 timeout / 采集器置于非 PID 1 子进程，等待该精确子进程并保留真实退出，然后收束、退出；不得因 shell 最后一条命令的 exec 优化丢失 PID 1 角色。具体实现、信号 / 孤儿回收、PID 身份、超时 / 取消 / 超额负例尚未形成，进程仍计入 16 PID / 128 MiB，不自动加入未审 `--init`、新依赖或 cap。此修正不提供 daemon 失联时的独立管理能力。

## 生命周期、清理与失败留存

以下是未来可授权的顺序，**本批没有执行任何 create / start / kill / remove**。实施后须先导出确切结构化 argv / 参数和边界检查，再取得执行授权；不把此表转换成自动执行 runbook。

1. **准备。** 接受精确镜像 / applet / 脚本，绑定当前 context / daemon / 规则和唯一批次标识；本机独占创建记录文件，确认容量、无相同任务实例。若镜像缺失、source 不明或目标已变，停止；无 pull 或配置补救。
2. **创建后读回。** 只创建一个指定名称 / 本批 label 的容器并保留完整 CID；不用 `--rm`，以免失去失败状态。创建本身已是环境写入，必须另获授权。通过完整 CID 核对 image、原 argv、挂载、UID、cap / security、namespace、资源、日志与重启策略；任何漂移都不启动，只保留并走精确清理。
3. **一次启动与捕获。** `start --attach` 对该 CID 启动已审 PID 1 启动器及非 PID 1 采集子进程，无交互输入；读取有界双流。采集器先检查自身身份 / 限值 / mount，再读白名单；缺事实报告缺失，不填假的零值或成功。超时、取消、超额或观察错误保存首错并转清理。
4. **停止与留证。** 在剩余期限内向同一 CID 请求 kill / wait，留存真实退出 / 信号、OOM / 错误和状态，再对照身份。启动请求超时后也可能已有实例运行，不能把客户端退出当作容器退出。内置 timeout 不是独立管理器的资格证明。
5. **精确移除。** 仅在该 CID / daemon / 本批 label / image 一致且已确认停止后，移除该单个容器，不带 volume 删除、不删镜像、不 prune、不批量按名称清理。移除后按 CID 读回不存在；原镜像、原输入和所有报告保留。Docker 侧 stopped / absent 只说明 runtime 观察，不能代替 A8 的 Linux 整树与回收资格。
6. **未知残留。** daemon 请求无响应、身份不一致、CID 未留全、退出或移除未确认时，记录现存精确身份 / 最后观察和未知项，封锁下一次创建；不 force remove、不重启 OrbStack / daemon、不删全局路径。恢复后先只读重核同一 CID，再对精确对象请求清理授权；不能杀同名替代实例。

采集端只读输入；若实际发现对 host source 的写入、意外网络 / FD / 挂载 / 执行、异常 namespace 或超出预算，则本候选失败。用前后摘要一致不能掩盖意外写入。Linux 内核、daemon 与管理者仍属 trusted，单一 daemon 自报的 inspect / wait / remove 不是三个独立信任源。

## 验收出口与下一步

静态方案及镜像 / 来源 / 许可声明的离线核对已有实际结果，**仍不接受新信任、镜像或诊断执行例外**。下一切片围绕已定位的 PID 1 启动器 / 回收拓扑、精确宿主读取权限关联和剩余来源 / 许可接受收口，不重复完整清单或直接运行原 timeout 入口。自有采集 / 有界编排与正负例另行核定实现，随后才就确切诊断范围和执行作决定；不先创建环境试错。

真实执行如果另获授权，必须分别报告：创建 / 配置读回是否一致；采集是否真实完整；宿主 / namespace 来源是否可定位；资源 / 退出 / Docker 清理各自观察与缺失。身份 / 数据矛盾为失败，缺失为未取得，不合成为资格 success。只能用结果决定同宿主后续具体根 / quota / 控制权限的可行性，不能把本次读回写成 A3 / A4 / A7 / A8 或 C1 / E0 / E4 通过。

接口依据为 Docker [create](https://docs.docker.com/reference/cli/docker/container/create/) / [start](https://docs.docker.com/reference/cli/docker/container/start/)、[run 参数](https://docs.docker.com/reference/cli/docker/container/run/)和 [bind mount](https://docs.docker.com/engine/storage/bind-mounts/)文档，以及 OrbStack [卷 / 路径共享](https://docs.orbstack.dev/docker/file-sharing)。这些文档仅支持配置方向，不证明本机权限 / 路径翻译或时限已验收。新建 machine 的替代成本依据 [isolated machines](https://docs.orbstack.dev/machines/isolated)的范围说明；本批不选择或创建 machine。
