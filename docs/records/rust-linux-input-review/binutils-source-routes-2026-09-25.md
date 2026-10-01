# Binutils 其他取钥路径与 Debian 原包候选核对

用途：记录公钥服务器观察、精确 Debian 候选与配方原包的实际差异，为后续来源决策排除不成立的路线。本记录不是新来源接受决定、公共 Evidence 或安装授权。

## 本批范围

项目所有者要求提交并继续推进。此前 GNU 钥环刷新切片已提交为 `b1de5c8`；提交前仓库 1,208 文件检查和差异检查通过，提交后工作区干净。随后完成两项完整指纹取钥；其结果未补强自认证，再单独说明、获执行权限确认并取得一个固定 Debian `.xz` 候选，用于比较。三个请求均由未修改的 [fetch 方法](fetch-mpc-mpfr-inputs.py)执行，没有安装、导入钥环或运行 GnuPG。

## 公钥服务器结果

[Ubuntu 公钥服务器](https://keyserver.ubuntu.com/)说明提供公钥分发；[keys.openpgp.org API](https://keys.openpgp.org/about/api/)支持完整指纹 GET。本次只查询 `3A24BC1E8FB409FA9F14371813FCEF89DD9E3C4F`，未使用邮箱搜索、上传、验证邮件或任何写入接口。分发服务并不自动成为发布者身份的可信起点。

两个精确目标各请求一次，每份 256 KiB 上限、60 秒 / 父进程 65 秒，不重定向、不重试。2026-09-25 **15:37:13–15:37:16（Asia/Shanghai）**实际结果：

| URL | 结果 | SHA-256 |
| --- | --- | --- |
| `https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x3A24BC1E8FB409FA9F14371813FCEF89DD9E3C4F` | curl 0 / HTTP 200，5,726 bytes | `2ce8ad1dd1bf31ea10f213e3bf88d23994184124c68691f8a69c6010c3e0aab7` |
| `https://keys.openpgp.org/vks/v1/by-fingerprint/3A24BC1E8FB409FA9F14371813FCEF89DD9E3C4F` | curl 0 / HTTP **404**，69 bytes | `1bcb3d1df4237a58c2ad59e2adde0b3615b70a8b4981779021e97fdcf5f4237b` |

Ubuntu 返回一个主钥块、11 个包。主钥 / 子钥包体和两份声明自签的完整包体与此前 GNU 公告附件相同；两份自签仍为 SHA-1。新增六份 UID 第三方认证声明（五份 SHA-256、一份 SHA-512），这些不是该主钥的强摘要自认证，也未经密码学或身份链验证。本次不接受这些第三方认证，不把多份强摘要字段误写成自认证已补齐。404 原文也完整保留，不能据此断言其他服务或外部材料不存在更新。

## Debian 候选：认证链与整包等价分别判断

本次首先完整重算 [六项来源盘点](musl-remaining-sources-2026-09-16.json)，输出逐字节一致，锁定唯一 `binutils=2.44-3` 条目。固定 InRelease 经 Sources 指向 `pool/main/b/binutils/binutils_2.44.orig.tar.xz`，27,504,768 bytes / SHA-256 `c41a0272424f41bb01bf828e7ffef1b2d59d1788064fd6b5f1d971717e9320b8`。

随后对 `https://deb.debian.org/debian/pool/main/b/binutils/binutils_2.44.orig.tar.xz` 单独说明范围并获执行权限确认：一次 HTTPS 请求，上限等于上述长度，60 秒 / 父进程 65 秒，无重试 / 重定向。实际 **15:45:27–15:45:34** curl 0 / HTTP 200；原包长度和 SHA-256 与固定索引一致。没有替换配方中的 `.gz`，没有更换版本或执行归档内容。

调用现有 `collect_success()`，重算 [九项真实验签 / 66 条命令导出](musl-verification-success-2026-09-16.json)逐字节一致；固定 InRelease、完整 Sources 及两必要角色的原始证据仍沿 [MPC 审阅中的证据链](mpc-source-acceptance-review-2026-09-25.md#debian-路线的实际证据)定位。这里复用的是完整索引的既有执行观察，不继承 MPC 的来源接受决定，也没有重新运行密码学。工具 / 宿主、Debian 身份与材料时点假设没有消失。

[比较方法](compare-binutils-streams.py)在每输入 64 MiB、展开 512 MiB、XZ 解码器内存 256 MiB 范围内，对完整 gzip / XZ 流逐块直接比较，并同时计算各自展开长度与 SHA-256。即使发现差异，也继续消费和校验完整输入；截断、CRC 错误、拼接流、尾随数据和超限拒绝。没有将文件解压到目录，也没有重新压缩生成替代原包。

| 对象 | bytes | SHA-256 |
| --- | ---: | --- |
| 配方固定 `.gz` | 51,342,242 | `0cdd76777a0dfd3dd3a63f215f030208ddb91c2361d2bcc02acec0f1c16b6a2e` |
| `.gz` 展开 tar | 317,317,120 | `9628a14839e0f16a0aa63bdf0d53b1b28d67b54bbab3e81f6e615be552a18ed1` |
| Debian `.xz` 展开 tar | 316,579,840 | `65731125a1bf2ef7ebdd8f396baa0eb666d4cf5cd7c14ca78d4904dbfc604c29` |

展开流首个差异位于零基偏移 **14**。为了定位差异，另对完整 `.xz` 做有界逻辑成员盘点，并与重新盘点的固定 `.gz` 对照，拒绝越界 / 重复路径、链接、特殊 / 稀疏成员、带数据目录、文件祖先冲突及非零 tar 尾部。比较范围明确限于路径、文件类型、长度、SHA-256、模式、uid / gid；不声称物理头、顺序、mtime 或目录元数据等价。

- `.gz` 有 28,449 个普通文件，`.xz` 有 28,447 个，后者另有 314 个显式目录。
- 仅 `.gz` 有 `bfd/doc/bfd.info` 和 `zlib/contrib/dotzlib/DotZLib.chm`（均相对 `binutils-2.44/`）。
- 三个共同文件的长度 / 内容摘要不同：`bfd/doc/bfd.texi`、`bfd/doc/bfdint.texi`、`ld/ldint.texi`。
- 其余 28,444 个共同文件的长度 / 内容摘要相同；所有 28,447 个共同文件的 uid / gid 均由 `.gz` 的 `(0, 0)` 变为 `.xz` 的 `(1000, 1000)`，模式未观察到差异。

这些结果明确排除“只是压缩格式不同”及“整个解压内容相同”的假设。**该 Debian 候选不能为当前 `.gz` 整包背书。** 没有忽略缺失文件、剔除文档或接受部分目录作为完整来源终点；也没有改变公共格式、配方、许可证范围或既有信任规则。

## 重放与留存

[统一诊断入口](inspect-binutils-source-routes.py)核对三项请求 / 日志 / 计划、Ubuntu 公钥、旧材料、完整索引、历史执行记录、两种归档及成员差异，生成[本批导出](binutils-source-routes-2026-09-25.json)。所有字段都是诊断观察；`source_acceptance` 保持 `not-assessed`，第三方认证接受为 `false`。

```bash
python3 docs/records/rust-linux-input-review/inspect-binutils-source-routes.py
python3 docs/records/rust-linux-input-review/check-binutils-streams.py
python3 docs/records/rust-linux-input-review/check-binutils-content.py
python3 docs/records/rust-linux-input-review/check-mpc-mpfr-key-inputs.py
./scripts/check-repo.sh
git diff --check
```

新增流 / 成员比较 9 项，既有内容边界 13 项、公钥解析 9 项，共 **31 项通过**。没有重跑 Rust / CI、GnuPG 或产品构建。

`./scripts/check-repo.sh` 通过（1,215 个文件），`git diff --check` 通过。七个新增文件的 UTF-8 / 换行与 `0644` 权限检查通过，34 个留存路径的长度 / SHA-256 无漂移。

[留存清单](binutils-source-routes-retention-manifest-2026-09-25.json)涵盖 **34 个文件、27,670,798 bytes**。存储为 `artifacts/source-inputs/binutils-source-routes-b1de5c8-20260925/`，布局为 `files/<原项目相对路径>`；`.xz` 超过旧小对象工具的 16 MiB 上限，因此沿此前大原包留存惯例，使用未修改的 `read_regular(path, limit)` / `write_new()` 原语，按清单精确上限复制并读回。没有拆包或修改旧 CAS profile。

随后从留存目录恢复至 `.tmp/binutils-source-routes-restore-20260925/`，逐文件长度 / SHA-256 与原字节一致。调用 `inspect()`，将两个目录参数指向恢复的 `.tmp/binutils-keyservers-b1de5c8-20260925` 和 `.tmp/binutils-content-chain-b1de5c8-20260925`；配方 gzip 继续从此前留存目录读取，完整导出逐字节一致，详见[恢复记录](binutils-source-routes-retention-2026-09-25.json)。旧 Debian 执行 / Sources 对象库及其仓库方法仍是依赖，不声称本增量是完整或异盘备份。

## 收口与后续

本批已完成两条其他取钥路线及一个精确归档候选的审阅。Binutils 上游认证与整包来源接受仍未通过，继续保留安装 / 构建停止线；不重复获取已确认的旧钥，不以弱摘要兼容或部分文件相同绕过缺口。

后续将 GCC 9.4.0 的独立原包 / 强摘要 / 签名材料核对列为近期工作，再处理 GMP / headers。推进其他依赖不表示 Binutils 已验收，也不允许完整 source lock 或安装越过它。若要改变 Binutils 的身份起点、验收对象、信任规则或配方，须另行形成精确方案并由项目所有者确认；本批没有提出或批准这类变更。

本批新方法、导出和文档未提交；`dev` 相对未刷新的本地 `origin/dev` ahead 6，未推送。没有新增长期进程；三个原始请求及临时比较结果、留存 / 恢复目录均保留。
