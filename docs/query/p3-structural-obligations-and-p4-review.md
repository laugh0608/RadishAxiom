# 剩余结构义务与 P4 接续审阅

日期：2026-10-08。状态：P3-E 已按 [ADR 0023](../adr/0023-core-empty-effect-derivation.md)及[正式规则](core-empty-effects-v0.1.md)完成本机组件验收并提交为 `47e3ff9`；field-origin 的 P3-F 内部分析范围已按 [ADR 0024](../adr/0024-core-field-origin-derivation.md)接受，P4 仍待单独审阅，具体接续以[字段来源与 P4 接口审阅](field-origin-and-p4-interface-review.md)为准。以下保留 P3-E 实施前的审阅推导，不授权外部工具执行。

用途：供项目所有者和实现者决定 P3-D 之后的切片，明确 effect-empty、field-origin 与真实后端的不同依赖。依据为已提交的 P3-D `a008520`、[P2 规则](../evidence/ir-derived-obligations-v0.2.md)、[IR v0.2](../ir/axiom-ir-v0.2.md)与[语义快照](../semantics/keyed-finite-table-semantics-v0.2.md)。不包含生产实现、完整 Evidence、独立 checker 支持或新的证明结果。

## P3-E 实施前的建议顺位

建议下一实施切片为 **P3-E：纯核心空效果的显式结构推导组件**。它从完整规范 IR 重建逐构造空效果规则，绑定原 P2 effect-empty 目标，导出可核对的内部推导记录。该记录不冒充 SMT、kernel-replay support 或公共 Evidence，不产生五态。只检查 `effects = []` 或复用一个 P1 成功标志，均不满足本切片。

field-origin 暂不并入 P3-E：需要先区分显式来源是否合法、保守标签规则是否满足、业务值是否正确和关系非干扰。真实 P4 不以完成所有结构义务为单条 query 尝试的技术前提，但新旧 adapter / artifact 集成和实际执行条件必须先闭合；完整 Evidence 仍要求所有必需义务有合法支持。

不建议继续把每种义务都加入 query profile。结构推导与 SMT 查询分别保留入口，不能发出恒假查询借后端 `unsat` 代替尚未定义的规则，也不能删除 P2 中的 prove 位置或改成 check。

## 实际清单与证据等级

只读重跑既有 `scripts/generate-p3-query-review.py` 的 `coverage()`：该函数逐项核对 26 份 IR / P2 文件的 raw digest、完整 IR 身份与义务数量。本次统计如下；形状内只表示符合现有 query 整图功能集合，不是推导成功、资源验收或证明：

| 目标 | 全部位置 | query 功能形状内 |
| --- | --- | --- |
| effect-empty | 26 | 14 |
| field-origin | 161 | 98 |
| ir-structure（check） | 26 | 14 |

v0.4 的实际验收为 151 查询、1 资源拒绝、197 UnsupportedKind、107 UnsupportedFeature、26 check；197 项未支持 kind 恰为 26 effect-empty、161 field-origin、6 group-conservation、4 noninterference。不能将“功能形状内 14 份”当作空效果规则的语义边界：join / group / 有限量化同样属于已接受的纯核心，结构推导无需展开表容量。

AX-B01 correct / wrong-add / wrong-drop-zero 各有 13 项 P2 义务：9 项属于现有五类 query，另有 1 effect-empty、2 field-origin、1 ir-structure。P3-E 即使完成，也只补充空效果推导，不完成这 13 项的真实生产结果，更不完成 P0–P9。

复现本节清单的只读命令：

```bash
python3 - <<'PY'
from collections import Counter
import runpy
rows = runpy.run_path('scripts/generate-p3-query-review.py')['coverage']()
for label, selected in [('all', rows), ('query-shape', [r for r in rows if not r['blockers']])]:
    counts = Counter(o['kind'] for r in selected for o in r['obligations'])
    print(label, len(selected), dict(sorted(counts.items())))
PY
```

## 空效果：可接受的最小实施范围

[声明检查](../../crates/axiom-ir/src/declarations.rs)已拒绝非空 effects；[契约检查](../../crates/axiom-ir/src/contracts.rs)与表达式 / 节点检查只接受闭合纯核心。依据足够支持规则推导，但目前没有导出的 effect-empty 规则记录、独立材料核对或可消费的证明 support。

拟接受的输入是 IR v0.2 CanonicalDocument、严格匹配的完整 ir-derived ObligationSet、effect-empty 目标 ID、显式生成器身份与资源预算。支持全部已接受 P1 v0.2 构造，不因 query 的 join / group / 量化限制而拒绝纯语法推导；不增加任何新 IR 操作。旧 IR 仍先显式迁移。

| 推导层 | 必须核验的前提 | 不可偷换的结论 |
| --- | --- | --- |
| 字面值、合法 bound / field 引用 | 精确 tag、闭合成员、绑定环境；只引用显式记录或值 | 字段值来自已声明输入，不保证现实来源可信 |
| 算术、比较、Bool、Record、Option 与分支 | 按每个构造的精确子项表覆盖全部子树；未知 tag / 成员拒绝；条件两分支均纳入静态效果推导 | 空效果不说明算术无故障或程序 totality；不借不可达分支跳过未知能力 |
| 契约表读取、lookup、有限量化与聚合公式 | 只读取已经物化的显式接口；绑定与所有公式子项闭合 | 读取接口不是文件 / 网络 IO；公式真假和范围另行验证 |
| input / filter / map / lookup_join / group | 输入为物化表；精确前驱、表达式、键 / 聚合字段与节点规则闭合 | 节点纯性不保证覆盖、连接恰好一次、标签或守恒成立 |
| 文档 | effects 恰为空；全部节点与契约均有推导；命名输出绑定到文档节点 | 只约束语言核心，不约束编译器、solver、输入采集或宿主进程的外围效果 |

实现前在新 ADR / 正式规则中列出闭合规则 ID 和各构造子项；不能把通用 JSON 遍历遇到的任意 `op` 当作完整语义验证。规范路径从规范节点 / 契约根出发，图前驱按 ID 引用，表达式位置按路径引用；共享图不展开成树，同一表达式出现在不同位置不能无依据合并。无论 Pre 是否可满足、容量是否为零，结构效果均按全构造检查。

内部推导记录拟单独版本化，绑定 IR raw / document digest、语义、完整 P2 集合、目标、规则版本与生成器身份；内容为确定顺序的规则步骤和前提引用。具体成员与规范字节须随正式规则一次冻结，不借用 `EncodedQuery` 或向旧 query 添加伪命令。生产 strict 检查重建完整记录，拒绝遗漏、重复、额外、错误规则 / 路径 / 引用和字节篡改，不修补后报告成功。

预算至少覆盖 IR JSON、步骤、前提边、规范路径字节和输出字节，先收费后分配，累加溢出等同资源拒绝。资源用量随 IR 构造规模增长，不随表容量或所有输入世界展开；深图用迭代路径。此预算不声称 OS 硬内存保证。

验收至少包含：现有 26 份 IR（包括 join / group 与全部契约形式）、补足未出现的合法构造、未知外部调用 / 非空效果 / 隐藏成员负例、遗漏分支与契约、错误来源 / 目标绑定、重复或缺失步骤、前向错误引用、零 / 巨大容量、深共享图及全部预算精确值 / 差一。Python 独立验收器按明确规则重建步骤，不调用 Rust 生成器，也不读取生产成功标志作为期望。它核验的是本批规则与记录；完整 P1 类型正确性仍须明确为输入前提，不能宣称已有跨仓独立证明链。

成功只交付“规则推导记录及核对通过”的内部组件事实。将其接入 `kernel-replay`，仍需完整 Evidence v0.2 的 support / execution 规则、独立 checker 规则集合与真实复核；不能仅靠本生产实现自检填 `proved`。

## field-origin：先明确目标，再选择支持路径

现有 [NodeFlowAnalysis](../../crates/axiom-ir/src/nodes/flow.rs)保存 row_control、field_labels 和 label_gaps；field_labels 是声明与推导的上确界，并不是精确来源集合，label_gaps 也不是完整的传递依赖路径。filter 传递字段标签，同时单独提升行控制标签；map 的本地缺口不能代表整条前驱链的全部约束。

后续最小提案必须逐项规定：允许来源由实际 IR 绑定环境决定，还是增加任务白名单；输出接口别名及顶层复合字段如何绑定；值依赖、行存在性、关联选择、故障观察分别进入哪项义务；上游标签缺口如何追踪；分支是否仅作保守并集。当前 IR 没有新的任务白名单字段，不能从 benchmark expected outcome 猜一个策略再塞入 P2 同一 ID。

| 区分例 | 可以得出的判断 | 不能据此宣布 |
| --- | --- | --- |
| AX-B01 wrong-add 读取合法字段但用了错误算术 | IR 来源可合法，业务等式需由 guarantee 检验 | 来源合法即业务正确 |
| wrong-drop-zero 忠实执行额外筛选 | 相对实际谓词的内建 coverage 可以成立；原业务保留要求由 guarantee 定位 | 原内建 row-coverage 必然失败 |
| 输出公开字段前按 sensitive 条件 filter | 字段值标签可不变，row_control 升高 | 无本地 label gap 即非干扰成立 |
| `if sensitive then 0 else 0` | 保守分析仍可能得到 sensitive；必须说明选择的是静态上界规则还是双世界值等价 | 保守缺口天然提供具体泄漏见证 |
| Record 未读取的兄弟字段故障、敏感算术故障 | 严格求值 / 终止观察需由相关语义单独覆盖 | 只检查字段投影足以证明全部安全目标 |

建议未来 field-origin 先定义可重建的来源 / 静态标签规则及其适用范围，保留 contract-guarantee 和 noninterference 的独立目标。若将保守上界作为充分条件，无法导出不能直接写为 `failed`；若选择把某项静态规则本身作为命题，必须明确结构违例的支持形式，不能伪造数据世界。任何改变原命题或拒绝集合的选择，均按 P2 版本约束重新审阅，不能原地改旧 definition / ID 含义。

## P4：可以先做什么，真实执行还缺什么

| 层级 | 可以形成的交付 | 保留的前置 |
| --- | --- | --- |
| 本仓纯协议组件 | 对精确 query / binding 建立后端请求描述、响应严格解析、模型到输入世界的解码与目标重放设计；合成响应可测协议拒绝 | 需另行接受范围；模拟 stdout 不是实际 attempt / timeout / unsat |
| 单目标真实尝试 | 已支持的一条 query 的真实 cvc5 响应、资源结果与重放观察 | 新 artifact / adapter 精确对应、来源 / 许可 / payload 验收、执行宿主及 OS hard memory / deadline、当前任务执行授权 |
| AX-B01 完整验证 | 三候选全部必需义务及 invalid / timeout / 篡改路径 | field-origin / effect 的支持、ir-structure check、完整 Evidence v0.2 与真实执行绑定；不能以九条 query 的子集声明完整验证 |
| P6–P9 与独立复核 | 门控、Node、输出一致、Evidence / receipt 和独立结果 | 各自精确版本与验收，不能沿用 checker 宿主授权替 solver / Node 开门 |

当前 query 制品为 `axiom-smtlib2-qf-uflia-query0.2`，末尾只有 check-sat，没有 model / proof 请求；旧 ADR 0007 / cvc5 adapter 对应旧公共管线。P4 必须规定如何绑定 query 原始字节、附加交互与响应，不能追加请求后仍声称是原查询摘要。Input / Text 符号映射也是模型解释必需输入；未解释 Text 的等价类须还原为精确已知字面值或彼此区分的新字符串，并保留 Unicode 差异、活动槽位、Option 掩码和数学整数。缺失或不一致模型不得补默认成功。

`sat` 只表示候选模型；解码后独立检查 WF、Pre 与声明的目标违反，其他义务失败不能顶替目标。`unsat` 的 attestation / certificate policy、timeout / crash / 截断 / 协议错误区分遵循 [ADR 0007](../adr/0007-first-verification-first-compilation-pipeline.md)，未执行不产生 unknown。完整新 Evidence 继续受 [ADR 0009](../adr/0009-axiom-evidence-v0-drift-and-migration.md)约束。

仓库的 cvc5 adapter / payload 登记仍未形成当前主机执行验收；本次只核对仓库材料，未检查联网最新版本或本机安装状态。不能因 P3-E 无 solver 依赖，再次把所有工作串行阻塞到工具安装：P3-E 之后应转入 field-origin 精确提案与 P4 adapter / replay 接口审阅，分别解决语义与执行缺口，不新增通用框架或无上限取证链。

## 已接受的 P3-E 精确范围

只接受 P3-E 空效果结构推导内部组件：全部现有 P1 v0.2 纯构造、独立版本化推导记录、原 P2 绑定、明确预算、生产 strict 与独立有限验收。正式 ADR / 规则已形成，保持旧 IR / P2 / query / Evidence / adapter 规范和材料原字节。field-origin 正式命题、公共 kernel / certificate 支持、P4 执行及外部动作不包含在该接受范围。
