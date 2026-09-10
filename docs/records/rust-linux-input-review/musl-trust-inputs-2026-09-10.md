# musl 信任补证：Debian 指纹页面与 keyring 包

日期：2026-09-10；基线 `dev` / `bbbe083`。用途：留存项目所有者授权的两个精确下载目标及本地核对，供来源审阅者复核；不是密码学验签、完整工具来源验收或安装回执。执行前已有四份未提交的策略确认文档，本批在其基础上继续更新，未提交或推送。

## 实际结果

两个下载均成功，页面列示的两个完整主指纹与既有诊断相符；精确 `.deb` 的长度 / SHA-256 与旧 bookworm 索引一致，包内完整 keyring 与旧 GnuPG 输入逐字节相同。[本地核对结果](musl-trust-inputs-2026-09-10.json)保留 `acceptance = not-assessed`、`signature_reverified = false`、`tools_provenance_accepted = false`。

| 原始材料 | bytes | SHA-256 |
| --- | --- | --- |
| Debian FTP keys 页面 | 10,718 | `b271f4c351a3b54f6a6be9667bb834809d12ee514055b903ccb06839d274e3e0` |
| `debian-archive-keyring_2023.3+deb12u2_all.deb` | 178,572 | `f699e2f88dca05212f2a452b58475f2993cb6993dfbafb1d0205a3291eb8b4b8` |
| 包内 `usr/share/keyrings/debian-archive-keyring.gpg` | 55,918 | `506b815cbb32d9b6066b4a2aa524071e071761e7e7f68c3ac74f3061ba852017` |

页面和 `.deb` 原始字节分别留在 `.tmp/musl-trust-bbbe083-20260910/keys-attempt-2.html` 与 `keyring-attempt-2.deb`。本轮没有获取 InRelease、Sources 或 musl 原包的新副本；它们仍采用此前固定字节。

## 页面身份依据及未访问的链接

[实际下载的官方页面](https://ftp-master.debian.org/keys.html)在 archive 与 stable release 两个对应条目分别列出：

- trixie archive 主钥：`04B54C3CDCA79751B16BC6B5225629DF75B188BD`；
- trixie stable release 主钥：`41587F7DB8C774BCCF131416762F67A0B2C39DE4`。

两指纹均以完整 40 位形式在页面出现一次。页面说明 stable Release 使用自动归档钥和每发行版 release key；同时明确提醒页面信息不能单独作为信任验证依据。本项目按[已确认方案](musl-debian-auth-2026-09-10.md#项目所有者确认与执行顺位)承担 Debian 官方 HTTPS / WebPKI 初始身份假设，并保留补证条件，不把本次网页核对改写为独立 Web of Trust。

页面提供以下精确后续目标，本批只解析链接，没有请求其内容：

| 材料 | 页面给出的 URL | 尚未形成的结论 |
| --- | --- | --- |
| trixie archive 公钥 | `https://ftp-master.debian.org/keys/archive-key-13.asc` | 未与本地公钥 packet 对照，未核对新撤销材料 |
| trixie stable release 公钥 | `https://ftp-master.debian.org/keys/release-13.asc` | 同上；不能假定它与旧 keyring 仍完全一致 |
| Debian 13/trixie keys 公告 | `https://lists.debian.org/debian-devel-announce/2025/04/msg00001.html` | 公告正文和其中的认证依据未取得；不能假定覆盖两个角色的全部依据 |

页面包含通用密钥更替 / 撤销程序说明和一些旧钥的撤销链接。本轮没有发现单独标为 trixie 撤销材料的链接；这是这份页面的观察，不能推出不存在撤销。网页列为 active / stable 也不能替代密钥的密码学状态检查或验证时点声明。未访问 security key、旧钥、其他站点资源或页面内脚本 / 图片。

## 包内字节对照与方法边界

包摘要固定后，先审阅已有 [inspect-controls.py](../linux-builder-source-chain/inspect-controls.py) 的 ar 解析和内存 tar 读取方法。该入口固定旧三包并只处理 control archive，直接套用会扩大其历史职责；本批在记录内保留[固定输入检查方法](inspect-musl-trust-inputs.py)，不修改旧入口或验收生成器。

读取仅在主机 Python 内存中进行，没有将 tar 成员释放到文件系统。要求 ar 恰为 `debian-binary`、`control.tar.xz`、`data.tar.xz`，检查长度、重复名与 padding；两个 XZ 流各限解码 4 MiB、decoder 内存 128 MiB，拒绝截断、拼接或多余压缩数据。tar 各限 512 个逻辑成员、单文件 1 MiB，只接受目录 / 普通文件，拒绝绝对路径、路径穿越、重复路径、链接和 PAX 扩展。本检查是固定 `.deb` 的有界逻辑成员读取，不是通用安装器或完整物理 tar 验收。

实际 control archive 共 8 个逻辑成员，data archive 共 32 个；控制字段为 `debian-archive-keyring / 2023.3+deb12u2 / all`。选定 keyring 与[旧 release-verification.json](../linux-builder-source-chain/release-verification.json) 的 `keyring.base64` 解码结果逐字节相同。control / data 文件库存、长度、摘要、模式及方法摘要均在本地核对 JSON 中；maintainer scripts 只作为文件读取和计算摘要，未执行。

包内 `usr/share/doc/debian-archive-keyring/copyright` 的声明将 keyring 公钥材料与 Debian 支持文件区分，支持文件声明为 GPL-2.0-or-later。这里只记录该文件的声明及其字节摘要，不把整个包或网页视为本项目自有许可材料，不作新增再分发方案结论。原网页不整页复制进 Git，包和网页均保留来源 URL / 获取记录供复核。

该结果补齐“旧诊断 keyring 与该精确发行包内容相同”，但 `.deb` 摘要仍来自旧 GnuPG 观察下的 bookworm 索引，不能循环证明 GnuPG、镜像或公钥初始身份。未读取 / 验收新的 `gpg`、libgcrypt 或其他运行库包，未导入宿主 keyring，未调用 GnuPG 重新验签。

## 下载执行及复核

[四次请求记录](musl-trust-inputs-execution-2026-09-10.json)保存 URL、完整参数、UTC 起止时间、HTTP 状态、curl 退出码、原始 stdout / stderr 及响应字节摘要；[下载方法](fetch-musl-trust-inputs.py)与执行时缓存中的 `fetch.py` 字节相同。宿主 `/usr/bin/curl` 报告 `8.7.1`，版本文本及程序 SHA-256 留存；这不是 curl 完整来源验收。

两个目标首轮均因沙箱无法连接 `127.0.0.1:10808` 代理而退出 7 / HTTP 000，零字节正文；按授权在沙箱外各重试同一 URL 一次，均退出 0 / HTTP 200。成功请求分别发生于 `2026-09-10 13:39:27–13:39:28 UTC` 和 `13:40:11–13:40:13 UTC`。共四次请求、两个目标，响应正文累计 189,290 bytes，未超过既定次数和大小上限，没有重定向或跟随链接。

每次均使用 `--disable` 禁用默认 curl 配置、HTTPS / TLS ≥ 1.2、60 秒期限及独立输出文件；页面限 1 MiB、包限 512 KiB。未增加弱 TLS 选项、安装、容器、远程写入或系统配置修改。无后台进程需要清理；任务目录保留原文和失败 / 成功日志，未删除旧缓存。

在现有缓存上重算（不下载、不运行容器）：

```bash
python3 docs/records/rust-linux-input-review/inspect-musl-trust-inputs.py \
  .tmp/musl-trust-bbbe083-20260910
./scripts/check-repo.sh
git diff --check
```

本地检查首次退出 0，stdout 原样保存为本目录的核对 JSON，stderr 为空。下载器不是仓库默认检查的一部分，勿直接从记录目录重跑下载；重跑必须重新明确缓存目录与下载授权。缓存缺失时 Git 只能提供方法、诊断结果和摘要，不能独立提供完整网页 / `.deb`；它们的持久留存缺口仍在。

收口复核：四次请求的正文、stdout / stderr 长度和摘要与留存 JSON 一致，缓存下载方法与记录内方法字节相同；本地检查重跑输出与结果 JSON 逐字节一致。仓库检查通过（1,076 文件），`git diff --check` 通过。本轮未新增或重跑密码学测试，未运行 Rust / CI、GnuPG、容器、安装或构建；这些本地检查不能将诊断升级为来源验收。

本批结束时，下一步为取得上述精确公告 / 公钥并核对指定时点的密钥状态，目标尚未获下载授权。提交 `ef02b43` 后项目所有者要求继续，随后完成[三份材料读取与本地对照](musl-key-status-2026-09-10.md)；当前顺位转为最小验证环境来源与密码学复核。两批成功均不代表工具来源或 musl source acceptance 已齐备；musl 上游 SHA-1 拒绝及禁止据此安装的边界保持不变。
