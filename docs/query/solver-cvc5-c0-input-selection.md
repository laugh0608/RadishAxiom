# cvc5 C0：固定源码与 SDK 候选输入选择

日期：2026-10-17。状态：`partial-selection / blocked-on-sdk-metadata / not-accepted`。用途：供实施者和主代理审阅 D3 C0 已选输入、实际依据及剩余精确阻断；接续[构建候选方案](solver-cvc5-build-candidate-plan.md)。本文不是安装或构建入口，不接受新工具、许可证、SDK、运行资格或分发。

本轮固定五项源码归档目标，并选择一个有限二进制 SDK 来源：Debian 12 bookworm、`20230612T000000Z` snapshot、`arm64`（工具数据可为 `all`）。**只固定了发行版、快照与待解析包角色；没有取得快照索引，不能声称 SDK 的包版本、文件或闭包已经选定。C0 未完成，`build_ready=false`。** 不递归重建 GCC 或整个 guest；快照是否实际包含所需文件也未验证，不把时间戳 URL 当成存在性证明。

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

## 单一 SDK 来源及未解析输入

主来源固定为 `https://snapshot.debian.org/archive/debian/20230612T000000Z/`，suite `bookworm/main`。不使用当前 bookworm、Ubuntu、镜像 tag、宿主 `/usr` 或在线 apt 求解作替代。未来元数据入口限该快照的 `dists/bookworm/InRelease` / `Release`、`main/binary-arm64/Packages.xz` 与 `main/source/Sources.xz`；签名可信根、Release 到索引的 hash 及时效策略须另审。没有在本轮预先接受 Debian keyring 或关闭签名验证。

以下是限定的**待解析包名候选**，不是已验证发行包存在性或文件归属。每组 JSON 均为 `selection=unresolved`，版本、精确包 URL、源包、声明包摘要和实际 raw hash 均为 `null`。取得索引后只闭合这些工具及其 `Depends/Pre-Depends`、明确选择的 alternatives / essential 运行需求，不装推荐项、不引入桌面或完整 guest；发现新生成器 / 依赖须先补清单。

| 角色 | 待从固定快照核对的包名 | 必须冻结的实际内容 |
| --- | --- | --- |
| C/C++ | `gcc-12`, `g++-12`, `cpp-12`, `gcc-12-base` | compiler 路径 / triplet / specs / 默认搜索；GCC 12 路线本身尚未得到包索引确认 |
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

每个包将来须固定 `Package/Version/Architecture/Filename/Size/SHA256/Source`，再关联 `Sources` 中 `.dsc`、orig 与 Debian diff / tar 的 URL、hash、签名及 copyright；不能只选 compiler 三个包便声称 SDK 闭包。包声明 hash 仍只是元数据，实际包原字节 hash 在授权取得并重算前保持 `null`。实际安装、解包到 SDK、执行工具、构建检测程序也不在本轮授权。

## 实际查询失败与差异停止线

本轮沙盒 Python `urllib.request.urlopen` 对固定快照 `Release` 的只读查询返回 `URLError: [Errno 1] Operation not permitted`。随后只针对 Release / Packages / Sources 元数据的提权请求等待 **1062.0 秒**后被主代理中断以收口，无成功或网络执行输出；复核 `.tmp/cvc5-c0-2026-10-17` **不存在**，没有部分索引或依赖包可认证。停止该路径，没有重试、换渠道或取得源码包 / 安装包。

另以 web 查看[Debian 当前 g++-12 官方包页](https://packages.debian.org/bookworm/g%2B%2B-12)，页面报告 `12.2.0-14+deb12u1`；该页面是当前 bookworm 的信息，不是所选快照证据，未填入 SDK 版本栏，也没有可重算的 HTTP 原字节。web 对固定快照 Release 返回不可访问。工具返回的失败文本为本轮观察，不宣称捕获了远端错误响应原字节或签名。

新候选相对原 CLI `.comment` 中 Ubuntu GCC `11.4.0-1ubuntu1~22.04.3` 明确变化：发行版、GCC 主版本路线、glibc/CRT、libstdc++/libgcc、Binutils、libedit/tinfo/bsd/md 及构建工具均将重新选择。原 glibc 和系统库精确版本本就未知，不能编造逐版本等价。它们会改变新 bytes、优化、ABI、启动行为、内存页、NSS/locale 文件依赖及信号兼容；新的 source-to-object / map / ELF 核对和 E0、E4、E5 独立阻断继续适用。特别要验证继承阻塞信号 mask、W syscall、静态装载和原 128 MiB / 6 s 资源；任何不适配均停止，不增限或换库。

语义功能沿既定 Production / static / non-GPL / Editline / Poly / GMP / CaDiCaL / SymFPU；完整 `configure.sh`、`ConfigProduction`、Helpers 与生成树尚未取得，不能宣称有效宏展开已冻结。已留存 `CMakeLists` 能确认 Python 解释器是必需工具，并在静态分支关闭 Python bindings；Java 对 CLI 生成头及对象的影响尚未闭合，因此本批不要求全 JDK / JAR，也不假造“已证明可关闭 Java”。先取得同 commit 完整源码，审阅 CLI 目标依赖与选项 diff，再决定是否需要绑定工具。`ENABLE_SAFE_MODE` 的构建值不能因运行参数而改开（会关闭 Poly）。可选 CryptoMiniSat / Kissat / MPFR 仍须 Production 展开确认。

范围有限的 imported-path 构建 patch 仍不存在，`source_patch=null`；不能从部分 Find 模块拼一个未审的完整 patch。已有 Poly sed / 条件 patch、CaDiCaL makefile 生成等保留在候选方案要求中。源码取得后保存实际 diff、前后 tree、生成工具与 imports，不以“只改构建”跳过兼容审阅。

## 后续取得计划及本轮离线检查

本轮不申请或执行下载。未来须先补快照元数据并汇总精确包大小 / 来源 / license / 命令，再向项目所有者单独说明原包取得、SDK 组装、工具执行与构建的精确范围；主代理主持设计与验收。选择不等于接受，原授权不自动延伸为下载 / 安装 / 编译 / 镜像 / 探针 / solver / 系统修改 / commit / push。

待审获取 argv 形式为 `curl --fail --location --max-time 180 --output <本项唯一文件> <记录中的精确URL>`，每项零重试、零备用源；此处不是可执行批次脚本。归档目标逐项固定为 `.tmp/cvc5-c0-acquisition-2026-10-17/{cvc5,cadical,symfpu,libpoly,gmp}.source-archive`；包名未解析前不生成猜测的包 URL 或命令。未来入口必须实施字节上限（仅 curl 时限不够），校验 hash、解包安全及许可后才进入 C1。

规划上限：cvc5 64 MiB、四依赖各 32 MiB（合计 192 MiB）；索引合计 28 MiB；SDK 包暂按最多 512 MiB、对应源码最多 1 GiB。网络阶段暂估 10–30 分钟，均为未测量预算，不是精确发行体积或授权；索引取得后须用实际 Size 求和更新，越限停止，不自动增加。构建仍沿方案 4 jobs / 8 GiB / 20 GiB / 90 分钟单独审查。原包、索引、日志与检查结果只落本批目录，清理须按实际解析的精确路径另定，不碰旧 ZIP / 历史取证或整个 `.tmp`。

实际已运行：

```text
python3 scripts/generate-cvc5-c0-input-selection.py
python3 scripts/check-cvc5-c0-input-selection.py
python3 scripts/test-cvc5-c0-input-selection.py
```

检查器接受的只是固定候选草案一致性，结果明确 `draft_consistent=true / build_ready=false`；实际重核 29 份留存观察、5 项源码目标、16 组 unresolved SDK 输入。11 个测试覆盖 false acceptance、未取得 raw hash 冒充认证、伪 SDK 版本、重复 component / JSON key、预算漂移与超量。该检查器与生成器共享本批选择数据，不是独立来源认证、构建验证器或公共 acceptance schema。材料缺失 / 改变使重核失败，不能用本轮生成记录覆盖原文件。

仍阻断：快照签名与索引、全部 SDK 精确包版本和闭包、完整源码与生成器 imports、有效选项展开 / 差异、实际 patch、原包 / tree / SDK 内容清单 / 许可证接受。未完成 C0，也未进入 C1–C5；本轮没有下载依赖、安装、构建 Linux 制品或镜像、运行探针 / solver、修改系统、提交或推送。
