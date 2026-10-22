# 表达式与节点身份独立向量

本目录是 P1 局部组件的合成验收材料，不是完整 IR、Evidence 或证明成功制品。

- `expressions.tsv`：具名输入及人工指定的规范表达式结构，覆盖布尔展平 / 排序 / 去重、相等与加法排序、有语义顺序和精确 Unicode。
- `input.json` / `normalized-input.json`：同一节点图的表示变化，包含五类节点、乱序字段 / pairs / aggregates、嵌套重复布尔式，以及 Unicode scalar 与 UTF-16 排序不同的名称。group keys 顺序保留。二者只用于节点规范化验收，不核准契约或完整文档。
- `expected.tsv`：按 ID 排序的规范节点 definition 字节及内容 ID。
- `wrong-hashes.tsv`：遗漏域名 / NUL、错误域名、末尾换行及将 ID 包进摘要的负例。

生成入口为 `scripts/generate-ir-node-vectors.py`，仅用 Python 标准库，复用既有 `scripts/generate-ir-type-vectors.py` 的 JSON / 类型向量 helper。表达式期望逐例指定、节点期望 definition 显式组装，再由 Python `json` / `hashlib` 编码和计算摘要；不调用 Rust 生产 parser、规范器或摘要实现，不根据候选名称推断正确性。

从仓库根运行以下命令重生成或核对；生成文件不手工编辑：

```bash
python3 scripts/generate-ir-node-vectors.py
python3 scripts/generate-ir-node-vectors.py --check
```

仓库级检查纳入 `--check`。这些向量检验局部规范字节与身份，不构成独立 checker 或形式证明，也不补全现有表达式未支持范围。
