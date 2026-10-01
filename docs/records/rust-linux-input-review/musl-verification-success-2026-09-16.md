# musl 两角色真实验签与负例结果（2026-09-16）

用途：记录修正后的第二次有限执行、原始证据留存及剩余验收边界，供来源验收维护者复核。

不包含：musl 正式来源 acceptance、当前所有渠道撤销状态、工具安装、产品隔离 qualification 或性能结论。

## 真实结果

项目所有者再次回复“确认”后，按[已审阅入口与范围](musl-verification-entry-2026-09-16.md)执行一次：

```bash
python3 docs/records/rust-linux-input-review/run-musl-verification.py --execute-authorized \
  --output /Users/luobo/Code/RadishAxiom/.tmp/musl-verification-20260916-attempt-2
```

宿主记录时间为 **2026-09-16 20:49:01–20:49:06（Asia/Shanghai）**，批次约 4.68 秒，入口退出 **0**，九项检查全部达到预期。九个容器分别执行一个 GnuPG 命令并退出，经 ID / ownership 核对后全部删除；没有重试、kill 请求、超时、流超限、OOM 或 daemon 失联。该时长仅描述本次固定诊断，不作为性能或容量验收。

| 步骤 | GnuPG 退出码 | 实际结果 |
| --- | --- | --- |
| archive-filter | 0 | 导出 5,834 bytes 自签名材料；原始 key / UID 与 7 个自签名正文全部保留 |
| archive-certifications | 0 | GnuPG 核验 7 个自签名，包含子钥绑定；5 个指定撤销者与原始材料对应 |
| release-filter | 0 | 导出 278 bytes 自签名材料，原始 key / UID 和自签名保留 |
| release-certifications | 0 | GnuPG 核验 1 个自签名 |
| verify | 0 | archive 与 stable release 两个必要角色均通过；正文与固定快照一致 |
| tampered-text | 1 | 三个签名均报告 `BADSIG`，篡改正文被拒绝 |
| missing-archive | 2 | 指定 archive signer 缺少公钥，额外角色不能替代 |
| missing-release | 2 | 指定 stable release signer 缺少公钥，archive 成功不能替代 |
| bad-cross-certification | 2 | archive signer 报告预期 `ERRSIG`；stderr 明确说明交叉认证无效，其他两签名仍通过 |

“九项通过”包括四个负例按预期拒绝，不是九次 GnuPG 均返回 0。负例仍会输出 138,607 bytes 正文，说明正文存在不能替代签名状态和退出码检查；本批没有消费这些失败正文作为可信来源。

两必要角色的 InRelease 签名均为 SHA-256，archive signer 为 `B8E5F13176D2A7A75220028078DBA3BC47EF2265`，stable release signer 为 `41587F7DB8C774BCCF131416762F67A0B2C39DE4`。额外 bookworm 签名也通过，但未代替两必要角色。原始公钥没有被导出材料覆盖；过滤移除了第三方认证，原始自签名正文保留并逐项核验。

交叉认证负例只改变 archive back-signature 的一个签名值字节，保留外层 binding 的已签名数据。实际 `ERRSIG` 指向 archive signer，code 为 `1`；该 signer 没有 `GOODSIG`、`VALIDSIG` 或 `NO_PUBKEY`，stderr 为 `has an invalid cross-certification`。正例与该负例共同支持本次固定 GnuPG 路径执行了交叉认证拒绝检查。

## 正文、Sources 与原包

正例解出正文为 **138,607 bytes**，与固定 InRelease 的已绑定正文逐字节一致，Release 日期检查通过。运行前、运行尾部及离线导出时均对原始归档和完整来源链复算：

| 对象 | bytes | SHA-256 |
| --- | ---: | --- |
| 完整 Sources.xz | 10,527,804 | `e8bbadd8389119e841494630998187f961d7de4d5b1dcbeed4f792a1d423299f` |
| musl 1.2.5 原包 | 1,080,786 | `a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4` |

Sources 中唯一 `musl = 1.2.5-3.1~deb13u1` 条目绑定上述原包；没有拆分 Sources、替换快照、下载或安装依赖。

## 原始材料与离线复核

[成功执行导出](musl-verification-success-2026-09-16.json)保留未改写的 `result.json`、**66 条** Docker 命令记录及全部 stdout / stderr、九份专用 status、输入与工具 / 方法身份。二进制公钥导出 stdout 使用 base64 保存，其余可严格解码的流保留 UTF-8 原文。导出大小为 1,174,101 bytes。

[统一导出入口](collect-musl-verification-execution.py)增加 `--attempt 2`，只读取本地记录，不调用 Docker 或 GnuPG。它重新核对运行方法、每条日志和每个 status 的长度 / 摘要、调用编号 / 命令 / 退出码、输入身份、自签名材料、两角色验签状态、正文来源链和四个负例，九项重算结果与原始执行报告一致。重新生成的成功导出逐字节一致。

```bash
python3 docs/records/rust-linux-input-review/collect-musl-verification-execution.py --attempt 2
```

对导出器另做了三次内存中的损坏注入：分别在正例 stdout、status 加入合成破坏字节，以及替换原报告的正例判定。三者分别因流摘要不符、status 不符、离线判定与原报告不一致而拒绝；没有改写真实文件。此复算仍复用原判定代码与宿主，不是第二套独立密码学实现，也没有再次执行签名算法。

首次失败仍保留在[原执行导出](musl-verification-execution-2026-09-16.json)和[初始运行方法](musl-verification-method-initial-2026-09-16.py)中；为保持原导出的精确生成身份，[首版导出方法](musl-verification-collector-initial-2026-09-16.py)也已留存。默认 `--attempt 1` 仍能生成与首次导出逐字节一致的内容，不用第二次成功覆盖首轮失败。

原始宿主任务目录 `/Users/luobo/Code/RadishAxiom/.tmp/musl-verification-20260916-attempt-2` 保留公开输入、status 与编号日志，文件内容共 1,528,072 bytes；原镜像、首轮任务目录与独立输入归档继续保留。九个容器的精确 ID、配置、结束状态与删除结果全部在成功导出中。没有新增后台服务或遗留本批容器。

## 能力边界与下一步

- 本次完成的是固定材料在受信任 GnuPG 2.4.7 / 宿主环境下的两角色验签、自签名检查、交叉认证拒绝负例和完整摘要链复核。纯解析器输出中的 `cryptography_executed_by_parser = false` 等字段保持原义；真实密码学操作由不同的 GnuPG 步骤及其参数、状态和退出码提供证据。
- `TRUST_UNDEFINED` 和 stderr 的公钥身份信任警告保留。身份信任仍依据[已确认的限定 Debian / HTTPS 方案](musl-debian-auth-2026-09-10.md#项目所有者确认与执行顺位)，不宣称独立 Web of Trust。
- 公钥材料时效仍限于 2026-09-10 获取时点。公告不覆盖 stable release，公告签名与当前所有渠道撤销状态没有重验；快照材料中未见撤销不能推出外部不存在更新的撤销。
- 本次正常与拒绝路径完成容器清理；未动态制造资源耗尽、daemon 失联或宿主崩溃，不扩大为这些故障路径或产品 runtime qualification 的验收。
- **来源 acceptance 仍为 `not-assessed`。** 下一步按同一原包的有条件方案，审阅来源验收声明、剩余信任、材料保留及恢复责任；不自动更改正式验收格式或批准安装。

已有四组合成 / 本地检查 90 项通过，未因本次真实执行再次运行；本轮验证为九项真实诊断、全部日志身份复核、九项离线判定重算、三项损坏拒绝及仓库检查。`./scripts/check-repo.sh` 通过（1,151 个文件），`git diff --check` 通过。Rust / CI、产品构建、安装、激活与远程写入未执行。本任务共 11 个变更文件，仍未暂存、未提交、未 push。
