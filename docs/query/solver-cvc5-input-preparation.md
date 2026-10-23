# cvc5 C1 输入接受与 C2 离线准备

更新日期：2026-10-23。用途：供输入审阅者和构建实施者核对 C1 的精确缺口、原字节获取结果与 C2 离线检查入口；接续[构建候选方案](solver-cvc5-build-candidate-plan.md)。本文不改变公共契约、许可或信任决定，不提供实际构建 / 运行授权；当前均未 accepted。


2026-10-22，按项目所有者要求先收口 C1 缺口、准备精确获取清单并推进可离线完成的 C2。现已完成全部原包获取、独立原字节核对，以及[后续留存、包内容和真实验签审阅](../records/2026-10-23-cvc5-c1-input-review.md)，**C1 尚未接受，C2 已形成可审阅的离线配方与预检，尚无执行资格**。实际复核见[本批记录](../records/2026-10-22-cvc5-c1-c2-preparation.md)。旧 C0 / Production / patch 记录与公共格式不改写。

### C1 的三个决定边界

| 项目 | 已有材料能确定什么 | 关闭缺口所需的具体出口 |
| --- | --- | --- |
| LibPoly 许可冲突 | [上游历史核对](../records/2026-10-23-libpoly-license-history.md)确认 Debian 冲突在 2017 年首次加入时已存在；Polyxx 作为同项目封装加入，属于根许可覆盖的支持依据；新 memstream 有 Mesa / MIT 声明及引入讨论，旧 memstream 来源仍未明确 | 需固定版本整体许可及 Poly / Polyxx 覆盖的权威解释，并补旧 `open_memstream.c` 来源授权；MIT 通知须保留，Mesa 原文件独立比对尚未完成。不能认定已确认笔误或改 GPL 路线。当前 `not-accepted` |
| 快照签名与信任 | 初次 GnuPG exit 2 暴露旧钥匙及历史角色缺口；随后从既有 removed-keys 取得精确 buster 块，经项目所有者明确接受三历史角色及有限身份 / 时效依据后，原文三签名、钥匙认证、Release / 索引绑定与五负例全部通过 | 本次本地诊断范围已收口；保留公钥材料时点、HTTPS / 留存包身份与全渠道最新撤销未覆盖的显式信任限制，不外推运行资格 |
| SDK 内容与 copyright | 172 包 control 与元数据一致，全部 copyright 路径解析到文件；101 `.dsc` 与源码集合 / 摘要匹配；工具、CRT、静态库、`.pc` 已有实际路径与字节身份 | 库存 / 声明来源已补齐；整体输入接受仍受 LibPoly 许可约束。真实搜索行为、patch 生效、实际链接对象及完整静态闭包留到 C2–C4；不以静态摘要升级为 ABI、重建或运行接受 |

既有 55,918 bytes keyring 单独验证原文时失败；本任务随后明确接受[历史三角色方案](../records/solver-cvc5-c1-review-2026-10-23/historical-key-candidate.json)，追加同一留存 keyring 包 removed-keys 中的 8,132 bytes buster 公钥块，完整原文三签名必须全部通过。[实际验证](../records/solver-cvc5-c1-review-2026-10-23/historical-verification.json)及五负例均通过；没有删除签名或忽略 NO_PUBKEY。当前 Docker CLI SHA-256 为 `4a728ee98f89005a90198a9be791e8fdaebbcb5e6af9721251efe0113df37759`、daemon 为 `29.8.2 / API 1.56`，两次漂移及限定信任确认见[本批记录](../records/2026-10-23-cvc5-c1-input-review.md)。三次执行共 20 个短时容器全部退出并删除；无新增钥匙下载、安装或构建。公钥材料、官方身份页面、工具与宿主仍是明确的信任输入，全渠道最新撤销未覆盖；不得沿用为 SDK / solver 运行资格。

copyright 核对按用途分层：

- **候选嵌入项**：glibc / CRT / libgcc / libstdc++、Editline / tinfo / bsd / md 及自建库，最终用实际 header / object / archive member / link map 定位；不把整个 SDK 统一标为 LGPL。
- **构建期执行项**：compiler / binutils、CMake / Make、Python / pyparsing / m4、shell / 文本 / 解包工具及其运行依赖，保留精确包与对应源包的 copyright、例外和 patch。预编译工具的发行版构建仍为显式信任。
- **包内未用项**：文档、测试、打包 / maintainer scripts、Essential 基线等保留原包库存；不能据元数据选择声称已执行或已嵌入。源包用于对应与审阅，不展开其 Build-Depends 或递归重建全套 SDK。
- **任何分发**：二进制、镜像、SDK、静态组合的分发条件另行验收；本批只准备本地诊断，不将材料取得升级为分发许可。

### 精确获取范围与首错停止

[获取清单](../records/solver-cvc5-c1-2026-10-22/acquisition-plan.json)由[离线准备入口](../../scripts/cvc5-build-preparation.py)消费现有 C0 / SDK 选择生成；每个文件记录 URL、声明长度 / SHA-256、相对留存路径与所属包 / 源版本，并绑定原清单、元数据、Production 和 patch 身份。没有重新解析包选择或添加工具。

| 原包类别 | 文件数 | 声明 bytes |
| --- | ---: | ---: |
| arm64 / all 二进制 `.deb` | 172 | 120,870,556 |
| `.dsc` | 101 | 563,428 |
| Debian patch 归档 | 91 | 7,554,610 |
| native source | 10 | 6,673,425 |
| orig 及索引中附带的签名文件 | 126 | 555,943,445 |
| 合计 | 500 | 691,605,464 |

源文件共 328 个、570,734,908 bytes；按精确 URL 去重，保留共享文件的全部来源关联。这些包内的 copyright 路径现已逐项解析并留存，见本批内容记录；原获取清单没有增加额外版权 URL。仅请求固定 `https://snapshot.debian.org/archive/debian/20230612T000000Z/` 下清单中的目标；允许记录到的同站 `/file/<40 位十六进制>/<单段安全名称>` 重定向，至多五跳，最终仍须匹配清单的 SHA-256 / 长度，地址中的 SHA-1 不代替内容 SHA-256。

精确留存目录为 `/Users/luobo/Code/RadishAxiom/.tmp/cvc5-c1-acquisition-2026-10-22`；首次取得六项后在第七项编码重定向处停止，[原失败记录](../records/2026-10-22-cvc5-c1-acquisition.md)保留。经项目所有者确认，修正后的入口从第七项接续，在第 41 项达到单项 180 秒限时后停止；累计 40 项通过字节核对，第 41 项部分文件保留、459 项未请求，详见[接续记录](../records/2026-10-22-cvc5-c1-continuation.md)。新日志与冻结方法独立放 `continuation-1/`，前六项没有重复请求或覆盖。

前两批原包放清单规定的 `inputs/pool/main/...`，串行获取、零自动重试、零替代来源；当时每项 180 秒、每批 90 分钟硬停止。第七项接续范围为 494 文件 / 691,366,296 bytes 正文，日志另限 8 MiB；实际持续约 14 分 50 秒，在第 41 项超时退出，不能据原先 15–45 分钟估算宣称能完成整批。开始前检查至少 1 GiB 可用空间；不足则停止，不清理既有文件。`--continue-from-7` 仅接受原失败记录与恰好六项已取得的状态，且要求 `continuation-1/` 不存在；本次执行后拒绝重跑。后续部分文件处理与获取预算须明确范围后另行确认，不能隐式续传或放宽限时。

首次 HTTP / 重定向 / TLS / 摘要 / 长度 / 超时 / 占用失败即停止并保留原始结果、部分文件；不自动下载剩余项或扩大预算。不得覆盖已有同名批次，不隐式续传。仅获取和流式摘要核对，不解包、运行 maintainer scripts、安装、组装 SDK、构建或执行 solver。完成后可用离线入口只读核对整套原包；若原包无法取得，保留这一具体失败再决定，不自动换镜像 / 新快照。清理需另行确认本批精确文件；本批保留原包与日志，不删除旧取证材料，无系统状态需要回滚，不上传。

### Range 接续与最终原字节获取结果

[超时分析与第二次接续提案](../records/2026-10-22-cvc5-c1-timeout-review.md)固定原材料只读、Range 获取第 41 项尾部后再取得第 42–500 项，正文总上限 636,150,180 bytes；新输出独立放 `continuation-2/`。预算区分 60 秒无进展、按剩余大小计算的单项上限与 6 小时批次上限，未写回原批准清单。[离线实施与验证](../records/2026-10-22-cvc5-c1-range-preparation.md)完成后，又加入显式本机 HTTP 代理选项，下载器 68 项测试通过；原 C1 / C2 离线准备 47 项测试结果保留。

已按后续确认通过本机代理实际试取：第 41 项 Range 和完整拼接核对成功，但尾部仅约 55.5 KiB/s；按低速即汇报要求主动停止。累计完成至第 46 项，第 47 项部分文件保留，453 项未请求；旧材料未变，详见[代理获取记录](../records/2026-10-22-cvc5-c1-proxy-acquisition.md)。当前 `continuation-2/` 已占用，原接续入口拒绝重跑，不自动续下或整包重下。2026-10-23 按项目所有者“继续下载”完成[第三次接续](../records/2026-10-23-cvc5-c1-continuation.md)：复用用户取得的第 48 项，补齐第 47 项后取得第 49–500 项；本批新正文 628,212,768 bytes，耗时约 29 分 35 秒，无失败。现已完整取得全部 500 项 / 691,605,464 bytes，下载器与独立原字节复核均通过，旧材料未变。新目录 `continuation-3/` 已占用，当时第 48 项仍在用户提供的系统临时目录；后续已复制留存到项目 `artifacts/cvc5-c1-retained-2026-10-23/`，全部 500 项再次回读匹配，见[新留存索引](../records/solver-cvc5-c1-review-2026-10-23/retained-inventory.json)。没有后台下载。70 项下载器测试属于获取批次；后续内容扫描、初次失败与经确认接续通过的验签另行记录，原字节齐全不解除 C1 接受或构建门禁。

### 已实现的 C2 离线部分与剩余依赖

2026-10-23 已完成[离线入口与留证规则](../records/2026-10-23-cvc5-c2-offline-entry.md)：[入口](../../scripts/prepare-cvc5-offline-build.py)只生成 / 核对命令数据，绑定全部原包、五源码、SDK 库存、patch、工具路径、环境及阶段条件；包含日志 / 链接清单、失败保留和精确清理约束。`check` 通过准备检查后仍返回 2，保持 `execution_ready=false` / `build_ready=false`。不存在执行或删除模式；CMake 检测项目仅保存为文本。

随后形成[SDK 组装与构建监督离线接线设计](solver-cvc5-execution-preparation.md)：真实库存生成 14,719 路径的候选，显式保留 `etc/rmt` 悬空链接和五处权限变换待审阅项；事件纯规则检查原配方顺序、预算及失败保留。36 项新测试及 33 项配方回归通过，见[本批记录](../records/2026-10-23-cvc5-c2-execution-review.md)。尚无组装 / 执行适配器、完整读取监控或宿主资格，旧 solver 监督策略未放宽。

1. `python3 scripts/cvc5-build-preparation.py verify` 从现有 C0 / SDK 输入重建原清单并逐类型核对，拒绝清单、状态、预算或绑定漂移；输出的 signature_verified / authorization 是被冻结原计划的时点，不读取本批后续验签接受记录。`audit-archives` 只读核对实际原包，逐文件检查长度 / SHA-256，拒绝多余文件 / 目录、符号链接与特殊文件；缺文件返回 2。它不解压和执行第三方内容，全部原包匹配仍返回 `build_ready=false`。
2. [构建输入预检](../../scripts/check-cvc5-build-inputs.py)消费[既有 patch 的私有输入格式](solver-cvc5-build-patch-review.md#私有输入约束)，通过 `manifest` 路径与必需的 `--sha256` 接收另行审阅的真实输入。检查闭合 JSON 字段、六类 header 全量文件、必要头、至少六类 `.a`、实际字节和绑定的 closure review；保留 Editline 顺序及重复项，拒绝遗漏、多余、错序绑定、路径逃逸与特殊文件。未知字段、重复键和非有限数也拒绝。
3. Python 预检比 CMake 字节守卫更早执行，附加 8 MiB JSON、单文件 1 GiB、累计读取 4 GiB / 100,000 文件与树项上限；这些仅约束离线检查器，不改变 solver 或构建额度。输出只说明字节与外部审阅声明绑定成立，不证明 `.a` 对象 ABI、许可、工具接受或 CMake 行为。它不生成 `reviewed-for-configuration` 标记或真实 manifest，不认证可被并发修改的文件树；实际构建仍须只读挂载与启动时重核。

当前离线配方已固定已知路径、命令与条件分支；以下实际观察仍是未来执行前或阶段间的门禁，不填入假输出摘要：

| 准备项 | 所需真实输入 / 何时才能完成 |
| --- | --- |
| 工具路径 / sysroot / CRT / specs / `.pc` 清单 | 真实工具 / CRT / 静态库 / `.pc` 路径及 symlink 归属已定位，见[文件关联结果](../records/solver-cvc5-c1-review-2026-10-23/derived-content-review.json)。必须绑定版本化 gcc-12 / g++-12，包集合未提供通用 cc / gcc / g++；默认 specs 与运行搜索目录仍未查询。执行 `pkgconf --static` 属工具执行，另行说明并确认；静态文本解析不能冒充该结果 |
| 四依赖与主目标精确 argv / patch manifest | 在输入路径明确后固定 GMP / CaDiCaL / Poly / SymFPU 顺序、配方变换和 `cvc5-bin` 目标；依赖输出真实产生后才具备头 / 库摘要和 ABI / closure 审阅材料，不能要求在首次依赖构建前伪造这些输出 |
| 环境与资源 | 使用无继承环境的明确 PATH / locale / TZ / umask / CPU / SOURCE_DATE_EPOCH 来源；清空已有方案列出的查找 / launcher 变量；输入只读、独立源码工作副本、无网络、无宿主 socket / credentials。4 jobs / 8 GiB / 20 GiB / 90 分钟仍为待核定构建估算 |
| 留证与失败处理 | 精确 argv / cwd / 环境，CMake trace/cache、生成器输出、依赖文件、对象 / archive 成员、link map / trace / response file、strip 前后 ELF 与退出码分别保存；未知输入或越额立即停，保留失败。不能仅用 compile_commands 代替完整输入关系 |

当前已交付分阶段的可审阅配方和预检，主目标 argv 通过真实 manifest 后绑定；未实现实际隔离调度与读取 / 资源监控，不宣称验证 `.pc --static`、CMake/configure、目标构建或实际链接。通过 C1 后可先准备依赖构建的精确授权范围；拿到真实依赖输出，再完成主 cvc5 配置输入清单，两步均受原 C2–C4 停止线约束。
