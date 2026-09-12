# musl 验证材料独立归档、恢复与宿主身份

日期：2026-09-12；用途：供后续验证环境实施者恢复来源原文、复跑静态诊断，并区分宿主身份观察与运行验收。基线 `dev` / `2fb2e70`；项目所有者要求提交工作区并继续，前批 13 个文件已精确提交，提交后工作区干净，相对本地 `origin/dev` 领先 4 个提交，未查询远端。本文不是完整项目 source lock、异盘备份、工具来源验收或容器执行许可。

## 已建立的本机独立副本

已将 **132 个精确文件**按内容 SHA-256 去重为 **87 个对象 / 28,655,060 bytes**，放入项目内：

```text
artifacts/source-inputs/musl-verifier-2fb2e70-20260912/
  manifest.json
  objects/<SHA-256>
```

绝对前缀为 `/Users/luobo/Code/RadishAxiom/`，该目录约占 28 MiB。沿用仓库现有 `artifacts/` 忽略规则，没有新增第二套 `.artifacts/` 配置。开始时向项目所有者询问是否已有指定归档位置；执行时尚未收到替代位置，按已说明的项目内默认方案完成可逆的本地复制。没有使用或写入云盘、远端、系统安装目录或工作区以外目录。

[精确清单](musl-retention-manifest-2026-09-12.json)为诊断用途的版本化 manifest，SHA-256 为 `3937d4570faa72ec359dbedf8fdc9c62aa5f26942cc08ee29d1a809e03a54ae9`、31,477 bytes。每项绑定恢复相对路径、用途、原始长度和摘要，存储目录中的 manifest 与 Git 待提交副本完全相同。选择范围由[归档方法](retain-musl-verifier-inputs.py)的 `plan` 固定，不扫描或整包复制所有缓存：

- 已下载的 17 个验证工具包与 base-files 许可包，固定 Packages 与 Sources；
- musl 原始归档、上游签名、公钥与 releases 页面，保留已有弱签名拒绝的原始材料；
- Debian InRelease、keyring 原包、指纹页面、archive 公告和两份官方公钥；
- 本轮工具包、索引、许可包的成功 / 失败获取输出及方法，已入 Git 的来源记录；
- 内容、许可、公钥材料及静态布局重跑需要的原始方法、辅助 reader 和预期报告，包括必要的历史观察引用。

源码索引原文 **10,527,804 bytes**整体保存，没有拆分、重写或为入 Git 放宽 10 MiB 门禁。相同公钥及空失败正文可共享内容对象，但所有原始恢复路径仍分别在清单中。没有将完整 `.tmp`、无关 Rust / kernel 输入、私钥、宿主用户配置或所有历史实验打包；因此不是整个项目的完整 source lock。

## 写入与恢复行为

方法先核对清单中全部源文件，再独占创建目标目录；只写常规文件，以 `fsync` 同步对象及 manifest，不覆盖已有目标，不删除源文件。manifest 在对象写完后生成；中途失败保留不完整目录供诊断，不能凭目录存在就判定成功。接续失败任务须使用新且明确的目标路径，不清空旧目录冒充首次运行。

读取拒绝符号链接路径、非普通文件和超限输入；清单拒绝绝对路径、`..`、`.git`、重复路径和文件祖先冲突。单文件 16 MiB、累计 128 MiB、最多 512 项、manifest 1 MiB。恢复先逐项验证已归档对象，再写入新的恢复根，最后重新读回全部目标验证摘要；缺对象、多余对象、内容损坏或 manifest 不匹配均不能成功。

这些是本地诊断工具的边界，不是生产 descriptor-relative store。它没有针对恶意并发目录替换提供完整竞态保证，没有使用 Darwin full-sync，也不声明物理断电或介质失效下的耐久保证。恢复只保留文件内容和原路径，采用普通文件创建模式，不复制可执行位、所有权、扩展属性或系统安装状态；所有自有检查方法均由显式 Python 调用。

可复跑入口如下。`pack` / `restore` 的目标必须不存在；本批目标已存在，重复执行会拒绝覆盖。先审阅新目标路径再另开一轮，不直接复用现有目录：

```bash
python3 docs/records/rust-linux-input-review/retain-musl-verifier-inputs.py plan --source .
python3 docs/records/rust-linux-input-review/retain-musl-verifier-inputs.py pack \
  --source . \
  --manifest docs/records/rust-linux-input-review/musl-retention-manifest-2026-09-12.json \
  --destination artifacts/source-inputs/musl-verifier-2fb2e70-20260912
python3 docs/records/rust-linux-input-review/retain-musl-verifier-inputs.py restore \
  --source artifacts/source-inputs/musl-verifier-2fb2e70-20260912 \
  --manifest docs/records/rust-linux-input-review/musl-retention-manifest-2026-09-12.json \
  --destination .tmp/musl-retention-2fb2e70-20260912/restore
```

新归档先保持本机内部用途，不自动进入公开 Release、制品托管或再分发；这些外部动作与相应许可责任另行确认。

## 实际恢复验证

已经仅从对象目录恢复到 `.tmp/musl-retention-2fb2e70-20260912/restore/`，全部 132 个文件重新读取后与 manifest 一致。以恢复目录为 cwd，用恢复出来的方法及相对输入路径执行下列四条检查，均退出 0、stderr 为空，stdout 与恢复出来的原报告**逐字节一致**：

| 检查 | 预期报告 | 输出 bytes |
| --- | --- | --- |
| 原包内容摘要 | `musl-verifier-content-summary-2026-09-12.json` | 28,548 |
| 许可补充盘点 | `musl-verifier-licenses-2026-09-12.json` | 45,354 |
| Debian 公钥 / 包内字节对照 | `musl-key-status-2026-09-10.json` | 3,717 |
| 静态布局 / GNU 版本摘要 | `musl-verifier-layout-summary-2026-09-12.json` | 95,281 |

实际 argv、恢复根 cwd、退出码和输出摘要见[执行记录](musl-retention-execution-2026-09-12.json)；原始 stdout / stderr 与执行 JSON 保留于 `.tmp/musl-retention-2fb2e70-20260912/`。重跑仍使用已安装的宿主 Python，最后一项使用同一已记录 LLVM 静态工具；它不是可在没有任何宿主工具时自行启动的环境。

真实恢复没有删除或改名原缓存，也没有声称对宿主文件系统做访问隔离。恢复方法仅读取对象库；四条重跑的方法和输入路由到恢复树，不配置原缓存兜底。原始缓存不存在时的恢复边界另由合成检查覆盖。这不是 GnuPG 运行或密码学验签，公钥时效仍限于原材料获取时点。

## 宿主只读观察

已读 OrbStack 应用的 Info.plist，并通过现存的 `/Users/luobo/.orbstack/run/docker.sock` 发起一次成功的 `GET /version`。首次沙箱访问被 `PermissionError: [Errno 1] Operation not permitted` 拒绝；获准沙箱外只读重试后返回 HTTP 200。没有使用会自动启动应用的入口、没有启动 daemon / 容器，也没有读取 Docker 凭据、容器环境或业务数据。

[宿主观察记录](musl-verifier-host-2026-09-12.json)保留成功工具输出中选取的版本字段，以及本机文件身份；API 原始响应未单独保存，不能当作完整原始 HTTP 证据：

| 对象 | 实际观察 |
| --- | --- |
| macOS / 架构 | `26.6.2` / `arm64` |
| OrbStack 应用 | `2.2.1`，build `20628` |
| Docker Engine | `29.4.0`，API `1.54`，minimum API `1.40`，commit `daa0cb7f` |
| Linux guest kernel | `7.0.11-orbstack-00360-gc9bc4d96ac70`，Linux arm64 |
| containerd / runc / docker-init | `v2.2.2` / `1.4.2` / `0.19.0` |

Python、curl、Docker 命令入口、LLVM 文件摘要也已重新读取；本机文件身份和 daemon 自报版本不等于其供应来源或安全性验收。尚未读取 `/info` 中的 cgroup / memory / pids 等能力，也未动态验证资源、网络、挂载、seccomp 或 cleanup 行为。因此不能据此宣称受控运行环境已验收。

后续只读运行前置应保存经过字段白名单筛选的响应和可重跑采集入口，不把当前选取字段记录扩大为完整 TCB 库存。若 daemon / kernel / 工具版本变化，重跑身份与相关运行前置，不能自动沿用本次观察。

## 留存责任与下一停止点

本轮落实的是**项目内独立副本和实际恢复路径**。原缓存约 58 MiB 之外，新归档约 28 MiB，恢复验证目录另约 28 MiB；它们仍在同一台机器、同一磁盘故障域中。未设置异盘备份、自动备份任务或远程存储，也没有验证现有 Time Machine / 云盘是否覆盖这些路径。

默认由项目所有者保管项目内归档；后续若指定其他主存储，先核对全量对象、完成从目标介质恢复和四条静态重跑，再调整位置。归档不作为普通 `.tmp` 清理对象；未落实另一份可恢复副本前不删除原始输入。对 `artifacts/` 的通用清理同样必须避开本目录，不能因 Git 忽略就视为可丢弃。

下一步补齐以下事项；备份位置安排与只读资源审阅可以并行，未指定备份介质不阻断后者：

1. 明确异盘备份位置 / 保留责任及目标介质恢复检查；本机恢复成功不代替这项。
2. 补只读资源能力、精确组装文件 / 配置及有限运行的资源、输出、超时和清理方案。
3. 明确接受或拒绝 Debian 官方 HTTPS / WebPKI 作为这次发行版验证工具的初始信任终点；接受公钥身份的历史授权不自动覆盖工具二进制。
4. 组装 rootfs、导入镜像、有限工具执行与正式两角色验签继续分别明确目标、影响并授权，不能由本次复制原文推出运行许可。

## 检查与交接

`check-musl-retention.py` 的 7 项合成检查通过，覆盖源漂移、归档损坏、原缓存不存在时恢复、路径冲突 / 越界、符号链接、拒绝覆盖和额外对象；真实 132 文件恢复及四条静态重跑通过。从原工作区、恢复树分别重新生成 manifest，均与已归档清单逐字节相同。仓库检查通过（1,117 文件），`git diff --check` 通过。

本批没有下载、安装、执行包内程序、创建 rootfs / 镜像、启动服务、推送或修改系统配置。没有新 Rust / CI 或密码学验证。前批提交为 `2fb2e70`；本批归档方法、清单、记录及状态更改尚未提交或推送。原文归档和恢复树已被 Git 忽略，无本批后台进程。`source_acceptance = not-assessed`、active runtime 为 0、产品执行停止线保持原义。
