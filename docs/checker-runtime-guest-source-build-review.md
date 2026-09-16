# Checker guest 来源与构建入口审阅

审阅日期：2026-09-16

状态：候选环境、kernel / Debian 来源与 Rust Linux 输入已形成诊断；安装、完整 source lock 与构建验收尚未完成。

用途：把 kernel / init / runner / transport 与 Linux checker 的来源前置落实为可核对输入、构建职责和验收交付，支撑[产品化依赖审阅](checker-runtime-productization-dependency-review.md)的来源切片。

读者：runtime、guest、独立 Checker、工具来源与发布维护者。

最初静态审阅读取主仓 `fd0e396` 与官方材料；后续在 `dc4de70` 基线上获准取得 kernel 源包 / 签名 / 公开验证材料，并在任务隔离容器内盘点及验签，见[实际核验记录](records/linux-6.18.49-source-review/README.md)。未安装依赖、修改宿主 keyring、执行源码构建、创建产品 VM、签名产品、跨仓写入、迁移公共契约；上述来源诊断本身不接受 ADR 0015，不重验历史验收。资源 ADR 与维护责任已在 2026-09-10 另行确认，见[产品化依赖审阅](checker-runtime-productization-dependency-review.md#许可证与维护责任)。

## 结论

1. Linux `6.18.49` 官方源包已取得，压缩 SHA-256 匹配；未压缩 tar 的分离签名通过固定 Greg KH 指纹核验。归档文件、链接与许可证材料库存已有[实际盘点](records/linux-6.18.49-archive-inventory/README.md)，工具来源和许可义务仍未完整验收，不能填写 source accepted。
2. init 的语言不能仅按交叉编译成本选择。Go `go1.26.7` 的标准子进程入口缺少直接安装 child seccomp 的钩子；本审阅建议优先论证 Rust init 的窄系统调用路径。它仍需 Linux target std / 静态链接来源，尚未形成语言或依赖决策。
3. kernel builder 是独立的 Linux 工具环境。主仓已验收的 Darwin Rust、Go 材料不能覆盖 Linux 的编译器、链接器、构建工具及宿主库，已盘点本地固定 Debian 12 arm64 镜像的 413 个包条目与工具身份，但缺少 `flex` / `bison` / `bc`，Rust 为 `1.96.1`；该镜像尚未验收为 builder。
4. checker source identity、workflow commit 与 Release commit 不是同一身份。Linux artifact 必须从重新核实的完整来源链构建，并生成新的验收与 companion；当前 Darwin record 只提供追溯起点。

## Kernel 固定来源与验证链

2026-09-06 [kernel.org 发布索引](https://www.kernel.org/)列出 longterm `6.18.49`，发布日期为 2026-09-02。本审阅继续使用该候选，不跟随 `latest`。

| 项目 | 本次记录 | 证据状态 |
| --- | --- | --- |
| 压缩源码 | [linux-6.18.49.tar.xz](https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.18.49.tar.xz) | 已下载 154,627,808 bytes，原始摘要见下行 |
| 发布者 SHA-256 | `ae826f33111fea6f1d279dde7299d7463c8dfd204aeb75a8fb5432bc60a28191` | 本地重算匹配 [sha256sums.asc](https://www.kernel.org/pub/linux/kernel/v6.x/sha256sums.asc)所列摘要；未以该索引自动签名替代开发者签名 |
| 开发者分离签名 | [linux-6.18.49.tar.sign](https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.18.49.tar.sign) | 第二次离线验证返回 0 / `VALIDSIG`，完整指纹 `647F28654894E3BD457199BE38DBBDC86092693E`；首次缺 UID 导入失败留存 |
| 未压缩 tar、归档文件库存 | 1,610,598,400 bytes；SHA-256 `e1ff34affa6a24460d47dbad47d60ff971b88a18c06841554664358313d5026c` | 已只读盘点文件 / 链接及许可材料；未提取为构建目录或形成完整许可验收 |
| stable tag / commit | tar 的 PAX comment 为 `1c732c6b94f0faee1526bd375add2fe10cba2e26`，与 stable 镜像 `refs/tags/v6.18.49` JSON 的 peeled commit 相符 | 精确 tag 元数据对应已补齐；原始 tag 签名 / Git tree 重建尚未完成，TEXT 入口 HTTP 400 留存 |

[kernel.org 签名说明](https://www.kernel.org/signature.html)区分两条链：开发者签名对应**未压缩 tar**；`sha256sums.asc` 的自动签名用于镜像一致性，不替代开发者签名。后续必须分别核对压缩文件摘要、解压后的 tar 签名、签名公钥指纹与所采用的信任来源。不能将网页可访问、摘要相等或 `Good signature` 单独写成完整来源可信。

验签只使用任务隔离的 keyring，不改变用户默认信任库；公钥指纹须从已审阅来源核对，不能按下载内容自带的短 key ID 自动信任。签名过期、撤销、身份无法核实或摘要错配都停止，不换镜像 / patch / key 掩盖失败。本轮获准用已盘点的 GnuPG `2.2.40` 做诊断核验，未安装工具；其完整来源尚未验收，因此本次结果不能直接进入正式 acceptance。keyring 保持 `TRUST_UNDEFINED`，完整指纹关联依赖 kernel.org 官方页面。

源包验收应先列 tar 库存，再决定是否展开：拒绝路径逃逸、重复路径、危险类型 / 权限，审核相对链接目标及顶层目录；源码合法链接不能被静默忽略，也不能直接沿用面向 Go binary 包的无链接规则。现有 [tar 检查器](../scripts/inspect-toolchain-tar.py)只接受已登记 Go / Rust profile；其源码摘要已被历史 acceptance 生成链绑定，不能直接改动后重算旧记录。本轮增加独立 [source-tar v1 诊断入口](../scripts/inspect-source-tar-v1.py)，只识别固定 Linux profile，使用新格式标识；旧脚本 / 生成器 / contracts 不变，新输出不能被旧 acceptance consumer 消费。它不是生产提取器或新的已接受公共格式。

## Linux builder 的最小库存

建议采用独立 Linux arm64 构建环境，首轮选择该环境中经过库存验收的 GCC / binutils 路径；固定 native host 与 arm64 target，避免同时引入交叉 sysroot。LLVM 可作为重新审阅的替代构建方案，不能遇到失败自动切换；[官方 LLVM 构建说明](https://docs.kernel.org/kbuild/llvm.html)要求同时明确 compiler 与整组 LLVM utilities，而不是只替换 `CC`。

下面的最低版本来自 [Linux 6.18 构建要求](https://docs.kernel.org/6.18/process/changes.html)，**不是本项目选定版本或验收结果**。正式库存还须以 `6.18.49` 实际源码、最终 config 与所选发行环境复核。

| 库存组 | 必须锁定的内容 |
| --- | --- |
| builder 本体 | Linux OS / arch、rootfs 或镜像原始身份、包仓库快照、已安装包与来源 / 许可证；使用容器时还包括镜像 digest 与运行器版本 |
| C 编译 / 链接 | GCC ≥ 8.1、binutils ≥ 2.30 的精确包修订、源码、binary 摘要、HOSTCC / CC / LD 及宿主 libc / headers |
| 构建 / 生成 | GNU make ≥ 4.0、bash ≥ 4.2、flex ≥ 2.5.35、bison ≥ 2.0、bc ≥ 1.06.95；Perl 及实际使用模块、Python 与 pkg-config |
| 文件 / 验证 | shell、coreutils、awk / sed / grep、tar / xz、hash / signature 工具的实际版本、路径和来源；不能隐式借用 PATH |
| 条件工具 | BTF 对应 pahole，Rust kernel 对应 Rust / bindgen，签名 / 证书对应 OpenSSL 等；由最终 config 决定实际依赖，不从候选裁剪项预先声称已排除 |
| boot 材料生成 | 优先使用 kernel 源码内已锁定的 `scripts/dtc`、`usr/gen_init_cpio` 及受审阅输入；额外生成器须单列源码和运行时 |

发行版包名或 OCI digest 都不能替代上述库存。构建环境可以包含所需工具，但 guest 输出只允许已审阅 kernel / init / checker 与固定材料；不能把 builder rootfs 整体打入 guest。

最初宿主 `command -v` 只发现默认 Go 为 `1.26.3` 路径，`gpg` / `gpg2` / `xz` 未在当前 PATH 解析到。未执行这些工具，也未扫描全盘；这不证明它们在机器上完全不存在，但足以排除“直接使用当前 PATH 构建 / 验签”的方案。精确 Go `go1.26.7` 的历史验收不等于本轮已定位安装并核实运行身份。

后续使用已有 OrbStack 的固定本地镜像进行无网络、只读、非 root 盘点和隔离 keyring 验签；工具、包来源字段、二进制摘要、命令与实际退出状态见[实际核验记录](records/linux-6.18.49-source-review/README.md)。镜像 digest 不替代包来源验收；诊断容器已自动删除，未调整宿主 PATH 或密钥环。

### 已核对的缺失包与后续来源链

[精确候选记录](records/linux-6.18.49-archive-inventory/builder-package-candidates.json)固定的三个 arm64 包已完成后续[签名来源链诊断](records/linux-builder-source-chain/README.md)：InRelease 验签、Packages / Sources 摘要以及 3 个 binary / 9 个 source 材料的长度与摘要全部匹配。包内控制字段与签名索引一致；无网络 apt 模拟显示只新增三包、无升级或移除、未安装 recommends。`flex` 的 debconf 前置依赖、`bison` 的 alternatives / 旧 manpage 操作、`bc` 的条件 menu 更新已列明；首次只读 /tmp 导致模拟失败与修正均留存。尚未实际安装或执行脚本，不把模拟当成配置 / 回滚验收。

后续 [Rust Linux 诊断](records/rust-linux-input-review/README.md)已取得 GNU host 与 musl std 实际归档，均匹配固定 channel manifest 摘要并通过本轮 GnuPG 分离签名核验；逻辑归档、文件 / component 清单和部分 ELF 动态依赖已盘点。公钥旧 SHA-1 自认证、镜像 / 工具来源、实际静态 runtime 来源与动态库闭包仍未完整验收，未回写正式登记。旧镜像的 `1.96.1` 不能代替 `1.97.1`，也不为缩短准备切换 init 语言。

实际 musl 包带有 `libc.a`、`libunwind.a` 和 9 个 CRT 对象；GNU host 的 `rustc` component 提供 `rust-lld`，但后者自身需要 builder 的 loader、LLVM / zlib / libc 等库。下一步对应精确源码 / 许可及宿主库，不再把这些文件列为“尚未取得”。安装候选仅选择 GNU 的 rustc / cargo / std 与 musl std，采用新隔离前缀并禁用 `ldconfig`；安装器会处理旧组件，不能直接复用已有 prefix。尚未实际安装或构建，最终 kernel config 和条件工具仍未冻结。

2026-09-10 已对选定 GNU component 的全部 14 个 ELF 补查动态段，并核对压缩流、tar 流及单文件与原库存身份一致；driver / LLVM 的传递依赖包括此前根工具摘要未列出的 `librt.so.1`。实际记录及系统库、符号版本、静态 runtime 的剩余缺口见 [Rust 输入补查](records/rust-linux-input-review/README.md#2026-09-10宿主依赖补查与安装前置收敛)。同名库库存不等于 loader 解析成功。下一次安装的具体范围、命令和中间核对见[隔离安装切片审阅](checker-runtime-linux-install-slice-review.md)，来源前置与安装授权仍未闭合。

同日获准重新取得精确 Rust `1.97.1` 源包，摘要与既有 source acceptance 一致。[配方补查](records/rust-linux-input-review/source-recipes-2026-09-10.md)区分 musl 目录的 libc / 5 个 CRT 与 LLVM compiler-rt 的 4 个 CRT，确认 libunwind 的源码树内构建入口，并定位 musl-cross-make `3635262e4524c991552789af6f36211a335a77b3`、musl `1.2.5` 及随包 patch。对应 LLVM 源码 / 许可已取得；后续[固定 musl-cross-make 补查](records/rust-linux-input-review/musl-cross-make-2026-09-10.md)取得 340 文件库存，确认实际 Binutils 2.44 / GCC 9.4.0、七项源依赖、四份 musl patch 及工具 / patch 许可边界。后续 [musl 原包及补丁诊断](records/rust-linux-input-review/musl-source-2026-09-10.md)取得 1.2.5 精确源码 / 许可、完成四份 patch 的零 fuzz 应用，确认 LIBCC 只在已见 libc.so 规则中使用；但包签名与公钥自认证均为 SHA-1，严格验签拒绝。后续 [Debian 强摘要链](records/rust-linux-input-review/musl-debian-auth-2026-09-10.md)已核对 trixie 两个必要签名角色、自认证及 Sources → 同一原包 SHA-256；项目所有者随后已确认仅限该原包的有条件 Debian 归档信任方案，包括以官方 HTTPS / WebPKI 为初始身份来源；[页面、精确 keyring 包及两公钥 / archive 公告](records/rust-linux-input-review/musl-key-status-2026-09-10.md)已补证，字节匹配。公告不覆盖 stable release，未核验公告签名；后续指定材料的真实验签与限定来源验收决定见下文。其他六项依赖、实际发布构建关联、宿主库和最终链接仍未验收；没有安装或切换工具链。

2026-09-12 已完成 [musl 验证环境的包 / 源码关联、内容、静态符号及许可材料盘点](records/2026-09-12-closeout.md#提交回顾)，并从[本机独立归档](records/rust-linux-input-review/musl-retention-2026-09-12.md)恢复重跑。项目所有者已接受固定 Debian 工具二进制与本机宿主为该诊断的可信输入；镜像导入、GnuPG 2.4.7 版本 / 目录和两项 loader 诊断已实际完成，四个容器正常退出并删除。该范围不覆盖 Rust 构建环境或产品隔离。2026-09-16 已补齐有界入口并完成[九项真实验签](records/rust-linux-input-review/musl-verification-success-2026-09-16.md)，覆盖两角色、自认证、交叉认证拒绝与完整来源链；原始公钥材料时点为 9 月 10 日，不代表当前全渠道撤销状态。[来源验收审阅](records/rust-linux-input-review/musl-source-acceptance-review-2026-09-16.md)已获项目所有者确认，该精确原包在固定工具 / 宿主与材料时点条件下的限定来源验收通过；异盘备份作为恢复风险并行安排，完整工具来源闭包和分发责任未验收。

### 归档诊断的范围

新入口对物理 USTAR / PAX、压缩 / tar / 文件长度、路径、权限、重复项、链接图和逐文件摘要进行受限检查，首次权限误判与修正均保留在[实际盘点记录](records/linux-6.18.49-archive-inventory/README.md)。源码归档的 group-write 位只作为元数据记录，不应用到宿主文件系统；后续提取策略另行审阅。SPDX 标记扫描与许可证文件清单不等于许可义务验收。

其 17 项合成拒绝 / 正向测试已接入 `check-repo`；实际 1.6 GB tar 只在显式命令下扫描，不放入默认仓库检查。完整库存压缩留存并绑定方法 / Python 版本、输入和输出摘要；没有把诊断 Python 或标准库声明为产品已接受工具。

## init 语言与启动边界

init 是产品侧 guest TCB：准备只读文件系统、管理 checker 子进程与真实后代、封装输出并保留实际失败。它不解析 Evidence、不重建义务，也不能复制 Checker parser。按 [ADR 0012](adr/0012-product-checker-runtime-host-and-persistence-interface.md)和 ADR 0013 的组件边界审阅其来源，不能因与 checker 使用同一语言就合并独立实现。

| 候选 | 可复用前置 | 需要补齐的真实边界 | 本次判断 |
| --- | --- | --- | --- |
| Go `go1.26.7` / `CGO_ENABLED=0` | 既有 Darwin host / source 验收；checker 也使用 Go | `SysProcAttr` 有 chroot / credential 等字段，但没有通用 pre-exec 或 seccomp 配置入口；自行 fork、重入 runtime 或新增 trampoline 都会扩大审阅面 | 不按“标准库即可”冻结；保留重新比较 |
| Rust `1.97.1` / Linux arm64 静态 ELF | 产品工具链与 Rust source 验收；`pre_exec` 提供明确的 child 执行前位置 | Linux target std、libc / CRT / linker 与 Linux 系统调用绑定未验收；hook 内必须遵守 fork 后限制 | **优先论证建议**；材料已获准下载诊断，安装 / 新增项目依赖尚未授权 |
| C / 自定义裸 syscall init | 可与 kernel builder 使用同一 C 工具族 | 新语言实现面、手工 ABI / 内存安全 / libc 或运行时维护 | 不为缩短来源准备而采用 |

本判断基于精确标签的 [Go exec_linux.go](https://raw.githubusercontent.com/golang/go/go1.26.7/src/syscall/exec_linux.go)和 [Rust Unix process API 源码](https://raw.githubusercontent.com/rust-lang/rust/1.97.1/library/std/src/os/unix/process.rs)。Go 没有直接 hook 不等于无法实现隔离；只意味着此前的“Go 标准库单用途 init”还缺具体安全启动设计。不能先启动 checker 再从 parent 补装限制，也不能给整个多线程 PID 1 加过滤器后假定全部线程、管理路径和后代均符合预期。

Rust 路径也不能只调用一个 `pre_exec` 就宣布安全：[API 约束](https://doc.rust-lang.org/std/os/unix/process/trait.CommandExt.html#tymethod.pre_exec)要求审阅 fork 后操作。所有固定路径、参数、过滤规则与缓冲在 parent 准备；child 阶段只做已核实的必要 syscall，避免分配、锁、环境查询、格式化日志与异常展开，错误保留 errno。

建议把启动顺序固定为：parent 建立只读投影和固定 fd → child 关闭多余 fd / 隔离 root 与 cwd → 清除 supplementary groups 和 capabilities、降 uid / gid → 设置并核实 `no_new_privs` → 安装覆盖预期 syscall ABI 的 filter → exec 精确 checker。权限与 capability 清除顺序、stdlib hook 前后动作、exec 错误管道和 filter 所需 syscall 都必须从实际实现核对；任一步失败即阻止 exec。

[seccomp 说明](https://docs.kernel.org/userspace-api/seccomp_filter.html)不将 syscall filter 视为完整 sandbox；只读投影、权限、进程能力与无 host device 仍需一起验收。PID 1 保留管理职责，checker 不直接替换 PID 1；不能让 checker 获得管理输出设备、mount 能力或 init 的控制 fd。Rust `aarch64-unknown-linux-musl` 可作为静态目标候选，但是否真正无动态 loader / `DT_NEEDED`、嵌入哪些 musl / compiler runtime 材料，须以新 artifact 检查和来源库存为准。

## Kernel / boot 输入与可复现交付

首轮建议以 C kernel、无模块、无网络 / 磁盘 / host share、单 vCPU、受审阅 RAM 文件系统和固定输出设备为配置目标。保留 Go checker 所需线程、futex、signal、时钟、随机源与 syscall 能力；来源存在不等于能力可暴露给 checker。随机源与启动非确定性进入环境 / TCB 记录，不得影响规范输出或伪称全 VM 执行确定。

完整 `.config` 必须从已验收源码和 builder 生成并留存，同时记录配置输入、命令、diff 与被依赖关系重新打开的项。裁剪列表只表达意图，不能替代最终 config；不得提前把未经 Kconfig 验证的片段登记为可启动 profile。

按 [Linux arm64 boot 协议](https://docs.kernel.org/6.18/arch/arm64/booting.html)，候选输出使用未压缩 `Image`，验证其 header / effective size / flags、内存区间、DTB 和 initrd 对齐与不重叠关系。guest 的全部 boot 内容仍位于同一 128 MiB RAM；不得用额外只读映射绕过 RAM 上限。

initramfs 输入先采用固定 `newc` 布局，逐项列路径、类型、mode、uid / gid、时间、内容身份与顺序，限制链接和设备节点；不使用宿主目录自动递归收集。按 [initramfs 说明](https://docs.kernel.org/6.18/filesystems/ramfs-rootfs-initramfs.html)核对源码生成入口与 PID 1 生命周期；源码中的通用生成能力不代表本产品允许其全部 entry 类型。

依据[可复现构建要求](https://docs.kernel.org/6.18/kbuild/reproducible-builds.html)，首个构建任务须交付：

- 精确 source / builder 库存、完整配置、环境白名单、路径映射、固定构建时间 / user / host / version、patch 列表和所有命令；
- 两个独立工作目录中的干净构建，比较 `Image`、init ELF、DTB、initramfs 和布局的原始长度 / SHA-256；
- 区分 upstream source、未签名产品 artifact 与签名后的 runner；签名变换单独留记录；
- 保留比较失败、实际资源与构建工具退出状态；不能重试后丢弃第一次失败或把不同输入的相同输出作为来源完整证明。

两次相同输出只证明本次输入与环境下的可复现观察，不证明编译器、kernel、init 或 checker 实现正确。

## Linux checker 的跨仓交接

来源起点为[当前 Darwin 登记](../contracts/checker-runtime-payloads-v0.1/records/checker-go0.1-dev-darwin-arm64-current-registered-inactive.json)，其中包含：

| 身份 | 既有值 | Linux 交接要求 |
| --- | --- | --- |
| checker source | `sha256:401158c3c304f45faebebe879edf064512998423d7b08aec486f4be0012e3999`，703 文件 | 从源清单按原算法重算；构建 Linux 所需改动若进入 source 范围，形成新身份 |
| candidate workflow commit | `f6a02b9314051fd841e1f3d3d1491a8a73ad7da7` | 只是既有 workflow 来源，不能当作新 Linux 构建结果 |
| source identity commit | `4b95b2a81616110f5d3ed076f882a18ddc6aba37` | 重验源码清单与 commit 关系，不与 Release commit 混用 |
| Release / merge commit | `f960603aa1120ebe427eb9227f116f4a41513d5e` | 只追溯既有 Darwin 发布，未请求新发布或重跑 CI |

交给 [RadishAxiomChecker](https://github.com/laugh0608/RadishAxiomChecker) 的下一任务应精确覆盖：核实 Linux 目标构建入口与源码身份 → 使用已验收 `go1.26.7`，锁定 `GOOS=linux`、`GOARCH=arm64`、`GOARM64=v8.0`、`CGO_ENABLED=0` 与原有 build flags / source 注入 → 两次离线构建 → ELF / 依赖 / runtime self-identity 检查 → 在另行获准的精确 Linux 运行边界下取得真实 companion。

必须单列 `ax-b01-correct`、`chk-digest-01`、`chk-resource-01` 和迁移影响场景；旧结果只作对照，不能预填新 binary 身份后的结果摘要。目标归因、同域泛化与证书支持仍按 Checker 语义线验收。主仓本次不读取兄弟 checkout、不修改其文件、不发送任务或触发 workflow。

## 下一可执行切片

已有 kernel / Debian 诊断、Rust Linux 实际字节 / 签名 / 库存、kernel tag 元数据对应和许可材料审阅。musl 有界验签与[同一原包的限定来源验收](records/rust-linux-input-review/musl-source-acceptance-review-2026-09-16.md#决策与下一步)已完成；其余六项已完成[来源路线盘点](records/rust-linux-input-review/musl-remaining-sources-2026-09-16.md)；MPC / MPFR 原包与公钥已取得，来源验收仍未通过，近期顺位以当前状态为准。发布构建关联、Rust 公钥绑定策略与 driver / LLVM / 系统库闭包继续待补。备份交付与日终位置观察见[日终记录](records/2026-09-16-closeout.md#本机材料与外部影响)，不将本机归档称为异盘恢复。三包加选定 Rust component 的隔离安装范围已有独立审阅，安装与有限执行仍未获授权。kernel 分发需保留对应源码、patch、配置与构建 / 安装脚本的候选交付已列明，具体产物 / 分发方案尚未接受。镜像、诊断工具和材料库存不等于完整 acceptance；旧摘要绑定入口不改动。分别验收 source、builder、init target 与 Go checker 输入后才写入 source lock。

| 切片 | 完成交付 | 当前缺口 |
| --- | --- | --- |
| 构建环境确定 | 精确环境、工具 / 库库存、版本 / 摘要、隔离与清理范围 | 三包模拟、Rust 选定 component 的 14 个 ELF 静态依赖与隔离安装范围已有；尚未安装，镜像 / 工具 / 系统库和源码许可未完整验收 |
| Kernel source 验收 | 压缩摘要、未压缩 tar 签名、完整指纹、文件 / 许可证库存、来源记录 | 摘要 / 签名 / 文件库存、tag 元数据对应及许可材料已审阅；原始 tag、实际分发材料与工具来源尚未完整验收 |
| init 方案收口 | 语言 / target / 依赖决定、child 限制安装顺序、失败矩阵 | Rust 优先建议待设计验收；CRT / unwind 精确配方与 LLVM 源码 / 许可已补查，固定 musl 原包限定来源验收通过，MPC / MPFR 原包与公钥已盘点；验证环境仅获该 musl 诊断 / 来源结论的窄信任，剩余输入、发布构建关联与实际链接未验收 |
| 可留存合成装置 | 自有 runner / init / transport 源码、输入与重跑入口 | 先满足 ADR、工具、私有 FFI 范围与单独签名 / VM 授权 |

本审阅没有解除来源、资源或真实执行门槛。当前产品能力与下一顺位仍只由[当前状态](status/current.md)统一维护。
