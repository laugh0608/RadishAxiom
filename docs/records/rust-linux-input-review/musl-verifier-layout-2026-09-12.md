# musl 验证环境静态布局与符号版本盘点

日期：2026-09-12；基线 `dev` / `6c02daf`。项目所有者要求提交已有更改并继续下一步；前批 8 个文件已精确提交，提交后工作区干净，相对本地 `origin/dev` 领先 3 个提交，未查询远端。本批只使用已有原包、固定索引和已安装的宿主静态工具，没有下载、安装、组装 rootfs 或执行包内程序。

后续：项目所有者随后明确授权单个 base-files 原包获取，已完成[许可材料补充与本机影响说明](musl-verifier-licenses-2026-09-12.md)。本文“待获取”等措辞和 JSON 候选状态保留前批时点；没有改写原观察或组装布局。

## 结论及边界

已将[前批 14 个 ELF 候选](musl-verifier-content-2026-09-12.md#根工具与静态依赖候选)收敛为可逐项复核的布局提案：**14 个 ELF、12 份包内 copyright、12 个原包链接、1 个拟生成根链接、18 个目录，共 57 项**。常规文件累计 **8,203,682 bytes**，其中 ELF 为 8,064,784 bytes。加入提案中的 `lib → usr/lib` 后，39 条固定目录 `DT_NEEDED` 候选和 3 条 interpreter 路径均在内存模型中解析到选定文件。

14 个 ELF 共 **67 条 GNU 版本需求**，按声明库找到的版本定义名称与哈希全部相符；**1,277 个带版本未定义符号**均在声明了同名版本的候选库中找到同名、同版本导出。另有 92 个无版本未定义符号：56 个强符号在直接依赖库中找到默认导出，36 个弱符号未匹配，名字为 `_ITM_deregisterTMCloneTable`、`_ITM_registerTMCloneTable`、`__gmon_start__`，逐项保留。

这些是静态候选观察，不能升级为装载、ABI、密码学或来源验收。GNU 版本索引到精确符号提供者的绑定、作用域 / 抢占、重定位、IFUNC / TLS、实际库映射、动态数据访问和子进程仍需受控执行复核。`GLIBC_2.17` 同时出现在 libc 与 loader 的版本需求中，方法保留多个候选，不用版本名字武断选择其中一个。`GLIBC_PRIVATE` 和 `GLIBC_ABI_DT_RELR` 也进入检查，不能只比较一个“最高 GLIBC 版本”。

`acceptance = not-assessed`、`runtime_closure_assessed = false`；尚未接受 Debian HTTPS / WebPKI 作为工具二进制信任终点。musl 原包验签、当前密钥状态、持久材料和产品 qualification 均未因此闭合。

## 可重跑方法和材料

[本批方法](inspect-musl-verifier-layout.py)复用固定原包、ar / XZ / tar reader、ELF 声明和候选路径解析。原包内容只在内存中展开；仅把选定 ELF 字节经 stdin 送入宿主 `llvm-objdump`，不使用 `ldd`，不调用目标 loader，不提取或运行 AArch64 程序。

实际工具通过只读 `xcrun --find objdump` 定位，解析后为：

```text
/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-objdump
Apple LLVM version 21.0.0
18,272,848 bytes
SHA-256 3cccdd0dad838d2130d7fc6237aa176c8c13a593a56b79c64fd980ddb89c670c
```

每个输入使用 `--no-debuginfod --private-headers --dynamic-syms -`，环境只传 `LC_ALL=C`、`PATH=/usr/bin:/bin`，单次超时 20 秒；要求退出 0、stderr 为空，返回 stdout 小于 2 MiB。输出大小是返回后的 profile 检查，不声称是进程内存或输出流的硬限制。命令参数含义参见 [LLVM llvm-objdump 官方说明](https://llvm.org/docs/CommandGuide/llvm-objdump.html)。宿主工具、Python、macOS 及其运行库是本次诊断的可信输入；工具文件摘要不等于工具来源验收。

[完整观察](musl-verifier-layout-2026-09-12.json.gz)保留 14 次完整 stdout / stderr / argv / 退出码、输入摘要、解析后符号、逐符号候选和布局；[摘要与布局](musl-verifier-layout-summary-2026-09-12.json)绑定压缩 / 展开身份、方法摘要、版本比较及新许可材料候选。gzip 使用 `mtime=0`，不是上游文件分片，也不是产品 Evidence。原包、manpage 与版权正文仍需从固定缓存复现，报告不能替代原始材料。

首次方法试跑因为把共享版本名要求为唯一 provider 而显式失败，保留 `layout-method-attempt-1.py`、`layout-attempt-1.json` / `.stderr`；修正为候选集合后再次运行成功，保留第 2 次与最终输出。没有弱化精确版本定义检查，也没有把候选匹配写成精确绑定成功。前批方法和输出未改写。

## 布局提案

摘要 JSON 的 `layout.entries` 是包内文件 / 链接、目录和拟生成根链接的逐项清单，含模式、owner、来源包及常规文件长度 / SHA-256。`origin = proposed-generated` 的根链接由本项目布局生成，不能伪称为原包文件。该清单尚不包含下表中的运行配置、挂载和缺失许可全文；`runtime_complete = false`。

12 个原包链接保留到已选 ELF 的全部别名，包括两条 bz2 别名与 `usr/lib/ld-linux-aarch64.so.1`。3 条 interpreter 包括 gpg、gpgconf 以及 libc 自身；每条最终都指向同一个已固定 loader。没有创建宿主 `/lib`，没有更改原 ELF interpreter，也没有补入宿主库。

保留的 12 份 copyright 对应实际选定文件所属包。`libksba8`、`libgcc-s1`、`gcc-14-base`、`readline-common`、`init-system-helpers` 不在这一静态文件集内，但 17 包原文继续留存；不据此声称所有操作永远不会使用这些包。任何运行时新需求都返回补审阅，不自动扩展环境。

以下是运行配置和数据的明确提案，尚未写入 rootfs；未来组装清单须将实际生成字节、模式、owner、挂载选项和摘要一并固定：

| 对象 | 提案与验收要求 |
| --- | --- |
| home | 预建 `/work/full`、`/work/self`，owner 为合成 UID/GID `1000:1000`、模式 `0700`；每条命令显式 `--homedir`，禁止继承宿主 HOME / GNUPGHOME |
| GnuPG 配置 | 两个 home 中预建零字节 `common.conf`、模式 `0600`；系统 `/etc/gnupg` 为空，`gpg.conf` 不存在；保留 `--no-options`。执行前后记录配置字节，不能默许自动启用 `use-keyboxd` |
| 环境 | 从空环境构造 `PATH=/usr/bin`、`HOME=/work`、`LC_ALL=C`、`TZ=UTC0`；不继承 LD_*、GCONV_PATH、GPG 配置、agent socket 或代理变量 |
| 用户查询 | 拟生成 `/etc/passwd` 的唯一条目 `verifier:x:1000:1000:Verifier:/work:/nonexistent`，`/etc/group` 的唯一条目 `verifier:x:1000:`；均加 LF、模式 `0644`。这些是合成诊断身份，无登录 / 用户管理程序 |
| NSS | 拟生成 `/etc/nsswitch.conf`：`passwd: files`、`group: files`、`hosts: files` 三行并加 LF，模式 `0644`。不启用 DNS；内置 files 路径及实际访问仍须运行检查，不据此宣称 NSS / dlopen 已闭合 |
| 编码 / 终端 | 第一运行切片使用 C locale、batch / no-tty、空 stdin；不预装 locale archive、gettext catalog、gconv 模块或 terminfo。若实际公钥 UID 等输入触发转换或交互数据需求则停止并明确补入文件，不能丢失 UID 或静默切换语义 |
| 数据写入 | 只允许独立 `/work` 中公钥 keybox、trustdb、锁文件、随机状态、诊断导出与日志；不预置宿主 trustdb、ownertrust 或任何私钥。不关闭锁，也不引入 always-trust |
| 只读输入 | 固定 keyring、两公钥、InRelease 等逐文件挂载到 `/inputs`；清单需绑定原始字节。完整 Sources / musl 原包可在主机后置摘要复核，不将旧 verified_text 当作输入事实 |
| 运行设施 | `/dev/null`、随机源、`/proc`、临时空间、时钟、kernel、资源和超时由后续受控运行方案分别定义；它们不是 Debian tar 内已有文件，不从宿主目录任意复制 |
| loader | 保留原 loader 及库目录；不生成 `ld.so.cache`、不设置 `LD_PRELOAD` 或库搜索兜底。实际加载映射必须与固定清单相符；静态路径可解析不替代运行观察 |

配置提案的依据是固定包内 `usr/share/man/man1/gpg.1.gz` 与 `gpgconf.1.gz`，原始及解压摘要见报告 `manuals`，不是其他版本的在线手册。gpg 手册说明：默认 home 不存在时可创建带 `use-keyboxd` 的 `common.conf`；`--no-options` 对应禁读默认 options，并抑制默认 home 创建。`common.conf` 是另一份可读配置，不能因 `--no-options` 就假定所有配置均被禁用。

沿用[密码学命令设计](musl-verifier-environment-2026-09-12.md#密码学复核命令清单设计未执行)的公钥操作和两角色合取要求；将来运行公共参数另加包内手册已有的 `--disable-dirmngr` 和 `--exit-on-status-write-error`，分别禁止使用 dirmngr 和在状态输出失败时终止。这只是待运行参数设计，不改变信任、摘要或有效期条件，也不能证明没有其他子进程。

gpgconf 暂保留作路径诊断，允许方案限定为 `--version`、指定 home 的 `--list-dirs`；不采用 `--check-programs`、`--launch`、`--apply-defaults`、`--query-swdb` 等会检查 / 启动后端、改配置或涉及下载的入口。gpgconf 手册还允许同目录 `gpgconf.ctl` 改写编译路径，本布局不含该文件。后续实际路径、进程、文件访问若与清单不符必须停止。

## 许可全文的下一项精确材料

包内 copyright 引用的 common-licenses 在已有 17 包中不存在。本次从**同一已固定 Packages / Sources** 唯一关联 `base-files`，得到以下待取候选：

```text
https://deb.debian.org/debian/pool/main/b/base-files/base-files_13.8+deb13u6_arm64.deb
73,276 bytes
SHA-256 5f5a571ec846d7db05d9f825f0388a37bc033267b33cbf85b4eaa838dffcc41b
Source: base-files 13.8+deb13u6
```

这是为补 common-license 原文准备的内容候选，尚未取得或核对包内路径。12 份版权文本提及 `CC0-1.0`、`GPL-2`、`GPL-2.0`、`GPL-3`、`LGPL`、`LGPL-2`、`LGPL-2.1`、`LGPL-3`、`GFDL`；其中别名 / 文本路径可能不直接存在，不能擅自改名或假定全部由该包覆盖。取得后逐项辨别实际许可版本及引用范围，必要时补明确的来源映射。正文归属与未来分发责任另行审阅，不能将留了 copyright 写成许可证验收完成。

只做原包内容读取，不安装 base-files，也不扩展其 `Pre-Depends: awk` 为运行依赖。不会执行包脚本或套用其系统配置 / 根目录布局。

[精确 fetch 差异](musl-verifier-licenses-fetch-method.patch)复用已有方法，仅保留这个目标并加入固定长度 / SHA-256 成功条件；准备脚本位于 `.tmp/musl-verifier-d04b225-20260912/fetch-musl-verifier-licenses.py`，SHA-256 为 `a0c1963741a5663a05bc6744ac8ff13fd8e3696b0d20d7ff162efe476f63a3b1`，尚未调用 curl。

若项目所有者授权下一次获取，精确入口为：

```bash
python3 .tmp/musl-verifier-d04b225-20260912/fetch-musl-verifier-licenses.py base-files 1
```

只请求上述 HTTPS URL，不跟随重定向、不降级 TLS 校验；正文上限 73,276 bytes，curl 每次 60 秒、父进程 65 秒。仅首轮满足既有传输失败条件时允许 `base-files 2` 一次；404、重定向、摘要漂移不换地址或滚动版本。两次正文上限累计 146,552 bytes，预计获取和静态盘点 2–5 分钟。

副作用是该公开端点的一次请求（符合条件时重试一次）及任务目录中的包和日志。所有文件保留，不启动后台进程，不安装、不组装或执行；失败后保留记录，无需系统回滚。清理只处理后续明确列出的本批文件。工具信任终点、rootfs 组装和容器验签仍另行明确目标、影响并取得授权。

## 复核与交接

可重跑静态观察：

```bash
python3 docs/records/rust-linux-input-review/inspect-musl-verifier-layout.py \
  .tmp/musl-verifier-d04b225-20260912 \
  --objdump /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/objdump \
  --sources .tmp/musl-auth-chain-0a66901/Sources.xz
python3 docs/records/rust-linux-input-review/check-musl-verifier-layout.py
python3 docs/records/rust-linux-input-review/check-musl-verifier-content.py
./scripts/check-repo.sh
git diff --check
```

本批 8 项合成检查覆盖版本定义不符、版本存在但符号不符、共享版本名、未匹配弱符号、非默认导出、依赖缺失和输出格式漂移，全部通过；已有内容盘点的 8 项检查亦通过。合成检查不调用 objdump 或 GnuPG，不是密码学负例。实际原包观察已独立重跑，完整 gzip 与摘要 JSON 均逐字节一致；fetch 差异经 patch 重建与准备脚本一致，语法检查通过，未调用网络。仓库检查通过（1,106 文件），`git diff --check` 通过。

前批已提交为 `6c02daf`；本批代码、报告、fetch 差异和状态更新尚未提交或推送。尚未运行 Rust / CI、GnuPG、容器、安装、构建、网络下载或远程写入，无本批后台进程。完整 Sources、原包、网页、keyring 包与验证工具包仍依赖忽略缓存；持久存储位置、保留责任与恢复验证尚待落实。下一步先补上述许可材料，再收口宿主运行身份、持久留存和受控离线验签方案。
