# Checker Runtime Payload Registration v0.1

本目录把独立 checker 的源码身份、目标平台、候选二进制、构建 provenance、独立 acceptance、字节保留 / 取得方式和重新验证条件绑定为闭合登记记录。它物化 [ADR 0003](../../docs/adr/0003-version-identities-and-compatibility-layers.md)、[ADR 0008](../../docs/adr/0008-independent-checker-isolation-and-artifact-exchange.md) 与[当前状态](../../docs/status/current.md)的 runtime 身份边界，不定义安装器、launcher、Release 或公共 Evidence 新字段。

## 当前结论

`contract.json` 明确登记 `active = 0`，即当前没有可由产品 launcher 使用的 runtime payload：

- 2026-08-28 的 macOS arm64 候选曾通过 `accepted-for-controlled-runtime-registration`，但它绑定旧 `checker.source = sha256:3b809b...d90b4`；artifact、canonical provenance 与 canonical acceptance 原始字节已经删除，也没有登记 fetch 入口，因此只保留为 `historical-ineligible`，不得重绑到当前 source。
- 当前 `checker.source = sha256:e2c4ae...9044` 只形成 `awaiting-controlled-build-and-acceptance` 记录；闭合 source 已包含只手工触发的候选 workflow 实现，checker `origin/dev` 已精确指向 commit `014f35cc268cb6cce6c35b840841696cff538f7b`，常规 `Checker Checks` run `33238577710` 成功，但该文件尚未进入默认分支或运行，仍无 artifact、provenance、acceptance 或 candidate archive。Git commit、远程 ref 与 CI 只作来源和治理追溯，不能补全或替代 payload 身份。

已知摘要仍可用于审计历史陈述，但摘要存在不等于字节可取得、可重新验证、已安装或可运行。未来把记录提升为正式登记，至少要让当前 source 经过精确 `go1.26.7` 受控构建和独立 acceptance，并为 artifact、provenance、acceptance 三类规范字节形成可复核的 retention 或 fetch 边界；launcher 的 OS / architecture 硬隔离仍是之后的独立门禁。

## 两级存储策略

`contract.json` 选择 `laugh0608/RadishAxiomChecker` 的 GitHub Actions direct-file artifact 作为候选阶段有限期暂存：上传对象必须是 checker 仓库归档器形成的确定性 USTAR 单文件，并由精确固定的 `actions/upload-artifact` v7.0.1 以 `archive: false` 上传，不生成 provider 外层 ZIP。它绑定精确 workflow run / attempt / ref / head SHA、artifact ID / name / created / expires / provider direct-file digest / size，以及内层 archive / retention manifest 身份。fetch 只允许精确 artifact ID；上传后还须由独立 job 使用精确固定的 `actions/download-artifact` v8.0.1 从 provider 原样回读并复核内层 USTAR 与 REST API 元数据。公开仓库最长 90 天的 Actions artifact 只允许 `candidate-only-never-active`，到期或 workflow run / artifact 被删除后必须转为 unavailable。

候选 workflow 只有 `workflow_dispatch`，要求显式 source、version 和上传确认，并限制为 `dev` / `master` ref；构建 job 使用 `macos-15` arm64 runner，read-back job 使用 Ubuntu。GitHub 只会接收已经存在于默认分支的手工 workflow，因此当前状态是 `workflow-on-dev-not-default-branch-or-materialized`；进入 `master`、下载 Go archive、构建、上传和回读都属于后续分别授权的远程动作。

active runtime 的 durable provider 仍保持 `not-selected`。它必须满足不可变资产、稳定精确 fetch、原始长度 / SHA-256、provider 独立回读、无 latest alias、撤销 / replacement 规则和单独发布授权。GitHub immutable release assets 只是待发布治理审查的候选；当前契约没有选择、创建或授权 Release / tag / upload。

## 文件与生成边界

- `records/` 保存历史不可用记录和当前待构建记录；每份记录都以 `radishaxiom.checker-runtime-payload-registration.v0.1` 域摘要闭合。
- `contract.json` 绑定当前 `checker.source`、记录原始摘要 / 域摘要、状态计数、两级 storage policy 和生成器原始摘要。
- `schemas/` 固定 Draft 2020-12 闭合结构；schema 通过不能提升任何 acceptance 或运行结论。
- `fixtures/negative/` 拒绝旧 artifact 重绑当前 source、已删除字节的 retention 过度声明、历史 payload 冒充正式登记、把 acceptance 扩大到安装、只有 binary 摘要却没有 provenance / acceptance，以及未知 member。

除本 README 外，本目录由以下入口生成，生成文件不得手工修改：

```bash
python3 scripts/generate-checker-runtime-payloads.py --write
```

离线复核：

```bash
python3 scripts/generate-checker-runtime-payloads.py --check
```

该复核只验证仓库内登记事实、域摘要与负例闭合，不下载、构建、执行、安装或发布 checker，也不能在缺少原始 payload 时冒充重新验收。
