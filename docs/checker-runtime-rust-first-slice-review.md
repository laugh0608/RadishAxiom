# Checker runtime 首个 Rust 纵向切片审阅单

状态：已审阅，未授权实施
审阅日期：2026-08-30

## 目标与结论

本审阅单把 [ADR 0004](adr/0004-raxc-production-implementation-language.md)、[ADR 0011](adr/0011-checker-runtime-launcher-installation-and-activation.md) 和 [ADR 0012](adr/0012-product-checker-runtime-host-and-persistence-interface.md) 冻结的边界压缩为首个可提交、可测试的原生 Rust 纵向切片。它不是新的架构决策，也不授权下载、安装、执行、创建 Cargo workspace、生成 lockfile 或激活 runtime。

结论如下：

- 首个切片只创建一个内部 library crate `radishaxiom-checker-runtime`，不创建 `raxc` 空壳、公开 CLI、provider client、平台 facade 或第二套配置入口；
- 首个切片的 production dependencies 与 dev-dependencies 都保持为空，只依赖 Rust standard library；
- 首个真实路径只闭合 canonical launcher policy / registered-inactive record 的严格读取、身份重算、精确 target selection 和 qualification / product 两种选择语义；不在同一提交混入 distribution 下载、USTAR 安装、进程执行或系统隔离；
- 精确 Rust `1.97.1` 工具链的版本和当前 host / source publisher 摘要已经核对，但安装字节仍未验收；`rustup` component 路径与 registry 当前 standalone 路径也尚未统一，故工具链安装和 workspace 写入继续停止；
- 本机已有 Rust `1.96.0` 只能用于环境观察，不能生成本切片的 `Cargo.lock`、格式化结果、静态分析结果或验收证据。

## 工具链来源审阅

Rust 项目于 2026-07-16 发布 `1.97.1`，该 patch 修复了 `1.97.0` 随带 LLVM 的已知错误编译问题。项目继续使用 ADR 0004 已冻结的 `1.97.1`，不因 `1.98.0` 已发布而漂移。来源为 [Rust 1.97.1 发布说明](https://blog.rust-lang.org/2026/07/16/Rust-1.97.1/)与 [Rust 官方 dist](https://static.rust-lang.org/dist/2026-07-16/index.html)。

当前已从官方 `.sha256` sidecar 捕获、但尚未下载或接受的摘要为：

| 对象 | Publisher SHA-256 | 当前状态 |
| --- | --- | --- |
| `rust-1.97.1-aarch64-apple-darwin.tar.xz` | `c9748cc86107734a2a024069908a895de7caa2d37062fb641eef9f756938ace2` | `not-downloaded` / `not-accepted` |
| `rustc-1.97.1-src.tar.xz` | `0ed06fdaffd4722a7702e0b4eebfafc897ab8f513e8e1b247cdd7e5c6df6ded2` | `not-downloaded` / `not-accepted` |
| `channel-rust-1.97.1.toml` | `03569b1886ceb5c05276b50c8431ab111de944cd6140fe1fa7d821dd8e0f29cf` | 元数据已读；未作为 payload 接受 |

拟议的仓库 pin 为 `rust-toolchain.toml` 中精确 `channel = "1.97.1"`、`profile = "minimal"`，并显式加入 `rustfmt` 与 `clippy`，以同时形成编译、格式化和静态分析门禁。[rustup profile](https://rust-lang.github.io/rustup/concepts/profiles.html) 说明 minimal profile 只保证 `rustc`、`rust-std` 与 `cargo`；附加组件因此必须显式列出。[rustup override](https://rust-lang.github.io/rustup/overrides.html) 也说明 toolchain file 会让 Cargo 以固定 channel 运行。

这里存在一条尚未闭合的供应链边界：当前 Toolchain Registry 登记的是 standalone archive，而 `rustup` 会依据 channel manifest 下载 `rustc`、`cargo`、`rust-std`、`rustfmt`、`clippy` 等拆分 component。即使 rustup 内部校验通过，也不能把 standalone archive 的摘要或未来 acceptance 外推给另一组字节。实施前必须二选一并把实际安装路径写入机器登记：

1. 登记、下载并分别验收 rustup 实际使用的精确 component；或
2. 只从已登记且验收通过的 standalone archive 安装，并定义仓库如何稳定选择该工具链。

在这项选择完成前，不安装工具链、不创建 toolchain file，也不让 `Cargo.lock` 先于真实 `1.97.1` 生成。

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

首次获准写入时只创建以下结构：

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

在精确工具链与 workspace 获得授权后，首次实现至少通过：

- `cargo fmt --all --check`；
- `cargo clippy --workspace --all-targets --all-features -- -D warnings`；
- `cargo test --workspace --all-targets`；
- `cargo metadata --locked --format-version 1`，确认唯一成员、无外部 package 和 resolver `3`；
- `cargo tree --workspace --edges normal,build,dev`，确认没有第三方、build dependency 或 proc macro；
- 既有 Python launcher consistency tests 与 `./scripts/check-repo.sh`，形成跨实现同矩阵而不是让 Rust 自证；
- `git diff --check` 和工作区复核。

测试至少覆盖 policy / record 正例、duplicate / unknown / noncanonical JSON、摘要错配、unknown target、Rosetta / architecture mismatch、active-only 拒绝 inactive、qualification 接受精确 inactive、重复 target 和 ambiguous selection 失败关闭，以及上述 SHA-256 向量。通过这些动态和静态门禁只说明实现满足当前规范与测试，不升级为形式证明或 runtime activation。

## 下一次授权边界

下一连续动作仍是工具链 payload acceptance，而不是直接写 Rust 代码。执行前应向所有者说明并取得一次精确授权，范围包括：

- 选择 standalone 或 rustup component 安装路径，并把实际安装字节登记到 registry；
- 下载当前 macOS arm64 对应字节与 Rust source 到隔离临时目录，预计数百 MiB、数分钟到数十分钟；
- 重算 publisher SHA-256，只读检查 archive path / type / mode / link、组件 inventory、license / notice 和 source 对应关系；
- 将观察与 acceptance record 写入仓库，但不安装或执行工具链；
- 复核后删除临时下载副本；仓库改动可由单独提交回滚，临时字节删除后需重新下载。

只有 payload acceptance 通过，才另行授权工具链安装和本审阅单所列 workspace 写入。该后续安装会修改用户级 Rust toolchain 状态，workspace 会新增 Cargo 文件并由精确 `1.97.1` 生成 lockfile；回滚分别为卸载精确新增 toolchain 与回退该次 workspace 提交。两项授权不包含真实 checker distribution 下载 / 安装、payload 执行、系统配置修改、远程写入、push 或 `registered-inactive -> active`。
