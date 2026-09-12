# musl 验证工具：固定 arm64 包清单

日期：2026-09-12；基线 `dev` / `fa8d010`。用途：供来源审阅者复核索引获取、包级依赖与源码关联，并界定下一次原包内容审阅。不包含工具信任 acceptance、安装可行性、ELF 闭包或实际验签结论。

项目所有者要求“提交工作区更改，继续推进”，本批先提交[前批来源审阅](musl-verifier-environment-2026-09-12.md)的五个文件，随后按前轮说明的单一索引范围执行。该授权不扩展到 `.deb` 下载、工具信任终点、安装或容器执行。

后续：本记录随 `03d23b6` 提交后，项目所有者授权继续，17 包已取得并完成[只读内容盘点](musl-verifier-content-2026-09-12.md)。下文包下载“待授权”“尚未取得”及工作区状态保留本记录原批次时点；当前事实见后续记录。

## 实际获取与保留

两次请求均使用同一固定 URL：

```text
https://deb.debian.org/debian/dists/trixie/main/binary-arm64/by-hash/SHA256/753da751bbc7a679f48bd1b623ffd4479cb6861c426118284c76eb82909e4908
```

首轮在沙箱中退出 7 / HTTP 000，连接本机代理失败，正文 0 bytes；按方案在沙箱外重试一次，退出 0 / HTTP 200。成功正文 **9,607,412 bytes** / SHA-256 `753da751bbc7a679f48bd1b623ffd4479cb6861c426118284c76eb82909e4908`，与固定 InRelease 的 SHA256 段一致。成功获取时间为 `2026-09-12 11:36:37–11:36:53 UTC`；完整两次观察及原始输出身份见[获取记录](musl-verifier-index-fetch-2026-09-12.json)。

正文位于 `.tmp/musl-verifier-d04b225-20260912/packages-attempt-2.xz`，失败正文、日志和两份原始观察留在同一目录，未覆盖或清理。共两个请求、累计正文 9,607,412 bytes；未重下 InRelease / Sources / musl 原包、公钥或其他索引。记录仅含公开材料与本机代理连接错误。

前批带上下文的 fetch 差异在暂存后检查出现空白上下文行的尾随空格提示；当时组合命令的最终退出码来自后续 `git diff --stat`，不能把它记为暂存检查无告警。本批将同一[差异文件](musl-verifier-index-fetch-method.patch)改为零上下文，并实际重建验证：执行脚本字节仍为 SHA-256 `37225785634c2108d46b8522cc83fc23cddccb10cad70ac7d7ea4168257ddbfe`，原 fetch 方法未修改。不 amend 已有提交；这是补丁表示修正，不是下载方法变化。

HTTPS 下载、摘要一致与旧签名观察的引用不构成新的密码学验签或工具来源自举。完整索引仍在忽略缓存，尚无经审阅的持久副本；提取的包清单不替代完整索引。沿前批持久材料待办处理，不借本次下载宣布该项闭合。

## 精确包及源码关联

[盘点方法](inspect-musl-verifier-packages.py)复用固定 Sources / InRelease 绑定与有界 XZ / Deb822 reader，完整读取 Packages 后从 `gpg` 遍历 Depends / Pre-Depends。实际 **17 包、35 条边**，所有明确版本约束成立。14 个唯一源码身份均在同一完整 Sources 中找到，含新增的 `gcc-14=14.2.0-19` 关联；前批 13 个候选源码家族的历史输出不改写。

| 包 | binary 版本 | 架构 | `.deb` bytes |
| --- | --- | --- | --- |
| `gpg` | `2.4.7-21+deb13u1+b4` | arm64 | 578,896 |
| `gpgconf` | `2.4.7-21+deb13u1+b4` | arm64 | 121,684 |
| `libassuan9` | `3.0.2-2` | arm64 | 59,112 |
| `libbz2-1.0` | `1.0.8-6` | arm64 | 37,772 |
| `libc6` | `2.41-12+deb13u3` | arm64 | 2,489,480 |
| `libgcc-s1` | `14.2.0-19` | arm64 | 54,104 |
| `libgcrypt20` | `1.11.0-7+deb13u1` | arm64 | 741,128 |
| `libgpg-error0` | `1.51-4` | arm64 | 78,544 |
| `libksba8` | `1.6.7-2+b1` | arm64 | 125,004 |
| `libnpth0t64` | `1.8-3` | arm64 | 22,900 |
| `libreadline8t64` | `8.2-6` | arm64 | 159,264 |
| `libsqlite3-0` | `3.46.1-7+deb13u1` | arm64 | 853,772 |
| `libtinfo6` | `6.5+20250216-2` | arm64 | 341,360 |
| `zlib1g` | `1:1.3.dfsg+really1.3.1-1+b1` | arm64 | 85,116 |
| `gcc-14-base` | `14.2.0-19` | arm64 | 49,444 |
| `init-system-helpers` | `1.69~deb13u1` | all | 39,360 |
| `readline-common` | `8.2-6` | all | 69,360 |

总量 **5,906,300 bytes**。精确 URL / Filename / SHA-256、原始关系字段、源版本及源码文件摘要字段见[完整清单](musl-verifier-packages-2026-09-12.json)。这些是索引声明，`.deb` 尚未取得；不能从包名推导 loader 路径、SONAME 或许可正文已检查。

按 [Debian Control 字段规则](https://www.debian.org/doc/debian-policy/ch-controlfields.html#s-f-version)区分 epoch、上游版本与 Debian 修订，按数字段及 `~` 等顺序核对版本。Source 有显式版本时采用该版本，否则沿用 binary Version；Source 字段缺省时名称也沿用 binary Package。因此 `gpg/gpgconf` 对应 `gnupg2=2.4.7-21+deb13u1`，`libksba8` 对应 `libksba=1.6.7-2`，`zlib1g` 保留 epoch 与不同的源码 / binary 修订。

脚本仅支持本次遇到的单一包依赖项、无版本 / `=` / `>=` 与 arm64 / all；对 alternatives、架构限定、其他运算符或缺失 / 多候选项明确失败，不默默截断成首个包名。支持边界参照 [Debian 依赖关系语法](https://www.debian.org/doc/debian-policy/ch-relationships.html#syntax-of-relationship-fields)，本批没有实现完整 apt 求解器。

## 结论上限与后续材料

只覆盖显式 Depends / Pre-Depends，不递归 Recommends，不加入完整 `gnupg` 套件；保留 Conflicts / Breaks / Replaces / Provides 等原文，但未执行安装事务求解。`libc6` 与 `libgcc-s1` 的依赖环已遍历，不能据此推导安装可行。

`gcc-14-base`、`init-system-helpers`、`readline-common` 仍列入原包审阅集合，以检查数据、许可和安装辅助内容；是否含实际运行必需内容，由包内观察决定。未覆盖隐含 Essential 环境、maintainer scripts 需求、实际 `DT_NEEDED`、NSS / `dlopen`、子进程、符号版本或 loader 解析。当前 `runtime_closure_assessed = false`、`installability_assessed = false`。

下一步取得原始 `.deb`，核对 control 的身份与关系字段，读取 data 清单、copyright、许可引用、ELF 和链接；不向 rootfs 或系统提取可执行文件，不运行包内脚本或工具。既有 keyring 包读取方法只支持其很小的无链接归档，不能假定支持 libc6 等包；内容检查前须按实际压缩成员和链接类型审阅有界 reader，不支持时保留失败并停止。各包的来源 / 许可分别处理，不把所有包重标为 GnuPG 的许可证。

## 下一次下载范围（待授权）

精确目标为清单 JSON `packages` 数组中的 **17 个 Debian 官方 HTTPS `.deb` URL**，逐项绑定同一 Filename / 长度 / SHA-256，不请求包内引用的其他 URL。下载仅作为审阅输入，不接受工具信任终点、不安装、不运行容器或程序、不构建 rootfs、不改 lockfile / PATH / keyring。

已复用原 [fetch 方法](fetch-musl-trust-inputs.py)准备[零上下文差异](musl-verifier-packages-fetch-method.patch)。任务脚本为 `.tmp/musl-verifier-d04b225-20260912/fetch-musl-verifier-packages.py`，SHA-256 `fa17118d61750dcefa91977e5fee960cc4aeb41c9075c68c605aa9b1beea5cb8`。仅改变固定目标表、单包上限和精确成功条件；请求上限等于索引声明长度，超限即拒绝。`libbz2-1.0` 的请求标识为 `libbz2-1_0`，避免原方法的路径后缀处理截断含点标识；不改变 URL 或包身份。

授权后使用 `python3 .tmp/musl-verifier-d04b225-20260912/fetch-musl-verifier-packages.py <请求标识> 1`，按清单逐项执行；标识仅可来自固定表。每项最多两次，第二次仅用于符合原规则的连接 / 传输失败；HTTP 3xx / 403 / 404、摘要或长度不符及超限时停止整批，不换镜像 / 版本 / 包，不重下成功项。

HTTPS / TLS ≥ 1.2、不跟随重定向；每请求 60 秒、父进程 65 秒。最多 34 次请求，累计正文上限 **11,812,600 bytes**；正常下载及静态盘点预计 5–10 分钟，若所有请求均走到父进程上限，请求阶段约 37 分钟。逐项保留时间、stdout / stderr、HTTP、退出码、内容 / 方法摘要；父进程中断的不完整记录单列失败，不能作为可重试成功状态。

仅写任务目录，无后台进程或系统回滚需求。原包和观察先保留；后续清理仅处理确认归属的本批文件，不递归删除目录。工具信任决定、宿主盘点、组装、离线验签与产品运行分别验收和授权。

## 验证与交接

```bash
python3 docs/records/rust-linux-input-review/inspect-musl-verifier-packages.py \
  .tmp/musl-verifier-d04b225-20260912/packages-attempt-2.xz \
  .tmp/musl-auth-chain-0a66901/Sources.xz
python3 docs/records/rust-linux-input-review/check-musl-verifier-packages.py
./scripts/check-repo.sh
git diff --check
```

新盘点首次执行与重跑成功，输出和留存 JSON 逐字节一致。新增 7 项合成检查通过，覆盖版本顺序、依赖环、缺失 / 重复 / 错误架构、约束不满足、不支持语法、source 版本及错误来源 / 路径 / 摘要字段；既有 `scripts/check-debian-source-chain.py` 的 10 项检查也通过。这些检查不访问网络、不执行 apt 或密码学验签。

两次下载的原始正文 / stdout / stderr 长度及摘要与获取记录相符。两份零上下文差异均实际重建成功，所得方法与任务目录脚本逐字节一致；下一批脚本经 Python 语法与 AST 常量核对，17 个 URL、上限、包名和摘要均与清单一致，未执行该脚本。仓库检查通过（1,094 文件），`git diff --check` 通过。

前批已提交为 `fa8d010`，相对本地 `origin/dev` 领先 1 个提交，未推送；后续盘点及补丁表示修正共 9 个文件尚未暂存或提交。任务缓存与复核输出保留，无后台进程。未取得 `.deb`、安装、运行容器、重新验签或运行 Rust / CI。musl 来源仍为 `not-assessed`，工具信任终点未接受，产品与公共格式停止线未改变。
