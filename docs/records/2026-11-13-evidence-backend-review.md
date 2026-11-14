# AX-B01 后端绑定契约审查与离线验证

日期：2026-11-13（Asia/Shanghai）。基线：`dev` 的 `5c530c0`，开始时工作区干净，与本地记录的 `origin/dev` 一致；未 fetch。

用途：留存 B1–B3、机器候选和现有读回实现的审查事实，供所有者决定下一实施范围。不接受新语义、信任或公共字节，不认证真实来源，不完成 M1，也不修改独立 checker 仓。待确认选择只维护于[现有审阅专题的 D1–D5](../evidence/ax-b01-evidence-v0.2-backend-support-review.md#待所有者确认的决定2026-11-13)。

## 审查结论

当前材料分为三个不同层次：S1–S3 已有本仓 Rust 严格读回；后端只有单目标 Python 合成投影；实际来源认证、全部九项后端结果、完整 Evidence 与独立 checker 尚未接通。旧向量全部通过不代表新层次已完成。P6 保持 `closed / p6-not-evaluated`。

| 编号 | 发现及依据 | 影响与处理 |
| --- | --- | --- |
| R1 · 已复现检查缺口 | 对 wrong-add 合成投影的 replay tool 分别添加未知成员、改为 `latest`、重复角色、增加未知角色，并重算 tool / execution ID 和 result 引用；四案都返回 `replay-bound`。`check_packet` 只对 solve actor 检查完整成员，`check_run` 只检查所需角色是否存在；没有对每个 actor 统一执行闭合工具规则。 | 不符合基础工具契约。下一实现批先增加拒绝回归，再修复；无需新增语义选择。本仓 Rust `read_tools` 已有闭合成员、固定版本和角色集合检查，此观察不证明生产读回有同样漏洞。 |
| R2 · 信任范围待定 | `minimal-unknown` 投影的 trust 为空，消费侧允许集为空仍返回 `indeterminate`。反例投影只登记 solve execution scope 的 host-runtime，未单独覆盖 replay。 | 这是局部投影返回值，不是独立四态结果；不能直接推出“没有剩余信任”。D2 建议在完整文档顶层登记所有实际来源依赖，保持 unknown 原字段。 |
| R3 · 历史聚合未实现 | `check_packet` 固定一次 solve 与可选一次 replay，执行和工具数量仅允许 1 或 2；追加一个重算 ID 的执行在 `execution-closure` 被拒绝。 | 此探针只确认数量门槛，追加记录没有独立重试来源，不能作为聚合语义测试。D4 需补真正的多调用合成清单、相容支持及冲突矩阵。仅靠 ordinal 不能检测 producer 删除历史后重编号。 |
| R4 · 来源认证尚无生产入口 | `expected_capture` 来源于预校验的模拟导出。replay 的 invocation / observation / solve 关系由同一模拟 source 提供；当前没有具名的真实采集授权配置与批次清单。 | 模拟范围已明确，不属于真实认证被绕过的证据。D2 需确定调用方受信 pin、重放绑定和完整批次边界，不能把 scope 改标签当资格。 |
| R5 · 中止与 provenance 需要按模式整合 | 基础 Rust `Mode::read` 仅有 Structure / Effect / Origin；`attempt` 读取旧 kind，所有 provenance descriptor 固定 `execution-provenance / 0.1`。后端投影使用 `interrupted + code` 和两个具名封套。 | 属于尚未接通的明确接口差异，不能直接复用旧解析函数。D5 建议按 mode 增加支持，保留旧字节及拒绝行为。 |
| R6 · 登记分支超出向量范围 | backend.json 登记 absent、tool-unavailable、inputs_before_world 及多种 replay 中止，但 `load_source` 只从现有完整 / 前缀导出构造封套；流检查直接访问 `artifact`；`check_run` 始终使用标准 inputs，sat 分支要求已完成 replay。 | 这些分支没有正向验收。当前脚本不是整个登记的通用读取器；应补独立预期后逐分支实现，禁止将现有 12 个投影概括为全模式覆盖。 |
| R7 · 独立语义和闭包未验收 | 投影没有完整 artifacts 描述表、全部义务、trust-boundary 义务和 conclusion；反例字段期望复用 `counterexample`，结果重建依赖预校验 source。SIM 检查含 wrong-add 固定有限算术对照，但不是五类目标的一般独立解释器。 | 完整来源闭包、五类目标的独立重建、缺项与矛盾四态、全义务聚合必须另外验收。现有生产 P4-B 及独立有限组件回归可复用，不能冒充独立产品 checker。 |

R1 的四个输入均保留规范 JSON 与有效条目身份，避免只测试摘要拒绝。它们是对既有规则的反例，不应更新原固定指纹使其成为合法样例。本轮不修改投影检查器或生产实现，只保留审查发现；后续修复后的期望应变为明确拒绝。

## 已运行验证

本机 Python `3.14.5`；Rust 命令显式使用已安装的 `1.97.1-aarch64-apple-darwin`，`--locked --offline`。没有依赖安装、lockfile 更新或 solver / 容器运行。合成导出只运行既有本仓 Rust 示例。

| 检查 | 实际结果 | 证据边界 |
| --- | --- | --- |
| `check_vectors.py` | 退出 0；8 个审阅向量，5 份部分文档拒绝，字节、绑定及 group 检查通过。 | 候选基础契约 / S1–S3。 |
| `export_simulation_observations` | 退出 0；新建任务专用合成导出。 | 模拟观察，不是真实 solve attempt。 |
| `check_backend_vectors.py` | 退出 0；12 个指纹匹配、16 个负例拒绝。 | 既有单目标投影，另有两项消费策略不完整检查；不覆盖 R1–R7 的全部缺口。 |
| `evidence_review::tests` | 1 项 Rust 测试通过，159 项被过滤。 | 测试内部读入 11 份 Python 材料及执行变异；不是 11 项独立 checker 验收。 |
| `replay::` | 14 项 Rust 测试通过，146 项被过滤。 | 包含模型来源、精确目标手工期望、有限语义对照、资源与变异拒绝，以及两项匹配该过滤串的 compact replay 测试。 |
| 本次审查探针 | 退出 0；记录 R1 的四项漏拒绝、R2 的空 trust 观察、R3 的数量门槛。 | 退出 0 只说明探针完成，不表示这些行为正确。 |

探针源码为[probe.py](2026-11-13-evidence-backend-review/probe.py)，实际输出为[observations.json](2026-11-13-evidence-backend-review/observations.json)。输出固定了被审查源码、两份机器登记、既有后端指纹、探针本身和本次导出 manifest 的 SHA-256。复现使用 `5c530c0` 的被审查文件与本记录探针；后续修复改变输出时保留该历史观察，不重写为通过。

复现命令（新导出目录必须不存在；再次运行时换用新的精确目录）：

```sh
python3 -I -B docs/evidence/evidence-v0.2-machine-contract/check_vectors.py
cargo +1.97.1-aarch64-apple-darwin run -p radishaxiom-solver-diagnostic-host --example export_simulation_observations --locked --offline -- .tmp/evidence-review-2026-11-13
python3 -I -B docs/evidence/evidence-v0.2-machine-contract/check_backend_vectors.py .tmp/evidence-review-2026-11-13
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir evidence_review::tests --lib --locked --offline
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir replay:: --lib --locked --offline
python3 -I -B docs/records/2026-11-13-evidence-backend-review/probe.py .tmp/evidence-review-2026-11-13
```

## 接入前必须补齐的验收

| 类别 | 必须覆盖的新增材料 / 拒绝 |
| --- | --- |
| 来源及闭包 | 缺独立 solve / replay pin、换工具 / 规则 / 预算 / 目标 / 请求、重复 invocation、换上游 solve、删历史并重编号、缺原件与原件错摘要。区分合法缺项、不支持和已知矛盾；模拟不能提升到真实 scope。 |
| 工具及字节 | R1 四类拒绝覆盖每个工具；按模式核对 provenance 格式与内部引用；完整流、前缀、空完整流和 absent 分别测试；未知字段 / tag / 版本、重复键、非规范 bytes 拒绝。 |
| 反例 | 五类目标、WF / Pre 拒绝、精确目标未违反、wrong-drop-zero 归因区分；模型解码前 / 后中止分别留存。生产重演与独立期望不一致必须拒绝。 |
| 信任政策 | 后端、generator、solve 与 replay host scope 逐项错绑 / 缺失；unknown 运行信任；生产 certificate-required 与消费 certificate-required 分开；未允许 trust 为 incomplete，不把它当 Evidence 格式错误。 |
| 多次尝试 | timeout → 完成、完成 → timeout、相容多完成、多个未知原因、重放中止、同目标矛盾、跨目标交错、至少 11 次顺序以检出字符串排序、历史清单漏项。 |
| 完整 Evidence | 同一 IR / P2 的 13 项核心义务及实际 trust-boundary、缺义务拒绝、完整结论重算；新 Evidence 两类摘要与独立结果绑定。S1–S3 部分材料继续拒绝，ADR 0009 的 group / 旧历史 / 版本矩阵保留。 |

本轮未运行独立 Go checker、真实 solver、工具资格检查、M1 完整迁移、P6–P9 或跨平台验证；未做全 workspace Clippy / 测试，因为没有生产源码变更。新机器字节、来源清单格式及 D1–D5 均未接受。

## 收口

`./scripts/check-repo.sh` 通过（3004 个文件），`git diff --check` 通过。复核了 tracked diff、三个新增文件及工具输出：本轮仅修改后端审阅专题、机器契约说明和当前状态，新增本记录、探针及观察 JSON。机器 JSON、既有向量指纹、ADR、IR / Evidence 原件与生产代码保持不变。

六个文件的改动尚未暂存或提交；无新增提交、push 或其他远程写入。任务合成导出保留在已忽略的 `.tmp/evidence-review-2026-11-13`，可从上述精确入口重生成；无任务后台进程。下一步由所有者确认 D1–D5，随后进入限定候选实现与验证，不据本记录放开真实执行或 P6。
