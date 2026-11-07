# 2026-11-01：L2 提交与 L3 精确 target / 构建输入方案核定

日期：2026-11-01（Asia/Shanghai）。状态：**方案与指定既有字节核对完成；未安装 target、构建 Linux 制品或接受真实资格**。用途：保存本批提交、实际观察 / 方法与停止线；正式设计只见 [L3 专题](../query/solver-linux-channel-l3.md)，顺位只见[当前状态](../status/current.md)。不是完整输入 v0.2、安装回执、制品接受或正式 Evidence。

## 提交与本批范围

项目所有者要求先提交 L2 更改，再核定 L3 精确 target 组件与完整构建输入方案。开始时 `dev` 相对本地 `origin/dev` 领先 7 笔，暂存区为空，恰为 L2 的 22 路径；留存源 / 方法 / 材料绑定、七份脚本流、仓库检查和差异卫生均通过后，按精确路径提交 **`5dab738` — `feat(cvc5): 接通诊断通道 L2 有界管道与最终退出`**。提交后工作区干净、领先 8 笔，没有 push、fetch、身份变更、AI 署名或历史改写。

之后只修改正式方案 / 状态 / 索引及本批诊断记录。读取指定旧归档 / 库存 / 源文本、现有工具与安装清单，执行已有 rustup 的 version、已有 LLD 的 help、Python 只读 / 合成检查与 Git 元数据读取，并查阅必要官方文档 / 精确 Rustup 1.29.0 源码。不修改 Rust / Cargo / lockfile / Accepted ADR 或现行私有输入 / wire，不实现 v0.2 或构建包装器。

本批没有下载 target / source 归档、安装 / 移除组件、预填全局 cache、执行 archive install.sh、生成实际完整 root、调用 cargo build / Linux linker、运行 collector / leaf / Linux ELF / solver、操作 Docker / OrbStack / VM / mount / 长期服务或远程状态。现有宿主默认 Rust 1.96.0 未改；诊断方法的 version 调用仅在该子进程固定 1.97.1，并禁用自动安装，没有把 1.96.0 计作本批验证。

## 已取得材料的精确复用

[实际观察](cvc5-control-plane-2026-11-01/channel-l3-input-observation.json)由[固定只读方法](cvc5-control-plane-2026-11-01/inspect-channel-l3-inputs.py)生成：

- 原归档就在 `.tmp/rust-linux-inputs-bb014fd/`：`rust-std-1.97.1-aarch64-unknown-linux-musl.tar.xz`，29,062,284 bytes，SHA256 `49ff0879d94e2e8e86d5e85eb15a9215943e8c78b51363d6553443598cab5d31`。没有重下。重用旧有界 reader 仅扫描这个 musl 包，没有运行旧 main 去重新扫描无关 GNU host。
- 全部逻辑成员与已提交旧库存相等：7 目录 / 78 文件；tar 152,835,072 bytes / `f0314c4b28d4d5d89cd7fba9144e3a97e2643d6918a3807458b5b8d35c8e7d77`。66 个 component file claim / 152,642,974 bytes 的完整模式 / 摘要映射在观察 JSON。只在内存解码，没有提取为可执行目录或进行 .a 对象级 / 实际链接验收。
- 原发行清单 845,916 bytes / `03569b1886ceb5c05276b50c8431ab111de944cd6140fe1fa7d821dd8e0f29cf`；现有 sysroot 的已安装清单 972,396 bytes / `09cbf0ad7b7e084e3bf1131c6bd970ad34c29c9fcdc8db1f7836463b7322e69a`。两者 target URL / gz / xz 摘要及日期投影相等，未混称原字节相同。Linux target 目录 / component manifest、预期 cache 与 .partial 均不存在，原五个 host component 保持。
- 三工具原字节与既有交付候选一致；新增只读绑定 installer：rustup 1.29.0、11,053,296 bytes / `aeb4105778ca1bd3c6b0e75768f581c656633cd51368fa61289b6a71696ac7e1`。原生宿主工具 metadata 调用并非 target 运行、publisher / dylib 闭包接受。
- 固定源包仍在 `.tmp/rust-source-review-1262570/`，242,787,896 bytes / `0ed06fdaffd4722a7702e0b4eebfafc897ab8f513e8e1b247cdd7e5c6df6ded2`。重核原包摘要，复用已留存选定文本 JSON，与 Git 中 255 份元数据逐项匹配，并逐份验证文本长度 / 摘要；单列六份 Rust / compiler-builtins / compiler-rt / libunwind 许可摘要。没有重新解码 3.7 GiB 全源码 tar 或展开 GCC / Debian 信任研究。
- 既有 rust-lld 22.1.6 的 `-flavor gnu --help` 退出 0，stdout 28,876 bytes、stderr 0；真实含 --Map / --trace / --why-extract 选项。方法绑定输出摘要，不能从 help 推导参数组合或最终 ELF 通过。
- Cargo 祖先配置只检查精确路径是否存在，结果为空，没有读取 / 留存用户配置内容。`git ls-tree -rlz 5dab738` 的完整 tracked 基线为 2,931 文件 / 97,632,590 bytes，模式仅 100644 / 100755；本批没有复制这个快照或创建候选构建 / 安装任务根。

旧完整库存压缩及展开摘要先核对再复用，不改旧诊断。旧 Rust 分离签名及 SHA-1 自认证、公钥 / 宿主信任缺口原样保留，没有重新验签或将 musl 原包的限定 source acceptance 转为发布 component / 构建来源接受。

## 核定方案中的具体决定

[候选计划 JSON](cvc5-control-plane-2026-11-01/channel-l3-candidate-plan.json)是 proposal-only-not-native-build-inputs；它引用上述观察原字节，base_source_commit 为 L2，未来实现 commit=null，安装 / 构建授权和 readiness 均 false。具体绝对路径、argv 数组、28 段 rustflags、白名单环境和所有预算均可审阅，缺失实现 / 接受 / 安装观察使它不能执行或作为 native root。

1. **单组件安装。** 未来只给现有 rustup 新建已核对归档的 cache 副本，target add 这一个版本 / target；cache 或 .partial 先前存在即停，避免 installer 成功清 cache 越过所有权。使用空的本地 file: dist root、重试 0，不转官方网络下载、install.sh、新工具链或手改 sysroot。明确 target 树、component / multirust 元数据、cache 与事务临时项都可能改变。120 s / 新增磁盘观测限额 512 MiB、强制终止后未知部分状态与独立授权的精确 target remove 全部列明。
2. **完整输入设计。** v0.2 root 仅绑定最终源码 / 实际安装 / 工具与有限接受、五份受界 sidecar 和真实有序参数；不给 source-only v0.1 或 null build_inputs fallback。66 项 target、数千项 workspace 库存不塞入 64 项数组的报告 parser；不改其限制。root / sidecars / ELF / 外置 manifest 的无自引用顺序已列明；所有接受和实际生成均尚未发生。
3. **构建包装器。** 完整 committed workspace 快照保持 Cargo 图，实际 normal 编译闭包仍是三个既有 path 包。白名单环境 / 祖先配置拒绝、唯一 cargo / rustc / lld、受审 argv recorder / 生成字节绑定，避免从 -vv shell 文本猜参数。600 s、jobs=1、任务 512 MiB、ELF 16 MiB、map 8 MiB、why-extract 4 MiB、双流 4 MiB 不续期；所有阶段 / 副本计量，不构成 Mac RSS / 磁盘硬限或 Linux G0 资格。
4. **来源与许可。** libc / musl 的 5 个 CRT、compiler-rt 的 4 个 CRT、compiler-builtins、unwind、编译宿主分别列出真实材料 / 例外，保留最终 archive-member / 实际发布构建关联与分发接受缺口；不把根双许可证覆盖全部输入。未产生新的对象接受或许可证政策决定。

下一源码切片先实现 v0.2 纯生成 / 独立复核、native root 捕获与有界包装器静态测试。真实 root 还需实际安装观察和特定对象接受；之后安装、一次 Linux 构建、L4 离线制品验收与 L5 执行前收口分别授权。不以本页的具体参数充作执行许可。

## 实际验证与未覆盖范围

- 提交前 L2 原材料 / 方法摘要与当前源一致，50 源输入复核和七份脚本流独立复核通过；完整仓库检查通过（2,931 文件），`git diff --check` 通过。未重跑无变化的 117 项 Rust；该测试结果仍引用 L2 历史记录。
- `python3.14 docs/records/cvc5-control-plane-2026-11-01/inspect-channel-l3-inputs.py`：成功。最终 stdout 与观察 JSON 逐字节比对，当前 tar / manifest / 方法 / 工具 / 元数据身份及 target / cache 缺席重新核对；没有安装动作。
- `python3.14 -O docs/records/rust-linux-input-review/check-diagnostics.py`：复用旧 reader 的 8 项合成边界通过；不是密码学或 Linux 测试。
- 对候选计划逐项核对 target / archive 摘要、未来 root 缺席、精确包 / bin / feature / profile / argv、28 段 flags、profile 与根 Cargo、预算及 false / null 停止条件；与观察和正式方案一致。不会执行计划中 argv。
- `python3.14 scripts/check-repo.py`、差异卫生、本批路径 / 本地引用 / 文件模式 / 材料绑定核对通过，完整仓库检查为 2,936 文件；局部复核为本批 10 个精确路径、388 处本地引用 / 锚点、0644 / UTF-8 / LF 和空暂存区，均通过。没有修改 Rust / Cargo / lockfile，不扩大到 fmt / Clippy / Rust / Linux 编译或真实 runtime / OOM / 链接验收。

探索时一条宽泛 shell glob 没有匹配，zsh 报 no matches found；没有将其当材料缺失，随后使用正式记录定位到精确旧归档。没有依此下载新包、放宽检查或覆盖旧材料。

当前没有新 runtime 环境、后台进程或全局 cache 需要清理；只新增方案 / 记录与本机临时 JSON 观察，旧来源 / 失败 / L1 / L2 材料保留。C1 / E0 / E4、G0 / A1–A10、镜像 / 权限 / 独立终止 / 存储硬限与 solver 停止线不变。L3 本批文件未自动提交 / 推送，`dev` 相对本地 `origin/dev` 领先 8 笔。
