# F1 共享边界与启动声明验收

日期：2026-10-17。用途：记录 ADR 0030 接受后的纯组件实施、原字节兼容与独立离线复核。读者：项目所有者、原生执行层实现者与验收者。本记录不授予 CLI 接受、Linux 构建、真实 FFI 或运行资格。

## 授权与提交

项目所有者明确接受 D1、D2、D3，要求先提交本批方案与补证，再推进 F1 纯共享边界 / 启动描述实现及 D3 构建候选方案；具体实现委派 `gpt-6.1-sol / high`，主代理主持设计与验收。原容量、旧字节和资源限值保持，不构建镜像、不运行探针或 solver、不修改系统配置、不 push。

启动时 `dev` 位于 `c489ec2`，相对本地 `origin/dev` ahead 2，工作树为前批 13 份方案与补证文件。接受状态和精确材料已提交为 **`f2ad466` — `docs(solver): 接受 bootstrap 方案并补充 E0 来源证据`**；随后工作树干净，ahead 3。F1 开发以此提交为基线。本次后续实现和验收材料留在工作区，未再次提交。

三个指定模型 / 推理级别的实现任务分别负责共享 core / 摘要 / 清单、启动描述 / 双端接口、D3 方案 / 独立检查。主代理审阅接口、资源来源和证据边界，执行最终检查；共享 core 实现者另对启动描述及双端接口做只读交叉审阅。D1 已接受新增私有 path crate 及相应 Cargo.lock 改动，本次只新增纯 core 与锁文件中的本地包条目，没有第三方 Rust 依赖或工具安装。

## 交付

- [solver-supervision-core](../../crates/solver-supervision-core/README.md) 从 host 提取 ABI 值、W/S cBPF 生成、wire codec 与 cgroup 文件值解析；全 crate 禁止 unsafe，不依赖 Axiom IR，没有 OS / FFI、进程、时钟或网络入口。wire / cgroup 预算显式传入，host 的兼容包装继续使用原固定资源。模拟身份、观察区间与监督器仍留在 host。
- 既有 digest 增加 `Sha256::new / update / finalize`，复用原压缩函数；旧一次性接口委托增量接口，不保存完整输入。长度溢出显式拒绝且不改变状态。
- [启动描述 v0.1](../query/solver-bootstrap-start-v0.1.md) 使用有界、固定键序的 ASCII JSON，拒绝重复 / 未知键、空白 / 转义、非规范整数、畸形摘要和附加输入。host 通过既有 strict 请求检查重建实际 query，绑定 request / query / 工具接受记录声明，保留新 profile 与 linux-arm64 的显式限制。
- Mac / S 分离本地时钟类型和单次 READY / ARM 状态。Mac 由全局剩余时间扣除声明误差生成 Linux 截止；S 只消费 ARM，不取得 Mac 时间或本地生成 ARM 的入口。检查期限、回退、溢出、重放、绑定和实际 query；失败保持首次错误。返回值仅为声明 / 截止 / query 核对计划，不能构造认证捕获。
- 显式 example 导出四份离线资源 / 策略输入；编译时捕获 22 份当前源码，固定资源、wire 预算、21 FD 角色、W/S 实际 bytes 均有摘要绑定。独立 Python 按手写固定值和旧策略 golden 核对，再运行独立 E3 有限解释器。它不是完整 policy bundle：outer setup 尚未建立，native build 未接受。
- [D3 构建候选方案](../query/solver-cvc5-build-candidate-plan.md) 保持同版本 cvc5、静态 non-GPL 候选与原功能比较基线，列出输入缺项、最小 CLI 范围、固定查找 / 缓存、实际对象 / link map 来源链及 C0–C5 停止线。未知输入仍阻断执行，没有生成假摘要、安装脚本或可运行配方。

启动配置、镜像、nonce、boot / namespace、CLI 接受记录和时间均由外部声明输入；形状、相等性和摘要检查不能认证来源。配置摘要目前是外部不透明值，尚不核实其构成。将来 OS adapter 必须建立实际观察、在散列完成后重新读时钟并核对期限；当前计划不具有装载、资源资格或执行授权。

## 审阅与拒绝证据

1. 清单最初的来源集合未覆盖后来合入的启动模块，独立 checker 拒绝不匹配；生产清单和独立固定列表统一为 22 份。来源 bytes 改为编译时 `include_bytes!` 捕获，避免运行时读取变化后的源码却冒充本次编译输入。
2. 独立检查除有限策略解释外固定原 W/S golden，不能用一个通过有限案例的新策略替换原字节。补充资源、FD、路径、来源摘要、清单重算及错误策略的拒绝测试。
3. 摘要源码格式化后，早期导出 `.tmp/solver-f1-bootstrap-manifest-a` 被独立检查以 `source-length` 拒绝。该历史输出保留；最终重新编译并导出到新目录，没有改旧摘要或放宽来源检查。
4. 双端接口明确区分 ARM 头部核对和实际 query 核对，不把声明长度 / 摘要视作 query 已收到；Mac 和 S 错误分别永久终止正常推进。编译失败文档测试核对跨时钟和越权接口不能使用。
5. D3 不把原 `--all-bindings` 扩为默认完整 SDK 重建：C0 先核对其对 CLI 对象 / 生成头的影响，只有实际需要才固定 Java / bindings 工具；构建所需 Python 独立保留。构建预算与 solver 运行预算分开。

## 验证入口与保留材料

本轮仅使用已安装的 pinned Darwin 工具链，命令均 `--locked --offline`，未触发依赖解析 / 下载。重跑导出应使用新的输出目录：

```bash
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline
cargo +1.97.1-aarch64-apple-darwin test --doc -p radishaxiom-solver-supervision-core -p radishaxiom-solver-diagnostic-host --locked --offline
cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-solver-diagnostic-host --example solver_bootstrap_manifest --locked --offline -- .tmp/solver-f1-bootstrap-manifest-new
python3 scripts/check-solver-bootstrap-inputs.py .tmp/solver-f1-bootstrap-manifest-new
python3 scripts/test-solver-bootstrap-inputs.py
cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-solver-diagnostic-host --example export_e3_offline --locked --offline -- .tmp/solver-f1-e3-offline-new
python3 scripts/check-solver-e3-offline.py .tmp/solver-f1-e3-offline-new
python3 scripts/test-solver-e3-offline.py
./scripts/check-repo.sh
git diff --check
```

最终导出保存于 `.tmp/solver-f1-bootstrap-manifest-final` 和 `.tmp/solver-f1-e3-offline-final`，检查 / 测试日志及基线保存于 `.tmp/solver-f1-2026-10-17`。生成器、合成测试和独立检查脚本进入仓库；机器结果与导出摘要见 [offline-results.json](solver-f1-2026-10-17/offline-results.json)。临时目录不当作已持久归档；来源摘要不替代输入本身。

## 实际结果与剩余边界

| 检查 | 实际结果与边界 |
| --- | --- |
| Rust workspace / all-targets | 36 组、396 项通过，0 失败；1 项既有 ignored：`solver::tests::legacy::export_legacy_materials`；各组时间合计 386.69 s，实际退出 0 |
| 编译失败文档测试 | 3 项通过，覆盖两端时钟类型及合成接口隔离；不代替 OS 能力验证 |
| fmt / clippy | `fmt --all --check` 与 workspace / all-targets / all-features clippy `-D warnings` 通过 |
| 增量摘要 | 原已知向量、百万 a、1,025-byte 非均匀固定摘要、分块 / 空更新、全部两段切分和长度溢出检查通过；原容量 query 的多种分块与旧摘要一致 |
| 启动与双端时间 | 闭合语法、N / N+1 预算、错误 request / tool / query、回退 / 溢出 / 重放与首次错误保持通过；2,700 组单位速率合成矩阵为 891 接受、1,809 拒绝 |
| F1 离线清单 | 四份最终输入、22 份编译时来源和固定资源 / 21 FD 角色一致；独立 Python 9 项正负例测试通过；outer setup / 完整 policy bundle 未建立，native build 未接受 |
| W / S 独立有限核对 | 3,176 / 1,450 项通过，实际策略 bytes 与旧 golden 完全相同；不计作内核 verifier 或实际 syscall 资格 |
| 原 E3 导出回归 | 13 份产物与原 `.tmp/solver-e3-offline-export-c` 逐字相同；原容量 query 962,642 bytes / 501 自由符号，Mac 17 帧、S 7 帧、控制 4,576 bytes；合成见证重放通过，独立检查器 6 项负例通过 |
| 基线对照 | 对 `f2ad466` 的 2,035 份既有 crate / contract / Cargo / toolchain 文件比较：2,024 不变，11 份变化仅为预期共享提取、digest、模块注册和本地 path 依赖；完整变化表见机器记录。旧 IR / query / P4、contract 与资源配置保持 |

`./scripts/check-repo.sh` 实际通过 2,726 份文件，覆盖文本卫生和本地文档链接；`git diff --check` 通过。最终 diff / status / 未跟踪文件复核未发现越界产物或意外权限变化，暂存区为空；`dev` 相对本地 `origin/dev` ahead 3，F1 实现与 D3 方案尚未提交。没有刷新远端。本机组件验收不包含上表明确排除的实际运行能力。

没有执行 Linux / 六平台构建、真实 syscall / 内核策略安装、容器创建、镜像、探针、solver、系统配置、远程写入或 push。没有新增常驻进程，临时导出与日志保留在忽略目录。原 CLI 仍为 not-accepted，E0 来源关联与 E4 真实能力未闭合；F1 不提供通过模拟结果解除门禁的入口。

下一可审阅切片为 F2 原生实现和 D3 C0 精确输入选择；它们不在本次实施范围。D3 当前是 blocked-on-inputs / not-accepted 的方案，不是新 CLI、payload 身份或构建接受。F1 的本机纯组件检查不等于真实 bootstrap、完整 P4、形式证明或工具 / 宿主资格。
