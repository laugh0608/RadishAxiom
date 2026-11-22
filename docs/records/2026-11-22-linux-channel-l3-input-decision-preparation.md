# AX-B01 的 L3 输入接受待决项

2026-11-22。以干净的 `dev` / `330fb3be1fda310c4868ea49df0126caa01979ed` 开始。无 Poly solver 的 C1 固定 Debian 输入已获限定接受。L3 诊断启动器使用 Darwin AArch64 Rust `1.97.1` 交叉构建 Linux AArch64 musl，其输入仍为 `not-accepted`。本记录为下一次决定准备精确证据。单次安装、真实 v0.2 root、构建、G0 和运行资格均待各自前置。 [C1 限定接受](2026-11-22-cvc5-no-poly-c1-acceptance.md) · [L3 专题](../query/solver-linux-channel-l3.md)

## 已核对的源码基线

在快照包装器采用的精简 Git 环境中，读回 HEAD、干净状态、全树及每个 Git blob。计算了每个 blob 的原 Git 对象标识并核对大小和封套，前后 HEAD 和干净状态一致。基线 Git tree 为 `2ec3cbe0de1404e89bf59b60fc35e9926ddc2897`，原 `ls-tree -rlz` 输出 SHA-256 为 `82c3273309f3cebcccb0b6e3747a53153852f93ffd940463009ce891ceb0662d`。

| 项目 | 结果 |
| --- | --- |
| 全树 | 3,098 个普通 Git blob，99,284,576 bytes。路径和模式符合包装器的快照约束，低于 4,096 文件和 128 MiB 上限。 |
| L3 实现 | 与 `998ae8e` 比较，独立输入检查器、构建包装器、`solver-bootstrap-linux`、Cargo workspace 和 lockfile 无差异。 |
| 实际输入绑定时点 | 本次只读检查未物化快照，也未生成 `source-snapshot.json` 或正式 pin。真实安装回执齐备后，根据执行前的最终干净提交重新读取全树。 |

## Cargo 解析数据的字节与许可范围

使用 L3 既有记录中声明的两个精确普通文件。已逐字节比对本机原位置和原离线试验保留在 `.tmp/linux-channel-l3-implementation-20261101-a/host-resolution-home/` 的相同路径副本。两份副本可作为后续身份对照，未来构建仍须按正式清单指定实际源路径及摘要。

| 文件 | 长度 | SHA-256 |
| --- | ---: | --- |
| `registry/index/index.crates.io-1949cf8c6b5b557f/config.json` | 76 bytes | `5b943a2c6f7eb743f7308aba07bdbb47d9ae44aafecd832d7f15df186afbafb3` |
| `registry/index/index.crates.io-1949cf8c6b5b557f/.cache/li/bc/libc` | 84,005 bytes | `0c0c0edd0d15a477311bebab5f7b35d68767bb2ebeea274f85404cd2921c498a` |

原 `config.json` 声明 crates.io 的 `dl`、`api` 地址。本地索引为 Cargo sparse cache v3 / index v2，包含 ETag 字段及 **209 条** `libc` 版本记录。匹配 `Cargo.lock` 的唯一非 yanked `0.2.189` 条目原始 JSON 为 485 bytes，SHA-256 为 `1284aa9df41937e760dc3d6361129453feb39f880c8973f1e13d5a94d7a257dd`。lockfile 中的 crate SHA-256 `3eaf3ede3fee6db1a4c2ee091bf8a8b4dccdc6d17f656fb07896ee72867612f2` 与独立留存的完整 `libc-0.2.189.crate` 原字节相等。

核对结果仅覆盖同一份本地缓存及锁定条目的对应。仍缺原 registry 响应或可对应缓存内容的发布材料，以及覆盖**实际复制的整个索引文件和 config** 的许可依据。crate 的 MIT / Apache-2.0 只覆盖此前审阅的 crate。现行配方的用途限于新任务 Cargo home 内的 workspace 锁解析，仍只复制上述两份元数据。若许可依据只覆盖锁定条目，需要单独审阅输入收窄及 Cargo 离线兼容性。 [原解析观察与使用边界](2026-11-01-linux-channel-l3-implementation.md#宿主发现与根因修正) · [crate 许可审阅](../checker-runtime-darwin-store-slice-review.md#依赖与供应链边界)

## 安装前须形成的输入决定

| 对象 | 依据及待决定范围 |
| --- | --- |
| 唯一 Rust target 与 installer | 采用留存的 `2026-07-16` Rust 发布清单、精确 `rust-std-1.97.1-aarch64-unknown-linux-musl.tar.xz` 与 66 文件库存，以及匹配同平台官方摘要的 `rustup 1.29.0`。决定须说明旧 GnuPG 对归档 SHA-512 分离签名的观察、公钥 SHA-1 自认证限制及发布清单 / HTTPS 信任。沿用 Darwin 组件已登记的范围。 [目标与签名边界](rust-linux-input-review/README.md#签名结果与信任缺口) · [installer 和 Rust driver](2026-11-07-linux-channel-l3-rust-source-readback.md) |
| Darwin 宿主与工具 | 限定实际的 macOS `27.0.1 (26A434)`、dyld、libproc、文件系统和进程组语义，以及固定 Rust / Python 工具与实际加载材料。Python 复用之前的发布制品与 libffi 证据，后续对实际读取的文件和字节码重核。 [宿主记录](2026-11-07-linux-channel-l3-input-acceptance-review.md#决定) · [Python 来源与许可](2026-11-07-linux-channel-l3-python-source-readback.md) |
| Apple Git | 固定 `/usr/bin/git` 及 Xcode `27.2 (27B52)` 中签名的 Apple Git-157，已留存包归属和随包 GPL v2 声明。精确 Apple 源码与构建对应仍缺。可以单独裁决是否按既有签名分发和字节证据，仅信任该二进制执行一次本地只读 Git 快照。包装器继续按执行链前后读回阻断选择漂移。 [Apple Git 执行链](2026-11-07-linux-channel-l3-apple-git-readback.md) |
| Cargo 元数据 | 补上述 config 和 libc 索引的精确来源、许可及输入范围。适用证据限于官方 registry 响应或索引的固定权利声明与内容关联。无可靠关联时继续保留缺口。 |

以上决定齐备后，单独审批唯一 target 安装范围。使用固定原归档的 29,062,284 bytes 新 cache 副本，检查目标、component manifest 和同名 cache / partial 缺席，由已绑定 rustup 在离线配置下处理限定事务。上限为 120 s、额外磁盘观察 512 MiB，核对 66 项文件和原五个宿主组件、三工具以及实际元数据差异。失败保留日志、精确的差异、可能的部分安装和 cache，清理由实际副作用另行决定。真实安装观察、正式工具和来源审阅、源快照及外部 review pin 到位后才生成真实 v0.2 root。 [安装目标和停止线](../query/solver-linux-channel-l3.md#未来安装只增加一个-target)

G0 仍以证据不足结束。独立恢复先指定同一 Linux 宿主的管理入口与候选存储根，核对实际身份、隔离、块 / inode 硬限与整树终止条件。L3 的诊断启动器完成构建和独立制品验收后进入只读诊断授权，真实 G0 资格须按原矩阵分别取得。 [G0 结束决定](2026-11-01-cvc5-g0-capability-review.md#g0-各项结果与停止决定)
