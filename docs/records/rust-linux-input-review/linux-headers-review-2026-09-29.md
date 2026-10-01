# Linux headers 4.19.88 全文件声明与制作过程审阅

日期：2026-09-29（Asia/Shanghai）

基线：`84bd6f8`，`dev`。

用途：在既有精确输入上缩小认证、制作过程和许可待补范围，供后续来源审阅使用。不包含法律结论、来源接受、实际构建 / 安装或新增网络取证结果。

## 输入与复核结果

继续使用[9 月 25 日留存批次](linux-headers-inputs-2026-09-25.md)，未替换 Rust 配方对象：

- Rust 镜像 `linux-headers-4.19.88.tar.xz`：1,052,880 bytes，SHA-256 `d3f3acf6d16bdb005d3f2589ade1df8eff2e1c537f92e6cd9222218ead882feb`。
- 候选 `sabotage-linux/kernel-headers` commit `fefadd9e4e093f776cd14ee3685a80eb4ca000f4` 归档：1,415,704 bytes，SHA-256 `e875ffc69332bb4a8776e29ba15659be3e27785762fc8c769d9d2f4cf002ff87`。归档中的 commit 字样仍是声明。
- 本机输入库 `artifacts/source-inputs/linux-headers-inputs-38edae0-20260925/` 的 38 路径 / 34 对象读回通过；manifest 为 9,393 bytes，SHA-256 `961ba896f42f9324e8349def7c50663efbbca325fe764f20eb734169b9aca8b3`。

新入口 [inspect-linux-headers-review.py](inspect-linux-headers-review.py)复用既有有界解压、逻辑路径 / 链接核对及投影方法，核对被留存的旧方法字节，重算两份成员盘点与比较结果，与旧完整报告一致。只在内存读取普通文件，没有把归档解出到文件系统，也没有运行上游脚本。

完整[逐文件报告](linux-headers-review-2026-09-29.json.gz)为 172,880 bytes，SHA-256 `8f7720f3e946dae47b1e1b44c0f46d1dccee37a7df45b6fb0c11ed1d22443623`。报告保留每项内容身份、SPDX 原始行及行号、`copyright` 字样行号、866 项 include 路径到普通源文件的映射和补丁 blob 观察。原始声明的解码为 UTF-8 / backslashreplace；不是 SPDX 表达式解析器或许可分类器。

## 全文件声明盘点

本轮读取每个普通文件的全部字节，补足旧方法仅查看前 4 KiB 的覆盖边界。计数是字面标记的有无，不把“无标记”解释为没有许可证，也不把“有标记”解释为已获可分发授权。

| 范围 | 普通文件 / 投影项 | 有 SPDX 标记 | 无 SPDX 标记 | 有 copyright 字样 |
| --- | --- | --- | --- | --- |
| Rust 镜像普通文件 | 1,188 | 944 | 244 | 446 |
| 候选归档普通文件 | 1,191 | 944 | 247 | 446 |
| AArch64 include 投影 | 866 | 769 | 97 | 384 |

866 项投影对应 866 个唯一普通源文件；候选投影逐项一致。769 项标记中，758 项声明包含 `Linux-syscall-note` 字样，另 11 项的声明不含该字样：

| 声明原文 | include 路径 |
| --- | --- |
| `GPL-2.0` | `asm/bpf_perf_event.h`、`linux/bpfilter.h`、`linux/ipmi_bmc.h`、`linux/vmcore.h`、`sound/skl-tplg-interface.h` |
| `GPL-2.0+` | `linux/usb/g_uvc.h` |
| `MIT` | `linux/batman_adv.h`、`linux/vbox_err.h` |
| `BSD-3-Clause` | `linux/qemu_fw_cfg.h` |
| `(GPL-2.0 OR CDDL-1.0)` | `linux/vbox_vmmdev_types.h`、`linux/vboxguest.h` |

97 项无标记路径逐项保留在报告中，包括 `drm/` 文件、架构转发头及 `linux/version.h`；需要继续阅读实际声明和对应来源，不能一概按空文件、自动生成文件或统一例外处理。报告也保留了 AND / OR、`Linux-OpenIB`、不同 GPL / LGPL 版本的原样声明，未合并为一个许可证。

下一批许可材料应围绕精确 4.19.88 来源补齐：原 kernel 对应的许可正文和例外正文、上游文件到导出文件的映射、上述未带 syscall 字样 / 无 SPDX 文件的完整声明、sabotage 改动与制作工具的归属及授权。当前两份归档没有独立 `COPYING` / `LICENSE` / `LICENCE` 普通文件；不能从别的 kernel 版本搬一份许可就宣称闭合，也不能把 syscall 例外自动套到所有文件。产品分发与生成用户程序的边界仍按项目许可专题另行审阅。

## 制作过程的具体缺口

以下均为留存 `selected-review-texts.json` 与归档源码的静态阅读；没有执行 shell、Git clone、make、patch 或编译器。

| 环节 | 脚本实际行为 | 尚缺材料 |
| --- | --- | --- |
| 原 kernel 导出 | `UPDATE.sh` 要求先做 `make allnoconfig` / `make headers_install_all`，从 `$1/usr/include` 复制公共及架构目录 | 精确 kernel tree、配置、导出工具 / 环境及日志；版本宏只声明 4.19.88 |
| 额外输入 | 同一脚本另行 `cd ../linux` 并调用 `scripts/headers_install.sh`，补 `a.out.h`、`kvm.h`、`kvm_para.h`、`module.h` | 该相邻 tree 是否等于传入 `$1`，以及补出文件的精确来源；不能只锁一个参数路径就视为输入完整 |
| sabotage 修改 | README 声称修复 musl / userspace 兼容；`patches/` 有五份补丁 | 更新脚本没有应用这些补丁；还缺原始导出内容到最终文件的完整修改链，包括 `libc-compat.h` |
| 发布打包 | `create-dist.sh` 从当前本机仓库 clone；`VER` 由环境给定，`git checkout v$VER` 行被注释；删除 `.git`、`.gitignore`、`docs` 和根目录 `*.sh` 后 tar / xz | 实际 clone 到的提交、打包工作树、环境、工具身份和产物日志；删除三个根脚本与所见成员差异相容，但不能据此证明该包由此脚本产生 |
| 消费安装 | Makefile 的五层 `.h` 匹配通过 `tools/install.sh -D -m 644` 安装，允许 `config.mak` / 命令行覆盖 | 消费时精确配置和实际安装结果；本轮只重算固定默认规则下的路径投影 |

`test.sh` 依赖外部 `CC`（默认 `cc`），失败分支打印 `FAIL`，未形成整批失败累积规则；不能仅以它最终退出成功作为所有头文件兼容验收。该脚本未运行，也未修改。

## 五份补丁的有限内容观察

本轮计算目标普通文件的 Git blob SHA-1，与补丁声明的七位 after 前缀比较。用途仅为定位版本关联，不构成来源认证或完整补丁重放。

| 补丁 | 目标 | 声明 after 前缀 | 当前目标比较 |
| --- | --- | --- | --- |
| 0001 | `generic/include/linux/stat.h` | `8b6831c` | 匹配 |
| 0002 | `generic/include/linux/kernel.h` | `cf999da` | 匹配 |
| 0003 | `generic/include/linux/tcp.h` | `fa6836e` | 不匹配；当前为 `f3224da…` |
| 0004 | `generic/include/linux/time.h` | `6246e9c` | 匹配 |
| 0005 | `generic/include/linux/tcp.h` | `f3224da` | 匹配 |

0003 与 0005 指向同一文件，但 0005 的 before 声明为 `0e4bd0c`，不等于 0003 的 after `fa6836e`。因此不能将这五份文件描述为已重放、完整且连续的补丁链；也不能把中间版本不匹配直接判为最终文件损坏。需要补出中间修改及原始输入，才能判断链路。

## 已准备、尚未执行的认证取证

下一步先取得精确 tag ref 与固定 commit 元数据，判断是轻量 tag 还是附注 tag、是否提供签名材料，以及 commit / tree / parent 的声明关系。现有 tags 页面和 codeload PAX 不足以给出这些结论。

两个固定 HTTPS GET 目标：

1. `https://api.github.com/repos/sabotage-linux/kernel-headers/git/ref/tags/v4.19.88`，正文上限 64 KiB。
2. `https://api.github.com/repos/sabotage-linux/kernel-headers/git/commits/fefadd9e4e093f776cd14ee3685a80eb4ca000f4`，正文上限 256 KiB。

入口 [fetch-linux-headers-git-metadata.py](fetch-linux-headers-git-metadata.py)复用现有获取方法；[固定计划](linux-headers-git-metadata-plan-2026-09-29.json)为 1,331 bytes，SHA-256 `d5748231caec0f62fdd3e3dd0eb220a413dbcf6378e7033d4126bba37c26d6d9`。

精确执行范围：每项一次、无重定向、无自动重试、不使用凭据、不追踪响应给出的 URL；每项 curl 60 秒 / 父进程 65 秒，总调用上限约 130 秒，正文合计上限 320 KiB。写入仅限 `.tmp/linux-headers-git-metadata-84bd6f8-20260929/` 的计划、正文与日志，随后将必要原始材料、方法和报告纳入既有本机留存体系。请求会把公开 URL 及网络连接信息发送给 GitHub，不写远程仓库、不装依赖或启动服务。进程有界退出；失败材料保留，不覆盖旧批次；留存恢复核对前不删除原始材料。

当前未发起这两个请求。取得当前任务明确授权后，先以排他创建方式建立上述新目录并保存与仓库内计划逐字一致的 `fetch-plan.json`，再运行：

```bash
python3 docs/records/rust-linux-input-review/fetch-linux-headers-git-metadata.py --execute-authorized
```

若 ref 指向新 tag 对象、返回不同 commit、接口失败或响应缺少原始签名材料，保留事实并停止自动扩张；不自动下载 tag 对象、完整仓库或 kernel 原包。即使 GitHub `verification` 声明有效，也不能替代独立验签、签名者绑定和项目所有者对精确来源声明的决定。制作过程、许可和实际安装缺口不因这两个请求成功而解除。

## 本轮验证与交接

新增 11 项合成检查通过：全文扫描超过旧 4 KiB 前缀、多标记计数、无标记 / 非 UTF-8 / 大小边界、补丁前缀匹配和不匹配、缺失 / 多目标拒绝、精确请求范围和计划漂移拒绝。既有 headers 19 项、MPC / MPFR 输入 18 项、musl-cross-make 8 项、留存 7 项检查通过，合计 63 项；完整报告离线重算与上述 gzip 逐字节一致，请求计划与当前方法一致，不需重新下载。

```bash
python3 docs/records/rust-linux-input-review/check-linux-headers-review.py
python3 docs/records/rust-linux-input-review/check-linux-headers.py
python3 docs/records/rust-linux-input-review/inspect-linux-headers-review.py --output /private/tmp/radishaxiom-linux-headers-review-replay-20260929.json.gz
```

输出采用排他创建；重放使用新的精确路径，不覆盖已有结果。新报告只保存诊断元数据，第三方完整内容仍在原本机输入库中；没有形成异盘备份。

仓库检查首次因本文日期行的两个尾随空格失败（退出码 1），移除后复跑通过，检查 1,306 个文件；`git diff --check` 通过。没有放宽文本检查。新源码 / 文档均为普通文件、模式 0644；工作区只含本轮九个路径，尚未提交，`dev` 相对本地 `origin/dev` 记录领先三个提交，未刷新远端状态。

本轮没有新增网络请求、外部验签、容器、依赖安装、上游程序执行、产品安装或推送；未运行 Rust 测试 / CI。headers 来源仍未接受，完整 source lock 与实际构建 / 安装仍阻断。
