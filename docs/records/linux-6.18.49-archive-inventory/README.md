# Linux 6.18.49 源码归档盘点

日期：2026-09-06；基线 `ee7b0a0`。用途：留存版本化只读盘点入口的实际输出、失败与修正，以及缺失构建包的精确候选。读者为源码、构建与 runtime 维护者。本记录不接受公共格式、builder 或源码许可证闭包，不授权安装、构建或产品执行。

## 结果与材料

输入为[前次核验](../linux-6.18.49-source-review/README.md)已下载的同一 Linux `6.18.49` 压缩源包；本轮重新核对压缩摘要，未重新下载或验签。

| 项目 | 实际观察 |
| --- | --- |
| 未压缩 tar | 1,610,598,400 bytes；SHA-256 `e1ff34affa6a24460d47dbad47d60ff971b88a18c06841554664358313d5026c` |
| 归档条目 | 6,048 个目录、91,120 个普通文件、85 个符号链接；无 hardlink |
| 普通文件内容 | 总计 1,537,369,970 bytes；每个文件均保留长度与 SHA-256 |
| 链接 | 85 个目标均存在并位于同一归档根内；拒绝循环、逃逸或穿越非目录 |
| 权限 | 实际为 `0664`、`0775`、`0777`（symlink）；数值 owner / group 均为 0 |
| 扩展元数据 | 1 个 global PAX `comment`；值为 `1c732c6b94f0faee1526bd375add2fe10cba2e26` |
| 许可证材料 | 34 个按 `LICENSES/` 或许可证文件名选取的普通文件，保留长度 / 摘要；每文件前 8 KiB 共扫描到 75,970 个 SPDX 原始声明 |

摘要、链接和许可证文件表见 [summary.json](summary.json)。完整逐文件库存及 SPDX 原始扫描输出以 [inventory.json.gz](inventory.json.gz)留存，压缩后约 5 MiB；解压后的 JSON 为 42,275,109 bytes，原始与压缩字节摘要均在 summary。压缩只用于留存，不是新的来源输入或产品 payload。该文件是自有检查器生成的元数据，不包含源码文件正文。

PAX comment 与 [kernel stable 镜像的 Linux 6.18.y 页面](https://kernel.googlesource.com/pub/scm/linux/kernel/git/stable/linux-stable.git/+/refs/heads/linux-6.18.y)本轮显示的 `Linux 6.18.49` commit 一致。它是已核验签名 tar 内的来源声明；未取得并验证 stable tag 原始签名，也未逐文件重建 Git tree，不能把网页对应写成完整 Git 来源证明。[Git archive 文档](https://git-scm.com/docs/git-archive)说明 commit ID 的 PAX 存放方式。

SPDX 扫描保留原始标记文本，包含可能的注释结束符或示例；没有解析 SPDX 表达式、检查全文件所有声明或决定产品分发义务。34 个文件的库存也不代表源码只有 34 个需要审阅的许可对象。

## 版本化与拒绝边界

[inspect-source-tar-v1.py](../../../scripts/inspect-source-tar-v1.py)输出独立的 `radishaxiom-source-tar-inventory` / `format_version = "1"`，明确标为 `diagnostic-observation` / `not-assessed`，只接受 `linux-6.18.49-source` 与已固定压缩摘要。它不是现行 toolchain inspection v0.1 的新 profile，现有 acceptance consumer 不应消费此输出。

旧 [inspect-toolchain-tar.py](../../../scripts/inspect-toolchain-tar.py)、现有生成器及历史 contracts 保持字节不变。新入口使用标准库 `lzma` 的受限单流解码和 `tarfile.TarInfo` 的 header 校验，再单独处理受限物理 PAX header、文件内容和链接图；不调用 `extract` / `extractall` 或源码脚本。旧入口主要收集工具包布局，直接调用或复制其完整实现既不能覆盖新边界，也会耦合历史验收，因此未修改或抽取旧方法。

实际限制为：压缩输入 256 MiB、tar 流 2 GiB、单文件 32 MiB、200,000 个成员及最多同数扩展、单扩展 16 KiB、路径 4 KiB、XZ decoder 128 MiB、链接跳转 40 次。程序逐文件计算摘要，拒绝截断、未知扩展、重复路径、危险类型 / 权限、坏 checksum、非零尾随数据和拼接 XZ；开始和解码完成均检查压缩摘要。限制不等于整个 Python 进程的 OS 内存 / 墙钟硬限制，更不是产品 guest 的 128 MiB 配额。

## 失败与修正

首跑退出 1，stdout 为零字节；[原 stderr](attempt-1.stderr.txt)指出根目录权限不符。初版把 regular / directory 限制为近似二进制包的 `0644/0755`，而实际源码根目录为 `0775`。核对 Git `tar.umask` 默认 `0002` 与原 header 后，源码 profile 记录 `0664/0775`，继续拒绝普通文件 / 目录的 world-write、setuid / setgid、非零数值 owner / group 和设备文件。盘点不把权限应用到文件系统；将来展开仍须单独审阅策略。

第二次盘点通过；补充物理 USTAR 标识与目录尾随斜杠校验后最终重跑也通过，两次来源派生字段一致，方法摘要不同。首跑方法可从当前方法副本应用 [attempt-1-method.patch](attempt-1-method.patch)恢复；summary 绑定其 SHA-256。首跑失败不是源包损坏，修正也没有改写源包、签名或既有验收拒绝规则。

## 重跑与核对

使用宿主现有 Python `3.14.5` 完成只读盘点；精确版本和方法摘要保留在输出。未引入依赖、启动容器或 VM、修改系统配置，也未执行编译。此 Python / 标准库尚未形成产品工具 acceptance，属于本次诊断的信任边界。

在仓库根执行的最终命令：

```bash
python3 scripts/inspect-source-tar-v1.py --profile linux-6.18.49-source \
  .tmp/linux-6.18.49-source-review-dc4de70/linux-6.18.49.tar.xz \
  > .tmp/linux-6.18.49-inventory-ee7b0a0/inventory-final.json \
  2> .tmp/linux-6.18.49-inventory-ee7b0a0/inventory-final.stderr
```

留存压缩使用 Python `gzip.compress(raw_json, compresslevel=9, mtime=0)`。重跑先核对方法摘要与 Python 版本，再比较原始 JSON；另一 Python 版本产生的 gzip header 差异应与解压后的 JSON 差异分别判断。失败时不可把重定向创建的空文件作为有效记录。

[合成检查](../../../scripts/check-source-tar-inventory.py)覆盖正常内容摘要、PAX 长路径、路径别名 / 逃逸、重复路径、链接祖先 / 逃逸 / 循环、设备 / 权限、版本 / 布局、截断 / 尾随内容、资源上限及 CLI 失败无成功输出。

```bash
python3 scripts/check-source-tar-inventory.py
./scripts/check-repo.sh
git diff --check
```

## 精确构建输入候选

[builder-package-candidates.json](builder-package-candidates.json)记录 Debian 官方 arm64 页面、源包入口、copyright 来源、发布者长度 / SHA-256 及与前次镜像库存的关系。三项候选合计 1,670,120 bytes，尚未下载或安装：

| 包 | arm64 binary 版本 | source 版本 | 直接依赖观察 |
| --- | --- | --- | --- |
| [flex](https://packages.debian.org/bookworm/flex) | `2.6.4-8.2` | `2.6.4-8.2` | debconf、libc6、m4 已出现在镜像库存 |
| [bison](https://packages.debian.org/bookworm/bison) | `2:3.8.2+dfsg-1+b1` | `2:3.8.2+dfsg-1` | libc6、m4 已出现在镜像库存；保留 epoch 与 binary rebuild 差异 |
| [bc](https://packages.debian.org/bookworm/bc) | `1.07.1-3` | `1.07.1-3` | libc6、libreadline8 已出现在镜像库存 |

这只是依赖元数据比较，未运行包管理器求解；不能声称安装一定只增加三项。正式取得材料时先核对签名 `InRelease` / `Release` → `Packages` / `Sources` → 对应 `.deb` / `.dsc` 与 source archives，再审阅 maintainer scripts 和精确依赖闭包。网页 SHA-256 不替代 [apt-secure](https://manpages.debian.org/bookworm/apt/apt-secure.8.en.html) 的来源链；已有 keyring 包的存在也不等于完成了签名验证。不要自动安装 recommends、升级已有包或执行系统级 apt。

三个包的许可细分见 candidates 中的 Debian copyright 来源；其中构建生成器本体与嵌入生成结果的材料分别审阅。Linux Rust `1.97.1` 优先沿用现有 registry 的 GNU arm64 standalone 入口，发布者摘要与 payload 尚未取得；musl target std / CRT / linker 也不由 GNU host 包自动覆盖。本轮没有增加工具登记或决定 init 依赖。

下一步验收上述包索引与来源链、Rust Linux 工具材料，并完成 kernel 许可 / stable tag 对应审阅，再安排获准的隔离构建。当前状态以[项目状态](../../status/current.md)为准。
