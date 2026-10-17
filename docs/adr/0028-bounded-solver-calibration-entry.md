# ADR 0028：真实 solver 校准与单目标诊断的窄入口

日期：2026-10-17。状态：Accepted。项目所有者已接受 D1–D3，并授权提交准备材料、继续精确 CLI 依赖 / 许可证补证与执行层实施清单；未授权构建镜像、运行探针、启动 solver、修改系统配置或 push。

用途：为 P4 的真实模型协议与单目标诊断提出可单独验收的入口，明确它与完整验证后端原型、产品隔离及 Evidence 的关系。

## 背景

[ADR 0027](0027-compact-query-and-p4-binding.md)的生产组件已通过本机验收。原容量 AX-B01 新查询小于 1 MiB，但纯请求规划与合成模型不能认证真实工具身份、打印文法、资源限制或反例来源。

[ADR 0005](0005-first-verification-backend.md)的完整原型入口同时要求四题证明、八个错误候选、失败矩阵、三系统与 Evidence；[ADR 0016](0016-core-semantic-slice-entry.md)及后续组件 ADR 没有授予真实执行例外。直接用 Docker 启动 cvc5 会跨越这个边界，不能把安装工具视为纯组件授权的延伸。

本次[准备记录](../records/2026-10-17-solver-preparation.md)选定现有 OrbStack Linux arm64 Docker 宿主作为诊断候选。制品摘要与静态 ELF 布局检查通过，完整依赖 / 许可证验收与宿主动态资格仍未完成。

## 决定

1. 增加独立的**本地诊断入口**，只允许精确 cvc5 1.3.4 non-GPL Linux arm64 CLI、既有 P4 新 profile、最多八份小型协议校准查询，以及校准合格后一次原容量 AX-B01-wrong-add 的 contract-guarantee 尝试。每份输入独立进程、一次执行；失败保留，不自动重试、换工具或换 profile。
2. 这是对 ADR 0005 完整原型入口和 ADR 0007 完整管线实施入口的限定分阶段例外：不要求在协议校准前先取得四题证明和完整 Evidence，但仍要求精确工具 / 依赖 / 许可证接受、可审阅执行层、资源与能力资格以及当前任务的执行授权。完整原型的原门禁保持，不因一次诊断通过而标为完成。
3. 使用现有 OrbStack Linux arm64 宿主，不启动停止中的 UTM 虚拟机、不复用兄弟项目容器或工具镜像、不把结果称为 Darwin native 或产品 checker 资格。宿主、运行时或镜像变化后原资格失效；没有自动切换 Docker context、原生执行或虚拟机的路径。
4. 使用既有 immutable SolverRequest 与固定十二项 argv；不追加 get-model、版本查询、proof dump 或调试选项，不扩大模型 parser。只通过显式的新执行层认证进程与响应来源。原 P4 规则及其 `planned-not-calibrated` 字节保持，真实观察绑定在单独的本地诊断记录中。
5. stdin 1,048,576、stdout 4,194,304、stderr 65,536、外层内存 134,217,728 字节与时限 6,000 ms，内部 steps 1,000,000 / time 5,000 ms 均保持。内存范围为隔离 cgroup 内的 bootstrap、solver 及全部后代；Mac 控制进程、Docker daemon 和 Linux VM 整体不是该 128 MiB 范围。该范围已经显式接受，不能引用 ADR 0015 的 checker guest 例外自动成立。
6. 外层终止、资源超限、流截断、退出失败或来源不明均失败关闭；真实 unknown 保留 unknown。sat 只进入既有解码与 P4-B 精确重放；unsat 仅记录后端观察。本入口不产生 proved、公共 counterexample、backend-attestation、Evidence 或完整 pipeline receipt，也不冻结公共执行观察格式。

## 资源解释与停止条件

执行层方案见[窄入口执行设计](../query/solver-execution-preparation.md)。cgroup v2 的 `memory.max` 是内核限制机制，但官方文档允许部分情况下暂时超过限值；不能据此承诺所有瞬时 RSS 或整个物理宿主永远低于 128 MiB。[内核文档](https://docs.kernel.org/admin-guide/cgroup-v2.html)

本决策接受上述明确的 Linux cgroup 记账口径；记录 peak、events 与 swap，不能仅采样 RSS 或把 OOM 日志解释成硬资格。若要求绝对瞬时物理上界，则本方案停止，另审阅执行宿主和 profile，不调高原数值。6,000 ms 也不是已取得的实时调度保证：正常完成须在外层窗口内完成进程终止、流收尾与无遗留确认；超时后的失败收集不能改写成窗口内成功。

当前不满足执行前置：完整制品接受、最小 bootstrap 的来源 / 构建、受限加载与系统调用策略、OOM / timeout / 流 / 清理负向探针尚缺。不能为了让诊断发生而跳过这些项目；若现有宿主不能在不修改系统配置的条件下支持方案，报告阻断，不自行调整系统或启用 privileged 容器。

## 已接受的决定

| 项目 | 已接受范围与后果 |
| --- | --- |
| D1：窄入口 | 接受八份校准加一次指定目标的诊断范围及完整原型门禁例外；不授权本次实际执行 |
| D2：宿主与资源 | 接受 OrbStack Linux arm64 候选、cgroup 进程范围与内核限制语义；Mac / daemon / VM 开销另行报告，不冒充被 128 MiB 包含 |
| D3：后续实施边界 | 先补精确制品接受材料，再实现固定请求执行层和合成负向探针；镜像构建、容器探针和真实 solver 分别列出目标、副作用、时间与清理方式后授权 |

接受本 ADR 不等于上述缺口已闭合，也不自动授权 fetch 其他依赖、安装、执行、系统配置、push、远程发布或正式 Agent 实验。保持旧 query / P4 规范字节、IR 容量和全部既有资源限值。
