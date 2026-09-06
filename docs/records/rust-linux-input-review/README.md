# Rust Linux 输入与 kernel 许可诊断

日期：2026-09-06；基线 `bb014fd`。用途：留存 Rust `1.97.1` GNU arm64 host / musl target 的实际字节、签名、归档与安装边界观察，以及 kernel 许可和 tag 对应审阅。读者为工具来源、guest 与构建维护者。本记录是受控诊断，不是公共 payload acceptance、完整 source lock、安装回执或产品许可决策；未执行安装器、Rust、linker、内核构建或产品 VM。

## 实际结果

| 材料 | 长度 | 本地 SHA-256 |
| --- | --- | --- |
| `channel-rust-1.97.1.toml` | 845,916 | `03569b1886ceb5c05276b50c8431ab111de944cd6140fe1fa7d821dd8e0f29cf` |
| `rust-1.97.1-aarch64-unknown-linux-gnu.tar.xz` | 175,976,652 | `9a7a2c336b4787f1b72f6bab7c35d5b7af2fd03cbd39b4fc721466a70d402a7d` |
| `rust-std-1.97.1-aarch64-unknown-linux-musl.tar.xz` | 29,062,284 | `49ff0879d94e2e8e86d5e85eb15a9215943e8c78b51363d6553443598cab5d31` |

[完整清单](channel-rust-1.97.1.toml)的摘要与既有 Darwin 批次绑定一致，channel date 为 `2026-07-16`。两份实际归档分别匹配该清单的精确 package / target / URL / SHA-256；它们与相邻平台、rustup component 及 source 的身份不可互换，旧 registry / acceptance 保持原字节。

[归档库存](archive-inventory.json.gz)是完整 JSON 的无时间戳 gzip；压缩与展开长度 / 摘要、方法身份及选择摘要见 [summary.json](summary.json)。GNU host 有 1,545 个目录、65,785 个文件、11 个 component；musl target 有 7 个目录、78 个文件、1 个 component。两者均无链接或特殊成员，owner 为 `0:0`，mode 为 `0644` / `0755`。版本文本与 commit 均为 `1.97.1 (8bab26f4f 2026-07-14)` / `8bab26f4f68e0e26f0bb7960be334d5b520ea452`。

## 签名结果与信任缺口

三份材料的分离签名在固定本地镜像的 GnuPG `2.2.40` 下均退出 0，得到唯一 `VALIDSIG`，digest algorithm 为 10（SHA-512），主指纹为 `108F66205EAEB0AAA8DD5E1C85AB96E6FA1BE5FE`。[实际观察](signature-verification.json)保留全部 GnuPG 状态、stderr、binary 摘要、公钥显示 / 导入及 certification 检查；[方法](verify-signatures.py)拒绝不同主指纹、弱摘要、过期 / 撤销 / 失败状态。

公钥取自 [Rust Forge 所链接](https://forge.rust-lang.org/infra/other-installation-methods.html)的[官方公钥](https://static.rust-lang.org/rust-key.gpg.ascii)，留存为 [rust-key.gpg.ascii](rust-key.gpg.ascii)。完整指纹另与 Rust 上游[公开问题记录](https://github.com/rust-lang/simpleinfra/issues/218)核对；这不是额外建立了一条独立信任链。keyring 为 `TRUST_UNDEFINED`，没有修改宿主 keyring 或使用 Web of Trust 认证。

**公钥 certification 的 digest algorithm 仍为 2（SHA-1）**。本轮 GnuPG 接受这些旧自认证，不能将其成功外推为严格现代 key-binding policy 已通过。上游问题亦记载此类策略差异；本轮没有安装 Sequoia、增加弱算法兼容选项、改写公钥或采用替代指纹。正式验收仍需解决 / 明确公钥绑定策略、镜像与验证工具来源；`pinned_signature_passed` 只表示本记录声明的 GnuPG 核验条件成立，不代表工具已接受或代码正确。

## 只读盘点方法与失败保留

[inspect-archives.py](inspect-archives.py)固定两份输入和 channel manifest，先重算压缩摘要，再流式扫描并在结束时复算摘要 / 文件状态。它限制压缩量 512 MiB、展开 tar 4 GiB、单成员 512 MiB、200,000 个逻辑成员、路径 4,096 bytes、元数据文本 8 MiB；拒绝路径别名 / 逃逸、重复项、链接 / 特殊类型、异常 owner / mode、缺失祖先、错误 component manifest claim、尾随 / 拼接 XZ 和非零 tar 尾部。逐文件保留摘要，并核对 180 / 66 个 component claim 所指对象及类型。

这是标准库 `tarfile` 的**逻辑成员诊断**，不等于旧 v0.1 物理归档验收，也不是产品提取器；没有新增可被旧 consumer 消费的公共格式。选定 ELF 只观察头部 / 动态段，不是链接或运行兼容验收。

首次扫描在 XZ decoder 的 128 MiB 限额处失败，stdout 无成功结果；[原错误](archive-inventory-attempt-1.stderr)和[方法差异](archive-inventory-attempt-1-method.patch)保留。将**宿主诊断工具**的 decoder 上限显式改为 256 MiB 后，两包完整盘点成功。这没有改变 ADR 0015 的产品 guest 128 MiB RAM 候选边界，也没有给产品放宽限制。patch 从当前 `inspect-archives.py` 重建首次方法，摘要见 summary；失败与成功不是同一方法的无说明重试。

## 静态目标与精确安装候选

实际 musl 包包含 `libc.a`、`libunwind.a` 和 9 个 CRT 对象：`crt1.o`、`Scrt1.o`、`rcrt1.o`、`crtbegin.o`、`crtbeginS.o`、`crtend.o`、`crtendS.o`、`crti.o`、`crtn.o`。CRT 头部均为 ELF64 little-endian / AArch64 / relocatable；两个 `.a` 仅观察到 archive magic，未逐对象验收。每份长度 / 摘要均在库存中。[精确 Rust target 源码](https://raw.githubusercontent.com/rust-lang/rust/1.97.1/compiler/rustc_target/src/spec/targets/aarch64_unknown_linux_musl.rs)声明 musl `1.2.5` 和默认静态 CRT；[musl base 源码](https://raw.githubusercontent.com/rust-lang/rust/1.97.1/compiler/rustc_target/src/spec/base/linux_musl.rs)使用 inferred self-contained 策略，不能仅据此宣称最终 ELF 没有动态 loader。

GNU host 的 `rustc` component 实际带有 `rust-lld`。选定工具 ELF 的静态观察见 [selected-inputs.json](selected-inputs.json)：

| 工具 | 实际宿主依赖 |
| --- | --- |
| rustc | `/lib/ld-linux-aarch64.so.1`；`librustc_driver-bb2b40829e117684.so`、libdl、libpthread、libc；RUNPATH 为 `$ORIGIN/../lib` |
| cargo | 同一 loader；libdl、libgcc_s、libpthread、libm、libc；RUNPATH 为 `$ORIGIN/../lib` |
| rust-lld | 同一 loader；libpthread、libz、`libLLVM.so.22.1-rust-1.97.1-stable`、libm、libgcc_s、libc；保留原 RUNPATH |

这些依赖属于 builder，不是 guest 的依赖声明。尚未递归验收 driver / LLVM 动态库闭包，未执行 `ldd` 或任何归档程序；现有镜像包名或存在同名库不能替代实际 loader、symbol version 与运行验收。

两份 `install.sh` 已只读审阅：默认 prefix 是 `/usr/local`，默认选择全部 component，会先处理已安装 / legacy manifest，并默认运行 `ldconfig`；特定默认路径下还可能写 `/etc/ld.so.conf.d/`。下一安装候选必须是固定容器内**不存在的新前缀** `/opt/radishaxiom/rust-1.97.1`，第一包显式选择 `rustc,cargo,rust-std-aarch64-unknown-linux-gnu`，第二包只选择 `rust-std-aarch64-unknown-linux-musl`，两次均使用 `--disable-ldconfig`。不复用镜像已有 rustup 目录或修改宿主 PATH。

按 component manifest 展开的候选 payload 为 146 个 GNU 文件 / 543,554,271 bytes，加 66 个 musl 文件 / 152,642,974 bytes；不包括安装器新增日志、manifest、目录开销，不能当作最终磁盘占用或安装回执。尚未提取成可执行目录或运行安装器，提取策略、隔离安装和有限执行仍需单独收口。

主仓既有 Rust source acceptance 可提供源码追溯起点，但不能覆盖 Linux binary 的构建证明或外部 runtime。musl 包只带根部三份许可文本；GNU host 的 `COPYRIGHT-library.html` 未找到 `musl` / `libunwind` / `compiler-rt` / `compiler_builtins` 这些精确词条，不能据此宣称外部 CRT 已覆盖或存在法律违规。下一步须把实际 `libc.a` / CRT / unwind 与 Rust 构建配方、精确源码及各自许可对应，再确定 init 的最终链接方案；不把根部 `MIT OR Apache-2.0` 当成全部静态输入的许可证。

## Kernel tag 与许可材料

[tag 元数据](kernel-tag.response.txt)来自 stable 官方 Google 镜像的 `refs/tags/v6.18.49` JSON 入口，其 peeled commit 为 `1c732c6b94f0faee1526bd375add2fe10cba2e26`，与已验签 tar 的 PAX comment 相符；tree 为 `3fd77c646490ad640a4cb7f37c63a1eaf8c2bd7b`。这补上了精确 tag 引用的元数据对应，不是 Git tree 重建或原始 tag 验签。尝试 `+show/refs/tags/v6.18.49?format=TEXT` 返回 HTTP 400 / curl transfer 56；同一 curl 后续 Rust 签名传输成功导致整个多传输命令退出 0，未将其误记为 tag 成功。失败状态和 URL 见 summary。

本轮从已固定摘要的 Linux `6.18.49` 源包中重新读取 `COPYING`、`LICENSES/preferred/GPL-2.0`、`LICENSES/exceptions/Linux-syscall-note` 和 `Documentation/process/license-rules.rst`，文件摘要与前次完整库存核对一致。原文保留在上游源包，仓库不再复制一套第三方文档；[选定输入方法](inspect-selected-inputs.py)可重读。

依据实际 GPL v2 第 1–3 节及 [kernel 许可说明](https://docs.kernel.org/process/license-rules.html)，后续分发设计应单列：kernel 的版权 / 许可证 / 无担保说明；修改文件及日期；与实际 `Image` 对应的源码、patch、配置及控制构建 / 安装的脚本。建议按第 3(a) 路径提供对应源码材料，不仅给可漂移的上游网址。正常 syscall 使用的例外与 kernel 自身的分发义务分别判断；不能把同一 initramfs 中所有文件一概重标为 GPL，也不能用 syscall 例外免除 kernel 的义务。最终组件、生成器、DTB、UAPI 使用与实际分发边界尚未确定，本段不接受具体分发方案，也不修改项目 Apache-2.0 策略。

## 输入来源、运行与复核

Rust 原始 URL：`https://static.rust-lang.org/dist/channel-rust-1.97.1.toml` 及 `.asc`；两个归档使用清单内的 `https://static.rust-lang.org/dist/2026-07-16/` 加上表中 filename，签名为相同 URL 加 `.asc`。curl 固定 HTTPS、TLS ≥ 1.2、`--fail --location`；公开元数据每项 ≤ 2 MiB / 45 秒，GNU archive ≤ 512 MiB / 240 秒，musl archive ≤ 128 MiB / 120 秒。首次 metadata fetch 的四项均成功；后续 raw tag 尝试的单项失败另列。公开公钥 / 清单 / 签名作为验证元数据留存，Rust binary 与第三方安装器正文只留在本任务忽略缓存。

离线验签原命令在仓库根执行：

```bash
docker --context orbstack run --rm --name radishaxiom-rust-signatures-bb014fd \
  --pull=never --platform=linux/arm64 --network=none --read-only \
  --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=64 \
  --memory=512m --cpus=1 --user=65534:65534 \
  --tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777 \
  --mount type=bind,src=/Users/luobo/Code/RadishAxiom/.tmp/rust-linux-inputs-bb014fd,dst=/inputs,readonly \
  --interactive --entrypoint=/usr/bin/timeout \
  sha256:a339861ae23e9abb272cea45dfafde21760d2ce6577a70f8a926153677902663 \
  120s /usr/bin/python3 - < docs/records/rust-linux-input-review/verify-signatures.py \
  > .tmp/rust-linux-inputs-bb014fd/signature-verification.json \
  2> .tmp/rust-linux-inputs-bb014fd/signature-verification.stderr
```

镜像来源仍沿用[已有库存的诊断边界](../linux-6.18.49-source-review/README.md)，没有隐式升级为可信 builder。keyring 在容器临时目录内创建并清理，容器退出自动删除；宿主库 / 默认 keyring 不变。

主机 Python `3.14.5` 的复核入口：

```bash
python3 docs/records/rust-linux-input-review/inspect-archives.py \
  .tmp/rust-linux-inputs-bb014fd > .tmp/rust-linux-inputs-bb014fd/archive-inventory-recheck.json
python3 docs/records/rust-linux-input-review/inspect-selected-inputs.py \
  .tmp/rust-linux-inputs-bb014fd \
  .tmp/linux-6.18.49-source-review-dc4de70/linux-6.18.49.tar.xz \
  > .tmp/rust-linux-inputs-bb014fd/selected-inputs-recheck.json
python3 docs/records/rust-linux-input-review/check-diagnostics.py
./scripts/check-repo.sh
git diff --check
```

首次实际选定文件读取使用 `--include-text`，留存在忽略目录；移除每个文件的 `text` 字段后原样留存本目录的 JSON。`selected_lines` 是带原行号的安装器审阅摘录，来源与许可沿用精确 Rust archive 的 COPYRIGHT / 许可文件；不复制完整上游安装脚本或二进制。[8 项合成检查](check-diagnostics.py)覆盖路径、manifest claim、危险成员 / 权限、资源上限、损坏 / 拼接压缩、ELF 动态段与签名状态拒绝；签名状态使用 mock，不能替代上述真实 GnuPG 结果。它们是本记录的复核入口，不宣称已加入默认仓库门禁。

下一步明确公钥绑定策略、静态 runtime 来源及 driver / LLVM / 系统库闭包，再提出精确容器安装 / 有限执行范围。既有三包 apt 模拟与本轮静态清单都不授权真实安装；ADR 0015、维护投入、公共迁移及产品运行继续分别处理，近期顺位见[当前状态](../../status/current.md)。
