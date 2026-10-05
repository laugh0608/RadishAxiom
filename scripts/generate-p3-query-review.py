#!/usr/bin/env python3
"""Reproduce proposal coverage and small mathematical distinctions, not SMT queries."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs/query/p3-query-review"
P2 = ROOT / "contracts/ir-derived-obligations-v0.2"
KINDS = {"numeric-range", "contract-guarantee"}
DEFERRED_OPS = {"exists_rows", "count_where", "sum_where"}


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def objects(value):
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            yield item
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def coverage():
    rows = []
    for line in (P2 / "cases.tsv").read_text().splitlines():
        name, source, document, raw, count, _, _, _, set_raw = line.split("\t")
        ir_bytes = (ROOT / source).read_bytes()
        set_path = P2 / "sets" / (name + ".jcs")
        set_bytes = set_path.read_bytes()
        ir = json.loads(ir_bytes)
        obligations = json.loads(set_bytes)
        assert digest(ir_bytes) == raw
        assert digest(set_bytes) == set_raw
        assert obligations["ir_artifact"] == raw
        assert obligations["ir_document_digest"] == document
        assert len(obligations["obligations"]) == int(count)
        blockers = sorted(
            {"node:" + n["definition"]["kind"] for n in ir["nodes"]
             if n["definition"]["kind"] not in {"input", "filter", "map"}}
            | {"op:" + o["op"] for o in objects(ir) if o.get("op") in DEFERRED_OPS}
        )
        entries = []
        for item in obligations["obligations"]:
            definition = item["definition"]
            if definition["expectation"] != "prove":
                reason = "not-prove"
            elif definition["kind"] not in KINDS:
                reason = "unsupported-kind"
            elif blockers:
                reason = "unsupported-document-feature"
            else:
                reason = "candidate-by-shape-only"
            entries.append({"id": item["id"], "kind": definition["kind"], "classification": reason})
        rows.append({"name": name, "ir": source, "ir_raw": raw,
                     "ir_document_digest": document, "obligation_set_raw": set_raw,
                     "blockers": blockers, "obligations": entries})
    return rows


def distinctions():
    # These deliberately independent scalar equations do not evaluate IR or parse SMT.
    cases = []

    def record(name, inputs, actual, expected):
        assert actual == expected, name
        cases.append({"name": name, "inputs": inputs, "value": actual, "expected": expected})

    for name, wf, pre_ok, pre_value, reach, operands_ok, value, expected in [
        ("live-overflow", True, True, True, True, True, 11, True),
        ("at-upper-bound", True, True, True, True, True, 10, False),
        ("dead-branch", True, True, True, False, True, 11, False),
        ("empty-or-filtered-row", True, True, True, False, True, 11, False),
        ("invalid-input", False, True, True, True, True, 11, False),
        ("pre-false", True, True, False, True, True, 11, False),
        ("pre-fault", True, False, True, True, True, 11, False),
        ("operand-fault", True, True, True, True, False, 11, False),
    ]:
        within = 0 <= value <= 10
        correct = wf and pre_ok and pre_value and reach and operands_ok and not within
        record(name, {"WF": wf, "PreOK": pre_ok, "PreValue": pre_value,
                      "Reach": reach, "operandsOK": operands_ok, "value": value,
                      "lower": 0, "upper": 10}, correct, expected)
        if name == "live-overflow":
            record("circular-own-range-guard", {"violation": correct, "Within": within},
                   correct and within, False)
            record("circular-program-ok-guard", {"violation": correct, "ProgramOK": False},
                   correct and False, False)
    for name, program_ok, formula_ok, formula_value in [
        ("guarantee-true", True, True, True),
        ("guarantee-false", True, True, False),
        ("guarantee-fault", True, False, True),
        ("program-fault", False, True, True),
        ("strict-or-true-with-fault", True, False, True),
        ("record-unread-sibling-fault", True, False, True),
    ]:
        record(name, {"ProgramOK": program_ok, "formulaOK": formula_ok, "formulaValue": formula_value},
               not (program_ok and formula_ok and formula_value), name != "guarantee-true")
    record("inactive-payload-not-wf-constrained", {"active": False, "payload": -1, "lower": 0},
           not False or -1 >= 0, True)
    record("lookup-none-not-zero-record", {"matched_rows": 0},
           {"is_some": 0 > 0}, {"is_some": False})
    record("empty-forall", {"bodies": []}, all([]), True)
    record("text-nfc-nfd-distinct", {"left": "é", "right": "e\u0301"}, "é" == "e\u0301", False)
    record("ax-b01-wrong-add-schematic", {"subtotal": 1, "discount": 1, "settled": True},
           {"expected_net": 1 - 1, "actual_net": 1 + 1}, {"expected_net": 0, "actual_net": 2})
    record("ax-b01-wrong-drop-zero-schematic", {"subtotal": 1, "discount": 1, "settled": True},
           {"expected_present": True, "actual_present": 1 - 1 > 0},
           {"expected_present": True, "actual_present": False})
    return cases


def resource_cases():
    result = []
    for name, factors, budget, expected in [
        ("zero-capacity", [0], 0, True),
        ("exact-budget", [3], 3, True),
        ("one-below", [3], 2, False),
        ("huge-before-host-conversion", [10**100], 10000, False),
        ("nested-bindings", [10] * 122, 10000, False),
        ("source-extent-not-output-capacity", [3], 2, False),
    ]:
        # Bounded multiplication models preflight only, never allocates slots.
        value = 1
        fits = True
        for factor in factors:
            if factor and value > budget // factor:
                fits = False
                break
            value *= factor
        fits = fits and value <= budget
        assert fits == expected, name
        result.append({"name": name, "factors": [str(x) for x in factors],
                       "budget": str(budget), "fits": fits})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows = coverage()
    counts = {}
    for row in rows:
        for obligation in row["obligations"]:
            key = obligation["classification"]
            counts[key] = counts.get(key, 0) + 1
    data = {"status": "accepted-scope-static-review-only", "generator_raw": digest(Path(__file__).read_bytes()),
            "review_raw": digest((DEST.parent / "p3-query-encoding-review.md").read_bytes()),
            "inventory_raw": digest((P2 / "cases.tsv").read_bytes()),
            "limits": "Shape inventory and scalar distinctions only; no IR execution, SMT, solver or Evidence.",
            "counts": counts, "coverage": rows,
            "scalar_distinctions": distinctions(), "resource_distinctions": resource_cases()}
    output = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    target = DEST / "materials.json"
    if args.check:
        if not target.is_file() or target.read_bytes() != output:
            raise SystemExit("P3 review materials drift; regenerate and review")
    else:
        DEST.mkdir(parents=True, exist_ok=True)
        target.write_bytes(output)
    print(f"P3 proposal: {len(rows)} IR, {counts}, {len(data['scalar_distinctions'])} scalar / "
          f"{len(data['resource_distinctions'])} resource distinctions; no queries generated")


if __name__ == "__main__":
    main()
