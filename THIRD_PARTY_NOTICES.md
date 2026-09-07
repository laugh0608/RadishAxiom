# RadishAxiom 第三方依赖记录

本文件记录进入 RadishAxiom 生产构建图的第三方依赖。Cargo lockfile 是精确解析结果；本文件补充用途、来源、许可证、构建与分发边界。项目原创内容继续以根 `LICENSE` 的 Apache-2.0 授权，第三方组件保留各自授权。

## `libc 0.2.189`

| 字段 | 记录 |
| --- | --- |
| 用途 | 只为 macOS 私有 `radishaxiom-checker-runtime-darwin-store` crate 提供 Darwin 文件系统 FFI 与 ABI 类型 |
| crates.io package | `libc 0.2.189`，exact requirement `=0.2.189` |
| crates.io checksum | `3eaf3ede3fee6db1a4c2ee091bf8a8b4dccdc6d17f656fb07896ee72867612f2` |
| 上游 | <https://github.com/rust-lang/libc> |
| 许可证 | `MIT OR Apache-2.0`；crate 内含 `LICENSE-MIT` 与 `LICENSE-APACHE` |
| Rust 基线 | edition 2021，MSRV 1.65；由仓库精确 Rust 1.97.1 构建 |
| features | `default-features = false`，只启用 `std` |
| 传递依赖 | 当前目标与 features 下为 0；可选 `rustc-std-workspace-core` 未启用 |
| build script | 有；读取 Cargo / target / Rust 配置，运行受 Cargo 指定的 `rustc --version`，按目标发出 `cfg` / `check-cfg`；macOS 路径不编译 C/C++、不下载、不联网 |
| proc macro / native code | 无 proc macro；crate 是 raw Rust FFI binding，不随项目编译或嵌入第三方 C/C++ 源码，运行时调用系统 `libSystem` |
| `unsafe` 边界 | binding 自身包含平台 `unsafe` 声明；项目侧调用只允许位于私有 Darwin store crate，core crate 继续 `#![forbid(unsafe_code)]` |
| 替代方案 | 标准库缺少所需 `renameatx_np`、descriptor inventory 与 `F_FULLFSYNC`；手写完整 ABI、自建 C shim 和较大通用文件系统依赖均被审阅拒绝 |
| 分发影响 | 产品分发必须保留本记录以及上游所选许可证文本；生成代码、用户程序和 checker payload 不链接或嵌入该 crate |
| 验收日期 | 2026-09-01 |

本次验收以本机 Cargo registry cache 中的 exact `.crate`、规范化 / 原始 manifest、两份许可证和完整 `build.rs` 为输入；历史候选记录不替代本次 checksum 与内容复核。
