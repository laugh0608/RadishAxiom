# 2026-11-07：L3 精确构建输入有限接受审阅

日期为 2026-11-07（Asia/Shanghai）。基线为干净的 `dev` / `7c9d14c`，L3 实现为 `bb9d963`。范围为已留存的唯一 target、既有工具与宿主解析、两份 Cargo 解析数据。采用两小时上限，遇到需要新来源链或新增信任决定的缺口即结束审阅。正式方案见 [L3 专题](../query/solver-linux-channel-l3.md)，现行顺位见[当前状态](../status/current.md)。

## 决定

本轮结论为 **`not-accepted`**。目标归档及 Cargo 解析数据的字节核对通过。安装器的发布身份、Python 构建来源与嵌入材料、Apple Git 的执行解析约束、Cargo 解析数据本身的来源与许可，以及固定宿主的剩余信任需要收口。单次 target 安装继续阻断，`build_ready=false`、`execution_ready=false`。没有生成安装回执、生产 `host-resolution`、`input-review.json`、外部 review pin 或真实 v0.2 root。

| 对象 | 实际观察 | 本轮判定 |
| --- | --- | --- |
| Rust `1.97.1` / `aarch64-unknown-linux-musl` | 重跑[既有只读方法](cvc5-control-plane-2026-11-01/inspect-channel-l3-inputs.py)，输出与[原观察](cvc5-control-plane-2026-11-01/channel-l3-input-observation.json)逐字节相同。29,062,284 bytes 的归档匹配发行清单及现有 multirust 清单的 target 投影，逻辑归档 7 目录 / 78 文件，组件恰有 66 文件 / 152,642,974 bytes。目标目录、组件清单、指定 cache 与 `.partial` 均缺席。 | 精确字节已核对。旧 SHA-512 分离签名结果沿用，公钥 SHA-1 自认证缺口保留。若采用已登记 Rust 发布清单作为这个额外 component 的有限信任终点，须明确记下该范围。 [签名边界](rust-linux-input-review/README.md#签名结果与信任缺口) |
| Target 材料及许可 | 既有方法重核 Rust source 原包、255 份选定文本与其中 6 份许可摘要。Rust 根许可、musl 1.2.5 的 libc 与五个 CRT、compiler-rt 的四个 CRT、compiler-builtins 与 libunwind 分列。 | 材料可复用。精确归档成员参与实际链接的归属仍待 L4 以 trace / map / why-extract 对账，分发判断留在其对应阶段。 [固定配方与许可](rust-linux-input-review/source-recipes-2026-09-10.md) |
| `rustup` installer | `1.29.0 (28d1352db 2026-03-05)` 和原文件摘要与 L3 方案记录一致。启动观察的加载库均属系统路径。签名元数据显示 ad hoc。 | 旧源码审阅支持该版本的预期 cache / transaction 行为。已安装文件仍缺发布方原包或校验材料与实测字节的对应，现有 Darwin 五组件接受范围也未覆盖 installer。需补此精确证据，或由所有者明确选择接受已安装的特定文件及其来源假设。 [原方案记录](2026-11-01-linux-channel-l3-review.md) |
| Cargo、rustc、LLD | 直调固定 sysroot 的 `cargo 1.97.1`、`rustc 1.97.1`、GNU flavor `LLD 22.1.6`。三个文件匹配原观察。`rustc` 的 `@rpath` 经 `@loader_path/../lib` 解析到同一 sysroot 的 `librustc_driver-e03ed1db822dfa4c.dylib`；此次启动观测的其他库在系统路径内。记录了 installed Rust / Cargo 许可材料摘要。 | 原 Darwin 组件接受作为来源起点。已绑定本机 driver 的实际字节，仍需将它对回固定 rustc component 的原始材料，或明确已安装树在一次构建中的信任范围。版本探针不覆盖真实编译、链接或任意动态加载。 [Darwin 组件既有接受](../checker-runtime-rust-first-slice-review.md#工具链来源审阅) |
| Python 和 `ctypes` | 采用 mise 中实际版本目录的 `3.14.5/bin/python3.14`。可执行文件与旧宿主观察摘要一致。清空继承环境后用 `-I -S -B` 导入标准库并解析系统符号，共盘点 65 个 Python 文件。观察范围内仅见系统共享库，`_ctypes` 为 built-in。留存安装的 Python `LICENSE.txt` 摘要。 | 本批没有发现能把实际可执行文件、标准库及内嵌 `_ctypes` / libffi 对应到固定发布制品与第三方许可清单的留存材料。mise backend 标识和 PSF 许可文本只覆盖各自声明范围。 [原 Python 身份观察](rust-linux-input-review/musl-verifier-environment-2026-09-12.md#宿主与运行库边界) |
| Git 与 Xcode | 现行检查器固定 `/usr/bin/git`。它的 Mach-O 链接 `libxcselect`；`xcode-select -p` 和 `xcrun --no-cache --find git` 指向 Xcode 27.2（27B52）内的 Git。直接运行该解析结果为 `2.54.0 (Apple Git-157)`，启动观察只有系统库。Apple Git 的代码签名元数据显示 Apple 签名链。 | 入口摘要与实际程序分别绑定。探针直接运行解析结果，实际包装器运行入口，仍需在限定宿主信任下核对入口到实现的选择关系，并规定 selector / Xcode / 实际程序漂移时停止。需要将精确 Xcode 分发及 Git 许可材料纳入审阅。先从交互 PATH 看到的 Homebrew Git 及其 PCRE2 / gettext 不属于此候选。 [固定工具约束](../../scripts/check-linux-channel-inputs.py) |
| OS / dyld / libproc | macOS `27.0.1`（`26A434`）、Darwin `27.0.0 arm64`。记录 `SystemVersion.plist`、`/usr/lib/dyld` 原字节与本进程 shared cache UUID `c284a291-b68b-3d0d-a1a0-3f866f87efdc`。在 Python 中以绝对路径打开 `/usr/lib/libproc.dylib`，`dladdr` 将 `proc_listpids` 解析到 `/usr/lib/system/libsystem_kernel.dylib`。本机 SDK 声明匹配 `PROC_PGRP_ONLY=2` 和参数布局。 | 可将这些对象作为精确宿主候选。仍须明确接受 Apple 系统及 loader、文件系统、进程组 / 信号 / wait 语义和工具不逃逸原组的假设。这里只查找符号，没有调用 `proc_listpids` 或发送信号。共享缓存 UUID 只用于识别，系统库未逐一重建或验收。 [包装器监督边界](../query/solver-linux-channel-l3.md#native-捕获与一次包装器) |
| Cargo 解析数据 | `config.json` 76 bytes 与 `.cache/li/bc/libc` 84,005 bytes 均匹配历史摘要。用既有 `check_cargo_resolution` 校验官方 registry URL、cache 版本、唯一的非 yanked `libc 0.2.189` 条目、checksum 及 `Cargo.lock`。用途仅为离线 workspace 锁解析。 | 锁文件绑定的是 crate checksum。两份缓存的来源需有精确依据，或明示信任已留存的具体字节。许可需另有适用于这两份 registry 数据的依据，现有记录仅覆盖 crate。未读取凭据或其他索引，也未调用 Cargo 解析这批数据。 [已有 crate 审阅](../checker-runtime-darwin-store-slice-review.md) · [索引范围](2026-11-01-linux-channel-l3-implementation.md#宿主发现与根因修正) |

恢复先复用下列本机观察。所需补证限于表中的精确对象。涉及新来源链或信任决定时，先核定证据与影响。之后若条件齐备，按专题单独授权一次 target 安装，限 120 s / 新增磁盘观测 512 MiB，安装后对账 66 项及原五组件 / 三工具。C1 / LibPoly、E0 / E4 与 G0 仍各有独立前置。

## 原字节与复核方法

既有发行清单、目标包、安装元数据与 Rust 工具引用见[逐文件观察](cvc5-control-plane-2026-11-01/channel-l3-input-observation.json)。本批只读诊断保留于本机忽略目录 `.tmp/l3-input-review-20261107.CCTZwaIG/`，文件原字节没有加入 Git。

| 本机文件 | SHA-256 |
| --- | --- |
| `target-observation.json` | `9c3b7f3bb3a206c3c0f8544ffe9257164f9bb773fa882080490af9e37b9d67db` |
| `observe-host.py` | `d2d1d22b7603cfa0844b227b89264d0625d39dad85564eb4304147485122616f` |
| `host-observation.json`（627,014 bytes） | `b0cf07fce6624dabd0cc8a033e87eacbfd7a9631e1e2f08d8ccb0e8740f01704` |

关键身份如下。完整观察含工具 / 文件的绝对路径、字节长、摘要、启动映射、Mach-O 声明、原 argv、Python 文件、许可材料和 Cargo 锁解析引用。动态探针中的 PID 会随复核改变。

| 对象 | bytes | SHA-256 |
| --- | ---: | --- |
| `rustup` | 11,053,296 | `aeb4105778ca1bd3c6b0e75768f581c656633cd51368fa61289b6a71696ac7e1` |
| `librustc_driver-e03ed1db822dfa4c.dylib` | 207,258,056 | `57f6b5280f218ed25ba6b7e4bc1d74da3ac8e4fd85bee1b8982ad4114d757c11` |
| `python3.14` | 18,053,472 | `c015ab131972822e27ed108cf353582af6ca2fd7daf6296789576c7e7d1ad61a` |
| `/usr/bin/git` | 200,560 | `34129c71a01a74f7f3b2443521519b2e5447553fa187f5fcafaaf8c42cc192e2` |
| `/Applications/Xcode.app/Contents/Developer/usr/bin/git` | 3,838,240 | `775851091335fd0f0e3eba68e92667b95115208e57ad5ca312936d10edb9ffd3` |
| `/usr/lib/dyld` | 4,129,840 | `be8904b70f95adeb9d244308ca470f939bb89bd32a9b1b05e3f65ac92579e226` |
| Cargo `config.json` | 76 | `5b943a2c6f7eb743f7308aba07bdbb47d9ae44aafecd832d7f15df186afbafb3` |
| Cargo `.cache/li/bc/libc` | 84,005 | `0c0c0edd0d15a477311bebab5f7b35d68767bb2ebeea274f85404cd2921c498a` |

- `python3.14 -I -B docs/records/cvc5-control-plane-2026-11-01/inspect-channel-l3-inputs.py` 及输出 `cmp` 通过。复用旧有界 reader 在内存扫描单包。
- `observe-host.py` 使用固定 Python、`env -i`、`-I -S -B`、短时版本探针和 `DYLD_PRINT_LIBRARIES=1`。对实际观察的非系统 Mach-O 及系统入口读取 `otool -L/-l`，使用现有 `file_record` 流式核对原字节。动态范围限于探针的启动及明确导入路径。首轮遇到 dyld 的 delayed 诊断格式，第二轮发现 Rust 许可文件路径假设有误；两次 stderr 均保留。最终按实际格式记录 delayed 行、绑定实际存在的 Rust / Cargo 许可文件，运行成功。另以 `codesign -dv` 读取签名元数据，未执行证书链验证。
- 本批没有下载、预填 cache、安装组件、构建 Linux 制品、启动容器 / VM 或执行 solver。

## F2 小范围静态审阅

L3 结论停在外部来源和信任缺口后，按当前接续仅核对 F2 的 AArch64 syscall 与 FD 所有权交接。检查了 `NativeKernel::invoke` 的 x8、x0–x5、x0 返回及内存效果声明。`OwnedFd` 由成功操作建立，`close` 消费 owner 且 EINTR 不重试。固定 FD 重映射先拒绝占用，再按子尾段顺序完成 remap、`close_range`、单次 listener 发送和固定 exec。对目标 FD 的空闲预检与 dup 之间仍依赖单线程和不共享描述符表的前置条件。 [F2 边界](../query/solver-bootstrap-native-boundary.md#fd信号与-b-尾段)

用固定 Rust `1.97.1-aarch64-apple-darwin` 执行 `cargo test --package radishaxiom-solver-bootstrap-linux --lib --locked --offline` 的三个单测筛选，各一项通过。筛选为 `native_layouts_match_lp64_uapi`、`close_consumes_once_even_on_eintr_and_dup_does_not_replace` 和 `child_remaps_before_close_range_then_sends_once_and_executes_exactly`。未发现需要修改的静态问题。仍待目标构建核对 AArch64 机器码与布局，并在获准的真实环境核对关闭、重映射及拒绝路径。
