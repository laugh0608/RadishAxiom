# Rust 1.97.1 静态 runtime 构建配方核验

日期：2026-09-10；基线：`dev` / `e849aff`。

用途：记录本次获准重新取得的精确 Rust 源包，核对 Linux musl payload 中 libc、CRT、unwind 的来源入口。读者为工具来源与 guest 维护者。本记录只报告源码和既有 binary 库存之间的静态对应，不接受新的工具、许可证政策、公共格式或产品运行能力；没有安装、构建或执行源码。

## 实际下载与源码身份

获准从 `https://static.rust-lang.org/dist/rustc-1.97.1-src.tar.xz` 取得单个源码包；没有取得其他版本的 Rust、musl、musl-cross-make、镜像或新工具。

| 身份 | 实际结果 |
| --- | --- |
| 原始长度 / SHA-256 | 242,787,896 bytes；`0ed06fdaffd4722a7702e0b4eebfafc897ab8f513e8e1b247cdd7e5c6df6ded2` |
| 既有验收对应 | 与 [Rust source acceptance](../../../contracts/toolchain-payload-acceptance-v0.1/records/rustc-1.97.1-source.acceptance.json) 的同一 source 对象一致；不改其历史签名状态或方法 |
| 源码内版本 / commit | `1.97.1 (8bab26f4f 2026-07-14)`；`8bab26f4f68e0e26f0bb7960be334d5b520ea452` |
| 完整 tar 流 | 3,772,501,504 bytes；SHA-256 `535ef70ed7ce23b36e4673c11ef175e36281e6be88f989c1e7f1dc4026ea0a1f` |
| 归档逻辑成员数 | 323,914，与既有 source 库存一致 |

原包保留在忽略目录 `.tmp/rust-source-review-1262570/`。首次沙盒内 curl 返回 7，未连接到本机代理；经授权的沙盒外网络重试返回 0、HTTP 200，37.927538 秒下载完整对象。两次 stdout / stderr / headers、退出码、长度 / 摘要、curl 版本和选项留存在 [fetch 观察](source-fetch-2026-09-10.json)，失败未被成功覆盖。没有把网络成功或摘要相同升级为新的签名验证。

[只读扫描方法](inspect-source-recipes.py)先核对原始大小与摘要，再用已留存的 XZ reader 完整扫描并重算压缩流 / tar 流；选择 255 份构建、配置、源码及许可文本，逐项保存路径、长度、摘要和检索行号。未提取为源码目录，也未执行下载所得脚本。完整源包与本地带文本的扫描 JSON 可重读原文；Git 仅保存 [255 文件元数据](source-recipes-2026-09-10.json)，不复制上游源码正文。

扫描是固定输入下的逻辑成员诊断，不替代旧 v0.1 物理归档验收。宿主诊断沿用 256 MiB XZ decoder / 4 GiB tar 上限；单份选定文本最多 4 MiB、累计最多 16 MiB、最多 2,048 份、完整成员最多 400,000。预先列出的 `library/unwind/build.rs` 在此源包中不存在，输出如实保留该未匹配路径；实际构建入口位于下述 bootstrap 文件，不能用邻近版本的旧路径补齐。

## 静态对象的构建来源对应

本节所有源码路径均相对于 `rustc-1.97.1-src`。行号来自本次实际字节，可用扫描方法重读；链接指向同一 Rust commit 的源码导航。binary 长度和摘要引用 [musl 实际库存](summary.json)，本轮未重新扫描 binary，也未做重建比较。

| 已有 payload 对象 | 该版本源码定义的来源路径 | 判定边界 |
| --- | --- | --- |
| `libc.a` 和 `crt1.o`、`Scrt1.o`、`rcrt1.o`、`crti.o`、`crtn.o` | [compile.rs](https://github.com/rust-lang/rust/blob/8bab26f4f68e0e26f0bb7960be334d5b520ea452/src/bootstrap/src/core/build_steps/compile.rs) 392–405 从 `musl_libdir` 复制这六个文件 | libc 加 5 个 CRT 属于配置的外部 musl 库目录；不能按 Rust 根许可证覆盖 |
| `crtbegin.o`、`crtbeginS.o`、`crtend.o`、`crtendS.o` | 同文件 407–412 调用 `llvm::CrtBeginEnd`；[llvm.rs](https://github.com/rust-lang/rust/blob/8bab26f4f68e0e26f0bb7960be334d5b520ea452/src/bootstrap/src/core/build_steps/llvm.rs) 1609–1663 使用源码树内 `compiler-rt/lib/builtins/crtbegin.c` / `crtend.c` | 这 4 个 CRT 由 LLVM compiler-rt 源码构建；本次没有将它们误归入 musl 或 GCC CRT |
| `libunwind.a` | compile.rs 428–430 对非 s390x 的相应 target 调用 `copy_llvm_libunwind`；333–338 进入 `llvm::Libunwind`；llvm.rs 1685–1828 从 `src/llvm-project/libunwind` 构建 | 此源码路径不是从 musl-cross-make 输出直接复制 libunwind；脚本顶部注释不能替代 bootstrap 实际代码 |

[target_selection.rs](https://github.com/rust-lang/rust/blob/8bab26f4f68e0e26f0bb7960be334d5b520ea452/src/bootstrap/src/core/config/target_selection.rs) 99–100 的条件为 target 含 `musl` 且不含 `unikraft`；`aarch64-unknown-linux-musl` 满足该条件且不是 s390x。[bootstrap lib.rs](https://github.com/rust-lang/rust/blob/8bab26f4f68e0e26f0bb7960be334d5b520ea452/src/bootstrap/src/lib.rs) 1414–1436 优先使用配置的 `musl-libdir`，否则从配置的 musl root 加 `lib`；不能在本项目中依赖上游未配置时的 `/usr` 分支。

CRT 的配方使用 target C compiler、`-O3`、C11、`CRT_HAS_INITFINI_ARRAY` 和 `EH_USE_FRAME_REGISTRY`，将每份生成对象分别复制 / 重命名为带 `S` 和不带 `S` 的文件。既有 musl 库存中 `crtbegin.o` 与 `crtbeginS.o` 长度 / SHA-256 相同，`crtend.o` 与 `crtendS.o` 也相同；这与配方行为一致，只是对应观察，不是构建证明。

libunwind 的配方列出 5 份 C / assembly 与 3 份 C++ 输入：`Unwind-sjlj.c`、`UnwindLevel1-gcc-ext.c`、`UnwindLevel1.c`、`UnwindRegistersRestore.S`、`UnwindRegistersSave.S`、`Unwind-EHABI.cpp`、`Unwind-seh.cpp`、`libunwind.cpp`。本次均已取得原文与摘要；配方还引用 include 目录、target 编译器 / archiver 及 `cc` 构建支持。C++ 路径关闭 exceptions / RTTI、使用 `-nostdinc++`；这些设置不能替代对最终 `.a` 对象、符号和链接依赖的检查。

## AArch64 musl 发布配方与外部输入

本次从完整源包成功读到上轮网页接口未返回的 GNU host Dockerfile。它位于 `src/ci/docker/host-aarch64/dist-aarch64-linux/Dockerfile`，配置 GNU host，不能自动覆盖 musl std 的构建来源。

源码树中与 AArch64 musl 对应的入口是 [host-x86_64/dist-arm-linux-musl/Dockerfile](https://github.com/rust-lang/rust/blob/8bab26f4f68e0e26f0bb7960be334d5b520ea452/src/ci/docker/host-x86_64/dist-arm-linux-musl/Dockerfile)：以 `ghcr.io/rust-lang/ubuntu:22.04` 为基线，调用 `musl-toolchain.sh aarch64`，设置 `HOSTS=aarch64-unknown-linux-musl`、`--musl-root-aarch64=/usr/local/aarch64-linux-musl`，随后为该 host / target 运行 dist。这里是源代码中的发布入口对应；本轮没有取得证明实际发布任务执行了这些精确输入的构建记录。

[musl-toolchain.sh](https://github.com/rust-lang/rust/blob/8bab26f4f68e0e26f0bb7960be334d5b520ea452/src/ci/docker/scripts/musl-toolchain.sh) 的有效命令固定：

- musl-cross-make 仓库 `https://github.com/richfelker/musl-cross-make`，checkout `3635262e4524c991552789af6f36211a335a77b3`；本次没有下载该仓库。
- `MUSL_VER=1.2.5`，Linux headers 标识 `headers-4.19.88`，来源站点 `https://ci-mirrors.rust-lang.org/rustc/sabotage-linux-tarballs`。
- 复制随本次 Rust 源包提供的 `musl-cve-2026-6042.diff`、`musl-cve-2026-40200.diff` 到 musl-cross-make patch 目录；两份 patch 的字节摘要已留存。名称按源文件记录，本次不作漏洞覆盖或安全状态判断。
- 编译器和 binutils 的精确配方仍须读取该固定 musl-cross-make commit 的 Makefile、hashes、patches 与配置；脚本头部提到的 Binutils / GCC 版本只是注释，不能升级为实际 build lock。

同目录的通用 `musl.sh` 也被扫描，它包含另一条直接下载 musl 的路径及额外内联 patch。AArch64 musl Dockerfile 实际调用的是 `musl-toolchain.sh`，不能把两套脚本的 patch 列表合并后声称全部已用于 AArch64 payload。Dockerfile 的 `crt-static=false` 是该 bootstrap 配置，不改变 target 源码的默认静态 CRT 定义，也不证明本项目最终 init ELF 的链接结果。

上游 Dockerfile 使用 image tag、安装脚本和外部构建输入，本次没有取得这些镜像 / 包的完整精确身份；也没有把它们作为本项目已验收 builder。阅读配方不授权执行其中的 clone、下载、安装、链接或系统目录写入。

## 许可材料与仍未闭合的边界

`crtbegin.c`、`crtend.c` 及上面 8 份 libunwind 源文件的头部明确标有 `Apache-2.0 WITH LLVM-exception`。两份 LLVM `LICENSE.TXT` 和其摘要已取得；它们也保留 legacy / 第三方条款，不能只据顶层标题对所有材料作统一授权判断。

`library/compiler-builtins/LICENSE.txt`、相关 Cargo.toml 与 libm 许可文件亦已取得。它们是 Rust 源包内不同组件的归属材料，不等于此次 binary 所带外部 `libc.a` 的精确 musl COPYRIGHT / 文件级许可。该固定 musl-cross-make checkout、musl 原始 tar、patch 后的对应源码和许可仍未取得；不从 rust-lang/libm 的衍生说明反推整份 libc 的许可。

本轮将“CRT / unwind 构建入口不明”收敛为精确源码路径和外部输入清单，但以下条件仍未满足：

1. musl-cross-make 固定 commit 的源码、依赖摘要、patch 集合和许可，以及其实际选定 musl / GCC / binutils / headers 输入；获取这些新材料仍需精确授权。
2. 原有 SHA-1 自认证的 key-binding policy、builder 来源、宿主系统库 / loader / 符号版本，以及 kernel 原始 tag 验签；本轮未执行容器或其他验签程序。
3. 发布 binary 与实际构建输入的可核对关联、`.a` 对象级检查和最终链接验收。配方存在、文件同名及 CRT 成对摘要一致均不能替代这些证据。

没有修改主仓依赖 / lockfile、工具版本、PATH、rustup、许可证政策或历史 acceptance；没有安装 / 执行 Rust、构建 init / kernel / checker 或启动产品 VM。后续安装继续遵循[隔离安装审阅](../../checker-runtime-linux-install-slice-review.md)。

## 复核入口

本轮实际通过新增 6 项来源诊断检查、原有 `check-diagnostics.py` 的 8 项检查、`check-repo.sh` 的 1,043 文件仓库检查与 `git diff --check`。另行核对 255 文件元数据与本地完整文本观察一致、方法摘要一致、8 个指定 libunwind 源文件的 SPDX 标记均与正文声明相符。未运行 Rust / CI、真实构建、验签或链接测试；本诊断的合成检查仍为显式入口，不宣称已接入默认仓库门禁。

在仓库根、已取得上述精确源包的前提下运行：

```bash
python3 docs/records/rust-linux-input-review/inspect-source-recipes.py \
  .tmp/rust-source-review-1262570/rustc-1.97.1-src.tar.xz \
  > .tmp/rust-source-review-1262570/source-recipes-recheck.json
python3 docs/records/rust-linux-input-review/check-source-recipes.py
./scripts/check-repo.sh
git diff --check
```

首次按构建入口发现扫描 200 份文本，随后把引用到的配置与 LLVM 源码纳入同一方法，最终扫描 255 份；两次均退出 0，完整 tar 身份一致。最终实际调用增加 `--include-text`，输出在忽略目录；留存 JSON 仅移除每个文件的 `text` 字段，其他内容不变。使用相同 Python 版本和方法重跑时，默认输出应与留存 JSON 逐字一致；方法与被复用方法的 SHA-256 已写入输出。

下载使用 `/usr/bin/curl -q`，固定 HTTPS / HTTPS redirects、TLS ≥ 1.2、20 秒 connect timeout、240 秒总时间和 256 MiB 上限；无自动重试或解压执行，原始文件在扫描前后均按既有摘要绑定。精确选项和两次实际日志见 fetch 观察；原包、带文本扫描输出和 stderr 均保留，未清理来源输入。
