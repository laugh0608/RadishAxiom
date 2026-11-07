# 诊断通道 L3：精确 target 组件与完整构建输入方案

日期：2026-11-01。状态：**方案及 v0.2 / native 捕获 / 包装器源码已实现，完成宿主静态与合成验证；未安装 target 或构建 Linux 制品**。读者：项目所有者、实施者与输入 / 制品审阅者。用途：收口[交付方案](solver-linux-channel-build-and-delivery-plan.md)中 L3 的具体组件、安装副作用、输入绑定和有界包装器；不另开工具链路线、修改公共 Evidence / solver 格式或接受新运行资格。方案基线为 [L2](solver-linux-channel-l2.md)；原包观察见[方案记录](../records/2026-11-01-linux-channel-l3-review.md)，本次实现、发现与验证见[实现记录](../records/2026-11-01-linux-channel-l3-implementation.md)。

## 已冻结的选择与现有材料

唯一目标继续是 macOS AArch64 的 `1.97.1-aarch64-apple-darwin` 交叉构建 `aarch64-unknown-linux-musl`，使用已有 rust-lld 的 GNU flavor，产出静态非 PIE ET_EXEC。无新 GNU SDK / GCC / Linux builder、QEMU 或动态 libc 路线。

L2 已提交为 `5dab738`；L3 源码实现已提交为 **`bb9d963b38273bfd9ec7aefe69cc13417a4a8f34`**，其中含 v0.2 纯生成 / 独立复核、native 捕获与有界包装器。它是本次已验证的实现基线；未来完整构建输入仍须绑定执行前最终干净 commit 的完整树，不把 L2 或本页日终文档提交误记为已构建制品来源。原方案批次只形成方案和诊断记录。具体候选参数见[候选计划 JSON](../records/cvc5-control-plane-2026-11-01/channel-l3-candidate-plan.json)，其 scope 为 proposal-only-not-native-build-inputs，final_implementation_commit=null 是方案生成时的历史状态，旧 JSON 不回填；所有安装 / 构建授权和 readiness=false；它不能被原生入口当 inputs 消费。

[只读观察 JSON](../records/cvc5-control-plane-2026-11-01/channel-l3-input-observation.json)绑定以下真实对象，全部以本机实际字节重核：

| 对象 | 精确身份 / 当前状态 |
| --- | --- |
| 发行清单 | 已留存 `channel-rust-1.97.1.toml`，2026-07-16；845,916 bytes，SHA256 `03569b1886ceb5c05276b50c8431ab111de944cd6140fe1fa7d821dd8e0f29cf` |
| 唯一 target 归档 | `.tmp/rust-linux-inputs-bb014fd/rust-std-1.97.1-aarch64-unknown-linux-musl.tar.xz`；29,062,284 bytes，SHA256 `49ff0879d94e2e8e86d5e85eb15a9215943e8c78b51363d6553443598cab5d31`；**已存在，不重新下载** |
| 发布 URL | 清单对应 `https://static.rust-lang.org/dist/2026-07-16/rust-std-1.97.1-aarch64-unknown-linux-musl.tar.xz`；只作原来源定位，本批未请求归档 |
| 完整逻辑归档 | 新扫描与旧库存逐项相等：7 目录 / 78 文件；tar 152,835,072 bytes，SHA256 `f0314c4b28d4d5d89cd7fba9144e3a97e2643d6918a3807458b5b8d35c8e7d77`；没有释放成员到文件系统 |
| 实际 component payload | `rust-std-aarch64-unknown-linux-musl` 的 66 个 file claim，共 152,642,974 bytes；完整路径 / mode / 长度 / SHA256 在观察 JSON，不把安装器 / 根许可文件算成已安装 payload |
| 宿主工具 | rustc / cargo / rust-lld 三文件与交付批观察完全匹配；installer 为已有 rustup `1.29.0 (28d1352db 2026-03-05)`，11,053,296 bytes，SHA256 `aeb4105778ca1bd3c6b0e75768f581c656633cd51368fa61289b6a71696ac7e1` |
| 当前安装元数据 | 已安装 multirust 清单的 target URL / 哈希投影与发行清单一致；其原文件另按自身摘要绑定，不声称两份 TOML 原字节相等。现行五个 host component 不变，target 目录 / component manifest 和所选下载 cache 文件均不存在 |

旧 Rust 分离签名诊断、SHA-1 自认证缺口和 [payload 接受的有限范围](../checker-runtime-rust-first-slice-review.md)保持原义；本批没有重新验签或把历史 GNU host / musl 原包接受转移到此 component。后续可按既有受控二进制输入方式，单独审阅这个精确归档、installer 与宿主运行时的有限信任范围；不要求重建整套 Rust / GCC，也不把摘要匹配写成发布构建证明。未形成该对象的接受决定前，停止安装与构建。

2026-11-07 的有限输入审阅重核了归档与 Cargo 解析数据，并记录实际宿主工具及加载边界。后续核对确认 installer 匹配官方发布摘要、实际加载的 Rust driver 与已接受 Darwin 组件成员逐块相等。总体决定为 `not-accepted`，单次 target 安装仍以剩余输入审阅为前置条件。 [有限输入审阅](../records/2026-11-07-linux-channel-l3-input-acceptance-review.md) · [来源核对与剩余缺口](../records/2026-11-07-linux-channel-l3-rust-source-readback.md)

## 未来安装：只增加一个 target

候选安装仍使用现有 rustup 的 `target add --toolchain 1.97.1-aarch64-apple-darwin aarch64-unknown-linux-musl`，不是 archive 内的 install.sh。该参数和下面写入目标只是供审阅，**本页不授权执行**。

核对了 rustup [1.29.0 add_component](https://github.com/rust-lang/rustup/blob/1.29.0/src/toolchain/distributable.rs)、[缓存检查](https://github.com/rust-lang/rustup/blob/1.29.0/src/dist/download.rs)和[组件事务](https://github.com/rust-lang/rustup/blob/1.29.0/src/dist/manifestation.rs)：该版本的静态路径读取已安装清单；命中按哈希命名且重算相等的 cache 时使用本地文件，成功后可能删除该 cache 并重写 component 元数据。这是精确版本源码的预期，不是已安装 binary 的源码重建证明或真实安装回执。

未来经独立授权后的顺序：

1. 重新核对 installer / 三工具字节、发行与已安装清单、target 缺席、现有 component 与必要元数据；确保安装窗口没有其他进程写同一 toolchain。保留原元数据副本与精确差异清单；不能把前后摘要比较称为原子排他证明。
2. 仅把已审归档复制到 `/Users/luobo/.rustup/downloads/49ff0879d94e2e8e86d5e85eb15a9215943e8c78b51363d6553443598cab5d31`。仅当 cache 和同名 .partial 均不存在时，新建副本 / 重算后才调用 installer；若其中任一预先存在，即便摘要相同也停止并重新核定范围，不覆盖、复用或代删，因为 installer 可能自行清理 cache。保留仓库内原归档，不 hardlink 它给会清 cache 的 installer。
3. 直接调用已绑定的 rustup 绝对路径，固定 RUSTUP_HOME / 指定 toolchain / RUSTUP_AUTO_INSTALL=0；重试数 0、下载与解包 IO 并发各 1、UNPACK_RAM=268435456，使用任务目录内空的 file: dist root。期望只命中本地 cache；缺失 / 错误时停止，不回退官方 HTTPS、换压缩格式、更新 toolchain / rustup 或运行 install.sh。这里没有认证 Rustup 的实际零联网或内存硬限；UNPACK_RAM 只是其内部 IO 参数。
4. 同一安装请求 120 s 总截止，预计一分钟量级、上界两分钟；超时 / 失败保留 cache / 日志 / 部分状态，不自动重试、remove 或手工恢复 sysroot。事务在强制终止后是否已完整回滚必须观察，不能先写“安装原子成功”。
5. 成功后按 66 项 file claim 与 target 全树双向核对，拒绝遗漏 / 新增 / symlink / 模式 / 字节漂移。元数据只允许增加这个 component 及相关清单变化，原五个 component、rustc / cargo / lld 字节须保持；读回 target list 不能代替逐文件核对。形成外置安装观察 / 有限接受记录后，才允许生成真实完整构建输入。

写入仅限上述单个 cache、`/Users/luobo/.rustup/tmp` 的本次精确事务项、现有 toolchain 的 `lib/rustlib/aarch64-unknown-linux-musl/`、`manifest-rust-std-aarch64-unknown-linux-musl`、components、multirust config / channel manifest 等实际事务元数据。新增元数据 / 临时项必须逐项登记，未知写入即停止；不假定只改变 target 目录。默认 toolchain、仓库依赖 / lockfile、宿主 PATH、全局权限和其他版本不改。

新增磁盘观测限额 512 MiB，含 29 MB cache 副本、约 153 MB 解包临时树和约 153 MB payload 及元数据，原有归档 / 宿主工具另列。它不是块 / inode 硬 quota 或 RSS 保证；若实测超额或工具不满足边界，留存失败结束，不增限。未来构建另有 512 MiB 任务限额，两者不能互相挪用或漏计；开始前按最多额外约 1 GiB 容量审阅，已有工具 / 原包继续计作基线占用。

后续清理另行明确授权，正常卸载仅用精确 `target remove --toolchain 1.97.1-aarch64-apple-darwin aarch64-unknown-linux-musl`，不卸载整个 toolchain。只处理本次证明新建且仍身份一致的 cache / 临时项；旧 cache 不代删，原归档 / 诊断 / 接受材料保留。卸载可重写元数据序列化，须核对组件语义和真实字节差异，不承诺原元数据逐字节自动复原。失败时不手删 target 树或把旧元数据覆盖回活动 prefix；先核对精确状态再核定恢复操作。

## 完整输入 v0.2 与无自引用绑定

**本节为私有输入约束；实现接口和宿主验证发现的补正见下文。尚未生成真实完整 v0.2 root。** 保留现有 v0.1 offline-source-binding-only 的纯导出和严格拒绝；不把 null 改成空对象或把 readiness 改 true 冒充迁移。

候选 root 继续 format=radishaxiom-private-linux-channel-inputs，version 升为 `0.2`、scope=target-build-input-binding。原 profile / budgets / collector / collector_reads / 有序源码闭包仍由类型化常量与编译捕获源双向核对。build_inputs 必须完整，包含最终 source commit、安装观察与有限接受引用、有序构建参数 / 环境和以下清单的 path / bytes / `sha256:` 原字节引用。native_build=not-accepted 与两个产品 readiness=false 保持，有限构建许可来自独立的对象接受和本次执行授权，不用内嵌布尔值开关代替它们。

| 独立清单 | 必须完整绑定的内容 |
| --- | --- |
| source-snapshot.json | 最终已提交源码的完整 Git blob 库存及模式 / 长度 / SHA256；实际编译三包、根 Cargo / lock / pin、正文、生成器 / checker / wrapper / recorder 的选定闭包另显式核对 |
| target-payload.json | 发行清单 / 原归档 / 安装观察身份；66 项 target 文件与安装路径的双向关联，含所有 rust-std rlib / rmeta、panic / alloc / compiler-builtins、musl / CRT / unwind，不只列最终猜测会用的项 |
| tool-inventory.json | cargo / rustc / rust-lld / installer 与宿主生成 / 核对工具；精确路径 / 版本 / 文件摘要；非系统 dylib 的真实解析闭包，系统 dyld / OS 身份与明确可信宿主边界。当前只有选定工具身份，后续不得将未核对库默认为已绑定 |
| build-plan.json | 唯一 package / bin / feature / target / profile、rustflags 数组、精确 cwd / 源 / 输出 / inputs 路径、白名单环境、Rustc 参数记录器身份、固定预算、预期产物与拒绝规则；不含输入自身摘要或最终 ELF |
| input-review.json | 上述特定对象的有限接受范围、工具 / 系统信任假设、来源 / 许可证材料与未覆盖边界；引用真实决定的原字节，拒绝 not-assessed / 空记录 / 伪造 accepted |

root ≤1 MiB、维持现有控制 JSON 的深度 / 64 项数组等边界；大清单分别 ≤4 MiB / 4,096 行，由独立受界离线 checker 核对，不把 66 项或数千项塞入报告 parser，也不放宽报告预算。原生入口只校验并消费被编译捕获的 root，其摘要传递绑定外置清单；它不在容器中读取 sidecar、重新枚举工具或认证外部接受决定。

顺序为：**最终源码快照 + 实际安装观察 + 工具 / 来源审阅 → 有序 sidecars → root inputs 原字节 → 编译 → 外置 build-manifest → 独立制品接受记录**。清单不得反向含 root 摘要；root 不含自身摘要、最终 ELF、build-manifest 或 CID。生成文件在忽略的任务 records 中，不提交进其 source commit，不从编译结果反推 pre-build 输入。

编译 root 使用受控的 `RADISHAXIOM_LINUX_CHANNEL_INPUTS` 路径作为 include_bytes 输入；先完整生成 / 独立复核，再固定原字节进入唯一编译，前后均核对。原生 prepare 必须消费这一捕获值，替换 L2 对运行时 source export 的调用；缺变量 / 文件、v0.1、错误 scope / null build_inputs / 漂移均失败，不回退旧 source-only 绑定，也不从运行环境或 argv 载入 inputs。仅文件捕获原语受目标 cfg 约束，所有校验和绑定逻辑继续用宿主纯 / 脚本后端检查，不能用 cfg 隐藏实现。

报告 wire v0.1 保持不变；input_binding 是新 root 的 raw SHA256，Mac 将来必须使用预先登记的期望 root / build-manifest。不能从 Start 建立信任，不能用 source-only v0.1 导出冒充新 root。L2 的 50 源是历史基线，本次实现为 53 源；完整源码快照还须包含最终 commit 的全部 tracked 文件，不能把 53 源选定闭包当全树。

## 一次构建包装器与占用

原方案批次仅声明包装器；本次已实现源码和合成验证，未以真实输入调用 build 或进入其 Cargo / Linux 构建分支。候选任务根为 `.tmp/linux-channel-build-l3-01/`，当前不存在；未来执行前必须重新解析、拒绝已有 / symlink / 并行写入并登记精确目标。候选参数全部在 JSON 中，含缺失实现和授权的停止条件，不是可直接执行的已接受构建配方。

- **快照。** 从最终干净 commit 按 Git blob 复制全部 tracked 普通文件到新 source 根，不复制 .git、ignored 缓存、全局配置或工作树未提交内容；不使用可能改变文件的 export filter。因为根 workspace 声明七包，不能只复制三个 normal 编译包而破坏 Cargo 图。`5dab738` 的实际基线为 2,931 文件 / 97,632,590 bytes；候选快照上限 4,096 文件 / 128 MiB，纳入任务总量，超额停止。完整树不等于全部文件都会编译或链接。
- **Cargo 图。** 独立只读 metadata / 三包 Cargo 核对 normal 闭包恰为 bootstrap / supervision-core / digest，均已有 path 依赖；拒绝 build.rs、build-dependency、proc macro、注册表 / Git 新依赖和非预期 target。examples / tests / dev-dependency 不进入目标构建；不能只看 Cargo.lock 包数量作此判断。
- **调用。** 绑定 sysroot 内 cargo / rustc / rust-lld 的绝对路径；指定 package=radishaxiom-solver-bootstrap-linux、bin=axiom-linux-channel-init、no-default-features、features=linux-channel-entry、target=aarch64-unknown-linux-musl、profile=linux-channel、locked / offline / jobs=1 / verbose×2。不通过 rustup proxy 选择默认 1.96，也不调用 cargo run / test / install 或任何产物。
- **配置与环境。** 从白名单构造子进程环境，不拷贝宿主完整环境 / 凭据 / DYLD / LD 注入、代理、继承 RUSTFLAGS / wrapper / runner。HOME 不改写；CARGO_HOME 是新任务目录。Cargo 会读取 cwd 及祖先的 `.cargo/config` / config.toml，[空 CARGO_HOME 不能隔离这些配置](https://doc.rust-lang.org/cargo/reference/config.html#hierarchical-structure)。本批仅检查路径存在性、未读用户配置内容，结果为空；未来重查，发现未枚举配置即拒绝，不自动移动 / 改写用户文件或只靠 CLI override 掩盖数组合并。
- **真实参数。** 继承 wrapper 关闭；只显式绑定本任务受审的 rustc-record 入口为 RUSTC_WRAPPER，先记录受界 canonical argv，再调用唯一已绑定 rustc。记录器 / Python 解释器及生成字节纳入输入；正常 Cargo 只读探测亦区分记录，拒绝任意可执行路径、递归 wrapper 或未登记编译单位。Cargo `-vv` 文本保留为诊断，不拿 shell 日志猜测实际 argv；不记录全环境。
- **flags。** 沿交付方案的静态 CRT / self-contained / generic CPU / static relocation / ld.lld / -static / -no-pie / noexecstack，不改变独立 profile。结构化数组用 U+001F 生成 CARGO_ENCODED_RUSTFLAGS，不经 shell split。Map 与 --trace 外增加仅一项 `--why-extract=<任务 records>/link-why-extract.tsv`，以关联真实 archive member；已有 LLD 22.1.6 --help 确认选项存在，未构建验证。不使用复制整个工具输入的 --reproduce，不在失败后换 linker / flags 重跑。
- **上限与失败。** 首个单调 t0 起 600 s 覆盖前检 / 快照 / 必要宿主纯生成 / 唯一目标编译 / 记录；一个受管进程组内运行可信宿主工具，取消不续期。jobs=1；整个任务（source / cargo-home / target / records / delivery 副本）观测限 512 MiB，ELF 16 MiB、map 8 MiB、why-extract 4 MiB、双流日志合计 4 MiB。增量读取 / 落盘有界，超限、短写、ENOSPC、取消、未知子进程 / 未能停止都保存失败，不能返回成功或增限重试。Mac 进程组与文件计量不是 RSS / 块 / inode 硬限、独立终止或 Linux G0 资格。

未来优先扩展现有 export example / check-linux-channel-inputs.py 处理明确版本，新增单个 scripts/build-linux-channel.py 承担私有 plan / 执行与内部参数记录职责；只在任务 tools 目录生成受绑定的 recorder 入口，不另造常驻服务、第二份资源配置或通用命令 runner。本次源码接续已实现这些入口，仍未进行真实 Linux 构建。

终止后只按精确已登记任务文件 / 子进程身份审阅；保留失败 / 源 / inputs / 日志和旧材料，不自动清理全局 Cargo / rustup 缓存。未知存活状态仍失败，后续恢复 / 删除另列精确范围。生成成功也不执行 ELF，build-manifest 只记实际结果，不自填 accepted。

## 来源、许可和验收出口

| 输入角色 | 复用材料与必须保持的区分 |
| --- | --- |
| 自有三包与正文 | 本仓 Apache-2.0；固定正文原字节 9,717 bytes / 已登记摘要不变，不引入第三方模板或给用户产物追加许可证 |
| Rust std / alloc / panic 等 | 精确 Rust source / component 根许可与 vendor 库存；MIT OR Apache-2.0 不能替代每个第三方组件条款 |
| libc.a / musl 的 5 个 CRT | 既有 musl 1.2.5 / 规定 patch / COPYRIGHT 与文件例外；固定原包的限定来源接受不证明发布 binary 的实际构建材料。不能套用 Alpine rootfs 的 musl 身份 |
| compiler-rt 的 4 个 CRT / compiler-builtins | 既有精确 Rust 源包对应配方与各自 LICENSE；compiler-rt / 指定源码含 Apache-2.0 WITH LLVM-exception，其他包含材料按原许可保留，不一概称为 GCC CRT / 普通 Apache |
| libunwind.a | 既有源码树 LLVM libunwind 配方与 LICENSE，含 legacy / 第三方说明；panic=abort 不证明 archive 或其中对象未参与链接 |
| 编译 / 安装宿主工具 | 与静态嵌入 guest 的材料分开记录；rustup / compiler / LLVM / dylib / 系统运行时的许可与可信输入范围不能从版本文本推导，也不自动传递成诊断 ELF 的许可证 |

[旧精确配方与许可材料](../records/rust-linux-input-review/source-recipes-2026-09-10.md)继续作为起点。本轮重核其 255 份留存文本与已提交元数据逐项一致，并单列六份 Rust / compiler-builtins / compiler-rt / libunwind 许可摘要，没有重扫 / 重建整套源码工具链。目标 .a 当前只在归档 / 文件层绑定；最终 trace / map / why-extract、对象解析、ELF 与必要来源 / 归属文件的对应仍属 L4。必要许可材料放 records、不挂入只含单 ELF 的 runtime 目录；具体分发接受不在本批发生。

本次源码切片已实现 v0.2 纯生成 / 独立复核、native 捕获与有界包装器，使用合成安装观察 / argv / 短时宿主进程覆盖旧版 / null / 篡改 / 配置注入 / 超额 / 取消 / 失败拒绝；实际边界与命令见实现记录。不自动安装或构建 Linux。真实完整 root 只有实际组件安装观察、精确工具 / 系统范围和接受材料齐备后才能生成，不能用合成 fixture 替代。随后按独立授权安装这一 target，再单独授权一次构建；L4 离线制品核对和 L5 执行前收口顺序不变。

C1 / LibPoly、E0 / E4、G0 / A1–A10、镜像 / 权限 / 无写别名 / 独立终止 / 存储硬限仍未闭合。输入方案、签名历史或元数据成功均不授权诊断环境，不创建 / 启动 Linux 环境试错，也不推进 solver 真实路径。


## v0.2 实现接口与静态出口

入口沿用 [Rust export example](../../crates/solver-bootstrap-linux/examples/export_linux_channel_inputs.rs)、[独立输入 checker](../../scripts/check-linux-channel-inputs.py)，新增唯一 [build / recorder 包装器](../../scripts/build-linux-channel.py)；[合成测试](../../scripts/test-linux-channel-build.py)不安装或执行 Linux。当前选定闭包为 **53 个源文件**（L2 的 50 个加包装器、其测试和原已被 Python checker 调用的 bootstrap checker）；旧 v0.1 仍按现行源码严格导出，不接受历史库存漂移。L1 / L2 旧记录的 45 / 50 计数不重写。

### 纯 root 与宿主清单

Rust `export_v02(request)` 接受 canonical ASCII JSON：`source_commit` 为最终 40 位小写 Git ID，`sidecars` 为上表顺序的五个 `{path,bytes,digest}` 引用；只能使用固定 basename、非零 ≤4 MiB 长度和 `sha256:` 摘要。它不读取外部状态或认定材料 accepted。example 的 `--v02 <request-file> <new-output-directory>` 模式输出 root、原正文和显式 synthetic-report；后者始终是合成互操作样本。旧无 flag 模式仍导出 v0.1。

独立 checker 的 v0.2 模式要求 `--v02-source <exact-snapshot> --source-commit <registered-commit> --review-digest <registered-review-sha256>`。两项 pin 必须来自外部审阅，不从输入自行发现或默认接受。checker 核对 root 固定数值 / 源闭包、五份原字节引用、完整 source 文件树、66 项安装 payload / 多余文件拒绝、实际工具 / 库文件、安装及宿主解析回执、固定构建计划和有限接受范围。root parser 保持 16 层 / 64 项数组 / 32 字段对象 / 256 字符串；仅 inputs 字节限独立为 1 MiB，报告仍为 32 KiB。sidecar 独立限制为 4 MiB / 4,096 项 / 16 层 / 1,024 字符串，不放宽报告 parser。

五份清单均有 `format=radishaxiom-private-linux-channel-<name>, version=0.2`：

| 清单 | 具体实现字段 |
| --- | --- |
| source-snapshot | source_commit、完整 files（path / Git mode / bytes / digest）、有序 compile_sources；必须与实际快照全树及独立枚举的选定源相等，≤4,096 文件 / 128 MiB |
| target-payload | target、installed_root、archive / release_manifest 原字节引用、66 项 files、materials 下的 installation-receipt 引用；真实模式还与已固定的 L3 原观察 / 归档身份核对 |
| tool-inventory | toolchain、cargo / rustc / lld / installer / python / git 六角色身份、dylibs、host-resolution 引用、system OS / dyld 身份材料和显式信任边界、下文 cargo_resolution |
| build-plan | 固定 package / bin / feature / target / profile / argv / metadata_argv / flags / env / paths / limits、recorder / interpreter_flags / 生成入口字节引用；由 checker 自己的固定预期核对，不导入 producer |
| input-review | scope=finite-diagnostic-build-inputs、decision=accepted-for-one-diagnostic-build、synthetic=false、source_commit、前四份对象的精确引用、非空 decisions / licenses 材料引用及 trust / limitations；raw SHA256 必须命中外部登记 |

installation-receipt 必须声明 installed-reconciled，绑定 archive / files_digest、真实元数据文件与原三工具未改身份；host-resolution 必须将所有工具 / 非系统库文件绑定到解析边、明确系统路径及 limitations。这两类回执和有限接受是**独立审阅的信任输入**：本 checker 复核结构和字节，不认证发布者、不重演安装事务、不自行解析 Mach-O / dyld cache 或证明宿主解析完整性。缺少真实限定审阅就没有真实 root；不能靠填写 accepted 字符串解除此门禁。测试用 `synthetic=True` 只存在于纯 Python 调用，结果明确带 synthetic；生产 CLI / build 不开放此模式。

### 空 Cargo home 的解析输入补正

宿主验证发现原方案遗漏：已有 Cargo 在全新空 CARGO_HOME 下，`metadata --no-deps` 能成功，但即便只选择 digest，编译前的 workspace lock 解析仍会要求 Darwin store 已有 `libc 0.2.189` 的索引。原三个 normal path 编译包没有新增依赖，不能因此放行整个用户 Cargo home、联网、下载 crate 或把 libc 纳入诊断制品。

唯一补正是 tool-inventory 的 `cargo_resolution`：scope=workspace-lock-resolution-only-not-compiled，固定 package / version / Cargo.lock checksum；只允许两份既有普通文件，分别种入新任务 Cargo home 的 `registry/index/index.crates.io-1949cf8c6b5b557f/config.json` 和 `.cache/li/bc/libc`。每份必须绑定原路径 / 长度 / SHA256，有限接受须覆盖这两份数据。checker 验证官方 registry URL、已有 sparse cache v3 / index v2、唯一 0.2.189 条目的 checksum / 非 yanked 与实际 lock 相等。不得复制 `.crate`、已解包源、凭据、其他索引或全局配置。wrapper create-new 复制并在构建后读回核对；它不是依赖安装器。

本机仅为验证这一根因，在忽略任务目录复制了现存的 **76 bytes + 84,005 bytes** 索引数据，并完成 Darwin digest 检查 / rlib 构建；没有下载或解包 libc。未回写这两份原索引或预填全局缓存，文件未加入仓库。实际身份与原空 home 失败均保留于实现记录；此宿主结果不代签未来特定输入接受或 Linux 构建资格。

### native 捕获与一次包装器

原生入口仅在原精确 cfg 内使用 `include_bytes!(env!("RADISHAXIOM_LINUX_CHANNEL_INPUTS"))`。缺变量 / 文件在编译期失败；`prepare` 和宿主测试共用 `native_binding` 校验被捕获 root 并散列原字节，拒绝 v0.1 / null / 错误 scope / 源漂移。runtime argv 仅保留 run-id，runtime 不加载 inputs 环境或 sidecar；wire v0.1 不变。

`build-linux-channel.py plan` 是纯输出，不创建任务；`build` 接受已生成且完成外部审阅的 bundle / source commit / review digest 与明确任务根。必要的 Rust 纯导出在执行请求前完成，build 不隐式编译 host generator。build 的同一 600 s 从前检起覆盖输入复核、Git 精确 blob 快照、两份解析数据、只读 Cargo metadata、唯一 cargo build、前后复核与外置 manifest。只有独立执行授权后才能调用 build，本批没有调用其真实构建路径。

Git 只读调用禁用用户全局 / 系统配置、fsmonitor hook、可选锁和 lazy fetch；保持完整七包快照，拒绝脏源、symlink / 其他模式，另核对三个 normal 包无 build.rs / build-dependency / proc macro / 注册表依赖及实际 metadata。所有工具直指已绑定文件，不使用 rustup proxy。

recorder 的生成字节和 Python 身份均进入输入，启动解释器固定 `-I -S -B`，关闭继承 wrapper。记录真实 canonical argv 后仅 exec 绑定的 rustc；允许精确 version / host / target probes 和四个编译单位（三个 lib + 唯一 bin），有序 flags 必须完整出现且仅一次，拒绝未知执行路径 / 单位 / 输出 / response file / 覆盖参数。最多 64 记录、每份 64 KiB；`-vv` 只作日志。源码闭包包含 recorder 实现，不另造通用 runner。

超时、取消、流超额、文件增长、短写 / ENOSPC、非零退出、未知存活组或未确认停止全部保留失败；cleanup 失败同时保留主因。只停止自己创建的进程组，不自动重试 / 更改 linker / 清理缓存。宿主监督要求 SIGCHLD 为默认处置且本进程为唯一 waiter；通过 waitid(WNOWAIT) 保留组长 PID，在其回收前用固定 macOS libproc 的 PROC_PGRP_ONLY 枚举（≤64）核对 / 停止原组，回收后不再发组信号。libproc / ctypes / Python 扩展属于待审宿主运行时输入；未知成员或查询失败不认定成功。枚举只覆盖原组，不能证明不存在改变 session / PGID 后逃逸的后代；工具不得产生此类逃逸，仍依赖有限宿主信任。失败中的数值 PID / PGID 仅作诊断，不能用于事后发信号。600 s / 512 MiB 及单文件限额为受信宿主下的截止与观测：Popen 所有权交接、文件 IO、SIGKILL / wait 依赖宿主 OS，停止确认最多另观察 1 s；不是 OS 硬 quota、RSS 限制或独立终止证明。manifest 始终 built-not-accepted，须同时核对包装器实际退出和失败记录，不能仅凭 manifest 判定成功，更不能据此执行 ELF。
