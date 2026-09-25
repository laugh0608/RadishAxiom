# Checker runtime 产品化与 AX-B01 依赖审阅

审阅日期：2026-09-16；来源状态同步：2026-09-25

状态：ADR 0015 与维护预算于 2026-09-10 获确认，项目所有者为唯一维护负责人；公共迁移与实施仍未接受。

用途：把 ADR 0013 / 0014 的隔离候选收敛成可验收的来源、身份、资源、维护与实施切片，并识别首个真实 AX-B01 闭环的必要依赖。

读者：产品与架构决策者、runtime / pipeline 实现者、Checker 维护者及供应链审阅者。

不包含：创建 runner / guest、依赖下载或安装、签名、VM / checker / cvc5 / Node 执行、公共字节修改、产品根选择、qualification、激活或发布。本稿中的候选与预算均不是已验收能力，也不分配格式版本。

## 审阅结论

1. 保留 [ADR 0013](adr/0013-darwin-checker-hard-isolation.md) 的逐次 signed App-Sandboxed Hypervisor runner。现有 native plan 和 Mach-O payload 保持不可执行；合成 Linux 观察只支持继续设计，不是生产 runner 或可重跑回归。
2. **现行 memory 契约不能直接由 guest mapping 满足。** `process-outer / launcher-os-hard-limit` 与 guest 可寻址 RAM 不是同一计量域。[ADR 0015](adr/0015-virtualized-checker-resource-profile.md) 已于 2026-09-10 正式接受，为虚拟执行单独定义资源 profile，显式承认宿主总 footprint 没有现行等价硬限制；公共迁移、来源及执行前置验收前不执行真实 checker。若调用方必须保留整个宿主 128 MiB 硬限，则新候选也必须拒绝选择。
3. kernel / init / VMM / transport 的新来源链、可复现材料和更新责任是具体前置。先用源码和配置闭合最小 Linux 装置，不能把已删除 probe 的摘要当源码，不能直接提升 Alpine 实验 kernel 或旧 Go probe 的验收等级。
4. 生产 P0–P9、checker 离线复核、产品安装激活是三条分别验收的链。cvc5 / Node 的来源及执行限制、ADR 0007 的跨平台字节入口、checker 目标归因等是核心闭环依赖；产品 UI、自动更新、最终安装路径和正式 Agent 实验不是纯语义设计前置。现行 ADR 对真实实现和执行的门槛仍有效。

## 输入与证据等级

仓库审阅基点为 `a195232`。只读核对 [开发计划](development-plan.md)、ADR 0007 / 0008 / 0011–0014、[Execution Profiles](../contracts/execution-profiles-v0.1/README.md)、[readiness](../contracts/implementation-readiness-v0.1/README.md)、Rust spawn / result / store 边界及已有合成观察；没有重跑 Hypervisor 或读取兄弟仓库本机 checkout。

| 材料 | 可用于本次判断 | 不可外推 |
| --- | --- | --- |
| `e600e18` 的 Rust CI | macOS 26.6.2 上已有 core / Darwin store 回归通过 | runner、guest、cvc5 / Node、最低产品系统 |
| [历史 Linux microguest](checker-runtime-darwin-hard-isolation-review.md#synthetic-linux-microguest-feasibility) | 单主机 128 MiB mapping、真实后代、合成 syscall 拒绝和 cold lifecycle 有过观察 | 原源码可取回、生产签名、真实 bundle / checker、宿主硬内存上限 |
| 28 个指定态 bundle | 现有协议形状、静态大小、拒绝路径与场景 ID | 真实 P0–P9、最大容量、动态耗时、独立 proof |
| 官方上游文档 | API / 构建 / 许可证材料的候选依据 | source acceptance、无漏洞、许可证全库存或安装授权 |

本次按 `bundle/` 内全部普通文件原始长度求和：`ax-b01-correct` 为 **200,660 bytes / 22 文件**，最大单文件 31,599 bytes；28 个目录的最大总长也是 200,660 bytes。此计数用于装载容量设计，包含 request / manifest，不冒充 checker 内部 `bundle-bytes` 计数。真实 query / proof / 日志会改变生产 bundle 大小。

## 威胁角色与可信基

| 角色 / 输入 | 必须阻断的行为 | 保留的信任 |
| --- | --- | --- |
| 不可信 bundle、被替换的 checker | 读取宿主数据、网络、持久写入、跨 VM 后代、用超长或伪造输出驱动宿主分配 | 验证过的装载器、guest kernel / init、Hypervisor 与 App Sandbox |
| 同用户非协作 writer | 替换路径、修改已打开文件、污染 container、抢占发布 / 审计窗口 | descriptor containment、对实际复制字节重算摘要、签名动态身份、受管目录与审计协调 |
| 恶意或失控 guest EL1 | 畸形 MMIO、地址溢出、无限 VM exit、反复输出、越界 guest physical access | VMM 必须把所有 guest exit 当不可信输入；不以 Linux 正常行为作为宿主内存安全前提 |
| runner / guest kernel / init 缺陷 | 假造状态、解释错误、container 跨请求读写 | 这些组件属于 TCB；隔离不证明其实现正确，runner 被攻破后的持久写入不在 ADR 0014 保证内 |
| 宿主 kernel、系统 framework、签名服务 | 执行限额、页映射、身份、文件系统或调度不符合公开语义 | 平台供应商 TCB；记录实际版本，不宣称抵抗宿主 kernel 攻破或物理断电 |

新增 TCB 必须与 checker 的四项内部 TCB 区分。当前 result consumer 将 `canonicalization`、`checker-core`、`cryptographic-primitive`、`rule-interpreter` 绑定到 checker artifact；不能把 runner / Linux 身份塞进这四项，也不能用 checker 的 `isolation-report` 证明宿主隔离。

## 来源、构建与更新方案

以下是下一来源审阅的具体候选，不是新工具登记或已接受 payload。

| 组件 | 候选来源与职责 | 构建 / 分发 / 更新边界 |
| --- | --- | --- |
| Linux kernel | kernel.org 的 **6.18 LTS**；2026-09-06 官方列出的 patch 为 **6.18.49**。从 [官方 release 索引](https://www.kernel.org/)定位该精确源包、签名和 stable tag，审核后锁定完整身份 | 自建裁剪配置与未压缩 arm64 `Image`；不直接重用历史 Alpine `vmlinuz-virt`。源包摘要 / 签名与归档文件库存已有诊断核验；许可义务、config、patch、编译器与构建环境仍待验收 |
| minimal init | 主仓新写、单用途、独立于 Checker parser 的用户态程序；[来源与构建审阅](checker-runtime-guest-source-build-review.md#init-语言与启动边界)发现 Go 标准 child API 的 seccomp 安装缺口，建议优先论证 Rust `1.97.1` Linux arm64 静态 ELF | 管理只读投影、降权、空 cwd / env、seccomp、子进程与输出封装；不带 shell / 包管理器。语言 / target / Linux 链接依赖尚未接受，不能只凭交叉编译便利选择 Go |
| runner / VMM | 主仓 Rust `1.97.1` 私有签名制品，按 ADR 0012 / 0013 共用产品发布图；只实现 arm64 boot、GIC / timer 和固定输出通道 | 窄平台 FFI 单独审阅；现有 policy 的 `darwin-filesystem-only` / `libc-upstream-build-script-only` 不能授权新增 Hypervisor / Security 绑定。不开新通用 VMM 框架，不复制已删除 C probe |
| boot 布局与 transport | 主仓自有固定布局 / framing；parent 输入是预打开 descriptor，guest 获得内存中的字节，输出经有界通道返回 | 布局、端序、对齐、长度、终态和错误码形成私有版本化契约并先做合成拒绝测试；不是 checker 的第二套 CLI，不支持路径请求或通用 RPC |
| checker | RadishAxiomChecker 的精确源码提交 / source digest；以已接受 Go `go1.26.7` 构建新的 `linux / arm64 / v8.0 / ELF` 制品 | 不复用 Darwin artifact 的 binary / acceptance / companion 摘要；由 Checker 仓库独立构建和验收，本仓只消费离线制品与公共协议 |
| host framework / signing | Apple Security、Hypervisor、App Sandbox、系统链接器和签名工具；沿用精确 Xcode / SDK 核查路径 | 开发签名和生产 Developer ID / entitlement / 分发分别审阅。SDK、OS framework 不是项目可复现构建产物；不复制 SDK / 系统库进 guest |

Linux 6.18.49 只是本次源码审阅起点。进入下载 / 构建任务前重查该分支安全修复；需要换 patch 时显式更新候选和身份，不在脚本使用 `latest`。不从 tag 名生成虚构 digest，也不因官网列出版本就标记源码或 binary 已验收。

来源、builder 库存、init 比较与 Checker 交接由[来源与构建入口审阅](checker-runtime-guest-source-build-review.md)承接。[来源核验](records/linux-6.18.49-source-review/README.md)、[kernel 归档盘点](records/linux-6.18.49-archive-inventory/README.md)和[Debian 包诊断](records/linux-builder-source-chain/README.md)已留存各自实际结果；后续 [Rust Linux 输入诊断](records/rust-linux-input-review/README.md)取得 host / musl 实际字节、签名、归档和安装候选，并补齐 kernel tag 元数据对应与许可材料审阅。公钥旧自认证、镜像 / 工具、静态 runtime / 动态库来源及实际分发材料仍未闭合，不能作为完整 source lock。

### 可复现构建的验收单位

按 [Linux reproducible builds](https://docs.kernel.org/kbuild/reproducible-builds.html) 固定源码、完整 `.config`、patch 集合、工具与构建环境、时间 / user / host 输入、路径映射和文件顺序。两次干净构建使用不同目录，比较原始 `Image`、init ELF、布局及 initramfs；签名 Mach-O 与签名前输出分别记录，不要求含外部签名时间戳的 bytes 自然一致。

Linux builder 尚无已接受环境：候选是无运行时联网的独立 Linux arm64 构建环境，精确编译器 / binutils / make / 构建工具及其来源须先列全并验收。容器 tag 不足以绑定它，OCI digest 也不能替代包与许可证库存；不能临时借用未登记的 Docker image、系统 GCC 或历史 Go 1.26.3。

根据 [arm64 boot protocol](https://docs.kernel.org/arch/arm64/booting.html)，先核对 `Image` 头、有效大小、DTB、RAM 与 initrd 的边界及对齐。首轮倾向装载未压缩 `Image` 和固定 newc 布局，避免把 EFI zboot / gzip 解码额外放进宿主请求路径；是否压缩分发包是安装层问题，最终装载身份绑定解包后的精确 bytes。

每个实际构建保留 source inventory、完整命令、环境白名单、输出原始长度 / 摘要和两次比较结果。生成器源码及输入也要留存。清理只能移除可再生构建产物，不能再次只剩 probe 摘要。

### 许可证与维护责任

[Linux licensing rules](https://docs.kernel.org/process/license-rules.html) 明确 kernel 整体为 GPL-2.0-only，并说明 syscall / UAPI 例外。具体分发仍须审阅文件级 SPDX、配置启用的代码、补丁、源码提供与归属材料；不将 Linux 源码并入 Apache-2.0 自有源码许可声明，也不把 kernel 许可证外推到所有用户程序。用户态 init、checker、runner 和生成给用户的 Node module 分别核对嵌入材料。未下载新材料，本次不修改 `THIRD_PARTY_NOTICES.md` 或声明已完成分发合规。

2026-09-10 项目所有者确认以下维护预算：首轮自有新增生产 TCB 以 **8,000 行可审阅源码**为预警线（包括 FFI / framing；生成绑定、测试和第三方库存另列，不能隐藏规模），先投入最多 **10 人日**重建可留存的合成装置。它不是整个产品交付工期，也不意味着数百万行 Linux 已被本项目逐行审阅。

常态预留每周 **4 小时**用于 Linux stable / Apple 安全更新评估、依赖差异与回归；严重上游事件建议一个工作日内完成影响分级，无法确认影响时停止推进受影响候选或新激活。这是已确认的投入与内部响应目标，不是对外 SLA。项目所有者（萝卜SAMA）已明确自己是本仓库唯一负责人，统一承担产品 runtime 与 kernel / init 的维护责任；没有第二位维护者或独立审阅者的配置承诺。Agent 协助不替代该责任，也不能计为额外独立人力。预算或审阅规模不可承担时触发 ADR 0013 的重新选型条件。

更新以新的 source / artifact / execution-environment 身份及离线重新验收进行，保留旧失败；不覆盖 immutable slot，不自动回滚到旧 kernel 或 native adapter。安全撤销先阻止新 invocation，如何处置正在运行的请求在正式迁移中显式规定。

## 128 MiB 与 cold deadline 的兼容结论

现有唯一数值来源是 [Execution Profile manifest](../contracts/execution-profiles-v0.1/manifest.jcs)：

| 域 | 当前数值与性质 | 虚拟执行不能偷换的含义 |
| --- | --- | --- |
| checker request | 单 artifact 1 MiB、bundle 4 MiB、深度 128、集合项 10,000、semantic steps 1,000,000、5,000 ms、逻辑 working-memory 64 MiB | 内部逻辑计费不是 guest RSS，也不等于 Go heap 上限；沿用全部计数与拒绝路径 |
| checker process outer | stdout 1 MiB、stderr 64 KiB、6,000 ms、128 MiB `launcher-os-hard-limit` | 固定 guest RAM 不能证明整个宿主 physical footprint 同样受限 |
| 候选 guest RAM | 134,217,728 bytes，kernel / init / checker / bundle / 页表 / buffer 全部计入 | 不加第二块 RAM、balloon、swap、host share 或额外映射来绕过上限 |
| 宿主占用 | guest resident pages、runner control / streams、线程栈、系统 framework、Hypervisor backing，以及 parent 请求处理 | 不能只看 runner `ru_maxrss`、只数 `hv_vm_map` 或减掉未测量开销后声明满足原契约 |

`G_reserved + G_kernel + G_init + G_checker + G_bundle + G_buffers` 的**同时峰值**必须容纳于固定 guest RAM。装载副本、initramfs 解包、只读投影和 Go GC 瞬态不能各自通过大小检查后被漏算。历史 98,353,152-byte runner RSS 是合成观察，未包括真实负载，不能作为剩余容量承诺。

[Hypervisor memory management](https://developer.apple.com/documentation/hypervisor/memory-management) 提供 guest 映射原语；本次没有取得可对普通签名 runner 强制施加整个 host physical-footprint 硬上限的新证据。guest 内增加 [cgroup `memory.max`](https://docs.kernel.org/admin-guide/cgroup-v2.html) 也只能约束 guest 内计量域，不能修复宿主边界，且会扩大 init / kernel 配置面。

### 资源选择与迁移交接

项目所有者已正式接受下表第二项；长期边界见 [ADR 0015](adr/0015-virtualized-checker-resource-profile.md)，状态为 Accepted。维护投入单独按上节确认；8 MiB 控制缓冲仍为候选预算，公共版本分配、字节迁移与真实执行未获本次授权。

| 选择 | 可宣称的能力 | 后果 |
| --- | --- | --- |
| 保留整个宿主 128 MiB 硬上限 | 继续保持现行要求 | 当前 Hypervisor 候选没有满足证据，真实 checker 继续不可用；只做来源 / 纯设计，或以新 ADR 重选宿主 |
| **已接受：给虚拟执行定义不同的资源 profile** | guest 128 MiB 是硬映射上界；宿主控制内存按固定预算审阅，总 footprint 单独观察并明确没有等价硬保证 | 这是新的公开能力 / 信任边界，不是对 v0.1 的兼容解释；替代 ADR 已接受，另行验收并授权迁移 policy / profile / 外层记录和消费者 |

建议方案仍须禁止按 guest 声明长度进行无界 host allocation。自有控制缓冲可先按 **8 MiB 候选审阅预算**设计，列明每项固定容量、最大并发数与分配失败路径；这个数既不是已测量峰值，也不是把整个宿主限制改成 136 MiB。Hypervisor / OS 隐含开销无法被该预算硬约束，必须直接报告该缺口。总宿主内存硬限是调用方必需能力时，新的 profile 也必须被拒绝选择。

deadline 从 suspended spawn 前开始，覆盖身份校验、装载、boot、checker、输出收束和 teardown / reap。guest 内 5,000 ms 不得延后外层 6,000 ms；结果完整但 reap / 外层收束不满足要求也不能放行。watchdog 必须在预留清理时间内触发强制 vCPU exit；预留量由后续冷启动矩阵确定，不能把清理移到计时窗口外。OS 调度延迟与无法及时 reap 作为失败保留，不宣称实时系统级保证。

## 排他的 virtualized plan 与身份迁移

现有 [CheckerSpawnPlan](../crates/checker-runtime/src/spawn.rs) 绑定 native executable path、native target 和 host bundle realpath；新增虚拟执行不能只加一个布尔开关或把 executable 字段换成 runner。

建议的内部类型形状如下，名称仅表达职责，不是本次新增 API：

```text
ValidatedExecutionEnvironment + ValidatedGuestRegistration
  + VerifiedRunnerIdentity + ExactReadOnlyInputDescriptors
  + AcceptedVirtualResourcePolicy + HeldContainerAuditScope
    -> VirtualizedCheckerSpawnPlan
       -> one signed runner / one VM / one vCPU / one checker invocation
       -> verified complete guest stdout OR typed outer failure
```

若以后同时保留 native / virtualized 类型，用闭合 tagged union 表达，选择必须与登记的 execution kind 精确一致；Darwin native 分支继续不可执行。qualification 与产品调用共享同一个虚拟 plan 和 consumer，仅允许的登记状态 / 持久证据不同；不通过错误后尝试另一分支来选择 adapter。

| 身份层 | 必需绑定 | 排除项 |
| --- | --- | --- |
| execution host | 可信原生 `darwin / arm64`、受支持 OS / API 能力、原生而非翻译进程 | 用户参数、bundle 自述、文件扩展名 |
| signed runner | 精确 artifact、source / build、签名 requirement、opaque unique identity、固定 identifier、恰好两项 entitlement | 逐请求 identifier、写死 CDHash 算法、只验静态路径不验 suspended running code |
| guest environment | kernel Image、完整 config、init、DTB / 布局、transport、资源与设备 profile 的精确身份 | Alpine 版本别名、boot URL、宿主路径、未登记 device |
| checker target | 独立 `linux / arm64 / v8.0 / ELF`、精确 source / artifact / Go toolchain、source acceptance | 当前 Darwin record 重标、同源码推断同 binary、复用旧 companion digest |
| invocation | request / manifest / blob 原始字节与投影绑定，输入 descriptor 的真实复制字节、plan identity、完整结果或失败 | 自描述 host path、PID / 绝对目录进入公共 identity、guest 自报覆盖外层失败 |

装载必须验证**实际复制到受控内存的 bytes**。预先 `fstat` 或摘要相同不能防止同 inode 的内容修改；边读边计数 / 摘要，完整验证前不得 resume guest。guest 可写 RAM 在执行后当然可变，装载身份绑定的是开始执行前的已验证字节。runner 动态签名检查在 suspended child 上完成，执行后重验与失败观察不省略。

### 需显式迁移的消费者闭包

| 契约 / 实现 | 必要变更方向 | 保留边界 |
| --- | --- | --- |
| launcher policy / registration | 分离 host、runner、guest，闭合 execution kind、来源与可选能力 | 旧 v0.1 payload record 不追溯修改；未知版本 / kind 拒绝，active count 仍为 0 |
| execution profile | 明确计量域、host 保证缺口和 guest 设备 / 时间边界 | 不原地修改 `process-outer` 字节或把新保证标为旧能力 |
| installation receipt / slot / qualification | 同时绑定 runner 与 guest 制品组合、签名及 policy；三条 qualification 重新生成真实结果 | immutable、exclusive、append-only 与 inactive-before-active；旧 receipt 不证明新组合 |
| attempt / 外层运行记录 | 独立记录 guest RAM、host 观察、boot / teardown、runner / kernel / transport 与 container 审计 | 不是第二份 checker result，不向现有四项 checker TCB 填塞宿主角色 |
| Rust policy / selection / manifest / receipt / spawn / result | 严格解析新闭合字段、排他构造、旧 / 新错配拒绝，consumer 验 checker artifact 与外层组合 | 不复用 Checker Go parser；不让缺失字段采用默认成功 |
| 生成器、schema、readiness、bundle / companion 材料 | 列全正负例并重算被迁移内容的传递摘要；升级 source / artifact 后锁定新的实际输出 | 原规范与实验绑定材料保留；Evidence v0.2 如涉及，仍须同时处理 ADR 0009 |

checker 的 request / result v0.1 不应仅为打包方便而扩展。若迁移能够把宿主保证全部放在版本化外层记录中，可保留其 schema，但必须验证新 ELF、source 和当前支持规则对应的真实 result bytes；否则单独提出 Independent Check 版本决策。不能预先声称“无需任何跨仓变化”。

## guest 与 transport 的最小实现边界

Linux 启动只提供已审阅 RAM / DTB、GIC、architected timer 和固定输出设备；不实现网络、磁盘、host share、输入设备、通用 hypercall 或动态设备挂载。配置裁剪须验证最终 `.config`，不能因 DTB 没列设备就声称 kernel 没有相应代码。首轮评估关闭模块加载、网络与无关文件系统，保留 Go 所需进程 / 线程 / signal / futex / 时钟和受审阅的最小 RAM 文件系统。

init 先建立只读 bundle 投影和 mode / mount 边界，再以非特权 uid / gid、无 capabilities、空环境、空 stdin、空且不可写 cwd 启动 checker。文件路径只由固定 guest 根与合法 manifest entry 派生；checker 仍只接受 `check --bundle-root=<guest-canonical-realpath>`。挂载 / 降权 / `no_new_privs` / syscall filter 任一失败都不得启动 checker。

[seccomp 文档](https://docs.kernel.org/userspace-api/seccomp_filter.html) 明确 syscall filtering 本身不是完整 sandbox。不能用字符串路径过滤假装只读文件系统，不能假定过滤器能解引用用户指针，也不能只拒绝 `openat` 就覆盖所有写入方式；只读投影、文件权限、能力删除、过滤器和无 host device 共同验收。真实 Linux 后代必须在同一 VM 内，fork / exec 的实际许可范围由兼容性与负例验证确认。

transport 接收端必须核对 frame 类型 / 长度 / 序号 / EOF / 唯一终态；stdout 与 stderr 分别累加原有上限。启动日志、PID 1 诊断与 checker stdout 使用不同通道标识，任何未知 frame、重复 result、超限或尾随字节都形成外层失败。VMM 不把 guest 地址当 host pointer；所有地址加法、宽度、对齐、缓冲区索引都先验证，再复制到有界宿主缓冲。预复制 bundle 不需要 guest 向宿主发文件读取请求。

## 系统 / 硬件与 container 基线

首次产品化验证只声明 **macOS 26.6.2 / Apple Silicon arm64 / 单 VM 单 vCPU** 的候选范围。已有观察硬件为 `Mac17,2` / 32 GiB；不能由 API 从 macOS 11 可用或 store CI 通过外推到 M1、8 GiB、Intel、Rosetta 或全部 macOS 26。后续矩阵至少覆盖现有主机和另一较低内存 Apple Silicon 主机；具体设备可用性未确认，不虚构通过。首次支持矩阵还须核实 Hypervisor、签名、container 与严格 Darwin 文件系统原语。

[ADR 0014](adr/0014-darwin-app-sandbox-container-state.md) 允许的是安装级固定 container skeleton，不是 runner 获得任意持久存储。按 Apple [container 保护文档](https://developer.apple.com/documentation/xcode/protecting-local-app-data-using-containers)，普通协调器不能假定可以读改受保护 metadata 或删除整个 container。

建议将 container 审计分成三个时点：

1. 独立授权的初始化 / 安装验收阶段，在无 request 时建立固定 identity 的允许 inventory；只记录可合法观察的相对 entry、类型 / mode 与 opaque metadata 存在性，不读取受保护正文，不在首个业务请求后倒推允许基线。
2. 每次 invocation 前确认允许基线，reap 后比较。禁止新增 request 派生文件、可复用内容、跨请求读取、不可解释增量；无法观察、权限拒绝或无法区分系统 / 请求写入即失败关闭。metadata 的 opaque 例外只能对应事先定义的系统项。
3. 用请求 A / B、crash、timeout、恶意写入尝试验证无跨请求状态；卸载或升级对 container 的保留 / 删除另行授权，per-invocation launcher 不请求 root 或 Full Disk Access。

同一个 runner identity 的并发请求会破坏逐次 pre/post 归因。首版建议在审计范围内跨产品进程序列化该 identity 的 invocation；需明确受管锁的生命周期和 crash recovery。现有六项 store 能力不自动等价于 runner 审计租约，也不能未经决策挪用安装锁。若不能以可审阅方式协调、或平台不允许必要 inventory，则产品化保持阻断，不能标记为“无变化”。

## 真实负载与资源验收矩阵

执行本节前必须完成资源决策、来源 / 工具验收、公共身份迁移和精确执行授权；本稿不运行任何单元。容量材料与正式四题 / Agent 注册隔离，单独保存输入和预期，不重写锁定场景。

| 矩阵维度 | 首批材料 | 判定 |
| --- | --- | --- |
| 代表性负载 | 迁移后精确绑定的 AX-B01 correct、两个 wrong、invalid、backend timeout，以及其余三题各一代表 bundle | 区分预期 checker 四态与外层失败；旧指定态 kernel claim 材料不足不能强行要求 accepted |
| 安装资格 | 新 payload acceptance 对应的 `ax-b01-correct`、`chk-digest-01`、`chk-resource-01` | 在与产品相同 plan 下对照新 binary 的实际 companion 原始 / 文档摘要；旧 Darwin 预期不可重用 |
| 请求容量 | artifact 1 MiB、bundle 4 MiB、深度 128、集合项 10,000 的合法边界与各自越界值；选择能形成完整闭包的组合 | 不用非法填充或 unused blob 冒充最大合法 bundle；分别记录传输、boot、内部资源拒绝与完成情况 |
| 布局 / RAM | 已接受 kernel / init / checker 的最大制品长度；装载与解包重叠峰值；guest 全 RAM 触页及首个未映射地址 | guest mapping 始终恰好 128 MiB；OOB 失败；固定 host 缓冲不随恶意长度增长；真实 host footprint 单列 |
| cold lifecycle | 每个已声明主机 / OS，fresh runner / VM 正常至少 30 次；压力材料至少 10 次；首次 container 建立与安装另列 | 保存全部样本、最大值和失败，不以平均值掩盖任何超时；不暖机复用 VM，OS 文件缓存冷热条件如实记录 |
| 异常收束 | boot crash、checker / 后代 crash、hang、边界时刻退出、stdout / stderr 上限与上限加一、重复 / 截断 frame | 强制 exit / destroy / unmap / reap，失败前缀不可消费；同一精确制品重试须新 attempt |
| container / 身份 | descriptor path replacement、同 inode 写入、截断、签名或 entitlement 错配、A/B 请求、审计锁持有者 crash | 错误必须在允许的执行前门禁或结果门禁失败；保留可观察异常，无 host 数据清理旁路 |

至少记录：输入 raw digest / 长度、source / artifact / tool identity、host / guest 环境、guest 映射与可用内存、逻辑计数、guest checker / init 峰值、runner 和 parent 的分项宿主观察、spawn / boot / checker / teardown 时间、stream 总量、真实 exit / signal、结果摘要或外层失败、container 及清理状态。不可获得的字段标记未观测，不用 0 补齐。

只要合法声明范围不能在限制内完成，就保留对应失败或未知。裁剪配置可以在新构建身份下重新验收；降低公开输入上限、放大 memory / deadline 或换 warm VM 则必须重新决策。

## AX-B01 依赖交接

P0–P9 逐阶段的输入、解除证据与首个纵向验收集合见[AX-B01 首切片依赖审阅](axiom-pipeline-first-slice-dependency-review.md)。尤其应先核对 cvc5 / Node 自身的 outer hard memory 与执行宿主；checker 的 Hypervisor 决策不能自动用于另外两种工具。该审阅保留 ADR 0007 全部实现入口，只区分技术依赖与产品包装依赖。

## 下一切片与停止条件

| 顺位 | 输入与具体交付 | 完成 / 停止标准 |
| --- | --- | --- |
| 1：资源与维护决策 | [ADR 0015](adr/0015-virtualized-checker-resource-profile.md) 已接受；8,000 行预警线 / 最多 10 人日 / 每周 4 小时投入已确认，项目所有者统一负责 runtime 与 kernel / init | 决策已收口；既有 v0.1、inactive 登记及来源 / 迁移 / 执行门禁继续有效，预算不代表能力验收 |
| 2：来源与可复现输入锁 | kernel / Debian、Rust 配方及 musl 补证已有诊断，见[guest 来源审阅](checker-runtime-guest-source-build-review.md)。musl 有条件路线、诊断工具窄信任、本机归档 / 恢复与九项真实验签已形成；[来源验收审阅](records/rust-linux-input-review/musl-source-acceptance-review-2026-09-16.md)的限定声明已获确认，该精确原包来源验收通过；异盘保留并行安排。其余六项已盘点来源路线，MPC / MPFR 原包与公钥已取得；MPFR 六项真实验签通过，[限定来源声明](records/rust-linux-input-review/mpfr-source-acceptance-review-2026-09-25.md)已获项目所有者确认，该精确原包限定来源接受通过；MPC 上游签名尚未验证，[固定 Debian 路线审阅](records/rust-linux-input-review/mpc-source-acceptance-review-2026-09-25.md)限定声明已获项目所有者确认，该精确原包限定归档来源接受通过；其余四项已补原包 / 公钥 / 内容材料，见[分项状态](checker-runtime-guest-source-build-review.md#rust-配方剩余输入的-9-月-25-日状态)，GMP 两次诊断失败与 GCC / Binutils 认证阻断、headers 未认证不解除；继续补发布构建关联、Rust 公钥绑定与宿主库；[隔离安装范围](checker-runtime-linux-install-slice-review.md)已有，实际安装 / 有限执行仍未验收 | 不把摘要 / GnuPG 成功 / 库存等同完整 acceptance；不沿用默认 Go 或未知 builder；安装 / 构建须精确授权，不导入旧 probe 的虚构源码 |
| 3：公共迁移与合成装置 | 接受的资源 ADR、source lock、身份 / consumer 闭包；生成新 policy / profile / 外层记录的正负例，再实现可留存合成 runner / guest | 未完成字节迁移和单独签名 / VM 授权前不得运行；不把合成装置算作产品 qualification |
| 4：真实容量与离线复核 | accepted Linux checker + guest TCB、代表性 / 上限输入和预注册 cold 矩阵 | 分别授权受控执行；失败保留，超预算或不可审计 container 触发重新决策 |
| 按独立依赖准备：核心管线入口 | cvc5 / Node 来源与各自执行边界、ADR 0007 八项入口核对、AX-B01 P0–P9 切片设计、checker 目标归因交接 | 纯设计不必等待产品安装 / 激活；生产实现仍需全部入口或正式切片例外决策，不跨仓写入 |

真实产品 fetch / install、生产签名、三条 qualification 和 active 转换最后按各自门槛闭合。以上顺位不授权分仓写入、外部消息、远程发布、全局工具或系统配置变更。

## 本次验证与保留事项

本稿通过只读契约 / 实现核对、官方资料检索、bundle 静态大小核算及仓库文档检查形成。没有新跑源码构建、性能、Hypervisor、签名、container 审计或 checker / cvc5 / Node；旧运行结果只按其精确来源引用。正式语义、IR / Evidence、ADR 0008 / 0011 / 0013 原文与 `contracts/` 字节保持不变；2026-09-10 仅将已确认的 ADR 0015 从 Proposed 转为 Accepted，并落实维护投入与责任。2026-09-12 按[日终代码 / 文档复核](records/2026-09-12-closeout.md)同步 musl 诊断前置进展；当天真实工具运行属于单独授权的来源诊断，不是本产品化方案的执行验收。2026-09-16 按[日终复核](records/2026-09-16-closeout.md)同步限定 musl 来源验收与剩余材料状态，未扩大为 builder 或产品验收。2026-09-25 按[日终复核](records/2026-09-25-closeout.md)同步 MPFR / MPC 限定接受及四项剩余输入材料，未形成完整 source lock 或安装验收。当前顺位由[当前状态](status/current.md)维护。
