# Toolchain & Adapter Identity Registry v0.1

本目录把 ADR 0004–0008 已冻结的生产工具链、独立 checker 工具链、验证后端、目标运行时和执行 profile 物化为可复算身份清单。它固定：

- Rust `1.97.1` 与 Rust 2024 edition 的首个生产工具链基线；
- Go `go1.26.7` 与六平台独立 checker 构建基线；
- cvc5 `1.3.4` 六个平台的官方 non-GPL static 候选制品；
- Node.js `24.19.0` 六个平台的官方归档候选制品；
- cvc5、Node、production pipeline、Rust build、Go checker build 与独立 checker 的稳定 profile 身份和禁止 fallback 边界；
- 官方元数据来源、publisher 记录的 SHA-256、源码归档、依赖审阅目标、许可证来源和 profile 对应 ADR 的原始摘要绑定。

`registry.json` 与 `schemas/` 由生成器维护。Go `go1.26.7` 的 `macos-arm64` host/source，以及 Rust `1.97.1` macOS arm64 rustup 的 `rustc`、`cargo`、`rust-std`、`rustfmt`、`clippy` 与 source，已经分别绑定 [Toolchain Payload Acceptance v0.1](../toolchain-payload-acceptance-v0.1/README.md) 记录，状态为 publisher 摘要匹配、`toolchain-tar-v0.1` archive 检查通过和 `accepted-for-controlled-build-input`。这些结论不表示安装、执行、签名验证、源码可复现构建或 checker / compiler 正确性。

其余 Go 五个平台、Rust standalone / 其他平台以及 cvc5、Node 的全部制品仍明确为 `not-downloaded`、`not-performed` 和 `not-accepted`；不因工具版本相同、source 或相邻平台已经验收而外推。Rust rustup distribution 单独绑定 `channel-rust-1.97.1.toml` 的原始摘要、`2026-07-16` channel date、manifest version `2`、`minimal` profile、`aarch64-apple-darwin` target 和两个显式 quality component，且保持 `installation = not-authorized`。Rust 工具级依赖与许可证审阅只标记为 `partial-accepted-set-only`，source 中观察到的多种 SPDX 表达式不是整包许可证结论。

cvc5 adapter、Node invocation 与独立 checker 的允许参数、资源限制、进程失败边界和 certificate 空能力停止线由 [Execution Profile Contract v0.1](../execution-profiles-v0.1/README.md) 统一物化。registry 中的 `specified-not-materialized` 只表示这些 profile 已有机器规范但尚无实现或运行证据；Go 两个 payload 的供应链验收也不会把 profile 升级为已实现或已运行。

Rust 首次实现选择 `1.97.1`，不自动采用 2026-08-20 刚发布的 `1.98.0`。`1.97.1` 是已经发布一个月且修复已知 LLVM miscompilation 的 stable patch；这只是首个可审阅基线，不形成未来 stable release 的兼容承诺。

首个 Rust 纵向切片的工具链、候选依赖、零第三方依赖决策、crate 边界与后续授权停止线见 [Checker runtime 首个 Rust 纵向切片审阅单](../../docs/checker-runtime-rust-first-slice-review.md)。standalone archive 与 rustup component 继续是不可互换的字节链；component acceptance 完成后，下一动作仍须单独授权工具链安装，之后才单独授权 workspace / lockfile 写入。

生成：

```bash
python3 scripts/generate-toolchain-adapter-identities.py --write
```

只读校验：

```bash
python3 scripts/generate-toolchain-adapter-identities.py --check
```

除本 README 外，本目录文件均由生成器维护，不接受手工修改。生成器校验登记内容、排序、引用、摘要形状、平台覆盖，以及仅允许两个精确 Go 制品、五个精确 Rust component 和一个 Rust source 引用版本化验收记录的停止线；它不是下载器、安装器、签名验证器、SBOM、Rust / Go 构建器、cvc5 adapter 或 Node launcher。
