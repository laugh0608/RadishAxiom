# Bootstrap 内部传输 v0.1

日期：2026-10-17。用途：闭合 [ADR 0029](../adr/0029-solver-linux-supervision-and-capabilities.md)接受的内部 `bootstrap-control-v0.1` 帧格式与纯组件边界。读者：未来 bootstrap 实现者、模拟组件维护者与静态审阅者。本文不定义公共观察 / Evidence schema，不提供真实传输适配器、可执行程序或运行资格。

纯实现为 `crates/solver-supervision-core/src/wire.rs`；`crates/solver-diagnostic-host/src/e3_wire.rs` 保留原构造器与资源常量包装，旧测试为 host 的 `tests/e3_wire.rs`。它仅解释字节；解码成功不认证消息来源、挑战随机性、内核事实、时间可信性或容器身份，不产生 Qualified / Accepted 能力。离线调用必须保留独立的 simulation 包装，不能把此模块的普通帧类型转换成真实 capture 身份。[监督设计](solver-linux-supervision-design.md)与[syscall 策略](solver-linux-syscall-policy.md)的 E0 / E4 / E5 门禁继续生效。

## 承载与方向

Mac 控制输入承载 ARM、query chunk 与 query end；S 的封套输出承载 READY、子进程两流、退出与终态。W 只看到解封后的原 query bytes；W 的原 stdout / stderr bytes 原样成为对应 chunk 正文。S 的封套输出整体不能直接交给 P4。

它与 Docker Engine 八字节 multiplex header 是两个格式。Docker CLI 已分离的 stdout 不能再次经过 Engine 解码，也不能通过头部嗅探自动选择格式。只有显式选定的 bootstrap 解码器接收本格式；解出的 stdout / stderr 不解释 UTF-8、不去 BOM、不规整换行、不拼入控制诊断。

方向值 `1=MacToSupervisor`、`2=SupervisorToMac`。每方向 sequence 独立从 0 起，严格连续递增；不允许重放、跳号或计数溢出。v0.1 不协商版本，不接受未知 kind、扩展正文、非零 reserved、其他方向值或其他 major / minor；升级必须引入明确的新版本和兼容性审阅。

## 固定头

头部恰为 24 bytes。下表 offset 从帧起点计算，范围为半开区间；所有整数均无符号、大端序，时间均为整数纳秒。

| offset | bytes | 字段与唯一合法编码 |
| --- | --- | --- |
| 0 | 4 | magic：ASCII `RAXB`，即 `52 41 58 42` 十六进制 |
| 4 | 1 | major：`0` |
| 5 | 1 | minor：`1` |
| 6 | 1 | direction：`1` 或 `2`，且须等于预先选定的方向 |
| 7 | 1 | kind：下表的闭合集合 |
| 8 | 4 | reserved：全零 |
| 12 | 8 | sequence：u64BE |
| 20 | 4 | payload_len：u32BE，不含本头，最大 65,536 |
| 24 | payload_len | payload：160-byte binding 加类型化正文 |

没有可选字段、字符串、TLV、压缩、路径、argv、envp 或任意执行请求。未知字段不能跳过后继续。

## 每帧 binding

每帧 payload 前 160 bytes 完全相同布局。下表 offset 从 payload 起点计算，亦即帧 offset 24 加该值。

| offset | bytes | 字段 |
| --- | --- | --- |
| 0 | 32 | attempt raw digest |
| 32 | 32 | request raw digest |
| 64 | 32 | policy raw digest |
| 96 | 32 | image raw digest |
| 128 | 32 | nonce |

四个 digest 是 SHA-256 的原始 32 bytes，不是十六进制文本、`sha256:` 字符串或另一轮摘要。nonce 恰 32 bytes；本次离线模型使用合成值，不能据长度判断它来自真实随机源。wire 层保留这些字节，但不替调用者认证来源。实际候选消费必须使用 `BootstrapDecoder::new_bound(direction, expected_binding)` 固定同一 attempt / request / policy / image 与本次 READY nonce；它在收齐前 160 bytes 后、复制正文前逐项比较，任一变化返回 Binding 并永久毒化。预期值仍须由可信的调用流程选定，不能由当前未认证消息自行决定；监督状态机继续负责 READY 挑战接纳与跨阶段绑定。错误绑定不允许启动、续期或发布。普通 `new(direction)` 仅用于语法 fixture，不建立尝试绑定。

## kind 与闭合正文

正文 offset 从 binding 之后计算，亦即 payload offset 160、帧 offset 184。

| kind | 方向 | 名称 | 正文长度与字段 |
| --- | --- | --- | --- |
| 1 | 2 | READY | 恰 112 bytes，见下表 |
| 2 | 1 | ARM | 恰 44 bytes，见下表 |
| 3 | 1 | QUERY_CHUNK | 1–65,376 bytes 原 query bytes |
| 4 | 1 | QUERY_END | 0 bytes |
| 5 | 2 | STDOUT_CHUNK | 1–65,376 bytes 原 stdout bytes |
| 6 | 2 | STDOUT_EOF | 0 bytes |
| 7 | 2 | STDERR_CHUNK | 1–65,376 bytes 原 stderr bytes |
| 8 | 2 | STDERR_EOF | 0 bytes |
| 9 | 2 | CHILD_EXIT | 恰 2 bytes：`tag`、`value` |
| 10 | 2 | FINAL | 恰 2 bytes：仅 `01 01` |
| 11 | 2 | FAILURE | 恰 1 byte：闭合原因值 |

READY 正文：

| offset | bytes | 字段 |
| --- | --- | --- |
| 0 | 8 | `linux_ready_ns`，u64BE |
| 8 | 8 | `preparation_deadline_ns`，u64BE，严格大于 linux_ready_ns |
| 16 | 32 | `boot_digest` |
| 48 | 32 | `namespace_digest` |
| 80 | 32 | `configuration_digest` |

ARM 正文：

| offset | bytes | 字段 |
| --- | --- | --- |
| 0 | 8 | `deadline_ns`，u64BE，Linux 绝对时刻 |
| 8 | 4 | `query_len`，u32BE，最大 1,048,576 |
| 12 | 32 | `query_digest`，原 query bytes 的 SHA-256 raw digest |

wire 不计算 Mac / Linux 时钟差，不截断到毫秒，不为 δ 提供默认值。ARM 的期限、query 长度 / 摘要、READY 身份与配置是否匹配，以及 ARM 是否已经消费，由监督状态机负责。

CHILD_EXIT 的 `tag=0` 表示正常退出，`value` 为完整 u8 退出码；`tag=1` 表示信号退出，`value` 仅允许 1–64。其他 tag / 信号值拒绝，不把退出状态改写成零，不把信号退出推断成 OOM。

FINAL 的两个 byte 分别表示 `child_reaped=true` 与 `only_supervisor=true`；只有 `01 01` 合法，不允许 false 或非规范布尔值。它是绑定的本地声明；真实事实须由监督器取得，正常完成还需要双 EOF、子进程状态、最终 cgroup 事实及外层 runtime / 清理确认。wire 类型本身不能证明这些前驱。

FAILURE 原因值：`1=Protocol`、`2=Deadline`、`3=ControlLost`、`4=OutputLimit`、`5=Policy`、`6=Resource`、`7=Loader`、`8=Child`、`9=Observation`。其他值拒绝。它只区分停止类别，不能替代保留真实错误的事实记录；不提供任意诊断字符串通道。

## 资源与状态约束

| 项目 | 上限 / 行为 |
| --- | --- |
| 单 payload | 65,536 bytes，含 binding |
| 单 chunk 原数据 | 65,376 bytes；零长度 chunk 不规范 |
| query 原数据累计 | 1,048,576 bytes |
| stdout 原数据累计 | 4,194,304 bytes |
| stderr 原数据累计 | 65,536 bytes |
| 双向控制累计 | 65,536 bytes；当前纯实现保守分配为每方向 32,768 |
| pending 写数据 | 设计上限 131,072；实现只留单帧，实际上限 65,560 |

控制预算包含所有帧头、所有 binding，以及非 chunk 正文；chunk 原数据仅进入对应数据流预算。固定方向配额是此实现的额外收紧，不允许一方向借用另一方向剩余额度。两方向因此合计不超过 65,536。用极小 chunk 消耗控制预算会提前失败；禁止通过无界小帧规避总量约束。按最大 chunk 分帧仍可承载原 query / 两流限额。

所有 declared length、固定正文长度、checked 累加、方向、sequence、单例与 EOF 检查在分配 / 复制 payload 前执行。超限不是截断为正常完整流。READY、ARM、QUERY_END、各 EOF、CHILD_EXIT、FINAL、FAILURE 都是单例；重复拒绝。各流 EOF 后该流新 chunk 拒绝。FINAL / FAILURE 是互斥终态；任一终态后的帧拒绝。

同一方向内的其他跨消息时序由监督状态机检查，包括 READY → ARM → 完整 query → 单次创建、期限不续期、首次 exec 通知只消费一次、双 EOF / reap / 最终事实前不得 FINAL。wire 层不是第二套监督状态机。

## 增量接口与背压

`BootstrapDecoder::poll(&[u8])` 接受部分头、部分载荷或拼接输入，返回 `DecodeStep { consumed, frame }`。每次最多交付一帧；调用者保留未消费尾部，下轮显式再次 poll。解码器不接收整个大输入并建立无界 `Vec<Frame>`。未完成帧最多保留 24-byte 头加 65,536-byte payload。交付 chunk 时保留原字节；拷贝的短暂峰值也小于 131,072 bytes，不将完整 query / 两流积累在解码器里。

`BootstrapEncoder` 按同一 canonical 规则产生单帧字节，供编码和离线 fixture 使用。实际候选写循环须经过 `PendingFrameBuffer`：`push` 在当前帧未排空时返回 `Backpressure`，不会复制新帧、消耗 sequence 或排队；`remaining` 返回尚未写出的切片，`consume(n)` 只消费已确认写出的 n bytes。越界 consume 保留首个错误并永久停止写入；一个单帧排空后才能编码下一个。调用者不能在其外另建无界队列，也不能因下游不读取而阻塞监督期限检查。

decoder 遇到任何协议错误后毒化；其后的 poll / EOF 只返回 Stopped，不尝试重同步、头部扫描或恢复。encoder 的编码错误同样停止后续编码；写缓冲只有 Backpressure 是可恢复的正常流控，且不会改变 encoder 状态。写缓冲的尺寸溢出、超限、编码错误或 consume 越界均永久毒化，丢弃尚未发送的数据，此后的 push / consume 只返回 Stopped，禁止在失去写入记账后继续尝试。

`QUERY_END` 仅表示 query 数据结束，未来适配器只关闭 W stdin；它不关闭控制连接。物理控制 EOF 在显式 FINAL / FAILURE 之前一律为 ControlEof，部分帧 EOF 为 Truncated，两者均毒化。显式终态后 `end_of_input()` 只允许字节层干净结束，不把终态声明或连接关闭转换成真实成功；外层监督仍检查 deadline 与回收事实。Mac→S 方向不存在终态帧，因此 QUERY_END 后的物理 EOF 仍是失联。

## 验证边界

精准测试覆盖五项 binding 篡改 / 跨帧切换、绑定模式逐切分与不认证来源边界、所有类型的每个切分位置、逐字节输入、拼接输入只交付一帧、原始非 UTF-8 字节、头 / 字段腐败、未知版本 / kind、超大 declared length、数据量 N / N+1、方向控制预算、重复 / 跳号 / 重放、EOF 后数据、缺终态 / 截断与单帧写背压。所有材料均为合成 bytes。

这些结果只表示纯组件的动态测试与静态范围检查，不能升级为 Linux seccomp / timerfd / cgroup 的内核验证、真实 solver 适配或宿主资格。真实实现的部分写入、系统错误、绝对 deadline 与独立回收仍须在授权后的专用 Linux bootstrap 与 E4 入口中验证。
