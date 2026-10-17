# cvc5 C0：Production 与 CLI 生成链静态审阅

日期：2026-10-17。用途：供主代理审阅完整固定源码的配置分支、CLI 生成依赖和候选差异，接续 [C0 输入选择](solver-cvc5-c0-input-selection.md)及[构建候选](solver-cvc5-build-candidate-plan.md)。本文不是 configure / 构建入口，不接受工具、SDK、许可证、产物或运行资格。状态为 `static-reviewed-not-configured-not-accepted`；`build_ready=false`。

本轮只读取五份已审安全解包源码，没有执行上游 `configure.sh`（包括 `--help`）、CMake、Make、Autotools、Python / shell 生成器、编译检测程序或 solver。[来源记录](../records/solver-cvc5-source-review-2026-10-17/source-inputs.json)绑定实际归档 / tree；[配置机器记录](../records/solver-cvc5-source-review-2026-10-17/production-review.json)逐文件保存长度、SHA-256 和行摘录。下文路径相对该记录对应的组件原树；`文件:行` 是真实原树行号。源码字节绑定检查不能独立证明配置推导正确，更不能证明未来动态 effective configuration。

## Production 的静态推导

比较基线是同 commit CI `ubuntu:production-arm64` 的 `production --auto-download --all-bindings --editline -DBUILD_GMP=1`，static 分支另有 `--werror --static`。`configure.sh` 先给 `poly=ON`、`build_shared=ON`，其余大多数变量为 `default`；只把非 `default` 项变成 `-D`。`--all-bindings` 同时选择 Java / Python，`--werror` 还会覆盖导出的 `CFLAGS/CXXFLAGS=-Werror`，因此仅写 `TREAT_WARNING_AS_ERROR=ON` 不能替代原 `--werror` 的编译器 flags（`configure.sh:129–180,322–324,420–518`）。

`Helpers.cmake:180–197` 的三值选项先取 cache `IGNORE`，`cvc5_set_option` 仅在仍为 `IGNORE` 时设置；显式 `-D` 优先。`IGNORE` 在 CMake 条件中为 false，但它仍是原始字符串，不能写成已观察的 cache `OFF`。本表的“关闭”是静态条件分支判定；将来入口可显式冻结 `OFF`，并记录这个规范化差异。`CMakeLists.txt` 先 include `ConfigProduction`，后执行 flags / probes / 依赖 / 编译定义。

| 配置 | 固定基线的静态结果 | 候选要求 / 依据 |
| --- | --- | --- |
| `CMAKE_BUILD_TYPE`、优化级 | `Production`，`OPTIMIZATION_LEVEL=3` | 保持；`ConfigProduction.cmake:12–14`。`-O3` 是否加入仍由 compiler flag 检测决定 |
| assertions / debug symbols / tracing / muzzle / unit testing | 均 `OFF` | 保持；Production:15–26；assertions 关产生 `NDEBUG`，tracing / muzzle 宏不加；顶层还在 assertions 关时强制关 unit testing |
| statistics | `ON` | 保持 `CVC5_STATISTICS_ON`；不为体积 / 性能关闭 |
| `ENABLE_SAFE_MODE`、`ENABLE_STABLE_MODE` | 原始 `IGNORE`，分支关闭 | 显式冻结 `OFF`；不能从运行参数 `--safe-mode=safe` 推导编译 safe mode。顶层:601–614 会在编译 safe mode 开启时关闭 Poly / CoCoA |
| ASAN / UBSAN / TSAN / Valgrind / IPO | 原始 `IGNORE`，分支关闭 | 显式冻结 `OFF`；Production 不启用 IPO。原 CI 未给 `--best` / `--ipo`。若开 IPO，顶层:329–337 的 `check_ipo_supported` 会再决定是否生效，不能预言结果 |
| coverage / profiling / debug context MM / clang-tidy | 默认 `OFF` | 保持；无 sanitizer、gprof、gcov、debug-context 宏。编译器仍执行普通 flags 检测 |
| `ENABLE_PROOFS` | Production 文件有一次 `cvc5_set_option(ENABLE_PROOFS ON)`；顶层未声明该三值 option，其他生产源无消费开关 | 不虚构 `CVC5_PROOFS` 宏或声称这一行证明 proof 已开启；proof 源文件在 `src/CMakeLists.txt` 的无条件源列表，CLI proof 参数仍需后续运行验收 |
| `BUILD_SHARED_LIBS`、`STATIC_BINARY` | static 分支 `OFF`；非 Darwin 静态默认 `STATIC_BINARY=ON` | 保持；`src/main/CMakeLists.txt:75–85` 为 CLI 设置 `-static` 和 static search。是否真的静态须未来 ELF / map 检查 |
| GPL / CLN / GLPK / CoCoA | 默认 `OFF` | 显式冻结 `OFF`；不走 GPL 替代路径；GMP、Poly 许可另审 |
| Editline / Poly | `ON` / `ON` | 保持。Poly 来自 wrapper 的默认 `poly=ON`，不是顶层 `option(USE_POLY)` 默认；绕过 wrapper 直接 CMake 必须显式传 `ON` |
| CryptoMiniSat / Kissat / MPFR | 默认 `OFF` | 显式冻结 `OFF`；此 Production 没有 `--best`。SymFPU 即使 MPFR 开仍无条件必需（顶层:633–643）；本候选保留 SymFPU |
| `NO_GLOBAL_POLY_CTX` | 默认 `OFF` | 保持；不应用 `poly-global-ctx.patch`，但原静态安装目标 sed 必须保留。Windows patch 不适用 Linux |
| C / C++ 标准 | C11 / C++17；extensions 关闭 | 保持。CaDiCaL 原配方另为 C++11；Poly 为 gnu99 / C++11；GMP CFLAGS 原为 `-std=gnu99`，不能顺手统改 |
| 其余声明选项 | `BUILD_CLN/SKIP_COMPRESS_DEBUG/SKIP_SET_RPATH/USE_DEFAULT_LINKER=OFF`；`GLPK_DIR/PYTHONIC_PATH/PROGRAM_PREFIX/WASM_FLAGS` 为空，`WASM=OFF` | 保留默认，显式防止 cache / 环境漂移。static CLI 自身最终 INSTALL_RPATH 为空；不据此擅改其他目标的 RPATH 配置 |
| CPU / ISA / linker | cvc5 没有无条件 `-march=native`；AArch64 分支跳过 mold/gold 检测 | 固定目标 `aarch64`、显式工具路径 / sysroot；`Helpers:26–48` 在 Linux AArch64 把 GMP build triplet 设成 `aarch64-linux-gnu`。GMP configure 的实际 ABI / assembler / flags 尚待检测 |

普通编译选项候选为 `-O3 -Wall -Wextra`、C `-fexceptions`、C++ `-Wsuggest-override -Wnon-virtual-dtor`、共同 `-Wimplicit-fallthrough -Wshadow -Wtype-limits -fno-operator-names`、非 clang-tidy 的 `-fno-extern-tls-init`；生成源另尝试 `-fno-var-tracking-assignments`。这些均经 `add_check_*`，**不能静态承诺每项最终存在**（顶层:253–285、Helpers:80–122、src:1497）。GCC 13 特有的 `-Wno-dangling-reference` 分支不适用拟选 GCC 12。IPO 候选关闭不引入 LTO；未来若漂移即停止重新审阅。

## CLI 与绑定目标的边界

目标链为 `cvc5-bin → main + cvc5 + cvc5parser`；`main → gen-tokens + cvc5-obj + cvc5parser-objs`，`cvc5-obj → cvc5base/cvc5context + gen-expr/gen-versioninfo/gen-options/gen-rewrites/gen-tags/gen-theory`。parser 对象依赖 `gen-expr/gen-options`。来源为 `src/main/CMakeLists.txt:36–57,86`、`src/CMakeLists.txt:1502–1510`、`src/parser/CMakeLists.txt:61–75`。

顶层先 `add_subdirectory(src)`，后按 `BUILD_BINDINGS_JAVA` 才进入 Java 子目录（顶层:687–700）。Java 的枚举生成器输出 `.java`，`javac -h` 输出 JNI headers，`cvc5jni` 使用这些 JNI 文件并单向链接 `cvc5/cvc5parser`，JAR 依赖 JNI / 库；CLI / 核心对象没有反向依赖 Java / JAR / JNI 输出。Java 子目录的 include / link 设置为子目录或 `cvc5jni` target 范围，没有回写核心源列表。故本候选可明确选择 `BUILD_BINDINGS_JAVA=OFF`；这是一项真实配置差异，避免 Java `find_package` / JVM settings 调用及独立 SDK / JAR 目标，不声称原整套发布包等价（`src/api/java/CMakeLists.txt:18–102,168–204,295–308,370–397`）。

Python 在顶层 static 分支自动关闭（:689–696），故显式 `BUILD_BINDINGS_PYTHON=OFF` 与该分支一致；解释器仍是 CLI 的必需生成工具。`BUILD_DOCS/BUILD_DOCS_GA` 默认 `OFF`；mkoptions 仅在 docs 开时增加文档 byproduct。tests 框架存在，`check/build-tests` 是显式目标，API/binary 子树 `EXCLUDE_FROM_ALL`，unit 关闭；CLI 不依赖它们。examples 没有进入顶层子目录列表，不存在可假称已冻结的顶层 `BUILD_EXAMPLES=OFF`。Murxla 外部项目虽有 URL，但 `EXCLUDE_FROM_ALL ON` 且仅 fuzz 目标依赖，不进入 `cvc5-bin`；未来入口只能构建已审目标，不执行 `all/check/install-for-murxla/fuzz-murxla` 扩大范围。

## 每个 CLI Python 生成器的 imports

只解析源码 AST，没有 import 或执行第三方脚本。完整逐模块行号 / imports 见机器记录 `python_generators`。

| 入口 / 本地模块 | imports 分类及作用 |
| --- | --- |
| `src/options/mkoptions.py` | stdlib `os,re,sys,textwrap,tomllib`；Python <3.11 才用额外 `tomli`。当前固定 3.11 不需该 fallback |
| `src/expr/{mkexpr,mkkind,mkmetakind}.py` | stdlib `argparse,sys,os,datetime`（mkmetakind 另 `re`）、`tomllib` / 同条件 `tomli`；本地 `theory_validator` 只 import stdlib `os` |
| `src/theory/{mkrewriter,mktheorytraits}.py` | stdlib `argparse,sys,os,datetime`（traits 另 `re`）、`tomllib` / 同条件 `tomli`；本地 `expr.theory_validator` |
| `src/rewriter/mkrewrites.py` | stdlib `argparse,logging,os,sys,collections,dataclasses,pathlib`；本地 `rw_parser,node,util` |
| `rw_parser.py` / `node.py` / `rule.py` / `util.py` | 唯一额外必需模块 `pyparsing`；本地 `node,rule,util`；其余 stdlib `enum,os,shutil,sys,subprocess`；rule 无 import |
| `src/base/collect_tags.py` | stdlib `argparse,glob,os,re,shutil,subprocess`；若目标文件已存在会调用外部 `diff`，因此保留 `diffutils` |

`src/rewriter/CMakeLists.txt:14` 无条件检查 `pyparsing`，:63–90 的 `gen-rewrites` 进入 `cvc5-obj`，故现有 Python 解释器角色不足，须增加固定 snapshot 的 `python3-pyparsing`。API 版本可运行性仍未验证，不能因包元数据闭合而宣称生成兼容。`Helpers:277–313` 的模块检查会在 auto-download 开时 pip install；候选必须关闭该路径，缺模块即失败。

其他生成输入：`gen-tokens` 调用 shell 脚本内 `grep|sed|sort`（`src/main/gen-token-header.sh:11–13`）；`gen-versioninfo` 调用 CMake script；`gen-tags` 即使 tracing 关闭仍生成头。expr / theory 生成器使用 `date.today().year`；`rw_parser` 的输出生成会调用 `util.format_cpp`，只有 PATH 找到 `clang-format` 才启动格式化（util:27–34）。候选固定 PATH 中不提供 clang-format，保留未格式化分支并保存输出摘要；不能无意借用宿主 formatter。此选择影响生成 bytes，未声称与历史生成文件字节相同。

## 五源码的未来工具闭包

| 工具 / 角色 | 静态判定及来源 |
| --- | --- |
| Python 3.11 + `python3-pyparsing` | CLI 必需；解释器既有，新模块新增 SDK root；`tomllib` 使用固定 3.11 stdlib，不新增 `python3-tomli` |
| GNU m4 | 新增 SDK root；GMP `configure:25604–25655` 在发现 `.asm` 时要求可用 m4；AArch64 case :4411–4417 选 `mpn/arm64`，其中实际 `.asm`；`mpn/Makefile.in:742–768` 对这些文件预处理。不能为避免 m4 关闭 assembly |
| shell / sed / grep / awk / coreutils / diff / GNU Make / CMake / compiler/binutils | 既有根角色；CLI tokens/tags、CaDiCaL makefile / build.hpp、GMP configure / libtool / Makefile 均使用。工具路径仍待包内容取得后固定；不依赖 gcc/g++未版本化 alias |
| Autoconf / Automake / 外部 Libtool / Perl | 本候选无需重生成 GMP 的 `configure/Makefile.in/aclocal.m4/config.in/ltmain.sh`；这些已在归档。GMP `configure:3709–3726` 默认 maintainer mode 关闭，`Makefile.in:797–824` 再生依赖加 `@MAINTAINER_MODE_TRUE@` 后被注释；不触碰或删除它们，也不靠 touch 掩盖再生。Perl 在已选 SDK 的间接闭包仍保留；不据此称它是 CLI 必需生成器 |
| Bison / Flex | cvc5 parser 的 CMake 列表直接编译现成 C++ lexer/parser，没有生成命令。GMP configure 会查找 yacc/lex，但用途为 demos/calc；归档已有 `calc.c/calc.h/calclex.c`，非 maintainer 规则 `am__skiplex/am__skipyacc=test -f $@ ||`；该目录 `all-am` 仅 Makefile，calc 为 EXTRA_PROGRAM，故本候选不需 Bison/Flex root。若改维护模式、缺失生成文件或增建 demo，立即重新闭包 |
| Texinfo / makeinfo | 原 `FindGMP.cmake:105–107` 已显式 `MAKEINFO=true`；保留这一原配方选择，不新增文档构建工具。GMP `.info/version.texi` 文件已随包提供；未来记录实际 makeinfo 是否被拦截，不能借此漏报文档目标 |
| Java/JNI/JAR/Cython/setuptools/pip/venv | Java / Python bindings 的工具，不在本候选 CLI 目标链；显式关闭绑定及 auto-download/venv 后不新增包。关闭 binding 不移除 Python CLI 解释器 / pyparsing |
| Git / clang-format / IWYU / clang / Murxla | 不是 CLI 必需工具。版本路径补丁禁 Git，避免 `.tmp` 原树向上发现 RadishAxiom `.git`；固定 PATH 不提供 formatter/IWYU。`cmake/IWYU.cmake` 若发现 IWYU 会配置时再找并执行 clang，故也须记录其不存在；Murxla 不构建 |

GMP 仍必须在后续获准构建时运行归档 `configure`，生成 `config.status/config.h/gmp.h/Makefile/config.m4/libtool`，执行 compiler/ABI/函数/assembler 检测；“自带 configure”只免去 Autoconf 再生。GMP Makefile:1455–1497 还编译 / 运行 `gen-fac/gen-sieve/gen-fib/gen-bases/gen-trialdivtab/gen-jacobitab/gen-psqr`。LibPoly CMake 检测 `open_memstream` 并配置 `include/version.h`；该上游规则写入源码树，未来须使用独立可写工作副本、保留原树，不能把本批原树改成已接受构建输出。

CaDiCaL 按原 `FindCaDiCaL` 手工实例化 makefile，不运行其 configure；保留 `-fPIC -O3 -DNDEBUG -DQUIET -std=c++11` 及 getc_unlocked/closefrom 两项 compiler 检测控制的 `NUNLOCKED/NCLOSEFROM`。`makefile.in:67–78` 会生成 `build.hpp`，脚本读取 VERSION、调用 compiler `--version`、date/uname、get-git-id。原 `get-git-id.sh` 使用裸 `git show`，同样存在父仓库污染风险；未来隔离根中不提供 Git，以空 ID 的原 warning 分支保留，不以 RadishAxiom SHA 假充 CaDiCaL identity。date / uname / hostname 没有读取 `SOURCE_DATE_EPOCH`，不能仅设置该变量就宣称构建可复现；实际 header / 时间 / 主机观察必须留存。SymFPU 仅复制 core/utils 头文件，无编译生成器。

## 明确候选差异与剩余停止线

| 差异 | 原路径 → 候选路径 | 已知影响 / 尚待验证 |
| --- | --- | --- |
| 自动获取 / venv | auto-download ON、venv 默认 ON → 两者 OFF | 固定模块和依赖输入，不再 pip / 自动 ExternalProject 取得；缺输入失败。生成文件实际等价尚未运行验证 |
| GMP | `BUILD_GMP=1` 内部 ExternalProject → `BUILD_GMP=OFF`，导入独立按原 6.3.0 配方产生的 GMP/GMPXX | 保留 gnu99、PIC、C++、static、build triplet 与原检测；导入二进制与 ABI 尚不存在。上游 GMP target仅直接导出 libgmp，不能顺手给 CLI 加入libgmpxx |
| 绑定 | 原 `--all-bindings` → Java/Python OFF | Java/JNI/JAR 独立子图已静态排除；Python static自动OFF；不保证历史整包 SDK 等价 |
| 查找 / patch | 系统/deps/install/pkg-config/缓存/stamp选择 → 显式原包tree和未来静态输入清单 | 实际 patch 另审；Editline `.pc --static`、库成员和顺序未取得，不能预填“已闭合” |
| Git 版本信息 | `find_package(Git)` 及祖先仓库检测 → 自有 patch 禁 Git | 避免串入 RadishAxiom 分支 / commit / dirty；版本基数仍1.3.4，versioninfo bytes有真实差异 |
| launchers / clocks / formatter / paths | CI ccache与环境发现 → 无 launcher、新空树、固定PATH/locale/TZ/umask/工具路径 | ccache在原 workflow外部注入；不能用同源码声称同binary；时钟与CaDiCaL date/uname输入仍需保存 |

尚未验证：实际 CMake flags、配置头和 compiler/platform 检测；GMP ABI/assembly选择与生成执行；CaDiCaL 两项宏；Poly warning flag / open_memstream；GMPXX、Editline静态闭包 / pkg-config输出、SDK包内容/许可/签名/信任；全部编译、链接、ELF和原资源下的运行兼容。关闭可选库的静态决定不消除系统默认库/CRT或运行时读文件边界。

下一停止线为输入 / patch / 配置差异人工审阅与 C1 接受。[自有生成入口](../../scripts/generate-cvc5-production-source-review.py)只组装人工配置结论、原树摘要及 AST imports；[只读检查器](../../scripts/check-cvc5-production-source-review.py)重核全部必需矩阵项、来源记录/归档身份、tree inventory对应文件、字节与摘录，不能把手写结论升级成独立语义证明。[12 项合成测试](../../scripts/test-cvc5-production-source-review.py)覆盖删除矩阵、错身份、重复键、源/记录同时篡改及符号链接等拒绝，实际通过。未来 CMake/try_compile/try_run/GMP configure/生成器全部属于另批构建授权。仍保留 Production/static/non-GPL/Editline/Poly/GMP/CaDiCaL/SymFPU、原十二项运行参数、1 MiB/4 MiB/64 KiB、128 MiB/swap0/pids2、外层6秒及solver5秒/1,000,000steps，不扩功能、改profile、换GPL路径或增限。

[查找 patch 审阅](solver-cvc5-build-patch-review.md)已按本表交叉检查：原 `src/` 中 Poly/Polyxx 并列和 GMP 最后链接保留，额外 GMPXX target 没有自动加入 CLI；Editline manifest中的顺序/重复项被保留为 target list，最终 link argv仍须另批 trace核对。helper变量作用域与五个Find的使用在静态审阅中未发现新的阻断；未运行CMake解释器，不能据此宣称配置成功。完整工具绝对路径、CMake modules/SDK/CRT/specs和实际读取闭包仍属C2停止线。
