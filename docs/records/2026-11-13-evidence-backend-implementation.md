# Evidence v0.2 后端候选实施与离线验证

日期：2026-11-13（Asia/Shanghai）。基线：`dev` 的 `5c530c0`；本任务承接同日六个未提交的审查文档 / 探针文件，不覆盖其历史观察。没有 fetch。所有者明确确认按 [D1–D5](../evidence/ax-b01-evidence-v0.2-backend-support-review.md#所有者确认的实施决定2026-11-13) 推进，先修重放工具拒绝回归，再完成本仓候选实现与离线验证；暂不提交或推送。

用途：为维护者和后续独立 checker 实施提供本批行为、复现入口及验收边界。不发布新公共格式，不认证实际来源，不完成 M1，不提供 solver 执行或 P6 放行授权。

## 实际变更

| 范围 | 本批行为与验证意义 |
| --- | --- |
| 旧投影检查器 | 先增加 replay tool 未知成员、浮动版本、重复角色、未知角色的四项拒绝回归并观察失败，再修复每个 actor 的闭合检查。旧 12 份投影指纹不变，负例由 16 增至 20。 |
| Rust 候选入口 | `readback_v02_with_backend` 显式接收来源批次、外部预期 pin、消费政策、信任允许集和组件资源上限。旧入口不自动启用后端；S1–S3 原件、身份及旧拒绝仍保留。 |
| 来源与闭包 | 只支持 simulation 的封存批次。精确 IR / P2、契约、策略和全部后端 executions 按整数顺序绑定；invocation 唯一，replay 在后端清单中紧接唯一同目标 solve。封套、流、工具、请求内规则 / generator / profile、模型、world、观察原件逐项取得并校验。缺原件与已知矛盾分开报错。 |
| 正向与未决 | attestation 所需后端、生成器和运行信任按 scope 核对；所有 unknown 和保留历史的 solve / replay 也需运行信任及对应义务。生产 certificate-required 产生 unknown，消费策略不满足返回本地 Incomplete，不改写 Evidence。 |
| 反例 | 复用 P4 请求重建、协议解析、模型解码及精确目标重放，重新装配 witness / world / assume / trace。Pre 不成立或目标未违反保持 unknown；解码前 / 后资源中止分别留存，不合成缺失制品。 |
| 历史聚合 | timeout→完成及完成→timeout 均保留有效完成支持；多次相容完成取最后一个；同目标 unsat 与有效反例冲突拒绝。全未决按最后求解链原因选匹配终态，保留所有历史和信任。包含 12 次尝试及跨目标交错测试。 |
| 完整文档 | 合成 AX-B01 correct 包含 13 项核心义务、九项后端结果和实际信任义务；重算 conclusion、原始摘要与文档域摘要。缺义务拒绝；两个 wrong 的完整包产生精确反例投影。 |

源码入口为 [evidence_review.rs](../../crates/axiom-ir/src/evidence_review.rs) 与 [backend.rs](../../crates/axiom-ir/src/evidence_review/backend.rs)。来源解析、限额、solve、replay 分为内部模块，未增加依赖、执行器或第二套公共读取配置。来源机器成员及聚合选择登记于 [backend.json](../evidence/evidence-v0.2-machine-contract/backend.json) 的 `local_readback`；该新增候选字节尚未公共接受。

测试包由 [fixtures.rs](../../crates/axiom-ir/src/evidence_review/backend/tests/fixtures.rs) 及其 replay 子模块从既有 IR 构造，S1–S3 前缀复用 `check_vectors.py --backend-core`。该输出仅供测试补齐，不能当作合法完整 Evidence。模型和捕获均明确合成，流程不启动 solver。前提拒绝用例把既有 pre-false 的规范 contracts 加到已支持 minimal IR；临时文件只在 `target` 中创建，读入后删除。

## 独立有限对照与覆盖限制

[check_backend_readback.py](../evidence/evidence-v0.2-machine-contract/check_backend_readback.py) 通过 stdin 读取 Rust 测试包，复用已有 Python 有限解释器直接计算 WF / Pre / 精确目标与 witness。AX-B01 correct、wrong-add、wrong-drop-zero 各有九项，前提为 false 的 minimal 有一项，共 28 个观察。五类目标均覆盖；wrong-drop-zero 的 guarantee 失败而 row-coverage 未违反。每份包还改坏生产 result，要求独立计算拒绝不一致。四份完整包的原始 / 文档域 / 批次 / 契约摘要固定在 [backend-readback-fingerprints.json](../evidence/evidence-v0.2-machine-contract/backend-readback-fingerprints.json)，固定后已再次运行测试核对。

这些结果只支持有限输入观察，不认证批次来源，不验证 unsat 的普遍性，不核对真实工具资格，也不是 ADR 0008 的独立产品四态。五类目标的广泛正反例和 WF 拒绝继续由既有 P4-B 组件测试覆盖；新完整包未逐一构造每种 replay 中止码及每种目标的失败路径。核心 S3 支持边界未扩张。

本地 `BackendPolicyStatus::TrustAllowed` 仅表示允许集满足；`remaining_trust` 不为空时不能解释为无信任证明。调用方必须从与 producer 分离的受信渠道取得预期 pin，本仓纯函数无法证明调用方确实进行了这种分离。batch 只声明这一封存批次完整，不能证明历史上没有其他执行。测试中自行生成 pin 仅为合成装置，不是生产来源认证。

## 验证与复现

Python `3.14.5`，Rust `1.97.1-aarch64-apple-darwin` / Rust 2024。命令使用已安装工具与缓存依赖，`--locked --offline`；无依赖安装、lockfile 更新、容器或真实 solver。

| 实际检查 | 结果 |
| --- | --- |
| 基础 Python 向量 | 8 份审阅向量通过、5 份部分文档拒绝；既有字节 / group 检查通过。 |
| 后端 Python 投影 | 12 份原指纹匹配、20 项负例拒绝。 |
| Rust `evidence_review::` | 最终定向集 17 项通过，包含旧 S1–S3 回归及新增工具 descriptor / 消费侧组件上限拒绝。 |
| 完整包固定指纹 | 固定四组摘要后重跑 independent 定向测试，1 项通过；内部 28 个有限观察一致、4 份生产结果变异拒绝。 |
| 全 workspace / all-targets | 退出 0，41 个测试目标共 551 项通过、1 项既有手动 legacy 导出测试按配置忽略。最终补充的回归另由上述 17 项定向集覆盖。 |
| 格式与静态分析 | `fmt --all --check`、workspace / all-targets / all-features Clippy（`-D warnings`）均通过。 |
| 仓库与差异 | `check-repo.sh` 通过（3017 个文件），`git diff --check` 通过；已复核 tracked diff、未跟踪文件与权限变化。 |

未运行真实 solver / 容器、独立 Go 产品 checker、跨平台资格、M1 完整迁移或 P6–P9。workspace 测试涵盖当前平台可运行的离线组件，不能外推为 Linux / Darwin 实际隔离或运行资格。

```sh
python3 -I -B docs/evidence/evidence-v0.2-machine-contract/check_vectors.py
python3 -I -B docs/evidence/evidence-v0.2-machine-contract/check_backend_vectors.py .tmp/evidence-review-2026-11-13
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir evidence_review:: --lib --locked --offline -- --nocapture
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline
./scripts/check-repo.sh
git diff --check
```

合成导出目录沿用同日审查任务产物，重生成入口见[审查记录](2026-11-13-evidence-backend-review.md#已运行验证)，必须选择新的精确目录。新的完整文档测试不依赖该导出目录，也不读取真实执行材料。

已观察的失败：新增四项 replay tool 回归先失败，修复后通过；开发过程的编译 / Clippy 诊断已修正。独立对照首次选用原 pre-false 输入时，退出 101，报 `Invalid { at: "origin", reason: "unsupported field" }`。该旧输入超出 S3 当前支持，随后改用上文 minimal IR 的同前提变体，未放宽实现或吞掉错误。

## 接续与工作区

下一步审阅本批新机器字节与精确包身份，明确独立 request / manifest / result 的版本化交换，再在授权的分仓任务中实现并验收四态、来源政策和完整迁移矩阵。真实来源端及工具 / 宿主资格仍需独立收口；本批没有写独立 checker 仓。

原 `contract.json`、基础 / 后端固定投影指纹、ADR、IR 与旧 Evidence 原件未改。修复前探针观察保留，不用当前实现重写旧事实。P6 保持 `closed / p6-not-evaluated`。

首次实施收口时，本批与承接的审查改动均未暂存、未提交；无新增提交、push、PR 或远程写入。合成导出及验证日志保留在已忽略 `.tmp`，Cargo 产物在已忽略 `target`。没有启动长期服务或真实 solver。

首次收口分支为 `dev`，与本地记录的 `origin/dev` 无 ahead / behind；工作树有本批及承接审查的未提交改动。

## 提交前复审（2026-11-13）

所有者随后要求再次审查来源绑定、信任边界和历史聚合，发现问题直接修复验证，确认后提交到 `dev`，暂不推送。本次沿原工作树逐文件复核，无并行或范围外改动。

发现并修复一处资源边界问题：批次原件在尺寸检查前先计算 SHA-256，超限数据仍会消耗完整摘要扫描成本。新增回归先得到退出 101（其余三个新审查测试通过），随后将 `max_input_bytes` 检查前置至摘要与身份检查之前。合法包字节、固定指纹、结果语义和真实执行门禁均不变。

[复审回归](../../crates/axiom-ir/src/evidence_review/backend/tests/review.rs) 额外覆盖：

- 重算原件摘要、execution / trust / obligation 身份和批次 pin 后，错 request、invocation、调度事实、CLI 绑定与终态仍在来源检查处拒绝；replay 的父 solve 与 invocation 错绑也拒绝。
- 将 attestation 的 generator、backend、host 三类依赖移到另一个合法 scope，不能替代精确依赖；删除被后次成功覆盖的早期 solve 或 replay 运行信任，即使对应 trust-boundary 义务同步删除也拒绝。
- 有效反例后超时仍保留 failed；重复有效反例选最后一次相容支持；反例后 unsat 与既有反方向冲突测试均拒绝。
- 批次超过输入字节上限时，在摘要计算与来源身份检查前拒绝。

变异测试的重绑定只用于合成装置；`verify` 中重算测试 pin 不代表真实调用方可自行更换受信来源。普通删除 / 换批次仍由既有外部固定 pin 测试覆盖。未发现来源身份、精确信任或历史聚合的新增接受绕过；这不是一般正确性证明或生产来源认证。

修复后 23 项 `evidence_review::` 定向测试通过，基础与后端 Python 向量及四组完整包指纹均保持通过。格式和 workspace Clippy 通过。提交前验证与本次提交均只作用于本仓候选；真实 solver、公共发布、独立 checker、M1 与 P6 门禁不变。

最终全 workspace / all-targets 离线重跑退出 0：41 个测试目标共 558 项通过、1 项既有手动 legacy 导出测试忽略；包含 181 项 IR 单元测试和全部本批回归。仓库检查通过（3018 个文件），差异卫生通过。验证进程均已结束。本次按所有者新授权将完整改动提交到 `dev`；不 push、不新增远程状态，提交身份与摘要以 Git 记录为准。
