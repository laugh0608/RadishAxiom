# 2026-11-01：精确诊断镜像、来源 / 许可与读取权限离线核对

日期：2026-11-01（Asia/Shanghai）。状态：**离线核对已完成；镜像与执行仍 not-accepted，未创建 / 启动环境**。用途：留存[最小通道方案](../query/solver-linux-management-channel-minimum-plan.md)的实际内容、来源 / 许可证声明、权限边界及新增停止条件，供项目所有者与后续实施者审阅。本文不签发工具接受、OS qualification、独立证明或诊断执行授权；现行顺位只见[当前状态](../status/current.md)。

## 起点、授权与实际范围

项目所有者要求先提交前批最小方案，再推进精确镜像内容、来源 / 许可证与宿主文件读取权限的离线核对，暂不创建或启动环境。开始时 `dev` 相对本地 `origin/dev` 领先 2 笔，暂存区为空，工作区恰为前批 8 个文件。复核并精确提交为 **`aa162af` — `docs(cvc5): 核定新 Linux 诊断通道最小方案`**；随后工作区干净、领先 3 笔。没有 fetch、push、身份变更、AI 署名或历史改写。

本批实际动作限本机固定镜像导出、归档内存解析、少量固定来源材料取得与静态检查、自有离线脚本 / 合成测试及文档更新。没有 image pull / build、container create / start / exec、machine / 服务启动、SDK / 包安装、上游构建或 solver 执行；没有修改宿主挂载、权限、quota、证书、全局工具或远程状态。来源材料获取是当前任务的必要只读核对，不改变机器运行环境。

## 输入、入口与留存

任务专用留存根为仓库 `.tmp/linux-channel-image-audit-2026-11-01/`；不构成可运行 rootfs。原归档、失败和来源原字节均保留，没有自动删除，未承诺异盘备份。归档始终只经 `extractfile` / 内存读取，不向目录解包、不加载 ELF、不运行 APKBUILD。

| 材料 / 入口 | 本批实际绑定与范围 |
| --- | --- |
| 本机镜像导出 | `docker image save sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40` 的 stdout，经 Python 增量摘要、64 MiB / 8 s 上限、独占新建文件保存；退出 0、4,289,024 bytes，SHA256 `b235aa410b8cf689f2ebfb340eac1f6ebe0d569b300f667809a59ca097787adb` |
| [离线镜像检查入口](../../scripts/inspect-linux-channel-image.py) | 消费原导出摘要与[前批候选观察](cvc5-control-plane-2026-11-01/channel-image-candidate.json)，核对 OCI 图 / descriptor / layer、APK 文件校验、执行字节与声明；不含 Docker 或网络调用 |
| [独立相对树核对](../../scripts/check-linux-channel-source-tree.py) | 不导入上述入口的判定函数；从同一 image tar 与固定原始 minirootfs 重算压缩摘要、diff ID、Git blob SHA1、发布清单 SHA512，再逐项比较文件树 |
| [本批合成测试](../../scripts/test-inspect-linux-channel-image.py) | 仅自有合成 tar / OCI / ELF 数据，无 Linux 工具或网络执行；检查篡改、预算、路径、关系、来源前缀与真实差异保留 |
| [镜像实际检查结果](cvc5-control-plane-2026-11-01/image-offline-inspection.json) | 由检查入口生成，带入口源码与候选原字节摘要；保留完整 514 项库存、16 包声明和失败 / 差异，不是成功接受记录 |
| [来源相对树比较](cvc5-control-plane-2026-11-01/image-source-comparison.json) | 由独立入口生成，带输入 / 入口摘要、明确的前缀归一规则和未比较字段 |
| [来源材料与许可矩阵](cvc5-control-plane-2026-11-01/image-offline-materials.json) | 保存实际获取 URL / 摘要 / 失败、16 包对应固定配方及参考内核文件身份；不是发布者签名或授权结论 |

检查器使用 Python 标准库，现有 static ZIP 检查入口限定 `ET_EXEC` / 无动态段，不能为本次 `ET_DYN` 放宽原规则；本次单独检查动态 ELF 的布局。归档范围固定为一个 arm64/v8 payload、单 gzip layer 和两类附带声明，不实现通用 OCI 管理器。拒绝未知 tar 类型 / 扩展、路径逃逸 / 重复 / 非目录祖先、特权位、未知 blob、混配摘要、解压 / JSON / 成员预算超额；没有网络 / 执行 / 接受入口。

## 实际镜像身份与内容

先前 `docker image inspect` 的 Id 在此 containerd 后端对应多平台 **index**，不能当成 config 摘要。实际链如下，均由留存 bytes 重算：

| 层级 | SHA256（不含前缀） |
| --- | --- |
| 多平台 index | `fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40` |
| Linux arm64/v8 manifest | `d858bb5442632a31bd4bca6c5e601dbe6b536fd7942092ea6a08a0a95805693c` |
| config | `1087dfd14fa77fe3bd102f39d42ee9c7e183876bd1a65f38fe2c18198ae976b4` |
| gzip layer | `14a4754c352fba4c6c0da8e4f01bb990463c19f7ff63e090073c385bd2bc5046` |
| 未压缩 tar / diff ID | `91d5cf66444f05b8c72e1b9d725c1752b9b015b68a7918125fc46ecdb7cc46d5` |

导出共 13 项，包含 8 个所选平台相关 blob；index 中另外 14 个平台 / 声明 descriptor 的 payload 未留存，不能外推其他平台。未压缩 tar 为 8,939,520 bytes、514 项，无特殊设备 / FIFO、hardlink、PAX 属性或 setuid / setgid 位。`etc/shadow` 是 `0:42 / 0640`；初版自有检查器错误假设所有组均为 0，已改为保留有界 UID / GID，同时继续要求执行文件归属 `0:0`，没有改变既有冻结检查器或将非零组静默改写。

`bin/busybox` 为 919,304 bytes，SHA256 `dd10691d81c84f0182f5af5f1583d566ddc0b9d0d9fc46b41b99b83c398306dd`；ELF64 LE / AArch64 / `ET_DYN`，解释器 `/lib/ld-musl-aarch64.so.1`，唯一 DT_NEEDED 为 `libc.musl-aarch64.so.1`，未见 RPATH / RUNPATH。loader 为 723,480 bytes，SHA256 `fc61b6e11fd8c6bfee3235865249cd78eea34aa36d88277e6008038031160993`，无额外 DT_NEEDED。sh / env / timeout 的链接解析到同一 BusyBox，libc 别名解析到 loader；这是静态字节与布局，不是 ABI / applet 运行资格。

config 的初始环境仅为固定 PATH，未见加载器注入变量；未来 create / 启动环境仍须独立读回，不能据此继承本机环境。没有把完整 rootfs、shadow 内容、私钥或凭据复制到仓库或日志；库存只保留路径 / 模式 / 身份与摘要。

## 来源关联、APK 差异和 SBOM 角色

所选 manifest 与附带 provenance 指向 [docker-alpine 固定提交](https://github.com/alpinelinux/docker-alpine/tree/4ad948cca27e7a605aa63ae1c59c22081a2c6d13/aarch64)。实际取得其 Dockerfile、未截断 Git tree、minirootfs 和 `checksums.sha512`；Dockerfile 内容为 scratch + ADD 固定 minirootfs + shell 默认命令。原 minirootfs **4,021,949 bytes**，SHA256 `d9a77cb31f715c56afa4f0a5aa42c04cfde813b70ad74a64725902b09c29a6cc`；Git blob `5d1dae18a0c27a6af3afaad29f0864b56a31085f` 和同提交 SHA512 清单均匹配。

源 tar 含单独 `.` 根目录头，其余路径带一个 `./` 前缀；镜像 tar 不含该头且不带前缀。最初按原路径比较自然不等，失败材料保留。独立入口随后显式记录根目录头 `0:0 / 0755`，只移除源路径的一个 `./`，拒绝归一后的冲突 / 逃逸，比较相对路径、类型、mode、UID / GID、字节数、链接原文和普通文件 SHA256，**514 / 514 全部相同**。没有比较 mtime / uname / gname / tar 编码，也没有取得容器实际根目录属性或运行挂载；不声明 tar 逐字节相同或运行环境等价。

APK 数据库列出的 109 项文件 / 链接校验，108 项匹配；`alpine-baselayout-data` 的 `etc/shadow` 与安装数据库 SHA1 不同，且独立比较确认该差异已经存在于固定原 minirootfs。**差异和实际检查退出码 2 保留**，不豁免该路径、不改写 DB、不把根树相同写成 APK 全等。Q1 SHA1 这里只作旧格式一致性核对，不是认证或抗碰撞来源证明。初轮工具在该项拒绝后，补成能留存完整差异诊断的入口；无接受或部分成功制品。

附带 SBOM / provenance 的 digest 和 subject 均绑定 arm64 manifest，但没有取得签名认证，仍为发行工具声明。SBOM 有 20 条 APK 记录，完整覆盖 16 个已安装包；额外的 `alpine-base`、`ca-certificates`、`openssl`、`pax-utils` 均对应 APK origin，且有 installed package → source 的 `GENERATED_FROM` 声明。原始 20 / 16 集合不等仍记录；不将来源记录计作另装了四个包，也不把关联声明当独立构建证明。

## 固定许可证声明与范围

16 个已安装包分属 10 个 origin；已取得每个 origin 在 APK 数据库所声明提交处的 APKBUILD，所有版本和对应 base / subpackage 许可证声明逐项一致，完整清单见材料矩阵。没有运行 shell 配方、构建包或验证 APK 包签名，不能因此宣布包内容已由发行者认证。

| 组成（同 origin 合并） | 固定版本 | 实际配方 / 数据库声明 |
| --- | --- | --- |
| alpine-baselayout / data | `3.7.2-r0` | GPL-2.0-only |
| alpine-keys；alpine-release | `2.6-r0`；`3.23.5-r0` | MIT；MIT |
| apk-tools / libapk | `3.0.6-r0` | GPL-2.0-only |
| busybox / binsh / ssl_client | `1.37.0-r30` | GPL-2.0-only |
| ca-certificates-bundle | `20260611-r0` | MPL-2.0 AND MIT |
| libcrypto3 / libssl3 | `3.5.7-r0` | Apache-2.0 |
| musl；musl-utils | `1.2.5-r23` | MIT；MIT AND BSD-2-Clause AND GPL-2.0-or-later（utils 函数覆盖） |
| scanelf | `1.3.8-r2` | GPL-2.0-only |
| zlib | `1.3.2-r0` | Zlib |

原 rootfs 未携带独立 COPYING / LICENSE 文件路径，不据此断言没有许可。取得 musl `v1.2.5` COPYRIGHT，以及同一 SHA512 的 BusyBox `1.37.0` 原源码 LICENSE 和 timeout 源码；均有原字节摘要与来源。BusyBox 主站归档首次获取报 `URLError`，该轮仅保留异常类、未留底层原因，不补造原因；随后明确改选 **Alpine v3.23 distfiles 固定缓存一次**，取得 2,565,764 bytes，SHA256 `3311dff32e746499f4df0d5df04d7eb396382d7e108bb9250e7b519b837043a4`，匹配 APKBUILD 的原 SHA512。此前 Docker recipe LICENSE 与 BusyBox LICENSE URL 的 404 均保留；不能把 recipe 没有 LICENSE 解读为整个镜像是 MIT。

本批实际来源日志共 27 项，24 项取得、3 项失败；选取的两份 BusyBox 源文件从已核对归档内存读取，不算额外下载。许可证层只形成固定版本声明和所取得正文的事实：未审阅所有补丁 / 文件级授权，未建立完整二进制到源码的认证链，不接受重新分发或生成运行时嵌入，不改变本仓许可证。不能用“诊断不会调用某包”抹掉整个可访问 rootfs 的组成与许可边界。

## 宿主读取权限的离线结论

留存上游 Linux **v6.18** 的七个固定文件作为参考；它不是实际 `7.2.12-orbstack-00394-gbecdd6130068` 的源码身份。当前未取得该精确宿主的实现 / patch / 配置 / LSM / 挂载属性绑定，不从参考代码升级实际可读性。官方通用 proc 文档不能替代逐入口检查。

| 白名单输入 | v6.18 参考实现的静态事实 | 保留前置 |
| --- | --- | --- |
| boot_id | `drivers/char/random.c` 注册 mode `0444` 的 proc sysctl；读取可能初始化 / 读取内核缓存 | 真实 source、sysctl / LSM 和挂载，不把读操作描述为内核零副作用 |
| filesystems | `fs/filesystems.c` 的 proc entry 通过 `fs/proc/generic.c` 默认 `0444` 注册 | 目标内核配置、文件系统身份与真实挂载来源 |
| PID 1 mountinfo | `base.c` 注册 `S_IRUGO`，该文件使用默认 inode 操作；`proc_namespace.c` 的 `mountinfo_open → mounts_open_common` 本身没有统一 ptrace 检查。`proc_pid_permission` / hidepid 是进程目录路径上的另一层 | daemon 解析 source 的目录检查，与诊断者对已绑定单文件的 open 必须分开；仍受实际 DAC / LSM / inode / namespace 等条件约束。不因非 root 一概判失败，也不因 bind 成功判可读 |
| cgroup | `cgroup_file_mode` 按 read / write 方法决定文件 mode；controllers / subtree_control 有读取方法。**cgroup.type 和 cgroup.events 标为 NOT_ON_ROOT** | 真正根层不能要求这两项；只在精确本实例非根 cgroup 读取 type / events / 限值。已定义根层缺项不是任意 ENOENT 豁免，实际权限 / 控制器 / 所有者仍待读回 |

据此修正最小方案的通用 ptrace 疑点和根 cgroup 文件清单，保持非 root、空 capabilities、只读白名单，不加 `CAP_SYS_PTRACE` 或修改宿主权限。实际目标源码 / runtime 路径关联和允许的真实读回范围仍未闭合。

## 新发现的内部超时拓扑阻断

已核对 BusyBox 上游 `1.37.0` timeout 源码与固定 Alpine 配置（`CONFIG_TIMEOUT=y`）。其正常路径派生中间子进程 / grandchild watchdog，监控**原进程 PID**，原进程随后 exec 被监控程序；它不是简单的“父监督器等待子进程”模型。

结合 [Linux PID namespace 的信号规则](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html)，若直接把 timeout / exec 链作为容器 PID 1，同 namespace 内 watchdog 不能以原方案假定的 SIGKILL 强制终止该 PID 1。源码的发信号 / 退出也不能被当成内核已终止目标。因此这是一项静态设计阻断，**未运行实测，不声称已复现本机超时故障**。

最小方案现要求：固定自有 PID 1 保持监督 / 回收身份，不 exec 成被监控程序；BusyBox timeout 与采集器位于非 PID 1 子进程，PID 1 等待并保留其真实退出，收束后才退出。所有进程仍计入原 16 PID / 128 MiB 候选额度；不得靠 shell 最后一条命令的隐式 exec、未审 `--init`、新增 cap 或依赖 daemon 的唯一计时器补救。具体启动器、信号 / 孤儿回收、PID 身份和取消 / 超额负例另行实现 / 验收，原 20 s / 90 s 不能写成已验证保证。

## 验证、已保留失败与结束决定

实际运行与结果如下，均未执行归档内程序：

- `python3.14 -O scripts/test-inspect-linux-channel-image.py`：20 项合成测试通过，包含关系篡改、预算 / 路径拒绝、真实校验差异保留和独立相对树比较；优化模式没有移除入口的显式拒绝检查。
- 镜像入口消费上表原导出、原候选和原导出 SHA256，独占输出 `inspection-reviewed.json`：退出 **2**，留存 APK 差异和 SBOM 严格集合不等；不是镜像接受成功，也不是未留证的工具崩溃。仓库报告与该原输出逐字节内容一致。
- 独立入口消费同一 image tar、表中 layer / diff ID、原 minirootfs / Git blob 与 `sources/rootfs-checksums.txt`，独占输出 `source-comparison-reviewed.json`：退出 0，514 项相对树相同；不消除前项 APK 差异。仓库报告与该原输出内容一致。
- `python3.14 scripts/check-repo.py`：完整仓库检查通过，2,903 文件；`git diff --check` 通过。局部核对通过：恰为本批 11 路径、17 处新增本地文档引用可解析、UTF-8 / LF / 无尾随空格 / `0644`、JSON 可解析、入口 / 候选 / 留存输入摘要绑定、声明矩阵和差异 / 未接受字段一致。

实际 CLI 参数可按上述入口的 `--help` 及输入表重建：镜像入口的 `--archive-sha256` 是 `b235aa410b8cf689f2ebfb340eac1f6ebe0d569b300f667809a59ca097787adb`；独立入口的 `--image-sha256` 同值，`--layer-sha256` / `--diff-id` 对应身份表，`--source-sha256` / `--source-blob-sha1` 对应来源段。两者 `--output` 均须使用尚不存在的任务专用文件，不覆盖已留存成功或失败材料。后续重核仍需这些实际输入，不以摘要替代留存字节。

未重跑无变化的 Rust workspace / cvc5 组件测试，也未运行任何 Linux syscall / 容器 / 目标 ELF、上游构建、solver、CI 或独立程序语义 checker。

离线切片到此结束：已具体化平台字节链、原始 rootfs 关系、16 包版本 / 许可声明、四类读取的参考路径，并找出超时和根 cgroup 清单问题；**镜像 not-accepted、execution_ready=false，原 G0 / C1 / E0 / E4 / A1–A10 实际资格均不升级**。下一切片先围绕明确的 PID 1 启动器 / 回收拓扑和精确宿主权限关联核定实施 / 接受范围；不重复全套来源清单、不自动重试失败来源、不扩大工具链，也不直接创建环境。publisher / 构建关联与完整可访问组成的许可接受仍须显式处理，范围决定不能伪装成已取得认证或许可事实。

大归档与第三方源码只在专用留存根；仓库保存自有入口 / 测试、机器可读观察与本记录，不嵌入镜像或第三方程序。没有后台进程、容器、machine 或卷需要清理，原包 / 既有失败材料保留。本批新改动未包含在 `aa162af` 中，最终路径、未提交 / 未推送状态由交接消息报告。
