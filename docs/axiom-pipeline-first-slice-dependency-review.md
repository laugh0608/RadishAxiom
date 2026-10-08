# AX-B01 真实管线首切片依赖审阅

审阅日期：2026-09-06；阶段入口整理：2026-09-29；新 P2 目标归因接续：2026-10-08

状态：完整管线依赖已梳理；组件入口按已接受的 ADR 0016，真实工具执行门槛不变。

用途：明确首个真实 P0–P9 与独立复核的必要前置，避免把产品安装包装扩大为所有语义工作的依赖。

读者：pipeline、checker、runtime 实现者和项目决策者。

不包含：生产管线实现、工具下载 / 安装 / 执行、公共语义或格式变更、切片例外授权。隔离来源、内存兼容性、宿主身份与容量矩阵统一见[产品化依赖审阅](checker-runtime-productization-dependency-review.md)。本稿以主仓 `a195232` 的规范、readiness 和 AX-B01 语料做静态核对，不重验跨仓动态结果。

## AX-B01 的真实 P0–P9 依赖

这里区分“阶段技术上需要什么”和“当前获准进入什么”。[ADR 0007 的八项实现入口](adr/0007-first-verification-first-compilation-pipeline.md#进入受控实现的验收条件)仍约束完整管线；本表不取消其中的 cvc5 / Node 来源审阅、跨平台字节或独立验收要求。组件实施仅适用下述已接受例外，不能扩大为生产编译器骨架。

[ADR 0016](adr/0016-core-semantic-slice-entry.md)已接受更窄的 P1–P2 组件入口：先验收 P1，P2 在生产义务版本明确后进入；不包含完整 P0 invocation 或 P3 实现。下表描述完整管线依赖，不要求每个纯组件预先具备产品安装能力。

| 阶段 | 必需输入 / 实现与解除证据 | 不属于该阶段技术前置 |
| --- | --- | --- |
| P0 | 精确 invocation / mode / assurance / tools / limits；实际字节捕获，未知或缺失身份停止；未验收工具场景仍拒绝 | checker 激活、最终安装 UI |
| P1 | 完整首域 IR 严格 parser / normalizer / 类型效果检查与规范字节；非法输入和资源失败分开 | VM、checker binary；但不能直接复用当前 ASCII runtime parser 冒充完整 Unicode IR |
| P2 | 独立于 Checker 实现的完整义务生成；正确及两个 wrong 候选、稳定 ID、遗漏义务负例 | 产品下载器、container inventory |
| P3 | 每义务确定性 QF_UFLIA 编码；类型、WF / Pre / 目标违反的语义映射、跨平台逐字节一致 | VM 安装；生成 query 不等于执行 solver 或证明正确 |
| P4 | cvc5 `1.3.4` 精确 source / artifact / 许可证与 adapter 验收；真实逐义务进程、硬限制、model 重建及目标反例重放；明确 attestation / certificate policy | checker 产品激活；但不得把 checker 的 Hypervisor 方案自动复用给 cvc5 |
| P5 | benchmark-data 到 host-data 的严格转换，base / boundary / invalid，前置、键与容量核验 | Node 已启动、安装资格复核 |
| P6 | 门控全部满足后，确定性且可审阅的自包含 Node module；生成代码许可边界闭合 | 产品 runner 签名；但无 P4 / P5 真结果就不能开放 target gate |
| P7 | Node `24.19.0` 精确来源、Permission Model 与外层时限 / memory / 环境边界；每输入新进程 | guest checker 已 active；但 V8 old-space 64 MiB 不替代总进程硬限制 |
| P8 | 严格 output codec、宿主一致性与独立黄金比较；wrong output / operational failure 区分 | 自动升级、最终产品界面 |
| P9 | 真实 attempts / artifacts 装配 Evidence 与 receipt、保留失败与恢复历史、严格身份闭合；生产自检只给生产结论 | installer UI、SDK、语言表面语法 |
| P9 后独立复核 | 新 Linux checker acceptance、目标归因核实、受控 launcher / guest、独立 source / parser / replay、同一 Evidence digest 的离线真实结果 | 正式 Agent 模型调用；受控验证也不等于任意产品请求获准执行 |

**cvc5 和 Node 的 Darwin 执行限制是独立缺口。** 它们的 outer profile 也要求 OS hard memory，Node Permission Model / cvc5 内部预算都不能自动提供该保证。ADR 0013 只选择 checker 宿主，不授权把 solver / Node 放进该 guest。可以先做来源与 adapter 静态审阅；真实 P4 / P7 前需各自证明已有 profile 能执行，或按对应 ADR 重新决定宿主 / profile。若选其他平台，也必须有该平台精确工具 acceptance 和执行授权。

### 首个纵向切片的验收材料

沿用 [AX-B01 task](../benchmarks/keyed-finite-table-v0.1/ax-b01/task.json) 与 [readiness manifest](../contracts/implementation-readiness-v0.1/manifest.jcs)，不另造状态或成功码：

- `AX-B01-CORRECT`：base 与 boundary，从 candidate 真实走完 P0–P9，再独立复核；公开 golden 只参与对照，不能驱动生产结果。
- `AX-B01-WRONG-ADD` / `AX-B01-WRONG-DROP-ZERO`：必须按精确版本验证所声明目标确实违反，加入“其他义务失败而目标成立”的独立合成区分例。新 P2 / P3 中，wrong-drop-zero 的错误筛选仍可满足相对于实际谓词的内建 row-coverage，原业务丢行要求应由 contract-guarantee 定位；不能移植旧指定态标签。全部必需 attempt 真实产生，P6–P8 不运行。
- `AX-B01-INVALID-INPUT` / `AX-B01-BACKEND-TIMEOUT`：分别保留 P5 invalid / P4 timeout，门控关闭，不生成 module 或伪造 host attempt。timeout 要由受控真实执行取得，不以手填 `unknown` 替代。
- `PIPE-GATE-BYPASS-01`、`PIPE-CACHE-FORGED-HIT-01`、`CHK-DIGEST-01`、`CHK-OBLIGATION-01`：按既有摘要链构造有效到达目标检查的篡改负例；同时保留 P9 装配、恢复与 host mismatch 的既有验收要求。

四题范围、八个 wrong、六平台指定范围和 Evidence v0.2 的 group 修正义务没有因先做 AX-B01 而删除。首条独立证明链不是允许 attestation 的基本产品流程前置，但 `certificate-required` 必须拒绝当前空支持集合，任何 accepted-with-trust 都不能升级为独立 proof。

P3-D 之后的具体缺项和拟议顺位见[剩余结构义务与 P4 接续审阅](query/p3-structural-obligations-and-p4-review.md)。当前 AX-B01 每份 IR 的 13 项 P2 义务中，九项可生成 query；effect-empty、两个 field-origin 与 ir-structure 的实际结果支持仍须分别闭合。单目标后端尝试不以其他义务已完成为技术前提，完整验证仍要求全集；该区分不接受新 adapter、Evidence 或真实工具执行。

下一切片只按[当前状态](status/current.md)的全项目顺位推进；[产品化审阅](checker-runtime-productization-dependency-review.md#下一切片与停止条件)描述产品运行线内部依赖，不作为纯语义组件的全项目串行前置。本稿不构成实施或执行授权。
