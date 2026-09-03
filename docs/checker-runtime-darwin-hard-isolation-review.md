# Checker runtime Darwin 强隔离架构审阅单

状态：公开原语与 synthetic bare-metal microguest 低层探针已完成；Linux guest / checker 与 qualification 仍阻断
审阅日期：2026-09-03

## 目标与结论

本审阅承接 [Darwin process isolation 原语审阅](checker-runtime-darwin-process-isolation-review.md)，比较 App Sandbox、受权 broker、`Virtualization.framework` 与 `Hypervisor.framework` 能否在不弱化现行 hard boundary 的情况下闭合 Darwin checker execution。架构选择阶段只运行无 VM 合成 helper；ADR 0013 接受后的独立 feasibility 切片又在精确临时根中编译、ad-hoc 签名并运行 synthetic bare-metal microguest runner。两阶段都没有注册 service、修改系统设置 / 公共格式或执行 checker。

结论由 [ADR 0013](adr/0013-darwin-checker-hard-isolation.md)正式冻结：

- native `posix_spawn` supervisor 和单独 App Sandbox helper 都不能同时形成 hard memory 与不可逃逸 process-tree containment；
- privileged broker 会引入管理员批准、持久系统状态和 root TCB，公开原语仍未补齐 process tree，因此不采用；
- `Virtualization.framework` 可表达 128 MiB、零 network device 和只读 directory share，但 URL boot / image / share 入口没有关闭现行 descriptor identity 到实际 execution bytes 的缝隙，只保留为 feasibility 对照；
- 唯一进入实施候选是 per-invocation、signed、App-Sandboxed 的 Hypervisor runner：从已打开 descriptor 将 guest TCB、checker 与 bundle 装入固定映射，不实现 network / writable host device，并在每次请求后销毁 VM；
- 当前 Mach-O payload 保持 inactive；低层 runner / VM 动态证据已经物化，但 Linux guest、真实 fork / exec、guest payload、公共身份迁移和 qualification 仍未物化。

## 审阅环境与边界

| 项目 | 当前观察 |
| --- | --- |
| 主机 | macOS `26.6.2` build `25G83`，Darwin `25.6.0` arm64 |
| 开发工具 | Xcode `26.6` build `17F113` |
| SDK | macOS SDK `26.5` |
| 源码 / 头文件 | 本机 macOS SDK 的 Security / Virtualization / Hypervisor / spawn 公开头文件，Apple Developer Documentation，Apple OSS XNU `main` |
| 动态输入 | 架构阶段两个合成程序与空 share；feasibility 阶段自行生成的 parent、ad-hoc App bundle runner、bare-metal arm64 guest 指令和精确 `/private/tmp` 根 |
| 未触及 | checker / payload、产品根、真实 bundle、Linux kernel / init、生产签名、Service Management、qualification、activation、真实网络与远程状态 |

本审阅只支持架构选择和下一证据门槛，不证明其他 macOS / SDK、Intel、实际签名产品、guest kernel 或六平台行为。

## 公开原语核查

### App Sandbox 与 signed helper

[App Sandbox](https://developer.apple.com/documentation/security/app-sandbox)是 entitlement 驱动的 kernel containment，可以拒绝未授予的 network / filesystem 能力。Apple 对 sandboxed app 中 helper 的公开说明要求明确签名 / entitlement / embedding 关系；当 helper 需要与 parent 不同的能力集合时，应使用独立 XPC service、login item 或 helper app，而不是假设直接 child 自动获得更窄 profile。

它能作为 runner 的外层最小宿主，但不提供以下保证：

- 没有 `128 MiB` physical working-memory hard limit；
- 不把 fork / exec 后代放入可整体销毁的资源容器；
- 直接 inherit 还会继承 parent 的 sandbox 能力，未必等于 readonly-bundle-only；
- 当前 standalone checker 的签名 / entitlement 不在 registration、receipt 或 qualification 身份链中。

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

## 决策证据与未决风险

| 边界 | native / App Sandbox | Virtualization configuration | Hypervisor runner 方向 |
| --- | --- | --- | --- |
| no network | App Sandbox 可覆盖 | empty network devices 可表达 | sandbox + 不实现 device |
| readonly bundle | 需要签名 / grant，native 不成立 | read-only URL share 可表达，identity 未闭合 | descriptor-fed bounded read-only projection |
| hard memory | 不成立 | fixed guest memory 可表达 | exact mapped guest physical range |
| process tree | process group 可逃逸 | VM teardown 可作为候选 | VM / vCPU destroy 是所选 containment boundary |
| executable identity | suspended SecCode 可闭合 signed runner，不闭合 unsigned payload path | guest URLs 仍有 lookup 缝隙 | signed runner + descriptor-loaded accepted bytes |
| 当前 payload | Mach-O 可 native 执行但边界不足 | Linux guest 不兼容 | 需要新 Linux guest payload |

所选方向仍有四项决定性风险：`128 MiB` 是否足够承载最小 kernel + init + bundle + Go checker，现行 `process-outer` 语义是否接受“guest 可寻址硬上界 + 固定可信 runner overhead”而不要求整个 host runner RSS 也小于 128 MiB，cold VM 是否能在 `6,000 ms` 内稳定完成，以及低层 VMM / guest TCB 是否能保持可审阅规模。任一失败都只允许保持 runtime unavailable 或重新立 ADR，不能自动放宽 limit、用文档重解释既有语义、启用 warm VM、root broker 或 native fallback。

## 清理与工作区影响

两个 probe 的 source、binary、module cache 与空 share directory 在结果记录后从精确临时根 `/private/tmp/radishaxiom-darwin-isolation-probe.6X2viy` 删除，并确认路径不存在。仓库只保留本审阅与 ADR / 状态索引更新；没有新增 dependency、Cargo package、FFI、机器 schema、canonical fixture、签名制品、VM image 或系统残留。

后续 microguest probe 的 `/private/tmp/radishaxiom-microguest-feasibility-a13-v1`、两个定位用 crash report 和 App Sandbox container Data 树也已精确删除；没有 runner 进程、VM image、日志或临时根残留。唯一未能删除的是上文记录的 container-manager metadata plist 与空父目录。仓库只更新本审阅和当前状态，没有保留 probe code、binary、entitlement、公共格式或机器 fixture。
