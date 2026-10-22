#!/usr/bin/env python3
"""核对实际 Rust 空效果记录，并导出生产 strict 必须拒绝的精确变异。"""
import argparse
import copy
import json
from pathlib import Path
from p3_effect_derivation import ROOT, canonical, check, derive, digest, make_set


def record_mutations(record):
    for field in record["binding"]:
        value = copy.deepcopy(record)
        value["binding"][field] = "wrong"
        yield "binding-" + field, value
    for field in ["format", "format_version", "rule_profile", "root"]:
        value = copy.deepcopy(record); value[field] = "wrong"
        yield field, value
    for name in ["missing", "duplicate", "extra", "reversed", "wrong-rule", "wrong-path", "wrong-anchor", "forward-ref", "missing-premise", "extra-premise"]:
        value = copy.deepcopy(record)
        if name == "missing": value["steps"].pop(0)
        elif name == "duplicate": value["steps"].insert(0, value["steps"][0])
        elif name == "extra": value["unexpected"] = []
        elif name == "reversed": value["steps"].reverse()
        elif name == "wrong-rule": value["steps"][0]["rule"] = "assume-pure"
        elif name == "wrong-path": value["steps"][0]["path"] = ["fake"]
        elif name == "wrong-anchor": value["steps"][0]["anchor"]["id"] = "wrong"
        elif name == "forward-ref": value["steps"][0]["premises"] = [value["root"]]
        elif name == "missing-premise": value["steps"][-1]["premises"].pop()
        else: value["steps"][-1]["premises"].append("0")
        yield name, value
    # 定位真实分支、字段或接口，不把所有删除统一算作一类规则检验。
    for op, name, index in [("expr.if", "omit-else", 2), ("expr.match_option", "omit-some", 2),
                            ("expr.record", "omit-record-field", 0), ("expr.sum_where", "omit-sum-value", 2),
                            ("node.lookup_join", "omit-join-side", 1), ("node.group", "omit-group-source", 0),
                            ("contract.noninterference", "omit-ni-interface", 0)]:
        match = next((i for i, s in enumerate(record["steps"]) if s["rule"] == op), None)
        if match is not None:
            value = copy.deepcopy(record); value["steps"][match]["premises"].pop(index)
            yield name, value


def invalid_inputs(ir):
    value = copy.deepcopy(ir); value["effects"] = ["filesystem"]
    yield "external-effect", value
    value = copy.deepcopy(ir); value["nodes"][0]["definition"]["capability"] = "network"
    yield "hidden-node-capability", value
    value = copy.deepcopy(ir); value["nodes"][0]["definition"]["kind"] = "external_call"
    yield "external-node", value
    # 新增明确 formula，以避免依赖样本是否已含某种表达式。
    for name, expression in [
        ("unknown-dead-branch", {"op": "if", "condition": {"op": "literal_bool", "value": True},
                                  "then": {"op": "literal_bool", "value": True}, "else": {"op": "external_call"}, "result_type": {"kind": "bool"}}),
        ("hidden-expression-member", {"op": "literal_bool", "value": True, "effects": []}),
        ("unbound-reference", {"op": "bound", "index": "0"}),
        ("assume-output", {"op": "forall_rows", "table": {"kind": "output", "name": ir["outputs"][0]["name"]},
                            "body": {"op": "literal_bool", "value": True}}),
    ]:
        value = copy.deepcopy(ir)
        value["contracts"] = [{"id": "synthetic-negative", "definition": {"kind": "formula", "role": "assume", "expression": expression}}]
        yield name, value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    mutations, coverage, total = [], set(), 0
    for line in (ROOT / "contracts/core-empty-effects-v0.1/cases.tsv").read_text().splitlines():
        name, source, ir_digest, expected, raw, *_ = line.split("\t")
        ir_bytes = (ROOT / source).read_bytes()
        assert digest(ir_bytes) == ir_digest
        ir = json.loads(ir_bytes)
        obligations = make_set(ir)
        actual = (args.directory / (name + ".jcs")).read_bytes()
        record = check(ir, obligations, actual)
        assert actual == (ROOT / expected).read_bytes() and digest(actual) == raw
        total += 1
        for mutation, changed in record_mutations(record):
            if mutation in coverage: continue
            data = canonical(changed).encode()
            try: check(ir, obligations, data)
            except AssertionError: pass
            else: raise AssertionError("mutant accepted: " + mutation)
            coverage.add(mutation)
            path = f"mutant-{len(mutations)}.jcs"
            (args.directory / path).write_bytes(data)
            mutations.append("\t".join([source, path]))
    assert len(coverage) == 28, coverage
    for suffix in [b"\n", b" "]:
        try: check(ir, obligations, actual + suffix)
        except AssertionError: pass
        else: raise AssertionError("noncanonical accepted")
    negatives = set()
    negative_rows = []
    for name, value in invalid_inputs(ir):
        try: derive(value, make_set(value))
        except (AssertionError, KeyError): negatives.add(name)
        else: raise AssertionError("invalid effect construct accepted: " + name)
        filename = f"negative-{name}.jcs"
        (args.directory / filename).write_bytes(canonical(value).encode())
        negative_rows.append("\t".join([source, filename]))
    assert len(negatives) == 7
    (args.directory / "mutations.tsv").write_text("\n".join(mutations) + "\n")
    (args.directory / "negatives.tsv").write_text("\n".join(negative_rows) + "\n")
    print(f"P3-E independent check: {total} actual records / {len(coverage)} record mutation classes / {len(negatives)} synthetic effect-rule negatives; P1 typing remains a premise; no proof")


if __name__ == "__main__": main()
