# ADR 0013：Darwin checker 强隔离宿主与虚拟执行边界

日期：2026-09-03

状态：Accepted

用途：在不弱化现行 hard boundary 的前提下，冻结 Darwin 宿主上 checker 的强隔离方向、可信基、产品制品边界、身份链和进入实现前的停止线。

读者：checker runtime / launcher、Darwin 平台适配、产品签名与打包、独立 checker、供应链和安全审阅维护者。

不包含：本次实现或签名 runner、申请或写入 entitlement、创建 VM、启动 service、修改系统设置、生成 guest image、修改公共机器格式、下载 / 安装 / 执行真实 checker、形成 qualification、激活 runtime、push、发布或部署。

## 背景

[ADR 0008](0008-independent-checker-isolation-and-artifact-exchange.md)、[ADR 0011](0011-checker-runtime-launcher-installation-and-activation.md)与 [Execution Profile Contract v0.1](../../contracts/execution-profiles-v0.1/README.md)要求 checker 每次调用离线、环境为空、只能读取解析后的只读 bundle、没有生产工具和网络，并受 `6,000 ms` hard deadline、`128 MiB` outer working-memory hard limit、bounded streams、精确 executable identity 与失败关闭约束。[ADR 0012](0012-product-checker-runtime-host-and-persistence-interface.md)把 launcher core 放入主仓 Rust 生产图，但同时规定：如果目标平台不能可靠施加这些进程 / 资源限制，或者强隔离要求独立签名与权限，就应以新 ADR 重新比较宿主，而不是增加 fallback。

[Darwin process isolation 原语审阅](../checker-runtime-darwin-process-isolation-review.md)已经触发该重新评估条件。公开 native process API 可以闭合 exact spawn、descriptor cwd、stream / deadline supervisor 和 direct-child observation，却不能共同闭合以下四项：

- App Sandbox 不是 `posix_spawn` flag；它需要产品签名、entitlement 和明确的 helper / packaging 关系；
- `RLIMIT_RSS` 是 `RLIMIT_AS` alias，`128 MiB` 配置在当前主机不可用；`task_set_phys_footprint_limit` 又有 privilege 门禁，并被 XNU 源码注明可能应废弃；
- process group 可由新 session / group 逃离，Darwin 没有本路径可依赖的公开 Job Object / subreaper；
- `posix_spawn` 按 path 解析 executable，没有 `fexecve` / `execveat`；preflight / postflight 与 `proc_pidpath` 只能检测部分漂移，不能原子绑定已打开的登记字节。

本 ADR 保留全部 hard boundary。把 memory 改成 rusage polling、把 process tree 改成 best-effort group kill，或把 App Sandbox 未授权路径写成“等效隔离”均不在候选中。

## 方案比较

| 方案 | 可覆盖边界 | 无法闭合或新增代价 | 结论 |
| --- | --- | --- | --- |
| native `posix_spawn` + process group + rusage | stream、deadline、direct child、部分身份观察 | 无 hard memory、不可逃逸后代和正式 filesystem / network sandbox；path TOCTOU 仍在 | 拒绝作为 qualification / product adapter |
| signed helper + App Sandbox | 由内核执行静态 filesystem / network capability；可形成独立签名身份 | 不提供 `128 MiB` hard memory 或 process-tree container；直接 child 继承 sandbox 也不能单独表达全部能力 | 只作为所选 runner 的外层宿主，不单独成立 |
| privileged broker / `SMAppService` launch daemon | 理论上可取得 footprint privilege，并可隔离产品权限 | 需要用户 / 管理员批准和系统持久状态；公开 API 没有补齐不可逃逸 process tree；`task_set_phys_footprint_limit` 的长期支持不稳定 | 拒绝 |
| `Virtualization.framework` per-invocation Linux VM | 公开配置可表达固定 guest memory、空 network devices、只读 directory share 和整 VM 生命周期 | boot loader、disk image 与 directory share 仍以 URL 为主要身份；当前 Darwin Mach-O checker 不能在 Linux guest 执行；entitlement、guest TCB、启动时延均未验收 | 保留为可行性对照，不可形成正式 adapter |
| signed、App-Sandboxed 的 per-invocation Hypervisor runner | guest memory 由固定映射形成；checker 及其全部 guest descendants 在同一 VM；可只从已打开 descriptor 装载精确字节；不实现 network device | 需要新的受审阅 VMM / Linux microguest TCB、签名与 entitlement、单独产品制品、guest payload 身份和后续 policy 迁移 | **采用；synthetic Linux feasibility 已通过，产品化门槛仍阻断** |
| 弱化公共 hard boundary | 可减少平台实现成本 | 改变已冻结的失败、资源和信任语义 | 拒绝 |

## 决策

### 当前 native 路径保持禁用

当前 `darwin / arm64 / v8.0 / macho-64-arm64` payload 保持 `registered-inactive`，`NativeIsolationStatus` 保持 `RequiredNotProven`，active runtime 保持 0。不得为推进实现而接入 native process adapter、运行 checker 或形成 qualification；已有 native supervisor 原语只能继续作为非授权研究证据。

### 采用逐次 Hypervisor runner

Darwin hard-isolation 的唯一进入实施候选是一个**每次调用新建、签名、App-Sandboxed、无请求派生持久状态的 Hypervisor runner**；App Sandbox 固有 container 的安装级状态边界由 [ADR 0014](0014-darwin-app-sandbox-container-state.md)窄修订：

```text
product / Rust runtime core
  -> verify registration, slot, request and descriptor inputs
  -> spawn exact signed runner suspended
  -> validate running code identity and required entitlements
  -> pass only bounded pipes and already-open read-only descriptors
  -> resume runner
       -> allocate exactly 128 MiB guest physical memory
       -> load accepted kernel / init / checker / bundle bytes from descriptors
       -> create one VM and one vCPU
       -> expose fixed request / result channels only
       -> expose no network, socket, writable disk or host path device
       -> run one checker invocation
       -> destroy vCPU and VM on result, deadline or any failure
  -> recheck runner and input identities
  -> feed one complete stdout result or one outer failure to existing consumer
```

runner 属于产品侧可信计算基，与主仓 Rust runtime core 共用仓库、精确工具链治理和产品发布图，但它是独立签名的私有产品制品，不是公共 CLI、daemon、登录项、launch agent 或 launch daemon。每次请求必须创建新的 runner process 和新的 VM；禁止常驻 service、warm VM、跨请求 guest memory、结果 cache 或失败后切换 native adapter。只允许固定 bundle identifier 对应的 OS-managed container skeleton 作为安装级 host state；runner 禁止读写该 container，container 不得成为输入、输出、cache 或 guest device。

这对 ADR 0012 的“首版不冻结单独产品进程”形成窄修订：installer / store / policy / result core 继续留在现有 Rust workspace，只有 Darwin checker execution boundary 被允许拆为独立签名 runner。ADR 0012 的网络隔离、store 六项能力、单一 result consumer、Checker Go parser 不复用和 Python 非生产依赖等其余决策保持不变。

### Hard boundary 映射

| 现行边界 | runner 架构要求 |
| --- | --- |
| network forbidden | runner 不得拥有网络 entitlement；VMM 不实现或附加 network / socket device；guest 中没有网络接口或 host network proxy |
| resolved-readonly-bundle-only | bundle 由 runtime core 从已验证 descriptor 形成有界只读输入；runner 不接收产品根、bundle path 或可写 host filesystem；guest 只看到 immutable boot TCB、checker 与只读 bundle 投影 |
| production tools forbidden | guest image 只包含已登记 boot TCB、最小 init 与 checker，不包含 shell、package manager、compiler、provider credential 或产品工具 |
| isolated-empty working directory | guest init 在执行 checker 前进入一个不含 entry、不可由 checker 写入的目录，并以非特权身份启动 checker |
| `128 MiB` hard working memory | runner 只映射 `134,217,728` bytes guest physical memory，不建立 balloon 或额外 guest RAM；kernel、init、bundle 投影与 checker 共同受该上限，checker 可用量只会更小；访问未映射 guest physical address 必须形成 VM exit / outer failure |
| `6,000 ms` hard deadline | parent 与 runner 都使用单调时钟；deadline 覆盖 runner spawn、VM setup、guest boot、checker 和 teardown；到期强制 vCPU exit、destroy VM，并由 parent 终止 / reap runner |
| bounded stdout / stderr | host / guest channel 具有固定容量，达到上限即停止接受结果并形成 outer failure；截断前缀不得进入 result consumer |
| process containment | checker fork / exec 的任何后代都只能存在于 guest；调用结束销毁全部 vCPU / VM，不使用 process group 冒充 guest process tree containment |
| executable identity | parent 在 suspended runner 开始用户逻辑前用 Security framework 取得 dynamic code，并核对签名有效性、opaque unique identity、designated requirement 与 entitlement；kernel / init / checker / bundle 只从 pre-opened descriptor 按接受的长度 / SHA-256 读入映射，不再按 path 查找 |
| persistent host state | 只允许固定 runner identity 对应的 OS-managed App Sandbox container skeleton；不得有请求派生 container data、逐请求 identity / container、App Group、security-scoped bookmark、VM image、日志或 cache；runner 不发现、读取或写入 container path |

runner 自身、Darwin Hypervisor / App Sandbox / code-signing enforcement、guest Linux kernel、minimal init、host / guest transport、现有 Rust orchestration / store / result consumer，以及 checker binary 都必须分别进入 runtime TCB。Hypervisor 隔离不会把这些组件自动升级为独立 proof。

这里不把 host runner 的 RSS 偷换成 guest checker 的计量。现行 `process-outer / launcher-os-hard-limit` 是在 native checker 进程形状下冻结的；后续公共迁移必须明确：`128 MiB` 仍是 checker 与 guest TCB 可寻址的硬上界，runner 只使用固定、与 guest 输入无关的有界 control / stream buffer，Hypervisor / runner 的可信宿主开销另行观测并进入 TCB。若审阅认定公共语义要求“整个 host runner physical footprint 也不超过 128 MiB”，当前公开 Hypervisor 原语尚不足以证明该项，必须保持阻断并重新立 ADR，不能靠文档重解释为通过。

### Guest target 与当前 payload

当前登记的 Mach-O checker 不能被复制进 Linux guest 后执行，也不能因 source 相同而重标为 Linux artifact。所选架构需要独立构建、验收和登记的 Linux arm64 checker payload，以及受控 kernel / init / guest-layout 制品链。

ADR 0011 当前把 host target 与 checker payload target 合并为同一个四元组；虚拟 guest 路径必须在后续公共策略迁移中显式区分：

- Darwin execution host 与签名 runner identity；
- guest platform / architecture / executable format；
- guest kernel、init、transport 与 checker artifact identity；
- guest-memory enforcement 和无 network / disk / host share 等 capability-bearing guest I/O device 证明；
- native 与 virtualized adapter 的 closed selection，且无 fallback。

现有 `CheckerSpawnPlan` 也只表达 host executable path 与 `--bundle-root=<canonical-realpath>`，不能被静默重解释成 runner / guest plan。后续迁移必须建立排他的 virtualized plan；checker 在 guest 内仍只接受原有 `check` 与单一 `--bundle-root=` 形状，host / guest transport 不得成为 checker 的第二个公共 CLI。

本 ADR 不分配新的 policy / receipt / registration 格式版本，也不修改现有 canonical bytes。完成该迁移并重算全部摘要链之前，runtime core 不得选择虚拟 guest payload。

### 为什么不直接采用 `Virtualization.framework`

Apple 的高层 API 已公开：`VZVirtualMachineConfiguration.memorySize` 表示 guest 看到的 physical memory，network device 列表默认为空，`VZSharedDirectory` 可标为 read-only；本次合成配置探针也确认当前主机的公开 memory range 为 `4 MiB..32 GiB`，`128 MiB` 位于范围内。

这些事实只证明配置表达力。`VZLinuxBootLoader` 的 kernel / initramfs、`VZDiskImageStorageDeviceAttachment` 和 `VZSharedDirectory` 使用 file URL；公开契约没有把这些 lookup 绑定到 runtime core 已打开并摘要验证的 descriptor。若 runner 退回 URL boot / share，它必须先以新的证据证明 execution bytes 与 descriptor 原子绑定；在此之前不可替代所选低层装载边界。

## 实施前门槛

本 ADR 接受后的首个实现入口只是单独授权的**合成 microguest feasibility 切片**，且不得执行 checker。其门槛为：

1. 使用独立测试签名和 `com.apple.security.app-sandbox` / `com.apple.security.hypervisor` entitlement 的临时 runner；说明签名目标、持续时间、写入范围和清理方式，不能借用生产身份或注册系统 service；
2. parent suspended-spawn 后用公开 Security API 验证 dynamic code、designated requirement 与精确 entitlement，再允许 runner 继续；失败必须在 guest 创建前关闭；
3. 所有 guest 输入由 pre-opened descriptor / bounded pipe 提供，strace 等调试工具不得成为生产依赖；加入 path replacement、descriptor drift、截断和重复输入负例；
4. 只映射 `128 MiB` guest RAM，建立 one-VM / one-vCPU 最小生命周期；Linux 启动必需的 interrupt controller / timer 与 output-only transport 必须显式进入 TCB，除此之外不实现 network、disk、host share、input 或 writable-host device；证明 deadline 能迫使 vCPU exit、destroy 和 runner reap；
5. 使用不会解释公共 checker 协议的 synthetic guest，覆盖正常、超时、越界内存访问、guest crash、尝试网络 / writable filesystem、fork / exec 后代和 stream overflow；
6. 记录完整 TCB source / artifact / toolchain / license、启动与峰值资源、最低 macOS 和硬件前置；`6,000 ms` 必须包含冷启动，不允许先热机；
7. 证明失败后没有 guest / runner process、VM / vCPU、mapping、临时文件、VM image、日志、credential、系统设置或请求派生 container data；只允许 ADR 0014 定义的固定 OS-managed container skeleton 与 opaque metadata 基线，且 runner 不读写它、不把它暴露给 guest。

当前主机上的 synthetic Linux 结果与限制记录在[强隔离架构审阅单](../checker-runtime-darwin-hard-isolation-review.md)：该切片已通过，但只解除“可以另行提出”后续设计 / 实施切片的停止线。guest checker 构建、公共 policy / registration / receipt 迁移和真实 product packaging 尚未因此被接受；真实 checker execution、qualification、系统签名 / entitlement 变更和 activation 继续分别验证、分别授权。

## 后果

收益：

- 架构选择不以弱化 hard memory、process tree、filesystem / network 或 executable identity 边界换取实现；是否实际满足仍由实施前门槛决定；
- checker 的不可信进程树位于 guest，结束 VM 比追踪 Darwin process group 更接近真实 containment；
- descriptor-fed byte loading 可以复用现有 content-addressed store 与身份重算，而不是重新依赖 path execution；
- 不引入 root daemon、管理员批准、system extension 或私有 kernel API。

代价与风险：

- 新增低层 VMM、Linux kernel / init、host / guest transport、签名 runner 和 entitlement，可信基与发布面显著扩大；
- current Darwin payload 不能复用，需要新的 guest target、受控构建、许可证清单、acceptance、registration 和 policy identity；
- synthetic Linux kernel + minimal init + 1.84 MiB Go probe 已在 exact `128 MiB` mapping 与 `6,000 ms` cold deadline 内动态通过，但真实 resolved bundle + checker 的容量、时延和失败分布尚未证明；若失败，不允许自动增大 limit 或改用 warm VM；
- Hypervisor API 只提供虚拟化原语，不提供 Linux boot、设备模型、guest filesystem 或协议实现；这些都需要独立审阅，不能把 Apple framework 通过当作 runner 通过；
- entitlement 和签名会改变产品打包 / 更新边界，最低 macOS 与支持矩阵尚待合成切片冻结。
- App Sandbox 固有 container 是 runner 默认可写的持久 host namespace；ADR 0014 把“不读写它、无请求派生增量”列为 runner TCB 义务，而不是声称物理零持久状态。安装、升级、卸载与异常增量审计必须单独闭合。

回滚保持失败关闭：删除尚未激活的 runner / guest 候选和对应 future registration 即可；现有 `registered-inactive` Darwin record 与公共格式原字节不追溯修改，产品继续报告 runtime unavailable。不得以回滚为理由重新启用 native best-effort adapter。

## 公开依据与重新评估条件

本决策依据 Apple 公开的 [App Sandbox](https://developer.apple.com/documentation/security/app-sandbox)、[sandboxed app helper](https://developer.apple.com/documentation/xcode/embedding-a-helper-tool-in-a-sandboxed-app)、[Security dynamic code lookup](https://developer.apple.com/documentation/security/seccodecopyguestwithattributes%28_%3A_%3A_%3A_%3A%29)、[Hypervisor framework](https://developer.apple.com/documentation/hypervisor)、[Hypervisor memory management](https://developer.apple.com/documentation/hypervisor/memory-management)、[`com.apple.security.hypervisor`](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.hypervisor) 与 [Virtualization configuration](https://developer.apple.com/documentation/virtualization/vzvirtualmachineconfiguration)；当前主机 / SDK 核查与合成结果见[强隔离架构审阅单](../checker-runtime-darwin-hard-isolation-review.md)。

出现以下任一事实时，以新 ADR 重新比较，而不是增加 fallback：

- synthetic microguest 或后续真实 checker 在受支持主机上无法在 `128 MiB` guest memory 和 `6,000 ms` cold deadline 内稳定完成；
- App Sandbox / Hypervisor entitlement 无法在目标产品签名与分发渠道中获得或保持；
- 固定 container 基线出现请求派生写入、跨请求读取、无法审计的非 opaque 增量，或必须增加 App Group / bookmark / 清理权限；
- descriptor-fed boot / checker / bundle 装载无法避免新的 path / writable-host dependency；
- VMM / guest TCB 无法被限制到可独立审阅的规模，或其依赖 / 许可证不可接受；
- Apple 提供新的公开 native process container，能同时闭合 hard memory、不可逃逸 process tree、filesystem / network 与 atomic executable identity，且可信基明显更小；
- 支持 Intel Mac、其他 guest architecture 或多平台要求使当前 host / guest identity 模型不再闭合。

任何 native best-effort fallback、常驻 VM / service、root broker、guest network / writable host share、跨请求状态复用、当前 Mach-O payload 重标为 guest artifact，或把 entitlement / synthetic probe 直接当 qualification，均必须以新 ADR 替代本决策。
