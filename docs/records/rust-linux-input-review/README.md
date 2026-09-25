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

## 2026-09-10：宿主依赖补查与安装前置收敛

本次基线为 `dev` / `3aa2dbb`，工作区初始干净。使用主机 Python 只读扫描既有 GNU archive，未下载新依赖、启动容器、执行 ELF 或安装器。前述 9 月 6 日的观察与摘要不改写。

[新增方法](inspect-host-dependencies.py)复用已留存的 XZ reader 与 ELF 动态段观察函数，输入为固定摘要的原始 GNU archive 和固定摘要的完整库存。先校验压缩 SHA-256，再完整扫描；扫描过程中重算压缩流和 tar 流身份，并逐项核对选定 ELF 的长度 / 摘要。单个 ELF 的宿主诊断读取上限为 192 MiB，XZ / tar 上限沿用已有方法，不改变产品资源 profile。

[实际输出](host-dependencies-2026-09-10.json)覆盖选定 rustc / cargo / GNU std 三个 component 内的 **全部 14 个 ELF**，包括 driver、LLVM、rustdoc、proc-macro server、linker wrappers、objcopy 和共享 std。每个文件记录实际 `DT_NEEDED`、interpreter、RPATH / RUNPATH；扫描退出 0，全部与原库存绑定一致。

| 项目 | 新取得的字节观察 | 仍不能推出 |
| --- | --- | --- |
| driver | `librustc_driver-bb2b40829e117684.so`，114,267,984 bytes；直接依赖精确 LLVM 库以及 libdl / libgcc_s / libpthread / libc | driver 可在候选镜像中实际装载 |
| LLVM | `libLLVM.so.22.1-rust-1.97.1-stable`，165,558,632 bytes；依赖 librt / libdl / libpthread / libm / libz / libgcc_s / libc | 根工具摘要列出的依赖已经覆盖传递依赖；尤其不能漏掉此次补见的 librt |
| 外部库名并集 | `libc.so.6`、`libdl.so.2`、`libgcc_s.so.1`、`libm.so.6`、`libpthread.so.0`、`librt.so.1`、`libz.so.1` | 同名库存候选已被 loader 选中，或具备要求的符号版本 |
| interpreter 并集 | `/lib/ld-linux-aarch64.so.1` | 该路径及其 symlink 目标、实际字节、包归属和来源已复核 |

输出中的 `bundled_name_candidates` 只是同名库存候选；`loader_resolution` 始终为 `not-assessed`，不模拟 ELF loader，也不执行 `ldd`。符号版本、运行时 `dlopen`、子进程工具与系统库自身的递归依赖未覆盖。历史镜像库存中的 `libc6=2.36-9+deb12u14`、`libgcc-s1=12.2.0-14+deb12u1`、`zlib1g=1:1.2.13.dfsg-1` 只能作为下一轮包归属核对入口，不是本轮实际库字节证据。

### 尚待补齐的来源材料

| 项目 | 下一份精确材料 / 判定 | 本次状态 |
| --- | --- | --- |
| Rust 公钥绑定 | 在完整指纹及已留存公钥字节下明确身份信任来源、弱自认证处理、撤销 / 过期与密钥更新规则 | 继续保留阻断；没有调整 GnuPG policy 或接受弱算法 |
| musl libc 与对应 CRT | 对应 Rust `1.97.1` / commit `8bab26f4f68e0e26f0bb7960be334d5b520ea452` 的实际发布构建配方、musl 精确源包 / patch / 配置 / 许可，再映射实际 archive 成员 | target 源码的 musl 版本声明不能替代实际构建配方；本轮未取得新源码材料 |
| compiler CRT / unwind | 分别确认 9 个 CRT 的来源归属及 `libunwind.a` 构建输入；核对使用的是哪些 LLVM / compiler-rt / 其他上游材料 | 不根据文件名或根部双许可证推断来源；仍未逐对象验收 `.a` |
| 系统库与 builder | 固定镜像下上述 7 个库名、loader 的实际解析链、文件摘要、包归属、符号版本及包 / source 链；同时核对安装命令所用工具 | 此次补齐 archive 内 14 个 ELF 的静态观察，系统库侧未执行 |
| kernel tag | 获取原始 annotated tag 对象、记录对象身份并核对签名与 peeled commit | 历史 JSON 对应与 tar 验签继续各自成立，原始 tag 尚未验签 |

公钥策略的审阅建议是先保持当前严格阻断：优先补现代认证材料；若上游材料仍无法满足，须另行审阅“直接固定公钥身份”的窄信任决策，明确它不依赖旧 UID 自认证建立发布者身份。不能只增加允许 SHA-1 的工具选项。本段是候选处理顺序，不接受新信任策略，也不要求安装另一套验签工具。

9 月 10 日只读查询了 [Rust Forge](https://forge.rust-lang.org/infra/other-installation-methods.html)和 [simpleinfra #218](https://github.com/rust-lang/simpleinfra/issues/218)：前者继续给出手工验签入口，后者展示旧自认证被现代策略拒绝的问题。这些网页只作审阅线索，不构成新身份认证材料。通过网页读取工具请求上述精确 Rust commit 的 `src/ci/docker/host-aarch64/dist-aarch64-linux/Dockerfile` 时返回 `Cache miss`；未取得正文，不能据此判定该路径不存在，也未把它计为源码配方已核对。未改用邻近版本代替精确输入。

### 安装切片与复核

已形成[隔离安装切片审阅](../../checker-runtime-linux-install-slice-review.md)：固定镜像、精确三包与四 component、新前缀、容器权限、时限、日志、安装器旧 manifest / ldconfig 副作用，以及提取 / 两包间核对 / 清理要求。它保留来源前置和分段执行核对，不是无人值守安装脚本；未提出“现在安装即可通过”的结论。

本次实际命令（仓库根）：

```bash
python3 docs/records/rust-linux-input-review/inspect-host-dependencies.py \
  .tmp/rust-linux-inputs-bb014fd/rust-1.97.1-aarch64-unknown-linux-gnu.tar.xz \
  > .tmp/rust-linux-inputs-bb014fd/host-dependencies-2026-09-10.json
python3 docs/records/rust-linux-input-review/check-host-dependencies.py
```

输出原样留存，方法、被复用方法、库存与 archive 摘要见 JSON。[6 项合成检查](check-host-dependencies.py)通过，覆盖字节篡改、大小 / 架构错误、动态段越界、传递外部依赖保留及同名歧义不升级为 loader 解析成功；不替代真实装载或密码学验证。它们按本记录显式运行，未加入默认仓库门禁。

同时通过原有 `check-diagnostics.py` 的 8 项检查、`check-repo.sh` 的 1,038 文件仓库检查、安装审阅所有 bash 代码块的 `bash -n` 和 `git diff --check`；保留输出的三个方法摘要与实际文件一致。未重跑 Rust / CI、真实验签、容器安装或产品执行；bash 语法检查不等于安装验证。本轮更改未提交、未推送。

## 2026-09-10：精确源码配方补查

上述首轮更改已提交为 `1262570`；随后 `e849aff` 接受 ADR 0015 并落实维护责任。经本次明确授权，仅重新取得既有 Rust `1.97.1` source 对象，242,787,896 bytes / SHA-256 与历史 source acceptance 一致；未安装或切换 Rust。

[源码配方核验记录](source-recipes-2026-09-10.md)完整扫描 323,914 个逻辑成员，选择 255 份文本并留存方法 / 元数据：5 个 CRT 从 musl 库目录复制，4 个由 LLVM compiler-rt 构建，libunwind 进入源码树内 LLVM 构建路径。已定位 AArch64 musl 对应 Dockerfile、musl-cross-make 精确 commit、musl 版本与两份随包 patch；相关 LLVM 源码和许可原文已取得。配方不等于发布 binary 的构建证明，外部 musl-cross-make / musl 原始材料、宿主库及签名策略仍待闭合；不改写上面的历史观察。

## 2026-09-10：固定 musl-cross-make 源码补查

精确 Rust 配方批次已提交为 `c38a1c1`。本轮获准取得脚本引用的 musl-cross-make 固定 commit，归档 213,688 bytes，完整盘点 340 个文件；[详细记录](musl-cross-make-2026-09-10.md)及其库存 / 下载日志 / 方法已留存。实际 Makefile 使用 Binutils 2.44 / GCC 9.4.0，与 Rust 脚本旧注释不同；七项源依赖和四份 musl patch 已列明，上游依赖使用 SHA-1 校验，构建工具许可不覆盖 patch 与产物。

该批只读诊断没有下载七项依赖、应用 patch、安装或构建；来源真实性、原始依赖许可、发布构建关联与最终链接继续待验收。新增 8 项合成检查和 1,048 文件仓库检查通过；历史验签、Rust / CI 和产品运行未重验，旧记录保持原样。

## 2026-09-10：musl 原包、签名与补丁应用

固定 musl-cross-make 批次已提交为 `c7f7f60`。本轮[实际取得 musl 1.2.5 原包及认证材料](musl-source-2026-09-10.md)，完整盘点 2,697 文件，读取 COPYRIGHT / 文件级许可和 libc / CRT 配方；四份既有 patch 在固定镜像的临时副本中以 `fuzz=0` 应用成功，行偏移与三个结果文件摘要均保留。LIBCC 出现在已见 libc.so 链接规则中，libc.a 归档规则没有直接合入它。

**musl 分离签名本身及公钥自认证均为 SHA-1，严格签名条件未通过。** GnuPG 退出 0 不等于来源接受；最终诊断命令保持退出 1。首次补丁诊断因名单外输出中止，随后显式关闭 mismatch 备份并补充失败日志，在原白名单下复验成功；原失败与方法差异留存。新增 8 项合成检查与 1,060 文件仓库检查通过，不覆盖或改写实际签名拒绝。

本次没有安装、编译或执行 musl / 产品代码；两次短时离线容器和临时 keyring / 源码副本均已删除，输入与日志保留。下一步先处理 musl 强摘要来源认证和公钥绑定策略，其余依赖、宿主库、发布构建关联与最终链接继续待验收。

## musl 强摘要认证候选

2026-09-10 提交原包诊断后，先完成 [Debian 归档认证路线审阅](musl-authentication-route-2026-09-10.md)，随后获准完成 [强摘要链实际诊断](musl-debian-auth-2026-09-10.md)：trixie 两个必要签名角色、自认证及 Sources → 原包 SHA-256 均通过本批条件；首轮 GnuPG 崩溃和路径解析拒绝也已留存。原包与既有字节一致；不改变 musl 上游严格签名拒绝或正式 acceptance 状态。

基于 `70b7235` 的[后续信任审阅](musl-debian-auth-2026-09-10.md#仅限该原包的信任审阅待确认)推荐有条件采用仅限该原包的 Debian 归档认证路线；该审阅只复算已有字节及读取旧索引。提交 `bbbe083` 后项目所有者已[确认方案](musl-debian-auth-2026-09-10.md#项目所有者确认与执行顺位)，并另行授权完成[指纹页面与精确 keyring 包补证](musl-trust-inputs-2026-09-10.md)：页面两主指纹一致，包摘要匹配，包内完整 keyring 与旧诊断输入逐字节相同。公告 / 公钥链接未访问，密钥状态、验证工具来源与持久材料仍待补齐；正式 acceptance 未通过，未运行容器或安装。

上述确认与补证已提交为 `ef02b43`，随后按继续下一步的要求完成[两份公钥与 trixie 公告读取](musl-key-status-2026-09-10.md)。两公钥与精确包内字节一致，公告的 archive 身份和摘要匹配；公告不含 stable release 主指纹，签名及第三方认证未核验。下一步集中审阅最小验证环境来源，再作指定时点的完整密码学复核；旧镜像只读身份观察不改变 `acceptance = not-assessed`。

## 2026-09-12：musl 验证环境与验签准备

今日 8 笔提交完成验证工具候选及固定包 / 源码关联、18 个工具 / 许可包的内容与静态布局、本机独立归档和离线恢复、rootfs tar 组装与读回、四项受控动态诊断，以及四份验签输入与严格双角色状态判定。逐笔代码 / 文档核对和实际验证入口见[日终回顾](../2026-09-12-closeout.md)。

此前“持久材料仅依赖缓存”“工具信任终点待接受”等措辞保留相应历史时点。本机独立归档已形成，异盘备份尚未落实；固定工具和宿主已被接受为本次诊断可信输入。GnuPG 2.4.7 版本、目录及 loader 正常诊断不等于完整密码学验签或 production qualification。镜像保留在 OrbStack，四个短时容器已删除；新验签入口尚待实现，`source_acceptance = not-assessed` 和上游 SHA-1 拒绝不变。下一顺位只见[当前状态](../../status/current.md)。

## 2026-09-16：双角色验签与来源验收审阅

[真实九项验签](musl-verification-success-2026-09-16.md)已完成，包含两角色、自认证、完整摘要链及四个预期拒绝负例；首次启动前失败与修正原文保留，九个容器已删除。此前“入口尚待实现”是 9 月 12 日时点，已由本批补齐。

[来源验收审阅](musl-source-acceptance-review-2026-09-16.md)逐项对应既有条件，离线重算全部九项与 66 条日志一致，并复核本机归档 132 个路径 / 87 个对象。项目所有者随后确认固定工具 / 宿主及公钥材料时点下的限定声明，该精确原包的限定来源验收通过；历史诊断 JSON 中的 `not-assessed` 保留批次时点含义。异盘保留作为介质失效风险并行安排，不新增为密码学验收门槛。上游 SHA-1 拒绝、公共验收契约与安装停止线不变。

## 2026-09-16：备份、其余来源路线与 MPC / MPFR

[固定 musl 快照备份](musl-backup-2026-09-16.md)已在交付时完成 1,628 个文件的恢复与三个离线导出核对。[其余六项来源路线](musl-remaining-sources-2026-09-16.md)区分格式、重打包和版本缺失；随后[两个原包及签名](mpc-mpfr-inputs-2026-09-16.md)取得并匹配索引，盘点 920 个文件。[公钥材料审阅](mpc-mpfr-key-inputs-2026-09-16.md)识别 MPFR 新旧主钥以及 MPC 到期声明；结构观察不等于身份或真实验签，两者来源验收仍待完成。

两批新增材料已分别本机归档和恢复，未加入先前 Downloads 包。日终三个交付文件已不在 Downloads 原路径，项目内最终包仍匹配原摘要；目标副本与异盘状态未核实。今日收尾前四笔提交及文档收尾、65 项日终合成检查和四份导出重算见[日终回顾](../2026-09-16-closeout.md)。下一顺位只见[当前状态](../../status/current.md#下一步)，历史批次的“尚未取得 / 未提交”保留当时含义。

## 2026-09-25：MPFR 离线验签

[本批切片](mpfr-verification-entry-2026-09-25.md)完成固定归档读回、多 UID 与原始自认证对应、六次调用的有界执行入口及 38 项合成检查；既有编排 / 采集 65 项回归通过。选定主钥的三份旧钥 SHA-1 认证保留但不作为本轮认证依据，真实密码学、自认证与来源接受仍待验收。没有运行 Docker / GnuPG、下载或安装；真实执行须按记录中的精确范围取得本次授权。

准备切片提交为 `9fd5893` 后，按项目所有者本次授权完成[六项真实诊断](mpfr-verification-entry-2026-09-25.md#本次授权与真实执行结果)：正向验签及三个预期拒绝负例均符合要求，六个容器已删除。45 条命令日志和六项判定离线重放一致，新增 7 项导出检查通过；来源接受仍为 `not-assessed`，下一步进入固定原包的限定来源接受审阅。前段“未运行”保留准备阶段事实。
