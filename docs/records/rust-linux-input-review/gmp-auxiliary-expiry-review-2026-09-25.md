# GMP 辅助到期状态修订方案（v2）

日期：2026-09-25（Asia/Shanghai）。基线：`dev` / `6852a43`，ahead 11；启动时上一轮 8 个记录 / 复核文件改动尚未提交，本轮保留。

用途：供维护者审阅首次失败后的辅助状态处理修正、测试与第二次单次运行范围。本文不授权执行、不接受来源，不改写[首次失败](gmp-verification-attempt-2026-09-25.md)或其方法 / 材料。

## 修订内容与边界

首次 `filter` 在 GnuPG 正常退出后，因辅助状态 `KEYEXPIRED 1736961163` 被原白名单拒绝而停止。离线复核确认输入 / 导出 packet 包体一致；此前没有执行自认证检查、分离签名或负例。

[修订入口](run-gmp-verification-v2.py)以 `gmp-auxiliary-expiry-v2` 显式登记新判定版本，保留原执行文件及其传递依赖的字节。直接复用原输入准备、六项 GnuPG 命令、`run_one`、资源限制、ownership 和清理；仅本批编排、辅助状态联合判定及报告版本进入新文件。原入口供历史重放，新运行使用 v2；不是两个可互换的生产入口。

这次修改将**固定到期声明纳入辅助步骤的结构判定**，不改变来源接受规则。`KEYEXPIRED` 本身没有指纹，不能单独据它判定主体或认证有效性；必须先盘点单一固定主钥材料，再与导出包体或完整 colon 输出联合核对。任何联合条件不成立，仍停止。没有在共享 `IMPORT_ALLOWED` 中增加宽泛例外。

| 步骤 | v2 预注册状态序列 | 必须同时满足 |
| --- | --- | --- |
| 导出 `filter` | 恰好两行：`KEYEXPIRED 1736961163`，随后 `IMPORT_RES 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0` | 正常零退出、完整采集；原材料中单一主钥 `343C2FF0FBEE5EC2EDBEF399F3599FF828C67298`、两个固定 SHA-256 自认证及到期时间匹配；导入前后全部主体与两份自认证包体一致 |
| 自认证 `certifications` | 恰好一行 `KEY_CONSIDERED <固定主钥完整指纹> 0`；或在该行之前恰好一行 `KEYEXPIRED 1736961163` | 正常零退出、完整采集；逐主体 colon 检查两份 `sig:!`、算法 / 摘要 / class / 日期 / 指纹 / UID、明确到期状态及主钥 / 子钥各自到期时间；派生公钥与原候选一致 |
| 原包 `verify` | 沿用原 GMP `SIG_ID` / `EXPKEYSIG` / `KEYEXPIRED` / `VALIDSIG` 的固定判定 | 原 signer、RSA / SHA-512、时间、class、唯一签名组、正常零退出等全部条件保持原样 |
| 三个负例 | 沿用指定 signer 的 `BADSIG` 或精确缺钥原因 | 不把 IO、超时、OOM、信号或额外失败当作预期拒绝 |

辅助状态上限进一步限定为 **256 bytes**；逐字节匹配，不接受额外空白、CRLF、重复、乱序、错误指纹 / flags、子钥到期冒充主钥到期、非零异常计数、未知成功 / 失败 / 撤销记录。未识别状态不是被忽略，而是使整步失败。状态正确也不能替代包体对应、自认证检查或签名验证。

导出步骤的结果明确保留 `current_key_state = expired`、`self_certifications_checked = false`、`historical_validity = not-established`、`source_acceptance = not-assessed`。自认证步骤状态流可不另发到期行，但完整 colon 判定仍要求明确的到期状态，不因此忽略到期。实际核验时钟须晚于两个已声明到期时点，不允许假时间参数；宿主 / guest 时间正确仍是可信假设。

自认证步骤尚无 GMP 动态输出。本轮只读核对同一既有工具的 MPFR `certifications.status`，其中只有单行 `KEY_CONSIDERED`；这不证明 GMP 会有同样输出。上表两种自认证序列是预注册的有界候选：固定 GnuPG 若发出其他顺序、额外行或不同 flags，仍保存失败并停止，不扩展白名单或自动重跑。

签署时点仍是 2023 年的受保护声明，主钥到期仍为 2025 年，材料仍是 2026-09-25 有限快照；本轮没有取得更新公钥或撤销材料。第三方 class `0x30` 声明未认证、身份与工具 / 宿主假设、可信时间戳缺口均沿用原方案。到期不是判定历史签名无效的充分条件，导出通过也不能证明历史有效。

## 旧结果与新候选的离线对照

以下入口先调用首次失败复核，校验原 bundle / 结果固定摘要、归档输入及旧方法、10 条命令日志与清理，再只将已留存的导入响应传给新版纯判定函数：

```bash
python3 docs/records/rust-linux-input-review/run-gmp-verification-v2.py --review-retained-filter
```

[本轮机器对照](gmp-auxiliary-expiry-review-2026-09-25.json)记录：旧判定仍复现 `unexpected auxiliary status: KEYEXPIRED`；新候选过滤判定匹配，并显式保留当前到期和自认证未检查状态。`actions_executed = false`、`new_cryptography_executed = false`。它不会改写旧 `result.json`、生成派生 keyring、运行容器或继续到第二步；没有把首次整批失败改标成功。

新执行报告为 `diagnostic-gmp-verification-run-v2`，另含 `assessment_profile`；[新导出 / 重放入口](collect-gmp-verification-v2.py)使用 `diagnostic-gmp-verification-bundle-v2`，拒绝 v1 / 未知版本。旧收集器与旧复核入口不变。新收集器与实际执行共用新版纯判定函数，避免一个入口严格检查辅助状态、另一个入口仍消费旧白名单。

输入、实际方法源码、命令 / stdout / stderr / status、退出 / 限额 / 时间、清理状态均按原方案留存。成功仍须完整重放 45 条命令和六步判定；失败只留存已有材料，不产生成功结论。重放不执行保存的源码或密码学工具；是同一判定器的记录一致性复核，不是独立证明。JSON / 文件数量、流、输入、存储上限沿用原方案。

## 本地检查

[新版检查入口](check-gmp-verification-v2.py)包含 30 项合成检查，覆盖精确辅助状态与全部绑定、主体 / 包体 / 摘要变化、超限 / 退出 / 时钟、未满足条件时禁止落盘、版本隔离、命令参数和资源不漂移、逐步失败停止、六步假工具执行与移除合成原目录后的重放、日志 / 状态 / 方法 / cleanup 篡改、失败导出。测试不运行 GnuPG / Docker；默认计划 CLI 测试只运行宿主 Python。

```bash
python3 docs/records/rust-linux-input-review/check-gmp-verification-v2.py
python3 docs/records/rust-linux-input-review/check-gmp-verification.py
python3 docs/records/rust-linux-input-review/check-gmp-execution-record.py
python3 docs/records/rust-linux-input-review/check-gmp-filter-attempt.py
python3 docs/records/rust-linux-input-review/inspect-gmp-filter-attempt.py
./scripts/check-repo.sh
git diff --check
```

开发中新增测试文件曾出现插入位置导致的缩进错误，以及默认计划比较受合成指纹补丁影响；已修正测试结构和补丁范围，未放宽状态判定。

最终新版 30 项、旧 GMP 37 项、旧导出 13 项及首次失败复核 6 项，共 **86 项通过**；仓库检查通过（1,269 个文件），`git diff --check` 通过。首次失败报告从恢复 bundle 重算后逐字节一致，旧方法身份仍匹配；本轮候选对照导出重复生成也逐字节一致。没有重跑无改动的 MPFR / musl 全部测试、Rust / CI 或产品构建。`attempt2` 目录尚未创建；本轮 5 个新文件与两个入口文档更新，加上上一轮记录合计 13 个工作区文件改动，均未暂存、未提交；`dev` 仍 ahead 11，未推送。

## 第二次运行的精确待授权范围

只请求以下命令**运行一次**，任何步骤失败即停；不自动从第二步续跑，不复用第一次的临时钥环或输出目录：

```bash
python3 docs/records/rust-linux-input-review/run-gmp-verification-v2.py --execute-authorized
```

- 输入：原 GMP 固定留存库、原包与签名、原强摘要候选、同一错误主钥及空 keyring；不下载或刷新任何材料，不执行上游程序。
- 工具：既有 image `sha256:55063921d0e996f717092e07dce8041cb2376cc171a070bf9a0a38a5dd16c777`、GnuPG 2.4.7；CLI `/usr/local/bin/docker`，socket `/Users/luobo/.orbstack/run/docker.sock`；daemon 29.4.0 / API 1.54。原 CLI、rootfs plan / tar、image 及资源能力核对不变。无 pull / import / 安装，不启动 OrbStack 应用。
- 副作用：独占新建 `/Users/luobo/Code/RadishAxiom/.tmp/gmp-verification-20260925-attempt2`（`0700`），保存输入、原方法快照、派生公钥、全部日志与报告。最多 9 个只读输入，每文件 2 MiB / 合计 5 MiB；唯一可写宿主 bind 为该步 status 文件。
- 至多六个串行短命容器：无网络、只读根、uid / gid 1000、drop ALL、no-new-privileges、1 CPU、128 MiB memory / swap 同限、32 PID；每次两个 16 MiB tmpfs。stdout / stderr / status 各 1 MiB，GnuPG 每次 30 秒、控制命令每次 10 秒。
- 预计 2–6 分钟；整批预算 600 秒并保留 150 秒停止 / 清理余量。超时先终止，只删除完整 ID 和 ownership 已核对的本批容器；不确认清理则报告精确 ID / 名称，不声明已清理。
- 原目录、第一次失败 bundle、持久归档、镜像与 rootfs 均保留。无安装或系统修改，不需要对应回滚；新增磁盘材料保留，后续清理再限定精确目标。

若获得执行授权，随后在本地导出、重放并将真实材料转入新持久留存目录；不会借此授权新增下载、来源接受、安装、提交或推送：

```bash
python3 docs/records/rust-linux-input-review/collect-gmp-verification-v2.py \
  --output .tmp/gmp-verification-execution-20260925-attempt2.json
# 使用实际导出并另行留存的摘要；占位不是已有结果。
python3 docs/records/rust-linux-input-review/collect-gmp-verification-v2.py \
  --replay .tmp/gmp-verification-execution-20260925-attempt2.json --sha256 REVIEWED_BUNDLE_SHA256
```

本轮“继续推进下一步”用于完成本地修订、测试与可审阅范围；首次单次执行授权已经消耗，没有自动覆盖这次不同判定 / 新目录的运行。按当前任务授权边界和 [Agent 执行规则](../../governance/agent-collaboration.md#授权进程与环境)，第二次真实运行须取得上述范围的明确授权。

GMP 仍未完成自认证 / 原包验签或来源接受；GCC / Binutils 继续阻断完整 source lock 和安装，headers 仍未认证来源。本轮未新增下载、真实验签、容器、安装、提交或推送。
