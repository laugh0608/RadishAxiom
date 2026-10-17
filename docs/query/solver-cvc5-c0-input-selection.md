# cvc5 C0：固定源码与 SDK 元数据输入选择

日期：2026-10-17。状态：`sdk-metadata-selected / blocked-on-configuration-and-acceptance / not-accepted`。用途：供实施者和主代理审阅 D3 C0 已选输入、实际依据及剩余精确阻断；接续[构建候选方案](solver-cvc5-build-candidate-plan.md)。本文不是安装或构建入口，不接受新工具、许可证、SDK、运行资格或分发。

五项源码归档目标保持。SDK 唯一来源为 Debian 12 bookworm、`20230612T000000Z` snapshot、`arm64` / `all`。本轮按明确授权取得 Release / InRelease / Packages / Sources 元数据，固定 **170 个二进制包、472 条依赖关系及 99 个精确源包版本**；16 组角色的 51 个根包加 23 个 Essential 包参与解析。**元数据选择已闭合；完整配置、输入接受与构建条件尚未闭合，C0 整体仍未完成，`build_ready=false`。** 没有取得任何依赖包或源码归档，也不递归重建 GCC 或整个 guest。实际执行及独立复核见[本批验收](../records/2026-10-17-cvc5-c0-sdk-metadata.md)。

原 CLI 的 `not-accepted`、B1/B2 缺口及摘要保持；本选择不补证原 Ubuntu 发布作业。Debian / GCC 12 路线相对原 Ubuntu / GCC 11 是待接受的构建候选变化。SDK 受信任输入及其来源认证仍待接受，摘要也不能消除 compiler / linker 信任。

## 固定源码与已重核材料

私有[输入记录](../records/solver-cvc5-c0-2026-10-17/input-selection.json)由 [C0 生成入口](../../scripts/generate-cvc5-c0-input-selection.py)离线生成。输入是两份已提交的 source-inputs 索引及其 `.tmp` 留存原文件；本轮逐字节重核 **29 份**材料的长度与 raw SHA-256，连同索引本身摘要写入记录。它们是部分源码 / API / 许可观察，不是五个完整源码包，也不是签名或链接认证。

| 输入 | 固定版本 / commit | 精确获取目标 | 依据与未取得项 |
| --- | --- | --- | --- |
| cvc5 | `1.3.4` / `f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341` | [同 commit 归档](https://github.com/cvc5/cvc5/archive/f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341.tar.gz) | 已留存 commit/tree；完整归档未取得，声明归档 hash 也未知；内嵌 MiniSat 及全部许可树须随完整源码复核 |
| CaDiCaL | `rel-2.1.3-elevate` / `a384d221a920d473b770df6a7221f35fc5d99e90` | [原配方归档](https://github.com/arminbiere/cadical/archive/rel-2.1.3-elevate.tar.gz) | tag 解析来自已留存 API；原配方声明 SHA-256 `15e1e82f7f9a9da0e97070cb8ac41d5b32139f65d54f72d2ff84849b0466ef92` |
| SymFPU | `227a7246b8ce513b393cc2645d6d65d3490ea1de` | [固定 commit 归档](https://github.com/cvc5/symfpu/archive/227a7246b8ce513b393cc2645d6d65d3490ea1de.tar.gz) | 原配方声明 SHA-256 `ff22e37dbc133120ada5760878974811737bec65b12a8883f92b1ed9e3f96e99` |
| LibPoly | `0.2.1` / `3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a` | [原配方归档](https://github.com/SRI-CSL/libpoly/archive/refs/tags/v0.2.1.tar.gz) | tag 解析来自已留存 API；原配方声明 SHA-256 `f9920afc876f998633348b9cbfcf180757ada48cc872040256c60ad0707b5a0f` |
| GMP | `6.3.0`；该归档没有本轮已知 Git commit | [原配方目标](https://github.com/cvc5/cvc5-deps/blob/main/gmp-6.3.0.tar.bz2?raw=true) | URL 含浮动 `main`，内容以原配方声明 SHA-256 `ac28211a7cfb609bae2e2c8d6058d66c8fe96434f740cf6fe2e47b000d1c20cb` 固定；不匹配即停，不修改期望值 |

所有归档 `status=not-obtained`，实际 `bytes/raw_digest=null`；配方期望 hash 与项目重算 hash 分列，不能互抄。CaDiCaL MIT、SymFPU BSD 选项及 Poly LGPL 事实沿[既有版本化材料](../records/2026-10-17-cvc5-cli-dependencies.md)；这些事实不等于本批完整输入、使用范围或分发许可已接受。GMP 源包许可与对应源码仍须实际取得核对。

## 单一 SDK 来源与精确元数据选择

主来源固定为 `https://snapshot.debian.org/archive/debian/20230612T000000Z/`，suite `bookworm/main`。不使用当前 bookworm、Ubuntu、镜像 tag、宿主 `/usr` 或在线 apt 求解作替代。本轮元数据入口限该快照的 `dists/bookworm/InRelease` / `Release`、`main/binary-arm64/Packages.xz` 与 `main/source/Sources.xz`；Release 到两份压缩索引的 SHA-256 / 长度已与实际字节核对，InRelease 明文与 Release 一致。签名可信根、签名验证和历史时效策略尚未接受；本轮没有安装 keyring 或执行签名验证。

以下是已从固定索引解析的根包角色，**不是包内文件归属或工具可执行路径的验证结果**。详细精确版本、包路径 / URL、声明大小 / SHA-256、Source 关联、依赖边和选择理由保存于[SDK 清单](../records/solver-cvc5-c0-2026-10-17/sdk-selection.json)。未取得包的实际 raw digest / bytes 仍为 `null`，许可和工具接受仍为 `not-accepted`。解析覆盖全部 `Depends/Pre-Depends`、显式替代项 / Provides、Essential 运行基线与已选包的 Conflicts / Breaks，不纳入 Recommends / Suggests，也不递归展开 Sources 的 Build-Depends。发现完整 cvc5 源码所需的新生成器时仍须补清单。

| 角色 | 已在固定快照选定的根包名 | 后续仍须核对的包内内容 |
| --- | --- | --- |
| C/C++ | `gcc-12`, `g++-12`, `cpp-12`, `gcc-12-base` | 显式版本化 compiler 路径 / triplet / specs / 默认搜索；不能假定 `gcc` / `g++` / `cpp` 别名存在 |
| Binutils | `binutils`, `binutils-aarch64-linux-gnu`, `binutils-common` | `as`, `ld.bfd`, `ar`, `ranlib`, `strip`, `readelf`, `nm`, `objdump` |
| GCC runtime | `libgcc-12-dev`, `libstdc++-12-dev`, `libgcc-s1`, `libstdc++6` | `crtbegin/end`, `libstdc++.a`, `libgcc.a`, `libgcc_eh.a` 与 compiler 运行库；区分工具运行依赖与最终嵌入对象 |
| glibc / UAPI | `libc6`, `libc6-dev`, `libc-dev-bin`, `linux-libc-dev` | 启动对象、静态 libc/libm/pthread/dl/rt、头文件、linker scripts、对应源码 / Debian patch；不改 musl |
| Editline | `libedit-dev`, `libedit2` | `histedit.h`, `libedit.a`, `libedit.pc`；`.pc --static` 必须取得并复核 |
| terminfo | `libncurses-dev`, `libtinfo6` | `libtinfo.a`, `.pc` / headers；是否读 terminfo 数据另做实际判断 |
| BSD / MD | `libbsd-dev`, `libbsd0`, `libmd-dev`, `libmd0` | `.a`、头文件、`.pc` 与传递依赖；声明不代替 link map |
| CMake / Make | `cmake`, `cmake-data`, `make` | modules / generator 与完整工具运行闭包 |
| Python | `python3`, `python3-minimal`, `python3.11`, `python3.11-minimal`, `libpython3.11-stdlib`, `libpython3.11-minimal` | 解释器及生成脚本真实 imports；不自动 pip / venv 安装 |
| pkg-config | `pkgconf`, `pkgconf-bin`, `libpkgconf3` | 显式固定可执行文件，不依赖宿主 alias / alternatives |
| Shell / 文本 | `dash`, `bash`, `coreutils`, `sed`, `grep`, `gawk`, `findutils`, `diffutils`, `patch` | shell、配方变换、文件与摘要工具 |
| 解包 / 检查 | `tar`, `gzip`, `bzip2`, `xz-utils`, `file`, `libmagic1`, `libmagic-mgc` | 各解压器、ELF 辅助检查及 magic 数据；解包路径/类型另限 |

每个二进制包已固定 `Package/Version/Architecture/Filename/Size/SHA256/Source`，并关联 Sources 中精确版本的 `.dsc`、orig 与 Debian diff / tar 文件声明。`Built-Using` / `Static-Built-Using` 也进入对应源码检查；本次选中包均未声明这两类额外项。99 个源包共对应 321 个去重文件；没有读取 `.dsc` 正文、源码、签名或 copyright。包声明 hash 仍只是元数据，实际包原字节 hash 在授权取得并重算前保持 `null`。实际安装、解包到 SDK、执行工具、构建检测程序也不在本轮授权。

主要版本如下，完整清单只以 SDK 机器记录为准：

| 输入 | 固定快照声明版本 |
| --- | --- |
| GCC / G++ | `12.2.0-14` |
| Binutils | `2.40-2` |
| glibc / libc6-dev | `2.36-9` |
| Linux UAPI (`linux-libc-dev`) | `6.1.27-1` |
| Editline / ncurses | `3.1-20221030-2` / `6.4-4` |
| libbsd / libmd | `0.11.7-2` / `1.0.4-2` |
| CMake / Make | `3.25.1-1` / `4.3-4.1` |
| Python 3.11 / pkgconf | `3.11.2-6` / `1.8.1-1` |

替代项按声明顺序选择首个可满足项，优先真实包，再选已选 provider / 名称排序；版本按 Debian epoch / upstream / revision 比较。`:any` 仅接受明确 `Multi-Arch: allowed`，不把单架构环境当成忽略限定的理由。全部已选关系可满足且未发现 Conflicts / Breaks 矛盾。Essential 闭包会纳入 usrmerge、PAM / login、procps / util-linux 和 Perl 等；这不等于已审阅其安装副作用或已得到可直接组装的 rootfs。

## 获取历史与差异停止线

前批沙盒 Python `urllib.request.urlopen` 对固定快照 `Release` 的只读查询返回 `URLError: [Errno 1] Operation not permitted`。随后只针对 Release / Packages / Sources 元数据的提权请求等待 **1062.0 秒**后被主代理中断以收口，无成功或网络执行输出；复核 `.tmp/cvc5-c0-2026-10-17` **不存在**，没有部分索引或依赖包可认证。停止该路径，没有重试、换渠道或取得源码包 / 安装包。

前批另以 web 查看[Debian 当前 g++-12 官方包页](https://packages.debian.org/bookworm/g%2B%2B-12)，页面报告 `12.2.0-14+deb12u1`；该页面是当前 bookworm 的信息，不是所选快照证据，未填入 SDK 版本栏，也没有可重算的 HTTP 原字节。web 对固定快照 Release 返回不可访问。工具返回的失败文本为本轮观察，不宣称捕获了远端错误响应原字节或签名。

本批的元数据联网授权取代前批该路径的停止状态。首次请求和两次接续只访问固定快照及其实际返回的同域内容地址；本地守卫先后拒绝 Release 文件名和索引摘要文件名这两种跳转形式，均在读取对应正文前停止。离线确认目标属于同一元数据、索引地址末段精确等于 Release 声明 SHA-256 后才继续已捕获的 Location，没有重发初始请求或换源。一次子代理提权请求等待 277 秒后被主代理中断，未返回执行会话或网络输出；随后由主代理执行。实际原字节共 **18,722,419 bytes**，请求、时间、摘要和保留路径见[元数据观察](../records/solver-cvc5-c0-2026-10-17/metadata-observations.json)及[执行历史](../records/solver-cvc5-c0-2026-10-17/metadata-execution-history.json)。历史 fetch 执行时的脚本摘要未捕获；清单中的源码绑定只标识当前离线验证器，不冒充当时下载器版本。

新候选相对原 CLI `.comment` 中 Ubuntu GCC `11.4.0-1ubuntu1~22.04.3` 明确变化：发行版、GCC 主版本路线、glibc/CRT、libstdc++/libgcc、Binutils、libedit/tinfo/bsd/md 及构建工具均将重新选择。原 glibc 和系统库精确版本本就未知，不能编造逐版本等价。它们会改变新 bytes、优化、ABI、启动行为、内存页、NSS/locale 文件依赖及信号兼容；新的 source-to-object / map / ELF 核对和 E0、E4、E5 独立阻断继续适用。特别要验证继承阻塞信号 mask、W syscall、静态装载和原 128 MiB / 6 s 资源；任何不适配均停止，不增限或换库。

语义功能沿既定 Production / static / non-GPL / Editline / Poly / GMP / CaDiCaL / SymFPU；完整 `configure.sh`、`ConfigProduction`、Helpers 与生成树尚未取得，不能宣称有效宏展开已冻结。已留存 `CMakeLists` 能确认 Python 解释器是必需工具，并在静态分支关闭 Python bindings；Java 对 CLI 生成头及对象的影响尚未闭合，因此本批不要求全 JDK / JAR，也不假造“已证明可关闭 Java”。先取得同 commit 完整源码，审阅 CLI 目标依赖与选项 diff，再决定是否需要绑定工具。`ENABLE_SAFE_MODE` 的构建值不能因运行参数而改开（会关闭 Poly）。可选 CryptoMiniSat / Kissat / MPFR 仍须 Production 展开确认。

范围有限的 imported-path 构建 patch 仍不存在，`source_patch=null`；不能从部分 Find 模块拼一个未审的完整 patch。已有 Poly sed / 条件 patch、CaDiCaL makefile 生成等保留在候选方案要求中。源码取得后保存实际 diff、前后 tree、生成工具与 imports，不以“只改构建”跳过兼容审阅。

## 后续取得计划及本轮离线检查

本轮仅取得上述四份元数据。未来须继续补完整配置与许可 / 来源接受，再向项目所有者单独说明原包取得、SDK 组装、工具执行与构建的精确范围；主代理主持设计与验收。选择不等于接受，原授权不自动延伸为下载 / 安装 / 编译 / 镜像 / 探针 / solver / 系统修改 / commit / push。

待审获取 argv 形式为 `curl --fail --location --max-time 180 --output <本项唯一文件> <记录中的精确URL>`，每项零重试、零备用源；此处不是可执行批次脚本。归档目标逐项固定为 `.tmp/cvc5-c0-acquisition-2026-10-17/{cvc5,cadical,symfpu,libpoly,gmp}.source-archive`；包 URL 已由固定索引精确关联，但这些 URL 不构成下载授权。未来入口必须实施字节上限（仅 curl 时限不够），校验 hash、解包安全及许可后才进入 C1。

规划上限：cvc5 64 MiB、四依赖各 32 MiB（合计 192 MiB）；索引合计 28 MiB；SDK 包暂按最多 512 MiB、对应源码最多 1 GiB。网络阶段暂估 10–30 分钟，均为未测量预算，不是精确发行体积或授权；本批索引声明的 170 个包合计 **120,455,832 bytes**，321 个对应源码文件合计 **567,050,311 bytes**；均在原预算内。它们是声明大小总和，不是已下载字节或实际解包占用。越限停止，不自动增加。构建仍沿方案 4 jobs / 8 GiB / 20 GiB / 90 分钟单独审查。原包、索引、日志与检查结果只落本批目录，清理须按实际解析的精确路径另定，不碰旧 ZIP / 历史取证或整个 `.tmp`。

实际已运行：

```text
python3 scripts/cvc5-c0-sdk-metadata.py metadata-verify
python3 scripts/cvc5-c0-sdk-selection.py resolve
python3 scripts/cvc5-c0-sdk-selection.py verify
python3 scripts/generate-cvc5-c0-input-selection.py
python3 scripts/check-cvc5-c0-input-selection.py
python3 scripts/check-cvc5-c0-sdk-independent.py
python3 scripts/test-cvc5-c0-sdk-metadata.py
python3 scripts/test-cvc5-c0-sdk-selection.py
python3 scripts/test-cvc5-c0-input-selection.py
python3 scripts/test-cvc5-c0-sdk-independent.py
```

输入清单升级为私有 `0.2`，旧 `0.1` 必须显式重新生成；不悄悄解释为已解析 SDK。选择检查器核对生成器一致性、SDK 记录摘要及未接受边界；另有不导入生产解析器的[独立复核入口](../../scripts/check-cvc5-c0-sdk-independent.py)，从原始索引重新派生并核对真实包集、关系、来源和声明大小。二者均不是签名认证、构建验证器或公共 acceptance schema。实际计数、负例及失败修正见本批验收。材料缺失 / 改变必须失败，不能以记录摘要替代原字节。

仍阻断：快照签名信任 / 历史时效政策、完整源码与生成器 imports、有效选项展开 / 差异、实际 patch、原包 / tree / SDK 内容清单 / 许可证与受信任工具接受。SDK 元数据选择已闭合，C0 整体未完成，也未进入 C1–C5；本批没有下载依赖包或源码归档、安装、构建 Linux 制品或镜像、运行探针 / solver、修改系统或 push。F2 已先提交为 `bf197ad`，本批元数据工作保留未提交。
