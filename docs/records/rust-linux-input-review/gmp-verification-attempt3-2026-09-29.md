# GMP v3 第三次诊断与六步真实结果

日期：2026-09-29（Asia/Shanghai）；基线 `dev` / `f3811cb`。

用途：记录已授权的一次真实诊断、清理、导出及本机留存恢复。不接受 GMP 来源，不建立历史有效性，不授权再次运行、安装或发布；此前准备记录保留其执行前时点含义。

## 授权与结果

项目所有者对[第三次诊断的精确范围](gmp-verification-v3-entry-2026-09-29.md#第三次诊断的精确待授权范围)回复“确认，继续推进”。按该范围执行一次 `run-gmp-verification-v3.py --execute-authorized`，实际时间为北京时间 **20:11:05.482566–20:11:16.311687**，约 **10.83 秒**。整批 `passed = true`，六步均符合预注册判定；没有重试、续跑或临场放宽规则。

| 步骤 | GnuPG 退出码 | 实际结果 |
| --- | ---: | --- |
| 强摘要材料过滤 | 0 | 五包材料对应，保留明确到期通知 |
| 自认证 | 0 | 两份 SHA-256 自认证 `sig:!`，精确四行 status 与 v3 联合判定一致 |
| GMP 原包分离签名 | 0 | `EXPKEYSIG` 与 `VALIDSIG`，签名关系匹配、钥匙当前已到期 |
| 单字节篡改正文 | 1 | `BADSIG` 与 `FAILURE gpg-exit 33554433`，按负例预期拒绝 |
| 错误主钥 | 2 | 指定 signer 的 `ERRSIG` / `NO_PUBKEY`，按负例预期拒绝 |
| 缺失主钥 | 2 | 指定 signer 的 `ERRSIG` / `NO_PUBKEY`，按负例预期拒绝 |

真实原包为 2,094,196 bytes 的 `gmp-6.3.0.tar.xz`，SHA-256 `a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898`；分离签名 374 bytes，SHA-256 `94def8c1a731854de684689126046ec93589147abd4cd0025f12d741d323aa82`。`VALIDSIG` 完整 signer / primary 均为 `343C2FF0FBEE5EC2EDBEF399F3599FF828C67298`，RSA / SHA-512、v4 / class `00`，签署时间声明为 `2023-07-30 12:18:33 UTC`。

自认证保留两种不同事实：包内子钥到期声明为 `1736961679`，工具列出的子钥有效到期为 `1736961163`，与已到期主钥一致。真实 status 为一条固定到期通知、一条 `KEY_CONSIDERED`、再两条相同到期通知；本次没有将它外推为通用协议。

## 执行与清理

运行 ID 为 `c5ebdc411cff462e891f90ae4e41f2e8`。仍使用方案固定的 Docker CLI / socket、daemon 29.4.0 / API 1.54、image `sha256:55063921d0e996f717092e07dce8041cb2376cc171a070bf9a0a38a5dd16c777` 和 GnuPG 2.4.7。工具 / rootfs / image / 资源配置门禁通过。

六个容器均无网络、只读根、非 root，沿用 1 CPU / 128 MiB / 32 PID 与两个 16 MiB tmpfs；只挂载固定只读输入和当步 status。45 条命令保存了实际参数、限额、输出、退出码、时间与清理状态；六次 ownership 核对和 `container rm` 均成功，没有待协调的残留容器。宿主日志保留在 `.tmp/gmp-verification-20260929-attempt3`；已有镜像、工具库和两次失败材料保持不变。

执行前留存 33 个方法 / 依据文件，结束后重核输入和方法一致。没有联网取钥、下载、安装、执行上游源码、回拨时钟、写 ownertrust 或系统钥环；没有新增后台服务。

## 导出、重放与留存

[v3 收集器](collect-gmp-verification-v3.py)导出完整 bundle 并无执行重放全部 45 条命令，重新检查六项判定，返回 `six-case-record-replayed` / `replayed_success = true`。[重放机器结果](gmp-verification-replay3-2026-09-29.json)可以用以下命令逐字节重算：

```bash
python3 docs/records/rust-linux-input-review/collect-gmp-verification-v3.py \
  --replay .tmp/gmp-verification-execution-20260929-attempt3.json \
  --sha256 2b097ea44fcb792b03ec185e5edc604b3bb7221f6b30b9452cdcd225e5ca31d1
```

| 对象 | bytes | SHA-256 |
| --- | ---: | --- |
| 完整 bundle | 6,480,599 | `2b097ea44fcb792b03ec185e5edc604b3bb7221f6b30b9452cdcd225e5ca31d1` |
| 原始 `result.json` | 85,999 | `51c87a9860fb6da2604a4310555c6fc8d28411dceacf15636454b62302b87d19` |
| 重放机器结果 | 2,932 | `407f58edf48e0ed721b408b950a1fbedb6de9fc58d2d4b13b6fa830110875c6f` |
| 留存 manifest | 2,123 | `234474ae5af4af0d71fae3b0e41d0bc29bc8a357516f78da8c4636c51ca2d4df` |

[精确留存清单](gmp-verification-retention-manifest3-2026-09-29.json)覆盖完整 bundle、v3 执行 / 收集 / 检查入口、准备方案、机器计划和重放结果，**7 路径 / 7 对象 / 6,535,704 bytes**。bundle 内含完整输入、日志和实际方法快照；第三方原始材料没有新增到 Git。

使用既有 `retain-musl-verifier-inputs.py` 的 `pack` / `restore`，持久库为 `artifacts/source-inputs/gmp-verification-f3811cb-20260929-attempt3`，恢复目录为 `.tmp/gmp-verification-v3-restore-20260929`。全部恢复字节一致，见[留存恢复报告](gmp-verification-retention3-2026-09-29.json)；从恢复 bundle 重放的报告与上述 2,932 bytes 结果逐字节一致。仅为本机留存，不代表异盘备份或包含 Python / image 的完整环境恢复。

## 结论边界与下一步

本次支持固定 GnuPG 对固定材料报告的签名关系，以及三个负例拒绝；不是独立密码学实现复验。原判定器继续返回 `source_acceptance = not-assessed`、`historical_validity = not-established`、`runtime_qualification = false`。过期主钥并不单独证明历史签名无效，签名内时间声明也不是可信时间戳，不能因实际退出 0 自动建立历史有效性。

公钥及身份材料仍为有限快照，第三方认证撤销声明未认证、全渠道撤销 / 最新性未闭合；现实身份依据、固定工具及宿主 / 时钟假设仍须明确审阅。下一步先整理固定 GMP 原包能够支持的限定来源声明及剩余信任，再判断是否需要补充精确材料；现有执行授权不包含接受这些假设、刷新材料或再次验签。GCC / Binutils 和 headers 来源缺口仍在，完整 source lock 与安装继续阻断。

执行入口未修改；此前 113 项合成检查保留原验证时点，本轮复跑 v3 的 15 项检查通过。仓库检查与 `git diff --check` 通过。未运行 Rust / CI、产品构建或安装，未提交 / 推送；`dev` 相对本地 `origin/dev` ahead 1。本轮新增四个结果 / 留存文件，加上前轮七个未提交文件，共 11 个工作区文件改动，均属于 GMP 切片。
