#!/usr/bin/env python3
"""独立解释真实 P3-C SMT；程序有限语义和局部合成唯一键谓词分别报告。"""
import argparse
import copy
import itertools
import json
from pathlib import Path
import runpy

from p3_query_semantics import FAULT, Interpreter
from p3_cardinality_semantics import prepared, results

ROOT = Path(__file__).resolve().parents[1]
Smt = runpy.run_path(str(ROOT / "scripts/check-p3-query-semantics.py"))["Smt"]


def mutations(case, document, actual, queries):
    found = set()
    keys = [i for i, t in enumerate(case["targets"]) if t["definition"]["kind"] == "key-cardinality"]
    totals = [i for i, t in enumerate(case["targets"]) if t["definition"]["kind"] == "totality"]
    guarantees = [i for i, t in enumerate(case["targets"]) if t["definition"]["kind"] == "contract-guarantee"]
    for i in keys:
        smt, symbols = queries[i]
        _, op, args = smt.instructions[smt.assertion]
        assert op == "and" and len(args) == 3
        violation = args[-1]
        _, op, (ready, failure) = smt.instructions[violation]
        assert op == "and"
        _, op, (not_unique, not_capacity) = smt.instructions[failure]
        assert op == "or"
        capacity = smt.instructions[not_capacity][2][0]
        _, op, (count, bound) = smt.instructions[capacity]
        assert op == "<="
        variants = {}
        mutant = copy.deepcopy(smt)
        mutant.assertion = mutant.add("Bool", "and", [mutant.assertion, ready, capacity])
        variants["target-ok-guard"] = mutant
        mutant = copy.deepcopy(smt)
        mutant.assertion = mutant.add("Bool", "and", [*args[:2], failure])
        variants["omit-ready"] = mutant
        mutant = copy.deepcopy(smt)
        mutant.instructions[capacity] = ("Bool", "<", [count, bound])
        variants["strict-capacity"] = mutant
        mutant = copy.deepcopy(smt)
        # 实际表示槽位由目标来源链的 input 容量决定。
        interpreter = Interpreter(document, {})
        node = interpreter.nodes[case["targets"][i]["definition"]["subject"]["id"]]
        while node["kind"] != "input":
            node = interpreter.nodes[node["source"]]
        extent = int(interpreter.tables[node["table_type"]]["capacity"])
        mutant.instructions[count] = ("Int", "literal", extent)
        variants["slot-count"] = mutant
        mutant = copy.deepcopy(smt)
        # 截断行会使 min(count, capacity) <= capacity 恒成立。
        truncated = mutant.add("Int", "ite", [capacity, count, bound])
        fits = mutant.add("Bool", "<=", [truncated, bound])
        bad_capacity = mutant.add("Bool", "not", [fits])
        bad_failure = mutant.add("Bool", "or", [not_unique, bad_capacity])
        bad_violation = mutant.add("Bool", "and", [ready, bad_failure])
        mutant.assertion = mutant.add("Bool", "and", [*args[:2], bad_violation])
        variants["truncate-output"] = mutant
        mutant = copy.deepcopy(smt)
        mutant.instructions[not_capacity] = ("Bool", "literal", False)
        variants["omit-capacity"] = mutant
        mutant = copy.deepcopy(smt)
        mutant.assertion = mutant.add("Bool", "literal", False)
        variants["assert-false"] = mutant
        for name, mutant in variants.items():
            if any(mutant.evaluate(Interpreter(document, w).assignment(symbols)) != row[i]
                   for w, row in zip(case["worlds"], actual)):
                found.add(name)
        # 错误归因组合的每列均来自真实 SMT；不冒充单条 AST 变异。
        if any((row[i] and not any(row[j] for j in totals)) != row[i] for row in actual):
            found.add("program-ok-guard")
        if any((row[i] or any(row[j] for j in guarantees)) != row[i] for row in actual):
            found.add("guarantee-as-key-fault")
        if any(row[i] != row[j] for row in actual for j in keys):
            found.add("wrong-target")
    return found


def unique_only(directory):
    """不使用输入 WF：注入 O* 包含合法程序不能产生的重复键。"""
    document = json.loads((ROOT / "contracts/map-filter-query-v0.3/inputs/composite-unicode.jcs").read_bytes())
    case = next(c for c in json.loads((ROOT / "contracts/map-filter-query-v0.3/cases.json").read_bytes())["cases"]
                if c["name"] == "composite-unicode")
    row = next(s["row"] for w in case["worlds"] for s in w["in"] if s["active"])
    smt = Smt((directory / "unique.smt2").read_bytes())
    symbols = json.loads((directory / "unique.json").read_bytes())
    found, count = set(), 0
    _, op, (not_both, different) = smt.instructions[smt.assertion]
    assert op == "or"
    equal = smt.instructions[different][2][0]
    _, op, components = smt.instructions[equal]
    assert op == "and" and len(components) == 2
    variants = {}
    mutant = copy.deepcopy(smt)
    mutant.instructions[equal] = ("Bool", "or", components)
    variants["any-component-equal"] = mutant
    mutant = copy.deepcopy(smt)
    mutant.assertion = different
    variants["omit-active-guard"] = mutant
    mutant = copy.deepcopy(smt)
    mutant.assertion = mutant.add("Bool", "literal", True)
    variants["ignore-collision"] = mutant
    for active0, active1, key, text in itertools.product([False, True], [False, True], [0, 1], ["é", "e\u0301"]):
        world = {"in": [{"active": active0, "row": {**row, "key": 0, "text": "é"}},
                        {"active": active1, "row": {**row, "key": key, "text": text}}]}
        expected = not (active0 and active1 and key == 0 and text == "é")
        assignment = Interpreter(document, world).assignment(symbols)
        assert smt.evaluate(assignment) == expected, world
        found.update(name for name, mutant in variants.items() if mutant.evaluate(assignment) != expected)
        count += 1
    assert found == set(variants), found
    print(f"synthetic O* predicate only: {count} assignments / {len(found)} mutation classes; not program counterexamples")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--unique-only", action="store_true")
    args = parser.parse_args()
    if args.unique_only:
        unique_only(args.directory)
        return
    cases = json.loads((ROOT / "contracts/map-filter-query-v0.3/cases.json").read_bytes())["cases"]
    comparisons, count, found = 0, 0, set()
    for case in cases:
        document = json.loads((ROOT / case["ir"]).read_bytes())
        queries = []
        for index, _ in enumerate(case["targets"]):
            stem = args.directory / (case["name"] + "-" + str(index))
            smt = Smt(stem.with_suffix(".smt2").read_bytes())
            symbols = json.loads(stem.with_suffix(".json").read_bytes())
            assert {s["name"]: s["sort"] for s in symbols} == smt.symbols
            queries.append((smt, symbols))
        actual = []
        for world, expected, observations in zip(case["worlds"], case["expected"], case["prepared_observations"]):
            assert results(document, world, case["targets"]) == expected, "concrete expectation drift"
            interpreter = Interpreter(document, world)
            for target in case["targets"]:
                if target["definition"]["kind"] == "key-cardinality":
                    rows = prepared(interpreter, target["definition"]["subject"]["id"])
                    assert observations[target["id"]] == {"ready": rows is not FAULT, "rows": None if rows is FAULT else rows}
            got = [smt.evaluate(Interpreter(document, world).assignment(symbols)) for smt, symbols in queries]
            assert got == expected, (case["name"], world, expected, got)
            actual.append(got)
            comparisons += len(queries)
        if case["name"] in {"filter-capacity", "predicate-fault-capacity", "capacity-sparse", "capacity-unrelated-fault", "false-guarantee"}:
            found.update(mutations(case, document, actual, queries))
        count += len(queries)
        print(f"{case['name']}: {len(queries)} actual queries matched independent worlds", flush=True)
    assert found == {"target-ok-guard", "program-ok-guard", "omit-ready", "strict-capacity", "slot-count",
                     "truncate-output", "omit-capacity", "assert-false", "guarantee-as-key-fault", "wrong-target"}, found
    print(f"P3-C semantic comparison passed: {count} queries / {comparisons} assignments / {len(found)} mutation classes; no solver or proof")


if __name__ == "__main__":
    main()
