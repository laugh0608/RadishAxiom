# musl 来源材料压缩备份与恢复检查

日期：2026-09-16；基线 `dev` / `aa13d7c`。项目所有者要求先提交已有工作区，再推进下一步，并将压缩备份放入 `/Users/luobo/Downloads/`，由其后续上传云端或转移介质。本记录面向材料保管者，不构成已经完成异盘备份或公开再分发的声明。

## 已交付文件

Downloads 中已独占创建并逐字节读回以下三个文件，没有覆盖已有文件或上传：

| 文件名 | bytes |
| --- | ---: |
| `RadishAxiom-musl-source-aa13d7c-20260916.tar.gz` | 63,357,870 |
| `RadishAxiom-musl-source-aa13d7c-20260916.tar.gz.sha256` | 114 |
| `RadishAxiom-musl-source-aa13d7c-20260916-RESTORE.md` | 3,697 |

压缩包约 **63.4 MB / 60.4 MiB**，SHA-256 为 `db826bd19472363a07b7306763b5ffc262526cd31fff5580e36a316d7f9cea27`。完整结果、方法身份与三个复核输出摘要见[交付记录](musl-backup-transfer-2026-09-16.json)。Downloads 位于本机，`off_device_backup_verified = false`；项目所有者负责后续介质选择、转移、保管并核对目标副本。

包内 1,628 个文件，内容字节合计 **82,857,946**（不含 tar 头与文件系统开销）：包含固定提交的完整仓库文件快照、87 个归档对象及清单、验签两批与 smoke 原始日志、固定 rootfs tar、打包方法及[恢复说明](musl-backup-restore-instructions.md)。快照不含 Git 历史；打包方法是该快照之外的显式补充文件。本轮后续六项依赖审阅不在快照中，不声称这是整个项目全部缓存的备份。

选择范围由[打包入口](package-musl-source-backup.py)精确列出；先重算两份验签及 smoke 导出、核对所有旧归档对象，再对固定提交执行 `git archive`，不扫描并打包整个工作区或用户目录。没有 `.git`、用户 Docker 配置、凭据、daemon 镜像库或其他大型 Rust / kernel 缓存。单文件 16 MiB、全部选择内容 128 MiB、最多 2,048 项；这是私用备份边界，不改变仓库 10 MiB 单文件门禁。

## 实际恢复与发现的问题

完整归档读回通过后，用 `tar -xzpf` 解压到全新任务目录，对 MANIFEST 中所有文件逐项核对集合、长度、SHA-256 和权限，全部通过。随后仅从恢复树调用三个既有导出入口：首次验签失败、第二次九项验签成功、此前 smoke，均退出 0 / stderr 为空，输出与该树内提交记录逐字节相同。这个检查补上了“旧对象库未包含新验签日志”的复核恢复路径，没有重新运行 GnuPG 或 Docker。

两次失败没有被隐藏：首次打包将本地文件统一为 `0600`，第二次验签的恢复复核因输入应为 `0444` 而拒绝。修正打包为保留原始模式后，Python `tarfile` 的 `data` 提取过滤器仍添加 owner-write 位，恢复复核再次拒绝；归档内模式当时已正确。最终恢复采用显式保留模式的 `tar -xzpf`，并验证全部文件模式。恢复说明记录此要求，没有放宽原验签入口检查。

首次、第二次及最终包分别留在 `.tmp/musl-backup-aa13d7c-20260916/`、其 `attempt-2/`、`final/` 子目录；恢复检查目录与日志也保留在这些目录内。只有最终包被复制到 Downloads。失败包不能交付或冒充已通过恢复验证；本轮没有删除原材料或广泛清理目录。

生成入口（输出必须不存在）：

```bash
python3 docs/records/rust-linux-input-review/package-musl-source-backup.py \
  .tmp/musl-backup-aa13d7c-20260916/final/RadishAxiom-musl-source-aa13d7c-20260916.tar.gz
```

该路径已有最终产物，重复调用将拒绝覆盖。宿主 Python 及 Git 仍为复核可信工具，复制 / 解压测试不验证物理介质耐久性。新机器动态运行需要单独准备和审阅环境，镜像 ID 不能跨 daemon 当作自动可用的安装状态。

## 存储选择

本轮按用户安排交付私人转移包。建议与校验文件一起保存到私人云端或其他介质，并从目标位置重新读取校验；此后再记录备份位置与恢复责任，不能仅凭上传界面成功就声称完成恢复检查。

本仓普通 Git 单文件上限 10 MiB，因此这个 60.4 MiB 包不进入 Git 历史、不分片绕过门禁。Git 继续保存打包方法、交付摘要和恢复说明。如希望使用 GitHub，可以另行选择合适可见性的 [Release 附件](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github#distributing-large-binaries)；该机制与普通 Git 文件不同，本轮没有创建 Release、tag、引入 LFS 或上传。包内含第三方工具二进制及来源材料，私人备份不自动授权公开再分发，公开共享仍按已有许可审阅边界处理。

前批六份验收文档已提交为 `aa13d7c`，该提交及此前 `3c9bb06` 尚未推送。本批备份方法、恢复说明、交付记录和进度文档为后续未提交更改，无新增后台进程；来源验收范围、安装与产品停止线不变。

本批与六项来源路线记录一并通过 `./scripts/check-repo.sh`（1,159 个文件）及 `git diff --check`。没有重新执行密码学算法、安装、构建或远端写入；真实恢复与三个离线重算是本次备份的实际验证。

## 日终位置复核（2026-09-16）

上述三份文件在交付时存在并通过核对；日终只读检查发现三者均已不在 Downloads 原路径。未推断移动 / 删除原因或云端状态，未重新复制、搜索用户其他目录或覆盖文件。项目内 `.tmp/musl-backup-aa13d7c-20260916/final/` 的最终压缩包仍为 63,357,870 bytes，重算 SHA-256 与交付值一致；日终未重新解压。后续两个 MPC / MPFR 材料增量各自有本机归档，未进入这个固定包。转移后的副本核对与后续增量安排见[明日事项](../../status/current.md#明日事项2026-09-17)，不改写先前交付与恢复事实。
