# Binutils 公钥刷新：GNU 官方钥环核对

用途：为来源审阅者保留两条官方取钥路线的实际结果及可重放比对；不构成公钥身份接受、密码学验签或 Binutils 来源接受。

## 范围与获取结果

上一批[公钥与内容盘点](binutils-key-content-review-2026-09-25.md)已按项目所有者要求提交为 `383b570`，提交前仓库 1,202 文件检查及差异检查通过，提交后工作区干净。随后沿既定顺位寻找主钥 `3A24BC1E8FB409FA9F14371813FCEF89DD9E3C4F` 的更新自认证材料。

[GNU 官方安全说明](https://www.gnu.org/software/security/)列出 Savannah 项目发布公钥接口与 GNU 官方钥环作为取钥路径。网页检索取得该说明；直接网页打开 GNU / Savannah 页超时，Savannah 下载端点无法由网页工具读取，未把这些结果当成公钥字节或身份认证。

本次明确两个精确 HTTPS 目标、每项一次、不重定向 / 重试、单项 60 秒 / 父进程 65 秒、预计最多约两分钟以及本地留存影响后，经执行权限确认完成获取。执行时点为 2026-09-25 **15:28:24–15:28:29（Asia/Shanghai）**。复用未修改的 `fetch-mpc-mpfr-inputs.py`，SHA-256 `2feb632c6422198255c1f3d46b1be18be8914e2c22e67635ce6a106bb01beeab`；没有导入系统钥环或运行 GnuPG。

| 目标 | 上限 | 实际结果 | 原文字节 SHA-256 |
| --- | ---: | --- | --- |
| `https://savannah.gnu.org/project/release-gpgkeys.php?group=binutils&download=1` | 256 KiB | curl 0 / HTTP **404**，7,563 bytes，获取失败 | `13e67cc21fbd848f0c00c80fa78036b851f6f023e54483437dc75ed63ba1de20` |
| `https://ftp.gnu.org/gnu/gnu-keyring.gpg` | 8 MiB | curl 0 / HTTP **200**，3,687,794 bytes | `b136fbe57ade4ee5270ca66c402cae7b50349fd07646b5b3de7962d58d4df608` |

404 原文及两次 stdout / stderr、请求记录和执行前计划均保留；Savannah 响应没有作为公钥解析。不能从一个接口 404 推断 Savannah 不再提供其他公钥入口。计划的 `executed: false` 是执行前时点；实际结果以上述日志为准。

## 精确选取与比对

[诊断入口](inspect-binutils-key-refresh.py)核对请求参数、日志、固定钥环身份和此前附件身份；[导出](binutils-key-refresh-2026-09-25.json)保存完整观察与方法摘要。

完整钥环有 612 个主钥块、27,066 个包。新方法限定 8 MiB / 50,000 包，仅遍历包边界并定位唯一完整 v4 指纹；旧版 / 其他钥的语义不在本次验证范围。重复目标主钥、秘密钥包、未知标签、截断、部分 / 不定长编码及超限均拒绝。新方法不放宽旧 musl / MPFR 的窄公钥解析器。

目标块包含 5 个公钥材料包和 4 个 tag `12` 本地 trust 包。全部原始字节留在钥环中，逐项偏移和摘要进入导出；本地 trust 包只被排除于**公钥材料比对**，不导入、不作为信任依据。剩余公钥材料继续通过旧窄解析器检查。

最初诊断要求去除 trust 包后的编码逐字节相同，实际退出 1，报 `selected key differs: new review required`。已保留该方法原文、失败原因 / 退出码及空输出。随后检查发现两种材料使用旧 / 新格式包头；修正为比较**有序标签和完整包体**，并分别报告包体相等与编码不相等。回归覆盖旧 / 新包头、包体或标签变化、重排、增删、重复目标和资源边界，不能仅凭指纹相同跳过内容差异。

本次结果：

- 目标公钥材料 2,234 bytes，SHA-256 `0c20cd3d5695a7c70f9de37e5b0694261d364dd317cdce3732ee2212ba53eea1`；与旧附件解甲后的 2,234 bytes / `e58bd2ef610ee2c039562ba23cb8cb00d930c5372639e54eb431b495c0224b46` **编码不同**。
- 五个包的有序标签 / 完整包体全部相同：主钥、UID、自认证、子钥、子钥绑定；对应摘要逐项记录在导出 `comparison`。
- UID 自认证与子钥绑定仍均声明 SHA-1，没有新增强摘要自认证、到期或吊销声明。该结论只覆盖取得的材料，不声明外部没有更新或吊销。

因此 GNU 官方钥环未解除既有停止线。未运行真实验签，不能称为 GnuPG 失败；也不能因钥环来自 GNU 就把自签、发布者身份或原包来源标为已接受。原包、归档格式和许可证范围没有变化。

## 留存、复核与下一步

[留存清单](binutils-key-refresh-retention-manifest-2026-09-25.json)涵盖 **24 个路径 / 22 个对象，共 3,789,938 bytes**，含钥环、404 响应、原始日志、旧附件、初版失败方法与最终方法 / 回归 / 导出。复用原小对象留存器；所有文件均低于原 16 MiB 单文件上限。

本机存储为 `artifacts/source-inputs/binutils-key-refresh-383b570-20260925/`，已恢复至 `.tmp/binutils-key-refresh-restore-20260925/`，全部字节核对一致。用清单核对过的工作区方法读取恢复材料，完整诊断与仓库导出逐字节相同，见[恢复结果](binutils-key-refresh-retention-2026-09-25.json)。这不是异盘备份或全新宿主验收。

```bash
python3 docs/records/rust-linux-input-review/inspect-binutils-key-refresh.py \
  --directory .tmp/binutils-key-refresh-restore-20260925/.tmp/binutils-key-refresh-383b570-20260925 \
  --previous .tmp/binutils-key-refresh-restore-20260925/.tmp/binutils-key-inputs-20260925
python3 docs/records/rust-linux-input-review/check-binutils-key-refresh.py
python3 docs/records/rust-linux-input-review/check-mpc-mpfr-key-inputs.py
```

新增 10 项、既有公钥解析 9 项，共 **19 项通过**。未重跑无改动的内容盘点、Rust / CI 或产品构建；没有安装、真实验签、新增长期进程或远程写入。两个 HTTPS 请求已完成，其授权不延续为其他取钥或执行。

`./scripts/check-repo.sh` 通过（1,208 个文件），`git diff --check` 通过；另核对六个新增文件的 UTF-8 / 换行、权限及 24 个留存路径的长度 / 摘要，没有材料漂移。

下一步限定为核对维护者公开的其他取钥路径或完整指纹的公开钥服务器材料；检索没有找到更新材料不等于证明其不存在。若仍只有弱自认证，则保留 Binutils 阻断并单独审阅精确原包的其他来源认证路线；不重复下载已确认相同的历史附件 / GNU 钥环，不启用弱摘要兼容，不继承 MPC / musl 的来源决定，也不替换 `.gz` 为 `.xz` 或更改版本。

本批新增方法、导出和文档未提交；`dev` 相对未刷新的本地 `origin/dev` ahead 5，未推送。任务专用原始材料、失败记录和本机留存 / 恢复目录均保留。
