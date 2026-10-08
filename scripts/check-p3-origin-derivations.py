#!/usr/bin/env python3
"""核对真实 Rust 导出、手算区分例和独立篡改；静态缺口不是具体反例。"""
import copy
import json
import sys
from pathlib import Path
from p3_origin_derivation import ROOT, canonical, check, derive, make_set


def reachable(record, root, roles):
    seen, queue = set(), [int(root)]
    while queue:
        p = queue.pop()
        if p not in seen:
            seen.add(p)
            queue += [int(e["step"]) for e in record["steps"][p]["premises"] if e["role"] in roles]
    return seen


def hand_checks(records, rows):
    checks = json.loads((ROOT / "contracts/core-field-origin-v0.1/hand-checks.json").read_bytes())
    count = 0
    for case in checks:
        expected = case["expected"]
        record = next(records[c[0]] for c in rows if c[1] == case["ir"] and records[c[0]]["target"]["interface"] == "out" and records[c[0]]["target"]["name"] == expected["field"])
        root = record["steps"][int(record["roots"]["value"])]
        control = record["steps"][int(record["roots"]["control"])]
        assert root["labels"]["propagated"] == expected["value"], case["name"]
        assert control["labels"]["propagated"] == expected["control"], case["name"]
        assert bool(record["gaps"]) == expected["gaps"], case["name"]
        assignment = record["steps"][int(next(e["step"] for e in root["premises"] if e["role"] == "value"))]
        if expected["inferred"] is not None:
            assert assignment["labels"]["inferred"] == expected["inferred"], case["name"]
        assert set(expected["rules"]) <= {s["rule"] for s in record["steps"]}, case["name"]
        value_dependencies = reachable(record, record["roots"]["value"], {"value", "selection"})
        if case["name"] == "constant-after-gap":
            assert not assignment["gap"]
            assert not set(map(int, record["gaps"])) & value_dependencies
            assert any(s["gap"] and s["item"] == "copy/~😀" for s in record["steps"])
        if case["name"] == "record-sibling":
            assert not any(record["steps"][i]["rule"] == "input.field" and record["steps"][i]["item"] == "secret" for i in value_dependencies)
            assert any(s["rule"] == "input.field" and s["item"] == "secret" for s in record["steps"])
        if case["name"] == "unread-sibling-fault":
            assert not any(record["steps"][i]["rule"] == "expr.int_add" for i in value_dependencies)
        if case["name"] == "sensitive-relabel-after-gap":
            assert not assignment["gap"] and record["gaps"]
        count += 1
    print(f"P3-F hand distinctions: {count}; value/control/evaluation separated; no dynamic counterexamples")


def mutations(record):
    for key in record["binding"]:
        m = copy.deepcopy(record)
        m["binding"][key] = "0.1" if key == "ir_version" else "sha256:" + "0" * 64
        yield "binding-" + key, canonical(m).encode()
    for key in ["format", "format_version", "rule_profile"]:
        m = copy.deepcopy(record); m[key] += "-wrong"
        yield key, canonical(m).encode()
    for key in record["target"]:
        m = copy.deepcopy(record); m["target"][key] += "-wrong"
        yield "target-" + key, canonical(m).encode()
    for key in record["roots"]:
        m = copy.deepcopy(record); m["roots"][key] = "0"
        yield "root-" + key, canonical(m).encode()
    m = copy.deepcopy(record); m["extra"] = True
    yield "extra-member", canonical(m).encode()
    m = copy.deepcopy(record); m["steps"].pop()
    yield "missing-step", canonical(m).encode()
    m = copy.deepcopy(record); m["steps"].append(copy.deepcopy(m["steps"][-1]))
    yield "extra-step", canonical(m).encode()
    m = copy.deepcopy(record); m["steps"][1], m["steps"][2] = m["steps"][2], m["steps"][1]
    yield "reordered-steps", canonical(m).encode()
    for field in ["rule", "item"]:
        m = copy.deepcopy(record); m["steps"][-1][field] += "-wrong"
        yield "step-" + field, canonical(m).encode()
    m = copy.deepcopy(record); m["steps"][-1]["anchor"]["id"] += "-wrong"
    yield "anchor", canonical(m).encode()
    m = copy.deepcopy(record); m["steps"][-1]["path"] = ["not-a-path"]
    yield "path", canonical(m).encode()
    for field in record["steps"][-1]["labels"]:
        m = copy.deepcopy(record); old = m["steps"][-1]["labels"][field]
        m["steps"][-1]["labels"][field] = "sensitive" if old == "public" else "public"
        yield "label-" + field, canonical(m).encode()
    for role in ["value", "selection", "evaluation", "declaration"]:
        m = copy.deepcopy(record)
        s = next(s for s in reversed(m["steps"]) if any(e["role"] == role for e in s["premises"]))
        s["premises"] = [e for e in s["premises"] if e["role"] != role]
        yield "missing-" + role + "-edges", canonical(m).encode()
    m = copy.deepcopy(record); m["steps"][-1]["premises"][0]["role"] = "evaluation"
    yield "value-as-evaluation", canonical(m).encode()
    m = copy.deepcopy(record); m["steps"][-1]["premises"][0]["step"] = str(len(m["steps"])-1)
    yield "cyclic-premise", canonical(m).encode()
    m = copy.deepcopy(record); m["steps"][-1]["premises"][0]["step"] = str(len(m["steps"])+1)
    yield "forward-premise", canonical(m).encode()
    m = copy.deepcopy(record); m["steps"][-1]["premises"].append(m["steps"][-1]["premises"][0].copy())
    yield "duplicate-premise", canonical(m).encode()
    m = copy.deepcopy(record); m["gaps"] = []
    yield "omitted-gaps", canonical(m).encode()
    m = copy.deepcopy(record)
    for s in m["steps"]:
        s["gap"] = False
    m["gaps"] = []
    yield "hidden-gap-and-index", canonical(m).encode()
    m = copy.deepcopy(record); m["steps"][-1]["gap"] = True; m["gaps"].append(str(len(m["steps"])-1))
    yield "invented-gap", canonical(m).encode()
    data = canonical(record).encode()
    yield "leading-whitespace", b" " + data
    yield "trailing-newline", data + b"\n"
    yield "duplicate-member", b'{"format_version":"0.1",' + data[1:]


def main():
    directory = Path(sys.argv[1])
    rows = [line.split("\t") for line in (ROOT / "contracts/core-field-origin-v0.1/cases.tsv").read_text().splitlines()]
    records = {}
    for c in rows:
        ir = json.loads((ROOT / c[1]).read_bytes())
        expected, _ = derive(ir, make_set(ir), c[3])
        actual = (directory / (c[0] + ".jcs")).read_bytes()
        assert actual == canonical(expected).encode(), c[0]
        records[c[0]] = json.loads(actual)
    hand_checks(records, rows)
    source = next(c for c in rows if c[0].startswith("origin-join-secret-pairs-") and records[c[0]]["target"]["name"] == "result")
    original = records[source[0]]
    manifest = []
    for name, data in mutations(original):
        # 拒绝必须对原 IR / P2 独立重建，不能仅看目标记录是否 JSON 良构。
        ir = json.loads((ROOT / source[1]).read_bytes())
        expected, _ = derive(ir, make_set(ir), source[3])
        try:
            check(ir, make_set(ir), source[3], data)
        except AssertionError:
            pass
        else:
            raise AssertionError("accepted mutation: " + name)
        path = "mutation-" + name + ".jcs"
        (directory / path).write_bytes(data)
        manifest.append("\t".join([source[1], source[3], path]))
    (directory / "mutations.tsv").write_text("\n".join(manifest) + "\n")
    print(f"P3-F independent checker: {len(rows)} Rust records; {len(manifest)} record mutations rejected")


if __name__ == "__main__":
    main()
