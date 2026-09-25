# 固定 MPC 原包的来源接受审阅

日期：2026-09-25；基线 `dev` / `8d803cb`。用途：向项目所有者交接官方公钥刷新事实，以及该原包经固定 Debian 快照认证的限定来源决定。**项目所有者已确认，固定原包限定归档来源接受通过。** 不定义公共 acceptance 格式，不接受安装、构建、许可证或产品 qualification。

## 官方公钥刷新结果

项目所有者确认 MPFR 限定声明并要求继续推进后，本轮先完成 MPFR 决定同步，再说明并经执行权限确认获取以下三个公开 HTTPS 对象。复用 [fetch-mpc-mpfr-inputs.py](fetch-mpc-mpfr-inputs.py) 的 `fetch()`，将目录限定为 `.tmp/mpc-key-refresh-20260925/`，目标限定为下表；执行前核对方法为 5,126 bytes / SHA-256 `2feb632c6422198255c1f3d46b1be18be8914e2c22e67635ce6a106bb01beeab`。具体目标和方法摘要先写入该目录的 `fetch-plan.json`；其中 `executed: false` 表示执行前计划，实际结果以各请求日志为准。

| 对象与精确 URL | bytes | SHA-256 |
| --- | ---: | --- |
| 下载页 `https://www.multiprecision.org/mpc/download.html` | 8,741 | `fa9e8c70c479bd2599515cec7ea17f8fdacc4f5c0cb85c45375cfb3435c6c438` |
| 指纹页 `https://www.multiprecision.org/mpfrcx/download.html` | 8,272 | `dd742d48f2898cbaeecf9d8a28b052a448a9d4c6676866f0d7fb84708967e0de` |
| 公钥 `https://www.multiprecision.org/downloads/enge.gpg` | 124,014 | `dae0bf8d40b5e3cbb64b3c98fbcf48857f983b8bf811f761a206ebae75f040a8` |

每项限制 256 KiB / 60 秒、父进程 65 秒，HTTPS / TLS ≥ 1.2、不跟随重定向、不自动重试。实际时间为 14:05:31–14:05:52（Asia/Shanghai），三项均一次完成，curl 退出 0 / HTTP 200，无父进程超时，正文合计 141,027 bytes。命令、URL、时间、curl / 方法身份、正文及 stdout / stderr 摘要完整留存；没有安装依赖、导入宿主钥匙环、启动容器或运行 GnuPG。

下载页、公钥与 9 月 16 日留存内容逐字节一致；指纹页本次成功补齐原来 curl 35 / HTTP 000 的材料缺口。按 UTF-8 严格解码、标准库 `HTMLParser` 读取文本及链接：下载页仍链接上述 `enge.gpg`，指纹页列完整主指纹 `AD17A21EF8AED8F1CC02DBD9F7D5C9BF765C61E3`，与公钥结构计算值一致。页面另有 HTTP keyserver 链接，本轮没有访问，不把它引入身份或撤销信息链。

复用 [公钥结构盘点](inspect-mpc-mpfr-key-inputs.py) 的 `inventory()`：仍为一个主钥、两个 UID、232 个 packet；26 份自签候选均声明 SHA-256，两个 UID 最新候选创建时间为 2023-07-05，声明主钥到期时间为 **2024-07-04 08:50:37 UTC**。这些是未数学认证的字段，不等同于 GnuPG 已判定过期；本次没有取得更新认证，也不能断言其他渠道不存在更新。

因此不把本次刷新写成上游验签成功或失败，不倒拨时钟、忽略到期或自动采用历史有效性解释。官方页的完整指纹补齐了身份材料，但不能改变旧自认证字节或替代密码学验证。

## Debian 路线的实际证据

本次接受固定 Debian 快照对**同一压缩原包字节**的归档声明。该路线的限定声明已由项目所有者单独确认，不继承 musl 的既有来源决定；没有换包、改配方或选择相邻版本。

| 对象 | bytes | SHA-256 |
| --- | ---: | --- |
| [固定 InRelease](musl-debian-InRelease-2026-09-10) | 140,416 | `98b25b5cd185c59d34aa6e4c3e9b5b8f01bbe9d104fe2dcfbcd30dc0a14a59ed` |
| 完整 Sources.xz | 10,527,804 | `e8bbadd8389119e841494630998187f961d7de4d5b1dcbeed4f792a1d423299f` |
| `mpc-1.3.1.tar.gz` | 773,573 | `ab642492f5cf882b74aa0cb730cd410a81edcdbec895183ce930e706c1c759b8` |
| [九项真实验签执行导出](musl-verification-success-2026-09-16.json) | 1,174,101 | `d5b9566e7c776a5cec1305b02aff33395074bdf02a0b0b756f1f3e1093d5359a` |

完整 Sources 唯一候选为 `mpclib3 = 1.3.1-1`，目录 `pool/main/m/mpclib3`，原包名 `mpclib3_1.3.1.orig.tar.gz`。其 `Checksums-Sha256` 与本机 MPC 上游原包长度 / 摘要一致；这条绑定不依赖配方的 SHA-1，也不接受 Debian patch 或重打包制品。

本轮执行以下只读复核，没有重新执行密码学：

1. 调用 [collect-musl-verification-execution.py](collect-musl-verification-execution.py) 的 `collect_success()`，按 `json.dumps(..., sort_keys=True, indent=2) + '\n'` 序列化，与上表导出逐字节一致。它复核 66 条命令、九项判定、两必要角色的自认证、原始输入和 InRelease 正文明文对应。名称中的 musl 描述原批次；密码学认证对象是完整 InRelease，而本次 MPC 条目的对应另行核对。
2. 调用 [inspect-musl-remaining-sources.py](inspect-musl-remaining-sources.py) 的 `inspect()`，完整消耗固定 Sources 流，重算与 [9 月 16 日六项盘点](musl-remaining-sources-2026-09-16.json)逐字节一致。取唯一 MPC 候选，核对包名、版本、目录及唯一原包字段。
3. 调用 [prepare-mpfr-verification.py](prepare-mpfr-verification.py) 的 `read_store()`，按既有固定 manifest 复核 MPC / MPFR 原包归档 28 个路径 / 21 个对象、公钥归档 43 个路径 / 31 个对象；从原包归档取 `mpc-attempt-2.tar.gz` 重算字节身份，与上述唯一索引原包完全匹配。另从公钥归档读取旧公钥与本次刷新字节比较。

两必要角色及其真实证据详见 [9 月 16 日执行记录](musl-verification-success-2026-09-16.md)：archive 主钥 `04B54C3CDCA79751B16BC6B5225629DF75B188BD` / signer `B8E5F13176D2A7A75220028078DBA3BC47EF2265`，stable release 主钥 / signer `41587F7DB8C774BCCF131416762F67A0B2C39DE4`，两个 InRelease 签名均为 SHA-256。archive 七项自认证为 SHA-512，release 一项为 SHA-256；交叉认证拒绝、正文篡改及分别缺少角色的真实负例均有记录。额外 bookworm 签名不能替代这两个必要角色；不能宣称两角色的运维或失陷风险相互独立。

这些复核继续信任已有解析器、宿主和先前执行观察，不是独立密码学复验。实际九项 GnuPG 调用发生于 9 月 16 日，本次不冒称新跑了 MPC 上游签名；既有负例也不扩大为 MPC 原包的动态故障注入。

## 已确认的完整限定声明

决定日期：2026-09-25；决定者：项目所有者。审阅提交为 `8a610c7` 后，已向项目所有者解释 Debian 身份、工具 / 宿主信任、精确文件范围及未覆盖事项；项目所有者回复“接受，继续推进吧”，确认下述完整限定声明。该决定仅将指定 MPC 原包记为限定归档来源接受通过，MPC 作者签名仍未验证，历史诊断 JSON 保留产生时点的 `not-assessed`。

> 以 2026-09-10 留存的 Debian 官方 HTTPS / WebPKI 身份资料和两角色公钥为身份起点，接受 Debian 归档维护者对该固定快照的原包标注，信任 2026-09-16 九项验签所用的固定 GnuPG / 发行版工具字节及已记录宿主执行环境的正确性。既有真实验签与本次完整索引、原包字节复核支持：上表固定 InRelease 经完整 Sources，将 773,573 bytes、SHA-256 `ab642492f5cf882b74aa0cb730cd410a81edcdbec895183ce930e706c1c759b8` 的字节串列为 `mpclib3 / 1.3.1-1` 的 MPC 1.3.1 上游原包。结论仅覆盖该固定快照与所持公钥材料时点，不包含此后的撤销信息或验收日最新安全状态，不声称 MPC 作者签名已通过，也不证明代码安全、许可证完备或发布二进制的构建来源。

本次接受的固定工具为 GnuPG 2.4.7，Debian `gpg/gpgconf 2.4.7-21+deb13u1+b4`，image ID `sha256:55063921d0e996f717092e07dce8041cb2376cc171a070bf9a0a38a5dd16c777`，rootfs 8,407,040 bytes / SHA-256 `f1ac49bc29d33182a9c9a070b70509c739d857369876afbe307b9e9898d6b8b3`。具体包、库、运行参数与工具身份绑定上述执行导出及其引用材料。Python / 哈希 / XZ、macOS、Docker / OrbStack / Linux / runc、文件系统、硬件与墙钟仍是可信边界，没有通过工具验证自身材料来消除这些假设。

官方 Debian 身份资料、公钥和验证环境的依据沿 [musl 来源审阅的证据表](musl-source-acceptance-review-2026-09-16.md#精确对象与证据)定位，本次将明确列出的假设用于 MPC，**不继承 musl 的接受决定**。`TRUST_UNDEFINED` 保留，未写入 ownertrust；固定 Release 为 `Debian / stable / trixie / 13.6`、日期 `2026-07-11 09:02:23 UTC`，缺少 `Valid-Until` 不等于永久新鲜。两角色公钥没有在本轮刷新，9 月 25 日刷新的 MPC 公钥不能更新 Debian 钥匙的撤销时点。

本次确认只记录该精确 MPC 原包的限定来源接受，不新增下载、GnuPG 执行、安装、push 或系统变更。原始 JSON 仍保留诊断时点的 `not-assessed`；公共 schema、产品 inactive 登记和安装停止线不变。精确原包、快照、角色、工具字节或身份 / 时点要求变化时须重新审阅。该决定可另行撤回，不改写历史证据。

## 留存、验证与交接

三份正文、请求日志、执行前计划、旧归档读回及本轮复核观察，连同获取 / 结构盘点 / 留存方法，已使用既有内容寻址工具归档到 `artifacts/source-inputs/mpc-key-refresh-8d803cb-20260925/`。共 **18 个路径、14 个不同对象、178,524 bytes**；[清单](mpc-key-refresh-retention-manifest-2026-09-25.json)和[恢复结果](mpc-key-refresh-retention-2026-09-25.json)记录全部恢复到 `.tmp/mpc-key-refresh-restore-20260925/` 后逐项字节一致。这是本机增量，仍依赖既有仓库方法、原包 / 工具归档及九项验签日志，不是完整或异盘备份；没有更新 Downloads 交付包。

复核观察在归档的 `.tmp/mpc-key-refresh-20260925/review-observations.json` 中：生成入口为上节列出的既有函数及请求日志逐项摘要核对，输入由清单绑定；它记录人工审阅阶段的对应结果，不是新验收器或公共 Evidence。原始公钥盘点可在恢复材料后直接调用 `inspect-mpc-mpfr-key-inputs.py` 的 `inventory(raw, EXPECTED['mpc'])` 重算；公钥与旧归档相同的结论须直接比较原始字节。

未修改执行器或解析器；本轮没有新增依赖、锁文件、后台进程或远程写入。限定声明已确认，下一步按当前顺位补 Binutils / GCC / GMP / headers，再推进发布构建关联、Rust 公钥与宿主库。MPC 许可证、补丁与最终链接仍单独验收，不因来源接受而自动通过。

本轮 `python3 docs/records/rust-linux-input-review/check-mpc-mpfr-key-inputs.py` 的 9 项合成回归通过；`./scripts/check-repo.sh` 通过（1,187 个文件），`git diff --check` 通过。未重跑 Rust / CI 或产品构建，未把结构测试升级为签名认证。收尾为 `dev`，相对本地 `origin/dev` ahead 2，未刷新远端；本轮含 MPFR 确认同步共 10 个工作区文件未提交、未推送。原任务目录和恢复目录保留，没有清理既有材料。

确认轮仅记录项目所有者的接受决定，没有重跑九项密码学或改变原始诊断。随后 [Binutils 原包材料切片](binutils-inputs-2026-09-25.md)的三项获取经单独执行权限确认完成；MPC 来源接受不作为新的网络执行授权。
