# AX-B01 无 Poly 候选的 C1 限定接受

2026-11-22，项目所有者确认接受 `ax-b01-cvc5-1.3.4-linux-aarch64-no-poly` 的固定 C1 输入，用途限于 AX-B01 的受控本地诊断。候选固定 cvc5 `1.3.4` / `f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341`、Linux AArch64 little-endian、glibc/GCC、Production、静态、non-GPL、Editline 和 `USE_POLY=OFF`。输入接受已登记。实际制品接受、构建及执行资格仍待验，`build_ready=false`、`execution_ready=false`。

## 接受对象与工具信任

以提交 `432d4f3` 中以下两个文件的原字节为接受对象。清单递归绑定四份保留源码、选定补丁、固定 SDK 的获取 / 留存 / 内容及 copyright 对账、历史签名记录。配方固定使用角色、工具绝对路径、环境、构建与链接留证门禁。两份文件各自保留生成时的准备状态，后续审阅应读取本决定与同一份冻结输入。

| 冻结对象 | 长度 | SHA-256 |
| --- | ---: | --- |
| [候选输入清单](solver-cvc5-no-poly-2026-11-22/candidate-inputs.json) | 15,293 bytes | `c7173478b3172056455999e2d159f26e537680a1d69e551eba115f34321cedef` |
| [离线配方](solver-cvc5-no-poly-2026-11-22/offline-build-recipe.json) | 95,356 bytes | `b2ed7ba533c030099fb4c965ac3268ac36aaddb0cb422ecc97020f5fd9ea09e0` |

| 受信任输入 | 限定范围 |
| --- | --- |
| GCC / Binutils | Debian GCC/G++/CPP `12.2.0-14`，配套 libstdc++ / libgcc 开发库及运行库以固定库存为准。Binutils `2.40-2`，按配方选用精确 AArch64 工具路径和 `ld.bfd`。 |
| glibc / CRT / SDK | Debian `bookworm/main` 的 `20230612T000000Z` 快照。glibc `2.36-9`、Linux UAPI 包 `6.1.27-1`、GCC / glibc 启动对象及所选库和头文件。固定 172 个二进制包、101 个源码声明，共 500 份原始文件、691,605,464 bytes。SDK 输入限于此库存与隔离布局审阅批准的内容。 |
| 生成与辅助工具 | 固定 CMake `3.25.1-1`、Make `4.3-4.1`、Python `3.11.2-6`、pyparsing `3.0.9-1`、GNU m4 `1.4.19-3`、pkgconf `1.8.1-1`，以及同一库存中配方指定的 shell、文本、归档、检查工具及其运行依赖。 |

按 [ADR 0031](../adr/0031-local-cvc5-build-provenance-boundary.md#信任与攻击边界)信任这些固定工具在所列配置下正确转换输入并如实提供对应工具信息。已回读原包 SHA-256、签名索引到包的链、172 个版权路径及 101 份 `.dsc` 对应的源文件声明。预编译工具仍以固定发行版输入受信任；`.dsc` 维护者签名与源码重建未验。构建控制面、宿主、运行时和内核须单独接受。若候选、工具、来源、可访问输入或用途发生变化，应停止并重新评估受影响的决定。 [SDK 角色与精确选包](../query/solver-cvc5-c0-input-selection.md#精确获取范围与首错停止)

## 历史签名范围

同一份 Debian `InRelease` 的验签适用既有三角色限定决定。日期为 2023-06-10，使用已留存的 Debian archive keyring `2025.1` 及其中的 8,132 bytes buster 历史公钥块。

| 角色 | 主钥匙指纹 | 签名钥匙指纹 |
| --- | --- | --- |
| buster archive | `80D15823B7FD1561F9F7BCDDDC30D7C23CBBABEE` | `0146DC6D4A0B2914BDED34DB648ACFD622F3D138` |
| bullseye archive | `1F89983E0081FDE018F3CC9673A4F27B8DD47936` | `A7236886F3CCCAAD148A27F80E98404D386FA1D9` |
| bookworm release | `4D64FEC119C2029067D6E791F8D2585B8783D481` | `4D64FEC119C2029067D6E791F8D2585B8783D481` |

离线回读匹配原文、两个压缩索引、留存公钥及 12 份原验签状态，含正文篡改、分别缺失三个角色、损坏子钥匙交叉认证的五项拒绝。身份依据限于当时核对的官方公告、HTTPS 和留存包，密码学结果来自原批次已接受的验签环境。本轮未重跑验签器。快照 `Release` 无 `Valid-Until`，安全新鲜度、全渠道当前撤销及其他快照仍在此次决定之外。四份上游独立源码各以自己的原归档和来源记录绑定。 [历史回执](solver-cvc5-c1-review-2026-10-23/historical-verification.json) · [完整验签范围](2026-10-23-cvc5-c1-input-review.md#经确认的历史三角色接续)

## 许可与归属

| 组成 | 本地诊断的许可及归属边界 |
| --- | --- |
| cvc5 和内嵌 MiniSat | cvc5 主体按 BSD-3-Clause 保留 `COPYING` 及 `AUTHORS`。MiniSat 按 MIT 保留独立许可和著作权声明。上游原归档及补丁上下文保留原声明。 |
| CaDiCaL、SymFPU、GMP/GMPXX | CaDiCaL 按 MIT 保留 `LICENSE` 与各作者声明。SymFPU 采用 BSD-3-Clause 选项，保留 `LICENSE-BSD`、`AUTHORS` 及原归档的双选许可材料。GMP/GMPXX 按 LGPL 路线使用库源码，保留双许可文本、文件内声明及生成工具各自条款。 |
| 终端支持 | Editline 按 BSD-3-Clause、tinfo/ncurses 按实际文件的 MIT/X11 及 BSD 声明；libbsd、libmd 按多文件版权清单保留各自声明，包括适用的 BSD、ISC 等条款。libmd 是否抽取及归档顺序由实际链接证据决定。 |
| 运行库、CRT、生成工具及 SDK 其他项 | glibc、CRT、Linux UAPI、GCC runtime、CMake、Make、Python、pyparsing、m4、pkgconf 等按 172 条包内版权路径及关联的固定源码 / Debian patch 追踪。保留 GCC Runtime Library Exception 原文及条件，实际汇入的 CRT、头文件、对象和 archive members 逐项核对。 |

本地接受包括保留上述原始许可和版权材料及受限内部使用。SDK 归档库存、构建期使用和最终制品归属分别记账；最终组成须按真实头文件、对象、链接顺序、成员抽取、map 和 ELF 对账。静态 CLI、镜像或 SDK 的分发须另行评审，包括对应源码、可重链接材料及例外适用性。本候选排除了 LibPoly 的外部输入和阶段；原启用 Poly 路线的许可歧义继续跟踪。 [上游许可库存](solver-cvc5-source-review-2026-10-17/license-review.md) · [SDK 版权及对应源码](2026-10-23-cvc5-c1-input-review.md#sdk-静态内容核对)

L3/G0、构建授权、实际编译 / 链接、E0 和 E4–E6 各有独立停止线。当前登记只改变上述固定输入的 C1 决定，未来实际制品仍须登记新身份并完成独立对账。 [候选停止线](../query/solver-cvc5-no-poly-offline.md#停止线)
