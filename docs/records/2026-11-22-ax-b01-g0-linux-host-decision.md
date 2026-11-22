# 2026-11-22 AX-B01 专用 Linux 宿主与 G0 通道评审决定

项目所有者于 2026-11-22 确认离线选型，并同意对该宿主单独评审。选定候选为一台由 Apple `Virtualization.framework` 承载的本机专用 Linux AArch64 虚拟机，配一条由 Linux 向 macOS 输出的单向 virtio 串行通道。适用范围仅为 AX-B01 的 `cvc5 1.3.4 / USE_POLY=OFF` 本地诊断路线。 [G0 原盘点](2026-11-01-cvc5-g0-capability-review.md) · [前次 G0 / L5 复核](2026-11-22-linux-channel-g0-l5-preflight.md)

## 候选范围

| 事项 | 已登记的选型和评审边界 |
| --- | --- |
| 同一 Linux 宿主 | 候选 OCI runtime、候选私有存储根和 Linux 监督进程须在同一虚拟机实例内，评审时绑定 macOS 启动进程、Linux 内核与 boot ID、实际 runtime、命名空间和 cgroup。OrbStack 既有读回只适用于原实例的观察范围 |
| 单向报告 | 固定的来宾启动程序只采集白名单中的 G0 元数据，经具名、非系统控制台的 virtio 端口向 macOS 输出一次有界报告。macOS 端只接收，`VZFileHandleSerialPortAttachment` 的 `fileHandleForReading` 为 `nil`。候选配置无 TTY、命令输入、网络设备或共享目录 |
| 私有存储与留证 | 首选固定容量私有块设备，隔开工作区和留证文件系统。沿原 20 GiB 构建预算核算文件系统元数据、实际新增副本、runtime 写入和已 unlink 但仍持有 FD 的文件。128 MiB 留证可用空间和独立 inode 余量计入全批，并与构建主体隔离。精确文件系统、设备归属、容量和 inode 硬限待读回和实测 |
| 写入隔离 | 启动材料和磁盘映像经 macOS URL 打开。须核定 macOS 进程身份和目录 / 文件所有权，验证普通开发进程无法替换启动材料或经其他路径改写映像。Linux 侧核对块设备、挂载、FD / 映射和写入主体，验证工作负载无法访问管理接口、留证根或已发布的只读输入 |
| 独立整树终止 | Linux watchdog 位于工作子树外，独占精确非 threaded 工作 cgroup 的终止句柄和资源预留。后续独立资格须验证 daemon 不响应时可经 `cgroup.kill` 终止工作树，确认 `cgroup.events` 的 `populated=0` 并回收受管子进程。串行端口只承担报告传输 |

离线选型核对了本机 macOS 27.2 SDK 的 `VZVirtioConsolePortConfiguration`、`VZFileHandleSerialPortAttachment`、`VZVirtualMachineConfiguration`、`VZLinuxBootLoader` 与 `VZDiskImageStorageDeviceAttachment` 声明。实际端口方向、启动字节身份、macOS 写入隔离和 Linux runtime 行为留待宿主评审与资格验收。 [控制面与资格要求](../query/solver-local-cvc5-control-plane-plan.md) · [ADR 0031 来源与信任边界](../adr/0031-local-cvc5-build-provenance-boundary.md)

## 宿主评审的下一项输入

先固定 macOS 宿主版本、启动程序和 entitlement、Linux kernel / initramfs / rootfs、OCI runtime 及其来源、摘要、许可与所需主体权限。明确候选磁盘路径和所有权、来宾挂载、报告白名单和字节上限。随后才能核定一次只读检查的精确权限、占用、时限、失败保留与清理对象。只读报告用于核对实例、挂载 / 文件系统、访问主体和 cgroup 能力，块与 inode 耗尽、写别名以及 daemon 失联后的终止各需实际资格证据。 [原控制面负向矩阵](../query/solver-local-cvc5-control-plane-plan.md#a3--a4--a7--a8-真实负向矩阵)

本次授权止于候选宿主的单独评审。创建、启动、挂载、实际探针，以及后续构建与求解各有独立执行授权。G0 维持 `evidence-insufficient-stop-before-wiring`，`build_ready`、`execution_ready` 和 `runtime_qualification` 均为 `false`。L5 的镜像接受、实际 `proc` / seccomp / bind、资源与清理证据仍待取得；本次登记未创建或运行虚拟机。 [L5 运行前条件](2026-11-22-linux-channel-g0-l5-preflight.md#l5-离线结果)
