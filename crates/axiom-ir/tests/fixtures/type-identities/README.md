# 类型声明身份向量

输入均为仓库自有合成材料。生成入口与完整合成输入定义在 `scripts/generate-ir-type-vectors.py`，无网络、第三方数据或 Rust 生产 helper。从仓库根运行：

```bash
python3 scripts/generate-ir-type-vectors.py
python3 scripts/generate-ir-type-vectors.py --check
```

Python 标准库 `json` 独立编码、`hashlib.sha256` 计算域分离摘要；键按 UTF-16 排序，记录字段按 Unicode scalar 排序。算法与字节规则仍以 IR v0.1 为准，本脚本仅为这些明确合成输入生成期望，不是另一份生产 IR 验证器。

- `input.json`：两种枚举、两种记录和三种表；覆盖所有值类型、嵌套引用、超机器范围整数、转义与 Unicode scalar 排序。
- `permuted.json`：同一声明抽象值，反转对象成员、声明和记录字段顺序，改用 Unicode 转义与不同缩进；不改变枚举成员或主键顺序。
- `expected.tsv`：每行为声明类别、内容 ID、规范 definition，三个字段用 tab 分隔；类别内按 ID 排序。规范 JSON 本身不含实际 tab / 换行。
- `wrong-hashes.tsv`：独立计算的错误摘要构造（漏域名、漏 NUL、错误域名、额外换行、把 ID 包进摘要），用于证明这些规则不能互换。

这些文档故意没有 input / output，**不是完整合法 IR 示例**。只用于声明组件的身份、规范化与拒绝路径验收；不属于正式基准或 Evidence。
