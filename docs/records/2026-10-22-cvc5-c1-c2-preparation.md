# C1 缺口与 C2 离线准备验收

日期：2026-10-22。基线 `dev` / `26e8855`，启动时工作区干净，相对本地 `origin/dev` 无 ahead / behind；未查询远端。用途：记录本批输入接受审阅、精确获取清单和离线检查的实际结果；下一步骤与操作边界见[输入准备专题](../query/solver-cvc5-input-preparation.md)，本记录不授权下载、工具执行或构建。

## 交付与未完成部分

项目所有者授权按 C1 → 获取清单 → 可离线完成的 C2 推进，要求下载、安装、构建或真实执行前说明精确范围并确认。本批全程离线，只读取既有材料、编写自有检查器并进行本机文件 / 文本验证。

| 项目 | 实际交付 | 保留边界 |
| --- | --- | --- |
| C1 接受缺口 | LibPoly 六份精确文件与原 inventory 对照；Release 历史日期 / 有效期字段；既有 keyring 字节读回与旧签名目标区分；SDK copyright 按用途的核对出口 | 不裁定声明冲突已经解决，不接受新信任或工具；C1 仍未通过 |
| 精确获取计划 | [acquisition-plan.json](solver-cvc5-c1-2026-10-22/acquisition-plan.json)列 172 二进制包 / 328 去重源文件，共 691,605,464 bytes；URL、SHA-256、大小、归属、留存位置与停止条件齐全 | 来源仍是未认证索引声明；没有实际 SDK 原包摘要，没有新下载或自动授权 |
| C2 原包核对 | [准备入口](../../scripts/cvc5-build-preparation.py)复用 C0 检查 / SDK 选择，生成与核对计划，并逐文件流式重核原包；拒绝缺失、额外项、路径问题、特殊文件和错摘要 | 无网络、解包、安装或执行模式；完整原包一致不等于签名 / 许可接受 |
| C2 配置前预检 | [输入预检](../../scripts/check-cvc5-build-inputs.py)消费现有 patch 私有格式，核对 manifest / closure / headers / archives / Editline 顺序和真实字节 | 不产生真实 manifest 或接受标记，不运行 CMake，不证明 ABI、工具来源或静态链接闭包；完整 C2 未完成 |

计划与检查代码是当前任务的新文件；旧 C0 记录、Production / patch 字节、四依赖 / cvc5 原归档、Rust / Cargo、IR / Evidence / query / P4 公共格式均未改动。新增机器记录为私有版本 `0.1`，不作为产品 Evidence 或公共 acceptance schema。

## C1 核对的具体事实

LibPoly 固定归档中 `debian/copyright:8,10` 为 `GPL-3+`，第 12 行为 Lesser 正文；原文件 SHA-256 `cd3eb8b96019760e240235847501addff027f870ffe57687c4128ec78a155664` 保持。根 `LICENCE`、`include/poly.h`、顶层 / src / include 三份 CMake 文件均从原 tree 清单重算一致。顶层直接进入 src / include 及条件 Python / tests；这个源码层面的定位不能消除 `Files: *` 声明冲突或代替未来实际链接输入核对。限定用途接受或针对该版本的权威澄清仍待决定；没有修改第三方许可文本。

固定 Release 正文为 2023-06-10、Debian 12.0、bookworm，没有 `Valid-Until`。这是缺少该字段的事实，不能描述为已发生 Release 到期，也不提供最新状态保证。此前成功签名诊断的 InRelease SHA-256 为 `77737fa4b34f2693e982cc9ee35736816c35a7778fc2d326cc1bbf5b301fe1aa`，与本次固定原字节不同。

从[历史记录](linux-builder-source-chain/release-verification.json)解码 55,918 bytes 公钥环，重算 SHA-256 与原记录的 `506b815cbb32d9b6066b4a2aa524071e071761e7e7f68c3ac74f3061ba852017` 一致；未导出到系统 keyring、执行公钥工具或验签。后续 [GnuPG 2.4.7 环境](rust-linux-input-review/musl-verifier-smoke-execution-2026-09-12.md)提供复用候选，不迁移历史任务的信任或执行授权。SDK 闭包本身没有 keyring 包；本批没有为此另造一套工具链或追加下载。

获取清单为现有 SDK 选择的投影，不重新决定根包或依赖。原 SDK 独立检查器从留存原始元数据再次导出同一 172 包、474 条关系、101 源版本与 328 源文件，声明大小分别为 120,870,556 和 570,734,908 bytes。现有 29 份来源观察、五原归档与全部留存展开项也重核通过；这些都是内容 / 记录一致性检查，不是认证或构建验收。

## 实际验证

[本批机器记录](solver-cvc5-c1-2026-10-22/validation.json)保留四条新入口命令、退出码与日志身份；本机完整 stdout / stderr 位于 `.tmp/cvc5-c1-c2-validation-2026-10-22/`。新增代码与原数据共同构成可重跑入口，不以日志摘要替代输入。

| 实际执行 | 结果与范围 |
| --- | --- |
| `python3 scripts/test-cvc5-build-preparation.py` | 47 项通过；包含十种获取清单篡改子例、固定选择投影、历史目标区分、缺失 / 截断 / 同长度篡改 / 额外文件 / symlink / FIFO、闭合字段、版本 / ABI 声明、closure 错序绑定、头文件与各项预算拒绝 |
| `python3 scripts/cvc5-build-preparation.py verify` | 500 项计划与当前输入重建一致，保持待确认和不可构建；生成计划会复用原 C0 检查器并重核 SDK 元数据 |
| `audit-archives --directory` 指向本批新建空目录 | 实际退出 2；完整报告 500 个缺失文件、0 个匹配项、`build_ready=false`，不产生部分成功接受 |
| 构建输入预检指向本批不存在的 manifest | 实际退出 2，明确文件不存在；未调用 CMake 或生成占位 manifest |
| `python3 scripts/check-cvc5-c0-input-selection.py` | 旧 v0.3 输入 / 29 观察、五源码、Production / patch 绑定一致，接受边界不变 |
| `python3 scripts/check-cvc5-c0-sdk-independent.py` | 原始元数据独立派生集合一致，无冲突 / Breaks；保留 `signature_verified=false` |
| `python3 scripts/cvc5-c0-source-inputs.py verify` | 五份原归档、物理 tar 清单与所有展开项重核通过 |
| `./scripts/check-repo.sh` | 仓库检查通过，2,809 文件；文档链接、既有契约与生成检查没有因本批入口增加而放宽 |
| `git diff --check` 与新增文件逐字节文本卫生核对 | 通过；新增自有文件无 BOM / CRLF / 尾随空白，均在文件大小与路径预算内 |

合成正例刻意使用非 ELF 的合成 `.a` 内容；它只证明预检对声明字节与绑定的处理，输出仍为 `abi_verified=false`、`tool_acceptance=not-accepted`。实际 CMake 执行、`.pc --static`、SDK 内容、密码学验签、目标编译和链接没有验证；没有运行 Rust / 跨平台测试、CI、solver、探针或 Docker。自有 Python 检查与测试不是 Linux 工具执行。

## 交接与下一确认

下一外部动作限于[专题中的 500 文件原包获取](../query/solver-cvc5-input-preparation.md#精确获取范围与首错停止)：新建唯一批次目录，固定快照、约 660 MiB 正文、预计 15–45 分钟 / 90 分钟停止，首个错误停并保留，无安装、解包、环境组装、构建或真实载荷执行。必须先由项目所有者确认；本批尚未请求网络或新系统权限。

收口后工作区留存本批未提交改动，无暂存、提交或 push；没有后台服务。测试临时文件由测试自身清理，本批验证空目录与日志保留；真实获取目录尚未创建。C1 未接受、完整 C2 / E0 / E4 / E5 未通过，原容量、旧字节、1 MiB 输入与 128 MiB / 6 s 运行限制保持。

后续：项目所有者随后确认这批下载与字节核对；实际首错停止、六项取得和剩余 494 项见[获取接续](2026-10-22-cvc5-c1-acquisition.md)。上文“未下载 / 待确认”保留准备阶段事实，不用于描述后续运行结果。
