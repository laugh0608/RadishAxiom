# Toolchain & Adapter Identity Registry v0.1

本目录把 ADR 0004–0008 已冻结的生产工具链、独立 checker 工具链、验证后端、目标运行时和执行 profile 物化为可复算身份清单。它固定：

- Rust `1.97.1` 与 Rust 2024 edition 的首个生产工具链基线；
- Go `go1.26.7` 与六平台独立 checker 构建基线；
- cvc5 `1.3.4` 六个平台的官方 non-GPL static 候选制品；
- Node.js `24.19.0` 六个平台的官方归档候选制品；
- cvc5、Node、production pipeline、Rust build、Go checker build 与独立 checker 的稳定 profile 身份和禁止 fallback 边界；
- 官方元数据来源、publisher 记录的 SHA-256、源码归档、依赖审阅目标、许可证来源和 profile 对应 ADR 的原始摘要绑定。

`registry.json` 与 `schemas/` 由生成器维护。所有目标制品当前都明确标为 `not-downloaded`、`not-performed` 和 `not-accepted`：publisher 页面上的摘要只表示元数据已经登记，不表示本项目已下载原始 payload、重算摘要、验证签名、检查 archive 内容或接受完整许可证清单。Rust 制品和 cvc5 source 的摘要还保持 `pending-publisher-capture`，不能用于构建门禁。

Rust 首次实现选择 `1.97.1`，不自动采用 2026-08-20 刚发布的 `1.98.0`。`1.97.1` 是已经发布一个月且修复已知 LLVM miscompilation 的 stable patch；这只是首个可审阅基线，不形成未来 stable release 的兼容承诺。

生成：

```bash
python3 scripts/generate-toolchain-adapter-identities.py --write
```

只读校验：

```bash
python3 scripts/generate-toolchain-adapter-identities.py --check
```

除本 README 外，本目录文件均由生成器维护，不接受手工修改。生成器只校验本仓库登记内容、排序、引用、摘要形状、平台覆盖和“未验收”停止线；它不是下载器、签名验证器、SBOM / 许可证扫描器、Rust / Go 构建器、cvc5 adapter 或 Node launcher。
