# musl 验证环境受控运行入口与待执行方案

日期：2026-09-12；基线 `dev` / `dbab49c`。项目所有者要求提交工作区再推进；前批 10 个文件已精确提交，提交后工作区干净，相对本地 `origin/dev` 领先 6 个提交，未查询远端。本文面向本次来源诊断的实施者，记录入口行为、合成验证与待确认的实际动作，不定义 production runner 或新的公共格式。

## 已实现的入口

后续：项目所有者已确认下述实际动作与诊断工具信任范围；导入、四项运行、清理及字段映射修复见[真实执行记录](musl-verifier-smoke-execution-2026-09-12.md)。下文保留执行前的方案与合成检查事实，当前入口已修复，原方法原文在执行记录中留存。

[运行方法](run-musl-verifier-smoke.py)消费[前批已组装并读回的 tar](musl-verifier-preflight-2026-09-12.md#实际组装与读回结果)，复用原读回检查和静态路径解析，不重复下载或组装。默认只打印离线计划，不访问 socket、不创建目录或调用 Docker：

```bash
python3 docs/records/rust-linux-input-review/run-musl-verifier-smoke.py
```

`--action import` 与 `--action run` 是两个明确入口；只有同时给出 `--authorized` 与新的日志目录才进入执行。该 flag 仅表达操作者已经获得当前任务授权，本身不构成授权或技术安全屏障。本轮仅实现和测试，没有调用两个执行入口。

真实执行前检查既有 socket、Docker CLI 摘要、固定 plan / tar 摘要及 tar 全量读回。随后以白名单格式重读 daemon 版本与资源支持；版本或必需资源报告变化时停止。Docker CLI 固定为 `/usr/local/bin/docker`，解析到前批留存的 OrbStack 工具字节；连接固定为 `/Users/luobo/.orbstack/run/docker.sock`，API 固定 `1.54`，不根据宿主 Docker context 自动选择别处。

每次执行使用新任务目录中的空 `docker-config`，显式传递 `--config` / `--host` 和最小宿主环境，不继承宿主 Docker 凭据、代理或环境变量。只通过参数数组调用 CLI，不经 shell。Docker inspect 仅输出所列字段，完整 daemon 或其他容器配置不进入日志。

## 运行与清理行为

导入入口只读取固定 tar，以 `linux/arm64` 导入无滚动 tag 的本地镜像，并写入诊断来源 label。记录完整 image ID 后，检查平台、label 以及不存在意外的环境、入口命令、volume、OnBuild 或 healthcheck；失败保留已知 ID，不自动删除或重复导入。label 和 image ID 是在可信本地 daemon 操作下的关联信息，不是发行方签名或独立的来源证明。

运行入口只接受完整 `sha256:<64 hex>` image ID，先复核镜像元数据，再顺序执行前批列明的四项命令：gpg 版本、gpgconf 目录、gpg 与 gpgconf 的 loader `--list`。每项使用独立随机名称、批次 label 和新容器，禁止 pull。流程为：

1. `container create` 后，核对精确 ID、批次归属、命令、环境、限制与 `created` 状态；检查失败不启动。
2. `container start --attach` 捕获 stdout / stderr，空 stdin，无 TTY。
3. 保存退出状态，检查退出码、OOM、运行状态和配置；非零退出、警告 / stderr、输出或配置偏差均停止本批。
4. 清理前再次核对 ID / 名称 / label / image 的归属。仍运行则向精确 ID 发 KILL，读取终止状态后 remove；保存状态早于删除，不使用 `--rm`、force remove、prune 或按名称批量删除。

配置落实前批草案：`1000:1000`、只读 rootfs、network `none`、drop ALL、no-new-privileges、内置 seccomp、private cgroup namespace、`runc`、128 MiB memory 与同值 memory-swap、1 CPU、pids 32、core dump 0、log driver `none`、不重启、禁 healthcheck；`/tmp` 为 16 MiB tmpfs，`noexec,nosuid,nodev`。补充显式 `ipc=none`，避免额外共享内存区域。`/work` 保持镜像内预建只读目录，不以空 tmpfs 遮住 home 和 common.conf。

这些参数按 Docker 官方 [create](https://docs.docker.com/reference/cli/docker/container/create/) 和 [start](https://docs.docker.com/reference/cli/docker/container/start/) 入口编排。Docker 自行提供的 `/dev`、`/proc`、`/sys`、hosts / resolver 文件仍属于运行环境信任边界；inspect 清单不是完整 mount namespace 审计，也不证明内置 seccomp 对恶意程序的全部隔离效果。

gpg 版本必须为 `2.4.7`，gpgconf 的 home 必须为 `/work/full`；其余编译时辅助路径只记录观察，不据此启动缺失程序。loader 输出必须能按已审阅 rootfs 解析为常规文件，并包含 libc 映射；未知格式、缺库或越界路径拒绝。该检查并未证明实际重定位、IFUNC、密码学正确性或全部动态访问行为。

## 时限、输出与故障边界

| 操作 | 宿主命令时限 | 单路 stdout / stderr 上限 |
| --- | --- | --- |
| 单次导入 | 60 秒 | 256 KiB |
| version / info / inspect / create / kill / remove | 每条 10 秒 | 256 KiB |
| 四项附着运行 | 每项 30 秒 | 每项 1 MiB |

stdout 与 stderr 通过同一单调时钟 deadline 并行排空；恰好达到上限允许，超过即失败，保留至多上限的前缀且明确记录超限。到时或超限后终止并回收 CLI 进程组，随即另发 Docker KILL；不能把 CLI 被终止当作容器已经终止。关闭输出管道仍不退出的进程也受到时限约束。客户端回收另最多等待 2 秒。

四项运行等待合计最多 120 秒；控制和清理命令另计。按顺序调用的上限计算，正常完整批次预计 1–3 分钟，故障及清理预留后整体预算为 10 分钟。**30 秒是宿主发起终止的 deadline，不是 daemon 失联或宿主被强制终止时仍可证明的 guest 停机硬限**；kill 控制请求还有自己的等待上限。此入口不能满足或替代 ADR 0015 的 production guest 限制与 qualification。

超时、日志写入失败、daemon 错误与实际输出会进入编号日志 / 结果；日志存储完全不可写时无法保证最终报告落盘，不能声称证据完整。宿主崩溃、SIGKILL、daemon 无响应、恶意后代逃逸客户端进程组不在自动回收保证内。遇到这些情况保留任务目录，人工依据精确 ID 补查；没有后台 watchdog 或无限重试。

创建请求超时且未收到完整 ID 时，报告随机任务名称和“不确定”，不按名称强制删除，也不以即时查询不到就证明不存在——daemon 可能稍后才完成创建。已知 ID 的 inspect、kill 或 remove 失败同样使批次失败并明确未确认清理。镜像保留给下一步验签诊断，不在本次自动清理范围；以后只有核对精确 ID 与使用者后才另行删除。

## 下一次确认的精确范围

尚未授权实际导入、容器执行或工具信任。本次可供项目所有者一并确认的范围是：

- 接受固定 Debian 工具包字节、发行版构建，以及本次 macOS / OrbStack / Docker / Linux / runc 执行环境为本次诊断的可信输入。既有 HTTPS 公钥身份授权不自动扩展到这项工具信任；它不构成工具链形式证明、musl acceptance 或产品 qualification。
- 只导入下列固定 tar；成功后使用返回的完整 image ID 执行四项只读诊断，并按上述精确 ID 清理本批容器。
- 只在项目任务目录新增日志与空 Docker 配置，并在既有 OrbStack daemon 内新增一个诊断镜像及最多四个顺序容器。无网络下载、宿主业务目录挂载、全局安装或系统配置修改。

固定输入为 `.tmp/musl-preflight-80768b6-20260912/rootfs.tar`，8,407,040 bytes，SHA-256 `f1ac49bc29d33182a9c9a070b70509c739d857369876afbe307b9e9898d6b8b3`。全部相对路径的绝对前缀为 `/Users/luobo/Code/RadishAxiom/`。

导入命令：

```bash
python3 docs/records/rust-linux-input-review/run-musl-verifier-smoke.py \
  --action import --authorized \
  --output .tmp/musl-smoke-dbab49c-20260912/import
```

成功后读取 `import/result.json` 的 `image_id`，将其原样作为下列参数；`<IMPORT_RESULT_IMAGE_ID>` 只是说明性占位，不能直接执行或编造：

```bash
python3 docs/records/rust-linux-input-review/run-musl-verifier-smoke.py \
  --action run --authorized --image-id <IMPORT_RESULT_IMAGE_ID> \
  --output .tmp/musl-smoke-dbab49c-20260912/run
```

两个输出目录必须全新，故障后保留原目录，不原地重试。四项共最多 8 MiB 程序输出，加有界控制输出及元数据，本批日志预算 32 MiB；daemon 中镜像存储包括 layer / metadata 开销，不能用 tar 大小宣称相同物理占用。只读 rootfs 仍会产生容器管理层元数据，正常清理会删除本批容器，镜像保留并报告 ID。若清理失败，报告精确目标和原因，不进行宽泛回滚。

## 本轮实际验证与交接

新增 [23 项合成检查](check-musl-smoke.py)通过：真实合成子进程的双流排空、stdin EOF、恰好限额 / 超一字节、超时回收、关闭管道后不退出、非零退出与警告；模拟 Docker 的配置偏差阻止启动、超限先 kill 再 inspect、OOM、失败停止后续项、容器归属拒绝、创建不确定、daemon 失联、清理失败、启动后日志写入失败、导入检查失败仍保存 image ID 等。导入测试替换了宿主输入检查与 Docker 适配，不连接真实 socket；合成测试不构成 Docker 实际行为验收。

实际只读前置复核也已通过：固定 tar 摘要与 84 项内容、Docker CLI 摘要和既有 socket 类型均匹配，没有调用 Docker。该次方法为 23,080 bytes / SHA-256 `f33d178cb9f6ddb9c4ce24f97608d1f7a9ae1202c7c7ac9d7a620924c27d8cb0`，原输出保留为任务目录中的 `input-preflight.json`。

只运行了上述测试、只读输入检查和默认离线计划。日志保留在 `.tmp/musl-smoke-dbab49c-20260912/`；`import/`、`run/` 尚不存在，没有新镜像或容器，无本批后台进程。前批 tar、归档和缓存未改动。未运行 GnuPG、Rust / CI、联网下载、安装、远端写入或新的密码学验签。`./scripts/check-repo.sh` 通过（1,128 个文件），`git diff --check` 通过。

当前 `source_acceptance = not-assessed`，`runtime_qualification = false`。本轮方法、测试、交接及当前状态更新未提交；已有 `dbab49c` 等 6 个提交未推送。下一步只在确认上述实际动作与工具信任范围后执行；第一处失败即停止并复核，不自动放宽配置。
