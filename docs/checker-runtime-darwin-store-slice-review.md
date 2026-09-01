# Checker runtime Darwin store 生产切片审阅单

状态：policy `0.3`、exact `libc`、私有 Darwin crate、descriptor-backed core 与原生进程矩阵已实现；真实产品安装仍未授权
实施日期：2026-09-01

## 交付结论

本切片在 [Darwin 生产文件系统边界审阅](checker-runtime-darwin-filesystem-review.md)的精确授权内完成四项工作：迁移机器 policy、重新验收唯一第三方 binding、实现窄 `unsafe` / FFI 平台 crate，并在合成临时根运行真实独立进程的并发与 crash recovery。它没有读取产品安装根、下载 / 安装 / 执行 checker、写 qualification / attempt、激活 runtime、修改远程状态或 push。

canonical launcher policy 已从 `0.2` 升级为 `0.3`，摘要域为 `radishaxiom.checker-runtime-launcher-policy.v0.3`，当前 policy digest 为 `sha256:4c4943002d6c0199d834d3e3361c8bca0cf1329137985a009d3b2b270d5b705c`。新增闭合事实包括：

- exact `libc 0.2.189` 的 crates.io checksum、`MIT OR Apache-2.0`、上游 build script 与无项目 C shim 边界；
- 唯一 `publish = false`、macOS-only 的 `radishaxiom-checker-runtime-darwin-store`；
- `unsafe` 只存在于平台 crate，core `radishaxiom-checker-runtime` 继续 `#![forbid(unsafe_code)]`；
- descriptor-relative no-follow containment、三 flags `renameatx_np` exclusive publication、文件 / 目录 `F_FULLFSYNC` 和无较弱 fallback。

policy schema、集合 contract、launcher 负例、Python oracle 与 Rust strict parser 已同步。新增负例拒绝未审阅依赖、core `unsafe`、较弱文件系统 fallback 和 superseded `0.2`。两份 Checker Runtime Payload Registration `v0.1` record 不包含 launcher policy 身份，迁移前后 SHA-256 分别保持：

- current registered-inactive：`ec0c5408e2ae0f840b450c0b64ee8a91831a44e916760698fcc9dd87c61bfa13`；
- historical-ineligible：`46953307393ed81393c80f93d36d93c0f6e2cee7509f2657b51c5afa1a1ee0a1`。

## 依赖与供应链边界

本机 Cargo registry cache 已存在 exact `libc-0.2.189.crate`，本次没有联网下载。重新计算的 `.crate` SHA-256 为 `3eaf3ede3fee6db1a4c2ee091bf8a8b4dccdc6d17f656fb07896ee72867612f2`，与 crates.io index / policy 候选事实一致。完整检查规范化与原始 manifest、`LICENSE-MIT`、`LICENSE-APACHE` 和 `build.rs` 后确认：

- 当前 target / feature 图只有 `libc 0.2.189` 一个 registry package，传递依赖为 0；
- `default-features = false`，只启用 `std`；没有 proc macro，也不编译或嵌入第三方 C/C++；
- upstream `build.rs` 读取 Rust / Cargo / target 配置、运行 Cargo 指定的 `rustc --version` 并发出 `cfg` / `check-cfg`；macOS 路径不下载、不联网；
- 运行时 FFI 指向系统 `libSystem`；生成代码、用户程序和 checker payload 不链接或嵌入该 crate。

完整归属与分发记录见根 [第三方依赖记录](../THIRD_PARTY_NOTICES.md)。Cargo version 4 lockfile 由精确 `1.97.1` 在 offline 模式生成，没有手工编辑。

## 平台 crate 与 core 边界

私有平台 crate 只暴露 `Directory`、`RegularFile`、`Entry` 和保留原始 OS error 的 `PlatformError`。16 个有安全注释的 `unsafe` block 只承担以下 ABI 边界：

- `open` / `openat` / `mkdirat` / `unlinkat`；
- `fdopendir` / `rewinddir` / `readdir` / `closedir` 与 Darwin thread-local errno；
- `renameatx_np(RENAME_EXCL | RENAME_NOFOLLOW_ANY | RENAME_RESOLVE_BENEATH)`；
- `fcntl(F_FULLFSYNC)`、`geteuid` 和成功 syscall descriptor 的唯一所有权接管。

所有相对 API 只接受单个 portable component。directory inventory 从持有的 descriptor 枚举，每个 entry 再相对于父 descriptor 打开并检查实际 file type；special file、symlink、hard link、mode 或 inventory 漂移失败关闭。recursive cleanup 只从 exact owned staging directory capability 向下执行，不接受 absolute path 或调用方裸 fd。

根 capability 是唯一绝对路径入口：它要求 absolute / canonical、当前有效 UID 所有、`0700`、非 symlink，并比较打开前后的 device / inode / owner / mode。当前 `libSystem` 对 absolute `open + O_NOFOLLOW_ANY` 和 `openat + O_NOFOLLOW | O_NOFOLLOW_ANY` 返回 `EINVAL`；因此 root acquisition 使用 leaf `O_NOFOLLOW` + 前后身份复核，root 之后的每个 relative lookup 单独使用 `O_NOFOLLOW_ANY`。此兼容结论来自失败测试后的收敛，不把去掉后续 no-follow 当作 fallback。

macOS 上的 core `FilesystemStore` 已切换到 descriptor capability；旧 path-based Unix 逻辑只在 `not(target_os = "macos")` 下保留为未升级的平台候选。Darwin publication 状态机顺序为：

1. descriptor-relative exclusive create、写入、mode / 内容验证和每文件 `F_FULLFSYNC`；
2. exact staging inventory / receipt / executable / tree digest 重读；
3. staging tree 与 staging / final parent chain 自内向外 `F_FULLFSYNC`；
4. 单次三 flags exclusive rename；
5. final parent 与原 staging parent `F_FULLFSYNC`；
6. 从 final parent descriptor 重新打开并 exact verify，才返回 `Published`。

已有 destination 只在完整 verification 相同时返回 `Reused`，并在返回前重新同步 final parent；mismatch 保留 staging 且不覆盖。rename 后、parent sync 前的崩溃由下一次 exact publish 重放为 final re-sync + `Reused`，不从目录存在直接推断 installed-inactive。

## 原生验证结果

平台 crate 的直接测试覆盖 descriptor tree create / inventory / read / recursive cleanup、三 flags no-replace rename 的 `EEXIST` 且 source 保留，以及 intermediate symlink 的 `ELOOP`。core 原有 28 项测试全部在新的 Darwin backend 上重放，tree digest 继续与 Python oracle 相同。

新增 test-only 独立进程 helper 和两项矩阵测试覆盖：

- staging create、binary full-sync、receipt full-sync、staging verified 后直接退出；后继持锁者只删除 exact owned staging，final slot 不存在；
- exclusive rename 返回后、parent sync 完成后、完整 publication 返回后退出；后继 exact publish 只返回 `Reused`，原 transaction staging 已不存在；
- 两个独立进程并发发布同一字节，一个 `Published`、一个等待真实 OS 锁后 `Reused`；
- 持锁进程被 kill 后，OS 释放锁，后继进程重新取得；
- destination mismatch 不覆盖、symlink leaf / ancestor、hard link、mode / inventory 漂移继续失败关闭。

当前本机没有第二个可安全挂载的合成 filesystem，因此没有制造真实 `EXDEV`；实现会比较 staging / final parent device，并将 `renameatx_np` 的 `EXDEV` 映射为 `cross-filesystem-publication`，但这仍是代码与单 volume 观察，不是跨 volume 运行证据。进程 crash 测试也不冒充物理断电证明；`F_FULLFSYNC` 成功仍是 kernel / filesystem / hardware 边界内的 best-effort observation。

## 停止线与下一入口

本切片关闭了当前 Darwin slot store 的 path-based TOCTOU、非原子 no-replace 与目录持久化实现缺口，但没有完成整个 launcher policy。`checker-runtime-store-v0.1` 仍缺 `create_qualification_exclusive` 与 `append_attempt` 的生产持久化；两层业务 manifest parser、result consumer、spawn / isolation、真实产品根选择、immutable asset fetch / install、payload execution、qualification 和 activation 仍分别验证、分别授权。

下一连续本地切片优先实现 store 的 qualification / attempt 两项剩余能力，继续只使用合成临时根；真实 checker 安装仍须单独授权。

后续状态：同日已按该停止线完成 [qualification / attempt store 切片](checker-runtime-evidence-store-slice-review.md)。本文件保留 Darwin slot store 完成时的历史范围，不把后续 40 项 core 测试追溯写成本切片证据。
