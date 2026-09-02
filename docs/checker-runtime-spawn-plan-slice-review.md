# Checker runtime immutable spawn plan 切片审阅单

状态：qualification / invocation 共用的 immutable spawn plan 与外层排他状态机已实现并通过本地门禁
审阅日期：2026-09-02

## 目标与结论

本切片承接[两层业务 manifest parser 切片](checker-runtime-manifest-parser-slice-review.md)，实现 [ADR 0011](adr/0011-checker-runtime-launcher-installation-and-activation.md) 与 [ADR 0012](adr/0012-product-checker-runtime-host-and-persistence-interface.md) 已冻结的单一 spawn 配置和 result-or-failure 类型边界。实现只使用调用方提供的合成 executable、只读 bundle、空工作目录和进程观察；不创建子进程，也不执行真实 checker。

`LauncherPolicy` parser 现在逐字段闭合 invocation：只接受两个精确 argument token、空且不继承的 environment、empty-then-EOF stdin、只读 canonical bundle、isolated empty working directory、禁止网络 / fallback、同一 exact slot retry，以及每次 spawn 前后 executable identity 复核。只满足对象 shape 或重算 policy digest，不能绕过这些语义检查。

`ExecutionProfileContract` 先把 canonical `contracts/execution-profiles-v0.1/manifest.jcs` 的原始 SHA-256 绑定 policy，再严格读取唯一 `keyed-finite-table-independent-check-v0.1` profile 和 `keyed-finite-table-independent-check-process-v0.1` 外层 limit set。plan 因而固定：

- executable 只来自与 registration artifact 长度 / SHA-256 和完整 target 一致的 observed identity；
- argv 恰好是 `check` 与一个 `--bundle-root=<observed canonical path>`，不接受 PATH、相邻目录或额外参数；
- environment 集合为空，stdin 为 empty-then-EOF，bundle observation 为 read-only，working directory observation 为 isolated empty；
- stdout 为 1,048,576 bytes、stderr 为 65,536 bytes、wall-clock 为 6,000 ms、working memory 为 134,217,728 bytes；
- qualification 只接受 `registered-inactive`，product invocation 只接受 `active`，两者共享同一个不可变 plan 类型。

## 排他状态机与失败关闭

`ProcessTerminationObservation` 用互斥 enum 表达 spawn failure、timeout、working-memory termination、signal 或单一 exited 观察，不能同时声明互相冲突的终止状态。exited 观察携带 bounded stdout / stderr、wall-clock 与 peak working-memory；stream 要么完整，要么明确 cap exceeded，不使用“部分输出但仍可消费”的布尔组合。

`consume_process_observation` 的唯一返回类型 `CheckerProcessOutcome` 只能是：

- `Result(ConsumedIndependentResult)`：current registration 未漂移、postflight executable 与 plan 的 path / filesystem object / target / length / digest 完全相同、进程零退出、四项外层上限内、stderr 是 bounded UTF-8，且 stdout 通过既有单一 Rust Independent Check result consumer；或
- `Failure(OuterInvocationFailure)`：上述任一前置、进程、输出、资源或身份条件失败。

因此 outer failure 与四态结果不能同时存在。spawn、signal、timeout、memory termination、非零退出、stdout / stderr 超限、stderr 非 UTF-8 或非 canonical result 统一停在 process failure；registration、executable、checker / request / Evidence / TCB 身份漂移停在 identity failure。failure 只保存稳定 code 和分类，不把诊断、路径、环境、PID 或用户数据写入公共结果。

## 验证与停止线

测试在自动清理的合成临时根中创建占位 executable、bundle 和 empty working directory，但 executable observation 只模拟已由未来 native adapter 获取的登记身份；测试从未把占位文件作为 checker 执行。正例证明单一 canonical stdout 只能形成一个 `ConsumedIndependentResult`；负例覆盖 profile raw identity、重绑摘要后的 limit 弱化、registration status、executable identity、postflight unavailable / drift、spawn / signal / timeout / memory、非零退出、stream cap、stderr UTF-8、wall / memory 观察超限、非 canonical stdout 和 request identity 漂移。

本切片没有新增依赖，没有修改 launcher policy、execution profile、registration、installation receipt、qualification、attempt 或 Independent Check 公共格式，也没有读取真实产品根、真实 slot、Release asset 或远程状态。完整 Cargo、Python、生成契约、schema、仓库和差异门禁结果统一记录在[当前状态](status/current.md)。

`ReadonlyBundleObservation`、`IsolatedWorkingDirectoryObservation` 与 filesystem object identity 是未来可信 native adapter 的输入契约，不是当前 core 对 mount、目录内容或 OS metadata 的自行证明。`NativeIsolationStatus` 被固定为 `RequiredNotProven`：plan 中的 network prohibition、wall deadline 与 working-memory hard limit 只是必须施加的配置，不能冒充 Darwin 已实际隔离、杀死或计量进程。

[Darwin process isolation 原语审阅](checker-runtime-darwin-process-isolation-review.md)随后确认 exact spawn、descriptor working directory、stream / deadline supervisor、process-group kill、direct-child reap 与 executable / rusage observation 可由公开 API 形成；但 App Sandbox 会引入签名 / entitlement / 产品打包边界，`128 MiB` hard working-memory limit 在当前普通进程中没有可用 enforcement，process group 与 path-based spawn 也不能闭合不可逃逸 process tree 和 executable lookup TOCTOU。因此 `RequiredNotProven` 保持不变。新增 process FFI / 平台 crate、强隔离架构或弱化 public hard limit 都必须先分别决策和授权；真实 checker 执行、产品绝对根、qualification 和 activation 继续分别验证、分别授权。
