# musl 两角色验签有界执行入口（2026-09-16）

用途：记录本批入口实现、离线检查和下一次真实有限执行的精确范围，供维护者审阅与执行。

不包含：musl 来源 acceptance、安装或产品 qualification。首次真实执行在容器启动前失败，原始结果与修正见文末；随后获确认的[第二次真实九项诊断已通过](musl-verification-success-2026-09-16.md)。

## 本批范围与解除的不确定性

接续[输入与状态判定准备](musl-verification-preparation-2026-09-12.md)，本批从 `dev` 的 `91bade1` 开始，初始工作区干净，与本地 `origin/dev` 引用一致；未刷新远端。

固定镜像没有 shell，不能在镜像内增加临时脚本，也不能假设一个容器的 tmpfs home 能被另一个容器继续使用。[新入口](run-musl-verification.py)复用[既有采集与生命周期代码](run-musl-verifier-smoke.py)，将每次 GnuPG 调用拆为独立容器。容器每次挂载新 `/work/full` tmpfs，以只读目录接收输入；过滤结果通过有界 stdout 回到宿主，检查后另存为只读文件，再显式传给下一次调用。

旧 smoke 入口与历史方法字节未修改。新入口没有 import 镜像、fetch、安装、shell 或新增工具路径；默认运行只打印计划，不连接 Docker。

输入仍是[已留存归档](musl-retention-2026-09-12.md)中的固定 manifest、InRelease、官方 archive / release 公钥、keyring 包、完整 Sources.xz 与原包。首先调用已有准备方法核对全部长度与摘要；从完整原始 keyring 分离的两角色块必须与官方 armor 解码字节完全一致。所有数据准备写入本次新建目录，不覆盖前批暂存输入。

## 原始材料与密码学职责

[公钥检查模块](inspect-musl-verification-keys.py)是固定 v4 公钥材料的有界结构读取器。它支持本输入用到的定长 packet 与 signature subpacket，拒绝截断、部分 / 不定长包、秘密材料、额外 key / UID / subkey、重复指纹、撤销签名和弱摘要。它不验证密码学、不替代 GnuPG、不新增通用 OpenPGP API。

结构依据为 [RFC 4880 的 packet / v4 signature 格式](https://www.rfc-editor.org/rfc/rfc4880)；只用于既有 v4 快照，不声称覆盖后继标准。v4 指纹使用 SHA-1 计算身份，与接受 SHA-1 签名是不同操作；本批继续拒绝弱签名。

原始公钥与 `import-export,self-sigs-only` 派生材料分别保留。派生材料必须保持所有 key / UID 字节及原始自签名正文多重集，不能因导入移除了无效自签名而通过；外国签名可被过滤，但原文仍参与撤销与强摘要结构检查。GnuPG 随后以 `--check-sigs` 检查派生材料，colon 输出必须覆盖全部原始自签名及其正确上下文、主钥、指纹、有效期和摘要算法。指定撤销者的 `rvk` 行与原始已签名 subpacket 绑定；它表示撤销权限指定，不是撤销事实。

archive 签名子钥必须有原始绑定与强摘要 back-signature 结构；最终 InRelease 验证显式使用 `--require-cross-certification`。只有固定 GnuPG 在实际验签中接受该 signer，才能报告由该工具复核了交叉认证。`--check-sigs`、`import-export` 和交叉认证选项的职责依据 [GnuPG 2.4.7 手册](https://raw.githubusercontent.com/gpg/gnupg/gnupg-2.4.7/doc/gpg.texi)，colon / status 字段依据 [2.4.7 DETAILS](https://raw.githubusercontent.com/gpg/gnupg/gnupg-2.4.7/doc/DETAILS)。真实输出若超出当前判定集合，应保留失败并审阅，不静默忽略新状态。

## 采集、资源与失败传播

- 保留原 smoke 的非 root、只读根、无网络、drop ALL、no-new-privileges、private cgroup、IPC none、1 CPU、128 MiB memory / swap 同限、32 PID、无日志驱动、无重启与禁止拉取设置。新入口先检查新增的两个 bind、tmpfs home 与文件限额，再复用原有其余容器断言。
- `/tmp` 与 `/work/full` 各为 16 MiB tmpfs，后者 mode `0700`、uid / gid `1000`；每次容器删除后不复用。输入目录只读挂载到 `/inputs`。宿主与 Docker / OrbStack 仍是诊断可信输入，这些参数不是产品隔离验收。
- 每次仅有一个宿主可写 bind 文件 `/work/status`，用于 GnuPG 专用 status；stdout 承载二进制、colon 或 Release 正文，stderr 留存人类诊断，二者不混进 status。宿主 status 文件位于新建 `0700` 任务目录，调用期间 mode `0666` 供容器 uid 写入，清理后改为 `0600`。未挂载可写宿主目录。
- GnuPG 每次 30 秒，stdout / stderr 各最多 1 MiB；status 文件通过 `RLIMIT_FSIZE = 1 MiB` 和读取上限控制，status 写失败要求退出。该文件限额也作用于容器其他常规文件写入。Docker 控制命令每次 10 秒、每流 256 KiB；继续使用旧采集器的单调时钟、双流排空、客户端进程组终止与回收。
- 批次预算 600 秒，距预算结束不足 150 秒时不再启动新调用，为该次状态核对与清理留余量。此预算不是对宿主文件系统阻塞或 daemon 失联的硬实时保证。
- 每次绑定确切命令及编号日志、工具与方法身份、调用观察时间、stdout / stderr / status 身份、真实退出码、容器结束状态与输入摘要；开始前和结束后复核输入。退出码不一致、OOM、采集超限 / 超时、文件变化、未知状态和清理未确认都会阻止后续步骤与整批通过。
- 只清理已确认完整 ID 且 ownership 匹配的本批容器。create 结果不明不按名称删除；daemon 失联不宣称已清理。异常保留编号日志与 `result.json`，停止后由维护者对精确名字 / ID 做人工核对。

这些参数固定诊断执行面，不能证明宿主可信，也不能把前后摘要相同解释成抵御恶意宿主的不可变输入保证。

## 已准备的九次 GnuPG 调用

| 顺位 | 操作 | 必须满足的结果 |
| --- | --- | --- |
| 1–2 | archive 原始公钥的 self-only 导出与自签名检查 | 原始自签名不被丢弃，全部 colon 结果有效 |
| 3–4 | release 原始公钥的 self-only 导出与自签名检查 | 同上 |
| 5 | 用完整原始 keyring 验证原 InRelease 并输出正文 | 原两角色严格状态判定通过；正文等于固定快照，绑定完整 Sources 与原包 |
| 6 | 将正文唯一 `Origin: Debian` 改为 `Origin: DebiaX` 后验签 | 正常 GnuPG 非零退出，出现已知 signer 的 `BADSIG` |
| 7 | 仅提供 release 原始公钥 | 正常非零退出，缺少 archive 指定 signer |
| 8 | 仅提供 archive 原始公钥 | 正常非零退出，缺少 release 指定 signer |
| 9 | 完整 keyring 中仅破坏 archive back-signature 的一个签名值字节 | 原 archive signer 报告预期 `ERRSIG`，不能转为该 signer 的 `VALIDSIG` / `GOODSIG` 或缺少公钥 |

第 9 项先确认嵌入签名位于外层 binding 的 unhashed 区；只翻转其末字节，不改变 binding 的已签名数据。若位置、唯一性或结构不符合预期则停止。第 6–9 项使用 `--proc-all-sigs`，避免前面的其他签名失败使必要角色负例没有被执行。非零退出本身、超时、资源失败或无关错误不能充当负例通过。

执行尾部重新核对归档中的完整 Sources.xz（10,527,804 bytes）和原包（1,080,786 bytes）。任何步骤失败都不会产生整批成功；即使九项全部通过，结果仍为 `source_acceptance = not-assessed`，需沿已确认的有条件信任方案另行审阅 acceptance。

## 执行前的入口验证

已完成本地归档读回与摘要链复算，没有写入新暂存目录或调用 GnuPG。两份解码原文分别为 archive 8,698 bytes、release 962 bytes，与完整 keyring 中对应块一致；结构读取得到 archive 7 个自签名及 5 个指定撤销者、release 1 个自签名。交叉认证负例已在本地检查为等长且只差一个字节；这些均不是新密码学证据。

以下四组检查实际通过，共 **88 项**：

```bash
python3 docs/records/rust-linux-input-review/check-musl-verification-execution.py
python3 docs/records/rust-linux-input-review/check-musl-smoke.py
python3 docs/records/rust-linux-input-review/check-musl-verification.py
python3 docs/records/rust-linux-input-review/check-musl-debian-auth.py
```

分别为新入口 36 项、既有采集 / 生命周期 27 项、已有输入 / 状态判定 16 项及历史 Debian 诊断 9 项。新测试全部使用合成公钥结构、状态或假 daemon；采集器测试仅启动宿主 Python 合成子进程。它们不连接 Docker，也不执行已下载工具，不构成真实签名、容器限额、挂载传递或资源耗尽验收。新检查延续本主题显式诊断入口，未加入默认仓库门禁。

仓库级 `./scripts/check-repo.sh` 通过（1,145 个文件），`git diff --check` 通过。复核范围为本批四个新增文件与当前状态更新，未改动既有实现或历史证据。

上述入口准备阶段未运行真实 Docker / GnuPG、Rust / CI、产品构建、下载、安装或远程操作；未修改公共格式、首域语义、正式信任方案及既有历史证据。新增文件和状态更新未暂存、未提交、未 push；入口准备阶段没有启动后台服务或遗留容器。

## 已确认的首次真实有限执行范围

默认离线预览：

```bash
python3 docs/records/rust-linux-input-review/run-musl-verification.py
```

项目所有者随后回复“确认”，以下命令已执行一次；实际结果见文末，不覆盖后续执行：

```bash
python3 docs/records/rust-linux-input-review/run-musl-verification.py --execute-authorized
```

参数标志只记录当前任务授权，不自行授予权限。精确目标为已有 image ID `sha256:55063921d0e996f717092e07dce8041cb2376cc171a070bf9a0a38a5dd16c777`、已有 socket `/Users/luobo/.orbstack/run/docker.sock` 与 `/usr/local/bin/docker`。CLI、rootfs tar、rootfs plan、daemon 版本与能力必须仍符合原 smoke pin，否则保持失败。不会重新下载、导入镜像或启动 OrbStack 应用。

预计 3–10 分钟，最多九个串行短命容器，每次 GnuPG 最多 30 秒，不自动重试。任务目录为 `/Users/luobo/Code/RadishAxiom/.tmp/musl-verification-20260916`，必须尚不存在；输出为九次调用的原始日志、status、派生公开材料与汇总结果，容器与日志配置见上节。整个材料量上界按流与文件限额估算低于 128 MiB，不是宿主目录配额保证。

清理仅覆盖本次确认 ownership 的容器；原镜像、前批缓存和独立归档保留，日志与派生公开输入留待复核。清理未确认时停止并报告精确容器标识，不自动更改系统或其他容器。没有产品激活、系统安装或远程状态需要回滚。

公钥时效仍限于 2026-09-10 获取材料；公告不覆盖 stable release，公告签名与当前所有渠道撤销状态没有重新核验。固定工具、Python 与宿主仍属于诊断可信输入。真实九项运行及输出差异审阅完成前，不把本批入口标为已动态验收。

## 首次执行、修正与第二次执行范围

首次实际调用于 2026-09-16 20:41:31–20:41:32（Asia/Shanghai）完成，入口退出 **1**。固定归档、Docker CLI、rootfs、daemon / image 前置通过，随后创建首个 archive-filter 容器；启动前 inspect 因 `verification bind specification drift` 被拒绝，整批停止。**没有发出 `container start`，GnuPG 实际执行次数为 0。** 容器 `34f956c252d19cfd8e768211af3bc8ee3b08930b98c818af2106923f4a965528` 经 ownership 检查后删除，`container rm` 退出 0；最后核对状态为 `created`、`Running = false`，status 文件为空。没有新镜像、后台进程或遗留本批容器。

[原始执行导出](musl-verification-execution-2026-09-16.json)保留全部 8 条命令的 stdout / stderr、参数、限额、时间与退出码，以及未改写的失败 `result.json`、输入与方法摘要。[导出入口](collect-musl-verification-execution.py)只读取本地材料，逐项复核执行方法、日志与输入身份后生成该 JSON；不连接 Docker。[初始方法源码](musl-verification-method-initial-2026-09-16.py)已按实际报告的 `df5d658e120b95e47cbaa8f82afcee3f86820fdf040ad32e8cef17885c7c0941` 摘要留存，当前修正不能重写首次运行事实。原任务目录和全部公开输入继续保留。

根因在入口的 API 判定：真实 `HostConfig.Mounts` 对 status bind 省略 `ReadOnly = false`，同时 effective `Mounts` 明确返回该 bind 的 `RW = true`；输入 bind 的 `ReadOnly = true` 与 `RW = false` 均存在。[Moby 字段定义](https://raw.githubusercontent.com/moby/moby/master/api/types/mount/mount.go)将 `ReadOnly` 声明为带 `omitempty` 的 bool，与此次观察一致；该在线源码用于解释字段语义，精确本机事实以导出的原始 inspect 为准。

先新增回归再修实现：新 38 项检查首次退出 1，有两处失败，一处复现省略字段被误拒，另一处暴露 Python 字典相等把数字 `0` 当作 `False`。修正仅将缺失的 `ReadOnly` 按该布尔字段定义解释为 false，并对显式值强制 bool 类型；只读输入缺失声明、status 的 null / 数字 / 字符串、额外挂载以及 effective `RW` 错误仍拒绝。没有修改实际挂载命令、资源限额或停止条件。

修正后 38 项检查通过；以保存的真实启动前 inspect 做离线重放，完整容器判定通过。该重放没有调用 daemon，不代表 GnuPG、tmpfs 生命周期、数据传递或九项矩阵通过。本轮重跑上述四组检查，共 **90 项通过**（38 + 27 + 16 + 9）；仓库检查通过（1,148 个文件），`git diff --check` 通过。首次真实失败不会因本地修正被改为成功。八个本任务变更文件仍未暂存、未提交、未 push；任务目录内公开输入、空 status 与编号日志保留。

首次授权明确为一次运行且不自动重试，因此修正轮未自行进行第二次真实执行。第二次沿用同一镜像、九项命令、3–10 分钟预计时长、30 秒单次 GnuPG 限额与相同清理方式；只更换新输出目录以保留首轮材料。项目所有者随后再次回复“确认”，以下命令已执行一次，结果见[成功记录](musl-verification-success-2026-09-16.md)：

```bash
python3 docs/records/rust-linux-input-review/run-musl-verification.py --execute-authorized \
  --output /Users/luobo/Code/RadishAxiom/.tmp/musl-verification-20260916-attempt-2
```

新目录按要求独占创建，未重复下载或导入镜像；九项达到预期，九个容器全部删除，日志与派生输入保留。实际挂载与资源范围同上，没有自动重试。当前 musl 来源 acceptance 继续为 `not-assessed`，下一步进入该固定原包的来源验收审阅。
