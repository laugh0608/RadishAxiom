# cvc5 C0 构建查找 patch 静态审阅

日期：2026-10-17。状态：`prepared-static-candidate / blocked-on-actual-inputs / not-accepted`。用途：供维护者审阅固定 cvc5 `1.3.4` 归档的依赖发现差异、文本应用证据与停止线；接续[构建候选](solver-cvc5-build-candidate-plan.md)及[完整配置审阅](solver-cvc5-production-source-review.md)。本文不提供安装或构建入口，不接受 SDK、ABI、链接闭包、工具或新 CLI，也不构成分发决定。

## 实际修改与影响

[候选 patch](../../patches/cvc5/1.3.4/explicit-inputs.patch)只面向提交 `f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341`。完整归档及其全部文件已由[源码输入记录](../records/solver-cvc5-source-review-2026-10-17/source-inputs.json)另行绑定；原解包树只读留存。patch 改动 8 个构建文件，未修改 `src/`、`ConfigProduction.cmake`、十二项运行参数、旧 payload 或任何运行资源限值。

| 文件 | 变化及兼容边界 |
| --- | --- |
| `CMakeLists.txt` | 在 `project()` 前验证显式清单，避免先检测编译器再发现缺少输入；移除 GLPK 与 `deps/install` 自动 prefix；在 `ConfigProduction` 后拒绝配置漂移。保留原配置赋值、编译宏、静态链接 flags、目标及顺序 |
| `cmake/FindGMP.cmake` | 用精确头文件根和 `libgmp.a` / `libgmpxx.a` 取代系统查找、探测和内部构建。保留 `GMP` 的 C 库接口；新增独立 `GMPXX` imported target 并传播 `GMP`，现有 CLI 不主动链接该新 target |
| `cmake/FindCaDiCaL.cmake` | 导入精确 `.a` / 头文件，移除版本检测程序与 `ExternalProject`；版本从已经核对源码及归档组成的外部审阅绑定，不能把声明字符串当作库内容证明。Linux 路线不承接 Windows `psapi` 分支 |
| `cmake/FindPoly.cmake` | 导入 `libpicpoly.a` / `libpicpolyxx.a`；保留 `Poly → GMP`、原 `src/CMakeLists.txt` 中 Poly / Polyxx 并列及 GMP 最后链接的顺序，不新增 Polyxx 自动依赖边 |
| `cmake/FindSymFPU.cmake` | 保留 interface target / system include 属性；仅消费固定头文件 inventory，移除系统查找和下载 / 复制路径 |
| `cmake/FindEditline.cmake` | 改为 interface target，按外部审阅明确给定的顺序链接绝对 `.a` imported targets；不执行 pkg-config，不追加裸 `bsd` / `tinfo` / `md` 或 `-l`。允许审阅确有需要的重复 archive；没有默认顺序 |
| `cmake/cvc5-c0-inputs.cmake` | 新增仅用于这一固定候选的清单验证；关闭 CMake 用户 / 系统 package registry、环境查找及 Git package 发现。该文件不组装 SDK、不生成依赖、不安装工具 |
| `cmake/version.cmake` | 精确禁用配置期及 `gen-versioninfo` 子脚本中的 Git 发现，避免归档上溯到 RadishAxiom 仓库。`version-base` 仍为 1.3.4；这是归档身份记录路径差异，不保证与原发行版 `versioninfo` 字节相同 |

原 Find 模块中的系统查找、历史 ExternalProject stamp、自动获取和检测程序路径均完整移除，没有留下“空变量后走原模块”的回退。内部 `BUILD_GMP=1` 变为外部同版本输入；GMP C99 / PIC / C++、CaDiCaL makefile 与检测宏、Poly 安装目标改写和条件 patch 的实际生成过程仍须在独立依赖构建计划中逐项登记。当前 patch 不执行或替代这些过程。

## 私有输入约束

补丁要求 `CVC5_C0_INPUT_MANIFEST` 为规范绝对文件路径，`CVC5_C0_INPUT_MANIFEST_SHA256` 为独立审阅的实际 SHA-256。私有 JSON 标识为 `radishaxiom-cvc5-private-build-inputs / 0.1`，须固定上游提交、`linux-aarch64-le-glibc-gcc12`、四依赖源码版本以及 `reviewed-for-configuration` 状态。CMake JSON 支持要求至少 3.19，既定 SDK 的 3.25 满足该接口；上游整体 minimum 3.16 没有改动。

`header_roots` 精确包含 GMP、GMPXX、CaDiCaL、Poly、SymFPU、Editline 六种角色，每项带规范绝对根路径和全部普通文件的相对路径 / 实际 bytes / SHA-256。必须含对应主要头文件，逐文件重算并检查缺失、额外项、重复、目录逃逸及符号链接。`archives` 至少含 GMP、GMPXX、CaDiCaL、Poly、Polyxx、Editline；其余项必须全部被 `editline_link_order` 消费。每项须有实际 `.a` 绝对路径、bytes / SHA-256；未取得文件、空值或错摘要直接失败，不搜系统库。

`closure_review` 必须另给实际审阅文件的绝对路径、bytes / SHA-256，helper 重算并读取它，要求 `static-closure-and-abi-reviewed` 状态，以及与输入清单完全相符的上游提交、目标、版本、archives、header inventories 和 Editline 顺序。它把审阅材料绑定到实际输入集合；格式检查、文件摘要和状态字段本身不能完成 `.pc --static`、archive 成员、对象 ABI、版本、许可或可信工具审查。原来的 `try_run` / `try_compile` 不会因改成输入声明就被视为已经通过。

**当前没有生成这份输入清单，也没有 closure 审阅文件、SDK `.a`、实际库输出摘要或接受标记。** [patch 机器记录](../records/solver-cvc5-source-review-2026-10-17/patch-review.json)中的 `actual_dependency_manifest` / `actual_sdk_archive_inputs` 为 `null`，`build_ready=false`；任何配置均应先因缺实际输入而停止。Editline / tinfo / bsd / md 的实际包内容和静态传递闭包未知，不能以候选名字或猜测顺序称为闭合。

配置守卫与完整矩阵对齐：保留 statistics、Poly、Editline、static、`TREAT_WARNING_AS_ERROR=ON`；拒绝 assertions、symbols、tracing、muzzle、sanitizers、stable / safe、Valgrind、IPO、coverage / profiling、debug context、非候选可选库、`NO_GLOBAL_POLY_CTX`、bindings / docs 及内部依赖构建的开启。三值选项按原 `OFF / IGNORE` 的有效 false 检查，不改写 cache。launcher 和自定义 prefix / Pythonic / WASM flags 必须为空；压缩调试、RPATH、默认 linker 的 skip / override 开关保持 OFF，语言标准及 extensions 沿原值。原顶层 `TREAT_WARNING_AS_ERROR` 只在 clang-tidy 分支使用，故不能靠该布尔值表示普通编译的 `--werror`；守卫还将两组 `CMAKE_C_FLAGS` / `CMAKE_CXX_FLAGS` 分词，要求精确 `-Werror` token，拒绝 `-Wno-error*` 和 `-w`。实际各目标 / response file / 最终 argv 仍须后续对账。静态宏和开关本身仍不证明产物静态或 ABI 正确。

## 文本应用与验证

自有[只读检查器](../../scripts/check-cvc5-build-patch.py)先绑定来源审阅记录及完整原树，再解析固定八文件 unified diff；每个 hunk 必须在声明行号及原上下文精确匹配，不搜索附近位置、不接受 fuzz / offset。检查器在内存中重建修改并计算完整后树；派生树留在本批独立 `review-tree/cvc5`，没有写入原 `sources/cvc5`。机器记录保存实际 patch bytes / SHA-256、8 个文件前后摘要、完整前后 inventory 摘要及本地生成入口摘要。inventory 是按路径排序的普通文件 `path/bytes/raw_digest/executable` 紧凑 JSON；目录无内容身份，符号链接与特殊文件拒绝。

实际通过：自有检查器、宿主 `git apply --check` 文本 dry-run，以及 [17 项合成测试](../../scripts/test-cvc5-build-patch.py)（使用 `python3 -O`）。覆盖错误 upstream、错误 preimage、禁止 offset / fuzz、截断 hunk / header、路径逃逸、额外 / 重复文件、原树额外文件 / 符号链接、Find 裸查找 / 裸库名残留及虚假接受 / 执行状态。unified diff 的上下文 / 删除行须保留原字节；精确路径 whitespace 属性仅允许这些字节，检查器仍拒绝任何新增行的尾随空格或 tab。它们是离线文本检查，没有运行 CMake 解释器，也没有验证此 helper 的实际配置期行为或链接兼容性。

另对本批实际 patch / 原树的派生副本执行 11 项变异拒绝检查：错误 upstream / 接受 / 执行记录、实际 Find preimage、截断 patch、路径逃逸、额外重复 patch、残留裸查找、patch 摘要篡改、原树文件篡改和额外文件均被拒绝。完成后重算原 7066 文件树确认未变；本地观察的路径 / 摘要绑定在机器记录。Production 审阅者交叉检查了目标传播、变量作用域、完整配置表、closure 和 `-Werror` 守卫；该结论同样限于静态审阅。

没有执行上游脚本、`configure.sh`、CMake、Make、autotools、编译器、探针或 solver；包括 `--help` 在内均未执行。完整源码审阅与此 patch 候选不能升级为构建通过、形式证明、C0 整体完成或 E0 / E4 / E5 接受。

## 剩余停止线与许可

本清单仅覆盖库 / 头文件和相应闭包审阅绑定。完整 SDK 工具、Python 及模块、sysroot / CRT / linker scripts / compiler specs、构建期 shell / 文本工具、环境变量、默认搜索目录、执行隔离、实际读入文件 / 目标跟踪和无网络执行方案仍是 C1 / C2 阻断。registry 关闭和五个 Find 替换不能称为完整 hermetic build；上游其余工具发现路径须按完整配置矩阵处理。环境查找关闭意味着未来须显式提供 `CMAKE_MAKE_PROGRAM` 等工具，不能把本 patch 当作即用构建入口。Editline 的 imported target 列表保留声明顺序 / 重复项，最终 link argv 仍可能受 CMake 展开、去重或传递关系影响，须由 C3 实际 trace / map 对账。后续清单还须由拒绝重复 JSON 键的预检读取，并对普通文件类型 / 只读输入边界复核；CMake helper 不充当文件系统安全沙盒。

patch 的上游上下文与删除内容来自上述 cvc5 固定提交，原版权注记保留，BSD-3-Clause 的 COPYING / AUTHORS 由完整源码许可清单绑定；新私有 helper 为项目自有 Apache-2.0 文本。第三方原归档、原源码及派生源码树没有加入 Git。当前只做本地受控审阅；未来分发 patch、静态 CLI、SDK 或镜像须按实际内容另行保留许可 / 归属并审查 LGPL 等义务，不以本次本地准备替代分发接受。
