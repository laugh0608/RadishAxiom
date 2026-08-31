# Checker runtime 首个 Rust 纵向切片审阅单

状态：首个零第三方依赖 Rust 纵向切片已实现并通过本地门禁
审阅日期：2026-08-31

## 目标与结论

本审阅单把 [ADR 0004](adr/0004-raxc-production-implementation-language.md)、[ADR 0011](adr/0011-checker-runtime-launcher-installation-and-activation.md) 和 [ADR 0012](adr/0012-product-checker-runtime-host-and-persistence-interface.md) 冻结的边界压缩为首个可提交、可测试的原生 Rust 纵向切片。工具链 payload 的隔离下载、只读验收和用户级安装已经分别授权并完成；2026-08-31 获得实现授权后，workspace、Cargo 生成 lockfile 与本单限定的产品代码已经物化。本单仍不授权真实安装、payload 执行、runtime 激活或远程动作。

结论如下：

- 首个切片已经只创建一个内部 library crate `radishaxiom-checker-runtime`，没有创建 `raxc` 空壳、公开 CLI、provider client、平台 facade 或第二套配置入口；
- production dependencies 与 dev-dependencies 均为空，只依赖 Rust standard library；crate 根使用 `#![forbid(unsafe_code)]`；
- 首个真实路径已经闭合 canonical launcher policy / registered-inactive record 的严格读取、完整闭合对象形状、域分离身份重算、typed native target，以及 qualification / product 两种 registration selection 语义；没有混入 distribution 下载、USTAR 安装、进程执行或系统隔离；
- 精确 Rust `1.97.1` 已选择 rustup `minimal` + 显式 `rustfmt` / `clippy` 路径；macOS arm64 的五个实际 component 与 source 已分别通过 publisher 摘要和只读归档验收，standalone archive 保持未接受；同一精确用户级工具链已安装并核对，仓库已写入 toolchain pin；
- 本机默认 Rust 与当前任务进程的 `RUSTUP_TOOLCHAIN` 覆盖仍为 `1.96.0`，只能用于环境观察；本切片的 lockfile 生成、格式化、静态分析、metadata、dependency tree 和测试均显式使用 `+1.97.1-aarch64-apple-darwin`，没有把 `1.96.0` 结果计入验收。

## 工具链来源审阅

Rust 项目于 2026-07-16 发布 `1.97.1`，该 patch 修复了 `1.97.0` 随带 LLVM 的已知错误编译问题。项目继续使用 ADR 0004 已冻结的 `1.97.1`，不因 `1.98.0` 已发布而漂移。来源为 [Rust 1.97.1 发布说明](https://blog.rust-lang.org/2026/07/16/Rust-1.97.1/)与 [Rust 官方 dist](https://static.rust-lang.org/dist/2026-07-16/index.html)。

当前机器登记与验收状态为：

| 对象 | Publisher SHA-256 | 当前状态 |
| --- | --- | --- |
| `cargo-1.97.1-aarch64-apple-darwin.tar.xz` | `2d84a74e9558192a7de674aca6aa3ab7464bed2df97e0377156ddb7e09a0fd7a` | `accepted-for-controlled-build-input` |
| `clippy-1.97.1-aarch64-apple-darwin.tar.xz` | `5e44c0ac5ca9b6f14a3c9031a61f583348b902f908f46e95717aef1dbd2807db` | `accepted-for-controlled-build-input` |
| `rust-std-1.97.1-aarch64-apple-darwin.tar.xz` | `a4895f5c6995e83cab8687e46b14324592398049def71ce75ca308c981cf200d` | `accepted-for-controlled-build-input` |
| `rustc-1.97.1-aarch64-apple-darwin.tar.xz` | `6076cad38ccabaa24325f26a74080a363a2633a9cd34c473a8977255d8a593cb` | `accepted-for-controlled-build-input` |
| `rustfmt-1.97.1-aarch64-apple-darwin.tar.xz` | `358bbba5d0c7c37116ec15f67cfd3ac4da5d3c319cddb49389c26d3a0c65747a` | `accepted-for-controlled-build-input` |
| `rustc-1.97.1-src.tar.xz` | `0ed06fdaffd4722a7702e0b4eebfafc897ab8f513e8e1b247cdd7e5c6df6ded2` | `accepted-for-controlled-build-input` |
| `rust-1.97.1-aarch64-apple-darwin.tar.xz` | `c9748cc86107734a2a024069908a895de7caa2d37062fb641eef9f756938ace2` | standalone；`not-downloaded` / `not-accepted` |
| `channel-rust-1.97.1.toml` | `03569b1886ceb5c05276b50c8431ab111de944cd6140fe1fa7d821dd8e0f29cf` | component URL / 摘要 / profile 的 publisher 元数据绑定 |

仓库 pin 已在 `rust-toolchain.toml` 中精确使用 `channel = "1.97.1"`、`profile = "minimal"`，并显式加入 `rustfmt` 与 `clippy`，以同时形成编译、格式化和静态分析门禁。[rustup profile](https://rust-lang.github.io/rustup/concepts/profiles.html) 说明 minimal profile 只保证 `rustc`、`rust-std` 与 `cargo`；附加组件因此必须显式列出。[rustup override](https://rust-lang.github.io/rustup/overrides.html) 也说明 toolchain file 会让 Cargo 以固定 channel 运行。调用环境若显式设置 `RUSTUP_TOOLCHAIN`，该环境变量会覆盖仓库文件；正式门禁必须读取实际 `rustc` / `cargo` 身份，不能只从文件存在推断工具版本。

供应链路径已经选择 rustup component，并在 Toolchain Registry 中把 channel manifest、target、profile、显式组件和五个精确归档分别登记。只读验收没有执行归档内程序：component 都没有 link / hardlink / 特殊文件；source 的 148 个 symlink 均解析在同一顶层内，4,613 份 `Cargo.toml`、1,977 份 `Cargo.lock` 与两套许可证元数据只作为库存记录。Rust 主项目仍记录为 `MIT OR Apache-2.0`，但 source 中的 LLVM exception、Unicode、OFL、GPL / GCC exception 等表达式不被错误归并为双许可证，也不构成任一具体分发的法律结论。

standalone archive 继续保持独立的 `not-downloaded` / `not-accepted` 候选，不能替代或扩张本次 component acceptance。验收批次本身没有安装工具链或创建 toolchain file；随后获准的用户级安装也没有创建 Cargo workspace 或 `Cargo.lock`。

## 用户级安装复核

2026-08-30 经单独授权，当前用户 rustup 安装了 `1.97.1-aarch64-apple-darwin`，最终组件清单严格为：

- `cargo-aarch64-apple-darwin`；
- `clippy-aarch64-apple-darwin`；
- `rust-std-aarch64-apple-darwin`；
- `rustc-aarch64-apple-darwin`；
- `rustfmt-aarch64-apple-darwin`。

实际工具身份为 `rustc 1.97.1 (8bab26f4f 2026-07-14)`、`cargo 1.97.1 (c980f4866 2026-06-30)`、`rustfmt 1.9.0-stable` 和 `clippy 0.1.97`。下载恢复期间只使用官方 `2026-07-16` dist URL 的连续 Range；五个组件整包 SHA-256 全部重新匹配上表及版本化 acceptance record 后才进入 rustup 安装。安装后默认工具链仍为 `1.96.0-aarch64-apple-darwin`；本切片随后新增仓库 toolchain file，但没有修改用户默认工具链、shell 或系统配置。中断残片和隔离临时目录均已删除。

这是一台开发主机上的用户级可用性观察，不是可移植安装 receipt、CI / 六平台证据或 checker runtime 安装。Toolchain Registry 的 `installation = not-authorized` 继续表达 payload acceptance 批次本身不授予安装权限，不作为本机 rustup inventory；当前可变主机状态只在本审阅单和[当前状态](status/current.md)中记录。

## 候选依赖审阅

身份重算需要 SHA-256，但 Rust standard library 不提供 SHA-256。审阅过 `sha2 = "=0.11.0"` 且 `default-features = false` 的方案：2026-08-30 依据 crates.io sparse index 在 macOS arm64 上观察到九个 production packages。所有下载到隔离临时目录的 `.crate` 字节都与 index checksum 匹配，manifest 均声明 `MIT OR Apache-2.0`；审阅后临时副本已删除，未执行 crate code，也没有生成 lockfile。

| Package | 观察版本 | crates.io checksum |
| --- | --- | --- |
| `sha2` | `0.11.0` | `446ba717509524cb3f22f17ecc096f10f4822d76ab5c0b9822c5f9c284e825f4` |
| `cfg-if` | `1.0.4` | `9330f8b2ff13f34540b44e946ef35111825727b38d33286ef986142615121801` |
| `cpufeatures` | `0.3.1` | `5ca28b0ae3115b884660db4118d803791fd6756b6e88f39c0f3f7859060d7566` |
| `libc` | `0.2.189` | `3eaf3ede3fee6db1a4c2ee091bf8a8b4dccdc6d17f656fb07896ee72867612f2` |
| `digest` | `0.11.3` | `f1dd6dbb5841937940781866fa1281a1ff7bd3bf827091440879f9994983d5c2` |
| `block-buffer` | `0.12.1` | `d2f6c7dbe95a6ed67ad9f18e57daf93a2f034c524b99fd2b76d18fdfeb6660aa` |
| `crypto-common` | `0.2.2` | `ce6e4c961d6cd6c9a86db418387425e8bdeaf05b3c8bc1411e6dca4c252f1453` |
| `hybrid-array` | `0.4.14` | `707114b52a152fa7bdb290cd7cd5912d9467273b6d74e21b8d81aca1f8533f6b` |
| `typenum` | `1.20.1` | `b6f5e870be6c3b371b77fe0ee0bafb859fa4964b4404c27de1d380043c4dda20` |

这只是当日 resolution snapshot，不是 Cargo 生成的依赖锁。`sha2` 对 `cpufeatures` 的 target dependency 会在 Apple arm64 路径继续引入 `libc`；`libc` 含 `build.rs` 并承载平台 FFI / `unsafe` 边界。对于当前只做内容身份、没有 secret 或 constant-time 要求的窄切片，这个依赖面大于功能面，暂不引入。

首个切片改用项目自有、safe Rust 的小型 SHA-256 模块。它只接受字节并返回 32-byte digest / 小写 hex，不暴露通用密码学 API，不使用 `unsafe`、SIMD、CPU feature detection、FFI 或 build script。风险通过 NIST 已知向量、空串、`abc`、55 / 56 / 63 / 64-byte padding 边界、million-`a` 和既有 Python fixture 的交叉结果覆盖。若后续需要硬件加速或广义密码学能力，必须重新提交依赖审阅，不能把本次拒绝默认为永久禁用第三方 crate。

严格 JSON 同样不引入 `serde` / `serde_json`。首个 parser 只实现当前 policy / record 实际使用的闭合 canonical JSON 子集：UTF-8 ASCII key、string、boolean、array、object；拒绝 duplicate member、unknown member / version、number、`null`、非 canonical escape、非 ASCII、尾随字节和非规范 member 顺序。它不扩展成公共 JSON 库。

## 最小 workspace 与 crate 边界

本切片获准后只创建以下结构：

```text
Cargo.toml
Cargo.lock
rust-toolchain.toml
crates/checker-runtime/
  Cargo.toml
  src/
    lib.rs
    canonical.rs
    policy.rs
    registration.rs
    selection.rs
    sha256.rs
```

根 `Cargo.toml` 是 virtual workspace，Rust 2024 edition 显式使用 [resolver `3`](https://doc.rust-lang.org/stable/edition-guide/rust-2024/cargo-resolver.html)。crate 设置 `publish = false`，默认禁止 `unsafe`，不声明 feature、binary、build script、外部依赖或网络能力。只有出现第二个真实生产 crate 时才抽取 workspace package metadata；不为未来可能的 `raxc` 预建空层。

首个 public-to-crate 行为闭合如下：

1. 读取仓库现有 canonical `launcher-policy.jcs` 与 registered-inactive record bytes；
2. 严格解析并重算各自 domain-separated SHA-256 身份；
3. 接受产品注入的 typed native host identity，不自行猜测 Rosetta、路径或环境；
4. qualification 路径只允许精确匹配的 `registered-inactive` target，product 路径仍只允许 active record；
5. 返回 typed selection / rejection，不返回“已验证”布尔值，也不把 inactive、unknown target、identity mismatch 或 parser failure 降级为 fallback。

该切片不读网络、不写安装根、不解压 archive、不生成 receipt、不 spawn checker。后续 store / USTAR / receipt、single result consumer、process / identity observation 和平台隔离分别作为真实纵向切片进入，避免一个首次提交同时跨越解析、文件事务与进程边界。

## 验证门禁

首次实现的门禁为：

- `cargo fmt --all --check`；
- `cargo clippy --workspace --all-targets --all-features -- -D warnings`；
- `cargo test --workspace --all-targets`；
- `cargo metadata --locked --format-version 1`，确认唯一成员、无外部 package 和 resolver `3`；
- `cargo tree --workspace --edges normal,build,dev`，确认没有第三方、build dependency 或 proc macro；
- 既有 Python launcher consistency tests 与 `./scripts/check-repo.sh`，形成跨实现同矩阵而不是让 Rust 自证；
- `git diff --check` 和工作区复核。

测试至少覆盖 policy / record 正例、duplicate / unknown / noncanonical JSON、摘要错配、unknown target、Rosetta / architecture mismatch、active-only 拒绝 inactive、qualification 接受精确 inactive、重复 target 和 ambiguous selection 失败关闭，以及上述 SHA-256 向量。通过这些动态和静态门禁只说明实现满足当前规范与测试，不升级为形式证明或 runtime activation。

2026-08-31 的实际结果为：精确 `rustc 1.97.1` / `cargo 1.97.1` 下 `cargo fmt --all --check`、`clippy -D warnings`、13 项 Rust test、locked / offline metadata 与 dependency tree 全部通过；metadata 只有唯一 library package、Rust 2024、resolver `3`、零 dependency / feature。既有 Python launcher oracle 19 项测试、checker runtime payload 34 个生成文件和仓库级 935 文件门禁同时通过。真实 policy / record 的既有 Python 域摘要作为跨实现 fixture 被 Rust 独立重算匹配；这些结果仍不是形式证明、安装证据、runtime companion、跨平台证据或 active runtime。

## 下一次授权边界

首个 workspace / identity / selection 切片已经完成。下一连续实现应在重新审阅后，从严格 outer / inner archive inventory、installation receipt 与 store transaction 中选择一个仍可独立验收的真实切片；不得把它们与 result consumer、subprocess、平台资源隔离或真实安装一次性混合。若下一切片需要第三方 crate、build script、proc macro、native code、网络能力或新的平台适配，必须先重新完成依赖与授权审阅。

后续实现仍不自行授权真实 checker distribution 下载 / 安装、checker payload 执行、系统配置修改、远程写入、push 或 `registered-inactive -> active`。当前 policy 继续保持 `specified-not-implemented`、active runtime 继续为 0：本切片只实现其中的 registry input、身份和 registration selection 前段，不能冒充完整 installer / launcher。

后续状态：同日已按该停止线完成下一项[严格 USTAR 切片](checker-runtime-rust-ustar-slice-review.md)；receipt、store、result consumer、subprocess、真实安装与激活仍未由本单授权或实现。
