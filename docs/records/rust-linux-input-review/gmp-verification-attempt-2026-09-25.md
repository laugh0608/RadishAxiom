# GMP 首次受限离线执行：导入阶段停止

日期：2026-09-25（Asia/Shanghai）。执行基线：`dev` / `6852a43`。

用途：记录本次授权、实际停止点、清理、留存与离线诊断，供后续方案审阅。本文不接受 GMP 来源，不将导入工具退出 0 写成自认证或原包验签通过，也不改写[原方案](gmp-verification-entry-2026-09-25.md)及其方法。

## 授权、提交与实际结果

项目所有者明确要求“授权，提交工作区更改，然后继续推进”。先复核并精确提交原方案的 10 个文件为 `6852a43`（`chore(runtime): 准备 GMP 受限离线验签方案与入口`）；提交后工作区干净，相对本地 `origin/dev` ahead 11，未 push。

随后在可访问 Docker socket 的权限范围内，按原方案、原镜像、原输出目录执行一次：

```bash
python3 docs/records/rust-linux-input-review/run-gmp-verification.py --execute-authorized
```

实际时间 **20:15:59.686–20:16:00.212**，整批约 0.526 秒，入口退出 **1**。仅执行第一步 `filter`：固定 GnuPG 正常退出 **0**，未 OOM，stdout 为 1,501 bytes，但状态输出为：

```text
[GNUPG:] KEYEXPIRED 1736961163
[GNUPG:] IMPORT_RES 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0
```

原入口导入阶段复用的 `IMPORT_ALLOWED` 不包含 `KEYEXPIRED`，因此真实结果为 `passed = false` / `failure = unexpected auxiliary status: KEYEXPIRED`。原方案曾明确要求未知输出保存失败并停止；本次照此执行，没有继续 `certifications`、原包 `verify` 或三个负例，没有重试、放宽白名单、启用弱摘要或回拨时钟。

固定 CLI、daemon / 资源 preflight、image 与该次 mount / 隔离检查通过。唯一容器 `bbbc68d8bad9b12584ccf4bd872c571bb60150d7789a90350119d3ef951a4bde` 已确认 ownership、非运行 / 非 OOM 状态并删除，`container rm` 退出 0。没有遗留本批容器、后台进程或新增镜像；保留原有 image / rootfs 与所有公开输入、日志。

## 离线诊断：不改变原判定

[复核方法](inspect-gmp-filter-attempt.py)固定绑定本次 bundle 与 `result.json` 摘要，核对原执行方法、原归档及 staged 输入，消费全部 **10 条命令日志**，重放 preflight、image、create、前后 inspect、start 参数与采集限额、ownership 和清理。它不连接 Docker，不运行 GnuPG，也不重新调用有写入副作用的执行判定。

原白名单对这两行状态的拒绝已在离线复核中复现。输入 `gmp.strong.gpg` 与 GnuPG stdout 的五个主体 / 自认证 packet 包体逐项相同；包编码不同，因此整文件 SHA-256 不同：

| 材料 | bytes | SHA-256 |
| --- | --- | --- |
| 强摘要候选输入 | 1,501 | `fee8194e5cde8f7b023639e929cae3c8773f8b9e7e3a561ee9335bbae5381fdf` |
| 实际导出 stdout | 1,501 | `928ac84aa0e2134bbb335cd439110dc3f9b967eb04caff4a44dd5d04a3f13474` |
| 实际 status | 81 | `b3ca051b505c765d34f4e4bed8ff60593beca7dca3955a405295edce5e8aa7ec` |
| 原始 `result.json` | 56,153 | `c0ccd560880bccaaa7a565677a4ec11ef6555c1061fcbce9d33ac065b5c6d158` |

这说明本次可观察到的停止点在辅助状态判定，未观察到包体被导入器改写；不说明尚未运行的 `--check-sigs` 或分离签名验证会通过。到期报告仍完整保留，第三方撤销、材料最新性、身份、可信时间与工具 / 宿主假设均未闭合。

## 留存、恢复与复现

既有 [导出入口](collect-gmp-verification-execution.py)生成失败留存包：6,034,533 bytes，SHA-256 `480c6889fd21a595a0f5981c700c86439a4d71c50d0e71a39d3ea4c4de4cf336`。包内保存全部公开输入、原方法快照、命令 / stream / status 和原始报告；原收集器的离线重放保持 `failed-run-retained` / `replayed_success = false`。它不把失败包重标为六项成功。

- 真实执行目录：`.tmp/gmp-verification-20260925/`，保持原字节。
- 本次失败导出：`.tmp/gmp-verification-execution-20260925.json`。
- [机器复核结果](gmp-verification-attempt-2026-09-25.json)只包含摘要、有限日志与诊断；完整第三方字节留在本机材料库，不新增到 Git。
- [留存清单](gmp-verification-retention-manifest-2026-09-25.json)覆盖完整 bundle、复核源码 / 测试、结果及原收集器，共 5 项 / 5 对象 / 6,060,928 bytes。
- 持久目录：`artifacts/source-inputs/gmp-verification-6852a43-20260925/`。
- 恢复目录：`.tmp/gmp-verification-restore-20260925/`；[恢复结果](gmp-verification-retention-2026-09-25.json)确认全部身份一致，不代表异盘备份。

以下均为离线读取，不授权重跑容器：

```bash
python3 docs/records/rust-linux-input-review/collect-gmp-verification-execution.py \
  --replay .tmp/gmp-verification-execution-20260925.json \
  --sha256 480c6889fd21a595a0f5981c700c86439a4d71c50d0e71a39d3ea4c4de4cf336
python3 docs/records/rust-linux-input-review/inspect-gmp-filter-attempt.py
python3 docs/records/rust-linux-input-review/inspect-gmp-filter-attempt.py \
  --bundle .tmp/gmp-verification-restore-20260925/.tmp/gmp-verification-execution-20260925.json
python3 docs/records/rust-linux-input-review/check-gmp-filter-attempt.py
./scripts/check-repo.sh
git diff --check
```

本批新增 **6 项合成检查通过**：原拒绝复现、包编码与包体区别、错误 / 缺失 / 重复到期及导入计数、额外错误 / 成功状态、主体 / 自认证篡改，以及白名单被静默放宽后不得继续声称复现原失败。准备阶段 153 项检查属于此前结果，本轮未重复执行；没有改动原执行方法或历史输入。

恢复副本重新生成机器复核结果，与仓库导出逐字节一致。仓库检查通过（1,264 个文件），`git diff --check` 通过。

## 下一步与停止线

下一步先单独审阅 GMP 导入与自认证检查阶段的辅助到期状态：如果设计修正，必须绑定精确主体和到期时间、限制状态数量 / 顺序、保留所有失败状态，并增加错误时间、错误主体、重复、额外失败及包体变化负例。不能仅把 `KEYEXPIRED` 加入宽松白名单，不能将当前到期或来源未接受状态消除；还须评估未运行阶段是否有同类状态假设。

本轮没有修改该判定或准备另一次容器运行。任何修正后的真实执行应使用新的独占输出目录，保留本次失败材料，先形成可审阅方案再取得新的精确授权；本次单次执行授权已消耗。

GMP 仍未完成自认证 / 原包验签，也未接受来源。GCC / Binutils 缺口继续阻断完整 source lock 与安装；headers 仍仅为内容对应核对。本轮没有新增下载、安装、产品构建、Rust / CI 或远程写入。执行后的记录与离线复核文件留在工作区，未再次提交。
