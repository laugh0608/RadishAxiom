# E1–E2 纯诊断组件与模拟规则 v0.1

日期：2026-10-17。范围：项目所有者明确授权的 E1–E2 纯组件与模拟测试，依据 [ADR 0028](../adr/0028-bounded-solver-calibration-entry.md)及[实施清单](solver-execution-implementation-plan.md)。主代理主持设计与验收，实现委派 gpt-6.1-sol / high。

本规则只规定本地模拟记录与控制行为，不是公共 Evidence、真实工具接受、宿主资格或真实执行 adapter。E0 与 E3 的缺口保持；没有运行镜像、探针或 solver 的能力入口。

## 身份与类型边界

所有可构造身份、计划和观察都必须是显式 `Simulation*` 类型，规范记录固定 `scope = simulation`，禁止可由调用方传入 bool 或字符串升级为真实认证。生产库不得包含 process spawn、网络、文件操作、环境继承、真实时钟或任意外部执行回调；测试和导出示例的合成 fixture 读取 / 输出不属于实际 solver 执行。

模拟材料包含实际 bytes 与期望 raw digest，先检查预算与实际摘要，再复制 / 绑定。payload 库存明确区分 archive、CLI、依赖、许可与模拟 acceptance 材料；它们只是模拟声明，不解释为 E0 正式接受格式。P4 的 `tool.payload_digest` 沿登记语义对应 archive raw；CLI raw 单独绑定，不能原地重解释旧字段。模拟 acceptance 的摘要与同一请求的 acceptance 字段必须相符。

宿主声明完整绑定 platform、context、daemon、kernel、runtime、image、bootstrap 与策略；平台限定 linux-arm64、context 限定 orbstack，但材料可为自有合成数据，不认证真实宿主。真实资格不可仅凭同名字段、摘要形状或 docker info 构造。

计划借用 / 保留既有不可变 `SolverRequest`，只接受新 v0.5 / query0.3 配对，绑定 request / query / 完整身份及预算。请求构造本身已完成原始 IR / P2 / symbols / layout strict 重建，本层不增加任意反序列化请求入口。必要时向既有请求增加只读 tool、argv、fixed process limits 元数据接口，复用原单一来源，保持旧规范字节和错误行为。

## 资源与规范记录

原十二参数和所有资源值保持：stdin 1,048,576、stdout 4,194,304、stderr 65,536、memory 134,217,728 bytes，外层 6,000 ms，内部 5,000 ms / 1,000,000 steps。新组件的材料、计划、观察、失败事实与控制诊断预算显式给出，不扩大 solver 上限。各次复制、累计和大小换算先 checked 记账，不以饱和算术掩盖溢出。

内部记录采用现有无 JSON number / null 的规范子集，数值为规范十进制字符串，对象顺序沿既有 canonical JSON。各记录固定独立 format / version / scope，精确 bytes 求 raw digest；strict 入口从同一类型输入重建并比较完整 bytes，拒绝额外 / 缺失成员、重复成员、错摘要或非规范表示。不得建立第二个宽松 JSON parser。

观察区分完整流与截断前缀；前缀的摘要不得被命名或消费为完整 stdout / stderr 摘要。记录实际模拟启动与否、exit、全部失败事实、时间和清理状态；不填默认退出零、空树或完成标记。可作为 P4 输入的正常响应仍明确是模拟响应，不能称为认证的真实 `CapturedSolverResponse`。

### 本地记录字段

三个 format 分别为 `axiom-solver-simulation-identity`、`axiom-solver-simulation-plan`、`axiom-solver-simulation-observation`，version 固定 `0.1`。它们只属于本批内部模拟格式，不绑定为旧 query / P4 规则，也不进入公共 Evidence。

- identity：platform、context、cli_member、固定 claim_status 与十三份材料；每份包含 scope、raw_digest、byte_length、raw_hex。材料角色为 archive、cli、inventory、licenses、acceptance、host、context、daemon、kernel、runtime、image、bootstrap、policy。
- plan：固定 real_execution=`blocked-E0-E3`、identity / archive / CLI / acceptance / request / query 摘要、完整 request / stdin hex、profile、stdin_protocol、attempts=`1`、空 environment、原序 argv 和固定资源。预算作用于本层输入与输出，不能通过调整本层预算修改 solver 限值。
- observation：固定 source=`simulation-not-authenticated-capture`、plan / identity / request / query 摘要、started、elapsed_ms、cleanup、primary_outer、exit、两流、独立控制诊断和排序后失败事实。流包含 kind、complete、exceeded、captured_bytes、observed_bytes_lower_bound、raw_hex；完整流仅使用 full_raw_digest，前缀仅使用 prefix_raw_digest。exit 使用 kind 及已观察到的 code，不可用零代替 unavailable。事实包含 kind、stage、at_ms；重复事实拒绝。

`HostLimits` 显式提供 material_bytes、total_material_bytes、record_bytes、stream_bytes、control_diagnostic_bytes、failure_facts、json_values、json_nesting。控制诊断固定 65,536 bytes；controller 在创建时检查固定流上限及精确 stdin 复制所需的合计预算。每次 advance 只处理一项调用方已经持有的模拟事件，不留存成功事件历史；不设置调用方循环次数上限，组件内留存由流与失败事实预算约束。事实预算耗尽不产生部分成功观察。

## 控制状态与传输

状态机只处理带模拟计划 / 请求 / 容器身份的事件，产生类型化模拟控制意图，没有 Docker 命令执行或 transport callback。E3 的 bootstrap、pids、syscall / cgroup 配置未冻结，本批不得伪造可直接运行的 create 配方。

正常顺序为 create → attach → start → 精确 stdin / EOF 与捕获 → exit / inspect → 空树确认 → cleanup → 终态。乱序、重复 start、容器错配、请求错配和时钟倒退失败关闭。失败后只能走终止 / 检查 / 清理尾链，不能重试或创建另一 attempt。缺失 exit / EOF / 空树 / 清理成功时不发布正常响应。

`finish` 只消费当前状态并导出观察，不能替调用方执行清理；尾链缺失必须失败。单个通道 EOF 后另一通道仍可继续捕获，空通道块不当作向已关闭流写入。deadline 到达时保留已经发生的合法启动 / 控制失败事实，但删除继续运行的控制意图。

时间由调用方显式提供模拟单调计数，不读取 OS 时钟。从首个控制动作计时，elapsed `< 6000` 才可能正常；`>= 6000` 为 deadline。失败收集可发生在窗口后，但不得回写成窗口内成功或授权再运行。

分离字节流与多路帧是两个明确入口：Docker CLI 的 stdout / stderr 已是独立通道，不能再次按 Engine header 解码。多路帧组件只对模拟的 Engine 风格二进制材料工作，固定 8 字节头（stream 1 / 2、三个零保留字节、四字节大端长度），按任意分块增量处理；未知 stream、非零保留字节、截断头 / payload 和超限帧均拒绝。不声称已对真实 Docker 传输完成校准。

不得按不可信声明长度预分配 payload。分离流并发交错不改变各自 bytes；在上限后的下一字节触发限制，保留有界前缀、至少 N+1 的观察和截断事实，不继续排空无限输出。控制诊断单独有界保存，不能进入 solver stderr。

## 失败与 P4 接续

全部原因保留，不从 exit 137 或 stderr 文本推断 OOM。模拟 memory 事件也必须来自同一模拟容器 / 计划。若有多个外层原因，主要原因取最早 `at_ms`；同一时刻按 deadline、memory、stdout-limit、stderr-limit、crash、unavailable 排序。后到的 cleanup deadline 不覆盖先前 OOM 的主要归因。

选出外层原因后，沿既有 P4 的 outer termination → 非正常 exit → 流失败 → 协议解析优先级。任何控制 / 传输 / 清理失败、非正常退出、截断、未启动或缺失观察均不能把 stdout 中的 sat 升级为可解码候选。

正常模拟响应按原字节进入现行 `parse_solver_response`；sat 模型由原 decoder 与 `ReplayWorldInput::ModelCandidate` 重放，unknown 不产生 world，unsat 不产生 proved。完整模型文法、全部自由符号、WF / Pre、精确目标、原容量及规范 query 保持。

## 本批验收要求

必须覆盖身份与摘要错配、旧 profile 拒绝、规范字节与 strict 篡改、材料 / 事件预算、流恰等与差一、全分段帧、双流交错、事件乱序、时钟倒退、超时 / OOM 同时与先后、清理失败伴随 sat、exit 137 不猜 OOM，以及成功 / unsat / unknown 的实际 P4 接续。

至少一个原容量 AX-B01-wrong-add guarantee 的 query 仍为 962,642 bytes / 100 槽位 / 501 自由符号，以合成模型贯穿新组件和 P4-B；这不计真实 solver 尝试。验收需保留可由独立小脚本核对的计划 / 观察 / 原始流样本，复核旧字节、格式、Clippy、workspace 测试和仓库检查。本批实现及验收状态另见完成记录，不由本规则自证。
