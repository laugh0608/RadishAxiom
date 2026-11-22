# 2026-11-22 AX-B01 专用 Linux 宿主输入与首次只读检查复核

承接项目所有者同意的 [G0 专用宿主评审](2026-11-22-ax-b01-g0-linux-host-decision.md)。本批核对 Darwin 宿主、Linux 启动来源、存储布局与首次只读检查范围。选择和静态结果只用于评审，G0 仍为 `evidence-insufficient-stop-before-wiring`。

## 宿主和启动来源

| 输入 | 本批复核结果与剩余条件 |
| --- | --- |
| macOS 与工具 | 本机读回 macOS `27.0.1 (26A434)`、Darwin `27.0.0 arm64`。固定 Xcode 路径读回 `27.2 (27B52)` 与 macOS 27.2 SDK。此身份是拟用宿主基线。启动器二进制、`com.apple.security.virtualization` entitlement、执行主体及实际框架加载仍须单独绑定。 [Apple Linux boot loader](https://developer.apple.com/documentation/virtualization/vzlinuxbootloader) |
| Linux 发布对象 | 选定并取得 Alpine `3.24.4` aarch64 的 Virtual ISO 和 minirootfs。两个实物重算 SHA-256 分别为 `cf88d8ba67389d20d9ed307366b52e487c15d7d3ee3233b62b95f709daa1d430` 与 `4b14c18f7e90a063b61462ea1462a5732c154bf6adad594974fe6487cd98a8de`，与官方发布声明匹配。该批留存两份分离签名和发布公钥，官网声明指纹为 `0482D84022F52DF1C4E7CD43293ACD0907D9495A`。 [发布目录](https://dl-cdn.alpinelinux.org/alpine/v3.24/releases/aarch64/) · [官方发布键](https://alpinelinux.org/downloads/) |
| 内核与模块 | 发布配置 `config-6.18.60-0-virt` 为 161,528 bytes，SHA-256 `b7643cddcd3ba109183a2aaafa3c911d91e7d89485fd7b2caf5ede9396bf78ca`。`VIRTIO_PCI`、`VIRTIO_CONSOLE`、cgroup、PID / memory controller、namespace 与 seccomp 为内建。`VIRTIO_MMIO`、`VIRTIO_BLK`、`EXT4_FS` 和 `OVERLAY_FS` 为模块。使用 Virtual ISO 同一发布的 `6.18.60-0-virt` 内核和匹配模块；分支索引的 `linux-virt 6.18.64-r0` 属另一版本。模块须绑定摘要、ABI 与依赖，根挂载前所需模块进入固定 initramfs。 [固定内核配置](https://dl-cdn.alpinelinux.org/alpine/v3.24/releases/aarch64/netboot-3.24.4/config-6.18.60-0-virt) |
| 启动时可执行字节 | 首次检查采用经审阅的自有 initramfs，固定启动程序从内存生成一次回执。官方 minirootfs 的归档读回显示版本 `3.24.4` 和 16 个安装包，用作后续用户态来源候选。首启的命令行、initramfs、端口配置和制品摘要仍待固定，minirootfs 的签名、包许可闭包和最终组合字节也待核对。 |
| OCI 运行时 | 沿 Docker Engine / containerd / runc 组合审阅。同批 aarch64 索引记录 `docker-engine` / `docker-cli 29.9.3-r1`、`containerd 2.3.7-r0`、`runc 1.4.4-r0`，均声明 `Apache-2.0`。已定位直接依赖中的 musl、libseccomp、iptables、tini 与 CA 包。索引署名、精确 APK 字节、递归依赖与许可仍待核；不在首次启动中启动 daemon。 [Alpine main 索引](https://dl-cdn.alpinelinux.org/alpine/v3.24/main/aarch64/APKINDEX.tar.gz) · [Alpine community 索引](https://dl-cdn.alpinelinux.org/alpine/v3.24/community/aarch64/APKINDEX.tar.gz) |

Virtual ISO 内 `boot/vmlinuz-virt` 为 10,412,544 bytes，SHA-256 `cd05fed9e617b5df93dc62ece9b78c422fd94e9b432a2f7c092714b139d5eef4`。在内存中按 zboot 头的范围解开 gzip，得到 36,306,944 bytes 的 AArch64 LE `Image`，SHA-256 `a2cecb9b6fdbd83e87bd43c8040de67300d5b8dde1fc50c34714faa272888f17`，头部和内置 release 与候选匹配。官方 `initramfs-virt` 的 307 项归档清单中已找到 `virtio_blk`、`virtio_mmio`、`ext4`、`overlay`、`jbd2`、`mbcache` 与 `crc16`。7 个文件的 ELF 架构及 `vermagic` 匹配，`ext4` 的声明依赖为 `jbd2`、`mbcache`、`crc16`。实际加载、内核符号和启动资格待核。 [Linux zboot 头](https://github.com/torvalds/linux/blob/v6.18/drivers/firmware/efi/libstub/zboot-header.S) · [AArch64 Image 头](https://docs.kernel.org/arch/arm64/booting.html)

## 存储与写入主体

- 候选宿主根为 `/private/var/db/radishaxiom/ax-b01-g0/`。本机路径尚未建立。拟由受信管理员保有父目录和 `boot/`，VM 启动由单独非管理员身份执行，仅获启动输入读权及本批 `batches/<id>/` 的写权。日常开发身份须对目录命名、文件替换、现有 FD 和磁盘映像写入实际受限；UID / GID、父路径、ACL、设备及 URL 目标身份均待读回。
- 本地 `work.raw` 候选采用固定长度的块设备和两个独立 ext4 文件系统，分别供批内工作与外围留证。工作主体只能访问已登记的阶段写区；留证文件系统提供至少 128 MiB 可用空间和独立 inode 余量。后续检查同时绑定分区范围、ext4 UUID、superblock 块 / inode 计数以及工作身份的可用计数。文件系统元数据、宿主后备文件的实际占用、新增副本与全部批次记录计入原 20 GiB 容量；虚拟逻辑容量不能单独说明宿主真实占用。 [ext4 计数定义](https://docs.kernel.org/filesystems/ext4/super.html)
- Docker `data-root` 与 containerd root / state 分别定位，其磁盘写入、快照、日志和卷都须进入已计量的存储范围。索引中的 `e2fsprogs 1.47.4-r0` 仅为待审工具候选，块数、inode 数、格式化参数和宿主 APFS 分配仍未核定。后续读盘需使用只读块设备，挂载确有必要时要求 ext4 `ro,noload` 并拒绝需恢复的文件系统。 [Docker 数据目录](https://docs.docker.com/engine/daemon/#configure-the-data-directory-location) · [ext4 日志回放](https://docs.kernel.org/admin-guide/ext4.html#options)

## 首次只读检查的候选范围

本次只登记可审阅的检查边界。第一次针对 Linux kernel、initramfs 与单向报告的启动候选为一台 VM、启动一次、1 vCPU、512 MiB 来宾内存，Mac 端 90 s 总期限含 25 s 清理预留。单份报告上限 64 KiB，本机留证上限 256 KiB。该次使用固定内存启动，无数据盘、网络设备、目录共享、来宾服务或 OCI 工作负载。端口为非系统控制台，`fileHandleForReading=nil`。任何报告缺失、重复、截断、身份漂移、超限或退出未确认均停止，保留首错和最后状态；无法确认同一 VM 已停止时暂停新的创建。 [串行附件接口](https://developer.apple.com/documentation/virtualization/vzfilehandleserialportattachment)

报告白名单限架构、内核 release、boot ID、已绑定的来宾端口身份、所需伪文件系统的类型和挂载读回、cgroup v2 控制器与可读能力。候选磁盘、OCI runtime 与硬限资格仍待后续独立读回，未观察字段明示缺失。实际布局、耗尽用例、写别名和 `cgroup.kill` / 回收资格沿[控制面负向矩阵](../query/solver-local-cvc5-control-plane-plan.md#a3--a4--a7--a8-真实负向矩阵)各自取证。

## 留存、当前阻塞和恢复

两个发布对象、两份分离签名、发布公钥、内核配置及两份索引共 100,696,883 bytes，留存在本机忽略的 `.tmp/ax-b01-g0-host-review-20261122/`。ISO 顺序读取首次到时限时留下 13,631,488 bytes，随后按同一 URL 和 ETag 的连续 HTTP 206 字节范围补全，并重算全包摘要。两份索引的 SHA-256 分别为 `f34aa54e8920921d3db09c0e03b9bdf54d52e7d430fc5dba1faaf564b80794bd` 和 `fe06b0b295bd4ae699860ae0333ba497d3d5cf4e490ee62587982cc270e708a5`。来源、归档及模块观察保存在以下回执中。

| 回执 | SHA-256 |
| --- | --- |
| `source-acquisition.json` | `b22b4d5bca29a98e415abf59eef53cc2fdabc489b958eb6d8a4dee3c44d53a0f` |
| `iso-range-recovery.json` | `b4002545460d95aacad0a4489f628c19518b64e8dc523fc05382856d4cf14369` |
| `static-release-review.json` | `48e0a14f8bdb6ed9f31c80ae426ad4a37a5833cf5718fcfa856344383aa4bcd6` |
| `ext4-module-dependency.json` | `09d7a47bf703146ae034c41b36402b70b50d84dbde53ff86fa5fb4ca9c396281` |

该批在检查过的本机命令与安装路径中未找到 `gpg` / `gpgv`。后续已使用本机缓存的 OpenPGP 库完成两份精确原包的验签与四个负例。接续审阅首启程序、签名与 entitlement、initramfs、固定端口、宿主执行身份和 URL 路径保护，完成精确检查授权后才可启动。`build_ready`、`execution_ready` 和 `runtime_qualification` 均为 `false`。本批未创建或启动虚拟机、容器或服务，未挂载镜像、安装包、执行来宾制品或运行 solver。 [发布验签](2026-11-22-ax-b01-g0-alpine-release-signatures.md)
