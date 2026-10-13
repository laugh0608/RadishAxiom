#!/usr/bin/env python3
"""独立重建 P4-B 有限语义 / 见证及输入绑定；费用只核对上限，不声称独立证明。"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import runpy
from p4b_replay_semantics import canonical, observe, Interpreter

ROOT = Path(__file__).resolve().parents[1]
P2 = runpy.run_path(str(ROOT / "scripts/generate-p2-profile-review.py"))


def digest(b):
    return "sha256:" + hashlib.sha256(b).hexdigest()


def world(document, entries):
    interp = Interpreter(document, {})

    def value(ty, v):
        kind = ty["kind"]
        if kind in {"bool", "text"}:
            assert v["kind"] == kind
            return v["value"]
        if kind in {"int", "fixed"}:
            assert v["kind"] == kind
            return int(v["coefficient"] if kind == "fixed" else v["value"])
        if kind == "enum":
            assert v["enum_type"] == ty["enum_type"]
            return interp.enums[ty["enum_type"]].index(v["member"])
        if kind == "option":
            return None if v["kind"] == "none" else {"some": value(ty["inner"], v["value"])}
        assert v["record_type"] == ty["record_type"]
        types = {f["name"]: f["type"] for f in interp.records[ty["record_type"]]["fields"]}
        assert set(types) == {f["name"] for f in v["fields"]}
        return {f["name"]: value(types[f["name"]], f["value"]) for f in v["fields"]}

    nodes = {n["port"]: n for n in interp.nodes.values() if n["kind"] == "input"}
    assert set(nodes) == {e["interface"] for e in entries}
    result = {}
    for e in entries:
        assert nodes[e["interface"]]["table_type"] == e["table_type"]
        ty = {"kind": "record", "record_type": interp.tables[e["table_type"]]["record_type"]}
        result[e["interface"]] = [{"active": True, "row": value(ty, r)} for r in e["rows"]]
    return result


def validate(record, ir_bytes, p2_bytes, world_bytes, expected_input):
    assert set(record) == {"format", "version", "profile", "rule_digest", "binding", "source", "world_raw_digest", "limits", "result", "usage"}
    assert record["format"] == "axiom-p4-target-replay-observation" and record["version"] == "0.1"
    assert record["profile"] == "axiom-p4-map-filter-replay-v0.1"
    assert record["rule_digest"] == digest((ROOT / "docs/query/p4-concrete-target-replay-v0.1.md").read_bytes())
    doc, p2 = json.loads(ir_bytes), json.loads(p2_bytes)
    doc_id = P2["identity"]("axiom-ir-v0.2:document", doc)
    definitions = P2["proposed_definitions"](doc, doc_id)
    rebuilt = P2["obligation_set"]({"ir": doc, "ir_artifact": digest(ir_bytes), "ir_document_digest": doc_id, "definitions": definitions})
    assert canonical(rebuilt) == p2_bytes
    assert record["binding"] == {"ir_artifact": digest(ir_bytes), "ir_document_digest": doc_id,
        "obligation_set_artifact": digest(p2_bytes), "obligation": expected_input["target"],
        "semantics_digest": "sha256:" + doc["semantics"]["sha256"], "generator": expected_input["generator"]}
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", expected_input["generator"])
    assert record["source"] == expected_input["source"] == {"kind": "provided-world"}
    assert record["world_raw_digest"] == digest(world_bytes)
    assert record["limits"] == expected_input["limits"]
    assert set(record["usage"]) == set(record["limits"]) - {"ir_json"}
    for k, v in record["usage"].items():
        assert re.fullmatch(r"0|[1-9][0-9]*", v) and int(v) <= int(record["limits"][k])
    assert int(record["usage"]["world_bytes"]) == len(world_bytes)
    assert int(record["usage"]["output_bytes"]) == len(canonical(record))
    target = next(t["definition"] for t in definitions if t["id"] == expected_input["target"])
    expected = observe(doc, world(doc, json.loads(world_bytes)), target)
    assert record["result"] == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--mutations", action="store_true")
    args = parser.parse_args()
    record_bytes = (args.directory / "observation.jcs").read_bytes()
    record = json.loads(record_bytes)
    assert canonical(record) == record_bytes
    inputs = [(args.directory / n).read_bytes() for n in ["ir.jcs", "p2.jcs", "world.jcs"]]
    expected = json.loads((args.directory / "input.jcs").read_bytes())
    validate(record, *inputs, expected)
    count = 0
    if args.mutations:
        mutants = []
        for field in ["binding", "source", "world_raw_digest", "limits", "rule_digest", "usage"]:
            mutant = copy.deepcopy(record)
            mutant[field] = {}
            mutants.append(mutant)
        mutant = copy.deepcopy(record)
        mutant["result"] = {"kind": "target-not-violated", "observation": {"kind": "contract-guarantee", "value": True}}
        mutants.append(mutant)
        for mutant in mutants:
            try:
                validate(mutant, *inputs, expected)
            except (AssertionError, KeyError, TypeError, ValueError):
                count += 1
            else:
                raise AssertionError("mutated observation accepted")
        for at in [0, 1, 2]:
            changed = list(inputs)
            changed[at] += b" "
            try:
                validate(record, *changed, expected)
            except (AssertionError, KeyError, TypeError, ValueError):
                count += 1
            else:
                raise AssertionError("changed input accepted")
    print(f"P4-B independent finite witness matched; {count} mutation classes rejected; no proof / solver provenance")


if __name__ == "__main__":
    main()
