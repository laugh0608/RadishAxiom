# GCC 9.4.0 公钥与有界内容盘点

日期：2026-09-25（Asia/Shanghai）。基线：`50ef87c`。

用途：记录本批两个公开请求、主钥 / 签名子钥诊断、精确原包的逻辑成员及选定许可文本盘点。供下一轮来源审阅与离线重放使用；不构成真实验签、来源接受、完整许可证审查、安装或产品构建验收。

## 结果与停止线

- [上一批精确原包](gcc-inputs-2026-09-25.md)的压缩字节身份不变。完整扫描得到 94,646 个逻辑成员：4,806 个目录、89,840 个普通文件，没有链接、稀疏或特殊成员；逐文件记录内容 SHA-256。
- GCC [官方身份页面](https://gcc.gnu.org/mirrors.html)列出的 `7F74F97C103468EE5D750B583AB00996FC26A641` 与原包分离签名声明一致，但该指纹实际是签名子钥。其主钥为 `13975A70E63C361C73AE69EF6EEB81F8981C74C7`。页面身份仍是待审阅的 HTTPS 输入，不是密码学身份证明。
- GNU 钥环和 Ubuntu 材料的该子钥绑定包体一致，绑定声明使用 SHA-1，嵌入的反向认证声明也使用 SHA-1。原包签名的 SHA-256 声明不能替代这两项认证。没有取得可进入既有强摘要执行路径的完整认证链；GCC 来源保持未接受。
- 本批没有执行 GnuPG、导入钥环、安装依赖或运行原包中的程序。下一步先补可独立推进的 GMP / headers 材料；GCC 与 Binutils 缺口继续阻断完整 source lock。改变认证规则、验收对象或接受更弱信任输入需要另行具体审阅，不由本记录授权。

## 获取范围与原始材料

执行前展示了两个固定目标及副作用，并通过本任务执行授权完成。入口为 [fetch-gcc-key-inputs.py](fetch-gcc-key-inputs.py)，复用原有 [有界请求方法](fetch-mpc-mpfr-inputs.py)，不改动历史方法。

| 对象 | 精确入口 | 结果 / 原始字节 |
| --- | --- | --- |
| 身份页 | `https://gcc.gnu.org/mirrors.html` | HTTP 200，5,173 bytes；SHA-256 `7235342adb022666828ad687490b18008a9206ad024a01b88e20807c22d6425b` |
| 公钥 | `https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x7F74F97C103468EE5D750B583AB00996FC26A641` | HTTP 200，23,601 bytes；SHA-256 `4862f6aac833d841e2af4eb875919940133965888a00e18fbd175e752fb71b6b` |

两项均为单次请求，curl 退出 0；每项上限 256 KiB、60 秒，父进程 65 秒，无重试、跳转、系统钥环导入。实际本地时间 16:15:12–16:15:16。原文、stdout、stderr、调用参数、工具 / 方法身份与时间均在 `.tmp/gcc-key-content-50ef87c-20260925/`，持久留存见下文。公开材料只用于本机诊断与留存；原包、完整公钥和页面原文不加入 Git。

另复用[此前取得的 GNU 官方钥环](binutils-key-refresh-2026-09-25.md)，未再次联网：3,687,794 bytes，SHA-256 `b136fbe57ade4ee5270ca66c402cae7b50349fd07646b5b3de7962d58d4df608`。按真实主钥选择后得到 7,947 bytes 公共包，SHA-256 `ccc9d767efb358d914e4e58acefed8d10fc06db4243ec4a920d52bee4025bf7b`；本地 trust 包仅记录偏移 / 摘要后排除，不导入其信任。

## 主钥、子钥与历史诊断

取钥计划沿用了 `expected_primary` 字段名，事前将签名指纹当作主钥。实际取钥请求按完整指纹查找，取得包含目标子钥的主钥块；原计划、方法与请求日志保持原样，诊断显式记录 `historical_expected_primary_is_actually_subkey: true`。

[新公钥诊断](inspect-gcc-key-inputs.py)复现并保留三项失败：

1. 在 GNU 钥环按签名指纹选主钥：`target primary absent`。这不代表 GNU 钥环没有该子钥；按正确主钥重新定位后存在。
2. 旧盘点器按该签名指纹检查 Ubuntu 主钥：`expected primary key absent`。
3. 改用真实主钥后，旧 v4-only 盘点器遇到 v3 签名：`unsupported signature version`。

新诊断复用现有封包、指纹与 v4 字段读取方法。非 v4 签名只记录版本 / 包体身份并标记语义未检查；不放宽旧盘点器或强摘要验签规则。完整结果见 [公钥导出](gcc-key-inputs-2026-09-25.json)。

| 材料 | 公钥 / UID | v4 签名 | 不透明签名 | 声明为主钥自签的 v4 摘要计数 |
| --- | --- | --- | --- | --- |
| GNU 钥环所选块 | 1 主钥、3 子钥 / 6 UID | 36 | 1 个 v3 | 10 个，均为算法 2（SHA-1） |
| Ubuntu 返回块 | 1 主钥、3 子钥 / 6 UID | 67 | 1 个 v3 | 19 个，均为算法 2（SHA-1） |

两份材料的目标子钥 class `0x18` 绑定声明包体 SHA-256 均为 `325c28101667b794083431f8a1e943edf5835ef995a60d3cf9aca2abcac52aa2`；绑定内 unhashed 区的 class `0x19` 反向认证包体 SHA-256 均为 `7069c31cc577cc282647be045d21a4e4a0f82834ff36d2bf7c94c4e2188e8bda`。以上仅为字段与字节比较，未校验签名值。

Ubuntu 另有三个 class `0x30` UID 认证撤销声明，关联两个旧 UID；不能据此写成“整个主钥已撤销”，也不能忽略它们推定公钥当前有效。没有验证有效期、撤销的密码学真实性、最新性或所有签名语义。

## 原包与许可文本范围

[内容诊断](inspect-gcc-content.py)复用既有 XZ 有界解码与路径规则，建立 GCC 专用的较窄资源上限，不改变历史 Rust / Binutils 方法：压缩 96 MiB、完整 tar 1 GiB、单成员 32 MiB、200,000 成员、选定文本每项 2 MiB、XZ 解码内存 256 MiB、路径 4,096 bytes。只在内存流中读取，不提取到目录或执行。

完整展开流为 716,871,680 bytes，SHA-256 `b71fea8421126610b2bd211b9b732220c62e91debf768704bad86a9802013ce2`；最大普通文件 7,056,957 bytes，没有隐含父目录。拒绝路径逃逸、重复路径、文件作为父目录、目录负载、链接 / 稀疏 / 特殊成员、非零 tar 尾部，以及 XZ 截断、校验错误、串接或尾随数据。这是逻辑 tar 盘点，不是生产物理 tar profile 验收。

完整成员清单见 [gzip JSON](gcc-content-2026-09-25.json.gz)，摘要与选定文件身份见 [内容摘要](gcc-content-summary-2026-09-25.json)。`gcc/BASE-VER` 为 `9.4.0`、`gcc/DATESTAMP` 为 `20210601`、`gcc/DEV-PHASE` 为空。

读取了 20 项选定文本，以下仅报告文件自身的声明：

- 根目录含 GPL v2 / v3、LGPL v2.1 / v3 文本及 `COPYING.RUNTIME` 的 GCC Runtime Library Exception 3.1。
- `gcc/version.c` 声明 GPL v3 或后续版本；`libgcc/libgcc2.c`、`libstdc++-v3/libsupc++/new`、`libatomic/libatomic_i.h`、`libgomp/libgomp.h` 的头部声明 GPL v3 或后续版本及 Runtime Library Exception 3.1。
- `libsanitizer/LICENSE.TXT` 声明 Illinois/NCSA 与 MIT 双许可；`libgo/LICENSE` 是三条款许可文本；`libquadmath/COPYING.LIB` 是 LGPL v2.1 文本。
- `README` 明确提醒手册和部分运行库条款不同。文件名含 COPYING / LICENSE / COPYRIGHT 的候选为 29 项，其中也含脚本名等假阳性；不能将这个名称筛选当成完整许可清单。
- `contrib/download_prerequisites` 含独立下载逻辑及不同版本依赖声明。本批只读其文本，没有运行；后续仍以固定构建配方中的精确输入为对象。

这些观察不推定所有文件采用同一许可证，不确定实际构建 / 嵌入 / 最终链接集合，也不判定产物满足运行库例外条件。完整许可与最终分发审查保持未完成。

## 留存、复现与验证

[留存清单](gcc-key-content-retention-manifest-2026-09-25.json)覆盖 39 路径、35 个去重对象、8,761,821 bytes；包括两个请求原文 / 日志、GNU 钥环与既有请求记录、分离签名、选定文本、机器导出、方法和测试。复用既有 16 MiB 单对象 / 128 MiB 总量的留存方法，没有调整限制。

- 存储：`artifacts/source-inputs/gcc-key-content-50ef87c-20260925/`。
- 恢复：`.tmp/gcc-key-content-restore-20260925/`。
- 大原包不重复装入本批对象库，精确依赖写入清单 `external_required_inputs`；原包及失败半包仍在[上一批留存](gcc-retention-manifest-2026-09-25.json)。本批重算使用上一批已经恢复的完整原包。
- [实际结果](gcc-key-content-retention-2026-09-25.json)：39 路径恢复摘要一致；用工作区中已核对身份的方法读取恢复后的公钥 / GNU 钥环 / 签名，完整公钥导出一致；重算原包完整清单、摘要与选定文本均一致。单独搬走本批对象库不足以重放大原包盘点，必须同时保存清单指明的上一批材料。

原始缓存存在时，重算入口如下；输出路径必须尚不存在：

```bash
python3 docs/records/rust-linux-input-review/inspect-gcc-key-inputs.py
python3 docs/records/rust-linux-input-review/inspect-gcc-content.py \
  --output .tmp/gcc-content-replay.json.gz --summary .tmp/gcc-content-summary-replay.json
```

公钥诊断支持显式 `--directory`、`--ring`、`--signature`，内容诊断支持 `--archive`，可指向恢复副本；请求日志中的原始执行路径按历史计划比较，不改写成恢复路径。

实际检查：新公钥 7 项、新内容 13 项，复用 GNU 选择 10 项、旧公钥盘点 9 项、留存 7 项，共 **46 项通过**。三项历史窄 profile 拒绝路径按预期重现，不计为真实密码学失败。仓库级检查和 `git diff --check` 通过；没有重跑 Rust / CI、GnuPG、容器或产品构建。本机留存不是异盘备份验证，两个网络请求未留下后台进程。
