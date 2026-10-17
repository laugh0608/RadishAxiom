# cvc5 C0：固定源码与 SDK 元数据输入选择

日期：2026-10-17。状态：`source-static-reviewed / sdk-metadata-selected / blocked / not-accepted`。用途：供实施者和主代理审阅 D3 C0 已选输入、实际依据及剩余阻断；接续[构建候选方案](solver-cvc5-build-candidate-plan.md)。本文不是安装或构建入口，不接受新工具、许可证、SDK、运行资格或分发。

五份固定源码原包已取得，合计 **13,368,905 bytes**，完成受限解包、tree / 许可清点与静态审阅。SDK 唯一来源仍为 Debian 12 bookworm、`20230612T000000Z` snapshot、`arm64` / `all`；仅用前批留存索引离线增选两个必需根包 `python3-pyparsing` 与 `m4`，现为 **172 个二进制包、474 条依赖关系、101 个精确源包版本**，17 组角色的 53 个根包及 23 个 Essential 包参与解析。没有取得 SDK 二进制包或其对应源码包。

**静态审阅与 SDK 元数据选择均有记录，动态有效配置、SDK 内容、输入接受与构建条件尚未闭合，C0 整体未完成，`build_ready=false`。** 本批结果见[源码审阅总验收](../records/2026-10-17-cvc5-c0-source-review.md)。原 CLI 的 `not-accepted`、B1/B2 缺口及摘要保持；本选择不补证原 Ubuntu 发布作业。

## 当前记录与历史边界

私有[输入记录](../records/solver-cvc5-c0-2026-10-17/input-selection.json)由既有 [C0 生成入口](../../scripts/generate-cvc5-c0-input-selection.py)离线生成，升级为 `0.3`；检查器显式拒绝旧 `0.1` / `0.2`，必须重新生成，不能悄悄按新含义解释。原两份 source-inputs 索引及其 **29 份**部分源码 / API / 许可观察继续逐字节重核；新增引用绑定本批完整源码记录、Production 静态审阅记录、patch 审阅记录及 patch 本体的长度 / raw SHA-256。

前批元数据取得、重定向守卫、失败修正和 96 项测试属于[历史验收](../records/2026-10-17-cvc5-c0-sdk-metadata.md)。原 `0.2` 清单与原 SDK 选择可在提交 `c2ea5d0` 重现；本批下载入口已冻结该 `0.2` 清单于 `.tmp/cvc5-c0-acquisition-2026-10-17/input-selection.json`，其摘要由[源码记录](../records/solver-cvc5-source-review-2026-10-17/source-inputs.json)绑定。冻结输入不随当前清单更新，避免下载记录与现行选择之间循环引用。前批 `validation-results.json` 保留发生时事实，本批新增[整合验收机器记录](../records/solver-cvc5-source-review-2026-10-17/selection-integration-validation.json)；当前独立 SDK 报告已按新选择重新生成。

## 已取得的固定源码

| 输入 | 固定版本 / commit | 实际原包 bytes | 原包摘要依据与范围 |
| --- | --- | --- | --- |
| cvc5 | `1.3.4` / `f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341` | 9,279,538 | 未留存发布者期望归档 SHA-256；重算 raw SHA-256，并把全部 7,066 个文件的 Git blob SHA-1 与既有未签名 tree 逐一比对一致 |
| CaDiCaL | `rel-2.1.3-elevate` / `a384d221a920d473b770df6a7221f35fc5d99e90` | 732,469 | 实际 SHA-256 与固定 cvc5 Find 模块声明一致 |
| SymFPU | `227a7246b8ce513b393cc2645d6d65d3490ea1de` | 83,411 | 实际 SHA-256 与固定 cvc5 Find 模块声明一致 |
| LibPoly | `0.2.1` / `3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a` | 629,599 | 实际 SHA-256 与固定 cvc5 Find 模块声明一致 |
| GMP | `6.3.0`；未声明 Git commit | 2,643,888 | URL 含浮动 `main`，内容以原配方期望 SHA-256 固定；实际匹配，未改期望值 |

每项 URL、配方期望摘要、实际摘要、长度及范围以输入记录和[本批源码记录](../records/solver-cvc5-source-review-2026-10-17/source-inputs.json)为准。源码记录分别绑定原包、tree 清点及许可清点。四依赖的期望 hash 匹配、cvc5 的留存 tree 一致性均不等于签名认证、发布作业来源认证或许可证接受；`signature_authentication=not-established`，五项 `license_acceptance=not-accepted`。

完整许可材料已取得并清点，[许可静态审阅](../records/solver-cvc5-source-review-2026-10-17/license-review.md)保留范围与冲突。特别是 LibPoly `debian/copyright` 的 `GPL-3+` 标签与 LGPL 正文冲突、GMP 不同文件的多许可及构建工具范围，仍须精确决定使用 / 嵌入 / 分发接受。内嵌 MiniSat 也在 cvc5 完整树和许可清点内；不因取得源码或上游标注 non-GPL 就自动接受全部树。

## 单一 SDK 来源与精确选择

主来源固定为 `https://snapshot.debian.org/archive/debian/20230612T000000Z/`，suite `bookworm/main`。不使用当前 bookworm、Ubuntu、镜像 tag、宿主 `/usr` 或在线 apt 求解作替代。前批取得的四份元数据为 `InRelease`、`Release`、`main/binary-arm64/Packages.xz` 与 `main/source/Sources.xz`，实际合计 **18,722,419 bytes**；Release 声明的两份压缩索引摘要 / 长度与原字节匹配，InRelease 明文与 Release 一致。原字节和定位链见[元数据观察](../records/solver-cvc5-c0-2026-10-17/metadata-observations.json)及[执行历史](../records/solver-cvc5-c0-2026-10-17/metadata-execution-history.json)。签名可信根、签名验证及历史时效政策仍未接受。

以下为固定索引解析的根包角色，**不等于包内文件归属、可执行路径或兼容性验证**。精确版本、包路径 / URL、声明大小 / SHA-256、Source 关联、关系及理由只以[SDK 清单](../records/solver-cvc5-c0-2026-10-17/sdk-selection.json)为准。所有 SDK 原包实际 `bytes/raw_digest=null`，`package_status=not-obtained`、许可和工具接受仍为 `not-accepted`。

| 角色 | 固定快照的根包名 | 后续仍须核对的内容 |
| --- | --- | --- |
| C/C++ | `gcc-12`, `g++-12`, `cpp-12`, `gcc-12-base` | 显式版本化路径 / triplet / specs / 默认搜索；不假定未版本化别名 |
| Binutils | `binutils`, `binutils-aarch64-linux-gnu`, `binutils-common` | `as`, `ld.bfd`, `ar`, `ranlib`, `strip`, `readelf`, `nm`, `objdump` |
| GCC runtime | `libgcc-12-dev`, `libstdc++-12-dev`, `libgcc-s1`, `libstdc++6` | CRT、静态 libstdc++ / libgcc / libgcc_eh；区分工具运行依赖和嵌入对象 |
| glibc / UAPI | `libc6`, `libc6-dev`, `libc-dev-bin`, `linux-libc-dev` | 启动对象、静态库、头文件、linker scripts、对应源码 / Debian patch |
| Editline | `libedit-dev`, `libedit2` | `histedit.h`, `libedit.a`、`.pc --static` 及真实依赖顺序 |
| terminfo | `libncurses-dev`, `libtinfo6` | `libtinfo.a`、`.pc` / headers 与实际数据文件依赖 |
| BSD / MD | `libbsd-dev`, `libbsd0`, `libmd-dev`, `libmd0` | 静态库、头文件、`.pc`、传递依赖与 link map |
| CMake / Make | `cmake`, `cmake-data`, `make` | modules / generator 与工具运行闭包 |
| Python | `python3`, `python3-minimal`, `python3.11`, `python3.11-minimal`, `libpython3.11-stdlib`, `libpython3.11-minimal`, **`python3-pyparsing`** | CLI 生成器必需解释器 / stdlib / pyparsing；导入及 API 实际运行仍未验证 |
| GMP 汇编生成 | **`m4`** | 固定 GMP arm64 汇编生成链必需；不新增 Autotools |
| pkg-config | `pkgconf`, `pkgconf-bin`, `libpkgconf3` | 显式固定可执行文件，不依赖宿主 alias / alternatives |
| Shell / 文本 | `dash`, `bash`, `coreutils`, `sed`, `grep`, `gawk`, `findutils`, `diffutils`, `patch` | shell、配方变换、文件与摘要工具 |
| 解包 / 检查 | `tar`, `gzip`, `bzip2`, `xz-utils`, `file`, `libmagic1`, `libmagic-mgc` | 解压器、ELF 辅助检查、magic 数据和运行闭包 |

本批新增 `python3-pyparsing 3.0.9-1 all`（声明 138,444 bytes）与 `m4 1.4.19-3 arm64`（276,280 bytes），没有新增其他传递包；新增两条关系、两个源包版本及七个对应源文件，二进制声明总量增加 414,724 bytes，对应源码增加 3,684,597 bytes。Perl 已在原闭包中，没有因此新增根包；不新增 Autotools、Bison、Flex 或 Java。必要性、CLI imports 与 Production 差异见[完整源码静态审阅](solver-cvc5-production-source-review.md)。

解析覆盖全部 `Depends/Pre-Depends`、显式替代项 / Provides、Essential 基线及已选包的 Conflicts / Breaks，不纳入 Recommends / Suggests，也不展开 Sources 的 Build-Depends。替代项、Debian 版本比较、Multi-Arch 与冲突规则保持前批口径。每个二进制包关联精确 Source 版本、`.dsc`、orig、Debian diff / tar 声明；`Built-Using` / `Static-Built-Using` 仍检查，本次无额外声明项。**101 个源包版本共对应 328 个去重文件**，未读取这些文件的正文、签名或 copyright。Essential 包含 usrmerge、PAM / login、procps / util-linux 与 Perl，不等于已接受安装副作用或已得到可组装 rootfs。

主要版本保持 GCC/G++ `12.2.0-14`、Binutils `2.40-2`、glibc `2.36-9`、Linux UAPI `6.1.27-1`、Editline `3.1-20221030-2`、ncurses `6.4-4`、libbsd `0.11.7-2`、libmd `1.0.4-2`、CMake `3.25.1-1`、Make `4.3-4.1`、Python `3.11.2-6`、pkgconf `1.8.1-1`。

## 静态配置与 patch 的边界

完整 `configure.sh`、`ConfigProduction`、Helpers、CLI 生成树及依赖配方已静态审阅，并以逐文件原字节 / 行摘录绑定[Production 机器记录](../records/solver-cvc5-source-review-2026-10-17/production-review.json)。候选继续沿 Production / static / non-GPL / Editline / Poly / GMP / CaDiCaL / SymFPU；Java / Python bindings 显式关闭，CLI 必需 Python / pyparsing 保留，auto-download / pip / venv 路径关闭。`ENABLE_SAFE_MODE` 不能因运行参数而改开（会关闭 Poly）。具体宏、可选功能和原 CI 差异以静态审阅专题为准。状态是 `static-reviewed-not-configured`；未运行配置和生成脚本，静态推导不代表有效动态配置或生成器 API 兼容。

范围受限的 [explicit-inputs.patch](../../patches/cvc5/1.3.4/explicit-inputs.patch)已形成真实 diff，并有[patch 审阅记录](../records/solver-cvc5-source-review-2026-10-17/patch-review.json)绑定本体摘要、变更文件与前后 tree。只做自有文本处理 / 精确应用及 `git apply --check`；没有执行上游 CMake / Make / configure。状态为 `prepared-static-candidate-not-executed`，实际依赖清单与 SDK archive 输入仍为空。patch 不使待取得的 `.pc`、库 / 头文件哈希、目标 ABI、静态库顺序或未来检测程序自动成立。

新候选相对原 CLI `.comment` 的 Ubuntu GCC `11.4.0-1ubuntu1~22.04.3` 明确改变发行版、GCC 主版本路线、glibc/CRT、libstdc++/libgcc、Binutils、Editline/tinfo/bsd/md 与构建工具。原 glibc / 系统库精确版本本就未知，不能编造等价。source-to-object / map / ELF 核对及 E0、E4、E5 阻断继续适用；须验证继承阻塞信号 mask、W syscall、静态装载与原 128 MiB / 6 s 资源，任何不适配均停止，不增限或换库。

## 验证与剩余停止线

当前选择检查器重算旧观察、新源码原包 / 清点、SDK 与静态审阅记录摘要，核对 `0.3` 一致性及未接受边界。另有不导入生产解析器的[独立 SDK 复核](../../scripts/check-cvc5-c0-sdk-independent.py)，从原始留存索引派生包集、关系、来源及声明大小；独立 root set 单独增列两个必需根包。源码与 patch 各有独立 / 专题检查入口。它们均不是签名认证、构建验证器或公共 acceptance schema；材料缺失 / 改变必须失败，摘要不能替代原字节。实际命令、测试计数、输入摘要及本批 delta 见总验收和整合机器记录。

预算不增加：既有源码下载上限合计 192 MiB，元数据 28 MiB；未来 SDK 二进制包最多 512 MiB、对应源码最多 1 GiB。当前声明量分别为 **120,870,556 bytes** 与 **570,734,908 bytes**，均在预算内；这不是已下载或解包占用。构建 4 jobs / 8 GiB / 20 GiB / 90 分钟仍须单独审查。原包、索引和日志留在本批精确目录，没有清理旧 ZIP、历史取证或 `.tmp`。

剩余阻断为快照签名信任 / 历史时效政策、SDK 原包与对应源码 / 内容清单、许可冲突和精确范围接受、受信任 compiler / linker / SDK 接受、动态有效配置与生成兼容、实际 `.pc` 静态闭包 / link map 及 E0/E4/E5。没有取得 SDK 包、安装依赖、执行上游脚本、构建 Linux 制品 / 镜像、运行探针 / solver、修改系统或 push；也未进入 C1–C5。下一步原包下载、SDK 组装、工具执行及构建各自仍需说明精确目标、影响、时间与清理方式并取得对应授权。主代理主持后续设计与验收。
