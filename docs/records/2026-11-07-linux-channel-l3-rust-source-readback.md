# 2026-11-07：L3 两项 Rust 工具来源核对

日期为 2026-11-07（Asia/Shanghai）。基线为干净的 `dev` / `e3d41f2`，本地领先 `origin/dev` 一笔。批次限 90 分钟，只核对[前次决定](2026-11-07-linux-channel-l3-input-acceptance-review.md)中的 `rustup` 发布字节和 `librustc_driver` 组件归属。

## 结果

| 对象 | 实际对应与判定 |
| --- | --- |
| 宿主 `rustup` | `/Users/luobo/.cargo/bin/rustup` 是 ARM64 Mach-O，版本为 `1.29.0 (28d1352db 2026-03-05)`，11,053,296 bytes。SHA-256 `aeb4105778ca1bd3c6b0e75768f581c656633cd51368fa61289b6a71696ac7e1` 与 Rust 官方同版本、同平台 `rustup-init.sha256` 的 `./rustup-init` 条目一致。本轮证据为官方 HTTPS 端点给出的 SHA-256 与本机字节的对应。 [官方发布](https://blog.rust-lang.org/2026/03/12/Rustup-1.29.0/) · [官方 ARM64 校验文本](https://static.rust-lang.org/rustup/archive/1.29.0/aarch64-apple-darwin/rustup-init.sha256) |
| 实际加载的 Rust driver | 清空继承环境后直接调用固定 sysroot 的 `rustc --version --verbose`，确认 `1.97.1 (8bab26f4f 2026-07-14)`、host `aarch64-apple-darwin`。`DYLD_PRINT_LIBRARIES=1` 的 driver 映射唯一指向 sysroot 的 `lib/librustc_driver-e03ed1db822dfa4c.dylib`，UUID 为 `C2FCDA42-D98F-3763-8010-CA527981215A`。固定组件中的 `rustc/manifest.in` 恰有一条 `file:lib/librustc_driver-e03ed1db822dfa4c.dylib`。对应普通文件成员与加载路径上的文件模式均为 `0644`，207,258,056 bytes 逐块相等，SHA-256 均为 `57f6b5280f218ed25ba6b7e4bc1d74da3ac8e4fd85bee1b8982ad4114d757c11`。 [既有 Darwin 组件接受](../../contracts/toolchain-payload-acceptance-v0.1/records/rustc-1.97.1-aarch64-apple-darwin.acceptance.json) |

Darwin `rustc-1.97.1-aarch64-apple-darwin.tar.xz` 整包为 68,127,952 bytes，SHA-256 `6076cad38ccabaa24325f26a74080a363a2633a9cd34c473a8977255d8a593cb`，与[留存发行清单](rust-linux-input-review/channel-rust-1.97.1.toml)和既有接受记录相同。重跑[原归档检查器](../../scripts/inspect-toolchain-tar.py)后，结果与[既有检查结果](../../contracts/toolchain-payload-acceptance-v0.1/observations/rustc-1.97.1-aarch64-apple-darwin.inspection.json)逐字节相同。归档成员仅流式读取，前后重算整包和本机 driver 摘要，无文件释放到工具链。 [官方组件归档](https://static.rust-lang.org/dist/2026-07-16/rustc-1.97.1-aarch64-apple-darwin.tar.xz)

## 实际获取与原字节引用

两项获取均使用本机 `/usr/bin/curl`，禁用用户 curl 配置，限定官方 HTTPS 端点和字节上限。校验文本 HTTP 200，80 bytes。整包请求在 300 秒达到超时，退出码 28，已取得 60,909,076 bytes。保留前缀原字节，只请求剩余 7,218,876 bytes。续传为 HTTP 206，`Content-Range: bytes 60909076-68127951/68127952`，拼接后整包长度与 SHA-256 均通过才读取归档。

本机原件、获取日志和复核方法保存在忽略目录 `.tmp/l3-rust-source-review-20261107.Li8ySR0A/`。以下 SHA-256 供原字节复核。

| 文件 | SHA-256 |
| --- | --- |
| `rustup-init.sha256` | `9bd78459b78e1f8a793b27162bd51dd6810ca2978b16009580550737f7f89e91` |
| `rustc-1.97.1-aarch64-apple-darwin.tar.xz.attempt-1.prefix` | `2ec317add0874b2a79c90b18a61afe74811add9eb5f58ceec61f126122fac464` |
| `rustc-1.97.1-aarch64-apple-darwin.tar.xz.tail` | `08b6b4b2f24226ab88119928c2a715278b854482750f3a42b52759c0403e9eb3` |
| `rustc-dyld.stderr` | `c1e5ea6217dcca32584cde60931c6e233ebc6dafd7c6e6604786a1a87abd57d8` |
| `rustc-inspection.json` | `9028d3e373e4a3b35938e0d7961a51248ddc892cbadd027561264218bbc1b0a9` |
| `check-rust-identities.py` | `dee724133c023499342b0b6085d09b597c393019fde6baca35c4de61b46e03ff` |
| `comparison.json` | `9ee4a760be30a6a5b7114c19959c17e5a96f8d80412d0f4dce71d261615dd941` |

先按原接受记录指定的 profile 和摘要运行 `inspect-toolchain-tar.py`，用 `cmp` 核对原观察。再从仓库根用 `python3.14 -I -S -B <任务目录>/check-rust-identities.py <任务目录>` 复核发布选择、组件 claim、实际加载路径和逐块比较。两种方法均通过。Rustup 仅执行现有文件的版本读取，固定工具链并设置 `RUSTUP_AUTO_INSTALL=0`。

## 剩余缺口

L3 总体仍为 **`not-accepted`**。两项 Rust 字节对应已经查清。Rustup 校验继续信任官方 HTTPS 发布端点，Darwin 组件沿用既有接受范围。本轮没有重验分离签名、从源码复现发布二进制或验证实际安装事务。剩余输入审阅限于 target 发布清单的信任范围、Python 构建与内嵌材料、Apple Git 选择约束、两份 Cargo 解析数据的来源与许可、以及固定 macOS / dyld / libproc 的宿主信任。具体边界沿用[前次审阅](2026-11-07-linux-channel-l3-input-acceptance-review.md#决定)。

target 安装保持阻断。本批只进行了两个精确官方对象的获取、宿主版本探针和只读核对，没有预填 rustup cache、安装 target、生成真实 v0.2 root、构建 Linux 制品或执行 solver。
