# Toolchain Payload Acceptance v0.1

本目录记录工具 payload 从“publisher 元数据已登记”进入“可作为后续受控构建输入”的独立供应链门禁。当前覆盖 Go `go1.26.7` 的两个精确对象，以及 Rust `1.97.1` macOS arm64 rustup 路径的五个 component 与 source：

| 制品 | 平台 | 字节数 | 项目重算 SHA-256 | 结论 |
| --- | --- | ---: | --- | --- |
| `go1.26.7.darwin-arm64.tar.gz` | `macos-arm64` | 64,772,572 | `020a1e8224811be75163e920bc77e0926a1390a6aeea19bdcf23f74b9d749f6d` | `accepted-for-controlled-build-input` |
| `go1.26.7.src.tar.gz` | `source` | 34,150,794 | `0ed24eac755105085b89fe9cabc2742b91a0ad7b94b59d3ad364918ebc8956ad` | `accepted-for-controlled-build-input` |
| `cargo-1.97.1-aarch64-apple-darwin.tar.xz` | `macos-arm64` | 8,876,992 | `2d84a74e9558192a7de674aca6aa3ab7464bed2df97e0377156ddb7e09a0fd7a` | `accepted-for-controlled-build-input` |
| `clippy-1.97.1-aarch64-apple-darwin.tar.xz` | `macos-arm64` | 3,171,216 | `5e44c0ac5ca9b6f14a3c9031a61f583348b902f908f46e95717aef1dbd2807db` | `accepted-for-controlled-build-input` |
| `rust-std-1.97.1-aarch64-apple-darwin.tar.xz` | `macos-arm64` | 29,286,636 | `a4895f5c6995e83cab8687e46b14324592398049def71ce75ca308c981cf200d` | `accepted-for-controlled-build-input` |
| `rustc-1.97.1-aarch64-apple-darwin.tar.xz` | `macos-arm64` | 68,127,952 | `6076cad38ccabaa24325f26a74080a363a2633a9cd34c473a8977255d8a593cb` | `accepted-for-controlled-build-input` |
| `rustfmt-1.97.1-aarch64-apple-darwin.tar.xz` | `macos-arm64` | 1,502,516 | `358bbba5d0c7c37116ec15f67cfd3ac4da5d3c319cddb49389c26d3a0c65747a` | `accepted-for-controlled-build-input` |
| `rustc-1.97.1-src.tar.xz` | `source` | 242,787,896 | `0ed06fdaffd4722a7702e0b4eebfafc897ab8f513e8e1b247cdd7e5c6df6ded2` | `accepted-for-controlled-build-input` |

八项摘要都与 [Toolchain & Adapter Identity Registry v0.1](../toolchain-adapters-v0.1/README.md) 登记的 publisher 元数据逐字匹配。下载只发生在隔离临时目录；没有释放到安装前缀，没有执行归档内工具，也没有修改 rustup、`mise`、`PATH`、`RUSTUP_HOME`、`CARGO_HOME`、`GOROOT`、`GOPATH` 或 shell 配置。连接中断的归档使用官方 HTTPS URL 的连续 Range 分段补齐；出现不完整分段时先拒绝错误组装，再补齐精确区间。最终只以完整字节数和整包 publisher SHA-256 匹配作为 payload 身份结论。

## 记录分层

- `observations/` 是 `scripts/inspect-toolchain-tar.py` 对摘要已匹配归档产生的只读观察。公共层记录 archive 全成员元数据清单摘要、路径与类型检查、权限/owner/mtime 集合、顶层布局与必需文件；Go profile 记录许可证/专利和 vendor module，Rust profile 记录 component manifest、Cargo manifest / lock 数量、选定许可证文件和 publisher SPDX 元数据。不包含归档、二进制、绝对路径或环境值。
- `records/` 是逐制品 acceptance record。它把 publisher 摘要、项目重算摘要、来源 URL、签名状态、观察记录、依赖/许可证结论和最终适用范围绑定到域摘要。
- `contract.json` 绑定 registry、检查器原始字节和八份 record 的原始摘要/域摘要；`schemas/` 固定 Draft 2020-12 结构；`fixtures/negative/` 拒绝摘要漂移、签名过度声明、失败 archive 被接受、作用域遗漏、许可证/依赖清单漂移和未知 member。

Go host/source 的 `VERSION`、许可证/专利清单、vendor manifest 和版本化模块仍逐字一致。五个 Rust component 均没有 link / hardlink / 特殊文件；Rust source 包含 323,914 个 member、148 个受控 symlink、4,613 份 `Cargo.toml` 与 1,977 份 `Cargo.lock`，链接目标都停留在 `rustc-1.97.1-src` 顶层内。Rust 主项目表达式记录为 `MIT OR Apache-2.0`；source 的两套元数据各观察到 12 种 SPDX 表达式，包含 LLVM exception、Unicode、OFL、GPL / GCC exception 等材料，明确只作为库存，不外推为整包双许可证或具体分发法律结论。

## 验收边界

`accepted-for-controlled-build-input` 只接受以下事实：原始 payload 身份匹配、archive 布局/元数据通过当前检查 profile、archive 内许可证与 vendor 清单已记录，以及未来可以在另行授权的隔离构建中精确选择该制品。它明确不证明或授权：

- 安装或执行工具；
- publisher detached signature 已验证；registry 没有为这些制品登记可验证的签名输入；
- host binary 可由 source 可复现地产生；
- checker 已实现、正确或已经通过真实 bundle；
- 其他 Go 平台制品、其他工具或跨平台结果等价；
- 任一具体再分发方案已经完成法律合规判断。

因此其余 Go 五个平台、Rust standalone 与其他 Rust 平台 payload 仍保持 `not-downloaded` / `not-accepted`。Rust 工具级依赖与许可证状态只升级为 `partial-accepted-set-only`，不把本批局部审阅外推到未观察归档；rustup distribution 也保持 `installation = not-authorized`。

## 复核入口

对已有归档重新产生观察（路径仅为示例，不会安装）：

```bash
python3 scripts/inspect-toolchain-tar.py \
  --archive /isolated/go1.26.7.darwin-arm64.tar.gz \
  --filename go1.26.7.darwin-arm64.tar.gz \
  --expected-sha256 020a1e8224811be75163e920bc77e0926a1390a6aeea19bdcf23f74b9d749f6d \
  --profile go1.26.7-darwin-arm64-host
```

Rust component 使用同一入口与精确 profile，例如：

```bash
python3 scripts/inspect-toolchain-tar.py \
  --archive /isolated/rustc-1.97.1-aarch64-apple-darwin.tar.xz \
  --filename rustc-1.97.1-aarch64-apple-darwin.tar.xz \
  --expected-sha256 6076cad38ccabaa24325f26a74080a363a2633a9cd34c473a8977255d8a593cb \
  --profile rust-1.97.1-rustc-aarch64-apple-darwin
```

生成由观察记录派生的 acceptance record、schema、contract 和负例：

```bash
python3 scripts/generate-toolchain-payload-acceptance.py --write
```

离线只读校验：

```bash
python3 scripts/generate-toolchain-payload-acceptance.py --check
```

除本 README 与 `observations/` 外，本目录文件由 acceptance 生成器维护。`observations/` 只能由已核对 publisher 摘要的精确归档通过登记检查器重新产生；仓库级校验验证其闭合结构、内部摘要、Go host/source 一致性、Rust profile 冻结事实和派生记录，但不会在没有外部 payload 时冒充重新检查归档原始字节。
