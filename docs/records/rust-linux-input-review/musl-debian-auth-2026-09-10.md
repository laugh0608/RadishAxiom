# musl 原包的 Debian 强摘要链诊断

日期：2026-09-10；基线 `0a66901`。按项目所有者对[精确范围](musl-authentication-route-2026-09-10.md)的授权，取得 trixie InRelease 和完整 Sources 索引，在固定镜像内完成离线诊断。本记录不接受新的产品信任策略，不改写 musl 上游签名拒绝，不安装、编译或执行源码。

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

下一步先审阅：是否仅对上述固定原包接受 Debian 归档声明及现有公钥 bootstrap 假设，以及镜像 / 验证工具来源如何闭合。通过与否必须显式记录，不能把本诊断自动写入正式 acceptance。其他六项源依赖、Rust 公钥策略、发布构建关联、宿主库、kernel 原始 tag 与最终链接仍分别待办。
