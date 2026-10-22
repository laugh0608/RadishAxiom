# Solver bootstrap 启动声明与双端纯接口 v0.1

日期：2026-10-17。用途：落实 [ADR 0030 D2](../adr/0030-solver-bootstrap-ffi-and-build-provenance.md) 已接受的私有启动描述和 F1 Mac/S 纯声明核对接口。读者：bootstrap 实现者、宿主适配器实施者与验收者。本文不定义公共 IR / Evidence、不授予 E0/E4 资格，不包含 OS 适配、原生执行或真实捕获构造。

实施顺序与未来原生边界见[实施方案](solver-bootstrap-ffi-implementation-plan.md)；既有 [bootstrap-control-v0.1](solver-bootstrap-wire-v0.1.md) 的 bytes、消息和绑定布局保持原规则。实现位于 `solver-supervision-core::{bootstrap_start,handshake}`，宿主规划入口位于 `solver-diagnostic-host::bootstrap_start`。

## 启动描述的唯一编码

`StartDescription::parse(bytes, WireLimits)` 首先检查输入长度，再检查 ASCII，然后解析闭合字段；输入最多 4,096 bytes。它只接受单个无空白 ASCII JSON 对象，下表即唯一键顺序。

| 键 | 值与绑定 |
| --- | --- |
| `format` | 字符串 `solver-bootstrap-start-v0.1` |
| `attempt` | 恰 64 位小写 hex；wire attempt 原始 32 bytes |
| `request` | `sha256:` 加恰 64 位小写 hex；完整规范 SolverRequest bytes 的原始摘要 |
| `query_bytes` | uint32 十进制，无符号、无前导零；1..已导出的 `PROCESS_LIMITS.stdin_bytes` |
| `query_digest` | `sha256:` 加恰 64 位小写 hex；实际 SMT bytes 的原始摘要 |
| `policy_bundle` | 同上；版本化策略清单摘要，包含准确 W/S filter bytes、固定 FD map 和外层 setup policy 摘要 |
| `image` | 同上；Mac 声明的已登记最终 OCI image 摘要 |
| `cli_acceptance` | 同上；request 中精确 CLI 接受记录摘要的声明 |
| `configuration` | 同上；固定容器配置 / 角色 / 资源模板摘要的声明 |

不接受转义、BOM、额外空白、重复或未知键、键顺序变化、尾随数据、浮点数、指数、字符串数字、缺字段或扩展版本。摘要前缀也必须为小写 `sha256:`。parser 使用固定字面量和有界整数 / hex 解析，解析后重编码逐字比较；所有拒绝返回字段 / offset、实际长度与上限等相应上下文。它不提供宽松 JSON fallback、版本协商或输入恢复。

`StartFields` 用 `[u8;32]` 保存摘要与 attempt，只有 `StartDescription::new` 的界限检查或严格 parser 能构造描述。`canonical_bytes()` 不插入尾部换行。`validate_query(actual)` 在计算摘要前检查实际长度必须完全相等，再计算原始 bytes 的 SHA-256；不解释文本、不规整换行、不复制完整 query。

描述没有路径、任意命令、argv、环境、原 query 或资源覆盖字段。`WireLimits` 是显式类型化输入；core 没有资源默认值或 IR 依赖。宿主通过唯一 `PROCESS_LIMITS` 导出 `process_wire_limits()` 和 checked 的 `process_handshake_window()`。原 stdin 1 MiB、全局 6 s 与其他既有资源不变；未来 native 只能接收已审阅的构建固定导出，不能从描述设置资源。

## 绑定声明与实际来源

`description.binding(declared_nonce)` 将 attempt、request、policy_bundle、image 和 nonce 映射到现有 `BootstrapBinding`，不改 wire bytes。READY 的 `configuration_digest` 必须等于描述配置摘要。配置规范化必须排除描述本身、attempt、nonce 和本摘要字段；该字段本身不能检查其输入是否形成自引用，真实适配器必须核对固定模板生成入口。

最终 image 摘要由 Mac 在真实构建后独立登记，不能预嵌进同一 image 来声称自包含相等。S 回显 request、image、CLI 接受记录或配置摘要，始终只是对外部声明的传输匹配。F1 没有检查 E0 记录内容、E4 资格、镜像来源、随机源、内核身份或真实时钟的能力。

`StartDescription::scope()` 为 `external-declarations-only`。握手与宿主规划对象的 scope 为 `external-declaration-check-and-plan`。`StartMaterialDeclarations`、`ExpectedReadyDeclaration` 和 `LocalReadyDeclaration` 都显式命名为声明；没有从 `SimulationIdentity`、`SyntheticCgroupObservation` 或 `SimulationCompletion` 到执行能力的转换。手动复制字段也只构造新的外部声明，不能恢复来源。

## Mac 独立状态

`MacHandshake::new(description, create_start, declared_clock_error_ns, expected_ready, window)` 只保存 Mac 时间域与已声明的期望 boot / namespace 身份。`MacInstant` 与 `LinuxInstant` 是互不兼容的类型；构造函数名 `declared_ns` 明示时间仍为外部输入。

1. checked 计算 `DM = M0 + window`；零 window 或溢出拒绝。
2. `receive_ready(Mr, frame)` 只接受一次 READY，检查 Mac 时钟不倒退、`Mr < DM`、描述绑定与期望 boot / namespace / configuration。
3. 检查 `Lr < preparation_deadline` 且 `preparation_deadline - Lr <= window`。这只是 Linux 声明内部的界限核对，不认证其 entry。
4. checked 计算 `remaining = DM - Mr - δ` 并要求严格大于零，再计算 `DL = Lr + remaining`。`DL > preparation_deadline` 拒绝，不截断、不续期、不比较两端绝对时钟。
5. 返回现有 `BootstrapFrame::Arm`，携带 READY 的 nonce 和描述 query 长度 / 摘要。再次 READY、错类型或任一失败永久保留首错。

Mac 接收第一条 READY 才取得声明的 nonce。F1 不将其称为已认证挑战；未来 Mac OS 适配器须独立固定来源与 runtime/container 身份。`tick` 只核对声明的单调时间和 DM；本接口不声称在 DM 前确认了实际退出或删除。

## S 独立状态

`SupervisorHandshake::new(description, entry, local_ready, window)` 没有 Mac 时刻、DM、δ 或本地 `make_arm`。它 checked 计算本地 `prep_deadline = entry + window`，核对本地配置声明等于描述，然后保存固定绑定 / nonce。

| 调用 | 纯核对与输出 |
| --- | --- |
| `ready(nowL)` | 要求准备阶段且 `entry <= nowL < prep_deadline`；记录一次 Lr，返回现有 READY frame |
| `receive_arm(nowL, frame)` | 要求 READY 后首次 ARM；核对全部 binding（含 nonce）、query header；要求 `nowL < DL <= prep_deadline`；保留原 DL，返回 `DeadlinePlan` |
| `query_complete(nowL, binding, actual)` | 要求已接受 ARM，仍在原 DL 内；再次核对 binding、实际长度 / 摘要；返回 `QueryCheckedPlan` |
| `tick(nowL)` | 核对该端时钟不倒退且在当前准备期限 / DL 内 |

`DeadlinePlan` 仅表明 ARM 头和声明时间通过检查，不能替代 query 完整接收。`QueryCheckedPlan` 仅表明本次实际传入 bytes 匹配声明；它不是 clone 能力、正常 P4 response 资格或 authenticated capture。S 可核对独立收到的 ARM，不要求它预先在本地生成相同 offer。

每次阶段调用先检查该端时钟，`now == deadline` 即失败；重放、错绑定 / nonce / 配置、错误 query、错误消息 / 阶段、超期、溢出或倒退都永久毒化对象。后续调用只返回首个错误，没有重试或恢复状态。构造时失败直接返回错误，不产生对象。

这套纯接口不访问 OS，也不能判断一次 hash 或消息处理期间真实时间是否越过期限。未来 adapter 必须在实际有界循环和操作前后读取各自时钟、保留真实错误，并按已接受的本地 deadline 机制停止；调用方传入的时刻本身不是计时事实。

## 宿主 strict 规划入口

`StartupDeclarationPlan::from_request_bytes` 接受原始 request bytes、既有语义输入 / profile / 预算、独立 `StartMaterialDeclarations` 与实际 query bytes。入口先调用 `check_solver_request` 完整重建请求，限定本切片 `Cvc5Query0_3ModelV0_1` / `linux-arm64`；再绑定 request bytes、query bytes 和 request 的工具接受记录摘要，最后核对实际 query。不能把另一个 request、接受记录身份或实际 query 偷换进描述。

宿主对象保留重建后的 immutable request 和描述，不接收 `SimulationIdentity`，不创建 E0 接受记录，也没有调用方布尔值开启执行。未来真实适配器在创建之前仍须分别取得精确 E0 接受、E4 资格、工具 / runtime / policy / image / 配置来源；当前声明规划成功不能替代这些门禁。

## 有限验证与兼容性

精准测试覆盖固定编码正例、每个截断点、字段损坏 / 重排、重复 / 未知键、转义 / BOM / 非 ASCII、4096 / 4097 bytes、整数和 query N / N+1、实际 query 长度 / 摘要、严格 request / 工具身份替换，以及原容量 AX-B01 wrong-add 的 962,642-byte query。READY / ARM 通过现有 wire codec 往返；没有新增 wire 格式。

分离的 Mac/S 在与旧 E3 同样的 2,700 组单位速率、无暂停时间矩阵中与独立毫秒公式比较，结果为 891 接受、1,809 拒绝，并与既有模拟计数比较。矩阵包括 Linux 时钟巨大 offset、entry / setup、双向消息延迟与 δ；另有期限相等、超期、overflow / rollback、超长 READY 准备窗口、DL 不截断、重放 / 错 nonce、ARM 与实际 query 分离测试。编译失败文档例检查跨时钟类型和 simulation 声明混用的拒绝。

这些是纯组件动态 / 编译期检查，不是形式证明、真实 OS 行为、随机源、E0/E4 资格或 solver 验收。F1 未提供原生 adapter、FFI、镜像、探针、系统配置或真实捕获入口。
