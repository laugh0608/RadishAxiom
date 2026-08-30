# ADR 0012：产品侧 checker runtime 宿主与持久化接口

日期：2026-08-30

状态：Accepted

用途：冻结产品侧 checker installer / launcher 的实现宿主、与 `raxc` 的归属、网络能力切分、持久化能力接口，以及 Independent Check result 的生产消费边界。

读者：`raxc`、runtime / launcher、安装与发布、独立 checker、产品打包、供应链和跨平台维护者。

不包含：本次创建 Cargo workspace、安装 Rust 或 crate、生成 `Cargo.lock`、冻结用户可见 CLI、确定产品绝对安装路径、下载或执行 checker payload、真实安装、激活、push、发布或部署。

## 背景

[ADR 0004](0004-raxc-production-implementation-language.md)选择 Rust 2024 edition 与精确 Rust `1.97.1` 作为生产 `raxc` 宿主，但明确没有替独立 checker 或其他产品组件自动选语言。[ADR 0008](0008-independent-checker-isolation-and-artifact-exchange.md)随后把 checker 固定为独立 Go 仓库、独立依赖图和一次请求一个离线进程，禁止生产端 import、链接或复制 checker parser 与语义实现。[ADR 0011](0011-checker-runtime-launcher-installation-and-activation.md)又冻结 active-only 选择、严格安装、qualification、每次 spawn 身份复核和失败不形成 checker 四态的行为边界。

仓库现有 Python 一致性核心已经在合成 USTAR、临时文件系统、companion 元数据和进程观察上闭合 ADR 0011 的主要不变量。它是可执行设计 oracle，不是产品实现：Python 解释器身份、模块搜索路径、宿主环境和宽松标准库默认值不能静默进入产品可信计算基。进入原生实现前还必须回答三个长期问题：

1. launcher 是 `raxc` 生产图的一部分、另一个产品进程，还是 checker 仓库的一部分；
2. 下载、安装验证、持久化、qualification 和产品调用分别拥有哪些能力；
3. 产品怎样严格消费 `axiom-independent-check-result`，而不破坏 checker 的实现独立性或建立第二套结果语义。

## 方案比较

| 方案 | 优点 | 主要代价与风险 | 结论 |
| --- | --- | --- | --- |
| 主仓 Rust 生产图中的内部 runtime 组件 | 与 `raxc` 共用精确生产工具链、构建与产品发布图；原生文件系统 / 进程控制；无需第二个产品运行时 | 必须保持 runtime 与生产语义模块的职责边界；首批依赖仍需审阅 | **采用** |
| 主仓或独立仓库的单独 Rust launcher 产品 | 可形成单独进程和权限封装 | 提前冻结第二个产品制品、CLI、发布与更新协议；复制 codec、配置和打包成本 | 暂不采用 |
| 在 Checker Go 仓库实现或复用 Go parser | 已有严格 result parser 和精确 Go 工具链 | 合并生产与独立实现边界，使 checker 自己参与选择、安装或解释自身结果；同源缺陷和发布耦合不可接受 | 拒绝 |
| 以 Python 一致性核心作为产品 launcher | 已有测试模型，迭代快 | 引入解释器、环境与模块路径可信边界；原生资源 / 进程限制和跨平台分发不稳定 | 仅保留为测试 oracle |
| 首版使用 Swift / macOS 专属组件 | 原生 macOS API 直接 | 把当前单目标验证误写为长期单平台产品结构，并为后续 Linux / Windows 建立第二套实现 | 拒绝 |

launcher 不承担独立复核职责，因此与 `raxc` 共享生产工具链不会削弱 ADR 0008 要求的 checker 隔离；真正必须保持独立的是 checker 的源码、依赖、parser、规则、构建和结论。反过来，单独产品进程只有在权限、更新或威胁模型证明需要时才有价值，不能仅为目录整齐提前增加发布面。

## 决策

### 实现宿主与产品归属

产品侧 checker runtime 选择 **Rust 2024 edition 与精确 Rust `1.97.1` stable 工具链**，位于 RadishAxiom 主仓未来与 `raxc` 相同的 Cargo workspace、依赖治理和产品发布图中。它是生产侧内部 runtime 组件，不是独立 checker 的一部分，也不在本 ADR 中冻结为单独用户可见二进制、daemon、插件或公共 SDK。

这一决定把 ADR 0004 的精确 Rust 基线显式扩展到产品侧 checker runtime，但不改变 ADR 0004 对 `raxc` 的语义要求，也不把 Rust 扩展到 Go checker。未来 workspace 可以按真实实现边界拆 crate；本 ADR 只冻结职责与依赖方向，不为尚未出现的复用创建空 crate、manager、adapter 或 CLI。

生产依赖方向必须保持：

```text
product / raxc orchestration
  -> checker runtime component
       -> production canonical-byte primitives
       -> trusted host and process adapters
       -> versioned runtime store interface
       -> exact checker subprocess protocol

independent checker Go repository
  <- canonical request / readonly bundle
  -> canonical result / process status
```

runtime 组件不得依赖 checker 仓库源码、Go package、生成代码、parser、测试 helper、构建 cache 或本机 checkout。checker 也不得依赖主仓 Rust workspace。

### 机器策略版本迁移

ADR 0011 已将目标选择、安装与 qualification 物化为闭合的 `radishaxiom-checker-runtime-launcher-policy` `0.1`。本 ADR 新增的实现宿主、网络能力、store 和 result consumer 都是必需 member；把它们追加到 `0.1` 会让同一版本出现两种闭合结构。因此当前 canonical launcher policy 升级为 `format_version = 0.2`，document digest 域同步升级为 `radishaxiom.checker-runtime-launcher-policy.v0.2`，schema ID、负例集合和 qualification 对 policy version 的绑定一并更新。

Checker Runtime Payload Registration 集合与现有 payload record 继续保持 `v0.1` 且字节不作追溯修改；它们只把当前 policy 的版本和摘要作为外部 readiness 输入。历史 policy `0.1` 由 Git 保留审计，不允许被 `0.2` parser 接受，也不建立回退。当前没有产品实现、installation receipt、qualification record 或 active runtime，因此这次 pre-implementation 迁移不需要双读期；未来再改变闭合字段或语义仍须升级 policy 版本。

### 六个实际职责边界

首版只建立以下有真实输入、输出和失败边界的职责，不建立泛化插件框架：

1. **Registry input**：从产品提供的 canonical launcher policy 与 registration snapshot 字节形成闭合 typed records，重算域摘要并拒绝未知字段、版本、重复 member、数字、`null` 与非规范字节。仓库相对路径不是产品运行时查找协议。
2. **Host identity**：由受信任的目标平台适配层提供当前原生 `(goos, goarch, variant, executable-format)`；不读取用户参数、bundle、环境变量或下载文件名。适配层失败即 target unavailable。
3. **Installation verifier / publisher**：只接收调用方已经取得的精确 distribution bytes、verified registration、host identity、安装 metadata 和持有中的目标锁；内部没有 HTTP client、URL resolver、provider credential 或自动下载能力。
4. **Runtime store**：通过下述版本化能力接口创建 owned staging、验证并发布 immutable slot、重读 receipt、保存 qualification 和追加失败观察；它不通过目录存在、mtime、inode 或浮动 symlink 推断成功。
5. **Independent result consumer**：以主仓 Rust 对公共 Independent Check Contract v0.1 的严格消费实现解析 stdout，核对 result document digest、checker / request / Evidence / TCB 身份和四态闭合结构；它只验证“结果是否是可消费的 checker 输出”，不重新实现 checker 的义务重建或把结果改写为生产证明。
6. **Spawn boundary**：qualification 与产品 invocation 共享同一种 immutable `SpawnPlan`，其中绑定 exact executable、参数、空环境、空 stdin、隔离工作目录、只读 bundle、stream cap、wall / memory limit 和 spawn 前后身份。两条入口只在允许的 registration state 和持久证据前置上不同。

真实 fetch 属于安装协调层的单独 capability。它只能在独立安装授权后按登记的 immutable provider 身份取得 bytes，再把原始 bytes 与 provider readback metadata 交给网络隔离的 installation core；fetch failure 不能进入 core 后触发 cache、PATH、latest 或邻接 fallback。

### 类型化状态与失败

原生实现以不可混用的状态值表达转换，名称可按 Rust 代码惯例调整，但语义必须保持：

```text
ValidatedRegistration
  + NativeHostIdentity
  + HeldTargetLock
  + ExactDistributionBytes
    -> VerifiedStaging
    -> InstalledInactiveSlot
    -> QualifiedInactiveSlot

ValidatedRegistration(active)
  + QualifiedInactiveSlot
  + verified pre-spawn identity
    -> ActiveInvocationPlan
```

不得让裸路径、布尔 `verified = true`、字符串状态或目录存在代替上述能力。`runtime-unavailable`、`installation-failed`、`qualification-failed`、`process-failure` 和 `identity-failure` 是产品外层 outcome；只有严格通过的 checker stdout 才承载 `accepted`、`accepted-with-trust`、`incomplete` 或 `rejected`。外层 outcome 与 checker 四态不得使用同一个 enum 或隐式转换。

### `checker-runtime-store-v0.1` 持久化能力接口

首个 store 接口固定为 `checker-runtime-store-v0.1`。产品打包层向它注入一个已经解析、规范且位于用户级私有数据区域的绝对根；runtime core 不从 `HOME`、当前目录、环境变量、注册表默认值或 repository checkout 自行发现根。绝对根只存在于本机配置与诊断，不进入 receipt、qualification、companion、slot identity 或其他 canonical artifact。

接口只暴露六种能力：

1. `acquire_target_lock(target)`：返回只对精确目标有效的持锁能力；锁失败不降级为无锁写入。
2. `create_owned_staging(lock, transaction)`：在最终 slot 的同一文件系统创建本次事务独占的 staging；transaction identity 只用于恢复和诊断，不进入 canonical identity。
3. `publish_slot_exclusive(lock, slot_identity, verified_staging)`：仅以原子 rename 发布；已有 slot 必须逐文件、mode 与 receipt 精确一致才返回 reuse，否则不覆盖。
4. `read_slot_exact(slot_identity)`：重读 immutable slot、receipt 和 binary，检查 realpath containment、普通文件、link count、mode、长度、SHA-256 与 executable format。
5. `create_qualification_exclusive(registration, qualification_bytes)`：在 slot 外按 canonical document identity exclusive create 成功 record 与三份 companion；不得修改 slot receipt。
6. `append_attempt(registration, bounded_observation)`：追加 installation / qualification / invocation 的失败或资源观察；后续成功不覆盖旧 attempt，观察不得包含凭据、绝对路径、环境值或真实用户数据。

物理目录名和产品绝对路径属于后续打包实现，不是跨版本公共格式；以下身份和原子性则是接口契约：

- slot identity 仍精确为 `target + distribution raw SHA-256`；
- slot 内 executable 与 installation receipt 路径继续以 launcher policy 为唯一来源；
- qualification success 位于 slot 外，按 record 与 qualification document identity 唯一；
- staging、slot 与 publish rename 必须位于同一文件系统；
- 只有持锁者可以删除自己创建的 incomplete staging，不能清理未知目录、旧 slot 或其他 attempt；
- recovery 重新验证全部字节，不从目录名、partial receipt 或先前进程状态推断完成。

测试实现可以使用临时文件系统或内存 store，但 production `FilesystemStore` 必须在原生 macOS 测试中验证 rename、symlink / hard-link、mode、进程并发、崩溃恢复和正在使用的 executable 不被替换。mock 成功不能替代这些结果。

### Independent Check parser 的复用边界

qualification 与产品 invocation 在主仓内复用同一个 Rust result consumer，避免两条产品入口对同一 stdout 形成不同解释。该 consumer 以公共 schema、canonical fixture、域摘要和负例为输入，可以复用主仓生产侧经过审阅的 UTF-8、strict JSON / JCS、SHA-256 与闭合数据结构基础；它不得：

- import、链接、翻译或复制 Checker Go 实现的 parser、四态聚合、义务重建或语义规则；
- 在运行时调用 Python 一致性核心决定产品结果；
- 读取 expected companion 后改写实际 stdout，或只比较 raw digest 而跳过严格 parse 与身份绑定；
- 把 checker `rejected` / `incomplete` 当外层进程失败，或把外层失败合成为 checker 四态；
- 因 parser 不支持新字段或版本而调用旧 parser、宽松 JSON 库、schema-only fallback 或 checker 自解析 API。

允许共享的是 Independent Check Contract 的公开规范字节、schema、正负 fixture 和 domain separator。Python 核心与 Checker Go parser 都可在测试中对同一 fixture 形成交叉实现观察，但任何一个实现通过都不能替代 Rust consumer 自身的拒绝矩阵。

### 工具链、依赖与 workspace 停止线

本 ADR 不授权创建 Cargo workspace。首次原生实现变更必须在同一受审阅切片中：

1. 提交精确固定 Rust `1.97.1` 的工具链文件和 Rust 2024 edition 配置；
2. 由 Cargo 创建并提交 `Cargo.lock`，所有构建与测试使用 locked mode；
3. 只创建支撑首个真实纵向切片的 package / module，不建立空 compiler、plugin、provider 或跨平台 facade；
4. 对每项 crate 说明精确解析版本、用途、许可证、维护状态、build script、proc macro、native code、传递依赖、替代方案和分发影响；
5. 明确哪些 strict JSON / JCS、SHA-256、USTAR、文件锁、process limit 与 Mach-O 能力由自有代码或依赖承担，并给出负例与交叉实现计划；
6. 先以合成 bytes 和临时根重放现有矩阵，不下载、安装或执行真实 checker payload。

当前本机 Rust `1.96.0` 不能替代冻结的 `1.97.1`。在 `1.97.1` payload、来源 / 许可证和首批依赖审阅完成前，不得用本机旧工具链生成“临时” lockfile、编译结果或验收证据，也不得手工伪造 Cargo 解析产物。

## 验证与进入真实安装的门槛

原生切片至少重放 Python 一致性核心当前覆盖的 target selection、USTAR、receipt、atomic publish、exact reuse、qualification 和 process / identity failure 矩阵，并新增：

- Rust result consumer 对 Independent Check Contract 全部 canonical result 与负例的独立接受 / 拒绝；
- 主仓 Rust consumer 与 Checker Go parser 对公共 fixture 的结论对照，但不共享实现；
- 外层 / 内层真实 distribution 结构的合成小尺寸等价 fixture，不把 4.7 MiB 已发布 payload 当单元测试依赖；
- macOS arm64 原生文件锁、同文件系统 rename、symlink / hard-link、mode、Mach-O、spawn、timeout、signal、stdout cap、空环境、只读 bundle 与 spawn 后身份漂移测试；
- store crash recovery、重复 qualification exclusive create、revoked / replacement 和既有 slot 不变性测试。

只有上述原生测试、精确工具链、依赖审阅和产品打包根选择都通过后，才能提出真实 immutable asset fetch / install 计划。真实安装仍只允许推进为 `installed-inactive` 与 qualification evidence；active 转换继续由 ADR 0011 的独立授权控制。

## 后果

收益：

- 产品编译、runtime 调用与打包使用一个精确原生工具链和发布图，不增加 Python 或第二个产品 daemon；
- 网络能力与安装验证核心分离，测试和产品调用都能证明 checker 进程没有下载能力；
- store 以锁、staging、exclusive create 和 append-only attempt 表达真实事务，不靠可变路径或隐式成功；
- qualification 与 invocation 共用一个生产 result consumer，同时继续与 Checker Go parser 保持源码和依赖独立；
- 当前 Python 实现保留为跨实现 oracle，不会悄然变成产品可信基。

代价与风险：

- Rust 标准库不足以直接提供全部 strict JSON / JCS、SHA-256、USTAR、跨平台锁和资源限制能力，首批依赖或自有实现审阅不可跳过；
- 与 `raxc` 同 workspace 会让 runtime 受生产工具链升级影响，必须用 package 边界、依赖方向和定向矩阵控制耦合；
- 当前只有 macOS arm64 原生目标证据，逻辑接口可跨平台不等于 Linux / Windows 实现已经成立；
- 产品打包根、权限模型、撤销中运行进程策略和用户可见 CLI 仍待具体产品版本冻结。

## 重新评估条件

出现以下任一事实时，以新 ADR 重新比较，而不是增加 fallback：

- 产品威胁模型要求 launcher 与 `raxc` 使用不同签名、权限、更新节奏或强制进程隔离，内部组件无法满足；
- 同一 Cargo workspace 导致 checker runtime 必须依赖生产语义模块、未审阅 native code 或与产品无关的大型依赖；
- Rust 在目标平台无法可靠施加 ADR 0011 的外层资源 / 进程限制，而小型受审阅平台进程可以显著缩小可信基；
- 六平台实现证明单一 store / spawn 接口隐藏了不可兼容的安全语义，必须显式分裂平台 profile；
- Independent Check 公共格式演进后，主仓 consumer 无法保持严格兼容且只能复用 checker 私有实现。

修改生产宿主语言、把 launcher 移入 checker 仓库、允许 in-process checker、让 core 持有网络 / provider credential、从环境发现安装根、共享 Checker Go parser、让 Python 成为产品运行依赖、把外层失败映射为 checker 四态，或取消 store 的持锁 / exclusive / append-only 边界，必须以新 ADR 替代本决策。
