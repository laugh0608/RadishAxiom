# GMP 6.3.0 受限离线验签方案与入口

日期：2026-09-25（Asia/Shanghai）。基线：`dev` / `619d90c`，启动工作区干净，相对本地 `origin/dev` ahead 10；未刷新远端。

用途：供维护者审阅 GMP 固定材料的诊断范围、实现、合成验证及下一次执行授权。不包含真实验签结果、来源接受、安装或产品 qualification；不改写[原材料批次](gmp-inputs-2026-09-25.md)、MPFR 或 musl 的历史方法。

## 当前结果与时间含义

本批完成本地准备、判定、六次受限调用入口、结果留存 / 重放及合成检查。**未运行 GnuPG、Docker 或新下载；没有 GMP 来源接受。** 默认入口只输出计划，不创建执行目录、不连接 daemon。后文的预期输出不能写成真实观察。

| 时点 | 固定声明 / 将来观察 | 可以说明与不能说明 |
| --- | --- | --- |
| 主钥创建 | `2013-01-07T19:26:27Z`（epoch `1357586787`） | v4 公钥包声明，完整指纹绑定公钥字节 |
| 最新 UID 自认证 | epoch `1579281163`；RSA / SHA-256 | 候选有效期来自此份自认证，须由固定工具核实其签名；不能只凭字段相信 |
| 原包签署 | `2023-07-30T12:18:33Z`（epoch `1690719513`）；RSA / SHA-512 | 签名中受保护的签署时间声明；即使签名通过，也不是独立可信时间戳，不能排除事后回填时间 |
| 主钥到期 | `2025-01-15T17:12:43Z`（epoch `1736961163`） | 原包声明时间落在所选自认证创建之后、主钥到期之前；当前到期本身不证明 2023 年签名无效，也不证明当时未失陷 / 未撤销 |
| 加密子钥到期 | epoch `1736961679`，晚于主钥 516 秒 | 单独核对绑定与到期；不是原包 signer，不声称检查签名子钥反向认证 |
| 材料获取 | 2026-09-25 原批次 | HTTPS 页面 / Ubuntu keyserver / GNU 钥环的有限快照；获取日期不等于全渠道最新钥匙状态 |
| 实际核验 | 执行时宿主 UTC 起止时间、逐次 `observed_at`、命令起止时间 | 使用真实执行时钟；不提供回拨、`--faked-system-time`、忽略时间或弱摘要兼容入口。宿主与 guest 时钟正确且一致仍为信任假设 |

正向诊断必须同时保留 `EXPKEYSIG`、精确 `KEYEXPIRED` 和唯一指定主钥的 `VALIDSIG`。它只可输出 `signature-relation-matched-with-expired-key`、`current_key_state = expired`；`historical_validity = not-established` 和 `source_acceptance = not-assessed` 不变。不将 `EXPKEYSIG` 改名为 `GOODSIG`，也不把签名关系成立写成“当前公钥有效”或“历史来源已接受”。

GnuPG 的具体到期输出与退出码尚待动态核实。当前 profile 预注册正例退出 0、上述状态组合和固定 colon 字段；不同输出（包括非零退出或缺少预期到期状态）一律保存失败、停止后续步骤并另行审阅，不自动重试、放宽或改变工具时钟。字段判定沿用 [MPFR 方法依据](mpfr-verification-entry-2026-09-25.md#判定方法与六次调用)中的 GnuPG 2.4.7 文档口径；本轮未联网重新获取文档。

## 固定输入、完整材料与强摘要候选

[准备入口](prepare-gmp-verification.py)从 `artifacts/source-inputs/gmp-inputs-50ef87c-20260925/` 读回固定 manifest 下 50 路径 / 40 个对象，核对每项长度与摘要。manifest 同时匹配仓库原文及 SHA-256 `7d2d36dfe650ca3bd9c3aa678023fdb8001fd000f95c84847310be8793f337ab`。不依赖原下载缓存，不声称异盘恢复。输入导出见 [gmp-verification-inputs-2026-09-25.json](gmp-verification-inputs-2026-09-25.json)。

- 精确原包：2,094,196 bytes，SHA-256 `a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898`；配方 SHA-1 对应关系仍不构成来源认证。
- 分离签名：374 bytes，SHA-256 `94def8c1a731854de684689126046ec93589147abd4cd0025f12d741d323aa82`；签署主钥为 `343C2FF0FBEE5EC2EDBEF399F3599FF828C67298`。
- 完整 armor：32,347 bytes，SHA-256 `50561c50f40cd9746af214c995fb219bbe7f3b9c5f038b918f5df543bb3f846f`；解码 23,795 bytes、53 个 packet。原始与解码字节均留存。
- 显式强摘要候选 `gmp.strong.gpg`：1,501 bytes，SHA-256 `fee8194e5cde8f7b023639e929cae3c8773f8b9e7e3a561ee9335bbae5381fdf`。仅选择原始主钥、UID、SHA-256 UID 自认证、加密子钥及 SHA-256 binding 五个原 packet，不重签、不修改任何包体或日期。导入前后主体与两份自认证必须逐字节对应；不能通过工具丢弃坏自认证来过关。

[GMP 判定器](inspect-gmp-verification.py)记录全部 48 个未选签名 packet 的上下文、issuer、算法、时间声明和包体身份：两份旧 SHA-1 自认证、45 份未使用的第三方认证及一份第三方认证撤销。旧自认证不参与本轮认证依据，不启用 SHA-1 签名兼容；v4 指纹计算使用 SHA-1 是公钥身份格式，不能据此接受 SHA-1 签名。候选主钥仅保留已声明 `certify/sign` 能力的最新强自认证；子钥只作加密绑定检查。

第三方 issuer `598F95AAF6C99C5F` 的 class `0x30` 包体严格固定为 SHA-256 `f10200d9f5fd7bca0ac077164da53094bb785fb24fb49ec42b1768836f4701bb`，报告为 `unverified-third-party-certification-revocation`。此类声明不能直接解释为主钥自己撤销整钥，但本入口也不认证其 issuer、目标认证及撤销有效性，不据排除它而宣布撤销审查完成。新增 / 变化的撤销包、主钥 / 子钥 / UID 自撤销、未知关键 subpacket、指定撤销者、额外主体或不符固定 profile 的材料均停止；不自动换用旧认证。

公钥原文中未见某个撤销包，不等于不存在撤销；keyserver 快照可能滞后或遗漏，HTTPS 身份页也不是独立公证。是否需要最新官方钥、撤销说明、独立身份确认或可信发布时间材料，应在诊断后单独审阅；**本方案不含任何刷新请求**，新对象须先列精确 URL、限制及影响再获授权。

错误主钥负例从同一已留存 GNU 钥环选择固定 `3A24BC1E8FB409FA9F14371813FCEF89DD9E3C4F`，2,234 bytes。它只用于触发 GMP 主钥缺失，不认证该钥、不检查其弱认证、不继承 Binutils 或任何包的来源接受。正文负例只翻转原包中点一个字节，长度不变；另有空 keyring。

## 六步执行与停止条件

[执行入口](run-gmp-verification.py)参考 MPFR，保留独立 GMP 输入上限和到期诊断，复用既有采集器、容器参数、ownership 与清理检查；未修改历史文件。原公钥及排除盘点始终留存，候选是诊断输入，不是重新定义的上游完整公钥。

| 顺位 | 精确用途 | 预注册要求 |
| --- | --- | --- |
| 1 | 强摘要候选的 `import-export,self-sigs-only` | 零退出；五个主体 / 自认证包体保留；派生 stdout 不得丢弃、替换或移置任一自认证 |
| 2 | 派生 keyring `--check-sigs`，显示不可用 UID / 子钥 | 两份 `sig:!`，RSA / SHA-256、class `13` / `18`、上下文 / issuer / 日期全匹配；主钥及子钥明确到期，不能把 expired 状态改成可用 |
| 3 | 固定原包 + 固定分离签名 | 零退出，唯一签名组；`SIG_ID`、`EXPKEYSIG`、`KEYEXPIRED`、`VALIDSIG`、完整主钥 / signer、时间、version 4、RSA / SHA-512、class `00` 匹配；stdout 空 |
| 4 | 单字节篡改原包 | 正常非零退出、指定 signer 的 `BADSIG`，无成功状态 |
| 5 | 固定错误主钥 | 正常非零退出、精确算法 / signer / 时间的 `ERRSIG` 原因 9 及 `NO_PUBKEY` |
| 6 | 空 keyring | 同上，不能用 IO 错误、超时、OOM 或信号退出替代缺钥拒绝 |

任何步骤失败、未知状态、额外签名组、失败采集、身份漂移、输入修改或清理不确认，立即停止并保留原始日志。成功仅指六项诊断与清理符合预注册；不输出 `proved`、不设来源接受、不接受完整 source lock。

## 待授权的精确执行范围

仅在本次明确授权之后执行一次：

```bash
python3 docs/records/rust-linux-input-review/run-gmp-verification.py --execute-authorized
```

- 使用已有 image `sha256:55063921d0e996f717092e07dce8041cb2376cc171a070bf9a0a38a5dd16c777`，GnuPG 2.4.7 与此前 rootfs plan 的固定组件；rootfs tar SHA-256 `f1ac49bc29d33182a9c9a070b70509c739d857369876afbe307b9e9898d6b8b3`。每次执行前读回 plan / tar、核对 CLI 摘要、daemon 版本 / 能力及 image 配置。精确 rootfs、系统库、GnuPG 实现与其密码学正确性仍是可信工具，不属于独立证明。
- CLI `/usr/local/bin/docker`；socket `/Users/luobo/.orbstack/run/docker.sock`；预期 daemon `29.4.0` / API `1.54`、Linux arm64。只用已有环境；没有 pull、image import、包安装、启动 OrbStack 应用或改变系统钥环的步骤。工具、宿主或资源能力漂移即停止。
- 至多六个串行短命容器：无网络、只读根、uid / gid 1000、drop ALL、no-new-privileges、1 CPU、128 MiB memory / swap 同限、32 PID、无日志驱动、无重启；每次全新 `/work/full` 与 `/tmp`，各 16 MiB tmpfs。不挂载系统钥环、不用 ownertrust、不联网取钥、不伪造时钟。这些是诊断容器配置，不是产品隔离 / 宿主总资源硬保证。
- 新建且独占 `/Users/luobo/Code/RadishAxiom/.tmp/gmp-verification-20260925`（`0700`），目录存在即拒绝。初始 8 项输入、派生后最多 9 项；每项 2 MiB、合计 5 MiB、只读 `0444`。GMP 原包略小于 2 MiB，但双份正文和公钥合计超过 MPFR 的 4 MiB，因此本入口明确使用 5 MiB 累计上限。
- 唯一宿主可写 bind 是每次新建 status 文件：执行期间 `0666`、结束后 `0600`。stdout / stderr / status 各 1 MiB，GnuPG 文件大小限制 1 MiB；控制命令输出每流 256 KiB。输入不提取、不执行上游源码。
- 每次 GnuPG 30 秒、控制命令 10 秒；整批启动预算 600 秒、保留 150 秒停止与清理余量。预计 2–6 分钟，不保证 daemon / 宿主失联时的硬实时终止。超时先终止，清理不确认就报告具体 ID / 名称，不当作已删除。
- 只清理本轮已确认完整 ID、image / label / 名称 ownership 一致的容器。保留原有镜像、rootfs、归档与本批日志；不删除其他容器。无安装 / 系统修改，无对应回滚需求；磁盘产物留在精确任务目录，后续如需删除另行限定目标。

宿主 Python、文件系统、Docker / OrbStack、CLI / daemon、guest kernel / 库、资源报告和时钟均在可信计算基础内。现有 GMP HTTPS 身份声明是身份假设，签名不会自证公钥属于维护者；不从 MPFR / MPC / musl 的接受结论转移信任。

## 结果留存与无执行重放

执行目录保存固定输入、完整原钥、强摘要候选、派生公钥、正文负例、每次编号命令 / stdout / stderr / status、真实退出 / 采集失败、时间、清理状态与 `result.json`。启动前将本轮全部传递依赖方法按摘要读回并复制至 `methods/`；后续方法漂移不覆盖原方法快照。Python 版本 / 可执行文件摘要、image / rootfs / CLI 身份入报告。

[导出与重放入口](collect-gmp-verification-execution.py)不连接 Docker、不调用 GnuPG。成功运行必须消费恰好 45 条原命令日志，复核 daemon / image、每项命令及限额、容器前后配置、清理、输入和原始状态，再用同一判定器重算六项结论。`observed_at` 必须与保留的命令时间对应；这只是日志一致性，不是可信时间戳或独立密码学证明。失败运行只保存失败和已有部分材料，不产生成功重放声明。

```bash
python3 docs/records/rust-linux-input-review/collect-gmp-verification-execution.py \
  --output .tmp/gmp-verification-execution-20260925.json

# 将下列占位替换为导出后另行审阅 / 留存的真实摘要；不是预先声称存在结果。
python3 docs/records/rust-linux-input-review/collect-gmp-verification-execution.py \
  --replay .tmp/gmp-verification-execution-20260925.json --sha256 REVIEWED_BUNDLE_SHA256
```

JSON 导出无损保存输入、日志和原方法，二进制用 base64；单文件 16 MiB、每集合最多 256 项 / 解码合计 64 MiB、外部 JSON 最多 128 MiB。仅允许已知执行文件路径；拒绝 symlink、路径逃逸、摘要变化、额外非空 Docker config、版本或方法漂移。输出必须新建。重放无需原执行目录或输入库；须有摘要匹配的当前仓库方法，不自动执行导出中的源码。保留包仍应转入经审阅的持久存储并记录外部摘要；这不是异盘备份或包含 image / Python 的完整环境备份。

## 本地验证与未执行范围

本批新增 [37 项材料 / 状态 / 编排检查](check-gmp-verification.py)和 [13 项导出 / 重放检查](check-gmp-execution-record.py)，共 **50 项合成检查通过**。合成五包公钥含无效占位签名值，只用于结构和假工具报告测试，不冒充真实签名。覆盖到期与签署时点分离、强自认证丢失 / 移置 / 篡改、弱摘要、未知关键 subpacket / 指定撤销者、撤销变化、错误签名 / 缺钥、输出溢出、OOM / 超时、挂载 / ownership / 输入漂移、失败停止、清理失败、原方法留存，以及删除合成原目录后六项结果的完整离线重放。

开发中首轮测试暴露主体字典被当作计数映射（已改为显式主体键集）、复用测试仍调用旧模块接口，以及假采集记录缺少耗时字段；分别修正代码 / 合成夹具后通过，没有放宽密码学或到期判定。真实工具若不符合预期，仍按失败处理。

```bash
python3 docs/records/rust-linux-input-review/prepare-gmp-verification.py
python3 docs/records/rust-linux-input-review/run-gmp-verification.py
python3 docs/records/rust-linux-input-review/check-gmp-verification.py
python3 docs/records/rust-linux-input-review/check-gmp-execution-record.py
python3 docs/records/rust-linux-input-review/check-mpfr-verification.py
python3 docs/records/rust-linux-input-review/check-musl-verification-execution.py
python3 docs/records/rust-linux-input-review/check-musl-smoke.py
./scripts/check-repo.sh
git diff --check
```

留存输入重算与新导出逐字节一致，默认计划检查通过。MPFR 38 项、musl 编排 38 项及采集 / 生命周期 27 项回归均通过，连同本批共 **153 项检查通过**；复用的采集器检查只运行宿主 Python 合成子进程。仓库检查通过（1,258 个文件），`git diff --check` 通过。未运行真实验签、容器、Rust / CI、上游程序、安装、构建或远程写入；未提交、未推送。真实执行目录尚未创建，仅本地预览与 Python 缓存处于既有忽略目录。

GCC / Binutils 缺口继续阻断完整 source lock 与安装；headers 仅为内容 / 路径对应核对，未认证来源。下一步只请求上述一次 GMP 离线诊断及本地结果留存 / 重放授权；没有新增下载目标，不继承任何历史授权。诊断之后是否接受固定 GMP 来源，须依据真实结果与未闭合身份 / 撤销 / 最新性另行决定。
