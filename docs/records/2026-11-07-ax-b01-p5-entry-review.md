# AX-B01 P5 入口与样本核对

日期：2026-11-07。基线：`dev` 的 `998ae8e`。

本记录供 P5 实施者复核既有样本的独立期望与组件实测。使用原语料、IR 和宿主制品契约作只读核对。组件范围见 [ADR 0032（Accepted）](../adr/0032-ax-b01-p5-component-entry.md)。

## IR 身份与样本结果

[原始 canonical IR](../../benchmarks/keyed-finite-table-v0.1/ax-b01/candidates/correct.ir.jcs) 的文档 ID 为 `sha256:1fa8846fb3ba15937e3e4b5848e74d84d89050711086d7462eb16175510b4154`，等于现有[最小宿主样本](../../contracts/pipeline-artifacts-v0.1/fixtures/minimal/host-input.jcs)中的 IR 绑定。[已迁移 canonical IR](../../crates/axiom-ir/tests/fixtures/v0.2/migrated/ax-b01-correct.jcs) 的文档 ID 为 `sha256:90d876b9fdd533944e09f4274ba4aaa313d179454427e60eca81575707054f0b`。按各自 `axiom-ir-v<version>:document` 域重算。两份 IR 的 `assume` 定义相等，均要求每条 `orders` 行的 `discount_cents <= subtotal_cents`。v0.2 的契约 ID 为 `sha256:49489c1f3a97fcdc66fa15edb16e44fc274987c6d37d7cd5fdf0e2e190b8a7ae`。

独立核对 `base` 的三行和 `boundary` 的一行均满足前置。按任务说明手算，`base` 黄金输出应为 `O1:900`、`O3:0`，`boundary` 为 `O4:100000`，与原值一致。`invalid` 的 `orders:OX` 以 `101 <= 100` 使前置为假，原始文件摘要为 `sha256:6696f9f034391a5b6b8e15e0dbdcf47eb157fddec3078638074e2f0d92af4805`。[语料清单与原始摘要](../../benchmarks/keyed-finite-table-v0.1/ax-b01/task.json)

| 样本 | `tables` 投影长度 / 原始 SHA-256 | IR v0.1 参考封套长度 / 原始 SHA-256 |
| --- | --- | --- |
| `base.input` | 273 / `cdf75e9fa4b524bf16836e5007f61e80511a9efe98e97eacb4620c330c0a5a8b` | 444 / `c8bffc56c9aaff6e2ccead55cd9d3b0599409f71d6585db2884b4290572e90fb` |
| `base.golden` | 102 / `01e7ded7d2b992d0aa39ff29769c3454ac97212c0252d2f17a2eddcb4b70bc4f` | 274 / `bbe7d677b41f429b02d6da1b7f7b9091efd7e2a7a7383396bcb5ee3350ba96e2` |
| `boundary.input` | 111 / `3dfcac85f47bf6ec8b0bb52385600a5b7870b857c2a36d801b70d65b4ced111d` | 282 / `a5436c6528c62c05d61a28452e643cea053a5c3f2701b19901e8540a3dc8e87d` |
| `boundary.golden` | 71 / `577ad6d2e25fe4a4e50cdf6ab45455c313c30cfaae252be5570e279f227a692a` | 243 / `6e17392e8949bf385dd794578adbd171a4631e26820390cb316f223c066fb237` |

## 复核方法与覆盖

在仓库根运行下列只读命令。制品验证器只复核旧参考封套的结构和规范字节。前置与业务样本的有限核对使用独立的数学比较。四份表投影用来验收组件，四份旧封套用于版本对照。

```bash
python3.14 -I -B - <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path("scripts").resolve()))
from pipeline_artifact_contracts.validation import validate_host_data_bytes

def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("ascii")

def digest(raw):
    return "sha256:" + sha256(raw).hexdigest()

def document(path):
    raw = path.read_bytes()
    ir = json.loads(raw)
    assert encode(ir) == raw
    domain = f"axiom-ir-v{ir['ir_version']}:document".encode("ascii")
    assume = next(c for c in ir["contracts"] if c["definition"]["role"] == "assume")
    return digest(domain + b"\0" + raw), assume

corpus = Path("benchmarks/keyed-finite-table-v0.1")
task = json.loads((corpus / "ax-b01/task.json").read_bytes())
old, old_assume = document(corpus / "ax-b01/candidates/correct.ir.jcs")
new, new_assume = document(Path(
    "crates/axiom-ir/tests/fixtures/v0.2/migrated/ax-b01-correct.jcs"))
assert old != new and old_assume["definition"] == new_assume["definition"]
assert old == next(c["document_digest"] for c in task["candidates"] if c["name"] == "correct")
minimal = Path("contracts/pipeline-artifacts-v0.1/fixtures/minimal/host-input.jcs")
assert validate_host_data_bytes(minimal.read_bytes())["ir_document_digest"] == old
print(old, new, new_assume["id"])

for case in task["fixtures"]:
    rows_by_kind = {}
    for kind, role in (("input", "input"), ("golden", "output")):
        if kind not in case:
            continue
        ref = case[kind]
        raw = (corpus / ref["path"]).read_bytes()
        assert digest(raw) == ref["sha256"]
        tables = json.loads(raw)["tables"]
        table, = tables
        rows = table["rows"]
        keys = [r["order_id"] for r in rows]
        assert keys == sorted(set(keys))
        if case["name"] == "invalid":
            row, = rows
            assert keys == ["OX"] and int(row["discount_cents"]) > int(row["subtotal_cents"])
            print(case["name"], digest(raw))
            continue
        rows_by_kind[kind] = rows
        projection = encode(tables)
        envelope = encode(dict(format="axiom-host-data", format_version="0.1",
                               ir_document_digest=old, role=role, tables=tables))
        assert validate_host_data_bytes(envelope)["tables"] == tables
        print(case["name"], kind, len(projection), digest(projection), len(envelope), digest(envelope))
    if rows_by_kind:
        assert all(int(r["discount_cents"]) <= int(r["subtotal_cents"])
                   for r in rows_by_kind["input"])
        assert [(r["order_id"], int(r["subtotal_cents"]) - int(r["discount_cents"]))
                for r in rows_by_kind["input"] if r["state"] == "settled"] == [
            (r["order_id"], int(r["net_cents"])) for r in rows_by_kind["golden"]]
PY
```

## 组件验证

[P5 组件](../../crates/axiom-ir/src/fixtures.rs)返回绑定 IR v0.2 与原始数据摘要的类型化表值。复用既有 JSON、P1 类型与数学整数实现。每份数据和每项实际解析的前置定义使用显式 JSON 预算，整份 IR 也受输入字节限制。表数按输入或输出方向约束，行数按夹具累计。整数按位数限制，每行每项前置比较收费一次。输出预算统计结果保存的文档 ID、夹具摘要、表名、字段名和标量 UTF-8 字节，JSON 单元数和行数另外约束容器数量。

七项组件测试全部通过。四份原样本的表投影与上表的字节长度和原始摘要一致。同一份 `invalid` 在原 `assume` 下定位 `orders:OX`，反转比较的两个操作数后通过，同时保留原条件则仍拒绝。测试还覆盖表和行的顺序、缺失或重复表、重复键、100 行容量边界、错误身份和角色、非法 JSON 与字段值、黄金输出模式、未支持前置条件和资源耗尽。黄金输出的合规检查只判断其是否满足输出类型，业务值比对归 P8。

本机测试使用显式 Darwin arm64 Rust `1.97.1` 工具链。工作区全目标回归使用 `--locked --offline`，526 项通过，1 项按既有配置忽略。全仓格式、`radishaxiom-ir` 的全目标 / 全 feature Clippy 与仓库检查通过。公共封套配对、生产 `check-fixture`、P6 门控、真实 solver 和宿主执行均留在原验收范围。
