# Checker runtime Rust installation receipt 切片审阅单

状态：零第三方依赖的纯内存 canonical installation receipt 已实现并通过本地门禁
审阅日期：2026-08-31

## 目标与结论

本切片承接[严格 USTAR 切片](checker-runtime-rust-ustar-slice-review.md)，实现 [ADR 0011](adr/0011-checker-runtime-launcher-installation-and-activation.md) 与 canonical launcher policy 已冻结的 `radishaxiom-checker-runtime-installation-receipt` `0.1`。实现只从已经严格解析的 `LauncherPolicy`、`RegistrationRecord`、安装时间和 verifier 身份构造 canonical bytes，或对给定 bytes 执行闭合重读；不持有网络能力，不读取或写入产品安装根，不创建 staging / slot，不执行 checker，也不推进登记状态。

`radishaxiom-checker-runtime` 新增并公开：

- `InstallationVerifierIdentity`：类型化保存 verifier 的 `identity`、`name` 与 `version`，其中 identity 必须为小写 `sha256:`；
- `build_installation_receipt`：只接受 `registered-inactive` 记录，核对 immutable provider release / asset 与 distribution 的名称、长度和摘要一致，再形成唯一 canonical receipt；
- `parse_installation_receipt`：拒绝非 compact canonical JSON、未知或缺失 member、格式 / 版本 / 域漂移、document digest 漂移，以及摘要正确但与登记事实不一致的 receipt；
- `InstallationReceipt`：只暴露 canonical bytes、document digest、安装时间、slot 相对身份和 verifier，不携带绝对安装路径或环境值。

成功只说明 receipt 字节与调用方提供的当前登记快照严格一致。它不说明 distribution 已下载或解包、binary 已写盘、slot 已原子发布、receipt 已持久化、qualification 已执行，亦不把 `registered-inactive` 提升为 active。

## 闭合身份与失败边界

receipt 以 `radishaxiom.checker-runtime-installation-receipt.v0.1` 域摘要绑定：

- registration record ID 与 record digest；
- checker implementation、source、version 与 toolchain；
- binary artifact 和 distribution 的 byte length / raw SHA-256；
- provider repository、release ID / tag / target commit 与 asset ID / name；
- `goos / goarch / goarm64 / executable_format` 完整目标键；
- 由目标键和 distribution digest 唯一形成的 `slots/...` 相对身份；
- installation verifier 身份、UTC 秒级时间与 `installed-inactive` 状态。

构造前还会拒绝 active / revoked 登记、可变或 draft release，以及 provider asset 与 distribution 的 digest、length 或 filename 漂移。receipt 不记录 launcher policy digest；该身份依照既有 policy 由后续 qualification record 绑定，不在本切片擅自扩展公共 receipt 格式。

## 跨实现黄金结果

Python 参考实现与 Rust 对当前真实 `registered-inactive` record、`2026-08-30T10:00:00Z` 和合成 verifier 形成完全相同的结果：

| 项目 | 值 |
| --- | --- |
| canonical byte length | `1797` |
| raw SHA-256 | `sha256:54c1dad27b5f35efcc706a8599dd1b23798de9cda1ce313b48bbec798efe53c1` |
| document digest | `sha256:7a53b34f39059e97363a87d33532ee265cf4faa3d438a22a709f25ee47170ac2` |

两侧都将这组值作为回归黄金结果。它绑定当前登记记录，不是一次真实安装 receipt，也不得被复制到未来不同时间、verifier、登记或 distribution 的 slot。

## 验证与下一停止线

精确 `+1.97.1-aarch64-apple-darwin` 下的格式、Clippy、locked / offline test、metadata 与 dependency tree 继续作为 Rust 门禁；Python launcher oracle、checker runtime payload 生成复核、仓库级检查与差异卫生继续作为跨实现和仓库门禁。通过这些测试只说明实现满足所测字节与身份边界，不构成形式证明或安装证据。

下一连续实现进入 `checker-runtime-store-v0.1` 的最小事务切片，优先形成纯接口与 owned staging / target lock / exclusive publish 的可测试状态机；绝对产品根仍由未来产品适配层注入。真实 immutable asset fetch / install、业务 manifest parser、result consumer、subprocess / isolation、qualification、激活、push 与远程状态继续分别验证、分别授权。
