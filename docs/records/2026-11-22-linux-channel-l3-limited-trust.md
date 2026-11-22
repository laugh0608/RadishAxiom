# AX-B01 的 L3 输入限定信任

2026-11-22，所有者在 `dev` / `8d14c57` 上确认以下四项限定信任。用途限于 L3 的一次本机 Linux AArch64 musl 诊断启动器构建所需输入，后续安装和构建仍分别授权。L3 整体保持 `not-accepted`，`build_ready=false`、`execution_ready=false`。本记录提供输入审阅依据，真实安装回执、`host-resolution`、`input-review.json`、外部 review pin 和真实 v0.2 root 仍待形成。 [原输入审阅](2026-11-07-linux-channel-l3-input-acceptance-review.md) · [本轮待决基线](2026-11-22-linux-channel-l3-input-decision-preparation.md) · [L3 专题](../query/solver-linux-channel-l3.md)

## 1. Cargo 官方解析元数据

只接受下列两个精确文件，从 `/Users/luobo/.cargo/` 下按原相对路径复制到一次任务的隔离 `CARGO_HOME`，用于 `--locked --offline` 的 workspace 依赖解析。两份本机原件与上次离线试验的保留副本逐字节一致。

| `CARGO_HOME` 相对路径 | bytes | SHA-256 |
| --- | ---: | --- |
| `registry/index/index.crates.io-1949cf8c6b5b557f/config.json` | 76 | `5b943a2c6f7eb743f7308aba07bdbb47d9ae44aafecd832d7f15df186afbafb3` |
| `registry/index/index.crates.io-1949cf8c6b5b557f/.cache/li/bc/libc` | 84,005 | `0c0c0edd0d15a477311bebab5f7b35d68767bb2ebeea274f85404cd2921c498a` |

`config.json` 与官方 sparse 响应及官方 Git 索引相同。`libc` 本机文件为 Cargo sparse cache v3 / index v2，解码后全部 209 条记录的字节和顺序均与两个官方来源相同。原始 NDJSON 为 82,389 bytes，SHA-256 `de437e8dbc298365b02d7ec43a8e8480094eecde6bd7d4ddbc52553d92ae571f`，稀疏响应 ETag 为 `"3493734e19f35430b70d023b1c1ad969"`。唯一非 yanked `libc 0.2.189` 条目的 checksum 对应 `Cargo.lock` 中的 `3eaf3ede3fee6db1a4c2ee091bf8a8b4dccdc6d17f656fb07896ee72867612f2`。 [官方 config](https://index.crates.io/config.json) · [官方 sparse 索引](https://index.crates.io/li/bc/libc) · [固定 Git 索引](https://github.com/rust-lang/crates.io-index/tree/e049d137b586b0e020a7bc0ca9b04689ea73b39c)

本地用途依据 crates.io 对 Cargo 使用索引的公开说明。独立的通用再分发许可仍未确认。政策正文的 CC BY 4.0、registry 实现许可及 `libc` crate 的 MIT / Apache-2.0 各有适用对象。该决定仅覆盖两份元数据的上述本地用途，再分发、额外 registry 数据及 `.crate` 文件均需独立依据。 [数据访问政策](https://crates.io/data-access) · [crates.io 政策](https://crates.io/policies) · [固定政策源码](https://github.com/rust-lang/crates.io/tree/6898ff3b275ed7ce25544fb81ab31aeb90898810/svelte/src/routes) · [crate 许可审阅](../checker-runtime-darwin-store-slice-review.md#依赖与供应链边界)

## 2. Rust target 与固定安装器

只接受 `1.97.1-aarch64-apple-darwin` 的额外 `aarch64-unknown-linux-musl` target。发布清单日期 `2026-07-16`，845,916 bytes，SHA-256 `03569b1886ceb5c05276b50c8431ab111de944cd6140fe1fa7d821dd8e0f29cf`。只使用本机留存的 `rust-std-1.97.1-aarch64-unknown-linux-musl.tar.xz`，29,062,284 bytes，SHA-256 `49ff0879d94e2e8e86d5e85eb15a9215943e8c78b51363d6553443598cab5d31`。实际组件载荷按已经核对的 66 文件、152,642,974 bytes 清单逐项绑定。安装器限 `/Users/luobo/.cargo/bin/rustup` 的 Darwin arm64 `1.29.0`，11,053,296 bytes，SHA-256 `aeb4105778ca1bd3c6b0e75768f581c656633cd51368fa61289b6a71696ac7e1`，对应官方发布摘要。 [Rust 官方清单](https://static.rust-lang.org/dist/2026-07-16/channel-rust-1.97.1.toml) · [rustup 官方摘要](https://static.rust-lang.org/rustup/archive/1.29.0/aarch64-apple-darwin/rustup-init.sha256) · [目标 payload 清单](cvc5-control-plane-2026-11-01/channel-l3-input-observation.json)

信任终点限于这次官方 HTTPS 发布清单、固定摘要和留存原件。此前 GnuPG 2.2.40 对 SHA-512 分离签名的观察以指纹 `108F66205EAEB0AAA8DD5E1C85AB96E6FA1BE5FE` 为限，公钥的历史 SHA-1 自认证限制继续保留。Rust、musl libc / CRT、compiler-rt、compiler-builtins 和 libunwind 依各自材料与许可范围登记，实际参与链接的成员及相应归属待 L4 对账。既有五个 Darwin 组件的接受范围单独延续。 [历史签名](rust-linux-input-review/README.md#签名结果与信任缺口) · [Rust 源回读](2026-11-07-linux-channel-l3-rust-source-readback.md) · [目标材料与许可](rust-linux-input-review/source-recipes-2026-09-10.md)

## 3. 固定 Darwin 宿主与 libproc ABI

仅信任本机 macOS `27.0.1 (26A434)` / Darwin `27.0.0 arm64`、已观察的 dyld / 系统共享缓存及本轮固定的宿主工具。`/System/Library/CoreServices/SystemVersion.plist` 为 604 bytes，SHA-256 `bd61e19dd67dd97ce9a27c79a2148d42cc9685a71c6f17ff27d62b819f39f983`。`/usr/lib/dyld` 为 4,129,840 bytes，SHA-256 `be8904b70f95adeb9d244308ca470f939bb89bd32a9b1b05e3f65ac92579e226`。此前读取的 shared cache UUID 为 `c284a291-b68b-3d0d-a1a0-3f866f87efdc`。`rustc`、Cargo、GNU flavor 的 rust-lld 与实际 Rust driver 沿用 Darwin 固定组件及安装字节证据。Python 范围为已绑定 Astral `20260510` 的 `3.14.5` 解释器及实际读取的库文件、字节码、内建 `_ctypes` 和静态 libffi `3.4.6`，沿用其发布、证明与许可留存。执行前须再核实际工具与读取材料。 [Apple 系统发布](https://developer.apple.com/news/releases/?id=09282026c) · [宿主观察](2026-11-07-linux-channel-l3-input-acceptance-review.md#原字节与复核方法) · [Rust driver](2026-11-07-linux-channel-l3-rust-source-readback.md) · [Python 和 libffi](2026-11-07-linux-channel-l3-python-source-readback.md)

宿主假设限于一次包装器所依赖的文件系统、系统加载、PID / PGID 和信号 / 等待语义。监督进程须使用默认 SIGCHLD 处置并成为唯一 waiter，`waitid(WNOWAIT)` 保留组长 PID，回收前用 libproc 枚举原组的至多 64 项成员。工具须留在原组。Linux G0 的资源硬限、进程树终止、隔离与内核行为由实际 Linux 宿主另行证明。 [监督边界](../query/solver-linux-channel-l3.md#native-捕获与一次包装器)

ABI 证据更新到 Xcode `27.2 (27B52)` 的固定 `/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX27.2.sdk/usr/include/` 下两份头文件。

| 头文件 | bytes | SHA-256 |
| --- | ---: | --- |
| `libproc.h` | 7,575 | `246d87709fc6b9157ce5cf3c475656ac48e0e1ae8bbdc46cf45acd34294448cd` |
| `sys/proc_info.h` | 31,262 | `e427fa96b348537b21552b9de71e01039410bcad2cedee5584c5e5fddafd70fc` |

两份头文件的长度与摘要分别匹配此前 CLT 27.0 SDK 的留存观察。现行证据采用上述 Xcode 路径，原批次记录保留。`libproc.h` 的 `int proc_listpids(uint32_t type, uint32_t typeinfo, void *buffer, int buffersize)` 与 `sys/proc_info.h` 的 `PROC_PGRP_ONLY = 2` 对上 Python `ctypes` 参数、返回类型和查询选择。先前只通过 `dladdr` 将符号解析到 `/usr/lib/system/libsystem_kernel.dylib`，本批只读头文件与包装器源码，实际调用与组回收行为留待获准的宿主执行验证。 [27.0 历史证据](cvc5-control-plane-2026-11-01/channel-l3-implementation-results.json) · [参数绑定](../../scripts/build-linux-channel.py)

## 4. Apple Git-157 的精确二进制

只接受 `/usr/bin/git` 经固定 `xcode-select` / `xcrun` 解析到 `/Applications/Xcode.app/Contents/Developer/usr/bin/git` 的 Apple Git-157，用于一次隔离配置下的本地只读 Git blob 快照。四个程序的文件摘要沿用执行链记录，Xcode 的 `Contents/version.plist` 为 527 bytes，SHA-256 `93b253c224fee82d869beb7a0462f2e90138cad83bcdc64784c614eee6f8ba2d`。随包 Apple 签名、CDHash `c6bc766780e7df21ce04dab18fb8c9189ea48169`、安装收据及 GPL v2 致谢作为分发证据。精确 Git-157 Apple 源码及其与二进制的对应仍缺，本轮信任以该固定签名二进制为限。

包装器只读 `rev-parse`、`status`、`ls-tree` 和 `cat-file`，关闭系统与用户配置、hooks、懒取对象和交互提示。快照前后须读回相同选择路径和文件身份，两个选择命令须成功且 stderr 均为零字节。 [Apple Git 执行链与许可](2026-11-07-linux-channel-l3-apple-git-readback.md) · [Apple Xcode 27.2 发布](https://developer.apple.com/news/releases/?id=10292026a) · [快照门禁](../query/solver-linux-channel-l3.md#native-捕获与一次包装器)

## xcrun 路径与 stderr 复核

在同一工作目录，以空继承环境、相同的快照环境变量、绝对命令路径和独立进程会话运行每个只读查询。每条命令的超时为 7 s。所有轮次退出码均为 0，stdout 分别精确等于 `/Applications/Xcode.app/Contents/Developer\n` 和 `/Applications/Xcode.app/Contents/Developer/usr/bin/git\n`。

| 2026-11-22，Asia/Shanghai | 轮次 | `/usr/bin/xcode-select -p` stderr | `/usr/bin/xcrun --no-cache --find git` stderr |
| --- | ---: | --- | --- |
| 14:06:09–14:06:12，Codex 执行沙盒 | 3 | 均 0 bytes | 均 105 bytes |
| 14:06:30–14:06:33，普通宿主权限 | 3 | 均 0 bytes | 均 0 bytes |
| 14:06:59，回到 Codex 执行沙盒 | 1 | 0 bytes | 105 bytes |

沙盒内四次均由 `xcodebuild` 报出 `DVTFilePathFSEvents: Failed to start fs event stream.`。相同命令仅在沙盒中复现，定位到 Codex 执行沙盒下的 Xcode 文件事件流启动失败，固定路径和退出码一致。沙盒内的统一日志查询返回 `Cannot run while sandboxed`，普通宿主权限按首组三个 PID 和时间窗检索也未找到对应的 FSEvents 或拒绝日志。具体被拒绝的底层操作尚未确认。

按现有守卫，沙盒中的非空 stderr 会触发 `apple-git-resolved-path-drift`。普通宿主对照满足这两个查询的路径及 stderr 条件。本批只运行查询探针。实际快照须在拟用且单独授权的执行环境，在前后两次核对中读回相同文件身份与路径，两个命令的 stderr 均须为空。仍有诊断时在 Cargo 前停止。 [原守卫](../../scripts/build-linux-channel.py#L290)

## 剩余阻塞与恢复

1. 单独授权一次 target 安装，执行前重核唯一目标、预期元数据及同名 cache / partial 均缺席。沿用 120 s 和额外磁盘观测 512 MiB 的边界，安装后核对 66 文件、原五个宿主组件、三工具及元数据变化。 [安装事务](../query/solver-linux-channel-l3.md#未来安装只增加一个-target)
2. 绑定最终干净提交的完整源码树和真实安装、实际宿主与工具证据，取得外部 review pin 后生成并独立复核真实 v0.2 root。按实际拟用环境复核上述路径与 stderr，再分别授权 L3 构建、L4 制品验收和 L5 交付、挂载与诊断。 [L3 专题](../query/solver-linux-channel-l3.md)
3. G0 须先确定同一 Linux 宿主的管理入口、权限与私有候选根，再取得隔离、无写别名、块 / inode 硬限和独立整树终止的实证。实际 C3、C4 / E0、E4、E5 与 E6 继续依原顺序及授权推进。 [G0 停止决定](2026-11-01-cvc5-g0-capability-review.md#g0-各项结果与停止决定) · [Solver 当前顺位](../status/current.md#solver-与运行交付)
