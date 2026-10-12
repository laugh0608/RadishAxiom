#!/usr/bin/env python3
"""P4-A 自有合成输入与手算叶 / 业务值；不运行或导入生产实现。"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "contracts/solver-model-v0.1"
IR = runpy.run_path(str(ROOT / "scripts/generate-ir-v02-vectors.py"))


def raw(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def build():
    identified, field, record_type = IR["identified"], IR["field"], IR["record_type"]
    enum = identified("enum-type", {"name": "Order", "members": ["z", "a", "é"]})
    enum_ty = {"kind": "enum", "enum_type": enum["id"]}
    positive = {"kind": "int", "lower": "1", "upper": "9"}
    option = lambda ty: {"kind": "option", "inner": ty}
    leaf = record_type([field("mark", IR["TEXT"]), field("maybe", option(option(positive)))])
    row = record_type([
        field("big", {"kind": "int", "lower": "-" + "9" * 100, "upper": "9" * 100}),
        field("fixed", {"kind": "fixed", "scale": "7", "lower": "-1000", "upper": "1000"}),
        field("flag", IR["BOOL"]), field("key", {"kind": "int", "lower": "-100", "upper": "100"}),
        field("mode", enum_ty), field("nested", option({"kind": "record", "record_type": leaf["id"]})),
        field("option", option(enum_ty)), field("text", IR["TEXT"]), field("音", IR["TEXT"]),
    ])
    other = record_type([field("key", IR["BOOL"])])
    table = identified("table-type", {"record_type": row["id"], "primary_key": ["key", "mode", "text"], "capacity": "5"})
    second = identified("table-type", {"record_type": other["id"], "primary_key": ["key"], "capacity": "2"})
    first_node = identified("node", {"kind": "input", "port": "in", "table_type": table["id"]})
    second_node = identified("node", {"kind": "input", "port": "另一路", "table_type": second["id"]})
    # 每种已知 literal 出现在完整绑定契约；不以该契约真假决定模型 / 世界。
    literals = ["", "@axiom-text:0:0", "e\u0301", "é"]
    formula = {"op": "and", "values": [{"op": "eq", "left": {"op": "literal_text", "value": v}, "right": {"op": "literal_text", "value": ""}} for v in literals]}
    base = json.loads((ROOT / "contracts/map-filter-query-v0.1/inputs/minimal.jcs").read_bytes())
    document = IR["ordered_document"]({**base, "enum_types": [enum], "record_types": [leaf, row, other], "table_types": [table, second], "nodes": [first_node, second_node], "outputs": [{"name": "out", "node": first_node["id"]}], "contracts": [identified("contract", IR["normal_expression"]({"kind": "formula", "role": "guarantee", "expression": formula}))]})
    huge = "8" * 100
    # 完整组件顺序由规则手算：big,fixed,flag,key,mode,nested-tag,mark,maybe-tag,inner-tag,int,option-tag,enum,text,音。
    slots = [
        {"active": True, "values": [huge, "7", "true", "10", "0", "true", "@Text_20", "true", "false", "999", "false", "999", "@Text_3", "@Text_21"]},
        {"active": False, "values": ["999", "999", "false", "999", "999", "true", "@Text_22", "true", "true", "999", "true", "999", "@Text_22", "@Text_22"]},
        {"active": True, "values": [f"(- {huge})", "(- 7)", "false", "(- 2)", "1", "false", "@Text_23", "false", "false", "999", "true", "2", "@Text_20", "@Text_0"]},
        {"active": True, "values": ["0", "0", "false", "(- 10)", "2", "true", "@Text_2", "true", "true", "2", "true", "0", "@Text_2", "@Text_21"]},
        {"active": True, "values": ["0", "0", "true", "10", "1", "false", "@Text_23", "false", "true", "999", "false", "999", "@Text_3", "@Text_0"]},
    ]
    fresh = lambda atom: {"text-class": atom}
    # 与上面模型列分别手写的完整语义值，行序是 -10,-2,10(z),10(a)，不是词法 / 槽位序。
    expected = [
        {"big": "0", "fixed": "0", "flag": False, "key": "-10", "mode": "é", "nested": {"some": {"mark": "e\u0301", "maybe": {"some": {"some": "2"}}}}, "option": {"some": "z"}, "text": "e\u0301", "音": fresh("@Text_21")},
        {"big": "-" + huge, "fixed": "-7", "flag": False, "key": "-2", "mode": "a", "nested": None, "option": {"some": "é"}, "text": fresh("@Text_20"), "音": ""},
        {"big": huge, "fixed": "7", "flag": True, "key": "10", "mode": "z", "nested": {"some": {"mark": fresh("@Text_20"), "maybe": {"some": None}}}, "option": None, "text": "é", "音": fresh("@Text_21")},
        {"big": "0", "fixed": "0", "flag": True, "key": "10", "mode": "a", "nested": None, "option": None, "text": "é", "音": ""},
    ]
    cases = {"format": "axiom-p4a-synthetic-hand-cases", "version": "0.1", "input": "inputs/composite.jcs", "literal_atoms": {v: f"@Text_{i}" for i, v in enumerate(literals)}, "slots": {"in": slots, "另一路": [{"active": False, "values": ["true"]}, {"active": True, "values": ["false"]}]}, "expected_rows": {"in": expected, "另一路": [{"key": False}]}}
    sources = ["scripts/generate-p4a-model-vectors.py", "scripts/check-p4a-model-world.py", "scripts/generate-ir-v02-vectors.py", "docs/adr/0025-p4-request-response-model-decoding.md", "docs/query/p4-request-response-model-v0.1.md", "contracts/map-filter-query-v0.1/inputs/minimal.jcs"]
    cases["sources"] = [{"path": p, "raw_digest": raw((ROOT / p).read_bytes())} for p in sources]
    deep_source = "contracts/map-filter-query-v0.1/resource-inputs/deep-type-and-graph.jcs"
    deep = json.loads((ROOT / deep_source).read_bytes())
    node = next(n for n in deep["nodes"] if n["definition"]["kind"] == "input")
    deep = IR["ordered_document"]({**deep, "nodes": [node], "outputs": [{"name": "out", "node": node["id"]}], "contracts": [identified("contract", {"kind": "formula", "role": "guarantee", "expression": IR["YES"]})]})
    cases["sources"].append({"path": deep_source, "raw_digest": raw((ROOT / deep_source).read_bytes())})
    return {"inputs/composite.jcs": IR["canonical"](document).encode(), "inputs/deep-type.jcs": IR["canonical"](deep).encode(), "hand-cases.json": (json.dumps(cases, ensure_ascii=False, indent=2) + "\n").encode()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, data in build().items():
        target = DEST / path
        if args.check:
            if not target.exists() or target.read_bytes() != data:
                raise SystemExit(f"P4-A vector drift: {path}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    print("P4-A synthetic vectors passed" if args.check else "P4-A synthetic vectors written")
