# P4-A v0.2：紧凑查询的请求与模型绑定

日期：2026-10-17。状态：Accepted，依据 [ADR 0027](../adr/0027-compact-query-and-p4-binding.md)。

用途：精确规定 query v0.5 的 P4 配对、请求差异、名称恢复与验收；供 P4 实现者及验收者使用。

不包含：真实 cvc5 校准或执行、模型文法扩张、OS 资源保证、完整 Evidence 或新的 P4-B 语义。

本文件是 [P4-A v0.1](p4-request-response-model-v0.1.md)的显式新分支。除本稿逐项列出的差异外，沿用其纯入口、规范 JSON、模型文法、Text 类与世界构造、资源收费和错误优先级；旧文件原文字节不改。

## 精确支持矩阵

| solver profile | query profile / artifact | 请求版本 | 处理 |
| --- | --- | --- | --- |
| `axiom-p4-cvc5-1.3.4-query0.2-model-v0.1` | v0.1、v0.2、v0.3、v0.4 / query0.2 | 0.1 | 原路径，旧规则摘要与规范字节不变 |
| `axiom-p4-cvc5-1.3.4-query0.3-model-v0.1` | v0.5 / query0.3 | 0.2 | 本稿新路径 |
| 任一已知 profile | 上述交叉配对或 profile / artifact 不一致 | 无 | 显式 profile 配对错误，无自动重编码、降级或重试 |
| 未知字符串或版本 | 任意 | 无 | 不支持错误 |

query 完整字符串及 artifact 以 [query v0.5](map-filter-query-v0.5.md)和旧规则为准。新分支先检查配对，再按原流程检查 stdin 尺寸、strict query 与绑定；旧合法配对的拒绝顺序保持。不能依赖“所有 QueryProfile enum 都受支持”来放行未来版本。

## 请求 v0.2 的闭合成员

请求 format 仍为 `axiom-p4-solver-request`，version 为 `0.2`。顶层闭合集合保持 `{format, version, profile, protocol_rules, query, binding, symbols, layout, tool, adapter, limits}`。相对于 v0.1，只有以下规范差异：

| 位置 | v0.2 规则 |
| --- | --- |
| `profile` | 固定新 solver profile |
| `protocol_rules` | 本文件完整 UTF-8 原文的 raw digest |
| `query` | 闭合 `{artifact_type, dialect, encoding_profile, raw_digest, byte_length, query_rules}`；前三项为新 query 身份及原方言，query_rules 为 v0.5 规则原文 raw digest，其余绑定完整 stdin |
| `limits.component.query` | 闭合 `{base, compact}`；base 是 v0.1 的七成员 query limits 对象（含 ir_json）；compact 是 v0.5 的七成员 compact limits 对象，成员名与其资源表逐字相同 |

compact 的七个成员分别为 `max_normalized_nodes`、`max_normalized_edges`、`max_scratch_cells`、`max_work_steps`、`max_temporary_bytes`、`max_integer_digits`、`max_dag_depth`。所有限值仍是规范非负十进制字符串；无缺省、null、未知成员或忽略的额外限制。旧请求不添加 compact 或 query_rules，不重算旧 protocol_rules。

`binding` 仍闭合为 IR raw / document、P2 raw、目标、语义与 generator_source 六成员。query_rules 在 query 对象中参与请求摘要，同时来自不可变 QueryBinding；不接受调用方提供一个任意合法摘要。规则正文引用旧语义及编码规范，这些依赖由保留的文件字节和回归基线锁定，不能修改被引用旧规范而声称新规则身份未变。

symbols / layout / tool / adapter 及其子成员、参数 token 顺序、canonical JSON 与 raw digest 规则全部沿用 v0.1。adapter.status 仍为 `planned-not-calibrated`；base_execution_profile / digest 引用原指定态 profile，表示参数资源来源，不声称 registry 已支持 query0.3。

所有执行上限不变：stdin=1,048,576、stdout=4,194,304、stderr=65,536、working_memory=134,217,728 字节，外层 6,000 ms、内部 5,000 ms / 1,000,000 steps。请求只发送精确 query bytes 后 EOF，不追加 get-model、注释或 proof 命令。新预算是组件构造成本，不是 solver 增限。

## 规划、symbols 与 layout

既有 `plan_solver_request` / `check_solver_request` 入口显式承载新分支和完整预算；新 immutable SolverRequest 保留选择的 profile、规则、query 和预算，parse / decode 不允许另给更宽限制。旧调用可保持源级适配，但不得把旧 QueryLimits 自动解释成带默认值的 compact limits。

规划重新运行 query v0.5 strict 编码，核对 bytes / raw digest、完整 binding（含 query_rules）、所有新自由名称 / sort / origin。layout 从真实 IR 构造，覆盖全部 port、原容量、Record / Option 组件和零容量接口；不能从 `sN` 的数字或 AX-B01 字段名猜测布局。

符号制品仍为 `axiom-p4-query-symbols` v0.1，布局制品仍为 `axiom-p4-input-layout` v0.1；成员与原语义完全相同，绑定新的 query raw digest。symbols 按新名称字典序排列，必须精确包含所有自由声明；derived 仅含新 query **实际输出**的全部零参数 define-fun 名称 / sort，按名称字典序排列。内联或被裁剪的节点不在 derived 中。

生成的 legacy-name → new-name 对应只用于内部重建或测试审计，不新增独立公共名称映射输入，不扩展 symbols schema。不同旧符号即使有相等值也不能共享 origin；名字交换、origin 交换、遗漏 inactive / None 叶或外加自由符号均须拒绝。

## 响应与候选的兼容边界

响应观察继续使用 `axiom-p4-solver-response-observation` v0.1，模型候选继续使用 `axiom-p4-model-world-candidate` v0.1。结构与值解释不变；它们通过精确 request digest 绑定 v0.2 请求。既有 P4-A v0.1 的接受集合不扩张，新接受范围来自本规则与新 profile。

- sat 仍要求每个自由符号有唯一同 sort 定义；未知旧 `q…_t…` 名称、虚构 `dN`、被内联定义、缺项、重复、非法别名 / 表达式或类型不符均拒绝。已知 derived 可以省略，出现时仍按原文法检查；不能当作程序输出或反例答案。
- unknown 可带或不带受支持模型，但永远不能进入 decode_model_world。非零退出、截断、外层 timeout / memory / stream limit 等仍按原失败优先级保留，不能因有完整模型而成功。
- Text 类仍以**全部自由 Text 名称**中的最小名称排序，literal 锚点、合成字符串避碰和 inactive / None 参与规则不变。保序双射保证对应模型赋值下 class 顺序及 world bytes 相同；atom 可任意重命名而不改变世界。
- 新旧候选的 request / response 摘要和 text_classes 中的符号名称通常不同，不能要求完整 candidate bytes 相同，也不能只换摘要迁移旧候选。必须用新请求和对应模型重新解码。

纯 parser 仍不认证真实 stdout 来源，不产生 attempt、证明或 Evidence 五态。实际 solver 省略未使用的声明、输出更复杂定义或超限时保留相应失败，另审阅工具或文法；不在本 profile 中补项或扩大 parser。

## P4-B 接入边界

新候选通过既有 `ReplayWorldInput::ModelCandidate` 路径进入 [P4-B v0.1](p4-concrete-target-replay-v0.1.md)。先核对同一 request / model / candidate 与 IR / P2 / 目标，strict 重建候选，再直接求值原 IR 的完整 WF / Pre 和精确目标；不从 query 中的 `dN` 读取求值答案。

ReplayProfile、world 值格式、五类目标含义与 observation schema 不变。来源记录里的 query_profile / query / request 摘要按新输入改变，旧记录不重写。若实现发现旧重放格式存在限制新来源的额外契约，先报告并审阅，不能静默修改已绑定 P4-B 规则。

## 必需验收与拒绝矩阵

| 材料 / 操作 | 必须观察 |
| --- | --- |
| 旧四版、旧 P4 合成材料与尺寸拒绝 | 原 bytes、symbols、layout、request、候选及错误不漂移；原容量旧 stdin 仍拒绝 |
| 原容量三候选的新 v0.5 / 五类目标 | 新请求完整 stdin 实测 ≤ 1 MiB；IR 容量、目标全集不变；最大值与余量独立报告 |
| 新旧 profile、artifact、规则、请求版本交叉配对 | 全部非矩阵允许项拒绝；同 SMT bytes 也不能替代完整绑定 |
| IR / P2 / target / generator / query_rules / limits / tool 任一变化或篡改 | 合法不同输入形成不同请求身份；错配输入或伪造派生摘要拒绝 |
| 完整合成模型、定义顺序变化、Text atom 重命名、Option / Record / Fixed / Enum、inactive 与 None | 对应赋值的新旧 world bytes 相同，候选重新生成并 strict 通过；完整候选无需字节相同 |
| 缺符号、交换 origin、旧名混入、已裁剪 / 内联派生名、别名循环、Text literal 冲突、非法活动值 | 可定位的原类别拒绝；没有补默认值、部分世界或静默去重 |
| sat / unsat / unknown、非零退出、截断、外层 timeout / memory | 原文法与失败优先级保持；unknown 无 world；合成超时不计真实校准 |
| 新候选进 P4-B 与直接 world 对照 | WF / 全部 Pre / 精确目标一致；满 100 槽、乱序、重复键、Pre 失败与两个 wrong 的手算区分均覆盖 |
| component / compact 全部预算、恰等上限、差一与溢出 | 请求绑定所有限值；不足不回退旧 query、不增限、不产生部分制品；parse / decode 沿同一请求限值 |

实施验收仍须格式、Clippy、workspace 测试和仓库检查；独立有限路径解释真实新 SMT，不复用生产 canonicalizer 自证。完成这些只形成纯组件接入与本机验收，真实 solver、其他平台、完整 Evidence 和独立 checker 分别保留停止线。
