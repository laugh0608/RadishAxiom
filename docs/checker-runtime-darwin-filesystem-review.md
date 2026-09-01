# Checker runtime Darwin 生产文件系统边界审阅单

状态：Darwin 原语、威胁模型、依赖方向与原生测试矩阵已审阅；policy 迁移、第三方依赖和 `unsafe` 实现尚未授权
审阅日期：2026-09-01

## 目标与结论

本审阅承接 [Rust store 最小事务切片](checker-runtime-rust-store-slice-review.md)，只回答生产 `FilesystemStore` 如何关闭当前 cooperative lock + path-based rename 的已知边界。它不实现平台适配，不修改 Cargo dependency / lockfile，不改变 launcher policy 字节，不读取产品安装根，不安装或执行 checker，也不授权 qualification、激活或远程动作。

结论如下：

- Rust `1.97.1` 标准库能够提供文件锁、普通文件 I/O 和 `fsync`，但没有完整暴露 Darwin 的 descriptor-relative lookup、目录枚举、no-replace rename 和 full-sync 控制；只在现有 `store.rs` 上增加更多 path-based precheck 不能关闭检查与使用之间的竞态；
- 当前 macOS SDK 已提供足够的原生能力：`openat` / `mkdirat` / `unlinkat`、`O_NOFOLLOW_ANY`、`renameatx_np` 与 `RENAME_EXCL | RENAME_NOFOLLOW_ANY | RENAME_RESOLVE_BENEATH`，以及 `F_FULLFSYNC` / `F_BARRIERFSYNC`；不支持这些语义的 volume 或系统只能返回 `runtime-unavailable` / `installation-failed`，不得回退到普通 rename；
- 不接受在 core 内手写完整 Darwin `dirent` / syscall ABI，也不接受自建 C shim / build script 或更大的通用 filesystem facade；推荐新增一个 `publish = false` 的私有 `radishaxiom-checker-runtime-darwin-store` crate，以精确版本 `libc` 提供平台 ABI，只向仍保持 `#![forbid(unsafe_code)]` 的 core 暴露窄的安全 capability；
- 当前 `launcher-policy.jcs` `0.2` 明确声明 `dependency_status = reviewed-zero-third-party-not-authorized`。引入 `libc` 会改变闭合必需事实，因此实现前必须先将 policy 显式迁移到新版本并重算摘要链，不能让代码事实与 `0.2` 机器声明漂移；
- 当前产品最低 macOS 版本尚未冻结。SDK 声明 `openat` 从 macOS 10.10、`renameatx_np` 从 macOS 10.12 可用，但新 no-follow / resolve flags 的完整兼容矩阵尚未形成；实现必须同时提供运行时 capability probe，并在产品支持矩阵冻结前拒绝把当前开发机观察扩大为所有 macOS arm64 主机证据。

## 一手接口与本机观察

审阅使用精确 `rustc 1.97.1 (8bab26f4f 2026-07-14)`、Xcode `26.6` build `17F113` 与 macOS SDK `26.5`。SDK 头文件直接确认：

- `usr/include/sys/stdio.h`：`renameatx_np`、`RENAME_EXCL = 0x00000004`、`RENAME_NOFOLLOW_ANY = 0x00000010`、`RENAME_RESOLVE_BENEATH = 0x00000020`；
- `usr/include/sys/fcntl.h`：`O_NOFOLLOW`、`O_DIRECTORY`、`O_CLOEXEC`、`O_NOFOLLOW_ANY`、`AT_SYMLINK_NOFOLLOW_ANY`、`AT_RESOLVE_BENEATH`、`F_FULLFSYNC` 与 `F_BARRIERFSYNC`；
- `usr/include/sys/stat.h` / `sys/unistd.h`：`fstatat`、`mkdirat`、`readlinkat` 与 `unlinkat`。

Apple 对 [`fsync`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fsync.2.html) 的说明明确区分“提交给设备”和断电后的真实持久化，并建议需要更强顺序保证时使用 [`F_FULLFSYNC`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fcntl.2.html)。即使 `F_FULLFSYNC` 成功也只能记录 best-effort durability observation，不能声称对任意硬件形成断电证明。

只在自动清理的测试临时目录中通过 Python `ctypes` 直接调用当前主机 `libSystem`，观察到：

| 观察 | 结果 |
| --- | --- |
| `renameatx_np` 使用三项 flags 首次发布目录 | 成功 |
| 已有 destination 时再次 `RENAME_EXCL` | `EEXIST (17)`，source 保留 |
| `openat` 穿过中间 symlink 且使用 `O_NOFOLLOW_ANY` | `ELOOP (62)` |
| 普通文件 `fsync` / `F_BARRIERFSYNC` / `F_FULLFSYNC` | 全部成功 |
| 目录 descriptor `fsync` / `F_BARRIERFSYNC` / `F_FULLFSYNC` | 全部成功 |

这些探针没有写仓库、没有保留二进制或临时目录。它们只证明当前开发主机与当前 volume 接受这些调用；没有形成 volume 类型、最低 OS、其他文件系统、系统崩溃或物理断电证据。

## 威胁与可信边界

生产 store 首版按以下边界成立：

- 信任产品注入的根 descriptor、Darwin kernel / libc、实际 filesystem 对已接受 syscall 的语义，以及极小平台 wrapper；根必须由产品适配层创建并核对为当前用户拥有的 `0700` 本地私有目录；
- 防御损坏或恶意构造的目录项、遗留 staging、符号链接 / 硬链接、mode / inode 漂移、多个产品进程和在 publication 窗口抢占 destination 的非协作写者；这些情况只能得到精确失败或 exact reuse，不能覆盖已有 slot、越出根或形成安装成功；
- 同 UID 的任意恶意进程在 DAC 权限模型下始终可以在 publication 之后直接篡改用户拥有的文件。store 通过 descriptor-relative 操作、exact read 和后续 spawn 前后身份检查降低竞态并检测漂移，但不声称能对同 UID 攻击者形成不可修改存储；若产品要求这种保护，必须以权限分离、sandbox 或签名执行边界重新评估 ADR 0012；
- root / 内核攻击者、filesystem 违反已报告 syscall 语义和绝对物理断电保证不在本切片可证明范围内。远程或不支持所需能力的 volume 不建立兼容 fallback。

## 推荐的 crate 与原语边界

推荐新增的 Darwin crate 只允许以下职责：

1. 以 `openat` 和单个 portable component 逐层打开 directory / file capability，使用 `O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW`，对需要多组件 lookup 的入口额外要求 `O_NOFOLLOW_ANY`；
2. 使用 `fdopendir` / `readdir` 的 descriptor inventory，并将每个 entry 再相对于已持有的父目录 descriptor 打开；不把 `F_GETPATH` 后的字符串交回 `std::fs::read_dir` 作为可信 lookup；
3. 使用 `O_CREAT | O_EXCL` 创建文件，返回拥有 fd 的 Rust 类型；mode、link count、device / inode 与内容验证继续由 core 的 typed state 消费；
4. 使用 `renameatx_np` 和 `RENAME_EXCL | RENAME_NOFOLLOW_ANY | RENAME_RESOLVE_BENEATH` 发布单个 staging directory；`EEXIST` 只进入 exact final read / reuse，`EXDEV`、`ELOOP`、`EINVAL`、`ENOTSUP` 或未知错误均失败关闭；
5. 使用 `unlinkat` 从持有的 directory descriptor 递归清理 exact owned staging；不接受 absolute path、裸 fd、调用方 transaction 字符串之外的删除目标；
6. 对文件与目录提供明确的 full-sync 操作，并保留原始 `io::Error`；不把 `fsync` 或 `F_BARRIERFSYNC` 静默当作 `F_FULLFSYNC` 成功。

core crate 继续禁止 `unsafe`；平台 crate 只在调用 `libc` 和接管 / 释放 raw fd 的最小函数内使用有注释的 `unsafe` block，并启用 `unsafe_op_in_unsafe_fn`、Clippy 与 macOS-only 单元 / 进程测试。它不暴露 CLI、网络、provider、canonical codec、registration 或产品路径发现能力。

`libc 0.2.189` 已在 2026-08-30 的 SHA-256 候选依赖审阅中记录 crates.io checksum `3eaf3ede3fee6db1a4c2ee091bf8a8b4dccdc6d17f656fb07896ee72867612f2` 与 `MIT OR Apache-2.0`；[Rust 上游当前 `std` manifest](https://github.com/rust-lang/rust/blob/main/library/std/Cargo.toml) 也引用同一版本。该旧观察不自动授权安装：实现前仍须重新取得 exact `.crate`、核对 index checksum、source / manifest / license / build script、生成 Cargo lockfile，并记录第三方归属。当前 `libc` 暴露 `renameatx_np`、`RENAME_EXCL`、`O_NOFOLLOW_ANY`、`F_FULLFSYNC` 和 Darwin ABI，但尚未暴露 SDK 26.5 的全部新 rename / `AT_*` flags；平台 crate 只能以本机 SDK 与 Apple 开源来源核对后的极小常量补充，不能复制通用头文件。

## Publication 持久化顺序

实现必须把以下顺序变成可注入故障的状态机：

1. exclusive create、写入、设定 mode、重读并验证每个文件；
2. 对每个文件执行 full-sync，失败则保持 owned staging；
3. 从最内层目录到 staging root 同步目录 metadata，再同步 staging parent；
4. 以三项 rename flags 执行唯一 publication syscall；
5. 同步 final parent 与原 staging parent，任一失败都返回“publication durability unknown”，不得直接形成 installed-inactive 成功；
6. 从 final parent descriptor 重新打开最终 slot，重放 exact inventory / receipt / binary / tree digest；只有重新验证与持久化观察都通过才返回 `Published`。

既有 final slot 的 exact reuse 不修改 slot；删除 owned staging 后仍需同步 staging parent。`F_FULLFSYNC` 不可用时首版失败关闭，是否允许仅 barrier 的 profile 必须另行设计，不能作为默认兼容路径。

## 并发与 crash 矩阵

原生测试至少覆盖：

| 注入点或竞争 | 唯一允许结果 |
| --- | --- |
| staging 创建后、首文件同步前退出 | 下次持锁只识别 owned incomplete staging 并删除 |
| binary 同步后、receipt 同步前退出 | 不形成 final slot；下次持锁删除 staging |
| staging tree 全部同步后、rename 前退出 | 不形成 final slot；下次持锁重新验证后仍按 incomplete 删除，不从完整字节推断已安装 |
| rename syscall 返回后、parent sync 前退出 | 恢复时枚举 staging / final；只有 exact final 可重新同步并验证，其他组合失败关闭 |
| final parent sync 后、返回前退出 | exact final 重读成功；重复事务只允许 reuse |
| 两个独立产品进程发布相同树 | 一个 `Published`，另一个持锁后 `Reused` |
| 非协作进程先占 destination | publisher 不覆盖；只在 destination exact 时 reuse，否则 mismatch |
| symlink 替换任一祖先或 leaf | `ELOOP` / containment failure，外部 marker 不变 |
| 跨 device staging / final | `EXDEV` / explicit same-filesystem failure |
| 锁持有进程被 kill | OS 释放锁；后继进程仍按上述恢复矩阵重放字节 |

测试 helper 必须是仓库内 test-only binary，以确定性 checkpoint 和 `_exit` / kill 形成真实独立进程观察；不能用 mock callback 冒充 crash。进程退出测试只能证明 OS process-crash recovery，物理断电仍保持未验证。

## 实施授权停止线

本审阅已经证明当前目标需要新的第三方 binding、`unsafe` 和 Darwin 平台 package，超出此前 safe / zero-third-party 实现授权。下一切片只有在项目所有者明确同意以下精确范围后才能开始：

1. 将 canonical launcher policy 从 `0.2` 显式迁移到新版本，更新 dependency status、schema、负例、摘要链和审阅记录；由迁移分析决定 registered-inactive payload record 能否保持 `v0.1` 原字节，不预先假定；
2. 精确验收并加入 `libc = "=0.2.189"`，允许其现有 build script 与平台 `unsafe` binding，更新 `Cargo.lock` 和第三方许可证记录；
3. 新增一个 macOS-only 私有 Darwin store crate，在上述窄接口内使用 `unsafe`，并把 core 的 path-based production 实现替换为 descriptor capability；
4. 只运行合成临时根、原生并发与 process-crash 测试，不读取真实产品根、不下载 / 安装 / 执行 checker、不激活 runtime、不修改远程状态且不 push。

未取得这四项授权前，当前 store 继续标记为 Unix 临时根事务候选，policy 继续为 `specified-not-implemented`，active runtime 保持 0。
