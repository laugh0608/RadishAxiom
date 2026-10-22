# cvc5 C1 输入接受与 C2 离线准备

更新日期：2026-10-22。用途：供输入审阅者和构建实施者核对 C1 的精确缺口、待确认获取范围与 C2 离线检查入口；接续[构建候选方案](solver-cvc5-build-candidate-plan.md)。本文不改变公共契约、许可或信任决定，不提供实际构建 / 运行授权；当前均未 accepted。


2026-10-22，按项目所有者要求先收口 C1 缺口、准备精确获取清单并推进可离线完成的 C2。当前完成的是缺口定位、获取计划与离线字节检查能力，**C1 尚未接受，C2 尚未形成完整构建入口**。实际复核见[本批记录](../records/2026-10-22-cvc5-c1-c2-preparation.md)。旧 C0 / Production / patch 记录与公共格式不改写。

### C1 的三个决定边界

| 项目 | 已有材料能确定什么 | 关闭缺口所需的具体出口 |
| --- | --- | --- |
| LibPoly 许可冲突 | 固定 `debian/copyright` 的两处 `GPL-3+` 标签、Lesser 正文和末尾 GPL 路径确有冲突；根 `LICENCE` 与 `include/poly.h` 支持 LGPL 声明。顶层 CMake 进入 src / include 与条件 bindings / tests，没有直接进入 debian 子目录 | 区分库源码 / 头文件、构建输入、Debian 打包文本及未来实际嵌入对象，给出限定本地诊断的明确接受依据；如既有声明不足则仅取得针对该版本的权威澄清。不能仅凭未构建 debian 目录消除 `Files: *` 的声明冲突，不能删去或修写原文；当前继续 `not-accepted` |
| 快照签名与信任 | 固定 Release 为 2023-06-10 / Debian 12.0，未含 `Valid-Until`；摘要链已核对。已有历史 keyring 可读回，旧签名结果对应另一份 InRelease；已有 GnuPG 2.4.7 环境记录可供复用审阅 | 明确当前任务的公钥身份依据、两必要 bookworm 角色、验证工具 / 宿主信任范围及材料截至时点；另获真实验签授权并核对固定 2023 原字节。没有有效期字段不等于永久有效或最新安全状态，不关闭过期 / 撤销检查，不以同一未认证索引里的钥匙自证索引 |
| SDK 内容与 copyright | 已有 172 包 / 101 源版本的精确元数据关联，未取得实际内容；源码、工具运行库与候选嵌入对象是不同用途 | 取得固定原包后按文件建立 compiler / linker、sysroot / CRT、生成器、Editline 依赖的内容 / 来源 / patch / copyright 关联。先审实际用途和例外，再作工具输入接受；原包匹配本身不满足 C1 |

签名复用优先检查仓库既有材料，避免新增工具链取证：历史 [keyring / gpgv 记录](../records/linux-builder-source-chain/release-verification.json)含 55,918 bytes 公钥环，SHA-256 `506b815cbb32d9b6066b4a2aa524071e071761e7e7f68c3ac74f3061ba852017`；[历史说明](../records/linux-builder-source-chain/README.md#信任与时效边界)列出 bookworm archive / stable release 完整主指纹及 HTTPS / 镜像信任缺口。[后续验证环境](../records/rust-linux-input-review/musl-verifier-smoke-execution-2026-09-12.md)记录 GnuPG 2.4.7 的限定信任接受。它们不是本次验签结果或本次运行授权；本轮不查询 daemon、不导入 keyring、不启动容器。当前不追加 keyring 下载，也不假称复用环境已经完成本次资格检查。

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

源文件共 328 个、570,734,908 bytes；按精确 URL 去重，保留共享文件的全部来源关联。版权文件预计位于这些包内，**当前没有假设其具体内容或额外版权 URL**。仅请求固定 `https://snapshot.debian.org/archive/debian/20230612T000000Z/` 下清单中的目标；允许记录到的同站 `/file/<40 位十六进制>/<单段安全名称>` 重定向，至多五跳，最终仍须匹配清单的 SHA-256 / 长度，地址中的 SHA-1 不代替内容 SHA-256。

精确留存目录为 `/Users/luobo/Code/RadishAxiom/.tmp/cvc5-c1-acquisition-2026-10-22`；已按项目所有者确认创建，六项取得后在第七项编码重定向处停止；原方法、日志和文件保留，详见[获取记录](../records/2026-10-22-cvc5-c1-acquisition.md)。编码处理只作离线修正，未恢复下载，后续接续范围须另行确认。原包放清单规定的 `inputs/pool/main/...`，请求 / 失败日志及冻结清单放本批目录内。串行获取、零自动重试、零替代来源；每项 180 秒、整批 90 分钟硬停止。预计 15–45 分钟，网络与 500 次请求的延迟未实测；正常正文约 660 MiB，整批正文上限等于上述精确总量，日志另限 8 MiB。开始前检查至少 1 GiB 可用空间；不足则停止，不清理既有文件。

首次 HTTP / 重定向 / TLS / 摘要 / 长度 / 超时 / 占用失败即停止并保留原始结果、部分文件；不自动下载剩余项或扩大预算。不得覆盖已有同名批次，不隐式续传。仅获取和流式摘要核对，不解包、运行 maintainer scripts、安装、组装 SDK、构建或执行 solver。完成后可用离线入口只读核对整套原包；若原包无法取得，保留这一具体失败再决定，不自动换镜像 / 新快照。清理需另行确认本批精确文件；本批保留原包与日志，不删除旧取证材料，无系统状态需要回滚，不上传。

### 已实现的 C2 离线部分与剩余依赖

1. `python3 scripts/cvc5-build-preparation.py verify` 从现有 C0 / SDK 输入重建清单并逐类型核对，拒绝清单、状态、预算或绑定漂移。`audit-archives` 只读核对实际原包，逐文件检查长度 / SHA-256，拒绝多余文件 / 目录、符号链接与特殊文件；缺文件返回 2。它不解压和执行第三方内容，全部原包匹配仍返回 `build_ready=false`。
2. [构建输入预检](../../scripts/check-cvc5-build-inputs.py)消费[既有 patch 的私有输入格式](solver-cvc5-build-patch-review.md#私有输入约束)，通过 `manifest` 路径与必需的 `--sha256` 接收另行审阅的真实输入。检查闭合 JSON 字段、六类 header 全量文件、必要头、至少六类 `.a`、实际字节和绑定的 closure review；保留 Editline 顺序及重复项，拒绝遗漏、多余、错序绑定、路径逃逸与特殊文件。未知字段、重复键和非有限数也拒绝。
3. Python 预检比 CMake 字节守卫更早执行，附加 8 MiB JSON、单文件 1 GiB、累计读取 4 GiB / 100,000 文件与树项上限；这些仅约束离线检查器，不改变 solver 或构建额度。输出只说明字节与外部审阅声明绑定成立，不证明 `.a` 对象 ABI、许可、工具接受或 CMake 行为。它不生成 `reviewed-for-configuration` 标记或真实 manifest，不认证可被并发修改的文件树；实际构建仍须只读挂载与启动时重核。

完整 C2 按以下具体依赖接续，暂不填入猜测路径或占位命令：

| 准备项 | 所需真实输入 / 何时才能完成 |
| --- | --- |
| 工具路径 / sysroot / CRT / specs / `.pc` 清单 | 先取得并只读审阅 SDK 包；固定 compiler / linker / ar / strip / Python / pkgconf 的实际文件身份，解析 symlink 归属。执行 `pkgconf --static` 属工具执行，另行说明并确认；静态文本解析不能冒充该结果 |
| 四依赖与主目标精确 argv / patch manifest | 在输入路径明确后固定 GMP / CaDiCaL / Poly / SymFPU 顺序、配方变换和 `cvc5-bin` 目标；依赖输出真实产生后才具备头 / 库摘要和 ABI / closure 审阅材料，不能要求在首次依赖构建前伪造这些输出 |
| 环境与资源 | 使用无继承环境的明确 PATH / locale / TZ / umask / CPU / SOURCE_DATE_EPOCH 来源；清空已有方案列出的查找 / launcher 变量；输入只读、独立源码工作副本、无网络、无宿主 socket / credentials。4 jobs / 8 GiB / 20 GiB / 90 分钟仍为待核定构建估算 |
| 留证与失败处理 | 精确 argv / cwd / 环境，CMake trace/cache、生成器输出、依赖文件、对象 / archive 成员、link map / trace / response file、strip 前后 ELF 与退出码分别保存；未知输入或越额立即停，保留失败。不能仅用 compile_commands 代替完整输入关系 |

当前只验收上述离线入口；不宣称已经生成完整执行计划、验证 `.pc --static`、CMake/configure、目标构建或实际链接。通过 C1 后可先准备依赖构建的精确授权范围；拿到真实依赖输出，再完成主 cvc5 配置输入清单，两步均受原 C2–C4 停止线约束。
