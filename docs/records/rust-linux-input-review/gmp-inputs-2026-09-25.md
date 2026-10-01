# GMP 6.3.0 原包、公钥与内容盘点

日期：2026-09-25（Asia/Shanghai）。提交基线：`50ef87c`；启动时上一批 GCC 13 个文件仍未提交，本批未提交或改写其方法 / 导出。

用途：留存 GMP 精确配方输入的获取事实、签名 / 公钥声明及选定内容观察，供来源与执行方案审阅。本文不构成密码学验签、来源接受、完整许可或构建验收。

## 结果与边界

- 已取得 `gmp-6.3.0.tar.xz`，2,094,196 bytes，本机重算 SHA-256 `a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898`，匹配固定配方 SHA-1 `b4043dd2964ab1a858109da85c44de224384f352`。SHA-256 是本机观察，配方 SHA-1 是对应关系，二者都不单独构成来源认证。
- 分离签名声明为 RSA / SHA-512，完整 issuer 为 `343C2FF0FBEE5EC2EDBEF399F3599FF828C67298`，与[官方主页](https://gmplib.org/index)声明相同；创建时间声明为 `2023-07-30T12:18:33+00:00`。未校验签名值。
- Ubuntu 公钥材料比已有 GNU 钥环多出 SHA-256 的主钥 UID 自认证及子钥绑定声明，但最新 UID 自认证声明的主钥到期时间为 `2025-01-15T17:12:43+00:00`。尚未验证有效性、撤销与材料最新性，不能写成“公钥当前有效”或“GMP 来源通过”。也不能仅凭这个到期声明判定 2023 年的历史签名无效。
- 完成 2,343 个逻辑成员、2,156 个普通文件的有界盘点，以及七项选定文本读取；没有提取或执行原包程序。来源与完整许可审查保持未完成。

完整机器记录见 [gmp-inputs-2026-09-25.json.gz](gmp-inputs-2026-09-25.json.gz)，重算入口见 [inspect-gmp-inputs.py](inspect-gmp-inputs.py)。GCC / Binutils 原有缺口不变，本批不推进安装、构建或完整 source lock。

## 请求与留存字节

执行前说明五个固定对象、单次时限、正文上限与缓存副作用，经本任务执行授权后运行 [fetch-gmp-inputs.py](fetch-gmp-inputs.py)。该入口复用旧 curl 获取方法，任一失败即停止；不更换目标、跳转或自动重试。每项 60 秒、父进程 65 秒，总正文上限 2,946,164 bytes。原包最多 2,094,196 bytes，签名 64 KiB，其他每项 256 KiB。

| 对象 | 精确 URL | 实际字节 / SHA-256 |
| --- | --- | --- |
| 身份主页 | `https://gmplib.org/index` | 20,743 / `3e743143ae362de50a972cdd0103ff17d484fc3c3e9275f222a2b73601d40b83` |
| 发布公告 | `https://gmplib.org/list-archives/gmp-announce/2023-July/000050.html` | 5,708 / `03831f223ac1a7a5a9d6f81c0259bd0e95669de29de6d983bf016f0a05fd9d1c` |
| 原包 | `https://gmplib.org/download/gmp/gmp-6.3.0.tar.xz` | 2,094,196 / `a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898` |
| 分离签名 | `https://gmplib.org/download/gmp/gmp-6.3.0.tar.xz.sig` | 374 / `94def8c1a731854de684689126046ec93589147abd4cd0025f12d741d323aa82` |
| 公钥 | `https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x343C2FF0FBEE5EC2EDBEF399F3599FF828C67298` | 32,347 / `50561c50f40cd9746af214c995fb219bbe7f3b9c5f038b918f5df543bb3f846f` |

五项均 HTTP 200 / curl 0，实际本地时间 19:21:43–19:21:56。原始正文、stdout、stderr、参数、工具 / 方法身份与时间保存在 `.tmp/gmp-inputs-50ef87c-20260925/`，没有系统钥环导入或后台进程。第三方原包、公钥与页面只进入本机材料库；Git 保存自有方法、诊断和说明。

主页原文的精确原包链接、字节数与完整指纹声明，以及公告中的原包 / 签名链接均重新解析核对。固定 `musl-cross-make-3635262.tar.gz` 也重新有界读取，直接核对 `hashes/gmp-6.3.0.tar.xz.sha1` 原文，未仅复制历史摘要。

此前完整 Debian Sources 对应的是 `gmp_6.3.0+dfsg.orig.tar.xz`，1,870,556 bytes，见[剩余来源记录](musl-remaining-sources-2026-09-16.md)。它与本次原包的大小不同，不能把 Debian 重打包的认证转移给该上游压缩字节。本批没有重新下载或逐文件比较 Debian 原包。

## 公钥差异与待验证项

按官方完整主钥指纹复用[已有 GNU 钥环](binutils-key-refresh-2026-09-25.md)，无需新请求。原钥环 SHA-256 为 `b136fbe57ade4ee5270ca66c402cae7b50349fd07646b5b3de7962d58d4df608`；选择出的公共包为 1,527 bytes / SHA-256 `7b0d2f9d6b336566cec2a80d90c3febc684e7fafc9516fe14d3d574ef53175a4`，排除并记录本地 trust 包，不导入信任。

Ubuntu 材料是同一主钥块，包含一个 UID 与子钥 `48C9DE74746361F8617018347520153007F35B23`。原包签名声明由主钥签署，不是该子钥。所有解析均沿用既有有界 OpenPGP 方法，没有更改强摘要验签器。

- GNU 材料中的 UID 自认证及子钥绑定声明均为 SHA-1。
- Ubuntu 保留旧声明，另有主钥自签的两个 SHA-256 声明：UID 自认证包体 SHA-256 `8030b90a7235c1194ad9e32aba69bc7f6ec0a39569fade0a59da0dfb8a5ae30d`，子钥绑定包体 SHA-256 `da9f6fc37b44d75d6eb77445b72e01488067147e8e6084c351749041c3d1ee88`。这只是新增包体与声明字段，不是认证成功。
- 最新 UID 自认证创建时间声明为 2020 年，到期提示通过主钥创建时间加声明的 `key_expiry_seconds` 得出；没有通过 GnuPG 核实该声明的真实性、有效性或是否存在后续延长。
- 材料还包含第三方 issuer `598F95AAF6C99C5F` 的 class `0x30` 认证撤销声明，`declared_self_signature` 为 false。不能将它误判为主钥自己撤销整个密钥，也不能通过忽略该包声明完成撤销审查。

下一轮 GMP 执行方案须明确签署时间与核验时点、过期状态、撤销 / 最新性范围，以及哪些身份 / 宿主材料仍是可信输入。不得自动回拨时钟、忽略到期状态或套用 MPC 的 Debian 来源接受；也不因存在 SHA-256 字段就直接进入来源接受。

## 内容与许可声明观察

复用 [MPC / MPFR 有界盘点器](inspect-mpc-mpfr-inputs.py)的既有范围：压缩输入最多 4 MiB、展开 tar 32 MiB、单成员 8 MiB、最多 5,000 个成员、XZ 解码内存 128 MiB。拒绝超限、截断 / 串接 / 尾随压缩流、路径逃逸、重复路径、链接 / 特殊类型与非零 tar 尾部；输出仍明确 `physical_tar_profile_verified: false`，不是生产提取器或物理 tar 格式验收。

本次 tar 为 18,759,680 bytes，SHA-256 `c43feeac97e48b42a4c2491950ab9892dadcfbf132807088a0581c60ac5b63af`。每个逻辑普通文件记录路径、模式、大小与 SHA-256；`gmp-h.in` 三个版本宏声明 6.3.0。

读取 `README`、`COPYING`、`COPYING.LESSERv3`、`COPYINGv2`、`COPYINGv3`、`gmp-h.in` 和 `doc/gmp.texi`。以下只报告这些原文的许可声明，不判定最终产物合规：

- `README` / `gmp-h.in` 声明 LGPL v3 或后续版本、GPL v2 或后续版本的双许可选择；根目录保留对应文本。
- 手册区分库本体与示例 / 测试程序，后者声明 GPL v3 或后续版本。
- `doc/gmp.texi` 声明 GFDL 1.3 或后续版本、无不变章节，但有前 / 后封面文字要求。不能将库代码的许可选择直接覆盖手册。

未核对所有文件许可、实际编译 / 静态链接集合、最终产物归属或分发义务；`license_review_complete` 保持 false。

## 复现与验证

[留存清单](gmp-retention-manifest-2026-09-25.json)覆盖 50 路径、40 个去重对象、6,984,962 bytes：本批五对象全部原文与日志、完整原包、GNU 钥环及其旧记录、固定配方、诊断、选定文本与方法 / 测试。使用既有 16 MiB 单对象 / 128 MiB 总量限制，不改动留存方法。

- 持久目录：`artifacts/source-inputs/gmp-inputs-50ef87c-20260925/`。
- 恢复目录：`.tmp/gmp-inputs-restore-20260925/`。
- [实际恢复结果](gmp-retention-2026-09-25.json)：50 路径身份一致；工作区方法身份核对后，以恢复副本为输入重算完整机器导出及选定文本，均完全一致。这不是异盘备份。

缓存仍在时的重算入口如下；输出文件必须尚不存在：

```bash
python3 docs/records/rust-linux-input-review/inspect-gmp-inputs.py \
  --output .tmp/gmp-inputs-replay.json.gz
```

支持 `--directory`、`--recipe`、`--ring` 指向恢复副本；历史请求参数仍与原计划路径比较。完整导出采用固定 `mtime=0` 的 gzip JSON。

实际通过：新增 [GMP 7 项检查](check-gmp-inputs.py)，复用输入 / 签名 / 请求 18 项、公钥 9 项、GNU 选择 10 项、留存 7 项，共 **51 项**。包含错误版本 / 域名 / 指纹 / 大小、摘要篡改、计划漂移、首次失败停止及现有资源 / 截断边界；请求超时输出是合成测试，五次真实请求均成功。

仓库级检查与 `git diff --check` 通过。未重跑 GnuPG、Rust / CI、容器、产品构建或上游测试。下一步独立核对 headers 重打包来源，并为 GMP 整理有效性与受限验签方案；这些后续顺位不是新下载或执行授权。
