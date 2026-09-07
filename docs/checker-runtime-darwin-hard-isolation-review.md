# Checker runtime Darwin 强隔离架构审阅单

状态：synthetic Linux microguest feasibility 已在单一 Darwin / arm64 主机通过；真实 checker、产品化 TCB / 身份迁移与 qualification 仍阻断
审阅日期：2026-09-03

## 目标与结论

本审阅承接 [Darwin process isolation 原语审阅](checker-runtime-darwin-process-isolation-review.md)，比较 App Sandbox、受权 broker、`Virtualization.framework` 与 `Hypervisor.framework` 能否在不弱化现行 hard boundary 的情况下闭合 Darwin checker execution。架构选择阶段只运行无 VM 合成 helper；ADR 0013 接受后的两个独立 feasibility 切片先后在精确临时根中运行 synthetic bare-metal microguest 与最小 Linux microguest。两者都只使用临时 ad-hoc 签名和合成 guest，没有注册 service、修改系统设置 / 公共格式或执行 checker。

结论由 [ADR 0013](adr/0013-darwin-checker-hard-isolation.md)正式冻结：

- native `posix_spawn` supervisor 和单独 App Sandbox helper 都不能同时形成 hard memory 与不可逃逸 process-tree containment；
- privileged broker 会引入管理员批准、持久系统状态和 root TCB，公开原语仍未补齐 process tree，因此不采用；
- `Virtualization.framework` 可表达 128 MiB、零 network device 和只读 directory share，但 URL boot / image / share 入口没有关闭现行 descriptor identity 到实际 execution bytes 的缝隙，只保留为 feasibility 对照；
- 唯一进入实施候选是 per-invocation、signed、App-Sandboxed 的 Hypervisor runner：从已打开 descriptor 将 guest TCB、checker 与 bundle 装入固定映射，不实现 network / writable host device，并在每次请求后销毁 VM；
- 当前 Mach-O payload 保持 inactive；Linux kernel / minimal init、真实非特权进程与后代、syscall 拒绝、128 MiB guest RAM 和 6 秒 cold deadline 的合成动态证据已经物化，但真实 checker / bundle、生产 runner / guest TCB、公共身份迁移和 qualification 仍未物化。

## 审阅环境与边界

| 项目 | 当前观察 |
| --- | --- |
| 主机 | macOS `26.6.2` build `25G83`，Darwin `25.6.0` arm64 |
| 开发工具 | Xcode `26.6` build `17F113` |
| SDK | macOS SDK `26.5` |
| 源码 / 头文件 | 本机 macOS SDK 的 Security / Virtualization / Hypervisor / spawn 公开头文件，Apple Developer Documentation，Apple OSS XNU `main` |
| 动态输入 | 架构阶段两个合成程序与空 share；feasibility 阶段自行生成的 supervisor、ad-hoc App bundle runner、bare-metal arm64 guest，以及从官方 Alpine 3.24.1 release descriptor-fed 装载的 Linux kernel 与自行生成的 minimal initramfs |
| 未触及 | checker / payload、产品根、真实 bundle、生产签名、Service Management、qualification、activation、真实网络、公共格式与远程状态 |

本审阅只支持架构选择和当前单主机 synthetic feasibility，不证明其他 macOS / SDK、Intel、实际签名产品、production guest kernel acceptance 或六平台行为。

## 公开原语核查

### App Sandbox 与 signed helper

[App Sandbox](https://developer.apple.com/documentation/security/app-sandbox)是 entitlement 驱动的 kernel containment，可以拒绝未授予的 network / filesystem 能力。Apple 对 sandboxed app 中 helper 的公开说明要求明确签名 / entitlement / embedding 关系；当 helper 需要与 parent 不同的能力集合时，应使用独立 XPC service、login item 或 helper app，而不是假设直接 child 自动获得更窄 profile。

[Accessing files from the macOS App Sandbox](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox)与[配置 macOS App Sandbox](https://developer.apple.com/documentation/xcode/configuring-the-macos-app-sandbox)都明确说明，sandboxed app 首次启动时系统会在 `~/Library/Containers` 创建并关联 container。[受 container 保护的本地 app data](https://developer.apple.com/documentation/xcode/protecting-local-app-data-using-containers)还说明该 data container 受系统保护。当前公开配置没有“保留 App Sandbox policy 但禁用 app container”的开关，也没有普通 parent 可用于逐次原子销毁受保护 container 的 API。

它能作为 runner 的外层最小宿主，但不提供以下保证：

- 没有 `128 MiB` physical working-memory hard limit；
- 不把 fork / exec 后代放入可整体销毁的资源容器；
- 直接 inherit 还会继承 parent 的 sandbox 能力，未必等于 readonly-bundle-only；
- 当前 standalone checker 的签名 / entitlement 不在 registration、receipt 或 qualification 身份链中。

继承型 command-line helper 不能修复该冲突。Apple 的 [sandboxed app helper](https://developer.apple.com/documentation/xcode/embedding-a-helper-tool-in-a-sandboxed-app)要求 child 只带 `com.apple.security.app-sandbox` 与 `com.apple.security.inherit`，其静态能力来自 parent；这个受支持配置没有 helper 独立 Hypervisor entitlement 的位置，若依靠继承取得该能力就必须扩大 parent entitlement，不能保留当前 runner 独立的两项 profile。XPC service 虽可独立配置 entitlement，但由 `launchd` 按需管理，并具有自己的 sandbox 与 container；它改变 runner process / lifecycle / identity 边界，也不消除持久状态。

Security framework 的 `SecCodeCopyGuestWithAttributes` 可按 PID / audit 等属性取得 running code；`SecCodeCheckValidity` 与 `SecCodeCopySigningInformation` 可复核签名并取得 `kSecCodeInfoUnique`。SDK 将该 unique identity 描述为能唯一识别特定 static code 的 opaque bytes，同时明确算法未来可变，因此不能把当前长度或 hash 算法写死为公共兼容键。

### Privileged broker / service

[Service Management](https://developer.apple.com/documentation/servicemanagement/) 和 `SMAppService` 可安装 / 管理 launch agent、login item 或 launch daemon；launch daemon 路径需要用户 / 管理员批准并形成 System Settings / 系统 service 状态。这与当前无系统状态、用户级私有 runtime 的边界不同。

Apple OSS XNU 的 [`task_set_phys_footprint_limit`](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/kern/task.c#L7114-L7138) 在调用前执行 `proc_check_footprint_priv`，失败返回 `KERN_NO_ACCESS`，源码还注明该调用可能应被废弃。即使 privileged broker 可越过该门禁，公开 API 仍没有给出与 Windows Job Object 等价的不可逃逸 process-tree container；组合 root broker + process-group polling 不能作为完整 hard boundary。

### `Virtualization.framework`

当前 SDK 的公开头文件和 Apple 文档确认：

- `VZVirtualMachineConfiguration.memorySize` 是 guest OS 看到的 physical memory，必须位于公开 min / max 之间且为 1 MiB 整数倍；
- `networkDevices` 默认为空；
- `VZSharedDirectory(url:readOnly:)` 可让 directory 对 guest 只读；
- 使用配置需要 `com.apple.security.virtualization` entitlement；
- Linux boot loader 的 kernel / initramfs、RAW disk image 和 shared directory 都以 file URL 为主要输入。

因此高层 API 能表达隔离配置，却没有把 boot / checker / bundle 的实际读取原子绑定到已有 store descriptor。`VZDiskBlockDeviceStorageDeviceAttachment` 虽接受 `NSFileHandle`，但公开语义要求它指向实际 block device，典型访问需要 root，不是普通 RAW image descriptor 的替代入口。当前不把 URL 路径上的 preflight / postflight 摘要误写成 execution identity 闭合。

### `Hypervisor.framework`

[Hypervisor framework](https://developer.apple.com/documentation/hypervisor)是 entitlement 驱动的 user-space virtualization API，不需要 KEXT。公开 API 与当前 SDK 头文件给出：

- 当前进程通过 `hv_vm_create` / `hv_vm_destroy` 拥有一个 VM 生命周期；
- `hv_vm_map` 只把 caller 已分配的、page-aligned host memory 映射到 guest physical address；guest 访问未映射范围会使 `hv_vcpu_run` 退出；
- vCPU 由 caller thread 创建 / 运行 / 销毁，并可被强制退出；
- framework 不自动提供 network、disk、filesystem 或 Linux boot stack，设备与 transport 只有 runner 显式实现后才存在；
- 使用进程必须具有 [`com.apple.security.hypervisor`](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.hypervisor) entitlement。

这些原语允许 runner 从已经打开并摘要验证的 descriptor 把 accepted bytes 复制到唯一 `128 MiB` mapping，再由自有最小 guest / transport 使用；不需要把 guest identity 交回 URL lookup。它同时意味着 Linux boot、interrupt / timer、只读 bundle 投影和 result channel 都成为新的项目 TCB，必须在后续切片逐项证明。

## 合成探针

### Virtualization 配置表达力

探针只实例化 `VZVirtualMachineConfiguration`、`VZSharedDirectory`、`VZSingleDirectoryShare` 与 `VZVirtioFileSystemDeviceConfiguration`；没有设置 boot loader、调用 validation、创建或启动 `VZVirtualMachine`。结果：

```text
minimum_memory=4194304
maximum_memory=34359738368
requested_memory=134217728
requested_in_public_range=true
network_device_count=0
directory_share_count=1
share_read_only=true
vm_started=false
```

它证明当前主机上 `128 MiB` 落在公开配置范围内，空 network device 与只读 share 对象可形成；不证明 entitlement、guest boot、host filesystem 实际写保护、memory pressure、deadline、process containment 或 executable identity。

### Suspended dynamic code identity

第二个合成程序用 `POSIX_SPAWN_START_SUSPENDED` 启动自身副本，在 child 未恢复执行用户逻辑时按 PID 调用 Security framework，然后立即 `SIGKILL` / `waitpid` 清理。结果：

```text
spawn_suspended=true
guest_lookup_status=0
strict_validity_status=0
signing_information_status=0
unique_identifier_present=true
unique_identifier_length=20
child_resumed=false
```

这证明当前主机可以在 suspended child 上取得 dynamic code、执行 strict validity 检查并读取 opaque unique identity。`20` 只是在当前 synthetic ad-hoc binary 上的观察，不冻结为 SHA-1、CDHash 格式或公共字段；生产 runner 还必须核对 designated requirement、entitlement、team / signing policy 和实际 packaging。

### 前次架构审阅中有意未执行的探针

前次架构审阅没有调用 `hv_vm_create`、`VZVirtualMachine.start`、`SMAppService.register`、`codesign`、`launchctl`、App Sandbox 容器写入、`task_set_phys_footprint_limit` 或真实 checker。受限任务环境中的只读 `kern.hv_support` 查询返回 `Operation not permitted`，当时未请求扩大权限，也未把它计入平台支持证据。

### Synthetic bare-metal microguest feasibility

ADR 0013 接受后，以单独授权在精确临时根 `/private/tmp/radishaxiom-microguest-feasibility-a13-v1` 运行后续切片。所有 guest 输入都是 parent 预先打开的只读 descriptor 与固定二进制 control pipe；runner 没有接收 guest path、产品根或真实 checker 参数。Codex 外层沙盒不能嵌套启动 App Sandbox / Hypervisor，因此保留其 `SIGABRT` 观察后，只对同一临时矩阵在外层沙盒外复验。

runner 必须作为含 `CFBundleIdentifier` 的临时 `.app` 签名；裸 Mach-O 虽具有 `codesign --identifier`，仍被 `secinitd` 在 `main` 前拒绝。最终 ad-hoc runner 的 designated requirement 为当前签名字节的 cdhash requirement，opaque unique identity 长度观察为 20 bytes；parent 对每次 suspended child 完成 strict validity、designated requirement、unique identity 和**恰好** `com.apple.security.app-sandbox = true` / `com.apple.security.hypervisor = true` 两项 entitlement 核对后才 `SIGCONT`。缺少 Hypervisor entitlement 的同源负例在 resume 前被杀死并 reap，没有进入 runner 用户逻辑或创建 VM。

| 场景 | 动态结果 |
| --- | --- |
| descriptor 正常 / path replacement | 原 descriptor 的 32-byte guest blob 均执行成功；path 被 crash blob 替换后仍执行已打开的原字节 |
| descriptor drift / 截断 / 重复输入 | SHA-256 漂移、31 / 32 bytes 和 `descriptor_count = 2` 均在 `hv_vm_create` 前拒绝，`vm_count = 0` |
| 正常 cold invocation | parent 从 spawn 前计时至 reap 为 `12.936 ms`；runner 输出 13 bytes，随后 vCPU destroy、128 MiB unmap、VM destroy |
| exact memory / 越界 | 每个 VM 只映射 `134,217,728` bytes；guest 访问首个未映射地址 `0x08000000`，得到 syndrome `0x93c18006` 与 physical address `0x08000000` |
| guest panic | synthetic guest 通过固定 panic transport 退出；runner 不把该失败前缀送入 result channel，并完成 teardown |
| network / writable filesystem | VMM 没有实现任何 device；两项 synthetic device request 均得到 device absent 并 teardown。这不是 Linux syscall 证据 |
| stream overflow | guest 请求 4,097 bytes、host 上限为 4,096 bytes；result channel 保持 0 bytes 并形成 outer failure |
| cold deadline | 从 spawn 前开始的 `6,000 ms` deadline 在 `6000.990 ms` 完成 parent 观察；watchdog 强制 vCPU exit，随后 destroy / unmap / destroy / reap |
| synthetic descendant | guest task model 从 1 进入 2 并发生 exec transition，随后同一 vCPU 在 deadline 被强制退出；这是 fork / exec-like 合成状态，不是 Linux kernel `fork` / `execve` 证据 |
| 无残留 | 每个 child 都由 `wait4` reap，runner 自报 vCPU / mapping / VM 已销毁，矩阵后无匹配进程且精确临时根已删除；App Sandbox container 的 Data 树已清空，但系统保护的 metadata plist 与空 container 目录无法由当前任务删除，因此本项**未通过** |

最终矩阵 13 项全部得到预期结果。正常 runner 的单进程 `ru_maxrss` 峰值观察为 `6,438,912` bytes；这只说明 128 MiB guest mapping 没有全部成为 resident host pages，不能替代 guest 内 kernel / init / checker 的峰值测量。deadline 与正常时延也只是当前单主机单轮观察，不是稳定性或支持矩阵。

可追溯临时输入为：`runner.c` `sha256:1dea1602226ad51b4b6f36df07165a74c49f968c0f26f121473464a8e818fd00`、`parent.c` `sha256:3f1185d30a7e13dce3812fa1dac27d04573001229d88ae9ffe12756d6bc88b1e`、entitlement plist `sha256:c1709c44101bb30342b603ed59ac21b4ec6ceaa23a29b9c8de7602ea5d466ca3` 与 runner `Info.plist` `sha256:84281afe37501b52a84de12e2d1fca0103f8ff3b8058370d8b2d8087d995f3d4`；最终 runner Mach-O 为 `sha256:44ba5114c49e280fdaaa13b751953c89d814dfbcd7f8ef354d7143a0cf9f61a8`，parent 为 `sha256:155238fbb4eccc423a5b386b8c19bb9187383a6140205274382b0e0aa67d26ae`。这些字节只属于已删除的合成探针，不是登记 payload、可发布制品或公共身份。

构建使用 Apple clang `21.0.0 (clang-2100.1.1.101)`、Xcode `26.6` / macOS SDK `26.5` 与系统 `codesign`；动态链接 TCB 为 Hypervisor `259.6.4`、Security `61901.120.67`、CoreFoundation `5026.5.4` 和 libSystem `1356.0.0`。实际硬件为 `Mac17,2`、arm64、32 GiB，`kern.hv_support = 1`；SDK header 的 Hypervisor arm64 API availability 从 macOS 11.0 起，但本探针只证明 macOS `26.6.2`，最低支持版本保持未冻结。探针没有第三方源码或新增依赖；Apple SDK / 系统 framework 继续受其供应商许可约束，临时代码没有进入分发。

该切片证明低层 descriptor → exact mapping → one VM / one vCPU → forced teardown 链在当前主机可行，但**没有完整通过 ADR 0013 实施前门槛**：bare-metal guest 不包含 Linux kernel / minimal init，因而没有证明真实非特权 checker process、empty cwd、Linux `fork` / `execve` 后代、guest syscall 级 network / filesystem 拒绝，也没有证明 128 MiB 能容纳 kernel + init + bundle + Go checker。App Sandbox 还会为 runner bundle identifier 自动创建持久 container skeleton；本次精确临时根与 container Data 树已经清除，但当前任务没有权限删除 `/Users/luobo/Library/Containers/dev.radishaxiom.synthetic.microguest.runner.a13/.com.apple.containermanagerd.metadata.plist` 及其空父目录，`rm` 明确返回 `Operation not permitted`。该精确 28,896-byte metadata residual 是当前未闭合项，后续产品 packaging 必须显式解决或纳入状态边界。

### Synthetic Linux microguest feasibility

接受 ADR 0014 后，后续切片在精确 `/private/tmp/radishaxiom-linux-microguest-feasibility-a14-v1` 根中建立临时 runner `dev.radishaxiom.synthetic.linux-microguest.runner.a14`。parent 只打开 kernel / initramfs 并映射到 child 的 fixed descriptor 3 / 4；runner 对 regular-file type、精确长度和 SHA-256 复核完成后才创建 VM。每轮 runner 都由 `POSIX_SPAWN_START_SUSPENDED` 启动，supervisor 在 `SIGCONT` 前以 Security framework 复核 dynamic code、strict validity、designated requirement、opaque unique identity、精确 identifier，以及**只有** App Sandbox / Hypervisor 两项 entitlement。

临时 TCB / 输入记录如下：

| 输入 | 来源、构建与实测身份 |
| --- | --- |
| Linux kernel | Alpine `3.24.1` aarch64 官方 release 的 [`vmlinuz-virt`](https://dl-cdn.alpinelinux.org/alpine/v3.24/releases/aarch64/netboot-3.24.1/vmlinuz-virt)，10,351,104 bytes，`sha256:47970e0ee0478fe5c60824a89f162d5a353fa29466e5d3bddb0f9c506f1ed756`；配套 `config-6.18.35-0-virt` 为 161,238 bytes，`sha256:5557553d228d407e8eac80ea7a1c7bf36dab558625067c9ada355032cf6a9c51`。按 [Linux arm64 boot protocol](https://docs.kernel.org/arch/arm64/booting.html) 与 EFI zboot header 提取并解压的 arm64 `Image` 为 36,110,336 bytes，`sha256:8b216f74e7f89def4604adf69e2345437363aff4819101bb1551c9e83cd35cdd`；guest 自报 Linux `6.18.35-0-virt`、Alpine GCC `15.2.0`。kernel / Alpine package 许可证口径为 [`GPL-2.0-only`](https://docs.kernel.org/process/license-rules.html)；本记录不是生产 source acceptance 或可复现构建证明。 |
| minimal init / synthetic process | 自写 `probe.go` 为 `sha256:a19ce614fde6137d7e8b08e195472c2d49954a82a953548e0ab8a85225969638`，由本机既有 Go `1.26.3` 以 `GOOS=linux GOARCH=arm64 GOARM64=v8.0 CGO_ENABLED=0 -trimpath` 构建；static ELF 为 1,835,170 bytes，`sha256:52796604be1d55befa92f43f756fa74882e0950d7157151f74b0d5abcdd79159`。自写 deterministic newc / gzip 生成器为 `sha256:036f7103dd1debc43004501775fff7ea29e27f24ce1451bfd065c0e8e4f83aef`；最终 initramfs 761,634 bytes，`sha256:33fee17daa5d782a559aaed4cfe96aa8440d2c5107c6535068faedfc2c14d50a`。只含 `/probe`、`/init -> probe`、empty / proc / dev 基础节点，无 shell、包管理器、compiler 或第三方 module。 |
| VMM / supervisor | 自写 `runner.c` 为 `sha256:14039455f5d1391d29c2950b7b831133e4dad9d7f6e5858662664cfdfec8e349`，`supervisor.c` 为 `sha256:af4e31e270d3f46f7a63f4baa655c40343263d6e8865542d9b750457e63f652f`；Apple clang `21.0.0` / Xcode `26.6` / SDK `26.5` 构建。最终 runner Mach-O 为 `sha256:5afb5967d47c7ed077dc314f9f7bbdcae52c6cbf2f7f7851d8f0c9465cc7e4b6`，ad-hoc `CDHash=9fce6944e30e20f033244e08b83cc76f3d566482`；supervisor 为 `sha256:a4d57b8e0b794a9036a0b27fc7c9ace1c9bac7ee54bbfe18938c079b38d201f7`。动态链接只含系统 Hypervisor / Security / CoreFoundation / libSystem；仓库没有新增依赖。 |

每个有效 guest 只建立一个 VM / 一个 vCPU，并且只映射 `134,217,728` bytes guest physical RAM。Linux 启动所需 GIC v3、architected virtual timer 和固定 output-only PL011 属于显式 TCB；没有 network interface、disk、host share、input device 或 writable-host device。因此本结果不把“无 capability-bearing I/O device”误写成字面上的零虚拟硬件。

最终 8 类、共 10 次 suspended spawn 的矩阵结果：

| 场景 | 动态结果 |
| --- | --- |
| normal × 3 | cold spawn-to-reap 分别为 `129.405 ms`、`125.935 ms`、`120.158 ms`；descriptor identity、one VM / one vCPU、teardown 和 direct runner reap 全部通过 |
| guest identity / cwd | synthetic child 为 `uid=65534 gid=65534`，cwd 为 mode `0555` 的空 `/empty`，entry count 0；实际 Linux process 创建 / exec 后的 grandchild 被观察并等待 |
| syscall / device | init 安装的 arm64 seccomp filter 让 child 的 writable `openat` 与 `AF_INET` socket 返回 `EPERM`；VMM 没有 network / disk / share device。此结论依赖 minimal init / seccomp TCB，不是 kernel 全局关闭 `CONFIG_NET` |
| exact / requested over-limit memory | 所有有效 VM 只映射 128 MiB；`134,221,824`-byte 配置在建 VM 前拒绝，`vms=0 vcpus=0` |
| guest physical OOB | 仍只映射 128 MiB，但合成 DT 多声明 4 KiB；guest 首次访问 `0x48000000` 形成 stage-2 VM exit，随后 vCPU / mapping / VM 销毁 |
| guest crash | synthetic child 自发 `SIGKILL`，PID 1 报告 guest crash；host 不接受失败前缀为结果并完成 teardown / reap |
| stream overflow | guest 产生 4,097-byte result line，host 以 4,096-byte 上限失败关闭并强制结束 VM；截断内容不进入 result consumer |
| descendant at deadline | child 与实际 Linux grandchild 同时保持运行；从 supervisor spawn 前开始的 6 秒外层 deadline 在 `5956.120 ms` 完成 vCPU forced exit、destroy、unmap、VM destroy 和 runner reap，未触发 `SIGKILL` fallback |
| 无请求残留 | 每轮 `wait4` 后再次 `waitpid` 得到 `ECHILD`、`kill(pid, 0)` 得到 `ESRCH`；最终精确进程匹配为空，临时根已删除，新 A14 container `Data` 子树为空。保留的只有 ADR 0014 允许的固定 container、空 `Data` 目录和 29,400-byte containermanager metadata |

正常 guest 自报 `memory_total=94,769,152` bytes；这是扣除 kernel / reserved 后的 Linux 可用 RAM，不是把 128 MiB mapping 改小。最终 runner `ru_maxrss` 最大观察为 `98,353,152` bytes；它是当前 host residency 观察，不是新的公共 memory limit。三次正常 cold 结果和单次 deadline 只证明当前 `Mac17,2` / macOS `26.6.2` 主机，不冻结最低 macOS、其他 Apple Silicon 或稳定性分布。

该切片通过了 ADR 0013 synthetic Linux feasibility 中的真实 Linux process / syscall、descriptor-fed boot、128 MiB、cold deadline、bounded stream 和 VM containment 项，但仍没有执行或装入 checker / resolved bundle，也没有形成产品 source acceptance、production signing / packaging、公共 host + runner + guest identity 迁移或 qualification。`NativeIsolationStatus = RequiredNotProven`、active runtime 0 与现有 canonical bytes 均保持不变。

## 决策证据与未决风险

| 边界 | native / App Sandbox | Virtualization configuration | Hypervisor runner 方向 |
| --- | --- | --- | --- |
| no network | App Sandbox 可覆盖 | empty network devices 可表达 | sandbox + 不实现 device |
| readonly bundle | 需要签名 / grant，native 不成立 | read-only URL share 可表达，identity 未闭合 | descriptor-fed bounded read-only projection |
| hard memory | 不成立 | fixed guest memory 可表达 | exact mapped guest physical range |
| process tree | process group 可逃逸 | VM teardown 可作为候选 | VM / vCPU destroy 是所选 containment boundary |
| executable identity | suspended SecCode 可闭合 signed runner，不闭合 unsigned payload path | guest URLs 仍有 lookup 缝隙 | signed runner + descriptor-loaded accepted bytes |
| 当前 payload | Mach-O 可 native 执行但边界不足 | Linux guest 不兼容 | 需要新 Linux guest payload |

synthetic Linux closure 已降低 guest boot、process / syscall、128 MiB 与 6 秒 cold lifecycle 风险，但仍有四项决定性未决边界：真实 checker + resolved bundle 是否能在相同 guest 上限与 deadline 内完成；现行 `process-outer` 语义是否接受“guest 可寻址硬上界 + 固定可信 runner overhead”而不要求整个 host runner RSS 也小于 128 MiB；kernel / init / VMM / transport 的生产 source acceptance、可重现 artifact、更新与许可证治理能否保持可审阅；生产签名 / 分发、最低 macOS、固定 container 增量审计和 host + runner + guest 公共身份迁移能否闭合。任一失败都只允许保持 runtime unavailable 或重新立 ADR，不能自动放宽 limit、用文档重解释既有语义、启用 warm VM、root broker 或 native fallback。

[ADR 0014](adr/0014-darwin-app-sandbox-container-state.md)已经接受：只允许固定产品 identity 的 OS-managed container skeleton 作为安装级 host state，并把 runner 不读写 container、无请求派生增量设为 TCB 义务。本轮 Linux runner 没有 container path discovery 或 I/O；动态运行只产生系统首次启动建立的 skeleton，清理前 Data 树磁盘占用为 0 KiB。该结果仍不替代未来安装 / 升级 / 卸载与异常增量审计。

## 清理与工作区影响

两个 probe 的 source、binary、module cache 与空 share directory 在结果记录后从精确临时根 `/private/tmp/radishaxiom-darwin-isolation-probe.6X2viy` 删除，并确认路径不存在。仓库只保留本审阅与 ADR / 状态索引更新；没有新增 dependency、Cargo package、FFI、机器 schema、canonical fixture、签名制品、VM image 或系统残留。

后续 microguest probe 的 `/private/tmp/radishaxiom-microguest-feasibility-a13-v1`、两个定位用 crash report 和 App Sandbox container Data 树也已精确删除；没有 runner 进程、VM image、日志或临时根残留。唯一未能删除的是上文记录的 container-manager metadata plist 与空父目录。仓库只更新本审阅和当前状态，没有保留 probe code、binary、entitlement、公共格式或机器 fixture。

本轮 Linux probe 记录最终摘要后，精确 `/private/tmp/radishaxiom-linux-microguest-feasibility-a14-v1` 已递归删除并确认不存在；新 identity `dev.radishaxiom.synthetic.linux-microguest.runner.a14` 的 `Data` 子树已清空且无 entry，进程精确匹配为空，DiagnosticReports 中没有 `SyntheticRunner` crash report。按 ADR 0014 保留 OS-managed container 父目录、空 `Data` 目录与 29,400-byte `.com.apple.containermanagerd.metadata.plist`，未读取或改写 metadata 内容。仓库没有保留 probe source / binary / entitlement，也没有写入 VM image、产品根、系统 service 或远程状态。

## 复现材料缺口（2026-09-05 审阅补记）

上述 probe 的摘要、环境与结果叙述保留了历史身份和观察，但自有源码、完整构建 / 运行入口及输入字节未持久留存，独立协作者不能仅凭本记录复现原实验。这不撤销当时观察，也不构成新的运行验收；后续不得把它计为已具备可重跑回归的产品证据。

后续产品化实验应按[协作规则](governance/agent-collaboration.md)先保留最小源码、配置、合成输入和机器结果，再清理临时运行产物。新实验使用新身份与实际证据，不能用重新编写的 probe 冒充原摘要对应源码。真实 checker / bundle、资源语义与 TCB 审查入口见[开发计划](development-plan.md)。
