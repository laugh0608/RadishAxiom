#!/usr/bin/env python3
"""生成契约身份独立向量；逐例写明规范结构，不调用 Rust 或通用表达式规范器。"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "crates/axiom-ir/tests/fixtures/contract-identities"
TYPE_VECTORS = runpy.run_path(str(ROOT / "scripts/generate-ir-type-vectors.py"))
canonical = TYPE_VECTORS["canonical"]
entry = TYPE_VECTORS["entry"]
field = TYPE_VECTORS["field"]


def identified(kind, definition):
    data = f"axiom-ir-v0.1:{kind}\0".encode() + canonical(definition).encode()
    return {"id": "sha256:" + hashlib.sha256(data).hexdigest(), "definition": definition}


def read_field(name, index="0"):
    return {"op": "field", "field": name, "record": {"op": "bound", "index": index}}


def artifacts():
    yes = {"op": "literal_bool", "value": True}
    no = {"op": "literal_bool", "value": False}
    raw_bool = {"op": "and", "values": [yes, {"op": "and", "values": [yes, no]}, no]}
    normalized_bool = {"op": "and", "values": [no, yes]}
    integer = {"kind": "int", "lower": "0", "upper": "10"}
    fixed = {"kind": "fixed", "scale": "2", "lower": "0", "upper": "100"}
    record = entry("record", {"fields": [field("flag", {"kind": "bool"}),
                                         field("units", integer), field("price", fixed),
                                         field("\U00010000", {"kind": "text"}),
                                         field("\ue000", {"kind": "text"})]})
    table = entry("table", {"capacity": "4", "primary_key": ["\U00010000", "\ue000"],
                            "record_type": record["id"]})
    ports = ["source", "é", "e\u0301", "\U00010000", "\ue000"]
    inputs = [identified("node", {"kind": "input", "port": port, "table_type": table["id"]})
              for port in ports]
    filtered = identified("node", {"kind": "filter", "source": inputs[0]["id"],
                                   "predicate": normalized_bool, "table_type": table["id"]})
    outputs = [{"name": "result", "node": filtered["id"]}] + [
        {"name": port, "node": node["id"]} for port, node in zip(ports[1:], inputs[1:])]
    source = {"kind": "input", "name": "source"}
    result = {"kind": "output", "name": "result"}
    cases = []

    def formula(name, role, raw, expected):
        cases.append((name, {"kind": "formula", "role": role, "expression": raw},
                      {"kind": "formula", "role": role, "expression": expected}))

    formula("forall-assume", "assume", {"op": "forall_rows", "table": source, "body": raw_bool},
            {"op": "forall_rows", "table": source, "body": normalized_bool})
    # forall -> exists -> match.some：绑定 0 为 lookup 行，1 为 output 行，2 为 input 行。
    # lookup.keys 在 match 新绑定外求值；目标主键顺序 U+10000、U+E000 不可重排。
    raw_match = {"op": "match_option", "result_type": {"kind": "bool"}, "none": no,
                 "subject": {"op": "lookup", "table": source,
                             "keys": [read_field("\U00010000", "1"), read_field("\ue000", "0")]},
                 "some": {"op": "eq", "left": read_field("flag", "2"), "right": read_field("flag", "0")}}
    expected_match = copy.deepcopy(raw_match)
    expected_match["some"] = {"op": "eq", "left": read_field("flag", "0"), "right": read_field("flag", "2")}
    for name, binding in [("nested-lookup", "2"), ("different-binding", "1")]:
        raw = copy.deepcopy(raw_match)
        expected = copy.deepcopy(expected_match)
        raw["some"]["left"]["record"]["index"] = binding
        expected["some"]["right"]["record"]["index"] = binding
        formula(name, "guarantee",
                {"op": "forall_rows", "table": source, "body": {"op": "exists_rows", "table": result, "body": raw}},
                {"op": "forall_rows", "table": source, "body": {"op": "exists_rows", "table": result, "body": expected}})
    count_type = {"kind": "int", "lower": "0", "upper": "4"}
    raw_count = {"op": "count_where", "table": result, "predicate": raw_bool, "result_type": count_type}
    expected_count = {**raw_count, "predicate": normalized_bool}
    literal_count = {"op": "literal_int", "type": count_type, "value": "0"}
    formula("count", "guarantee", {"op": "eq", "left": literal_count, "right": raw_count},
            {"op": "eq", "left": expected_count, "right": literal_count})
    one = {"op": "literal_int", "type": integer, "value": "1"}
    raw_add = {"op": "int_add", "result_type": integer, "values": [one, read_field("units")]}
    expected_add = {**raw_add, "values": [read_field("units"), one]}
    sum_type = {"kind": "int", "lower": "0", "upper": "80"}
    raw_sum = {"op": "sum_where", "table": source, "predicate": raw_bool, "value": raw_add, "result_type": sum_type}
    expected_sum = {**raw_sum, "predicate": normalized_bool, "value": expected_add}
    literal_sum = {"op": "literal_int", "type": sum_type, "value": "0"}
    formula("sum-int", "guarantee", {"op": "eq", "left": raw_sum, "right": literal_sum},
            {"op": "eq", "left": literal_sum, "right": expected_sum})
    two, ten = [{"op": "literal_fixed", "type": fixed, "coefficient": n} for n in ["2", "10"]]
    raw_fixed = {"op": "sum_where", "table": source, "predicate": yes, "result_type": fixed,
                 "value": {"op": "fixed_add", "values": [two, ten], "result_type": fixed}}
    expected_fixed = {**raw_fixed, "value": {"op": "fixed_add", "values": [ten, two], "result_type": fixed}}
    formula("sum-fixed", "guarantee", {"op": "eq", "left": raw_fixed, "right": two},
            {"op": "eq", "left": two, "right": expected_fixed})
    # 公式真值、常量条件与数学范围不由规范器证明或求值。
    formula("false-guarantee", "guarantee", {"op": "or", "values": [no, no]}, no)
    formula("false-assume", "assume", no, no)
    raw_if = {"op": "if", "condition": yes, "then": raw_bool, "else": read_field("flag"), "result_type": {"kind": "bool"}}
    expected_if = {**raw_if, "then": normalized_bool}
    formula("exists-if", "guarantee", {"op": "exists_rows", "table": result, "body": raw_if},
            {"op": "exists_rows", "table": result, "body": expected_if})
    formula("range-obligation", "guarantee",
            {"op": "eq", "left": {**raw_count, "result_type": {"kind": "int", "lower": "1", "upper": "1"}},
             "right": {"op": "literal_int", "type": {"kind": "int", "lower": "1", "upper": "1"}, "value": "1"}},
            {"op": "eq", "left": {**expected_count, "result_type": {"kind": "int", "lower": "1", "upper": "1"}},
             "right": {"op": "literal_int", "type": {"kind": "int", "lower": "1", "upper": "1"}, "value": "1"}})
    raw_ni = {"kind": "noninterference", "inputs": ports,
              "outputs": [output["name"] for output in outputs]}
    expected_ni = {"kind": "noninterference", "inputs": ["e\u0301", "source", "é", "\ue000", "\U00010000"],
                   "outputs": ["e\u0301", "result", "é", "\ue000", "\U00010000"]}
    cases.append(("unicode-interfaces", raw_ni, expected_ni))
    contracts = [identified("contract", expected) for _, _, expected in cases]
    document = {
        "contracts": sorted(contracts, key=lambda item: item["id"]), "digest_algorithm": "sha-256",
        "effects": [], "enum_types": [], "format": "axiom-ir", "ir_version": "0.1",
        "nodes": sorted(inputs + [filtered], key=lambda item: item["id"]),
        "outputs": sorted(outputs, key=lambda item: item["name"]),
        "record_types": [record], "table_types": [table],
        "semantics": {"name": "keyed-finite-table-semantics", "sha256": TYPE_VECTORS["SEMANTICS"]},
    }
    raw_document = copy.deepcopy(document)
    raw_document["contracts"] = [{"id": item["id"], "definition": raw}
                                  for (_, raw, _), item in zip(cases, contracts)]
    raw_document["nodes"] = list(reversed(copy.deepcopy(inputs + [filtered])))
    raw_document["nodes"][0]["definition"]["predicate"] = raw_bool
    raw_document["outputs"].reverse()
    raw_document["record_types"][0]["definition"]["fields"].reverse()
    target = contracts[-1]
    definition_bytes = canonical(target["definition"]).encode()
    wrong = {"raw-definition": definition_bytes,
             "missing-nul": b"axiom-ir-v0.1:contract" + definition_bytes,
             "wrong-domain": b"axiom-ir-v0.1:node\0" + definition_bytes,
             "extra-newline": b"axiom-ir-v0.1:contract\0" + definition_bytes + b"\n",
             "including-id": b"axiom-ir-v0.1:contract\0" + canonical(target).encode()}
    named = sorted(zip(cases, contracts), key=lambda pair: pair[1]["id"])
    base = copy.deepcopy(raw_document)
    base["contracts"] = []
    return {
        "base.json": json.dumps(base, ensure_ascii=False, indent=2) + "\n",
        "input.json": json.dumps(TYPE_VECTORS["reverse_objects"](raw_document), ensure_ascii=True, indent=2) + "\n",
        "normalized-input.json": json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        "expected.tsv": "".join(f"{case[0]}\t{item['id']}\t{canonical(item['definition'])}\n" for case, item in named),
        "wrong-hashes.tsv": "".join(f"{name}\t{target['id']}\tsha256:{hashlib.sha256(data).hexdigest()}\n" for name, data in wrong.items()),
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
    print("IR contract identity vectors match" if args.check else "IR contract identity vectors generated")


if __name__ == "__main__":
    main()
