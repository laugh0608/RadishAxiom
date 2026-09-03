# Checker runtime Darwin 强隔离架构审阅单

状态：公开原语与无 VM 合成探针已完成；方向由 ADR 0013 冻结，实施与 qualification 仍阻断
审阅日期：2026-09-03

## 目标与结论

本审阅承接 [Darwin process isolation 原语审阅](checker-runtime-darwin-process-isolation-review.md)，比较 App Sandbox、受权 broker、`Virtualization.framework` 与 `Hypervisor.framework` 能否在不弱化现行 hard boundary 的情况下闭合 Darwin checker execution。动态部分只编译 / 运行自行生成的合成 helper，且只写自动清理的 `/private/tmp` 精确目录；没有创建 VM、签名 entitlement、注册 service、修改系统设置 / 公共格式，或执行 checker。

结论由 [ADR 0013](adr/0013-darwin-checker-hard-isolation.md)正式冻结：

- native `posix_spawn` supervisor 和单独 App Sandbox helper 都不能同时形成 hard memory 与不可逃逸 process-tree containment；
- privileged broker 会引入管理员批准、持久系统状态和 root TCB，公开原语仍未补齐 process tree，因此不采用；
- `Virtualization.framework` 可表达 128 MiB、零 network device 和只读 directory share，但 URL boot / image / share 入口没有关闭现行 descriptor identity 到实际 execution bytes 的缝隙，只保留为 feasibility 对照；
- 唯一进入实施候选是 per-invocation、signed、App-Sandboxed 的 Hypervisor runner：从已打开 descriptor 将 guest TCB、checker 与 bundle 装入固定映射，不实现 network / writable host device，并在每次请求后销毁 VM；
- 当前 Mach-O payload 保持 inactive，runner、Linux guest、公共身份迁移和任何动态 VM 证据都尚未物化。

## 审阅环境与边界

| 项目 | 当前观察 |
| --- | --- |
| 主机 | macOS `26.6.2` build `25G83`，Darwin `25.6.0` arm64 |
| 开发工具 | Xcode `26.6` build `17F113` |
| SDK | macOS SDK `26.5` |
| 源码 / 头文件 | 本机 macOS SDK 的 Security / Virtualization / Hypervisor / spawn 公开头文件，Apple Developer Documentation，Apple OSS XNU `main` |
| 动态输入 | 两个自行编译的合成程序、一个空 share directory、自动清理的 `/private/tmp` 根 |
| 未触及 | checker / payload、产品根、真实 bundle、VM lifecycle、代码签名变更、entitlement、App Sandbox container、Service Management、qualification、activation、网络与远程状态 |

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

### 有意未执行的探针

本轮没有调用 `hv_vm_create`、`VZVirtualMachine.start`、`SMAppService.register`、`codesign`、`launchctl`、App Sandbox 容器写入、`task_set_phys_footprint_limit` 或真实 checker。受限任务环境中的只读 `kern.hv_support` 查询返回 `Operation not permitted`，未请求扩大权限，也未把它计入平台支持证据。

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
