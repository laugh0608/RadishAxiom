#!/usr/bin/env python3
"""独立解释 P3-B 实际 SMT；有限语义 / 变异比较，不调用 solver。"""
import argparse
import copy
import json
from pathlib import Path
import runpy

from p3_query_semantics import Interpreter
from p3_totality_semantics import results

ROOT = Path(__file__).resolve().parents[1]
Smt = runpy.run_path(str(ROOT / "scripts/check-p3-query-semantics.py"))["Smt"]


def mutations(case, document, actual, queries):
    """实际 SMT term 变异及多目标查询的错误归因组合；不是 proof。"""
    found = set()
    totals = [i for i, t in enumerate(case["targets"]) if t["definition"]["kind"] == "totality"]
    guarantees = [i for i, t in enumerate(case["targets"]) if t["definition"]["kind"] == "contract-guarantee"]
    for i in totals:
        smt, symbols = queries[i]
        _, op, args = smt.instructions[smt.assertion]
        assert op == "and" and len(args) == 3
        violation = args[-1]
        assert smt.instructions[violation][1] == "not"
        target_ok = smt.instructions[violation][2][0]
        _, op, target_args = smt.instructions[target_ok]
        assert op == "and" and len(target_args) >= 3
        source_ok = target_args[0]
        variants = {}
        for name, guard in [("target-ok-guard", target_ok), ("source-ok-guard", source_ok)]:
            mutant = copy.deepcopy(smt)
            mutant.assertion = mutant.add("Bool", "and", [mutant.assertion, guard])
            variants[name] = mutant
        mutant = copy.deepcopy(smt)
        mutant.instructions[target_ok] = ("Bool", "and", target_args[:-1])
        variants["omit-capacity"] = mutant
        mutant = copy.deepcopy(smt)
        mutant.instructions[target_ok] = ("Bool", "and", target_args[1:])
        variants["ignore-upstream"] = mutant
        mutant = copy.deepcopy(smt)
        mutant.assertion = mutant.add("Bool", "literal", False)
        variants["assert-false"] = mutant
        for name, mutant in variants.items():
            if any(mutant.evaluate(Interpreter(document, w).assignment(symbols)) != row[i]
                   for w, row in zip(case["worlds"], actual)):
                found.add(name)
        # 每列均来自实际、严格解析的查询；OR / 换列模拟错误的目标归因。
        if any(any(row[j] for j in totals) != row[i] for row in actual):
            found.add("global-program-fault")
        if any((row[i] or any(row[j] for j in guarantees)) != row[i] for row in actual):
            found.add("guarantee-as-node-fault")
        if any(row[j] != row[i] for row in actual for j in totals):
            found.add("wrong-target")
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    cases = json.loads((ROOT / "contracts/map-filter-query-v0.2/cases.json").read_bytes())["cases"]
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
        for world, expected in zip(case["worlds"], case["expected"]):
            assert results(document, world, case["targets"]) == expected, "concrete expectation drift"
            got = [smt.evaluate(Interpreter(document, world).assignment(symbols)) for smt, symbols in queries]
            assert got == expected, (case["name"], world, expected, got)
            actual.append(got)
            comparisons += len(queries)
        # 大容量 AX-B01 保留正常比较；变异在专用合成材料上区分即可。
        if case["name"] in {"filter-capacity", "node-strict-or", "independent-node-fault", "false-guarantee"}:
            found.update(mutations(case, document, actual, queries))
        count += len(queries)
        print(f"{case['name']}: {len(queries)} actual queries matched independent worlds", flush=True)
    assert found == {"target-ok-guard", "source-ok-guard", "omit-capacity", "ignore-upstream", "assert-false",
                     "global-program-fault", "guarantee-as-node-fault", "wrong-target"}, found
    print(f"P3-B semantic comparison passed: {count} queries / {comparisons} assignments / {len(found)} mutation classes; no solver or proof")


if __name__ == "__main__":
    main()
