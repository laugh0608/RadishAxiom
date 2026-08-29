# ADR 0010：独立 checker runtime payload 的持久发布与登记

日期：2026-08-29

状态：Accepted

用途：冻结独立 checker runtime payload 的首个持久 provider、发布身份、分发包、登记状态机、撤销 / replacement 和激活边界。

读者：checker 维护者、发布维护者、runtime / launcher 实现者、供应链审阅者和 Checker Runtime Payload Registration 消费者。

不包含：本次启用 GitHub 仓库设置、创建 tag / Release、上传 asset、登记 active runtime、实现 launcher、安装 payload、修改 Ruleset，或为 RadishAxiom 分配产品版本。

## 背景

[ADR 0008](0008-independent-checker-isolation-and-artifact-exchange.md)冻结了独立 checker 的分仓、构建、进程与离线制品边界，但把远程 artifact service、release signing 和产品安装留在范围外。[Checker Runtime Payload Registration v0.1](../../contracts/checker-runtime-payloads-v0.1/README.md)随后把 source、target、binary、build provenance、payload acceptance、retention、fetch 与重新验证条件闭合，并明确区分历史不可用记录、有限期候选和 active runtime。

当前 `checker.source = sha256:e2c4ae31b15162051735a76e44c2fc0a079117994caf3ef53d5710ead1199044` 的 macOS arm64 候选已经完成精确 `go1.26.7` 双次隔离构建、独立 payload acceptance、确定性 USTAR、GitHub Actions 直传和按 artifact ID 独立回读。但 GitHub Actions artifact 最长只保留 90 天，到期或删除后不可取得，不能作为 active runtime 的持久来源。

当前候选归档也不是分发包。它只包含 binary、canonical build provenance、canonical payload acceptance 和 retention manifest；payload acceptance 明确排除 `legal-compliance-for-distribution`、`publication` 与 `release-signing`。把该 USTAR 原样上传到 Release 会把“受控登记候选”错误升级为“可分发制品”，同时遗漏 checker 与 Go runtime 所需许可证 / 专利材料。

GitHub 已提供 repository-level immutable releases：启用后，未来发布的 Release 及其 assets 在发布后不可修改，tag 受到锁定，并自动形成 release attestation。该设置不追溯既有 Release；发布后仍须从 API 确认 `immutable = true`，并可用 GitHub CLI 验证 Release 与 asset。[Immutable releases 概念](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases)、[启用方式](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/prevent-release-changes)、[验证方式](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/verify-release-integrity)、[Release REST API](https://docs.github.com/en/rest/releases/releases)

## 决策

### 首个持久 provider

首个 durable provider 选择公开仓库 `laugh0608/RadishAxiomChecker` 的 **GitHub immutable Release asset**。选择状态是 `selected-setting-not-verified-release-not-materialized`：本 ADR 只决定后续实现边界，不声称仓库已启用 immutable releases，也不声称任何 tag、Release 或 asset 已存在。

下列候选不用于首个 active runtime：

| 方案 | 结论 | 原因 |
| --- | --- | --- |
| GitHub Actions artifact | 仅候选暂存 | 有限 retention，删除 / 到期后不可取得 |
| 普通可变 GitHub Release | 拒绝 | asset 或 tag 可变，不能稳定绑定已登记字节 |
| GitHub immutable Release asset | 采用 | 与 checker 公开仓库、API 元数据、精确 asset 和 provider attestation 闭合，新增基础设施最少 |
| 外部 object storage / OCI registry | 延后 | 需要另行冻结凭据、保留、不可变策略、费用与 provider 信任边界 |

Provider 的 release attestation 只补充“GitHub 发布了哪些 asset”的来源证据，不能替代项目的原始字节 SHA-256、build provenance、payload acceptance、分发许可证审阅、checker 正确性或独立 provider 回读。

### 专用发布身份

checker payload 的持久 tag 不使用 [ADR 0003](0003-version-identities-and-compatibility-layers.md) 的 `vYY.M.RELEASE-*` 产品 tag。当前尚未分配 RadishAxiom 产品版本，强行使用产品 CalVer 会制造尚不存在的产品发布。

每个 `checker.source + checker implementation version + target` 使用一个不可变 Release，tag 规范为：

```text
checker-payload/go0.1-dev/<goos>-<goarch>-<variant>/sha256-<checker-source-hex>
```

当前 `e2c4ae...9044` source 缺少 distribution 实现且不能原样发布；实现本 ADR 会形成新的 source identity，因此不为当前候选预先分配具体 tag。一个 Release 只承载一个 source / version / target，避免先发布单平台 immutable Release 后无法追加其他平台 asset，也不让单平台证据冒充六平台支持。

唯一 runtime distribution asset 名称规范为：

```text
radishaxiom-checker-go0.1-dev-<goos>-<goarch>-<variant>-sha256-<checker-source-hex>.distribution.tar
```

禁止使用 `latest`、`releases/latest`、`latest/download`、浮动分支或可重定向别名作为登记身份或 fetch 入口。

### 分发包前置条件

现有候选 USTAR 继续作为候选级内层 payload，不直接成为 Release asset。持久发布前必须形成 `radishaxiom-checker-runtime-distribution` `0.1` 确定性外层 USTAR，至少包含：

```text
checker-payload-candidate.tar
checker-payload-distribution-manifest-v0.1.jcs
licenses/go/LICENSE
licenses/go/PATENTS
licenses/radishaxiom-checker/LICENSE
```

distribution manifest 必须绑定 source、implementation version、target、内层候选 USTAR 的文件名 / 长度 / 原始 SHA-256，以及每份许可证 / 专利文件的路径、长度、原始 SHA-256 与作用域。若 checker 仓库未来增加 `NOTICE`、第三方 module、生成器、C / `cgo`、动态库或其他需随分发保留的材料，必须扩展并重新验收清单，不能靠旧 manifest 默认覆盖。

分发 acceptance 是 payload acceptance 之后的独立决定，至少复核：

1. 外层 USTAR 的确定性、闭合 member、路径、mode、长度与摘要；
2. 内层候选归档仍通过其严格 verifier，binary / provenance / acceptance 未改变；
3. 许可证 / 专利材料与实际 binary 的 module、Go toolchain / standard library、项目许可证相符；
4. 发布 asset 名称、tag、source、version 和 target 一致；
5. scope 明确区分可分发字节、目标平台与尚未覆盖的安装、launcher 隔离、签名和跨平台等价。

在上述格式、生成器与 acceptance 尚未实现前，当前候选只能保持 `candidate-retained-temporarily`。这不是通过补一份 README 或 Release notes 就能消除的停止线。

### 发布与独立回读

未来每次远程发布都需要针对精确目标的单独授权，并按以下顺序失败关闭：

1. 在 authenticated repository Settings 中确认 immutable releases 已在创建 draft 前启用；启用只作用于未来发布，不能用随后启用来补救先前 Release。
2. 只读确认精确 tag / Release 不存在，目标 commit、source、version、target、distribution asset 和分发 acceptance 全部闭合。
3. 创建指向精确 checker commit 的 draft Release；draft 是可变的临时编排状态，不能进入登记。
4. 上传完整且唯一的 distribution asset，在 draft 状态按原始字节复核长度、SHA-256、内层候选和许可证 inventory。
5. 只发布一次，不在发布后补传、替换或删除 asset。
6. 发布后读取 Release REST 元数据，要求精确 repository、release ID、tag、target commit、`immutable = true`、`published_at`，并读取 asset ID、name、size、digest、state、API URL 与 browser download URL。
7. 使用 release / asset verification 验证 provider attestation；再由与上传 job 分离的读取路径按精确 asset ID 或精确 tag + asset name 下载原始字节，复算外层 / 内层全部身份和分发 acceptance。
8. 只有上述事实进入主仓生成契约并通过审阅，记录才可由 `durable-published` 进入 `registered-inactive`。

Release 自动生成的 source archive 不进入 payload 登记，也不作为 distribution asset；GitHub 的 release integrity verification 不覆盖这类自动 source archive。

### 登记、激活与状态机

存储 / 登记状态与产品激活严格分离：

```text
candidate-retained-temporarily
  -> distribution-package-accepted
  -> durable-published
  -> registered-inactive
  -> active
```

允许的撤销边为：

```text
durable-published   -> revoked
registered-inactive -> revoked
active              -> revoked
```

每次转换都需要该边所要求的实际证据与单独授权，不能由 workflow success、provider attestation、registry generator 或 launcher 启动自动提升。`registered-inactive` 只说明主仓已绑定持久字节和重新验证路径；`active` 还必须具有精确 OS / architecture / variant 硬隔离、安装协调、runtime companion 和激活授权。

候选过期、字节丢失或 source 漂移时转为历史不可用记录，不允许跳过分发或发布状态。当前 active count 保持 0。

### 撤销与 replacement

已发布 asset、tag 与登记记录不原地替换或重指向。发现错误、许可证遗漏、provider 异常或安全问题时：

1. 主仓保留原记录并追加 `revoked`、原因、时间和可审计证据；
2. launcher 不再选择该记录；已经安装的副本由另行冻结的安装 / 回滚流程处理；
3. 修复产生新的 source、version 或 target identity，并从新的候选与分发验收开始；
4. 新 Release 使用新 tag、新 asset ID 和新登记记录，旧 tag 不复用。

删除 immutable Release 不是正常撤销或 replacement 机制。即使 provider 允许删除，登记仍保留 tombstone，且不能依赖复用同名 tag 恢复身份。紧急远程删除属于破坏性外部动作，必须另行授权并记录后果。

## 后果

收益：

- active runtime 可以绑定稳定、不可变且可独立回读的精确字节；
- checker payload 发布不必冒充尚未存在的 RadishAxiom 产品版本；
- 候选验收、分发法律 / inventory 验收、provider provenance、正式登记和 launcher 激活不再混为一个“发布成功”；
- 单目标 Release 与 append-only replacement 避免单平台证据外推和 tag 重指向。

代价与风险：

- 需要在 checker 仓库实现新的 distribution pack / verify / accept 路径，形成新的 `checker.source` 并重跑候选 workflow；
- immutable Release 发布后不能修补 asset，draft 阶段必须完成全部预发布复核；
- GitHub provider 与 repository 设置仍属于外部可信 / 可用性边界，主仓必须保留足够身份供迁移和独立回读；
- 许可证 inventory 的接受只限定于审阅过的制品与作用域，不等于无限期、跨平台或所有司法辖区的法律结论。

## 实施顺序与停止线

1. 先在 checker 仓库实现 distribution format、确定性 pack / verify、许可证 inventory 和独立 distribution acceptance，并通过本地门禁。
2. 代码审阅 / 提交 / push、候选 workflow、immutable release setting、draft / publish 和主仓登记分别取得授权；前一项成功不自动授权后一项。
3. 新 source 的 candidate 与 distribution package 通过后，才可提出精确 Release 计划。
4. `registered-inactive` 完成后再冻结 launcher OS / architecture 硬隔离与安装协调；此前 active count 必须为 0。

修改首个 durable provider、tag namespace、distribution format、发布不可变要求、状态机、撤销 / replacement 或激活分离原则，必须以新 ADR 替代本决策，并同步 Checker Runtime Payload Registration、当前状态、仓库治理和相关自动化。provider 的 release ID、asset ID、摘要、时间与单次运行事实只进入生成记录或当前状态，不复制到本 ADR。
