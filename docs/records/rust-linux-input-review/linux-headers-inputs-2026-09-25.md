# Linux headers 4.19.88 制品与重打包源码核对

日期：2026-09-25（Asia/Shanghai）；基线：`38edae0`。

用途：记录固定 Rust 配方的 headers 制品、上游标签线索、逐成员比较与 AArch64 安装路径观察，供下一轮来源和执行方案审阅。不包含上游签名验证、实际重打包 / 安装、完整许可审查或产品验收。

## 本批结论

- 取得 Rust 配方指定的 `linux-headers-4.19.88.tar.xz`，1,052,880 bytes，SHA-256 `d3f3acf6d16bdb005d3f2589ade1df8eff2e1c537f92e6cd9222218ead882feb`，匹配固定配方 SHA-1 `de12b9c8ae2de9e85056a36be9f0fcc0a1e4abe9`。没有换成 `-1` / `-2`、其他镜像制品或完整 kernel 原包。
- 原包有 1,343 个逻辑成员：1,188 个普通文件、69 个目录、86 个符号链接。符号链接仅在内存命名空间中解析，未提取到文件系统，未修改生产归档规则。
- GitHub 首批标签元数据声明 `v4.19.88` 对应 commit `fefadd9e4e093f776cd14ee3685a80eb4ca000f4`。经另一项精确请求授权取得该 commit 的源码归档，与镜像包共有路径的内容、类型、链接目标一致；三个仅在源码归档中的根目录脚本符合其打包脚本的删除规则。模式与 owner / mtime 不同，整包不等价，来源尚未认证。
- 两者在既定五层路径深度内的 AArch64 `.h` 路径、源文件及摘要投影均为 866 项且相同。这是内存路径诊断，未运行 Makefile、安装脚本、编译器或上游测试。

完整导出见 [gzip JSON](linux-headers-inputs-2026-09-25.json.gz)，可读统计见 [摘要](linux-headers-summary-2026-09-25.json)。状态仍为 `source_acceptance: not-assessed`、`license_review_complete: false`。来源接受、真实安装和完整 source lock 不能由本批内容对应替代。

## 三个精确请求

第一批先展示并获准两个对象，随后依据返回的标签声明，单独展示并获准固定 commit 归档。各请求一次，curl 退出 0 / HTTP 200；每项 60 秒、父进程 65 秒，不重试、跳转或自动追踪远端返回 URL。

| 对象 | 精确 URL | 原始字节 / SHA-256 |
| --- | --- | --- |
| Rust 镜像制品 | `https://ci-mirrors.rust-lang.org/rustc/sabotage-linux-tarballs/linux-headers-4.19.88.tar.xz` | 1,052,880 / `d3f3acf6d16bdb005d3f2589ade1df8eff2e1c537f92e6cd9222218ead882feb` |
| 标签第一页 | `https://api.github.com/repos/sabotage-linux/kernel-headers/tags?per_page=100` | 9,809 / `188e3bc305d86b6d42db63ba0d2da1aa43b78f43494a40e0e5c01ece76b636bd` |
| 上游固定 commit | `https://codeload.github.com/sabotage-linux/kernel-headers/tar.gz/fefadd9e4e093f776cd14ee3685a80eb4ca000f4` | 1,415,704 / `e875ffc69332bb4a8776e29ba15659be3e27785762fc8c769d9d2f4cf002ff87` |

两个归档各限 4 MiB，标签正文限 256 KiB。获取方法分别为 [初始入口](fetch-linux-headers-inputs.py)与[固定候选入口](fetch-linux-headers-candidate.py)，复用原有 curl 方法，历史方法未改写。原始计划、正文、stdout、stderr、调用参数、工具身份与时间在 `.tmp/linux-headers-inputs-38edae0-20260925/` 并已另存。没有写系统目录、修改 lockfile 或留下后台进程。

API 本次返回 19 个条目；仅按完整 tag 名选出唯一目标，没有宣称穷尽历史。前期网页工具读取该 tag / release 页面及 API 未成功，不据此判定对象不存在；实际独立请求随后成功。API 声明、归档顶层目录与 PAX comment 均不是 Git 对象重建或签名证明。

## 归档与重打包比较

[新内容方法](inspect-linux-headers-content.py)复用旧有界解压与路径规范，单独处理 headers 的符号链接；不放宽旧版只允许普通文件 / 目录的盘点器。范围为压缩 4 MiB、tar 32 MiB、单成员 8 MiB、5,000 成员、XZ 解码内存 128 MiB、路径 / 链接目标 4,096 bytes、每次解析最多 64 次链接跳转。

普通文件记录摘要与元数据，符号链接记录原目标及内存解析终点。拒绝逃逸、绝对 / 非法链接目标、悬空、循环、超跳数、通过普通文件继续遍历、在物理链接下嵌入成员、hardlink / sparse / 特殊成员、重复路径、目录负载及非零 tar 尾部。父目录必须显式存在。生产物理 tar profile 仍未验证。

| 比较项 | 镜像制品 | 固定 commit 候选 |
| --- | --- | --- |
| tar 长度 | 6,260,736 | 6,266,880 |
| tar SHA-256 | `768a1078918618287f2b836480ac6e7d39fda2f38b8b95e4bbe644097f00880a` | `74527d5e6fffe9be7ce74e007a61cc49771a46de888b613fd6a57cf0d1d899d5` |
| 普通文件 / 目录 / 符号链接 | 1,188 / 69 / 86 | 1,191 / 69 / 86 |
| 独有路径 | 无 | `UPDATE.sh`、`create-dist.sh`、`test.sh` |

去掉各自顶层目录名后，共有路径的文件内容、长度、成员类型、链接目标没有差异；1,257 路径的模式不同，全部 1,343 个共有路径的 owner 或 mtime 至少一项不同。比较保留这些差异，不将忽略元数据后的内容对应写成整包认证或可重复构建。

固定候选的 `create-dist.sh` 声明：克隆本地仓库，删除 `.git` / `.gitignore` / `docs` 和根目录 `*.sh`，再 tar / xz 打包。三个额外脚本与该规则相符；但脚本的 tag checkout 行被注释，`VER` 来自环境，未记录本次制品实际执行时的工作树 / 工具身份。因此只能报告“与这套规则相符”，不能证明实际由该 commit 生成。

`UPDATE.sh` 从外部 kernel tree 的导出目录复制通用及架构头文件，并创建相对链接；它依赖外部 kernel tree、预先运行的 headers 导出及其他目录。README 的添加架构示例仍引用 4.4.2。没有取得本次 4.19.88 重打包的原始 kernel 身份、制作日志、完整补丁应用记录或可重跑的固定环境；本批未执行这些脚本。

## Rust 配方到 AArch64 头文件的静态对应

[输入诊断](inspect-linux-headers-inputs.py)重新扫描已有固定 musl-cross-make 原包，直接读取 Makefile、litecross/Makefile 与精确 headers SHA-1 文件；另读取此前与 Rust 源包绑定的 `musl-toolchain.sh` 原字节，其 SHA-256 为 `faae0de27e4ca1661a030ce3623e4959f34f5d1b6f795ea9b5b84c10c2086b2e`。该脚本从已留存全文观察中取得，与[旧源码诊断](source-recipes-2026-09-10.json)中的身份一致；本批没有重扫 242 MiB 的 Rust 完整源码包。

- Rust 有效赋值仍覆盖 `LINUX_VER=headers-4.19.88` 与上述 Rust 镜像站点；不是 musl-cross-make 的 `headers-4.19.88-2` 默认值。
- litecross 将 `aarch64` 映射为 `arm64`，从 `arch/*` 选架构，调用 `headers_install`。该制品中的 `arch/arm64` 解析为 `arm64`；其 `include` 下的链接连接到通用头目录。
- headers Makefile 在五层 glob 范围中选 `.h`，安装规则声明模式 644。内存投影只模拟该深度内可达的非隐藏 `.h` 路径，并核对候选与镜像的路径 / 摘要相同；不声称实际 make 求值、环境覆盖、shell、工具和安装副作用已验收。
- `generic/include/linux/version.h` 的 `LINUX_VERSION_CODE` 为 `267096`，即 4.19.88 的数值声明。它不证明头文件未经修改，也不是本项目未来 guest kernel 的版本选择。

该原包还带五个 patch 文件，涉及 kernel.h / sysinfo、stat、tcphdr、time 与 TCP_NLA 定义。它们已逐字读取并绑定，但尚未对有认证身份的原 Linux 输入重放，不能从补丁文件存在推断每个补丁已被正确应用。

## 许可材料边界

镜像与候选均没有 basename 含 COPYING / LICENSE / LICENCE 的普通许可材料。诊断逐文件记录前 4 KiB 内的原样 SPDX 声明；其中包括 `GPL-2.0 WITH Linux-syscall-note`，也存在 MIT、BSD、LGPL、GPL / CDDL 选择及组合条款。这个文字库存不是完整许可分类或覆盖证明。

已读的 `arm64/include/asm/unistd.h` 与 `generic/include/linux/libc-compat.h` 带 Linux syscall-note 声明，但不能据此把整个归档、脚本和补丁统一标为同一许可。需继续取得与精确输入关联的许可正文、归属及制作过程材料，再核对实际使用 / 分发集合。没有更改项目许可证策略，也没有认定这些缺口已经构成具体法律违规。

## 留存与验证

[清单](linux-headers-retention-manifest-2026-09-25.json)覆盖 38 路径、34 个去重对象、3,619,821 bytes，包括三个新请求及计划 / 日志、完整两个归档、固定 musl-cross-make、此前已绑定的 Rust 脚本、旧来源记录、选定文本、诊断及方法 / 测试。复用既有 16 MiB 单对象 / 128 MiB 总量的留存器，未放宽限制。

- 存储：`artifacts/source-inputs/linux-headers-inputs-38edae0-20260925/`。
- 恢复：`.tmp/linux-headers-restore-20260925/`。
- [结果](linux-headers-retention-2026-09-25.json)：38 路径身份一致；工作区方法身份核对后，读取恢复副本重算完整导出、摘要与选定文本，全部一致。本批不包含完整 Rust source 原包，所需脚本文本及旧绑定记录已留存；不声称重做 Rust 源包验收或完成异盘备份。

重算入口如下，输出文件须尚不存在；可用 `--directory`、`--recipe` 指向恢复副本：

```bash
python3 docs/records/rust-linux-input-review/inspect-linux-headers-inputs.py \
  --output .tmp/linux-headers-replay.json.gz --summary .tmp/linux-headers-summary-replay.json
```

新增 [19 项检查](check-linux-headers.py)，复用解压 / 签名 / 请求 18 项、固定配方 8 项、留存 7 项，共 **52 项通过**。覆盖链接组件先解析再处理 `..`、逃逸 / 悬空 / 循环 / 上限、物理父目录、五层投影、内容与元数据差异及请求计划漂移。仓库检查与 `git diff --check` 通过。未重跑 Rust / CI、密码学工具、原包脚本、上游构建 / 测试或安装。

下一步先整理 GMP 到期 / 撤销及验证时点的受限验签方案；headers 后续补强认证、精确 kernel 输入到重打包的过程与许可材料。GCC / Binutils 缺口仍保留，不以本轮内容对应绕过完整 source lock 的前置。
