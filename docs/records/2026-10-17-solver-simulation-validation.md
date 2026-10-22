# E1–E2 纯组件与模拟验收记录

日期：2026-10-17。用途：记录 ADR 0028 执行层 E1–E2 的实现、设计复核、本机模拟验收与剩余门禁。读者为项目所有者、实现者及验收者；本记录不接受真实工具、宿主、Docker adapter 或 solver 结果。

## 授权与基线

项目所有者要求先提交精确 CLI 补证和执行层清单，再推进 E1–E2 的纯组件实现与模拟测试，由主代理主持设计和验收，明确实现委派 gpt-6.1-sol / high；E0 / E3 仍为真实执行硬门禁，保持原容量、旧字节与资源限值，不构建镜像、不运行探针或 solver、不修改系统配置、不 push。

第一步已将前批八个精确路径提交为 `ff2e4ed`（`docs(solver): 补充 CLI 依赖证据与执行层清单`）。提交后工作树干净，`dev` 相对未刷新的本地 `origin/dev` 为 ahead 7。随后本批实现、规则和验收材料保持未提交；不扩大首次提交授权。

实现任务分为 E1 身份 / 计划 / 观察、E2 控制 / 传输、独立合成 workflow / 导出三个代理，均使用指定模型与推理档位。主代理建立[模拟规则](../query/solver-diagnostic-simulation-v0.1.md)，审查具体接口、失败与预算边界，编写独立 Python 核对并运行最终工作区验证。

## 实际交付

新增私有 [solver-diagnostic-host](../../crates/solver-diagnostic-host/src/lib.rs)，`publish = false`、`forbid(unsafe_code)`，仅使用既有 `axiom-ir` 与 `digest` 的本地 path 依赖。Cargo.lock 仅新增本地包及这两个依赖边；没有新增第三方依赖、下载或 Linux 工具安装。

- [identity](../../crates/solver-diagnostic-host/src/identity.rs) 核对十三份合成材料的实际 bytes / raw digest / 每份与合计预算。archive 与 CLI 单独绑定，旧请求 payload 仍表示 archive；材料摘要一致不等于来源认证或 E0 接受。
- [plan](../../crates/solver-diagnostic-host/src/plan.rs) 只借用既有不可变新 profile 请求，保留完整 request / stdin、身份链、十二参数和资源。`real_execution` 固定 `blocked-E0-E3`，环境为空、attempts 为 1；没有可解锁真实执行的 bool、能力类型或回调。
- [observation](../../crates/solver-diagnostic-host/src/observation.rs) 固定 simulation，完整流与前缀摘要分开，保留启动、退出、清理与全部失败事实。先取最早外层事实，同时按 deadline、memory、stdout-limit、stderr-limit、crash、unavailable 定序，再沿原 P4 失败优先级。未知退出 / 清理、超限和时间事实不一致直接拒绝，不自动补造成功。
- [controller](../../crates/solver-diagnostic-host/src/controller.rs) 是单次、纯内存状态机，事件绑定 plan / request / container token，动作只表达模拟意图。乱序、重复 start、错误 stdin、时钟倒退、超时、控制失败和清理失败关闭；预算耗尽仍允许收尾意图，但拒绝最终部分观察。
- [transport](../../crates/solver-diagnostic-host/src/transport.rs) 区分已分离的 CLI 字节流与模拟 Engine 八字节头。两流分别有界，超限保留 N bytes 前缀和至少 N+1 观察，不按不可信声明长度预分配，不持续排空超限流；控制诊断不混入 solver stderr。

`axiom-ir` 的修改仅增加只读 tool / argv / process limits 元数据并复用原值。公共请求格式、模型文法、候选字节、P4-B、IR / P2 / query 语义保持；原固定资源为 stdin 1 MiB、stdout 4 MiB、stderr 64 KiB、内存 128 MiB、外层 6 s、内部 5 s / 1,000,000 steps。

### 设计复核发现与修正

主代理和交叉验收在最终门禁前发现并补齐以下边界，均保留回归：deadline 恰逢 Started 时不能丢失已启动事实或继续发 stdin；捕获预算应在首次复制前检查；一流 EOF 不应让另一流的合法输出失败；正常退出后的首次 inspect 失败应先发终止意图；失败事实预算耗尽不能阻断终止 / 清理尾链；未知退出和清理失败必须有对应事实。没有通过降低容量、增大 solver 限值、默认成功或忽略失败解决问题。

## 本机模拟与独立复核

[workflow](../../crates/solver-diagnostic-host/tests/workflow.rs) 用真实 P1 / P2 / query v0.5 / P4 请求构造，手选合成模型经过模拟控制捕获后，原始 bytes 原样进入既有 parser / decoder 与 `ReplayWorldInput::ModelCandidate`。minimal、含 Text / Option / 复合类型的 composite 和 AX-B01 wrong-add 均走该路径；unsat / unknown 不构造 world，cleanup 失败和 exit 137 不能由 stdout 中的 sat 覆盖。exit 137 不推断 OOM。

原容量 wrong-add contract-guarantee 请求仍为 **962,642 bytes、100 槽位、501 自由符号**。精确 query 为 `sha256:5ba58e0d9754c3448f299ce4d9be2060c2d91d829253ec3e4a170e0d4d07a85a`，目标为 `sha256:4916b2ef17b43cab21bff8ae87433922c60fbf86fb72fc52972e06964584476e`。合成模型中三行订单有唯一主键且满足折扣前置条件；两个 settled 行的 wrong-add 与规范减法不同，例如 `10 + 10 = 20`，规范为 `10 - 10 = 0`，P4-B 返回该精确目标的 `target-violated`。这是有限合成输入检查，不是 solver 尝试或普遍证明。

[导出示例](../../crates/solver-diagnostic-host/examples/export_simulation_observations.rs) 只能向不存在的 `.tmp/<新目录>` 写入，自有合成模型与全部生成入口保留在 [common](../../crates/solver-diagnostic-host/tests/common/mod.rs)。11 组材料包括三组 sat、unsat、unknown、cleanup failure、exit137、stdout-limit 和 OOM / deadline 先后及同时三组。stdout-limit 保留 4,194,304 bytes 前缀、至少 4,194,305 观测，stderr 已独立完成。

主代理的[独立标准库核对器](../../scripts/check-solver-simulation-export.py) 不调用 Rust 库，重新核对规范 JSON、raw hashes、十三份材料、request / query / plan / observation / P4 来源链、固定参数和资源、完整流 / 前缀摘要、最早失败原因、未发布失败候选，以及 wrong-add 三行的主键、有限 Pre 和算术见证。它不是独立完整语义 checker，也不认证事件来自真实宿主。结果见[独立观察](solver-simulation-2026-10-17/independent-observation.json)。

## 验证命令与实际结果

验证使用已安装的精确 Rust 工具链及离线依赖。格式检查与完整 workspace Clippy 已通过；完整 workspace 测试通过 **329 项，0 失败，1 项默认 ignored**；该导出项已另外显式运行通过。独立 Python 核对的三项拒绝测试与 11 组实际导出检查通过，最终导出 104 个文件与代理导出逐字节一致。仓库检查通过（2,668 文件），232 个本批文档本地链接有效，`git diff --check` 通过。

```bash
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline
cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-solver-diagnostic-host --example export_simulation_observations --locked --offline -- .tmp/solver-e12-root-export
python3 scripts/check-solver-simulation-export.py .tmp/solver-e12-root-export
python3 scripts/test-check-solver-simulation-export.py
./scripts/check-repo.sh
```

新增 Rust 定向覆盖包括 1 项预算单元、9 项 E1、12 项 E2、7 项传输和 6 项 workflow，共 35 项。生产库静态审查未发现 process / network / filesystem / env / clock / thread 或执行回调入口；合成文件读取与输出仅在测试 / 导出示例。

本批独立核对器初次运行因自身把符号声明误计为 `declare-fun` 而返回 `free symbol count`；检查实际 query 后改为固定 profile 使用的 `declare-const`，没有改写 producer 字节或放宽 501 符号要求，最终 11 组核对通过。

旧产物另以 `RADISHAXIOM_P4_BASELINE_DIR` 指定不存在的绝对输出目录，显式运行默认 ignored 的 `solver::tests::legacy::export_legacy_materials`，对照此前从 `14a9693` 独立旧源码导出的 query / symbols / layout / request / response / candidate 三组共十八份 bytes，全部一致；该 ignored 导出测试显式单独运行通过。相对 `ff2e4ed`，2,080 份既有源码、契约与规范保持逐字节一致（排除两个明确修改的 solver 元数据文件和现行实施清单）。[验证输入快照](solver-simulation-2026-10-17/source-inputs.json)绑定本批 21 份实现 / fixture 生成入口 / 核对器与模拟规则的 SHA-256。

## 未执行与剩余门禁

E1–E2 仅完成纯组件与模拟接续，不是可启动的生产 executor。E0 仍缺实际系统库版本、完整链接库存及配方到精确 CLI 的认证关联；E3 仍缺控制端失联后的独立终止拓扑，以及实际 cgroup / OOM / 整树清理和固定 ELF / syscall 能力。详见[实施清单](../query/solver-execution-implementation-plan.md)；E4 镜像与负向探针、E5 八份校准、E6 单次目标尝试仍须各自具体范围与授权。

本批没有构建镜像、启动容器 / VM / 服务、运行探针或 solver、修改系统配置、执行 CI / 其他平台、push 或其他远程写入。没有新增真实接受记录、host qualification、认证 capture、Evidence 状态或 proved 声明。临时合成导出与日志保留在已忽略的 `.tmp/solver-e12-root-export`、`.tmp/solver-e12-root-legacy`、`.tmp/solver-e12-root-validation` 及代理模拟导出目录，不删除既有来源材料。所有本批构建 / 测试与导出进程已结束，无新增长期运行进程。收口时工作区为 `dev`、ahead 7（本地远端引用未刷新），本批 27 个文件未提交，暂存区为空。
