# musl 信任补证：trixie 公钥与公告

日期：2026-09-10；基线 `dev` / `ef02b43`。用途：供来源审阅者核对已定位的三份公开材料、它们与既有 keyring 的关系及剩余验证环境门槛；不是来源 acceptance 或新密码学验签。项目所有者要求提交已有更改并继续下一步；本批先完成提交，再按[前批定位的三个 URL](musl-trust-inputs-2026-09-10.md#页面身份依据及未访问的链接)取得材料。

## 本批结论

两份官方公钥的 ASCII 原文及解码内容分别与精确 keyring 包内对应文件逐字节相同，解码 SHA-256 同时匹配旧 GnuPG 导出摘要。trixie 公告已取得，确认其正文列出的 archive 主指纹、签名 subkey 和公钥文件 SHA-256 与本批一致；公告不包含 stable release 主指纹。结果见[本地核对 JSON](musl-key-status-2026-09-10.json)，仍为 `acceptance = not-assessed`。

| 输入 | bytes | SHA-256 |
| --- | --- | --- |
| [archive 公钥原文](debian-trixie-archive-2026-09-10.asc) | 11,861 | `6f1d277429dd7ffedcc6f8688a7ad9a458859b1139ffa026d1eeaadcbffb0da7` |
| [stable release 公钥原文](debian-trixie-release-2026-09-10.asc) | 1,384 | `4d097bb93f83d731f475c5b92a0c2fcf108cfce1d4932792fca72d00b48d198b` |
| trixie 公告 HTML（任务缓存） | 29,691 | `5384b92ed7ad6cf8ce31afff8b5edf88fc0e997ef641c7c43bffc0660d92615d` |

公钥原文已进入 Git 待提交文件，网页完整原文仅保留于 `.tmp/musl-key-status-ef02b43-20260910/announcement-attempt-2.html`，不把来源未审阅的邮件网页整页复制进仓库。公钥来源分别是 `https://ftp-master.debian.org/keys/archive-key-13.asc` 和 `https://ftp-master.debian.org/keys/release-13.asc`；它们与[前批已读 keyring 包](musl-trust-inputs-2026-09-10.md#包内字节对照与方法边界)中的公钥文件字节相同，沿用该包公开公钥材料的来源 / 许可说明，不归为项目自有代码，不包含私钥。

## 公告覆盖的身份及未验证声明

[公告页面](https://lists.debian.org/debian-devel-announce/2025/04/msg00001.html)显示作者 Ansgar、邮件日期 `2025-04-06 14:56:33 +0200`、主题为 Debian 13/trixie 新归档签名钥。它公布 archive 和 security archive 两类钥，并说明当时尚未立即启用、计划进入 trixie 及后续 bookworm point release。该日期是邮件页面声明，不是本批下载时间或独立验证的签名时间。

archive 主指纹为 `04B54C3CDCA79751B16BC6B5225629DF75B188BD`，签名子钥为 `B8E5F13176D2A7A75220028078DBA3BC47EF2265`；其公钥 URL / SHA-256 与本批下载完全匹配。正文还声称新钥由两位 FTP masters 和既有 bookworm 归档钥认证，并带有 `Hash: SHA512` 的 clearsigned 外壳。本轮未验证公告签名或第三方认证链，因此只记录这些声明，不将其用作已建立的独立信任链。

公告没有 `41587F7DB8C774BCCF131416762F67A0B2C39DE4`，不能拿 archive / security 公告替代 stable release 的角色说明。stable release 的身份材料仍明确来自已核对的官方指纹页面、对应公钥 URL 和精确 keyring 包；本轮没有查到另一份 stable release 公告，也没有将未检索到写成不存在。

在[已确认的 Debian 官方 HTTPS / WebPKI 起点](musl-debian-auth-2026-09-10.md#项目所有者确认与执行顺位)下，两角色目前均有可审阅的页面身份映射、官方公钥字节和发行包对照。archive 公告提供额外发布说明，但这些材料共享 Debian 发布方与 HTTPS 信任体系。若将来要依赖公告签名或第三方认证承担独立身份保证，须单独核对 signer 的既有信任依据，不能自行扩大当前声明。

## 相同字节与密钥时效的区别

[检查方法](inspect-musl-key-status.py)只读取三个固定摘要输入，并复用前批有界 ar / tar 读取方法。既有 `.deb` 原始字节保持只读；没有提取到系统目录、调用 GnuPG 或导入 keyring。新 `.asc` 同时与包中 `etc/apt/trusted.gpg.d/` 的 automatic / stable `.asc` 及 `usr/share/keyrings/` 的对应 `.gpg` 对照：

| 角色 | 解码 bytes / SHA-256 | 旧 GnuPG 观察中的到期时间（UTC） |
| --- | --- | --- |
| archive 主钥及签名 subkey | 8,698 / `8dbd0029697f8c9b009eeb9a153c6536b62ca031fa0a5b4cec74e8d718fccef6` | 主钥与子钥均为 `2035-03-28 12:50:29` |
| stable release 主钥 | 962 / `abced156a22aa8683b228299ac35c1ea51515eef900cec0e562f56716dfe3915` | `2033-03-22 18:56:21` |

指纹、签名关系及到期字段沿用[旧实际 GnuPG 观察](musl-debian-execution-2026-09-10.json)，本轮未独立重新解析或验证 OpenPGP 签名。解码只用于包内字节比较，armor CRC 不作为认证依据；原始 ASCII 字节另有固定 SHA-256 和直接对照。

两个官方端点在本次获取时返回的公钥字节没有变化，因此未在这些返回材料中引入相对旧导出的新增撤销 packet。但此结论仅覆盖实际取得的材料，不能证明其他渠道没有撤销，不能把旧 GnuPG 的无撤销 / 未过期结果改写为当前重新验签的结论。结果 JSON 明确保留 `signature_reverified = false` 和 `current_revocation_status_verified = false`。后续验证须固定核对时间及所查材料集合，保留未覆盖其后或其他渠道更新的边界。

## 下载与验证环境观察

[执行 JSON](musl-key-status-execution-2026-09-10.json)留存六次请求及本地检查结果。[下载方法差异](musl-key-status-fetch-method.patch)仅替换前批 [fetch-musl-trust-inputs.py](fetch-musl-trust-inputs.py) 的固定目标表；两份方法的 SHA-256 均保留，不重写前批方法。三个目标各限 512 KiB / 60 秒、HTTPS / TLS ≥ 1.2，不跟随重定向或页面其他链接；仅连接 / 传输失败允许一次同 URL 重试。任务目录独占创建为 `.tmp/musl-key-status-ef02b43-20260910/`。

三项首轮均因沙箱无法连接代理而退出 7 / HTTP 000；在沙箱外获准重试后，均退出 0 / HTTP 200。成功下载分别发生于 `2026-09-10 13:51:05–13:51:07 UTC`、`13:51:16–13:51:18 UTC`、`13:51:29–13:51:31 UTC`。共三个固定目标、六次请求，响应正文累计 42,936 bytes。没有下载 security key、其他公告、验证器、库或镜像；公告正文自带的 security 公钥仅作为该 HTML 的一部分读取，未导入或用于信任判断。

为确定下一验证环境的已有条件，本轮另作两项只读观察：

- `command -v gpg gpgv sq openssl` 仅返回 `/opt/homebrew/bin/openssl`，退出 1；只能说明本次 PATH 未找到前三个命令，不代表整台主机没有它们，也不据此接受 OpenSSL 为 OpenPGP 验证环境。
- Docker `image inspect` 首轮被沙箱 socket 权限拒绝，获准只读重试后，仍得到原 image ID / RepoDigest、Linux arm64 及五个 RootFS layer 标识。输出只选这些字段，未读取环境变量或凭据，未创建 / 启动容器、pull 或修改镜像。标识并非原始 OCI manifest / config / layer 字节或发布者认证，镜像来源缺口没有因此闭合。

没有安装、构建、系统 keyring 修改或远程写入，无后台进程需要清理；缓存原文和日志留存，未删除旧材料。来源 acceptance、安装授权、公共身份迁移和产品运行均未改变。

## 复核与下一步

```bash
python3 docs/records/rust-linux-input-review/inspect-musl-key-status.py \
  .tmp/musl-key-status-ef02b43-20260910 \
  --keyring-package .tmp/musl-trust-bbbe083-20260910/keyring-attempt-2.deb
./scripts/check-repo.sh
git diff --check
```

检查输出同时绑定新检查方法、复用方法和旧 GnuPG execution JSON。检查依赖公告缓存及精确 `.deb`；可用本目录保留的两份 `.asc` 恢复对应 `archive-attempt-2.asc` / `release-attempt-2.asc` 后重算，但没有公告或 `.deb` 时不得声称完整复核。新下载仍须明确授权；重跑本地主机字节核对不调用 GnuPG 或网络。

收口验证：六次请求的正文及 stdout / stderr 长度 / 摘要均与执行 JSON 相符，保留公钥与下载原文相同；下载方法差异可从前批方法与本批执行文件精确重建。本地检查首次退出 0、stderr 为空，重跑输出与本目录结果 JSON 逐字节一致。仓库检查通过（1,083 文件），`git diff --check` 通过；未运行新密码学验签、Rust / CI、容器、安装或构建，不将字节比较当作上述未执行验证。

下一步集中审阅**来源明确的最小验证环境**：精确工具与运行库、供应来源和字节绑定、宿主 / kernel 等可信输入、以及两角色验签、自认证、cross-certification、时间 / 撤销与失败传播的完整复核命令。现有 PATH 没有可直接采用的候选，旧镜像也未验收，因此本轮不编造工具版本或自动安装。接受发行版二进制作为工具信任终点须显式记录，不以重建全部工具为默认要求；具体新增工具 / 环境及运行仍另行授权。原始 Sources、原包及网页的持久留存继续单列，musl 上游 SHA-1 拒绝与 `acceptance = not-assessed` 保持不变。
