# Checker runtime Rust store 最小事务切片审阅单

状态：零第三方依赖的 Unix 临时根事务候选已实现并通过本地门禁，生产文件系统适配仍未完成
审阅日期：2026-09-01

## 目标与结论

本切片承接[installation receipt 切片](checker-runtime-rust-receipt-slice-review.md)，实现 [ADR 0012](adr/0012-product-checker-runtime-host-and-persistence-interface.md) 中 `checker-runtime-store-v0.1` 与安装相关的最小连续事务：产品注入唯一 canonical 私有根，调用方持有精确 target lock 后创建 owned staging，写入并验证闭合 slot inventory，再以同文件系统 rename 发布或精确复用既有 slot；持锁调用方还可精确重读 slot，或按 transaction identity 丢弃自身 staging。

本切片没有发现产品安装根，没有网络或 provider credential，不下载或解包真实 distribution，不解析两层业务 manifest，不执行 checker，不形成 qualification / attempt record，也不推进登记状态。所有文件系统测试只操作测试进程创建的 `0700` 临时目录。

`radishaxiom-checker-runtime` 新增并公开：

- `FilesystemStore`：只接受调用方注入的绝对、canonical、`0700` 私有根，并在根内建立 `0700` 的 `.locks` 与 `.staging`；
- `HeldTargetLock`：使用 Rust `1.97.1` 标准库原生文件锁形成按完整 target 隔离的线性能力，释放 capability 时解锁；
- `StoreTransactionIdentity` 与 `OwnedStaging`：transaction identity 只允许闭合可移植 ASCII 单组件，staging 写入只允许 `create_new` 的 `0644` / `0755` 普通文件；
- `VerifiedStaging`：只有在精确 policy、registered-inactive record、binary、receipt 与目录清单全部复核后才能形成；
- `SlotPublication` 与 `InstalledInactiveSlot`：区分首次 `Published` 和既有字节完全相同的 `Reused`，exact read 不伪装为一次 publication；
- `discard_owned_staging`：只在同一 store、同一 target 的 held lock 下按精确 transaction identity 清理，路径链出现符号链接或非目录即失败关闭。

这些类型使裸路径、布尔 `verified` 和调用方声称“已持锁”不再成为成功接口。成功仍只说明当前 Unix 测试文件系统上的受控事务满足所测边界，不说明真实 payload 已安装或可由产品选择。

## Slot 闭合与复用边界

slot verifier 从 canonical policy 读取 executable 相对路径和 receipt filename，并要求：

- slot inventory 恰好包含 executable、receipt 与两者必需的目录，不接受额外文件或目录；
- executable 为 `0755` 单链接普通文件，长度、SHA-256 与 Mach-O arm64 header 匹配登记；
- receipt 为 `0644` 单链接普通文件，canonical 重读后与 policy、record、slot 和 `installed-inactive` 身份一致；
- 所有路径组件都在注入根内，任何符号链接、硬链接、权限漂移或目标身份漂移都失败关闭；
- tree digest 以文件相对路径、mode、长度、raw SHA-256 和目录 mode 形成稳定的域摘要。

发布前要求 staging 与最终 slot parent 位于同一文件系统。若 slot 不存在，当前实现执行 rename 并立即重新验证；若 slot 已存在，只允许 tree verification 完全相同的精确复用并删除 owned staging，任何 mismatch 都保留 staging、拒绝覆盖。

## 跨实现黄金结果

Python 一致性 oracle 与 Rust 对同一个合成 Mach-O arm64 binary、合成 registered-inactive record、`2026-08-30T10:00:00Z` receipt 和相同 slot inventory 得到一致结果：

| 项目 | 值 |
| --- | --- |
| tree digest | `sha256:856141f47eceb4962bc290c8d2bcacfb39ef6a6e90631af6d241e5b5ab4f81fd` |
| publish sequence | `published -> exact reused` |
| mismatch behavior | 拒绝覆盖，保留 owned staging |

Rust 测试还实际打开两个 store handle 验证 OS 锁互斥与释放后重获，并覆盖相对 / 非 canonical root、跨 store capability、额外 inventory、错误 mode、硬链接、符号链接和 held-lock recovery 正反例。

## 未闭合的生产文件系统风险

当前实现是 Unix 路径上的最小事务候选，不是已经验收的生产 `FilesystemStore` 适配器：

- Rust 标准库 `rename` 没有跨平台 no-replace 语义；目标锁能序列化遵循本接口的 writer，但尚未用平台原语关闭不合作进程在“目标不存在”检查与 rename 之间创建目标的竞态；
- containment、符号链接与 metadata 检查仍是 path-based，尚未用 descriptor-relative lookup / `O_NOFOLLOW` 一类原语关闭检查与使用之间的替换竞态；
- 文件会 `sync_all`，但 staging / slot parent 的目录持久化与断电恢复序列尚未形成，当前测试也不是进程 crash / 电源故障证明；
- 只验证了当前 macOS / Unix 开发主机上的临时根，没有产品权限适配、真实产品根或其他平台原生证据。

因此本切片不得把 policy 的 `specified-not-implemented` 改为已实现，不得形成真实 installation receipt、qualification companion、runtime companion 或 active runtime。

## 验证与下一停止线

精确 `+1.97.1-aarch64-apple-darwin` 下的格式、Clippy、locked / offline test、metadata 与 dependency tree 继续作为 Rust 门禁；Python launcher oracle、checker runtime payload 生成复核、仓库级检查与差异卫生继续作为跨实现和仓库门禁。通过这些测试只说明实现满足所测事务不变量，不构成形式证明或安装证据。

2026-09-01 的实际结果为：`cargo fmt --all --check`、locked / offline `clippy -D warnings`、28 项 locked / offline Rust test、metadata 与 dependency tree 全部通过；metadata 仍只有一个 `publish = false` 的 Rust 2024 library、零 dependency / feature。Python launcher oracle 21 项测试、checker runtime payload 34 个生成文件、仓库级 942 文件门禁和 `git diff --check` 同时通过。

后续[Darwin 生产文件系统边界审阅](checker-runtime-darwin-filesystem-review.md)已确认需要原子 no-replace publication、descriptor-relative containment、目录持久化与真实并发 / crash 矩阵，并收敛到私有平台 crate + 精确 `libc` binding 的方案。由于这会改变 policy 的零第三方依赖声明并引入 build script / `unsafe` / native FFI，policy 迁移、依赖验收和实现仍须取得精确授权。真实 immutable asset fetch / install、业务 manifest parser、result consumer、subprocess / isolation、qualification、激活、push 与远程状态继续分别验证、分别授权。

项目所有者随后授权并完成该范围；policy `0.3`、依赖验收、descriptor-backed macOS core 与原生进程矩阵的实际结果见 [Darwin store 生产切片审阅](checker-runtime-darwin-store-slice-review.md)。本文件保留最小事务候选完成时的边界，不把当时 28 项 path-based 测试追溯写成生产原语证据。

同日后续又按独立范围补齐 [qualification / attempt store 切片](checker-runtime-evidence-store-slice-review.md)；该后续实现不改变本文件记录的最小事务历史证据。
