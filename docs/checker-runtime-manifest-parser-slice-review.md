# Checker runtime 两层业务 manifest parser 切片审阅单

状态：distribution / candidate 业务 manifest 的严格 Rust 消费路径已实现并通过本地门禁
审阅日期：2026-09-02

## 目标与结论

本切片承接[严格 USTAR 切片](checker-runtime-rust-ustar-slice-review.md)，实现 [ADR 0010](adr/0010-checker-runtime-payload-durable-registration.md) 与 [ADR 0011](adr/0011-checker-runtime-launcher-installation-and-activation.md) 已冻结的两层 manifest inventory / identity 复核。实现只消费 `validate_ustar` 已形成的 extraction-free 外层成员及其父归档身份，再从外层原始 `checker-payload-candidate.tar` 切片严格验证内层 USTAR；不提取或写盘任何成员。

`radishaxiom-checker-runtime` 新增唯一公开入口 `validate_payload_manifests`。成功结果同时保留：

- 外层 `radishaxiom-checker-runtime-distribution-manifest` `0.1` 与内层 `radishaxiom-checker-payload-retention-manifest` `0.1` 的原始长度 / SHA-256；
- checker implementation / source / version / `go1.26.7` / `darwin-arm64-v8.0` / Mach-O 目标身份；
- 每层有序 content 的 path、role、mode、长度和原始 SHA-256；
- 与当前 registration record 中 distribution、candidate archive、两份 manifest、distribution acceptance、build provenance、payload acceptance 和 executable artifact 的逐项绑定。

`ValidatedArchiveMember` 同时保留父归档长度与 SHA-256。因此业务入口能确认调用方传入的外层成员确实来自登记的 distribution，并确认从外层借用的内层 candidate 字节等于登记的 candidate archive；不把成员摘要集合误当成父归档身份。

## 严格格式与失败关闭

两份 manifest 均先执行 64 KiB 前置上限、128 层 JSON 深度上限和当前 Rust canonical ASCII JSON 子集检查，再验证闭合对象形状。重复 / 未知 / 缺失字段、非规范 member 顺序或空白、number / null、非规范 escape 和尾随 JSON 均拒绝。

业务验证继续要求：

- 精确 format / `0.1`、非 `latest` 的闭合版本身份、当前 checker implementation、`go1.26.7` 和 registration source / version / target；
- `ustar`、固定 header profile，以及内层四成员 / 外层六成员的精确 `member_order`；
- candidate 的三项 content 必须依次为 build provenance、payload acceptance 与 `0755` checker artifact；
- distribution 的五项 content 必须依次为 candidate archive、distribution acceptance、Go LICENSE、Go PATENTS 与 Checker LICENSE，全部为 `0644`；
- 每项 manifest 声明的十进制长度和小写 `sha256:` 必须等于已经验证的实际成员；两层规范化身份必须一致。

USTAR header 验证成功不能替代这些检查。测试专门构造了 USTAR 完全有效但 manifest 含未知字段、非 canonical 空白、错误 source、内容摘要、header profile 或 member order 的归档，业务入口全部失败关闭。registration 中的父归档、manifest、acceptance 或 executable 身份漂移也分别在使用前被拒绝。

## 验证与停止线

测试只在内存中构造小尺寸合成 candidate / distribution USTAR 和合成 registration 绑定；没有读取、下载或安装已发布 Release asset，没有使用真实产品根，也没有执行 checker。完整 Cargo、Python oracle、生成契约、schema、仓库与差异门禁的实际结果统一记录在[当前状态](status/current.md)。

本切片不解析 build provenance、payload acceptance 或 distribution acceptance 的业务正文，不形成法律结论，也不实现 fetch、staging 写入、Mach-O 内容复核、installation coordinator、spawn / isolation、qualification 判定或 activation。manifest / archive 成功只说明所给字节满足当前两层 packaging 与 registration identity，不能升级 payload acceptance、四态结果、runtime companion 或 active 状态。

下一连续本地切片进入 qualification / invocation 共用的 immutable spawn plan 与外层 result-or-failure 排他状态机。真实 asset fetch / install、checker 执行、产品绝对根、系统隔离验证、qualification 与 `registered-inactive -> active` 继续分别验证、分别授权。
