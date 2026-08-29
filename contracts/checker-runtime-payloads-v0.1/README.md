# Checker Runtime Payload Registration v0.1

本目录把独立 checker 的源码身份、目标平台、候选二进制、构建 provenance、独立 acceptance、字节保留 / 取得方式和重新验证条件绑定为闭合登记记录。它物化 [ADR 0003](../../docs/adr/0003-version-identities-and-compatibility-layers.md)、[ADR 0008](../../docs/adr/0008-independent-checker-isolation-and-artifact-exchange.md)、[ADR 0010](../../docs/adr/0010-checker-runtime-payload-durable-registration.md) 与[当前状态](../../docs/status/current.md)的 runtime 身份边界，不定义安装器、launcher 或公共 Evidence 新字段，也不授权创建 Release。

## 当前结论

`contract.json` 明确登记 `active = 0`，即当前没有可由产品 launcher 使用的 runtime payload：

- 2026-08-28 的 macOS arm64 候选曾通过 `accepted-for-controlled-runtime-registration`，但它绑定旧 `checker.source = sha256:3b809b...d90b4`；artifact、canonical provenance 与 canonical acceptance 原始字节已经删除，也没有登记 fetch 入口，因此只保留为 `historical-ineligible`，不得重绑到当前 source。
- 当前 `checker.source = sha256:e2c4ae...9044` 已形成 `candidate-retained-temporarily` 记录：`Checker Payload Candidate` run `33246312135` 在精确 `master` head `a81f5b4704efddd1d8c293f9e8e47c58149e65b7` 上以 attempt 1 成功；构建 / 上传 job `99084274782` 与按 artifact ID 回读 job `99084367932` 均成功。当前 binary 为 4,689,378 bytes / `sha256:02bdc0...3a2e5`，canonical provenance 为 1,389 bytes / `sha256:747777...4812`，canonical acceptance 为 1,580 bytes / `sha256:afbfe9...79a4`；acceptance 决定仍为 `accepted-for-controlled-runtime-registration`。三类字节与 1,295-byte retention manifest 已封装进 4,697,600-byte USTAR `sha256:5e567f...eb701`，由 GitHub Actions artifact ID `9712952210` 暂存并完成 provider 独立回读。Git commit、远程 ref、CI 与临时候选仍不能替代 durable active runtime 登记。

已知摘要仍可用于审计历史陈述，但摘要存在不等于字节可取得、可重新验证、已安装或可运行。当前候选的精确 fetch 只在 artifact ID `9712952210` 未过期且 provider 对象仍存在时成立；provider 回读时记录的创建时间为 `2026-08-29T09:48:31Z`，到期时间为 `2026-11-27T09:47:39Z`。ADR 0010 已选择 Checker 仓库的 GitHub immutable Release asset 作为首个 durable provider；distribution 实现提交 `f6a02b9314051fd841e1f3d3d1491a8a73ad7da7` 的常规 `Checker Checks` run `33253582957` / attempt 1 三个 job 均成功。随后 `dev` 治理提交 `12bbd5b4c14583e625ec6c242d5cdf7fe6d9ba1d` 关闭普通 push CI，并由补正提交 `4b95b2a81616110f5d3ed076f882a18ddc6aba37` 重放 source sidecar；当前 `checker.source = sha256:401158...e3999`。`dev -> master` PR `#2` 在精确 base `a81f5b4...49e65b7` / head `4b95b2a...aba37` 上通过 `Checker Checks` run `33255345832` / attempt 1 三个 job，随后以 merge commit `f960603aa1120ebe427eb9227f116f4a41513d5e` 晋升，并精确 fast-forward 回流；当前 `origin/master` / `origin/dev` 与本地 Checker `dev` 均为 `f960603...13d5e`，tree 为 `fb542000...d91b20`。它尚未形成新 source 的候选 / distribution 实例。当前仓库设置尚未验证，tag / Release / asset 均不存在；provider 选型、源码实现与常规 CI 都不等于正式登记。launcher 的 OS / architecture 硬隔离仍是之后的独立门禁。

## 两级存储策略

`contract.json` 选择 `laugh0608/RadishAxiomChecker` 的 GitHub Actions direct-file artifact 作为候选阶段有限期暂存：上传对象必须是 checker 仓库归档器形成的确定性 USTAR 单文件，并由精确固定的 `actions/upload-artifact` v7.0.1 以 `archive: false` 上传，不生成 provider 外层 ZIP。它绑定精确 workflow run / attempt / ref / head SHA、artifact ID / name / created / expires / provider direct-file digest / size，以及内层 archive / retention manifest 身份。fetch 只允许精确 artifact ID；上传后还须由独立 job 使用精确固定的 `actions/download-artifact` v8.0.1 从 provider 原样回读并复核内层 USTAR 与 REST API 元数据。公开仓库最长 90 天的 Actions artifact 只允许 `candidate-only-never-active`，到期或 workflow run / artifact 被删除后必须转为 unavailable。

候选 workflow 只有 `workflow_dispatch`，要求显式 source、version 和上传确认，并限制为 `dev` / `master` ref；构建 job 使用 `macos-15` arm64 runner，read-back job 使用 Ubuntu。该文件已经进入默认分支并回流到 `dev`，当前状态是 `candidate-retained-temporarily-provider-readback-passed`。本次只运行 attempt 1，没有重跑；候选未被安装、发布、复制到 durable provider 或提升为 active runtime。

active runtime 的 durable provider 已选择 `laugh0608/RadishAxiomChecker` 的 GitHub immutable Release asset，状态为 `selected-setting-not-verified-release-not-materialized`。每个 source / implementation version / target 使用一个专用 `checker-payload/...` tag 与唯一 distribution asset；禁止 `latest` alias，登记必须绑定 release / asset ID、immutable flag、target commit、名称、长度、digest、state、发布时间和精确 fetch，并在发布后完成 provider 元数据与原始 asset 的独立回读。release attestation 只是补充 provider provenance，不能替代 payload / distribution acceptance。

当前 `e2c4ae...9044` 候选 USTAR 不是可发布 distribution asset：它缺少 checker Apache-2.0 与 Go `LICENSE` / `PATENTS` 材料，现有 acceptance 也明确排除 distribution legal compliance 与 publication。Checker `dev` 提交 `f6a02b9314051fd841e1f3d3d1491a8a73ad7da7` 已增加 `radishaxiom-checker-runtime-distribution` `0.1` 确定性外层 USTAR、闭合许可证 inventory 和独立 distribution acceptance；外层 6 个成员包括内层候选、distribution acceptance / manifest 与三份法律材料。生产 package 仍须以新 source 和精确 `go1.26.7` 重跑候选 workflow 才能形成。之后才可经单独授权在启用 immutable releases 后走 draft → 一次发布 → provider verification → 独立回读。当前没有创建或授权 Release / tag / upload。

登记状态机只允许：

```text
candidate-retained-temporarily
  -> distribution-package-accepted
  -> durable-published
  -> registered-inactive
  -> active
```

`durable-published` / `registered-inactive` / `active` 可转为 `revoked`；replacement 必须使用新 source / version / target、新 immutable Release 和新记录，不能原地替换 asset 或重指 tag。激活仍要求单独的 launcher 隔离、安装协调与授权。

## 文件与生成边界

- `records/` 保存历史不可用记录和当前仍未激活的临时候选记录；每份记录都以 `radishaxiom.checker-runtime-payload-registration.v0.1` 域摘要闭合。
- `contract.json` 绑定当前 `checker.source`、记录原始摘要 / 域摘要、状态计数、两级 storage policy 和生成器原始摘要。
- `schemas/` 固定 Draft 2020-12 闭合结构；schema 通过不能提升任何 acceptance 或运行结论。
- `fixtures/negative/` 拒绝旧 artifact 重绑当前 source、已删除字节的 retention 过度声明、历史 payload 冒充正式登记、把 acceptance 扩大到安装、只有 binary 摘要却没有 provenance / acceptance、未知 member、临时候选直接 active、可变 Release 登记、`latest` alias、用 release attestation 冒充 distribution acceptance、缺少独立回读和原地 replacement。

除本 README 外，本目录由以下入口生成，生成文件不得手工修改：

```bash
python3 scripts/generate-checker-runtime-payloads.py --write
```

离线复核：

```bash
python3 scripts/generate-checker-runtime-payloads.py --check
```

该复核只验证仓库内登记事实、域摘要与负例闭合，不下载、构建、执行、安装或发布 checker，也不能在缺少原始 payload 时冒充重新验收。
