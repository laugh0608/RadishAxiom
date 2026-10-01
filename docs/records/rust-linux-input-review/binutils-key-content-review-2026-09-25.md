# Binutils 2.44 公钥材料与有界内容盘点

用途：记录固定原包的后续材料获取、逻辑归档盘点及自认证缺口，供来源审阅和离线复核。本文不是来源接受决定、完整许可证结论、公共 Evidence 或安装授权。

## 范围与实际获取

项目所有者要求“提交工作区更改，继续推进下一步”。原工作区已提交为 `e854595`；本批承接[原包材料](binutils-inputs-2026-09-25.md)，没有更换 `binutils-2.44.tar.gz` 或修改已有验签方法。

本次说明精确目标、每项 256 KiB 上限、单请求 60 秒 / 父进程 65 秒、最多三项请求及本地留存影响后，经执行权限确认取得下列材料。2026-09-25 15:12:22–15:12:28（Asia/Shanghai）三项均 HTTP 200 / curl 0，无重试、重定向或超时。复用原 `fetch-mpc-mpfr-inputs.py`，方法身份与此前记录相同；获取前计划及原始 stdout / stderr 均保留。计划的 `executed: false` 只描述执行前时点。

| 材料 | bytes | SHA-256 |
| --- | ---: | --- |
| [GNU 2.43 公告](https://lists.gnu.org/archive/html/info-gnu/2024-08/msg00001.html) | 8,635 | `b1616e492295e19766a513db72c70161dc5824242f97520c8f7c02225163c1c1` |
| [GNU 2.44 公告](https://lists.gnu.org/archive/html/info-gnu/2025-02/msg00001.html) | 8,097 | `0b57fae29d7dc924d40a584fc42a3ed05658ffd6b8402761512282490c936af5` |
| [2.43 公告公钥附件](https://lists.gnu.org/archive/html/info-gnu/2024-08/binqltbMeQqcS.bin) | 3,106 | `2cad260c1b933559858ef82943b72049af96426138a99c299f63fabda2a305b4` |

请求公钥前已从取得的 2.43 公告解析并核对附件完整 URL。2.44 公告仍列出固定原包的 SHA-256；这些仅是 HTTPS 获取及文本对应，不是身份认证或密码学验签。

## 公钥结果与停止线

[核对入口](inspect-binutils-key-inputs.py)复核精确请求、日志、原文、公告链接、完整指纹和声明字段；[导出](binutils-key-inputs-2026-09-25.json)保留全部观察。

- 主钥 `3A24BC1E8FB409FA9F14371813FCEF89DD9E3C4F` 与原包签名声明的完整指纹一致；唯一 UID 文本为 `Nick Clifton (Chief Binutils Maintainer) <nickc@redhat.com>`，尚未认证。
- 共 5 个 OpenPGP 包，包含一把 RSA 主钥、一把 RSA 子钥、一个 UID 及两份签名。子钥指纹为 `DB07E960FE6E5D284CE41E4C141E0FE3342C4914`。
- UID 自认证候选（class `0x13`）和子钥绑定候选（class `0x18`）**均声明 SHA-1**（digest algorithm `2`）。两者声明创建 epoch 均为 `1505745349`；未声明钥 / 签名到期，不等于当前有效。
- 材料内未解析出吊销声明，不代表外部不存在吊销。公钥包结构、声明自签和完整指纹对应，不能替代自签真值及发布者身份核对。

因此现有附件不能满足本项目既有强摘要自认证前置。原包签名自身声明 SHA-256 也不能补上公钥认证缺口。本批没有运行 GnuPG，不能把结果写成“真实验签失败”；没有启用弱摘要兼容、修改时钟或接受旧钥认证。

后续优先寻找同一完整指纹、含可接受强摘要自认证的更新材料，并重新核对发布者绑定。历史网页检索只补到 2018 年邮件中的同指纹线索，未取得更新公钥，不能据此断言更新材料不存在。如转向其他归档来源，须另行审阅其对这份精确 `.gz` 字节的认证链；已有 MPC / musl 的限定决定不自动适用于 Binutils，不用 Debian `.xz` 或 `with-gold` 变体替换。

## 有界内容与许可观察

[内容入口](inspect-binutils-content.py)只读取已固定原包，逐项计算成员摘要，不解压到目录、不执行上游程序。上限为压缩输入 64 MiB、完整展开 tar 512 MiB、单成员 32 MiB、100,000 个成员、单份选读文本 2 MiB；拒绝重复 / 越界路径、链接、特殊或稀疏成员、带数据目录、文件充当祖先目录、截断 / CRC 错误、拼接 gzip 和非零 tar 尾部。

[完整压缩库存](binutils-content-2026-09-25.json.gz)含逐文件路径、类型、模式、所有者、长度和 SHA-256；[摘要](binutils-content-summary-2026-09-25.json)只汇总该库存。库存以 CLI 的排序 JSON 加末尾换行、`gzip.compress(..., mtime=0)` 生成，不手改。摘要由同一报告去除 `members` / `implicit_directories`，另计算两者数量、唯一排序的所有者 / 模式及压缩库存身份；本次已重算逐字节一致。

- 固定原包 51,342,242 bytes，SHA-256 `0cdd76777a0dfd3dd3a63f215f030208ddb91c2361d2bcc02acec0f1c16b6a2e`。
- 完整 tar 317,317,120 bytes，SHA-256 `9628a14839e0f16a0aa63bdf0d53b1b28d67b54bbab3e81f6e615be552a18ed1`。
- **28,449 个普通文件、0 个显式目录条目、314 个隐含祖先目录**；所有者均 `(0, 0)`，模式为 `0644` / `0755`。固定 `bfd/version.m4` 声明 `2.44`。
- 库存 1,378,903 bytes，SHA-256 `0fc3ea4031b22c15f9f293ee7eba1018c0e8d619825a627932b3cb26a1e8e0ee`。

首次方法错误地要求显式根目录条目，退出 1，报 `missing archive root`，没有产出库存。该方法原文（SHA-256 `8624d9fa221816fd4cf139a155b0bbb8ead19d85ffb73515e1479c1af20c6bc9`）、错误日志和失败记录均留存。修正仅涉及本批新逻辑盘点器：tar 文件可通过成员路径隐含目录，故完整记录这些路径，同时拒绝真实文件与祖先目录冲突。合成回归覆盖这两种情况；修正后真实盘点退出 0。未修改已有 Rust 产品 USTAR 规则，`physical_tar_profile_verified` 仍为 `false`。

从 11 份选读文件观察到：根 `COPYING` / `COPYING3` 为 GPL v2 / v3 文本，`COPYING.LIB` 为 GNU Library GPL v2，`COPYING3.LIB` 为 LGPL v3，`libiberty/COPYING.LIB` 为 LGPL v2.1；`include/ansidecl.h` 头部声明 GPL v2 或后续版本。三个工具手册入口声明 GFDL v1.3 或后续版本，无 Invariant Sections、Front-Cover Texts、Back-Cover Texts。这里只记录文本内容，不能由根目录许可文件推导每个文件、产物或再分发方案已获完整审阅；`license_review_complete` 仍为 `false`。

## 留存与离线复核

复用未修改的小对象留存器，本批增量均低于其每文件 16 MiB 限制，没有切分原包绕过上限。[清单](binutils-review-retention-manifest-2026-09-25.json)列出 **38 个路径 / 32 个唯一对象，共 1,523,012 bytes**；包含原始三项获取、计划、失败 / 成功日志、初版失败方法、最终方法及解析依赖、合成检查和导出。

本机存储为 `artifacts/source-inputs/binutils-review-e854595-20260925/`，已从存储恢复到 `.tmp/binutils-review-restore-20260925/`，全部对象和路径逐字节一致。51 MiB 原包仍在此前 `artifacts/source-inputs/binutils-inputs-8a610c7-20260925/inputs/`，本批不重复存储。使用清单核对过的工作区方法读取恢复公钥输入，并从前一留存目录读取原包重新盘点；公钥导出、完整压缩库存和摘要全部重算一致，详见[恢复结果](binutils-review-retention-2026-09-25.json)。这证明本机留存 / 恢复与诊断可重放，不代表异盘备份、全项目 source lock 或全新宿主可复现。

```bash
python3 docs/records/rust-linux-input-review/inspect-binutils-key-inputs.py \
  --directory .tmp/binutils-review-restore-20260925/.tmp/binutils-key-inputs-20260925
python3 docs/records/rust-linux-input-review/inspect-binutils-content.py \
  --archive artifacts/source-inputs/binutils-inputs-8a610c7-20260925/inputs/binutils-attempt-1.tar.gz \
  --output .tmp/binutils-content-replay-new.json.gz
```

输出路径必须尚不存在；原始 curl 参数中的绝对路径保持历史记录，公钥核对仍在原项目根运行。

## 验证与交接

内容 13 项、公钥页面 4 项、公钥包解析回归 9 项，共 **26 项通过**。本批未运行 Docker / GnuPG、Rust / CI、构建或安装；原包来源接受仍为 `not-assessed`，不升级为 `checked` / `proved`。三个已说明的 HTTPS 请求是本批外部动作，未推送、发布或改写系统配置，没有新增长期进程。

```bash
python3 docs/records/rust-linux-input-review/check-binutils-content.py
python3 docs/records/rust-linux-input-review/check-binutils-key-inputs.py
python3 docs/records/rust-linux-input-review/check-mpc-mpfr-key-inputs.py
./scripts/check-repo.sh
git diff --check
```

仓库检查通过（1,202 个文件），差异卫生检查通过；诊断测试尚未接入默认仓库门禁。

本批新增实现、导出及文档留在工作区；`dev` 相对未刷新的本地 `origin/dev` ahead 4。原始目录、失败材料、留存及恢复目录均保留。
