# musl 1.2.5 强摘要认证候选审阅

日期：2026-09-10；基线 `0a66901`。本轮只完成网页检索、既有公开 keyring 的本地读取和下一批诊断范围设计；没有取得新的原始签名索引、运行容器或改变 acceptance 条件。

执行状态：该范围随后获项目所有者授权，实际下载、两次离线诊断及结果见 [Debian 强摘要链记录](musl-debian-auth-2026-09-10.md)。下文保留执行前审阅，不将候选描述改写为历史成功。

## 结论与候选

既有 [musl 原包诊断](musl-source-2026-09-10.md)仍然成立：包分离签名、公钥 UID 自认证和 subkey binding 均使用 SHA-1，严格签名条件拒绝。此次检索尚未取得同一原包的现代上游签名；这不证明上游不存在其他材料。

建议下一批验证 **Debian trixie 归档签名 → Sources 的 SHA-256 → 已有 musl 原包**，只增加发行版来源诊断。成功也不能改写为 musl 上游现代签名通过，更不自动接受 Debian 作为该输入的最终信任根。

| 路线 | 本轮依据 | 尚缺什么 |
| --- | --- | --- |
| 上游强摘要签名 | 已有精确原包与旧签名；官网发布页、tag 页面本轮网页读取未成功 | 同一字节的现代签名及可接受的 key binding；不能把未找到写成不存在 |
| Debian 归档链（优先诊断） | [trixie 源码页](https://packages.debian.org/source/trixie/musl)实际打开时列 `1.2.5-3.1~deb13u1`，包含 `musl_1.2.5.orig.tar.gz` | 实际 InRelease 验签、完整 Sources 摘要绑定及原包 SHA-256；当前网页只列 MD5，不据此认定字节相同 |
| 仅接受官网 HTTPS 加本地摘要 | 可固定现有下载字节 | 这是额外的窄信任决策，不能冒充补齐签名；本轮未提议直接启用 |

网页搜索缓存曾显示 Debian `1.2.5-3`，随后打开页面显示上述更新版本；后续必须固定实际签名索引的版本与时间，不用缓存摘要挑选旧版本。原始 `.dsc` 网页读取亦失败，未把网页内容或邮件中的 `Hash: SHA512` 声明当成已经完成密码学验证。

[apt-secure](https://manpages.debian.org/trixie/apt/apt-secure.8.en.html)说明归档签名认证的是归档维护者及其完整性链，不能保证包内代码无恶意，也不等于包级签名核验。这正是本候选新增的信任边界。

## 可复用的本地材料与方法

[已有 Debian 观察](../linux-builder-source-chain/release-verification.json)保留完整公开 keyring，解码后为 55,918 bytes，SHA-256 为 `506b815cbb32d9b6066b4a2aa524071e071761e7e7f68c3ac74f3061ba852017`。本轮重算相符，并从主钥 packet 重算得到以下完整标识：

- trixie archive：`04B54C3CDCA79751B16BC6B5225629DF75B188BD`；
- trixie stable release：`41587F7DB8C774BCCF131416762F67A0B2C39DE4`。

两者与 [Debian FTP key 页面](https://ftp-master.debian.org/keys.html)列示一致。packet 标识不是新验签结果；用于 OpenPGP v4 指纹标识的 SHA-1 计算也不是对 SHA-1 签名算法的接受。已有 keyring 包含候选所需两把主钥，因此无需先下载新公钥或修改宿主 keyring。

FTP 页面明确提醒不要仅凭页面建立信任；所链接的 trixie key announcement 本轮返回 403。既有镜像、公钥环来源及独立身份认证缺口继续保留。下一批需检查实际签名、有效期 / 撤销状态、所用签名 subkey 的绑定与相关自认证算法，不能只比较指纹。

复用 [Debian 索引诊断方法](../../../scripts/inspect-debian-source-chain.py)的有界 XZ / Deb822 解析、SHA-256 行解析及文件字节检查。其现有入口固定 bookworm、三包和两个 bookworm 签名角色，不能直接运行后宣称已核验 trixie。下一批仅在本诊断记录内组合已有解析函数及 trixie 的精确选择，不改变 bookworm 历史要求，也不另造自动安装入口。

## 下一批待授权的精确执行范围

以下为尚未执行的候选，批准它只授权取得材料和诊断，不接受新的产品信任策略：

1. 下载 `https://deb.debian.org/debian/dists/trixie/InRelease`，单文件最多 512 KiB、60 秒。保留原始字节、HTTP 结果、长度、SHA-256 和每次尝试的日志。
2. 在既有固定镜像中离线核验该 InRelease，要求上述两个 trixie 主钥角色都成功，不用其他发行版签名替代。仅允许 SHA-256 / SHA-384 / SHA-512；检查失败、过期、撤销、重复签名和算法异常。记录实际正文、版本、发布日期及有效期；缺少有效期只能说明固定快照，不能推出最新安全状态。
3. 仅在上一步通过后，从已验证正文选出唯一 `main/source/Sources.xz` 的长度和 SHA-256，再访问 `https://deb.debian.org/debian/dists/trixie/main/source/by-hash/SHA256/<该摘要>`。上限 16 MiB、120 秒；域名、路径前缀和 64 位十六进制摘要固定，不跟随索引中任意 URL。
4. 主机有界读取 Sources（展开上限 256 MiB、XZ 内存上限 128 MiB），要求唯一 `musl`、版本 `1.2.5-3.1~deb13u1`、目录 `pool/main/m/musl`，以 `Checksums-Sha256` 核对现有原包。索引版本漂移或缺项时停止，不自动换包。目标是已有 1,080,786 bytes、SHA-256 `a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4`；不重新下载源码、Debian patch 或二进制。

下载固定 HTTPS / TLS ≥ 1.2；普通网络请求失败时保留日志，最多各重试一次相同目标，不换源。材料和日志仅写入 `.tmp/musl-auth-chain-0a66901/`；已有源码只读。预计下载与诊断 3–6 分钟，不含失败排查。

离线容器使用镜像 `sha256:a339861ae23e9abb272cea45dfafde21760d2ce6577a70f8a926153677902663`，`--pull=never`、`linux/arm64`、`--network=none`、只读根 / 输入、非 root、drop ALL capabilities、no-new-privileges，512 MiB / 1 CPU / 64 pids，临时 `/tmp` 为 64 MiB `noexec,nosuid,nodev`。最多两次，每次 120 秒；第二次仅供有记录的方法修正复验。只执行自有诊断脚本及已盘点的 GnuPG 工具，不运行包内程序。

容器名限定 `radishaxiom-musl-auth-0a66901-attempt-1` / `radishaxiom-musl-auth-0a66901-attempt-2`，退出 `--rm` 删除；临时 keyring 随 tmpfs 清除，宿主缓存留存复核。没有安装、编译、系统配置修改、远程写入或正式 source lock 变更；无需回滚产品状态。若签名或 key binding 不满足要求，保留失败并停止，不增加弱算法兼容选项。

## 验收后的决策边界

诊断成功最多支持“Debian 签名快照将该 SHA-256 字节串列为 musl 上游原包”。是否据此接受该来源、如何承担 Debian 归档维护者与公钥 bootstrap 的信任，仍需项目所有者在实际结果可审阅后明确决定。四份 Rust / musl-cross-make patch、发布构建关联和最终静态产物身份继续分别核对。

本轮仅作设计与材料审阅；验证限于公开 keyring 长度 / 摘要 / packet 标识复算、文档一致性与仓库检查。未重新运行 GnuPG、patch、Rust / CI、安装或构建。
