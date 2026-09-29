# GMP 工具语义本地审阅与精确材料缺口

日期：2026-09-29（Asia/Shanghai）；基线：`dev` / `3e28608`，启动时工作区干净，与本地 `origin/dev` 一致，未刷新远端。

用途：向维护者交接第二次 GMP 诊断后，已核对的本地工具材料、尚缺的语义依据和下一项有界获取方案。不包含判定器 v3、第三次真实验签、来源接受、安装或产品 qualification。

后续：项目所有者随后授权四项获取，[实际结果与源码审阅](gmp-tool-source-review-2026-09-29.md)已完成，并形成 v3 离线判定候选。下文“材料不足 / 尚未执行”及机器导出保留本轮获取前的时点含义，当前顺位以状态页为准。

## 本批结果

本地材料尚不足以确认两处工具语义，因此保持原判定器和两次失败不变：

- `KEYEXPIRED` 在第二次自认证检查中出现三次，尚未确认对应调用路径、允许重复的条件和可接受顺序 / 数量。
- colon `sub:e` 的到期字段为 `1736961163`，比绑定包声明的 `1736961679` 早 516 秒。与主钥到期相同是实际观察；“有效到期被主钥截断”仍是待核实解释。

本次授权是先读本地材料、依据充分后准备修订；缺依据时列精确补充范围。没有以已有动态输出替代依据，没有去重、改原声明、回拨时钟或扩大白名单。GMP 原包分离签名及三个负例仍未执行，`source_acceptance = not-assessed`、`historical_validity = not-established`。

## 本地核对与证据层级

[只读入口](inspect-gmp-tool-materials.py)与[机器导出](gmp-tool-semantics-review-2026-09-29.json)完成以下核对：

1. 从 `artifacts/source-inputs/musl-verifier-2fb2e70-20260912` 读回固定 manifest 下全部 **132 路径 / 87 对象**，核对长度和摘要；不依赖原下载缓存。
2. 从已留存的 `gpg` 二进制包在内存读取 control、完整 payload 目录和手册；没有提取或运行包内程序。包为 `gpg=2.4.7-21+deb13u1+b4` / arm64，control 声明源码为 `gnupg2=2.4.7-21+deb13u1`。二进制包 578,896 bytes，SHA-256 `840abc3e9178b9578fbc9c9674ebb2f3b983790f713ffd2b6a0371d8670dc8e7`。
3. `usr/share/man/man1/gpg.1.gz` 解压正文为 181,578 bytes，SHA-256 `1c3f57387f18152a63d383a4c289a055c679666fc5d7acfef36067ac990ace29`，与本机此前导出的 `gpg-manual.txt` 一致。第 324–338 行说明 `--check-sigs` 的签名检查用途与状态标记，也明确该命令不展示签名钥的撤销状态。第 2962–2968、3355–3362 行将 colon 与 status 的详细定义引向源码的 `doc/DETAILS`。
4. 该固定 `gpg` 包未携带 `DETAILS` / `gpg.texi`；手册没有 `KEYEXPIRED` 或 `KEY_CONSIDERED` 字面定义，未提供本次重复通知或有效子钥到期的充分依据。缺失结论限定于已检查的持久库与该包，不能外推为全机或上游不存在材料。
5. 重新扫描固定完整 Sources 索引，`gnupg2` 唯一候选与旧源码投影逐项一致；四个源码对象的摘要均不在该持久库中。先前记录中的 GnuPG 2.4.7 在线文档链接可用于导航，但不能代替本次可读回、绑定到实际 Debian 修订的正文与补丁。

这里区分上游版本 `2.4.7`、Debian 源码修订 `-21+deb13u1` 与 arm64 二进制重建 `+b4`。仅阅读上游 tag 不能排除发行版补丁影响；control / 索引对应也不是该 binary 的可重复构建证明。固定工具及宿主仍保留既有信任角色。

两次历史失败的只读导出重算分别与原有 1,942 bytes、3,958 bytes 报告逐字节一致；原始 bundle、方法、状态及结果未改写。新审阅入口不导入或执行归档中的源码，不调用 Docker / GnuPG。

## 下一项精确获取方案（尚未执行）

目标仅为补齐实际 GnuPG 修订的语义审阅材料。四个 URL 均由固定 Sources 条目的 `Directory` 和文件名拼接，尚未重新请求确认在线可用性；404、跳转或摘要不符均停止，不换版本、镜像或自动重试。

共同 URL 前缀：`https://deb.debian.org/debian/pool/main/g/gnupg2/`。每个完整 URL、长度与 SHA-256 同时保存在机器导出的 `supplemental_material_targets`。

| 文件名 | bytes | SHA-256 |
| --- | ---: | --- |
| `gnupg2_2.4.7-21+deb13u1.dsc` | 4,933 | `30a96cd2d26a57f6796507bf8f083825734d4081e3c5f922d2b99bb2bf671212` |
| `gnupg2_2.4.7.orig.tar.bz2` | 8,010,244 | `7b24706e4da7e0e3b06ca068231027401f238102c41c909631349dcc3b85eb46` |
| `gnupg2_2.4.7.orig.tar.bz2.asc` | 390 | `cec7da75dab60e3e2f6bf92ed1174126a1e5a1cc5e448f9e004a23be2dd227f6` |
| `gnupg2_2.4.7-21+deb13u1.debian.tar.xz` | 131,264 | `3941a8a537e258f6216ad1c1b9ecb255dfc286e5d03eb39805e536de4a448856` |

总正文 **8,146,831 bytes，约 7.77 MiB**。原包用于 `doc/DETAILS`、相关实现及许可正文；Debian 包用于补丁序列和构建配方；`.dsc` 用于交叉核对源码组成；`.asc` 只留存随源码发布的签名材料，不在本批执行验签或取钥。

拟执行范围与副作用：

- 使用已有 `/usr/bin/curl`，每项一次 HTTPS 请求；保留 TLS 校验，禁用用户 curl 配置，不跟随跳转、不自动重试。正文上限为表中各自精确长度，取得后逐项核对 SHA-256，任一步失败即停止。
- 每项 curl 最多 60 秒，父进程最多 65 秒；四项串行请求预计 1–5 分钟。失败日志和部分正文保留，不追加未说明的恢复请求。
- 独占新建项目内 `.tmp/gmp-tool-semantics-3e28608-20260929/`，已有同名目录则拒绝覆盖；保存请求计划、方法、时间、工具身份、正文、stdout / stderr。成功后复用现有留存器写入新的 `artifacts/source-inputs/gmp-tool-semantics-3e28608-20260929/` 并恢复核对，原目录和持久库均保留。新增磁盘占用预估低于 40 MiB，不是宿主配额保证。
- 后续只作有界静态读取：归档解压总量每包最多 128 MiB、最多 10,000 成员、单成员最多 8 MiB；拒绝异常路径、特殊成员和超限，不执行 build / configure / maintainer scripts，也不把归档成员落到系统目录。取出相关文档、实现和补丁作逐处依据审阅。
- 无安装、容器、GnuPG、系统配置或远程写入。无安装状态需要回滚；输入与失败材料保留供复核，不在任务结束时自动删除。新增材料仅绑定本次审阅，不自动接受 GMP 来源或构成 GnuPG 自证。

获取后先确认文档定义、源码调用路径和 Debian 补丁是否共同解释两处差异，再设计版本化联合判定与正负例。若仍缺依据就继续保持阻断；这项获取授权不自动覆盖第三次 GMP 验签。

## 验证与交接

已运行两次历史失败导出的逐字节重算；首次失败回归 6 项、第二次失败回归 7 项，共 **13 项通过**。本地材料导出重新生成后逐字节一致；仓库级检查与 `git diff --check` 通过。

```bash
python3 docs/records/rust-linux-input-review/inspect-gmp-tool-materials.py
python3 docs/records/rust-linux-input-review/check-gmp-filter-attempt.py
python3 docs/records/rust-linux-input-review/check-gmp-certification-attempt.py
./scripts/check-repo.sh
git diff --check
```

本批只增加诊断入口、机器导出和审阅记录，并更新当前状态与本专题索引；未改历史方法或生产代码。未运行 Rust / CI、真实密码学工具、网络获取、产品构建 / 安装或提交 / 推送；没有后台进程。本批更改未暂存、未提交，临时导出与 Python 缓存位于既有忽略目录。headers、GCC / Binutils、备份增量的后续顺位保留，本次未扩展为这些主题的执行验收。
