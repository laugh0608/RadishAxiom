# GCC 9.4.0 精确原包、摘要与签名材料

用途：供后续 GCC 来源审阅者核对取得的精确字节、首次下载超时、单独授权的恢复及离线复核。本文不是来源接受、许可证验收、构建或安装结果。

## 范围与实际获取

项目所有者要求提交并继续推进。此前 Binutils 其他取钥 / Debian 候选切片已提交为 `dac0405`，提交前仓库 1,215 文件及差异检查通过，提交后工作区干净。依当前顺位，本批推进固定 musl-cross-make 配方的 `gcc-9.4.0.tar.xz`，Binutils 阻断继续保留。

[GCC 官方 9.4.0 目录](https://gcc.gnu.org/pub/gcc/releases/gcc-9.4.0/)列出精确原包、分离签名与 `sha512.sum`。官方 [GCC 9 系列页](https://gcc.gnu.org/gcc-9/)注明该系列已不再支持；本次仍按固定配方核对，不升级或据此声称版本安全。网页工具未能读取 `sha512.sum`，后续有界实际获取成功，不能混淆两者。

说明四个精确目标、原包 96 MiB 上限、小文件上限、每项 60 秒 / 父进程 65 秒及本地留存影响后，经执行权限确认发起首批请求。所有请求 HTTPS / TLS ≥ 1.2，不跟随重定向、不自动重试。复用未修改的 [fetch 方法](fetch-mpc-mpfr-inputs.py)，SHA-256 `2feb632c6422198255c1f3d46b1be18be8914e2c22e67635ce6a106bb01beeab`。

以下名称均相对上述官方目录；精确命令、URL、时间、工具身份与 stdout / stderr 见[诊断导出](gcc-inputs-2026-09-25.json)。

| 对象 | 上限 | bytes | SHA-256 |
| --- | ---: | ---: | --- |
| 目录页 | 256 KiB | 1,985 | `e2d6d8617b7503b72c0878aafd1846c3ef071426a8e5ab2af96cd0b23cac993e` |
| `sha512.sum` | 64 KiB | 596 | `75253b34f1ba6c41e236a74d82ee257de131f145f53412a2054f56d81dd6eef4` |
| `gcc-9.4.0.tar.xz.sig` | 64 KiB | 310 | `764f191a8679cf7269dd73a5b313d5597b28424dd7c74a82d43570ba5da0eced` |
| 原包首次下载的**不完整字节** | 96 MiB | 56,872,510 | `60fb27083ee63e77274a3e45bd649b097344c6b74fe641b97e18b5a33ce68a32` |
| 第二次取得的完整原包 | 96 MiB | 72,411,232 | `c95da32f440378d7751dd95533186f7fc05ceb4fb65eb5b85234e6299eb9838e` |

前三项均 HTTP 200 / curl 0。原包首次请求于 2026-09-25 **15:59:59–16:00:59（Asia/Shanghai）**执行，curl 28，在 60 秒期限结束；HTTP 200 并不代表正文完整。stderr 明确报告收到 56,872,510 / 72,411,232 bytes，`passed` 为 `false`，未将部分文件当作原包。

## 单独授权的恢复

保留首次失败后，另行说明并获执行权限确认：只对同一原包 URL 完整重取一次，上限仍为 96 MiB，将时限改为 180 秒 / 父进程 185 秒，写入 `gcc-attempt-2.*`，不覆盖、续传或拼接首次字节。此次执行为 **16:02:28–16:03:37**，HTTP 200 / curl 0，无父进程超时。

[专用恢复入口](fetch-gcc-archive-recovery.py)先核对首次 curl 28、失败状态及部分字节身份，再排他创建第二次文件；已存在第二次任何产物时拒绝重复运行。它没有修改旧获取方法或其 60 秒规则，没有无限重试、镜像切换、隐式取钥、解压或安装。执行前计划保留在原目录 `recovery-plan.json`，`executed: false` 仅为计划时点；真实请求以各日志为准。恢复方法 SHA-256 为 `fa4e57c143b6a71928c4fe78c3e39c79bd86e3765c659dabdae974a3b39d92f3`。

## 字节对应与签名声明

[离线核对入口](inspect-gcc-inputs.py)严格复核五次请求的参数、结果和原字节；对目录页解析精确 `.xz` / `.sig` / 清单链接，对摘要清单要求唯一且完整的四个 9.4.0 文件名，拒绝重复、缺失、其他版本或格式替换。完整原包与签名分别匹配清单中的 SHA-512：

- 原包：`dfd3500bf21784b8351a522d53463cf362ede66b0bc302edf350bb44e94418497a8b4b797b6af8ca9b2eeb746b3b115d9c3698381b989546e9151b4496415624`。
- 签名：`714d6aec5d2019ecb12311bd400caa21848a29310279d673482e0b622fb27b36548f636e7c6dc876bff9b9e869e84ba71d6ce50350cbb47c1b042015ebaf45ee`。

方法另读取固定 `musl-cross-make-3635262` 原归档中的 `hashes/gcc-9.4.0.tar.xz.sha1`，与取得原包的 `bf6d6480fb32e5a28dac849449f533a84d4e6547` 对应。SHA-1 只用于配方字节对应，不作为强认证；本机摘要及 HTTPS 清单一致也不自动成为发布者密码学认证。

分离签名为一个二进制 OpenPGP v4 / class `0x00` 包，声明 RSA / SHA-256，创建时间 `2021-06-01T08:18:34Z`；散列区含完整 issuer 指纹 **`7F74F97C103468EE5D750B583AB00996FC26A641`**。原始签名数学值尚未验证，`cryptography_executed`、`public_key_identity_accepted` 和 `signature_mpis_verified` 均为 `false`。

[GCC 官方镜像说明](https://gcc.gnu.org/mirrors.html)的网页查询列出同一完整指纹，标注 Richard Guenther。该页本批未作为带本地获取日志的身份输入留存，也未取得 / 审阅该公钥；它只是后续精确身份路线，不是当前身份接受结论。

## 留存与复核

[留存清单](gcc-retention-manifest-2026-09-25.json)涵盖 **36 个文件、129,607,458 bytes**，包含首次不完整原包、第二次完整原包、三个小对象、全部请求 / 计划、诊断 / 恢复方法及回归、固定配方归档和方法依赖。存储为 `artifacts/source-inputs/gcc-inputs-dac0405-20260925/`，布局为 `files/<原项目相对路径>`。

两个原包对象超过旧 CAS 的 16 MiB 单文件 profile。本批沿已用的大对象留存方式，使用未修改的 `read_regular(path, limit)` 与 `write_new()`，按清单对这两个精确文件使用 96 MiB 上限，其他文件沿原上限，排他复制并读回；没有改旧 CAS 上限或拆文件绕过规则。

已从存储恢复到 `.tmp/gcc-inputs-restore-20260925/`，36 个文件逐字节一致。使用清单核对过的工作区方法读取恢复输入，完整诊断与导出逐字节一致，详见[恢复结果](gcc-retention-2026-09-25.json)。核对器仍在原项目根运行并读取已固定的配方路径；不声称全新宿主复现、全项目 source lock 或异盘备份。

```bash
python3 docs/records/rust-linux-input-review/inspect-gcc-inputs.py \
  --directory .tmp/gcc-inputs-restore-20260925/.tmp/gcc-inputs-dac0405-20260925
python3 docs/records/rust-linux-input-review/check-gcc-inputs.py
python3 docs/records/rust-linux-input-review/check-mpc-mpfr-inputs.py
./scripts/check-repo.sh
git diff --check
```

新增摘要 / 链接 / 恢复边界 9 项、既有获取 / 签名 / 原包解析回归 18 项，共 **27 项通过**。恢复用例使用合成文件及 mock 子进程，不发起网络请求；实际两次原包请求另见上述日志。

`./scripts/check-repo.sh` 通过（1,222 个文件），`git diff --check` 通过；七个新增文件的 UTF-8 / 换行 / `0644` 权限检查通过，36 个留存输入的长度与 SHA-256 无漂移。

本轮没有解压或盘点 GCC 包内内容，许可、发布者公钥身份 / 自认证、真实验签与来源接受仍待补；未运行 GnuPG、Rust / CI、构建或安装。下一步先取得 / 核对完整指纹的身份与公钥材料，并制定有界内容盘点；不把网页姓名、完整指纹对应或 SHA-512 匹配称为 `proved`。

本批新方法、导出和文档未提交；`dev` 相对未刷新的本地 `origin/dev` ahead 7，未推送。没有新增长期进程；原始目录、首次失败文件、本机留存与恢复目录全部保留。
