# ADR 0015：虚拟 checker 资源 profile 与宿主保证边界

日期：2026-09-06

状态：Proposed

用途：为 Darwin 上逐次 Hypervisor checker 定义独立资源保证，明确 guest 硬上限、宿主总内存保证缺口、排他选择和公共迁移范围。

读者：产品决策者、runtime / launcher、独立 checker、机器契约与安全审阅维护者。

不包含：接受具体 kernel / init / builder、批准维护预算、分配格式版本、修改公共机器字节、实现或执行 runner / checker、签名、qualification、激活、提交或远程动作。

项目所有者已确认“guest 保留 128 MiB 硬上限，宿主总占用没有等价硬保证”的起草方向。本文件是可审阅草案，尚未替代任何 Accepted ADR，也不是实现依据。来源、投入与验证顺位由[产品化依赖审阅](../checker-runtime-productization-dependency-review.md)及[当前状态](../status/current.md)维护。

## 背景与选择

[ADR 0008](0008-independent-checker-isolation-and-artifact-exchange.md)与 [Execution Profiles v0.1](../../contracts/execution-profiles-v0.1/README.md)冻结了 checker 的内部逻辑资源与外层进程硬限制。[ADR 0013](0013-darwin-checker-hard-isolation.md)选择 signed App-Sandboxed Hypervisor runner，但要求在“整个宿主 physical footprint 也须受同一硬限”无法闭合时重新立 ADR。

[产品化资源审阅](../checker-runtime-productization-dependency-review.md#128-mib-与-cold-deadline-的兼容结论)确认了该缺口：固定 guest RAM 不包括 runner、parent、系统 framework 与 Hypervisor 的全部宿主开销。固定控制缓冲、峰值采样、guest 内存限制和合成运行成功均不能证明现行 `process-outer / launcher-os-hard-limit` 已满足。原 probe 只剩历史观察，不能提升为可重跑验收。

| 方案 | 可承诺的资源边界 | 取舍 |
| --- | --- | --- |
| 保持整个宿主 128 MiB 硬限 | 继续要求现行能力 | 当前候选没有满足证据，真实 checker 继续阻断；仍可审来源或重选宿主 |
| 为虚拟执行另立 profile | guest 128 MiB 硬限；明确不承诺宿主总内存硬限 | **本草案选择**；调用方必须能识别较弱的宿主保证，且不得隐式降级 |
| 原地重解释旧 profile、以 RSS polling 或 guest cgroup 代替宿主硬限 | 名称相同但能力不同 | 拒绝；破坏既有调用方的资源要求与兼容性 |

选择第二项意味着接受**整个宿主内存耗尽风险未被该 profile 的硬限消除**。恶意请求即使不能扩展 guest RAM，仍可能通过被信任的 runner / framework 开销影响宿主；降低该风险需要有界实现和验收，但不能声称具有 OS 强制的总量保证。

## 拟议决策及替代范围

本 ADR 若被接受，只对 **Darwin execution host + signed Hypervisor runner + Linux arm64 checker guest** 引入新的资源能力组合：

- 窄替代 ADR 0008 / 0011 中要求该虚拟路径继续满足旧外层进程 memory profile、以及把 host target 与 checker target 合并选择的部分；
- 窄替代 ADR 0013 中“保留全部现行 hard boundary”和将 guest mapping 对应旧 working-memory 保证的部分，明确这里改变了宿主内存保证；
- 保留 ADR 0013 的逐次 runner / VM、签名、descriptor 字节装载、网络与设备限制、后代 containment、deadline、失败关闭和无 fallback；保留 ADR 0014 的全部 container / TCB 边界；
- 不替代其他 native 平台的硬限，不改变 cvc5 / Node 的资源要求，也不解除 ADR 0007 的生产管线入口。

当前 Accepted ADR 原文及已绑定摘要不在草案阶段改写。接受后应在迁移清单中标明上述窄替代关系；旧决策的其余条款继续适用，不能把 ADR 0008、0011 或 0013 整体标记为失效。

### 三个资源计量域

| 域 | 新虚拟路径的要求 | 不允许作出的推断 |
| --- | --- | --- |
| checker request 内部 | 保留七项现行计数、64 MiB 逻辑 working-memory、5,000 ms 与原拒绝语义 | 逻辑计费不是 Go heap、guest RSS 或宿主硬限 |
| guest 可寻址 RAM | 总量恰好 `134,217,728` bytes；kernel、init、checker、bundle、页表、解包副本和 buffer 共同使用 | 不能声称 checker 独享 128 MiB，或把各阶段峰值分别通过当作同时峰值通过 |
| 宿主 | 自有缓冲必须有静态容量与有界分配；总占用分项观察，**不承诺 OS 强制的总宿主内存硬上限** | 不能将 guest 128 MiB 加控制预算后宣称新的宿主硬限，也不能从观察值推出未采样峰值 |

guest 不得通过第二块 RAM、额外可寻址 image 映射、balloon、swap、host share 或动态设备扩容。MMIO 只承担受审阅的固定通道，不得提供扩展存储。访问未映射 guest physical address 必须形成外层失败；映射构造、整数溢出与所有 VM exit 都按不可信输入处理。guest kernel 也不能作为宿主地址 / 长度合法性的担保者。

runner 与 parent 的自有控制 / stream 分配须列出容量、数量、最大并发与失败路径，拒绝先按 guest 长度分配再校验。产品化审阅中的 8 MiB 仅是控制缓冲候选预算，尚未冻结；它不覆盖全部栈、运行时、framework 或内核开销，不是新的公共 memory limit。未知开销不能记为零。

宿主观察须记录度量名称、范围、采样方式、时间与不可观测项，区分 guest mapping / resident pages、runner、parent 及系统开销；共享页和不同时刻的峰值不得直接相加冒充精确总量。观察采集失败不得填写虚构数值；正式外层记录须区分不支持的可选度量与必需审计失败。任何观测或软件预算都不能满足调用方的宿主硬限要求。

### 时间、输出与结束条件

外层 `6,000 ms` 从 suspended spawn 前开始，包含身份校验、装载、boot、checker、完整输出、VM 销毁与 runner reap。内部 `5,000 ms` 不重启或延后外层计时。保持 stdout `1,048,576` bytes、stderr `65,536` bytes 上限；boot / init 诊断不得混入 checker stdout，transport 自身也须有界。

仅在完整结果、身份复核、container 审计及外层收束都通过后，才可交给现有结果消费者。超时、guest OOM / crash、非零退出、VM exit 异常、stream 超限 / 截断、身份漂移或清理失败只能形成外层失败；不得合成 checker `incomplete`，也不得保留超限前缀作为结果。checker 内部主动资源拒绝只有在结果完整且外层全部通过时，才按原协议消费。

watchdog 必须预留收束时间；具体预留量由 cold 矩阵验收。无法在窗口内完成 reap 即失败，后续仍须收束已创建资源并记录实际完成时间，不能因宣告失败而遗留进程。该截止判定不承诺通用 OS 具有实时调度能力，也不允许把清理移到计时窗口外后宣称成功。

## 排他选择与身份

新 profile 必须以可区分的版本化身份表达 guest 硬限及宿主硬限缺失；本草案不提前发明 canonical 字段名或版本号。调用方的资源要求来自可信配置 / policy，不能由不可信 bundle 声明。只有明确允许该能力组合、全部来源 / 身份 / capability 均通过且对应 runtime 状态合格，才能构造虚拟 plan。

| 调用方要求或输入 | 选择结果 |
| --- | --- |
| 明确允许新虚拟 profile，且 host / runner / guest / checker 与该用途的登记状态匹配 | 可进入新 plan 构造；不表示已运行或独立验证通过 |
| 要求整个宿主内存 OS 硬限，或仍要求旧 `launcher-os-hard-limit` | 拒绝该虚拟候选；不得自动降低要求 |
| 未声明新能力、缺少字段、未知版本 / kind 或新旧记录混用 | 拒绝；不得默认选择或试跑探测 |
| 虚拟 plan 构造或执行失败 | 保留原失败；不得切换 native、URL boot、warm VM 或 root broker |

新 plan 与现有 native `CheckerSpawnPlan` 排他构造，不能只换 executable 或加一个绕过校验的布尔值。Darwin native 仍为 `RequiredNotProven`，现有 Mach-O payload 保持 `registered-inactive`，active runtime 为 0，直到相应独立门槛被实际解除。

必须分别绑定可信 Darwin host、runner 的 source / artifact / 动态签名 / 精确 entitlement、guest kernel / config / init / layout / transport、Linux checker source / ELF artifact 以及资源 / 设备 profile。装载身份绑定实际复制后的字节，验证完成前不得执行 guest。宿主 TCB 不得填入现有四项 checker TCB 或由 guest 自报证明；现有 checker CLI 不因虚拟打包而增加第二入口。

qualification 与业务调用共用同一 plan 和结果消费者，但用途门禁不同：资格验收从已核实的 `installed-inactive` 组合及安装 receipt 开始，不循环要求已有 qualification；业务调用必须具备当前组合的 qualification 和 active 登记。profile、runner、kernel / init / layout / transport、checker 或被绑定的宿主能力变化都须重新核对组合身份和资格；旧 Darwin companion 或旧 qualification 不证明新的虚拟组合。

## 公共迁移闭包

执行迁移前应逐项形成旧 / 新兼容矩阵，并沿[版本分层 ADR 0003](0003-version-identities-and-compatibility-layers.md)分配格式版本；不能原地重解释 v0.1 或只修改 README。

| 范围 | 必须完成的迁移 |
| --- | --- |
| execution profile / launcher policy | 明确 execution kind、计量域与宿主保证缺口；旧消费者必须拒绝新 profile |
| 工具与 payload 登记 / acceptance | 分离 host / runner / guest；Linux ELF 重新构建验收，不能重标 Mach-O 或复用 binary digest |
| receipt / slot / qualification / attempt | 绑定完整组合与新资源身份，区分宿主观测和强制能力；重建三条真实 qualification，保留 immutable / append-only 和 inactive-before-active |
| Rust parser / selection / manifest / spawn / result | 严格消费新增身份，拒绝新旧混用；外层失败优先，保持单一 checker result 消费入口 |
| schema / 生成器 / readiness / bundle / companion | 从唯一规范源生成，重算传递摘要；旧指定态材料保留，不把未运行的新结果填成验收记录 |
| Independent Check / Evidence / 跨仓交接 | 先验证宿主信息能否完整留在外层记录；若可以，保留 request / result schema 并重验真实 ELF 输出；否则另提格式迁移，涉及 Evidence v0.2 时仍须满足 ADR 0009 |

接受本 ADR 也不等于接受上述机器格式或授权迁移实施。回退应停止选择新候选、保持 runtime unavailable，保留既有 immutable 记录及失败证据；不得把新 slot 降格重标为旧版本、擦除失败或恢复 native best-effort。

## 后续验收与停止条件

机器迁移必须包含下列可执行验收材料；本草案只定义要求，不声称测试已运行：

| 类别 | 必备材料与判定 |
| --- | --- |
| 正例 | 完整身份且明确接受新能力的 plan；内部资源拒绝的完整结果与正常结果分别按协议消费 |
| 负例 | 未知 / 缺失 profile、旧 receipt 配新 guest、checker / runner / kernel 错配、额外映射、超长 frame、签名漂移均拒绝 |
| 关键反例 | guest 恰好 128 MiB 且宿主观测超过 128 MiB：不能因此声称旧宿主硬限通过；要求旧硬限的调用方必须在执行前拒绝新 profile，即使某次观测低于 128 MiB |
| 时间与清理 | 完整 stdout 先到但 reap 超时、边界时刻退出、后代残留、清理失败均不得消费成功；记录真实收束时间 |
| 兼容性 | 旧消费者拒绝新版本；新消费者不把旧记录提升为虚拟资格；旧摘要材料可独立按旧版本复核，不参与新执行选择 |
| 动态容量与可信边界 | 已接受来源下的真实代表性 / 上限 bundle、cold lifecycle、全 RAM 触页、OOB、恶意设备输入、container 跨请求与清理矩阵；留存源码、输入和全部失败 |

动态验证的详细材料沿用[产品化验收矩阵](../checker-runtime-productization-dependency-review.md#真实负载与资源验收矩阵)，每项仍需自己的来源、工具、签名与执行授权。来源、维护负责人和预算未闭合，或容量 / deadline / container / 签名无法满足时，保持阻断并重新决策；不得自动扩大资源或支持矩阵。该 profile 也不提供宿主总内存的跨请求聚合硬限。

本决定会缩小可接受调用方范围并扩大显式信任边界；收益是使实际能力可识别、可拒绝、可验收。它不降低独立 checker 的证明要求，不改变 `proved`、`checked`、`unknown`、`failed` 或 `trusted` 的含义，不把虚拟执行或动态成功升级为独立 proof。
