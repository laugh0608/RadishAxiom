# C2 离线构建入口与输入预检

日期：2026-10-23。用途：交接本批可审阅、尚不执行的构建配方、输入检查和留证规则。接续[输入准备](../query/solver-cvc5-input-preparation.md)，不接受 LibPoly、SDK、构建宿主或新 solver，不授权安装、配置、构建或发送上游消息。

## 已交付及边界

新增[离线入口](../../scripts/prepare-cvc5-offline-build.py)、[检测项目文本](../../scripts/cvc5-build-support/CMakeLists.txt)、[拒绝测试](../../scripts/test-prepare-cvc5-offline-build.py)及[固定配方](solver-cvc5-c2-2026-10-23/offline-build-recipe.json)。入口只有 `prepare`、`check` 和 `bind-inputs`；没有执行子进程、网络、解包写入、安装、构建或清理模式。配方中的命令是数据；其操作序列和审阅门禁供后续 C3 实施者消费，本批没有实现或调用实际隔离调度器。

**C2 的离线配方与预检已形成；执行资格仍未形成。** 配方准备成功不意味着 `build_ready=true`。C1 的固定版本许可缺口仍在；实际 SDK 组装、工具 / 宿主接受、检测结果、依赖输出与 ABI / 静态闭包、完整输入读取观察和构建资源监控仍须分别满足。不能通过修改 JSON 中一个布尔值来绕过这些边界。

原 C1 获取清单绑定了旧生成器字节，因此本批新增下游消费者，未改写被冻结的 `cvc5-build-preparation.py` 或既有 patch / manifest 格式。继续复用其清单验证、已有源码 / patch 检查器、包内路径解析器，以及 `check-cvc5-build-inputs.py` 的严格清单检查；没有第二套包选择或依赖版本。

## 离线使用与退出码

固定配方的摘要见[验证记录](solver-cvc5-c2-2026-10-23/validation.json)。重建时输出必须不存在，候选 batch 目录也必须未占用；入口不会创建 batch 或组装 SDK。

```bash
python3 scripts/prepare-cvc5-offline-build.py prepare \
  --batch-id candidate-2026-10-23 \
  --output /absolute/new-review-output.json
```

`--output` 是审阅文件目的地，不是构建目录。`prepare` 对实际输入完成只读检查后创建配方，返回 0；任何错字节、非规范路径、目录占用或材料漂移返回 1，不生成部分成功配方。

```bash
python3 scripts/prepare-cvc5-offline-build.py check \
  /absolute/path/to/offline-build-recipe.json \
  --sha256 <另行核对的配方摘要>
```

`check` 从真实材料重建整个配方并作逐类型比较，字段增删、命令 / 环境 / 资源变化、把 `false` 改成 `0` 等均拒绝。完整匹配时输出 `preparation_check=passed`，但仍以 **退出码 2** 报告 `execution_ready=false` 和 `build_ready=false`；不能把该状态当成 C3 可运行。CLI 参数错误也会返回 2，应同时查看结构化结果而非只看退出码。

`bind-inputs` 是后续依赖审阅完成后的只读入口：在未来映射后的命名空间中消费真实 `/work/review/build-inputs.json` 及独立提供的摘要，复用现有严格字节 / 审阅声明绑定检查，核对配置矩阵和入口身份，再生成带真实 manifest 摘要的主目标 argv。它不生产许可 / ABI 审阅声明，也不启动 CMake；仍返回阻断状态。当前没有这份真实清单，因此本批没有对真实依赖执行该绑定；测试使用明确的合成材料及受测检查器边界。

## 输入与布局

本批真实预检重新核对 **500 文件 / 691,605,464 bytes**，并复核五个来源归档、全部留存源码条目和八文件 patch 的前后树。SDK 的内容库存只扫描了 binary / `.dsc` / Debian patch / native source 共 374 项，不能误当成 500 项；未重复展开其余 orig 归档。全部 500 项原字节仍单独核对。

SDK 命令路径绑定 21 个实际文件 / 符号链接解析结果，包括版本化 GCC / G++ 12、binutils、CMake、Make、Python 3.11、pkgconf、m4、gawk 和 shell。完整 172 包库存仍是间接工具、头文件、CRT、specs、链接脚本与库的来源映射；21 个路径不是完整执行闭包已验证的声明。

| 范围 | 固定安排 |
| --- | --- |
| 宿主候选目录 | `artifacts/cvc5-build-candidate-2026-10-23`，在配方中绑定规范绝对路径；本批未创建 |
| 隔离根 `/` | 未来另行审阅的 SDK payload 组装结果，冻结为只读；不运行 apt / dpkg maintainer scripts，不借宿主 `/usr` |
| `/recipe` | 只读自有入口、实际 Python 本地导入闭包、配置审阅记录及检测项目；具体映射列在配方，不挂载整份仓库或凭据 |
| `/work/src/<id>` | 五源码的独立工作副本；先核对原树再变换，不修改原取证树 |
| `/work/prefix` | 各依赖独立前缀；真实输出审阅后冻结为只读，主目标启动时重核 |
| `/work/build`、`logs`、`evidence`、`output`、`review` | 新建专用构建树、逐步日志、组成证据、strip 前后 ELF 和审阅输入，不复用历史目录 |

原留存普通文件为隔离审阅用途的 `0600`。预检拒绝这层权限漂移；未来只在工作副本按归档 `original_mode` 的执行位恢复普通文件 `0755` / `0644`、目录 `0755`，不恢复 setuid / setgid。只保留归档已验证的内部链接，不允许新的外部链接。

## 阶段、argv 与尚待观察的结果

配方列出 32 个依赖阶段步骤，命令均有精确 argv、cwd、环境覆盖、stdout / stderr 和 receipt 路径；审阅门禁没有自动成功分支。

1. **工具与查找观察。** 未来执行 GCC target / version / search / specs / CRT 查询和 `pkgconf --static --cflags --libs libedit`，留原顺序和重复项，逐项映射库存；出现未列路径即停。本批只保存这些命令，没有执行查询。
2. **检测分支。** 自有 CMake 项目按固定 Find 模块的头文件和选项检查 `getc_unlocked`、`closefrom` 及 deprecated literal warning flag，显式指定 C11 / C++17 与 extensions OFF。保留 cache / trace / compiler 诊断；工具或基础设施错误不能被解释成“功能不存在”。原完整配置与独立检测上下文的等价性仍需实际审阅，不能把本批静态文本当成检测通过。
3. **GMP。** 计划在独立源码副本以 `gnu99`、PIC、C++、static 和 `--build=aarch64-linux-gnu` 配置、构建及前缀安装；检测程序和生成工具执行属于未来授权范围。产出实际头 / 库并核对 ABI 后才能供 Poly 使用。
4. **CaDiCaL。** 不运行其 configure；按固定配方四项替换实例化 makefile。两项功能检测的四个分支均已在内存生成并记录摘要，没有默认假值；保留原宏和 flags，构建目标限 `libcadical.a`。归档中的 Git ID 脚本按无 Git 的原分支保留告警；不引入宿主仓库身份。
5. **Poly / SymFPU。** Poly 的六条非 PIC 安装规则按原 sed 语义去除，保留 PIC 目标与头文件安装；不应用 global-context / Windows patch。C++ warning flag 的两个分支显式列出。SymFPU 只复制固定 core / utils 头文件。
6. **主目标绑定与配置审阅。** 真实六类头文件、归档及 Editline 有序闭包审阅后，才能绑定主 cvc5 清单。原八文件 patch 精确应用到独立副本；主配置保持 Production、static、Poly、Editline、`-Werror`，关闭自动下载、venv、bindings 和非候选能力。实际配置 cache / trace、AArch64 分支和 linker 再审阅后，才允许 `cvc5-bin` 编译。
7. **产物留存。** 单独复制 unstripped ELF，`strip --strip-all -o` 另生成 stripped ELF；两者分别保留摘要和 readelf 输出。不调用新 cvc5 的 `--version` 或 solver。

GCC sysroot 明确为隔离根 `/`，CPU flags 为 `-march=armv8-a -mtune=generic`，不使用 native tuning。主链接明确 BFD；固定上游 `CMakeLists.txt` 对 AArch64 跳过 mold / gold 自动选择，仍须以真实配置及 linker trace 核实。新增 sysroot / CPU 固定和观测 flags 是候选构建参数，不能声称与发行版 bytes 等价。

环境不继承宿主，仅列 PATH、locale、TZ、HOME、TMPDIR、工具及 pkg-config 根等字段。`AWK` 明确绑定已有 `/usr/bin/gawk`，不假定安装过程生成了 `/usr/bin/awk`；缺少 `/usr/bin/mawk` 不代表缺少 AWK 工具。`SOURCE_DATE_EPOCH=1778167660` 来自已留存 cvc5 固定提交的 committer 时间；CaDiCaL date / uname 及部分生成器日期不一定使用该变量，必须保留实际生成内容，不宣称可复现构建。

## 日志、链接清单与失败保留

每步 receipt 绑定配方摘要、精确 argv / cwd / 完整环境、stdin、时间、退出码 / 信号 / 超时原因、stdout / stderr 字节摘要及资源峰值。stdout / stderr 分开保留；CMake trace 使用 JSONL、`--trace-expand` 和 `--debug-trycompile`，保存检测目录。配置阶段的可覆盖观测必须在进入构建前单独留存。

主链接计划启用 `-Map`、`--cref` 和两次 `-t`，另保存完整 `link.txt`、生成 Makefiles、响应文件及 linker scripts。`/work/evidence/link-inputs.json` 必须由**实际链接**形成，保留参数展开顺序和重复项、每个对象 / archive、重名成员 occurrence、抽取成员及触发符号、CRT / specs / 默认库、丢弃 sections / LTO 观察及源码 / SDK 包归属。计划中的库名或 compile_commands 不能代替这份清单。

完整 header / generator / assembler 读入关联及 map / trace 双向对账仍由后续执行观察和独立检查完成；本批只定义采集及拒绝要求，不伪造实际 map 或声称系统调用级读取跟踪已实现。任一未归属输入、额外库、选项漂移、缺失 / 截断日志或响应文件都必须停止，不能记录为成功。

候选资源保持最多 4 jobs、8 GiB 内存、swap 0、20 GiB 专用可写空间、90 分钟总时限；均未实测，须在执行前核定。预留末尾 60 秒终止 / 留证及 128 MiB 最终记录空间，不得在额度耗尽后悄悄增额。stdout 每步 256 MiB、stderr 每步 64 MiB、CMake trace 每步 512 MiB、全部日志 2 GiB、事件 32 MiB、inventory 64 MiB，均计入专用空间。限额由未来执行监督器强制及读回，本批 Python 入口不假称能限制未启动的外部进程。

失败 / 取消 / 失联要求终止整批隔离进程组或 cgroup，禁止重试或继续下一阶段；保留部分源码、对象、日志和产物，追加失败 receipt。清理默认不删除数据：临时执行实例只能按精确身份终止 / 移除，宿主批次目录全部保留。之后若获准清理，先列出本批拥有的精确路径、类型、摘要，拒绝越界和符号链接，再仅删除已批准集合；不提供递归删除仓库、共享工具或宽泛 `.tmp` 的命令。

## 本批验证

实际结果及文件身份见[验证记录](solver-cvc5-c2-2026-10-23/validation.json)。仓库检查通过（2,862 文件），`git diff --check` 通过；实际 `check` 输出准备通过并按设计返回 2。新增 33 项测试与既有 47 项预检测试通过，覆盖字节损坏、路径 / FIFO / 链接、重复 JSON / NaN / 预算、输出覆盖 / batch 占用、配方重哈希后篡改、检测分支、主配置绑定、假接受及外部命令 / 清理模式拒绝。

开发期真实预检先后拒绝三处建模错误：误把 374 项内容观察要求为 500 项、误用 header 路径字符集拒绝带空格的 SDK 文档名、假定存在 mawk。分别改为按内容扫描范围对齐、复用既有归档安全路径检查、绑定实际 gawk；没有放宽摘要、来源、目录或接受门禁。相关失败事实保存在验证记录，成功后没有把它们改写为成功。

本批只运行自有 Python、字节 / 文本复核和仓库检查。未运行上游 configure、CMake、Make、pkgconf、编译器、安装程序、检测项目或 solver；未启动容器、发送消息或 push。新输入和入口不产生形式证明或工具接受。
