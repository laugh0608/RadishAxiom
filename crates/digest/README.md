# 内部 SHA-256

从 `radishaxiom-checker-runtime` 提取的既有标准库实现（基线 `231a0ed` 的 `crates/checker-runtime/src/sha256.rs`），供 runtime 与 IR 的实际内容寻址共用。沿用仓库自有代码的 Apache-2.0 许可证，不引入第三方源码。只提供原始 digest 和小写十六进制编码，不承载 IR 域分离、JSON、类型语义或运行状态。独立 Go checker 不依赖此包。

Rust 2024、`publish = false`、禁止 unsafe；无第三方依赖、build script、过程宏、FFI 或安装步骤。提取保留原算法及 NIST / 填充边界 / 百万 `a` 测试向量。摘要一致只绑定字节，不证明语义正确或来源可信。

复用避免两个生产组件各自维护 SHA-256，但不会形成独立证明路径。测试不替代密码学实现审计；SHA-256 碰撞抗性仍为外部假设。
