# musl-cross-make 固定源码与依赖配方核验

日期：2026-09-10；基线：`dev` / `c38a1c1`。

用途：为工具来源与 guest 维护者记录 Rust `1.97.1` 引用的外部构建工具、依赖和补丁。只报告实际源码观察；不接受新工具、弱摘要策略、许可证政策或产品执行能力。本轮仅下载一个获准归档，未执行上游脚本、安装、构建或获取其依赖包。

## 实际输入与复核边界

取得 [musl-cross-make 固定 commit 归档](https://codeload.github.com/richfelker/musl-cross-make/tar.gz/3635262e4524c991552789af6f36211a335a77b3)。commit 来自前轮已绑定 Rust 源码的 `musl-toolchain.sh`，不是本轮选择的最新版本。

| 对象 | 实际身份 |
| --- | --- |
| 请求 commit | `3635262e4524c991552789af6f36211a335a77b3` |
| gzip 归档 | 213,688 bytes；SHA-256 `60bed670d689d5c2164020960df36b80189dc5617e9763e023672f98a99d567e` |
| 展开 tar | 1,597,440 bytes；SHA-256 `cb051a24ba421cd4768fc41d078f625d8eac52f617a93d60a4a0119a508c537c` |
| 逻辑库存 | 385 个成员，其中 340 个文件；无链接或特殊成员 |
| PAX comment | 与请求 commit 相同 |

这些 SHA-256 是本次取得字节的观察和后续复核 pin，不是独立上游认证。归档目录名和 PAX comment 相符也不等于 Git 对象重建、commit 签名验证或发布构建证明；输出的 `commit_authentication` 与 `acceptance` 均保留 `not-assessed`。

首次沙盒内 curl 返回 7，未连接到本机代理；经沙盒外授权重试返回 0 / HTTP 200，耗时 1.318636 秒。两次 stdout、stderr、headers、退出码及 curl 版本 / 选项完整保存在 [fetch 记录](musl-cross-make-fetch-2026-09-10.json)。固定 HTTPS / HTTPS redirect、TLS ≥ 1.2、20 秒连接超时、60 秒总时限及 4 MiB 上限，没有自动重试、安装或运行下载内容。

[只读方法](inspect-musl-cross-make.py)先核对固定大小 / SHA-256，再有界解压和读取；上限为压缩 4 MiB、tar 32 MiB、单成员 8 MiB、4,096 个成员，复用已有路径检查，拒绝逃逸、重复、链接 / 特殊成员、非零尾部和错误 commit comment。它是 Python `tarfile` 逻辑成员诊断，不是物理 tar 验收或产品提取器。原包及带全文的扫描 JSON 留在忽略目录 `.tmp/musl-cross-make-review-c38a1c1/`；仓库只保留 [340 文件的路径 / 长度 / 摘要及方法身份](musl-cross-make-inventory-2026-09-10.json)，不复制上游实现或补丁正文。

## 实际依赖版本及下载校验

[固定 Makefile](https://github.com/richfelker/musl-cross-make/blob/3635262e4524c991552789af6f36211a335a77b3/Makefile) 5–11 行指定下表默认版本；Rust 脚本命令行将 `MUSL_VER` 指定为同一 `1.2.5`，并将 `LINUX_VER` 从默认 `headers-4.19.88-2` 覆盖为 **`headers-4.19.88`**。归档不含 `config.mak`，Rust 已读脚本也没有创建该文件；下表按这套已见源码推导，不声称实际发布构建环境不存在额外覆盖。

| 配方输入 | 精确归档名 | 随该 commit 保存的 SHA-1 声明 |
| --- | --- | --- |
| Binutils | `binutils-2.44.tar.gz` | `568ba0a286cf79520572c1597a203c1aafd462de` |
| GCC | `gcc-9.4.0.tar.xz` | `bf6d6480fb32e5a28dac849449f533a84d4e6547` |
| musl | `musl-1.2.5.tar.gz` | `36210d3423172a40ddcf83c762207c5f760b60a6` |
| GMP | `gmp-6.3.0.tar.xz` | `b4043dd2964ab1a858109da85c44de224384f352` |
| MPC | `mpc-1.3.1.tar.gz` | `bac1c1fa79f5602df1e29e4684e103ad55714e02` |
| MPFR | `mpfr-4.2.2.tar.xz` | `a63a264b273a652e27518443640e69567da498ce` |
| Linux headers | `linux-headers-4.19.88.tar.xz` | `de12b9c8ae2de9e85056a36be9f0fcc0a1e4abe9` |

每条声明来自 `hashes/<归档名>.sha1` 的实际正文，其文件 SHA-256 可在库存复核。**本轮没有下载或验证这七个归档**；表中 SHA-1 不是本项目新增的 acceptance。Makefile 28、90 行的下载校验确实使用 `sha1sum -c`；这是与 Rust 公钥旧 UID 自认证不同的另一处弱摘要边界，不能混为同一问题，也不能通过本地补算 SHA-256 自动得到上游身份认证。

已见配方的原始下载入口：

- GNU 包以 `https://ftpmirror.gnu.org/gnu` 为根；Binutils / GMP / MPC / MPFR 分别追加组件目录和归档名，GCC 追加 `gcc/gcc-9.4.0/gcc-9.4.0.tar.xz`。实际 mirror redirect 和下载对象本轮未观察。
- musl 为 `https://musl.libc.org/releases/musl-1.2.5.tar.gz`。
- Rust 命令行覆盖的 headers 入口为 `https://ci-mirrors.rust-lang.org/rustc/sabotage-linux-tarballs/linux-headers-4.19.88.tar.xz`；不替换为 Makefile 默认站点或带 `-2` 的包。

Rust 脚本顶部仍写 Binutils `2.31.1` / GCC `9.2.0`，与固定 checkout 的有效赋值不符；来源清单应采用上述实际配方，不能从旧注释建立 build lock。此次不改写第三方源码。`ISL_VER` 没有默认赋值，不把可选 ISL 自动列为已选输入。

Makefile 还定义外部 `config.sub` 下载规则和 `CONFIG_SUB_REV=3d5db9ebe860`；但已见 `all` / `install` 依赖链没有引用该下载目标，litecross 使用 GCC 源目录内的 `config.sub`。因此不把规则的存在升级为第八个实际下载输入；后续应在 GCC 原包中核对其内置脚本与实际构建日志。

## 补丁集合与 musl 构建关联

Makefile 140 行把选定版本目录的全部 patch 经 shell glob 展开、串接后传给 `cowpatch.sh -p1`，没有按目标架构过滤。固定归档包含 GCC `9.4.0` 的 19 个补丁、Binutils `2.44` 的 4 个补丁、musl `1.2.5` 的 2 个补丁；其余表列版本没有对应补丁文件。库存保留每个文件的名称和摘要，不因某些补丁名指向 SH / RISC-V 等架构而从配方中删除。

Rust 另复制两份已绑定补丁，形成如下 musl 文件集合；数字前缀表示配方预期顺序，实际 shell / locale 与 patch 应用结果仍待构建材料核对：

| musl patch 目标名 | 原文来源及 SHA-256 |
| --- | --- |
| `0001-cve-2025-26519-p1.diff` | 本次 checkout；`89ec5af152afb9c0ba8e37ecdca63a7a7fd13b60247f1a2d8024a59baa18e7dc` |
| `0002-cve-2025-26519-p2.diff` | 本次 checkout；`d5b88fe87f9554238bdd69235694b0d50bb909f38149a7be417a0240a490e813` |
| `0003-cve-2026-6042.diff` | Rust 源包的 `musl-cve-2026-6042.diff`；`444fa70e52ca158fb7d4bad560637790bbf8f72e80b82fff840dd66fa83091e3` |
| `0004-cve-2026-40200.diff` | Rust 源包的 `musl-cve-2026-40200.diff`；`1ee29f64f9ca8e8ad7c349779d661ff6b52126a27575d3586981357a52c406fb` |

前两份修改 `src/locale/iconv.c`；第三份修改该文件并新增 `src/locale/gb18030utf.h`；第四份包含三个修改 `src/stdlib/qsort.c` 的补丁段。第一、二、三份中 iconv 的 abbreviated index 标记依次衔接 `9605c8e9 → 008c93f0 → 52178950 → 4151411d`，只是文本对应线索，不能替代原包上的应用验证或安全修复验收。本轮没有运行 `patch` 或 `cowpatch.sh`。

[litecross/Makefile](https://github.com/richfelker/musl-cross-make/blob/3635262e4524c991552789af6f36211a335a77b3/litecross/Makefile) 84–85、112 行给 musl 配置 `--prefix= --host=$(TARGET)`，交叉路径使用刚构建的 `xgcc`，并将该 GCC 目标下的 `libgcc.a` 传为 `LIBCC`。因此 musl 构建输入边界也包含 GCC 支持库，不能只列 musl tar；是否有具体对象进入最终 `libc.a` 还需源码及 `.a` 对象检查。headers 安装使用目标映射与 `headers_install`，不等于本项目拟构建 kernel 的版本身份。

结合前轮 Rust bootstrap 的已读路径，外部 musl 输出对应 libc / 5 个 CRT；LLVM compiler-rt 的另外 4 个 CRT 和 libunwind 仍分别沿用[精确 Rust 配方记录](source-recipes-2026-09-10.md)，不因发现 GCC 构建链而重新归属为 GCC 产物。

## 许可材料与下一步

本次已取得 `COPYRIGHT`、`LICENSE`、`README.md`、`cowpatch.sh` 原文并绑定摘要。`COPYRIGHT` 明确将构建工具 / 文档的 MIT/Expat 授权与 patches、构建产物分开：patch 沿用被修改上游项目的条款，产物保留原上游许可；不能把整个链统一标为 MIT。`cowpatch.sh` 自身另带文件级许可及免责声明，需在最终材料中单列复核。

`cowpatch.sh` 头部还明确说明它未对恶意 patch 提供完整路径保护。后续若需要应用 patch，必须先审阅输入路径并在精确隔离范围内执行；本次未把该脚本作为本项目的安全提取 / patch 工具，也未运行 `make -n`，因为 Makefile 求值本身含 shell 调用。

下一步优先取得精确 musl `1.2.5` 原包、可信摘要 / 签名材料和 COPYRIGHT / 文件级许可，再核对上述四文件补丁能否应用及得到的源码身份；七项依赖的完整来源、GCC 支持库与分发材料随后分别闭合。新下载、patch 执行、安装与构建仍按精确范围授权。

此外仍缺 commit / 发布构建关联、builder 来源、宿主库 / loader / 符号版本、Rust 公钥绑定策略、kernel 原始 tag 和最终链接验收。本轮没有改动历史 acceptance、公共格式、依赖 / lockfile、PATH 或系统配置，active runtime 仍为 0。

## 实际验证与重跑

新增 8 项合成检查通过，覆盖诊断不升级认证、路径逃逸、链接、重复路径、解压前摘要、展开限额、commit comment 和非零尾部；不替代真实签名或构建。完整实际扫描退出 0，340 文件元数据与本地全文输出一致。1,048 文件仓库门禁与 `git diff --check` 通过，库存重跑逐字一致，方法摘要及两次下载原始日志均核对一致；Rust / CI、安装、patch 应用、链接和产品执行均未运行。

在仓库根、已取得上述精确归档后：

```bash
python3 docs/records/rust-linux-input-review/inspect-musl-cross-make.py \
  .tmp/musl-cross-make-review-c38a1c1/musl-cross-make-3635262.tar.gz \
  > .tmp/musl-cross-make-review-c38a1c1/inventory-recheck.json
python3 docs/records/rust-linux-input-review/check-musl-cross-make.py
./scripts/check-repo.sh
git diff --check
```

首次探索使用忽略目录中的准备脚本；最终留存方法加入固定输入入口和 commit comment 核对后重新扫描成功。最终实际命令带 `--include-text`，Git 中库存只移除每个文件的 `text`；同一 Python / 方法下默认输出应与留存 JSON 一致。原包、全文观察和下载日志保留供重读。
