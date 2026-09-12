# musl 最小验证环境来源审阅

日期：2026-09-12；基线 `dev` / `d04b225`，启动时工作区干净，与本地 `origin/dev` 一致，未查询远端。用途：供来源审阅者确定验证环境候选、未闭合依赖、复核命令和下一次精确获取范围。本文是设计与本地材料盘点，不是工具 acceptance、完整 source lock、安装或运行授权。

后续：本记录已随 `fa8d010` 提交，项目所有者随后授权继续；固定索引已取得并形成[17 个精确包的后续盘点](musl-verifier-packages-2026-09-12.md)。下文“待授权”“尚未取得”及工作区状态保留前批时点，当前事实见该后续记录；工具信任终点仍未接受。

## 本批结论与路线

推荐审阅同一 trixie 快照中的 **GnuPG 2.4.7 系列 arm64 公钥操作工具及其实际运行闭包**，随后从已审阅包字节组装新的最小 rootfs，以现有 Docker / OrbStack 的 Linux 宿主运行离线复核。宿主仍是显式可信输入；新 rootfs 不继承旧 Rust 镜像的来源结论。暂不创建 rootfs 或镜像，不执行候选工具。

这一路线尚有两个不同的前置：

1. **取得完整二进制索引并锁定实际包。** 本地固定 Sources 含 `gnupg2=2.4.7-21+deb13u1`，但同一索引存在三个 `glibc` 版本、两个 `libgcrypt20` 版本；源码包版本也不能替代 arm64 binary 的 binNMU 修订号。缺少对应 Packages 时，不能填写一个看似精确的库闭包。
2. **明确工具的初始信任终点。** 建议在包清单固定后，另行确认以 Debian 官方 HTTPS / WebPKI 取得的精确发行版二进制作为本次验证工具的可信起点，再用签名链作一致性复核。此前接受官方 HTTPS 的范围是 musl 归档公钥身份，不自动覆盖工具二进制。尚未接受此新增信任假设；不以新 GnuPG 验证自身所在的 Packages 就宣称来源自举完成。

不要求先从零重建 Debian 全部工具，但须明确发行版构建正确性、主机及运行时仍被信任。若不接受这个工具信任终点，需选择另一个已有可信验证环境；此时保持阻断，不回退到旧镜像或弱签名。新版本尚未复现旧 double-free，不能宣称该故障已修复。

## 已复核材料与候选身份

[盘点方法](inspect-musl-verifier-sources.py)复用已有有界 Deb822 / XZ 读取入口，先核对固定 InRelease 和 Sources 摘要，再保留 13 个候选源码家族的全部 16 条记录；不按版本字符串排序选“最新”，不推导安装闭包。[输出](musl-verifier-sources-2026-09-12.json)保留源码文件摘要字段、方法摘要和下一份索引身份，明确 `signature_reverified = false`、`binary_selection_complete = false`、`runtime_closure_assessed = false`。

| 角色 | 同一 Sources 的候选版本 | 待核对内容 |
| --- | --- | --- |
| `gnupg2` → `gpg` / `gpgconf` | `2.4.7-21+deb13u1` | arm64 binary 修订、两工具是否实际需要、包内程序 / 许可 |
| `libgcrypt20` | `1.11.0-7`、`1.11.0-7+deb13u1` | 由 Packages 的 Source 绑定消歧 |
| `glibc` → `libc6` / loader | `2.40-5`、`2.41-11`、`2.41-12+deb13u3` | arm64 归属、loader 链接目标、符号版本 |
| `libassuan`、`libgpg-error`、`libksba`、`npth` | `3.0.2-2`、`1.51-4`、`1.6.7-2`、`1.8-3` | binary 修订及递归库需求 |
| `bzip2`、`readline`、`sqlite3`、`zlib`、`ncurses` | 逐项见盘点 JSON | 实际压缩 / 终端 / 数据库库及传递依赖 |
| `init-system-helpers` | `1.69~deb13u1` | 区分包安装依赖与离线公钥操作运行依赖 |

2026-09-12 阅读 [Debian gpg 包说明](https://packages.debian.org/trixie/gpg)，页面列出 arm64 `2.4.7-21+deb13u1+b4` 及库依赖，并说明该包可用于公钥操作；这仅是候选导航，不是本快照 binary 的锁定依据。此次网页读取经浏览工具完成，未将页面原始字节持久留存，不把搜索缓存版本或网页包大小当作下载摘要。

本批重新读取下列既有缓存，长度与 SHA-256 均匹配历史记录：

| 输入 | bytes | SHA-256 |
| --- | --- | --- |
| InRelease | 140,416 | `98b25b5cd185c59d34aa6e4c3e9b5b8f01bbe9d104fe2dcfbcd30dc0a14a59ed` |
| 完整 Sources.xz | 10,527,804 | `e8bbadd8389119e841494630998187f961d7de4d5b1dcbeed4f792a1d423299f` |
| musl 原包 | 1,080,786 | `a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4` |
| 官方指纹页面 | 10,718 | `b271f4c351a3b54f6a6be9667bb834809d12ee514055b903ccb06839d274e3e0` |
| 精确 keyring 包 | 178,572 | `f699e2f88dca05212f2a452b58475f2993cb6993dfbafb1d0205a3291eb8b4b8` |
| archive 公告 HTML | 29,691 | `5384b92ed7ad6cf8ce31afff8b5edf88fc0e997ef641c7c43bffc0660d92615d` |

路径沿用[前批公钥记录](musl-key-status-2026-09-10.md)与[原包诊断](musl-debian-auth-2026-09-10.md)，没有重复下载或移动。公钥原文已有 Git 副本；完整 Sources、原包、网页及 keyring 包仍依赖忽略缓存。下一持久留存方案须明确存储位置、项目所有者的保留责任、备份和恢复检查；未指定或写入远程存储。本次清单及摘要不替代这些原始文件，也不解决单文件 10 MiB 上限。

## 宿主与运行库边界

本批只读确认 PATH 未发现 `gpg`、`gpgv`、`sq`。主机为 macOS `26.6.2` / build `25G83`；Python 为 `3.14.5`。以下仅是实际文件身份，不是来源认证或完整动态依赖闭包：

| 主机工具 | 解析后的文件 | bytes / SHA-256 |
| --- | --- | --- |
| Python | mise 下 `python/3.14.5/bin/python3.14` | 18,053,472 / `c015ab131972822e27ed108cf353582af6ca2fd7daf6296789576c7e7d1ad61a` |
| curl | `/usr/bin/curl` | 551,152 / `b636262803922ee1dd0fbf614818473ffa53c811e44fd3278c2270d3af4759d3` |
| Docker 命令入口 | `/Applications/OrbStack.app/Contents/MacOS/xbin/docker-tools` | 72,126,112 / `c93921f27c941f7661e5478e8af4042e546b66e69707a2b43f31a86cfe9c85d2` |

未连接 Docker daemon、启动 OrbStack 或查询 Linux kernel；Docker CLI、daemon、OrbStack、Linux kernel 的精确运行版本仍待只读运行盘点。Python 的解析 / XZ / SHA-256 实现、curl / TLS / 证书信任、macOS、Linux 宿主、硬件、文件系统及墙钟均进入可信计算基础（TCB）；程序摘要不能替代其中任何一项的来源说明。

后续二进制来源审阅应从固定 Packages 选择 `gpg` 起，核对 Depends / Pre-Depends 的完整语法、版本约束及架构；`gpgconf` 列为候选，是否进入实际运行闭包由操作与进程观察决定。`Recommends` 不自动触发整个 `gnupg` 套件安装。取得精确包之后：

- 先按索引长度 / SHA-256 核对 `.deb`，有界审阅 control、data、copyright、链接与权限；不运行 maintainer scripts。依赖声明、包内 ELF 的 `DT_NEEDED`、loader / RPATH / RUNPATH、符号版本和实际加载映射分别留证。
- rootfs 只含已审阅的程序、闭包、必要数据和许可文件；任何遗漏库、子进程、NSS / `dlopen` 需求都停止并重新补审阅，不从旧镜像、宿主目录或联网包管理器自动补齐。
- 采用空的 GnuPG 配置与独立 home；不挂载宿主 keyring、agent socket、Docker socket、用户 HOME。实际启动方式、rootfs 摘要、资源限制、日志提取、失败终止和镜像清理由后续精确运行方案定义，未就绪前不提供可执行的 Docker 命令冒充完成。

## 密码学复核命令清单（设计，未执行）

完整复核继续要求 archive 主钥 `04B54C3CDCA79751B16BC6B5225629DF75B188BD`、实际 signer `B8E5F13176D2A7A75220028078DBA3BC47EF2265`，以及 stable release 主钥 / signer `41587F7DB8C774BCCF131416762F67A0B2C39DE4`。两角色是合取条件；bookworm 附加签名不替代它们。

以下是将来已验收 rootfs 内 `/usr/bin/gpg` 的参数设计，不能直接在当前主机运行。每次均附加以下公共参数，home 在执行前以 `0700` 创建：

```text
--batch --no-tty --no-options --homedir /work/full
--no-autostart --no-auto-key-retrieve --auto-key-locate clear
--no-auto-key-import --no-sig-cache --require-cross-certification
```

运行环境明确 `LC_ALL=C`、固定 PATH / HOME、空的 `/etc/gnupg` 和 home 配置，stdin 接空输入；不设置弱摘要兼容、忽略时效或 always-trust。参考 [GnuPG 配置说明](https://gnupg.org/documentation/manuals/gnupg/GPG-Configuration-Options.html)：强制交叉认证检查实际 back signature，列出 packet 文本本身不足以验证它；`--assert-signer` 的多指纹含义是至少一个匹配，不能用它实现两角色同时成立。

| 顺位 | 附加参数 / 本地步骤 | 必须保留与判定 |
| --- | --- | --- |
| 0 | `--version`；核对包内二进制、loader 和实际加载库 | 符合固定字节与版本；帮助文本不代替执行闭包 |
| 1 | `--status-fd 1 --import /inputs/debian-archive-keyring.gpg`；随后分别 import 两份经身份核对的官方公钥 | 保留完整 keyring 中的撤销及导入状态；输入摘要逐项绑定；新公钥变化先审阅 |
| 2 | 将 home 改为 `/work/self`，以 `--import-options self-sigs-only --import` 分别处理相同三份输入 | 隔离第三方 certification 诊断；不能替代 full home 的撤销检查 |
| 3 | self home 中分别运行 `--with-colons --fixed-list-mode --with-fingerprint --with-subkey-fingerprint --check-sigs` 加两个完整主指纹 | 自认证、UID 绑定、signing subkey binding 必须实际验证；完整 issuer 指纹、签名 class、时间和摘要符合条件 |
| 4 | full home 中分别运行 `--output /work/角色.gpg --export` 加完整主指纹，再 `--list-packets /work/角色.gpg` | 两角色原始导出摘要、撤销 packet、嵌入 back signature 和全部强摘要字段；不把仅出现 class `0x19` 当成验证成功 |
| 5 | full home 中 `--status-fd 1 --output /work/Release --decrypt /inputs/InRelease` | 两个必要 `VALIDSIG` 的主钥及实际 signer 精确匹配，摘要只允许 8 / 9 / 10；任一错误、过期、撤销、缺角色或非零退出均停止 |
| 6 | 主机重算验证正文与原 InRelease 的 cleartext 绑定；从 SHA256 字段绑定完整 Sources，再唯一选择 musl 条目并重算原包 | 同一原始快照和同一原包；不能直接采用旧 `verified_text` 或读取预期结果决定通过 |

指定核对时间须记录本次执行开始 / 结束 UTC、宿主时钟来源，以及每项 key / signature 的创建、到期与撤销状态。默认使用实际核对时钟；历史回放另标时间，不改系统时间。[Debian gpg 手册](https://manpages.debian.org/trixie/gpg/gpg.1.en.html)说明 `--no-autostart` 禁止自动启动 agent / dirmngr，`--faked-system-time` 是测试选项；二者均不能解决密钥材料是否新鲜的问题。

目前官方公钥实际获取时间仍为 2026-09-10，未刷新。只用这些字节执行时，结论必须限定为“在指定核对时间、对截至该获取时点的材料验签”；不报告 2026-09-12 所有渠道均未撤销。如正式验收要求截至执行日的官方端点状态，另行明确两公钥 / 身份页面刷新范围；这与不重复下载未变化的原包、Sources 是不同目的。公告签名及第三方认证不在所选 HTTPS 身份保证中承担独立证明，仍不得标为已验证。

所有命令分别保留 argv、退出码、stdout / stderr、输入 / 输出摘要和实际时间。崩溃、超时、输出超限、未知状态或输出格式漂移不准归为成功；新收集器须适配 2.4 的真实输出并保留新方法，不改写旧 execution JSON 或把新结果灌入固定命名的历史 `offline-invocation-3.stdout`。

后续验收集合须含同一原始链正例，以及缺一个角色、错误 signer、弱签名 / 自认证、过期 / 撤销、缺失或无效交叉认证、被改动 Release / Sources / 原包、子命令崩溃 / 超时和库解析越界。状态解析合成测试与真实密码学负例分开报告；不得生成新密钥去冒充 Debian 真实身份。

## 下一次获取：只取固定 arm64 索引（待授权）

固定 URL：

```text
https://deb.debian.org/debian/dists/trixie/main/binary-arm64/by-hash/SHA256/753da751bbc7a679f48bd1b623ffd4479cb6861c426118284c76eb82909e4908
```

预期为 **9,607,412 bytes** / SHA-256 `753da751bbc7a679f48bd1b623ffd4479cb6861c426118284c76eb82909e4908`，直接来自已留存 InRelease 的 SHA256 段。本地 `.tmp` 检索只发现旧 bookworm Packages，未发现该 trixie 索引。by-hash 对象能否仍从服务器取得尚未知；404 或摘要漂移时停止，不改用当前 rolling 索引。

已复用[既有 fetch 方法](fetch-musl-trust-inputs.py)准备[精确差异](musl-verifier-index-fetch-method.patch)：仅保留 `packages` 目标、12 MiB 响应上限并增加精确长度 / SHA-256 成功条件。原方法及历史日志不改写。准备脚本位于 `.tmp/musl-verifier-d04b225-20260912/fetch-musl-verifier-index.py`，SHA-256 为 `37225785634c2108d46b8522cc83fc23cddccb10cad70ac7d7ea4168257ddbfe`；原方法为 `af211b69e88d500840cee1d55ad48e2ddaee3628e2f32d397272f14640c2e822`。文件已创建并做语法检查，尚未调用 curl。

授权后在仓库根执行：

```bash
python3 .tmp/musl-verifier-d04b225-20260912/fetch-musl-verifier-index.py packages 1
```

仅首轮连接 / 传输失败且状态符合原方法时允许 `packages 2` 一次；不得因内容不符、3xx、403、404、超限而重试或换地址。HTTPS / TLS ≥ 1.2、不跟随重定向、不降级证书验证，每次 60 秒、父进程 65 秒上限；最多两次、累计正文上限 24 MiB，预计获取与索引盘点 2–5 分钟。中断时保留原始日志与未完成记录，不把空 JSON 当成功。脚本记录 HTTP、退出码、原始输出身份及方法摘要；传输通过与内容匹配必须同时成立。

副作用只有一个固定公开 HTTPS 目标请求和任务目录内的新文件。不下载 `.deb`、源码、公钥、镜像或安装工具，不运行容器；不接受新增工具信任终点，不改系统或产品状态。完成后先离线核对索引并提出精确包清单及库边界。文件保留供复核，无后台进程；无需系统回滚。如后续清理，仅处理经确认的本批文件，不递归删除目录或清除旧缓存。

## 验证与交接

可重跑的本地盘点入口：

```bash
python3 docs/records/rust-linux-input-review/inspect-musl-verifier-sources.py \
  .tmp/musl-auth-chain-0a66901/Sources.xz
python3 docs/records/rust-linux-input-review/check-musl-debian-auth.py
./scripts/check-repo.sh
git diff --check
```

本批盘点生成与重跑均成功，输出与留存 JSON 逐字节相同；fetch 差异经实际 patch 重建，与任务目录准备方法逐字节相同，准备方法通过 Python 语法检查。现有 Debian 诊断 9 项合成检查通过；仓库检查通过（1,088 文件），`git diff --check` 通过。合成检查不执行密码学验签，准备方法未做真实网络执行验证。

工作区仅有本批当前状态修改和四个新增记录 / 方法文件，未暂存、未提交或推送；任务目录仅含准备方法及重建副本，无后台进程。尚未重新验签、取得索引、安装、构建、执行容器、运行 Rust / CI 或写入远端。musl `acceptance = not-assessed`、旧 payload inactive、公共契约与当前产品执行停止线均保持原义。
