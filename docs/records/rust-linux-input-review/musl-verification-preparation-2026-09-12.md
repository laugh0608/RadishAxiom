# musl 验签输入与状态判定准备（2026-09-12）

用途：记录四项工具诊断之后的输入准备与状态判定实现，供下一批有限执行入口复用。不包含新密码学验签、来源 acceptance 或产品 qualification。

前批工作区已提交为 `f3ed1ce`（`chore(runtime): 完成 musl 验证环境受控诊断`），仍在 `dev`，未 push。四项真实诊断、镜像与容器清理事实以[前批记录](musl-verifier-smoke-execution-2026-09-12.md)为准，本批没有重跑 Docker 或 GnuPG。

## 输入准备与实际读回

[准备入口](prepare-musl-verification-inputs.py)只使用 Python 标准库与已有解析方法，从[独立归档](musl-retention-2026-09-12.md)读取六个对象：InRelease、两份官方公钥、keyring Debian 包、完整 Sources.xz 和 musl 原包。先校验固定 manifest 摘要，再逐项核对长度与 SHA-256；从 keyring 包的固定路径提取原始公钥环，不执行包脚本。

实际准备到 `.tmp/musl-verification-f3ed1ce-20260912/inputs/` 的文件为：

| 文件 | bytes | 用途 |
| --- | ---: | --- |
| `InRelease` | 140,416 | 待验签的原始 cleartext envelope |
| `archive.asc` | 11,861 | trixie archive 官方公钥原文 |
| `release.asc` | 1,384 | trixie stable release 官方公钥原文 |
| `debian-archive-keyring.gpg` | 55,918 | 从已归档包提取的完整原始公钥环 |

四份合计 **209,579 bytes**，逐项写入新目录、设为 `0444` 并读回；入口拒绝覆盖已有目标目录、符号链接父路径以及额外 / 缺失文件名。文件权限是普通宿主文件权限，不代表不可变存储；未来执行前仍须复核内容与挂载配置。

完整 Sources.xz（10,527,804 bytes）和 musl 原包（1,080,786 bytes）继续留在归档对象中，不复制进这四份待传入容器的文件。准备入口同时核对未验签的 InRelease 正文摘要与完整 Sources，并按唯一 `musl = 1.2.5-3.1~deb13u1` 条目绑定同一 `musl-1.2.5.tar.gz`。这只说明给定字节相互匹配，不能证明正文或公钥可信。

[实际准备报告](musl-verification-inputs-2026-09-12.json)保留六个归档对象、四份输出、宿主侧两份大文件及生成方法的精确身份。首次执行命令为：

```bash
python3 docs/records/rust-linux-input-review/prepare-musl-verification-inputs.py \
  --stage .tmp/musl-verification-f3ed1ce-20260912/inputs
```

父目录预先建立；原 stdout 留在同批 `inputs-plan.json`。不应对已有目录重复执行 `--stage`。省略该选项可无写入重新核对归档并输出计划；其 `staged = false`，不带 `staging_path`，其他字段应与实际报告一致。本批已重新调用 `prepare()` 比较其余全部字段，另行读回四份文件和权限，结果一致；Git 中报告与首次 stdout 原文一致。

上述相对路径均以 `/Users/luobo/Code/RadishAxiom/` 为根。没有下载、安装、系统配置修改或新增后台进程；既有 OrbStack 镜像本批未变更，缓存和独立归档未清理。

## 两角色状态判定

[状态判定器](inspect-musl-verification-status.py)接收 GnuPG 专用 status 字节、调用退出码、观察时间及采集失败原因，逐个 `NEWSIG` 分组核对：

- archive 主钥 `04B54C3CDCA79751B16BC6B5225629DF75B188BD` 必须配对 signer `B8E5F13176D2A7A75220028078DBA3BC47EF2265`；stable release 主钥和 signer 均为 `41587F7DB8C774BCCF131416762F67A0B2C39DE4`。两角色缺一即拒绝，已知 bookworm 签名不能替代它们。
- 同组 `GOODSIG`、`VALIDSIG`、`SIG_ID` 和 `KEY_CONSIDERED` 必须相互一致；重复角色、缺失或不完整分组均拒绝。接受固定 v4、cleartext 类和 SHA-256 / SHA-384 / SHA-512，拒绝 SHA-1、未来签名、已过期签名及不一致的日期。
- 任意非零退出码、采集失败、明确错误状态或未知状态均拒绝；`TRUST_UNDEFINED` 只作为注解，不作为身份信任证明。单有 `VALIDSIG` 或退出 0 不足以通过。
- 输入最多 1 MiB、4,096 行、每行 8,192 bytes，严格 UTF-8 与 LF 分行；不混入 stderr、人类可读诊断或控制字符。

字段定义依据 [GnuPG 2.4.7 DETAILS](https://raw.githubusercontent.com/gpg/gnupg/gnupg-2.4.7/doc/DETAILS)。这是固定诊断输入的严格消费器，不是通用 OpenPGP 实现；遇到真实 2.4.7 输出差异应保留失败并审阅，不静默忽略新状态。

输出仅为 `required-role-statuses-matched`，明确保留 `cryptography_executed_by_parser = false`、`self_certifications_assessed = false`、`cross_certification_assessed = false` 和 `source_acceptance = not-assessed`。本批测试使用合成状态，尚未消费本次真实 2.4.7 验签输出。状态、退出码、采集是否完整及观察时间的真实性依赖未来执行入口；此解析器自身不能证明它们来自固定工具、固定输入或同一次调用。

## 验证与剩余实现

`python3 docs/records/rust-linux-input-review/check-musl-verification.py` 的 **16 项合成检查通过**，覆盖角色错配、缺一角色、失败传播、算法 / 时间 / 分组、输入上限、LF 分帧及暂存边界。新增 LF 回归用例最初暴露三个失败：Python `splitlines()` 将 U+0085 / U+2028 / U+2029 也作为换行，预期拒绝却未抛错；该次命令退出 1。判定器现显式拒绝这些分隔符并按 LF 切分，同一命令重跑退出 0；没有通过删减负例处理失败。

实际执行入口仍需完成以下工作，不能把本批两个准备入口视为已可完成正式验签：

1. 复用固定镜像和已有有界命令采集，明确逐次 tmpfs home 初始化、输入传递和退出清理。现有镜像没有 shell；一个 GnuPG 容器退出后，其 tmpfs 不保留给下一个容器，不能假设 import 后其他容器可直接使用其 home。
2. 分开保留完整原始 keyring 与过滤后的自签名材料，并分别实现自签名、撤销、子钥绑定和交叉认证检查。[GnuPG 2.4.7 手册](https://raw.githubusercontent.com/gpg/gnupg/gnupg-2.4.7/doc/gpg.texi)中的 `import-export` 会导出经导入处理的公钥，不能用它替代原文做完整性检查；`self-sigs-only` 也不能替代完整撤销材料。具体传递方式尚未动态验证。
3. 将真实命令、工具 / 输入身份、status、stdout / stderr、退出码、时限与输出上限、采集失败及观察时间绑定，再接入本批判定器；解出的 Release 正文须与原快照及完整 Sources / 原包再次匹配，并补真实密码学负例。
4. 保留材料时效边界：归档公钥和 InRelease 不是对所有渠道当前撤销状态的证明，固定快照也不代表最新安全更新。按[已确认信任方案](musl-debian-auth-2026-09-10.md#项目所有者确认与执行顺位)完成完整链后再决定 acceptance。

本批没有执行新公钥导入或密码学验签，未变更公共格式、首域语义、正式信任方案及上游 SHA-1 拒绝。下一批先实现并复核上述执行入口；需要新的真实有限执行时，再给出精确命令、副作用、时限和清理方式供确认。资源耗尽 / daemon 失联的真实行为、产品 runtime qualification 仍未验收。

仓库级 `./scripts/check-repo.sh` 通过（1,140 个文件），`git diff --check` 通过。本批六个文件变更留在工作区未提交；`dev` 相对本地 `origin/dev` 领先 7 个提交，未刷新远端引用或 push。未运行 Rust / CI 或产品构建，这些实现本批未修改。
