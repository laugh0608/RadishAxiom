# 完整 IR 文档字节与身份独立向量

本目录验收现有支持范围内的完整文档组合、strict canonical 检查和文档域摘要；不代表全语义 P1、公式 / 非干扰证明、Evidence 或执行门控验收。

- `node.jcs` / `contract.jcs`：分别组合既有节点 / 契约独立向量的规范 definition，再按 IR 规则排列顶层数组。原始输入继续使用相邻组件目录，不复制第二份。
- `type-input.json` / `type.jcs`：给类型独立向量补上真实 input / output，覆盖名义枚举、嵌套记录 / Option、大整数、复合主键顺序、字段及输出排序，以及引号、反斜线、U+2028、Unicode scalar / UTF-16 的区别。
- `renamed-output.jcs` / `reordered-key.jcs`：同域语义变化，分别改变输出名称、一个输入使用的主键顺序；声明内容身份与节点引用按变化更新。
- `unicode-nfc.jcs` / `unicode-nfd.jcs`：仅一个输出名分别为 `é` / `é`，规范字节和文档身份不同；不合并视觉相同的 Unicode scalar 序列。
- `deep-binders.jcs`：含 122 层量词的完整文档，验证同一 JSON 深度预算下的解析、类型、规范编码与身份路径，不按表容量展开公式。
- `mixed-int-ranges-input.json` / `mixed-int-ranges.jcs`：不同范围 Int 在 filter 与契约四种有序比较中的类型、规范化与身份，包含敏感控制依赖。结构合法不代表公式可满足或得到证明。
- `identities.tsv`：九个完整文档的文档域 ID 与文件原始 SHA-256，两者明确区分。
- `wrong-hashes.tsv`：遗漏文档域 / NUL、错误域、额外换行和误对 pretty 字节计算的对照。
- `candidates.tsv`：从四题 `task.json` 精确提取 12 个候选的规范路径、既有文档摘要与文件摘要；不读取 expected outcome，不重新生成候选。

生成入口为 `scripts/generate-ir-document-vectors.py`。只用 Python 标准库，复用既有类型 / 节点 / 契约向量的明确期望、JCS 子集编码与 `hashlib`；不调用 Rust 生产 parser、规范器或摘要实现。`.jcs` 是无 BOM、额外空白或末尾换行的规范机器字节，其他自有文本使用 LF 与末尾换行。

从仓库根重生成或核对；生成产物不手工修改：

```bash
python3 scripts/generate-ir-document-vectors.py
python3 scripts/generate-ir-document-vectors.py --check
```

仓库检查纳入 `--check`。单个向量或单一宿主结果不能替代独立 checker 或六平台一致性验收；现有 Unsupported 拒绝继续保留。
