# Checker Runtime Payload Registration v0.1

本目录把独立 checker 的源码身份、目标平台、候选二进制、构建 provenance、独立 acceptance、字节保留 / 取得方式和重新验证条件绑定为闭合登记记录。它物化 [ADR 0003](../../docs/adr/0003-version-identities-and-compatibility-layers.md)、[ADR 0008](../../docs/adr/0008-independent-checker-isolation-and-artifact-exchange.md)、[ADR 0010](../../docs/adr/0010-checker-runtime-payload-durable-registration.md) 与[当前状态](../../docs/status/current.md)的 runtime 身份边界，不定义安装器、launcher 或公共 Evidence 新字段，也不授权创建 Release。

## 当前结论

`contract.json` 明确登记 `active = 0`，即当前没有可由产品 launcher 使用的 runtime payload：

- 2026-08-28 的 macOS arm64 候选曾通过 `accepted-for-controlled-runtime-registration`，但它绑定旧 `checker.source = sha256:3b809b...d90b4`；artifact、canonical provenance 与 canonical acceptance 原始字节已经删除，也没有登记 fetch 入口，因此只保留为 `historical-ineligible`，不得重绑到当前 source。
- 当前 `checker.source = sha256:401158...e3999` 已形成 `registered-inactive` 记录：`Checker Payload Candidate` run `33301288846` 在精确 `master` head `f960603aa1120ebe427eb9227f116f4a41513d5e` 上以 attempt 1 成功；构建 / 验收 / 分发 / 上传 job `99229841973` 与按 artifact ID 回读 job `99229998823` 均成功。该 binary 为 4,689,378 bytes / `sha256:7e2816...5aaf`，canonical provenance 为 1,389 bytes / `sha256:45d0ef...2404`，canonical payload acceptance 为 1,580 bytes / `sha256:575705...7b55`；payload acceptance 决定仍为 `accepted-for-controlled-runtime-registration`。三类字节与 1,295-byte retention manifest 已封装进 4,697,600-byte 内层 USTAR `sha256:fb3364...4f3ea`；独立 distribution acceptance 决定为 `accepted-for-controlled-durable-publication-candidate`，外层 4,720,640-byte distribution USTAR 为 `sha256:17b44a...fa437`。该外层 USTAR 已成为精确 immutable Release 的唯一 asset 并进入主仓正式 inactive 登记，但尚未安装或成为 active runtime。

已知摘要仍可用于审计历史陈述，但摘要存在不等于字节可取得、可重新验证、已安装或可运行。Actions artifact ID `9729031154` 继续保留候选历史及有限期精确 fetch；durable fetch 已转为 Release ID `379226889` / asset ID `536372439` 的精确 API URL 与 browser download URL。经分别授权，repository immutable releases 先被启用并回读确认，随后 draft 在完整字节复核后于 `2026-08-30T08:53:07Z` 单次发布；REST 返回 `immutable = true`，tag 精确解析到 `f960603...13d5e`。GitHub Release 与 asset attestation、draft 回读、发布后 authenticated CLI 回读、公开 URL 回读以及严格 distribution / inner candidate verifier 均通过。launcher 的 OS / architecture 硬隔离仍是之后的独立门禁。

## 两级存储策略

`contract.json` 为当前 `401158...e3999` distribution candidate 选择 `laugh0608/RadishAxiomChecker` 的 GitHub Actions direct-file artifact 作为暂存：上传对象是 checker 仓库分发器形成的确定性外层 USTAR 单文件，并由精确固定的 `actions/upload-artifact` v7.0.1 以 `archive: false` 上传，不生成 provider 外层 ZIP。记录绑定精确 workflow run / attempt / ref / head SHA、artifact ID / name / created / expires / provider direct-file digest / size，以及外层 distribution、distribution acceptance / manifest、内层 candidate 与 retention manifest 身份。fetch 只允许精确 artifact ID；上传后还由独立 job 使用精确固定的 `actions/download-artifact` v8.0.1 从 provider 原样回读，并在 Ubuntu 上严格复核外层 distribution、内层 candidate 与 REST API 元数据。公开仓库最长 90 天的 Actions artifact 只允许 `candidate-only-never-active`，到期或 workflow run / artifact 被删除后必须转为 unavailable。

候选 workflow 只有 `workflow_dispatch`，要求显式 source、version 和上传确认，并限制为 `dev` / `master` ref；构建 job 使用 `macos-15` arm64 runner，read-back job 使用 Ubuntu。当前记录只保存 run `33301288846` attempt 1 的实际输出和 provider 元数据，不读取 expected 结果补造身份。候选没有被安装、复制到 durable provider 或提升为 active runtime。

active runtime 的 durable provider 已选择 `laugh0608/RadishAxiomChecker` 的 GitHub immutable Release asset，当前精确 Release 已发布、完成 provider / 字节回读并登记为 `registered-inactive-not-installed-or-active`。每个 source / implementation version / target 使用一个专用 `checker-payload/...` tag 与唯一 distribution asset；禁止 `latest` alias，登记绑定 release / asset ID、immutable flag、target commit、名称、长度、digest、state、发布时间和精确 fetch。GitHub 将仓库首个 Release 报告为 `isLatest = true`，但该可变展示标签没有进入身份或 fetch；`latest`、`releases/latest` 与 `latest/download` 仍全部禁止。release attestation 只是补充 provider provenance，不能替代 payload / distribution acceptance。

当前外层 distribution 已包含内层候选、distribution acceptance / manifest、checker Apache-2.0 `LICENSE` 与 Go `LICENSE` / `PATENTS` 六个成员，并由独立 acceptance 接受为受控 durable publication candidate。精确 tag `checker-payload/go0.1-dev/darwin-arm64-v8.0/sha256-401158...e3999`、target commit `f960603...13d5e`、Release ID `379226889` 与唯一 4,720,640-byte asset ID `536372439` 已通过不可变发布和全部发布后门禁；经独立状态转换授权，主仓现已绑定持久字节和重新验证路径并推进到 `registered-inactive`。进入 `active` 还必须另行完成 launcher OS / architecture / variant 硬隔离、安装协调、runtime companion 与激活授权。

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

- `records/` 保存历史不可用记录和当前已正式登记但尚未激活的 `registered-inactive` 记录；每份记录都以 `radishaxiom.checker-runtime-payload-registration.v0.1` 域摘要闭合。
- `contract.json` 绑定当前 `checker.source`、记录原始摘要 / 域摘要、状态计数、两级 storage policy 和生成器原始摘要。
- `schemas/` 固定 Draft 2020-12 闭合结构；schema 通过不能提升任何 acceptance 或运行结论。
- `fixtures/negative/` 拒绝旧 artifact 重绑当前 source、已删除字节的 retention 过度声明、历史 payload 冒充正式登记、把 acceptance 扩大到安装、正式 inactive 登记缺少 provenance、未知 member、`registered-inactive` 跳过 launcher 隔离 / 安装 / 激活授权直接 active、可变 Release 登记、`latest` alias、用 release attestation 冒充 distribution acceptance、缺少独立回读和原地 replacement。

除本 README 外，本目录由以下入口生成，生成文件不得手工修改：

```bash
python3 scripts/generate-checker-runtime-payloads.py --write
```

离线复核：

```bash
python3 scripts/generate-checker-runtime-payloads.py --check
```

该复核只验证仓库内登记事实、域摘要与负例闭合，不下载、构建、执行、安装或发布 checker，也不能在缺少原始 payload 时冒充重新验收。
