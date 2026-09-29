# GMP v3 执行编排与第三次诊断准备

日期：2026-09-29（Asia/Shanghai）；基线 `dev` / `f3811cb`。

用途：向维护者交接 v3 六步编排、合成回归及一次新诊断的精确待授权范围。不包含第三次真实执行、密码学新结果、来源接受或产品 qualification。

## 已完成的本地切片

项目所有者要求“提交工作区更改，继续推进下一步”。前轮 16 个文件已精确提交为 `f3811cb`（`chore(runtime): 核实 GMP 工具语义并准备 v3 离线判定`）；提交后工作区干净，`dev` 相对本地 `origin/dev` ahead 1，未刷新远端、未推送。

[新版执行入口](run-gmp-verification-v3.py)使用 `gmp-certification-expiry-v3`，将[已审阅候选](inspect-gmp-certification-v3.py)接入自认证步骤；子判定仍报告其原 `gmp-certification-expiry-v3-offline-candidate` 身份。解析器始终不执行密码学。仅以后真实 GnuPG 调用成功时，执行层才记录工具操作；这两层字段不能混用。

过滤与四项分离签名调用直接复用 v2 判定，六项命令、资源限制、输入准备和 v1 容器生命周期不变。自认证同时核对固定四行 status、原始及派生公钥、两份强摘要自认证与 colon 输出，分别保留包内声明到期和工具有效到期；不会改写原包或删除重复通知。

旧 v1 / v2、历史复核器及候选已进入摘要绑定留存，故以新版本编排 / 导出文件承接；没有改动旧方法，也没有在运行时改写旧模块全局变量来复用旧判定。新版导出器保留 v2 审阅过的流程，并独立标识 `diagnostic-gmp-verification-bundle-v3`，拒绝 v1 / v2 bundle。

执行前绑定并留存 33 个方法 / 依据文件，包括传递依赖、候选、v3 导出器及源码盘点压缩材料；盘点 SHA-256 必须为 `4353f860d766b28fc353020672a40c6869df4a4142d48b837eef57e189ca3cf9`。结束时重读输入与方法，变化即失败。默认命令只输出[机器计划](gmp-verification-v3-plan-2026-09-29.json)，没有 Docker 调用。

[v3 导出与重放](collect-gmp-verification-v3.py)对成功记录消费恰好 45 条命令日志，重核命令、限额、容器前后状态、清理、时间对应、输入、六项判定和信任字段。失败记录保留实际部分日志及失败原因，显式为 `failed-run-retained` / `replayed_success = false` / `failure_logs_replayed = false`；不把保存失败日志称为完整重放。即使失败，仍检查方法、源码依据与信任字段。

## 验证与限制

[新版检查](check-gmp-verification-v3.py)共 15 项，覆盖实际 `execute` 编排与容器生命周期的合成调用、六步成功后导出 / 删除原目录再重放、第三条额外到期通知导致第二步失败停止、超时终止清理、清理失败、输入 / 方法漂移、目录不可覆盖、旧版本拒绝，以及命令 / 限额 / status / colon / 清理 / 时间 / 信任 / 方法 / 依据篡改。篡改输出并同步重算所有相关摘要仍被联合判定拒绝，不能只凭日志内部摘要一致通过。

首轮合成测试 8 项失败：测试替换了 rootfs 摘要，却未同步合成镜像 / 容器 fixture 的来源 label，真实配置门禁在任何步骤前正确拒绝。仅修正 fixture 的合成身份对应，未放宽生产门禁。修正后 13 项通过；再补一致重算摘要的输出篡改与目录复用拒绝两项，最终 15 项通过。

既有 GMP 37 项、v2 30 项、历史失败 6 + 7 项、候选 10 项、源码检查 8 项，共 98 项亦通过；本轮合计 **113 项**。以下纯本地报告重算均逐字节一致：

- `gmp-verification-attempt-2026-09-25.json`：第一次失败及 10 条日志；
- `gmp-verification-attempt2-2026-09-25.json`：第二次失败及 17 条日志；
- `gmp-certification-v3-review-2026-09-29.json`：旧输出与候选的离线比较。

固定 GMP 留存输入离线准备成功，初始 8 项合计 4,248,643 bytes；没有写入真实第三次执行目录。机器计划重算一致；仓库级检查和 `git diff --check` 通过。未运行 Docker / GnuPG、Rust / CI 或产品构建；合成成功不预测真实六步会成功。

原包验签与三个负例仍无实际结果。`source_acceptance = not-assessed`、`historical_validity = not-established`，最新性 / 全渠道撤销未闭合。固定 Debian 工具、源码到 binary 的关联、宿主 / 时间仍可信；源码审阅与日志重放不是独立密码学证明。GCC / Binutils 与 headers 的既有来源缺口保持不变。

## 第三次诊断的精确待授权范围

仅在项目所有者确认本节后，使用默认目录运行以下命令**一次**；失败即停，不续跑、不自动重试：

```bash
python3 docs/records/rust-linux-input-review/run-gmp-verification-v3.py --execute-authorized
```

- 固定输入为现有 GMP 原包、分离签名、公钥有限快照、强摘要投影、同一错误主钥、空 keyring 与单字节改动正文。不新增获取、刷新材料、执行上游源码、放宽弱摘要或回拨时钟。
- 使用已有 image `sha256:55063921d0e996f717092e07dce8041cb2376cc171a070bf9a0a38a5dd16c777` / GnuPG 2.4.7；rootfs SHA-256 `f1ac49bc29d33182a9c9a070b70509c739d857369876afbe307b9e9898d6b8b3`。CLI `/usr/local/bin/docker`，摘要 `c93921f27c941f7661e5478e8af4042e546b66e69707a2b43f31a86cfe9c85d2`；socket `/Users/luobo/.orbstack/run/docker.sock`；daemon 29.4.0 / API 1.54、Linux arm64。执行前重核工具、rootfs plan / tar、image 及资源能力；漂移即停止。无 pull、import、依赖安装或启动 OrbStack 应用。
- 副作用：独占新建 `/Users/luobo/Code/RadishAxiom/.tmp/gmp-verification-20260929-attempt3`（`0700`），保存输入、原方法与依据快照、派生公钥、命令 / 输出 / status 日志和报告。最多 9 个 `0444` 输入，每项 2 MiB、合计 5 MiB。唯一可写宿主 bind 是当步 status 文件，执行中 `0666`、结束后 `0600`。
- 至多六个串行短命容器：过滤、自认证、原包验签、篡改正文、错误主钥、缺失主钥。无网络、只读根、uid / gid 1000、drop ALL、no-new-privileges、1 CPU、128 MiB memory / swap 同限、32 PID、无重启 / 日志驱动，每次两个 16 MiB tmpfs。stdout / stderr / status 各 1 MiB，控制流每项 256 KiB。
- 预计 2–6 分钟；GnuPG 每次 30 秒、控制命令每次 10 秒，整批启动预算 600 秒并留 150 秒停止 / 清理余量。该预算不是 daemon / 宿主失联时的硬实时保证。超时先请求终止，清理不确认则报告具体 ID / 名称并停止。
- 只删除已确认完整 ID 且 image / label / 名称 ownership 一致的本批容器。保留已有镜像、rootfs、旧失败目录与归档。无系统 / 安装变更，无对应回滚；新增材料保留在精确本机目录，后续删除再限定目标。

真实诊断后，在本地导出、重放，并使用既有留存器将结果 / 方法 / 日志归入新的 `artifacts/source-inputs/gmp-verification-f3811cb-20260929-attempt3`，恢复到新的 `.tmp/gmp-verification-v3-restore-20260929` 核对；不宣称异盘备份。目录均须新建，不覆盖既有材料。导出命令为：

```bash
python3 docs/records/rust-linux-input-review/collect-gmp-verification-v3.py \
  --output .tmp/gmp-verification-execution-20260929-attempt3.json
# 仅在真实导出后，使用另行审阅 / 留存的实际摘要；占位不是已有结果。
python3 docs/records/rust-linux-input-review/collect-gmp-verification-v3.py \
  --replay .tmp/gmp-verification-execution-20260929-attempt3.json --sha256 REVIEWED_BUNDLE_SHA256
```

本轮只完成本地编排与可审阅方案。按 [AGENTS.md](../../../AGENTS.md)“授权只覆盖已经说明的动作、目标和影响”，前轮四项获取及历史两次运行授权均不覆盖上述新判定、新目录的第三次诊断；仍需确认本节范围。授权也不包含来源接受、安装、推送或发布。

## 工作区交接

`f3811cb` 已提交未推送；本轮新增三个 Python 文件、机器计划与本文，并更新当前状态和本目录索引，共 7 个文件，尚未提交。无新增后台进程、真实诊断目录或容器；测试临时目录已自动清理，前轮忽略目录中的留存材料保留。
