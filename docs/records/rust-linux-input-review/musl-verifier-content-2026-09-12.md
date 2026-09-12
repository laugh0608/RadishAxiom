# musl 验证工具原包内容盘点

日期：2026-09-12；基线 `dev` / `03d23b6`，启动时工作区干净，相对本地 `origin/dev` 领先 2 个提交，未查询远端。用途：供来源与运行环境审阅者复核原始包、文件身份、ELF 声明与许可材料；不包含工具来源 acceptance、可运行 rootfs、符号兼容验收或密码学验签。

## 已完成范围

项目所有者在提交前批更改后要求“推进吧”，本批按[已列明的 17 包范围](musl-verifier-packages-2026-09-12.md#下一次下载范围待授权)执行下载与只读内容检查，没有扩大到安装、容器或工具执行。

17 包全部取得，累计正文 **5,906,300 bytes**，每项长度 / SHA-256 与固定清单一致。`gcc-14-base` 首轮因沙箱无法连接本机代理退出 7 / HTTP 000、正文为 0；获准在沙箱外重试后成功，其余 16 包各一次成功。共 18 次请求、17 次 HTTP 200；没有换 URL、重下成功项或取得清单外内容。请求区间为 `2026-09-12 11:50:39–11:53:24 UTC`；原始输出、实际时间、HTTP、退出码、方法与内容摘要见[获取记录](musl-verifier-package-fetch-2026-09-12.json)。

输入留在 `.tmp/musl-verifier-d04b225-20260912/`，文件为 `<请求标识>-attempt-<次数>.deb`；只有 `gcc-14-base` 使用第 2 次成功正文，`libbz2-1.0` 使用已声明的标识 `libbz2-1_0`。输入与失败日志均保留。下载方法 SHA-256 仍为 `fa17118d61750dcefa91977e5fee960cc4aeb41c9075c68c605aa9b1beea5cb8`，没有修改既有 fetch 方法或历史清单。

## 内容与检查方法

[只读方法](inspect-musl-verifier-content.py)先固定候选清单 SHA-256，再逐包核对原始字节，复用已有严格 ar reader 和 ELF 动态段观察。所有包均为 `debian-binary=2.0`、`control.tar.xz`、`data.tar.xz` 三成员。XZ / tar 只在内存中展开，不调用 tar 提取、dpkg、apt、ldd、loader 或包内程序。

新 tar 读取限定每 control 4 MiB、每 data 64 MiB、累计展开 256 MiB、单文件 16 MiB、每归档 10,000 成员、路径 / 链接文本 1,024 bytes、XZ decoder 128 MiB；拒绝截断 / 拼接 XZ、非零尾部、PAX、重复路径、越界链接、特殊文件、非 root owner 和非目录祖先。它是本批逻辑成员诊断，不替代产品严格 USTAR 契约。

共盘点 **583 个 payload 成员、290 个 ELF、15 个链接**，control 与 data 展开 tar 累计 **33,157,120 bytes**。control 的包名、版本、架构、source 与已记录关系字段全部匹配固定索引。payload 未见 setuid / setgid 位；15 个链接均在候选文件树内找到目标，无循环或向根外逃逸。跨包重复路径只允许元数据相同的目录，不覆盖文件。链接解析不访问宿主文件系统。

[完整库存](musl-verifier-content-2026-09-12.json.gz)为固定 `mtime=0` 的 gzip；[摘要](musl-verifier-content-summary-2026-09-12.json)绑定压缩与展开 JSON 长度 / SHA-256、方法、获取记录、各包 copyright 和根工具静态候选。原始 `.deb` 仍是文件内容的复现输入；库存摘要不替代原包持久留存。详细 copyright 和安装脚本文本只用于本地阅读，可经 `--include-text` 从同一输入重新得到，没有将上游全文或可执行文件复制进 Git。

## 根工具与静态依赖候选

| 对象 | 包内路径 | bytes / SHA-256 |
| --- | --- | --- |
| GnuPG | `usr/bin/gpg` | 1,266,832 / `8abfa53f25b7e338fcef742ac0f900bd87dbdcd9c0d0cb2c7c89accdd1299192` |
| 配置工具 | `usr/bin/gpgconf` | 204,184 / `cf92e711c3bb7ebdb57dcc627a740da6c77348fa12257e2c842c4059bbd13ae4` |
| loader 本体 | `usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1` | 201,344 / `1d8b77f28b7cec0329dca107a28fb0a850193b1dcce59be68fa0b06b514548cc` |

包版本仍为 `gpg/gpgconf=2.4.7-21+deb13u1+b4`，这是 control / 索引身份，本轮未运行 `--version`。ELF 均为 AArch64；两个根工具没有 RPATH / RUNPATH。

以 `gpg`、`gpgconf` 为根，只对 `DT_NEEDED` 在 `usr/lib/aarch64-linux-gnu/` 的同名路径作候选查找并沿实际包内链接解析，递归得到 **14 个常规文件 / 8,064,784 bytes**：两个根工具、loader，以及 libassuan、libbz2、libc、libgcrypt、libgpg-error、libm、libnpth、libreadline、libsqlite3、libtinfo、libz。完整文件路径、包归属、长度 / 摘要见摘要 JSON 的 `root_static_candidates`；该图内没有未找到的 `DT_NEEDED` 候选。

这不是 loader 的实际选择结果，也不是最小运行环境证明：

- 两个根工具的 interpreter 都是 **`/lib/ld-linux-aarch64.so.1`**。17 包树中没有根级 `lib`；虽然包内有 `usr/lib/ld-linux-aarch64.so.1 → aarch64-linux-gnu/ld-linux-aarch64.so.1`，仍不能经原 interpreter 路径找到本体。后续须在生成布局中明确根级链接及来源，或审阅显式 loader 调用与所有子进程路径；本批没有创建任何链接或 rootfs。
- 包级依赖包含 `libksba8` / `libgcc-s1` 等，不等于根工具的静态 `DT_NEEDED` 一定使用它们；同样，未进入这 14 个文件也不能证明实际运行永不需要它们。`dlopen`、NSS、locale、配置、数据和子进程依赖仍待核对。
- 全部 ELF 扫描还包含 glibc gconv 模块。六个 `libCNS.so` / `libGB.so` / `libISOIR165.so` / `libJIS.so` / `libJISX0213.so` / `libKSC.so` 名字不在本次固定主库目录内；它们实际位于 gconv 子目录，相关模块的 RUNPATH 为 `$ORIGIN`。此结果只是固定目录候选未命中，不能写成六个外部包缺失，也未实现通用 RPATH loader 模拟。
- 尚未解析 GNU symbol version 的需求 / 定义或验证符号解析；现有 ELF helper 的字段观察不证明装载兼容。宿主 Docker / OrbStack / Linux kernel 的精确运行身份也未补齐。

因此 `runtime_closure_assessed = false`、`symbol_versions_inspected = false`，不能执行“包齐了就运行”的隐式升级。

## 许可材料与安装副作用观察

17 包各自的 copyright 均已在候选文件树中定位，并记录最终路径、包归属和摘要。`libgcc-s1` 的文档目录链接到 `gcc-14-base`，不能漏留后者的版权说明。机器提取的 `License:` 行只作导航：它可能混合源码、构建脚本、文档和例外；没有这种字段也不等于没有许可证。

以下只转述本批原包内的主要声明，不作新分发许可或最终文件级归属判定：

| 材料 | 已读声明及作用域提醒 |
| --- | --- |
| gpg / gpgconf | GnuPG 默认 `Files: *` 为 GPL-3+；另列多种组件条款 |
| libc6、libassuan9、libgpg-error0、libnpth0t64 | 默认源码声明 LGPL-2.1+，详细例外仍随各自 copyright 保留 |
| libgcrypt20 | 文本区分 library 的 LGPLv2.1+ 与 manual / tools 的 GPLv2+ |
| libksba8 | 正文对 library / headers 声明 LGPLv3+ / GPLv2+ 双路线；不能只读取后部某条 `License:` 就概括整个包 |
| libreadline8t64 / readline-common | 默认源码声明 GPL-3+，另列文档 / 示例条款 |
| libbz2-1.0、libtinfo6、zlib1g | 分别保留 BSD-variant、MIT/X11、Zlib 的默认声明及例外 |
| libsqlite3-0 | 区分 SQLite 默认 public-domain 与 Debian 包装文件的 GPL-2+ 等声明 |
| gcc-14-base / libgcc-s1 | 版权正文按 GCC 组件分列，并含 Runtime Library Exception；不将整个 GCC 版权文件概括为单一工具许可证 |
| init-system-helpers | 默认 BSD-3-clause，同时存在 GPL-2+ 的脚本条目 |

多份说明引用 `/usr/share/common-licenses/`。这些路径没有包含在当前 17 包树中；摘要逐项保留未命中情况，不自动从宿主复制或扩大下载。后续应先确定哪些文件进入诊断 rootfs，再对其引用的许可原文、来源与必要归属补齐；原包本体、完整索引和其他来源材料的持久存储仍单列待办。

安装维护脚本已读取但未执行。具体观察包括：gpg 的 postinst 调用用户级 `deb-systemd-helper` 处理 `keyboxd.socket`；libc6 的脚本包含服务协调、`systemctl daemon-reexec` 及 cache 操作；init-system-helpers 涉及 `/etc/os-release`；libgcrypt20 调用清理脚本；readline-common 涉及 `/etc/inputrc`。各脚本的原始文件身份保存在 control 库存中。只读审阅不授权任何这些副作用，也不能将整个 data 树无选择地视为最小运行集。

## 下一步与停止线

先利用已取得字节完成诊断 rootfs 的**静态布局与运行前置**：固定选定文件 / 链接 / 配置 / 数据清单，解决 interpreter 路径，核对 GNU symbol version 和潜在子进程，明确必要许可文本与持久存储的精确来源。需要新增材料时先列目标和摘要，不重复下载已有 17 包。

布局与材料明确后，再提出工具信任终点及受控离线验签方案：Debian 二进制的来源假设、宿主 TCB、输入 / 输出路径、时间与资源限制、失败终止和清理方式必须一起可审阅。现有官方 HTTPS 公钥身份信任不自动扩展为工具二进制来源 acceptance；不以该 GnuPG 验证自身索引自证可信。

本批不组装 rootfs、不创建镜像、不运行容器、GnuPG、安装器或系统服务；不改变 musl `acceptance = not-assessed`、上游 SHA-1 拒绝、产品 inactive 登记或公共格式。没有到达需要运行授权的可执行方案，下一静态步骤可以继续利用本地材料推进。

## 复核与交接

```bash
python3 docs/records/rust-linux-input-review/inspect-musl-verifier-content.py \
  .tmp/musl-verifier-d04b225-20260912
python3 docs/records/rust-linux-input-review/inspect-musl-verifier-content.py \
  .tmp/musl-verifier-d04b225-20260912 --summary
python3 docs/records/rust-linux-input-review/check-musl-verifier-content.py
./scripts/check-repo.sh
git diff --check
```

默认命令 stdout 为完整库存 JSON；以 Python `gzip.compress(raw_stdout_bytes, mtime=0)` 可重建压缩库存。`--summary` 根据同一库存与已留存获取记录生成摘要；`--include-text` 与摘要模式互斥，只用于本地重读版权及安装脚本文本。首次内容盘点成功，之后补充静态根图和许可引用路径观察，最终输出均绑定最终方法；没有覆盖原始下载观察。

新增 8 项合成检查通过，覆盖精确文件读取、截断 / 拼接 / 超限 XZ、恶意路径、重复项、特殊文件、tar 尾部、链接逃逸 / 循环 / 跨包目录链接和未解析候选的真实报告。它们不执行密码学验签或 loader。最终库存 gzip 与摘要重跑后逐字节一致，18 次获取的原始正文 / stdout / stderr 均与记录匹配；另核对六个 gconv 候选文件确实存在。仓库检查通过（1,100 文件），`git diff --check` 通过。

本批共 8 个更改文件，未暂存、未提交或推送；`dev` 仍相对本地 `origin/dev` 领先原有 2 个提交。原包、失败日志、带全文的本地审阅输出和首次方法副本保留于任务缓存，无后台进程。没有运行 Rust / CI、容器、GnuPG 或安装器，没有新密码学证明或来源 acceptance。
