#!/usr/bin/env python3
"""P3-D 真实 SMT / 中间观察与独立具体期望；局部变异单列，不调用 solver。"""
import argparse
import copy
import itertools
import json
from pathlib import Path
import runpy

from p3_query_semantics import Interpreter
from p3_coverage_semantics import coverage, observe, results

ROOT = Path(__file__).resolve().parents[1]
Smt = runpy.run_path(str(ROOT / "scripts/check-p3-query-semantics.py"))["Smt"]


def values(smt, assignment):
    """读取全部已有 term 的值用于观察；SMT 文本仍由冻结严格解析器验收。"""
    assert set(assignment) == set(smt.symbols)
    out = []
    for sort, op, args in smt.instructions:
        if op == "input": value = assignment[args]
        elif op == "literal": value = args
        elif op == "and": value = all(out[i] for i in args)
        elif op == "or": value = any(out[i] for i in args)
        elif op == "not": value = not out[args[0]]
        elif op == "ite": value = out[args[1] if out[args[0]] else args[2]]
        elif op == "+": value = out[args[0]] + out[args[1]]
        elif op == "-": value = -out[args[0]] if len(args) == 1 else out[args[0]] - out[args[1]]
        elif op == "=": value = out[args[0]] == out[args[1]]
        elif op == "<": value = out[args[0]] < out[args[1]]
        elif op == "<=": value = out[args[0]] <= out[args[1]]
        elif op == ">": value = out[args[0]] > out[args[1]]
        elif op == ">=": value = out[args[0]] >= out[args[1]]
        else: raise AssertionError(op)
        assert type(value) is {"Bool": bool, "Int": int, "Text": str}[sort]
        out.append(value)
    return out


def decode(interpreter, ty, leaves):
    kind = ty["kind"]
    if kind == "record":
        return {f["name"]: decode(interpreter, f["type"], leaves) for f in interpreter.records[ty["record_type"]]["fields"]}
    if kind == "option":
        some = next(leaves)
        inner = decode(interpreter, ty["inner"], leaves)
        return {"some": inner} if some else None
    return next(leaves)


def ordered(rows):
    return sorted(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in rows)


def observed(document, world, target, smt, trace, computed):
    read = lambda name: computed[smt.names[name]]
    if not read(trace["ready"]):
        return {"ready": False, "expected_keys": None, "output": None}
    interpreter = Interpreter(document, world)
    node = interpreter.nodes[target["definition"]["subject"]["id"]]
    ty = {"kind": "record", "record_type": interpreter.tables[node["table_type"]]["record_type"]}
    chosen = [[read(k) for k in keys] for select, keys in zip(trace["selected"], trace["expected_keys"]) if read(select)]
    output = [decode(interpreter, ty, iter(read(t) for t in slot["lanes"])) for slot in trace["output"] if read(slot["active"])]
    return {"ready": True, "expected_keys": chosen, "output": output}


def check_observation(actual, expected):
    assert actual["ready"] == expected["ready"], (actual, expected)
    if actual["ready"]:
        assert ordered(actual["expected_keys"]) == ordered(expected["expected_keys"]), (actual, expected)
        assert ordered(actual["output"]) == ordered(expected["output"]), (actual, expected)


def observation_mutations(document, world, target, smt, trace, assignment, expected):
    """测试专用 term 导出的错误观察；在合法程序世界核对选择和完整行，而非只看恒假断言。"""
    found = set()
    if not expected["ready"]:
        return found
    variants = {}
    mutant = copy.deepcopy(smt)
    for name in trace["selected"]:
        mutant.instructions[mutant.names[name]] = ("Bool", "literal", False)
    variants["wrong-selection"] = mutant
    mutant = copy.deepcopy(smt)
    for slot in trace["output"]:
        mutant.instructions[mutant.names[slot["active"]]] = ("Bool", "literal", False)
    variants["truncate-observed-output"] = mutant
    mutant = copy.deepcopy(smt)
    for keys in trace["expected_keys"]:
        if len(keys) == 2 and all(mutant.instructions[mutant.names[k]][0] == "Int" for k in keys):
            a, b = [mutant.names[k] for k in keys]
            mutant.instructions[a], mutant.instructions[b] = mutant.instructions[b], mutant.instructions[a]
    variants["wrong-key-projection"] = mutant
    for name, mutant in variants.items():
        actual = observed(document, world, target, mutant, trace, values(mutant, assignment))
        try:
            check_observation(actual, expected)
        except AssertionError:
            found.add(name)
    return found


def local_only(directory):
    smt = Smt((directory / "local.smt2").read_bytes())
    symbols = json.loads((directory / "local.json").read_bytes())
    origins = {s["name"]: s["origin"] for s in symbols}
    assert smt.instructions[smt.assertion][1] == "and"
    ready, failure = smt.instructions[smt.assertion][2]
    relation = smt.instructions[failure][2][0]
    forward, backward = smt.instructions[relation][2]
    variants = {}
    for name, keep in [("omit-forward", backward), ("omit-backward", forward)]:
        mutant = copy.deepcopy(smt)
        mutant.instructions[relation] = ("Bool", "and", [keep, keep])
        variants[name] = mutant
    mutant = copy.deepcopy(smt)
    for i, (sort, op, args) in enumerate(mutant.instructions):
        if op == "=" and smt.instructions[args[0]][1] == "+":
            mutant.instructions[i] = (sort, ">=", args)
    variants["exists-not-exactly-one"] = mutant
    def key_eq(i):
        _, op, args = smt.instructions[i]
        if op != "or": return False
        _, op, pair = smt.instructions[args[-1]]
        return op == "=" and all(smt.instructions[k][1] == "input" for k in pair)
    matches = [i for i, (_, op, args) in enumerate(smt.instructions) if op == "and" and len(args) == 2 and all(key_eq(k) for k in args)]
    assert len(matches) == 9
    for name in ["one-key-only", "any-key", "match-true", "slot-index-match"]:
        mutant = copy.deepcopy(smt)
        for pair, i in enumerate(matches):
            _, _, args = mutant.instructions[i]
            if name == "one-key-only": mutant.instructions[i] = ("Bool", "and", [args[0], args[0]])
            elif name == "any-key": mutant.instructions[i] = ("Bool", "or", args)
            else: mutant.instructions[i] = ("Bool", "literal", True if name == "match-true" else pair // 3 == pair % 3)
        variants[name] = mutant
    active = {o["interface"]: {} for o in origins.values()}
    for name, o in origins.items():
        if o["component"] == "active": active[o["interface"]][int(o["slot"])] = name
    mutant = copy.deepcopy(smt)
    for slot, name in active["source"].items():
        mutant.instructions[mutant.names[name]] = ("Bool", "input", active["output"][slot])
    variants["output-derived-selection"] = mutant
    mutant = copy.deepcopy(smt)
    mutant.assertion = failure
    variants["omit-ready"] = mutant
    for name, slot in [("target-ok-guard", 1), ("program-ok-guard", 2)]:
        mutant = copy.deepcopy(smt)
        guard = smt.names[active["guards"][slot]]
        mutant.assertion = mutant.add("Bool", "and", [mutant.assertion, guard])
        variants[name] = mutant
    mutant = copy.deepcopy(smt)
    mutant.assertion = mutant.add("Bool", "literal", False)
    variants["false-violation"] = mutant
    interpreter = Interpreter(json.loads((ROOT / "contracts/map-filter-query-v0.3/inputs/composite-unicode.jcs").read_bytes()), {})
    input_node = next(n for n in interpreter.nodes.values() if n["kind"] == "input")
    ty = {"kind": "record", "record_type": interpreter.tables[input_node["table_type"]]["record_type"]}
    row = interpreter.default(ty)
    # 独立两侧可以为空、稀疏、乱序、遗漏、额外或重复；没有程序 WF 守卫。
    patterns = [[], [(0, 0)], [(0, 1)], [(1, 0)], [(0, 0), (1, 1)], [(1, 1), (0, 0)],
                [(0, 0), (0, 0)], [None, (0, 0)], [(0, 0), (1, 1), (2, 2)]]
    found, count = set(), 0
    for source, output, is_ready, target_ok, program_ok in itertools.product(patterns, patterns, [False, True], [False, True], [False, True]):
        chosen = [list(k) for k in source if k is not None]
        out = [list(k) for k in output if k is not None]
        expected = is_ready and not coverage(chosen, out)
        assignment = {}
        sides = {"source": source, "output": output}
        for name, origin in origins.items():
            slot = int(origin["slot"])
            if origin["interface"] == "guards":
                value = [is_ready, target_ok, program_ok][slot]
            else:
                entries = sides[origin["interface"]]
                key = entries[slot] if slot < len(entries) else None
                if origin["component"] == "active": value = key is not None
                else:
                    record = {**row, "key": key[0] if key else 99, "x": key[1] if key else -99}
                    value = interpreter.flatten(ty, record)[int(origin["component"])]
            assignment[name] = value
        assert smt.evaluate(assignment) == expected, (source, output, is_ready)
        found.update(name for name, mutant in variants.items() if mutant.evaluate(assignment) != expected)
        count += 1
    assert found == set(variants), (found, set(variants) - found)
    print(f"synthetic relation only: {count} assignments / {len(found)} mutation classes; not legal program counterexamples")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args()
    if args.local_only:
        local_only(args.directory)
        return
    cases = json.loads((ROOT / "contracts/map-filter-query-v0.4/cases.json").read_bytes())["cases"]
    count, comparisons, observations, found = 0, 0, 0, set()
    for case in cases:
        doc = json.loads((ROOT / case["ir"]).read_bytes())
        queries = []
        for index, target in enumerate(case["targets"]):
            stem = args.directory / (case["name"] + "-" + str(index))
            smt = Smt(stem.with_suffix(".smt2").read_bytes())
            symbols = json.loads(stem.with_suffix(".json").read_bytes())
            assert {s["name"]: s["sort"] for s in symbols} == smt.symbols
            trace = json.loads(stem.with_suffix(".trace.json").read_bytes()) if target["definition"]["kind"] == "row-coverage" else None
            queries.append((smt, symbols, trace))
        for world, expected, obs in zip(case["worlds"], case["expected"], case["coverage_observations"]):
            assert results(doc, world, case["targets"]) == expected
            for i, (smt, symbols, trace) in enumerate(queries):
                assignment = Interpreter(doc, world).assignment(symbols)
                assert smt.evaluate(assignment) == expected[i], (case["name"], i, world)
                comparisons += 1
                if trace is not None:
                    target = case["targets"][i]
                    independent = observe(doc, world, target["definition"]["subject"]["id"])
                    assert independent == obs[target["id"]]
                    got = observed(doc, world, target, smt, trace, values(smt, assignment))
                    check_observation(got, independent)
                    observations += 1
                    if case["name"] in {"composite-key-permutation", "capacity-sparse"}:
                        found.update(observation_mutations(doc, world, target, smt, trace, assignment, independent))
        count += len(queries)
        print(f"{case['name']}: {len(queries)} queries and intermediate observations matched", flush=True)
    assert found == {"wrong-selection", "truncate-observed-output", "wrong-key-projection"}, found
    print(f"P3-D passed: {count} queries / {comparisons} assignments / {observations} observations / {len(found)} observation mutations; no solver or proof")


if __name__ == "__main__":
    main()
