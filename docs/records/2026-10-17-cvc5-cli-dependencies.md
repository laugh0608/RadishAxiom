# cvc5 精确 CLI 依赖与许可证补证记录

日期：2026-10-17。范围：`cvc5-Linux-arm64-static.zip` 中单一 CLI 的静态补证与后续实施准备。读者为项目所有者及执行层实现者。没有安装、构建镜像、运行探针或 solver，不改变系统配置、原容量、旧 profile 字节或资源限值。

## 本批结论

[ADR 0028](../adr/0028-bounded-solver-calibration-entry.md)的 D1–D3 已 Accepted，前批 11 个准备文件已提交为 `6593254`。本批取得 25 份来源材料，锁定四项依赖的上游配方，补齐 CaDiCaL / SymFPU / LibPoly 的版本化许可依据，并发现需要纳入 CLI 库存的 Editline / terminfo / glibc 链。静态补证有进展，**精确 CLI 的完整组成与许可证接受仍未闭合**，不生成 accepted payload。

执行层的边界与拆分见[实施清单](../query/solver-execution-implementation-plan.md)。当前可交付的是补证结果和可审阅工作项；不是生产 executor 或运行资格。

## 对象与来源关联

目标保持前批精确字节：ZIP SHA-256 `2a4c108367f20b0c8990abd6b9535a5d62e08908d471d4671c00734e408f85bc`，成员 `cvc5-Linux-arm64-static/bin/cvc5` SHA-256 `26fa94d71ecb3d4f1458eb06b9b9d4762fb3753cfb5cb9dca6f917fbf4dbe6c7`，27,115,880 bytes。前批[静态观察](cvc5-linux-arm64-preparation-2026-10-17/static-inspection.json)保持字节不变。

[来源清单](cvc5-cli-dependencies-2026-10-17/source-inputs.json)记录每份材料的精确 URL、长度、SHA-256、用途及适用的 Git blob SHA-1；[补充观察](cvc5-cli-dependencies-2026-10-17/dependency-observation.json)绑定检查脚本、前批观察、来源清单、CLI、ELF sections 与实际字符串位置。观察不是 SBOM 完整性声明或公共 acceptance 格式。

| 证据 | 核对结果 | 不能推出 |
| --- | --- | --- |
| cvc5 tag / source | 官方 API 将 `cvc5-1.3.4` 指向 `f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341`；12 份固定提交文件的内容 Git blob 与 tree 一致；包内 COPYING 与固定提交 COPYING 逐字节相同 | 二进制由这些输入可复现地产生；发布者签名已验证 |
| CI 元数据 | [run 25505454189 / job 74849773758](https://github.com/cvc5/cvc5/actions/runs/25505454189/job/74849773758)，`ubuntu:production-arm64`，同一 head SHA，标签 `ubuntu-22.04-arm`，success | CI success 不是本项目工具或资源验收 |
| 发布时间关联 | static package 步骤为 15:36:33–15:36:41 UTC；目标 release asset 创建 / 更新为 15:36:39 / 15:36:41 UTC | 时间重合只是关联，不能替代有摘要的构建来源证明 |
| 实际 ELF | 29 个 section，无 SHT_SYMTAB；`.comment` 含 `GCC: (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0` | 无符号表不能当作“没有链接库”；compiler comment 不认证 libgcc / libstdc++ 的精确包版本 |
| 实际字符串 | CaDiCaL、SymFPU、GMP、LibPoly、Editline、terminfo、glibc、libstdc++ 特征的位置 / 次数已记录 | 字符串存在不是完整链接图；缺失字符串也不能证明组件未链接 |

官方 commit API 对 cvc5 / CaDiCaL 返回 unsigned，对 LibPoly 返回 valid；本批仅保存 API 观察，没有本地验证签名，不升级为已验证来源。静态字符串 `cadical-2.1.3-elevate-f3b21c4` 的后缀与 cvc5 提交前缀相同，不能拿它当作 CaDiCaL 的 Git commit。

详细作业日志 GET 返回 HTTP 403，响应要求仓库管理权限；本批没有使用额外凭据、请求上游授权或发送消息。错误响应的实际字节已绑定到来源清单，**不是**构建日志。停止此获取路径，不将 403 解释为日志不存在或版本已确认。

## 依赖与许可矩阵

表中“配方”指固定 cvc5 提交声明的下载 / 链接方式。除明确强制构建的项外，CMake 可优先接受系统已有库 / 头文件，因此配方 pin 不能自动升级为精确发布二进制的完整输入身份。完整 URL 与摘要均在来源清单。

| 组件 | 已取得的精确依据 | 许可路径 / 归属 | 剩余边界 |
| --- | --- | --- | --- |
| cvc5 1.3.4 | CLI / ZIP 摘要、固定 source commit、同字节 COPYING、包内 AUTHORS | modified BSD，即 BSD-3-Clause；保留版权、条款及免责声明 | source-to-binary 认证与完整链接清单尚缺 |
| MiniSat | cvc5 COPYING 指明内嵌源码；包内 `licenses/minisat-LICENSE` 已绑定 | 包内 MIT 风格许可与原作者归属；不套用 cvc5 主许可 | 按内嵌 cvc5 commit 追溯；未单独证明每个编入对象 |
| CaDiCaL | 配方 `rel-2.1.3-elevate`；官方 tag 解析为 `a384d221a920d473b770df6a7221f35fc5d99e90`；tag / 固定提交 LICENSE 相同；CLI 有对应版本特征 | MIT；Armin Biere、Mathias Fleury、Nils Froleyks、Katalin Fazekas、Florian Pollitt、Tobias Faller 的许可归属在固定文件中 | 仍需实际构建输入与 CLI 的关联；不能以版本字符串证明全来源 |
| SymFPU | 配方固定 `227a7246b8ce513b393cc2645d6d65d3490ea1de`；读取 LICENSE 和 LICENSE-BSD；CLI 有 SymFPU 类型线索 | 上游允许 GPL v3 或 BSD-3-Clause 二选一；non-GPL 路径可采用 BSD-3-Clause，保留许可与作者归属 | 需确认实际使用该头文件版本，排除构建缓存 / 系统路径替代 |
| LibPoly | 配方 0.2.1；tag 解析为 `3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a`；固定 LICENCE 与 `include/poly.h`；CLI 特征及随包 `libpicpoly*.a` | 头部明确 LGPL-3.0-or-later，版权 SRI International；不是无条件宽松许可 | 实际输入版本与可能 patch 仍需关联；静态分发义务单独检查 |
| GMP / GMPXX | 配方 6.3.0；arm64 CI 配置 `-DBUILD_GMP=1`；包内 pkg-config 也写 6.3.0；CLI 有 GMP 线索 | GMP 库提供 LGPL-3.0-or-later 或 GPL-2.0-or-later 路径；本 non-GPL 审阅沿 LGPL 路径；包内 LGPLv3 文本保留 | 尚未获取 / 校验配方指向的源码包；配方一致性不等于完整构建证明 |
| libgcc / libstdc++ | GCC 11.4.0 编译器注记、libstdc++ 字符串；包内 GCC Runtime Library Exception 3.1 与 GPLv3 | cvc5 COPYING 声明 GCC runtime 许可为 GPLv3 加 runtime exception；例外适用条件须随具体构建核对 | 精确 Ubuntu runtime 包、所含源文件 / 例外资格未闭合，不能用 compiler 注记替代 |
| glibc | CLI 中实际 glibc 错误字符串，ELF 静态布局，无动态解释器 | 尚须按精确发行版源码 / copyright 清单确定各组成许可与归属 | 具体版本、Ubuntu patch 级别和静态组成未知；不能仅由 ubuntu-22.04 推定版本 |
| Editline / libedit | arm64 配方明确 `--editline`；`FindEditline.cmake` 使用 pkg-config；CLI 实际含 Editline 线索 | 上游说明为 Berkeley-style；本批不将其替代为该 Ubuntu 制品的完整许可清单 | 精确系统包版本 / copyright 未取得，须进入库存而非归为 SDK-only |
| terminfo / ncurses | FindEditline 在相应 Linux 分支追加 `tinfo`；CLI 有实际 terminfo 路径串 | 待精确包 copyright / 版本，不推定整包一种许可 | 无精确链接 map；暂列有依据的链接候选，需确认实际版本与组成 |
| libbsd / 可能的 libmd 等间接系统库 | CI 安装 libbsd-dev；FindEditline 条件追加 `bsd` | 待实际链接清单；不因安装包存在就宣称链接 | 有条件候选，不能无证据排除，也不能从 libbsd 推定整个传递闭包已经存在 |

GMP 许可选择依据为[GNU MP 6.3.0 官方说明](https://gmplib.org/manual/Copying)。LibPoly 的版本化[头部授权](https://github.com/SRI-CSL/libpoly/blob/3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a/include/poly.h)与[许可正文](https://github.com/SRI-CSL/libpoly/blob/3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a/LICENCE)共同确定 or-later 路径；仅看一份通用 LGPL 文本不足以确定这一点。Editline 官方[项目说明](https://thrysoee.dk/editline/)用于确认项目族和关联，不把其最新发布当作本 CLI 版本。

SDK / JNI / JAR 仍只作为随包库存；执行镜像计划只用 CLI 与自有 bootstrap。Java、Python 构建绑定、libfl 等 CI 安装项不会仅因安装或随包就被列为 CLI 已链接组件；反之，静态嵌入 CLI 的库不能通过“不复制对应 `.a`”从许可范围移除。

四项下载配方另有固定 archive SHA-256，已由检查器从源码提取到补充观察：CaDiCaL `15e1e82f…`、SymFPU `ff22e37d…`、LibPoly `f9920afc…`、GMP `ac28211a…`（完整值见 JSON）。本批**未下载这四个源码归档**，不将声明摘要写成项目重算摘要，也不启动这些配方中的安装 / 构建命令。

## 静态分发与本地诊断的区分

本批没有把第三方库链接进 RadishAxiom，也没有分发 CLI / 镜像，因此没有改变项目 Apache-2.0 或用户生成产物的许可边界。后续本地诊断接受范围应明确限定，不顺带接受对外分发。

若未来分发静态 CLI 或包含它的镜像，须按实际组成保留归属 / 许可，并检查 LGPL combined work 的对应源码、重新组合 / 链接材料等要求；“non-GPL”、只复制 ELF、或有上游源码链接都不能代替这些条件。[LGPLv3 第 4 节](https://raw.githubusercontent.com/SRI-CSL/libpoly/3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a/LICENCE)规定相关选择；GCC runtime exception 也不覆盖所有其他库。本批不作整包再分发合规通过结论。

## 剩余缺口与有界接续

| 缺口 | 最小所需材料 | 结束条件 |
| --- | --- | --- |
| B1：实际系统库身份 | 该精确作业的构建配置 / 链接 map / dpkg 版本清单及包 copyright，或绑定同一 CLI 摘要的发布者组件清单 | 能列全 libedit / tinfo / libc / compiler runtime 及实际间接依赖；不能用同平台当前包代替 |
| B2：实际依赖输入 | 同一构建的 CaDiCaL / SymFPU / Poly 选择结果与输入摘要；GMP 及必要 patch 关联 | 配方、缓存 / 系统覆盖、实际 CLI 之间关系明确；不要求本批复现整个构建 |
| B3：接受记录范围 | 在 B1 / B2 满足后补固定许可 / 归属材料与工具接受 schema / 生成链审阅 | 仅接受精确 CLI 的后续受控本地执行输入；执行仍单独授权，分发另审 |

当前公开日志路径因 403 停止；不请求管理员权限、不自动联系上游，不从此转入 GCC / headers / 全 guest 构建取证。下一步需要的是上述精确缺失材料；若取得不了，保持 not-accepted，并审阅是否另选具备完整来源材料的精确构建。换制品 / 自行构建是新的工具身份与任务范围，不在本批自动执行。

## 生成与验证

原始来源仅保存在 `.tmp/solver-cli-licenses-2026-10-17/`，仓库保存自有观察、索引和复核脚本，不复制上游源码或许可证正文。[补充检查脚本](../../scripts/inspect-cvc5-cli-dependencies.py)使用标准库，复用前批 ZIP / ELF 检查，验证来源长度 / SHA-256 与适用 Git blob，提取配方 / CI 元数据和实际 CLI 特征；不访问网络或执行载荷。

```bash
python3 scripts/test-inspect-cvc5-cli-dependencies.py
python3 scripts/inspect-cvc5-cli-dependencies.py \
  .tmp/solver-preparation-2026-10-17/cvc5-Linux-arm64-static.zip \
  .tmp/solver-cli-licenses-2026-10-17 \
  .tmp/solver-cli-licenses-2026-10-17/dependency-observation-recheck.json
./scripts/check-repo.sh
git diff --check
```

输出路径必须尚不存在。重新获取来源时沿索引的精确 URL / commit，写入各自 `file`，先核对摘要；GitHub API 运行状态 / 签名说明可能变化，若原始响应不可恢复，应报告重跑身份差异，不改预期摘要迁就新响应。当前原始响应及 403 已本机保留。

本批在 shell URL 未引用时遇到 glob 拒绝，修正引用后沙箱代理连接失败，再按权限流程取得官方文件；网页抓取的 cache miss / 超时不算来源通过。最初 LibPoly `src/poly.h` 路径 404，核对 tree 后改为实际 `include/poly.h` 并固定提交。所有来源为只读 GET，没有触发 CI、安装或执行上游代码。

实际验证：3 项合成边界测试通过，25 份来源 / 获取观察的长度与摘要核对通过，真实 ZIP 的补充重检结果与持久 JSON 逐字节相同，4 项检查器 / 输入绑定一致。2,086 份既有源码、契约、规范与前批静态观察和 `6593254` 字节一致，214 个本地文档链接目标存在。仓库检查通过（2,648 文件），`git diff --check` 通过；日志在 `.tmp/solver-cli-licenses-2026-10-17/check-repo.log`。

本批 8 个文件未提交，`dev` 相对未刷新的本地 `origin/dev` ahead 6；没有暂存其他改动或改变文件权限。新增临时来源 / 诊断约 3.5 MiB，前批 ZIP 与失败材料保持。未重跑 Rust workspace：本批无 Rust、依赖或旧规范修改，前批结果仍按原记录引用，不外推为执行层验证。没有后台执行器、镜像 / 探针、solver、系统配置或 push 动作。
