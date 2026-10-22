# 内部 SHA-256

从 `radishaxiom-checker-runtime` 提取的既有标准库实现（基线 `231a0ed` 的 `crates/checker-runtime/src/sha256.rs`），供 runtime 与 IR 的实际内容寻址共用。沿用仓库自有代码的 Apache-2.0 许可证，不引入第三方源码。只提供原始 digest 和小写十六进制编码，不承载 IR 域分离、JSON、类型语义或运行状态。独立 Go checker 不依赖此包。

Rust 2024、`publish = false`、禁止 unsafe；无第三方依赖、build script、过程宏、FFI 或安装步骤。提取保留原算法及 NIST / 填充边界 / 百万 `a` 测试向量。摘要一致只绑定字节，不证明语义正确或来源可信。

复用避免两个生产组件各自维护 SHA-256，但不会形成独立证明路径。测试不替代密码学实现审计；SHA-256 碰撞抗性仍为外部假设。

`Sha256::new()` / `update(&[u8])` / `finalize()` 提供增量输入，复用原压缩函数；旧 `digest` 与 `digest_hex` 委托同一实现。状态仅保留压缩状态、长度和一个 64-byte 部分块，不积累完整输入。`finalize` 消费状态；空块不改变摘要。

`update` 返回 `Result<(), LengthOverflow>`，累计输入超过 SHA-256 的 `2^64 - 1` bit 长度编码能力时显式拒绝，并保持原状态不变；可接受的完整 byte 长度至多 `u64::MAX / 8`。旧便捷接口保留超长输入时的显式 panic。验证包括既有 NIST / 百万 `a`、非均匀固定摘要、填充和块边界、所有二段切分与空块、溢出原子性；host 另核对原容量 query 多种块长与既有固定摘要。
