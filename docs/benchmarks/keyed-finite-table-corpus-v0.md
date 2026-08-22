# 有键有限表基准语料库 v0.1

状态：Accepted

更新日期：2026-08-20

用途：定义 ADR 0002 四个基准的版本化语料目录、生成边界、任务身份、合成数据、候选实现和预期 Evidence 断言格式。

读者：基准维护者、Agent 评测设计者、IR / Evidence 实现者和工具链比较审阅者。

不包含：真实 Axiom Evidence、求解结果、Agent 实验成绩、表面语法、编译器、验证后端或宿主运行时实现。

## 核心结论

- 语料根目录为 [`benchmarks/keyed-finite-table-v0.1/`](../../benchmarks/keyed-finite-table-v0.1/README.md)。
- `corpus.json` 和每个 `task.json` 是机器入口；除目录 README 外的语料内容由 `scripts/generate-benchmark-corpus.py` 确定性生成。
- 每个任务包含合成基础输入、边界输入、无效输入、黄金输出、一个正确候选、两个错误候选和五类预期 Evidence 场景。
- 候选共享同一任务契约、输入接口和输出模式；错误候选只能改变实现 DAG，不能削弱规范。
- Axiom IR 同时提交规范 JCS 字节和 pretty JSON。`.jcs` 是摘要输入；`.json` 只用于审阅，往返后必须恢复相同规范字节。
- Expected Evidence 文件只声明未来真实 Evidence 必须满足的结论、状态、反例类别和 trust / uncovered 下界，不冒充已经运行验证器或独立检查器。

## 版本与摘要

语料格式、任务 manifest、数据和 Expected Evidence assertion 的首版均为 `0.1`。它们是基准资产版本，不是项目 CalVer、语言语义版本、Axiom IR 版本或 Axiom Evidence 版本。

根 manifest 固定：

- 语料版本；
- 采用的语义 SHA-256；
- Axiom IR / Evidence 精确版本；
- 生成脚本路径和原始字节摘要；
- 四个任务 manifest 的路径和原始字节摘要。

任务 identity 使用域 `axiom-benchmark-v0.1:task` 对 benchmark ID、语义摘要、输入 port / table type、输出名称 / table type 和 contract ID 集合内容寻址。候选 IR 文档摘要使用 Axiom IR 自己的文档域。任务 identity 不包含实现节点，因此正确和错误候选必须保持相同任务摘要。

## 文件角色

每个任务目录包含：

- `task.json`：接口、契约、候选、fixture、场景及全部原始文件摘要；
- `candidates/*.ir.jcs`：无 BOM、无额外空白、无末尾换行的 Axiom IR 规范字节；
- `candidates/*.ir.json`：相同抽象值的两空格 pretty 投影；
- `fixtures/*.input.json`：有限合成输入；
- `fixtures/*.golden.json`：有效输入的黄金输出；
- `expected/*.json`：未来 Evidence 的最低断言。

数据文件格式 `axiom-benchmark-data` 使用 `benchmark_id`、`data_version`、`format`、`role` 和按表名排序的 `tables`。行对象必须完整，受对应 IR input / output table type 解释；整数使用十进制字符串，没有隐式 `null`、默认值或类型推断。

Expected Evidence assertion 使用：

- `candidate` 与 `fixtures` 绑定场景；
- `expected_conclusion` 与 `expected_independent_result` 固定最低结论；
- `required_results` 固定必须出现的义务类别、状态及适用的 `unknown` 原因；
- `counterexample` 固定见证类别、最小性标签和必须引用的键 / 字段；
- `required_trust` / `required_uncovered` 固定不能被报告省略的边界。

这些断言不是完整 Evidence schema 的替代，也不允许按断言直接写死最终 Evidence。真实生成器仍须按 Evidence profile 产生完整义务集合，独立检查器必须发现多余、遗漏或错误状态。

## 四个任务

| ID | 正确候选 | 错误候选一 | 错误候选二 | 无效输入 |
| --- | --- | --- | --- | --- |
| AX-B01 | settled 筛选并计算减法净额 | 把减法写成加法 | 丢弃零净额 settled 行 | `discount > subtotal` |
| AX-B02 | 按 `customer_id` 恰好一次连接 | 错按非唯一 `region` 连接 | 把 `tier` 写成常量 | 缺失客户外键 |
| AX-B03 | 按账户计数并求和 | 把全部账户改成同一组 | 先把 `units` 改成 1 再求和 | 重复 `event_id` |
| AX-B04 | 完整行覆盖并只投影公开白名单 | 按敏感邮箱筛选 | 用敏感邮箱派生公开优先级 | 重复 `ticket_id` |

每个任务另有 correct + backend timeout 场景，要求目标核心义务为 `unknown`、结论为 `inconclusive`，用于阻止“无法证明即成功”。

## 生成与校验

写出生成制品：

```bash
python3 scripts/generate-benchmark-corpus.py --write
```

只读重生成并逐字节比较：

```bash
python3 scripts/generate-benchmark-corpus.py --check
```

`./scripts/check-repo.sh` 会执行同一只读检查。生成器只使用 Python 标准库，限制在本语料实际使用的 ASCII、无 JSON number / null 子集；它不是通用 JCS、Axiom IR normalizer、类型检查器、验证器或独立 Evidence checker。

生成器通过构造和重生成检查以下事实：

- 所有类型、节点、契约与文档摘要按已冻结域分离规则计算；
- 无语义顺序数组已规范排序；
- 每个候选引用闭合、无死节点且输出 table type 正确；
- 同一任务的契约、输入接口和输出类型不随候选变化；
- canonical / pretty 投影往返一致；
- task 与 corpus manifest 中的原始字节摘要匹配。

这只能称为确定性语料生成与一致性检查，不能称为语言实现正确性证明。下一阶段的独立原型仍须从提交制品重新解析、生成义务并执行负向拒绝。

## 变更要求

修改任务契约、输入 / 输出模式、候选语义、fixture、黄金输出、Expected Evidence 或生成规则必须提升受影响的语料版本或明确执行受审计迁移，并同步 ADR 0002、语义、IR、Evidence 验证矩阵与当前状态。只修正文档说明且不改变生成字节时可以保持 `0.1`。
