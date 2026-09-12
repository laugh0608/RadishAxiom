# musl 验证环境许可材料补充与本机写入范围

日期：2026-09-12；基线 `dev` / `6c02daf`，启动时保留前批 8 个未提交文件，相对本地 `origin/dev` 领先 3 个提交，未查询远端。用途：记录经项目所有者明确确认后的单包下载、静态内容盘点及本机影响；不构成工具来源、许可证分发责任、可运行 rootfs 或密码学验收。

## 获取与内容结果

项目所有者确认[前批精确获取范围](musl-verifier-layout-2026-09-12.md#许可全文的下一项精确材料)，并询问材料保存位置和本机环境影响。本批只请求固定 `base-files=13.8+deb13u6` / arm64 的 Debian HTTPS URL，未扩大到依赖安装、其他下载或目标程序执行。

首轮在沙箱内连接失败，curl 退出 7 / HTTP 000、正文 0 bytes；按已声明重试条件申请沙箱外重试后，第二次退出 0 / HTTP 200，正文 **73,276 bytes**，SHA-256 为 `5f5a571ec846d7db05d9f825f0388a37bc033267b33cbf85b4eaa838dffcc41b`，与固定索引一致。未换地址、跟随重定向或关闭 TLS 检查。两次请求区间为 `2026-09-12 12:22:41–12:22:52 UTC`；实际起止时间、命令、退出码、正文和原始输出身份见[获取记录](musl-verifier-licenses-fetch-2026-09-12.json)。方法仍为 `a0c1963741a5663a05bc6744ac8ff13fd8e3696b0d20d7ff162efe476f63a3b1`。

成功原包是 `.tmp/musl-verifier-d04b225-20260912/base-files-attempt-2.deb`；首轮空正文及全部日志保留。原包未解包写入磁盘，只由[本批方法](inspect-musl-verifier-licenses.py)复用前批 ar / 有界 XZ / tar reader 在内存中读取。

control 的包名、版本、架构、Source 归属及关系字段与固定候选一致。data 中共 **89 个成员**，没有 ELF；`usr/share/common-licenses` 下有 **14 个常规文本和 3 个链接**，逐项模式、owner、长度和 SHA-256 见[盘点结果](musl-verifier-licenses-2026-09-12.json)。检查了安装元数据身份，但没有执行 `preinst` / `postinst` / `postrm` 等脚本。

## 引用匹配与增补清单

对前批选定 12 包的 copyright 以及 base-files 自身的 copyright，共检查 **30 条 common-license 路径引用**：28 条能按包内路径解析，2 条保留为字面路径缺失。以下区分路径事实与经人工审阅的文本候选，不把一个通用别名当作所有组件的实际许可证。

| 引用或声明 | 原包事实 | 本批处理 |
| --- | --- | --- |
| gpg / gpgconf 的 `GPL-2.0` 引用 | 该路径不存在；相邻正文明确 GPL version 2.0，`GPL-2` 文本标题为 Version 2, June 1991 | 保留两条缺失结果，另列 `GPL-2` 为文本候选；不修改上游 copyright，不创建伪称上游提供的别名 |
| libgcrypt20 的通用 `LGPL` 引用 | 原包链接 `LGPL → LGPL-3`；库声明为 2.1 或更高版本 | 同时保留原链接事实与明确的 `LGPL-2.1` 文本候选；链接本身不决定库的许可版本或选择路线 |
| readline copyright 的 `GFDL` 引用 | 原包链接 `GFDL → GFDL-1.3`，原 copyright 对相关文档声明 1.3+ | 保留别名及精确 1.3 文本；不把文档条款套到整个 readline 库 |
| base-files copyright 的 `GPL` 引用 | `GPL → GPL-3`；copyright 另外区分 GNU 许可文档的 verbatim 条款 | 保留自身 copyright 和引用文本，不将整包默认声明用于重写各许可文档 |

这一步只补齐静态提案需要的许可材料来源及引用对应关系，`license_acceptance_assessed = false`。没有改变上游许可、项目 LICENSE 或作出分发许可结论；组件级条款、版权归属和未来分发责任仍按专题审阅。

`supplemental_layout_entries` 列出 **13 项增补提案**，累计常规文件 **144,028 bytes**：

- 7 份 common-license 文本：`CC0-1.0`、`GFDL-1.3`、`GPL-2`、`GPL-3`、`LGPL-2`、`LGPL-2.1`、`LGPL-3`；
- 3 个原包别名：`GFDL`、`GPL`、`LGPL`；
- base-files 的 copyright，以及 common-licenses 和 base-files 文档两个目录。

与前批 57 项组合后是 **70 项 / 8,347,710 bytes 常规文件**的静态材料清单，仍不包含运行配置和挂载，尚未实际组装。base-files 原包也有 `lib → usr/lib`，本批保留这一来源观察，未自动替换前批拟生成根链接的来源标记，也没有在宿主创建 `/lib`。不引入该包的其他目录、`/etc/profile`、`os-release`、登录配置或 `Pre-Depends: awk`。

## 下载位置与本机环境影响

截至本批结束，主要原包与来源材料均位于项目根下已忽略的 `.tmp/`。下表占用由 `du -sh` 读取，包含原文、方法副本、失败日志和中间报告，数字为本批时点近似值，不是下载正文总量：

| 项目内目录 | 主要材料 | 占用 |
| --- | --- | --- |
| `.tmp/musl-verifier-d04b225-20260912/` | 固定 Packages、原先 17 个验证工具包、本次 base-files、检查输出与日志 | 约 26 MiB |
| `.tmp/musl-auth-chain-0a66901/` | 固定 Sources、keyring 数据和原来源链诊断 | 约 21 MiB |
| `.tmp/musl-source-review-c7f7f60/` | musl 原始归档和此前来源审阅材料 | 约 11 MiB |
| `.tmp/musl-trust-bbbe083-20260910/` | Debian keyring 原包、身份页面及获取日志 | 约 244 KiB |

上述路径的绝对前缀为 `/Users/luobo/Code/RadishAxiom/`；本次缓存路径解析后仍位于该工作区，没有转向系统安装目录。正式诊断方法、摘要和记录位于 `docs/records/rust-linux-input-review/`。Python 导入还会产生项目内、已忽略的 `__pycache__`；这些属于本地分析缓存，不是第三方包安装。

**就这批验证环境材料获取和静态检查而言，没有修改本机已安装的软件环境。** 没有调用包管理器安装 / 升级，没有执行下载包中的程序或安装脚本，没有写入系统库 / 系统 `/lib`，没有修改全局 PATH、shell 启动文件、用户 GnuPG home、证书或密钥链，也没有启动服务或创建容器。使用的是既有 Python、curl 和前批已有 LLVM 静态工具。实际影响是上述文件占用，以及有限检查进程的 CPU / 内存消耗。

沙箱外重试仅用于同一已授权公开 HTTPS 请求，其输出仍在任务缓存内；获得网络执行许可不等于安装许可。安装脚本虽然包含 profile、目录迁移及权限修改逻辑，本批仅作为字节读取，未触发这些行为。这一陈述限定于所述操作，不冒充整台机器的系统配置审计或更早所有开发活动的完整盘点。

Git 已确认这些下载路径被忽略；提交诊断代码和记录不会自动提交 `.deb` / 源码缓存。删除缓存不需要卸载软件，但会丢失原包和复现材料，因此本批没有清理或移动任何已有缓存。长期留存、备份和恢复验证仍需单独落实；忽略缓存和一串摘要不能充当持久 source lock。

## 验证与下一步

重跑入口：

```bash
python3 docs/records/rust-linux-input-review/inspect-musl-verifier-licenses.py \
  .tmp/musl-verifier-d04b225-20260912 --attempt 2
python3 docs/records/rust-linux-input-review/check-musl-verifier-licenses.py
python3 docs/records/rust-linux-input-review/check-musl-verifier-content.py
./scripts/check-repo.sh
git diff --check
```

本批 5 项合成检查全部通过，覆盖字面路径缺失不被候选掩盖、不对其他包泛化改写、声明 / 标题漂移、别名与组件声明分离以及缺少替代文本的拒绝；已有内容 reader 的 8 项检查亦通过。获取记录已与两次原始正文 / stdout / stderr / 方法逐项核对；完整静态盘点独立重跑后与留存 JSON 逐字节相同。70 项组合内存布局无路径碰撞，全部选定链接可解析。仓库检查通过（1,111 文件），`git diff --check` 通过。这些检查不执行目标程序或密码学验签。

下一步使用已有材料收口持久存储位置与恢复检查、宿主运行身份及受控离线执行方案，再明确接受或拒绝工具二进制的初始信任假设。组装、容器执行和验签仍分别授权。本批不再需要重复下载已有 18 个工具 / 许可包，也不因已取得许可文本就启动运行。`acceptance = not-assessed`、旧 payload inactive、公共契约和产品执行停止线保持不变。

前批 8 个未提交文件保留，本批方法、测试、获取记录、盘点与本文亦未提交或推送；没有修改 Git 身份或远端。未运行 Rust / CI、GnuPG、容器、产品安装或构建；本批获取与检查进程已结束，无后台进程。
