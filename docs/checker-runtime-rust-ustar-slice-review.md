# Checker runtime Rust 严格 USTAR 切片审阅单

状态：零第三方依赖的 extraction-free 内外层 USTAR 清单已实现并通过本地门禁
审阅日期：2026-08-31

## 目标与结论

本切片沿用 [ADR 0011](adr/0011-checker-runtime-launcher-installation-and-activation.md) 与 [ADR 0012](adr/0012-product-checker-runtime-host-and-persistence-interface.md) 的产品边界，把真实安装前必需的两层 archive inventory 收敛为一个纯内存、无副作用的 Rust 原语。它不读取网络或文件系统，不释放成员，不创建 staging / slot / receipt，不执行 checker，也不改变 `registered-inactive` 或 active 状态。

`radishaxiom-checker-runtime` 新增并公开：

- `ArchiveMemberExpectation`：调用方显式提供相对路径、`0644` / `0755` mode、原始长度和 `sha256:` 身份；构造时即拒绝不可移植路径、危险组件、未知 mode 和非法摘要；
- `validate_ustar`：只在完整 archive 字节与闭合期望清单同时给出时工作，按期望基数有界解析并返回借用原始成员切片的 `ValidatedArchiveMember`，不提取、复制或写盘；
- `CHECKER_PAYLOAD_CANDIDATE_MEMBER_ORDER` 与 `CHECKER_RUNTIME_DISTRIBUTION_MEMBER_ORDER`：分别固定当前内层四成员和外层六成员顺序，但不以名称常量替代 manifest、长度或摘要验证。

成功只表示这批输入字节满足当前 USTAR header profile 与调用方提供的精确清单。它不说明 retention / distribution manifest 的 canonical JSON、字段身份或相互绑定已经解析，也不把 archive digest 升级为 payload acceptance、installation receipt、runtime companion 或 active runtime。

## 严格字节边界

parser 对每个 512-byte header 执行 unsigned checksum 复算，并按 Checker Go packer 的确定性 profile 重建 header 后逐字比较。当前只接受：

- `ustar\0` / `00`、显式普通文件 typeflag `0`；
- uid / gid `0`、Unix epoch mtime、空 uname / gname、空 linkname、device major / minor `0`；
- canonical octal 数字字段、portable ASCII 相对路径和规范 USTAR name / prefix 分割；
- `0644` 或 `0755` 的期望 mode、精确 size、成员 SHA-256、成员顺序和唯一名称；
- 全零成员 padding，以及 archive 末尾恰好两个全零 block。

绝对路径、`\\` 根路径、`.` / `..` / 空组件、非 portable 字符、重复或未知成员、错误顺序、base-256 / 非规范数字、NUL regular type alias、硬链接、符号链接、device、FIFO、PAX / xattr、未知 type、header profile 漂移、checksum 漂移、截断、非零 padding、缺少或多余 trailer 全部失败关闭。archive 即使总体可被宽松 tar reader 接受，也不能绕过本 profile。

## 跨实现 oracle 收口

现有 Python 合成 USTAR helper 原先把 `devmajor` / `devminor` 留为全零字节；Checker 的 Go `archive/tar` 确定性 USTAR 会把零值写为 canonical octal 字段。Rust 的逐字 header 重建首次暴露了该 fixture 漂移。本轮把 Python helper 修正为与 Go packer 相同的字段，并让 Python validator 同样重建 header；这只修正合成 oracle，不修改已发布 archive、机器契约或公共格式。

Python 重新产生的等价合成清单黄金值为：

| 归档 | 成员数 | 字节数 | 原始 SHA-256 |
| --- | ---: | ---: | --- |
| 内层 candidate | 4 | 5,120 | `sha256:d8c51c18196507d868816a2456b24a9fb756286e87f6aa124bccc806173782c2` |
| 外层 distribution | 6 | 11,776 | `sha256:d5ce0e3a00d7a66366c152257d54f71957778c39d08315b7ca65cd22dd8dd424` |

Rust 测试独立重建相同字节和摘要，并从外层借用 `checker-payload-candidate.tar` 原始切片后再次验证内层清单。黄金值只属于合成 fixture，不得替代当前已登记 Release asset 的真实摘要。

## 验证与停止线

精确 `+1.97.1-aarch64-apple-darwin` 下的格式、Clippy、locked / offline test、metadata 与 dependency tree 继续作为 Rust 门禁；Python launcher oracle、checker runtime payload 生成复核、仓库级检查与差异卫生继续作为跨实现和仓库门禁。通过这些测试只说明实现满足所测闭合边界，不构成形式证明或真实安装证据。

后续状态：同日已按该停止线完成下一项[installation receipt 切片](checker-runtime-rust-receipt-slice-review.md)；`checker-runtime-store-v0.1` transaction、真实 immutable asset fetch / install、业务 manifest parser、result consumer、subprocess / isolation、qualification、激活、push 与远程状态仍分别验证、分别授权。
