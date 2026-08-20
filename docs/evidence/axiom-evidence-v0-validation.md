# Axiom Evidence v0.1：验证矩阵

状态：Accepted

更新日期：2026-08-20

用途：定义 [Axiom Evidence v0.1](axiom-evidence-v0.md) 对 ADR 0002 四个基准的状态映射、必需负向验证和进入实现前的 Evidence 验收条件。

读者：基准语料维护者、Evidence 与独立检查器实现者、工具链评估者和阶段验收者。

不包含：新的 Evidence 字段、状态、义务类别、证明后端、实现语言或基准制品字节级格式的重复定义。

四个任务的版本化候选、fixture 和 Expected Evidence 最低断言见[有键有限表基准语料库 v0.1](../benchmarks/keyed-finite-table-corpus-v0.md)。这些断言不是已经产生的 Axiom Evidence。

## 四个基准的 Evidence 映射

| 基准 | 核心 `proved` | 具体 `checked` | 错误候选的 `failed` |
| --- | --- | --- | --- |
| AX-B01 订单净额 | 筛选双向覆盖、减法定义、范围、键与效果 | 输入符合、示例 / 边界输出 | 单行 world、算术或丢行 trace |
| AX-B02 客户等级连接 | 外键、恰好一次匹配、无扇出 / 丢行、字段来源 | 两表输入与黄金输出 | 一个订单加两个同区客户的 row-pair |
| AX-B03 账户用量汇总 | 分区覆盖 / 不相交、计数与求和、守恒、范围 | 空表、单组、边界数值输出 | 带组键、事件键和差额的 group witness |
| AX-B04 工单最小化导出 | 字段白名单、行覆盖、字段与控制非干扰 | 示例与成对夹具输出 | 两个公开等价 world 或字段依赖 trace |

四个基准的 verification Evidence 可以在没有宿主执行时得到 `satisfied`，但只说明静态 verification profile 完成。ADR 0002 的整体基准通过必须使用 benchmark profile，并在独立结果达到预注册策略要求后才能记录通过。

## 必需验证矩阵

| ID | 输入 / 变化 | 预期结果 |
| --- | --- | --- |
| `EV-CAN-01` | 只改变 JSON 空白或 object member 输入顺序 | normalizer 恢复相同规范字节；strict checker 拒绝非规范原字节 |
| `EV-HASH-01` | 修改 tool / execution / obligation definition 并保留旧 ID | 拒绝 ID 不一致 |
| `EV-ARTIFACT-01` | artifact 字节与 content digest 不同 | 独立检查拒绝依赖结果 |
| `EV-IR-01` | IR raw digest、文档域摘要或语义摘要不匹配 | 拒绝 |
| `EV-OBLIGATION-01` | 删除一个范围或非干扰义务 | 独立重建集合后拒绝遗漏 |
| `EV-OBLIGATION-02` | 增加未知、重复或错误 expectation 的义务 | 拒绝 |
| `EV-STATUS-01` | 用 `checked` 完成核心 prove | 拒绝状态漂移 |
| `EV-STATUS-02` | 用 `trusted` 绕过失败或未知核心义务 | 拒绝信任洗白 |
| `EV-UNKNOWN-01` | timeout / 资源耗尽 attempt | 保留 `unknown`，结论不得 satisfied |
| `EV-FAILED-01` | failed 反例不满足 Pre 或无法重放 | 拒绝 failed 声明 |
| `EV-MIN-01` | heuristic shrink 标为 proved-minimal | 拒绝最小性过度声明 |
| `EV-INPUT-01` | 具体输入键重复 | `input_rejected`，不评价程序正确性 |
| `EV-HOST-01` | 核心义务 proved 但宿主输出不同 | `implementation_inconsistent` |
| `EV-CONCLUSION-01` | 义务集合与 conclusion 不一致 | 拒绝生产聚合 |
| `EV-CHECKER-01` | 生产工具自报独立检查成功 | 不采纳；必须由外部 checker 绑定 Evidence digest |
| `EV-VERSION-01` | 未知 Evidence `0.2` / `1.0` | 精确拒绝，不按 `0.1` 猜测 |
| `EV-MIGRATE-01` | 未来受支持显式迁移 | 记录源 / 目标摘要并重新生成义务与检查结果 |

命令退出码为零不能替代结构、摘要、负向拒绝、重放和独立结果检查。语料库必须同时提供预期接受和预期拒绝，不得只保存 happy path。

## 进入实现前的 Evidence 验收条件

Evidence 设计只有在以下制品于下一阶段物化并可独立复核后，才满足 ADR 0002 的实现入口：

1. 两个 profile 的义务生成清单和 ID 对四个基准全部可确定重建；
2. 每个基准至少有一份正确候选、两个错误候选和一个 `unknown` 路径的预期 Evidence；
3. single-row、row-pair、missing-key、group 与 paired-input 见证均有正向和篡改负例；
4. 独立原型能够发现遗漏义务、错误状态、反例不可重放、trust 洗白、artifact 篡改和错误 conclusion；
5. 至少一种 `proved` support 可以被独立重演，不能让全部核心证明只剩生产工具自述；
6. 对没有可检查证书的候选后端，支持矩阵准确显示 proof-backend trust 与独立检查能力；
7. Evidence、IR、输入、输出、工具和检查结果的摘要链能够在无网络环境重放；
8. 资源上限和恶意嵌套输入策略在实现技术栈冻结时补齐，并以 `unknown` / `incomplete` 失败关闭。

满足这些条件只允许进入受 ADR 0002 约束的实现阶段，不表示产品已经发布、验证后端已经可信或 Evidence 已达到 v1 稳定兼容。

## 变更要求

修改基准状态映射、必需验证矩阵或实现入口，必须同步 Evidence 主规范、ADR 0002、当前状态和后续版本化语料库。只增加能够暴露既有规则错误的负向用例，不需要提升 Evidence 格式版本。
