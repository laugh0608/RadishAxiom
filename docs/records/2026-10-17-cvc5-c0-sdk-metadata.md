# D3 C0 固定快照 SDK 元数据复核

日期：2026-10-17（Asia/Shanghai）。用途：记录 F2 提交后、固定 Debian 快照的 SDK 元数据选择及独立复核；读者为项目所有者、实施者和后续输入验收者。本文不接受 SDK、包内容、构建配置、许可证、CLI 或运行资格。

## 授权与提交基线

项目所有者要求先提交本批 F2 实现与验收材料，再继续闭合 D3 C0，并明确允许联网取得固定快照的 Release / Packages / Sources 元数据，补齐 SDK 精确版本与依赖闭包；禁止下载依赖包、安装、构建、运行探针或 solver、修改系统配置及 push。主代理主持设计与验收，具体获取、解析、集成及独立审查委派 `gpt-6.1-sol / high`。

启动时 `dev` 位于 `1a7ff38`、相对本地 `origin/dev` ahead 4，工作区有前批已验收的 43 份 F2 / C0 文件。再次核对 32 份源码 / 脚本与前批验收清单字节一致，暂存前后 `git diff --check` 均通过。精确路径提交为 **`bf197ad` — `feat(solver): 实现 F2 原生监督源码与离线验收`**，包含前批 C0 草案及其验收引用；提交后工作区干净，ahead 5。没有刷新远端、修改用户身份或添加协作者署名。

前批 441 项 workspace 测试、3 项文档测试、Clippy / 格式 / 仓库检查结果见[F2 验收](2026-10-17-solver-f2-validation.md)。本轮 SDK 元数据工作不修改 Rust 实现、Cargo、query / P4 字节或运行资源限值。

## 本轮设计边界

唯一来源是 Debian `20230612T000000Z` 快照的 `bookworm/main`，目标为 `arm64` / `all`。网络入口只允许 Release / InRelease 与二进制、源码索引；只保留元数据原字节，不取得 `.deb`、`.dsc` 或源码归档，不调用 apt 或执行包内程序。网络读取预算为原计划 28 MiB、每项最多 180 秒、零重试、零备用源。

SDK 选择以既定 16 组角色为根，加上固定索引中的 Essential 包；完整处理 `Depends` / `Pre-Depends`、版本约束、替代项、Provides 与冲突检查。每个选定二进制包关联精确 Source 名称 / 版本及 Sources 声明的文件、大小和摘要。包级闭包仅针对已选角色，不替代完整 cvc5 源码才能确定的生成器 imports、包内文件、`.pc --static`、ELF 运行依赖或实际链接清单。

Release 对索引的摘要一致性与签名信任分别报告。索引中声明的包 SHA-256 / Size 不填入未取得包的实际 raw digest / bytes；元数据解析成功不升级工具、来源、许可或执行接受状态。

## 实际结果与验收

四份元数据原字节合计 **18,722,419 bytes**。Release 为 Debian 12.0 / bookworm，声明日期 `Sat, 10 Jun 2023 08:51:17 UTC`；原文件仍保留于 `.tmp/cvc5-c0-sdk-metadata-2026-10-17`，完整请求、返回路径、时间和摘要见[元数据观察](solver-cvc5-c0-2026-10-17/metadata-observations.json)。

| 元数据 | 实际 bytes | 实际 SHA-256 |
| --- | --- | --- |
| Release | 145,119 | `010b226303e531b2ca0d268079228b6667418b8ad021d6c126374837ad327055` |
| InRelease | 146,972 | `2814476b311085e250ddfdee295907bac45afb66f40dc7c1b35ab41a447c1d6c` |
| main/binary-arm64/Packages.xz | 8,801,860 | `4926bbf128b8e497cb83c59c8212fd2ef4df5b2c30e9140a688198cd2cd55471` |
| main/source/Sources.xz | 9,628,468 | `d1d5103c4ddd76196acc292e90fd0ffece1fe0d04408ab544633f25568e6cb19` |

Packages / Sources 解压后分别为 49,240,269 / 50,170,234 bytes；索引分别有 62,557 个二进制包记录和 34,337 个源码记录。每项有界单 stream XZ 解压，拒绝截断、尾部、额外 stream 或超限；没有执行其中任何内容。

[SDK 精确清单](solver-cvc5-c0-2026-10-17/sdk-selection.json)包含 16 组角色的 **51 个根包**，加上 **23 个 Essential** 包并闭合全部 Depends / Pre-Depends 后，共 **170 个包、472 条依赖边**，其中 12 个子句包含替代项。实际两个 `:any` 依赖都指向声明 `Multi-Arch: allowed` 的 Perl。已选包之间未发现 Conflicts / Breaks 矛盾；20 个包的二进制版本与对应 Source 版本不同，17 个二进制包版本含 epoch，均按实际字段处理，没有抹去 binNMU / epoch。

对应源码固定为 **99 个精确版本、321 个去重文件声明**；`Built-Using` / `Static-Built-Using` 已检查，本次选中包没有额外声明。二进制包声明大小合计 **120,455,832 bytes**，对应源码文件声明大小合计 **567,050,311 bytes**，分别低于原 512 MiB / 1 GiB 计划上限。上述包和源码均未下载，实际包 bytes / raw digest 仍为 null。

GCC / G++ 固定为 `12.2.0-14`，Binutils 为 `2.40-2`，glibc 为 `2.36-9`，Linux UAPI 包为 `6.1.27-1`；其余主要版本与兼容差异见[C0 专题](../query/solver-cvc5-c0-input-selection.md)。这不补证原 Ubuntu / GCC 11 CLI，也不接受新编译器或运行库。Essential 闭包包含 usrmerge、PAM / login、procps / util-linux、Perl 等，未来组装及 maintainer scripts 的副作用尚未审阅，不能把包清单当安装计划。

## 失败、修正与实际检查

1. 沙盒首次联网返回权限错误；同一命令提权后，快照服务返回同域内容地址。本地守卫先后拒绝 `/file/<40hex>/Release` 与索引的 `/file/<40hex>/<Release 声明 SHA-256>` 两种跳转，均在读取该文件正文前停止。主代理确认限定目标后，只继续已捕获 Location，不重发初始请求或切换来源。历史失败 manifest 原字节保留，完整成功清单另嵌入前序事实；路径中的 SHA-1 只作为内容定位核对，不视为签名认证。
2. 一次子代理提权请求等待 277 秒后被主代理中断，没有返回执行会话或网络输出；随后由主代理执行，事实见[执行历史](solver-cvc5-c0-2026-10-17/metadata-execution-history.json)。这不是用户拒绝，也没有据此声称远端 HTTP 失败。当前脚本摘要只绑定离线验证器 / 生成器；执行下载时未保存脚本摘要，不能事后把当前源码说成历史 fetch 版本。
3. 首次真实解析因全索引中 `librust-winapi-dev` 的 Provides 达 75,639 bytes / 1,603 项，触发原 64 KiB / 1,024 项限制。经主审后将**元数据字段解析**限额设为 128 KiB / 2,048 项并补拒绝测试，完整解析而不跳过该包。原网络、包 / 源码预算和 solver 的运行限值均未改变。原错误及实际最大值保留于本地 `resolver-first-failure.json`。

生产选择复核器从原字节重建，明确只报告一致性；[独立检查器](../../scripts/check-cvc5-c0-sdk-independent.py)不导入生产模块、根表、关系解析器或版本比较器，独立抄录已审根包，重新派生包集并逐字段 / 逐边核对。它同时检查原元数据摘要、Release / InRelease 关系、HTTP 内容定位链、Source 与 Built-Using 关联、声明大小总和及未接受状态；不是来源认证或形式证明。[独立结果](solver-cvc5-c0-2026-10-17/independent-check.json)保存输入摘要、检查器摘要、实际计数及未覆盖项。

主代理重跑元数据、SDK 重建、输入选择及独立复核入口，均通过；独立输出与归档结果逐字节相同。四组测试分别为 **32 / 33 / 19 / 12 项，共 96 项通过**；独立 12 项由主代理使用 `python3 -O` 运行，确认不依赖可被优化关闭的 `assert`，包括真实记录删边、Source 版本错误、源码摘要篡改及伪造 ready 的拒绝。[机器验收结果](solver-cvc5-c0-2026-10-17/validation-results.json)记录命令结果、9 份自有源码 / 测试、5 份结果文件和本地日志摘要。

相对 `bf197ad` 的 crates、Cargo、contracts 与 rust-toolchain 无任何差异，旧 query / P4 字节、容量和资源限值保持。本轮只执行 Python 离线解析、合成 / 篡改测试和仓库检查，不重复未改动的 Rust 验证；前批 F2 结果按提交基线保留。仓库检查与 `git diff --check` 通过；最终工作区为 `dev` ahead 5，暂存区为空，新 C0 元数据工作未提交，未 push，没有长期进程。

可复跑的离线入口（必须仍有原 `.tmp` 材料，缺失即失败）：

```text
python3 scripts/cvc5-c0-sdk-metadata.py metadata-verify
python3 scripts/cvc5-c0-sdk-selection.py verify
python3 scripts/check-cvc5-c0-input-selection.py
python3 scripts/check-cvc5-c0-sdk-independent.py
python3 scripts/test-cvc5-c0-sdk-metadata.py
python3 scripts/test-cvc5-c0-sdk-selection.py
python3 scripts/test-cvc5-c0-input-selection.py
python3 scripts/test-cvc5-c0-sdk-independent.py
./scripts/check-repo.sh
git diff --check
```

输入记录升级为私有 v0.2，旧 v0.1 要求显式重新生成；原 29 份来源观察和五项源码目标继续重核，未改变公共格式或真实接受状态。完整元数据和本轮日志留在忽略的任务目录，持久记录保存必要派生字段和摘要；摘要不替代原始输入，未清理这些文件。

## 未覆盖范围与后续门禁

完整源码、Production 有效配置及选项差异、实际构建 patch、包原字节 / tree / 文件清单、签名信任、许可与受信任 SDK 决定仍须分别闭合。元数据选择不能使 `build_ready` 成为 true，不能进入 C1–C5 的执行，也不能改变原 CLI 与新 payload 的 `not-accepted`。
