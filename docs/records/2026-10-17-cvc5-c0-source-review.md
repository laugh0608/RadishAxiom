# C0 完整源码、Production 与构建 patch 静态验收

日期：2026-10-17。用途：记录本批实际取得、静态审阅、离线验证与剩余边界，接续[元数据批验收](2026-10-17-cvc5-c0-sdk-metadata.md)。读者：项目所有者、实施者及验收者。本文不接受工具、SDK、许可证、构建或运行资格。

## 范围与实际交付

项目所有者明确要求先提交上批 C0 元数据选择与验收材料，再推进完整源码、Production 配置和构建 patch 审阅，允许下载固定五项源码归档及必要许可材料，禁止 SDK 二进制包、安装、构建、探针 / solver、系统配置和 push。主代理先复核并精确提交上批 22 个文件为 `c2ea5d0`（`feat(solver): 固定 C0 SDK 元数据与依赖闭包`）；提交后工作区干净，`dev` 相对本地 `origin/dev` ahead 6，未刷新远端。后续具体工作由 gpt-6.1-sol / high 承担，主代理主持设计、静态复核和本批验收。

本批完成五源码原字节、安全审树、逐文件许可库存、Production / CLI 生成链静态分析、实际构建 patch 候选及 SDK 生成工具元数据补选。**这是静态审阅交付；C0 整体、C1 输入接受与后续构建条件仍未闭合，`build_ready=false`。** 本批改动留在工作区，未提交；唯一外部动作是获授权五源码的 HTTPS 获取，没有 SDK 二进制包或额外许可文件下载。

| 交付 | 实际结果与证据 | 结论边界 |
| --- | --- | --- |
| 五源码 | 原包共 13,368,905 bytes；四依赖重算摘要匹配固定配方；cvc5 归档 9,279,538 bytes，SHA-256 `cbaa927c4d8085e38e7a097191bb9dd3a6780cc17fcde65cb156c9583e597760` | cvc5 原无已留存的上游归档 hash；四项 Git 归档的 commit comment 一致，仅是未签名内容声明 |
| 完整树 | 10,466 条归档成员，9,949 个普通文件及 CaDiCaL 的一条内部链接；cvc5 7,066 个文件与此前留存 Git tree 的 blob 内容一致 | 不表示签名认证或源码到旧 CLI 的链接关联；原 mode / owner 记录而不应用 |
| 许可 / 组成 | 五份 tree 与五份逐文件许可库存，区分主库、嵌入 MiniSat、生成输入、工具、测试与文档 | LibPoly 的 GPL 标签 / LGPL 正文冲突保留；GMP 多种许可 / 例外按用途分开；SDK copyright 尚缺，未接受许可或分发 |
| Production | 62 个实际源码文件、59 项配置记录、13 个 CLI Python 模块 imports；区分静态可定与编译器 / 平台检测 | 未执行 configure、CMake、生成器或检测程序，不能把源码推导称为真实有效 cache / flags |
| SDK 生成角色 | 同一 Debian `20230612T000000Z` 快照新增 `python3-pyparsing 3.0.9-1` 与 `m4 1.4.19-3`；17 组 / 53 根包 / 172 包 / 474 关系 / 101 源版本 / 328 源文件 | 仅原索引离线解析；无新增传递包，无包下载或安装；真实内容 / API / 许可 / 签名 / 工具接受未闭合 |
| 构建 patch | 固定 cvc5 提交的 8 个构建文件；完整前树 7,066 文件、后树 7,067 文件及逐文件摘要，精确文本应用与宿主 git dry-run | 没有实际依赖输入 manifest、closure 审阅文件、SDK `.a` 或生成库；未运行 CMake，不能声称配置期拒绝已动态验证 |

源码的完整获取历史、限额、实际 tree 计数和检查见[获取审阅](solver-cvc5-source-review-2026-10-17/source-acquisition-review.md)及[源码记录](solver-cvc5-source-review-2026-10-17/source-inputs.json)；许可结论只到[静态许可审阅](solver-cvc5-source-review-2026-10-17/license-review.md)。首次下载完成 cvc5 后在 CaDiCaL 的同 ref 规范化重定向处被本地守卫拦下；旧失败及下载器原稿保留，修正仅接受已捕获的精确 Location 后继续，没有重发原始请求、换源或更改预期 hash。旧 manifest 未单独记录 302 status，恢复依据和限制已另记，未倒填成当时捕获的响应。

## 配置与 patch 的审阅结论

[Production 专题](../query/solver-cvc5-production-source-review.md)保留 Production / static / non-GPL / Editline / Poly / GMP / CaDiCaL / SymFPU；确认 statistics 开，assertions、tracing、muzzle、safe / stable、sanitizers、IPO 和其他可选 solver 库关闭。三值 `IGNORE` 的原始字符串与条件 false 分开记录。原 `ENABLE_PROOFS` 赋值缺少对应 option / 消费链，未据此虚构 proof 宏或运行验收。

Java/JNI/JAR 子图没有 CLI 反向依赖，可选择 Java OFF；Python bindings 在原 static 分支自动关闭。Python 解释器和 pyparsing 仍在 CLI 生成链，GMP AArch64 汇编必须有 m4，不能为少选依赖而关闭 assembly。既有 GMP 生成文件与非 maintainer 模式不要求新增 Autotools / Bison / Flex；不靠 touch、移除文件或运行上游脚本凑结论。Git、formatter、IWYU、时钟和 CaDiCaL date/uname 等隐藏输入均明确进入未来构建约束，不宣称可复现构建。

[patch 专题](../query/solver-cvc5-build-patch-review.md)只替换五个依赖 Find、顶层入口、私有清单 helper 和版本 Git 发现，原 `src/` 与 ConfigProduction 字节不改。主代理复核后补齐完整配置守卫、真实 `-Werror` token 检查、外部 closure 文件的内容绑定和静态记录误升接受的拒绝。清单要求真实库 / 头文件路径、bytes / hash 及 Editline 有序静态闭包；当前这些输入不存在，不能用伪摘要或占位 `.a` 构造可执行入口。工具、sysroot / CRT、环境、剩余查找路径与实际读入追踪仍是 C1 / C2 工作；该 patch 不是完整 hermetic build。

SDK 元数据补选只增加两个直接根包、两条依赖边、两个源版本及七个源文件。二进制声明总量 120,870,556 bytes（增加 414,724），对应源码声明总量 570,734,908 bytes（增加 3,684,597），不是下载量。当前[总选择](solver-cvc5-c0-2026-10-17/input-selection.json)升级为私有 0.3，引用真实 source / production / patch 字节，显式拒绝旧版及被篡改的上游接受状态。上批 0.2 位于 `c2ea5d0`，下载时冻结副本继续保持原字节；前批验收事实不改写成新计数。

## 实际验证

本批自有 Python 测试共 **147 项**：源码审树 8、Production 12、patch 17，以及元数据 / SDK / 总选择 / 独立闭包 32 / 33 / 33 / 12。测试涵盖路径 / 类型 / 链接 / 预算、精确重定向、来源与配置摘录篡改、完整矩阵漏项、patch 的 preimage / offset / fuzz / 截断 / 额外文件、元数据闭包及误升执行 / 接受状态。具体整合结果见[机器验收](solver-cvc5-source-review-2026-10-17/selection-integration-validation.json)，主代理最终重核的命令、输出及当前入口摘要见[最终离线检查](solver-cvc5-source-review-2026-10-17/root-validation.json)。patch 记录中的入口摘要对应此前 16 项测试观察；补入新增行空白拒绝后的现行检查器及 17 项结果由最终离线检查绑定，不把旧摘要冒充当前源码。

只读实际原字节检查包括：

```text
python3 scripts/cvc5-c0-source-inputs.py verify
python3 scripts/check-cvc5-c0-source-independent.py
python3 -O scripts/check-cvc5-production-source-review.py
python3 -O scripts/check-cvc5-build-patch.py .tmp/cvc5-c0-acquisition-2026-10-17/sources/cvc5/cvc5-f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341 patches/cvc5/1.3.4/explicit-inputs.patch docs/records/solver-cvc5-source-review-2026-10-17/patch-review.json
python3 scripts/cvc5-c0-sdk-metadata.py metadata-verify
python3 scripts/cvc5-c0-sdk-selection.py verify
python3 scripts/check-cvc5-c0-input-selection.py
python3 scripts/check-cvc5-c0-sdk-independent.py
./scripts/check-repo.sh
git diff --check
```

精确 patch 路径的 Git whitespace 属性允许 unified diff 保留上游 context / deletion 的原空白及末尾空 context 行；自有 patch 检查器另行拒绝新增行的尾空格 / tab，没有裁剪原文或宽免新增代码。

整合期间检查曾正确拒绝并行审阅导致的 patch 摘要漂移；待 patch 冻结后显式重生总选择，不放宽检查或抹掉失败。首次仓库检查在整合验收 JSON 尚未生成时报告两处缺失链接，文件完成后再核对；patch 的第一次新文件空白检查报告末尾 context 空行，精确属性补齐后无空白诊断（`git diff --no-index --check /dev/null <patch>` 的退出码 1 只表示文件存在差异）。源码独立检查器采用不同 tar 解析路径，SDK 独立检查器从原索引重建包与关系；Production 检查仅绑定原字节 / 摘录，patch 检查仅验证文本应用，均不是配置 / 构建通过、签名认证或形式证明。

没有重跑 Rust workspace、Clippy、其他平台、CI、真实 checker / cvc5；本批不修改 Rust、Cargo 依赖、公共语义 / IR / Evidence 或运行资源，因此没有把这些未运行项目写成通过。全部上游脚本（包括 `--help`）、CMake / Make / Autotools / Python 生成器、compiler probes 和 solver 均未执行。

## 留存与后续停止线

原包、冻结下载器 / 选择副本、失败观察、原树和派生树保留在 `.tmp/cvc5-c0-acquisition-2026-10-17`，没有清理或上传；摘要、tree / 许可库存、差异和自有检查入口进入本批待审工作区。主代理下载进程均已退出，无本批长期服务。仅本机留存不等于异盘持久归档或签名认证。

下一步仍须分别闭合 SDK 原包内容 / copyright / 信任、LibPoly 许可歧义、实际生成库 / 头文件 / Editline `.pc --static` 顺序、工具链与 sysroot、真实配置检测、离线构建入口和执行环境。取得包、组装 / 安装、构建及检测程序执行须各按精确范围授权。本批不请求或替代这些授权；原 CLI 与新候选继续 `not-accepted`，E0 / E4 / E5 未取得资格，原容量、旧 query / P4 字节及 128 MiB / 6 s 等限制保持。
