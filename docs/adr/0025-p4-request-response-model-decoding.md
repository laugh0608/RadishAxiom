# ADR 0025：P4 请求、响应与模型解码内部组件

日期：2026-10-12。状态：Accepted，项目所有者于 2026-10-12 接受精确范围并要求实施 P4-A。

## 背景

P3-A–F 已完成限定内部组件的本机验收。下一项应连接实际 query 与可重放的输入世界，而不是继续按义务清单扩大 SMT 支持。[前次接口审阅](../query/field-origin-and-p4-interface-review.md)拆分了 P4-A 协议 / 解码与 P4-B 具体目标重放，但尚未冻结文法、世界表示或预算。

现有 cvc5 adapter 已指定 `--dump-models`，因此不能仅因 query 末尾没有 `get-model` 就改写发送字节。另据 cvc5 1.3.4 的[命令执行源码](https://raw.githubusercontent.com/cvc5/cvc5/cvc5-1.3.4/src/main/command_executor.cpp)，`unknown(INCOMPLETE)` 也可能触发模型输出。旧 adapter 的概括性状态描述不是新 parser 的完整文法，更不是本机校准结果。

## 决定

1. 在现有 IR crate 内交付 `plan_solver_request`、`parse_solver_response`、`decode_model_world` 三个纯组件。输入使用完整不可变 IR v0.2 / ir-derived P2 / 目标与 P3 query，显式选择新内部 profile；不增加依赖或进程执行入口。
2. P4-A 显式覆盖现有四个 map / filter query profile 已支持的五类目标；不改变它们的支持集合或规范字节。请求重建 query、绑定、符号及类型布局，分别摘要绑定完整 stdin、符号清单、布局和请求；调用方提供的来源或摘要不能代替重建。
3. 新内部 adapter profile 为 `axiom-p4-cvc5-1.3.4-query0.2-model-v0.1`。规划复用旧登记参数与资源值，保留 query 字节后 EOF；新 profile 明确接受 query0.2 并定义响应子集。它是 `planned-not-calibrated` 的内部对应关系，不写入旧 registry，不授予真实执行资格。
4. 严格解析单状态与相应模型帧。`sat` 必须完整定义全部自由 QuerySymbol；`unsat` 不带模型；`unknown` 可不带或带一个受支持模型帧，始终保留为 unknown，不解码 world。未知成员、重复 / 冲突、截断、超限、非零退出与外层终止保留可定位原因。
5. 模型仅支持零参数 Bool / 数学 Int / Text 常量及有界同 sort 别名；允许精确 query 中已知派生零参数名称的相同子集，逐项检查而不消费为程序输出。其他函数、表达式和打印模式显式拒绝。该子集是本组件支持决定，不声称已经覆盖固定工具的全部实际输出。
6. 解码覆盖所有输入接口与原容量槽位、Record / Option、Enum、Fixed 和 Text。只物化活动行及 Some 载荷；Text 等价类以所有自由 Text 符号的规范名称确定顺序，保留已知 literal，分配不碰撞的合成字符串。不得补缺项、去重键、归一化 Unicode 或将模型输出字段用作重放答案。
7. 输出版本化内部 `ModelWorldCandidate`，检查闭合类型、活动值范围、容量和键唯一性，按现行语义键序外部化。P4-A 不声称完整 WF / Pre / 目标已重放；外键与全部 assume 在 P4-B 中统一检查。候选只支持交接到具体重放，不产生 Evidence 五态、证明状态、attempt 或 target gate 凭证。
8. 资源收费先于分配；响应字节、token、深度、整数位数、定义、别名边、类型布局、槽位、物化值、Text 字节与输出字节分别有界。生产严格重建与独立合成材料核对分开，均不等于独立 checker 或形式证明。

精确闭合成员、文法、算法、诊断和验收矩阵见[正式规则](../query/p4-request-response-model-v0.1.md)。

## 影响与接受范围

新增版本化内部请求 / 候选格式和 query0.2 adapter 对应关系；既有语义、IR、P2、四版 query、结构记录、Evidence、registry、execution profiles 和锁定实验材料字节保持。无公共格式迁移、语义命题变更或执行信任放宽。纯 parser 无法认证 stdout 来源；工具与来源身份由调用方声明，真实来源绑定必须由后续执行层完成。

本决定只接受实施 P4-A 与其合成、本机组件验收。P4-B 的五类目标重放、真实 cvc5 校准 / 执行、完整 Evidence v0.2、独立 checker、join / group、双世界、安装、服务、跨仓、提交 / push 和正式实验均不在本决定的授权范围内。

## 验收与停止线

必须展示绑定输入到请求、受支持完整模型到确定性世界候选，以及错配、缺项、冲突、非法活动值和预算拒绝；包含同模型不同定义顺序、Text atom 重命名、稀疏槽位、None 载荷和大整数的手算区分例。覆盖原 AX-B01 三候选、零容量 / 空表、多接口和复合类型，不从候选名称或 expected outcome 决定结果。

真实工具没有校准材料时仍可验收纯组件，但只报告合成协议 / 解码结果。实际固定工具输出超出子集时保留失败，另审阅新 profile；不静默扩大文法、补默认值或追加命令而复用旧 query 摘要。实现与验证按本决定范围单独验收，不因范围接受而提前报告能力完成。
