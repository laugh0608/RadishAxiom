# Toolchain Payload Acceptance v0.1

本目录记录工具 payload 从“publisher 元数据已登记”进入“可作为后续受控构建输入”的独立供应链门禁。首批只覆盖 Go `go1.26.7` 的两个精确原始字节对象：

| 制品 | 平台 | 字节数 | 项目重算 SHA-256 | 结论 |
| --- | --- | ---: | --- | --- |
| `go1.26.7.darwin-arm64.tar.gz` | `macos-arm64` | 64,772,572 | `020a1e8224811be75163e920bc77e0926a1390a6aeea19bdcf23f74b9d749f6d` | `accepted-for-controlled-build-input` |
| `go1.26.7.src.tar.gz` | `source` | 34,150,794 | `0ed24eac755105085b89fe9cabc2742b91a0ad7b94b59d3ad364918ebc8956ad` | `accepted-for-controlled-build-input` |

两项摘要都与 [Toolchain & Adapter Identity Registry v0.1](../toolchain-adapters-v0.1/README.md) 登记的 Go publisher 摘要逐字匹配。下载只发生在隔离临时目录；没有释放到安装前缀，没有执行归档内 `go`，没有修改 `mise`、`PATH`、`GOROOT`、`GOPATH` 或 shell 配置。源码归档因单连接中断而使用官方 HTTPS URL 的连续 Range 分段补齐；每段长度和连续性检查通过后组装，最终只以完整字节数和整包 publisher SHA-256 匹配作为 payload 身份结论。

## 记录分层

- `observations/` 是 `scripts/inspect-toolchain-tar.py` 对摘要已匹配归档产生的只读观察。记录 archive 全成员元数据清单摘要、路径与类型检查、权限/owner/mtime 集合、顶层布局、必需文件、许可证/专利文件以及 vendor module 清单；不包含归档、二进制、绝对路径或环境值。
- `records/` 是逐制品 acceptance record。它把 publisher 摘要、项目重算摘要、来源 URL、签名状态、观察记录、依赖/许可证结论和最终适用范围绑定到域摘要。
- `contract.json` 绑定 registry、检查器原始字节和两份 record 的原始摘要/域摘要；`schemas/` 固定 Draft 2020-12 结构；`fixtures/negative/` 拒绝摘要漂移、签名过度声明、失败 archive 被接受、作用域遗漏、许可证/依赖清单漂移和未知 member。

观察到的 host/source `go/VERSION` 都是 `go1.26.7` 与 `time 2026-08-18T21:44:21Z`；`LICENSE`、`PATENTS`、36 项许可证/专利清单、3 份 vendor manifest 和 17 个版本化模块逐字一致。许可证文本结论覆盖 BSD-3-Clause、Apache-2.0、MIT，以及 BoringCrypto 目录中的 OpenSSL、original SSLeay、ISC 和 BSD-style 组合文本；`PATENTS` 单独作为 Go patent grant，不与软件许可证状态混写。

## 验收边界

`accepted-for-controlled-build-input` 只接受以下事实：原始 payload 身份匹配、archive 布局/元数据通过当前检查 profile、archive 内许可证与 vendor 清单已记录，以及未来可以在另行授权的隔离构建中精确选择该制品。它明确不证明或授权：

- 安装或执行工具；
- publisher detached signature 已验证；registry 没有为这两个制品登记可验证的签名输入；
- host binary 可由 source 可复现地产生；
- checker 已实现、正确或已经通过真实 bundle；
- 其他 Go 平台制品、其他工具或跨平台结果等价；
- 任一具体再分发方案已经完成法律合规判断。

因此其余 Go 五个平台 payload 仍保持 `not-downloaded` / `not-accepted`，Go 工具级许可证状态也继续保持整体 `not-accepted`，不把本批局部审阅外推到未观察归档。

## 复核入口

对已有归档重新产生观察（路径仅为示例，不会安装）：

```bash
python3 scripts/inspect-toolchain-tar.py \
  --archive /isolated/go1.26.7.darwin-arm64.tar.gz \
  --filename go1.26.7.darwin-arm64.tar.gz \
  --expected-sha256 020a1e8224811be75163e920bc77e0926a1390a6aeea19bdcf23f74b9d749f6d \
  --profile go1.26.7-darwin-arm64-host
```

生成由观察记录派生的 acceptance record、schema、contract 和负例：

```bash
python3 scripts/generate-toolchain-payload-acceptance.py --write
```

离线只读校验：

```bash
python3 scripts/generate-toolchain-payload-acceptance.py --check
```

除本 README 与 `observations/` 外，本目录文件由 acceptance 生成器维护。`observations/` 只能由已核对 publisher 摘要的精确归档通过登记检查器重新产生；仓库级校验验证其闭合结构、内部摘要、host/source 一致性和派生记录，但不会在没有外部 payload 时冒充重新检查归档原始字节。
