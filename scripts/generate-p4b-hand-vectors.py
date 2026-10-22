#!/usr/bin/env python3
"""P4-B 手算区分与深度合成材料；只写调用方指定的测试目录。"""
import argparse
import json
from pathlib import Path
import runpy
from p4b_replay_semantics import canonical, world_bytes, observe, Interpreter

ROOT = Path(__file__).resolve().parents[1]
IR = runpy.run_path(str(ROOT / "scripts/generate-ir-v02-vectors.py"))
Q = runpy.run_path(str(ROOT / "scripts/generate-p3-query-vectors.py"))
P2 = runpy.run_path(str(ROOT / "scripts/generate-p2-profile-review.py"))
KINDS = {"numeric-range", "totality", "key-cardinality", "row-coverage", "contract-guarantee"}


def targets(doc):
    return [o for o in P2["proposed_definitions"](doc, P2["identity"]("axiom-ir-v0.2:document", doc)) if o["definition"]["kind"] in KINDS]


def write_case(dest, name, doc, world):
    ts = targets(doc)
    (dest / f"{name}.ir.jcs").write_bytes(canonical(doc))
    (dest / f"{name}.world.jcs").write_bytes(world_bytes(doc, world))
    data = {"name": name, "targets": [t["id"] for t in ts], "results": [observe(doc, world, t["definition"]) for t in ts]}
    (dest / f"{name}.expected.jcs").write_bytes(canonical(data))
    return data


def deep_world(doc):
    # Explicit writer avoids Python recursion and intentionally does not use Rust.
    interp = Interpreter(doc, {})
    node = next(n for n in interp.nodes.values() if n["kind"] == "input")
    table = interp.tables[node["table_type"]]
    out = [b'[{"interface":"in","rows":[']
    tasks = [{"kind": "record", "record_type": table["record_type"]}]
    while tasks:
        ty = tasks.pop()
        if isinstance(ty, bytes):
            out.append(ty)
        elif ty["kind"] == "record":
            out.append(b'{"fields":[')
            tasks.append(b'],"kind":"record","record_type":' + canonical(ty["record_type"]) + b'}')
            fields = interp.records[ty["record_type"]]["fields"]
            for index, f in reversed(list(enumerate(fields))):
                tasks.extend([b'}', f["type"], b'{"name":' + canonical(f["name"]) + b',"value":'])
                if index:
                    tasks.append(b',')
        elif ty["kind"] == "bool":
            out.append(b'{"kind":"bool","value":false}')
        elif ty["kind"] == "int":
            out.append(canonical({"kind": "int", "value": ty["lower"]}))
        else:
            raise AssertionError(ty)
    out.append(b'],"table_type":' + canonical(node["table_type"]) + b'}]')
    return b''.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    dest = args.directory
    dest.mkdir(parents=True, exist_ok=True)
    names = []
    for variant in ["correct", "wrong-add", "wrong-drop-zero"]:
        name = "ax-b01-" + variant
        doc = json.loads((ROOT / f"crates/axiom-ir/tests/fixtures/v0.2/migrated/{name}.jcs").read_bytes())
        rows = [{"order_id": "a", "state": 1, "subtotal_cents": 10, "discount_cents": 10},
                {"order_id": "b", "state": 1, "subtotal_cents": 20, "discount_cents": 5},
                {"order_id": "c", "state": 0, "subtotal_cents": 8, "discount_cents": 0}]
        world = {"orders": [{"active": True, "row": r} for r in rows]}
        data = write_case(dest, name, doc, world)
        # Hand result: correct -> a:0,b:15; wrong-add -> a:20,b:25;
        # wrong-drop-zero -> b:15. Each faithful built-in coverage still holds.
        for result in data["results"]:
            detail = result.get("witness", result.get("observation"))
            if detail["kind"] == "contract-guarantee":
                assert (result["kind"] == "target-violated") == (variant != "correct")
            if detail["kind"] == "row-coverage":
                assert result["kind"] == "target-not-violated"
        names.append(name)
    # One false guarantee cannot poison a different true guarantee.
    _, doc = Q["build"]("two-guarantees", formula=IR["YES"])
    doc["contracts"].append(IR["identified"]("contract", {"kind": "formula", "role": "guarantee", "expression": IR["NO"]}))
    doc = IR["ordered_document"](doc)
    write_case(dest, "two-guarantees", doc, {"in": []})
    names.append("two-guarantees")
    # Input foreign-key-like assumption, expressed solely through declared lookup.
    lookup = {"op": "lookup", "table": {"kind": "input", "name": "in"}, "keys": [Q["literal"](1, {"kind": "int", "lower": "0", "upper": "2"})]}
    assume = {"op": "match_option", "subject": lookup, "none": IR["NO"], "some": IR["YES"], "result_type": IR["BOOL"]}
    _, doc = Q["build"]("foreign-key", assumes=[assume])
    interp = Interpreter(doc, {})
    node = next(n for n in interp.nodes.values() if n["kind"] == "input")
    row = interp.default({"kind": "record", "record_type": interp.tables[node["table_type"]]["record_type"]})
    for key in [0, 1]:
        row = {**row, "key": key}
        name = "foreign-key-" + str(key)
        write_case(dest, name, doc, {"in": [{"active": True, "row": row}]})
        names.append(name)
    # Reuse separately hand-written P4-A semantic values, retaining 100-digit Int,
    # Fixed coefficients, nested Option/Record, Enum declaration order and Unicode.
    doc = json.loads((ROOT / "contracts/solver-model-v0.1/inputs/composite.jcs").read_bytes())
    hand = json.loads((ROOT / "contracts/solver-model-v0.1/hand-cases.json").read_bytes())
    interp = Interpreter(doc, {})
    def native(ty, v):
        kind = ty["kind"]
        if kind in {"int", "fixed"}:
            return int(v)
        if kind == "enum":
            return interp.enums[ty["enum_type"]].index(v)
        if kind == "text":
            return v["text-class"] if isinstance(v, dict) else v
        if kind == "option":
            return None if v is None else {"some": native(ty["inner"], v["some"])}
        if kind == "record":
            return {f["name"]: native(f["type"], v[f["name"]]) for f in interp.records[ty["record_type"]]["fields"]}
        return v
    world = {}
    for node in interp.nodes.values():
        ty = {"kind": "record", "record_type": interp.tables[node["table_type"]]["record_type"]}
        world[node["port"]] = [{"active": True, "row": native(ty, r)} for r in hand["expected_rows"][node["port"]]]
    write_case(dest, "composite-values", doc, world)
    names.append("composite-values")
    # Deep Record reading / destruction uses the existing 5,002 type DAG.
    doc = json.loads((ROOT / "contracts/solver-model-v0.1/inputs/deep-type.jcs").read_bytes())
    (dest / "deep-record.ir.jcs").write_bytes(canonical(doc))
    (dest / "deep-record.world.jcs").write_bytes(deep_world(doc))
    # 1,500 dependent maps propagate a single range fault with a flat cause chain.
    _, doc = Q["build"]("deep-graph", updates={"x": Q["arithmetic"]("int_add", Q["literal"](2), Q["literal"](1))})
    first = next(n for n in doc["nodes"] if n["definition"]["kind"] == "map")
    predecessor = first
    fields = [{"name": f["name"], "expression": Q["access"](f["name"])} for f in next(r for r in doc["record_types"] if r["id"] == next(t for t in doc["table_types"] if t["id"] == first["definition"]["table_type"])["definition"]["record_type"])["definition"]["fields"]]
    for _ in range(1500):
        predecessor = IR["identified"]("node", {"kind": "map", "source": predecessor["id"], "table_type": first["definition"]["table_type"], "fields": fields})
        doc["nodes"].append(predecessor)
    doc["outputs"] = [{"name": "out", "node": predecessor["id"]}]
    doc = IR["ordered_document"](doc)
    (dest / "deep-graph.ir.jcs").write_bytes(canonical(doc))
    (dest / "deep-graph.world.jcs").write_bytes(world_bytes(doc, {"in": [{"active": True, "row": row}]}))
    (dest / "deep-graph.target.txt").write_text(predecessor["id"])
    # Unsupported work remains rejected even in an unselected guarantee branch.
    exists = {"op": "exists_rows", "table": {"kind": "input", "name": "in"}, "body": IR["NO"]}
    _, unsupported = Q["build"]("unsupported-dead-branch", formula={"op": "if", "condition": IR["YES"], "then": IR["YES"], "else": exists, "result_type": IR["BOOL"]})
    (dest / "unsupported.ir.jcs").write_bytes(canonical(unsupported))
    # Huge declaration never expands actual rows.
    _, doc = Q["build"]("huge-capacity", capacity=int("9" * 100))
    write_case(dest, "huge-capacity", doc, {"in": []})
    names.append("huge-capacity")
    (dest / "names.jcs").write_bytes(canonical(names))


if __name__ == "__main__":
    main()
