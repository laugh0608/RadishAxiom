# P4-A 请求 / 模型 / 世界候选验收材料

对应 [ADR 0025](../../docs/adr/0025-p4-request-response-model-decoding.md)与[正式规则](../../docs/query/p4-request-response-model-v0.1.md)。本材料只验收纯规划、合成协议解析与候选解码；没有真实 cvc5 输出、尝试、WF / Pre / 目标重放或证明。

`inputs/composite.jcs` 是自有合成 IR v0.2，包含两接口、稀疏容量、100 位数学整数、Fixed、非词法顺序 Enum、嵌套 Option / Record、Unicode 和复合主键。`hand-cases.json` 分别手写完整模型叶赋值与完整预期语义值，保留被遮蔽的非法载荷，固定数学 / Enum / 复合键序和 Text literal / 类关系。二者不是生产输出。生成入口和输入源码摘要见该清单；IR 内容身份只复用既有独立 Python 构造入口。

`inputs/deep-type.jcs` 保留既有合成材料的 5,002 个记录类型，将转换图缩为直接输入输出，以独立验收布局路径与活动世界的深度边界。原深图 / query 材料不改写；这是明确的新合成输入，不能用于声称原超限请求已成功。字段路径只在叶 / Option 标签复制；物化与编码均以显式栈处理，避免随 Record 深度产生平方复制或递归销毁。

Rust 测试从实际 IR / P2 / query 建立请求，把精确 query、符号、布局、请求、合成 stdout、响应观察和候选写入独占任务临时目录。`scripts/check-p4a-model-world.py` 从原 IR 与实际 SMT 声明重建 origin、类型布局、常量 / alias、Text 类、活动世界与键序，再逐字节核对候选，并与手算语义值比较。它不导入 Rust、不读取生产解码结果生成期望，也不重放转换或目标。失败保留目录，成功只删除测试自己创建的精确目录。

既有 P3 三批合成输入另外核对完整接口的空世界，含 Pre=false / fault；成功只说明解码与已做的类型 / 键检查，不说明 WF、Pre 或任何义务成立。AX-B01 原容量 query 另按四个显式 profile 核对请求与 stdin 上限，不缩小容量或改写 query。

拒绝与资源测试覆盖状态 / 模型帧、非零退出、外层终止、UTF-8、缺项 / 重复 / 未知成员、sort、别名环、辅助定义、Text 冲突、活动范围 / Enum、重复键、各阶段预算精确值 / 差一与溢出。旧 P3 字节与支持集合继续由原回归验收。

复现（精确工具已安装，不授权下载）：

```bash
python3 scripts/generate-p4a-model-vectors.py --check
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir solver --lib --locked --offline
```

再生成使用 `python3 scripts/generate-p4a-model-vectors.py`。除本 README 外，目录中的提交产物由该入口维护；临时实际查询和合成响应不提交。独立有限核对、生产 strict 与真实 checker / solver / proof 的验收分别报告。
