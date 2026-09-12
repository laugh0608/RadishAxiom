# musl 验证环境首次真实诊断与清理结果

日期：2026-09-12；基线 `dev` / `dbab49c`。面向下一步 musl 来源验签的实施者，记录已授权诊断的原始结果、失败修复及当前保留状态；不构成来源 acceptance、密码学验签或 production qualification。

## 已确认的范围与结果

项目所有者在审阅[精确执行与工具信任方案](musl-verifier-smoke-entry-2026-09-12.md#下一次确认的精确范围)后回复“确认”。本次接受固定 Debian 工具包字节及发行版构建、当前 macOS / OrbStack / Docker / Linux / runc 为这四项诊断的可信输入；授权仅覆盖固定 tar 导入、四项只读诊断及精确容器清理、保留镜像和日志。该确认不自动接受未来其他工具版本、宿主或任务，也不把可信输入升级为独立证明。

共发出 **一次镜像导入、四次容器启动与四次成功删除**。四项实际运行全部退出 0，stderr 为空、无 OOM / 超时 / 输出超限，启动前后配置检查通过。四项运行整体区间为北京时间 **2026-09-12 21:39:48.960521–21:39:50.286119**；前置诊断和修复用时另计，不把约 1.33 秒写成整轮任务耗时。

| 项目 | 实际观察 | 附着命令耗时 |
| --- | --- | --- |
| gpg 版本 | GnuPG `2.4.7`，libgcrypt `1.11.0`，Home `/work/full` | 约 0.133 秒 |
| gpgconf 目录 | `homedir` 与 `socketdir` 均为 `/work/full` | 约 0.085 秒 |
| gpg loader | 12 项文件映射均可在既定 rootfs 中解析，另有 vDSO | 约 0.084 秒 |
| gpgconf loader | 4 项文件映射均可在既定 rootfs 中解析，另有 vDSO | 约 0.097 秒 |

这些耗时包含宿主 Docker CLI 附着交互，不是程序纯计算基准。gpgconf 输出还声明了本切片未包含的辅助程序 / 数据目录；本批没有启动这些程序。未进行公钥导入、验签、密码学负例或实际资源耗尽测试。

## 失败、修复与方法留存

全部步骤先停止于首个异常，再依据原始日志复核根因。修复仅改变 Docker 字段读取的表示映射，未更改 tar、程序命令、UID/GID、网络、挂载或资源限额；每次恢复均使用新日志目录，未覆盖失败记录。

| 日志目录（任务目录内） | 结果与范围 |
| --- | --- |
| `import/` | 沙箱拒绝连接 socket；仅版本查询，未发出导入请求 |
| `import-attempt-2/` | 获准沙箱外执行；CLI 模板误用 `.Server.ApiVersion`，仅版本查询失败 |
| `import-attempt-3/` | 版本查询通过；资源模板误用 `.CpuCfsPeriod`，未发出导入请求 |
| `import-attempt-4/` | 查询通过并成功导入唯一镜像；后续 inspect 遇到省略的可选 `Config.Env` 字段失败 |
| `run/` | 复用已有镜像；已修复可选字段读取，但把省略的 image `Config.User` 当作必须存在的空字符串，未创建容器 |
| `run-attempt-2/` | 识别未设置的镜像 User，容器仍显式 `1000:1000`；四项运行及清理全部通过 |

Docker 的 Go 模板字段与 JSON tag 并不总是同名：`APIVersion` 与 `ApiVersion`、`CPUCfsPeriod / CPUCfsQuota` 与 `CpuCfsPeriod / CpuCfsQuota` 分别对应。依据为 [Docker CLI version 类型](https://github.com/docker/cli/blob/master/cli/command/system/version.go)与 [Moby Info 类型](https://github.com/moby/moby/blob/master/api/types/system/info.go)，网页用于解释字段差异，实际生效情况以留存的本机 CLI 输出为准。

inspect 使用 JSON map，未设置的可选键可能省略。入口改用明确 map lookup；必须字段仍逐项检查。image User 的 null / 空字符串都表示未声明 User，本批实际容器 User 继续严格要求 `1000:1000`，不接受其他声明值；没有把未知资源支持当作默认成功。

原失败结果中的 `image_state = unconfirmed` 是入口的概括性错误字段；前三个目录的完整命令序列证明仅发出了只读查询，不能据此虚构曾导入未知镜像。第四个目录保存的 import 结果整体仍为失败，不能改写为通过；其已知 image ID 后来在成功运行的前置 inspect 中得到复核。

四份历史方法原文作为证据保存，不是新的执行入口：

- [初始方法](musl-smoke-method-initial-2026-09-12.py)，SHA-256 `f33d178cb9f6ddb9c4ce24f97608d1f7a9ae1202c7c7ac9d7a620924c27d8cb0`；
- [仅修复版本字段的方法](musl-smoke-method-version-fix-2026-09-12.py)，`8a0bad11100adb7ed21c822ef97b61e30bc0c23baa1a32a0fa3f7c91279c72e3`；
- [补齐 CPU 字段的方法](musl-smoke-method-info-fix-2026-09-12.py)，`3aacd11c6af3058f70c356da557805096b9e5ae41861a3f0365c78d94d4a6580`；
- [修复可选字段 map 读取的方法](musl-smoke-method-map-fix-2026-09-12.py)，`28e1dad71330156ab75b2d99810a71773a7980db79a83f68ff2b59e5abe85344`。

最终[执行入口](run-musl-verifier-smoke.py)为 23,815 bytes，SHA-256 `4b0151dfbe00b7772697c06afb447521e0cf66fe2011ca1e4adb84f4029c016c`。新增四项回归检查，现共 **27 项合成检查通过**。此前合成测试遗漏 CLI 模板与实际 JSON 省略行为，是这次暴露的覆盖缺口；真实执行通过不能消除前面发生过的失败。

## 产物、容器清理与复核入口

镜像完整 ID 为 `sha256:55063921d0e996f717092e07dce8041cb2376cc171a070bf9a0a38a5dd16c777`，保留在已存在的 OrbStack Docker daemon 中，没有写 tag 或发布。输入仍是项目内 `.tmp/musl-preflight-80768b6-20260912/rootfs.tar`，8,407,040 bytes，SHA-256 `f1ac49bc29d33182a9c9a070b70509c739d857369876afbe307b9e9898d6b8b3`；物理镜像存储占用没有另行测量，不能按 tar 大小推断。

本批 run ID 为 `8d8fa8641e60410899240a97fac54f14`。四个完整 container ID 及删除前退出状态见[原始执行汇总](musl-verifier-smoke-execution-2026-09-12.json)。四条 remove 均退出 0 且 stdout 返回对应完整 ID；没有本批容器保留。没有修改宿主 PATH、全局库、GnuPG home、证书或系统配置，没有向宿主展开 rootfs；既有 daemon 本地镜像状态已按授权改变。

原始编号日志与空 Docker 配置目录保留在 `.tmp/musl-smoke-dbab49c-20260912/`，绝对前缀为 `/Users/luobo/Code/RadishAxiom/`。失败与成功共 **42 条命令记录**，stdout / stderr 与原摘要逐项匹配；汇总同时保留原结果、原命令、方法身份和白名单 inspect 内容。[汇总方法](collect-musl-smoke-execution.py)只读取这个固定批次，可离线重建 Git 中的 JSON：

```bash
python3 docs/records/rust-linux-input-review/collect-musl-smoke-execution.py
```

归档输入、真实 tar 和历史方法都保留；本轮未清理来源缓存或旧日志。没有新下载、依赖安装、Rust / CI、push 或其他远端写入。`./scripts/check-repo.sh` 通过（1,135 个文件），`git diff --check` 通过，执行汇总离线重建逐字节一致；本轮新增内容和前批未提交的入口改动仍未提交，`dev` 相对本地 `origin/dev` 领先 6 个提交。

## 当前结论与下一步

已取得这台主机、这些固定输入和配置下的四项动态观察，并实际检查了配置与正常退出清理。超时、OOM、输出耗尽、daemon 失联和恶意程序的真实隔离行为未动态验证；这些路径目前只有合成检查，`runtime_qualification = false`。当前工具信任是项目所有者明确接受的诊断假设；`source_acceptance = not-assessed` 不变。

下一步准备同一 musl 原包的正式验证切片：复用现有镜像与已归档公钥 / InRelease / Sources，先确定有界可写 home 的初始化、输入传递和清理，再实现两角色验签状态解析及失败传播。现有只读 home 不可直接用于公钥导入；真实导入公钥和验签属于新的有限执行范围，按具体方案另行确认，不重复导入当前镜像或下载已有材料。
