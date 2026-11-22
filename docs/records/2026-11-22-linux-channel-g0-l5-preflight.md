# 2026-11-22：G0 既有入口与 L5 运行前复核

本批沿 AX-B01 无 Poly 候选的诊断通道顺位复核。基线为 `dev` 的 `dd69233`。范围为既有入口、固定本机 OCI 镜像的只读元数据与本机留存材料。G0 维持 `evidence-insufficient-stop-before-wiring`，镜像维持 `not-accepted`，`build_ready`、`execution_ready` 和 `runtime_qualification` 均为 `false`。

## G0 管理入口与候选根

复用原 G0 盘点，未重复查询全部 machine、镜像或 daemon 信息。本次只在已有 OrbStack 进程可见、Docker 连接匹配固定本机 socket 后，按固定 image ID 获取 ID、系统、架构和 diff ID。该连接读回 `linux/arm64`，OCI index `sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40`，层 diff ID `sha256:91d5cf66444f05b8c72e1b9d725c1752b9b015b68a7918125fc46ecdb7cc46d5`，均与离线归档匹配。Linux 宿主身份、命名空间和底层文件系统仍缺实例证据。 [原 G0 观察](2026-11-01-cvc5-g0-capability-review.md)

OrbStack 的公开架构将 Docker engine 与 Linux machines 置于共享内核的同一 VM。`orb` 的 shell / `run` 面向选定的 machine，debug shell 面向容器，现有入口仍缺可核对到 Docker 宿主的管理上下文。OrbStack 同时提供 macOS 上的容器和卷文件编辑视图，因此必须对具体候选根核对写别名。 [架构](https://docs.orbstack.dev/architecture) · [Linux 命令](https://docs.orbstack.dev/machines/commands) · [调试入口](https://docs.orbstack.dev/features/debug) · [原生文件视图](https://docs.orbstack.dev/features/native-files)

| 待取得 | 恢复条件 |
| --- | --- |
| 同一 Linux 宿主的管理入口 | 指定可用入口、实例、管理主体与允许的读回范围，核对它与目标 daemon 的关系。现用 Docker socket 只提供本批镜像观察 |
| 私有根、块与 inode 硬限 | 指定同一宿主的候选路径及允许访问主体，再核定实际文件系统、挂载和可用硬限机制；实测失败与资格按独立授权处理 |
| 无未受控写别名、独立整树终止 | 核定 macOS 共享视图、daemon 管理者、继承 FD / 映射和辅助写入者的访问边界；取得树外 watchdog 对精确工作 cgroup 的独立终止与回收证据 |

若现有宿主未提供上述入口，先明确候选管理通道的目标、权限、占用上限、时限和清理范围，再作独立决定。拟议的单次普通诊断可以提供拓扑线索，其覆盖范围止于读回。 [G0 原恢复条件](2026-11-01-cvc5-g0-capability-review.md#g0-各项结果与停止决定)

## L5 离线结果

| 核对项 | 结果 |
| --- | --- |
| L4 交付 | 回执摘要、绑定的 83 个文件及模式通过复核。`runtime/` 仍只有既有 `0555` 的 AArch64 ELF，6,263,080 bytes。制品内唯一一份 9,717 bytes 采集正文与交付及仓库正文逐字节一致 |
| 固定镜像与 applet | 归档的 arm64/v8 manifest、514 项树、16 个安装包及 BusyBox / musl loader 的摘要复读匹配。`sh`、`awk`、`head`、`od`、`readlink`、`stat`、`uname` 七个既有入口均指向 `/bin/busybox`，固定上游配置启用相应 applet 与已核对的选项支持。实际 applet 行为、`ash` 的 `pipefail` 行为与目标进程权限仍待运行资格 |
| APK 摘要差异 | 109 项检查仍留存唯一差异 `alpine-baselayout-data` 的 `etc/shadow`。固定 minirootfs 的该条目与镜像层摘要一致，归档元数据为 UID 0、GID 42、`0640`。按 Alpine `v3.23.5` 成像脚本的密码锁定步骤在内存中反向变换唯一一次，SHA-1 从 `fdcce813d9a3aa27fffcf07126d2deabf17cb057` 恢复为 APK 声明的 `9a24457ba32e602580895c6a885ce175d7a006ae`，正向再变换逐字节恢复发布归档条目。证据只留摘要和元数据。 [Alpine 成像脚本](https://raw.githubusercontent.com/alpinelinux/aports/v3.23.5/scripts/genrootfs.sh#L33-L47) |
| 镜像内挂载目标 | `/mnt` 是空的 `0755`、UID / GID 均为 0 的目录，归档中无 `/host-observe`。实际 runtime 目标创建、Linux procfs / cgroupfs 身份、source 关联及只读和传播属性仍待核对 |

APK 差异已有可重放的字节解释，原检查器的差异分支和历史记录继续保留。镜像接受仍需发布者、构建关联与完整包来源和许可的精确处理。实际 L5 还需绑定目标内核及 Docker / OCI 策略，核清 `65532:65532`、用户映射、capability 全丢弃、`no-new-privileges`、有效 seccomp、四个白名单观察挂载及 `/mnt` 单目录 bind。尤其要核对 `/proc/1/mountinfo` 的 source、文件系统与普通 UID 读取权限，以及 cgroup 层级与只读条件。 [原镜像核对](cvc5-control-plane-2026-11-01/image-offline-inspection.json) · [来源与权限材料](cvc5-control-plane-2026-11-01/image-offline-materials.json) · [L5 参数和限额](../query/solver-linux-management-channel-minimum-plan.md#权限与输入的闭合范围)

候选仍为单 CID、一次启动、无网络、只读 rootfs、128 MiB / swap 0、0.5 CPU、16 PID、64 FD、启动器 20 s、Mac 总期限 90 s。提交可执行参数前须核定 Docker 元数据实际占用及停止界限、精确 CID 清理、宿主写别名与 daemon 失联处理。UID、挂载或策略的证据缺失继续挡住 `create` / `start`。 [交付方案](../query/solver-linux-channel-build-and-delivery-plan.md)

## 留存

本机忽略目录 `.tmp/linux-channel-g0-l5-20261122/` 保留 `targeted-image-readback.json`（SHA-256 `9c23e891aaad7c1d157f69f157f2edfad50f1a342a63c0eb5deb4f91a4cc172d`）、`l5-offline-preflight.json`（SHA-256 `3e1cc77f47ad74276b04e896a1c500cc26e442643c98897382c871620129f2b9`）与复核脚本。使用已安装的 Python 3.14.5 在内存中解析固定归档。未创建或启动 machine、容器或服务，未挂载或执行制品，也未安装、配置、构建或运行 solver。

真实归档重跑离线检查器得到与原回执一致的 JSON，保留预期退出码 `2`。镜像检查器现有 20 项测试、仓库基线检查和 `git diff --check` 通过。
