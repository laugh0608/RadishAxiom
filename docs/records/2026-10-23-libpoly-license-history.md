# LibPoly 固定版本许可与上游历史核对

日期：2026-10-23。接续 [C1 输入审阅](2026-10-23-cvc5-c1-input-review.md)。本任务先将上一批提交为 `9e276a9`，随后只读核对公开上游资料和既有本地源码，未发送外部消息、安装或构建。

## 结论与范围

**历史已查明，许可冲突尚未获得权威解释；C1 仍为 `not-accepted`，`build_ready=false`。** 固定候选仍是 `v0.2.1` / `3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a`，没有换版本、修改第三方声明或选择 GPL 路线。

本次观测的上游 `master` 为 `8779171e061fdbda9708d8839e3ca8d0a250df4f`。固定提交、该上游提交和本地留存源码的两份声明逐字节一致：

| 文件 | bytes | SHA-256 |
| --- | ---: | --- |
| `LICENCE` | 7,651 | `da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768` |
| `debian/copyright` | 912 | `cd3eb8b96019760e240235847501addff027f870ffe57687c4128ec78a155664` |

来源身份、35 份查询快照及 9 个本地文件摘要见[取证索引](solver-cvc5-c1-review-2026-10-23/libpoly-history-index.json)。查询响应保存在项目忽略目录 `artifacts/cvc5-libpoly-license-history-2026-10-23/`，没有把整份第三方源码或讨论复制进正式文档；这些原始快照尚无远程备份。索引是研究记录，不是许可接受或签名认证。

## 上游声明冲突从何而来

1. 2015-07-08，[`1e570302`](https://github.com/SRI-CSL/libpoly/commit/1e570302ff1fb53b6ea2d5bc09a286fb19947730)加入根 `LICENCE`，内容为 LGPL v3。所查该路径历史只返回这次修改。
2. 2017-06-13，[`9d25ed27`](https://github.com/SRI-CSL/libpoly/commit/9d25ed278c2faf4772f581ed6593448b4550ba2b)首次加入 `debian/copyright`，已经同时包含 `Files: *`、两处 `GPL-3+` 标签、LGPL v3 或以后版本的正文及 GPL-3 路径。冲突并非后来单独把 LGPL 标签改成 GPL 所产生。
3. 2017-07-25，[`41dde08f`](https://github.com/SRI-CSL/libpoly/commit/41dde08ff67a5db23d62f8ce5c1cafc5d0715f81)仅补 `Upstream-Name`、`Upstream-Contact` 和 `Source`；没有修正许可字段。其关联 [issue #12](https://github.com/SRI-CSL/libpoly/issues/12)及两条评论讨论 Debian 打包检查，没有说明该冲突。

这些事实支持“打包声明从创建时就不自洽”，**不等于已经证实笔误，也没有证明上游曾有意重许可**。根 LGPL 文本、94 个文件内 LGPL 声明和打包正文是一组支持 LGPL 的材料；相反标签仍须解释。仅排除 `debian/` 的构建用途不能消除 `Files: *` 的声明范围。

## Polyxx：有整体项目归属依据，缺明确的冲突消解

2020-06-11 的 [`fabc345b`](https://github.com/SRI-CSL/libpoly/commit/fabc345b836bea35883602cecf2aadac103412aa)加入 C++ 库实现及 CMake 目标；同日 [`79474f7b`](https://github.com/SRI-CSL/libpoly/commit/79474f7b4218938b30382917eaefbfbf3c8188bf)加入公开封装头文件。[PR #25](https://github.com/SRI-CSL/libpoly/pull/25)明确将这些内容介绍为 LibPoly 的 C++ 封装。PR 正文、6 条普通评论、6 条 review 记录和 6 条行内评论未提供专门的许可覆盖说明。

加入时项目已有根 LGPL 文本，所查引入提交没有另加独立许可证。这是整体覆盖的支持依据；不能把“文件内未重复声明”直接认定为无许可。另一方面，PR 被合入本身不能解决现有相反声明，也不足以单独宣称全部贡献权利来源已经核实。所需补证是对固定版本 Poly / Polyxx 及无文件内声明部分的整体覆盖说明，不是机械要求给每个文件补相同头部。

## 两种 memstream 必须分开处理

| 文件 | 已核事实 | 仍缺什么 |
| --- | --- | --- |
| `src/utils/open_memstream.c` | 2017-10-19 的 [`53d544c1`](https://github.com/SRI-CSL/libpoly/commit/53d544c110acfbf6e755d3810f021aa16d020c37)加入，提交说明只有函数名；正文有接口说明，没有作者、原始来源 URL 或独立许可声明。同次加入的 `.h` 有 SRI / LGPL 声明。2019 年两次后续修改仅处理 Windows 条件和注释 | `.c` 是上游原创还是外部引入、原作者 / 来源版本、适用授权及应保留的归属。不能把头文件声明或另一实现的 MIT 条款直接套用到 `.c` |
| `src/utils/u_memstream.c/.h` | 2023-03-17 的 [`59ee683e`](https://github.com/SRI-CSL/libpoly/commit/59ee683e544b573101bcdac213cd7a494d67b86a) / [PR #66](https://github.com/SRI-CSL/libpoly/pull/66)明确从 Mesa 改编；两个文件保存固定 Mesa commit `14f9f98dcb4b6034c331120acf405e9a3c64edc6` 的来源地址、Lag Free Games 版权及 MIT 许可全文 | 后续使用 / 分发时保留版权、许可和免责文本；本次未完成对 Mesa 原文件的独立字节比对，不把现有声明升级为第三方权利链全部验证 |

[issue #65 的讨论](https://github.com/SRI-CSL/libpoly/issues/65#issuecomment-1471933726)解释了从 `fmem` 候选转向 Mesa 的过程；讨论中对 `fmem` 的 MIT 描述不是最终引入代码的身份依据。另一条维护者评论要求把许可留在代码中，但没有给出旧 `open_memstream.c` 的来源或适用许可，不能据此关闭旧实现缺口。

本次尝试读取文件所指的 Mesa GitLab blob 页面及 `.c` / `.h` raw 页面，均返回不可访问；未用无来源镜像填补，也未取得并运行 Mesa 代码。原页面链接及失败范围记入索引。

固定 `src/CMakeLists.txt` 无条件列入 `u_memstream.c`，仅在 `NOT HAVE_OPEN_MEMSTREAM` 时列入旧 `open_memstream.c`。本次没有执行 CMake，因而没有实际条件值、对象集合或链接图。未来如果选择以实际未使用来界定某个构建制品的范围，必须另有配置 / 编译 / 链接证据；这仍不自动解决源码包分发范围。

## 关闭缺口所需的具体依据

1. **固定版本整体许可及冲突解释。** 上游具有相应权限的维护者或权利人提供可公开追溯、明确适用于固定 commit 的说明，确认 Poly / Polyxx 与无文件内声明部分的覆盖，并说明 `debian/copyright` 哪些字段需要修正。只修当前分支且没有历史适用范围，不自动覆盖旧版本；根许可证识别标签也不能替代这一解释。
2. **旧 memstream 来源授权。** 给出原作者、原始来源版本及可用条款，或确认其为有权许可的原创并说明适用许可。只有相似代码、接口名、提交者身份或相邻文件许可，均不足以补齐这项事实。
3. **在补证后作明确接受审阅。** 将上述材料绑定固定源码及预期用途，记录覆盖和未覆盖范围。MIT 通知保留属于已知义务；LGPL 的实际链接 / 组合 / 分发履约仍按后续制品审阅，不因本地输入接受自动取得分发资格。

本次没有发送 issue、邮件或 PR。下一步最有针对性的外部澄清仅为前两项；在暂不联系上游的范围内，这轮历史核对已经完成，不能再靠重复读取同样材料宣称许可闭合。也可以提交新的、充分的权利来源材料供审阅，但单纯接受风险不能将尚不明确的上游事实改写成确定。

## 检索和验证的实际边界

- 核对根许可、Debian copyright、旧 memstream、Polyxx 代表文件和新 memstream 的路径历史、引入提交、#12 / #25 / #65 / #66 相关讨论；按 `license`、`licence`、`LGPL`、`GPL` 检索该仓库 issues，只有 `license` 返回 #65。没有声称穷尽所有 PR、私下沟通、历史网页或全部贡献者权利。
- 最初两个通用 issues 查询缺少工具要求的类型限定而返回 422，失败响应保留；随后使用专用仓库 issue 搜索。未把检索失败当成无结果。
- 固定版本 / 观测上游 / 既有本地两份许可文本逐字节一致；35 份留存响应和 9 个本地文件的摘要可独立回读。固定五归档、500 项输入及旧失败记录未改写。
- 本批仅新增研究记录及更新文档路由；仓库级检查通过（2,855 文件），`git diff --check` 通过；35 份响应及 9 个本地文件摘要再次回读一致。不重跑无关 Rust、SDK 测试；未启动容器、安装、配置、构建或运行第三方载荷，未 push。
