# AX-B01 P5 Darwin arm64 release 候选与接受接线

日期为 2026-11-07（Asia/Shanghai）。本记录面向生产工具审阅者和回执消费者，覆盖一次 Darwin arm64 候选构建、实际执行及 P5 接受记录验证。候选基线为 `cee27dc` 加本批源文件，精确构建材料以候选清单的原始字节为准。

## 制品及构建

[候选清单](2026-11-07-ax-b01-p5-pairing/darwin-release-candidate.jcs)的原始 SHA-256 为 `7fe8afc6fbc3416264069a263348a4d2a25d2ba33619a5d30030f1a21e417ff4`。实际 Mach-O 为 1,339,024 bytes，SHA-256 为 `c860a38f2f5b182b7eca0f481d0e3c47e1f4207ff10dc7de7b6bfad1af350d0e`，UUID 为 `94F70D35-1F25-3452-8E9D-7AC7AC9698B0`。制品、原始链接观测和标准库版权文件在清单指定的本机忽略目录留存。源快照临时目录已清理。

- [构建观察](2026-11-07-ax-b01-p5-pairing/capture_darwin_release.py)从 88 项冻结材料构建，其中 71 项由 Cargo 依赖清单报告。使用 Rust `1.97.1`、显式 `aarch64-apple-darwin` 和 `release`，清理继承环境并固定 `--locked --offline`。Cargo 的目标依赖树只有本仓的 `radishaxiom-ir` 和 `radishaxiom-digest`。源集合、依赖清单及已选工具文件通过前后重核。
- Clang 和实际链接器固定到 Xcode 27.2（27B52），链接器实参、依赖文件、文件轨迹和 map 按摘要留存。Mach-O 的 `LC_BUILD_VERSION` 为 macOS、SDK 27.2、最低 14.0、LD 27106.1。依赖记录列出 42 个 SDK stub 路径，对应 40 个实际文件。清单记录解析后文件的摘要、SDK 设置和 `libSystem` stub。实际运行仅在 macOS 27.0.1（26A434）观察，14.0 是链接设置。
- 链接器实参引用 19 个 Rust `.rlib`，逐个对回精确 Darwin `rust-std 1.97.1` 归档。链接 map 中贡献对象的归档为其中 9 个，完整名称和摘要见清单。归档为 29,286,636 bytes，首次请求超时后按 HTTP 206 拼接剩余字节，整包匹配既有发布摘要 `a4895f5c6995e83cab8687e46b14324592398049def71ce75ca308c981cf200d`。观察到的链接输入仅为本次对象文件、Rust 归档及 SDK stub。 [标准库接受记录](../../contracts/toolchain-payload-acceptance-v0.1/records/rust-std-1.97.1-aarch64-apple-darwin.acceptance.json)
- `otool -L` 的直接依赖为系统 `libSystem.B.dylib`。一次精简环境的实际 dyld 启动观察记录了候选 UUID 和 80 个系统映像的路径与 UUID。SDK stub 属于构建侧，系统映像由宿主提供。当前证据范围是一次构建的已观测链接输入和一次宿主加载，生产调用仍需事前固定宿主与实际启动路径。

## 来源、许可与范围

本仓两项 Rust crate 使用根 [LICENSE](../../LICENSE)。Cargo 和 rustc 可执行文件分别与已登记的同平台归档成员逐字节相等，实际构建记录中的 `librustc_driver` 摘要与[此前逐块核对](2026-11-07-linux-channel-l3-rust-source-readback.md)一致。安装目录的 `COPYRIGHT-library.html` 也与 rustc 归档成员相等，已按清单摘要随本地构建材料保留。标准库发布根声明 `MIT OR Apache-2.0`，库版权清单还单列第三方组件及其归属。拟交付范围仅为工具可执行文件和适用告知材料，Apple SDK、编译工具和系统库由生产宿主提供。制品对外分发前须组装并审阅实际随附告知材料。 [Cargo 组件记录](../../contracts/toolchain-payload-acceptance-v0.1/records/cargo-1.97.1-aarch64-apple-darwin.acceptance.json) · [rustc 组件记录](../../contracts/toolchain-payload-acceptance-v0.1/records/rustc-1.97.1-aarch64-apple-darwin.acceptance.json) · [Rust 上游版权说明](https://github.com/rust-lang/rust/blob/8bab26f4f68e0e26f0bb7960be334d5b520ea452/COPYRIGHT)

## 回执验收

用上述实际候选分别运行观察路径和显式接受测试路径。两条路径各有 7 份回执通过独立规范字节重建、Schema 检查和 Rust 读回。场景为 `base`、`boundary`、`invalid`、封套预算不足、黄金缺失、错案黄金、刚好达到预算。显式接受测试使用临时合成记录和独立传入的测试摘要，检查了缺失或错误摘要、替换来源字节、篡改工具与作用范围、重新计算摘要的非规范接受记录，以及两种入口交叉读回。错案黄金替换、伪造 P6 开门和旧版回执也被拒绝。 [独立复核入口](2026-11-07-ax-b01-p5-pairing/verify_receipt.py)

```bash
python3.14 -I -B docs/records/2026-11-07-ax-b01-p5-pairing/verify_receipt.py "$candidate" \
  --schema contracts/pipeline-artifacts-v0.2/schemas/axiom-pipeline-receipt.schema.json
python3.14 -I -B docs/records/2026-11-07-ax-b01-p5-pairing/verify_receipt.py "$candidate" \
  --schema contracts/pipeline-artifacts-v0.2/schemas/axiom-pipeline-receipt.schema.json --exercise-acceptance
```

本批生产状态为 `not-accepted`。正式接受待项目所有者审阅这个精确制品、构建来源和宿主信任范围，由受信配置提供[接受记录](../../contracts/pipeline-artifacts-v0.2/README.md#p5-工具接受记录-v01)的摘要，并在受保护的实际启动路径重跑上述场景。候选清单摘要用于绑定构建来源。正式接受记录及其受信摘要尚未签发，P6 继续执行原有义务与保证门控。
