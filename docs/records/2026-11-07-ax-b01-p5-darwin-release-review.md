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

初次接线完成时，生产状态为 `not-accepted`。正式接受要求项目所有者审阅精确制品、构建来源和宿主信任范围，由受信配置提供[接受记录](../../contracts/pipeline-artifacts-v0.2/README.md#p5-工具接受记录-v01)的摘要，并通过受保护的实际启动路径重跑上述场景。实际决定见[本机生产接受](#本机生产接受)。

## 生产接受前复核

基线为 `dev` 的 `e9ac904`。重读了清单的 37,539 bytes 与上述 Mach-O 的 1,339,024 bytes，长度、SHA-256 和 arm64 UUID 均吻合。Apple 工具的严格签名检查通过，签名为链接器生成的 ad hoc 签名。五份原始链接记录和版权文件匹配清单。88 项源材料、源集合摘要、71 个编译器输入的包含关系、9 项工具和 SDK 材料、42 个 SDK stub 路径对应的 40 个文件、19 个已安装 Rust 归档、9 个实际贡献归档及标准库接受记录均已重核。整包与归档成员的对应沿用原构建时的核对，本轮在候选留存目录及检查的本机缓存中未找到 Rust 标准库原归档。未重建候选。

### 宿主信任范围

宿主范围限当前本机的 native Darwin arm64，Darwin `27.0.0`、macOS `27.0.1`（`26A434`）。启动入口核对 `SystemVersion.plist` 和 `/usr/lib/dyld` 的原始摘要、当前 shared cache UUID `c284a291-b68b-3d0d-a1a0-3f866f87efdc`，并逐次核对实际暂存路径、清单绑定的制品 UUID 和 80 个系统映像的路径及 UUID。当前根卷报告 sealed、read-only。UUID 用于识别实际装载集合，系统映像未逐文件验收。

本地复跑信任该宿主的 Apple 启动系统、内核、dyld、系统共享缓存、文件系统权限和进程语义，及项目所有者控制的 root / 同 UID 进程。独立复核还信任已审阅的脚本、固定 Schema 和本机 Python `3.14.5` 安装。入口核对 Python 可执行文件摘要，Python 标准库、`ctypes` 和现有 `jsonschema 4.26.0` 及其依赖在本次有限宿主信任内。脚本和解释器由受信操作者选定并保持稳定。构建期 Xcode SDK、编译器和 Rust 归档用于来源复核，运行期依赖以实际装载集合为准。

受保护路径的保证依赖操作者维持上述边界，尤其是没有能写入暂存目录、启动器、解释器、复核输入或审批配置的不受信同 UID 或管理员进程。换宿主、更新系统或换启动链时需重审。范围限本机 AX-B01 的 P5 夹具检查和回执复核。系统加载观察与进程超时不提供产品隔离或运行资格。

### 受保护启动与独立复跑

[受保护入口](2026-11-07-ax-b01-p5-pairing/verify_darwin_release.py)使用固定清单摘要和精确留存路径读取制品，将已核对的原字节独占写入 `/private/tmp` 下新建的 `0700` 目录，以 `0500` 权限启动该副本。每次运行都使用绝对路径、私有工作目录和白名单环境，检查启动前后的目录与文件标识、权限和制品摘要。dyld 输出必须报告暂存副本的精确路径、制品 UUID 和清单中的完整系统映像列表。错误或缺失的装载观察阻断回执交付。复跑末尾重核留存原件、宿主和适用的受信配置，通过后才输出整批结果。

独立 Python 路径继续重建规范回执原字节、校验 Schema 并调用 Rust 读回。用下列命令执行本机观察复跑，默认生成 `not-accepted` 的回执：

```bash
pair=docs/records/2026-11-07-ax-b01-p5-pairing
p5_python="$HOME/.local/share/mise/installs/python/3.14.5/bin/python3.14"
/usr/bin/env -i PATH=/usr/bin:/bin LANG=C LC_ALL=C "$p5_python" -I -B "$pair/verify_darwin_release.py"
```

实际观察七案通过规范字节重建、Schema 与 Rust 读回。基础、边界、恰好达到预算均为 `completed`，非法输入为 `invalid`，预算不足为 `resource-exhausted`，黄金缺失与错案黄金为 `error`。篡改黄金、工具角色、接受声明和 P6 门控，以及跨版本回执均被拒绝。新增[本机回归检查](2026-11-07-ax-b01-p5-pairing/test_verify_darwin_release.py)覆盖清单与制品漂移、同字节文件替换、错误实参及实际启动路径、缺失装载日志、宿主 cache UUID 不符、缺失或错误接受摘要和不受保护的配置。合成批准通过同一受保护启动和七案独立复核，合成来源与真实构建清单不同。

## 本机生产接受

2026-11-07，项目所有者明确批准 SHA-256 为 `c860a38f2f5b182b7eca0f481d0e3c47e1f4207ff10dc7de7b6bfad1af350d0e` 的精确 Mach-O，以及[本机 macOS 27.0.1（26A434）原生 arm64 宿主范围](#宿主信任范围)。复核了制品、原始构建清单和宿主指纹。正式[接受记录](2026-11-07-ax-b01-p5-pairing/darwin-tool-acceptance.jcs)保留审阅草案的 1,131 个原始字节，SHA-256 为 `9f754b227607ccd06d26711eba06064946eec147813736662a6be249683dabbe`。记录按既有 v0.1 契约绑定 Mach-O、原始构建清单、固定 P5 规则、AX-B01 IR、任务、工具 ID、调用方式、角色及预算。宿主范围由受保护入口执行。

获批后在仓库和暂存目录之外独占创建了 `~/.config/radishaxiom/p5/acceptance.sha256`，目录为 `0700`，配置为 `0400` 的单链接普通文件，内容为上述记录摘要加 LF。受保护入口从当前账户的系统登记 home 读取此配置，核对祖先目录的所有权、权限、ACL 和真实路径，并在复跑前后重核摘要。配置缺失、摘要错误、记录范围不符、制品或宿主漂移、实际启动路径不符均阻断。

在上述观察命令后加 `--acceptance-record "$pair/darwin-tool-acceptance.jcs"` 复跑。受保护入口以退出码 0 完成实际七案，每份回执均通过独立规范字节重建、Schema 与 Rust 读回，工具状态为 `accepted`。错案黄金替换、篡改工具角色或接受声明、伪造 P6 开门、跨版本与跨接受入口读回均被拒绝。

| 场景 | P5 结果 | 回执原始 SHA-256 |
| --- | --- | --- |
| `base` | `completed` | `4eccb2031b45a288bcac129608770a9229fdb8cb7e22bab40330367527308982` |
| `boundary` | `completed` | `586f8c019143003e048e95a41569507da7c06eea66c3ddcd863cb6c88b540efe` |
| `invalid` | `invalid` | `6b5013e32c0cdd5ca9d1576d3afc53e15439ec9175ee96901b93d58884d61b88` |
| `resource` | `resource-exhausted` | `a769551ee14585b46874bc814ffecfdf491cf94d9f611fb8decdcac940244ae9` |
| `missing-golden` | `error` | `74aa4991c8a80b4ee4e14f0a720fb62a1bd295cc1e96c4225b1a73c159f1755e` |
| `wrong-golden` | `error` | `19963ad42b3f6e1fc3b5cb2c46a70a43b842d019b87bf81f3064749303cd1961` |
| `boundary-exact` | `completed` | `c6aec80c0bca90d07bc017d1c65682d2dc1bf10e686b48193aff0daffbfce7b3` |

本次接受限上述精确制品、宿主和受保护入口上的本地 AX-B01 P5。所有回执的 P6 门控为 `closed / p6-not-evaluated`，Evidence 为 `not-assembled`。
