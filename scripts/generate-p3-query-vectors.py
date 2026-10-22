#!/usr/bin/env python3
"""P3-A 独立具体语义期望；合成 IR / 世界与一个手算 SMT 向量，不调用生产编码器。"""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import runpy

from p3_query_semantics import Interpreter

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "contracts/map-filter-query-v0.1"
IR = runpy.run_path(str(ROOT / "scripts/generate-ir-v02-vectors.py"))
P2 = runpy.run_path(str(ROOT / "scripts/generate-p2-profile-review.py"))
canonical, identified, normal = IR["canonical"], IR["identified"], IR["normal_expression"]
field, record_type, access = IR["field"], IR["record_type"], IR["access"]
YES, NO, BOOL, TEXT = IR["YES"], IR["NO"], IR["BOOL"], IR["TEXT"]
INT = {"kind": "int", "lower": "-2", "upper": "2"}
POS = {"kind": "int", "lower": "1", "upper": "2"}
FIXED = {"kind": "fixed", "scale": "2", "lower": "-2", "upper": "2"}


def literal(n, ty=INT):
    return {"op": "literal_fixed" if ty["kind"] == "fixed" else "literal_int", "type": ty,
            "coefficient" if ty["kind"] == "fixed" else "value": str(n)}


def arithmetic(op, left, right, ty=INT):
    return {"op": op, "result_type": ty, **({"values": [left, right]} if op.endswith("_add") else {"left": left, "right": right})}


def compare(op, left, right):
    return {"op": op, "left": left, "right": right}


def forall(body, direction="input", name="in"):
    return {"op": "forall_rows", "table": {"kind": direction, "name": name}, "body": body}


def choose(condition, left, right, ty=INT):
    return {"op": "if", "condition": condition, "then": left, "else": right, "result_type": ty}


def build(name, updates=None, predicate=None, formula=None, assumes=(), capacity=2, filter_capacity=None, port="in", second=False):
    enum = identified("enum-type", {"name": "Mode", "members": ["a", "b"]})
    leaf = record_type([field("number", INT), field("optional", {"kind": "option", "inner": BOOL})])
    row = record_type([field("key", {"kind": "int", "lower": "0", "upper": "2"}), field("x", INT),
                       field("flag", BOOL), field("fixed", FIXED), field("text", TEXT),
                       field("option", {"kind": "option", "inner": POS}),
                       field("mode", {"kind": "enum", "enum_type": enum["id"]}),
                       field("nested", {"kind": "record", "record_type": leaf["id"]})])
    table = identified("table-type", {"record_type": row["id"], "primary_key": ["key"], "capacity": str(capacity)})
    source = identified("node", {"kind": "input", "port": port, "table_type": table["id"]})
    tables, nodes = [table], [source]
    if predicate is not None:
        out_table = table if filter_capacity is None else identified("table-type", {**table["definition"], "capacity": str(filter_capacity)})
        if out_table != table:
            tables.append(out_table)
        filtered = identified("node", normal({"kind": "filter", "predicate": predicate, "source": source["id"], "table_type": out_table["id"]}))
        nodes.append(filtered)
        source, table = filtered, out_table
    fields = [{"name": f["name"], "expression": (updates or {}).get(f["name"], access(f["name"]))} for f in row["definition"]["fields"]]
    mapped = identified("node", normal({"kind": "map", "source": source["id"], "table_type": table["id"], "fields": fields}))
    nodes.append(mapped)
    outputs = [{"name": "out", "node": mapped["id"]}]
    if second:
        other_fields = copy.deepcopy(fields)
        for f in other_fields:
            if f["name"] == "x":
                f["expression"] = arithmetic("int_sub", access("x"), literal(2))
        other = identified("node", normal({**mapped["definition"], "fields": other_fields}))
        nodes.append(other)
        outputs.append({"name": "other", "node": other["id"]})
    formula = YES if formula is None else formula
    contracts = [identified("contract", normal({"kind": "formula", "role": "guarantee", "expression": formula}))]
    contracts.extend(identified("contract", normal({"kind": "formula", "role": "assume", "expression": e})) for e in assumes)
    document = IR["ordered_document"]({"format": "axiom-ir", "ir_version": "0.2", "digest_algorithm": "sha-256",
        "semantics": {"name": "keyed-finite-table-semantics", "sha256": IR["SEMANTICS"]}, "effects": [],
        "enum_types": [enum], "record_types": [row, leaf], "table_types": tables, "nodes": nodes,
        "contracts": contracts, "outputs": outputs})
    return name, document


def synthetic_cases():
    one, two, x = literal(1), literal(2), access("x")
    overflow = arithmetic("int_add", two, one)
    fault_bool = compare("eq", overflow, literal(0))
    cases = [
        build("identity", formula=forall(compare("ge", access("x"), literal(0)), "output", "out")),
        build("int-add", {"x": arithmetic("int_add", x, one)}),
        build("int-sub", {"x": arithmetic("int_sub", x, one)}),
        build("fixed-add", {"fixed": arithmetic("fixed_add", access("fixed"), literal(1, FIXED), FIXED)}),
        build("fixed-sub", {"fixed": arithmetic("fixed_sub", access("fixed"), literal(1, FIXED), FIXED)}),
        build("conditional-range", {"x": choose(access("flag"), arithmetic("int_add", x, one), arithmetic("int_sub", x, one))}),
        build("dead-range", {"x": choose(NO, overflow, x)}),
        build("filter-reach", {"x": overflow}, predicate=access("flag")),
        build("filter-capacity", predicate=YES, filter_capacity=1),
        build("strict-or", formula={"op": "or", "values": [YES, fault_bool]}),
        build("strict-and", formula={"op": "and", "values": [NO, fault_bool]}),
        build("pre-false", {"x": overflow}, assumes=[NO]),
        build("pre-fault", {"x": overflow}, assumes=[fault_bool]),
        build("pre-dependent", {"x": arithmetic("int_add", x, one)}, assumes=[forall(compare("le", x, one))]),
        build("child-fault", {"x": arithmetic("int_sub", overflow, one)}),
        build("independent-node-fault", {"x": arithmetic("int_add", x, two)}, second=True),
        build("zero-capacity", {"x": overflow}, formula=forall(NO), capacity=0),
        build("option-none-equality", formula=forall(compare("eq", access("option"), {"op": "none", "type": {"kind": "option", "inner": POS}}))),
        build("option-some-equality", formula=forall(compare("eq", access("option"), {"op": "some", "value": literal(1, POS)}))),
        build("match-option", formula=forall({"op": "match_option", "subject": access("option"), "none": YES,
              "some": compare("le", {"op": "bound", "index": "0"}, literal(1, POS)), "result_type": BOOL})),
        build("nested-option", formula=compare("eq", {"op": "some", "value": {"op": "none", "type": {"kind": "option", "inner": BOOL}}},
              {"op": "none", "type": {"kind": "option", "inner": {"kind": "option", "inner": BOOL}}})),
        build("text-exact", formula=forall(compare("eq", access("text"), {"op": "literal_text", "value": "é"}))),
        build("unicode-literals", formula=compare("eq", {"op": "literal_text", "value": "é"}, {"op": "literal_text", "value": "e\u0301"})),
        build("escaped-literal", formula=compare("eq", {"op": "literal_text", "value": 'a\n"\\\U00010000'}, {"op": "literal_text", "value": "other"})),
        build("symbol-name-isolation", formula=NO, port="in) (assert false) (😀"),
    ]
    for op in ["lt", "le", "gt", "ge"]:
        cases.append(build("compare-" + op, formula=forall(compare(op, access("x"), literal(0, {"kind": "int", "lower": "0", "upper": "0"})))) )
    enum_id = cases[0][1]["enum_types"][0]["id"]
    cases.append(build("enum-not", formula=forall({"op": "not", "value": compare("eq", access("mode"), {"op": "literal_enum", "enum_type": enum_id, "member": "b"})})))
    # 一个显式构造的记录，number 未越界而 optional 的兄弟子式故障。
    leaf_id = next(r["id"] for r in cases[0][1]["record_types"] if {f["name"] for f in r["definition"]["fields"]} == {"number", "optional"})
    constructed = {"op": "record", "record_type": leaf_id, "fields": [
        {"name": "number", "expression": one}, {"name": "optional", "expression": {"op": "some", "value": fault_bool}}]}
    cases.append(build("record-sibling-fault", formula=compare("eq", {"op": "field", "field": "number", "record": constructed}, one)))
    cases.append(build("record-constructor", {"nested": {**constructed, "fields": [
        {"name": "number", "expression": arithmetic("int_sub", access("x"), one)},
        {"name": "optional", "expression": {"op": "some", "value": access("flag")}}]}}))
    lookup = {"op": "lookup", "table": {"kind": "output", "name": "out"}, "keys": [access("key")]}
    body = {"op": "match_option", "subject": lookup, "none": NO,
            "some": compare("eq", access("x"), access("x", "1")), "result_type": BOOL}
    cases.append(build("lookup-identity", formula=forall(body)))
    cases.append(build("lookup-missing", predicate=access("flag"), formula=forall(body)))
    cases.append(build("nested-forall", formula=forall(forall(compare("le", access("x"), access("x", "1"))))))
    huge = {"kind": "int", "lower": "-" + "9" * 100, "upper": "9" * 100}
    huge_sum = arithmetic("int_add", literal(int("8" * 100), huge), literal(int("8" * 100), huge), huge)
    cases.append(build("big-integer-overflow", formula=compare("gt", huge_sum, literal(0, huge))))
    row = record_type([field("key", BOOL)])
    table = identified("table-type", {"record_type": row["id"], "primary_key": ["key"], "capacity": "0"})
    node = identified("node", {"kind": "input", "port": "in", "table_type": table["id"]})
    minimum = IR["ordered_document"]({**cases[0][1], "enum_types": [], "record_types": [row], "table_types": [table],
        "nodes": [node], "contracts": [identified("contract", {"kind": "formula", "role": "guarantee", "expression": YES})],
        "outputs": [{"name": "out", "node": node["id"]}]})
    cases.append(("minimal", minimum))
    return cases


def worlds(document):
    interpreter = Interpreter(document, {})
    node = next(n["definition"] for n in document["nodes"] if n["definition"]["kind"] == "input")
    table = interpreter.tables[node["table_type"]]
    port = node["port"]
    if int(table["capacity"]) == 0:
        return [{port: []}]
    row = {"key": 0, "x": 0, "flag": False, "fixed": 0, "text": "é", "option": None,
           "mode": 0, "nested": {"number": 0, "optional": None}}
    result = [{port: []}, {port: [{"active": False, "row": {**row, "x": 999, "mode": 999}}]}]
    for x, flag, option in itertools.product(range(-2, 3), [False, True], [None, {"some": 1}, {"some": 2}]):
        result.append({port: [{"active": True, "row": {**row, "x": x, "fixed": x, "flag": flag, "option": option}}]})
    for text_value in ["e\u0301", "fresh-text"]:
        result.append({port: [{"active": True, "row": {**row, "text": text_value, "mode": 1}}]})
    first = {"active": True, "row": {**row, "x": 2, "flag": True}}
    second = {"active": True, "row": {**row, "key": 1, "x": -2}}
    result.extend([{port: [first, second]}, {port: [second, first]}, {port: [{"active": False, "row": row}, first]},
                   {port: [first, first]}, {port: [{"active": True, "row": {**row, "x": 999}}]}])
    return result


def ax_b01_worlds():
    result = [{"orders": []}]
    for subtotal, discount, state in itertools.product(range(3), range(3), range(2)):
        result.append({"orders": [{"active": True, "row": {"order_id": "id-0", "subtotal_cents": subtotal,
            "discount_cents": discount, "state": state}}]})
    zero = {"active": True, "row": {"order_id": "id-0", "subtotal_cents": 1, "discount_cents": 1, "state": 1}}
    other = {"active": True, "row": {"order_id": "id-1", "subtotal_cents": 2, "discount_cents": 1, "state": 0}}
    result.extend([{"orders": [zero, other]}, {"orders": [other, zero]},
                   {"orders": [{**zero, "active": False}, other]}, {"orders": [zero, zero]}])
    return result


def resource_inputs():
    expression = YES
    for _ in range(60):
        expression = forall(expression)
    _, nested = build("nested-expansion", formula=expression)
    # 类型和转换分别为 5,000 层，JSON 本身保持浅层；测试沿引用不递归展开栈。
    records = [record_type([field("value", BOOL)])]
    for _ in range(5000):
        records.append(record_type([field("child", {"kind": "record", "record_type": records[-1]["id"]})]))
    row = record_type([field("key", INT), field("value", {"kind": "record", "record_type": records[-1]["id"]})])
    records.append(row)
    table = identified("table-type", {"record_type": row["id"], "primary_key": ["key"], "capacity": "1"})
    nodes = [identified("node", {"kind": "input", "port": "in", "table_type": table["id"]})]
    for _ in range(5000):
        nodes.append(identified("node", {"kind": "filter", "source": nodes[-1]["id"], "predicate": YES, "table_type": table["id"]}))
    deep = IR["ordered_document"]({**nested, "enum_types": [], "record_types": records, "table_types": [table],
            "nodes": nodes, "contracts": [identified("contract", {"kind": "formula", "role": "guarantee", "expression": YES})],
            "outputs": [{"name": "out", "node": nodes[-1]["id"]}]})
    return {"nested-expansion": nested, "deep-type-and-graph": deep}


def artifacts():
    files, cases = {}, []
    for name, document in synthetic_cases():
        files[f"inputs/{name}.jcs"] = canonical(document).encode()
        cases.append((name, document, f"contracts/map-filter-query-v0.1/inputs/{name}.jcs", worlds(document)))
    for name, document in resource_inputs().items():
        files[f"resource-inputs/{name}.jcs"] = canonical(document).encode()
    for name in ["ax-b01-correct", "ax-b01-wrong-add", "ax-b01-wrong-drop-zero"]:
        path = f"crates/axiom-ir/tests/fixtures/v0.2/migrated/{name}.jcs"
        cases.append((name, json.loads((ROOT / path).read_bytes()), path, ax_b01_worlds()))
    manifest = []
    op_coverage = set()
    for name, document, path, samples in cases:
        document_id = P2["identity"]("axiom-ir-v0.2:document", document)
        obligations = [o for o in P2["proposed_definitions"](document, document_id)
                       if o["definition"]["kind"] in {"numeric-range", "contract-guarantee"}]
        if name == "minimal":
            # 手算七项：false、true、空 Text、formulaOK、ProgramOK、violation、最终目标。
            assert len(obligations) == 1
            q = "q" + obligations[0]["id"][7:] + "_t"
            lines = ["(set-logic QF_UFLIA)", "(declare-sort Text 0)",
                     f"(define-fun {q}0 () Bool false)", f"(define-fun {q}1 () Bool true)",
                     f"(declare-const {q}2 Text)", f"(define-fun {q}3 () Bool (and {q}1 {q}1))",
                     f"(define-fun {q}4 () Bool (and {q}1 {q}3))", f"(define-fun {q}5 () Bool (not {q}4))",
                     f"(define-fun {q}6 () Bool (and {q}1 {q}1 {q}5))", f"(assert {q}6)", "(check-sat)"]
            files["expected/minimal.smt2"] = ("\n".join(lines) + "\n").encode()
        expected = [Interpreter(document, w).results(obligations) for w in samples]
        # 三个候选的业务区分由手算额外锚定，不读取基准 expected outcome。
        guarantees = [i for i, o in enumerate(obligations) if o["definition"]["kind"] == "contract-guarantee"]
        if name == "ax-b01-correct":
            assert not any(any(row) for row in expected)
        elif name.startswith("ax-b01-wrong"):
            assert any(row[guarantees[0]] for row in expected)
        elif name in {"strict-or", "strict-and", "record-sibling-fault", "unicode-literals", "escaped-literal", "big-integer-overflow", "nested-option"}:
            assert all(row[guarantees[0]] for w, row in zip(samples, expected) if Interpreter(document, w).wf())
        elif name in {"dead-range", "pre-false", "pre-fault", "zero-capacity", "lookup-identity"}:
            assert not any(any(row) for row in expected)
        manifest.append({"name": name, "ir": path, "ir_raw": P2["raw_digest"](canonical(document).encode()),
                         "targets": obligations, "worlds": samples, "expected": expected})
        pending = [document]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                if "op" in value:
                    op_coverage.add(value["op"])
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
    assert op_coverage == {"literal_bool", "literal_int", "literal_fixed", "literal_text", "literal_enum", "none", "some", "record",
                           "bound", "field", "not", "and", "or", "eq", "lt", "le", "gt", "ge", "int_add", "int_sub", "fixed_add", "fixed_sub",
                           "if", "match_option", "forall_rows", "lookup"}
    provenance = {str(p.relative_to(ROOT)): P2["raw_digest"](p.read_bytes()) for p in [Path(__file__), ROOT / "scripts/p3_query_semantics.py", ROOT / "scripts/check-p3-query-semantics.py",
                  ROOT / "scripts/generate-ir-v02-vectors.py", ROOT / "scripts/generate-p2-profile-review.py", ROOT / "scripts/generate-ir-type-vectors.py"]}
    files["cases.json"] = (json.dumps({"status": "finite-independent-expectations-not-proof", "sources": provenance,
                          "operator_coverage": sorted(op_coverage), "cases": manifest}, ensure_ascii=False, indent=2) + "\n").encode()
    return files, len(manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files, count = artifacts()
    for name, data in files.items():
        path = DEST / name
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                raise SystemExit("P3 semantic vectors drift: " + name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f"P3 independent vectors: {count} cases, 26 operators, one hand-derived SMT vector; no production encoder or solver")


if __name__ == "__main__":
    main()
