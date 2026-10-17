# cvc5 Linux arm64 静态验收与窄入口准备记录

日期：2026-10-17。范围：当前任务授权的只读环境检查、精确发布包获取与静态验收、窄入口 ADR / 执行层设计。未安装、解包到工具目录或启动 cvc5，未构建 / 启动容器或 VM，未修改系统配置、依赖或远程状态。

## 基线与结果

上一批 25 个实现 / 验收文件已按项目所有者要求提交为 `d055658`（`feat(query): 实现紧凑查询与 P4 显式接入`）。本准备批次从干净 `dev` 开始，相对本地 `origin/dev` ahead 5，未刷新远端。本批新材料未提交。

已确定现有 **OrbStack Linux arm64 Docker 宿主**作为执行设计候选，状态为 `selected-for-design-not-qualified`。精确 cvc5 ZIP 的来源 / 摘要、包内路径 / 字节以及 CLI 静态 ELF 布局通过检查；完整链接依赖、许可证、运行能力及隔离资格未通过验收，不能将本结果登记为 accepted payload。

本批产物：[ADR 0028（Proposed）](../adr/0028-bounded-solver-calibration-entry.md)、[执行层设计（Proposed）](../query/solver-execution-preparation.md)、以下三份只读观察及两个标准库诊断脚本。没有修改生产 Rust、旧 query / P4 规则或公共工具契约。

## 宿主只读观察

[host-observation.json](cvc5-linux-arm64-preparation-2026-10-17/host-observation.json)只保留本次判断需要的字段；完整筛选前 Docker info 留于本机 `.tmp/solver-preparation-2026-10-17/docker-host.json`，其摘要写入观察。

| 项目 | 实际观察 | 限制 |
| --- | --- | --- |
| 物理主机 | macOS 27.0.1 / arm64 | 不沿用旧 macOS 26.6.2 的资格 |
| Docker | 当前 context `orbstack`，server 29.8.2，daemon ID 见 JSON | 已有服务，只做只读调用；未选择其他 context |
| Linux | aarch64，kernel `7.2.9-orbstack-00391-g2b298d05fbd4`，cgroup v2 / cgroupfs | daemon 报告，未在新进程内验证 |
| 资源能力 | daemon 报告 memory / swap / pids limit 可用，seccomp builtin / cgroupns | 不是限制已施加或负向探针通过 |
| runtime | runc 1.5.2，libseccomp 2.6.0；namespace 清单见 JSON | 未认证所有组件来源或执行配置 |
| 已有负载 | Docker 报告 0 个运行中容器；读取已有镜像元数据 | 未使用任何已有项目镜像作 solver rootfs |
| UTM / OrbStack machine | `utmctl list` 的九台 VM 均停止；`orb list` 成功但 stdout 为空 | 未启动 VM，不借用其他项目环境 |

实际使用只读 `docker context ls`、`docker info --format '{{json .}}'`、镜像元数据列表、`utmctl list`、`orb --help` / `orb list` 与主机 / PATH 检查。初次沙箱 Docker socket 被拒，按权限流程重跑只读调用；沙箱内 `orb list` 挂起后中断，获得权限后只读重跑成功。没有把这些失败算作能力通过，也没有以启动服务修复环境。

选择理由：已有运行中的 Linux arm64 Docker daemon，不需启动停止的 VM；能够先设计并验证与宿主隔离的单进程路径。尚缺 cgroup 限值实际读回、OOM、timeout、syscall 拒绝、固定二进制加载、空环境、流与清理探针。当前没有选定或生成执行镜像，没有可调用的生产 executor。

## 精确制品与静态检查

来源：[cvc5 1.3.4 官方 release](https://github.com/cvc5/cvc5/releases/tag/cvc5-1.3.4) 的 `cvc5-Linux-arm64-static.zip`，不是 `-gpl` 变体。获取 release 元数据和该单一制品，没有获取其他依赖、源码链或安装工具。

| 对象 | 实测身份 |
| --- | --- |
| 发布资产 | ID 414512582；release ID 319022075，tag `cvc5-1.3.4` |
| ZIP 长度 | 41,650,395 bytes |
| ZIP SHA-256 | `2a4c108367f20b0c8990abd6b9535a5d62e08908d471d4671c00734e408f85bc`；与仓库登记及公开 release API 摘要一致 |
| CLI 成员 | `cvc5-Linux-arm64-static/bin/cvc5`，27,115,880 bytes |
| CLI SHA-256 | `26fa94d71ecb3d4f1458eb06b9b9d4762fb3753cfb5cb9dca6f917fbf4dbe6c7` |
| ZIP 内容 | 48 entries，解压内容总长度 140,369,085 bytes；均为普通文件 / 目录，无链接或特殊类型 |
| CLI 布局 | ELF64 little-endian，ET_EXEC，AArch64，6 个 program headers；无 PT_INTERP / PT_DYNAMIC，入口在 executable LOAD 内 |

[publisher-asset-observation.json](cvc5-linux-arm64-preparation-2026-10-17/publisher-asset-observation.json)绑定选定资产字段与下载元数据 raw digest。API 摘要和 HTTPS 获取不是发布者签名验证，也不证明二进制与源码对应。

[static-inspection.json](cvc5-linux-arm64-preparation-2026-10-17/static-inspection.json)绑定登记文件、检查脚本、ZIP 及每个文件的实际摘要，记录 ELF headers、许可文件路径与包内版本线索。脚本只在内存中读取 ZIP 成员；未加载或执行 ELF，未向文件系统提取成员。无动态加载段只支持静态布局判断，不能证明运行期不访问文件、网络或宿主功能。

下载先因沙箱代理不可达失败，再经授权执行相同精确 URL 获取成功；没有改 URL 绕过或下载替代构建。原包与 API 原始响应保存在 `.tmp/solver-preparation-2026-10-17/`，不提交第三方二进制、SDK 或许可证全文。

## 依赖 / 许可证未闭合部分

包内含 SDK headers、`libcvc5*.a`、GMP / GMPXX、CaDiCaL、LibPoly 静态库、JNI `.so` 及 JAR。拟议执行 rootfs 只采用 CLI，其他文件不因同包存在而获准安装或分发。

实际读取包内 COPYING / AUTHORS / licenses 后发现：存在 LGPLv3、GPLv3、GCC exception、Apache LLVM exception、MiniSat 文本；GMP pkg-config 声明 6.3.0。CLI 可见 `cadical-2.1.3-elevate-f3b21c4` 字符串，**仅是未认证构建线索**。包内 COPYING 对 cvc5、GMP、CaDiCaL、SymFPU、编译器 runtime 和可选组件说明不能替代该精确 CLI 的完整组件清单。

待补范围限于本次 CLI：确认实际链接的 CaDiCaL、SymFPU、LibPoly、libc / 编译器 runtime 及其他组件的精确版本 / 来源、适用许可证与必要归属，区分“SDK 随包附带”与“CLI 实际链接”；补齐缺失文本 / 静态链接适用义务与来源校验审阅。不沿猜测自动开启 GCC / headers / guest 全链取证；若发布材料不足，先报告最小补证对象与停止点。

`non-GPL` 文件名不表示包内不存在 GPL 许可文本，也不自动免除 LGPL / runtime 义务；本记录没有给出完整许可证接受结论。正式 registry / acceptance 生成材料保持原字节、`not-accepted` 状态；本记录补充“已获取并静态检查”的新事实，不重写历史指定态。后续正式接受须用可追溯生成路径，不手填 accepted。

## 可重跑检查与本批验证

新增 [inspect-cvc5-static-zip.py](../../scripts/inspect-cvc5-static-zip.py) 仅检查登记的 1.3.4 Linux arm64 ZIP；读入最多 64 MiB 的同一不可变字节串后核对摘要，避免校验后重开 archive 路径。拒绝路径穿越、重复、链接 / 特殊文件、特权位、加密、未知压缩、缺父目录和预算超限；逐成员读取验证 CRC、长度及摘要，再检查 CLI ELF。输出只允许新建，不覆盖旧观察。

```bash
python3 scripts/test-inspect-cvc5-static-zip.py
python3 scripts/inspect-cvc5-static-zip.py \
  .tmp/solver-preparation-2026-10-17/cvc5-Linux-arm64-static.zip \
  .tmp/solver-preparation-2026-10-17/static-inspection-recheck.json
./scripts/check-repo.sh
git diff --check
```

重跑输出路径必须尚不存在。合成测试覆盖 ZIP / ELF 正例，路径 / 链接 / 特权 / 预算 / 架构 / 动态段负例，错误归档摘要与既有输出不可覆盖；不启动 solver。

实际结果：6 项合成测试通过；真实 ZIP 重检通过且输出与持久 `static-inspection.json` 逐字节一致。6 项来源 / 观察身份关联核对通过；2,080 份既有源码、契约及规范文件与 `d055658` 字节一致，242 个本批文档链中的本地链接目标存在。仓库检查通过（2,642 文件），`git diff --check` 通过；日志留存 `.tmp/solver-preparation-2026-10-17/check-repo.log`。最终复核未跟踪文件仅为本任务材料，无工具二进制、缓存或权限变化进入提交候选。

未重跑 Rust workspace 测试：本批没有 Rust、依赖或已绑定规范变更；上一实现批次的 294 项测试与有限比较结果见[生产验收记录](2026-10-17-compact-query-production-validation.md)。本次静态 ELF 检查不补足真实 model / proof、Linux 运行、资源隔离或独立 checker 验收。

## 后续边界

ADR 0028 与执行层设计保持 Proposed；现有宿主已选定为诊断候选，但不是 qualified。后续先决定窄入口与资源记账口径，再完成有明确投入上限的依赖 / 许可证补证和执行层实施准备。当前任务授权到静态验收与设计为止，不启动 solver、镜像构建 / 容器探针、系统配置或远程动作；原包及失败材料留存，不擅自清理。

后续接受：项目所有者于同日接受 ADR 0028 的 D1–D3，并要求先提交本批准备材料，再推进精确 CLI 依赖 / 许可证补证及执行层实施清单。本文中 Proposed 与未提交描述保留准备完成时事实；现行决定见 ADR 0028，提交身份由当前状态与交接报告接续。未授权镜像构建、探针、solver、系统配置或 push。
