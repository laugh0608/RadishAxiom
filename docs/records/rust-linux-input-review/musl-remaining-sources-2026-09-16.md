# musl-cross-make 其余六项输入的来源路线审阅

日期：2026-09-16；基线 `dev` / `aa13d7c`。用途：供后续材料获取与来源审阅者核对精确版本、现有索引候选和不可替代边界。本轮只有本地完整索引 / 配方重读及官方网页查询，没有取得六个原包、接受新的信任策略、运行构建或安装。

后续执行：项目所有者确认下述四对象范围后，已完成 MPC / MPFR 原包及签名获取、920 文件盘点与本机增量恢复核对，见[执行记录](mpc-mpfr-inputs-2026-09-16.md)。本文“尚未下载”描述的是执行前路线审阅时点；机器诊断保留原样，新的来源验收仍未完成。

## 实际进展

已将[固定 musl 配方](musl-cross-make-2026-09-10.md)的其余六个输入与留存完整 trixie Sources 对照，结果见[机器诊断](musl-remaining-sources-2026-09-16.json)。[方法](inspect-musl-remaining-sources.py)重新扫描原 musl-cross-make 归档并与已提交 340 文件库存一致，逐字读取对应 `.sha1` 声明；完整消费 Sources 流后才报告缺失。输入 Sources 为 10,527,804 bytes / SHA-256 `e8bbadd8389119e841494630998187f961d7de4d5b1dcbeed4f792a1d423299f`，没有取相邻版本替代。

**MPC 与 MPFR 最适合组成下一批小范围原包核对。** 已有同版本、同压缩格式的索引候选，总计 2,279,169 bytes，但尚未取得上游原包，不能预先声称字节相同或来源通过。musl 的限定来源验收不自动授权其他包使用同一信任结论。

| 配方精确输入 | 已有索引观察 | 下一条来源路线 / 停止线 |
| --- | --- | --- |
| `binutils-2.44.tar.gz` | 存在 `binutils=2.44-3`，但原包是 27,504,768 bytes 的 `.orig.tar.xz` | 官方 GNU [目录](https://ftp.gnu.org/gnu/binutils/)列出精确 `.tar.gz` 及 `.sig`；优先核对这个归档及签名。不能把 `.xz` 摘要填给 `.gz`，也不能自动换压缩格式改配方 |
| `gcc-9.4.0.tar.xz` | 完整快照没有 `gcc-9` source 条目 | 官方 [9.4.0 目录](https://gcc.gnu.org/pub/gcc/releases/gcc-9.4.0/)列出精确原包、`.sig` 和 `sha512.sum`；需取得原文及发布者公钥身份 / 自认证。网页查询 `sha512.sum` 本轮失败，尚无可留存强摘要；不以 GCC 14 或目录列名代替 |
| `gmp-6.3.0.tar.xz` | `gmp=2:6.3.0+dfsg-3` 的原包为 1,870,556 bytes | 上游 [发布说明](https://gmplib.org/list-archives/gmp-announce/2023-July/000050.html)与[主页](https://gmplib.org/index)给出原包 / `.sig`，主页列原包 2,094,196 bytes。`+dfsg` 与大小差异排除“直接相同归档”假设；需核对上游原包，不能将 Debian 重打包当作配方输入 |
| `mpc-1.3.1.tar.gz` | `mpclib3=1.3.1-1`，原包 773,573 bytes / SHA-256 `ab642492f5cf882b74aa0cb730cd410a81edcdbec895183ce930e706c1c759b8` | 官方 [下载页](https://www.multiprecision.org/mpc/download.html)仍列 1.3.1 与签名链接；先取得精确上游归档，与索引声明和配方 SHA-1 分开核对。SHA-1 只用于配方字节对应，不作为强认证 |
| `mpfr-4.2.2.tar.xz` | `mpfr4=4.2.2-1`，原包 1,505,596 bytes / SHA-256 `b67ba0383ef7e8a8563734e2e889ef5ec3c3b898a01d00fa0a6869ad81c6ce01` | 官方 [固定版本页](https://www.mpfr.org/mpfr-4.2.2/)列原包和 `.asc`，身份指纹为 `A534BE3F83E241D918280AEB5831D11A0D4DB02A`；页面身份声明不代替取得公钥和真实核验 |
| `linux-headers-4.19.88.tar.xz` | 快照的 `linux` 条目为 6.12 系列，不是该 headers 制品 | 保持 Rust 配方的 `ci-mirrors.rust-lang.org/rustc/sabotage-linux-tarballs/` 精确入口；尚无这份重打包制品的强认证、制作配方与上游 kernel 对应。不能换成 `headers-4.19.88-2`、原 kernel tar 或拟构建 kernel 版本 |

上表仅记录本轮所查网页的入口信息，没有下载 / 执行官方页面推荐的取钥命令。GNU `.sig` 两次网页读取分别为超时或不支持内容类型，MPC 官方 `.sig` 网页读取为二进制解码失败；这些失败不等于签名不存在。MPFR `.asc` 可由网页工具读取，但尚未作为有获取日志与字节身份的本地验签输入留存，也未验签。网页内容随时间变化，实际下载仍要记录独立原文及获取事实。

## 下一批精确获取范围

建议先获取以下四个公开 HTTPS 对象，仅用于字节、签名结构及许可审阅；本轮尚未执行这批下载，也不将该方案视为已取得许可。

| 标识 | 精确 URL | 正文上限 / 成功要求 |
| --- | --- | --- |
| MPC 原包 | `https://www.multiprecision.org/downloads/mpc-1.3.1.tar.gz` | 773,573 bytes；匹配上表 SHA-256 后，另核对配方 SHA-1 `bac1c1fa79f5602df1e29e4684e103ad55714e02` |
| MPC 签名 | `https://www.multiprecision.org/downloads/mpc-1.3.1.tar.gz.sig` | 64 KiB；保留原字节，不预填 digest / signer / 验签结果 |
| MPFR 原包 | `https://www.mpfr.org/mpfr-4.2.2/mpfr-4.2.2.tar.xz` | 1,505,596 bytes；匹配上表 SHA-256 后，另核对配方 SHA-1 `a63a264b273a652e27518443640e69567da498ce` |
| MPFR 签名 | `https://www.mpfr.org/mpfr-4.2.2/mpfr-4.2.2.tar.xz.asc` | 64 KiB；保留原字节，不根据网页出现 ASCII armor 就判定成功 |

HTTPS / TLS ≥ 1.2，不跟随重定向、不自动重试、不更换域名或版本；四项目标，单项 60 秒、父进程 65 秒，一套正文上界 2,410,241 bytes，正常预计 1–5 分钟。3xx / 非 200、超限、原包摘要 / 长度不符或连接失败，保留当次日志并停止；仅沙箱网络拒绝允许申请最小权限后对同一 URL 重试一次，总计最多八次调用、正文累计上界 4,820,482 bytes，最坏父进程等待合计约九分钟。不把权限批准当作更换目标或无限重试许可。

成功记录须包含 URL、时间、命令、curl / 方法身份、HTTP / 退出码、正文及 stdout / stderr 摘要，失败也保留。新任务目录为 `.tmp/musl-remaining-source-fetch-aa13d7c-20260916/`，须独占创建；不覆盖旧材料、不写系统目录、不更新 lockfile，不下载公钥、其他四个大型输入或任何隐式依赖，不运行 GnuPG、tar 内程序、patch、make 或安装器。没有后台进程；失败文件先留存，清理仅限另行确认的本批文件。

原包成功匹配后还须有界盘点内容及许可、检查签名算法与 issuer，再提出公钥身份、自认证和有限验签方案。MPC / MPFR 的索引对应只是候选路线，若拟以 Debian 归档认证为正式来源终点，需要按该两个精确原包单独审阅；不自动继承 musl 的已接受范围。目录页面、配方 SHA-1、主机重算 SHA-256 和签名成功分别报告。

## 验证与顺位

```bash
python3 docs/records/rust-linux-input-review/inspect-musl-remaining-sources.py
```

输出与本记录 JSON 逐字节比较；这是重用现有有界归档 / XZ / Deb822 读取器的只读诊断，分类文字是人工审阅提示，不是自动来源判定器。没有运行第三方 Makefile 或把同名包推定为等价。

Binutils / GCC / GMP 的精确上游认证、headers 的重打包来源，以及发布二进制到配方 / 实际构建输入的关联仍待分别补足；其后继续 Rust 公钥策略、宿主库和隔离安装前置。此前固定 musl 原包的限定验收不变。该轮新记录和方法未提交，未安装、构建或操作远端。

最终机器诊断重新生成与留存 JSON 逐字节一致；`./scripts/check-repo.sh` 通过（1,159 个文件），`git diff --check` 通过。本轮未新增密码学测试，未重跑 Rust / CI 或真实容器；网页查询不替代下一批的原始材料获取与验收。
