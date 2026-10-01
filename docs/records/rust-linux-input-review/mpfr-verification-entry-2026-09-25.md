# MPFR 当前主钥离线验签切片（2026-09-25）

用途：向维护者交接已实现的方法、合成检查和真实执行结果。不包含 MPFR 来源接受、许可证接受、安装或产品 qualification。前文保留准备阶段的事实与授权边界，本次已授权运行见文末。

## 本批结果与输入

基线为 `dev` / `a222b03`，初始工作区干净，与本地 `origin/dev` 引用一致，未刷新远端。项目所有者确认开始推进 MPFR 验签切片；本批先完成本地方法和合成验证，没有继承历史 Docker / GnuPG 执行授权。

[输入准备入口](prepare-mpfr-verification.py)逐字节读回两个已固定 manifest 下的全部对象：原包批 28 个路径 / 21 个对象、公钥批 43 个路径 / 31 个对象，共 71 个路径条目 / 52 个对象。两份 manifest 同时匹配项目内审阅原文与固定 SHA-256。全部长度与摘要匹配；读取来自独立本机归档，不依赖原始下载缓存，不代表异盘备份已验收。

[本批输入导出](mpfr-verification-inputs-2026-09-25.json)可由入口直接重算：MPFR `4.2.2` 原包为 1,505,596 bytes，SHA-256 `b67ba0383ef7e8a8563734e2e889ef5ec3c3b898a01d00fa0a6869ad81c6ce01`；签名 228 bytes，完整原始公钥 15,034 bytes。它们仍是 2026-09-16 留存材料，不是 9 月 25 日重新取得的最新钥匙状态。

完整 armor 保留新旧两个主钥；选定主钥 `A534BE3F83E241D918280AEB5831D11A0D4DB02A` 的原始块为 1,088 bytes，SHA-256 `8d342ce1048e4169a957505be1d62a942ba23329be936e5058f89b7beff131cd`。三个 UID 各有一份当前 EdDSA 主钥的 SHA-256 自认证，一份 ECDH 加密子钥有 SHA-256 binding；原包声明为当前主钥直接签名，不将加密子钥当成 signer，也不声称检查了签名子钥的 back-signature。

**该选定块另含三份旧 DSA 钥的 SHA-1 UID 认证。** 新方法逐项盘点、保留原文并将其排除于本轮认证依据；不启用弱摘要兼容选项，不核验或接受它们，不从它们推导新旧钥之间的身份连续性。旧 musl 单 UID / 两角色严格判定器及历史方法字节没有修改。MPFR 身份与来源接受仍待真实结果后的独立审阅。

错误主钥负例采用已有归档中的固定 Debian release 公钥（962 bytes），准备时通过既有输入方法读回并确认不含 MPFR 主钥。它仅用来触发指定 MPFR signer 缺失，不将 musl 或 Debian 的验收结论转移给 MPFR。空 keyring 是另一个独立缺失主钥负例。

本批还只读核对了既有 Docker CLI 文件、socket 类型、rootfs plan 和 tar：rootfs 8,407,040 bytes，匹配 `f1ac49bc29d33182a9c9a070b70509c739d857369876afbe307b9e9898d6b8b3`。没有连接 daemon；当前 daemon / image 状态须在获授权执行时重新检查。

## 判定方法与六次调用

[材料和结果判定](inspect-mpfr-verification.py)复用已有有界 packet / subpacket reader，但以 MPFR 的固定主钥、子钥、三个 UID 和四份自认证建立独立 profile。该 Python 方法不进行密码学验证，也不是公共 OpenPGP API。

原始与 `import-export,self-sigs-only` 输出按 key / UID 原始字节，以及绑定到具体 UID 或子钥的自认证正文多重集比较。允许 GnuPG 调整 UID 顺序，拒绝丢失、更改、重复或移置自认证。colon 判定逐项核对 UID 解码后的字节、指纹、算法、日期、自签名 `!` 状态、class 和 SHA-256；仅比较数量不足以通过。未知记录、撤销、到期、禁用或超出固定 profile 的材料均停止。

colon 字段与 status 语义依据 [GnuPG 2.4.7 DETAILS](https://raw.githubusercontent.com/gpg/gnupg/gnupg-2.4.7/doc/DETAILS)；导入和自认证操作沿用[既有验签入口审阅](musl-verification-entry-2026-09-16.md)中的精确工具及选项依据。最终分离签名要求唯一签名组，主钥 / signer、签名日期、version 4、算法 22、digest 8、class `00` 全部匹配；拒绝额外失败状态和多签名。状态匹配只消费固定工具的报告，不构成独立密码学证明。

| 顺位 | 调用 | 判定 |
| --- | --- | --- |
| 1 | 当前主钥原始块 self-only 导出 | 所有当前自认证及其主体保留，三份旧钥认证不进入派生 keyring |
| 2 | 派生 keyring 的 `--check-sigs` | 三个 UID 自认证及一个加密子钥 binding 逐项通过 |
| 3 | 固定原包与分离签名 | 零退出、唯一正确的 `GOODSIG` / `VALIDSIG` / `SIG_ID`，stdout 为空 |
| 4 | 仅翻转原包中间一个字节后验签 | 正常非零退出、指定 signer 的 `BADSIG` |
| 5 | 仅使用固定错误主钥验原签名 | 正常非零退出、指定 signer 的 `ERRSIG` 缺钥原因及 `NO_PUBKEY` |
| 6 | 空 keyring 验原签名 | 同上，不能用无关 IO 错误或超时替代 |

所有负例拒绝 `GOODSIG` / `VALIDSIG`、无关失败、异常退出与采集失败。只有六项及清理均符合预期，整批才可能通过；即使通过仍输出 `source_acceptance = not-assessed`、`runtime_qualification = false`。未知真实输出先保存失败再审阅，不自动重试或放宽白名单。

## 执行面与清理

[执行入口](run-mpfr-verification.py)默认只打印计划，不创建目录或连接 Docker。采集器、容器参数、mount 校验、ownership 和 cleanup 复用现有 musl 方法。MPFR 原包超过原 musl 调用的 1 MiB 输入上限，因此本切片单独保留有界调用编排：只读输入上限为每文件 2 MiB、目录合计 4 MiB、最多 8 个文件；没有改写已绑定摘要的历史方法。stdout、stderr、status 的限制仍各为 1 MiB。

- 固定 image ID：`sha256:55063921d0e996f717092e07dce8041cb2376cc171a070bf9a0a38a5dd16c777`；CLI：`/usr/local/bin/docker`；socket：`/Users/luobo/.orbstack/run/docker.sock`。只使用已有环境，不 import / pull 镜像、不启动 OrbStack 应用；CLI、daemon 版本或资源能力漂移就停止。
- 最多六个串行短命容器；无网络、只读根、uid / gid 1000、drop ALL、no-new-privileges、1 CPU、128 MiB memory / swap 同限、32 PID、无日志驱动、无重启。诊断容器限额不是产品隔离验收。
- 每次全新 `/work/full` 与 `/tmp`，各为 16 MiB tmpfs；输入只读挂载。唯一宿主可写 bind 是该次 status 文件，位于新建 `0700` 任务目录，调用期间 `0666`，结束后 `0600`。不挂载宿主钥匙环，不使用 ownertrust，不联网取钥、不倒拨时钟。
- 每次 GnuPG 30 秒，控制命令 10 秒；整批启动预算 600 秒，保留 150 秒核对与清理余量。预计 2–6 分钟，发生失败即停。预算不是 daemon 或宿主文件系统失联时的硬实时保证。
- 独占新建 `/Users/luobo/Code/RadishAxiom/.tmp/mpfr-verification-20260925`，已有同名目录就拒绝；保留公开输入、派生公钥、编号 stdout / stderr / status、方法身份、输入摘要、真实退出码和 `result.json`。命令、文件与流上限估计总材料低于 128 MiB，不代表设置了宿主目录配额。
- 仅删除已确认完整 ID 且 ownership 匹配的本批容器；超时先终止，清理未确认则失败并报告精确 ID / 名称。保留既有镜像、rootfs、归档、日志和输入，不删除其他容器。无需回滚安装或系统设置，因为本切片不执行这些动作。

执行命令（**待本次明确授权，尚未运行**）：

```bash
python3 docs/records/rust-linux-input-review/run-mpfr-verification.py --execute-authorized
```

标志只记录授权，不自行授予权限。依据[当前停止线](../../status/current.md#当前停止线与待决策)和[协作规则](../../governance/agent-collaboration.md#授权进程与环境)，真实执行需要本次精确范围授权；此前“开始”用于完成本批本地方法与检查，没有自动覆盖未说明的容器执行范围。

## 准备阶段验证与未验收项

新入口 38 项合成检查通过；既有调用编排 38 项、采集 / 生命周期 27 项回归通过，共 **103 项**。新测试全部使用合成公钥、签名状态、临时输入或假 daemon；继承采集器测试运行的是宿主 Python 合成子进程。没有生成真实签名或运行 GnuPG。

首轮新增 34 项中有 1 项失败：合成 colon 样本将能力字段放在第 11 列，而实际规范为第 12 列，导致“禁用钥”变异未命中判定字段。修正样本分隔符后通过；另补充 ownership、日志写入失败、累计输入限额与动态加载方法身份检查，形成最终 38 项。没有修改禁用钥拒绝逻辑来迎合测试。

```bash
python3 docs/records/rust-linux-input-review/prepare-mpfr-verification.py
python3 docs/records/rust-linux-input-review/run-mpfr-verification.py
python3 docs/records/rust-linux-input-review/check-mpfr-verification.py
python3 docs/records/rust-linux-input-review/check-musl-verification-execution.py
python3 docs/records/rust-linux-input-review/check-musl-smoke.py
./scripts/check-repo.sh
git diff --check
```

输入导出与重新生成结果逐字节一致；正文负例与原包等长且恰好相差一个字节；默认计划预览通过。`./scripts/check-repo.sh` 通过（1,180 个文件），`git diff --check` 通过。不新增默认 CI 门禁；真实 GnuPG、多 UID 导入行为、容器挂载与资源限制尚待动态验证。未重跑 Rust / CI、产品构建、来源接受或安装，没有新下载、提交、push、后台服务或本批容器。

本批 6 个新文件与 4 个文档更新留在工作区，未暂存、未提交；其中两份历史记录只修复指向当前顺位的锚点，不改批次事实。测试临时目录由测试自行清理，Python import 缓存处于既有忽略规则内；真实执行目录尚未创建。

## 本次授权与真实执行结果

项目所有者随后要求“提交工作区更改，授权该方案”。先将上述 10 个文件精确暂存并提交为 `9fd5893`（`chore(runtime): 准备 MPFR 有界离线验签切片`）；提交后工作区干净，相对本地 `origin/dev` ahead 1，未 push。随后按上文原命令、原镜像与原目录执行一次，没有重试、修改方法、放宽检查或变更资源范围。

执行时间为 **2026-09-25 13:40:00.956–13:40:04.684（Asia/Shanghai）**，实际约 3.73 秒，入口退出 **0**。六项均符合原预期：

| 步骤 | GnuPG 退出码 | 实际结果 |
| --- | --- | --- |
| self-only 导出 | 0 | 派生公钥 803 bytes；三 UID、加密子钥和四份原始自认证保持对应，三份旧钥认证被排除 |
| 自认证检查 | 0 | 三份 UID class `13` 与子钥 class `18` 均为 `sig:!`，算法 22 / digest 8、上下文与日期匹配 |
| 固定原包 | 0 | 唯一指定主钥 `GOODSIG` / `VALIDSIG`，EdDSA / SHA-256、class `00`，签名时间与原始 packet 声明匹配 |
| 正文单字节篡改 | 1 | 指定 signer 的 `BADSIG`，没有成功状态 |
| 错误主钥 | 2 | 指定 signer 的 `ERRSIG` 原因 9 与 `NO_PUBKEY` |
| 缺失主钥 | 2 | 同上；没有将 IO、超时或资源失败当成预期拒绝 |

派生公钥 SHA-256 为 `3fe00f68bbf3888ae185b950d4db0f708dd01b6159cb03dec77296f9045b6372`。全部六个容器正常结束、未 OOM，逐项 ownership 复核后删除；六次 `container rm` 退出 0。没有遗留本批容器、后台进程或新增镜像。已有镜像、rootfs、输入归档以及本次任务目录的日志与公开材料保留。

固定 CLI、daemon 版本 / 能力、image、逐次 mount / 隔离参数及前后输入身份检查通过。本次只观察了这些参数与正常 / 错误签名路径，没有进行内存耗尽、宿主失联或异常 teardown 压力实验，不扩展为产品隔离或 qualification 声明。

### 结果留存与离线重放

[导出方法](collect-mpfr-verification-execution.py)绑定本次 `result.json` 的 37,352 bytes / SHA-256 `601bd0d92811382c378eb6e3c8f51c05c93d90aa0636ce79b69332b161b2d129`，核对全部 20 个执行方法身份、固定输入归档和 **45 条命令日志**。[执行导出](mpfr-verification-execution-2026-09-25.json)包含原始报告、所有命令的 stdout / stderr、六份 status 及重算判定；二进制 stdout 使用 base64 无损保存，不用文本解码丢弃字节。

离线重放消费固定命令响应，重新检查 preflight、image、逐项 command / capture limit、容器前后状态及 cleanup，再重算原始 / 派生自认证关系和六项结果。该重放不连接 Docker、不运行 GnuPG、不再次写入派生输入；复用同一判定逻辑，因此是记录一致性复核，不是第二套独立密码学证明。复算仍需仓库方法、已留存输入归档和本机任务目录；导出保留核心运行日志，但不是完整环境备份或异盘恢复声明。

新增 [7 项合成导出检查](check-mpfr-execution-record.py)通过，覆盖命令目标 / 顺序、socket / config、采集限额、日志耗尽、失败保留和二进制 / Unicode 往返。执行方法没有变化，准备阶段 103 项检查作为此前证据保留，本轮未重复运行它们。

执行导出重新生成后逐字节一致：303,335 bytes，SHA-256 `014b34ef48dc1607e7a80f742b4c6e2bc9b93f64d82ccb28b43e6baaa12fa037`。本轮仓库检查通过（1,183 个文件），`git diff --check` 通过。

```bash
python3 docs/records/rust-linux-input-review/collect-mpfr-verification-execution.py
python3 docs/records/rust-linux-input-review/check-mpfr-execution-record.py
./scripts/check-repo.sh
git diff --check
```

### 剩余信任与下一步

正例保留 `TRUST_UNDEFINED 0 pgp` 与 GnuPG 关于尚未认证钥匙所有者的提示。它不否定此次数学验签结果，也不证明公钥属于所声明维护者；没有使用 ownertrust、第三方弱认证或默认信任来消除提示。固定 GnuPG、Python、宿主、Docker / OrbStack 和此前身份页面仍分别承担已有信任角色。公钥材料时点为 2026-09-16，未获取所有渠道的最新撤销状态。

因此本次保持 `source_acceptance = not-assessed`、`runtime_qualification = false`。下一步审阅固定 MPFR 原包的身份依据、工具 / 宿主信任及来源接受范围；许可证审阅、构建关联、安装、激活仍分别验收与授权。此次未执行 MPC、下载、安装、产品构建、Rust / CI 或远程写入。后续新增导出方法、结果与状态更新留在工作区，未再次提交。

本次执行记录随后提交为 `8d803cb`；[来源接受审阅](mpfr-source-acceptance-review-2026-09-25.md)已完成，项目所有者随后确认完整限定声明，该精确原包限定来源接受通过。该后续决定不修改本文诊断结果或原始 JSON。
