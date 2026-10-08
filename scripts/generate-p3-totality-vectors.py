#!/usr/bin/env python3
"""P3-B 独立合成材料；不重写 v0.1 材料，不调用生产编码器或 solver。"""
import argparse
import copy
import json
from pathlib import Path
import runpy

from p3_query_semantics import Interpreter
from p3_totality_semantics import results

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "contracts/map-filter-query-v0.2"
V = runpy.run_path(str(ROOT / "scripts/generate-p3-query-vectors.py"))
P2, IR = V["P2"], V["IR"]
build, arithmetic, literal, compare = [V[k] for k in ("build", "arithmetic", "literal", "compare")]
access, identified, normal, canonical = [V[k] for k in ("access", "identified", "normal", "canonical")]
YES, NO, BOOL, INT = [V[k] for k in ("YES", "NO", "BOOL", "INT")]


def additions():
    overflow = arithmetic("int_add", literal(2), literal(1))
    fault_bool = compare("eq", overflow, literal(0))
    cases = [
        build("no-guarantee"),
        build("false-guarantee", formula=NO),
        build("node-strict-and", predicate={"op": "and", "values": [NO, fault_bool]}),
        build("node-strict-or", predicate={"op": "or", "values": [YES, fault_bool]}),
        build("node-match-option", {"x": {"op": "match_option", "subject": access("option"),
              "none": literal(0), "some": overflow, "result_type": INT}}),
        build("downstream-fault", {"x": overflow}, predicate=YES),
        build("capacity-unrestricted", predicate=YES),
        build("renamed-key"),
        build("renamed-interface", {"x": arithmetic("int_add", access("x"), literal(1))}, port="新输入"),
    ]
    # 直接字段保持键的合法重命名，不增加新的键表达式语义。
    for name, document in cases:
        if name == "no-guarantee":
            document["contracts"] = []
        elif name == "renamed-key":
            mapped = next(n for n in document["nodes"] if n["definition"]["kind"] == "map")
            tables = {t["id"]: t["definition"] for t in document["table_types"]}
            old_table = tables[mapped["definition"]["table_type"]]
            old_record = next(r for r in document["record_types"] if r["id"] == old_table["record_type"])
            fields = copy.deepcopy(old_record["definition"]["fields"])
            for field in fields:
                if field["name"] == "key":
                    field["name"] = "renamed_key"
            record = V["record_type"](fields)
            table = identified("table-type", {**old_table, "primary_key": ["renamed_key"], "record_type": record["id"]})
            definition = copy.deepcopy(mapped["definition"])
            definition["table_type"] = table["id"]
            for field in definition["fields"]:
                if field["name"] == "key":
                    field["name"] = "renamed_key"
            definition["fields"].sort(key=lambda f: f["name"])
            changed = identified("node", normal(definition))
            document["nodes"] = [changed if n["id"] == mapped["id"] else n for n in document["nodes"]]
            document["record_types"].append(record)
            document["table_types"].append(table)
            document["outputs"][0]["node"] = changed["id"]
        yield name, IR["ordered_document"](document)
    base = build("base")[1]
    leaf = next(r["id"] for r in base["record_types"] if {f["name"] for f in r["definition"]["fields"]} == {"number", "optional"})
    record = {"op": "record", "record_type": leaf, "fields": [
        {"name": "number", "expression": literal(0)},
        {"name": "optional", "expression": {"op": "some", "value": fault_bool}}]}
    yield build("node-record-sibling", {"x": {"op": "field", "record": record, "field": "number"}})


def hand_check(name, document, worlds, targets, expected):
    """独立于具体解释器的手算锚点；完整期望仍逐世界保存。"""
    totalities = [i for i, o in enumerate(targets) if o["definition"]["kind"] == "totality"]
    guarantees = [i for i, o in enumerate(targets) if o["definition"]["kind"] == "contract-guarantee"]
    safe = {"identity", "no-guarantee", "false-guarantee", "renamed-key", "dead-range", "strict-and", "strict-or",
            "record-sibling-fault", "pre-false", "pre-fault", "zero-capacity", "capacity-unrestricted"}
    if name in safe:
        assert all(not row[i] for row in expected for i in totalities), name
    for world, values in zip(worlds, expected):
        if not Interpreter(document, world).wf():
            assert not any(values), name
            continue
        if name.startswith("ax-b01-"):
            # 样本金额仅 0..2，正确 / 两个 wrong 均不发生类型范围故障。
            assert not any(values[i] for i in totalities), name
            continue
        port = next(iter(world))
        rows = [s["row"] for s in world[port] if s["active"]]
        if name == "filter-capacity":
            assert all(values[i] == (len(rows) > 1) for i in totalities)
        elif name in {"node-strict-and", "node-strict-or", "node-record-sibling"}:
            assert all(values[i] == bool(rows) for i in totalities)
        elif name == "node-match-option":
            assert all(values[i] == any(r["option"] is not None for r in rows) for i in totalities)
        elif name in {"int-add", "renamed-interface", "int-sub", "fixed-add", "fixed-sub"}:
            field = "fixed" if name.startswith("fixed") else "x"
            boundary = -2 if name.endswith("sub") else 2
            assert all(values[i] == any(r[field] == boundary for r in rows) for i in totalities)
        elif name == "downstream-fault":
            nodes = {n["id"]: n["definition"] for n in document["nodes"]}
            for i in totalities:
                kind = nodes[targets[i]["definition"]["subject"]["id"]]["kind"]
                assert values[i] == (bool(rows) if kind == "map" else False)
        if name == "false-guarantee":
            assert all(values[i] for i in guarantees)


def artifacts():
    old = json.loads((ROOT / "contracts/map-filter-query-v0.1/cases.json").read_bytes())
    cases = [(c["name"], json.loads((ROOT / c["ir"]).read_bytes()), c["ir"], c["worlds"]) for c in old["cases"]]
    files = {}
    # 拒绝路径仍通过真实 P1 / P2；不得用坏 ID 使请求在功能检查前失败。
    table = {"kind": "input", "name": "in"}
    count_type = {"kind": "int", "lower": "0", "upper": "2"}
    formulas = {
        "exists_rows": {"op": "exists_rows", "table": table, "body": YES},
        "count_where": compare("eq", {"op": "count_where", "table": table, "predicate": YES,
                                     "result_type": count_type}, literal(0, count_type)),
        "sum_where": compare("eq", {"op": "sum_where", "table": table, "predicate": YES,
                                   "value": access("x"), "result_type": INT}, literal(0)),
    }
    for op, formula in formulas.items():
        document = build(op, formula=formula)[1]
        files[f"resource-inputs/{op}.jcs"] = canonical(document).encode()
    huge = build("huge-input", capacity=10 ** 100)[1]
    files["resource-inputs/huge-input.jcs"] = canonical(huge).encode()
    for name, document in additions():
        path = f"contracts/map-filter-query-v0.2/inputs/{name}.jcs"
        files[f"inputs/{name}.jcs"] = canonical(document).encode()
        cases.append((name, document, path, V["worlds"](document)))
    manifest = []
    for name, document, path, worlds in cases:
        document_id = P2["identity"]("axiom-ir-v0.2:document", document)
        obligations = P2["proposed_definitions"](document, document_id)
        targets = [o for o in obligations if o["definition"]["kind"] in {"totality", "numeric-range", "contract-guarantee"}]
        expected = [results(document, world, targets) for world in worlds]
        hand_check(name, document, worlds, targets, expected)
        manifest.append({"name": name, "ir": path, "ir_raw": P2["raw_digest"](canonical(document).encode()),
                         "ir_document_digest": document_id, "targets": targets, "worlds": worlds, "expected": expected})
    sources = [Path(__file__), ROOT / "scripts/p3_totality_semantics.py", ROOT / "scripts/check-p3-totality-semantics.py",
               ROOT / "scripts/generate-p3-query-vectors.py", ROOT / "scripts/p3_query_semantics.py",
               ROOT / "scripts/check-p3-query-semantics.py", ROOT / "contracts/map-filter-query-v0.1/cases.json",
               ROOT / "scripts/generate-ir-v02-vectors.py", ROOT / "scripts/generate-p2-profile-review.py",
               ROOT / "scripts/generate-ir-type-vectors.py", ROOT / "docs/query/map-filter-query-v0.2.md"]
    data = {"status": "finite-independent-expectations-not-proof", "profile": "axiom-p3-map-filter-query-v0.2",
            "sources": {str(p.relative_to(ROOT)): P2["raw_digest"](p.read_bytes()) for p in sources}, "cases": manifest}
    files["cases.json"] = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    return files, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files, cases = artifacts()
    for name, data in files.items():
        path = DEST / name
        if args.check:
            assert path.is_file() and path.read_bytes() == data, "P3-B material drift: " + name
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f"P3-B independent vectors: {len(cases)} cases / {sum(len(c['targets']) for c in cases)} targets / "
          f"{sum(len(c['targets']) * len(c['worlds']) for c in cases)} assignments; no solver or proof")


if __name__ == "__main__":
    main()
