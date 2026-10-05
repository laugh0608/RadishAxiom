# 契约身份独立向量

本目录是 P1 局部组件的自有合成验收材料，不是完整 IR、Evidence 或证明成功制品。

- `input.json` / `normalized-input.json`：同一类型 / 节点 / 契约集合的表示变化，覆盖全部五类契约表操作、嵌套量词与 Option 绑定、布尔与数值子式规范化、assume / guarantee 角色、非干扰接口名称排序。名称含 NFC / NFD 和 Unicode scalar / UTF-16 顺序不同的字符，复合主键按 U+10000、U+E000 保留顺序。后者只是已有规范 definition 的测试输入，不代表完整文档入口已验收。
- `base.json`：同一图的空契约版本，供测试插入同域变体；节点 / 输出保留原测试次序。
- `expected.tsv`：具名的 11 项契约、已排序 ID 和规范 definition 字节。含恒 false 公式、无法仅靠类型判定的范围、不同绑定以及同式不同角色，不把内容身份视为公式成立。
- `wrong-hashes.tsv`：遗漏域名 / NUL、错误域名、末尾换行及将 ID 包进摘要的负例。

生成入口为 `scripts/generate-ir-contract-vectors.py`，仅用 Python 标准库，复用既有类型向量的 JCS 子集编码与类型身份 helper。公式规范结构和非干扰名称次序逐例写明，再由 Python `json` / `hashlib` 编码、计算摘要；不调用 Rust 生产 parser、规范器、类型推导器或摘要实现，不实现第二个通用表达式规范器。

从仓库根运行以下命令重生成或核对；生成文件不手工编辑：

```bash
python3 scripts/generate-ir-contract-vectors.py
python3 scripts/generate-ir-contract-vectors.py --check
```

仓库级检查纳入 `--check`。独立向量只验收支持范围内的规范字节与身份，不替代独立 checker、公式 / 非干扰证明或完整 P1 验收。
