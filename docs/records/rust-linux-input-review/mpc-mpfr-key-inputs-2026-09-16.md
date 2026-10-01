# MPC / MPFR 公钥材料与验签前置

日期：2026-09-16；基线 `dev` / `ee917c7`。用途：记录公开公钥与身份页面的实际获取、未认证结构和后续执行边界，供来源审阅者交接；不作身份、密码学或来源验收决定。

## 本轮推进

项目所有者要求“提交工作区更改，继续推进下一步”。先将上一轮 15 个文件提交为 `ee917c7`，工作区当时干净；随后说明公开身份材料的目标及有界 HTTPS 获取范围，经网络执行权限确认完成本批读取。没有安装依赖、运行 GnuPG、导入宿主钥匙环、启动容器或接受新信任策略。

[获取入口](fetch-mpc-mpfr-key-inputs.py)复用已留存的 `fetch-mpc-mpfr-inputs.py`，原方法未改。每次另存路由方法身份与目标范围；每对象至多 256 KiB、curl 60 秒 / 父进程 65 秒，仅 HTTPS / TLS ≥ 1.2、不跟随重定向。MPFR 公钥 URL 经人工从实际留存身份页选择，入口要求它确实是该页链接且仍在 `https://www.vinc17.net/` 下，不自动遍历链接或查询 keyserver。

| 目标 | 实际结果 |
| --- | --- |
| [MPC 下载页](https://www.multiprecision.org/mpc/download.html) | 第一次沙箱请求无法连接本机代理（curl 7 / HTTP `000` / 空正文），获执行权限后同 URL 重试，HTTP `200` / 8,741 bytes；页面直接链接 `enge.gpg` |
| [MPFRCX 指纹页](https://www.multiprecision.org/mpfrcx/download.html) | curl 35 / HTTP `000` / 空正文，TLS 握手失败；保留 stderr，不自动重试。网页工具本轮可读完整指纹，但未得到有获取日志的本地页面正文 |
| [MPFR 4.2.2 页](https://www.mpfr.org/mpfr-4.2.2/) | HTTP `200` / 7,752 bytes；完整指纹及维护者身份页链接留存 |
| [MPFR 维护者身份页](https://www.vinc17.net/pgp.html) | 网页工具报告不支持 `application/xhtml+xml`；有界 HTTPS 请求 HTTP `200` / 20,721 bytes，列当前与旧指纹并链接 `key.asc` |
| [MPC 公钥](https://www.multiprecision.org/downloads/enge.gpg) | HTTP `200` / 124,014 bytes；SHA-256 `dae0bf8d40b5e3cbb64b3c98fbcf48857f983b8bf811f761a206ebae75f040a8` |
| [MPFR 公钥](https://www.vinc17.net/key.asc) | HTTP `200` / 15,034 bytes；SHA-256 `c534c66170c22555573751da626d0bbef8d032b61d03be9cf8be7571dd07ab07` |

七次请求共五次成功、176,262 bytes 正文；失败分别保留，没有以重试成功抹去。MPFRCX 页面失败后，只继续其余不同目标的首次请求。[机器记录](mpc-mpfr-key-inputs-2026-09-16.json)包含所有请求及路由身份、签名字段和公钥库存。只读页面与公钥字节不是独立信任链；完整身份验收仍待审阅。

## 公钥结构观察

[盘点方法](inspect-mpc-mpfr-key-inputs.py)核对实际获取正文 / 日志、两层方法身份、固定 URL 和 armor CRC24，再复用有界 OpenPGP packet / subpacket reader。v4 指纹按其定义使用 SHA-1，这与接受 SHA-1 签名是两回事。新方法将摘要字段原样报告，不放宽旧 musl 严格验证器，也不把未认证 issuer 当成真实签名者。

### MPC

- 唯一主钥指纹 `AD17A21EF8AED8F1CC02DBD9F7D5C9BF765C61E3`，算法字段 17 / DSA，与已取得原包签名的声明一致；一个算法 16 的子钥、两个 UID，共 232 个 packet。
- 228 份签名中有 26 份的 issuer **声明**为主钥，自签候选摘要字段均为 SHA-256；其余第三方认证不承担本轮身份信任。
- 两个 UID 最新的自签候选创建字段均为 2023-07-05，对主钥声明的到期时间均为 **2024-07-04 08:50:37 UTC**。该时间由主钥创建字段加 key-expiration 间隔计算，尚未数学验签，也不是完整有效性判定。
- 已取得 MPC 原包签名声明时间为 2022-12-15。不能通过倒拨验签时间、忽略过期状态或默认采用历史有效性来自动接受这个包。若需要当前有效钥，应先取得同指纹的更新认证材料；若采用历史验签或 Debian 路线，须单独明确结论与时效范围。

### MPFR

- 同一原始公钥包含两个主钥，完整保留，不能以全包中的旧签名算法替代所选主钥判断。
- 旧主钥 `07F3DBBECC1A39605078094D980C197698C3739D` 为 DSA，8 个 UID，自签候选有 15 份 SHA-1；它不是本次原包签名声明的 issuer。
- 当前主钥 `A534BE3F83E241D918280AEB5831D11A0D4DB02A` 为算法 22 / EdDSALegacy，与维护者页面及原包签名声明一致；3 个 UID、1 个算法 18 子钥，共 12 个 packet。4 份自签候选均声明 SHA-256，UID 自签候选未声明 key-expiration 上限；这不证明当前有效或永不撤销。
- 固定版本页称其为 DSA 的文字与实际公钥 / 签名算法字段不同，保留差异；不据此换回旧 DSA 钥。

所持包未解析出 class `0x20` / `0x28` / `0x30` 的撤销签名，但未核验签名数学、未知渠道、最新状态或外部撤销者，不能声称无撤销。所有 `public_key_identity_accepted` 和 `cryptography_executed` 保持 `false`，`source_acceptance` 为 `not-assessed`。

## 下一步与执行边界

优先形成 **MPFR 当前主钥**的有限离线验签切片：在已固定的诊断工具环境中，保留原始完整包，按完整指纹选择当前主钥；逐项核对原始自认证及导入后的材料对应，验证固定原包的唯一强摘要签名，并加入原包正文篡改、错误 / 缺失主钥的负例。多 UID、历史认证与所选加密子钥不适配 musl 的单 UID / 两 Debian 角色 profile，不能直接复用其成功判定或修改旧方法绕过差异。不得隐式联网取钥、采用 ownertrust 或弱摘要兼容选项。

MPC 先补同指纹更新材料和完整身份页留存，或另行审阅明确的历史 / Debian 认证路线。当前公钥取得与结构诊断不授权改变过期、撤销或来源验收政策，也未把 MPC 的问题扩大为阻断 MPFR 材料准备。真实 GnuPG 诊断入口、精确资源和清理方案应完成后再执行；本轮没有运行该步骤。

其余四项依赖、发布构建关联、Rust 公钥与宿主库、kernel 和安装前置仍按[当前状态](../../status/current.md)推进。此次不改变产品实现、公共格式或许可证。

## 留存与验证

原始页面、公钥、成功 / 失败日志与路由范围保留在 `.tmp/mpc-mpfr-keys-ee917c7-20260916/`；另使用现有内容寻址工具归档至 `artifacts/source-inputs/mpc-mpfr-keys-ee917c7-20260916/`，其清单及恢复结果分别见 [manifest](mpc-mpfr-key-retention-manifest-2026-09-16.json)和[恢复记录](mpc-mpfr-key-retention-2026-09-16.json)。该增量与前两批本机归档互补，不包含完整仓库或验签工具 rootfs。

实际归档为 43 个路径、31 个不同对象、480,986 bytes；全部恢复并逐字节匹配。机器导出重算与留存的 240,940 bytes JSON 一致，`./scripts/check-repo.sh` 通过（1,173 个文件），`git diff --check` 通过。

```bash
python3 docs/records/rust-linux-input-review/check-mpc-mpfr-key-inputs.py
python3 docs/records/rust-linux-input-review/inspect-mpc-mpfr-key-inputs.py
./scripts/check-repo.sh
```

9 项合成测试通过，覆盖新旧主钥分离、到期字段不升级为有效性、无声明到期、缺失目标钥、错误 armor、秘密 packet、截断、非支持签名版本，以及弱摘要只作观察。它们不验证合成公钥或签名的数学正确性。没有重跑 Rust / CI、产品构建或容器。

Downloads 的 `aa13d7c` 备份未改，本批与 MPC / MPFR 原包增量均未加入该包；没有上传、push 或后台进程。`ee917c7` 后产生的新记录与方法留在工作区，未再次提交。
