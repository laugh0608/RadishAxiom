# MPC / MPFR 原包获取与内容核对

日期：2026-09-16；基线 `dev` / `aa13d7c`。用途：交接本批四个输入的获取、内容盘点、未认证签名字段和本机留存事实；供下一步来源审阅使用，不作为来源验收、安装或构建通过声明。

## 授权与实际结果

项目所有者确认继续执行[上一轮列出的四个精确 HTTPS 对象](musl-remaining-sources-2026-09-16.md#下一批精确获取范围)。[获取方法](fetch-mpc-mpfr-inputs.py)只访问该四个目标；未跟随重定向、替换版本或获取公钥。第一次 MPC 请求因沙箱下无法连接本机代理而以 curl 7 / HTTP `000` 失败，正文为空；申请执行权限后对同一 URL 重试成功。其余三项一次成功，总共五次调用、四个 HTTP `200`，正文合计 **2,279,516 bytes**。失败及成功的命令、时间、工具身份、正文和 stdout / stderr 均保留在[机器记录](mpc-mpfr-inputs-2026-09-16.json)及本机归档中。

| 对象 | 字节数 | SHA-256 |
| --- | --- | --- |
| `mpc-1.3.1.tar.gz` | 773,573 | `ab642492f5cf882b74aa0cb730cd410a81edcdbec895183ce930e706c1c759b8` |
| 对应 `.sig` | 119 | `1e34f97870c82ba4ba3e96e3f134906e3d1a43b88ed52061bf1b44f3b6ed1991` |
| `mpfr-4.2.2.tar.xz` | 1,505,596 | `b67ba0383ef7e8a8563734e2e889ef5ec3c3b898a01d00fa0a6869ad81c6ce01` |
| 对应 `.asc` | 228 | `c6264c9a3652bc40775205ce90e7c96cea5058629e2e68f9eede5d8213f23ee6` |

两个原包均匹配完整留存 Sources 的唯一候选长度与 SHA-256；另行匹配 musl-cross-make 固定配方的 SHA-1。该对应关系不把配方 SHA-1 升级为强认证，也不将先前仅限 musl 的 Debian 路线验收扩展到这两个包。当前 `source_acceptance` 仍为 `not-assessed`。

## 内容与许可观察

[盘点方法](inspect-mpc-mpfr-inputs.py)重新读取固定配方及完整 Sources；对新原包先核对压缩字节，再进行有界解压和逻辑 tar 盘点。限制为压缩输入 4 MiB、展开 32 MiB、单成员 8 MiB、最多 5,000 个成员，XZ 解码内存上限 128 MiB；拒绝路径越界、链接或特殊成员、重名、拼接 / 截断压缩流和非零 tar 尾部。这里使用标准库逻辑 tar 读取器，**没有验收产品的物理 USTAR profile**，未执行任何包内程序。

| 原包 | 展开 tar 字节 | 成员 | 普通文件 | 目录 |
| --- | --- | --- | --- | --- |
| MPC | 3,758,080 | 357 | 348 | 9 |
| MPFR | 10,045,440 | 591 | 572 | 19 |

920 个普通文件的路径、模式、长度和 SHA-256 已进入机器记录；两个公开头文件的版本宏与目标版本一致。人工重读范围为 README、库头文件、许可文本、手册源码及 config.sub：

- 两个库头文件声明 LGPL v3 或后续版本；不能据此把整个原包统称为 LGPL。
- MPC 带 `COPYING.LESSER` 和 `doc/fdl-1.3.texi`，手册声明 GFDL v1.3 或后续版本且无不变章节；README 有自己的复制分发声明。库存未发现名为 `COPYING` 的 GPL 全文，LGPL 文本引用 GPL v3 的事实仍需在后续分发审阅中处理。
- MPFR 带 `COPYING`、`COPYING.LESSER` 和 `doc/fdl.texi`；手册声明 GFDL v1.3 或后续版本、无不变章节和封面文本。
- 配置辅助脚本有单独的 GPL 声明及配置脚本分发例外；最终保留或嵌入哪些文件、归属与许可文本是否齐全，尚未完成逐项审阅。

完整上游文本留在原包中，Git 内只记录库存和审阅结论。`license_review_complete` 保持 `false`；本批不改变项目许可证、工具版本或 lockfile。

## 签名结构与下一步

两份输入均解析为一个 v4、class 0 的 detached binary-document signature，摘要算法字段均为 8（SHA-256）。MPFR ASCII armor 的 CRC24 一致；这不是密码学认证。公钥算法编号对应 [IANA OpenPGP 登记](https://www.iana.org/assignments/openpgp)。

| 签名 | 声明的公钥算法 | 声明的 issuer 指纹（尚未认证） |
| --- | --- | --- |
| MPC | 17 / DSA | `AD17A21EF8AED8F1CC02DBD9F7D5C9BF765C61E3` |
| MPFR | 22 / EdDSALegacy | `A534BE3F83E241D918280AEB5831D11A0D4DB02A` |

尚未取得或接受这两个发布者公钥，未检查其自认证、撤销状态、签名 MPI 或真实数学签名；签名包中的 issuer 和时间均只是待认证字段。MPFR 固定版本网页仍称其为 DSA key，而本次实际签名字段是 22，应保留差异并以原始材料推进核对，不能照抄网页算法标签。

身份线索来自 [MPC 下载页](https://www.multiprecision.org/mpc/download.html)、同一维护者的 [MPFRCX 下载页](https://www.multiprecision.org/mpfrcx/download.html)所列完整指纹，以及 [MPFR 4.2.2 页](https://www.mpfr.org/mpfr-4.2.2/)所列指纹。MPFR 链接的维护者身份页 `https://www.vinc17.net/pgp.html` 本次被网页工具拒绝打开，未绕过该限制或猜测替代取钥地址；这不表示公钥不存在。网页线索不能代替公钥身份验收。

下一步先明确两个公钥的可访问来源、身份锚点和自认证核对范围，再形成受限验签入口；若选择以现有 Debian 归档认证作为来源终点，则单独审阅这两个精确原包的信任范围。当前四对象授权不包含公钥下载、GnuPG 执行或信任策略扩展。其余四项依赖及发布构建关联仍按[来源路线审阅](musl-remaining-sources-2026-09-16.md)推进。

## 留存、恢复与验证

本批已使用现有内容寻址留存方法，将五次请求的正文 / 日志、方法、机器记录和固定配方原包加入 `artifacts/source-inputs/mpc-mpfr-aa13d7c-20260916`。共 **28 个恢复路径、21 个不同对象、2,784,702 bytes**；[清单](mpc-mpfr-retention-manifest-2026-09-16.json)和[实际恢复结果](mpc-mpfr-retention-2026-09-16.json)记录了全量恢复及逐字节一致。完整重跑还依赖既有 musl 留存和仓库方法，该增量不是独立完整备份。

先前 Downloads 中的 **60.4 MiB** [备份包](musl-backup-2026-09-16.md)保持原样，**不含本批新增 MPC / MPFR 材料**。新旧材料均未宣称异盘备份完成，未上传云端或 Git 远端。

只读重算与合成验证入口：

```bash
python3 docs/records/rust-linux-input-review/inspect-mpc-mpfr-inputs.py
python3 docs/records/rust-linux-input-review/check-mpc-mpfr-inputs.py
./scripts/check-repo.sh
```

18 项合成测试已通过，覆盖库存边界、压缩截断 / 拼接 / 超限、缺失审阅文件、未认证签名字段、弱摘要 / 错误 class / issuer 分歧、损坏 packet / armor，以及超时留存和禁止覆盖已有请求。测试不运行网络请求、GnuPG 或第三方程序。真实材料导出重算与 190,133 bytes 的留存 JSON 逐字节一致；`./scripts/check-repo.sh` 通过（1,166 个文件），`git diff --check` 通过。未重跑 Rust / CI、产品构建、容器或真实验签。无后台进程，原始材料继续留存于忽略目录。

收尾时仍为 `dev`，相对本地 `origin/dev` ahead 2；本批及上一轮备份 / 六项来源路线记录尚未提交，未 push。本批不改写已接受 musl 声明、旧方法或旧诊断 JSON。
