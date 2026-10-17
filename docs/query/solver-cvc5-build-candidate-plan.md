# cvc5 1.3.4 可追溯构建候选方案

日期：2026-10-17。状态：`planned / blocked-on-inputs / not-accepted`。[ADR 0030 D3](../adr/0030-solver-bootstrap-ffi-and-build-provenance.md#d3e0-公开来源不足时的下一候选)已接受准备此方案；本文的工具、包、patch、构建参数与新产物尚未接受。用途：给实施者及验收者提供一次有界受控构建的输入闭合、执行顺序与停止线。本文不提供可直接运行的构建脚本，不授权下载、安装、编译、镜像或载荷执行，也不接受对外分发。

## 候选路线与身份

候选保持 cvc5 `1.3.4`、源码提交 `f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341`，构建 Linux AArch64 LE、glibc / GCC C++ runtime、Production、静态 CLI；保留 Editline、GMP、CaDiCaL、SymFPU 与 LibPoly 功能面。glibc 路线用于减少与原发布 CLI 的运行库差异，不把 bootstrap 的 musl 候选迁给 solver。新候选的固定快照元数据已选择 GCC `12.2.0-14` / glibc `2.36-9`，详见[C0 输入选择](solver-cvc5-c0-input-selection.md)；包原字节和工具接受尚未完成。这些版本不能倒填为原 CLI 的构建输入。

新 CLI 必须按实际新 bytes 登记独立身份、接受记录与来源链，不能替换原 CLI 或追认原来源。原 ZIP SHA-256 `2a4c108367f20b0c8990abd6b9535a5d62e08908d471d4671c00734e408f85bc`、成员 `bin/cvc5` SHA-256 `26fa94d71ecb3d4f1458eb06b9b9d4762fb3753cfb5cb9dca6f917fbf4dbe6c7` 继续 `not-accepted`；其 B1 / B2 缺口按[前批补证](../records/2026-10-17-cvc5-cli-dependencies.md)及[有界后续复核](../records/2026-10-17-cvc5-provenance-followup.md)保留。本路线建立新构建的来源关联，不声称复现原发行 bytes。

当前可以固定的是源码提交、四项声明配方、候选功能面与闭合方法。完整五项源码及实际归档摘要现已取得，Production 和构建 patch 已进入[本批静态审阅](../records/2026-10-17-cvc5-c0-source-review.md)。SDK 包内容、受信任工具接受、实际配置探测与链接闭包仍未闭合，**现在不能形成执行许可所需的精确命令**。本批不运行上游脚本；历史四归档审批中止事实保留，当前五源码取得来自后续明确授权。

## 已有依据与输入账本

依据限于已留存的[依赖来源索引](../records/cvc5-cli-dependencies-2026-10-17/source-inputs.json)、[静态观察](../records/cvc5-cli-dependencies-2026-10-17/dependency-observation.json)、[后续来源索引](../records/cvc5-provenance-followup-2026-10-17/source-inputs.json)及其绑定的本地原字节。其 raw digest / Git blob 用于复核已有材料，没有重新解释为发布者签名、源码包取得或 binary 关联。本方案最初仅使用留存材料；C0 接续已按后续授权取得固定快照元数据并闭合已选 SDK 根包的依赖关系；原包 / 配置 / 来源接受继续分开，见下述接续。

下一批须先形成私有输入清单：每项记录角色、来源 URL / 固定提交或包版本与架构、获取状态、实际 raw SHA-256 / 字节数、源包与二进制包关联、许可证 / copyright 路径、必要归属、使用路径及接受决定。未取得的实际摘要用 `null` 并使清单不可执行；不放置伪摘要或能绕过检查的占位脚本。清单正文、生成器、原输入及其摘要一起审阅；不是新的公共 acceptance schema。

| 输入 / 产物角色 | 候选固定依据、取得状态与许可边界 | 构建前必须补齐 |
| --- | --- | --- |
| cvc5 与内嵌 MiniSat | 上述固定 commit；完整归档和 tree 已取得，7,066 个文件与此前留存 Git tree 内容一致。cvc5 为 BSD-3-Clause；MiniSat 沿同提交内嵌源码和独立 MIT 风格许可 | 源码 / 许可清单已形成；签名信任及实际编译对象的来源关联仍须接受 |
| CaDiCaL | `rel-2.1.3-elevate`，ref 已解析为 `a384d221a920d473b770df6a7221f35fc5d99e90`，实际重定向为 `refs/heads/rel-2.1.3-elevate`；完整归档及 MIT 许可材料已取得 | 原配方归档摘要、展开 tree 与归档声明 commit 已核对；仍须固定生成 makefile / flags，含 `getc_unlocked`、`closefrom` 检测结果及对应宏 |
| SymFPU | `227a7246b8ce513b393cc2645d6d65d3490ea1de`；完整归档、LICENSE / LICENSE-BSD 已取得，候选沿 BSD-3-Clause 选项 | 归档 / 头文件 tree 摘要已固定；仍须编译依赖文件确认使用这些头而非系统副本；不能因仅含头文件而漏库存 |
| LibPoly / Polyxx | `0.2.1`，tag 已解析为 `3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a`；完整归档已取得；主许可 / 头文件写 LGPL-3.0-or-later，但附带 Debian copyright 标签为 GPL-3+，许可接受保留歧义 | 原包、全部 patch / 改写及前后 tree 摘要；`libpicpoly.a` / `libpicpolyxx.a`、GMP 绑定与对应源码；保留 LGPL 边界 |
| GMP / GMPXX | `6.3.0` 原配方归档已取得并匹配固定摘要；核心库有 LGPL 路径，构建辅助 / 文档还包含 GPL、例外与 GFDL，按文件审阅 | 实际归档、源码许可 / copyright 清单、C / C++ 静态库和头文件；GMP `main` URL 只作定位，内容须匹配已固定摘要 |
| Editline / libedit | 保留 `USE_EDITLINE=ON`。现有 Find 通过 pkg-config 获取；精确版本、源包和二进制包的元数据已固定；实际包、patch 与 copyright 尚未取得 | 选择并审阅一个新候选的精确版本 / 来源 / 摘要与完整许可，固定 `.pc` 及静态库；不能拿最新上游 Berkeley-style 说明替代该包许可 |
| terminfo / ncurses | Linux Find 明确追加 `tinfo`；新候选包版本已在 C0 固定，实际组成未知，也并非已确认原 CLI 的完整依赖 | 固定提供 `libtinfo.a` 的包 / 头文件 / 源包 / patch / copyright；判断是否还需 ncurses 对象或数据，实际新增须入清单 |
| libbsd / libmd 及其他间接项 | 原配方可条件追加 `bsd`，安装记录不是链接证明。新候选先将两者列为需闭合的候选，新候选包版本已固定，许可文件尚未取得 | libedit / tinfo / bsd 的静态依赖闭包、包身份与许可；若实际不链接某项，用显式依赖声明和 link map 共同排除，不能仅因主链接行未写而排除 |
| glibc / CRT / Linux UAPI headers | 候选保留 glibc；`crt1.o` / `crti.o` / `crtn.o`、libc / libm / pthread / dl / rt 等包版本 / 对应源文件已按 C0 固定，实际文件选择、头文件内容及补丁尚未核对 | 精确 sysroot 归档与逐文件包归属、源包 / patch / copyright 关联；按实际包核对许可及例外，不将整个 sysroot 标成一种 LGPL；旧版本独立库与合并版本差异不得默认处理 |
| GCC / libstdc++ / libgcc / Binutils | 原 CLI 的 GCC 11.4.0 注记只是历史线索。新候选 compiler、linker、assembler、ar / ranlib / strip / readelf / nm、`crtbegin` / `crtend`、运行库包版本已按 C0 固定；工具路径、包内文件摘要及默认行为未知 | 取得精确可信工具包、目标 / ABI、默认 specs 与搜索目录、启动对象和静态运行库；按文件核对 GPL / GCC Runtime Library Exception 等。编译器及其依赖作为显式 trusted 输入，不递归重建 GCC 或整个 guest |
| 构建工具与生成器 | CMake、GNU Make、Python 及所需模块、shell、sed、patch、tar / 解压器、pkg-config、文件 / 摘要检查工具均须固定；精确包及 Depends / Pre-Depends / Essential 元数据闭包已固定；完整源码发现须补 `python3-pyparsing` 与 `m4`，见当前 C0 选择；实际包内文件与运行闭包仍待核对 | 逐包版本 / 架构 / 实际摘要 / 来源 / 许可与命令路径；完整源码会揭示的生成脚本和模块一并闭合；不运行 pip / apt 在线解析 |
| Java / Python bindings 条件输入 | 原 CI `--all-bindings` 仅作配置比较基线；static 自动关闭 Python bindings，Java 无 CLI 反向依赖，候选显式关闭两种 bindings，详见[Production 审阅](solver-cvc5-production-source-review.md) | 不新增 JDK / JAR / bindings 工具；Python 3.11 / pyparsing 为独立 CLI 生成角色，实际包内容与 API 可运行性仍须接受，不随 bindings 裁剪移除 |
| 构建基底与执行平台 | 隔离的 Linux AArch64 LE 只读根文件树 / SDK / sysroot；尚无已接受的精确 rootfs 或镜像摘要 | 固定各包、组装入口、根树摘要、OS / 内核 / CPU 特征与执行宿主；既有 OrbStack 仅为诊断候选，不因此取得 E4 资格。不得使用浮动 `ubuntu:22.04` 或当前 runner 镜像推历史事实 |

四归档的声明 URL / SHA-256 如下；本批项目重算值已逐项匹配这些**配方期望值**，实际 CLI 关联仍无。cvc5 归档另有观察摘要和 Git tree 一致性核对；详见[源码记录](../records/solver-cvc5-source-review-2026-10-17/source-inputs.json)。摘要匹配不等于签名或输入接受。

| 组件 | 声明 URL | 声明 SHA-256 |
| --- | --- | --- |
| CaDiCaL | `https://github.com/arminbiere/cadical/archive/rel-2.1.3-elevate.tar.gz` | `15e1e82f7f9a9da0e97070cb8ac41d5b32139f65d54f72d2ff84849b0466ef92` |
| SymFPU | `https://github.com/cvc5/symfpu/archive/227a7246b8ce513b393cc2645d6d65d3490ea1de.tar.gz` | `ff22e37dbc133120ada5760878974811737bec65b12a8883f92b1ed9e3f96e99` |
| LibPoly | `https://github.com/SRI-CSL/libpoly/archive/refs/tags/v0.2.1.tar.gz` | `f9920afc876f998633348b9cbfcf180757ada48cc872040256c60ad0707b5a0f` |
| GMP | `https://github.com/cvc5/cvc5-deps/blob/main/gmp-6.3.0.tar.bz2?raw=true` | `ac28211a7cfb609bae2e2c8d6058d66c8fe96434f740cf6fe2e47b000d1c20cb` |

## 固定配置与兼容性

比较基线是已有固定 CI 的 `ubuntu:production-arm64`：`production --auto-download --all-bindings --editline -DBUILD_GMP=1`，static 分支追加 `--werror --static`，使用 ccache 并 strip。本候选交付仅为 CLI 及必需生成输入；不自动扩为完整 SDK / JAR 重建。新候选保留 Production 与 CLI 功能选择，主动改变的是输入取得 / 选择与留证机制。同 commit 的 `configure.sh`、`cmake/ConfigProduction.cmake`、Helpers / deps-helper 和生成树已取得并进行[静态配置审阅](solver-cvc5-production-source-review.md)；下表保留构建前要求，静态推导与未来真实配置检测分开，不把 `IGNORE` 或默认 OFF 直接当最终有效值。

| 选项组 | 候选要求及兼容影响 / 停止条件 |
| --- | --- |
| Production、safe / stable / assertions / statistics / tracing / muzzle | 静态结果为优化级 3、statistics 开、assertions / debug symbols / tracing / muzzle / unit testing 关；safe / stable 原始值为 `IGNORE`，候选显式 OFF，完整矩阵见 Production 审阅。未来仍须冻结真实 cache、配置头和优化 flags。`ENABLE_SAFE_MODE` 编译配置必须保持 Production 路线，不能为匹配运行时 `--safe-mode=safe` 而打开：现有源码会因此关闭 Poly。statistics / tracing / muzzle 会影响输出和资源，不能为减依赖或提速改变。展开与预期不一致先审阅 |
| `BUILD_SHARED_LIBS=OFF`、`STATIC_BINARY=ON` | 保留静态 solver 目标；不构建原 CI 的 shared SDK 分支不代表关闭 CLI 语义。最终仍须检查 ELF，参数本身不能证明静态。不得改 musl、libc++、动态库或使用宿主库绕过失败 |
| `ENABLE_GPL=OFF`、`USE_CLN/USE_GLPK/USE_COCOA=OFF` | 对齐原 non-GPL 候选的明确许可 / 功能边界；保留 GMP 与 Poly。不能借此排除 LGPL 组成，也不提出 GPL 路径来规避输入缺口；若固定 Production 展开要求不同，停止重新决定 |
| `USE_EDITLINE=ON`、`USE_POLY=ON`、CaDiCaL / SymFPU 必需 | 保留交互 / polynomial / SAT / FP 代码，即便当前 QF_UFLIA 不主动用到。`NO_GLOBAL_POLY_CTX` 静态默认 OFF，候选保持，不应用 global-context patch；原静态 Poly 安装目标的 sed 改写仍须保留并登记 |
| CryptoMiniSat / Kissat / MPFR | 完整固定源码确认普通 Production 基线三项均默认 OFF，候选显式冻结 OFF；此选择不是运行兼容验收。若出现它们或任何新库，先补精确源包 / patch / 许可 / 静态闭包，不能仅据本表排除 |
| ASAN / UBSAN / TSAN / Valgrind / coverage / profiling / IPO / debug context / debug symbols | 完整源码静态确认普通 Production 中这些 instrumentation / IPO 条件关闭，候选保持 OFF；不打开 IPO / LTO 或调试配置。编译器 flags 检测仍未执行；strip 前后均留存，不能只保留 stripped bytes |
| `--all-bindings`、docs / tests / examples | 已静态核对 Java/JNI/JAR 无 CLI 反向依赖，候选显式关闭 Java；Python bindings 在 static 原分支自动关闭，候选显式 OFF。docs 默认 OFF，unit testing 随 Production 关闭，其他 tests / Murxla 不是 cvc5-bin 依赖；只构建已审 CLI 目标。Python 3.11 / pyparsing 仍为 CLI 生成输入。该配置差异不承诺原整套发布包等价 |
| `ENABLE_AUTO_DOWNLOAD=OFF`、`USE_PYTHON_VENV`、`BUILD_GMP` | 候选禁止构建期网络与自动依赖安装；依赖先独立离线构建再以固定路径提供，因此拟从内部 `BUILD_GMP=1` 改为导入同 6.3.0 的固定 GMP / GMPXX。这改变构建路径，不允许改变 GMP flags / ABI。venv 自动化用固定工具环境取代，完整脚本必须证明生成结果等价；不兼容则停止，不悄悄开网 |
| 编译器 launcher、并行度、strip / linker / prefix | 移除 ccache / restored deps；固定绝对 compiler、linker、ar、工具路径、链接顺序、目标 CPU / ISA、jobs、生成器、路径映射与 strip 参数。避免 `-march=native`。保留 `--werror`。这些因素可改变 bytes / 性能，因此新身份与 E5 独立，不承诺原 binary 等价 |

运行时十二项参数及顺序保持与[现有请求实现](../../crates/axiom-ir/src/solver.rs)一致：`--safe-mode=safe`、`--strict-parsing`、`--force-logic=QF_UFLIA`、`--lang=smt2`、`--no-incremental`、`--produce-models`、`--dump-models`、`--check-models`、`--produce-proofs`、`--check-proofs`、`--rlimit-per=1000000`、`--tlimit-per=5000`。新 payload 的绑定接入另审；现有 query / P4 profile、旧字节、目标与模型文法不自动迁移或改名。源码同版与构建成功均不能证明这些参数在新运行库 / 继承信号 mask / W 策略下可用。

## 消除系统选择、缓存与隐含 patch

首选将四依赖在固定 SDK 中按已审阅的原配方等价步骤独立构建 / 安装到一次性 prefix；cvc5 只消费这些精确输出。对固定 Find 模块准备一个范围有限的自有构建 patch：不改变 solver 源码语义，只把查找改为带存在性、摘要 / tree 核对的显式 imported 路径，并在缺失时失败，禁止回退到系统或下载。[实际 patch 候选](solver-cvc5-build-patch-review.md)现已形成，包含精确 diff 与前后树摘要；只完成静态核对，没有运行 CMake 或证明构建可行。SDK 文件 / Editline 有序静态闭包尚缺，不能生成可接受的执行 manifest。

1. CaDiCaL、GMP / GMPXX、Poly / Polyxx 均显式指定头文件目录、绝对 `.a` 路径及传递链接关系；SymFPU 指向固定头文件 tree。消除项目 `deps/install` 的自动优先路径；若保留该目录，只能由本批清单生成且启动时为空，不能复用旧 stamp。
2. Editline 的原模块会追加裸 `bsd` / `tinfo`，仅加 `CMAKE_PREFIX_PATH` 不足。固定 `.pc`、`pkg-config` 可执行文件、`PKG_CONFIG_LIBDIR` / sysroot，清除外部 `PKG_CONFIG_PATH`；记录 `--static` 依赖结果，把闭包转成已核对的绝对库路径与固定顺序。原 module 的头文件存在条件分支也须记录，不能为了避开追加项而传空 include 目录。
3. CMake 使用新空 build tree，关闭用户 / 系统 package registry 与宿主环境查找；编译器显式 `--sysroot`，固定所有查找根 / 工具路径，清除 CPATH、CPLUS_INCLUDE_PATH、LIBRARY_PATH、外部 CFLAGS / LDFLAGS、CMake toolchain / preload、launcher 注入。只允许清单内 SDK 头 / 库 / 工具；不导出一个可写宿主 `/usr` 挂载。
4. 用离线、只读 inputs / SDK 与无网络的隔离 build root执行；输出目录单独可写，无 host socket、credentials、runner cache 或历史 ccache。环境固定 PATH、locale / TZ、umask、工作目录、SOURCE_DATE_EPOCH 的来源和 CPU 特征。内核、构建根与 compiler 是显式 trusted 输入；不声称隔离或摘要消除编译器信任。
5. 完整保存 CMake trace / cache / configure 检测、编译依赖文件、实际命令及 linker 搜索 / 追踪结果。对每个读入头、库、启动对象、specs / linker script和生成输入做 allowlist 核对；发现未列文件、自动下载、默认系统库或 cache 命中立即失败。`compile_commands.json` 不覆盖所有外部项目 / 生成工具，不能单独作为完整证明。

还须固定上游的真实变换：CaDiCaL 手工实例化 `makefile.in` 的 sed 替换及宏；GMP C99 / PIC / C++ / 静态配置、构建 triplet 与探测；Poly 的安装目标 sed、可条件启用的 global-context patch与编译器警告 flag 探测；其余源码生成。每项保存入口 / 输入 / 输出摘要、工具及顺序；Windows patch 不适用于此 Linux 目标，不能因文件存在就声称应用。不得把 ExternalProject 的已下载 stamp 或 ccache 作为输入认证。

## 从输入到新 bytes 的留证与验收

每次构建使用唯一批次目录，输出只追加；输入清单先冻结并取得自己的摘要，实际构建记录引用它。输出记录再绑定命令 / 环境 / 日志、返回码、所有中间与最终文件摘要；最终记录不把自身摘要嵌回自身。生成器 / patch / 清单属于自有文件，未来进入仓库；第三方原包、工具包、中间对象与日志放任务专用保留区并给出持久留存决定，不复制进正式文档仓库。

| 检查层 | 必须保存与判定 |
| --- | --- |
| 原包与配置 | 下载原字节、获取记录、实际摘要、展开 tree、许可、patch 前后 tree、生成源码、冻结的有效选项和配置头。来源到生成头 / 对象的依赖路径必须能追溯 |
| 编译 / 归档 | 精确 compiler / assembler、每个 translation unit / 头文件摘要、完整 argv / cwd / 环境、对象摘要、archive 成员顺序 / 重名成员与各成员摘要；保留自建 GMP / Poly / CaDiCaL 以及预编译系统 `.a` 的包归属 |
| 链接 | 完整 link 命令、response file / linker script、绝对输入顺序、link map / cross-reference 与 linker trace、被抽取 archive 成员和触发符号、被丢弃 section / LTO 情况；MiniSat / SymFPU 来源通过对象 / 头依赖复核。系统 `.a` 中未抽取的对象不算 CLI 已嵌入，但整个归档仍是本次输入 |
| 产物静态检查 | strip 前 ELF、debug / 符号材料与最终 ELF的大小 / raw SHA-256，strip 工具 / 参数；ELF64 LE / EM_AARCH64、入口、程序头、segments / sections、无 PT_INTERP / DT_NEEDED、无 RPATH / RUNPATH、无 W+X / executable stack、重定位 / TLS / init / fini / IFUNC / GNU 属性及启动对象清单。可疑动态加载、文件 / locale / terminfo / NSS 依赖须明确记录；“静态 ELF”不证明运行时不读文件 |
| 组成对账 | 每个实际链接对象可归属已固定源码或精确受信任二进制 SDK 包；实际库 / header / 生成器均在清单，声明与 map 双向一致；许可证 / copyright 逐组成归档。`strings`、版本输出和 Build ID 只能补充，不能取代对象 / 输入清单 |
| 独立复核 | 独立只读检查器从原字节重算摘要，解析 map / archive / ELF 与清单，覆盖错对象、额外库、遗漏头、错误 patch、含系统路径、变更选项、截断日志 / response file等拒绝。构建进程自报 success 不足。若另批获准做第二次干净构建，比较 bytes 并解释差异；一次受控构建可建立来源关联，不能声称可复现构建或形式证明 |

本地 E0 接受最少需要：全部实际输入闭合、许可 / 归属与选定使用范围核对、静态产物符合固定装载边界、来源记录与新 ELF 摘要对应、独立复核通过及明确 trusted compiler / SDK 声明。若预编译库只有“可能来源于某包”的猜测、无对应源码 / patch / copyright，不能用编译器信任声明吞掉。E0 接受只允许将新精确工具列为后续受控本地诊断候选，不产生运行资格或公共 Evidence 五态。

## 批次、占用、授权与停止线

| 顺序 | 下一批的具体交付与出口 | 阻断 / 授权 |
| --- | --- | --- |
| C0：冻结候选差异 | [本轮选择接续](solver-cvc5-c0-input-selection.md)已取得五项源码并补审生成工具、Production 与有限 patch；SDK 元数据沿 Debian 12 arm64 固定快照扩选。当前精确计数以 C0 机器记录为准，静态审阅不代替实际配置 | 元数据批已提交 `c2ea5d0`；后续授权取得固定五源码，Production / patch 静态结果见本批记录。SDK 包未取得，许可歧义 / 信任 / 实际配置与链接输入仍阻断，`build_ready=false` |
| C1：输入接受 | 实际原包摘要 / tree / 许可核对，锁定 compiler / SDK / rootfs 包与可信边界；完成有效选项差异逐项决定 | 任一 unknown、版权缺项、可选库闭包未知或 patch 未审即停；不能先安装再决定接受。来源选择不等于允许安装 |
| C2：构建准备 | 提交可审阅离线入口、输入清单校验器、精确 argv / 环境 / 输出目录、无网络设置、资源 / 日志 / map 采集及失败保留 / 清理计划 | 工具安装 / 环境组装、构建环境镜像、实际编译分别说明并授权。CMake try_run / GMP configure 等生成的检测程序也属构建期执行，须写入授权范围；不包含运行 cvc5 `--version` / solver |
| C3：一次受控构建 | 授权后先空目录验证，离线构建依赖再生成 cvc5，保存所有中间 / link map / stripped 前后 bytes、实际占用与失败 | 任一未列输入 / 下载 / 包安装 / 选项漂移、资源耗尽或超时即停止保留；不自动增额重跑，不把新 bytes 放原 CLI 路径 |
| C4：本地 E0 决定 | 静态 ELF、完整组成 / 许可与独立复核闭合后，提交新精确接受记录候选 | 主代理主持验收，项目所有者决定本地范围；未通过则 `not-accepted`。原 CLI 状态不变；不因此执行新 CLI |
| C5：后续运行 | 分别准备 runtime 镜像、E4 实际装载 / 能力 / 信号兼容负例，再按 E5 执行原校准方案 | 镜像构建、宿主探针、`--version` / solver、真实校准与单目标尝试各按已定边界授权；E0 不能替代 ABI / unsafe 审查或 E4 / E5 |

构建占用的首次规划估算为单次最多 4 个并行编译任务、8 GiB 内存、20 GiB 专用可写空间、90 分钟总时限；尚未测量、未承诺足够，执行授权前按实际工具包 / 源码大小核定并提供停止 / 保留方案。这是离线构建预算，**不是运行增限**。运行仍保持 stdin 1 MiB、stdout 4 MiB、stderr 64 KiB、同 cgroup 128 MiB / swap 0 / pids 2、外层 6 s、solver 内部 5 s / 1,000,000 steps；S / B、ELF / memfd、运行库与队列都计入原额度。新 bytes 体积 / 初始页占用若不适配，应报告 E4 / E5 失败，不暗改 limit、功能或 profile。

授权申请必须列已解析的唯一批次目录、精确下载 / 安装 / 构建目标、主要副作用、预计持续时间、输出保留和撤回方式。建议保留原包、输入 manifest、patch、完整构建日志、对象 / map、最终 ELF 及检查结果，直至验收与恢复材料另行确认；清理只针对本批已解析的具体文件 / 目录，不碰原 ZIP、原失败材料、共享工具或整个 `.tmp`。持久归档和镜像是否含第三方材料须各自审阅，不自动上传。

## 本地使用与分发边界

候选仅为受控本地诊断。当前没有把第三方库链接进 RadishAxiom，没有改变项目 Apache-2.0 或用户生成产物的许可。若以后分发静态 CLI、镜像或构建 SDK，须按实际组成单独检查版权 / 许可证、LGPL corresponding source 与 relink / recombination 材料、安装信息适用性、GCC runtime exception 条件及其他各包义务；仅留上游 URL、称 non-GPL 或不复制 `.a` 均不构成分发接受。新本地 E0 接受不替代该决定。

本方案之后已接续 [C0 精确输入选择](solver-cvc5-c0-input-selection.md)与[机器记录](../records/solver-cvc5-c0-2026-10-17/input-selection.json)：固定源码目标与单一 SDK 快照，离线重核 29 份既有材料；随后按明确元数据联网授权完成精确 SDK 选择和独立包级闭包复核，见[本批验收](../records/2026-10-17-cvc5-c0-sdk-metadata.md)。该元数据批已提交为 `c2ea5d0`；随后源码取得、Production / patch 审阅及生成工具补选见[当前批验收](../records/2026-10-17-cvc5-c0-source-review.md)。SDK 包、签名信任、许可接受、实际配置和链接输入仍阻断；未安装、构建、运行探针 / solver、修改系统配置或 push。候选选择与静态审阅不产生工具或运行接受。
