# musl 验证环境资源观察与离线组装方案

日期：2026-09-12；基线 `dev` / `80768b6`。项目所有者要求先提交再继续，前批 8 个文件已提交，提交后工作区干净，相对本地 `origin/dev` 领先 5 个提交，未查询远端。用途：把 daemon 资源报告、精确 rootfs 文件 / 配置、已确认组装的读回结果和首次有限执行范围交给实施者审阅；不接受工具信任起点、不执行 GnuPG，也不构成产品隔离验收。

## 资源能力的实际观察

后续：本批已提交 `dbab49c`；受控运行、失败清理入口及新的待执行范围见[下一批记录](musl-verifier-smoke-entry-2026-09-12.md)。下文保留组装时的事实与当时草案。

[只读采集方法](inspect-musl-verifier-capabilities.py)只允许通过已存在的 Unix socket 对 `/version` 和 `/v1.54/info` 发起 GET，不调用 Docker CLI 或启动应用。API / Linux arm64 平台改变时不继续资源查询。每次 socket I/O timeout 为 5 秒，响应最多读取 256 KiB + 1 字节；它不是整体墙钟硬限或 daemon 资源消耗保证。

第一轮因沙箱 socket 权限返回 `PermissionError / errno 1`；获准沙箱外重试后，两项请求均 HTTP 200，实际成功区间为 `2026-09-12 12:53:26.035568–12:53:26.115029 UTC`。失败与成功记录见[完整白名单观察](musl-verifier-capabilities-2026-09-12.json)。原响应只在内存中处理，保留长度 / 摘要和白名单字段，不保存可能包含代理、凭据或无关 daemon 配置的完整 `/info`。

| 字段 | daemon 报告 |
| --- | --- |
| Engine / API | `29.4.0` / `1.54`，与前批相同 |
| Kernel / 架构 | `7.0.11-orbstack-00360-gc9bc4d96ac70` / `aarch64` |
| Cgroup | version `2`，driver `cgroupfs` |
| MemoryLimit / SwapLimit / PidsLimit | 均为 `true` |
| CpuCfsPeriod / CpuCfsQuota / CPUShares / CPUSet | 均为 `true` |
| SecurityOptions | `name=seccomp,profile=builtin`、`name=cgroupns` |
| Storage driver | `overlayfs` |
| NCPU / MemTotal | `10` / `16,820,461,568` bytes，属于 daemon 可见环境，不是本次容器额度 |

所有选定字段均存在；字段类型不符、非法控制字符、非白名单请求均拒绝。缺失或 null 独立记录，不当作 false 或默认支持。`runtime_limits_verified = false`：支持报告不证明实际 cgroup 限制、网络隔离、挂载、OOM、超时或清理已经有效。Docker 官方[资源限制说明](https://docs.docker.com/engine/containers/resource_constraints/)也区分内核支持检查和具体容器资源配置。

## 已准备的精确组装入口

[组装方法](prepare-musl-verifier-rootfs.py)已经实现并完成只读计划生成，输入直接来自已归档对象库，不依赖原 `.tmp` 包文件或联网包管理器。它先固定归档 manifest SHA-256，再核对所用 21 个归档输入对象：18 个原包、包清单、前批布局摘要与许可盘点。原包仍在内存中展开；默认只输出 JSON，只有明确传入 `--assemble` 才写 tar。

[文件与配置计划](musl-verifier-rootfs-plan-2026-09-12.json)包含 **84 项 / 8,347,816 bytes 常规文件**：

- 原 70 项程序、库、许可文件、链接与目录；
- 9 个明确新增目录：`etc`、`etc/gnupg`、`work`、`work/full`、`work/self`、`tmp`、`dev`、`proc`、`sys`；
- 5 个配置文件：合成 `passwd`、`group`、仅 files 后端的 `nsswitch.conf`，以及两个零字节 `common.conf`。

工作目录及 home 在 tar 元数据中属于 `1000:1000`、模式 `0700`；common.conf 为 `0600`，系统配置为 `0644`。其余新增目录为 root / `0755`。精确生成文字及摘要全部在 JSON 中，未把原包不存在的配置伪称为 Debian 文件。根 `lib → usr/lib` 保留前批拟生成来源标记。

首次有限执行仅做只读 smoke，`/work` 将保持 image 中预建的只读目录，不挂载 tmpfs 覆盖它，否则会丢失预建 home 和空配置。`/tmp` 可在运行时单独挂载有界 tmpfs。今后的公钥导入需要另行准备有界可写 home 的初始化与回收方案，不能把本次只读配置直接用于导入。

组装会输出普通 USTAR 文件；只在 tar 头内记录 root / UID 1000 与模式，不调用宿主 chown，不解压到宿主路径，不执行安装脚本、loader 或 GnuPG，不调用 Docker。输出独占创建，已有文件拒绝覆盖；全部文件与链接先核对，模式不允许 setuid / setgid，路径祖先必须是列明目录，链接必须留在模型内并找到目标。该诊断 tar 不替代产品严格 USTAR 契约或 production installer。

当前方法 SHA-256 为 `c098240041c51f2dcb5793eb726fec58a6ed9b7eed25522de76a0246a3749080`。已运行的只读入口：

```bash
python3 docs/records/rust-linux-input-review/prepare-musl-verifier-rootfs.py \
  --store artifacts/source-inputs/musl-verifier-2fb2e70-20260912
```

### 已确认并执行的范围：只组装 tar

项目所有者在审阅以下精确范围后回复“确认”，已执行一次：

```bash
python3 docs/records/rust-linux-input-review/prepare-musl-verifier-rootfs.py \
  --store artifacts/source-inputs/musl-verifier-2fb2e70-20260912 \
  --assemble .tmp/musl-preflight-80768b6-20260912/rootfs.tar
```

输出目标的绝对前缀为 `/Users/luobo/Code/RadishAxiom/`。授权时预计 1–3 分钟，tar 含头和填充预计小于 9 MiB，方法本身以 16 MiB 输出复核上限拒绝超限。追加 JSON / 日志亦在同一任务目录；实际结果见下节。同名产物已存在，不应直接重跑组装命令。

副作用只有新的 tar 和检查日志；原归档和缓存不变，无网络、后台进程、系统写入、镜像导入或程序执行。不需要系统回滚；失败保留部分文件，不能重用同名输出覆盖故障。成功后用独立 tar 读取复核条目集合、路径、类型、模式、owner、链接和文件摘要，再绑定产物身份；清理只处理经确认的这个产物及本批日志，不递归删除目录。

### 实际组装与读回结果

组装于北京时间 `2026-09-12 21:04:19` 完成，退出 0、stderr 为空。实际 tar 为 **8,407,040 bytes**，SHA-256 为 `f1ac49bc29d33182a9c9a070b70509c739d857369876afbe307b9e9898d6b8b3`。组装输出除新增 tar 身份及 `rootfs_assembled = true` 外，与原 84 项计划完全相同；原计划保留组装前的 `false`，不改写历史输入。

[读回方法](inspect-musl-verifier-rootfs.py)不导入组装器或其验证函数，只读取 tar 和已审阅计划，检查条目集合、类型、mode / UID / GID、mtime、链接文字、常规文件长度 / SHA-256、头格式和零填充。它与组装器共享 Python `tarfile` 标准库，属于独立比较路径，不宣称解析器独立或形式证明。另用宿主 `/usr/bin/tar -tf`（`bsdtar 3.5.3 / libarchive 3.7.4`）交叉枚举，84 个路径与计划相符；该第二实现只复核路径清单，不复核全部文件内容。

实际 **39 个常规文件 / 30 个目录 / 15 个符号链接**均与计划相符，常规文件合计 **8,347,816 bytes**。两条读回命令均退出 0、stderr 为空；完整命令、时刻、方法 / 计划 / tar 摘要见[读回报告](musl-verifier-rootfs-readback-2026-09-12.json)。可重复执行的只读入口：

```bash
python3 docs/records/rust-linux-input-review/inspect-musl-verifier-rootfs.py \
  --plan docs/records/rust-linux-input-review/musl-verifier-rootfs-plan-2026-09-12.json \
  --tar .tmp/musl-preflight-80768b6-20260912/rootfs.tar
```

tar 与原始组装 / 读回日志保留在该任务缓存；脚本、计划和摘要报告进入本批待提交文件。tar 可由已归档原包及精确入口重建，本轮没有新增独立或异盘 tar 副本。读取过程没有向宿主展开归档、修改 ownership 或执行包内程序。

## 随后的有限执行草案（本次不授权）

tar 内容验收后，另行授权导入一个仅供本诊断使用的 Linux arm64 镜像。Docker [image import](https://docs.docker.com/reference/cli/docker/image/import/)会改变 daemon 的本地镜像状态，不能把“写出了 tar”当作镜像已经存在或获得运行许可。届时先固定 tar 摘要，保存实际导入 image ID，以该 ID 调用，不用滚动 tag 或自动 pull；镜像 ID 不是发行方签名认证。

首次候选运行固定为以下四项，每项使用新容器，顺序执行，无并发：

| 项 | 容器内命令 |
| --- | --- |
| GnuPG 版本 | `/usr/bin/gpg --batch --no-tty --no-options --homedir /work/full --no-autostart --disable-dirmngr --version` |
| 配置目录 | `/usr/bin/gpgconf --homedir /work/full --list-dirs` |
| gpg loader 依赖 | `/lib/ld-linux-aarch64.so.1 --list /usr/bin/gpg` |
| gpgconf loader 依赖 | `/lib/ld-linux-aarch64.so.1 --list /usr/bin/gpgconf` |

只有上述输出允许列入 smoke 结果；不追加 import、check-sigs、decrypt、联网、daemon 启动或 shell。loader 自身也属于包内程序，必须纳入执行授权。预计的配置要求如下，尚未创建容器或验证生效：

- user `1000:1000`；只读 rootfs；显式 `PATH=/usr/bin`、`HOME=/work`、`LC_ALL=C`、`TZ=UTC0`；空 stdin、无 TTY，不继承宿主环境。
- network `none`；不发布端口、不挂载宿主 HOME / socket / Docker socket /业务目录；不使用 privileged / host namespace；drop 全部 capabilities，设置 no-new-privileges，保留 daemon 内置 seccomp，private cgroup namespace。
- memory `128 MiB`，memory+swap 合计同为 `128 MiB`；CPU quota `1 CPU`；pids `32`；关闭 core dump。`/tmp` tmpfs 为 `16 MiB`、`noexec,nosuid,nodev`，模式 `1777`，不另提供可写数据挂载。
- 每项运行墙钟 30 秒，四项运行合计最多 120 秒，超时立即 kill 精确容器 ID；每项 stdout / stderr 各 1 MiB，捕获超限立即终止，禁止通过截断后仍标成功。daemon 日志驱动应禁止重复无界落盘，并由有界 host 收集器保留附着输出。

上述内存数值只服务于本诊断容器草案，不替代 ADR 0015 对 production guest 的内存语义，也不限制整个 OrbStack / macOS 进程树。Docker 官方说明同值的 memory / memory-swap 表示容器不可使用额外 swap，CPU quota 控制可用 CPU 份额；这些仍需在真实创建配置中核对并与[资源说明](https://docs.docker.com/engine/containers/resource_constraints/)一致。

执行前后保存白名单 inspect 字段、实际退出码 / OOM 状态、请求限制和输出。版本不符、库路径越界或缺失、非零退出、OOM、写入失败、超时、超限、daemon 断开均停止本批，不换库、不降低限制或追加工具；目录和 loader 输出只是观察，不证明动态导入路径或资源攻击负例已覆盖。

清理应在最终状态和输出留存后针对本次精确容器 ID 执行 remove；避免 `--rm` 在检查退出状态前删除证据。每项 kill / remove 另设有限控制超时，daemon 失联时明确报告无法确认清理，不声称容器已消失。镜像只有核对本批 ID 且无其他使用者后才按授权删除，不使用 prune、宽泛 tag 或通配删除。完整收集 / 终止 / inspect / cleanup 入口尚待实现和合成检查，因此本文还不是可直接执行的容器命令脚本。

## 信任与尚未完成项

Debian HTTPS / WebPKI 对既有公钥身份的已确认范围不变。把固定发行版二进制、发行版构建、宿主 macOS / OrbStack / Linux / Docker / runc 作为本次工具执行的可信输入，仍需项目所有者明确接受；不以 GnuPG 复核自己所在 Packages 的签名宣称自举信任已证明。组装 tar 本身不会接受这一假设。

本机归档与恢复已经可用，异盘备份尚未落实；这不阻断当前只读资源审阅和方案准备。正式 musl 两角色验签仍需新一批受控公钥导入、状态解析、反例 / 失败传播和材料时间边界检查；本次 smoke 即使将来成功，也不完成这些验收。

## 检查与交接

授权前 7 项合成检查及 1,123 文件仓库检查通过，默认计划重跑逐字节一致；当时真实 tar 尚不存在。确认组装后新增 3 项读回检查，本次 `check-musl-preflight.py` 共 **10 项通过**，覆盖内容损坏、元数据 / 链接 / 类型不符、缺项、重复、头损坏及尾部 / padding 异常的拒绝路径。测试只使用 `abc` 合成文件；真实 tar 另按上节命令完成读回。`./scripts/check-repo.sh` 通过（**1,125 个文件**），`git diff --check` 通过。

只读 API 请求与组装 / 读回均已结束，无本批后台进程。本批没有新下载、安装、镜像、容器、GnuPG、Rust / CI、系统配置或远端写入。前批已提交 `80768b6`；本批采集 / 组装 / 读回方法、测试、计划与记录及当前状态更新尚未提交或推送。下一步实现有界运行与清理入口并完成合成检查，之后再提交具体镜像导入 / 有限执行及工具信任范围供确认。
