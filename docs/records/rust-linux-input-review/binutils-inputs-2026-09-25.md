# Binutils 2.44 原包与分离签名材料

日期：2026-09-25；基线 `dev` / `8a610c7`。用途：向来源维护者交接固定配方原包的获取、摘要对应、未认证签名字段和本机保留情况。状态：**原包材料核对完成，公钥身份、真实验签及来源接受未完成**。本批没有解压盘点、许可证验收、安装或构建。

## 本轮范围与结果

项目所有者在解释信任范围后回复“接受，继续推进吧”，已记录 [MPC 限定归档来源决定](mpc-source-acceptance-review-2026-09-25.md)。按[剩余依赖路线](musl-remaining-sources-2026-09-16.md)，下一项选择固定配方中的 `binutils-2.44.tar.gz`。其余 GCC / GMP / headers 仍待补，不用 Debian 的 `.orig.tar.xz` 替代本项 `.tar.gz`。

[Sourceware 官方发布公告](https://sourceware.org/pipermail/binutils/2025-February/139195.html)链接发布目录并列出精确 `.tar.gz` 的 SHA-256；公告同时区分 `binutils-with-gold-2.44`，本次没有替换为该变体。首次 GNU FTP / Binutils 主页网页查询分别未成功 / 超时，后续直接采用公告明确列出的 Sourceware 官方发布目录，没有改用未知镜像。

说明以下精确范围后，经本次执行权限确认完成三个 HTTPS 请求。复用已有 [fetch 方法](fetch-mpc-mpfr-inputs.py) 的 `fetch()`，调用前核对方法 5,126 bytes / SHA-256 `2feb632c6422198255c1f3d46b1be18be8914e2c22e67635ce6a106bb01beeab`，指定本批目录和固定目标；未修改旧方法。执行前计划保留在 `.tmp/binutils-inputs-20260925/fetch-plan.json`，`executed: false` 仅描述计划时点，实际获取以各请求日志为准。

| 对象与精确 URL | 上限 | 实际 bytes | SHA-256 |
| --- | ---: | ---: | --- |
| `https://sourceware.org/pipermail/binutils/2025-February/139195.html` | 256 KiB | 6,813 | `a982a9527d2373a9d29d5e12bb06fb40f55d0d5219ad45c48c1b01cf3d6dcf9f` |
| `https://sourceware.org/pub/binutils/releases/binutils-2.44.tar.gz` | 64 MiB | 51,342,242 | `0cdd76777a0dfd3dd3a63f215f030208ddb91c2361d2bcc02acec0f1c16b6a2e` |
| `https://sourceware.org/pub/binutils/releases/binutils-2.44.tar.gz.sig` | 64 KiB | 833 | `3f30d34757e8ead05682f067e501432ee045cc2fb8083a906e000c4ec49a07dd` |

请求使用 HTTPS / TLS ≥ 1.2、不跟随重定向、不自动重试；单项 60 秒、父进程 65 秒，批次正文上界 67,436,544 bytes。实际顺序为公告、签名、原包，15:00:48–15:01:03（Asia/Shanghai）全部完成，均为 curl 退出 0 / HTTP 200，无超时或重试。原包同时匹配公告 SHA-256 及固定配方 SHA-1 `568ba0a286cf79520572c1597a203c1aafd462de`。

三份 fetch 日志的 `passed` 仅表示有界传输成功，`index_and_recipe_bytes_match` 均为 `null`；摘要对应由后续离线入口独立检查。公告是 HTTPS 发布材料，配方 SHA-1 是原配方的字节对应线索，两者都没有被提升为已完成的公钥身份或密码学认证。

## 离线核对入口

[inspect-binutils-inputs.py](inspect-binutils-inputs.py) 只读取本地材料，生成[诊断记录](binutils-inputs-2026-09-25.json)：

- 核对执行前范围、原始 curl 命令、HTTP / 退出码 / 超时标记，以及正文、stdout、stderr 的长度 / SHA-256 和对应文本。
- 严格解析公告中唯一 `binutils-2.44.tar.gz` 摘要行，拒绝不同格式、`with-gold` 替代、缺失或重复行；原包匹配固定长度 / SHA-256。
- 重新读取已固定的 musl-cross-make 配方原始归档，按原有归档摘要检查入口取得对应 `.sha1` 声明，再与新原包 SHA-1 对应；不是仅接受复制到新脚本的常量。
- 复用已有分离签名结构读取器，保留其“未认证”标记；不调用 GnuPG、Docker、keyserver 或包内程序，不写宿主钥匙环。

```bash
python3 docs/records/rust-linux-input-review/inspect-binutils-inputs.py
python3 docs/records/rust-linux-input-review/check-binutils-inputs.py
python3 docs/records/rust-linux-input-review/check-mpc-mpfr-inputs.py
```

签名为带 CRC24 的 ASCII armor，解码后 566 bytes，单个 v4 / class `00` packet；声明算法为 RSA（1）/ SHA-256（8），完整 issuer 为 `3A24BC1E8FB409FA9F14371813FCEF89DD9E3C4F`，该字段位于 hashed area，声明创建时间为 `2025-02-02 12:27:34 UTC`。这些字段尚未由真实签名验证认证，不能仅凭 issuer 或算法字段判断签名有效。公钥身份、MPI 数学核验、撤销和到期均待检查，`source_acceptance` 保持 `not-assessed`。

## 本机留存与恢复

材料目录为 `artifacts/source-inputs/binutils-inputs-8a610c7-20260925/`，按 `inputs/` 和 `methods/` 保留原始请求材料、计划、诊断方法和结果；精确路径、每项读取上限与摘要见[留存清单和恢复结果](binutils-retention-2026-09-25.json)。共 **22 个文件、51,419,594 bytes**，另有目录内与 Git 中逐字节相同的 `manifest.json`。

原包超过旧 musl 小对象留存器的 16 MiB profile。本批保持旧方法和旧清单格式不变，使用其 `read_regular(path, limit)` 与排他写入 `write_new()` 原语，按本批表格上限先复制到新材料目录并读回，再从该材料目录读取、核对清单并恢复到 `.tmp/binutils-inputs-restore-from-store-20260925/`，每次写入后与输入字节比较。初次同步副本目录另保留在清单的 `initial_parallel_copy` 字段，不把从原目录同步复制当成从归档恢复。新清单是本批本地诊断记录，不是公共验收 schema，也不伪装成旧对象库。

从恢复目录重跑以下命令，输出与已留存诊断 JSON 逐字节一致；恢复路径不会改写原日志中的获取位置：

```bash
python3 docs/records/rust-linux-input-review/inspect-binutils-inputs.py \
  --directory /Users/luobo/Code/RadishAxiom/.tmp/binutils-inputs-restore-from-store-20260925/inputs
```

重跑仍依赖仓库内复用方法，以及既有固定配方归档 `.tmp/musl-cross-make-review-c38a1c1/musl-cross-make-3635262.tar.gz`；本批不是完整仓库或异盘备份。原包没有拆分入 Git，完整字节仍在项目忽略目录中；本次未更新 Downloads 备份、上传或清理旧材料。

## 后续顺位与验证边界

下一步补签名者公钥及身份依据，并开展有界内容 / 许可盘点，再形成精确离线验签切片。网页查询找到 [GNU 列表上的 Binutils 2.43 公告](https://lists.gnu.org/archive/html/info-gnu/2024-08/msg00001.html)所附 `OpenPGP_0x13FCEF89DD9E3C4F.asc`；其链接目标为 `https://lists.gnu.org/archive/html/info-gnu/2024-08/binqltbMeQqcS.bin`，本轮网页读取返回 cache miss，没有本地公钥字节。该历史附件目前只是待核对线索，短 ID 相同不能替代完整指纹、当前材料状态或自认证验证；不自动视为 2.44 的已接受身份。

新增 **5 项**合成检查覆盖精确文件名、不同压缩格式 / 签名后缀、缺失 / 重复公告项、编码 / 长度边界、原包篡改、公告摘要和配方不一致；既有 **18 项**归档 / 签名 / 获取边界回归通过。回归输出中的模拟超时是预期合成负例，不是本轮真实下载失败。

这批没有解压或检查原包内部内容，`archive_content_inspected` 与 `license_review_complete` 均为 `false`；未安装、构建、运行真实验签、Rust / CI 或产品测试，没有新增后台进程。公钥 / 许可证及来源接受分别补齐，不能把本批摘要一致或结构解析称为 `proved`。

`./scripts/check-repo.sh` 通过（1,192 个文件），`git diff --check` 通过。收尾仍为 `dev`，相对本地 `origin/dev` ahead 3，未刷新或推送远端。本次 MPC 决定同步与 Binutils 材料切片共 11 个文件留在工作区，未提交；原获取目录、同步副本、留存目录和实际恢复目录均保留。
