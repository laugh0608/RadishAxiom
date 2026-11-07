# 2026-10-23 cvc5 C1 输入接受审阅

用途：记录第 48 项留存、固定 SDK 内容核对、LibPoly 声明审阅与真实验签结果。供 C1 审阅者使用；不提供安装、构建、分发或 solver 运行接受。现行停止线以[输入准备专题](../query/solver-cvc5-input-preparation.md)为准。

## 结果与授权边界

项目所有者要求先留存第 48 项，再推进三个 C1 缺口，解包或验签前说明范围，暂不安装或构建。已完成下面的有限审阅，**C1 仍为 `not-accepted`，`build_ready=false`**。本批不是三个接受决定全部通过：SDK 库存 / 来源关联已补齐；真实检查否定原签名角色预期后，项目所有者接受限定历史三角色方案，后续验证通过；LibPoly 逐文件许可范围问题仍阻断整体接受。

| 缺口 | 实际结果 | 仍需的出口 |
| --- | --- | --- |
| LibPoly | 固定源码 / 头文件与构建文件关联已补审；不能把整库概括成每文件都有 LGPL 声明；原 `Files: *` 冲突保留 | 对固定版本取得能够覆盖 Poly / Polyxx、无文件内声明部分和 memstream 来源的权威澄清，或另行审阅明确的许可接受依据；不能改 GPL 路线、删除功能或宣称是已确认笔误 |
| 快照签名 / 信任 | 初次真实 GnuPG 返回 2；随后在既有 removed-keys 中定位缺失 buster 公钥，经本任务明确接受历史角色 / 身份依据后，三签名、钥匙认证、正文 / 索引绑定和五负例全部通过 | 该缺口按本次本地诊断范围收口；公钥材料时点、HTTPS / 留存包身份依据与未覆盖全渠道最新撤销均保持显式 trusted 限制，不产生通用运行资格 |
| SDK 内容 / copyright | 172 包内容和 control 核对，172 条 copyright 路径均解析；101 `.dsc` 与对应源码文件清单 / 摘要逐项一致；实际工具、CRT、静态库和 `.pc` 身份已固定 | 文件库存与来源关联已补齐；接受仍依赖 LibPoly 许可决定。运行搜索行为、实际对象使用、源码 patch 生效与完整静态闭包留到 C2–C4，不能声称本批完成这些运行检查 |

没有安装、构建、执行 SDK 载荷 / maintainer scripts、应用源码 patch、拉取 / 导入镜像、运行 solver、修改系统配置或远程仓库。先后启动 20 个明确授权的短时 GnuPG 容器（初次失败 1 个、历史方案首次 7 个、完整重跑 12 个），全部确认退出并删除；用户既有 OrbStack 服务未停止。

## 第 48 项与输入留存

[留存入口](solver-cvc5-c1-review-2026-10-23/retain-user-input.py)将用户原 `/private/tmp/cvc5-proxy-test.nLZRSY/libhwasan0.deb` 以排他创建方式复制到 `artifacts/cvc5-c1-retained-2026-10-23/inputs/pool/main/g/gcc-12/libhwasan0_12.2.0-14_arm64.deb`，没有移动 / 删除原文件或建立硬链接。

复制前后均为 998,432 bytes，SHA-256 `c64188f901ecc0f2dd5e3ff9de40d3b295d13e495ca13595f3f5a41615de1aef`。[新留存索引](solver-cvc5-c1-review-2026-10-23/retained-inventory.json)绑定原获取清单和第三次接续独立回读，覆写映射仅限第 48 项，并重新核对全部 **500 文件 / 691,605,464 bytes**。旧获取记录不改写。

第 48 项现在不再依赖系统临时目录；其余 499 项仍引用既有项目 `.tmp` 路径。本地 `artifacts` / `.tmp` 均被 Git 忽略，不等于远端备份；清理前须保留这些复现输入。没有因本批审阅额外复制整套 691 MB 原包。

## SDK 静态内容核对

[检查入口](../../scripts/inspect-cvc5-c1-sdk-content.py)只使用 Python 标准库，流式读取 172 `.deb`、101 `.dsc`、91 Debian patch（89 tar 与 2 `.diff.gz`）和 10 native source。126 项 orig / 附带签名只沿用原字节核对，未展开。tar 不调用 `extractall`；归档路径不映射到宿主文件系统，链接只记录。仅 copyright、control、maintainer scripts、`.pc`、Debian rules / patches 等审阅文本按 SHA-256 保存为无执行权限普通文件；载荷只取摘要 / ELF 头 / 静态成员特征。

资源边界为每次 600 秒、累计展开 4 GiB、单归档 1 GiB、单普通成员 128 MiB、每归档 100,000 项、选中文本累计 64 MiB。初始单文本 8 MiB；遇 GCC `git-updates.diff` 16,564,696 bytes 后明确说明并改为 32 MiB，其他上限不变。[四次结果](solver-cvc5-c1-review-2026-10-23/content-attempts.json)分别保留：

1. 第 59 项 `libmcheck.a` 实为 ELF relocatable，最初按 ar 解析失败；新增显式格式分支和拒绝 executable / 未知格式的测试。
2. 第 250 项达到上述单文本上限；保留失败并增加预算负例。
3. 第 396 项 `.diff.gz` 被误当 tar；确认清单只有 Make / PCRE2 两项 Debian 1.0 diff 后新增明确分支，仅保存文本、不应用补丁。
4. 全部 374 项完成，累计展开 674,818,233 bytes，选中文本 29,873,712 bytes；control 737 项、data 17,125 项、source tar 10,673 项。不是通过跳过失败输入取得成功。

[完整压缩库存](solver-cvc5-c1-review-2026-10-23/content-inventory.json.gz)包含逐项路径、类型、链接目标、bytes、SHA-256、ELF 头及 `.a` 成员概况，不包含第三方源码正文。[派生入口](solver-cvc5-c1-review-2026-10-23/derive-content-review.py)与[关联结果](solver-cvc5-c1-review-2026-10-23/derived-content-review.json)核对：

- 172 包的 Package / Version / Architecture / Source、依赖及冲突字段与已选索引一致。
- 172 个标准 copyright 路径全部可解析，包括 GCC / binutils / ncurses 的目录符号链接；不是因对应包没有独立 copyright 普通文件而漏项。
- 101 `.dsc` 的 Source / Version / Format、`Checksums-Sha256` 文件集合与已选 Sources 元数据完全一致。`.dsc` maintainer 签名未验证；这里是字节和来源声明关联，不是预编译工具已由这些源码重建的证明。
- 重叠非目录路径若内容 / 链接不一致即拒绝；链接在虚拟包根解析，拒绝循环、超深及逃逸，不创建真实 SDK 树。

| 用途 | 已核对的真实包内路径 / 观察 |
| --- | --- |
| compiler | `/usr/bin/aarch64-linux-gnu-gcc-12`、`aarch64-linux-gnu-g++-12`；前端和 collect2 在 `/usr/lib/gcc/aarch64-linux-gnu/12/`。包集合不含 `/usr/bin/cc`、`gcc`、`g++`，不得猜测安装会补出它们 |
| binutils | `/usr/bin/aarch64-linux-gnu-{as,ld,ar,ranlib,strip}` 的链接目标与文件身份均已定位 |
| 生成器 | `/usr/bin/cmake`、`make`、`python3` → `python3.11`、`pkgconf`、`m4`；`/bin/sh` → `dash`。没有运行任何一个工具 |
| sysroot / CRT | glibc 路径 `/usr/lib/aarch64-linux-gnu/`，GCC CRT / runtime 路径 `/usr/lib/gcc/aarch64-linux-gnu/12/`；具体 `.o` / `.a` 见关联结果。仅检查 ELF 头，不认定完整 ABI 或动态运行依赖 |
| Editline | `libedit.pc` 声明 `-ledit`，private 为 `-ltermcap -lbsd`；`libtermcap.a` 实际链接到 `libtinfo.a`；`libbsd.pc` 另声明 private `-lmd`。不能把 `Libs.private` 中的 `-lbsd` 当成 `Requires.private: libbsd`，也不能声称已执行 `pkgconf --static` 或完成传递闭包 |
| 静态候选 | `libedit.a` / `libtinfo.a` / `libbsd.a` / `libmd.a` 分别含 26 / 53 / 48 / 14 个 ELF64 little-endian AArch64 relocatable 成员，未见非 ELF 成员；这不证明所有成员实际进入最终链接 |

copyright 按用途保留而不整体贴许可证标签：Editline 的 BSD-3-Clause、ncurses 的 MIT/X11、libbsd / libmd 多文件许可、GCC 的 GPL / Runtime Library Exception、glibc 的 LGPL 与其他声明、Linux UAPI、Python 及生成工具声明均有精确包内来源。glibc copyright 开头仍写 2.23，包 control / 已选源码版本是 2.36-9；保留原文并按实际包身份绑定，不据陈旧说明改写版本。实际例外适用对象、内嵌头文件与分发条件仍需按最终使用证明，不把所有 SDK 组成认定为 LGPL。

## LibPoly 的可确定事实与澄清范围

固定版本为 `v0.2.1` / `3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a`。`src/CMakeLists.txt` 的 C 目标列出 40 个常规 `.c` 和一个条件 `open_memstream.c`；Polyxx 为 18 个 `.cpp`。公开头文件按 include CMake 的 `.h` 集合安装。没有执行配置，因此条件结果和实际对象集合尚未产生。

在 `src` / `include` 的 134 个 `.c` / `.cpp` / `.h` / `.in` 文件中，94 个含 LGPL v3 或以后版本声明，2 个 `u_memstream.c/.h` 明确保存 Mesa 来源与 MIT 声明，其余 38 个没有该 LGPL 文件内声明（主要是 Polyxx 与条件 memstream）。没有文件内声明不等于无许可，应继续审根许可及覆盖关系，不能反过来声称逐文件 LGPL 都已证实。

根 `LICENCE` 为 LGPL v3；`debian/copyright` 两处 `GPL-3+` 标签、Lesser 正文及 GPL-3 路径冲突仍在（SHA-256 `cd3eb8b96019760e240235847501addff027f870ffe57687c4128ec78a155664`）。`Files: *` 不能仅靠“不进入 debian 构建目录”排除；Debian 格式中的 License 首行本来就表达短名称，见[官方格式说明](https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/)。本批只读查询上游当前同名文件，仍是相同 Git blob；未找到针对该固定版本的权威澄清，没有向上游发送消息。

待澄清的具体问题已收敛为：固定版本中 Poly / Polyxx 的 LGPL 覆盖是否包括无文件内声明的源码 / 头文件；`Files: *` 的 GPL-3+ 与 Lesser 正文哪一处应被修正；条件 `open_memstream.c` 的来源 / 授权；MIT 的 `u_memstream` 保留条款。不能由项目所有者同意承担风险就将上游许可事实改写为确定。原 non-GPL 候选边界保持。

## 签名、宿主变化及首错停止

历史 CLI 为 SHA-256 `c93921f27c941f7661e5478e8af4042e546b66e69707a2b43f31a86cfe9c85d2`；当前 `/usr/local/bin/docker` 指向 OrbStack 2.2.4 wrapper，SHA-256 `4a728ee98f89005a90198a9be791e8fdaebbcb5e6af9721251efe0113df37759`。项目所有者首先明确接受当前 CLI 的限定验签信任。首次[预检失败](solver-cvc5-c1-review-2026-10-23/verifier-preflight-failed.json)发现 daemon 从 `29.4.0 / API 1.54` 变为 `29.8.2 / API 1.56`，在查询镜像或创建容器前停止；项目所有者随后明确接受该 daemon 的相同限定范围。

[再次预检](solver-cvc5-c1-review-2026-10-23/verifier-preflight.json)核对 Linux arm64、cgroup v2、资源能力及安全选项；固定镜像 ID 为 `sha256:55063921d0e996f717092e07dce8041cb2376cc171a070bf9a0a38a5dd16c777`，rootfs tar 为 `f1ac49bc29d33182a9c9a070b70509c739d857369876afbe307b9e9898d6b8b3`，均匹配历史材料。只接受本次诊断，不产生 SDK 构建宿主或 solver 运行资格；旧记录不改写。

[实际入口](solver-cvc5-c1-review-2026-10-23/verify-snapshot.py)复用已审阅的收集、隔离和清理入口，对固定 GnuPG 2.4.7 image 运行一次原文验证。rootfs 只读、无网络、UID/GID 1000、cap drop ALL、no-new-privileges、128 MiB memory / memory-swap、1 CPU、pids 32；两个 16 MiB tmpfs；输入只读，仅状态文件可写；每命令 30 秒、每控制调用 10 秒、流与状态各限 1 MiB。只挂两个公开输入，不挂宿主 socket / 凭据，不导入系统 keyring。

原 InRelease 为 146,972 bytes / SHA-256 `2814476b311085e250ddfdee295907bac45afb66f40dc7c1b35ab41a447c1d6c`；既有公钥环为 55,918 bytes / `506b815cbb32d9b6066b4a2aa524071e071761e7e7f68c3ac74f3061ba852017`。[真实结果](solver-cvc5-c1-review-2026-10-23/snapshot-verification.json)：

- GnuPG exit 2，`NO_PUBKEY 648ACFD622F3D138`，对应声明 signer `0146DC6D4A0B2914BDED34DB648ACFD622F3D138`。
- 两份 `VALIDSIG` 对应 bullseye archive 主钥匙 `1F89983E0081FDE018F3CC9673A4F27B8DD47936` / signer `A7236886F3CCCAAD148A27F80E98404D386FA1D9`，以及 bookworm release 主钥匙 / signer `4D64FEC119C2029067D6E791F8D2585B8783D481`。
- 不存在预期的 bookworm archive 主钥匙 `B8B80B5B623EAB6AD8775C45B7C5D7D6350947F8` 签名；同一文件也不会因再取这把钥匙而补出该签名。
- 解出的正文与固定 Release 逐字节一致；这是部分签名观察，不能覆盖整次命令失败或角色缺失。
- 容器已确认 exited / 非 OOM / 非运行，删除成功。正向不通过即停止，没有继续篡改正文、缺角色或损坏交叉认证负例，也没有做本次钥匙自签名 / 当前撤销全渠道检查。

[Debian 官方 key 页面](https://ftp-master.debian.org/keys.html)说明 stable 同时由当时使用的 archive key 和 per-release key 签名，并提醒网页信息本身不能作为唯一身份核验。[2023-03-09 官方公告](https://lists.debian.org/debian-devel-announce/2023/03/msg00001.html)说明新 bookworm archive key 在 release 或其后才投入使用；本轮直接打开曾返回 403，搜索服务随后返回公告正文，应区分这两次观察。它解释了为什么不能仅按 codename 推断同代 archive key，但不自动接受本次缺钥匙签名。

### 经确认的历史三角色接续

[只读准备入口](solver-cvc5-c1-review-2026-10-23/prepare-historical-key-review.py)从既有固定 `debian-archive-keyring` 包找到缺失公钥，没有下载新文件：包 178,572 bytes / SHA-256 `f699e2f88dca05212f2a452b58475f2993cb6993dfbafb1d0205a3291eb8b4b8`；removed-keys 环 72,636 bytes / `0ff45da93c7fd62cc3f10b4c5019985caf49e5959bb3bf992f558d11963870fa`。所需 buster 块 8,132 bytes / `89d89bcedee9ed88b25eabb5be786fbca6259f121e6ad6ebf5651f852f5227cf`，主钥匙 `80D15823B7FD1561F9F7BCDDDC30D7C23CBBABEE`、子钥匙 `0146DC6D4A0B2914BDED34DB648ACFD622F3D138`。主 / 子指纹与[2019 官方公告](https://lists.debian.org/debian-devel-announce/2019/04/msg00008.html)一致；bullseye 身份亦与[2021 官方公告](https://lists.debian.org/debian-devel-announce/2021/01/msg00003.html)一致。材料来自既有 2025.1 keyring，网页核对日为 2026-10-23；不声称对公告签名进行了密码学认证。

[候选方案](solver-cvc5-c1-review-2026-10-23/historical-key-candidate.json)先保留 proposed 状态；项目所有者随后明确接受本次限定历史三角色、旧钥匙、官方公告 / 留存包身份依据及当前全渠道撤销检查未覆盖的限制。不是在程序中静默把缺 bookworm archive 改成“任一签名成功”：新 profile 必须恰好匹配 **buster archive + bullseye archive + bookworm release** 三份签名，保留完整原文，不允许缺失或额外角色。

[实际接续入口](solver-cvc5-c1-review-2026-10-23/verify-historical-snapshot.py)和[固定状态解析器](solver-cvc5-c1-review-2026-10-23/inspect-signature-status.py)沿用原镜像、容器资源和每条 30 秒限制。首次在第七步密码学验证通过后，宿主索引路径误写为 `Packages` 导致 FileNotFoundError；[失败记录](solver-cvc5-c1-review-2026-10-23/historical-verification-failed.json)和冻结方法保留，7 个容器全部删除。修正为既有精确文件名 `main__binary-arm64__Packages.xz` / `main__source__Sources.xz`，并加入启动前存在性检查后，用独立目录完整重跑。

[完整结果](solver-cvc5-c1-review-2026-10-23/historical-verification.json)为 passed，12 步约 2.75 秒，所有容器退出并删除：

- 三把钥匙分别过滤只保留自认证材料，再逐字节核对过滤前后原始 key / UID / 自签名集合不变。GnuPG 检查 buster / bullseye 各 7 份、bookworm release 1 份自认证；按当前观察时点拒绝材料内过期、禁用、撤销或缺失认证。archive 子钥匙交叉认证始终要求。
- 原文 GnuPG exit 0，三份固定 `VALIDSIG` 与主 / 子钥匙、算法、签名时间一致；签名时间为 2023-06-10，没有签名过期字段。Release 原文 145,119 bytes / `010b226303e531b2ca0d268079228b6667418b8ad021d6c126374837ad327055` 逐字节匹配。
- 已认证 Release 绑定 arm64 Packages.xz（8,801,860 bytes / `4926bbf128b8e497cb83c59c8212fd2ef4df5b2c30e9140a688198cd2cd55471`）及 Sources.xz（9,628,468 bytes / `d1d5103c4ddd76196acc292e90fd0ffece1fe0d04408ab544633f25568e6cb19`），接续已核对的 500 原包与 101 `.dsc` 声明链。
- 五个负例均实际产生预期拒绝：正文一字节篡改、分别缺 buster / bullseye / release 钥匙、损坏 bullseye archive 子钥匙交叉认证。三项缺钥匙用例还要求另外两份签名确实验证成功，避免将不相关的工具故障当作负例通过。

原 Release 没有 `Valid-Until`，不能解读成永久有效或安全最新。完整批次只检查留存钥匙材料及当前时间下的密码学行为；公钥身份、已接受宿主 / GnuPG 和材料时点仍是信任输入，不覆盖全渠道最新撤销，也不构成源码 / binary 重建证明或 solver 运行资格。签名缺口在项目所有者明确接受的这一本地诊断范围内收口，旧两次失败仍保留。

## 验证与留存

本批实际完成：归档 / 包路径检查器 25 项合成测试；签名状态解析器 9 项合成测试；374 项真实静态扫描；172 copyright 路径与 101 `.dsc` 关联核对；500 项原字节留存回读；首次真实失败验签、历史方案首次路径失败、完整 12 步真实验证及所有容器清理。检查器前三次失败、宿主预检失败和原 GnuPG 失败及宿主索引路径失败全部保留。

本批未运行 Rust 构建 / 测试、CMake、pkgconf、SDK 工具、其他平台、CI 或 solver。仓库文本 / 链接检查通过（2,853 文件），`git diff --check` 通过；原 C1 清单重建 `python3 scripts/cvc5-build-preparation.py verify` 也通过。该旧入口仍输出原获取计划的 `signature_verified=false` / 待确认状态，只复核被冻结的原计划，不消费本批后续验签结果；当前签名结论以本文实际接续记录为准，不改写旧机器证据。原始审阅文本、完整 Docker 调用 / stdout / stderr / status、方法快照放各 `artifacts/cvc5-c1-*2026-10-23*` 精确批次；机器结果在本文链接目录。没有提交或 push 本批修改。

## LibPoly 尚需的外部澄清（未发送）

可提交给上游的精确问题范围为固定 `v0.2.1` / commit `3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a`：确认根 LGPL 对 Poly / Polyxx 的覆盖；澄清 `debian/copyright` 的 `Files: *`、GPL-3+ 标签与 Lesser 正文冲突；确认 `src/utils/open_memstream.c` 来源 / 许可。`u_memstream.c/.h` 已有 MIT 声明，不请求改写它们。请求最好得到版本化、可公开追溯的上游说明或修正提交；新上游提交仅作澄清依据，不自动更换已冻结源码。当前没有发送 issue、邮件或其他外部消息。
