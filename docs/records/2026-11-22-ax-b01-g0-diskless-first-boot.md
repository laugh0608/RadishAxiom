# 2026-11-22 AX-B01 G0 无盘首启制品与离线复核

承接 `f0d2acb` 的 [Alpine 发布验签](2026-11-22-ax-b01-g0-alpine-release-signatures.md)。本批固定首启源码、来宾字节、entitlement 与执行前检查，使用普通 Darwin 宿主读回并通过 Apple 配置对象校验。G0 状态为 `evidence-insufficient-stop-before-wiring`。没有实例运行回执，`build_ready`、`execution_ready` 和 `runtime_qualification` 均为 `false`。

## 制品与执行身份

| 项目 | 固定内容与实际结果 |
| --- | --- |
| Darwin 首启程序 | [host.m](../../scripts/cvc5-build-support/g0-first-boot/host.m) 由 Xcode `27.2 (27B52)` 的 Clang 与 macOS 27.2 SDK 构建为 81,728 bytes 的 Darwin arm64 Mach-O。最终 SHA-256 为 `ae3391bb1639f4675fa1102f19a5290b0043780ed50b59c29604b764858a65f3`，CDHash 为 `f4808ed9da8bb9e8f54875b8a230be0eb4f5a4cd`。实际复核只调用 `--offline`、`--check-report` 和 `--preflight-paths` |
| 内核与来宾 initramfs | `Image` 从已验签 Virtual ISO 定长解包，36,306,944 bytes，SHA-256 `a2cecb9b6fdbd83e87bd43c8040de67300d5b8dde1fc50c34714faa272888f17`。[来宾 init](../../scripts/cvc5-build-support/g0-first-boot/guest.go) 由 Go `1.26.7` 离线交叉构建，静态 AArch64 ELF 无动态段或解释器。initramfs 为 1,801,852 bytes，SHA-256 `a6fb5c3b93fe38dab1ab68e478501c723200e7ade9d8ef3af74947272b0a42cb`。归档只含 `/init`、同版 `virtio_mmio.ko`、`dev` / `proc` / `sys` 目录和两个基础字符设备节点。内建 PCI、console 和固定 MMIO 模块覆盖评审的传输输入，实际端口枚举与模块加载结果留待实测 |
| Entitlement | [entitlements.plist](../../scripts/cvc5-build-support/g0-first-boot/entitlements.plist) 及签名内读回均只含 `com.apple.security.virtualization=true`。本地 ad hoc hardened-runtime 签名由 `codesign --verify --strict` 验证，普通宿主上签名身份通过程序自身和 `validateWithError` 检查。 [Apple 虚拟化接口](https://developer.apple.com/documentation/virtualization/vzvirtualmachine) |
| 执行身份 | `--run` 固定选择 `_raxcg0` 及同名主组，要求非 root、非 admin、`/usr/bin/false` 登录 shell、实效 UID / GID 与账户一致，附加组至多主组。实际 `--preflight-paths` 退出 1，报告账户不存在。实际 UID / GID 仍待以单独授权的部署读回绑定 |
| 宿主路径 | 固定 `/private/var/db/radishaxiom/ax-b01-g0/`，现有 `/`、`/private`、`/private/var`、`/private/var/db` 的 POSIX 读回均为 UID/GID `0:0`、`0755`。候选根与 `boot/` 要求同样归属和模式，路径逐段拒绝符号链接与额外 ACL。`boot/` 中三个普通单链接文件由 `0:0` 所有，launcher 为 `0555`，`Image` 与 `initramfs.cpio.gz` 为 `0444` 且绑定摘要。`records/` 为专用账户所有、`0700`、无额外 ACL。专用根和子路径尚未建立，路径防写未授予实际资格 |

[构建入口](../../scripts/cvc5-build-support/g0-first-boot/build.py)使用留存原件、固定 Go / Xcode 及本机工具。独立输出路径冷重建一次，`Image`、initramfs 和签名后的 Mach-O 三者逐字节一致。首次编译拒绝了 SDK 禁用的 ObjC `new`，修正为指定初始化方法后通过。后续受限环境返回 `VZErrorDomain (2)`，原因是虚拟化不可用。同一最终制品在普通宿主以 `--offline` 复核返回 0。两次读回除配置校验结果外一致。

## 单次启动参数

| 维度 | 固定或实际离线读回的值 |
| --- | --- |
| 入口 | 受保护 `boot/g0-first-boot --run`，无路径、命令行和设备参数覆盖。Darwin 为 `26A434`，固定 `VZGenericPlatformConfiguration` 机器身份，关闭嵌套虚拟化。机器身份的不透明字节保留在配置回执 |
| 启动 | 1 台、1 次、1 vCPU、512 MiB 来宾可见内存，`VZLinuxBootLoader` 使用已绑定的 `Image` 和 `initramfs.cpio.gz`，固定命令行 `rdinit=/init panic=0 quiet`。无数据盘、网络设备、共享目录、socket、图形及额外设备 |
| 通道 | `org.radishaxiom.ax-b01.g0`，唯一具名非系统控制台端口，Mac 端 `fileHandleForReading=nil`。来宾按 sysfs 名称和字符设备号绑定，只写一帧，白名单覆盖架构、内核、boot ID、端口、四个只读伪文件系统和 cgroup 控制器 |
| 时间与留存 | 首启制品和权限预检完成后，在创建 VM 对象前启动 90 s 单调外层窗口，前 65 s 为工作窗，后 25 s 为清理预留。来宾采集与输出候选期限 8 s。串行字节上限 64 KiB，留存上限 256 KiB。实际启动前先独占并持久记录 `records/first-boot.jsonl`，以单次启动、来宾主动关机、宿主 stopped、EOF 和完整回执共同判定；超时或无法确认退出时保留未完成记录并阻挡下一次 |

离线阶段只构造和验证 `VZVirtualMachineConfiguration`。上述内存值是来宾配置，宿主峰值占用、求值时限和退出上界尚无实测。 [Apple 配置校验](https://developer.apple.com/documentation/virtualization/vzvirtualmachineconfiguration/validate()) · [Linux initramfs](https://docs.kernel.org/filesystems/ramfs-rootfs-initramfs.html)

## 验证与恢复条件

[离线复核入口](../../scripts/cvc5-build-support/g0-first-boot/review.py)独立核对归档清单、ELF、签名及配置字段。合法合成回执通过；重复键、双帧、缺结束符、超长、不同内核 / 端口、零 boot ID、可写 proc 和缺少 memory controller 共九项拒绝。另两项拒绝改动后的 initramfs 与符号链接内核。未启动虚拟机或容器，未执行 Linux 来宾制品，也未配置、构建或运行 solver。

最终制品和回执留在本机忽略目录 `.tmp/ax-b01-g0-first-boot-03/`。`build.json` SHA-256 为 `334413f7d3003903e264e14f9fcc446748a3e19fbd5e44d2bdc87c7ad8a813b4`，`ordinary-config.json` 为 `01c6ad71f6d0246ea8d9f7a81870f41d505a540a29f0a8a269c1bed911d0443a`，`sandbox-review.json` 为 `7ec332e4a7c007f4fdafd3d7af5f43e2b39f36c6f7a30206232920c29fe75658`，`path-observation.json` 为 `ef1d0d00d7d9c5dd74327eca044feca325bf37c31fadd189bd19a58ebc42ab51`。

恢复条件是单独批准创建并限制 `_raxcg0`、同名组与精确私有目录，将上述固定制品交付为指定所有权和模式。以实际专用身份重核有效 UID / GID、祖先路径、ACL、哈希及普通开发进程写入拒绝，才可另行授权一次无盘首启。首启的验收范围限单向回执、实际挂载、端口和同一实例退出。私有盘块 / inode 硬限、写别名、OCI 与 daemon 失联时的独立整树终止仍按原资格矩阵处理。 [宿主决定](2026-11-22-ax-b01-g0-linux-host-decision.md) · [真实资格矩阵](../query/solver-local-cvc5-control-plane-plan.md#a3--a4--a7--a8-真实负向矩阵)
