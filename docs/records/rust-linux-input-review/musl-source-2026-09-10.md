# musl 1.2.5 原包、签名与四份补丁核验

日期：2026-09-10；基线：`dev` / `c7f7f60`。

用途：为工具来源与 guest 维护者记录精确 musl 源码、许可文本、离线签名诊断和局部补丁应用结果。本轮取得原包并成功应用四份补丁，但**严格签名条件未通过**，不形成 source acceptance、完整构建证明或安装许可；未安装工具、运行 musl 代码或构建产物。

## 原包身份与留存

本轮获准下载 `musl-1.2.5.tar.gz`、其 `.asc`、官方发布历史页及该页直接链接的同站发布公钥；获准在已有固定镜像中最多执行两次有界离线诊断。源码与签名入口同时见 [Rich Felker 的 1.2.5 发布公告](https://www.openwall.com/lists/musl/2024/03/01/2)，未改为其他 musl 版本或镜像。

| 输入 | 实际长度 / SHA-256 |
| --- | --- |
| `musl-1.2.5.tar.gz` | 1,080,786 bytes；`a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4` |
| `musl-1.2.5.tar.gz.asc` | 490 bytes；`d9030116fd03e4acfa0b665a13a5de46110296b4e30bb8e67be1f08af29f6306` |
| `musl.pub` | 1,707 bytes；`bf6baaa63c2c4958636850a24bb9d2d514c8b6a1b3ab9c08f3b75910fb6f57be` |
| `releases.html` | 61,597 bytes；`5153be19d53ad2ae418993a15a8ba005400ba8e16b6781a533e2c8a0658a8a30` |

原包 SHA-1 为 `36210d3423172a40ddcf83c762207c5f760b60a6`，与前轮固定 musl-cross-make 的声明一致；本地 SHA-256 绑定后续复核字节，不自行建立发布者身份。源码 `VERSION` 为 `1.2.5`，tar PAX comment 为 `0784374d561435f7c787a555aeab8ede699ed298`；comment 是归档声明，未进行 Git 对象重建或 tag 验签。

[完整库存](musl-source-inventory-2026-09-10.json.gz)覆盖 2,933 个逻辑成员、2,697 个文件，无链接 / 特殊成员。展开 tar 为 5,775,360 bytes，SHA-256 `1efeecf639b04eae538fb20a3d185105488bf5901668ec4cfe411f5973a222cb`。[摘要记录](musl-source-summary-2026-09-10.json)绑定压缩库存和原始 JSON；[扫描方法](inspect-musl-source.py)记录逐文件 SHA-256、Git blob SHA-1 标识和许可关键词行号。Git blob 标识只供文本对象比对，不作为认证算法。

扫描在固定原始长度 / SHA-256 核对后进行，限制压缩 4 MiB、tar 32 MiB、单成员 8 MiB、10,000 个成员；复用既有规范路径检查，拒绝重复、链接 / 特殊成员及非零尾部。它是只读逻辑成员诊断，不替代物理 tar 验收。135 个文件含许可检索词，这是审阅线索，不是自动完成了所有文件的许可证分类。

原包、带全文的扫描 JSON、四份既有 patch、下载与离线日志保留在忽略目录 `.tmp/musl-source-review-c7f7f60/`；仓库只保留方法、元数据、公开[公钥](musl.pub)和[签名](musl-1.2.5.tar.gz.asc)，不复制整套上游源码。下载失败及成功分别留存在 [fetch 记录](musl-source-fetch-2026-09-10.json)：四项首次沙盒 curl 均因代理连接失败返回 7；授权后沙盒外重试均返回 0 / HTTP 200。网页读取工具早前无法取得发布历史页 / 公钥正文，未把接口超时当作文件不存在；本次实际 curl 已取得字节。

## 签名：GnuPG 成功，严格条件拒绝

实际取得的 [官方发布历史页](https://musl.libc.org/releases.html)第 69–70 行直接链接 `musl.pub`，同时列出完整指纹：

`8364 8929 0BB6 B70F 99FF DA05 56BC DB59 3020 450F`

下载地址解析为 `https://musl.libc.org/musl.pub`，实际主指纹一致。该 HTTPS 页面是本轮记录的身份来源，不等于独立认证链；没有使用第三方 keyserver、自动取 key、修改宿主 keyring 或设置 `trust-model always`。

固定镜像内 GnuPG `2.2.40` / libgcrypt `1.10.1` 的实际观察：

| 层次 | 结果 | 本轮判定 |
| --- | --- | --- |
| 公钥 | RSA 2048，主指纹与官方页面一致；当前下载材料未声明到期 | 对应观察成立；不宣称已独立核对所有撤销 / 更新渠道 |
| UID 自认证 | signature class `0x13`，digest algorithm **2 / SHA-1** | 不能视为现代 key-binding policy 已通过 |
| 加密子钥绑定 | signature class `0x18`，digest algorithm **2 / SHA-1** | 原样保留，不放宽绑定策略 |
| 原包分离签名 | GnuPG 退出 0，唯一 `VALIDSIG` 对应主指纹；digest algorithm **2 / SHA-1**，日期 `2024-03-01` | **`pinned_signature_passed = false`** |
| 身份信任 | `TRUST_UNDEFINED` | `publisher_identity_acceptance = not-assessed` |

本次分离签名本身就使用 SHA-1；这与前轮 Rust 分离签名为 SHA-512、仅旧自认证涉及 SHA-1 的情况不同。[核验方法](verify-musl-source.py)只把 SHA-256 / SHA-384 / SHA-512 纳入严格签名条件，因此没有将 GnuPG 的成功退出码升级为来源接受。两次实际容器调用最终都退出 1：首次还包含下述补丁诊断错误；第二次补丁已成功，仍因签名条件拒绝而退出 1。

公钥显示、packet 解析、导入、certification 检查、分离签名 packet 和全部 GnuPG 状态均留在[离线记录](musl-source-offline-2026-09-10.json)。本次没有修改旧 Rust 策略，也没有把自行重算的 SHA-256 当成新上游强签名。

## 四份补丁的实际应用

输入沿用[固定配方补查](musl-cross-make-2026-09-10.md)中两份 musl-cross-make patch 与两份 Rust patch，原文 / 摘要未修改。[补丁预检方法](inspect-musl-patches.py)检查固定 SHA-256、大小、统一差异头和路径；只允许 `src/locale/iconv.c`、`src/locale/gb18030utf.h`、`src/stdlib/qsort.c`，拒绝删除、重命名、额外目标和路径逃逸。

在容器的 `/tmp` 新副本中，只复制原包内两个待修改文件，逐份先 dry-run 再实际应用。GNU patch `2.7.6` 最终使用 `--batch --forward --fuzz=0 --no-backup-if-mismatch -p1`；不调用 `cowpatch.sh`。四个输入文件共包含 7 组文件差异、14 个 hunk，八次 dry-run / apply 子进程均退出 0：

| 输入文件 | 实际观察 |
| --- | --- |
| `0001-cve-2025-26519-p1.diff` | iconv hunk 成功，行偏移 `-7` |
| `0002-cve-2025-26519-p2.diff` | iconv hunk 成功，行偏移 `-7` |
| `0003-cve-2026-6042.diff` | 新增 `gb18030utf.h` 并修改 iconv；iconv 第 3 个 hunk 行偏移 `-7` |
| `0004-cve-2026-40200.diff` | qsort 的三个补丁段均成功，未报告偏移 |

所有步骤均保持 `fuzz=0`，没有忽略上下文；行偏移不隐藏，不能描述为全部在原行号应用。最终只有预定三个文件，未留下备份或 reject 文件：

| 最终文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `src/locale/iconv.c` | 15,479 | `9a1fc56619fccf8daab368411e1b48955e8bff933cd00f71d995e71aefc47897` |
| `src/locale/gb18030utf.h` | 3,172 | `94b51d272a81a1164a035918253004ab71cc21e29f11100dcf9bd3dc22757c28` |
| `src/stdlib/qsort.c` | 5,574 | `b40e91d98930b6fa929a42d9129821de5b73ce2fdc3f2a94023143d82408a7f2` |

原始 iconv 的 Git blob 为 `175def1c…`，不同于第一份 patch 的 `9605c8e9`；最终 iconv 为 `a7320227…`，不同于第三份 patch 的 `4151411d`。qsort 的原始 / 最终 blob 也不等于 patch 中的上游 index 声明；新增 `gb18030utf.h` 则与 `322a2440…` 相符。这说明补丁按上下文应用到 1.2.5 的结果不能冒充 patch 作者所用完整上游文件或原始 commit。前轮记录中的 abbreviated index 衔接仍只是文本线索，本轮用实际字节补齐了这个边界。

摘要记录还推导一个完整内容清单：将原库存的 `path -> sha256` 映射替换 / 新增上述三项，按 `json.dumps(sort_keys=True, separators=(',', ':'))` 加 LF 序列化，得到 2,698 项、248,611 bytes，SHA-256 `f8fe4e7d754047068cd583a172b54ecdd5590b6a875bb196c59bf3d040777af4`。这是可重算的**清单组合结果**；本轮没有落盘完整 patched source tree、生成源码 tar 或构建 binary。

### 首次失败与方法修正

首次真实容器诊断在 patch 应用后的输出路径检查处抛出 `unexpected patch result path`，立即中止，未通过放宽白名单继续。原方法没有在异常前返回局部 patch 日志，因此首次记录不能确定名单外文件的具体名称；这个可观测性缺口如实保留，不事后补造日志。

GNU patch 的实际 `--help` 列出 mismatch 备份行为和 `--no-backup-if-mismatch` 控制项；已成功复验的相同输入也确实存在行偏移。第二次显式禁用 mismatch 备份，并先保留 apply 日志、再检查输出路径；保留相同 `fuzz=0` 和三个文件白名单后全部通过。首轮文件可能是备份是基于这些事实的解释，不写成已经观察到其文件名。最终方法和[还原首轮方法的差异](musl-offline-first-method.patch)均留存，首轮方法摘要由原始输出绑定；没有重写首次失败为成功。

## 许可清单与 libc / CRT 构建范围

原包 `COPYRIGHT` 为 6,204 bytes，SHA-256 `f9bc4423732350eb0b3f7ed7e91d530298476f8fec0c6c427a1c04ade22655af`。它声明 musl 整体采用 MIT，同时明确列出第三方材料和特定文件例外。本次已读根文本及下列代表文件的实际许可头；表格不替代所有文件级条款或最终分发审阅。

| 材料范围 | 源码中实际见到的条款 / 归属 |
| --- | --- |
| 无单独版权注释的原始文件 | COPYRIGHT 163 行起给出统一归属说明；不能把缺少逐文件 SPDX 当成没有许可 |
| TRE regex | `src/regex/regcomp.c` 等保留两条款 BSD 的源码 / 二进制归属要求 |
| math / complex | 多个原始作者及许可；例如 `src/math/exp.c` 为 Arm MIT，`src/complex/cexp.c` 为 David Schultz 的两条款 BSD |
| AArch64 memcpy / memset | 两份实际 `.S` 文件均带 Arm 版权与 `SPDX-License-Identifier: MIT`；年份以文件头为准 |
| crypt | DES 保留 BSD 条款；blowfish 声明 public domain 并附宽松许可作为法律适用上的替代条款 |
| qsort | Valentin Ochs 的 MIT-style 文件头；本次补丁保留原头部 |
| public headers 与指定 CRT 文件 | COPYRIGHT 171 行起明确允许指定 `include/*`、`arch/*/bits/*`、`crt/*`、`ldso/dlstart.c`、`arch/*/crt_arch.h` 省略通常要求的版权 / 许可通知 |

最后一项例外只按原文指定文件范围理解，不能扩大到整份静态 `libc.a`。补丁自身沿用对应上游项目的许可口径；新增文件没有独立许可头时，需要连同来源 patch、musl 根条款和修改记录一起审阅，不改写项目 Apache-2.0 策略。

实际 Makefile 21–35 行按架构选择对象；AArch64 的 `crt/aarch64/crti.s` / `crtn.s` 替代通用空文件，`crt1.c`、`Scrt1.c`、`rcrt1.c` 和 `arch/aarch64/crt_arch.h` / `ldso/dlstart.c` 提供另外三个入口。它们与 Rust 配方复制的五个 musl CRT 相对应，但本次未编译或比较对象字节。

另一个已澄清边界：Makefile 161–163 行仅在 `lib/libc.so` 链接规则使用 `$(LIBCC)`；165–168 行的 `lib/libc.a` 通过 `ar rc` 归档 `AOBJS = LIBC_OBJS`，没有直接合入 `LIBCC`。因此前轮发现的 GCC 支持库属于该工具链的构建输入，不能直接推导已嵌入 Rust 所带 `libc.a`。编译生成的未定义支持符号、实际 `.a` 对象及最终链接仍须另验收。

## 执行边界、复核与下一步

实际 Docker context 为 `orbstack`，固定已有 arm64 镜像为 `sha256:a339861ae23e9abb272cea45dfafde21760d2ce6577a70f8a926153677902663`。两次容器均无网络、非 root、根只读、drop ALL capabilities、no-new-privileges，限 512 MiB / 1 CPU / 64 pids / 120 秒；只读挂载任务输入，`/tmp` 为 64 MiB 的 noexec / nosuid / nodev tmpfs。每个 patch 子进程限 10 秒。镜像来源仍保持既有诊断边界，不因其能验签而升级为可信 builder。

初次沙盒 Docker 调用未连上 socket，容器未启动；随后仅执行两次获准容器诊断。每次 `--rm` 退出，临时 keyring 和补丁副本随容器删除，最终按精确容器名只读查询为空。没有增加依赖、修改 PATH / 系统 keyring、执行 configure / make / musl、安装工具或启动产品 VM。

本轮新增 8 项合成拒绝检查通过；实际 source 库存、四份 patch 输入及三份结果文本摘要均有复核。开发期修正了合成测试自身把断言误作上下文管理器的错误，没有改动严格签名条件。1,060 文件仓库门禁与差异检查通过；库存重跑逐字一致，最终 / 首轮方法及三次离线调用的日志绑定均核对一致。Rust / CI、构建、最终链接和产品执行未运行。验签拒绝仍属于实际结果，不计为通过。

复核入口（已有精确输入为前提，不授权新下载或容器执行）：

```bash
python3 docs/records/rust-linux-input-review/inspect-musl-source.py \
  .tmp/musl-source-review-c7f7f60/musl-1.2.5.tar.gz \
  > .tmp/musl-source-review-c7f7f60/source-recheck.json
python3 docs/records/rust-linux-input-review/inspect-musl-patches.py \
  .tmp/musl-source-review-c7f7f60
python3 docs/records/rust-linux-input-review/check-musl-source.py
./scripts/check-repo.sh
git diff --check
```

离线调用的完整程序、镜像、挂载、限制、工具摘要与实际输出见离线 JSON；输入目录内的 `verify-musl-source.py` 和 `inspect-musl-patches.py` 必须与留存方法摘要一致。默认 source 输出与 gzip 库存展开后逐字一致；最终离线输出只移除 `patches.final_text` 后进入 Git，原始 stdout / stderr 长度与摘要仍保留。

下一步首先处理 **musl 的强摘要来源认证与公钥绑定策略**：继续寻找同一源码身份的现代认证材料；若材料不足，另行审阅明确的窄信任方案，不能静默接受 SHA-1。其他六项工具链源依赖、发布构建关联、宿主系统库 / loader / 符号版本、Rust 公钥策略、kernel 原始 tag 和最终链接仍待闭合。此次四份补丁成功只是源码应用诊断，不代表漏洞修复验证、发布 payload 已含修复或允许安装 / 激活。
