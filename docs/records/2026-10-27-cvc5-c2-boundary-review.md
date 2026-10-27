# C2 有限边界审阅与 LibPoly 澄清发送

日期：2026-10-27（Asia/Shanghai）。用途：记录本批直接问题修正、离线验证与获准的上游消息，供后续实施与验收使用。基线 `dev` / `5013c8b`，开始时工作区干净，与本地 `origin/dev` 引用无领先 / 落后；未 fetch，不据此声明远端最新状态。

本批不接受 SDK / 工具、许可、隔离宿主或真实执行资格，不改变 P1–P4、Evidence、旧配方、资源 profile 或依赖。正式接线候选归入[原设计](../query/solver-cvc5-execution-preparation.md#有限缺口审阅2026-10-27)，本记录只保存本次事实。

## 新增结果

1. 修正[布局入口](../../scripts/prepare-cvc5-execution-review.py)的三处边界：链接目标中的目录限定符不能被归一化掉；恰好 40 次链接展开后仍检查终点；符号链接权限仅作库存，不产生 chmod 变换。
2. 原接线设计补充 `etc/rmt` 单项省略建议、五处精确权限差异、内部非 root UID/GID 候选、原归档扩展元数据门禁。它们仍待接受，不在布局代码中加入 `etc/rmt` 特例，也没有实际省略、解包、chown 或 chmod。
3. 完整读取观察审阅排除 fanotify 单独承担的路线；ptrace 仍缺全线程 / FD、稳定对象、生成输入版本及未支持路径的拒绝设计，只保留为有限可行性候选。PID / inode、采样间隔及独立整树终止须核定和实测；没有填入猜测数值或新增通用监控框架。
4. 按项目所有者本次明确授权发布 LibPoly 三项澄清；仅此一条外部消息，C1 仍 `not-accepted`。

## 缺陷复现与修正

先新增有独立手算期望的回归，再改实现，使用 `python3 -O` 验证拒绝不依赖 assert。

| 问题 | 修正前观察 | 修正后行为 |
| --- | --- | --- |
| 目录限定符丢失 | `a/`、`a/.`、`a/./.`，以及经另一符号链接到普通文件的 `indirect/`、`indirect/.` 均未拒绝；该测试出现 5 个失败子例 | 保留目录遍历要求，在直接或间接解析到非目录时拒绝。真实目录的 `/`、`/.`、中间 `/./` 和虚拟根仍可解析 |
| 40 层边界 | 恰好 40 个链接后到达普通文件仍报 `layout-link-depth` | 允许最后一次终点检查；41 层与循环的既有拒绝继续通过 |
| 符号链接权限 | 合成 `4777` 符号链接被列入 `permission_changes`，与“仅库存、不 chmod”设计不一致 | 保留链接的原模式信息，仅非符号链接移除 setuid / setgid；合成普通文件 / 目录的 sticky 位保持 |

前两项首次定向运行共 3 个测试，退出 1，含上述 5 个失败子例及一个深度错误；真实目录正例通过。第三项单独运行 1 个测试，退出 1。错误均为回归发现的旧实现问题；随后修正并运行完整范围，没有放宽测试或原停止线。基线实现可从 `5013c8b` 取得，新增测试在[同一测试入口](../../scripts/test-cvc5-execution-review.py)。

Linux 路径依据为 [path_resolution](https://man7.org/linux/man-pages/man7/path_resolution.7.html)；观察与控制原语依据为 [fanotify](https://man7.org/linux/man-pages/man7/fanotify.7.html)、[ptrace](https://man7.org/linux/man-pages/man2/ptrace.2.html) 和 [cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)，本批只读核对。手册能力不等于目标内核 / 宿主资格；本机测试也不执行 Linux 路径查找或 syscall。

## 实际离线验证

| 命令 / 检查 | 实际结果 |
| --- | --- |
| `python3 -O scripts/test-cvc5-execution-review.py` | 40 项通过，包括真实留存库存逐项核对；新增 4 个测试方法 |
| `python3 -O scripts/test-prepare-cvc5-offline-build.py` | 33 项既有配方回归通过 |
| 布局入口，原配方摘要及规范绝对路径 | 返回 2，生成离线候选，`assembly_ready=false`、`execution_ready=false`、`build_ready=false` |
| 新布局与 10 月 23 日留存布局比较 | 完整 `layout` 对象逐项一致；输入原文件、源码与 patch 经原 `checked_plan` 重核 |
| `./scripts/check-repo.sh` / `git diff --check` | 仓库检查通过（2,870 文件），差异卫生检查通过；未更改根入口或文件模式 |

原配方为 `docs/records/solver-cvc5-c2-2026-10-23/offline-build-recipe.json`，SHA-256 `2ee5ae5e9c437036c6b0cc6ec8c4324b875b0376dcd91c9aa3d5dca29d01f4dd`。生成命令沿原设计的运行入口，`--recipe` 与 `--output` 使用规范绝对路径。新输出保存在 `artifacts/cvc5-c2-boundary-2026-10-27/sdk-layout-review.json`，SHA-256 `b2620482bb3c7609d8016c2e1ad16f02268090c589e3cd86c716a1e9d77962ae`。输出绑定当前方法摘要；方法发生修正，因此整体输出摘要与旧记录不同，不能要求旧 method 身份不变。

实际仍为 172 包、17,125 个原归档条目、14,719 路径、537,445,262 普通文件 bytes；没有隐式父目录。唯一悬空链接仍是 `etc/rmt`，五项权限差异仍与旧记录完全一致。旧输出和原库存未改写。

第一次生成调用误传相对 `--recipe` 路径，入口按原规则返回 1 / `noncanonical-file`，未生成布局；失败输出保留。改为规范绝对路径后得到预期的离线候选退出码 2；未修改路径校验器、未把失败算作成功。

任务日志位于 `.tmp/cvc5-c2-boundary-2026-10-27/`：`layout-tests.*`、`recipe-tests.*`、首次 `layout-generation.*` 及随后 `layout-generation-absolute.*`。各次运行的 `.result.json` 保留 argv 与实际退出码，stdout / stderr 分开保存。产物与日志仅本机留存，未建立新的异盘或远程备份；复核入口与合成测试在仓库。

## LibPoly 外部消息

项目所有者在本次任务明确批准将[已有草稿](2026-10-23-libpoly-upstream-clarification-draft.md)发布到 `SRI-CSL/libpoly`，范围仅为固定版本三项许可 / 来源澄清；已说明公开正文、通知维护者和无法撤回已发送通知的影响。

- 发布前精确标题查询未发现同题 issue。GitHub 插件创建返回 `403 Resource not accessible by integration`，没有用该失败宣称已发送。
- 随后使用本机已有、已登录的 `gh`，以 `--body-file` 传入原英文正文，创建 [issue #113](https://github.com/SRI-CSL/libpoly/issues/113)。未安装 CLI、修改权限、申请上游权限或发送邮件。
- API 创建时间为 `2026-10-27T11:55:26Z`，即北京时间 **2026-10-27 19:55:26**。创建后读回为 OPEN，标题完全匹配；正文只归一化 CRLF / LF 和末尾换行后匹配授权草稿。原草稿正文 SHA-256 为 `e2c55d2f9b0e79b9e9ba069b185322f59fed2d500c8e08b59cc9fc9f43f79b82`。
- 正文、创建响应及读回保存在同一任务日志目录的 `libpoly-issue-body.md`、`libpoly-create.*`、`libpoly-issue-readback.json`。仓库保留正文与公开链接，不收录凭据。

发送只改变联络状态，没有取得权利人说明或作出许可接受。整体冲突、Polyxx 覆盖和旧 `open_memstream.c` 来源授权仍须按[原关闭标准](2026-10-23-libpoly-license-history.md#关闭缺口所需的具体依据)复核；不自动轮询、追加消息或重开同题 issue。

## 结束边界与后续

本批完成计划中的有限离线审阅和直接缺陷修正；完整 C2 执行准备仍未完成。下一项决定限定为读取后端四个具体缺口是否能在可维护范围内实现；若不能，应提交精确成本 / 信任决策并停止，不能换成 trace / 摘要即宣称已满足要求。LibPoly 答复到达后另作 C1 接受审阅；两条条件都不自动授权组装或执行。

未改 Rust、lockfile、旧 profile / IR / Evidence 字节，未重跑无改动的 Rust workspace、Linux 目标构建或 F2 验收。未安装 / 组装 SDK、启动容器 / VM、运行 configure / CMake / compiler / solver / 资格探针，也未创建构建批次根。没有新增后台进程或自动清理。工作区为本批 6 个已跟踪文件修改及 1 份新增记录，未暂存、提交、push 或创建 PR；本地分支仍与本地 `origin/dev` 引用一致。
