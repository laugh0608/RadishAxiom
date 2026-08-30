# ADR 0011：独立 checker runtime launcher、安装与激活边界

日期：2026-08-30

状态：Accepted

用途：冻结首个 macOS arm64 checker runtime 的目标选择、安装事务、正式 runtime companion、产品调用与激活失败边界。

读者：runtime / launcher 实现者、安装与发布维护者、独立 checker 维护者、供应链审阅者和 Checker Runtime Payload Registration 消费者。

不包含：本次下载或安装 payload、实现产品 launcher、运行用户 bundle、把任何记录推进为 `active`、修改 Independent Check Contract / Execution Profile Contract 公共格式、分配产品版本、push、发布或部署。

## 背景

[ADR 0008](0008-independent-checker-isolation-and-artifact-exchange.md)已经冻结 checker 一次请求一个离线独立进程、只读 bundle、canonical stdout result 与外层进程失败的隔离原则；[Execution Profile Contract v0.1](../../contracts/execution-profiles-v0.1/README.md)固定了唯一 CLI 参数、空环境、只读 bundle、外层 stream / wall-clock / memory 限制和结果形成停止线。[ADR 0010](0010-checker-runtime-payload-durable-registration.md)又把 payload 状态机固定为 `candidate -> distribution accepted -> durable published -> registered inactive -> active`，并要求 active 前另行完成精确 OS / architecture / variant 隔离、安装协调、runtime companion 与激活授权。

本 ADR 接受时，当前 `checker.source = sha256:401158c3c304f45faebebe879edf064512998423d7b08aec486f4be0012e3999` 的 `go0.1-dev` / `darwin-arm64-v8.0` distribution 已由 immutable Release 持久发布并登记为 `registered-inactive`，但没有安装、没有产品 launcher，也没有可选择的 active runtime。Release、asset、artifact、acceptance 与当前登记的精确事实继续只以 [Checker Runtime Payload Registration v0.1](../../contracts/checker-runtime-payloads-v0.1/README.md) 和[当前状态](../status/current.md)为准，不复制为本 ADR 的长期事实。

项目既有文字中的“正式 runtime companion”专指实际 checker binary 以真实 source / artifact / toolchain / runtime TCB 身份形成的 `axiom-independent-check-result` `0.1` canonical companion。它不是安装 receipt、launcher 配置或另一种结果格式。本 ADR 不创建第二套 companion。

## 决策

### 目标键与硬隔离

launcher 只使用闭合目标键：

```text
(goos, goarch, variant, executable-format)
```

首个且唯一已登记目标为：

```text
(darwin, arm64, v8.0, macho-64-arm64)
```

四项都必须精确匹配，不定义“最近版本”、兼容架构、同族 OS、文件扩展名猜测或降级顺序：

- `goos` 与 `goarch` 来自 launcher 的可信宿主适配层和当前原生进程身份，不能来自环境变量、命令行、bundle、下载文件名或 `uname` 自由文本；在翻译进程中观察到 `amd64` 时不能越权选择 `arm64` payload。
- `variant` 是登记表中的闭合构建兼容键，不是用户输入或任意 CPU marketing name。首个适配层只把原生 `darwin/arm64` 映射到已冻结的 `v8.0` 基线；未知值、新 variant 或未来兼容关系必须先扩展机器策略与原生测试，不能尝试后回退。
- `executable-format` 必须从安装字节重新检查为 64-bit arm64 Mach-O，不能仅相信登记、manifest、路径后缀或操作系统愿意启动该文件。
- launcher 只从主仓当前登记集合选择 `registration.status = active` 的记录，并要求目标键、checker source、实现版本、toolchain、binary 长度 / SHA-256、distribution 长度 / SHA-256 和安装 receipt 全部一致。匹配结果不是恰好一项时失败关闭。
- `registered-inactive` 即使字节已经存在于安装根，也只能由安装协调器的资格复核入口执行锁定测试 bundle；产品请求路径必须拒绝选择。

禁止搜索 `PATH`、系统 Go 安装、相邻目录、当前工作目录、用户指定 executable、旧 cache、Actions artifact、“latest” URL 或其他平台 payload。provider 不可用、active 记录缺失或目标不匹配时直接报告 runtime unavailable，不联网补齐或切换实现。

### 安装事务与本地布局

安装是 `registered-inactive` 之后、active 之前的单独授权动作。安装协调器可以取得精确 immutable Release asset，但 checker 进程本身保持离线且永不下载。首版安装遵循以下事务：

1. 在产品管理的用户级私有数据根内取得每目标单写者锁；不写系统目录、不修改 `PATH`、不替换系统 Go，也不执行安装脚本。
2. 只按登记的 repository、release ID、tag、asset ID、asset name、长度和 SHA-256 取得 distribution。重定向后的最终对象仍须逐字节满足登记身份；禁止 name-only、latest 或邻接 cache fallback。
3. 在同一文件系统的新 staging 目录中严格解析外层 distribution 与内层 candidate。只接受登记的闭合 member、USTAR header、相对路径和模式，拒绝绝对路径、`..`、空组件、硬链接、符号链接、device、FIFO、socket、PAX / xattr、额外或尾随字节。
4. 重新核对 distribution acceptance / manifest、candidate manifest、build provenance、payload acceptance、法律材料、checker source / version / toolchain / target，以及 binary 原始长度与 SHA-256。安装 verifier 的成功不能替代这些已有 acceptance。
5. 最终 slot 由 `target + distribution SHA-256` 唯一确定；binary 的 slot 内相对路径固定为 `payload/radishaxiom-independent-checker-go`。文件为普通文件，binary 只允许 `0755`，其余保存材料只允许 `0644`，目录只允许 `0755`；任何 setuid、setgid、sticky、链接或越出管理根的 realpath 都拒绝。
6. 在 staging 内形成 canonical `radishaxiom-checker-runtime-installation-receipt` `0.1`，至少绑定登记 record ID / digest、provider release / asset、distribution、checker source / version / toolchain、binary、完整目标键、slot 相对身份、安装 verifier 身份、安装时间和 `installed-inactive` 状态。receipt 使用域 `radishaxiom.checker-runtime-installation-receipt.v0.1` 形成 document digest，不记录绝对用户路径、环境值或凭据。
7. 全部文件与 receipt 写入完成并重新读取通过后，才以同文件系统原子 rename 发布 immutable slot。已有同名 slot 只能在所有字节与 receipt 完全一致时复用；不得覆盖、原地修补或把失败 staging 当成完成安装。

安装失败只清理由本次事务创建且仍持锁的 staging；既有完整 slot 与其他进程正在使用的 executable 不受影响。崩溃遗留 staging 在下次持锁恢复时按未完成状态处理，不能从目录存在推断成功。卸载、垃圾回收与已撤销 slot 的法证保留留给后续产品生命周期决策，不由 launcher 请求路径顺手删除。

### 安装资格复核与正式 runtime companion

安装完成仍只得到 `installed-inactive`，不能直接进入产品选择。安装协调器必须通过与产品调用相同的 executable resolution、目标门禁、空环境、只读 bundle、参数、stream cap、hard wall 和 memory 边界，对当前 payload acceptance 已绑定的三条路径各执行一次：

| 场景 | 预期 result | 资格要求 |
| --- | --- | --- |
| `ax-b01-correct` | `accepted-with-trust` | canonical stdout 原始 SHA-256 与 payload acceptance 记录一致 |
| `chk-digest-01` | `rejected` | canonical stdout 原始 SHA-256 与 payload acceptance 记录一致 |
| `chk-resource-01` | `incomplete` | canonical stdout 原始 SHA-256 与 payload acceptance 记录一致 |

每份 stdout 都必须由 Independent Check Contract v0.1 严格 parser 接受，并再次核对真实 `checker.source`、实现版本、`go1.26.7`、`checker.artifact`、四类 runtime TCB、request / Evidence 身份、四态、refs 和 result document digest。只有从已安装 exact binary 在目标 launcher 边界下产生并通过这些检查的 `axiom-independent-check-result`，才称为正式 runtime companion。

三种预期四态不是“都成功”的同义词：资格复核验证的是 launcher 忠实运行、保存并校验 checker 的真实决定。`rejected` 与 `incomplete` 不得被重写为 `accepted`，`accepted-with-trust` 也不升级为无 trust 的 `accepted`。三条 qualification 只覆盖既有锁定边界，不证明任意用户 bundle、六平台等价、kernel rule、certificate 或产品正确。

三条结果通过后，协调器在 slot 外的产品管理证据区形成新的 canonical `radishaxiom-checker-runtime-qualification-record` `0.1`，以域 `radishaxiom.checker-runtime-qualification-record.v0.1` 绑定 installation receipt digest、目标、实际 binary、launcher policy / execution profile，以及三份 companion 的场景、raw / document digest。失败 attempt 保留为有界观察，不能原地改成成功；成功 qualification record 只允许 exclusive create。slot 内 installation receipt 不因资格复核而修改，companion 本身也继续遵循现有公共格式，不增加安装或 launcher 私有字段。

### 激活与每次调用

`registered-inactive -> active` 仍是独立状态转换并需要明确授权。激活前必须同时满足：

1. 当前登记记录及其 durable fetch / readback 仍有效且未 revoked；
2. launcher policy 已由目标产品实现并通过 native `darwin/arm64` 测试；
3. 对应 immutable slot 和完整 installation receipt 可重读，目标、distribution 与 binary 身份未漂移；
4. qualification record 与三条 companion 全部满足上述精确要求；
5. 主仓状态转换和产品可选择性属于本次授权的精确范围。

主仓每个目标最多登记一个 active payload，因此 target 与 distribution digest 足以确定唯一 slot，不建立浮动 `current` / `latest` symlink 或可变 executable pointer。每次产品调用仍须在 spawn 前重新核对 active 记录、receipt、slot realpath、普通文件 / mode、binary 长度 / SHA-256 与目标键；spawn 后对 executable 再核对，防止调用期间替换。任何漂移都使本次 invocation 失败并阻止后续选择，不能因 checker 内部也会自校验而省略 launcher 外层检查。

调用形状继续只有：

```text
radishaxiom-independent-checker-go
check
--bundle-root=<caller-mounted-readonly-canonical-realpath>
```

stdin 为空，环境不继承，工作目录为空隔离目录，bundle root 是调用方解析且只读的 canonical realpath；stdout、stderr、`6,000 ms` hard wall、`128 MiB` outer memory 与其余边界完整引用既有 Execution Profile Contract v0.1，不在本 ADR 复制第二套数值来源。launcher 不解析 stderr 推断 checker 结果，也不向 checker 暴露 provider 凭据、安装根、网络、生产 cache 或其他工具路径。

### 失败分层

失败按发生位置保留，不能互相洗白：

| 边界 | 结果 |
| --- | --- |
| 无 active 记录、目标不匹配、slot / receipt / binary 身份失败 | product runtime unavailable；不启动 checker，不形成四态结果 |
| fetch、解包、验收或 atomic publish 失败 | installation failed；不形成完整 receipt，不改变 active 状态 |
| qualification 任一输出、身份、四态或摘要不匹配 | installation remains inactive；保存失败观察，不推进 active |
| spawn 失败、外层 timeout / memory kill、crash、signal、非零退出、stdout 截断 / 超限 / 非 canonical 或 conflicting output | process failure；不把部分 stdout 解释为 `incomplete` 或其他四态 |
| stdout 是完整 canonical result，但 result identity 与 active registration、request 或实际 binary 不一致 | identity failure；该 result 不可消费 |
| spawn 后 executable 身份漂移或记录 revoked | invocation failure，并停止该 slot 的后续选择；不自动回退旧 payload |

若 canonical request 的 raw / document identity 已经形成，外层可按既有 `axiom-checker-invocation-failure` `0.1` 保存 `result = not-produced`；该 envelope 只能绑定 request 与未产出事实，实际 exit / signal / timeout / truncation 观察另存为有界产品运行记录。request 尚未形成时不能用合成摘要补造 envelope。一次 invocation 只能消费一个严格通过的 result 或形成 failure，不能同时接受结果再隐藏外层失败。

launcher 不自动重试到其他 payload、平台、version 或实现。对同一 exact slot 的人工重试形成新 attempt 并保留旧失败；后续成功不覆盖前一次观察。

### 撤销与 replacement

record 进入 `revoked` 后，launcher 即使仍能读取 slot 也不得执行。正在运行的进程是否立即终止属于撤销响应策略，必须在具体产品威胁模型中单独冻结；默认最低要求是阻止所有新 invocation 并保留现有法证记录。

replacement 继续遵循 ADR 0010：新 source / version / target、immutable Release、登记 record 和 content-addressed slot，不修改旧 slot。没有自动 rollback；重新选择任何旧 payload 都必须证明其记录未 revoked、重新满足当前策略并取得新的明确授权。

## 后果

收益：

- 已发布字节、主仓登记、本地安装、正式 companion 与产品可选择性成为连续但不可跳过的证据链；
- OS / architecture / variant 不再依赖 PATH、文件名或“兼容猜测”，翻译进程和未知平台失败关闭；
- 安装中断不会污染完整 slot，replacement 不会覆盖正在运行的 binary；
- runtime companion 沿用现有 Independent Check Contract，不增加另一套结果语义；
- launcher、checker 内部身份检查和 provider acceptance 互相补强但职责可区分。

代价与风险：

- 产品侧必须实现严格 USTAR / canonical receipt、content-addressed slot、锁与 atomic publish，并原生验证 macOS 文件系统与进程限制行为；
- 每次 invocation 前重算约 4.7 MiB binary 摘要有固定成本，但首版优先选择可审计身份而不是隐式 inode / mtime cache；
- 当前只冻结 `darwin/arm64/v8.0`，不能外推其他 macOS 架构、Linux、Windows 或更高 GOARM64 variant；
- 当前 target 没有表达最低 macOS 版本；资格复核只说明实际验收宿主可运行，产品支持的 OS version 范围仍需在产品版本与原生矩阵中单独冻结。

## 实施顺序与停止线

1. 先将本决策物化为 Checker Runtime Payload Registration 的 canonical launcher policy、schema、负例与 inactive readiness；active count 保持 0。
2. 再实现纯本地、网络隔离的 installer / launcher 验证核心及合成文件系统测试；引入 Rust workspace、依赖或 lockfile 时按当次范围另行审阅和授权。
3. 对精确 immutable asset 的真实下载与安装单独授权；只允许得到 `installed-inactive` 和 qualification evidence。
4. 只有本机目标门禁、三条正式 companion、外层失败矩阵与安装恢复验证全部通过后，才提出精确 `registered-inactive -> active` 计划并另行授权。

本 ADR 本身不安装、不执行 payload，也不授权激活。修改 active-only 选择、精确目标匹配、content-addressed immutable slot、独立安装授权、三条 qualification、现有 companion 格式复用、无 fallback、失败不形成四态或每次调用重验 binary 的原则，必须以新 ADR 替代本决策，并同步 runtime payload 登记契约、当前状态与相关实现。
