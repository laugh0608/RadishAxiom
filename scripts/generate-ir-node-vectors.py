#!/usr/bin/env python3
"""生成表达式 / 节点身份独立向量；期望结构逐例指定，不调用 Rust 或生产规范器。"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "crates/axiom-ir/tests/fixtures/node-identities"
# 复用已有测试生成器的 JCS 子集编码与类型身份构造，不引入第二套编码口径。
TYPE_VECTORS = runpy.run_path(str(ROOT / "scripts/generate-ir-type-vectors.py"))
canonical = TYPE_VECTORS["canonical"]
entry = TYPE_VECTORS["entry"]
field = TYPE_VECTORS["field"]


def expression_vectors():
    a = {"op": "literal_bool", "value": False}
    b = {"op": "literal_bool", "value": True}
    both = {"op": "and", "values": [a, b]}
    nested = {"op": "and", "values": [b, {"op": "and", "values": [b, a]}, a]}
    int_type = {"kind": "int", "lower": "0", "upper": "100"}
    one, two, ten = [{"op": "literal_int", "type": int_type, "value": n} for n in ["1", "2", "10"]]
    fixed_type = {"kind": "fixed", "scale": "2", "lower": "0", "upper": "100"}
    fixed_two, fixed_ten = [{"op": "literal_fixed", "type": fixed_type, "coefficient": n} for n in ["2", "10"]]
    cases = [
        ("and-flatten", nested, both),
        ("or-singleton", {"op": "or", "values": [a, {"op": "or", "values": [a, a]}]}, a),
        ("mixed-connectives", {"op": "and", "values": [b, {"op": "or", "values": [b, a, b]}]},
         {"op": "and", "values": [b, {"op": "or", "values": [a, b]}]}),
        ("eq-order", {"op": "eq", "left": b, "right": a}, {"op": "eq", "left": a, "right": b}),
        ("int-add-lexical", {"op": "int_add", "result_type": int_type, "values": [two, ten]},
         {"op": "int_add", "result_type": int_type, "values": [ten, two]}),
        ("int-add-duplicates", {"op": "int_add", "result_type": int_type, "values": [one, one]},
         {"op": "int_add", "result_type": int_type, "values": [one, one]}),
        ("fixed-add-lexical", {"op": "fixed_add", "result_type": fixed_type, "values": [fixed_two, fixed_ten]},
         {"op": "fixed_add", "result_type": fixed_type, "values": [fixed_ten, fixed_two]}),
        ("sub-order", {"op": "int_sub", "result_type": int_type, "left": two, "right": one},
         {"op": "int_sub", "result_type": int_type, "left": two, "right": one}),
        ("lt-order", {"op": "lt", "left": two, "right": one}, {"op": "lt", "left": two, "right": one}),
        ("if-no-evaluation", {"op": "if", "condition": b, "then": nested, "else": a, "result_type": {"kind": "bool"}},
         {"op": "if", "condition": b, "then": both, "else": a, "result_type": {"kind": "bool"}}),
        ("match-binder", {"op": "match_option", "subject": {"op": "some", "value": b}, "none": nested,
                          "some": {"op": "bound", "index": "0"}, "result_type": {"kind": "bool"}},
         {"op": "match_option", "subject": {"op": "some", "value": b}, "none": both,
          "some": {"op": "bound", "index": "0"}, "result_type": {"kind": "bool"}}),
        ("unicode-exact", {"op": "literal_text", "value": "é e\u0301 \ue000 \U00010000 \n"},
         {"op": "literal_text", "value": "é e\u0301 \ue000 \U00010000 \n"}),
    ]
    return "".join(f"{name}\t{json.dumps(raw, ensure_ascii=True)}\t{canonical(expected)}\n"
                   for name, raw, expected in cases), nested, both


def node(definition):
    raw = b"axiom-ir-v0.1:node\0" + canonical(definition).encode()
    return {"definition": definition, "id": "sha256:" + hashlib.sha256(raw).hexdigest()}


def read_field(name, index="0"):
    return {"op": "field", "field": name, "record": {"op": "bound", "index": index}}


def artifacts():
    expressions, raw_predicate, expected_predicate = expression_vectors()
    source_record = entry("record", {"fields": [
        field("\U00010000", {"kind": "text"}), field("\ue000", {"kind": "text"}),
        field("flag", {"kind": "bool"}), field("units", {"kind": "int", "lower": "0", "upper": "10"}),
    ]})
    group_record = entry("record", {"fields": [
        field("\U00010000", {"kind": "text"}), field("\ue000", {"kind": "text"}),
        field("count", {"kind": "int", "lower": "0", "upper": "4"}),
        field("sum", {"kind": "int", "lower": "0", "upper": "40"}),
    ]})
    source_table, group_table = [entry("table", {"capacity": "4", "primary_key": ["\U00010000", "\ue000"],
                                                "record_type": record["id"]}) for record in [source_record, group_record]]
    first, second = [node({"kind": "input", "port": port, "table_type": source_table["id"]})
                     for port in ["source", "reference"]]
    filtered = node({"kind": "filter", "predicate": expected_predicate, "source": first["id"], "table_type": source_table["id"]})
    fields = [{"name": name, "expression": read_field(name)} for name in ["flag", "units", "\ue000", "\U00010000"]]
    mapped = node({"kind": "map", "fields": fields, "source": filtered["id"], "table_type": source_table["id"]})
    joined = node({"kind": "lookup_join", "left": mapped["id"], "right": second["id"], "table_type": source_table["id"],
                   "pairs": [{"left": name, "right": name} for name in ["\ue000", "\U00010000"]],
                   "fields": [{"name": name, "expression": read_field(name, "1" if name == "flag" else "0")}
                              for name in ["flag", "units", "\ue000", "\U00010000"]]})
    grouped = node({"kind": "group", "source": joined["id"], "table_type": group_table["id"],
                    "keys": [{"name": name, "source_field": name} for name in ["\U00010000", "\ue000"]],
                    "aggregates": [{"kind": "count", "name": "count"}, {"kind": "sum", "field": "units", "name": "sum"}]})
    nodes = [first, second, filtered, mapped, joined, grouped]
    document = {
        "contracts": [], "digest_algorithm": "sha-256", "effects": [], "enum_types": [],
        "format": "axiom-ir", "ir_version": "0.1", "nodes": list(reversed(nodes)),
        "outputs": [{"name": "result", "node": grouped["id"]}],
        "record_types": [source_record, group_record], "table_types": [source_table, group_table],
        "semantics": {"name": "keyed-finite-table-semantics", "sha256": TYPE_VECTORS["SEMANTICS"]},
    }
    permuted = copy.deepcopy(document)
    for item in permuted["nodes"]:
        definition = item["definition"]
        if definition["kind"] == "filter":
            definition["predicate"] = raw_predicate
        for key in ["fields", "pairs", "aggregates"]:
            if key in definition:
                definition[key].reverse()
    definition_bytes = canonical(grouped["definition"]).encode()
    wrong = {
        "raw-definition": definition_bytes,
        "missing-nul": b"axiom-ir-v0.1:node" + definition_bytes,
        "wrong-domain": b"axiom-ir-v0.1:table-type\0" + definition_bytes,
        "extra-newline": b"axiom-ir-v0.1:node\0" + definition_bytes + b"\n",
        "including-id": b"axiom-ir-v0.1:node\0" + canonical(grouped).encode(),
    }
    return {
        "input.json": json.dumps(permuted, ensure_ascii=True, indent=2) + "\n",
        "normalized-input.json": json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        "expressions.tsv": expressions,
        "expected.tsv": "".join(f"{item['id']}\t{canonical(item['definition'])}\n" for item in sorted(nodes, key=lambda item: item["id"])),
        "wrong-hashes.tsv": "".join(f"{name}\t{grouped['id']}\tsha256:{hashlib.sha256(data).hexdigest()}\n"
                                    for name, data in wrong.items()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只核对已提交字节，不改文件")
    args = parser.parse_args()
    for name, content in artifacts().items():
        path = DESTINATION / name
        data = content.encode("utf-8")
        if args.check:
            if not path.exists() or path.read_bytes() != data:
                raise SystemExit(f"fixture drift: {path.relative_to(ROOT)}")
        else:
            DESTINATION.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print("IR node / expression vectors match" if args.check else "IR node / expression vectors generated")


if __name__ == "__main__":
    main()
