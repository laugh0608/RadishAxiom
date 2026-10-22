#!/usr/bin/env python3
"""解释实际 P3 SMT 文本，与独立具体求值和冻结小域期望比较；不调用 solver。"""
import argparse
import json
from pathlib import Path
import re

from p3_query_semantics import Interpreter

ROOT = Path(__file__).resolve().parents[1]


def parse(text):
    tokens = re.findall(r"[()]|[^()\s]+", text)
    stack, result = [], None
    for token in tokens:
        if token == "(":
            stack.append([])
        elif token == ")":
            assert stack, "unmatched close"
            value = stack.pop()
            if stack:
                stack[-1].append(value)
            else:
                assert result is None, "multiple forms per line"
                result = value
        else:
            assert stack, "atom outside form"
            stack[-1].append(token)
    assert not stack and result is not None, "unclosed form"
    return result


class Smt:
    def __init__(self, data):
        assert data.isascii() and data.endswith(b"\n") and not data.endswith(b"\n\n")
        assert b"\r" not in data and b";" not in data
        lines = data.decode("ascii").splitlines()
        assert lines[:2] == ["(set-logic QF_UFLIA)", "(declare-sort Text 0)"]
        assert lines[-1] == "(check-sat)"
        self.instructions, self.symbols, self.names = [], {}, {}
        for line in lines[2:-2]:
            form = parse(line)
            assert form[0] in {"declare-const", "define-fun"}, "unexpected command"
            name = form[1]
            assert re.fullmatch(r"q[0-9a-f]{64}_t[0-9]+", name) and name not in self.names
            if form[0] == "declare-const":
                assert len(form) == 3 and form[2] in {"Bool", "Int", "Text"}
                idx = self.add(form[2], "input", name)
                self.symbols[name] = form[2]
            else:
                assert len(form) == 5 and form[2] == [] and form[3] in {"Bool", "Int", "Text"}
                idx = self.compile(form[4])
                assert self.instructions[idx][0] == form[3], "definition sort mismatch"
            self.names[name] = idx
        assertion = parse(lines[-2])
        assert len(assertion) == 2 and assertion[0] == "assert"
        self.assertion = self.compile(assertion[1])
        assert self.instructions[self.assertion][0] == "Bool"

    def add(self, sort, op, args):
        self.instructions.append((sort, op, args))
        return len(self.instructions) - 1

    def compile(self, expression):
        if isinstance(expression, str):
            if expression in self.names:
                return self.names[expression]
            if expression in {"true", "false"}:
                return self.add("Bool", "literal", expression == "true")
            assert re.fullmatch(r"0|[1-9][0-9]*", expression), "unbound / invalid atom"
            return self.add("Int", "literal", int(expression))
        op, *operands = expression
        args = [self.compile(e) for e in operands]
        sorts = [self.instructions[i][0] for i in args]
        if op == "not":
            assert sorts == ["Bool"]
            sort = "Bool"
        elif op in {"and", "or"}:
            assert len(sorts) >= 2 and set(sorts) == {"Bool"}
            sort = "Bool"
        elif op == "=":
            assert len(sorts) == 2 and sorts[0] == sorts[1]
            sort = "Bool"
        elif op in {"<", "<=", ">", ">="}:
            assert sorts == ["Int", "Int"]
            sort = "Bool"
        elif op in {"+", "-"}:
            assert sorts == ["Int", "Int"] or (op == "-" and sorts == ["Int"])
            sort = "Int"
        elif op == "ite":
            assert len(sorts) == 3 and sorts[0] == "Bool" and sorts[1] == sorts[2]
            sort = sorts[1]
        else:
            raise AssertionError("unexpected SMT operator " + op)
        return self.add(sort, op, args)

    def evaluate(self, assignment):
        assert set(assignment) == set(self.symbols), "symbol coverage differs"
        for name, sort in self.symbols.items():
            assert type(assignment[name]) is {"Bool": bool, "Int": int, "Text": str}[sort]
        values = []
        for _, op, args in self.instructions:
            if op == "literal":
                value = args
            elif op == "input":
                value = assignment[args]
            elif op == "not":
                value = not values[args[0]]
            elif op == "and":
                value = all(values[i] for i in args)
            elif op == "or":
                value = any(values[i] for i in args)
            elif op == "ite":
                value = values[args[1] if values[args[0]] else args[2]]
            elif op == "+":
                value = values[args[0]] + values[args[1]]
            elif op == "-":
                value = -values[args[0]] if len(args) == 1 else values[args[0]] - values[args[1]]
            elif op == "=":
                value = values[args[0]] == values[args[1]]
            elif op == "<":
                value = values[args[0]] < values[args[1]]
            elif op == "<=":
                value = values[args[0]] <= values[args[1]]
            elif op == ">":
                value = values[args[0]] > values[args[1]]
            elif op == ">=":
                value = values[args[0]] >= values[args[1]]
            else:
                raise AssertionError(op)
            values.append(value)
        return values[self.assertion]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    cases = json.loads((ROOT / "contracts/map-filter-query-v0.1/cases.json").read_bytes())["cases"]
    comparisons = 0
    queries = 0
    mutation_rejections = 0
    for case in cases:
        document = json.loads((ROOT / case["ir"]).read_bytes())
        actual_outputs = []
        for index, target in enumerate(case["targets"]):
            stem = args.directory / (case["name"] + "-" + str(index))
            query_bytes = stem.with_suffix(".smt2").read_bytes()
            smt = Smt(query_bytes)
            symbols = json.loads(stem.with_suffix(".json").read_bytes())
            assert {s["name"]: s["sort"] for s in symbols} == smt.symbols
            actual = []
            for world_index, world in enumerate(case["worlds"]):
                expected = case["expected"][world_index][index]
                interpreter = Interpreter(document, world)
                recomputed = interpreter.results(case["targets"])[index]
                assert expected == recomputed, "independent expectation drift"
                got = smt.evaluate(interpreter.assignment(symbols))
                assert got == expected, (case["name"], target["definition"], world_index, world, expected, got)
                actual.append(got)
                comparisons += 1
            actual_outputs.append(actual)
            queries += 1
            if case["name"] == "int-add" and target["definition"]["kind"] == "numeric-range":
                # 语法 / 类型仍合法的错误数学与恒假目标必须被独立世界区分。
                altered = query_bytes.replace(b"(+ ", b"(- ", 1)
                lines = query_bytes.splitlines()
                lines[-2] = b"(assert false)"
                for mutation in [altered, b"\n".join(lines) + b"\n"]:
                    bad = Smt(mutation)
                    assert any(bad.evaluate(Interpreter(document, world).assignment(symbols)) != case["expected"][wi][index]
                               for wi, world in enumerate(case["worlds"])), "semantic mutation escaped independent check"
                    mutation_rejections += 1
            if case["name"] == "unicode-literals":
                assignment = Interpreter(document, case["worlds"][0]).assignment(symbols)
                unicode_symbols = [s["name"] for s in symbols if s["origin"]["kind"] == "text" and s["origin"]["value"] in {"é", "e\u0301"}]
                assert len(unicode_symbols) == 2
                assignment[unicode_symbols[1]] = assignment[unicode_symbols[0]]
                assert smt.evaluate(assignment) is False, "distinct Text literals may not collapse"
                mutation_rejections += 1
        print(f"{case['name']}: {len(actual_outputs)} actual queries matched independent worlds", flush=True)
    assert mutation_rejections == 3
    print(f"P3 semantic comparison passed: {queries} queries / {comparisons} assignments / {mutation_rejections} mutations; no solver or proof")


if __name__ == "__main__":
    main()
