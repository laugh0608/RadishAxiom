# musl 原包的 Debian 强摘要链诊断

日期：2026-09-10；诊断基线 `0a66901`。按项目所有者对[精确范围](musl-authentication-route-2026-09-10.md)的授权，取得 trixie InRelease 和完整 Sources 索引，在固定镜像内完成离线诊断。该诊断批次未接受新的产品信任策略，未改写 musl 上游签名拒绝，未安装、编译或执行源码。

用途：供来源审阅者追溯该原包的诊断和信任边界，不作为产品 acceptance 或安装授权。[基于 `70b7235` 的信任审阅](#仅限该原包的信任审阅待确认)保留提交时的候选状态；项目所有者随后已[确认有条件信任方案](#项目所有者确认与执行顺位)，来源验收仍未完成。

## 实际结论

**Debian trixie 签名快照绑定的 musl 1.2.5 原包，与已有原包的长度和 SHA-256 完全一致。** [链结果](musl-debian-chain-2026-09-10.json)为 `archive_diagnostic_passed = true`、`source_bytes_checked = true`，仍为 `acceptance = not-assessed`。

| 材料 | bytes | SHA-256 |
| --- | --- | --- |
| [InRelease 原文](musl-debian-InRelease-2026-09-10) | 140,416 | `98b25b5cd185c59d34aa6e4c3e9b5b8f01bbe9d104fe2dcfbcd30dc0a14a59ed` |
| 完整 Sources.xz（任务缓存） | 10,527,804 | `e8bbadd8389119e841494630998187f961d7de4d5b1dcbeed4f792a1d423299f` |
| 既有 `musl-1.2.5.tar.gz` | 1,080,786 | `a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4` |

实际 Release 为 `Debian / stable / trixie / 13.6`，日期 `2026-07-11 09:02:23 UTC`，未提供 `Valid-Until`。这是固定发布快照的一致性诊断，不能推导最新安全状态。

完整索引选中唯一 `musl` / `1.2.5-3.1~deb13u1`，目录为 `pool/main/m/musl`；其 `Checksums-Sha256` 绑定原包长度 / 摘要。原包只重读既有缓存，未从 Debian 重新下载或换包。索引还列 `.dsc`、上游 `.asc` 和 Debian patch 包；本轮保留这些索引字段，没有下载它们，也没有采用 Debian patch 替换 Rust / musl-cross-make 的四份 patch。

## 签名、自认证与仍未接受的信任

[GnuPG 原始观察](musl-debian-execution-2026-09-10.json)保留版本、程序摘要、输入摘要、公开 keyring 导入、自认证检查、原始 key packet、全部签名状态及验证正文。使用 GnuPG `2.2.40` / libgcrypt `1.10.1`，程序 SHA-256 为 `c3f988abfbf4a51ec36e90437045c1ea45464aadc691a2f78f81c41a31587075`。

| 角色 | 实际签名钥完整指纹 | InRelease 摘要算法 | 公钥材料诊断 |
| --- | --- | --- | --- |
| trixie archive，主钥 `04B54C3CDCA79751B16BC6B5225629DF75B188BD` | `B8E5F13176D2A7A75220028078DBA3BC47EF2265` | SHA-256 | 五份 direct-key 自签、UID 自认证、subkey binding 均为 SHA-512；内嵌 cross-certification 亦为 SHA-512 |
| trixie stable release | `41587F7DB8C774BCCF131416762F67A0B2C39DE4` | SHA-256 | UID 自认证为 SHA-256；由主钥直接签名 |

上述两个角色均为必要条件。另观察到 bookworm archive 的 SHA-256 签名，但它不替代任何必要角色，也未在本批重新审阅其公钥自认证。GnuPG 使用完整公钥环验签并要求 cross-certification；状态含三个 `VALIDSIG` 和 `TRUST_UNDEFINED`，无过期 / 撤销 / 错签状态。必要角色的自认证输出均含 `sig:!`，完整 issuer 指纹、有效期、签名 class 和算法由诊断方法逐项核对。

公钥环复用[既有留存材料](../linux-builder-source-chain/release-verification.json)的 55,918 bytes，SHA-256 `506b815cbb32d9b6066b4a2aa524071e071761e7e7f68c3ac74f3061ba852017`。其原始 bytes 可从该 JSON 的 `keyring.base64` 恢复；本轮未下载新 key、查询 keyserver 或改动宿主 keyring。完整指纹与 Debian 官网的对应关系、公告读取失败及 bootstrap 边界见[前置审阅](musl-authentication-route-2026-09-10.md#可复用的本地材料与方法)。未检查该固定公钥环之外是否出现新撤销材料。

这条链认证的是 Debian 归档声明，不是 musl 上游现代签名。镜像 / GnuPG 来源尚未完整验收，公钥身份仍依赖已有镜像材料和已审阅 HTTPS 指纹页面；没有建立独立 Web of Trust，也没有将公钥自认证等同于现实身份认证。musl 上游原包及其公钥的 SHA-1 拒绝结论保持原样。

## 两类失败与修正

首次实际容器的两个 `--no-sig-cache --check-sigs` 子进程均以 `-6` 终止，stderr 为 `free(): double free detected in tcache 2`；其输出不完整。该容器的 InRelease 验签成功，但首版收集器只返回最后验签的退出码，因而整体退出 0。这个 0 不代表所有检查通过；本轮未据此下载 Sources。首次完整输出、方法摘要及[还原首版收集器的差异](musl-debian-auth-first-method.patch)均保留。

[GnuPG 上游问题索引](https://dev.gnupg.org/project/profile/159/)列有 `--no-sig-cache --check-sigs` 的 double-free 报告（T7547）；具体问题页本轮读取失败。本次现象与该报告相符，但没有调试或修复上游二进制，不声称已定位本机崩溃的全部根因。

第二次保留完整 keyring 用于 InRelease 验签与原始 packet 导出，另建临时 keyring，以 `--import-options self-sigs-only` 核对所需自认证 / subkey binding。此项只排除第三方认证检查；它不用于现实身份信任判断。[GnuPG 2.2.40 文档](https://raw.githubusercontent.com/gpg/gnupg/gnupg-2.2.40/doc/gpg.texi)说明该导入选项的作用，字段解释以同版本 [DETAILS](https://raw.githubusercontent.com/gpg/gnupg/gnupg-2.2.40/doc/DETAILS)为准。

第二次所有所选子命令均退出 0，自认证成功；方法同时核对完整导出 packet 的摘要算法与撤销 packet，并保留 `--no-sig-cache` / `--require-cross-certification`。没有关闭检查、放宽弱算法、改写原始公钥或增加第三次容器运行。修正后的收集器会将任一所选命令失败传播为非零退出；宿主诊断也逐项拒绝子命令失败。

随后主机首次链解析拒绝了版本名中含 `~` 的 `.dsc` / Debian patch 文件名。旧三包解析器的路径字母表较窄；本次在诊断中精确列举已选版本的四个文件名，再复用原包摘要解析，不修改历史 bookworm 规则。失败重现日志及首版方法摘要留在执行记录，[方法差异](musl-debian-chain-first-method.patch)与新负例测试一同保留。没有忽略异常行或将版本漂移作为 fallback。

## 下载与隔离执行

[下载日志](musl-debian-fetch-2026-09-10.json)保留两份材料各两次请求。首次均因沙箱不能连接代理而 curl 退出 7；获准在沙箱外重试相同 URL 后，均退出 0 / HTTP 200。InRelease 限 512 KiB / 60 秒，Sources 限 16 MiB / 120 秒，均固定 HTTPS / TLS ≥ 1.2；Sources 的实际 by-hash URL 由已验证 Release 的 SHA-256 段确定。

Docker 首次宿主调用因 socket 权限失败，未创建容器；重试后第一次实际容器使用首版方法，随后第二次实际容器使用最终方法。两次均采用：

```bash
docker --context orbstack run --rm \
  --name radishaxiom-musl-auth-0a66901-attempt-2 \
  --pull=never --platform=linux/arm64 --network=none --read-only \
  --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=64 \
  --memory=512m --cpus=1 --user=65534:65534 \
  --tmpfs=/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777 \
  --mount type=bind,src=/Users/luobo/Code/RadishAxiom/.tmp/musl-auth-chain-0a66901,dst=/inputs,readonly \
  --entrypoint=/usr/bin/timeout \
  sha256:a339861ae23e9abb272cea45dfafde21760d2ce6577a70f8a926153677902663 \
  120s /usr/bin/python3 /inputs/collect-musl-debian-auth.py
```

第一次实际运行仅名称为 `...attempt-1`，且缓存脚本为首版方法；stdout / stderr 对应执行记录中的 invocation 2。最终方法对应 invocation 3；invocation 1 为宿主 socket 失败，不能算第三次容器。`container ls --all` 按本批名称过滤结果为空，确认两容器均已自动删除；tmpfs / 临时 keyring 随之清除，宿主缓存留存复核。

## 复核入口与下一步

[主机链检查](inspect-musl-debian-auth.py)消费可信的本次 GnuPG 观察和固定原始字节，本身不是密码学验证器；[收集器](collect-musl-debian-auth.py)也不是产品来源验收器。完整 InRelease 保留在本目录；完整 Sources 为 `.tmp/musl-auth-chain-0a66901/Sources.xz`，原包仍在先前忽略缓存。Sources 比仓库单文件 10 MiB 上限多 42,044 bytes，首次仓库检查因此拒绝；本轮将该未跟踪副本移回任务缓存，保留相同字节与摘要，不放宽检查、不切片绕过上限，也不引入 LFS。Git 本身不能独立提供这份完整索引，复核须保留本地缓存或另行按固定 by-hash 地址取得。以下主机命令不重跑容器：

```bash
python3 docs/records/rust-linux-input-review/inspect-musl-debian-auth.py \
  .tmp/musl-auth-chain-0a66901 \
  --source .tmp/musl-source-review-c7f7f60/musl-1.2.5.tar.gz
python3 docs/records/rust-linux-input-review/check-musl-debian-auth.py
./scripts/check-repo.sh
git diff --check
```

缓存恢复时，将留存 InRelease 及另行保留或取得的完整 Sources 分别恢复为 `InRelease` / `Sources.xz`，由旧 Debian JSON 的 `keyring.base64` 恢复 `debian-archive-keyring.gpg`，并将本记录 execution JSON 的 `invocations[2].observation` 用 Python `json.dumps(..., sort_keys=True, indent=2) + '\n'` 恢复为 `offline-invocation-3.stdout`。先核对其原始 stdout 长度 / 摘要，再运行主机检查；缺少原包则只能复查索引链，不报告原包字节重算通过。任何新下载或容器复跑另行授权。

9 项合成检查通过，覆盖缺失 / 重复 / 弱算法签名、过期 / 撤销 / 错误指纹、崩溃子命令、错误自认证上下文、cross-certification 缺失以及版本 / 路径漂移。它们不执行密码学验签。实际链结果重算与留存 JSON 逐字节一致；原始日志（含 HTTP CRLF / 进度回车）、两次收集器输出、方法摘要及失败方法差异均已复核。仓库检查通过（1,071 文件），`git diff --check` 通过；不重跑 Rust / CI、patch、安装或构建。

后续信任审阅及项目所有者确认见下文，不能把本诊断自动写入正式 acceptance。其他六项源依赖、Rust 公钥策略、发布构建关联、宿主库、kernel 原始 tag 与最终链接仍分别待办。

## 仅限该原包的信任审阅（待确认）

审阅日期：2026-09-10；基线 `dev` / `70b7235`，开始时工作区干净、相对本地 `origin/dev` 领先 6 个提交，未查询远端。本节为方案审阅与本地材料复算，没有新网页读取、下载、容器运行、安装或正式信任策略变更。

历史说明：本节“推荐”“待确认”及表内“目前状态”均指提交 `bbbe083` 时的状态；随后确认范围以下节为准，不把当时的材料缺口改写成已验证事实。

### 推荐方案与精确范围

**推荐有条件采用 Debian 归档声明作为该固定原包的来源认证路线；先确认策略范围，再补公钥初始信任与验证工具证据，最后单独记录 acceptance。当前不接受现有诊断作为最终来源验收。**

拟采纳范围仅为上表 1,080,786 bytes / SHA-256 `a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4`，通过本记录固定 InRelease、Sources.xz、`musl / 1.2.5-3.1~deb13u1` 和 `pool/main/m/musl/musl_1.2.5.orig.tar.gz` 绑定。批准后允许形成的声明最多是：**在明确接受的 Debian 归档密钥身份及验证环境假设下，该签名快照将此字节串列为 musl 上游原包。**

候选条件如下，均不是本轮已生效的规则：

1. 固定前述 trixie archive 主钥、实际签名 subkey 和 stable release 主钥，两个角色都必须成立；保留 SHA-256 / SHA-384 / SHA-512 签名与自认证条件、cross-certification、时间及撤销检查。不同角色不代表已证明运维、身份渠道或失陷风险互相独立；bookworm 额外签名不替代它们。
2. 明确承担 Debian 归档维护者将正确原包纳入该快照的信任。归档链不认证 musl 作者的现代签名，不保证代码安全、补丁适用性或 Rust 发布二进制确实由该输入构建。musl 上游 SHA-1 拒绝继续单列。
3. 公钥初始身份推荐由项目所有者明确选择 Debian 官方 HTTPS 身份资料及 WebPKI 为起点，补齐可留存的完整指纹页面、角色 / 密钥公告和获取时间，并与现有原始 keyring 核对。当前只有既有审阅叙述和未成功取得的公告，尚不足以完成这一步。若要求独立于 Debian 网站 / WebPKI 的身份保证，应另选已有可信密钥的认证链或带外确认；本材料没有这样的起点。
4. 镜像 / 验证工具优先通过另一个已明确接受来源的最小验证环境复核相同原始输入；其取得路径不能只靠当前镜像输出背书。该环境的精确身份与来源必须另行提出，不能凭“换了工具”视为可信。复核仍须覆盖两角色、自认证、subkey binding、cross-certification 和失败传播，单独再验 InRelease 不足以替代全部条件。
5. 只处理固定历史快照。无 `Valid-Until`，不能认证其在验收日仍是最新发布；正式验收前需补截至指定核对时间的密钥状态依据，并明确未覆盖此后撤销。重算旧 observation 中的有效期不等于在新日期重新核验。未来更换原包、快照、必要 signer 或信任起点必须重新审阅，不能自动扩展到其他 musl 版本或全部 Debian 包。

本方案不批准 Debian patch、`.dsc` 维护者签名、Rust key policy、其他六项源依赖、整个镜像 / builder 或任何安装。新下载、复验执行和安装各自另行说明精确目标、影响、时限、清理方式并取得授权。确认本方案也不自动把 `acceptance = not-assessed` 改为通过。

### 公钥初始信任：已有依据与循环边界

| 层次 | 现有证据 | 尚不能推出 |
| --- | --- | --- |
| 公钥字节身份 | 从旧 [release-verification.json](../linux-builder-source-chain/release-verification.json) 恢复的公开 keyring 为 55,918 bytes，摘要与本批输入一致；两主钥完整指纹在[前置审阅](musl-authentication-route-2026-09-10.md#可复用的本地材料与方法)中与 Debian FTP 页面核对 | 包来自哪个可信发布过程、网页身份已由独立渠道认证 |
| 密钥内部绑定 | 本批自认证和 subkey binding 诊断通过，保留原始 packet 与强摘要算法；v4 指纹的 SHA-1 标识计算不等于接受 SHA-1 签名 | 自签 UID 是现实 Debian 归档维护者；`sig:!` 不建立 Web of Trust，`TRUST_UNDEFINED` 不作可信身份判定 |
| 初始身份资料 | 既有记录引用官方 HTTPS 完整指纹页面，也记载页面的信任提醒；公告当时返回 403 | 可复核的公告正文、公告签名的可信认证链、独立带外核对、最新撤销检查已齐备 |
| 发行版包关联 | 既有 bookworm 索引包含与库存相同版本的 `debian-archive-keyring` | 索引中的 `.deb` 已取得，或包内 keyring 与当前原始 bytes 已对照 |

公钥自签只说明内部绑定；两个 Debian 页面即使都补齐，也仍共享 Debian 发布方和 HTTPS 信任体系。推荐方案须把它们作为明确的初始信任假设及交叉核对材料，不能计为两条独立身份链。密钥公告即使含签名，也需说明公告 signer 的既有信任依据，不能按公告自带 key 再次自举。

同理，用镜像内 keyring 和 GnuPG 验证发行版索引，再用该索引中的同名包证明镜像 / keyring 一定可信，会形成循环。包内字节对照在外部信任起点确定后有价值，但不能凭空创建起点。固定 keyring 未含撤销 packet，也不证明外部没有更新的撤销材料。

### 镜像与 GnuPG：可以复用到哪一步

[历史镜像观察](../linux-6.18.49-source-review/observation.json)同时记录本地 image ID `sha256:a339861ae23e9abb272cea45dfafde21760d2ce6577a70f8a926153677902663` 和 RepoDigest 字符串 `rust@sha256:a339861ae23e9abb272cea45dfafde21760d2ce6577a70f8a926153677902663`。这仅是留存的身份观察；所读材料没有原始 OCI index / manifest / config / layer 字节及相互绑定，也没有可信发布者认证或镜像构建配方到该内容的关联。不能从 `rust@` 名称或两个相同摘要反推官方镜像来源已经验收。

[413 包库存](../linux-6.18.49-source-review/builder-inventory.json)记录 Debian bookworm / arm64，`gpg` 来自 source package `gnupg2`，包版本为 `2.2.40-1.1+deb12u2`；`debian-archive-keyring` 为 `2023.3+deb12u2`，`libgcrypt20` 为 `1.10.1-3+deb12u1`。旧库存 `/usr/bin/gpg` 摘要与本次执行摘要 `c3f988ab…17075` 相同，支持所观察程序的字节连续性。版本输出只显示 GnuPG `2.2.40` / libgcrypt `1.10.1`，不能据此省略 Debian 修订号或认为 `.deb` 到实际执行文件的绑定已完成。

本轮有界读取 Git 内已有 [bookworm Packages.xz](../linux-builder-source-chain/Packages.xz) / [Sources.xz](../linux-builder-source-chain/Sources.xz)，先按 [payload-chain.json](../linux-builder-source-chain/payload-chain.json) 的 `indexes` 重算长度 / SHA-256，再复用 `inspect-debian-source-chain.py` 的 `index_stanzas` 读取。以下版本各只有一个匹配条目，且 source 索引存在同版本 `gnupg2`、`debian-archive-keyring`、`libgcrypt20`；只是复用历史签名观察下的索引读取，没有新验签或取得包：

| binary package | 索引版本 / 架构 | `.deb` bytes / SHA-256 |
| --- | --- | --- |
| `gpg` | `2.2.40-1.1+deb12u2` / arm64 | 901,672 / `4ba017857a169efab487e4dd660dacdb4451223fc39a1c5c9046c446cd5702e6` |
| `debian-archive-keyring` | `2023.3+deb12u2` / all | 178,572 / `f699e2f88dca05212f2a452b58475f2993cb6993dfbafb1d0205a3291eb8b4b8` |
| `libgcrypt20` | `1.10.1-3+deb12u1` / arm64 | 620,056 / `140af58350c9b15bfa611000d9e0205528bbed2cba39271bf12bd36de2678f2e` |

这些是后续材料选择入口，不是下载清单的批准。`gpg` 条目还声明 `gpgconf`、`libassuan0`、`libbz2-1.0`、`libc6`、`libgpg-error0`、`libreadline8`、`libsqlite3-0`、`zlib1g` 依赖。包依赖声明不等于实际加载库闭包，仍缺实际 loader / 共享库身份与包内字节绑定。Python、收集器、timeout、宿主解析 / XZ / SHA-256 路径、Docker / OrbStack、宿主及时间来源也属于结果可信所依赖的环境；摘要和隔离参数只分别固定内容、限制副作用，不能证明环境输出正确。

若选择继续验收现有镜像，应补原始 OCI 绑定、发布来源、相关包 / 源码 / 许可证和实际执行闭包，或者由项目所有者明确接受其中仍属可信输入的部分；不必为这一个原包先宣称全部 413 包已验收。推荐优先使用来源明确的最小环境复核，原因是现有镜像 provenance 缺口较大且已发生 GnuPG double-free。第二次诊断成功只说明选定检查路径通过，不能推导旧二进制已修复或没有其他缺陷；更换环境也不自动解决首次崩溃根因。来源认证不等于必须从零重建所有工具，但任何采用发行版二进制的信任终点都须显式记录。

### 剩余证据与停止条件

| 缺口 | 建议闭合材料 / 判定 | 目前状态 |
| --- | --- | --- |
| 归档替代路线的授权 | 项目所有者确认上述固定原包、两角色、声明上限及不扩大范围 | 待确认；正式策略未变 |
| 公钥初始身份与时效 | 可留存的官方指纹 / 角色 / 公告原文、获取时间和摘要；明确 HTTPS / WebPKI 或另选带外信任；核对适用时间的撤销 / 过期信息 | 只有历史网页核对叙述与旧 keyring，公告缺失；不能声称最新状态 |
| keyring 的发行包关联 | 在选定信任起点下，认证精确 `.deb` 并比较其 keyring 与 55,918 bytes 原始材料；差异需解释，不自动替换 key | 索引版本 / 摘要可复用，包内对照未完成；这不替代上一项 |
| 验证环境来源与复核 | 明确选择现有镜像闭合或另一个可接受环境，固定工具 / 库 / 方法及可信宿主边界；复核全部必要条件，保存成功和失败原文 | 当前仅诊断 TCB；换环境、下载或运行均未授权 |
| 原始材料持久留存 | 保留固定 InRelease、完整 Sources、原包、公钥、观察及方法的可取回副本；恢复后重算摘要 | Git 内有 InRelease / keyring / 日志 / 方法；完整 trixie Sources 与原包仍依赖忽略缓存，未建立受审阅的持久副本 |
| 正式验收记录 | 策略确认且证据补齐后，单列适用输入、信任假设、核对时间、工具身份及剩余边界，沿现有验收流程评估 | `acceptance = not-assessed` 保持不变；本记录不是新 acceptance 格式 |

若项目所有者不接受 Debian 归档维护者或所提初始信任，应继续阻断，转回寻找同一字节的上游强摘要签名及可接受 key binding；现有材料不能保证该路线可取得。仅凭 HTTPS 下载摘要、放宽 SHA-1 或将旧镜像直接标为可信均不推荐作为本批捷径。

本轮主机重跑上节 `inspect-musl-debian-auth.py ... --source ...`，退出 0，stdout 与 Git 内链结果逐字节一致；keyring 解码长度 / 摘要相符，完整本地 trixie Sources 和原包参与重算。这是对旧 GnuPG 观察和现有字节的复算，没有重新进行密码学验签，也没有补足上述缺口。文档更新后运行仓库检查与 `git diff --check`；未重跑 Rust / CI、GnuPG、容器、patch、安装、构建或远程操作。

## 项目所有者确认与执行顺位

2026-09-10，提交 `bbbe083` 后，项目所有者对“仅限该固定原包的有条件信任方案”明确回复“确认”。**该方案的策略范围现已确认，证据门槛不豁免，来源 acceptance 仍为 `not-assessed`。** 本节承接上节五项条件，作为本输入的决策记录；不改变全局工具信任策略或公共验收格式。

已确认的信任包括 Debian 归档维护者对该固定原包的归档声明，以及以 Debian 官方 HTTPS 身份资料 / WebPKI 作为公钥初始身份起点。作用域固定为本记录的原包长度 / SHA-256、InRelease / Sources 字节与 trixie 两角色，不声称独立 Web of Trust 或上游现代签名通过。优先采用来源明确的最小验证环境复核；尚未选定或接受任何新增环境、镜像、工具或运行库。

| 决策核对情形 | 允许的结论 / 停止线 |
| --- | --- |
| 正例：同一原包、固定两角色及全部补证条件满足 | 可进入本输入的单独来源验收；策略确认本身不产生通过记录 |
| 负例：缺少角色、弱签名 / 自认证、错误指纹、过期或撤销 | 拒绝该链，不以额外 bookworm 签名或宽松参数替代 |
| 反例：旧镜像 GnuPG 成功且包名 / 版本相同，但工具或身份来源未闭合 | 仍是诊断，不能自证环境可信或批准安装 |
| 兼容边界：其他版本、快照、signer、Rust 签名或整个 builder | 不继承本决定；musl SHA-1 拒绝、旧诊断 JSON、冻结 acceptance 契约保持原样 |

此表是文档层的条件审阅，不是新增密码学测试结果。公钥公告 / 密钥状态、keyring 包内对照、验证环境来源和持久留存仍按上节逐项补齐。现有 [Toolchain Payload Acceptance v0.1](../../../contracts/toolchain-payload-acceptance-v0.1/README.md)只覆盖其冻结的 Go / Rust 对象；本轮不把 musl 填入该生成链，也不执行生成器改写历史记录。

### 身份资料与 keyring 包：原授权范围

执行状态：项目所有者随后明确授权以下两个下载及本地核对，已完成[实际补证](musl-trust-inputs-2026-09-10.md)。页面两主指纹一致，精确 `.deb` 摘要匹配，包内 keyring 与旧诊断输入逐字节相同；公告和公钥链接只解析未访问。以下保留执行前范围，不视为后续下载授权。

本批只准备以下两个精确 HTTPS 目标；原始内容尚未取得，不预设成功。沿用已有 curl 下载和本地摘要复核方式，不增加自动取 key 或安装入口：

| 目标 | 用途 | 单次上限 / 固定结果要求 |
| --- | --- | --- |
| `https://ftp-master.debian.org/keys.html` | 留存完整指纹、角色说明、官方公告与公钥链接，核对前述两个主指纹 | 1 MiB / 60 秒；保留获取时间、URL、HTTP 状态、原文长度 / SHA-256；网页当前内容尚未知 |
| `https://deb.debian.org/debian/pool/main/d/debian-archive-keyring/debian-archive-keyring_2023.3+deb12u2_all.deb` | 取得与旧库存及本地 bookworm 索引一致的公开 keyring 包，供后续包内字节对照 | 512 KiB / 60 秒；必须为 178,572 bytes / SHA-256 `f699e2f88dca05212f2a452b58475f2993cb6993dfbafb1d0205a3291eb8b4b8` |

执行参数固定 HTTPS / TLS ≥ 1.2、禁止重定向跟随、不使用 `--insecure`、不自动重试。每个目标最多两次：仅连接或传输失败允许对同一 URL 重试一次；3xx、403、404、超限、指纹或摘要不符时保留失败并停止该项，不换域名、版本或包。每次请求分别保存 stdout / stderr、HTTP 状态、响应正文、长度 / 摘要与退出码；不覆盖首轮失败，也不将非 200 响应当成功。网页不自动抓取其链接。

任务目录为 `.tmp/musl-trust-bbbe083-20260910/`，执行时独占创建；若已存在则先检查归属，不覆盖。最多四次请求，响应正文累计上限 3 MiB，预计 2–5 分钟含日志和本地复核。副作用只有公开 HTTPS 请求与该目录内的新文件；不安装 `.deb`、不执行 maintainer scripts、不导入宿主 keyring、不运行容器，不重新下载 InRelease、完整 Sources 或 musl 原包。下载包的摘要匹配只能报告“与旧诊断索引一致”，仍不能为其背后的工具来源自证。

成功后先读取网页并固定 trixie 公告、公开 key / 撤销资料的精确 URL；目前所读材料没有这些公告的可复用完整地址，不能用旧 bookworm 公告替代。本批不预授权沿链接下载，也不宣称网页没有撤销提示就证明未撤销。包内对照须先审阅有界 ar / tar 读取方法，保留原始 `.deb`，禁止借机执行包内程序。

无后台进程需要清理；日志与输入先保留复核，不删除原缓存。若需要清理，本批仅删除经核对的任务目录内新建文件，不作递归宽泛删除；没有产品或系统状态需要回滚。公开资料的来源及许可 / 归属另行记录，未审阅的网页不整页复制入 Git。

后续顺位：身份材料固定后，另列最小验证环境的精确工具 / 库 / 来源和运行范围；获授权取得与复核后再评估验收。完整 Sources 与原包继续只读保留，另明确持久存储位置、保留责任和恢复摘要检查；本次不选择远程存储、不上传、不分片绕过仓库大小限制。

方案确认轮只更新决策、状态和待授权范围；旧原始证据与检查代码未变。当轮文档 / 仓库检查和现有 9 项 Debian 诊断合成检查通过，未重新验签、下载、运行容器、安装、构建或操作远端；合成检查不验证新信任假设的现实真实性。随后实际下载与本地核对以[执行记录](musl-trust-inputs-2026-09-10.md)为准；来源 acceptance 仍为 `not-assessed`。
